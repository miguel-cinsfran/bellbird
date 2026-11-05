"""Los escenarios que no tienen un área propia: arranque, cierre, menús,
descargas, ayuda, actualizaciones e IA."""

from __future__ import annotations

import re
import time

from banco_app import (
    Aplicacion, RAIZ, Resultado, _textos_de, dialogo_nativo,
    mensaje_salir_es_de_chat, nombres_sin_daemon, pulsar_boton_nativo,
)
from banco_auditoria import auditar_dialogo, recorrer_tab, revisar_nombres
from guyrapu.core.config import APP_NAME

# ── Escenarios ───────────────────────────────────────────────────────────────

def escenario_arranque_frio(app: Aplicacion, args, res: Resultado):
    """¿Responde la ventana mientras libVLC se precalienta?

    Monta una aplicación aparte y la sondea desde el instante del lanzamiento.
    Esperar primero a que la ventana conteste no sirve: en una máquina con el
    caché de plugins caliente el precalentamiento ya terminó para entonces, y
    la medición llega tarde a lo único que quería medir.

    En el registro que mandó el amigo del dueño, del 19 al 21/08/2026, el hilo
    `ReproductorWarmup` tardó 56, 92 y 128 segundos, y los tres bloqueos más
    largos de la interfaz, de 10, 40 y 53 segundos, terminaron en el mismo
    segundo en que ese hilo terminaba. `reproductor.py:381` da por hecho que
    crear la instancia cuesta uno o dos segundos.

    Acá el disco está caliente, así que el número va a salir mucho más chico.
    Lo que se mira no es el número: es si mientras ese hilo vive la ventana
    deja o no de contestar. Si deja, el mecanismo está confirmado y en la
    máquina del amigo solo escala.
    """
    aparte = Aplicacion(app.anuncios_ruta.parent / "arranque")
    t0 = time.time()
    aparte.arrancar()
    try:
        primera = None
        muestras = []          # (t, latencia, contesto, hilos)
        vio_warmup = False
        while time.time() - t0 < 150:
            antes = time.time()
            try:
                r = aparte.pedir("ping", tiempo=2.0, tolerar=True)
                contesto = bool(r.get("ok"))
            except TimeoutError:
                contesto = False
            latencia = time.time() - antes
            vivos = []
            if contesto:
                if primera is None:
                    primera = antes - t0
                try:
                    vivos = aparte.hilos()
                except Exception:
                    vivos = []
            muestras.append((antes - t0, latencia, contesto, vivos))

            if "ReproductorWarmup" in vivos:
                vio_warmup = True
            elif vio_warmup and contesto:
                break          # el precalentamiento terminó
            elif (primera is not None and not vio_warmup
                  and antes - t0 > primera + 5):
                break          # nunca lo vimos: el caché estaba caliente
            if aparte.murio_sola():
                break
            time.sleep(0.1)

        if aparte.murio_sola() and primera is None:
            res.nota("arranque: la aplicación se cerró sola, casi seguro porque "
                     "ya había otra instancia abierta; este escenario necesita "
                     "la máquina para él solo")
            return
        if primera is None:
            res.fallo("arranque: la ventana no contestó ni una vez en 150 s")
            return

        res.nota("arranque: la ventana contesta por primera vez a los %.1f s"
                 % primera)

        # Solo cuentan las muestras posteriores a la primera respuesta: antes de
        # eso «no contesta» quiere decir «todavía no existe», que no es lo mismo
        # que estar congelada.
        utiles = [m for m in muestras if m[0] >= primera]
        peor_t, peor = max(((m[0], m[1]) for m in utiles), key=lambda x: x[1])
        durante = [m for m in utiles if "ReproductorWarmup" in m[3]]

        if not vio_warmup:
            res.nota("arranque: el precalentamiento de libVLC ya había terminado "
                     "antes de la primera respuesta; con el caché de plugins "
                     "caliente no se lo puede juzgar desde acá")
        else:
            ventana = durante[-1][0] - durante[0][0] if len(durante) > 1 else 0.0
            peor_dentro = max((m[1] for m in durante), default=0.0)
            res.nota("arranque: ReproductorWarmup vivo durante %.1f s, y la peor "
                     "respuesta mientras tanto fue de %.1f s"
                     % (ventana, peor_dentro))
            if peor_dentro > 2.0:
                res.fallo("arranque: la ventana estuvo %.1f s sin responder "
                          "mientras libVLC se precalentaba" % peor_dentro)

        res.nota("arranque: %d sondeos, peor respuesta %.1f s a los %.1f s"
                 % (len(utiles), peor, peor_t))
        if peor > 2.0 and not vio_warmup:
            res.fallo("arranque: la ventana estuvo %.1f s sin responder" % peor)
    finally:
        aparte.cerrar()


def escenario_principal(app: Aplicacion, args, res: Resultado):
    """La ventana con la que se encuentra alguien al abrir la aplicación."""
    app.pedir("frente")
    revisar_nombres(app.arbol(), res, "ventana principal")
    # Tab desde el frame no recorre nada: hay que empezar dentro, en un
    # control de verdad. En los diálogos no hace falta porque wx ya le da el
    # foco al primero al abrirlos.
    try:
        app.pedir("foco", nombre="Enlace del directo o vídeo")
    except Exception as exc:
        res.fallo(f"ventana principal: no pude enfocar el campo de enlace, {exc}")
    orden = recorrer_tab(app, res, "ventana principal", vueltas=12)
    res.nota(f"orden de Tab, {len(orden)} paradas: " + " > ".join(orden))

    n = len(app.anuncios)
    app.teclas(("f2",))
    if app.esperar_dicho("desconectado", segundos=8, desde=n):
        res.nota("F2 anuncia el estado")
    else:
        res.fallo("F2 no anunció nada en 8 segundos")


def _atajo_descargas() -> tuple[tuple, str]:
    """El atajo de fábrica para abrir el gestor de descargas.

    Se lee de `config_predeterminada`, la misma fuente de los valores de
    fábrica que usa la aplicación, y se nombra con `atajo_legible`, que ya
    usa el banco para los atajos de música. Así no va escrito a mano: con
    el mapa por familias pasó de Ctrl+S a Ctrl+Mayús+D. Devuelve el paso
    para `teclas` y el nombre legible para el informe.
    """
    texto = "ctrl+shift+d"
    try:
        from guyrapu.core import config_predeterminada
        texto = (config_predeterminada.obtener(
            "atajos", "descargas_abrir", texto) or texto)
    except Exception:
        pass
    try:
        from guyrapu.ui.atajos_captura import atajo_legible
        legible = atajo_legible(texto) or texto
    except Exception:
        legible = texto
    partes = (texto or "").strip().lower().replace(" ", "").split("+")
    tecla = partes[-1] if partes and partes[-1] else "d"
    mods = [p for p in partes[:-1] if p] or ["ctrl"]
    return (tecla, mods), legible


def escenario_descargas(app: Aplicacion, args, res: Resultado):
    """El gestor de descargas, que entró al repositorio sin que nadie lo abra."""
    paso_atajo, nombre_atajo = _atajo_descargas()
    app.pedir("frente")
    # El foco tiene que estar DENTRO de un control, no en el frame, o el
    # acelerador no llega. Sin esto el escenario pasaba o fallaba segun que
    # otro escenario se hubiera corrido antes, que es la peor clase de prueba.
    try:    app.pedir("foco", nombre="Enlace del directo o vídeo")
    except Exception: pass
    app.teclas(paso_atajo)
    dlg = app.esperar_ventana("Administrador de descargas", segundos=12)
    if dlg is None:
        res.fallo(f"{nombre_atajo} no abrió el gestor de descargas")
        return
    res.nota(f"{nombre_atajo} abre «{dlg['titulo']}», clase {dlg['clase']}")

    controles = app.arbol("Administrador de descargas")
    revisar_nombres(controles, res, "descargas")

    juntos = " ".join(
        ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        for c in controles).lower()
    for esperado in ("formato", "calidad", "lista de descargas", "cerrar",
                       "buscar o pegar enlace", "resultados de la búsqueda"):
        if esperado not in juntos:
            res.fallo(f"descargas: no aparece nada llamado «{esperado}»")

    orden = recorrer_tab(app, res, "descargas", vueltas=18)
    res.nota(f"descargas, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden))

    app.pedir("cerrar_ventana", ventana="Administrador de descargas")
    if app.esperar_ventana("Administrador de descargas", segundos=3) is None:
        res.nota("descargas: el diálogo cierra")
    else:
        res.fallo("descargas: el diálogo no cerró")


def escenario_diagnostico(app: Aplicacion, args, res: Resultado):
    """¿El diagnóstico se está anunciando por voz? No debería.

    Es la regresión que reportó el dueño: cada 30 segundos el lector le lee el
    censo de hilos, y cuando salta el vigilante de bloqueo, una traza entera.
    El censo va cada `INTERVALO_CENSO_HILOS_S`, que son 30, así que hay que
    escuchar más que eso o la prueba no puede fallar.
    """
    res.nota("escuchando 35 segundos, más que el intervalo del censo")
    fin = time.time() + 35
    while time.time() < fin:
        time.sleep(1.0)

    marcas = ("HILOS vivos", "HILO inicia", "HILO termina",
              "INTERFAZ bloqueada", "ENTORNO")
    fugas = [a for a in app.anuncios
             if a["canal"] in ("voz", "braille")
             and any(m in a["texto"] for m in marcas)]
    if fugas:
        res.fallo(f"el diagnóstico se anuncia por voz: {len(fugas)} veces")
        for a in fugas[:3]:
            res.fallo(f"  se dijo: {a['texto'][:70]}")
    else:
        res.nota("el diagnóstico no se anuncia por voz")




def escenario_menus(app: Aplicacion, args, res: Resultado):
    """Todos los ítems de menú: que tengan texto, atajo anunciable y estado."""
    items = app.menus()
    if not items:
        res.fallo("no se pudo leer la barra de menú")
        return
    hojas = [i for i in items if not i.get("submenu")]
    res.nota(f"{len(items)} entradas de menú, {len(hojas)} accionables")

    sin_texto = [i for i in items if not i["etiqueta"].strip()]
    for i in sin_texto:
        res.fallo(f"menú: una entrada sin texto en «{i['camino']}»")

    # Un ítem que promete atajo y otro que hace lo mismo sin prometerlo es una
    # inconsistencia que el usuario paga aprendiendo dos veces.
    con_atajo = [i for i in hojas if i["acelerador"]]
    res.nota(f"{len(con_atajo)} ítems anuncian atajo en su etiqueta")

    repetidos: dict[str, list[str]] = {}
    for i in con_atajo:
        repetidos.setdefault(i["acelerador"].lower(), []).append(i["camino"])
    for atajo, donde in repetidos.items():
        if len(donde) > 1:
            res.fallo(f"menú: el atajo {atajo} está en {len(donde)} sitios: "
                      + ", ".join(donde))

    apagados = [i["camino"] for i in hojas if not i["habilitado"]]
    res.nota(f"sin conexión hay {len(apagados)} ítems deshabilitados")
    if apagados:
        res.nota("  " + ", ".join(apagados[:8]))


def escenario_historial(app: Aplicacion, args, res: Resultado):
    """El historial de directos vistos."""
    auditar_dialogo(app, res, "Historial de directos", "Historial de directos",
                    vueltas_tab=12)


def escenario_ia(app: Aplicacion, args, res: Resultado):
    """La ventana Preguntar a la IA, abierta desde el menú Ver.

    Solo se abre, se audita y se cierra: no se envía nada, no se pulsa
    Agregar captura ni se toca la casilla. Agregar captura no se abre
    en el banco: necesita OBS.
    """
    res.nota("IA: no se envía nada, la ventana solo se audita. "
             "Agregar captura no se abre en el banco: necesita OBS")
    esperados = ("Conversación", "Mensaje",
                 "Enviar", "Agregar captura", "Copiar respuesta",
                 "Nueva conversación", "Cerrar")
    auditar_dialogo(
        app, res, "Preguntar a la IA sobre la imagen…", "Preguntar a la IA",
        vueltas_tab=14,
        esperados=esperados,
        esperados_en_tab=esperados)


def _estado_actualizacion_asentado(app: Aplicacion, titulo: str,
                                   segundos: float = 30.0) -> str:
    """Espera a que la ventana deje de decir que está buscando.

    Devuelve el texto del cuadro de estado, o cadena vacía si no se pudo
    leer. Si a los 30 segundos sigue buscando, se sigue igual con lo que
    haya: la búsqueda depende de la red, y una red lenta no es un defecto
    de la ventana.
    """
    estado = ""
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            controles = app.arbol(titulo)
        except Exception:
            time.sleep(0.5)
            continue
        for c in controles:
            if (c.get("nombre") or "") == "Estado":
                estado = c.get("valor") or ""
                break
        if estado and "buscando" not in estado.lower():
            break
        time.sleep(0.5)
    return estado


def _auditar_actualizacion(app: Aplicacion, res: Resultado, etiqueta_menu: str,
                           titulo: str) -> bool:
    """Abre una ventana de actualización, espera a que se asiente y la audita.

    Replica `auditar_dialogo`, con la espera en el medio: estas ventanas
    nacen buscando en un hilo aparte, y auditar en el primer instante mide
    la pantalla de espera, no la ventana. NUNCA pulsa el botón de acción:
    solo se cierra con `cerrar_ventana`.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu(etiqueta_menu)
    except Exception as exc:
        res.fallo(f"{titulo}: no se pudo disparar «{etiqueta_menu}», {exc}")
        return False

    dlg = app.esperar_ventana(titulo, segundos=15)
    if dlg is None:
        res.fallo(f"{titulo}: el menú no abrió ninguna ventana con ese título")
        return False
    res.nota(f"{titulo}: abre desde «{etiqueta_menu}», clase {dlg['clase']}")

    estado = _estado_actualizacion_asentado(app, titulo)
    if estado and "buscando" in estado.lower():
        res.nota(f"{titulo}: sigue buscando a los 30 s, se audita igual; "
                 f"dice «{estado[:70]}»")
    elif estado:
        res.nota(f"{titulo}: dice «{estado[:90]}»")
    else:
        res.nota(f"{titulo}: no se pudo leer el cuadro de estado")

    controles = app.arbol(titulo)
    revisar_nombres(controles, res, titulo)

    juntos = " ".join(
        ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        for c in controles).replace("&", "").lower()
    for e in ("Estado", "Progreso", "Novedades", "Cerrar"):
        if e.lower() not in juntos:
            res.fallo(f"{titulo}: no aparece nada llamado «{e}»")

    orden = recorrer_tab(app, res, titulo, vueltas=10, ventana=titulo)
    res.nota(f"{titulo}, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden))

    app.pedir("cerrar_ventana", ventana=titulo)
    if app.esperar_ventana(titulo, segundos=4) is not None:
        res.fallo(f"{titulo}: el diálogo no cerró")
    return True


def escenario_actualizaciones(app: Aplicacion, args, res: Resultado):
    """Las dos ventanas de actualización, que nadie recorría.

    Las dos usan el mismo `DialogoActualizacion` genérico: estado, progreso,
    novedades y cerrar. Cada una busca en un hilo aparte nada más abrir, así
    que se espera a que el estado se asiente antes de auditar. La búsqueda de
    yt-dlp puede dejar un binario preparado si hay versión nueva, pero
    instalarlo pide el botón de acción y ese no se pulsa nunca.
    """
    _auditar_actualizacion(app, res, "Buscar actualizaciones",
                           "Buscar actualizaciones")
    _auditar_actualizacion(app, res, "Actualizar yt-dlp", "Actualizar yt-dlp")


def escenario_ayuda(app: Aplicacion, args, res: Resultado):
    """El menú Ayuda, que abre ventanas de texto largo."""
    items = [i for i in app.menus()
             if not i.get("submenu") and i["camino"].startswith("Ayuda")]
    if not items:
        res.fallo("ayuda: el menú no tiene entradas accionables")
        return
    res.nota(f"ayuda: {len(items)} entradas: "
             + ", ".join(i["etiqueta"] for i in items))
    for i in items:
        if not i["habilitado"]:
            res.fallo(f"ayuda: «{i['etiqueta']}» está deshabilitado sin motivo")


def escenario_dialogos_ayuda(app: Aplicacion, args, res: Resultado):
    """Las tres entradas del menú Ayuda, que son de tres tipos distintos.

    Y esa es la lección: dar por hecho que un ítem de menú «abre una ventana»
    es lo que hizo que la primera versión de este escenario dijera que ninguno
    de los tres abría nada. Uno abre el navegador, otro solo anuncia, y el
    tercero abre un cuadro nativo que wx no lista.
    """
    # 1. Marcar incidencia: no abre nada, anuncia. Se comprueba el anuncio.
    app.pedir("frente")
    n = len(app.anuncios)
    try:
        app.abrir_por_menu("Marcar incidencia")
    except Exception as exc:
        res.fallo(f"Marcar incidencia: no se pudo disparar, {exc}")
    else:
        if app.esperar_dicho("incidencia", segundos=8, desde=n):
            res.nota("«Marcar incidencia» anuncia que se guardó")
        else:
            res.fallo("«Marcar incidencia» no anunció nada, y es su única "
                      "señal: no abre ventana ni hace ruido")

    # 2. Acerca de: cuadro nativo, invisible para wx.
    app.pedir("frente")
    try:
        app.abrir_por_menu("Acerca de")
    except Exception as exc:
        res.fallo(f"Acerca de: no se pudo disparar, {exc}")
        return
    dlg = dialogo_nativo("Acerca de", segundos=8)
    if dlg is None:
        res.fallo("«Acerca de» no abrió ningún cuadro que Windows exponga")
    else:
        textos, botones = [], []
        try:
            for d in dlg.descendants():
                try:
                    rol = d.element_info.control_type
                    nombre = (d.element_info.name or "").strip()
                except Exception:
                    continue
                if rol == "Text" and nombre:
                    textos.append(nombre)
                elif rol == "Button" and nombre:
                    botones.append(nombre)
        except Exception:
            pass
        res.nota(f"«Acerca de» abre un cuadro nativo con {len(textos)} textos "
                 f"y botones: {', '.join(botones) or 'ninguno'}")
        _version_coherente(textos, res)
        for x in textos[:3]:
            res.nota("  dice: " + x[:70])
        if not textos:
            res.fallo("«Acerca de»: el cuadro no expone ningún texto, así que "
                      "un lector de pantalla no tiene qué leer")
        try:
            dlg.type_keys("{ESC}")
        except Exception:
            try:    dlg.close()
            except Exception: pass
        time.sleep(0.8)

    # 3. La guía de la API abre el NAVEGADOR. No se dispara salvo que se pida.
    if getattr(args, "con_navegador", False):
        app.pedir("frente")
        app.abrir_por_menu("Guía de configuración de la API")
        res.nota("«Guía de configuración de la API» abrió el navegador")
    else:
        res.nota("«Guía de configuración de la API» abre el navegador con "
                 "`webbrowser.open`; se salta para no llenar de pestañas la "
                 "máquina de quien corre las pruebas. Usá --con-navegador.")



def _version_coherente(textos: list, res: Resultado) -> None:
    """La version que la aplicacion MUESTRA contra la que documenta el CHANGELOG.

    Nadie vigilaba esto: comprobado el 26/08/2026, ninguna prueba mira
    `APP_VERSION`, asi que se podia publicar una version con el numero mal y el
    unico sintoma seria que el «Acerca de» dijera una cosa y las novedades
    otra. Quien lo sufre es el que descarga el ZIP y no sabe que tiene.
    """
    mostrada = ""
    for x in textos:
        m = re.search(rf"{re.escape(APP_NAME)}\s+(\d+\.\d+\.\d+)", x)
        if m:
            mostrada = m.group(1)
            break
    if not mostrada:
        res.fallo("«Acerca de» no muestra ningun numero de version")
        return

    try:
        texto = (RAIZ / "docs" / "es" / "CHANGELOG.md").read_text(encoding="utf-8")
    except Exception as exc:
        res.nota(f"no se pudo leer CHANGELOG.md: {exc}")
        return
    # La entrada mas nueva suele ser un trabajo en curso marcado "sin
    # publicar". Esa no cuenta como publicada: se compara con la primera
    # entrada publicada. Si la aplicacion ya dice la sin publicar, tambien
    # es coherente, porque es el momento de publicar.
    entradas = re.findall(r"^##\s*(\d+\.\d+\.\d+)(.*)$", texto,
                          re.MULTILINE)
    sin_publicar = next((v for v, resto in entradas
                         if "sin publicar" in resto.lower()), "")
    documentada = next((v for v, resto in entradas
                        if "sin publicar" not in resto.lower()), "")
    if not documentada:
        res.fallo("CHANGELOG.md no tiene ninguna entrada de version publicada")
    elif mostrada == documentada:
        res.nota(f"version coherente: la aplicacion dice {mostrada} y la "
                 f"ultima entrada publicada del CHANGELOG es {documentada}")
    elif sin_publicar and mostrada == sin_publicar:
        res.nota(f"version coherente: la aplicacion dice {mostrada}, que es "
                 f"la entrada sin publicar; la ultima publicada es {documentada}")
    else:
        res.fallo("la aplicacion dice v%s y la ultima entrada publicada del "
                  "CHANGELOG es %s" % (mostrada, documentada))


def avisos_wx(lineas):
    """Filtra de la salida de error las líneas que son avisos de wx.

    Recibe las líneas tal cual, sin recortar. No cuenta las líneas del
    registro de la app (empiezan con HH:MM:SS y dos espacios) ni las de
    una traza de Python, desde 'Traceback (most recent call last):'
    hasta su línea final de excepción inclusive.
    """
    marcas = ("should be created as child", "failed with error", "Assert",
              "wxWidgets", "Warning:", "Error:")
    avisos = []
    en_traza = False
    for cruda in lineas:
        linea = cruda.strip()
        if not linea:
            continue
        if linea.startswith("Traceback (most recent call last):"):
            en_traza = True
            continue
        if en_traza:
            if cruda[0].isspace():
                continue
            en_traza = False
            continue
        if re.match(r"\d\d:\d\d:\d\d  ", linea):
            continue
        if any(m in linea for m in marcas):
            avisos.append(linea)
    return avisos


def escenario_avisos_wx(app: Aplicacion, args, res: Resultado):
    """Lo que wx escribe por la salida de error y nadie lee nunca.

    wxWidgets avisa por ahí de widgets mal construidos, de jerarquías que no
    corresponden y de llamadas que fallan. En uso normal esa salida se pierde,
    porque la aplicación se lanza sin consola. Acá se captura y se mira.

    No todo aviso es un defecto, pero un aviso que se repite en cada arranque
    y que nadie ha leído nunca merece por lo menos una mirada.
    """
    # Se recorre un poco de interfaz para que salgan los avisos de construir
    # paneles, no solo los del arranque.
    app.pedir("frente")
    app.simular_sesion_youtube()
    app.mensaje("Ana", "hola")
    time.sleep(2.0)

    if not app.salida_ruta.exists():
        res.fallo("no se capturó la salida de la aplicación")
        return
    crudo = app.salida_ruta.read_text(encoding="utf-8", errors="replace")
    avisos = avisos_wx(crudo.splitlines())

    # Se agrupan, porque el mismo aviso sale muchas veces y en bruto tapa todo.
    resumen = {}
    for a in avisos:
        clave = a[:110]
        resumen[clave] = resumen.get(clave, 0) + 1

    if not resumen:
        res.nota("wx no escribió ningún aviso")
        return
    res.nota(f"wx escribió {len(avisos)} avisos, {len(resumen)} distintos")
    for texto, veces in sorted(resumen.items(), key=lambda x: -x[1])[:6]:
        res.fallo(f"aviso de wx x{veces}: {texto}")


def escenario_cierre(app: Aplicacion, args, res: Resultado):
    """Cerrar la ventana con una sesion abierta.

    Cierra la instancia PRINCIPAL, no una aparte, y por eso va el ultimo de la
    corrida completa. No se puede levantar una segunda: `main.py` tiene guarda
    de instancia unica, avisa y se cierra sola. Costo una corrida descubrirlo.

    Lo que esto NO prueba, y conviene decirlo en vez de dar por cubierto lo que
    no lo esta: aca la sesion esta simulada y NO hay hilos de captura de verdad
    girando, que es justamente el caso que se sospecha del cierre con Alt+F4.
    Ese sigue SIN PROBAR y necesita un directo real.
    """
    app.pedir("frente")
    app.simular_sesion_youtube(titulo="Prueba de cierre")
    app.mensaje("Ana", "hola")
    time.sleep(1.5)
    hilos = app.hilos_con_daemon()
    nombres = sorted(hilo["nombre"] for hilo in hilos)
    sin_daemon = nombres_sin_daemon(hilos)
    res.nota("cierre: antes de cerrar hay %d hilos: %s"
             % (len(hilos), ", ".join(nombres[:8])))

    arranque = time.time()
    try:
        # Sin forzar, como un Alt+F4: el cierre se puede vetar y la
        # aplicación pregunta «Salir».
        app.pedir("cerrar_ventana", tiempo=6.0, forzar=False)
    except Exception:
        pass  # el cuadro modal se come la respuesta, como en directo_sin_imagen
    dlg = dialogo_nativo("Salir", segundos=8)
    if dlg is None:
        res.fallo("cierre: con una sesión abierta no apareció la pregunta "
                  "«Salir» en 8 s")
    else:
        textos = _textos_de(dlg)
        if not mensaje_salir_es_de_chat(textos):
            res.fallo("cierre: la pregunta «Salir» no trae el mensaje del chat "
                      "conectado: %s" % " / ".join(textos[:2]))
        elif not pulsar_boton_nativo(dlg, "Sí"):
            res.fallo("cierre: la pregunta «Salir» no ofrece ningún botón «Sí»")
        else:
            res.nota("cierre: apareció la pregunta «Salir» con el mensaje del "
                     "chat conectado y se contestó Sí")
            limite = time.time() + 4.0
            while time.time() < limite:
                if dialogo_nativo("Salir", segundos=1.0) is None:
                    break
                time.sleep(0.3)
    limite = time.time() + 20
    murio = False
    while time.time() < limite:
        if app.murio_sola():
            murio = True
            break
        time.sleep(0.5)
    tardanza = time.time() - arranque

    if not murio:
        res.fallo("cierre: la aplicacion no cerro en 20 s con una sesion "
                  "abierta; hilos que no eran daemon: "
                  + (", ".join(sin_daemon) or "ninguno"))
        return
    res.nota("cierre: la aplicacion cerro sola en %.1f s" % tardanza)
    # `apagado.TOPE_ESPERA_CIERRE` son 3 segundos. Con margen para que arranque
    # el proceso de cierre, mas de 10 significa que algo se quedo esperando.
    if tardanza > 10:
        res.fallo("cierre: tardo %.1f s, y el tope de espera de las capturas "
                  "es de %.0f s" % (tardanza, 3.0))
    if app.dijo("cerrando"):
        res.nota("cierre: se anuncia antes de cerrar")
    else:
        res.nota("cierre: SIN COMPROBAR que se anuncie; no aparece «cerrando» "
                 "entre lo grabado")

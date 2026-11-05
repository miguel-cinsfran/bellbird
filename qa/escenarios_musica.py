"""Escenarios de música y del reproductor."""

from __future__ import annotations

import re
import time
from pathlib import Path

from banco_app import (
    Aplicacion, DIRECTO_YOUTUBE, OrdenRechazada, Resultado, VentanaNoActiva,
    conectar_de_verdad, contestar_salir_si_aparece, subarbol,
)
from banco_auditoria import auditar_dialogo, recorrer_tab

try:
    import medidor_sonido  # noqa: E402
except Exception:
    medidor_sonido = None

# Cuánto puede tardar una acción del reproductor antes de que se note. Medio
# segundo no lo percibe nadie; a partir de uno la ventana ya "va dura", y por
# encima de dos, sin ver la pantalla, no se sabe si la tecla entró.
BLOQUEO_SOSPECHOSO = 1.0
BLOQUEO_INACEPTABLE = 2.0
# Y cuánto puede tardar en hablar. Un anuncio que llega tarde es peor que uno
# que no llega: para entonces la persona ya pulsó otra cosa.
VOZ_LENTA = 1.5


def medir_accion(app: Aplicacion, hacer, espera: float = 3.0):
    """Hace algo y mide las dos cosas que producen «torpeza».

    La primera es cuánto tarda la ventana en volver a atender a nadie. Como la
    sonda despacha con `wx.CallAfter`, un `ping` que vuelve es la prueba de que
    el hilo de interfaz está libre otra vez; lo que tarde en volver es tiempo
    en el que la aplicación no responde a una tecla.

    La segunda es cuánto tarda en decir algo. Devuelve
    `(bloqueo, latencia_de_voz, lo_que_dijo)`, con la latencia en `None` si no
    llegó a hablar.
    """
    # Esperar a que la aplicación se calle ANTES de actuar. Si no, el primer
    # anuncio que llegue se le atribuye a la acción, y con una carga en vuelo
    # eso mide la red y no el control. El 21/08/2026 esto produjo tres fallos
    # contra un directo real que en la corrida siguiente no aparecieron.
    quieto = time.time() + 8
    ultimo = len(app.anuncios)
    calma = time.time() + 0.6
    while time.time() < quieto and time.time() < calma:
        if len(app.anuncios) != ultimo:
            ultimo = len(app.anuncios)
            calma = time.time() + 0.6
        time.sleep(0.05)

    antes = len(app.anuncios)
    t0 = time.time()
    hacer()
    app.pedir("ping", tiempo=120)
    bloqueo = time.time() - t0

    latencia = None
    limite = time.time() + espera
    while time.time() < limite:
        if any(a["canal"] == "voz" for a in app.anuncios[antes:]):
            latencia = time.time() - t0
            break
        time.sleep(0.05)
    dichos = [a["texto"] for a in app.anuncios[antes:] if a["canal"] == "voz"]
    return bloqueo, latencia, dichos


def juzgar_accion(res: Resultado, donde: str, que: str, medida) -> bool:
    """Convierte una medida en veredicto. Devuelve si habló."""
    bloqueo, latencia, dichos = medida
    if not dichos:
        res.fallo(f"{donde}: {que} no dice nada")
        hablo = False
    else:
        hablo = True
        detalle = dichos[0][:58]
        if latencia is not None and latencia > VOZ_LENTA:
            res.fallo(f"{donde}: {que} tarda {latencia:.1f} s en decir "
                      f"«{detalle}»")
        else:
            res.nota(f"{donde}: {que} dice «{detalle}»"
                     + (f", a los {latencia:.2f} s" if latencia else ""))

    if bloqueo > BLOQUEO_INACEPTABLE:
        res.fallo(f"{donde}: {que} deja la ventana {bloqueo:.1f} s sin responder")
    elif bloqueo > BLOQUEO_SOSPECHOSO:
        res.nota(f"{donde}: ojo, {que} tarda {bloqueo:.1f} s en devolver la "
                 f"ventana")
    return hablo


# Los seis botones de transporte, por la etiqueta con la que se los encuentra.
BOTONES_REPRODUCTOR = (
    ("Reproducir", "el botón de reproducir"),
    ("Retroceder 1 min", "el botón de retroceder"),
    ("Avanzar 1 min", "el botón de avanzar"),
    ("Detener", "el botón de detener"),
    ("Silenciar audio", "el botón de silenciar"),
    ("Pantalla completa", "el botón de pantalla completa"),
)

# Y los atajos, que son el camino que de verdad usa quien no ve la pantalla:
# `AGENTS.md` cuenta que los botones vienen ocultos justamente porque se maneja
# por teclado. Son los de `config.ATAJOS_DEFAULTS`, área Ctrl.
ATAJOS_REPRODUCTOR = (
    (("p", ["ctrl"]), "Ctrl+P, reproducir o pausa"),
    (("left", ["ctrl"]), "Ctrl+Izquierda, retroceder"),
    (("right", ["ctrl"]), "Ctrl+Derecha, avanzar"),
    (("m", ["ctrl"]), "Ctrl+M, silenciar"),
    (("up", ["ctrl"]), "Ctrl+Arriba, subir volumen"),
    (("down", ["ctrl"]), "Ctrl+Abajo, bajar volumen"),
    (("d", ["ctrl"]), "Ctrl+D, detener"),
)


def bateria_reproductor(app: Aplicacion, res: Resultado, donde: str,
                        hay_medio: bool = False) -> None:
    """Maltrata el reproductor entero y mide cada golpe.

    Se usa dos veces: sin nada cargado, que es como arranca la aplicación, y
    contra un directo de verdad desde `escenario_directo_youtube`. Las dos
    situaciones tienen que hablar; la segunda además tiene que ser rápida.
    `hay_medio` lo dice quien llama, que es quien cargó el medio: sin vídeo
    el volumen con flechas tiene que avisar y no moverse, con vídeo se mueve
    en silencio.
    """
    # ── los seis botones ────────────────────────────────────────────────────
    for etiqueta, quien in BOTONES_REPRODUCTOR:
        medida = medir_accion(app, lambda e=etiqueta: app.pedir("pulsar", nombre=e))
        juzgar_accion(res, donde, quien, medida)

        # Pantalla completa abre una ventana nueva que se queda con el foco y
        # con el teclado. Hay que volver, o todo lo que se mida después se mide
        # sobre la ventana equivocada.
        if etiqueta == "Pantalla completa":
            ctrl = app.foco() or {}
            nombre = (ctrl.get("nombre") or ctrl.get("etiqueta") or "").strip()
            if not nombre:
                res.fallo(f"{donde}: en pantalla completa el foco queda en un "
                          f"control sin nombre ({ctrl.get('clase')})")
            else:
                res.nota(f"{donde}: en pantalla completa el foco va a «{nombre}»")
            medida = medir_accion(
                app, lambda e=etiqueta: app.pedir("pulsar", nombre=e))
            juzgar_accion(res, donde, "salir de pantalla completa", medida)
            ctrl = app.foco() or {}
            nombre = (ctrl.get("nombre") or ctrl.get("etiqueta") or "").strip()
            if not nombre:
                res.fallo(f"{donde}: al salir de pantalla completa el foco "
                          f"queda en el aire ({ctrl.get('clase')})")
            else:
                res.nota(f"{donde}: al salir, el foco vuelve a «{nombre}»")

    # ── dos pulsaciones seguidas, que es lo que hace cualquiera cuando la
    #    primera no contestó ─────────────────────────────────────────────────
    app.pedir("pulsar", nombre="Reproducir")
    medida = medir_accion(app, lambda: app.pedir("pulsar", nombre="Reproducir"))
    if not medida[2]:
        res.fallo(f"{donde}: pulsar reproducir dos veces seguidas deja la "
                  f"segunda muda")
    else:
        res.nota(f"{donde}: la segunda pulsación de reproducir también habla")

    # ── los siete atajos ────────────────────────────────────────────────────
    # Antes de juzgar los atajos hay que saber si el menú que los sostiene está
    # encendido. `gui.py:1769` apaga el menú Reproductor entero mientras no hay
    # conexión (`mb.EnableTop`), y un menú apagado se lleva por delante a sus
    # siete aceleradores aunque cada ítem se declare habilitado. Sin esto, el
    # banco daba siete atajos por rotos cuando lo que pasaba es que estaban
    # apagados a propósito.
    menu_vivo = None
    for m in app.menus():
        if m["camino"].strip().lower() == "reproductor":
            menu_vivo = bool(m.get("habilitado"))
            break
    if menu_vivo is False:
        res.nota(f"{donde}: el menú Reproductor está apagado, así que sus siete "
                 f"atajos no pueden funcionar")
        # Y ahí está lo que sí es un defecto: los botones de la ventana siguen
        # encendidos y respondiendo. Dos caminos para lo mismo, uno vivo y otro
        # muerto, sin que nada se lo diga a quien no ve la pantalla.
        encendidos = [c.get("etiqueta") or c.get("nombre")
                      for c in app.arbol()
                      if c.get("clase") in ("Button", "BitmapButton")
                      and c.get("habilitado") and c.get("en_pantalla")
                      and (c.get("etiqueta") or "") in
                      [e for e, _ in BOTONES_REPRODUCTOR]]
        if encendidos:
            res.fallo(f"{donde}: con el menú Reproductor apagado, sus atajos no "
                      f"hacen nada pero estos botones siguen encendidos y "
                      f"funcionando: " + ", ".join(encendidos))

    # Los aceleradores solo llegan si el foco está DENTRO de un control, no en
    # el frame. Se ancla a propósito para que el resultado no dependa de dónde
    # lo haya dejado la comprobación anterior.
    for candidato in ("Volumen del reproductor", "Enlace del directo o vídeo", "Chat del directo"):
        try:
            app.pedir("foco", nombre=candidato)
            break
        except OrdenRechazada:
            continue

    for combo, quien in ATAJOS_REPRODUCTOR:
        try:
            medida = medir_accion(app, lambda c=combo: app.teclas(c))
        except VentanaNoActiva as exc:
            res.no_probado(f"{donde}: no se pudo probar {quien}, {exc}")
            continue
        if menu_vivo is False:
            if medida[2]:
                res.nota(f"{donde}: {quien} habla aun con el menú apagado")
            continue
        juzgar_accion(res, donde, quien, medida)

    # ── los dos deslizadores, con las flechas ───────────────────────────────
    # La posición anuncia; el volumen NO, a propósito desde el 15/10: NVDA
    # ya lee el valor del deslizador y se oía dos veces. La excepción, a
    # propósito desde el 19/10/2026: sin vídeo cargado `ajustar_volumen`
    # avisa «No hay ningún vídeo cargado» y no cambia nada.
    try:
        app.pedir("foco", nombre="Posición de reproducción")
    except OrdenRechazada as exc:
        res.fallo(f"{donde}: no se llega a la posición, {exc}")
    else:
        for tecla in ("right", "left"):
            try:
                medida = medir_accion(app, lambda t=tecla: app.teclas(t))
            except VentanaNoActiva as exc:
                res.no_probado(f"{donde}: no se pudo probar la posición, {exc}")
                break
            juzgar_accion(res, donde, f"la posición con la flecha {tecla}",
                          medida)
    try:
        app.pedir("foco", nombre="Volumen del reproductor")
    except OrdenRechazada as exc:
        res.fallo(f"{donde}: no se llega al volumen, {exc}")
    else:
        for tecla in ("up", "down"):
            previo = _valor_deslizador(app, "Volumen del reproductor")
            try:
                medida = medir_accion(app, lambda t=tecla: app.teclas(t))
            except VentanaNoActiva as exc:
                res.no_probado(f"{donde}: no se pudo probar el volumen, {exc}")
                break
            _juzgar_volumen_silencioso(app, res, donde, tecla, medida, previo,
                                     hay_medio)


def _valor_deslizador(app: Aplicacion, nombre: str):
    """El valor de un deslizador, leído con la sonda. None si no se pudo."""
    objetivo = (nombre or "").strip().lower()
    try:
        controles = app.arbol()
    except Exception:
        return None
    for c in controles:
        if c.get("clase") != "Slider":
            continue
        junto = ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        if objetivo in junto.strip().lower():
            return c.get("valor")
    return None


def _juzgar_volumen_silencioso(app: Aplicacion, res: Resultado, donde: str,
                               tecla: str, medida, previo,
                               hay_medio: bool = False) -> None:
    """El volumen con flechas no anuncia y tiene que mover el deslizador.

    Sin vídeo cargado es al revés, a propósito desde el 19/10/2026:
    `ajustar_volumen` avisa «No hay ningún vídeo cargado» y no cambia nada.
    """
    bloqueo, _latencia, dichos = medida
    if hay_medio:
        if dichos:
            res.fallo(f"{donde}: el volumen con la flecha {tecla} anuncia "
                      f"«{dichos[0][:58]}», y no debería: NVDA ya lee el valor "
                      "del deslizador")
        else:
            res.nota(f"{donde}: el volumen con la flecha {tecla} no anuncia, "
                     "a propósito")
    elif any("No hay ningún vídeo cargado" in d for d in dichos):
        res.nota(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                 "avisa «No hay ningún vídeo cargado»")
    elif dichos:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  f"anuncia «{dichos[0][:58]}» en vez de avisar "
                  "«No hay ningún vídeo cargado»")
    else:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  "no avisa «No hay ningún vídeo cargado»")
    if bloqueo > BLOQUEO_INACEPTABLE:
        res.fallo(f"{donde}: el volumen con la flecha {tecla} deja la ventana "
                  f"{bloqueo:.1f} s sin responder")
    elif bloqueo > BLOQUEO_SOSPECHOSO:
        res.nota(f"{donde}: ojo, el volumen con la flecha {tecla} tarda "
                 f"{bloqueo:.1f} s en devolver la ventana")
    posterior = _valor_deslizador(app, "Volumen del reproductor")
    if previo is None or posterior is None:
        res.nota(f"{donde}: la sonda no leyó el valor del deslizador, así que "
                 f"el cambio con la flecha {tecla} queda sin comprobar")
    elif hay_medio:
        if posterior == previo:
            res.fallo(f"{donde}: el volumen con la flecha {tecla} no movió el "
                      f"deslizador (sigue en {previo})")
        else:
            res.nota(f"{donde}: el volumen con la flecha {tecla} mueve el "
                     f"deslizador de {previo} a {posterior}")
    elif posterior != previo:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  f"movió el deslizador de {previo} a {posterior}, "
                  "y no debería")
    else:
        res.nota(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                 f"deja el deslizador en {previo}, a propósito")


def escenario_reproductor(app: Aplicacion, args, res: Resultado):
    """El reproductor sin nada cargado, que es como arranca la aplicación.

    Nunca lo probó nadie: `reproductor.py` son 1.059 líneas con cinco pruebas,
    y las cinco son del parser de atajos. El recorrido de Tab lo pasaba de largo
    porque los seis botones vienen ocultos de fábrica.

    Va primero de todos los escenarios y no es capricho: en cuanto `chat` o
    `tiktok` simulan una sesión, el estado «sin nada cargado» no vuelve sin
    reiniciar, y el botón de reproducir pasa la comprobación por el motivo
    equivocado.

    La regla que se comprueba no admite matices: un control que se activa y no
    dice nada es indistinguible, para quien no ve la pantalla, de una
    aplicación colgada. Y uno que tarda dos segundos en contestar, también.
    """
    if not app.al_frente():
        res.nota("reproductor: Windows no puso la ventana al frente")

    # Sin python-vlc el panel no se construye: en su lugar va un aviso de una
    # línea. Juzgar los botones ahí daría seis fallos de accesibilidad que en
    # realidad son una dependencia que falta.
    todo = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                    for c in app.arbol())
    if "AvisoReproductor" in todo or "no disponible" in todo.lower():
        res.nota("reproductor: no hay panel; falta VLC o yt-dlp en este "
                 "entorno, así que no se juzga nada. Correlo con el intérprete "
                 "del proyecto, .venv/Scripts/python.exe")
        return

    # Los botones vienen ocultos («minimalista»), y ocultos wx los saca del
    # recorrido de Tab. Hay que mostrarlos para poder probarlos como los prueba
    # una persona. Se anota cómo estaban para dejarlo igual al terminar.
    # Se pregunta por la etiqueta del propio interruptor, que dice «Ocultar…»
    # cuando están visibles y «Mostrar…» cuando no. Mirar `en_pantalla` de los
    # botones no sirve: `IsShownOnScreen` da falso también cuando la ventana
    # está tapada o minimizada, y entonces el banco creía que estaban ocultos,
    # los ocultaba, y encima le dejaba la preferencia cambiada al dueño.
    estaban_visibles = any(
        (c.get("etiqueta") or "").lower().startswith("ocultar botones")
        for c in app.arbol())
    if not estaban_visibles:
        medida = medir_accion(
            app, lambda: app.pedir("pulsar", nombre="AlternarBotonesReproductor"))
        juzgar_accion(res, "reproductor", "mostrar los botones", medida)

    faltan = []
    visibles = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                        for c in app.arbol()).lower()
    for etiqueta, quien in BOTONES_REPRODUCTOR:
        if etiqueta.lower() not in visibles:
            faltan.append(quien)
    if faltan:
        res.fallo("reproductor: no aparecen " + ", ".join(faltan))
        return

    bateria_reproductor(app, res, "reproductor")

    orden = recorrer_tab(app, res, "reproductor", vueltas=12)
    res.nota("reproductor, orden de Tab, %d paradas: %s"
             % (len(orden), " > ".join(orden)))

    # Dejarlo como estaba: el banco no puede cambiarle la ventana al dueño. La
    # visibilidad de los botones se guarda en `config.ini`, así que sin esto
    # cada corrida le deja la aplicación distinta de como la encontró.
    if not estaban_visibles:
        app.pedir("pulsar", nombre="AlternarBotonesReproductor")


def escenario_musica(app: Aplicacion, args, res: Resultado):
    """La ventana de música, abierta por sus dos entradas del menú.

    Sin carpeta ningún control queda deshabilitado: «Cambiar carpeta» solo
    se apaga mientras carga y `_al_biblioteca` lo vuelve a habilitar, así
    que los ocho entran en el orden de Tab. No se pulsa Reproducir ni
    ningún atajo de reproducción, y si la configuración trae una carpeta de
    música real no se toca: la ventana solo se abre, se audita y se cierra.
    """
    res.nota("Música: no se reproduce nada, la ventana solo se audita")
    esperados = ("Colecciones", "Buscar en la música", "Mostrar filtros",
                  "Canciones", "Mostrar cola", "Abrir enlace", "Nueva lista",
                 "Cambiar carpeta", "Cerrar")
    auditar_dialogo(
        app, res, "Elegir música…", "Música",
        vueltas_tab=14,
        esperados=esperados,
        esperados_en_tab=esperados)


def agujas_unicas(nombres, indice, tope=6):
    """Búsquedas cortas que solo encuentran al tema elegido.

    Las candidatas salen de las palabras del nombre sin extensión, de la
    palabra sola al nombre entero. Se comprueban con la misma regla del
    buscador de la aplicación: cada palabra buscada empieza una palabra del
    nombre, título, artista o álbum.
    """
    from bellbird.music.biblioteca import coincide_por_palabras
    if tope <= 0:
        return []
    nombres_sin_extension = [Path(nombre).stem for nombre in nombres]
    palabras = re.findall(r"[^\W_]+", nombres_sin_extension[indice])
    candidatas = []
    for cantidad in range(1, len(palabras) + 1):
        for inicio in range(len(palabras) - cantidad + 1):
            aguja = " ".join(palabras[inicio:inicio + cantidad])
            if aguja not in candidatas:
                candidatas.append(aguja)
    agujas = []
    for aguja in candidatas:
        encontrados = [
            i for i, nombre in enumerate(nombres_sin_extension)
            if coincide_por_palabras(aguja, [nombre])]
        if encontrados == [indice]:
            agujas.append(aguja)
            if len(agujas) >= tope:
                break
    return agujas


def aguja_grupo(nombres, incluidos, excluidos):
    """La palabra común que encuentra a todo el grupo y a ningún excluido.

    Se comprueba con la misma regla del buscador de la aplicación, así una
    palabra que solo es prefijo de otra no sirve para aislar el grupo.
    """
    import re
    from bellbird.music.biblioteca import coincide_por_palabras
    nombres_sin_extension = [Path(nombre).stem for nombre in nombres]
    comunes = set.intersection(*[
        set(re.findall(r"[^\W_]+", nombres_sin_extension[i]))
        for i in incluidos])
    for aguja in sorted(comunes, key=lambda palabra: (-len(palabra), palabra)):
        if len(aguja) < 2:
            continue
        if not all(coincide_por_palabras(aguja, [nombres_sin_extension[i]])
                   for i in incluidos):
            continue
        if any(coincide_por_palabras(aguja, [nombres_sin_extension[i]])
               for i in excluidos):
            continue
        return aguja
    return None


def escenario_musica_real(app: Aplicacion, args, res: Resultado):
    """Música real de punta a punta, con archivos y sonido de verdad.

    Prepara una carpeta temporal con 5 temas de la música del usuario más
    un tono corto generado, respalda la configuración y las listas, fija
    volumen 40 y corre cada comando de música comprobando con el medidor
    de sonido de Windows que de verdad empieza, se pausa, sigue y se
    detiene. Al terminar deja los datos del usuario exactamente como
    estaban. Usa `tecla_en` y `menu_contextual` para disparar las acciones
    de la ventana nueva por su cableado real, filtra por el buscador, que
    deja el tema aislado seleccionado, y elige lo demás por posición por
    defecto.
    Corre ANTES de lanzar la aplicación compartida (como `arranque_frio`),
    porque la configuración se escribe antes de arrancar.
    """

    import array
    import configparser
    import math
    import random
    import re
    import shutil
    import tempfile
    import wave
    from bellbird.core import paths
    from bellbird.core.config import (
        codificar_texto_ini, decodificar_texto_ini, guardar_opciones)
    from bellbird.music import anuncios as anuncios_musica
    from bellbird.music import enlaces as enlaces_musica
    from bellbird.music import listas as listas_musica
    from bellbird.music import vista as vista_musica
    from bellbird.music.biblioteca import EXTENSIONES
    from tests.test_musica_enlaces import LISTA as _LISTA_PRUEBA
    from tests.test_musica_enlaces import VIDEO as _VIDEO_PRUEBA

    class _Corte(Exception):
        """La escena no puede seguir (el fallo ya quedó anotado)."""

    _NOMBRE_LISTA = "QA música real"
    _TOPE_RECORRIDO = 6 * 60
    _URL_VIDEO = f"https://www.youtube.com/watch?v={_VIDEO_PRUEBA}"
    _URL_LISTA = ("https://www.youtube.com/playlist"
                  f"?list={_LISTA_PRUEBA}")

    def _corta(texto):
        res.fallo(texto)
        raise _Corte()

    if medidor_sonido is None or not medidor_sonido.DISPONIBLE:
        res.no_probado("musica_real: sin medidor de sonido en esta PC")
        return

    # ── Origen: carpeta pedida, la de la configuración o la del usuario ──

    pedida = (getattr(args, "carpeta_musica", None) or "").strip()
    if pedida:
        origen = Path(pedida).expanduser()
    else:
        origen = None
        try:
            lector = configparser.ConfigParser(interpolation=None)
            lector.read(paths.config_ini(), encoding="utf-8")
            cruda = lector.get("musica", "carpeta", fallback="").strip()
            if cruda:
                origen = Path(decodificar_texto_ini(cruda))
        except Exception:
            origen = None
        if origen is None:
            origen = Path.home() / "Music"
    if not origen.is_dir():
        res.no_probado(f"musica_real: no hay carpeta de música en «{origen}»")
        return
    candidatos = sorted(
        (p for p in origen.rglob("*")
         if p.is_file() and p.suffix.lower() in EXTENSIONES),
        key=lambda p: str(p).lower())
    if len(candidatos) < 5:
        res.no_probado(f"musica_real: la carpeta «{origen}» tiene "
                       f"{len(candidatos)} temas y hacen falta 5")
        return
    elegidos = random.Random(18102026).sample(candidatos, 5)
    nombres_archivo = ([f"{i + 1:02d} {f.name}" for i, f in enumerate(elegidos)]
                       + ["06 corto QA.wav"])
    if any(", " in Path(nombre).stem for nombre in nombres_archivo):
        res.no_probado(
            "musica_real: un tema elegido tiene una coma en el nombre y no "
            "se puede separar el título del artista y la duración")
        return

    # ── Rutas que se tocan (solo lectura acá, se escriben en el `try`) ──

    ruta_config = paths.config_ini()
    ruta_listas = paths.listas_musica()
    ruta_estado = paths.estado_musica()
    ruta_etiquetas = paths.cache_etiquetas_musica()

    tmp_musica = None
    tmp_respaldo = None
    respaldo_config = None
    respaldo_estado = None
    respaldo_etiquetas = None
    listas_habia = False
    propia = None

    def _agujas_unicas(indice, tope=6):
        return agujas_unicas(nombres_archivo, indice, tope)

    def _aguja_grupo(incluidos, excluidos):
        return aguja_grupo(nombres_archivo, incluidos, excluidos)

    try:
        # ── Carpeta temporal con los 6 temas ──

        tmp_musica = Path(tempfile.mkdtemp(prefix="qa-musica-"))
        tmp_respaldo = Path(tempfile.mkdtemp(prefix="qa-musica-respaldo-"))
        for i, fuente in enumerate(elegidos):
            shutil.copy2(fuente, tmp_musica / nombres_archivo[i])
        with wave.open(str(tmp_musica / "06 corto QA.wav"), "w") as oleada:
            oleada.setnchannels(1)
            oleada.setsampwidth(2)
            oleada.setframerate(44100)
            muestras = array.array(
                "h", (int(16383 * math.sin(2 * math.pi * 440 * i / 44100))
                      for i in range(44100 * 3)))
            oleada.writeframes(muestras.tobytes())

        # ── Respaldo en otra carpeta temporal ──

        if ruta_config.is_file():
            respaldo_config = ruta_config.read_bytes()
            (tmp_respaldo / "config.ini").write_bytes(respaldo_config)
        if ruta_listas.is_dir():
            listas_habia = True
            shutil.copytree(ruta_listas, tmp_respaldo / "listas")
        if ruta_estado.is_file():
            respaldo_estado = ruta_estado.read_bytes()
            (tmp_respaldo / "musica_estado.json").write_bytes(respaldo_estado)
        if ruta_etiquetas.is_file():
            respaldo_etiquetas = ruta_etiquetas.read_bytes()
            (tmp_respaldo / "etiquetas_musica.json").write_bytes(
                respaldo_etiquetas)

        # ── Solo las claves de música necesarias ──

        cambios = [
            ("musica", "carpeta", codificar_texto_ini(str(tmp_musica))),
            ("musica", "volumen", "40"),
            ("musica", "aleatorio", "false"),
            ("musica", "repetir", "false"),
            ("musica", "retomar", "false"),
            ("musica", "decir", "titulo"),
            ("musica", "decir_pausa", "true"),
            ("musica", "sonido_tema", "true"),
            ("musica", "preguntar_igualar", "false"),
            ("musica", "mostrar_cola", "false"),
            ("musica", "atajos_globales", "false"),
        ]
        if ruta_config.is_file():
            if not guardar_opciones(ruta_config, cambios):
                _corta("musica_real: no se pudo fijar la configuración "
                       "de música")
        else:
            nuevo = configparser.ConfigParser(interpolation=None)
            nuevo["musica"] = {clave: valor for _, clave, valor in cambios}
            with open(ruta_config, "w", encoding="utf-8") as f:
                nuevo.write(f)

        # ── Aplicación propia, con la sonda adentro ──

        propia = Aplicacion(app.anuncios_ruta.parent / "musica_real")
        propia.arrancar()
        if not propia.esperar_lista(segundos=60):
            _corta("musica_real: la aplicación no contestó al ping en 60 s")
        if not propia.dijo("grabador instalado"):
            _corta("musica_real: la sonda no dejó constancia; "
                   "podría estar hablando")
        try:
            pid_sonda = propia.pedir("pid").get("datos", {}).get("pid")
        except Exception as exc:
            _corta(f"musica_real: no se pudo leer el pid de la sonda: {exc}")
        if not isinstance(pid_sonda, int) or pid_sonda <= 0:
            _corta("musica_real: la sonda devolvió un pid inválido")
        pids = {propia.proceso.pid, pid_sonda}

        sin_salida = False

        # ── Atajos del recorrido ──

        def _arbol(ventana):
            return propia.arbol(ventana)

        def _filas(ventana, nombre):
            for control in _arbol(ventana):
                if (control.get("clase") == "ListBox"
                        and (control.get("nombre") or "") == nombre):
                    return list(control.get("items", []))
            return None

        def _filas_hasta(ventana, nombre, cantidad, segundos):
            limite = time.monotonic() + segundos
            while time.monotonic() < limite:
                filas = _filas(ventana, nombre)
                if filas is not None and len(filas) == cantidad:
                    return filas
                time.sleep(0.2)
            return _filas(ventana, nombre)

        def _filas_estables(ventana, nombre, segundos=8.0):
            # Las etiquetas se leen en un hilo y cambian los títulos: se
            # espera a que se asienten antes de tomarlos como esperados.
            anteriores = _filas(ventana, nombre) or []
            limite = time.monotonic() + segundos
            while time.monotonic() < limite:
                time.sleep(1.2)
                actuales = _filas(ventana, nombre) or []
                if actuales and actuales == anteriores:
                    return actuales
                anteriores = actuales
            return anteriores

        def _titulo_fila(fila):
            # Quita el prefijo que pone `bellbird.music.vista.filas_cola`:
            # el estado («Sonando: » o «En pausa: »), el número y el punto.
            # La fila sigue con el título, el artista y la duración separados
            # por «, », así que el título es lo que queda antes de la primera.
            texto = fila
            for prefijo in ("Sonando: ", "En pausa: "):
                if texto.startswith(prefijo):
                    texto = texto[len(prefijo):]
                    break
            punto = texto.find(". ")
            if punto > 0 and texto[:punto].isdigit():
                texto = texto[punto + 2:]
            return texto.split(", ", 1)[0]

        def _filtrar(ventana, texto):
            propia.pedir("foco", ventana=ventana,
                         nombre="Buscar en la música")
            propia.pedir("texto", valor=texto)

        def _pico():
            try:
                return medidor_sonido.pico(pids)
            except Exception:
                return None

        def _menu(etiqueta):
            try:
                propia.abrir_por_menu(etiqueta)
            except Exception as exc:
                _corta(f"musica_real: el menú no tiene «{etiqueta}»: {exc}")

        def _elegir(ventana, nombre, indice):
            propia.pedir("elegir", ventana=ventana, nombre=nombre,
                         indice=indice)

        def _menu_contextual(ventana, nombre, entrada, responder_ya=False):
            propia.pedir("menu_contextual", ventana=ventana, nombre=nombre,
                         entrada=entrada, responder_ya=responder_ya)

        def _aislar(indice, esperado):
            for aguja in _agujas_unicas(indice):
                _filtrar("Música", aguja)
                filas = _filas_hasta("Música", "Canciones", 1, 5.0)
                if filas is not None and len(filas) == 1:
                    titulo = _titulo_fila(filas[0])
                    if titulo != esperado:
                        _corta(f"musica_real: el buscador aisló "
                               f"«{filas[0]}» en vez de «{esperado}»")
                    return titulo
            _corta(f"musica_real: no se pudo aislar «{esperado}» "
                   "con el buscador")

        def _boton_aceptar(ventana):
            for control in _arbol(ventana):
                if control.get("clase") not in ("Button", "BitmapButton"):
                    continue
                texto = ((control.get("nombre") or "") + " "
                         + (control.get("etiqueta") or "")).lower()
                if ("aceptar" in texto or texto.strip() == "ok"
                        or " ok " in f" {texto} "):
                    return (control.get("nombre")
                            or control.get("etiqueta"))
            return None

        def _escribir_cuadro(ventana, valor):
            campo = next((c for c in _arbol(ventana)
                          if c.get("clase") == "TextCtrl"), None)
            if campo is None:
                _corta(f"musica_real: «{ventana}» no tiene cuadro de texto")
            nombre = campo.get("nombre") or campo.get("etiqueta")
            if nombre:
                try:
                    propia.pedir("foco", ventana=ventana, nombre=nombre)
                except Exception as exc:
                    _corta(f"musica_real: no se llega al cuadro de "
                           f"«{ventana}»: {exc}")
            propia.pedir("texto", valor=valor)
            for control in _arbol(ventana):
                if control.get("clase") == "TextCtrl":
                    if (control.get("valor") or "") == valor:
                        return
                    _corta(f"musica_real: el cuadro de «{ventana}» no tomó "
                           f"«{valor}»")

        def _pulsar_aceptar(ventana):
            nombre = _boton_aceptar(ventana)
            if nombre is None:
                _corta(f"musica_real: «{ventana}» no ofrece ningún botón "
                       "para aceptar")
            propia.pedir("pulsar", nombre=nombre, ventana=ventana)
            if propia.esperar_ventana(ventana, segundos=3) is not None:
                _corta(f"musica_real: «{ventana}» no cerró al aceptar")

        def _pulsar_y_cerrar(ventana, boton):
            propia.pedir("pulsar", nombre=boton, ventana=ventana)
            if propia.esperar_ventana(ventana, segundos=3) is not None:
                _corta(f"musica_real: «{ventana}» no cerró al pulsar "
                       f"«{boton}»")

        inicio = time.monotonic()
        tope = inicio + _TOPE_RECORRIDO

        def _aire():
            if time.monotonic() > tope:
                _corta("musica_real: se pasó de 6 minutos, "
                       "se corta el recorrido")
            return True

        # ── a. La ventana Música muestra los 6 temas ──

        _menu("elegir música")
        if propia.esperar_ventana("Música", segundos=15) is None:
            _corta("musica_real: «Elegir música» no abrió la ventana")
        res.nota("musica_real: abre «Música» desde el menú")
        filas = _filas_hasta("Música", "Canciones", 6, 30.0)
        if filas is None or len(filas) != 6:
            _corta(f"musica_real: la lista de temas tiene "
                   f"{len(filas) if filas is not None else 'nada'} "
                   "elementos en vez de 6")
        # La Cola arranca oculta de fábrica: se la muestra una sola vez con
        # su botón, que así también se prueba, antes de leerla o usarla.
        propia.pedir("pulsar", nombre="Mostrar cola", ventana="Música")
        if _filas_hasta("Música", "Cola de reproducción", 0, 1.0) is None:
            _corta("musica_real: la Cola no responde tras mostrarla")
        # Los filtros arrancan ocultos y no filtran. Se marca la casilla para
        # comprobar que los dos cuadros aparecen y que se anuncia, y se vuelve
        # a desmarcar para no cambiar lo que ve el resto del recorrido.
        n = len(propia.anuncios)
        propia.pedir("casilla", nombre="Mostrar filtros", ventana="Música",
                     valor=True)
        for nombre in ("Mostrar", "Ordenar por"):
            rama = subarbol(_arbol("Música"), nombre)
            if not rama or not rama[0].get("visible"):
                res.fallo("musica_real: al mostrar los filtros no aparece "
                          f"«{nombre}»")
        if not propia.esperar_dicho("Filtros visibles", segundos=5, desde=n):
            res.fallo("musica_real: al mostrar los filtros no se anunció")
        n = len(propia.anuncios)
        propia.pedir("casilla", nombre="Mostrar filtros", ventana="Música",
                     valor=False)
        if not propia.esperar_dicho("Filtros ocultos", segundos=5, desde=n):
            res.fallo("musica_real: al ocultar los filtros no se anunció")
        # Con `--capturas`: la misma ventana, ahora con la cola visible. La
        # apertura con la cola oculta ya la capturó `esperar_ventana`.
        captor_musica = getattr(args, "captor", None)
        if captor_musica is not None:
            captor_musica.capturar(propia, "musica_real", "Música",
                                   extra="cola visible")

        # ── b. Reproducir todo: anuncia el título y se oye ──

        _aire()
        filas = _filas_estables("Música", "Canciones")
        titulo_primero = _titulo_fila(filas[0]) if filas else ""
        n = len(propia.anuncios)
        _elegir("Música", "Canciones", 0)
        _menu_contextual("Música", "Canciones",
                         "Reproducir todo desde aquí")
        anunciado = (bool(titulo_primero)
                     and propia.esperar_dicho(titulo_primero, segundos=10,
                                              desde=n))
        suena = False
        todo_none = True
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            valor = _pico()
            if valor is not None:
                todo_none = False
                if valor > 0.005:
                    suena = True
                    break
            time.sleep(0.1)
        if todo_none:
            sin_salida = True
            res.no_probado("musica_real: sin salida de audio en esta PC; "
                           "se siguen comprobando solo los anuncios y la cola")
        if not anunciado:
            res.fallo("musica_real: no se anunció el título del primer "
                      f"tema («{titulo_primero}»)")
        elif not sin_salida and not suena:
            res.fallo("musica_real: el primer tema no se oye "
                      "(pico bajo 10 s)")
        else:
            res.nota(f"musica_real: suena el primer tema "
                     f"(«{titulo_primero}»)")

        # ── c. Pausa y reanudación ──

        _aire()
        n = len(propia.anuncios)
        _menu("Música > Reproducir o pausar")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_PAUSA, segundos=8,
                                      desde=n):
            res.fallo("musica_real: pausar no anunció "
                      f"«{anuncios_musica.TEXTO_PAUSA}»")
        else:
            res.nota("musica_real: la pausa se anuncia")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: pausada y el pico no cayó "
                          "bajo 0,001 en 3 s")
        n = len(propia.anuncios)
        _menu("Música > Reproducir o pausar")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_REANUDADA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: reanudar no anunció "
                      f"«{anuncios_musica.TEXTO_REANUDADA}»")
        if not sin_salida:
            limite = time.monotonic() + 5
            suena = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor > 0.005:
                    suena = True
                    break
                time.sleep(0.1)
            if not suena:
                res.fallo("musica_real: reanudada y no volvió el sonido")

        # ── d. Siguiente y anterior, según la cola ──

        _aire()
        cola = _filas("Música", "Cola de reproducción") or []
        if len(cola) < 2:
            res.fallo("musica_real: la cola no trae dos temas y no se puede "
                      "probar siguiente ni anterior")
        else:
            primero = _titulo_fila(cola[0])
            segundo = _titulo_fila(cola[1])
            if not primero or not segundo:
                res.fallo("musica_real: la cola trae filas sin título y no "
                          "se puede probar siguiente ni anterior")
            else:
                n = len(propia.anuncios)
                _menu("siguiente canción")
                if propia.esperar_dicho(segundo, segundos=8, desde=n):
                    res.nota(f"musica_real: siguiente anuncia «{segundo}»")
                else:
                    res.fallo("musica_real: «Siguiente canción» no anunció "
                              f"«{segundo}»")
                n = len(propia.anuncios)
                _menu("canción anterior")
                reiniciado = False
                limite = time.time() + 8
                while time.time() < limite:
                    if propia.dijo(anuncios_musica.TEXTO_REINICIADO,
                                   desde=n):
                        reiniciado = True
                        break
                    if propia.dijo(primero, desde=n):
                        break
                    time.sleep(0.1)
                if reiniciado:
                    res.nota("musica_real: anterior reinició el tema")
                    n = len(propia.anuncios)
                    _menu("canción anterior")
                    if propia.esperar_dicho(primero, segundos=8, desde=n):
                        res.nota(f"musica_real: anterior anuncia «{primero}»")
                    else:
                        res.fallo("musica_real: «Canción anterior» no anunció "
                                  f"«{primero}»")
                elif propia.dijo(primero, desde=n):
                    res.nota(f"musica_real: anterior anuncia «{primero}»")
                else:
                    res.fallo("musica_real: «Canción anterior» no anunció "
                              f"«{primero}»")

        # ── e. Volumen: sube a 50 y vuelve a 40 ──

        _aire()
        n = len(propia.anuncios)
        _menu("Música > Subir volumen")
        esperado = anuncios_musica.TEXTO_VOLUMEN.format(valor=50)
        if not propia.esperar_dicho(esperado, segundos=8, desde=n):
            res.fallo(f"musica_real: subir no anunció «{esperado}»")
        n = len(propia.anuncios)
        _menu("Música > Bajar volumen")
        esperado = str(40)
        if not propia.esperar_dicho(esperado, segundos=8, desde=n):
            res.fallo(f"musica_real: bajar no anunció «{esperado}»")
        else:
            res.nota("musica_real: el volumen sube a 50 y vuelve a 40")

        # ── f. Anunciar canción actual contiene el título actual ──

        _aire()
        cola = _filas("Música", "Cola de reproducción") or []
        actual = next((f for f in cola if f.startswith("Sonando: ")), "")
        titulo_actual = _titulo_fila(actual) if actual else ""
        if not actual or not titulo_actual:
            res.fallo("musica_real: la cola no marca ningún tema actual y "
                      "no se puede probar la canción actual")
        else:
            antes, despues = anuncios_musica.TEXTO_QUE_SUENA.split("{nombre}")
            posicion = cola.index(actual) + 1
            fragmento_titulo = antes + titulo_actual
            fragmento_tema = despues.format(posicion=posicion,
                                            total=len(cola))
            n = len(propia.anuncios)
            _menu("anunciar canción actual")
            if not propia.esperar_dicho(fragmento_titulo, segundos=8,
                                        desde=n):
                res.fallo("musica_real: «Anunciar canción actual» no dijo "
                          f"«{fragmento_titulo}»")
            else:
                limite = time.monotonic() + 8
                oido = ""
                while time.monotonic() < limite:
                    for dicho in propia.anuncios[n:]:
                        texto = dicho.get("texto", "")
                        if (fragmento_titulo.lower() in texto.lower()
                                and fragmento_tema.lower() in texto.lower()):
                            oido = texto
                            break
                    if oido:
                        break
                    time.sleep(0.1)
                if oido:
                    res.nota(f"musica_real: anunciar canción actual dice «{oido}»")
                elif not any(fragmento_tema.lower()
                             in d.get("texto", "").lower()
                             for d in propia.anuncios[n:]):
                    res.fallo("musica_real: «Anunciar canción actual» no dijo "
                              f"«{fragmento_tema}»")
                else:
                    res.fallo("musica_real: «Anunciar canción actual» dijo "
                              f"«{fragmento_titulo}» y «{fragmento_tema}» "
                              "pero nunca en el mismo anuncio")

        # ── f2. Atajos globales con otra ventana al frente ──

        import musica_globales
        musica_globales.probar_atajos_globales(propia, res, tmp_respaldo)

        # ── g. Orden aleatorio dos veces ──

        _aire()
        n = len(propia.anuncios)
        _menu("orden aleatorio")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_ALEATORIO_ON,
                                     segundos=8, desde=n):
            res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_ALEATORIO_ON}»")
        n = len(propia.anuncios)
        _menu("orden aleatorio")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_ALEATORIO_OFF,
                                     segundos=8, desde=n):
            res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_ALEATORIO_OFF}»")
        else:
            res.nota("musica_real: el orden aleatorio se anuncia "
                     "activado y desactivado")

        # ── h. El corto a continuación, suena y avanza solo ──

        _aire()
        _aislar(5, "06 corto QA")
        cola_antes = _filas("Música", "Cola de reproducción") or []
        n = len(propia.anuncios)
        propia.pedir("tecla_en", ventana="Música", nombre="Canciones",
                     tecla="enter", modificadores=["shift"])
        esperado = anuncios_musica.TEXTO_A_CONTINUACION.format(
            nombre="06 corto QA")
        if not propia.esperar_dicho(esperado, segundos=8, desde=n):
            res.fallo(f"musica_real: no se anunció «{esperado}»")
        cola = _filas("Música", "Cola de reproducción") or []
        if (len(cola) != len(cola_antes) + 1
                or _titulo_fila(cola[1]) != "06 corto QA"):
            res.fallo("musica_real: «06 corto QA» no quedó justo detrás "
                      "del actual en la cola")
        else:
            res.nota("musica_real: el corto queda justo detrás del actual")
        que_seguia = _titulo_fila(cola[2]) if len(cola) > 2 else ""
        n = len(propia.anuncios)
        _menu("siguiente canción")
        if not propia.esperar_dicho("06 corto QA", segundos=10, desde=n):
            res.fallo("musica_real: «Siguiente canción» no anunció el corto")
        elif que_seguia and propia.esperar_dicho(que_seguia, segundos=15,
                                                    desde=n):
            res.nota(f"musica_real: el corto sonó y avanzó solo "
                     f"a «{que_seguia}»")
        else:
            res.fallo("musica_real: el corto no avanzó solo al tema que "
                      f"seguía («{que_seguia}»)")
        _filtrar("Música", "")
        if _filas_hasta("Música", "Canciones", 6, 10.0) is None:
            _corta("musica_real: al limpiar el buscador no vuelven los 6")

        # ── i. El quinto a la cola ──

        _aire()
        filas = _filas_estables("Música", "Canciones") or []
        if len(filas) != 6:
            _corta("musica_real: la lista de temas no tiene 6 elementos")
        quinto = _titulo_fila(filas[4])
        _aislar(4, quinto)
        cola_antes = _filas("Música", "Cola de reproducción") or []
        propia.pedir("tecla_en", ventana="Música", nombre="Canciones",
                     tecla="enter", modificadores=["ctrl"])
        cola = _filas("Música", "Cola de reproducción") or []
        if (len(cola) != len(cola_antes) + 1
                or (quinto and _titulo_fila(cola[-1]) != quinto)):
            res.fallo("musica_real: la cola no creció en uno con el "
                      f"quinto («{quinto}»)")
        else:
            res.nota("musica_real: el quinto se agrega al final de la cola")
        _filtrar("Música", "")
        _filas_hasta("Música", "Canciones", 6, 10.0)

        # ── j. Reproducir ahora el tercero ──

        _aire()
        filas = _filas_estables("Música", "Canciones") or []
        if len(filas) != 6:
            _corta("musica_real: la lista de temas no tiene 6 elementos")
        tercero = _titulo_fila(filas[2])
        cola_antes = _filas("Música", "Cola de reproducción") or []
        # `reproducir_ahora` inserta el tema detrás del que suena, así que el
        # contrato está en esa fila y no en que la cola copie la carpeta:
        # comparar contra la carpeta medía el botón viejo «Reproducir este».
        indice_sonando = next((i for i, f in enumerate(cola_antes)
                               if f.startswith("Sonando: ")), None)
        n = len(propia.anuncios)
        # El Intro de verdad, no un EVT_KEY_DOWN armado a mano: el 19/10/2026
        # la lista de temas y la Cola quedaban mudas con el teclado de
        # Windows porque el diálogo se comía la tecla antes del control.
        try:
            propia.pedir("foco", ventana="Música", nombre="Canciones")
            _elegir("Música", "Canciones", 2)
            propia.teclas("enter")
        except VentanaNoActiva as exc:
            res.no_probado("musica_real: «Reproducir ahora» no se pudo probar "
                           f"con el teclado real: {exc}")
        else:
            if not tercero:
                res.fallo("musica_real: la tercera fila no tiene título y no "
                          "se puede probar «Reproducir ahora»")
            elif not propia.esperar_dicho(tercero, segundos=10, desde=n):
                res.fallo("musica_real: «Reproducir ahora» no anunció "
                          f"«{tercero}»")
            cola = _filas("Música", "Cola de reproducción") or []
            if not cola:
                res.fallo("musica_real: la cola está vacía tras "
                          "«Reproducir ahora»")
            elif len(cola) != len(cola_antes) + 1:
                res.fallo("musica_real: «Reproducir ahora» no agregó un tema "
                          "a la cola")
            elif indice_sonando is None:
                res.fallo("musica_real: antes de «Reproducir ahora» la cola "
                          "no marcaba ningún tema sonando")
            else:
                siguiente = cola[indice_sonando + 1: indice_sonando + 2]
                if (not siguiente or not siguiente[0].startswith("Sonando: ")
                        or _titulo_fila(siguiente[0]) != tercero):
                    res.fallo("musica_real: «Reproducir ahora» no dejó el "
                              "tercero sonando justo detrás del que sonaba")
                elif not sin_salida:
                    limite = time.monotonic() + 10
                    suena = False
                    while time.monotonic() < limite:
                        valor = _pico()
                        if valor is not None and valor > 0.005:
                            suena = True
                            break
                        time.sleep(0.1)
                    if not suena:
                        res.fallo("musica_real: el tercero no se oye")

        # ── k. Guardar la cola como lista y reproducirla ──

        _aire()
        cola = _filas("Música", "Cola de reproducción") or []
        cantidad_cola = len(cola)
        _elegir("Música", "Cola de reproducción", 0)
        try:
            _menu_contextual("Música", "Cola de reproducción",
                             "Guardar la cola como lista", responder_ya=True)
        except Exception:
            pass  # el cuadro es modal y se come la respuesta
        if propia.esperar_ventana("Nueva lista", segundos=10) is None:
            _corta("musica_real: no abrió «Nueva lista»")
        _escribir_cuadro("Nueva lista", _NOMBRE_LISTA)
        n = len(propia.anuncios)
        _pulsar_aceptar("Nueva lista")
        esperado = anuncios_musica.TEXTO_LISTA_GUARDADA.format(
            nombre=_NOMBRE_LISTA)
        if not propia.esperar_dicho(esperado, segundos=10, desde=n):
            res.fallo(f"musica_real: no se anunció «{esperado}»")
        ruta_lista = ruta_listas / (_NOMBRE_LISTA + ".m3u8")
        if not ruta_lista.is_file():
            res.fallo("musica_real: no existe el .m3u8 en la carpeta "
                      "de listas")
        else:
            try:
                guardados, _saltadas = listas_musica.cargar(
                    ruta_listas, _NOMBRE_LISTA)
            except Exception as exc:
                res.fallo(f"musica_real: no se pudo leer la lista "
                          f"guardada: {exc}")
            else:
                if len(guardados) != cantidad_cola:
                    res.fallo("musica_real: la lista guardada tiene "
                              f"{len(guardados)} entradas y la cola "
                              f"{cantidad_cola}")
                else:
                    res.nota("musica_real: la cola se guarda como lista "
                             f"con {cantidad_cola} entradas")
        # Agregar un tema de la biblioteca a la lista recién guardada, con
        # el submenú del menú de «Canciones».
        _elegir("Música", "Colecciones", 0)
        if _filas_hasta("Música", "Canciones", 6, 10.0) is None:
            _corta("musica_real: la biblioteca no mostró 6 temas para "
                   "agregar a la lista")
        _elegir("Música", "Canciones", 0)
        n = len(propia.anuncios)
        _menu_contextual("Música", "Canciones",
                         f"Agregar a una lista > {_NOMBRE_LISTA}")
        esperado = anuncios_musica.TEXTO_AGREGADO_A_LISTA.format(
            nombre=_NOMBRE_LISTA)
        if not propia.esperar_dicho(esperado, segundos=10, desde=n):
            res.fallo(f"musica_real: no se anunció «{esperado}»")
        cantidad_lista = cantidad_cola + 1
        try:
            agregados, _saltadas = listas_musica.cargar(
                ruta_listas, _NOMBRE_LISTA)
        except Exception as exc:
            res.fallo(f"musica_real: no se pudo leer la lista tras "
                      f"agregar: {exc}")
        else:
            if len(agregados) != cantidad_lista:
                res.fallo("musica_real: la lista quedó con "
                          f"{len(agregados)} entradas tras agregar y se "
                          f"esperaban {cantidad_lista}")
            else:
                res.nota("musica_real: se agregó un tema de la carpeta a "
                         "la lista")
        n = len(propia.anuncios)
        _menu("detener música")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: detenida y el pico no cayó "
                          "bajo 0,001 en 3 s")
        esperadas = vista_musica.filas_colecciones(
            [_NOMBRE_LISTA], cantidad_biblioteca=len(nombres_archivo),
            cantidades={_NOMBRE_LISTA: cantidad_lista})
        import musica_colecciones
        fila_biblioteca = esperadas[0]
        fila_qa = esperadas[1]
        # `_filas_hasta` solo espera la cantidad (2) y vuelve enseguida con
        # «Biblioteca» sin contar: se espera la posición real de la lista
        # de QA, con el mismo plazo.
        limite_colecciones = time.monotonic() + 10.0
        elegidas = None
        indice_qa = None
        while time.monotonic() < limite_colecciones:
            elegidas = _filas("Música", "Colecciones")
            indice_qa = musica_colecciones.indice_coleccion_qa(
                elegidas, fila_biblioteca, fila_qa)
            if indice_qa is not None:
                break
            time.sleep(0.2)
        if indice_qa is None:
            _corta(f"musica_real: «Colecciones» ofrece {elegidas} en vez "
                   f"de {esperadas}")
        _elegir("Música", "Colecciones", indice_qa)
        filas = _filas_hasta("Música", "Canciones", cantidad_lista, 10.0)
        if filas is None or len(filas) != cantidad_lista:
            _corta("musica_real: la lista no trajo "
                   f"{cantidad_lista} temas a «Canciones»")
        # El Intro de verdad, como en el paso j, en lugar del menú
        # contextual: reproduce la lista elegida en «Colecciones».
        try:
            propia.pedir("foco", ventana="Música", nombre="Colecciones")
            _elegir("Música", "Colecciones", indice_qa)
            propia.teclas("enter")
        except VentanaNoActiva as exc:
            res.no_probado("musica_real: la lista no se pudo reproducir "
                           f"con el teclado real: {exc}")
        else:
            if not sin_salida:
                limite = time.monotonic() + 10
                suena = False
                while time.monotonic() < limite:
                    valor = _pico()
                    if valor is not None and valor > 0.005:
                        suena = True
                        break
                    time.sleep(0.1)
                if not suena:
                    res.fallo("musica_real: la lista no se oye")
            cola = _filas_hasta("Música", "Cola de reproducción",
                                cantidad_lista, 10.0) or []
            if len(cola) != cantidad_lista:
                res.fallo("musica_real: la cola tiene "
                          f"{len(cola)} entradas en vez de {cantidad_lista}")
            else:
                res.nota("musica_real: la lista suena con sus "
                         f"{cantidad_lista} entradas")
        _elegir("Música", "Colecciones", 0)
        if _filas_hasta("Música", "Canciones", 6, 10.0) is None:
            _corta("musica_real: al volver a la carpeta no aparecen 6 temas")

        # ── l. Agregar el enlace del vídeo: se oye ──

        _aire()
        n = len(propia.anuncios)
        _menu("detener música")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: detenida y el pico no cayó "
                          "bajo 0,001 en 3 s")
        cola_antes = _filas("Música", "Cola de reproducción") or []
        try:
            propia.pedir("pulsar", nombre="Abrir enlace", responder_ya=True)
        except Exception:
            pass  # el cuadro es modal y se come la respuesta
        if propia.esperar_ventana("Abrir enlace", segundos=10) is None:
            _corta("musica_real: no abrió «Abrir enlace»")
        _escribir_cuadro("Abrir enlace", _URL_VIDEO)
        n = len(propia.anuncios)
        _pulsar_y_cerrar("Abrir enlace", "Agregar a la cola")
        if not propia.esperar_dicho(
                anuncios_musica.TEXTO_LEYENDO_ENLACE, segundos=10, desde=n):
            res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_LEYENDO_ENLACE}»")
        prefijo_agregado = anuncios_musica.TEXTO_AGREGADO_POSICION.split(",")[0]
        if not propia.esperar_dicho(prefijo_agregado, segundos=60, desde=n):
            dichos = " ".join(a.get("texto", "")
                              for a in propia.anuncios[n:])[-200:]
            res.fallo("musica_real: el vídeo no se agregó a la cola en "
                      f"60 s; dijo «{dichos}»")
        else:
            cola = _filas("Música", "Cola de reproducción") or []
            if len(cola) != len(cola_antes) + 1:
                res.fallo("musica_real: la cola no creció con el enlace")
            else:
                ultimo = _titulo_fila(cola[-1])
                if not ultimo:
                    res.fallo("musica_real: la última fila de la cola está "
                              "vacía y no se puede comprobar el vídeo")
                else:
                    visto = False
                    suena = False
                    limite = time.monotonic() + 10
                    while time.monotonic() < limite:
                        actual = (_filas("Música",
                                        "Cola de reproducción") or [])
                        if (len(actual) == len(cola_antes) + 1 and actual
                                and actual[-1].startswith("Sonando: ")
                                and _titulo_fila(actual[-1]) == ultimo):
                            visto = True
                        if not sin_salida:
                            valor = _pico()
                            if valor is not None and valor > 0.005:
                                suena = True
                        if visto and (sin_salida or suena):
                            break
                        time.sleep(0.2)
                    if not visto:
                        res.fallo("musica_real: la última fila de la cola "
                                  f"(«{ultimo}») no es lo que suena en 10 s")
                    elif sin_salida:
                        res.nota("musica_real: el vídeo se agrega a la cola")
                    elif not suena:
                        res.fallo("musica_real: el vídeo de YouTube no se oye")
                    else:
                        res.nota("musica_real: el vídeo de YouTube se oye")

        # ── m. Agregar el enlace de la lista ──

        _aire()
        try:
            propia.pedir("pulsar", nombre="Abrir enlace", responder_ya=True)
        except Exception:
            pass  # el cuadro es modal y se come la respuesta
        if propia.esperar_ventana("Abrir enlace", segundos=10) is None:
            _corta("musica_real: no abrió «Abrir enlace» por segunda vez")
        _escribir_cuadro("Abrir enlace", _URL_LISTA)
        n = len(propia.anuncios)
        _pulsar_y_cerrar("Abrir enlace", "Agregar a la cola")
        limite = time.monotonic() + 90
        agregados = 0
        lista_muerta = False
        patron_agregados = re.compile(
            re.escape(anuncios_musica.TEXTO_AGREGADOS).replace(
                re.escape("{cantidad}"), r"(\d+)"))
        while time.monotonic() < limite:
            for dicho in propia.anuncios[n:]:
                texto = dicho.get("texto", "")
                coincidencia = patron_agregados.search(texto)
                if coincidencia:
                    agregados = max(agregados, int(coincidencia.group(1)))
                if (enlaces_musica.TEXTO_NO_SE_PUDO_LEER.lower() in texto.lower()
                        or enlaces_musica.TEXTO_SIN_VIDEOS.lower() in texto.lower()):
                    lista_muerta = True
            if agregados >= 2 or lista_muerta:
                break
            time.sleep(0.5)
        if lista_muerta:
            res.no_probado("musica_real: la lista de prueba ya no existe "
                           "en YouTube: cambiarla")
        elif agregados < 2:
            res.fallo("musica_real: la lista no sumó 2 o más temas en 90 s")
        else:
            res.nota(f"musica_real: la lista sumó {agregados} temas")

        # ── n. Detener música ──

        _aire()
        try:
            propia.pedir("cerrar_ventana", ventana="Música")
        except Exception:
            pass
        n = len(propia.anuncios)
        _menu("detener música")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: al final detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: al final el pico no cayó "
                          "bajo 0,001 en 3 s")
        else:
            res.nota("musica_real: recorrido completo sin salida de audio")
    except _Corte:
        pass
    except Exception as exc:
        res.fallo(f"musica_real: el recorrido reventó: {exc!r}")
    finally:
        if propia is not None:
            try:
                try:
                    propia.pedir("salir", tiempo=5.0, tolerar=True)
                except Exception:
                    pass
                try:
                    contestar_salir_si_aparece(segundos=2.0)
                except Exception:
                    pass
                limite = time.monotonic() + 15.0
                while (propia.proceso is not None
                       and propia.proceso.poll() is None
                       and time.monotonic() < limite):
                    time.sleep(0.5)
                if (propia.proceso is not None
                        and propia.proceso.poll() is None):
                    try:
                        propia.proceso.kill()
                    except Exception:
                        pass
                    res.nota("musica_real: la aplicación no cerró en 15 s "
                             "y se la mató")
            finally:
                try:
                    propia._salida.close()
                except Exception:
                    pass
        # La aplicación guarda al salir: se restaura DESPUÉS de cerrarla.
        try:
            if respaldo_config is None:
                try:
                    ruta_config.unlink()
                except FileNotFoundError:
                    pass
                if ruta_config.exists():
                    res.fallo("musica_real: config.ini no existía y no se "
                              "pudo borrar el creado")
            else:
                ruta_config.write_bytes(respaldo_config)
                if ruta_config.read_bytes() != respaldo_config:
                    res.fallo("musica_real: config.ini no quedó idéntico "
                              "al respaldo")
        except Exception as exc:
            res.fallo(f"musica_real: no se pudo restaurar config.ini: {exc}")
        try:
            shutil.rmtree(ruta_listas, ignore_errors=True)
            if listas_habia:
                shutil.copytree(tmp_respaldo / "listas", ruta_listas)
        except Exception as exc:
            res.fallo("musica_real: no se pudo restaurar la carpeta "
                      f"de listas: {exc}")
        for nombre, ruta, respaldo in (
                ("musica_estado.json", ruta_estado, respaldo_estado),
                ("etiquetas_musica.json", ruta_etiquetas,
                 respaldo_etiquetas)):
            try:
                if respaldo is None:
                    try:
                        ruta.unlink()
                    except FileNotFoundError:
                        pass
                    if ruta.exists():
                        res.fallo(f"musica_real: {nombre} no existía y no "
                                  "se pudo borrar el creado")
                else:
                    ruta.write_bytes(respaldo)
            except Exception as exc:
                res.fallo(f"musica_real: no se pudo restaurar {nombre}: "
                          f"{exc}")
        if tmp_musica is not None:
            shutil.rmtree(tmp_musica, ignore_errors=True)
        if tmp_respaldo is not None:
            shutil.rmtree(tmp_respaldo, ignore_errors=True)
# Vídeo grabado para `reproductor_en_marcha`, que se pasa con `--url-vod`.
VOD_YOUTUBE = "https://www.youtube.com/watch?v=j906Pf7n7Sg"


def esperar_reproductor(app: Aplicacion, condicion, segundos: float):
    """Sondea el estado del reproductor hasta que `condicion` se cumpla.

    Devuelve el último estado y si se cumplió. Espera hechos, no relojes.
    """
    ultimo: dict = {}
    limite = time.time() + segundos
    while True:
        try:
            ultimo = app.reproductor() or {}
        except Exception:
            ultimo = {}
        if ultimo and condicion(ultimo):
            return ultimo, True
        if time.time() >= limite:
            return ultimo, False
        time.sleep(0.25)


def _en_marcha_teclas(app: Aplicacion, res: Resultado, donde: str,
                      *pasos) -> bool:
    """Pasa las teclas, y si la ventana no está al frente no juzga nada."""
    try:
        app.teclas(*pasos)
    except VentanaNoActiva as exc:
        res.no_probado(f"{donde}: no se pudo probar, {exc}")
        return False
    return True


def _en_marcha_salto(app: Aplicacion, res: Resultado, donde: str, p0: int,
                     delta_ms: int, dur_ms: int, espera: float = 30.0):
    """Juzga un salto ya pulsado: destino, tolerancia y que siga avanzando.

    Devuelve la posición final, o None si no pasó.
    """
    destino = p0 + delta_ms
    if dur_ms > 0:
        destino = min(max(destino, 0), dur_ms)
    else:
        destino = max(destino, 0)
    t0 = time.time()

    def _cerca(e):
        pos = e.get("pos_ms") or 0
        return (e.get("estado") == "playing"
                and destino - 5000 <= pos <= destino + 20000)

    estado, ok = esperar_reproductor(app, _cerca, espera)
    pos = (estado.get("pos_ms") or 0) if estado else 0
    if not ok:
        res.fallo(f"{donde}: desde {p0 / 1000:.1f} s no quedó cerca de "
                  f"{destino / 1000:.1f} s en {espera:.0f} s; está en "
                  f"{pos / 1000:.1f} s con estado {estado.get('estado')!r}")
        return None
    time.sleep(3.0)
    pos2 = app.reproductor().get("pos_ms") or 0
    if pos2 <= pos:
        res.fallo(f"{donde}: quedó en {pos / 1000:.1f} s pero no avanza desde "
                  f"ahí ({pos2 / 1000:.1f} s 3 s después)")
        return None
    res.nota(f"{donde}: de {p0 / 1000:.1f} s a {pos / 1000:.1f} s "
             f"(destino {destino / 1000:.1f} s) en {time.time() - t0:.1f} s, "
             f"y sigue a {pos2 / 1000:.1f} s")
    return pos2


def _en_marcha_grabado(app: Aplicacion, args, res: Resultado) -> None:
    """Saltos y pausa en un vídeo grabado, con los atajos de verdad."""
    url = getattr(args, "url_vod", None) or VOD_YOUTUBE
    res.nota(f"reproductor en marcha (grabado): {url}")
    n = len(app.anuncios)
    if not conectar_de_verdad(app, res, url, "reproductor en marcha"):
        return
    if not app.esperar_dicho("reproduciendo", segundos=60, desde=n):
        res.fallo("reproductor en marcha: no se oyó «Reproduciendo» en 60 s")
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "playing", 60.0)
    if not ok:
        res.fallo("reproductor en marcha: no llegó a «playing» en 60 s; "
                  f"estado {estado.get('estado')!r}")
        return
    pa = estado.get("pos_ms") or 0
    time.sleep(2.0)
    pb = app.reproductor().get("pos_ms") or 0
    if pb <= pa:
        res.fallo("reproductor en marcha: en «playing» la posición no avanza "
                  f"({pa / 1000:.1f} s y {pb / 1000:.1f} s)")
        return
    res.nota(f"reproductor en marcha: reproduce desde {pa / 1000:.1f} s "
             f"y avanza a {pb / 1000:.1f} s en 2 s")

    # Dos avances seguidos, sin espera entre ellos, como hace cualquiera
    # cuando el primero no contestó.
    p0 = app.reproductor().get("pos_ms") or 0
    dur = app.reproductor().get("dur_ms") or 0
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    _en_marcha_salto(app, res, "reproductor en marcha, salto +2 min",
                     p0, 120000, dur)

    p1 = app.reproductor().get("pos_ms") or 0
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("left", ["ctrl"])):
        return
    _en_marcha_salto(app, res, "reproductor en marcha, salto -1 min",
                     p1, -60000, dur)

    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("p", ["ctrl"])):
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "paused", 5.0)
    if not ok:
        res.fallo("reproductor en marcha: no entró en pausa en 5 s; "
                  f"estado {estado.get('estado')!r}")
        return
    pa = estado.get("pos_ms") or 0
    time.sleep(2.0)
    pb = app.reproductor().get("pos_ms") or 0
    if abs(pb - pa) > 1000:
        res.fallo(f"reproductor en marcha: en pausa se movió de "
                  f"{pa / 1000:.1f} s a {pb / 1000:.1f} s en 2 s")
        return
    res.nota(f"reproductor en marcha: en pausa queda en {pa / 1000:.1f} s "
             f"y no se mueve")

    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("p", ["ctrl"])):
        return
    destino = pa + 60000

    def _reanudado(e):
        pos = e.get("pos_ms") or 0
        return (e.get("estado") == "playing"
                and destino - 5000 <= pos <= destino + 20000)

    estado, ok = esperar_reproductor(app, _reanudado, 30.0)
    pos = (estado.get("pos_ms") or 0) if estado else 0
    if not ok:
        res.fallo(f"reproductor en marcha: tras saltar en pausa desde "
                  f"{pa / 1000:.1f} s no reanudó cerca de "
                  f"{destino / 1000:.1f} s en 30 s; está en "
                  f"{pos / 1000:.1f} s con estado {estado.get('estado')!r}")
    else:
        res.nota(f"reproductor en marcha: salto en pausa y reanudado en "
                 f"{pos / 1000:.1f} s (destino {destino / 1000:.1f} s)")


def _en_marcha_directo(app: Aplicacion, args, res: Resultado) -> None:
    """Retroceso por relevo y vuelta al borde en un directo real."""
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"reproductor en marcha (directo): {url}")
    n = len(app.anuncios)
    if not conectar_de_verdad(app, res, url, "reproductor en marcha "
                                             "(directo)"):
        return
    if not app.esperar_dicho("reproduciendo", segundos=60, desde=n):
        res.fallo("reproductor en marcha (directo): no se oyó "
                  "«Reproduciendo» en 60 s")
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "playing", 60.0)
    if not ok:
        res.fallo("reproductor en marcha (directo): no llegó a «playing» "
                  f"en 60 s; estado {estado.get('estado')!r}")
        return
    res.nota("reproductor en marcha (directo): reproduce el directo")

    # Tres flechas seguidas en el deslizador: cada una son 10 s, o sea dos
    # segmentos de 5 s, así que el desfase esperado es 6.
    ventana_corta = False
    try:
        app.pedir("foco", nombre="Posición de reproducción")
    except OrdenRechazada as exc:
        res.fallo("reproductor en marcha (directo): no se llega a la "
                  f"posición, {exc}")
    else:
        n = len(app.anuncios)
        for _ in range(3):
            if not _en_marcha_teclas(app, res,
                                     "reproductor en marcha (directo)",
                                     "left"):
                return
        if app.esperar_dicho("no se puede retroceder más", segundos=5,
                             desde=n):
            res.nota("reproductor en marcha (directo): YouTube da una "
                     "ventana corta de 30 s y no deja retroceder; se sigue "
                     "con la vuelta al directo")
            ventana_corta = True
        else:
            t0 = time.time()

            def _atras(e):
                return (e.get("desfase") == 6
                        and e.get("estado") == "playing")

            estado, ok = esperar_reproductor(app, _atras, 20.0)
            if not ok:
                res.fallo("reproductor en marcha (directo): tras tres "
                          "flechas el desfase no llegó a 6 en 20 s; "
                          f"desfase {(estado.get('desfase') if estado else '?')}, "
                          f"estado {(estado.get('estado') if estado else '?')!r}")
            else:
                res.nota("reproductor en marcha (directo): tres flechas "
                         f"dejan el desfase en 6 en {time.time() - t0:.1f} s")

    if not ventana_corta:
        n = len(app.anuncios)
        if not _en_marcha_teclas(app, res, "reproductor en marcha (directo)",
                                 ("end", ["ctrl"])):
            return
        app.esperar_dicho("en el directo", segundos=8, desde=n)
        t0 = time.time()

        def _al_borde(e):
            return e.get("desfase") == 0 and e.get("estado") == "playing"

        estado, ok = esperar_reproductor(app, _al_borde, 20.0)
        junto = " ".join(a.get("texto", "") for a in app.anuncios[n:]).lower()
        dijo_borde = ("en el directo" in junto
                      and "ya estás en el directo" not in junto)
        if not dijo_borde or not ok:
            res.fallo("reproductor en marcha (directo): Ctrl+Fin no volvió "
                      f"al borde en 20 s; dijo «{junto[:80]}», desfase "
                      f"{(estado.get('desfase') if estado else '?')}, estado "
                      f"{(estado.get('estado') if estado else '?')!r}")
        else:
            res.nota("reproductor en marcha (directo): Ctrl+Fin dice «En el "
                     f"directo» y el desfase vuelve a 0 en "
                     f"{time.time() - t0:.1f} s")

    n = len(app.anuncios)
    if not _en_marcha_teclas(app, res, "reproductor en marcha (directo)",
                             ("end", ["ctrl"])):
        return
    if app.esperar_dicho("ya estás en el directo", segundos=8, desde=n):
        res.nota("reproductor en marcha (directo): Ctrl+Fin en el borde "
                 "dice «Ya estás en el directo»")
    else:
        junto = " ".join(a.get("texto", "") for a in app.anuncios[n:])
        res.fallo("reproductor en marcha (directo): Ctrl+Fin en el borde no "
                  f"avisó; dijo «{junto[:80]}»")


def escenario_reproductor_en_marcha(app: Aplicacion, args, res: Resultado):
    """El reproductor en marcha: saltos, pausa y vuelta al directo, de verdad.

    El banco nunca lo probaba: ningún escenario comprobaba que después de un
    salto el vídeo siga desde el destino, ni la pausa, ni volver al directo.
    Acá se pulsan los atajos de verdad contra un vídeo grabado y un directo
    reales, y se juzga la posición que la aplicación le da al usuario, no
    solo lo que anuncia. La segunda parte corre aunque la primera falle.
    """
    _en_marcha_grabado(app, args, res)
    app.llamar("set_conectado", False)
    _en_marcha_directo(app, args, res)
    app.llamar("set_conectado", False)

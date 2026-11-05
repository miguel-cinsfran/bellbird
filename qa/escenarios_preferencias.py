"""Escenarios de la ventana de Preferencias."""

from __future__ import annotations

import time

from banco_app import Aplicacion, Resultado
from banco_auditoria import (
    _ULTIMOS_NOMBRES, nombres_segun_windows, recorrer_tab, revisar_nombres,
    roles_segun_windows,
)

def escenario_preferencias(app: Aplicacion, args, res: Resultado):
    """Preferencias, donde `AGENTS.md` y el código no dicen lo mismo.

    El contrato afirma que el diálogo va sin paleta, porque colorear una
    casilla en Windows la convierte en botón owner-drawn y NVDA la lee como
    botón y sin estado. El código colorea nueve casillas y un radio. Acá se
    mira qué rol expone Windows de verdad, que es lo que zanja la discusión.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias: no se pudo abrir, {exc}")
        return
    dlg = app.esperar_ventana("Preferencias", segundos=15)
    if dlg is None:
        res.fallo("preferencias: no abrió")
        return
    res.nota(f"preferencias: abre, clase {dlg['clase']}")

    controles = app.arbol("Preferencias")
    revisar_nombres(controles, res, "preferencias")

    # Solo lo que está en pantalla: el resto vive en pestañas no seleccionadas
    # y Windows no lo expone, así que compararlo daría una diferencia falsa.
    casillas_wx = [c for c in controles
                   if c["clase"] == "CheckBox" and c.get("en_pantalla")]
    radios_wx = [c for c in controles
                 if c["clase"] in ("RadioButton", "RadioBox")
                 and c.get("en_pantalla")]
    res.nota(f"preferencias, pestaña visible: wx dice {len(casillas_wx)} "
             f"casillas y {len(radios_wx)} radios")

    roles = roles_segun_windows("Preferencias")
    if not roles:
        res.nota("preferencias: no se pudo leer el árbol de Windows, se salta "
                 "la comprobación de owner-drawn")
    else:
        vistos_casilla = roles.get("CheckBox", 0)
        vistos_radio = roles.get("RadioButton", 0)
        res.nota(f"preferencias: Windows expone {vistos_casilla} CheckBox y "
                 f"{vistos_radio} RadioButton")
        if casillas_wx and vistos_casilla < len(casillas_wx):
            res.fallo(
                "preferencias: wx creó %d casillas y Windows solo expone %d "
                "como CheckBox. Las que faltan se anuncian con otro rol, que "
                "es lo que avisa AGENTS.md sobre el color."
                % (len(casillas_wx), vistos_casilla))

    orden = recorrer_tab(app, res, "preferencias", vueltas=20)
    res.nota(f"preferencias, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden))

    # Y ahora el resto de las pestanas, una por una. Auditar solo la visible
    # dejaba fuera la pagina de atajos entera, que son veinte botones.
    try:
        respuesta = app.pedir("pestanas", ventana="Preferencias")
    except Exception as exc:
        res.nota(f"preferencias: no se pudieron listar las pestañas, {exc}")
        respuesta = {}
    if not respuesta.get("ok"):
        if respuesta:
            res.nota("preferencias: no se pudieron listar las pestañas, "
                     + str(respuesta.get("error", "sin motivo")))
        info = None
    else:
        info = respuesta.get("datos", {})
    if info:
        paginas = info.get("paginas", [])
        res.nota(f"preferencias: {len(paginas)} pestañas: "
                 + ", ".join(paginas))
        for i, nombre in enumerate(paginas):
            app.pedir("pestanas", ventana="Preferencias", indice=i)
            visibles = [c for c in app.arbol("Preferencias")
                        if c.get("en_pantalla")]
            revisar_nombres(visibles, res, f"preferencias/{nombre}")
            casillas = [c for c in visibles if c["clase"] == "CheckBox"]
            # Ojo con la diferencia, que ya produjo una alarma falsa el
            # 21/08/2026: `wx.RadioBox` es un CONTENEDOR, un solo control para
            # wx, y Windows expone sus opciones como varios RadioButton
            # sueltos. Compararlos juntos da siempre un desajuste inventado.
            radios = [c for c in visibles if c["clase"] == "RadioButton"]
            cajas_radio = [c for c in visibles if c["clase"] == "RadioBox"]
            # Sincronizar con un hecho, no con un reloj. Windows redibuja la
            # pestana nueva cuando le parece, y un `sleep` fijo daba dos
            # recuentos distintos en dos corridas seguidas: el 21/08/2026 eso
            # produjo una alarma que no era tal. Se espera a que el arbol de
            # accesibilidad muestre algo de ESTA pagina antes de contar nada.
            testigo = ""
            for c in visibles:
                texto = (c.get("etiqueta") or c.get("nombre") or "")
                texto = texto.replace("&", "").strip()
                if len(texto) > 6:
                    testigo = texto.lower()
                    break
            roles = {}
            limite_pag = time.time() + 10
            while time.time() < limite_pag:
                roles = roles_segun_windows("Preferencias")
                if not testigo:
                    break
                todos = [n.replace("&", "").strip().lower()
                         for lista in _ULTIMOS_NOMBRES.values() for n in lista]
                if any(testigo in n or n in testigo for n in todos if n):
                    break
                time.sleep(0.4)
            else:
                res.nota(f"preferencias/{nombre}: Windows no llegó a mostrar "
                         f"«{testigo[:40]}», no se juzgan los roles")
                roles = {}

            if roles and casillas and roles.get("CheckBox", 0) < len(casillas):
                res.fallo(
                    "preferencias/%s: wx creó %d casillas y Windows solo "
                    "expone %d como CheckBox"
                    % (nombre, len(casillas), roles.get("CheckBox", 0)))
            if roles and cajas_radio:
                sueltos = roles.get("RadioButton", 0) - len(radios)
                if sueltos <= 0:
                    # Nota y no fallo, a propósito. Esta misma cuenta dio la
                    # alarma del 21/08/2026 y el dueño la desmintió probándolo
                    # con NVDA: se lee bien. La medición depende de cuándo
                    # Windows termine de redibujar la pestaña, así que da
                    # números distintos en corridas seguidas. Mientras no se
                    # sepa medirla estable, no puede acusar a nadie.
                    res.nota(
                        "preferencias/%s: %d agrupación(es) de radios y Windows "
                        "no expone ninguna opción como RadioButton; la medida "
                        "es inestable y ya se desmintió con NVDA, así que no "
                        "cuenta como fallo" % (nombre, len(cajas_radio)))
                else:
                    res.nota(
                        "preferencias/%s: %d agrupación(es) de radios, y "
                        "Windows expone %d opciones como RadioButton pese al "
                        "color" % (nombre, len(cajas_radio), sueltos))
            if roles and radios and roles.get("RadioButton", 0) < len(radios):
                vistos = {n.replace("&", "").strip().lower()
                          for n in nombres_segun_windows("RadioButton")}
                ausentes = [
                    (c.get("etiqueta") or c.get("nombre") or "?").replace("&", "")
                    for c in radios
                    if (c.get("etiqueta") or c.get("nombre") or ""
                        ).replace("&", "").strip().lower() not in vistos]
                res.fallo(
                    "preferencias/%s: wx creó %d radios y Windows solo expone "
                    "%d como RadioButton. No aparece: %s"
                    % (nombre, len(radios), roles.get("RadioButton", 0),
                       ", ".join(ausentes) or "no se pudo emparejar por nombre"))
                for rol_otro in ("Button", "Group", "Custom", "Pane", "Text"):
                    for n in nombres_segun_windows(rol_otro):
                        if n and any(n.replace("&", "").strip().lower()
                                     == a.strip().lower() for a in ausentes):
                            res.nota("  Windows lo expone como %s" % rol_otro)

    app.pedir("cerrar_ventana", ventana="Preferencias")


def escenario_preferencias_categorias(app: Aplicacion, args, res: Resultado):
    """Las 13 categorías de Preferencias, una por una.

    El escenario `preferencias` audita solo la categoría a la vista. Acá se
    recorre cada pestaña y se auditan sus controles visibles con Tab, sin
    tocar ningún valor y cerrando sin guardar.

    Solo se anota cuántas paradas tuvo cada categoría, sin listarlas: en
    «API y sesión» los campos muestran la clave y el secreto del dueño, y
    eso no puede quedar en el informe ni en la terminal.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias_categorias: no se pudo abrir, {exc}")
        return
    if app.esperar_ventana("Preferencias", segundos=15) is None:
        res.fallo("preferencias_categorias: Preferencias no abrió")
        return
    try:
        respuesta = app.pedir("pestanas", ventana="Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias_categorias: no se pudieron listar las "
                  f"pestañas, {exc}")
        app.pedir("cerrar_ventana", ventana="Preferencias")
        return
    paginas = respuesta.get("datos", {}).get("paginas", [])
    if len(paginas) < 13:
        res.fallo(f"preferencias_categorias: hay {len(paginas)} categorías, "
                  f"se esperaban 13")
    if any(n.strip().lower() in ("diagnóstico", "diagnostico")
           for n in paginas):
        res.fallo("preferencias_categorias: existe la categoría "
                  "«Diagnóstico», que ya no debería existir")
    if paginas and paginas[0].strip().lower() != "general":
        res.fallo(f"preferencias_categorias: la primera categoría es "
                  f"«{paginas[0]}» y debería ser «General»")
    try:
        for i, nombre in enumerate(paginas):
            app.pedir("pestanas", ventana="Preferencias", indice=i)
            time.sleep(0.8)
            visibles = [c for c in app.arbol("Preferencias")
                        if c.get("en_pantalla")]
            revisar_nombres(visibles, res, f"Preferencias/{nombre}")
            orden = recorrer_tab(app, res, f"Preferencias/{nombre}",
                                 vueltas=40, ventana="Preferencias")
            res.nota(f"Preferencias/{nombre}: {len(orden)} paradas de Tab")
            if len(orden) < 3:
                res.fallo(f"Preferencias/{nombre}: solo {len(orden)} paradas "
                          f"de Tab, la categoría quedó sin contenido "
                          f"alcanzable")
    finally:
        app.pedir("cerrar_ventana", ventana="Preferencias")


def _sonido_inicio_guardado_en_disco() -> str:
    """El valor de `[ui] sonido_inicio` en el `config.ini` real, en minúsculas."""
    import configparser
    try:
        from bellbird.core import paths
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(paths.config_ini(), encoding="utf-8")
        return parser.get("ui", "sonido_inicio", fallback="").strip().lower()
    except Exception:
        return ""


def escenario_preferencias_persisten(app: Aplicacion, args, res: Resultado):
    """Una preferencia cambiada y guardada se conserva al reabrir Preferencias.

    Invierte la casilla «Reproducir sonido de inicio» (General, clave
    `[ui] sonido_inicio`), guarda, comprueba el `config.ini` y reabre para
    comprobar que la casilla muestra el valor invertido. Restaura el valor
    original en un `finally`, como `escenario_transmitir_destino`.
    """
    NOMBRE_CASILLA = "Reproducir sonido de inicio"
    previo_txt = _sonido_inicio_guardado_en_disco()
    previo = previo_txt in ("true", "yes", "1", "on")
    invertido = not previo
    esperado_txt = "true" if invertido else "false"
    try:
        app.pedir("frente")
        try:
            app.abrir_por_menu("Preferencias")
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudo abrir, {exc}")
            return
        if app.esperar_ventana("Preferencias", segundos=15) is None:
            res.fallo("preferencias_persisten: Preferencias no abrió")
            return
        try:
            paginas = app.pedir("pestanas", ventana="Preferencias").get(
                "datos", {}).get("paginas", [])
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudieron listar las "
                      f"pestañas, {exc}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        try:
            indice = next(i for i, n in enumerate(paginas)
                          if n.strip().lower() == "general")
        except StopIteration:
            res.fallo(f"preferencias_persisten: no existe la categoría "
                      f"«General»; hay {paginas}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        app.pedir("pestanas", ventana="Preferencias", indice=indice)
        time.sleep(0.8)
        # La casilla se invierte con la orden `casilla`, sin teclas del
        # sistema: `pulsar` manda un evento de botón que no alterna
        # casillas, y `teclas` exige que Windows deje la app al frente.
        try:
            app.pedir("casilla", ventana="Preferencias", nombre=NOMBRE_CASILLA)
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudo invertir la "
                      f"casilla «{NOMBRE_CASILLA}», {exc}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        time.sleep(0.5)
        # Guardar se pulsa por su `name=`, como los botones de `captura_atajo`.
        app.pedir("pulsar", nombre="GuardarPreferencias")
        if app.esperar_ventana("Preferencias", segundos=4) is not None:
            res.fallo("preferencias_persisten: «Guardar» no cerró Preferencias")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        en_disco = _sonido_inicio_guardado_en_disco()
        if en_disco != esperado_txt:
            res.fallo(f"preferencias_persisten: el config.ini dice "
                      f"«{en_disco or 'vacío'}» y debería decir "
                      f"«{esperado_txt}»")
        else:
            res.nota(f"preferencias_persisten: el config.ini quedó en "
                     f"«{esperado_txt}»")
        # Reabrir y comprobar que la casilla muestra el valor invertido.
        try:
            app.abrir_por_menu("Preferencias")
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudo reabrir, {exc}")
            return
        if app.esperar_ventana("Preferencias", segundos=15) is None:
            res.fallo("preferencias_persisten: al reabrir no abrió")
            return
        try:
            paginas = app.pedir("pestanas", ventana="Preferencias").get(
                "datos", {}).get("paginas", [])
            indice = next(i for i, n in enumerate(paginas)
                          if n.strip().lower() == "general")
            app.pedir("pestanas", ventana="Preferencias", indice=indice)
        except StopIteration:
            res.fallo(f"preferencias_persisten: al reabrir no existe la "
                      f"categoría «General»; hay {paginas}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        except Exception as exc:
            res.fallo(f"preferencias_persisten: al reabrir no se pudo ir a "
                      f"«General», {exc}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        time.sleep(0.8)
        controles = app.arbol("Preferencias")
        casilla = next((c for c in controles
                        if c.get("clase") == "CheckBox"
                        and (c.get("nombre") or "") == NOMBRE_CASILLA), None)
        if casilla is None:
            res.fallo(f"preferencias_persisten: al reabrir no existe la "
                      f"casilla «{NOMBRE_CASILLA}»")
        elif "marcado" not in casilla:
            res.fallo("preferencias_persisten: la sonda no informa si la "
                      "casilla está marcada")
        elif bool(casilla.get("marcado")) != invertido:
            res.fallo(f"preferencias_persisten: al reabrir la casilla muestra "
                      f"«{'marcada' if casilla.get('marcado') else 'sin marcar'}» "
                      f"y debería mostrar "
                      f"«{'marcada' if invertido else 'sin marcar'}»")
        else:
            res.nota(f"preferencias_persisten: al reabrir la casilla muestra "
                     f"«{'marcada' if invertido else 'sin marcar'}»")
        app.pedir("cerrar_ventana", ventana="Preferencias")
    finally:
        try:
            from bellbird.core import paths
            from bellbird.core.config import guardar_opcion
            guardar_opcion(paths.config_ini(), "ui", "sonido_inicio",
                           "true" if previo else "false")
        except Exception as exc:
            res.nota("preferencias_persisten: no se pudo restaurar el valor "
                     f"original ({exc})")
        else:
            res.nota("preferencias_persisten: el valor original vuelve a "
                     f"«{'true' if previo else 'false'}»")


def escenario_programados(app: Aplicacion, args, res: Resultado):
    """La pestaña de mensajes automáticos, control por control.

    Interesa sobre todo por los dos `wx.SpinCtrl`: son controles COMPUESTOS
    (una caja de texto más dos flechas), y en Windows el `name=` de wx no
    siempre llega al servicio de accesibilidad. Un intervalo que el lector
    anuncia como «cuadro de edición» a secas, sin decir si es el mínimo o el
    máximo, deja al usuario adivinando cuál de los dos está tocando.
    """
    etiqueta_pag = "Mensajes automáticos"
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"programados: no se pudo abrir Preferencias, {exc}")
        return
    if app.esperar_ventana("Preferencias", segundos=15) is None:
        res.fallo("programados: Preferencias no abrió")
        return

    try:
        paginas = app.pedir("pestanas", ventana="Preferencias").get(
            "datos", {}).get("paginas", [])
        if etiqueta_pag not in paginas:
            res.fallo(f"programados: no existe la pestaña «{etiqueta_pag}»; "
                      f"hay {paginas}")
            return
        res.nota(f"pestaña encontrada, es la {paginas.index(etiqueta_pag) + 1} "
                 f"de {len(paginas)}")
        app.pedir("pestanas", ventana="Preferencias",
                  indice=paginas.index(etiqueta_pag))
        time.sleep(0.4)

        controles = app.arbol("Preferencias")
        visibles = [c for c in controles if c.get("en_pantalla")]
        revisar_nombres(visibles, res, "programados")

        # El texto de introducción es donde se explican los límites de la API.
        # Si desaparece, el usuario no tiene dónde enterarse.
        textos = " ".join((c.get("etiqueta") or "") + " " + (c.get("nombre") or "")
                          for c in controles)
        for clave, que in (("5 minutos", "el intervalo mínimo"),
                           ("200 caracteres", "el límite de caracteres"),
                           ("enlaces", "el aviso sobre los enlaces")):
            if clave not in textos:
                res.fallo(f"programados: la introducción no menciona {que}")
        if all(k in textos for k in ("5 minutos", "200 caracteres", "enlaces")):
            res.nota("la introducción explica intervalo, longitud y enlaces")

        # Los controles que tienen que estar, por su name= de wx.
        esperados = ("ActivarProgramados", "Mensajes automáticos guardados",
                      "TextoProgramado",
                     "MinutosMin", "MinutosMax", "MensajeActivo",
                     "AgregarProgramado", "GuardarProgramado", "QuitarProgramado")
        nombres = {(c.get("nombre") or "") for c in controles}
        faltan = [n for n in esperados if n not in nombres]
        if faltan:
            res.fallo(f"programados: no aparecen en el árbol: {faltan}")
        else:
            res.nota(f"los {len(esperados)} controles de la pestaña están")
    finally:
        app.pedir("cerrar_ventana", ventana="Preferencias")

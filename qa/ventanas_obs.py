"""Cómo el banco de QA audita el panel de OBS.

La app abre OBS si hace falta al abrir el panel, así que el banco no lo lanza
por su cuenta: recorre el mismo camino que el usuario. El OBS que quedó abierto
lo cierra el final de la corrida, como con los demás escenarios.

Este módulo no importa `conducir.py`, que se corre como guion: recibe las
funciones del banco que necesita y se limita a ordenar las llamadas.
"""

from __future__ import annotations

import time

SEGUNDOS_CARGA_OBS = 90.0

TITULO_VENTANA = "Panel de OBS"

PESTANAS_OBS = ("General", "Escena", "Transmisión", "Audio", "Grabación")

PESTANA_GENERAL = 0
PESTANA_ESCENA = 1
PESTANA_TRANSMISION = 2
PESTANA_GRABACION = 4

ESPERADOS_EN_TODAS = ("Cerrar",)

ORDEN_TRANSMISION = ("Transmitir en directo", "Restream…")

ESPERADOS_POR_PESTANA = {
    "General": ("Estado", "Actualizar estado", "Mostrar OBS"),
    "Transmisión": ("Transmitir en directo", "Restream…"),
    "Escena": ("Escenas", "Cambiar escena", "Agregar escena", "Fuentes",
               "Aplicar diseño", "Agregar fuente",
               "Deshacer todos los cambios"),
    "Audio": ("Fuentes de audio", "Silenciar", "Elegir micrófono",
              "Probar nivel", "Filtros", "Escuchar"),
    "Grabación": ("Iniciar grabación", "Grabar también al transmitir",
                  "Grabaciones y clips"),
}


def descuadre_de_pestanas(encontradas: list[str],
                          esperadas: tuple[str, ...] = PESTANAS_OBS
                          ) -> str | None:
    """Las pestañas halladas si no son exactamente las esperadas, en orden.

    Devuelve `None` cuando coinciden. Si no, un texto que nombra las que
    encontró, para que el fallo del banco no obligue a adivinar.
    """
    vistas = [str(nombre).strip().casefold() for nombre in encontradas]
    queridas = [nombre.casefold() for nombre in esperadas]
    if vistas == queridas:
        return None
    return (f"las pestañas son {list(encontradas)} y deberían ser "
            f"{list(esperadas)}, en ese orden")


def esperados_de_pestana(nombre: str) -> tuple[str, ...]:
    """Los controles propios de esa pestaña, más los que están en todas."""
    clave = str(nombre).strip().casefold()
    for pagina, esperados in ESPERADOS_POR_PESTANA.items():
        if pagina.casefold() == clave:
            return (*esperados, *ESPERADOS_EN_TODAS)
    return ESPERADOS_EN_TODAS


def faltan_en_tab(esperados: tuple[str, ...],
                  orden: list[str]) -> list[str]:
    """Los esperados que no aparecen en el orden de Tab.

    Como en `auditar_dialogo`, se quita la marca de mnemónico y no se
    distingue mayúsculas: una etiqueta «&Fuente» sí ofrece «Fuente».
    """
    juntos = " ".join(str(parada) for parada in orden).replace("&", "").casefold()
    return [nombre for nombre in esperados
            if str(nombre).casefold() not in juntos]


def _nombre_de_parada(parada: str) -> str:
    texto = str(parada).split(": ", 1)[-1]
    return texto.replace("&", "").strip().casefold()


def orden_de_transmision(orden: list[str]) -> str | None:
    """El desorden de los controles de Transmisión, o `None` si están en orden.

    Solo mira los controles que aparecen en el recorrido de Tab.
    """
    queridos = [nombre.casefold() for nombre in ORDEN_TRANSMISION]
    vistos = [_nombre_de_parada(parada) for parada in orden]
    encontrados = [nombre for nombre in vistos if nombre in queridos]
    esperados = [nombre for nombre in queridos if nombre in encontrados]
    if encontrados:
        inicio = encontrados.index(esperados[0])
        encontrados = encontrados[inicio:] + encontrados[:inicio]
    if encontrados == esperados:
        return None
    return ("el orden de Tab de Transmisión es " + ", ".join(encontrados)
            + " y debería ser " + ", ".join(esperados))


def esperar_habilitado(app, faltan_habilitados, nombre: str, segundos: float,
                       res) -> bool:
    """Espera a que el control se habilite y lo dice si no llega a tiempo.

    Una ventana que consulta a OBS nace con sus controles deshabilitados y los
    habilita cuando termina la carga. Auditar antes mide la pantalla de espera,
    así que sin la habilitación no se sigue y el fallo nombra el control.
    """
    limite = time.monotonic() + segundos
    pendientes = [nombre]
    while True:
        try:
            pendientes = faltan_habilitados(
                app.arbol(TITULO_VENTANA), (nombre,))
        except Exception:
            pendientes = [nombre]
        if not pendientes or time.monotonic() >= limite:
            break
        time.sleep(0.5)
    if pendientes:
        res.fallo(f"Panel de OBS: «{pendientes[0]}» no se habilitó en "
                  f"{segundos:.0f} segundos")
        return False
    res.nota(f"Panel de OBS: «{nombre}» se habilitó, "
             "la carga inicial terminó")
    return True


def _pestana_actual(app) -> int:
    datos = app.pedir("pestanas", ventana=TITULO_VENTANA).get("datos", {})
    return int(datos.get("actual", -1))


def _abrir_panel(app, res) -> bool:
    """Abre el panel con Ctrl+Mayús+O en la pestaña General."""
    app.pedir("frente")
    try:
        app.teclas(("o", ["ctrl", "shift"]))
    except Exception as exc:
        res.fallo(f"Panel de OBS: no se pudo pulsar Ctrl+Mayús+O, {exc}")
        return False
    if app.esperar_ventana(TITULO_VENTANA, segundos=15) is None:
        res.fallo("Panel de OBS: Ctrl+Mayús+O no abrió la ventana")
        return False
    actual = _pestana_actual(app)
    if actual != PESTANA_GENERAL:
        res.fallo(f"Panel de OBS: Ctrl+Mayús+O abrió la pestaña {actual + 1}, "
                  f"debería abrir la {PESTANA_GENERAL + 1}")
        return False
    res.nota("Panel de OBS: Ctrl+Mayús+O abre en General")
    return True


def _ir_a_pestana(app, res, indice: int) -> bool:
    """Cambia de pestaña con Ctrl+Tab hasta la que se quiere auditar."""
    for _ in range(indice):
        try:
            app.teclas(("tab", ["ctrl"]))
        except Exception as exc:
            res.fallo(f"Panel de OBS: no se pudo pulsar Ctrl+Tab, {exc}")
            return False
    actual = _pestana_actual(app)
    if actual != indice:
        res.fallo(f"Panel de OBS: Ctrl+Tab dejó la pestaña {actual + 1}, "
                  f"debería dejar la {indice + 1}")
        return False
    res.nota(f"Panel de OBS: Ctrl+Tab llega a {PESTANAS_OBS[indice]}")
    return True


def _cerrar(app, res) -> None:
    app.pedir("cerrar_ventana", ventana=TITULO_VENTANA)
    if app.esperar_ventana(TITULO_VENTANA, segundos=4) is not None:
        res.fallo("Panel de OBS: la ventana no cerró")


def auditar_escena(app, res, recorrer_tab, revisar_nombres,
                   faltan_habilitados, vueltas_tab: int) -> None:
    """Abre el panel con Ctrl+Mayús+O, pasa a Escena con Ctrl+Tab y audita todo.

    La app abre OBS si hace falta y el final de la corrida lo cierra. Solo se
    cambia de pestaña, se recorre el Tab y se cierra la ventana: ningún botón
    ni casilla que cambie OBS.
    """
    if not _abrir_panel(app, res):
        return
    try:
        if not _ir_a_pestana(app, res, PESTANA_ESCENA):
            return
        _auditar_pestanas(app, res, recorrer_tab, revisar_nombres,
                          faltan_habilitados, vueltas_tab)
    finally:
        _cerrar(app, res)


def auditar_grabacion(app, res, recorrer_tab, revisar_nombres,
                      faltan_habilitados, vueltas_tab: int) -> None:
    """Abre el panel con Ctrl+Mayús+O, pasa a Grabación con Ctrl+Tab y audita."""
    if not _abrir_panel(app, res):
        return
    try:
        if not _ir_a_pestana(app, res, PESTANA_GRABACION):
            return
        if not esperar_habilitado(app, faltan_habilitados, "Iniciar grabación",
                                  SEGUNDOS_CARGA_OBS, res):
            return
        visibles = [c for c in app.arbol(TITULO_VENTANA)
                    if c.get("en_pantalla")]
        revisar_nombres(visibles, res, "Panel de OBS/Grabación")
        orden = recorrer_tab(app, res, "Panel de OBS/Grabación",
                             vueltas=vueltas_tab, ventana=TITULO_VENTANA)
        res.nota("Panel de OBS/Grabación, orden de Tab, "
                 f"{len(orden)} paradas: " + " > ".join(orden))
        for falta in faltan_en_tab(esperados_de_pestana("Grabación"), orden):
            res.fallo("Panel de OBS/Grabación: "
                      f"«{falta}» no aparece en el orden de Tab")
    finally:
        _cerrar(app, res)


def auditar_transmision(app, res, recorrer_tab, revisar_nombres,
                        faltan_habilitados, vueltas_tab: int) -> None:
    """Abre el panel con Ctrl+Mayús+O, pasa a Transmisión y la audita."""
    if not _abrir_panel(app, res):
        return
    try:
        if not _ir_a_pestana(app, res, PESTANA_TRANSMISION):
            return
        paginas = app.pedir("pestanas", ventana=TITULO_VENTANA).get(
            "datos", {}).get("paginas", [])
        descuadre = descuadre_de_pestanas(paginas)
        if descuadre:
            res.fallo(f"Panel de OBS: {descuadre}")
        if not esperar_habilitado(app, faltan_habilitados,
                                  "Transmitir en directo",
                                  SEGUNDOS_CARGA_OBS, res):
            return
        visibles = [c for c in app.arbol(TITULO_VENTANA)
                    if c.get("en_pantalla")]
        revisar_nombres(visibles, res, "Panel de OBS/Transmisión")
        orden = recorrer_tab(app, res, "Panel de OBS/Transmisión",
                             vueltas=vueltas_tab, ventana=TITULO_VENTANA)
        res.nota("Panel de OBS/Transmisión, orden de Tab, "
                 f"{len(orden)} paradas: " + " > ".join(orden))
        for falta in faltan_en_tab(esperados_de_pestana("Transmisión"), orden):
            res.fallo("Panel de OBS/Transmisión: "
                      f"«{falta}» no aparece en el orden de Tab")
        descuadre = orden_de_transmision(orden)
        if descuadre:
            res.fallo(f"Panel de OBS/Transmisión: {descuadre}")
    finally:
        _cerrar(app, res)


def _auditar_pestanas(app, res, recorrer_tab, revisar_nombres,
                      faltan_habilitados, vueltas_tab: int) -> None:
    """Recorre y audita cada pestaña de un panel de OBS ya abierto."""
    if not esperar_habilitado(app, faltan_habilitados, "Cambiar escena",
                              SEGUNDOS_CARGA_OBS, res):
        return
    try:
        paginas = app.pedir("pestanas", ventana=TITULO_VENTANA).get(
            "datos", {}).get("paginas", [])
    except Exception as exc:
        res.fallo(f"Panel de OBS: no se pudieron listar las pestañas, {exc}")
        return
    descuadre = descuadre_de_pestanas(paginas)
    if descuadre:
        res.fallo(f"Panel de OBS: {descuadre}")
    for i, nombre in enumerate(paginas):
        app.pedir("pestanas", ventana=TITULO_VENTANA, indice=i)
        time.sleep(0.8)
        visibles = [c for c in app.arbol(TITULO_VENTANA)
                    if c.get("en_pantalla")]
        revisar_nombres(visibles, res, f"Panel de OBS/{nombre}")
        orden = recorrer_tab(app, res, f"Panel de OBS/{nombre}",
                             vueltas=vueltas_tab, ventana=TITULO_VENTANA)
        res.nota(f"Panel de OBS/{nombre}, orden de Tab, {len(orden)} paradas: "
                 + " > ".join(orden))
        for falta in faltan_en_tab(esperados_de_pestana(nombre), orden):
            res.fallo(f"Panel de OBS/{nombre}: «{falta}» no aparece en el "
                      "orden de Tab")

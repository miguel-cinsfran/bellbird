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

PESTANAS_OBS = ("Escena", "Audio", "Grabación", "Fuentes", "Agregar",
                "General")

PESTANA_ESCENA = 0
PESTANA_GRABACION = 2

ESPERADOS_EN_TODAS = ("Ayuda", "Cerrar")

ESPERADOS_POR_PESTANA = {
    "Escena": ("Escena", "Cambiar escena", "Descripción de la escena",
               "Guardar imagen"),
    "Audio": ("Silenciar micrófono", "Elegir micrófono"),
    "Grabación": ("Estado", "Iniciar grabación",
                  "Grabar también al transmitir", "Actualizar estado",
                  "Grabaciones"),
    "Fuentes": ("Fuente", "Posición", "Mover fuente", "Detalle de la fuente",
                "Ancho", "Alto", "Cambiar tamaño", "Mostrar en la escena",
                "Bloquear posición", "Mover con flechas", "Traer al frente",
                "Traer adelante", "Enviar atrás", "Enviar al fondo",
                "Deshacer cambios"),
    "Agregar": ("Ventana", "Capturar ventana", "Agregar cámara"),
    "General": ("Estado de OBS", "Actualizar estado", "Mostrar OBS"),
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


def _abrir_con_atajo(app, res, tecla: str, esperada: int) -> bool:
    """Abre el panel con Ctrl+Mayús y comprueba en qué pestaña quedó."""
    app.pedir("frente")
    try:
        app.teclas((tecla, ["ctrl", "shift"]))
    except Exception as exc:
        res.fallo(f"Panel de OBS: no se pudo pulsar Ctrl+Mayús+{tecla.upper()}, "
                  f"{exc}")
        return False
    if app.esperar_ventana(TITULO_VENTANA, segundos=15) is None:
        res.fallo("Panel de OBS: Ctrl+Mayús+" + tecla.upper()
                  + " no abrió la ventana")
        return False
    actual = _pestana_actual(app)
    if actual != esperada:
        res.fallo("Panel de OBS: Ctrl+Mayús+" + tecla.upper()
                  + f" abrió la pestaña {actual + 1}, debería abrir la "
                  f"{esperada + 1}")
        return False
    res.nota("Panel de OBS: Ctrl+Mayús+" + tecla.upper()
             + f" abre en {PESTANAS_OBS[esperada]}")
    return True


def _cerrar(app, res) -> None:
    app.pedir("cerrar_ventana", ventana=TITULO_VENTANA)
    if app.esperar_ventana(TITULO_VENTANA, segundos=4) is not None:
        res.fallo("Panel de OBS: la ventana no cerró")


def auditar_escena(app, res, recorrer_tab, revisar_nombres,
                   faltan_habilitados, vueltas_tab: int) -> None:
    """Abre el panel con Ctrl+Mayús+E y audita sus seis pestañas.

    La app abre OBS si hace falta y el final de la corrida lo cierra. Solo se
    cambia de pestaña, se recorre el Tab y se cierra la ventana: ningún botón
    ni casilla que cambie OBS.
    """
    if not _abrir_con_atajo(app, res, "e", PESTANA_ESCENA):
        return
    try:
        _auditar_pestanas(app, res, recorrer_tab, revisar_nombres,
                          faltan_habilitados, vueltas_tab)
    finally:
        _cerrar(app, res)


def auditar_grabacion(app, res, recorrer_tab, revisar_nombres,
                      faltan_habilitados, vueltas_tab: int) -> None:
    """Abre el panel con Ctrl+Mayús+G y audita la pestaña Grabación."""
    if not _abrir_con_atajo(app, res, "g", PESTANA_GRABACION):
        return
    try:
        if not esperar_habilitado(app, faltan_habilitados, "Actualizar estado",
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

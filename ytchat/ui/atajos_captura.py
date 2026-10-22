"""Decisiones y textos de la captura de atajos."""

import wx

from ytchat.core import config as cfg
from ytchat.ui import teclado_altgr


# ── Captura de atajos (pulsar en vez de escribir) ─────────────────────────────
# Idea tomada del proyecto bellbird del dueño: en vez de teclear el atajo (con
# riesgo de escribirlo mal), se pulsa un botón, se captura la combinación real y
# se valida al vuelo (área correcta y sin conflicto). Así no hay atajos inválidos.

_TECLA_WX_A_TEXTO = {
    wx.WXK_LEFT: "left", wx.WXK_RIGHT: "right", wx.WXK_UP: "up", wx.WXK_DOWN: "down",
    wx.WXK_RETURN: "enter", wx.WXK_NUMPAD_ENTER: "enter", wx.WXK_SPACE: "space",
    wx.WXK_END: "end",
}


def tecla_texto(keycode: int) -> str | None:
    """Nombre de tecla en nuestro formato («left», «f5», «p»…) desde un keycode
    de wx. None si no es una tecla admitida como atajo."""
    if keycode in _TECLA_WX_A_TEXTO:
        return _TECLA_WX_A_TEXTO[keycode]
    if wx.WXK_F1 <= keycode <= wx.WXK_F12:
        return f"f{keycode - wx.WXK_F1 + 1}"
    if 33 <= keycode < 127:   # letras, dígitos y símbolos ASCII
        return chr(keycode).lower()
    return None


def combo_a_texto(mods: int, keycode: int) -> str | None:
    """(modificadores, keycode) de wx → texto tipo «ctrl+p», «alt+enter», «f5».
    None si la tecla no sirve como atajo. Deja que config valide el resto."""
    tecla = tecla_texto(keycode)
    if not tecla:
        return None
    partes = []
    if mods & wx.MOD_CONTROL: partes.append("ctrl")
    if mods & wx.MOD_ALT:     partes.append("alt")
    if mods & wx.MOD_SHIFT:   partes.append("shift")
    return "+".join(partes + [tecla]) if partes else tecla


_AREA_AYUDA = {
    "ctrl": "Debe ser Ctrl y una tecla (por ejemplo Ctrl+P).",
    "alt": "Debe ser Alt y una tecla (por ejemplo Alt+C).",
    "ctrl+shift": "Debe ser Ctrl+Mayús y una tecla (por ejemplo Ctrl+Mayús+P).",
    "alt+shift": "Debe ser Alt+Mayús y una tecla (por ejemplo Alt+Mayús+C).",
    "ctrl+alt": "Debe ser Ctrl+Alt y una flecha, Espacio, una letra o un número, o Ctrl+Alt+Mayús y Flecha izquierda o derecha (por ejemplo Ctrl+Alt+T).",
    "f": "Debe ser una tecla de función, de F1 a F12, sola, con Ctrl o con Ctrl+Mayús (por ejemplo F2 o Ctrl+F2).",
}
ETIQUETAS = {
    # Reproductor
    "rep_play": "Reproducir o pausa", "rep_retro": "Retroceder 1 minuto",
    "rep_avanz": "Avanzar 1 minuto", "rep_directo": "Ir al directo",
    "rep_detener": "Detener vídeo",
    "rep_mute": "Silenciar o activar audio",
    "rep_vol_menos": "Bajar volumen del reproductor",
    "rep_vol_mas": "Subir volumen del reproductor",
    "descargas_abrir": "Abrir el gestor de descargas",
    "pantalla_completa": "Pantalla completa",
    "abrir_preferencias": "Abrir Preferencias",
    "abrir_historial": "Abrir el historial de directos",
    "marcar_incidencia": "Marcar incidencia",
    "abrir_transmision": "Abrir Transmisión",
    "copiar_enlace": "Copiar enlace del directo",
    "obs_micro": "Silenciar el micrófono de OBS",
    "avisos_sobrecarga": "Activar o desactivar los avisos de sobrecarga",
    # Conexión y chat
    "conectar": "Conectar",
    "desconectar": "Desconectar", "enviar_chat": "Enviar mensaje al chat",
    "ir_lista": "Ir a la lista del panel actual", "salir": "Salir de la aplicación",
    # Voz / lectura
    "pausa": "Pausar o reanudar lectura", "detener_tts": "Detener voz actual",
    "velocidad_menos": "Bajar velocidad",
    "velocidad_mas": "Subir velocidad",
    "volumen_menos": "Bajar volumen del TTS",
    "volumen_mas": "Subir volumen del TTS",
    "silenciar_lectura": "Silenciar lectura TTS",
    "silenciar_sonidos": "Silenciar sonidos", "anunciar_estado": "Anunciar estado",
    "anunciar_autor": "Anunciar autor del último mensaje",
    "describir_escena": "Describir la escena de OBS",
    "consulta_rapida_ia": "Consulta rápida a la IA sobre la escena",
    "region_siguiente": "Región siguiente", "region_anterior": "Región anterior",
    # Música (Ctrl+Alt)
    "musica_play": "Reproducir o pausar la música",
    "musica_siguiente": "Siguiente canción",
    "musica_anterior": "Canción anterior",
    "musica_vol_mas": "Subir el volumen de la música",
    "musica_vol_menos": "Bajar el volumen de la música",
    "musica_que_suena": "Qué suena",
    "musica_silenciar": "Silenciar o devolver el sonido de la música",
    "musica_aleatorio": "Orden aleatorio de la música",
    "musica_repetir": "Cambiar la repetición de la música",
    "musica_detener": "Detener la música",
    "musica_adelantar": "Adelantar la música 10 segundos",
    "musica_retroceder": "Retroceder la música 10 segundos",
    "musica_ventana": "Abrir la ventana de música",
    "preguntar_ia": "Preguntar a la IA sobre la imagen",
    "chat_reciente_1": "Leer el último mensaje del chat",
    "chat_reciente_2": "Leer el mensaje 2 desde el final del chat",
    "chat_reciente_3": "Leer el mensaje 3 desde el final del chat",
    "chat_reciente_4": "Leer el mensaje 4 desde el final del chat",
    "chat_reciente_5": "Leer el mensaje 5 desde el final del chat",
    "chat_reciente_6": "Leer el mensaje 6 desde el final del chat",
    "chat_reciente_7": "Leer el mensaje 7 desde el final del chat",
    "chat_reciente_8": "Leer el mensaje 8 desde el final del chat",
    "chat_reciente_9": "Leer el mensaje 9 desde el final del chat",
    "chat_reciente_10": "Leer el mensaje 10 desde el final del chat",
}


NOTA_PAGINA = (
    "Cada familia de atajos tiene su modificador: Ctrl para el "
    "reproductor, Alt para el chat, Ctrl+Mayús para abrir ventanas, "
    "Alt+Mayús para el directo y OBS, Ctrl+Alt para la música y las "
    "teclas F para la voz. Pulsa un botón y luego la combinación que "
    "quieras: se comprueba sola que sirva para esa familia y que no "
    "choque con otra. F6, Mayús+F6, F9 a F12 y Alt+F4 son fijas y se "
    "muestran para que no se puedan pisar.")


def mostrar_atajo(valor: str) -> str:
    """Devuelve el texto legible de un atajo, en español."""
    if not valor:
        return "(sin asignar)"
    return atajo_legible(valor)


# Tecla guardada → nombre en español para leer en voz alta. Cubre las teclas
# con nombre que admite la app; lo no listado (letras, dígitos, F1 a F12)
# sale en mayúscula.
_NOMBRE_TECLA_LEER = {
    "home": "Inicio", "end": "Fin",
    "left": "Flecha izquierda", "right": "Flecha derecha",
    "up": "Flecha arriba", "down": "Flecha abajo",
    "pageup": "Re Pág", "pagedown": "Av Pág",
    "delete": "Supr", "insert": "Ins",
    "enter": "Intro", "return": "Intro",
    "space": "Espacio", "backspace": "Retroceso", "back": "Retroceso",
    "escape": "Escape", "esc": "Escape", "tab": "Tab",
}
_MOD_LEER = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Mayús"}


def atajo_legible(texto_guardado: str | None) -> str:
    """Texto en español de un atajo guardado, para leer en voz alta.

    «ctrl+end» → «Ctrl+Fin», «alt+d» → «Alt+D», «f2» → «F2».
    "" si no hay atajo (desactivado en Preferencias).
    """
    if not texto_guardado:
        return ""
    partes = []
    for parte in str(texto_guardado).strip().lower().replace(" ", "").split("+"):
        if not parte:
            continue
        if parte in _MOD_LEER:
            partes.append(_MOD_LEER[parte])
        elif parte in _NOMBRE_TECLA_LEER:
            partes.append(_NOMBRE_TECLA_LEER[parte])
        else:
            partes.append(parte.upper())
    return "+".join(partes)


def etiqueta_boton(etiqueta: str, valor: str) -> str:
    """Devuelve la etiqueta completa de un botón de atajo."""
    return f"{etiqueta}: {mostrar_atajo(valor)}"


def etiqueta_de_accion(accion: str) -> str:
    """Nombre legible de una acción, o la clave en frase si falta."""
    try:
        etiqueta = ETIQUETAS.get(accion)
        if etiqueta is not None:
            return etiqueta
        return str(accion).replace("_", " ").capitalize()
    except Exception:
        return ""


def texto_de_espera(etiqueta: str, ayuda_area: str) -> str:
    """Devuelve el anuncio para entrar en modo captura."""
    return (f"Pulsa la combinación para {etiqueta}. {ayuda_area} "
            "Intro la deja sin atajo. Escape cancela.")


def resolver(accion: str, combo: str | None,
             valores: dict[str, str],
             altgr=None) -> tuple[str, str | None, str]:
    """Decide qué hacer con una combinación y construye su anuncio."""
    etiqueta = ETIQUETAS.get(accion, accion.replace("_", " ").capitalize())
    if combo is None:
        return "desactivado", "", f"{etiqueta} sin atajo. Desactivado."

    # Hay fijas que la gramática editable no admite; por eso este choque va antes.
    for otra, valor in valores.items():
        if otra != accion and valor and valor == combo:
            otra_etiqueta = ETIQUETAS.get(
                otra, otra.replace("_", " ").capitalize())
            return "rechazado", None, f"Ya lo usa: {otra_etiqueta}. Elige otra."

    normalizado = cfg._normalizar_atajo(combo)
    if normalizado is None:
        return "rechazado", None, "Esa combinación no se puede usar. Elige otra."
    if not cfg.atajo_valido_para_area(accion, normalizado):
        ayuda = _AREA_AYUDA.get(cfg.ATAJOS_AREA.get(accion), "")
        return "rechazado", None, f"No vale aquí. {ayuda}"

    if normalizado.startswith("ctrl+alt+"):
        tecla = normalizado.split("+")[-1]
        if len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
            if altgr is None:
                altgr = teclado_altgr.caracter_altgr
            escrito = altgr(tecla)
            if escrito:
                return "rechazado", None, (
                    f"Con este teclado, AltGr+{tecla.upper()} escribe "
                    f"{escrito}. Elige otra.")

    for otra, valor in valores.items():
        if otra != accion and valor and valor == normalizado:
            otra_etiqueta = ETIQUETAS.get(
                otra, otra.replace("_", " ").capitalize())
            return "rechazado", None, f"Ya lo usa: {otra_etiqueta}. Elige otra."
    return "capturado", normalizado, (
        f"Capturado: {mostrar_atajo(normalizado)}. Se aplica al pulsar Guardar.")

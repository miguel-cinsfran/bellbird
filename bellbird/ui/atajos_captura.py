"""Decisiones y textos de la captura de atajos."""

import wx

from bellbird.core import config as cfg
from bellbird.core.idioma import N_, _
from bellbird.ui import teclado_altgr


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
    "ctrl": N_("Debe ser Ctrl y una tecla (por ejemplo Ctrl+P)."),
    "alt": N_("Debe ser Alt y una tecla (por ejemplo Alt+C)."),
    "ctrl+shift": N_("Debe ser Ctrl+Mayús y una tecla (por ejemplo Ctrl+Mayús+P)."),
    "alt+shift": N_("Debe ser Alt+Mayús y una tecla (por ejemplo Alt+Mayús+C)."),
    "ctrl+alt": N_("Debe ser Ctrl+Alt y una flecha, Espacio, una letra o un número, o Ctrl+Alt+Mayús y Flecha izquierda o derecha (por ejemplo Ctrl+Alt+T)."),
    "f": N_("Debe ser una tecla de función, de F1 a F12, sola, con Ctrl o con Ctrl+Mayús (por ejemplo F2 o Ctrl+F2)."),
}
ETIQUETAS = {
    # Reproductor
    "rep_play": N_("Reproducir o pausa"), "rep_retro": N_("Retroceder 1 minuto"),
    "rep_avanz": N_("Avanzar 1 minuto"), "rep_directo": N_("Ir al directo"),
    "rep_detener": N_("Detener vídeo"),
    "rep_mute": N_("Silenciar o activar audio"),
    "rep_vol_menos": N_("Bajar volumen del reproductor"),
    "rep_vol_mas": N_("Subir volumen del reproductor"),
    "descargas_abrir": N_("Abrir el gestor de descargas"),
    "pantalla_completa": N_("Pantalla completa"),
    "abrir_preferencias": N_("Abrir Preferencias"),
    "abrir_historial": N_("Abrir el historial de directos"),
    "marcar_incidencia": N_("Marcar incidencia"),
    "abrir_transmision": N_("Abrir Transmisión"),
    "mostrar_obs": N_("Mostrar OBS"),
    "copiar_enlace": N_("Copiar enlace del directo"),
    "obs_micro": N_("Silenciar el micrófono de OBS"),
    "avisos_sobrecarga": N_("Activar o desactivar los avisos de sobrecarga"),
    # Conexión y chat
    # Traductores: acción del atajo que conecta el chat.
    "conectar": N_("Conectar"),
    # Traductores: acción del atajo que desconecta el chat.
    "desconectar": N_("Desconectar"), "enviar_chat": N_("Enviar mensaje al chat"),
    "ir_lista": N_("Ir a la lista del panel actual"), "salir": N_("Salir de la aplicación"),
    # Voz / lectura
    "pausa": N_("Pausar o reanudar lectura"), "detener_tts": N_("Detener voz actual"),
    "velocidad_menos": N_("Bajar velocidad"),
    "velocidad_mas": N_("Subir velocidad"),
    "volumen_menos": N_("Bajar volumen del TTS"),
    "volumen_mas": N_("Subir volumen del TTS"),
    "silenciar_lectura": N_("Silenciar lectura TTS"),
    "silenciar_sonidos": N_("Silenciar sonidos"), "anunciar_estado": N_("Anunciar estado"),
    "anunciar_autor": N_("Anunciar autor del último mensaje"),
    "describir_escena": N_("Describir escena de OBS"),
    "consulta_rapida_ia": N_("Consulta rápida a la IA sobre la escena"),
    "region_siguiente": N_("Región siguiente"), "region_anterior": N_("Región anterior"),
    # Música (Ctrl+Alt)
    "musica_play": N_("Reproducir o pausar la música"),
    "musica_siguiente": N_("Siguiente canción"),
    "musica_anterior": N_("Canción anterior"),
    "musica_vol_mas": N_("Subir el volumen de la música"),
    "musica_vol_menos": N_("Bajar el volumen de la música"),
    "musica_que_suena": N_("Qué suena"),
    "musica_silenciar": N_("Silenciar o devolver el sonido de la música"),
    "musica_aleatorio": N_("Orden aleatorio de la música"),
    "musica_repetir": N_("Cambiar la repetición de la música"),
    "musica_detener": N_("Detener música"),
    "musica_adelantar": N_("Adelantar la música 10 segundos"),
    "musica_retroceder": N_("Retroceder la música 10 segundos"),
    "musica_ventana": N_("Abrir la ventana de música"),
    "preguntar_ia": N_("Preguntar a la IA sobre la imagen"),
    "chat_reciente_1": N_("Leer el último mensaje del chat"),
    "chat_reciente_2": N_("Leer el mensaje 2 desde el final del chat"),
    "chat_reciente_3": N_("Leer el mensaje 3 desde el final del chat"),
    "chat_reciente_4": N_("Leer el mensaje 4 desde el final del chat"),
    "chat_reciente_5": N_("Leer el mensaje 5 desde el final del chat"),
    "chat_reciente_6": N_("Leer el mensaje 6 desde el final del chat"),
    "chat_reciente_7": N_("Leer el mensaje 7 desde el final del chat"),
    "chat_reciente_8": N_("Leer el mensaje 8 desde el final del chat"),
    "chat_reciente_9": N_("Leer el mensaje 9 desde el final del chat"),
    "chat_reciente_10": N_("Leer el mensaje 10 desde el final del chat"),
}


NOTA_PAGINA = N_(
    "Cada familia de atajos tiene su modificador. Ctrl es para el "
    "reproductor, Alt para el chat y Ctrl+Mayús para abrir ventanas. "
    "Alt+Mayús es para el directo y OBS, Ctrl+Alt para la música y las "
    "teclas F para la voz. Pulsa un botón y luego la combinación que "
    "quieras. La aplicación comprueba que sirva para esa familia y que no "
    "choque con otra. F6, Mayús+F6, F9 a F12 y Alt+F4 son fijas, y se "
    "muestran para que no se puedan pisar.")


def mostrar_atajo(valor: str) -> str:
    """Devuelve el texto legible de un atajo, en español."""
    if not valor:
        return _("(sin asignar)")
    return atajo_legible(valor)


# Tecla guardada → nombre en español para leer en voz alta. Cubre las teclas
# con nombre que admite la app; lo no listado (letras, dígitos, F1 a F12)
# sale en mayúscula.
_NOMBRE_TECLA_LEER = {
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "home": N_("Inicio"), "end": N_("Fin"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "left": N_("Flecha izquierda"), "right": N_("Flecha derecha"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "up": N_("Flecha arriba"), "down": N_("Flecha abajo"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "pageup": N_("Re Pág"), "pagedown": N_("Av Pág"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "delete": N_("Supr"), "insert": N_("Ins"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "enter": N_("Intro"), "return": N_("Intro"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "space": N_("Espacio"), "backspace": N_("Retroceso"), "back": N_("Retroceso"),
    # Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
    "escape": N_("Escape"), "esc": N_("Escape"), "tab": N_("Tab"),
}
# Traductores: nombre de la tecla como se lee en voz alta, el del teclado en español de Windows.
_MOD_LEER = {"ctrl": N_("Ctrl"), "alt": N_("Alt"), "shift": N_("Mayús")}


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
            partes.append(_(_MOD_LEER[parte]))
        elif parte in _NOMBRE_TECLA_LEER:
            partes.append(_(_NOMBRE_TECLA_LEER[parte]))
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
            return _(etiqueta)
        return str(accion).replace("_", " ").capitalize()
    except Exception:
        return ""


def texto_de_espera(etiqueta: str, ayuda_area: str) -> str:
    """Devuelve el anuncio para entrar en modo captura."""
    return (_("Pulsa la combinación para {etiqueta}. {ayuda} "
              "Intro la deja sin atajo. Escape cancela.").format(
                  etiqueta=etiqueta, ayuda=_(ayuda_area) if ayuda_area else ""))


def resolver(accion: str, combo: str | None,
             valores: dict[str, str],
             altgr=None) -> tuple[str, str | None, str]:
    """Decide qué hacer con una combinación y construye su anuncio."""
    etiqueta = etiqueta_de_accion(accion)
    if combo is None:
        return "desactivado", "", _("{etiqueta} sin atajo. Desactivado.").format(etiqueta=etiqueta)

    # Hay fijas que la gramática editable no admite; por eso este choque va antes.
    for otra, valor in valores.items():
        if otra != accion and valor and valor == combo:
            otra_etiqueta = etiqueta_de_accion(otra)
            return "rechazado", None, _("Ya lo usa: {otra}. Elige otra.").format(otra=otra_etiqueta)

    normalizado = cfg._normalizar_atajo(combo)
    if normalizado is None:
        return "rechazado", None, _("Esa combinación no se puede usar. Elige otra.")
    if not cfg.atajo_valido_para_area(accion, normalizado):
        ayuda = _AREA_AYUDA.get(cfg.ATAJOS_AREA.get(accion), "")
        return "rechazado", None, _("No vale aquí. {ayuda}").format(ayuda=_(ayuda) if ayuda else "")

    if normalizado.startswith("ctrl+alt+"):
        tecla = normalizado.split("+")[-1]
        if len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
            if altgr is None:
                altgr = teclado_altgr.caracter_altgr
            escrito = altgr(tecla)
            if escrito:
                return "rechazado", None, (
                    _("Con este teclado, AltGr+{tecla} escribe "
                      "{letra}. Elige otra.").format(
                          tecla=tecla.upper(), letra=escrito))

    for otra, valor in valores.items():
        if otra != accion and valor and valor == normalizado:
            otra_etiqueta = etiqueta_de_accion(otra)
            return "rechazado", None, _("Ya lo usa: {otra}. Elige otra.").format(otra=otra_etiqueta)
    return "capturado", normalizado, (
        _("Capturado: {atajo}. Se aplica al pulsar Guardar.").format(
            atajo=mostrar_atajo(normalizado)))

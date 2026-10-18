"""Decisiones y textos de la captura de atajos."""

from ytchat.core import config as cfg
from ytchat.ui import teclado_altgr


_NOMBRE_TECLA_MOSTRAR = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "enter": "Enter",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "space": "Space", "end": "End",
}
_AREA_AYUDA = {
    "ctrl": "Debe ser Ctrl y una tecla (por ejemplo Ctrl+P).",
    "alt": "Debe ser Alt y una tecla (por ejemplo Alt+C).",
    "ctrl+alt": "Debe ser Ctrl+Alt y una flecha, Espacio, una letra o un número (por ejemplo Ctrl+Alt+T).",
    "f": "Debe ser una tecla de función, de F1 a F12, sola o con Ctrl (por ejemplo F2 o Ctrl+F2).",
}
_ETIQUETAS = {
    "rep_play": "Reproducir o pausa", "rep_retro": "Retroceder 1 minuto",
    "rep_avanz": "Avanzar 1 minuto", "rep_directo": "Ir al directo",
    "rep_detener": "Detener vídeo",
    "rep_mute": "Silenciar o activar audio",
    "rep_vol_menos": "Bajar volumen del reproductor",
    "rep_vol_mas": "Subir volumen del reproductor",
    "descargas_abrir": "Abrir el gestor de descargas",
    "pantalla_completa": "Pantalla completa", "conectar": "Conectar",
    "desconectar": "Desconectar", "enviar_chat": "Enviar mensaje al chat",
    "ir_lista": "Ir a la lista del panel actual", "salir": "Salir de la aplicación",
    "pausa": "Pausar o reanudar lectura", "detener_tts": "Detener voz actual",
    "velocidad_menos": "Bajar velocidad (fija)",
    "velocidad_mas": "Subir velocidad (fija)",
    "volumen_menos": "Bajar volumen del TTS (fijo)",
    "volumen_mas": "Subir volumen del TTS (fijo)",
    "silenciar_lectura": "Silenciar lectura TTS",
    "silenciar_sonidos": "Silenciar sonidos", "anunciar_estado": "Anunciar estado",
    "anunciar_autor": "Anunciar autor del último mensaje",
    "describir_escena": "Describir la escena de OBS",
    "avisos_sobrecarga": "Activar o desactivar los avisos de sobrecarga",
    "region_siguiente": "Región siguiente", "region_anterior": "Región anterior",
    "musica_play": "Reproducir o pausar la música",
    "musica_siguiente": "Siguiente tema",
    "musica_anterior": "Tema anterior",
    "musica_vol_mas": "Subir el volumen de la música",
    "musica_vol_menos": "Bajar el volumen de la música",
    "musica_que_suena": "Qué suena",
    "musica_ventana": "Abrir la ventana de música",
    "musica_listas": "Abrir las listas de música",
}


def mostrar_atajo(valor: str) -> str:
    """Devuelve el texto legible de un atajo."""
    if not valor:
        return "(sin asignar)"
    partes = [_NOMBRE_TECLA_MOSTRAR.get(parte, parte.upper())
              for parte in valor.split("+")]
    return "+".join(partes)


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


def texto_de_espera(etiqueta: str, ayuda_area: str) -> str:
    """Devuelve el anuncio para entrar en modo captura."""
    return (f"Pulsa la combinación para {etiqueta}. {ayuda_area} "
            "Enter la deja sin atajo. Escape cancela.")


def resolver(accion: str, combo: str | None,
             valores: dict[str, str],
             altgr=None) -> tuple[str, str | None, str]:
    """Decide qué hacer con una combinación y construye su anuncio."""
    etiqueta = _ETIQUETAS.get(accion, accion.replace("_", " ").capitalize())
    if combo is None:
        return "desactivado", "", f"{etiqueta} sin atajo. Desactivado."

    # Hay fijas que la gramática editable no admite; por eso este choque va antes.
    for otra, valor in valores.items():
        if otra != accion and valor and valor == combo:
            otra_etiqueta = _ETIQUETAS.get(
                otra, otra.replace("_", " ").capitalize())
            return "rechazado", None, f"Ya lo usa: {otra_etiqueta}. Elige otra."

    normalizado = cfg._normalizar_atajo(combo)
    if normalizado is None:
        return "rechazado", None, "Esa combinación no es válida."
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
            otra_etiqueta = _ETIQUETAS.get(
                otra, otra.replace("_", " ").capitalize())
            return "rechazado", None, f"Ya lo usa: {otra_etiqueta}. Elige otra."
    return "capturado", normalizado, (
        f"Capturado: {mostrar_atajo(normalizado)}. Se aplica al pulsar Guardar.")

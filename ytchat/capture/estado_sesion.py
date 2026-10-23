"""Formateo del estado de sesión que anuncia F2 (lógica pura, sin wx).

Inspirado en el `status_formatter` de bellbird (otro proyecto del dueño): una
función pura toma un snapshot inmutable de la sesión y un conjunto de
componentes activos (toggles) y arma la frase en español. Aislado aquí para
configurarlo y probarlo sin GUI; qué se anuncia se elige en
Preferencias → Estado (F2).

Antes F2 decía cosas internas del TTS (cola, velocidad, volumen) poco útiles
para quien mira un directo. Ahora, por defecto, prioriza los datos del
contenido: estado, título, canal, espectadores, mensajes leídos y aportes; lo
técnico queda disponible pero desactivado.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.core import config_predeterminada


# Códigos de tipo de conexión → etiqueta legible.
_TIPO_TXT = {
    "live_youtube": "Directo de YouTube",
    "live_tiktok":  "Directo de TikTok",
    "vod":          "Vídeo",
    "upcoming":     "Directo programado",
}


@dataclass(frozen=True)
class SnapshotSesion:
    """Foto inmutable de la sesión para formatear. Los campos que no apliquen
    van en su valor «vacío» (None, "", 0) y su componente se omite."""
    conectado: bool = False
    tipo: str = ""              # clave de _TIPO_TXT, o ""
    titulo: str = ""
    canal: str = ""
    espectadores: int | None = None
    espectadores_total: int | None = None
    segundos_directo: int | None = None
    desfase_directo: str = ""
    mensajes_leidos: int = 0
    aportes: int = 0            # nº de Super Chats (YouTube) o regalos (TikTok)
    total_aportes: str = ""     # ya formateado (p. ej. "US$12.50"), "" si no hay
    en_cola: int = 0
    voz_velocidad: int = 0
    voz_volumen: int = 0
    lectura_silenciada: bool = False
    overlay_puerto: int | None = None
    overlay_clientes: int = 0
    programados_proximo: str = ""
    descartados: str = ""
    obs_transmision: str = ""
    obs_grabacion: str = ""
    obs_escena: str = ""
    transmision_supervisada: str = ""
    atajo_directo: str = ""   # texto legible del atajo de Ir al directo
                              # (p. ej. «Ctrl+Fin»); "" si está desactivado
    musica: str = ""          # qué suena ahora, ya formateado; "" si no hay
    igualando: str = ""       # progreso de la igualación, ya formateado; "" si no hay


# Orden canónico de los componentes: estado → contenido → actividad → ajustes.
COMPONENTES: tuple[str, ...] = (
    "estado",
    "titulo",
    "canal",
    "espectadores",
    "tiempo_directo",
    "desfase_directo",
    "mensajes_leidos",
    "aportes",
    "en_cola",
    "voz",
    "lectura_silenciada",
    "overlay",
    "programados",
    "descartados",
    "obs_transmision",
    "obs_grabacion",
    "obs_escena",
    "musica",
    "igualando",
)

# Activos por defecto: derivan de la sección [estado] de la fuente canónica.
# Lo relevante para quien mira un directo viene activado; lo técnico apagado.
def _activos_desde_canonica() -> frozenset[str]:
    sec = config_predeterminada.seccion("estado")
    return frozenset(k for k, v in sec.items()
                     if v.strip().lower() in ("true", "yes", "1", "on"))


ACTIVOS_DEFECTO: frozenset[str] = _activos_desde_canonica()

# Etiquetas para el editor de Preferencias.
ETIQUETAS = {
    "estado":             "Estado de conexión y tipo",
    "titulo":             "Título del vídeo o directo",
    "canal":              "Canal o autor",
    "espectadores":       "Espectadores ahora",
    "tiempo_directo":     "Tiempo que lleva el directo",
    "desfase_directo":    "Cuánto por detrás del directo va el reproductor",
    "mensajes_leidos":    "Mensajes leídos",
    "aportes":            "Super Chats / regalos",
    "en_cola":            "Mensajes en cola de lectura",
    "voz":                "Velocidad y volumen de la voz",
    "lectura_silenciada": "Aviso de lectura silenciada",
    "overlay":            "Panel de chat para transmitir",
    "programados":        "Mensajes automáticos",
    "descartados":        "Mensajes descartados",
    "obs_transmision":    "Estado de la transmisión de OBS",
    "obs_grabacion":      "Estado de la grabación de OBS",
    "obs_escena":         "Escena al aire en OBS",
    "musica":             "Música que suena",
    "igualando":          "Igualación del volumen de la música",
}


def _fmt_num(n) -> str:
    """Miles con punto al estilo español: 30044 → «30.044»."""
    try:    return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError): return str(n)


def _duracion(segundos: int) -> str:
    if segundos < 60:
        return "menos de un minuto"
    minutos = segundos // 60
    # El corte en 48 horas conserva legibles los maratones de hasta dos días.
    if minutos >= 48 * 60:
        dias = minutos // (24 * 60)
        # Hoy es inalcanzable con el corte fijado en 48 horas.
        return f"{dias} día" if dias == 1 else f"{dias} días"
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas} h {minutos} min"
    return f"{minutos} min"


def _render_estado(s: SnapshotSesion, largo: bool) -> str:
    if not s.conectado:
        return "Desconectado"
    return _TIPO_TXT.get(s.tipo, "Conectado")


def _render_titulo(s: SnapshotSesion, largo: bool) -> str:
    t = (s.titulo or "").strip()
    if not t:
        return ""
    return f"Título: {t}" if largo else t


def _render_canal(s: SnapshotSesion, largo: bool) -> str:
    c = (s.canal or "").strip()
    return (f"Canal: {c}" if c else "")


def _render_espectadores(s: SnapshotSesion, largo: bool) -> str:
    if s.espectadores is None:
        return ""
    n = _fmt_num(s.espectadores)
    # En un directo es el nº de espectadores AHORA; en un vídeo, las vistas
    # totales (números distintos, no confundir).
    en_directo = s.tipo in ("live_youtube", "live_tiktok")
    palabra = "espectadores" if en_directo else "vistas"
    if s.espectadores == 1:
        palabra = "espectador" if en_directo else "vista"
    if s.tipo == "live_tiktok" and s.espectadores_total is not None:
        total = _fmt_num(s.espectadores_total)
        if largo:
            return f"{palabra.capitalize()}: {n} ahora, {total} en total"
        return f"{n} {palabra} ahora, {total} en total"
    return f"{palabra.capitalize()}: {n}" if largo else f"{n} {palabra}"


def _render_tiempo_directo(s: SnapshotSesion, largo: bool) -> str:
    if s.segundos_directo is None or s.segundos_directo < 0:
        return ""
    texto = _duracion(s.segundos_directo)
    return (f"Tiempo del directo: {texto}" if largo
            else f"Lleva {texto}")


def _render_desfase_directo(s: SnapshotSesion, largo: bool) -> str:
    texto = (s.desfase_directo or "").strip()
    if not texto:
        return ""
    base = f"Reproductor: {texto}" if largo else texto
    atajo = (s.atajo_directo or "").strip()
    if atajo:
        vuelta = f"Pulsa {atajo} para volver al directo"
    else:
        vuelta = "Para volver: menú Reproductor, Ir al directo"
    # En largo la línea es una frase completa y lleva su punto; en corto
    # lo pone el punto final de la frase armada.
    if largo:
        return f"{base}. {vuelta}."
    return f"{base}. {vuelta}"


def _render_mensajes_leidos(s: SnapshotSesion, largo: bool) -> str:
    n = _fmt_num(s.mensajes_leidos)
    return f"Mensajes leídos: {n}" if largo else f"{n} leídos"


def _render_aportes(s: SnapshotSesion, largo: bool) -> str:
    if s.aportes <= 0:
        return ""
    # «Super Chats» en YouTube, «regalos» en TikTok.
    palabra = "regalos" if s.tipo == "live_tiktok" else "Super Chats"
    base = f"{s.aportes} {palabra}"
    if s.total_aportes:
        base += f" ({s.total_aportes})"
    return f"Aportes: {base}" if largo else base


def _render_en_cola(s: SnapshotSesion, largo: bool) -> str:
    n = _fmt_num(s.en_cola)
    return f"En cola: {n}" if largo else f"{n} en cola"


def _render_voz(s: SnapshotSesion, largo: bool) -> str:
    return (f"Voz: velocidad {s.voz_velocidad}, volumen {s.voz_volumen}%")


def _render_lectura_silenciada(s: SnapshotSesion, largo: bool) -> str:
    return "Lectura silenciada" if s.lectura_silenciada else ""


def _render_overlay(s: SnapshotSesion, largo: bool) -> str:
    if s.overlay_puerto is None:
        return ""
    if s.overlay_clientes:
        return f"Panel de chat activo en el puerto {s.overlay_puerto}, mostrándose"
    return (f"Panel de chat activo en el puerto {s.overlay_puerto}, pero nadie "
            "lo está mostrando")


def _render_programados(s: SnapshotSesion, largo: bool) -> str:
    return s.programados_proximo or ""


def _render_descartados(s: SnapshotSesion, largo: bool) -> str:
    return s.descartados or ""


def _render_obs_transmision(s: SnapshotSesion, largo: bool) -> str:
    return s.obs_transmision or ""


def _render_obs_grabacion(s: SnapshotSesion, largo: bool) -> str:
    return s.obs_grabacion or ""


def _render_obs_escena(s: SnapshotSesion, largo: bool) -> str:
    return s.obs_escena or ""


def _render_musica(s: SnapshotSesion, largo: bool) -> str:
    return s.musica or ""


def _render_igualando(s: SnapshotSesion, largo: bool) -> str:
    return s.igualando or ""


_RENDERERS = {
    "estado": _render_estado,
    "titulo": _render_titulo,
    "canal": _render_canal,
    "espectadores": _render_espectadores,
    "tiempo_directo": _render_tiempo_directo,
    "desfase_directo": _render_desfase_directo,
    "mensajes_leidos": _render_mensajes_leidos,
    "aportes": _render_aportes,
    "en_cola": _render_en_cola,
    "voz": _render_voz,
    "lectura_silenciada": _render_lectura_silenciada,
    "overlay": _render_overlay,
    "programados": _render_programados,
    "descartados": _render_descartados,
    "obs_transmision": _render_obs_transmision,
    "obs_grabacion": _render_obs_grabacion,
    "obs_escena": _render_obs_escena,
    "musica": _render_musica,
    "igualando": _render_igualando,
}


def _render(nombre: str, s: SnapshotSesion, largo: bool) -> str:
    """Un componente a texto, o "" si no hay dato que mostrar."""
    dibujar = _RENDERERS.get(nombre)
    if dibujar is None:
        return ""
    return dibujar(s, largo)


def formatear_estado(snap: SnapshotSesion, toggles, modo: str = "corto") -> str:
    """Frase de estado a partir del snapshot y los componentes activos.

    modo="corto": una frase con «; » entre componentes y punto final.
    modo="largo": una línea por componente («Etiqueta: valor»).
    Función pura y determinista; los componentes sin dato se omiten.
    """
    partes = []
    supervisada = (snap.transmision_supervisada or "").strip()
    if supervisada:
        partes.append(f"Transmisión: {supervisada}" if modo == "largo"
                      else supervisada)
    for nombre in COMPONENTES:
        if nombre not in toggles:
            continue
        if supervisada and nombre == "obs_transmision":
            continue
        txt = _render(nombre, snap, largo=(modo == "largo"))
        if txt:
            partes.append(txt)
    if not partes:
        return ""
    if modo == "largo":
        return "\n".join(partes)
    return "; ".join(partes) + "."

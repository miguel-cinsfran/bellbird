"""Formateo del panel de información del vídeo (lógica pura, sin wx).

Toma el dict de metadatos que arma `main._metadatos_desde_ytdlp` (lo que trae
yt-dlp en la extracción `process=False`) y lo convierte en el texto, en orden,
que muestra el cuadro de solo lectura. Aislado aquí para poder probarlo sin GUI.
"""

from __future__ import annotations

from bellbird.core.idioma import N_, _


# Traductores: aviso del panel de información cuando no hay datos.
_SIN_INFO = N_("Sin información del vídeo.")


def _fmt_num(n) -> str:
    """Miles con punto, al estilo español: 30044 → «30.044». Vacío si no es número."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _fmt_fecha(yyyymmdd) -> str:
    """«20240131» → «31/01/2024». Vacío si no encaja el formato de yt-dlp."""
    s = str(yyyymmdd or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
    return ""


def _fmt_duracion(seg) -> str:
    """Segundos → «H:MM:SS» (o «M:SS» si dura menos de una hora). Vacío si <=0."""
    try:
        s = int(seg)
    except (TypeError, ValueError):
        return ""
    if s <= 0:
        return ""
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def formatear(meta: dict) -> str:
    """Texto del panel de información, en orden: título, canal, vistas (o
    espectadores si es directo), me gusta, comentarios, fecha, duración y
    descripción. Omite lo que no venga. Devuelve un aviso si no hay nada."""
    if not meta:
        return _(_SIN_INFO)

    lineas = []
    titulo = (meta.get("titulo") or "").strip()
    if titulo:
        lineas.append(titulo)
    canal = (meta.get("canal") or "").strip()
    if canal:
        # Traductores: línea del panel de información. {canal} es el nombre del canal.
        lineas.append(_("Canal: {canal}").format(canal=canal))

    en_vivo = bool(meta.get("en_vivo"))
    vistas = _fmt_num(meta.get("vistas"))
    if vistas:
        # Traductores: línea del panel de información de un directo. {vistas} es cuántas personas miran.
        # Traductores: línea del panel de información de un vídeo. {vistas} es cuántas vistas tiene.
        lineas.append((_("Espectadores: {vistas}") if en_vivo else _("Vistas: {vistas}")).format(vistas=vistas))
    me_gusta = _fmt_num(meta.get("me_gusta"))
    if me_gusta:
        # Traductores: línea del panel de información. {cuantos} es cuántos me gusta tiene.
        lineas.append(_("Me gusta: {cuantos}").format(cuantos=me_gusta))
    comentarios = _fmt_num(meta.get("comentarios"))
    if comentarios:
        # Traductores: línea del panel de información. {cuantos} es cuántos comentarios tiene.
        lineas.append(_("Comentarios: {cuantos}").format(cuantos=comentarios))

    fecha = _fmt_fecha(meta.get("fecha"))
    if fecha:
        # Traductores: línea del panel de información. {fecha} es la fecha de publicación.
        lineas.append(_("Publicado: {fecha}").format(fecha=fecha))
    # En un directo la «duración» no tiene sentido (crece en vivo): se omite.
    if not en_vivo:
        dur = _fmt_duracion(meta.get("duracion"))
        if dur:
            # Traductores: línea del panel de información. {duracion} es cuánto dura.
            lineas.append(_("Duración: {duracion}").format(duracion=dur))

    cabecera = "\n".join(lineas) if lineas else _(_SIN_INFO)
    desc = (meta.get("descripcion") or "").strip()
    if desc:
        return f"{cabecera}\n\nDescripción:\n{desc}"
    return cabecera

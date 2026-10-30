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

from bellbird.capture.componentes_estado import (ACTIVOS_DEFECTO, COMPONENTES, ETIQUETAS, etiqueta)
from bellbird.core.idioma import N_, _


# Códigos de tipo de conexión → etiqueta legible. Se traducen al usarlas.
_TIPO_TXT = {
    # Traductores: parte del estado F2 (tipo de conexión).
    "live_youtube": N_("Directo de YouTube"),
    # Traductores: parte del estado F2 (tipo de conexión).
    "live_tiktok": N_("Directo de TikTok"),
    # Traductores: parte del estado F2 (tipo de conexión).
    "vod": N_("Vídeo"),
    # Traductores: parte del estado F2 (tipo de conexión).
    "upcoming": N_("Directo programado"),
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


def _fmt_num(n) -> str:
    """Miles con punto al estilo español: 30044 → «30.044»."""
    try:    return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError): return str(n)


def _duracion(segundos: int) -> str:
    if segundos < 60:
        # Traductores: parte del estado F2 (duración del directo).
        return _("menos de un minuto")
    minutos = segundos // 60
    # El corte en 48 horas conserva legibles los maratones de hasta dos días.
    if minutos >= 48 * 60:
        dias = minutos // (24 * 60)
        # Hoy es inalcanzable con el corte fijado en 48 horas.
        if dias == 1:
            # Traductores: parte del estado F2 (duración). {dias} es el nº de días.
            return _("{dias} día").format(dias=dias)
        # Traductores: parte del estado F2 (duración). {dias} es el nº de días.
        return _("{dias} días").format(dias=dias)
    horas, minutos = divmod(minutos, 60)
    if horas:
        # Traductores: parte del estado F2 (duración). {horas} son horas y {minutos} minutos.
        return _("{horas} h {minutos} min").format(horas=horas, minutos=minutos)
    # Traductores: parte del estado F2 (duración). {minutos} son los minutos.
    return _("{minutos} min").format(minutos=minutos)


def _render_estado(s: SnapshotSesion, largo: bool) -> str:
    if not s.conectado:
        # Traductores: parte del estado F2 (conexión).
        return _("Desconectado")
    texto = _TIPO_TXT.get(s.tipo)
    if texto is None:
        # Traductores: parte del estado F2 (conexión).
        return _("Conectado")
    return _(texto)


def _render_titulo(s: SnapshotSesion, largo: bool) -> str:
    t = (s.titulo or "").strip()
    if not t:
        return ""
    if largo:
        # Traductores: parte del estado F2 (título). {titulo} es el título.
        return _("Título: {titulo}").format(titulo=t)
    return t


def _render_canal(s: SnapshotSesion, largo: bool) -> str:
    c = (s.canal or "").strip()
    if not c:
        return ""
    # Traductores: parte del estado F2 (canal). {canal} es el canal o autor.
    return _("Canal: {canal}").format(canal=c)


def _espectadores_tiktok(n: str, total: str, largo: bool, singular: bool) -> str:
    if largo and singular:
        # Traductores: parte del estado F2 (espectadores TikTok). {n} son los de ahora y {total} el total.
        return _("Espectador: {n} ahora, {total} en total").format(n=n, total=total)
    if largo:
        # Traductores: parte del estado F2 (espectadores TikTok). {n} son los de ahora y {total} el total.
        return _("Espectadores: {n} ahora, {total} en total").format(n=n, total=total)
    if singular:
        # Traductores: parte del estado F2 (espectadores TikTok). {n} son los de ahora y {total} el total.
        return _("{n} espectador ahora, {total} en total").format(n=n, total=total)
    # Traductores: parte del estado F2 (espectadores TikTok). {n} son los de ahora y {total} el total.
    return _("{n} espectadores ahora, {total} en total").format(n=n, total=total)


def _espectadores_resto(n: str, en_directo: bool, largo: bool, singular: bool) -> str:
    if en_directo and largo and singular:
        # Traductores: parte del estado F2 (espectadores). {n} es el nº actual.
        return _("Espectador: {n}").format(n=n)
    if en_directo and largo:
        # Traductores: parte del estado F2 (espectadores). {n} es el nº actual.
        return _("Espectadores: {n}").format(n=n)
    if en_directo and singular:
        # Traductores: parte del estado F2 (espectadores). {n} es el nº actual.
        return _("{n} espectador").format(n=n)
    if en_directo:
        # Traductores: parte del estado F2 (espectadores). {n} es el nº actual.
        return _("{n} espectadores").format(n=n)
    if largo and singular:
        # Traductores: parte del estado F2 (vistas). {n} es el nº total.
        return _("Vista: {n}").format(n=n)
    if largo:
        # Traductores: parte del estado F2 (vistas). {n} es el nº total.
        return _("Vistas: {n}").format(n=n)
    if singular:
        # Traductores: parte del estado F2 (vistas). {n} es el nº total.
        return _("{n} vista").format(n=n)
    # Traductores: parte del estado F2 (vistas). {n} es el nº total.
    return _("{n} vistas").format(n=n)


def _render_espectadores(s: SnapshotSesion, largo: bool) -> str:
    if s.espectadores is None:
        return ""
    n = _fmt_num(s.espectadores)
    # En un directo es el nº de espectadores AHORA; en un vídeo, las vistas
    # totales (números distintos, no confundir).
    singular = s.espectadores == 1
    if s.tipo == "live_tiktok" and s.espectadores_total is not None:
        return _espectadores_tiktok(n, _fmt_num(s.espectadores_total), largo, singular)
    en_directo = s.tipo in ("live_youtube", "live_tiktok")
    return _espectadores_resto(n, en_directo, largo, singular)


def _render_tiempo_directo(s: SnapshotSesion, largo: bool) -> str:
    if s.segundos_directo is None or s.segundos_directo < 0:
        return ""
    texto = _duracion(s.segundos_directo)
    if largo:
        # Traductores: parte del estado F2 (tiempo). {texto} es la duración.
        return _("Tiempo del directo: {texto}").format(texto=texto)
    # Traductores: parte del estado F2 (tiempo). {texto} es la duración.
    return _("Lleva {texto}").format(texto=texto)


def _render_desfase_directo(s: SnapshotSesion, largo: bool) -> str:
    texto = (s.desfase_directo or "").strip()
    if not texto:
        return ""
    if largo:
        # Traductores: parte del estado F2 del desfase. {texto} es el desfase.
        base = _("Reproductor: {texto}").format(texto=texto)
    else:
        base = texto
    atajo = (s.atajo_directo or "").strip()
    if atajo:
        # Traductores: parte del estado F2 del desfase. {atajo} es el atajo de teclado.
        vuelta = _("Pulsa {atajo} para volver al directo").format(atajo=atajo)
    else:
        # Traductores: parte del estado F2 del desfase cuando no hay atajo.
        vuelta = _("Para volver: menú Reproductor, Ir al directo")
    # En largo la línea es una frase completa y lleva su punto; en corto
    # lo pone el punto final de la frase armada.
    if largo:
        return f"{base}. {vuelta}."
    return f"{base}. {vuelta}"


def _render_mensajes_leidos(s: SnapshotSesion, largo: bool) -> str:
    n = _fmt_num(s.mensajes_leidos)
    if largo:
        # Traductores: parte del estado F2 (leídos). {n} es el nº de mensajes.
        return _("Mensajes leídos: {n}").format(n=n)
    # Traductores: parte del estado F2 (leídos). {n} es el nº de mensajes.
    return _("{n} leídos").format(n=n)


def _aportes_tiktok(n: int, total: str, largo: bool) -> str:
    if largo and total:
        # Traductores: parte del estado F2 (aportes TikTok). {n} es el nº y {total} el importe.
        return _("Aportes: {n} regalos ({total})").format(n=n, total=total)
    if largo:
        # Traductores: parte del estado F2 (aportes TikTok). {n} es el nº de regalos.
        return _("Aportes: {n} regalos").format(n=n)
    if total:
        # Traductores: parte del estado F2 (aportes TikTok). {n} es el nº y {total} el importe.
        return _("{n} regalos ({total})").format(n=n, total=total)
    # Traductores: parte del estado F2 (aportes TikTok). {n} es el nº de regalos.
    return _("{n} regalos").format(n=n)


def _aportes_youtube(n: int, total: str, largo: bool) -> str:
    if largo and total:
        # Traductores: parte del estado F2 (aportes YouTube). {n} es el nº y {total} el importe.
        return _("Aportes: {n} Super Chats ({total})").format(n=n, total=total)
    if largo:
        # Traductores: parte del estado F2 (aportes YouTube). {n} es el nº de Super Chats.
        return _("Aportes: {n} Super Chats").format(n=n)
    if total:
        # Traductores: parte del estado F2 (aportes YouTube). {n} es el nº y {total} el importe.
        return _("{n} Super Chats ({total})").format(n=n, total=total)
    # Traductores: parte del estado F2 (aportes YouTube). {n} es el nº de Super Chats.
    return _("{n} Super Chats").format(n=n)


def _render_aportes(s: SnapshotSesion, largo: bool) -> str:
    if s.aportes <= 0:
        return ""
    # «Super Chats» en YouTube, «regalos» en TikTok, cada uno con su frase.
    total = (s.total_aportes or "").strip()
    if s.tipo == "live_tiktok":
        return _aportes_tiktok(s.aportes, total, largo)
    return _aportes_youtube(s.aportes, total, largo)


def _render_en_cola(s: SnapshotSesion, largo: bool) -> str:
    n = _fmt_num(s.en_cola)
    if largo:
        # Traductores: parte del estado F2 (cola). {n} es el nº en cola.
        return _("En cola: {n}").format(n=n)
    # Traductores: parte del estado F2 (cola). {n} es el nº en cola.
    return _("{n} en cola").format(n=n)


def _render_voz(s: SnapshotSesion, largo: bool) -> str:
    # Traductores: componente del estado F2. {velocidad} es la velocidad y {volumen} el volumen.
    return (_("Voz: velocidad {velocidad}, volumen {volumen}%").format(
        velocidad=s.voz_velocidad, volumen=s.voz_volumen))


def _render_lectura_silenciada(s: SnapshotSesion, largo: bool) -> str:
    if not s.lectura_silenciada:
        return ""
    # Traductores: parte del estado F2 (lectura silenciada).
    return _("Lectura silenciada")


def _render_overlay(s: SnapshotSesion, largo: bool) -> str:
    if s.overlay_puerto is None:
        return ""
    if s.overlay_clientes:
        # Traductores: componente del estado F2. {puerto} es el puerto del panel.
        return _("Panel de chat activo en el puerto {puerto}, mostrándose").format(
            puerto=s.overlay_puerto)
    # Traductores: componente del estado F2. {puerto} es el puerto del panel.
    return (_("Panel de chat activo en el puerto {puerto}, pero nadie "
              "lo está mostrando").format(puerto=s.overlay_puerto))


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


def _render_supervisada(supervisada: str, modo: str) -> str:
    if modo == "largo":
        # Traductores: parte del estado F2 (transmisión). {texto} es el estado.
        return _("Transmisión: {texto}").format(texto=supervisada)
    return supervisada


def formatear_estado(snap: SnapshotSesion, toggles, modo: str = "corto") -> str:
    """Frase de estado a partir del snapshot y los componentes activos.

    modo="corto": una frase con «; » entre componentes y punto final.
    modo="largo": una línea por componente («Etiqueta: valor»).
    Función pura y determinista; los componentes sin dato se omiten.
    """
    partes = []
    supervisada = (snap.transmision_supervisada or "").strip()
    if supervisada:
        partes.append(_render_supervisada(supervisada, modo))
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

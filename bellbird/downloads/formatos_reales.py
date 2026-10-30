"""Resume los formatos de un vídeo en opciones legibles con su tamaño real.

Una sola responsabilidad: cómo se resumen los formatos que yt-dlp devuelve
con `--dump-json`. Puro, sin wx: lo usan la elección de formato y la cola
de descargas.
"""

from __future__ import annotations

from dataclasses import dataclass

from bellbird.core.idioma import _


@dataclass(frozen=True)
class OpcionFormato:
    """Una opción legible: etiqueta, selector exacto y tamaño en bytes."""

    etiqueta: str
    selector: str
    contenedor: str
    tamano: int | None


_MEGA = 1048576

_CONTENEDOR_MOSTRADO = {"mp4": "MP4", "webm": "WebM", "m4a": "M4A",
                        "opus": "Opus"}


def _tamano_de(formato) -> int | None:
    """Bytes del formato, con el aproximado si falta el exacto."""
    for clave in ("filesize", "filesize_approx"):
        valor = formato.get(clave)
        if isinstance(valor, (int, float)):
            return int(valor)
    return None


def _es_solo_audio(formato) -> bool:
    return (formato.get("vcodec") or "none") == "none" \
        and (formato.get("acodec") or "none") != "none"


def _es_video(formato) -> bool:
    return (formato.get("vcodec") or "none") != "none" \
        and isinstance(formato.get("height"), int)


def _descartado(formato) -> bool:
    """Fuera: sin identificador, trozos de emisión o sonido comprimido."""
    fid = formato.get("format_id")
    if not fid:
        return True
    protocolo = formato.get("protocol") or ""
    if protocolo.startswith("m3u8") or protocolo == "mhtml":
        return True
    if _es_solo_audio(formato):
        texto = f"{fid} {formato.get('format_note') or ''}".lower()
        if "drc" in texto:
            return True
    return False


def _cuadros(formato):
    """Cuadros por segundo, que cuentan solo si son más de 30."""
    fps = formato.get("fps")
    if isinstance(fps, (int, float)) and fps > 30:
        return fps
    return 0


def _preferencia_video(formato) -> int:
    """H.264 antes que VP9, VP9 antes que AV1 y AV1 antes que el resto."""
    vcodec = (formato.get("vcodec") or "").lower()
    if vcodec.startswith(("avc1", "h264")):
        return 0
    if vcodec.startswith(("vp9", "vp09")):
        return 1
    if vcodec.startswith(("av01", "av1")):
        return 2
    return 3


def _tbr(formato) -> float:
    tbr = formato.get("tbr")
    return tbr if isinstance(tbr, (int, float)) else 0


def _abr(audio) -> float:
    abr = audio.get("abr")
    return abr if isinstance(abr, (int, float)) else 0


def _es_m4a(audio) -> bool:
    return audio.get("ext") == "m4a" \
        and (audio.get("acodec") or "").startswith("mp4a")


def _es_opus(audio) -> bool:
    return (audio.get("acodec") or "").startswith("opus")


def _mejor_audio(audios, ext_video):
    """El audio que se une al vídeo: M4A para MP4, Opus para WebM."""
    if ext_video == "mp4":
        preferidos = [a for a in audios if _es_m4a(a)]
    elif ext_video == "webm":
        preferidos = [a for a in audios if _es_opus(a)]
    else:
        preferidos = []
    candidatos = preferidos or audios
    if not candidatos:
        return None
    return max(candidatos, key=_abr)


def _texto_tamano(tamano) -> str:
    if tamano is None:
        # Traductores: cuando yt-dlp no informa el tamaño de la opción.
        return _("tamaño desconocido")
    megas = round(tamano / _MEGA)
    if megas < 1:
        # Traductores: tamaño menor a un megabyte.
        return _("menos de 1 MB")
    # Traductores: {n} son megabytes enteros, sin decimales.
    return _("{n} MB").format(n=megas)


def _etiqueta_video(alto, cuadros, contenedor, tamano) -> str:
    mostrado = _CONTENEDOR_MOSTRADO.get(contenedor, contenedor)
    texto = _texto_tamano(tamano)
    if cuadros:
        enteros = int(cuadros) if float(cuadros).is_integer() else cuadros
        # Traductores: {alto} es la resolución vertical, {cuadros} los
        # cuadros por segundo, {contenedor} MP4 o WebM y {tamano} el tamaño.
        return _("{alto}p {cuadros} fps, {contenedor}, {tamano}").format(
            alto=alto, cuadros=enteros, contenedor=mostrado, tamano=texto)
    # Traductores: {alto} es la resolución vertical, {contenedor} MP4 o
    # WebM y {tamano} el tamaño.
    return _("{alto}p, {contenedor}, {tamano}").format(
        alto=alto, contenedor=mostrado, tamano=texto)


def _etiqueta_audio(audio, contenedor) -> str:
    # Traductores: {contenedor} es M4A u Opus, {kbps} los kilobits por
    # segundo y {tamano} el tamaño.
    return _("Solo audio, {contenedor}, {kbps} kbps, {tamano}").format(
        contenedor=_CONTENEDOR_MOSTRADO.get(contenedor, contenedor),
        kbps=int(round(_abr(audio))), tamano=_texto_tamano(_tamano_de(audio)))


def _opcion_solo_audio(audios):
    candidatos = [a for a in audios if _es_m4a(a) or _es_opus(a)]
    if not candidatos:
        return None
    mejor = max(candidatos, key=_abr)
    contenedor = "m4a" if _es_m4a(mejor) else "opus"
    return OpcionFormato(
        etiqueta=_etiqueta_audio(mejor, contenedor),
        selector=str(mejor["format_id"]),
        contenedor=contenedor,
        tamano=_tamano_de(mejor))


def _opcion_de_grupo(candidatos, audios):
    """El elegido de un par (alto, cuadros) con su selector y su tamaño.

    None si el vídeo solo se puede unir y no hay audio para unirlo.
    """
    solos = [f for f in candidatos
             if (f.get("acodec") or "none") == "none"]
    elegido = min(solos or candidatos,
                  key=lambda f: (_preferencia_video(f), -_tbr(f)))
    if (elegido.get("acodec") or "none") != "none":
        return elegido, str(elegido["format_id"]), _tamano_de(elegido)
    audio = _mejor_audio(audios, elegido.get("ext"))
    if audio is None:
        return None
    selector = f"{elegido['format_id']}+{audio['format_id']}"
    tamano_video = _tamano_de(elegido)
    tamano_audio = _tamano_de(audio)
    if tamano_video is None or tamano_audio is None:
        return elegido, selector, None
    return elegido, selector, tamano_video + tamano_audio


def opciones(info: dict) -> list:
    """Una opción por resolución con su tamaño real, más una de solo audio.

    Orden de mayor a menor alto y, con el mismo alto, de más a menos
    cuadros, con el solo audio al final. Sin formatos útiles, lista vacía.
    """
    formatos = info.get("formats") if isinstance(info, dict) else None
    if not formatos:
        return []
    audios = []
    grupos = {}
    for formato in formatos:
        if _descartado(formato):
            continue
        if _es_video(formato):
            grupos.setdefault((formato["height"], _cuadros(formato)),
                              []).append(formato)
        elif _es_solo_audio(formato):
            audios.append(formato)
    elegidos = []
    for (alto, cuadros), candidatos in grupos.items():
        resuelto = _opcion_de_grupo(candidatos, audios)
        if resuelto is None:
            continue
        elegido, selector, tamano = resuelto
        elegidos.append((alto, cuadros, elegido, selector, tamano))
    elegidos.sort(key=lambda item: (item[0], item[1]), reverse=True)
    resultado = [OpcionFormato(
        etiqueta=_etiqueta_video(alto, cuadros, elegido.get("ext") or "",
                                 tamano),
        selector=selector, contenedor=elegido.get("ext") or "",
        tamano=tamano) for alto, cuadros, elegido, selector, tamano
        in elegidos]
    solo_audio = _opcion_solo_audio(audios)
    if solo_audio is not None:
        resultado.append(solo_audio)
    return resultado


def transitorias(opcion: OpcionFormato) -> dict:
    """Lo que la cola guarda para descargar exactamente esta opción."""
    return {"formato": "exacto", "selector": opcion.selector,
            "contenedor": opcion.contenedor}

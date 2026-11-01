"""Elección del formato de yt-dlp para vídeos y directos de YouTube.

Módulo puro: opera sobre la información que ya devolvió yt-dlp, sin red, sin
wx y sin libVLC.
"""

from __future__ import annotations

from bellbird.player.formatos import (
    mejor_audio as _mejor_audio,
    mejor_audio_estereo,
    segundos_hasta_disponible,
)


def _alturas_disponibles(info: dict) -> list[int]:
    alturas = set()
    for f in info.get("formats", []) or []:
        if f.get("vcodec") not in (None, "none") and f.get("height"):
            alturas.add(int(f["height"]))
    return sorted(alturas, reverse=True)


def _altura_auto_vod(alturas, tope: int = 1080):
    """Altura efectiva del VOD en calidad automática: la mayor disponible
    que no supere el tope y, si todas lo superan, la menor disponible.
    None si no hay ninguna altura."""
    lista = list(alturas or [])
    if not lista:
        return None
    menores = [a for a in lista if a <= tope]
    if menores:
        return max(menores)
    return min(lista)


def _con_video(f: dict) -> bool:
    """Dice si el formato trae imagen."""
    return f.get("vcodec") not in (None, "none")


def _con_audio(f: dict) -> bool:
    """Dice si el formato trae sonido."""
    return f.get("acodec") not in (None, "none")


def _usable(f: dict) -> bool:
    """Dice si el formato tiene dirección y altura para elegir."""
    return bool(f.get("url") and f.get("height"))


def _preferencia_solo(f: dict):
    """Ordena vídeos solos de la misma altura: primero https, después mayor tbr."""
    # El relevo de VOD remuxa mejor desde https que desde m3u8.
    return (not (f.get("protocol") or "").startswith("m3u8"),
            f.get("tbr") or 0)


def _video_para_altura(info: dict, altura: int) -> tuple[str, bool]:
    """(url, progresivo). Busca el mejor flujo para esa altura; progresivo=True
    si ya trae audio (no hace falta slave)."""
    fmts = info.get("formats", []) or []
    prog = [f for f in fmts if _con_video(f) and _con_audio(f) and _usable(f)]
    cand = [f for f in prog if int(f["height"]) <= altura]
    if cand:
        f = max(cand, key=lambda x: int(x["height"]))
        # El progresivo cercano por debajo no alcanza: solo gana si es exacto.
        if int(f["height"]) == altura:
            return f["url"], True
    solo = [f for f in fmts if _con_video(f) and not _con_audio(f)
            and _usable(f) and int(f["height"]) == altura]
    if solo:
        return max(solo, key=_preferencia_solo)["url"], False
    if prog:
        return max(prog, key=lambda x: int(x["height"]))["url"], True
    solo = [f for f in fmts if _con_video(f) and not _con_audio(f)
            and _usable(f)]
    if solo:
        cand = [f for f in solo if int(f["height"]) <= altura]
        if cand:
            altura_elegida = max(int(f["height"]) for f in cand)
            cand = [f for f in cand if int(f["height"]) == altura_elegida]
        else:
            altura_elegida = min(int(f["height"]) for f in solo)
            cand = [f for f in solo if int(f["height"]) == altura_elegida]
        return max(cand, key=_preferencia_solo)["url"], False
    return "", False


def _preferir_hls(formatos: list) -> list:
    """Para directos, yt-dlp suele traer en la misma lista variantes HLS
    (.m3u8) y variantes «DASH en crudo» (protocol=https/http_dash_segments):
    una URL que exige el manejo de secuencias propio de yt-dlp y que ni VLC
    ni ffmpeg saben leer bien solos («Invalid data found», comprobado). Si
    hay HLS con vídeo, se usa esa familia; si no, se deja la lista igual:
    quedarse con una familia HLS de solo audio dejaría el directo sin imagen
    (y el audio se resuelve aparte, ver fuentes_para_directo)."""
    hls = [f for f in formatos if "m3u8" in (f.get("protocol") or "")]
    if any(f.get("vcodec") not in (None, "none") for f in hls):
        return hls
    return list(formatos)


def fuentes_para_directo(info: dict) -> tuple[str, str]:
    """(url de vídeo, url de audio esclavo). Audio vacío si no hace falta."""
    url = info.get("url") or ""
    if url:
        return url, ""

    info_hls = {**info, "formats": _preferir_hls(info.get("formats") or [])}
    url, progresivo = _video_para_altura(info_hls, 10_000)
    if url:
        # Si la familia HLS trae vídeo pero ningún audio suelto, el directo
        # quedaba mudo: se cae al mejor audio de la lista completa.
        return url, "" if progresivo else (_mejor_audio(info_hls)
                                          or _mejor_audio(info))

    video = audio = ""
    for formato in info.get("requested_formats", []) or []:
        url = formato.get("url") or ""
        if not url:
            continue
        tiene_video = formato.get("vcodec") not in (None, "none")
        tiene_audio = formato.get("acodec") not in (None, "none")
        if tiene_video:
            video = url
            if tiene_audio:
                return video, ""
        elif tiene_audio:
            audio = url
    if video:
        return video, audio
    return "", ""


def fuentes_de_vod(info: dict, altura,
                   solo_audio: bool = False) -> tuple[str, str]:
    """(url de vídeo, url de audio esclavo) de un vídeo grabado.

    Con `altura` None se usa la altura automática; si no hay ninguna altura,
    se cae a `fuentes_para_directo`, como el resto del camino. Con
    `solo_audio`, y si hay una pista de audio directa, se devuelve esa sola
    dirección: sin vídeo, sin esclavo y sin relevo. Si no hay ninguna que no
    sea HLS, se sigue con las reglas normales.
    """
    if solo_audio:
        audio = mejor_audio_estereo(info)
        if audio:
            return audio, ""
    if altura is None:
        altura = _altura_auto_vod(_alturas_disponibles(info))
        if altura is None:
            return fuentes_para_directo(info)
    url, progresivo = _video_para_altura(info, altura)
    return url, "" if progresivo else _mejor_audio(info, evitar_hls=True)


def espera_para_abrir(info: dict, altura, ahora: float,
                      solo_audio: bool = False) -> float:
    """Segundos a esperar antes de abrir las direcciones que se van a usar.

    YouTube responde 403 a la dirección de un formato hasta su
    `available_at`; esperar esa hora antes de dársela a ffmpeg evita el
    relevo fallido. Se eligen las direcciones con las mismas reglas que
    `_reproducir_calidad`.
    """
    if info.get("is_live"):
        url, slave = fuentes_para_directo(info)
    else:
        url, slave = fuentes_de_vod(info, altura, solo_audio)
    return segundos_hasta_disponible(info, (url, slave), ahora)


def _es_hls(info: dict, url: str) -> bool:
    """Dice si esa URL de vídeo es una lista HLS (protocol m3u8).

    Se mira el formato de info["formats"] cuya url coincide; si la URL es
    la de nivel superior (yt-dlp ya eligió un formato mixto), se mira
    info["protocol"]. Cualquier otra URL no es HLS.
    """
    if not url or not isinstance(info, dict):
        return False
    for formato in info.get("formats", []) or []:
        if formato.get("url") == url:
            return (formato.get("protocol") or "").startswith("m3u8")
    if (info.get("url") or "") == url:
        return (info.get("protocol") or "").startswith("m3u8")
    return False

"""Selección de formatos de yt-dlp, compartida por el vídeo y la música.

Módulo puro: opera sobre la información que ya devolvió yt-dlp, sin red, sin
wx y sin libVLC. Nació de mover `_mejor_audio` fuera de `reproductor.py` para
que la música por enlace elija el audio sin depender de la interfaz.
"""

from __future__ import annotations


def mejor_audio(info: dict, evitar_hls: bool = False) -> str:
    # Preferimos la pista ORIGINAL antes que la de mayor bitrate: cada vez más
    # vídeos traen doblajes y yt-dlp marca la original/«default» con
    # language_preference alto (10). Sin esto, entre dos bitrates parecidos
    # podríamos reproducir el doblaje en vez del audio original. A igualdad de
    # idioma, gana el bitrate (como antes), así que un vídeo de una sola pista
    # se comporta igual que siempre.
    # Con evitar_hls (solo el VOD por relevo) se ignoran las pistas HLS: el
    # ffmpeg del relevo no puede escribir el encabezado Matroska a un destino
    # TCP con audio HLS AAC, mientras que con AAC u Opus normales sí funciona.
    # Si solo hay HLS, se elige entre ellas como siempre.
    auds = [f for f in info.get("formats", []) or []
            if f.get("acodec") != "none"
            and f.get("vcodec") in (None, "none") and f.get("url")]
    if not auds:
        return ""
    if evitar_hls:
        sin_hls = [f for f in auds
                   if not (f.get("protocol") or "").startswith("m3u8")]
        if sin_hls:
            auds = sin_hls
    # Con evitar_hls (relevo de VOD) el m4a/AAC abre más rápido en ffmpeg
    # que el webm/Opus (medido: 1,6-2,1 s contra 4,8-6,6 s), así que a
    # igualdad de idioma gana el m4a. El idioma siempre va primero: un
    # webm original le gana a un m4a doblado.
    if evitar_hls:
        def _clave(x):
            es_m4a = 1 if (x.get("ext") == "m4a"
                           or (x.get("acodec") or "").startswith("mp4a")) else 0
            return ((x.get("language_preference") or 0), es_m4a,
                    (x.get("abr") or 0))
    else:
        def _clave(x):
            return ((x.get("language_preference") or 0), (x.get("abr") or 0))
    mejor = max(auds, key=_clave)
    return mejor["url"]

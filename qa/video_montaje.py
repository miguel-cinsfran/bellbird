"""Cómo se arma el video de la verificación de Google, sin correr nada.

Arma el SRT de los subtítulos y las listas de argumentos de ffmpeg para
grabar el escritorio, la portada, quemar los subtítulos, unir portada y
grabación y sacar un cuadro. Todo es puro: las pruebas lo comprueban sin
ffmpeg ni ventanas.
"""

from __future__ import annotations

PORTADA_SEGUNDOS = 3.0
PORTADA = (
    "Guyrapu: how the app uses the youtube.force-ssl scope",
    "A Windows desktop app for blind streamers",
)
SUBTITULOS = {
    1: "The app starts signed out. We sign in from Preferences.",
    2: "Google's sign-in screen: we pick the account and pass the "
       "unverified app warning.",
    3: "The consent screen. The OAuth client ID is in the address bar. "
       "We grant the youtube.force-ssl scope.",
    4: "We create an unlisted live stream on our own channel, with its title.",
    5: "OBS sends the video in the background. The broadcast is live.",
    6: "We send a message to the live chat from the app.",
    7: "Chat moderation: timeout or hide a user, always after a "
       "confirmation. Here we cancel.",
    8: "We end the broadcast from the app.",
    9: "We post a comment on the video of the broadcast that just ended.",
    10: "That is every use of the scope. All data stays on the user's "
        "computer.",
    11: "The app is signed in.",
}
ANCHO = 1280
ALTO = 720
CUADROS = 30
FUENTE = r"C\:/Windows/Fonts/arial.ttf"


def _marca(segundos: float) -> str:
    """Segundo con el formato HH:MM:SS,mmm que pide el SRT."""
    total = max(0, int(round(float(segundos) * 1000)))
    horas, resto = divmod(total, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segundos_enteros, milesimas = divmod(resto, 1000)
    return (f"{horas:02d}:{minutos:02d}:{segundos_enteros:02d},"
            f"{milesimas:03d}")


def _validar(inicio: float, fin: float) -> None:
    if float(fin) < float(inicio):
        raise ValueError(
            f"el paso termina antes de empezar: {inicio} -> {fin}")


def armar_srt(pasos, desplazamiento: float = 0.0) -> str:
    """Texto SRT numerado desde 1 desde una lista de pasos.

    Cada paso trae `inicio`, `fin` y `texto` en segundos. `desplazamiento`
    suma el mismo margen a todos, para que la portada quede antes.
    """
    bloques = []
    for numero, paso in enumerate(pasos, start=1):
        inicio = float(paso["inicio"])
        fin = float(paso["fin"])
        _validar(inicio, fin)
        bloques.append(
            f"{numero}\n"
            f"{_marca(inicio + desplazamiento)} --> "
            f"{_marca(fin + desplazamiento)}\n"
            f"{paso['texto']}\n"
        )
    return "\n".join(bloques)


def duracion_total(pasos, portada: float = PORTADA_SEGUNDOS) -> float:
    """Segundos que durará el video: la portada más cada paso."""
    total = float(portada)
    for paso in pasos:
        inicio = float(paso["inicio"])
        fin = float(paso["fin"])
        _validar(inicio, fin)
        total += fin - inicio
    return total


def args_grabacion(salida: str) -> list[str]:
    """ffmpeg grabando el escritorio con gdigrab, 30 cuadros y H.264."""
    return [
        "ffmpeg", "-y", "-f", "gdigrab", "-framerate", str(CUADROS),
        "-i", "desktop",
        "-vf", f"scale={ANCHO}:{ALTO}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        salida,
    ]


def _escapar(texto: str) -> str:
    """Escapa lo que el filtro drawtext interpreta como separador."""
    for viejo, nuevo in (("\\", "\\\\"), (":", "\\:"), ("'", "\\'"),
                         ("%", "\\%"), (",", "\\,"), ("[", "\\["),
                         ("]", "\\]")):
        texto = texto.replace(viejo, nuevo)
    return texto


def args_portada(salida: str, lineas, segundos: float = PORTADA_SEGUNDOS
                 ) -> list[str]:
    """Portada de fondo liso con las líneas de texto dadas."""
    alto_linea = 52
    centro = f"y=(h-{alto_linea * len(lineas)})/2"
    dibujos = []
    for indice, linea in enumerate(lineas):
        posicion = f"y=(h-{alto_linea * len(lineas)})/2+{indice * alto_linea}"
        dibujos.append(
            f"drawtext=fontfile='{FUENTE}':text='{_escapar(linea)}':"
            f"fontcolor=white:fontsize=40:x=(w-text_w)/2:{posicion}")
    filtro = ",".join(dibujos) or f"drawtext=fontfile='{FUENTE}':" \
        f"text='Guyrapu':fontcolor=white:fontsize=40:x=(w-text_w)/2:{centro}"
    return [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"color=c=0x0B1F33:s={ANCHO}x{ALTO}:r={CUADROS}:d={segundos}",
        "-t", str(segundos),
        "-vf", filtro,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        salida,
    ]


def args_quemar(entrada: str, ruta_srt: str, salida: str) -> list[str]:
    """Quema los subtítulos del SRT sobre el video ya unido."""
    return [
        "ffmpeg", "-y", "-i", entrada,
        "-vf", f"subtitles={ruta_srt}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "copy", salida,
    ]


def args_unir(portada: str, grabacion: str, salida: str) -> list[str]:
    """Une la portada y la grabación con el filtro concat."""
    filtro = (
        f"[0:v]scale={ANCHO}:{ALTO},setsar=1,fps={CUADROS}[v0];"
        f"[1:v]scale={ANCHO}:{ALTO},setsar=1,fps={CUADROS}[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[out]"
    )
    return [
        "ffmpeg", "-y", "-i", portada, "-i", grabacion,
        "-filter_complex", filtro, "-map", "[out]",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        salida,
    ]


def args_cuadro(video: str, segundo: float, salida: str) -> list[str]:
    """Saca un PNG del video en el segundo dado."""
    return [
        "ffmpeg", "-y", "-ss", str(segundo), "-i", video,
        "-frames:v", "1", salida,
    ]


def args_captura_pantalla(salida: str) -> list[str]:
    """Captura el escritorio entero en un PNG, para diagnosticar un fallo."""
    return [
        "ffmpeg", "-y", "-f", "gdigrab", "-i", "desktop",
        "-frames:v", "1", salida,
    ]

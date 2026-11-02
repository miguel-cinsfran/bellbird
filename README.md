# Bellbird

Aplicación de escritorio para Windows que lee en voz alta el chat de los
directos de YouTube y TikTok. Está pensada para personas ciegas o con baja
visión que transmiten: todo se maneja con el teclado y se prueba con el
lector de pantalla NVDA.

Hasta la versión 2.5 se llamaba `YTChat TTS`.

[Descargar la última versión](https://github.com/miguel-cinsfran/bellbird/releases/latest)
· [Manual de uso](docs/es/MANUAL.md) · [Novedades](docs/es/CHANGELOG.md)

## Qué hace

- Lee en voz alta el chat de los directos de YouTube y TikTok, y lo modera.
  También permite escribir en él y publica comentarios en vídeos.
- Inicia sesión con una cuenta de Google para moderar, comentar y crear el
  directo de YouTube.
- Reproduce el vídeo del directo dentro de la aplicación.
- Pone música de una carpeta, de listas propias o de YouTube, con el
  volumen de las canciones igualado.
- Inicia y finaliza el directo con OBS Studio, controla la grabación y
  organiza la escena.
- Describe el encuadre de la cámara de OBS y avisa cuando el rostro sale
  del encuadre.
- Muestra el chat a los espectadores en un panel para OBS.
- Manda mensajes automáticos al chat cada cierto tiempo.
- Resume el estado del directo por voz a pedido.
- Pregunta a un modelo de IA qué se ve en la escena al aire y lee la
  respuesta.
- Descarga vídeo y audio, y guarda el historial de lo descargado y de los
  directos vistos.
- Busca e instala las actualizaciones desde la aplicación, con vuelta a la
  versión anterior si falla.

El manual explica cada función y tiene las tablas de atajos.

## Con qué está hecha

Python 3.14 y wxPython para la interfaz, que usa los controles nativos de
Windows para que los lectores de pantalla los lean bien. Además:

- pytchat y TikTokLive para leer los chats.
- La API de datos de YouTube v3 para comentar y moderar.
- Prism (`prismatoid`) para hablar con NVDA, con SAPI 5 y con OneCore.
- libVLC (`python-vlc`) para el reproductor y la música.
- yt-dlp y ffmpeg para los enlaces, las descargas y medir el volumen de
  las canciones.
- El WebSocket de OBS para la transmisión.
- PyInstaller para el paquete que se publica.

## Desde el código

Hace falta Windows 10 u 11 y [uv](https://docs.astral.sh/uv/).

    instalar.bat      prepara el entorno con Python 3.14 y las dependencias
    ejecutar.bat      abre la aplicación
    construir.bat     arma el ZIP que se publica

El login de Google necesita un cliente OAuth propio: los pasos están en
[docs/CONFIGURACION_API.md](docs/CONFIGURACION_API.md).

## Pruebas

    python -m unittest discover -s tests
    python scripts/smoke_test.py

La suite cubre la lógica y la interfaz. El smoke abre la ventana y
comprueba que cada control tenga nombre accesible. Las dos abren
ventanas, así que conviene correrlas en un escritorio aparte.

`qa/conducir.py` es un banco que maneja la aplicación de verdad con el
teclado, como lo haría una persona con NVDA, y comprueba lo que se
anuncia. Su uso está en [qa/README.md](qa/README.md).

## Estructura

    main.py           punto de entrada
    bellbird/ui         ventanas y diálogos
    bellbird/capture    lectura del chat de YouTube y TikTok
    bellbird/youtube    API de YouTube y sesión de Google
    bellbird/voice      voces y sonidos
    bellbird/player     reproductor de vídeo
    bellbird/music      biblioteca, listas y reproducción de música
    bellbird/obs        transmisión con OBS
    bellbird/downloads  descargas con yt-dlp
    bellbird/core       configuración, rutas y utilidades
    tests/            pruebas
    qa/               banco de pruebas de punta a punta

## Licencia

GPL-3.0 desde la 2.5.1. Ver [LICENSE](LICENSE). Las versiones hasta la
2.5.0 se publicaron con licencia MIT.

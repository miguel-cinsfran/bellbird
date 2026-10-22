"""Valores de fábrica de config.ini, única fuente ejecutable.

Este módulo es la definición canónica de los valores predeterminados
que gobiernan primera ejecución, migración de claves ausentes,
paquete distribuible y restablecimientos de Preferencias.
No importa wx ni config.py: es puro y se puede ejecutar sin entorno gráfico.

Orden por sección y clave se conserva en _ORDEN. Helpers pequeños
permiten consultar una clave/sección y producir el texto INI completo.

Para regenerar config.predeterminado.ini (copia legible versionada):
    uv run python -m ytchat.core.config_predeterminada
o con ruta explícita:
    uv run python -m ytchat.core.config_predeterminada RUTA\\config.ini
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

from ytchat.core import paths

# Orden canónico: sección -> lista ordenada de (clave, valor)
_ORDEN: list[tuple[str, list[tuple[str, str]]]] = [
    ("voz", [
        ("motor", "sapi"),
        ("voz", ""),
        ("velocidad_voz", "50"),
        ("volumen", "1.0"),
        ("tono", "50"),
        ("multivoz", "false"),
        ("voz_eventos", ""),
        ("voz_respaldo", ""),
        ("elevenlabs_tope", "30000"),
        ("elevenlabs_solo_importantes", "false"),
    ]),
    ("cola", [
        ("estrategia", "limite"),
        ("tamanio_maximo", "15"),
        ("umbral_solo_nombre", "0"),
    ]),
    ("reconexion", [
        ("reconectar", "true"),
        ("espera_entre_intentos", "15"),
        ("max_intentos", "20"),
    ]),
    ("lectura", [
        ("formato_prefijo", "nombre_mensaje"),
    ]),
    ("filtros", [
        ("palabras_silenciadas", ""),
        ("usuarios_silenciados", ""),
    ]),
    ("texto", [
        ("limpiar_emojis", "true"),
        ("eliminar_urls", "true"),
        ("max_longitud_mensaje", "200"),
    ]),
    ("atajos", [
        ("rep_play", "ctrl+p"),
        ("rep_retro", "ctrl+left"),
        ("rep_avanz", "ctrl+right"),
        ("rep_directo", "ctrl+end"),
        ("rep_detener", "ctrl+d"),
        ("rep_mute", "ctrl+m"),
        ("rep_vol_menos", "ctrl+down"),
        ("rep_vol_mas", "ctrl+up"),
        ("descargas_abrir", "ctrl+shift+d"),
        ("pantalla_completa", "ctrl+f"),
        ("abrir_preferencias", "ctrl+shift+p"),
        ("abrir_historial", "ctrl+shift+h"),
        ("marcar_incidencia", "alt+shift+i"),
        ("abrir_transmision", "ctrl+shift+t"),
        ("copiar_enlace", "alt+shift+e"),
        ("obs_micro", "alt+shift+m"),
        ("avisos_sobrecarga", "alt+shift+a"),
        ("conectar", "alt+shift+c"),
        ("desconectar", "alt+shift+d"),
        ("enviar_chat", "alt+enter"),
        ("ir_lista", "alt+shift+l"),
        ("pausa", "f5"),
        ("detener_tts", "f8"),
        ("velocidad_menos", "f9"),
        ("velocidad_mas", "f10"),
        ("volumen_menos", "f11"),
        ("volumen_mas", "f12"),
        ("silenciar_lectura", "f4"),
        ("silenciar_sonidos", "f7"),
        ("anunciar_estado", "f2"),
        ("anunciar_autor", "f3"),
        ("describir_escena", "ctrl+f2"),
        ("consulta_rapida_ia", "ctrl+shift+f2"),
        ("musica_play", "ctrl+alt+space"),
        ("musica_siguiente", "ctrl+alt+right"),
        ("musica_anterior", "ctrl+alt+left"),
        ("musica_vol_mas", "ctrl+alt+up"),
        ("musica_vol_menos", "ctrl+alt+down"),
        ("musica_que_suena", "ctrl+alt+t"),
        ("musica_silenciar", "ctrl+alt+m"),
        ("musica_aleatorio", "ctrl+alt+a"),
        ("musica_repetir", "ctrl+alt+r"),
        ("musica_detener", "ctrl+alt+d"),
        ("musica_adelantar", "ctrl+alt+shift+right"),
        ("musica_retroceder", "ctrl+alt+shift+left"),
        ("musica_ventana", "ctrl+shift+m"),
        ("preguntar_ia", "ctrl+shift+i"),
    ]),
    ("ui", [
        ("tamanio_fuente_chat", "12"),
        ("mostrar_total_superchats", "true"),
        ("autoplay_reproductor", "true"),
        ("reproductor_solo_audio", "false"),
        ("filtro_activo", "todos"),
        ("silenciar_sonidos", "false"),
        ("mostrar_botones_reproductor", "true"),
        ("cache_video_mb", "1024"),
        ("mostrar_metadatos", "true"),
        ("confirmar_salida", "true"),
        ("recordar_direccion", "true"),
        ("sonido_inicio", "true"),
    ]),
    ("sesion", [
        ("silenciar_lectura", "false"),
        ("ultima_direccion", ""),
        ("version_atajos", "2"),
    ]),
    ("tiktok", [
        ("anunciar_entradas", "false"),
        ("usuario", ""),
    ]),
    ("programados", [
        ("activo", "false"),
    ]),
    ("diagnostico", [
        ("registro_detallado", "false"),
    ]),
    ("overlay", [
        ("activo", "false"),
        ("puerto", "8730"),
    ]),
    ("obs", [
        ("microfono", ""),
    ]),
    ("transmision", [
        ("destino", ""),
        ("avisar_sobrecarga", "true"),
        ("youtube_titulo", ""),
        ("youtube_descripcion", ""),
        ("youtube_privacidad", "unlisted"),
        ("youtube_latencia", "normal"),
        ("youtube_ninos", "false"),
        ("youtube_dvr", "true"),
        ("youtube_categoria", ""),
        ("youtube_etiquetas", ""),
        ("youtube_miniatura", ""),
        ("youtube_lista", ""),
        ("youtube_lista_titulo", ""),
    ]),
    ("estado", [
        ("estado", "true"),
        ("titulo", "true"),
        ("canal", "true"),
        ("espectadores", "true"),
        ("tiempo_directo", "true"),
        ("desfase_directo", "true"),
        ("mensajes_leidos", "true"),
        ("aportes", "true"),
        ("en_cola", "false"),
        ("voz", "false"),
        ("lectura_silenciada", "true"),
        ("overlay", "true"),
        ("programados", "true"),
        ("descartados", "false"),
        ("obs_transmision", "false"),
        ("obs_grabacion", "false"),
        ("obs_escena", "false"),
        ("musica", "true"),
        ("igualando", "true"),
    ]),
    ("descargas", [
        ("formato", "mp4"),
        ("bitrate", "192"),
        ("carpeta", "Descargas"),
        ("enumerar", "false"),
    ]),
    ("actualizaciones", [
        ("buscar_al_iniciar", "true"),
    ]),
    ("musica", [
        ("carpeta", ""),
        ("aleatorio", "false"),
        ("repetir", "false"),
        ("retomar", "true"),
        ("sonido_tema", "true"),
        ("decir", ""),
        ("decir_titulo", "true"),
        ("incluir_artista", "false"),
        ("decir_pausa", "true"),
        ("normalizar", "true"),
        ("preguntar_igualar", "true"),
        ("volumen", "50"),
        ("salida", ""),
        ("salida_nombre", ""),
        ("atajos_globales", "false"),
        ("mostrar_cola", "false"),
    ]),
    ("ia", [
        ("proveedor", "gemini"),
        ("modelo", ""),
        ("direccion", ""),
        ("pregunta", ""),
        ("largo", "media"),
        ("tiempo_espera", "60"),
        ("solo_gratis", "false"),
        ("privacidad_aceptada", "false"),
        ("decir_analizando", "true"),
    ]),
]

# Comentarios útiles por sección (breves y prácticos)
_COMENTARIOS: dict[str, str] = {
    "voz": (
        "# Motor de voz: sapi, onecore o elevenlabs. Voz vacía es la\n"
        "# primera del sistema; se guarda por nombre. Multivoz usa otra\n"
        "# voz para eventos (Super Chats, regalos). Se cambia en\n"
        "# Preferencias > Lectura. Con ElevenLabs, voz_respaldo es la voz\n"
        "# de Windows que suena si falla o se pasa el tope de caracteres\n"
        "# (elevenlabs_tope, 0 sin tope), y elevenlabs_solo_importantes\n"
        "# reserva la nube para Super Chats, stickers, miembros, cofres,\n"
        "# el dueño del canal y los moderadores.\n"
    ),
    "cola": "# Cola de lectura: con límite descarta los más viejos si se llena.\n",
    "reconexion": "# Reconexión automática si se corta el chat.\n",
    "lectura": "# Qué parte del mensaje se lee: nombre y mensaje, solo uno, etc.\n",
    "filtros": "# Listas en minúsculas, separadas por comas. Vacías no filtran.\n",
    "texto": "# Limpieza del texto antes de leer y longitud máxima en caracteres.\n",
    "atajos": (
        "# Atajos por familia: Ctrl reproductor, Alt chat, Ctrl+Shift ventanas y Alt+Shift directo.\n"
        "# F voz y Ctrl+Alt música. F9-F12 se guardan pero no se editan. Alt+F4 y F6 no se guardan.\n"
    ),
    "ui": (
        "# Interfaz: fuente del chat y opciones visibles.\n"
        "# confirmar_salida pregunta antes de salir con chat o\n"
        "# transmisión en curso; recordar_direccion guarda la última\n"
        "# dirección conectada; sonido_inicio suena al arrancar.\n"
    ),
    "sesion": (
        "# Silenciar lectura al arrancar.\n"
        "# ultima_direccion es la última dirección conectada, para\n"
        "# ofrecerla al arrancar si recordar_direccion está activado.\n"
    ),
    "tiktok": "# Solo TikTok: anunciar quién entra al directo puede ser muchísimo.\n",
    "diagnostico": "# Registro detallado para diagnosticar fallos (requiere reiniciar).\n",
    "overlay": "# Panel de chat para transmitir por navegador (overlay web).\n",
    "obs": "# Integración con OBS: nombre de la fuente de micrófono.\n",
    "transmision": (
        "# Transmisión: destino del directo y datos del directo de\n"
        "# YouTube (se piden al transmitir y se recuerdan). La\n"
        "# descripción guarda los saltos de línea como \\n.\n"
    ),
    "estado": (
        "# Componentes que anuncia F2. true se dice, false se omite.\n"
        "# Se elige en Preferencias > Estado. El orden en que se dice es fijo.\n"
    ),
    "descargas": (
        "# Gestor de descargas con yt-dlp. Formato: mp4 | webm | mp3 | m4a.\n"
        "# Bitrate solo para audio. Carpeta portable junto al ejecutable.\n"
    ),
    "actualizaciones": "# Buscar actualizaciones de la app al iniciar.\n",
    "musica": (
        "# Música local: carpeta de la biblioteca, orden y opciones de\n"
        "# reproducción. La salida es el identificador de un dispositivo\n"
        "# de audio de libVLC; vacía usa el predeterminado del sistema.\n"
    ),
    "ia": (
        "# Preguntar a la IA sobre la imagen. La clave de cada proveedor no\n"
        "# va acá: se guarda en el Administrador de credenciales de Windows.\n"
        "# Pregunta vacía usa la de fábrica. Dirección solo para «Otro\n"
        "# compatible con OpenAI». Tiempo de espera en segundos.\n"
    ),
}


# Mapa para consultas rápidas por sección y clave (con orden preservado)
_CANONICA: OrderedDict[str, OrderedDict[str, str]] = OrderedDict(
    (sec, OrderedDict(pares)) for sec, pares in _ORDEN
)


def obtener(seccion: str, clave: str, fallback: str = "") -> str:
    """Valor de fábrica de una clave, o fallback si no existe."""
    sec = _CANONICA.get(seccion)
    if sec is None:
        return fallback
    return sec.get(clave, fallback)


def seccion(nombre: str) -> dict[str, str]:
    """Copia del diccionario de una sección (orden preservado)."""
    sec = _CANONICA.get(nombre)
    if sec is None:
        return {}
    return dict(sec)


def secciones() -> list[str]:
    """Nombres de sección en orden canónico."""
    return list(_CANONICA.keys())


def datos() -> dict[str, dict[str, str]]:
    """Copia completa de la configuración canónica (sección -> clave -> valor)."""
    return {sec: dict(vals) for sec, vals in _CANONICA.items()}


def generar_texto() -> str:
    """Produce el contenido completo de config.predeterminado.ini."""
    partes: list[str] = []
    partes.append(
        "# YTChat TTS, configuración de fábrica\n"
        "# Valores predeterminados. Este archivo se genera con:\n"
        "#   uv run python -m ytchat.core.config_predeterminada\n"
        "# No editar a mano sin regenerar la otra copia: config_predeterminada.py\n"
    )
    for sec, pares in _ORDEN:
        partes.append(f"\n[{sec}]\n")
        comentario = _COMENTARIOS.get(sec, "")
        if comentario:
            partes.append(comentario)
        for clave, valor in pares:
            if valor == "":
                partes.append(f"{clave} =\n")
            else:
                partes.append(f"{clave} = {valor}\n")
    # Asegurar salto final
    texto = "".join(partes)
    if not texto.endswith("\n"):
        texto += "\n"
    return texto


def escribir(ruta: str | Path) -> Path:
    """Escribe el texto canónico en ruta y devuelve la ruta."""
    p = Path(ruta)
    p.write_text(generar_texto(), encoding="utf-8")
    return p


if __name__ == "__main__":
    if len(sys.argv) > 1:
        escribir(Path(sys.argv[1]))
    else:
        escribir(paths.config_predeterminada_ini())

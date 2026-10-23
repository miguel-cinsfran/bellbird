"""Constantes, carga de configuración, atajos de teclado y logging."""

from __future__ import annotations

import configparser
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ytchat.core import config_predeterminada
from ytchat.core import diagnostico
from ytchat.core.eventos_sonido import EVENTOS as _EVENTOS_SONIDO
from ytchat.core import paths
from ytchat.core.atajos import (
    ATAJOS_DEFAULTS, ATAJOS_FIJOS_DEFAULTS, ATAJOS_FIJOS, ATAJOS_GRUPOS,
    _AREA_POR_GRUPO, ATAJOS_AREA, _SIMBOLOS_PERMITIDOS, _TECLAS_NOMBRE,
    _RE_ATAJO, _RE_CTRL_ALT, _RE_FKEY, _RE_CTRL_FKEY, Atajo,
    todos_los_atajos_default, _normalizar_atajo, atajo_valido_para_area,
    parsear_atajos, detectar_conflictos_atajos, migrar_atajos_config,
)  # noqa: F401  (reexport para quien importa desde config)
from ytchat.core.config_descargas import guardar_opciones_descarga, obtener_opciones_descarga
from ytchat.core.config_lectura import opciones_lectura
from ytchat.core.config_musica import opciones_musica


LIBRERIAS_SILENCIADAS = (
    "httpx", "httpcore", "hpack", "h2", "websockets", "googleapiclient",
    "google_auth_httplib2", "google.auth", "urllib3", "asyncio", "comtypes",
    "libloader", "PIL", "charset_normalizer",
)


# ── Identidad ─────────────────────────────────────────────────────────────────

APP_NAME    = "YTChat TTS"
APP_VERSION = "2.4.1"

# ── Tipos de mensaje ──────────────────────────────────────────────────────────

TIPO_TEXTO     = "text"
TIPO_SUPERCHAT = "superchat"
TIPO_STICKER   = "sticker"
TIPO_MIEMBRO   = "member"
TIPO_ENTRADA   = "entrada"   # alguien entra al directo (solo TikTok, opcional)
TIPO_SEGUIR    = "seguir"    # alguien sigue el canal (solo TikTok)
TIPO_COMPARTIR = "compartir" # alguien comparte el directo (solo TikTok)
TIPO_COFRE     = "cofre"     # cofre de regalos (solo TikTok)
TIPO_ME_GUSTA  = "me_gusta"  # me gusta del directo (solo TikTok, solo suena)

FILTROS = [
    ("Todos",        None),
    ("Solo texto",   TIPO_TEXTO),
    ("Super Chats",  TIPO_SUPERCHAT),
    ("Membresías",   TIPO_MIEMBRO),
]


# ── Carpeta base ──────────────────────────────────────────────────────────────
# Cuando se empaqueta con PyInstaller (onedir), los archivos editables
# (config.ini, sounds.ini, sounds/) viven junto al .exe, no dentro de
# _MEIPASS. Esta función resuelve la ruta correcta en ambos contextos.

def app_dir() -> Path:
    # Se conserva por las herramientas fuera de la app que la usan. El código
    # de la aplicación obtiene sus rutas de `paths`, no de aquí.
    return paths.carpeta_instalacion()


# ── Logging ───────────────────────────────────────────────────────────────────

def librerias_silenciadas() -> tuple[str, ...]:
    return LIBRERIAS_SILENCIADAS


def configurar_logging(nivel_consola: int = logging.INFO) -> None:
    root = logging.getLogger()
    # Idempotente: se marcan los handlers propios y, si ya están puestos, no
    # se vuelven a añadir (cada línea saldría duplicada en consola y en el log).
    if any(getattr(h, "_ytchat_propio", False) for h in root.handlers):
        return
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(nivel_consola)
    ch.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    ch._ytchat_propio = True
    root.addHandler(ch)

    log_path = paths.log_principal()
    try:
        fh = RotatingFileHandler(log_path, maxBytes=1_048_576, backupCount=1, encoding="utf-8")
        fh.setLevel(logging.WARNING)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
    except Exception as exc:
        logger.warning("No se pudo crear ytchat.log: %s", exc)

    # El registro detallado se activa únicamente si se solicita en Preferencias.
    detallado = False
    try:
        p_diag = _mk_parser()
        p_diag.read(paths.config_ini(), encoding="utf-8")
        detallado = p_diag.getboolean("diagnostico", "registro_detallado",
                                     fallback=False)
    except Exception as exc:
        logger.warning(
            "No se pudo leer la configuración de diagnóstico: %s", exc)
    if detallado:
        try:
            root.addHandler(diagnostico.crear_manejador_detallado(
                paths.log_detallado()))
        except Exception as exc:
            logger.warning(
                "No se pudo crear ytchat-debug.log: %s", exc)

    # ytchat.log conserva los avisos de terceros, que pueden explicar un fallo.
    # Las librerías de terceros no deben ocultar los diagnósticos propios.
    for _lib in librerias_silenciadas():
        logging.getLogger(_lib).setLevel(logging.WARNING)


logger = diagnostico.obtener_logger(__name__)


# ── Carga de config.ini ──────────────────────────────────────────────────────

_CONFIG_FALLBACK = config_predeterminada.generar_texto()

_SOUNDS_FALLBACK = """\
[sonidos]
activar = true
volumen = 0.7

# Tema de sonido: carpeta dentro de sounds/themes/ con un WAV por evento,
# nombrado igual que el evento (p. ej. mensaje_nuevo.wav). Para crear tu
# propio tema, copia sounds/themes/default a sounds/themes/mi_tema,
# reemplaza los .wav que quieras y pon aquí:  tema = mi_tema
tema = default

# Opcional (avanzado): puedes forzar un archivo concreto para un evento
# escribiendo su ruta aquí; tiene prioridad sobre el tema. Por ejemplo:
#   superchat = sounds/mis_efectos/caja.wav
"""

# Carpeta base de temas y tema por defecto.
_TEMAS_DIR   = "themes"
_TEMA_DEFECTO = "default"


def _mk_parser() -> configparser.ConfigParser:
    # Lo que escribe la persona se lee tal cual, sin interpolación ni
    # comentarios en línea: un `%`, `#` o `;` en un valor no lo toca.
    return configparser.ConfigParser(interpolation=None, default_section="__none__")


def _fallback(sec: str, k: str) -> str:
    return config_predeterminada.obtener(sec, k, "")


def _gs(p, sec, k):       return p.get(sec, k, fallback=_fallback(sec, k)).strip()
def _gi(v, d):
    try:    return int(str(v).strip())
    except Exception: return d
def _gf(v, d):
    try:    return float(str(v).strip())
    except Exception: return d
def _pi(p, sec, k, lo=0, hi=None):
    fb = _fallback(sec, k)
    try:
        d = int(fb.strip()) if fb.strip() else 0
    except Exception:
        d = 0
    v = max(lo, _gi(_gs(p, sec, k), d))
    return min(hi, v) if hi is not None else v
def _pf(p, sec, k, lo=0.0, hi=1.0):
    fb = _fallback(sec, k)
    try:
        d = float(fb.strip()) if fb.strip() else 1.0
    except Exception:
        d = 1.0
    return max(lo, min(hi, _gf(_gs(p, sec, k), d)))
def _pb(p, sec, k):
    try:    return p.getboolean(sec, k)
    except Exception: return _fallback(sec, k).strip().lower() in ("true", "yes", "1", "on")
def normalizar_repetir(valor) -> str:
    """Modo de repetición como texto: "no", "todo" o "tema".

    Acepta los booleanos viejos de la preferencia además de los tres textos.
    "false", vacío y cualquier valor desconocido valen "no".
    """
    if valor is True:
        return "todo"
    if valor is False:
        return "no"
    texto = str(valor or "").strip().lower()
    if texto == "true":
        return "todo"
    if texto in ("no", "todo", "tema"):
        return texto
    return "no"
def _lista(v: str) -> list:
    return [x.strip().lower() for x in v.split(",") if x.strip()]


def codificar_texto_ini(texto: str | None) -> str:
    """Codifica un texto libre para guardarlo en una línea del INI.

    El parser (`_mk_parser`, con interpolación y comentarios en línea)
    interpreta `%`, `#` y `;`, así que se escapan junto con la barra
    invertida y el salto de línea. `decodificar_texto_ini` lo restaura.
    """
    plano = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    plano = plano.replace("\\", "\\\\")
    plano = plano.replace("\n", "\\n")
    plano = plano.replace("%", "\\x25")
    plano = plano.replace("#", "\\x23")
    plano = plano.replace(";", "\\x3b")
    return plano


def decodificar_texto_ini(valor: str | None) -> str:
    """Restaura un texto guardado con `codificar_texto_ini`.

    Recorre el texto una sola vez: solo deshace las cinco secuencias
    exactas (`\\\\`, `\\n`, `\\x25`, `\\x23`, `\\x3b`). Una barra seguida
    de cualquier otra cosa se deja tal cual, para que lo que la persona
    escribió vuelva idéntico.
    """
    texto = valor or ""
    salida: list[str] = []
    i = 0
    while i < len(texto):
        if texto[i] == "\\" and i + 1 < len(texto):
            siguiente = texto[i + 1]
            if siguiente == "\\":
                salida.append("\\")
                i += 2
                continue
            if siguiente == "n":
                salida.append("\n")
                i += 2
                continue
            secuencia = texto[i + 1:i + 4]
            if secuencia in ("x25", "x23", "x3b"):
                salida.append({"x25": "%", "x23": "#", "x3b": ";"}[secuencia])
                i += 4
                continue
        salida.append(texto[i])
        i += 1
    return "".join(salida)


def _aplicar_opcion(lineas: list[str], seccion: str, clave: str, valor: str) -> list[str]:
    """Aplica un cambio sobre las líneas del INI y devuelve las líneas.

    Preserva comentarios y orden: reemplaza la clave si existe, la inserta
    tras la última clave de la sección, o crea la sección al final si no
    existe. Arregla el salto de línea final cuando hace falta.
    """
    sec_lower = seccion.lower()
    clave_lower = clave.lower()
    nueva = f"{clave} = {valor}\n"
    in_sec = False
    insert_pos = None

    for i, line in enumerate(lineas):
        stripped = line.strip()
        if stripped.startswith("["):
            if in_sec:
                break
            in_sec = stripped.lower() == f"[{sec_lower}]"
            if in_sec:
                insert_pos = i + 1
        elif in_sec:
            # Los blancos y comentarios del final de la sección no mueven el
            # punto de inserción: la clave nueva va tras la última clave, no
            # pegada a la cabecera de la sección siguiente.
            if not stripped or stripped.startswith(("#", ";")):
                continue
            k = stripped.split("=", 1)[0].strip().lower() if "=" in stripped else ""
            if k == clave_lower:
                lineas[i] = nueva
                return lineas
            insert_pos = i + 1

    if in_sec:
        if insert_pos is None:
            insert_pos = len(lineas)
        # Si la línea anterior no termina en salto (final de archivo), la
        # clave nueva quedaría pegada a ella.
        if insert_pos > 0 and not lineas[insert_pos - 1].endswith("\n"):
            lineas[insert_pos - 1] += "\n"
        lineas.insert(insert_pos, nueva)
    elif insert_pos is None:
        lineas.extend(["\n", f"[{seccion}]\n", nueva])
    return lineas


def guardar_opciones(ruta: Path | None, cambios: list[tuple[str, str, str]]) -> bool:
    """Aplica varios cambios al INI en una sola lectura y una sola escritura.

    `cambios` es una lista de tuplas `(seccion, clave, valor)` en orden. Se
    aplican sobre las líneas en memoria con las mismas reglas que
    `guardar_opcion`, y se escribe una sola vez de forma atómica (temporal al
    lado + reemplazo). Devuelve True si escribió, si `ruta` es None o si la
    lista está vacía; False si no pudo leer o escribir. El fallo se registra
    como aviso, porque el usuario pierde datos.
    """
    from ytchat.core import archivos

    if ruta is None:
        return True
    if not cambios:
        return True
    try:
        txt = ruta.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("guardar_opciones: no se pudo leer %s: %s", ruta, exc)
        return False

    lineas = txt.splitlines(keepends=True)
    for seccion, clave, valor in cambios:
        _aplicar_opcion(lineas, seccion, clave, valor)

    try:
        archivos.escribir_texto_atomico(ruta, "".join(lineas))
    except Exception as exc:
        logger.warning("guardar_opciones: no se pudo escribir %s: %s", ruta, exc)
        return False
    return True


def guardar_opcion(ruta: Path | None, seccion: str, clave: str, valor: str) -> bool:
    """Actualiza una clave en el INI preservando comentarios y orden.

    Escribe de forma atómica (temporal al lado + reemplazo). Devuelve True
    si escribió o si `ruta` es None (no hay nada que guardar); False si no
    pudo leer o escribir. El fallo se registra como aviso, porque el usuario
    pierde datos.
    """
    return guardar_opciones(ruta, [(seccion, clave, valor)])


# La sección [musica] vive en `config_musica`: mismo nombre corto para lo
# que la usaba por acá.
_opciones_musica = opciones_musica
# La sección [lectura] vive en `config_lectura`: mismo nombre corto.
_opciones_lectura = opciones_lectura


def cargar_configuracion() -> dict:
    ruta = paths.config_ini()
    if not ruta.exists():
        logger.warning("config.ini no encontrado. Creando con valores por defecto.")
        try:    ruta.write_text(_CONFIG_FALLBACK, encoding="utf-8")
        except Exception as exc: logger.error("No se pudo crear config.ini: %s", exc)

    p = _mk_parser()
    try:
        if not p.read(ruta, encoding="utf-8"):
            logger.error("No se pudo leer config.ini."); sys.exit(1)
    except configparser.Error as exc:
        logger.error("Error de sintaxis en config.ini: %s", exc)
        logger.error("Borra config.ini y vuelve a abrir la aplicación para regenerarlo.")
        sys.exit(1)

    estrategia = _gs(p, "cola", "estrategia").lower()
    if estrategia not in ("todas", "limite"): estrategia = "limite"

    atajos_raw = {}
    if p.has_section("atajos"):
        atajos_raw = {k.strip().lower(): (v or "").strip() for k, v in p.items("atajos")}
    migrar_atajos_config(p, ruta, atajos_raw)
    # Migración genérica: agregar toda sección o clave ausente desde la fuente
    # canónica, preservando valores existentes incluso vacíos y claves desconocidas.
    _atajos_faltantes = []
    for _sec, _claves in config_predeterminada.datos().items():
        for _clave, _valor_def in _claves.items():
            if not p.has_option(_sec, _clave):
                guardar_opcion(ruta, _sec, _clave, _valor_def)
                if _sec == "atajos":
                    atajos_raw[_clave] = _valor_def
                    _atajos_faltantes.append(_clave)
    if _atajos_faltantes:
        logger.info("Atajos nuevos añadidos a config.ini: %s", ", ".join(_atajos_faltantes))

    desc_op = obtener_opciones_descarga()

    # Estado (F2): un booleano por componente.
    from ytchat.capture.estado_sesion import COMPONENTES as _EST_COMP
    # Fallback canónico para estado: true donde la fábrica lo marca así.
    _estado_defaults = config_predeterminada.seccion("estado")
    estado_toggles = set()
    for comp in _EST_COMP:
        try:    activo = p.getboolean("estado", comp)
        except Exception: activo = _estado_defaults.get(comp, "false").lower() in ("true", "yes", "1", "on")
        if activo:
            estado_toggles.add(comp)

    filtro_activo = _gs(p, "ui", "filtro_activo").lower()
    if filtro_activo not in ("todos", "texto", "superchat", "miembro"):
        filtro_activo = "todos"

    from ytchat.obs import obs_destinos as _destinos
    destino = _gs(p, "transmision", "destino")
    if destino not in _destinos.DESTINOS:
        destino = ""

    from ytchat.youtube import emision as _emision
    privacidad = _gs(p, "transmision", "youtube_privacidad")
    if privacidad not in _emision.PRIVACIDADES:
        privacidad = _emision.PRIVACIDAD_INICIAL
    latencia = _gs(p, "transmision", "youtube_latencia")
    if latencia not in _emision.LATENCIAS:
        latencia = _emision.LATENCIA_INICIAL
    categoria = _gs(p, "transmision", "youtube_categoria")
    if categoria not in {identificador for identificador, _t
                         in _emision.CATEGORIAS}:
        categoria = ""

    # [voz]: el motor se valida contra los válidos de Prism (importarlos aquí
    # no arrastra Prism: motores lo importa de forma perezosa). La velocidad se
    # guarda como porcentaje propio (0..100); la clave vieja en palabras por
    # minuto se convierte una sola vez y se fija en el archivo, así el arranque
    # siguiente no vuelve al valor de fábrica.
    from ytchat.voice import escala_voz as _escala
    from ytchat.voice import motores as _motores
    motor = _gs(p, "voz", "motor").lower()
    if motor not in _motores.MOTORES:
        motor = "sapi"
    if p.has_option("voz", "velocidad_voz"):
        velocidad_voz = max(0, min(100, _gi(
            _gs(p, "voz", "velocidad_voz"), _escala.VELOCIDAD_NORMAL)))
    elif p.has_option("voz", "velocidad"):
        velocidad_voz = _escala.velocidad_desde_wpm(
            _gi(_gs(p, "voz", "velocidad"), 175))
        guardar_opcion(ruta, "voz", "velocidad_voz", str(velocidad_voz))
    else:
        velocidad_voz = _escala.VELOCIDAD_NORMAL

    return {
        "motor": motor,
        "voz": _gs(p, "voz", "voz"),
        "velocidad_voz": velocidad_voz,
        "volumen": _pf(p, "voz", "volumen"),
        "tono": _pi(p, "voz", "tono", lo=0, hi=100),
        "multivoz": _pb(p, "voz", "multivoz"),
        "voz_eventos": _gs(p, "voz", "voz_eventos"),
        "voz_respaldo": _gs(p, "voz", "voz_respaldo"),
        "elevenlabs_tope": _pi(p, "voz", "elevenlabs_tope", lo=0),
        "elevenlabs_solo_importantes": _pb(p, "voz", "elevenlabs_solo_importantes"),
        "estrategia": estrategia,
        "tamanio_maximo": _pi(p, "cola", "tamanio_maximo", lo=1),
        "umbral_solo_nombre": _pi(p, "cola", "umbral_solo_nombre"),
        "reconectar": _pb(p, "reconexion", "reconectar"),
        "espera_entre_intentos": _pi(p, "reconexion", "espera_entre_intentos", lo=1),
        "max_intentos": _pi(p, "reconexion", "max_intentos"),
        **_opciones_lectura(p),
        "palabras_silenciadas": _lista(_gs(p, "filtros", "palabras_silenciadas")),
        "usuarios_silenciados": _lista(_gs(p, "filtros", "usuarios_silenciados")),
        "limpiar_emojis": _pb(p, "texto", "limpiar_emojis"),
        "eliminar_urls": _pb(p, "texto", "eliminar_urls"),
        "max_longitud_mensaje": _pi(p, "texto", "max_longitud_mensaje"),
        "tamanio_fuente_chat": _pi(p, "ui", "tamanio_fuente_chat", lo=8, hi=24),
        "mostrar_total_superchats": _pb(p, "ui", "mostrar_total_superchats"),
        "autoplay_reproductor": _pb(p, "ui", "autoplay_reproductor"),
        "reproductor_solo_audio": _pb(p, "ui", "reproductor_solo_audio"),
        "mostrar_botones_reproductor": _pb(p, "ui", "mostrar_botones_reproductor"),
        "cache_video_mb": _pi(p, "ui", "cache_video_mb", lo=0, hi=20000),
        "mostrar_metadatos": _pb(p, "ui", "mostrar_metadatos"),
        "confirmar_salida": _pb(p, "ui", "confirmar_salida"),
        "sonido_inicio": _pb(p, "ui", "sonido_inicio"),
        "filtro_activo": filtro_activo,
        "silenciar_sonidos": _pb(p, "ui", "silenciar_sonidos"),
        "silenciar_lectura": _pb(p, "sesion", "silenciar_lectura"),
        "tiktok_anunciar_entradas": _pb(p, "tiktok", "anunciar_entradas"),
        "tiktok_usuario": _gs(p, "tiktok", "usuario"),
        "transmision_destino": destino,
        "avisar_sobrecarga": _pb(p, "transmision", "avisar_sobrecarga"),
        "transmision_youtube_titulo": decodificar_texto_ini(_gs(p, "transmision", "youtube_titulo")),
        "transmision_youtube_descripcion": decodificar_texto_ini(_gs(p, "transmision", "youtube_descripcion")),
        "transmision_youtube_privacidad": privacidad,
        "transmision_youtube_latencia": latencia,
        "transmision_youtube_ninos": _pb(p, "transmision", "youtube_ninos"),
        "transmision_youtube_dvr": _pb(p, "transmision", "youtube_dvr"),
        "transmision_youtube_categoria": categoria,
        "transmision_youtube_etiquetas": decodificar_texto_ini(
            _gs(p, "transmision", "youtube_etiquetas")),
        "transmision_youtube_miniatura": decodificar_texto_ini(
            _gs(p, "transmision", "youtube_miniatura")),
        "transmision_youtube_lista": _gs(p, "transmision", "youtube_lista"),
        "transmision_youtube_lista_titulo": decodificar_texto_ini(
            _gs(p, "transmision", "youtube_lista_titulo")),
        "programados_activo": _pb(p, "programados", "activo"),
        "buscar_actualizaciones_al_iniciar": _pb(p, "actualizaciones", "buscar_al_iniciar"),
        "registro_detallado": _pb(p, "diagnostico", "registro_detallado"),  # configurar_logging se adelanta al diccionario.
        "overlay_activo": _pb(p, "overlay", "activo"),
        "overlay_puerto": _pi(p, "overlay", "puerto", lo=1),
        "obs_microfono": _gs(p, "obs", "microfono"),
        # [musica]: biblioteca local y reproducción. La carpeta va como texto libre, igual que en [transmision].
        **_opciones_musica(p),
        "estado_toggles": estado_toggles,
        "atajos_raw": atajos_raw,
        "ruta_config": ruta,
        # Gestor de descargas (GestorDescargas / gui_descargas). Las opciones
        # validadas viven además en `desc_op` por si alguien quiere pasarlas
        # explícitamente sin parsear el INI de nuevo.
        "descargas": desc_op,
        "descargas_formato": desc_op["formato"],
        "descargas_bitrate": desc_op["bitrate"],
        "descargas_carpeta": desc_op["carpeta"],
        "descargas_enumerar": desc_op["enumerar"],
    }


def cargar_sonidos() -> dict:
    """Devuelve dict para `sound_player.cargar()`."""
    ruta = paths.sounds_ini()
    if not ruta.exists():
        logger.warning("sounds.ini no encontrado. Creando con valores por defecto.")
        try:    ruta.write_text(_SOUNDS_FALLBACK, encoding="utf-8")
        except Exception as exc: logger.error("No se pudo crear sounds.ini: %s", exc)

    p = _mk_parser()
    try:
        if not p.read(ruta, encoding="utf-8"):
            return {"activar": False, "volumen": 0.7, "eventos": {}}
    except configparser.Error as exc:
        logger.warning("Error en sounds.ini: %s. Sonidos desactivados.", exc)
        return {"activar": False, "volumen": 0.7, "eventos": {}}

    activar, volumen, tema = True, 0.7, _TEMA_DEFECTO
    if p.has_section("sonidos"):
        try:    activar = p.getboolean("sonidos", "activar", fallback=True)
        except Exception: pass
        try:    volumen = max(0.0, min(1.0, float(p.get("sonidos", "volumen", fallback="0.7"))))
        except Exception: pass
        try:    tema = (p.get("sonidos", "tema", fallback=_TEMA_DEFECTO).strip()
                        or _TEMA_DEFECTO)
        except Exception: pass

    eventos: dict[str, Path | None] = {}
    for ev in _EVENTOS_SONIDO:
        # 1) Ruta explícita en sounds.ini (override avanzado, máxima prioridad).
        # Una clave PRESENTE con valor vacío silencia el evento (None); una
        # clave AUSENTE cae al archivo del tema, como antes.
        if p.has_option("sonidos", ev):
            raw = (p.get("sonidos", ev, fallback="") or "").strip()
            if not raw:
                eventos[ev] = None
                continue
            ruta_ev = Path(raw)
            if not ruta_ev.is_absolute():
                ruta_ev = paths.carpeta_instalacion() / ruta_ev
            eventos[ev] = ruta_ev
            continue
        # 2) Si no, el archivo del tema: sounds/themes/<tema>/<evento>.wav
        eventos[ev] = _ruta_evento_tema(tema, ev)

    return {"activar": activar, "volumen": volumen, "eventos": eventos}


def _ruta_evento_tema(tema: str, evento: str) -> Path:
    """Ruta del `.wav` de un evento dentro de un tema."""
    return paths.carpeta_sonidos() / _TEMAS_DIR / tema / f"{evento}.wav"


def ruta_muestra_tema(tema: str, evento: str = "mensaje_nuevo") -> Path:
    """Ruta de la muestra que suena al recorrer la lista de temas."""
    return _ruta_evento_tema(tema, evento)


# ── Helpers de temas de sonido (para el diálogo de Preferencias) ──────────────

def listar_temas_sonido() -> list[str]:
    """Nombres de carpeta dentro de sounds/themes/ (cada una es un tema)."""
    carpeta = paths.carpeta_sonidos() / _TEMAS_DIR
    try:
        temas = sorted(d.name for d in carpeta.iterdir() if d.is_dir())
    except Exception:
        temas = []
    if _TEMA_DEFECTO not in temas:
        temas.insert(0, _TEMA_DEFECTO)
    return temas


def tema_sonido_actual() -> str:
    """Lee el tema activo de sounds.ini (o el por defecto)."""
    ruta = paths.sounds_ini()
    p = _mk_parser()
    try:
        p.read(ruta, encoding="utf-8")
        return (p.get("sonidos", "tema", fallback=_TEMA_DEFECTO).strip()
                or _TEMA_DEFECTO)
    except Exception:
        return _TEMA_DEFECTO

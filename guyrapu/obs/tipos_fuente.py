"""Qué fuentes puede agregar Guyrapu y cómo se traducen a OBS.

Es lógica pura: el catálogo, el nombre libre, el tipo de texto que OBS
acepta, los ajustes de cada tipo en los dos sentidos y el filtro de las
listas que devuelve OBS.
"""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.core.idioma import N_, _


@dataclass(frozen=True)
class TipoFuente:
    clave: str
    etiqueta: object
    nombre: object
    tipo_obs: str
    lugar: str


# El orden es el del menú Agregar fuente.
CATALOGO = (
    TipoFuente("camara", N_("&Cámara…"), N_("Cámara"),
               "dshow_input", "camara"),
    TipoFuente("pantalla", N_("Captura de &pantalla…"),
               N_("Captura de pantalla"), "monitor_capture", "ajustada"),
    TipoFuente("ventana", N_("Captura de &ventana…"),
               N_("Captura de ventana"), "window_capture", "ventana"),
    TipoFuente("juego", N_("Captura de &juego…"),
               N_("Captura de juego"), "game_capture", "ajustada"),
    TipoFuente("imagen", N_("&Imagen…"), N_("Imagen"),
               "image_source", "ajustada"),
    TipoFuente("multimedia", N_("&Archivo multimedia…"),
               N_("Archivo multimedia"), "ffmpeg_source", "ajustada"),
    TipoFuente("texto", N_("&Texto…"), N_("Texto"),
               "text_gdiplus", "texto"),
    TipoFuente("otra_escena", N_("&Fuente de otra escena…"), "",
               "", "otra_escena"),
)

# Los tipos legibles que pone `obs_prevuelo` en las filas de la escena.
TIPOS_CAPTURA = (N_("captura de ventana"), N_("captura de juego"))

_TIPOS_OBS = {
    "dshow_input": "camara",
    "monitor_capture": "pantalla",
    "window_capture": "ventana",
    "game_capture": "juego",
    "image_source": "imagen",
    "ffmpeg_source": "multimedia",
}


def por_clave(clave):
    return next((tipo for tipo in CATALOGO if tipo.clave == clave), None)


def etiquetas_menu() -> tuple:
    return tuple(_(tipo.etiqueta) for tipo in CATALOGO)


def nombre_libre(base, ocupados) -> str:
    """El nombre base o el primero con número libre, como los de hoy."""
    nombre = base
    contador = 2
    while nombre in ocupados:
        # Traductores: {nombre} es el nombre base y {contador} el número libre.
        nombre = _("{nombre} {contador}").format(nombre=base,
                                                 contador=contador)
        contador += 1
    return nombre


def nombre_propuesto(tipo, ocupados) -> str:
    return nombre_libre(_(tipo.nombre), ocupados)


def tipo_de_texto(tipos) -> str:
    """El tipo de texto versionado que trae OBS, o su base si no hay."""
    for tipo in tipos or ():
        if tipo == "text_gdiplus" or str(tipo).startswith("text_gdiplus_v"):
            return tipo
    return "text_gdiplus"


def clave_de_obs(tipo_obs) -> str:
    """La clave de Guyrapu para un `inputKind` de OBS, o vacío si es ajeno."""
    texto = str(tipo_obs or "")
    if texto == "text_gdiplus" or texto.startswith("text_gdiplus_v"):
        return "texto"
    return _TIPOS_OBS.get(texto, "")


def hay_captura(filas) -> bool:
    """Si la escena ya tiene una captura de ventana o de juego."""
    buscados = {_(texto) for texto in TIPOS_CAPTURA}
    return any(getattr(fila, "tipo", "") in buscados for fila in filas or ())


def ajustes(clave, valores, actual=None) -> dict:
    """Los ajustes de OBS que corresponden a los valores del cuadro."""
    valores = valores or {}
    if clave == "camara":
        return {"video_device_id": valores.get("dispositivo", "")}
    if clave == "pantalla":
        return {"monitor_id": valores.get("pantalla", "")}
    if clave == "ventana":
        return {"window": valores.get("ventana", "")}
    if clave == "juego":
        modo = valores.get("modo") or "any_fullscreen"
        if modo != "window":
            return {"capture_mode": "any_fullscreen"}
        return {"capture_mode": "window",
                "window": valores.get("ventana", "")}
    if clave == "imagen":
        return {"file": valores.get("archivo", "")}
    if clave == "multimedia":
        return {"local_file": valores.get("archivo", ""),
                "is_local_file": True,
                "looping": bool(valores.get("repetir", False))}
    if clave == "texto":
        fuente = dict((actual or {}).get("font") or {})
        fuente.setdefault("face", "Arial")
        if valores.get("cara"):
            fuente["face"] = valores["cara"]
        if valores.get("tamano") is not None:
            fuente["size"] = int(valores["tamano"])
        return {"text": valores.get("texto", ""), "font": fuente}
    return {}


def valores(clave, ajustes_obs) -> dict:
    """Los valores del cuadro leídos de los ajustes de OBS."""
    ajustes_obs = ajustes_obs or {}
    if clave == "camara":
        return {"dispositivo": str(ajustes_obs.get("video_device_id") or "")}
    if clave == "pantalla":
        return {"pantalla": str(ajustes_obs.get("monitor_id") or "")}
    if clave == "ventana":
        return {"ventana": str(ajustes_obs.get("window") or "")}
    if clave == "juego":
        modo = str(ajustes_obs.get("capture_mode") or "any_fullscreen")
        if modo not in ("any_fullscreen", "window"):
            modo = "any_fullscreen"
        return {"modo": modo,
                "ventana": str(ajustes_obs.get("window") or "")}
    if clave == "imagen":
        return {"archivo": str(ajustes_obs.get("file") or "")}
    if clave == "multimedia":
        return {"archivo": str(ajustes_obs.get("local_file") or ""),
                "repetir": bool(ajustes_obs.get("looping", False))}
    if clave == "texto":
        fuente = ajustes_obs.get("font") or {}
        return {"texto": str(ajustes_obs.get("text") or ""),
                "tamano": int(fuente.get("size", 72)),
                "cara": str(fuente.get("face") or "Arial")}
    return {}


def filtrar_items(items) -> tuple:
    """Los pares (nombre, valor) que se pueden ofrecer: ni apagados ni vacíos."""
    return tuple(
        (item.get("itemName", ""), item.get("itemValue", ""))
        for item in items or ()
        if item.get("itemEnabled", True) is not False
        and item.get("itemValue", ""))


def transformacion_texto(ancho, alto) -> dict:
    """Abajo al centro del vídeo, con la alineación 8 de OBS y sin cuadro."""
    return {"positionX": float(ancho) / 2,
            "positionY": float(alto) * 0.95,
            "alignment": 8,
            "boundsType": "OBS_BOUNDS_NONE"}

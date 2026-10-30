"""Catálogo de componentes del estado de sesión (F2).

Una sola razón para cambiar: qué partes tiene F2 y cómo se llaman en
Preferencias. El formateo vive en estado_sesion, que reexporta estos nombres.
"""

from __future__ import annotations

from bellbird.core import config_predeterminada
from bellbird.core.idioma import N_, _


# Orden canónico de los componentes: estado → contenido → actividad → ajustes.
COMPONENTES: tuple[str, ...] = (
    "estado",
    "titulo",
    "canal",
    "espectadores",
    "tiempo_directo",
    "desfase_directo",
    "mensajes_leidos",
    "aportes",
    "en_cola",
    "voz",
    "lectura_silenciada",
    "overlay",
    "programados",
    "descartados",
    "obs_transmision",
    "obs_grabacion",
    "obs_escena",
    "musica",
    "igualando",
)

# Activos por defecto: derivan de la sección [estado] de la fuente canónica.
# Lo relevante para quien mira un directo viene activado; lo técnico apagado.
def _activos_desde_canonica() -> frozenset[str]:
    sec = config_predeterminada.seccion("estado")
    return frozenset(k for k, v in sec.items()
                     if v.strip().lower() in ("true", "yes", "1", "on"))


ACTIVOS_DEFECTO: frozenset[str] = _activos_desde_canonica()

# Etiquetas para el editor de Preferencias. Se traducen con etiqueta().
ETIQUETAS = {
    # Traductores: rótulo en Preferencias del componente de F2.
    "estado": N_("Estado de conexión y tipo"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "titulo": N_("Título del vídeo o directo"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "canal": N_("Canal o autor"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "espectadores": N_("Espectadores ahora y en total"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "tiempo_directo": N_("Tiempo que lleva el directo"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "desfase_directo": N_("Cuánto por detrás del directo va el reproductor"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "mensajes_leidos": N_("Mensajes leídos"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "aportes": N_("Super Chats / regalos"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "en_cola": N_("Mensajes en cola de lectura"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "voz": N_("Velocidad y volumen de la voz"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "lectura_silenciada": N_("Aviso de lectura silenciada"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "overlay": N_("Panel de chat para transmitir"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "programados": N_("Mensajes automáticos"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "descartados": N_("Mensajes descartados"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "obs_transmision": N_("Estado de la transmisión de OBS"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "obs_grabacion": N_("Estado de la grabación de OBS"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "obs_escena": N_("Escena al aire en OBS"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "musica": N_("Música que suena"),
    # Traductores: rótulo en Preferencias del componente de F2.
    "igualando": N_("Igualación del volumen de la música"),
}


def etiqueta(componente: str) -> str:
    """Rótulo traducido del componente de F2 para Preferencias."""
    texto = ETIQUETAS.get(componente)
    if texto is None:
        return componente
    return _(texto)

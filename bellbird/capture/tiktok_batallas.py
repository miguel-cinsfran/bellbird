"""Lectura de `LinkMicBattleEvent` y `LinkMicArmiesEvent` de TikTokLive.

Único módulo que conoce los eventos de batalla de TikTokLive. Única razón
para cambiar: cómo se leen de la biblioteca. Las etapas se reconocen por
`action`; las armies solo actualizan los puntajes, sin anunciar.
"""

from __future__ import annotations

from TikTokLiveProto.v3.webcast.im import LinkMicBattleBattleAction

from bellbird.capture import batallas
from bellbird.core.tipos_mensaje import TIPO_BATALLA, TIPO_BATALLA_FIN

_ABRIR = int(LinkMicBattleBattleAction.OPEN)
_TERMINAR = int(LinkMicBattleBattleAction.FINISH)
_CORTAR = int(LinkMicBattleBattleAction.LINK_MIC_BATTLE_BATTLE_ACTION_CUT_SHORT)


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _entero(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _accion(evento) -> int:
    try:
        return int(getattr(evento, "action", -1))
    except (TypeError, ValueError):
        return -1


def _anfitriones(evento) -> list[tuple[str, str]]:
    lista = []
    for envoltorio in (getattr(evento, "anchors_info", None) or []):
        valor = getattr(envoltorio, "value", None)
        usuario = getattr(valor, "user", None)
        ident = _texto(getattr(usuario, "user_id", ""))
        if not ident:
            ident = _texto(getattr(envoltorio, "key", ""))
        apodo = _texto(getattr(usuario, "nick_name", ""))
        if ident or apodo:
            lista.append((ident, apodo or ident))
    return lista


def _puntajes(evento) -> dict[str, int]:
    return {_texto(ident): _entero(getattr(resultado, "score", 0))
            for ident, resultado
            in (getattr(evento, "battle_result", None) or {}).items()}


def _puntajes_de_armies(evento) -> dict[str, int]:
    return {_texto(ident): _entero(getattr(armies, "hostscore", 0))
            for ident, armies
            in (getattr(evento, "armies", None) or {}).items()}


def procesar(evento, on_evento) -> None:
    """Lee una batalla y avisa cuando empieza o termina."""
    clave = _texto(getattr(evento, "battle_id", ""))
    if not clave:
        return
    accion = _accion(evento)
    if accion == _ABRIR:
        anfitriones = _anfitriones(evento)
        puntajes = _puntajes(evento)
        if batallas.registro.abrir(clave, anfitriones, puntajes):
            on_evento("", batallas.frase_inicio(anfitriones),
                      TIPO_BATALLA, "", "")
        return
    if accion in (_TERMINAR, _CORTAR):
        anfitriones = (_anfitriones(evento)
                       or batallas.registro.anfitriones_de(clave))
        puntajes = (_puntajes(evento)
                    or batallas.registro.puntajes_de(clave))
        if batallas.registro.cerrar(clave, anfitriones, puntajes):
            on_evento("", batallas.frase_fin(anfitriones, puntajes),
                      TIPO_BATALLA_FIN, "", "")


def procesar_armies(evento) -> None:
    """Actualiza los puntajes de la batalla en curso, sin anunciar."""
    clave = _texto(getattr(evento, "battle_id", ""))
    if not clave:
        return
    puntajes = _puntajes_de_armies(evento)
    if puntajes:
        batallas.registro.actualizar_puntajes(clave, puntajes)


def reiniciar() -> None:
    """Olvida las batallas de la conexión anterior."""
    batallas.registro.reiniciar()

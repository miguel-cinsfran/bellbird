"""Avisos que esperan a que el usuario quede libre, en vez de hablar encima.

Lo que la aplicación avisa por su cuenta (versión nueva, resultado de una
actualización, fin de una descarga) abre una ventana con estado y opciones.
Si en ese momento el usuario está ocupado (chat conectado, transmisión en
curso u otro diálogo modal abierto), la apertura se posterga con
`cuando_libre` hasta que quede libre. Nunca se cambia por voz.
"""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(f"ytchat.{__name__}")


def ocupado(conectado: bool, transmitiendo: bool, modal_abierto: bool) -> bool:
    """Dice si el usuario está ocupado. Solo «todo falso» es libre."""
    return bool(conectado or transmitiendo or modal_abierto)


def esta_ocupado(frame) -> bool:
    """Dice si el frame está ocupado. Cualquier duda cuenta como ocupado."""
    try:
        conectado = bool(getattr(frame, "_conectado", False))
        try:
            transmitiendo = bool(frame._supervisar_transmision("activo"))
        except Exception:
            return True
        modal_abierto = False
        try:
            ventanas = wx.GetTopLevelWindows()
        except Exception:
            return True
        for ventana in ventanas:
            try:
                if ventana is frame:
                    continue
                if not ventana.IsShown():
                    continue
                es_modal = getattr(ventana, "IsModal", None)
                if callable(es_modal):
                    try:
                        if not bool(es_modal()):
                            continue
                    except Exception:
                        return True
                else:
                    continue
                modal_abierto = True
                break
            except Exception:
                return True
        return ocupado(conectado, transmitiendo, modal_abierto)
    except Exception:
        return True


def _frame_destruido(frame) -> bool:
    """Dice si el frame ya no existe (cerrado o destruido)."""
    if frame is None:
        return True
    try:
        if getattr(frame, "_alive", True) is False:
            return True
    except Exception:
        return True
    mostrar = getattr(frame, "IsShown", None)
    if callable(mostrar):
        try:
            mostrar()
        except Exception:
            return True
    return False


def cuando_libre(frame, funcion, *args, intervalo_ms=30000) -> None:
    """Llama a `funcion(*args)` cuando el frame quede libre.

    Si el frame ya no existe no hace nada. Si está ocupado, vuelve a
    probar con `wx.CallLater(intervalo_ms, ...)`. Nunca deja subir una
    excepción.
    """
    try:
        if _frame_destruido(frame):
            return
        if esta_ocupado(frame):
            wx.CallLater(
                intervalo_ms,
                lambda: cuando_libre(frame, funcion, *args,
                                     intervalo_ms=intervalo_ms))
            return
        funcion(*args)
    except Exception as exc:
        logger.warning("aviso diferido: %s", exc)

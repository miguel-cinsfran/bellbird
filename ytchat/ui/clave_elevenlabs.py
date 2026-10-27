"""Consulta en segundo plano la cuenta de ElevenLabs y describe el resultado."""

from __future__ import annotations

import wx

from ytchat.core import diagnostico


def _miles(numero) -> str:
    """Separa los miles con punto, como se escriben los números en español."""
    try:
        return f"{int(numero):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(numero)


def texto_clave_valida(cantidad, usados, limite) -> str:
    return (f"Clave válida. {cantidad} voces. "
            f"Usados {_miles(usados)} de {_miles(limite)} caracteres este mes.")


def comprobar(clave, al_ok, al_fallo):
    def consultar():
        from ytchat.voice import elevenlabs

        try:
            cliente = elevenlabs.ClienteElevenLabs(clave)
            pares = cliente.voces()
            usados, limite = cliente.saldo()
        except Exception as exc:
            wx.CallAfter(al_fallo, str(exc))
            return
        wx.CallAfter(al_ok, pares, usados, limite)

    diagnostico.crear_hilo(consultar, "ComprobarClaveEleven").start()

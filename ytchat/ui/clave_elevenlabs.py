"""Consulta en segundo plano la cuenta de ElevenLabs y describe el resultado."""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import _, ngettext


def _miles(numero) -> str:
    """Separa los miles con punto, como se escriben los números en español."""
    try:
        return f"{int(numero):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(numero)


def texto_clave_valida(cantidad, usados, limite) -> str:
    try:
        cuantas = int(cantidad)
    except (TypeError, ValueError):
        cuantas = 1
    # Traductores: resultado de comprobar la clave; {voces} cuántas voces trae,
    # {usados} y {limite} los caracteres del mes con miles con punto.
    return ngettext("Clave válida. {voces} voz. Usados {usados} "
                    "de {limite} caracteres este mes.",
                    "Clave válida. {voces} voces. Usados {usados} "
                    "de {limite} caracteres este mes.",
                    cuantas).format(voces=cantidad, usados=_miles(usados), limite=_miles(limite))


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

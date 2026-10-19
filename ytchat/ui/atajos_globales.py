"""Atajos de música que funcionan en cualquier programa.

Mientras están activos, las combinaciones dejan de llegar a los demás
programas (por eso la casilla viene apagada de fábrica). Lo puro
(`combinacion_windows`) no toca wx; el registro vive en `AtajosGlobales`,
que recibe la ventana.
"""

from __future__ import annotations

import wx

from ytchat.ui.atajos_captura import atajo_legible

# Acciones de música con atajo global, en orden fijo: el índice da el id.
# Abrir la ventana de música no es global: Ctrl+Mayús+M solo vale dentro.
ACCIONES = (
    "musica_play",
    "musica_siguiente",
    "musica_anterior",
    "musica_vol_mas",
    "musica_vol_menos",
    "musica_que_suena",
)

# Base de los ids propios para `RegisterHotKey`, lejos de otros usos.
BASE_IDS = 0xB000

# Teclas con nombre del área Ctrl+Alt a su código virtual de Windows.
_TECLAS_VK = {
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "space": 0x20,
}


def combinacion_windows(texto: str | None) -> tuple[int, int] | None:
    """Traduce un atajo del área Ctrl+Alt a lo que pide `RegisterHotKey`.

    Devuelve `(modificadores, código virtual)`: los modificadores son
    `wx.MOD_*` (con los mismos valores que los `MOD_*` de Windows:
    `MOD_ALT` 1, `MOD_CONTROL` 2) y el código es el VK de Windows
    (flechas 0x25 a 0x28, Espacio 0x20, letras y dígitos su `ord` en
    mayúscula). Cualquier otra cosa da None.
    """
    partes = (texto or "").strip().lower().replace(" ", "").split("+")
    if len(partes) != 3:
        return None
    primero, segundo, tecla = partes
    if not ((primero == "ctrl" and segundo == "alt")
            or (primero == "alt" and segundo == "ctrl")):
        return None
    if tecla in _TECLAS_VK:
        codigo = _TECLAS_VK[tecla]
    elif len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
        codigo = ord(tecla.upper())
    else:
        return None
    return (wx.MOD_CONTROL | wx.MOD_ALT, codigo)


class AtajosGlobales:
    """Registra los atajos de música en todo el sistema con una ventana.

    `acciones` es un dict `{acción: función}` con lo mismo que llama el
    menú de música. Nunca lanza: registrar o soltar puede fallar (otro
    programa tiene la combinación, la ventana se cerró) y se informa con
    el valor devuelto, no con excepciones.
    """

    def __init__(self, ventana, acciones: dict) -> None:
        self._ventana = ventana
        self._acciones = dict(acciones)
        self._registrados: dict[str, tuple[int, object]] = {}

    @property
    def activos(self) -> bool:
        """Si hay al menos un atajo registrado."""
        return bool(self._registrados)

    def activar(self, atajos: dict[str, str]) -> list[str]:
        """Registra los atajos traducibles y devuelve los que fallaron.

        Solo mira las acciones de música conocidas: cada una con un atajo
        que se pueda traducir pide su id propio a la ventana. Lo que otro
        programa ya tiene vuelve como texto legible. Llamarla de nuevo
        primero desactiva todo.
        """
        self.desactivar()
        fallidos: list[str] = []
        for indice, accion in enumerate(ACCIONES):
            funcion = self._acciones.get(accion)
            if funcion is None:
                continue
            valor = atajos.get(accion)
            valor = getattr(valor, "texto", valor)
            if not valor:
                continue
            combo = combinacion_windows(valor)
            if combo is None:
                continue
            mods, vk = combo
            ident = BASE_IDS + indice
            try:
                registrado = self._ventana.RegisterHotKey(ident, mods, vk)
            except Exception:
                registrado = False
            if not registrado:
                fallidos.append(atajo_legible(valor))
                continue
            manejador = self._enlazar(ident, funcion)
            self._registrados[accion] = (ident, manejador)
        return fallidos

    def _enlazar(self, ident: int, funcion) -> object:
        """Enlaza `EVT_HOTKEY` a la acción, que corre con `CallAfter`."""
        def al_pulsar(_evento, _funcion=funcion) -> None:
            wx.CallAfter(_funcion)

        self._ventana.Bind(wx.EVT_HOTKEY, al_pulsar, id=ident)
        return al_pulsar

    def desactivar(self) -> None:
        """Suelta todos los registrados. Nunca lanza; dos veces no falla."""
        registrados, self._registrados = self._registrados, {}
        for _accion, (ident, _manejador) in registrados.items():
            try:
                self._ventana.Unbind(wx.EVT_HOTKEY, id=ident)
            except Exception:
                pass
            try:
                self._ventana.UnregisterHotKey(ident)
            except Exception:
                pass

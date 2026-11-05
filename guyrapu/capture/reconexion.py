"""Piezas puras de la reconexión del chat de YouTube.

No importa wx ni pytchat: la espera creciente y el filtro de mensajes se
prueban sin red y sin ventanas.
"""

from collections import deque
from datetime import datetime, timezone

_ESCALONES = (1, 2, 5, 10)
_MEMORIA = 2000


def espera_reconexion(intento, tope) -> int:
    """Segundos de espera antes del reintento número `intento`.

    Los primeros cuatro reintentos esperan 1, 2, 5 y 10 segundos; desde el
    quinto se usa el tope. El tope manda siempre y nunca baja de 1.
    """
    try:
        tope = int(tope)
    except (TypeError, ValueError):
        tope = 0
    if tope < 1:
        return 1
    if intento < 1:
        escalon = 1
    elif intento <= len(_ESCALONES):
        escalon = _ESCALONES[intento - 1]
    else:
        escalon = tope
    return max(1, min(tope, escalon))


class FiltroNuevos:
    """Filtro de mensajes nuevos y sin repetir para toda una sesión.

    La hora de corte se fija la primera vez que se arranca y no se mueve: así
    lo escrito durante un corte se lee al reconectar, y lo anterior al primer
    contacto no. Los identificadores vistos se recuerdan en una ventana
    acotada para no crecer sin límite.
    """

    def __init__(self, memoria=_MEMORIA):
        self._corte = None
        self._vistos = deque(maxlen=memoria)
        self._ids = set()

    def arrancar(self):
        if self._corte is None:
            self._corte = datetime.now(timezone.utc)

    def es_nuevo(self, item) -> bool:
        if not self._posterior(item):
            return False
        ident = getattr(item, "id", None)
        if ident is None or ident == "":
            return True
        if ident in self._ids:
            return False
        self._recordar(ident)
        return True

    def _posterior(self, item) -> bool:
        try:
            ts = item.timestamp
            if isinstance(ts, (int, float)):
                ts = datetime.fromtimestamp(ts / 1_000, tz=timezone.utc)
            elif isinstance(ts, datetime):
                if ts.tzinfo is None:
                    ts = ts.astimezone(timezone.utc)
            else:
                return True
            return ts >= self._corte
        except Exception:
            return True

    def _recordar(self, ident):
        if len(self._vistos) == self._vistos.maxlen:
            self._ids.discard(self._vistos[0])
        self._vistos.append(ident)
        self._ids.add(ident)

"""Cola de la voz con mensajes normales y adelantados.

La voz toma primero el pedido adelantado más viejo y después el normal más
viejo. El descarte de la cola hace lo contrario: saca normales antes que
adelantados, para que llenarla nunca tire un pedido reciente.
"""

from __future__ import annotations

import queue
from collections import deque


class ColaTTS(queue.Queue):
    """Cola FIFO con un depósito aparte para lo que debe sonar antes."""

    def _init(self, maxsize):
        self._normales = deque()
        self._adelantados = deque()

    def _qsize(self):
        return len(self._normales) + len(self._adelantados)

    def _put(self, item):
        self._normales.append(item)

    def _get(self):
        if self._adelantados:
            return self._adelantados.popleft()
        return self._normales.popleft()

    def adelantar(self, item):
        with self.not_empty:
            self._adelantados.append(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def get_nowait(self):
        with self.mutex:
            if self._normales:
                item = self._normales.popleft()
            elif self._adelantados:
                item = self._adelantados.popleft()
            else:
                raise queue.Empty
            self.not_full.notify()
            return item

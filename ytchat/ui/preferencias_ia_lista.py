"""Actualización de la lista de modelos de la página Inteligencia artificial.

Dueña del botón, del hilo que descarga el catálogo, del sondeo de la clave y
de los anuncios del final. La página le entrega el proveedor elegido y una
función que rehace la lista con la muestra y las marcas nuevas.
"""

from __future__ import annotations

from datetime import datetime

import wx

from ytchat.ai import catalogo
from ytchat.ai import claves
from ytchat.ai import consulta
from ytchat.ai import envio_ia
from ytchat.ai import opciones_ia
from ytchat.ai import protocolos
from ytchat.ai import sondeo_gratis
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.ui.gui import anunciar
from ytchat.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


class ActualizacionModelosIA:
    """El botón de actualizar, su hilo, su sondeo y sus anuncios."""

    def __init__(self, boton, proveedor_elegido, al_actualizar):
        self._boton = boton
        self._proveedor_elegido = proveedor_elegido
        self._al_actualizar = al_actualizar
        boton.Bind(wx.EVT_BUTTON, self._al_pulsar)
        boton.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)

    def _al_pulsar(self, _event):
        self._boton.Disable()
        anunciar(opciones_ia.TEXTO_ACTUALIZANDO)
        proveedor = self._proveedor_elegido()
        diagnostico.crear_hilo(
            lambda: self._en_hilo(proveedor), "ActualizarModelosIA").start()

    def _al_destruir(self, event):
        self._boton = None
        event.Skip()

    def _en_hilo(self, proveedor):
        # La red nunca corre en el hilo de la interfaz.
        try:
            muestra = catalogo.descargar(
                paths.catalogo_ia(), datetime.now().isoformat())
        except Exception as exc:
            logger.warning("IA: no se pudo actualizar el catálogo: %s", exc)
            wx.CallAfter(self.recibir, None)
            return
        resultados = self._sondear(proveedor, muestra)
        wx.CallAfter(self.recibir, muestra, resultados, proveedor)

    def _sondear(self, proveedor, muestra):
        if not proveedor.gratis_por_clave:
            return None
        try:
            clave = claves.leer(proveedor.id) or ""
        except Exception as exc:
            logger.warning("IA: sin clave guardada para sondear: %s", exc)
            return None
        if not clave:
            return None
        resultados = sondeo_gratis.sondear(
            proveedor, muestra, clave, envio_ia.enviar, 20)
        sondeo_gratis.guardar(
            paths.gratis_ia(), proveedor.id,
            sondeo_gratis.marcas(resultados), datetime.now().isoformat())
        return resultados

    def recibir(self, muestra, resultados=None, proveedor=None):
        if not self._boton:   # la página pudo cerrarse mientras trabajaba
            return
        self._boton.Enable()
        if muestra is None:
            _snd.reproducir("ia_error")
            anunciar(opciones_ia.TEXTO_LISTA_FALLO)
            return
        actual = proveedor or self._proveedor_elegido()
        marcas = self._leer_marcas(self._proveedor_elegido())
        n = self._al_actualizar(muestra, marcas, actual)
        if n is None:
            return
        if resultados is not None:
            self._anunciar_sondeo(actual, muestra, resultados)
            return
        _snd.reproducir("ia_respuesta")
        if actual.id_catalogo is None:
            anunciar(opciones_ia.TEXTO_LISTA_ACTUALIZADA_SIN_PROVEEDOR)
        else:
            anunciar(opciones_ia.TEXTO_LISTA_ACTUALIZADA.format(
                n=n, proveedor=actual.nombre))

    def _leer_marcas(self, proveedor):
        return sondeo_gratis.leer(paths.gratis_ia(), proveedor.id)

    def _anunciar_sondeo(self, proveedor, muestra, resultados):
        if sondeo_gratis.CLAVE_MALA in resultados.values():
            _snd.reproducir("ia_error")
            anunciar(consulta.texto_de_error(
                protocolos.ErrorIA(protocolos.CLAVE_RECHAZADA)))
            return
        n = len(catalogo.modelos(muestra, proveedor.id_catalogo))
        _snd.reproducir("ia_respuesta")
        anunciar(opciones_ia.resumen_sondeo(resultados, n, proveedor.nombre))

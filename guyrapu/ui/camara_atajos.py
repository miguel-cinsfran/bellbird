"""Qué hacen los atajos de cámara y dónde valen.

Alt+F3 oculta o muestra la cámara elegida en la escena al aire de OBS. Los
tres atajos de cámara (los dos del encuadre y el de la cámara) pueden valer
en cualquier programa si la casilla de Preferencias lo pide.
"""

from __future__ import annotations

import wx

from guyrapu.core import config, diagnostico
from guyrapu.core.idioma import N_, _
from guyrapu.music import anuncios
from guyrapu.obs import obs_activacion, obs_camara, obs_cliente
from guyrapu.obs.obs_camara import CamaraNoEncontrada
from guyrapu.ui import atajos_globales, encuadre_camara, ia_agregar_captura
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.atajos_globales import combinacion_funcion
from guyrapu.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)

# Traductores: respuesta al atajo que oculta la cámara.
TEXTO_CAMARA_OCULTA = N_("Cámara oculta")
# Traductores: respuesta al atajo que vuelve a mostrar la cámara.
TEXTO_CAMARA_VISIBLE = N_("Cámara visible")
# Traductores: confirmación de que los atajos de cámara valen fuera de la app.
TEXTO_ACTIVOS = N_("Atajos de cámara en cualquier aplicación")
# Traductores: confirmación de que los atajos de cámara valen solo en la app.
_TEXTO_SOLO = N_("Atajos de cámara solo en {app}")

# Acciones de cámara con atajo global, en orden: el índice da el id.
ORDEN = ("anunciar_encuadre", "avisos_encuadre", "camara_visible")

# Base de los ids propios para `RegisterHotKey`, lejos de los de música.
BASE_IDS = 0xB200


def alternar_camara(frame) -> None:
    """Oculta o muestra la cámara de la escena al aire, en un hilo."""
    try:
        diagnostico.crear_hilo(
            lambda: _alternar_en_hilo(frame), "AlternarCamara").start()
    except Exception:
        logger.exception("No se pudo lanzar el cambio de cámara")


def _alternar_en_hilo(frame) -> None:
    if not obs_activacion.obs_esta_en_ejecucion():
        anunciar(_(ia_agregar_captura.TEXTO_OBS_CERRADO))
        return
    cliente = None
    cambio = False
    try:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        fuente = str(frame._config.get("camara_fuente", "") or "")
        visible = obs_camara.alternar_camara(cliente, fuente)
        cambio = True
        texto = _(TEXTO_CAMARA_VISIBLE if visible else TEXTO_CAMARA_OCULTA)
    except CamaraNoEncontrada as fallo:
        texto = str(fallo)
    except Exception as fallo:
        texto = obs_cliente.mensaje_de_fallo_obs(fallo)
    finally:
        if cliente is not None:
            try:
                cliente.cerrar()
            except Exception as fallo:
                logger.warning("CamaraAtajos: no se pudo cerrar OBS: %s",
                               fallo)
    anunciar(texto)
    if cambio:
        encuadre_camara.olvidar_camara(frame)


class CamaraAtajos:
    """Los atajos de cámara dentro de la app o en todo el sistema.

    `frame` es la ventana principal: de ella salen los atajos configurados,
    la configuración y la ventana que registra las combinaciones. Nunca
    lanza: registrar o soltar puede fallar y se informa con el anuncio.
    """

    def __init__(self, frame) -> None:
        self._ventana = frame
        self._config = frame._config
        self._acciones = {
            "anunciar_encuadre":
                lambda: encuadre_camara.anunciar_encuadre(frame),
            "avisos_encuadre":
                lambda: encuadre_camara.alternar_avisos(frame),
            "camara_visible": lambda: alternar_camara(frame),
        }
        self._globales = atajos_globales.AtajosGlobales(
            frame, self._acciones, orden=ORDEN, base_ids=BASE_IDS,
            traducir=combinacion_funcion)
        self._globales_atajos = None
        if bool(self._config.get("camara_atajos_globales", False)):
            # Después de que la ventana exista: el registro es del sistema
            # y pide el bucle de eventos.
            try:
                wx.CallAfter(self.activar_arranque)
            except Exception:
                logger.debug("No se pudieron activar los atajos de cámara")

    def _textos(self) -> dict:
        """Los atajos efectivos de cámara, acción → texto guardado."""
        atajos = getattr(self._ventana, "_atajos", None) or {}
        textos = {}
        for accion in ORDEN:
            atajo = atajos.get(accion)
            texto = getattr(atajo, "texto", atajo)
            if texto:
                textos[accion] = texto
        return textos

    def activar_arranque(self) -> None:
        """Activa los globales al arrancar: calla salvo que algo falle."""
        try:
            textos = self._textos()
            fallidos = self._globales.activar(textos)
        except Exception:
            logger.exception("No se pudieron activar los atajos de cámara")
            return
        self._globales_atajos = textos
        if fallidos:
            self._avisar(anuncios.aviso_atajos_globales_fallo(fallidos))

    def aplicar_preferencias(self) -> None:
        """Activa o desactiva los globales según la preferencia.

        Al activar desde Preferencias se anuncia (y el fallo, con el tono de
        ocupado); al desactivar, también. Nunca lanza.
        """
        try:
            if bool(self._config.get("camara_atajos_globales", False)):
                textos = self._textos()
                if self._globales.activos and textos == self._globales_atajos:
                    return
                fallidos = self._globales.activar(textos)
                self._globales_atajos = dict(textos)
                if fallidos:
                    self._avisar(anuncios.aviso_atajos_globales_fallo(fallidos))
                else:
                    self._avisar(anuncios.Aviso(_(TEXTO_ACTIVOS)))
            elif self._globales.activos:
                self._globales.desactivar()
                self._globales_atajos = None
                self._avisar(anuncios.Aviso(
                    _(_TEXTO_SOLO).format(app=config.APP_NAME)))
        except Exception:
            logger.exception("No se pudieron aplicar los atajos de cámara")

    def _avisar(self, aviso) -> None:
        if aviso is None:
            return
        if aviso.sonido:
            try:
                _snd.reproducir(aviso.sonido)
            except Exception:
                logger.debug("No se pudo reproducir el sonido %s", aviso.sonido)
        if aviso.texto:
            anunciar(aviso.texto)

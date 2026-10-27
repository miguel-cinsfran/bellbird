"""Consulta rápida a la IA sobre la escena al aire, sin abrir ventanas.

Ctrl+Mayús+F2 captura la escena al aire de OBS, la envía con la
instrucción de Preferencias y anuncia la respuesta. Al terminar, la
conversación queda guardada en la instancia: la ventana Preguntar a la
IA la toma con `tomar_conversacion` y arranca con ella.
"""

from __future__ import annotations

import weakref
from datetime import datetime

import wx

from ytchat.ai import ajustes_ia
from ytchat.ai import catalogo
from ytchat.ai import claves
from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import envio_ia
from ytchat.ai import proveedores
from ytchat.ai import ventana_ia
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.obs import obs_activacion
from ytchat.obs import obs_captura_ia
from ytchat.obs import obs_cliente
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.ui import ia_agregar_captura
from ytchat.ui import ia_privacidad
from ytchat.ui import ia_ventana
from ytchat.ui.accesibilidad import anunciar
from ytchat.voice.sound_player import reproducir

logger = diagnostico.obtener_logger(__name__)

TEXTO_EN_CURSO = "Ya hay una consulta rápida en curso."


class ConsultaRapida:
    """Una consulta rápida por ventana principal, con su estado.

    Guarda la conversación que deja para la ventana Preguntar a la IA.
    Al marco solo lo usa como padre: nunca lee sus atributos.
    """

    def __init__(self, frame):
        try:
            self._marco = weakref.ref(frame)
        except TypeError:
            self._marco = lambda: frame
        self._en_curso = False
        self._decir_analizando = True
        self._guardada = None
        self._temporizador = wx.Timer(frame)
        frame.Bind(wx.EVT_TIMER, self._al_temporizador, self._temporizador)
        self._melodia = wx.Timer(frame)
        frame.Bind(wx.EVT_TIMER, self._al_temporizador_melodia, self._melodia)

    @property
    def _frame(self):
        try:
            marco = self._marco()
        except Exception as fallo:
            logger.warning("ConsultaRapida: sin marco: %s", fallo)
            return None
        if marco is None:
            return None
        try:
            borrandose = marco.IsBeingDeleted()
        except Exception as fallo:
            logger.warning("ConsultaRapida: sin estado del marco: %s", fallo)
            borrandose = False
        return None if borrandose else marco

    def consultar(self) -> None:
        marco = self._frame
        if marco is None:
            return
        if self._en_curso:
            anunciar(TEXTO_EN_CURSO)
            return
        if not obs_activacion.obs_esta_en_ejecucion():
            anunciar(ia_agregar_captura.TEXTO_OBS_CERRADO)
            reproducir("ia_error")
            return
        self._en_curso = True
        diagnostico.crear_hilo(
            self._capturar_en_hilo, "ConsultaRapidaCapturar").start()

    def tomar_conversacion(self):
        tomada = self._guardada
        self._guardada = None
        return tomada

    def _capturar_en_hilo(self) -> None:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        try:
            cliente.conectar()
            opcion = obs_captura_ia.opciones(cliente)[0]
            captura = obs_captura_ia.capturar(cliente, opcion)
        except obs_captura_ia.CapturaFallida as fallo:
            wx.CallAfter(self._vuelta_fallo, str(fallo))
            return
        except Exception as fallo:
            wx.CallAfter(self._vuelta_fallo,
                         obs_cliente.mensaje_de_fallo_obs(fallo))
            return
        finally:
            try:
                cliente.cerrar()
            except Exception as fallo:
                logger.warning("ConsultaRapida: no se pudo cerrar OBS: %s",
                               fallo)
        wx.CallAfter(self._vuelta_captura, opcion, captura,
                     self._descripcion_escena())

    def _descripcion_escena(self) -> str:
        gestor = GestorPanelObs()
        try:
            gestor.conectar()
            return gestor.descripcion_escena()
        except Exception as fallo:
            logger.warning("ConsultaRapida: sin descripción: %s", fallo)
            return ""
        finally:
            try:
                gestor.cerrar()
            except Exception as fallo:
                logger.warning("ConsultaRapida: no se pudo cerrar: %s",
                               fallo)

    def _vuelta_fallo(self, mensaje) -> None:
        if not self._frame:
            return
        self._en_curso = False
        anunciar(mensaje)
        reproducir("ia_error")

    def _avisar_negra(self, opcion, captura) -> None:
        self._en_curso = False
        anunciar(ia_agregar_captura.texto_negra(
            opcion.etiqueta, captura.motivo, captura.fuente_motivo))
        reproducir("ia_imagen_negra")

    def _vuelta_captura(self, opcion, captura, descripcion) -> None:
        marco = self._frame
        if not marco:
            return
        if captura.negra is True:
            self._avisar_negra(opcion, captura)
            return
        charla = conversacion.Conversacion()
        charla.agregar_captura(captura.jpeg, opcion.fuente,
                               ventana_ia.hora_de(datetime.now()))
        ajustes = ajustes_ia.leer(paths.config_ini())
        self._decir_analizando = ajustes.decir_analizando
        muestra = catalogo.cargar(paths.catalogo_ia(),
                                  paths.catalogo_ia_empaquetado())
        try:
            clave = claves.leer(ajustes.proveedor)
        except OSError as fallo:
            logger.warning("ConsultaRapida: sin clave: %s", fallo)
            clave = None
        try:
            preparada = consulta.preparar(charla, "", ajustes, muestra,
                                          clave, descripcion)
        except (conversacion.SinCaptura, conversacion.SinTexto,
                consulta.FaltaConfiguracion) as fallo:
            self._en_curso = False
            anunciar(consulta.texto_de_error(fallo))
            reproducir("ia_error")
            return
        proveedor = proveedores.por_id(ajustes.proveedor)
        if proveedor is None:
            proveedor = proveedores.PROVEEDORES[0]
        if not ia_privacidad.confirmar(marco, ajustes, proveedor.nombre):
            self._en_curso = False
            return
        reproducir("ia_enviada")
        self._temporizador.Start(ia_ventana.INTERVALO_AVISO_MS)
        self._melodia.Start(ia_ventana.INTERVALO_MELODIA_MS)
        diagnostico.crear_hilo(self._enviar_en_hilo, "ConsultaRapidaEnviar",
                               args=(charla, preparada, clave,
                                     descripcion)).start()

    def _enviar_en_hilo(self, charla, preparada, clave,
                        descripcion) -> None:
        try:
            respuesta = envio_ia.enviar(preparada.pedido, clave,
                                        preparada.tiempo_espera)
        except Exception as fallo:
            wx.CallAfter(self._vuelta_fallo_envio, fallo)
            return
        wx.CallAfter(self._vuelta_envio, charla, preparada, clave,
                     descripcion, respuesta)

    def _vuelta_envio(self, charla, preparada, clave, descripcion,
                      respuesta) -> None:
        if not self._frame:
            return
        self._frenar_avisos()
        self._en_curso = False
        try:
            texto = consulta.consultar(charla, preparada, clave,
                                       enviar=lambda *args: respuesta)
        except Exception as fallo:
            self._avisar_fallo(fallo)
            return
        self._guardada = (charla, descripcion)
        reproducir("ia_respuesta")
        anunciar(texto)

    def _vuelta_fallo_envio(self, fallo) -> None:
        if not self._frame:
            return
        self._frenar_avisos()
        self._en_curso = False
        self._avisar_fallo(fallo)

    def _avisar_fallo(self, fallo) -> None:
        try:
            detalle = fallo.detalle
        except AttributeError:
            detalle = str(fallo)
        logger.warning("ConsultaRapida: falló la consulta: %s", detalle)
        reproducir("ia_error")
        anunciar(consulta.texto_de_error(fallo))

    def _al_temporizador(self, _event) -> None:
        if self._decir_analizando:
            anunciar(ventana_ia.TEXTO_ANALIZANDO, urgente=False)

    def _al_temporizador_melodia(self, _event) -> None:
        reproducir("ia_analizando")

    def _frenar_avisos(self) -> None:
        try:
            self._temporizador.Stop()
        except Exception as fallo:
            logger.warning("ConsultaRapida: no se pudo frenar el aviso: %s",
                           fallo)
        try:
            self._melodia.Stop()
        except Exception as fallo:
            logger.warning("ConsultaRapida: no se pudo frenar la melodía: %s",
                           fallo)


_INSTANCIAS: dict = {}


def _instancia_para(frame):
    instancia = _INSTANCIAS.get(id(frame))
    if instancia is not None and instancia._frame is frame:
        return instancia
    instancia = ConsultaRapida(frame)
    _INSTANCIAS[id(frame)] = instancia
    return instancia


def consultar(frame) -> None:
    """Pregunta por la escena al aire sin abrir ninguna ventana."""
    _instancia_para(frame).consultar()


def tomar_conversacion(frame):
    """La conversación guardada y su descripción, olvidadas al tomarlas."""
    instancia = _INSTANCIAS.get(id(frame))
    if instancia is None or instancia._frame is not frame:
        return None
    return instancia.tomar_conversacion()

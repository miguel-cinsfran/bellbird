"""Subventana para elegir qué capturar de OBS y preguntarle a la IA.

Modal y chica como `gui_elegir_destino`: lista «Capturar de» con lo que
ofrece `obs_captura_ia.opciones`, vista previa solo para resto visual
y botones Capturar y Cancelar. El cliente llega ya conectado.
"""

from __future__ import annotations

import io
import threading

import wx

from ytchat.core import diagnostico
from ytchat.obs import obs_activacion
from ytchat.obs import obs_captura_ia
from ytchat.obs import obs_cliente
from ytchat.ui.gui import anunciar, nombre_accesible
from ytchat.voice.sound_player import reproducir


logger = diagnostico.obtener_logger(__name__)

TEXTO_CARGANDO = "Cargando las fuentes de OBS…"
TEXTO_OBS_CERRADO = "OBS no está abierto."

ANCHO_VISTA = 320
ALTO_VISTA = 180


def texto_negra(etiqueta) -> str:
    """Aviso cuando la captura sale negra, en palabras para el usuario."""
    return (f"La captura de {etiqueta} salió negra y no se agregó. "
            "Si usas la cortina de pantalla de NVDA, cambia en OBS "
            "el método de captura de esa fuente a Windows 10.")


class DialogoAgregarCaptura(wx.Dialog):
    def __init__(self, padre, cliente):
        super().__init__(padre, title="Agregar captura",
                         name="DialogoAgregarCaptura")
        self._cliente = cliente
        self._cerrojo = threading.Lock()
        self._cerrado = False
        self._opciones = ()
        self._resultado = None
        self._generacion_vista = 0

        vs = wx.BoxSizer(wx.VERTICAL)
        self.rotulo_fuente = wx.StaticText(self, label="&Capturar de:")
        vs.Add(self.rotulo_fuente, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_fuente = wx.Choice(
            self, choices=[TEXTO_CARGANDO], name="Capturar de")
        self.cho_fuente.SetSelection(0)
        nombre_accesible(self.cho_fuente, "Capturar de")
        vs.Add(self.cho_fuente, 0, wx.EXPAND | wx.ALL, 10)

        self.bmp_vista = wx.StaticBitmap(
            self, bitmap=wx.NullBitmap, size=(ANCHO_VISTA, ALTO_VISTA),
            name="Vista previa")
        self.bmp_vista.SetMinSize((ANCHO_VISTA, ALTO_VISTA))
        nombre_accesible(self.bmp_vista, "Vista previa")
        vs.Add(self.bmp_vista, 0, wx.LEFT | wx.RIGHT, 10)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_capturar = wx.Button(self, wx.ID_OK, "Captu&rar")
        self.btn_capturar.SetDefault()
        self.btn_capturar.SetName("Capturar")
        self.btn_capturar.Disable()
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, "Ca&ncelar")
        self.btn_cancelar.SetName("Cancelar")
        fila.Add(self.btn_capturar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizerAndFit(vs)
        self._temporizador = wx.Timer(self)
        self.cho_fuente.Bind(wx.EVT_CHOICE, self._al_elegir)
        self.btn_capturar.Bind(wx.EVT_BUTTON, self._al_capturar)
        self.Bind(wx.EVT_TIMER, self._al_temporizador, self._temporizador)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.Bind(wx.EVT_CLOSE, self._al_cerrar)
        self.cho_fuente.SetFocus()
        self._cargar_opciones()

    @property
    def resultado(self):
        return self._resultado

    def _terminar(self, codigo) -> None:
        self._cerrado = True
        try:
            self._temporizador.Stop()
        except Exception as error:
            logger.warning("AgregarCaptura: no se pudo frenar el aviso: %s",
                           error)
        self.EndModal(codigo)

    def _al_cerrar(self, event) -> None:
        if self._cerrado:
            event.Skip()
            return
        self._terminar(wx.ID_CANCEL)

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._terminar(wx.ID_CANCEL)
            return
        event.Skip()

    def _opcion_elegida(self):
        indice = self.cho_fuente.GetSelection()
        if 0 <= indice < len(self._opciones):
            return self._opciones[indice]
        return None

    def _cargar_opciones(self) -> None:
        def _trabajo():
            try:
                with self._cerrojo:
                    opciones = obs_captura_ia.opciones(self._cliente)
            except Exception as error:
                logger.warning("AgregarCaptura: no se pudo listar: %s", error)
                wx.CallAfter(self._opciones_fallaron, error)
                return
            wx.CallAfter(self._opciones_listas, opciones)

        diagnostico.crear_hilo(_trabajo, "AgregarCapturaOpciones").start()

    def _opciones_listas(self, opciones) -> None:
        if self._cerrado:
            return
        self._opciones = tuple(opciones)
        self.cho_fuente.Clear()
        for opcion in self._opciones:
            self.cho_fuente.Append(opcion.etiqueta)
        if self._opciones:
            self.cho_fuente.SetSelection(0)
        self.btn_capturar.Enable()
        self._programar_vista_previa()

    def _opciones_fallaron(self, error) -> None:
        if self._cerrado:
            return
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))
        reproducir("ia_error")
        self._terminar(wx.ID_CANCEL)

    def _al_elegir(self, _event) -> None:
        self._programar_vista_previa()

    def _programar_vista_previa(self) -> None:
        if self._cerrado or not self._opciones:
            return
        self._generacion_vista += 1
        self._temporizador.Stop()
        self._temporizador.Start(400, True)

    def _al_temporizador(self, _event) -> None:
        opcion = self._opcion_elegida()
        if opcion is None or self._cerrado:
            return
        generacion = self._generacion_vista

        def _trabajo():
            try:
                with self._cerrojo:
                    jpeg = obs_captura_ia.vista_previa(self._cliente, opcion)
            except Exception as error:
                logger.warning("AgregarCaptura: sin vista previa: %s", error)
                wx.CallAfter(self._vista_fallida, generacion)
                return
            wx.CallAfter(self._vista_lista, generacion, jpeg)

        diagnostico.crear_hilo(_trabajo, "AgregarCapturaVista").start()

    def _vista_lista(self, generacion, jpeg) -> None:
        if self._cerrado or generacion != self._generacion_vista:
            return
        try:
            imagen = wx.Image(io.BytesIO(jpeg))
        except Exception as error:
            logger.warning("AgregarCaptura: vista previa rota: %s", error)
            return
        ancho = imagen.GetWidth()
        alto = imagen.GetHeight()
        if ancho <= 0 or alto <= 0:
            return
        factor = min(ANCHO_VISTA / ancho, ALTO_VISTA / alto)
        if factor < 1:
            nuevo = (max(1, int(ancho * factor)),
                     max(1, int(alto * factor)))
            imagen = imagen.Scale(nuevo[0], nuevo[1], wx.IMAGE_QUALITY_HIGH)
        try:
            self.bmp_vista.SetBitmap(wx.Bitmap(imagen))
        except Exception as error:
            logger.warning("AgregarCaptura: no se pudo mostrar: %s", error)

    def _vista_fallida(self, generacion) -> None:
        if self._cerrado or generacion != self._generacion_vista:
            return
        try:
            self.bmp_vista.SetBitmap(wx.NullBitmap)
        except Exception as error:
            logger.warning("AgregarCaptura: no se pudo vaciar: %s", error)

    def _al_capturar(self, _event) -> None:
        opcion = self._opcion_elegida()
        if opcion is None:
            return
        self.btn_capturar.Disable()

        def _trabajo():
            try:
                with self._cerrojo:
                    captura = obs_captura_ia.capturar(self._cliente, opcion)
            except obs_captura_ia.CapturaFallida as error:
                wx.CallAfter(self._captura_fallida, str(error))
                return
            except Exception as error:
                logger.warning("AgregarCaptura: fallo al capturar: %s", error)
                wx.CallAfter(self._captura_fallida,
                             obs_cliente.mensaje_de_fallo_obs(error))
                return
            wx.CallAfter(self._captura_lista, opcion, captura)

        diagnostico.crear_hilo(_trabajo, "AgregarCapturaCapturar").start()

    def _captura_fallida(self, mensaje) -> None:
        if self._cerrado:
            return
        anunciar(mensaje)
        reproducir("ia_error")
        self.btn_capturar.Enable()
        self.cho_fuente.SetFocus()

    def _captura_lista(self, opcion, captura) -> None:
        if self._cerrado:
            return
        if captura.negra is True:
            anunciar(texto_negra(opcion.etiqueta))
            reproducir("ia_error")
            self.btn_capturar.Enable()
            self.cho_fuente.SetFocus()
            return
        self._resultado = (opcion.fuente, captura)
        self._terminar(wx.ID_OK)


def _cerrar(cliente) -> None:
    try:
        cliente.cerrar()
    except Exception as fallo:
        logger.warning("AgregarCaptura: no se pudo cerrar: %s", fallo)


def _mostrar(padre, cliente, al_terminar) -> None:
    dialogo = DialogoAgregarCaptura(padre, cliente)
    try:
        if dialogo.ShowModal() == wx.ID_OK and dialogo.resultado:
            al_terminar(dialogo.resultado)
        else:
            al_terminar(None)
    finally:
        try:
            dialogo.Destroy()
        except Exception as fallo:
            logger.warning("AgregarCaptura: no se pudo destruir: %s", fallo)
        _cerrar(cliente)


def pedir_captura(padre, al_terminar) -> None:
    """Pide una captura de OBS sin bloquear. Llama a `al_terminar`.

    El resultado es `(fuente, captura)` o None, siempre en el hilo de
    la interfaz. Sin OBS abierto o sin conexión, avisa y termina con
    None sin abrir nada.
    """
    if not obs_activacion.obs_esta_en_ejecucion():
        anunciar(TEXTO_OBS_CERRADO)
        reproducir("ia_error")
        al_terminar(None)
        return
    cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())

    def _conexion_fallida(error) -> None:
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))
        reproducir("ia_error")
        _cerrar(cliente)
        al_terminar(None)

    def _conexion_lista() -> None:
        _mostrar(padre, cliente, al_terminar)

    def _trabajo():
        try:
            cliente.conectar()
        except Exception as error:
            logger.warning("AgregarCaptura: no se pudo conectar: %s", error)
            wx.CallAfter(_conexion_fallida, error)
            return
        wx.CallAfter(_conexion_lista)

    diagnostico.crear_hilo(_trabajo, "AgregarCapturaConectar").start()

"""Cuadro para elegir el micrófono de OBS sin abrir OBS.

Lo abre el menú Transmisión con `abrir_microfono_obs`: consulta las
fuentes en un hilo y, con los datos, muestra el cuadro en la interfaz.
Cambiar de fuente y aplicar también consultan en hilos, cada vez con un
cliente nuevo que se cierra al terminar. El cuadro sigue abierto después
de aplicar, para probar otro dispositivo.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.config import guardar_opcion
from bellbird.core.idioma import _
from bellbird.obs import obs_audio
from bellbird.obs import obs_cliente
from bellbird.obs import obs_entradas_audio
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


def _conectar():
    """Cliente conectado al websocket de OBS; quien lo pide lo cierra."""
    cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
    cliente.conectar()
    return cliente


def _cerrar(cliente) -> None:
    if cliente is None:
        return
    try:
        cliente.cerrar()
    except Exception as exc:
        logger.debug("No se pudo cerrar la conexión con OBS: %s", exc)


def _pares_de_elegir(fuentes):
    """Pares para `elegir_microfono`: las fuentes ya son micrófonos."""
    return [(nombre, obs_entradas_audio.TIPO_MICROFONO)
            for nombre in fuentes]


def abrir_microfono_obs(frame) -> None:
    """Lee los micrófonos en un hilo y abre el cuadro con lo que elija."""
    preferido = frame._config.get("obs_microfono", "")

    def consultar():
        cliente = None
        try:
            cliente = _conectar()
            fuentes = obs_entradas_audio.microfonos(cliente)
            if not fuentes:
                wx.CallAfter(
                    anunciar, _(obs_entradas_audio.AVISO_SIN_MICROFONO))
                return
            especial = obs_entradas_audio.microfono_especial(cliente)
            elegida = obs_audio.elegir_microfono(
                _pares_de_elegir(fuentes), preferido, especial)
            pares, actual = obs_entradas_audio.dispositivos(cliente, elegida)
        except Exception as exc:
            wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
        else:
            wx.CallAfter(_mostrar, fuentes, elegida, pares, actual)
        finally:
            _cerrar(cliente)

    def _mostrar(fuentes, elegida, pares, actual):
        dialogo = MicrofonoObsDialog(frame, fuentes, elegida, pares, actual)
        try:
            dialogo.ShowModal()
        finally:
            dialogo.Destroy()
        try:
            frame.SetFocus()
        except Exception as exc:
            logger.debug("No se pudo devolver el foco: %s", exc)

    diagnostico.crear_hilo(consultar, "MicrofonoObs").start()


class MicrofonoObsDialog(wx.Dialog):
    """Fuente de OBS y su dispositivo, para transmitir con ese micrófono."""

    def __init__(self, padre, fuentes, fuente, pares, actual):
        super().__init__(padre, title=_("Micrófono de OBS"),
                         name="DialogoMicrofonoObs")
        self._padre = padre
        self._valores = []
        vs = wx.BoxSizer(wx.VERTICAL)
        self.rotulo_fuente = wx.StaticText(self, label=_("&Fuente de OBS:"))
        vs.Add(self.rotulo_fuente, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_fuente = wx.Choice(
            self, choices=list(fuentes), name=_("Fuente de OBS"))
        self.cho_fuente.SetMinSize((320, -1))
        if fuente:
            self.cho_fuente.SetStringSelection(fuente)
        vs.Add(self.cho_fuente, 0, wx.EXPAND | wx.ALL, 10)
        self.rotulo_dispositivo = wx.StaticText(
            self, label=_("&Dispositivo:"))
        vs.Add(self.rotulo_dispositivo, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_dispositivo = wx.Choice(
            self, choices=[], name=_("Dispositivo"))
        self.cho_dispositivo.SetMinSize((320, -1))
        vs.Add(self.cho_dispositivo, 0, wx.EXPAND | wx.ALL, 10)
        self._cargar_dispositivos(pares, actual)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aplicar = wx.Button(self, wx.ID_ANY, _("&Aplicar"))
        self.btn_aplicar.SetDefault()
        self.btn_cerrar = wx.Button(self, wx.ID_CANCEL, _("Cerrar"))
        fila.Add(self.btn_aplicar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cerrar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizerAndFit(vs)
        self.cho_fuente.Bind(wx.EVT_CHOICE, self._al_cambiar_fuente)
        self.btn_aplicar.Bind(wx.EVT_BUTTON, self._al_aplicar)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._al_cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.cho_dispositivo.SetFocus()

    def _cargar_dispositivos(self, pares, actual) -> None:
        self._valores = [valor for _nombre, valor in pares]
        self.cho_dispositivo.Set([nombre for nombre, _valor in pares])
        buscado = actual or "default"
        if buscado in self._valores:
            self.cho_dispositivo.SetSelection(self._valores.index(buscado))

    def _al_cambiar_fuente(self, event) -> None:
        # La fuente viaja como argumento: los hilos no leen controles.
        fuente = self.cho_fuente.GetStringSelection()
        self.cho_dispositivo.Enable(False)

        def recargar():
            cliente = None
            try:
                cliente = _conectar()
                pares, actual = obs_entradas_audio.dispositivos(
                    cliente, fuente)
            except Exception as exc:
                wx.CallAfter(
                    self._fallo_recarga,
                    obs_cliente.mensaje_de_fallo_obs(exc))
            else:
                wx.CallAfter(self._recarga_lista, fuente, pares, actual)
            finally:
                _cerrar(cliente)

        diagnostico.crear_hilo(recargar, "MicrofonoDispositivos").start()
        event.Skip()

    def _recarga_lista(self, fuente, pares, actual) -> None:
        if not self:
            return
        if self.cho_fuente.GetStringSelection() != fuente:
            return
        self._cargar_dispositivos(pares, actual)
        self.cho_dispositivo.Enable(True)

    def _fallo_recarga(self, mensaje) -> None:
        if not self:
            return
        self.cho_dispositivo.Enable(True)
        anunciar(mensaje)

    def _al_aplicar(self, event) -> None:
        # Fuente, valor y nombre viajan como argumentos: los hilos no leen
        # controles de wx, eso solo es seguro desde el hilo principal.
        fuente = self.cho_fuente.GetStringSelection()
        indice = self.cho_dispositivo.GetSelection()
        if indice == wx.NOT_FOUND or not 0 <= indice < len(self._valores):
            anunciar(_("Elige un dispositivo."))
            return
        valor = self._valores[indice]
        nombre = self.cho_dispositivo.GetStringSelection()
        self.btn_aplicar.Enable(False)

        def aplicar():
            cliente = None
            try:
                cliente = _conectar()
                obs_entradas_audio.cambiar_dispositivo(cliente, fuente, valor)
                if obs_entradas_audio.silenciada(cliente, fuente):
                    senal = "silenciada"
                else:
                    senal = obs_entradas_audio.senal_microfono(fuente)
            except Exception as exc:
                wx.CallAfter(
                    self._fallo_aplicacion,
                    obs_cliente.mensaje_de_fallo_obs(exc))
            else:
                wx.CallAfter(
                    self._aplicacion_lista, fuente, nombre, senal)
            finally:
                _cerrar(cliente)

        diagnostico.crear_hilo(aplicar, "MicrofonoAplicar").start()

    def _aplicacion_lista(self, fuente, nombre, senal) -> None:
        if not self:
            return
        self.btn_aplicar.Enable(True)
        self._guardar_fuente(fuente)
        # Traductores: {dispositivo} es el nombre del dispositivo elegido.
        anunciar(_("Micrófono cambiado: {dispositivo}.").format(
            dispositivo=nombre))
        if senal == "silenciada":
            # Traductores: el micrófono quedó elegido pero OBS lo silencia.
            anunciar(_("El micrófono está silenciado en OBS."))
        elif senal is False:
            _snd.reproducir("microfono_sin_senal")
            anunciar(_(obs_audio.TEXTO_SIN_SENAL))
        elif senal is True:
            anunciar(_("El micrófono recibe sonido."))

    def _fallo_aplicacion(self, mensaje) -> None:
        if not self:
            return
        self.btn_aplicar.Enable(True)
        anunciar(mensaje)

    def _guardar_fuente(self, fuente) -> None:
        # RUTA_CONFIG vive en gui y solo vale tras iniciar: se lee tarde.
        from bellbird.ui.gui import RUTA_CONFIG
        guardar_opcion(RUTA_CONFIG, "obs", "microfono", fuente)
        self._padre._config["obs_microfono"] = fuente

    def _al_cerrar(self, _event) -> None:
        self.EndModal(wx.ID_CANCEL)

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()

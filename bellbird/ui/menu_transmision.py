"""Menú Transmisión de la barra principal.

Qué comandos tiene el menú Transmisión, cómo se mantiene al día su estado y
los botones de grabación que comparte con el panel.
"""

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import obs_entradas_audio
from bellbird.obs import obs_estado
from bellbird.obs import obs_ventana
from bellbird.ui import encuadre_camara
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.preferencias_comun import mostrar_control, nombre_de_etiqueta
from bellbird.voice import sound_player


_INICIAR_GRABACION = N_("Iniciar &grabación")
_DETENER_GRABACION = N_("Detener &grabación")
_PAUSAR_GRABACION = N_("&Pausar grabación")
_REANUDAR_GRABACION = N_("&Reanudar grabación")


class ControlGrabacion:
    """Botones de grabación del panel: iniciar o detener, y pausar o reanudar."""

    def __init__(self, padre, operaciones, gestor, al_cambiar, foco):
        self._operaciones = operaciones
        self._gestor = gestor
        self._al_cambiar = al_cambiar
        self._foco = foco
        self.grabando = False
        self.en_pausa = False
        self.boton = wx.Button(padre, label=_(_INICIAR_GRABACION),
                               name=nombre_de_etiqueta(_(_INICIAR_GRABACION)))
        self.pausar = wx.Button(padre, label=_(_PAUSAR_GRABACION),
                               name=nombre_de_etiqueta(_(_PAUSAR_GRABACION)))
        self.boton.Bind(wx.EVT_BUTTON, self._alternar)
        self.pausar.Bind(wx.EVT_BUTTON, self._alternar_pausa)

    def fijar(self, grabando, en_pausa):
        self.grabando = bool(grabando)
        self.en_pausa = bool(en_pausa)
        etiqueta = (_DETENER_GRABACION if self.grabando else _INICIAR_GRABACION)
        self.boton.SetLabel(_(etiqueta))
        self.boton.SetName(nombre_de_etiqueta(_(etiqueta)))
        etiqueta = (_REANUDAR_GRABACION if self.en_pausa
                    else _PAUSAR_GRABACION)
        self.pausar.SetLabel(_(etiqueta))
        self.pausar.SetName(nombre_de_etiqueta(_(etiqueta)))
        mostrar_control(self.pausar, self.grabando, self._foco)

    def _alternar(self, event):
        self._operaciones.en_hilo(
            self._gestor.alternar_grabacion, self._alternada)

    def _alternada(self, activa):
        self.fijar(activa, False)
        accion = "grabacion_iniciada" if activa else "grabacion_detenida"
        self._resultado(accion)

    def _alternar_pausa(self, event):
        self._operaciones.en_hilo(
            self._gestor.alternar_pausa_grabacion, self._pausa_alternada)

    def _pausa_alternada(self, en_pausa):
        self.fijar(self.grabando, en_pausa)
        accion = "grabacion_en_pausa" if en_pausa else "grabacion_reanudada"
        self._resultado(accion)

    def _resultado(self, accion):
        sound_player.reproducir(obs_estado.sonido_resultado(accion))
        anunciar(obs_estado.frase_resultado(accion))
        self._al_cambiar()


def mostrar_obs() -> None:
    """Trae al frente la ventana principal de OBS, si está abierto."""
    texto = obs_ventana.mostrar()
    if texto:
        anunciar(texto)


def _agregar_encuadre(frame, m):
    """La sección de encuadre: anuncio a pedido y casilla de avisos."""
    m.AppendSeparator()
    frame.mi_anunciar_encuadre = m.Append(
        wx.ID_ANY, _("Anunciar en&cuadre de cámara") + frame._accel("anunciar_encuadre"))
    frame.mi_avisos_encuadre = m.AppendCheckItem(
        wx.ID_ANY, _("A&visar si el rostro sale del encuadre") + frame._accel("avisos_encuadre"))
    frame.mi_avisos_encuadre.Check(bool(frame._config.get("avisar_encuadre", False)))
    frame._bind_menu(frame.mi_anunciar_encuadre,
                     encuadre_camara.anunciar_encuadre, frame)
    frame._bind_menu(frame.mi_avisos_encuadre,
                     encuadre_camara.alternar_avisos, frame)
    encuadre_camara.sincronizar(frame)


def construir(frame, mb):
    m = wx.Menu()
    frame.mi_transmision = m.Append(
        wx.ID_ANY, _("&Panel de transmisión…") + frame._accel("abrir_transmision"))
    frame.mi_obs_micro = m.AppendCheckItem(
        wx.ID_ANY, _("Silenciar &micrófono de OBS") + frame._accel("obs_micro"))
    frame.mi_micro_obs = m.Append(wx.ID_ANY, _("&Elegir micrófono…"))
    frame.mi_mostrar_obs = m.Append(
        wx.ID_ANY, _("Mostrar &OBS") + frame._accel("mostrar_obs"))
    frame.mi_avisos_sobrecarga = m.AppendCheckItem(
        wx.ID_ANY,
        _("&Avisar si OBS se sobrecarga") + frame._accel("avisos_sobrecarga"))
    frame.mi_avisos_sobrecarga.Check(bool(frame._config.get("avisar_sobrecarga", True)))
    frame.mi_grabar_al_transmitir = m.AppendCheckItem(
        wx.ID_ANY, _("&Grabar también al transmitir"))
    frame.mi_grabar_al_transmitir.Check(bool(frame._config.get("grabar_al_transmitir", False)))
    _agregar_encuadre(frame, m)
    mb.Append(m, _("&Transmisión"))
    _enlazar(frame, m)


def _enlazar(frame, m):
    """Conecta el menú Transmisión ya armado con sus manejadores."""
    from bellbird.ui import gui_microfono
    from bellbird.ui import gui_transmitir
    frame.Bind(wx.EVT_MENU,
              lambda e: wx.CallAfter(frame._on_transmision, None),
              frame.mi_transmision)
    frame.Bind(wx.EVT_MENU, frame._on_obs_micro, frame.mi_obs_micro)
    frame._bind_menu(frame.mi_micro_obs, gui_microfono.abrir_microfono_obs, frame)
    frame.Bind(wx.EVT_MENU_OPEN, lambda e: _al_abrir_transmision(frame, m, e))
    frame._bind_menu(frame.mi_mostrar_obs, mostrar_obs)
    frame._bind_menu(frame.mi_avisos_sobrecarga, frame._alternar_aviso_sobrecarga)
    frame._bind_menu(frame.mi_grabar_al_transmitir,
                     gui_transmitir.alternar_grabar_al_transmitir, frame)


def _al_abrir_transmision(frame, menu, evento):
    evento.Skip()
    if evento.GetMenu() is not menu:
        return
    if getattr(frame, "_consultando_micro", False):
        return
    frame._consultando_micro = True
    preferido = frame._config.get("obs_microfono", "")
    def _consultar():
        try:
            estado = obs_entradas_audio.estado_microfono(preferido)
        finally:
            frame._consultando_micro = False
        if estado is not None:
            wx.CallAfter(frame.mi_obs_micro.Check, estado)
    diagnostico.crear_hilo(_consultar, "MicrofonoEstado").start()

"""Panel de OBS: reúne en pestañas lo que se ve, se oye y se graba en OBS."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import consultas_transmision
from bellbird.obs import estado_panel
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_general
from bellbird.obs import obs_lanzador
from bellbird.obs.obs_destinos import DESTINOS
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.obs.restablecimiento import RegistroRestablecimiento
from bellbird.ui import gui_microfono, paleta
from bellbird.ui.accesibilidad import anunciar, enlazar_anuncio_de_pestana
from bellbird.ui.escena_pagina_agregar import PaginaAgregar
from bellbird.ui.escena_pagina_audio import PaginaAudio
from bellbird.ui.escena_pagina_escena import PaginaEscena
from bellbird.ui.escena_pagina_fuentes import PaginaFuentes
from bellbird.ui.gui_transmision import PaginaTransmision
from bellbird.ui.obs_pagina_grabacion import PaginaGrabacion
from bellbird.ui.obs_pagina_general import PaginaGeneral
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui.preferencias_comun import boton

logger = diagnostico.obtener_logger(__name__)

PESTANA_GENERAL = 0
PESTANA_ESCENA = 1
PESTANA_FUENTES = 2
PESTANA_AGREGAR = 3
PESTANA_TRANSMISION = 4
PESTANA_AUDIO = 5
PESTANA_GRABACION = 6


class VentanaObs(wx.Dialog):

    def __init__(self, parent, principal, gestor=None,
                 pestana=PESTANA_ESCENA):
        super().__init__(parent, title=_("Panel de OBS"), size=(680, 600),
                         name="DialogoObs")
        self._principal = principal
        self._propio = gestor is None
        self._gestor = gestor or GestorPanelObs()
        self._restablecimiento = RegistroRestablecimiento()
        self._asegurar = obs_lanzador.asegurar_obs
        self._operaciones = OperacionesObs(
            self, self._activar, self._escribir_fallo, self._enfocar_tras_fallo,
            self._tras_operacion)
        self._pestana_inicial = (
            pestana if 0 <= pestana < 7 else PESTANA_ESCENA)
        self._crear_controles()
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelObs")
        caja = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(panel, name="PestanasObs")
        self._pagina_transmision = PaginaTransmision(
            self.nb, self._principal, self._gestor, self._operaciones,
            self._refrescar_general)
        self._pagina_escena = PaginaEscena(
            self.nb, self._gestor, self._operaciones, self._elegir_escena)
        self._pagina_audio = PaginaAudio(
            self.nb, self._principal, self._gestor, self._operaciones)
        self._pagina_grabacion = PaginaGrabacion(
            self.nb, self._principal, self._gestor, self._operaciones,
            self._refrescar_grabacion)
        self._pagina_fuentes = PaginaFuentes(
            self.nb, self, self._gestor, self._operaciones,
            self._restablecimiento, self._escena_elegida)
        self._pagina_agregar = PaginaAgregar(
            self.nb, self, self._gestor, self._operaciones,
            self._escena_elegida, self._recargar_escena)
        self._pagina_general = PaginaGeneral(
            self.nb, self._actualizar_general, self._mostrar_obs)
        self.nb.AddPage(self._pagina_general, _("General"))
        self.nb.AddPage(self._pagina_escena, _("Escena"))
        self.nb.AddPage(self._pagina_fuentes, _("Fuentes"))
        self.nb.AddPage(self._pagina_agregar, _("Agregar"))
        self.nb.AddPage(self._pagina_transmision, _("Transmisión"))
        self.nb.AddPage(self._pagina_audio, _("Audio"))
        self.nb.AddPage(self._pagina_grabacion, _("Grabación"))
        self.nb.SetSelection(self._pestana_inicial)
        caja.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)
        self._crear_pie(panel, caja)
        panel.SetSizer(caja)
        self._enlazar_eventos()
        self.SetMinSize((620, -1))
        self.Centre()
        paleta.pintar_ventana(self)

    def _crear_pie(self, panel, caja):
        self.btn_cerrar = boton(panel, _("Cerrar"), _("Cerrar"), wx.ID_CANCEL)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.AddStretchSpacer(1)
        fila.Add(self.btn_cerrar, 0)
        caja.Add(fila, 0, wx.EXPAND | wx.ALL, 10)

    def _enlazar_eventos(self):
        enlazar_anuncio_de_pestana(self.nb)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._al_cambiar_pestana)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.Bind(wx.EVT_CLOSE, self._cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def _al_cambiar_pestana(self, evento):
        seleccion = evento.GetSelection()
        if self.nb.GetPage(seleccion) is self._pagina_grabacion:
            self._pagina_grabacion.releer_lista()
        if seleccion == PESTANA_GENERAL:
            self._refrescar_general()
            self._pagina_general.txt_estado.SetFocus()
        evento.Skip()

    def _primer_control(self, indice):
        controles = (
            self._pagina_general.txt_estado,
            self._pagina_escena.cho_escena,
            self._pagina_fuentes.cho_fuente,
            self._pagina_agregar.cho_ventana,
            self._pagina_transmision.cho_destino,
            self._pagina_audio.chk_silenciar,
            self._pagina_grabacion._grabacion.boton)
        return controles[indice] if 0 <= indice < len(controles) else None

    def _enfocar_pestana(self, indice):
        control = self._primer_control(indice)
        if control is not None:
            control.SetFocus()

    def _preferido(self):
        return gui_microfono.microfono_preferido(self._principal)

    def _cargar_inicial(self):
        self._asegurar(
            lambda: self._gestor.conectar(),
            al_anunciar=lambda frase: wx.CallAfter(anunciar, frase))
        if not self._gestor.conectado:
            self._gestor.conectar()
        escenas = self._gestor.escenas()
        al_aire = self._gestor.escena_al_aire()
        escena = al_aire if al_aire in escenas else (escenas[0] if escenas else "")
        leida = consultas_transmision.leer_escena(self._gestor, escena)
        perfil = self._gestor.perfil_actual()
        destino = perfil if perfil in DESTINOS else ""
        estado = consultas_transmision.leer_estado(
            self._gestor, destino, self._preferido())
        estadisticas = self._gestor.estadisticas()
        return escenas, escena, leida, estado, estadisticas

    def _inicial_cargada(self, datos):
        escenas, escena, leida, estado, estadisticas = datos
        self._pagina_escena.cargar(escenas, escena, leida.descripcion)
        self._pagina_fuentes.cargar(leida.fuentes, leida.fuente, leida.snap)
        self._pagina_agregar.cargar_ventanas(leida.opciones, leida.actual)
        self._pagina_audio.fijar(estado.silenciado)
        self._pagina_grabacion.aplicar(estado)
        self._pagina_transmision.cargar(estado)
        self._mostrar_general(estado, estadisticas)
        if self.nb.GetSelection() != self._pestana_inicial:
            return
        if self._pestana_inicial == PESTANA_TRANSMISION:
            self._pagina_transmision.enfocar_inicial()
        elif self._pestana_inicial == PESTANA_GRABACION:
            self._pagina_grabacion._grabacion.boton.SetFocus()
        elif self._pestana_inicial == PESTANA_ESCENA:
            if leida.descripcion:
                anunciar(leida.descripcion)
            self._pagina_escena.cho_escena.SetFocus()
        else:
            self._enfocar_pestana(self._pestana_inicial)

    def _escena_elegida(self):
        return self._pagina_escena.escena()

    def _elegir_escena(self, escena):
        if self._operaciones.en_vuelo:
            return
        self._en_hilo(
            lambda: consultas_transmision.leer_escena(self._gestor, escena),
            self._escena_leida)

    def _escena_leida(self, leida):
        self._pagina_escena.mostrar_descripcion(leida.descripcion)
        self._pagina_fuentes.cargar(leida.fuentes, leida.fuente, leida.snap)
        self._pagina_agregar.cargar_ventanas(leida.opciones, leida.actual)
        if leida.fuentes:
            self._pagina_fuentes.anunciar_snap(leida.snap)

    def _recargar_escena(self):
        if self._operaciones.en_vuelo:
            return
        self._elegir_escena(self._escena_elegida())

    def _refrescar_grabacion(self):
        self._en_hilo(
            lambda: consultas_transmision.leer_estado(
                self._gestor, "", self._preferido()),
            self._grabacion_leida)

    def _grabacion_leida(self, datos):
        self._pagina_grabacion.aplicar(datos)
        self._refrescar_general()

    def _mostrar_general(self, estado, estadisticas):
        resumen = estado_panel.resumir(
            self._pagina_transmision.destino_actual(), estado.transmision,
            estado.grabacion, estado.escena, estado.microfono,
            estado.silenciado, estado.problemas)
        self._pagina_general.mostrar(
            obs_general.resumen(resumen, estado.perfil, estadisticas))

    def _refrescar_general(self):
        if self._operaciones.en_vuelo or self._operaciones.cerrando:
            return
        destino = self._pagina_transmision.destino_actual()
        self._en_hilo(lambda: self._leer_general(destino), self._general_leida)

    def _actualizar_general(self):
        destino = self._pagina_transmision.destino_actual()
        self._en_hilo(lambda: self._leer_general(destino),
                      self._general_actualizada)

    def _leer_general(self, destino=""):
        estado = consultas_transmision.leer_estado(
            self._gestor, destino, self._preferido())
        return estado, self._gestor.estadisticas()

    def _general_leida(self, datos):
        self._mostrar_general(*datos)

    def _general_actualizada(self, datos):
        self._mostrar_general(*datos)
        anunciar(self._pagina_general.texto())

    def _mostrar_obs(self):
        from bellbird.obs import obs_ventana as ventana_obs
        texto = ventana_obs.mostrar()
        if texto:
            anunciar(texto)

    def _activar(self, activo):
        paginas = (self._pagina_transmision, self._pagina_escena,
                   self._pagina_audio, self._pagina_grabacion,
                   self._pagina_fuentes, self._pagina_agregar,
                   self._pagina_general)
        for pagina in paginas:
            for control in pagina.acciones:
                control.Enable(activo)
        self.btn_cerrar.Enable(activo)

    def _tras_operacion(self, resultado):
        if isinstance(resultado, obs_disposicion.SnapshotPanel):
            self._pagina_fuentes.mostrar_snap(resultado)

    def _escribir_fallo(self, mensaje):
        self._pagina_general.mostrar([mensaje])
        self._pagina_escena.mostrar_fallo(mensaje)

    def _enfocar_tras_fallo(self):
        """El foco se queda donde estaba: el fallo ya se anunció."""
        return None

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _al_tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_F1:
            from bellbird.ui import gui_menu
            gui_menu.abrir_documento_paquete(self, "MANUAL",
                                             _("Manual de uso"))
            return
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            if self._pagina_fuentes.en_ajuste:
                evento.Skip()
                return
            self._cerrar(evento)
            return
        evento.Skip()

    def _cerrar(self, event):
        if self._operaciones.cerrando:
            return
        self._pagina_transmision.cerrar_directo()
        self._operaciones.cerrar()
        if self._propio:
            diagnostico.crear_hilo(
                self._cerrar_gestor, "CerrarPanelOBS").start()
        self.EndModal(wx.ID_CANCEL)

    def _cerrar_gestor(self):
        try:
            self._gestor.cerrar()
        except Exception as error:
            logger.debug("no se pudo cerrar el gestor de OBS: %s", error)


def abrir_obs(padre, principal, gestor=None, pestana=PESTANA_ESCENA):
    dialogo = VentanaObs(padre, principal, gestor, pestana)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()

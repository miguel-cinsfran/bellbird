"""Panel de OBS: reúne en pestañas lo que se ve, se oye y se graba en OBS."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_general
from bellbird.obs import obs_lanzador
from bellbird.obs.estado_panel import EstadoPanel
from bellbird.obs.obs_destinos import DESTINOS
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.obs.restablecimiento import RegistroRestablecimiento
from bellbird.ui import gui_microfono, paleta
from bellbird.ui.accesibilidad import anunciar, enlazar_anuncio_de_pestana
from bellbird.ui.atajos_captura import tecla_texto
from bellbird.ui.escena_pagina_agregar import PaginaAgregar
from bellbird.ui.escena_pagina_audio import PaginaAudio
from bellbird.ui.escena_pagina_escena import PaginaEscena
from bellbird.ui.escena_pagina_fuentes import PaginaFuentes
from bellbird.ui.gui_transmision import PaginaTransmision
from bellbird.ui.obs_pagina_grabacion import PaginaGrabacion
from bellbird.ui.obs_pagina_general import PaginaGeneral
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui.preferencias_comun import boton, nombre_de_etiqueta

logger = diagnostico.obtener_logger(__name__)

PESTANA_TRANSMISION = 0
PESTANA_ESCENA = 1
PESTANA_AUDIO = 2
PESTANA_GRABACION = 3
PESTANA_FUENTES = 4
PESTANA_AGREGAR = 5
PESTANA_GENERAL = 6

TEXTO_AYUDA_OBS = N_(
    "Esta ventana reúne en pestañas lo que se hace con OBS. Ctrl+Tab pasa a "
    "la pestaña siguiente y Ctrl+Mayús+Tab a la anterior.\n\n"
    "Transmisión inicia y detiene el directo, elige adónde se transmite y "
    "muestra el chat en el vídeo. Restream abre la ventana de Restream.\n\n"
    "Escena elige cuál se edita, dice qué tiene y cambia cuál se emite. "
    "Recorrer la lista no cambia nada en el directo.\n\n"
    "Audio silencia el micrófono de OBS y elige cuál se usa.\n\n"
    "Grabación inicia, pausa y detiene la grabación. La lista tiene lo "
    "grabado: Intro abre el archivo y Supr lo elimina de la lista. La tecla "
    "Aplicaciones muestra las demás acciones.\n\n"
    "Fuentes elige una fuente de la escena. La mueve, la cambia de tamaño, "
    "la oculta, la bloquea o cambia su capa. Mover con flechas la mueve "
    "en pasos pequeños: Ctrl da pasos grandes, Mayús pasos de un píxel, "
    "Intro confirma y Esc deshace. Deshacer cambios vuelve a como estaba "
    "todo al abrir esta ventana.\n\n"
    "Agregar captura una ventana del equipo o agrega una cámara de Windows "
    "a la escena actual.\n\n"
    "General dice el perfil de OBS y cómo rinde el equipo. Mostrar OBS trae "
    "su ventana al frente.")


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
            self.nb, self._principal, self._gestor, self._operaciones)
        self._pagina_escena = PaginaEscena(
            self.nb, self._gestor, self._operaciones, self._elegir_escena)
        self._pagina_audio = PaginaAudio(
            self.nb, self._principal, self._gestor, self._operaciones)
        self._pagina_grabacion = PaginaGrabacion(
            self.nb, self._principal, self._gestor, self._operaciones,
            self._refrescar_grabacion, self._actualizar_grabacion)
        self._pagina_fuentes = PaginaFuentes(
            self.nb, self, self._gestor, self._operaciones,
            self._restablecimiento, self._escena_elegida)
        self._pagina_agregar = PaginaAgregar(
            self.nb, self, self._gestor, self._operaciones,
            self._escena_elegida, self._recargar_escena)
        self._pagina_general = PaginaGeneral(
            self.nb, self._actualizar_general, self._mostrar_obs)
        self.nb.AddPage(self._pagina_transmision, _("Transmisión"))
        self.nb.AddPage(self._pagina_escena, _("Escena"))
        self.nb.AddPage(self._pagina_audio, _("Audio"))
        self.nb.AddPage(self._pagina_grabacion, _("Grabación"))
        self.nb.AddPage(self._pagina_fuentes, _("Fuentes"))
        self.nb.AddPage(self._pagina_agregar, _("Agregar"))
        self.nb.AddPage(self._pagina_general, _("General"))
        self.nb.SetSelection(self._pestana_inicial)
        caja.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)
        self._crear_pie(panel, caja)
        panel.SetSizer(caja)
        self._acciones = (
            *self._pagina_transmision.acciones,
            *self._pagina_escena.acciones, *self._pagina_audio.acciones,
            *self._pagina_grabacion.acciones, *self._pagina_fuentes.acciones,
            *self._pagina_agregar.acciones, *self._pagina_general.acciones,
            self.btn_ayuda, self.btn_cerrar)
        self._enlazar_eventos()
        self.SetMinSize((620, -1))
        self.Centre()
        paleta.pintar_ventana(self)

    def _crear_pie(self, panel, caja):
        self.btn_ayuda = boton(
            panel, _("A&yuda"), nombre_de_etiqueta(_("A&yuda")))
        self.btn_cerrar = boton(panel, _("Cerrar"), _("Cerrar"), wx.ID_CANCEL)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.btn_ayuda, 0, wx.RIGHT, 8)
        fila.AddStretchSpacer(1)
        fila.Add(self.btn_cerrar, 0)
        caja.Add(fila, 0, wx.EXPAND | wx.ALL, 10)

    def _enlazar_eventos(self):
        enlazar_anuncio_de_pestana(self.nb)
        self.btn_ayuda.Bind(wx.EVT_BUTTON, self._ayuda)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.Bind(wx.EVT_CLOSE, self._cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def _primer_control(self, indice):
        controles = (
            self._pagina_transmision.cho_destino,
            self._pagina_escena.cho_escena,
            self._pagina_audio.chk_silenciar,
            self._pagina_grabacion.txt_estado,
            self._pagina_fuentes.cho_fuente,
            self._pagina_agregar.cho_ventana,
            self._pagina_general.txt_estado)
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
        self._pagina_general.mostrar(
            obs_general.lineas(estado.perfil, estadisticas))
        if self._pestana_inicial == PESTANA_TRANSMISION:
            self._pagina_transmision.enfocar_inicial()
        elif self._pestana_inicial == PESTANA_GRABACION:
            anunciar(self._pagina_grabacion.titular)
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

    def _actualizar_grabacion(self):
        self._en_hilo(
            lambda: consultas_transmision.leer_estado(
                self._gestor, "", self._preferido()),
            lambda datos: self._grabacion_actualizada(datos))

    def _grabacion_actualizada(self, datos):
        self._pagina_grabacion.aplicar(datos)
        anunciar(self._pagina_grabacion.txt_estado.GetValue())

    def _actualizar_general(self):
        self._en_hilo(self._leer_general, self._general_leida)

    def _leer_general(self):
        return self._gestor.perfil_actual(), self._gestor.estadisticas()

    def _general_leida(self, datos):
        perfil, estadisticas = datos
        self._pagina_general.mostrar(obs_general.lineas(perfil, estadisticas))
        anunciar(self._pagina_general.texto())

    def _mostrar_obs(self):
        from bellbird.obs import obs_ventana as ventana_obs
        texto = ventana_obs.mostrar()
        if texto:
            anunciar(texto)

    def _activar(self, activo):
        for control in self._acciones:
            control.Enable(activo)

    def _tras_operacion(self, resultado):
        if isinstance(resultado, obs_disposicion.SnapshotPanel):
            self._pagina_fuentes.mostrar_snap(resultado)

    def _escribir_fallo(self, mensaje):
        self._pagina_transmision.mostrar_fallo(mensaje)
        self._pagina_escena.mostrar_fallo(mensaje)
        self._pagina_grabacion.mostrar_estado(
            EstadoPanel(mensaje, "aviso", ()))

    def _enfocar_tras_fallo(self):
        if self.nb.GetSelection() == PESTANA_TRANSMISION:
            self._pagina_transmision.enfocar_actualizar()
        else:
            self.btn_cerrar.SetFocus()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _ayuda(self, event):
        wx.MessageBox(_(TEXTO_AYUDA_OBS), _("Ayuda del panel de OBS"),
                      wx.OK | wx.ICON_INFORMATION, self)

    def _atajo_configurado(self, accion):
        atajos = getattr(self._principal, "_atajos", None) or {}
        atajo = atajos.get(accion)
        return atajo.texto if atajo else ""

    def _combinacion(self, evento):
        tecla = tecla_texto(evento.GetKeyCode())
        if not tecla:
            return None
        partes = []
        if evento.ControlDown():
            partes.append("ctrl")
        if evento.AltDown():
            partes.append("alt")
        if evento.ShiftDown():
            partes.append("shift")
        return "+".join(partes + [tecla]) if partes else tecla

    def _saltar_por_atajo(self, evento):
        combinacion = self._combinacion(evento)
        if not combinacion:
            return False
        for accion, indice in (("abrir_escena", PESTANA_ESCENA),
                               ("abrir_grabacion", PESTANA_GRABACION)):
            if combinacion == self._atajo_configurado(accion):
                self.nb.SetSelection(indice)
                self._enfocar_pestana(indice)
                return True
        return False

    def _al_tecla(self, evento):
        if self._saltar_por_atajo(evento):
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

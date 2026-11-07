"""Ventana de Restream: la cuenta, los destinos, los perfiles y los eventos.

Cuatro pestañas en el orden en que se arma todo: Cuenta, Destinos, Perfiles
y Eventos. Cada una vive en su módulo y crea sus controles. La ventana
guarda lo común, lee la cuenta y los destinos en un hilo aparte y conecta,
reautoriza o desconecta la cuenta.
"""

from __future__ import annotations

import threading

import wx

from guyrapu.core import diagnostico
from guyrapu.core.config import APP_NAME
from guyrapu.core.idioma import _
from guyrapu.restream import canal_youtube, resumen_cuenta
from guyrapu.restream.api import ErrorApi
from guyrapu.ui import paleta
from guyrapu.ui import restream_acciones_destino
from guyrapu.ui.accesibilidad import anunciar, enlazar_anuncio_de_pestana, nombre_accesible
from guyrapu.ui.restream_pagina_cuenta import PaginaCuenta
from guyrapu.ui.restream_pagina_destinos import PaginaDestinos
from guyrapu.ui.restream_pagina_eventos import PaginaEventos
from guyrapu.ui.restream_pagina_perfiles import PaginaPerfiles
from guyrapu.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)


def _id_canal_de_la_sesion():
    """Identificador del canal de YouTube de la sesión, o "" sin sesión."""
    from guyrapu.youtube import credenciales, youtube_api
    if not credenciales.hay_sesion():
        return ""
    cliente = youtube_api.ClienteYouTube(credenciales.efectivas())
    return cliente.id_canal_propio() or ""


class VentanaRestream(wx.Dialog):

    def __init__(self, parent, cuenta, canales, ruta_perfiles,
                 al_conectar=None, al_reautorizar=None, al_desconectar=None,
                 destinos=None, perfil=None, eliminar=None, eventos=None,
                 estadisticas=None, id_canal=None):
        super().__init__(parent, title=_("Restream"), size=(640, 480),
                         name="DialogoRestream")
        self._cuenta = cuenta
        self._fuente_destinos = destinos or canales
        self._ruta = ruta_perfiles
        self._al_conectar = al_conectar
        self._al_reautorizar = al_reautorizar
        self._al_desconectar = al_desconectar
        self._funcion_perfil = perfil
        self._funcion_eliminar = eliminar
        self._funcion_eventos = eventos
        self._funcion_estadisticas = estadisticas
        self._funcion_id_canal = id_canal or _id_canal_de_la_sesion
        self._destinos = []
        self._id_canal = ""
        self._nombre_cuenta = ""
        self._esperando_destinos = False
        self._parada = threading.Event()
        self._vivo = True
        self._trabajo_en_curso = False
        self._error_cuenta = ""
        self._error_destinos = ""
        self._error_perfil = ""
        self._crear_ui()
        self._preparar()

    def _preparar(self):
        paleta.pintar_ventana(self)
        self.Centre()
        if self._cuenta.conectada():
            self._leer_canales()
            self._leer_perfil()

    @property
    def _canales_leidos(self):
        return [(destino.id, destino.texto) for destino in self._destinos]

    def _crear_ui(self):
        panel = wx.Panel(self, name="PanelRestream")
        vs = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(panel, name="PestanasRestream")
        self._crear_paginas()
        vs.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)
        self._crear_cerrar(panel, vs)
        panel.SetSizer(vs)
        self._enlazar_ventana()
        self._actualizar_cuenta()

    def _enlazar_ventana(self):
        self.Bind(wx.EVT_CLOSE, self._al_cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla_ventana)
        self.Bind(wx.EVT_ACTIVATE, self._al_activar)

    def _crear_cerrar(self, panel, vs):
        self.btn_cerrar = wx.Button(
            panel, wx.ID_CANCEL, _("Cerrar"), name=_("Cerrar"))
        nombre_accesible(self.btn_cerrar, self.btn_cerrar.GetName())
        vs.Add(self.btn_cerrar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.btn_cerrar.Bind(
            wx.EVT_BUTTON, lambda evento: self._cerrar())

    def _crear_paginas(self):
        self._pagina_perfiles = PaginaPerfiles(
            self.nb, self._ruta, lambda: self._canales_leidos,
            nombres_destinos=self._nombres_destinos,
            destinos_leidos=lambda: self._pagina_destinos.leidos,
            esta_conectada=self._cuenta.conectada)
        self._pagina_destinos = PaginaDestinos(
            self.nb, self._agregar_destino, self._eliminar_destino,
            lambda: self._leer_canales(pedido=True),
            lambda: restream_acciones_destino.alternar(self),
            lambda: restream_acciones_destino.cambiar_titulo(self),
            lambda: restream_acciones_destino.agregar_manual(self),
            lambda: restream_acciones_destino.abrir_enlace(self),
            lambda: restream_acciones_destino.copiar_enlace(self),
            esta_conectada=self._cuenta.conectada)
        self._pagina_eventos = PaginaEventos(
            self.nb, self._funcion_eventos, self._funcion_estadisticas,
            self._nombres_destinos, self._cuenta.conectada)
        self._pagina_cuenta = PaginaCuenta(
            self.nb, self._conectar, self._reautorizar, self._desconectar)
        self.nb.AddPage(self._pagina_cuenta, _("Cuenta"))
        self.nb.AddPage(self._pagina_destinos, _("Destinos"))
        self.nb.AddPage(self._pagina_perfiles, _("Perfiles"))
        self.nb.AddPage(self._pagina_eventos, _("Eventos"))
        self.nb.SetSelection(0)
        enlazar_anuncio_de_pestana(self.nb)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._al_cambiar_pestana)

    def _nombres_destinos(self):
        return {destino.id: destino.texto for destino in self._destinos}

    def _al_cambiar_pestana(self, evento):
        if self.nb.GetPage(evento.GetSelection()) is self._pagina_eventos:
            self._pagina_eventos.al_mostrarse()
        evento.Skip()

    def _actualizar_cuenta(self):
        conectada = bool(self._cuenta.conectada())
        self._pagina_cuenta.mostrar(
            conectada, self._nombre_cuenta, self._destinos,
            self._pagina_perfiles.cantidad(),
            canal_youtube.texto(self._destinos, self._id_canal),
            (self._error_cuenta, self._error_destinos, self._error_perfil))
        self._pagina_cuenta.fijar_botones(not self._trabajo_en_curso)

    def _conectar(self):
        self._iniciar_cuenta(
            self._al_conectar, self._fin_conectar, "RestreamConectar", True)

    def _reautorizar(self):
        self._iniciar_cuenta(
            self._al_reautorizar, self._fin_conectar,
            "RestreamReautorizar", True)

    def _desconectar(self):
        if self._al_desconectar is None:
            return
        self._iniciar_cuenta(
            lambda _parada: self._al_desconectar(),
            self._fin_desconectar, "RestreamDesconectar", False)

    def _iniciar_cuenta(self, funcion, exito, nombre, abriendo):
        if funcion is None or self._trabajo_en_curso:
            return
        self._trabajo_en_curso = True
        self._error_cuenta = ""
        self._actualizar_cuenta()
        if abriendo:
            anunciar(_("Abriendo el navegador para iniciar sesión en "
                       "Restream. Autoriza y vuelve aquí."))

        def _correr():
            error = None
            try:
                funcion(self._parada)
            except Exception as exc:
                error = exc
            self._en_hilo_principal(self._terminar_cuenta, exito, error)

        diagnostico.crear_hilo(_correr, nombre).start()

    def _terminar_cuenta(self, exito, error):
        self._trabajo_en_curso = False
        if error is None:
            exito()
        else:
            self._fallo_cuenta(error)

    def _fallo_cuenta(self, error):
        mensaje = str(error).strip() or _("No se pudo conectar con Restream.")
        self._error_cuenta = mensaje
        _snd.reproducir("error")
        self._actualizar_cuenta()
        anunciar(mensaje)

    def _fin_conectar(self):
        _snd.reproducir("conectado")
        self._error_cuenta = ""
        self._error_destinos = ""
        self._error_perfil = ""
        self._actualizar_cuenta()
        anunciar(_("Cuenta de Restream conectada."))
        self._pagina_eventos.reiniciar()
        self._leer_canales()
        self._leer_perfil()

    def _fin_desconectar(self):
        _snd.reproducir("desconectado")
        self._error_cuenta = ""
        self._error_destinos = ""
        self._error_perfil = ""
        self._destinos = []
        self._id_canal = ""
        self._nombre_cuenta = ""
        self._pagina_destinos.mostrar([])
        self._pagina_eventos.reiniciar()
        self._actualizar_cuenta()
        anunciar(_("Cuenta de Restream desconectada."))

    def _en_hilo_principal(self, funcion, *args):
        def _envoltura():
            if self._vivo:
                funcion(*args)

        wx.CallAfter(_envoltura)

    def _leer_canales(self, anunciar_nuevos=False, pedido=False):
        if self._fuente_destinos is None:
            return

        def _correr():
            try:
                leidos = [resumen_cuenta.como_destino(destino)
                          for destino in self._fuente_destinos()]
            except Exception as exc:
                self._en_hilo_principal(
                    self._fallo_destinos, exc, pedido)
                return
            self._en_hilo_principal(
                self._destinos_listos, leidos, anunciar_nuevos,
                self._leer_id_canal())

        diagnostico.crear_hilo(_correr, "RestreamCanales").start()

    def _leer_id_canal(self):
        try:
            return self._funcion_id_canal() or ""
        except Exception:
            logger.warning(
                "no se pudo leer el identificador del canal de la sesión",
                exc_info=True)
            return ""

    def _destinos_listos(self, leidos, anunciar_nuevos=False, id_canal=""):
        antes = {destino.id for destino in self._destinos}
        self._destinos = list(leidos)
        self._id_canal = id_canal
        self._error_destinos = ""
        self._pagina_destinos.mostrar(self._destinos)
        self._pagina_perfiles.actualizar()
        self._pagina_eventos.actualizar_nombres()
        self._actualizar_cuenta()
        if anunciar_nuevos:
            for destino in self._destinos:
                if destino.id not in antes:
                    anunciar(_("Destino agregado: {destino}.").format(
                        destino=destino.texto))

    def _fallo_destinos(self, error, pedido=False):
        if isinstance(error, ErrorApi):
            texto = str(error).strip()
        else:
            texto = _("No se pudieron leer los destinos.")
        self._error_destinos = texto
        self._actualizar_cuenta()
        if pedido:
            _snd.reproducir("error")
            anunciar(texto)

    def _leer_perfil(self):
        if self._funcion_perfil is None:
            return

        def _correr():
            try:
                datos = self._funcion_perfil()
            except Exception as exc:
                self._en_hilo_principal(self._fallo_perfil, exc)
            else:
                self._en_hilo_principal(self._perfil_listo, datos)

        diagnostico.crear_hilo(_correr, "RestreamPerfil").start()

    def _perfil_listo(self, datos):
        self._nombre_cuenta = (getattr(datos, "correo", "")
                               or getattr(datos, "usuario", ""))
        self._error_perfil = ""
        self._actualizar_cuenta()

    def _fallo_perfil(self, error):
        self._error_perfil = str(error).strip()
        self._actualizar_cuenta()

    def _agregar_destino(self):
        self._esperando_destinos = True
        anunciar(_("Restream se abre en el navegador. Agrega el destino ahí "
                   "y vuelve a {app}.").format(app=APP_NAME))

    def _al_activar(self, evento):
        if evento.GetActive() and self._esperando_destinos:
            self._esperando_destinos = False
            self._leer_canales(anunciar_nuevos=True)
        evento.Skip()

    def _eliminar_destino(self):
        destino = self._pagina_destinos.seleccionado()
        if destino is None:
            anunciar(_("Sin selección"))
            return
        if self._funcion_eliminar is None:
            return
        if not self._pagina_destinos.confirmar(destino.texto):
            return

        def _correr():
            try:
                self._funcion_eliminar(destino.id)
            except Exception as exc:
                self._en_hilo_principal(self._fallo_eliminar, exc)
            else:
                self._en_hilo_principal(
                    self._destino_eliminado, destino.id)

        diagnostico.crear_hilo(_correr, "RestreamEliminar").start()

    def _fallo_eliminar(self, _error):
        texto = _("No se pudo eliminar el destino. Vuelve a intentarlo.")
        self._error_destinos = texto
        _snd.reproducir("error")
        self._actualizar_cuenta()
        anunciar(texto)

    def _destino_eliminado(self, identificador):
        self._destinos = [destino for destino in self._destinos
                          if destino.id != identificador]
        self._pagina_destinos.mostrar(self._destinos)
        self._actualizar_cuenta()
        anunciar(_("Destino eliminado."))

    def _marcar_cerrada(self):
        self._vivo = False
        self._parada.set()

    def _cerrar(self):
        self._marcar_cerrada()
        self.EndModal(wx.ID_CANCEL)

    def _al_cerrar(self, _evento):
        self._cerrar()

    def Destroy(self):
        self._marcar_cerrada()
        return super().Destroy()

    def _al_tecla_ventana(self, evento):
        tecla = evento.GetKeyCode()
        if tecla == wx.WXK_F1:
            from guyrapu.ui import gui_menu
            gui_menu.abrir_documento_paquete(
                self, "MANUAL", _("Manual de uso"))
        elif tecla == wx.WXK_ESCAPE:
            self._cerrar()
        else:
            evento.Skip()


def abrir_restream(padre, cuenta, canales, ruta_perfiles, al_conectar=None,
                   al_reautorizar=None, al_desconectar=None, destinos=None,
                   perfil=None, eliminar=None, eventos=None,
                   estadisticas=None, id_canal=None):
    dialogo = VentanaRestream(
        padre, cuenta, canales, ruta_perfiles, al_conectar, al_reautorizar,
        al_desconectar, destinos=destinos, perfil=perfil, eliminar=eliminar,
        eventos=eventos, estadisticas=estadisticas, id_canal=id_canal)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()

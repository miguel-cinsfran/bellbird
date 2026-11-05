"""Pestaña Audio de la ventana Escena: las fuentes de audio y sus acciones."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import (
    filtros_microfono, nivel_microfono, prueba_microfono)
from guyrapu.ui import escena_escucha, escena_filtros, fila_audio, gui_microfono
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.preferencias_comun import (
    boton, fila_campo, nombre_de_etiqueta)
from guyrapu.voice import sound_player


class PaginaAudio(wx.Panel):

    def __init__(self, parent, principal, gestor, operaciones):
        super().__init__(parent, name="PaginaAudio")
        self._principal = principal
        self._gestor = gestor
        self._operaciones = operaciones
        self._preparar_estado()
        self._crear_controles()
        self._silencio = self._crear_silencio()
        self._enlazar_eventos()
        self._observar_pestana()

    def _preparar_estado(self):
        self._filas = ()
        self._prueba = None
        self._prueba_fuente = ""
        self._viva = True
        self._listo = False

    def _crear_silencio(self):
        return gui_microfono.ControlSilencio(
            self._gestor, self.chk_silenciar, self._operaciones,
            self.fuente, lambda: self._refrescar_fila(self.fuente()))

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        self._crear_lista(caja)
        self.chk_silenciar = self._crear_casilla(_("Si&lenciar"))
        self._crear_botones()
        self.chk_escuchar = self._crear_casilla(_("&Escuchar"))
        caja.Add(self._crear_fila(), 0, wx.ALL, 8)
        self.SetSizer(caja)
        self.acciones = (
            self.lst_audio, self.chk_silenciar, self.btn_microfono,
            self.btn_probar, self.btn_filtros, self.chk_escuchar)
        self._escucha = self._crear_escucha()

    def _crear_escucha(self):
        return escena_escucha.ControlEscucha(
            self.chk_escuchar, self._gestor, self._operaciones, self.fuente,
            lambda fuente: self._refrescar_fila(fuente))

    def _crear_lista(self, caja):
        etiqueta = _("Fuentes de &audio:")
        self.rotulo_audio = wx.StaticText(self, label=etiqueta)
        self.lst_audio = wx.ListBox(
            self, name=nombre_de_etiqueta(etiqueta))
        nombre_accesible(self.lst_audio, self.lst_audio.GetName())
        self.lst_audio.SetMinSize((-1, 120))
        fila_campo(caja, self.rotulo_audio, self.lst_audio)

    def _crear_botones(self):
        etiquetas = (_("Elegir &micrófono…"), _("&Probar nivel"),
                     _("&Filtros…"))
        self.btn_microfono, self.btn_probar, self.btn_filtros = (
            boton(self, etiqueta, nombre_de_etiqueta(etiqueta))
            for etiqueta in etiquetas)

    def _crear_casilla(self, etiqueta):
        return wx.CheckBox(
            self, label=etiqueta, name=nombre_de_etiqueta(etiqueta))

    def _crear_fila(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.chk_silenciar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        fila.Add(self.btn_microfono, 0, wx.ALL, 6)
        fila.Add(self.btn_probar, 0, wx.ALL, 6)
        fila.Add(self.btn_filtros, 0, wx.ALL, 6)
        fila.Add(self.chk_escuchar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        return fila

    def _enlazar_eventos(self):
        self.lst_audio.Bind(wx.EVT_KEY_DOWN, self._tecla_audio)
        self.lst_audio.Bind(wx.EVT_CONTEXT_MENU, self._menu_contextual)
        self.lst_audio.Bind(wx.EVT_LISTBOX, self._al_cambiar_seleccion)
        self.btn_microfono.Bind(
            wx.EVT_BUTTON,
            lambda evento: gui_microfono.abrir_microfono_obs(
                self._principal, al_cerrar=self.btn_microfono.SetFocus))
        self.btn_probar.Bind(wx.EVT_BUTTON, self._al_probar)
        self.btn_filtros.Bind(wx.EVT_BUTTON, self._al_filtros)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)

    def _observar_pestana(self):
        padre = self.GetParent()
        if isinstance(padre, wx.Notebook):
            padre.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._al_cambiar_pestana)

    def _al_cambiar_pestana(self, evento):
        padre = self.GetParent()
        if (self._listo and isinstance(padre, wx.Notebook)
                and padre.GetPage(evento.GetSelection()) is self):
            self._releer_lista()
        evento.Skip()

    def _es_visible(self):
        padre = self.GetParent()
        return (isinstance(padre, wx.Notebook)
                and padre.GetSelection() == padre.FindPage(self))

    def fijar(self, silenciado):
        self._silencio.fijar(silenciado)
        self._listo = True
        if self._es_visible():
            self._releer_lista()

    def _releer_lista(self, preferido=None):
        if self._es_visible():
            preferido = preferido or gui_microfono.microfono_preferido(
                self._principal)
        objetivo = self.fuente() or preferido
        self._operaciones.en_hilo(
            self._leer_fuentes,
            lambda datos: self._poner_filas(datos, objetivo))

    def _leer_fuentes(self):
        nombres = self._gestor.fuentes_audio()
        filtros = filtros_microfono.leer_filtros_de(nombres)
        return tuple(
            (nombre, bool(self._gestor.silenciada(nombre)),
             filtros.get(nombre, ()))
            for nombre in nombres)

    def _poner_filas(self, datos, preferido=""):
        actual = self.fuente()
        self._filas = tuple(datos)
        self.lst_audio.Set(
            [fila_audio.texto(nombre, silenciada, filtros)
             for nombre, silenciada, filtros in self._filas])
        indice = self._indice_de(actual or preferido)
        if indice is None:
            indice = 0 if self._filas else wx.NOT_FOUND
        self.lst_audio.SetSelection(indice)
        self._fijar_casilla()

    def fuente(self):
        fila = self._fila()
        return fila[0] if fila is not None else ""

    def _fila(self):
        indice = self.lst_audio.GetSelection()
        if 0 <= indice < len(self._filas):
            return self._filas[indice]
        return None

    def _indice_de(self, nombre):
        for indice, fila in enumerate(self._filas):
            if fila[0] == nombre:
                return indice
        return None

    def _fijar_casilla(self):
        fila = self._fila()
        self._silencio.fijar(bool(fila[1]) if fila is not None else False)

    def _al_cambiar_seleccion(self, evento):
        self._fijar_casilla()
        evento.Skip()

    def _tecla_audio(self, evento):
        tecla = evento.GetKeyCode()
        if (tecla == wx.WXK_WINDOWS_MENU
                or (tecla == wx.WXK_F10 and evento.ShiftDown())):
            self._mostrar_menu_audio(self.lst_audio)
            return
        evento.Skip()

    def _menu_contextual(self, _evento):
        self._mostrar_menu_audio(self.lst_audio)

    def _mostrar_menu_audio(self, ancla):
        if self._fila() is None:
            anunciar(_("Sin selección"))
            return
        menu = self._menu_de_audio()
        ancla.PopupMenu(menu)
        menu.Destroy()

    def _menu_de_audio(self):
        menu = wx.Menu()
        self._agregar_silencio(menu)
        menu.AppendSeparator()
        for etiqueta, accion in self._acciones_de_menu():
            self._agregar_accion(menu, etiqueta, accion)
        return menu

    def _acciones_de_menu(self):
        return ((_("&Probar nivel"), self._al_probar),
                (_("&Filtros…"), self._al_filtros),
                (_("&Escuchar"), self._al_escuchar))

    def _agregar_silencio(self, menu):
        fila = self._fila()
        silencio = menu.AppendCheckItem(wx.NewIdRef(), _("Si&lenciar"))
        silencio.Check(bool(fila[1]))
        menu.Bind(wx.EVT_MENU,
                  lambda evento: self._silenciar_desde_menu(evento.IsChecked()),
                  id=silencio.GetId())

    def _agregar_accion(self, menu, etiqueta, accion):
        identificador = wx.NewIdRef()
        menu.Append(identificador, etiqueta)
        menu.Bind(wx.EVT_MENU,
                  lambda _evento, accion=accion: accion(),
                  id=identificador)

    def _silenciar_desde_menu(self, marcada):
        self._silencio.fijar(marcada)
        self._silencio.alternar()

    def _al_probar(self, evento=None):
        if self._prueba is not None:
            self._prueba.detener()
            return
        fuente = self.fuente()
        if not fuente:
            anunciar(_("Elige una fuente de audio."))
            return
        self._operaciones.en_hilo(
            lambda: prueba_microfono.preparar(self._gestor, fuente),
            self._preparada)

    def _preparada(self, resultado):
        fuente, silenciado, nombre = resultado
        if not self._puede_empezar(fuente, silenciado):
            return
        self._prueba_fuente = fuente
        anunciar(_("Probando {fuente}. ").format(fuente=fuente)
                 + prueba_microfono.frase_de_inicio(nombre))
        self._cambiar_rotulo(_("&Detener prueba"))
        self._prueba = self._nueva_prueba(fuente)
        self._prueba.iniciar()
        self._refrescar_fila(fuente)

    def _nueva_prueba(self, fuente):
        return prueba_microfono.PruebaMicrofono(
            fuente,
            lambda nivel: wx.CallAfter(self._anunciar_tramo, nivel),
            lambda motivo: wx.CallAfter(self._terminada, motivo))

    def _puede_empezar(self, fuente, silenciado):
        if not fuente:
            anunciar(_("Elige una fuente de audio."))
            return False
        if silenciado:
            anunciar(_("La fuente {fuente} está silenciada en OBS. "
                       "Desmárcala y vuelve a probar.").format(fuente=fuente))
            return False
        return True

    def _anunciar_tramo(self, nivel):
        if not self._viva:
            return
        sound_player.reproducir(nivel_microfono.sonido_de_tramo(nivel))
        anunciar(nivel_microfono.frase_de_tramo(nivel), False)

    def _terminada(self, motivo):
        fuente = self._prueba_fuente
        self._prueba = None
        self._prueba_fuente = ""
        if not self._viva:
            return
        self._cambiar_rotulo(_("&Probar nivel"))
        self._anunciar_fin(motivo, fuente)
        if fuente:
            self._refrescar_fila(fuente)

    @staticmethod
    def _anunciar_fin(motivo, fuente):
        if motivo == prueba_microfono.MOTIVO_FALLO:
            anunciar(_("No se pudo medir {fuente} en OBS. "
                       "Prueba detenida.").format(fuente=fuente))
        else:
            anunciar(_("Prueba de nivel de {fuente} detenida.").format(
                fuente=fuente))

    def _cambiar_rotulo(self, texto):
        self.btn_probar.SetLabel(texto)
        self.btn_probar.SetName(nombre_de_etiqueta(texto))

    def _al_filtros(self, evento=None):
        fuente = self.fuente()
        if not fuente:
            anunciar(_("Elige una fuente de audio."))
            return
        self._operaciones.en_hilo(
            lambda: (fuente, filtros_microfono.leer(fuente)),
            self._filtros_listos)

    def _filtros_listos(self, resultado):
        fuente, estado = resultado
        if not fuente:
            anunciar(_("Elige una fuente de audio."))
            return
        elegido = escena_filtros.pedir_filtros(self, fuente, estado)
        self.btn_filtros.SetFocus()
        if elegido is not None:
            self._operaciones.en_hilo(
                lambda: filtros_microfono.aplicar(fuente, elegido),
                lambda _resultado: self._filtros_aplicados(fuente, elegido))

    def _filtros_aplicados(self, fuente, elegido):
        # Traductores: {fuente} es la fuente de audio y {resumen} lo aplicado.
        anunciar(_("{fuente}: {resumen}").format(
            fuente=fuente, resumen=filtros_microfono.resumen(elegido)))
        self._refrescar_fila(fuente)

    def _al_escuchar(self):
        self.chk_escuchar.SetValue(not self._escucha.activa)
        self._escucha.alternar()

    def _refrescar_fila(self, fuente):
        if not fuente:
            return
        self._operaciones.en_hilo(
            lambda: self._leer_fila(fuente), self._fila_leida)

    def _leer_fila(self, fuente):
        return (fuente, bool(self._gestor.silenciada(fuente)),
                filtros_microfono.leer_filtros(fuente))

    def _fila_leida(self, datos):
        fuente, silenciada, filtros = datos
        indice = self._indice_de(fuente)
        if indice is None:
            return
        filas = list(self._filas)
        filas[indice] = (fuente, silenciada, filtros)
        seleccion = self.lst_audio.GetSelection()
        self._filas = tuple(filas)
        self.lst_audio.SetString(
            indice, fila_audio.texto(fuente, silenciada, filtros))
        self.lst_audio.SetSelection(seleccion)
        self._fijar_casilla()

    def _al_destruir(self, evento):
        self._viva = False
        if self._prueba is not None:
            self._prueba.detener()
        self._escucha.al_cerrar()
        evento.Skip()

"""Página Mensajes automáticos del diálogo de Preferencias.

Mezcla sin estado propio: `gui_preferencias` hereda de acá. Se separó
porque ese módulo no puede crecer y la página siguiente (IA) necesita sitio.
"""

from __future__ import annotations

import wx

from ytchat.core import paths
from ytchat.capture import programados
from ytchat.ui.gui import ContadorAccesible, anunciar, nombre_accesible


class PaginaProgramados:
    """Página Mensajes automáticos: lista, texto, intervalo y activación."""

    def _iniciar_programados(self):
        self._ruta_programados = paths.mensajes_programados()
        self._mensajes_programados = programados.cargar(self._ruta_programados)

    def _pag_programados(self, parent):
        p = self._make_panel(parent, "PagProgramados")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._programados_intro(p, vs)
        self._programados_lista(p, vs)
        self._programados_datos(p, vs)
        self._programados_botones(p, vs)
        p.SetSizer(vs)
        self.lista_programados.Bind(wx.EVT_LISTBOX, self._programado_elegido)
        self.btn_programado_agregar.Bind(wx.EVT_BUTTON, self._agregar_programado)
        self.btn_programado_guardar.Bind(wx.EVT_BUTTON, self._guardar_programado)
        self.btn_programado_quitar.Bind(wx.EVT_BUTTON, self._quitar_programado)
        return p

    def _programados_intro(self, p, vs):
        # Definidos en gui_preferencias: se importan acá para evitar un import circular.
        from ytchat.ui.gui_preferencias import ANCHO_NOTA, _T
        intro = wx.StaticText(p, name="IntroProgramados", label=(
            "Envía mensajes al chat de tu directo cada cierto tiempo. Necesita "
            "sesión de Google iniciada y un directo de YouTube conectado. El "
            "intervalo mínimo son 5 minutos y cada mensaje admite 200 caracteres. "
            "YouTube suele bloquear los enlaces en el chat en vivo: conviene "
            "escribir el nombre de usuario en vez de la dirección completa."))
        intro.SetForegroundColour(_T.dim)
        intro.Wrap(ANCHO_NOTA)
        vs.Add(intro, 0, wx.ALL, 10)

        self.chk_programados = wx.CheckBox(
            p, label="&Activar los mensajes automáticos", name="ActivarProgramados")
        vs.Add(self.chk_programados, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _programados_lista(self, p, vs):
        self.lista_programados = wx.ListBox(p, choices=[
            programados.describir_mensaje(m) for m in self._mensajes_programados
        ], name="ListaProgramados")
        nombre_accesible(self.lista_programados, "Mensajes automáticos guardados")
        vs.Add(self.lista_programados, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

    def _programados_datos(self, p, vs):
        vs.Add(self._fila_label(p, "&Texto del mensaje"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_programado = wx.TextCtrl(p, name="TextoProgramado")
        self.txt_programado.SetMaxLength(200)
        vs.Add(self.txt_programado, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        vs.Add(self._fila_label(p, "Cada, &mínimo (minutos)"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_min_programado = ContadorAccesible(
            p, min=5, max=240, initial=10, name="MinutosMin")
        vs.Add(self.sp_min_programado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vs.Add(self._fila_label(p, "y &máximo (minutos)"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_max_programado = ContadorAccesible(
            p, min=5, max=240, initial=10, name="MinutosMax")
        vs.Add(self.sp_max_programado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.chk_mensaje_activo = wx.CheckBox(
            p, label="&Enviar este mensaje", name="MensajeActivo")
        # Un mensaje nuevo nace activo: si no, quien lo agrega y activa los
        # automáticos no ve salir nada porque quedó «Pausado».
        self.chk_mensaje_activo.SetValue(True)
        vs.Add(self.chk_mensaje_activo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

    def _programados_botones(self, p, vs):
        # Definidos en gui_preferencias: se importan acá para evitar un import circular.
        from ytchat.ui.gui_preferencias import _T
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_programado_agregar = wx.Button(p, label="&Agregar", name="AgregarProgramado")
        self.btn_programado_guardar = wx.Button(
            p, label="&Guardar cambios", name="GuardarProgramado")
        self.btn_programado_quitar = wx.Button(p, label="&Quitar", name="QuitarProgramado")
        for boton in (self.btn_programado_agregar, self.btn_programado_guardar,
                      self.btn_programado_quitar):
            boton.SetBackgroundColour(_T.btn)
            boton.SetForegroundColour(_T.btn_t)
            fila.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(fila, 0, wx.ALL, 10)

    def _programado_elegido(self, event):
        indice = self.lista_programados.GetSelection()
        if indice != wx.NOT_FOUND:
            mensaje = self._mensajes_programados[indice]
            self.txt_programado.SetValue(mensaje.get("texto", ""))
            self.sp_min_programado.SetValue(mensaje.get("minutos_min", 10))
            self.sp_max_programado.SetValue(mensaje.get("minutos_max", 10))
            self.chk_mensaje_activo.SetValue(mensaje.get("activo", False))
            anunciar(programados.describir_mensaje(mensaje))
        event.Skip()

    def _datos_programado(self):
        return {
            "texto": self.txt_programado.GetValue(),
            "minutos_min": self.sp_min_programado.GetValue(),
            "minutos_max": self.sp_max_programado.GetValue(),
            "activo": self.chk_mensaje_activo.GetValue(),
            "proximo": 0.0,
        }

    def _validar_programado(self, mensaje):
        error, aviso = programados.validar_mensaje(
            mensaje["texto"], mensaje["minutos_min"], mensaje["minutos_max"])
        if error:
            anunciar(error)
            if not mensaje["texto"].strip() or len(mensaje["texto"]) > programados.MAX_CARACTERES:
                self.txt_programado.SetFocus()
            elif mensaje["minutos_min"] < programados.MINUTOS_MINIMOS:
                self.sp_min_programado.SetFocus()
            else:
                self.sp_max_programado.SetFocus()
            return False
        if aviso:
            anunciar(aviso)
        return True

    def _refrescar_programados(self, indice=-1):
        self.lista_programados.Set([programados.describir_mensaje(m)
                                    for m in self._mensajes_programados])
        if indice >= 0:
            self.lista_programados.SetSelection(indice)

    def _agregar_programado(self, event):
        mensaje = self._datos_programado()
        if not self._validar_programado(mensaje):
            return
        self._mensajes_programados.append(mensaje)
        programados.guardar(self._ruta_programados, self._mensajes_programados)
        self._refrescar_programados(len(self._mensajes_programados) - 1)
        anunciar("Mensaje agregado")

    def _guardar_programado(self, event):
        indice = self.lista_programados.GetSelection()
        if indice == wx.NOT_FOUND:
            anunciar("Elige primero un mensaje de la lista")
            return
        mensaje = self._datos_programado()
        if not self._validar_programado(mensaje):
            return
        mensaje["proximo"] = self._mensajes_programados[indice].get("proximo", 0.0)
        self._mensajes_programados[indice] = mensaje
        programados.guardar(self._ruta_programados, self._mensajes_programados)
        self._refrescar_programados(indice)
        anunciar("Mensaje guardado")

    def _quitar_programado(self, event):
        indice = self.lista_programados.GetSelection()
        if indice == wx.NOT_FOUND:
            anunciar("Elige primero un mensaje de la lista")
            return
        self._mensajes_programados.pop(indice)
        programados.guardar(self._ruta_programados, self._mensajes_programados)
        self._refrescar_programados(min(indice, len(self._mensajes_programados) - 1))
        anunciar("Mensaje quitado")

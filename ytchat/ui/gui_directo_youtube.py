"""Ventana para pedir los datos del directo de YouTube antes de transmitir.

Modal pequeña como `DialogoRedactar`: título, descripción, privacidad y las
opciones del directo (latencia, hecho para niños, rebobinar, categoría,
etiquetas y miniatura), que se recuerdan para la próxima vez. Pura salvo wx.
"""

from __future__ import annotations

import os
from datetime import datetime

import wx

from ytchat.core import diagnostico
from ytchat.ui.gui import anunciar, nombre_accesible
from ytchat.youtube import youtube_api
from ytchat.youtube.emision import (
    CATEGORIAS,
    ETIQUETAS_LATENCIA,
    ETIQUETAS_PRIVACIDAD,
    LATENCIA_INICIAL,
    LATENCIAS,
    PRIVACIDAD_INICIAL,
    PRIVACIDADES,
    EmisionError,
    error_de_miniatura,
    etiquetas_de_texto,
    opciones_lista,
    titulo_por_defecto,
)

_FILTRO_IMAGENES = ("Imágenes JPG y PNG (*.jpg;*.jpeg;*.png)|"
                    "*.jpg;*.jpeg;*.png")


def resultado_directo(titulo, descripcion, privacidad,
                      latencia=LATENCIA_INICIAL, ninos=False, dvr=True,
                      categoria="", etiquetas="", miniatura="", lista="",
                      lista_titulo="") -> dict:
    """Valida los valores de la ventana y arma el dict del directo.

    Pura y sin ventanas: la usan el diálogo y las pruebas. El título
    vacío anuncia «Falta el título del directo.» vía excepción, igual
    que `cuerpo_emision`. La lista de etiquetas la arma
    `etiquetas_de_texto` a partir del texto separado por comas.
    """
    titulo = (titulo or "").strip()
    if not titulo:
        raise EmisionError("Falta el título del directo.")
    if privacidad not in PRIVACIDADES:
        privacidad = PRIVACIDAD_INICIAL
    if latencia not in LATENCIAS:
        latencia = LATENCIA_INICIAL
    if categoria not in {identificador for identificador, _texto in CATEGORIAS}:
        categoria = ""
    lista = (lista or "").strip()
    lista_titulo = (lista_titulo or "").strip() if lista else ""
    return {"titulo": titulo[:100], "descripcion": descripcion or "",
            "privacidad": privacidad, "latencia": latencia,
            "ninos": bool(ninos), "dvr": bool(dvr), "categoria": categoria,
            "etiquetas": etiquetas_de_texto(etiquetas),
            "miniatura": (miniatura or "").strip(),
            "lista": lista, "lista_titulo": lista_titulo}


class DialogoDirectoYoutube(wx.Dialog):
    def __init__(self, padre, titulo="", descripcion="",
                 privacidad=PRIVACIDAD_INICIAL, revision=None,
                 latencia=LATENCIA_INICIAL, ninos=False, dvr=True,
                 categoria="", etiquetas="", miniatura="", lista="",
                 lista_titulo="", cargar_listas=None):
        super().__init__(padre, title="Directo de YouTube",
                         name="DialogoDirectoYoutube")
        if privacidad not in PRIVACIDADES:
            privacidad = PRIVACIDAD_INICIAL
        if latencia not in LATENCIAS:
            latencia = LATENCIA_INICIAL
        if not (titulo or "").strip():
            titulo = titulo_por_defecto(datetime.now())
        self._datos = None
        self._miniatura = (miniatura or "").strip()
        self._cargar_listas = cargar_listas

        vs = wx.BoxSizer(wx.VERTICAL)
        rotulo_titulo = wx.StaticText(self, label="Título:")
        vs.Add(rotulo_titulo, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_titulo = wx.TextCtrl(
            self, value=titulo, name="Título del directo")
        self.txt_titulo.SetMaxLength(100)
        self.txt_titulo.SelectAll()
        nombre_accesible(self.txt_titulo, "Título del directo")
        vs.Add(self.txt_titulo, 0, wx.EXPAND | wx.ALL, 10)

        rotulo_descripcion = wx.StaticText(
            self, label="Descripción, opcional:")
        vs.Add(rotulo_descripcion, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_descripcion = wx.TextCtrl(
            self, value=descripcion or "", style=wx.TE_MULTILINE,
            name="Descripción del directo")
        self.txt_descripcion.SetMinSize(
            (-1, 3 * self.txt_descripcion.GetCharHeight() + 12))
        nombre_accesible(self.txt_descripcion, "Descripción del directo")
        vs.Add(self.txt_descripcion, 1, wx.EXPAND | wx.ALL, 10)

        rotulo_privacidad = wx.StaticText(self, label="Privacidad:")
        vs.Add(rotulo_privacidad, 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_privacidad = wx.Choice(
            self, choices=[ETIQUETAS_PRIVACIDAD[p] for p in PRIVACIDADES],
            name="Privacidad")
        self.cho_privacidad.SetSelection(PRIVACIDADES.index(privacidad))
        nombre_accesible(self.cho_privacidad, "Privacidad")
        vs.Add(self.cho_privacidad, 0, wx.EXPAND | wx.ALL, 10)

        rotulo_latencia = wx.StaticText(self, label="&Latencia:")
        vs.Add(rotulo_latencia, 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_latencia = wx.Choice(
            self, choices=[ETIQUETAS_LATENCIA[l] for l in LATENCIAS],
            name="Latencia")
        self.cho_latencia.SetSelection(LATENCIAS.index(latencia))
        nombre_accesible(self.cho_latencia, "Latencia")
        vs.Add(self.cho_latencia, 0, wx.EXPAND | wx.ALL, 10)

        self.chk_ninos = wx.CheckBox(
            self, label="Hecho para &niños (YouTube apaga el chat)",
            name="Hecho para niños")
        self.chk_ninos.SetValue(bool(ninos))
        nombre_accesible(self.chk_ninos, "Hecho para niños")
        vs.Add(self.chk_ninos, 0, wx.LEFT | wx.RIGHT, 10)

        self.chk_dvr = wx.CheckBox(
            self, label="Permitir re&bobinar el directo",
            name="Permitir rebobinar")
        self.chk_dvr.SetValue(bool(dvr))
        nombre_accesible(self.chk_dvr, "Permitir rebobinar")
        vs.Add(self.chk_dvr, 0, wx.LEFT | wx.RIGHT, 10)

        rotulo_categoria = wx.StaticText(self, label="Cate&goría:")
        vs.Add(rotulo_categoria, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_categoria = wx.Choice(
            self, choices=[texto for _id, texto in CATEGORIAS],
            name="Categoría")
        ids = [identificador for identificador, _texto in CATEGORIAS]
        self.cho_categoria.SetSelection(
            ids.index(categoria) if categoria in ids else 0)
        nombre_accesible(self.cho_categoria, "Categoría")
        vs.Add(self.cho_categoria, 0, wx.EXPAND | wx.ALL, 10)

        rotulo_etiquetas = wx.StaticText(
            self, label="&Etiquetas, separadas por comas:")
        vs.Add(rotulo_etiquetas, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_etiquetas = wx.TextCtrl(
            self, value=etiquetas or "", name="Etiquetas")
        nombre_accesible(self.txt_etiquetas, "Etiquetas")
        vs.Add(self.txt_etiquetas, 0, wx.EXPAND | wx.ALL, 10)

        rotulo_miniatura = wx.StaticText(self, label="Miniatura:")
        vs.Add(rotulo_miniatura, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_miniatura = wx.TextCtrl(
            self, value=self._texto_miniatura(),
            style=wx.TE_MULTILINE | wx.TE_READONLY, name="Miniatura")
        self.txt_miniatura.SetMinSize(
            (-1, self.txt_miniatura.GetCharHeight() + 12))
        nombre_accesible(self.txt_miniatura, "Miniatura")
        vs.Add(self.txt_miniatura, 0, wx.EXPAND | wx.ALL, 10)

        fila_miniatura = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_elegir_miniatura = wx.Button(
            self, label="Elegir &miniatura...", name="Elegir miniatura")
        self.btn_quitar_miniatura = wx.Button(
            self, label="&Quitar miniatura", name="Quitar miniatura")
        fila_miniatura.Add(self.btn_elegir_miniatura, 0, wx.RIGHT, 6)
        fila_miniatura.Add(self.btn_quitar_miniatura, 0)
        vs.Add(fila_miniatura, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._opciones_lista, seleccion_lista = opciones_lista(
            None, lista, lista_titulo)
        rotulo_lista = wx.StaticText(self, label="Lista de re&producción:")
        vs.Add(rotulo_lista, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_lista = wx.Choice(
            self, choices=[texto for _id, texto in self._opciones_lista],
            name="Lista de reproducción")
        self.cho_lista.SetSelection(seleccion_lista)
        nombre_accesible(self.cho_lista, "Lista de reproducción")
        vs.Add(self.cho_lista, 0, wx.EXPAND | wx.ALL, 10)
        self.btn_cargar_listas = wx.Button(
            self, label="Ca&rgar listas", name="Cargar listas")
        vs.Add(self.btn_cargar_listas, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        from ytchat.obs import obs_prevuelo
        texto_revision = (obs_prevuelo.frase_revision(revision)
                          if revision is not None else "")
        rotulo_revision = wx.StaticText(self, label="Revisión de OBS:")
        vs.Add(rotulo_revision, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_revision = wx.TextCtrl(
            self, value=texto_revision,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="Revisión de OBS")
        self.txt_revision.SetMinSize(
            (-1, 3 * self.txt_revision.GetCharHeight() + 12))
        nombre_accesible(self.txt_revision, "Revisión de OBS")
        vs.Add(self.txt_revision, 0, wx.EXPAND | wx.ALL, 10)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_crear = wx.Button(self, wx.ID_OK, "&Transmitir")
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, "C&ancelar")
        fila.Add(self.btn_crear, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.txt_titulo.SetMinSize((420, -1))
        self.SetSizerAndFit(vs)
        self.btn_crear.Bind(wx.EVT_BUTTON, self._al_crear)
        self.btn_elegir_miniatura.Bind(wx.EVT_BUTTON,
                                       self._al_elegir_miniatura)
        self.btn_quitar_miniatura.Bind(wx.EVT_BUTTON,
                                       self._al_quitar_miniatura)
        if self._cargar_listas is None:
            self.btn_cargar_listas.Disable()
        else:
            self.btn_cargar_listas.Bind(wx.EVT_BUTTON, self._al_cargar_listas)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        if revision is not None and bool(getattr(revision, "problemas", ())):
            self.btn_cancelar.SetDefault()
            self.btn_cancelar.SetFocus()
        else:
            self.btn_crear.SetDefault()
            self.txt_titulo.SetFocus()

    @property
    def datos(self):
        return self._datos

    def _texto_miniatura(self) -> str:
        if not self._miniatura:
            return "Ninguna"
        return os.path.basename(self._miniatura)

    def _privacidad_elegida(self) -> str:
        return PRIVACIDADES[self.cho_privacidad.GetSelection()]

    def _latencia_elegida(self) -> str:
        return LATENCIAS[self.cho_latencia.GetSelection()]

    def _categoria_elegida(self) -> str:
        return CATEGORIAS[self.cho_categoria.GetSelection()][0]

    def _opcion_lista_elegida(self) -> tuple[str, str]:
        indice = self.cho_lista.GetSelection()
        if indice < 0 or indice >= len(self._opciones_lista):
            return "", ""
        return self._opciones_lista[indice]

    def _al_elegir_miniatura(self, _event) -> None:
        with wx.FileDialog(
                self, "Elegir miniatura", wildcard=_FILTRO_IMAGENES,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        error = error_de_miniatura(ruta)
        if error:
            anunciar(error)
            return
        self._miniatura = ruta
        nombre = os.path.basename(ruta)
        self.txt_miniatura.SetValue(nombre)
        anunciar("Miniatura: " + nombre)

    def _al_quitar_miniatura(self, _event) -> None:
        self._miniatura = ""
        self.txt_miniatura.SetValue("Ninguna")
        anunciar("Sin miniatura.")

    def _al_cargar_listas(self, _event) -> None:
        self.btn_cargar_listas.Disable()
        anunciar("Cargando las listas.")

        def _traer():
            try:
                listas = self._cargar_listas()
            except Exception as exc:
                wx.CallAfter(self._listas_fallo, exc)
                return
            wx.CallAfter(self._listas_ok, listas)

        diagnostico.crear_hilo(_traer, "ListasYouTube").start()

    def _listas_ok(self, listas) -> None:
        if not self:
            return
        self.btn_cargar_listas.Enable()
        id_elegido, titulo_elegido = self._opcion_lista_elegida()
        self._opciones_lista, seleccion = opciones_lista(
            listas, id_elegido, titulo_elegido)
        self.cho_lista.SetItems([texto for _id, texto in self._opciones_lista])
        self.cho_lista.SetSelection(seleccion)
        if not listas:
            anunciar("El canal no tiene listas.")
        elif len(listas) == 1:
            anunciar("1 lista.")
        else:
            anunciar(f"{len(listas)} listas.")

    def _listas_fallo(self, exc) -> None:
        if not self:
            return
        self.btn_cargar_listas.Enable()
        anunciar("No se pudieron cargar las listas: "
                 + youtube_api.mensaje_error_api(exc))

    def _al_crear(self, _event) -> None:
        lista, lista_titulo = self._opcion_lista_elegida()
        try:
            self._datos = resultado_directo(
                self.txt_titulo.GetValue(),
                self.txt_descripcion.GetValue(),
                self._privacidad_elegida(),
                self._latencia_elegida(),
                self.chk_ninos.GetValue(),
                self.chk_dvr.GetValue(),
                self._categoria_elegida(),
                self.txt_etiquetas.GetValue(),
                self._miniatura,
                lista,
                lista_titulo)
        except EmisionError as exc:
            anunciar(str(exc))
            self.txt_titulo.SetFocus()
            return
        self.EndModal(wx.ID_OK)

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_datos_directo(padre, titulo="", descripcion="",
                        privacidad=PRIVACIDAD_INICIAL, revision=None,
                        latencia=LATENCIA_INICIAL, ninos=False, dvr=True,
                        categoria="", etiquetas="", miniatura="", lista="",
                        lista_titulo="", cargar_listas=None):
    """Pide los datos del directo. Devuelve el dict o None si se cancela."""
    dialogo = DialogoDirectoYoutube(
        padre, titulo, descripcion, privacidad, revision, latencia,
        ninos, dvr, categoria, etiquetas, miniatura, lista, lista_titulo,
        cargar_listas)
    try:
        if dialogo.ShowModal() == wx.ID_OK:
            return dialogo.datos
        return None
    finally:
        dialogo.Destroy()

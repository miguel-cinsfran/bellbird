"""Página API y sesión del diálogo de Preferencias.

Dueña de sus campos, del inicio y del cierre de sesión. El diálogo la
construye por composición y no copia ninguno de sus controles.
"""

from __future__ import annotations

import webbrowser

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.tema import _T, _tc
from bellbird.ui.preferencias_comun import ANCHO_NOTA, crear_panel
from bellbird.voice import sound_player as _snd
from bellbird.youtube import credenciales
from bellbird.youtube import youtube_api

logger = diagnostico.obtener_logger(__name__)


URL_GUIA = "https://github.com/miguel-cinsfran/bellbird/blob/main/docs/CONFIGURACION_API.md"


class PaginaApi:
    """Página API y sesión: claves, inicio y cierre de sesión."""

    def __init__(self, ventana):
        self._ventana = ventana
        self._login_en_curso = False

    def construir(self, parent):
        p = crear_panel(parent, "PagApi")
        vs = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(p, name="IntroApi", label=_(
            "La clave de API permite leer comentarios sin iniciar sesión. Con la sesión "
            "iniciada también se puede moderar el chat, enviar mensajes y comentar."))
        intro.SetForegroundColour(_T.dim)
        intro.Wrap(ANCHO_NOTA)
        vs.Add(intro, 0, wx.ALL, 10)

        if not youtube_api.google_disponible():
            # Traductores: no traduzcas el comando «pip install ...», solo el resto.
            aviso = wx.StaticText(p, name="AvisoLibreriasApi", label=_(
                "AVISO: faltan las bibliotecas de la API. Instálalas con:\n"
                "pip install google-api-python-client google-auth-oauthlib"))
            aviso.SetForegroundColour(_T.red)
            vs.Add(aviso, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        datos = credenciales.cargar()
        grid = wx.FlexGridSizer(3, 2, 8, 8)
        grid.AddGrowableCol(1, 1)
        self.txt_api = self._fila_api(p, grid, _("Clave de &API:"), _("Clave de API de YouTube"),
                                      datos.get("api_key", ""))
        self.txt_cid = self._fila_api(p, grid, _("ID de &cliente OAuth:"),
                                      _("ID de cliente OAuth"), datos.get("oauth_client_id", ""))
        self.txt_secret = self._fila_api(p, grid, _("&Secreto de cliente OAuth:"),
                                         _("Secreto de cliente OAuth"),
                                         datos.get("oauth_client_secret", ""), password=True)
        vs.Add(grid, 0, wx.EXPAND | wx.ALL, 10)

        self.lbl_estado_api = wx.StaticText(p, name="EstadoSesion", label="")
        self.lbl_estado_api.SetForegroundColour(_T.accent)
        vs.Add(self.lbl_estado_api, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._botones(p, vs)
        p.SetSizer(vs)
        self._api_refrescar_estado()
        return p

    def _botones(self, p, vs):
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_api_guardar = wx.Button(p, label=_("&Guardar claves"), name="GuardarClaves")
        self.btn_api_login   = wx.Button(p, label=_("&Iniciar sesión"), name="IniciarSesion")
        self.btn_api_logout  = wx.Button(p, label=_("Cerrar s&esión"), name="CerrarSesion")
        self.btn_api_guia    = wx.Button(p, label=_("Abrir g&uía"), name="AbrirGuia")
        for b in (self.btn_api_guardar, self.btn_api_login, self.btn_api_logout, self.btn_api_guia):
            b.SetBackgroundColour(_T.btn)
            b.SetForegroundColour(_T.btn_t)
            row.Add(b, 0, wx.RIGHT, 6)
        vs.Add(row, 0, wx.ALL, 10)

        self.btn_api_guardar.Bind(wx.EVT_BUTTON, self._api_guardar)
        self.btn_api_login.Bind(wx.EVT_BUTTON, self._api_login)
        self.btn_api_logout.Bind(wx.EVT_BUTTON, self._api_logout)
        self.btn_api_guia.Bind(wx.EVT_BUTTON, lambda e: webbrowser.open(URL_GUIA))

    def _fila_api(self, p, grid, etiqueta, nombre, valor, password=False):
        lbl = wx.StaticText(p, label=etiqueta)
        lbl.SetForegroundColour(_T.text)
        estilo = wx.TE_PASSWORD if password else 0
        txt = wx.TextCtrl(p, value=valor or "", style=estilo, name=nombre)
        _tc(txt)
        grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(txt, 1, wx.EXPAND)
        return txt

    def _api_refrescar_estado(self):
        if credenciales.hay_sesion():
            texto = _("Estado: sesión iniciada. Moderación y comentarios activos.")
            self.btn_api_logout.Enable()
        else:
            texto = _("Estado: sin sesión. Solo lectura de comentarios (si hay clave de API).")
            self.btn_api_logout.Disable()
        if credenciales.usa_cliente_de_la_app():
            texto += _(" Se usa el cliente de Google de la aplicación.")
        if not youtube_api.google_disponible():
            self.btn_api_login.Disable()
        self.lbl_estado_api.SetLabel(texto)

    def _api_guardar(self, event):
        credenciales.guardar_campo("api_key", self.txt_api.GetValue().strip())
        credenciales.guardar_campo("oauth_client_id", self.txt_cid.GetValue().strip())
        credenciales.guardar_campo("oauth_client_secret", self.txt_secret.GetValue().strip())
        _snd.reproducir("copiar")
        anunciar(_("Claves guardadas"))
        self._api_refrescar_estado()

    def _api_login(self, event):
        if self._login_en_curso:
            return
        cid = self.txt_cid.GetValue().strip()
        secret = self.txt_secret.GetValue().strip()
        if not (cid and secret):
            # Sin cliente propio, vale el que trae la app: la persona solo
            # pulsa «Iniciar sesión», sin guardar nada en sus campos.
            efectivas = credenciales.efectivas()
            cid_app = (efectivas.get("oauth_client_id") or "").strip()
            secret_app = (efectivas.get("oauth_client_secret") or "").strip()
            if not (cid_app and secret_app):
                wx.MessageBox(_("Rellena el ID y el secreto de cliente OAuth antes de "
                                "iniciar sesión."), _("Faltan datos"), wx.OK | wx.ICON_WARNING,
                              self._ventana)
                return
            cid, secret = cid_app, secret_app
        else:
            self._api_guardar(None)
        self._login_en_curso = True
        self.btn_api_login.Disable()
        anunciar(_("Abriendo el navegador para iniciar sesión. Autoriza y vuelve aquí."))

        def _run():
            try:
                token = youtube_api.iniciar_sesion(cid, secret)
                credenciales.guardar_campo("token", token)
                wx.CallAfter(self._api_login_ok)
            except Exception as exc:
                logger.warning("Login OAuth falló: %s", exc)
                wx.CallAfter(self._api_login_err, exc)

        diagnostico.crear_hilo(_run, "OAuthLogin").start()

    def _api_login_ok(self):
        if not self._ventana:   # el diálogo pudo cerrarse mientras se autorizaba
            return
        self._login_en_curso = False
        self.btn_api_login.Enable()
        _snd.reproducir("conectado")
        anunciar(_("Sesión iniciada correctamente."))
        self._api_refrescar_estado()

    def _api_login_err(self, exc):
        if not self._ventana:
            return
        self._login_en_curso = False
        self.btn_api_login.Enable()
        _snd.reproducir("error")
        anunciar(_("No se pudo iniciar sesión."))
        wx.MessageBox(_("No se pudo iniciar sesión:\n\n{exc}").format(exc=exc), _("Error de inicio de sesión"),
                      wx.OK | wx.ICON_ERROR, self._ventana)

    def _api_logout(self, event):
        credenciales.cerrar_sesion()
        _snd.reproducir("desconectado")
        anunciar(_("Sesión cerrada."))
        self._api_refrescar_estado()

"""Adaptador entre la captura y la ventana principal.

La captura (ytchat.capture.conexion) no conoce wx ni la ventana: le habla
a VistaGui, que resuelve el marco global en cada llamada y programa con
wx.CallAfter el método que antes se llamaba directo. Sin marco, o con el
marco ya cerrado donde hoy se comprobaba, no hace nada.

Cada método devuelve si llegó a programar la llamada, para que la captura
conserve sus guardas (por ejemplo, el sonido de «conectado» en un vídeo
subido solo suena si había marco).
"""

from ytchat.core.config import TIPO_TEXTO


def _marco():
    from ytchat.ui import gui as _gm
    return _gm._gui_frame


def _marco_vivo():
    marco = _marco()
    if marco and marco._alive:
        return marco
    return None


class VistaGui:
    """Adaptador sin estado propio hacia el marco global."""

    @property
    def activa(self):
        """Si hay marco vivo (lo que hoy se comprobaba con _alive)."""
        return _marco_vivo() is not None

    def _programar(self, nombre_metodo, solo_si_vivo, *args, **kwargs):
        marco = _marco_vivo() if solo_si_vivo else _marco()
        if not marco:
            return False
        import wx
        wx.CallAfter(getattr(marco, nombre_metodo), *args, **kwargs)
        return True

    def url_invalida(self):
        return self._programar("url_invalida", False)

    def agregar_mensaje(self, autor, mensaje, hora, tipo=TIPO_TEXTO,
                        monto="", canal_id="", plataforma="", rol=""):
        return self._programar("agregar_mensaje_chat", True, autor, mensaje,
                               hora, tipo, monto, canal_id,
                               plataforma=plataforma, rol=rol)

    def set_conectado(self, conectado, sonido=None):
        if sonido is None:
            return self._programar("set_conectado", True, conectado)
        return self._programar("set_conectado", True, conectado, sonido)

    def set_conectado_si_existe(self, conectado, sonido=None):
        if sonido is None:
            return self._programar("set_conectado", False, conectado)
        return self._programar("set_conectado", False, conectado, sonido)

    def set_titulo(self, titulo):
        return self._programar("set_titulo_stream", True, titulo)

    def set_titulo_si_existe(self, titulo):
        return self._programar("set_titulo_stream", False, titulo)

    def set_tipo_video(self, tipo, vid):
        return self._programar("set_tipo_video", True, tipo, vid)

    def set_tipo_video_si_existe(self, tipo, vid):
        return self._programar("set_tipo_video", False, tipo, vid)

    def set_metadatos(self, meta):
        return self._programar("set_metadatos", True, meta)

    def set_metadatos_si_existe(self, meta):
        return self._programar("set_metadatos", False, meta)

    def registrar_historial(self, plataforma, clave, url, titulo, canal,
                            directo=False):
        return self._programar("registrar_historial", True, plataforma,
                               clave, url, titulo, canal, directo)

    def registrar_historial_si_existe(self, plataforma, clave, url, titulo,
                                      canal, directo=False):
        return self._programar("registrar_historial", False, plataforma,
                               clave, url, titulo, canal, directo)

    def set_espectadores(self, n):
        return self._programar("set_espectadores", True, n)

    def set_inicio_directo(self, comienzo):
        return self._programar("set_inicio_directo", True, comienzo)

    def configurar_tiktok(self, usuario, url):
        return self._programar("configurar_tiktok", True, usuario, url)

    def anunciar(self, texto):
        if _marco_vivo() is None:
            return False
        import wx
        from ytchat.ui.gui import anunciar
        wx.CallAfter(anunciar, texto)
        return True

    def fallo_video(self, metadatos):
        if not _marco():
            return False
        import wx
        import main
        main._anunciar_fallo_video(metadatos, wx.CallAfter)
        return True

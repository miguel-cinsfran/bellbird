"""Cuándo un relevo de directo está roto y hay que reiniciarlo.

La decisión es pura: recibe la hora, el estado del panel y los callbacks, y
no toca wx ni el reproductor. `conectar` es el adaptador que traduce esas
decisiones a llamadas del panel. El relevo de un directo se reinicia con las
mismas fuentes y el mismo desfase, sin volver a resolver el vídeo.
"""

from __future__ import annotations

import re
import time

from bellbird.core.idioma import N_, _

REINICIAR = "reiniciar"
AVISAR = "avisar"
NADA = "nada"

CORTES_PARA_REINICIAR = 3
VENTANA_CORTES = 60.0
MAX_REINICIOS = 3
VENTANA_REINICIOS = 600.0
ESPERA_ENTRE_MOTIVOS = 20.0

_FRASE_RECONEXION = N_("Reconectando el directo")
_FRASE_CORTES = N_("El directo sigue con cortes. Vuelve a cargarlo si no mejora.")


def aviso_de_corte(pct, pct_anterior) -> str:
    """Devuelve avisos solo al empezar y recuperarse un corte de búfer."""
    if pct < 100 and (pct_anterior is None or pct_anterior >= 100):
        return f"VLC_CORTE empezó porcentaje={pct:.0f}"
    if pct >= 100 and pct_anterior is not None and pct_anterior < 100:
        return "VLC_CORTE recuperado"
    return ""


def entrada_de_error(texto: str, dos_entradas: bool) -> str:
    """Entrada de ffmpeg que falló, si el relevo tiene dos entradas."""
    if not dos_entradas:
        return ""
    marca = re.search(r"in#(\d+)", texto)
    if marca is None:
        return "mixta"
    return {"0": "video", "1": "audio"}.get(marca.group(1), "mixta")


def _parece_error(texto: str) -> bool:
    return "error during demuxing" in texto.lower()


class Nada:
    """Vigilancia inerte para paneles de prueba y caminos sin relevo."""

    def buffer(self, pct, pct_anterior):
        return aviso_de_corte(pct, pct_anterior)

    def corte(self, instante=None):
        return NADA

    def aviso(self, texto, instante=None):
        return NADA

    def registrar_vuelta(self, instante):
        return ""

    def olvidar(self):
        return None


NADA_OBJETO = Nada()


class Vigilancia:
    """Decide si un corte o un error de ffmpeg se convierte en reinicio."""

    def __init__(self, reabrir, anunciar, sonar, despachar,
                 activo=lambda: True, dos_entradas=lambda: True,
                 reloj=time.monotonic):
        self.activo = activo
        self.dos_entradas = dos_entradas
        self._reabrir = reabrir
        self._anunciar = anunciar
        self._sonar = sonar
        self._despachar = despachar
        self._reloj = reloj
        self._cortes = []
        self._reinicios = []
        self._ultimo = None
        self._avisado = False
        self._pendiente = None

    def olvidar(self):
        """Empieza de cero para el próximo vídeo o la próxima carga."""
        self._cortes = []
        self._reinicios = []
        self._ultimo = None
        self._avisado = False
        self._pendiente = None

    def buffer(self, pct, pct_anterior):
        aviso = aviso_de_corte(pct, pct_anterior)
        if aviso.startswith("VLC_CORTE empezó"):
            self.corte()
        return aviso

    def corte(self, instante=None):
        self._despachar(
            self._procesar_corte,
            self._reloj() if instante is None else instante)

    def aviso(self, texto, instante=None):
        self._despachar(
            self._procesar_aviso, texto,
            self._reloj() if instante is None else instante)

    def registrar_vuelta(self, instante):
        pendiente = self._pendiente
        if pendiente is None:
            return ""
        self._pendiente = None
        marca, motivo, entrada, desfase = pendiente
        return ("RELEVO_RECONEXION motivo=%s entrada=%s desfase=%d "
                "vuelta_ms=%.0f" % (motivo, entrada or "unica", desfase,
                                    (instante - marca) * 1000))

    def _procesar_corte(self, instante):
        if self._avisado or not self.activo():
            return NADA
        if self._ultimo is not None \
                and instante - self._ultimo < ESPERA_ENTRE_MOTIVOS:
            return NADA
        self._cortes = [t for t in self._cortes
                        if instante - t < VENTANA_CORTES]
        self._cortes.append(instante)
        if len(self._cortes) < CORTES_PARA_REINICIAR:
            return NADA
        return self._reconectar("buffer", "ninguna", instante)

    def _procesar_aviso(self, texto, instante):
        if self._avisado or not self.activo() or not _parece_error(texto):
            return NADA
        if self._ultimo is not None \
                and instante - self._ultimo < ESPERA_ENTRE_MOTIVOS:
            return NADA
        dos = self.dos_entradas()
        if not isinstance(dos, bool):
            dos = bool(dos)
        entrada = entrada_de_error(texto, dos)
        return self._reconectar("error", entrada, instante)

    def _reconectar(self, motivo, entrada, instante):
        self._reinicios = [t for t in self._reinicios
                           if instante - t < VENTANA_REINICIOS]
        if len(self._reinicios) >= MAX_REINICIOS:
            self._avisar(instante)
            return AVISAR
        frase = _(_FRASE_RECONEXION)
        desfase = self._reabrir(None, frase)
        if desfase is None:
            return NADA
        self._reinicios.append(instante)
        self._ultimo = instante
        self._cortes = []
        self._pendiente = (instante, motivo, entrada, int(desfase))
        self._anunciar(frase)
        self._sonar("reconectando_directo")
        return REINICIAR

    def _avisar(self, instante):
        if self._avisado:
            return
        self._avisado = True
        self._ultimo = instante
        self._anunciar(_(_FRASE_CORTES))
        self._sonar("directo_con_cortes")


def conectar(panel, anunciar, despachar):
    """Instala la vigilancia sobre un panel del reproductor."""
    from bellbird.voice import sound_player as _snd

    def fuentes():
        return getattr(panel, "_relevo_fuentes", None) or ("", "")

    def activo():
        try:
            return (getattr(panel, "_relevo_ffmpeg", None) is not None
                    and not getattr(panel, "_cargando", False)
                    and not getattr(panel, "_vod_por_relevo", False)
                    and not getattr(panel, "_url_flujo", "")
                    and panel._es_directo_actual())
        except Exception:
            return False

    def dos_entradas():
        return bool(fuentes()[1])

    def reabrir(desfase, anuncio):
        if not activo():
            return None
        url, slave = fuentes()
        if not url:
            return None
        if desfase is None:
            desfase = int(getattr(panel, "_relevo_desfase", 0) or 0)
        panel._cancelar_busqueda()
        panel._cancelar_transporte()
        panel._detener_relevo_ffmpeg()
        panel._relevo_fuentes = (url, slave)
        panel._arrancar_relevo(url, slave, True, desfase=int(desfase),
                               anuncio=anuncio)
        return int(desfase)

    return Vigilancia(reabrir, anunciar, _snd.reproducir, despachar,
                      activo, dos_entradas)

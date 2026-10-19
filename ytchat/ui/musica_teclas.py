"""Teclas de música: silencio y saltos de diez segundos."""

from __future__ import annotations

from ytchat.music import anuncios
from ytchat.music import anuncios_teclas


class TeclasMusica:
    """Silencio y saltos compartidos por el menú, los atajos y la ventana."""

    def acciones_musica(self) -> dict:
        """Acción de música → método, para el menú, los atajos y los globales."""
        return {
            "musica_play": self.reproducir_o_pausar,
            "musica_siguiente": self.siguiente,
            "musica_anterior": self.anterior,
            "musica_vol_mas": self.subir_volumen,
            "musica_vol_menos": self.bajar_volumen,
            "musica_que_suena": self.que_suena,
            "musica_silenciar": self.alternar_silencio,
            "musica_aleatorio": self.alternar_aleatorio,
            "musica_repetir": self.ciclar_repetir,
            "musica_detener": self.detener,
            "musica_adelantar": self.adelantar,
            "musica_retroceder": self.retroceder,
        }

    def alternar_silencio(self) -> None:
        """Silencia o devuelve el sonido, y pone la casilla al día."""
        if self._coordinador is None:
            self._accion_coordinador("detener")
            return
        activo = not self._coordinador.silenciado
        resultado = self._coordinador.fijar_silencio(activo)
        if not resultado.ok:
            self._avisar(anuncios.aviso_accion(
                "detener", resultado, self._incluir_artista()))
            return
        self._sincronizar_silencio(activo)
        self._avisar(anuncios_teclas.aviso_silencio(activo))
        self._refrescar_ventana_abierta()

    def adelantar(self) -> None:
        """Salta diez segundos hacia adelante."""
        self._saltar(10_000)

    def retroceder(self) -> None:
        """Salta diez segundos hacia atrás."""
        self._saltar(-10_000)

    def _saltar(self, delta_ms) -> None:
        if self._coordinador is None:
            self._accion_coordinador("detener")
            return
        salto = self._coordinador.saltar(delta_ms)
        if salto.ok:
            self._avisar(anuncios_teclas.aviso_posicion(salto.posicion_ms))
        else:
            self._avisar(anuncios.aviso_accion(
                "detener", salto, self._incluir_artista()))
        self._refrescar_ventana_abierta()

    def _sincronizar_silencio(self, activo=None) -> None:
        """Marca la casilla del menú con el estado real del coordinador."""
        if activo is None:
            activo = bool(self._coordinador is not None
                          and self._coordinador.silenciado)
        item = getattr(self._frame, "mi_musica_silenciar", None)
        if item is not None:
            item.Check(bool(activo))

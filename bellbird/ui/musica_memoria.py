"""Memoria de la música: retomar al arrancar y recordar la cola."""

from __future__ import annotations

from bellbird.core import paths
from bellbird.music import anuncios
from bellbird.music import memoria


class MemoriaMusica:
    """Memoria de la música: retomar al arrancar y recordar la cola."""

    def cola_visible(self) -> bool:
        """Si la Cola de la ventana de música quedó visible."""
        return bool(self._config.get("musica_mostrar_cola", False))

    def recordar_cola_visible(self, visible) -> None:
        """Recuerda si la Cola quedó visible u oculta."""
        self._guardar("mostrar_cola", "true" if visible else "false")
        self._config["musica_mostrar_cola"] = bool(visible)

    def filtros_guardados(self):
        """Si los filtros quedaron visibles, el artista y el orden."""
        return (
            bool(self._config.get("musica_mostrar_filtros", False)),
            str(self._config.get("musica_artista", "") or ""),
            str(self._config.get("musica_orden", "coleccion") or "coleccion"),
        )

    def recordar_filtros(self, visibles, artista, orden) -> None:
        """Recuerda la visibilidad de los filtros, el artista y el orden."""
        self._guardar("mostrar_filtros", "true" if visibles else "false")
        self._guardar("artista", str(artista or ""))
        self._guardar("orden", str(orden or "coleccion"))
        self._config["musica_mostrar_filtros"] = bool(visibles)
        self._config["musica_artista"] = str(artista or "")
        self._config["musica_orden"] = str(orden or "coleccion")

    def _primera_vez(self) -> bool:
        """En el primer Reproducir de la sesión, retoma si hay memoria.

        Dice si se ocupó de arrancar la música desde la memoria guardada, para
        no seguir con la carpeta. La memoria se intenta una sola vez por
        sesión: después de eso, reproducir vuelve a la carpeta como siempre.
        """
        if self._retomo_intentado:
            return False
        self._retomo_intentado = True
        if not self._retomar_activo():
            return False
        guardada = memoria.leer(self._ruta_memoria())
        if guardada is None:
            return False
        temas, posicion = guardada
        self._asegurar_motor(lambda: self._retomar(temas, posicion))
        return True

    def _retomar(self, temas, posicion) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(
            temas, en_orden=True, desde=posicion)
        actual = self._coordinador.estado().actual
        if resultado.ok and actual is not None:
            self._avisar(anuncios.aviso_retomando(
                anuncios.nombre_tema(actual, self._incluir_artista()),
                len(temas)))
            self._guardar_memoria()
            return
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))

    def _guardar_memoria(self) -> None:
        """Recuerda la cola y el tema tras un cambio, o limpia la memoria.

        Con `musica_retomar` apagada no se guarda nada y se borra el archivo
        si existe. Se escribe un segundo después del último cambio, salvo al
        cerrar, que se vacía en el acto. Nunca lanza.
        """
        self._guardado_memoria.pedir(self._escribir_memoria)

    def _escribir_memoria(self) -> None:
        if not self._retomar_activo():
            memoria.guardar(self._ruta_memoria(), None)
            return
        memoria.guardar(self._ruta_memoria(), self.estado())

    def _retomar_activo(self) -> bool:
        return bool(self._config.get("musica_retomar", True))

    def _ruta_memoria(self):
        return paths.estado_musica()

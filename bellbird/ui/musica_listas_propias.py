"""Listas de música propias: guardar, cargar y editar sus temas."""

from __future__ import annotations

from bellbird.core import paths
from bellbird.music import anuncios
from bellbird.music import listas


class ListasPropiasMusica:
    """Listas de música propias: guardar, cargar y editar sus temas."""

    def carpeta_listas(self):
        """La carpeta donde viven las listas de música propias."""
        return paths.listas_musica()

    def reproducir_lista_guardada(self, nombre) -> None:
        """Reproduce una lista guardada, avisando si se saltaron entradas.

        La preferencia de orden aleatorio decide si se mezcla, igual que al
        reproducir la carpeta.
        """
        try:
            temas, faltantes = listas.cargar(self.carpeta_listas(), nombre)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        if faltantes:
            self._avisar(anuncios.aviso_faltantes(faltantes))
        self.reproducir_temas(temas)

    # ── Listas propias ───────────────────────────────────────────────────────

    def guardar_cola_como_lista(self, nombre) -> None:
        """Guarda la cola actual como una lista propia."""
        temas = self.cola_actual()
        if not temas:
            self._avisar(anuncios.aviso_sin_cola())
            return
        try:
            limpio = listas.guardar(self.carpeta_listas(), nombre, temas)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_lista_guardada(limpio))

    def guardar_lista(self, nombre, temas, viejo=None) -> None:
        """Crea o edita una lista con los temas marcados en el editor."""
        carpeta = self.carpeta_listas()
        try:
            if viejo is None:
                limpio = listas.crear(carpeta, nombre)
            else:
                limpio = listas.renombrar(carpeta, viejo, nombre)
            limpio = listas.guardar(carpeta, limpio, tuple(temas))
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_lista_guardada(limpio))

    def agregar_a_lista(self, nombre, temas) -> None:
        """Suma temas al final de una lista que ya existe."""
        try:
            listas.agregar(self.carpeta_listas(), nombre, tuple(temas))
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_agregado_a_lista(nombre))

    def quitar_de_lista(self, nombre, indice) -> None:
        """Quita un tema de una lista propia."""
        try:
            listas.quitar(self.carpeta_listas(), nombre, indice)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_tema_quitado())

    def crear_lista(self, nombre) -> None:
        """Crea una lista propia vacía."""
        try:
            limpio = listas.crear(self.carpeta_listas(), nombre)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_lista_creada(limpio))

    def renombrar_lista(self, viejo, nuevo) -> None:
        """Cambia el nombre de una lista propia."""
        try:
            limpio = listas.renombrar(self.carpeta_listas(), viejo, nuevo)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_lista_renombrada(limpio))

    def borrar_lista(self, nombre) -> None:
        """Borra una lista propia."""
        try:
            listas.borrar(self.carpeta_listas(), nombre)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_lista_borrada(nombre))

    def temas_de_lista(self, nombre):
        """Los temas de una lista propia, avisando una vez qué falta."""
        try:
            temas, faltantes = listas.cargar(self.carpeta_listas(), nombre)
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return ()
        if self._cambiaron_los_faltantes(nombre, faltantes) and faltantes:
            self._avisar(anuncios.aviso_faltantes(faltantes))
        return temas

    def _cambiaron_los_faltantes(self, nombre, faltantes) -> bool:
        """Guarda qué falta en la lista y dice si cambió desde la última vez."""
        por_lista = getattr(self, "_faltantes_por_lista", None)
        if por_lista is None:
            por_lista = {}
            self._faltantes_por_lista = por_lista
        clave = str(nombre).casefold()
        if por_lista.get(clave, ()) == faltantes:
            return False
        por_lista[clave] = faltantes
        return True

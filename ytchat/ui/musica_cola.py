"""Operaciones de la cola de música: reproducir, mover y reordenar."""

from __future__ import annotations

from ytchat.core import config as cfg
from ytchat.music import anuncios
from ytchat.music.modelo import FIN_LISTA


class ColaMusica:
    """Operaciones de la cola de música: reproducir, mover y reordenar."""

    def reproducir_temas(self, temas, en_orden: bool = False) -> None:
        """Pone la lista como cola y empieza por el primer tema."""
        self._asegurar_motor(lambda: self._iniciar_lista(tuple(temas), en_orden))

    def reproducir_temas_desde(self, temas, indice) -> None:
        """Pone la lista como cola, en orden, y empieza por el elegido.

        Así, al terminar el elegido, sigue con los siguientes del resultado.
        """
        self._asegurar_motor(
            lambda: self._iniciar_lista_desde(tuple(temas), indice))

    def agregar_temas(self, temas) -> None:
        """Suma la lista al final de la cola sin cortar lo que suena."""
        self._asegurar_motor(lambda: self._agregar_a_la_cola(tuple(temas)))

    def reproducir_a_continuacion(self, tema) -> None:
        """Mete el tema justo detrás del que suena, sin cortar nada."""
        self._asegurar_motor(lambda: self._poner_a_continuacion(tema))

    def reproducir_desde(self, indice) -> None:
        """Empieza por el tema de la cola actual que ocupa ese índice."""
        self._asegurar_motor(lambda: self._reproducir_de_la_cola(indice))

    # ── Operaciones de la cola de la ventana nueva ───────────────────────────

    def reproducir_ahora(self, temas) -> None:
        """Mete la lista detrás del tema actual y empieza por el primero."""
        self._asegurar_motor(
            lambda: self._reproducir_ahora(tuple(temas)))

    def poner_a_continuacion(self, temas) -> None:
        """Mete la lista justo detrás de lo que suena, sin cortar nada."""
        self._asegurar_motor(
            lambda: self._poner_varios_a_continuacion(tuple(temas)))

    def agregar_al_final(self, temas) -> None:
        """Suma la lista al final de la cola sin cortar lo que suena."""
        self._asegurar_motor(
            lambda: self._agregar_al_final(tuple(temas)))

    def reproducir_desde_aqui(self, temas, indice) -> None:
        """Reemplaza la cola con la lista y empieza por el tema elegido."""
        self._asegurar_motor(
            lambda: self._iniciar_lista_desde(tuple(temas), indice))

    def quitar_de_cola(self, indice) -> None:
        """Quita un tema de la cola y avisa cuál salió."""
        self._asegurar_motor(lambda: self._quitar_de_la_cola(indice))

    def mover_en_cola(self, indice, paso) -> None:
        """Mueve un tema un paso en la cola y avisa la posición nueva."""
        self._asegurar_motor(
            lambda: self._mover_en_la_cola(indice, paso))

    def vaciar_cola(self) -> None:
        """Deja solo lo que suena, o vacía la cola si no hay nada activo."""
        self._asegurar_motor(self._vaciar_la_cola)

    def mezclar_cola(self) -> None:
        """Reordena al azar la cola visible dejando el actual primero."""
        self._asegurar_motor(self._mezclar_la_cola)

    def fijar_repetir(self, modo) -> None:
        """Guarda y anuncia el modo de repetición, y lo aplica si hay motor."""
        modo = cfg.normalizar_repetir(modo)
        self._config["musica_repetir"] = modo
        self._guardar("repetir", modo)
        if self._coordinador is not None:
            self._coordinador.fijar_repetir(modo)
        self._avisar(anuncios.aviso_repetir(modo))
        self._refrescar_ventana_abierta()

    def ciclar_repetir(self) -> None:
        """Pasa de "no" a "todo" a "tema" y vuelve a "no"."""
        siguiente = {"no": "todo", "todo": "tema", "tema": "no"}
        actual = cfg.normalizar_repetir(
            self._config.get("musica_repetir", "no"))
        self.fijar_repetir(siguiente[actual])

    def _iniciar_lista(self, temas, en_orden) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(temas, en_orden=en_orden)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))
        self._guardar_memoria()

    def _iniciar_lista_desde(self, temas, indice) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(
            temas, en_orden=True, desde=indice)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))
        self._guardar_memoria()

    def _agregar_a_la_cola(self, temas) -> None:
        if self._coordinador is None:
            return
        antes = self._coordinador.estado()
        resultado = self._coordinador.agregar(temas)
        if resultado.ok:
            self._avisar_agregado(temas, antes, resultado)
            return
        self._avisar(anuncios.aviso_accion(
            "agregar", resultado, self._incluir_artista()))

    def _poner_a_continuacion(self, tema) -> None:
        if self._coordinador is None:
            return
        antes = self._coordinador.estado()
        resultado = self._coordinador.a_continuacion((tema,))
        if resultado.ok:
            if antes.posicion is not None and not antes.terminado:
                self._avisar(anuncios.aviso_a_continuacion(
                    tema, self._incluir_artista()))
            else:
                self._avisar_agregado((tema,), antes, resultado)
            return
        self._avisar(anuncios.aviso_accion(
            "agregar", resultado, self._incluir_artista()))

    def _reproducir_de_la_cola(self, indice) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_desde(indice)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))
        self._guardar_memoria()

    def _reproducir_ahora(self, temas) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_ahora(temas)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))
        self._guardar_memoria()

    def _poner_varios_a_continuacion(self, temas) -> None:
        if self._coordinador is None:
            return
        antes = self._coordinador.estado()
        resultado = self._coordinador.a_continuacion(temas)
        if resultado.ok:
            if antes.posicion is None or antes.terminado:
                self._avisar_agregado(temas, antes, resultado)
            else:
                posicion = self._indice_insertado(antes, resultado) + 1
                if len(temas) == 1:
                    self._avisar(anuncios.aviso_a_continuacion_posicion(
                        temas[0], posicion, self._incluir_artista()))
                else:
                    self._avisar(anuncios.aviso_a_continuacion_varios(
                        len(temas), posicion))
        else:
            self._avisar(anuncios.aviso_accion(
                "agregar", resultado, self._incluir_artista()))
        self._guardar_memoria()

    @staticmethod
    def _indice_insertado(antes, resultado) -> int:
        """Índice del primer tema nuevo, comparando por identidad."""
        i = j = 0
        despues = resultado.estado.cola
        while i < len(despues) and j < len(antes.cola):
            if despues[i] is antes.cola[j]:
                i += 1
                j += 1
            else:
                return i
        return i

    def _avisar_agregado(self, temas, antes, resultado) -> None:
        """Avisa lo sumado; si con eso arranca la música, dice qué suena."""
        activo = antes.posicion is not None and not antes.terminado
        sonando = None
        if not activo:
            actual = resultado.estado.actual
            if actual is not None:
                sonando = anuncios.nombre_tema(
                    actual, self._incluir_artista())
        if len(temas) == 1:
            self._avisar(anuncios.aviso_agregado_posicion(
                len(antes.cola) + 1, sonando))
        else:
            self._avisar(anuncios.aviso_agregados(len(temas), sonando))

    def _agregar_al_final(self, temas) -> None:
        if self._coordinador is None:
            return
        antes = self._coordinador.estado()
        resultado = self._coordinador.agregar(temas)
        if resultado.ok:
            self._avisar_agregado(temas, antes, resultado)
        else:
            self._avisar(anuncios.aviso_accion(
                "agregar", resultado, self._incluir_artista()))

    def _quitar_de_la_cola(self, indice) -> None:
        if self._coordinador is None:
            return
        antes = self._coordinador.estado()
        quitado = None
        if (not isinstance(indice, bool) and isinstance(indice, int)
                and 0 <= indice < len(antes.cola)):
            quitado = antes.cola[indice]
        resultado = self._coordinador.quitar(indice)
        if resultado.ok and quitado is not None:
            nombre = anuncios.nombre_tema(quitado, self._incluir_artista())
            texto = anuncios.TEXTO_QUITADO_COLA.format(nombre=nombre)
            nuevo = resultado.estado.actual
            if (indice == antes.posicion and nuevo is not None
                    and not resultado.estado.terminado):
                texto += ". " + anuncios.nombre_tema(
                    nuevo, self._incluir_artista())
            self._avisar(anuncios.Aviso(texto))
        elif resultado.codigo == FIN_LISTA:
            self._avisar(anuncios.Aviso(anuncios.TEXTO_FIN_LISTA))
        else:
            self._avisar(anuncios.aviso_accion(
                "quitar", resultado, self._incluir_artista()))
            return
        self._guardar_memoria()

    def _mover_en_la_cola(self, indice, paso) -> None:
        if self._coordinador is None:
            return
        antes = self._coordinador.estado()
        valido = (not isinstance(indice, bool) and isinstance(indice, int)
                  and 0 <= indice < len(antes.cola))
        resultado = self._coordinador.mover(indice, paso)
        if not valido:
            self._avisar(anuncios.aviso_accion(
                "mover", resultado, self._incluir_artista()))
            return
        total = len(resultado.estado.cola)
        posicion = indice + 1
        if resultado.ok:
            posicion = indice + paso + 1
            self._guardar_memoria()
        self._avisar(anuncios.aviso_tema_movido(posicion, total))

    def _vaciar_la_cola(self) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.vaciar()
        actual = resultado.estado.actual
        nombre = None
        if actual is not None and not resultado.estado.terminado:
            nombre = anuncios.nombre_tema(actual, self._incluir_artista())
        self._avisar(anuncios.aviso_cola_vaciada(nombre))
        self._guardar_memoria()

    def _mezclar_la_cola(self) -> None:
        if self._coordinador is None:
            return
        self._coordinador.mezclar_cola()
        self._avisar(anuncios.aviso_cola_mezclada())
        self._guardar_memoria()

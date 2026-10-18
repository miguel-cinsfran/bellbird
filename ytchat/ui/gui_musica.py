"""Control de la música desde la interfaz: acciones, motor y avisos.

Al crearse NO toca libVLC ni el disco: el motor nace con la primera acción
que lo necesita, en un hilo, para que la ventana nunca se congele esperando a
VLC o al índice de la carpeta. Lo que no necesita wx vive en funciones puras
de arriba, con pruebas sin ventana.
"""

from __future__ import annotations

import wx

from ytchat.core import config as cfg
from ytchat.core import diagnostico
from ytchat.music import anuncios
from ytchat.music.adaptador_vlc import AdaptadorVlc, MotorNoDisponible
from ytchat.music.biblioteca import Biblioteca, ErrorBiblioteca
from ytchat.music.coordinador import Coordinador
from ytchat.music.modelo import EstadoMusica, Resultado, SIN_TEMA
from ytchat.ui.gui import anunciar
from ytchat.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)

PASO_VOLUMEN = 10
VOLUMEN_MIN = 0
VOLUMEN_MAX = 100
VOLUMEN_INICIAL = 50

# Acciones de música que la ventana reconoce por atajo mientras está abierta.
_ACCIONES_ATAJO = (
    "musica_play", "musica_siguiente", "musica_anterior",
    "musica_vol_mas", "musica_vol_menos", "musica_que_suena",
)

TEXTO_CARPETA_INEXISTENTE = (
    "No se encontró la carpeta de música. Elige otra en Preferencias, "
    "página Música")


def nuevo_volumen(actual, paso, minimo=VOLUMEN_MIN, maximo=VOLUMEN_MAX) -> int:
    """Volumen nuevo tras sumar un paso, recortado a sus límites. Función pura."""
    try:
        base = int(actual)
    except (TypeError, ValueError):
        base = minimo
    return max(minimo, min(maximo, base + paso))


def toca_pausar(estado) -> bool:
    """¿«Reproducir o pausar» pausa o reanuda en vez de empezar una lista?

    Sí si el coordinador ya tiene un tema cargado y no terminó. Función pura.
    """
    return bool(estado is not None and estado.actual is not None
                and not estado.terminado)


def _resultado_sin_tema() -> Resultado:
    return Resultado(False, SIN_TEMA,
                     EstadoMusica((), None, False, False, VOLUMEN_MAX, False))


class ControlMusica:
    """Acciones de música del menú y los atajos, con el motor en un hilo."""

    def __init__(self, frame):
        self._frame = frame
        self._config = frame._config
        self._adaptador = None
        self._coordinador = None
        self._preparando = False
        self._cerrado = False
        self._biblioteca = None
        self._ventana = None

    # ── Acciones del menú y los atajos ───────────────────────────────────────

    def reproducir_o_pausar(self) -> None:
        if self._coordinador is not None and toca_pausar(
                self._coordinador.estado()):
            self._ejecutar("pausa", self._coordinador.alternar_pausa)
            return
        if not self._carpeta():
            self._avisar(anuncios.aviso_sin_carpeta())
            return
        self._asegurar_motor(self._reproducir_carpeta)

    def siguiente(self) -> None:
        self._accion_coordinador("siguiente")

    def anterior(self) -> None:
        self._accion_coordinador("anterior")

    def detener(self) -> None:
        self._accion_coordinador("detener")

    def subir_volumen(self) -> None:
        self._cambiar_volumen(PASO_VOLUMEN)

    def bajar_volumen(self) -> None:
        self._cambiar_volumen(-PASO_VOLUMEN)

    def que_suena(self) -> None:
        if self._coordinador is None:
            self._avisar(anuncios.Aviso(anuncios.TEXTO_SIN_TEMA))
            return
        self._avisar(anuncios.aviso_que_suena(
            self._coordinador.estado(), self._incluir_artista()))

    # ── Reproducir listas y cola desde la ventana ────────────────────────────

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

    def reproducir_desde(self, indice) -> None:
        """Empieza por el tema de la cola actual que ocupa ese índice."""
        self._asegurar_motor(lambda: self._reproducir_de_la_cola(indice))

    # ── Biblioteca compartida y ventana ──────────────────────────────────────

    def biblioteca(self, al_lista) -> None:
        """Entrega la biblioteca indexada a `al_lista`.

        Sin índice todavía, o con la carpeta cambiada, indexa en un hilo y
        llama `al_lista(biblioteca)` con wx.CallAfter. Si ya estaba indexada,
        llama a `al_lista` enseguida. Si el índice no se pudo armar, entrega
        None.
        """
        if self._biblioteca is not None:
            al_lista(self._biblioteca)
            return
        carpeta = self._carpeta()
        if not carpeta:
            al_lista(None)
            return
        diagnostico.crear_hilo(
            self._indexar, "musica-indice", args=(carpeta, al_lista)).start()

    def cambiar_carpeta(self, ruta) -> None:
        """Guarda la carpeta nueva e invalida el índice compartido."""
        ruta = (ruta or "").strip()
        self._config["musica_carpeta"] = ruta
        self._biblioteca = None
        self._guardar("carpeta", cfg.codificar_texto_ini(ruta))

    def estado(self):
        """El estado del coordinador, o None si el motor todavía no nació."""
        if self._coordinador is None:
            return None
        return self._coordinador.estado()

    def incluir_artista(self) -> bool:
        """Si se muestra el artista junto al título."""
        return self._incluir_artista()

    def abrir_ventana(self) -> None:
        """Abre la ventana modal para elegir qué suena."""
        from ytchat.ui import gui_musica_ventana
        gui_musica_ventana.abrir_ventana(self)

    def registrar_ventana(self, ventana) -> None:
        """La ventana quedó abierta: hay que refrescarle la cola."""
        self._ventana = ventana

    def olvidar_ventana(self) -> None:
        """La ventana se cerró."""
        self._ventana = None

    # ── Atajos dentro de la ventana modal ────────────────────────────────────

    def combos_atajo(self) -> dict:
        """(modificadores, tecla) → acción, para los atajos de música guardados.

        La ventana modal no recibe los atajos del menú: los traduce con el
        mismo `_combo_wx` que usa el reproductor a pantalla completa.
        """
        from ytchat.player import reproductor
        atajos = cfg.parsear_atajos(self._config.get("atajos_raw", {}))
        combos = {}
        for accion in _ACCIONES_ATAJO:
            atajo = atajos.get(accion)
            if atajo is None:
                continue
            combo = reproductor._combo_wx(atajo.texto)
            if combo is not None:
                combos[combo] = accion
        return combos

    def ejecutar_atajo(self, accion) -> None:
        """Corre la acción de música de un atajo, como si viniera del menú."""
        acciones = {
            "musica_play": self.reproducir_o_pausar,
            "musica_siguiente": self.siguiente,
            "musica_anterior": self.anterior,
            "musica_vol_mas": self.subir_volumen,
            "musica_vol_menos": self.bajar_volumen,
            "musica_que_suena": self.que_suena,
        }
        funcion = acciones.get(accion)
        if funcion is not None:
            funcion()

    def alternar_aleatorio(self) -> None:
        nuevo = not bool(self._config.get("musica_aleatorio", False))
        self._config["musica_aleatorio"] = nuevo
        item = getattr(self._frame, "mi_musica_aleatorio", None)
        if item is not None:
            item.Check(nuevo)
        self._guardar("aleatorio", "true" if nuevo else "false")
        if self._coordinador is not None:
            self._coordinador.fijar_aleatorio(nuevo)
        self._avisar(anuncios.aviso_aleatorio(nuevo))

    def aplicar_preferencias(self) -> None:
        """Aplica en caliente las preferencias de música, si el motor nació.

        Volumen, salida (para el próximo tema), aleatorio y repetir. Sin motor
        no hace nada. Nunca lanza: lo llama el frame al guardar Preferencias.
        """
        if self._coordinador is None:
            return
        try:
            self._coordinador.fijar_volumen(self._volumen_config())
            if self._adaptador is not None:
                self._adaptador.fijar_dispositivo(
                    self._config.get("musica_salida") or None)
            aleatorio = bool(self._config.get("musica_aleatorio", False))
            self._coordinador.fijar_aleatorio(aleatorio)
            self._coordinador.fijar_repetir(
                bool(self._config.get("musica_repetir", False)))
            item = getattr(self._frame, "mi_musica_aleatorio", None)
            if item is not None:
                item.Check(aleatorio)
        except Exception:
            logger.exception("No se pudieron aplicar las preferencias de música")

    def cerrar(self) -> None:
        """Cierra el motor si llegó a nacer. Nunca lanza."""
        self._cerrado = True
        if self._adaptador is not None:
            try:
                self._adaptador.cerrar()
            except Exception:
                logger.exception("No se pudo cerrar el motor de música")

    # ── Motor: se prepara una sola vez, en un hilo ───────────────────────────

    def _asegurar_motor(self, continuar) -> None:
        if self._coordinador is not None:
            continuar()
            return
        if self._preparando:
            # Una segunda acción durante la preparación se descarta: lo más
            # simple es crear el motor una sola vez y no encolar nada.
            self._avisar(anuncios.aviso_preparando_ocupado())
            return
        self._preparando = True
        self._avisar(anuncios.aviso_preparando())
        diagnostico.crear_hilo(
            self._preparar_motor, "musica-motor", args=(continuar,)).start()

    def _preparar_motor(self, continuar) -> None:
        try:
            adaptador = AdaptadorVlc(
                dispositivo=self._config.get("musica_salida") or None,
                volumen=self._volumen_config())
            coordinador = Coordinador(
                adaptador, al_cambiar=self._al_cambiar,
                volumen=self._volumen_config())
            adaptador.asignar_aviso(coordinador.tema_terminado)
            coordinador.fijar_aleatorio(
                bool(self._config.get("musica_aleatorio", False)))
            coordinador.fijar_repetir(
                bool(self._config.get("musica_repetir", False)))
            adaptador.volumen(self._volumen_config())
        except MotorNoDisponible:
            wx.CallAfter(self._motor_no_disponible)
            return
        except Exception:
            logger.exception("No se pudo preparar el motor de música")
            wx.CallAfter(self._motor_no_disponible)
            return
        self._adaptador = adaptador
        self._coordinador = coordinador
        wx.CallAfter(self._motor_listo, continuar)

    def _motor_listo(self, continuar) -> None:
        self._preparando = False
        if self._cerrado:
            return
        continuar()

    def _motor_no_disponible(self) -> None:
        self._preparando = False
        self._avisar(anuncios.aviso_motor_no_disponible())

    # ── Reproducir una carpeta ───────────────────────────────────────────────

    def _reproducir_carpeta(self) -> None:
        self.biblioteca(self._reproducir_indexado)

    def _indexar(self, carpeta, al_lista) -> None:
        try:
            biblioteca = Biblioteca(carpeta)
            biblioteca.indexar()
        except ErrorBiblioteca:
            wx.CallAfter(al_lista, None)
            return
        except Exception:
            logger.exception("No se pudo indexar la carpeta de música")
            wx.CallAfter(al_lista, None)
            return
        self._biblioteca = biblioteca
        wx.CallAfter(al_lista, biblioteca)

    def _reproducir_indexado(self, biblioteca) -> None:
        if biblioteca is None:
            self._avisar(anuncios.Aviso(
                TEXTO_CARPETA_INEXISTENTE, anuncios.SONIDO_ERROR))
            return
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(biblioteca.temas())
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))

    def _iniciar_lista(self, temas, en_orden) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(temas, en_orden=en_orden)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))

    def _iniciar_lista_desde(self, temas, indice) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(temas, en_orden=True)
        if resultado.ok:
            resultado = self._coordinador.reproducir_desde(indice)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))

    def _agregar_a_la_cola(self, temas) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.agregar(temas)
        if resultado.ok:
            self._avisar(anuncios.aviso_agregados(len(temas)))
            return
        self._avisar(anuncios.aviso_accion(
            "agregar", resultado, self._incluir_artista()))

    def _reproducir_de_la_cola(self, indice) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_desde(indice)
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))

    # ── Avisos ───────────────────────────────────────────────────────────────

    def _al_cambiar(self, resultado) -> None:
        """Aviso automático del coordinador, que llega desde otro hilo."""
        wx.CallAfter(self._aviso_automatico, resultado)

    def _aviso_automatico(self, resultado) -> None:
        # Las tres preferencias se leen acá y no al preparar el motor: así un
        # cambio en Preferencias vale sin reiniciar.
        aviso = anuncios.aviso_automatico(
            resultado,
            bool(self._config.get("musica_sonido_tema", True)),
            bool(self._config.get("musica_decir_titulo", True)),
            bool(self._config.get("musica_incluir_artista", False)))
        self._avisar(aviso)
        self._refrescar_ventana_abierta()

    def _refrescar_ventana_abierta(self) -> None:
        """Pone al día la cola de la ventana si está abierta."""
        ventana = self._ventana
        if ventana is None:
            return
        try:
            ventana.refrescar_cola()
        except Exception:
            logger.debug("No se pudo refrescar la cola de la ventana de música")

    def _avisar(self, aviso) -> None:
        if aviso is None:
            return
        if aviso.sonido:
            try:
                _snd.reproducir(aviso.sonido)
            except Exception:
                logger.debug("No se pudo reproducir el sonido %s", aviso.sonido)
        if aviso.texto:
            anunciar(aviso.texto)

    # ── Interno ──────────────────────────────────────────────────────────────

    def _accion_coordinador(self, accion) -> None:
        if self._coordinador is None:
            self._avisar(anuncios.aviso_accion(
                accion, _resultado_sin_tema(), self._incluir_artista()))
            return
        operacion = getattr(self._coordinador, accion)
        self._ejecutar(accion, operacion)

    def _ejecutar(self, accion, operacion) -> None:
        resultado = operacion()
        self._avisar(anuncios.aviso_accion(
            accion, resultado, self._incluir_artista()))

    def _cambiar_volumen(self, paso) -> None:
        actual = self._config.get("musica_volumen", VOLUMEN_INICIAL)
        nuevo = nuevo_volumen(actual, paso)
        self._config["musica_volumen"] = nuevo
        self._guardar("volumen", str(nuevo))
        if self._coordinador is not None:
            self._coordinador.fijar_volumen(nuevo)
        self._avisar(anuncios.aviso_volumen(nuevo))

    def _guardar(self, clave, valor) -> None:
        try:
            from ytchat.ui import gui as _gui
            _gui.guardar_opcion(_gui.RUTA_CONFIG, "musica", clave, valor)
        except Exception:
            logger.exception("No se pudo guardar la preferencia de música")

    def _carpeta(self) -> str:
        return (self._config.get("musica_carpeta") or "").strip()

    def _incluir_artista(self) -> bool:
        return bool(self._config.get("musica_incluir_artista", False))

    def _volumen_config(self) -> int:
        return nuevo_volumen(
            self._config.get("musica_volumen", VOLUMEN_INICIAL), 0)

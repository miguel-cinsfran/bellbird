"""Control de la música desde la interfaz: acciones, motor y avisos.

Al crearse NO toca libVLC ni el disco: el motor nace con la primera acción
que lo necesita, en un hilo, para que la ventana nunca se congele esperando a
VLC o al índice de la carpeta. Lo que no necesita wx vive en funciones puras
de arriba, con pruebas sin ventana.
"""

from __future__ import annotations

import wx

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

    # ── Acciones del menú y los atajos ───────────────────────────────────────

    def reproducir_o_pausar(self) -> None:
        if self._coordinador is not None and toca_pausar(
                self._coordinador.estado()):
            self._ejecutar("pausa", self._coordinador.alternar_pausa)
            return
        carpeta = self._carpeta()
        if not carpeta:
            self._avisar(anuncios.aviso_sin_carpeta())
            return
        self._asegurar_motor(lambda: self._reproducir_carpeta(carpeta))

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

    def _reproducir_carpeta(self, carpeta) -> None:
        diagnostico.crear_hilo(
            self._indexar, "musica-indice", args=(carpeta,)).start()

    def _indexar(self, carpeta) -> None:
        try:
            biblioteca = Biblioteca(carpeta)
            biblioteca.indexar()
        except ErrorBiblioteca:
            wx.CallAfter(self._avisar, anuncios.Aviso(
                TEXTO_CARPETA_INEXISTENTE, anuncios.SONIDO_ERROR))
            return
        except Exception:
            logger.exception("No se pudo indexar la carpeta de música")
            wx.CallAfter(self._avisar, anuncios.Aviso(
                TEXTO_CARPETA_INEXISTENTE, anuncios.SONIDO_ERROR))
            return
        wx.CallAfter(self._reproducir_indexado, biblioteca.temas())

    def _reproducir_indexado(self, temas) -> None:
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(temas)
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

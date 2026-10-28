"""Control de la música desde la interfaz: acciones, motor y avisos.

Al crearse NO toca libVLC ni el disco: el motor nace con la primera acción
que lo necesita, en un hilo, para que la ventana nunca se congele esperando a
VLC o al índice de la carpeta. Lo que no necesita wx vive en funciones puras
de arriba, con pruebas sin ventana.
"""

from __future__ import annotations

import wx

from ytchat.core import anuncio_ajuste, musica_decir
from ytchat.core import config as cfg
from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.music import anuncios, cruce
from ytchat.music.adaptador_vlc import AdaptadorVlc, MotorNoDisponible
from ytchat.music.coordinador import Coordinador
from ytchat.music.guardado_diferido import GuardadoDiferido
from ytchat.music.modelo import (
    AVANZO, FIN_LISTA, EstadoMusica, Resultado, SIN_TEMA)
from ytchat.music.normalizado import Normalizado
from ytchat.ui import atajos_globales
from ytchat.ui.accesibilidad import anunciar
from ytchat.ui.musica_cola import ColaMusica
from ytchat.ui.musica_enlaces import EnlacesMusica
from ytchat.ui.musica_indice import IndiceMusica, TEXTO_CARPETA_INEXISTENTE
from ytchat.ui.musica_listas_propias import ListasPropiasMusica
from ytchat.ui.musica_memoria import MemoriaMusica
from ytchat.ui.musica_sonoridad import SonoridadMusica
from ytchat.ui.musica_teclas import TeclasMusica
from ytchat.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)

PASO_VOLUMEN = 10
VOLUMEN_MIN = 0
VOLUMEN_MAX = 100
VOLUMEN_INICIAL = 50

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
    return bool(estado is not None and estado.actual is not None and not estado.terminado)


def _resultado_sin_tema() -> Resultado:
    return Resultado(False, SIN_TEMA, EstadoMusica(
        (), None, False, False, VOLUMEN_MAX, False))

class ControlMusica(ColaMusica, EnlacesMusica, IndiceMusica, SonoridadMusica,
                    ListasPropiasMusica, MemoriaMusica, TeclasMusica):
    """Acciones de música del menú y los atajos, con el motor en un hilo."""

    def __init__(self, frame):
        self._frame = frame
        self._config = frame._config
        self._adaptador = None
        self._coordinador = None
        self._preparando = False
        self._cerrado = False
        self._biblioteca = None
        # La ventana de música abierta, si hay.
        self._ventanas = {}
        self._retomo_intentado = False
        self._cache_etiquetas = None
        self._generacion_etiquetas = 0
        self._guardado_memoria = GuardadoDiferido(wx.CallLater)
        self._guardado_volumen = GuardadoDiferido(wx.CallLater)
        self._globales = atajos_globales.AtajosGlobales(frame, self.acciones_musica())
        self._globales_atajos = None
        if bool(self._config.get("musica_atajos_globales", False)):
            # Después de que la ventana exista: el registro es del sistema
            # y pide el bucle de eventos.
            try:
                wx.CallAfter(self._activar_globales_arranque)
            except Exception:
                logger.debug("No se pudieron activar los atajos globales")

    # ── Acciones del menú y los atajos ───────────────────────────────────────

    def reproducir_o_pausar(self) -> None:
        if self._coordinador is not None and toca_pausar(self._coordinador.estado()):
            self._ejecutar("pausa", self._coordinador.alternar_pausa)
            return
        if self._primera_vez():
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
            self._avisar(anuncios.Aviso(_(anuncios.TEXTO_SIN_TEMA)))
            return
        self._avisar(anuncios.aviso_que_suena(self._coordinador.estado(), True))

    # ── Biblioteca compartida y ventana ──────────────────────────────────────

    def estado(self):
        """El estado del coordinador, o None si el motor todavía no nació."""
        if self._coordinador is None:
            return None
        return self._coordinador.estado()

    def incluir_artista(self) -> bool:
        """Si se muestra el artista junto al título."""
        return self._incluir_artista()

    def texto_estado(self) -> str:
        """Qué suena, para el componente «Música que suena» de F2.

        Vacío sin motor, sin tema o con la lista terminada. Función pura
        envuelta: lo llama la GUI al armar el estado.
        """
        return anuncios.texto_estado_musica(self.estado(), True)

    def abrir_ventana(self) -> None:
        """Abre la ventana modal para elegir qué suena.

        Con una ventana de música abierta no abre otra: trae al frente la
        que ya está.
        """
        if self._traer_al_frente_si_hay():
            return
        from ytchat.ui import musica_ventana
        musica_ventana.abrir_ventana(self)

    def cola_actual(self):
        """Los temas que están en la cola, o vacío si el motor no nació."""
        if self._coordinador is None:
            return ()
        return self._coordinador.estado().cola

    def registrar_ventana(self, ventana) -> None:
        """La ventana de música quedó abierta: hay que refrescarle la cola."""
        self._ventanas["musica"] = ventana

    def olvidar_ventana(self) -> None:
        """La ventana de música se cerró."""
        self._ventanas.pop("musica", None)

    def _traer_al_frente_si_hay(self) -> bool:
        """Sube la ventana de música abierta, si la hay, y lo anuncia.

        Dice si ya había una abierta, para no crear otra encima. El foco
        vuelve a su primer control.
        """
        ventana = self._ventanas.get("musica")
        if ventana is None:
            return False
        try:
            ventana.Raise()
        except Exception:
            logger.debug("No se pudo traer al frente la ventana de música")
        try:
            ventana.enfocar_primer_control()
        except Exception:
            logger.debug("No se pudo enfocar el primer control de la ventana")
        self._avisar(anuncios.Aviso(_(anuncios.TEXTO_VENTANA_ABIERTA)))
        return True

    # ── Atajos dentro de la ventana modal ────────────────────────────────────

    def combos_atajo(self) -> dict:
        """(modificadores, tecla) → acción, para los atajos de música guardados.

        La ventana modal no recibe los atajos del menú: los traduce con
        `combo_wx` de `teclas_wx`, como la pantalla completa.
        """
        from ytchat.ui import teclas_wx
        atajos = cfg.parsear_atajos(self._config.get("atajos_raw", {}))
        combos = {}
        for accion in self.acciones_musica():
            atajo = atajos.get(accion)
            if atajo is None:
                continue
            combo = teclas_wx.combo_wx(atajo.texto)
            if combo is not None:
                combos[combo] = accion
        return combos

    def ejecutar_atajo(self, accion) -> None:
        """Corre la acción de música de un atajo, como si viniera del menú."""
        funcion = self.acciones_musica().get(accion)
        logger.debug("ATAJO origen=musica accion=%s%s", accion,
                     "" if funcion is not None else " desconocida=si")
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

        Volumen, salida (para el próximo tema), aleatorio y repetir. Los
        atajos globales no necesitan motor y van antes, así que valen aunque
        todavía no haya sonado nada. Nunca lanza: lo llama el frame al
        guardar Preferencias.
        """
        self._aplicar_globales_desde_preferencias()
        if self._coordinador is None:
            return
        try:
            self._reaplicar_volumen()
            self._aplicar_sonoridad()
            if self._adaptador is not None:
                self._adaptador.fijar_dispositivo(self._config.get("musica_salida") or None)
            aleatorio = bool(self._config.get("musica_aleatorio", False))
            self._coordinador.fijar_aleatorio(aleatorio)
            self._coordinador.fijar_repetir(cfg.normalizar_repetir(
                self._config.get("musica_repetir", "no")))
            item = getattr(self._frame, "mi_musica_aleatorio", None)
            if item is not None:
                item.Check(aleatorio)
        except Exception:
            logger.exception("No se pudieron aplicar las preferencias de música")

    # ── Atajos globales (valen en cualquier programa) ────────────────────────

    def _atajos_globales_textos(self) -> dict:
        """Los atajos efectivos de música, acción → texto guardado."""
        atajos = cfg.parsear_atajos(self._config.get("atajos_raw", {}))
        return {accion: atajos[accion].texto for accion in atajos_globales.ACCIONES
                if accion in atajos}

    def _activar_globales_arranque(self) -> None:
        """Activa los globales al arrancar: calla salvo que algo falle."""
        try:
            textos = self._atajos_globales_textos()
            fallidos = self._globales.activar(textos)
        except Exception:
            logger.exception("No se pudieron activar los atajos globales")
            return
        self._globales_atajos = textos
        if fallidos:
            self._avisar(anuncios.aviso_atajos_globales_fallo(fallidos))

    def _aplicar_globales_desde_preferencias(self) -> None:
        """Activa o desactiva los globales según la preferencia.

        Reactiva si cambiaron los atajos. Al activar desde Preferencias se
        anuncia (y el fallo, con error); al desactivar, también. Nunca lanza.
        """
        try:
            if bool(self._config.get("musica_atajos_globales", False)):
                textos = self._atajos_globales_textos()
                if self._globales.activos and textos == self._globales_atajos:
                    return
                fallidos = self._globales.activar(textos)
                self._globales_atajos = dict(textos)
                if fallidos:
                    self._avisar(anuncios.aviso_atajos_globales_fallo(fallidos))
                else:
                    self._avisar(anuncios.aviso_atajos_globales_activos())
            elif self._globales.activos:
                self._globales.desactivar()
                self._globales_atajos = None
                self._avisar(anuncios.aviso_atajos_globales_solo())
        except Exception:
            logger.exception("No se pudieron aplicar los atajos globales")

    def cerrar(self) -> None:
        """Cierra el motor si llegó a nacer y suelta los atajos. Nunca lanza."""
        self.parar_vigia()
        try:
            self._guardado_memoria.vaciar()
            self._guardado_volumen.vaciar()
        except Exception:
            logger.exception("No se pudo guardar lo pendiente de la música")
        try:
            self._globales.desactivar()
        except Exception:
            logger.debug("No se pudieron soltar los atajos globales")
        if self._adaptador is not None:
            try:
                self._adaptador.cerrar()
            except Exception:
                logger.exception("No se pudo cerrar el motor de música")

    # ── Motor: se prepara una sola vez, en un hilo ───────────────────────────

    def _asegurar_motor(self, continuar) -> None:
        if self._coordinador is not None:
            continuar()
            self._refrescar_ventana_abierta()
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
            adaptador = Normalizado(AdaptadorVlc(
                dispositivo=self._config.get("musica_salida") or None,
                volumen=self._volumen_config(), cruce_de=lambda: self._config.get("musica_cruce", cruce.CRUCE_FABRICA_S)),
                self._ganancia_de, volumen=self._volumen_config())
            adaptador.fijar_activo(bool(self._config.get("musica_normalizar", True)))
            coordinador = Coordinador(
                adaptador, al_cambiar=self._al_cambiar, volumen=self._volumen_config())
            adaptador.asignar_aviso(coordinador.tema_terminado, coordinador.cruzaria)
            coordinador.fijar_aleatorio(bool(self._config.get("musica_aleatorio", False)))
            coordinador.fijar_repetir(cfg.normalizar_repetir(
                self._config.get("musica_repetir", "no")))
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
        self._refrescar_ventana_abierta()

    def _motor_no_disponible(self) -> None:
        self._preparando = False
        self._avisar(anuncios.aviso_motor_no_disponible())

    # ── Avisos ───────────────────────────────────────────────────────────────

    def _al_cambiar(self, resultado) -> None:
        """Aviso automático del coordinador, que llega desde otro hilo."""
        wx.CallAfter(self._aviso_automatico, resultado)

    def _aviso_automatico(self, resultado) -> None:
        # Las dos preferencias se leen acá y no al preparar el motor: así un
        # cambio en Preferencias vale sin reiniciar.
        aviso = anuncios.aviso_automatico(
            resultado, bool(self._config.get("musica_sonido_tema", False)),
            self._config.get("musica_decir", "titulo"))
        self._avisar(aviso)
        if resultado.codigo in (AVANZO, FIN_LISTA):
            self._guardar_memoria()
        self._refrescar_ventana_abierta()

    def _refrescar_ventana_abierta(self) -> None:
        """Pone al día la cola de la ventana de música si está abierta."""
        ventana = self._ventanas.get("musica")
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
            self._refrescar_ventana_abierta()
            return
        operacion = getattr(self._coordinador, accion)
        self._ejecutar(accion, operacion)
        self._guardar_memoria()

    def _ejecutar(self, accion, operacion) -> None:
        resultado = operacion()
        self._avisar(anuncios.aviso_accion(accion, resultado, self._incluir_artista(),
                                           bool(self._config.get("musica_decir_pausa", True)),
                                           self._config.get("musica_decir", "titulo")))
        self._refrescar_ventana_abierta()

    def _cambiar_volumen(self, paso) -> None:
        actual = self._config.get("musica_volumen", VOLUMEN_INICIAL)
        nuevo = nuevo_volumen(actual, paso)
        self._config["musica_volumen"] = nuevo
        self._guardado_volumen.pedir(self._escribir_volumen)
        if self._coordinador is not None:
            self._coordinador.fijar_volumen(nuevo)
        self._sincronizar_silencio()
        texto = anuncio_ajuste.COMPARTIDO.frase(
            "volumen_musica", _(anuncios.TEXTO_VOLUMEN).format(valor=nuevo), str(nuevo))
        self._avisar(anuncios.Aviso(texto))

    def _escribir_volumen(self) -> None:
        self._guardar(
            "volumen", str(self._config.get("musica_volumen", VOLUMEN_INICIAL)))

    def _guardar(self, clave, valor) -> None:
        try:
            from ytchat.ui import gui as _gui
            _gui.guardar_opcion(_gui.RUTA_CONFIG, "musica", clave, valor)
        except Exception:
            logger.exception("No se pudo guardar la preferencia de música")

    def _carpeta(self) -> str:
        return (self._config.get("musica_carpeta") or "").strip()

    def _incluir_artista(self) -> bool:
        return musica_decir.incluye_artista(self._config.get("musica_decir", "titulo"))

    def _volumen_config(self) -> int:
        return nuevo_volumen(self._config.get("musica_volumen", VOLUMEN_INICIAL), 0)

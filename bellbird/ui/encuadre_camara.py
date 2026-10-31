"""El encuadre de la cámara en la ventana principal.

Ctrl+F3 anuncia cómo está el encuadre de la cámara de la escena al aire
de OBS. Ctrl+Mayús+F3 activa y desactiva los avisos automáticos, que
vigilan en un hilo propio y suenan solo cuando el rostro sale del
encuadre o vuelve. F2 puede decir la última frase con el componente
«Encuadre de cámara».
"""

from __future__ import annotations

import threading
import time
import weakref

import wx

from bellbird.camera import detector_rostros, encuadre
from bellbird.camera.detector_rostros import DetectorRostros
from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import obs_activacion, obs_camara, obs_cliente
from bellbird.obs.obs_camara import CamaraNoEncontrada
from bellbird.obs.obs_captura_ia import CapturaFallida
from bellbird.ui import guia_encuadre, ia_agregar_captura
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice.sound_player import reproducir


logger = diagnostico.obtener_logger(__name__)

# Traductores: aviso cuando el detector de rostros no está instalado.
TEXTO_SIN_DETECTOR = N_("El detector de rostros no está instalado.")
# Traductores: aviso al activar los avisos automáticos del encuadre.
TEXTO_AVISOS_ACTIVADOS = N_("Avisos de encuadre activados")
# Traductores: aviso al desactivar los avisos automáticos del encuadre.
TEXTO_AVISOS_DESACTIVADOS = N_("Avisos de encuadre desactivados")

# Cada cuánto mira la cámara, cuánto espera tras un fallo y cada cuánto
# vuelve a buscar la cámara.
INTERVALO_VUELTA = 0.5
ESPERA_TRAS_FALLO = 5.0
INTERVALO_REBUSCAR = 10.0

# Doble pulsación del atajo que inicia la guía de encuadre con pitidos.
VENTANA_DOBLE_PULSACION = 0.6


class _Terminar(Exception):
    """El marco murió: el hilo termina sin decir nada."""


class _Pausa(Exception):
    """Esta vuelta no dio cuadro: esperar y seguir en silencio."""


class _Encuadre:
    """El encuadre de la cámara de una ventana principal, con su vigilancia.

    Al marco solo lo usa como padre y para leer la configuración: nunca
    toca sus controles. La cámara se busca sola salvo que `camara_fuente`
    diga cuál.
    """

    def __init__(self, frame):
        try:
            self._marco = weakref.ref(frame)
        except TypeError:
            self._marco = lambda: frame
        self._en_curso = False
        self._hilo = None
        self._parada = None
        self._cliente = None
        self._detector = None
        self._camara = None
        self._ultima_busqueda = 0.0
        self._vigia = encuadre.VigiaEncuadre()
        self._contador = encuadre.ContadorCongelada()
        self._ultima_frase = ""
        self._candado = threading.Lock()
        self._guia = guia_encuadre.Guia()
        self._ultima_pulsacion = 0.0

    @property
    def _frame(self):
        try:
            marco = self._marco()
        except Exception as fallo:
            logger.warning("EncuadreCamara: sin marco: %s", fallo)
            return None
        if marco is None:
            return None
        try:
            borrandose = marco.IsBeingDeleted()
        except Exception:
            borrandose = False
        return None if borrandose else marco


_INSTANCIAS: dict = {}


def _instancia_para(frame):
    instancia = _INSTANCIAS.get(id(frame))
    if instancia is not None and instancia._frame is frame:
        return instancia
    instancia = _Encuadre(frame)
    _INSTANCIAS[id(frame)] = instancia
    return instancia


def _fuente(marco) -> str:
    try:
        return str(marco._config.get("camara_fuente", "") or "")
    except Exception:
        return ""


def _invertir(marco) -> bool:
    try:
        return bool(marco._config.get("camara_invertir", False))
    except Exception:
        return False


def anunciar_encuadre(frame) -> None:
    """Dice el encuadre actual; dos veces seguidas inicia la guía."""
    inst = _instancia_para(frame)
    ahora = time.monotonic()
    if inst._guia.en_marcha():
        inst._guia.detener(_(guia_encuadre.TEXTO_GUIA_DETENIDA))
        inst._ultima_pulsacion = 0.0
        return
    if ahora - inst._ultima_pulsacion < VENTANA_DOBLE_PULSACION:
        inst._ultima_pulsacion = 0.0
        marco = inst._frame
        inst._guia.iniciar(marco, _fuente(marco), _invertir(marco),
                           inst._vigia.reiniciar)
        return
    inst._ultima_pulsacion = ahora
    if inst._en_curso:
        return
    if not detector_rostros.disponible():
        anunciar(_(TEXTO_SIN_DETECTOR))
        return
    if not obs_activacion.obs_esta_en_ejecucion():
        anunciar(_(ia_agregar_captura.TEXTO_OBS_CERRADO))
        return
    inst._en_curso = True
    diagnostico.crear_hilo(
        lambda: _consultar_en_hilo(inst), "AnunciarEncuadre").start()


def _consultar_en_hilo(inst) -> None:
    marco = inst._frame
    if marco is None:
        inst._en_curso = False
        return
    cliente = None
    try:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        camara = obs_camara.buscar_camara(cliente, _fuente(marco))
        bmp = obs_camara.capturar_cuadro(cliente, camara)
        cuadro = DetectorRostros().analizar(bmp)
        estado = encuadre.analizar(
            cuadro.rostros, cuadro.ancho, cuadro.alto,
            espejo=(camara.espejo != _invertir(marco)),
            luz_rostro=cuadro.luz_rostro, luz_fondo=cuadro.luz_fondo)
        frase = encuadre.frase(estado)
    except (CamaraNoEncontrada, CapturaFallida) as fallo:
        wx.CallAfter(_vuelta_fallo, inst, str(fallo))
        return
    except Exception as fallo:
        wx.CallAfter(_vuelta_fallo, inst,
                     obs_cliente.mensaje_de_fallo_obs(fallo))
        return
    finally:
        if cliente is not None:
            try:
                cliente.cerrar()
            except Exception as fallo:
                logger.warning("EncuadreCamara: no se pudo cerrar OBS: %s",
                               fallo)
    wx.CallAfter(_vuelta_frase, inst, frase)


def _vuelta_frase(inst, frase) -> None:
    inst._en_curso = False
    if inst._frame is None:
        return
    anunciar(frase)


def _vuelta_fallo(inst, mensaje) -> None:
    inst._en_curso = False
    if inst._frame is None:
        return
    anunciar(mensaje)


def alternar_avisos(frame) -> None:
    """Invierte los avisos automáticos, los guarda y los pone en marcha."""
    nuevo = not bool(frame._config.get("avisar_encuadre", False))
    frame._config["avisar_encuadre"] = nuevo
    item = getattr(frame, "mi_avisos_encuadre", None)
    if item is not None:
        try:
            item.Check(nuevo)
        except Exception as fallo:
            logger.warning("EncuadreCamara: sin casilla: %s", fallo)
    from bellbird.ui import gui as _gui
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "avisar_encuadre",
                        "true" if nuevo else "false")
    anunciar(_(TEXTO_AVISOS_ACTIVADOS) if nuevo
            else _(TEXTO_AVISOS_DESACTIVADOS))
    sincronizar(frame)


def aplicar_preferencia(frame) -> None:
    """Marca la casilla de avisos y sincroniza la vigilancia.

    Nada sale de acá: cada paso atrapa y registra sus propios fallos.
    """
    try:
        frame.mi_avisos_encuadre.Check(
            bool(frame._config.get("avisar_encuadre", False)))
    except Exception as fallo:
        logger.warning("EncuadreCamara: sin casilla: %s", fallo)
    try:
        sincronizar(frame)
    except Exception as fallo:
        logger.warning("EncuadreCamara: sin vigilancia: %s", fallo)


def sincronizar(frame) -> None:
    """Pone en marcha o detiene la vigilancia según la preferencia."""
    inst = _instancia_para(frame)
    quiere = bool(frame._config.get("avisar_encuadre", False))
    with inst._candado:
        vivo = inst._hilo is not None and inst._hilo.is_alive()
        if quiere and not vivo:
            inst._parada = threading.Event()
            inst._hilo = diagnostico.crear_hilo(
                lambda: _bucle(inst), "VigilarEncuadre")
            inst._hilo.start()
        elif not quiere and vivo:
            inst._parada.set()
            inst._hilo = None


def texto_estado(frame) -> str:
    """La última frase de la vigilancia, o vacío si no vigila."""
    inst = _INSTANCIAS.get(id(frame))
    if inst is None or inst._frame is not frame:
        return ""
    with inst._candado:
        hilo = inst._hilo
    if hilo is None or not hilo.is_alive():
        return ""
    return inst._ultima_frase


def _bucle(inst) -> None:
    inst._vigia.reiniciar()
    inst._contador = encuadre.ContadorCongelada()
    inst._detector = DetectorRostros()
    inst._cliente = None
    inst._camara = None
    inst._ultima_busqueda = 0.0
    inst._ultima_frase = ""
    try:
        while not inst._parada.is_set():
            try:
                espera = _paso(inst, time.monotonic())
            except _Terminar:
                return
            inst._parada.wait(espera)
    finally:
        _soltar_cliente(inst)


def _paso(inst, ahora) -> float:
    """Una vuelta de vigilancia: segundos hasta la siguiente."""
    try:
        _vuelta(inst, ahora)
    except _Pausa:
        inst._vigia.reiniciar()
        inst._contador = encuadre.ContadorCongelada()
        inst._camara = None
        _soltar_cliente(inst)
        return ESPERA_TRAS_FALLO
    return INTERVALO_VUELTA


def _vuelta(inst, ahora) -> None:
    marco = inst._frame
    if marco is None:
        raise _Terminar()
    if not obs_activacion.obs_esta_en_ejecucion():
        inst._ultima_frase = _(ia_agregar_captura.TEXTO_OBS_CERRADO)
        raise _Pausa()
    try:
        cliente = _cliente(inst)
    except Exception as fallo:
        logger.warning("EncuadreCamara: sin cliente de OBS: %s", fallo)
        raise _Pausa()
    if inst._camara is None \
            or ahora - inst._ultima_busqueda >= INTERVALO_REBUSCAR:
        try:
            inst._camara = obs_camara.buscar_camara(cliente, _fuente(marco))
        except CamaraNoEncontrada as fallo:
            inst._ultima_frase = str(fallo)
            raise _Pausa()
        except Exception as fallo:
            logger.warning("EncuadreCamara: sin cámara: %s", fallo)
            raise _Pausa()
        inst._ultima_busqueda = ahora
    try:
        bmp = obs_camara.capturar_cuadro(cliente, inst._camara)
        cuadro = inst._detector.analizar(bmp)
    except Exception as fallo:
        logger.warning("EncuadreCamara: sin cuadro: %s", fallo)
        raise _Pausa()
    congelada = inst._contador.observar(cuadro.huella, ahora)
    estado = encuadre.analizar(
        cuadro.rostros, cuadro.ancho, cuadro.alto,
        espejo=(inst._camara.espejo != _invertir(marco)),
        luz_rostro=cuadro.luz_rostro, luz_fondo=cuadro.luz_fondo,
        congelada=congelada)
    frase = encuadre.frase(estado)
    inst._ultima_frase = frase
    aviso = inst._vigia.observar(estado, ahora)
    if aviso is not None and not inst._guia.en_marcha():
        wx.CallAfter(_avisar, aviso)


def _cliente(inst):
    """El cliente de OBS, reutilizado entre vueltas."""
    if inst._cliente is None:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        inst._cliente = cliente
    return inst._cliente


def _soltar_cliente(inst) -> None:
    """Cierra el cliente de OBS y lo suelta, para crear uno nuevo."""
    cliente, inst._cliente = inst._cliente, None
    if cliente is None:
        return
    try:
        cliente.cerrar()
    except Exception as fallo:
        logger.warning("EncuadreCamara: no se pudo cerrar OBS: %s",
                       fallo)


def _avisar(aviso) -> None:
    anunciar(aviso.frase)
    reproducir("encuadre_fuera" if aviso.tipo == "fuera"
               else "encuadre_dentro")

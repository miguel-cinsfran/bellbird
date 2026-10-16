"""Hilo TTS con Prism (SAPI 5 u OneCore) y sanitización de texto.

Prism unifica los motores de voz de Windows bajo una API. El motor se crea,
se usa y se cierra DENTRO del hilo: Prism no es seguro entre hilos. Hablar es
asíncrono y `hablando()` dice si el motor sigue sonando; eso permite
interrumpir un mensaje en curso (Alt+D) sin cortar el siguiente por error.

La subida y la bajada del estado no son simétricas: en SAPI `hablando()` tarda
entre 14 y 18 ms en pasar a True tras `hablar`, y en OneCore la pausa lo deja
en False mientras está en pausa. Por eso se espera la subida y la pausa se
mira antes que el estado.
"""

from __future__ import annotations

import queue
import re
import threading
import time

from ytchat.core import diagnostico
from ytchat.voice import escala_voz
from ytchat.voice import motores

logger = diagnostico.obtener_logger(__name__)

_STOP = object()

# Máximo de espera a que `hablando()` pase a True, y ritmo con que se lo mira.
_ESPERA_SUBIDA = 1.0
_PASO_SUBIDA = 0.005
# Ritmo con que se mira la bajada mientras el motor suena.
_PASO_ESPERA = 0.05


def _entero(valor, defecto: int) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def _volumen_inicial(valor) -> int:
    try:
        return max(0, min(100, int(float(valor) * 100)))
    except (TypeError, ValueError):
        return 100


# ── Sanitización de texto ────────────────────────────────────────────────────

_EMOJI = re.compile(
    "[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF"
    "\U00002702-\U000027B0\U0001F1E0-\U0001F1FF"
    "\u2600-\u2B55\u200d\ufe0f\u3030]+",
    flags=re.UNICODE,
)
_URL   = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", re.IGNORECASE)
_CTRL  = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_SPACE = re.compile(r"\s+")
# Emojis personalizados de YouTube que pytchat entrega como texto «:nombre:»
# (p. ej. :blue_heart:). Sin esto el TTS leería «dos puntos blue heart…».
_SHORTCODE = re.compile(r":[a-zA-Z0-9_+\-]{2,}:")


def quitar_emojis(texto: str) -> str:
    """Quita emojis Unicode y los shortcodes :nombre: de YouTube."""
    if not texto:
        return ""
    return _SHORTCODE.sub("", _EMOJI.sub("", texto))


def sanitizar(texto: str, emojis: bool, urls: bool, maxlen: int) -> str:
    if not texto:
        return ""
    if urls:   texto = _URL.sub("", texto)
    if emojis: texto = quitar_emojis(texto)
    texto = _CTRL.sub("", texto)
    texto = _SPACE.sub(" ", texto).strip()
    if maxlen > 0 and len(texto) > maxlen:
        t  = texto[:maxlen]
        sp = t.rfind(" ")
        texto = (t[:sp] if sp > maxlen // 2 else t) + "..."
    return texto


def construir_tts(autor: str, mensaje: str, config: dict) -> str:
    autor_limpio = sanitizar(autor, config["limpiar_emojis"], False, 50) or "Usuario"
    fmt = config.get("formato_prefijo", "nombre_mensaje")
    if fmt == "solo_mensaje": return mensaje
    if fmt == "solo_nombre":  return autor_limpio
    if fmt == "mensaje_nombre": return f"{mensaje}, de {autor_limpio}"
    return f"{autor_limpio}: {mensaje}"


# ── Hilo TTS ─────────────────────────────────────────────────────────────────

class TTSWorker(threading.Thread):

    def __init__(self, cola: queue.Queue, config: dict, fabrica_motor=None):
        super().__init__(daemon=True, name="TTSWorker")
        self.cola   = cola
        self.config = config
        # `None` usa el envoltorio real de Prism. Un doble permite probar el
        # worker sin abrir un motor de verdad.
        self._fabrica_motor = fabrica_motor or motores.MotorPrism
        self._ready  = threading.Event()
        self._error  = None
        self._active = threading.Event()
        self._active.set()
        self._paused = False
        self._cmds   = queue.Queue()
        # El contador de velocidad es el porcentaje propio (0..100, pasos de 5).
        self._rate   = escala_voz.ajustar_velocidad(
            _entero(config.get("velocidad_voz"), escala_voz.VELOCIDAD_NORMAL), 0)
        self._volume = _volumen_inicial(config.get("volumen", 1.0))
        self._tono   = max(0, min(100, _entero(config.get("tono"), 50)))
        self._purge_pending = threading.Event()
        # Autor del último mensaje que la voz empezó a leer, para anunciarlo
        # con F3 sin volver a la lista. Se registra en run() justo antes de
        # hablar; asignar una cadena es atómico en CPython y no lleva lock.
        self._ultimo_autor = ""
        # Motor, voces y voz activa. Todo se crea y se usa en el hilo del
        # worker; la interfaz lee `voces()` solo después de `esperar_inicio`.
        self._motor = None
        self._voces: list[str] = []
        self._voz_base = 0        # índice de la voz del menú/preferencias
        self._voz_actual = None   # índice de la voz activa, o None antes de abrir

    def run(self):
        try:
            self._abrir_motor()
        except Exception as exc:
            self._error = exc
            self._ready.set()
            logger.error("TTSWorker: %s", exc)
            self._cerrar_motor()
            return
        self._ready.set()
        logger.info("TTSWorker listo (motor %s).", self.motor_activo())
        _err = 0
        try:
            while True:
                self._active.wait()
                self._procesar_comandos()
                try:
                    item = self.cola.get(timeout=0.3)
                except queue.Empty:
                    continue
                if item is _STOP:
                    break
                texto = (item.get("texto_tts") or "").strip()
                if not texto:
                    continue
                self._active.wait()
                try:
                    # El autor viaja en el item y se guarda al empezar a leerlo,
                    # no al encolar: entre medias hay cola y descartes. Un item
                    # sin autor (avisos internos) no borra el anterior.
                    autor = item.get("autor") or ""
                    if autor:
                        self._ultimo_autor = autor
                    self._hablar(texto, item.get("voz")); _err = 0
                except Exception as exc:
                    _err += 1
                    if _err <= 5:
                        logger.warning("TTS error: %s", exc)
                    elif _err == 6:
                        logger.error("TTS: demasiados errores seguidos.")
        finally:
            self._cerrar_motor()
        logger.info("TTSWorker terminado.")

    # ── Arranque y cierre del motor ──────────────────────────────────────────

    def _abrir_motor(self) -> None:
        """Crea el motor pedido (con respaldo a SAPI), carga las voces y aplica
        velocidad, volumen y tono. Lanza si no hay ningún motor con voces."""
        pedido = self.config.get("motor") or "sapi"
        try:
            self._motor = self._fabrica_motor(pedido)
        except motores.MotorNoDisponible as exc:
            if pedido == "sapi":
                raise
            logger.warning("El motor de voz %r no está disponible (%s); "
                           "se usa Windows SAPI 5.", pedido, exc)
            self._motor = self._fabrica_motor("sapi")

        self._voces = list(self._motor.voces())
        if not self._voces:
            raise RuntimeError("El motor de voz no tiene voces instaladas.")

        guardada = self.config.get("voz")
        idx = escala_voz.resolver_voz(guardada, self._voces)
        if idx is None:
            if guardada:
                # Voz guardada que ya no está instalada: avisar con la lista
                # numerada. Vacío significa «la primera» y no es un problema.
                nombres = "\n".join(f"  [{i}] {n}" for i, n in enumerate(self._voces))
                logger.warning("Voz '%s' no encontrada; se usa la primera "
                               "disponible.\n%s", guardada, nombres)
            idx = 0
        self._voz_base = idx
        if self._motor.elegir_voz(idx):
            self._voz_actual = idx

        self._motor.fijar_velocidad(self._rate)
        self._motor.fijar_volumen(self._volume)
        self._motor.fijar_tono(self._tono)
        logger.info("Voz: %s | Velocidad: %d | Volumen: %d%% | Tono: %d",
                    self._voces[idx], self._rate, self._volume, self._tono)

    def _cerrar_motor(self) -> None:
        if self._motor is not None:
            self._motor.cerrar()

    # ── Voz y habla ──────────────────────────────────────────────────────────

    def _aplicar_voz(self, voz) -> None:
        """Cambia la voz activa si el mensaje pide otra (o vuelve a la base)."""
        if voz is None:
            idx = self._voz_base
        else:
            idx = escala_voz.resolver_voz(voz, self._voces)
            if idx is None:
                idx = self._voz_base
        if idx != self._voz_actual and self._motor.elegir_voz(idx):
            self._voz_actual = idx

    def _hablar(self, texto: str, voz=None) -> None:
        # Multi-voz: si el mensaje pide una voz concreta, se usa; si no, la base.
        self._aplicar_voz(voz)
        # Una purga pedida con la voz callada (p. ej. detener_actual() al
        # reconectar) quedaba armada y cortaba el SIGUIENTE mensaje: el primer
        # mensaje de cada reconexión se oía a medias. No había nada que cortar,
        # así que se descarta antes de hablar.
        self._purge_pending.clear()
        if not self._motor.hablar(texto):
            return
        # La subida del estado es asíncrona: hay que verla pasar a True o el
        # bucle de abajo daría el mensaje por terminado antes de que suene.
        limite = time.monotonic() + _ESPERA_SUBIDA
        while not self._motor.hablando() and time.monotonic() < limite:
            self._procesar_comandos()
            if self._purge_pending.is_set():
                self._purge_pending.clear()
                self._motor.parar()
                return
            time.sleep(_PASO_SUBIDA)
        # Bajada: mientras suene, se atienden comandos y purgas. La pausa se
        # mira ANTES que `hablando()`: en OneCore la pausa deja el estado en
        # False y mirarlo primero arrancaría el mensaje siguiente en pausa.
        while True:
            self._procesar_comandos()
            if not self._active.is_set():
                self._esperar_pausa()
            if self._purge_pending.is_set():
                self._purge_pending.clear()
                self._motor.parar()
                return
            if not self._motor.hablando():
                return
            time.sleep(_PASO_ESPERA)

    def _esperar_pausa(self) -> None:
        """Pausa a mitad de frase sin dejar de atender comandos ni purgas.

        Antes el hilo quedaba en wait() pero la voz seguía sonando hasta acabar
        la frase; ahora se pausa el motor de verdad y los comandos (voz,
        velocidad, volumen, purga) se siguen atendiendo."""
        self._motor.pausar()
        try:
            while not self._active.wait(0.1):
                self._procesar_comandos()
                if self._purge_pending.is_set():
                    break   # Alt+D en pausa: se reanuda para poder purgar
        finally:
            self._motor.reanudar()

    def _cambiar_voz_base(self, val) -> None:
        idx = escala_voz.resolver_voz(val, self._voces)
        if idx is None:
            logger.debug("Voz base %r no resuelta.", val)
            return
        self._voz_base = idx
        if idx != self._voz_actual and self._motor.elegir_voz(idx):
            self._voz_actual = idx
        logger.info("Voz base: %s", self._voces[idx])

    def _cambiar_motor(self, motor, voz) -> None:
        """Reemplaza el motor activo dentro del hilo del worker.

        Prism exige un motor por hilo: el nuevo se crea aquí, se para y se
        cierra el anterior solo si el nuevo se pudo crear y tiene voces. Si la
        fábrica falla se conserva el motor viejo sin tocarlo, para no dejar al
        worker mudo."""
        try:
            nuevo = self._fabrica_motor(motor)
        except motores.MotorNoDisponible as exc:
            logger.warning("El motor de voz %r no está disponible (%s); "
                           "se conserva %s.", motor, exc, self.motor_activo())
            return
        voces = list(nuevo.voces())
        if not voces:
            logger.warning("El motor de voz %r no tiene voces; se conserva %s.",
                           motor, self.motor_activo())
            nuevo.cerrar()
            return
        if self._motor is not None:
            self._motor.parar()
            self._motor.cerrar()
        self._motor = nuevo
        self._voces = voces
        idx = escala_voz.resolver_voz(voz, voces)
        if idx is None:
            idx = 0
        self._voz_base = idx
        self._voz_actual = None
        if self._motor.elegir_voz(idx):
            self._voz_actual = idx
        self._motor.fijar_velocidad(self._rate)
        self._motor.fijar_volumen(self._volume)
        self._motor.fijar_tono(self._tono)
        logger.info("Motor de voz: %s | Voz: %s", motor, self._voces[idx])

    def _procesar_comandos(self):
        while not self._cmds.empty():
            try:    cmd, val = self._cmds.get_nowait()
            except queue.Empty: break
            try:
                if cmd == "voice":
                    self._cambiar_voz_base(val)
                elif cmd == "motor":
                    self._cambiar_motor(*val)
                elif cmd == "rate":
                    self._motor.fijar_velocidad(val)
                elif cmd == "volume":
                    self._motor.fijar_volumen(val)
                elif cmd == "tono":
                    self._motor.fijar_tono(val)
                elif cmd == "purge":
                    self._purge_pending.set()
            except Exception as exc:
                logger.warning("Comando %s: %s", cmd, exc)

    # ── API pública ──────────────────────────────────────────────────────────

    def esperar_inicio(self, timeout=10.0):
        if not self._ready.wait(timeout=timeout): return False
        if self._error:
            logger.error(str(self._error)); return False
        return True

    def voces(self) -> list[str]:
        """Nombres de voz del motor activo. Válida tras `esperar_inicio`."""
        return list(self._voces)

    def motor_activo(self) -> str:
        """Motor que quedó activo de verdad: 'sapi' u 'onecore'."""
        return self._motor.motor if self._motor is not None else ""

    def pausar(self):
        if not self._paused:
            self._paused = True; self._active.clear()

    def reanudar(self):
        if self._paused:
            self._paused = False; self._active.set()

    def toggle_pausa(self):
        self.reanudar() if self._paused else self.pausar()

    def esta_pausado(self):
        return self._paused

    def vaciar_cola(self):
        n = 0
        while not self.cola.empty():
            try:    self.cola.get_nowait(); n += 1
            except queue.Empty: break
        if n: logger.info("Cola vaciada: %d mensaje(s).", n)

    def detener(self):
        if self._paused: self._active.set()
        try:    self.cola.put(_STOP)
        except Exception: pass
        self.join(timeout=5.0)

    def detener_actual(self):
        """Interrumpe el mensaje en curso y vacía la cola (Alt+D)."""
        self.vaciar_cola()
        self._cmds.put(("purge", None))

    def cambiar_voz(self, idx: int):
        self._cmds.put(("voice", idx))

    def cambiar_motor(self, motor: str, voz) -> None:
        """Pide cambiar de motor en caliente (SAPI u OneCore).

        El trabajo real ocurre en el hilo del worker: Prism no admite que un
        motor se cree en un hilo y se use en otro."""
        self._cmds.put(("motor", (motor, voz)))

    def cambiar_rate(self, pasos: int) -> None:
        # El contador se actualiza AQUÍ (en el hilo del llamador) y al hilo TTS
        # va el valor absoluto: así get_rate() devuelve el valor nuevo al
        # instante y pulsar rápido no desfasa lo anunciado/persistido.
        self._rate = escala_voz.ajustar_velocidad(self._rate, pasos)
        self._cmds.put(("rate", self._rate))

    def cambiar_volumen(self, delta: int) -> None:
        self._volume = max(0, min(100, self._volume + int(delta)))
        self._cmds.put(("volume", self._volume))

    def cambiar_tono(self, pct: int) -> None:
        self._tono = max(0, min(100, _entero(pct, self._tono)))
        self._cmds.put(("tono", self._tono))

    def fijar_rate(self, pct: int) -> None:
        """Fija la velocidad en un valor absoluto (0..100, múltiplo de 5)."""
        self._rate = escala_voz.ajustar_velocidad(_entero(pct, self._rate), 0)
        self._cmds.put(("rate", self._rate))

    def fijar_volumen_pct(self, pct: int) -> None:
        """Fija el volumen en un porcentaje absoluto (0..100)."""
        self._volume = max(0, min(100, _entero(pct, self._volume)))
        self._cmds.put(("volume", self._volume))

    def get_rate(self) -> int:
        return self._rate

    def get_volume(self) -> int:
        return self._volume

    def get_tono(self) -> int:
        return self._tono

    def ultimo_autor(self) -> str:
        """Autor del último mensaje que la voz empezó a leer.

        Cadena vacía si todavía no se leyó nada."""
        return self._ultimo_autor

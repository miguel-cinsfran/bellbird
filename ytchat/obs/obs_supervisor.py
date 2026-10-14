"""Supervisor de la transmisión sin interfaz.

Vive aparte de la ventana Transmisión: si la persona cierra esa ventana para
leer el chat, el supervisor sigue. Al iniciar arranca OBS, confirma que la
señal sale, espera a que TikTok muestre el directo, pide conectar el chat, y
después vigila el directo hablando solo ante problemas. Nadie lo llama
todavía: lo usará la ventana en el encargo siguiente.
"""

from __future__ import annotations

import threading
import time

from ytchat.capture import tiktok_vivo
from ytchat.core import diagnostico
from ytchat.obs import obs_cliente
from ytchat.obs import obs_estado
from ytchat.obs import obs_lanzador
from ytchat.obs import obs_salida
from ytchat.obs.obs_panel import GestorPanelObs

# La misma frase no se repite antes de este plazo durante la vigilancia.
PLAZO_REPETICION = 60.0


def duracion_legible(segundos) -> str:
    """Duración en horas, minutos y segundos para leer en voz alta."""
    try:
        total = int(segundos)
    except (TypeError, ValueError):
        total = 0
    if total < 0:
        total = 0
    horas, resto = divmod(total, 3600)
    minutos, resto = divmod(resto, 60)
    partes = []
    if horas:
        partes.append(f"{horas} hora" if horas == 1 else f"{horas} horas")
    if minutos:
        partes.append(f"{minutos} minuto" if minutos == 1 else f"{minutos} minutos")
    if resto or not partes:
        partes.append(f"{resto} segundo" if resto == 1 else f"{resto} segundos")
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " y " + partes[-1]


class SupervisorTransmision:
    """Arranca OBS y vigila el directo desde un hilo propio."""

    def __init__(self, destino, usuario_tiktok="",
                 al_anunciar=None, al_conectar_chat=None,
                 crear_gestor=GestorPanelObs,
                 esperar_salida=obs_salida.esperar_salida,
                 esperar_en_vivo=tiktok_vivo.esperar_en_vivo,
                 dormir=time.sleep, reloj=time.monotonic,
                 intervalo_salud=5.0, limite_tiktok=120.0,
                 asegurar=None, al_terminar=None):
        self._destino = destino
        self._usuario = usuario_tiktok or ""
        self._al_anunciar = al_anunciar or (lambda frase, sonido: None)
        self._al_conectar_chat = al_conectar_chat or (lambda url: None)
        self._crear_gestor = crear_gestor
        self._esperar_salida = esperar_salida
        self._esperar_en_vivo = esperar_en_vivo
        self._dormir = dormir
        self._reloj = reloj
        self._intervalo_salud = intervalo_salud
        self._limite_tiktok = limite_tiktok
        self._asegurar = (asegurar if asegurar is not None
                          else obs_lanzador.asegurar_obs)
        self._al_terminar = al_terminar
        self._parada = threading.Event()
        self._corte = threading.Event()
        self._hilo = None
        self._ultimo_estado = None
        self._ultima_frase = ""
        self._tiktok_confirmado = None

    @property
    def activo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def frase_estado(self) -> str:
        """Fase actual para F2, sin repetir lo ya anunciado.

        Si ya se leyó un estado con transmisión activa, nombra el
        destino con la duración del último estado; si no, repite la
        última frase anunciada sin el punto final."""
        ultimo = self._ultimo_estado
        if ultimo is not None and bool(ultimo.get("outputActive")):
            try:
                frase = obs_estado.frase_transmision(
                    ultimo.get("outputActive"),
                    ultimo.get("outputDuration", 0),
                    ultimo.get("outputSkippedFrames", 0),
                    ultimo.get("outputTotalFrames", 0))
            except Exception:
                frase = ""
            if frase:
                if self._tiktok_confirmado is True:
                    frase += ", ya se ve en TikTok"
                elif self._tiktok_confirmado is False:
                    frase += ", sin confirmar en TikTok"
                return f"Directo a {self._destino}: {frase}"
        texto = (self._ultima_frase or "").strip()
        if texto.endswith("."):
            texto = texto[:-1].rstrip()
        return texto

    def iniciar(self) -> None:
        if self.activo:
            return
        self._parada.clear()
        self._corte.clear()
        self._hilo = diagnostico.crear_hilo(
            self._supervisar, "SupervisorTransmision")
        self._hilo.start()

    def detener(self) -> None:
        estaba_activo = self.activo
        self._parada.set()
        self._corte.set()
        if estaba_activo:
            try:
                gestor = self._crear_gestor()
                try:
                    gestor.conectar()
                    try:
                        activa = bool(gestor.estado_transmision().get(
                            "outputActive"))
                    except Exception:
                        activa = True
                    if activa:
                        try:
                            gestor.detener_transmision()
                        except Exception:
                            pass
                finally:
                    try:
                        gestor.cerrar()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                self._al_anunciar("Transmisión detenida.", None)
            except Exception:
                pass
        hilo = self._hilo
        if hilo is not None:
            hilo.join(2.0)

    def abandonar(self) -> None:
        # Deja de vigilar sin detener OBS y sin anunciar: cerrar YTChat no
        # corta el directo.
        self._parada.set()
        self._corte.set()
        hilo = self._hilo
        if hilo is not None:
            hilo.join(2.0)

    def _esperar(self, segundos) -> None:
        # La vigilancia duerme con la parada para que detener() despierte
        # enseguida; los dobles de las pruebas inyectan otro dormir y se
        # respeta para no romper su reloj falso.
        if self._dormir is time.sleep:
            self._parada.wait(segundos)
        else:
            self._dormir(segundos)

    def _anunciar(self, frase, sonido) -> None:
        self._ultima_frase = frase if isinstance(frase, str) else ""
        self._al_anunciar(frase, sonido)

    def _probar_obs(self) -> None:
        gestor = self._crear_gestor()
        try:
            gestor.conectar(self._parada)
        finally:
            try:
                gestor.cerrar()
            except Exception:
                pass

    def _supervisar(self) -> None:
        gestor = None
        try:
            self._anunciar("Comenzando la transmisión.", "conectando")
            if self._parada.is_set():
                return
            self._asegurar(self._probar_obs,
                           al_anunciar=lambda frase: self._anunciar(
                               frase, None),
                           parada=self._parada)
            if self._parada.is_set():
                return
            gestor = self._crear_gestor()
            gestor.conectar(self._parada)
            if self._parada.is_set():
                return
            gestor.iniciar_transmision(self._parada)
            if self._parada.is_set():
                return
            cliente = getattr(gestor, "_cliente", gestor)
            veredicto = self._esperar_salida(cliente, self._parada)
            if self._parada.is_set():
                return
            frase = obs_salida.frase_salida(veredicto, self._destino)
            if veredicto != "enviando":
                self._anunciar(frase, "error")
                return
            self._anunciar(frase, "conectado")
            if self._destino == "TikTok" and self._usuario:
                self._anunciar(
                    "Esperando a que TikTok muestre el directo.", None)
                resultado = self._esperar_en_vivo(
                    self._usuario, self._parada,
                    limite=self._limite_tiktok)
                if self._parada.is_set():
                    return
                if resultado.en_vivo:
                    self._tiktok_confirmado = True
                    self._anunciar(
                        "Tu directo de TikTok ya está al aire.", "conectado")
                    self._al_conectar_chat(
                        tiktok_vivo.url_directo(self._usuario))
                elif getattr(resultado, "cuenta_sin_directos", False):
                    self._tiktok_confirmado = False
                    self._anunciar(
                        f"OBS está transmitiendo, pero TikTok todavía no "
                        f"muestra ningún directo de {self._usuario}. "
                        "Revisa que en Restream esté activado TikTok.",
                        "error")
                else:
                    self._tiktok_confirmado = False
                    self._anunciar(
                        "OBS está transmitiendo, pero TikTok todavía no "
                        "muestra el directo.", "error")
            elif self._destino == "TikTok":
                self._anunciar(
                    "No hay usuario de TikTok guardado: "
                    "conecta el chat a mano.", None)
            self._vigilar(gestor)
        except Exception as error:
            if self._parada.is_set():
                return
            try:
                self._anunciar(
                    obs_cliente.mensaje_de_fallo_obs(error), "error")
            except Exception:
                pass
        finally:
            if gestor is not None:
                try:
                    gestor.cerrar()
                except Exception:
                    pass
            if self._al_terminar is not None:
                try:
                    self._al_terminar()
                except Exception:
                    pass

    def _vigilar(self, gestor) -> None:
        anterior = gestor.estado_transmision(self._parada)
        try:
            self._ultimo_estado = dict(anterior)
        except Exception:
            self._ultimo_estado = anterior
        if self._parada.is_set() or self._corte.is_set():
            return
        if not anterior.get("outputActive"):
            return
        ultimos_avisos = {}
        while not self._parada.is_set():
            self._esperar(self._intervalo_salud)
            if self._parada.is_set() or self._corte.is_set():
                return
            actual = gestor.estado_transmision(self._parada)
            try:
                self._ultimo_estado = dict(actual)
            except Exception:
                self._ultimo_estado = actual
            if not actual.get("outputActive"):
                if self._corte.is_set() or self._parada.is_set():
                    return
                try:
                    segundos = int(float(actual.get("outputDuration", 0)))
                except (TypeError, ValueError):
                    segundos = 0
                self._anunciar(
                    "La transmisión terminó. "
                    f"Duró {duracion_legible(segundos)}.", None)
                return
            frase = obs_salida.problema_en_directo(anterior, actual)
            if frase:
                ahora = self._reloj()
                ultimo = ultimos_avisos.get(frase)
                if ultimo is None or ahora - ultimo >= PLAZO_REPETICION:
                    self._anunciar(frase, "error")
                    ultimos_avisos[frase] = ahora
            anterior = actual

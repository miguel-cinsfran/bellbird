"""Supervisor de la transmisión sin interfaz.

Vive aparte de la ventana Transmisión: si la persona cierra esa ventana para
leer el chat, el supervisor sigue. Al iniciar arranca OBS, confirma que la
señal sale, espera a que TikTok muestre el directo, pide conectar el chat, y
después vigila el directo hablando solo ante problemas. Lo crea
`ytchat/ui/gui_transmitir.py`.
"""

from __future__ import annotations

import threading
import time

from ytchat.capture import tiktok_vivo
from ytchat.core import diagnostico
from ytchat.obs import obs_activacion
from ytchat.obs import obs_cliente
from ytchat.obs import obs_estado
from ytchat.obs import obs_lanzador
from ytchat.obs import obs_salida
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.youtube import emision
from ytchat.youtube import fin_pendiente

logger = diagnostico.obtener_logger(__name__)

# La misma frase no se repite antes de este plazo durante la vigilancia.
PLAZO_REPETICION = 60.0

# El aviso de sobrecarga es más molesto y no aporta nada repetirlo seguido:
# no se repite antes de este plazo, y solo si el usuario lo tiene activado.
PLAZO_SOBRECARGA = 300.0

# Sonido por tipo de aviso de la vigilancia. Los problemas de red y de
# sobrecarga comparten el de transmisión con problema; la vuelta de la conexión
# tiene el suyo, distinto, para no sonar a alarma cuando ya se resolvió.
SONIDOS_AVISO = {
    "reconexion": "transmision_problema",
    "red": "transmision_problema",
    "sobrecarga": "transmision_problema",
    "vuelta": "transmision_recuperada",
}

# Al detener: cuánto se espera a que OBS apague la salida, cada cuánto se
# consulta, y desde cuándo se avisa de que la espera sigue.
LIMITE_ESPERA_OBS = 90.0
INTERVALO_ESPERA_OBS = 1.0
AVISO_ESPERA_OBS = 3.0


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
                 asegurar=None, al_terminar=None,
                 preparar_emision=None, esperar_emision=None,
                 finalizar_emision=None, ruta_fin_pendiente=None,
                 avisar_sobrecarga=None):
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
        self._preparar_emision = preparar_emision
        self._esperar_emision = esperar_emision
        self._finalizar_emision = finalizar_emision
        self._ruta_fin_pendiente = ruta_fin_pendiente
        # Invocable sin argumentos que decide, en cada vuelta, si el aviso de
        # sobrecarga se anuncia. El supervisor no lee la configuración solo:
        # quien lo crea se la pasa.
        self._avisar_sobrecarga = avisar_sobrecarga or (lambda: True)
        self._id_video = None
        self._cerrojo_fin = threading.Lock()
        self._fin_youtube = False
        self._parada = threading.Event()
        self._corte = threading.Event()
        self._hilo = None
        self._deteniendo = False
        self._ultimo_estado = None
        self._ultima_frase = ""
        self._destino_confirmado = None

    @property
    def activo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    @property
    def deteniendo(self) -> bool:
        # Verdadero desde que detener() empieza con la transmisión activa
        # hasta que _detener_obs deja de esperar a OBS. El fin en YouTube no
        # la mantiene: la salida de OBS ya no emite.
        return self._deteniendo

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
                if self._destino_confirmado is True:
                    frase += f", ya se ve en {self._destino}"
                elif self._destino_confirmado is False:
                    frase += f", sin confirmar en {self._destino}"
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
        self._id_video = None
        with self._cerrojo_fin:
            self._fin_youtube = False
        self._hilo = diagnostico.crear_hilo(
            self._supervisar, "SupervisorTransmision")
        self._hilo.start()

    def detener(self) -> None:
        estaba_activo = self.activo
        if estaba_activo:
            # Antes de la parada: la vigilancia sale enseguida y `activo`
            # pasa a False, pero OBS todavía emite hasta `_detener_obs`.
            self._deteniendo = True
        self._parada.set()
        self._corte.set()
        if estaba_activo:
            try:
                self._detener_obs()
            finally:
                self._deteniendo = False
            self._finalizar_youtube_si_toca()
        hilo = self._hilo
        if hilo is not None:
            hilo.join(2.0)
        # Repite el aviso que ya dio la vigilancia al salir: ahora sí se
        # puede refrescar el botón con la parada confirmada.
        if self._al_terminar is not None:
            try:
                self._al_terminar()
            except Exception:
                pass

    def _detener_obs(self) -> None:
        """Pide parar a OBS y espera a que confirme, sin congelar la ventana.

        Corre en el hilo DetenerSupervisor, así que puede dormir con
        `self._dormir` directamente: `self._esperar` volvería enseguida
        porque la parada ya está puesta.
        """
        gestor = None
        try:
            gestor = self._crear_gestor()
            gestor.conectar()
        except Exception as error:
            self._cerrar_gestor(gestor)
            self._anunciar_obs_sin_respuesta(error)
            return
        try:
            try:
                activa = bool(
                    gestor.estado_transmision().get("outputActive"))
            except Exception:
                # Sin respuesta al preguntar el estado, se asume activa:
                # mejor mandar StopStream de más que dejar la salida
                # corriendo. `_esperar_a_obs` dirá lo que toque si OBS
                # sigue sin responder.
                activa = True
            if not activa:
                self._anunciar("Transmisión detenida.",
                               "transmision_detenida")
                return
            try:
                gestor.detener_transmision()
            except Exception:
                pass
            self._esperar_a_obs(gestor)
        finally:
            self._cerrar_gestor(gestor)

    def _esperar_a_obs(self, gestor) -> None:
        """Consulta a OBS hasta que la salida se apague, con un límite."""
        inicio = self._reloj()
        avisado = False
        while True:
            try:
                activa = bool(
                    gestor.estado_transmision().get("outputActive"))
            except Exception as error:
                self._anunciar_obs_sin_respuesta(error)
                return
            if not activa:
                self._anunciar("Transmisión detenida.",
                               "transmision_detenida")
                return
            transcurrido = self._reloj() - inicio
            if not avisado and transcurrido >= AVISO_ESPERA_OBS:
                self._anunciar(
                    "Deteniendo la transmisión. "
                    "Esperando a que OBS confirme.", None)
                avisado = True
            if transcurrido >= LIMITE_ESPERA_OBS:
                self._anunciar(
                    "OBS sigue transmitiendo. "
                    "Detén la transmisión en OBS.", "transmision_problema")
                return
            self._dormir(INTERVALO_ESPERA_OBS)

    def _anunciar_obs_sin_respuesta(self, error=None) -> None:
        # Sin poder hablar con OBS, la señal depende de si OBS sigue abierto:
        # si no corre, la transmisión ya no sale y está detenida.
        try:
            corre = obs_activacion.obs_esta_en_ejecucion()
        except Exception:
            corre = False
        if corre:
            self._anunciar(
                "No se pudo conectar con OBS para detener la transmisión.",
                "transmision_problema")
        else:
            self._anunciar("Transmisión detenida.", "transmision_detenida")

    def _cerrar_gestor(self, gestor) -> None:
        if gestor is None:
            return
        try:
            gestor.cerrar()
        except Exception:
            pass

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

    def _panel_tapado(self, gestor):
        # Los dobles viejos de las pruebas no tienen el método y se salta.
        traer = getattr(gestor, "traer_panel_adelante", None)
        if traer is None:
            return None
        try:
            return traer(self._parada)
        except Exception as error:
            try:
                logger.debug("no se pudo poner el panel delante: %s", error)
            except Exception:
                pass
            return None

    def _anunciar_panel_tapado(self, nombre) -> None:
        self._anunciar(
            f"El panel de chat estaba detrás de «{nombre}». "
            "Lo puse adelante.", "aviso")

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
            cliente = getattr(gestor, "_cliente", gestor)
            if self._preparar_emision is not None:
                self._anunciar("Creando el directo en YouTube.", None)
                try:
                    self._id_video = self._preparar_emision(
                        cliente, self._parada)
                except emision.EmisionError as error:
                    self._anunciar(str(error), "transmision_problema")
                    return
            nombre = self._panel_tapado(gestor)
            if nombre:
                self._anunciar_panel_tapado(nombre)
            gestor.iniciar_transmision(self._parada)
            if self._parada.is_set():
                return
            veredicto = self._esperar_salida(cliente, self._parada)
            if self._parada.is_set():
                return
            frase = obs_salida.frase_salida(veredicto, self._destino)
            if veredicto != "enviando":
                self._anunciar(frase, "transmision_problema")
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
                    self._destino_confirmado = True
                    self._anunciar(
                        "Tu directo de TikTok ya está al aire.", "al_aire")
                    self._al_conectar_chat(
                        tiktok_vivo.url_directo(self._usuario))
                elif getattr(resultado, "cuenta_sin_directos", False):
                    self._destino_confirmado = False
                    self._anunciar(
                        f"OBS está transmitiendo, pero TikTok todavía no "
                        f"muestra ningún directo de {self._usuario}. "
                        "Revisa que en Restream esté activado TikTok.",
                        "transmision_problema")
                else:
                    self._destino_confirmado = False
                    self._anunciar(
                        "OBS está transmitiendo, pero TikTok todavía no "
                        "muestra el directo.", "transmision_problema")
            elif self._destino == "YouTube" and self._id_video \
                    and self._esperar_emision is not None:
                self._anunciar(
                    "Esperando a que YouTube muestre el directo.", None)
                ok = self._esperar_emision(
                    self._id_video, self._parada, self._limite_tiktok)
                if self._parada.is_set():
                    return
                if ok:
                    self._destino_confirmado = True
                    self._anunciar(
                        "Tu directo de YouTube ya está al aire.",
                        "al_aire")
                    self._al_conectar_chat(
                        emision.url_video(self._id_video))
                else:
                    self._destino_confirmado = False
                    self._anunciar(
                        "OBS está transmitiendo, pero YouTube todavía no "
                        "muestra el directo.", "transmision_problema")
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
                    obs_cliente.mensaje_de_fallo_obs(error), "transmision_problema")
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

    def _finalizar_youtube_si_toca(self) -> None:
        # Cierra el directo en YouTube una sola vez por emisión, solo con
        # id de vídeo (los directos de TikTok no tienen). El id se anota
        # antes de pedirlo: si la red falla, el pedido sobrevive al cierre
        # en el archivo de fines pendientes. Con la ruta en None no se toca
        # el disco y no se lanza reintento.
        gancho = self._finalizar_emision
        id_video = self._id_video
        if gancho is None or not id_video:
            return
        with self._cerrojo_fin:
            if self._fin_youtube:
                return
            self._fin_youtube = True
        self._anotar_fin_pendiente(id_video)
        try:
            gancho(id_video)
        except Exception as error:
            try:
                self._anunciar(
                    "YouTube no confirmó el fin del directo. "
                    "Se reintentará durante 10 minutos.",
                    "transmision_problema")
            except Exception:
                pass
            try:
                logger.warning("no se pudo finalizar la emisión %s: %s",
                               id_video, error)
            except Exception:
                pass
            self._lanzar_reintento_fin(id_video)
        else:
            self._quitar_fin_pendiente(id_video)

    def _anotar_fin_pendiente(self, id_video) -> None:
        if self._ruta_fin_pendiente is None:
            return
        try:
            fin_pendiente.anotar(self._ruta_fin_pendiente, id_video)
        except Exception as error:
            logger.debug("no se pudo anotar el fin pendiente: %s", error)

    def _quitar_fin_pendiente(self, id_video) -> None:
        if self._ruta_fin_pendiente is None:
            return
        try:
            fin_pendiente.quitar(self._ruta_fin_pendiente, id_video)
        except Exception as error:
            logger.debug("no se pudo quitar el fin pendiente: %s", error)

    def _lanzar_reintento_fin(self, id_video) -> None:
        # Sin archivo no hay nada que sobreviva a un cierre de la app, así
        # que no se abre un reintento a ciegas: la ruta la pone quien usa
        # el supervisor en producción.
        if self._ruta_fin_pendiente is None:
            return
        try:
            diagnostico.crear_hilo(
                lambda: self._reintentar_fin(id_video),
                "ReintentarFinDirecto").start()
        except Exception as error:
            logger.warning("no se pudo lanzar el reintento del fin: %s", error)

    def _reintentar_fin(self, id_video) -> None:
        def intento():
            self._finalizar_emision(id_video)

        if fin_pendiente.reintentar(intento, self._dormir, self._reloj):
            self._quitar_fin_pendiente(id_video)
            try:
                self._anunciar("Directo finalizado en YouTube.",
                               "directo_finalizado")
            except Exception:
                pass
        else:
            try:
                self._anunciar(
                    "YouTube sigue sin confirmar el fin del directo. "
                    "Se intentará de nuevo al abrir YTChat.",
                    "transmision_problema")
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
        estadisticas_anterior = self._estadisticas(gestor)
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
                    f"Duró {duracion_legible(segundos)}.", "transmision_detenida")
                self._finalizar_youtube_si_toca()
                return
            estadisticas = self._estadisticas(gestor)
            for tipo, frase in obs_salida.problemas_en_directo(
                    anterior, actual, estadisticas_anterior, estadisticas):
                if tipo == "sobrecarga" and not self._avisar_sobrecarga():
                    continue
                if tipo != "vuelta":
                    ahora = self._reloj()
                    ultimo = ultimos_avisos.get(tipo)
                    plazo = (PLAZO_SOBRECARGA if tipo == "sobrecarga"
                             else PLAZO_REPETICION)
                    if ultimo is not None and ahora - ultimo < plazo:
                        continue
                    ultimos_avisos[tipo] = ahora
                self._anunciar(frase, SONIDOS_AVISO[tipo])
            nombre = self._panel_tapado(gestor)
            if nombre:
                frase_panel = (
                    f"El panel de chat estaba detrás de «{nombre}». "
                    "Lo puse adelante.")
                ahora = self._reloj()
                ultimo = ultimos_avisos.get(frase_panel)
                if ultimo is None or ahora - ultimo >= PLAZO_REPETICION:
                    self._anunciar(frase_panel, "aviso")
                    ultimos_avisos[frase_panel] = ahora
            anterior = actual
            if estadisticas is not None:
                estadisticas_anterior = estadisticas

    def _estadisticas(self, gestor):
        # Los dobles que no traen estadísticas quedan sin avisos de equipo en
        # esa vuelta; un fallo real de OBS tampoco corta la vigilancia.
        try:
            return gestor.estadisticas(self._parada)
        except Exception as error:
            try:
                logger.debug("no se pudieron leer las estadísticas de OBS: %s",
                             error)
            except Exception:
                pass
            return None

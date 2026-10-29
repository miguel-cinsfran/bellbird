"""Interfaz del actualizador de la app: ventana y avisos de arranque.

La ventana es el `DialogoActualizacion` genérico, el mismo de yt-dlp: este
módulo solo le pone los textos y las acciones de la app. Nada de red corre
en el hilo de la interfaz: cada consulta y descarga va en un hilo de
`diagnostico` y vuelve con `ventana.en_hilo_principal`, que descarta en
silencio si la ventana ya se cerró.
"""

from __future__ import annotations

import configparser
import functools
import logging
import os
import sys
import webbrowser
from pathlib import Path

import wx

from bellbird.core import actualizacion
from bellbird.core import diagnostico
from bellbird.core import paths
from bellbird.core.config import APP_NAME, APP_VERSION, guardar_opcion
from bellbird.core.idioma import _
from bellbird.downloads import ytdlp_bin
from bellbird.ui import aviso_diferido
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player as _snd

logger = logging.getLogger(f"bellbird.{__name__}")

SECCION_AVISO = "actualizaciones"
CLAVE_AVISADA = "avisada"


# ── Versión avisada ──────────────────────────────────────────────────────
# Se guarda con `guardar_opcion`, el mismo mecanismo de las preferencias:
# escribe el config.ini en forma atómica y conserva comentarios y orden.

def leer_version_avisada(ruta: Path | None = None) -> str:
    """Última versión avisada al arrancar, o cadena vacía si no hay."""
    if ruta is None:
        ruta = paths.config_ini()
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(ruta, encoding="utf-8")
        return parser.get(SECCION_AVISO, CLAVE_AVISADA, fallback="").strip()
    except (OSError, configparser.Error, ValueError):
        return ""


def guardar_version_avisada(version: str, ruta: Path | None = None) -> bool:
    """Recuerda la versión avisada. Devuelve si pudo escribir."""
    if ruta is None:
        ruta = paths.config_ini()
    return guardar_opcion(ruta, SECCION_AVISO, CLAVE_AVISADA, version)


# ── Ganchos de arranque ──────────────────────────────────────────────────
# Los llama `iniciar_gui` después de `frame.Show()`, cada uno con
# `wx.CallLater` y sin bloquear el hilo de la interfaz. Ninguno revienta
# la app: cada uno captura sus excepciones y las registra.

def programar_confirmacion_arranque() -> None:
    """A los 1500 ms confirma el arranque tras una actualización."""
    try:
        wx.CallLater(1500, _confirmar_arranque)
    except Exception as exc:
        logger.warning("confirmación de arranque: %s", exc)


def _confirmar_arranque() -> None:
    try:
        actualizacion.confirmar_arranque(APP_VERSION)
    except Exception as exc:
        logger.warning("confirmación de arranque: %s", exc)


def programar_resultado_actualizacion(frame=None) -> None:
    """A los 4000 ms muestra el resultado de la última actualización.

    Recibe el frame para poder abrir la ventana del resultado cuando la
    app está empaquetada; desde código fuente solo anuncia, como siempre.
    """
    try:
        wx.CallLater(4000, _anunciar_resultado, frame)
    except Exception as exc:
        logger.warning("resultado de actualización: %s", exc)


def _anunciar_resultado(frame=None) -> None:
    try:
        resultado = actualizacion.tomar_resultado()
        texto = actualizacion.texto_resultado(resultado, APP_VERSION)
        if not texto:
            return
        if frame is not None and bool(getattr(sys, "frozen", False)):
            correcto = not (isinstance(resultado, dict)
                            and resultado.get("resultado") == "fallo")
            aviso_diferido.cuando_libre(
                frame, _mostrar_resultado_en_ventana,
                frame, texto, correcto)
            return
        anunciar(texto)
        if isinstance(resultado, dict) and resultado.get("resultado") == "fallo":
            _snd.reproducir("error")
    except Exception as exc:
        logger.warning("resultado de actualización: %s", exc)


def _mostrar_resultado_en_ventana(frame, texto: str, correcto: bool) -> None:
    """Abre la ventana del resultado con su texto, su barra y el foco."""
    from bellbird.ui.gui_actualizacion import DialogoActualizacion
    ventana = DialogoActualizacion(frame, _("Actualización"))
    ventana.Show()
    ventana.estado(texto)
    ventana.progreso(100 if correcto else 0)
    try:
        ventana.btn_cerrar.SetFocus()
    except Exception:
        pass
    if not correcto:
        try:
            _snd.reproducir("error")
        except Exception:
            pass
    else:
        try:
            _snd.reproducir("actualizacion_lista")
        except Exception:
            pass


def programar_aviso_version(frame) -> None:
    """A los 10000 ms consulta en un hilo si hay versión nueva y avisa.

    Empaquetada abre la ventana de actualización al arrancar, esperando a
    que el usuario quede libre si está ocupado. Desde código fuente se
    queda con el anuncio hablado, una vez por versión.
    """
    try:
        wx.CallLater(10000, _consultar_en_hilo, frame)
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)


def _consultar_en_hilo(frame) -> None:
    try:
        diagnostico.crear_hilo(
            lambda: _consultar_version(frame), "BuscarActualizacion").start()
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)


def _consultar_version(frame) -> None:
    try:
        actualizacion.limpiar_restos()
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)
    try:
        config = getattr(frame, "_config", None) or {}
        buscar = config.get("buscar_actualizaciones_al_iniciar", True)
    except Exception:
        buscar = True
    if not buscar:
        return
    try:
        paquete = actualizacion.consultar_ultima_version()
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)
        return
    if paquete is None:
        logger.debug("aviso de versión: sin conexión o sin paquete compatible")
        return
    if not actualizacion.hay_version_nueva(APP_VERSION, paquete.version):
        return
    wx.CallAfter(_decidir_aviso, frame, paquete)


def _decidir_aviso(frame, paquete) -> None:
    """En el hilo principal abre la ventana o, desde fuente, solo habla.

    Empaquetada siempre abre la ventana de actualización al arrancar: si el
    usuario está ocupado, la apertura espera a que quede libre. Desde código
    fuente se queda con el anuncio hablado, una vez por versión.
    """
    try:
        empaquetada = bool(getattr(sys, "frozen", False))
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)
        return
    if empaquetada:
        try:
            aviso_diferido.cuando_libre(
                frame,
                functools.partial(abrir_ventana_actualizacion, frame,
                                  paquete=paquete, al_arrancar=True))
        except Exception as exc:
            logger.warning("aviso de versión: %s", exc)
        return
    try:
        avisada = leer_version_avisada()
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)
        return
    if actualizacion.debe_avisar(paquete.version, APP_VERSION, avisada):
        _avisar_version(paquete.version)


def _avisar_version(version: str) -> None:
    try:
        anunciar(_("Hay una versión nueva de {app}, la {version}. "
                  "Para instalarla: menú Ayuda, Buscar actualizaciones.").format(app=APP_NAME, version=version))
        guardar_version_avisada(version)
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)


# ── Ventana ──────────────────────────────────────────────────────────────
# La abre el menú Ayuda. Con una abierta, el menú le da el foco en vez de
# abrir otra, igual que `_on_actualizar_ytdlp`.

class _FlujoActualizacion:
    """El recorrido de la ventana, de la consulta al instalador.

    Guarda el estado del recorrido: el paquete elegido y el
    último texto de progreso. Cada paso es un método corto.
    """

    def __init__(self, frame, ventana):
        self.frame = frame
        self.ventana = ventana
        self.paquete_elegido = None
        self.ultimo_texto = None

    def arrancar(self, paquete):
        """Muestra el paquete dado o consulta en un hilo si no hay."""
        if paquete is not None:
            self._mostrar_respuesta(paquete)
            return
        self.ventana.estado(_("Buscando la última versión."))
        diagnostico.crear_hilo(
            self._run_consulta, "BuscarActualizacion").start()

    def _run_consulta(self):
        try:
            paquete = actualizacion.consultar_ultima_version()
        except Exception as exc:
            logger.warning("consulta de versión: %s", exc)
            paquete = None
        self.ventana.en_hilo_principal(self._mostrar_respuesta, paquete)

    def _mostrar_respuesta(self, paquete):
        if paquete is None:
            self._mostrar_sin_respuesta()
            return
        if not actualizacion.hay_version_nueva(APP_VERSION, paquete.version):
            self.ventana.progreso(100)
            self.ventana.estado(_("Esta es la última versión, la {version}.").format(version=APP_VERSION))
            return
        self.paquete_elegido = paquete
        texto = (_("Hay una versión nueva, la {nueva}. La instalada es la {instalada}.").format(
            nueva=paquete.version, instalada=APP_VERSION))
        if not getattr(sys, "frozen", False):
            self.ventana.estado(texto + _(" Desde el código fuente no se instala: "
                                          "se actualiza con git."))
            self._ofrecer_pagina(paquete)
        elif not actualizacion.carpeta_admite_escritura(
                paths.carpeta_instalacion()):
            self.ventana.estado(texto + _(" La carpeta del programa no admite "
                                          "cambios. Se puede descargar a mano desde la página."))
            self._ofrecer_pagina(paquete)
        else:
            self.ventana.estado(texto)
            if paquete.notas:
                self.ventana.notas(paquete.notas)
            self.ventana.ofrecer_accion(_("&Descargar e instalar"), self._descargar)

    def _mostrar_sin_respuesta(self):
        self.ventana.progreso(0)
        self.ventana.estado(_("No se pudo consultar si hay una versión nueva. "
                              "Revise la conexión a Internet."))

    def _ofrecer_pagina(self, paquete):
        if paquete.notas:
            self.ventana.notas(paquete.notas)
        self.ventana.ofrecer_accion(_("&Abrir la página"), self._abrir_pagina)

    def _abrir_pagina(self):
        try:
            webbrowser.open(actualizacion.URL_PAGINA_RELEASES)
        except Exception as exc:
            logger.warning("página de releases: %s", exc)

    def _descargar(self):
        self.ventana.quitar_accion()
        self.ventana.estado(
            _("Descargando la versión {version}.").format(version=self.paquete_elegido.version))
        diagnostico.crear_hilo(
            self._run_descarga, "DescargarActualizacion").start()

    def _run_descarga(self):
        try:
            resultado = actualizacion.descargar_paquete(
                self.paquete_elegido.url_zip, self.paquete_elegido.url_firma,
                paths.paquete_descargado(),
                aviso_progreso=self._aviso_progreso,
                cancelar=self.ventana.cancelado.is_set)
        except Exception as exc:
            logger.warning("descarga del paquete: %s", exc)
            resultado = actualizacion.ResultadoDescarga(
                False, _("no se pudo descargar el paquete: {detalle}").format(detalle=exc))
        self.ventana.en_hilo_principal(self._terminar_descarga, resultado)

    def _aviso_progreso(self, porcentaje):
        self.ventana.en_hilo_principal(self._actualizar_progreso, porcentaje)

    def _actualizar_progreso(self, porcentaje):
        self.ventana.progreso(porcentaje)
        if ytdlp_bin.debe_actualizar_texto_progreso(
                self.ultimo_texto, porcentaje):
            self.ultimo_texto = porcentaje
            self.ventana.txt_estado.SetValue(
                _("Descargando la versión {version}: {porcentaje} por ciento").format(
                    version=self.paquete_elegido.version, porcentaje=porcentaje))

    def _terminar_descarga(self, resultado):
        if not resultado.correcta:
            self._mostrar_descarga_fallida(resultado)
            return
        self.ventana.estado(_("Comprobando el paquete."))
        diagnostico.crear_hilo(
            self._run_extraer, "ComprobarPaquete").start()

    def _mostrar_descarga_fallida(self, resultado):
        motivo = resultado.motivo or _("motivo desconocido")
        self.ventana.progreso(0)
        if resultado.codigo == "cancelada":
            self.ventana.estado(_("Descarga cancelada."))
        elif resultado.codigo == "firma_distinta":
            self.ventana.estado(_("La descarga no se completó: "
                                  "la firma SHA-256 no coincide."))
        else:
            self.ventana.estado(_("La descarga no se completó: {motivo}.").format(motivo=motivo))

    def _run_extraer(self):
        try:
            raiz = actualizacion.extraer_paquete(
                paths.paquete_descargado(), paths.paquete_extraido())
        except actualizacion.PaqueteInvalido as exc:
            self.ventana.en_hilo_principal(
                self._mostrar_paquete_invalido, str(exc))
            return
        except Exception as exc:
            logger.warning("extracción del paquete: %s", exc)
            self.ventana.en_hilo_principal(
                self._mostrar_paquete_invalido, str(exc))
            return
        try:
            Path(paths.paquete_descargado()).unlink(missing_ok=True)
        except OSError as error:
            logger.debug("no se pudo borrar el paquete descargado %s: %s", paths.paquete_descargado(), error)
        try:
            ejecutable = actualizacion.validar_paquete(
                raiz, self.paquete_elegido.version)
        except actualizacion.PaqueteInvalido as exc:
            self.ventana.en_hilo_principal(
                self._mostrar_paquete_invalido, str(exc))
            return
        except Exception as exc:
            logger.warning("validación del paquete: %s", exc)
            self.ventana.en_hilo_principal(
                self._mostrar_paquete_invalido, str(exc))
            return
        self.ventana.en_hilo_principal(self._mostrar_listo, raiz, ejecutable)

    def _mostrar_paquete_invalido(self, motivo):
        self.ventana.estado(_("El paquete no sirve: {motivo}.").format(motivo=motivo))

    def _mostrar_listo(self, raiz, ejecutable):
        self.ventana.estado(_("La actualización está preparada. {app} se cierra y vuelve "
                              "a abrirse sola en alrededor de un minuto. Si hay un "
                              "chat conectado o un directo en curso, se interrumpe.").format(app=APP_NAME))
        self.ventana.ofrecer_accion(
            _("&Instalar y reiniciar"),
            lambda: self._instalar(raiz, ejecutable))

    def _instalar(self, raiz, ejecutable):
        try:
            actualizacion.lanzar_instalador(
                raiz, ejecutable, paths.carpeta_instalacion(),
                paths.ejecutable_actual(), os.getpid(), APP_VERSION)
        except Exception as exc:
            self.ventana.estado(_("No se pudo iniciar la instalación: {detalle}.").format(detalle=exc))
            return
        self.frame._cerrar_sin_preguntar = True
        self.frame.Close()


def abrir_ventana_actualizacion(frame, paquete=None, al_arrancar=False) -> None:
    """Abre la ventana de actualización o enfoca la ya abierta.

    Con `paquete` no consulta la red: muestra esa respuesta directamente.
    Con `al_arrancar` el botón Cerrar pasa a decir «Más tarde».
    """
    from bellbird.ui.gui_actualizacion import DialogoActualizacion
    abierta = getattr(frame, "_ventana_actualizar_app", None)
    if abierta is not None and not abierta.cerrado:
        try:
            abierta.Raise()
        except Exception:
            pass
        try:
            abierta.btn_cerrar.SetFocus()
        except Exception:
            pass
        return
    ventana = DialogoActualizacion(frame, _("Buscar actualizaciones"))
    frame._ventana_actualizar_app = ventana
    if al_arrancar:
        ventana.etiqueta_cerrar(_("&Más tarde"))
    ventana.Show()
    if al_arrancar:
        try:
            _snd.reproducir("actualizacion_disponible")
        except Exception:
            pass
    _FlujoActualizacion(frame, ventana).arrancar(paquete)

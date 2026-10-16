"""Interfaz del actualizador de la app: ventana y avisos de arranque.

La ventana es el `DialogoActualizacion` genérico, el mismo de yt-dlp: este
módulo solo le pone los textos y las acciones de la app. Nada de red corre
en el hilo de la interfaz: cada consulta y descarga va en un hilo de
`diagnostico` y vuelve con `ventana.en_hilo_principal`, que descarta en
silencio si la ventana ya se cerró.
"""

from __future__ import annotations

import configparser
import logging
import os
import sys
import webbrowser
from pathlib import Path

import wx

from ytchat.core import actualizacion
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.core.config import APP_NAME, APP_VERSION, guardar_opcion
from ytchat.downloads import ytdlp_bin
from ytchat.ui.gui import anunciar
from ytchat.voice import sound_player as _snd

logger = logging.getLogger(f"ytchat.{__name__}")

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
        return parser.get(SECCION_AVISO, CLAVE_AVISADA,
                          fallback="").strip()
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


def programar_resultado_actualizacion() -> None:
    """A los 4000 ms anuncia el resultado de la última actualización."""
    try:
        wx.CallLater(4000, _anunciar_resultado)
    except Exception as exc:
        logger.warning("resultado de actualización: %s", exc)


def _anunciar_resultado() -> None:
    try:
        resultado = actualizacion.tomar_resultado()
        texto = actualizacion.texto_resultado(resultado, APP_VERSION)
        if not texto:
            return
        anunciar(texto)
        if isinstance(resultado, dict) and resultado.get("resultado") == "fallo":
            _snd.reproducir("error")
    except Exception as exc:
        logger.warning("resultado de actualización: %s", exc)


def programar_aviso_version(frame) -> None:
    """A los 10000 ms consulta en un hilo si hay versión nueva y avisa.

    Empaquetada, sin chat conectado y sin transmisión en curso, abre la
    ventana de actualización al arrancar. En cualquier otro caso se queda
    con el anuncio hablado, una vez por versión.
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
    """En el hilo principal decide entre abrir la ventana o solo hablar."""
    try:
        empaquetada = bool(getattr(sys, "frozen", False))
        if (empaquetada and not frame._conectado
                and not frame._supervisar_transmision("activo")):
            abrir_ventana_actualizacion(frame, paquete=paquete,
                                        al_arrancar=True)
            return
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
        anunciar(f"Hay una versión nueva de {APP_NAME}, la {version}. "
                  "Para instalarla: menú Ayuda, Buscar actualizaciones.")
        guardar_version_avisada(version)
    except Exception as exc:
        logger.warning("aviso de versión: %s", exc)


# ── Ventana ──────────────────────────────────────────────────────────────
# La abre el menú Ayuda. Con una abierta, el menú le da el foco en vez de
# abrir otra, igual que `_on_actualizar_ytdlp`.

def abrir_ventana_actualizacion(frame, paquete=None, al_arrancar=False) -> None:
    """Abre la ventana de actualización o enfoca la ya abierta.

    Con `paquete` no consulta la red: muestra esa respuesta directamente.
    Con `al_arrancar` el botón Cerrar pasa a decir «Más tarde».
    """
    from ytchat.ui.gui_actualizacion import DialogoActualizacion
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
    ventana = DialogoActualizacion(frame, "Buscar actualizaciones")
    frame._ventana_actualizar_app = ventana
    if al_arrancar:
        ventana.etiqueta_cerrar("&Más tarde")
    ventana.Show()
    ultimo_texto = None
    paquete_elegido = None

    def _run_consulta():
        try:
            paquete = actualizacion.consultar_ultima_version()
        except Exception as exc:
            logger.warning("consulta de versión: %s", exc)
            paquete = None
        ventana.en_hilo_principal(_mostrar_respuesta, paquete)

    def _mostrar_respuesta(paquete):
        nonlocal paquete_elegido
        if paquete is None:
            ventana.progreso(0)
            ventana.estado("No se pudo consultar si hay una versión nueva. "
                           "Revise la conexión a Internet.")
            return
        if not actualizacion.hay_version_nueva(APP_VERSION, paquete.version):
            ventana.progreso(100)
            ventana.estado(f"Esta es la última versión, la {APP_VERSION}.")
            return
        paquete_elegido = paquete
        texto = (f"Hay una versión nueva, la {paquete.version}. "
                 f"La instalada es la {APP_VERSION}.")
        if not getattr(sys, "frozen", False):
            ventana.estado(texto + " Desde el código fuente no se instala: "
                           "se actualiza con git.")
            if paquete.notas:
                ventana.notas(paquete.notas)
            ventana.ofrecer_accion("&Abrir la página", _abrir_pagina)
        elif not actualizacion.carpeta_admite_escritura(
                paths.carpeta_instalacion()):
            ventana.estado(texto + " La carpeta del programa no admite "
                           "cambios. Se puede descargar a mano desde la página.")
            if paquete.notas:
                ventana.notas(paquete.notas)
            ventana.ofrecer_accion("&Abrir la página", _abrir_pagina)
        else:
            ventana.estado(texto)
            if paquete.notas:
                ventana.notas(paquete.notas)
            ventana.ofrecer_accion("&Descargar e instalar", _descargar)

    def _abrir_pagina():
        try:
            webbrowser.open(actualizacion.URL_PAGINA_RELEASES)
        except Exception as exc:
            logger.warning("página de releases: %s", exc)

    def _descargar():
        ventana.quitar_accion()
        ventana.estado(f"Descargando la versión {paquete_elegido.version}.")
        diagnostico.crear_hilo(_run_descarga, "DescargarActualizacion").start()

    def _run_descarga():
        try:
            resultado = actualizacion.descargar_paquete(
                paquete_elegido.url_zip, paquete_elegido.url_firma,
                paths.paquete_descargado(),
                aviso_progreso=_aviso_progreso,
                cancelar=ventana.cancelado.is_set)
        except Exception as exc:
            logger.warning("descarga del paquete: %s", exc)
            resultado = actualizacion.ResultadoDescarga(
                False, f"no se pudo descargar el paquete: {exc}")
        ventana.en_hilo_principal(_terminar_descarga, resultado)

    def _aviso_progreso(porcentaje):
        ventana.en_hilo_principal(_actualizar_progreso, porcentaje)

    def _actualizar_progreso(porcentaje):
        nonlocal ultimo_texto
        ventana.progreso(porcentaje)
        if ytdlp_bin.debe_actualizar_texto_progreso(ultimo_texto, porcentaje):
            ultimo_texto = porcentaje
            ventana.txt_estado.SetValue(
                f"Descargando la versión {paquete_elegido.version}: "
                f"{porcentaje} por ciento")

    def _terminar_descarga(resultado):
        if not resultado.correcta:
            motivo = resultado.motivo or "motivo desconocido"
            ventana.progreso(0)
            if "cancelada" in motivo.lower():
                ventana.estado("Descarga cancelada.")
            elif "firma" in motivo.lower():
                ventana.estado("La descarga no se completó: "
                               "la firma SHA-256 no coincide.")
            else:
                ventana.estado(f"La descarga no se completó: {motivo}.")
            return
        ventana.estado("Comprobando el paquete.")
        diagnostico.crear_hilo(_run_extraer, "ComprobarPaquete").start()

    def _run_extraer():
        try:
            raiz = actualizacion.extraer_paquete(
                paths.paquete_descargado(), paths.paquete_extraido())
        except actualizacion.PaqueteInvalido as exc:
            ventana.en_hilo_principal(_mostrar_paquete_invalido, str(exc))
            return
        except Exception as exc:
            logger.warning("extracción del paquete: %s", exc)
            ventana.en_hilo_principal(_mostrar_paquete_invalido, str(exc))
            return
        try:
            Path(paths.paquete_descargado()).unlink(missing_ok=True)
        except OSError:
            pass
        try:
            ejecutable = actualizacion.validar_paquete(
                raiz, paquete_elegido.version)
        except actualizacion.PaqueteInvalido as exc:
            ventana.en_hilo_principal(_mostrar_paquete_invalido, str(exc))
            return
        except Exception as exc:
            logger.warning("validación del paquete: %s", exc)
            ventana.en_hilo_principal(_mostrar_paquete_invalido, str(exc))
            return
        ventana.en_hilo_principal(_mostrar_listo, raiz, ejecutable)

    def _mostrar_paquete_invalido(motivo):
        ventana.estado(f"El paquete no sirve: {motivo}.")

    def _mostrar_listo(raiz, ejecutable):
        ventana.estado(f"Listo para instalar. {APP_NAME} se cierra y vuelve "
                       "a abrirse sola en alrededor de un minuto. Si hay un "
                       "chat conectado o un directo en curso, se corta.")
        ventana.ofrecer_accion(
            "&Instalar y reiniciar",
            lambda: _instalar(raiz, ejecutable))

    def _instalar(raiz, ejecutable):
        try:
            actualizacion.lanzar_instalador(
                raiz, ejecutable, paths.carpeta_instalacion(),
                paths.ejecutable_actual(), os.getpid(), APP_VERSION)
        except Exception as exc:
            ventana.estado(f"No se pudo iniciar la instalación: {exc}.")
            return
        frame.Close()

    if paquete is not None:
        _mostrar_respuesta(paquete)
        return
    ventana.estado("Buscando la última versión.")
    diagnostico.crear_hilo(_run_consulta, "BuscarActualizacion").start()

"""Ventana de actualización de yt-dlp.

El cuerpo de `abrir_ventana_actualizacion` es el antiguo
`YTChatFrame._on_actualizar_ytdlp`, movido sin cambios, igual que ya hace
`gui_actualizar_app.abrir_ventana_actualizacion(frame)` para la app. En la
clase queda un delegado de dos líneas porque lo enlazan el menú
Herramientas y las pruebas.
"""

from __future__ import annotations

from bellbird.core.idioma import _
from bellbird.downloads import ytdlp_actualizar


def abrir_ventana_actualizacion(frame) -> None:
    """Abre la ventana de actualización de yt-dlp o enfoca la ya abierta."""
    from bellbird.ui.gui import diagnostico, logger
    from bellbird.ui.gui_actualizacion import DialogoActualizacion
    abierta = getattr(frame, "_ventana_actualizar_ytdlp", None)
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
    ventana = DialogoActualizacion(frame, _("Actualizar yt-dlp"))
    frame._ventana_actualizar_ytdlp = ventana
    ventana.Show()
    ventana.estado(_("Buscando la última versión de yt-dlp."))
    ultimo_texto = None

    def _avisar(version_nueva):
        ventana.en_hilo_principal(
            _mostrar_descarga, version_nueva)

    def _mostrar_descarga(version_nueva):
        # Traductores: {version} es la versión nueva de yt-dlp.
        texto = _("Hay una versión nueva de yt-dlp, la {version}. "
                  "Descargando.")
        ventana.estado(texto.format(version=version_nueva))

    def _progreso(porcentaje, _descargado, _total):
        ventana.en_hilo_principal(_actualizar_progreso, porcentaje)

    def _actualizar_progreso(porcentaje):
        nonlocal ultimo_texto
        ventana.progreso(porcentaje)
        if ytdlp_actualizar.debe_actualizar_texto_progreso(ultimo_texto, porcentaje):
            ultimo_texto = porcentaje
            # Traductores: {porcentaje} es el avance de 0 a 100.
            texto = _("Descargando yt-dlp: {porcentaje} por ciento")
            ventana.txt_estado.SetValue(texto.format(porcentaje=porcentaje))

    def _terminar(estado, texto):
        if ytdlp_actualizar.resultado_actualizacion_es_fallo(estado):
            ventana.progreso(0)
        else:
            ventana.progreso(100)
        ventana.estado(texto)
        try:
            ventana.btn_cerrar.SetFocus()
        except Exception:
            pass

    def _run():
        try:
            estado, version_actual, version_nueva = ytdlp_actualizar.actualizar_ytdlp(
                _avisar, _progreso, ventana.cancelado.is_set)
            texto = ytdlp_actualizar.mensaje_de_actualizacion(
                estado, version_actual, version_nueva)
        except Exception as exc:
            logger.warning("actualización de yt-dlp: %s", exc)
            estado = "otro_fallo"
            texto = ytdlp_actualizar.mensaje_de_actualizacion(
                "otro_fallo", motivo=str(exc))
        ventana.en_hilo_principal(_terminar, estado, texto)

    diagnostico.crear_hilo(_run, "ActualizarYtdlp").start()

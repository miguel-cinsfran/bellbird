"""Estado de la conexión vigente: qué directo, qué chat y de qué plataforma."""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.capture import deteccion


@dataclass
class SesionConectada:
    live_chat_id: str = ""
    video_id: str = ""  # vídeo de YouTube de la conexión vigente
    enlace_directo: str = ""  # URL del directo conectado, solo si es live
    causa_sin_chat: str = ""
    usuario_tiktok: str = ""  # usuario del directo conectado
    url_flujo_tiktok: str = ""  # flujo FLV o HLS del directo vigente
    conexion_propia: bool = False  # la pidió la transmisión
    chat_propio: bool = False  # el directo conectado es del canal propio
    tipo_video: str = deteccion.DESCONOCIDO
    es_tiktok: bool = False  # para que F2 distinga TikTok de YouTube (ambos LIVE)
    descartes_avisado: bool = False

    def acepta_chat_de(self, video_id: str | None) -> bool:
        """Si el chat que llega es de esta conexión.

        Descarta la respuesta tardía del hilo LiveChatId de una
        conexión anterior: con ese id, el compositor y los mensajes
        programados escribirían en el chat del directo equivocado.
        """
        return video_id is None or video_id == self.video_id

    def es_reconexion_tiktok(self, usuario: str) -> bool:
        """Si el usuario ya tiene la sesión: reconecta, no conecta."""
        return (self.es_tiktok and bool(self.usuario_tiktok)
                and self.usuario_tiktok == usuario)

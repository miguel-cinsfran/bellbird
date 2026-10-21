"""Pruebas puras de los textos de la ventana Preguntar a la IA.

Sin wx.App ni ventanas: solo importa `ventana_ia`, que no crea
controles al importarse.
"""

import unittest
from datetime import datetime

from ytchat.ai import ventana_ia
from ytchat.ai import conversacion
from ytchat.ai import protocolos


class TestTextosVentanaIA(unittest.TestCase):

    def test_constantes(self):
        self.assertEqual(
            ventana_ia.FILA_GUIA,
            "Sin mensajes. Agrega una captura y escribe tu pregunta.")
        self.assertEqual(ventana_ia.TEXTO_ANALIZANDO, "Analizando…")
        self.assertEqual(ventana_ia.TEXTO_CANCELADA, "Consulta cancelada.")
        self.assertEqual(ventana_ia.TEXTO_COPIADA, "Respuesta copiada.")
        self.assertEqual(
            ventana_ia.TEXTO_NO_COPIADA,
            "No se pudo copiar la respuesta.")
        self.assertEqual(
            ventana_ia.TEXTO_SIN_RESPUESTA,
            "Todavía no hay ninguna respuesta.")
        self.assertEqual(ventana_ia.TEXTO_NUEVA, "Conversación nueva.")

    def test_captura_agregada_nombra_la_fuente(self):
        self.assertEqual(
            ventana_ia.texto_captura_agregada("Cámara"),
            "Captura agregada: Cámara.")

    def test_filas_visibles_con_guia_si_vacia(self):
        self.assertEqual(
            ventana_ia.filas_visibles([]), [ventana_ia.FILA_GUIA])
        self.assertEqual(
            ventana_ia.filas_visibles(["a", "b"]), ["a", "b"])

    def test_ultima_respuesta_sin_respuesta(self):
        charla = conversacion.Conversacion()
        self.assertIsNone(ventana_ia.ultima_respuesta(charla))

    def test_ultima_respuesta_devuelve_la_ultima(self):
        charla = conversacion.Conversacion()
        charla.mensajes.append(protocolos.Mensaje("usuario", "hola"))
        charla.mensajes.append(protocolos.Mensaje("asistente", "primera"))
        charla.mensajes.append(protocolos.Mensaje("usuario", "otra"))
        charla.mensajes.append(protocolos.Mensaje("asistente", "final"))
        self.assertEqual(ventana_ia.ultima_respuesta(charla), "final")

    def test_hora_de_formato(self):
        self.assertEqual(
            ventana_ia.hora_de(datetime(2026, 10, 20, 9, 5)), "09:05")


if __name__ == "__main__":
    unittest.main()

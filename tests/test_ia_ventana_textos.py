"""Pruebas puras de los textos de la ventana Preguntar a la IA.

Sin wx.App ni ventanas: solo importa `ventana_ia`, que no crea
controles al importarse.
"""

import unittest
from datetime import datetime

from tests.pseudo_prueba import con_pseudo
from ytchat.ai import ventana_ia
from ytchat.ai import conversacion
from ytchat.ai import protocolos
from ytchat.core.idioma import _


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


class TestTextosMarcados(unittest.TestCase):

    def test_guia_de_lista_vacia_va_marcada(self):
        with con_pseudo():
            guia = ventana_ia.filas_visibles([])
        self.assertEqual(
            guia,
            ["[¡Sin mensajes. Agrega una captura y escribe tu pregunta.!]"])

    def test_filas_con_datos_pasan_sin_marcar(self):
        fila = "Captura: Cámara, 10:00"
        with con_pseudo():
            self.assertEqual(ventana_ia.filas_visibles([fila]), [fila])

    def test_captura_agregada_nombra_la_fuente_marcada(self):
        with con_pseudo():
            texto = ventana_ia.texto_captura_agregada("Cámara")
        self.assertEqual(texto, "[¡Captura agregada: Cámara.!]")

    def test_constantes_se_traducen_donde_se_usan(self):
        with con_pseudo():
            marcados = [_(ventana_ia.TEXTO_ANALIZANDO),
                        _(ventana_ia.TEXTO_CANCELADA),
                        _(ventana_ia.TEXTO_COPIADA),
                        _(ventana_ia.TEXTO_NO_COPIADA),
                        _(ventana_ia.TEXTO_SIN_RESPUESTA),
                        _(ventana_ia.TEXTO_NUEVA)]
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


if __name__ == "__main__":
    unittest.main()

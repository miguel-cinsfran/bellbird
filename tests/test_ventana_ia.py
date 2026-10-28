"""Pseudotraducción de los textos puros de la ventana Preguntar a la IA.

Sin ventanas: llama a las funciones de `ventana_ia` bajo `con_pseudo()`
y exige los fragmentos propios marcados y los datos sin marcar.
"""

import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.ai import ventana_ia
from ytchat.core.idioma import _


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

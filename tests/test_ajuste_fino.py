"""Pruebas de las decisiones del ajuste fino."""

import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.obs import ajuste_fino


class TestAjusteFino(unittest.TestCase):

    def test_flecha_izquierda_mueve_a_la_izquierda(self):
        self.assertEqual(ajuste_fino.resolver(314, False, False), ("mover", -10, 0))

    def test_flecha_derecha_mueve_a_la_derecha(self):
        self.assertEqual(ajuste_fino.resolver(316, False, False), ("mover", 10, 0))

    def test_flecha_arriba_mueve_hacia_arriba(self):
        self.assertEqual(ajuste_fino.resolver(315, False, False), ("mover", 0, -10))

    def test_flecha_abajo_mueve_hacia_abajo(self):
        self.assertEqual(ajuste_fino.resolver(317, False, False), ("mover", 0, 10))

    def test_control_usa_paso_grande(self):
        self.assertEqual(ajuste_fino.resolver(316, True, False), ("mover", 50, 0))

    def test_mayusculas_usa_paso_fino(self):
        self.assertEqual(ajuste_fino.resolver(316, False, True), ("mover", 1, 0))

    def test_control_manda_sobre_mayusculas(self):
        self.assertEqual(ajuste_fino.resolver(316, True, True), ("mover", 50, 0))

    def test_intro_confirma(self):
        self.assertEqual(ajuste_fino.resolver(13, False, False), ("confirmar", 0, 0))

    def test_escape_cancela(self):
        self.assertEqual(ajuste_fino.resolver(27, False, False), ("cancelar", 0, 0))

    def test_tab_sale(self):
        self.assertEqual(ajuste_fino.resolver(9, False, False), ("salir", 0, 0))

    def test_otra_tecla_se_ignora(self):
        self.assertEqual(ajuste_fino.resolver(ord("A"), False, False), ("ignorar", 0, 0))

    def test_etiqueta_activa(self):
        self.assertEqual(ajuste_fino.etiqueta_boton(True, "Ajuste &fino"),
                         "Ajustando, flechas para mover")

    def test_etiqueta_inactiva(self):
        self.assertEqual(ajuste_fino.etiqueta_boton(False, "Ajuste &fino"),
                         "Ajuste &fino")

    def test_texto_de_entrada(self):
        self.assertEqual(ajuste_fino.texto_de_entrada(),
                         "Ajuste fino. Flechas para mover, Control para pasos grandes, "
                         "Mayúsculas para pasos de un píxel. Intro confirma, Escape deshace, "
                         "Tab sale.")

    def test_texto_de_entrada_sale_marcado(self):
        with con_pseudo():
            texto = ajuste_fino.texto_de_entrada()
        self.assertTrue(texto.startswith("[¡"), texto)


class TestEstadoAjuste(unittest.TestCase):

    def test_valores_iniciales(self):
        estado = ajuste_fino.EstadoAjuste()
        self.assertFalse(estado.en_curso)
        self.assertFalse(estado.en_vuelo)
        self.assertFalse(estado.deshacer_pendiente)
        self.assertIsNone(estado.transformacion)

    def test_entrar_guarda_y_activa(self):
        estado = ajuste_fino.EstadoAjuste()
        transformacion = {"positionX": 32}
        estado.entrar(transformacion)
        self.assertTrue(estado.en_curso)
        self.assertIs(estado.transformacion, transformacion)

    def test_puede_mover_falso_fuera_del_ajuste(self):
        self.assertFalse(ajuste_fino.EstadoAjuste().puede_mover())

    def test_puede_mover_verdadero_en_curso(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        self.assertTrue(estado.puede_mover())

    def test_puede_mover_falso_con_movimiento_en_vuelo(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        estado.empezar_movimiento()
        self.assertFalse(estado.puede_mover())

    def test_aterrizar_apaga_el_vuelo_y_muestra(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        estado.empezar_movimiento()
        self.assertEqual(estado.aterrizar(), ajuste_fino.MOSTRAR)
        self.assertFalse(estado.en_vuelo)

    def test_aterrizar_deshace_si_hay_pendiente(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        estado.empezar_movimiento()
        estado.salir(False)
        self.assertEqual(estado.aterrizar(), ajuste_fino.DESHACER)

    def test_aterrizar_nada_si_ya_no_esta_en_curso(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        estado.empezar_movimiento()
        estado.salir(True)
        self.assertEqual(estado.aterrizar(), ajuste_fino.NADA)

    def test_salir_nada_si_no_esta_en_curso(self):
        self.assertEqual(ajuste_fino.EstadoAjuste().salir(False), ajuste_fino.NADA)
        self.assertEqual(ajuste_fino.EstadoAjuste().salir(True), ajuste_fino.NADA)

    def test_salir_confirmado(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        self.assertEqual(estado.salir(True), ajuste_fino.CONFIRMADO)
        self.assertFalse(estado.en_curso)

    def test_salir_espera_con_movimiento_en_vuelo(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        estado.empezar_movimiento()
        self.assertEqual(estado.salir(False), ajuste_fino.ESPERAR)
        self.assertFalse(estado.en_curso)
        self.assertTrue(estado.deshacer_pendiente)

    def test_salir_deshace_sin_vuelo(self):
        estado = ajuste_fino.EstadoAjuste()
        estado.entrar({})
        self.assertEqual(estado.salir(False), ajuste_fino.DESHACER)

    def test_secuencia_escape_con_flecha_en_vuelo(self):
        estado = ajuste_fino.EstadoAjuste()
        transformacion = {"positionX": 32, "positionY": 18, "alignment": 5}
        estado.entrar(transformacion)
        estado.empezar_movimiento()
        self.assertEqual(estado.salir(False), ajuste_fino.ESPERAR)
        self.assertEqual(estado.aterrizar(), ajuste_fino.DESHACER)
        self.assertIs(estado.tomar_para_deshacer(), transformacion)
        self.assertFalse(estado.deshacer_pendiente)


if __name__ == "__main__":
    unittest.main()

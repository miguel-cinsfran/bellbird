"""Diseños de fábrica y cómo se completan con las fuentes de una escena."""

import unittest

from bellbird.obs import disenos_escena, disenos_fabrica


def _fuentes():
    return [
        disenos_escena.Fuente("Juego", "otra", 1600, 900),
        disenos_escena.Fuente("Cámara", "camara", 1280, 720),
        disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620),
    ]


class FabricaTest(unittest.TestCase):

    def test_los_seis_disenos_en_orden(self):
        self.assertEqual(
            [fabrica.nombre for fabrica in disenos_fabrica.FABRICA],
            ["Fuente principal con cámara en una esquina",
             "Fuente principal con cámara y chat a la derecha",
             "Fuente principal a pantalla completa",
             "Cámara a pantalla completa",
             "Fuente principal y cámara lado a lado",
             "Fuente principal grande y cámara a la derecha"])

    def test_cada_diseno_se_calcula_con_juego_camara_y_chat(self):
        fuentes = _fuentes()
        for fabrica in disenos_fabrica.FABRICA:
            with self.subTest(diseno=fabrica.clave):
                diseno = disenos_fabrica.completar(
                    fabrica.diseno, fabrica.papeles, fuentes)
                disenos_escena.calcular(1600, 900, fuentes, diseno)

    def test_completar_pone_la_camara_y_el_juego_donde_van(self):
        fuentes = [disenos_escena.Fuente("Cámara", "camara", 1280, 720),
                   disenos_escena.Fuente("Juego", "otra", 1600, 900),
                   disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620)]
        imagen = disenos_fabrica.FABRICA[0]
        completa = disenos_fabrica.completar(
            imagen.diseno, imagen.papeles, fuentes)
        self.assertEqual((completa.principal, completa.secundaria),
                         ("Juego", "Cámara"))
        dividida = disenos_fabrica.FABRICA[4]
        completa = disenos_fabrica.completar(
            dividida.diseno, dividida.papeles, fuentes)
        self.assertEqual((completa.izquierda, completa.derecha),
                         ("Juego", "Cámara"))

    def test_papel_principal_acepta_captura_y_otra(self):
        self.assertIn("captura", disenos_fabrica.PAPEL_PRINCIPAL)
        self.assertIn("otra", disenos_fabrica.PAPEL_PRINCIPAL)
        fuentes = [disenos_escena.Fuente("Pantalla", "captura", 1600, 900),
                   disenos_escena.Fuente("Imagen", "otra", 800, 600)]
        for fuente in fuentes:
            with self.subTest(tipo=fuente.tipo):
                completa = disenos_fabrica.completar(
                    disenos_escena.Diseno(clase="pantalla_completa"),
                    {"principal": disenos_fabrica.PAPEL_PRINCIPAL}, [fuente])
                self.assertEqual(completa.principal, fuente.nombre)

    def test_el_chat_y_la_camara_no_van_a_la_principal_si_hay_otra(self):
        fuentes = [disenos_escena.Fuente("Cámara", "camara", 1280, 720),
                   disenos_escena.Fuente("Juego", "otra", 1600, 900),
                   disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620)]
        completa = disenos_fabrica.completar(
            disenos_escena.Diseno(clase="pantalla_completa"),
            {"principal": disenos_fabrica.PAPEL_PRINCIPAL}, fuentes)
        self.assertEqual(completa.principal, "Juego")

    def test_completar_conserva_el_nombre_guardado_que_sigue_en_la_escena(self):
        diseno = disenos_escena.Diseno(
            clase="dividida", izquierda="Cámara", derecha="Juego",
            proporcion="mitades")
        completa = disenos_fabrica.completar(
            diseno, {"izquierda": "otra", "derecha": "otra"}, _fuentes())
        self.assertEqual((completa.izquierda, completa.derecha),
                         ("Cámara", "Juego"))

    def test_completar_reemplaza_el_nombre_guardado_que_no_esta(self):
        fuentes = [disenos_escena.Fuente("Cámara", "camara", 1280, 720),
                   disenos_escena.Fuente("Juego", "otra", 1600, 900)]
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Vieja")
        completa = disenos_fabrica.completar(
            diseno, {"principal": "otra"}, fuentes)
        self.assertEqual(completa.principal, "Juego")

    def test_completar_no_repite_y_no_pone_chat(self):
        fuentes = [disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620),
                   disenos_escena.Fuente("Juego", "otra", 1600, 900)]
        diseno = disenos_escena.Diseno(clase="imagen_en_imagen")
        completa = disenos_fabrica.completar(
            diseno, {"principal": "otra", "secundaria": "camara"}, fuentes)
        self.assertEqual((completa.principal, completa.secundaria),
                         ("Juego", ""))
        self.assertNotIn("Chat en el vídeo",
                         (completa.principal, completa.secundaria))


class MotivoTest(unittest.TestCase):

    def test_sin_fuente_en_un_lugar(self):
        diseno = disenos_escena.Diseno(clase="pantalla_completa")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
            ("principal", "Elige una fuente para la fuente principal."))

    def test_fuente_que_no_esta_en_la_escena(self):
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Vieja")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
            ("principal", "Elige una fuente para la fuente principal."))

    def test_fuente_repetida_nombra_el_segundo_lugar(self):
        diseno = disenos_escena.Diseno(
            clase="dividida", izquierda="Juego", derecha="Juego")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
            ("derecha", "Juego está en dos lugares. Elige otra."))

    def test_chat_sin_panel(self):
        fuentes = [disenos_escena.Fuente("Juego", "otra", 1600, 900)]
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Juego", chat="franja")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, fuentes),
            ("chat", "La escena no tiene el chat en el vídeo. Elige Sin chat "
                     "o activa Mostrar chat en el vídeo en la pestaña "
                     "Transmisión."))


class ResumenTest(unittest.TestCase):

    def test_nombra_el_diseno_y_cada_fuente_sin_el_chat(self):
        texto = disenos_fabrica.resumen("Mi diseño", [
            ("Cámara", disenos_escena.ESTADO_LLENA),
            ("Juego", disenos_escena.ESTADO_AJUSTA),
            ("Tarde", disenos_escena.ESTADO_AJUSTA_SIN_ORIGEN),
            ("Chat en el vídeo", ""),
        ])
        self.assertEqual(
            texto,
            "Diseño aplicado: Mi diseño. Cámara llena su lugar, con los "
            "bordes recortados. Juego se ajusta a su lugar. Tarde todavía no "
            "informa su tamaño y se ajusta a su lugar.")
        self.assertNotIn("Chat en el vídeo", texto)

    def test_sin_fuentes_que_no_se_movieron_no_agrega_la_frase(self):
        texto = disenos_fabrica.resumen("Mi diseño", [])
        self.assertEqual(texto, "Diseño aplicado: Mi diseño.")

    def test_nombra_las_fuentes_de_la_escena_que_no_se_movieron(self):
        texto = disenos_fabrica.resumen(
            "Mi diseño", [], sin_mover=("Cámara", "Chat en el vídeo"))
        self.assertEqual(
            texto,
            "Diseño aplicado: Mi diseño. No se movieron: Cámara, "
            "Chat en el vídeo.")


if __name__ == "__main__":
    unittest.main()

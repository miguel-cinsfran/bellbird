"""Diseños de fábrica y cómo se completan con las fuentes de una escena."""

import unittest

from guyrapu.obs import disenos_escena, disenos_fabrica


def _fuentes():
    return [
        disenos_escena.Fuente("Juego", "otra", 1600, 900),
        disenos_escena.Fuente("Cámara", "camara", 1280, 720),
        disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620),
    ]


def _fabrica(clave):
    return next(fabrica for fabrica in disenos_fabrica.FABRICA
                if fabrica.clave == clave)


def _solo_camara():
    return [disenos_escena.Fuente("Cámara", "camara", 1280, 720)]


def _solo_captura():
    return [disenos_escena.Fuente("Pantalla", "captura", 1600, 900)]


def _captura_y_camara():
    return [disenos_escena.Fuente("Cámara", "camara", 1280, 720),
            disenos_escena.Fuente("Pantalla", "captura", 1600, 900)]


def _completar(clave, fuentes):
    fabrica = _fabrica(clave)
    return disenos_fabrica.completar(fabrica.diseno, fabrica.papeles, fuentes)


class FabricaTest(unittest.TestCase):

    def test_los_tres_disenos_en_orden(self):
        self.assertEqual(
            [(fabrica.clave, fabrica.nombre, fabrica.diseno.clase)
             for fabrica in disenos_fabrica.FABRICA],
            [("pantalla_completa", "Pantalla completa", "pantalla_completa"),
             ("imagen_en_imagen", "Imagen en imagen", "imagen_en_imagen"),
             ("dividida", "Dividida en dos", "dividida")])

    def test_cada_diseno_se_calcula_con_juego_camara_y_chat(self):
        fuentes = _fuentes()
        for fabrica in disenos_fabrica.FABRICA:
            with self.subTest(diseno=fabrica.clave):
                diseno = disenos_fabrica.completar(
                    fabrica.diseno, fabrica.papeles, fuentes)
                disenos_escena.calcular(1600, 900, fuentes, diseno)

    def test_pantalla_completa_prefiere_captura_y_cae_en_camara(self):
        self.assertEqual(
            _completar("pantalla_completa", _captura_y_camara()).principal,
            "Pantalla")
        self.assertEqual(
            _completar("pantalla_completa", _solo_captura()).principal,
            "Pantalla")
        self.assertEqual(
            _completar("pantalla_completa", _solo_camara()).principal,
            "Cámara")

    def test_imagen_en_imagen_pone_captura_grande_y_camara_en_la_esquina(self):
        completa = _completar("imagen_en_imagen", _captura_y_camara())
        self.assertEqual((completa.principal, completa.secundaria),
                         ("Pantalla", "Cámara"))
        completa = _completar("imagen_en_imagen", _solo_captura())
        self.assertEqual((completa.principal, completa.secundaria),
                         ("Pantalla", ""))
        completa = _completar("imagen_en_imagen", _solo_camara())
        self.assertEqual((completa.principal, completa.secundaria),
                         ("Cámara", ""))

    def test_dividida_en_dos_pone_captura_izquierda_y_camara_derecha(self):
        completa = _completar("dividida", _captura_y_camara())
        self.assertEqual((completa.izquierda, completa.derecha),
                         ("Pantalla", "Cámara"))
        self.assertEqual(completa.proporcion, "mitades")
        completa = _completar("dividida", _solo_captura())
        self.assertEqual((completa.izquierda, completa.derecha),
                         ("Pantalla", ""))
        completa = _completar("dividida", _solo_camara())
        self.assertEqual((completa.izquierda, completa.derecha),
                         ("Cámara", ""))

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


class FaltanFuentesTest(unittest.TestCase):

    def test_cuenta_los_lugares_que_pide_cada_clase(self):
        casos = {
            "pantalla_completa": ([0, 1, 2, 3], [1, 0, 0, 0]),
            "imagen_en_imagen": ([0, 1, 2, 3], [2, 1, 0, 0]),
            "dividida": ([0, 1, 2, 3], [2, 1, 0, 0]),
        }
        for clase, (cantidades, esperados) in casos.items():
            for cantidad, esperado in zip(cantidades, esperados):
                with self.subTest(clase=clase, fuentes=cantidad):
                    fuentes = [disenos_escena.Fuente(f"Fuente {indice}", "otra")
                               for indice in range(cantidad)]
                    self.assertEqual(
                        disenos_fabrica.faltan_fuentes(clase, fuentes), esperado)

    def test_el_chat_en_el_video_no_cuenta(self):
        fuentes = [disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620)]
        self.assertEqual(
            disenos_fabrica.faltan_fuentes("pantalla_completa", fuentes), 1)
        fuentes.append(disenos_escena.Fuente("Juego", "otra", 1600, 900))
        self.assertEqual(
            disenos_fabrica.faltan_fuentes("imagen_en_imagen", fuentes), 1)


class MotivoTest(unittest.TestCase):

    def test_sin_fuente_en_un_lugar(self):
        diseno = disenos_escena.Diseno(clase="pantalla_completa")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
            ("principal", "Falta la fuente principal."))

    def test_fuente_que_no_esta_en_la_escena(self):
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Vieja")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
            ("principal", "Falta la fuente principal."))

    def test_fuente_repetida_nombra_el_segundo_lugar(self):
        diseno = disenos_escena.Diseno(
            clase="dividida", izquierda="Juego", derecha="Juego")
        self.assertEqual(
            disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
            ("derecha", "Juego está en dos lugares. Elige otra."))

    def test_los_cuatro_textos_de_fuente_faltante(self):
        casos = [
            (disenos_escena.Diseno(clase="pantalla_completa"),
             "principal", "Falta la fuente principal."),
            (disenos_escena.Diseno(
                clase="imagen_en_imagen", principal="Juego"),
             "secundaria", "Falta la fuente de la esquina."),
            (disenos_escena.Diseno(
                clase="dividida", derecha="Cámara"),
             "izquierda", "Falta la fuente de la izquierda."),
            (disenos_escena.Diseno(
                clase="dividida", izquierda="Juego"),
             "derecha", "Falta la fuente de la derecha."),
        ]
        for diseno, lugar, texto in casos:
            with self.subTest(lugar=lugar):
                self.assertEqual(
                    disenos_fabrica.motivo_para_no_aplicar(diseno, _fuentes()),
                    (lugar, texto))

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

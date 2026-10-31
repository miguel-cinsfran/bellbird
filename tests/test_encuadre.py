"""Pruebas de la lógica pura del encuadre de cámara y del vigía de avisos."""

import math
import unittest

from bellbird.camera.encuadre import (
    ContadorCongelada,
    Encuadre,
    Rostro,
    VigiaEncuadre,
    analizar,
    frase,
    principal,
)

ANCHO = 640
ALTO = 480


def hacer_rostro(x, y, ancho, alto, ojo_izquierda, ojo_derecha, nariz,
                 confianza=0.9):
    return Rostro(x=x, y=y, ancho=ancho, alto=alto,
                  ojo_izquierda=ojo_izquierda, ojo_derecha=ojo_derecha,
                  nariz=nariz, confianza=confianza)


def rostro_centrado(ancho_imagen=ANCHO, alto_imagen=ALTO):
    """Un rostro centrado, con los ojos a 0,33 y tamaño medio."""
    ancho, alto = 160, 160
    x = (ancho_imagen - ancho) // 2
    y = 150
    ojo_y = int(round(0.33 * alto_imagen))
    medio_x = x + ancho // 2
    return hacer_rostro(x, y, ancho, alto, (medio_x - 40, ojo_y),
                        (medio_x + 40, ojo_y), (medio_x, ojo_y + 42))


def rostro_en(cx, ancho_imagen=ANCHO, alto_imagen=ALTO, oy=0.33, tam=0.33,
              y=None):
    """Un rostro neutro con el centro horizontal, la altura de ojos y el
    tamaño pedidos, sin ningún otro problema."""
    ancho = int(round(tam * alto_imagen))
    alto = int(round(tam * alto_imagen))
    x = int(round(cx * ancho_imagen - ancho / 2))
    if y is None:
        y = int(round(oy * alto_imagen - alto * 0.2))
    ojo_y = int(round(oy * alto_imagen))
    medio_x = x + ancho // 2
    mitad = max(ancho // 4, 1)
    return hacer_rostro(x, y, ancho, alto, (medio_x - mitad, ojo_y),
                        (medio_x + mitad, ojo_y),
                        (medio_x, ojo_y + max(alto // 4, 1)))


def mal(*problemas):
    return Encuadre(cantidad=1, problemas=tuple(problemas))


def bien(cantidad=1):
    return Encuadre(cantidad=cantidad, problemas=())


class TestBasicos(unittest.TestCase):

    def test_sin_uno_y_dos_centrados_con_sus_frases(self):
        sin_rostro = analizar([], ANCHO, ALTO)
        self.assertEqual(sin_rostro, Encuadre(cantidad=0,
                                              problemas=("sin_rostro",)))
        self.assertEqual(frase(sin_rostro), "Ningún rostro.")
        uno = analizar([rostro_centrado()], ANCHO, ALTO)
        self.assertEqual(uno, Encuadre(cantidad=1, problemas=()))
        self.assertEqual(frase(uno), "Rostro centrado.")
        chico = rostro_en(0.85, oy=0.35, tam=0.12)
        dos = analizar([rostro_centrado(), chico], ANCHO, ALTO)
        self.assertEqual(dos, Encuadre(cantidad=2, problemas=()))
        self.assertEqual(frase(dos), "2 rostros. Rostro principal centrado.")

    def test_el_principal_es_el_de_mayor_area_aunque_venga_segundo(self):
        chico = rostro_en(0.5, oy=0.35, tam=0.12)
        grande = rostro_en(0.2, oy=0.33, tam=0.33)
        encuadre = analizar([chico, grande], ANCHO, ALTO)
        self.assertEqual(encuadre.cantidad, 2)
        self.assertIn("mover_izquierda", encuadre.problemas)
        solo_grande = analizar([grande], ANCHO, ALTO)
        self.assertEqual(encuadre.problemas, solo_grande.problemas)


class TestHorizontales(unittest.TestCase):

    def test_izquierda_derecha_y_espejo_los_intercambia(self):
        izquierda = analizar([rostro_en(0.25)], ANCHO, ALTO)
        self.assertIn("mover_izquierda", izquierda.problemas)
        self.assertNotIn("mover_derecha", izquierda.problemas)
        self.assertEqual(frase(izquierda), "Muévete a tu izquierda.")
        derecha = analizar([rostro_en(0.75)], ANCHO, ALTO)
        self.assertIn("mover_derecha", derecha.problemas)
        self.assertNotIn("mover_izquierda", derecha.problemas)
        self.assertEqual(frase(derecha), "Muévete a tu derecha.")
        for cx in (0.05, 0.2, 0.3, 0.37, 0.38, 0.5, 0.62, 0.63, 0.8, 0.95):
            with self.subTest(cx=cx):
                normal = analizar([rostro_en(cx)], ANCHO, ALTO).problemas
                espejado = analizar([rostro_en(cx)], ANCHO, ALTO,
                                    espejo=True).problemas
                espero = tuple(
                    "mover_derecha" if codigo == "mover_izquierda"
                    else "mover_izquierda" if codigo == "mover_derecha"
                    else codigo for codigo in normal)
                self.assertEqual(espejado, espero)


class TestCortados(unittest.TestCase):

    def test_cortado_arriba_excluye_alto_y_abajo_excluye_bajo(self):
        arriba = hacer_rostro(240, 0, 160, 160, (280, 48), (360, 48),
                              (320, 90))
        encuadre = analizar([arriba], ANCHO, ALTO)
        self.assertIn("cortado_arriba", encuadre.problemas)
        self.assertNotIn("alto", encuadre.problemas)
        self.assertEqual(frase(encuadre), "Rostro cortado arriba.")
        abajo = hacer_rostro(240, 320, 160, 160, (280, 440), (360, 440),
                             (320, 460))
        encuadre_abajo = analizar([abajo], ANCHO, ALTO)
        self.assertIn("cortado_abajo", encuadre_abajo.problemas)
        self.assertNotIn("bajo", encuadre_abajo.problemas)
        self.assertEqual(frase(encuadre_abajo), "Rostro cortado abajo.")


class TestLejos(unittest.TestCase):

    def test_cerca_y_lejos_del_umbral(self):
        lejos = analizar([rostro_en(0.5, tam=0.10)], ANCHO, ALTO)
        self.assertIn("lejos", lejos.problemas)
        self.assertEqual(frase(lejos), "Rostro lejos: acércate a la cámara.")
        adentro = analizar([rostro_en(0.5, tam=0.20)], ANCHO, ALTO)
        self.assertNotIn("lejos", adentro.problemas)
        self.assertNotIn("cerca", adentro.problemas)


class TestCerca(unittest.TestCase):

    def test_cerca_y_lejos_del_umbral(self):
        cerca = analizar([rostro_en(0.5, tam=0.65, y=100)], ANCHO, ALTO)
        self.assertIn("cerca", cerca.problemas)
        self.assertEqual(frase(cerca),
                         "Rostro muy cerca: aléjate de la cámara.")
        adentro = analizar([rostro_en(0.5, tam=0.55, y=100)], ANCHO, ALTO)
        self.assertNotIn("cerca", adentro.problemas)
        self.assertNotIn("lejos", adentro.problemas)


class TestGirado(unittest.TestCase):

    def test_nariz_un_poco_mas_alla_y_un_poco_mas_aca(self):
        base = rostro_centrado()
        d = abs(base.ojo_izquierda[0] - base.ojo_derecha[0])
        medio = (base.ojo_izquierda[0] + base.ojo_derecha[0]) // 2
        apartado = hacer_rostro(base.x, base.y, base.ancho, base.alto,
                                base.ojo_izquierda, base.ojo_derecha,
                                (medio + int(0.36 * d) + 1, base.nariz[1]))
        self.assertIn("girado", analizar([apartado], ANCHO, ALTO).problemas)
        self.assertEqual(frase(analizar([apartado], ANCHO, ALTO)),
                         "Rostro de lado: mira a la cámara.")
        pegada = hacer_rostro(base.x, base.y, base.ancho, base.alto,
                              base.ojo_izquierda, base.ojo_derecha,
                              (medio + int(0.34 * d), base.nariz[1]))
        self.assertNotIn("girado",
                         analizar([pegada], ANCHO, ALTO).problemas)


class TestInclinado(unittest.TestCase):

    def test_mas_y_menos_de_quince_grados(self):
        base = rostro_centrado()
        ancho_ojos = abs(base.ojo_izquierda[0] - base.ojo_derecha[0])
        alto_si = int(math.ceil(ancho_ojos * math.tan(math.radians(16))))
        inclinado = hacer_rostro(
            base.x, base.y, base.ancho, base.alto, base.ojo_izquierda,
            (base.ojo_derecha[0], base.ojo_izquierda[1] + alto_si),
            base.nariz)
        self.assertIn("inclinado",
                      analizar([inclinado], ANCHO, ALTO).problemas)
        self.assertEqual(frase(analizar([inclinado], ANCHO, ALTO)),
                         "Cabeza inclinada.")
        alto_no = int(ancho_ojos * math.tan(math.radians(14)))
        recto = hacer_rostro(
            base.x, base.y, base.ancho, base.alto, base.ojo_izquierda,
            (base.ojo_derecha[0], base.ojo_izquierda[1] + alto_no),
            base.nariz)
        self.assertNotIn("inclinado",
                         analizar([recto], ANCHO, ALTO).problemas)

    def test_ojos_a_la_misma_altura_en_1280_por_720(self):
        cara = hacer_rostro(440, 200, 400, 300, (500, 300), (900, 300),
                            (700, 380))
        self.assertNotIn("inclinado",
                         analizar([cara], 1280, 720).problemas)


class TestOrdenYFrase(unittest.TestCase):

    def test_problemas_en_orden_y_ejemplo_completo(self):
        cara = hacer_rostro(450, 150, 100, 300, (480, 300), (520, 320),
                            (520, 360))
        encuadre = analizar([cara], ANCHO, ALTO)
        self.assertEqual(encuadre.problemas,
                         ("mover_derecha", "bajo", "cerca", "girado",
                          "inclinado"))
        principal = rostro_en(0.25, oy=0.20, tam=0.33, y=40)
        segundo = rostro_en(0.85, oy=0.35, tam=0.12)
        ejemplo = analizar([principal, segundo], ANCHO, ALTO)
        self.assertEqual(ejemplo.problemas, ("mover_izquierda", "alto"))
        self.assertEqual(
            frase(ejemplo),
            "2 rostros. Muévete a tu izquierda. Rostro alto en la imagen.")


class TestVigiaFuera(unittest.TestCase):

    def test_dos_coma_nueve_no_avisa_y_tres_avisa_una_sola_vez(self):
        vigia = VigiaEncuadre()
        estado = mal("mover_izquierda")
        self.assertIsNone(vigia.observar(estado, 0.0))
        self.assertIsNone(vigia.observar(estado, 2.9))
        aviso = vigia.observar(estado, 3.0)
        self.assertIsNotNone(aviso)
        self.assertEqual(aviso.tipo, "fuera")
        self.assertEqual(aviso.frase, frase(estado))
        self.assertIsNone(vigia.observar(estado, 5.0))


class TestVigiaDentro(unittest.TestCase):

    def test_vuelve_a_bien_y_avisa_dentro_al_segundo_y_medio(self):
        vigia = VigiaEncuadre()
        estado = mal("mover_izquierda")
        vigia.observar(estado, 0.0)
        aviso = vigia.observar(estado, 3.0)
        self.assertIsNotNone(aviso)
        self.assertIsNone(vigia.observar(bien(), 6.0))
        self.assertIsNone(vigia.observar(bien(), 7.4))
        dentro = vigia.observar(bien(), 7.5)
        self.assertIsNotNone(dentro)
        self.assertEqual(dentro.tipo, "dentro")
        self.assertEqual(dentro.frase, "Rostro centrado.")
        self.assertIsNone(vigia.observar(bien(), 9.0))


class TestVigiaParpadeo(unittest.TestCase):

    def test_alternando_cada_segundo_no_avisa_en_sesenta(self):
        vigia = VigiaEncuadre()
        estado = mal("mover_izquierda")
        for segundo in range(61):
            observado = estado if segundo % 2 == 0 else bien()
            self.assertIsNone(vigia.observar(observado, float(segundo)),
                              f"avisó en el segundo {segundo}")


class TestVigiaCambio(unittest.TestCase):

    def test_problema_nuevo_respeta_tres_segundos_y_diez_desde_el_aviso(self):
        vigia = VigiaEncuadre()
        primero = mal("mover_izquierda")
        vigia.observar(primero, 0.0)
        self.assertIsNotNone(vigia.observar(primero, 3.0))
        segundo = mal("mover_derecha")
        self.assertIsNone(vigia.observar(segundo, 4.0))
        self.assertIsNone(vigia.observar(segundo, 6.9))
        self.assertIsNone(vigia.observar(segundo, 7.0))
        self.assertIsNone(vigia.observar(segundo, 12.9))
        aviso = vigia.observar(segundo, 13.0)
        self.assertIsNotNone(aviso)
        self.assertEqual(aviso.tipo, "fuera")
        self.assertEqual(aviso.frase, frase(segundo))
        self.assertIsNone(vigia.observar(segundo, 14.0))


class TestVigiaReiniciar(unittest.TestCase):

    def test_recien_creado_da_por_bien_y_reiniciar_vuelve_ahi(self):
        vigia = VigiaEncuadre()
        self.assertIsNone(vigia.observar(bien(), 0.0))
        self.assertIsNone(vigia.observar(bien(), 1.5))
        estado = mal("mover_izquierda")
        vigia.observar(estado, 5.0)
        self.assertIsNotNone(vigia.observar(estado, 8.0))
        vigia.reiniciar()
        self.assertIsNone(vigia.observar(bien(), 9.0))
        self.assertIsNone(vigia.observar(bien(), 10.5))
        self.assertIsNone(vigia.observar(estado, 11.0))


class TestPrincipal(unittest.TestCase):

    def test_el_de_mayor_area_y_a_igual_area_el_primero(self):
        chico = rostro_en(0.5, oy=0.35, tam=0.12)
        grande = rostro_en(0.2, oy=0.33, tam=0.33)
        self.assertIs(principal([chico, grande]), grande)
        gemelo = rostro_en(0.5, oy=0.35, tam=0.12)
        self.assertIs(principal([chico, gemelo]), chico)


class TestLuz(unittest.TestCase):

    def test_contraluz_con_fondo_mucho_mas_claro(self):
        encuadre = analizar([rostro_centrado()], ANCHO, ALTO, luz_rostro=100.0,
                            luz_fondo=180.0)
        self.assertIn("contraluz", encuadre.problemas)
        self.assertEqual(frase(encuadre), "Contraluz: la luz está detrás de ti.")

    def test_oscuro_con_poca_luz_delante(self):
        encuadre = analizar([rostro_centrado()], ANCHO, ALTO, luz_rostro=30.0,
                            luz_fondo=40.0)
        self.assertIn("oscuro", encuadre.problemas)
        self.assertEqual(frase(encuadre), "Rostro oscuro: falta luz delante.")

    def test_contraluz_excluye_oscuro(self):
        encuadre = analizar([rostro_centrado()], ANCHO, ALTO, luz_rostro=30.0,
                            luz_fondo=150.0)
        self.assertIn("contraluz", encuadre.problemas)
        self.assertNotIn("oscuro", encuadre.problemas)

    def test_en_el_umbral_justo_no_avisa(self):
        al_limite = analizar([rostro_centrado()], ANCHO, ALTO, luz_rostro=50.0,
                             luz_fondo=120.0)
        self.assertNotIn("contraluz", al_limite.problemas)
        self.assertNotIn("oscuro", al_limite.problemas)

    def test_sin_luz_no_mira_ni_contraluz_ni_oscuro(self):
        encuadre = analizar([rostro_centrado()], ANCHO, ALTO, luz_fondo=200.0)
        self.assertNotIn("contraluz", encuadre.problemas)
        self.assertNotIn("oscuro", encuadre.problemas)


class TestCongelada(unittest.TestCase):

    def test_congelada_es_el_unico_problema(self):
        cara = rostro_en(0.25, oy=0.20, tam=0.33, y=40)
        encuadre = analizar([cara], ANCHO, ALTO, congelada=True)
        self.assertEqual(encuadre.problemas, ("congelada",))
        self.assertEqual(frase(encuadre), "Imagen congelada.")

    def test_congelada_no_cuenta_rostros(self):
        rostros = [rostro_centrado(), rostro_en(0.85, oy=0.35, tam=0.12)]
        encuadre = analizar(rostros, ANCHO, ALTO, congelada=True)
        self.assertEqual(encuadre.cantidad, 2)
        self.assertEqual(frase(encuadre), "Imagen congelada.")


class TestContadorCongelada(unittest.TestCase):

    def test_cuatro_nueve_no_avisa_y_cinco_si(self):
        contador = ContadorCongelada()
        self.assertFalse(contador.observar("huella", 0.0))
        self.assertFalse(contador.observar("huella", 4.9))
        self.assertTrue(contador.observar("huella", 5.0))

    def test_huella_distinta_reinicia_la_cuenta(self):
        contador = ContadorCongelada()
        self.assertFalse(contador.observar("primera", 0.0))
        self.assertTrue(contador.observar("primera", 5.0))
        self.assertFalse(contador.observar("segunda", 6.0))
        self.assertFalse(contador.observar("segunda", 10.9))
        self.assertTrue(contador.observar("segunda", 11.0))


if __name__ == "__main__":
    unittest.main()

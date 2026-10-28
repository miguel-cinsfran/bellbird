"""Pruebas de las listas de música propias (listas.py), sin wx ni VLC."""

import random
import tempfile
import unittest
from pathlib import Path

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.music import listas
from ytchat.music.listas import ErrorListas
from ytchat.music.modelo import Tema


class TestNombres(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name) / "listas"

    def tearDown(self):
        self.tmp.cleanup()

    def test_carpeta_inexistente_es_lista_vacia(self):
        self.assertEqual(listas.nombres(self.carpeta), [])

    def test_ordena_sin_mayusculas_ni_tildes(self):
        self.carpeta.mkdir()
        for nombre in ("Zeta.m3u8", "álbum.m3u8", "Beta.m3u8"):
            (self.carpeta / nombre).write_text("#EXTM3U\n", encoding="utf-8")
        self.assertEqual(listas.nombres(self.carpeta),
                         ["álbum", "Beta", "Zeta"])

    def test_ignora_archivos_que_no_son_listas(self):
        self.carpeta.mkdir()
        (self.carpeta / "Una.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
        (self.carpeta / "notas.txt").write_text("no", encoding="utf-8")
        (self.carpeta / "sub").mkdir()
        self.assertEqual(listas.nombres(self.carpeta), ["Una"])


class TestValidarNombre(unittest.TestCase):

    def test_recorta_espacios(self):
        self.assertEqual(listas.validar_nombre("  Mi lista  "), "Mi lista")

    def test_vacio_lanza(self):
        for valor in ("", "   ", None):
            with self.subTest(valor=valor):
                with self.assertRaises(ErrorListas) as exc:
                    listas.validar_nombre(valor)
                self.assertEqual(str(exc.exception),
                                 "Escribe un nombre para la lista")

    def test_caracteres_prohibidos_lanzan(self):
        for caracter in '\\/:*?"<>|':
            with self.subTest(caracter=caracter):
                with self.assertRaises(ErrorListas) as exc:
                    listas.validar_nombre(f"a{caracter}b")
                self.assertIn("no puede tener", str(exc.exception))


class TestCrearRenombrarBorrar(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name) / "listas"

    def tearDown(self):
        self.tmp.cleanup()

    def test_crear_arma_la_carpeta_y_la_lista_vacia(self):
        limpio = listas.crear(self.carpeta, "  Favoritas ")
        self.assertEqual(limpio, "Favoritas")
        self.assertTrue(self.carpeta.is_dir())
        self.assertEqual((self.carpeta / "Favoritas.m3u8").read_text(
            encoding="utf-8"), "#EXTM3U\n")
        self.assertEqual(listas.nombres(self.carpeta), ["Favoritas"])

    def test_crear_duplicado_sin_distinguir_mayusculas(self):
        listas.crear(self.carpeta, "Favoritas")
        with self.assertRaises(ErrorListas) as exc:
            listas.crear(self.carpeta, "favoritas")
        self.assertEqual(str(exc.exception), "Ya hay una lista con ese nombre")

    def test_renombrar_cambia_el_archivo(self):
        sonoro = self.carpeta.parent / "a.mp3"
        sonoro.write_bytes(b"x")
        listas.crear(self.carpeta, "Vieja")
        listas.guardar(self.carpeta, "Vieja",
                       (Tema(str(sonoro.resolve()), "A"),))
        limpio = listas.renombrar(self.carpeta, "Vieja", "Nueva")
        self.assertEqual(limpio, "Nueva")
        self.assertEqual(listas.nombres(self.carpeta), ["Nueva"])
        temas, _ = listas.cargar(self.carpeta, "Nueva")
        self.assertEqual(len(temas), 1)

    def test_renombrar_a_uno_existente_lanza(self):
        listas.crear(self.carpeta, "Una")
        listas.crear(self.carpeta, "Otra")
        with self.assertRaises(ErrorListas) as exc:
            listas.renombrar(self.carpeta, "Una", "otra")
        self.assertEqual(str(exc.exception), "Ya hay una lista con ese nombre")

    def test_renombrar_al_mismo_nombre_con_otra_caja_conserva(self):
        listas.crear(self.carpeta, "Favoritas")
        self.assertEqual(listas.renombrar(self.carpeta, "favoritas", "Favoritas"),
                         "Favoritas")
        self.assertEqual(listas.nombres(self.carpeta), ["Favoritas"])

    def test_renombrar_y_borrar_inexistente_lanzan(self):
        with self.assertRaises(ErrorListas):
            listas.renombrar(self.carpeta, "No está", "Otra")
        with self.assertRaises(ErrorListas):
            listas.borrar(self.carpeta, "No está")

    def test_borrar_quita_el_archivo(self):
        listas.crear(self.carpeta, "Borrame")
        listas.borrar(self.carpeta, "borrame")
        self.assertEqual(listas.nombres(self.carpeta), [])


class TestGuardarCargar(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "listas"
        self.a = self._mp3("cancion")
        self.b = self._mp3("otra")

    def tearDown(self):
        self.tmp.cleanup()

    def _mp3(self, nombre):
        ruta = self.raiz / f"{nombre}.mp3"
        ruta.write_bytes(b"x")
        return str(ruta.resolve())

    def test_ida_y_vuelta_con_tildes(self):
        temas = (Tema(self.a, "Canción ñandú"), Tema(self.b, "Otra"))
        listas.guardar(self.carpeta, "Mi lista", temas)
        cargados, faltantes = listas.cargar(self.carpeta, "Mi lista")
        self.assertEqual(faltantes, ())
        self.assertEqual([(t.origen, t.titulo) for t in cargados],
                         [(self.a, "Canción ñandú"), (self.b, "Otra")])

    def test_guardar_devuelve_el_nombre_limpio(self):
        self.assertEqual(
            listas.guardar(self.carpeta, "  Mi lista ", ()), "Mi lista")

    def test_cargar_inexistente_lanza(self):
        with self.assertRaises(ErrorListas):
            listas.cargar(self.carpeta, "No está")

    def test_cargar_devuelve_los_nombres_de_lo_que_falta(self):
        listas.crear(self.carpeta, "Mezcla")
        destino = self.carpeta / "Mezcla.m3u8"
        destino.write_text(
            "#EXTM3U\n"
            "#EXTINF:-1,Válida\n"
            f"{self.a}\n"
            "no-existe.mp3\n"
            "https://ejemplo.test/v.mp3\n",
            encoding="utf-8")
        temas, faltantes = listas.cargar(self.carpeta, "Mezcla")
        self.assertEqual(faltantes, ("no-existe", "v"))
        self.assertEqual([t.titulo for t in temas], ["Válida"])

    def test_agregar_suma_al_final(self):
        listas.guardar(self.carpeta, "Cola", (Tema(self.a, "A"),))
        listas.agregar(self.carpeta, "Cola", (Tema(self.b, "B"),))
        temas, _ = listas.cargar(self.carpeta, "Cola")
        self.assertEqual([t.titulo for t in temas], ["A", "B"])

    def test_ida_y_vuelta_de_la_duracion(self):
        temas = (Tema(self.a, "A", duracion_ms=222000),
                 Tema(self.b, "B", duracion_ms=7000))
        listas.guardar(self.carpeta, "Duraciones", temas)
        cargados, faltantes = listas.cargar(self.carpeta, "Duraciones")
        self.assertEqual(faltantes, ())
        self.assertEqual([t.duracion_ms for t in cargados], [222000, 7000])

    def test_sin_duracion_escribe_menos_uno_y_se_lee_sin_duracion(self):
        listas.guardar(self.carpeta, "Sin duración",
                       (Tema(self.a, "A"), Tema(self.b, "B")))
        texto = (self.carpeta / "Sin duración.m3u8").read_text(encoding="utf-8")
        self.assertIn("#EXTINF:-1,A", texto)
        cargados, _ = listas.cargar(self.carpeta, "Sin duración")
        self.assertEqual([t.duracion_ms for t in cargados], [0, 0])

    def test_lista_vieja_con_menos_uno_se_lee_sin_duracion(self):
        self.carpeta.mkdir()
        (self.carpeta / "Vieja.m3u8").write_text(
            f"#EXTM3U\n#EXTINF:-1,Vieja\n{self.a}\n", encoding="utf-8")
        cargados, faltantes = listas.cargar(self.carpeta, "Vieja")
        self.assertEqual(faltantes, ())
        self.assertEqual(cargados[0].titulo, "Vieja")
        self.assertEqual(cargados[0].duracion_ms, 0)


class TestQuitarMover(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "listas"

    def tearDown(self):
        self.tmp.cleanup()

    def _temas(self, *titulos):
        temas = []
        for i, titulo in enumerate(titulos):
            ruta = self.raiz / f"t{i}.mp3"
            ruta.write_bytes(b"x")
            temas.append(Tema(str(ruta.resolve()), titulo))
        return tuple(temas)

    def test_quitar_la_del_medio(self):
        listas.guardar(self.carpeta, "L", self._temas("A", "B", "C"))
        listas.quitar(self.carpeta, "L", 1)
        temas, _ = listas.cargar(self.carpeta, "L")
        self.assertEqual([t.titulo for t in temas], ["A", "C"])

    def test_quitar_fuera_de_rango_lanza(self):
        listas.guardar(self.carpeta, "L", self._temas("A", "B"))
        for indice in (-1, 2, 5):
            with self.subTest(indice=indice):
                with self.assertRaises(ErrorListas):
                    listas.quitar(self.carpeta, "L", indice)

    def test_mover_una_posicion_y_devuelve_la_nueva(self):
        listas.guardar(self.carpeta, "L", self._temas("A", "B", "C"))
        self.assertEqual(listas.mover(self.carpeta, "L", 0, 1), 1)
        temas, _ = listas.cargar(self.carpeta, "L")
        self.assertEqual([t.titulo for t in temas], ["B", "A", "C"])

    def test_mover_no_pasa_de_los_bordes(self):
        listas.guardar(self.carpeta, "L", self._temas("A", "B", "C"))
        self.assertEqual(listas.mover(self.carpeta, "L", 0, -5), 0)
        self.assertEqual(listas.mover(self.carpeta, "L", 2, 5), 2)
        temas, _ = listas.cargar(self.carpeta, "L")
        self.assertEqual([t.titulo for t in temas], ["A", "B", "C"])

    def test_mover_fuera_de_rango_lanza(self):
        listas.guardar(self.carpeta, "L", self._temas("A"))
        with self.assertRaises(ErrorListas):
            listas.mover(self.carpeta, "L", 1, 1)

    def test_propiedad_cien_operaciones_al_azar(self):
        base = self._temas("T0", "T1", "T2", "T3", "T4", "T5")
        modelo = []
        rng = random.Random(20261018)
        listas.crear(self.carpeta, "Propia")
        for _ in range(100):
            accion = rng.choice(("agregar", "quitar", "mover"))
            if accion == "agregar":
                tema = rng.choice(base)
                listas.agregar(self.carpeta, "Propia", (tema,))
                modelo.append(tema)
            elif accion == "quitar" and modelo:
                indice = rng.randrange(len(modelo))
                listas.quitar(self.carpeta, "Propia", indice)
                modelo.pop(indice)
            elif accion == "mover" and modelo:
                indice = rng.randrange(len(modelo))
                paso = rng.choice((-1, 1))
                nuevo = listas.mover(self.carpeta, "Propia", indice, paso)
                destino = max(0, min(len(modelo) - 1, indice + paso))
                self.assertEqual(nuevo, destino)
                modelo.insert(destino, modelo.pop(indice))
        cargados, faltantes = listas.cargar(self.carpeta, "Propia")
        self.assertEqual(faltantes, ())
        self.assertEqual([(t.origen, t.titulo) for t in cargados],
                         [(t.origen, t.titulo) for t in modelo])


class TestCantidad(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "listas"

    def tearDown(self):
        self.tmp.cleanup()

    def _temas(self, cantidad):
        temas = []
        for i in range(cantidad):
            ruta = self.raiz / f"c{i}.mp3"
            ruta.write_bytes(b"x")
            temas.append(Tema(str(ruta.resolve()), f"Canción {i}"))
        return tuple(temas)

    def test_lista_con_tres_da_tres(self):
        listas.guardar(self.carpeta, "Tres", self._temas(3))
        self.assertEqual(listas.cantidad(self.carpeta, "Tres"), 3)

    def test_lista_vacia_da_cero(self):
        listas.crear(self.carpeta, "Vacía")
        self.assertEqual(listas.cantidad(self.carpeta, "Vacía"), 0)

    def test_inexistente_da_none(self):
        self.assertIsNone(listas.cantidad(self.carpeta, "No está"))


class TestPseudoListas(unittest.TestCase):
    """Pseudotraducción de los errores de las listas propias.

    Sin ventanas: provoca cada error bajo `con_pseudo()` y exige el
    mensaje marcado, con los datos presentes.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name) / "listas"
        self.carpeta.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_errores_salen_marcados_con_los_datos(self):
        with con_pseudo():
            with self.assertRaises(ErrorListas) as vacio:
                listas.validar_nombre("   ")
            with self.assertRaises(ErrorListas) as invalido:
                listas.validar_nombre("a/b")
            listas.crear(self.carpeta, "Rock")
            with self.assertRaises(ErrorListas) as duplicado:
                listas.crear(self.carpeta, "rock")
            with self.assertRaises(ErrorListas) as no_existe:
                listas.borrar(self.carpeta, "Pop")
            with self.assertRaises(ErrorListas) as posicion:
                listas.quitar(self.carpeta, "Rock", 3)
        for mensaje in (str(vacio.exception), str(invalido.exception),
                        str(duplicado.exception), str(no_existe.exception),
                        str(posicion.exception)):
            with self.subTest(mensaje=mensaje):
                self.assertTrue(mensaje.startswith("[¡"), mensaje)
        self.assertIn(listas.CARACTERES_PROHIBIDOS, str(invalido.exception))
        self.assertIn("Pop", str(no_existe.exception))
        self.assertIn("4", str(posicion.exception))


if __name__ == "__main__":
    unittest.main()

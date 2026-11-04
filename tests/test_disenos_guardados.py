"""Diseños de escena propios guardados en disco, sin interfaz ni OBS."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.core import archivos
from bellbird.obs import disenos_escena
from bellbird.obs import disenos_guardados


def _diseno(**cambios):
    valores = {"clase": "pantalla_completa", "principal": "Juego"}
    valores.update(cambios)
    return disenos_escena.Diseno(**valores)


class DisenosGuardadosTest(unittest.TestCase):

    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporal.cleanup)
        self.ruta = Path(self._temporal.name) / "disenos_escena.json"

    def test_guarda_y_carga_dos_en_orden(self):
        primero = _diseno(principal="Juego", modos={"Juego": "llenar"})
        segundo = _diseno(clase="dividida", izquierda="Cámara",
                          derecha="Chat", proporcion="dos_tercios")
        disenos_guardados.guardar_diseno("Primero", primero, self.ruta)
        lista = disenos_guardados.guardar_diseno("Segundo", segundo, self.ruta)
        self.assertEqual([nombre for nombre, _ in lista],
                         ["Primero", "Segundo"])
        self.assertEqual(disenos_guardados.cargar(self.ruta),
                         [("Primero", primero), ("Segundo", segundo)])
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(set(datos[0]), {
            "nombre", "clase", "principal", "secundaria", "izquierda",
            "derecha", "esquina", "tamano", "proporcion", "chat",
            "esquina_chat", "modos"})

    def test_conserva_tilde_y_emoji_en_el_nombre(self):
        diseno = _diseno()
        disenos_guardados.guardar_diseno("  Diseño 🎬  ", diseno, self.ruta)
        self.assertEqual(disenos_guardados.cargar(self.ruta),
                         [("Diseño 🎬", diseno)])
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertIn("Diseño 🎬", texto)
        self.assertNotIn("\\u", texto)

    def test_reemplaza_sin_distinguir_mayusculas_en_su_lugar(self):
        antes = _diseno(principal="Antes")
        viejo = _diseno(principal="Juego")
        despues = _diseno(principal="Después")
        nuevo = _diseno(principal="Juego nuevo")
        for nombre, diseno in (("Antes", antes), ("Juego", viejo),
                               ("Después", despues)):
            disenos_guardados.guardar_diseno(nombre, diseno, self.ruta)
        lista = disenos_guardados.guardar_diseno("juego", nuevo, self.ruta)
        self.assertEqual([nombre for nombre, _ in lista],
                         ["Antes", "juego", "Después"])
        self.assertEqual(disenos_guardados.cargar(self.ruta),
                         [("Antes", antes), ("juego", nuevo),
                          ("Después", despues)])

    def test_elimina_por_nombre(self):
        uno = _diseno(principal="Uno")
        dos = _diseno(principal="Dos")
        disenos_guardados.guardar_diseno("Uno", uno, self.ruta)
        disenos_guardados.guardar_diseno("Dos", dos, self.ruta)
        lista = disenos_guardados.eliminar_diseno("Uno", self.ruta)
        self.assertEqual(lista, [("Dos", dos)])
        self.assertEqual(disenos_guardados.cargar(self.ruta), [("Dos", dos)])

    def test_archivo_que_falta_devuelve_lista_vacia(self):
        self.assertEqual(disenos_guardados.cargar(self.ruta), [])

    def test_archivo_que_no_es_json_devuelve_lista_vacia(self):
        self.ruta.write_text("{esto no es json", encoding="utf-8")
        self.assertEqual(disenos_guardados.cargar(self.ruta), [])

    def test_archivo_que_no_es_una_lista_devuelve_lista_vacia(self):
        self.ruta.write_text('{"nombre": "Uno"}', encoding="utf-8")
        self.assertEqual(disenos_guardados.cargar(self.ruta), [])

    def test_descarta_la_entrada_invalida_y_conserva_las_demas(self):
        self.ruta.write_text(json.dumps([
            {"nombre": "Bueno", "clase": "pantalla_completa"},
            {"nombre": "Malo", "clase": "otra"},
            {"clase": "pantalla_completa"},
        ], ensure_ascii=False), encoding="utf-8")
        with self.assertLogs(disenos_guardados.logger,
                             level="WARNING") as registros:
            cargados = disenos_guardados.cargar(self.ruta)
        self.assertEqual(
            cargados,
            [("Bueno", disenos_escena.Diseno(clase="pantalla_completa"))])
        self.assertTrue(any("Malo" in linea for linea in registros.output))

    def test_guardar_pasa_por_la_escritura_atomica(self):
        uno = _diseno(principal="Uno")
        disenos_guardados.guardar_diseno("Uno", uno, self.ruta)
        antes = self.ruta.read_text(encoding="utf-8")
        with mock.patch.object(archivos.os, "replace",
                               side_effect=OSError("falla de prueba")):
            with self.assertRaises(OSError):
                disenos_guardados.guardar_diseno(
                    "Dos", _diseno(principal="Dos"), self.ruta)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)
        self.assertFalse(self.ruta.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()

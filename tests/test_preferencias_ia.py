"""Pseudotraducción de la página Inteligencia artificial de Preferencias.

Abre ventanas.
Construye el diálogo de Preferencias con la pseudotraducción y exige que
la página no deje ningún texto visible sin envolver.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.ai import catalogo
from bellbird.ui import gui, gui_preferencias
from bellbird.ui import preferencias_ia
from bellbird.ui import preferencias_ia_clave
from bellbird.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


class TestPseudoIA(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = redirigir_rutas(Path(self.tmp.name))
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)
        # Nunca el Administrador de credenciales real.
        sin_clave = mock.patch.object(
            preferencias_ia_clave.claves, "leer", return_value="")
        sin_clave.start()
        self.addCleanup(sin_clave.stop)
        # Catálogo vacío: la lista muestra el aviso de lista vacía.
        catalogo_vacio = mock.patch.object(
            preferencias_ia.catalogo, "cargar",
            return_value={"version": catalogo.VERSION, "fecha": None,
                          "proveedores": {}})
        catalogo_vacio.start()
        self.addCleanup(catalogo_vacio.stop)

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            pagina = next(p for p in dialogo._paginas()
                          if p.GetName() == "PagIA")
            sin_marcar = textos_sin_marcar(pagina)

        self.assertEqual([], sin_marcar)

    def test_nombres_de_proveedores_marcados(self):
        with con_pseudo():
            dialogo = self._dialogo()
            nombres = dialogo.pagina_ia.cho_ia_proveedor.GetStrings()

        self.assertEqual(len(nombres), 7)
        for nombre in nombres:
            self.assertTrue(nombre.startswith("[¡"), nombre)

    def test_restaurar_marca_la_instruccion(self):
        with con_pseudo():
            dialogo = self._dialogo()
            dialogo.pagina_ia._on_ia_restaurar(mock.Mock())
            valor = dialogo.pagina_ia.txt_ia_pregunta.GetValue()
        self.assertTrue(valor.startswith("[¡"), valor)


class TestDisenoIA(unittest.TestCase):
    """Guardar y Probar comparten fila; Actualizar va junto al Modelo.

    Abren ventanas.
    """

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = redirigir_rutas(Path(self.tmp.name))
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)
        sin_clave = mock.patch.object(
            preferencias_ia_clave.claves, "leer", return_value="")
        sin_clave.start()
        self.addCleanup(sin_clave.stop)
        catalogo_vacio = mock.patch.object(
            preferencias_ia.catalogo, "cargar",
            return_value={"version": catalogo.VERSION, "fecha": None,
                          "proveedores": {}})
        catalogo_vacio.start()
        self.addCleanup(catalogo_vacio.stop)

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_guardar_y_probar_comparten_una_fila_partible(self):
        dialogo = self._dialogo()
        guardar = dialogo.pagina_ia.ia_clave.btn_guardar
        probar = dialogo.pagina_ia.btn_ia_probar_clave
        fila = guardar.GetContainingSizer()
        self.assertIsNotNone(fila)
        self.assertIs(probar.GetContainingSizer(), fila)
        self.assertIsInstance(fila, gui.wx.WrapSizer)
        self.assertEqual([elemento.GetWindow()
                          for elemento in fila.GetChildren()],
                         [guardar, probar])

    def test_actualizar_comparte_la_fila_con_el_modelo(self):
        dialogo = self._dialogo()
        modelo = dialogo.pagina_ia.cho_ia_modelo
        actualizar = dialogo.pagina_ia.btn_ia_actualizar
        fila = modelo.GetContainingSizer()
        self.assertIsNotNone(fila)
        self.assertIs(actualizar.GetContainingSizer(), fila)
        ventanas = [elemento.GetWindow()
                     for elemento in fila.GetChildren()]
        self.assertLess(ventanas.index(modelo),
                        ventanas.index(actualizar))


if __name__ == "__main__":
    unittest.main()

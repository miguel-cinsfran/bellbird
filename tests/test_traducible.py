"""Pruebas de que el código se puede traducir con gettext.

`_` queda reservado para la función de traducción. Un módulo que además lo
liga como descartable vuelve local a `_` en toda la función y la llamada
revienta.
"""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from guyrapu.core import idioma


class TestEtiquetasDeTablas(unittest.TestCase):
    """Las etiquetas de las tablas de datos salen traducidas al mostrarse."""

    def setUp(self):
        idioma.instalar(idioma.IDIOMA_PSEUDO)

    def tearDown(self):
        idioma._reiniciar()

    def test_etiquetas_de_los_filtros_salen_marcadas(self):
        from guyrapu.ui import gui_menu

        visibles = [idioma._(nombre) for nombre, _valor in gui_menu.FILTROS]
        self.assertTrue(all(texto.startswith("[¡") for texto in visibles),
                        visibles)

    def test_anuncio_del_filtro_sale_marcado(self):
        from guyrapu.ui import gui

        falso = SimpleNamespace(
            chat_vivo=SimpleNamespace(filtro=None, reconstruir=lambda: None),
            lb_chat=mock.Mock(**{"GetCount.return_value": 3}))
        with mock.patch.object(gui, "guardar_opcion"), \
                mock.patch.object(gui, "anunciar") as anunciar:
            gui.VentanaPrincipal._aplicar_filtro(falso, 0)
        texto = anunciar.call_args.args[0]
        self.assertTrue(texto.startswith("[¡"), texto)
        self.assertIn("[¡Todos!]", texto)

    def test_criterios_de_orden_salen_marcados(self):
        from guyrapu.music import filtros

        visibles = [idioma._(etiqueta)
                    for _clave, etiqueta in filtros.CRITERIOS]
        self.assertTrue(all(texto.startswith("[¡") for texto in visibles),
                        visibles)

    def test_titulos_de_grupos_de_atajos_salen_marcados(self):
        from guyrapu.core import atajos

        visibles = [idioma._(titulo)
                    for titulo, _acciones in atajos.ATAJOS_GRUPOS]
        self.assertTrue(all(texto.startswith("[¡") for texto in visibles),
                        visibles)

    def test_tema_suave_sale_marcado(self):
        from guyrapu.ui import preferencias_sonidos

        self.assertTrue(
            preferencias_sonidos._nombre_visible_tema("suave").startswith("[¡"))


class TestNombreReservado(unittest.TestCase):

    def test_ningun_modulo_liga_el_nombre_de_traduccion(self):
        raiz = Path(__file__).resolve().parent.parent
        archivos = [raiz / "main.py"]
        archivos.extend(sorted((raiz / "guyrapu").rglob("*.py")))
        violaciones = []
        for ruta in archivos:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"),
                              filename=str(ruta))
            relativa = ruta.relative_to(raiz).as_posix()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Name) and nodo.id == "_" \
                        and isinstance(nodo.ctx, ast.Store):
                    violaciones.append(f"{relativa}:{nodo.lineno}: liga _")
                elif isinstance(nodo, ast.arg) and nodo.arg == "_":
                    violaciones.append(f"{relativa}:{nodo.lineno}: parámetro _")
                elif isinstance(nodo, ast.ExceptHandler) and nodo.name == "_":
                    violaciones.append(f"{relativa}:{nodo.lineno}: except as _")
                elif isinstance(nodo, ast.alias) and nodo.asname == "_":
                    violaciones.append(f"{relativa}:{nodo.lineno}: import as _")
        self.assertEqual([], violaciones,
                         "el nombre _ queda reservado para traducir:\n"
                         + "\n".join(violaciones))


if __name__ == "__main__":
    unittest.main()

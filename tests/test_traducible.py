"""Pruebas de que el código se puede traducir con gettext.

`_` queda reservado para la función de traducción. Un módulo que además lo
liga como descartable vuelve local a `_` en toda la función y la llamada
revienta.
"""

import ast
import unittest
from pathlib import Path


class TestNombreReservado(unittest.TestCase):

    def test_ningun_modulo_liga_el_nombre_de_traduccion(self):
        raiz = Path(__file__).resolve().parent.parent
        archivos = [raiz / "main.py"]
        archivos.extend(sorted((raiz / "ytchat").rglob("*.py")))
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

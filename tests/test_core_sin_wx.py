"""El núcleo de bellbird no puede depender de wxPython."""

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "bellbird" / "core"

# La autocomprobación del paquete comprueba que wx está empaquetado, así que
# necesita importarlo. Es la única excepción del núcleo.
EXCEPCIONES = (
    ("autocomprobacion.py",
     "La autocomprobación del paquete comprueba que wx está empaquetado."),
)


def _importa_wx(nodo):
    if isinstance(nodo, ast.Import):
        return any(alias.name == "wx" or alias.name.startswith("wx.")
                   for alias in nodo.names)
    if isinstance(nodo, ast.ImportFrom):
        modulo = nodo.module or ""
        return modulo == "wx" or modulo.startswith("wx.")
    return False


class TestCoreSinWx(unittest.TestCase):

    def test_ningun_modulo_del_nucleo_importa_wx(self):
        exceptuados = {nombre for nombre, _motivo in EXCEPCIONES}
        fallos = []
        for ruta in sorted(RAIZ.rglob("*.py")):
            if ruta.name in exceptuados:
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"),
                              filename=str(ruta))
            for nodo in ast.walk(arbol):
                if _importa_wx(nodo):
                    fallos.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}")
        self.assertEqual(fallos, [])


if __name__ == "__main__":
    unittest.main()

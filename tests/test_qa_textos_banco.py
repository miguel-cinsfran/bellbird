"""Los textos que el banco de QA espera tienen que existir en la aplicación.

Lee `qa/conducir.py` con el árbol sintáctico, sin importarlo, y busca cada
texto en los módulos de `bellbird/`. Los que no son textos de la aplicación
llevan su motivo en la lista de excepciones.
"""

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "qa" / "conducir.py"

# Funciones del banco que reciben un texto que después se compara con la
# aplicación. `boton_de` busca un control por su nombre accesible.
FUNCIONES = frozenset({
    "esperar_ventana", "esperar_dicho", "dialogo_nativo", "auditar_dialogo",
    "subarbol", "boton_de",
})

# Textos que la prueba no tiene que encontrar en `bellbird/`, cada uno con su
# motivo en una frase.
EXCEPCIONES = {
    "Atajo_conectar": "La aplicación arma el nombre como f\"Atajo_{accion}\".",
    "06 corto QA": "Es un archivo de prueba de la música, no un texto de la aplicación.",
    "should be created as child": "Es una marca de diagnóstico de wxWidgets.",
    "failed with error": "Es una marca de diagnóstico de wxWidgets.",
    "Assert": "Es una marca de diagnóstico de wxWidgets.",
    "wxWidgets": "Es una marca de diagnóstico de wxWidgets.",
    "Warning:": "Es una marca de diagnóstico de wxWidgets.",
    "Error:": "Es una marca de diagnóstico de wxWidgets.",
}


def _literales(nodo) -> list[str]:
    """Los textos constantes de un argumento, también dentro de una tupla."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return [nodo.value]
    if isinstance(nodo, (ast.Tuple, ast.List, ast.Set)):
        salida = []
        for elemento in nodo.elts:
            salida.extend(_literales(elemento))
        return salida
    return []


def _menciona_nombre_o_texto(nodo) -> bool:
    """Si la expresión habla de un nombre, texto o etiqueta de la interfaz."""
    try:
        fuente = ast.unparse(nodo).lower()
    except Exception:
        return False
    return any(clave in fuente for clave in ("nombre", "texto", "etiqueta"))


def textos_esperados(codigo: str) -> list[tuple[int, str]]:
    """Los pares (línea del banco, texto) que el banco espera de la app."""
    arbol = ast.parse(codigo)
    encontrados: list[tuple[int, str]] = []

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            nombre = getattr(nodo.func, "id", None) or getattr(
                nodo.func, "attr", None)
            if nombre in FUNCIONES:
                for argumento in nodo.args:
                    for texto in _literales(argumento):
                        encontrados.append((nodo.lineno, texto))
                for clave in nodo.keywords:
                    if clave.arg in ("esperados", "esperados_en_tab"):
                        for texto in _literales(clave.value):
                            encontrados.append((nodo.lineno, texto))
        elif isinstance(nodo, ast.Assign):
            for objetivo in nodo.targets:
                if (isinstance(objetivo, ast.Name)
                        and objetivo.id in ("esperados", "esperados_en_tab")):
                    for texto in _literales(nodo.value):
                        encontrados.append((nodo.lineno, texto))
        elif isinstance(nodo, ast.Compare):
            if not any(isinstance(op, (ast.Eq, ast.NotEq))
                       for op in nodo.ops):
                continue
            lados = [nodo.left] + list(nodo.comparators)
            for lado in lados:
                if not _menciona_nombre_o_texto(lado):
                    continue
                for otro in lados:
                    if otro is lado:
                        continue
                    for texto in _literales(otro):
                        encontrados.append((nodo.lineno, texto))

    unicos = []
    vistos = set()
    for linea, texto in encontrados:
        if not texto or (linea, texto) in vistos:
            continue
        vistos.add((linea, texto))
        unicos.append((linea, texto))
    return unicos


def _contenido_de_la_app() -> str:
    """Todos los módulos de `bellbird/`, sin la marca de mnemónico y en minúsculas."""
    trozos = []
    for ruta in (RAIZ / "bellbird").rglob("*.py"):
        trozos.append(ruta.read_text(encoding="utf-8"))
    return "\n".join(trozos).replace("&", "").lower()


def _existe(texto: str, contenido: str) -> bool:
    """Si el texto está en la app. Un camino de menú se busca por partes."""
    if " > " in texto:
        partes = [p.strip() for p in texto.split(" > ") if p.strip()]
        return all(_existe(parte, contenido) for parte in partes)
    return texto.replace("&", "").lower() in contenido


class TextosDelBancoTest(unittest.TestCase):

    def test_cada_texto_que_espera_el_banco_existe_en_la_app(self):
        codigo = BANCO.read_text(encoding="utf-8")
        contenido = _contenido_de_la_app()
        faltan = []
        for linea, texto in textos_esperados(codigo):
            if texto in EXCEPCIONES:
                continue
            if not _existe(texto, contenido):
                faltan.append("«%s» en qa/conducir.py:%d" % (texto, linea))
        self.assertEqual(
            faltan, [],
            "El banco espera textos que la aplicación no tiene: "
            + " y ".join(faltan))


if __name__ == "__main__":
    unittest.main()

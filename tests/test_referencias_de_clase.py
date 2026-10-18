"""Guarda: lo asignado en `setUpClass` se suelta en `tearDownClass`."""

import ast
import unittest
from pathlib import Path


def _asignados(en_metodo, nombre_cls):
    """Nombres de `cls.<nombre> = ...` dentro del método."""
    hallados = set()
    for nodo in ast.walk(en_metodo):
        if isinstance(nodo, ast.Assign):
            objetivos = nodo.targets
        elif isinstance(nodo, ast.AnnAssign):
            objetivos = [nodo.target]
        else:
            continue
        for objetivo in objetivos:
            if (isinstance(objetivo, ast.Attribute)
                    and isinstance(objetivo.value, ast.Name)
                    and objetivo.value.id == nombre_cls):
                hallados.add(objetivo.attr)
    return hallados


def _soltados(en_metodo, nombre_cls):
    """Nombres de `del cls.<nombre>` o `delattr(cls, "<nombre>")`."""
    hallados = set()
    for nodo in ast.walk(en_metodo):
        if isinstance(nodo, ast.Delete):
            for objetivo in nodo.targets:
                if (isinstance(objetivo, ast.Attribute)
                        and isinstance(objetivo.value, ast.Name)
                        and objetivo.value.id == nombre_cls):
                    hallados.add(objetivo.attr)
        elif (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Name)
                and nodo.func.id == "delattr"
                and len(nodo.args) >= 2
                and isinstance(nodo.args[0], ast.Name)
                and nodo.args[0].id == nombre_cls
                and isinstance(nodo.args[1], ast.Constant)
                and isinstance(nodo.args[1].value, str)):
            hallados.add(nodo.args[1].value)
    return hallados


def _faltantes(raiz):
    """Lista de (archivo, clase, atributo) sin su `del` en `tearDownClass`."""
    faltan = []
    for archivo in sorted(raiz.glob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in arbol.body:
            if not isinstance(nodo, ast.ClassDef):
                continue
            metodos = {item.name: item for item in nodo.body
                       if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if "setUpClass" not in metodos or not metodos["setUpClass"].args.args:
                continue
            nombre_cls = metodos["setUpClass"].args.args[0].arg
            asignados = _asignados(metodos["setUpClass"], nombre_cls)
            if "tearDownClass" in metodos and metodos["tearDownClass"].args.args:
                nombre_cierre = metodos["tearDownClass"].args.args[0].arg
                soltados = _soltados(metodos["tearDownClass"], nombre_cierre)
            else:
                soltados = set()
            for nombre in sorted(asignados - soltados):
                faltan.append((archivo.name, nodo.name, nombre))
    return faltan


class TestReferenciasDeClase(unittest.TestCase):

    def test_todo_setUpClass_tiene_su_del_en_tearDownClass(self):
        raiz = Path(__file__).resolve().parent
        faltan = _faltantes(raiz)
        detalle = ", ".join(
            f"{archivo}: la clase {clase} asigna cls.{atributo} en "
            f"setUpClass pero no lo suelta con del en tearDownClass"
            for archivo, clase, atributo in faltan)
        self.assertEqual(faltan, [], detalle)


if __name__ == "__main__":
    unittest.main()

"""Diseños de escena propios guardados en disco.

Su única razón para cambiar: cómo se guardan y se leen los diseños de
escena que arma el usuario. No habla con OBS ni con wx: convierte entre
`Diseno` y el JSON de `paths.disenos_escena()`.
"""

from __future__ import annotations

from dataclasses import MISSING, fields

from guyrapu.core import archivos, diagnostico, paths
from guyrapu.obs.disenos_escena import (
    CHATS, CLASES, ESQUINAS, MODOS, PROPORCIONES, TAMANOS, Diseno)

logger = diagnostico.obtener_logger(__name__)

_TOPE_NOMBRE = 60

_CAMPOS_VALIDOS = {
    "esquina": ESQUINAS,
    "proporcion": PROPORCIONES,
    "chat": CHATS,
    "esquina_chat": ESQUINAS,
}
_DEFECTOS = {campo.name: campo.default for campo in fields(Diseno)
             if campo.default is not MISSING}


def _ruta_de(ruta):
    return ruta or paths.disenos_escena()


def _normalizar_nombre(nombre):
    return (nombre or "").strip()[:_TOPE_NOMBRE]


def _motivo_de_descarte(datos):
    """El motivo por el que una entrada no sirve, o None si es válida."""
    if not isinstance(datos, dict):
        return "la entrada no es un objeto"
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        return "la entrada no tiene nombre"
    if datos.get("clase") not in CLASES:
        return f"la clase del diseño {nombre.strip()} es desconocida"
    for campo in ("principal", "secundaria", "izquierda", "derecha"):
        if not isinstance(datos.get(campo, ""), str):
            return f"el campo {campo} del diseño {nombre.strip()} no es texto"
    for campo, permitidos in _CAMPOS_VALIDOS.items():
        if datos.get(campo, _DEFECTOS[campo]) not in permitidos:
            return f"el campo {campo} del diseño {nombre.strip()} es desconocido"
    tamano = datos.get("tamano", _DEFECTOS["tamano"])
    if not isinstance(tamano, str) or tamano not in TAMANOS:
        return f"el tamaño del diseño {nombre.strip()} es desconocido"
    modos = datos.get("modos", {})
    if not isinstance(modos, dict):
        return f"los modos del diseño {nombre.strip()} no son un objeto"
    for fuente, modo in modos.items():
        if not isinstance(fuente, str) or modo not in MODOS:
            return f"el diseño {nombre.strip()} tiene un modo de ajuste desconocido"
    return None


def _diseno_de(datos):
    valores = {campo: datos.get(campo, defecto)
               for campo, defecto in _DEFECTOS.items()}
    return Diseno(clase=datos["clase"],
                  modos=dict(datos.get("modos") or {}), **valores)


def _a_dict(nombre, diseno):
    return {
        "nombre": nombre,
        "clase": diseno.clase,
        "principal": diseno.principal,
        "secundaria": diseno.secundaria,
        "izquierda": diseno.izquierda,
        "derecha": diseno.derecha,
        "esquina": diseno.esquina,
        "tamano": diseno.tamano,
        "proporcion": diseno.proporcion,
        "chat": diseno.chat,
        "esquina_chat": diseno.esquina_chat,
        "modos": dict(diseno.modos),
    }


def _escribir(disenos, ruta):
    archivos.escribir_json_atomico(
        _ruta_de(ruta),
        [_a_dict(nombre, diseno) for nombre, diseno in disenos],
        ensure_ascii=False)


def cargar(ruta=None) -> list:
    """Los diseños guardados como pares (nombre, Diseno), en su orden.

    Un archivo que falta, está roto o no es una lista se lee como lista
    vacía. Las entradas inválidas se descartan y se registran, sin tirar
    las que sí sirven ni lanzar.
    """
    datos = archivos.leer_json(_ruta_de(ruta), [])
    if not isinstance(datos, list):
        logger.warning("El archivo de diseños guardados no es una lista")
        return []
    disenos = []
    for indice, entrada in enumerate(datos, 1):
        motivo = _motivo_de_descarte(entrada)
        if motivo is not None:
            logger.warning("Se descartó el diseño número %s: %s", indice, motivo)
            continue
        disenos.append((entrada["nombre"].strip(), _diseno_de(entrada)))
    return disenos


def guardar_diseno(nombre, diseno, ruta=None) -> list:
    """Guarda el diseño y devuelve la lista nueva.

    Un nombre que ya existe, sin distinguir mayúsculas, se reemplaza en su
    lugar y conserva el orden.
    """
    nombre = _normalizar_nombre(nombre)
    if not nombre:
        raise ValueError("El nombre del diseño no puede estar vacío")
    disenos = cargar(ruta)
    for indice, (existente, _diseno) in enumerate(disenos):
        if existente.casefold() == nombre.casefold():
            disenos[indice] = (nombre, diseno)
            break
    else:
        disenos.append((nombre, diseno))
    _escribir(disenos, ruta)
    return disenos


def eliminar_diseno(nombre, ruta=None) -> list:
    """Saca el diseño con ese nombre y devuelve la lista nueva."""
    buscado = _normalizar_nombre(nombre).casefold()
    disenos = [par for par in cargar(ruta) if par[0].casefold() != buscado]
    _escribir(disenos, ruta)
    return disenos

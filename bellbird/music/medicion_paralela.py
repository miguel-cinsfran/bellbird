"""Reparto de mediciones de sonoridad entre trabajos simultáneos.

Módulo puro: no sabe de la caché, de la música ni de la interfaz. Solo
decide cuántas mediciones corren a la vez y las entrega a medida que
terminan.
"""

from __future__ import annotations

import concurrent.futures

from bellbird.core import diagnostico


logger = diagnostico.obtener_logger(__name__)

MAXIMO_TRABAJOS = 4


def trabajos_de_medicion(nucleos):
    """Cuántas canciones se miden a la vez con esa cantidad de núcleos.

    La mitad de los núcleos, con un mínimo de uno y un tope de cuatro:
    la medición puede correr mientras OBS transmite en el mismo equipo.
    """
    return max(1, min(MAXIMO_TRABAJOS, (nucleos or 1) // 2))


def _medir_seguro(medir, elemento):
    """El resultado de `medir`, o None si lanzó."""
    try:
        return medir(elemento)
    except Exception:
        logger.exception("No se pudo medir %r", elemento)
        return None


def medir_en_paralelo(elementos, medir, seguir, trabajos):
    """Entrega `(elemento, resultado)` a medida que termina cada medición.

    Nunca hay más de `trabajos` mediciones enviadas sin terminar: los
    elementos se envían de a poco, no todos al principio. Antes de enviar
    cada uno consulta `seguir()`; si da falso no envía más, espera las que
    están en curso, las entrega y termina. Si `medir` lanza, ese elemento
    se entrega con resultado None y se anota en el registro.
    """
    pendientes = iter(elementos)
    en_curso = {}
    limite = max(1, trabajos)
    agotados = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=limite) as ejecutor:
        while en_curso or not agotados:
            while (not agotados and len(en_curso) < limite and seguir()):
                try:
                    elemento = next(pendientes)
                except StopIteration:
                    agotados = True
                    break
                futuro = ejecutor.submit(_medir_seguro, medir, elemento)
                en_curso[futuro] = elemento
            if not en_curso:
                break
            terminados, _restantes = concurrent.futures.wait(
                en_curso, return_when=concurrent.futures.FIRST_COMPLETED)
            for futuro in terminados:
                elemento = en_curso.pop(futuro)
                yield elemento, futuro.result()

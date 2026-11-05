"""Edición textual de la sección [sonidos] de sounds.ini, sin wx.

`silenciados` lee qué eventos están callados (clave presente con valor
vacío) y `con_silenciados` devuelve el texto con los cambios aplicados,
conservando comentarios, orden y el resto de líneas. La lectura y la
escritura del archivo viven en la página de Preferencias.
"""

from __future__ import annotations


def _en_sonidos(linea: str, dentro: bool) -> bool:
    """Si esta línea abre una sección, dice si es [sonidos]."""
    cortada = linea.strip()
    if cortada.startswith("["):
        return cortada.lower() == "[sonidos]"
    return dentro


def _clave(linea: str) -> str:
    """Clave en minúsculas si la línea trae `clave = valor`, si no «»."""
    cortada = linea.strip()
    if not cortada or cortada.startswith(("#", ";", "[")):
        return ""
    if "=" not in linea:
        return ""
    return linea.split("=", 1)[0].strip().lower()


def _valor(linea: str) -> str | None:
    """Valor sin bordes si la línea trae `=`, si no None."""
    if "=" not in linea:
        return None
    return linea.split("=", 1)[1].strip()


def silenciados(texto: str) -> set:
    """Eventos callados: clave presente con valor vacío en [sonidos]."""
    callados = set()
    dentro = False
    for linea in texto.splitlines():
        dentro = _en_sonidos(linea, dentro)
        if not dentro:
            continue
        clave = _clave(linea)
        if clave and _valor(linea) == "":
            callados.add(clave)
    return callados


def _pos_insercion(lineas: list) -> int | None:
    """Dónde va una clave nueva: tras la última clave de [sonidos]."""
    dentro = False
    pos = None
    for i, linea in enumerate(lineas):
        cortada = linea.strip()
        if cortada.startswith("["):
            if dentro:
                break
            dentro = cortada.lower() == "[sonidos]"
            if dentro:
                pos = i + 1
            continue
        if not dentro:
            continue
        if not cortada or cortada.startswith(("#", ";")):
            continue
        if "=" not in linea:
            continue
        pos = i + 1
    return pos


def con_silenciados(texto: str, silenciar: set, eventos: list) -> str:
    """Texto con `silenciar` callados (`evento =` vacío) y el resto de
    `eventos` activos. Destildar pisa el override con la línea vacía y
    volver a tildar usa el archivo del tema, porque la ruta se perdió.
    Una ruta propia de un evento que sigue tildado no se toca nunca:
    solo se quitan las líneas vacías. Conserva comentarios y orden."""
    silenciar_bajo = {str(ev).strip().lower() for ev in silenciar}
    eventos_bajo = [str(ev).strip().lower() for ev in eventos]
    originales = {str(ev).strip().lower(): str(ev).strip() for ev in eventos}
    for ev in silenciar_bajo:
        originales.setdefault(ev, ev)
    lineas = texto.splitlines(keepends=True)
    dentro = False
    vistos = set()
    quitar = set()
    for i, linea in enumerate(lineas):
        dentro = _en_sonidos(linea, dentro)
        if not dentro:
            continue
        clave = _clave(linea)
        if not clave:
            continue
        if clave in silenciar_bajo:
            vistos.add(clave)
            if _valor(linea) != "":
                fin = "\n" if linea.endswith("\n") else ""
                lineas[i] = f"{linea.split('=', 1)[0].strip()} ={fin}"
        elif clave in eventos_bajo and _valor(linea) == "":
            quitar.add(i)
    lineas = [l for i, l in enumerate(lineas) if i not in quitar]
    faltan = []
    for ev in eventos_bajo:
        if ev in silenciar_bajo and ev not in vistos:
            faltan.append(originales[ev])
    for ev in sorted(silenciar_bajo - vistos - set(eventos_bajo)):
        faltan.append(originales[ev])
    if faltan:
        pos = _pos_insercion(lineas)
        if pos is None:
            if lineas and not lineas[-1].endswith("\n"):
                lineas[-1] += "\n"
            lineas.extend(["\n", "[sonidos]\n"])
            pos = len(lineas)
        for j, ev in enumerate(faltan):
            lineas.insert(pos + j, f"{ev} =\n")
    return "".join(lineas)

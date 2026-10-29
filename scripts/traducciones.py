"""Extrae, actualiza y compila los catálogos de traducción con Babel.

Órdenes:

    python scripts/traducciones.py extraer
    python scripts/traducciones.py actualizar <código>
    python scripts/traducciones.py compilar
    python scripts/traducciones.py revisar <código>

La plantilla queda en idiomas/bellbird.pot. Cada idioma vive en
idiomas/<código>/LC_MESSAGES/bellbird.po y su catálogo compilado en
bellbird.mo. Las funciones reciben las carpetas por parámetro para poder
probarlas en una carpeta temporal.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from babel.messages import catalog, extract, mofile, pofile

DOMINIO = "bellbird"
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_IDIOMAS = RAIZ / "idiomas"

PALABRAS_CLAVE = {
    "_": None,
    "N_": None,
    "ngettext": (1, 2),
    "pgettext": ((1, "c"), 2),
}
ETIQUETAS = ("Traductores:",)


def ruta_plantilla(carpeta_idiomas):
    return Path(carpeta_idiomas) / f"{DOMINIO}.pot"


def ruta_po(carpeta_idiomas, codigo):
    return Path(carpeta_idiomas) / codigo / "LC_MESSAGES" / f"{DOMINIO}.po"


def ruta_mo(carpeta_idiomas, codigo):
    return Path(carpeta_idiomas) / codigo / "LC_MESSAGES" / f"{DOMINIO}.mo"


def _archivos_fuente(carpeta_raiz):
    raiz = Path(carpeta_raiz)
    archivos = [raiz / "main.py"]
    archivos.extend(sorted((raiz / "bellbird").rglob("*.py")))
    return [archivo for archivo in archivos if archivo.is_file()]


def _agregar(catalogo, mensaje, archivo, numero, comentarios, contexto):
    if not mensaje:
        return
    catalogo.add(
        mensaje,
        locations=[(archivo, numero)],
        auto_comments=comentarios,
        context=contexto,
    )


def extraer(carpeta_raiz=RAIZ, carpeta_idiomas=CARPETA_IDIOMAS):
    """Genera la plantilla .pot desde main.py y bellbird/."""
    raiz = Path(carpeta_raiz)
    catalogo = catalog.Catalog(domain=DOMINIO, project="Bellbird")
    for archivo in _archivos_fuente(raiz):
        relativa = str(archivo.relative_to(raiz)).replace("\\", "/")
        extraidos = extract.extract_from_file(
            "python", archivo, keywords=PALABRAS_CLAVE,
            comment_tags=ETIQUETAS)
        for numero, mensaje, comentarios, contexto in extraidos:
            _agregar(catalogo, mensaje, relativa, numero, comentarios, contexto)
    plantilla = ruta_plantilla(carpeta_idiomas)
    plantilla.parent.mkdir(parents=True, exist_ok=True)
    with plantilla.open("wb") as salida:
        pofile.write_po(salida, catalogo)
    return plantilla


def actualizar(codigo, carpeta_raiz=RAIZ, carpeta_idiomas=CARPETA_IDIOMAS):
    """Crea o actualiza el .po del código sin perder lo ya traducido."""
    plantilla = ruta_plantilla(carpeta_idiomas)
    if not plantilla.is_file():
        extraer(carpeta_raiz, carpeta_idiomas)
    with plantilla.open("rb") as entrada:
        base = pofile.read_po(entrada)
    destino = ruta_po(carpeta_idiomas, codigo)
    if destino.is_file():
        with destino.open("rb") as entrada:
            catalogo = pofile.read_po(entrada)
    else:
        catalogo = catalog.Catalog(locale=codigo, domain=DOMINIO)
    catalogo.update(base)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as salida:
        pofile.write_po(salida, catalogo, include_previous=True)
    return destino


def compilar(carpeta_idiomas=CARPETA_IDIOMAS):
    """Compila todos los .po de la carpeta a su .mo."""
    compilados = []
    for po in sorted(Path(carpeta_idiomas).rglob("*.po")):
        with po.open("rb") as entrada:
            catalogo = pofile.read_po(entrada)
        mo = po.with_suffix(".mo")
        with mo.open("wb") as salida:
            mofile.write_mo(salida, catalogo)
        compilados.append(mo)
    return compilados


_HUECO = re.compile(r"\{[^{}]*\}")


def _huecos(texto):
    return sorted(_HUECO.findall(texto))


def _accesos(texto):
    return len(re.findall(r"&(?!&)\S", texto.replace("&&", "")))


def _atajo(texto):
    return texto.split("\t", 1)[1] if "\t" in texto else None


def problemas_de(original, traducido):
    """Lista de problemas de un par original y traducción."""
    salida = []
    if _huecos(original) != _huecos(traducido):
        salida.append(f"huecos {_huecos(original)} contra {_huecos(traducido)}")
    if _accesos(original) != _accesos(traducido):
        salida.append("letras de acceso distintas")
    if _atajo(original) != _atajo(traducido):
        salida.append("el atajo tras el tabulador cambió")
    if original.rstrip().endswith("…") != traducido.rstrip().endswith("…"):
        salida.append("puntos suspensivos distintos")
    if original.strip() and not traducido.strip():
        salida.append("vacío")
    return salida


def _pares(mensaje):
    if isinstance(mensaje.id, (list, tuple)):
        destinos = mensaje.string or ()
        return [(mensaje.id[min(i, 1)], d) for i, d in enumerate(destinos)]
    return [(mensaje.id, mensaje.string)]


def revisar(ruta):
    """Revisa un .po traducido sin leerlo entero.

    Por cada entrada traducida comprueba lo que rompe la app o el lector
    si sale mal: los huecos con nombre ({autor}) iguales, una letra de
    acceso donde el original tiene una, el atajo después de un tabulador
    sin traducir, y los puntos suspensivos donde el original los tiene.
    Cuenta también las que faltan traducir y las marcadas fuzzy. Sale
    con 1 si hay algún problema.
    """
    with open(ruta, "rb") as archivo:
        catalogo = pofile.read_po(archivo)
    total = faltan = difusas = 0
    errores = []
    for mensaje in catalogo:
        if not mensaje.id:
            continue
        total += 1
        if mensaje.fuzzy:
            difusas += 1
        pares = _pares(mensaje)
        if not all(d for _o, d in pares):
            faltan += 1
            continue
        for original, traducido in pares:
            for problema in problemas_de(original, traducido):
                lugar = mensaje.locations[0] if mensaje.locations else ("?", 0)
                errores.append(f"{lugar[0]}:{lugar[1]}: {problema}: {original[:60]!r}")
    for linea in errores:
        print(linea)
    print(f"{total} textos, {total - faltan} traducidos, {faltan} sin traducir, "
          f"{difusas} fuzzy, {len(errores)} problemas.")
    return 1 if errores else 0


def _agregar_carpetas(parser):
    parser.add_argument("--carpeta-raiz", type=Path, default=RAIZ)
    parser.add_argument("--carpeta-idiomas", type=Path, default=CARPETA_IDIOMAS)


def _parser():
    parser = argparse.ArgumentParser(
        description="Extrae, actualiza y compila las traducciones de Bellbird.")
    ordenes = parser.add_subparsers(dest="orden", required=True)

    extraer_parser = ordenes.add_parser(
        "extraer", help="genera idiomas/bellbird.pot")
    _agregar_carpetas(extraer_parser)

    actualizar_parser = ordenes.add_parser(
        "actualizar", help="crea o actualiza el .po de un idioma")
    actualizar_parser.add_argument("codigo")
    _agregar_carpetas(actualizar_parser)

    compilar_parser = ordenes.add_parser(
        "compilar", help="compila todos los .po a .mo")
    compilar_parser.add_argument(
        "--carpeta-idiomas", type=Path, default=CARPETA_IDIOMAS)

    revisar_parser = ordenes.add_parser(
        "revisar", help="revisa el .po de un idioma")
    revisar_parser.add_argument("codigo")
    revisar_parser.add_argument(
        "--carpeta-idiomas", type=Path, default=CARPETA_IDIOMAS)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.orden == "extraer":
        ruta = extraer(args.carpeta_raiz, args.carpeta_idiomas)
        print(f"Plantilla actualizada: {ruta}")
    elif args.orden == "actualizar":
        ruta = actualizar(
            args.codigo, args.carpeta_raiz, args.carpeta_idiomas)
        print(f"Catálogo actualizado: {ruta}")
    elif args.orden == "revisar":
        return revisar(ruta_po(args.carpeta_idiomas, args.codigo))
    else:
        rutas = compilar(args.carpeta_idiomas)
        print(f"Catálogos compilados: {len(rutas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

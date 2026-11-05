#!/usr/bin/env python
"""Genera las versiones HTML de la documentación con pandoc.

Los .md son cómodos para editar y se leen bien en GitHub, pero el amigo que usa
la aplicación no tiene por qué saber abrir un Markdown. Este script convierte
los documentos de cara al usuario a HTML autocontenido (con el estilo dentro del
propio archivo, sin depender de nada externo), fácil de abrir con doble clic y
de leer con lector de pantalla.

Cada idioma tiene su carpeta en `docs/`: `docs/es/`, `docs/en/` y las que
lleguen. Cada `.md` se convierte al `.html` que queda a su lado. El manual y el
historial de versiones viven en esas carpetas; la guía de la API sigue suelta
en `docs/`.

Además escribe `docs/manual-paquete.html`, una página corta que lleva al manual
de cada idioma desde la raíz del paquete.

Uso:
    uv run python scripts/generar_docs.py

Requiere pandoc en el PATH (https://pandoc.org). Los HTML se escriben junto a
su .md y se versionan; hay que regenerarlos y commitearlos cuando cambie un .md.
El paquete distribuible (construir.bat) copia docs/, así que viajan con la app.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Raíz del repositorio: la carpeta padre de scripts/.
RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"

# Título de la pestaña y del lector de pantalla para cada documento e idioma.
TITULOS = {
    ("es", "MANUAL"): "Guyrapu, manual de uso",
    ("es", "CHANGELOG"): "Guyrapu, novedades",
    ("es", "CONFIGURACION_API"): "Guyrapu, configurar la API de YouTube",
    ("en", "MANUAL"): "Guyrapu, user manual",
    ("en", "CHANGELOG"): "Guyrapu, what's new",
}

# Cómo se llama el manual en la página del paquete, en cada idioma.
NOMBRES_MANUAL = {"es": "Manual de uso", "en": "User manual"}

# Estilo embebido: sobrio, legible y responsivo, con modo claro y oscuro según
# el sistema. Sin fuentes ni recursos externos, para que el HTML se abra en
# cualquier equipo sin conexión.
_ESTILO = """<style>
:root {
  --fondo: #ffffff; --texto: #1c2629; --tenue: #56656a;
  --acento: #0b6e63; --borde: #e2e8e8; --codigo-fondo: #f3f6f6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fondo: #14191b; --texto: #e4ebeb; --tenue: #9aa8ac;
    --acento: #45c9b6; --borde: #2f393c; --codigo-fondo: #1c2427;
  }
}
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.65; color: var(--texto); background: var(--fondo);
  max-width: 46rem; margin: 0 auto; padding: 2rem 1.25rem 4rem;
  font-size: 1.05rem;
}
h1, h2, h3 { line-height: 1.25; margin-top: 2.2rem; }
h1 { font-size: 1.9rem; color: var(--acento); border-bottom: 2px solid var(--borde); padding-bottom: .4rem; }
h2 { font-size: 1.4rem; border-bottom: 1px solid var(--borde); padding-bottom: .3rem; }
h3 { font-size: 1.15rem; color: var(--tenue); }
a { color: var(--acento); }
code {
  background: var(--codigo-fondo); padding: .12em .35em;
  border-radius: 4px; font-size: .9em;
}
pre {
  background: var(--codigo-fondo); padding: 1rem; border-radius: 6px;
  overflow-x: auto; border: 1px solid var(--borde);
}
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; overflow-x: auto; display: block; }
th, td { border: 1px solid var(--borde); padding: .5rem .7rem; text-align: left; }
th { background: var(--codigo-fondo); }
blockquote {
  border-left: 3px solid var(--acento); margin: 1rem 0;
  padding: .2rem 1rem; color: var(--tenue);
}
hr { border: none; border-top: 1px solid var(--borde); margin: 2rem 0; }
</style>
"""

_ESQUEMA = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_HREF = re.compile(r'href="([^"]*)"')


def documentos_sueltos():
    """Los .md de docs/ que no viven en una carpeta de idioma."""
    return [DOCS / "CONFIGURACION_API.md"]


def idiomas():
    """Carpetas de idioma de docs/ que tienen algún .md."""
    return sorted(carpeta for carpeta in DOCS.iterdir()
                  if carpeta.is_dir() and any(carpeta.glob("*.md")))


def _titulo(idioma, md):
    return TITULOS.get((idioma, md.stem), md.stem)


def documentos():
    """Origen, destino, título e idioma de cada documento a convertir."""
    lista = [(md, md.with_suffix(".html"), _titulo("es", md), "es")
             for md in documentos_sueltos()]
    for carpeta in idiomas():
        for md in sorted(carpeta.glob("*.md")):
            lista.append((md, md.with_suffix(".html"),
                          _titulo(carpeta.name, md), carpeta.name))
    return lista


def _reescribir_enlaces(html: str) -> str:
    """Pasa los enlaces relativos a .md a su .html y deja intactos los absolutos."""
    def cambiar(coincidencia):
        url = coincidencia.group(1)
        if _ESQUEMA.match(url) or url.startswith("#"):
            return coincidencia.group(0)
        if url.endswith(".md"):
            return f'href="{url[:-3]}.html"'
        return coincidencia.group(0)

    return _HREF.sub(cambiar, html)


def _convertir(md: Path, salida: Path, titulo: str, header: Path,
               idioma: str = "es") -> bool:
    if not md.exists():
        print(f"  [saltado] no existe {md.name}")
        return True   # no es un fallo: puede que ese .md aún no exista
    # pagetitle (no title): pone el <title> de la pestaña/lector SIN duplicar un
    # <h1> de título en el cuerpo (el .md ya trae su propio encabezado de nivel 1).
    cmd = [
        "pandoc", str(md), "-o", str(salida),
        "--standalone", "--from", "gfm", "--to", "html5",
        "--metadata", f"pagetitle={titulo}", "--metadata", f"lang={idioma}",
        "--include-in-header", str(header),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(f"  [FALLO] {md.name}: {exc.stderr.strip()}")
        return False
    html = salida.read_text(encoding="utf-8")
    salida.write_text(_reescribir_enlaces(html), encoding="utf-8")
    print(f"  [ok] {md.name}  ->  {salida.name}")
    return True


def _escribir_manual_paquete() -> bool:
    """Página corta que lleva al manual de cada idioma desde la raíz del paquete."""
    enlaces = []
    for carpeta in idiomas():
        if (carpeta / "MANUAL.md").is_file():
            nombre = NOMBRES_MANUAL.get(carpeta.name, "Manual de uso")
            enlaces.append(f'<li><a href="docs/{carpeta.name}/MANUAL.html">'
                           f"{nombre}</a></li>")
    if not enlaces:
        print("  [saltado] ningún idioma tiene manual")
        return True
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Guyrapu, manual de uso</title>\n"
        "<!-- Los enlaces valen desde la raíz del paquete. -->\n"
        f"{_ESTILO}"
        "</head>\n"
        "<body>\n"
        "<h1>Guyrapu</h1>\n"
        "<ul>\n"
        + "\n".join(f"  {enlace}" for enlace in enlaces)
        + "\n</ul>\n"
        "</body>\n"
        "</html>\n"
    )
    (DOCS / "manual-paquete.html").write_text(html, encoding="utf-8")
    print("  [ok] manual-paquete.html")
    return True


def main() -> int:
    if shutil.which("pandoc") is None:
        print("ERROR: pandoc no está en el PATH. Instálalo desde https://pandoc.org")
        return 1
    DOCS.mkdir(exist_ok=True)
    print("Generando documentación HTML (pandoc)...")
    # El bloque <style> va a un archivo temporal que pandoc mete en el <head>.
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        f.write(_ESTILO)
        header = Path(f.name)
    ok = True
    try:
        for md, salida, titulo, idioma in documentos():
            ok = _convertir(md, salida, titulo, header, idioma) and ok
        ok = _escribir_manual_paquete() and ok
    finally:
        try:    header.unlink()
        except OSError: pass
    print("Listo." if ok else "Terminó con errores.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

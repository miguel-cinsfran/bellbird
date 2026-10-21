"""Coherencia entre la fábrica, el código, Preferencias, los sonidos y el manual.

Cuatro reglas con una clase de pruebas por regla. Sin wx y sin ventanas:
todo se comprueba con `ast` sobre el código fuente y leyendo archivos de
texto, más los módulos puros (`config_predeterminada`, `config` y
`atajos_captura`), que no arrastran wx.
"""

import ast
import re
import unittest
from pathlib import Path

from ytchat.core import config as cfg
from ytchat.core import config_predeterminada as fabrica
from ytchat.ui import atajos_captura

RAIZ = Path(__file__).resolve().parent.parent


def _arbol(ruta_relativa):
    """Árbol `ast` de un archivo del repositorio."""
    return ast.parse((RAIZ / ruta_relativa).read_text(encoding="utf-8"))


def _es_texto(nodo):
    return isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)


# ── Regla 1: F2 ─────────────────────────────────────────────────────────────

def _datos_f2():
    """COMPONENTES, ETIQUETAS, claves del dict de render, campos del snapshot
    y campos dichos (`s.campo`) en una sola pasada por `estado_sesion.py`.
    `formatear_estado` cuenta como render porque anuncia
    `transmision_supervisada`, que ningún `_render_*` toca por separado."""
    componentes, etiquetas, render, campos, dichos = set(), set(), set(), set(), set()
    arbol = _arbol("ytchat/capture/estado_sesion.py")
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            valor = nodo.value
            destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            if len(destinos) == 1 and isinstance(destinos[0], ast.Name):
                nombre = destinos[0].id
                if nombre == "COMPONENTES":
                    componentes = {ast.literal_eval(e) for e in valor.elts}
                elif nombre == "ETIQUETAS" and isinstance(valor, ast.Dict):
                    etiquetas = {k.value for k in valor.keys}
                elif (isinstance(valor, ast.Dict) and valor.keys and all(
                        _es_texto(k) and isinstance(v, ast.Name)
                        and v.id.startswith("_render")
                        for k, v in zip(valor.keys, valor.values))):
                    render = {k.value for k in valor.keys}
        elif isinstance(nodo, ast.ClassDef) and nodo.name == "SnapshotSesion":
            campos = {n.target.id for n in nodo.body
                      if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
        elif (isinstance(nodo, ast.FunctionDef)
                and (nodo.name.startswith("_render")
                     or nodo.name == "formatear_estado")):
            parametros = nodo.args.args
            dueno = parametros[0].arg if parametros else ""
            dichos.update(sub.attr for sub in ast.walk(nodo)
                          if isinstance(sub, ast.Attribute)
                          and isinstance(sub.value, ast.Name)
                          and sub.value.id == dueno)
    return componentes, etiquetas, render, campos, dichos


class PruebaEstadoF2(unittest.TestCase):
    def test_conjuntos_iguales(self):
        componentes, etiquetas, render, _, _ = _datos_f2()
        candidatos = {
            "ETIQUETAS (ytchat/capture/estado_sesion.py)": etiquetas,
            "render (ytchat/capture/estado_sesion.py)": render,
            "[estado] (ytchat/core/config_predeterminada.py)": set(
                fabrica.seccion("estado")),
        }
        problemas = []
        for nombre, conjunto in sorted(candidatos.items()):
            problemas.extend(f"falta {f!r} en {nombre}"
                             for f in sorted(componentes - conjunto))
            problemas.extend(f"sobra {s!r} en {nombre}"
                             for s in sorted(conjunto - componentes))
        self.assertEqual(problemas, [],
                         "F2 desparejo con COMPONENTES:\n" + "\n".join(problemas))

    def test_todo_campo_se_dice(self):
        _, _, _, campos, dichos = _datos_f2()
        mudos = sorted(campos - dichos)
        self.assertEqual(mudos, [],
                         "Campos de SnapshotSesion que ninguna función de render "
                         f"lee (ytchat/capture/estado_sesion.py): {mudos}")


# ── Regla 2: sonidos ────────────────────────────────────────────────────────

def _ruta_punteada(nodo):
    partes = []
    while isinstance(nodo, ast.Attribute):
        partes.append(nodo.attr)
        nodo = nodo.value
    if isinstance(nodo, ast.Name):
        partes.append(nodo.id)
    return ".".join(reversed(partes))


def _nombres_y_dinamicos():
    """Nombres de eventos juntados con `ast` sobre `ytchat/` y `main.py`:
    literales de `_snd.reproducir(...)` (o `sound_player` por otro nombre),
    segundo argumento literal o `sonido=` de `Aviso(...)`, y valores de las
    constantes `SONIDO*` (incluidos los dicts como `_SONIDO_POR_FIN`).
    Devuelve (nombres, dinámicos) donde dinámicos son "archivo:línea"."""
    nombres, dinamicos = set(), []
    archivos = sorted((RAIZ / "ytchat").rglob("*.py")) + [RAIZ / "main.py"]
    for ruta in archivos:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        relativo = str(ruta.relative_to(RAIZ))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            punteo = _ruta_punteada(nodo.func)
            ultimo = punteo.rsplit(".", 1)[-1]
            if ultimo == "reproducir" and ("_snd" in punteo
                                           or "sound_player" in punteo
                                           or punteo == "reproducir"):
                if nodo.args and _es_texto(nodo.args[0]):
                    nombres.add(nodo.args[0].value)
                else:
                    dinamicos.append(f"{relativo}:{nodo.lineno}")
            elif ultimo == "Aviso":
                if len(nodo.args) >= 2 and _es_texto(nodo.args[1]):
                    nombres.add(nodo.args[1].value)
                for palabra in nodo.keywords:
                    if palabra.arg == "sonido" and _es_texto(palabra.value):
                        nombres.add(palabra.value.value)
        for stmt in arbol.body:
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            destinos = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for destino in destinos:
                if not (isinstance(destino, ast.Name)
                        and (destino.id.startswith("SONIDO")
                             or destino.id.startswith("_SONIDO"))):
                    continue
                valor = stmt.value
                if _es_texto(valor):
                    nombres.add(valor.value)
                elif isinstance(valor, ast.Dict):
                    for item in valor.values:
                        if _es_texto(item):
                            nombres.add(item.value)
    return nombres, sorted(dinamicos)


def _eventos_sounds_ini():
    """Nombres de la lista comentada de eventos de `sounds.ini`: las líneas
    con `#` que traen comas (las de prosa no traen y se saltean)."""
    eventos = set()
    for linea in (RAIZ / "sounds.ini").read_text(encoding="utf-8").splitlines():
        if linea.startswith("#") and "," in linea:
            eventos.update(re.findall(r"[a-z_]+", linea))
    return eventos


def _eventos_generadores():
    """Evento por `.wav` de cada diccionario de `TEMAS` en `sound_gen.py`."""
    arbol = _arbol("scripts/sound_gen.py")
    temas = {}
    for nodo in ast.walk(arbol):
        destino = None
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            destino = nodo.targets[0]
        elif isinstance(nodo, ast.AnnAssign):
            destino = nodo.target
        if (isinstance(destino, ast.Name) and destino.id == "TEMAS"
                and isinstance(nodo.value, ast.Dict)):
            for clave, valor in zip(nodo.value.keys, nodo.value.values):
                archivo = ast.literal_eval(clave)
                temas[archivo] = {ast.literal_eval(k)[:-4] for k in valor.keys}
    return temas


class PruebaSonidos(unittest.TestCase):
    TEMAS = ("default", "suave")

    def test_usados_tienen_wav_en_temas(self):
        nombres, _ = _nombres_y_dinamicos()
        faltan = [f"{tema}/{ev}.wav" for ev in sorted(nombres)
                  for tema in self.TEMAS
                  if not (RAIZ / "sounds" / "themes" / tema / f"{ev}.wav").exists()]
        self.assertEqual(faltan, [], "Sonidos usados sin .wav:\n" + "\n".join(faltan))

    def test_usados_en_generadores(self):
        nombres, _ = _nombres_y_dinamicos()
        generadores = _eventos_generadores()
        faltan = [f"{t}/{ev}" for ev in sorted(nombres) for t in self.TEMAS
                  if ev not in generadores.get(t, set())]
        self.assertEqual(faltan, [],
                         "Sonidos usados fuera de scripts/sound_gen.py:\n"
                         + "\n".join(faltan))

    def test_usados_en_sounds_ini(self):
        nombres, _ = _nombres_y_dinamicos()
        faltan = sorted(nombres - _eventos_sounds_ini())
        self.assertEqual(faltan, [],
                         "Sonidos usados fuera de la lista comentada de "
                         f"sounds.ini: {faltan}")

    def test_usados_en_lista_canonica(self):
        nombres, _ = _nombres_y_dinamicos()
        faltan = sorted(nombres - set(cfg._EVENTOS_SONIDO))
        self.assertEqual(faltan, [],
                         "Sonidos usados fuera de config._EVENTOS_SONIDO "
                         f"(ytchat/core/config.py): {faltan}")


# ── Regla 3: configuración ──────────────────────────────────────────────────

# Secciones que Preferencias arma recorriendo una lista: [estado] sale de
# COMPONENTES (regla 1) y [atajos] se edita en su página propia (regla 4).
_SECCIONES_CON_REGLA_PROPIA = {"estado", "atajos"}

# Claves sin control a propósito: dónde se escribe cada una.
INTERNAS = {
    ("descargas", "bitrate"): "gestor de descargas (config.py:436, desde gui_descargas.py:353)",
    ("descargas", "carpeta"): "gestor de descargas (config.py:436, desde gui_descargas.py:353)",
    ("descargas", "enumerar"): "gestor de descargas (config.py:436, desde gui_descargas.py:353)",
    ("descargas", "formato"): "gestor de descargas (config.py:436, desde gui_descargas.py:353)",
    ("ia", "direccion"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("ia", "largo"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("ia", "modelo"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("ia", "pregunta"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("ia", "privacidad_aceptada"): "la escribe el aviso de privacidad de la IA, no lleva control",
    ("ia", "proveedor"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("ia", "solo_gratis"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("ia", "tiempo_espera"): "su control llega con la página Inteligencia artificial de Preferencias (MD/roadmap.md, sección 8)",
    ("musica", "mostrar_cola"): "la recuerda la ventana Música (musica_memoria.py:19, guarda en gui_musica.py:465)",
    ("overlay", "activo"): "la enciende la ventana Transmisión (gui_transmitir.py:32 y 37)",
    ("sesion", "silenciar_lectura"): "la cambia F4 en la ventana principal (gui.py:1340)",
    ("sesion", "ultima_direccion"): "se guarda al conectar (gui.py:1874)",
    ("sesion", "version_atajos"): "la escribe la migración de atajos (atajos.py:303)",
    ("tiktok", "usuario"): "lo guarda la ventana Transmisión (gui_transmitir.py:42)",
    ("transmision", "destino"): "lo guarda la ventana Transmisión (gui_transmitir.py:51)",
    ("transmision", "avisar_sobrecarga"): "lo cambia su menú (gui_transmitir.py:60)",
    ("transmision", "youtube_titulo"): "lo guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_descripcion"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_privacidad"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_latencia"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_ninos"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_dvr"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_categoria"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_etiquetas"): "las guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_miniatura"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_lista"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("transmision", "youtube_lista_titulo"): "la guarda la ventana Transmisión (gui_transmitir.py:79)",
    ("ui", "filtro_activo"): "lo cambia el menú de filtros (gui.py:1309)",
    ("ui", "silenciar_sonidos"): "lo cambia F7 en la ventana principal (gui.py:1332)",
}

# Pares que se leen fuera de `config.py`: dónde se lee cada uno.
LEIDAS_FUERA = {
    ("ia", "direccion"): "la lee ajustes_ia.leer (ajustes_ia.py:93)",
    ("ia", "largo"): "la lee ajustes_ia.leer (ajustes_ia.py:95)",
    ("ia", "modelo"): "la lee ajustes_ia.leer (ajustes_ia.py:92)",
    ("ia", "pregunta"): "la lee ajustes_ia.leer (ajustes_ia.py:88)",
    ("ia", "privacidad_aceptada"): "la lee ajustes_ia.leer (ajustes_ia.py:99)",
    ("ia", "proveedor"): "la lee ajustes_ia.leer (ajustes_ia.py:91)",
    ("ia", "solo_gratis"): "la lee ajustes_ia.leer (ajustes_ia.py:98)",
    ("ia", "tiempo_espera"): "la lee ajustes_ia.leer (ajustes_ia.py:97)",
    ("sesion", "version_atajos"): "la lee y la escribe la migración de atajos (atajos.py:294 y 303)",
}

# Pares sin control a propósito que solo migran configuraciones viejas.
MIGRACION = {
    ("musica", "decir_titulo"): "solo para migrar configuraciones viejas a [musica] decir (musica_decir.desde_ini, leída en config.py:622)",
    ("musica", "incluir_artista"): "solo para migrar configuraciones viejas a [musica] decir (musica_decir.desde_ini, leída en config.py:622)",
}

_LECTORAS_CONFIG = {"_gs", "_pb", "_pi", "_pf"}
_LECTORAS_PARSER = {"get", "getboolean", "getint", "has_option"}


def _pares_leidos_en_config():
    """Pares (sección, clave) leídos en `config.py`: llamadas `_gs`, `_pb`,
    `_pi`, `_pf` (literales en 2.º y 3.º lugar) y parecidas del parser
    (`get`, `getboolean`, ...) con literales en 1.º y 2.º lugar."""
    leidos = set()
    for nodo in ast.walk(_arbol("ytchat/core/config.py")):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        if (isinstance(funcion, ast.Name)
                and funcion.id in _LECTORAS_CONFIG):
            invocados = nodo.args[1:3]
        elif (isinstance(funcion, ast.Attribute)
                and funcion.attr in _LECTORAS_PARSER):
            invocados = nodo.args[0:2]
        else:
            continue
        if (len(invocados) >= 2 and _es_texto(invocados[0])
                and _es_texto(invocados[1])):
            leidos.add((invocados[0].value, invocados[1].value))
    return leidos


def _filas_de_tabla(nodo, tablas):
    """Filas (sección, clave) de una tabla: tupla de filas, suma con `+` o
    nombre de otra tabla (como `OPCIONES_MUSICA` dentro de `_OPCIONES_SIMPLES`)."""
    if (isinstance(nodo, ast.Tuple) and nodo.elts
            and _es_texto(nodo.elts[0])):
        return [(nodo.elts[1].value, nodo.elts[2].value)]
    if isinstance(nodo, ast.Tuple):
        filas = []
        for elemento in nodo.elts:
            filas.extend(_filas_de_tabla(elemento, tablas))
        return filas
    if isinstance(nodo, ast.BinOp):
        return (_filas_de_tabla(nodo.left, tablas)
                + _filas_de_tabla(nodo.right, tablas))
    if isinstance(nodo, ast.Name) and nodo.id in tablas:
        return _filas_de_tabla(tablas[nodo.id], tablas)
    return []


def _pares_con_control():
    """Pares con control en Preferencias: tablas `_OPCIONES_SIMPLES` y
    `OPCIONES_MUSICA`, más llamadas literales `self._set(...)` y
    `guardar_opcion(...)` de esos dos archivos."""
    con_control = set()
    tablas = {}
    arboles = {rel: _arbol(rel) for rel in (
        "ytchat/ui/gui_preferencias.py", "ytchat/ui/preferencias_musica.py")}
    for arbol in arboles.values():
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.Assign, ast.AnnAssign)):
                continue
            destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            for destino in destinos:
                if isinstance(destino, ast.Name) and destino.id in (
                        "_OPCIONES_SIMPLES", "OPCIONES_MUSICA"):
                    tablas[destino.id] = nodo.value
    for tabla in tablas.values():
        con_control.update(_filas_de_tabla(tabla, tablas))
    for arbol in arboles.values():
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Call)
                    and isinstance(nodo.func, ast.Attribute)):
                continue
            if (nodo.func.attr == "_set" and len(nodo.args) >= 2
                    and _es_texto(nodo.args[0]) and _es_texto(nodo.args[1])):
                con_control.add((nodo.args[0].value, nodo.args[1].value))
            if (nodo.func.attr in ("guardar_opcion", "guardar_opciones")
                    and len(nodo.args) >= 3
                    and _es_texto(nodo.args[1]) and _es_texto(nodo.args[2])):
                con_control.add((nodo.args[1].value, nodo.args[2].value))
    return con_control


class PruebaConfiguracion(unittest.TestCase):
    def _pares_fabrica(self):
        return {(sec, clave)
                for sec, claves in fabrica.datos().items()
                for clave in claves
                if sec not in _SECCIONES_CON_REGLA_PROPIA}

    def test_todo_par_se_lee(self):
        faltan = sorted(set(self._pares_fabrica()) - _pares_leidos_en_config()
                        - set(LEIDAS_FUERA))
        self.assertEqual(
            faltan, [],
            "Pares de fábrica que no se leen en ytchat/core/config.py: "
            f"{faltan}")

    def test_todo_par_tiene_control(self):
        faltan = sorted(set(self._pares_fabrica())
                        - _pares_con_control() - set(INTERNAS) - set(MIGRACION))
        self.assertEqual(
            faltan, [],
            "Pares de fábrica sin control en Preferencias "
            "(ytchat/ui/gui_preferencias.py, ytchat/ui/preferencias_musica.py): "
            f"{faltan}")

    def test_excepciones_existen_en_fabrica(self):
        sobran = sorted((set(INTERNAS) | set(MIGRACION) | set(LEIDAS_FUERA))
                        - set(self._pares_fabrica()))
        self.assertEqual(
            sobran, [],
            "Excepciones que sobran (ya no están en la fábrica): "
            f"{sobran}")


# ── Regla 4: atajos ─────────────────────────────────────────────────────────

def _atajos_en_manual():
    """Textos de atajo citados en `MANUAL.md` entre comillas simples.
    Normalización: una fila como "`Ctrl+Alt+Flecha derecha` / `izquierda`"
    trae el segundo tramo abreviado, así que si un tramo no trae `+` hereda
    el prefijo del tramo anterior de la misma línea (todo hasta su última
    palabra: "`Ctrl+Flecha izquierda` / `derecha`" vale por
    "`Ctrl+Flecha derecha`"). Lo mismo vale para "`Ctrl+Flecha arriba` /
    `abajo`" y "`Ctrl+Alt+Flecha derecha` / `izquierda`."""
    vistos = set()
    for linea in (RAIZ / "MANUAL.md").read_text(encoding="utf-8").splitlines():
        anterior = ""
        for tramo in re.findall(r"`([^`]+)`", linea):
            tramo = tramo.strip()
            if "+" not in tramo and "+" in anterior:
                tramo = re.sub(r"[^+ ]+$", "", anterior) + tramo
            vistos.add(tramo)
            anterior = tramo
    return vistos


class PruebaAtajos(unittest.TestCase):
    def test_toda_clave_tiene_nombre(self):
        claves = set(fabrica.seccion("atajos"))
        faltan = sorted(claves - set(atajos_captura.ETIQUETAS))
        self.assertEqual(
            faltan, [],
            "Claves de [atajos] sin nombre en la tabla de "
            f"ytchat/ui/atajos_captura.py: {faltan}")

    def test_todo_atajo_figura_en_manual(self):
        manual = _atajos_en_manual()
        faltan = []
        for clave in sorted(fabrica.seccion("atajos")):
            legible = atajos_captura.atajo_legible(fabrica.obtener("atajos", clave))
            if legible and legible not in manual:
                faltan.append(f"{clave} ({legible})")
        self.assertEqual(
            faltan, [],
            "Atajos de fábrica que no figuran en MANUAL.md: " + ", ".join(faltan))


# ── Regla 5: solo lectura con Tab ─────────────────────────────────────────


def _solo_lectura_sin_tab():
    """Llamadas a `wx.TextCtrl(...)` en `ytchat/` y `main.py` cuyo `style=`
    nombra `TE_READONLY` sin `TE_MULTILINE`: wx en Windows deja esos campos
    de una línea fuera del orden de Tab. Devuelve "archivo:línea"."""
    problemas = []
    archivos = sorted((RAIZ / "ytchat").rglob("*.py")) + [RAIZ / "main.py"]
    for ruta in archivos:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        relativo = str(ruta.relative_to(RAIZ))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            if _ruta_punteada(nodo.func).rsplit(".", 1)[-1] != "TextCtrl":
                continue
            for palabra in nodo.keywords:
                if palabra.arg != "style":
                    continue
                usados = {n.attr for n in ast.walk(palabra.value)
                          if isinstance(n, ast.Attribute)}
                if ("TE_READONLY" in usados
                        and "TE_MULTILINE" not in usados):
                    problemas.append(f"{relativo}:{nodo.lineno}")
    return sorted(problemas)


class PruebaSoloLecturaConTab(unittest.TestCase):
    def test_ningun_solo_lectura_fuera_del_tab(self):
        problemas = _solo_lectura_sin_tab()
        self.assertEqual(
            problemas, [],
            "TextCtrl de solo lectura de una línea (fuera del Tab en "
            "Windows, usar wx.TE_MULTILINE | wx.TE_READONLY): "
            + ", ".join(problemas))


if __name__ == "__main__":
    unittest.main()

"""Prueba real de la IA de punta a punta, para correr a mano.

Arma la escena conocida en OBS, pregunta con Ctrl+Mayús+F2 y en la
ventana, comprueba cada respuesta y deja todo en qa/salida/ia-real.txt.
No corre en la suite: `python qa/ia_real.py` en la PC donde nadie está.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

import directo_real
from ytchat.core.config import APP_NAME  # noqa: E402
from conducir import contestar_salir_si_aparece

TITULO_PRIVACIDAD = "Privacidad"
PREGUNTA_RAPIDA = "(consulta rápida con la instrucción de Preferencias)"
PREGUNTA_VENTANAS = "¿Cuántas ventanas de color se ven y dónde está cada una?"
PREGUNTA_PANEL = "¿Qué texto se lee en el panel de chat?"
PREGUNTA_CAMBIO = "¿Cambió algo respecto de la captura anterior?"

def _sin_tildes(texto) -> str:
    """Minúsculas sin tildes, para comparar sin importar el acento."""
    base = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(x for x in base if unicodedata.category(x) != "Mn").lower()

def nombra_colores(texto) -> bool:
    """Si nombra al menos uno de los colores de las ventanas de prueba."""
    base = _sin_tildes(texto)
    return any(c in base for c in ("verde", "magenta", "fucsia", "rosa",
                                   "violeta", "morado"))

def tiene_dos(texto) -> bool:
    """Si dice dos ventanas: «dos» en letras o «2» solo, sin contar 12."""
    base = _sin_tildes(texto)
    return (re.search(r"\bdos\b", base) is not None
            or re.search(r"(?<!\d)2(?!\d)", base) is not None)

_ERRORES = None

def _textos_error() -> tuple:
    """Frases de `consulta` que anuncian una falla, para comparar."""
    global _ERRORES
    if _ERRORES is None:
        from ytchat.ai import consulta
        dic = getattr(consulta, "_TEXTOS", getattr(consulta, "_ERRORES", None))
        lista = list(dic.values()) if isinstance(dic, dict) else []
        lista.extend(getattr(consulta, n, "") for n in
                     ("TEXTO_SIN_NIVEL_GRATUITO", "_MSG_PROVEEDOR",
                      "_MSG_MODELO", "_MSG_DIRECCION"))
        lista.extend(("Agrega una captura antes de preguntar.",
                      "Escribe una pregunta.",
                      "No se pudo completar la consulta. Vuelve a intentarlo.",
                      "Falta la clave de"))
        _ERRORES = tuple(str(f) for f in lista if f)
    return _ERRORES

def es_error(texto) -> bool:
    """Si el anuncio es una falla de la consulta, no una respuesta."""
    base = _sin_tildes(texto)
    return bool(base.strip()) and any(
        p and p in base for p in map(_sin_tildes, _textos_error()))

def modelo_permitido(proveedor, modelo) -> bool:
    """OpenRouter solo usa gratis («:free»); el resto vale todo."""
    otro = (proveedor or "").strip().lower() != "openrouter"
    return otro or (modelo or "").strip().lower().endswith(":free")

def informe(pasos, proveedor, modelo) -> str:
    """El contenido de qa/salida/ia-real.txt. La clave nunca llega acá."""
    lineas = ["Prueba de IA - {}".format(time.strftime("%Y-%m-%d %H:%M")),
              "Proveedor: {}".format((proveedor or "").strip()),
              "Modelo: {}".format((modelo or "").strip()), ""]
    fallos = total = 0
    for nombre, pregunta, respuesta, segundos, bien in pasos or ():
        total += 1
        fallos += 0 if bien else 1
        lineas.append("Paso {} - {}: {} ({} s)".format(
            total, nombre, "pasó" if bien else "falló", segundos))
        lineas.append("Pregunta: {}".format(pregunta))
        lineas.append("Respuesta: {}".format(respuesta))
        lineas.append("")
    lineas.append("Resumen: {} pasos, {} fallo{}.".format(
        total, fallos, "" if fallos == 1 else "s"))
    return "\n".join(lineas) + "\n"

# -- Impuro: archivos, procesos, UI Automation y OBS. Fuera de las pruebas. --

def _config():
    """(proveedor, modelo, espera, problema): lo que hay, sin la clave."""
    from ytchat.ai import ajustes_ia, claves
    from ytchat.core import paths
    try:
        aj = ajustes_ia.leer(paths.config_ini())
        prov, mod = (aj.proveedor or "").strip(), (aj.modelo or "").strip()
        if not prov:
            raise ValueError("sin proveedor en Preferencias")
        if not mod:
            raise ValueError("sin modelo en Preferencias")
        if not (claves.leer(prov) or "").strip():
            raise ValueError("sin clave de {} en Preferencias".format(prov))
    except Exception as f:
        return ("", "", 60, str(f))
    return (prov, mod, aj.tiempo_espera, "")

def _nueva(ruta, marca, segundos) -> str:
    """El último anuncio nuevo que no es de espera, o cadena vacía."""
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            with open(ruta, encoding="utf-8") as f:
                lineas = f.read()[marca:].splitlines()
        except OSError:
            lineas = []
        for linea in reversed(lineas):
            texto = re.sub(r"^\d\d:\d\d:\d\d\s+", "", linea or "").strip()
            if texto and "analizando" not in _sin_tildes(texto):
                return texto
        time.sleep(1)
    return ""

def _sin_privacidad(principal, segundos):
    """(salió, detalle): si sale el aviso lo cierra con No, sin aceptar."""
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            aviso = directo_real._control(principal, TITULO_PRIVACIDAD, "Window", 2)
        except Exception:
            continue
        try:
            directo_real._control(aviso, "No", "Button", 10).invoke()
            return (True, "")
        except Exception as f:
            return (True, "salió y no se pudo cerrar ({})".format(f))
    return (False, "")

def _consultar(ctx, pregunta, espera, rapida=False, ventana=None,
               comprueba=None, mala=""):
    """Una consulta: con teclas si es rápida, con valor si hay ventana."""
    from pywinauto import keyboard
    from ytchat.ai import ventana_ia
    inicio = time.time()
    try:
        ctx["principal"].set_focus()
        time.sleep(1)
        marca = len(directo_real._leer_anuncios(ctx["anuncios"]))
        if rapida:
            keyboard.send_keys("^+{F2}")
        else:
            cuadro = directo_real._control(ventana, "Mensaje", "Edit", 20)
            puesto = [m for m in (getattr(cuadro, n, None)
                                  for n in ("set_edit_text", "set_value"))
                      if callable(m)]
            if not puesto:
                raise RuntimeError("sin patrón de valor")
            puesto[0](pregunta)
            directo_real._control(ventana, "Enviar", "Button", 20).invoke()
    except Exception as f:
        return (False, "", 0, "no se pudo pedir ({})".format(f))
    if _sin_privacidad(ctx["principal"], 10)[0]:
        nota = "hay que aceptar el aviso de privacidad una vez a mano"
        return (False, "", int(time.time() - inicio), nota)
    respuesta = _nueva(ctx["anuncios"], marca, 120 if rapida else espera)
    if not respuesta and ventana is not None:
        try:
            lista = directo_real._control(ventana, "Conversación", "List", 10)
            fila = [str(t or "").strip() for t in lista.texts()]
            fila = [t for t in fila if t and t != ventana_ia.FILA_GUIA]
            respuesta = fila[-1] if fila else ""
        except Exception:
            respuesta = ""
    segundos = int(time.time() - inicio)
    if not respuesta:
        return (False, "", segundos, "sin respuesta en {} s".format(segundos))
    if es_error(respuesta):
        return (False, "", segundos, "la app anunció una falla: {}".format(
            respuesta))
    if comprueba is not None and not comprueba(respuesta):
        return (False, "", segundos, "{}: {}".format(mala or "no pasó",
                                                     respuesta))
    return (True, respuesta, segundos, respuesta)

def _capturar(ctx, ventana, espera):
    """«Agregar captura», primera opción y tercera pregunta."""
    try:
        directo_real._control(ventana, "Agregar captura", "Button", 20).invoke()
        dialogo = directo_real._dialogo_hijo(ventana, "Agregar captura", 20)
        combo = directo_real._control(dialogo, "Capturar de", "ComboBox", 30)
        boton = directo_real._control(dialogo, "Capturar", "Button", 10)
    except Exception as f:
        return (False, "", 0, "no abrió la lista ({})".format(f))
    fin = time.time() + 30
    while time.time() < fin:
        try:
            if boton.is_enabled():
                break
        except Exception:
            break
        time.sleep(0.5)
    marca = len(directo_real._leer_anuncios(ctx["anuncios"]))
    try:
        combo.select(0)
        boton.invoke()
    except Exception as f:
        return (False, "", 0, "no se pudo capturar ({})".format(f))
    if not _nueva(ctx["anuncios"], marca, 15):
        return (False, "", 0, "sin «Captura agregada»")
    return _consultar(ctx, PREGUNTA_CAMBIO, espera, ventana=ventana)

def _obs():
    """Abre OBS como lo abre la app si no corre. (estaba, problema)."""
    from ytchat.obs import obs_lanzador
    from ytchat.obs.obs_panel import GestorPanelObs
    if directo_real._obs_en_ejecucion():
        return (True, "")
    gestor = GestorPanelObs()
    try:
        obs_lanzador.asegurar_obs(gestor.conectar)
    except Exception as f:
        return (False, "OBS no quedó disponible ({})".format(f))
    finally:
        gestor.cerrar()
    return (False, "")

def _levantar(ctx) -> str:
    """Lanza la app, abre OBS y arma la escena. "" si salió bien."""
    from ytchat.core import paths
    tmpdir = tempfile.mkdtemp(prefix="ia-real-")
    ctx["anuncios"] = os.path.join(tmpdir, "anuncios.txt")
    entorno = dict(os.environ, DIRECTO_REAL_ANUNCIOS=ctx["anuncios"],
                   DIRECTO_REAL_CHAT=os.path.join(tmpdir, "chat.txt"))
    try:
        open(ctx["anuncios"], "w").close()
        open(entorno["DIRECTO_REAL_CHAT"], "w").close()
        with open(os.path.join(tmpdir, "app.py"), "w",
                  encoding="utf-8") as f:
            f.write(directo_real._LANZADOR.format(repo=str(RAIZ)))
        ctx["ventanas"] = directo_real._abrir_ventanas_prueba()
        ctx["app"] = subprocess.Popen(
            [sys.executable, os.path.join(tmpdir, "app.py")],
            cwd=str(RAIZ), env=entorno)
        ctx["principal"] = directo_real._ventana(APP_NAME, 60)
        time.sleep(4)
    except Exception as f:
        return "sin app ({})".format(f)
    ctx["estaba_obs"], problema = _obs()
    if problema:
        return problema
    try:
        ctx["gestor"] = directo_real._gestor_obs()
        url = "http://127.0.0.1:{}/chat".format(
            directo_real._puerto_panel(paths.config_ini()))
        ctx["escena"], ctx["creo_panel"] = (
            directo_real._armar_escena_prueba(ctx["gestor"], url))
    except Exception as f:
        return "sin escena ({})".format(f)
    return ""

def _limpiar(ctx) -> list:
    """Desarma la escena, cierra todo y deja OBS como estaba."""
    notas = []
    escena, gestor = ctx.get("escena") or "", ctx.get("gestor")
    if escena and gestor is not None:
        for fuente in (directo_real.FUENTE_CAMARA, directo_real.FUENTE_APLICACION):
            try:
                directo_real._quitar_fuente(gestor, escena, fuente,
                                            borrar_entrada=True)
            except Exception as f:
                notas.append("sin quitar {} ({})".format(fuente, f))
        if ctx.get("creo_panel"):
            try:
                from ytchat.obs.obs_panel import NOMBRE_FUENTE
                directo_real._quitar_fuente(gestor, escena, NOMBRE_FUENTE)
            except Exception as f:
                notas.append("sin quitar el panel ({})".format(f))
    try:
        directo_real._cerrar_ventanas_prueba(ctx.get("ventanas") or ())
        notas.append("ventanas de prueba cerradas")
    except Exception as f:
        notas.append("sin cerrar las ventanas ({})".format(f))
    try:
        if ctx.get("principal") is not None:
            ctx["principal"].close()
            contestar_salir_si_aparece(segundos=8.0)
            time.sleep(8)
        if ctx.get("app") is not None and ctx["app"].poll() is None:
            ctx["app"].kill()
    except Exception as f:
        notas.append("sin cerrar la app ({})".format(f))
    try:
        if gestor is not None:
            gestor.cerrar()
        if not ctx.get("estaba_obs", True) and directo_real._obs_en_ejecucion():
            directo_real._cerrar_obs()
            notas.append("OBS cerrado")
    except Exception as f:
        notas.append("sin dejar OBS como estaba ({})".format(f))
    return notas

def _recorrer(ctx, pasos, espera) -> tuple[list, int]:
    """Los cinco pasos sobre la app ya armada. (pasos, código)."""
    from pywinauto import keyboard
    problema = _levantar(ctx)
    if problema:
        pasos.append(("preparar escena", "", problema, 0, False))
        return (pasos, 1)
    bien, respuesta, segundos, nota = _consultar(
        ctx, PREGUNTA_RAPIDA, espera, rapida=True, comprueba=nombra_colores,
        mala="no nombra los colores")
    pasos.append(("Consulta rápida", PREGUNTA_RAPIDA,
                  respuesta if bien else nota, segundos, bien))
    if not bien:
        return (pasos, 1)
    try:
        ctx["principal"].set_focus()
        time.sleep(1)
        keyboard.send_keys("^+i")
        ventana = directo_real._dialogo_hijo(
            ctx["principal"], "Preguntar a la IA", 30)
    except Exception as f:
        pasos.append(("abrir Preguntar a la IA", "",
                      "no abrió «Preguntar a la IA» ({})".format(f), 0, False))
        return (pasos, 1)
    for nombre, pregunta, comprueba, mala in (
            ("Pregunta por las ventanas", PREGUNTA_VENTANAS, tiene_dos,
             "no dice cuántas ventanas"),
            ("Pregunta por el panel", PREGUNTA_PANEL, None, "")):
        bien, respuesta, segundos, nota = _consultar(
            ctx, pregunta, espera, ventana=ventana, comprueba=comprueba,
            mala=mala)
        pasos.append((nombre, pregunta, respuesta if bien else nota,
                      segundos, bien))
        if not bien:
            return (pasos, 1)
    bien, respuesta, segundos, nota = _capturar(ctx, ventana, espera)
    pasos.append(("Agregar captura y preguntar", PREGUNTA_CAMBIO,
                  respuesta if bien else nota, segundos, bien))
    if not bien:
        return (pasos, 1)
    try:
        directo_real._control(ventana, "Cerrar", "Button", 10).invoke()
    except Exception as f:
        pasos.append(("Cerrar", "(sin pregunta)",
                      "sin «Cerrar» ({})".format(f), 0, False))
        return (pasos, 1)
    pasos.append(("Cerrar", "(sin pregunta)", "ventana cerrada", 0, True))
    return (pasos, 0)

def _correr() -> tuple[list, int]:
    """Verifica, recorre, guarda qa/salida/ia-real.txt y dice el código."""
    proveedor, modelo, espera, problema = _config()
    if problema or not modelo_permitido(proveedor, modelo):
        texto = problema or "OpenRouter solo usa modelos gratis (:free)."
        print(texto)
        nombre = "configuración de IA" if problema else "modelo admitido"
        return ([(nombre, "", texto, 0, False)], 2)
    ctx = {"anuncios": "", "ventanas": (), "app": None, "principal": None,
           "gestor": None, "escena": "", "creo_panel": False,
           "estaba_obs": True}
    pasos: list = []
    try:
        try:
            return _recorrer(ctx, pasos, espera + 60)
        except Exception as f:
            pasos.append(("corrida", "", "falló la herramienta ({})".format(
                f), 0, False))
            return (pasos, 1)
    finally:
        notas = _limpiar(ctx)
        texto = informe(pasos, proveedor, modelo)
        try:
            destino = RAIZ / "qa" / "salida"
            destino.mkdir(parents=True, exist_ok=True)
            (destino / "ia-real.txt").write_text(texto, encoding="utf-8")
        except OSError as f:
            print("no se pudo guardar la salida ({})".format(f))
        print(texto)
        for nota in notas:
            print(nota)

def main(argv: list | None = None) -> int:
    argparse.ArgumentParser(
        description="Prueba real de la IA con app y OBS de verdad. Manda "
                    "teclas y gasta consultas: solo escritorio real.").parse_args(argv)
    _, codigo = _correr()
    return codigo

if __name__ == "__main__":
    sys.exit(main())

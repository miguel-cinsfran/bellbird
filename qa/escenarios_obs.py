"""Escenarios de OBS: transmisión, escena, grabación, encuadre y Restream."""

from __future__ import annotations

import glob
import os
import subprocess
import tempfile
import time
from pathlib import Path

from banco_app import Aplicacion, RAIZ, Resultado, VentanaNoActiva
from banco_auditoria import (
    VUELTAS_TAB_TRANSMISION, auditar_dialogo, faltan_habilitados,
    recorrer_tab, revisar_nombres,
)

import ventanas_obs  # noqa: E402

def escenario_restream(app: Aplicacion, args, res: Resultado):
    """La ventana de Restream: la pestaña por defecto y la de la cuenta.

    Primero se audita la pestaña que abre sola, y después la de la cuenta,
    elegida con la orden `pestanas`. Los controles de una pestaña que no está
    seleccionada no existen para el servicio de accesibilidad de Windows.
    """
    auditar_dialogo(app, res, "Transmisión > Restream…", "Restream",
                    vueltas_tab=12)
    esperados = ("Estado de la cuenta", "Conectar", "Cerrar")
    auditar_dialogo(app, res, "Transmisión > Restream…", "Restream",
                    vueltas_tab=12, esperados=esperados,
                    esperados_en_tab=esperados, pestana="Cuenta")


def obs_abierto() -> bool:
    """¿Hay un proceso `obs64.exe` corriendo? Falso ante cualquier error."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW)
        return "obs64.exe" in (r.stdout or "").lower()
    except Exception:
        return False


def limpiar_sentinel_obs() -> int:
    """Borra los restos de cierres forzados para que OBS no pida modo seguro.

    Copiada de `qa/directo_real.py` y no importada de ahí: los dos scripts se
    corren sueltos y no se conocen entre sí.
    """
    base = os.environ.get("APPDATA", "")
    if not base:
        return 0
    borrados = 0
    for resto in glob.glob(os.path.join(
            base, "obs-studio", ".sentinel", "run_*")):
        try:
            os.remove(resto)
            borrados += 1
        except OSError:
            pass
    return borrados


def debe_cerrar_obs_al_final(estaba_al_empezar: bool,
                             abierto_ahora: bool) -> bool:
    """El banco cierra el OBS que abrió él, no el que ya estaba ni nada si no hay."""
    return not estaba_al_empezar and abierto_ahora


def cerrar_obs_del_banco(res: Resultado) -> None:
    """Cierra el OBS que quedó abierto y limpia la marca de modo seguro.

    `taskkill` sin `/F` primero: si OBS puede cerrarse solo, lo hace limpio y
    deja el estado de una corrida normal. Forzarlo hace que la próxima vez
    arranque en modo seguro, y eso se desactiva borrando el `run_*` que deja
    en `.sentinel`.
    """
    try:
        subprocess.run(["taskkill", "/IM", "obs64.exe"],
                       capture_output=True, timeout=30)
    except Exception:
        pass
    time.sleep(5)
    forzado = False
    if obs_abierto():
        forzado = True
        try:
            subprocess.run(["taskkill", "/F", "/IM", "obs64.exe"],
                           capture_output=True, timeout=30)
        except Exception:
            pass
        time.sleep(2)
    if forzado:
        marcas = limpiar_sentinel_obs()
        res.nota("OBS cerrado al terminar el banco "
                 f"(forzado, {marcas} marcas de modo seguro borradas)")
    else:
        res.nota("OBS cerrado al terminar el banco")


def escenario_transmision(app: Aplicacion, args, res: Resultado):
    """La pestaña Transmisión dentro del panel de OBS.

    La abre la app con Ctrl+Mayús+O, que lanza OBS si hace falta, y el final
    del banco cierra el OBS que abrió. Se audita entera, sin pulsar el botón
    del directo ni cambiar nada en OBS.
    """
    ventanas_obs.auditar_transmision(
        app, res, recorrer_tab, revisar_nombres, faltan_habilitados,
        VUELTAS_TAB_TRANSMISION)


def escenario_escena(app: Aplicacion, args, res: Resultado):
    """La ventana que reúne lo que se ve y se oye en OBS.

    La abre la app con Ctrl+Mayús+O y pasa a Escena con Ctrl+Tab. El final del
    banco cierra el OBS que abrió. Se auditan las pestañas, sin pulsar ningún
    botón ni casilla que cambie OBS.
    """
    ventanas_obs.auditar_escena(
        app, res, recorrer_tab, revisar_nombres, faltan_habilitados,
        VUELTAS_TAB_TRANSMISION)


def escenario_grabacion(app: Aplicacion, args, res: Resultado):
    """La pestaña para grabar en OBS sin abrir Transmisión.

    La abre la app con Ctrl+Mayús+O y pasa a Grabación con Ctrl+Tab. El final
    del banco cierra el OBS que abrió. Se audita entera, sin pulsar los botones
    que cambiarían la grabación de la PC.
    """
    ventanas_obs.auditar_grabacion(
        app, res, recorrer_tab, revisar_nombres, faltan_habilitados,
        VUELTAS_TAB_TRANSMISION)


def escenario_microfono(app: Aplicacion, args, res: Resultado):
    """El cuadro para elegir el micrófono de OBS.

    Sin OBS no hay nada que auditar: el cuadro solo se abre si OBS
    responde, sin él la aplicación anuncia el fallo y no se abre. Con OBS
    abierto se audita entero, pero sin pulsar «Aplicar»: el banco no cambia
    el micrófono de OBS de la PC donde corre.
    """
    if not obs_abierto():
        res.nota("Micrófono de OBS: OBS está cerrado, el cuadro no se abre "
                 "y no se audita")
        return
    res.nota("Micrófono de OBS: no se pulsa Aplicar, el banco no cambia "
             "el micrófono de la PC")
    esperados = ("Fuente de OBS", "Dispositivo", "Aplicar", "Cerrar")
    auditar_dialogo(
        app, res, "Elegir micrófono…", "Micrófono de OBS",
        vueltas_tab=8,
        esperados=esperados,
        esperados_en_tab=esperados)


def _bmp_gris(ruta, ancho=160, alto=120, tono=128):
    """Un BMP gris de 24 bits, para tapar el rostro en la prueba."""
    import struct
    fila = bytes([tono, tono, tono]) * ancho
    fila += b"\x00" * ((4 - len(fila) % 4) % 4)
    datos = fila * alto
    cabecera = struct.pack("<2sIHHI", b"BM", 54 + len(datos), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, ancho, alto, 1, 24, 0,
                       len(datos), 0, 0, 0, 0)
    ruta.write_bytes(cabecera + info + datos)


def _quitar_fuente_encuadre(gestor, escena, nombre):
    """Saca la fuente de la escena y borra la entrada, sin reventar."""
    try:
        elementos = gestor._pedir(
            "GetSceneItemList", {"sceneName": escena}).get(
            "sceneItems", ()) or ()
    except Exception:
        return
    for elemento in elementos:
        if elemento.get("sourceName") == nombre \
                and elemento.get("sceneItemId") is not None:
            try:
                gestor._pedir("RemoveSceneItem",
                              {"sceneName": escena,
                               "sceneItemId": elemento.get("sceneItemId")})
            except Exception:
                pass
    try:
        gestor._pedir("RemoveInput", {"inputName": nombre})
    except Exception:
        pass


def _nuevo_anuncio(propia, desde, segundos):
    """El primer anuncio nuevo, o None si no llega a tiempo."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        nuevos = propia.anuncios[desde:]
        if nuevos:
            return nuevos[0].get("texto", "")
        time.sleep(0.2)
    return None


def _frase_final_guia(propia, desde, segundos):
    """Lo que dijo la guía tras el inicio: frase, o None si no terminó."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        for anuncio in propia.anuncios[desde:]:
            texto = anuncio.get("texto", "") or ""
            bajado = texto.lower()
            if not texto or "sigue los pitidos" in bajado:
                continue
            if "guía de encuadre" in bajado and "detenida" in bajado:
                return None
            return texto
        time.sleep(0.2)
    return None


def escenario_encuadre(app: Aplicacion, args, res: Resultado):
    """Ctrl+F3 anuncia el encuadre y los avisos siguen al rostro.

    Monta su propia aplicación con la cámara ya elegida, como
    arranque_frio: la configuración se escribe antes de abrir. Sin OBS
    no hay nada que mirar y se vuelve. La fuente sigue visible todo el
    tiempo: lo que cambia es su archivo, entre la foto de prueba y un
    gris generado en un temporal. Deja OBS y config.ini como los
    encontró.
    """
    from bellbird.core import paths as _rutas
    from bellbird.core.config import guardar_opcion
    if not obs_abierto():
        res.nota("Encuadre: OBS está cerrado, no hay cámara que mirar")
        return
    ruta_config = _rutas.config_ini()
    respaldo = ruta_config.read_bytes() if ruta_config.is_file() else None
    nombre = "Prueba Bellbird encuadre"
    gestor = None
    escena = ""
    temporal = Path(tempfile.mkdtemp(prefix="qa-encuadre-"))
    gris = temporal / "gris.bmp"
    propia = None
    try:
        from bellbird.obs.obs_panel import GestorPanelObs
        gestor = GestorPanelObs()
        try:
            gestor.conectar()
        except Exception as exc:
            res.nota(f"Encuadre: OBS no contestó, {exc}")
            return
        escena = gestor.escena_al_aire()
        if not escena:
            res.nota("Encuadre: OBS no tiene escena al aire")
            return
        _bmp_gris(gris)
        foto = RAIZ / "tests" / "datos" / "rostro.jpg"
        _quitar_fuente_encuadre(gestor, escena, nombre)
        try:
            gestor._pedir("CreateInput",
                          {"sceneName": escena, "inputName": nombre,
                           "inputKind": "image_source",
                           "inputSettings": {"file": str(foto)},
                           "sceneItemEnabled": True})
        except Exception as exc:
            res.fallo(f"Encuadre: no se pudo agregar la fuente, {exc}")
            return
        if not guardar_opcion(ruta_config, "transmision", "camara_fuente",
                              nombre):
            res.fallo("Encuadre: no se pudo fijar la cámara en config.ini")
            return
        propia = Aplicacion(app.anuncios_ruta.parent / "encuadre")
        propia.arrancar()
        if not propia.esperar_lista(segundos=60):
            res.fallo("Encuadre: la aplicación no contestó al ping en 60 s")
            return
        try:
            antes = len(propia.anuncios)
            propia.teclas(("f3", ["ctrl"]))
        except VentanaNoActiva as exc:
            res.no_probado(f"Encuadre: no se pudo pulsar Ctrl+F3, {exc}")
            return
        dicho = _nuevo_anuncio(propia, antes, segundos=20.0)
        if dicho is None:
            res.fallo("Encuadre: Ctrl+F3 no anunció nada")
            return
        if "ningún rostro" in dicho.lower():
            res.fallo(f"Encuadre: Ctrl+F3 anunció «{dicho}» "
                      "con el rostro a la vista")
            return
        res.nota(f"Encuadre: Ctrl+F3 anunció «{dicho}»")
        try:
            antes = len(propia.anuncios)
            propia.teclas(("f3", ["ctrl", "shift"]))
        except VentanaNoActiva as exc:
            res.no_probado(f"Encuadre: no se pudo activar avisos, {exc}")
            return
        if not propia.esperar_dicho("Avisos de encuadre activados",
                                    segundos=10, desde=antes):
            res.fallo("Encuadre: no se activaron los avisos")
            return
        try:
            gestor._pedir("SetInputSettings",
                          {"inputName": nombre,
                           "inputSettings": {"file": str(gris)}})
        except Exception as exc:
            res.fallo(f"Encuadre: no se pudo tapar el rostro, {exc}")
            return
        antes = len(propia.anuncios)
        if not propia.esperar_dicho("Ningún rostro.", segundos=6,
                                    desde=antes):
            res.fallo("Encuadre: tapado el rostro, no avisó que no hay "
                      "ninguno en 6 s")
            return
        res.nota("Encuadre: tapado el rostro, avisó «Ningún rostro.»")
        try:
            gestor._pedir("SetInputSettings",
                          {"inputName": nombre,
                           "inputSettings": {"file": str(foto)}})
        except Exception as exc:
            res.fallo(f"Encuadre: no se pudo mostrar el rostro, {exc}")
            return
        antes = len(propia.anuncios)
        if not propia.esperar_dicho("Rostro centrado.", segundos=8,
                                    desde=antes):
            res.fallo("Encuadre: vuelto el rostro, no avisó de la vuelta")
        else:
            res.nota("Encuadre: vuelto el rostro, avisó «Rostro centrado.»")
        try:
            antes = len(propia.anuncios)
            propia.teclas(("f3", ["ctrl"]), ("f3", ["ctrl"]))
        except VentanaNoActiva as exc:
            res.no_probado("Encuadre: no se pudo pulsar dos veces Ctrl+F3, "
                           f"{exc}")
        else:
            if not propia.esperar_dicho(
                    "Guía de encuadre. Sigue los pitidos.",
                    segundos=10, desde=antes):
                res.nota("Encuadre: la doble pulsación no inició la guía")
            else:
                frase = _frase_final_guia(propia, len(propia.anuncios),
                                          segundos=10.0)
                if frase is None:
                    res.nota("Encuadre: la guía no terminó sola en 10 s")
                    try:
                        propia.teclas(("f3", ["ctrl"]))
                    except VentanaNoActiva as exc:
                        res.no_probado("Encuadre: no se pudo detener la guía, "
                                       f"{exc}")
                else:
                    res.nota(f"Encuadre: la guía terminó sola: «{frase}»")
    finally:
        if propia is not None:
            propia.cerrar()
        if respaldo is not None:
            try:
                ruta_config.write_bytes(respaldo)
            except Exception as exc:
                res.fallo(f"Encuadre: no se pudo restaurar config.ini, {exc}")
        if gestor is not None:
            _quitar_fuente_encuadre(gestor, escena, nombre)
            try:
                gestor.cerrar()
            except Exception:
                pass
        import shutil
        shutil.rmtree(temporal, ignore_errors=True)


def _destino_guardado_en_disco() -> str:
    """El destino de transmisión que guarda el `config.ini`, o cadena vacía."""
    import configparser
    try:
        from bellbird.core import paths
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(paths.config_ini(), encoding="utf-8")
        return parser.get("transmision", "destino", fallback="").strip()
    except Exception:
        return ""


def escenario_transmitir_destino(app: Aplicacion, args, res: Resultado):
    """El camino a «Transmitir a» y al «Directo de YouTube», sin crear nada.

    Se abre por el mismo botón que usa la aplicación, no por menú: ese
    diálogo no cuelga de ningún menú. Primero se audita y se cancela, y
    después se vuelve con YouTube elegido para llegar al segundo diálogo.

    NUNCA se pulsa «Transmitir»: eso crearía un directo real. Si el segundo
    diálogo no aparece porque no hay sesión de Google, se anota y no cuenta
    como fallo: eso no lo decide el código.
    """
    app.pedir("frente")

    # El botón solo se ve desconectado. Si se llega conectado, el escenario
    # corre en el lugar equivocado de la corrida, igual que le pasa a `chat`.
    conectado_ya = any(
        i["habilitado"] for i in app.menus()
        if not i.get("submenu")
        and "desconectar" in (i.get("camino") or "").lower())
    if conectado_ya:
        res.fallo("transmitir_destino: llegué con la aplicación conectada; "
                  "este escenario necesita el botón «Transmitir en directo», "
                  "que solo se ve desconectado")
        return

    boton = next((c for c in app.arbol()
                  if (c.get("nombre") or "") == "Transmitir en directo"), None)
    if boton is None:
        res.fallo("transmitir_destino: no hay botón «Transmitir en directo» "
                  "en el árbol")
        return
    if not boton.get("visible") or not boton.get("habilitado"):
        res.fallo("transmitir_destino: el botón «Transmitir en directo» está "
                  "oculto o deshabilitado")
        return

    # 1. Abrir, auditar y cancelar: no se abre nada más.
    try:
        app.pedir("pulsar", nombre="Transmitir en directo", tiempo=3.0,
                  responder_ya=True)
    except Exception:
        pass  # el diálogo es modal y se come la respuesta, como en `conectar`
    if app.esperar_ventana("Transmitir a", segundos=15) is None:
        res.fallo("transmitir_destino: el botón no abrió «Transmitir a»")
        return
    res.nota("«Transmitir a» abre desde el botón «Transmitir en directo»")

    controles = app.arbol("Transmitir a")
    revisar_nombres(controles, res, "Transmitir a")
    juntos = " ".join(
        ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        for c in controles).replace("&", "").lower()
    for e in ("Transmitir a", "Continuar", "Cancelar"):
        if e.lower() not in juntos:
            res.fallo(f"Transmitir a: no aparece nada llamado «{e}»")
    orden = recorrer_tab(app, res, "Transmitir a", vueltas=10,
                         ventana="Transmitir a")
    res.nota("Transmitir a, orden de Tab, %d paradas: %s"
             % (len(orden), " > ".join(orden)))

    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Cancelar")
    if app.esperar_ventana("Transmitir a", segundos=4) is not None:
        res.fallo("transmitir_destino: «Transmitir a» no cerró con «Cancelar»")
        return
    if app.dijo("No se transmitió", desde=n):
        res.nota("transmitir_destino: «Cancelar» anuncia que no se transmitió")
    else:
        res.fallo("transmitir_destino: «Cancelar» no anunció nada")
    if app.esperar_ventana("Directo de YouTube", segundos=3) is not None:
        res.fallo("transmitir_destino: tras «Cancelar» se abrió algo más")

    # 2. Con YouTube elegido, «Continuar» lleva al «Directo de YouTube».
    # Pulsar «Continuar» guarda el destino en la configuración, así que se
    # respalda antes y se restaura en un `finally`, como hace `directo_real`.
    # La lista se cambia por teclado: escribir la inicial salta a la primera
    # coincidencia, y la Y solo la tiene YouTube.
    previo = _destino_guardado_en_disco()
    estaba_obs = obs_abierto()
    try:
        try:
            app.pedir("pulsar", nombre="Transmitir en directo", tiempo=3.0,
                      responder_ya=True)
        except Exception:
            pass  # modal otra vez: la respuesta llega cuando se cierre
        if app.esperar_ventana("Transmitir a", segundos=15) is None:
            res.fallo("transmitir_destino: al abrir por segunda vez no "
                      "apareció «Transmitir a»")
            return
        try:
            app.pedir("foco", ventana="Transmitir a", nombre="Transmitir a")
        except Exception as exc:
            res.fallo(f"transmitir_destino: no se llega a la lista, {exc}")
            app.pedir("cerrar_ventana", ventana="Transmitir a")
            return
        try:
            app.teclas("y")
        except VentanaNoActiva as exc:
            res.no_probado(f"transmitir_destino: no se pudo elegir YouTube, "
                           f"{exc}")
            app.pedir("cerrar_ventana", ventana="Transmitir a")
            return
        time.sleep(0.5)

        n = len(app.anuncios)
        app.pedir("pulsar", nombre="Continuar")
        if app.esperar_ventana("Transmitir a", segundos=5) is not None:
            if app.dijo("Falta el usuario", desde=n):
                res.fallo("transmitir_destino: la lista no quedó en YouTube, "
                          "sigue pidiendo el usuario de TikTok")
            else:
                res.fallo("transmitir_destino: «Continuar» no cerró el diálogo")
            app.pedir("cerrar_ventana", ventana="Transmitir a")
            return
        if app.dijo("Revisando OBS", desde=n):
            res.nota("transmitir_destino: «Continuar» pasa a revisar OBS")

        # La revisión de OBS corre en un hilo: el diálogo tarda lo que tarde.
        # Se espera a cualquiera de los tres finales: el diálogo de YouTube,
        # el de confirmación de TikTok (la lista no era YouTube), o un anuncio
        # que explique por qué no hay diálogo (sin sesión, sin OBS, o ya al
        # aire, que también vale: no se interfiere con lo que ya emite).
        motivo = ""
        limite = time.time() + 120
        while time.time() < limite:
            try:
                visibles = [v.get("titulo") or "" for v in app.ventanas()]
            except Exception:
                visibles = []
            if any("Directo de YouTube" in t for t in visibles):
                break
            if any(t.strip() == "Panel de OBS" for t in visibles):
                motivo = "tiktok"
                break
            dichos = " ".join(a.get("texto", "") for a in app.anuncios[n:])
            dichos = dichos.lower()
            if "sesión" in dichos or "sesion" in dichos:
                motivo = "sesion"
                break
            if "ya está transmitiendo" in dichos:
                motivo = "emitiendo"
                break
            if ("no se pudo" in dichos or "rechazó" in dichos
                    or "no encuentra" in dichos or "no pudo" in dichos
                    or "error" in dichos):
                motivo = "obs"
                break
            time.sleep(1.0)

        if motivo == "tiktok":
            res.fallo("transmitir_destino: «Continuar» llevó al Panel de OBS, "
                      "o sea que el destino no era YouTube")
            app.pedir("cerrar_ventana", ventana="Panel de OBS")
            return
        if motivo in ("sesion", "emitiendo", "obs"):
            porques = {
                "sesion": "no hay sesión de Google iniciada",
                "emitiendo": "OBS ya está transmitiendo",
                "obs": "OBS no está disponible o falló la revisión",
            }
            res.nota("transmitir_destino: «Directo de YouTube» no apareció, "
                     + porques[motivo] + "; no cuenta como fallo")
            return
        if app.esperar_ventana("Directo de YouTube", segundos=2) is None:
            dichos = " ".join(a.get("texto", "") for a in app.anuncios[n:])
            res.fallo("transmitir_destino: «Directo de YouTube» no apareció "
                      f"en 120 s; dijo «{dichos[:120]}»")
            return

        controles = app.arbol("Directo de YouTube")
        revisar_nombres(controles, res, "Directo de YouTube")
        juntos = " ".join(
            ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
            for c in controles).replace("&", "").lower()
        for e in ("Título del directo", "Descripción del directo",
                  "Privacidad", "Revisión de OBS", "Transmitir", "Cancelar"):
            if e.lower() not in juntos:
                res.fallo(f"Directo de YouTube: no aparece nada llamado "
                          f"«{e}»")
        orden = recorrer_tab(app, res, "Directo de YouTube", vueltas=14,
                             ventana="Directo de YouTube")
        res.nota("Directo de YouTube, orden de Tab, %d paradas: %s"
                 % (len(orden), " > ".join(orden)))
        # Se cierra con «Cancelar»: pulsar «Transmitir» crearía un directo.
        app.pedir("cerrar_ventana", ventana="Directo de YouTube")
        if app.esperar_ventana("Directo de YouTube", segundos=4) is not None:
            res.fallo("transmitir_destino: «Directo de YouTube» no cerró")
    finally:
        try:
            from bellbird.core import paths
            from bellbird.core.config import guardar_opcion
            guardar_opcion(paths.config_ini(), "transmision", "destino",
                           previo)
        except Exception as exc:
            res.nota("transmitir_destino: no se pudo restaurar el destino "
                     f"guardado ({exc})")
        else:
            res.nota("transmitir_destino: el destino guardado vuelve a "
                     f"«{previo or 'vacío'}»")
        # Si la revisión abrió OBS y no estaba, se lo cierra: el banco no
        # puede dejarle al dueño una aplicación abierta que no tenía.
        if not estaba_obs and obs_abierto():
            res.nota("transmitir_destino: la revisión abrió OBS y no estaba, "
                     "se lo cierra")
            import subprocess
            try:
                subprocess.run(["taskkill", "/IM", "obs64.exe"],
                               capture_output=True, timeout=30)
                time.sleep(5)
                if obs_abierto():
                    subprocess.run(["taskkill", "/F", "/IM", "obs64.exe"],
                                   capture_output=True, timeout=30)
            except Exception as exc:
                res.nota("transmitir_destino: no se pudo cerrar OBS "
                         f"({exc})")


def escenario_overlay(app: Aplicacion, args, res: Resultado):
    """El panel de chat para transmitir: interruptor, servicio y estado.

    La fase 3 de `scripts/smoke_test.py` no llega a este diálogo, y las pruebas unitarias no arrancan la aplicación entera, que es donde se ve si el interruptor está cableado de verdad.

    Comprueba lo único que el dueño no puede mirar: que cuando dice que está
    activo, esté sirviendo la página de verdad.
    """
    import urllib.request

    etiqueta = "Mostrar chat en el vídeo"
    puerto = 8730
    url = f"http://127.0.0.1:{puerto}/chat"

    def responde(tiempo=4.0):
        try:
            with urllib.request.urlopen(url, timeout=tiempo) as r:
                return r.status == 200 and len(r.read()) > 0
        except Exception:
            return False

    def alternar_panel():
        try:
            app.abrir_por_menu("OBS > Panel de OBS…")
        except Exception as exc:
            res.fallo(f"Panel de OBS: no se pudo abrir el panel, {exc}")
            return False
        if app.esperar_ventana("Panel de OBS", segundos=15) is None:
            res.fallo("Panel de OBS: el menú no abrió el panel")
            return False
        if not ventanas_obs.esperar_habilitado(
                app, faltan_habilitados, etiqueta, 15, res):
            app.pedir("cerrar_ventana", ventana="Panel de OBS")
            return False
        try:
            app.pedir("foco", ventana="Panel de OBS", nombre=etiqueta)
            app.teclas("space")
        except Exception as exc:
            res.fallo(f"Panel de OBS: no se pudo alternar «{etiqueta}», {exc}")
            app.pedir("cerrar_ventana", ventana="Panel de OBS")
            return False
        app.pedir("cerrar_ventana", ventana="Panel de OBS")
        return True

    encendido_al_entrar = responde(2.0)
    if encendido_al_entrar:
        res.nota("el panel ya venía encendido; se apaga para probar el ciclo")
        if not alternar_panel():
            return
        app.esperar_dicho("chat en el vídeo desactivado", 8)

    # Encender
    antes = len(app.anuncios)
    if not alternar_panel():
        return
    if not app.esperar_dicho("chat en el vídeo activado", 10, desde=antes):
        dichos = [a["texto"][:60] for a in app.anuncios[antes:]]
        res.fallo(f"al encender no anunció el puerto; dijo: {dichos}")
    if not responde():
        res.fallo(f"anunció el panel activo pero {url} no responde")
    else:
        res.nota(f"{url} responde")

    # F2 distingue si alguien muestra el panel: nadie o fuente en OBS
    antes = len(app.anuncios)
    app.abrir_por_menu("Anunciar estado")
    app.esperar_dicho("chat en el vídeo", 8, desde=antes)
    dicho = " ".join(a["texto"].lower() for a in app.anuncios[antes:])
    if "chat en el vídeo activado" not in dicho:
        res.fallo("F2 no menciona el panel estando encendido")
    elif "nadie lo est" in dicho:
        res.nota("F2 dice que nadie lo está mostrando")
    elif "mostr" in dicho:
        res.nota("F2 dice que el panel se está mostrando")
    else:
        res.fallo("F2 no distingue si alguien está mostrando el panel")

    # Apagar
    antes = len(app.anuncios)
    if not alternar_panel():
        return
    if not app.esperar_dicho("chat en el vídeo desactivado", 10, desde=antes):
        res.fallo("al apagar no lo anunció")
    if responde(3.0):
        res.fallo("apagado, el puerto sigue respondiendo")
    else:
        res.nota("apagado, el puerto deja de responder")

    if encendido_al_entrar:
        alternar_panel()   # se deja como estaba

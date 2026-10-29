"""Tramo de atajos globales de música para la escena `musica_real`.

Con la aplicación ya sonando, activa la casilla de atajos globales desde
Preferencias como lo haría el usuario y manda por el teclado del sistema
cada una de las doce combinaciones de música de fábrica (`PASOS`), con
una ventana ajena al frente: comprueba que cada una hace lo suyo, que no
le llega a la ventana ajena y que la aplicación no le roba el foco.
Después desactiva la casilla y comprueba que el mismo atajo ya no hace
nada, escribiendo «qa» en la ventana ajena para demostrar que el teclado
sí le llega (que el silencio no es por teclas perdidas).

Si al activar otro programa ya tiene alguna combinación de música, queda
como fallo con la lista completa y la prueba sigue con el resto: para el
usuario eso es un fallo, y cada paso tomado se prueba igual y falla.
Todo fallo queda anotado en `res` con el prefijo «musica_real: » y nunca
lanza. Lo puro (`se_dijo_desde`, `leer_registro`, `tomados_de_fallo`,
`traducir_atajo_a_teclas`, `PASOS`) vive acá con pruebas en
`tests/test_qa_musica_globales.py`. Importar este módulo no abre
ventanas ni manda teclas: eso solo pasa dentro de
`probar_atajos_globales`, que corre el banco en la otra PC.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

from bellbird.core import config_predeterminada
from bellbird.music import anuncios as anuncios_musica
from bellbird.music import anuncios_teclas
from bellbird.ui.atajos_captura import atajo_legible
from bellbird.ui.atajos_globales import ACCIONES

# La sonda (`qa/sonda.py`) busca por nombre accesible y si no por
# etiqueta: este es el `name=` de la casilla en `gui_preferencias.py`.
NOMBRE_CASILLA = "MusicaAtajosGlobales"
PAGINA = "Música"
TECLA_QUE_SUENA = "^%t"
ATAJO_QUE_SUENA = "ctrl+alt+t"
NOMBRE_QUE_SUENA = atajo_legible(ATAJO_QUE_SUENA)
PREFIJO_QUE_SUENA = anuncios_musica.TEXTO_QUE_SUENA.split("{nombre}")[0]
PREFIJO_FALLO = anuncios_musica.TEXTO_ATAJOS_GLOBALES_FALLO.split("{lista}")[0]
TEXTO_QA = "qa"
TITULO_VENTANA_AJENA = "Ventana ajena de QA"
ESPERA_VENTANA_AJENA = 15.0
VK_MENU = 0x12
TECLA_ARRIBA = 0x0002
WM_CLOSE = 0x0010
ESPERA_PASO = 5.0


def traducir_atajo_a_teclas(texto) -> str | None:
    """Traduce un atajo de config a la sintaxis de `send_keys`.

    Solo el área Ctrl+Alt de la música: letra o dígito, Espacio, flechas
    y las dos de Mayús (Flecha izquierda y derecha). Cualquier otra cosa
    da None sin lanzar.
    """
    plano = str(texto or "").strip().lower().replace(" ", "")
    if not plano:
        return None
    partes = plano.split("+")
    if len(partes) == 4:
        if (set(partes[:3]) != {"ctrl", "alt", "shift"}
                or partes[3] not in ("left", "right")):
            return None
        return "^%%+{%s}" % partes[3].upper()
    if len(partes) != 3:
        return None
    primero, segundo, tecla = partes
    if not ((primero == "ctrl" and segundo == "alt")
            or (primero == "alt" and segundo == "ctrl")):
        return None
    if tecla in ("left", "right", "up", "down", "space"):
        return "^%%{%s}" % tecla.upper()
    if len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
        return "^%%%s" % tecla
    return None


# Atajo de fábrica por acción, leído de la misma fuente que la app.
ATAJOS_FABRICA = {
    accion: config_predeterminada.obtener("atajos", accion, "")
    for accion in ACCIONES
}


class Paso(NamedTuple):
    """Un paso del tramo con atajos activos: qué se manda y qué se espera.

    `esperado` es el fragmento anunciado, o None si vale cualquier
    anuncio nuevo (dice el título o la posición).
    """

    accion: str
    teclas: str
    esperado: str | None


def _paso(accion, esperado):
    """Arma un paso con las teclas de fábrica de su acción."""
    return Paso(accion,
                traducir_atajo_a_teclas(ATAJOS_FABRICA.get(accion, "")),
                esperado)


# Los doce atajos en orden fijo, con lo que la escena deja configurado
# (`decir` = `titulo`, `decir_pausa` = `true`, aleatorio y repetir
# apagados, música sonando). Los interruptores vuelven a quedar como
# estaban y el último paso deja la música sonando para el resto.
PASOS = (
    _paso("musica_que_suena", PREFIJO_QUE_SUENA),
    _paso("musica_play", anuncios_musica.TEXTO_PAUSA),
    _paso("musica_play", anuncios_musica.TEXTO_REANUDADA),
    _paso("musica_siguiente", None),
    _paso("musica_anterior", None),
    _paso("musica_vol_mas", None),
    _paso("musica_vol_menos", None),
    _paso("musica_adelantar", None),
    _paso("musica_retroceder", None),
    _paso("musica_silenciar", anuncios_teclas.TEXTO_SILENCIADA),
    _paso("musica_silenciar", anuncios_teclas.TEXTO_RESTAURADA),
    _paso("musica_aleatorio", anuncios_musica.TEXTO_ALEATORIO_ON),
    _paso("musica_aleatorio", anuncios_musica.TEXTO_ALEATORIO_OFF),
    _paso("musica_repetir", anuncios_musica.TEXTO_REPETIR_TODO),
    _paso("musica_repetir", anuncios_musica.TEXTO_REPETIR_TEMA),
    _paso("musica_repetir", anuncios_musica.TEXTO_REPETIR_NO),
    _paso("musica_detener", anuncios_musica.TEXTO_DETENIDA),
    _paso("musica_play", None),
)


def se_dijo_desde(anuncios, fragmento, desde=0) -> bool:
    """Si algún anuncio desde el índice dado contiene el fragmento.

    Los anuncios son dicts con «texto», como los de la sonda, o cadenas.
    Un índice fuera de rango o un fragmento vacío da falso.
    """
    try:
        inicio = max(0, int(desde))
    except (TypeError, ValueError):
        inicio = 0
    pedido = (fragmento or "").lower()
    if not pedido:
        return False
    try:
        trozo = list(anuncios or ())[inicio:]
    except TypeError:
        return False
    for dicho in trozo:
        if isinstance(dicho, dict):
            texto = dicho.get("texto", "")
        else:
            texto = dicho
        if pedido in (texto or "").lower():
            return True
    return False


def leer_registro(ruta) -> str:
    """Contenido del registro de la ventana ajena.

    El archivo ausente o vacío da cadena vacía, para que «no escribió
    nada» y «no se pudo leer» se distingan donde se usa.
    """
    try:
        texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return texto or ""


def tomados_de_fallo(anuncio) -> list[str]:
    """Combinaciones del anuncio de fallo de atajos globales.

    Recibe el texto anunciado (o el dict de la sonda con «texto») con la
    forma de `TEXTO_ATAJOS_GLOBALES_FALLO` y devuelve cada combinación
    como lista. Sin ese anuncio, lista vacía.
    """
    if isinstance(anuncio, dict):
        texto = anuncio.get("texto", "")
    else:
        texto = anuncio
    texto = texto or ""
    comienzo, separador, final = (
        anuncios_musica.TEXTO_ATAJOS_GLOBALES_FALLO.partition("{lista}"))
    if not separador or comienzo not in texto:
        return []
    resto = texto.split(comienzo, 1)[1]
    if final:
        resto = resto.split(final, 1)[0]
    return [parte.strip() for parte in resto.split(",") if parte.strip()]


def _texto_dicho_desde(anuncios, fragmento, desde=0):
    """Texto del primer anuncio desde el índice con el fragmento.

    None si ninguno lo contiene. Acepta dicts con «texto» o cadenas,
    como `se_dijo_desde`.
    """
    try:
        inicio = max(0, int(desde))
    except (TypeError, ValueError):
        inicio = 0
    pedido = (fragmento or "").lower()
    if not pedido:
        return None
    try:
        trozo = list(anuncios or ())[inicio:]
    except TypeError:
        return None
    for dicho in trozo:
        if isinstance(dicho, dict):
            texto = dicho.get("texto", "")
        else:
            texto = dicho
        if pedido in (texto or "").lower():
            return texto or ""
    return None


def _fijar_atajos(propia, res, valor: bool, anotar: bool = True) -> bool:
    """Fija la casilla de atajos globales como lo haría el usuario.

    Abre Preferencias desde el menú, elige la página «Música», fija la
    casilla con la orden `casilla` y guarda. Devuelve si se anunció el
    texto que corresponde al valor pedido. Con `anotar=False` no escribe
    en `res`: lo usa la limpieza para intentar apagar sin duplicar
    fallos ya anotados.
    """
    def fallo(texto: str) -> bool:
        if anotar:
            res.fallo(texto)
        return False

    esperado = (anuncios_musica.TEXTO_ATAJOS_GLOBALES_ACTIVOS if valor
                else anuncios_musica.TEXTO_ATAJOS_GLOBALES_SOLO)
    verbo = "activar" if valor else "desactivar"
    try:
        propia.pedir("frente")
        try:
            propia.abrir_por_menu("Preferencias")
        except Exception as exc:
            return fallo(f"musica_real: no se pudo abrir Preferencias para "
                         f"{verbo} los atajos globales, {exc}")
        if propia.esperar_ventana("Preferencias", segundos=15) is None:
            return fallo(f"musica_real: Preferencias no abrió para {verbo} "
                         f"los atajos globales")
        try:
            paginas = propia.pedir(
                "pestanas", ventana="Preferencias").get(
                    "datos", {}).get("paginas", [])
        except Exception as exc:
            try:
                propia.pedir("cerrar_ventana", ventana="Preferencias")
            except Exception:
                pass
            return fallo(f"musica_real: no se pudieron listar las pestañas "
                         f"para {verbo} los atajos globales, {exc}")
        try:
            indice = next(i for i, n in enumerate(paginas)
                          if n.strip().lower() == PAGINA.lower())
        except StopIteration:
            try:
                propia.pedir("cerrar_ventana", ventana="Preferencias")
            except Exception:
                pass
            return fallo(f"musica_real: no existe la categoría «{PAGINA}»; "
                         f"hay {paginas}")
        propia.pedir("pestanas", ventana="Preferencias", indice=indice)
        time.sleep(0.8)
        try:
            propia.pedir("casilla", ventana="Preferencias",
                         nombre=NOMBRE_CASILLA, valor=bool(valor))
        except Exception as exc:
            try:
                propia.pedir("cerrar_ventana", ventana="Preferencias")
            except Exception:
                pass
            return fallo(f"musica_real: no se pudo fijar la casilla "
                         f"«{NOMBRE_CASILLA}», {exc}")
        time.sleep(0.5)
        desde = len(propia.anuncios)
        propia.pedir("pulsar", nombre="GuardarPreferencias")
        if propia.esperar_ventana("Preferencias", segundos=4) is not None:
            try:
                propia.pedir("cerrar_ventana", ventana="Preferencias")
            except Exception:
                pass
            return fallo(f"musica_real: «Guardar» no cerró Preferencias al "
                         f"{verbo} los atajos globales")
        if not valor:
            if propia.esperar_dicho(esperado, segundos=10, desde=desde):
                if anotar:
                    res.nota(f"musica_real: al {verbo} los atajos globales "
                             f"se anuncia «{esperado}»")
                return True
            return fallo(f"musica_real: no se anunció «{esperado}» al "
                         f"{verbo} los atajos globales")
        return _resolver_activacion(propia, res, desde, esperado, anotar)
    except Exception as exc:
        try:
            propia.pedir("cerrar_ventana", ventana="Preferencias")
        except Exception:
            pass
        return fallo(f"musica_real: no se pudo {verbo} los atajos globales "
                     f"desde Preferencias, {exc}")


def _resolver_activacion(propia, res, desde, esperado,
                         anotar: bool = True) -> bool:
    """Resuelve la activación con o sin combinaciones tomadas.

    Espera hasta 10 s el anuncio de activos o el de fallo. Con fallo que
    lista combinaciones anota un fallo con la lista completa y deja
    seguir: para el usuario eso es un fallo, y cada paso tomado se prueba
    igual y falla. Devuelve si la prueba puede seguir.
    """
    limite = time.monotonic() + 10
    texto_fallo = None
    while True:
        try:
            anuncios = propia.anuncios
        except Exception:
            anuncios = []
        if se_dijo_desde(anuncios, esperado, desde):
            if anotar:
                res.nota("musica_real: al activar los atajos globales se "
                         f"anuncia «{esperado}»")
            return True
        texto_fallo = _texto_dicho_desde(anuncios, PREFIJO_FALLO, desde)
        if texto_fallo is not None or time.monotonic() >= limite:
            break
        time.sleep(0.2)
    if texto_fallo is None:
        if anotar:
            res.fallo(f"musica_real: no se anunció «{esperado}» al activar "
                      f"los atajos globales")
        return False
    lista = tomados_de_fallo(texto_fallo)
    if not lista:
        if anotar:
            res.fallo("musica_real: el anuncio de fallo no trae "
                      "combinaciones y no se probaron los atajos globales")
        return False
    if anotar:
        res.fallo(f"musica_real: al activar los atajos globales otro "
                  f"programa ya usaba {', '.join(lista)} y la prueba sigue "
                  f"con el resto")
    return True


def _pid_al_frente():
    """Pid de la ventana al frente, None si no se pudo saber."""
    try:
        import ctypes
        actual = ctypes.windll.user32.GetForegroundWindow()
        if not actual:
            return None
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(actual,
                                                      ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def _usuario32():
    """`user32`, None si no hay Win32."""
    try:
        import ctypes
        return ctypes.windll.user32
    except Exception:
        return None


def _hwnd_por_titulo(usuario, titulo):
    """HWND con ese título exacto, None si no existe o falla."""
    try:
        hwnd = usuario.FindWindowW(None, titulo)
    except Exception:
        return None
    return hwnd or None


def _pid_de_hwnd(usuario, hwnd):
    """Pid dueño de la ventana, None si no se pudo saber."""
    try:
        import ctypes
        pid = ctypes.c_ulong()
        usuario.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def _esperar_ventana_ajena(segundos: float = ESPERA_VENTANA_AJENA):
    """HWND y pid reales de la ventana ajena.

    El `python.exe` del `.venv` es un lanzador: abre al Python real
    como proceso hijo y la ventana es de ese hijo, así que el pid del
    `Popen` no sirve. Se espera hasta `segundos` a que exista la
    ventana titulada exactamente como `TITULO_VENTANA_AJENA` y se toma
    el pid dueño de esa ventana. Sin ventana, `(None, None)`.
    """
    usuario = _usuario32()
    if usuario is None:
        return None, None
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        hwnd = _hwnd_por_titulo(usuario, TITULO_VENTANA_AJENA)
        if hwnd is not None:
            pid = _pid_de_hwnd(usuario, hwnd)
            if pid is not None:
                return hwnd, pid
        time.sleep(0.3)
    return None, None


def _pulsar_alt(usuario) -> None:
    """Pulsación suelta de Alt para levantar el bloqueo del primer plano.

    Windows le niega el primer plano a un proceso que no es el del
    frente; esa pulsación lo levanta. Es lo que hace `pywinauto` en
    `set_focus`.
    """
    try:
        usuario.keybd_event(VK_MENU, 0, 0, 0)
        usuario.keybd_event(VK_MENU, 0, TECLA_ARRIBA, 0)
    except Exception:
        pass


def _pedir_cierre_ventana_ajena() -> None:
    """Pide a la ventana ajena que se cierre, si sigue existiendo.

    `terminate()` solo mata al lanzador del `.venv` y deja huérfano al
    Python real con su ventana: el `WM_CLOSE` le llega a ese proceso.
    """
    try:
        usuario = _usuario32()
        if usuario is None:
            return
        hwnd = _hwnd_por_titulo(usuario, TITULO_VENTANA_AJENA)
        if hwnd is not None:
            usuario.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    except Exception:
        pass


def _traer_al_frente(hwnd, pid: int, segundos: float = 10.0) -> bool:
    """Lleva al frente la ventana ajena y espera que Windows confirme.

    Comprueba con `GetForegroundWindow` que el primer plano es del pid
    dueño de la ventana e intenta `SetForegroundWindow` con su hwnd si
    no, con una pulsación suelta de Alt antes de cada intento para
    levantar el bloqueo del primer plano. Devuelve si quedó al frente.
    """
    try:
        import ctypes
        usuario = ctypes.windll.user32
    except Exception:
        return False
    if hwnd is None or pid is None:
        return False
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if _pid_al_frente() == pid:
            return True
        _pulsar_alt(usuario)
        try:
            usuario.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.3)
    try:
        return _pid_al_frente() == pid
    except Exception:
        return False


def _enviar(teclas: str) -> bool:
    """Manda teclas reales por el teclado del sistema con `SendInput`."""
    try:
        from pywinauto import keyboard
        keyboard.send_keys(teclas)
        return True
    except Exception:
        return False


def _lanzar_ventana_ajena(registro, cerrar_con):
    """Lanza la ventana ajena como proceso aparte, None si no salió."""
    guion = Path(__file__).resolve().parent / "ventana_ajena.py"
    try:
        return subprocess.Popen(
            [sys.executable, str(guion), "--registro", str(registro),
             "--cerrar-con", str(cerrar_con)])
    except Exception:
        return None


def _esperar_paso(propia, esperado, desde, segundos=ESPERA_PASO) -> bool:
    """Espera el anuncio del paso: el fragmento o cualquiera nuevo.

    Con `esperado` None vale con que crezca la lista de anuncios desde el
    índice dado (dice el título o la posición). Nunca lanza.
    """
    limite = time.monotonic() + segundos
    while True:
        try:
            anuncios = propia.anuncios
        except Exception:
            anuncios = []
        if esperado is None:
            try:
                if len(anuncios) > max(0, int(desde)):
                    return True
            except (TypeError, ValueError):
                pass
        elif se_dijo_desde(anuncios, esperado, desde):
            return True
        if time.monotonic() >= limite:
            return False
        time.sleep(0.2)


def _probar_paso(propia, res, hwnd, pid: int, registro, paso):
    """Un paso de la tabla con otra ventana al frente.

    Devuelve `(foco_ok, registro_ok)` o None si el paso no se pudo
    mandar. Un fallo no corta los siguientes: cada uno nombra su
    combinación con `atajo_legible`.
    """
    nombre = atajo_legible(ATAJOS_FABRICA.get(paso.accion, ""))
    if not _traer_al_frente(hwnd, pid):
        res.no_probado(f"musica_real: la ventana ajena no quedó al frente "
                       f"y no se probó {nombre}")
        return None
    try:
        desde = len(propia.anuncios)
    except Exception:
        desde = 0
    if not _enviar(paso.teclas):
        res.fallo(f"musica_real: no se pudo mandar {nombre} con los "
                  f"atajos activos")
        return None
    if _esperar_paso(propia, paso.esperado, desde):
        if paso.esperado is None:
            res.nota(f"musica_real: {nombre} anuncia algo nuevo con otra "
                     f"ventana al frente")
        else:
            res.nota(f"musica_real: {nombre} dice «{paso.esperado}» con "
                     f"otra ventana al frente")
    elif paso.esperado is None:
        res.fallo(f"musica_real: {nombre} no anunció nada nuevo en 5 s")
    else:
        res.fallo(f"musica_real: {nombre} no dijo «{paso.esperado}» en 5 s")
    try:
        al_frente = _pid_al_frente()
    except Exception:
        al_frente = None
    foco_ok = al_frente == pid
    if not foco_ok:
        res.fallo("musica_real: tras el atajo global la aplicación le robó "
                  f"el foco a la ventana ajena ({nombre})")
    escrito = leer_registro(registro)
    registro_ok = escrito == ""
    if not registro_ok:
        res.fallo(f"musica_real: {nombre} le llegó a la ventana ajena "
                  f"(su registro dice «{escrito}»)")
    return foco_ok, registro_ok


def _probar_activos(propia, res, hwnd, pid: int, registro) -> None:
    """Con los atajos activos: cada paso de la tabla por el teclado real.

    Un fallo en un paso no corta los siguientes. Si el foco y el registro
    sobrevivieron a todos los pasos que se pudieron mandar, se anota una
    vez al final.
    """
    focos = []
    registros = []
    for paso in PASOS:
        nombre = atajo_legible(ATAJOS_FABRICA.get(paso.accion, ""))
        try:
            resultado = _probar_paso(propia, res, hwnd, pid, registro, paso)
        except Exception as exc:
            res.fallo(f"musica_real: {nombre} no se pudo probar, {exc}")
            continue
        if resultado is None:
            continue
        foco_ok, registro_ok = resultado
        focos.append(foco_ok)
        registros.append(registro_ok)
    if focos and all(focos):
        res.nota("musica_real: la aplicación no le roba el foco a la "
                 "ventana ajena")
    if registros and all(registros):
        res.nota("musica_real: los atajos no le llegan a la ventana ajena")


def _probar_apagados(propia, res, hwnd, pid, registro) -> None:
    """Con los atajos apagados: el atajo no hace nada y el teclado llega.

    Si «qa» no llega a la ventana ajena, el «no hizo nada» queda como no
    probado en vez de nota: sin esa prueba el silencio podría ser por
    teclas perdidas.
    """
    if hwnd is None or pid is None or not _traer_al_frente(hwnd, pid):
        res.no_probado("musica_real: la ventana ajena nunca quedó al "
                       "frente y no se pudo comprobar que el atajo apagado "
                       "no hace nada")
        return
    desde = len(propia.anuncios)
    if not _enviar(TECLA_QUE_SUENA):
        res.no_probado(f"musica_real: no se pudo mandar {NOMBRE_QUE_SUENA} "
                       f"con los atajos apagados y no se pudo comprobar que "
                       f"no hace nada")
        return
    time.sleep(4)
    dicho = se_dijo_desde(propia.anuncios, PREFIJO_QUE_SUENA, desde)
    if not _enviar(TEXTO_QA):
        res.no_probado("musica_real: no se pudo escribir en la ventana "
                       "ajena y el «no hizo nada» no se pudo comprobar")
        return
    limite = time.monotonic() + 3
    llego = False
    while time.monotonic() < limite:
        if TEXTO_QA in leer_registro(registro):
            llego = True
            break
        time.sleep(0.1)
    if not llego:
        res.no_probado("musica_real: «qa» no llegó a la ventana ajena y el "
                       "«no hizo nada» no se pudo comprobar (teclas "
                       "perdidas)")
        return
    if dicho:
        res.fallo(f"musica_real: {NOMBRE_QUE_SUENA} dijo qué suena con los "
                  f"atajos apagados")
    else:
        res.nota(f"musica_real: con los atajos apagados {NOMBRE_QUE_SUENA} "
                 f"no hace nada y el teclado sí le llega a la ventana ajena")


def probar_atajos_globales(propia, res, carpeta_tmp) -> None:
    """Tramo de atajos globales de `musica_real`, con la música sonando.

    Activa la casilla desde Preferencias, comprueba que dice qué suena
    con una ventana ajena al frente, desactiva la casilla y comprueba que
    el atajo ya no hace nada. Cierra la ventana ajena en un `finally` e
    intenta dejar la casilla apagada si algo falló en el camino. La
    configuración en disco la restaura `musica_real` al final, como ya
    hace.
    """
    base = Path(carpeta_tmp)
    registro = base / "ventana_ajena.txt"
    cerrar_con = base / "cerrar_ventana_ajena"
    try:
        cerrar_con.unlink()
    except OSError:
        pass
    proceso = None
    apagados_ok = False
    try:
        if not _fijar_atajos(propia, res, True):
            return
        proceso = _lanzar_ventana_ajena(registro, cerrar_con)
        if proceso is None:
            res.no_probado("musica_real: no se pudo lanzar la ventana "
                           "ajena y no se probaron los atajos globales")
            return
        hwnd_ajena, pid_ajeno = _esperar_ventana_ajena()
        if hwnd_ajena is None:
            res.no_probado("musica_real: no se pudo lanzar la ventana "
                           "ajena y no se probaron los atajos globales")
            return
        if not _traer_al_frente(hwnd_ajena, pid_ajeno):
            res.no_probado("musica_real: la ventana ajena nunca quedó al "
                           "frente y no se probaron los atajos globales")
        else:
            _probar_activos(propia, res, hwnd_ajena, pid_ajeno, registro)
        if not _fijar_atajos(propia, res, False):
            return
        apagados_ok = True
        _probar_apagados(propia, res, hwnd_ajena, pid_ajeno, registro)
    finally:
        if proceso is not None:
            try:
                cerrar_con.write_bytes(b"")
            except OSError:
                pass
            limite = time.monotonic() + 5
            while proceso.poll() is None and time.monotonic() < limite:
                time.sleep(0.1)
            if proceso.poll() is None:
                _pedir_cierre_ventana_ajena()
                limite = time.monotonic() + 3
                while (proceso.poll() is None
                       and time.monotonic() < limite):
                    time.sleep(0.1)
            if proceso.poll() is None:
                try:
                    proceso.terminate()
                except Exception:
                    pass
        if not apagados_ok:
            try:
                _fijar_atajos(propia, res, False, anotar=False)
            except Exception:
                pass

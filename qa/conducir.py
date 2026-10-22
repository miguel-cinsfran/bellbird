"""Banco de QA: maneja la aplicación desde dentro y comprueba lo que dice.

Segunda versión. La primera manejaba la aplicación desde fuera con teclas
sintéticas y no servía: para poder teclear había que robarle el primer plano a
Windows, el truco para lograrlo era un ALT sintético, y ALT abre la barra de
menú, así que los aceleradores dejaban de llegar. La herramienta rompía lo que
estaba midiendo, y llegó a dar por roto un Ctrl+S que funciona perfectamente.

Lo que se hace ahora, que es lo que hace la gente que prueba aplicaciones de
escritorio en serio:

- **Manejar desde dentro**, con `wx.UIActionSimulator`, que es la herramienta
  que wxWidgets trae para conducir sus propias pruebas. Sin peleas de foco.
- **Esperar hechos, no relojes.** Ni un `sleep` a ciegas: se espera a que
  aparezca una ventana, a que el foco caiga en un control, o a que la
  aplicación diga algo. Es como sincroniza el banco de pruebas del propio NVDA.
- **Grabar la voz en vez de decirla**, para que correr las pruebas no le
  secuestre el lector de pantalla al dueño.

Lo que sí prueba: que los controles tengan nombre y se alcancen con Tab, que
los atajos hagan lo que dicen, y que la aplicación intente decir lo que
corresponde cuando corresponde.

Lo que NO prueba, y no hay que declararlo probado: que NVDA lo lea, cómo suena,
la línea braille, y si la ventana se ve bien.

Uso:

    .venv\\Scripts\\python.exe qa/conducir.py
    .venv\\Scripts\\python.exe qa/conducir.py --escenario descargas
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

from sonda import VAR_DESTINO, VAR_ORDENES, VAR_RESULTADOS  # noqa: E402

import capturas  # noqa: E402

try:
    import medidor_sonido  # noqa: E402
except Exception:
    medidor_sonido = None

TIEMPO_ORDEN = 20.0

# La consola de Windows va en cp1252 y el chat lleva emojis. Sin esto, imprimir
# un super chat revienta la corrida entera con UnicodeEncodeError, y el fallo
# parece de la aplicacion cuando es del banco.
for _flujo in (sys.stdout, sys.stderr):
    try:    _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass


class Resultado:
    def __init__(self):
        self.fallos: list[str] = []
        self.notas: list[str] = []
        self.sin_probar: list[str] = []

    def fallo(self, texto: str) -> None:
        self.fallos.append(texto)
        print(f"    FALLO  {texto}")

    def nota(self, texto: str) -> None:
        self.notas.append(texto)
        print(f"    . {texto}")

    def no_probado(self, texto: str) -> None:
        self.sin_probar.append(texto)
        print(f"    SIN PROBAR  {texto}")

    @property
    def ok(self) -> bool:
        return not self.fallos


class VentanaNoActiva(RuntimeError):
    """No se pudo dejar la ventana al frente, así que no se tecleó nada.

    Pasa cuando el dueño está usando la máquina, que es lo normal mientras el
    banco corre. No es un defecto de la aplicación y no se cuenta como tal.
    """


class OrdenRechazada(RuntimeError):
    """La sonda recibió la orden y dijo que no. No es un fallo de la aplicación."""


class Aplicacion:
    """La aplicación corriendo, con el canal de órdenes abierto."""

    def __init__(self, carpeta: Path):
        carpeta.mkdir(parents=True, exist_ok=True)
        self.anuncios_ruta = carpeta / "qa-anuncios.jsonl"
        self.ordenes_ruta = carpeta / "qa-ordenes.jsonl"
        self.resultados_ruta = carpeta / "qa-resultados.jsonl"
        self.salida_ruta = carpeta / "qa-salida-app.txt"
        for r in (self.anuncios_ruta, self.ordenes_ruta, self.resultados_ruta,
                  self.salida_ruta):
            if r.exists():
                r.unlink()
        self._siguiente_id = 1
        self.proceso = None

    # ── ciclo de vida ────────────────────────────────────────────────────────

    def arrancar(self) -> None:
        entorno = dict(os.environ)
        entorno[VAR_DESTINO] = str(self.anuncios_ruta)
        entorno[VAR_ORDENES] = str(self.ordenes_ruta)
        entorno[VAR_RESULTADOS] = str(self.resultados_ruta)
        codigo = (
            "import sys; sys.path.insert(0, r'%s'); "
            "import sonda as qa_sonda; qa_sonda.arrancar_aplicacion(r'%s')"
            % (RAIZ / "qa", RAIZ / "main.py")
        )
        # La salida de la aplicacion NO se tira: wx escribe ahi sus avisos de
        # widgets mal construidos, y hoy no los lee nadie.
        self._salida = open(self.salida_ruta, "w", encoding="utf-8",
                            errors="replace")
        self.proceso = subprocess.Popen(
            [sys.executable, "-c", codigo], cwd=str(RAIZ), env=entorno,
            stdout=self._salida, stderr=subprocess.STDOUT)

    def esperar_lista(self, segundos: float = 60.0) -> bool:
        """Espera a que la ventana principal exista, preguntándoselo a ella."""
        limite = time.time() + segundos
        while time.time() < limite:
            # Si el proceso ya murió no hay nada que esperar. Pasa cuando otra
            # instancia sigue abierta: `main.py` avisa y se cierra, y sin esto
            # el banco agotaba el minuto entero sin saber por qué.
            if self.proceso is not None and self.proceso.poll() is not None:
                return False
            try:
                r = self.pedir("ping", tiempo=3.0, tolerar=True)
                if r.get("ok") and r.get("datos", {}).get("listo"):
                    return True
            except TimeoutError:
                pass
        return False

    def murio_sola(self) -> bool:
        """¿Se cerró la aplicación por su cuenta? Normalmente, el guardián de
        instancia única: ya había otra ventana abierta."""
        return self.proceso is not None and self.proceso.poll() is not None

    def cerrar(self) -> None:
        try:
            self.pedir("salir", tiempo=5.0)
        except Exception:
            pass
        # Si un escenario dejó la pregunta «Salir» abierta, el hilo de
        # interfaz está dentro del modal y la orden de arriba no vuelve: se
        # contesta desde fuera y se sigue como hoy si no hay nada.
        try:
            contestar_salir_si_aparece(segundos=2.0)
        except Exception:
            pass
        if self.proceso is not None:
            try:
                self.proceso.terminate()
                self.proceso.wait(timeout=10)
            except Exception:
                try:    self.proceso.kill()
                except Exception: pass
        try:    self._salida.close()
        except Exception: pass
        # `main.py` solo deja abrir una instancia: si la anterior sigue viva,
        # la siguiente muere mostrando un aviso y el banco se queda esperando
        # un `ping` que no va a llegar nunca.
        self.proceso = None

    # ── canal de órdenes ─────────────────────────────────────────────────────

    def pedir(self, op: str, tiempo: float = TIEMPO_ORDEN,
              tolerar: bool = False, **extra) -> dict:
        """Manda una orden y espera la respuesta.

        Una orden rechazada revienta, y eso es a propósito. Antes devolvía el
        sobre con `ok` en falso y el escenario seguía como si nada: el
        21/08/2026 el escenario del reproductor dio nueve fallos de
        accesibilidad que en realidad eran nueve órdenes que la sonda nunca
        pudo ejecutar. Un banco que confunde «no lo encontré» con «está mal
        hecho» miente en la dirección más cara.

        `tolerar=True` para los casos en que el rechazo es la respuesta.
        """
        id_orden = self._siguiente_id
        self._siguiente_id += 1
        orden = {"id": id_orden, "op": op}
        orden.update(extra)
        with open(self.ordenes_ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(orden, ensure_ascii=False) + "\n")
            f.flush()

        limite = time.time() + tiempo
        while time.time() < limite:
            for linea in self._lineas(self.resultados_ruta):
                if linea.get("id") == id_orden:
                    if not linea.get("ok") and not tolerar:
                        raise OrdenRechazada(
                            f"{op}({extra}): {linea.get('error')}")
                    return linea
            time.sleep(0.05)
        raise TimeoutError(f"la orden {op!r} no contestó en {tiempo} s")

    @staticmethod
    def _lineas(ruta: Path) -> list[dict]:
        if not ruta.exists():
            return []
        salida = []
        crudo = ruta.read_text(encoding="utf-8", errors="replace")
        for linea in crudo.splitlines():
            linea = linea.strip()
            if linea:
                try:
                    salida.append(json.loads(linea))
                except ValueError:
                    pass
        return salida

    # ── consultas ────────────────────────────────────────────────────────────

    @property
    def anuncios(self) -> list[dict]:
        return self._lineas(self.anuncios_ruta)

    def dijo(self, fragmento: str, desde: int = 0) -> bool:
        f = fragmento.lower()
        return any(f in a["texto"].lower() for a in self.anuncios[desde:])

    def esperar_dicho(self, fragmento: str, segundos: float = 15.0,
                      desde: int = 0) -> bool:
        """Espera a que la aplicación intente decir algo. Así sincroniza NVDA."""
        limite = time.time() + segundos
        while time.time() < limite:
            if self.dijo(fragmento, desde):
                return True
            time.sleep(0.1)
        return False

    def ventanas(self) -> list[dict]:
        return self.pedir("ventanas").get("datos", {}).get("ventanas", [])

    def esperar_ventana(self, titulo: str, segundos: float = 15.0):
        """Espera un diálogo.

        Se pregunta desde dentro, así que los modales también se ven. Eso es lo
        que la versión anterior no conseguía: `Desktop().windows()` de pywinauto
        no devolvía los diálogos modales, y por eso parecía que no se abrían.
        """
        objetivo = titulo.lower()
        limite = time.time() + segundos
        while time.time() < limite:
            for v in self.ventanas():
                if objetivo in (v.get("titulo") or "").lower() and v.get("visible"):
                    return v
            time.sleep(0.2)
        return None

    def arbol(self, ventana: str | None = None) -> list[dict]:
        datos = self.pedir("arbol", ventana=ventana).get("datos", {})
        return datos.get("controles", [])

    def foco(self) -> dict | None:
        return self.pedir("quien_tiene_foco").get("datos", {}).get("control")

    def navegar(self, ventana: str | None = None) -> bool:
        """Avanza una parada en el orden de Tab, por la cadena de foco de wx.

        No manda una tecla al sistema, a diferencia de `teclas`. Eso lo hace
        inmune a que la ventana no esté al frente del escritorio, que es la
        razón por la que el recorrido de Tab de este banco daba una sola parada
        en todos los diálogos. Lo que no cubre es el camino del teclado del
        sistema operativo hasta la ventana.
        """
        datos = self.pedir("navegar", ventana=ventana).get("datos", {})
        return bool(datos.get("movido"))

    def al_frente(self, segundos: float = 5.0) -> bool:
        """Trae la ventana al frente y espera a que Windows lo confirme.

        `wx.UIActionSimulator` escribe en la ventana que el sistema tenga al
        frente, no en la que uno cree. Pedir `frente` y teclear en la línea
        siguiente funcionaba o no según lo ocupada que estuviera la máquina: el
        21/08/2026 eso hizo que el banco diera por mudo el volumen del
        reproductor, que anuncia perfectamente.
        """
        limite = time.time() + segundos
        while time.time() < limite:
            if self.pedir("frente").get("datos", {}).get("activa"):
                return True
            time.sleep(0.2)
        return False

    def hilos(self) -> list[str]:
        """Los hilos vivos de la aplicación, por nombre."""
        return self.pedir("hilos").get("datos", {}).get("vivos", [])

    def reproductor(self) -> dict:
        """La posición que la aplicación le da al usuario, no lo que anuncia."""
        return self.pedir("reproductor").get("datos", {})

    def llamar(self, metodo: str, *args, **kwargs) -> dict:
        """Llama a un método público del frame, como hace `main.py`."""
        return self.pedir("llamar", metodo=metodo, args=list(args),
                          kwargs=kwargs)

    def simular_sesion_youtube(self, titulo: str = "Directo de prueba",
                               espectadores: int = 42) -> None:
        """Monta una sesión de YouTube sin tocar la red.

        Usa la misma API pública que `main.py` invoca desde el hilo de captura.
        No es hacer trampa: es probar la interfaz sin depender de que haya un
        directo vivo y de que la red se porte bien.
        """
        self.llamar("set_conectado", True)
        self.llamar("set_tipo_video", "live", "ArKbAx1K-2U")
        self.llamar("set_titulo_stream", titulo)
        self.llamar("set_espectadores", espectadores)
        self.llamar("set_live_chat_id", "prueba-qa")

    def restaurar_desconectado(self) -> None:
        """Deshace una sesion simulada y deja la aplicacion desconectada.

        Lo necesita cualquier escenario que simule una sesion y no sea el
        ultimo de la corrida. Medido el 26/08/2026: `redactar` simulaba una
        sesion y no la deshacia, asi que `chat`, que corre despues y mide
        justamente el PASO de desconectado a conectado, encontraba la
        aplicacion ya conectada y fallaba diciendo que conectar no anunciaba
        nada. El defecto no estaba donde saltaba.
        """
        self.llamar("set_live_chat_id", "")
        self.llamar("set_titulo_stream", "")
        self.llamar("set_espectadores", 0)
        self.llamar("set_conectado", False)

    def simular_sesion_tiktok(self, usuario: str = "rolon_100") -> None:
        self.llamar("set_conectado", True)
        self.llamar("configurar_tiktok", usuario, "")

    def mensaje(self, autor: str, texto: str, hora: str = "12:00",
                tipo: str = "text", monto: str = "") -> None:
        self.llamar("agregar_mensaje_chat", autor, texto, hora, tipo, monto, "")

    def menus(self) -> list[dict]:
        return self.pedir("menus").get("datos", {}).get("menus", [])

    def abrir_por_menu(self, etiqueta: str) -> dict:
        """Dispara un ítem de menú por su texto, sin usar el teclado."""
        return self.pedir("menu_click", etiqueta=etiqueta, tiempo=10.0)

    def teclas(self, *pasos) -> dict:
        """teclas(("s", ["ctrl"])) para Ctrl+S, o teclas("tab").

        Se asegura de que la ventana esté al frente antes y después. El
        simulador de wx escribe en la ventana que tenga el sistema al frente,
        no en la que uno cree: si el dueño se pasó al navegador en medio de la
        corrida, las teclas van a parar allá y el banco lo reporta como que la
        aplicación se quedó muda. Prefiere no medir a medir mal.
        """
        if not self.al_frente():
            raise VentanaNoActiva("la ventana no está al frente")
        secuencia = []
        for p in pasos:
            secuencia.append(list(p) if isinstance(p, (list, tuple)) else [p])
        r = self.pedir("teclas", secuencia=secuencia)
        if not self.pedir("frente").get("datos", {}).get("activa"):
            raise VentanaNoActiva("la ventana perdió el frente mientras se "
                                  "tecleaba, no se puede juzgar lo que pasó")
        return r


# ── Comprobaciones ───────────────────────────────────────────────────────────

CLASES_INTERACTIVAS = {
    "Button", "BitmapButton", "TextCtrl", "Choice", "ComboBox", "ListBox",
    "ListCtrl", "CheckBox", "RadioButton", "RadioBox", "Slider",
    "DirPickerCtrl", "FilePickerCtrl", "SpinCtrl", "Notebook",
}

# wx le pone a cada control un nombre por defecto según su clase. Que exista no
# quiere decir que alguien lo haya nombrado, así que estos no cuentan.
NOMBRES_POR_DEFECTO = {
    "", "button", "text", "textctrl", "choice", "listctrl", "listbox",
    "checkbox", "panel", "staticbox", "dirpicker", "filepicker", "combobox",
    "radiobutton", "radiobox", "slider", "spinctrl", "notebook", "control",
}


def parece_clave_cruda(texto: str) -> bool:
    """¿Esto es lenguaje humano o una clave del `config.ini` que se escapó?

    Distinción pagada el 21/08/2026: una mutación cambió la etiqueta de un
    botón de atajos por su clave de configuración, `descargas_abrir`, y ni la
    suite ni este banco dijeron nada. El control tenía nombre, y el banco solo
    comprobaba que lo tuviera. Un lector de pantalla lee «descargas guion bajo
    abrir», que no es un nombre: es un identificador de programador.
    """
    t = (texto or "").strip()
    # Los botones de atajo se llaman «accion: Ctrl+S», asi que la parte que
    # tiene que ser legible es la de antes de los dos puntos.
    if ":" in t:
        t = t.split(":", 1)[0].strip()
    if not t or " " in t:
        return False
    return "_" in t and t == t.lower() and t.replace("_", "").isalnum()


def revisar_nombres(controles: list[dict], res: Resultado, donde: str) -> None:
    """Un control interactivo sin nombre ni etiqueta es mudo para el lector."""
    mudos = []
    crudos = []
    interactivos = 0
    for c in controles:
        if c.get("clase") not in CLASES_INTERACTIVAS or not c.get("visible"):
            continue
        interactivos += 1
        nombre = (c.get("nombre") or "").strip()
        etiqueta = (c.get("etiqueta") or "").strip()
        if nombre.lower() in NOMBRES_POR_DEFECTO and not etiqueta:
            mudos.append(c)
        # Solo se juzga el texto que de verdad se anuncia. El `name=` interno
        # de wx puede ser un identificador (`Atajo_silenciar_sonidos`) sin que
        # eso llegue al lector, y darlo por defecto llena el informe de ruido.
        elif parece_clave_cruda(etiqueta or nombre):
            crudos.append((c, etiqueta or nombre))
    for c in mudos:
        res.fallo(f"{donde}: un {c['clase']} no tiene nombre ni etiqueta")
    for c, texto in crudos:
        res.fallo(f"{donde}: un {c['clase']} se llama «{texto}», que parece "
                  "una clave de configuración y no una frase")
    if not mudos and not crudos:
        res.nota(f"{donde}: {interactivos} controles interactivos, "
                 "todos con nombre o etiqueta")


# Cuanto se le concede a un dialogo que consulta algo de fuera para volverse
# navegable entero. Medido: el de Transmision con OBS abierto tarda menos de
# dos segundos; el margen es para una maquina cargada.
SEGUNDOS_TAB_COMPLETO = 12.0

# La ventana Transmision tiene 28 controles con OBS abierto y crece con cada
# funcion nueva, asi que el tope de paradas necesita aire de sobra.
VUELTAS_TAB_TRANSMISION = 40


def recorrer_tab(app: Aplicacion, res: Resultado, donde: str,
                 vueltas: int = 20, ventana: str | None = None) -> list[str]:
    """Pulsa Tab y anota dónde cae el foco, preguntándoselo a wx."""
    visto: list[str] = []
    for _ in range(vueltas):
        ctrl = app.foco()
        if ctrl:
            nombre = (ctrl.get("nombre") or "").strip()
            etiqueta = (ctrl.get("etiqueta") or "").strip().replace("&", "")
            legible = etiqueta or nombre
            if nombre.lower() in NOMBRES_POR_DEFECTO and not etiqueta:
                legible = "(SIN NOMBRE)"
            etiq = f"{ctrl['clase']}: {legible}"
            if etiq not in visto:
                visto.append(etiq)
        app.navegar(ventana)
    for v in visto:
        if "(SIN NOMBRE)" in v:
            res.fallo(f"{donde}: el foco cae en algo sin nombre, {v}")
    if not visto:
        res.fallo(f"{donde}: Tab no movió el foco a ningún sitio legible")
    return visto


def _con_tope(funcion, segundos: float, por_defecto):
    """Corre algo en un hilo aparte y se rinde si tarda de más.

    Hace falta porque una llamada de UI Automation a un proceso que no responde
    no tiene tope propio y no se puede interrumpir. El hilo queda colgado, pero
    es demonio y no impide salir: peor es que se cuelgue la corrida entera.
    """
    import threading
    resultado = [por_defecto]

    def _correr():
        try:
            resultado[0] = funcion()
        except Exception:
            pass

    hilo = threading.Thread(target=_correr, daemon=True)
    hilo.start()
    hilo.join(segundos)
    return resultado[0]


def roles_segun_windows(titulo: str, tope: float = 20.0) -> dict[str, int]:
    """Qué roles expone esta ventana al servicio de accesibilidad de Windows.

    Es la única comprobación que necesita mirar desde fuera, y por eso usa
    pywinauto: desde dentro wx siempre dirá `CheckBox`, aunque Windows la esté
    exponiendo como botón. La diferencia es justo lo que discute `AGENTS.md`.
    """
    try:
        from pywinauto import Desktop
    except ImportError:
        return {}
    return _con_tope(lambda: _roles_sin_tope(titulo, Desktop), tope, {})


def _ventana_por_titulo(Desktop, objetivo):
    """La ventana cuyo titulo contiene `objetivo`, este donde este.

    Se mira primero entre las ventanas de raiz. Si no aparece ahi, se busca
    DENTRO de la ventana de la aplicacion, y esa segunda vuelta es la que hace
    falta de verdad: medido el 26/08/2026, el dialogo de Preferencias NO cuelga
    de la raiz sino de la ventana principal, porque un `wx.Dialog` modal tiene
    dueno y Windows lo expone como descendiente suyo.

    Ese detalle dejo muda la comprobacion de owner-drawn durante un dia entero:
    devolvia vacio y el banco lo anotaba como «no se pudo leer el arbol», que
    parece un problema del entorno y no una comprobacion que no se hace.

    La segunda vuelta se limita a la ventana de la aplicacion a proposito.
    Recorrer los descendientes de CADA ventana del escritorio tardo 72,4
    segundos contra 0,8, porque UI Automation pregunta a cada proceso ajeno y
    espera a su bucle de mensajes. Dentro de la propia aplicacion son 0,2.
    """
    for w in _candidatas_uia(Desktop):
        try:
            if (w.element_info.control_type in ("Window", "Pane")
                    and objetivo in (w.element_info.name or "").lower()):
                return w
        except Exception:
            continue
    return None


def _candidatas_uia(Desktop):
    """Las ventanas donde puede estar algo nuestro, primero las mas probables.

    Se recorren las ventanas de raiz, que son diez y se enumeran en menos de un
    segundo, y solo despues los descendientes de la ventana de la aplicacion,
    que son otros 0,2 segundos.

    Lo que NO se hace, y es el motivo de que esto exista, es pedirle a UI
    Automation `top_level_only=False`. Eso recorre los descendientes de CADA
    ventana del escritorio: pregunta a Chrome, a Steam, a Telegram, y espera al
    bucle de mensajes de cada uno. Medido el 25/08/2026 en 72,4 segundos contra
    0,8, y el 26/08/2026 comiendo casi entera la corrida de `dialogos_ayuda`,
    que bajo de 72 segundos a 12 al quitarlo.

    El tope por reloj no protegia de esto: una sola pasada tarda mas que el
    tope entero y no se puede interrumpir desde fuera.
    """
    raices = list(Desktop(backend="uia").windows(top_level_only=True))
    for w in raices:
        yield w
    for w in raices:
        try:
            if not (w.element_info.name or "").lower().startswith("ytchat"):
                continue
        except Exception:
            continue
        for d in w.descendants():
            yield d


def _roles_sin_tope(titulo, Desktop) -> dict[str, int]:
    cuenta: dict[str, int] = {}
    _ULTIMOS_NOMBRES.clear()
    try:
        w = _ventana_por_titulo(Desktop, titulo.lower())
        if w is None:
            return cuenta
        for d in w.descendants():
            try:
                rol = d.element_info.control_type
                nombre = (d.element_info.name or "").strip()
            except Exception:
                continue
            cuenta[rol] = cuenta.get(rol, 0) + 1
            _ULTIMOS_NOMBRES.setdefault(rol, []).append(nombre)
    except Exception:
        pass
    return cuenta


# Se guardan los nombres del ultimo vistazo para poder decir QUE control es el
# que no cuadra, en vez de solo cuantos faltan. Un recuento sin nombre obliga a
# adivinar, y adivinar es como se producen los hallazgos falsos.
_ULTIMOS_NOMBRES: dict[str, list[str]] = {}


def nombres_segun_windows(rol: str) -> list[str]:
    return list(_ULTIMOS_NOMBRES.get(rol, []))


def auditar_dialogo(app: Aplicacion, res: Resultado, etiqueta_menu: str,
                    titulo: str, vueltas_tab: int = 16,
                    esperados: tuple[str, ...] = (),
                    esperados_en_tab: tuple[str, ...] = ()) -> bool:
    """Abre un diálogo desde el menú, lo audita entero y lo cierra."""
    app.pedir("frente")
    try:
        app.abrir_por_menu(etiqueta_menu)
    except Exception as exc:
        res.fallo(f"{titulo}: no se pudo disparar «{etiqueta_menu}», {exc}")
        return False

    dlg = app.esperar_ventana(titulo, segundos=15)
    if dlg is None:
        res.fallo(f"{titulo}: el menú no abrió ninguna ventana con ese título")
        return False
    res.nota(f"{titulo}: abre desde «{etiqueta_menu}», clase {dlg['clase']}")

    controles = app.arbol(titulo)
    revisar_nombres(controles, res, titulo)

    if esperados:
        # Se quita la marca de mnemonico: una etiqueta como "Aplicar &tamano"
        # no contiene "aplicar tamano", y eso daba fallos que no existian.
        juntos = " ".join(
            ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
            for c in controles).replace("&", "").lower()
        for e in esperados:
            if e.lower() not in juntos:
                res.fallo(f"{titulo}: no aparece nada llamado «{e}»")

    # `esperados` busca el texto en TODO el dialogo, asi que un rotulo o el
    # cuadro de estado pueden hacerlo pasar aunque el control no exista. Lo que
    # se pide aca tiene que estar en una parada de Tab, que es lo unico que
    # demuestra que hay un control alcanzable, con nombre y habilitado.
    #
    # Se reintenta con plazo porque un dialogo que consulta algo de fuera nace
    # con sus controles deshabilitados a proposito, y deshabilitado no entra en
    # el orden de Tab. Auditar en el primer instante mide la pantalla de espera,
    # no el dialogo. Lo que se exige entonces es que se vuelva navegable ANTES
    # del plazo, que es la propiedad que le importa a quien no ve.
    limite = time.monotonic() + SEGUNDOS_TAB_COMPLETO
    while True:
        orden = recorrer_tab(app, res, titulo, vueltas=vueltas_tab,
                             ventana=titulo)
        faltan = [e for e in esperados_en_tab
                  if e.lower() not in " ".join(orden).replace("&", "").lower()]
        if not faltan or time.monotonic() >= limite:
            break
        time.sleep(0.5)
    res.nota(f"{titulo}, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden[:12]))
    for e in faltan if esperados_en_tab else ():
        res.fallo(f"{titulo}: «{e}» no aparece en el orden de Tab "
                  f"en {SEGUNDOS_TAB_COMPLETO:.0f} segundos")

    app.pedir("cerrar_ventana", ventana=titulo)
    if app.esperar_ventana(titulo, segundos=4) is not None:
        res.fallo(f"{titulo}: el diálogo no cerró")
    return True


def abrir_y_auditar(app: Aplicacion, res: Resultado, etiqueta_menu: str,
                    vueltas_tab: int = 14):
    """Dispara un ítem de menú y audita la ventana que aparezca, sea cual sea.

    No se le pide el título por adelantado a propósito: si el diálogo se
    llamara distinto de lo que uno cree, un escenario con el título escrito a
    mano diría «no abrió» y sería mentira. Ya pasó una vez hoy.
    """
    app.pedir("frente")
    antes = {v["titulo"] for v in app.ventanas()}
    try:
        app.abrir_por_menu(etiqueta_menu)
    except Exception as exc:
        res.fallo(f"«{etiqueta_menu}»: no se pudo disparar, {exc}")
        return None

    limite = time.time() + 12
    titulo = None
    while time.time() < limite:
        nuevas = {v["titulo"] for v in app.ventanas()} - antes
        if nuevas:
            titulo = sorted(nuevas)[0]
            break
        time.sleep(0.2)
    if titulo is None:
        res.nota(f"«{etiqueta_menu}»: no abre ventana, "
                 "puede ser una acción directa")
        return None

    res.nota(f"«{etiqueta_menu}» abre «{titulo}»")
    controles = app.arbol(titulo)
    revisar_nombres(controles, res, titulo)
    orden = recorrer_tab(app, res, titulo, vueltas=vueltas_tab,
                         ventana=titulo)
    res.nota(f"{titulo}, Tab: " + " > ".join(orden[:10]))
    app.pedir("cerrar_ventana", ventana=titulo)
    if app.esperar_ventana(titulo, segundos=4) is not None:
        res.fallo(f"{titulo}: no cerró")
    return titulo


def lista_del_chat(controles):
    """La lista donde aterrizan los mensajes. Primero por nombre, si no la
    primera lista con contenido que aparezca."""
    for c in controles:
        if c["clase"] in ("ListBox", "ListCtrl") and "items" in c:
            nombre = ((c.get("nombre") or "") + (c.get("etiqueta") or "")).lower()
            if "chat" in nombre:
                return c
    for c in controles:
        if c["clase"] == "ListBox" and "items" in c:
            return c
    return None



# ── Escenarios ───────────────────────────────────────────────────────────────

def escenario_arranque_frio(app: Aplicacion, args, res: Resultado):
    """¿Responde la ventana mientras libVLC se precalienta?

    Monta una aplicación aparte y la sondea desde el instante del lanzamiento.
    Esperar primero a que la ventana conteste no sirve: en una máquina con el
    caché de plugins caliente el precalentamiento ya terminó para entonces, y
    la medición llega tarde a lo único que quería medir.

    En el registro que mandó el amigo del dueño, del 19 al 21/08/2026, el hilo
    `ReproductorWarmup` tardó 56, 92 y 128 segundos, y los tres bloqueos más
    largos de la interfaz, de 10, 40 y 53 segundos, terminaron en el mismo
    segundo en que ese hilo terminaba. `reproductor.py:381` da por hecho que
    crear la instancia cuesta uno o dos segundos.

    Acá el disco está caliente, así que el número va a salir mucho más chico.
    Lo que se mira no es el número: es si mientras ese hilo vive la ventana
    deja o no de contestar. Si deja, el mecanismo está confirmado y en la
    máquina del amigo solo escala.
    """
    aparte = Aplicacion(app.anuncios_ruta.parent / "arranque")
    t0 = time.time()
    aparte.arrancar()
    try:
        primera = None
        muestras = []          # (t, latencia, contesto, hilos)
        vio_warmup = False
        while time.time() - t0 < 150:
            antes = time.time()
            try:
                r = aparte.pedir("ping", tiempo=2.0, tolerar=True)
                contesto = bool(r.get("ok"))
            except TimeoutError:
                contesto = False
            latencia = time.time() - antes
            vivos = []
            if contesto:
                if primera is None:
                    primera = antes - t0
                try:
                    vivos = aparte.hilos()
                except Exception:
                    vivos = []
            muestras.append((antes - t0, latencia, contesto, vivos))

            if "ReproductorWarmup" in vivos:
                vio_warmup = True
            elif vio_warmup and contesto:
                break          # el precalentamiento terminó
            elif (primera is not None and not vio_warmup
                  and antes - t0 > primera + 5):
                break          # nunca lo vimos: el caché estaba caliente
            if aparte.murio_sola():
                break
            time.sleep(0.1)

        if aparte.murio_sola() and primera is None:
            res.nota("arranque: la aplicación se cerró sola, casi seguro porque "
                     "ya había otra instancia abierta; este escenario necesita "
                     "la máquina para él solo")
            return
        if primera is None:
            res.fallo("arranque: la ventana no contestó ni una vez en 150 s")
            return

        res.nota("arranque: la ventana contesta por primera vez a los %.1f s"
                 % primera)

        # Solo cuentan las muestras posteriores a la primera respuesta: antes de
        # eso «no contesta» quiere decir «todavía no existe», que no es lo mismo
        # que estar congelada.
        utiles = [m for m in muestras if m[0] >= primera]
        peor_t, peor = max(((m[0], m[1]) for m in utiles), key=lambda x: x[1])
        durante = [m for m in utiles if "ReproductorWarmup" in m[3]]

        if not vio_warmup:
            res.nota("arranque: el precalentamiento de libVLC ya había terminado "
                     "antes de la primera respuesta; con el caché de plugins "
                     "caliente no se lo puede juzgar desde acá")
        else:
            ventana = durante[-1][0] - durante[0][0] if len(durante) > 1 else 0.0
            peor_dentro = max((m[1] for m in durante), default=0.0)
            res.nota("arranque: ReproductorWarmup vivo durante %.1f s, y la peor "
                     "respuesta mientras tanto fue de %.1f s"
                     % (ventana, peor_dentro))
            if peor_dentro > 2.0:
                res.fallo("arranque: la ventana estuvo %.1f s sin responder "
                          "mientras libVLC se precalentaba" % peor_dentro)

        res.nota("arranque: %d sondeos, peor respuesta %.1f s a los %.1f s"
                 % (len(utiles), peor, peor_t))
        if peor > 2.0 and not vio_warmup:
            res.fallo("arranque: la ventana estuvo %.1f s sin responder" % peor)
    finally:
        aparte.cerrar()


# Cuánto puede tardar una acción del reproductor antes de que se note. Medio
# segundo no lo percibe nadie; a partir de uno la ventana ya "va dura", y por
# encima de dos, sin ver la pantalla, no se sabe si la tecla entró.
BLOQUEO_SOSPECHOSO = 1.0
BLOQUEO_INACEPTABLE = 2.0
# Y cuánto puede tardar en hablar. Un anuncio que llega tarde es peor que uno
# que no llega: para entonces la persona ya pulsó otra cosa.
VOZ_LENTA = 1.5


def medir_accion(app: Aplicacion, hacer, espera: float = 3.0):
    """Hace algo y mide las dos cosas que producen «torpeza».

    La primera es cuánto tarda la ventana en volver a atender a nadie. Como la
    sonda despacha con `wx.CallAfter`, un `ping` que vuelve es la prueba de que
    el hilo de interfaz está libre otra vez; lo que tarde en volver es tiempo
    en el que la aplicación no responde a una tecla.

    La segunda es cuánto tarda en decir algo. Devuelve
    `(bloqueo, latencia_de_voz, lo_que_dijo)`, con la latencia en `None` si no
    llegó a hablar.
    """
    # Esperar a que la aplicación se calle ANTES de actuar. Si no, el primer
    # anuncio que llegue se le atribuye a la acción, y con una carga en vuelo
    # eso mide la red y no el control. El 21/08/2026 esto produjo tres fallos
    # contra un directo real que en la corrida siguiente no aparecieron.
    quieto = time.time() + 8
    ultimo = len(app.anuncios)
    calma = time.time() + 0.6
    while time.time() < quieto and time.time() < calma:
        if len(app.anuncios) != ultimo:
            ultimo = len(app.anuncios)
            calma = time.time() + 0.6
        time.sleep(0.05)

    antes = len(app.anuncios)
    t0 = time.time()
    hacer()
    app.pedir("ping", tiempo=120)
    bloqueo = time.time() - t0

    latencia = None
    limite = time.time() + espera
    while time.time() < limite:
        if any(a["canal"] == "voz" for a in app.anuncios[antes:]):
            latencia = time.time() - t0
            break
        time.sleep(0.05)
    dichos = [a["texto"] for a in app.anuncios[antes:] if a["canal"] == "voz"]
    return bloqueo, latencia, dichos


def juzgar_accion(res: Resultado, donde: str, que: str, medida) -> bool:
    """Convierte una medida en veredicto. Devuelve si habló."""
    bloqueo, latencia, dichos = medida
    if not dichos:
        res.fallo(f"{donde}: {que} no dice nada")
        hablo = False
    else:
        hablo = True
        detalle = dichos[0][:58]
        if latencia is not None and latencia > VOZ_LENTA:
            res.fallo(f"{donde}: {que} tarda {latencia:.1f} s en decir "
                      f"«{detalle}»")
        else:
            res.nota(f"{donde}: {que} dice «{detalle}»"
                     + (f", a los {latencia:.2f} s" if latencia else ""))

    if bloqueo > BLOQUEO_INACEPTABLE:
        res.fallo(f"{donde}: {que} deja la ventana {bloqueo:.1f} s sin responder")
    elif bloqueo > BLOQUEO_SOSPECHOSO:
        res.nota(f"{donde}: ojo, {que} tarda {bloqueo:.1f} s en devolver la "
                 f"ventana")
    return hablo


# Los seis botones de transporte, por la etiqueta con la que se los encuentra.
BOTONES_REPRODUCTOR = (
    ("Reproducir", "el botón de reproducir"),
    ("Retroceder 1 min", "el botón de retroceder"),
    ("Avanzar 1 min", "el botón de avanzar"),
    ("Detener", "el botón de detener"),
    ("Silenciar audio", "el botón de silenciar"),
    ("Pantalla completa", "el botón de pantalla completa"),
)

# Y los atajos, que son el camino que de verdad usa quien no ve la pantalla:
# `AGENTS.md` cuenta que los botones vienen ocultos justamente porque se maneja
# por teclado. Son los de `config.ATAJOS_DEFAULTS`, área Ctrl.
ATAJOS_REPRODUCTOR = (
    (("p", ["ctrl"]), "Ctrl+P, reproducir o pausa"),
    (("left", ["ctrl"]), "Ctrl+Izquierda, retroceder"),
    (("right", ["ctrl"]), "Ctrl+Derecha, avanzar"),
    (("m", ["ctrl"]), "Ctrl+M, silenciar"),
    (("up", ["ctrl"]), "Ctrl+Arriba, subir volumen"),
    (("down", ["ctrl"]), "Ctrl+Abajo, bajar volumen"),
    (("d", ["ctrl"]), "Ctrl+D, detener"),
)


def bateria_reproductor(app: Aplicacion, res: Resultado, donde: str,
                        hay_medio: bool = False) -> None:
    """Maltrata el reproductor entero y mide cada golpe.

    Se usa dos veces: sin nada cargado, que es como arranca la aplicación, y
    contra un directo de verdad desde `escenario_directo_youtube`. Las dos
    situaciones tienen que hablar; la segunda además tiene que ser rápida.
    `hay_medio` lo dice quien llama, que es quien cargó el medio: sin vídeo
    el volumen con flechas tiene que avisar y no moverse, con vídeo se mueve
    en silencio.
    """
    # ── los seis botones ────────────────────────────────────────────────────
    for etiqueta, quien in BOTONES_REPRODUCTOR:
        medida = medir_accion(app, lambda e=etiqueta: app.pedir("pulsar", nombre=e))
        juzgar_accion(res, donde, quien, medida)

        # Pantalla completa abre una ventana nueva que se queda con el foco y
        # con el teclado. Hay que volver, o todo lo que se mida después se mide
        # sobre la ventana equivocada.
        if etiqueta == "Pantalla completa":
            ctrl = app.foco() or {}
            nombre = (ctrl.get("nombre") or ctrl.get("etiqueta") or "").strip()
            if not nombre:
                res.fallo(f"{donde}: en pantalla completa el foco queda en un "
                          f"control sin nombre ({ctrl.get('clase')})")
            else:
                res.nota(f"{donde}: en pantalla completa el foco va a «{nombre}»")
            medida = medir_accion(
                app, lambda e=etiqueta: app.pedir("pulsar", nombre=e))
            juzgar_accion(res, donde, "salir de pantalla completa", medida)
            ctrl = app.foco() or {}
            nombre = (ctrl.get("nombre") or ctrl.get("etiqueta") or "").strip()
            if not nombre:
                res.fallo(f"{donde}: al salir de pantalla completa el foco "
                          f"queda en el aire ({ctrl.get('clase')})")
            else:
                res.nota(f"{donde}: al salir, el foco vuelve a «{nombre}»")

    # ── dos pulsaciones seguidas, que es lo que hace cualquiera cuando la
    #    primera no contestó ─────────────────────────────────────────────────
    antes = len(app.anuncios)
    app.pedir("pulsar", nombre="Reproducir")
    medida = medir_accion(app, lambda: app.pedir("pulsar", nombre="Reproducir"))
    if not medida[2]:
        res.fallo(f"{donde}: pulsar reproducir dos veces seguidas deja la "
                  f"segunda muda")
    else:
        res.nota(f"{donde}: la segunda pulsación de reproducir también habla")
    del antes

    # ── los siete atajos ────────────────────────────────────────────────────
    # Antes de juzgar los atajos hay que saber si el menú que los sostiene está
    # encendido. `gui.py:1769` apaga el menú Reproductor entero mientras no hay
    # conexión (`mb.EnableTop`), y un menú apagado se lleva por delante a sus
    # siete aceleradores aunque cada ítem se declare habilitado. Sin esto, el
    # banco daba siete atajos por rotos cuando lo que pasaba es que estaban
    # apagados a propósito.
    menu_vivo = None
    for m in app.menus():
        if m["camino"].strip().lower() == "reproductor":
            menu_vivo = bool(m.get("habilitado"))
            break
    if menu_vivo is False:
        res.nota(f"{donde}: el menú Reproductor está apagado, así que sus siete "
                 f"atajos no pueden funcionar")
        # Y ahí está lo que sí es un defecto: los botones de la ventana siguen
        # encendidos y respondiendo. Dos caminos para lo mismo, uno vivo y otro
        # muerto, sin que nada se lo diga a quien no ve la pantalla.
        encendidos = [c.get("etiqueta") or c.get("nombre")
                      for c in app.arbol()
                      if c.get("clase") in ("Button", "BitmapButton")
                      and c.get("habilitado") and c.get("en_pantalla")
                      and (c.get("etiqueta") or "") in
                      [e for e, _ in BOTONES_REPRODUCTOR]]
        if encendidos:
            res.fallo(f"{donde}: con el menú Reproductor apagado, sus atajos no "
                      f"hacen nada pero estos botones siguen encendidos y "
                      f"funcionando: " + ", ".join(encendidos))

    # Los aceleradores solo llegan si el foco está DENTRO de un control, no en
    # el frame. Se ancla a propósito para que el resultado no dependa de dónde
    # lo haya dejado la comprobación anterior.
    for candidato in ("Volumen del reproductor", "URL", "Chat en vivo"):
        try:
            app.pedir("foco", nombre=candidato)
            break
        except OrdenRechazada:
            continue

    for combo, quien in ATAJOS_REPRODUCTOR:
        try:
            medida = medir_accion(app, lambda c=combo: app.teclas(c))
        except VentanaNoActiva as exc:
            res.no_probado(f"{donde}: no se pudo probar {quien}, {exc}")
            continue
        if menu_vivo is False:
            if medida[2]:
                res.nota(f"{donde}: {quien} habla aun con el menú apagado")
            continue
        juzgar_accion(res, donde, quien, medida)

    # ── los dos deslizadores, con las flechas ───────────────────────────────
    # La posición anuncia; el volumen NO, a propósito desde el 15/10: NVDA
    # ya lee el valor del deslizador y se oía dos veces. La excepción, a
    # propósito desde el 19/10/2026: sin vídeo cargado `ajustar_volumen`
    # avisa «No hay ningún vídeo cargado» y no cambia nada.
    try:
        app.pedir("foco", nombre="Posición de reproducción")
    except OrdenRechazada as exc:
        res.fallo(f"{donde}: no se llega a la posición, {exc}")
    else:
        for tecla in ("right", "left"):
            try:
                medida = medir_accion(app, lambda t=tecla: app.teclas(t))
            except VentanaNoActiva as exc:
                res.no_probado(f"{donde}: no se pudo probar la posición, {exc}")
                break
            juzgar_accion(res, donde, f"la posición con la flecha {tecla}",
                          medida)
    try:
        app.pedir("foco", nombre="Volumen del reproductor")
    except OrdenRechazada as exc:
        res.fallo(f"{donde}: no se llega al volumen, {exc}")
    else:
        for tecla in ("up", "down"):
            previo = _valor_deslizador(app, "Volumen del reproductor")
            try:
                medida = medir_accion(app, lambda t=tecla: app.teclas(t))
            except VentanaNoActiva as exc:
                res.no_probado(f"{donde}: no se pudo probar el volumen, {exc}")
                break
            _juzgar_volumen_silencioso(app, res, donde, tecla, medida, previo,
                                     hay_medio)


def _valor_deslizador(app: Aplicacion, nombre: str):
    """El valor de un deslizador, leído con la sonda. None si no se pudo."""
    objetivo = (nombre or "").strip().lower()
    try:
        controles = app.arbol()
    except Exception:
        return None
    for c in controles:
        if c.get("clase") != "Slider":
            continue
        junto = ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        if objetivo in junto.strip().lower():
            return c.get("valor")
    return None


def _juzgar_volumen_silencioso(app: Aplicacion, res: Resultado, donde: str,
                               tecla: str, medida, previo,
                               hay_medio: bool = False) -> None:
    """El volumen con flechas no anuncia y tiene que mover el deslizador.

    Sin vídeo cargado es al revés, a propósito desde el 19/10/2026:
    `ajustar_volumen` avisa «No hay ningún vídeo cargado» y no cambia nada.
    """
    bloqueo, _latencia, dichos = medida
    if hay_medio:
        if dichos:
            res.fallo(f"{donde}: el volumen con la flecha {tecla} anuncia "
                      f"«{dichos[0][:58]}», y no debería: NVDA ya lee el valor "
                      "del deslizador")
        else:
            res.nota(f"{donde}: el volumen con la flecha {tecla} no anuncia, "
                     "a propósito")
    elif any("No hay ningún vídeo cargado" in d for d in dichos):
        res.nota(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                 "avisa «No hay ningún vídeo cargado»")
    elif dichos:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  f"anuncia «{dichos[0][:58]}» en vez de avisar "
                  "«No hay ningún vídeo cargado»")
    else:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  "no avisa «No hay ningún vídeo cargado»")
    if bloqueo > BLOQUEO_INACEPTABLE:
        res.fallo(f"{donde}: el volumen con la flecha {tecla} deja la ventana "
                  f"{bloqueo:.1f} s sin responder")
    elif bloqueo > BLOQUEO_SOSPECHOSO:
        res.nota(f"{donde}: ojo, el volumen con la flecha {tecla} tarda "
                 f"{bloqueo:.1f} s en devolver la ventana")
    posterior = _valor_deslizador(app, "Volumen del reproductor")
    if previo is None or posterior is None:
        res.nota(f"{donde}: la sonda no leyó el valor del deslizador, así que "
                 f"el cambio con la flecha {tecla} queda sin comprobar")
    elif hay_medio:
        if posterior == previo:
            res.fallo(f"{donde}: el volumen con la flecha {tecla} no movió el "
                      f"deslizador (sigue en {previo})")
        else:
            res.nota(f"{donde}: el volumen con la flecha {tecla} mueve el "
                     f"deslizador de {previo} a {posterior}")
    elif posterior != previo:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  f"movió el deslizador de {previo} a {posterior}, "
                  "y no debería")
    else:
        res.nota(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                 f"deja el deslizador en {previo}, a propósito")


def escenario_reproductor(app: Aplicacion, args, res: Resultado):
    """El reproductor sin nada cargado, que es como arranca la aplicación.

    Nunca lo probó nadie: `reproductor.py` son 1.059 líneas con cinco pruebas,
    y las cinco son del parser de atajos. El recorrido de Tab lo pasaba de largo
    porque los seis botones vienen ocultos de fábrica.

    Va primero de todos los escenarios y no es capricho: en cuanto `chat` o
    `tiktok` simulan una sesión, el estado «sin nada cargado» no vuelve sin
    reiniciar, y el botón de reproducir pasa la comprobación por el motivo
    equivocado.

    La regla que se comprueba no admite matices: un control que se activa y no
    dice nada es indistinguible, para quien no ve la pantalla, de una
    aplicación colgada. Y uno que tarda dos segundos en contestar, también.
    """
    if not app.al_frente():
        res.nota("reproductor: Windows no puso la ventana al frente")

    # Sin python-vlc el panel no se construye: en su lugar va un aviso de una
    # línea. Juzgar los botones ahí daría seis fallos de accesibilidad que en
    # realidad son una dependencia que falta.
    todo = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                    for c in app.arbol())
    if "AvisoReproductor" in todo or "no disponible" in todo.lower():
        res.nota("reproductor: no hay panel; falta VLC o yt-dlp en este "
                 "entorno, así que no se juzga nada. Correlo con el intérprete "
                 "del proyecto, .venv/Scripts/python.exe")
        return

    # Los botones vienen ocultos («minimalista»), y ocultos wx los saca del
    # recorrido de Tab. Hay que mostrarlos para poder probarlos como los prueba
    # una persona. Se anota cómo estaban para dejarlo igual al terminar.
    # Se pregunta por la etiqueta del propio interruptor, que dice «Ocultar…»
    # cuando están visibles y «Mostrar…» cuando no. Mirar `en_pantalla` de los
    # botones no sirve: `IsShownOnScreen` da falso también cuando la ventana
    # está tapada o minimizada, y entonces el banco creía que estaban ocultos,
    # los ocultaba, y encima le dejaba la preferencia cambiada al dueño.
    estaban_visibles = any(
        (c.get("etiqueta") or "").lower().startswith("ocultar botones")
        for c in app.arbol())
    if not estaban_visibles:
        medida = medir_accion(
            app, lambda: app.pedir("pulsar", nombre="AlternarBotonesReproductor"))
        juzgar_accion(res, "reproductor", "mostrar los botones", medida)

    faltan = []
    visibles = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                        for c in app.arbol()).lower()
    for etiqueta, quien in BOTONES_REPRODUCTOR:
        if etiqueta.lower() not in visibles:
            faltan.append(quien)
    if faltan:
        res.fallo("reproductor: no aparecen " + ", ".join(faltan))
        return

    bateria_reproductor(app, res, "reproductor")

    orden = recorrer_tab(app, res, "reproductor", vueltas=12)
    res.nota("reproductor, orden de Tab, %d paradas: %s"
             % (len(orden), " > ".join(orden)))

    # Dejarlo como estaba: el banco no puede cambiarle la ventana al dueño. La
    # visibilidad de los botones se guarda en `config.ini`, así que sin esto
    # cada corrida le deja la aplicación distinta de como la encontró.
    if not estaban_visibles:
        app.pedir("pulsar", nombre="AlternarBotonesReproductor")


def escenario_principal(app: Aplicacion, args, res: Resultado):
    """La ventana con la que se encuentra alguien al abrir la aplicación."""
    app.pedir("frente")
    revisar_nombres(app.arbol(), res, "ventana principal")
    # Tab desde el frame no recorre nada: hay que empezar dentro, en un
    # control de verdad. En los diálogos no hace falta porque wx ya le da el
    # foco al primero al abrirlos.
    try:
        app.pedir("foco", nombre="URL")
    except Exception as exc:
        res.fallo(f"ventana principal: no pude enfocar el campo de URL, {exc}")
    orden = recorrer_tab(app, res, "ventana principal", vueltas=12)
    res.nota(f"orden de Tab, {len(orden)} paradas: " + " > ".join(orden))

    n = len(app.anuncios)
    app.teclas(("f2",))
    if app.esperar_dicho("desconectado", segundos=8, desde=n):
        res.nota("F2 anuncia el estado")
    else:
        res.fallo("F2 no anunció nada en 8 segundos")


def _atajo_descargas() -> tuple[tuple, str]:
    """El atajo de fábrica para abrir el gestor de descargas.

    Se lee de `config_predeterminada`, la misma fuente de los valores de
    fábrica que usa la aplicación, y se nombra con `atajo_legible`, que ya
    usa el banco para los atajos de música. Así no va escrito a mano: con
    el mapa por familias pasó de Ctrl+S a Ctrl+Mayús+D. Devuelve el paso
    para `teclas` y el nombre legible para el informe.
    """
    texto = "ctrl+shift+d"
    try:
        from ytchat.core import config_predeterminada
        texto = (config_predeterminada.obtener(
            "atajos", "descargas_abrir", texto) or texto)
    except Exception:
        pass
    try:
        from ytchat.ui.atajos_captura import atajo_legible
        legible = atajo_legible(texto) or texto
    except Exception:
        legible = texto
    partes = (texto or "").strip().lower().replace(" ", "").split("+")
    tecla = partes[-1] if partes and partes[-1] else "d"
    mods = [p for p in partes[:-1] if p] or ["ctrl"]
    return (tecla, mods), legible


def escenario_descargas(app: Aplicacion, args, res: Resultado):
    """El gestor de descargas, que entró al repositorio sin que nadie lo abra."""
    paso_atajo, nombre_atajo = _atajo_descargas()
    app.pedir("frente")
    # El foco tiene que estar DENTRO de un control, no en el frame, o el
    # acelerador no llega. Sin esto el escenario pasaba o fallaba segun que
    # otro escenario se hubiera corrido antes, que es la peor clase de prueba.
    try:    app.pedir("foco", nombre="URL")
    except Exception: pass
    app.teclas(paso_atajo)
    dlg = app.esperar_ventana("Gestor de descargas", segundos=12)
    if dlg is None:
        res.fallo(f"{nombre_atajo} no abrió el gestor de descargas")
        return
    res.nota(f"{nombre_atajo} abre «{dlg['titulo']}», clase {dlg['clase']}")

    controles = app.arbol("Gestor de descargas")
    revisar_nombres(controles, res, "descargas")

    juntos = " ".join(
        ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        for c in controles).lower()
    for esperado in ("formato", "bitrate", "carpeta", "cola", "cerrar"):
        if esperado not in juntos:
            res.fallo(f"descargas: no aparece nada llamado «{esperado}»")

    orden = recorrer_tab(app, res, "descargas", vueltas=14)
    res.nota(f"descargas, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden))

    app.pedir("cerrar_ventana", ventana="Gestor de descargas")
    if app.esperar_ventana("Gestor de descargas", segundos=3) is None:
        res.nota("descargas: el diálogo cierra")
    else:
        res.fallo("descargas: el diálogo no cerró")


def escenario_diagnostico(app: Aplicacion, args, res: Resultado):
    """¿El diagnóstico se está anunciando por voz? No debería.

    Es la regresión que reportó el dueño: cada 30 segundos el lector le lee el
    censo de hilos, y cuando salta el vigilante de bloqueo, una traza entera.
    El censo va cada `INTERVALO_CENSO_HILOS_S`, que son 30, así que hay que
    escuchar más que eso o la prueba no puede fallar.
    """
    res.nota("escuchando 35 segundos, más que el intervalo del censo")
    fin = time.time() + 35
    while time.time() < fin:
        time.sleep(1.0)

    marcas = ("HILOS vivos", "HILO inicia", "HILO termina",
              "INTERFAZ bloqueada", "ENTORNO")
    fugas = [a for a in app.anuncios
             if a["canal"] in ("voz", "braille")
             and any(m in a["texto"] for m in marcas)]
    if fugas:
        res.fallo(f"el diagnóstico se anuncia por voz: {len(fugas)} veces")
        for a in fugas[:3]:
            res.fallo(f"  se dijo: {a['texto'][:70]}")
    else:
        res.nota("el diagnóstico no se anuncia por voz")




def escenario_menus(app: Aplicacion, args, res: Resultado):
    """Todos los ítems de menú: que tengan texto, atajo anunciable y estado."""
    items = app.menus()
    if not items:
        res.fallo("no se pudo leer la barra de menú")
        return
    hojas = [i for i in items if not i.get("submenu")]
    res.nota(f"{len(items)} entradas de menú, {len(hojas)} accionables")

    sin_texto = [i for i in items if not i["etiqueta"].strip()]
    for i in sin_texto:
        res.fallo(f"menú: una entrada sin texto en «{i['camino']}»")

    # Un ítem que promete atajo y otro que hace lo mismo sin prometerlo es una
    # inconsistencia que el usuario paga aprendiendo dos veces.
    con_atajo = [i for i in hojas if i["acelerador"]]
    res.nota(f"{len(con_atajo)} ítems anuncian atajo en su etiqueta")

    repetidos: dict[str, list[str]] = {}
    for i in con_atajo:
        repetidos.setdefault(i["acelerador"].lower(), []).append(i["camino"])
    for atajo, donde in repetidos.items():
        if len(donde) > 1:
            res.fallo(f"menú: el atajo {atajo} está en {len(donde)} sitios: "
                      + ", ".join(donde))

    apagados = [i["camino"] for i in hojas if not i["habilitado"]]
    res.nota(f"sin conexión hay {len(apagados)} ítems deshabilitados")
    if apagados:
        res.nota("  " + ", ".join(apagados[:8]))


def escenario_preferencias(app: Aplicacion, args, res: Resultado):
    """Preferencias, donde `AGENTS.md` y el código no dicen lo mismo.

    El contrato afirma que el diálogo va sin paleta, porque colorear una
    casilla en Windows la convierte en botón owner-drawn y NVDA la lee como
    botón y sin estado. El código colorea nueve casillas y un radio. Acá se
    mira qué rol expone Windows de verdad, que es lo que zanja la discusión.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias: no se pudo abrir, {exc}")
        return
    dlg = app.esperar_ventana("Preferencias", segundos=15)
    if dlg is None:
        res.fallo("preferencias: no abrió")
        return
    res.nota(f"preferencias: abre, clase {dlg['clase']}")

    controles = app.arbol("Preferencias")
    revisar_nombres(controles, res, "preferencias")

    # Solo lo que está en pantalla: el resto vive en pestañas no seleccionadas
    # y Windows no lo expone, así que compararlo daría una diferencia falsa.
    casillas_wx = [c for c in controles
                   if c["clase"] == "CheckBox" and c.get("en_pantalla")]
    radios_wx = [c for c in controles
                 if c["clase"] in ("RadioButton", "RadioBox")
                 and c.get("en_pantalla")]
    res.nota(f"preferencias, pestaña visible: wx dice {len(casillas_wx)} "
             f"casillas y {len(radios_wx)} radios")

    roles = roles_segun_windows("Preferencias")
    if not roles:
        res.nota("preferencias: no se pudo leer el árbol de Windows, se salta "
                 "la comprobación de owner-drawn")
    else:
        vistos_casilla = roles.get("CheckBox", 0)
        vistos_radio = roles.get("RadioButton", 0)
        res.nota(f"preferencias: Windows expone {vistos_casilla} CheckBox y "
                 f"{vistos_radio} RadioButton")
        if casillas_wx and vistos_casilla < len(casillas_wx):
            res.fallo(
                "preferencias: wx creó %d casillas y Windows solo expone %d "
                "como CheckBox. Las que faltan se anuncian con otro rol, que "
                "es lo que avisa AGENTS.md sobre el color."
                % (len(casillas_wx), vistos_casilla))

    orden = recorrer_tab(app, res, "preferencias", vueltas=20)
    res.nota(f"preferencias, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden[:10]))

    # Y ahora el resto de las pestanas, una por una. Auditar solo la visible
    # dejaba fuera la pagina de atajos entera, que son veinte botones.
    try:
        respuesta = app.pedir("pestanas", ventana="Preferencias")
    except Exception as exc:
        res.nota(f"preferencias: no se pudieron listar las pestañas, {exc}")
        respuesta = {}
    if not respuesta.get("ok"):
        if respuesta:
            res.nota("preferencias: no se pudieron listar las pestañas, "
                     + str(respuesta.get("error", "sin motivo")))
        info = None
    else:
        info = respuesta.get("datos", {})
    if info:
        paginas = info.get("paginas", [])
        res.nota(f"preferencias: {len(paginas)} pestañas: "
                 + ", ".join(paginas))
        for i, nombre in enumerate(paginas):
            app.pedir("pestanas", ventana="Preferencias", indice=i)
            visibles = [c for c in app.arbol("Preferencias")
                        if c.get("en_pantalla")]
            revisar_nombres(visibles, res, f"preferencias/{nombre}")
            casillas = [c for c in visibles if c["clase"] == "CheckBox"]
            # Ojo con la diferencia, que ya produjo una alarma falsa el
            # 21/08/2026: `wx.RadioBox` es un CONTENEDOR, un solo control para
            # wx, y Windows expone sus opciones como varios RadioButton
            # sueltos. Compararlos juntos da siempre un desajuste inventado.
            radios = [c for c in visibles if c["clase"] == "RadioButton"]
            cajas_radio = [c for c in visibles if c["clase"] == "RadioBox"]
            # Sincronizar con un hecho, no con un reloj. Windows redibuja la
            # pestana nueva cuando le parece, y un `sleep` fijo daba dos
            # recuentos distintos en dos corridas seguidas: el 21/08/2026 eso
            # produjo una alarma que no era tal. Se espera a que el arbol de
            # accesibilidad muestre algo de ESTA pagina antes de contar nada.
            testigo = ""
            for c in visibles:
                texto = (c.get("etiqueta") or c.get("nombre") or "")
                texto = texto.replace("&", "").strip()
                if len(texto) > 6:
                    testigo = texto.lower()
                    break
            roles = {}
            limite_pag = time.time() + 10
            while time.time() < limite_pag:
                roles = roles_segun_windows("Preferencias")
                if not testigo:
                    break
                todos = [n.replace("&", "").strip().lower()
                         for lista in _ULTIMOS_NOMBRES.values() for n in lista]
                if any(testigo in n or n in testigo for n in todos if n):
                    break
                time.sleep(0.4)
            else:
                res.nota(f"preferencias/{nombre}: Windows no llegó a mostrar "
                         f"«{testigo[:40]}», no se juzgan los roles")
                roles = {}

            if roles and casillas and roles.get("CheckBox", 0) < len(casillas):
                res.fallo(
                    "preferencias/%s: wx creó %d casillas y Windows solo "
                    "expone %d como CheckBox"
                    % (nombre, len(casillas), roles.get("CheckBox", 0)))
            if roles and cajas_radio:
                sueltos = roles.get("RadioButton", 0) - len(radios)
                if sueltos <= 0:
                    # Nota y no fallo, a propósito. Esta misma cuenta dio la
                    # alarma del 21/08/2026 y el dueño la desmintió probándolo
                    # con NVDA: se lee bien. La medición depende de cuándo
                    # Windows termine de redibujar la pestaña, así que da
                    # números distintos en corridas seguidas. Mientras no se
                    # sepa medirla estable, no puede acusar a nadie.
                    res.nota(
                        "preferencias/%s: %d agrupación(es) de radios y Windows "
                        "no expone ninguna opción como RadioButton; la medida "
                        "es inestable y ya se desmintió con NVDA, así que no "
                        "cuenta como fallo" % (nombre, len(cajas_radio)))
                else:
                    res.nota(
                        "preferencias/%s: %d agrupación(es) de radios, y "
                        "Windows expone %d opciones como RadioButton pese al "
                        "color" % (nombre, len(cajas_radio), sueltos))
            if roles and radios and roles.get("RadioButton", 0) < len(radios):
                vistos = {n.replace("&", "").strip().lower()
                          for n in nombres_segun_windows("RadioButton")}
                ausentes = [
                    (c.get("etiqueta") or c.get("nombre") or "?").replace("&", "")
                    for c in radios
                    if (c.get("etiqueta") or c.get("nombre") or ""
                        ).replace("&", "").strip().lower() not in vistos]
                res.fallo(
                    "preferencias/%s: wx creó %d radios y Windows solo expone "
                    "%d como RadioButton. No aparece: %s"
                    % (nombre, len(radios), roles.get("RadioButton", 0),
                       ", ".join(ausentes) or "no se pudo emparejar por nombre"))
                for rol_otro in ("Button", "Group", "Custom", "Pane", "Text"):
                    for n in nombres_segun_windows(rol_otro):
                        if n and any(n.replace("&", "").strip().lower()
                                     == a.strip().lower() for a in ausentes):
                            res.nota("  Windows lo expone como %s" % rol_otro)

    app.pedir("cerrar_ventana", ventana="Preferencias")


def escenario_preferencias_categorias(app: Aplicacion, args, res: Resultado):
    """Las 13 categorías de Preferencias, una por una.

    El escenario `preferencias` audita solo la categoría a la vista. Acá se
    recorre cada pestaña y se auditan sus controles visibles con Tab, sin
    tocar ningún valor y cerrando sin guardar.

    Solo se anota cuántas paradas tuvo cada categoría, sin listarlas: en
    «API y sesión» los campos muestran la clave y el secreto del dueño, y
    eso no puede quedar en el informe ni en la terminal.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias_categorias: no se pudo abrir, {exc}")
        return
    if app.esperar_ventana("Preferencias", segundos=15) is None:
        res.fallo("preferencias_categorias: Preferencias no abrió")
        return
    try:
        respuesta = app.pedir("pestanas", ventana="Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias_categorias: no se pudieron listar las "
                  f"pestañas, {exc}")
        app.pedir("cerrar_ventana", ventana="Preferencias")
        return
    paginas = respuesta.get("datos", {}).get("paginas", [])
    if len(paginas) < 13:
        res.fallo(f"preferencias_categorias: hay {len(paginas)} categorías, "
                  f"se esperaban 13")
    if any(n.strip().lower() in ("diagnóstico", "diagnostico")
           for n in paginas):
        res.fallo("preferencias_categorias: existe la categoría "
                  "«Diagnóstico», que ya no debería existir")
    if paginas and paginas[0].strip().lower() != "general":
        res.fallo(f"preferencias_categorias: la primera categoría es "
                  f"«{paginas[0]}» y debería ser «General»")
    try:
        for i, nombre in enumerate(paginas):
            app.pedir("pestanas", ventana="Preferencias", indice=i)
            time.sleep(0.8)
            visibles = [c for c in app.arbol("Preferencias")
                        if c.get("en_pantalla")]
            revisar_nombres(visibles, res, f"Preferencias/{nombre}")
            orden = recorrer_tab(app, res, f"Preferencias/{nombre}",
                                 vueltas=40, ventana="Preferencias")
            res.nota(f"Preferencias/{nombre}: {len(orden)} paradas de Tab")
            if len(orden) < 3:
                res.fallo(f"Preferencias/{nombre}: solo {len(orden)} paradas "
                          f"de Tab, la categoría quedó sin contenido "
                          f"alcanzable")
    finally:
        app.pedir("cerrar_ventana", ventana="Preferencias")


def _sonido_inicio_guardado_en_disco() -> str:
    """El valor de `[ui] sonido_inicio` en el `config.ini` real, en minúsculas."""
    import configparser
    try:
        from ytchat.core import paths
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(paths.config_ini(), encoding="utf-8")
        return parser.get("ui", "sonido_inicio", fallback="").strip().lower()
    except Exception:
        return ""


def escenario_preferencias_persisten(app: Aplicacion, args, res: Resultado):
    """Una preferencia cambiada y guardada se conserva al reabrir Preferencias.

    Invierte la casilla «Reproducir el sonido de inicio» (General, clave
    `[ui] sonido_inicio`), guarda, comprueba el `config.ini` y reabre para
    comprobar que la casilla muestra el valor invertido. Restaura el valor
    original en un `finally`, como `escenario_transmitir_destino`.
    """
    NOMBRE_CASILLA = "Reproducir el sonido de inicio"
    previo_txt = _sonido_inicio_guardado_en_disco()
    previo = previo_txt in ("true", "yes", "1", "on")
    invertido = not previo
    esperado_txt = "true" if invertido else "false"
    try:
        app.pedir("frente")
        try:
            app.abrir_por_menu("Preferencias")
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudo abrir, {exc}")
            return
        if app.esperar_ventana("Preferencias", segundos=15) is None:
            res.fallo("preferencias_persisten: Preferencias no abrió")
            return
        try:
            paginas = app.pedir("pestanas", ventana="Preferencias").get(
                "datos", {}).get("paginas", [])
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudieron listar las "
                      f"pestañas, {exc}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        try:
            indice = next(i for i, n in enumerate(paginas)
                          if n.strip().lower() == "general")
        except StopIteration:
            res.fallo(f"preferencias_persisten: no existe la categoría "
                      f"«General»; hay {paginas}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        app.pedir("pestanas", ventana="Preferencias", indice=indice)
        time.sleep(0.8)
        # La casilla se invierte con la orden `casilla`, sin teclas del
        # sistema: `pulsar` manda un evento de botón que no alterna
        # casillas, y `teclas` exige que Windows deje la app al frente.
        try:
            app.pedir("casilla", ventana="Preferencias", nombre=NOMBRE_CASILLA)
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudo invertir la "
                      f"casilla «{NOMBRE_CASILLA}», {exc}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        time.sleep(0.5)
        # Guardar se pulsa por su `name=`, como los botones de `captura_atajo`.
        app.pedir("pulsar", nombre="GuardarPreferencias")
        if app.esperar_ventana("Preferencias", segundos=4) is not None:
            res.fallo("preferencias_persisten: «Guardar» no cerró Preferencias")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        en_disco = _sonido_inicio_guardado_en_disco()
        if en_disco != esperado_txt:
            res.fallo(f"preferencias_persisten: el config.ini dice "
                      f"«{en_disco or 'vacío'}» y debería decir "
                      f"«{esperado_txt}»")
        else:
            res.nota(f"preferencias_persisten: el config.ini quedó en "
                     f"«{esperado_txt}»")
        # Reabrir y comprobar que la casilla muestra el valor invertido.
        try:
            app.abrir_por_menu("Preferencias")
        except Exception as exc:
            res.fallo(f"preferencias_persisten: no se pudo reabrir, {exc}")
            return
        if app.esperar_ventana("Preferencias", segundos=15) is None:
            res.fallo("preferencias_persisten: al reabrir no abrió")
            return
        try:
            paginas = app.pedir("pestanas", ventana="Preferencias").get(
                "datos", {}).get("paginas", [])
            indice = next(i for i, n in enumerate(paginas)
                          if n.strip().lower() == "general")
            app.pedir("pestanas", ventana="Preferencias", indice=indice)
        except StopIteration:
            res.fallo(f"preferencias_persisten: al reabrir no existe la "
                      f"categoría «General»; hay {paginas}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        except Exception as exc:
            res.fallo(f"preferencias_persisten: al reabrir no se pudo ir a "
                      f"«General», {exc}")
            app.pedir("cerrar_ventana", ventana="Preferencias")
            return
        time.sleep(0.8)
        controles = app.arbol("Preferencias")
        casilla = next((c for c in controles
                        if c.get("clase") == "CheckBox"
                        and (c.get("nombre") or "") == NOMBRE_CASILLA), None)
        if casilla is None:
            res.fallo(f"preferencias_persisten: al reabrir no existe la "
                      f"casilla «{NOMBRE_CASILLA}»")
        elif "marcado" not in casilla:
            res.fallo("preferencias_persisten: la sonda no informa si la "
                      "casilla está marcada")
        elif bool(casilla.get("marcado")) != invertido:
            res.fallo(f"preferencias_persisten: al reabrir la casilla muestra "
                      f"«{'marcada' if casilla.get('marcado') else 'sin marcar'}» "
                      f"y debería mostrar "
                      f"«{'marcada' if invertido else 'sin marcar'}»")
        else:
            res.nota(f"preferencias_persisten: al reabrir la casilla muestra "
                     f"«{'marcada' if invertido else 'sin marcar'}»")
        app.pedir("cerrar_ventana", ventana="Preferencias")
    finally:
        try:
            from ytchat.core import paths
            from ytchat.core.config import guardar_opcion
            guardar_opcion(paths.config_ini(), "ui", "sonido_inicio",
                           "true" if previo else "false")
        except Exception as exc:
            res.nota("preferencias_persisten: no se pudo restaurar el valor "
                     f"original ({exc})")
        else:
            res.nota("preferencias_persisten: el valor original vuelve a "
                     f"«{'true' if previo else 'false'}»")


def escenario_historial(app: Aplicacion, args, res: Resultado):
    """El historial de directos vistos."""
    auditar_dialogo(app, res, "Historial de directos", "Historial de directos",
                    vueltas_tab=12)


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
    """El diálogo que coloca el panel de chat dentro de una escena de OBS.

    Vale con OBS abierto y sin OBS. Sin él, el diálogo tiene que abrirse
    IGUAL, decir en su cuadro de estado por qué no puede hacer nada, y que sus
    controles se sigan anunciando: uno que se rinde y no abre deja a quien no
    ve sin saber qué pasó. Con OBS abierto se audita además con todos los
    controles habilitados, que es cuando el orden de Tab es completo.

    La fase 3 del smoke NO llega hasta acá: solo audita la pantalla
    desconectada. Esta es la única auditoría automática de esta superficie.
    """
    # Sin OBS los controles de OBS nacen deshabilitados a propósito, y wx saca
    # lo deshabilitado del orden de Tab. Exigirlos ahí mide la pantalla de
    # espera, no el diálogo. Medido el 29/09/2026.
    if obs_abierto():
        esperados_tab = ("Preparar el panel", "Fuente", "Escena",
                         "Poner al aire", "Posición del panel",
                         "Restablecer", "Transmitir", "Grabar")
    else:
        esperados_tab = ("Transmitir",)
        res.nota("Transmisión: OBS está cerrado, así que los controles de OBS "
                 "no se exigen en el orden de Tab")
    auditar_dialogo(
        app, res, "Transmisión", "Transmisión",
        vueltas_tab=VUELTAS_TAB_TRANSMISION,
        esperados=("Estado del panel", "Actualizar estado", "Preparar el panel", "Escena",
                   "Poner al aire", "Fuente",
                   "Posición del panel", "Ancho del panel", "Alto del panel",
                   "Aplicar tamaño", "Mostrar el panel", "Fijar el panel",
                   "Poner al frente", "Ajuste fino", "captura", "lienzo",
                   "Restablecer", "Transmitir", "Grabar", "Pausar la grabación",
                   "Cerrar"),
        # Arranca deshabilitado sin grabación y wx lo saca del orden de Tab.
        esperados_en_tab=esperados_tab)


def escenario_musica(app: Aplicacion, args, res: Resultado):
    """La ventana de música, abierta por sus dos entradas del menú.

    Sin carpeta ningún control queda deshabilitado: «Cambiar carpeta» solo
    se apaga mientras carga y `_al_biblioteca` lo vuelve a habilitar, así
    que los ocho entran en el orden de Tab. No se pulsa Reproducir ni
    ningún atajo de reproducción, y si la configuración trae una carpeta de
    música real no se toca: la ventana solo se abre, se audita y se cierra.
    """
    res.nota("Música: no se reproduce nada, la ventana solo se audita")
    esperados = ("Colecciones", "Buscar en la música", "Canciones",
                 "Mostrar la cola", "Abrir enlace", "Nueva lista",
                 "Cambiar carpeta", "Cerrar")
    auditar_dialogo(
        app, res, "Elegir música…", "Música",
        vueltas_tab=14,
        esperados=esperados,
        esperados_en_tab=esperados)


def escenario_ia(app: Aplicacion, args, res: Resultado):
    """La ventana Preguntar a la IA, abierta desde el menú Ver.

    Solo se abre, se audita y se cierra: no se envía nada, no se pulsa
    Agregar captura ni se toca la casilla. Agregar captura no se abre
    en el banco: necesita OBS.
    """
    res.nota("IA: no se envía nada, la ventana solo se audita. "
             "Agregar captura no se abre en el banco: necesita OBS")
    esperados = ("Conversación", "Mensaje",
                 "Enviar", "Agregar captura", "Copiar respuesta",
                 "Nueva conversación", "Cerrar")
    auditar_dialogo(
        app, res, "Preguntar a la IA sobre la imagen…", "Preguntar a la IA",
        vueltas_tab=14,
        esperados=esperados,
        esperados_en_tab=esperados)


def escenario_musica_real(app: Aplicacion, args, res: Resultado):
    """Música real de punta a punta, con archivos y sonido de verdad.

    Prepara una carpeta temporal con 5 temas de la música del usuario más
    un tono corto generado, respalda la configuración y las listas, fija
    volumen 10 y corre cada comando de música comprobando con el medidor
    de sonido de Windows que de verdad empieza, se pausa, sigue y se
    detiene. Al terminar deja los datos del usuario exactamente como
    estaban. Usa `tecla_en` y `menu_contextual` para disparar las acciones
    de la ventana nueva por su cableado real, filtra por el buscador, que
    deja el tema aislado seleccionado, y elige lo demás por posición por
    defecto.
    Corre ANTES de lanzar la aplicación compartida (como `arranque_frio`),
    porque la configuración se escribe antes de arrancar.
    """

    import array
    import configparser
    import math
    import random
    import re
    import shutil
    import tempfile
    import unicodedata
    import wave
    from ytchat.core import paths
    from ytchat.core.config import (
        codificar_texto_ini, decodificar_texto_ini, guardar_opciones)
    from ytchat.music import anuncios as anuncios_musica
    from ytchat.music import enlaces as enlaces_musica
    from ytchat.music import listas as listas_musica
    from ytchat.music import vista as vista_musica
    from ytchat.music.biblioteca import EXTENSIONES
    from tests.test_musica_enlaces import LISTA as _LISTA_PRUEBA
    from tests.test_musica_enlaces import VIDEO as _VIDEO_PRUEBA

    class _Corte(Exception):
        """La escena no puede seguir (el fallo ya quedó anotado)."""

    _NOMBRE_LISTA = "QA música real"
    _TOPE_RECORRIDO = 6 * 60
    _URL_VIDEO = f"https://www.youtube.com/watch?v={_VIDEO_PRUEBA}"
    _URL_LISTA = ("https://www.youtube.com/playlist"
                  f"?list={_LISTA_PRUEBA}")

    def _corta(texto):
        res.fallo(texto)
        raise _Corte()

    def _plegar(texto):
        descompuesto = unicodedata.normalize("NFKD", texto)
        return "".join(c for c in descompuesto
                       if not unicodedata.combining(c)).casefold()

    if medidor_sonido is None or not medidor_sonido.DISPONIBLE:
        res.no_probado("musica_real: sin medidor de sonido en esta PC")
        return

    # ── Origen: carpeta pedida, la de la configuración o la del usuario ──

    pedida = (getattr(args, "carpeta_musica", None) or "").strip()
    if pedida:
        origen = Path(pedida).expanduser()
    else:
        origen = None
        try:
            lector = configparser.ConfigParser(interpolation=None)
            lector.read(paths.config_ini(), encoding="utf-8")
            cruda = lector.get("musica", "carpeta", fallback="").strip()
            if cruda:
                origen = Path(decodificar_texto_ini(cruda))
        except Exception:
            origen = None
        if origen is None:
            origen = Path.home() / "Music"
    if not origen.is_dir():
        res.no_probado(f"musica_real: no hay carpeta de música en «{origen}»")
        return
    candidatos = sorted(
        (p for p in origen.rglob("*")
         if p.is_file() and p.suffix.lower() in EXTENSIONES),
        key=lambda p: str(p).lower())
    if len(candidatos) < 5:
        res.no_probado(f"musica_real: la carpeta «{origen}» tiene "
                       f"{len(candidatos)} temas y hacen falta 5")
        return
    elegidos = random.Random(18102026).sample(candidatos, 5)
    nombres_archivo = ([f"{i + 1:02d} {f.name}" for i, f in enumerate(elegidos)]
                       + ["06 corto QA.wav"])
    plegados = [_plegar(n) for n in nombres_archivo]
    if any(", " in Path(nombre).stem for nombre in nombres_archivo):
        res.no_probado(
            "musica_real: un tema elegido tiene una coma en el nombre y no "
            "se puede separar el título del artista y la duración")
        return

    # ── Rutas que se tocan (solo lectura acá, se escriben en el `try`) ──

    ruta_config = paths.config_ini()
    ruta_listas = paths.listas_musica()
    ruta_estado = paths.estado_musica()
    ruta_etiquetas = paths.cache_etiquetas_musica()

    tmp_musica = None
    tmp_respaldo = None
    respaldo_config = None
    respaldo_estado = None
    respaldo_etiquetas = None
    listas_habia = False
    propia = None

    def _agujas_unicas(indice, tope=6):
        objetivo = plegados[indice]
        otros = [n for j, n in enumerate(plegados) if j != indice]
        vistas = []
        for longitud in range(len(objetivo), 2, -1):
            for inicio in range(len(objetivo) - longitud + 1):
                aguja = objetivo[inicio:inicio + longitud]
                if aguja not in vistas and all(aguja not in otro
                                               for otro in otros):
                    vistas.append(aguja)
                    if len(vistas) >= tope:
                        return vistas
        return vistas

    def _aguja_grupo(incluidos, excluidos):
        def _pedazos(texto):
            actual = []
            for caracter in texto:
                actual.append(caracter if caracter.isalnum() else " ")
            return {t for t in "".join(actual).split() if len(t) >= 2}
        comunes = set.intersection(
            *[_pedazos(plegados[i]) for i in incluidos])
        for aguja in sorted(comunes, key=len, reverse=True):
            if all(aguja not in plegados[i] for i in excluidos):
                return aguja
        return None

    try:
        # ── Carpeta temporal con los 6 temas ──

        tmp_musica = Path(tempfile.mkdtemp(prefix="qa-musica-"))
        tmp_respaldo = Path(tempfile.mkdtemp(prefix="qa-musica-respaldo-"))
        for i, fuente in enumerate(elegidos):
            shutil.copy2(fuente, tmp_musica / nombres_archivo[i])
        with wave.open(str(tmp_musica / "06 corto QA.wav"), "w") as oleada:
            oleada.setnchannels(1)
            oleada.setsampwidth(2)
            oleada.setframerate(44100)
            muestras = array.array(
                "h", (int(16383 * math.sin(2 * math.pi * 440 * i / 44100))
                      for i in range(44100 * 3)))
            oleada.writeframes(muestras.tobytes())

        # ── Respaldo en otra carpeta temporal ──

        if ruta_config.is_file():
            respaldo_config = ruta_config.read_bytes()
            (tmp_respaldo / "config.ini").write_bytes(respaldo_config)
        if ruta_listas.is_dir():
            listas_habia = True
            shutil.copytree(ruta_listas, tmp_respaldo / "listas")
        if ruta_estado.is_file():
            respaldo_estado = ruta_estado.read_bytes()
            (tmp_respaldo / "musica_estado.json").write_bytes(respaldo_estado)
        if ruta_etiquetas.is_file():
            respaldo_etiquetas = ruta_etiquetas.read_bytes()
            (tmp_respaldo / "etiquetas_musica.json").write_bytes(
                respaldo_etiquetas)

        # ── Solo las claves de música necesarias ──

        cambios = [
            ("musica", "carpeta", codificar_texto_ini(str(tmp_musica))),
            ("musica", "volumen", "10"),
            ("musica", "aleatorio", "false"),
            ("musica", "repetir", "false"),
            ("musica", "retomar", "false"),
            ("musica", "decir", "titulo"),
            ("musica", "decir_pausa", "true"),
            ("musica", "sonido_tema", "true"),
            ("musica", "preguntar_igualar", "false"),
            ("musica", "mostrar_cola", "false"),
            ("musica", "atajos_globales", "false"),
        ]
        if ruta_config.is_file():
            if not guardar_opciones(ruta_config, cambios):
                _corta("musica_real: no se pudo fijar la configuración "
                       "de música")
        else:
            nuevo = configparser.ConfigParser(interpolation=None)
            nuevo["musica"] = {clave: valor for _, clave, valor in cambios}
            with open(ruta_config, "w", encoding="utf-8") as f:
                nuevo.write(f)

        # ── Aplicación propia, con la sonda adentro ──

        propia = Aplicacion(app.anuncios_ruta.parent / "musica_real")
        propia.arrancar()
        if not propia.esperar_lista(segundos=60):
            _corta("musica_real: la aplicación no contestó al ping en 60 s")
        if not propia.dijo("grabador instalado"):
            _corta("musica_real: la sonda no dejó constancia; "
                   "podría estar hablando")
        try:
            pid_sonda = propia.pedir("pid").get("datos", {}).get("pid")
        except Exception as exc:
            _corta(f"musica_real: no se pudo leer el pid de la sonda: {exc}")
        if not isinstance(pid_sonda, int) or pid_sonda <= 0:
            _corta("musica_real: la sonda devolvió un pid inválido")
        pids = {propia.proceso.pid, pid_sonda}

        sin_salida = False

        # ── Atajos del recorrido ──

        def _arbol(ventana):
            return propia.arbol(ventana)

        def _filas(ventana, nombre):
            for control in _arbol(ventana):
                if (control.get("clase") == "ListBox"
                        and (control.get("nombre") or "") == nombre):
                    return list(control.get("items", []))
            return None

        def _filas_hasta(ventana, nombre, cantidad, segundos):
            limite = time.monotonic() + segundos
            while time.monotonic() < limite:
                filas = _filas(ventana, nombre)
                if filas is not None and len(filas) == cantidad:
                    return filas
                time.sleep(0.2)
            return _filas(ventana, nombre)

        def _filas_estables(ventana, nombre, segundos=8.0):
            # Las etiquetas se leen en un hilo y cambian los títulos: se
            # espera a que se asienten antes de tomarlos como esperados.
            anteriores = _filas(ventana, nombre) or []
            limite = time.monotonic() + segundos
            while time.monotonic() < limite:
                time.sleep(1.2)
                actuales = _filas(ventana, nombre) or []
                if actuales and actuales == anteriores:
                    return actuales
                anteriores = actuales
            return anteriores

        def _titulo_fila(fila):
            # Quita el prefijo que pone `ytchat.music.vista.filas_cola`:
            # el estado («Sonando: » o «En pausa: »), el número y el punto.
            # La fila sigue con el título, el artista y la duración separados
            # por «, », así que el título es lo que queda antes de la primera.
            texto = fila
            for prefijo in ("Sonando: ", "En pausa: "):
                if texto.startswith(prefijo):
                    texto = texto[len(prefijo):]
                    break
            punto = texto.find(". ")
            if punto > 0 and texto[:punto].isdigit():
                texto = texto[punto + 2:]
            return texto.split(", ", 1)[0]

        def _filtrar(ventana, texto):
            propia.pedir("foco", ventana=ventana,
                         nombre="Buscar en la música")
            propia.pedir("texto", valor=texto)

        def _pico():
            try:
                return medidor_sonido.pico(pids)
            except Exception:
                return None

        def _menu(etiqueta):
            try:
                propia.abrir_por_menu(etiqueta)
            except Exception as exc:
                _corta(f"musica_real: el menú no tiene «{etiqueta}»: {exc}")

        def _elegir(ventana, nombre, indice):
            propia.pedir("elegir", ventana=ventana, nombre=nombre,
                         indice=indice)

        def _menu_contextual(ventana, nombre, entrada, responder_ya=False):
            propia.pedir("menu_contextual", ventana=ventana, nombre=nombre,
                         entrada=entrada, responder_ya=responder_ya)

        def _aislar(indice, esperado):
            for aguja in _agujas_unicas(indice):
                _filtrar("Música", aguja)
                filas = _filas_hasta("Música", "Canciones", 1, 5.0)
                if filas is not None and len(filas) == 1:
                    titulo = _titulo_fila(filas[0])
                    if titulo != esperado:
                        _corta(f"musica_real: el buscador aisló "
                               f"«{filas[0]}» en vez de «{esperado}»")
                    return titulo
            _corta(f"musica_real: no se pudo aislar «{esperado}» "
                   "con el buscador")

        def _boton_aceptar(ventana):
            for control in _arbol(ventana):
                if control.get("clase") not in ("Button", "BitmapButton"):
                    continue
                texto = ((control.get("nombre") or "") + " "
                         + (control.get("etiqueta") or "")).lower()
                if ("aceptar" in texto or texto.strip() == "ok"
                        or " ok " in f" {texto} "):
                    return (control.get("nombre")
                            or control.get("etiqueta"))
            return None

        def _escribir_cuadro(ventana, valor):
            campo = next((c for c in _arbol(ventana)
                          if c.get("clase") == "TextCtrl"), None)
            if campo is None:
                _corta(f"musica_real: «{ventana}» no tiene cuadro de texto")
            nombre = campo.get("nombre") or campo.get("etiqueta")
            if nombre:
                try:
                    propia.pedir("foco", ventana=ventana, nombre=nombre)
                except Exception as exc:
                    _corta(f"musica_real: no se llega al cuadro de "
                           f"«{ventana}»: {exc}")
            propia.pedir("texto", valor=valor)
            for control in _arbol(ventana):
                if control.get("clase") == "TextCtrl":
                    if (control.get("valor") or "") == valor:
                        return
                    _corta(f"musica_real: el cuadro de «{ventana}» no tomó "
                           f"«{valor}»")

        def _pulsar_aceptar(ventana):
            nombre = _boton_aceptar(ventana)
            if nombre is None:
                _corta(f"musica_real: «{ventana}» no ofrece ningún botón "
                       "para aceptar")
            propia.pedir("pulsar", nombre=nombre, ventana=ventana)
            if propia.esperar_ventana(ventana, segundos=3) is not None:
                _corta(f"musica_real: «{ventana}» no cerró al aceptar")

        def _pulsar_y_cerrar(ventana, boton):
            propia.pedir("pulsar", nombre=boton, ventana=ventana)
            if propia.esperar_ventana(ventana, segundos=3) is not None:
                _corta(f"musica_real: «{ventana}» no cerró al pulsar "
                       f"«{boton}»")

        inicio = time.monotonic()
        tope = inicio + _TOPE_RECORRIDO

        def _aire():
            if time.monotonic() > tope:
                _corta("musica_real: se pasó de 6 minutos, "
                       "se corta el recorrido")
            return True

        # ── a. La ventana Música muestra los 6 temas ──

        _menu("elegir música")
        if propia.esperar_ventana("Música", segundos=15) is None:
            _corta("musica_real: «Elegir música» no abrió la ventana")
        res.nota("musica_real: abre «Música» desde el menú")
        filas = _filas_hasta("Música", "Canciones", 6, 30.0)
        if filas is None or len(filas) != 6:
            _corta(f"musica_real: la lista de temas tiene "
                   f"{len(filas) if filas is not None else 'nada'} "
                   "elementos en vez de 6")
        # La Cola arranca oculta de fábrica: se la muestra una sola vez con
        # su botón, que así también se prueba, antes de leerla o usarla.
        propia.pedir("pulsar", nombre="Mostrar la cola", ventana="Música")
        if _filas_hasta("Música", "Cola de reproducción", 0, 1.0) is None:
            _corta("musica_real: la Cola no responde tras mostrarla")
        # Con `--capturas`: la misma ventana, ahora con la cola visible. La
        # apertura con la cola oculta ya la capturó `esperar_ventana`.
        captor_musica = getattr(args, "captor", None)
        if captor_musica is not None:
            captor_musica.capturar(propia, "musica_real", "Música",
                                   extra="cola visible")

        # ── b. Reproducir todo: anuncia el título y se oye ──

        _aire()
        filas = _filas_estables("Música", "Canciones")
        titulo_primero = _titulo_fila(filas[0]) if filas else ""
        n = len(propia.anuncios)
        _elegir("Música", "Canciones", 0)
        _menu_contextual("Música", "Canciones",
                         "Reproducir todo desde aquí")
        anunciado = (bool(titulo_primero)
                     and propia.esperar_dicho(titulo_primero, segundos=10,
                                              desde=n))
        suena = False
        todo_none = True
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            valor = _pico()
            if valor is not None:
                todo_none = False
                if valor > 0.005:
                    suena = True
                    break
            time.sleep(0.1)
        if todo_none:
            sin_salida = True
            res.no_probado("musica_real: sin salida de audio en esta PC; "
                           "se siguen comprobando solo los anuncios y la cola")
        if not anunciado:
            res.fallo("musica_real: no se anunció el título del primer "
                      f"tema («{titulo_primero}»)")
        elif not sin_salida and not suena:
            res.fallo("musica_real: el primer tema no se oye "
                      "(pico bajo 10 s)")
        else:
            res.nota(f"musica_real: suena el primer tema "
                     f"(«{titulo_primero}»)")

        # ── c. Pausa y reanudación ──

        _aire()
        n = len(propia.anuncios)
        _menu("reproducir o pausar")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_PAUSA, segundos=8,
                                      desde=n):
            res.fallo("musica_real: pausar no anunció "
                      f"«{anuncios_musica.TEXTO_PAUSA}»")
        else:
            res.nota("musica_real: la pausa se anuncia")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: pausada y el pico no cayó "
                          "bajo 0,001 en 3 s")
        n = len(propia.anuncios)
        _menu("reproducir o pausar")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_REANUDADA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: reanudar no anunció "
                      f"«{anuncios_musica.TEXTO_REANUDADA}»")
        if not sin_salida:
            limite = time.monotonic() + 5
            suena = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor > 0.005:
                    suena = True
                    break
                time.sleep(0.1)
            if not suena:
                res.fallo("musica_real: reanudada y no volvió el sonido")

        # ── d. Siguiente y anterior, según la cola ──

        _aire()
        cola = _filas("Música", "Cola de reproducción") or []
        if len(cola) < 2:
            res.fallo("musica_real: la cola no trae dos temas y no se puede "
                      "probar siguiente ni anterior")
        else:
            primero = _titulo_fila(cola[0])
            segundo = _titulo_fila(cola[1])
            if not primero or not segundo:
                res.fallo("musica_real: la cola trae filas sin título y no "
                          "se puede probar siguiente ni anterior")
            else:
                n = len(propia.anuncios)
                _menu("siguiente canción")
                if propia.esperar_dicho(segundo, segundos=8, desde=n):
                    res.nota(f"musica_real: siguiente anuncia «{segundo}»")
                else:
                    res.fallo("musica_real: «Siguiente canción» no anunció "
                              f"«{segundo}»")
                n = len(propia.anuncios)
                _menu("canción anterior")
                reiniciado = False
                limite = time.time() + 8
                while time.time() < limite:
                    if propia.dijo(anuncios_musica.TEXTO_REINICIADO,
                                   desde=n):
                        reiniciado = True
                        break
                    if propia.dijo(primero, desde=n):
                        break
                    time.sleep(0.1)
                if reiniciado:
                    res.nota("musica_real: anterior reinició el tema")
                    n = len(propia.anuncios)
                    _menu("canción anterior")
                    if propia.esperar_dicho(primero, segundos=8, desde=n):
                        res.nota(f"musica_real: anterior anuncia «{primero}»")
                    else:
                        res.fallo("musica_real: «Canción anterior» no anunció "
                                  f"«{primero}»")
                elif propia.dijo(primero, desde=n):
                    res.nota(f"musica_real: anterior anuncia «{primero}»")
                else:
                    res.fallo("musica_real: «Canción anterior» no anunció "
                              f"«{primero}»")

        # ── e. Volumen: sube a 20 y vuelve a 10 ──

        _aire()
        n = len(propia.anuncios)
        _menu("subir el volumen")
        esperado = anuncios_musica.TEXTO_VOLUMEN.format(valor=20)
        if not propia.esperar_dicho(esperado, segundos=8, desde=n):
            res.fallo(f"musica_real: subir no anunció «{esperado}»")
        n = len(propia.anuncios)
        _menu("bajar el volumen")
        esperado = str(10)
        if not propia.esperar_dicho(esperado, segundos=8, desde=n):
            res.fallo(f"musica_real: bajar no anunció «{esperado}»")
        else:
            res.nota("musica_real: el volumen sube a 20 y vuelve a 10")

        # ── f. Qué suena contiene el título actual ──

        _aire()
        cola = _filas("Música", "Cola de reproducción") or []
        actual = next((f for f in cola if f.startswith("Sonando: ")), "")
        titulo_actual = _titulo_fila(actual) if actual else ""
        if not actual or not titulo_actual:
            res.fallo("musica_real: la cola no marca ningún tema actual y "
                      "no se puede probar qué suena")
        else:
            antes, despues = anuncios_musica.TEXTO_QUE_SUENA.split("{nombre}")
            posicion = cola.index(actual) + 1
            fragmento_titulo = antes + titulo_actual
            fragmento_tema = despues.format(posicion=posicion,
                                            total=len(cola))
            n = len(propia.anuncios)
            _menu("qué suena")
            if not propia.esperar_dicho(fragmento_titulo, segundos=8,
                                        desde=n):
                res.fallo("musica_real: «Qué suena» no dijo "
                          f"«{fragmento_titulo}»")
            else:
                limite = time.monotonic() + 8
                oido = ""
                while time.monotonic() < limite:
                    for dicho in propia.anuncios[n:]:
                        texto = dicho.get("texto", "")
                        if (fragmento_titulo.lower() in texto.lower()
                                and fragmento_tema.lower() in texto.lower()):
                            oido = texto
                            break
                    if oido:
                        break
                    time.sleep(0.1)
                if oido:
                    res.nota(f"musica_real: qué suena dice «{oido}»")
                elif not any(fragmento_tema.lower()
                             in d.get("texto", "").lower()
                             for d in propia.anuncios[n:]):
                    res.fallo("musica_real: «Qué suena» no dijo "
                              f"«{fragmento_tema}»")
                else:
                    res.fallo("musica_real: «Qué suena» dijo "
                              f"«{fragmento_titulo}» y «{fragmento_tema}» "
                              "pero nunca en el mismo anuncio")

        # ── f2. Atajos globales con otra ventana al frente ──

        import musica_globales
        musica_globales.probar_atajos_globales(propia, res, tmp_respaldo)

        # ── g. Orden aleatorio dos veces ──

        _aire()
        n = len(propia.anuncios)
        _menu("orden aleatorio")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_ALEATORIO_ON,
                                     segundos=8, desde=n):
            res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_ALEATORIO_ON}»")
        n = len(propia.anuncios)
        _menu("orden aleatorio")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_ALEATORIO_OFF,
                                     segundos=8, desde=n):
            res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_ALEATORIO_OFF}»")
        else:
            res.nota("musica_real: el orden aleatorio se anuncia "
                     "activado y desactivado")

        # ── h. El corto a continuación, suena y avanza solo ──

        _aire()
        _aislar(5, "06 corto QA")
        cola_antes = _filas("Música", "Cola de reproducción") or []
        n = len(propia.anuncios)
        propia.pedir("tecla_en", ventana="Música", nombre="Canciones",
                     tecla="enter", modificadores=["shift"])
        esperado = anuncios_musica.TEXTO_A_CONTINUACION.format(
            nombre="06 corto QA")
        if not propia.esperar_dicho(esperado, segundos=8, desde=n):
            res.fallo(f"musica_real: no se anunció «{esperado}»")
        cola = _filas("Música", "Cola de reproducción") or []
        if (len(cola) != len(cola_antes) + 1
                or _titulo_fila(cola[1]) != "06 corto QA"):
            res.fallo("musica_real: «06 corto QA» no quedó justo detrás "
                      "del actual en la cola")
        else:
            res.nota("musica_real: el corto queda justo detrás del actual")
        que_seguia = _titulo_fila(cola[2]) if len(cola) > 2 else ""
        n = len(propia.anuncios)
        _menu("siguiente canción")
        if not propia.esperar_dicho("06 corto QA", segundos=10, desde=n):
            res.fallo("musica_real: «Siguiente canción» no anunció el corto")
        elif que_seguia and propia.esperar_dicho(que_seguia, segundos=15,
                                                    desde=n):
            res.nota(f"musica_real: el corto sonó y avanzó solo "
                     f"a «{que_seguia}»")
        else:
            res.fallo("musica_real: el corto no avanzó solo al tema que "
                      f"seguía («{que_seguia}»)")
        _filtrar("Música", "")
        if _filas_hasta("Música", "Canciones", 6, 10.0) is None:
            _corta("musica_real: al limpiar el buscador no vuelven los 6")

        # ── i. El quinto a la cola ──

        _aire()
        filas = _filas_estables("Música", "Canciones") or []
        if len(filas) != 6:
            _corta("musica_real: la lista de temas no tiene 6 elementos")
        quinto = _titulo_fila(filas[4])
        _aislar(4, quinto)
        cola_antes = _filas("Música", "Cola de reproducción") or []
        propia.pedir("tecla_en", ventana="Música", nombre="Canciones",
                     tecla="enter", modificadores=["ctrl"])
        cola = _filas("Música", "Cola de reproducción") or []
        if (len(cola) != len(cola_antes) + 1
                or (quinto and _titulo_fila(cola[-1]) != quinto)):
            res.fallo("musica_real: la cola no creció en uno con el "
                      f"quinto («{quinto}»)")
        else:
            res.nota("musica_real: el quinto se agrega al final de la cola")
        _filtrar("Música", "")
        _filas_hasta("Música", "Canciones", 6, 10.0)

        # ── j. Reproducir ahora el tercero ──

        _aire()
        filas = _filas_estables("Música", "Canciones") or []
        if len(filas) != 6:
            _corta("musica_real: la lista de temas no tiene 6 elementos")
        tercero = _titulo_fila(filas[2])
        cola_antes = _filas("Música", "Cola de reproducción") or []
        # `reproducir_ahora` inserta el tema detrás del que suena, así que el
        # contrato está en esa fila y no en que la cola copie la carpeta:
        # comparar contra la carpeta medía el botón viejo «Reproducir este».
        indice_sonando = next((i for i, f in enumerate(cola_antes)
                               if f.startswith("Sonando: ")), None)
        n = len(propia.anuncios)
        # El Intro de verdad, no un EVT_KEY_DOWN armado a mano: el 19/10/2026
        # la lista de temas y la Cola quedaban mudas con el teclado de
        # Windows porque el diálogo se comía la tecla antes del control.
        try:
            propia.pedir("foco", ventana="Música", nombre="Canciones")
            _elegir("Música", "Canciones", 2)
            propia.teclas("enter")
        except VentanaNoActiva as exc:
            res.no_probado("musica_real: «Reproducir ahora» no se pudo probar "
                           f"con el teclado real: {exc}")
        else:
            if not tercero:
                res.fallo("musica_real: la tercera fila no tiene título y no "
                          "se puede probar «Reproducir ahora»")
            elif not propia.esperar_dicho(tercero, segundos=10, desde=n):
                res.fallo("musica_real: «Reproducir ahora» no anunció "
                          f"«{tercero}»")
            cola = _filas("Música", "Cola de reproducción") or []
            if not cola:
                res.fallo("musica_real: la cola está vacía tras "
                          "«Reproducir ahora»")
            elif len(cola) != len(cola_antes) + 1:
                res.fallo("musica_real: «Reproducir ahora» no agregó un tema "
                          "a la cola")
            elif indice_sonando is None:
                res.fallo("musica_real: antes de «Reproducir ahora» la cola "
                          "no marcaba ningún tema sonando")
            else:
                siguiente = cola[indice_sonando + 1: indice_sonando + 2]
                if (not siguiente or not siguiente[0].startswith("Sonando: ")
                        or _titulo_fila(siguiente[0]) != tercero):
                    res.fallo("musica_real: «Reproducir ahora» no dejó el "
                              "tercero sonando justo detrás del que sonaba")
                elif not sin_salida:
                    limite = time.monotonic() + 10
                    suena = False
                    while time.monotonic() < limite:
                        valor = _pico()
                        if valor is not None and valor > 0.005:
                            suena = True
                            break
                        time.sleep(0.1)
                    if not suena:
                        res.fallo("musica_real: el tercero no se oye")

        # ── k. Guardar la cola como lista y reproducirla ──

        _aire()
        cola = _filas("Música", "Cola de reproducción") or []
        cantidad_cola = len(cola)
        _elegir("Música", "Cola de reproducción", 0)
        try:
            _menu_contextual("Música", "Cola de reproducción",
                             "Guardar la cola como lista", responder_ya=True)
        except Exception:
            pass  # el cuadro es modal y se come la respuesta
        if propia.esperar_ventana("Nueva lista", segundos=10) is None:
            _corta("musica_real: no abrió «Nueva lista»")
        _escribir_cuadro("Nueva lista", _NOMBRE_LISTA)
        n = len(propia.anuncios)
        _pulsar_aceptar("Nueva lista")
        esperado = anuncios_musica.TEXTO_LISTA_GUARDADA.format(
            nombre=_NOMBRE_LISTA)
        if not propia.esperar_dicho(esperado, segundos=10, desde=n):
            res.fallo(f"musica_real: no se anunció «{esperado}»")
        ruta_lista = ruta_listas / (_NOMBRE_LISTA + ".m3u8")
        if not ruta_lista.is_file():
            res.fallo("musica_real: no existe el .m3u8 en la carpeta "
                      "de listas")
        else:
            try:
                guardados, _saltadas = listas_musica.cargar(
                    ruta_listas, _NOMBRE_LISTA)
            except Exception as exc:
                res.fallo(f"musica_real: no se pudo leer la lista "
                          f"guardada: {exc}")
            else:
                if len(guardados) != cantidad_cola:
                    res.fallo("musica_real: la lista guardada tiene "
                              f"{len(guardados)} entradas y la cola "
                              f"{cantidad_cola}")
                else:
                    res.nota("musica_real: la cola se guarda como lista "
                             f"con {cantidad_cola} entradas")
        # Agregar un tema de la biblioteca a la lista recién guardada, con
        # el submenú del menú de «Canciones».
        _elegir("Música", "Colecciones", 0)
        if _filas_hasta("Música", "Canciones", 6, 10.0) is None:
            _corta("musica_real: la biblioteca no mostró 6 temas para "
                   "agregar a la lista")
        _elegir("Música", "Canciones", 0)
        n = len(propia.anuncios)
        _menu_contextual("Música", "Canciones",
                         f"Agregar a una lista > {_NOMBRE_LISTA}")
        esperado = anuncios_musica.TEXTO_AGREGADO_A_LISTA.format(
            nombre=_NOMBRE_LISTA)
        if not propia.esperar_dicho(esperado, segundos=10, desde=n):
            res.fallo(f"musica_real: no se anunció «{esperado}»")
        cantidad_lista = cantidad_cola + 1
        try:
            agregados, _saltadas = listas_musica.cargar(
                ruta_listas, _NOMBRE_LISTA)
        except Exception as exc:
            res.fallo(f"musica_real: no se pudo leer la lista tras "
                      f"agregar: {exc}")
        else:
            if len(agregados) != cantidad_lista:
                res.fallo("musica_real: la lista quedó con "
                          f"{len(agregados)} entradas tras agregar y se "
                          f"esperaban {cantidad_lista}")
            else:
                res.nota("musica_real: se agregó un tema de la carpeta a "
                         "la lista")
        n = len(propia.anuncios)
        _menu("detener la música")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: detenida y el pico no cayó "
                          "bajo 0,001 en 3 s")
        esperadas = vista_musica.filas_colecciones(
            [_NOMBRE_LISTA], cantidad_biblioteca=len(nombres_archivo),
            cantidades={_NOMBRE_LISTA: cantidad_lista})
        import musica_colecciones
        fila_biblioteca = esperadas[0]
        fila_qa = esperadas[1]
        # `_filas_hasta` solo espera la cantidad (2) y vuelve enseguida con
        # «Biblioteca» sin contar: se espera la posición real de la lista
        # de QA, con el mismo plazo.
        limite_colecciones = time.monotonic() + 10.0
        elegidas = None
        indice_qa = None
        while time.monotonic() < limite_colecciones:
            elegidas = _filas("Música", "Colecciones")
            indice_qa = musica_colecciones.indice_coleccion_qa(
                elegidas, fila_biblioteca, fila_qa)
            if indice_qa is not None:
                break
            time.sleep(0.2)
        if indice_qa is None:
            _corta(f"musica_real: «Colecciones» ofrece {elegidas} en vez "
                   f"de {esperadas}")
        _elegir("Música", "Colecciones", indice_qa)
        filas = _filas_hasta("Música", "Canciones", cantidad_lista, 10.0)
        if filas is None or len(filas) != cantidad_lista:
            _corta("musica_real: la lista no trajo "
                   f"{cantidad_lista} temas a «Canciones»")
        # El Intro de verdad, como en el paso j, en lugar del menú
        # contextual: reproduce la lista elegida en «Colecciones».
        try:
            propia.pedir("foco", ventana="Música", nombre="Colecciones")
            _elegir("Música", "Colecciones", indice_qa)
            propia.teclas("enter")
        except VentanaNoActiva as exc:
            res.no_probado("musica_real: la lista no se pudo reproducir "
                           f"con el teclado real: {exc}")
        else:
            if not sin_salida:
                limite = time.monotonic() + 10
                suena = False
                while time.monotonic() < limite:
                    valor = _pico()
                    if valor is not None and valor > 0.005:
                        suena = True
                        break
                    time.sleep(0.1)
                if not suena:
                    res.fallo("musica_real: la lista no se oye")
            cola = _filas_hasta("Música", "Cola de reproducción",
                                cantidad_lista, 10.0) or []
            if len(cola) != cantidad_lista:
                res.fallo("musica_real: la cola tiene "
                          f"{len(cola)} entradas en vez de {cantidad_lista}")
            else:
                res.nota("musica_real: la lista suena con sus "
                         f"{cantidad_lista} entradas")
        _elegir("Música", "Colecciones", 0)
        if _filas_hasta("Música", "Canciones", 6, 10.0) is None:
            _corta("musica_real: al volver a la carpeta no aparecen 6 temas")

        # ── l. Agregar el enlace del vídeo: se oye ──

        _aire()
        n = len(propia.anuncios)
        _menu("detener la música")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: detenida y el pico no cayó "
                          "bajo 0,001 en 3 s")
        cola_antes = _filas("Música", "Cola de reproducción") or []
        try:
            propia.pedir("pulsar", nombre="Abrir enlace", responder_ya=True)
        except Exception:
            pass  # el cuadro es modal y se come la respuesta
        if propia.esperar_ventana("Abrir enlace", segundos=10) is None:
            _corta("musica_real: no abrió «Abrir enlace»")
        _escribir_cuadro("Abrir enlace", _URL_VIDEO)
        n = len(propia.anuncios)
        _pulsar_y_cerrar("Abrir enlace", "Agregar a la cola")
        if not propia.esperar_dicho(
                anuncios_musica.TEXTO_LEYENDO_ENLACE, segundos=10, desde=n):
            res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_LEYENDO_ENLACE}»")
        prefijo_agregado = anuncios_musica.TEXTO_AGREGADO_POSICION.split(",")[0]
        if not propia.esperar_dicho(prefijo_agregado, segundos=60, desde=n):
            dichos = " ".join(a.get("texto", "")
                              for a in propia.anuncios[n:])[-200:]
            res.fallo("musica_real: el vídeo no se agregó a la cola en "
                      f"60 s; dijo «{dichos}»")
        else:
            cola = _filas("Música", "Cola de reproducción") or []
            if len(cola) != len(cola_antes) + 1:
                res.fallo("musica_real: la cola no creció con el enlace")
            else:
                ultimo = _titulo_fila(cola[-1])
                if not ultimo:
                    res.fallo("musica_real: la última fila de la cola está "
                              "vacía y no se puede comprobar el vídeo")
                else:
                    visto = False
                    suena = False
                    limite = time.monotonic() + 10
                    while time.monotonic() < limite:
                        actual = (_filas("Música",
                                        "Cola de reproducción") or [])
                        if (len(actual) == len(cola_antes) + 1 and actual
                                and actual[-1].startswith("Sonando: ")
                                and _titulo_fila(actual[-1]) == ultimo):
                            visto = True
                        if not sin_salida:
                            valor = _pico()
                            if valor is not None and valor > 0.005:
                                suena = True
                        if visto and (sin_salida or suena):
                            break
                        time.sleep(0.2)
                    if not visto:
                        res.fallo("musica_real: la última fila de la cola "
                                  f"(«{ultimo}») no es lo que suena en 10 s")
                    elif sin_salida:
                        res.nota("musica_real: el vídeo se agrega a la cola")
                    elif not suena:
                        res.fallo("musica_real: el vídeo de YouTube no se oye")
                    else:
                        res.nota("musica_real: el vídeo de YouTube se oye")

        # ── m. Agregar el enlace de la lista ──

        _aire()
        try:
            propia.pedir("pulsar", nombre="Abrir enlace", responder_ya=True)
        except Exception:
            pass  # el cuadro es modal y se come la respuesta
        if propia.esperar_ventana("Abrir enlace", segundos=10) is None:
            _corta("musica_real: no abrió «Abrir enlace» por segunda vez")
        _escribir_cuadro("Abrir enlace", _URL_LISTA)
        n = len(propia.anuncios)
        _pulsar_y_cerrar("Abrir enlace", "Agregar a la cola")
        limite = time.monotonic() + 90
        agregados = 0
        lista_muerta = False
        patron_agregados = re.compile(
            re.escape(anuncios_musica.TEXTO_AGREGADOS).replace(
                re.escape("{cantidad}"), r"(\d+)"))
        while time.monotonic() < limite:
            for dicho in propia.anuncios[n:]:
                texto = dicho.get("texto", "")
                coincidencia = patron_agregados.search(texto)
                if coincidencia:
                    agregados = max(agregados, int(coincidencia.group(1)))
                if (enlaces_musica.TEXTO_NO_SE_PUDO_LEER.lower() in texto.lower()
                        or enlaces_musica.TEXTO_SIN_VIDEOS.lower() in texto.lower()):
                    lista_muerta = True
            if agregados >= 2 or lista_muerta:
                break
            time.sleep(0.5)
        if lista_muerta:
            res.no_probado("musica_real: la lista de prueba ya no existe "
                           "en YouTube: cambiarla")
        elif agregados < 2:
            res.fallo("musica_real: la lista no sumó 2 o más temas en 90 s")
        else:
            res.nota(f"musica_real: la lista sumó {agregados} temas")

        # ── n. Detener la música ──

        _aire()
        try:
            propia.pedir("cerrar_ventana", ventana="Música")
        except Exception:
            pass
        n = len(propia.anuncios)
        _menu("detener la música")
        if not propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                     segundos=8, desde=n):
            res.fallo("musica_real: al final detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
        if not sin_salida:
            limite = time.monotonic() + 3
            callado = False
            while time.monotonic() < limite:
                valor = _pico()
                if valor is not None and valor < 0.001:
                    callado = True
                    break
                time.sleep(0.1)
            if not callado:
                res.fallo("musica_real: al final el pico no cayó "
                          "bajo 0,001 en 3 s")
        else:
            res.nota("musica_real: recorrido completo sin salida de audio")
    except _Corte:
        pass
    except Exception as exc:
        res.fallo(f"musica_real: el recorrido reventó: {exc!r}")
    finally:
        if propia is not None:
            try:
                try:
                    propia.pedir("salir", tiempo=5.0, tolerar=True)
                except Exception:
                    pass
                try:
                    contestar_salir_si_aparece(segundos=2.0)
                except Exception:
                    pass
                limite = time.monotonic() + 15.0
                while (propia.proceso is not None
                       and propia.proceso.poll() is None
                       and time.monotonic() < limite):
                    time.sleep(0.5)
                if (propia.proceso is not None
                        and propia.proceso.poll() is None):
                    try:
                        propia.proceso.kill()
                    except Exception:
                        pass
                    res.nota("musica_real: la aplicación no cerró en 15 s "
                             "y se la mató")
            finally:
                try:
                    propia._salida.close()
                except Exception:
                    pass
        # La aplicación guarda al salir: se restaura DESPUÉS de cerrarla.
        try:
            if respaldo_config is None:
                try:
                    ruta_config.unlink()
                except FileNotFoundError:
                    pass
                if ruta_config.exists():
                    res.fallo("musica_real: config.ini no existía y no se "
                              "pudo borrar el creado")
            else:
                ruta_config.write_bytes(respaldo_config)
                if ruta_config.read_bytes() != respaldo_config:
                    res.fallo("musica_real: config.ini no quedó idéntico "
                              "al respaldo")
        except Exception as exc:
            res.fallo(f"musica_real: no se pudo restaurar config.ini: {exc}")
        try:
            shutil.rmtree(ruta_listas, ignore_errors=True)
            if listas_habia:
                shutil.copytree(tmp_respaldo / "listas", ruta_listas)
        except Exception as exc:
            res.fallo("musica_real: no se pudo restaurar la carpeta "
                      f"de listas: {exc}")
        for nombre, ruta, respaldo in (
                ("musica_estado.json", ruta_estado, respaldo_estado),
                ("etiquetas_musica.json", ruta_etiquetas,
                 respaldo_etiquetas)):
            try:
                if respaldo is None:
                    try:
                        ruta.unlink()
                    except FileNotFoundError:
                        pass
                    if ruta.exists():
                        res.fallo(f"musica_real: {nombre} no existía y no "
                                  "se pudo borrar el creado")
                else:
                    ruta.write_bytes(respaldo)
            except Exception as exc:
                res.fallo(f"musica_real: no se pudo restaurar {nombre}: "
                          f"{exc}")
        if tmp_musica is not None:
            shutil.rmtree(tmp_musica, ignore_errors=True)
        if tmp_respaldo is not None:
            shutil.rmtree(tmp_respaldo, ignore_errors=True)


def _estado_actualizacion_asentado(app: Aplicacion, titulo: str,
                                   segundos: float = 30.0) -> str:
    """Espera a que la ventana deje de decir que está buscando.

    Devuelve el texto del cuadro de estado, o cadena vacía si no se pudo
    leer. Si a los 30 segundos sigue buscando, se sigue igual con lo que
    haya: la búsqueda depende de la red, y una red lenta no es un defecto
    de la ventana.
    """
    estado = ""
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            controles = app.arbol(titulo)
        except Exception:
            time.sleep(0.5)
            continue
        for c in controles:
            if (c.get("nombre") or "") == "Estado":
                estado = c.get("valor") or ""
                break
        if estado and "buscando" not in estado.lower():
            break
        time.sleep(0.5)
    return estado


def _auditar_actualizacion(app: Aplicacion, res: Resultado, etiqueta_menu: str,
                           titulo: str) -> bool:
    """Abre una ventana de actualización, espera a que se asiente y la audita.

    Replica `auditar_dialogo`, con la espera en el medio: estas ventanas
    nacen buscando en un hilo aparte, y auditar en el primer instante mide
    la pantalla de espera, no la ventana. NUNCA pulsa el botón de acción:
    solo se cierra con `cerrar_ventana`.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu(etiqueta_menu)
    except Exception as exc:
        res.fallo(f"{titulo}: no se pudo disparar «{etiqueta_menu}», {exc}")
        return False

    dlg = app.esperar_ventana(titulo, segundos=15)
    if dlg is None:
        res.fallo(f"{titulo}: el menú no abrió ninguna ventana con ese título")
        return False
    res.nota(f"{titulo}: abre desde «{etiqueta_menu}», clase {dlg['clase']}")

    estado = _estado_actualizacion_asentado(app, titulo)
    if estado and "buscando" in estado.lower():
        res.nota(f"{titulo}: sigue buscando a los 30 s, se audita igual; "
                 f"dice «{estado[:70]}»")
    elif estado:
        res.nota(f"{titulo}: dice «{estado[:90]}»")
    else:
        res.nota(f"{titulo}: no se pudo leer el cuadro de estado")

    controles = app.arbol(titulo)
    revisar_nombres(controles, res, titulo)

    juntos = " ".join(
        ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        for c in controles).replace("&", "").lower()
    for e in ("Estado", "Progreso", "Novedades", "Cerrar"):
        if e.lower() not in juntos:
            res.fallo(f"{titulo}: no aparece nada llamado «{e}»")

    orden = recorrer_tab(app, res, titulo, vueltas=10, ventana=titulo)
    res.nota(f"{titulo}, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden[:12]))

    app.pedir("cerrar_ventana", ventana=titulo)
    if app.esperar_ventana(titulo, segundos=4) is not None:
        res.fallo(f"{titulo}: el diálogo no cerró")
    return True


def escenario_actualizaciones(app: Aplicacion, args, res: Resultado):
    """Las dos ventanas de actualización, que nadie recorría.

    Las dos usan el mismo `DialogoActualizacion` genérico: estado, progreso,
    novedades y cerrar. Cada una busca en un hilo aparte nada más abrir, así
    que se espera a que el estado se asiente antes de auditar. La búsqueda de
    yt-dlp puede dejar un binario preparado si hay versión nueva, pero
    instalarlo pide el botón de acción y ese no se pulsa nunca.
    """
    _auditar_actualizacion(app, res, "Buscar actualizaciones",
                           "Buscar actualizaciones")
    _auditar_actualizacion(app, res, "Actualizar yt-dlp", "Actualizar yt-dlp")


def _destino_guardado_en_disco() -> str:
    """El destino de transmisión que guarda el `config.ini`, o cadena vacía."""
    import configparser
    try:
        from ytchat.core import paths
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
             % (len(orden), " > ".join(orden[:10])))

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
            if any(t.strip() == "Transmisión" for t in visibles):
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
            res.fallo("transmitir_destino: «Continuar» llevó a «Transmisión», "
                      "o sea que el destino no era YouTube")
            app.pedir("cerrar_ventana", ventana="Transmisión")
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
                 % (len(orden), " > ".join(orden[:10])))
        # Se cierra con «Cancelar»: pulsar «Transmitir» crearía un directo.
        app.pedir("cerrar_ventana", ventana="Directo de YouTube")
        if app.esperar_ventana("Directo de YouTube", segundos=4) is not None:
            res.fallo("transmitir_destino: «Directo de YouTube» no cerró")
    finally:
        try:
            from ytchat.core import paths
            from ytchat.core.config import guardar_opcion
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


def escenario_ayuda(app: Aplicacion, args, res: Resultado):
    """El menú Ayuda, que abre ventanas de texto largo."""
    items = [i for i in app.menus()
             if not i.get("submenu") and i["camino"].startswith("Ayuda")]
    if not items:
        res.fallo("ayuda: el menú no tiene entradas accionables")
        return
    res.nota(f"ayuda: {len(items)} entradas: "
             + ", ".join(i["etiqueta"] for i in items))
    for i in items:
        if not i["habilitado"]:
            res.fallo(f"ayuda: «{i['etiqueta']}» está deshabilitado sin motivo")




def escenario_chat(app: Aplicacion, args, res: Resultado):
    """Una sesión de YouTube con mensajes, sin tocar la red.

    Se monta con la misma API pública que usa `main.py` desde el hilo de
    captura. Así se prueba la parte conectada de la interfaz sin depender de
    que haya un directo vivo ni de que la red se porte bien.
    """
    app.pedir("frente")

    # Este escenario mide el PASO de desconectado a conectado, asi que si llega
    # con la aplicacion ya conectada no falla por un defecto suyo: falla porque
    # otro escenario dejo puesta una sesion simulada. Se dice asi, con el
    # nombre del culpable a la vista, porque el 26/08/2026 el mismo fallo se
    # leyo como «conectar no anuncia nada» y se busco durante un rato en el
    # sitio equivocado.
    conectado_ya = any(
        i["habilitado"] for i in app.menus()
        if not i.get("submenu")
        and "desconectar" in (i.get("camino") or "").lower())
    if conectado_ya:
        res.fallo("chat: llegue con la aplicacion YA conectada. No es un "
                  "defecto de la aplicacion: algun escenario anterior simulo "
                  "una sesion y no llamo a `restaurar_desconectado`")
        return

    apagados_antes = len([i for i in app.menus()
                          if not i.get("submenu") and not i["habilitado"]])

    n = len(app.anuncios)
    app.simular_sesion_youtube(titulo="Directo de prueba QA", espectadores=137)
    if app.esperar_dicho("conectado", segundos=10, desde=n):
        res.nota("chat: conectar se anuncia")
    else:
        res.fallo("chat: conectar no anunció nada")

    apagados = [i["camino"] for i in app.menus()
                if not i.get("submenu") and not i["habilitado"]]
    res.nota(f"al conectar, los ítems apagados bajan de {apagados_antes} "
             f"a {len(apagados)}")
    if len(apagados) >= apagados_antes:
        res.fallo("chat: conectar no habilitó ningún ítem de menú")
    if apagados:
        res.nota("  siguen apagados: " + ", ".join(apagados))

    muestras = [
        ("Ana", "hola que tal el directo", "text", ""),
        ("Beto", "gracias por todo", "superchat", "5,00 US$"),
        ("Cora", "me hice miembro", "member", ""),
        ("Dani", "un sticker", "sticker", "2,00 US$"),
    ]
    for autor, texto, tipo, monto in muestras:
        app.mensaje(autor, texto, tipo=tipo, monto=monto)

    # El chat se vuelca agrupado, así que se espera a que aparezca en la lista
    # en vez de dar por hecho que ya está.
    limite = time.time() + 12
    lista = None
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and len(lista.get("items", [])) >= len(muestras):
            break
        time.sleep(0.3)

    if not lista:
        res.fallo("chat: no encontré la lista del chat")
        return
    items = lista.get("items", [])
    res.nota(f"chat: la lista tiene {len(items)} entradas tras enviar "
             f"{len(muestras)}")
    if len(items) < len(muestras):
        res.fallo(f"chat: se enviaron {len(muestras)} mensajes y llegaron "
                  f"{len(items)}")
    texto_junto = " ".join(str(i) for i in items).lower()
    for autor, _, _, _ in muestras:
        if autor.lower() not in texto_junto:
            res.fallo(f"chat: «{autor}» no aparece en la lista")
    for entrada in items[:4]:
        res.nota("  lee: " + str(entrada)[:70])

    # El monto del super chat tiene que verse: es el motivo de la función.
    if "5,00" not in texto_junto and "5.00" not in texto_junto:
        res.fallo("chat: el monto del super chat no aparece en la lista")

    orden = recorrer_tab(app, res, "principal conectada", vueltas=16)
    res.nota(f"conectado, Tab da {len(orden)} paradas: "
             + " > ".join(orden[:10]))


def escenario_tiktok(app: Aplicacion, args, res: Resultado):
    """La ruta de TikTok, que es distinta y comparte la misma lista."""
    app.pedir("frente")
    n = len(app.anuncios)
    app.simular_sesion_tiktok(usuario="rolon_100")
    if not app.esperar_dicho("conectado", segundos=10, desde=n):
        res.nota("tiktok: no anunció «conectado», puede usar otra frase")

    for autor, texto, tipo in (("Eva", "hola desde tiktok", "text"),
                               ("Fito", "entra al directo", "entrada")):
        app.mensaje(autor, texto, tipo=tipo)

    limite = time.time() + 12
    lista = None
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(0.3)
    if not lista or not lista.get("items"):
        res.fallo("tiktok: no llegó ningún mensaje a la lista")
        return
    res.nota(f"tiktok: {len(lista.get('items'))} entradas en la lista")

    # «Descargar este vídeo» va apagado en TikTok, por diseño.
    item = [i for i in app.menus() if "Descargar este" in i["camino"]]
    if item and item[0]["habilitado"]:
        res.fallo("tiktok: «Descargar este vídeo» quedó habilitado, y el "
                  "diseño dice que en TikTok va apagado")
    elif item:
        res.nota("tiktok: «Descargar este vídeo» correctamente apagado")


def escenario_comentarios(app: Aplicacion, args, res: Resultado):
    """El panel de comentarios, que hasta el 26/08/2026 no entraba en el banco.

    Va sin red a propósito: traer comentarios de verdad necesita clave de API y
    sesión iniciada, y eso ya lo cubren las pruebas de `youtube_api`. Lo que
    solo se puede comprobar con la aplicación viva es otra cosa: que los
    controles tengan nombre, que Tab los alcance, y que la lista diga algo
    cuando se pulsa sobre nada.
    """
    app.pedir("frente")

    respuesta = app.pedir("pestanas")
    if not respuesta.get("ok"):
        res.fallo("comentarios: no se pudieron listar las pestañas, "
                  + str(respuesta.get("error", "sin motivo")))
        return
    paginas = respuesta.get("datos", {}).get("paginas", [])
    if "Comentarios" not in paginas:
        res.fallo("comentarios: no hay ninguna pestaña «Comentarios»; hay "
                  + ", ".join(paginas))
        return
    pagina = paginas.index("Comentarios")
    app.pedir("pestanas", indice=pagina)

    visibles = _panel_comentarios(app)
    revisar_nombres(visibles, res, "comentarios")

    lista = _lista_de_comentarios(visibles)
    if lista is None:
        res.fallo("comentarios: no encontré la lista del panel")
        return
    res.nota("comentarios: la lista arranca con %d entradas"
             % len(lista.get("items", [])))

    # «Cargar más» sin ninguna página cargada tiene que estar apagado: si
    # figura encendido, invita a pulsar algo que no puede hacer nada.
    botones = {(c.get("etiqueta") or "").replace("&", ""): c
               for c in visibles if c["clase"] == "Button"}
    mas = botones.get("Cargar más")
    if mas is None:
        res.fallo("comentarios: no está el botón «Cargar más»")
    elif mas["habilitado"]:
        res.fallo("comentarios: «Cargar más» está habilitado sin ninguna "
                  "página cargada")
    else:
        res.nota("comentarios: «Cargar más» correctamente apagado al empezar")

    # Este otro depende de que haya sesión iniciada, que no está en manos del
    # banco. Se anota lo que se encontró, sin juzgarlo.
    comentar = botones.get("Comentar en el vídeo")
    if comentar is None:
        res.fallo("comentarios: no está el botón «Comentar en el vídeo»")
    else:
        res.nota("comentarios: «Comentar en el vídeo» "
                 + ("habilitado, hay sesión" if comentar["habilitado"]
                    else "apagado, no hay sesión iniciada"))

    # Tab hay que empezarlo DENTRO de la pagina: desde el marco no recorre
    # nada, igual que en la ventana principal.
    app.pedir("foco", nombre="Lista de comentarios")
    orden = recorrer_tab(app, res, "comentarios", vueltas=12)
    res.nota("comentarios, orden de Tab, %d paradas: %s"
             % (len(orden), " > ".join(orden[:10])))

    # Enter sobre la lista vacía tiene que decir algo. Callarse es lo peor que
    # puede hacer: quien no ve la pantalla no sabe si la tecla llegó.
    app.pedir("foco", nombre="Lista de comentarios")
    n = len(app.anuncios)
    app.teclas("return")
    if app.esperar_dicho("sin comentario", segundos=5, desde=n):
        res.nota("comentarios: Enter sin selección avisa en vez de callarse")
    else:
        res.fallo("comentarios: Enter sobre la lista vacía no anunció nada")

    # El aviso de TikTok es la única entrada que el panel muestra sin red, y
    # existe para que la pestaña vacía no parezca una avería. Esto deja la
    # aplicación en sesión de TikTok, así que el escenario va justo antes de
    # `tiktok` en la corrida completa.
    app.simular_sesion_tiktok()
    app.pedir("pestanas", indice=pagina)
    items = []
    limite = time.time() + 8
    while time.time() < limite:
        actual = _lista_de_comentarios(subarbol(app.arbol(), "PanelComentarios"))
        items = actual.get("items", []) if actual else []
        if items:
            break
        time.sleep(0.3)
    if any("tiktok" in i.lower() for i in items):
        res.nota("comentarios: en TikTok la lista explica por qué está vacía")
    else:
        res.fallo("comentarios: en TikTok la lista no explica por qué está "
                  "vacía; dice %r" % (items,))


def subarbol(controles: list[dict], nombre: str) -> list[dict]:
    """Los controles que cuelgan del panel con ese nombre, el panel incluido.

    Hace falta porque en el marco principal NINGUNA de las dos banderas de
    visibilidad acota una pagina del cuaderno, medido el 26/08/2026: wx deja
    `IsShown` en True para las paginas que no estan al frente, asi que
    `visible` las incluye a todas, y `IsShownOnScreen` da False para todo lo
    que cuelga por debajo del nivel 3, asi que `en_pantalla` no deja ni la
    pagina que si esta seleccionada. En un dialogo aparte, como Preferencias,
    `en_pantalla` si funciona, y por eso el escenario de preferencias lo usa.

    Lo que si es fiable es el nivel, que `_arbol` pone en cada control.
    """
    inicio = None
    for i, c in enumerate(controles):
        if (c.get("nombre") or "") == nombre:
            inicio = i
            break
    if inicio is None:
        return []
    base = controles[inicio]["nivel"]
    for j in range(inicio + 1, len(controles)):
        if controles[j]["nivel"] <= base:
            return controles[inicio:j]
    return controles[inicio:]


def _lista_de_comentarios(controles: list[dict]) -> dict | None:
    for c in controles:
        if (c["clase"] == "ListBox"
                and "comentario" in (c.get("nombre") or "").lower()):
            return c
    return None


def _panel_comentarios(app: Aplicacion, segundos: float = 8.0) -> list[dict]:
    """Espera a que el panel este construido y devuelve solo sus controles."""
    limite = time.time() + segundos
    rama: list[dict] = []
    while time.time() < limite:
        rama = subarbol(app.arbol(), "PanelComentarios")
        if _lista_de_comentarios(rama) is not None:
            return rama
        time.sleep(0.3)
    return rama


def dialogo_nativo(titulo: str, segundos: float = 8.0):
    """Busca un cuadro de diálogo NATIVO de Windows, de los de `wx.MessageBox`.

    Estos no son ventanas de wx: no salen en `wx.GetTopLevelWindows()`, así
    que desde dentro son invisibles. Es el único caso donde hay que mirar
    desde fuera para saber siquiera que existen.
    """
    try:
        from pywinauto import Desktop
    except ImportError:
        return None
    objetivo = titulo.lower()
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            for w in _candidatas_uia(Desktop):
                try:
                    if objetivo in (w.element_info.name or "").lower():
                        return w
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.3)
    return None


def escenario_dialogos_ayuda(app: Aplicacion, args, res: Resultado):
    """Las tres entradas del menú Ayuda, que son de tres tipos distintos.

    Y esa es la lección: dar por hecho que un ítem de menú «abre una ventana»
    es lo que hizo que la primera versión de este escenario dijera que ninguno
    de los tres abría nada. Uno abre el navegador, otro solo anuncia, y el
    tercero abre un cuadro nativo que wx no lista.
    """
    # 1. Marcar incidencia: no abre nada, anuncia. Se comprueba el anuncio.
    app.pedir("frente")
    n = len(app.anuncios)
    try:
        app.abrir_por_menu("Marcar incidencia")
    except Exception as exc:
        res.fallo(f"Marcar incidencia: no se pudo disparar, {exc}")
    else:
        if app.esperar_dicho("incidencia", segundos=8, desde=n):
            res.nota("«Marcar incidencia» anuncia que se guardó")
        else:
            res.fallo("«Marcar incidencia» no anunció nada, y es su única "
                      "señal: no abre ventana ni hace ruido")

    # 2. Acerca de: cuadro nativo, invisible para wx.
    app.pedir("frente")
    try:
        app.abrir_por_menu("Acerca de")
    except Exception as exc:
        res.fallo(f"Acerca de: no se pudo disparar, {exc}")
        return
    dlg = dialogo_nativo("Acerca de", segundos=8)
    if dlg is None:
        res.fallo("«Acerca de» no abrió ningún cuadro que Windows exponga")
    else:
        textos, botones = [], []
        try:
            for d in dlg.descendants():
                try:
                    rol = d.element_info.control_type
                    nombre = (d.element_info.name or "").strip()
                except Exception:
                    continue
                if rol == "Text" and nombre:
                    textos.append(nombre)
                elif rol == "Button" and nombre:
                    botones.append(nombre)
        except Exception:
            pass
        res.nota(f"«Acerca de» abre un cuadro nativo con {len(textos)} textos "
                 f"y botones: {', '.join(botones) or 'ninguno'}")
        _version_coherente(textos, res)
        for x in textos[:3]:
            res.nota("  dice: " + x[:70])
        if not textos:
            res.fallo("«Acerca de»: el cuadro no expone ningún texto, así que "
                      "un lector de pantalla no tiene qué leer")
        try:
            dlg.type_keys("{ESC}")
        except Exception:
            try:    dlg.close()
            except Exception: pass
        time.sleep(0.8)

    # 3. La guía de la API abre el NAVEGADOR. No se dispara salvo que se pida.
    if getattr(args, "con_navegador", False):
        app.pedir("frente")
        app.abrir_por_menu("Guía de configuración de la API")
        res.nota("«Guía de configuración de la API» abrió el navegador")
    else:
        res.nota("«Guía de configuración de la API» abre el navegador con "
                 "`webbrowser.open`; se salta para no llenar de pestañas la "
                 "máquina de quien corre las pruebas. Usá --con-navegador.")



def _version_coherente(textos: list, res: Resultado) -> None:
    """La version que la aplicacion MUESTRA contra la que documenta el CHANGELOG.

    Nadie vigilaba esto: comprobado el 26/08/2026, ninguna prueba mira
    `APP_VERSION`, asi que se podia publicar una version con el numero mal y el
    unico sintoma seria que el «Acerca de» dijera una cosa y las novedades
    otra. Quien lo sufre es el que descarga el ZIP y no sabe que tiene.
    """
    import re
    mostrada = ""
    for x in textos:
        m = re.search(r"v(\d+\.\d+\.\d+)", x)
        if m:
            mostrada = m.group(1)
            break
    if not mostrada:
        res.fallo("«Acerca de» no muestra ningun numero de version")
        return

    try:
        texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    except Exception as exc:
        res.nota(f"no se pudo leer CHANGELOG.md: {exc}")
        return
    m = re.search(r"^##\s*(\d+\.\d+\.\d+)", texto, re.MULTILINE)
    documentada = m.group(1) if m else ""
    if not documentada:
        res.fallo("CHANGELOG.md no tiene ninguna entrada de version")
    elif documentada != mostrada:
        res.fallo("la aplicacion dice v%s y la entrada mas nueva del CHANGELOG "
                  "es %s" % (mostrada, documentada))
    else:
        res.nota(f"version coherente: la aplicacion y el CHANGELOG dicen {mostrada}")


def escenario_avisos_wx(app: Aplicacion, args, res: Resultado):
    """Lo que wx escribe por la salida de error y nadie lee nunca.

    wxWidgets avisa por ahí de widgets mal construidos, de jerarquías que no
    corresponden y de llamadas que fallan. En uso normal esa salida se pierde,
    porque la aplicación se lanza sin consola. Acá se captura y se mira.

    No todo aviso es un defecto, pero un aviso que se repite en cada arranque
    y que nadie ha leído nunca merece por lo menos una mirada.
    """
    # Se recorre un poco de interfaz para que salgan los avisos de construir
    # paneles, no solo los del arranque.
    app.pedir("frente")
    app.simular_sesion_youtube()
    app.mensaje("Ana", "hola")
    time.sleep(2.0)

    if not app.salida_ruta.exists():
        res.fallo("no se capturó la salida de la aplicación")
        return
    crudo = app.salida_ruta.read_text(encoding="utf-8", errors="replace")
    lineas = [l.strip() for l in crudo.splitlines() if l.strip()]

    marcas = ("should be created as child", "failed with error", "Assert",
              "wxWidgets", "Warning:", "Error:")
    avisos = [l for l in lineas if any(m in l for m in marcas)]

    # Se agrupan, porque el mismo aviso sale muchas veces y en bruto tapa todo.
    resumen = {}
    for a in avisos:
        clave = a[:110]
        resumen[clave] = resumen.get(clave, 0) + 1

    if not resumen:
        res.nota("wx no escribió ningún aviso")
        return
    res.nota(f"wx escribió {len(avisos)} avisos, {len(resumen)} distintos")
    for texto, veces in sorted(resumen.items(), key=lambda x: -x[1])[:6]:
        res.fallo(f"aviso de wx x{veces}: {texto}")



# Enlaces que dio el dueno el 21/08/2026 para poder probar contra la red.
# Un directo caduca: si el escenario dice que no hay nadie emitiendo, lo
# primero que hay que mirar es si el enlace sigue vivo, no el codigo.
# Directo de TN, que emite siempre y tiene el chat lleno. Lo eligio el
# dueno el 26/08/2026 como el sitio donde probar: es publico, va rapido
# y a nadie le llama la atencion un mensaje suelto.
DIRECTO_YOUTUBE = "https://www.youtube.com/watch?v=cb12KmMMDJA"
DIRECTO_TIKTOK = "https://www.tiktok.com/@rolon_100/live"
# Vídeo grabado para `reproductor_en_marcha`, que se pasa con `--url-vod`.
VOD_YOUTUBE = "https://www.youtube.com/watch?v=j906Pf7n7Sg"


def esperar_reproductor(app: Aplicacion, condicion, segundos: float):
    """Sondea el estado del reproductor hasta que `condicion` se cumpla.

    Devuelve el último estado y si se cumplió. Espera hechos, no relojes.
    """
    ultimo: dict = {}
    limite = time.time() + segundos
    while True:
        try:
            ultimo = app.reproductor() or {}
        except Exception:
            ultimo = {}
        if ultimo and condicion(ultimo):
            return ultimo, True
        if time.time() >= limite:
            return ultimo, False
        time.sleep(0.25)


def conectar_de_verdad(app: Aplicacion, res: Resultado, url: str,
                       donde: str, espera: float = 60.0):
    """Pega una URL, pulsa Conectar, y espera a que la aplicacion diga algo.

    Es el unico escenario que toca la red, y por eso es el unico que puede
    fallar por motivos ajenos al codigo. Cuando falle, antes de tocar nada hay
    que comprobar a mano que el directo siga emitiendo.
    """
    app.al_frente()
    # Por el nombre COMPLETO del campo. Pedir foco por «URL» a secas caia en la
    # etiqueta «URL/ID:», que tambien contiene esa palabra y va antes en el
    # arbol, y entonces la URL no se escribia nunca. El escenario no lo decia
    # porque las ordenes rechazadas se ignoraban; con `pedir` estricto salta.
    app.pedir("foco", nombre="URL del directo o vídeo")
    app.pedir("texto", valor=url)
    n = len(app.anuncios)

    boton = None
    for c in app.arbol():
        if c["clase"] == "Button" and "conectar" in (
                (c.get("etiqueta") or "") + (c.get("nombre") or "")).lower():
            boton = c
            break
    if boton is None:
        res.fallo(f"{donde}: no encuentro el botón Conectar")
        return False
    app.pedir("pulsar", nombre=boton.get("nombre") or boton.get("etiqueta"))

    # Se sincroniza con lo que la aplicación dice, no con un reloj: si tarda
    # veinte segundos porque yt-dlp está lento, esperar cinco daría un fallo
    # falso, y esperar sesenta a ciegas gastaría un minuto siempre.
    limite = time.time() + espera
    while time.time() < limite:
        dichos = " ".join(a.get("texto", "") for a in app.anuncios[n:]).lower()
        if "conectado" in dichos or "error" in dichos or "no se pudo" in dichos:
            break
        time.sleep(0.5)

    dichos = [a.get("texto", "") for a in app.anuncios[n:]]
    if not dichos:
        res.fallo(f"{donde}: pulsé Conectar y la aplicación no dijo nada en "
                  f"{espera:.0f} s. Un usuario ciego no sabría si pasó algo")
        return False
    for d in dichos[:6]:
        res.nota(f"  {donde} dice: {d[:90]}")
    junto = " ".join(dichos).lower()
    if "error" in junto or "no se pudo" in junto:
        res.fallo(f"{donde}: la conexión falló. Comprobá a mano que el directo "
                  "siga emitiendo antes de culpar al código")
        return False
    return True


def escenario_directo_youtube(app: Aplicacion, args, res: Resultado):
    """Un directo de YouTube de verdad, con la red de por medio."""
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"youtube en vivo: {url}")
    if not conectar_de_verdad(app, res, url, "youtube en vivo"):
        return

    # El título y los espectadores los rellena el hilo de captura, no la GUI:
    # que aparezcan prueba que el cableado entero funciona.
    limite = time.time() + 45
    titulo = ""
    while time.time() < limite:
        for c in app.arbol():
            texto = (c.get("etiqueta") or "").strip()
            if c["clase"] == "StaticText" and len(texto) > 12:
                titulo = texto
        if titulo:
            break
        time.sleep(1.0)
    if titulo:
        res.nota(f"youtube en vivo: la ventana muestra «{titulo[:70]}»")
    else:
        res.fallo("youtube en vivo: conectó pero no apareció ningún texto "
                  "largo en la ventana, o sea ni título ni estado")

    lista = None
    limite = time.time() + 90
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(2.0)
    if lista and lista.get("items"):
        items = lista["items"]
        res.nota(f"youtube en vivo: llegaron {len(items)} mensajes reales")
        for i in items[:3]:
            res.nota("  lee: " + str(i)[:80])
    else:
        res.nota("youtube en vivo: conectó pero no llegó ningún mensaje en "
                 "90 s. Puede ser un chat tranquilo, no es defecto por sí solo")

    # Y ahora lo que ningún escenario había hecho nunca: el reproductor con
    # vídeo de verdad cargado. Hasta el 21/08/2026 la batería solo se había
    # corrido sin nada cargado, que es el caso fácil: con medio real entran en
    # juego la red, el buffer y lo que tarda VLC en responder, y ahí es donde
    # viviría la torpeza de la que se queja quien la usa.
    #
    # Se espera a que termine de cargar antes de medir: juzgar la latencia
    # mientras yt-dlp todavía resuelve la URL mide la red, no la aplicación.
    if app.esperar_dicho("reproduciendo", segundos=60):
        res.nota("youtube en vivo: el reproductor arrancó")
    else:
        res.nota("youtube en vivo: no se oyó «Reproduciendo» en 60 s; se mide "
                 "igual, pero puede que no haya llegado a cargar")
    time.sleep(3.0)

    visibles = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                        for c in app.arbol()).lower()
    if "retroceder 1 min" not in visibles:
        app.pedir("pulsar", nombre="AlternarBotonesReproductor")
    bateria_reproductor(app, res, "youtube en vivo", hay_medio=True)

    app.llamar("set_conectado", False)


def escenario_directo_tiktok(app: Aplicacion, args, res: Resultado):
    """Un directo de TikTok de verdad. Ruta distinta y más frágil."""
    url = getattr(args, "url_tiktok", None) or DIRECTO_TIKTOK
    res.nota(f"tiktok en vivo: {url}")
    if not conectar_de_verdad(app, res, url, "tiktok en vivo", espera=75.0):
        return
    lista = None
    limite = time.time() + 60
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(2.0)
    if lista and lista.get("items"):
        res.nota(f"tiktok en vivo: llegaron {len(lista['items'])} eventos")
    else:
        res.nota("tiktok en vivo: conectó pero no llegó nada en 60 s")
    app.llamar("set_conectado", False)


def _en_marcha_teclas(app: Aplicacion, res: Resultado, donde: str,
                      *pasos) -> bool:
    """Pasa las teclas, y si la ventana no está al frente no juzga nada."""
    try:
        app.teclas(*pasos)
    except VentanaNoActiva as exc:
        res.no_probado(f"{donde}: no se pudo probar, {exc}")
        return False
    return True


def _en_marcha_salto(app: Aplicacion, res: Resultado, donde: str, p0: int,
                     delta_ms: int, dur_ms: int, espera: float = 30.0):
    """Juzga un salto ya pulsado: destino, tolerancia y que siga avanzando.

    Devuelve la posición final, o None si no pasó.
    """
    destino = p0 + delta_ms
    if dur_ms > 0:
        destino = min(max(destino, 0), dur_ms)
    else:
        destino = max(destino, 0)
    t0 = time.time()

    def _cerca(e):
        pos = e.get("pos_ms") or 0
        return (e.get("estado") == "playing"
                and destino - 5000 <= pos <= destino + 20000)

    estado, ok = esperar_reproductor(app, _cerca, espera)
    pos = (estado.get("pos_ms") or 0) if estado else 0
    if not ok:
        res.fallo(f"{donde}: desde {p0 / 1000:.1f} s no quedó cerca de "
                  f"{destino / 1000:.1f} s en {espera:.0f} s; está en "
                  f"{pos / 1000:.1f} s con estado {estado.get('estado')!r}")
        return None
    time.sleep(3.0)
    pos2 = app.reproductor().get("pos_ms") or 0
    if pos2 <= pos:
        res.fallo(f"{donde}: quedó en {pos / 1000:.1f} s pero no avanza desde "
                  f"ahí ({pos2 / 1000:.1f} s 3 s después)")
        return None
    res.nota(f"{donde}: de {p0 / 1000:.1f} s a {pos / 1000:.1f} s "
             f"(destino {destino / 1000:.1f} s) en {time.time() - t0:.1f} s, "
             f"y sigue a {pos2 / 1000:.1f} s")
    return pos2


def _en_marcha_grabado(app: Aplicacion, args, res: Resultado) -> None:
    """Saltos y pausa en un vídeo grabado, con los atajos de verdad."""
    url = getattr(args, "url_vod", None) or VOD_YOUTUBE
    res.nota(f"reproductor en marcha (grabado): {url}")
    n = len(app.anuncios)
    if not conectar_de_verdad(app, res, url, "reproductor en marcha"):
        return
    if not app.esperar_dicho("reproduciendo", segundos=60, desde=n):
        res.fallo("reproductor en marcha: no se oyó «Reproduciendo» en 60 s")
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "playing", 60.0)
    if not ok:
        res.fallo("reproductor en marcha: no llegó a «playing» en 60 s; "
                  f"estado {estado.get('estado')!r}")
        return
    pa = estado.get("pos_ms") or 0
    time.sleep(2.0)
    pb = app.reproductor().get("pos_ms") or 0
    if pb <= pa:
        res.fallo("reproductor en marcha: en «playing» la posición no avanza "
                  f"({pa / 1000:.1f} s y {pb / 1000:.1f} s)")
        return
    res.nota(f"reproductor en marcha: reproduce desde {pa / 1000:.1f} s "
             f"y avanza a {pb / 1000:.1f} s en 2 s")

    # Dos avances seguidos, sin espera entre ellos, como hace cualquiera
    # cuando el primero no contestó.
    p0 = app.reproductor().get("pos_ms") or 0
    dur = app.reproductor().get("dur_ms") or 0
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    _en_marcha_salto(app, res, "reproductor en marcha, salto +2 min",
                     p0, 120000, dur)

    p1 = app.reproductor().get("pos_ms") or 0
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("left", ["ctrl"])):
        return
    _en_marcha_salto(app, res, "reproductor en marcha, salto -1 min",
                     p1, -60000, dur)

    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("p", ["ctrl"])):
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "paused", 5.0)
    if not ok:
        res.fallo("reproductor en marcha: no entró en pausa en 5 s; "
                  f"estado {estado.get('estado')!r}")
        return
    pa = estado.get("pos_ms") or 0
    time.sleep(2.0)
    pb = app.reproductor().get("pos_ms") or 0
    if abs(pb - pa) > 1000:
        res.fallo(f"reproductor en marcha: en pausa se movió de "
                  f"{pa / 1000:.1f} s a {pb / 1000:.1f} s en 2 s")
        return
    res.nota(f"reproductor en marcha: en pausa queda en {pa / 1000:.1f} s "
             f"y no se mueve")

    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("p", ["ctrl"])):
        return
    destino = pa + 60000

    def _reanudado(e):
        pos = e.get("pos_ms") or 0
        return (e.get("estado") == "playing"
                and destino - 5000 <= pos <= destino + 20000)

    estado, ok = esperar_reproductor(app, _reanudado, 30.0)
    pos = (estado.get("pos_ms") or 0) if estado else 0
    if not ok:
        res.fallo(f"reproductor en marcha: tras saltar en pausa desde "
                  f"{pa / 1000:.1f} s no reanudó cerca de "
                  f"{destino / 1000:.1f} s en 30 s; está en "
                  f"{pos / 1000:.1f} s con estado {estado.get('estado')!r}")
    else:
        res.nota(f"reproductor en marcha: salto en pausa y reanudado en "
                 f"{pos / 1000:.1f} s (destino {destino / 1000:.1f} s)")


def _en_marcha_directo(app: Aplicacion, args, res: Resultado) -> None:
    """Retroceso por relevo y vuelta al borde en un directo real."""
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"reproductor en marcha (directo): {url}")
    n = len(app.anuncios)
    if not conectar_de_verdad(app, res, url, "reproductor en marcha "
                                             "(directo)"):
        return
    if not app.esperar_dicho("reproduciendo", segundos=60, desde=n):
        res.fallo("reproductor en marcha (directo): no se oyó "
                  "«Reproduciendo» en 60 s")
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "playing", 60.0)
    if not ok:
        res.fallo("reproductor en marcha (directo): no llegó a «playing» "
                  f"en 60 s; estado {estado.get('estado')!r}")
        return
    res.nota("reproductor en marcha (directo): reproduce el directo")

    # Tres flechas seguidas en el deslizador: cada una son 10 s, o sea dos
    # segmentos de 5 s, así que el desfase esperado es 6.
    ventana_corta = False
    try:
        app.pedir("foco", nombre="Posición de reproducción")
    except OrdenRechazada as exc:
        res.fallo("reproductor en marcha (directo): no se llega a la "
                  f"posición, {exc}")
    else:
        n = len(app.anuncios)
        for _ in range(3):
            if not _en_marcha_teclas(app, res,
                                     "reproductor en marcha (directo)",
                                     "left"):
                return
        if app.esperar_dicho("no se puede retroceder más", segundos=5,
                             desde=n):
            res.nota("reproductor en marcha (directo): YouTube da una "
                     "ventana corta de 30 s y no deja retroceder; se sigue "
                     "con la vuelta al directo")
            ventana_corta = True
        else:
            t0 = time.time()

            def _atras(e):
                return (e.get("desfase") == 6
                        and e.get("estado") == "playing")

            estado, ok = esperar_reproductor(app, _atras, 20.0)
            if not ok:
                res.fallo("reproductor en marcha (directo): tras tres "
                          "flechas el desfase no llegó a 6 en 20 s; "
                          f"desfase {(estado.get('desfase') if estado else '?')}, "
                          f"estado {(estado.get('estado') if estado else '?')!r}")
            else:
                res.nota("reproductor en marcha (directo): tres flechas "
                         f"dejan el desfase en 6 en {time.time() - t0:.1f} s")

    if not ventana_corta:
        n = len(app.anuncios)
        if not _en_marcha_teclas(app, res, "reproductor en marcha (directo)",
                                 ("end", ["ctrl"])):
            return
        app.esperar_dicho("en el directo", segundos=8, desde=n)
        t0 = time.time()

        def _al_borde(e):
            return e.get("desfase") == 0 and e.get("estado") == "playing"

        estado, ok = esperar_reproductor(app, _al_borde, 20.0)
        junto = " ".join(a.get("texto", "") for a in app.anuncios[n:]).lower()
        dijo_borde = ("en el directo" in junto
                      and "ya estás en el directo" not in junto)
        if not dijo_borde or not ok:
            res.fallo("reproductor en marcha (directo): Ctrl+Fin no volvió "
                      f"al borde en 20 s; dijo «{junto[:80]}», desfase "
                      f"{(estado.get('desfase') if estado else '?')}, estado "
                      f"{(estado.get('estado') if estado else '?')!r}")
        else:
            res.nota("reproductor en marcha (directo): Ctrl+Fin dice «En el "
                     f"directo» y el desfase vuelve a 0 en "
                     f"{time.time() - t0:.1f} s")

    n = len(app.anuncios)
    if not _en_marcha_teclas(app, res, "reproductor en marcha (directo)",
                             ("end", ["ctrl"])):
        return
    if app.esperar_dicho("ya estás en el directo", segundos=8, desde=n):
        res.nota("reproductor en marcha (directo): Ctrl+Fin en el borde "
                 "dice «Ya estás en el directo»")
    else:
        junto = " ".join(a.get("texto", "") for a in app.anuncios[n:])
        res.fallo("reproductor en marcha (directo): Ctrl+Fin en el borde no "
                  f"avisó; dijo «{junto[:80]}»")


def escenario_reproductor_en_marcha(app: Aplicacion, args, res: Resultado):
    """El reproductor en marcha: saltos, pausa y vuelta al directo, de verdad.

    El banco nunca lo probaba: ningún escenario comprobaba que después de un
    salto el vídeo siga desde el destino, ni la pausa, ni volver al directo.
    Acá se pulsan los atajos de verdad contra un vídeo grabado y un directo
    reales, y se juzga la posición que la aplicación le da al usuario, no
    solo lo que anuncia. La segunda parte corre aunque la primera falle.
    """
    _en_marcha_grabado(app, args, res)
    app.llamar("set_conectado", False)
    _en_marcha_directo(app, args, res)
    app.llamar("set_conectado", False)


def _hilos_de_captura(app: Aplicacion) -> list:
    """Los hilos de captura de chat vivos, por nombre."""
    vivos = app.hilos()
    return [h for h in vivos if h in ("Chat", "TikTok")]


def escenario_dos_conexiones(app: Aplicacion, args, res: Resultado):
    """Conectar dos veces sin desconectar no deja el hilo viejo girando.

    El 21/08/2026 los registros de un usuario real mostraron diez hilos `Chat`
    arrancados y nueve terminados: al conectar a otro vídeo, el anterior se
    quedaba pidiendo el chat para siempre porque nadie ponía su evento de
    parada. Esto lo comprueba con la aplicación de verdad, que es donde se vio.

    El camino por el que pasa de verdad, leído en `gui.py:872` el 21/08/2026:
    el botón alterna, así que estando conectado no se puede conectar otra vez.
    Pero un error de red hace `set_conectado(False)` y rehabilita el botón
    MIENTRAS el hilo de captura sigue vivo reintentando, y ahí una pulsación
    abre la segunda sesión. Por eso el escenario llama a `set_conectado(False)`
    en medio: es exactamente lo que la aplicación se hace a sí misma cuando
    pytchat pierde la conexión, y lo que le pasó al usuario a las 12:23 y a las
    12:30.

    Vale con conectar dos veces al MISMO directo: la conexión no compara el
    vídeo, abre una sesión nueva igual.
    """
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"dos conexiones: {url}")

    if not conectar_de_verdad(app, res, url, "dos conexiones (primera)"):
        return
    # Esperar a que el hilo de captura exista de verdad antes de medir: si se
    # mide antes de que arranque, el conteo da cero y el escenario pasa sin
    # haber probado nada.
    limite = time.time() + 30
    while time.time() < limite and not _hilos_de_captura(app):
        time.sleep(0.5)
    primeros = _hilos_de_captura(app)
    if not primeros:
        res.fallo("dos conexiones: la primera no llegó a arrancar ningún hilo "
                  "de captura en 30 s; sin eso no se puede medir nada")
        return
    res.nota(f"dos conexiones: tras la primera hay {len(primeros)} "
             f"({', '.join(primeros)})")

    # Lo que hace la aplicación sola al perder la conexión: apaga la interfaz
    # y deja el hilo reintentando. No mata nada.
    app.llamar("set_conectado", False)
    time.sleep(1.0)
    if not conectar_de_verdad(app, res, url, "dos conexiones (segunda)"):
        return
    # El hilo viejo puede tardar en morir: está dentro de una lectura de red y
    # no ve la parada hasta que vuelve. Se le da margen y se toma el mínimo,
    # porque un solape de un segundo es correcto y quedarse pegado no lo es.
    limite = time.time() + 45
    minimo = 99
    while time.time() < limite:
        minimo = min(minimo, len(_hilos_de_captura(app)))
        if minimo <= 1:
            break
        time.sleep(1.0)

    if minimo <= 1:
        res.nota(f"dos conexiones: el hilo de la primera murió, quedó {minimo}")
    else:
        vivos = _hilos_de_captura(app)
        res.fallo(f"dos conexiones: quedaron {minimo} hilos de captura vivos "
                  f"tras 45 s ({', '.join(vivos)}); el de la sesión vieja no "
                  f"se paró y va a seguir pidiendo el chat hasta que se cierre "
                  f"la aplicación")
    app.llamar("set_conectado", False)


def escenario_overlay(app: Aplicacion, args, res: Resultado):
    """El panel de chat para transmitir: interruptor, servicio y estado.

    La fase 3 de `scripts/smoke_test.py` no llega a este diálogo, y las pruebas unitarias no arrancan la aplicación entera, que es donde se ve si el interruptor está cableado de verdad.

    Comprueba lo único que el dueño no puede mirar: que cuando dice que está
    activo, esté sirviendo la página de verdad.
    """
    import urllib.request

    etiqueta = "Panel de chat para transmitir"
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
            app.abrir_por_menu("Transmisión")
        except Exception as exc:
            res.fallo(f"Transmisión: no se pudo abrir el diálogo, {exc}")
            return False
        if app.esperar_ventana("Transmisión", segundos=15) is None:
            res.fallo("Transmisión: el menú no abrió el diálogo")
            return False
        controles = app.arbol("Transmisión")
        casilla = next((c for c in controles
                        if c.get("clase") == "CheckBox" and c.get("nombre") == etiqueta), None)
        if casilla is None or not casilla.get("habilitado"):
            motivo = "no existe" if casilla is None else "está deshabilitada"
            res.fallo(f"Transmisión: la casilla «{etiqueta}» {motivo}")
            app.pedir("cerrar_ventana", ventana="Transmisión")
            return False
        try:
            app.pedir("foco", ventana="Transmisión", nombre=etiqueta)
            app.teclas("space")
        except Exception as exc:
            res.fallo(f"Transmisión: no se pudo alternar «{etiqueta}», {exc}")
            app.pedir("cerrar_ventana", ventana="Transmisión")
            return False
        app.pedir("cerrar_ventana", ventana="Transmisión")
        return True

    encendido_al_entrar = responde(2.0)
    if encendido_al_entrar:
        res.nota("el panel ya venía encendido; se apaga para probar el ciclo")
        if not alternar_panel():
            return
        app.esperar_dicho("panel de chat apagado", 8)

    # Encender
    antes = len(app.anuncios)
    if not alternar_panel():
        return
    if not app.esperar_dicho("panel de chat activo en el puerto", 10, desde=antes):
        dichos = [a["texto"][:60] for a in app.anuncios[antes:]]
        res.fallo(f"al encender no anunció el puerto; dijo: {dichos}")
    if not responde():
        res.fallo(f"anunció el panel activo pero {url} no responde")
    else:
        res.nota(f"{url} responde")

    # F2 tiene que distinguir que nadie lo está mostrando
    antes = len(app.anuncios)
    app.abrir_por_menu("Anunciar estado")
    app.esperar_dicho("panel", 8, desde=antes)
    dicho = " ".join(a["texto"].lower() for a in app.anuncios[antes:])
    if "panel de chat activo" not in dicho:
        res.fallo("F2 no menciona el panel estando encendido")
    elif "nadie lo est" not in dicho:
        res.fallo("F2 no distingue que nadie está mostrando el panel")
    else:
        res.nota("F2 dice que nadie lo está mostrando")

    # Apagar
    antes = len(app.anuncios)
    if not alternar_panel():
        return
    if not app.esperar_dicho("panel de chat apagado", 10, desde=antes):
        res.fallo("al apagar no lo anunció")
    if responde(3.0):
        res.fallo("apagado, el puerto sigue respondiendo")
    else:
        res.nota("apagado, el puerto deja de responder")

    if encendido_al_entrar:
        alternar_panel()   # se deja como estaba


def escenario_programados(app: Aplicacion, args, res: Resultado):
    """La pestaña de mensajes automáticos, control por control.

    Interesa sobre todo por los dos `wx.SpinCtrl`: son controles COMPUESTOS
    (una caja de texto más dos flechas), y en Windows el `name=` de wx no
    siempre llega al servicio de accesibilidad. Un intervalo que el lector
    anuncia como «cuadro de edición» a secas, sin decir si es el mínimo o el
    máximo, deja al usuario adivinando cuál de los dos está tocando.
    """
    etiqueta_pag = "Mensajes automáticos"
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"programados: no se pudo abrir Preferencias, {exc}")
        return
    if app.esperar_ventana("Preferencias", segundos=15) is None:
        res.fallo("programados: Preferencias no abrió")
        return

    try:
        paginas = app.pedir("pestanas", ventana="Preferencias").get(
            "datos", {}).get("paginas", [])
        if etiqueta_pag not in paginas:
            res.fallo(f"programados: no existe la pestaña «{etiqueta_pag}»; "
                      f"hay {paginas}")
            return
        res.nota(f"pestaña encontrada, es la {paginas.index(etiqueta_pag) + 1} "
                 f"de {len(paginas)}")
        app.pedir("pestanas", ventana="Preferencias",
                  indice=paginas.index(etiqueta_pag))
        time.sleep(0.4)

        controles = app.arbol("Preferencias")
        visibles = [c for c in controles if c.get("en_pantalla")]
        revisar_nombres(visibles, res, "programados")

        # El texto de introducción es donde se explican los límites de la API.
        # Si desaparece, el usuario no tiene dónde enterarse.
        textos = " ".join((c.get("etiqueta") or "") + " " + (c.get("nombre") or "")
                          for c in controles)
        for clave, que in (("5 minutos", "el intervalo mínimo"),
                           ("200 caracteres", "el límite de caracteres"),
                           ("enlaces", "el aviso sobre los enlaces")):
            if clave not in textos:
                res.fallo(f"programados: la introducción no menciona {que}")
        if all(k in textos for k in ("5 minutos", "200 caracteres", "enlaces")):
            res.nota("la introducción explica intervalo, longitud y enlaces")

        # Los controles que tienen que estar, por su name= de wx.
        esperados = ("ActivarProgramados", "Mensajes automáticos guardados",
                      "TextoProgramado",
                     "MinutosMin", "MinutosMax", "MensajeActivo",
                     "AgregarProgramado", "GuardarProgramado", "QuitarProgramado")
        nombres = {(c.get("nombre") or "") for c in controles}
        faltan = [n for n in esperados if n not in nombres]
        if faltan:
            res.fallo(f"programados: no aparecen en el árbol: {faltan}")
        else:
            res.nota(f"los {len(esperados)} controles de la pestaña están")
    finally:
        app.pedir("cerrar_ventana", ventana="Preferencias")


def escenario_conectar(app: Aplicacion, args, res: Resultado):
    """El boton Conectar, que en una corrida rutinaria no se pulsaba nunca.

    Lo pulsaban solo los tres escenarios de directo vivo, que estan fuera de
    `todos`, asi que sus dos caminos de error no los habia visto nadie. Este no
    toca la red: se queda en los dos casos que fallan antes de salir a buscar
    nada.
    """
    app.pedir("frente")

    # 1. Sin URL. Sale un cuadro nativo, no un anuncio: NVDA lo lee al recibir
    # el foco, pero si el cuadro no expone texto no hay nada que leer.
    app.llamar("set_url", "")
    try:
        app.pedir("pulsar", nombre="Conectar", tiempo=3.0, responder_ya=True)
    except Exception:
        pass                      # el cuadro es modal y se come la respuesta
    dlg = dialogo_nativo("Falta URL", segundos=8)
    if dlg is None:
        res.fallo("conectar: con la URL vacia no aparecio ningun aviso")
    else:
        textos = _textos_de(dlg)
        res.nota("conectar sin URL abre «Falta URL» con %d textos" % len(textos))
        for x in textos[:2]:
            res.nota("  dice: " + x[:70])
        if not textos:
            res.fallo("conectar: el aviso de URL vacia no expone ningun texto, "
                      "asi que un lector de pantalla no tiene que leer")
        _cerrar_nativo(dlg)

    # 2. URL que no es de YouTube ni de TikTok.
    app.llamar("set_url", "esto no es una direccion")
    n = len(app.anuncios)
    try:
        app.pedir("pulsar", nombre="Conectar", tiempo=3.0, responder_ya=True)
    except Exception:
        pass
    dlg = dialogo_nativo("URL", segundos=6) or dialogo_nativo("no vál", segundos=2)
    if dlg is not None:
        res.nota("conectar con una URL invalida abre un aviso nativo")
        _cerrar_nativo(dlg)
    elif app.dijo("no es válido", desde=n) or app.dijo("no válido", desde=n):
        res.nota("conectar con una URL invalida se anuncia con voz")
    else:
        res.fallo("conectar: una URL invalida no produjo ni aviso ni anuncio")

    app.llamar("set_url", "")


def escenario_directo_sin_imagen(app: Aplicacion, args, res: Resultado):
    """La pregunta de directo al aire sin imagen, que es un cuadro nativo.

    El diálogo es un `wx.MessageDialog`, invisible para la sonda: se lo
    busca desde fuera con `dialogo_nativo` y se pulsa «Dejarlo al aire»
    por UI Automation, la respuesta segura. Nunca se pulsa
    «Finalizar directo». Escape no sirve acá: el cuadro no tiene Cancelar
    y Windows no lo cierra.
    """
    app.pedir("frente")
    n = len(app.anuncios)
    try:
        app.pedir("directo_sin_imagen", tiempo=6.0)
    except Exception:
        pass                      # el cuadro es modal y se come la respuesta
    dlg = dialogo_nativo("Directo sin imagen", segundos=8)
    if dlg is None:
        res.fallo("directo sin imagen: no apareció la pregunta "
                  "«Directo sin imagen»")
        return
    textos = _textos_de(dlg)
    res.nota("directo sin imagen abre «Directo sin imagen» con %d textos"
             % len(textos))
    for x in textos[:2]:
        res.nota("  dice: " + x[:70])
    if not textos:
        res.fallo("directo sin imagen: la pregunta no expone ningún texto, "
                  "así que un lector de pantalla no tiene qué leer")
        if not _pulsar_dejarlo_al_aire(dlg):
            res.fallo("directo sin imagen: no apareció el botón "
                      "«Dejarlo al aire» para cerrar la pregunta")
            _cerrar_nativo(dlg)
        return
    if not any("prueba del banco" in (x or "").lower() for x in textos):
        res.fallo("directo sin imagen: la pregunta no nombra el directo "
                  "de prueba")
    botones = []
    try:
        for d in dlg.descendants():
            try:
                if d.element_info.control_type == "Button":
                    nombre = (d.element_info.name or "").strip()
                    if nombre:
                        botones.append(nombre)
            except Exception:
                continue
    except Exception:
        pass
    juntos = " ".join(textos + botones).lower()
    res.nota("directo sin imagen ofrece «Finalizar directo»: %s, "
             "«Dejarlo al aire»: %s"
             % ("sí" if "finalizar directo" in juntos else "no",
                "sí" if "dejarlo al aire" in juntos else "no"))
    if not _pulsar_dejarlo_al_aire(dlg):
        res.fallo("directo sin imagen: no apareció el botón «Dejarlo al aire»")
        _cerrar_nativo(dlg)
        if dialogo_nativo("Directo sin imagen", segundos=1.0) is not None:
            res.fallo("directo sin imagen: la pregunta sigue abierta y no se "
                      "pudo cerrar")
        return
    limite = time.time() + 5.0
    cerrado = False
    while time.time() < limite:
        if dialogo_nativo("Directo sin imagen", segundos=1.0) is None:
            cerrado = True
            break
    if not cerrado:
        res.fallo("directo sin imagen: «Dejarlo al aire» no cerró la pregunta")
        _pulsar_dejarlo_al_aire_por_coordenadas(dlg)
        if dialogo_nativo("Directo sin imagen", segundos=1.0) is not None:
            res.fallo("directo sin imagen: la pregunta sigue abierta y no hay "
                      "forma de cerrarla sin arrastrar a los demás escenarios")
            return
    if app.esperar_dicho("El directo sigue al aire", segundos=5.0, desde=n):
        res.nota("directo sin imagen con «Dejarlo al aire» anuncia que sigue "
                 "al aire")
    else:
        res.fallo("directo sin imagen: al dejarlo al aire no se anunció "
                  "«El directo sigue al aire»")


def _boton_dejarlo_al_aire(dlg):
    """El botón «Dejarlo al aire» entre los descendientes. None si no está.

    Se compara sin la marca de mnemónico. NUNCA devuelve el otro botón.
    """
    try:
        for d in dlg.descendants():
            try:
                if d.element_info.control_type != "Button":
                    continue
                nombre = (d.element_info.name or "").replace(
                    "&", "").strip()
            except Exception:
                continue
            if nombre.lower() == "dejarlo al aire":
                return d
    except Exception:
        pass
    return None


def _pulsar_dejarlo_al_aire(dlg) -> bool:
    """Pulsa «Dejarlo al aire» por UI Automation. NUNCA el otro."""
    boton = _boton_dejarlo_al_aire(dlg)
    if boton is None:
        return False
    try:
        if hasattr(boton, "invoke"):
            boton.invoke()
        else:
            boton.click_input()
    except Exception:
        try:
            boton.click_input()
        except Exception:
            return False
    return True


def _pulsar_dejarlo_al_aire_por_coordenadas(dlg) -> bool:
    """Último recurso: el mismo botón, con clic por coordenadas.

    Si ni eso sale, quien llama lo dice y no arrastra el modal abierto a
    los demás escenarios.
    """
    boton = _boton_dejarlo_al_aire(dlg)
    if boton is None:
        return False
    try:
        boton.click_input()
        return True
    except Exception:
        pass
    _cerrar_nativo(dlg)
    return False


def _textos_de(dlg) -> list:
    """Los textos que Windows expone de un cuadro nativo."""
    salida = []
    try:
        for d in dlg.descendants():
            try:
                if d.element_info.control_type == "Text":
                    nombre = (d.element_info.name or "").strip()
                    if nombre:
                        salida.append(nombre)
            except Exception:
                continue
    except Exception:
        pass
    return salida


def _cerrar_nativo(dlg) -> None:
    try:
        dlg.type_keys("{ESC}")
    except Exception:
        try:    dlg.close()
        except Exception: pass
    time.sleep(0.8)


def _boton_nativo(dlg, nombre):
    """Un botón de un cuadro nativo por su nombre. None si no está.

    Compara sin marca de mnemónico y sin mayúsculas, como
    `_boton_dejarlo_al_aire`, pero con el nombre por parámetro: la pregunta
    «Salir» pide «Sí» y No es el botón por defecto, así que Enter no sirve.
    """
    objetivo = (nombre or "").replace("&", "").strip().lower()
    try:
        for d in dlg.descendants():
            try:
                if d.element_info.control_type != "Button":
                    continue
                texto = (d.element_info.name or "").replace(
                    "&", "").strip()
            except Exception:
                continue
            if texto.lower() == objetivo:
                return d
    except Exception:
        pass
    return None


def pulsar_boton_nativo(dlg, nombre: str) -> bool:
    """Pulsa un botón de un cuadro nativo por UI Automation. False si no está."""
    boton = _boton_nativo(dlg, nombre)
    if boton is None:
        return False
    try:
        if hasattr(boton, "invoke"):
            boton.invoke()
        else:
            boton.click_input()
    except Exception:
        try:
            boton.click_input()
        except Exception:
            return False
    return True


def mensaje_salir_es_de_chat(textos: list) -> bool:
    """¿Estos textos son la pregunta de salir con un chat conectado?

    Pura para poder probarla sin ventanas: la pregunta dice
    «¿Salir de la aplicación?» primero y nombra el chat conectado.
    """
    juntos = " ".join(t or "" for t in textos).lower()
    return "salir de la aplicación" in juntos and "chat conectado" in juntos


def contestar_salir_si_aparece(segundos: float = 8.0) -> bool:
    """Contesta Sí a la pregunta «Salir» si está abierta. False si no aparece.

    Mira desde fuera con `dialogo_nativo`, como `escenario_directo_sin_imagen`:
    un `wx.MessageDialog` no sale en `wx.GetTopLevelWindows()` y la sonda no lo
    ve. Nunca pulsa Enter: el botón por defecto es No y cerraría sin salir.
    """
    dlg = dialogo_nativo("Salir", segundos=segundos)
    if dlg is None:
        return False
    if not pulsar_boton_nativo(dlg, "Sí"):
        return False
    limite = time.time() + 4.0
    while time.time() < limite:
        if dialogo_nativo("Salir", segundos=1.0) is None:
            break
        time.sleep(0.3)
    return True


def escenario_menu_chat(app: Aplicacion, args, res: Resultado):
    """El menu contextual de la lista del chat, donde vive casi toda la accion.

    Entre siete y nueve entradas segun haya sesion: copiar, copiar todo,
    releer, abrir enlace, silenciar de dos formas, rehabilitar, y con sesion
    expulsar y banear. Nunca se habia abierto en el banco.

    Se abre con la tecla Aplicaciones, que es como llega quien no usa raton.
    """
    app.pedir("frente")
    app.simular_sesion_youtube(titulo="Prueba del menu contextual")
    app.mensaje("Ana", "hola, mira esto https://example.com/algo")

    limite = time.time() + 12
    lista = None
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(0.3)
    if not lista or not lista.get("items"):
        res.fallo("menu del chat: no llego ningun mensaje a la lista")
        return

    app.pedir("foco", nombre="Chat en vivo")
    app.teclas("down")
    time.sleep(0.5)

    # El menu emergente es una ventana nativa: wx no la expone, hay que
    # mirarla desde fuera igual que los cuadros de `wx.MessageBox`.
    try:
        app.teclas("menu")
    except Exception as exc:
        res.nota("menu del chat: la tecla Aplicaciones no se pudo simular, %s" % exc)
        res.fallo("menu del chat: SIN PROBAR, no se pudo abrir")
        return

    entradas = _entradas_de_menu(segundos=8)
    if not entradas:
        res.fallo("menu del chat: la tecla Aplicaciones no abrio ningun menu "
                  "que Windows exponga")
        _escape()
        return

    res.nota("menu del chat: %d entradas" % len(entradas))
    for e in entradas[:9]:
        res.nota("  " + e[:70])

    juntas = " ".join(entradas).lower()
    for esperada in ("copiar", "releer", "enlace", "silenciar"):
        if esperada not in juntas:
            res.fallo("menu del chat: no aparece ninguna entrada de «%s»"
                      % esperada)
    sin_nombre = [e for e in entradas if not e.strip()]
    if sin_nombre:
        res.fallo("menu del chat: %d entradas sin texto, mudas para el lector"
                  % len(sin_nombre))
    _escape()


def _entradas_de_menu(segundos: float = 8.0) -> list:
    """Los textos de un menu emergente nativo, mirando desde fuera."""
    try:
        from pywinauto import Desktop
    except ImportError:
        return []
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            for w in _candidatas_uia(Desktop):
                try:
                    if w.element_info.control_type != "Menu":
                        continue
                    textos = []
                    for d in w.descendants():
                        try:
                            if d.element_info.control_type == "MenuItem":
                                textos.append((d.element_info.name or "").strip())
                        except Exception:
                            continue
                    if textos:
                        return textos
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.3)
    return []


def _escape() -> None:
    try:
        from pywinauto import keyboard
        keyboard.send_keys("{ESC}")
    except Exception:
        pass
    time.sleep(0.5)


def escenario_captura_atajo(app: Aplicacion, args, res: Resultado):
    """La pestana Atajos, ahora que la captura ya no abre ninguna ventana.

    Hasta el 26/08/2026 esto pulsaba un boton y esperaba un dialogo «Capturar
    atajo». Ese dialogo se borro: ahora el propio boton entra en modo captura.
    El escenario viejo daba un fallo que parecia de la aplicacion y era del
    banco, y estuvo dos dias en el informe.

    LO QUE ESTE ESCENARIO NO CUBRE, y conviene saberlo: no comprueba que teclas
    de verdad lleguen al boton, porque el simulador de wx escribe en la ventana
    que Windows tenga al frente y el banco trae al frente la ventana PRINCIPAL,
    no el dialogo modal de Preferencias. Esa parte, o sea que Escape cancele,
    que Tab salga y que Alt+Enter se capture en vez de desactivar, la cubren
    las pruebas de `tests/test_atajos_captura.py`, una por rama.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo("atajos: no se pudo abrir Preferencias, %s" % exc)
        return
    if app.esperar_ventana("Preferencias", segundos=15) is None:
        res.fallo("atajos: Preferencias no abrio")
        return

    try:
        respuesta = app.pedir("pestanas", ventana="Preferencias")
        paginas = respuesta.get("datos", {}).get("paginas", [])
        indice = next(i for i, n in enumerate(paginas) if "tajo" in n)
        app.pedir("pestanas", ventana="Preferencias", indice=indice)
        time.sleep(0.8)
    except Exception as exc:
        res.fallo("atajos: no se pudo llegar a la pestana, %s" % exc)
        app.pedir("cerrar_ventana", ventana="Preferencias")
        return

    def boton_de(nombre):
        for c in app.arbol("Preferencias"):
            if (c.get("nombre") or "") == nombre:
                return c
        return None

    # Cada boton dice su atajo en la etiqueta, y eso NO es decoracion: es lo
    # unico que lee un lector de pantalla al recorrer la pestana.
    conectar = boton_de("Atajo_conectar")
    if conectar is None:
        res.fallo("atajos: no encuentro el boton de la accion Conectar")
        app.pedir("cerrar_ventana", ventana="Preferencias")
        return
    etiqueta_inicial = (conectar.get("etiqueta") or "").replace("&", "")
    if ":" not in etiqueta_inicial:
        res.fallo("atajos: el boton se llama «%s» y no dice que atajo tiene"
                  % etiqueta_inicial)
    else:
        res.nota("atajos, el boton dice: " + etiqueta_inicial)

    # Entrar en modo captura tiene que anunciarse Y cambiar la etiqueta. Si
    # solo se anunciara, quien vuelve sobre el control mas tarde no tendria
    # forma de saber que esta esperando una combinacion.
    n = len(app.anuncios)
    # El foco PRIMERO, y no es un adorno: el modo captura se sale al perder el
    # foco, asi que si se entra con un evento sintetico sin foco, el boton
    # nunca lo pierde y la comprobacion de mas abajo da un fallo que parece de
    # la aplicacion. Pasó el 26/08/2026 al escribir este escenario.
    app.pedir("foco", ventana="Preferencias", nombre="Atajo_conectar")
    app.pedir("pulsar", nombre="Atajo_conectar")
    time.sleep(0.5)
    if app.esperar_dicho("combinación", segundos=6, desde=n):
        res.nota("atajos: entrar en captura se anuncia")
    else:
        res.fallo("atajos: pulsar el boton no anuncio nada, asi que nadie sabe "
                  "que la aplicacion esta esperando una combinacion")
    ahora = boton_de("Atajo_conectar")
    texto = (ahora.get("etiqueta") or "").replace("&", "") if ahora else ""
    if "combinación" not in texto.lower():
        res.fallo("atajos: en modo captura el boton sigue diciendo «%s», asi "
                  "que su estado no se puede leer" % texto)
    else:
        res.nota("atajos, en captura el boton dice: " + texto)

    # Se sale del modo por el mismo camino que usaria alguien que se arrepiente
    # sin teclado disponible: mover el foco a otro control.
    app.pedir("foco", ventana="Preferencias", nombre="RestablecerAtajos")
    time.sleep(0.5)
    vuelto = boton_de("Atajo_conectar")
    texto = (vuelto.get("etiqueta") or "").replace("&", "") if vuelto else ""
    if texto != etiqueta_inicial:
        res.fallo("atajos: al perder el foco el boton quedo en «%s» y antes "
                  "decia «%s»" % (texto, etiqueta_inicial))
    else:
        res.nota("atajos: perder el foco devuelve la etiqueta a como estaba")

    restablecer = boton_de("RestablecerAtajos")
    if restablecer is None:
        res.fallo("atajos: no hay boton para restablecer los valores de fabrica")
    elif not restablecer.get("habilitado"):
        res.fallo("atajos: el boton de restablecer esta deshabilitado, asi que "
                  "sale del orden de Tab")
    else:
        n = len(app.anuncios)
        app.pedir("pulsar", nombre="RestablecerAtajos")
        if app.esperar_dicho("restablecid", segundos=6, desde=n):
            res.nota("atajos: restablecer se anuncia")
        else:
            res.fallo("atajos: restablecer no anuncio nada")

    revisar_nombres(subarbol(app.arbol("Preferencias"), "PagAtajos"),
                    res, "atajos")
    app.pedir("cerrar_ventana", ventana="Preferencias")


def escenario_redactar(app: Aplicacion, args, res: Resultado):
    """El cuadro de escritura del chat.

    Lo que se comprueba es el contrato que lo hace usable sin ver: que el
    cuadro y el boton esten SIEMPRE, que el boton diga por que no se puede
    usar, y que activarlo sin poder lo anuncie en vez de callarse.
    """
    app.pedir("frente")

    def controles():
        rama = subarbol(app.arbol(), "PanelRedactar")
        cuadro = next((c for c in rama if c["clase"] == "TextCtrl"), None)
        boton = next((c for c in rama if c["clase"] == "Button"), None)
        return cuadro, boton

    cuadro, boton = controles()
    if cuadro is None or boton is None:
        res.fallo("redactar: no encuentro el cuadro o el boton en el arbol")
        return

    # Sin conectar tienen que seguir estando, y habilitados: deshabilitarlos
    # los sacaria del orden de Tab y el motivo quedaria fuera de alcance.
    for ctrl, comovse in ((cuadro, "el cuadro"), (boton, "el boton")):
        if not ctrl.get("habilitado"):
            res.fallo("redactar: %s esta deshabilitado sin conectar, asi que "
                      "sale del orden de Tab y su motivo no se puede leer"
                      % comovse)
    etiqueta = (boton.get("etiqueta") or "").replace("&", "")
    if "(" not in etiqueta:
        res.fallo("redactar: sin conectar, el boton se llama «%s» y no dice "
                  "por que no se puede usar" % etiqueta)
    else:
        res.nota("redactar, sin conectar el boton se llama: " + etiqueta)

    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Enviar mensaje al chat")
    if app.esperar_dicho("conéctate", segundos=6, desde=n):
        res.nota("redactar: activarlo sin conectar lo anuncia en vez de callarse")
    else:
        res.fallo("redactar: activarlo sin conectar no anuncio nada")

    # Conectado, el motivo desaparece.
    app.simular_sesion_youtube(titulo="Prueba del cuadro")
    time.sleep(1.2)
    _, boton = controles()
    etiqueta = (boton.get("etiqueta") or "").replace("&", "")
    if "(" in etiqueta:
        res.fallo("redactar: conectado, el boton sigue diciendo un motivo: «%s»"
                  % etiqueta)
    else:
        res.nota("redactar, conectado el boton vuelve a llamarse: " + etiqueta)

    # Con el cuadro vacio no se manda nada y se avisa.
    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Enviar mensaje al chat")
    if app.esperar_dicho("escribe un mensaje", segundos=6, desde=n):
        res.nota("redactar: con el cuadro vacio avisa en vez de mandar nada")
    else:
        res.fallo("redactar: con el cuadro vacio no avisa")

    orden = recorrer_tab(app, res, "redactar", vueltas=10)
    res.nota("redactar, orden de Tab: " + " > ".join(orden[:5]))
    esperado = ["Chat en vivo", "Mensaje para el chat", "Enviar"]
    juntos = " > ".join(orden)
    if not all(x in juntos for x in esperado):
        res.fallo("redactar: el orden de Tab no pasa por lista, cuadro y "
                  "boton; da %s" % juntos)

    # Se deja como se encontro: este escenario necesita el estado SIN conectar
    # para su primera mitad, y el de mas adelante mide el paso de uno al otro.
    app.restaurar_desconectado()
    time.sleep(0.5)


def escenario_enviar_live(app: Aplicacion, args, res: Resultado):
    """Manda un mensaje de verdad al chat de un directo, punta a punta.

    Es el unico que prueba la ruta de ESCRITURA de la API: credenciales, token,
    `liveChatId` y la llamada. Todo lo demas del cuadro se comprueba sin red en
    `redactar`, pero eso no toca la API ni una vez.

    Necesita tres cosas que no dependen del codigo: un directo emitiendo, sesion
    OAuth iniciada y que el directo tenga el chat abierto. Cuando falle, eso es
    lo primero que hay que descartar. Por eso vive fuera de `todos`.

    Manda la palabra «test» y nada mas, en el directo que el dueno eligio para
    esto. No se manda nada que parezca dirigido a nadie.
    """
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"enviar al chat: {url}")
    if not conectar_de_verdad(app, res, url, "enviar al chat", espera=75.0):
        return

    # El motivo dentro del nombre del boton es el que dice si se puede escribir.
    # Si sigue ahi conectado, no hay sesion o el directo no tiene chat, y eso no
    # es un fallo del cuadro: se dice y se para, en vez de mandar a ciegas.
    boton = None
    limite = time.time() + 30
    while time.time() < limite:
        rama = subarbol(app.arbol(), "PanelRedactar")
        boton = next((c for c in rama if c["clase"] == "Button"), None)
        if boton and "(" not in (boton.get("etiqueta") or ""):
            break
        time.sleep(1.0)
    if boton is None:
        res.fallo("enviar al chat: no encuentro el boton de enviar")
        return
    etiqueta = (boton.get("etiqueta") or "").replace("&", "")
    if "(" in etiqueta:
        res.nota("enviar al chat: NO se manda nada, el boton dice «%s». "
                 "Falta sesion o el directo no tiene chat abierto." % etiqueta)
        return

    app.pedir("foco", nombre="Mensaje para el chat")
    app.pedir("texto", valor="test")
    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Enviar mensaje al chat")

    # Se espera a lo que DICE, no a un reloj: la llamada va en un hilo aparte y
    # tarda lo que tarde la red.
    dicho = ""
    limite = time.time() + 45
    while time.time() < limite:
        dicho = " ".join(a.get("texto", "") for a in app.anuncios[n:]).lower()
        if "enviado" in dicho or "error" in dicho or "no se pudo" in dicho:
            break
        time.sleep(0.5)

    for d in [a.get("texto", "") for a in app.anuncios[n:]][:6]:
        res.nota("  enviar al chat dice: " + d[:90])
    if "enviado" in dicho:
        res.nota("enviar al chat: el mensaje salio y se anuncio")
    elif not dicho:
        res.fallo("enviar al chat: pulse enviar y la aplicacion no dijo nada "
                  "en 45 s. Sin voz, quien no ve no sabe si salio")
    else:
        res.fallo("enviar al chat: no confirmo el envio, dijo: " + dicho[:120])

    # Despues de enviar, el cuadro queda vacio y con el foco: si no, hay que
    # volver a buscarlo con Tab para escribir el siguiente.
    rama = subarbol(app.arbol(), "PanelRedactar")
    cuadro = next((c for c in rama if c["clase"] == "TextCtrl"), None)
    if cuadro is None:
        res.fallo("enviar al chat: el cuadro desaparecio despues de enviar")
    else:
        if (cuadro.get("valor") or "").strip():
            res.fallo("enviar al chat: el cuadro conserva el texto ya enviado, "
                      "asi que el siguiente mensaje saldria repetido")
        else:
            res.nota("enviar al chat: el cuadro queda vacio")


def escenario_cierre(app: Aplicacion, args, res: Resultado):
    """Cerrar la ventana con una sesion abierta.

    Cierra la instancia PRINCIPAL, no una aparte, y por eso va el ultimo de la
    corrida completa. No se puede levantar una segunda: `main.py` tiene guarda
    de instancia unica, avisa y se cierra sola. Costo una corrida descubrirlo.

    Lo que esto NO prueba, y conviene decirlo en vez de dar por cubierto lo que
    no lo esta: aca la sesion esta simulada y NO hay hilos de captura de verdad
    girando, que es justamente el caso que se sospecha del cierre con Alt+F4.
    Ese sigue SIN PROBAR y necesita un directo real.
    """
    app.pedir("frente")
    app.simular_sesion_youtube(titulo="Prueba de cierre")
    app.mensaje("Ana", "hola")
    time.sleep(1.5)
    hilos = app.hilos()
    res.nota("cierre: antes de cerrar hay %d hilos: %s"
             % (len(hilos), ", ".join(sorted(hilos)[:8])))

    arranque = time.time()
    try:
        # Sin forzar, como un Alt+F4: el cierre se puede vetar y la
        # aplicación pregunta «Salir».
        app.pedir("cerrar_ventana", tiempo=6.0, forzar=False)
    except Exception:
        pass  # el cuadro modal se come la respuesta, como en directo_sin_imagen
    dlg = dialogo_nativo("Salir", segundos=8)
    if dlg is None:
        res.fallo("cierre: con una sesión abierta no apareció la pregunta "
                  "«Salir» en 8 s")
    else:
        textos = _textos_de(dlg)
        if not mensaje_salir_es_de_chat(textos):
            res.fallo("cierre: la pregunta «Salir» no trae el mensaje del chat "
                      "conectado: %s" % " / ".join(textos[:2]))
        elif not pulsar_boton_nativo(dlg, "Sí"):
            res.fallo("cierre: la pregunta «Salir» no ofrece ningún botón «Sí»")
        else:
            res.nota("cierre: apareció la pregunta «Salir» con el mensaje del "
                     "chat conectado y se contestó Sí")
            limite = time.time() + 4.0
            while time.time() < limite:
                if dialogo_nativo("Salir", segundos=1.0) is None:
                    break
                time.sleep(0.3)
    limite = time.time() + 20
    murio = False
    while time.time() < limite:
        if app.murio_sola():
            murio = True
            break
        time.sleep(0.5)
    tardanza = time.time() - arranque

    if not murio:
        res.fallo("cierre: la aplicacion no cerro en 20 s con una sesion "
                  "abierta")
        return
    res.nota("cierre: la aplicacion cerro sola en %.1f s" % tardanza)
    # `apagado.TOPE_ESPERA_CIERRE` son 3 segundos. Con margen para que arranque
    # el proceso de cierre, mas de 10 significa que algo se quedo esperando.
    if tardanza > 10:
        res.fallo("cierre: tardo %.1f s, y el tope de espera de las capturas "
                  "es de %.0f s" % (tardanza, 3.0))
    if app.dijo("cerrando"):
        res.nota("cierre: se anuncia antes de cerrar")
    else:
        res.nota("cierre: SIN COMPROBAR que se anuncie; no aparece «cerrando» "
                 "entre lo grabado")


# Cada modulo de interfaz con el escenario que lo recorre. Los `gui*.py` NO se
# listan aca: se descubren del disco en `superficies_sin_escenario`, y esa es
# toda la gracia. Una lista escrita a mano solo caza lo que alguien se acordo
# de anotar, y el 25/08/2026 eso ya dejo dos escenarios registrados fuera de la
# corrida completa sin que nadie avisara. Descubriendo, un `gui_algo.py` nuevo
# sin escenario detiene la corrida y queda nombrado.
#
# La idea es de `miguel-cinsfran/tesis-orquestacion`, donde el barrido de
# accesibilidad descubre las pantallas del sistema de archivos por el mismo
# motivo.
#
# `reproductor.py` e `iconos.py` van a mano porque dibujan interfaz y no se
# llaman `gui*`: sin ellos el descubrimiento miraria para otro lado.
SUPERFICIES = {
    "gui.py": "principal",
    "gui_actualizacion.py": "actualizaciones",
    "gui_actualizar_app.py": "actualizaciones",
    "gui_actualizar_ytdlp.py": "actualizaciones",
    "gui_comentarios.py": "comentarios",
    "gui_descargas.py": "descargas",
    "gui_directo_huerfano.py": "directo_sin_imagen",
    "gui_directo_youtube.py": "transmitir_destino",
    "gui_elegir_destino.py": "transmitir_destino",
    "gui_envio_chat.py": "redactar",
    "gui_estado.py": "principal",
    "gui_historial.py": "historial",
    "gui_menu.py": "menus",
    "gui_musica.py": "musica",
    "musica_dialogo_enlace.py": "musica",
    "musica_colecciones.py": "musica",
    "musica_editor_lista.py": "musica",
    "musica_menus.py": "musica",
    "musica_ventana.py": "musica",
    "musica_ventana_acciones.py": "musica",
    "musica_ventana_igualando.py": "musica",
    "ia_ventana.py": "ia",
    "ia_agregar_captura.py": "ia",
    "ia_consulta_rapida.py": "ia",
    "ia_privacidad.py": "ia",
    "gui_transmision.py": "transmision",
    "gui_transmitir.py": "transmitir_destino",
    "gui_preferencias.py": "preferencias",
    "gui_redactar.py": "redactar",
    "reproductor.py": "reproductor",
    "iconos.py": "reproductor",
    "boton_directo.py": "principal",
    "preferencias_musica.py": "preferencias",
    "preferencias_sonidos.py": "preferencias",
    "preferencias_ia.py": "preferencias",
    "preferencias_ia_clave.py": "preferencias",
    "preferencias_ia_lista.py": "preferencias",
    "preferencias_programados.py": "preferencias",
    "paleta.py": "actualizaciones",
}

# Módulos que dibujan interfaz sin escena a propósito: cada uno lleva su
# motivo como valor y no cuenta como huérfano en `superficies_sin_escenario()`.
SIN_ESCENARIO: dict[str, str] = {}

EXTRAS_DE_INTERFAZ = ("reproductor.py", "iconos.py")

# Un modulo de `ytchat/ui/` o de `ytchat/player/` dibuja interfaz si crea o
# hereda de un control de wx. Los que solo calculan, tocan la red o piden
# `wx.CallAfter` no se exigen en el barrido: no tienen pantalla que auditar.
CLASES_DE_WX_QUE_DIBUJAN = frozenset({
    "Dialog", "Frame", "Panel", "Menu", "MenuBar", "StaticText", "TextCtrl",
    "Button", "BitmapButton", "Choice", "ComboBox", "ListBox", "ListCtrl",
    "CheckBox", "RadioButton", "RadioBox", "Slider", "SpinCtrl", "Notebook",
    "TextEntryDialog", "SingleChoiceDialog", "MessageDialog", "DirDialog",
    "FileDialog", "FilePickerCtrl", "DirPickerCtrl",
})


def dibuja_interfaz(ruta: Path) -> bool:
    """Si el modulo crea o hereda de un control de wx, mirando su codigo."""
    import ast
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ClassDef):
            bases = nodo.bases
        elif isinstance(nodo, ast.Call):
            bases = [nodo.func]
        else:
            continue
        for base in bases:
            if (isinstance(base, ast.Attribute)
                    and isinstance(base.value, ast.Name)
                    and base.value.id == "wx"
                    and base.attr in CLASES_DE_WX_QUE_DIBUJAN):
                return True
    return False


def superficies_sin_escenario() -> list[str]:
    """Modulos de interfaz que existen en el disco y no tiene quien los mire."""
    ui = RAIZ / "ytchat" / "ui"
    reproductor = RAIZ / "ytchat" / "player"
    modulos = {p.name
               for carpeta in (ui, reproductor)
               for p in carpeta.glob("*.py")
               if dibuja_interfaz(p)}
    modulos.update(p.name for p in ui.glob("gui*.py"))
    modulos.update(n for n in EXTRAS_DE_INTERFAZ
                   if (ui / n).exists() or (reproductor / n).exists())
    if not modulos:
        raise RuntimeError(
            "no se encontró ningún módulo de interfaz en ytchat/ui/ ni en "
            "ytchat/player/: el descubrimiento mira para otro lado y el banco "
            "quedaría en verde sin recorrer nada")
    huerfanos = []
    for nombre in sorted(modulos):
        if nombre in SIN_ESCENARIO:
            continue
        escenario = SUPERFICIES.get(nombre)
        if escenario is None or escenario not in ESCENARIOS:
            huerfanos.append(nombre)
    return huerfanos


# Escenarios que a proposito NO entran en `todos`, con su motivo. Los tres
# necesitan un directo de verdad emitiendo ahora mismo: en una corrida rutinaria
# fallarian por la red o porque el directo termino, no por la aplicacion.
FUERA_DE_TODOS = frozenset({
    "directo_youtube",   # pide un directo de YouTube vivo
    "directo_tiktok",    # pide un directo de TikTok vivo
    "reproductor_en_marcha",  # pide un vídeo y un directo reales
    "dos_conexiones",    # conecta dos veces a un directo vivo
    "enviar_live",       # escribe de verdad en un chat: pide directo y sesion
    "musica_real",       # suena de verdad, usa la red y cambia la
                         # configuración mientras corre
})

ESCENARIOS = {
    "menus": escenario_menus,
    "principal": escenario_principal,
    "descargas": escenario_descargas,
    "preferencias": escenario_preferencias,
    "preferencias_categorias": escenario_preferencias_categorias,
    "preferencias_persisten": escenario_preferencias_persisten,
    "historial": escenario_historial,
    "transmision": escenario_transmision,
    "musica": escenario_musica,
    "musica_real": escenario_musica_real,
    "ia": escenario_ia,
    "ayuda": escenario_ayuda,
    "dialogos_ayuda": escenario_dialogos_ayuda,
    "chat": escenario_chat,
    "actualizaciones": escenario_actualizaciones,
    "transmitir_destino": escenario_transmitir_destino,
    "comentarios": escenario_comentarios,
    "conectar": escenario_conectar,
    "directo_sin_imagen": escenario_directo_sin_imagen,
    "menu_chat": escenario_menu_chat,
    "captura_atajo": escenario_captura_atajo,
    "redactar": escenario_redactar,
    "cierre": escenario_cierre,
    "tiktok": escenario_tiktok,
    "avisos_wx": escenario_avisos_wx,
    "diagnostico": escenario_diagnostico,
    "reproductor": escenario_reproductor,
    "arranque_frio": escenario_arranque_frio,
    "directo_youtube": escenario_directo_youtube,
    "dos_conexiones": escenario_dos_conexiones,
    "directo_tiktok": escenario_directo_tiktok,
    "reproductor_en_marcha": escenario_reproductor_en_marcha,
    "overlay": escenario_overlay,
    "programados": escenario_programados,
    "enviar_live": escenario_enviar_live,
}


_ESCENARIO_EN_CURSO = "ninguno todavía"


def _armar_tope_global(minutos: float, app) -> None:
    """Mata la corrida entera si se cuelga, diciendo en qué escenario fue.

    Cada espera del banco tiene su propio tope, pero la corrida no tenía
    ninguno. El 25/08/2026 se colgó con el diálogo de Preferencias abierto y se
    quedó así hasta que alguien lo mató a mano, con la máquina del dueño
    secuestrada. Un banco que puede no terminar no se puede dejar corriendo.

    Sale con `os._exit` a propósito: si el hilo principal está bloqueado dentro
    de una llamada nativa, una excepción no lo despierta.
    """
    def _matar():
        print()
        print(f"TOPE: la corrida pasó de {minutos:g} minutos y se corta.")
        print(f"Se colgó en el escenario: {_ESCENARIO_EN_CURSO}")
        print("La aplicación se cierra igual. Esto es un fallo del banco o del")
        print("escenario, no necesariamente de la aplicación.")
        try:
            app.cerrar()
        except Exception:
            pass
        sys.stdout.flush()
        os._exit(2)

    temporizador = threading.Timer(minutos * 60, _matar)
    temporizador.daemon = True
    temporizador.start()


# Los escenarios que dejan un chat conectado (simulado o real): al
# terminar cada uno se captura la ventana principal ya conectada.
ESCENARIOS_QUE_CONECTAN = frozenset({
    "chat", "tiktok", "directo_youtube", "directo_tiktok", "dos_conexiones",
    "reproductor_en_marcha", "enviar_live",
})


def _argumentos(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--escenario", action="append", default=None,
                   choices=sorted(ESCENARIOS) + ["todos"])
    p.add_argument("--url-youtube", dest="url_youtube",
                   default=None, help="directo de YouTube a usar")
    p.add_argument("--url-tiktok", dest="url_tiktok",
                   default=None, help="directo de TikTok a usar")
    p.add_argument("--url-vod", dest="url_vod",
                   default=None, help="vídeo grabado de YouTube a usar")
    p.add_argument("--con-navegador", action="store_true",
                   dest="con_navegador",
                   help="permite abrir el navegador de verdad")
    p.add_argument("--carpeta", default=None,
                   help="dónde dejar las grabaciones")
    p.add_argument("--carpeta-musica", dest="carpeta_musica", default=None,
                   help="carpeta con música para el escenario musica_real")
    p.add_argument("--tope-minutos", dest="tope_minutos", type=float,
                   default=20.0,
                   help="corta la corrida entera si se cuelga (0 lo desactiva)")
    p.add_argument("--capturas", nargs="?", const="__auto__", default=None,
                   metavar="CARPETA",
                   help="guarda un PNG de cada ventana que el banco abre, "
                   "más un índice; sin valor usa "
                   "qa/salida/capturas/<fecha-hora>")
    _argumentos.p = p
    return p.parse_args(argv)


# Quién captura y para qué escenario, mientras corre con `--capturas`.
# El bucle de `main` lo mantiene al día; sin la opción queda en `None` y
# no se pide ni una orden nueva a la sonda.
_CAPTURA_EN_CURSO = {"captor": None, "escenario": ""}


class Captor:
    """Pide PNG a la sonda y lleva el índice. Nunca hace fallar nada."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.registro = capturas.RegistroCapturas(self.carpeta)

    def capturar(self, app, escenario, ventana, extra="") -> bool:
        try:
            return self._capturar(app, escenario, ventana, extra)
        except Exception:
            return False

    def _capturar(self, app, escenario, ventana, extra="") -> bool:
        reserva = self.registro.reservar(escenario, ventana, extra)
        if reserva is None:
            return False
        n, base = reserva
        try:
            r = app.pedir("capturar", ventana=ventana,
                          carpeta=str(self.carpeta), base=base, paginas=True,
                          tiempo=30.0)
        except Exception as exc:
            self.registro.anotar_fallo(n, escenario, ventana,
                                       f"la sonda no contestó: {exc}")
            return False
        if not r.get("ok"):
            self.registro.anotar_fallo(n, escenario, ventana,
                                       str(r.get("error", "sin motivo")))
            return False
        for f in r.get("datos", {}).get("archivos", []):
            titulo = f.get("titulo") or ventana
            if f.get("fallo") or not f.get("archivo"):
                self.registro.anotar_fallo(n, escenario, titulo,
                                           f.get("fallo") or "sin archivo")
            else:
                self.registro.anotar_ok(
                    n, f["archivo"], escenario, titulo,
                    f.get("pestana") or "",
                    (f.get("ancho", 0), f.get("alto", 0)), f.get("minimo"))
        return True

    def escribir_indice(self) -> Path:
        return self.registro.escribir()


def _instalar_capturas(captor):
    """Engancha `esperar_ventana`: cada ventana nueva se captura una vez.

    Es el punto común por el que pasa todo el banco (los diálogos que
    audita `auditar_dialogo` también), así que ningún escenario se toca.
    Devuelve la función original para restaurarla al terminar.
    """
    original = Aplicacion.esperar_ventana

    def _esperar_y_capturar(self, titulo, segundos=15.0):
        ventana = original(self, titulo, segundos)
        if ventana is not None and _CAPTURA_EN_CURSO["captor"] is not None:
            try:
                _CAPTURA_EN_CURSO["captor"].capturar(
                    self, _CAPTURA_EN_CURSO["escenario"],
                    ventana.get("titulo") or titulo)
            except Exception:
                pass
        return ventana

    Aplicacion.esperar_ventana = _esperar_y_capturar
    return original


# La corrida completa va a mano porque el ORDEN importa. `reproductor` va
# primero y no es capricho: comprueba qué dice la aplicación con NADA
# cargado, y en cuanto `chat` o `tiktok` simulan una sesión ese estado ya no
# vuelve sin reiniciar. Corrido después, el botón de reproducir pasa la
# comprobación por el motivo equivocado.
EN_TODOS = ["arranque_frio", "reproductor",
            "menus", "principal", "descargas", "preferencias",
            "preferencias_categorias", "preferencias_persisten",
            "programados", "historial", "transmision",
            # `musica` va con `historial` y `transmision`: audita
            # diálogos sin necesitar sesión, así que corre antes de
            # que `chat` simule una.
            "musica", "ia", "ayuda", "dialogos_ayuda",
            # `redactar` va antes que `chat` y no es capricho: la
            # mitad de lo que comprueba es como se comporta SIN
            # conectar, y en cuanto `chat` simula una sesion ese estado
            # no vuelve. Corrido despues, pasaba por el motivo
            # equivocado. Mismo motivo que `reproductor`.
            "conectar", "directo_sin_imagen", "captura_atajo", "redactar",
            # `transmitir_destino` va acá y no es capricho: necesita
            # el botón «Transmitir en directo», que solo se ve
            # desconectado, y `redactar` es el último que deja ese
            # estado antes de que `chat` simule una sesión.
            "actualizaciones", "transmitir_destino",
            "overlay", "chat", "menu_chat",
            "comentarios", "tiktok", "avisos_wx", "diagnostico", "cierre"]


def main() -> int:
    args = _argumentos()
    p = _argumentos.p

    pedidos = args.escenario or ["todos"]
    if "todos" in pedidos:
        pedidos = list(EN_TODOS)
        # Un escenario registrado que no este ni aca ni entre los excluidos no
        # se corre NUNCA con `todos`, y no lo dice nadie. Paso el 25/08/2026:
        # se agregaron `overlay` y `programados` al registro y quedaron fuera de
        # la corrida completa sin una linea de aviso. La lista va a mano porque
        # el ORDEN importa, asi que la unica defensa es comprobar que no falte.
        olvidados = sorted(set(ESCENARIOS) - set(pedidos) - FUERA_DE_TODOS)
        if olvidados:
            p.error("estos escenarios estan registrados pero no se corren con "
                    "`todos` ni figuran en FUERA_DE_TODOS: %s. Agregalos a la "
                    "lista, en el lugar que corresponda por orden, o a "
                    "FUERA_DE_TODOS con su motivo." % ", ".join(olvidados))

        # Y el otro lado del mismo agujero: un modulo de interfaz que nacio y
        # no tiene quien lo recorra. La guarda de arriba solo mira lo que ya
        # esta registrado, asi que no habria dicho nada de `gui_comentarios.py`,
        # que existia desde el principio y nunca entro en el banco.
        huerfanos = superficies_sin_escenario()
        if huerfanos:
            p.error("estos modulos de interfaz no tienen escenario que los "
                    "recorra: %s. Escribi uno y anotalo en SUPERFICIES."
                    % ", ".join(huerfanos))

    # Por defecto, dentro de `qa/salida/`, que está en el `.gitignore`: las
    # grabaciones llevan la salida cruda de la aplicación y no se suben. Fuera de
    # versiones. En la raíz ensuciaba el repositorio con tres archivos sueltos
    # después de cada corrida.
    carpeta = Path(args.carpeta) if args.carpeta else (RAIZ / "qa" / "salida")
    carpeta.mkdir(parents=True, exist_ok=True)
    app = Aplicacion(carpeta)
    res = Resultado()
    # Sin `--capturas` esto queda en `None` y el banco pide exactamente las
    # mismas órdenes que hoy: ninguna llamada nueva a la sonda.
    captor = None
    if args.capturas is not None:
        if args.capturas == "__auto__":
            carpeta_cap = (RAIZ / "qa" / "salida" / "capturas"
                           / capturas.carpeta_por_defecto())
        else:
            carpeta_cap = Path(args.capturas)
        captor = Captor(carpeta_cap)
        args.captor = captor
        _CAPTURA_EN_CURSO["captor"] = captor
        _esperar_original = _instalar_capturas(captor)
    if args.tope_minutos > 0:
        _armar_tope_global(args.tope_minutos, app)

    # El arranque en frío monta su propia aplicación, y `main.py` no admite dos
    # a la vez. Va antes de levantar la compartida, y no dentro del bucle.
    if "arranque_frio" in pedidos:
        pedidos = [n for n in pedidos if n != "arranque_frio"]
        print()
        print("--- escenario: arranque_frio ---")
        try:
            escenario_arranque_frio(app, args, res)
        except Exception as exc:
            res.fallo(f"arranque_frio: el escenario reventó, {exc!r}")

    # `musica_real` también monta su propia aplicación con datos preparados,
    # igual que `arranque_frio`: la configuración se escribe ANTES de lanzar.
    if "musica_real" in pedidos:
        pedidos = [n for n in pedidos if n != "musica_real"]
        print()
        print("--- escenario: musica_real ---")
        try:
            escenario_musica_real(app, args, res)
        except Exception as exc:
            res.fallo(f"musica_real: el escenario reventó, {exc!r}")

    print("Arrancando la aplicación con la sonda puesta. No va a hablar.")
    obs_al_empezar = obs_abierto()
    app.arrancar()
    try:
        if not app.esperar_lista(segundos=60):
            print("La aplicación no contestó al ping en 60 segundos.")
            return 1
        print("Lista y contestando órdenes.")
        # Prueba de que la sonda está puesta, no de que yo lo crea.
        if not app.dijo("grabador instalado"):
            print("AVISO: la sonda no dejó constancia. Podría estar hablando.")
        if captor is not None:
            _CAPTURA_EN_CURSO["escenario"] = "arranque"
            captor.capturar(app, "arranque", "principal")

        for nombre in pedidos:
            global _ESCENARIO_EN_CURSO
            _ESCENARIO_EN_CURSO = nombre
            _CAPTURA_EN_CURSO["escenario"] = nombre
            print()
            print(f"--- escenario: {nombre} ---")
            try:
                ESCENARIOS[nombre](app, args, res)
            except Exception as exc:
                res.fallo(f"{nombre}: el escenario reventó, {exc!r}")
            if captor is not None and nombre in ESCENARIOS_QUE_CONECTAN:
                captor.capturar(app, nombre, "principal")
    finally:
        if captor is not None:
            Aplicacion.esperar_ventana = _esperar_original
            _CAPTURA_EN_CURSO["captor"] = None
        app.cerrar()
        # Si el banco abrió OBS y no estaba al empezar, se lo cierra: no se le
        # puede dejar al dueño una aplicación abierta que no tenía. El cierre
        # que hace `transmitir_destino` cubre su escenario; este cubre la
        # corrida entera, por si otro escenario lo dejó abierto.
        try:
            if debe_cerrar_obs_al_final(obs_al_empezar, obs_abierto()):
                cerrar_obs_del_banco(res)
        except Exception:
            pass

    if captor is not None:
        try:
            ruta_indice = captor.escribir_indice()
            print(f"  Capturas en {captor.carpeta} ({len(captor.registro.lineas)} "
                  f"renglones), índice en {ruta_indice.name}")
        except Exception as exc:
            print(f"  AVISO: no se pudo escribir el índice de capturas: {exc}")

    print()
    print("=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"  {len(res.notas)} comprobaciones, {len(res.fallos)} fallos, "
          f"{len(res.sin_probar)} sin probar.")
    print(f"  Anuncios grabados: {len(app.anuncios)}, "
          f"en {app.anuncios_ruta.name}")
    print("  Esto no prueba que NVDA lo lea, ni cómo suena, ni la braille.")

    # Los fallos, aparte y en un archivo. Una corrida completa son veinte
    # minutos y mas de cien lineas: buscar los fallos volviendo atras en la
    # terminal es incomodo con lector de pantalla, y con el buffer lleno
    # directamente se pierden.
    informe = carpeta / "qa-informe.txt"
    try:
        lineas = ["Banco de QA de YTChat TTS",
                  "escenarios: " + ", ".join(pedidos),
                  "%d comprobaciones, %d fallos, %d sin probar"
                  % (len(res.notas), len(res.fallos), len(res.sin_probar)), ""]
        if res.fallos:
            lineas.append("FALLOS")
            lineas += ["%2d. %s" % (i, x)
                       for i, x in enumerate(res.fallos, 1)]
        if res.sin_probar:
            lineas.append("SIN PROBAR")
            lineas += ["%2d. %s" % (i, x)
                       for i, x in enumerate(res.sin_probar, 1)]
        if not res.fallos and not res.sin_probar:
            lineas.append("Sin fallos.")
        elif not res.fallos:
            lineas.append("Sin fallos, pero %d comprobaciones quedaron "
                          "sin probar." % len(res.sin_probar))
        lineas += ["", "NOTAS"]
        lineas += ["    " + x for x in res.notas]
        informe.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        print(f"  Informe con los fallos en {informe}")
    except Exception as exc:
        print(f"  AVISO: no se pudo escribir el informe: {exc}")
    if res.fallos:
        return 1
    if res.sin_probar:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

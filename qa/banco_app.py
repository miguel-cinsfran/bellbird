"""Piezas del banco de QA que lanzan y manejan la aplicación desde fuera.

Aquí vive todo lo que no es de un escenario concreto: la aplicación con su
canal de órdenes, el resultado de una corrida, las excepciones del banco, el
envío de teclas, la espera de ventanas, las capturas y los ayudantes que usan
varios escenarios.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

from guyrapu.core.config import APP_NAME  # noqa: E402

from sonda import VAR_DESTINO, VAR_ORDENES, VAR_RESULTADOS  # noqa: E402

import capturas  # noqa: E402
import fugas_banco  # noqa: E402

TIEMPO_ORDEN = 20.0
_TIEMPOS: list[dict] = []

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
        inicio = time.monotonic()
        try:
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
            raise TimeoutError(
                f"la orden {op!r} no contestó en {tiempo} s")
        finally:
            _TIEMPOS.append({
                "escenario": _ESCENARIO_EN_CURSO,
                "orden": op,
                "segundos": time.monotonic() - inicio,
                "tipo": "orden",
                "inicio": inicio,
            })

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

    def hilos_con_daemon(self) -> list[dict]:
        """Los hilos vivos con su nombre y si son daemon."""
        return self.pedir("hilos").get("datos", {}).get("hilos", [])

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


def es_ventana_de_la_app(nombre: str) -> bool:
    """Si el titulo es de la ventana principal de la app (nombre en APP_NAME).

    Los dos formatos salen de gui.py: el nombre con la version delante y el
    nombre detras del titulo de la sesion. No alcanza con buscar el nombre al
    principio: la ventana del Explorador de la carpeta del repositorio se
    llama igual y entraria.
    """
    minusculas = (nombre or "").lower()
    app = APP_NAME.lower()
    resto = minusculas[len(app):]
    return ((minusculas.startswith(app) and resto.startswith(" ")
             and resto[1:2].isdigit())
            or minusculas.endswith(f" — {app}"))


def nombres_sin_daemon(hilos: list[dict]) -> list[str]:
    """Los nombres de los hilos que pueden retener el cierre, en orden."""
    return sorted(hilo.get("nombre", "") for hilo in hilos
                  if not hilo.get("daemon"))


def titulo_de_la_principal(ventanas: list[dict]) -> str:
    """El título de la ventana principal entre las visibles, o "" si no está."""
    for ventana in ventanas:
        titulo = ventana.get("titulo") or ""
        if ventana.get("visible") and es_ventana_de_la_app(titulo):
            return titulo
    return ""


def cerrar_ventanas_sobrantes(app: Aplicacion, res: Resultado,
                              escenario: str) -> None:
    """Cierra las ventanas visibles que un escenario dejó fuera de la principal.

    No cierra la principal ni las invisibles. Si una no se deja cerrar, lo
    anota y sigue con las demás.
    """
    if app.proceso is None or app.proceso.poll() is not None:
        return
    try:
        ventanas = app.ventanas()
    except Exception:
        return
    principal = titulo_de_la_principal(ventanas)
    for ventana in fugas_banco.ventanas_sobrantes(ventanas, principal):
        titulo = ventana.get("titulo") or ""
        res.fallo(f"{escenario}: dejó abierta la ventana «{titulo}»")
        try:
            app.pedir("cerrar_ventana", ventana=titulo, tiempo=5.0)
        except Exception:
            res.fallo(f"{escenario}: no se pudo cerrar la ventana «{titulo}»")
            continue
        if app.esperar_ventana(titulo, segundos=2) is not None:
            res.fallo(f"{escenario}: no se pudo cerrar la ventana «{titulo}»")


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
            if not es_ventana_de_la_app(w.element_info.name):
                continue
        except Exception:
            continue
        for d in w.descendants():
            yield d


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



# Enlaces que dio el dueno el 21/08/2026 para poder probar contra la red.
# Un directo caduca: si el escenario dice que no hay nadie emitiendo, lo
# primero que hay que mirar es si el enlace sigue vivo, no el codigo.
# Directo de TN, que emite siempre y tiene el chat lleno. Lo eligio el
# dueno el 26/08/2026 como el sitio donde probar: es publico, va rapido
# y a nadie le llama la atencion un mensaje suelto.
DIRECTO_YOUTUBE = "https://www.youtube.com/watch?v=cb12KmMMDJA"


def conectar_de_verdad(app: Aplicacion, res: Resultado, url: str,
                       donde: str, espera: float = 60.0):
    """Pega una URL, pulsa Conectar, y espera a que la aplicacion diga algo.

    Es el unico escenario que toca la red, y por eso es el unico que puede
    fallar por motivos ajenos al codigo. Cuando falle, antes de tocar nada hay
    que comprobar a mano que el directo siga emitiendo.
    """
    app.al_frente()
    # Por el nombre COMPLETO del campo. Pedir foco por «Enlace» a secas caía en la
    # etiqueta «Enlace o ID:», que tambien contiene esa palabra y va antes en el
    # arbol, y entonces el enlace no se escribia nunca. El escenario no lo decia
    # porque las ordenes rechazadas se ignoraban; con `pedir` estricto salta.
    app.pedir("foco", nombre="Enlace del directo o vídeo")
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
    `_boton_dejarlo_en_curso`, pero con el nombre por parámetro: la pregunta
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


_ESCENARIO_EN_CURSO = "ninguno todavía"


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

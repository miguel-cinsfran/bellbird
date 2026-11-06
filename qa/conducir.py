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
import os
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

from guyrapu.core.config import APP_NAME  # noqa: E402

import capturas  # noqa: E402
import tiempos_banco  # noqa: E402

import banco_app  # noqa: E402
import banco_auditoria  # noqa: E402
from banco_app import (  # noqa: E402
    Aplicacion, Captor, Resultado, _CAPTURA_EN_CURSO, _ESCENARIO_EN_CURSO,
    _TIEMPOS, _instalar_capturas, cerrar_ventanas_sobrantes,
    contestar_salir_si_aparece, es_ventana_de_la_app,  # noqa: F401
    nombres_sin_daemon,  # noqa: F401
)
from banco_auditoria import (  # noqa: E402
    VUELTAS_TAB_TRANSMISION, _con_tope, faltan_habilitados,  # noqa: F401
    recorrer_tab,  # noqa: F401
)
from escenarios_app import (  # noqa: E402
    _version_coherente, avisos_wx,  # noqa: F401
    escenario_actualizaciones,
    escenario_arranque_frio, escenario_avisos_wx, escenario_ayuda,
    escenario_cierre, escenario_descargas, escenario_diagnostico,
    escenario_dialogos_ayuda, escenario_historial, escenario_ia,
    escenario_menus, escenario_principal,
)
from escenarios_chat import (  # noqa: E402
    escenario_captura_atajo, escenario_chat, escenario_comentarios,
    escenario_conectar, escenario_directo_sin_imagen,
    escenario_directo_tiktok, escenario_directo_youtube,
    escenario_dos_conexiones, escenario_enviar_live, escenario_menu_chat,
    escenario_redactar, escenario_tiktok,
)
from escenarios_musica import (  # noqa: E402
    escenario_musica, escenario_musica_real,
    escenario_reproductor, escenario_reproductor_en_marcha,
)
from musica_real import aguja_grupo, agujas_unicas  # noqa: E402, F401
from escenarios_obs import (  # noqa: E402
    cerrar_obs_del_banco, debe_cerrar_obs_al_final, escenario_encuadre,
    escenario_escena, escenario_grabacion, escenario_microfono,
    escenario_overlay, escenario_restream, escenario_transmision,
    escenario_transmitir_destino, limpiar_sentinel_obs,  # noqa: F401
    obs_abierto,
)
from escenarios_preferencias import (  # noqa: E402
    escenario_preferencias, escenario_preferencias_categorias,
    escenario_preferencias_persisten, escenario_programados,
)

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
    "confirmar_salida.py": "principal",
    "titulo_ventana.py": "principal",
    "gui_actualizacion.py": "actualizaciones",
    "gui_actualizar_app.py": "actualizaciones",
    "gui_actualizar_ytdlp.py": "actualizaciones",
    "gui_aplicar_preferencias.py": "preferencias",
    "gui_comentarios.py": "comentarios",
    "gui_descargas.py": "descargas",
    "descargas_buscador.py": "descargas",
    "buscador_filtros.py": "descargas",
    "buscador_acciones.py": "descargas",
    "buscador_escucha.py": "descargas",
    "elegir_formato.py": "descargas",
    "buscador_contenido.py": "descargas",
    "buscador_tandas.py": "descargas",
    "barra_progreso.py": "descargas",
    "descargas_listas.py": "descargas",
    "descargas_acciones.py": "descargas",
    "aviso_progreso.py": "descargas",
    "gui_directo_huerfano.py": "directo_sin_imagen",
    "gui_directo_youtube.py": "transmitir_destino",
    "gui_elegir_destino.py": "transmitir_destino",
    "gui_envio_chat.py": "redactar",
    "gui_estado.py": "principal",
    "dialogo_estado.py": "principal",
    "gui_historial.py": "historial",
    "gui_grabaciones.py": "grabacion",
    "obs_ventana.py": "escena",
    "obs_pagina_grabacion.py": "grabacion",
    "obs_pagina_general.py": "escena",
    "restream_ventana.py": "restream",
    "restream_pagina_perfiles.py": "restream",
    "restream_pagina_destinos.py": "restream",
    "restream_pagina_cuenta.py": "restream",
    "restream_pagina_eventos.py": "restream",
    "recientes_inicio.py": "principal",
    "gui_menu.py": "menus",
    "menu_obs.py": "menus",
    "menu_transmision.py": "menus",
    "gui_microfono.py": "microfono",
    "guia_encuadre.py": "encuadre",
    "gui_musica.py": "musica",
    "musica_dialogo_enlace.py": "musica",
    "musica_colecciones.py": "musica",
    "musica_editor_lista.py": "musica",
    "musica_filtros.py": "musica",
    "musica_menus.py": "musica",
    "musica_ventana.py": "musica",
    "musica_ventana_acciones.py": "musica",
    "musica_ventana_igualando.py": "musica",
    "ia_ventana.py": "ia",
    "ia_agregar_captura.py": "ia",
    "ia_consulta_rapida.py": "ia",
    "ia_privacidad.py": "ia",
    "gui_transmision.py": "transmision",
    "escena_pagina_escena.py": "escena",
    "escena_pagina_fuentes.py": "escena",
    "escena_agregar_fuente.py": "escena",
    "escena_propiedades.py": "escena",
    "escena_menu_fuente.py": "escena",
    "escena_menu_escena.py": "escena",
    "escena_edicion_fuente.py": "escena",
    "escena_captura_ventana.py": "escena",
    "escena_pagina_audio.py": "escena",
    "escena_escucha.py": "escena",
    "escena_tamano.py": "escena",
    "escena_filtros.py": "escena",
    "escena_disenos.py": "escena",
    "control_grabacion.py": "transmision",
    "directo_panel.py": "transmision",
    "mover_con_flechas.py": "escena",
    "confirmar_transmision.py": "transmision",
    "gui_transmitir.py": "transmitir_destino",
    "gui_preferencias.py": "preferencias",
    "gui_redactar.py": "redactar",
    "reproductor.py": "reproductor",
    "pantalla_completa.py": "reproductor",
    "iconos.py": "reproductor",
    "boton_directo.py": "principal",
    "camara_atajos.py": "principal",
    "accesibilidad.py": "principal",
    "preferencias_comun.py": "preferencias",
    "preferencias_api.py": "preferencias",
    "preferencias_atajos.py": "preferencias",
    "preferencias_general.py": "preferencias",
    "preferencias_musica.py": "preferencias",
    "preferencias_descargas.py": "preferencias",
    "preferencias_sonidos.py": "preferencias",
    "preferencias_ia.py": "preferencias",
    "preferencias_ia_clave.py": "preferencias",
    "preferencias_ia_lista.py": "preferencias",
    "preferencias_lectura.py": "preferencias",
    "preferencias_eventos.py": "preferencias",
    "preferencias_programados.py": "preferencias",
    "preferencias_transmision.py": "preferencias",
    "preferencias_camara.py": "preferencias",
    "preferencias_voz.py": "preferencias",
    "preferencias_voz_secundaria.py": "preferencias",
    "paleta.py": "actualizaciones",
}

# Módulos que dibujan interfaz sin escena a propósito: cada uno lleva su
# motivo como valor y no cuenta como huérfano en `superficies_sin_escenario()`.
SIN_ESCENARIO: dict[str, str] = {
    "operaciones_obs.py": "opera sobre OBS en un hilo para las ventanas; no abre una propia.",
    "comandos_grabacion.py": "comandos del menú OBS que actúan sobre OBS; no abren ventana.",
    "comandos_clips.py": "comanda el búfer de clips del menú OBS; no abre ventana.",
    "restream_perfil.py": "El banco no tiene cuenta ni canales; el diálogo lo cubren las pruebas con wx.",
    "restream_dialogos_destino.py": "El banco no tiene cuenta ni canales; los cuadros los cubren las pruebas con wx.",
    "agregar_camara.py": "El banco no tiene cámara de Windows; el flujo lo cubren las pruebas con wx y la prueba contra OBS real.",
    "confirmar.py": "Envuelve los cuadros nativos de Windows; no abre una ventana propia.",
}

EXTRAS_DE_INTERFAZ = ("reproductor.py", "iconos.py")

# Un modulo de `guyrapu/ui/` o de `guyrapu/player/` dibuja interfaz si crea o
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
    ui = RAIZ / "guyrapu" / "ui"
    reproductor = RAIZ / "guyrapu" / "player"
    modulos = {p.name
               for carpeta in (ui, reproductor)
               for p in carpeta.glob("*.py")
               if dibuja_interfaz(p)}
    modulos.update(p.name for p in ui.glob("gui*.py"))
    modulos.update(n for n in EXTRAS_DE_INTERFAZ
                   if (ui / n).exists() or (reproductor / n).exists())
    if not modulos:
        raise RuntimeError(
            "no se encontró ningún módulo de interfaz en guyrapu/ui/ ni en "
            "guyrapu/player/: el descubrimiento mira para otro lado y el banco "
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
    "restream": escenario_restream,
    "transmision": escenario_transmision,
    "escena": escenario_escena,
    "grabacion": escenario_grabacion,
    "microfono": escenario_microfono,
    "encuadre": escenario_encuadre,
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


def correr_escenario(nombre: str, app: Aplicacion, args, res: Resultado,
                     duraciones: list[tuple[str, float]]) -> None:
    """Corre un escenario, mide lo que tarda y cierra lo que dejó abierto."""
    global _ESCENARIO_EN_CURSO
    _ESCENARIO_EN_CURSO = nombre
    banco_app._ESCENARIO_EN_CURSO = nombre
    banco_auditoria._ESCENARIO_EN_CURSO = nombre
    _CAPTURA_EN_CURSO["escenario"] = nombre
    print()
    print(f"--- escenario: {nombre} ---")
    inicio = time.monotonic()
    try:
        ESCENARIOS[nombre](app, args, res)
    except Exception as exc:
        res.fallo(f"{nombre}: el escenario reventó, {exc!r}")
    finally:
        duraciones.append((nombre, time.monotonic() - inicio))
        cerrar_ventanas_sobrantes(app, res, nombre)


# La corrida completa va a mano porque el ORDEN importa. `reproductor` va
# primero y no es capricho: comprueba qué dice la aplicación con NADA
# cargado, y en cuanto `chat` o `tiktok` simulan una sesión ese estado ya no
# vuelve sin reiniciar. Corrido después, el botón de reproducir pasa la
# comprobación por el motivo equivocado.
EN_TODOS = ["arranque_frio", "reproductor",
            "menus", "principal", "descargas", "preferencias",
            "preferencias_categorias", "preferencias_persisten",
            "programados", "historial", "restream",
            "transmision", "escena", "grabacion",
            # `microfono` va justo después de `transmision`: los dos
            # necesitan OBS y auditan cuadros del menú OBS.
            "microfono",
            # `encuadre` va con `transmision` y `microfono`: necesita OBS
            # y monta su propia aplicación, como `arranque_frio`.
            "encuadre",
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


def ordenar_pedidos(pedidos):
    """Los pedidos en el orden de `EN_TODOS`; el resto al final como vino."""
    pedidos = list(pedidos)
    en_todos = [n for n in EN_TODOS if n in pedidos]
    resto = [n for n in pedidos if n not in EN_TODOS]
    return en_todos + resto


def escribir_informe(carpeta: Path, res: Resultado,
                     seccion_tiempos: list[str],
                     escenarios: list[str] = ()) -> Path:
    """Escribe el informe de la corrida y devuelve su ruta.

    Los fallos van aparte y en un archivo. Una corrida completa son veinte
    minutos y mas de cien lineas: buscar los fallos volviendo atras en la
    terminal es incomodo con lector de pantalla, y con el buffer lleno
    directamente se pierden.
    """
    informe = carpeta / "qa-informe.txt"
    lineas = [f"Banco de QA de {APP_NAME}",
              "escenarios: " + ", ".join(escenarios),
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
    lineas += [""] + seccion_tiempos
    informe.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return informe


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
    else:
        pedidos = ordenar_pedidos(pedidos)

    # Por defecto, dentro de `qa/salida/`, que está en el `.gitignore`: las
    # grabaciones llevan la salida cruda de la aplicación y no se suben. Fuera de
    # versiones. En la raíz ensuciaba el repositorio con tres archivos sueltos
    # después de cada corrida.
    carpeta = Path(args.carpeta) if args.carpeta else (RAIZ / "qa" / "salida")
    carpeta.mkdir(parents=True, exist_ok=True)
    app = Aplicacion(carpeta)
    res = Resultado()
    duraciones: list[tuple[str, float]] = []
    _TIEMPOS.clear()
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
        correr_escenario("arranque_frio", app, args, res, duraciones)

    # `musica_real` también monta su propia aplicación con datos preparados,
    # igual que `arranque_frio`: la configuración se escribe ANTES de lanzar.
    # `encuadre` monta la suya con la cámara ya elegida, por el mismo motivo.
    if "encuadre" in pedidos:
        pedidos = [n for n in pedidos if n != "encuadre"]
        correr_escenario("encuadre", app, args, res, duraciones)
    if "musica_real" in pedidos:
        pedidos = [n for n in pedidos if n != "musica_real"]
        correr_escenario("musica_real", app, args, res, duraciones)

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
            correr_escenario(nombre, app, args, res, duraciones)
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

    seccion_tiempos = tiempos_banco.lineas_tiempos(_TIEMPOS, duraciones)
    try:
        informe = escribir_informe(carpeta, res, seccion_tiempos, pedidos)
        print(f"  Informe con los fallos en {informe}")
    except Exception as exc:
        print(f"  AVISO: no se pudo escribir el informe: {exc}")
    print()
    print("\n".join(seccion_tiempos))
    if res.fallos:
        return 1
    if res.sin_probar:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

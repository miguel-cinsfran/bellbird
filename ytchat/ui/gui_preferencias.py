"""Diálogo de Preferencias por categorías (accesible).

Reúne en un solo sitio lo que antes solo se editaba a mano en config.ini y
sounds.ini: interfaz (fuente, tema de sonido), lectura, filtros de palabras y
usuarios, y un editor de atajos. Persiste con `config.guardar_opciones`, que
escribe todo de una vez al pulsar Guardar (conservando comentarios y orden del
INI), y actualiza el dict de config en memoria.
La configuración de API/OAuth sigue en su propio diálogo (Herramientas).
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core import config as cfg
from ytchat.core import paths
from ytchat.core.ini_tipado import separar_por_comas
from ytchat.ui import atajos_captura
from ytchat.capture import estado_sesion
from ytchat.obs import obs_cliente
from ytchat.obs import obs_activacion
from ytchat.voice import sound_player as _snd
from ytchat.ui.gui import ContadorAccesible, _T, _tc, anunciar, nombre_accesible
from ytchat.ui.preferencias_comun import (
    ANCHO_NOTA, EleccionTexto, ajustar_ancho_categorias, crear_panel, fila_label)
from ytchat.ui.preferencias_api import PaginaApi
from ytchat.ui.preferencias_atajos import PaginaAtajos
from ytchat.ui.preferencias_general import PaginaGeneral
from ytchat.ui.preferencias_musica import OPCIONES_MUSICA, PaginaMusica
from ytchat.ui.preferencias_lectura import OPCIONES_LECTURA, PaginaLectura
from ytchat.ui.preferencias_ia import PaginaIA
from ytchat.ui.preferencias_programados import PaginaProgramados
from ytchat.ui.preferencias_sonidos import PaginaSonidos
from ytchat.ui.preferencias_voz import PaginaVoz
from ytchat.obs.obs_panel import GestorPanelObs

logger = diagnostico.obtener_logger(__name__)

TAMANO_DIALOGO = (720, 600)


# Opciones que se guardan y se cargan con el mismo molde (leer el control,
# escribir el texto en el ini y copiar el valor a la config en memoria; y al
# revés, volcar la config en el control). Lo que no sigue ese molde va a mano
# en `_on_guardar`. El último campo es el valor de fábrica de
# `config_predeterminada`, ya convertido al tipo de la fila: es el que se
# escribe en el control cuando la config no trae la clave o la trae ilegible.
# `tests/test_preferencias_tabla.py` lo compara con el de fábrica para que no
# se separen.
_OPCIONES_SIMPLES = (
    ("chk_programados", "programados", "activo", "programados_activo", bool, False),
    ("sp_fuente", "ui", "tamanio_fuente_chat", "tamanio_fuente_chat", int, 12),
    ("chk_total_sc", "ui", "mostrar_total_superchats", "mostrar_total_superchats", bool, True),
    ("chk_autoplay", "ui", "autoplay_reproductor", "autoplay_reproductor", bool, True),
    ("chk_solo_audio", "ui", "reproductor_solo_audio", "reproductor_solo_audio", bool, False),
    ("chk_metadatos", "ui", "mostrar_metadatos", "mostrar_metadatos", bool, True),
    ("chk_botones_rep", "ui", "mostrar_botones_reproductor", "mostrar_botones_reproductor", bool, True),
    ("sp_cache_video", "ui", "cache_video_mb", "cache_video_mb", int, 1024),
    ("chk_multivoz", "voz", "multivoz", "multivoz", bool, False),
) + OPCIONES_LECTURA + (
    ("sp_cola_maxima", "cola", "tamanio_maximo", "tamanio_maximo", int, 15),
    ("sp_umbral_nombre", "cola", "umbral_solo_nombre", "umbral_solo_nombre", int, 0),
    ("chk_reconectar", "reconexion", "reconectar", "reconectar", bool, True),
    ("sp_espera_reconexion", "reconexion", "espera_entre_intentos", "espera_entre_intentos", int, 15),
    ("sp_max_intentos", "reconexion", "max_intentos", "max_intentos", int, 20),
    ("chk_buscar_actualizaciones", "actualizaciones", "buscar_al_iniciar", "buscar_actualizaciones_al_iniciar", bool, True),
    ("chk_confirmar_salida", "ui", "confirmar_salida", "confirmar_salida", bool, True),
    ("chk_sonido_inicio", "ui", "sonido_inicio", "sonido_inicio", bool, True),
    ("chk_registro_detallado", "diagnostico", "registro_detallado", "registro_detallado", bool, True),
    ("sp_puerto_overlay", "overlay", "puerto", "overlay_puerto", int, 8730),
    ("chk_avisar_sobrecarga", "transmision", "avisar_sobrecarga", "avisar_sobrecarga", bool, True),
) + OPCIONES_MUSICA


class PreferenciasDialog(wx.Dialog):

    def __init__(self, parent, config: dict):
        # Redimensionable: quien ve poco puede agrandarlo; las páginas se
        # desplazan solas si no caben.
        super().__init__(parent, title="Preferencias", size=TAMANO_DIALOGO,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         name="DialogoPreferencias")
        self._config = config
        self._ruta = paths.config_ini()
        self._cambios = False
        self._fallo_guardado = False
        self._pendientes = []
        self.avisos = []
        self.SetBackgroundColour(_T.bg)
        self._build_ui()
        self._ajustar_minimo()
        self.Centre()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        panel = wx.Panel(self, name="PanelPreferencias")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        # La lista se anuncia sola al recorrerla, a diferencia de las pestañas.
        self.nb = wx.Listbook(panel, name="Categorías de preferencias")
        self.lista_categorias = self.nb.GetListView()
        nombre_accesible(self.lista_categorias, "Categorías")
        _tc(self.lista_categorias, bg=_T.surface)
        self.pagina_general = PaginaGeneral(self)
        self.nb.AddPage(self.pagina_general.construir(self.nb), "General")
        self.chk_buscar_actualizaciones = (
            self.pagina_general.chk_buscar_actualizaciones)
        self.chk_confirmar_salida = self.pagina_general.chk_confirmar_salida
        self.chk_sonido_inicio = self.pagina_general.chk_sonido_inicio
        self.chk_registro_detallado = self.pagina_general.chk_registro_detallado
        self.pagina_voz = PaginaVoz(self, self._config)
        self.nb.AddPage(self.pagina_voz.construir(self.nb), "Voces")
        self.chk_multivoz = self.pagina_voz.chk_multivoz
        self.nb.AddPage(self._pag_lectura(self.nb), "Lectura")
        self.nb.AddPage(self._pag_cola(self.nb), "Cola de lectura")
        self.nb.AddPage(self._pag_interfaz(self.nb), "Interfaz y sonidos")
        self.pagina_sonidos = PaginaSonidos()
        self.nb.AddPage(self.pagina_sonidos.construir(self.nb), "Sonidos")
        self.nb.AddPage(self._pag_reproductor(self.nb), "Reproductor")
        self.pagina_musica = PaginaMusica(self, self._config)
        self.nb.AddPage(self.pagina_musica.construir(self.nb), "Música")
        for fila in OPCIONES_MUSICA:
            setattr(self, fila[0], getattr(self.pagina_musica, fila[0]))
        self.nb.AddPage(self._pag_conexion(self.nb), "Conexión")
        self.nb.AddPage(self._pag_filtros(self.nb), "Filtros")
        self.nb.AddPage(self._pag_estado(self.nb), "Estado (F2)")
        self.pagina_atajos = PaginaAtajos(self, self._config)
        self.nb.AddPage(self.pagina_atajos.construir(self.nb), "Atajos")
        self.pagina_api = PaginaApi(self)
        self.nb.AddPage(self.pagina_api.construir(self.nb), "API y sesión")
        self.pagina_programados = PaginaProgramados()
        self.nb.AddPage(self.pagina_programados.construir(self.nb), "Mensajes automáticos")
        self.chk_programados = self.pagina_programados.chk_programados
        self.nb.AddPage(self._pag_transmision(self.nb), "Transmisión")
        self.pagina_ia = PaginaIA(self, self._ruta)
        self.nb.AddPage(self.pagina_ia.construir(self.nb), "Inteligencia artificial")
        ajustar_ancho_categorias(self.nb, self.lista_categorias)
        # Mínimo explícito: si no, el libro pide el «mejor tamaño» de la página
        # más alta (Atajos, más de 1200 px) y el sizer lo desbordaría en vez
        # de dejar que la página se desplace.
        self.nb.SetMinSize((320, 240))
        vs.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)

        row = wx.BoxSizer(wx.HORIZONTAL)
        btn_guardar = wx.Button(panel, wx.ID_OK, "&Guardar", name="GuardarPreferencias")
        btn_cancelar = wx.Button(panel, wx.ID_CANCEL, "&Cancelar", name="CancelarPreferencias")
        for b in (btn_guardar, btn_cancelar):
            b.SetBackgroundColour(_T.btn)
            b.SetForegroundColour(_T.btn_t)
            row.Add(b, 0, wx.RIGHT, 6)
        vs.Add(row, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vs)
        btn_guardar.Bind(wx.EVT_BUTTON, self._on_guardar)
        self._cargar_opciones_simples()
        self.lista_categorias.SetFocus()

    def _cargar_opciones_simples(self):
        """Vuelca la config en los 33 controles de la tabla. El valor por
        defecto de cada fila es el de fábrica, y se usa tanto si la config no
        trae la clave como si el valor no se puede convertir al tipo."""
        for atributo, _seccion, _clave, en_memoria, tipo, por_defecto in _OPCIONES_SIMPLES:
            control = getattr(self, atributo)
            try:
                valor = tipo(self._config.get(en_memoria, por_defecto))
            except (TypeError, ValueError):
                valor = por_defecto
            control.SetValue(valor)
        # El estado de los controles que depende del valor de una opción simple
        # se decidió en `_build_ui` con el valor viejo del control; se recalcula
        # aquí, ya con el valor cargado.
        self.pagina_voz.actualizar_eventos()

    def _make_panel(self, parent, name):
        return crear_panel(parent, name)

    def _paginas(self):
        return [self.nb.GetPage(i) for i in range(self.nb.GetPageCount())]

    def _ajustar_minimo(self):
        """Ancho mínimo del diálogo: el que deja a la página más ancha entera
        (más la barra de desplazamiento). No hay desplazamiento horizontal,
        así que más angosto se cortarían controles."""
        try:
            self.Layout()
            visible = self.nb.GetPage(0).GetClientSize().width
            necesario = max(p.GetSizer().GetMinSize().width for p in self._paginas())
            barra = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
            ancho = self.GetSize().width - visible + necesario + barra
            alto = 480
            self.SetMinSize((ancho, alto))
            actual = self.GetSize()
            if actual.width < ancho or actual.height < alto:
                self.SetSize((max(actual.width, ancho), max(actual.height, alto)))
        except Exception as exc:
            logger.debug("mínimo del diálogo de preferencias: %s", exc)

    def _pag_interfaz(self, parent):
        p = self._make_panel(parent, "PagInterfaz")
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._fila_label(p, "Tamaño de &fuente del chat (8 a 24):"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.sp_fuente = ContadorAccesible(p, min=8, max=24,
                                     name="Tamaño de fuente del chat")
        _tc(self.sp_fuente)
        vs.Add(self.sp_fuente, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Tema de sonido:"), 0, wx.LEFT | wx.RIGHT, 10)
        temas = cfg.listar_temas_sonido()
        self.cho_tema = wx.Choice(p, choices=temas, name="Tema de sonido")
        _tc(self.cho_tema)
        actual = cfg.tema_sonido_actual()
        self.cho_tema.SetSelection(temas.index(actual) if actual in temas else 0)
        self.cho_tema.Bind(wx.EVT_CHOICE, self._on_muestra_tema)
        vs.Add(self.cho_tema, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_total_sc = wx.CheckBox(p, label="Mostrar el total de &Super Chats en la barra de estado",
                                        name="MostrarTotalSuperChats")
        self.chk_total_sc.SetForegroundColour(_T.text)
        vs.Add(self.chk_total_sc, 0, wx.ALL, 10)

        self.chk_metadatos = wx.CheckBox(p, label="Mostrar la pestaña de &información del vídeo (canal, vistas, descripción)",
                                         name="MostrarMetadatos")
        self.chk_metadatos.SetForegroundColour(_T.text)
        vs.Add(self.chk_metadatos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _on_muestra_tema(self, event):
        """Suena la muestra del tema elegido sin cambiar el tema activo."""
        try:
            tema = self.cho_tema.GetStringSelection()
            if tema:
                _snd.reproducir_archivo(cfg.ruta_muestra_tema(tema))
        except Exception:
            pass
        event.Skip()

    def _pag_cola(self, parent):
        p = self._make_panel(parent, "PagCola")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.rb_estrategia = wx.RadioBox(
            p, label="&Estrategia de la cola", majorDimension=1,
            choices=["Leer todos los mensajes",
                     "Descartar los más viejos si se acumulan"],
            style=wx.RA_SPECIFY_COLS, name="Estrategia de la cola")
        self.rb_estrategia.SetSelection(
            0 if self._config.get("estrategia", "limite") == "todas" else 1)
        vs.Add(self.rb_estrategia, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "Tamaño &máximo de la cola"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_cola_maxima = ContadorAccesible(
            p, min=1, max=500,
            name="Tamaño máximo de la cola")
        vs.Add(self.sp_cola_maxima, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "Leer solo el &nombre a partir de"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_umbral_nombre = ContadorAccesible(
            p, min=0, max=500,
            name="Leer solo el nombre a partir de")
        vs.Add(self.sp_umbral_nombre, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(wx.StaticText(p, label="Con 0, esta opción queda apagada."),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        p.SetSizer(vs)
        return p

    def _pag_conexion(self, parent):
        p = self._make_panel(parent, "PagConexion")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_reconectar = wx.CheckBox(
            p, label="&Reconectar automáticamente si se corta",
            name="Reconectar automáticamente si se corta")
        vs.Add(self.chk_reconectar, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "&Espera máxima entre intentos, en segundos"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_espera_reconexion = ContadorAccesible(
            p, min=1, max=300,
            name="Espera máxima entre intentos, en segundos")
        vs.Add(self.sp_espera_reconexion, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "Número máximo de &intentos"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_max_intentos = ContadorAccesible(
            p, min=0, max=100,
            name="Número máximo de intentos")
        vs.Add(self.sp_max_intentos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _pag_transmision(self, parent):
        p = self._make_panel(parent, "PagTransmision")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_avisar_sobrecarga = wx.CheckBox(
            p, label="A&visar cuando OBS no da abasto",
            name="AvisarSobrecargaObs")
        self.chk_avisar_sobrecarga.SetForegroundColour(_T.text)
        vs.Add(self.chk_avisar_sobrecarga, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "&Puerto del panel de chat"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.sp_puerto_overlay = ContadorAccesible(
            p, min=1024, max=65535,
            name="Puerto del panel de chat")
        vs.Add(self.sp_puerto_overlay, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Micrófono de OBS"),
               0, wx.LEFT | wx.RIGHT, 10)
        guardado = str(self._config.get("obs_microfono", ""))
        opciones = ["Elegir automáticamente"] + ([guardado] if guardado else [])
        self.cho_microfono_obs = wx.Choice(p, choices=opciones, name="Micrófono de OBS")
        self.cho_microfono_obs.SetSelection(1 if guardado else 0)
        vs.Add(self.cho_microfono_obs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_buscar_microfonos = wx.Button(
            p, label="&Buscar los micrófonos en OBS",
            name="Buscar los micrófonos en OBS")
        vs.Add(self.btn_buscar_microfonos, 0, wx.ALL, 10)
        self.btn_buscar_microfonos.Bind(wx.EVT_BUTTON, self._buscar_microfonos)

        self.btn_activar_websocket_obs = wx.Button(
            p, label="&Activar el servidor websocket de OBS",
            name="Activar el servidor websocket de OBS")
        vs.Add(self.btn_activar_websocket_obs, 0, wx.ALL, 10)
        self.btn_activar_websocket_obs.Bind(
            wx.EVT_BUTTON, self._activar_servidor_websocket_obs)

        p.SetSizer(vs)
        return p

    def _buscar_microfonos(self, event):
        # Consultar OBS puede tardar o no responder, por eso nunca corre en la interfaz.
        def consultar():
            gestor = None
            try:
                gestor = GestorPanelObs(ajustes=obs_cliente.leer_ajustes())
                gestor.conectar()
                wx.CallAfter(self._microfonos_encontrados, gestor.fuentes_audio())
            except Exception as exc:
                wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
            finally:
                if gestor is not None:
                    try:
                        gestor.cerrar()
                    except Exception:
                        pass

        diagnostico.crear_hilo(consultar, "MicrofonosPrefs").start()

    def _microfonos_encontrados(self, fuentes):
        if not self:   # el diálogo pudo cerrarse mientras OBS respondía
            return
        elegido = self.cho_microfono_obs.GetStringSelection()
        opciones = ["Elegir automáticamente"]
        # La fuente guardada se conserva aunque OBS no responda o ya no la vea.
        for fuente in (elegido, *fuentes):
            if fuente and fuente not in opciones:
                opciones.append(fuente)
        self.cho_microfono_obs.Set(opciones)
        self.cho_microfono_obs.SetStringSelection(elegido or opciones[0])
        anunciar(f"Se encontraron {len(fuentes)} micrófonos en OBS")

    def _activar_servidor_websocket_obs(self, event):
        def activar():
            try:
                accion, mensaje = obs_activacion.decidir_activacion(
                    obs_activacion.obs_esta_en_ejecucion(),
                    obs_cliente.leer_ajustes())
                if accion == obs_activacion.ACTIVAR:
                    mensaje = obs_activacion.activar_servidor(
                        obs_cliente.RUTA_CONFIG_OBS)
            except Exception as exc:
                logger.warning("No se pudo activar el servidor websocket de OBS: %s", exc)
                mensaje = f"No se pudo activar el servidor websocket de OBS: {exc}"
            wx.CallAfter(anunciar, mensaje)

        diagnostico.crear_hilo(activar, "ActivarWebsocketObs").start()

    def _pag_reproductor(self, parent):
        p = self._make_panel(parent, "PagReproductor")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_autoplay = wx.CheckBox(p, label="&Reproducir el audio automáticamente al conectar",
                                        name="AutoplayReproductor")
        self.chk_autoplay.SetForegroundColour(_T.text)
        vs.Add(self.chk_autoplay, 0, wx.ALL, 10)

        self.chk_solo_audio = wx.CheckBox(
            p, label="Reproducir &solo el audio, sin decodificar la imagen",
            name="SoloAudioReproductor")
        self.chk_solo_audio.SetForegroundColour(_T.text)
        vs.Add(self.chk_solo_audio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_botones_rep = wx.CheckBox(p, label="Mostrar los &botones del reproductor (también con su interruptor y el menú Reproductor)",
                                           name="MostrarBotonesReproductor")
        self.chk_botones_rep.SetForegroundColour(_T.text)
        vs.Add(self.chk_botones_rep, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        etiqueta_cache = wx.StaticText(
            p, label="&Tamaño máximo de la caché de vídeo, en megabytes:")
        self.sp_cache_video = wx.SpinCtrl(
            p, min=0, max=20000,
            name="Tamaño máximo de la caché de vídeo en megabytes")
        vs.Add(etiqueta_cache, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        vs.Add(self.sp_cache_video, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _pag_lectura(self, parent):
        # La página vive en PaginaLectura (composición); el diálogo conserva
        # los atributos públicos de los controles para las pruebas y la tabla.
        self.pagina_lectura = PaginaLectura(
            self._config, self._fila_label, self._make_panel)
        panel = self.pagina_lectura.construir(parent)
        self.rb_formato = self.pagina_lectura.rb_formato
        for fila in OPCIONES_LECTURA:
            setattr(self, fila[0], getattr(self.pagina_lectura, fila[0]))
        return panel

    def _pag_estado(self, parent):
        """Una casilla por componente del anuncio de estado (tecla F2). Sin
        colores en las casillas: en Windows eso rompe su rol accesible."""
        p = self._make_panel(parent, "PagEstado")
        vs = wx.BoxSizer(wx.VERTICAL)

        nota = wx.StaticText(p, name="NotaEstado", label=(
            "Elige qué dice la tecla F2 (estado de sesión). Marca lo que quieras "
            "oír; por defecto, los datos del vídeo y del chat. El orden en que se "
            "dice es fijo."))
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(ANCHO_NOTA)
        vs.Add(nota, 0, wx.ALL, 10)

        activos = self._config.get("estado_toggles") or estado_sesion.ACTIVOS_DEFECTO
        self._chk_estado: dict = {}
        for comp in estado_sesion.COMPONENTES:
            chk = wx.CheckBox(p, label=estado_sesion.ETIQUETAS.get(comp, comp),
                              name=f"EstadoComponente_{comp}")
            chk.SetForegroundColour(_T.text)
            chk.SetValue(comp in activos)
            self._chk_estado[comp] = chk
            vs.Add(chk, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        p.SetSizer(vs)
        return p

    def _pag_filtros(self, parent):
        p = self._make_panel(parent, "PagFiltros")
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._fila_label(p, "&Palabras silenciadas (separadas por comas):"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_palabras = wx.TextCtrl(
            p, value=", ".join(self._config.get("palabras_silenciadas", [])),
            name="Palabras silenciadas")
        _tc(self.txt_palabras)
        vs.Add(self.txt_palabras, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Usuarios silenciados (separados por comas):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.txt_usuarios = wx.TextCtrl(
            p, value=", ".join(self._config.get("usuarios_silenciados", [])),
            name="Usuarios silenciados")
        _tc(self.txt_usuarios)
        vs.Add(self.txt_usuarios, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        nota = wx.StaticText(p, label=(
            "Estos filtros ocultan y no leen los mensajes que contengan esas "
            "palabras o de esos usuarios. Se aplican a partir del próximo mensaje."),
            name="NotaFiltros")
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(ANCHO_NOTA)
        vs.Add(nota, 0, wx.ALL, 10)

        p.SetSizer(vs)
        return p

    def _fila_label(self, p, texto):
        return fila_label(p, texto)

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _set(self, seccion, clave, valor):
        self._pendientes.append((seccion, clave, valor))
        self._cambios = True

    def _on_guardar(self, event):
        c = self._config
        self._pendientes = []
        self._fallo_guardado = False
        registro_detallado_inicial = bool(c.get("registro_detallado", True))
        puerto_anterior = int(c.get("overlay_puerto", 8730))
        # Los atajos ya vienen validados desde la captura (área + conflicto), así
        # que aquí solo se guardan; no hace falta revalidar por escritura.

        # Opciones simples: las de la tabla van por el bucle, el resto a mano.
        for atributo, seccion, clave, en_memoria, tipo, _por_defecto in _OPCIONES_SIMPLES:
            control = getattr(self, atributo)
            if tipo is bool:
                valor = control.GetValue()
                self._set(seccion, clave, "true" if valor else "false")
                c[en_memoria] = valor
            elif tipo is str:
                valor = control.GetValue()
                self._set(seccion, clave, valor)
                c[en_memoria] = valor
            else:
                valor = int(control.GetValue())
                self._set(seccion, clave, str(valor))
                c[en_memoria] = valor

        tema = self.cho_tema.GetStringSelection()
        if tema and tema != cfg.tema_sonido_actual():
            if not cfg.guardar_opcion(paths.sounds_ini(), "sonidos", "tema", tema):
                self._fallo_guardado = True
            try:    _snd.cargar(cfg.cargar_sonidos())
            except Exception as exc: logger.warning("recargar sonidos: %s", exc)
            self._cambios = True

        motor_no_disponible = self.pagina_voz.guardar(self._set, c)

        # Lectura: la página calcula el valor en cambios(); se aplica con el
        # _set de hoy, igual que los demás controles manuales de abajo.
        cambios_lectura = self.pagina_lectura.cambios()
        formato = cambios_lectura[0][2]  # (sección, clave, valor) del formato
        self._set("lectura", "formato_prefijo", formato)
        c["formato_prefijo"] = formato

        # Se guarda la clave, no la etiqueta, porque config.ini solo admite estas claves.
        estrategia = ("todas", "limite")[self.rb_estrategia.GetSelection()]
        self._set("cola", "estrategia", estrategia)
        c["estrategia"] = estrategia
        registro_detallado = c["registro_detallado"]
        puerto_overlay = c["overlay_puerto"]
        microfono_obs = ("" if self.cho_microfono_obs.GetSelection() == 0
                         else self.cho_microfono_obs.GetStringSelection())
        self._set("obs", "microfono", microfono_obs)
        c["obs_microfono"] = microfono_obs

        self.pagina_musica.guardar(self._set, c)

        # Estado (F2): una clave por componente + el set en memoria.
        activos = set()
        for comp, chk in self._chk_estado.items():
            on = chk.GetValue()
            self._set("estado", comp, "true" if on else "false")
            if on:
                activos.add(comp)
        c["estado_toggles"] = activos

        # Filtros
        palabras = self.txt_palabras.GetValue().strip()
        self._set("filtros", "palabras_silenciadas", palabras)
        c["palabras_silenciadas"] = separar_por_comas(palabras)
        usuarios = self.txt_usuarios.GetValue().strip()
        self._set("filtros", "usuarios_silenciados", usuarios)
        c["usuarios_silenciados"] = separar_por_comas(usuarios)

        self.pagina_atajos.guardar(self._set, c)

        self._pendientes.extend(self.pagina_ia._cambios_ia())
        if not self.pagina_sonidos.guardar():
            self._fallo_guardado = True
        if not cfg.guardar_opciones(self._ruta, self._pendientes):
            self._fallo_guardado = True

        if not self._fallo_guardado:
            _snd.reproducir("copiar")
        else:
            _snd.reproducir("error")

        # Los avisos se juntan acá y los dice la ventana principal una sola vez,
        # ya con el foco de vuelta en ella: anunciarlos antes de cerrar hacía que
        # el cambio de foco los cortara entre sí.
        self.avisos = []
        if not self._fallo_guardado:
            self.avisos.append("Preferencias guardadas.")
        else:
            self.avisos.append("Las preferencias se aplicaron, pero no se pudieron "
                               "guardar en el disco. Se perderán al cerrar la "
                               "aplicación.")
        if motor_no_disponible:
            self.avisos.append("El motor elegido no está disponible, se conserva el anterior.")
        if registro_detallado != registro_detallado_inicial:
            self.avisos.append("El cambio del registro detallado se aplica al reiniciar "
                               "la aplicación.")
        # El servidor del panel ya escucha en el puerto viejo; no se reinicia
        # solo, así que se avisa dónde se aplica.
        if puerto_overlay != puerto_anterior and c.get("overlay_activo", False):
            self.avisos.append("El puerto nuevo del panel de chat se aplica al apagarlo y "
                               "volver a encenderlo desde el panel de transmisión.")
        self.EndModal(wx.ID_OK)

    def hubo_cambios(self) -> bool:
        return self._cambios


_ETIQUETAS_ATAJO = atajos_captura.ETIQUETAS
_mostrar_atajo = atajos_captura.mostrar_atajo
etiqueta_de_accion = atajos_captura.etiqueta_de_accion


def abrir_preferencias(parent, config: dict, pagina=None, avisos=None) -> bool:
    """Devuelve True si se guardaron cambios (para aplicarlos en caliente).

    Si `pagina` coincide con el texto de una pestaña (p. ej. "API y sesión"),
    esa queda seleccionada al abrir. Sin `pagina`, igual que siempre.
    Si se pasa una lista en `avisos`, al cerrar con Guardar se le agregan los
    avisos que armó el diálogo, para que la ventana principal los diga cuando
    recupera el foco.
    """
    dlg = PreferenciasDialog(parent, config)
    try:
        if pagina:
            try:
                for i in range(dlg.nb.GetPageCount()):
                    if dlg.nb.GetPageText(i) == pagina:
                        dlg.nb.SetSelection(i)
                        break
            except Exception as exc:
                logger.debug("abrir_preferencias: no se pudo elegir página: %s", exc)
        res = dlg.ShowModal()
        if res == wx.ID_OK and avisos is not None:
            avisos.extend(dlg.avisos)
        return res == wx.ID_OK and dlg.hubo_cambios()
    finally:
        dlg.Destroy()


def ofrecer_iniciar_sesion(parent, config) -> bool:
    """Ofrece abrir Preferencias en la pestaña de sesión tras caducar el token.

    Devuelve lo que devuelva `abrir_preferencias` si el usuario acepta, o
    False si no quiere.
    """
    if wx.MessageBox("Tu sesión de YouTube caducó. ¿Abrir Preferencias para "
                     "volver a iniciar sesión?",
                     "Sesión caducada", wx.YES_NO | wx.ICON_QUESTION,
                     parent) != wx.YES:
        return False
    return abrir_preferencias(parent, config, pagina="API y sesión")

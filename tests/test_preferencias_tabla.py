"""Pruebas de la tabla de opciones simples de Preferencias.

La lista de 38 va literal en este módulo, no se lee de la tabla nueva:
así protege la tabla en vez de repetirla.
"""

import unittest
from unittest import mock

from ytchat.ui import gui
from ytchat.ui import gui_preferencias
from ytchat.voice import motores
from ytchat.core import config_predeterminada as pred
from ytchat.core import musica_decir
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir
from pathlib import Path


# (atributo del control, sección, clave ini, clave en memoria, tipo).
OPCIONES_ESPERADAS = [
    ("chk_programados", "programados", "activo", "programados_activo", bool),
    ("sp_fuente", "ui", "tamanio_fuente_chat", "tamanio_fuente_chat", int),
    ("chk_total_sc", "ui", "mostrar_total_superchats", "mostrar_total_superchats", bool),
    ("chk_autoplay", "ui", "autoplay_reproductor", "autoplay_reproductor", bool),
    ("chk_solo_audio", "ui", "reproductor_solo_audio", "reproductor_solo_audio", bool),
    ("chk_metadatos", "ui", "mostrar_metadatos", "mostrar_metadatos", bool),
    ("chk_botones_rep", "ui", "mostrar_botones_reproductor", "mostrar_botones_reproductor", bool),
    ("sp_cache_video", "ui", "cache_video_mb", "cache_video_mb", int),
    ("chk_multivoz", "voz", "multivoz", "multivoz", bool),
    ("chk_emojis", "texto", "limpiar_emojis", "limpiar_emojis", bool),
    ("chk_urls", "texto", "eliminar_urls", "eliminar_urls", bool),
    ("chk_entradas", "tiktok", "anunciar_entradas", "tiktok_anunciar_entradas", bool),
    ("chk_me_gusta", "tiktok", "leer_me_gusta", "tiktok_leer_me_gusta", bool),
    ("sp_long", "texto", "max_longitud_mensaje", "max_longitud_mensaje", int),
    ("cho_lectura_recientes", "lectura", "recientes", "lectura_recientes", str),
    ("chk_lectura_atajos_globales", "lectura", "atajos_globales", "lectura_atajos_globales", bool),
    ("sp_cola_maxima", "cola", "tamanio_maximo", "tamanio_maximo", int),
    ("sp_umbral_nombre", "cola", "umbral_solo_nombre", "umbral_solo_nombre", int),
    ("chk_reconectar", "reconexion", "reconectar", "reconectar", bool),
    ("sp_espera_reconexion", "reconexion", "espera_entre_intentos", "espera_entre_intentos", int),
    ("sp_max_intentos", "reconexion", "max_intentos", "max_intentos", int),
    ("chk_buscar_actualizaciones", "actualizaciones", "buscar_al_iniciar", "buscar_actualizaciones_al_iniciar", bool),
    ("chk_confirmar_salida", "ui", "confirmar_salida", "confirmar_salida", bool),
    ("chk_sonido_inicio", "ui", "sonido_inicio", "sonido_inicio", bool),
    ("chk_registro_detallado", "diagnostico", "registro_detallado", "registro_detallado", bool),
    ("sp_puerto_overlay", "overlay", "puerto", "overlay_puerto", int),
    ("chk_avisar_sobrecarga", "transmision", "avisar_sobrecarga", "avisar_sobrecarga", bool),
    ("chk_musica_aleatorio", "musica", "aleatorio", "musica_aleatorio", bool),
    ("chk_musica_repetir", "musica", "repetir", "musica_repetir", str),
    ("chk_musica_retomar", "musica", "retomar", "musica_retomar", bool),
    ("chk_musica_sonido_tema", "musica", "sonido_tema", "musica_sonido_tema", bool),
    ("cho_musica_decir", "musica", "decir", "musica_decir", str),
    ("chk_musica_decir_pausa", "musica", "decir_pausa", "musica_decir_pausa", bool),
    ("sp_musica_volumen", "musica", "volumen", "musica_volumen", int),
    ("chk_musica_normalizar", "musica", "normalizar", "musica_normalizar", bool),
    ("chk_musica_preguntar_igualar", "musica", "preguntar_igualar", "musica_preguntar_igualar", bool),
    ("chk_musica_atajos_globales", "musica", "atajos_globales", "musica_atajos_globales", bool),
]

VALORES_SPIN = {
    "sp_fuente": 18,
    "sp_cache_video": 1500,
    "sp_long": 250,
    "sp_cola_maxima": 42,
    "sp_umbral_nombre": 7,
    "sp_espera_reconexion": 12,
    "sp_max_intentos": 3,
    "sp_puerto_overlay": 9000,
    "sp_musica_volumen": 80,
}


class TestTablaOpcionesSimples(unittest.TestCase):

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.ruta = Path.cwd()
        self.parche_ruta = redirigir_rutas(self.ruta)
        self.parche_ruta.__enter__()
        self.addCleanup(self.parche_ruta.__exit__, None, None, None)

    def _dialogo(self, config=None):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, config or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _config_distinto(self):
        """Un valor por fila que no es su por defecto: lo contrario en las
        casillas y uno más en los contadores (todos dentro de su rango). En
        las listas, un valor válido distinto del de fábrica."""
        config = {}
        for _at, _sec, _clave, en_memoria, tipo, por_defecto in gui_preferencias._OPCIONES_SIMPLES:
            if tipo is bool:
                config[en_memoria] = not por_defecto
            elif tipo is str:
                config[en_memoria] = {"musica_decir": "artista",
                                      "lectura_recientes": "voz"}.get(
                                          en_memoria, "tema")
            else:
                config[en_memoria] = por_defecto + 1
        return config

    def test_tabla_tiene_38_filas_sin_repetir_y_cada_atributo_existe(self):
        tabla = gui_preferencias._OPCIONES_SIMPLES
        self.assertEqual(len(tabla), 38)
        atributos = [fila[0] for fila in tabla]
        self.assertEqual(len(set(atributos)), 38)
        dialogo = self._dialogo()
        for atributo in atributos:
            with self.subTest(atributo=atributo):
                self.assertIsNotNone(getattr(dialogo, atributo))

    def test_cada_control_muestra_el_valor_del_config(self):
        config = self._config_distinto()
        dialogo = self._dialogo(config)
        for _at, _sec, _clave, en_memoria, tipo, _por_defecto in gui_preferencias._OPCIONES_SIMPLES:
            with self.subTest(en_memoria=en_memoria):
                self.assertIs(type(config[en_memoria]), tipo)
                self.assertEqual(getattr(dialogo, _at).GetValue(), config[en_memoria])

    def test_config_vacio_muestra_el_por_defecto(self):
        dialogo = self._dialogo()
        for atributo, _sec, _clave, _en_memoria, tipo, por_defecto in gui_preferencias._OPCIONES_SIMPLES:
            with self.subTest(atributo=atributo):
                valor = getattr(dialogo, atributo).GetValue()
                self.assertIs(type(valor), tipo)
                self.assertEqual(valor, por_defecto)

    def test_valor_ilegible_usa_el_por_defecto(self):
        config = {en_memoria: "abc"
                  for _at, _sec, _clave, en_memoria, tipo, _pf
                  in gui_preferencias._OPCIONES_SIMPLES if tipo is int}
        dialogo = self._dialogo(config)
        for atributo, _sec, _clave, _en_memoria, tipo, por_defecto in gui_preferencias._OPCIONES_SIMPLES:
            if tipo is not int:
                continue
            with self.subTest(atributo=atributo):
                self.assertEqual(getattr(dialogo, atributo).GetValue(), por_defecto)

    def test_multivoz_en_true_habilita_voz_eventos(self):
        dialogo = self._dialogo({"multivoz": True})
        self.assertTrue(dialogo.chk_multivoz.GetValue())
        self.assertTrue(dialogo.pagina_voz.cho_voz_eventos.IsEnabled())

    def test_guardar_escribe_texto_y_memoria_con_tipo_exacto(self):
        dialogo = self._dialogo()
        esperados = {}
        for atributo, seccion, clave, en_memoria, tipo in OPCIONES_ESPERADAS:
            control = getattr(dialogo, atributo)
            if tipo is bool:
                control.SetValue(not control.GetValue())
                valor = control.GetValue()
                esperados[(seccion, clave)] = ("true" if valor else "false", en_memoria, valor)
            elif tipo is str:
                control.SetValue({"musica_decir": "artista",
                                  "lectura_recientes": "voz"}.get(
                                      en_memoria, "tema"))
                valor = control.GetValue()
                esperados[(seccion, clave)] = (valor, en_memoria, valor)
            else:
                control.SetValue(VALORES_SPIN[atributo])
                valor = VALORES_SPIN[atributo]
                esperados[(seccion, clave)] = (str(valor), en_memoria, valor)
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones",
                               return_value=True) as guardar, \
                mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        self.assertEqual(guardar.call_count, 1)
        llamada = guardar.call_args.args[1]
        secciones = {seccion for seccion, _clave, _valor in llamada}
        self.assertTrue({"ia", "programados"}.issubset(secciones))
        anunciar.assert_not_called()
        escritos = {(seccion, clave): valor
                    for seccion, clave, valor in llamada}
        for (seccion, clave), (texto, en_memoria, valor) in esperados.items():
            with self.subTest(seccion=seccion, clave=clave):
                self.assertEqual(escritos.get((seccion, clave)), texto)
                self.assertIs(type(dialogo._config[en_memoria]), type(valor))
                self.assertEqual(dialogo._config[en_memoria], valor)

    def test_repetir_es_lista_desplegable_con_tres_opciones(self):
        dialogo = self._dialogo({"musica_repetir": "tema"})
        control = dialogo.chk_musica_repetir
        self.assertIsInstance(control, gui.wx.Choice)
        self.assertEqual(
            [control.GetString(i) for i in range(control.GetCount())],
            ["No", "Toda la cola", "Esta canción"])
        self.assertEqual(control.GetValue(), "tema")
        control.SetValue("todo")
        self.assertEqual(control.GetStringSelection(), "Toda la cola")

    def test_cada_atributo_existe_y_cada_clave_esta_en_fabrica(self):
        dialogo = self._dialogo()
        marca = object()
        for atributo, seccion, clave, _en_memoria, _tipo in OPCIONES_ESPERADAS:
            with self.subTest(atributo=atributo, clave=clave):
                self.assertTrue(hasattr(dialogo, atributo))
                self.assertIsNotNone(getattr(dialogo, atributo))
                self.assertIsNot(pred.obtener(seccion, clave, marca), marca)


class TestMuestraTema(unittest.TestCase):
    """Cableado del EVT_CHOICE de «Tema de sonido». Abre ventanas: la corre
    el advisor, no se corre acá."""

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.ruta = Path.cwd()
        self.parche_ruta = redirigir_rutas(self.ruta)
        self.parche_ruta.__enter__()
        self.addCleanup(self.parche_ruta.__exit__, None, None, None)

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_cambiar_tema_suena_muestra_sin_guardar(self):
        from ytchat.core import config as cfg
        dialogo = gui_preferencias.PreferenciasDialog.__new__(
            gui_preferencias.PreferenciasDialog)
        dialogo.cho_tema = mock.Mock()
        dialogo.cho_tema.GetStringSelection.return_value = "suave"
        evento = mock.Mock()
        esperada = cfg.ruta_muestra_tema("suave")
        with mock.patch.object(gui_preferencias._snd, "reproducir_archivo") as sonar, \
                mock.patch.object(gui_preferencias.cfg, "guardar_opcion") as guardar, \
                mock.patch.object(gui_preferencias.cfg, "cargar_sonidos") as recarga:
            dialogo._on_muestra_tema(evento)
        sonar.assert_called_once_with(esperada)
        guardar.assert_not_called()
        recarga.assert_not_called()
        evento.Skip.assert_called_once_with()

    def test_elegir_tema_en_control_suena_muestra(self):
        from ytchat.core import config as cfg
        dialogo = self._dialogo()
        actual = dialogo.cho_tema.GetSelection()
        total = dialogo.cho_tema.GetCount()
        self.assertGreaterEqual(total, 2)
        indice = (actual + 1) % total
        tema_elegido = dialogo.cho_tema.GetString(indice)
        dialogo.cho_tema.SetSelection(indice)
        evento = gui.wx.CommandEvent(gui.wx.wxEVT_CHOICE, dialogo.cho_tema.GetId())
        evento.SetEventObject(dialogo.cho_tema)
        evento.SetInt(indice)
        esperada = cfg.ruta_muestra_tema(tema_elegido)
        with mock.patch.object(gui_preferencias._snd, "reproducir_archivo") as sonar:
            dialogo.cho_tema.GetEventHandler().ProcessEvent(evento)
        sonar.assert_called_once_with(esperada)


class TestPorDefectoContraFabrica(unittest.TestCase):
    """Sin ventanas: no crea wx.App ni diálogo. Compara el `por_defecto` de cada
    fila con el valor de fábrica de `config_predeterminada`, convertido al tipo
    de la fila, para que no se vuelvan a separar."""

    @staticmethod
    def _convertir(tipo, texto, clave=""):
        # «false» es False: no usar bool() sobre el texto, que daría True.
        if tipo is bool:
            return str(texto).strip().lower() in ("true", "yes", "1", "on")
        if tipo is str:
            if clave == "decir":
                return musica_decir.normalizar(texto)
            if clave == "recientes":
                return (texto if texto in ("lector", "voz") else "lector")
            return gui_preferencias.cfg.normalizar_repetir(texto)
        return tipo(texto)

    def test_por_defecto_coincide_con_el_de_fabrica(self):
        marca = object()
        bool_en_falso = False
        for atributo, seccion, clave, _en_memoria, tipo, por_defecto \
                in gui_preferencias._OPCIONES_SIMPLES:
            with self.subTest(atributo=atributo, seccion=seccion, clave=clave):
                texto = pred.obtener(seccion, clave, marca)
                self.assertIsNot(texto, marca,
                                 f"sin valor de fábrica para {seccion}/{clave}")
                self.assertEqual(por_defecto, self._convertir(tipo, texto, clave))
            if tipo is bool and por_defecto is False:
                bool_en_falso = True
        # Cubre al menos una casilla cuyo valor de fábrica es «false».
        self.assertTrue(bool_en_falso)


if __name__ == "__main__":
    unittest.main()

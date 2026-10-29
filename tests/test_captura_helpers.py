"""Tests de helpers de captura de main: errores, cola y filtros."""

import queue
import sys
import threading
import types
import unittest
from unittest import mock

from ytchat.capture import alias
import main
from main import (
    _mensaje_error_amigable, _es_error_permanente,
    encolar, permitido, debe_leer_tts, procesar_entrante, Stats,
)


class TestErrores(unittest.TestCase):

    def test_id_invalido(self):
        self.assertIn("no es válido", _mensaje_error_amigable("Invalid video id"))

    def test_privado(self):
        self.assertIn("privado", _mensaje_error_amigable("This live is private"))

    def test_miembros(self):
        self.assertIn("miembros", _mensaje_error_amigable("members only chat"))

    def test_generico(self):
        self.assertIn("No se pudo conectar", _mensaje_error_amigable("kaboom"))

    def test_es_permanente(self):
        self.assertTrue(_es_error_permanente("Invalid video id"))
        self.assertTrue(_es_error_permanente("members only"))

    def test_no_es_permanente(self):
        self.assertFalse(_es_error_permanente("timeout temporal de red"))

    def test_sin_canal_se_traduce(self):
        crudo = ("Cannot find channel id for video id:5Hs2r-yrEeo. "
                 "This video id seems to be invalid.")
        self.assertIn("todavía no muestra este vídeo",
                      _mensaje_error_amigable(crudo))

    def test_sin_canal_no_es_permanente(self):
        crudo = ("Cannot find channel id for video id:5Hs2r-yrEeo. "
                 "This video id seems to be invalid.")
        self.assertFalse(_es_error_permanente(crudo))


class TestReconexionRegistro(unittest.TestCase):

    def _config(self):
        return {"reconectar": True, "max_intentos": 0,
                "espera_entre_intentos": 0}

    def _correr(self, errores, parada):
        estados = []
        fallos = list(errores)

        def captura(video_id, cola, cfg, ps, stats, on_message,
                    on_estado, sesion_activa, filtro=None):
            err = fallos.pop(0) if fallos else None
            if not fallos:
                parada.set()
            return err

        with mock.patch.object(main, "_captura", side_effect=captura), \
                mock.patch.object(main, "_directo_terminado",
                                  return_value=False), \
                mock.patch.object(main._snd, "reproducir"), \
                self.assertLogs(main.logger, level="WARNING") as registro:
            main.captura_con_reconexion(
                "v", queue.Queue(), self._config(), parada, Stats(),
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        return estados, registro.output

    def test_fallo_con_error_deja_el_texto_en_warning(self):
        _estados, salida = self._correr(
            [RuntimeError("boom"), RuntimeError("boom")],
            threading.Event())
        self.assertTrue(
            any("Reconexión del chat" in linea and "boom" in linea
                for linea in salida))

    def test_cierre_sin_error_deja_el_motivo_en_warning(self):
        _estados, salida = self._correr([None, None], threading.Event())
        self.assertTrue(
            any("Reconexión del chat" in linea
                and "la conexión se cerró sin error" in linea
                for linea in salida))

    def test_el_aviso_de_reconexion_nombra_el_video(self):
        _estados, salida = self._correr(
            [RuntimeError("boom"), RuntimeError("boom")],
            threading.Event())
        self.assertTrue(
            any("Reconexión del chat video=v," in linea for linea in salida))


class TestDirectoTerminado(unittest.TestCase):

    def _tipo(self, tipo, **kwargs):
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("", tipo, {})):
            return main._directo_terminado("v")

    def test_vod_es_terminado(self):
        self.assertTrue(self._tipo(main.deteccion.VOD))

    def test_live_upcoming_y_desconocido_no_lo_son(self):
        for tipo in (main.deteccion.LIVE, main.deteccion.UPCOMING,
                     main.deteccion.DESCONOCIDO):
            with self.subTest(tipo=tipo):
                self.assertFalse(self._tipo(tipo))

    def test_fallo_de_la_consulta_no_lo_da_por_terminado(self):
        with mock.patch.object(main, "obtener_info_video",
                               side_effect=RuntimeError("sin red")):
            self.assertFalse(main._directo_terminado("v"))

    def test_directo_terminado_real(self):
        # Sin dobles en la frontera: yt-dlp de verdad. o8itjwRYFvs es un
        # directo no listado que ya terminó, medido el 17/10/2026.
        _titulo, tipo, metadatos = main.obtener_info_video("o8itjwRYFvs")
        if tipo == main.deteccion.DESCONOCIDO and metadatos.get("fallo"):
            self.skipTest("sin red: " + metadatos["fallo"])
        if tipo == main.deteccion.DESCONOCIDO:
            self.skipTest("la consulta real no dio un tipo")
        self.assertTrue(main._directo_terminado("o8itjwRYFvs"))


class TestReconexionDirectoTerminado(unittest.TestCase):

    def _config(self, max_intentos=0):
        return {"reconectar": True, "max_intentos": max_intentos,
                "espera_entre_intentos": 0}

    def _correr(self, captura, terminado, parada, max_intentos=0):
        estados = []
        with mock.patch.object(main, "_captura", side_effect=captura), \
                mock.patch.object(main, "_directo_terminado",
                                  return_value=terminado), \
                mock.patch.object(main._snd, "reproducir") as sonido, \
                mock.patch.object(main.logger, "warning"):
            main.captura_con_reconexion(
                "vid123", queue.Queue(), self._config(max_intentos), parada,
                Stats(),
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        return estados, sonido

    def test_directo_terminado_avisa_corta_y_suena_una_vez(self):
        llamadas = [0]

        def captura(video_id, cola, cfg, parada, stats, on_message,
                    on_estado, sesion_activa, filtro=None):
            llamadas[0] += 1
            on_estado("conectado", "ok")
            if llamadas[0] >= 3:      # tope para no colgarse si el arreglo cae
                parada.set()
            return RuntimeError("Chat data stream is empty.")

        parada = threading.Event()
        estados, sonido = self._correr(captura, True, parada)
        self.assertEqual(llamadas[0], 1)
        self.assertIn(
            ("error_permanente", "El directo terminó. Chat desconectado."),
            estados)
        self.assertFalse(any(tipo == "reintentando" for tipo, _ in estados))
        sonido.assert_called_once_with("fin_directo")
        self.assertTrue(parada.is_set())

    def test_cortes_sin_lectura_agotan_los_intentos(self):
        llamadas = [0]

        def captura(video_id, cola, cfg, parada, stats, on_message,
                    on_estado, sesion_activa, filtro=None):
            llamadas[0] += 1
            # «conectado» ya no cuenta como lectura: sin «leido», el contador
            # no se reinicia y el límite se cumple.
            on_estado("conectado", "ok")
            if llamadas[0] >= 6:      # tope para no colgarse si el arreglo cae
                parada.set()
            return RuntimeError("corte")

        parada = threading.Event()
        estados, _sonido = self._correr(captura, False, parada, max_intentos=3)
        self.assertEqual(llamadas[0], 3)
        self.assertIn(("error", "Se agotaron los 3 intentos de reconexión."),
                      estados)

    def test_cortes_con_lectura_reinician_los_intentos(self):
        llamadas = [0]

        def captura(video_id, cola, cfg, parada, stats, on_message,
                    on_estado, sesion_activa, filtro=None):
            llamadas[0] += 1
            on_estado("leido", "ok")
            if llamadas[0] >= 5:
                parada.set()
            return RuntimeError("microcorte")

        parada = threading.Event()
        estados, _sonido = self._correr(captura, False, parada, max_intentos=3)
        self.assertEqual(llamadas[0], 5)
        self.assertFalse(any(tipo in ("error", "error_permanente")
                             for tipo, _ in estados))

    def test_leido_nunca_llega_a_on_estado(self):
        def captura(video_id, cola, cfg, parada, stats, on_message,
                    on_estado, sesion_activa, filtro=None):
            on_estado("leido", "interno")
            on_estado("conectado", "ok")
            parada.set()
            return None

        parada = threading.Event()
        estados, _sonido = self._correr(captura, False, parada)
        tipos = [tipo for tipo, _ in estados]
        self.assertNotIn("leido", tipos)
        self.assertIn("conectado", tipos)


class _ChatFalso:
    def __init__(self, items=None, error=None, fallos=1):
        self._items = list(items or [])
        self._error = error
        self._fallos = fallos if error is not None else 0
        self._vivo = True

    def is_alive(self):
        return self._vivo

    def get(self):
        if self._error is not None and self._fallos > 0:
            self._fallos -= 1
            self._vivo = self._fallos > 0
            raise self._error
        self._vivo = False
        chat = self

        class _Lote:
            def sync_items(self):
                return chat._items
        return _Lote()

    def raise_for_status(self):
        return None


class TestCapturaEnLoopLee(unittest.TestCase):

    def _correr(self, chat):
        estados = []
        pytchat_falso = types.SimpleNamespace(create=lambda **k: chat)
        with mock.patch.dict(sys.modules, {"pytchat": pytchat_falso}), \
                mock.patch.object(main, "_cliente_pytchat",
                                  return_value=mock.Mock(close=lambda: None)), \
                mock.patch.object(main._snd, "reproducir"), \
                self.assertLogs(main.logger, level="INFO") as registro:
            main._captura_en_loop(
                "dQw4w9WgXcQ", queue.Queue(), {}, threading.Event(), Stats(),
                on_message=None,
                on_estado=lambda tipo, texto: estados.append(tipo),
                sesion_activa=None)
        return estados, registro.output

    def test_emite_leido_una_vez_tras_una_vuelta_sin_error(self):
        estados, salida = self._correr(_ChatFalso())
        self.assertEqual(estados.count("leido"), 1)
        self.assertIn("conectado", estados)
        self.assertTrue(any("Conectado al directo video=dQw4w9WgXcQ." in linea
                            for linea in salida))

    def test_no_emite_leido_si_la_primera_vuelta_lanza(self):
        estados, _salida = self._correr(
            _ChatFalso(error=RuntimeError("Chat data stream is empty.")))
        self.assertNotIn("leido", estados)

    def test_cierre_sin_error_no_emite_desconectado_ni_error(self):
        estados, _salida = self._correr(_ChatFalso())
        self.assertNotIn("desconectado", estados)
        self.assertNotIn("error", estados)

    def test_cinco_errores_emiten_error_conexion_sin_desconectado_ni_error(self):
        estados, _salida = self._correr(
            _ChatFalso(error=RuntimeError("corte"), fallos=5))
        self.assertIn("error_conexion", estados)
        self.assertNotIn("desconectado", estados)
        self.assertNotIn("error", estados)


class TestEncolar(unittest.TestCase):

    def test_estrategia_todas_no_descarta(self):
        cola = queue.Queue()
        stats = Stats()
        cfg = {"estrategia": "todas", "tamanio_maximo": 2}
        for i in range(5):
            encolar(cola, {"texto_tts": str(i)}, cfg, stats)
        self.assertEqual(cola.qsize(), 5)
        self.assertEqual(stats.descartados, 0)

    def test_estrategia_limite_descarta_viejos(self):
        cola = queue.Queue()
        stats = Stats()
        cfg = {"estrategia": "limite", "tamanio_maximo": 2}
        for i in range(5):
            encolar(cola, {"texto_tts": str(i)}, cfg, stats)
        self.assertLessEqual(cola.qsize(), 2)
        self.assertGreater(stats.descartados, 0)


class TestFiltros(unittest.TestCase):

    def _cfg(self, **kw):
        base = {
            "usuarios_silenciados": [],
            "palabras_silenciadas": [],
            "silenciados_ocultar": set(),
            "silenciados_runtime": set(),
            "silenciar_lectura": False,
        }
        base.update(kw)
        return base

    def test_permitido_normal(self):
        self.assertTrue(permitido("Ana", "hola", self._cfg()))

    def test_usuario_silenciado_parcial(self):
        self.assertFalse(
            permitido("SpamBot99", "hola", self._cfg(usuarios_silenciados=["spambot"])))

    def test_palabra_silenciada(self):
        self.assertFalse(
            permitido("Ana", "compra ya en MiWeb", self._cfg(palabras_silenciadas=["miweb"])))

    def test_oculto_runtime(self):
        self.assertFalse(
            permitido("Ana", "hola", self._cfg(silenciados_ocultar={"ana"})))

    def test_debe_leer_tts_silencio_global(self):
        self.assertFalse(debe_leer_tts("Ana", self._cfg(silenciar_lectura=True)))

    def test_debe_leer_tts_silenciado_individual(self):
        self.assertFalse(
            debe_leer_tts("Ana", self._cfg(silenciados_runtime={"ana"})))

    def test_debe_leer_tts_normal(self):
        self.assertTrue(debe_leer_tts("Ana", self._cfg()))

    def test_alias_se_lee_y_el_autor_real_llega_a_los_filtros_y_a_la_gui(self):
        autor = "xX_gamer_29384756_Xx"
        alias.usar(alias.poner({}, autor, "Carlos"))
        self.addCleanup(alias.usar, {})
        autores_filtrados = []
        permitido_real = main.permitido

        def permitido_registrado(autor_recibido, mensaje, config):
            autores_filtrados.append(autor_recibido)
            return permitido_real(autor_recibido, mensaje, config)

        cola = queue.Queue()
        on_message = mock.Mock()
        config = self._cfg(
            limpiar_emojis=True, eliminar_urls=False, max_longitud_mensaje=200,
            umbral_solo_nombre=0, formato_prefijo="nombre_mensaje",
            estrategia="todas", tamanio_maximo=10,
        )
        with mock.patch.object(main, "permitido", side_effect=permitido_registrado):
            procesar_entrante(autor, "hola", 0, "", "canal", cola, config,
                              Stats(), on_message=on_message)

        self.assertEqual(cola.get_nowait()["texto_tts"], "Carlos: hola")
        self.assertEqual(autores_filtrados, [autor])
        self.assertEqual(on_message.call_args.args[0], autor)

    def test_alias_se_lee_en_las_ramas_especiales_y_el_umbral(self):
        autor = "xX_gamer_29384756_Xx"
        alias.usar(alias.poner({}, autor, "Carlos"))
        self.addCleanup(alias.usar, {})
        casos = (
            (main.TIPO_SUPERCHAT, "$2", 0, "Super Chat de Carlos: $2. hola"),
            (main.TIPO_MIEMBRO, "", 0, "Nuevo miembro: Carlos"),
            (main.TIPO_ENTRADA, "", 0, "Carlos entró"),
            (main.TIPO_TEXTO, "", 1, "Carlos"),
        )
        for tipo, monto, umbral, esperado in casos:
            with self.subTest(tipo=tipo, umbral=umbral):
                cola = queue.Queue()
                if umbral:
                    cola.put({"texto_tts": "anterior"})
                config = self._cfg(
                    limpiar_emojis=True, eliminar_urls=False,
                    max_longitud_mensaje=200, umbral_solo_nombre=umbral,
                    formato_prefijo="nombre_mensaje", estrategia="todas",
                    tamanio_maximo=10, tiktok_aviso_entradas="leer",
                )
                procesar_entrante(autor, "hola", tipo, monto, "canal", cola,
                                  config, Stats())
                if umbral:
                    cola.get_nowait()
                self.assertEqual(cola.get_nowait()["texto_tts"], esperado)


if __name__ == "__main__":
    unittest.main()

"""Tests de la lógica pura de tts_worker (sanitización, formato, rate)."""

import queue
import sys
import threading
import time
import types
import unittest
from unittest import mock

from ytchat.voice import tts_worker
from ytchat.voice.tts_worker import sanitizar, construir_tts, _wpm_a_rate


class TestArranque(unittest.TestCase):
    """El arranque del motor no debe tumbar la app por una voz desinstalada, y
    un fallo de COM debe llegar con su causa."""

    def _worker(self, voz):
        worker = tts_worker.TTSWorker.__new__(tts_worker.TTSWorker)
        worker.config = {"voz": voz}
        worker._volume = 70
        worker._rate = 0
        worker._voces_col = None
        worker._voz_base_idx = worker._voz_actual_idx = 0
        return worker

    def _sapi(self, descripciones):
        items = [mock.Mock(**{"GetDescription.return_value": d}) for d in descripciones]
        voces = mock.Mock(Count=len(items))
        voces.Item.side_effect = lambda i: items[i]
        tts = mock.Mock()
        tts.GetVoices.return_value = voces
        client = types.SimpleNamespace(Dispatch=mock.Mock(return_value=tts))
        return types.SimpleNamespace(client=client), client, tts, items

    def test_voz_desinstalada_cae_a_la_primera_sin_abortar(self):
        modulo, client, tts, items = self._sapi(["Microsoft Helena", "Microsoft Pablo"])
        worker = self._worker("Lucía")
        with mock.patch.dict(sys.modules, {"win32com": modulo, "win32com.client": client}), \
                mock.patch.object(tts_worker.logger, "warning") as avisar:
            voz = worker._create_voice()
        self.assertIs(voz, tts)
        self.assertIs(tts.Voice, items[0])
        self.assertEqual(worker._voz_base_idx, 0)
        self.assertIn("no encontrada", avisar.call_args.args[0])

    def test_voz_por_nombre_sigue_resolviendose(self):
        modulo, client, tts, items = self._sapi(["Microsoft Helena", "Microsoft Pablo"])
        worker = self._worker("pablo")
        with mock.patch.dict(sys.modules, {"win32com": modulo, "win32com.client": client}):
            worker._create_voice()
        self.assertIs(tts.Voice, items[1])
        self.assertEqual(worker._voz_base_idx, 1)

    def test_fallo_de_com_llega_a_error_con_su_causa(self):
        worker = tts_worker.TTSWorker.__new__(tts_worker.TTSWorker)
        worker._ready = threading.Event()
        worker._error = None
        worker._init_com = mock.Mock(side_effect=RuntimeError("pywin32 no instalado"))
        worker._create_voice = mock.Mock()
        worker.run()
        self.assertTrue(worker._ready.is_set())
        self.assertIn("pywin32", str(worker._error))
        worker._create_voice.assert_not_called()
        self.assertFalse(worker.esperar_inicio(timeout=0))


class TestPausaAMitadDeFrase(unittest.TestCase):

    def _worker(self):
        worker = tts_worker.TTSWorker.__new__(tts_worker.TTSWorker)
        worker._voz = mock.Mock()
        worker._purge_pending = threading.Event()
        worker._active = threading.Event()   # empieza en pausa
        worker._voz_base_idx = 0
        worker._aplicar_voz_idx = mock.Mock()
        return worker

    def test_en_pausa_se_pausa_la_voz_y_se_atienden_comandos(self):
        worker = self._worker()
        worker._voz.WaitUntilDone.side_effect = [False, True]
        llamadas = []

        def procesar():
            llamadas.append(1)
            if len(llamadas) >= 2:      # un comando llegó durante la pausa
                worker._active.set()
        worker._procesar_comandos = mock.Mock(side_effect=procesar)
        worker._hablar("mensaje largo")
        worker._voz.Pause.assert_called_once_with()
        worker._voz.Resume.assert_called_once_with()
        self.assertGreaterEqual(len(llamadas), 2)

    def test_purga_durante_la_pausa_corta_la_frase_y_sigue_en_pausa(self):
        worker = self._worker()
        worker._voz.WaitUntilDone.side_effect = [False, False, True]
        llamadas = []

        def procesar():
            llamadas.append(1)
            if len(llamadas) == 2:      # Alt+D con la voz en pausa
                worker._purge_pending.set()
        worker._procesar_comandos = mock.Mock(side_effect=procesar)
        worker._hablar("mensaje largo")
        worker._voz.Resume.assert_called_once_with()
        purgas = [c for c in worker._voz.Speak.call_args_list
                  if c.args == ("", tts_worker.SVSF_ASYNC | tts_worker.SVSF_PURGE_BEFORE)]
        self.assertEqual(len(purgas), 1)
        self.assertFalse(worker._active.is_set())


class TestPurgaArmada(unittest.TestCase):
    """Una purga pedida con la voz callada no debe cortar el mensaje siguiente."""

    def _worker(self):
        worker = tts_worker.TTSWorker.__new__(tts_worker.TTSWorker)
        worker._voz = mock.Mock()
        worker._voz.WaitUntilDone.return_value = True
        worker._purge_pending = threading.Event()
        worker._active = threading.Event()
        worker._active.set()
        worker._voz_base_idx = 0
        worker._aplicar_voz_idx = mock.Mock()
        worker._procesar_comandos = mock.Mock()
        return worker

    def test_purga_pendiente_se_descarta_antes_de_hablar(self):
        worker = self._worker()
        worker._purge_pending.set()   # detener_actual() con la voz callada
        worker._hablar("primer mensaje tras reconectar")
        self.assertFalse(worker._purge_pending.is_set())
        worker._voz.Speak.assert_called_once_with(
            "primer mensaje tras reconectar", tts_worker._SPEAK_FLAGS)

    def test_purga_durante_la_lectura_sigue_cortando(self):
        worker = self._worker()
        worker._voz.WaitUntilDone.side_effect = [False, False, True]

        def pedir_purga():
            worker._purge_pending.set()
        worker._procesar_comandos = mock.Mock(side_effect=pedir_purga)
        worker._hablar("mensaje largo")
        llamadas = worker._voz.Speak.call_args_list
        self.assertEqual(llamadas[0].args[0], "mensaje largo")
        self.assertEqual(llamadas[1].args, ("", tts_worker.SVSF_ASYNC | tts_worker.SVSF_PURGE_BEFORE))


class TestUltimoAutor(unittest.TestCase):
    """El worker recuerda quién mandó lo que empezó a leer (F3)."""

    def _worker_en_marcha(self, hablados):
        cola = queue.Queue()
        worker = tts_worker.TTSWorker(cola, {})
        worker._init_com = lambda: None
        worker._create_voice = lambda: mock.Mock()
        worker._hablar = lambda texto, voz=None: hablados.append(texto)
        worker.start()
        self.assertTrue(worker.esperar_inicio(timeout=5))
        self.addCleanup(worker.detener)
        return worker, cola

    def _esperar_autor(self, worker, esperado, timeout=5.0):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            if worker.ultimo_autor() == esperado:
                return
            time.sleep(0.02)
        self.assertEqual(worker.ultimo_autor(), esperado)

    def _esperar_hablados(self, hablados, cantidad, timeout=5.0):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            if len(hablados) >= cantidad:
                return
            time.sleep(0.02)
        self.assertGreaterEqual(len(hablados), cantidad)

    def test_empieza_sin_autor(self):
        worker, _cola = self._worker_en_marcha([])
        self.assertEqual(worker.ultimo_autor(), "")

    def test_registra_el_autor_que_empieza_a_leer(self):
        hablados = []
        worker, cola = self._worker_en_marcha(hablados)
        cola.put({"texto_tts": "hola", "autor": "Ana"})
        self._esperar_autor(worker, "Ana")
        self.assertEqual(hablados, ["hola"])

    def test_un_item_sin_autor_no_borra_el_anterior(self):
        hablados = []
        worker, cola = self._worker_en_marcha(hablados)
        cola.put({"texto_tts": "hola", "autor": "Ana"})
        self._esperar_autor(worker, "Ana")
        cola.put({"texto_tts": "aviso interno"})
        self._esperar_hablados(hablados, 2)
        self.assertEqual(worker.ultimo_autor(), "Ana")

    def test_un_item_con_texto_vacio_no_cambia_el_autor(self):
        hablados = []
        worker, cola = self._worker_en_marcha(hablados)
        cola.put({"texto_tts": "hola", "autor": "Ana"})
        self._esperar_autor(worker, "Ana")
        cola.put({"texto_tts": "   ", "autor": "Beto"})
        time.sleep(1.0)   # el bucle lo salta sin hablar (timeout 0,3)
        self.assertEqual(hablados, ["hola"])
        self.assertEqual(worker.ultimo_autor(), "Ana")


class TestSanitizar(unittest.TestCase):

    def test_vacio(self):
        self.assertEqual(sanitizar("", True, True, 200), "")

    def test_colapsa_espacios(self):
        self.assertEqual(sanitizar("hola    mundo", True, True, 200), "hola mundo")

    def test_elimina_urls(self):
        self.assertEqual(
            sanitizar("mira esto http://example.com/x ya", True, True, 200),
            "mira esto ya")

    def test_conserva_urls_si_se_pide(self):
        out = sanitizar("ve a http://example.com", True, False, 200)
        self.assertIn("http://example.com", out)

    def test_elimina_emojis(self):
        self.assertEqual(sanitizar("hola 😀🎉 mundo", True, True, 200), "hola mundo")

    def test_conserva_emojis_si_se_pide(self):
        out = sanitizar("hola 😀 mundo", False, True, 200)
        self.assertIn("😀", out)

    def test_elimina_caracteres_de_control(self):
        self.assertEqual(sanitizar("a\x00b\x07c", True, True, 200), "abc")

    def test_truncado_por_palabra(self):
        texto = "palabra " * 50  # 400 chars aprox
        out = sanitizar(texto.strip(), True, True, 40)
        self.assertTrue(out.endswith("..."))
        self.assertLessEqual(len(out), 43)

    def test_sin_truncado_si_maxlen_cero(self):
        texto = "x" * 500
        self.assertEqual(sanitizar(texto, True, True, 0), texto)


class TestConstruirTTS(unittest.TestCase):

    def _cfg(self, fmt="nombre_mensaje"):
        return {"limpiar_emojis": True, "formato_prefijo": fmt}

    def test_nombre_mensaje(self):
        self.assertEqual(construir_tts("Juan", "hola", self._cfg()), "Juan: hola")

    def test_solo_mensaje(self):
        self.assertEqual(
            construir_tts("Juan", "hola", self._cfg("solo_mensaje")), "hola")

    def test_solo_nombre(self):
        self.assertEqual(
            construir_tts("Juan", "hola", self._cfg("solo_nombre")), "Juan")

    def test_mensaje_nombre(self):
        self.assertEqual(
            construir_tts("Juan", "hola", self._cfg("mensaje_nombre")),
            "hola, de Juan")

    def test_mensaje_nombre_autor_vacio_usa_placeholder(self):
        self.assertEqual(
            construir_tts("", "hola", self._cfg("mensaje_nombre")),
            "hola, de Usuario")

    def test_autor_vacio_usa_placeholder(self):
        self.assertEqual(construir_tts("", "hola", self._cfg()), "Usuario: hola")


class TestWpmARate(unittest.TestCase):

    def test_valor_neutro(self):
        self.assertEqual(_wpm_a_rate(180), 0)

    def test_limite_inferior(self):
        # El rate SAPI5 nunca baja de -10 por mucho que se reduzca el wpm.
        self.assertEqual(_wpm_a_rate(-100), -10)

    def test_limite_superior(self):
        self.assertEqual(_wpm_a_rate(10000), 10)

    def test_rapido(self):
        self.assertEqual(_wpm_a_rate(220), 2)


if __name__ == "__main__":
    unittest.main()

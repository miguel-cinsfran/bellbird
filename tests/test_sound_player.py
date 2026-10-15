"""Pruebas del reproductor de sonidos sin usar el backend real."""

import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from ytchat.voice import sound_player


class PruebasBarridoAlias(unittest.TestCase):
    """El barrido cierra un alias cuando MCI dice que terminó, no a los 5 s:
    un tema de usuario largo se cortaba a mitad."""

    def test_alias_vencido_solo_si_dejo_de_sonar_o_supero_el_tope(self):
        self.assertFalse(sound_player._alias_vencido(6.0, "playing"))
        self.assertTrue(sound_player._alias_vencido(0.2, "stopped"))
        self.assertTrue(sound_player._alias_vencido(0.2, ""))   # MCI no contesta
        self.assertTrue(sound_player._alias_vencido(
            sound_player._TTL_ALIAS_SEG + 1, "playing"))

    def test_barrido_cierra_solo_los_alias_que_terminaron(self):
        modos = {"ytcsnd1": "playing", "ytcsnd2": "stopped"}
        enviados = []

        def mci(cmd, buf, n, cb):
            enviados.append(cmd)
            if cmd.startswith("status "):
                buf.value = modos[cmd.split()[1]]
            return 0
        winmm = mock.Mock()
        winmm.mciSendStringW.side_effect = mci
        activos = {"ytcsnd1": time.monotonic(), "ytcsnd2": time.monotonic()}
        with mock.patch.object(sound_player, "_winmm", winmm), \
                mock.patch.object(sound_player, "_alias_activos", activos):
            sound_player._barrer_alias()
            self.assertEqual(set(sound_player._alias_activos), {"ytcsnd1"})
        self.assertIn("close ytcsnd2", enviados)
        self.assertNotIn("close ytcsnd1", enviados)

    def test_barrido_cierra_por_tope_aunque_mci_diga_que_suena(self):
        def mci(cmd, buf, n, cb):
            if cmd.startswith("status "):
                buf.value = "playing"
            return 0
        winmm = mock.Mock()
        winmm.mciSendStringW.side_effect = mci
        activos = {"ytcsnd1": time.monotonic() - sound_player._TTL_ALIAS_SEG - 1}
        with mock.patch.object(sound_player, "_winmm", winmm), \
                mock.patch.object(sound_player, "_alias_activos", activos):
            sound_player._barrer_alias()
            self.assertEqual(sound_player._alias_activos, {})


class PruebasSoundPlayer(unittest.TestCase):
    def setUp(self):
        parches = (
            mock.patch.object(sound_player, "_eventos", {}),
            mock.patch.object(sound_player, "_volumen", 0.7),
            mock.patch.object(sound_player, "_activo", True),
            mock.patch.object(sound_player, "_silenciado_usuario", False),
            mock.patch.object(sound_player, "_backend_winmm", False),
            mock.patch.object(sound_player, "_init_backend"),
            mock.patch.object(sound_player, "_iniciar_hilo_sonido"),
            mock.patch.object(sound_player, "_hilo_sonido", None),
        )
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)

    def test_cargar_desactivado_silencia(self):
        sound_player.cargar({"activar": False})

        self.assertTrue(sound_player.esta_silenciado())

    def test_cargar_activo_con_eventos_no_silencia(self):
        sound_player.cargar({"activar": True, "eventos": {"mensaje": Path("mensaje.wav")}})

        self.assertFalse(sound_player.esta_silenciado())

    def test_cargar_recorta_el_volumen(self):
        sound_player.cargar({"volumen": 5})
        self.assertEqual(sound_player._volumen, 1.0)

        sound_player.cargar({"volumen": -3})
        self.assertEqual(sound_player._volumen, 0.0)

    def test_cargar_descarta_eventos_vacios(self):
        ruta = Path("mensaje.wav")
        sound_player.cargar({"eventos": {"mensaje": ruta, "vacio": "", "nulo": None}})

        self.assertEqual(sound_player._eventos, {"mensaje": ruta})

    def test_silenciar_todo_impide_llegar_al_backend(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directorio:
            ruta = Path(directorio) / "mensaje.wav"
            ruta.touch()
            sound_player.cargar({"eventos": {"mensaje": ruta}})
            sound_player.silenciar_todo(True)
            with mock.patch.object(sound_player, "_reproducir_winmm") as winmm, \
                    mock.patch.object(sound_player, "_reproducir_fallback") as fallback:
                sound_player.reproducir("mensaje")

        winmm.assert_not_called()
        fallback.assert_not_called()

    def test_reproducir_evento_desconocido_no_llama_al_backend(self):
        with mock.patch.object(sound_player, "_reproducir_winmm") as winmm, \
                mock.patch.object(sound_player, "_reproducir_fallback") as fallback:
            sound_player.reproducir("inexistente")

        winmm.assert_not_called()
        fallback.assert_not_called()

    def test_reproducir_archivo_ausente_no_llama_al_backend(self):
        sound_player.cargar({"eventos": {"mensaje": Path("no-existe.wav")}})
        with mock.patch.object(sound_player, "_reproducir_winmm") as winmm, \
                mock.patch.object(sound_player, "_reproducir_fallback") as fallback:
            sound_player.reproducir("mensaje")

        winmm.assert_not_called()
        fallback.assert_not_called()

    def test_reproducir_archivo_existente_llama_al_backend(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directorio:
            ruta = Path(directorio) / "mensaje.wav"
            ruta.touch()
            sound_player.cargar({"eventos": {"mensaje": ruta}})
            with mock.patch.object(sound_player, "_reproducir_fallback") as fallback:
                sound_player.reproducir("mensaje")

        fallback.assert_called_once_with(ruta)

    def test_cerrar_sin_haber_cargado_no_lanza(self):
        sound_player.cerrar()


class PruebasReproducirArchivo(unittest.TestCase):
    def setUp(self):
        try:
            while True:
                sound_player._cola_sonidos.get_nowait()
        except queue.Empty:
            pass
        parches = (
            mock.patch.object(sound_player, "_volumen", 0.7),
            mock.patch.object(sound_player, "_activo", True),
            mock.patch.object(sound_player, "_silenciado_usuario", False),
            mock.patch.object(sound_player, "_backend_winmm", True),
            mock.patch.object(sound_player, "_iniciar_hilo_sonido"),
        )
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        self.addCleanup(self._drenar)

    def _drenar(self):
        try:
            while True:
                sound_player._cola_sonidos.get_nowait()
        except queue.Empty:
            pass

    def test_encola_la_ruta_sin_tocar_disco(self):
        ruta = Path("no-existe.wav")
        sound_player.reproducir_archivo(ruta)
        self.assertEqual(sound_player._cola_sonidos.qsize(), 1)
        self.assertEqual(sound_player._cola_sonidos.get_nowait(), ruta)

    def test_silenciado_no_encola(self):
        sound_player.silenciar_todo(True)
        with mock.patch.object(sound_player, "_iniciar_hilo_sonido") as iniciar:
            sound_player.reproducir_archivo(Path("mensaje.wav"))
        iniciar.assert_not_called()
        self.assertTrue(sound_player._cola_sonidos.empty())
        sound_player.silenciar_todo(False)

    def test_desactivado_no_encola(self):
        with mock.patch.object(sound_player, "_activo", False), \
                mock.patch.object(sound_player, "_iniciar_hilo_sonido") as iniciar:
            sound_player.reproducir_archivo(Path("mensaje.wav"))
        iniciar.assert_not_called()
        self.assertTrue(sound_player._cola_sonidos.empty())


class PruebasHiloSonido(unittest.TestCase):
    """`reproducir` no ejecuta nada en el hilo que llama: todo MCI
    (abrir, reproducir, barrer, cerrar) vive en el hilo de sonido."""

    def setUp(self):
        sound_player.cerrar()
        self._drenar()
        self.llamadas = []
        llamadas = self.llamadas

        def mci(cmd, buf, n, cb):
            llamadas.append((cmd, threading.current_thread().name))
            if cmd.startswith("status "):
                buf.value = "stopped"
            return 0
        winmm = mock.Mock()
        winmm.mciSendStringW.side_effect = mci
        parches = (
            mock.patch.object(sound_player, "_eventos",
                              {"mensaje": Path("mensaje.wav")}),
            mock.patch.object(sound_player, "_volumen", 0.7),
            mock.patch.object(sound_player, "_activo", True),
            mock.patch.object(sound_player, "_silenciado_usuario", False),
            mock.patch.object(sound_player, "_backend_winmm", True),
            mock.patch.object(sound_player, "_winmm", winmm),
            mock.patch.object(sound_player, "_alias_activos", {}),
        )
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        self.addCleanup(sound_player.cerrar)
        self.addCleanup(self._drenar)

    def _drenar(self):
        try:
            while True:
                sound_player._cola_sonidos.get_nowait()
        except queue.Empty:
            pass

    def _esperar(self, condicion, segundos=2.0):
        limite = time.monotonic() + segundos
        while not condicion():
            if time.monotonic() > limite:
                break
            time.sleep(0.02)
        self.assertTrue(condicion())

    def test_reproducir_vuelve_sin_mci_en_el_hilo_que_llama(self):
        with mock.patch.object(sound_player, "_iniciar_hilo_sonido"):
            sound_player.reproducir("mensaje")

        self.assertEqual(self.llamadas, [])
        self.assertEqual(sound_player._cola_sonidos.qsize(), 1)

    def test_hilo_abre_y_reproduce_lo_encolado(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directorio:
            ruta = Path(directorio) / "mensaje.wav"
            ruta.touch()
            with mock.patch.object(sound_player, "_eventos",
                                   {"mensaje": ruta}):
                sound_player._iniciar_hilo_sonido()
                sound_player.reproducir("mensaje")
                self._esperar(lambda: any(
                    cmd.startswith('open "') for cmd, _ in self.llamadas))

        aperturas = [(cmd, hilo) for cmd, hilo in self.llamadas
                     if cmd.startswith('open "')]
        self.assertTrue(aperturas)
        for _, hilo in aperturas:
            self.assertEqual(hilo, "Sonidos")

    def test_cola_llena_descarta_el_quinto_en_silencio(self):
        with mock.patch.object(sound_player, "_iniciar_hilo_sonido"):
            for _ in range(sound_player._MAX_PENDIENTES + 1):
                sound_player.reproducir("mensaje")

        self.assertEqual(sound_player._cola_sonidos.qsize(),
                         sound_player._MAX_PENDIENTES)
        self.assertEqual(self.llamadas, [])

    def test_archivo_inexistente_no_llega_a_mci(self):
        with mock.patch.object(sound_player, "_iniciar_hilo_sonido"), \
                mock.patch.object(sound_player, "_eventos",
                                   {"mensaje": Path("no-existe.wav")}):
            sound_player.reproducir("mensaje")
            # Se encola sin comprobar nada en el hilo que llama...
            self.assertEqual(sound_player._cola_sonidos.qsize(), 1)
            # ...y el hilo de sonido lo descarta sin tocar MCI.
            sound_player._reproducir_en_hilo(
                sound_player._cola_sonidos.get_nowait())

        self.assertEqual(self.llamadas, [])

    def test_cerrar_cierra_los_alias_y_termina_el_hilo(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directorio:
            ruta = Path(directorio) / "mensaje.wav"
            ruta.touch()
            with mock.patch.object(sound_player, "_eventos",
                                   {"mensaje": ruta}):
                sound_player._iniciar_hilo_sonido()
                hilo = sound_player._hilo_sonido
                sound_player.reproducir("mensaje")
                self._esperar(lambda: any(
                    cmd.startswith('open "') for cmd, _ in self.llamadas))
                sound_player.cerrar()

        self.assertFalse(hilo.is_alive())
        self.assertEqual(sound_player._alias_activos, {})
        self.assertTrue(any(cmd.startswith("close ")
                            for cmd, _ in self.llamadas))

    def test_silenciado_no_encola_nada(self):
        sound_player.silenciar_todo(True)
        with mock.patch.object(sound_player, "_iniciar_hilo_sonido") as iniciar:
            sound_player.reproducir("mensaje")

        iniciar.assert_not_called()
        self.assertTrue(sound_player._cola_sonidos.empty())
        self.assertEqual(self.llamadas, [])


if __name__ == "__main__":
    unittest.main()

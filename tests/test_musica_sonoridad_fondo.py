"""Pruebas de la mezcla de sonoridad, sin ventanas ni motor.

La mezcla se prueba sobre un anfitrión mínimo (sin wx): el hilo corre en
el acto como `_HiloInmediato`, `medir` es falso salvo en la prueba real,
que usa el ffmpeg de verdad sobre un WAV generado.
"""

import math
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from ytchat.music.modelo import Tema
from ytchat.music.sonoridad import CacheSonoridad
from ytchat.ui import musica_sonoridad
from ytchat.ui.musica_sonoridad import SonoridadMusica


class _HiloInmediato:
    def __init__(self, target, args):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


def _crear_hilo_inmediato(target, nombre, *, args=(), daemon=True):
    return _HiloInmediato(target, args)


class _BibliotecaFalsa:
    def __init__(self, temas):
        self._temas = tuple(temas)

    def temas(self):
        return self._temas


class _Anfitrion(SonoridadMusica):
    def __init__(self, config=None, cache=None, biblioteca=None,
                 generacion=3):
        self._config = {"musica_normalizar": True}
        self._config.update(config or {})
        self._cache_sonoridad = cache
        self._progreso_sonoridad = None
        self._cerrado = False
        self._generacion_etiquetas = generacion
        self._biblioteca = biblioteca
        self._adaptador = mock.Mock()


def _tema_local(tmp, nombre="a.mp3", contenido=b"audio"):
    ruta = Path(tmp) / nombre
    ruta.write_bytes(contenido)
    return Tema(str(ruta.resolve()), nombre)


class TestGananciaDe(unittest.TestCase):

    def test_enlace_da_cero(self):
        anfitrion = _Anfitrion()
        self.assertEqual(
            anfitrion._ganancia_de(Tema("https://youtu.be/x", "Enlace")),
            0.0)

    def test_sin_cache_da_cero(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = _Anfitrion()
            self.assertEqual(
                anfitrion._ganancia_de(_tema_local(tmp)), 0.0)

    def test_archivo_medido_da_su_ganancia(self):
        with tempfile.TemporaryDirectory() as tmp:
            tema = _tema_local(tmp)
            cache = CacheSonoridad(Path(tmp) / "sonoridad.json")
            info = os.stat(tema.origen)
            cache.poner(tema.origen, info.st_mtime_ns, info.st_size, 3.5)
            anfitrion = _Anfitrion(cache=cache)
            self.assertEqual(anfitrion._ganancia_de(tema), 3.5)

    def test_archivo_cambiado_da_cero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tema = _tema_local(tmp, contenido=b"audio")
            cache = CacheSonoridad(Path(tmp) / "sonoridad.json")
            info = os.stat(tema.origen)
            cache.poner(tema.origen, info.st_mtime_ns, info.st_size, 3.5)
            Path(tema.origen).write_bytes("audio distinto y más largo".encode("utf-8"))
            anfitrion = _Anfitrion(cache=cache)
            self.assertEqual(anfitrion._ganancia_de(tema), 0.0)

    def test_archivo_que_no_se_puede_leer_da_cero(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheSonoridad(Path(tmp) / "sonoridad.json")
            anfitrion = _Anfitrion(cache=cache)
            faltante = Tema(str(Path(tmp, "falta.mp3").resolve()), "Falta")
            self.assertEqual(anfitrion._ganancia_de(faltante), 0.0)

    def test_ganancia_lee_el_disco_sin_haber_arrancado(self):
        with tempfile.TemporaryDirectory() as tmp:
            tema = _tema_local(tmp)
            ruta_cache = Path(tmp) / "sonoridad.json"
            previa = CacheSonoridad(ruta_cache)
            info = os.stat(tema.origen)
            previa.poner(tema.origen, info.st_mtime_ns, info.st_size, 4.5)
            previa.guardar()
            anfitrion = _Anfitrion()
            self.assertIsNone(anfitrion._cache_sonoridad)
            with mock.patch.object(musica_sonoridad.paths,
                                    "cache_sonoridad_musica",
                                    return_value=ruta_cache):
                self.assertEqual(anfitrion._ganancia_de(tema), 4.5)

    def test_cache_lista_devuelve_el_mismo_objeto(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "s.json"
            anfitrion = _Anfitrion()
            with mock.patch.object(musica_sonoridad.paths,
                                    "cache_sonoridad_musica",
                                    return_value=ruta_cache):
                primera = anfitrion._cache_sonoridad_lista()
                segunda = anfitrion._cache_sonoridad_lista()
            self.assertIs(primera, segunda)
            self.assertIs(anfitrion._cache_sonoridad, primera)


class TestArrancarSonoridad(unittest.TestCase):

    def _anfitrion_con(self, tmp, medidos=(), config=None):
        temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
        ruta_cache = Path(tmp) / "sonoridad.json"
        cache = CacheSonoridad(ruta_cache)
        for tema in medidos:
            info = os.stat(tema.origen)
            cache.poner(tema.origen, info.st_mtime_ns, info.st_size, 2.0)
        return _Anfitrion(config=config, biblioteca=_BibliotecaFalsa(temas))

    def test_con_opcion_apagada_no_arranca(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(
                tmp, config={"musica_normalizar": False})
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            crear.assert_not_called()
            self.assertIsNone(anfitrion._cache_sonoridad)

    def test_sin_ffmpeg_no_arranca(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(tmp)
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg", return_value=None):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            crear.assert_not_called()

    def test_sin_pendientes_no_arranca(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3")]
            cache = CacheSonoridad(Path(tmp) / "s.json")
            info = os.stat(temas[0].origen)
            cache.poner(temas[0].origen, info.st_mtime_ns, info.st_size,
                        2.0)
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas),
                                   cache=cache)
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            crear.assert_not_called()

    def test_mide_solo_lo_pendiente_y_no_guarda_un_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
            medidos = []

            def _medir(_ruta, origen):
                medidos.append(origen)
                if origen == temas[0].origen:
                    return None
                return 1.5

            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    _crear_hilo_inmediato), \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                       side_effect=_medir):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            self.assertEqual(sorted(medidos),
                             sorted(t.origen for t in temas))
            cache = anfitrion._cache_sonoridad
            info0 = os.stat(temas[0].origen)
            info1 = os.stat(temas[1].origen)
            self.assertIsNone(cache.buscar(temas[0].origen,
                                           info0.st_mtime_ns, info0.st_size))
            self.assertEqual(cache.buscar(temas[1].origen,
                                          info1.st_mtime_ns, info1.st_size),
                             1.5)
            self.assertIsNone(anfitrion._progreso_sonoridad)

    def test_sale_al_cambiar_la_generacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3")]
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            anfitrion._generacion_etiquetas = 4
            with mock.patch.object(musica_sonoridad.sonoridad, "medir") \
                    as medir:
                anfitrion._medir_sonoridad_fondo(tuple(temas), 3)
            medir.assert_not_called()
            self.assertIsNone(anfitrion._progreso_sonoridad)

    def test_sale_si_se_apaga_la_opcion_a_mitad(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
            vistos = []

            def _medir(_ruta, origen):
                vistos.append(origen)
                anfitrion._config["musica_normalizar"] = False
                return 1.5

            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas),
                                   cache=CacheSonoridad(
                                       Path(tmp) / "s.json"))
            with mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                    "ruta_ffmpeg",
                                    return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                       side_effect=_medir):
                anfitrion._medir_sonoridad_fondo(tuple(temas), 3)
            self.assertEqual(len(vistos), 1)
            self.assertIsNone(anfitrion._progreso_sonoridad)

    def test_guarda_cada_veinte_y_al_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, f"t{i:02d}.mp3",
                                 contenido=f"audio-{i}".encode())
                     for i in range(25)]
            ruta_cache = Path(tmp) / "s.json"
            cache = CacheSonoridad(ruta_cache)
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas),
                                   cache=cache)
            with mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                    "ruta_ffmpeg",
                                    return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                       return_value=1.0), \
                    mock.patch.object(CacheSonoridad, "guardar",
                                       wraps=cache.guardar) as guardar:
                anfitrion._medir_sonoridad_fondo(tuple(temas), 3)
            self.assertEqual(guardar.call_count, 2)
            releida = CacheSonoridad(ruta_cache)
            for tema in temas:
                info = os.stat(tema.origen)
                self.assertEqual(releida.buscar(tema.origen,
                                                info.st_mtime_ns,
                                                info.st_size), 1.0)

    def test_aplicar_con_opcion_apagada_desactiva_sin_medir(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3")]
            anfitrion = _Anfitrion(
                config={"musica_normalizar": False},
                biblioteca=_BibliotecaFalsa(temas))
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear:
                anfitrion._aplicar_sonoridad()
            anfitrion._adaptador.fijar_activo.assert_called_once_with(False)
            crear.assert_not_called()

    def test_aplicar_encendida_activa_y_mide_lo_que_falta(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3")]
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    _crear_hilo_inmediato), \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                       return_value=1.0):
                anfitrion._aplicar_sonoridad()
            anfitrion._adaptador.fijar_activo.assert_called_once_with(True)
            info = os.stat(temas[0].origen)
            self.assertEqual(anfitrion._cache_sonoridad.buscar(
                temas[0].origen, info.st_mtime_ns, info.st_size), 1.0)

    def test_dos_llamadas_seguidas_lanzan_un_solo_hilo(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            anfitrion._midiendo_sonoridad = False
            lanzados = []

            def _crear(target, nombre, *, args=(), daemon=True):
                lanzados.append((target, nombre, args))

                class _HiloFalso:
                    def start(self):
                        pass

                return _HiloFalso()

            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    side_effect=_crear), \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            self.assertEqual(len(lanzados), 1)
            self.assertTrue(anfitrion._midiendo_sonoridad)

    def test_una_instancia_midiendo_no_frena_a_otra(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
            biblioteca = _BibliotecaFalsa(temas)
            primera = _Anfitrion(biblioteca=biblioteca)
            segunda = _Anfitrion(biblioteca=biblioteca)
            self.addCleanup(setattr, SonoridadMusica,
                            "_midiendo_sonoridad", False)
            lanzados = []

            def _crear(target, nombre, *, args=(), daemon=True):
                lanzados.append((target, nombre, args))

                class _HiloFalso:
                    def start(self):
                        pass

                return _HiloFalso()

            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    side_effect=_crear), \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"):
                primera._arrancar_sonoridad(primera._biblioteca, 3)
                segunda._arrancar_sonoridad(segunda._biblioteca, 3)
            self.assertEqual(len(lanzados), 2)
            self.assertTrue(primera._midiendo_sonoridad)
            self.assertTrue(segunda._midiendo_sonoridad)
            self.assertFalse(SonoridadMusica._midiendo_sonoridad)

    def test_al_terminar_vuelve_a_false_y_una_tercera_si_lanza(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, f"t{i}.mp3",
                                 contenido=f"audio-{i}".encode())
                     for i in range(3)]
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            anfitrion._midiendo_sonoridad = False
            lanzados = []

            def _crear(target, nombre, *, args=(), daemon=True):
                lanzados.append(nombre)
                return _crear_hilo_inmediato(target, nombre, args=args,
                                             daemon=daemon)

            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    side_effect=_crear), \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                       "ruta_ffmpeg",
                                       return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                       return_value=None):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
                self.assertFalse(anfitrion._midiendo_sonoridad)
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
                self.assertFalse(anfitrion._midiendo_sonoridad)
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            self.assertEqual(len(lanzados), 3)
            self.assertFalse(anfitrion._midiendo_sonoridad)

    def test_el_progreso_cuenta_tambien_lo_fallido(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, f"t{i}.mp3",
                                 contenido=f"audio-{i}".encode())
                     for i in range(3)]
            vistos = []
            anfitrion = _Anfitrion(
                biblioteca=_BibliotecaFalsa(temas),
                cache=CacheSonoridad(Path(tmp) / "s.json"))
            anfitrion._midiendo_sonoridad = False

            def _medir(_ruta, origen):
                vistos.append(anfitrion._progreso_sonoridad)
                if origen == temas[0].origen:
                    return None
                return 1.5

            with mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                    "ruta_ffmpeg",
                                    return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                       side_effect=_medir):
                anfitrion._medir_sonoridad_fondo(tuple(temas), 3)
            self.assertEqual(vistos[-1], (2, 3))


def _generar_wav(ruta, segundos=1):
    muestras = int(44100 * segundos)
    with wave.open(str(ruta), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        for i in range(muestras):
            valor = int(16383 * math.sin(2 * math.pi * 440 * i / 44100))
            wav.writeframes(struct.pack("<h", valor))


class TestHiloRealConFfmpeg(unittest.TestCase):
    """Frontera real: ffmpeg mide un WAV y el hilo deja la ganancia."""

    def test_el_hilo_deja_la_ganancia_del_wav_en_la_cache(self):
        from ytchat.downloads import ffmpeg_bin as ffmpeg_real
        if ffmpeg_real.ruta_ffmpeg() is None:
            self.skipTest("sin ffmpeg en esta máquina")
        with tempfile.TemporaryDirectory() as tmp:
            ruta_wav = Path(tmp) / "tono.wav"
            _generar_wav(ruta_wav)
            tema = Tema(str(ruta_wav.resolve()), "Tono")
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa((tema,)))
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    _crear_hilo_inmediato), \
                    mock.patch.object(musica_sonoridad.paths,
                                       "cache_sonoridad_musica",
                                       return_value=Path(tmp) / "s.json"):
                anfitrion._arrancar_sonoridad(anfitrion._biblioteca, 3)
            info = os.stat(tema.origen)
            ganancia = anfitrion._cache_sonoridad.buscar(
                tema.origen, info.st_mtime_ns, info.st_size)
            self.assertIsInstance(ganancia, float)
            self.assertIsNone(anfitrion._progreso_sonoridad)


if __name__ == "__main__":
    unittest.main()

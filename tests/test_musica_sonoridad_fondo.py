"""Pruebas de la mezcla de sonoridad, sin ventanas ni motor.

La mezcla se prueba sobre un anfitrión mínimo (sin wx): el hilo corre en
el acto como `_HiloInmediato`, `medir` es falso salvo en la prueba real,
que usa el ffmpeg de verdad sobre un WAV generado.
"""

import math
import os
import struct
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest import mock

from bellbird.music.modelo import Tema
from bellbird.music import sonoridad
from bellbird.music.sonoridad import CacheSonoridad
from bellbird.ui import musica_indice
from bellbird.ui import musica_sonoridad
from bellbird.ui.musica_indice import IndiceMusica
from bellbird.ui.musica_sonoridad import SonoridadMusica


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


class _Anfitrion(SonoridadMusica, IndiceMusica):
    def __init__(self, config=None, cache=None, biblioteca=None,
                 generacion=3):
        self._config = {"musica_normalizar": True,
                        "musica_preguntar_igualar": True}
        self._config.update(config or {})
        self._cache_sonoridad = cache
        self._progreso_sonoridad = None
        self._cerrado = False
        self._generacion_etiquetas = generacion
        self._biblioteca = biblioteca
        self._adaptador = mock.Mock()
        self._midiendo_sonoridad = False
        self._detener_sonoridad = False
        self._total_sonoridad = 0
        self._cache_etiquetas = None
        self._coordinador = None
        self._ventanas = {}
        self.avisos = []
        self.guardados = []

    def _avisar(self, aviso):
        self.avisos.append(aviso)

    def _guardar(self, clave, valor):
        self.guardados.append((clave, valor))


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


class TestIndexarNoMide(unittest.TestCase):
    """El índice no arranca la medición: solo la pide el usuario."""

    def _anfitrion(self, tmp):
        for nombre in ("a.mp3", "b.mp3"):
            Path(tmp, nombre).write_bytes(b"audio")
        return _Anfitrion()

    def test_indexar_no_arranca_el_hilo_de_sonoridad(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp)
            entregadas = []
            hilos = []

            def _crear(target, nombre, *, args=(), daemon=True):
                hilos.append(nombre)

                class _HiloFalso:
                    def start(self):
                        pass

                return _HiloFalso()

            with mock.patch.object(musica_indice.diagnostico,
                                    "crear_hilo",
                                    side_effect=_crear), \
                    mock.patch.object(musica_indice.wx, "CallAfter",
                                       side_effect=lambda f, *a: f(*a)), \
                    mock.patch.object(musica_indice.motor_vlc,
                                       "disponible",
                                       return_value=False), \
                    mock.patch.object(musica_indice.paths,
                                       "cache_etiquetas_musica",
                                       return_value=Path(tmp) / "e.json"):
                anfitrion._indexar(tmp, entregadas.append)
            self.assertEqual(len(entregadas), 1)
            self.assertNotIn("musica-sonoridad", hilos)
            self.assertFalse(anfitrion._midiendo_sonoridad)


class TestIndexarCreaLaDeFabrica(unittest.TestCase):
    """La carpeta de fábrica se crea al indexar; una elegida, no."""

    def _entorno(self, tmp):
        return (mock.patch.object(musica_indice.wx, "CallAfter",
                                   side_effect=lambda f, *a: f(*a)),
                mock.patch.object(musica_indice.motor_vlc, "disponible",
                                   return_value=False),
                mock.patch.object(musica_indice.paths, "cache_etiquetas_musica",
                                   return_value=Path(tmp) / "e.json"))

    def test_crea_la_de_fabrica_si_no_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "app"
            with mock.patch.object(musica_indice.paths, "carpeta_instalacion",
                                    return_value=destino):
                fabrica = musica_indice.paths.musica_por_defecto()
                self.assertFalse(fabrica.exists())
                anfitrion = _Anfitrion()
                entregadas = []
                llamar, motor, etiquetas = self._entorno(tmp)
                with llamar, motor, etiquetas:
                    anfitrion._indexar(str(fabrica), entregadas.append)
                self.assertTrue(fabrica.is_dir())
                self.assertEqual(len(entregadas), 1)
                self.assertEqual(entregadas[0].temas(), ())

    def test_no_crea_una_elegida_que_no_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            faltante = Path(tmp) / "Elegida"
            anfitrion = _Anfitrion()
            entregadas = []
            llamar, motor, etiquetas = self._entorno(tmp)
            with llamar, motor, etiquetas:
                anfitrion._indexar(str(faltante), entregadas.append)
            self.assertFalse(faltante.exists())
            self.assertEqual(entregadas, [None])


class TestIniciarIgualacion(unittest.TestCase):

    def _anfitrion_con(self, tmp, medidos=(), config=None):
        temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
        ruta_cache = Path(tmp) / "sonoridad.json"
        cache = CacheSonoridad(ruta_cache)
        for tema in medidos:
            info = os.stat(tema.origen)
            cache.poner(tema.origen, info.st_mtime_ns, info.st_size, 2.0)
        return _Anfitrion(config=config, biblioteca=_BibliotecaFalsa(temas))

    def test_con_opcion_apagada_no_arranca_y_dice_apagada(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(
                tmp, config={"musica_normalizar": False})
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                        "ruta_ffmpeg",
                                        return_value="C:/ffmpeg.exe"):
                resultado = anfitrion.iniciar_igualacion(
                    anfitrion._biblioteca)
            crear.assert_not_called()
            self.assertEqual(resultado.codigo, sonoridad.OPCION_APAGADA)

    def test_sin_ffmpeg_no_arranca_y_dice_sin_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(tmp)
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                        "ruta_ffmpeg", return_value=None):
                resultado = anfitrion.iniciar_igualacion(
                    anfitrion._biblioteca)
            crear.assert_not_called()
            self.assertEqual(resultado.codigo, sonoridad.SIN_FFMPEG)

    def test_sin_pendientes_no_arranca_y_dice_nada_pendiente(self):
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
                resultado = anfitrion.iniciar_igualacion(
                    anfitrion._biblioteca)
            crear.assert_not_called()
            self.assertEqual(resultado.codigo, sonoridad.NADA_PENDIENTE)

    def test_sin_biblioteca_dice_nada_pendiente(self):
        anfitrion = _Anfitrion()
        with mock.patch.object(musica_sonoridad.diagnostico,
                                "crear_hilo") as crear:
            resultado = anfitrion.iniciar_igualacion(None)
        crear.assert_not_called()
        self.assertEqual(resultado.codigo, sonoridad.NADA_PENDIENTE)

    def test_ya_midiendo_devuelve_el_total_sin_otro_hilo(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(tmp)
            anfitrion._midiendo_sonoridad = True
            anfitrion._total_sonoridad = 7
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                        "ruta_ffmpeg",
                                        return_value="C:/ffmpeg.exe"):
                resultado = anfitrion.iniciar_igualacion(
                    anfitrion._biblioteca)
            crear.assert_not_called()
            self.assertEqual(resultado.codigo, sonoridad.YA_MIDIENDO)
            self.assertEqual(resultado.total, 7)

    def test_inicia_y_devuelve_inicio_con_el_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(tmp)

            def _crear(target, nombre, *, args=(), daemon=True):
                class _HiloFalso:
                    def start(self):
                        pass

                return _HiloFalso()

            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo",
                                    side_effect=_crear) as crear, \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                        "ruta_ffmpeg",
                                        return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                        "cache_sonoridad_musica",
                                        return_value=Path(tmp) / "s.json"):
                resultado = anfitrion.iniciar_igualacion(
                    anfitrion._biblioteca)
            self.assertEqual(crear.call_count, 1)
            self.assertTrue(anfitrion._midiendo_sonoridad)
            self.assertFalse(anfitrion._detener_sonoridad)
            self.assertEqual(resultado.codigo, sonoridad.INICIO)
            self.assertEqual(resultado.total, 2)

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
                resultado = anfitrion.iniciar_igualacion(
                    anfitrion._biblioteca)
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
            self.assertEqual(resultado.codigo, sonoridad.INICIO)
            self.assertEqual(resultado.total, 2)

    def test_detener_sale_antes_de_la_cancion_siguiente(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3"), _tema_local(tmp, "b.mp3")]
            vistos = []

            def _medir(_ruta, origen):
                vistos.append(origen)
                anfitrion.detener_igualacion()
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
            self.assertEqual(vistos, [temas[0].origen])
            self.assertIsNone(anfitrion._progreso_sonoridad)

    def test_iniciar_limpia_la_bandera_de_detener(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion_con(tmp)
            anfitrion._detener_sonoridad = True
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
                anfitrion.iniciar_igualacion(anfitrion._biblioteca)
            self.assertFalse(anfitrion._detener_sonoridad)

    def test_pendientes_devuelven_tambien_el_tamano(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3", contenido=b"12345"),
                      _tema_local(tmp, "b.mp3", contenido=b"1234567890")]
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            with mock.patch.object(musica_sonoridad.paths,
                                    "cache_sonoridad_musica",
                                    return_value=Path(tmp) / "s.json"):
                pendientes, total = anfitrion._pendientes_sonoridad(
                    anfitrion._biblioteca)
            self.assertEqual(len(pendientes), 2)
            self.assertEqual(total, 5 + 10)

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

    def test_aplicar_con_opcion_apagada_solo_desactiva(self):
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

    def test_aplicar_encendida_solo_activa_sin_medir(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = [_tema_local(tmp, "a.mp3")]
            anfitrion = _Anfitrion(biblioteca=_BibliotecaFalsa(temas))
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear:
                anfitrion._aplicar_sonoridad()
            anfitrion._adaptador.fijar_activo.assert_called_once_with(True)
            crear.assert_not_called()
            self.assertIsNone(anfitrion._cache_sonoridad)

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
                primero = anfitrion.iniciar_igualacion(anfitrion._biblioteca)
                segundo = anfitrion.iniciar_igualacion(anfitrion._biblioteca)
            self.assertEqual(len(lanzados), 1)
            self.assertTrue(anfitrion._midiendo_sonoridad)
            self.assertEqual(primero.codigo, sonoridad.INICIO)
            self.assertEqual(segundo.codigo, sonoridad.YA_MIDIENDO)

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
                primera.iniciar_igualacion(primera._biblioteca)
                segunda.iniciar_igualacion(segunda._biblioteca)
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
                anfitrion.iniciar_igualacion(anfitrion._biblioteca)
                self.assertFalse(anfitrion._midiendo_sonoridad)
                anfitrion.iniciar_igualacion(anfitrion._biblioteca)
                self.assertFalse(anfitrion._midiendo_sonoridad)
                anfitrion.iniciar_igualacion(anfitrion._biblioteca)
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

            def _medir(_ruta, _origen):
                vistos.append(anfitrion._progreso_sonoridad)
                return 1.5

            with mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                    "ruta_ffmpeg",
                                    return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.sonoridad, "medir",
                                        side_effect=_medir):
                anfitrion._medir_sonoridad_fondo(tuple(temas), 3)
        self.assertEqual(vistos[-1], (2, 3))


def _muchos_temas(tmp, cantidad):
    return [_tema_local(tmp, f"c{i:02d}.mp3",
                        contenido=f"audio-{i}".encode("utf-8"))
            for i in range(cantidad)]


class TestDatosIgualacion(unittest.TestCase):
    """Lo que necesita la pregunta: cantidad y tamaño, o None."""

    def _anfitrion(self, tmp, cantidad=2, medidos=0, config=None):
        temas = _muchos_temas(tmp, cantidad)
        cache = CacheSonoridad(Path(tmp) / "s.json")
        for tema in temas[:medidos]:
            info = os.stat(tema.origen)
            cache.poner(tema.origen, info.st_mtime_ns, info.st_size, 2.0)
        base = {"musica_normalizar": True, "musica_preguntar_igualar": True}
        base.update(config or {})
        return _Anfitrion(config=base, biblioteca=_BibliotecaFalsa(temas),
                          cache=cache)

    def _entorno(self):
        return (mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                   "ruta_ffmpeg",
                                   return_value="C:/ffmpeg.exe"),)

    def test_devuelve_cantidad_y_tamano(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp, 2)
            with self._entorno()[0]:
                datos = anfitrion.datos_igualacion(anfitrion._biblioteca)
            total = sum(os.stat(t.origen).st_size
                        for t in anfitrion._biblioteca.temas())
            self.assertEqual(datos, (2, total))

    def test_descuenta_lo_ya_medido(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp, 3, medidos=1)
            with self._entorno()[0]:
                datos = anfitrion.datos_igualacion(anfitrion._biblioteca)
            temas = anfitrion._biblioteca.temas()
            total = sum(os.stat(t.origen).st_size for t in temas[1:])
            self.assertEqual(datos, (2, total))

    def test_sin_biblioteca_no_hay_que_preguntar(self):
        anfitrion = _Anfitrion()
        self.assertIsNone(anfitrion.datos_igualacion(None))

    def test_con_opcion_apagada_no_hay_que_preguntar(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(
                tmp, config={"musica_normalizar": False})
            with self._entorno()[0]:
                self.assertIsNone(
                    anfitrion.datos_igualacion(anfitrion._biblioteca))

    def test_sin_preguntar_no_hay_que_preguntar(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(
                tmp, config={"musica_preguntar_igualar": False})
            with self._entorno()[0]:
                self.assertIsNone(
                    anfitrion.datos_igualacion(anfitrion._biblioteca))

    def test_midiendo_no_hay_que_preguntar(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp)
            anfitrion._midiendo_sonoridad = True
            with self._entorno()[0]:
                self.assertIsNone(
                    anfitrion.datos_igualacion(anfitrion._biblioteca))

    def test_sin_ffmpeg_no_hay_que_preguntar(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp)
            with mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                    "ruta_ffmpeg", return_value=None):
                self.assertIsNone(
                    anfitrion.datos_igualacion(anfitrion._biblioteca))

    def test_sin_pendientes_no_hay_que_preguntar(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp, 2, medidos=2)
            with self._entorno()[0]:
                self.assertIsNone(
                    anfitrion.datos_igualacion(anfitrion._biblioteca))


class TestPedirPendientes(unittest.TestCase):
    """El cálculo de pendientes corre fuera del hilo que lo pide."""

    def _anfitrion(self, tmp, cantidad=2):
        temas = _muchos_temas(tmp, cantidad)
        return _Anfitrion(biblioteca=_BibliotecaFalsa(temas))

    def _hilos_reales(self, registrados):
        crear_real = musica_sonoridad.diagnostico.crear_hilo

        def _crear(target, nombre, *, args=(), daemon=True):
            hilo = crear_real(target, nombre, args=args, daemon=daemon)
            registrados.append((nombre, hilo))
            return hilo

        return mock.patch.object(musica_sonoridad.diagnostico, "crear_hilo",
                                 side_effect=_crear)

    def test_calcula_fuera_del_hilo_que_llama(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp)
            principal = threading.get_ident()
            corridos = []
            recibidos = []
            hilos = []
            original = anfitrion._pendientes_sonoridad

            def _envuelto(biblioteca):
                corridos.append(threading.get_ident())
                return original(biblioteca)

            with mock.patch.object(anfitrion, "_pendientes_sonoridad",
                                    side_effect=_envuelto), \
                    mock.patch.object(musica_sonoridad.wx, "CallAfter",
                                       side_effect=lambda f, *a: f(*a)), \
                    mock.patch.object(musica_sonoridad.ffmpeg_bin,
                                        "ruta_ffmpeg",
                                        return_value="C:/ffmpeg.exe"), \
                    mock.patch.object(musica_sonoridad.paths,
                                        "cache_sonoridad_musica",
                                        return_value=Path(tmp) / "s.json"), \
                    self._hilos_reales(hilos):
                anfitrion.pedir_pendientes(
                    anfitrion._biblioteca,
                    lambda pendientes, total: recibidos.append(
                        (pendientes, total)))
                for _nombre, hilo in hilos:
                    hilo.join(timeout=10)
            self.assertEqual([nombre for nombre, _hilo in hilos],
                             ["musica-pendientes"])
            self.assertEqual(len(corridos), 1)
            self.assertNotEqual(corridos[0], principal)
            self.assertEqual(len(recibidos), 1)
            pendientes, total = recibidos[0]
            self.assertEqual(len(pendientes), 2)
            self.assertEqual(total, sum(
                os.stat(tema.origen).st_size
                for tema in anfitrion._biblioteca.temas()))

    def test_segundo_pedido_mientras_calcula_no_lanza_otro(self):
        with tempfile.TemporaryDirectory() as tmp:
            anfitrion = self._anfitrion(tmp)
            entrado = threading.Event()
            soltar = threading.Event()
            original = anfitrion._pendientes_sonoridad

            def _envuelto(biblioteca):
                entrado.set()
                soltar.wait(timeout=10)
                return original(biblioteca)

            primeros = []
            segundos = []
            hilos = []
            with mock.patch.object(anfitrion, "_pendientes_sonoridad",
                                    side_effect=_envuelto), \
                    mock.patch.object(musica_sonoridad.wx, "CallAfter",
                                       side_effect=lambda f, *a: f(*a)), \
                    mock.patch.object(musica_sonoridad.paths,
                                        "cache_sonoridad_musica",
                                        return_value=Path(tmp) / "s.json"), \
                    self._hilos_reales(hilos):
                anfitrion.pedir_pendientes(
                    anfitrion._biblioteca,
                    lambda pendientes, total: primeros.append(
                        (pendientes, total)))
                self.assertTrue(entrado.wait(timeout=10))
                anfitrion.pedir_pendientes(
                    anfitrion._biblioteca,
                    lambda pendientes, total: segundos.append(
                        (pendientes, total)))
                soltar.set()
                for _nombre, hilo in hilos:
                    hilo.join(timeout=10)
            self.assertEqual([nombre for nombre, _hilo in hilos],
                             ["musica-pendientes"])
            self.assertEqual(len(primeros), 1)
            self.assertEqual(segundos, [])

    def test_sin_biblioteca_o_midiendo_no_lanza_nada(self):
        anfitrion = _Anfitrion()
        with mock.patch.object(musica_sonoridad.diagnostico,
                                "crear_hilo") as crear:
            anfitrion.pedir_pendientes(None, lambda p, t: None)
        crear.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            otro = self._anfitrion(tmp)
            otro._midiendo_sonoridad = True
            with mock.patch.object(musica_sonoridad.diagnostico,
                                    "crear_hilo") as crear:
                otro.pedir_pendientes(otro._biblioteca, lambda p, t: None)
            crear.assert_not_called()


class TestFijarPreguntarIgualar(unittest.TestCase):
    """La casilla deja guardado que no se pregunte más."""

    def test_apagar_guarda_en_memoria_y_en_disco(self):
        anfitrion = _Anfitrion()
        self.assertTrue(anfitrion._config["musica_preguntar_igualar"])
        anfitrion.fijar_preguntar_igualar(False)
        self.assertIs(anfitrion._config["musica_preguntar_igualar"], False)
        self.assertEqual(anfitrion.guardados, [("preguntar_igualar",
                                                "false")])

    def test_encender_guarda_en_memoria_y_en_disco(self):
        anfitrion = _Anfitrion(config={"musica_preguntar_igualar": False})
        anfitrion.fijar_preguntar_igualar(True)
        self.assertIs(anfitrion._config["musica_preguntar_igualar"], True)
        self.assertEqual(anfitrion.guardados, [("preguntar_igualar",
                                                "true")])


class TestTextoIgualando(unittest.TestCase):

    def test_con_progreso_devuelve_el_texto(self):
        anfitrion = _Anfitrion()
        anfitrion._progreso_sonoridad = (3, 10)
        self.assertEqual(anfitrion.texto_igualando(),
                          "Igualando el volumen: 3 de 10")

    def test_sin_medicion_da_vacio(self):
        anfitrion = _Anfitrion()
        anfitrion._progreso_sonoridad = None
        self.assertEqual(anfitrion.texto_igualando(), "")


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
        from bellbird.downloads import ffmpeg_bin as ffmpeg_real
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
                resultado = anfitrion.iniciar_igualacion(anfitrion._biblioteca)
            self.assertEqual(resultado.codigo, sonoridad.INICIO)
            info = os.stat(tema.origen)
            ganancia = anfitrion._cache_sonoridad.buscar(
                tema.origen, info.st_mtime_ns, info.st_size)
            self.assertIsInstance(ganancia, float)
            self.assertIsNone(anfitrion._progreso_sonoridad)


if __name__ == "__main__":
    unittest.main()

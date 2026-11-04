"""Pruebas de la guía de encuadre en marcha.

Sin wx.App ni ventanas: el marco, OBS y el detector son dobles, y
`wx.CallAfter` se reemplaza por un registro para ejecutar sus finales a
mano. El tiempo entra por argumento en `_paso`, sin parches globales.
"""

import threading
import time
import unittest
from unittest import mock

from bellbird.camera import encuadre, guia
from bellbird.camera.detector_rostros import Cuadro
from bellbird.obs.obs_camara import CamaraNoEncontrada, CamaraObs
from bellbird.ui import guia_encuadre
from bellbird.ui.guia_encuadre import Guia


ANCHO = 320
ALTO = 240


def _rostro(centro_x, ojos_y):
    ancho, alto = 80.0, 100.0
    x = centro_x * ANCHO - ancho / 2
    ojos = ojos_y * ALTO
    return encuadre.Rostro(
        x=x, y=20.0, ancho=ancho, alto=alto,
        ojo_izquierda=(x + 20.0, ojos), ojo_derecha=(x + 60.0, ojos),
        nariz=(x + 40.0, ojos + 20.0), confianza=0.99)


def _cuadro_con(rostros):
    return Cuadro(rostros=tuple(rostros), ancho=ANCHO, alto=ALTO,
                  luz_rostro=120.0, luz_fondo=90.0, huella=b"huella")


class WorkerFalso:
    """Doble de la lectura: pausada o no, y cuántas veces cambió."""

    def __init__(self, pausado=False):
        self._pausado = pausado
        self.cambios = 0

    def esta_pausado(self):
        return self._pausado

    def toggle_pausa(self):
        self._pausado = not self._pausado
        self.cambios += 1


class MarcoFalso:
    """Doble del marco principal: config, lectura y bandera de vivo."""

    def __init__(self, pausado=False):
        self._config = {"camara_fuente": "", "camara_invertir": False}
        self._worker = WorkerFalso(pausado)

    def IsBeingDeleted(self):
        return False


class _Testigo(unittest.TestCase):

    def parchear(self, nombre, **kwargs):
        parche = mock.patch.object(guia_encuadre, nombre, **kwargs)
        self.addCleanup(parche.stop)
        return parche.start()

    def parchear_wx(self):
        llamadas = []

        def _callafter(funcion, *args):
            llamadas.append((funcion, args))

        falso_wx = mock.Mock()
        falso_wx.CallAfter.side_effect = _callafter
        self.parchear("wx", new=falso_wx)
        return llamadas

    def obs_abierto(self, camara=None):
        self.parchear("disponible", return_value=True)
        self.parchear("obs_activacion").obs_esta_en_ejecucion.return_value = True
        cliente = mock.Mock()
        self.parchear("obs_cliente").ClienteObs.return_value = cliente
        self.parchear("obs_camara").buscar_camara.return_value = \
            camara or CamaraObs("Cam", False)
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        return cliente

    def correr(self, llamadas):
        for funcion, args in llamadas:
            funcion(*args)


class TestIniciar(_Testigo):

    def test_anuncia_pausa_y_arranca(self):
        marco = MarcoFalso(pausado=False)
        self.obs_abierto()
        anunciar = self.parchear("anunciar")
        crear = self.parchear("diagnostico").crear_hilo
        al_terminar = mock.Mock()
        guiada = Guia()
        self.assertTrue(guiada.iniciar(marco, "", False, "normal", al_terminar))
        anunciar.assert_called_once_with(
            "Guía de encuadre. Sigue los pitidos.")
        self.assertEqual(marco._worker.cambios, 1)
        self.assertTrue(marco._worker.esta_pausado())
        crear.assert_called_once()
        self.assertTrue(guiada.en_marcha() or guiada._hilo is not None)

    def test_con_lectura_en_pausa_no_la_toca(self):
        marco = MarcoFalso(pausado=True)
        self.obs_abierto()
        self.parchear("anunciar")
        self.parchear("diagnostico").crear_hilo
        guiada = Guia()
        self.assertTrue(guiada.iniciar(marco, "", False, "normal", mock.Mock()))
        self.assertEqual(marco._worker.cambios, 0)
        self.assertTrue(marco._worker.esta_pausado())

    def test_sin_detector_lo_dice_y_no_arranca(self):
        marco = MarcoFalso()
        self.parchear("disponible", return_value=False)
        anunciar = self.parchear("anunciar")
        crear = self.parchear("diagnostico").crear_hilo
        guiada = Guia()
        self.assertFalse(guiada.iniciar(marco, "", False, "normal", mock.Mock()))
        anunciar.assert_called_once_with(
            "El detector de rostros no está instalado.")
        crear.assert_not_called()

    def test_con_obs_cerrado_lo_dice_y_no_arranca(self):
        marco = MarcoFalso()
        self.parchear("disponible", return_value=True)
        self.parchear("obs_activacion").obs_esta_en_ejecucion.return_value = False
        anunciar = self.parchear("anunciar")
        crear = self.parchear("diagnostico").crear_hilo
        guiada = Guia()
        self.assertFalse(guiada.iniciar(marco, "", False, "normal", mock.Mock()))
        anunciar.assert_called_once_with("OBS no está abierto.")
        crear.assert_not_called()

    def test_en_marcha_no_duplica(self):
        marco = MarcoFalso()
        self.obs_abierto()
        self.parchear("anunciar")
        hilo = mock.Mock()
        hilo.is_alive.return_value = True
        guiada = Guia()
        guiada._hilo = hilo
        crear = self.parchear("diagnostico").crear_hilo
        self.assertFalse(guiada.iniciar(marco, "", False, "normal", mock.Mock()))
        crear.assert_not_called()


class TestDetener(_Testigo):

    def _en_marcha(self, marco, pausada=True):
        guiada = Guia()
        guiada._hilo = mock.Mock()
        guiada._parada = threading.Event()
        guiada._pausa_tomada = pausada
        guiada._al_terminar = mock.Mock()
        import weakref
        guiada._marco = weakref.ref(marco)
        return guiada

    def test_devuelve_pausa_reinicia_y_anuncia(self):
        marco = MarcoFalso(pausado=True)
        self.parchear("anunciar")
        memoria = self.parchear("sonido_memoria")
        anunciar = guia_encuadre.anunciar
        guiada = self._en_marcha(marco, pausada=True)
        terminar = guiada._al_terminar
        guiada.detener("Guía de encuadre detenida.")
        memoria.detener.assert_called_once_with()
        self.assertEqual(marco._worker.cambios, 1)
        self.assertFalse(marco._worker.esta_pausado())
        terminar.assert_called_once_with()
        anunciar.assert_called_once_with("Guía de encuadre detenida.")
        self.assertIsNone(guiada._hilo)
        self.assertIsNone(guiada._parada)
        self.assertFalse(guiada.en_marcha())

    def test_sin_pausa_tomada_no_reanuda(self):
        marco = MarcoFalso(pausado=False)
        self.parchear("anunciar")
        guiada = self._en_marcha(marco, pausada=False)
        guiada.detener("Guía de encuadre detenida.")
        self.assertEqual(marco._worker.cambios, 0)

    def test_con_marco_muerto_no_toca_nada(self):
        marco = MarcoFalso(pausado=True)
        self.parchear("anunciar")
        self.parchear("sonido_memoria")
        anunciar = guia_encuadre.anunciar
        guiada = self._en_marcha(marco, pausada=True)
        guiada._marco = lambda: None
        terminar = guiada._al_terminar
        guiada.detener("Guía de encuadre detenida.")
        self.assertEqual(marco._worker.cambios, 0)
        anunciar.assert_not_called()
        terminar.assert_called_once_with()


class TestPaso(_Testigo):

    def _marcha(self, rostros):
        detector = mock.Mock()
        detector.analizar.return_value = _cuadro_con(rostros)
        return guia.Marcha(
            inicio=0.0, cliente=mock.Mock(), camara=mock.Mock(),
            detector=detector, espejo=False)

    def test_el_ritmo_de_la_guia_es_el_nuevo(self):
        self.assertEqual(guia_encuadre.INTERVALO_GUIA, 0.05)

    def test_un_cuadro_fuera_suena_el_pitido_con_paneo_y_nota(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        tonos = self.parchear("tono_guia")
        tonos.pitido.return_value = b"pitido"
        memoria = self.parchear("sonido_memoria")
        archivo = self.parchear("reproducir_archivo")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._timbre = "calido"
        guiada._marcha = self._marcha([_rostro(0.2, 0.35)])
        self.assertTrue(guiada._paso(1.0))
        self.assertEqual(llamadas, [])
        pulso = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        tonos.pitido.assert_called_once_with(
            pulso.paneo, pulso.frecuencia, "calido")
        memoria.reproducir.assert_called_once_with(b"pitido")
        archivo.assert_not_called()

    def test_sin_rostro_suena_cada_un_segundo(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        self.parchear("sonido_memoria")
        suena = self.parchear("reproducir_archivo")
        self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([])
        self.assertTrue(guiada._paso(1.0))
        self.assertTrue(str(suena.call_args[0][0]).endswith("sin_rostro.wav"))
        suena.reset_mock()
        self.assertTrue(guiada._paso(1.5))
        suena.assert_not_called()
        self.assertTrue(guiada._paso(2.1))
        self.assertTrue(str(suena.call_args[0][0]).endswith("sin_rostro.wav"))

    def test_en_la_zona_arranca_el_tono_una_sola_vez(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        tonos = self.parchear("tono_guia")
        tonos.tono_centro.return_value = b"centro"
        memoria = self.parchear("sonido_memoria")
        memoria.reproducir.return_value = True
        self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.5, 0.35)])
        self.assertTrue(guiada._paso(1.0))
        self.assertTrue(guiada._paso(1.1))
        tonos.tono_centro.assert_called_once_with("normal")
        memoria.reproducir.assert_called_once_with(b"centro", bucle=True)

    def test_al_salir_de_la_zona_corta_el_tono(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        tonos = self.parchear("tono_guia")
        tonos.tono_centro.return_value = b"centro"
        tonos.pitido.return_value = b"pitido"
        memoria = self.parchear("sonido_memoria")
        memoria.reproducir.return_value = True
        self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.5, 0.35)])
        self.assertTrue(guiada._paso(1.0))
        memoria.detener.reset_mock()
        guiada._marcha.detector.analizar.return_value = _cuadro_con(
            [_rostro(0.2, 0.35)])
        self.assertTrue(guiada._paso(1.1))
        memoria.detener.assert_called_once_with()
        memoria.reproducir.assert_called_with(b"pitido")

    def test_centrada_tras_racha_termina_con_listo_y_frase(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        self.parchear("tono_guia").tono_centro.return_value = b"centro"
        memoria = self.parchear("sonido_memoria")
        memoria.reproducir.return_value = True
        suena = self.parchear("reproducir_archivo")
        anunciar = self.parchear("anunciar")
        llamadas = self.parchear_wx()
        terminar = mock.Mock()
        marco = MarcoFalso(pausado=True)
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.5, 0.35)])
        guiada._al_terminar = terminar
        guiada._parada = threading.Event()
        guiada._marco = lambda: marco
        self.assertTrue(guiada._paso(1.0))
        self.assertFalse(guiada._paso(2.6))
        nombres = [str(llamada[0][0]) for llamada in suena.call_args_list]
        self.assertTrue(nombres[-1].endswith("listo.wav"))
        memoria.detener.assert_called()
        self.assertEqual(len(llamadas), 1)
        self.correr(llamadas)
        terminar.assert_called_once_with()
        anunciar.assert_called_once_with("Rostro centrado.")

    def test_a_los_60_segundos_se_detiene(self):
        self.parchear("obs_camara").capturar_cuadro.return_value = b"cuadro"
        self.parchear("sonido_memoria")
        suena = self.parchear("reproducir_archivo")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.2, 0.35)])
        self.assertFalse(guiada._paso(60.0))
        suena.assert_not_called()
        self.assertEqual(len(llamadas), 1)
        funcion, args = llamadas[0]
        self.assertIs(funcion.__self__, guiada)
        self.assertIs(funcion.__func__, Guia.detener)
        self.assertEqual(args, ("Guía de encuadre detenida.",))
        self.correr(llamadas)
        guia_encuadre.sonido_memoria.detener.assert_called_once_with()

    def test_fallo_de_captura_cierra_con_su_texto(self):
        self.parchear("obs_camara").capturar_cuadro.side_effect =             CamaraNoEncontrada("No hay ninguna cámara en OBS.")
        memoria = self.parchear("sonido_memoria")
        suena = self.parchear("reproducir_archivo")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marcha = self._marcha([_rostro(0.2, 0.35)])
        self.assertFalse(guiada._paso(1.0))
        suena.assert_not_called()
        self.assertEqual(llamadas[0][1],
                         ("No hay ninguna cámara en OBS.",))
        self.correr(llamadas)
        memoria.detener.assert_called_once_with()


class TestBucle(_Testigo):

    def test_con_marco_muerto_no_anuncia(self):
        anunciar = self.parchear("anunciar")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marco = lambda: None
        guiada._bucle("", False)
        self.assertEqual(len(llamadas), 1)
        self.correr(llamadas)
        anunciar.assert_not_called()

    def test_sin_camara_cierra_con_su_texto(self):
        marco = MarcoFalso()
        self.obs_abierto()
        self.parchear("obs_camara").buscar_camara.side_effect = \
            CamaraNoEncontrada("No hay ninguna cámara en OBS.")
        llamadas = self.parchear_wx()
        guiada = Guia()
        guiada._marco = lambda: marco
        guiada._parada = threading.Event()
        guiada._bucle("", False)
        self.assertEqual(llamadas[0][1], ("No hay ninguna cámara en OBS.",))


class TestDetenerEnCuadro(_Testigo):

    def _guiada(self, rostros, durante_captura):
        marco = MarcoFalso(pausado=True)
        self.obs_abierto()
        self.parchear("DetectorRostros").return_value.analizar.return_value = \
            _cuadro_con(rostros)
        self.parchear("tono_guia")
        self.parchear("sonido_memoria")
        self.parchear("reproducir_archivo")
        self.parchear_wx()
        guiada = Guia()
        guiada._marco = lambda: marco
        guiada._parada = threading.Event()
        guiada._timbre = "normal"

        def capturar(cliente, camara):
            durante_captura(guiada)
            return b"cuadro"

        self.parchear("obs_camara").capturar_cuadro.side_effect = capturar
        return guiada

    def test_tras_detener_no_suena_el_tono_del_centro_del_cuadro(self):
        guiada = self._guiada([_rostro(0.5, 0.35)],
                              lambda g: g.detener(None))
        guiada._bucle("", False)
        guia_encuadre.sonido_memoria.reproducir.assert_not_called()

    def test_tras_detener_no_suena_el_pitido_del_cuadro(self):
        guiada = self._guiada([_rostro(0.2, 0.35)],
                              lambda g: g.detener(None))
        guiada._bucle("", False)
        guia_encuadre.sonido_memoria.reproducir.assert_not_called()

    def test_tras_detener_no_suena_el_aviso_sin_rostro(self):
        guiada = self._guiada([], lambda g: g.detener(None))
        guiada._bucle("", False)
        guia_encuadre.reproducir_archivo.assert_not_called()

    def test_detener_e_iniciar_deja_salir_al_hilo_viejo(self):
        guiada = self._guiada([_rostro(0.2, 0.35)], lambda g: None)
        nueva = threading.Event()
        capturas = []

        def capturar(cliente, camara):
            capturas.append(1)
            if len(capturas) == 1:
                guiada.detener(None)
                guiada._parada = nueva
            else:
                nueva.set()
            return b"cuadro"

        guia_encuadre.obs_camara.capturar_cuadro.side_effect = capturar
        paso = mock.Mock(wraps=guiada._paso)
        guiada._paso = paso
        guiada._bucle("", False)
        self.assertEqual(paso.call_count, 1)

    def test_al_salir_corta_el_tono_que_quedo_sonando(self):
        guiada = self._guiada([_rostro(0.5, 0.35)], lambda g: None)
        memoria = guia_encuadre.sonido_memoria

        def arrancar_tono(*args, **kwargs):
            guiada._parada.set()
            return True

        memoria.reproducir.side_effect = arrancar_tono
        guiada._bucle("", False)
        memoria.detener.assert_called_once_with()


class TestCierreDeVentana(_Testigo):

    def test_al_cerrar_la_ventana_la_guia_termina_y_corta_el_tono(self):
        marco = MarcoFalso(pausado=True)
        marco._parada = threading.Event()
        self.obs_abierto()
        self.parchear("DetectorRostros").return_value.analizar.return_value = \
            _cuadro_con([_rostro(0.5, 0.35)])
        self.parchear("tono_guia").tono_centro.return_value = b"centro"
        memoria = self.parchear("sonido_memoria")
        memoria.reproducir.return_value = True
        self.parchear_wx()
        guiada = Guia()
        guiada._marco = lambda: marco
        guiada._parada = threading.Event()
        guiada._timbre = "normal"
        hilo = threading.Thread(target=guiada._bucle,
                                args=("", False), daemon=True)
        hilo.start()
        fin = time.monotonic() + 2.0
        while guiada._dueno_centro is None and time.monotonic() < fin:
            time.sleep(0.01)
        self.assertIsNotNone(guiada._dueno_centro)
        memoria.detener.reset_mock()
        memoria.reproducir.reset_mock()
        marco._parada.set()
        hilo.join(1.0)
        self.assertFalse(hilo.is_alive())
        memoria.detener.assert_called_once_with()
        memoria.reproducir.assert_not_called()


class TestTextoFallo(_Testigo):

    def test_de_camara_y_captura_es_su_texto(self):
        self.assertEqual(
            guia_encuadre._texto_fallo(
                CamaraNoEncontrada("No hay ninguna cámara en OBS.")),
            "No hay ninguna cámara en OBS.")

    def test_otro_fallo_es_el_traducido_de_obs(self):
        self.parchear("obs_cliente").mensaje_de_fallo_obs.return_value = \
            "Fallo traducido de OBS."
        self.assertEqual(guia_encuadre._texto_fallo(RuntimeError("socket")),
                         "Fallo traducido de OBS.")


if __name__ == "__main__":
    unittest.main()

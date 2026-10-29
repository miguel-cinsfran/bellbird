"""Pruebas de las teclas de silencio y salto de la música."""

import unittest

from bellbird.music.modelo import ERROR_MOTOR, OK, SIN_TEMA, Resultado
from bellbird.music.transporte import ResultadoSalto
from bellbird.ui.musica_teclas import TeclasMusica


class ItemFalso:

    def __init__(self):
        self.estado = None

    def Check(self, valor):
        self.estado = valor


class MarcoFalso:

    def __init__(self):
        self.mi_musica_silenciar = ItemFalso()


class CoordinadorFalso:

    def __init__(self, silenciado=False, salto=None):
        self.silenciado = silenciado
        self.saltos = []
        self.silencios = []
        self.volumenes = []
        self.salto = salto

    def fijar_volumen(self, valor):
        self.volumenes.append(valor)
        self.silenciado = False
        return Resultado(True, OK, None)

    def fijar_silencio(self, activo):
        self.silencios.append(activo)
        self.silenciado = activo
        return Resultado(True, OK, None)

    def saltar(self, delta_ms):
        self.saltos.append(delta_ms)
        return self.salto


class Host(TeclasMusica):
    """Control mínimo, sin ventana ni motor reales."""

    def __init__(self, coordinador=None):
        self._coordinador = coordinador
        self._frame = MarcoFalso()
        self.avisos = []
        self.acciones = []
        self.refrescos = 0

    def _avisar(self, aviso):
        self.avisos.append(aviso)

    def _refrescar_ventana_abierta(self):
        self.refrescos += 1

    def _accion_coordinador(self, accion):
        self.acciones.append(accion)

    def _incluir_artista(self):
        return False

    def _volumen_config(self):
        return 40

    def reproducir_o_pausar(self):
        pass

    def siguiente(self):
        pass

    def anterior(self):
        pass

    def subir_volumen(self):
        pass

    def bajar_volumen(self):
        pass

    def que_suena(self):
        pass

    def alternar_aleatorio(self):
        pass

    def ciclar_repetir(self):
        pass

    def detener(self):
        pass


class TestAcciones(unittest.TestCase):

    def test_acciones_musica_incluye_las_doce_en_orden(self):
        acciones = Host().acciones_musica()
        self.assertEqual(list(acciones), [
            "musica_play", "musica_siguiente", "musica_anterior",
            "musica_vol_mas", "musica_vol_menos", "musica_que_suena",
            "musica_silenciar", "musica_aleatorio", "musica_repetir",
            "musica_detener", "musica_adelantar", "musica_retroceder",
        ])
        self.assertTrue(all(callable(f) for f in acciones.values()))


class TestSilencioTeclas(unittest.TestCase):

    def test_alternar_silencia_y_marca_la_casilla(self):
        coordinador = CoordinadorFalso()
        host = Host(coordinador)
        host.alternar_silencio()
        self.assertEqual(coordinador.silencios, [True])
        self.assertTrue(host._frame.mi_musica_silenciar.estado)
        self.assertEqual(host.avisos[0].texto, "Música silenciada")
        self.assertIsNone(host.avisos[0].sonido)
        self.assertEqual(host.refrescos, 1)

    def test_alternar_devuelve_el_sonido(self):
        host = Host(CoordinadorFalso(silenciado=True))
        host.alternar_silencio()
        self.assertEqual(host.avisos[0].texto,
                         "Sonido de la música restaurado")

    def test_sin_motor_alternar_pide_detener(self):
        host = Host()
        host.alternar_silencio()
        self.assertEqual(host.acciones, ["detener"])
        self.assertEqual(host.avisos, [])

    def test_si_el_silencio_falla_avisa_el_error(self):
        class Fallon(CoordinadorFalso):
            def fijar_silencio(self, activo):
                return Resultado(False, ERROR_MOTOR, None)

        host = Host(Fallon())
        host.alternar_silencio()
        self.assertEqual(host.avisos[0].sonido, "error")
        self.assertIsNone(host._frame.mi_musica_silenciar.estado)


class TestReaplicarVolumen(unittest.TestCase):

    def test_con_silencio_aplica_volumen_y_lo_conserva(self):
        coordinador = CoordinadorFalso(silenciado=True)
        host = Host(coordinador)
        host._reaplicar_volumen()
        self.assertTrue(coordinador.silenciado)
        self.assertEqual(coordinador.volumenes, [40])
        self.assertTrue(host._frame.mi_musica_silenciar.estado)

    def test_sin_silencio_aplica_volumen_y_lo_deja_apagado(self):
        coordinador = CoordinadorFalso(silenciado=False)
        host = Host(coordinador)
        host._reaplicar_volumen()
        self.assertFalse(coordinador.silenciado)
        self.assertEqual(coordinador.volumenes, [40])
        self.assertFalse(host._frame.mi_musica_silenciar.estado)


class TestSaltoTeclas(unittest.TestCase):
    def _host(self, salto):
        coordinador = CoordinadorFalso(salto=salto)
        return Host(coordinador), coordinador

    def test_adelantar_pide_diez_segundos(self):
        host, coordinador = self._host(
            ResultadoSalto(True, OK, None, 40_000))
        host.adelantar()
        self.assertEqual(coordinador.saltos, [10_000])
        self.assertEqual(host.avisos[0].texto, "0:40")
        self.assertIsNone(host.avisos[0].sonido)

    def test_retroceder_pide_menos_diez_segundos(self):
        host, coordinador = self._host(
            ResultadoSalto(True, OK, None, 20_000))
        host.retroceder()
        self.assertEqual(coordinador.saltos, [-10_000])

    def test_sin_tema_avisa_que_no_hay_tema(self):
        host, _coordinador = self._host(
            ResultadoSalto(False, SIN_TEMA, None))
        host.adelantar()
        self.assertEqual(host.avisos[0].texto, "No hay música sonando")

    def test_sin_motor_los_saltos_piden_detener(self):
        host = Host()
        host.adelantar()
        host.retroceder()
        self.assertEqual(host.acciones, ["detener", "detener"])
        self.assertEqual(host.avisos, [])


if __name__ == "__main__":
    unittest.main()

"""Pruebas del guardado diferido de música (guardado_diferido.py)."""

import unittest

from bellbird.music.guardado_diferido import GuardadoDiferido


class _Temporizador:
    """Doble del objeto que devuelve `wx.CallLater`."""

    def __init__(self, ms, funcion):
        self.ms = ms
        self.funcion = funcion
        self.detenido = False

    def Stop(self):
        self.detenido = True


class _Programador:
    """Doble de `programar`: guarda lo pedido y lo dispara a mano."""

    def __init__(self):
        self.temporizadores = []

    def __call__(self, ms, funcion):
        temporizador = _Temporizador(ms, funcion)
        self.temporizadores.append(temporizador)
        return temporizador

    def disparar(self):
        for temporizador in self.temporizadores:
            if temporizador.detenido:
                continue
            temporizador.detenido = True
            temporizador.funcion()


class TestGuardadoDiferido(unittest.TestCase):

    def test_usa_el_retardo_pedido(self):
        programador = _Programador()
        GuardadoDiferido(programador, retardo_ms=1500).pedir(lambda: None)
        self.assertEqual(programador.temporizadores[0].ms, 1500)

    def test_el_retardo_por_defecto_es_un_segundo(self):
        programador = _Programador()
        GuardadoDiferido(programador).pedir(lambda: None)
        self.assertEqual(programador.temporizadores[0].ms, 1000)

    def test_n_pedidos_ejecuta_solo_la_ultima_funcion(self):
        programador = _Programador()
        guardado = GuardadoDiferido(programador)
        ejecutadas = []
        for numero in range(5):
            guardado.pedir(lambda numero=numero: ejecutadas.append(numero))
        programador.disparar()
        self.assertEqual(ejecutadas, [4])
        self.assertEqual(len(programador.temporizadores), 5)
        self.assertTrue(all(t.detenido for t in programador.temporizadores))

    def test_cada_pedido_reinicia_el_anterior(self):
        programador = _Programador()
        guardado = GuardadoDiferido(programador)
        ejecutadas = []
        guardado.pedir(lambda: ejecutadas.append("primero"))
        guardado.pedir(lambda: ejecutadas.append("segundo"))
        self.assertTrue(programador.temporizadores[0].detenido)
        self.assertFalse(programador.temporizadores[1].detenido)
        programador.disparar()
        self.assertEqual(ejecutadas, ["segundo"])

    def test_vaciar_ejecuta_en_el_acto_y_cancela_el_temporizador(self):
        programador = _Programador()
        guardado = GuardadoDiferido(programador)
        ejecutadas = []
        guardado.pedir(lambda: ejecutadas.append("guardado"))
        guardado.vaciar()
        self.assertEqual(ejecutadas, ["guardado"])
        self.assertTrue(programador.temporizadores[0].detenido)
        programador.disparar()
        self.assertEqual(ejecutadas, ["guardado"])

    def test_vaciar_sin_pendiente_no_hace_nada(self):
        programador = _Programador()
        guardado = GuardadoDiferido(programador)
        guardado.vaciar()
        self.assertEqual(programador.temporizadores, [])

    def test_despues_de_disparar_se_puede_pedir_de_nuevo(self):
        programador = _Programador()
        guardado = GuardadoDiferido(programador)
        ejecutadas = []
        guardado.pedir(lambda: ejecutadas.append("uno"))
        programador.disparar()
        guardado.pedir(lambda: ejecutadas.append("dos"))
        programador.disparar()
        self.assertEqual(ejecutadas, ["uno", "dos"])

    def test_si_stop_lanza_no_rompe_el_pedido_nuevo(self):
        class TemporizadorRoto:
            def Stop(self):
                raise RuntimeError("cerrado")

        class ProgramadorRoto(_Programador):
            def __call__(self, ms, funcion):
                return TemporizadorRoto()

        programador = ProgramadorRoto()
        guardado = GuardadoDiferido(programador)
        ejecutadas = []
        guardado.pedir(lambda: ejecutadas.append("uno"))
        guardado.pedir(lambda: ejecutadas.append("dos"))
        guardado.vaciar()
        self.assertEqual(ejecutadas, ["dos"])


if __name__ == "__main__":
    unittest.main()

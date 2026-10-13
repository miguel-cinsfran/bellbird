"""Pruebas del lanzador de OBS y del cableado del diálogo, sin ventanas."""

import os
import threading
import unittest
from unittest import mock

from ytchat.obs import obs_cliente
from ytchat.obs import obs_lanzador
from ytchat.obs.obs_lanzador import ObsNoInstalado, abrir_obs, asegurar_obs, ruta_obs

try:
    from ytchat.ui import gui_transmision
    _HAY_GUI = True
except Exception:
    _HAY_GUI = False


RUTA_PRINCIPAL = os.path.join("C:\\OBS", "bin", "64bit", "obs64.exe")
RUTA_WOW = os.path.join("C:\\OBS32", "bin", "64bit", "obs64.exe")
RUTA_PF = os.path.join("C:\\Program Files", "obs-studio", "bin", "64bit",
                        "obs64.exe")


def leer_con(principal=None, wow=None):
    def leer(clave):
        if clave == r"SOFTWARE\OBS Studio":
            return principal
        return wow
    return leer


class RutaObsTest(unittest.TestCase):
    def test_registro_principal(self):
        ruta = ruta_obs(leer_registro=leer_con("C:\\OBS"),
                        existe=lambda r: r == RUTA_PRINCIPAL,
                        entorno={})
        self.assertEqual(ruta, RUTA_PRINCIPAL)

    def test_nodo_de_32_bits(self):
        ruta = ruta_obs(leer_registro=leer_con(None, "C:\\OBS32"),
                        existe=lambda r: r == RUTA_WOW,
                        entorno={})
        self.assertEqual(ruta, RUTA_WOW)

    def test_program_files(self):
        entorno = {"ProgramFiles": "C:\\Program Files"}
        ruta = ruta_obs(leer_registro=leer_con(),
                        existe=lambda r: r == RUTA_PF,
                        entorno=entorno)
        self.assertEqual(ruta, RUTA_PF)

    def test_nada_devuelve_vacio(self):
        self.assertEqual(
            ruta_obs(leer_registro=leer_con(), existe=lambda r: False,
                     entorno={}), "")

    def test_registro_sin_ejecutable_sigue_buscando(self):
        entorno = {"ProgramFiles": "C:\\Program Files"}
        ruta = ruta_obs(leer_registro=leer_con("C:\\OBS"),
                        existe=lambda r: r == RUTA_PF,
                        entorno=entorno)
        self.assertEqual(ruta, RUTA_PF)


class AbrirObsTest(unittest.TestCase):
    def test_argumentos_cwd_y_ventana(self):
        import subprocess
        llamadas = {}

        def popen_falso(args, **kwargs):
            llamadas["args"] = args
            llamadas.update(kwargs)
            return mock.Mock()

        ruta = os.path.join("C:\\OBS", "bin", "64bit", "obs64.exe")
        abrir_obs(ruta, popen=popen_falso)
        self.assertEqual(llamadas["args"],
                          [ruta, "--disable-shutdown-check",
                           "--minimize-to-tray"])
        self.assertEqual(llamadas["cwd"],
                         os.path.join("C:\\OBS", "bin", "64bit"))
        self.assertEqual(llamadas["startupinfo"].wShowWindow, 7)
        self.assertTrue(llamadas["startupinfo"].dwFlags
                        & subprocess.STARTF_USESHOWWINDOW)

    def test_fallo_al_lanzar_es_obs_error(self):
        def popen_falso(args, **kwargs):
            raise OSError("sin permiso")

        with self.assertRaises(obs_cliente.ObsError) as contexto:
            abrir_obs("C:\\OBS\\bin\\64bit\\obs64.exe", popen=popen_falso)
        self.assertEqual(str(contexto.exception), "No se pudo abrir OBS.")


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.ahora += segundos


class AsegurarObsTest(unittest.TestCase):
    def test_ya_abierto_no_hace_nada(self):
        probar = mock.Mock()
        buscar = mock.Mock()
        abrir = mock.Mock()
        anuncia = mock.Mock()
        resultado = asegurar_obs(probar, al_anunciar=anuncia,
                                 en_ejecucion=lambda: True,
                                 buscar=buscar, abrir=abrir)
        self.assertFalse(resultado)
        buscar.assert_not_called()
        abrir.assert_not_called()
        probar.assert_not_called()
        anuncia.assert_not_called()

    def test_no_instalado_levanta_sin_anunciar_abriendo(self):
        anuncia = mock.Mock()
        abrir = mock.Mock()
        with self.assertRaises(ObsNoInstalado) as contexto:
            asegurar_obs(mock.Mock(), al_anunciar=anuncia,
                         en_ejecucion=lambda: False,
                         buscar=lambda: "", abrir=abrir)
        self.assertEqual(
            str(contexto.exception),
            "OBS no está instalado en este equipo. Instálalo desde "
            "obsproject.com y vuelve a intentarlo.")
        abrir.assert_not_called()
        self.assertFalse(any("Abriendo" in str(llamada)
                             for llamada in anuncia.call_args_list))

    def test_abre_y_conecta_al_tercer_intento(self):
        reloj = RelojFalso()
        anuncia = mock.Mock()
        abrir = mock.Mock()
        intentos = []

        def probar():
            intentos.append(1)
            if len(intentos) < 3:
                raise obs_cliente.ObsError("todavía no")

        resultado = asegurar_obs(probar, al_anunciar=anuncia,
                                 en_ejecucion=lambda: False,
                                 buscar=lambda: RUTA_PRINCIPAL,
                                 abrir=abrir, dormir=reloj.dormir,
                                 reloj=reloj.reloj)
        self.assertTrue(resultado)
        self.assertEqual(len(intentos), 3)
        abrir.assert_called_once_with(RUTA_PRINCIPAL)
        anuncia.assert_called_once_with(
            "Abriendo OBS en segundo plano, en el área de notificación. "
            "Puede tardar hasta un minuto.")

    def test_vence_el_plazo(self):
        reloj = RelojFalso()
        with self.assertRaises(obs_cliente.ObsError) as contexto:
            asegurar_obs(mock.Mock(side_effect=obs_cliente.ObsError("no")),
                         en_ejecucion=lambda: False,
                         buscar=lambda: RUTA_PRINCIPAL,
                         abrir=mock.Mock(), dormir=reloj.dormir,
                         reloj=reloj.reloj, limite=10.0, intervalo=2.0)
        self.assertEqual(
            str(contexto.exception),
            "OBS se abrió pero no responde. Comprueba que su servidor "
            "websocket esté activado.")

    def test_parada_puesta_sale_sin_anunciar(self):
        parada = threading.Event()
        parada.set()
        anuncia = mock.Mock()
        buscar = mock.Mock()
        abrir = mock.Mock()
        probar = mock.Mock()
        resultado = asegurar_obs(probar, al_anunciar=anuncia, parada=parada,
                                 en_ejecucion=mock.Mock(),
                                 buscar=buscar, abrir=abrir)
        self.assertTrue(resultado)
        anuncia.assert_not_called()
        buscar.assert_not_called()
        abrir.assert_not_called()
        probar.assert_not_called()


@unittest.skipUnless(_HAY_GUI, "wxPython no está instalado")
class CableadoDialogoTest(unittest.TestCase):
    def test_cargar_inicial_asegura_antes_de_conectar(self):
        orden = []
        llamadas_anuncio = []

        class GestorFalso:
            def conectar(self):
                orden.append("conectar")

            def escenas(self):
                return ("Principal",)

            def escena_al_aire(self):
                return "Principal"

            def fuentes(self, escena):
                return ("Chat YTChat",)

            def instantanea(self, escena, fuente=""):
                return mock.Mock()

            def transformacion(self, escena, fuente=""):
                return {}

            def estado_transmision(self):
                return {}

            def estado_grabacion(self):
                return {}

            def perfil_actual(self):
                return ""

        def asegurar_doble(probar_conexion, al_anunciar=None, parada=None):
            orden.append("asegurar")
            al_anunciar("Abriendo OBS en segundo plano, en el área de "
                       "notificación. Puede tardar hasta un minuto.")
            probar_conexion()

        import types
        falso = types.SimpleNamespace(_gestor=GestorFalso(),
                                      _asegurar=asegurar_doble)
        with mock.patch.object(gui_transmision.wx, "CallAfter",
                               side_effect=lambda f, *a: llamadas_anuncio.append(
                                   (f, a))) as call_after:
            gui_transmision.TransmisionDialog._cargar_inicial(falso)
        self.assertEqual(orden[:3], ["asegurar", "conectar", "conectar"])
        self.assertTrue(call_after.called)
        funcion, argumentos = llamadas_anuncio[0]
        self.assertIs(funcion, gui_transmision.anunciar)
        self.assertEqual(argumentos,
                          ("Abriendo OBS en segundo plano, en el área de "
                           "notificación. Puede tardar hasta un minuto.",))


if __name__ == "__main__":
    unittest.main()

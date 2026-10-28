"""Pruebas del lanzador de OBS y del cableado del diálogo, sin ventanas."""

import ctypes
import os
import tempfile
import threading
import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
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


@unittest.skipUnless(os.name == "nt", "SetDllDirectoryW es solo de Windows")
class AbrirObsSinCarpetaDllTest(unittest.TestCase):
    """OBS no debe heredar la carpeta de DLL de la app al abrirlo."""

    def setUp(self):
        from ctypes import wintypes
        self._nucleo = ctypes.WinDLL("kernel32", use_last_error=True)
        self._nucleo.GetDllDirectoryW.argtypes = [wintypes.DWORD,
                                                  wintypes.LPWSTR]
        self._nucleo.GetDllDirectoryW.restype = wintypes.DWORD
        self._nucleo.SetDllDirectoryW.argtypes = [wintypes.LPCWSTR]
        self._nucleo.SetDllDirectoryW.restype = wintypes.BOOL
        self._anterior = self._leer()
        self.addCleanup(self._restaurar)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _leer(self):
        bufer = ctypes.create_unicode_buffer(32768)
        largo = self._nucleo.GetDllDirectoryW(32768, bufer)
        return bufer.value if largo > 0 else ""

    def _restaurar(self):
        self._nucleo.SetDllDirectoryW(self._anterior or None)

    def test_popen_corre_sin_la_carpeta_heredada(self):
        self._nucleo.SetDllDirectoryW(self._tmp.name)
        visto = {}

        def popen_falso(args, **kwargs):
            visto["dll"] = self._leer()
            return mock.Mock()

        abrir_obs(os.path.join("C:\\OBS", "bin", "64bit", "obs64.exe"),
                  popen=popen_falso)
        self.assertEqual("", visto["dll"],
                         "OBS heredaría la carpeta de DLL de la app")

    def test_la_carpeta_vuelve_despues_de_abrir(self):
        self._nucleo.SetDllDirectoryW(self._tmp.name)
        abrir_obs(os.path.join("C:\\OBS", "bin", "64bit", "obs64.exe"),
                  popen=lambda args, **kwargs: mock.Mock())
        self.assertEqual(self._tmp.name, self._leer(),
                         "la carpeta no se restauró tras abrir OBS")


class CierreIncorrectoPrevioTest(unittest.TestCase):
    def test_con_run_da_true(self):
        falso = lambda carpeta: ["run_20240101", "otra_cosa.txt"]
        self.assertTrue(obs_lanzador.cierre_incorrecto_previo(
            "alguna", listar=falso))

    def test_sin_run_da_false(self):
        falso = lambda carpeta: ["config.json", "logs.txt"]
        self.assertFalse(obs_lanzador.cierre_incorrecto_previo(
            "alguna", listar=falso))

    def test_carpeta_vacia_da_false(self):
        self.assertFalse(obs_lanzador.cierre_incorrecto_previo(
            "alguna", listar=lambda carpeta: []))

    def test_carpeta_inexistente_da_false(self):
        def listar(carpeta):
            raise FileNotFoundError("no existe")
        self.assertFalse(obs_lanzador.cierre_incorrecto_previo(
            "alguna", listar=listar))

    def test_carpeta_ilegible_da_false(self):
        def listar(carpeta):
            raise PermissionError("sin permiso")
        self.assertFalse(obs_lanzador.cierre_incorrecto_previo(
            "alguna", listar=listar))

    def test_carpeta_real_con_run(self):
        with tempfile.TemporaryDirectory() as carpeta:
            abierto = open(os.path.join(carpeta, "run_12345"), "w")
            abierto.close()
            self.assertTrue(obs_lanzador.cierre_incorrecto_previo(carpeta))

    def test_carpeta_real_sin_run(self):
        with tempfile.TemporaryDirectory() as carpeta:
            abierto = open(os.path.join(carpeta, "config.json"), "w")
            abierto.close()
            self.assertFalse(obs_lanzador.cierre_incorrecto_previo(carpeta))


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
                                 buscar=buscar, abrir=abrir,
                                 hubo_cierre_incorrecto=lambda: False)
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
                         buscar=lambda: "", abrir=abrir,
                         hubo_cierre_incorrecto=lambda: False)
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
                                 reloj=reloj.reloj,
                                 hubo_cierre_incorrecto=lambda: False)
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
                         reloj=reloj.reloj, limite=10.0, intervalo=2.0,
                         hubo_cierre_incorrecto=lambda: False)
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
                                 buscar=buscar, abrir=abrir,
                                 hubo_cierre_incorrecto=lambda: False)
        self.assertTrue(resultado)
        anuncia.assert_not_called()
        buscar.assert_not_called()
        abrir.assert_not_called()
        probar.assert_not_called()

    def test_con_cierre_incorrecto_anuncia_los_dos_en_orden(self):
        reloj = RelojFalso()
        anuncia = mock.Mock()
        orden = []
        anuncia.side_effect = lambda frase: orden.append(frase)

        def consultar():
            orden.append("consultar")
            return True

        def abrir_orden(ruta):
            orden.append("abrir")

        resultado = asegurar_obs(mock.Mock(),
                                 al_anunciar=anuncia,
                                 en_ejecucion=lambda: False,
                                 buscar=lambda: RUTA_PRINCIPAL,
                                 abrir=abrir_orden, dormir=reloj.dormir,
                                 reloj=reloj.reloj,
                                 hubo_cierre_incorrecto=consultar)
        self.assertTrue(resultado)
        self.assertEqual(
            orden,
            ["consultar",
             obs_lanzador.TEXTO_ABRIENDO,
             obs_lanzador.TEXTO_MODO_SEGURO,
             "abrir"])

    def test_sin_cierre_incorrecto_solo_anuncia_abriendo(self):
        reloj = RelojFalso()
        anuncia = mock.Mock()
        resultado = asegurar_obs(mock.Mock(),
                                 al_anunciar=anuncia,
                                 en_ejecucion=lambda: False,
                                 buscar=lambda: RUTA_PRINCIPAL,
                                 abrir=mock.Mock(), dormir=reloj.dormir,
                                 reloj=reloj.reloj,
                                 hubo_cierre_incorrecto=lambda: False)
        self.assertTrue(resultado)
        anuncia.assert_called_once_with(obs_lanzador.TEXTO_ABRIENDO)

    def test_vence_con_cierre_incorrecto_nombra_modo_seguro(self):
        reloj = RelojFalso()
        with self.assertRaises(obs_cliente.ObsError) as contexto:
            asegurar_obs(mock.Mock(side_effect=obs_cliente.ObsError("no")),
                         en_ejecucion=lambda: False,
                         buscar=lambda: RUTA_PRINCIPAL,
                         abrir=mock.Mock(), dormir=reloj.dormir,
                         reloj=reloj.reloj, limite=10.0, intervalo=2.0,
                         hubo_cierre_incorrecto=lambda: True)
        self.assertEqual(str(contexto.exception),
                         obs_lanzador.TEXTO_SIN_RESPUESTA_MODO_SEGURO)

    def test_vence_sin_cierre_incorrecto_texto_de_siempre(self):
        reloj = RelojFalso()
        with self.assertRaises(obs_cliente.ObsError) as contexto:
            asegurar_obs(mock.Mock(side_effect=obs_cliente.ObsError("no")),
                         en_ejecucion=lambda: False,
                         buscar=lambda: RUTA_PRINCIPAL,
                         abrir=mock.Mock(), dormir=reloj.dormir,
                         reloj=reloj.reloj, limite=10.0, intervalo=2.0,
                         hubo_cierre_incorrecto=lambda: False)
        self.assertEqual(str(contexto.exception),
                         obs_lanzador.TEXTO_SIN_RESPUESTA)

    def test_ya_abierto_no_consulta_cierre(self):
        consultar = mock.Mock(return_value=True)
        resultado = asegurar_obs(mock.Mock(), al_anunciar=mock.Mock(),
                                 en_ejecucion=lambda: True,
                                 buscar=mock.Mock(), abrir=mock.Mock(),
                                 hubo_cierre_incorrecto=consultar)
        self.assertFalse(resultado)
        consultar.assert_not_called()


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

            def ventanas(self, escena, parada=None):
                return ((), "")

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

            def descripcion_escena(self, parada=None):
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


class TestPseudoLanzador(unittest.TestCase):
    """Pseudotraducción de los anuncios y errores de `obs_lanzador`.

    Sin ventanas: dispara los caminos bajo `con_pseudo()` con dobles y
    exige cada frase propia marcada.
    """

    def test_anuncios_de_apertura_salen_marcados(self):
        anuncios = []
        reloj = RelojFalso()
        with con_pseudo():
            asegurar_obs(mock.Mock(), al_anunciar=anuncios.append,
                         en_ejecucion=lambda: False,
                         buscar=lambda: RUTA_PRINCIPAL, abrir=mock.Mock(),
                         dormir=reloj.dormir, reloj=reloj.reloj,
                         hubo_cierre_incorrecto=lambda: True)
        self.assertEqual(len(anuncios), 2)
        for frase in anuncios:
            self.assertTrue(frase.startswith("[¡"), frase)

    def test_errores_de_apertura_salen_marcados(self):
        with con_pseudo():
            with self.assertRaises(ObsNoInstalado) as contexto:
                asegurar_obs(mock.Mock(), en_ejecucion=lambda: False,
                             buscar=lambda: "", abrir=mock.Mock(),
                             hubo_cierre_incorrecto=lambda: False)
            self.assertTrue(str(contexto.exception).startswith("[¡"),
                            contexto.exception)
            reloj = RelojFalso()
            with self.assertRaises(obs_cliente.ObsError) as contexto:
                asegurar_obs(
                    mock.Mock(side_effect=obs_cliente.ObsError("no")),
                    en_ejecucion=lambda: False, buscar=lambda: RUTA_PRINCIPAL,
                    abrir=mock.Mock(), dormir=reloj.dormir,
                    reloj=reloj.reloj, limite=10.0, intervalo=2.0,
                    hubo_cierre_incorrecto=lambda: False)
            self.assertTrue(str(contexto.exception).startswith("[¡"),
                            contexto.exception)

    def test_fallo_al_abrir_sale_marcado(self):
        def popen_falso(args, **kwargs):
            raise OSError("sin permiso")

        with con_pseudo():
            with self.assertRaises(obs_cliente.ObsError) as contexto:
                abrir_obs("C:\\OBS\\bin\\64bit\\obs64.exe",
                          popen=popen_falso)
        self.assertTrue(str(contexto.exception).startswith("[¡"),
                        contexto.exception)

    def test_constantes_marcadas_se_traducen_al_usarse(self):
        constantes = (obs_lanzador.TEXTO_ABRIENDO,
                      obs_lanzador.TEXTO_MODO_SEGURO,
                      obs_lanzador.TEXTO_SIN_RESPUESTA,
                      obs_lanzador.TEXTO_SIN_RESPUESTA_MODO_SEGURO)
        with con_pseudo():
            for constante in constantes:
                self.assertTrue(_(constante).startswith("[¡"), constante)


if __name__ == "__main__":
    unittest.main()

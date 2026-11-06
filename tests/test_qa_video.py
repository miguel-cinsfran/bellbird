"""Pruebas de qa/video_montaje.py y del cierre y reapertura real."""

import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_RUTA = _RAIZ / "qa" / "video_montaje.py"
_paquete = importlib.util.spec_from_file_location(
    "video_montaje_qa", _RUTA)
video_montaje = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(video_montaje)

_RUTA_DEMO = _RAIZ / "qa" / "video_demo.py"
_paquete_demo = importlib.util.spec_from_file_location(
    "video_demo_qa", _RUTA_DEMO)
video_demo = importlib.util.module_from_spec(_paquete_demo)
_paquete_demo.loader.exec_module(video_demo)


class TestArmarSrt(unittest.TestCase):

    def test_tres_pasos_con_tiempos_exactos_y_numerados(self):
        pasos = [
            {"inicio": 0.0, "fin": 1.5, "texto": "Uno"},
            {"inicio": 1.5, "fin": 65.25, "texto": "Dos"},
            {"inicio": 65.25, "fin": 3661.001, "texto": "Tres"},
        ]
        esperado = (
            "1\n"
            "00:00:00,000 --> 00:00:01,500\n"
            "Uno\n"
            "\n"
            "2\n"
            "00:00:01,500 --> 00:01:05,250\n"
            "Dos\n"
            "\n"
            "3\n"
            "00:01:05,250 --> 01:01:01,001\n"
            "Tres\n"
        )
        self.assertEqual(video_montaje.armar_srt(pasos), esperado)

    def test_desplazamiento_corre_inicio_y_fin(self):
        pasos = [{"inicio": 0.0, "fin": 1.5, "texto": "Uno"}]
        esperado = (
            "1\n"
            "00:00:03,000 --> 00:00:04,500\n"
            "Uno\n"
        )
        self.assertEqual(video_montaje.armar_srt(pasos, 3.0), esperado)

    def test_un_paso_que_termina_antes_de_empezar_se_rechaza(self):
        pasos = [{"inicio": 5.0, "fin": 4.0, "texto": "Al revés"}]
        with self.assertRaises(ValueError):
            video_montaje.armar_srt(pasos)


class TestCodigoDeSalida(unittest.TestCase):

    def test_permiso_previo_y_fallos(self):
        self.assertEqual(video_demo.codigo_de_salida(0, True), 2)
        self.assertEqual(video_demo.codigo_de_salida(1, True), 1)
        self.assertEqual(video_demo.codigo_de_salida(0, False), 0)


class TestDuracion(unittest.TestCase):

    def test_portada_mas_pasos_da_la_duracion_esperada(self):
        pasos = [
            {"inicio": 0.0, "fin": 10.0, "texto": "Uno"},
            {"inicio": 10.0, "fin": 25.5, "texto": "Dos"},
        ]
        self.assertEqual(video_montaje.duracion_total(pasos), 28.5)


class TestArgumentosFfmpeg(unittest.TestCase):

    def test_grabacion_usa_gdigrab_desktop_y_treinta_cuadros(self):
        argumentos = video_montaje.args_grabacion("salida.mp4")
        self.assertIn("gdigrab", argumentos)
        self.assertIn("desktop", argumentos)
        indice = argumentos.index("-framerate")
        self.assertEqual(argumentos[indice + 1], "30")

    def test_quemar_subtitulos_apunta_al_srt_recibido(self):
        argumentos = video_montaje.args_quemar(
            "entrada.mp4", "subtitulos.srt", "salida.mp4")
        self.assertIn("subtitulos.srt", " ".join(argumentos))


class TestSubtitulos(unittest.TestCase):

    def test_textos_clave(self):
        self.assertEqual(
            video_montaje.SUBTITULOS[2],
            "Google's sign-in screen: we pick the account and pass the "
            "unverified app warning.")
        self.assertEqual(
            video_montaje.SUBTITULOS[3],
            "The consent screen. The OAuth client ID is in the address bar. "
            "We grant the youtube.force-ssl scope.")
        self.assertEqual(
            video_montaje.SUBTITULOS[5],
            "OBS sends the video in the background. The broadcast is live.")
        self.assertEqual(video_montaje.SUBTITULOS[11], "The app is signed in.")

    def test_cada_paso_del_1_al_10_aparece_en_el_srt(self):
        pasos = [{"inicio": n * 10, "fin": n * 10 + 5,
                  "texto": video_montaje.SUBTITULOS[n]}
                 for n in range(1, 11)]
        srt = video_montaje.armar_srt(pasos)
        for numero in range(1, 11):
            self.assertIn(video_montaje.SUBTITULOS[numero], srt)


class TestDesplazamientoClientId(unittest.TestCase):

    def test_llega_al_comienzo_de_client_id(self):
        valor = ("https://accounts.google.com/o/oauth2/auth?scope=x"
                 "&client_id=626044875401-abc.apps.googleusercontent.com"
                 "&rapt=XYZ")
        desplazamiento = video_demo.video_consentimiento.desplazamiento_client_id(
            valor)
        self.assertEqual(
            desplazamiento,
            len(valor) - valor.index("client_id=") + 15)


class TestCoincide(unittest.TestCase):

    def test_rechaza_texto_mas_largo_y_acepta_mayusculas(self):
        coincide = video_demo.video_consentimiento.coincide
        self.assertFalse(coincide("to continue to", "Continue"))
        self.assertTrue(coincide("CONTINUE", "Continue"))
        self.assertTrue(coincide("  continue  ", "Continue"))
        self.assertTrue(coincide("Google hasn’t verified",
                                 "Google hasn't verified"))


class TestPerfilChrome(unittest.TestCase):

    def test_marca_el_perfil_como_cerrado_bien(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "User Data"
            perfil = user / "Profile 1"
            perfil.mkdir(parents=True)
            local = user / "Local State"
            local.write_text(
                json.dumps({"profile": {"last_used": "Profile 1"}}),
                encoding="utf-8")
            prefs = perfil / "Preferences"
            prefs.write_text(
                json.dumps({"profile": {"exit_type": "Crashed",
                                        "exited_cleanly": False},
                            "otra": 1}),
                encoding="utf-8")
            self.assertTrue(
                video_demo.video_chrome.corregir_perfil(local))
            datos = json.loads(prefs.read_text(encoding="utf-8"))
            self.assertEqual(datos["profile"]["exit_type"], "Normal")
            self.assertTrue(datos["profile"]["exited_cleanly"])
            self.assertEqual(datos["otra"], 1)


class TestPermiso(unittest.TestCase):

    def test_con_linea_se_muestra(self):
        self.assertEqual(
            video_demo.video_consentimiento.decidir_permiso(True, []),
            "mostrar")

    def test_sin_linea_pero_ya_dado_avisa(self):
        decidir = video_demo.video_consentimiento.decidir_permiso
        self.assertEqual(
            decidir(False, ["Guyrapu already has some access"]), "aviso")
        self.assertEqual(decidir(False, ["Guyrapu ya tiene acceso"]), "aviso")


class TestRevocarToken(unittest.TestCase):

    def test_prefiere_refresh_y_cae_al_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            programa = Path(tmp)
            (programa / "data").mkdir()
            ruta = programa / "data" / "credenciales.json"
            ruta.write_text(json.dumps({
                "token": json.dumps({"refresh_token": "R", "token": "A"})}),
                encoding="utf-8")
            with mock.patch("urllib.request.urlopen") as abrir:
                video_demo.video_consentimiento.revocar_token(str(programa))
            solicitud = abrir.call_args.args[0]
            self.assertEqual(solicitud.full_url,
                             "https://oauth2.googleapis.com/revoke")
            self.assertIn(b"token=R", solicitud.data)
            ruta.write_text(json.dumps({
                "token": json.dumps({"token": "A"})}), encoding="utf-8")
            with mock.patch("urllib.request.urlopen") as abrir:
                video_demo.video_consentimiento.revocar_token(str(programa))
            self.assertIn(b"token=A", abrir.call_args.args[0].data)


if __name__ == "__main__":
    unittest.main()

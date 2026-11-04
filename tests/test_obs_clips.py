"""Pruebas del búfer de repetición de OBS, sin wx y sin OBS real.

Lo puro decide con estados enlatados; lo demás habla con un doble que
responde como el websocket de OBS.
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from bellbird.obs import obs_cliente, obs_clips, obs_lanzador


class ObsFalso:
    """Doble del cliente de OBS con parámetros de perfil y búfer."""

    def __init__(self, modo="Simple", calidad="HQ", codificador="x264",
                 transmitiendo=False, grabando=False, buffer=False,
                 perfil="Principal", perfiles=("Principal", "Otro"),
                 rutas=None):
        self.modo = modo
        self.calidad = calidad
        self.codificador = codificador
        self.transmitiendo = transmitiendo
        self.grabando = grabando
        self.buffer = buffer
        self.perfil = perfil
        self.perfiles = list(perfiles)
        self.parametros = {}
        self.rutas = list(rutas if rutas is not None else ["C:/clips/clip.mkv"])
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        datos = dict(datos or {})
        self.llamadas.append((tipo, datos))
        if tipo == "GetStreamStatus":
            return {"outputActive": self.transmitiendo}
        if tipo == "GetRecordStatus":
            return {"outputActive": self.grabando}
        if tipo == "GetReplayBufferStatus":
            return {"outputActive": self.buffer}
        if tipo == "GetProfileList":
            return {"responseData": {"currentProfileName": self.perfil,
                                     "profiles": list(self.perfiles)}}
        if tipo == "GetProfileParameter":
            categoria = datos["parameterCategory"]
            nombre = datos["parameterName"]
            if (categoria, nombre) == ("Output", "Mode"):
                valor = self.modo
            elif nombre == "RecQuality":
                valor = self.calidad
            elif nombre == "RecEncoder":
                valor = self.codificador
            else:
                valor = self.parametros.get((categoria, nombre), "")
            return {"responseData": {"parameterValue": valor,
                                     "defaultParameterValue": valor}}
        if tipo == "SetProfileParameter":
            self.parametros[(datos["parameterCategory"],
                             datos["parameterName"])] = datos["parameterValue"]
            return {}
        if tipo == "StartReplayBuffer":
            self.buffer = True
            return {}
        if tipo == "SaveReplayBuffer":
            return {}
        if tipo == "GetLastReplayBufferReplay":
            ruta = self.rutas.pop(0) if len(self.rutas) > 1 else self.rutas[0]
            return {"responseData": {"savedReplayPath": ruta}}
        if tipo == "SetCurrentProfile":
            self.perfil = datos.get("profileName", self.perfil)
            return {}
        if tipo in ("CreateProfile", "RemoveProfile"):
            return {}
        return {}

    def tipos(self):
        return [tipo for tipo, _datos in self.llamadas]


class Reloj:
    def __init__(self):
        self.ahora = 0.0

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.ahora += segundos


class DecisionTest(unittest.TestCase):

    def test_cubre_las_ocho_combinaciones(self):
        casos = (
            (False, True, False, obs_clips.GUARDAR),
            (False, True, True, obs_clips.GUARDAR),
            (True, True, False, obs_clips.GUARDAR),
            (True, True, True, obs_clips.GUARDAR),
            (False, False, False, obs_clips.PREPARAR),
            (False, False, True, obs_clips.INICIAR),
            (True, False, False, obs_clips.RECHAZAR),
            (True, False, True, obs_clips.INICIAR),
        )
        for salida, buffer, preparado, esperado in casos:
            with self.subTest(salida=salida, buffer=buffer,
                              preparado=preparado):
                self.assertEqual(
                    obs_clips.decidir(salida, buffer, preparado), esperado)


class SoporteTest(unittest.TestCase):

    def test_tabla_del_perfil(self):
        casos = (
            ("Simple", "HQ", "", True),
            ("Simple", "Lossless", "", False),
            ("Advanced", "", "x264", True),
            ("Advanced", "", "ffmpeg", False),
            ("", "", "", False),
        )
        for modo, calidad, codificador, esperado in casos:
            with self.subTest(modo=modo, calidad=calidad,
                              codificador=codificador):
                self.assertIs(obs_clips.soporta_buffer(
                    modo, calidad, codificador), esperado)


class LeerSegundosTest(unittest.TestCase):

    def _leer(self, contenido):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            ruta.write_text(contenido, encoding="utf-8")
            return obs_clips.leer_segundos(ruta)

    def test_valores_validos(self):
        self.assertEqual(
            self._leer("[transmision]\nclips = 60\n"), 60)
        self.assertEqual(
            self._leer("[transmision]\nclips = 0\n"), 0)

    def test_valor_desconocido_cae_a_treinta(self):
        self.assertEqual(
            self._leer("[transmision]\nclips = 45\n"), 30)

    def test_sin_la_clave_cae_a_treinta(self):
        self.assertEqual(self._leer("[transmision]\n"), 30)


class LeerEstadoTest(unittest.TestCase):

    def test_perfil_simple_preparado_con_la_duracion(self):
        cliente = ObsFalso(modo="Simple", buffer=False)
        cliente.parametros[("SimpleOutput", "RecRB")] = "true"
        cliente.parametros[("SimpleOutput", "RecRBTime")] = "30"
        estado = obs_clips.leer_estado(cliente, 30)
        self.assertTrue(estado.conocido)
        self.assertTrue(estado.soportado)
        self.assertTrue(estado.preparado)
        self.assertFalse(estado.buffer_activo)
        self.assertFalse(estado.salida_activa)

    def test_otra_duracion_no_cuenta_como_preparado(self):
        cliente = ObsFalso(modo="Simple")
        cliente.parametros[("SimpleOutput", "RecRB")] = "true"
        cliente.parametros[("SimpleOutput", "RecRBTime")] = "60"
        self.assertFalse(obs_clips.leer_estado(cliente, 30).preparado)

    def test_grabar_o_transmitir_cuentan_como_salida_activa(self):
        for transmitiendo, grabando in ((True, False), (False, True)):
            with self.subTest(transmitiendo=transmitiendo,
                              grabando=grabando):
                cliente = ObsFalso(transmitiendo=transmitiendo,
                                   grabando=grabando)
                self.assertTrue(obs_clips.leer_estado(cliente, 30).salida_activa)

    def test_modo_desconocido_no_esta_preparado(self):
        cliente = ObsFalso(modo="Otro")
        estado = obs_clips.leer_estado(cliente, 30)
        self.assertFalse(estado.conocido)
        self.assertFalse(estado.soportado)
        self.assertFalse(estado.preparado)


class PrepararTest(unittest.TestCase):

    def test_cambia_los_dos_parametros_y_vuelve_de_perfil(self):
        cliente = ObsFalso(perfiles=("Principal", "Otro"))
        obs_clips.preparar(cliente, 30)
        self.assertEqual(
            cliente.parametros[("SimpleOutput", "RecRB")], "true")
        self.assertEqual(
            cliente.parametros[("SimpleOutput", "RecRBTime")], "30")
        self.assertEqual(
            [datos for tipo, datos in cliente.llamadas
             if tipo == "SetCurrentProfile"],
            [{"profileName": "Otro"}, {"profileName": "Principal"}])
        self.assertNotIn("CreateProfile", cliente.tipos())
        self.assertNotIn("RemoveProfile", cliente.tipos())
        self.assertTrue(cliente.buffer)

    def test_en_avanzado_usa_adv_out(self):
        cliente = ObsFalso(modo="Advanced", codificador="x264")
        obs_clips.preparar(cliente, 60)
        self.assertEqual(
            cliente.parametros[("AdvOut", "RecRBTime")], "60")

    def test_si_es_el_unico_perfil_crea_y_borra_uno_temporal(self):
        cliente = ObsFalso(perfiles=("Principal",))
        obs_clips.preparar(cliente, 30)
        creados = [datos["profileName"] for tipo, datos in cliente.llamadas
                   if tipo == "CreateProfile"]
        self.assertEqual(len(creados), 1)
        self.assertTrue(creados[0].startswith("Bellbird"))
        self.assertIn(("SetCurrentProfile", {"profileName": creados[0]}),
                      cliente.llamadas)
        self.assertIn(("RemoveProfile", {"profileName": creados[0]}),
                      cliente.llamadas)
        self.assertEqual(cliente.perfil, "Principal")

    def test_no_prepara_con_una_salida_activa(self):
        cliente = ObsFalso(transmitiendo=True)
        with self.assertRaises(obs_cliente.ObsError):
            obs_clips.preparar(cliente, 30)
        self.assertNotIn("SetProfileParameter", cliente.tipos())
        self.assertFalse(cliente.buffer)

    def test_calidad_sin_perdidas_no_se_prepara(self):
        cliente = ObsFalso(calidad="Lossless")
        with self.assertRaises(obs_cliente.ObsError):
            obs_clips.preparar(cliente, 30)
        self.assertNotIn("SetProfileParameter", cliente.tipos())


class GuardarTest(unittest.TestCase):

    def test_espera_a_que_obs_devuelva_la_ruta(self):
        cliente = ObsFalso(rutas=["", "", "C:/clips/clip.mkv"])
        reloj = Reloj()
        ruta = obs_clips.guardar(cliente, dormir=reloj.dormir,
                                 reloj=reloj, intervalo=0.2, limite=1.0)
        self.assertEqual(ruta, "C:/clips/clip.mkv")
        self.assertIn("SaveReplayBuffer", cliente.tipos())
        self.assertGreaterEqual(reloj.ahora, 0.2)

    def test_sin_ruta_a_tiempo_falla(self):
        cliente = ObsFalso(rutas=[""])
        reloj = Reloj()
        with self.assertRaises(obs_cliente.ObsError):
            obs_clips.guardar(cliente, dormir=reloj.dormir, reloj=reloj,
                              intervalo=0.2, limite=0.5)


class PrepararParaDirectoTest(unittest.TestCase):

    def test_sin_bufer_avisa_y_prepara(self):
        cliente = ObsFalso()
        avisos = []
        resultado = obs_clips.preparar_para_directo(
            cliente, 30, al_preparar=lambda: avisos.append("preparando"),
            al_fallar=avisos.append)
        self.assertEqual(resultado, "preparado")
        self.assertEqual(avisos, ["preparando"])
        self.assertTrue(cliente.buffer)

    def test_perfil_ya_preparado_solo_pone_en_marcha(self):
        cliente = ObsFalso()
        cliente.parametros[("SimpleOutput", "RecRB")] = "true"
        cliente.parametros[("SimpleOutput", "RecRBTime")] = "30"
        avisos = []
        resultado = obs_clips.preparar_para_directo(
            cliente, 30, al_preparar=lambda: avisos.append("preparando"),
            al_fallar=avisos.append)
        self.assertEqual(resultado, "listo")
        self.assertEqual(avisos, [])
        self.assertTrue(cliente.buffer)
        self.assertNotIn("SetProfileParameter", cliente.tipos())

    def test_calidad_sin_perdidas_avisa_y_no_toca_el_perfil(self):
        cliente = ObsFalso(calidad="Lossless")
        errores = []
        resultado = obs_clips.preparar_para_directo(
            cliente, 30, al_fallar=errores.append)
        self.assertEqual(resultado, "no_disponible")
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], obs_cliente.ObsError)
        self.assertNotIn("SetProfileParameter", cliente.tipos())
        self.assertFalse(cliente.buffer)

    def test_con_salida_activa_y_sin_preparar_no_cambia_el_perfil(self):
        cliente = ObsFalso(transmitiendo=True)
        errores = []
        resultado = obs_clips.preparar_para_directo(
            cliente, 30, al_fallar=errores.append)
        self.assertEqual(resultado, "no_preparado")
        self.assertEqual(len(errores), 1)
        self.assertNotIn("SetProfileParameter", cliente.tipos())
        self.assertFalse(cliente.buffer)

    def test_modo_desconocido_no_hace_nada_ni_avisa(self):
        cliente = ObsFalso(modo="")
        avisos = []
        resultado = obs_clips.preparar_para_directo(
            cliente, 30, al_preparar=lambda: avisos.append("preparando"),
            al_fallar=avisos.append)
        self.assertEqual(resultado, "sin_datos")
        self.assertEqual(avisos, [])
        self.assertFalse(cliente.buffer)

    def test_desactivado_no_consulta_obs(self):
        cliente = ObsFalso()
        self.assertEqual(
            obs_clips.preparar_para_directo(cliente, 0), "desactivado")
        self.assertEqual(cliente.llamadas, [])


def _cargar_conducir():
    ruta = Path(__file__).resolve().parent.parent / "qa" / "conducir.py"
    especificacion = importlib.util.spec_from_file_location(
        "conducir_obs_clips", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


@unittest.skipUnless(os.environ.get("BELLBIRD_PRUEBAS_CON_RED") == "1",
                     "habla con el OBS real")
class ObsRealTest(unittest.TestCase):
    """Prepara el búfer, guarda un clip y deja el perfil como estaba."""

    def setUp(self):
        self.conducir = _cargar_conducir()
        self.estaba_abierto = self.conducir.obs_abierto()
        self.cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        obs_lanzador.asegurar_obs(self._probar, limite=120.0)
        self.cliente.conectar()
        self.modo = obs_clips._parametro(self.cliente, "Output", "Mode")
        self.categoria = obs_clips._CATEGORIAS.get(self.modo, "")
        self.rb = self.rb_time = ""
        if self.categoria:
            self.rb = obs_clips._parametro(
                self.cliente, self.categoria, "RecRB")
            self.rb_time = obs_clips._parametro(
                self.cliente, self.categoria, "RecRBTime")
        self.buffer_inicial = bool(obs_clips._datos(
            self.cliente.pedir("GetReplayBufferStatus")).get("outputActive"))

    def _probar(self):
        self.cliente.conectar()
        self.cliente.cerrar()

    def tearDown(self):
        try:
            if not self.buffer_inicial:
                try:
                    self.cliente.pedir("StopReplayBuffer")
                except Exception:
                    pass
            if self.categoria:
                for nombre, valor in (("RecRB", self.rb),
                                      ("RecRBTime", self.rb_time)):
                    self.cliente.pedir("SetProfileParameter", {
                        "parameterCategory": self.categoria,
                        "parameterName": nombre,
                        "parameterValue": valor})
                obs_clips._cambiar_y_volver(self.cliente)
        finally:
            self.cliente.cerrar()
            if not self.estaba_abierto:
                self.conducir.cerrar_obs_del_banco(
                    self.conducir.Resultado())

    def test_prepara_guarda_un_clip_y_restaura_el_perfil(self):
        obs_clips.preparar(self.cliente, 30)
        ruta = obs_clips.guardar(self.cliente)
        archivo = Path(ruta)
        self.addCleanup(lambda: archivo.unlink(missing_ok=True))
        self.assertTrue(archivo.is_file(), ruta)


if __name__ == "__main__":
    unittest.main()

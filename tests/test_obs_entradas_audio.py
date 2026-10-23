import unittest

from ytchat.obs import obs_entradas_audio
from ytchat.obs import dispositivo_windows


class DobleCliente:
    def __init__(self, entradas=(), silencios=None, ajustes=None,
                 propiedades=None):
        self.entradas = list(entradas)
        self.silencios = dict(silencios or {})
        self.ajustes = dict(ajustes or {})
        self.propiedades = dict(propiedades or {})
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        datos = datos or {}
        self.llamadas.append((tipo, datos, parada))
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetInputMute":
            nombre = datos["inputName"]
            if nombre not in self.silencios:
                raise RuntimeError("No es una fuente de audio")
            return {"responseData": {"inputMuted": self.silencios[nombre]}}
        if tipo == "ToggleInputMute":
            nombre = datos["inputName"]
            self.silencios[nombre] = not self.silencios[nombre]
            return {"responseData": {"inputMuted": self.silencios[nombre]}}
        if tipo == "GetInputSettings":
            return {"responseData": dict(self.ajustes)}
        if tipo == "GetInputPropertiesListPropertyItems":
            return {"responseData": {
                "propertyItems": list(self.propiedades.get(
                    datos.get("propertyName"), ()))}}
        return {"responseData": {}}


class DobleGestor:
    def __init__(self, fuentes=(), silencio=False, dispositivo=("", False)):
        self.fuentes = tuple(fuentes)
        self.silencio = silencio
        self.dispositivo_resultado = dispositivo
        self.alternadas = []
        self.consultas = []

    def fuentes_audio(self, parada=None):
        return self.fuentes

    def alternar_silencio(self, fuente, parada=None):
        self.alternadas.append(fuente)
        return self.silencio

    def dispositivo(self, fuente, predeterminado, parada=None):
        self.consultas.append((fuente, predeterminado))
        if isinstance(self.dispositivo_resultado, Exception):
            raise self.dispositivo_resultado
        return self.dispositivo_resultado


class FuentesAudioTest(unittest.TestCase):
    def test_descarta_las_entradas_sin_nombre_y_las_que_obs_no_silencia(self):
        cliente = DobleCliente(
            entradas=({"inputName": "Mic/Aux"}, {"inputName": ""},
                      {"inputName": "Cámara"}),
            silencios={"Mic/Aux": False})
        self.assertEqual(obs_entradas_audio.fuentes_audio(cliente), ("Mic/Aux",))

    def test_conserva_el_orden_de_obs(self):
        cliente = DobleCliente(
            entradas=({"inputName": "Audio USB"}, {"inputName": "Mic/Aux"}),
            silencios={"Audio USB": True, "Mic/Aux": False})
        self.assertEqual(obs_entradas_audio.fuentes_audio(cliente),
                         ("Audio USB", "Mic/Aux"))


class SilencioTest(unittest.TestCase):
    def test_consulta_el_silencio_de_una_fuente(self):
        cliente = DobleCliente(silencios={"Mic/Aux": True})
        self.assertTrue(obs_entradas_audio.silenciada(cliente, "Mic/Aux"))

    def test_alterna_el_silencio_y_devuelve_el_estado_resultante(self):
        cliente = DobleCliente(silencios={"Mic/Aux": False})
        self.assertTrue(obs_entradas_audio.alternar_silencio(cliente, "Mic/Aux"))
        self.assertTrue(cliente.silencios["Mic/Aux"])


class AlternarMicrofonoTest(unittest.TestCase):
    def test_elige_el_preferido_y_anuncia_su_estado(self):
        gestor = DobleGestor(fuentes=("Mic/Aux", "Audio USB"), silencio=True)
        self.assertEqual(
            obs_entradas_audio.alternar_microfono(gestor, "Audio USB"),
            "Audio USB silenciado")
        self.assertEqual(gestor.alternadas, ["Audio USB"])

    def test_sin_fuentes_anuncia_la_ausencia_y_no_alterna(self):
        gestor = DobleGestor()
        self.assertEqual(obs_entradas_audio.alternar_microfono(gestor, ""),
                         "OBS no tiene ninguna fuente de audio")
        self.assertEqual(gestor.alternadas, [])

    def test_activado_nombra_el_dispositivo_y_consulta_el_predeterminado(self):
        gestor = DobleGestor(fuentes=("Mic/Aux",), silencio=False,
                             dispositivo=("Micrófono (WO Mic Device)", False))
        self.assertEqual(
            obs_entradas_audio.alternar_microfono(gestor, "Mic/Aux"),
            "Micrófono activado: WO Mic Device")
        self.assertEqual(gestor.consultas[0][0], "Mic/Aux")
        self.assertIs(gestor.consultas[0][1],
                      dispositivo_windows.microfono_predeterminado)

    def test_silenciado_no_consulta_el_dispositivo(self):
        gestor = DobleGestor(fuentes=("Mic/Aux",), silencio=True,
                             dispositivo=("Micrófono (WO Mic Device)", False))
        self.assertEqual(obs_entradas_audio.alternar_microfono(gestor, "Mic/Aux"),
                         "Micrófono silenciado")
        self.assertEqual(gestor.consultas, [])

    def test_si_la_consulta_del_dispositivo_lanza_anuncia_como_hoy(self):
        gestor = DobleGestor(fuentes=("Mic/Aux",), silencio=False,
                             dispositivo=RuntimeError("sin COM"))
        self.assertEqual(obs_entradas_audio.alternar_microfono(gestor, "Mic/Aux"),
                         "Micrófono activado")


class DispositivoTest(unittest.TestCase):
    def test_una_entrada_que_no_es_de_microfono_no_tiene_dispositivo(self):
        cliente = DobleCliente(ajustes={"inputKind": "browser_source",
                                        "inputSettings": {}})
        self.assertEqual(
            obs_entradas_audio.dispositivo(cliente, "Chat", lambda: "Windows"),
            ("", False))

    def test_el_dispositivo_predeterminado_se_nombra_con_el_de_windows(self):
        cliente = DobleCliente(ajustes={
            "inputKind": "wasapi_input_capture",
            "inputSettings": {"device_id": "default"}})
        self.assertEqual(
            obs_entradas_audio.dispositivo(cliente, "Mic/Aux", lambda: "Windows"),
            ("Windows", True))

    def test_sin_device_id_se_toma_el_predeterminado(self):
        cliente = DobleCliente(ajustes={
            "inputKind": "wasapi_input_capture", "inputSettings": {}})
        self.assertEqual(
            obs_entradas_audio.dispositivo(cliente, "Mic/Aux", lambda: "Windows"),
            ("Windows", True))

    def test_un_device_id_concreto_busca_su_nombre_en_la_lista(self):
        cliente = DobleCliente(
            ajustes={"inputKind": "wasapi_input_capture",
                     "inputSettings": {"device_id": "{mic-2}"}},
            propiedades={"device_id": (
                {"itemName": "Micrófono (WO Mic Device)", "itemValue": "{mic-1}"},
                {"itemName": "Micrófono (USB)", "itemValue": "{mic-2}"})})
        self.assertEqual(
            obs_entradas_audio.dispositivo(cliente, "Mic/Aux", lambda: "Windows"),
            ("Micrófono (USB)", False))

    def test_un_device_id_que_no_esta_en_la_lista_devuelve_vacio(self):
        cliente = DobleCliente(
            ajustes={"inputKind": "wasapi_input_capture",
                     "inputSettings": {"device_id": "{mic-9}"}},
            propiedades={"device_id": (
                {"itemName": "Micrófono (USB)", "itemValue": "{mic-2}"},)})
        self.assertEqual(
            obs_entradas_audio.dispositivo(cliente, "Mic/Aux", lambda: "Windows"),
            ("", False))


if __name__ == "__main__":
    unittest.main()

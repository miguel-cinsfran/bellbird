import unittest

from ytchat.obs import obs_entradas_audio


class DobleCliente:
    def __init__(self, entradas=(), silencios=None):
        self.entradas = list(entradas)
        self.silencios = dict(silencios or {})
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
        return {"responseData": {}}


class DobleGestor:
    def __init__(self, fuentes=(), silencio=False):
        self.fuentes = tuple(fuentes)
        self.silencio = silencio
        self.alternadas = []

    def fuentes_audio(self, parada=None):
        return self.fuentes

    def alternar_silencio(self, fuente, parada=None):
        self.alternadas.append(fuente)
        return self.silencio


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


if __name__ == "__main__":
    unittest.main()

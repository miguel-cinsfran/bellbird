import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from ytchat.obs import obs_audio
from ytchat.obs import obs_entradas_audio
from ytchat.obs import dispositivo_windows

TEXTO_SIN_SENAL = ("El micrófono no recibe sonido. Revisa cuál está elegido "
                   "en Windows o en OBS.")


ENTRADAS_MANU = (
    {"inputName": "Audio del escritorio", "inputKind": "wasapi_output_capture",
     "inputKindCaps": 642},
    {"inputName": "Mic/Aux", "inputKind": "wasapi_input_capture",
     "inputKindCaps": 130},
    {"inputName": "Captura de pantalla", "inputKind": "monitor_capture",
     "inputKindCaps": 32905},
    {"inputName": "Captura de ventana", "inputKind": "window_capture",
     "inputKindCaps": 32779},
)


class DobleCliente:
    def __init__(self, entradas=(), silencios=None, ajustes=None,
                 propiedades=None, especial="Mic/Aux",
                 fallo_especial=False):
        self.entradas = list(entradas)
        self.silencios = dict(silencios or {})
        self.ajustes = dict(ajustes or {})
        self.propiedades = dict(propiedades or {})
        self.especial = especial
        self.fallo_especial = fallo_especial
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        datos = datos or {}
        self.llamadas.append((tipo, datos, parada))
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetSpecialInputs":
            if self.fallo_especial:
                raise RuntimeError("sin especiales")
            if self.especial:
                return {"responseData": {"mic1": self.especial}}
            return {"responseData": {}}
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
    def __init__(self, entradas=(), especial="", silencio=False,
                 dispositivo=("", False), fuentes=()):
        self.entradas = tuple(entradas)
        self.especial = especial
        if not entradas and fuentes:
            self.entradas = tuple((nombre, "") for nombre in fuentes)
        self.silencio = silencio
        self.dispositivo_resultado = dispositivo
        self.alternadas = []
        self.consultas = []
        self.silencios = {}
        self.conectado = False
        self.cerrado = False

    def conectar(self, parada=None):
        self.conectado = True

    def cerrar(self):
        self.cerrado = True

    def fuentes_audio(self, parada=None):
        return tuple(nombre for nombre, _tipo in self.entradas)

    def entradas_audio(self, parada=None):
        return self.entradas

    def microfono_especial(self, parada=None):
        return self.especial

    def silenciada(self, fuente, parada=None):
        return self.silencios.get(fuente, False)

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


class EntradasAudioTest(unittest.TestCase):
    def test_con_la_lista_de_manu_devuelve_los_pares_con_audio(self):
        cliente = DobleCliente(entradas=ENTRADAS_MANU)
        pares = obs_entradas_audio.entradas_audio(cliente)
        nombres = [nombre for nombre, _tipo in pares]
        self.assertIn("Audio del escritorio", nombres)
        self.assertIn("Mic/Aux", nombres)
        self.assertNotIn("Captura de pantalla", nombres)
        tipos = dict(pares)
        self.assertEqual(tipos["Mic/Aux"], "wasapi_input_capture")

    def test_no_hace_ninguna_peticion_getinputmute(self):
        cliente = DobleCliente(entradas=ENTRADAS_MANU)
        obs_entradas_audio.entradas_audio(cliente)
        tipos = [llamada[0] for llamada in cliente.llamadas]
        self.assertEqual(tipos, ["GetInputList"])
        self.assertNotIn("GetInputMute", tipos)

    def test_sin_caps_entra_igual_por_obs_viejo(self):
        cliente = DobleCliente(
            entradas=({"inputName": "Mic/Aux", "inputKind": "wasapi_input_capture"},))
        self.assertEqual(obs_entradas_audio.entradas_audio(cliente),
                         (("Mic/Aux", "wasapi_input_capture"),))


class MicrofonoEspecialTest(unittest.TestCase):
    def test_devuelve_el_mic1_de_getspecialinputs(self):
        cliente = DobleCliente(especial="Mic/Aux")
        self.assertEqual(obs_entradas_audio.microfono_especial(cliente), "Mic/Aux")

    def test_sin_mic1_da_vacio(self):
        cliente = DobleCliente(especial="")
        self.assertEqual(obs_entradas_audio.microfono_especial(cliente), "")

    def test_si_la_peticion_falla_da_vacio(self):
        cliente = DobleCliente(fallo_especial=True)
        self.assertEqual(obs_entradas_audio.microfono_especial(cliente), "")


class AlternarMicrofonoTest(unittest.TestCase):
    AVISO_SIN_MICROFONO = ("OBS no tiene ningún micrófono. Elige uno en "
                           "Preferencias, página Transmisión, Micrófono de OBS.")

    def test_elige_el_preferido_y_anuncia_su_estado(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),
                      ("Audio USB", "wasapi_input_capture")),
            silencio=True, dispositivo=("Micrófono (USB)", False))
        texto, fuente, estado = obs_entradas_audio.alternar_microfono(
            gestor, "Audio USB")
        self.assertEqual((fuente, estado), ("Audio USB", True))
        self.assertEqual(texto, "Audio USB silenciado")
        self.assertEqual(gestor.alternadas, ["Audio USB"])

    def test_sin_fuentes_anuncia_la_ausencia_y_no_alterna(self):
        gestor = DobleGestor()
        self.assertEqual(obs_entradas_audio.alternar_microfono(gestor, ""),
                         (self.AVISO_SIN_MICROFONO, "", False))
        self.assertEqual(gestor.alternadas, [])

    def test_con_solo_audio_del_escritorio_da_vacio_y_no_alterna(self):
        gestor = DobleGestor(
            entradas=(("Audio del escritorio", "wasapi_output_capture"),))
        self.assertEqual(obs_entradas_audio.alternar_microfono(gestor, ""),
                         (self.AVISO_SIN_MICROFONO, "", False))
        self.assertEqual(gestor.alternadas, [])

    def test_con_la_lista_de_manu_sin_preferido_elige_mic_aux(self):
        pares = (("Audio del escritorio", "wasapi_output_capture"),
                 ("Mic/Aux", "wasapi_input_capture"))
        gestor = DobleGestor(entradas=pares, especial="Mic/Aux",
                             silencio=False,
                             dispositivo=("Micrófono (USB)", False))
        texto, fuente, estado = obs_entradas_audio.alternar_microfono(
            gestor, "")
        self.assertEqual((fuente, estado), ("Mic/Aux", False))
        self.assertEqual(texto, "Micrófono activado: USB")

    def test_activado_nombra_el_dispositivo_y_consulta_el_predeterminado(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=False,
            dispositivo=("Micrófono (WO Mic Device)", False))
        self.assertEqual(
            obs_entradas_audio.alternar_microfono(gestor, "Mic/Aux"),
            ("Micrófono activado: WO Mic Device", "Mic/Aux", False))
        self.assertEqual(gestor.consultas[0][0], "Mic/Aux")
        self.assertIs(gestor.consultas[0][1],
                      dispositivo_windows.microfono_predeterminado)

    def test_silenciado_tambien_nombra_el_dispositivo(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=True,
            dispositivo=("Micrófono (WO Mic Device)", False))
        self.assertEqual(
            obs_entradas_audio.alternar_microfono(gestor, "Mic/Aux"),
            ("Micrófono silenciado: WO Mic Device", "Mic/Aux", True))
        self.assertEqual(len(gestor.consultas), 1)

    def test_si_la_consulta_del_dispositivo_lanza_anuncia_como_hoy(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=False,
            dispositivo=RuntimeError("sin COM"))
        self.assertEqual(obs_entradas_audio.alternar_microfono(gestor, "Mic/Aux"),
                         ("Micrófono activado", "Mic/Aux", False))


class ClienteSenal:
    """Cliente doble para la medición de la señal del micrófono."""
    def __init__(self, eventos=None, fallo_conectar=None, fallo_escuchar=None):
        self.eventos = list(eventos or [])
        self.fallo_conectar = fallo_conectar
        self.fallo_escuchar = fallo_escuchar
        self.conectado = False
        self.escuchado = None
        self.cerrado = False

    def conectar(self, parada=None):
        if self.fallo_conectar:
            raise self.fallo_conectar
        self.conectado = True

    def escuchar(self, tipo, segundos, parada=None):
        self.escuchado = (tipo, segundos)
        if self.fallo_escuchar:
            raise self.fallo_escuchar
        return self.eventos

    def cerrar(self):
        self.cerrado = True


class SenalMicrofonoTest(unittest.TestCase):
    def _medir(self, cliente, fuente="Mic/Aux", segundos=None):
        args = (segundos,) if segundos is not None else ()
        return obs_entradas_audio.senal_microfono(
            fuente, *args, crear_cliente=lambda: cliente)

    def test_escucha_el_medidor_y_encuentra_senal(self):
        cliente = ClienteSenal(eventos=[{"inputs": [
            {"inputName": "Mic/Aux", "inputLevelsMul": [[0.0, 0.02, 0.049]]}]}])
        self.assertIs(self._medir(cliente), True)
        self.assertTrue(cliente.conectado)
        self.assertEqual(cliente.escuchado, ("InputVolumeMeters", 3.0))
        self.assertTrue(cliente.cerrado)

    def test_cero_niveles_es_sin_senal(self):
        cliente = ClienteSenal(eventos=[{"inputs": [
            {"inputName": "Mic/Aux", "inputLevelsMul": [[0.0, 0.0, 0.0]]}]}])
        self.assertIs(self._medir(cliente), False)
        self.assertTrue(cliente.cerrado)

    def test_otros_eventos_tambien_devuelven_ninguna(self):
        cliente = ClienteSenal(eventos=[{"inputs": [
            {"inputName": "Otro", "inputLevelsMul": [[0.9, 0.9, 0.9]]}]}])
        self.assertIsNone(self._medir(cliente))
        self.assertTrue(cliente.cerrado)

    def test_un_fallo_al_conectar_es_que_no_se_pudo_medir(self):
        cliente = ClienteSenal(fallo_conectar=RuntimeError("sin OBS"))
        self.assertIsNone(self._medir(cliente))
        self.assertTrue(cliente.cerrado)

    def test_un_fallo_al_escuchar_es_que_no_se_pudo_medir(self):
        cliente = ClienteSenal(fallo_escuchar=RuntimeError("colgado"))
        self.assertIsNone(self._medir(cliente))
        self.assertTrue(cliente.cerrado)

    def test_respeta_los_segundos_pedidos(self):
        cliente = ClienteSenal()
        self._medir(cliente, segundos=5.0)
        self.assertEqual(cliente.escuchado, ("InputVolumeMeters", 5.0))


class MicrofonoPorAtajoTest(unittest.TestCase):
    def _ejecutar(self, gestor, preferido="Mic/Aux", senal=None,
                  al_estado=None):
        avisos = []
        estados = []
        def _al_estado(estado):
            estados.append(estado)
            if al_estado is not None:
                al_estado(estado)
        with mock.patch("ytchat.obs.obs_panel.GestorPanelObs",
                        return_value=gestor) as clase, \
                mock.patch.object(obs_entradas_audio, "senal_microfono",
                                  return_value=senal) as medicion:
            obs_entradas_audio.microfono_por_atajo(
                preferido, lambda *args: avisos.append(args),
                al_estado=_al_estado)
        return clase, avisos, medicion, estados

    def test_activado_sin_senal_avisa_dos_veces_en_orden_y_con_sonido(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=False,
            dispositivo=("Micrófono (USB)", False))
        clase, avisos, medicion, estados = self._ejecutar(gestor, senal=False)
        self.assertEqual(avisos, [
            ("Micrófono activado: USB", ""),
            (TEXTO_SIN_SENAL, "microfono_sin_senal")])
        medicion.assert_called_once_with("Mic/Aux")
        self.assertTrue(gestor.cerrado)

    def test_activado_con_senal_avisa_una_sola_vez(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=False,
            dispositivo=("Micrófono (USB)", False))
        _, avisos, medicion, _ = self._ejecutar(gestor, senal=True)
        self.assertEqual(avisos, [("Micrófono activado: USB", "")])
        self.assertTrue(medicion.called)

    def test_silenciado_no_mide(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=True)
        _, avisos, medicion, _ = self._ejecutar(gestor, senal=None)
        self.assertEqual(avisos, [("Micrófono silenciado", "")])
        medicion.assert_not_called()

    def test_con_la_medicion_inalcanzable_no_avisa_nada_mas(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=False,
            dispositivo=("Micrófono (USB)", False))
        _, avisos, medicion, _ = self._ejecutar(gestor, senal=None)
        self.assertEqual(avisos, [("Micrófono activado: USB", "")])
        self.assertTrue(medicion.called)

    def test_sin_microfono_avisa_y_no_mide(self):
        gestor = DobleGestor(
            entradas=(("Audio del escritorio", "wasapi_output_capture"),),
            silencio=False)
        _, avisos, medicion, estados = self._ejecutar(gestor)
        self.assertEqual(avisos, [(
            "OBS no tiene ningún micrófono. Elige uno en Preferencias, "
            "página Transmisión, Micrófono de OBS.", "")])
        medicion.assert_not_called()
        self.assertEqual(estados, [None])

    def test_obs_caido_avisa_el_texto_de_siempre_y_no_mide(self):
        gestor = DobleGestor()
        gestor.conectar = mock.Mock(side_effect=RuntimeError("sin OBS"))
        _, avisos, medicion, estados = self._ejecutar(gestor)
        self.assertTrue(gestor.cerrado)
        self.assertEqual(avisos, [(
            "OBS no responde. En OBS, menú Herramientas, Configuración "
            "del servidor WebSocket, activa el servidor.", "")])
        medicion.assert_not_called()
        self.assertEqual(estados, [None])

    def test_un_fallo_al_cerrar_no_se_escapa(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=True)
        gestor.cerrar = mock.Mock(side_effect=RuntimeError("socket cerrado"))
        _, avisos, medicion, _ = self._ejecutar(gestor)
        self.assertEqual(avisos, [("Micrófono silenciado", "")])
        medicion.assert_not_called()

    def test_al_estado_recibe_verdadero_al_silenciar(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=True,
            dispositivo=("Micrófono (USB)", False))
        _, _, _, estados = self._ejecutar(gestor, senal=None)
        self.assertEqual(estados, [True])

    def test_al_estado_recibe_falso_al_activar(self):
        gestor = DobleGestor(
            entradas=(("Mic/Aux", "wasapi_input_capture"),), silencio=False,
            dispositivo=("Micrófono (USB)", False))
        _, _, _, estados = self._ejecutar(gestor, senal=True)
        self.assertEqual(estados, [False])

    def test_al_estado_recibe_nada_sin_microfono(self):
        gestor = DobleGestor(
            entradas=(("Audio del escritorio", "wasapi_output_capture"),))
        _, _, _, estados = self._ejecutar(gestor)
        self.assertEqual(estados, [None])


class EstadoMicrofonoTest(unittest.TestCase):
    def _estado(self, entradas, especial="Mic/Aux", silencios=None,
                fallo_conectar=False):
        gestor = DobleGestor(entradas=entradas, especial=especial)
        gestor.silencios = dict(silencios or {})
        if fallo_conectar:
            gestor.conectar = mock.Mock(side_effect=RuntimeError("sin OBS"))
        with mock.patch("ytchat.obs.obs_panel.GestorPanelObs",
                        return_value=gestor):
            return obs_entradas_audio.estado_microfono(""), gestor

    def test_devuelve_el_silencio_del_microfono(self):
        estado, _ = self._estado(
            (("Mic/Aux", "wasapi_input_capture"),), silencios={"Mic/Aux": True})
        self.assertIs(estado, True)

    def test_devuelve_falso_si_esta_activado(self):
        estado, _ = self._estado(
            (("Mic/Aux", "wasapi_input_capture"),),
            silencios={"Mic/Aux": False})
        self.assertIs(estado, False)

    def test_sin_microfono_da_nada(self):
        estado, _ = self._estado(
            (("Audio del escritorio", "wasapi_output_capture"),))
        self.assertIsNone(estado)

    def test_si_obs_no_responde_da_nada(self):
        estado, _ = self._estado((), fallo_conectar=True)
        self.assertIsNone(estado)


class TestPseudoAvisoSinSenal(unittest.TestCase):
    """Pseudotraducción del aviso de micrófono sin señal.

    Sin ventanas: dispara `microfono_por_atajo` bajo `con_pseudo()` con
    el doble y exige el aviso marcado. El texto lo arma `obs_audio` y lo
    muestra este módulo.
    """

    def test_aviso_de_microfono_sin_senal_sale_marcado(self):
        gestor = DobleGestor(
            fuentes=("Mic/Aux",), silencio=False,
            dispositivo=("Micrófono (USB)", False))
        avisos = []
        with con_pseudo(), \
                mock.patch("ytchat.obs.obs_panel.GestorPanelObs",
                           return_value=gestor), \
                mock.patch.object(obs_entradas_audio, "senal_microfono",
                                  return_value=False):
            obs_entradas_audio.microfono_por_atajo(
                "Mic/Aux", lambda *args: avisos.append(args))
        self.assertEqual(len(avisos), 2)
        self.assertTrue(avisos[0][0].startswith("[¡"), avisos)
        self.assertTrue(avisos[1][0].startswith("[¡"), avisos)
        self.assertEqual(avisos[1][1], "microfono_sin_senal")


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

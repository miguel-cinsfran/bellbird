import random
import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.obs import obs_audio
from ytchat.obs.obs_audio import elegir_microfono, frase_microfono, nombre_corto

TEXTO_SIN_SENAL = ("El micrófono no recibe sonido. Revisa cuál está elegido "
                   "en Windows o en OBS.")


def _evento(canales, fuente="Mic/Aux"):
    return {"inputs": [{"inputName": fuente, "inputLevelsMul": canales}]}


class ElegirMicrofonoTest(unittest.TestCase):
    def test_prefiere_el_nombre_guardado(self):
        self.assertEqual(elegir_microfono(("Mic/Aux", "Otro"), "Otro"), "Otro")

    def test_el_preferido_gana_a_una_fuente_con_mic(self):
        self.assertEqual(elegir_microfono(("Mic/Aux", "Audio USB"), "Audio USB"),
                         "Audio USB")

    def test_elije_la_primera_fuente_con_mic_sin_tildes(self):
        self.assertEqual(elegir_microfono(
            ("Audio del escritorio", "Mícrofono USB"), ""), "Mícrofono USB")

    def test_usa_la_primera_fuente_si_no_hay_microfono(self):
        self.assertEqual(elegir_microfono(("Audio del escritorio", "Auxiliar"), ""),
                         "Audio del escritorio")

    def test_devuelve_vacio_sin_fuentes(self):
        self.assertEqual(elegir_microfono((), "Mic/Aux"), "")


class FraseMicrofonoTest(unittest.TestCase):
    def test_anuncia_microfono_silenciado(self):
        self.assertEqual(frase_microfono("Mic/Aux", True), "Micrófono silenciado")

    def test_anuncia_microfono_activado(self):
        self.assertEqual(frase_microfono("Mic/Aux", False), "Micrófono activado")

    def test_nombra_la_fuente_que_no_es_microfono(self):
        self.assertEqual(frase_microfono("Audio del escritorio", True),
                         "Audio del escritorio silenciado")

    def test_anuncia_la_ausencia_de_fuentes(self):
        self.assertEqual(frase_microfono("", False),
                         "OBS no tiene ninguna fuente de audio")

    def test_anuncia_el_dispositivo_fijo_del_microfono(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", False, "Micrófono (WO Mic Device)"),
            "Micrófono activado: WO Mic Device")

    def test_anuncia_el_predeterminado_de_windows_con_su_nombre(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", False, "Micrófono (WO Mic Device)", True),
            "Micrófono activado: predeterminado de Windows, WO Mic Device")

    def test_anuncia_el_predeterminado_de_windows_sin_nombre(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", False, "", True),
            "Micrófono activado: predeterminado de Windows")

    def test_sin_dispositivo_anuncia_como_hoy(self):
        self.assertEqual(frase_microfono("Mic/Aux", False, "", False),
                         "Micrófono activado")

    def test_silenciado_no_nombra_el_dispositivo(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", True, "Micrófono (WO Mic Device)", True),
            "Micrófono silenciado")

    def test_la_fuente_que_no_es_microfono_no_nombra_el_dispositivo(self):
        self.assertEqual(
            frase_microfono("Audio del escritorio", False,
                            "Micrófono (WO Mic Device)"),
            "Audio del escritorio activado")


class NombreCortoTest(unittest.TestCase):
    def test_quita_el_envoltorio_de_windows(self):
        self.assertEqual(nombre_corto("Micrófono (WO Mic Device)"),
                         "WO Mic Device")

    def test_conserva_el_nombre_sin_envoltorio(self):
        self.assertEqual(nombre_corto("Mic/Aux"), "Mic/Aux")

    def test_usa_el_primer_parentesis_y_el_ultimo_cierre(self):
        self.assertEqual(nombre_corto("Micrófono (USB (2))"), "USB (2)")

    def test_nunca_es_vacio_si_el_nombre_no_lo_es(self):
        for nombre in ("Mic/Aux", "Micrófono (WO Mic Device)", " ()", " () ",
                       "Audio del escritorio"):
            with self.subTest(nombre=nombre):
                self.assertTrue(nombre_corto(nombre))


class EsMicrofonoTest(unittest.TestCase):
    def test_decide_por_el_nombre_sin_tildes(self):
        self.assertTrue(obs_audio.es_microfono("Mícrofonos (USB)"))

    def test_decide_por_el_nombre_con_tildes(self):
        self.assertTrue(obs_audio.es_microfono("Micrófono (WO Mic Device)"))

    def test_una_fuente_sin_nombre_no_es_microfono(self):
        for nombre in ("", "Audio del escritorio", "Auxiliar"):
            with self.subTest(nombre=nombre):
                self.assertFalse(obs_audio.es_microfono(nombre))


class TieneSenalTest(unittest.TestCase):
    def test_las_constantes_son_las_del_diseno(self):
        self.assertEqual(obs_audio.UMBRAL_SENAL, 0.0001)
        self.assertEqual(obs_audio.TEXTO_SIN_SENAL, TEXTO_SIN_SENAL)

    def test_solo_ceros_es_falso(self):
        eventos = [_evento([[0.0, 0.0, 0.0]]),
                   _evento([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])]
        self.assertIs(obs_audio.tiene_senal(eventos, "Mic/Aux"), False)

    def test_el_ruido_de_oficina_cuenta_como_senal(self):
        # Medido en OBS 32.2.2 el 23/10: apagado el micrófono, todo en cero;
        # prendido y sin hablar, pico 0,049 (menos 26 dBFS) y promedio 0,004.
        eventos = [_evento([[0.004, 0.03, 0.049]])]
        self.assertIs(obs_audio.tiene_senal(eventos, "Mic/Aux"), True)

    def test_decide_por_el_pico_de_entrada_y_no_por_el_volumen(self):
        # El índice 2 va antes del fader de OBS: un volumen casi cero no
        # puede tapar una señal que sí llegó.
        eventos = [_evento([[0.00006, 0.009, 0.049]])]
        self.assertIs(obs_audio.tiene_senal(eventos, "Mic/Aux"), True)

    def test_sin_muestras_de_la_fuente_devuelve_ninguna(self):
        self.assertIsNone(obs_audio.tiene_senal([], "Mic/Aux"))
        self.assertIsNone(
            obs_audio.tiene_senal([_evento([[0.2, 0.3, 0.4]])], "Otro"))
        self.assertIsNone(
            obs_audio.tiene_senal([{"inputs": []}], "Mic/Aux"))

    def test_busca_entre_varias_fuentes_y_canal_ingles(self):
        eventos = [
            {"inputs": [
                {"inputName": "Otro", "inputLevelsMul": [[0.9, 0.9, 0.9]]},
                {"inputName": "Mic/Aux", "inputLevelsMul": [[0.0, 0.0, 0.0]]},
            ]},
            _evento([[0.0, 0.0, 0.0011]]),
        ]
        self.assertIs(obs_audio.tiene_senal(eventos, "Mic/Aux"), True)

    def test_un_canal_corto_usa_su_ultimo_nivel(self):
        self.assertIs(obs_audio.tiene_senal(
            [_evento([[0.0, 0.05]])], "Mic/Aux"), True)
        self.assertIs(obs_audio.tiene_senal(
            [_evento([[0.0]])], "Mic/Aux"), False)
        self.assertIs(obs_audio.tiene_senal(
            [_evento([[0.02]])], "Mic/Aux"), True)

    def test_el_umbral_se_para_estricto(self):
        self.assertIs(obs_audio.tiene_senal(
            [_evento([[0.0001, 0.0001, 0.0001]])], "Mic/Aux"), False)

    def test_subir_un_nivel_nunca_baja_verdadero_a_falso(self):
        aleatorio = random.Random(13)
        probados = 0
        for _ in range(60):
            canales = []
            for _ in range(aleatorio.randint(1, 2)):
                canales.append([round(aleatorio.random(), 6)
                                for _ in range(3)])
            eventos = [_evento(canales)]
            antes = obs_audio.tiene_senal(eventos, "Mic/Aux")
            if antes is not True:
                continue
            probados += 1
            mas = aleatorio.random() * 0.1
            elevados = []
            for evento in eventos:
                entradas = []
                for entrada in evento["inputs"]:
                    subidos = [[min(1.0, v + mas) for v in canal]
                               for canal in entrada["inputLevelsMul"]]
                    entradas.append(dict(entrada, inputLevelsMul=subidos))
                elevados.append({"inputs": entradas})
            self.assertIs(obs_audio.tiene_senal(elevados, "Mic/Aux"), True,
                          f"sus niveles {canales} subidos {mas}")
        self.assertGreater(probados, 0)


class TestPseudoAudio(unittest.TestCase):
    """Pseudotraducción de los anuncios de `obs_audio`.

    Sin ventanas: llama a `frase_microfono` bajo `con_pseudo()` en todos
    los caminos y exige el texto propio marcado. El nombre del dispositivo
    es un dato de Windows y viaja sin marcar.
    """

    def test_todos_los_caminos_salen_marcados(self):
        casos = (
            ("", False, "", False),
            ("Mic/Aux", True, "", False),
            ("Mic/Aux", False, "", False),
            ("Mic/Aux", False, "Micrófono (WO Mic Device)", False),
            ("Mic/Aux", False, "", True),
            ("Mic/Aux", False, "Micrófono (WO Mic Device)", True),
            ("Audio del escritorio", True, "", False),
            ("Audio del escritorio", False, "", False),
            ("Audio del escritorio", True, "Micrófono (WO Mic Device)", True),
        )
        with con_pseudo():
            for fuente, silenciado, dispositivo, predeterminado in casos:
                with self.subTest(fuente=fuente, silenciado=silenciado,
                                  predeterminado=predeterminado):
                    frase = frase_microfono(
                        fuente, silenciado, dispositivo, predeterminado)
                    self.assertTrue(frase.startswith("[¡"), frase)
                    if dispositivo and fuente != "Audio del escritorio":
                        self.assertIn("WO Mic Device", frase)

    def test_texto_sin_senal_se_traduce_donde_se_muestra(self):
        with con_pseudo():
            self.assertTrue(_(obs_audio.TEXTO_SIN_SENAL).startswith("[¡"))


if __name__ == "__main__":
    unittest.main()

"""Pruebas de la grabación que arranca junto con la transmisión.

Sin ventanas y sin OBS real: el cliente, el gestor y la salida son dobles.
Lo único real es el hilo del supervisor en las pruebas de cableado.
"""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests.pseudo_prueba import con_pseudo
from bellbird.core.idioma import _
from bellbird.obs import obs_grabacion
from bellbird.obs.obs_grabacion import (
    AVISO_CODIFICADOR, FALLO_GRABACION, GrabacionAlTransmitir,
    codificador_propio, codificador_propio_en_obs, grabar_al_transmitir)
from bellbird.obs.obs_supervisor import SupervisorTransmision


def muestra(activa=True):
    return {"outputActive": activa, "outputDuration": 0,
            "outputSkippedFrames": 0, "outputTotalFrames": 0,
            "outputReconnecting": False}


def esperar_condicion(condicion, plazo=2.0):
    inicio = time.monotonic()
    while time.monotonic() - inicio < plazo:
        if condicion():
            return True
        time.sleep(0.005)
    return bool(condicion())


class DobleParametros:
    """GetProfileParameter con respuestas por categoría y nombre."""

    def __init__(self, respuestas=None, falla=False):
        self.respuestas = dict(respuestas or {})
        self.falla = falla
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        datos = dict(datos or {})
        self.llamadas.append((tipo, datos))
        if self.falla:
            raise RuntimeError("OBS sin responder")
        clave = (datos.get("parameterCategory"), datos.get("parameterName"))
        return {"responseData": dict(self.respuestas.get(clave, {}))}

    def pedidos(self):
        return [(datos.get("parameterCategory"), datos.get("parameterName"))
                for _tipo, datos in self.llamadas]


class CodificadorPropioTest(unittest.TestCase):
    def test_tabla_completa(self):
        casos = (
            ("Simple", "Stream", "", False),
            ("Simple", "Calidad personalizada", "x264", True),
            ("Advanced", "", "none", False),
            ("Advanced", "", "x264", True),
            ("Otro", "Stream", "none", False),
        )
        for modo, calidad, codificador, esperado in casos:
            with self.subTest(modo=modo, calidad=calidad,
                              codificador=codificador):
                self.assertIs(
                    codificador_propio(modo, calidad, codificador), esperado)


class CodificadorEnObsTest(unittest.TestCase):
    def test_en_simple_pregunta_modo_y_calidad(self):
        doble = DobleParametros({
            ("Output", "Mode"): {"parameterValue": "Simple"},
            ("SimpleOutput", "RecQuality"): {"parameterValue": "Stream"},
        })
        self.assertFalse(codificador_propio_en_obs(doble))
        self.assertEqual(doble.pedidos(), [
            ("Output", "Mode"),
            ("SimpleOutput", "RecQuality")])

    def test_en_advanced_pregunta_modo_y_codificador(self):
        doble = DobleParametros({
            ("Output", "Mode"): {"parameterValue": "Advanced"},
            ("AdvOut", "RecEncoder"): {"parameterValue": "x264"},
        })
        self.assertTrue(codificador_propio_en_obs(doble))
        self.assertEqual(doble.pedidos(), [
            ("Output", "Mode"),
            ("AdvOut", "RecEncoder")])

    def test_usa_el_valor_por_defecto_si_parameter_value_viene_vacio(self):
        doble = DobleParametros({
            ("Output", "Mode"): {"parameterValue": "",
                                 "defaultParameterValue": "Advanced"},
            ("AdvOut", "RecEncoder"): {"parameterValue": None,
                                      "defaultParameterValue": "none"},
        })
        self.assertFalse(codificador_propio_en_obs(doble))

    def test_si_obs_falla_da_none(self):
        self.assertIsNone(codificador_propio_en_obs(DobleParametros(falla=True)))

    def test_modo_desconocido_da_que_no(self):
        doble = DobleParametros({
            ("Output", "Mode"): {"parameterValue": "Raro"},
        })
        self.assertFalse(codificador_propio_en_obs(doble))
        self.assertEqual(doble.pedidos(), [("Output", "Mode")])


class GrabacionAlTransmitirConfigTest(unittest.TestCase):
    def _leer(self, contenido):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            ruta.write_text(contenido, encoding="utf-8")
            return grabar_al_transmitir(ruta)

    def test_marcado(self):
        self.assertIs(self._leer(
            "[transmision]\ngrabar_al_transmitir = true\n"), True)

    def test_desmarcado(self):
        self.assertIs(self._leer(
            "[transmision]\ngrabar_al_transmitir = false\n"), False)

    def test_ausente_da_falso(self):
        self.assertIs(self._leer("[transmision]\n"), False)

    def test_sin_archivo_da_falso(self):
        self.assertIs(grabar_al_transmitir(
            Path(tempfile.gettempdir()) / "no-existe-grabacion.ini"), False)


class GestorGrabacion:
    """Doble mínimo de GestorPanelObs para la grabación."""

    def __init__(self, registro=None):
        self._registro = registro if registro is not None else {"grabando": False}
        self._cliente = self
        self.llamadas = []

    def estado_grabacion(self, parada=None):
        self.llamadas.append("estado_grabacion")
        return {"outputActive": self._registro["grabando"]}

    def alternar_grabacion(self, parada=None):
        self.llamadas.append("alternar_grabacion")
        if self._registro.get("falla_alternar"):
            raise RuntimeError("no se pudo alternar")
        self._registro["grabando"] = bool(
            self._registro.get("alternar_devuelve")
            if self._registro.get("alternar_devuelve") is not None
            else not self._registro["grabando"])
        return self._registro["grabando"]


class EnvolverEsperarSalidaTest(unittest.TestCase):
    def _armar(self, activa=True, registro=None):
        registro = registro if registro is not None else {"grabando": False}
        creados = []
        anuncios = []

        def crear_gestor(cliente=None):
            gestor = GestorGrabacion(registro)
            creados.append(gestor)
            return gestor

        grabacion = GrabacionAlTransmitir(
            activa=lambda: activa,
            al_anunciar=lambda frase, sonido: anuncios.append((frase, sonido)),
            crear_gestor=crear_gestor)
        return grabacion, registro, creados, anuncios

    def test_graba_con_enviando_y_casilla_marcada(self):
        grabacion, registro, creados, anuncios = self._armar()
        envoltura = grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")
        self.assertEqual(envoltura(object()), "enviando")
        self.assertTrue(registro["grabando"])
        self.assertEqual(len(creados), 1)
        self.assertEqual(creados[0].llamadas,
                         ["estado_grabacion", "alternar_grabacion"])
        self.assertEqual(anuncios, [])

    def test_otro_veredicto_no_consulta_nada(self):
        grabacion, registro, creados, anuncios = self._armar()
        envoltura = grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "sin_salida")
        self.assertEqual(envoltura(object()), "sin_salida")
        self.assertEqual(creados, [])
        self.assertFalse(registro["grabando"])
        self.assertEqual(anuncios, [])

    def test_casilla_desmarcada_no_consulta_nada(self):
        grabacion, registro, creados, anuncios = self._armar(activa=False)
        envoltura = grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")
        self.assertEqual(envoltura(object()), "enviando")
        self.assertEqual(creados, [])
        self.assertFalse(registro["grabando"])

    def test_si_obs_ya_graba_no_alterna(self):
        grabacion, registro, creados, anuncios = self._armar(
            registro={"grabando": True})
        envoltura = grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")
        self.assertEqual(envoltura(object()), "enviando")
        self.assertTrue(registro["grabando"])
        self.assertEqual(creados[0].llamadas, ["estado_grabacion"])
        self.assertEqual(anuncios, [])

    def test_si_alternar_da_falso_anuncia_y_conserva_el_veredicto(self):
        grabacion, registro, creados, anuncios = self._armar(
            registro={"grabando": False, "alternar_devuelve": False})
        envoltura = grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")
        self.assertEqual(envoltura(object()), "enviando")
        self.assertEqual(anuncios, [(FALLO_GRABACION, "grabacion_problema")])

    def test_si_alternar_lanza_anuncia_y_conserva_el_veredicto(self):
        grabacion, registro, creados, anuncios = self._armar(
            registro={"grabando": False, "falla_alternar": True})
        envoltura = grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")
        self.assertEqual(envoltura(object()), "enviando")
        self.assertEqual(anuncios, [(FALLO_GRABACION, "grabacion_problema")])


class GestorReal:
    def __init__(self, registro, estados):
        self._registro = registro
        self._estados = list(estados)
        self._indice = 0
        self._cliente = self
        self.llamadas = []

    def estado_transmision(self, parada=None):
        estado = self._estados[min(self._indice, len(self._estados) - 1)]
        self._indice += 1
        self.llamadas.append("estado_transmision")
        return dict(estado)

    def estado_grabacion(self, parada=None):
        self.llamadas.append("estado_grabacion")
        return {"outputActive": self._registro["grabando"]}

    def alternar_grabacion(self, parada=None):
        self.llamadas.append("alternar_grabacion")
        self._registro["grabando"] = not self._registro["grabando"]
        return self._registro["grabando"]


class EnvolverCrearGestorTest(unittest.TestCase):
    def _armar(self, ya_grabando=False):
        registro = {"grabando": ya_grabando}
        creados = []

        def crear_gestor(cliente=None):
            gestor = GestorGrabacion(registro)
            creados.append(gestor)
            return gestor

        grabacion = GrabacionAlTransmitir(
            activa=lambda: True, al_anunciar=lambda frase, sonido: None,
            crear_gestor=crear_gestor)
        return grabacion, registro, creados

    def test_detiene_una_sola_vez_la_grabacion_de_la_app(self):
        grabacion, registro, creados = self._armar()
        grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")(object())
        self.assertTrue(registro["grabando"])
        creados.clear()
        real = GestorReal(registro, [{"outputActive": False}])
        envoltorio = grabacion.envolver_crear_gestor(lambda: real)()
        envoltorio.estado_transmision()
        envoltorio.estado_transmision()
        self.assertFalse(registro["grabando"])
        self.assertEqual(real.llamadas.count("alternar_grabacion"), 1)

    def test_no_toca_una_grabacion_que_no_empezo_la_app(self):
        grabacion, registro, creados = self._armar()
        real = GestorReal(registro, [{"outputActive": False}])
        envoltorio = grabacion.envolver_crear_gestor(lambda: real)()
        envoltorio.estado_transmision()
        self.assertEqual(creados, [])
        self.assertFalse(registro["grabando"])

    def test_si_la_grabacion_ya_termino_no_alterna(self):
        grabacion, registro, creados = self._armar()
        grabacion.envolver_esperar_salida(
            lambda cliente, parada=None: "enviando")(object())
        creados.clear()
        registro["grabando"] = False
        real = GestorReal(registro, [{"outputActive": False}])
        envoltorio = grabacion.envolver_crear_gestor(lambda: real)()
        envoltorio.estado_transmision()
        self.assertNotIn("alternar_grabacion", real.llamadas)


class ObsDeGrabacion:
    def __init__(self, registro, estados, cliente=None):
        self._registro = registro
        self._estados = list(estados)
        self._indice = 0
        self._cliente = cliente or self
        self.llamadas = []
        self.cerrado = 0

    def conectar(self, parada=None):
        self.llamadas.append("conectar")

    def iniciar_transmision(self, parada=None):
        self.llamadas.append("iniciar")

    def detener_transmision(self, parada=None):
        self.llamadas.append("detener")

    def estado_transmision(self, parada=None):
        self.llamadas.append("estado")
        estado = self._estados[min(self._indice, len(self._estados) - 1)]
        self._indice += 1
        return dict(estado)

    def estadisticas(self, parada=None):
        return {}

    def estado_grabacion(self, parada=None):
        self.llamadas.append("estado_grabacion")
        return {"outputActive": self._registro["grabando"]}

    def alternar_grabacion(self, parada=None):
        self.llamadas.append("alternar_grabacion")
        self._registro["grabando"] = not self._registro["grabando"]
        self._registro["cambios"] += 1
        return self._registro["grabando"]

    def traer_panel_adelante(self, parada=None):
        return None

    def cerrar(self):
        self.cerrado += 1


class CableadoSupervisorTest(unittest.TestCase):
    def _armar(self, grabar=True, ya_grabando=False):
        registro = {"grabando": ya_grabando, "cambios": 0}
        creados = []
        anuncios = []
        contador = {"sin_cliente": 0}

        def crear_obs(cliente=None):
            if cliente is None:
                contador["sin_cliente"] += 1
                if contador["sin_cliente"] == 1:
                    estados = [muestra(True)] * 1000
                else:
                    estados = [muestra(True), muestra(False)]
            else:
                estados = [muestra(True)]
            gestor = ObsDeGrabacion(registro, estados, cliente)
            creados.append(gestor)
            return gestor

        grabacion = GrabacionAlTransmitir(
            activa=lambda: grabar,
            al_anunciar=lambda frase, sonido: anuncios.append((frase, sonido)),
            crear_gestor=crear_obs)
        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append((frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=grabacion.envolver_crear_gestor(crear_obs),
            esperar_salida=grabacion.envolver_esperar_salida(
                lambda cliente, parada=None: "enviando"),
            dormir=lambda segundos: time.sleep(0.005),
            reloj=time.monotonic,
            intervalo_salud=0.01,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        return supervisor, registro, creados, anuncios

    def _esperar_grabando_y_vigilando(self, supervisor, registro, creados):
        self.assertTrue(esperar_condicion(lambda: registro["grabando"]),
                        "no empezó la grabación")
        self.assertTrue(esperar_condicion(
            lambda: creados and "estado" in creados[0].llamadas),
            "no entró en vigilancia")

    def test_detener_detiene_la_grabacion_que_empezo_la_app(self):
        supervisor, registro, creados, anuncios = self._armar()
        supervisor.iniciar()
        self._esperar_grabando_y_vigilando(supervisor, registro, creados)
        supervisor.detener()
        self.assertFalse(registro["grabando"])
        self.assertEqual(registro["cambios"], 2)

    def test_grabacion_previa_sigue_al_detener(self):
        supervisor, registro, creados, anuncios = self._armar(
            ya_grabando=True)
        supervisor.iniciar()
        self._esperar_grabando_y_vigilando(supervisor, registro, creados)
        supervisor.detener()
        self.assertTrue(registro["grabando"])
        self.assertEqual(registro["cambios"], 0)

    def test_abandonar_no_detiene_la_grabacion(self):
        supervisor, registro, creados, anuncios = self._armar()
        supervisor.iniciar()
        self._esperar_grabando_y_vigilando(supervisor, registro, creados)
        supervisor.abandonar()
        self.assertTrue(registro["grabando"])
        self.assertEqual(registro["cambios"], 1)


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_fallo_al_iniciar_salen_marcados(self):
        creados = []
        anuncios = []

        def crear_gestor(cliente=None):
            gestor = GestorGrabacion({"grabando": False,
                                      "alternar_devuelve": False})
            creados.append(gestor)
            return gestor

        grabacion = GrabacionAlTransmitir(
            activa=lambda: True,
            al_anunciar=lambda frase, sonido: anuncios.append((frase, sonido)),
            crear_gestor=crear_gestor)
        with con_pseudo():
            envoltura = grabacion.envolver_esperar_salida(
                lambda cliente, parada=None: "enviando")
            envoltura(object())
            marcados = [_(AVISO_CODIFICADOR), _(FALLO_GRABACION)]
        self.assertEqual(len(anuncios), 1)
        for texto, _sonido in anuncios:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


if __name__ == "__main__":
    unittest.main()

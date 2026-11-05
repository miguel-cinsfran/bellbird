"""Pruebas de llevar un diseño calculado a una escena de OBS, sin wx."""

import unittest

from bellbird.obs import (
    aplicar_diseno, disenos_escena, disenos_fabrica, obs_panel)
from bellbird.obs.fuente_chat import NOMBRE_FUENTE, TIPO_FUENTE
from tests.test_obs_panel import DobleObs, elemento


class RegistroFalso:

    def __init__(self, eventos):
        self._eventos = eventos

    def guardar(self, gestor, escena, fuente):
        self._eventos.append(("guardar", fuente))


class GestorQueAnota(obs_panel.GestorPanelObs):

    def __init__(self, cliente, eventos):
        super().__init__(cliente)
        self._eventos = eventos

    def transformar(self, escena, transformacion, parada=None, *, fuente=NOMBRE_FUENTE):
        self._eventos.append(("transformar", fuente))
        super().transformar(escena, transformacion, parada, fuente=fuente)

    def posicionar(self, escena, x, y, alineacion, parada=None, *, fuente=NOMBRE_FUENTE):
        self._eventos.append(("posicionar", fuente))
        super().posicionar(escena, x, y, alineacion, parada, fuente=fuente)

    def redimensionar(self, escena, ancho, alto, parada=None):
        self._eventos.append(("redimensionar", NOMBRE_FUENTE))
        super().redimensionar(escena, ancho, alto, parada)

    def al_frente(self, escena, parada=None, *, fuente=NOMBRE_FUENTE):
        self._eventos.append(("al_frente", fuente))
        super().al_frente(escena, parada, fuente=fuente)


def _escena():
    juego = elemento(1, "Juego", 0, ancho=1600, alto=900, alineacion=0,
                     ancho_fuente=1600, alto_fuente=900)
    juego["inputKind"] = "game_capture"
    camara = elemento(2, "Cámara", 1, ancho=640, alto=480,
                      ancho_fuente=1280, alto_fuente=720)
    camara["inputKind"] = "dshow_input"
    chat = elemento(3, NOMBRE_FUENTE, 2)
    chat["inputKind"] = TIPO_FUENTE
    return [juego, camara, chat]


def _diseno(chat="franja"):
    return disenos_escena.Diseno(
        clase="imagen_en_imagen", principal="Juego", secundaria="Cámara",
        chat=chat)


def _con_tipo(identificador, nombre, indice, tipo, visible=True, **tamano):
    creado = elemento(identificador, nombre, indice, visible=visible, **tamano)
    creado["inputKind"] = tipo
    return creado


def _fabrica(clave):
    return next(fabrica for fabrica in disenos_fabrica.FABRICA
                if fabrica.clave == clave)


def _principal(elementos):
    gestor = obs_panel.GestorPanelObs(DobleObs(elementos))
    fuentes = aplicar_diseno.fuentes_de_escena(gestor, "Escena")
    fabrica = _fabrica("pantalla_juego")
    return disenos_fabrica.completar(
        fabrica.diseno, fabrica.papeles, fuentes).principal


class FuentesDeEscenaTest(unittest.TestCase):

    def test_reconoce_captura_camara_y_chat(self):
        gestor = obs_panel.GestorPanelObs(DobleObs(_escena()))
        fuentes = aplicar_diseno.fuentes_de_escena(gestor, "Escena")
        self.assertEqual(
            [(fuente.nombre, fuente.tipo, fuente.ancho, fuente.alto)
             for fuente in fuentes],
            [("Juego", "captura", 1600, 900),
             ("Cámara", "camara", 1280, 720),
             (NOMBRE_FUENTE, "chat", 460, 620)])

    def test_sin_tamano_de_origen_usa_cero(self):
        elementos = [{"sourceName": "Rara", "inputKind": "image_source",
                      "sceneItemTransform": {}}]
        gestor = obs_panel.GestorPanelObs(DobleObs(elementos))
        fuente = aplicar_diseno.fuentes_de_escena(gestor, "Escena")[0]
        self.assertEqual((fuente.ancho, fuente.alto), (0, 0))

    def test_los_tres_tipos_de_captura_son_captura(self):
        for tipo in ("game_capture", "monitor_capture", "window_capture"):
            with self.subTest(tipo=tipo):
                elementos = [_con_tipo(1, "Fuente", 0, tipo)]
                gestor = obs_panel.GestorPanelObs(DobleObs(elementos))
                fuente = aplicar_diseno.fuentes_de_escena(gestor, "Escena")[0]
                self.assertEqual(fuente.tipo, "captura")

    def test_las_fuentes_de_solo_audio_no_aparecen(self):
        elementos = [
            _con_tipo(1, "Micrófono", 0, "wasapi_input_capture"),
            _con_tipo(2, "Escritorio", 1, "wasapi_output_capture"),
            _con_tipo(3, "Proceso", 2, "wasapi_process_output_capture"),
            _con_tipo(4, "Pantalla", 3, "monitor_capture")]
        gestor = obs_panel.GestorPanelObs(DobleObs(elementos))
        fuentes = aplicar_diseno.fuentes_de_escena(gestor, "Escena")
        self.assertEqual([fuente.nombre for fuente in fuentes], ["Pantalla"])

    def test_el_lugar_principal_prefiere_una_captura_sobre_una_imagen(self):
        elementos = [
            _con_tipo(1, "Imagen", 0, "image_source"),
            _con_tipo(2, "Pantalla", 1, "monitor_capture")]
        self.assertEqual(_principal(elementos), "Pantalla")

    def test_entre_dos_capturas_gana_la_visible(self):
        elementos = [
            _con_tipo(1, "Oculta", 0, "monitor_capture", visible=False),
            _con_tipo(2, "Visible", 1, "game_capture")]
        self.assertEqual(_principal(elementos), "Visible")

    def test_entre_dos_capturas_visibles_gana_la_de_abajo(self):
        elementos = [
            _con_tipo(1, "Abajo", 0, "window_capture"),
            _con_tipo(2, "Arriba", 1, "monitor_capture")]
        self.assertEqual(_principal(elementos), "Abajo")

    def test_sin_capturas_la_principal_es_otra_fuente(self):
        elementos = [
            _con_tipo(1, "Cámara", 0, "dshow_input"),
            _con_tipo(2, "Imagen", 1, "image_source")]
        self.assertEqual(_principal(elementos), "Imagen")

    def test_fuentes_de_escena_lee_los_elementos_una_sola_vez(self):
        doble = DobleObs(_escena())
        gestor = obs_panel.GestorPanelObs(doble)
        aplicar_diseno.fuentes_de_escena(gestor, "Escena")
        self.assertEqual(
            [llamada[0] for llamada in doble.llamadas].count(
                "GetSceneItemList"), 1)


class AplicarDisenoTest(unittest.TestCase):

    def _aplicar(self, chat="franja"):
        eventos = []
        doble = DobleObs(_escena())
        gestor = GestorQueAnota(doble, eventos)
        fuentes = aplicar_diseno.fuentes_de_escena(gestor, "Escena")
        colocaciones = disenos_escena.calcular(1600, 900, fuentes,
                                               _diseno(chat))
        resultado = aplicar_diseno.aplicar(
            gestor, RegistroFalso(eventos), "Escena", colocaciones)
        return doble, eventos, colocaciones, resultado

    def test_imagen_en_imagen_con_chat_en_franja(self):
        doble, eventos, colocaciones, resultado = self._aplicar()
        por_nombre = {colocacion["nombre"]: colocacion
                      for colocacion in colocaciones}

        guardados = [evento[1] for evento in eventos if evento[0] == "guardar"]
        self.assertEqual(guardados, [NOMBRE_FUENTE, "Cámara", "Juego"])
        primer_cambio = next(indice for indice, evento in enumerate(eventos)
                             if evento[0] != "guardar")
        ultimo_guardado = max(indice for indice, evento in enumerate(eventos)
                              if evento[0] == "guardar")
        self.assertLess(ultimo_guardado, primer_cambio)

        escrituras = {
            llamada[1]["sceneItemId"]: llamada[1]["sceneItemTransform"]
            for llamada in doble.llamadas
            if llamada[0] == "SetSceneItemTransform"}
        for nombre, identificador in (("Juego", 1), ("Cámara", 2)):
            esperado = {clave: valor for clave, valor in por_nombre[nombre].items()
                        if clave not in ("nombre", "estado")}
            self.assertEqual(escrituras[identificador], esperado)

        self.assertEqual(escrituras[3], {
            "positionX": por_nombre[NOMBRE_FUENTE]["positionX"],
            "positionY": por_nombre[NOMBRE_FUENTE]["positionY"],
            "alignment": por_nombre[NOMBRE_FUENTE]["alignment"]})
        tamano = next(llamada[1] for llamada in doble.llamadas
                      if llamada[0] == "SetInputSettings")
        self.assertEqual(
            (tamano["inputSettings"]["width"],
             tamano["inputSettings"]["height"]),
            (por_nombre[NOMBRE_FUENTE]["ancho"],
             por_nombre[NOMBRE_FUENTE]["alto"]))

        self.assertEqual([evento[1] for evento in eventos
                          if evento[0] == "al_frente"],
                         ["Juego", "Cámara", NOMBRE_FUENTE])
        self.assertEqual(resultado, [
            (NOMBRE_FUENTE, ""),
            ("Cámara", disenos_escena.ESTADO_LLENA),
            ("Juego", disenos_escena.ESTADO_AJUSTA)])

    def test_aplicar_diseno_lee_el_lienzo_y_aplica_lo_calculado(self):
        eventos = []
        doble = DobleObs(_escena())
        gestor = GestorQueAnota(doble, eventos)
        diseno = disenos_escena.Diseno(
            clase="pantalla_completa", principal="Juego")
        resultado, sin_mover = aplicar_diseno.aplicar_diseno(
            gestor, RegistroFalso(eventos), "Escena", diseno)
        self.assertEqual(resultado,
                         [("Juego", disenos_escena.ESTADO_AJUSTA)])
        self.assertEqual(sin_mover, ["Cámara", NOMBRE_FUENTE])
        escritura = next(
            llamada[1]["sceneItemTransform"] for llamada in doble.llamadas
            if llamada[0] == "SetSceneItemTransform"
            and llamada[1]["sceneItemId"] == 1)
        self.assertEqual(
            (escritura["boundsWidth"], escritura["boundsHeight"]), (1600, 900))

    def test_aplicar_diseno_nombra_la_fuente_que_no_entro(self):
        extra = elemento(4, "Extra", 3)
        extra["inputKind"] = "image_source"
        eventos = []
        gestor = GestorQueAnota(DobleObs(_escena() + [extra]), eventos)
        resultado, sin_mover = aplicar_diseno.aplicar_diseno(
            gestor, RegistroFalso(eventos), "Escena", _diseno())
        self.assertEqual([nombre for nombre, _estado in resultado],
                         [NOMBRE_FUENTE, "Cámara", "Juego"])
        self.assertEqual(sin_mover, ["Extra"])

    def test_chat_superpuesto_solo_se_coloca(self):
        doble, eventos, colocaciones, _resultado = self._aplicar("superpuesto")
        por_nombre = {colocacion["nombre"]: colocacion
                      for colocacion in colocaciones}
        self.assertIn(("posicionar", NOMBRE_FUENTE), eventos)
        self.assertNotIn(("redimensionar", NOMBRE_FUENTE), eventos)
        self.assertNotIn("SetInputSettings",
                         [llamada[0] for llamada in doble.llamadas])
        escritura = next(
            llamada[1]["sceneItemTransform"] for llamada in doble.llamadas
            if llamada[0] == "SetSceneItemTransform"
            and llamada[1]["sceneItemId"] == 3)
        self.assertEqual(escritura, {
            "positionX": por_nombre[NOMBRE_FUENTE]["positionX"],
            "positionY": por_nombre[NOMBRE_FUENTE]["positionY"],
            "alignment": por_nombre[NOMBRE_FUENTE]["alignment"]})


if __name__ == "__main__":
    unittest.main()

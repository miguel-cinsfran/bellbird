"""Pruebas de llevar un diseño calculado a una escena de OBS, sin wx."""

import unittest

from bellbird.obs import aplicar_diseno, disenos_escena, obs_panel
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


class FuentesDeEscenaTest(unittest.TestCase):

    def test_reconoce_camara_chat_y_otra(self):
        gestor = obs_panel.GestorPanelObs(DobleObs(_escena()))
        fuentes = aplicar_diseno.fuentes_de_escena(gestor, "Escena")
        self.assertEqual(
            [(fuente.nombre, fuente.tipo, fuente.ancho, fuente.alto)
             for fuente in fuentes],
            [("Juego", "otra", 1600, 900),
             ("Cámara", "camara", 1280, 720),
             (NOMBRE_FUENTE, "chat", 460, 620)])

    def test_sin_tamano_de_origen_usa_cero(self):
        elementos = [{"sourceName": "Rara", "inputKind": "image_source",
                      "sceneItemTransform": {}}]
        gestor = obs_panel.GestorPanelObs(DobleObs(elementos))
        fuente = aplicar_diseno.fuentes_de_escena(gestor, "Escena")[0]
        self.assertEqual((fuente.ancho, fuente.alto), (0, 0))


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

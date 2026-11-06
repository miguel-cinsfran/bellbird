"""Pruebas de la pila de deshacer de las acciones sobre una fuente."""

import unittest

from guyrapu.obs import deshacer, obs_cliente, obs_disposicion, restablecimiento


CLAVES = ("positionX", "positionY", "alignment", "rotation", "scaleX",
          "scaleY", "boundsType", "boundsAlignment", "boundsWidth",
          "boundsHeight", "cropLeft", "cropRight", "cropTop", "cropBottom")


def transformacion(x=10, y=20):
    return {
        "positionX": x, "positionY": y, "alignment": 5,
        "rotation": 0, "scaleX": 1, "scaleY": 1,
        "boundsType": "OBS_BOUNDS_NONE", "boundsAlignment": 0,
        "boundsWidth": 0, "boundsHeight": 0,
        "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
    }


class GestorFalso:

    def __init__(self):
        self.escena = "Principal"
        self.nombres = ["Cámara", "Chat en el vídeo", "Juego"]
        self.formas = {nombre: transformacion() for nombre in self.nombres}
        self.visibles = {nombre: True for nombre in self.nombres}
        self.bloqueadas = {nombre: False for nombre in self.nombres}
        self.llamadas = []
        self.transformadas = []
        self.fallar_transformar = False

    def instantanea(self, escena, parada=None, *, fuente=""):
        return obs_disposicion.SnapshotPanel(
            conectado=True, escena=escena, ancho=460, alto=620,
            visible=self.visibles[fuente], bloqueada=self.bloqueadas[fuente])

    def fuentes(self, escena, parada=None):
        return tuple(self.nombres)

    def elementos(self, escena, parada=None):
        return [
            {"sceneItemId": indice + 1, "sourceName": nombre,
             "sceneItemTransform": dict(self.formas[nombre])}
            for indice, nombre in enumerate(self.nombres)]

    def transformacion(self, escena, parada=None, *, fuente=""):
        return self.formas[fuente]

    def transformar(self, escena, datos, parada=None, *, fuente=""):
        if self.fallar_transformar:
            raise obs_cliente.ObsError("OBS no pudo completar la operación.")
        self.llamadas.append(("transformar", escena, datos, fuente))
        self.transformadas.append((escena, dict(datos), fuente))
        self.formas[fuente].update(datos)

    def redimensionar(self, escena, ancho, alto, parada=None):
        self.llamadas.append(("redimensionar", escena, ancho, alto))

    def escalar(self, escena, ancho, alto, parada=None, *, fuente=""):
        self.llamadas.append(("escalar", escena, ancho, alto, fuente))

    def mostrar(self, escena, visible, parada=None, *, fuente=""):
        self.llamadas.append(("mostrar", escena, visible, fuente))
        self.visibles[fuente] = visible

    def fijar(self, escena, fijada, parada=None, *, fuente=""):
        self.llamadas.append(("fijar", escena, fijada, fuente))
        self.bloqueadas[fuente] = fijada

    def mover_capa(self, escena, capa, parada=None, *, fuente=""):
        self.llamadas.append(("mover_capa", escena, capa, fuente))


class PilaDeshacerTest(unittest.TestCase):

    def setUp(self):
        self.gestor = GestorFalso()
        self.pila = deshacer.PilaDeshacer()

    def test_sin_cambios_no_hay_nada_que_deshacer(self):
        self.assertTrue(self.pila.vacia)
        self.assertIsNone(self.pila.deshacer(self.gestor))
        self.assertEqual(self.gestor.llamadas, [])

    def test_deshace_el_ultimo_primero(self):
        self.pila.guardar(self.gestor, "Principal", "Chat en el vídeo",
                          "visibilidad")
        self.pila.guardar(self.gestor, "Principal", "Chat en el vídeo",
                          "bloqueo")
        self.assertEqual(
            self.pila.deshacer(self.gestor).accion, "bloqueo")
        self.assertEqual(
            self.pila.deshacer(self.gestor).accion, "visibilidad")
        self.assertTrue(self.pila.vacia)

    def test_reaplica_la_forma_la_visibilidad_el_bloqueo_y_la_capa(self):
        fuente = "Chat en el vídeo"
        original = transformacion()
        self.pila.guardar(self.gestor, "Principal", fuente, "posición")
        self.gestor.formas[fuente] = transformacion(90, 90)
        self.gestor.visibles[fuente] = False
        self.gestor.bloqueadas[fuente] = True
        cambio = self.pila.deshacer(self.gestor)
        self.assertEqual(cambio.fuente, fuente)
        escena, datos, origen = self.gestor.transformadas[0]
        self.assertEqual((escena, origen), ("Principal", fuente))
        self.assertEqual(datos["positionX"], original["positionX"])
        self.assertEqual(datos["positionY"], original["positionY"])
        self.assertIn(("mostrar", "Principal", True, fuente),
                      self.gestor.llamadas)
        self.assertIn(("fijar", "Principal", False, fuente),
                      self.gestor.llamadas)
        self.assertIn(("mover_capa", "Principal", 1, fuente),
                      self.gestor.llamadas)
        self.assertEqual(self.gestor.formas[fuente], original)

    def test_si_falla_conserva_el_cambio_para_reintentar(self):
        fuente = "Chat en el vídeo"
        self.pila.guardar(self.gestor, "Principal", fuente, "giro")
        self.gestor.fallar_transformar = True
        with self.assertRaises(obs_cliente.ObsError):
            self.pila.deshacer(self.gestor)
        self.assertFalse(self.pila.vacia)
        self.gestor.fallar_transformar = False
        self.assertEqual(self.pila.deshacer(self.gestor).accion, "giro")

    def test_descartar_quita_la_ultima_sin_tocar_obs(self):
        self.pila.guardar(self.gestor, "Principal", "Cámara", "orden")
        self.gestor.llamadas.clear()
        self.pila.descartar()
        self.assertTrue(self.pila.vacia)
        self.assertEqual(self.gestor.llamadas, [])

    def test_cambiar_nombre_actualiza_los_cambios_guardados(self):
        self.pila.guardar(self.gestor, "Principal", "Cámara", "posición")
        self.pila.guardar(self.gestor, "Juego", "Cámara", "giro")
        self.pila.cambiar_nombre("Cámara", "Cámara nueva")
        self.assertEqual(
            [cambio.fuente for cambio in self.pila._cambios],
            ["Cámara nueva", "Cámara nueva"])

    def test_olvidar_quita_los_cambios_de_esa_fuente_en_esa_escena(self):
        self.pila.guardar(self.gestor, "Principal", "Cámara", "posición")
        self.pila.guardar(self.gestor, "Juego", "Cámara", "giro")
        self.pila.olvidar("Principal", "Cámara")
        self.assertEqual(
            [(cambio.escena, cambio.fuente) for cambio in self.pila._cambios],
            [("Juego", "Cámara")])


class InstantaneaTest(unittest.TestCase):

    def test_usa_la_misma_instantanea_que_el_restablecimiento(self):
        gestor = GestorFalso()
        datos = restablecimiento._instantanea(gestor, "Principal", "Juego")
        self.assertTrue(datos["completa"])
        self.assertEqual(datos["capa"], 0)
        self.assertEqual(datos["ancho"], 460)


if __name__ == "__main__":
    unittest.main()

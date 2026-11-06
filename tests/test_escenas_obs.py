"""Pruebas de las peticiones de escenas a OBS, con un doble."""

import unittest

import wx

from guyrapu.obs import escenas_obs
from guyrapu.ui import escena_menu_escena
from tests.ventanas_prueba import app_de_prueba


class PedirFalso:

    def __init__(self, respuestas=None, fallo=None):
        self.llamadas = []
        self._respuestas = respuestas or {}
        self._fallo = fallo

    def __call__(self, tipo, datos=None, parada=None):
        self.llamadas.append((tipo, datos or {}, parada))
        if self._fallo is not None:
            raise self._fallo
        respuesta = self._respuestas.get(tipo, {})
        return respuesta(datos or {}) if callable(respuesta) else respuesta


class GestorFalso:

    def __init__(self, elementos=None):
        self._elementos = elementos or {}
        self.llamadas = []

    def elementos(self, escena, parada=None):
        self.llamadas.append((escena, parada))
        return list(self._elementos.get(escena, ()))


def _elemento(identificador, indice, nombre, visible=True):
    return {
        "sceneItemId": identificador,
        "sceneItemIndex": indice,
        "sourceName": nombre,
        "sceneItemEnabled": visible,
        "sceneItemTransform": {
            "positionX": 10 * indice, "positionY": 5 * indice,
            "alignment": 5, "scaleX": 1.5, "scaleY": 1.5},
    }


class TestPeticiones(unittest.TestCase):

    def test_crear_una_escena(self):
        pedir = PedirFalso()
        escenas_obs.crear(pedir, "Charla")
        self.assertEqual(
            pedir.llamadas,
            [("CreateScene", {"sceneName": "Charla"}, None)])

    def test_cambiar_el_nombre(self):
        pedir = PedirFalso()
        escenas_obs.renombrar(pedir, "Juego", "Charla")
        self.assertEqual(
            pedir.llamadas,
            [("SetSceneName", {"sceneName": "Juego",
                               "newSceneName": "Charla"}, None)])

    def test_eliminar_una_escena(self):
        pedir = PedirFalso()
        escenas_obs.eliminar(pedir, "Juego")
        self.assertEqual(
            pedir.llamadas,
            [("RemoveScene", {"sceneName": "Juego"}, None)])

    def test_contar_las_fuentes_de_una_escena(self):
        gestor = GestorFalso({"Juego": [object(), object(), object()]})
        self.assertEqual(escenas_obs.contar_fuentes(gestor, "Juego"), 3)
        self.assertEqual(gestor.llamadas, [("Juego", None)])

    def test_el_inventario_conserva_el_orden_de_las_escenas(self):
        gestor = GestorFalso({
            "Juego": [object()],
            "Vacía": [],
        })
        self.assertEqual(
            escenas_obs.inventario(gestor, ("Juego", "Vacía")),
            (("Juego", 1), ("Vacía", 0)))


class TestDuplicar(unittest.TestCase):

    def setUp(self):
        self.fuentes = [
            _elemento(1, 0, "Cámara"),
            _elemento(2, 1, "Juego"),
            _elemento(3, 2, "Chat en el vídeo", visible=False),
        ]
        self.nuevos = iter((11, 12, 13))
        self.pedir = PedirFalso({
            "GetSceneItemList": {"sceneItems": [
                self.fuentes[2], self.fuentes[0], self.fuentes[1]]},
            "DuplicateSceneItem": lambda _datos: {
                "sceneItemId": next(self.nuevos)},
        })
        escenas_obs.duplicar(self.pedir, "Principal", "Principal - copia")

    def _de_tipo(self, tipo):
        return [datos for llamado, datos, _parada in self.pedir.llamadas
                if llamado == tipo]

    def test_crea_la_escena_de_destino(self):
        self.assertEqual(
            self._de_tipo("CreateScene"),
            [{"sceneName": "Principal - copia"}])

    def test_duplica_cada_fuente_en_el_orden_de_la_escena(self):
        self.assertEqual(
            [datos["sceneItemId"] for datos in self._de_tipo(
                "DuplicateSceneItem")],
            [1, 2, 3])

    def test_cada_duplicado_lleva_la_escena_de_destino(self):
        for datos in self._de_tipo("DuplicateSceneItem"):
            self.assertEqual(datos["sceneName"], "Principal")
            self.assertEqual(datos["destinationSceneName"],
                             "Principal - copia")

    def test_no_crea_fuentes_nuevas(self):
        self.assertEqual(self._de_tipo("CreateInput"), [])
        self.assertEqual(self._de_tipo("CreateSceneItem"), [])

    def test_conserva_el_indice(self):
        self.assertEqual(
            [datos["sceneItemIndex"] for datos in self._de_tipo(
                "SetSceneItemIndex")],
            [0, 1, 2])

    def test_conserva_la_posicion_el_tamano_y_la_visibilidad(self):
        transformaciones = self._de_tipo("SetSceneItemTransform")
        self.assertEqual(
            [datos["sceneItemTransform"]["positionX"]
             for datos in transformaciones], [0, 10, 20])
        self.assertEqual(
            [datos["sceneItemTransform"]["scaleX"]
             for datos in transformaciones], [1.5, 1.5, 1.5])
        self.assertEqual(
            [datos["sceneItemEnabled"] for datos in self._de_tipo(
                "SetSceneItemEnabled")], [True, True, False])

    def test_una_escena_vacia_solo_se_crea(self):
        pedir = PedirFalso({"GetSceneItemList": {"sceneItems": []}})
        escenas_obs.duplicar(pedir, "Vacía", "Vacía - copia")
        self.assertEqual(
            [tipo for tipo, _datos, _parada in pedir.llamadas],
            ["CreateScene", "GetSceneItemList"])


class TestMenuDeEscena(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()

    def _menu(self, llamadas):
        return escena_menu_escena.menu_de_escena(
            lambda: llamadas.append("cambiar"),
            lambda: llamadas.append("renombrar"),
            lambda: llamadas.append("duplicar"),
            lambda: llamadas.append("eliminar"),
            lambda: llamadas.append("guardar"))

    def _items(self, menu):
        return [item for item in menu.GetMenuItems()
                if item.GetItemLabelText()]

    def test_las_acciones_van_en_su_orden(self):
        llamadas = []
        menu = self._menu(llamadas)
        self.addCleanup(menu.Destroy)
        self.assertEqual(
            [item.GetItemLabelText() for item in self._items(menu)],
            ["Cambiar escena", "Cambiar nombre…", "Duplicar", "Eliminar",
             "Guardar imagen…"])

    def test_cada_elemento_muestra_su_tecla(self):
        llamadas = []
        menu = self._menu(llamadas)
        self.addCleanup(menu.Destroy)
        items = self._items(menu)
        self.assertEqual(
            [(item.GetAccel().GetFlags(), item.GetAccel().GetKeyCode())
             for item in items[:4]],
            [(wx.ACCEL_NORMAL, wx.WXK_RETURN),
             (wx.ACCEL_NORMAL, wx.WXK_F2),
             (wx.ACCEL_CTRL, ord("D")),
             (wx.ACCEL_NORMAL, wx.WXK_DELETE)])
        self.assertIsNone(items[4].GetAccel())

    def test_cada_entrada_llama_a_su_accion(self):
        for indice, accion in enumerate(
                ("cambiar", "renombrar", "duplicar", "eliminar", "guardar")):
            llamadas = []
            menu = self._menu(llamadas)
            self.addCleanup(menu.Destroy)
            item = self._items(menu)[indice]
            item.GetMenu().ProcessEvent(
                wx.CommandEvent(wx.EVT_MENU.typeId, item.GetId()))
            self.assertEqual(llamadas, [accion])


class _Evento:

    def __init__(self, codigo, ctrl=False, shift=False):
        self._codigo = codigo
        self._ctrl = ctrl
        self._shift = shift

    def GetKeyCode(self):
        return self._codigo

    def ControlDown(self):
        return self._ctrl

    def ShiftDown(self):
        return self._shift


class TestTeclasDeLaLista(unittest.TestCase):

    def test_intro_cambia_la_escena(self):
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(_Evento(wx.WXK_RETURN)),
            "cambiar")
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(_Evento(wx.WXK_NUMPAD_ENTER)),
            "cambiar")

    def test_f2_cambia_el_nombre(self):
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(_Evento(wx.WXK_F2)),
            "renombrar")

    def test_ctrl_d_duplica(self):
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(_Evento(ord("D"), ctrl=True)),
            "duplicar")

    def test_supr_elimina(self):
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(_Evento(wx.WXK_DELETE)),
            "eliminar")

    def test_la_tecla_aplicaciones_y_mayus_f10_abren_el_menu(self):
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(
                _Evento(wx.WXK_WINDOWS_MENU)), "menu")
        self.assertEqual(
            escena_menu_escena.accion_de_tecla(
                _Evento(wx.WXK_F10, shift=True)), "menu")

    def test_otra_tecla_no_hace_nada(self):
        self.assertIsNone(
            escena_menu_escena.accion_de_tecla(_Evento(wx.WXK_F3)))


if __name__ == "__main__":
    unittest.main()

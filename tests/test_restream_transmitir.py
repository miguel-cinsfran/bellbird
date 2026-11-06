"""Pruebas puras de las opciones de transmisión con perfiles de Restream."""

import unittest

from guyrapu.restream import transmitir
from guyrapu.restream.perfiles import Perfil
from guyrapu.restream.api import Canal


def _perfil(nombre="Uno", orientacion="vertical", canales=(1,), titulo="",
            descripcion=""):
    return Perfil(nombre=nombre, canales=canales, orientacion=orientacion,
                  titulo=titulo, descripcion=descripcion)


def _canal(identificador, plataforma, activo=True, url="", nombre=""):
    return Canal(id=identificador, plataforma_id=0, plataforma=plataforma,
                 nombre=nombre or f"canal {identificador}", url=url,
                 activo=activo)


class TestOpciones(unittest.TestCase):

    def test_sin_perfiles_solo_los_destinos_de_obs(self):
        self.assertEqual(transmitir.opciones([]), ("TikTok", "YouTube"))

    def test_con_uno_y_dos_perfiles_respeta_el_orden(self):
        uno = _perfil("Uno")
        dos = _perfil("Dos", "horizontal", (2,))
        self.assertEqual(transmitir.opciones([uno]),
                         ("TikTok", "YouTube", "restream:Uno"))
        self.assertEqual(transmitir.opciones([uno, dos]),
                         ("TikTok", "YouTube", "restream:Uno",
                          "restream:Dos"))

    def test_texto_visible_de_cada_opcion(self):
        self.assertEqual(transmitir.texto("TikTok"), "TikTok")
        self.assertEqual(transmitir.texto("YouTube"), "YouTube")
        self.assertEqual(transmitir.texto("restream:Uno"),
                         "Restream: Uno")

    def test_es_opcion_valida(self):
        for opcion in ("TikTok", "YouTube", "restream:Uno"):
            with self.subTest(opcion=opcion):
                self.assertTrue(transmitir.es_opcion_valida(opcion))
        for opcion in ("", "Twitch", "restream:", None):
            with self.subTest(opcion=opcion):
                self.assertFalse(transmitir.es_opcion_valida(opcion))

    def test_es_restream_y_su_nombre(self):
        self.assertTrue(transmitir.es_restream("restream:Uno"))
        self.assertEqual(transmitir.nombre_perfil("restream:Uno"), "Uno")
        self.assertFalse(transmitir.es_restream("TikTok"))
        self.assertEqual(transmitir.nombre_perfil("TikTok"), "")


class TestDestinoObs(unittest.TestCase):

    def test_destinos_de_obs_sin_perfil(self):
        self.assertEqual(transmitir.destino_obs("TikTok", []), "TikTok")
        self.assertEqual(transmitir.destino_obs("YouTube", []), "YouTube")

    def test_vertical_da_tiktok_y_horizontal_da_youtube(self):
        vertical = _perfil("Vertical", "vertical")
        horizontal = _perfil("Horizontal", "horizontal")
        self.assertEqual(
            transmitir.destino_obs("restream:Vertical",
                                   [vertical, horizontal]),
            "TikTok")
        self.assertEqual(
            transmitir.destino_obs("restream:Horizontal",
                                   [vertical, horizontal]),
            "YouTube")

    def test_perfil_de_una_opcion(self):
        uno = _perfil("Uno")
        dos = _perfil("Dos")
        self.assertIs(transmitir.perfil_de_opcion("restream:Dos", [uno, dos]),
                      dos)
        self.assertIsNone(transmitir.perfil_de_opcion("restream:Tres", [uno]))
        self.assertIsNone(transmitir.perfil_de_opcion("TikTok", [uno]))


class TestPlanDeCanales(unittest.TestCase):

    def test_los_que_ya_estan_bien_no_se_tocan(self):
        perfil = _perfil(canales=(1, 3))
        canales = [_canal(1, "YouTube", True), _canal(2, "YouTube", False),
                   _canal(3, "TikTok", True)]
        self.assertEqual(transmitir.plan_canales(perfil, canales), ())

    def test_activa_los_del_perfil_y_desactiva_los_demas(self):
        perfil = _perfil(canales=(1, 3))
        canales = [_canal(1, "YouTube", False), _canal(2, "YouTube", True),
                   _canal(3, "TikTok", False)]
        cambios = transmitir.plan_canales(perfil, canales)
        self.assertEqual(
            [(cambio.canal_id, cambio.activo, cambio.antes) for cambio in cambios],
            [(1, True, False), (2, False, True), (3, True, False)])

    def test_aplicar_el_plan_deja_activos_solo_los_del_perfil(self):
        perfil = _perfil(canales=(1, 3, 9))
        base = [_canal(1, "YouTube", True), _canal(2, "YouTube", True),
                _canal(3, "TikTok", False), _canal(4, "YouTube", False)]
        activos = {canal.id: canal.activo for canal in base}
        for cambio in transmitir.plan_canales(perfil, base):
            activos[cambio.canal_id] = cambio.activo
        self.assertEqual({canal_id for canal_id, activo in activos.items()
                          if activo}, {1, 3})


class TestUsuarioTikTok(unittest.TestCase):

    def test_sale_de_la_direccion_del_primer_tiktok_del_perfil(self):
        perfil = _perfil(canales=(1, 2))
        canales = [
            _canal(1, "YouTube", url="https://youtube.com/@canal"),
            _canal(2, "TikTok", url="https://www.tiktok.com/@amigo"),
        ]
        self.assertEqual(transmitir.usuario_tiktok(perfil, canales), "amigo")

    def test_respeta_el_orden_del_perfil(self):
        perfil = _perfil(canales=(2, 1))
        canales = [
            _canal(1, "TikTok", url="https://www.tiktok.com/@primero"),
            _canal(2, "TikTok", url="https://www.tiktok.com/@segundo"),
        ]
        self.assertEqual(transmitir.usuario_tiktok(perfil, canales), "segundo")

    def test_sin_direccion_prueba_con_el_nombre(self):
        perfil = _perfil(canales=(1,))
        canales = [_canal(1, "TikTok", url="", nombre="@otro")]
        self.assertEqual(transmitir.usuario_tiktok(perfil, canales), "otro")

    def test_sin_tiktok_devuelve_vacio(self):
        perfil = _perfil(canales=(1,))
        canales = [_canal(1, "YouTube", url="https://youtube.com/@canal")]
        self.assertEqual(transmitir.usuario_tiktok(perfil, canales), "")

    def test_canales_del_perfil_respeta_el_orden_y_salta_los_ajenos(self):
        perfil = _perfil(canales=(3, 1, 9))
        canales = [_canal(1, "YouTube"), _canal(2, "YouTube"),
                   _canal(3, "TikTok")]
        self.assertEqual([canal.id for canal in
                          transmitir.canales_del_perfil(perfil, canales)],
                         [3, 1])


if __name__ == "__main__":
    unittest.main()

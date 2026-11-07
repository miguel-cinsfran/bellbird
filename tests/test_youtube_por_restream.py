"""Pruebas del destino manual que lleva YouTube a través de Restream."""

import unittest

from guyrapu.restream import youtube_por_restream
from guyrapu.restream.api import Canal


class CuentaFalsa:

    def __init__(self, canales=()):
        self._canales = list(canales)
        self.llamadas = []

    def eliminar_canal(self, identificador):
        self.llamadas.append(("eliminar", identificador))

    def agregar_canal_manual(self, plataforma_id, nombre, servidor, clave):
        self.llamadas.append(("agregar", plataforma_id, nombre, servidor,
                              clave))
        return Canal(99, plataforma_id, "Custom RTMP", nombre, "", False)

    def activar_canal(self, identificador, activo):
        self.llamadas.append(("activar", identificador, activo))


class RestauradorFalso:

    def __init__(self):
        self.manuales = []

    def anotar_manual(self, identificador):
        self.manuales.append(identificador)


def _canal(identificador, nombre):
    return Canal(identificador, 29, "Custom RTMP", nombre, "", True)


class TestSobrantes(unittest.TestCase):

    def test_borra_solo_los_manuales_de_guyrapu(self):
        cuenta = CuentaFalsa([
            _canal(1, youtube_por_restream.NOMBRE_MANUAL),
            _canal(2, "Otro manual"),
            _canal(3, youtube_por_restream.NOMBRE_MANUAL),
        ])

        restantes = youtube_por_restream.borrar_sobrantes(
            cuenta, cuenta._canales)

        self.assertEqual(cuenta.llamadas, [("eliminar", 1), ("eliminar", 3)])
        self.assertEqual([canal.id for canal in restantes], [2])


class TestPrepararDestino(unittest.TestCase):

    def test_agrega_con_plataforma_29_anota_y_activa(self):
        cuenta = CuentaFalsa()
        restaurador = RestauradorFalso()
        destino = type("Destino", (), {
            "servidor": "rtmp://a.rtmp.youtube.com/live2",
            "clave": "clave-secreta"})
        preparar = youtube_por_restream.preparar_destino(cuenta, restaurador)

        identificador = preparar(None, destino)

        self.assertEqual(identificador, 99)
        self.assertEqual(cuenta.llamadas, [
            ("agregar", 29, youtube_por_restream.NOMBRE_MANUAL,
             "rtmp://a.rtmp.youtube.com/live2", "clave-secreta"),
            ("activar", 99, True),
        ])
        self.assertEqual(restaurador.manuales, [99])


if __name__ == "__main__":
    unittest.main()

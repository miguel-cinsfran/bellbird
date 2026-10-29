"""Prueba del aviso sonoro de la actualización de modelos, sin wx de verdad."""

import unittest
from unittest import mock

from bellbird.ai import proveedores
from bellbird.ui import preferencias_ia_lista


class _Panel:
    def Bind(self, _evento, _manejador, *_argumentos):
        pass


class _Boton:
    def __init__(self):
        self.habilitado = True
        self._padre = _Panel()

    def Bind(self, _evento, _manejador, *_argumentos):
        pass

    def GetParent(self):
        return self._padre

    def Disable(self):
        self.habilitado = False

    def Enable(self):
        self.habilitado = True

    def __bool__(self):
        return True


class _Temporizador:
    def __init__(self, _duenio):
        self.corriendo = False
        self.intervalo = 0

    def Start(self, intervalo):
        self.intervalo = intervalo
        self.corriendo = True

    def Stop(self):
        self.corriendo = False

    def IsRunning(self):
        return self.corriendo

    def GetInterval(self):
        return self.intervalo


class TestActualizacionModelosIA(unittest.TestCase):

    def _actualizacion(self):
        boton = _Boton()
        with mock.patch.object(
                preferencias_ia_lista.wx, "Timer", _Temporizador):
            return preferencias_ia_lista.ActualizacionModelosIA(
                boton, lambda: proveedores.por_id("gemini"),
                lambda muestra, marcas, proveedor: 3)

    def test_recibir_frena_el_temporizador_al_terminar(self):
        actualizacion = self._actualizacion()
        actualizacion._temporizador.Start(
            preferencias_ia_lista.INTERVALO_ANALIZANDO_MS)
        with mock.patch.object(
                preferencias_ia_lista.sondeo_gratis, "leer",
                return_value={}), \
                mock.patch.object(
                    preferencias_ia_lista._snd, "reproducir"), \
                mock.patch.object(preferencias_ia_lista, "anunciar"):
            actualizacion.recibir({"proveedores": {}})
        self.assertFalse(actualizacion._temporizador.IsRunning())


if __name__ == "__main__":
    unittest.main()

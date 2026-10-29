"""Pseudotraducción del diálogo entero de Preferencias.

Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
Recorre el diálogo con todas sus páginas y exige que lo único sin
envolver sea la unión de los pendientes que ya declaran las pruebas de
cada página (importados, no copiados) más los propios de este diálogo.
Cualquier texto nuevo sin envolver la pone en rojo.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.ai import catalogo
from ytchat.core import config
from ytchat.ui import gui, gui_preferencias
from ytchat.ui import preferencias_ia
from ytchat.ui import preferencias_ia_clave
from ytchat.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.test_preferencias_atajos import PENDIENTES_ATAJOS
from tests.test_preferencias_musica import (
    PENDIENTES_OTROS_MODULOS as PENDIENTES_MUSICA)
from tests.test_preferencias_voz import (
    PENDIENTES_OTROS_MODULOS as PENDIENTES_VOZ)
from tests.ventanas_prueba import destruir


# Textos que arma otro módulo y aparecen en el recorrido del diálogo
# entero: no se tocan acá. Las etiquetas de la página Estado salen de
# `ytchat/capture/estado_sesion.py` (ETIQUETAS) y el tema, de
# `ytchat/core/config.py` (listar_temas_sonido, valor de fábrica).
PENDIENTES_PROPIOS = (
    "Estado de conexión y tipo",
    "Título del vídeo o directo",
    "Canal o autor",
    "Espectadores ahora y en total",
    "Tiempo que lleva el directo",
    "Cuánto por detrás del directo va el reproductor",
    "Mensajes leídos",
    "Super Chats / regalos",
    "Mensajes en cola de lectura",
    "Velocidad y volumen de la voz",
    "Aviso de lectura silenciada",
    "Panel de chat para transmitir",
    "Mensajes automáticos",
    "Mensajes descartados",
    "Estado de la transmisión de OBS",
    "Estado de la grabación de OBS",
    "Escena al aire en OBS",
    "Música que suena",
    "Igualación del volumen de la música",
    "default",
)


# El aviso largo de Atajos trae saltos de línea del Wrap: se comparan los
# dos lados con los espacios normalizados.
def _normalizar(texto): return " ".join(texto.split())


class TestDialogoSinTextosSinEnvolver(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)
        # Nunca el Administrador de credenciales real.
        sin_clave = mock.patch.object(
            preferencias_ia_clave.claves, "leer", return_value="")
        sin_clave.start()
        self.addCleanup(sin_clave.stop)
        # Catálogo vacío: la lista muestra el aviso de lista vacía.
        catalogo_vacio = mock.patch.object(
            preferencias_ia.catalogo, "cargar",
            return_value={"version": catalogo.VERSION, "fecha": None,
                          "proveedores": {}})
        catalogo_vacio.start()
        self.addCleanup(catalogo_vacio.stop)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces", return_value=[]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(dialogo)
        esperados = (PENDIENTES_ATAJOS + PENDIENTES_MUSICA
                     + PENDIENTES_VOZ + PENDIENTES_PROPIOS)

        self.assertEqual(sorted(map(_normalizar, sin_marcar)),
                         sorted(map(_normalizar, esperados)))


if __name__ == "__main__":
    unittest.main()

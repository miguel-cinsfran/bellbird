"""Pseudotraducción de la parte de igualación de la ventana de música.

Abren ventanas: las corre el advisor en la otra PC, no se corren acá.
"""

import unittest

try:
    import wx
    from ytchat.ui import musica_ventana
    from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
    from tests.ventanas_prueba import destruir
    _HAY_WX = True
except Exception:
    wx = None
    musica_ventana = None
    _HAY_WX = False


class ControlFalso:
    """Mínimo para abrir la ventana y mover el progreso de igualación."""

    def __init__(self, biblioteca=None):
        self._biblio = biblioteca
        self._cola_visible = False
        self._filtros_guardados = (False, "", "coleccion")
        self._progreso_sonoridad = None
        self._midiendo = False

    def biblioteca(self, al_lista):
        al_lista(self._biblio)

    def carpeta_listas(self):
        return None

    def temas_de_lista(self, nombre):
        return ()

    def combos_atajo(self):
        return {}

    def estado(self):
        return None

    def cola_actual(self):
        return ()

    def cola_visible(self):
        return self._cola_visible

    def recordar_cola_visible(self, visible):
        self._cola_visible = bool(visible)

    def filtros_guardados(self):
        return self._filtros_guardados

    def recordar_filtros(self, visibles, artista, orden):
        self._filtros_guardados = (bool(visibles), artista, orden)

    def biblioteca_actual(self):
        return self._biblio

    def pedir_pendientes(self, biblioteca, al_pendientes):
        al_pendientes((), 0)

    def confirmar_pregunta(self, pendientes, total):
        return None

    def midiendo_igualacion(self):
        return self._midiendo


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestIgualandoPseudo(unittest.TestCase):
    """Ningún texto visible de la igualación sin pasar por gettext."""

    # Lo que arma otro módulo y esta ventana solo muestra: queda pendiente
    # hasta que se envuelva su módulo. Las filas de las listas no se
    # recorren: el ayudante solo lee opciones de Choice y columnas.
    PENDIENTES = (
        # ytchat/music/filtros.py, las opciones de «Ordenar por».
        "Orden de la colección",
        "Título",
        "Artista",
        "Más recientes primero",
        "Duración",
    )

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.control = None
        self.ventana = None

    def tearDown(self):
        if self.ventana is not None:
            self.ventana._cancelar_temporizador()
            self.ventana._parar_igualando()
            destruir(self.ventana)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            self.control = ControlFalso()
            self.ventana = musica_ventana.VentanaMusica(None, self.control)
            self.control._progreso_sonoridad = (3, 10)
            self.ventana._tic_igualando()
            sin_marcar = textos_sin_marcar(self.ventana)
        self.assertEqual(sorted(sin_marcar), sorted(self.PENDIENTES))

    def test_el_boton_rotulado_pasa_por_gettext(self):
        with con_pseudo():
            self.control = ControlFalso()
            self.ventana = musica_ventana.VentanaMusica(None, self.control)
            self.control._midiendo = True
            self.ventana._tic_igualando()
            rotulo = self.ventana.btn_igualar.GetLabel()
            # nombre_accesible pisa el nombre interno con el accesible.
            nombre = self.ventana.btn_igualar.GetName()
        self.assertEqual(rotulo, "[¡Detener la &igualación!]")
        self.assertEqual(nombre, "[¡Detener la igualación!]")


if __name__ == "__main__":
    unittest.main()

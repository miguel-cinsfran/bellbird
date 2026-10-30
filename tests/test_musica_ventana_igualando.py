"""Pseudotraducción de la parte de igualación de la ventana de música.

Abren ventanas.
"""

import unittest
from unittest import mock

try:
    import wx
    from bellbird.core.idioma import _
    from bellbird.music import pregunta_igualar
    from bellbird.music import sonoridad
    from bellbird.music.sonoridad import ResultadoIgualacion
    from bellbird.ui import musica_ventana
    from bellbird.ui import musica_ventana_igualando as igualando
    from bellbird.ui.musica_ventana_igualando import IgualandoVentanaMusica
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
        # bellbird/music/filtros.py, las opciones de «Ordenar por».
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


class TestPseudoAnunciosIgualando(unittest.TestCase):
    """Pseudotraducción de los avisos de la igualación.

    Maneja la mezcla con un control falso, sin ventanas, y exige lo
    anunciado marcado, con los datos presentes.
    """

    class Doble(IgualandoVentanaMusica):
        """La mezcla con un control falso, sin ventana."""

        def __init__(self, control):
            self._control = control
            self._preguntado_igualar = False

    def _manejar(self, control):
        return self.Doble(control)

    def test_detener_marca(self):
        control = mock.Mock()
        control.midiendo_igualacion.return_value = True
        with mock.patch.object(igualando, "anunciar") as anunciar:
            with con_pseudo():
                self._manejar(control).alternar_igualacion()
        control.detener_igualacion.assert_called_once_with()
        texto = anunciar.call_args.args[0]
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_sin_carpeta_marca(self):
        control = mock.Mock()
        control.midiendo_igualacion.return_value = False
        control.biblioteca_actual.return_value = None
        control.biblioteca.side_effect = lambda al: al(None)
        with mock.patch.object(igualando, "anunciar") as anunciar:
            with con_pseudo():
                self._manejar(control).alternar_igualacion()
        texto = anunciar.call_args.args[0]
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_empezar_marca_cada_codigo(self):
        casos = (
            (sonoridad.INICIO, 7),
            (sonoridad.YA_MIDIENDO, 7),
            (sonoridad.OPCION_APAGADA, 0),
            (sonoridad.SIN_FFMPEG, 0),
            (sonoridad.NADA_PENDIENTE, 0),
        )
        for codigo, total in casos:
            with self.subTest(codigo=codigo):
                control = mock.Mock()
                control.iniciar_medicion.return_value = ResultadoIgualacion(
                    codigo, total)
                with mock.patch.object(igualando, "anunciar") as anunciar, \
                        mock.patch.object(igualando, "_snd"):
                    with con_pseudo():
                        self._manejar(control)._empezar_igualacion(["a.mp3"])
                anunciar.assert_called_once()
                texto = anunciar.call_args.args[0]
                self.assertTrue(texto.startswith("[¡"), texto)
                if total:
                    self.assertIn("7", texto)

    def test_pregunta_muestra_texto_titulo_y_casilla_marcados(self):
        control = mock.Mock()
        control.confirmar_pregunta.return_value = (1, 5 * 1024 * 1024)
        capturado = {}

        class Dialogo:
            def __init__(self, parent, mensaje, titulo, estilo):
                capturado["mensaje"] = mensaje
                capturado["titulo"] = titulo

            def ShowCheckBox(self, texto):
                capturado["casilla"] = texto

            def ShowModal(self):
                return wx.ID_NO

            def IsCheckBoxChecked(self):
                return False

            def Destroy(self):
                pass

        with mock.patch.object(igualando.wx, "RichMessageDialog", Dialogo):
            with con_pseudo():
                self._manejar(control)._al_pendientes_pregunta(
                    ["a.mp3"], 5 * 1024 * 1024)
        for clave in ("mensaje", "titulo", "casilla"):
            with self.subTest(clave=clave):
                self.assertTrue(capturado[clave].startswith("[¡"),
                                capturado[clave])
        self.assertIn("Hay 1 canción", capturado["mensaje"])
        self.assertIn("5 MB", capturado["mensaje"])


if __name__ == "__main__":
    unittest.main()

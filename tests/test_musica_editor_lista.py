"""Pruebas puras del editor de listas, el submenú y `guardar_lista`.

No abren ventanas: comprueban las funciones de filas y orden, la validación
del nombre, la forma del submenú y el guardado en un directorio temporal.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.music import listas
from bellbird.music.listas import ErrorListas
from bellbird.music.modelo import Tema
from bellbird.ui import musica_menus
from bellbird.ui.musica_listas_propias import ListasPropiasMusica

try:
    import wx
    from bellbird.ui import musica_editor_lista
    from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
    from tests.ventanas_prueba import destruir
    _HAY_WX = True
except Exception:
    wx = None
    musica_editor_lista = None
    _HAY_WX = False


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFilas(unittest.TestCase):

    def test_los_de_la_lista_fuera_de_la_carpeta_van_primero(self):
        externo = Tema("C:/otro/x.mp3", "Externo")
        en_carpeta = Tema("C:/Musica/rock.mp3", "Rock")
        filas = musica_editor_lista.filas_editor((en_carpeta,), (externo,))
        self.assertEqual([(t.titulo, m) for t, m in filas],
                         [("Externo", True), ("Rock", False)])

    def test_la_carpeta_marca_lo_que_ya_estaba(self):
        tema = Tema("C:/Musica/rock.mp3", "Rock")
        filas = musica_editor_lista.filas_editor((tema,), (tema,))
        self.assertEqual([(t.titulo, m) for t, m in filas], [("Rock", True)])

    def test_sin_carpeta_queda_la_lista_marcada(self):
        externo = Tema("C:/otro/x.mp3", "Externo")
        filas = musica_editor_lista.filas_editor((), (externo,))
        self.assertEqual([(t.titulo, m) for t, m in filas],
                         [("Externo", True)])

    def test_la_primera_aparicion_no_se_duplica(self):
        tema = Tema("C:/Musica/rock.mp3", "Rock")
        filas = musica_editor_lista.filas_editor((tema, tema), (tema,))
        self.assertEqual(len(filas), 1)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestTemasAGuardar(unittest.TestCase):

    def test_primero_la_lista_y_despues_los_nuevos(self):
        a = Tema("C:/a.mp3", "A")
        b = Tema("C:/b.mp3", "B")
        salida = musica_editor_lista.temas_a_guardar(
            (a,), (b, a), {a.origen, b.origen})
        self.assertEqual([t.titulo for t in salida], ["A", "B"])

    def test_lo_desmarcado_no_se_guarda(self):
        a = Tema("C:/a.mp3", "A")
        b = Tema("C:/b.mp3", "B")
        salida = musica_editor_lista.temas_a_guardar(
            (a,), (a, b), {b.origen})
        self.assertEqual([t.titulo for t in salida], ["B"])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestValidarNombre(unittest.TestCase):

    def test_recorta_y_devuelve(self):
        self.assertEqual(
            musica_editor_lista.validar_nombre("  Favoritas "), "Favoritas")

    def test_vacio_lanza(self):
        with self.assertRaises(ErrorListas):
            musica_editor_lista.validar_nombre("   ")

    def test_prohibido_lanza(self):
        with self.assertRaises(ErrorListas):
            musica_editor_lista.validar_nombre("a/b")

    def test_mas_largo_que_sesenta_lanza(self):
        with self.assertRaises(ErrorListas) as exc:
            musica_editor_lista.validar_nombre("x" * 61)
        self.assertIn("más de 60", str(exc.exception))

    def test_sesenta_exactos_sirven(self):
        self.assertEqual(
            musica_editor_lista.validar_nombre("x" * 60), "x" * 60)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestAccionTecla(unittest.TestCase):

    def test_enter_en_la_lista_alterna(self):
        for codigo in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            with self.subTest(codigo=codigo):
                self.assertEqual(
                    musica_editor_lista.accion_tecla(codigo, True),
                    musica_editor_lista.ACCION_ALTERNAR)

    def test_enter_fuera_de_la_lista_sigue_su_camino(self):
        for codigo in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            with self.subTest(codigo=codigo):
                self.assertIsNone(
                    musica_editor_lista.accion_tecla(codigo, False))

    def test_espacio_en_la_lista_no_alterna(self):
        self.assertIsNone(
            musica_editor_lista.accion_tecla(wx.WXK_SPACE, True))

    def test_escape_cancela_aunque_no_este_en_la_lista(self):
        self.assertEqual(
            musica_editor_lista.accion_tecla(wx.WXK_ESCAPE, False),
            musica_editor_lista.ACCION_CANCELAR)

    def test_otra_tecla_sigue_su_camino(self):
        self.assertIsNone(
            musica_editor_lista.accion_tecla(wx.WXK_DOWN, True))


class TestSubmenu(unittest.TestCase):

    def test_una_entrada_por_lista_y_la_nueva_al_final(self):
        entradas = musica_menus.entradas_agregar_a_lista(("Mía", "Otra"))
        self.assertEqual([e for e, _a in entradas],
                         ["Mía", "Otra", "&Nueva lista…"])
        self.assertEqual(
            entradas[0][1],
            (musica_menus.ACCION_AGREGAR_A_LISTA, "Mía"))
        self.assertEqual(entradas[-1][1],
                         musica_menus.ACCION_NUEVA_LISTA_CON_TEMA)

    def test_sin_listas_solo_la_nueva(self):
        entradas = musica_menus.entradas_agregar_a_lista(())
        self.assertEqual([e for e, _a in entradas], ["&Nueva lista…"])


class _ControlGuardar(ListasPropiasMusica):
    """Doble mínimo: carpeta temporal y avisos en memoria."""

    def __init__(self, carpeta):
        self._carpeta = carpeta
        self.avisos = []

    def carpeta_listas(self):
        return self._carpeta

    def _avisar(self, texto):
        self.avisos.append(texto)


class TestGuardarLista(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "listas"
        self.a = self._mp3("a")
        self.tema_a = Tema(self.a, "A")

    def tearDown(self):
        self.tmp.cleanup()

    def _mp3(self, nombre):
        ruta = self.raiz / f"{nombre}.mp3"
        ruta.write_bytes(b"x")
        return str(ruta.resolve())

    def test_crea_la_lista_y_escribe_los_temas(self):
        control = _ControlGuardar(self.carpeta)
        control.guardar_lista("Nueva", [self.tema_a])
        temas, _ = listas.cargar(self.carpeta, "Nueva")
        self.assertEqual([t.titulo for t in temas], ["A"])

    def test_crear_con_nombre_existente_no_pisa(self):
        listas.crear(self.carpeta, "Nueva")
        control = _ControlGuardar(self.carpeta)
        control.guardar_lista("nueva", [self.tema_a])
        temas, _ = listas.cargar(self.carpeta, "Nueva")
        self.assertEqual(temas, ())
        self.assertTrue(any("Ya hay una lista con ese nombre" in a.texto
                            for a in control.avisos))

    def test_edita_y_renombra(self):
        listas.crear(self.carpeta, "Vieja")
        control = _ControlGuardar(self.carpeta)
        control.guardar_lista("Nueva", [self.tema_a], "Vieja")
        self.assertEqual(listas.nombres(self.carpeta), ["Nueva"])
        temas, _ = listas.cargar(self.carpeta, "Nueva")
        self.assertEqual([t.titulo for t in temas], ["A"])

    def test_edita_sin_cambiar_el_nombre(self):
        listas.crear(self.carpeta, "Vieja")
        control = _ControlGuardar(self.carpeta)
        control.guardar_lista("Vieja", [self.tema_a], "Vieja")
        temas, _ = listas.cargar(self.carpeta, "Vieja")
        self.assertEqual([t.titulo for t in temas], ["A"])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestEditorPseudo(unittest.TestCase):
    """Ningún texto visible del editor sin pasar por gettext."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.dialogo = None

    def tearDown(self):
        if self.dialogo is not None:
            destruir(self.dialogo)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            self.dialogo = musica_editor_lista.DialogoEditorLista(
                None, "Mía",
                (Tema("C:/Musica/rock.mp3", "Rock", artista="Ana"),), ())
            sin_marcar = textos_sin_marcar(
                self.dialogo, propios=("Mía", "Rock", "Ana"))
        self.assertEqual([], sin_marcar)

    def test_el_nombre_largo_se_anuncia_marcado(self):
        with con_pseudo():
            self.dialogo = musica_editor_lista.DialogoEditorLista(None)
            self.dialogo.txt_nombre.SetValue("x" * 61)
            with mock.patch.object(
                    musica_editor_lista, "anunciar") as anunciar:
                self.dialogo._guardar()
        anunciar.assert_called_once_with(
            "[¡El nombre no puede tener más de 60 caracteres!]")


if __name__ == "__main__":
    unittest.main()

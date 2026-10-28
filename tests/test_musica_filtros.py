"""Pruebas de los filtros y el orden de la música (filtros.py), sin wx.

La última clase abre ventanas: la corre el advisor en la otra PC, no se
corre acá.
"""

import unittest
from unittest import mock

from ytchat.music import filtros
from ytchat.music.modelo import Tema

try:
    import wx
    from ytchat.ui import musica_filtros
    from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
    from tests.ventanas_prueba import destruir
    _HAY_WX = True
except Exception:
    _HAY_WX = False


def _tema(n, **campos):
    return Tema(f"C:/musica/tema{n}.mp3", f"Tema {n}", **campos)


class TestArtistasDe(unittest.TestCase):

    def test_separa_por_y_comercial(self):
        self.assertEqual(
            filtros.artistas_de(_tema(1, artista="Lytos & Brock Ansiolitiko")),
            ("Lytos", "Brock Ansiolitiko"))

    def test_separa_por_feat_con_y_sin_punto_ni_mayusculas(self):
        for artista in ("Ana feat. Luis", "Ana FEAT Luis", "Ana Ft. Luis",
                        "Ana ft Luis"):
            with self.subTest(artista=artista):
                self.assertEqual(
                    filtros.artistas_de(_tema(1, artista=artista)),
                    ("Ana", "Luis"))

    def test_separa_por_coma_sin_partir_la_y(self):
        self.assertEqual(
            filtros.artistas_de(_tema(1, artista="Ana, Luis y Pedro")),
            ("Ana", "Luis y Pedro"))

    def test_artista_vacio_o_con_espacios_no_da_nombres(self):
        self.assertEqual(filtros.artistas_de(_tema(1, artista="")), ())
        self.assertEqual(filtros.artistas_de(_tema(1, artista="   ")), ())

    def test_quita_espacios_sobrantes_y_no_repite(self):
        self.assertEqual(
            filtros.artistas_de(_tema(1, artista="  Ana  &  Ana  ")),
            ("Ana",))

    def test_mezcla_de_separadores(self):
        self.assertEqual(
            filtros.artistas_de(
                _tema(1, artista="Ana ft. Luis & Pedro, María")),
            ("Ana", "Luis", "Pedro", "María"))


class TestOpcionesArtistas(unittest.TestCase):

    def _temas(self):
        return (
            _tema(1, artista="Lou Cornago"),
            _tema(2, artista="Lou Cornago"),
            _tema(3, artista="Lou Cornago"),
            _tema(4, artista="Ana"),
            _tema(5, artista=""),
            _tema(6, artista=""),
            _tema(7, artista="Lytos & Brock Ansiolitiko"),
            _tema(8, artista="lytos"),
        )

    def test_primero_todas_y_al_final_sin_artista(self):
        opciones = filtros.opciones_artistas(self._temas())
        self.assertEqual(opciones[0], (filtros.TODAS, "Todas las canciones"))
        self.assertEqual(opciones[-1][1], "Sin artista, 2 canciones")

    def test_cantidades_y_singular(self):
        opciones = dict(filtros.opciones_artistas(self._temas()))
        self.assertEqual(opciones["lou cornago"], "Lou Cornago, 3 canciones")
        self.assertEqual(opciones["ana"], "Ana, 1 canción")

    def test_los_artistas_combinados_cuentan_en_cada_uno(self):
        opciones = dict(filtros.opciones_artistas(self._temas()))
        self.assertEqual(opciones["lytos"], "Lytos, 2 canciones")
        self.assertEqual(opciones["brock ansiolitiko"],
                         "Brock Ansiolitiko, 1 canción")

    def test_orden_alfabetico_sin_tildes_ni_mayusculas(self):
        temas = (
            _tema(1, artista="Zeta"),
            _tema(2, artista="ángel"),
            _tema(3, artista="Beto"),
            _tema(4, artista="Ávila"),
        )
        etiquetas = [etiqueta for _clave, etiqueta
                     in filtros.opciones_artistas(temas)[1:]]
        self.assertEqual(etiquetas, [
            "ángel, 1 canción", "Ávila, 1 canción", "Beto, 1 canción",
            "Zeta, 1 canción"])

    def test_sin_canciones_sin_artista_no_agrega_la_fila(self):
        opciones = filtros.opciones_artistas((_tema(1, artista="Ana"),))
        self.assertEqual([clave for clave, _etiqueta in opciones],
                         [filtros.TODAS, "ana"])


class TestFiltrarPorArtista(unittest.TestCase):

    def _temas(self):
        return (
            _tema(1, artista="Lytos & Brock Ansiolitiko"),
            _tema(2, artista="Ana"),
            _tema(3, artista=""),
        )

    def test_todas_devuelve_todo(self):
        temas = self._temas()
        self.assertEqual(filtros.filtrar_por_artista(temas, filtros.TODAS),
                         temas)

    def test_un_artista_deja_solo_los_suyos(self):
        temas = self._temas()
        self.assertEqual(
            [tema.titulo for tema
             in filtros.filtrar_por_artista(temas, "brock ansiolitiko")],
            ["Tema 1"])
        self.assertEqual(
            [tema.titulo for tema in filtros.filtrar_por_artista(temas, "ana")],
            ["Tema 2"])

    def test_sin_artista_deja_solo_los_que_no_tienen(self):
        self.assertEqual(
            [tema.titulo for tema
             in filtros.filtrar_por_artista(self._temas(),
                                            filtros.SIN_ARTISTA)],
            ["Tema 3"])

    def test_nunca_devuelve_un_tema_sin_ese_artista(self):
        temas = tuple(
            _tema(n, artista=artista)
            for n, artista in enumerate(
                ("Lytos & Brock Ansiolitiko", "Ana feat. Luis", "Beto",
                 "", "Ana"), start=1))
        for clave, _etiqueta in filtros.opciones_artistas(temas):
            with self.subTest(clave=clave):
                resultado = filtros.filtrar_por_artista(temas, clave)
                for tema in resultado:
                    with self.subTest(tema=tema.titulo):
                        if clave == filtros.TODAS:
                            continue
                        if clave == filtros.SIN_ARTISTA:
                            self.assertEqual(filtros.artistas_de(tema), ())
                            continue
                        claves = [filtros.clave_artista(nombre)
                                  for nombre in filtros.artistas_de(tema)]
                        self.assertIn(clave, claves)


class TestOrdenar(unittest.TestCase):

    def _temas(self):
        return (
            _tema(1, artista="Zeta", fecha_ns=1, duracion_ms=3000),
            _tema(2, artista="Alfa", fecha_ns=3, duracion_ms=1000),
            _tema(3, artista="Beta", fecha_ns=2, duracion_ms=2000),
        )

    def test_orden_de_la_coleccion_devuelve_tal_cual(self):
        temas = self._temas()
        self.assertEqual(
            filtros.ordenar(temas, filtros.CRITERIO_COLECCION), temas)

    def test_titulo_sin_tildes_ni_mayusculas(self):
        temas = (Tema("a", "beta"), Tema("b", "Ángel"), Tema("c", "Alfa"))
        self.assertEqual(
            [tema.titulo for tema in
             filtros.ordenar(temas, filtros.CRITERIO_TITULO)],
            ["Alfa", "Ángel", "beta"])

    def test_artista_sin_tildes_ni_mayusculas(self):
        temas = (_tema(1, artista="Zeta"), _tema(2, artista="ángel"),
                 _tema(3, artista="Beto"))
        self.assertEqual(
            [tema.artista for tema in
             filtros.ordenar(temas, filtros.CRITERIO_ARTISTA)],
            ["ángel", "Beto", "Zeta"])

    def test_mas_recientes_primero(self):
        self.assertEqual(
            [tema.titulo for tema in
             filtros.ordenar(self._temas(), filtros.CRITERIO_RECIENTES)],
            ["Tema 2", "Tema 3", "Tema 1"])

    def test_duracion_ascendente(self):
        self.assertEqual(
            [tema.titulo for tema in
             filtros.ordenar(self._temas(), filtros.CRITERIO_DURACION)],
            ["Tema 2", "Tema 3", "Tema 1"])

    def test_es_estable(self):
        temas = (Tema("a", "Igual"), Tema("b", "Igual"), Tema("c", "Igual"))
        self.assertEqual(
            [tema.origen for tema in
             filtros.ordenar(temas, filtros.CRITERIO_TITULO)],
            ["a", "b", "c"])

    def test_criterio_desconocido_deja_el_orden_de_la_coleccion(self):
        temas = self._temas()
        self.assertEqual(filtros.ordenar(temas, "inventado"), temas)

    def test_devuelve_los_mismos_temas_que_recibe(self):
        temas = self._temas()
        for criterio, _etiqueta in filtros.CRITERIOS:
            with self.subTest(criterio=criterio):
                resultado = filtros.ordenar(temas, criterio)
                self.assertEqual(len(resultado), len(temas))
                self.assertEqual({tema.origen for tema in resultado},
                                 {tema.origen for tema in temas})


class TestNormalizarCriterio(unittest.TestCase):

    def test_los_validos_se_respetan(self):
        for criterio, _etiqueta in filtros.CRITERIOS:
            self.assertEqual(filtros.normalizar_criterio(criterio), criterio)

    def test_lo_desconocido_cae_al_orden_de_la_coleccion(self):
        for valor in ("", None, "inventado"):
            with self.subTest(valor=valor):
                self.assertEqual(filtros.normalizar_criterio(valor),
                                 filtros.CRITERIO_COLECCION)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFiltrosPseudo(unittest.TestCase):
    """Ningún texto visible de los filtros sin pasar por gettext."""

    # Lo que arma otro módulo y estos cuadros solo muestran: queda
    # pendiente hasta que se envuelva su módulo.
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
        self.marco = None

    def tearDown(self):
        if self.marco is not None:
            destruir(self.marco)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            self.marco = wx.Frame(None)
            musica_filtros.FiltrosMusica(self.marco)
            sin_marcar = textos_sin_marcar(self.marco)
        self.assertEqual(sorted(sin_marcar), sorted(self.PENDIENTES))


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoAvisosFiltros(unittest.TestCase):
    """Pseudotraducción de los avisos de los filtros.

    Dispara el camino real y exige lo avisado marcado. Abre ventanas.
    """

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.marco = None

    def tearDown(self):
        if self.marco is not None:
            destruir(self.marco)

    def test_mostrar_y_ocultar_marcan(self):
        self.marco = wx.Frame(None)
        avisos = mock.Mock()
        with con_pseudo():
            cuadros = musica_filtros.FiltrosMusica(
                self.marco, avisar=avisos, recordar=mock.Mock())
            cuadros._aplicar_visibilidad(avisar=True, enfocar=False)
            primero = avisos.call_args.args[0]
            cuadros.visibles = not cuadros.visibles
            cuadros._aplicar_visibilidad(avisar=True, enfocar=False)
            segundo = avisos.call_args.args[0]
        self.assertTrue(primero.startswith("[¡"), primero)
        self.assertTrue(segundo.startswith("[¡"), segundo)


if __name__ == "__main__":
    unittest.main()

"""Avisos de avance y de descarga quieta, sin wx.

La lógica pura recibe la lista de descargas y el instante en cada vuelta.
"""

import unittest
from types import SimpleNamespace

from guyrapu.downloads.progreso_anuncio import AnunciadorProgreso


def _item(ident, progreso=0.0, estado="descargando", procesando=False,
          nombre="", url=None):
    url = url or f"https://ejemplo/{ident}"
    return SimpleNamespace(id=ident, progreso=progreso, estado=estado,
                           procesando=procesando, nombre=nombre or url, url=url)


def _textos(avisos):
    return [aviso.texto for aviso in avisos]


def _tipos(avisos):
    return [aviso.tipo for aviso in avisos]


class PruebasProgresoAnuncio(unittest.TestCase):
    def test_anuncia_cada_multiplo_de_diez_hasta_noventa_y_el_cien_no(self):
        anunciador = AnunciadorProgreso()
        anunciador.avisos([_item("a", 0.0)], 0.0)
        anunciados = []
        for paso, progreso in enumerate(range(10, 100, 10), start=1):
            avisos = anunciador.avisos([_item("a", float(progreso))], float(paso))
            anunciados.extend(_textos(avisos))
        self.assertEqual(anunciados, [f"{p} por ciento" for p in range(10, 100, 10)])
        self.assertEqual(anunciador.avisos([_item("a", 100.0)], 20.0), [])

    def test_un_salto_anuncia_solo_el_ultimo_multiplo(self):
        anunciador = AnunciadorProgreso()
        anunciador.avisos([_item("a", 10.0)], 0.0)
        avisos = anunciador.avisos([_item("a", 40.0)], 1.0)
        self.assertEqual(_textos(avisos), ["40 por ciento"])

    def test_queda_quieta_a_los_quince_y_a_los_treinta_y_no_antes(self):
        anunciador = AnunciadorProgreso()
        anunciador.avisos([_item("a", 0.0)], 0.0)
        self.assertEqual(anunciador.avisos([_item("a", 0.0)], 14.0), [])
        primera = anunciador.avisos([_item("a", 0.0)], 15.0)
        self.assertEqual(_textos(primera), ["Descarga en curso"])
        self.assertEqual(_tipos(primera), ["quieta"])
        self.assertEqual(anunciador.avisos([_item("a", 0.0)], 29.0), [])
        segunda = anunciador.avisos([_item("a", 0.0)], 30.0)
        self.assertEqual(_textos(segunda), ["Descarga en curso"])

    def test_deja_de_avisar_al_pasar_del_uno_por_ciento(self):
        anunciador = AnunciadorProgreso()
        anunciador.avisos([_item("a", 0.0)], 0.0)
        anunciador.avisos([_item("a", 0.0)], 15.0)
        anunciador.avisos([_item("a", 1.0)], 20.0)
        self.assertEqual(anunciador.avisos([_item("a", 1.0)], 45.0), [])

    def test_el_nombre_va_delante_solo_con_mas_de_una_en_curso(self):
        anunciador = AnunciadorProgreso()
        una = _item("a", 0.0, nombre="Uno", url="https://ejemplo/a")
        anunciador.avisos([una], 0.0)
        avisos = anunciador.avisos(
            [_item("a", 10.0, nombre="Uno", url="https://ejemplo/a")], 1.0)
        self.assertEqual(_textos(avisos), ["10 por ciento"])

        anunciador = AnunciadorProgreso()
        anunciador.avisos(
            [_item("a", 0.0, nombre="Uno", url="https://ejemplo/a"),
             _item("b", 0.0, nombre="Dos", url="https://ejemplo/b")], 0.0)
        avisos = anunciador.avisos(
            [_item("a", 10.0, nombre="Uno", url="https://ejemplo/a"),
             _item("b", 10.0, nombre="Dos", url="https://ejemplo/b")], 1.0)
        self.assertEqual(_textos(avisos),
                         ["Uno: 10 por ciento", "Dos: 10 por ciento"])

    def test_sin_nombre_propio_el_aviso_va_sin_nombre(self):
        anunciador = AnunciadorProgreso()
        anunciador.avisos(
            [_item("a", 0.0, nombre="Uno", url="https://ejemplo/a"),
             _item("b", 0.0, nombre="", url="https://ejemplo/b")], 0.0)
        avisos = anunciador.avisos(
            [_item("a", 10.0, nombre="Uno", url="https://ejemplo/a"),
             _item("b", 10.0, nombre="", url="https://ejemplo/b")], 1.0)
        self.assertEqual(_textos(avisos),
                         ["Uno: 10 por ciento", "10 por ciento"])

    def test_el_nombre_tambien_va_delante_en_la_descarga_quieta(self):
        anunciador = AnunciadorProgreso()
        anunciador.avisos(
            [_item("a", 0.0, nombre="Uno", url="https://ejemplo/a"),
             _item("b", 0.0, nombre="Dos", url="https://ejemplo/b")], 0.0)
        avisos = anunciador.avisos(
            [_item("a", 0.0, nombre="Uno", url="https://ejemplo/a"),
             _item("b", 0.0, nombre="Dos", url="https://ejemplo/b")], 15.0)
        self.assertEqual(_textos(avisos),
                         ["Uno: descarga en curso",
                          "Dos: descarga en curso"])

    def test_una_descarga_en_procesando_no_cuenta(self):
        anunciador = AnunciadorProgreso()
        procesando = _item("a", 50.0, procesando=True)
        self.assertEqual(anunciador.avisos([procesando], 0.0), [])
        self.assertEqual(anunciador.avisos([procesando], 100.0), [])

    def test_la_secuencia_nunca_baja_ni_se_repite_si_el_progreso_retrocede(self):
        anunciador = AnunciadorProgreso()
        anunciados = []
        for instante, progreso in enumerate((0.0, 10.0, 40.0, 15.0, 50.0,
                                             20.0, 60.0)):
            avisos = anunciador.avisos([_item("a", progreso)], float(instante))
            anunciados.extend(int(texto.split()[0]) for texto in _textos(avisos))
        self.assertEqual(anunciados, [10, 40, 50, 60])
        self.assertEqual(anunciados, sorted(set(anunciados)))

    def test_al_empezar_a_vigilar_no_anuncia_los_multiplos_ya_pasados(self):
        anunciador = AnunciadorProgreso()
        self.assertEqual(anunciador.avisos([_item("a", 30.0)], 0.0), [])
        avisos = anunciador.avisos([_item("a", 40.0)], 1.0)
        self.assertEqual(_textos(avisos), ["40 por ciento"])


if __name__ == "__main__":
    unittest.main()

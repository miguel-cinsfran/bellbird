"""Pruebas de la lógica pura de filas de descargas, sin wx."""

import unittest

from bellbird.downloads import filas_descargas
from bellbird.downloads.descargas import ItemDescarga


def _item(ident, estado="en_cola", nombre=None, url=None, mensaje="",
          progreso=0.0, rutas=None, carpeta="C:/Descargas"):
    return ItemDescarga(
        ident, url or f"https://www.youtube.com/watch?v={ident}",
        "video", estado=estado, progreso=progreso, mensaje=mensaje,
        nombre=nombre or f"{ident}.mp4", carpeta=carpeta,
        rutas=list(rutas) if rutas else [])


def _entrada(ident=None, estado="completado", nombre="video.mp4",
             fecha="2026-10-30T08:33:00", url=None):
    entrada = {"nombre": nombre, "fecha": fecha, "estado": estado,
               "url": url if url is not None else "https://www.youtube.com/watch?v=abc",
               "carpeta": "C:/Descargas", "ruta": "C:/Descargas/video.mp4"}
    if ident is not None:
        entrada["id"] = ident
    return entrada


class TestConstruir(unittest.TestCase):

    def test_no_duplica_item_terminado_con_historial(self):
        item = _item("abc", estado="completado", mensaje="listo",
                     rutas=["C:/Descargas/video.mp4"])
        entrada = _entrada("abc", estado="completado")
        filas = filas_descargas.construir([item], [entrada])
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].clave, "abc")
        self.assertEqual(filas[0].mensaje, "listo")
        self.assertEqual(filas[0].nombre, "video.mp4")

    def test_respeta_orden_activos_y_terminados_recientes(self):
        primero = _item("uno", estado="en_cola")
        segundo = _item("dos", estado="descargando")
        tercero = _item("tres", estado="en_cola")
        vieja = _entrada("vieja", fecha="2026-10-29T08:00:00", nombre="vieja.mp4")
        nueva = _entrada("nueva", fecha="2026-10-30T08:00:00", nombre="nueva.mp4")
        filas = filas_descargas.construir([primero, segundo, tercero], [vieja, nueva])
        self.assertEqual([f.clave for f in filas],
                         ["dos", "uno", "tres", "nueva", "vieja"])

    def test_entrada_vieja_sin_id_usa_fecha_mas_nombre(self):
        entrada = {"nombre": "vieja.mp4", "fecha": "2026-10-29T08:00:00",
                   "estado": "completado", "url": "dQw4w9WgXcQ",
                   "carpeta": "", "ruta": ""}
        filas = filas_descargas.construir([], [entrada])
        self.assertEqual(filas[0].clave, "2026-10-29T08:00:00|vieja.mp4")

    def test_dos_entradas_viejas_iguales_dan_una_sola_fila(self):
        entrada = {"nombre": "vieja.mp4", "fecha": "2026-10-29T08:00:00",
                   "estado": "completado", "url": "dQw4w9WgXcQ",
                   "carpeta": "", "ruta": ""}
        filas = filas_descargas.construir([], [dict(entrada), dict(entrada)])
        self.assertEqual([f.clave for f in filas], ["2026-10-29T08:00:00|vieja.mp4"])


class TestFiltrarCantidades(unittest.TestCase):

    def _filas(self):
        return [
            filas_descargas.Fila("a", "descargando", 10.0, "a", "", "http://x", "", "", "", None),
            filas_descargas.Fila("b", "en_cola", 0.0, "b", "", "http://x", "", "", "", None),
            filas_descargas.Fila("c", "completado", 100.0, "c", "", "http://x", "", "", "", None),
            filas_descargas.Fila("d", "error", 0.0, "d", "", "http://x", "", "", "", None),
            filas_descargas.Fila("e", "parcial", 0.0, "e", "", "http://x", "", "", "", None),
            filas_descargas.Fila("f", "cancelado", 0.0, "f", "", "http://x", "", "", "", None),
        ]

    def test_filtrar_un_caso_por_estado(self):
        filas = self._filas()
        self.assertEqual([f.clave for f in filas_descargas.filtrar(filas, filas_descargas.TODAS)],
                         ["a", "b", "c", "d", "e", "f"])
        self.assertEqual([f.clave for f in filas_descargas.filtrar(filas, filas_descargas.EN_CURSO)], ["a"])
        self.assertEqual([f.clave for f in filas_descargas.filtrar(filas, filas_descargas.EN_ESPERA)], ["b"])
        self.assertEqual([f.clave for f in filas_descargas.filtrar(filas, filas_descargas.COMPLETADAS)], ["c"])
        self.assertEqual([f.clave for f in filas_descargas.filtrar(filas, filas_descargas.CON_ERRORES)],
                         ["d", "e"])

    def test_cantidades(self):
        cantidades = filas_descargas.cantidades(self._filas())
        self.assertEqual(cantidades[filas_descargas.TODAS], 6)
        self.assertEqual(cantidades[filas_descargas.EN_CURSO], 1)
        self.assertEqual(cantidades[filas_descargas.EN_ESPERA], 1)
        self.assertEqual(cantidades[filas_descargas.COMPLETADAS], 1)
        self.assertEqual(cantidades[filas_descargas.CON_ERRORES], 2)


class TestAcciones(unittest.TestCase):

    def _fila(self, estado, url="https://www.youtube.com/watch?v=abc",
              ruta="C:/D/video.mp4", carpeta="C:/D"):
        return filas_descargas.Fila("k", estado, 0.0, "n", "", url, ruta,
                                    carpeta, "", None)

    def test_tabla_de_estados(self):
        self.assertEqual(filas_descargas.acciones(self._fila("descargando")),
                         ("cancelar", "copiar"))
        self.assertEqual(filas_descargas.acciones(self._fila("en_cola")),
                         ("cancelar", "copiar"))
        self.assertEqual(filas_descargas.acciones(self._fila("completado")),
                         ("abrir_archivo", "abrir_carpeta", "volver_a_descargar",
                          "copiar", "eliminar"))
        self.assertEqual(filas_descargas.acciones(self._fila("parcial")),
                         ("abrir_carpeta", "reintentar", "copiar", "eliminar"))
        self.assertEqual(filas_descargas.acciones(self._fila("error")),
                         ("reintentar", "copiar", "eliminar"))
        self.assertEqual(filas_descargas.acciones(self._fila("cancelado")),
                         ("reintentar", "copiar", "eliminar"))

    def test_sin_url_no_van_las_que_descargan(self):
        fila = self._fila("completado", url="")
        self.assertEqual(filas_descargas.acciones(fila),
                         ("abrir_archivo", "abrir_carpeta", "eliminar"))
        fila = self._fila("error", url="basura")
        self.assertEqual(filas_descargas.acciones(fila), ("eliminar",))

    def test_sin_ruta_no_va_abrir_archivo(self):
        fila = self._fila("completado", ruta="")
        self.assertNotIn("abrir_archivo", filas_descargas.acciones(fila))
        self.assertIn("abrir_carpeta", filas_descargas.acciones(fila))

    def test_sin_ruta_ni_carpeta_no_va_abrir_carpeta(self):
        fila = self._fila("completado", ruta="", carpeta="")
        acciones = filas_descargas.acciones(fila)
        self.assertNotIn("abrir_archivo", acciones)
        self.assertNotIn("abrir_carpeta", acciones)


class TestUrlUtilizable(unittest.TestCase):

    def test_enlace_completo_pasa_tal_cual(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(filas_descargas.url_utilizable(url), url)

    def test_identificador_viejo_da_youtube(self):
        self.assertEqual(filas_descargas.url_utilizable("dQw4w9WgXcQ"),
                         "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_segmento_que_no_sirve_da_vacio(self):
        self.assertEqual(filas_descargas.url_utilizable("sin identificador"), "")
        self.assertEqual(filas_descargas.url_utilizable(""), "")


def _aplicar(claves, pasos):
    actual = list(claves)
    for paso in pasos:
        if paso[0] == "borrar":
            del actual[paso[1]]
        else:
            actual.insert(paso[1], paso[2])
    return actual


class TestPasos(unittest.TestCase):

    def test_lista_igual_no_da_pasos(self):
        self.assertEqual(filas_descargas.pasos_para_sincronizar(["a", "b"], ["a", "b"]), [])

    def test_aplicar_da_la_lista_deseada(self):
        casos = [
            ([], []),
            ([], ["a"]),
            (["a"], []),
            (["a", "b", "c"], ["a", "b", "c"]),
            (["a", "b", "c"], ["c", "b", "a"]),
            (["a", "b", "c"], ["b"]),
            (["b"], ["a", "b", "c"]),
            (["a", "b"], ["b", "a", "c"]),
            (["a", "b", "c", "d"], ["b", "d", "e"]),
            (["x", "y"], ["y", "x", "z", "w"]),
        ]
        for actuales, deseadas in casos:
            with self.subTest(actuales=actuales, deseadas=deseadas):
                pasos = filas_descargas.pasos_para_sincronizar(actuales, deseadas)
                self.assertEqual(_aplicar(actuales, pasos), deseadas)
                if actuales == deseadas:
                    self.assertEqual(pasos, [])


class TestFechaLegible(unittest.TestCase):

    def test_fecha_valida(self):
        self.assertEqual(filas_descargas.fecha_legible("2026-10-30T08:33:00"),
                         "30/10/2026 08:33")

    def test_fecha_invalida_pasa_tal_cual(self):
        self.assertEqual(filas_descargas.fecha_legible("no es fecha"), "no es fecha")


if __name__ == "__main__":
    unittest.main()

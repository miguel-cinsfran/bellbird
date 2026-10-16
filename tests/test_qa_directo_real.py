"""Pruebas de la lógica pura de qa/directo_real.py, sin red ni ventanas."""

import importlib.util
import unittest
from pathlib import Path

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "directo_real.py"
_paquete = importlib.util.spec_from_file_location(
    "directo_real_qa", _RUTA)
directo_real = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(directo_real)


class TestArmarTitulo(unittest.TestCase):

    def test_con_hora(self):
        self.assertEqual(directo_real.armar_titulo("20:15"),
                         "Prueba de YTChat 20:15")

    def test_sin_hora_no_deja_basura(self):
        self.assertEqual(directo_real.armar_titulo("  "), "Prueba de YTChat")


class TestEsBorrable(unittest.TestCase):

    def test_lo_propio_no_listado_se_borra(self):
        self.assertTrue(directo_real.es_borrable(
            "Prueba de YTChat 20:15", "unlisted"))

    def test_exige_privacidad_no_listada(self):
        self.assertFalse(directo_real.es_borrable(
            "Prueba de YTChat 20:15", "public"))
        self.assertFalse(directo_real.es_borrable(
            "Prueba de YTChat 20:15", "private"))
        self.assertFalse(directo_real.es_borrable(
            "Prueba de YTChat 20:15", ""))

    def test_exige_titulo_de_la_prueba(self):
        self.assertFalse(directo_real.es_borrable(
            "Mi directo", "unlisted"))
        self.assertFalse(directo_real.es_borrable("", "unlisted"))


class TestArmarTituloLista(unittest.TestCase):

    def test_con_hora(self):
        self.assertEqual(directo_real.armar_titulo_lista("20:15"),
                         "Prueba de YTChat lista 20:15")

    def test_sin_hora_no_deja_basura(self):
        self.assertEqual(directo_real.armar_titulo_lista("  "),
                         "Prueba de YTChat lista")


class TestEsListaBorrable(unittest.TestCase):

    def test_lo_propio_privado_se_borra(self):
        self.assertTrue(directo_real.es_lista_borrable(
            "Prueba de YTChat lista 20:15", "private"))

    def test_exige_privacidad_privada(self):
        self.assertFalse(directo_real.es_lista_borrable(
            "Prueba de YTChat lista 20:15", "public"))
        self.assertFalse(directo_real.es_lista_borrable(
            "Prueba de YTChat lista 20:15", "unlisted"))
        self.assertFalse(directo_real.es_lista_borrable(
            "Prueba de YTChat lista 20:15", ""))

    def test_exige_titulo_de_la_prueba(self):
        self.assertFalse(directo_real.es_lista_borrable(
            "Mi lista", "private"))
        self.assertFalse(directo_real.es_lista_borrable("", "private"))


class TestExtraerIdVideo(unittest.TestCase):

    def test_url_watch(self):
        self.assertEqual(directo_real.extraer_id_video(
            "mira https://www.youtube.com/watch?v=AbC123_-xYz y más"),
            "AbC123_-xYz")

    def test_url_corta(self):
        self.assertEqual(directo_real.extraer_id_video(
            "salió en https://youtu.be/AbC123_-xYz"),
            "AbC123_-xYz")

    def test_sin_id_da_vacio(self):
        self.assertEqual(directo_real.extraer_id_video(
            "Tu directo de YouTube ya está al aire."), "")
        self.assertEqual(directo_real.extraer_id_video(""), "")


class TestPrimerFaltante(unittest.TestCase):

    def test_todo_presente_da_none(self):
        anuncios = "ya está al aire, conectado al directo, transmisión detenida"
        self.assertIsNone(directo_real.primer_faltante(
            anuncios, ["ya está al aire", "conectado al directo"]))

    def test_devuelve_el_primer_paso_fallido(self):
        anuncios = "ya está al aire"
        self.assertEqual(directo_real.primer_faltante(
            anuncios, ["ya está al aire", "conectado al directo",
                       "transmisión detenida"]),
            "conectado al directo")

    def test_no_importan_mayusculas(self):
        self.assertIsNone(directo_real.primer_faltante(
            "YA ESTÁ AL AIRE", ["ya está al aire"]))


class TestFaltasDeOpciones(unittest.TestCase):

    def _contenido_ok(self, **cambios):
        contenido = {"latencyPreference": "ultraLow", "enableDvr": False}
        contenido.update(cambios)
        return contenido

    def _snippet_ok(self, **cambios):
        snippet = {"categoryId": "27", "tags": ["prueba", "ytchat"]}
        snippet.update(cambios)
        return snippet

    def test_todo_bien_no_falta_nada(self):
        self.assertEqual(
            directo_real.faltas_de_opciones(self._contenido_ok(),
                                            self._snippet_ok()), [])

    def test_latencia(self):
        self.assertEqual(
            directo_real.faltas_de_opciones(
                self._contenido_ok(latencyPreference="normal"),
                self._snippet_ok()),
            ["latencia ultrabaja"])

    def test_dvr(self):
        self.assertEqual(
            directo_real.faltas_de_opciones(
                self._contenido_ok(enableDvr=True), self._snippet_ok()),
            ["rebobinar apagado"])

    def test_categoria(self):
        self.assertEqual(
            directo_real.faltas_de_opciones(
                self._contenido_ok(), self._snippet_ok(categoryId="24")),
            ["categoría Educación"])

    def test_las_etiquetas_no_cuentan(self):
        self.assertEqual(
            directo_real.faltas_de_opciones(
                self._contenido_ok(), self._snippet_ok(tags=[])), [])

    def test_varias_faltas_en_orden(self):
        self.assertEqual(
            directo_real.faltas_de_opciones(
                self._contenido_ok(latencyPreference="normal",
                                   enableDvr=True),
                self._snippet_ok(categoryId="24", tags=[])),
            ["latencia ultrabaja", "rebobinar apagado",
             "categoría Educación"])

    def test_vacio_no_revienta(self):
        self.assertEqual(len(directo_real.faltas_de_opciones(None, None)), 3)


class TestEstadoMiniatura(unittest.TestCase):

    def test_sin_avisos_pasa(self):
        bien, detalle = directo_real.estado_miniatura(
            "Tu directo de YouTube ya está al aire.")
        self.assertTrue(bien)
        self.assertIn("sin avisos", detalle)

    def test_403_del_canal_sin_verificar_pasa(self):
        from ytchat.youtube import youtube_api
        bien, detalle = directo_real.estado_miniatura(
            "Aviso: " + youtube_api.FRASE_MINiatura_SIN_VERIFICAR)
        self.assertTrue(bien)
        self.assertIn("verificado por teléfono", detalle)

    def test_otro_fallo_no_pasa(self):
        bien, detalle = directo_real.estado_miniatura(
            "No se pudo poner la miniatura: Error de la API.")
        self.assertFalse(bien)
        self.assertIn("no pudo", detalle)


class TestEstadoLista(unittest.TestCase):

    def test_sin_aviso_y_en_la_lista_pasa(self):
        bien, detalle = directo_real.estado_lista("ya está al aire", True)
        self.assertTrue(bien)
        self.assertIn("está en la lista", detalle)

    def test_sin_aviso_y_fuera_de_la_lista_falla(self):
        bien, detalle = directo_real.estado_lista("ya está al aire", False)
        self.assertFalse(bien)
        self.assertIn("no muestra", detalle)

    def test_el_aviso_de_fallo_gana_aunque_la_api_diga_que_si(self):
        bien, detalle = directo_real.estado_lista(
            "No se pudo agregar el directo a la lista: cuota", True)
        self.assertFalse(bien)
        self.assertIn("no pudo agregarlo", detalle)

    def test_el_aviso_no_distingue_mayusculas(self):
        bien, _ = directo_real.estado_lista(
            "no se pudo agregar el directo a la lista", False)
        self.assertFalse(bien)


class TestDecidirCerrarObs(unittest.TestCase):

    def test_si_estaba_abierto_no_se_cierra(self):
        self.assertFalse(directo_real.decidir_cerrar_obs(True))

    def test_si_lo_abrio_la_app_se_cierra(self):
        self.assertTrue(directo_real.decidir_cerrar_obs(False))


VERDE = (0, 192, 0)
MAGENTA = (192, 0, 192)
AZUL = (30, 60, 200)
BLANCO = (255, 255, 255)
COLORES_PRUEBA = (VERDE, MAGENTA)


class TestFraccionDeColor(unittest.TestCase):

    def test_todo_verde_da_uno(self):
        pixeles = [VERDE] * 10
        self.assertEqual(
            directo_real.fraccion_de_color(pixeles, COLORES_PRUEBA, 0), 1.0)

    def test_nada_verde_da_cero(self):
        pixeles = [AZUL] * 10
        self.assertEqual(
            directo_real.fraccion_de_color(pixeles, COLORES_PRUEBA, 0), 0.0)

    def test_mitad_y_mitad_da_medio(self):
        pixeles = [VERDE] * 5 + [AZUL] * 5
        self.assertEqual(
            directo_real.fraccion_de_color(pixeles, COLORES_PRUEBA, 0), 0.5)

    def test_mezcla_verde_y_magenta_cuenta_todo(self):
        pixeles = [VERDE] * 3 + [MAGENTA] * 3 + [AZUL] * 4
        self.assertEqual(
            directo_real.fraccion_de_color(pixeles, COLORES_PRUEBA, 0), 0.6)

    def test_sin_pixeles_da_cero(self):
        self.assertEqual(
            directo_real.fraccion_de_color([], COLORES_PRUEBA, 0), 0.0)

    def test_tolerancia_acepta_casi_verde(self):
        pixeles = [(5, 187, 3)]
        self.assertEqual(
            directo_real.fraccion_de_color(pixeles, COLORES_PRUEBA, 0), 0.0)
        self.assertEqual(
            directo_real.fraccion_de_color(pixeles, COLORES_PRUEBA, 32), 1.0)


class TestPanelVisible(unittest.TestCase):

    def test_todo_verde_no_se_ve(self):
        self.assertFalse(directo_real.panel_visible(
            [VERDE] * 100, COLORES_PRUEBA))

    def test_todo_magenta_no_se_ve(self):
        self.assertFalse(directo_real.panel_visible(
            [MAGENTA] * 100, COLORES_PRUEBA))

    def test_mitad_verde_y_mitad_magenta_no_se_ve(self):
        self.assertFalse(directo_real.panel_visible(
            [VERDE] * 50 + [MAGENTA] * 50, COLORES_PRUEBA))

    def test_cinco_por_ciento_blanco_se_ve(self):
        self.assertTrue(directo_real.panel_visible(
            [VERDE] * 95 + [BLANCO] * 5, COLORES_PRUEBA))

    def test_uno_por_ciento_blanco_no_se_ve(self):
        self.assertFalse(directo_real.panel_visible(
            [VERDE] * 99 + [BLANCO], COLORES_PRUEBA))

    def test_sin_pixeles_no_se_ve(self):
        self.assertFalse(directo_real.panel_visible([], COLORES_PRUEBA))


class TestRectanguloDelPanel(unittest.TestCase):

    def test_mismo_tamano_no_escala(self):
        transformacion = {"positionX": 1400, "positionY": 400,
                          "width": 460, "height": 620}
        self.assertEqual(
            directo_real.rectangulo_del_panel(transformacion, 1920, 1920),
            (1400, 400, 460, 620))

    def test_captura_a_la_mitad_escala(self):
        transformacion = {"positionX": 1400, "positionY": 400,
                          "width": 460, "height": 620}
        self.assertEqual(
            directo_real.rectangulo_del_panel(transformacion, 960, 1920),
            (700, 200, 230, 310))

    def test_fuera_del_lienzo_da_vacio(self):
        transformacion = {"positionX": 2000, "positionY": 100,
                          "width": 460, "height": 620}
        self.assertEqual(
            directo_real.rectangulo_del_panel(transformacion, 1920, 1920),
            (2000, 100, 0, 620))

    def test_parcialmente_fuera_se_recorta(self):
        transformacion = {"positionX": 1800, "positionY": 900,
                          "width": 460, "height": 300}
        self.assertEqual(
            directo_real.rectangulo_del_panel(transformacion, 1920, 1920,
                                              1080, 1080),
            (1800, 900, 120, 180))

    def test_sin_lienzo_no_divide(self):
        transformacion = {"positionX": 10, "positionY": 20,
                          "width": 30, "height": 40}
        self.assertEqual(
            directo_real.rectangulo_del_panel(transformacion, 1920, 0),
            (10, 20, 30, 40))


class TestIdParaLimpiar(unittest.TestCase):

    def test_id_conocido_gana(self):
        self.assertEqual(
            directo_real.id_para_limpiar("abc123", "hallado456", True),
            "abc123")
        self.assertEqual(
            directo_real.id_para_limpiar("abc123", "hallado456", False),
            "abc123")

    def test_sin_id_y_con_hallazgo_usa_el_hallazgo(self):
        self.assertEqual(
            directo_real.id_para_limpiar("", "hallado456", True),
            "hallado456")

    def test_sin_pulsar_no_busca(self):
        self.assertEqual(
            directo_real.id_para_limpiar("", "hallado456", False), "")
        self.assertEqual(
            directo_real.id_para_limpiar("", "", False), "")

    def test_sin_hallazgo_da_vacio(self):
        self.assertEqual(directo_real.id_para_limpiar("", "", True), "")


class TestPasosDeLimpieza(unittest.TestCase):

    def test_todo_pendiente_en_orden(self):
        self.assertEqual(
            directo_real.pasos_de_limpieza(True, False, "abc123", True),
            ["detener_y_finalizar", "borrar_video", "quitar_capturas",
             "quitar_panel", "cerrar_ventanas", "cerrar_app_y_restaurar"])

    def test_sin_nada_pendiente_solo_cierra(self):
        self.assertEqual(
            directo_real.pasos_de_limpieza(False, False, "", False),
            ["quitar_capturas", "cerrar_ventanas", "cerrar_app_y_restaurar"])

    def test_finalizado_no_detiene(self):
        self.assertEqual(
            directo_real.pasos_de_limpieza(True, True, "abc123", False),
            ["borrar_video", "quitar_capturas", "cerrar_ventanas",
             "cerrar_app_y_restaurar"])

    def test_sin_video_no_borra(self):
        self.assertEqual(
            directo_real.pasos_de_limpieza(True, False, "", False),
            ["detener_y_finalizar", "quitar_capturas", "cerrar_ventanas",
             "cerrar_app_y_restaurar"])

    def test_pulso_sin_salir_detiene_por_si_creo_emision(self):
        self.assertEqual(
            directo_real.pasos_de_limpieza(False, False, "abc123", False,
                                           True),
            ["detener_y_finalizar", "borrar_video", "quitar_capturas",
             "cerrar_ventanas", "cerrar_app_y_restaurar"])

    def test_pulso_sin_id_igual_detiene_para_avisar_titulo(self):
        self.assertEqual(
            directo_real.pasos_de_limpieza(False, False, "", False, True),
            ["detener_y_finalizar", "quitar_capturas", "cerrar_ventanas",
             "cerrar_app_y_restaurar"])


class TestLeerValor(unittest.TestCase):

    def test_lista_devuelve_lo_elegido(self):
        class Lista:
            def selected_text(self):
                return "YouTube"

            def get_value(self):
                return ""

            def window_text(self):
                return "Transmitir a"

        self.assertEqual(directo_real._leer_valor(Lista()), "YouTube")

    def test_si_no_hay_elegido_usa_get_value(self):
        class ListaVacia:
            def selected_text(self):
                return ""

            def get_value(self):
                return "unlisted"

            def window_text(self):
                return "Privacidad"

        self.assertEqual(
            directo_real._leer_valor(ListaVacia()), "unlisted")

    def test_sin_selected_text_usa_get_value(self):
        class Campo:
            def get_value(self):
                return "mi título"

            def window_text(self):
                return "mi título"

        self.assertEqual(directo_real._leer_valor(Campo()), "mi título")

    def test_si_todo_vacio_usa_window_text(self):
        class Roto:
            def selected_text(self):
                return None

            def get_value(self):
                raise RuntimeError("sin valor")

            def window_text(self):
                return "texto"

        self.assertEqual(directo_real._leer_valor(Roto()), "texto")


class TestDetalleListaChat(unittest.TestCase):

    def test_sin_archivo_avisa(self):
        self.assertEqual(
            directo_real._detalle_lista_chat(None),
            "no se encontró el archivo del chat")

    def test_lista_vacia(self):
        self.assertEqual(
            directo_real._detalle_lista_chat([]),
            "lista vacía (0 elementos)")

    def test_cuenta_y_muestra_los_tres_ultimos(self):
        detalle = directo_real._detalle_lista_chat(
            ["uno", "dos", "tres", "cuatro"])
        self.assertIn("4 elementos", detalle)
        self.assertIn("«dos»", detalle)
        self.assertIn("«cuatro»", detalle)
        self.assertNotIn("«uno»", detalle)

    def test_con_menos_de_tres_muestra_todo(self):
        detalle = directo_real._detalle_lista_chat(["uno", "dos"])
        self.assertIn("2 elementos", detalle)
        self.assertIn("«uno»", detalle)
        self.assertIn("«dos»", detalle)


class TestComentarioFaltante(unittest.TestCase):

    def _ruta_con(self, lineas):
        import os
        import tempfile
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas) + ("\n" if lineas else ""))
        self.addCleanup(os.remove, ruta)
        return ruta

    def test_todo_presente_devuelve_none(self):
        ruta = self._ruta_con(
            ["10:00 Ana: Comentario de prueba 1", "10:01 Luis: otro"])
        faltante, leidos = directo_real._comentario_faltante(
            ruta, ["Comentario de prueba 1"], segundos=0)
        self.assertIsNone(faltante)
        self.assertEqual(leidos, ["10:00 Ana: Comentario de prueba 1",
                                  "10:01 Luis: otro"])

    def test_faltante_devuelve_lo_leido(self):
        ruta = self._ruta_con(["algo", "otro", "más", "último"])
        faltante, leidos = directo_real._comentario_faltante(
            ruta, ["Comentario de prueba 1"], segundos=0)
        self.assertEqual(faltante, "Comentario de prueba 1")
        self.assertEqual(leidos, ["algo", "otro", "más", "último"])

    def test_sin_archivo_devuelve_none_como_leido(self):
        import os
        import shutil
        import tempfile
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        ruta = os.path.join(carpeta, "chat.txt")
        faltante, leidos = directo_real._comentario_faltante(
            ruta, ["Comentario de prueba 1"], segundos=0)
        self.assertEqual(faltante, "Comentario de prueba 1")
        self.assertIsNone(leidos)


class TestVolumenPrueba(unittest.TestCase):

    def test_constante_al_doce_por_ciento(self):
        self.assertEqual(directo_real.VOLUMEN_PRUEBA, 0.12)

    def test_lanzador_compila_y_fija_reproductor(self):
        fuente = directo_real._LANZADOR.format(repo="C:/x")
        compile(fuente, "lanzador", "exec")
        self.assertIn("ReproductorPanel", fuente)
        self.assertIn("self._vol = 12", fuente)
        self.assertIn("sld_vol", fuente)
        self.assertIn("SetValue(12)", fuente)


class TestRespaldoSonidos(unittest.TestCase):

    def _ruta_con(self, contenido: bytes):
        import os
        import tempfile
        fd, ruta = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
        self.addCleanup(os.remove, ruta)
        return ruta

    def test_respalda_escribe_y_restaura_byte_a_byte(self):
        import os
        import tempfile
        from ytchat.core import config
        original = b"[sonidos]\nvolumen = 0.7\n"
        ruta = self._ruta_con(original)
        fd, respaldo = tempfile.mkstemp(suffix=".ini")
        os.close(fd)
        self.addCleanup(os.remove, respaldo)
        self.assertTrue(directo_real._respaldar_sonidos(ruta, respaldo))
        self.assertTrue(config.guardar_opcion(
            Path(ruta), "sonidos", "volumen",
            str(directo_real.VOLUMEN_PRUEBA)))
        with open(ruta, encoding="utf-8") as f:
            self.assertIn("0.12", f.read())
        directo_real._restaurar_sonidos(ruta, respaldo, True)
        with open(ruta, "rb") as f:
            self.assertEqual(f.read(), original)

    def test_sin_archivo_no_crea_nada(self):
        import os
        import shutil
        import tempfile
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        ruta = os.path.join(carpeta, "sounds.ini")
        respaldo = os.path.join(carpeta, "respaldo.ini")
        self.assertFalse(directo_real._respaldar_sonidos(ruta, respaldo))
        self.assertFalse(os.path.exists(ruta))
        directo_real._restaurar_sonidos(ruta, respaldo, False)
        self.assertFalse(os.path.exists(ruta))


class _ServicioListasFalso:
    """Doble mínimo de `playlists()`: `list`, `delete` y `execute`."""

    def __init__(self, items):
        self.items = items
        self.borrados: list = []

    def playlists(self):
        return self

    def list(self, **kwargs):
        return self

    def delete(self, **kwargs):
        self.borrados.append(kwargs.get("id"))
        return self

    def execute(self):
        return {"items": self.items}


class _ClienteListasFalso:

    def __init__(self, items):
        self.servicio = _ServicioListasFalso(items)

    def _escritura(self):
        return self.servicio


class TestBorrarLista(unittest.TestCase):

    def test_lista_de_la_prueba_se_borra(self):
        cliente = _ClienteListasFalso([{
            "snippet": {"title": "Prueba de YTChat lista 20:15"},
            "status": {"privacyStatus": "private"}}])
        borrada, motivo = directo_real._borrar_lista(cliente, "abc123")
        self.assertTrue(borrada)
        self.assertEqual(cliente.servicio.borrados, ["abc123"])

    def test_lista_ajena_no_se_borra(self):
        cliente = _ClienteListasFalso([{
            "snippet": {"title": "Mi lista"},
            "status": {"privacyStatus": "private"}}])
        borrada, motivo = directo_real._borrar_lista(cliente, "abc123")
        self.assertFalse(borrada)
        self.assertEqual(cliente.servicio.borrados, [])
        self.assertIn("no se borra", motivo)

    def test_lista_publica_no_se_borra(self):
        cliente = _ClienteListasFalso([{
            "snippet": {"title": "Prueba de YTChat lista 20:15"},
            "status": {"privacyStatus": "public"}}])
        borrada, _ = directo_real._borrar_lista(cliente, "abc123")
        self.assertFalse(borrada)
        self.assertEqual(cliente.servicio.borrados, [])

    def test_sin_items_no_borra(self):
        cliente = _ClienteListasFalso([])
        borrada, _ = directo_real._borrar_lista(cliente, "abc123")
        self.assertFalse(borrada)
        self.assertEqual(cliente.servicio.borrados, [])


if __name__ == "__main__":
    unittest.main()

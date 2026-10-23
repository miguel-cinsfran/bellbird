"""Tests de carga de config.ini (config.cargar_configuracion).

Se redirigen las rutas a un directorio temporal para no tocar el config.ini
real del proyecto.
"""

import tempfile
import unittest
import logging
from pathlib import Path
from unittest import mock

from ytchat.core import archivos
from ytchat.core import config
from ytchat.core import config_musica
from ytchat.core import paths
from tests.rutas_temporales import redirigir_rutas


class TestCargarConfiguracion(unittest.TestCase):

    def _cargar_en(self, contenido: str) -> dict:
        tmp = Path(self._tmp.name)
        (tmp / "config.ini").write_text(contenido, encoding="utf-8")
        with redirigir_rutas(tmp):
            return config.cargar_configuracion()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._root = logging.getLogger()
        self._handlers = self._root.handlers[:]
        self._nivel_raiz = self._root.level
        self._logger_websockets = logging.getLogger("websockets.client")
        self._nivel_websockets = self._logger_websockets.level
        self.addCleanup(self._restaurar_logging)

    def _restaurar_logging(self):
        self._root.handlers[:] = self._handlers
        self._root.setLevel(self._nivel_raiz)
        self._logger_websockets.setLevel(self._nivel_websockets)

    def test_librerias_silenciadas_incluye_dependencias_nuevas(self):
        silenciadas = config.librerias_silenciadas()
        self.assertIn("websockets", silenciadas)
        self.assertIn("googleapiclient", silenciadas)

    def test_configurar_logging_bloquea_debug_de_websockets(self):
        with redirigir_rutas(self._tmp.name), \
             mock.patch.object(config, "RotatingFileHandler"):
            config.configurar_logging()
        self.assertFalse(
            logging.getLogger("websockets.client").isEnabledFor(logging.DEBUG))

    def test_configurar_logging_conserva_warning_en_ytchat_log(self):
        """Si este nivel sube, el cierre por tope deja de llegar al archivo y se
        pierde la única pista disponible sobre la corrupción de heap al cerrar."""
        with redirigir_rutas(self._tmp.name):
            config.configurar_logging()
        manejador = next(manejador for manejador in self._root.handlers
                         if getattr(manejador, "baseFilename", "").endswith("ytchat.log"))
        self.addCleanup(manejador.close)
        self.assertEqual(manejador.level, logging.WARNING)

    def test_configurar_logging_es_idempotente(self):
        with redirigir_rutas(self._tmp.name), \
             mock.patch.object(config, "RotatingFileHandler"):
            config.configurar_logging()
            cuantos = len(self._root.handlers)
            config.configurar_logging()
        # Una segunda llamada duplicaba cada línea en consola y en ytchat.log.
        self.assertEqual(len(self._root.handlers), cuantos)

    def test_guardar_opcion_inserta_tras_la_ultima_clave_de_la_seccion(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n\n# comentario final\n\n[b]\ny = 2\n",
                        encoding="utf-8")
        config.guardar_opcion(ruta, "a", "z", "3")
        # Antes la clave migrada caía tras la línea en blanco, pegada a [b].
        self.assertEqual(ruta.read_text(encoding="utf-8"),
                         "[a]\nx = 1\nz = 3\n\n# comentario final\n\n[b]\ny = 2\n")

    def test_guardar_opcion_en_seccion_vacia_va_tras_la_cabecera(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\n\n[b]\ny = 2\n", encoding="utf-8")
        config.guardar_opcion(ruta, "a", "z", "3")
        self.assertEqual(ruta.read_text(encoding="utf-8"), "[a]\nz = 3\n\n[b]\ny = 2\n")

    def test_guardar_opcion_al_final_sin_salto_de_linea(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1", encoding="utf-8")
        config.guardar_opcion(ruta, "a", "z", "3")
        self.assertEqual(ruta.read_text(encoding="utf-8"), "[a]\nx = 1\nz = 3\n")

    def test_guardar_opcion_devuelve_true_y_cambia_la_clave(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n", encoding="utf-8")
        self.assertTrue(config.guardar_opcion(ruta, "a", "x", "2"))
        self.assertEqual(ruta.read_text(encoding="utf-8"), "[a]\nx = 2\n")
        self.assertEqual(list(ruta.parent.glob("*.tmp")), [])

    def test_guardar_opcion_en_solo_lectura_devuelve_false_y_no_toca_nada(self):
        import os
        import stat
        ruta = Path(self._tmp.name) / "config.ini"
        antes = "[a]\nx = 1\n"
        ruta.write_text(antes, encoding="utf-8")
        os.chmod(ruta, stat.S_IREAD)
        try:
            self.assertFalse(config.guardar_opcion(ruta, "a", "x", "2"))
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)
            self.assertEqual(list(ruta.parent.glob("*.tmp")), [])
        finally:
            os.chmod(ruta, stat.S_IWRITE | stat.S_IREAD)

    def test_guardar_opcion_clave_nueva_en_solo_lectura_devuelve_false(self):
        import os
        import stat
        ruta = Path(self._tmp.name) / "config.ini"
        antes = "[a]\nx = 1\n"
        ruta.write_text(antes, encoding="utf-8")
        os.chmod(ruta, stat.S_IREAD)
        try:
            self.assertFalse(config.guardar_opcion(ruta, "a", "z", "3"))
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)
            self.assertEqual(list(ruta.parent.glob("*.tmp")), [])
        finally:
            os.chmod(ruta, stat.S_IWRITE | stat.S_IREAD)

    def test_guardar_opcion_seccion_nueva_en_solo_lectura_devuelve_false(self):
        import os
        import stat
        ruta = Path(self._tmp.name) / "config.ini"
        antes = "[a]\nx = 1\n"
        ruta.write_text(antes, encoding="utf-8")
        os.chmod(ruta, stat.S_IREAD)
        try:
            self.assertFalse(config.guardar_opcion(ruta, "b", "y", "2"))
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)
            self.assertEqual(list(ruta.parent.glob("*.tmp")), [])
        finally:
            os.chmod(ruta, stat.S_IWRITE | stat.S_IREAD)

    def test_guardar_opcion_sin_ruta_devuelve_true(self):
        self.assertTrue(config.guardar_opcion(None, "a", "x", "2"))

    def test_guardar_opciones_varias_secciones_escribe_una_sola_vez(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n\n# final\n\n[b]\ny = 2\n", encoding="utf-8")
        with mock.patch("ytchat.core.archivos.escribir_texto_atomico",
                        wraps=archivos.escribir_texto_atomico) as escribir:
            self.assertTrue(config.guardar_opciones(
                ruta, [("a", "x", "9"), ("b", "z", "3"), ("c", "w", "4")]))
        # Con guardar_opcion por opción serían tres escrituras; acá es una.
        self.assertEqual(escribir.call_count, 1)
        self.assertEqual(ruta.read_text(encoding="utf-8"),
                         "[a]\nx = 9\n\n# final\n\n[b]\ny = 2\nz = 3\n\n[c]\nw = 4\n")

    def test_guardar_opciones_clave_existente_la_reemplaza(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n", encoding="utf-8")
        self.assertTrue(config.guardar_opciones(ruta, [("a", "x", "2")]))
        self.assertEqual(ruta.read_text(encoding="utf-8"), "[a]\nx = 2\n")

    def test_guardar_opciones_clave_nueva_va_tras_la_ultima_de_la_seccion(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n\n# comentario final\n\n[b]\ny = 2\n",
                        encoding="utf-8")
        self.assertTrue(config.guardar_opciones(ruta, [("a", "z", "3")]))
        self.assertEqual(
            ruta.read_text(encoding="utf-8"),
            "[a]\nx = 1\nz = 3\n\n# comentario final\n\n[b]\ny = 2\n")

    def test_guardar_opciones_seccion_nueva_va_al_final(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n", encoding="utf-8")
        self.assertTrue(config.guardar_opciones(ruta, [("b", "y", "2")]))
        self.assertEqual(ruta.read_text(encoding="utf-8"),
                         "[a]\nx = 1\n\n[b]\ny = 2\n")

    def test_guardar_opciones_seccion_nueva_con_dos_claves_una_sola_cabecera(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n", encoding="utf-8")
        self.assertTrue(config.guardar_opciones(
            ruta, [("b", "y", "2"), ("b", "z", "3")]))
        self.assertEqual(ruta.read_text(encoding="utf-8"),
                         "[a]\nx = 1\n\n[b]\ny = 2\nz = 3\n")

    def test_guardar_opciones_lista_vacia_no_escribe(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[a]\nx = 1\n", encoding="utf-8")
        with mock.patch("ytchat.core.archivos.escribir_texto_atomico") as escribir:
            self.assertTrue(config.guardar_opciones(ruta, []))
        escribir.assert_not_called()
        self.assertEqual(ruta.read_text(encoding="utf-8"), "[a]\nx = 1\n")

    def test_guardar_opciones_sin_ruta_devuelve_true(self):
        self.assertTrue(config.guardar_opciones(None, [("a", "x", "2")]))

    def test_guardar_opciones_fallo_de_lectura_devuelve_false(self):
        ruta = Path(self._tmp.name) / "no_existe.ini"
        self.assertFalse(config.guardar_opciones(ruta, [("a", "x", "2")]))

    def test_guardar_opciones_fallo_de_escritura_devuelve_false(self):
        import os
        import stat
        ruta = Path(self._tmp.name) / "config.ini"
        antes = "[a]\nx = 1\n"
        ruta.write_text(antes, encoding="utf-8")
        os.chmod(ruta, stat.S_IREAD)
        try:
            self.assertFalse(config.guardar_opciones(
                ruta, [("a", "x", "2"), ("b", "y", "3")]))
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)
            self.assertEqual(list(ruta.parent.glob("*.tmp")), [])
        finally:
            os.chmod(ruta, stat.S_IWRITE | stat.S_IREAD)

    def test_guardar_opciones_equivale_a_guardar_opcion_una_por_una(self):
        base = "[a]\nx = 1\n# comentario\n\n[b]\ny = 2\n\n[z]\nw = 9\n"
        listas = [
            [("a", "x", "10"), ("b", "y", "20"), ("z", "w", "90")],
            [("a", "nueva", "1"), ("c", "k", "2"), ("a", "x", "3")],
            [("b", "y", "0"), ("a", "nueva2", "77"), ("z", "w", "1")],
        ]
        for cambios in listas:
            with self.subTest(cambios=cambios):
                ruta_uno = Path(self._tmp.name) / "uno.ini"
                ruta_lote = Path(self._tmp.name) / "lote.ini"
                ruta_uno.write_text(base, encoding="utf-8")
                ruta_lote.write_text(base, encoding="utf-8")
                for seccion, clave, valor in cambios:
                    config.guardar_opcion(ruta_uno, seccion, clave, valor)
                config.guardar_opciones(ruta_lote, cambios)
                self.assertEqual(ruta_lote.read_text(encoding="utf-8"),
                                 ruta_uno.read_text(encoding="utf-8"))

    def test_regenera_si_falta(self):
        tmp = Path(self._tmp.name)
        with redirigir_rutas(tmp):
            cfg = config.cargar_configuracion()
        self.assertTrue((tmp / "config.ini").exists())
        self.assertEqual(cfg["formato_prefijo"], "nombre_mensaje")
        texto = (tmp / "config.ini").read_text(encoding="utf-8")
        self.assertIn("registro_detallado = false", texto)

    def test_registro_detallado_ausente_no_activa_manejador(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[diagnostico]\n", encoding="utf-8")
        with redirigir_rutas(self._tmp.name), \
             mock.patch.object(config.logging, "getLogger") as obtener_logger, \
             mock.patch.object(config, "RotatingFileHandler"), \
             mock.patch.object(config.diagnostico, "crear_manejador_detallado") as crear:
            config.configurar_logging()
            crear.assert_not_called()

    def test_registro_detallado_si_falla_lectura_no_activa_manejador(self):
        with redirigir_rutas(self._tmp.name), \
             mock.patch.object(config.logging, "getLogger") as obtener_logger, \
             mock.patch.object(config, "RotatingFileHandler"), \
             mock.patch.object(config.configparser.ConfigParser, "read",
                               side_effect=Exception("fallo de prueba")), \
             mock.patch.object(config.diagnostico, "crear_manejador_detallado") as crear:
            config.configurar_logging()
            crear.assert_not_called()

    def test_registro_detallado_ausente_se_persiste_apagado(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[diagnostico]\n", encoding="utf-8")
        with redirigir_rutas(self._tmp.name):
            config.cargar_configuracion()
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("registro_detallado = false", texto)

    def test_registro_detallado_true_se_conserva(self):
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[diagnostico]\nregistro_detallado = true\n", encoding="utf-8")
        with redirigir_rutas(self._tmp.name):
            config.cargar_configuracion()
        texto = ruta.read_text(encoding="utf-8")
        self.assertIn("registro_detallado = true", texto)

    def test_valores_basicos(self):
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertEqual(cfg["velocidad_voz"], 50)
        self.assertEqual(cfg["volumen"], 1.0)
        self.assertEqual(cfg["estrategia"], "limite")
        self.assertTrue(cfg["reconectar"])

    def test_buscar_actualizaciones_por_defecto_true(self):
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertTrue(cfg["buscar_actualizaciones_al_iniciar"])

    def test_buscar_actualizaciones_false_se_conserva(self):
        cfg = self._cargar_en("[actualizaciones]\nbuscar_al_iniciar = false\n")
        self.assertFalse(cfg["buscar_actualizaciones_al_iniciar"])

    def test_opciones_generales_por_defecto_activadas_y_direccion_vacia(self):
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertTrue(cfg["confirmar_salida"])
        self.assertTrue(cfg["recordar_direccion"])
        self.assertTrue(cfg["sonido_inicio"])
        self.assertEqual(cfg["ultima_direccion"], "")

    def test_opciones_generales_cambiadas_se_conservan(self):
        cfg = self._cargar_en(
            "[ui]\nconfirmar_salida = false\nrecordar_direccion = false\n"
            "sonido_inicio = false\n"
            "[sesion]\nultima_direccion = https://ejemplo.com/directo\n")
        self.assertFalse(cfg["confirmar_salida"])
        self.assertFalse(cfg["recordar_direccion"])
        self.assertFalse(cfg["sonido_inicio"])
        self.assertEqual(cfg["ultima_direccion"],
                         "https://ejemplo.com/directo")

    def test_clave_sobrante_guardar_historial_se_ignora_sin_error(self):
        # Un config.ini de usuario que todavía trae la opción muerta se
        # sigue leyendo sin error y la clave sobrante se ignora.
        cfg = self._cargar_en(
            "[sesion]\nguardar_historial = csv\n"
            "ultima_direccion = https://ejemplo.com/directo\n")
        self.assertNotIn("guardar_historial", cfg)
        self.assertEqual(cfg["ultima_direccion"],
                         "https://ejemplo.com/directo")

    def test_overlay_tiene_defaults_y_se_persiste_en_el_ejemplo(self):
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertFalse(cfg["overlay_activo"])
        self.assertEqual(cfg["overlay_puerto"], 8730)
        texto = (Path(self._tmp.name) / "config.ini").read_text(encoding="utf-8")
        self.assertIn("[overlay]", texto)
        self.assertIn("puerto = 8730", texto)

    def test_microfono_de_obs_viene_vacio_y_se_persiste_en_el_ejemplo(self):
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertEqual(cfg["obs_microfono"], "")
        texto = (Path(self._tmp.name) / "config.ini").read_text(encoding="utf-8")
        self.assertIn("[obs]", texto)
        self.assertIn("microfono =", texto)

    def test_programados_arranca_apagado_y_se_persiste_en_el_ejemplo(self):
        from ytchat.core import config_predeterminada as _pred
        self.assertEqual(_pred.obtener("programados", "activo"), "false")
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertFalse(cfg["programados_activo"])
        texto = (Path(self._tmp.name) / "config.ini").read_text(encoding="utf-8")
        self.assertIn("[programados]", texto)
        self.assertIn("activo = false", texto)

    def test_programados_ausente_arranca_apagado_por_defecto(self):
        cfg = self._cargar_en("[voz]\nvelocidad = 175\n")
        self.assertFalse(cfg["programados_activo"])

    def test_overlay_puerto_tiene_minimo_uno(self):
        cfg = self._cargar_en("[overlay]\nactivo = true\npuerto = 0\n")
        self.assertTrue(cfg["overlay_activo"])
        self.assertEqual(cfg["overlay_puerto"], 1)

    def test_velocidad_vieja_en_wpm_se_convierte(self):
        cfg = self._cargar_en("[voz]\nvelocidad = 175\n")
        self.assertEqual(cfg["velocidad_voz"], 50)

    def test_velocidad_vieja_rapida_se_convierte_y_topea(self):
        cfg = self._cargar_en("[voz]\nvelocidad = 400\n")
        self.assertEqual(cfg["velocidad_voz"], 100)

    def test_velocidad_vieja_se_fija_en_el_archivo(self):
        # Sin fijarla, el arranque siguiente no vería `velocidad` (los defaults
        # se escriben encima) y volvería a 50, cambiando la velocidad sola.
        self._cargar_en("[voz]\nvelocidad = 400\n")
        texto = (Path(self._tmp.name) / "config.ini").read_text(encoding="utf-8")
        self.assertIn("velocidad_voz = 100", texto)
        with redirigir_rutas(Path(self._tmp.name)):
            cfg2 = config.cargar_configuracion()
        self.assertEqual(cfg2["velocidad_voz"], 100)

    def test_velocidad_voz_nueva_gana_a_la_vieja(self):
        cfg = self._cargar_en("[voz]\nvelocidad_voz = 35\nvelocidad = 400\n")
        self.assertEqual(cfg["velocidad_voz"], 35)

    def test_velocidad_voz_ausente_cae_a_normal(self):
        cfg = self._cargar_en("[voz]\nvolumen = 1.0\n")
        self.assertEqual(cfg["velocidad_voz"], 50)

    def test_motor_invalido_cae_a_sapi(self):
        cfg = self._cargar_en("[voz]\nmotor = cualquiera\n")
        self.assertEqual(cfg["motor"], "sapi")

    def test_motor_valido_se_conserva(self):
        cfg = self._cargar_en("[voz]\nmotor = onecore\n")
        self.assertEqual(cfg["motor"], "onecore")

    def test_motor_elevenlabs_se_conserva(self):
        cfg = self._cargar_en("[voz]\nmotor = elevenlabs\n")
        self.assertEqual(cfg["motor"], "elevenlabs")

    def test_claves_de_voz_de_elevenlabs(self):
        cfg = self._cargar_en(config._CONFIG_FALLBACK)
        self.assertEqual(cfg["voz_respaldo"], "")
        self.assertEqual(cfg["elevenlabs_tope"], 30000)
        self.assertFalse(cfg["elevenlabs_solo_importantes"])

    def test_elevenlabs_tope_negativo_cae_a_cero(self):
        cfg = self._cargar_en("[voz]\nelevenlabs_tope = -5\n")
        self.assertEqual(cfg["elevenlabs_tope"], 0)

    def test_elevenlabs_config_ausente_usa_los_defaults(self):
        cfg = self._cargar_en("[voz]\nvolumen = 1.0\n")
        self.assertEqual(cfg["voz_respaldo"], "")
        self.assertEqual(cfg["elevenlabs_tope"], 30000)
        self.assertFalse(cfg["elevenlabs_solo_importantes"])

    def test_clamp_volumen(self):
        cfg = self._cargar_en("[voz]\nvolumen = 5.0\n")
        self.assertEqual(cfg["volumen"], 1.0)

    def test_estrategia_invalida_cae_a_limite(self):
        cfg = self._cargar_en("[cola]\nestrategia = loquesea\n")
        self.assertEqual(cfg["estrategia"], "limite")

    def test_listas_de_filtros(self):
        cfg = self._cargar_en(
            "[filtros]\npalabras_silenciadas = Spam, Publicidad\n"
            "usuarios_silenciados = Bot1, BOT2\n")
        self.assertEqual(cfg["palabras_silenciadas"], ["spam", "publicidad"])
        self.assertEqual(cfg["usuarios_silenciados"], ["bot1", "bot2"])

    def test_palabra_silenciada_con_porcentaje_se_lee_tal_cual(self):
        cfg = self._cargar_en(
            "[filtros]\npalabras_silenciadas = spam, 100%\n")
        self.assertEqual(cfg["palabras_silenciadas"], ["spam", "100%"])

    def test_usuario_silenciado_con_numeral_y_punto_y_coma_se_lee_entero(self):
        cfg = self._cargar_en(
            "[filtros]\nusuarios_silenciados = bot #1 ; prueba\n")
        self.assertEqual(cfg["usuarios_silenciados"], ["bot #1 ; prueba"])

    def test_carpeta_descargas_con_porcentaje_y_comentario_se_lee_entera(self):
        cfg = self._cargar_en(
            "[descargas]\ncarpeta = C:\\Descargas\\50% #2\n")
        self.assertEqual(cfg["descargas_carpeta"], "C:\\Descargas\\50% #2")

    def test_lineas_de_comentario_con_numeral_y_punto_y_coma_se_ignoran(self):
        cfg = self._cargar_en(
            "[filtros]\n# comentario con numeral\n"
            "; comentario con punto y coma\n"
            "palabras_silenciadas = spam\n")
        self.assertEqual(cfg["palabras_silenciadas"], ["spam"])

    def test_formato_invalido_cae_a_default(self):
        cfg = self._cargar_en("[lectura]\nformato_prefijo = raro\n")
        self.assertEqual(cfg["formato_prefijo"], "nombre_mensaje")

    def test_formato_mensaje_nombre_se_conserva(self):
        cfg = self._cargar_en("[lectura]\nformato_prefijo = mensaje_nombre\n")
        self.assertEqual(cfg["formato_prefijo"], "mensaje_nombre")

    def test_lectura_recientes_voz_se_conserva(self):
        cfg = self._cargar_en("[lectura]\nrecientes = voz\n")
        self.assertEqual(cfg["lectura_recientes"], "voz")

    def test_lectura_recientes_invalido_cae_a_lector(self):
        cfg = self._cargar_en("[lectura]\nrecientes = raro\n")
        self.assertEqual(cfg["lectura_recientes"], "lector")

    def test_lectura_recientes_ausente_es_lector(self):
        cfg = self._cargar_en("[voz]\nvolumen = 1.0\n")
        self.assertEqual(cfg["lectura_recientes"], "lector")

    def test_destino_de_transmision_ausente_queda_vacio(self):
        cfg = self._cargar_en("[voz]\nvoz = 0\n")
        self.assertEqual(cfg["transmision_destino"], "")

    def test_destino_de_transmision_valido_se_conserva(self):
        for destino in ("TikTok", "YouTube"):
            cfg = self._cargar_en(f"[transmision]\ndestino = {destino}\n")
            self.assertEqual(cfg["transmision_destino"], destino)

    def test_destino_de_transmision_invalido_queda_vacio(self):
        cfg = self._cargar_en("[transmision]\ndestino = Twitch\n")
        self.assertEqual(cfg["transmision_destino"], "")

    def test_directo_youtube_arranca_vacio_y_no_listado(self):
        cfg = self._cargar_en("[voz]\nvoz = 0\n")
        self.assertEqual(cfg["transmision_youtube_titulo"], "")
        self.assertEqual(cfg["transmision_youtube_descripcion"], "")
        self.assertEqual(cfg["transmision_youtube_privacidad"], "unlisted")

    def test_directo_youtube_privacidad_valida_se_conserva(self):
        for privacidad in ("public", "unlisted", "private"):
            cfg = self._cargar_en(
                f"[transmision]\nyoutube_privacidad = {privacidad}\n")
            self.assertEqual(cfg["transmision_youtube_privacidad"], privacidad)

    def test_directo_youtube_privacidad_invalida_cae_a_no_listado(self):
        cfg = self._cargar_en("[transmision]\nyoutube_privacidad = solo-yo\n")
        self.assertEqual(cfg["transmision_youtube_privacidad"], "unlisted")

    def test_directo_youtube_opciones_por_defecto(self):
        cfg = self._cargar_en("[voz]\nvoz = 0\n")
        self.assertEqual(cfg["transmision_youtube_latencia"], "normal")
        self.assertFalse(cfg["transmision_youtube_ninos"])
        self.assertTrue(cfg["transmision_youtube_dvr"])
        self.assertEqual(cfg["transmision_youtube_categoria"], "")
        self.assertEqual(cfg["transmision_youtube_etiquetas"], "")
        self.assertEqual(cfg["transmision_youtube_miniatura"], "")

    def test_directo_youtube_latencia_valida_se_conserva(self):
        for latencia in ("normal", "low", "ultraLow"):
            cfg = self._cargar_en(
                f"[transmision]\nyoutube_latencia = {latencia}\n")
            self.assertEqual(cfg["transmision_youtube_latencia"], latencia)

    def test_directo_youtube_latencia_invalida_cae_a_normal(self):
        cfg = self._cargar_en("[transmision]\nyoutube_latencia = turbo\n")
        self.assertEqual(cfg["transmision_youtube_latencia"], "normal")

    def test_directo_youtube_ninos_y_dvr_se_leen(self):
        cfg = self._cargar_en(
            "[transmision]\nyoutube_ninos = true\nyoutube_dvr = false\n")
        self.assertTrue(cfg["transmision_youtube_ninos"])
        self.assertFalse(cfg["transmision_youtube_dvr"])

    def test_directo_youtube_categoria_valida_se_conserva(self):
        cfg = self._cargar_en("[transmision]\nyoutube_categoria = 20\n")
        self.assertEqual(cfg["transmision_youtube_categoria"], "20")

    def test_directo_youtube_categoria_invalida_queda_vacia(self):
        cfg = self._cargar_en("[transmision]\nyoutube_categoria = 999\n")
        self.assertEqual(cfg["transmision_youtube_categoria"], "")

    def test_directo_youtube_miniatura_ruta_ida_y_vuelta(self):
        ruta = "C:\\fotos\\miniatura.png"
        cfg = self._cargar_en(
            "[transmision]\nyoutube_miniatura = "
            f"{config.codificar_texto_ini(ruta)}\n")
        self.assertEqual(cfg["transmision_youtube_miniatura"], ruta)

    def test_directo_youtube_lista_arranca_vacia(self):
        cfg = self._cargar_en("[voz]\nvoz = 0\n")
        self.assertEqual(cfg["transmision_youtube_lista"], "")
        self.assertEqual(cfg["transmision_youtube_lista_titulo"], "")

    def test_directo_youtube_lista_titulo_ida_y_vuelta(self):
        titulo = "Mixes 100% #1 ; bravo"
        cfg = self._cargar_en(
            "[transmision]\nyoutube_lista = PL123\n"
            "youtube_lista_titulo = "
            f"{config.codificar_texto_ini(titulo)}\n")
        self.assertEqual(cfg["transmision_youtube_lista"], "PL123")
        self.assertEqual(cfg["transmision_youtube_lista_titulo"], titulo)

    def _ida_y_vuelta_ini(self, texto: str) -> str:
        ruta = Path(self._tmp.name) / "ida.ini"
        ruta.write_text("[transmision]\nyoutube_titulo = "
                        f"{config.codificar_texto_ini(texto)}\n",
                        encoding="utf-8")
        leido = config._mk_parser()
        leido.read(ruta, encoding="utf-8")
        return config.decodificar_texto_ini(
            config._gs(leido, "transmision", "youtube_titulo"))

    def test_directo_youtube_texto_libre_ida_y_vuelta(self):
        textos = [
            "Al 100% en Champions",
            "Jugando #3 ; ranked",
            "línea uno\nlínea dos",
            "C:\\carpeta\\nueva",
            "50%% y %(x)s",
            "mezcla \\ % # ;\n fin",
        ]
        for texto in textos:
            with self.subTest(texto=texto):
                codificado = config.codificar_texto_ini(texto)
                self.assertNotIn("\n", codificado)
                self.assertNotIn("%", codificado)
                self.assertNotIn("#", codificado)
                self.assertNotIn(";", codificado)
                self.assertEqual(self._ida_y_vuelta_ini(texto), texto)

    def test_directo_youtube_texto_libre_combinaciones_de_dos(self):
        caracteres = ["\\", "\n", "%", "#", ";", "x", "2", "3", "b",
                      "á", "é", " "]
        for primero in caracteres:
            for segundo in caracteres:
                texto = primero + segundo
                with self.subTest(texto=repr(texto)):
                    # Los espacios de los bordes se pierden (`_gs` hace
                    # `strip`) y está bien: solo ellos se recortan, porque
                    # el resto de los caracteres viaja escapado.
                    self.assertEqual(self._ida_y_vuelta_ini(texto),
                                     texto.strip(" "))

    def test_directo_youtube_retornos_carro_se_normalizan(self):
        self.assertEqual(self._ida_y_vuelta_ini("uno\r\ndos\rtres"),
                         "uno\ndos\ntres")

    def test_directo_youtube_titulo_con_porcentaje_carga(self):
        titulo = "Al 100% en Champions"
        cfg = self._cargar_en(
            "[transmision]\n"
            f"youtube_titulo = {config.codificar_texto_ini(titulo)}\n")
        self.assertEqual(cfg["transmision_youtube_titulo"], titulo)

    def test_inyecta_seccion_descargas_con_defaults(self):
        # Sin [descargas] en el INI, cargar_configuracion debe inyectar los
        # defaults canónicos y devolverlos en el dict.
        cfg = self._cargar_en("[voz]\nvoz = 0\n")
        self.assertIn("descargas", cfg)
        self.assertEqual(cfg["descargas_formato"], "mp4")
        self.assertEqual(cfg["descargas_bitrate"], 192)
        # En el INI queda «Descargas»; el dict ya trae la ruta resuelta
        # contra la carpeta de datos, que es la que usa el gestor de descargas.
        self.assertEqual(cfg["descargas_carpeta"], str(Path(self._tmp.name) / "Descargas"))
        self.assertFalse(cfg["descargas_enumerar"])

    def test_obtener_opciones_descarga_devuelve_defaults_si_no_existe(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            op = config.obtener_opciones_descarga()
        self.assertEqual(op["formato"], "mp4")
        self.assertEqual(op["bitrate"], 192)
        self.assertIn("Descargas", op["carpeta"])
        self.assertFalse(op["enumerar"])

    def test_obtener_opciones_no_persiste_carpeta_por_defecto(self):
        from ytchat.core import config
        ruta = Path(self._tmp.name) / "config.ini"
        contenido = "[descargas]\nformato = mp4\nbitrate = 192\nenumerar = false\n"
        ruta.write_text(contenido, encoding="utf-8")
        with redirigir_rutas(self._tmp.name):
            op = config.obtener_opciones_descarga()
        self.assertEqual(op["carpeta"], str(Path(self._tmp.name) / "Descargas"))
        self.assertEqual(ruta.read_text(encoding="utf-8"), contenido)

    def test_obtener_opciones_resuelve_carpeta_relativa_contra_datos(self):
        from ytchat.core import config
        ruta = Path(self._tmp.name) / "config.ini"
        ruta.write_text("[descargas]\ncarpeta = Descargas\n", encoding="utf-8")
        with redirigir_rutas(self._tmp.name):
            op = config.obtener_opciones_descarga()
        self.assertEqual(op["carpeta"], str(Path(self._tmp.name) / "Descargas"))

    def test_obtener_opciones_respeta_carpeta_absoluta(self):
        from ytchat.core import config
        ruta = Path(self._tmp.name) / "config.ini"
        absoluta = Path(self._tmp.name) / "otra"
        ruta.write_text(f"[descargas]\ncarpeta = {absoluta}\n", encoding="utf-8")
        with redirigir_rutas(self._tmp.name):
            op = config.obtener_opciones_descarga()
        self.assertEqual(op["carpeta"], str(absoluta))

    def test_cargar_configuracion_persiste_carpeta_predeterminada(self):
        for contenido in (
            "[voz]\nvoz = 0\n",
            "[descargas]\nformato = mp4\nbitrate = 192\nenumerar = false\n",
        ):
            with self.subTest(seccion="descargas" in contenido):
                ruta = Path(self._tmp.name) / "config.ini"
                ruta.write_text(contenido, encoding="utf-8")
                with redirigir_rutas(self._tmp.name):
                    cfg = config.cargar_configuracion()
                # En el INI queda «Descargas»; el dict ya trae la ruta resuelta
                # contra la carpeta de datos, que es la que usa el gestor de descargas.
                self.assertEqual(cfg["descargas_carpeta"],
                                 str(Path(self._tmp.name) / "Descargas"))
                self.assertRegex(
                    ruta.read_text(encoding="utf-8").lower(),
                    r"(?m)^\s*carpeta\s*=\s*descargas\s*$",
                )

    def test_guardar_opciones_descarga_persiste(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "config.ini").write_text(
                config._CONFIG_FALLBACK, encoding="utf-8")
            config.guardar_opciones_descarga(
                {"formato": "mp3", "bitrate": 320, "carpeta": "/x/y", "enumerar": True})
            op = config.obtener_opciones_descarga()
        self.assertEqual(op["formato"], "mp3")
        self.assertEqual(op["bitrate"], 320)
        self.assertEqual(op["carpeta"], "/x/y")
        self.assertTrue(op["enumerar"])

    def test_guardar_opciones_descarga_normaliza_invalidos(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "config.ini").write_text(
                config._CONFIG_FALLBACK, encoding="utf-8")
            # enumerar en el dict es bool, no string. Pasamos un valor truthy
            # pero el código debe normalizarlo (o mantenerlo si es bool True).
            # En este test pasamos un bool True para forzar la rama de
            # normalización a no actuar — y verificamos que un bitrate fuera
            # de rango y un formato inválido caen a los defaults.
            config.guardar_opciones_descarga(
                {"formato": "raro", "bitrate": 999, "enumerar": True})
            op = config.obtener_opciones_descarga()
        self.assertEqual(op["formato"], "mp4")
        self.assertEqual(op["bitrate"], 192)
        self.assertTrue(op["enumerar"])


    def test_carpeta_relativa_se_resuelve_contra_instalacion(self):
        from ytchat.core import config, paths
        with tempfile.TemporaryDirectory() as tmp:
            inst, datos = Path(tmp) / "app", Path(tmp) / "datos"
            inst.mkdir()
            datos.mkdir()
            (datos / "config.ini").write_text(
                "[descargas]\ncarpeta = MisDescargas\n", encoding="utf-8")
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                op = config.obtener_opciones_descarga()
            self.assertEqual(op["carpeta"], str(inst / "MisDescargas"))

    def test_override_sonido_relativo_se_resuelve_contra_instalacion(self):
        from ytchat.core import config, paths
        with tempfile.TemporaryDirectory() as tmp:
            inst, datos = Path(tmp) / "app", Path(tmp) / "datos"
            inst.mkdir()
            datos.mkdir()
            (datos / "sounds.ini").write_text(
                "[sonidos]\nactivar = true\nsuperchat = MisSonidos/mio.wav\n",
                encoding="utf-8")
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                sonidos = config.cargar_sonidos()
            self.assertEqual(sonidos["eventos"]["superchat"],
                             inst / "MisSonidos/mio.wav")

    def test_sonido_con_valor_vacio_silencia_el_evento(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\nactivar = true\ncopiar =\n", encoding="utf-8")
            sonidos = config.cargar_sonidos()
        self.assertIsNone(sonidos["eventos"]["copiar"])

    def test_sonido_sin_clave_usa_el_archivo_del_tema(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\nactivar = true\n", encoding="utf-8")
            sonidos = config.cargar_sonidos()
        self.assertEqual(
            sonidos["eventos"]["copiar"],
            Path(self._tmp.name) / "sounds" / "themes" / "default" / "copiar.wav")

    def test_override_sonido_absoluto_se_respeta(self):
        from ytchat.core import config
        destino = Path(self._tmp.name) / "mio.wav"
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                f"[sonidos]\nactivar = true\nsuperchat = {destino}\n",
                encoding="utf-8")
            sonidos = config.cargar_sonidos()
        self.assertEqual(sonidos["eventos"]["superchat"], destino)

    def test_evento_silenciado_no_encola_nada_en_sound_player(self):
        from ytchat.core import config
        from ytchat.voice import sound_player
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\nactivar = true\ncopiar =\n", encoding="utf-8")
            sonidos = config.cargar_sonidos()
        with mock.patch.object(sound_player, "_init_backend"), \
             mock.patch.object(sound_player, "_iniciar_hilo_sonido"), \
             mock.patch.object(sound_player, "_reproducir_fallback") as fallback:
            sound_player.cargar(sonidos)
            try:
                while True:
                    sound_player._cola_sonidos.get_nowait()
            except Exception:
                pass
            sound_player.reproducir("copiar")
            fallback.assert_not_called()
            self.assertTrue(sound_player._cola_sonidos.empty())
        sound_player.cerrar()

    def test_ruta_muestra_tema_usa_mensaje_nuevo_por_defecto(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            ruta = config.ruta_muestra_tema("suave")
        self.assertEqual(
            ruta, Path(self._tmp.name) / "sounds" / "themes" / "suave"
            / "mensaje_nuevo.wav")

    def test_cargar_sonidos_arma_las_mismas_rutas_que_muestra(self):
        from ytchat.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\nactivar = true\ntema = suave\n", encoding="utf-8")
            sonidos = config.cargar_sonidos()
            muestra = config.ruta_muestra_tema("suave", "copiar")
            defecto = config.ruta_muestra_tema("suave")
        self.assertEqual(sonidos["eventos"]["mensaje_nuevo"], defecto)
        self.assertEqual(sonidos["eventos"]["copiar"], muestra)


class TestMusicaCargador(unittest.TestCase):
    """El cargador expone la sección [musica] con sus trece claves."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _cargar_en(self, contenido: str) -> dict:
        tmp = Path(self._tmp.name)
        (tmp / "config.ini").write_text(contenido, encoding="utf-8")
        with redirigir_rutas(tmp):
            return config.cargar_configuracion()

    def test_trece_valores_de_fabrica_con_ini_vacio(self):
        cfg = self._cargar_en("")
        self.assertEqual(cfg["musica_carpeta"],
                         str(Path(self._tmp.name) / "Música"))
        self.assertFalse(cfg["musica_aleatorio"])
        self.assertEqual(cfg["musica_repetir"], "no")
        self.assertTrue(cfg["musica_retomar"])
        self.assertFalse(cfg["musica_sonido_tema"])
        self.assertEqual(cfg["musica_decir"], "titulo")
        self.assertTrue(cfg["musica_decir_pausa"])
        self.assertTrue(cfg["musica_preguntar_igualar"])
        self.assertEqual(cfg["musica_volumen"], 50)
        self.assertEqual(cfg["musica_cruce"], 6)
        self.assertEqual(cfg["musica_salida"], "")
        self.assertEqual(cfg["musica_salida_nombre"], "")
        self.assertFalse(cfg["musica_atajos_globales"])
        self.assertFalse(cfg["musica_mostrar_cola"])

    def test_lee_valores_puestos_a_mano(self):
        cfg = self._cargar_en(
            "[musica]\n"
            "carpeta = C:/Mi Música/Grandes Éxitos\n"
            "aleatorio = true\n"
            "repetir = true\n"
            "retomar = false\n"
            "sonido_tema = false\n"
            "decir = artista\n"
            "decir_titulo = false\n"
            "incluir_artista = false\n"
            "decir_pausa = false\n"
            "preguntar_igualar = false\n"
            "volumen = 80\n"
            "cruce = 3\n"
            "salida = altavoces\n"
            "salida_nombre = Altavoces del sistema\n"
            "atajos_globales = true\n")
        self.assertEqual(cfg["musica_carpeta"], "C:/Mi Música/Grandes Éxitos")
        self.assertTrue(cfg["musica_aleatorio"])
        self.assertEqual(cfg["musica_repetir"], "todo")
        self.assertFalse(cfg["musica_retomar"])
        self.assertFalse(cfg["musica_sonido_tema"])
        self.assertEqual(cfg["musica_decir"], "artista")
        self.assertFalse(cfg["musica_decir_pausa"])
        self.assertFalse(cfg["musica_preguntar_igualar"])
        self.assertEqual(cfg["musica_volumen"], 80)
        self.assertEqual(cfg["musica_cruce"], 3)
        self.assertEqual(cfg["musica_salida"], "altavoces")
        self.assertEqual(cfg["musica_salida_nombre"], "Altavoces del sistema")
        self.assertTrue(cfg["musica_atajos_globales"])

    def test_cada_clave_booleana_lee_su_propia_clave(self):
        # Con las seis invertidas a la vez, una lectura cruzada pasa
        # inadvertida. De a una sola, la clave vecina ya no la tapa.
        casos = [
            ("aleatorio", "musica_aleatorio", False),
            ("retomar", "musica_retomar", True),
            ("sonido_tema", "musica_sonido_tema", False),
            ("decir_pausa", "musica_decir_pausa", True),
            ("preguntar_igualar", "musica_preguntar_igualar", True),
            ("atajos_globales", "musica_atajos_globales", False),
        ]
        for clave_ini, clave_memoria, valor_fabrica in casos:
            with self.subTest(clave=clave_ini):
                contrario = "false" if valor_fabrica else "true"
                cfg = self._cargar_en(f"[musica]\n{clave_ini} = {contrario}\n")
                self.assertEqual(cfg[clave_memoria], not valor_fabrica)
                for _, otra_memoria, otro_fabrica in casos:
                    if otra_memoria == clave_memoria:
                        continue
                    self.assertEqual(cfg[otra_memoria], otro_fabrica)

    def test_opciones_musica_devuelve_lo_mismo_que_cargar_configuracion(self):
        # Las claves musica_* viven en config_musica.opciones_musica y entran
        # con **: mismos valores y mismo orden que en el diccionario cargado.
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            ruta.write_text("[musica]\npreguntar_igualar = false\nvolumen = 80\n",
                            encoding="utf-8")
            with redirigir_rutas(Path(tmp)):
                p = config._mk_parser()
                p.read(paths.config_ini(), encoding="utf-8")
                opciones = config_musica.opciones_musica(p)
                self.assertEqual(config._opciones_musica(p), opciones)
                cfg = config.cargar_configuracion()
        musica = {clave: valor for clave, valor in cfg.items()
                  if clave.startswith("musica_")}
        self.assertEqual(musica, opciones)
        self.assertEqual(list(musica), list(opciones))

    def test_repetir_se_lee_como_texto_y_se_normaliza(self):
        casos = [
            ("true", "todo"),
            ("tema", "tema"),
            ("todo", "todo"),
            ("no", "no"),
            ("false", "no"),
            ("", "no"),
            ("otra cosa", "no"),
        ]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                cfg = self._cargar_en(f"[musica]\nrepetir = {texto}\n")
                self.assertEqual(cfg["musica_repetir"], esperado)

    def test_carpeta_con_espacios_y_tildes_ida_y_vuelta(self):
        carpeta = "C:\\Música\\Rock and Roll\\Ñandú"
        cfg = self._cargar_en(
            "[musica]\ncarpeta = "
            f"{config.codificar_texto_ini(carpeta)}\n")
        self.assertEqual(cfg["musica_carpeta"], carpeta)

    def test_clave_vacia_cae_en_la_de_windows(self):
        with mock.patch.object(paths, "carpeta_musica_windows",
                               return_value="C:\\Usuarios\\Prueba\\Música"):
            cfg = self._cargar_en("[musica]\ncarpeta = \n")
        self.assertEqual(cfg["musica_carpeta"], "C:\\Usuarios\\Prueba\\Música")

    def test_carpeta_relativa_cuelga_de_la_instalacion(self):
        cfg = self._cargar_en("[musica]\ncarpeta = Mis temas\n")
        self.assertEqual(cfg["musica_carpeta"],
                         str(Path(self._tmp.name) / "Mis temas"))

    def test_carpeta_del_ini_manda_aunque_no_exista(self):
        with mock.patch.object(paths, "carpeta_musica_windows",
                               return_value="C:\\Usuarios\\Prueba\\Música"):
            cfg = self._cargar_en("[musica]\ncarpeta = Z:\\Inexistente\\Música\n")
        self.assertEqual(cfg["musica_carpeta"], "Z:\\Inexistente\\Música")

    def test_salida_nombre_con_caracteres_especiales_ida_y_vuelta(self):
        nombre = "Altavoces 100% #1; principal"
        cfg = self._cargar_en(
            "[musica]\nsalida_nombre = "
            f"{config.codificar_texto_ini(nombre)}\n")
        self.assertEqual(cfg["musica_salida_nombre"], nombre)

    def test_volumen_mayor_a_cien_se_topea(self):
        cfg = self._cargar_en("[musica]\nvolumen = 150\n")
        self.assertEqual(cfg["musica_volumen"], 100)

    def test_volumen_negativo_cae_a_cero(self):
        cfg = self._cargar_en("[musica]\nvolumen = -10\n")
        self.assertEqual(cfg["musica_volumen"], 0)

    def test_cruce_se_recorta_entre_cero_y_doce(self):
        cfg = self._cargar_en("[musica]\ncruce = 13\n")
        self.assertEqual(cfg["musica_cruce"], 12)
        cfg = self._cargar_en("[musica]\ncruce = -2\n")
        self.assertEqual(cfg["musica_cruce"], 0)

    def test_decir_viejo_apagado_da_nada(self):
        cfg = self._cargar_en("[musica]\ndecir_titulo = false\n")
        self.assertEqual(cfg["musica_decir"], "nada")

    def test_decir_viejo_con_artista_da_los_dos(self):
        cfg = self._cargar_en("[musica]\ndecir_titulo = true\nincluir_artista = true\n")
        self.assertEqual(cfg["musica_decir"], "titulo_artista")

    def test_decir_ausente_da_titulo(self):
        cfg = self._cargar_en("[voz]\nvoz = 0\n")
        self.assertEqual(cfg["musica_decir"], "titulo")

    def test_decir_presente_manda_sobre_las_viejas(self):
        cfg = self._cargar_en(
            "[musica]\ndecir = artista\ndecir_titulo = false\nincluir_artista = false\n")
        self.assertEqual(cfg["musica_decir"], "artista")


if __name__ == "__main__":
    unittest.main()

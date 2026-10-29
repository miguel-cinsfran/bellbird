"""Pruebas de la migración de datos de la raíz a la subcarpeta de datos."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import migracion_datos
from ytchat.core import paths


def _instalacion_vieja(inst):
    """Crea una instalación vieja falsa y devuelve pares nombre y contenido."""
    piezas = {
        "config.ini": "[voz]\nvelocidad = 200\n",
        "credenciales.json": '{"falso": true}',
    }
    for nombre, contenido in piezas.items():
        (inst / nombre).write_text(contenido, encoding="utf-8")
    cache = inst / "cache-audio"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "clip.mp3").write_bytes(b"audio falso")
    return piezas


class TestMigrar(unittest.TestCase):

    def test_instalacion_vieja_completa_termina_en_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            piezas = _instalacion_vieja(inst)
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                resultado = migracion_datos.migrar(
                    paths.carpeta_instalacion(), paths.carpeta_datos(),
                    paths.datos_a_migrar(), paths.sounds_ini())
            for nombre, contenido in piezas.items():
                with self.subTest(archivo=nombre):
                    self.assertEqual((datos / nombre).read_text(encoding="utf-8"),
                                     contenido)
                    self.assertFalse((inst / nombre).exists())
            self.assertEqual((datos / "cache-audio" / "clip.mp3").read_bytes(),
                             b"audio falso")
            self.assertFalse((inst / "cache-audio").exists())
            self.assertIn("config.ini", resultado.movidos)

    def test_sounds_ini_se_copia_y_la_raiz_sigue(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            (inst / "sounds.ini").write_text("[sonidos]\n", encoding="utf-8")
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                resultado = migracion_datos.migrar(
                    paths.carpeta_instalacion(), paths.carpeta_datos(),
                    paths.datos_a_migrar(), paths.sounds_ini())
            self.assertTrue((inst / "sounds.ini").is_file())
            self.assertEqual(
                (datos / "sounds.ini").read_text(encoding="utf-8"),
                (inst / "sounds.ini").read_text(encoding="utf-8"))
            self.assertIn("sounds.ini", resultado.copiados)
            self.assertNotIn("sounds.ini", resultado.movidos)

    def test_destino_existente_no_se_pisa_y_figura_en_conflictos(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            datos.mkdir()
            (inst / "config.ini").write_text("viejo\n", encoding="utf-8")
            (datos / "config.ini").write_text("nuevo\n", encoding="utf-8")
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                resultado = migracion_datos.migrar(
                    paths.carpeta_instalacion(), paths.carpeta_datos(),
                    paths.datos_a_migrar(), paths.sounds_ini())
            self.assertEqual((datos / "config.ini").read_text(encoding="utf-8"),
                             "nuevo\n")
            self.assertEqual((inst / "config.ini").read_text(encoding="utf-8"),
                             "viejo\n")
            self.assertIn("config.ini", resultado.conflictos)

    def test_segunda_llamada_no_hace_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            _instalacion_vieja(inst)
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                rutas = paths.datos_a_migrar()
                sonidos = paths.sounds_ini()
                migracion_datos.migrar(inst, datos, rutas, sonidos)
                segunda = migracion_datos.migrar(inst, datos, rutas, sonidos)
            self.assertEqual(segunda.movidos, [])
            self.assertEqual(segunda.copiados, [])
            self.assertEqual(segunda.conflictos, [])
            self.assertEqual(segunda.errores, [])

    def test_sin_nada_viejo_no_crea_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                resultado = migracion_datos.migrar(
                    paths.carpeta_instalacion(), paths.carpeta_datos(),
                    paths.datos_a_migrar(), paths.sounds_ini())
            self.assertFalse(datos.exists())
            self.assertEqual(resultado.movidos, [])
            self.assertEqual(resultado.copiados, [])
            self.assertEqual(resultado.conflictos, [])
            self.assertEqual(resultado.errores, [])

    def test_si_mover_falla_cae_a_la_copia(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            (inst / "config.ini").write_text("viejo\n", encoding="utf-8")
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                rutas = paths.datos_a_migrar()
                sonidos = paths.sounds_ini()
                with mock.patch(
                        "ytchat.core.migracion_datos.os.replace",
                        side_effect=OSError("bloqueado")):
                    resultado = migracion_datos.migrar(
                        inst, datos, rutas, sonidos)
            self.assertIn("config.ini", resultado.copiados)
            self.assertEqual((datos / "config.ini").read_text(encoding="utf-8"),
                             "viejo\n")
            self.assertTrue((inst / "config.ini").is_file())

    def test_si_copiar_tambien_falla_va_a_errores_sin_lanzar(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            inst.mkdir()
            datos = inst / "data"
            (inst / "config.ini").write_text("viejo\n", encoding="utf-8")
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=inst), \
                 mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos):
                rutas = paths.datos_a_migrar()
                sonidos = paths.sounds_ini()
                with mock.patch(
                        "ytchat.core.migracion_datos.os.replace",
                        side_effect=OSError("bloqueado")), \
                     mock.patch(
                        "ytchat.core.migracion_datos.shutil.copy2",
                        side_effect=OSError("disco lleno")):
                    resultado = migracion_datos.migrar(
                        inst, datos, rutas, sonidos)
            self.assertTrue(
                any("config.ini" in error for error in resultado.errores))
            self.assertTrue((inst / "config.ini").is_file())


def _pares_anteriores(tmp: Path, datos: Path):
    """Pares (viejo, nuevo) de la migración de nombres, en carpetas reales."""
    return (
        [(tmp / "local" / "YTChat TTS" / "yt-dlp.exe", datos / "yt-dlp.exe")],
        [(datos / "ytchat-debug.log", datos / "bellbird-debug.log"),
         (datos / "ytchat-fallos.log", datos / "bellbird-fallos.log")],
    )


class TestNombresAnteriores(unittest.TestCase):
    """El yt-dlp fuera de data y los registros con el nombre viejo."""

    def _migrar(self, inst, datos, pares):
        return migracion_datos.migrar(inst, datos, [], datos / "sounds.ini", pares)

    def test_ytdlp_se_copia_y_se_borra_el_viejo_y_su_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            viejo = inst / "local" / "YTChat TTS" / "yt-dlp.exe"
            viejo.parent.mkdir(parents=True)
            viejo.write_bytes(b"binario")
            resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertEqual((datos / "yt-dlp.exe").read_bytes(), b"binario")
            self.assertFalse(viejo.exists())
            self.assertFalse(viejo.parent.exists())
            self.assertIn("yt-dlp.exe", resultado.copiados)

    def test_carpeta_del_viejo_con_otros_archivos_no_se_borra(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            viejo = inst / "local" / "YTChat TTS" / "yt-dlp.exe"
            viejo.parent.mkdir(parents=True)
            viejo.write_bytes(b"binario")
            (viejo.parent / "otro.txt").write_text("sigue", encoding="utf-8")
            self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertFalse(viejo.exists())
            self.assertTrue(viejo.parent.is_dir())
            self.assertEqual((viejo.parent / "otro.txt").read_text(encoding="utf-8"),
                             "sigue")

    def test_destino_del_ytdlp_existente_no_se_pisa(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            datos.mkdir(parents=True)
            (datos / "yt-dlp.exe").write_bytes(b"nuevo")
            viejo = inst / "local" / "YTChat TTS" / "yt-dlp.exe"
            viejo.parent.mkdir(parents=True)
            viejo.write_bytes(b"viejo")
            resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertEqual((datos / "yt-dlp.exe").read_bytes(), b"nuevo")
            self.assertTrue(viejo.is_file())
            self.assertIn("yt-dlp.exe", resultado.conflictos)

    def test_fallo_de_copia_de_ytdlp_no_corta_la_migracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            viejo = inst / "local" / "YTChat TTS" / "yt-dlp.exe"
            viejo.parent.mkdir(parents=True)
            viejo.write_bytes(b"binario")
            datos.mkdir(parents=True)
            (datos / "ytchat-fallos.log").write_text("fallos", encoding="utf-8")
            with mock.patch("ytchat.core.migracion_datos.shutil.copy2",
                            side_effect=OSError("disco lleno")):
                resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertTrue(viejo.is_file())
            self.assertTrue(any("yt-dlp.exe" in error for error in resultado.errores))
            self.assertEqual((datos / "bellbird-fallos.log").read_text(encoding="utf-8"),
                             "fallos")

    def test_copia_con_otro_tamano_no_borra_el_viejo(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            viejo = inst / "local" / "YTChat TTS" / "yt-dlp.exe"
            viejo.parent.mkdir(parents=True)
            viejo.write_bytes(b"binario")

            def copia_corta(origen, destino, *args, **kwargs):
                Path(destino).write_bytes(b"x")

            with mock.patch("ytchat.core.migracion_datos.shutil.copy2",
                            side_effect=copia_corta):
                resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertTrue(viejo.is_file())
            self.assertTrue(any("tama" in error for error in resultado.errores))

    def test_registros_y_rotados_se_renombran(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            datos.mkdir(parents=True)
            for nombre, contenido in (
                    ("ytchat-debug.log", "depura"),
                    ("ytchat-debug.log.1", "depura uno"),
                    ("ytchat-debug.log.2", "depura dos"),
                    ("ytchat-fallos.log", "fallos")):
                (datos / nombre).write_text(contenido, encoding="utf-8")
            resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            for nombre, contenido in (
                    ("bellbird-debug.log", "depura"),
                    ("bellbird-debug.log.1", "depura uno"),
                    ("bellbird-debug.log.2", "depura dos"),
                    ("bellbird-fallos.log", "fallos")):
                with self.subTest(archivo=nombre):
                    self.assertEqual((datos / nombre).read_text(encoding="utf-8"),
                                     contenido)
            self.assertFalse((datos / "ytchat-debug.log").exists())
            self.assertFalse((datos / "ytchat-fallos.log").exists())
            self.assertIn("bellbird-debug.log", resultado.movidos)

    def test_registro_nuevo_existente_no_se_pisa(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            datos.mkdir(parents=True)
            (datos / "ytchat-debug.log").write_text("viejo", encoding="utf-8")
            (datos / "bellbird-debug.log").write_text("nuevo", encoding="utf-8")
            resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertEqual((datos / "bellbird-debug.log").read_text(encoding="utf-8"),
                             "nuevo")
            self.assertTrue((datos / "ytchat-debug.log").is_file())
            self.assertIn("bellbird-debug.log", resultado.conflictos)

    def test_principal_y_rotados_se_renombran(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            datos.mkdir(parents=True)
            for nombre, contenido in (
                    ("ytchat.log", "principal"),
                    ("ytchat.log.1", "principal uno")):
                (datos / nombre).write_text(contenido, encoding="utf-8")
            with mock.patch.object(paths, "carpeta_datos", return_value=datos):
                pares = paths.pares_de_nombres_anteriores()
                resultado = self._migrar(inst, datos, pares)
            self.assertEqual((datos / "bellbird.log").read_text(encoding="utf-8"),
                             "principal")
            self.assertEqual((datos / "bellbird.log.1").read_text(encoding="utf-8"),
                             "principal uno")
            self.assertFalse((datos / "ytchat.log").exists())
            self.assertFalse((datos / "ytchat.log.1").exists())
            self.assertIn("bellbird.log", resultado.movidos)

    def test_principal_nuevo_existente_no_se_pisa(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            datos.mkdir(parents=True)
            (datos / "ytchat.log").write_text("viejo", encoding="utf-8")
            (datos / "bellbird.log").write_text("nuevo", encoding="utf-8")
            with mock.patch.object(paths, "carpeta_datos", return_value=datos):
                pares = paths.pares_de_nombres_anteriores()
                resultado = self._migrar(inst, datos, pares)
            self.assertEqual((datos / "bellbird.log").read_text(encoding="utf-8"),
                             "nuevo")
            self.assertTrue((datos / "ytchat.log").is_file())
            self.assertIn("bellbird.log", resultado.conflictos)

    def test_fallo_al_renombrar_un_registro_no_corta(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "app"
            datos = inst / "data"
            datos.mkdir(parents=True)
            (datos / "ytchat-debug.log").write_text("depura", encoding="utf-8")
            (datos / "ytchat-fallos.log").write_text("fallos", encoding="utf-8")
            with mock.patch("ytchat.core.migracion_datos.os.replace",
                            side_effect=OSError("abierto")), \
                    mock.patch("ytchat.core.migracion_datos.shutil.copy2",
                               side_effect=OSError("abierto")):
                resultado = self._migrar(inst, datos, _pares_anteriores(inst, datos))
            self.assertTrue(resultado.errores)
            self.assertTrue((datos / "ytchat-debug.log").is_file())
            self.assertTrue((datos / "ytchat-fallos.log").is_file())


class TestCableadoMain(unittest.TestCase):

    def test_migrar_se_llama_antes_que_configurar_logging(self):
        import main as app_main
        orden = []

        def falso_migrar(*args, **kwargs):
            orden.append("migrar")
            return migracion_datos.ResultadoMigracion()

        def falso_logging(*args, **kwargs):
            orden.append("logging")
            raise RuntimeError("corte de prueba")

        with mock.patch.object(app_main.migracion_datos, "migrar",
                               side_effect=falso_migrar), \
             mock.patch.object(app_main, "configurar_logging",
                               side_effect=falso_logging):
            with self.assertRaises(RuntimeError):
                app_main.main()
        self.assertEqual(orden, ["migrar", "logging"])

    def test_migrar_recibe_los_pares_de_nombres_anteriores(self):
        import main as app_main
        pares = object()
        with mock.patch.object(app_main.migracion_datos, "migrar",
                               return_value=migracion_datos.ResultadoMigracion()) as falso, \
             mock.patch.object(app_main.paths, "pares_de_nombres_anteriores",
                               return_value=pares), \
             mock.patch.object(app_main, "configurar_logging",
                               side_effect=RuntimeError("corte de prueba")):
            with self.assertRaises(RuntimeError):
                app_main.main()
        self.assertEqual(falso.call_args.args[4], pares)


if __name__ == "__main__":
    unittest.main()

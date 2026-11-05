"""Migración de credenciales, accesos directos y registros al nombre nuevo."""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from guyrapu.ai import claves
from guyrapu.core import migracion_datos, paths


class PruebaDecisionAcceso(unittest.TestCase):
    """Qué accesos se redirigen, cuáles se renombran y cuáles no se tocan."""

    def _acceso(self, ruta, destino, **campos):
        from guyrapu.core import migracion_nombre
        return migracion_nombre.AccesoDirecto(
            ruta=Path(ruta), destino=str(destino), **campos)

    def test_exe_viejo_de_la_app_se_redirige_conservando_los_campos(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Mi acceso.lnk", app / "Bellbird.exe",
            argumentos="--perfil dos", carpeta_inicio=str(app),
            tecla="Alt+Ctrl+G", descripcion="Acceso de prueba",
            modo_ventana=3, icono=str(app / "Bellbird.exe") + ",0")
        decision = migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe")
        self.assertIsNotNone(decision)
        self.assertEqual(Path(decision.destino), app / "Guyrapu.exe")
        self.assertEqual(decision.argumentos, "--perfil dos")
        self.assertEqual(decision.carpeta_inicio, str(app))
        self.assertEqual(decision.tecla, "Alt+Ctrl+G")
        self.assertEqual(decision.descripcion, "Acceso de prueba")
        self.assertEqual(decision.modo_ventana, 3)
        self.assertEqual(decision.icono, str(app / "Guyrapu.exe") + ",0")

    def test_la_carpeta_se_compara_sin_mayusculas(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Mi acceso.lnk",
            Path("c:/programas/guyrapu/BELLBIRD.EXE"))
        self.assertIsNotNone(migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe"))

    def test_exe_viejo_de_otra_carpeta_no_se_toca(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Mi acceso.lnk",
            Path("C:/Otra/Bellbird.exe"))
        self.assertIsNone(migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe"))

    def test_otro_programa_de_la_app_no_se_toca(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Mi acceso.lnk", app / "otro.exe")
        self.assertIsNone(migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe"))

    def test_el_nombre_viejo_pasa_a_guyrapu(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Bellbird.lnk", app / "Bellbird.exe")
        decision = migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe")
        self.assertEqual(decision.ruta_nueva,
                         app / "Escritorio" / "Guyrapu.lnk")

    def test_si_ya_hay_guyrapu_lnk_conserva_el_nombre(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "YTChat TTS.lnk", app / "YTChatTTS.exe")
        decision = migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe",
            ocupados=[app / "Escritorio" / "Guyrapu.lnk"])
        self.assertEqual(decision.ruta_nueva,
                         app / "Escritorio" / "YTChat TTS.lnk")

    def test_los_nombres_del_exe_viejo_pasan_a_guyrapu(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        for nombre in ("YTChatTTS.lnk", "YTChat TTS.lnk"):
            with self.subTest(acceso=nombre):
                acceso = self._acceso(
                    app / "Escritorio" / nombre, app / "YTChatTTS.exe")
                decision = migracion_nombre.decidir_redireccion(
                    acceso, app, "Guyrapu.exe")
                self.assertEqual(Path(decision.destino),
                                 app / "Guyrapu.exe")
                self.assertEqual(decision.ruta_nueva,
                                 app / "Escritorio" / "Guyrapu.lnk")

    def test_otro_nombre_puesto_por_el_usuario_se_conserva(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Mi Guyrapu.lnk", app / "Bellbird.exe")
        decision = migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe")
        self.assertEqual(decision.ruta_nueva,
                         app / "Escritorio" / "Mi Guyrapu.lnk")

    def test_el_icono_de_otro_archivo_se_conserva(self):
        from guyrapu.core import migracion_nombre
        app = Path("C:/Programas/Guyrapu")
        acceso = self._acceso(
            app / "Escritorio" / "Mi acceso.lnk", app / "Bellbird.exe",
            icono=str(app / "icono.ico") + ",2")
        decision = migracion_nombre.decidir_redireccion(
            acceso, app, "Guyrapu.exe")
        self.assertEqual(decision.icono, str(app / "icono.ico") + ",2")


@unittest.skipUnless(os.name == "nt", "solo Windows")
class PruebaEnvoltorioAccesos(unittest.TestCase):
    """Lectura y escritura reales de .lnk con WScript.Shell."""

    def _crear(self, migracion_nombre, lnk, destino, base):
        return migracion_nombre.escribir_accesos([
            migracion_nombre.Redireccion(
                ruta=lnk, destino=str(destino), argumentos="--perfil dos",
                carpeta_inicio=str(base), tecla="Ctrl+Alt+G",
                descripcion="Acceso de prueba ñ", modo_ventana=3,
                icono=str(destino) + ",0", ruta_nueva=lnk)])

    def test_redirige_conservando_campos_y_renombra(self):
        from guyrapu.core import migracion_nombre
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = base / "app"
            app.mkdir()
            (app / "Bellbird.exe").write_bytes(b"x")
            (app / "Guyrapu.exe").write_bytes(b"x")
            escritorio = base / "escritorio"
            escritorio.mkdir()
            lnk = escritorio / "Bellbird.lnk"
            self.assertEqual(self._crear(migracion_nombre, lnk,
                                         app / "Bellbird.exe", base), [])
            antes = migracion_nombre.leer_accesos([lnk])[0]
            marca = base / "data" / "marca"
            errores = migracion_nombre.migrar_accesos(
                carpetas=[escritorio], carpeta_app=app,
                nombre_nuevo="Guyrapu.exe", marca=marca)
            self.assertEqual(errores, [])
            nuevo = escritorio / "Guyrapu.lnk"
            self.assertFalse(lnk.exists())
            self.assertTrue(nuevo.is_file())
            despues = migracion_nombre.leer_accesos([nuevo])[0]
            self.assertTrue(migracion_nombre._misma(
                despues.destino, app / "Guyrapu.exe"))
            self.assertTrue(despues.icono.endswith(",0"))
            self.assertTrue(migracion_nombre._misma(
                despues.icono.rsplit(",", 1)[0], app / "Guyrapu.exe"))
            for campo in ("argumentos", "carpeta_inicio", "tecla",
                          "descripcion"):
                self.assertEqual(getattr(despues, campo),
                                 getattr(antes, campo))
            self.assertEqual(despues.modo_ventana, antes.modo_ventana)
            self.assertTrue(marca.is_file())

    def test_los_anclados_conservan_el_nombre_y_cambian_de_destino(self):
        from guyrapu.core import migracion_nombre
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = base / "app"
            app.mkdir()
            (app / "Bellbird.exe").write_bytes(b"x")
            (app / "Guyrapu.exe").write_bytes(b"x")
            escritorio = base / "Escritorio"
            escritorio.mkdir()
            inicio = base / "Inicio"
            inicio.mkdir()
            anclados = base / "User Pinned" / "TaskBar"
            anclados.mkdir(parents=True)
            for carpeta in (escritorio, inicio, anclados):
                lnk = carpeta / "Bellbird.lnk"
                self.assertEqual(self._crear(
                    migracion_nombre, lnk, app / "Bellbird.exe", base), [])
            marca = base / "data" / "marca"
            errores = migracion_nombre.migrar_accesos(
                carpetas=[escritorio, inicio, anclados], carpeta_app=app,
                nombre_nuevo="Guyrapu.exe", marca=marca)
            self.assertEqual(errores, [])
            for carpeta in (escritorio, inicio):
                self.assertFalse((carpeta / "Bellbird.lnk").exists())
                self.assertTrue((carpeta / "Guyrapu.lnk").is_file())
            self.assertTrue((anclados / "Bellbird.lnk").is_file())
            self.assertFalse((anclados / "Guyrapu.lnk").exists())
            anclado = migracion_nombre.leer_accesos(
                [anclados / "Bellbird.lnk"])[0]
            self.assertTrue(migracion_nombre._misma(
                anclado.destino, app / "Guyrapu.exe"))

    def test_un_fallo_no_deja_la_marca(self):
        from guyrapu.core import migracion_nombre
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = base / "app"
            app.mkdir()
            (app / "Bellbird.exe").write_bytes(b"x")
            (app / "Guyrapu.exe").write_bytes(b"x")
            escritorio = base / "escritorio"
            escritorio.mkdir()
            lnk = escritorio / "Bellbird.lnk"
            self._crear(migracion_nombre, lnk, app / "Bellbird.exe", base)
            marca = base / "data" / "marca"
            with mock.patch.object(migracion_nombre, "escribir_accesos",
                                   side_effect=OSError("disco lleno")):
                errores = migracion_nombre.migrar_accesos(
                    carpetas=[escritorio], carpeta_app=app,
                    nombre_nuevo="Guyrapu.exe", marca=marca)
            self.assertTrue(errores)
            self.assertFalse(marca.exists())


@unittest.skipUnless(os.name == "nt", "solo Windows")
class PruebaCredenciales(unittest.TestCase):
    """Migración real contra el Administrador de credenciales."""

    VIEJO = "PruebaNombre/ia-viejo/"
    NUEVO = "PruebaNombre/ia-nuevo/"
    PROVEEDOR = "proveedor-de-prueba"

    def setUp(self):
        from guyrapu.core import migracion_nombre
        self.migracion = migracion_nombre
        self.addCleanup(claves.borrar, self.PROVEEDOR, prefijo=self.VIEJO)
        self.addCleanup(claves.borrar, self.PROVEEDOR, prefijo=self.NUEVO)

    def test_la_clave_sola_pasa_al_prefijo_nuevo(self):
        claves.guardar(self.PROVEEDOR, "secreta", prefijo=self.VIEJO)
        self.migracion.migrar_credenciales(
            prefijo_anterior=self.VIEJO, prefijo_nuevo=self.NUEVO,
            proveedores=(self.PROVEEDOR,))
        self.assertEqual(claves.leer(self.PROVEEDOR, prefijo=self.NUEVO),
                         "secreta")
        self.assertIsNone(claves.leer(self.PROVEEDOR, prefijo=self.VIEJO))

    def test_si_existen_las_dos_queda_la_nueva_y_la_vieja(self):
        claves.guardar(self.PROVEEDOR, "vieja", prefijo=self.VIEJO)
        claves.guardar(self.PROVEEDOR, "nueva", prefijo=self.NUEVO)
        self.migracion.migrar_credenciales(
            prefijo_anterior=self.VIEJO, prefijo_nuevo=self.NUEVO,
            proveedores=(self.PROVEEDOR,))
        self.assertEqual(claves.leer(self.PROVEEDOR, prefijo=self.NUEVO),
                         "nueva")
        self.assertEqual(claves.leer(self.PROVEEDOR, prefijo=self.VIEJO),
                         "vieja")

    def test_un_fallo_queda_en_el_registro_y_no_corta(self):
        claves.guardar(self.PROVEEDOR, "secreta", prefijo=self.VIEJO)
        with mock.patch.object(self.migracion.claves, "guardar",
                               side_effect=OSError("sin acceso")), \
                self.assertLogs(self.migracion.logger, level="WARNING"):
            self.migracion.migrar_credenciales(
                prefijo_anterior=self.VIEJO, prefijo_nuevo=self.NUEVO,
                proveedores=(self.PROVEEDOR,))
        self.assertEqual(claves.leer(self.PROVEEDOR, prefijo=self.VIEJO),
                         "secreta")


class PruebaRegistros(unittest.TestCase):
    """Los registros viejos llegan al nombre nuevo, con sus rotados."""

    def _migrar(self, datos):
        with mock.patch.object(paths, "carpeta_datos", return_value=datos):
            pares = paths.pares_de_nombres_anteriores()
        return migracion_datos.migrar(
            datos.parent, datos, [], datos / "sounds.ini", pares)

    def test_bellbird_log_y_su_rotado_pasan_a_guyrapu(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "app" / "data"
            datos.mkdir(parents=True)
            (datos / "bellbird.log").write_text("principal", encoding="utf-8")
            (datos / "bellbird.log.1").write_text("rotado", encoding="utf-8")
            resultado = self._migrar(datos)
            self.assertEqual((datos / "guyrapu.log").read_text(encoding="utf-8"),
                             "principal")
            self.assertEqual((datos / "guyrapu.log.1").read_text(encoding="utf-8"),
                             "rotado")
            self.assertFalse((datos / "bellbird.log").exists())
            self.assertIn("guyrapu.log", resultado.movidos)

    def test_guyrapu_log_existente_no_se_pisa(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "app" / "data"
            datos.mkdir(parents=True)
            (datos / "bellbird.log").write_text("viejo", encoding="utf-8")
            (datos / "guyrapu.log").write_text("nuevo", encoding="utf-8")
            resultado = self._migrar(datos)
            self.assertEqual((datos / "guyrapu.log").read_text(encoding="utf-8"),
                             "nuevo")
            self.assertTrue((datos / "bellbird.log").is_file())
            self.assertIn("guyrapu.log", resultado.conflictos)


class PruebaCableadoArranque(unittest.TestCase):
    """El arranque llama a las migraciones y la marca evita repetir."""

    def test_el_arranque_migra_credenciales_y_lanza_accesos(self):
        import main
        ctypes_falso = types.SimpleNamespace(
            windll=types.SimpleNamespace(
                user32=types.SimpleNamespace(MessageBoxW=lambda *args: 0)))
        with mock.patch.object(main.migracion_datos, "migrar",
                               return_value=None), \
                mock.patch.object(main.migracion_nombre,
                                  "migrar_credenciales") as credenciales, \
                mock.patch.object(main.migracion_nombre,
                                  "lanzar_migracion_accesos") as accesos, \
                mock.patch.object(main, "configurar_logging"), \
                mock.patch.object(main, "_verificar_instancia_unica",
                                  return_value=False), \
                mock.patch.object(main.diagnostico, "instalar_capturadores"), \
                mock.patch.object(main.diagnostico,
                                  "registrar_entorno_en_hilo"), \
                mock.patch.dict(sys.modules, {"ctypes": ctypes_falso}), \
                mock.patch.object(sys, "exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                main.main()
        credenciales.assert_called_once_with()
        accesos.assert_called_once_with()

    def test_la_marca_evita_lanzar_los_accesos(self):
        from guyrapu.core import migracion_nombre
        with tempfile.TemporaryDirectory() as tmp:
            marca = Path(tmp) / "marca"
            marca.write_text("ok", encoding="utf-8")
            with mock.patch.object(migracion_nombre.paths,
                                   "marca_migracion_accesos",
                                   return_value=marca), \
                    mock.patch.object(migracion_nombre.sys, "frozen", True,
                                      create=True), \
                    mock.patch.object(migracion_nombre.threading,
                                      "Thread") as hilo:
                self.assertFalse(
                    migracion_nombre.lanzar_migracion_accesos())
            hilo.assert_not_called()

    def test_sin_marca_y_empaquetado_lanza_el_hilo(self):
        from guyrapu.core import migracion_nombre
        with tempfile.TemporaryDirectory() as tmp:
            marca = Path(tmp) / "marca"
            with mock.patch.object(migracion_nombre.paths,
                                   "marca_migracion_accesos",
                                   return_value=marca), \
                    mock.patch.object(migracion_nombre.sys, "frozen", True,
                                      create=True), \
                    mock.patch.object(migracion_nombre.threading,
                                      "Thread") as hilo:
                self.assertTrue(migracion_nombre.lanzar_migracion_accesos())
            hilo.return_value.start.assert_called_once_with()

    def test_desde_el_codigo_fuente_no_lanza_los_accesos(self):
        from guyrapu.core import migracion_nombre
        with mock.patch.object(migracion_nombre.sys, "frozen", False,
                               create=True), \
                mock.patch.object(migracion_nombre.threading,
                                  "Thread") as hilo:
            self.assertFalse(migracion_nombre.lanzar_migracion_accesos())
        hilo.assert_not_called()


if __name__ == "__main__":
    unittest.main()

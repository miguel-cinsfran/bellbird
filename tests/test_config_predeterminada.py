"""Pruebas de la configuración predeterminada canónica."""

import tempfile
import unittest
import configparser
from pathlib import Path
from unittest import mock

from ytchat.core import config
from ytchat.core import config_predeterminada as pred
from ytchat.capture import estado_sesion
from tests.rutas_temporales import redirigir_rutas


class TestArchivoIdentico(unittest.TestCase):
    def test_config_predeterminado_ini_identico_a_generador(self):
        base = Path(__file__).parent.parent
        archivo = base / "config.predeterminado.ini"
        self.assertTrue(archivo.exists(), "config.predeterminado.ini debe existir")
        esperado = pred.generar_texto()
        real = archivo.read_text(encoding="utf-8")
        self.assertEqual(real, esperado, "config.predeterminado.ini debe ser byte por byte igual al generador")

    def test_generar_y_escribir_coinciden(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "salida.ini"
            pred.escribir(ruta)
            self.assertEqual(ruta.read_text(encoding="utf-8"), pred.generar_texto())
            # vía CLI con argumento, como lo invoca construir.bat
            import subprocess, sys
            ruta2 = Path(tmp) / "cli.ini"
            base = Path(__file__).parent.parent
            subprocess.check_call(
                [sys.executable, "-m", "ytchat.core.config_predeterminada",
                 str(ruta2)],
                cwd=str(base))
            self.assertEqual(ruta2.read_text(encoding="utf-8"), pred.generar_texto())


class TestPrimeraEjecucion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_primera_ejecucion_crea_exactamente_canonica(self):
        tmp = Path(self._tmp.name)
        self.assertFalse((tmp / "config.ini").exists())
        with redirigir_rutas(tmp):
            cfg = config.cargar_configuracion()
        self.assertTrue((tmp / "config.ini").exists())
        texto = (tmp / "config.ini").read_text(encoding="utf-8")
        self.assertEqual(texto, pred.generar_texto())
        # valores clave del dict deben coincidir con la fuente
        self.assertEqual(cfg["voz"], "")
        self.assertEqual(cfg["velocidad_voz"], 50)
        self.assertEqual(cfg["volumen"], 1.0)
        self.assertEqual(cfg["estrategia"], "limite")
        self.assertEqual(cfg["formato_prefijo"], "nombre_mensaje")
        self.assertEqual(cfg["mostrar_metadatos"], True)
        self.assertEqual(cfg["descargas_formato"], "mp4")


class TestMigracion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_migracion_agrega_claves_conserva_valores_y_desconocidas(self):
        tmp = Path(self._tmp.name)
        # INI mínimo con valor distinto, vacío intencional y clave desconocida
        contenido = (
            "[voz]\n"
            "voz = 5\n"  # distinto del default 0, debe conservarse
            "[obs]\n"
            "microfono = \n"  # vacío intencional (default también vacío)
            "[filtros]\n"
            "palabras_silenciadas = \n"  # vacío intencional
            "[lectura]\n"
            "formato_prefijo = \n"  # vacío aunque el default no lo sea
            "[mi_seccion]\n"
            "clave_desconocida = valor_raro\n"
        )
        (tmp / "config.ini").write_text(contenido, encoding="utf-8")
        with redirigir_rutas(tmp):
            cfg = config.cargar_configuracion()
        texto = (tmp / "config.ini").read_text(encoding="utf-8")
        # conserva valor distinto
        self.assertEqual(cfg["voz"], "5")
        self.assertIn("voz = 5", texto)
        # conserva vacío intencional: la clave sigue existiendo y el valor no se reemplaza por default
        p = config._mk_parser()
        p.read(tmp / "config.ini", encoding="utf-8")
        self.assertTrue(p.has_option("obs", "microfono"))
        self.assertEqual(p.get("obs", "microfono").strip(), "")
        self.assertTrue(p.has_option("filtros", "palabras_silenciadas"))
        self.assertEqual(p.get("lectura", "formato_prefijo").strip(), "")
        # conserva clave desconocida
        self.assertTrue(p.has_section("mi_seccion"))
        self.assertEqual(p.get("mi_seccion", "clave_desconocida"), "valor_raro")
        self.assertIn("clave_desconocida = valor_raro", texto)
        # agrega todas las secciones y claves canónicas, incluida la carpeta
        for seccion, claves in pred.datos().items():
            self.assertTrue(p.has_section(seccion), f"falta sección [{seccion}]")
            for clave in claves:
                self.assertTrue(
                    p.has_option(seccion, clave),
                    f"falta {seccion}.{clave} tras migración",
                )


class TestFallbacksSeccion(unittest.TestCase):
    def test_fallbacks_distinguen_seccion_y_clave(self):
        # clave "voz" solo existe en [voz]; pedirla en [ui] debe dar fallback vacío
        self.assertEqual(pred.obtener("voz", "voz"), "")
        self.assertEqual(pred.obtener("ui", "voz"), "")
        # "activo" existe en varias secciones con mismo valor pero debe distinguirse por sección
        # si preguntamos una sección inexistente, debe dar fallback vacío
        self.assertEqual(pred.obtener("seccion_inexistente", "activo"), "")
        # a nivel de config._gs con parser vacío
        p = config._mk_parser()
        self.assertEqual(config._gs(p, "voz", "voz"), "")
        self.assertEqual(config._gs(p, "ui", "voz"), "")
        self.assertEqual(config._gs(p, "overlay", "activo"), "false")
        self.assertEqual(config._gs(p, "programados", "activo"), "false")
        self.assertEqual(config._gs(p, "inexistente", "activo"), "")


class TestAtajosDefaults(unittest.TestCase):
    def test_atajos_defaults_coincide_con_atajos_canonicos(self):
        self.assertEqual(config.ATAJOS_DEFAULTS, pred.seccion("atajos"))
        self.assertEqual(config._CONFIG_FALLBACK, pred.generar_texto())

    def test_boton_fabrica_usa_fuente_canonica_y_no_altera_fijos(self):
        try:
            import wx
            from ytchat.ui import gui_preferencias as gp
        except Exception:
            self.skipTest("wx no disponible")
        # Preparar dialogo sin construir UI completa
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        dialogo._valores_atajo = {"rep_play": "ctrl+q", "salir": "alt+x"}
        # necesitamos botones mock para _restaurar_etiqueta_atajo
        import unittest.mock as mock
        # crear botones para cada accion de la fuente canónica + fijos
        todas = {**config.ATAJOS_DEFAULTS, **config.ATAJOS_FIJOS_DEFAULTS}
        dialogo._botones_atajo = {a: mock.Mock() for a in todas}
        dialogo._valores_atajo["region_siguiente"] = "f6"
        # patch de la fuente canónica expuesta a la GUI
        nuevo = dict(pred.seccion("atajos"))
        nuevo["rep_play"] = "ctrl+z"
        # mantener el resto igual para no romper
        with mock.patch.object(pred, "seccion", return_value=nuevo):
            with mock.patch.object(gp, "anunciar"):
                dialogo._restablecer_atajos(None)
        self.assertEqual(dialogo._valores_atajo["rep_play"], "ctrl+z")
        # los fijos no se tocan
        self.assertEqual(dialogo._valores_atajo["salir"], "alt+x")


class TestEstadoDefecto(unittest.TestCase):
    def test_activos_defecto_coincide_con_true_de_estado(self):
        sec = pred.seccion("estado")
        esperados = {k for k, v in sec.items() if v.strip().lower() in ("true", "yes", "1", "on")}
        self.assertEqual(estado_sesion.ACTIVOS_DEFECTO, frozenset(esperados))

    def test_estado_cubre_exactamente_componentes(self):
        sec_keys = set(pred.seccion("estado").keys())
        comp = set(estado_sesion.COMPONENTES)
        self.assertEqual(sec_keys, comp, f"estado debe cubrir exactamente COMPONENTES. Faltan {comp - sec_keys}, sobran {sec_keys - comp}")

    def test_musica_activa_de_fabrica(self):
        self.assertEqual(pred.obtener("estado", "musica"), "true")


class TestConstruirBat(unittest.TestCase):
    def test_construir_sin_config_de_fabrica_y_con_guarda_antes_del_zip(self):
        base = Path(__file__).parent.parent
        texto = (base / "construir.bat").read_text(encoding="utf-8")
        lineas = texto.splitlines()
        self.assertNotIn("HEAD:config.ini", texto)
        # no debe copiar config.ini local
        self.assertNotIn('copy /y "config.ini"', texto)
        # ninguna línea que no sea REM invoca al generador
        for numero, linea in enumerate(lineas, 1):
            sin_espacios = linea.strip().lower()
            if sin_espacios.startswith("rem"):
                continue
            self.assertNotIn(
                "ytchat.core.config_predeterminada", sin_espacios,
                f"construir.bat:{numero} no debe invocar al generador de config",
            )
        # existe la guarda contra config.ini con salida de error
        indice_guarda = -1
        for i, linea in enumerate(lineas):
            baja = linea.lower()
            if "if exist" in baja and "%out%\\config.ini" in baja:
                misma = "exit /b 1" in baja
                siguiente = (
                    i + 1 < len(lineas)
                    and "exit /b 1" in lineas[i + 1].lower()
                )
                self.assertTrue(
                    misma or siguiente,
                    "la guarda de config.ini debe tener exit /b 1 en la misma línea o en la siguiente",
                )
                indice_guarda = i
                break
        self.assertGreater(
            indice_guarda, -1,
            'construir.bat debe tener la guarda if exist "%OUT%\\config.ini"',
        )
        # la guarda aparece antes de comprimir el zip
        indice_zip = texto.lower().find("compress-archive")
        self.assertGreater(indice_zip, -1, "construir.bat debe comprimir con Compress-Archive")
        inicio_guarda = texto.lower().find('%out%\\config.ini')
        self.assertLess(
            inicio_guarda, indice_zip,
            "la guarda de config.ini debe aparecer antes de comprimir el zip",
        )

    def test_construir_copia_el_cliente_de_la_app_antes_del_zip(self):
        base = Path(__file__).parent.parent
        texto = (base / "construir.bat").read_text(encoding="utf-8")
        self.assertIn('cliente_app.json', texto)
        self.assertIn('copy /y "cliente_app.json" "%OUT%\\"', texto)
        # la copia va antes de comprimir y antes de la higiene que borra datos
        indice_copia = texto.find('copy /y "cliente_app.json"')
        indice_zip = texto.lower().find("compress-archive")
        self.assertGreater(indice_copia, -1)
        self.assertLess(indice_copia, indice_zip)
        # el borrado de credenciales.json sigue intacto
        self.assertIn('del /q "%OUT%\\credenciales.json"', texto)
        # ASCII puro, como el resto del archivo
        for numero, linea in enumerate(
                (base / "construir.bat").read_bytes().splitlines(), 1):
            self.assertFalse(any(byte > 127 for byte in linea),
                             f"construir.bat:{numero} tiene bytes fuera de ASCII")


    def test_construir_escribe_manifiesto_de_sonidos(self):
        base = Path(__file__).parent.parent
        texto = (base / "construir.bat").read_text(encoding="utf-8")
        lineas = texto.splitlines()
        # La línea que lo genera usa Python con hashlib y SHA-256, igual
        # que paquete.json, y va a columna cero: fuera de todo bloque if,
        # donde un paréntesis rompería el script.
        indice_genera = -1
        for i, linea in enumerate(lineas):
            if "sonidos.json" in linea and "hashlib" in linea:
                self.assertFalse(
                    linea[:1].isspace(),
                    f"construir.bat:{i + 1} debe ir fuera de los bloques if",
                )
                indice_genera = i
                break
        self.assertGreater(
            indice_genera, -1,
            "construir.bat debe generar sonidos.json con hashlib",
        )
        ventana = "\n".join(lineas[indice_genera:indice_genera + 1])
        self.assertIn("sha256", ventana)
        # Guarda con salida de error si no quedó escrito, antes del zip.
        indice_guarda = texto.find('if not exist "%OUT%\\sonidos.json"')
        self.assertGreater(indice_guarda, -1)
        self.assertIn("exit /b 1", texto[indice_guarda:indice_guarda + 200])
        indice_zip = texto.lower().find("compress-archive")
        inicio_guarda = texto.lower().find('%out%\\sonidos.json')
        self.assertLess(inicio_guarda, indice_zip)

    def test_construir_escribe_manifiesto_y_firma(self):
        base = Path(__file__).parent.parent
        texto = (base / "construir.bat").read_text(encoding="utf-8")
        # Manifiesto con la versión y el ejecutable, antes de comprimir.
        self.assertIn("paquete.json", texto)
        self.assertIn("'ejecutable':'YTChatTTS.exe'", texto)
        indice_manifiesto = texto.find("paquete.json")
        indice_zip = texto.lower().find("compress-archive")
        self.assertGreater(indice_manifiesto, -1)
        self.assertLess(indice_manifiesto, indice_zip)
        # Firma SHA-256 del zip, después de comprimir, calculada con
        # Python y hashlib: el powershell viejo no veia Get-FileHash
        # cuando hereda PSModulePath de PowerShell 7.
        self.assertIn(".zip.sha256", texto)
        self.assertNotIn("Get-FileHash", texto)
        self.assertIn("hashlib", texto)
        indice_firma = texto.find("hashlib", indice_zip)
        self.assertGreater(indice_firma, indice_zip)
        # Si la firma no existe, el script se detiene con error.
        self.assertIn('if not exist "%OUT%.zip.sha256"', texto)
        indice_guarda = texto.find('if not exist "%OUT%.zip.sha256"')
        self.assertGreater(indice_guarda, indice_firma)
        self.assertIn("exit /b 1", texto[indice_guarda:indice_guarda + 200])
        # Se borran las firmas viejas donde se borran los zips viejos.
        self.assertIn('del /q "YTChat TTS v*.zip.sha256"', texto)
        # El resumen final menciona la firma, sin tildes por ser ASCII.
        self.assertIn("FIRMA", texto)
        self.assertIn("subelo junto al zip a la release", texto)


class TestGitignore(unittest.TestCase):
    def test_gitignore_ignora_config_y_no_ignora_predeterminado(self):
        base = Path(__file__).parent.parent
        txt = (base / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/config.ini", txt)
        # config.predeterminado.ini no debe estar ignorado: no aparece como patrón
        # que lo ignore y git check-ignore debe no ignorarlo
        import subprocess
        # git check-ignore devuelve 0 si está ignorado, 1 si no. Usar --no-index
        # porque config.ini aún está trackeado y sin --no-index no se ve ignorado.
        try:
            res = subprocess.run(["git", "check-ignore", "--no-index", "config.predeterminado.ini"],
                                 cwd=str(base), capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0, "config.predeterminado.ini no debe estar ignorado")
            res2 = subprocess.run(["git", "check-ignore", "--no-index", "config.ini"],
                                  cwd=str(base), capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0, "config.ini debe estar ignorado")
        except FileNotFoundError:
            # si git no está, al menos verificar que no hay patrón que lo ignore
            self.assertNotIn("config.predeterminado.ini", txt)


class TestReconexionYSonidos(unittest.TestCase):
    def test_reconexion_fabrica_cinco_minutos(self):
        self.assertEqual(pred.obtener("reconexion", "max_intentos"), "20")
        self.assertEqual(pred.obtener("reconexion", "espera_entre_intentos"), "15")

    def test_fabrica_trae_aviso_de_sobrecarga_encendido_y_con_atajo(self):
        self.assertEqual(
            pred.obtener("transmision", "avisar_sobrecarga"), "true")
        self.assertEqual(
            pred.obtener("atajos", "avisos_sobrecarga"), "alt+shift+a")

    def test_lectura_de_avisar_sobrecarga_es_bool(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(Path(tmp)):
                self.assertIs(config.cargar_configuracion()["avisar_sobrecarga"],
                              True)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config.ini").write_text(
                "[transmision]\navisar_sobrecarga = false\n", encoding="utf-8")
            with redirigir_rutas(Path(tmp)):
                self.assertIs(config.cargar_configuracion()["avisar_sobrecarga"],
                              False)

    def test_generador_se_invoca_como_modulo(self):
        texto = pred.generar_texto()
        self.assertNotIn("python config_predeterminada.py", texto)
        self.assertIn("-m ytchat.core.config_predeterminada", texto)

    def test_plantilla_sounds_sin_activar(self):
        base = Path(__file__).parent.parent
        p = config._mk_parser()
        p.read(base / "sounds.ini", encoding="utf-8")
        self.assertTrue(p.has_section("sonidos"))
        self.assertFalse(p.has_option("sonidos", "activar"))

    def test_cargar_sonidos_sobre_plantilla_activa(self):
        base = Path(__file__).parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "sounds.ini"
            destino.write_text((base / "sounds.ini").read_text(encoding="utf-8"),
                               encoding="utf-8")
            with redirigir_rutas(tmp):
                sonidos = config.cargar_sonidos()
        self.assertTrue(sonidos["activar"])

    def test_cargar_sonidos_respeta_activar_falso_heredado(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sounds.ini").write_text(
                "[sonidos]\nactivar = false\nvolumen = 0.7\n",
                encoding="utf-8")
            with redirigir_rutas(tmp):
                sonidos = config.cargar_sonidos()
        self.assertFalse(sonidos["activar"])


class TestMusicaFabrica(unittest.TestCase):
    def test_seccion_musica_valores_de_fabrica(self):
        self.assertEqual(pred.seccion("musica"), {
            "carpeta": "", "aleatorio": "false", "repetir": "false",
            "retomar": "true", "sonido_tema": "true", "decir": "",
            "decir_titulo": "true", "incluir_artista": "false",
            "decir_pausa": "true", "volumen": "50", "salida": "",
            "salida_nombre": "", "atajos_globales": "false",
            "mostrar_cola": "false",
        })

    def test_seccion_musica_respeta_el_orden_de_claves(self):
        self.assertEqual(list(pred.seccion("musica").keys()), [
            "carpeta", "aleatorio", "repetir", "retomar", "sonido_tema",
            "decir", "decir_titulo", "incluir_artista", "decir_pausa",
            "volumen", "salida", "salida_nombre", "atajos_globales",
            "mostrar_cola",
        ])

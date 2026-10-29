"""Pruebas del módulo paths, único origen de las rutas de la aplicación."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import config
from ytchat.core import paths
from tests.rutas_temporales import redirigir_rutas


# (función de paths, nombre esperado en disco)
RUTAS_DE_DATOS = [
    ("config_ini", "config.ini"),
    ("config_anterior", "config.anterior.ini"),
    ("credenciales", "credenciales.json"),
    ("historial_lives", "historial_lives.json"),
    ("historial_descargas", "historial_descargas.json"),
    ("alias", "alias.json"),
    ("mensajes_programados", "mensajes_programados.json"),
    ("fin_pendiente", "fin_pendiente.json"),
    ("catalogo_ia", "catalogo_ia.json"),
    ("gratis_ia", "gratis_ia.json"),
    ("sounds_ini", "sounds.ini"),
    ("listas_musica", "listas"),
    ("estado_musica", "musica_estado.json"),
    ("cache_etiquetas_musica", "etiquetas_musica.json"),
    ("cache_sonoridad_musica", "sonoridad_musica.json"),
    ("log_principal", "ytchat.log"),
    ("log_detallado", "bellbird-debug.log"),
    ("log_fallos", "bellbird-fallos.log"),
    ("ytdlp_actualizado", "yt-dlp.exe"),
    ("cache_audio", "cache-audio"),
    ("cache_video", "cache-video"),
    ("audio_temporal", "audio_temporal"),
]

# Única función de paths que crea su carpeta, así que no entra en la guarda
# de «ninguna función crea nada en disco»: se prueba aparte.
CREAN_CARPETA = {"audio_temporal"}

RUTAS_DE_INSTALACION = [
    ("descargas_por_defecto", "Descargas"),
    ("musica_por_defecto", "Música"),
    ("catalogo_ia_empaquetado", "catalogo_ia.json"),
    ("carpeta_sonidos", "sounds"),
    ("carpeta_idiomas", "idiomas"),
    ("config_predeterminada_ini", "config.predeterminado.ini"),
    ("cliente_app", "cliente_app.json"),
    ("ffmpeg_empaquetado", paths.NOMBRE_FFMPEG),
    ("ytdlp_empaquetado", paths.NOMBRE_YTDLP),
    ("carpeta_vlc_empaquetada", "vlc"),
    ("carpeta_interna", "_internal"),
]

TODAS_LAS_FUNCIONES = (
    [nombre for nombre, _ in RUTAS_DE_DATOS if nombre not in CREAN_CARPETA]
    + [nombre for nombre, _ in RUTAS_DE_INSTALACION]
    + ["pagina_overlay", "datos_a_migrar", "carpeta_musica_windows"]
    + ["ytdlp_actualizado_anterior", "pares_de_nombres_anteriores"]
    + ["carpeta_actualizacion", "paquete_descargado", "paquete_extraido",
        "respaldo_actualizacion", "actualizacion_pendiente",
        "arranque_confirmado", "resultado_actualizacion",
        "registro_actualizacion"]
    + ["orden_de_la_app"]
)


class TestRaices(unittest.TestCase):

    def test_empaquetada_es_la_carpeta_del_ejecutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = str(Path(tmp) / "YTChatTTS.exe")
            with mock.patch.object(sys, "frozen", True, create=True), \
                 mock.patch.object(sys, "executable", exe):
                self.assertEqual(paths.carpeta_instalacion(), Path(tmp))
                self.assertEqual(paths.carpeta_datos(), Path(tmp) / "data")
                self.assertEqual(paths.config_ini(), Path(tmp) / "data" / "config.ini")
                self.assertEqual(paths.ytdlp_empaquetado(),
                                 Path(tmp) / paths.NOMBRE_YTDLP)

    def test_en_desarrollo_es_la_raiz_del_repositorio(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            raiz = paths.carpeta_instalacion()
        self.assertEqual(raiz, Path(paths.__file__).resolve().parent.parent.parent)
        self.assertTrue((raiz / "main.py").is_file())

    def test_datos_coincide_con_instalacion_en_este_encargo(self):
        self.assertEqual(paths.carpeta_datos(),
                         paths.carpeta_instalacion() / "data")


class TestEjecutableActual(unittest.TestCase):

    def test_devuelve_el_nombre_simple_del_ejecutable(self):
        self.assertEqual(paths.ejecutable_actual(),
                         Path(sys.executable).name)

    def test_no_incluye_la_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = str(Path(tmp) / "YTChatTTS.exe")
            with mock.patch.object(sys, "executable", exe):
                self.assertEqual(paths.ejecutable_actual(), "YTChatTTS.exe")


class TestFunciones(unittest.TestCase):

    def test_cada_dato_cuelga_de_carpeta_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos, instalacion = Path(tmp) / "datos", Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos), \
                 mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                for nombre, esperado in RUTAS_DE_DATOS:
                    with self.subTest(funcion=nombre):
                        self.assertEqual(getattr(paths, nombre)(),
                                         datos / esperado)

    def test_cada_instalacion_cuelga_de_carpeta_instalacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos, instalacion = Path(tmp) / "datos", Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos), \
                 mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                for nombre, esperado in RUTAS_DE_INSTALACION:
                    with self.subTest(funcion=nombre):
                        self.assertEqual(getattr(paths, nombre)(),
                                         instalacion / esperado)
                self.assertEqual(paths.pagina_overlay(),
                                 instalacion / "web" / "chat.html")

    def test_ninguna_funcion_crea_nada_en_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "inexistente"
            with mock.patch.object(paths, "carpeta_datos",
                                   return_value=destino), \
                 mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=destino):
                for nombre in TODAS_LAS_FUNCIONES:
                    with self.subTest(funcion=nombre):
                        getattr(paths, nombre)()
            self.assertFalse(destino.exists())


class TestAudioTemporal(unittest.TestCase):
    """`audio_temporal` es la única función que crea su carpeta al llamarse."""

    def test_crea_la_carpeta_y_la_devuelve(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos"
            with mock.patch.object(paths, "carpeta_datos", return_value=datos):
                ruta = paths.audio_temporal()
            self.assertEqual(ruta, datos / "audio_temporal")
            self.assertTrue(ruta.is_dir())

    def test_llamarla_de_nuevo_no_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos"
            with mock.patch.object(paths, "carpeta_datos", return_value=datos):
                primera = paths.audio_temporal()
                segunda = paths.audio_temporal()
            self.assertEqual(primera, segunda)
            self.assertTrue(segunda.is_dir())


class TestFinPendiente(unittest.TestCase):

    def test_cuelga_de_carpeta_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos"
            with mock.patch.object(paths, "carpeta_datos", return_value=datos):
                self.assertEqual(paths.fin_pendiente(),
                                 datos / "fin_pendiente.json")

    def test_no_entra_en_datos_a_migrar(self):
        # No es un dato de la migración vieja de la raíz a data/.
        self.assertNotIn(paths.fin_pendiente(), paths.datos_a_migrar())
        self.assertNotIn(paths.listas_musica(), paths.datos_a_migrar())


class TestNombresAnteriores(unittest.TestCase):
    """Las rutas viejas que la migración de arranque lleva a los nombres nuevos."""

    def test_ytdlp_actualizado_cuelga_de_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos"
            with mock.patch.object(paths, "carpeta_datos", return_value=datos):
                self.assertEqual(paths.ytdlp_actualizado(), datos / "yt-dlp.exe")

    def test_ytdlp_anterior_usa_localappdata(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            self.assertEqual(
                paths.ytdlp_actualizado_anterior(),
                Path(tmp) / "YTChat TTS" / "yt-dlp.exe")

    def test_ytdlp_anterior_sin_localappdata_usa_la_carpeta_del_usuario(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(Path, "home", return_value=Path(tmp)):
            self.assertEqual(
                paths.ytdlp_actualizado_anterior(),
                Path(tmp) / "YTChat TTS" / "yt-dlp.exe")

    def test_pares_de_nombres_anteriores(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos = Path(tmp) / "datos"
            with mock.patch.object(paths, "carpeta_datos", return_value=datos), \
                    mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                binarios, registros = paths.pares_de_nombres_anteriores()
            self.assertEqual(
                binarios,
                [(Path(tmp) / "YTChat TTS" / "yt-dlp.exe",
                  datos / "yt-dlp.exe")])
            self.assertEqual(
                registros,
                [(datos / "ytchat-debug.log", datos / "bellbird-debug.log"),
                 (datos / "ytchat-fallos.log", datos / "bellbird-fallos.log")])


class TestOrdenDeLaApp(unittest.TestCase):

    def test_empaquetada_es_solo_el_ejecutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = str(Path(tmp) / "Bellbird.exe")
            with mock.patch.object(sys, "frozen", True, create=True), \
                 mock.patch.object(sys, "executable", exe):
                self.assertEqual(paths.orden_de_la_app(), [exe])

    def test_desde_el_codigo_es_el_interprete_con_main(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertEqual(
                paths.orden_de_la_app(),
                [sys.executable,
                 str(Path(paths.__file__).resolve().parent.parent.parent
                     / "main.py")])


class TestDatosAMigrar(unittest.TestCase):
    def test_descargas_cuelga_de_instalacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos, instalacion = Path(tmp) / "datos", Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos), \
                 mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                self.assertEqual(paths.descargas_por_defecto(),
                                 instalacion / "Descargas")

    def test_datos_a_migrar_excluye_sonidos_y_descargas(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos, instalacion = Path(tmp) / "datos", Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_datos",
                                   return_value=datos), \
                 mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                migradas = paths.datos_a_migrar()
                self.assertNotIn(paths.sounds_ini(), migradas)
                self.assertNotIn(paths.descargas_por_defecto(), migradas)
                esperadas = {
                    paths.config_ini(), paths.credenciales(),
                    paths.historial_lives(), paths.historial_descargas(),
                    paths.alias(), paths.mensajes_programados(),
                    paths.log_principal(), paths.log_detallado(),
                    paths.log_fallos(), paths.cache_audio(),
                    paths.cache_video(),
                }
                self.assertEqual(set(migradas), esperadas)
                for ruta in migradas:
                    self.assertEqual(ruta.parent, datos)


class TestActualizacion(unittest.TestCase):

    RUTAS = [
        ("carpeta_actualizacion", "actualizacion"),
        ("paquete_descargado", "paquete.zip"),
        ("paquete_extraido", "nueva"),
        ("respaldo_actualizacion", "respaldo"),
        ("actualizacion_pendiente", "pendiente.json"),
        ("arranque_confirmado", "arranque-ok"),
        ("resultado_actualizacion", "resultado.json"),
        ("registro_actualizacion", "registro.log"),
    ]

    def test_cuelgan_de_datos_actualizacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            instalacion = Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                self.assertEqual(paths.carpeta_actualizacion(),
                                 paths.carpeta_datos() / "actualizacion")
                for nombre, esperado in self.RUTAS[1:]:
                    with self.subTest(funcion=nombre):
                        self.assertEqual(
                            getattr(paths, nombre)(),
                            paths.carpeta_actualizacion() / esperado)

    def test_variantes_en_con_instalacion_explicita(self):
        with tempfile.TemporaryDirectory() as tmp:
            instalacion = Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                for nombre, _ in self.RUTAS:
                    with self.subTest(funcion=nombre):
                        self.assertEqual(
                            getattr(paths, nombre)(),
                            getattr(paths, nombre + "_en")(instalacion))
                # La variante _en no usa las raíces globales.
                otra = Path(tmp) / "otra"
                self.assertEqual(paths.paquete_descargado_en(otra),
                                 otra / "data" / "actualizacion" / "paquete.zip")

    def test_nombre_del_manifiesto(self):
        self.assertEqual(paths.NOMBRE_MANIFIESTO, "paquete.json")

    def test_nombre_del_manifiesto_de_sonidos(self):
        self.assertEqual(paths.NOMBRE_MANIFIESTO_SONIDOS, "sonidos.json")


class TestCarpetaMusicaWindows(unittest.TestCase):
    """La carpeta Música conocida de Windows, leída con SHGetKnownFolderPath."""

    @unittest.skipUnless(os.name == "nt", "la carpeta conocida solo existe en Windows")
    def test_llamada_real_devuelve_ruta_absoluta_no_vacia(self):
        ruta = paths.carpeta_musica_windows()
        self.assertTrue(ruta)
        self.assertTrue(os.path.isabs(ruta))

    @unittest.skipUnless(os.name == "nt", "reemplaza SHGetKnownFolderPath de Windows")
    def test_fallo_nativo_devuelve_vacio_y_deja_registro(self):
        import ctypes
        with mock.patch.object(ctypes.windll.shell32, "SHGetKnownFolderPath",
                               side_effect=OSError("falla de prueba")):
            with self.assertLogs(paths.logger, level="DEBUG") as registros:
                self.assertEqual(paths.carpeta_musica_windows(), "")
        self.assertTrue(any("sica" in linea for linea in registros.output))

    def test_fuera_de_windows_devuelve_vacio_y_deja_registro(self):
        with mock.patch.object(os, "name", "posix"):
            with self.assertLogs(paths.logger, level="DEBUG") as registros:
                self.assertEqual(paths.carpeta_musica_windows(), "")
        self.assertTrue(registros.output)


class TestCarpetaMusicaPorDefecto(unittest.TestCase):
    """La carpeta de fábrica y cómo se resuelve la configurada."""

    def test_por_defecto_es_musica_junto_al_programa(self):
        with tempfile.TemporaryDirectory() as tmp:
            instalacion = Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                self.assertEqual(paths.musica_por_defecto(),
                                 instalacion / "Música")

    def test_vacia_da_la_de_windows(self):
        with mock.patch.object(paths, "carpeta_musica_windows",
                               return_value="C:\\Musica"):
            self.assertEqual(paths.resolver_carpeta_musica(""),
                             "C:\\Musica")
            self.assertEqual(paths.resolver_carpeta_musica("   "),
                             "C:\\Musica")

    def test_relativa_cuelga_de_la_instalacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            instalacion = Path(tmp) / "app"
            with mock.patch.object(paths, "carpeta_instalacion",
                                   return_value=instalacion):
                self.assertEqual(paths.resolver_carpeta_musica("Mis temas"),
                                 str(instalacion / "Mis temas"))

    def test_absoluta_queda_igual(self):
        self.assertEqual(paths.resolver_carpeta_musica("C:\\Musica"),
                         "C:\\Musica")


class TestAyudante(unittest.TestCase):

    def test_redirigir_rutas_mueve_las_dos_raices_y_app_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            with redirigir_rutas(destino) as devuelta:
                self.assertEqual(devuelta, destino)
                self.assertEqual(paths.carpeta_datos(), destino)
                self.assertEqual(paths.carpeta_instalacion(), destino)
                self.assertEqual(paths.config_ini(), destino / "config.ini")
                # app_dir delega en paths: lo redirigido también la mueve.
                self.assertEqual(config.app_dir(), destino)
            self.assertNotEqual(paths.carpeta_instalacion(), destino)


class TestFronteraReal(unittest.TestCase):

    def test_cargar_configuracion_lee_el_ini_redirigido(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                # El nombre se escribe a propósito en literal: es el contrato
                # de ubicación física, y así la prueba lo exige sin pasar por
                # la función bajo prueba.
                esperada = Path(tmp) / "config.ini"
                esperada.write_text("[voz]\nvelocidad = 200\n", encoding="utf-8")
                cfg = config.cargar_configuracion()
            self.assertEqual(cfg["ruta_config"], esperada)
            # 200 wpm no es el valor por defecto (que da 50 en la escala nueva):
            # solo puede venir de ESE archivo, no de otro config.ini del disco.
            self.assertEqual(cfg["velocidad_voz"], 55)


def _sin_comentarios(texto: str) -> str:
    """Devuelve el texto sin comentarios `#`, respetando los strings."""
    salida = []
    i, n = 0, len(texto)
    comilla = None  # ', " o su variante triple
    while i < n:
        if comilla is None:
            if texto.startswith("#", i):
                while i < n and texto[i] != "\n":
                    i += 1
                continue
            for candidato in ('"""', "'''", '"', "'"):
                if texto.startswith(candidato, i):
                    comilla = candidato
                    salida.append(candidato)
                    i += len(candidato)
                    break
            else:
                salida.append(texto[i])
                i += 1
        else:
            if texto[i] == "\\":
                salida.append(texto[i:i + 2])
                i += 2
                continue
            if texto.startswith(comilla, i):
                salida.append(comilla)
                i += len(comilla)
                comilla = None
            else:
                salida.append(texto[i])
                i += 1
    return "".join(salida)


class TestGuardaRutas(unittest.TestCase):
    """Ningún módulo arma rutas por su cuenta: todo sale de paths."""

    EXCLUIDOS = {"paths.py"}

    NOMBRES_DATOS = (
        "config.ini", "credenciales.json", "historial_lives.json",
        "historial_descargas.json", "alias.json", "mensajes_programados.json",
        "fin_pendiente.json", "sounds.ini", "ytchat.log", "bellbird-debug.log",
        "bellbird-fallos.log", "etiquetas_musica.json", "sonoridad_musica.json",
    )

    # (archivo, fragmento permitido, motivo). Sin comodines.
    EXCEPCIONES = (
        ("config.py", "def app_dir",
         "app_dir se conserva delegando en paths, para herramientas fuera del alcance"),
    )

    def _exceptuado(self, archivo: str, codigo: str) -> bool:
        return any(archivo == exc_archivo and fragmento in codigo
                   for exc_archivo, fragmento, _motivo in self.EXCEPCIONES)

    def test_ningun_modulo_arma_rutas_por_su_cuenta(self):
        raiz = Path(__file__).resolve().parent.parent
        violaciones = []
        descubiertos = 0
        for modulo in sorted((raiz / "ytchat").rglob("*.py")):
            if modulo.name == "__init__.py":
                continue
            descubiertos += 1
            if modulo.name in self.EXCLUIDOS:
                continue
            codigo = _sin_comentarios(modulo.read_text(encoding="utf-8"))
            for nro, linea in enumerate(codigo.splitlines(), 1):
                if self._exceptuado(modulo.name, linea):
                    continue
                if "app_dir(" in linea:
                    violaciones.append(f"{modulo.name}:{nro}: usa app_dir(")
                if "sys.executable" in linea:
                    violaciones.append(f"{modulo.name}:{nro}: usa sys.executable")
                for nombre in self.NOMBRES_DATOS:
                    if f'"{nombre}"' in linea or f"'{nombre}'" in linea:
                        violaciones.append(
                            f"{modulo.name}:{nro}: nombra {nombre} entre comillas")
        self.assertGreaterEqual(
            descubiertos, 50,
            f"la guarda recorrió solo {descubiertos} módulos en ytchat/: "
            "si se movieron las carpetas, hay que actualizarla en vez de "
            "dejarla en verde sin mirar nada")
        self.assertEqual([], violaciones,
                         "rutas armadas fuera de paths:\n" + "\n".join(violaciones))


if __name__ == "__main__":
    unittest.main()

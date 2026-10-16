"""Pruebas de la interfaz del actualizador de la app.

La ventana se reemplaza por un doble, como en
`test_gui.TestActualizarYtdlp`: no se abre nada en pantalla. Los hilos de
`diagnostico` y `wx.CallAfter` corren en el acto.
"""

import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import actualizacion
from ytchat.core.config import APP_NAME, APP_VERSION
from ytchat.ui import gui_actualizar_app as app


VERSION_NUEVA = "99.0.0"


def _paquete(version=VERSION_NUEVA, notas="novedades"):
    return actualizacion.PaqueteElegido(
        version=version, notas=notas,
        url_zip="https://ejemplo.com/bajada/App.zip",
        url_firma="https://ejemplo.com/bajada/App.zip.sha256",
        tamanio=10)


class VentanaFalsa:
    """Doble de DialogoActualizacion: no abre nada en pantalla."""

    class _Evento:
        def __init__(self):
            self._marcado = False

        def is_set(self):
            return self._marcado

        def set(self):
            self._marcado = True

    def __init__(self, padre, titulo):
        self.padre = padre
        self.titulo = titulo
        self.mostrada = False
        self.elevada = False
        self._cerrado = False
        self._cancelado = self._Evento()
        self.estados = []
        self.anuncios = []
        self.progresos = []
        self.textos_sin_anunciar = []
        self.notas_vistas = []
        self.accion_etiqueta = None
        self.accion = None
        self.txt_estado = mock.Mock()
        self.txt_estado.SetValue.side_effect = self.textos_sin_anunciar.append
        self.btn_cerrar = mock.Mock()

    @property
    def cerrado(self):
        return self._cerrado

    @property
    def cancelado(self):
        return self._cancelado

    def Show(self):
        self.mostrada = True

    def Raise(self):
        self.elevada = True

    def estado(self, texto):
        self.estados.append(texto)
        self.anuncios.append(texto)

    def progreso(self, porcentaje):
        self.progresos.append(porcentaje)

    def notas(self, texto):
        self.notas_vistas.append(texto)

    def ofrecer_accion(self, etiqueta, al_pulsar):
        self.accion_etiqueta = etiqueta
        self.accion = al_pulsar

    def quitar_accion(self):
        self.accion_etiqueta = None
        self.accion = None

    def en_hilo_principal(self, funcion, *args):
        if self._cerrado:
            return
        funcion(*args)

    def cerrar(self):
        self._cerrado = True
        self._cancelado.set()

    def pulsar_accion(self):
        self.accion()


class TestVentana(unittest.TestCase):

    def _doble(self, parche):
        doble = parche.start()
        self.addCleanup(parche.stop)
        return doble

    def _abrir(self, consultar=None, frozen=False, admite=True,
               descargar=None, extraer=None, validar=None, frame=None):
        if frame is None:
            frame = types.SimpleNamespace(Close=mock.Mock())
        ventanas = []

        def crear(target, nombre, **kwargs):
            hilo = mock.Mock()
            hilo.start.side_effect = lambda: target()
            hilo.nombre = nombre
            return hilo

        def fabrica(padre, titulo):
            ventana = VentanaFalsa(padre, titulo)
            ventanas.append(ventana)
            return ventana

        self._doble(mock.patch(
            "ytchat.ui.gui_actualizacion.DialogoActualizacion",
            side_effect=fabrica))
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version", return_value=consultar))
        self._doble(mock.patch.object(
            app.diagnostico, "crear_hilo", side_effect=crear))
        self._doble(mock.patch.object(sys, "frozen", frozen, create=True))
        self._doble(mock.patch.object(
            actualizacion, "carpeta_admite_escritura", return_value=admite))
        if descargar is not None:
            self._doble(mock.patch.object(
                actualizacion, "descargar_paquete", side_effect=descargar))
        if extraer is not None:
            self._doble(mock.patch.object(
                actualizacion, "extraer_paquete", side_effect=extraer))
        if validar is not None:
            self._doble(mock.patch.object(
                actualizacion, "validar_paquete", side_effect=validar))
        red = self._doble(mock.patch("webbrowser.open"))
        app.abrir_ventana_actualizacion(frame)
        return frame, (ventanas[0] if ventanas else None), red

    def test_titulo_y_busqueda_inicial(self):
        _, ventana, _ = self._abrir(consultar=None)
        self.assertEqual("Buscar actualizaciones", ventana.titulo)
        self.assertTrue(ventana.mostrada)
        self.assertEqual("Buscando la última versión.", ventana.anuncios[0])

    def test_sin_respuesta_avisa_y_deja_la_barra_en_cero(self):
        _, ventana, _ = self._abrir(consultar=None)
        self.assertIn("No se pudo consultar si hay una versión nueva. "
                      "Revise la conexión a Internet.", ventana.anuncios)
        self.assertEqual(0, ventana.progresos[-1])

    def test_sin_version_nueva_anuncia_la_instalada(self):
        _, ventana, _ = self._abrir(consultar=_paquete(APP_VERSION, ""))
        self.assertIn(f"Esta es la última versión, la {APP_VERSION}.",
                      ventana.anuncios)
        self.assertEqual(100, ventana.progresos[-1])

    def test_desde_fuente_no_instala_y_ofrece_la_pagina(self):
        _, ventana, red = self._abrir(
            consultar=_paquete(VERSION_NUEVA), frozen=False)
        self.assertIn(f"Hay una versión nueva, la {VERSION_NUEVA}. "
                      f"La instalada es la {APP_VERSION}. "
                      "Desde el código fuente no se instala: "
                      "se actualiza con git.", ventana.anuncios)
        self.assertEqual(["novedades"], ventana.notas_vistas)
        self.assertEqual("&Abrir la página", ventana.accion_etiqueta)
        ventana.pulsar_accion()
        red.assert_called_once_with(actualizacion.URL_PAGINA_RELEASES)

    def test_sin_permiso_sugiere_descargar_a_mano(self):
        _, ventana, red = self._abrir(
            consultar=_paquete(VERSION_NUEVA), frozen=True, admite=False)
        self.assertIn("La carpeta del programa no admite cambios. Se puede "
                      "descargar a mano desde la página.", ventana.anuncios[-1])
        self.assertEqual("&Abrir la página", ventana.accion_etiqueta)
        ventana.pulsar_accion()
        red.assert_called_once_with(actualizacion.URL_PAGINA_RELEASES)

    def test_con_permiso_ofrece_descargar(self):
        _, ventana, _ = self._abrir(
            consultar=_paquete(VERSION_NUEVA), frozen=True, admite=True)
        self.assertEqual(f"Hay una versión nueva, la {VERSION_NUEVA}. "
                         f"La instalada es la {APP_VERSION}.",
                         ventana.anuncios[-1])
        self.assertEqual(["novedades"], ventana.notas_vistas)
        self.assertEqual("&Descargar e instalar", ventana.accion_etiqueta)

    def _abrir_descargable(self, descargar, **kwargs):
        params = {"extraer": lambda *a: Path("raiz"),
                  "validar": lambda *a: "App.exe"}
        params.update(kwargs)
        frame, ventana, _ = self._abrir(
            consultar=_paquete(VERSION_NUEVA), frozen=True, admite=True,
            descargar=descargar, **params)
        ventana.pulsar_accion()
        return frame, ventana

    def test_descarga_anuncia_descargando_y_saca_la_accion(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(False, "descarga cancelada")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIsNone(ventana.accion)
        self.assertIn(f"Descargando la versión {VERSION_NUEVA}.", ventana.anuncios)

    def test_fallo_de_red_dice_el_motivo(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(
                False, "no se pudo descargar el paquete: boom")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIn("La descarga no se completó: no se pudo descargar "
                      "el paquete: boom.", ventana.anuncios)
        self.assertEqual(0, ventana.progresos[-1])

    def test_firma_que_no_coincide(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(
                False, "la firma SHA-256 no coincide")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIn("La descarga no se completó: "
                      "la firma SHA-256 no coincide.", ventana.anuncios)
        self.assertEqual(0, ventana.progresos[-1])

    def test_cancelada(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(False, "descarga cancelada")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIn("Descarga cancelada.", ventana.anuncios)
        self.assertEqual(0, ventana.progresos[-1])

    def test_ventana_cerrada_no_anuncia_nada(self):
        def descargar(*args, **kwargs):
            ventana.cerrar()
            return actualizacion.ResultadoDescarga(False, "descarga cancelada")
        frame, ventana, _ = self._abrir(
            consultar=_paquete(VERSION_NUEVA), frozen=True, admite=True,
            descargar=descargar,
            extraer=lambda *a: Path("raiz"),
            validar=lambda *a: "App.exe")
        ventana.pulsar_accion()
        self.assertNotIn("Descarga cancelada.", ventana.anuncios)
        self.assertEqual(
            f"Descargando la versión {VERSION_NUEVA}.", ventana.anuncios[-1])

    def test_paquete_invalido(self):
        def extraer(*args):
            raise actualizacion.PaqueteInvalido(
                "la versión del paquete no coincide con la publicada")

        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        _, ventana = self._abrir_descargable(descargar, extraer=extraer)
        self.assertIn("Comprobando el paquete.", ventana.anuncios)
        self.assertIn("El paquete no sirve: la versión del paquete no "
                      "coincide con la publicada.", ventana.anuncios)

    def test_descarga_bien_deja_listo_e_instalar(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIn(f"Listo para instalar. {APP_NAME} se cierra y vuelve "
                      "a abrirse sola en alrededor de un minuto. Si hay un "
                      "chat conectado o un directo "
                      "en curso, se corta.", ventana.anuncios)
        self.assertEqual("&Instalar y reiniciar", ventana.accion_etiqueta)

    def test_instalar_llama_antes_de_cerrar(self):
        from ytchat.core import paths
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        lanzar = self._doble(mock.patch.object(
            actualizacion, "lanzar_instalador"))
        self._doble(mock.patch.object(
            paths, "ejecutable_actual", return_value="YTChatTTS.exe"))
        frame, ventana = self._abrir_descargable(descargar)
        # El cierre va después del lanzamiento, nunca antes.
        gestor = mock.Mock()
        gestor.attach_mock(lanzar, "lanzar")
        gestor.attach_mock(frame.Close, "cerrar")
        ventana.pulsar_accion()
        esperado = mock.call(
            Path("raiz"), "App.exe", paths.carpeta_instalacion(),
            "YTChatTTS.exe", os.getpid(), APP_VERSION)
        lanzar.assert_called_once()
        self.assertEqual(esperado, lanzar.call_args)
        frame.Close.assert_called_once_with()
        self.assertEqual(
            [mock.call.lanzar(*esperado.args, **esperado.kwargs),
             mock.call.cerrar()], gestor.mock_calls)

    def test_instalar_con_excepcion_no_cierra(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        self._doble(mock.patch.object(
            actualizacion, "lanzar_instalador",
            side_effect=RuntimeError("sin permiso")))
        frame, ventana = self._abrir_descargable(descargar)
        ventana.pulsar_accion()
        self.assertIn("No se pudo iniciar la instalación: sin permiso.",
                      ventana.anuncios)
        frame.Close.assert_not_called()

    def test_progreso_por_decenas_no_anuncia(self):
        def descargar(*args, **kwargs):
            aviso = kwargs["aviso_progreso"]
            for porcentaje in (10, 25, 40, 100):
                aviso(porcentaje)
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        _, ventana = self._abrir_descargable(descargar)
        self.assertEqual([10, 25, 40, 100], ventana.progresos)
        self.assertIn(f"Descargando la versión {VERSION_NUEVA}: 40 por ciento",
                      ventana.textos_sin_anunciar)
        self.assertFalse(any("por ciento" in texto
                             for texto in ventana.anuncios))

    def test_cancelacion_cableada_a_la_ventana(self):
        capturada = {}

        def descargar(*args, **kwargs):
            capturada["cancelar"] = kwargs["cancelar"]
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        _, ventana = self._abrir_descargable(descargar)
        self.assertFalse(capturada["cancelar"]())
        ventana.cerrar()
        self.assertTrue(capturada["cancelar"]())

    def test_segunda_pulsacion_reutiliza_la_ventana(self):
        frame, ventana, _ = self._abrir(consultar=_paquete(APP_VERSION, ""))
        anuncios = len(ventana.anuncios)
        self._abrir(consultar=_paquete(APP_VERSION, ""), frame=frame)
        self.assertTrue(ventana.elevada)
        ventana.btn_cerrar.SetFocus.assert_called()
        self.assertEqual(anuncios, len(ventana.anuncios))

    def test_ventana_cerrada_permite_abrir_otra(self):
        frame, ventana, _ = self._abrir(consultar=_paquete(APP_VERSION, ""))
        ventana.cerrar()
        frame_otro = types.SimpleNamespace(Close=mock.Mock())
        _, ventana2, _ = self._abrir(
            consultar=_paquete(APP_VERSION, ""), frame=frame_otro)
        self.assertTrue(ventana2.mostrada)
        self.assertIsNot(ventana, ventana2)


class TestGanchos(unittest.TestCase):

    def _doble(self, parche):
        doble = parche.start()
        self.addCleanup(parche.stop)
        return doble

    def _reloj(self):
        """CallLater y CallAfter que corren en el acto y anotan demoras."""
        demoras = []

        def call_later(ms, funcion, *args):
            demoras.append(ms)
            funcion(*args)

        self._doble(mock.patch.object(
            app.wx, "CallLater", side_effect=call_later))
        self._doble(mock.patch.object(
            app.wx, "CallAfter", side_effect=lambda f, *a: f(*a)))

        def crear(target, nombre, **kwargs):
            hilo = mock.Mock()
            hilo.start.side_effect = lambda: target()
            return hilo
        self._doble(mock.patch.object(app.diagnostico, "crear_hilo", side_effect=crear))
        return demoras

    def test_confirmacion_programada_y_llamada(self):
        demoras = self._reloj()
        confirmar = self._doble(mock.patch.object(
            actualizacion, "confirmar_arranque"))
        app.programar_confirmacion_arranque()
        self.assertEqual([1500], demoras)
        confirmar.assert_called_once_with(APP_VERSION)

    def test_resultado_ok_anuncia_sin_sonido(self):
        demoras = self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "tomar_resultado",
            return_value={"resultado": "ok", "hacia": VERSION_NUEVA}))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        sonido = self._doble(mock.patch.object(app._snd, "reproducir"))
        app.programar_resultado_actualizacion()
        self.assertEqual([4000], demoras)
        anunciar.assert_called_once_with(
            f"{APP_NAME} se actualizó a la versión {VERSION_NUEVA}.")
        sonido.assert_not_called()

    def test_resultado_fallido_anuncia_y_suena_error(self):
        self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "tomar_resultado",
            return_value={"resultado": "fallo", "motivo": "corte de luz"}))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        sonido = self._doble(mock.patch.object(app._snd, "reproducir"))
        app.programar_resultado_actualizacion()
        anunciar.assert_called_once_with(
            "La actualización no se completó: corte de luz. "
            f"Sigue la versión {APP_VERSION}.")
        sonido.assert_called_once_with("error")

    def test_sin_resultado_no_anuncia(self):
        self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "tomar_resultado", return_value=None))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        app.programar_resultado_actualizacion()
        anunciar.assert_not_called()

    def test_aviso_una_sola_vez_por_version_y_guarda(self):
        demoras = self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version",
            return_value=_paquete("9.9.9")))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        leer = self._doble(mock.patch.object(
            app, "leer_version_avisada", return_value=""))
        guardar = self._doble(mock.patch.object(app, "guardar_version_avisada"))
        app.programar_aviso_version()
        self.assertEqual([10000], demoras)
        anunciar.assert_called_once_with(
            f"Hay una versión nueva de {APP_NAME}, la 9.9.9. "
            "Para instalarla: menú Ayuda, Buscar actualizaciones.")
        guardar.assert_called_once_with("9.9.9")
        # Ya avisada: silencio.
        anunciar.reset_mock()
        leer.return_value = "9.9.9"
        app.programar_aviso_version()
        anunciar.assert_not_called()

    def test_sin_conexion_no_anuncia(self):
        self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version", return_value=None))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        guardar = self._doble(mock.patch.object(app, "guardar_version_avisada"))
        app.programar_aviso_version()
        anunciar.assert_not_called()
        guardar.assert_not_called()

    def test_consulta_limpia_restos_antes_de_consultar(self):
        self._reloj()
        orden = []
        self._doble(mock.patch.object(
            actualizacion, "limpiar_restos",
            side_effect=lambda *a: orden.append("limpiar")))
        def _consultar(*a, **k):
            orden.append("consultar")
            return None
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version",
            side_effect=_consultar))
        self._doble(mock.patch.object(app, "anunciar"))
        app.programar_aviso_version()
        self.assertEqual(["limpiar", "consultar"], orden)

    def test_ganchos_nunca_revientan(self):
        self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "confirmar_arranque",
            side_effect=RuntimeError("boom")))
        self._doble(mock.patch.object(
            actualizacion, "tomar_resultado",
            side_effect=RuntimeError("boom")))
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version",
            side_effect=RuntimeError("boom")))
        with mock.patch.object(app, "logger"):
            app.programar_confirmacion_arranque()
            app.programar_resultado_actualizacion()
            app.programar_aviso_version()

    def test_version_avisada_se_guarda_con_guardar_opcion(self):
        import configparser
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            ruta.write_text("[voz]\nvoz = 0\n", encoding="utf-8")
            self.assertTrue(app.guardar_version_avisada("9.9.9", ruta))
            self.assertEqual("9.9.9", app.leer_version_avisada(ruta))
            parser = configparser.ConfigParser(interpolation=None)
            parser.read(ruta, encoding="utf-8")
            self.assertEqual("9.9.9", parser.get("actualizaciones", "avisada"))
            self.assertEqual("0", parser.get("voz", "voz"))
            self.assertEqual("", app.leer_version_avisada(Path(tmp) / "nada.ini"))


class TestCableado(unittest.TestCase):

    def _texto_gui(self):
        ruta = (Path(__file__).resolve().parent.parent
                / "ytchat" / "ui" / "gui.py")
        return ruta.read_text(encoding="utf-8")

    def test_iniciar_gui_programa_los_tres_ganchos(self):
        texto = self._texto_gui()
        inicio = texto.index("def iniciar_gui(")
        resto = texto[inicio:]
        siguiente = resto.find("\ndef ", 1)
        cuerpo = resto[:siguiente if siguiente != -1 else len(resto)]
        for nombre in ("programar_confirmacion_arranque",
                       "programar_resultado_actualizacion",
                       "programar_aviso_version"):
            with self.subTest(nombre=nombre):
                self.assertIn(nombre, cuerpo)

    def test_menu_ayuda_ofrece_buscar_antes_de_acerca(self):
        texto = self._texto_gui()
        self.assertIn("&Buscar actualizaciones…", texto)
        self.assertLess(texto.index("&Buscar actualizaciones…"),
                        texto.index("&Acerca de"))


class TestConsultaReal(unittest.TestCase):

    def test_consulta_real_devuelve_un_paquete_coherente_o_none(self):
        from urllib.request import Request, urlopen
        try:
            solicitud = Request(
                actualizacion.URL_ULTIMA_VERSION,
                headers={"User-Agent": actualizacion.USER_AGENT})
            with urlopen(solicitud, timeout=10) as respuesta:
                respuesta.read(16)
        except Exception:
            self.skipTest("sin red")
        resultado = actualizacion.consultar_ultima_version()
        if resultado is None:
            return
        self.assertTrue(resultado.version.startswith("v"), resultado.version)
        self.assertTrue(resultado.url_zip.endswith(".zip"), resultado.url_zip)
        self.assertEqual(resultado.url_zip + ".sha256", resultado.url_firma)
        self.assertTrue(resultado.url_zip.startswith("https://github.com/"))
        self.assertTrue(resultado.url_firma.startswith("https://github.com/"))
        self.assertIsInstance(resultado.tamanio, int)
        self.assertGreater(resultado.tamanio, 0)


if __name__ == "__main__":
    unittest.main()
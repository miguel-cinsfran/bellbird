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

from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir
from bellbird.core import actualizacion
from bellbird.core.config import APP_NAME, APP_VERSION
from bellbird.ui import gui_actualizar_app as app

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


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
        self.etiqueta_cerrar_vista = None

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

    def etiqueta_cerrar(self, etiqueta):
        self.etiqueta_cerrar_vista = etiqueta

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
               descargar=None, extraer=None, validar=None, frame=None,
               paquete=None, al_arrancar=False):
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
            "bellbird.ui.gui_actualizacion.DialogoActualizacion",
            side_effect=fabrica))
        if paquete is None:
            self._doble(mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=consultar))
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
        app.abrir_ventana_actualizacion(frame, paquete=paquete,
                                       al_arrancar=al_arrancar)
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
        self.assertIn("La carpeta de la aplicación no admite cambios. Se puede "
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
                False, "la firma SHA-256 no coincide", "firma_distinta")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIn("La descarga no se completó: "
                      "la firma SHA-256 no coincide.", ventana.anuncios)
        self.assertEqual(0, ventana.progresos[-1])

    def test_cancelada(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(
                False, "descarga cancelada", "cancelada")
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

    def test_validar_invalido_muestra_que_no_sirve(self):
        def validar(*args):
            raise actualizacion.PaqueteInvalido("falta el ejecutable")

        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        _, ventana = self._abrir_descargable(descargar, validar=validar)
        self.assertIn("Comprobando el paquete.", ventana.anuncios)
        self.assertIn("El paquete no sirve: falta el ejecutable.",
                      ventana.anuncios)

    def test_descarga_bien_deja_listo_e_instalar(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        _, ventana = self._abrir_descargable(descargar)
        self.assertIn(f"La actualización está preparada. {APP_NAME} se cierra y vuelve "
                      "a abrirse sola en alrededor de un minuto. Si hay un "
                      "chat conectado o un directo "
                      "en curso, se interrumpe.", ventana.anuncios)
        self.assertEqual("&Instalar y reiniciar", ventana.accion_etiqueta)

    def test_instalar_llama_antes_de_cerrar(self):
        from bellbird.core import paths
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

    def test_instalar_marca_cierre_sin_preguntar_antes_de_cerrar(self):
        def descargar(*args, **kwargs):
            return actualizacion.ResultadoDescarga(True, "paquete descargado")
        self._doble(mock.patch.object(
            actualizacion, "lanzar_instalador"))
        frame, ventana = self._abrir_descargable(descargar)
        vista_al_cerrar = []
        cierre_real = frame.Close

        def cerrar_con_chequeo():
            vista_al_cerrar.append(
                getattr(frame, "_cerrar_sin_preguntar", False))
            return cierre_real()

        frame.Close = cerrar_con_chequeo
        ventana.pulsar_accion()
        self.assertEqual(vista_al_cerrar, [True])
        self.assertTrue(frame._cerrar_sin_preguntar)
        cierre_real.assert_called_once_with()

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

    def test_con_paquete_no_consulta_la_red(self):
        consulta = self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version",
            side_effect=AssertionError("no debe consultar la red")))
        _, ventana, _ = self._abrir(
            paquete=_paquete(VERSION_NUEVA), frozen=True, admite=True)
        consulta.assert_not_called()
        self.assertNotIn("Buscando la última versión.", ventana.anuncios)
        self.assertIn(f"Hay una versión nueva, la {VERSION_NUEVA}. "
                      f"La instalada es la {APP_VERSION}.", ventana.anuncios)
        self.assertEqual("&Descargar e instalar", ventana.accion_etiqueta)

    def test_al_arrancar_el_cierre_dice_mas_tarde(self):
        _, ventana, _ = self._abrir(
            paquete=_paquete(VERSION_NUEVA), frozen=True, admite=True,
            al_arrancar=True)
        self.assertEqual("&Más tarde", ventana.etiqueta_cerrar_vista)

    def test_al_arrancar_suena_disponible(self):
        with mock.patch.object(app._snd, "reproducir") as sonido:
            self._abrir(
                paquete=_paquete(VERSION_NUEVA), frozen=True, admite=True,
                al_arrancar=True)
        sonido.assert_called_once_with("actualizacion_disponible")

    def test_desde_el_menu_no_suena_disponible(self):
        with mock.patch.object(app._snd, "reproducir") as sonido:
            self._abrir(consultar=_paquete(VERSION_NUEVA), frozen=True,
                        admite=True)
        sonido.assert_not_called()

    def test_desde_el_menu_el_cierre_no_cambia(self):
        _, ventana, _ = self._abrir(consultar=_paquete(APP_VERSION, ""))
        self.assertIsNone(ventana.etiqueta_cerrar_vista)


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

    def _frame(self, conectado=False, transmitiendo=False):
        return types.SimpleNamespace(
            _conectado=conectado,
            _supervisar_transmision=lambda accion: transmitiendo)

    def _preparar_aviso(self, version=VERSION_NUEVA, frozen=False,
                        conectado=False, transmitiendo=False, avisada="",
                        diferir=False):
        self._reloj()
        self._doble(mock.patch.object(sys, "frozen", frozen, create=True))
        self._doble(mock.patch.object(actualizacion, "limpiar_restos"))
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version",
            return_value=_paquete(version)))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        self._doble(mock.patch.object(
            app, "leer_version_avisada", return_value=avisada))
        guardar = self._doble(mock.patch.object(app, "guardar_version_avisada"))
        abrir = self._doble(mock.patch.object(
            app, "abrir_ventana_actualizacion"))
        if diferir:
            cuando_libre = self._doble(mock.patch.object(
                app.aviso_diferido, "cuando_libre"))
        else:
            cuando_libre = self._doble(mock.patch.object(
                app.aviso_diferido, "cuando_libre",
                side_effect=lambda frame, funcion, *args, **kwargs: funcion(
                    *args, **kwargs)))
        frame = self._frame(conectado=conectado, transmitiendo=transmitiendo)
        app.programar_aviso_version(frame)
        return frame, anunciar, guardar, abrir, cuando_libre

    def test_empaquetado_sin_conexion_abre_ventana_al_arrancar(self):
        frame, anunciar, guardar, abrir, _ = self._preparar_aviso(frozen=True)
        abrir.assert_called_once()
        args, kwargs = abrir.call_args
        self.assertIs(args[0], frame)
        self.assertEqual(kwargs["paquete"].version, VERSION_NUEVA)
        self.assertTrue(kwargs["al_arrancar"])
        anunciar.assert_not_called()
        guardar.assert_not_called()

    def test_empaquetado_con_version_ya_avisada_abre_igual(self):
        _, anunciar, guardar, abrir, _ = self._preparar_aviso(
            frozen=True, avisada=VERSION_NUEVA)
        abrir.assert_called_once()
        anunciar.assert_not_called()
        guardar.assert_not_called()

    def test_empaquetado_ocupado_difiere_sin_hablar(self):
        for ocupado in ("conectado", "transmitiendo"):
            with self.subTest(ocupado=ocupado):
                frame, anunciar, guardar, abrir, cuando_libre = \
                    self._preparar_aviso(
                        frozen=True, diferir=True,
                        **{ocupado: True})
                cuando_libre.assert_called_once()
                self.assertIs(cuando_libre.call_args.args[0], frame)
                abrir.assert_not_called()
                anunciar.assert_not_called()
                guardar.assert_not_called()

    def test_diferida_abre_la_ventana_al_quedar_libre(self):
        frame, anunciar, guardar, abrir, cuando_libre = \
            self._preparar_aviso(frozen=True, conectado=True, diferir=True)
        abrir.assert_not_called()
        diferida = cuando_libre.call_args.args[1]
        diferida()
        abrir.assert_called_once()
        args, kwargs = abrir.call_args
        self.assertIs(args[0], frame)
        self.assertEqual(kwargs["paquete"].version, VERSION_NUEVA)
        self.assertTrue(kwargs["al_arrancar"])
        anunciar.assert_not_called()
        guardar.assert_not_called()

    def test_sin_empaquetar_hace_aviso_hablado(self):
        _, anunciar, guardar, abrir, _ = self._preparar_aviso(frozen=False)
        abrir.assert_not_called()
        anunciar.assert_called_once()
        guardar.assert_called_once_with(VERSION_NUEVA)

    def test_sin_version_nueva_no_hace_nada(self):
        _, anunciar, guardar, abrir, _ = self._preparar_aviso(
            version=APP_VERSION, frozen=True)
        abrir.assert_not_called()
        anunciar.assert_not_called()
        guardar.assert_not_called()

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

    def _resultado_empaquetado(self, resultado, frozen=True):
        """Corre el gancho del resultado con ventana falsa y lo devuelve."""
        demoras = self._reloj()
        self._doble(mock.patch.object(sys, "frozen", frozen, create=True))
        self._doble(mock.patch.object(
            actualizacion, "tomar_resultado", return_value=resultado))
        ventanas = []

        def fabrica(padre, titulo):
            ventana = VentanaFalsa(padre, titulo)
            ventanas.append(ventana)
            return ventana

        dialogo = self._doble(mock.patch(
            "bellbird.ui.gui_actualizacion.DialogoActualizacion",
            side_effect=fabrica))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        sonido = self._doble(mock.patch.object(app._snd, "reproducir"))
        self._doble(mock.patch.object(
            app.aviso_diferido, "cuando_libre",
            side_effect=lambda frame, funcion, *args, **kwargs: funcion(
                *args, **kwargs)))
        frame = self._frame()
        app.programar_resultado_actualizacion(frame)
        self.assertEqual([4000], demoras)
        return (ventanas[0] if ventanas else None), anunciar, sonido, dialogo

    def test_resultado_empaquetado_ok_abre_ventana_en_100(self):
        ventana, anunciar, sonido, _ = self._resultado_empaquetado(
            {"resultado": "ok", "hacia": VERSION_NUEVA})
        self.assertEqual("Actualización", ventana.titulo)
        self.assertTrue(ventana.mostrada)
        self.assertIn(
            f"{APP_NAME} se actualizó a la versión {VERSION_NUEVA}.",
            ventana.estados)
        self.assertEqual(100, ventana.progresos[-1])
        ventana.btn_cerrar.SetFocus.assert_called()
        anunciar.assert_not_called()
        sonido.assert_called_once_with("actualizacion_lista")

    def test_resultado_empaquetado_fallido_abre_ventana_en_0_y_suena(self):
        ventana, anunciar, sonido, _ = self._resultado_empaquetado(
            {"resultado": "fallo", "motivo": "corte de luz"})
        self.assertIn("La actualización no se completó: corte de luz. "
                      f"Sigue la versión {APP_VERSION}.", ventana.estados)
        self.assertEqual(0, ventana.progresos[-1])
        ventana.btn_cerrar.SetFocus.assert_called()
        anunciar.assert_not_called()
        sonido.assert_called_once_with("error")

    def test_resultado_desde_fuente_solo_anuncia_sin_ventana(self):
        ventana, anunciar, sonido, dialogo = self._resultado_empaquetado(
            {"resultado": "fallo", "motivo": "corte de luz"}, frozen=False)
        self.assertIsNone(ventana)
        dialogo.assert_not_called()
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
        self._doble(mock.patch.object(sys, "frozen", False, create=True))
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version",
            return_value=_paquete("9.9.9")))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        leer = self._doble(mock.patch.object(
            app, "leer_version_avisada", return_value=""))
        guardar = self._doble(mock.patch.object(app, "guardar_version_avisada"))
        frame = self._frame()
        app.programar_aviso_version(frame)
        self.assertEqual([10000], demoras)
        anunciar.assert_called_once_with(
            f"Hay una versión nueva de {APP_NAME}, la 9.9.9. "
            "Para instalarla: menú Ayuda, Buscar actualizaciones.")
        guardar.assert_called_once_with("9.9.9")
        # Ya avisada: silencio.
        anunciar.reset_mock()
        leer.return_value = "9.9.9"
        app.programar_aviso_version(frame)
        anunciar.assert_not_called()

    def test_sin_conexion_no_anuncia(self):
        self._reloj()
        self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version", return_value=None))
        anunciar = self._doble(mock.patch.object(app, "anunciar"))
        guardar = self._doble(mock.patch.object(app, "guardar_version_avisada"))
        app.programar_aviso_version(self._frame())
        anunciar.assert_not_called()
        guardar.assert_not_called()

    def test_opcion_desmarcada_no_consulta_pero_limpia(self):
        self._reloj()
        limpiar = self._doble(mock.patch.object(
            actualizacion, "limpiar_restos"))
        consultar = self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version"))
        frame = types.SimpleNamespace(
            _config={"buscar_actualizaciones_al_iniciar": False})
        app.programar_aviso_version(frame)
        limpiar.assert_called_once_with()
        consultar.assert_not_called()

    def test_opcion_marcada_consulta(self):
        self._reloj()
        self._doble(mock.patch.object(actualizacion, "limpiar_restos"))
        consultar = self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version", return_value=None))
        frame = types.SimpleNamespace(
            _config={"buscar_actualizaciones_al_iniciar": True})
        app.programar_aviso_version(frame)
        consultar.assert_called_once_with()

    def test_sin_clave_consulta_por_defecto(self):
        self._reloj()
        self._doble(mock.patch.object(actualizacion, "limpiar_restos"))
        consultar = self._doble(mock.patch.object(
            actualizacion, "consultar_ultima_version", return_value=None))
        app.programar_aviso_version(self._frame())
        consultar.assert_called_once_with()

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
        app.programar_aviso_version(self._frame())
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
            app.programar_aviso_version(self._frame())

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


class TestDialogoNotas(unittest.TestCase):
    """La lógica de los métodos del diálogo, sin wx: self doble."""

    def _doble(self):
        return mock.Mock()

    def test_notas_limpia_markdown_y_ubica_el_cursor(self):
        from bellbird.ui import gui_actualizacion as ui
        doble = self._doble()
        ui.DialogoActualizacion.notas(doble, "\r\n\r\n- **Uno** seguido")
        doble.txt_notas.SetValue.assert_called_once_with("• Uno seguido")
        doble.txt_notas.Show.assert_called_once_with()
        doble.txt_notas.SetInsertionPoint.assert_called_once_with(0)
        doble.txt_notas.ShowPosition.assert_called_once_with(0)

    def test_notas_vacias_ocultan_el_cuadro(self):
        from bellbird.ui import gui_actualizacion as ui
        doble = self._doble()
        ui.DialogoActualizacion.notas(doble, "   \r\n")
        doble.txt_notas.SetValue.assert_called_once_with("")
        doble.txt_notas.Hide.assert_called_once_with()
        doble.txt_notas.SetInsertionPoint.assert_not_called()

    def test_etiqueta_cerrar_cambia_el_boton(self):
        from bellbird.ui import gui_actualizacion as ui
        doble = self._doble()
        ui.DialogoActualizacion.etiqueta_cerrar(doble, "&Más tarde")
        doble.btn_cerrar.SetLabel.assert_called_once_with("&Más tarde")


class TestCableado(unittest.TestCase):

    def _texto_gui(self):
        ruta = (Path(__file__).resolve().parent.parent
                / "bellbird" / "ui" / "gui.py")
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
        self.assertIn("programar_aviso_version(frame)", cuerpo)
        self.assertIn("programar_resultado_actualizacion(frame)", cuerpo)

    def test_menu_ayuda_ofrece_buscar_antes_de_acerca(self):
        ruta = (Path(__file__).resolve().parent.parent
                / "bellbird" / "ui" / "gui_menu.py")
        texto = ruta.read_text(encoding="utf-8")
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


class TestRegistraLoQueFalla(unittest.TestCase):
    """El ESCONDE de la ventana deja su línea en el registro."""

    def test_borrado_del_zip_que_falla_deja_registro(self):
        flujo = app._FlujoActualizacion(mock.Mock(), mock.Mock())
        flujo.paquete_elegido = _paquete()
        flujo.ventana.en_hilo_principal.side_effect = (
            lambda funcion, *args: funcion(*args))
        with mock.patch.object(actualizacion, "extraer_paquete",
                               return_value=Path("raiz")), \
                mock.patch.object(actualizacion, "validar_paquete",
                                   return_value="App.exe"), \
                mock.patch.object(Path, "unlink",
                                   side_effect=OSError("bloqueado")):
            with self.assertLogs(app.logger, level="DEBUG") as registros:
                flujo._run_extraer()
        self.assertTrue(any("no se pudo borrar" in mensaje
                            for mensaje in registros.output))


def _crear_hilo_en_linea(destino, nombre, **kwargs):
    hilo = mock.Mock()
    hilo.start.side_effect = lambda: destino(*kwargs.get("args", ()))
    hilo.nombre = nombre
    return hilo


class TestPseudoAvisos(unittest.TestCase):
    """Anuncios propios salen marcados (sin ventana: corre acá)."""

    def _flujo(self):
        ventana = VentanaFalsa(None, "titulo")
        flujo = app._FlujoActualizacion(
            types.SimpleNamespace(Close=mock.Mock()), ventana)
        return flujo, ventana

    def test_avisos_propios_salen_marcados(self):
        captados = []
        with con_pseudo(), \
                mock.patch.object(app, "anunciar", captados.append), \
                mock.patch.object(app._snd, "reproducir"), \
                mock.patch.object(app, "guardar_version_avisada"), \
                mock.patch.object(app.diagnostico, "crear_hilo",
                                  side_effect=_crear_hilo_en_linea), \
                mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(actualizacion, "carpeta_admite_escritura",
                                  return_value=True), \
                mock.patch.object(actualizacion, "descargar_paquete",
                                  return_value=actualizacion.ResultadoDescarga(
                                      True, "paquete descargado")), \
                mock.patch.object(actualizacion, "extraer_paquete",
                                  return_value=Path("raiz")), \
                mock.patch.object(actualizacion, "validar_paquete",
                                  return_value="App.exe"):
            flujo, ventana = self._flujo()
            flujo.paquete_elegido = _paquete()
            flujo._mostrar_respuesta(_paquete())
            flujo._mostrar_sin_respuesta()
            flujo._descargar()
            flujo._actualizar_progreso(40)
            flujo._mostrar_paquete_invalido("falta el ejecutable")
            flujo._mostrar_listo(Path("raiz"), "App.exe")
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(False, "descarga cancelada"))
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(False, "la firma SHA-256 no coincide"))
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(False, "boom"))
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(False, ""))
            app._avisar_version("9.9.9")
            vistos = list(ventana.anuncios) + ventana.textos_sin_anunciar + captados
        self.assertTrue(vistos)
        for texto in vistos:
            self.assertTrue(texto.startswith("[¡"), texto)

    def test_descarga_que_falla_en_red_avisa_marcado(self):
        def descargar(*args, **kwargs):
            raise RuntimeError("corte de luz")

        with con_pseudo(), \
                mock.patch.object(app.diagnostico, "crear_hilo",
                                  side_effect=_crear_hilo_en_linea), \
                mock.patch.object(actualizacion, "descargar_paquete",
                                  side_effect=descargar):
            flujo, ventana = self._flujo()
            flujo.paquete_elegido = _paquete()
            flujo._descargar()
        self.assertIn("[¡La descarga no se completó: "
                      "[¡no se pudo descargar el paquete: corte de luz!].!]",
                      ventana.anuncios)

    def test_instalar_que_falla_avisa_marcado(self):
        with con_pseudo(), \
                mock.patch.object(actualizacion, "lanzar_instalador",
                                  side_effect=RuntimeError("sin permiso")):
            flujo, ventana = self._flujo()
            flujo.paquete_elegido = _paquete()
            flujo._instalar(Path("raiz"), "App.exe")
        self.assertIn("[¡No se pudo iniciar la instalación: sin permiso.!]",
                      ventana.anuncios)

    def test_codigo_firma_distinta_muestra_el_de_firma(self):
        flujo, ventana = self._flujo()
        with con_pseudo():
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(
                    False, "la firma SHA-256 no coincide",
                    "firma_distinta"))
        self.assertEqual(
            ventana.estados,
            ["[¡La descarga no se completó: "
             "la firma SHA-256 no coincide.!]"])

    def test_codigo_cancelada_muestra_cancelada(self):
        flujo, ventana = self._flujo()
        with con_pseudo():
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(
                    False, "descarga cancelada", "cancelada"))
        self.assertEqual(ventana.estados, ["[¡Descarga cancelada.!]"])

    def test_sin_firma_muestra_el_generico_y_no_el_de_firma(self):
        flujo, ventana = self._flujo()
        with con_pseudo():
            flujo._mostrar_descarga_fallida(
                actualizacion.ResultadoDescarga(
                    False, "el paquete no trae firma"))
        self.assertEqual(
            ventana.estados,
            ["[¡La descarga no se completó: el paquete no trae firma.!]"])

    def test_resultado_de_otro_modulo_pasa_tal_cual(self):
        # El texto lo arma `bellbird/core/actualizacion.py`, ya traducido.
        resultado = {"resultado": "fallo", "motivo": "corte de luz"}
        captados = []
        with mock.patch.object(actualizacion, "tomar_resultado",
                               return_value=resultado), \
                mock.patch.object(app, "anunciar", captados.append), \
                mock.patch.object(app._snd, "reproducir"):
            app._anunciar_resultado()
        self.assertEqual(
            captados,
            [actualizacion.texto_resultado(resultado, APP_VERSION)])


# La ventana genérica ya pasa por gettext: no quedan pendientes.
PENDIENTES_OTRO_MODULO = ()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoVentana(unittest.TestCase):
    """Pseudotraducción de la ventana (la corre el advisor)."""

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def _abrir(self, vistos, pulsar=False, **kwargs):
        from bellbird.ui.gui_actualizacion import DialogoActualizacion
        frozen = kwargs.pop("frozen", True)
        admite = kwargs.pop("admite", True)
        frame = wx.Frame(None)
        self.addCleanup(destruir, frame)
        with mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=kwargs.pop("consultar", None)), \
                mock.patch.object(app.diagnostico, "crear_hilo",
                                  side_effect=_crear_hilo_en_linea), \
                mock.patch.object(sys, "frozen", frozen, create=True), \
                mock.patch.object(actualizacion, "carpeta_admite_escritura",
                                  return_value=admite), \
                mock.patch.object(DialogoActualizacion, "en_hilo_principal",
                                  lambda ventana, funcion, *args: funcion(*args)), \
                mock.patch.object(app.aviso_diferido, "cuando_libre",
                                  side_effect=lambda marco, funcion, *a, **k: funcion(*a, **k)), \
                mock.patch("bellbird.ui.gui_actualizacion.anunciar"), \
                mock.patch.object(app._snd, "reproducir"), \
                mock.patch("webbrowser.open"):
            app.abrir_ventana_actualizacion(frame, **kwargs)
            ventana = frame._ventana_actualizar_app
            self.addCleanup(destruir, ventana)
            if pulsar:
                ventana._accion()
            vistos.extend(textos_sin_marcar(ventana))
            return frame, ventana

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        from bellbird.ui import gui_actualizacion
        vistos = []
        with con_pseudo(), \
                mock.patch.object(actualizacion, "descargar_paquete",
                                  return_value=actualizacion.ResultadoDescarga(
                                      True, "paquete descargado")), \
                mock.patch.object(actualizacion, "extraer_paquete",
                                  return_value=Path("raiz")), \
                mock.patch.object(actualizacion, "validar_paquete",
                                  return_value="App.exe"):
            self._abrir(vistos, paquete=_paquete(VERSION_NUEVA),
                        frozen=True, admite=True, pulsar=True)
            self._abrir(vistos, paquete=_paquete(VERSION_NUEVA),
                        frozen=True, admite=True, al_arrancar=True)
            real = gui_actualizacion.DialogoActualizacion
            creadas = []

            def fabrica(padre, titulo):
                ventana_nueva = real(padre, titulo)
                creadas.append(ventana_nueva)
                return ventana_nueva

            frame = wx.Frame(None)
            self.addCleanup(destruir, frame)
            with mock.patch.object(gui_actualizacion, "DialogoActualizacion",
                                   side_effect=fabrica), \
                    mock.patch.object(app._snd, "reproducir"), \
                    mock.patch("bellbird.ui.gui_actualizacion.anunciar"):
                app._mostrar_resultado_en_ventana(frame, "ejemplo", True)
            self.assertEqual(len(creadas), 1)
            self.addCleanup(destruir, creadas[0])
            vistos.extend(textos_sin_marcar(creadas[0]))
        self.assertEqual(sorted(set(vistos)), sorted(PENDIENTES_OTRO_MODULO))


if __name__ == "__main__":
    unittest.main()
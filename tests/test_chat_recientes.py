"""Pruebas de LecturaRecientes, sin ventanas salvo la clase real.

`TestLecturaRecientes` usa lista y globales falsos y no abre nada: se corre
acá. `TestRegistroRealRecientes` registra de verdad en Windows con una
ventana oculta.
"""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from bellbird.core.atajos import ATAJOS_FIJOS_DEFAULTS
from bellbird.core.config import APP_NAME
from bellbird.core.idioma import _
from bellbird.ui import atajos_globales, chat_recientes, gui
from bellbird.ui.atajos_globales import AtajosGlobales, combinacion_ctrl_mayus
from bellbird.voice.cola_tts import ColaTTS


class _ListaFalsa:
    def __init__(self, filas):
        self._filas = list(filas)

    def GetCount(self):
        return len(self._filas)

    def GetString(self, i):
        return self._filas[i]


class _GlobalesFalsos:
    def __init__(self, *args, **kwargs):
        self.activaciones = []
        self.desactivaciones = 0
        self.fallidos = []
        self._activos = False

    @property
    def activos(self):
        return self._activos

    def activar(self, textos):
        self.activaciones.append(dict(textos))
        self._activos = True
        return list(self.fallidos)

    def desactivar(self):
        self.desactivaciones += 1
        self._activos = False


def _recientes(config, filas=(), cola=None):
    with mock.patch.object(atajos_globales, "AtajosGlobales",
                           _GlobalesFalsos):
        lector = chat_recientes.LecturaRecientes(
            mock.Mock(), _ListaFalsa(filas), dict(config), cola)
    return lector


class TestLecturaRecientes(unittest.TestCase):

    def test_leer_anuncia_la_fila_correcta(self):
        lector = _recientes({}, ["primero", "segundo", "último"])
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.leer(1)
        anunciar.assert_called_once_with("último")

    def test_leer_con_menos_filas_avisa_cuantas_hay(self):
        lector = _recientes({}, ["solo uno"])
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.leer(5)
        anunciar.assert_called_once_with("El chat tiene 1 mensaje.")

    def test_leer_sin_mensajes_avisa_que_no_hay(self):
        lector = _recientes({})
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.leer(1)
        anunciar.assert_called_once_with("Todavía no hay mensajes en el chat.")

    def test_con_voz_adelanta_en_la_cola_y_no_anuncia(self):
        cola = ColaTTS()
        cola.put({"texto_tts": "en espera", "autor": "otro"})
        lector = _recientes({"lectura_recientes": "voz"},
                            ["primero", "segundo", "último"], cola)
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.leer(1)
        anunciar.assert_not_called()
        self.assertEqual(cola.get(),
                         {"texto_tts": "último", "autor": ""})
        self.assertEqual(cola.get()["texto_tts"], "en espera")

    def test_con_lector_anuncia_y_no_toca_la_cola(self):
        cola = mock.Mock()
        lector = _recientes({"lectura_recientes": "lector"},
                            ["primero", "último"], cola)
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.leer(1)
        anunciar.assert_called_once_with("último")
        cola.adelantar.assert_not_called()

    def test_con_voz_sin_cola_anuncia(self):
        lector = _recientes({"lectura_recientes": "voz"},
                            ["primero", "último"])
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.leer(1)
        anunciar.assert_called_once_with("último")

    def test_aplicar_con_preferencia_encendida_activa_y_anuncia(self):
        lector = _recientes({"lectura_atajos_globales": True})
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.aplicar_preferencias()
        self.assertEqual(lector._globales.activaciones, [
            {a: ATAJOS_FIJOS_DEFAULTS[a] for a in chat_recientes.ORDEN}])
        anunciar.assert_called_once_with(chat_recientes.TEXTO_ACTIVOS)

    def test_aplicar_con_preferencia_apagada_suelta_y_anuncia(self):
        lector = _recientes({"lectura_atajos_globales": True})
        lector._globales._activos = True
        lector._config["lectura_atajos_globales"] = False
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.aplicar_preferencias()
        anunciar.assert_called_once_with(
            _(chat_recientes.TEXTO_SOLO).format(app=APP_NAME))

    def test_aplicar_no_repite_si_ya_esta_activo(self):
        lector = _recientes({"lectura_atajos_globales": True})
        lector._globales._activos = True
        lector._globales_atajos = lector._textos()
        with mock.patch.object(gui, "anunciar") as anunciar:
            lector.aplicar_preferencias()
        self.assertEqual(lector._globales.activaciones, [])
        anunciar.assert_not_called()

    def test_fallo_al_activar_anuncia_con_sonido(self):
        lector = _recientes({"lectura_atajos_globales": True})
        lector._globales.fallidos = ["Ctrl+Mayús+1"]
        with mock.patch.object(gui, "anunciar") as anunciar, \
                mock.patch.object(chat_recientes._snd, "reproducir") as sonar:
            lector.aplicar_preferencias()
        anunciar.assert_called_once()
        self.assertIn("Ctrl+Mayús+1", anunciar.call_args.args[0])
        sonar.assert_called_once_with("atajos_ocupados")

    def test_cerrar_suelta_y_nunca_lanza(self):
        lector = _recientes({})
        lector.cerrar()
        self.assertEqual(lector._globales.desactivaciones, 1)
        with mock.patch.object(lector._globales, "desactivar",
                               side_effect=Exception("caído")):
            lector.cerrar()

    def test_no_lee_atributos_privados_ajenos(self):
        import ast
        from pathlib import Path
        arbol = ast.parse((Path(chat_recientes.__file__)).read_text(
            encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ClassDef) or nodo.name != "LecturaRecientes":
                continue
            for sub in ast.walk(nodo):
                if (isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id in ("ventana", "lista")
                        and sub.attr.startswith("_")):
                    self.fail(f"lee privado ajeno: {sub.value.id}.{sub.attr}")


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_avisos_de_atajos_salen_marcados(self):
        with con_pseudo():
            encendido = _recientes({"lectura_atajos_globales": True})
            with mock.patch.object(gui, "anunciar") as anunciar_on:
                encendido.aplicar_preferencias()
            apagado = _recientes({"lectura_atajos_globales": True})
            apagado._globales._activos = True
            apagado._config["lectura_atajos_globales"] = False
            with mock.patch.object(gui, "anunciar") as anunciar_off:
                apagado.aplicar_preferencias()
            marcados = [_(chat_recientes.TEXTO_ACTIVOS),
                        _(chat_recientes.TEXTO_SOLO).format(app=APP_NAME)]
        for llamar in (anunciar_on, anunciar_off):
            llamar.assert_called_once()
            self.assertTrue(llamar.call_args.args[0].startswith("[¡"),
                            llamar.call_args.args[0])
        self.assertIn(APP_NAME, anunciar_off.call_args.args[0])
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


class TestRegistroRealRecientes(unittest.TestCase):
    """Registra de verdad los diez fijos y los suelta. Abre ventanas."""

    def setUp(self):
        import wx
        from tests.ventanas_prueba import destruir
        self.app = wx.App(False) if not wx.App.Get() else wx.App.Get()
        self.frame = wx.Frame(None)
        self.addCleanup(destruir, self.frame)
        self.otro = wx.Frame(None)
        self.addCleanup(destruir, self.otro)

    def test_registra_y_suelta_de_verdad(self):
        import wx
        acciones = {accion: (lambda: None)
                    for accion in chat_recientes.ORDEN}
        textos = {accion: ATAJOS_FIJOS_DEFAULTS[accion]
                  for accion in chat_recientes.ORDEN}
        globales = AtajosGlobales(
            self.frame, acciones, orden=chat_recientes.ORDEN,
            base_ids=chat_recientes.BASE_IDS, traducir=combinacion_ctrl_mayus)
        self.addCleanup(globales.desactivar)
        fallidos = globales.activar(textos)
        if fallidos:
            self.skipTest("combinaciones tomadas por otro programa: "
                          + ", ".join(fallidos))
        self.assertTrue(globales.activos)
        for indice, accion in enumerate(chat_recientes.ORDEN):
            mods, vk = combinacion_ctrl_mayus(textos[accion])
            self.assertFalse(self.otro.RegisterHotKey(
                chat_recientes.BASE_IDS + indice, mods, vk))
        globales.desactivar()
        self.assertFalse(globales.activos)
        for indice, accion in enumerate(chat_recientes.ORDEN):
            mods, vk = combinacion_ctrl_mayus(textos[accion])
            self.assertTrue(self.otro.RegisterHotKey(
                chat_recientes.BASE_IDS + indice, mods, vk))
            self.otro.UnregisterHotKey(chat_recientes.BASE_IDS + indice)


if __name__ == "__main__":
    unittest.main()

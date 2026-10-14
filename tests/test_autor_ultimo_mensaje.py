"""Cableado del autor del último mensaje (F3): el item de voz lleva el
nombre visible y las relecturas desde la lista también."""

import queue
import types
import unittest
from unittest import mock

import main
from main import Stats, procesar_entrante
from ytchat.capture import alias
from ytchat.ui import gui
from ytchat.ui import gui_comentarios


class TestItemLlevaAutorVisible(unittest.TestCase):

    def _cfg(self, **kw):
        base = {
            "usuarios_silenciados": [],
            "palabras_silenciadas": [],
            "silenciados_ocultar": set(),
            "silenciados_runtime": set(),
            "silenciar_lectura": False,
            "limpiar_emojis": True,
            "eliminar_urls": False,
            "max_longitud_mensaje": 200,
            "umbral_solo_nombre": 0,
            "formato_prefijo": "nombre_mensaje",
            "estrategia": "todas",
            "tamanio_maximo": 10,
        }
        base.update(kw)
        return base

    def test_el_item_lleva_el_alias_que_se_oyo(self):
        autor = "xX_gamer_29384756_Xx"
        alias.usar(alias.poner({}, autor, "Carlos"))
        self.addCleanup(alias.usar, {})
        cola = queue.Queue()
        procesar_entrante(autor, "hola", main.TIPO_TEXTO, "", "canal", cola,
                           self._cfg(), Stats(), on_message=mock.Mock())
        item = cola.get_nowait()
        self.assertEqual(item["autor"], "Carlos")
        self.assertIn("Carlos", item["texto_tts"])


class TestRelecturasLlevanAutor(unittest.TestCase):

    def _frame_chat(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._cola = queue.Queue()
        frame._config = {"limpiar_emojis": True,
                         "formato_prefijo": "nombre_mensaje"}
        frame._get_selected_data = mock.Mock(return_value=types.SimpleNamespace(
            autor="Ana", texto="hola mundo"))
        return frame

    def test_releer_desde_la_lista_lleva_el_autor(self):
        frame = self._frame_chat()
        frame._releer_mensaje()
        item = frame._cola.get_nowait()
        self.assertEqual(item["autor"], "Ana")
        self.assertIn("hola mundo", item["texto_tts"])

    def test_releer_comentario_lleva_el_autor(self):
        panel = gui_comentarios.ComentariosPanel.__new__(
            gui_comentarios.ComentariosPanel)
        panel._cola = queue.Queue()
        panel._config = {"limpiar_emojis": True,
                         "formato_prefijo": "nombre_mensaje"}
        panel._seleccionado = mock.Mock(return_value=types.SimpleNamespace(
            autor="Beto", texto="buenas"))
        panel._leer()
        item = panel._cola.get_nowait()
        self.assertEqual(item["autor"], "Beto")
        self.assertIn("buenas", item["texto_tts"])


if __name__ == "__main__":
    unittest.main()

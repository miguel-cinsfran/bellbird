"""Pruebas del enganche de búsqueda al teclear, sin ventanas.

El listbox y el evento son mocks: no se crea ningún control ni wx.App.
Todo se comprueba a través del manejador enganchado en wx.EVT_CHAR.
"""

import unittest
from unittest import mock

from ytchat.ui import busqueda_teclado
from ytchat.ui.busqueda_teclado import instalar_busqueda_tipo


def _lista(textos, seleccion=None):
    listbox = mock.Mock()
    if seleccion is None:
        seleccion = busqueda_teclado.wx.NOT_FOUND
    listbox.GetSelection.return_value = seleccion
    return listbox


def _tecla(letra, ctrl=False, alt=False):
    evento = mock.Mock()
    evento.ControlDown.return_value = ctrl
    evento.AltDown.return_value = alt
    evento.GetUnicodeKey.return_value = ord(letra)
    return evento


def _instalar(textos, seleccion=None):
    listbox = _lista(textos, seleccion)
    instalar_busqueda_tipo(listbox, lambda: list(textos))
    manejador = listbox.Bind.call_args.args[1]
    return listbox, manejador


class TestBusquedaAlTeclear(unittest.TestCase):

    def test_instalar_enlaza_char(self):
        listbox, manejador = _instalar(["Ana: hola, 12:00"])

        listbox.Bind.assert_called_once()
        tipo, _ = listbox.Bind.call_args.args
        self.assertIs(tipo, busqueda_teclado.wx.EVT_CHAR)
        self.assertTrue(callable(manejador))

    def test_letra_que_encuentra_selecciona_y_anuncia(self):
        textos = ["Ana: hola, 12:00", "Miguel: buenas, 12:01"]
        listbox, manejador = _instalar(textos)

        with mock.patch.object(busqueda_teclado.wx, "CallLater"), \
                mock.patch.object(busqueda_teclado, "anunciar") as anunciar:
            manejador(_tecla("m"))

        listbox.SetSelection.assert_called_once_with(1)
        anunciar.assert_called_once_with("Miguel: buenas, 12:01")

    def test_sin_coincidencia_avisa_y_descarta_la_letra(self):
        textos = ["Ana: hola, 12:00"]
        listbox, manejador = _instalar(textos)

        with mock.patch.object(busqueda_teclado.wx, "CallLater"), \
                mock.patch.object(busqueda_teclado, "anunciar") as anunciar:
            manejador(_tecla("z"))
            anunciar.assert_called_once_with("No hay coincidencias con z")
            listbox.SetSelection.assert_not_called()
            # La siguiente tecla busca con el buffer anterior más la nueva:
            # si la "z" no se hubiera descartado, el buffer sería "za" y no
            # habría coincidencia.
            manejador(_tecla("a"))

        listbox.SetSelection.assert_called_once_with(0)
        self.assertEqual(anunciar.call_count, 2)
        anunciar.assert_called_with("Ana: hola, 12:00")

    def test_con_ctrl_o_alt_no_busca(self):
        for modificador in ("ctrl", "alt"):
            with self.subTest(modificador=modificador):
                textos = ["Ana: hola, 12:00"]
                listbox, manejador = _instalar(textos)
                evento = _tecla("a", ctrl=(modificador == "ctrl"),
                                alt=(modificador == "alt"))

                with mock.patch.object(busqueda_teclado.wx, "CallLater") as programar, \
                        mock.patch.object(busqueda_teclado, "anunciar") as anunciar:
                    manejador(evento)

                evento.Skip.assert_called_once_with()
                listbox.SetSelection.assert_not_called()
                anunciar.assert_not_called()
                programar.assert_not_called()

    def test_espacio_con_buffer_vacio_no_busca(self):
        textos = ["Ana: hola, 12:00"]
        listbox, manejador = _instalar(textos)
        evento = _tecla(" ")

        with mock.patch.object(busqueda_teclado.wx, "CallLater") as programar, \
                mock.patch.object(busqueda_teclado, "anunciar") as anunciar:
            manejador(evento)

        evento.Skip.assert_called_once_with()
        anunciar.assert_not_called()
        programar.assert_not_called()

    def test_segunda_letra_que_ya_coincide_no_mueve(self):
        textos = ["Miguel: hola, 12:00", "Ana: chau, 12:01"]
        listbox, manejador = _instalar(textos, seleccion=0)

        with mock.patch.object(busqueda_teclado.wx, "CallLater"), \
                mock.patch.object(busqueda_teclado, "anunciar") as anunciar:
            manejador(_tecla("m"))
            manejador(_tecla("i"))

        listbox.SetSelection.assert_called_once_with(0)
        anunciar.assert_called_once()

    def test_segunda_tecla_reprograma_el_temporizador(self):
        textos = ["Ana: hola, 12:00", "Anselmo: chau, 12:01"]
        listbox, manejador = _instalar(textos)
        temporizador_viejo = mock.Mock()
        temporizador_nuevo = mock.Mock()

        with mock.patch.object(busqueda_teclado.wx, "CallLater",
                               side_effect=[temporizador_viejo,
                                            temporizador_nuevo]) as programar, \
                mock.patch.object(busqueda_teclado, "anunciar"):
            manejador(_tecla("a"))
            manejador(_tecla("n"))

        temporizador_viejo.Stop.assert_called_once_with()
        temporizador_nuevo.Stop.assert_not_called()
        self.assertEqual(programar.call_count, 2)
        self.assertEqual(programar.call_args_list[1].args[0],
                         busqueda_teclado._MS_RESET_BUSQUEDA)

    def test_resetear_deja_el_buffer_vacio(self):
        textos = ["Beto: hola, 12:00"]
        listbox, manejador = _instalar(textos)

        with mock.patch.object(busqueda_teclado.wx, "CallLater") as programar, \
                mock.patch.object(busqueda_teclado, "anunciar") as anunciar:
            manejador(_tecla("a"))
            anunciar.assert_called_once_with("No hay coincidencias con a")
            # Vence el temporizador pedido en la primera tecla.
            programar.call_args.args[1]()
            manejador(_tecla("b"))

        # Con el buffer vaciado, "b" sola encuentra la fila; si el
        # temporizador no hubiera reseteado, el buffer sería "ab".
        listbox.SetSelection.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()

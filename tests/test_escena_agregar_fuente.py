"""Pruebas del menú Agregar fuente y de su recorrido, sin abrir ventanas."""

import unittest
from types import SimpleNamespace
from unittest import mock

from guyrapu.obs import fuente_nueva, tipos_fuente
from guyrapu.ui import escena_agregar_fuente, escena_acciones_fuente

_ID_OK = 5100
_WXK_RETURN = 13


class EventoTecla:
    def __init__(self, codigo, ctrl=False, alt=False):
        self._codigo = codigo
        self._ctrl = ctrl
        self._alt = alt

    def GetKeyCode(self):
        return self._codigo

    def ControlDown(self):
        return self._ctrl

    def AltDown(self):
        return self._alt

    def Skip(self):
        pass


class Operaciones:
    def __init__(self):
        self.en_vuelo = False
        self.cerrando = False

    def en_hilo(self, tarea, al_terminar):
        al_terminar(tarea())


class Gestor:
    def __init__(self, filas=()):
        self.llamadas = []
        self.filas = list(filas)
        self.ventana = None

    def _pedir(self, tipo, datos=None, parada=None):
        self.llamadas.append((tipo, dict(datos or {})))
        if tipo == "GetInputList":
            return {"inputs": []}
        if tipo == "GetSceneList":
            return {"scenes": []}
        return {}

    def filas_escena(self, escena, parada=None):
        return tuple(self.filas)

    def fuentes(self, escena):
        return ("Cámara", "Chat en el vídeo")

    def usar_ventana(self, escena, valor, parada=None, nombre=""):
        self.ventana = (escena, valor, nombre)
        return "Ahora se captura Champions, de juego.exe."


class Lista:
    def __init__(self):
        self.veces = 0

    def SetFocus(self):
        self.veces += 1


class Pagina:
    def __init__(self, gestor=None):
        self._gestor = gestor or Gestor()
        self._operaciones = Operaciones()
        self._ventana = None
        self.lst_fuentes = Lista()
        self._filas = ()
        self.cargado = None
        self.releido = None

    def _escena(self):
        return "Principal"

    def _destino(self):
        return "Principal", "Color"

    def _cargar_filas(self, filas, fuente):
        self.cargado = (filas, fuente)

    def _releer_filas(self, escena, fuente):
        self.releido = (escena, fuente)


class DialogoNombre:
    valores = []

    def __init__(self, propuesto=""):
        self.propuesto = propuesto

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def ShowModal(self):
        return _ID_OK

    def GetValue(self):
        return self.valores.pop(0)


class MenuTest(unittest.TestCase):
    def test_tiene_los_ocho_tipos_en_orden(self):
        self.assertEqual(
            escena_agregar_fuente.etiquetas_menu(),
            ("&Cámara…", "Captura de &pantalla…", "Captura de &ventana…",
             "Captura de &juego…", "&Imagen…", "&Archivo multimedia…",
             "&Texto…", "&Fuente de otra escena…"))


class NombreTest(unittest.TestCase):
    def test_un_nombre_repetido_avisa_y_vuelve_a_pedirlo(self):
        pagina = Pagina()
        DialogoNombre.valores = ["Imagen", "Imagen 2"]
        anuncios = []
        with mock.patch.object(
                escena_agregar_fuente, "_dialogo_nombre",
                lambda _pagina, propuesto: DialogoNombre(propuesto)), \
                mock.patch.object(escena_agregar_fuente, "anunciar",
                                  anuncios.append):
            nombre = escena_agregar_fuente._pedir_nombre(
                pagina, tipos_fuente.por_clave("imagen"), {"Imagen"})
        self.assertEqual(nombre, "Imagen 2")
        self.assertEqual(anuncios, ["Ya hay una fuente con ese nombre."])


class CancelarTest(unittest.TestCase):
    def test_cancelar_el_nombre_no_crea_nada(self):
        pagina = Pagina()
        with mock.patch.object(
                escena_agregar_fuente, "_pedir_nombre", return_value=None), \
                mock.patch.object(fuente_nueva, "crear") as crear:
            escena_agregar_fuente.agregar(pagina, "imagen")
        crear.assert_not_called()
        self.assertNotIn("CreateInput", [tipo for tipo, _datos
                                         in pagina._gestor.llamadas])

    def test_cancelar_las_propiedades_no_crea_nada(self):
        pagina = Pagina()
        with mock.patch.object(
                escena_agregar_fuente, "_pedir_nombre",
                return_value="Imagen"), \
                mock.patch.object(escena_agregar_fuente.escena_propiedades,
                                  "pedir", return_value=None), \
                mock.patch.object(fuente_nueva, "crear") as crear:
            escena_agregar_fuente.agregar(pagina, "imagen")
        crear.assert_not_called()
        self.assertNotIn("CreateInput", [tipo for tipo, _datos
                                         in pagina._gestor.llamadas])


class AgregarTest(unittest.TestCase):
    def test_al_agregar_relee_con_la_nueva_y_anuncia_la_frase(self):
        pagina = Pagina()
        filas = (SimpleNamespace(nombre="Imagen"),)
        anuncios = []
        with mock.patch.object(
                escena_agregar_fuente, "_pedir_nombre",
                return_value="Imagen"), \
                mock.patch.object(
                    escena_agregar_fuente.escena_propiedades, "pedir",
                    return_value={"archivo": "C:/foto.png"}), \
                mock.patch.object(fuente_nueva, "crear") as crear, \
                mock.patch.object(
                    escena_agregar_fuente.consultas_transmision,
                    "leer_filas", return_value=filas), \
                mock.patch.object(escena_agregar_fuente, "anunciar",
                                  anuncios.append):
            escena_agregar_fuente.agregar(pagina, "imagen")
        crear.assert_called_once_with(
            pagina._gestor._pedir, "Principal", "imagen", "Imagen",
            {"archivo": "C:/foto.png"})
        self.assertEqual(pagina.cargado, (filas, "Imagen"))
        self.assertIn("Imagen agregada a la escena Principal.", anuncios)
        self.assertGreater(pagina.lst_fuentes.veces, 0)

    def test_sin_fuentes_de_otras_escenas_lo_dice(self):
        pagina = Pagina()
        anuncios = []
        with mock.patch.object(
                fuente_nueva, "fuentes_de_otras", return_value=()), \
                mock.patch.object(escena_agregar_fuente, "anunciar",
                                  anuncios.append):
            escena_agregar_fuente.agregar(pagina, "otra_escena")
        self.assertIn("No hay fuentes de otras escenas para agregar.",
                      anuncios)


class VentanaTest(unittest.TestCase):
    def test_el_nombre_elegido_llega_a_usar_ventana(self):
        pagina = Pagina()
        escena_agregar_fuente._usar_ventana_y_leer(
            pagina, "Principal", "Champions:Ventana:juego.exe", "Mi captura")
        self.assertEqual(
            pagina._gestor.ventana,
            ("Principal", "Champions:Ventana:juego.exe", "Mi captura"))


class PropiedadesTest(unittest.TestCase):
    def test_alt_intro_en_la_lista_abre_propiedades(self):
        acciones = object.__new__(escena_acciones_fuente.AccionesFuente)
        acciones._mover = SimpleNamespace(en_curso=False)
        acciones.propiedades = mock.Mock()
        self.assertTrue(acciones.tecla(EventoTecla(_WXK_RETURN, alt=True)))
        acciones.propiedades.assert_called_once_with()

    def test_una_fuente_de_color_avisa_y_no_abre_nada(self):
        pagina = Pagina()
        anuncios = []
        with mock.patch.object(
                fuente_nueva, "propiedades", return_value=("", {})), \
                mock.patch.object(
                    escena_agregar_fuente.escena_propiedades, "pedir") as pedir, \
                mock.patch.object(escena_agregar_fuente, "anunciar",
                                  anuncios.append):
            escena_agregar_fuente.abrir_propiedades(pagina)
        pedir.assert_not_called()
        self.assertIn(
            "Esta fuente no tiene propiedades en Guyrapu. Cámbialas en OBS.",
            anuncios)
        self.assertNotIn("SetInputSettings", [tipo for tipo, _datos
                                              in pagina._gestor.llamadas])


if __name__ == "__main__":
    unittest.main()

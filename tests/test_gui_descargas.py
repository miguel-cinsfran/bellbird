"""Pruebas de accesibilidad del selector de carpeta."""

import unittest
import threading
from unittest import mock

from bellbird.downloads import descargas
from bellbird.ui import gui_descargas
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class TestTablaEstadosSinVentana(unittest.TestCase):
    # Sin ventana: la tabla vive en el módulo, así no se crea ningún control.

    def test_tabla_cubre_los_estados_con_el_texto_de_hoy(self):
        self.assertEqual(set(gui_descargas._ETIQUETAS_ESTADO),
                         {"en_cola", "descargando", "completado",
                          "cancelado", "error"})
        for nombre in ("descargando", "completado", "cancelado", "error"):
            self.assertEqual(gui_descargas._ETIQUETAS_ESTADO[nombre], nombre)
        self.assertEqual(gui_descargas._ETIQUETAS_ESTADO["en_cola"], "en cola")
        self.assertEqual(gui_descargas._texto_estado("error", "sin espacio"),
                         "error: sin espacio")

    def test_celda_de_una_descarga_en_cola_dice_en_cola(self):
        self.assertEqual(gui_descargas._texto_estado("en_cola", ""), "en cola")


class _DobleControl:

    def __init__(self):
        self.etiquetas = []

    def SetLabel(self, texto):
        self.etiquetas.append(texto)


class _DobleSelector:

    def __init__(self):
        self.texto = _DobleControl()
        self.boton = _DobleControl()

    def GetTextCtrl(self):
        return self.texto

    def GetPickerCtrl(self):
        return self.boton


class TestNombrarSelectorCarpeta(unittest.TestCase):

    def test_nombra_campo_y_boton(self):
        selector = _DobleSelector()
        llamadas = []

        def nombrar(control, nombre):
            llamadas.append((control, nombre))

        with mock.patch.object(gui_descargas, "nombre_accesible", nombrar):
            gui_descargas.nombrar_selector_carpeta(selector)

        self.assertEqual(
            llamadas[0], (selector.texto, "Carpeta de destino de las descargas"))
        self.assertEqual(selector.boton.etiquetas, ["Examinar…"])
        self.assertEqual(llamadas[1], (selector.boton, "Examinar…"))
        self.assertTrue(llamadas[1][1].startswith("Examinar"))
        self.assertNotEqual(llamadas[1][1], "Browse")

    def test_acepta_selector_sin_controles_internos(self):
        with mock.patch.object(gui_descargas, "nombre_accesible") as nombrar:
            gui_descargas.nombrar_selector_carpeta(object())

        nombrar.assert_not_called()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestGruposGestorDescargas(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        gui_descargas._registrados.clear()

    def tearDown(self):
        descargas.reiniciar_gestor()
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None

    def _sin_disco(self):
        """El historial no debe tocar el historial_descargas.json real."""
        return (mock.patch.object(gui_descargas.historial_descargas, "cargar",
                                  return_value=[]),
                mock.patch.object(gui_descargas.historial_descargas, "guardar"))

    def test_listas_en_pestanas_con_nombres_accesibles(self):
        dialogo = gui_descargas.GestorDescargasDialog(None)
        try:
            esperados = {
                "Cola de descargas": "Cola",
                "Lista del historial de descargas": "Historial",
            }
            encontrados = {}
            pendientes = list(dialogo.GetChildren())
            while pendientes:
                control = pendientes.pop()
                pendientes.extend(control.GetChildren())
                if control.GetName() in esperados:
                    encontrados[control.GetName()] = control
            self.assertEqual(set(esperados), set(encontrados))
            self.assertEqual(dialogo.pestanas.GetName(), "PestanasDescargas")
            for nombre, control in encontrados.items():
                indice = 0 if esperados[nombre] == "Cola" else 1
                self.assertIs(control.GetParent(), dialogo.pestanas.GetPage(indice))
        finally:
            destruir(dialogo)

    def test_columnas_de_la_cola_ponen_el_progreso_primero(self):
        dialogo = gui_descargas.GestorDescargasDialog(None)
        try:
            self.assertEqual(
                [dialogo.lista.GetColumn(indice).GetText()
                 for indice in range(dialogo.lista.GetColumnCount())],
                ["Progreso", "Estado", "Nombre"])
        finally:
            destruir(dialogo)

    def test_refresco_guarda_cada_dato_en_su_columna(self):
        dialogo = gui_descargas.GestorDescargasDialog(None)
        try:
            item = descargas.ItemDescarga("item", "https://youtu.be/x", "video",
                                          nombre="archivo.mp4")
            item.progreso = 42
            item.estado = "descargando"
            dialogo._gestor._items[item.id] = item
            dialogo._gestor._orden.append(item.id)
            dialogo.lista.InsertItem(0, "0 %")
            dialogo._items_fila[item.id] = 0
            dialogo._fila_items[0] = item.id
            dialogo._refrescar_desde_gestor()
            self.assertEqual(dialogo.lista.GetItemText(0, 0), "42 %")
            self.assertEqual(dialogo.lista.GetItemText(0, 2), "archivo.mp4")
        finally:
            destruir(dialogo)

    def test_refrescar_sin_cambios_no_reescribe_celdas(self):
        dialogo = gui_descargas.GestorDescargasDialog(None)
        try:
            item = descargas.ItemDescarga("item", "https://youtu.be/x", "video",
                                          nombre="archivo.mp4")
            item.progreso = 42
            item.estado = "descargando"
            dialogo._gestor._items[item.id] = item
            dialogo._gestor._orden.append(item.id)
            dialogo.lista.InsertItem(0, "0 %")
            dialogo._items_fila[item.id] = 0
            dialogo._fila_items[0] = item.id
            with mock.patch.object(dialogo.lista, "SetItem",
                                   wraps=dialogo.lista.SetItem) as escribir:
                dialogo._refrescar_desde_gestor()
                self.assertEqual(escribir.call_count, 3)
                escribir.reset_mock()
                dialogo._refrescar_desde_gestor()
                escribir.assert_not_called()
        finally:
            destruir(dialogo)

    def test_cancelar_un_item_terminado_no_cancela_y_avisa(self):
        cargar, guardar = self._sin_disco()
        with cargar, guardar, \
                mock.patch.object(gui_descargas, "anunciar") as anunciar, \
                mock.patch.object(gui_descargas._snd, "reproducir") as sonido:
            dialogo = gui_descargas.GestorDescargasDialog(None)
            try:
                item = descargas.ItemDescarga(
                    "item", "https://youtu.be/abc", "video", nombre="video.mp4")
                dialogo._gestor._items[item.id] = item
                dialogo._gestor._orden.append(item.id)
                dialogo.lista.InsertItem(0, "100 %")
                dialogo._items_fila[item.id] = 0
                dialogo._fila_items[0] = item.id
                dialogo.lista.Select(0)
                for final in gui_descargas._ESTADOS_FINALES:
                    with self.subTest(estado=final):
                        item.estado = final
                        anunciar.reset_mock()
                        sonido.reset_mock()
                        with mock.patch.object(dialogo._gestor, "cancelar") as cancelar:
                            dialogo._on_cancelar(None)
                        cancelar.assert_not_called()
                        anunciar.assert_called_once_with("La descarga ya terminó")
                        sonido.assert_called_once_with("error")
                for pendiente in ("en_cola", "descargando"):
                    with self.subTest(estado=pendiente):
                        item.estado = pendiente
                        anunciar.reset_mock()
                        sonido.reset_mock()
                        with mock.patch.object(dialogo._gestor, "cancelar") as cancelar:
                            dialogo._on_cancelar(None)
                        cancelar.assert_called_once_with(item.id)
                        anunciar.assert_called_once_with("Cancelando descarga")
                        sonido.assert_not_called()
            finally:
                destruir(dialogo)

    def test_fin_avisado_despues_de_cerrar_el_dialogo(self):
        inicio = threading.Event()
        terminar = threading.Event()
        completada = threading.Event()

        def descarga_simulada(_url, _opciones, _progreso, estado, _cancelar):
            inicio.set()
            terminar.wait(1)
            estado("completado", "")
            completada.set()

        cargar, guardar = self._sin_disco()
        with cargar, guardar as guardar_mock, \
                mock.patch.object(descargas, "analizar_url", return_value={}), \
                mock.patch.object(descargas, "descargar", descarga_simulada), \
                mock.patch.object(gui_descargas, "anunciar") as anunciar, \
                mock.patch.object(gui_descargas._snd, "reproducir") as sonido:
            dialogo = gui_descargas.GestorDescargasDialog(None)
            dialogo._gestor.encolar("https://youtu.be/video", lambda *_: None,
                                    lambda *_: None)
            self.assertTrue(inicio.wait(1))
            destruir(dialogo)
            terminar.set()
            self.assertTrue(completada.wait(1))
            wx.Yield()

        anunciar.assert_called_once_with("Descarga completada")
        sonido.assert_called_once_with("descarga_completada")
        # Con el diálogo ya cerrado, la descarga entra igual en el historial.
        guardar_mock.assert_called_once()
        entradas = guardar_mock.call_args.args[1]
        self.assertEqual((entradas[0]["url"], entradas[0]["estado"]),
                         ("video", "completado"))

    def test_avisar_fin_descarga_pasa_por_el_hilo_de_la_gui(self):
        # El suscriptor corre en el hilo de descarga: nada de wx directo.
        with mock.patch.object(gui_descargas.wx, "CallAfter") as call_after, \
                mock.patch.object(gui_descargas, "anunciar") as anunciar:
            gui_descargas._avisar_fin_descarga("completado", "", "v.mp4", None)
        call_after.assert_called_once_with(
            gui_descargas._fin_descarga_en_gui, "completado", "", "v.mp4", None)
        anunciar.assert_not_called()

    def test_terminar_descarga_agrega_una_entrada_al_historial(self):
        cargar, guardar = self._sin_disco()
        with cargar, guardar, mock.patch.object(gui_descargas, "anunciar"), \
                mock.patch.object(gui_descargas._snd, "reproducir"):
            dialogo = gui_descargas.GestorDescargasDialog(None)
            try:
                item = descargas.ItemDescarga(
                    "item", "https://www.youtube.com/watch?v=abc&token=secreto",
                    "video", nombre="video.mp4", carpeta="C:/Descargas")
                gui_descargas._fin_descarga_en_gui("completado", "", item.nombre, item)
                self.assertEqual(dialogo.lista_historial.GetItemCount(), 1)
                self.assertEqual(dialogo.lista_historial.GetItemText(0, 0), "video.mp4")
                self.assertEqual(dialogo._historial[0]["url"], "abc")
                self.assertEqual(dialogo._historial[0]["carpeta"], "C:/Descargas")
                # Un segundo aviso del mismo ítem no duplica la entrada.
                gui_descargas._fin_descarga_en_gui("completado", "", item.nombre, item)
                self.assertEqual(dialogo.lista_historial.GetItemCount(), 1)
            finally:
                destruir(dialogo)

    def test_filas_repobladas_reciben_el_progreso_por_el_temporizador(self):
        # Al reabrir, las filas no tienen callbacks (eran cierres del diálogo
        # anterior): el temporizador vuelca lo que hay en el gestor.
        gestor = descargas.gestor()
        item = descargas.ItemDescarga("item", "https://youtu.be/abc", "video",
                                      nombre="https://youtu.be/abc")
        gestor._items[item.id] = item
        gestor._orden.append(item.id)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        try:
            self.assertEqual(dialogo.lista.GetItemText(0, 0), "0 %")
            self.assertTrue(dialogo._temporizador.IsRunning())
            item.progreso = 42
            item.nombre = "archivo.mp4"
            item.estado = "descargando"
            dialogo._refrescar_desde_gestor()
            self.assertEqual(dialogo.lista.GetItemText(0, 0), "42 %")
            self.assertEqual(dialogo.lista.GetItemText(0, 1), "descargando")
            self.assertEqual(dialogo.lista.GetItemText(0, 2), "archivo.mp4")
            item.estado = "error"
            item.mensaje = "sin espacio"
            dialogo._refrescar_desde_gestor()
            self.assertEqual(dialogo.lista.GetItemText(0, 1), "error: sin espacio")
        finally:
            destruir(dialogo)

    def test_cerrar_para_el_temporizador_y_suelta_el_dialogo_activo(self):
        dialogo = gui_descargas.GestorDescargasDialog(None)
        try:
            self.assertIs(gui_descargas._dialogo_activo, dialogo)
            dialogo._soltar()
            self.assertFalse(dialogo._temporizador.IsRunning())
            self.assertIsNone(gui_descargas._dialogo_activo)
        finally:
            destruir(dialogo)

    def test_vaciar_historial_deja_la_lista_sin_filas(self):
        with mock.patch.object(gui_descargas.historial_descargas, "cargar",
                               return_value=[]), \
                mock.patch.object(gui_descargas.historial_descargas, "guardar") as guardar, \
                mock.patch.object(gui_descargas.wx, "MessageBox", return_value=wx.YES), \
                mock.patch.object(gui_descargas, "anunciar") as anunciar:
            dialogo = gui_descargas.GestorDescargasDialog(None)
            try:
                entrada = {"nombre": "video.mp4", "fecha": "2026-08-28T12:00:00",
                           "estado": "completado"}
                dialogo._historial = [entrada]
                dialogo._agregar_fila_historial(entrada)
                dialogo._on_vaciar_historial(None)
                self.assertEqual(dialogo.lista_historial.GetItemCount(), 0)
                guardar.assert_called_once_with(dialogo._ruta_historial, [])
                anunciar.assert_called_once_with("Se borró 1 elemento del historial")
            finally:
                destruir(dialogo)


class TestSonidosDeDescarga(unittest.TestCase):
    """Cada aviso del gestor suena con su sonido propio. Sin ventanas."""

    def setUp(self):
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None
        self._n = 0
        for parche in (
                mock.patch.object(gui_descargas.historial_descargas,
                                  "cargar", return_value=[]),
                mock.patch.object(gui_descargas.historial_descargas,
                                  "guardar"),
                mock.patch.object(gui_descargas, "anunciar")):
            parche.start()
            self.addCleanup(parche.stop)
        parche_sonido = mock.patch.object(gui_descargas._snd, "reproducir")
        self._sonido = parche_sonido.start()
        self.addCleanup(parche_sonido.stop)

    def tearDown(self):
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None

    def _item(self):
        self._n += 1
        return descargas.ItemDescarga(
            f"item-{self._n}", "https://www.youtube.com/watch?v=abc",
            "video", nombre="video.mp4", carpeta="C:/Descargas")

    def test_cada_fin_suena_con_su_sonido(self):
        casos = [("completado", "", "descarga_completada"),
                 ("error", "sin espacio", "descarga_fallida"),
                 ("cancelado", "", "descarga_cancelada")]
        for estado, mensaje, esperado in casos:
            with self.subTest(estado=estado):
                self._sonido.reset_mock()
                item = self._item()
                gui_descargas._fin_descarga_en_gui(
                    estado, mensaje, item.nombre, item)
                self._sonido.assert_called_once_with(esperado)

    def test_el_fin_con_gestor_cerrado_no_lo_abre(self):
        self.assertFalse(hasattr(gui_descargas, "_abrir_gestor_si_cerrado"))
        with mock.patch.object(gui_descargas, "abrir") as abrir:
            item = self._item()
            gui_descargas._fin_descarga_en_gui(
                "completado", "", item.nombre, item)
        abrir.assert_not_called()

    def test_al_descargar_suena_la_iniciada_sin_dialogo_abierto(self):
        self.assertIsNone(gui_descargas._dialogo_activo)
        item = self._item()
        gui_descargas._fin_descarga_en_gui("descargando", "", "x", item)
        self._sonido.assert_called_once_with("descarga_iniciada")
        self.assertNotIn(item.id, gui_descargas._registrados)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoVentana(unittest.TestCase):
    """Pseudotraducción de la ventana (la corre el advisor)."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        cargar = mock.patch.object(gui_descargas.historial_descargas, "cargar", return_value=[])
        guardar = mock.patch.object(gui_descargas.historial_descargas, "guardar")
        with cargar, guardar, con_pseudo():
            dialogo = gui_descargas.GestorDescargasDialog(None)
            # Son números: las tasas de bits no se traducen.
            sin_marcar = textos_sin_marcar(dialogo, propios=("192", "256", "320"))
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        self.assertEqual([], sin_marcar)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoAvisos(unittest.TestCase):
    """Anuncios y cuadros propios salen marcados (la corre el advisor)."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def _dialogo(self):
        cargar = mock.patch.object(gui_descargas.historial_descargas, "cargar", return_value=[])
        guardar = mock.patch.object(gui_descargas.historial_descargas, "guardar")
        cargar.start()
        guardar.start()
        self.addCleanup(cargar.stop)
        self.addCleanup(guardar.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def test_avisos_y_cuadros_propios_salen_marcados(self):
        dialogo = self._dialogo()
        captado = {}

        def caja(mensaje, titulo, estilo, padre=None):
            captado["mensaje"] = mensaje
            captado["titulo"] = titulo
            return wx.ID_OK

        with con_pseudo(), mock.patch.object(gui_descargas.wx, "MessageBox", caja):
            dialogo._on_anadir(None)
            dialogo._on_cancelar(None)
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        dialogo._historial = [{"nombre": "v", "fecha": "f", "estado": "completado"}]
        dialogo._agregar_fila_historial(dialogo._historial[0])
        avisos = []
        with con_pseudo(), mock.patch.object(gui_descargas.wx, "MessageBox", return_value=wx.YES), \
                mock.patch.object(gui_descargas, "anunciar", avisos.append):
            dialogo._on_vaciar_historial(None)
        self.assertTrue(avisos and avisos[0].startswith("[¡"))


if __name__ == "__main__":
    unittest.main()

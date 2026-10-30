"""Pruebas de accesibilidad del selector y de la página única de descargas."""

import unittest
import threading
from unittest import mock

from bellbird.downloads import descargas
from bellbird.downloads import filas_descargas
from bellbird.ui import descargas_acciones, descargas_listas, gui_descargas
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
        self.assertEqual(set(descargas_listas._ETIQUETAS_ESTADO),
                         {"en_cola", "descargando", "completado", "parcial",
                          "cancelado", "error"})
        for nombre in ("descargando", "completado", "cancelado", "error"):
            self.assertEqual(descargas_listas._ETIQUETAS_ESTADO[nombre], nombre)
        self.assertEqual(descargas_listas._ETIQUETAS_ESTADO["en_cola"], "en cola")
        self.assertEqual(descargas_listas._ETIQUETAS_ESTADO["parcial"], "con errores")
        self.assertEqual(descargas_listas._texto_estado("error", "sin espacio"),
                         "error: sin espacio")
        self.assertEqual(descargas_listas._texto_estado("parcial", "1 de 2 vídeos"),
                         "con errores: 1 de 2 vídeos")

    def test_celda_de_una_descarga_en_cola_dice_en_cola(self):
        self.assertEqual(descargas_listas._texto_estado("en_cola", ""), "en cola")


class TestTextoDeItem(unittest.TestCase):
    # Sin ventana: texto_de_item es puro, solo necesita el ítem.

    def _item(self, **cambios):
        item = descargas.ItemDescarga("id", "https://youtu.be/x", "video",
                                      nombre="video.mp4")
        for clave, valor in cambios.items():
            setattr(clave, valor) if False else setattr(item, clave, valor)
        return item

    def test_descargando_basico_dice_descargando(self):
        self.assertEqual(
            descargas_listas.texto_de_item(self._item(estado="descargando")),
            "descargando")

    def test_muestra_video_de_la_lista_velocidad_y_tiempo(self):
        item = self._item(estado="descargando", indice=2, total=4,
                          velocidad=2048, eta=125)
        self.assertEqual(
            descargas_listas.texto_de_item(item),
            "descargando, vídeo 2 de 4, 2 KB/s, quedan 2 minutos")

    def test_procesando_no_muestra_velocidad_ni_tiempo(self):
        item = self._item(estado="descargando", procesando=True,
                          velocidad=2048, eta=125)
        self.assertEqual(descargas_listas.texto_de_item(item), "procesando")

    def test_parcial_muestra_el_mensaje(self):
        item = self._item(estado="parcial", mensaje="1 de 2 vídeos")
        self.assertEqual(descargas_listas.texto_de_item(item),
                         "con errores: 1 de 2 vídeos")


class TestEliminarActiva(unittest.TestCase):
    # Sin ventana: AccionesDescarga.eliminar no toca wx en la rama activa.

    def test_eliminar_activa_no_quita_avisa_y_suena(self):
        gestor = descargas.GestorDescargas(
            {"formato": "mp4", "bitrate": 192, "carpeta": "/tmp"})
        al_cambiar = mock.Mock()
        acciones = descargas_acciones.AccionesDescarga(
            gestor, "ruta-falsa", lambda: None, al_cambiar)
        with mock.patch.object(descargas_acciones, "anunciar") as anunciar, \
                mock.patch.object(descargas_acciones._snd, "reproducir") as sonido:
            for estado in ("descargando", "en_cola"):
                fila = filas_descargas.Fila("k", estado, 0.0, "n", "",
                                            "https://youtu.be/x", "", "", "", None)
                acciones.eliminar(fila)
        anunciar.assert_called_with("Cancela la descarga antes de eliminarla.")
        sonido.assert_called_with("error")
        al_cambiar.assert_not_called()


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
class TestPaginaUnica(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        gui_descargas._registrados.clear()

    def tearDown(self):
        descargas.reiniciar_gestor()
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None

    def _sin_disco(self, entradas=None):
        return (mock.patch.object(descargas_listas.historial_descargas, "cargar",
                                  return_value=list(entradas or [])),
                mock.patch.object(descargas_listas.historial_descargas, "guardar"),
                mock.patch.object(descargas_acciones.historial_descargas, "guardar"))

    def _dialogo(self, entradas=None):
        cargar, guardar, guardar_acc = self._sin_disco(entradas)
        cargar.start()
        guardar.start()
        guardar_acc.start()
        self.addCleanup(cargar.stop)
        self.addCleanup(guardar.stop)
        self.addCleanup(guardar_acc.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def test_una_sola_pestana_descargas_con_columnas(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.pestanas.GetPageCount(), 1)
        self.assertEqual(dialogo.pestanas.GetPageText(0), "Descargas")
        pagina = dialogo.pagina_descargas
        self.assertIsInstance(pagina, descargas_listas.PaginaDescargas)
        self.assertEqual(pagina.lista.GetName(), "Lista de descargas")
        self.assertEqual(
            [pagina.lista.GetColumn(i).GetText()
             for i in range(pagina.lista.GetColumnCount())],
            ["Progreso", "Estado", "Nombre", "Fecha"])
        self.assertEqual(dialogo.pestanas.GetName(), "PestanasDescargas")

    def test_filtro_muestra_cantidades_y_filtra_lista(self):
        dialogo = self._dialogo([
            {"id": "vieja", "nombre": "vieja.mp4", "fecha": "2026-10-29T08:00:00",
             "estado": "completado", "url": "https://youtu.be/viejax",
             "carpeta": "", "ruta": ""},
            {"id": "mala", "nombre": "mala.mp4", "fecha": "2026-10-30T08:00:00",
             "estado": "error", "url": "https://youtu.be/malax",
             "carpeta": "", "ruta": ""}])
        pagina = dialogo.pagina_descargas
        item = descargas.ItemDescarga("cola1", "https://youtu.be/cola1", "video",
                                      nombre="cola1.mp4")
        item.estado = "en_cola"
        dialogo._gestor._items[item.id] = item
        dialogo._gestor._orden.append(item.id)
        pagina.refrescar()
        textos = [pagina.cho_mostrar.GetString(i)
                  for i in range(pagina.cho_mostrar.GetCount())]
        self.assertIn("Todas (3)", textos[0])
        pagina.cho_mostrar.SetSelection(2)
        pagina._on_filtro(None)
        self.assertEqual(pagina.lista.GetItemCount(), 1)
        self.assertEqual(pagina.lista.GetItemText(0, 2), "cola1.mp4")

    def test_menu_solo_lo_que_aplica_y_siempre_globales(self):
        dialogo = self._dialogo([
            {"id": "hecha", "nombre": "hecha.mp4", "fecha": "2026-10-30T08:33:00",
             "estado": "completado", "url": "https://youtu.be/hecha",
             "carpeta": "C:/D", "ruta": "C:/D/hecha.mp4"}])
        pagina = dialogo.pagina_descargas
        pagina.refrescar()
        pagina.lista.Select(0)
        vistos = {}

        def falso_popup(menu):
            vistos["etiquetas"] = [i.GetItemLabel()
                                   for i in menu.GetMenuItems()
                                   if i.GetKind() == wx.ITEM_NORMAL]

        with mock.patch.object(pagina.lista, "PopupMenu", falso_popup):
            pagina._mostrar_menu()
        etiquetas = " ".join(vistos["etiquetas"]).replace("&", "")
        self.assertIn("Abrir archivo", etiquetas)
        self.assertNotIn("Reintentar", etiquetas)
        self.assertIn("Cancelar todas", etiquetas)
        self.assertIn("Eliminar completadas", etiquetas)
        pagina.lista.Select(pagina.lista.GetFirstSelected(), False)
        vistos.clear()
        with mock.patch.object(pagina.lista, "PopupMenu", falso_popup):
            pagina._mostrar_menu()
        self.assertEqual(len(vistos["etiquetas"]), 2)

    def test_menu_dispara_cada_comando(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        item = descargas.ItemDescarga("activa", "https://youtu.be/activa", "video",
                                      nombre="activa.mp4")
        dialogo._gestor._items[item.id] = item
        dialogo._gestor._orden.append(item.id)
        dialogo._gestor._eventos[item.id] = __import__("threading").Event()
        pagina.refrescar()
        pagina.lista.Select(0)
        nombres = ("abrir_archivo", "abrir_carpeta", "cancelar", "reintentar",
                   "volver_a_descargar", "copiar", "eliminar",
                   "cancelar_todas", "eliminar_completadas")
        for estado, esperados in (("descargando", {"cancelar", "copiar",
                                                   "cancelar_todas", "eliminar_completadas"}),
                                  ("completado", {"abrir_archivo", "abrir_carpeta",
                                                  "volver_a_descargar", "copiar", "eliminar",
                                                  "cancelar_todas", "eliminar_completadas"})):
            with self.subTest(estado=estado):
                if estado == "completado":
                    pagina.lista.Select(pagina.lista.GetFirstSelected(), False)
                    dialogo._gestor._items.pop("activa", None)
                    try:
                        dialogo._gestor._orden.remove("activa")
                    except ValueError:
                        pass
                    dialogo._gestor._eventos.pop("activa", None)
                    entrada = {"id": "hecha", "nombre": "hecha.mp4",
                               "fecha": "2026-10-30T08:33:00", "estado": "completado",
                               "url": "https://youtu.be/hecha",
                               "carpeta": "C:/D", "ruta": "C:/D/hecha.mp4"}
                    with mock.patch.object(descargas_listas.historial_descargas, "cargar",
                                           return_value=[entrada]):
                        pagina._historial = [entrada]
                        pagina.refrescar()
                    pagina.lista.Select(0)
                else:
                    item.estado = estado
                    pagina.refrescar()
                    pagina.lista.Select(0)
                espias = {n: mock.Mock() for n in nombres}
                with mock.patch.multiple(pagina, **{n: espias[n] for n in nombres}):
                    with mock.patch.object(pagina.lista, "PopupMenu") as popup:
                        def falso(menu):
                            for it in menu.GetMenuItems():
                                if it.GetKind() != wx.ITEM_NORMAL:
                                    continue
                                menu.ProcessEvent(wx.CommandEvent(wx.EVT_MENU.typeId,
                                                                  it.GetId()))
                        popup.side_effect = falso
                        pagina._mostrar_menu()
                for nombre in esperados:
                    self.assertTrue(espias[nombre].called, nombre)

    def test_intro_abre_y_supr_elimina(self):
        dialogo = self._dialogo([
            {"id": "hecha", "nombre": "hecha.mp4", "fecha": "2026-10-30T08:33:00",
             "estado": "completado", "url": "https://youtu.be/hecha",
             "carpeta": "C:/D", "ruta": "C:/D/hecha.mp4"}])
        pagina = dialogo.pagina_descargas
        pagina.refrescar()
        pagina.lista.Select(0)
        with mock.patch.object(pagina, "abrir_archivo") as abrir:
            pagina._on_activar(None)
            abrir.assert_called_once_with()

        class Evento:
            def GetKeyCode(self):
                return wx.WXK_DELETE

            def ShiftDown(self):
                return False

            def Skip(self):
                pass

        with mock.patch.object(pagina, "eliminar") as eliminar:
            pagina._on_key(Evento())
            eliminar.assert_called_once_with()

    def test_reintentar_deja_solo_la_nueva(self):
        import threading as _hilos
        entrada = {"id": "mala", "nombre": "mala.mp4", "fecha": "2026-10-30T08:33:00",
                   "estado": "error", "url": "https://youtu.be/mala",
                   "carpeta": "C:/D", "ruta": ""}
        disco = [dict(entrada)]
        with mock.patch("bellbird.downloads.historial_descargas.cargar",
                        side_effect=lambda _ruta: list(disco)), \
                mock.patch("bellbird.downloads.historial_descargas.guardar",
                           side_effect=lambda _ruta, entradas: disco.__setitem__(
                               slice(None), list(entradas))):
            dialogo = gui_descargas.GestorDescargasDialog(None)
            self.addCleanup(destruir, dialogo)
            self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
            self.addCleanup(descargas.reiniciar_gestor)
            pagina = dialogo.pagina_descargas
            item = descargas.ItemDescarga("mala", "https://youtu.be/mala", "video",
                                          nombre="mala.mp4")
            item.estado = "error"
            dialogo._gestor._items[item.id] = item
            dialogo._gestor._orden.append(item.id)
            dialogo._gestor._eventos[item.id] = _hilos.Event()
            pagina._historial = list(disco)
            pagina.refrescar()
            self.assertEqual([f.clave for f in pagina._filas], ["mala"])
            pagina.lista.Select(0)
            with mock.patch.object(pagina._acciones, "_preparar_opciones",
                                   lambda: None), \
                    mock.patch.object(dialogo._gestor, "encolar") as encolar, \
                    mock.patch.object(descargas_acciones, "anunciar"):
                pagina.reintentar()
                encolar.assert_called_once()
            self.assertNotIn("mala", [f.clave for f in pagina._filas])

    def test_archivo_faltante_avisa_y_sigue(self):
        dialogo = self._dialogo([
            {"id": "hecha", "nombre": "hecha.mp4", "fecha": "2026-10-30T08:33:00",
             "estado": "completado", "url": "https://youtu.be/hecha",
             "carpeta": "C:/D", "ruta": "C:/D/falta.mp4"}])
        pagina = dialogo.pagina_descargas
        pagina.refrescar()
        pagina.lista.Select(0)
        with mock.patch.object(descargas_acciones, "anunciar") as anunciar, \
                mock.patch.object(descargas_acciones._snd, "reproducir") as sonido, \
                mock.patch.object(descargas_acciones.os.path, "exists",
                                   return_value=False):
            pagina.abrir_archivo()
        anunciar.assert_called_once_with("El archivo ya no está disponible.")
        sonido.assert_called_once_with("error")
        self.assertEqual(pagina.lista.GetItemCount(), 1)

    def test_errores_van_sin_modal(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        with mock.patch.object(gui_descargas, "anunciar") as anunciar, \
                mock.patch.object(gui_descargas._snd, "reproducir") as sonido, \
                mock.patch.object(gui_descargas.wx, "MessageBox",
                                   side_effect=AssertionError("modal")):
            dialogo.txt_url.SetValue("")
            dialogo._on_anadir(None)
        anunciar.assert_called_once_with("Escribe un enlace antes de agregar.")
        sonido.assert_called_once_with("error")
        with mock.patch.object(descargas_acciones, "anunciar") as anunciar2, \
                mock.patch.object(descargas_acciones._snd, "reproducir") as sonido2:
            pagina._on_cancelar(None)
        anunciar2.assert_called_once_with("Selecciona una descarga.")
        sonido2.assert_called_once_with("error")

    def test_doble_refresco_conserva_seleccion_sin_reescribir(self):
        dialogo = self._dialogo([
            {"id": "a", "nombre": "a.mp4", "fecha": "2026-10-30T08:00:00",
             "estado": "completado", "url": "https://youtu.be/a",
             "carpeta": "", "ruta": ""},
            {"id": "b", "nombre": "b.mp4", "fecha": "2026-10-29T08:00:00",
             "estado": "completado", "url": "https://youtu.be/b",
             "carpeta": "", "ruta": ""}])
        pagina = dialogo.pagina_descargas
        pagina.refrescar()
        pagina.lista.Select(1)
        with mock.patch.object(pagina.lista, "SetItem",
                               wraps=pagina.lista.SetItem) as escribir, \
                mock.patch.object(pagina.lista, "Select") as seleccionar, \
                mock.patch.object(pagina.lista, "Focus") as enfocar, \
                mock.patch.object(descargas_listas.historial_descargas,
                                   "cargar") as cargar:
            pagina.refrescar()
            pagina.refrescar()
            escribir.assert_not_called()
            seleccionar.assert_not_called()
            enfocar.assert_not_called()
            cargar.assert_not_called()
        self.assertEqual(pagina.lista.GetFirstSelected(), 1)
        self.assertEqual(pagina._fila_elegida().clave, "b")

    def test_vaciar_sin_terminadas_avisa_sin_preguntar(self):
        dialogo = self._dialogo([])
        pagina = dialogo.pagina_descargas
        with mock.patch.object(descargas_acciones, "anunciar") as anunciar, \
                mock.patch.object(descargas_acciones._snd, "reproducir") as sonido, \
                mock.patch.object(descargas_acciones.wx, "MessageBox",
                                   side_effect=AssertionError("modal")):
            pagina._on_vaciar(None)
        anunciar.assert_called_once_with("No hay descargas terminadas")
        sonido.assert_called_once_with("error")

    def test_fila_quitada_deja_foco_en_su_lugar(self):
        dialogo = self._dialogo([
            {"id": "a", "nombre": "a.mp4", "fecha": "2026-10-30T08:00:00",
             "estado": "completado", "url": "https://youtu.be/a",
             "carpeta": "", "ruta": ""},
            {"id": "b", "nombre": "b.mp4", "fecha": "2026-10-29T08:00:00",
             "estado": "completado", "url": "https://youtu.be/b",
             "carpeta": "", "ruta": ""}])
        pagina = dialogo.pagina_descargas
        pagina.refrescar()
        pagina.lista.Select(0)
        pagina._historial = [e for e in pagina._historial if e.get("id") != "a"]
        pagina.refrescar()
        self.assertEqual(pagina.lista.GetFirstSelected(), 0)
        self.assertEqual(pagina.lista.GetFocusedItem(), 0)
        self.assertEqual(pagina._fila_elegida().clave, "b")

    def test_cancelar_un_item_terminado_no_cancela_y_avisa(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        with mock.patch.object(descargas_acciones, "anunciar") as anunciar, \
                mock.patch.object(descargas_acciones._snd, "reproducir") as sonido:
            item = descargas.ItemDescarga(
                "item", "https://youtu.be/abc", "video", nombre="video.mp4")
            dialogo._gestor._items[item.id] = item
            dialogo._gestor._orden.append(item.id)
            pagina.refrescar()
            pagina.lista.Select(0)
            for final in descargas_listas._ESTADOS_FINALES:
                with self.subTest(estado=final):
                    item.estado = final
                    pagina.refrescar()
                    pagina.lista.Select(0)
                    anunciar.reset_mock()
                    sonido.reset_mock()
                    with mock.patch.object(dialogo._gestor, "cancelar") as cancelar:
                        pagina._on_cancelar(None)
                    cancelar.assert_not_called()
                    anunciar.assert_called_once_with("La descarga ya terminó")
                    sonido.assert_called_once_with("error")

    def test_fin_avisado_despues_de_cerrar_el_dialogo(self):
        inicio = threading.Event()
        terminar = threading.Event()
        completada = threading.Event()

        def descarga_simulada(_url, _opciones, _progreso, estado, _cancelar,
                              _detalle=None):
            inicio.set()
            terminar.wait(1)
            estado("completado", "")
            completada.set()

        cargar = mock.patch.object(descargas_listas.historial_descargas, "cargar",
                                   return_value=[])
        guardar = mock.patch.object(descargas_listas.historial_descargas, "guardar")
        guardar_acc = mock.patch.object(descargas_acciones.historial_descargas, "guardar")
        with cargar, guardar, guardar_acc as guardar_mock, \
                mock.patch.object(descargas, "analizar_url", return_value={}), \
                mock.patch.object(descargas, "descargar", descarga_simulada), \
                mock.patch.object(gui_descargas, "anunciar") as anunciar, \
                mock.patch.object(gui_descargas._snd, "reproducir") as sonido:
            dialogo = gui_descargas.GestorDescargasDialog(None)
            dialogo._gestor.encolar("https://youtu.be/video", lambda *_: None,
                                    lambda *_: None)
            self.assertTrue(inicio.wait(1))
            destruir(dialogo)
            gui_descargas._dialogo_activo = None
            terminar.set()
            self.assertTrue(completada.wait(1))
            wx.Yield()

        anunciar.assert_called_once_with("Descarga completada")
        sonido.assert_called_once_with("descarga_completada")
        guardar_mock.assert_called_once()
        entradas = guardar_mock.call_args.args[1]
        self.assertEqual(entradas[0]["estado"], "completado")

    def test_avisar_fin_descarga_pasa_por_el_hilo_de_la_gui(self):
        with mock.patch.object(gui_descargas.wx, "CallAfter") as call_after, \
                mock.patch.object(gui_descargas, "anunciar") as anunciar:
            gui_descargas._avisar_fin_descarga("completado", "", "v.mp4", None)
        call_after.assert_called_once_with(
            gui_descargas._fin_descarga_en_gui, "completado", "", "v.mp4", None)
        anunciar.assert_not_called()

    def test_terminar_descarga_guarda_id_y_enlace_completo(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_descargas, "anunciar"), \
                mock.patch.object(gui_descargas._snd, "reproducir"):
            item = descargas.ItemDescarga(
                "item", "https://www.youtube.com/watch?v=abc&token=secreto",
                "video", nombre="video.mp4", carpeta="C:/Descargas")
            item.rutas = ["C:/Descargas/video.mp4"]
            with mock.patch.object(gui_descargas.historial_descargas,
                                    "guardar") as guardar:
                gui_descargas._fin_descarga_en_gui("completado", "", item.nombre, item)
            entradas = guardar.call_args.args[1]
            self.assertEqual(entradas[0]["id"], "item")
            self.assertEqual(entradas[0]["url"],
                             "https://www.youtube.com/watch?v=abc&token=secreto")

    def test_agregar_enlace_encola_y_refresca(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_descargas.cfg, "guardar_opciones_descarga"), \
                mock.patch.object(gui_descargas, "anunciar") as anunciar:
            url = "https://youtu.be/abc"

            def encolar_doble(enlace, _progreso, _estado, creado_cb=None):
                encolar_doble.enlace = enlace

            encolar_doble.enlace = None
            with mock.patch.object(dialogo._gestor, "encolar",
                                   side_effect=encolar_doble):
                dialogo.txt_url.SetValue(url)
                dialogo._on_anadir(None)
            self.assertEqual(encolar_doble.enlace, url)
            self.assertEqual(dialogo.txt_url.GetValue(), "")
            anunciar.assert_called_once_with("Agregado a la cola")


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
                 ("parcial", "1 de 2 vídeos", "descarga_fallida"),
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
        cargar = mock.patch.object(descargas_listas.historial_descargas, "cargar", return_value=[])
        guardar = mock.patch.object(descargas_listas.historial_descargas, "guardar")
        guardar_acc = mock.patch.object(descargas_acciones.historial_descargas, "guardar")
        with cargar, guardar, guardar_acc, con_pseudo():
            dialogo = gui_descargas.GestorDescargasDialog(None)
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
        cargar = mock.patch.object(descargas_listas.historial_descargas, "cargar", return_value=[])
        guardar = mock.patch.object(descargas_listas.historial_descargas, "guardar")
        guardar_acc = mock.patch.object(descargas_acciones.historial_descargas, "guardar")
        cargar.start()
        guardar.start()
        guardar_acc.start()
        self.addCleanup(cargar.stop)
        self.addCleanup(guardar.stop)
        self.addCleanup(guardar_acc.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def test_avisos_y_cuadros_propios_salen_marcados(self):
        dialogo = self._dialogo()
        with con_pseudo(), mock.patch.object(gui_descargas, "anunciar") as anunciar, \
                mock.patch.object(gui_descargas._snd, "reproducir"):
            dialogo.txt_url.SetValue("")
            dialogo._on_anadir(None)
        self.assertTrue(anunciar.call_args.args[0].startswith("[¡"))
        with con_pseudo(), mock.patch.object(descargas_acciones, "anunciar") as anunciar2, \
                mock.patch.object(descargas_acciones._snd, "reproducir"):
            dialogo.pagina_descargas._on_cancelar(None)
        self.assertTrue(anunciar2.call_args.args[0].startswith("[¡"))


if __name__ == "__main__":
    unittest.main()

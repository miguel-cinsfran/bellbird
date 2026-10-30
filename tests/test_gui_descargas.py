"""Pruebas de accesibilidad del selector y de la página única de descargas."""

import tempfile
import unittest
import threading
from pathlib import Path
from unittest import mock

from bellbird.downloads import descargas
from bellbird.downloads import busqueda_youtube
from bellbird.downloads import filas_descargas
from bellbird.ui import barra_progreso, descargas_acciones, descargas_buscador, descargas_listas, gui_descargas
from bellbird.ui import tema as _tema
from bellbird.ui import buscador_acciones, buscador_escucha
from bellbird.ui.buscador_acciones import AccionesResultado, opciones_de
from bellbird.ui import buscador_contenido
from bellbird.ui import buscador_tandas
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class TestOpcionesDeResultado(unittest.TestCase):
    # Sin ventana: opciones_de es pura, solo mira el Resultado.

    def _res(self, tipo="video", directo=False, programado=False):
        return busqueda_youtube.Resultado(
            id="a", url="https://www.youtube.com/watch?v=a",
            titulo="Título a", canal="Canal a", duracion=60, vistas=10,
            marca_tiempo=1700000000, descripcion="", tipo=tipo,
            en_directo=directo, programado=programado)

    def test_tabla(self):
        video = self._res()
        casos = [
            ((video, True, True),
             ("agregar", "escuchar", "audio", "video", "bellbird", "musica",
              "copiar", "navegador", "sitios")),
            ((video, False, False),
             ("agregar", "escuchar", "audio", "video", "copiar", "navegador",
              "sitios")),
            ((self._res(directo=True), True, True),
             ("bellbird", "musica", "copiar", "navegador", "sitios")),
            ((self._res(directo=True), False, False),
             ("copiar", "navegador", "sitios")),
            ((self._res(programado=True), True, True),
             ("copiar", "navegador", "sitios")),
            ((self._res(tipo="lista"), True, True),
             ("contenido", "agregar", "musica", "copiar", "navegador",
              "sitios")),
            ((self._res(tipo="lista"), False, False),
             ("contenido", "agregar", "copiar", "navegador", "sitios")),
            ((self._res(tipo="canal"), True, True),
             ("contenido", "copiar", "navegador", "sitios")),
            (([video, self._res()], True, True),
             ("agregar", "audio", "video", "sitios")),
            (([video, self._res(tipo="lista")], False, False),
             ("agregar", "audio", "video", "sitios")),
            (([video, self._res(tipo="canal")], True, True),
             ("sitios",)),
            (([video, self._res(directo=True)], True, True),
             ("sitios",)),
        ]
        for (entrada, hay_bellbird, hay_musica), esperado in casos:
            with self.subTest(entrada=entrada, hay_musica=hay_musica):
                self.assertEqual(
                    opciones_de(entrada, hay_bellbird, hay_musica), esperado)


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
        with tempfile.TemporaryDirectory() as tmp:
            ruta = str(Path(tmp) / "historial.json")
            al_cambiar = mock.Mock()
            acciones = descargas_acciones.AccionesDescarga(
                gestor, ruta, lambda: None, al_cambiar)
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
                mock.patch.object(descargas_acciones.historial_descargas, "guardar"),
                mock.patch.object(descargas_buscador.busquedas_recientes, "cargar",
                                  return_value=[]),
                mock.patch.object(descargas_buscador.busquedas_recientes, "guardar"))

    def _dialogo(self, entradas=None):
        parches = self._sin_disco(entradas)
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def test_dos_pestanas_buscador_y_descargas_con_columnas(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.pestanas.GetPageCount(), 2)
        self.assertEqual(dialogo.pestanas.GetPageText(0), "Buscar en YouTube")
        self.assertEqual(dialogo.pestanas.GetPageText(1), "Descargas")
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
        pagina = dialogo.pagina_buscador
        with mock.patch.object(descargas_buscador, "anunciar") as anunciar, \
                mock.patch.object(buscador_tandas._snd, "reproducir") as sonido, \
                mock.patch.object(descargas_buscador.wx, "MessageBox",
                                   side_effect=AssertionError("modal")):
            pagina.campo.SetValue("")
            pagina._on_buscar(None)
        anunciar.assert_called_once_with("Escribe una búsqueda o un enlace.")
        sonido.assert_called_once_with("error")
        with mock.patch.object(descargas_acciones, "anunciar") as anunciar2, \
                mock.patch.object(descargas_acciones._snd, "reproducir") as sonido2:
            dialogo.pagina_descargas._on_cancelar(None)
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

    def test_agregar_urls_encola_y_avisa(self):
        dialogo = self._dialogo()
        with mock.patch.object(gui_descargas.cfg, "guardar_opciones_descarga"), \
                mock.patch.object(dialogo._gestor, "encolar") as encolar, \
                mock.patch.object(buscador_acciones, "anunciar") as anunciar:
            agregados = dialogo.agregar_urls(["https://youtu.be/abc"])
        encolar.assert_called_once()
        self.assertEqual(encolar.call_args.args[0], "https://youtu.be/abc")
        self.assertEqual(agregados, 1)
        anunciar.assert_called_once_with("Descargando")

    def test_agregar_urls_sin_turno_anuncia_en_cola(self):
        from bellbird.downloads.opciones_formato import SIMULTANEAS_DEFECTO
        dialogo = self._dialogo()
        dialogo._gestor._corriendo = dialogo._gestor._opciones.get(
            "simultaneas", SIMULTANEAS_DEFECTO)
        with mock.patch.object(gui_descargas.cfg, "guardar_opciones_descarga"), \
                mock.patch.object(dialogo._gestor, "encolar"), \
                mock.patch.object(buscador_acciones, "anunciar") as anunciar:
            agregados = dialogo.agregar_urls(
                ["https://youtu.be/abc"], titulo="Mi vídeo")
        self.assertEqual(agregados, 1)
        anunciar.assert_called_once_with("En cola: Mi vídeo")

    def test_cambiar_formato_llena_calidad_y_deshabilita(self):
        dialogo = self._dialogo()
        dialogo.cho_formato.SetSelection(7)
        dialogo._on_formato()
        self.assertFalse(dialogo.cho_calidad.IsEnabled())
        self.assertEqual(dialogo.cho_calidad.GetCount(), 0)
        dialogo.cho_formato.SetSelection(4)
        dialogo._on_formato()
        self.assertTrue(dialogo.cho_calidad.IsEnabled())
        self.assertEqual(
            [dialogo.cho_calidad.GetString(i)
             for i in range(dialogo.cho_calidad.GetCount())],
            ["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        dialogo.cho_formato.SetSelection(1)
        dialogo._on_formato()
        self.assertTrue(dialogo.cho_calidad.IsEnabled())
        self.assertEqual(
            [dialogo.cho_calidad.GetString(i)
             for i in range(dialogo.cho_calidad.GetCount())],
            ["Máxima", "2160p", "1440p", "1080p", "720p", "480p", "360p"])

    def test_volver_a_video_recupera_resolucion(self):
        dialogo = self._dialogo()
        dialogo.cho_formato.SetSelection(1)
        dialogo._on_formato()
        dialogo.cho_calidad.SetSelection(4)
        dialogo.cho_formato.SetSelection(4)
        dialogo._on_formato()
        dialogo.cho_calidad.SetSelection(2)
        dialogo.cho_formato.SetSelection(1)
        dialogo._on_formato()
        self.assertEqual(dialogo.cho_calidad.GetStringSelection(), "720p")
        op = dialogo._opciones_actuales()
        self.assertEqual(
            (op["formato"], op["resolucion"], op["bitrate"]),
            ("mp4", 720, 256))
        for clave in ("formato", "bitrate", "resolucion", "carpeta",
                      "enumerar"):
            self.assertIn(clave, op)

    def test_sin_carpeta_ni_enumerar(self):
        dialogo = self._dialogo()
        self.assertFalse(hasattr(dialogo, "dir_carpeta"))
        self.assertFalse(hasattr(dialogo, "chk_enumerar"))

    def test_opciones_actuales_toma_la_carpeta_guardada(self):
        dialogo = self._dialogo()
        guardadas = {"formato": "mp3", "bitrate": 192, "resolucion": 0,
                     "carpeta": "/guardada", "enumerar": True,
                     "simultaneas": 5, "limite": 3, "carpeta_lista": True,
                     "plantilla": "titulo"}
        with mock.patch.object(gui_descargas.cfg, "obtener_opciones_descarga",
                               return_value=dict(guardadas)):
            dialogo.cho_formato.SetSelection(4)
            dialogo._on_formato()
            op = dialogo._opciones_actuales()
        self.assertEqual(op["carpeta"], "/guardada")
        self.assertTrue(op["enumerar"])
        self.assertEqual(op["simultaneas"], 5)
        self.assertEqual(op["formato"], "mp3")


def _resultado_busqueda(id, tipo="video", directo=False, programado=False):
    return busqueda_youtube.Resultado(
        id=id, url=f"https://www.youtube.com/watch?v={id}",
        titulo=f"Título {id}", canal=f"Canal {id}", duracion=60, vistas=10,
        marca_tiempo=1700000000, descripcion=f"Descripción {id}",
        tipo=tipo, en_directo=directo, programado=programado)


def _respuesta_busqueda(items, error="", hay_mas=False):
    return busqueda_youtube.RespuestaBusqueda(list(items), error, hay_mas)


class _CorreYa:
    """Hilo que corre en el acto, para pruebas sin esperas."""

    def __init__(self, destino, argumentos):
        self._destino = destino
        self._argumentos = argumentos

    def start(self):
        self._destino(*self._argumentos)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestBuscador(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        gui_descargas._registrados.clear()

    def tearDown(self):
        descargas.reiniciar_gestor()
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None

    def _dialogo(self, entradas=None, url_inicial=None, abrir_en_bellbird=None,
                 musica=None):
        parches = list(TestPaginaUnica._sin_disco(self, entradas))
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        dialogo = gui_descargas.GestorDescargasDialog(
            None, url_inicial=url_inicial, abrir_en_bellbird=abrir_en_bellbird,
            musica=musica)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def _con_busqueda(self, respuesta):
        busco = mock.patch.object(
            descargas_buscador.busqueda_youtube, "buscar",
            return_value=respuesta)
        buscado = busco.start()
        self.addCleanup(busco.stop)
        hilo = mock.patch.object(
            buscador_tandas.diagnostico, "crear_hilo",
            side_effect=lambda destino, nombre, args=(), **kw:
            _CorreYa(destino, args))
        hilo.start()
        self.addCleanup(hilo.stop)
        entrega = mock.patch.object(
            descargas_buscador.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kw: funcion(*args, **kw))
        entrega.start()
        self.addCleanup(entrega.stop)
        anunciar = mock.patch.object(descargas_buscador, "anunciar")
        anunciar.start()
        self.addCleanup(anunciar.stop)
        anunciar_tanda = mock.patch.object(buscador_tandas, "anunciar")
        anunciar_tanda.start()
        self.addCleanup(anunciar_tanda.stop)
        sonido = mock.patch.object(buscador_tandas._snd, "reproducir")
        sonido.start()
        self.addCleanup(sonido.stop)
        return buscado

    def _dichos(self):
        return [llamada.args[0]
                for llamada in descargas_buscador.anunciar.call_args_list] + \
               [llamada.args[0]
                for llamada in buscador_tandas.anunciar.call_args_list]

    def test_dos_pestanas_con_buscador_primero(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.pestanas.GetPageCount(), 2)
        self.assertEqual(dialogo.pestanas.GetPageText(0), "Buscar en YouTube")
        self.assertEqual(dialogo.pestanas.GetPageText(1), "Descargas")
        self.assertIsInstance(dialogo.pagina_buscador,
                              descargas_buscador.PaginaBuscador)
        self.assertEqual(tuple(dialogo.GetSize()), (940, 700))

    def test_construir_no_busca_y_deja_todo_en_reposo(self):
        buscar = self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        buscar.assert_not_called()
        self.assertEqual(pagina.campo.GetValue(), "")
        self.assertEqual(pagina.campo.GetCount(), 0)
        self.assertFalse(pagina.filtros.chk_filtros.GetValue())
        self.assertFalse(pagina.filtros.cho_tipo.IsShown())
        self.assertEqual(pagina.cho_cantidad.GetStringSelection(), "20")
        self.assertEqual(pagina.lista.GetItemCount(), 0)
        self.assertFalse(pagina.btn_mas.IsEnabled())
        self.assertEqual(
            [pagina.lista.GetColumn(i).GetText()
             for i in range(pagina.lista.GetColumnCount())],
            ["Título", "Canal", "Duración", "Vistas", "Fecha"])
        self.assertEqual(pagina.lista.GetName(), "Resultados de la búsqueda")

    def test_palabras_buscan_y_muestran(self):
        buscar = self._con_busqueda(_respuesta_busqueda(
            [_resultado_busqueda("a"), _resultado_busqueda("b")], hay_mas=True))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.assert_called_once_with(
            "cumbia", busqueda_youtube.Filtros(), 1, 20)
        self.assertEqual(pagina.lista.GetItemCount(), 2)
        self.assertEqual(pagina.lista.GetItemText(0, 0), "Título a")
        self.assertEqual(pagina.lista.GetItemText(1, 1), "Canal b")
        self.assertEqual(pagina.lista.GetFirstSelected(), 0)
        dichos = self._dichos()
        self.assertIn("Buscando", dichos)
        self.assertIn("2 resultados", dichos)
        self.assertTrue(pagina.btn_mas.IsEnabled())

    def test_enlace_encola_sin_buscar(self):
        buscar = self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        url = "https://www.youtube.com/watch?v=abc"
        with mock.patch.object(pagina, "_agregar_urls",
                                return_value=1) as agregar:
            pagina.campo.SetValue(url)
            pagina._on_buscar(None)
        buscar.assert_not_called()
        agregar.assert_called_once_with([url])
        self.assertEqual(pagina.campo.GetValue(), "")

    def test_campo_vacio_avisa_sin_buscar(self):
        buscar = self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("   ")
        pagina._on_buscar(None)
        buscar.assert_not_called()
        self.assertIn("Escribe una búsqueda o un enlace.", self._dichos())
        buscador_tandas._snd.reproducir.assert_called_once_with("error")

    def test_enter_en_campo_busca(self):
        buscar = self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        evento = wx.CommandEvent(wx.EVT_TEXT_ENTER.typeId,
                                 pagina.campo.GetId())
        pagina.campo.GetEventHandler().ProcessEvent(evento)
        buscar.assert_called_once()

    def test_generacion_vieja_se_descarta(self):
        primera = _respuesta_busqueda([_resultado_busqueda("viejo")])
        segunda = _respuesta_busqueda([_resultado_busqueda("nuevo")])
        buscar = self._con_busqueda(primera)
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("a")
        pagina._on_buscar(None)
        buscar.return_value = segunda
        pagina.campo.SetValue("b")
        pagina._on_buscar(None)
        self.assertEqual(buscar.call_count, 2)
        pagina._al_volver(1, primera, False)
        self.assertEqual(pagina.lista.GetItemCount(), 1)
        self.assertEqual(pagina.lista.GetItemText(0, 0), "Título nuevo")

    def test_foco_solo_si_esta_en_campo(self):
        self._con_busqueda(_respuesta_busqueda([_resultado_busqueda("a")]))
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetFocus()
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(wx.Window.FindFocus(), pagina.lista)
        pagina.cho_cantidad.SetFocus()
        pagina.campo.SetValue("polca")
        pagina._on_buscar(None)
        self.assertEqual(wx.Window.FindFocus(), pagina.cho_cantidad)
        dialogo.Hide()

    def test_mostrar_mas_agrega_sin_repetir(self):
        primera = _respuesta_busqueda(
            [_resultado_busqueda("a"), _resultado_busqueda("b")], hay_mas=True)
        segunda = _respuesta_busqueda(
            [_resultado_busqueda("b"), _resultado_busqueda("c")], hay_mas=False)
        buscar = self._con_busqueda(primera)
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.return_value = segunda
        pagina._on_mas(None)
        self.assertEqual(buscar.call_count, 2)
        self.assertEqual(buscar.call_args.args,
                         ("cumbia", busqueda_youtube.Filtros(), 21, 20))
        self.assertEqual(pagina.lista.GetItemCount(), 3)
        self.assertEqual(pagina.lista.GetItemText(2, 0), "Título c")
        self.assertEqual(pagina.lista.GetFirstSelected(), 2)
        self.assertIn("1 resultado más", self._dichos())
        self.assertFalse(pagina.btn_mas.IsEnabled())

    def test_mostrar_mas_sin_nada_nuevo(self):
        primera = _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True)
        segunda = _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True)
        buscar = self._con_busqueda(primera)
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.return_value = segunda
        pagina.btn_mas.SetFocus()
        pagina._on_mas(None)
        self.assertIn("No hay más resultados", self._dichos())
        self.assertEqual(wx.Window.FindFocus(), pagina.lista)
        dialogo.Hide()

    def test_sin_resultados(self):
        self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("zzz sin nada")
        pagina._on_buscar(None)
        self.assertEqual(pagina.lista.GetItemCount(), 0)
        self.assertEqual(pagina.txt_detalles.GetValue(), "Sin resultados")
        self.assertIn("Sin resultados", self._dichos())
        self.assertFalse(pagina.btn_mas.IsEnabled())

    def test_error_muestra_texto_y_suena(self):
        self._con_busqueda(_respuesta_busqueda([], error="Falla la red"))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(pagina.txt_detalles.GetValue(), "Falla la red")
        self.assertIn("Falla la red", self._dichos())
        buscador_tandas._snd.reproducir.assert_called_with("busqueda_fallida")
        self.assertFalse(pagina.btn_mas.IsEnabled())

    def _sonidos(self):
        return [llamada.args[0]
                for llamada in
                buscador_tandas._snd.reproducir.call_args_list]

    def test_buscar_suena_iniciada_y_resultados(self):
        self._con_busqueda(_respuesta_busqueda(
            [_resultado_busqueda("a"), _resultado_busqueda("b")]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(
            self._sonidos(), ["busqueda_iniciada", "busqueda_resultados"])

    def test_mostrar_mas_suena_resultados_sin_repetir_iniciada(self):
        primera = _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True)
        segunda = _respuesta_busqueda([_resultado_busqueda("b")])
        buscar = self._con_busqueda(primera)
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.return_value = segunda
        pagina._on_mas(None)
        self.assertEqual(
            self._sonidos(),
            ["busqueda_iniciada", "busqueda_resultados",
             "busqueda_resultados"])

    def test_sin_resultados_suena(self):
        self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("zzz sin nada")
        pagina._on_buscar(None)
        self.assertEqual(
            self._sonidos(),
            ["busqueda_iniciada", "busqueda_sin_resultados"])

    def test_mas_sin_nada_nuevo_suena_sin_resultados(self):
        primera = _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True)
        segunda = _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True)
        buscar = self._con_busqueda(primera)
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.return_value = segunda
        pagina._on_mas(None)
        self.assertEqual(
            self._sonidos(),
            ["busqueda_iniciada", "busqueda_resultados",
             "busqueda_sin_resultados"])

    def test_cambiar_orden_no_busca_y_conserva_seleccion(self):
        items = [
            busqueda_youtube.Resultado(
                id="a", url="https://www.youtube.com/watch?v=a",
                titulo="Título a", canal="Canal a", duracion=30, vistas=5,
                marca_tiempo=1699000000, descripcion="", tipo="video",
                en_directo=False, programado=False),
            busqueda_youtube.Resultado(
                id="b", url="https://www.youtube.com/watch?v=b",
                titulo="Título b", canal="Canal b", duracion=10, vistas=9,
                marca_tiempo=1699900000, descripcion="", tipo="video",
                en_directo=False, programado=False),
            busqueda_youtube.Resultado(
                id="c", url="https://www.youtube.com/watch?v=c",
                titulo="Título c", canal="Canal c", duracion=20, vistas=7,
                marca_tiempo=1698000000, descripcion="", tipo="video",
                en_directo=False, programado=False)]
        buscar = self._con_busqueda(_respuesta_busqueda(items))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        pagina.lista.Select(pagina.lista.GetFirstSelected(), False)
        pagina.lista.Select(2)
        pagina.filtros.cho_orden.SetSelection(2)
        pagina._on_orden(None)
        buscar.assert_called_once()
        self.assertEqual(
            [pagina.lista.GetItemText(i, 0) for i in range(3)],
            ["Título b", "Título c", "Título a"])
        self.assertEqual(pagina.lista.GetFirstSelected(), 1)

    def test_sin_marcar_los_desplegables_no_se_usan(self):
        buscar = self._con_busqueda(_respuesta_busqueda([]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.filtros.cho_tipo.SetSelection(1)
        pagina.filtros.cho_duracion.SetSelection(2)
        pagina.filtros.cho_fecha.SetSelection(3)
        pagina.filtros.cho_orden.SetSelection(1)
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(buscar.call_args.args[1], busqueda_youtube.Filtros())
        pagina.filtros.chk_filtros.SetValue(True)
        pagina.campo.SetValue("polca")
        pagina._on_buscar(None)
        self.assertEqual(
            buscar.call_args.args[1],
            busqueda_youtube.Filtros(tipo="listas", duracion="media",
                                    fecha="mes", orden="fecha"))

    def test_cantidad_opciones_y_tanda(self):
        buscar = self._con_busqueda(
            _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        self.assertEqual(
            [pagina.cho_cantidad.GetString(i)
             for i in range(pagina.cho_cantidad.GetCount())],
            ["10", "20", "30", "50"])
        pagina.cho_cantidad.SetSelection(3)
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(buscar.call_args.args[1:], (busqueda_youtube.Filtros(),
                                                     1, 50))

    def test_filtros_se_muestran_y_ocultan(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        self.assertFalse(pagina.filtros.cho_tipo.IsShown())
        pagina.filtros.chk_filtros.SetValue(True)
        pagina._on_filtros(None)
        self.assertTrue(pagina.filtros.cho_tipo.IsShown())
        self.assertTrue(pagina.filtros.cho_orden.IsShown())
        pagina.filtros.chk_filtros.SetValue(False)
        pagina._on_filtros(None)
        self.assertFalse(pagina.filtros.cho_tipo.IsShown())

    def test_elegir_fila_muestra_detalles_sin_anunciar(self):
        self._con_busqueda(_respuesta_busqueda(
            [_resultado_busqueda("a"), _resultado_busqueda("b")]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        descargas_buscador.anunciar.reset_mock()
        pagina.lista.Select(pagina.lista.GetFirstSelected(), False)
        pagina.lista.Select(1)
        pagina._on_elegir(None)
        self.assertIn("Título b", pagina.txt_detalles.GetValue())
        descargas_buscador.anunciar.assert_not_called()

    def test_agregar_varios_rechaza_canal_y_directo(self):
        lista = busqueda_youtube.Resultado(
            id="l", url="https://www.youtube.com/playlist?list=PL1",
            titulo="Título l", canal="Canal l", duracion=None, vistas=None,
            marca_tiempo=None, descripcion="", tipo="lista",
            en_directo=False, programado=False)
        items = [_resultado_busqueda("v"), lista,
                 _resultado_busqueda("c", tipo="canal"),
                 _resultado_busqueda("d", directo=True)]
        self._con_busqueda(_respuesta_busqueda(items))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        for i in range(4):
            pagina.lista.Select(i)
        buscador_tandas._snd.reproducir.reset_mock()
        with mock.patch.object(pagina, "_agregar_urls",
                                return_value=2) as agregar:
            pagina._on_agregar(None)
        agregar.assert_called_once_with(
            ["https://www.youtube.com/watch?v=v",
             "https://www.youtube.com/playlist?list=PL1"], titulo=None)
        dichos = self._dichos()
        self.assertIn("Un canal no se puede agregar a la cola.", dichos)
        self.assertIn("Un directo en curso no se puede descargar.", dichos)
        self.assertEqual(
            buscador_tandas._snd.reproducir.call_count, 2)

    def test_agregar_programado_se_rechaza(self):
        self._con_busqueda(_respuesta_busqueda(
            [_resultado_busqueda("p", programado=True)]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        pagina.lista.Select(0)
        buscador_tandas._snd.reproducir.reset_mock()
        with mock.patch.object(pagina, "_agregar_urls") as agregar:
            pagina._on_agregar(None)
        agregar.assert_not_called()
        self.assertIn("Este directo todavía no empezó.", self._dichos())
        buscador_tandas._snd.reproducir.assert_called_once_with("error")

    def test_agregar_sin_seleccion_avisa(self):
        self._con_busqueda(_respuesta_busqueda([_resultado_busqueda("a")]))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        pagina.lista.Select(pagina.lista.GetFirstSelected(), False)
        buscador_tandas._snd.reproducir.reset_mock()
        with mock.patch.object(pagina, "_agregar_urls") as agregar:
            pagina._on_agregar(None)
        agregar.assert_not_called()
        self.assertIn("Selecciona un resultado.", self._dichos())
        buscador_tandas._snd.reproducir.assert_called_once_with("error")

    def test_orden_se_aplica_al_llegar(self):
        items = [
            busqueda_youtube.Resultado(
                id="a", url="https://www.youtube.com/watch?v=a",
                titulo="Título a", canal="Canal a", duracion=30, vistas=5,
                marca_tiempo=1699000000, descripcion="", tipo="video",
                en_directo=False, programado=False),
            busqueda_youtube.Resultado(
                id="b", url="https://www.youtube.com/watch?v=b",
                titulo="Título b", canal="Canal b", duracion=10, vistas=9,
                marca_tiempo=1699900000, descripcion="", tipo="video",
                en_directo=False, programado=False),
            busqueda_youtube.Resultado(
                id="c", url="https://www.youtube.com/watch?v=c",
                titulo="Título c", canal="Canal c", duracion=20, vistas=7,
                marca_tiempo=1698000000, descripcion="", tipo="video",
                en_directo=False, programado=False)]
        self._con_busqueda(_respuesta_busqueda(items))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.filtros.chk_filtros.SetValue(True)
        pagina.filtros.cho_orden.SetSelection(2)
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(
            [pagina.lista.GetItemText(i, 0) for i in range(3)],
            ["Título b", "Título c", "Título a"])

    def test_mostrar_mas_reordena_y_sigue_nueva(self):
        def _item(id, vistas):
            return busqueda_youtube.Resultado(
                id=id, url=f"https://www.youtube.com/watch?v={id}",
                titulo=f"Título {id}", canal="Canal", duracion=10,
                vistas=vistas, marca_tiempo=1699000000, descripcion="",
                tipo="video", en_directo=False, programado=False)
        buscar = self._con_busqueda(
            _respuesta_busqueda([_item("a", 5), _item("b", 9)], hay_mas=True))
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.filtros.chk_filtros.SetValue(True)
        pagina.filtros.cho_orden.SetSelection(2)
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.return_value = _respuesta_busqueda([_item("c", 7)])
        pagina._on_mas(None)
        self.assertEqual(
            [pagina.lista.GetItemText(i, 0) for i in range(3)],
            ["Título b", "Título c", "Título a"])
        self.assertEqual(
            pagina.lista.GetItemText(pagina.lista.GetFirstSelected(), 0),
            "Título c")

    def test_llegar_con_foco_en_mas_pasa_a_lista(self):
        buscar = self._con_busqueda(_respuesta_busqueda(
            [_resultado_busqueda("a")], hay_mas=True))
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        buscar.return_value = _respuesta_busqueda([_resultado_busqueda("b")])
        pagina.btn_mas.SetFocus()
        pagina._on_mas(None)
        self.assertEqual(wx.Window.FindFocus(), pagina.lista)
        self.assertEqual(pagina.lista.GetFirstSelected(), 1)
        dialogo.Hide()

    def test_error_en_mas_mantiene_tanda_y_boton(self):
        primera = _respuesta_busqueda([_resultado_busqueda("a")], hay_mas=True)
        buscar = self._con_busqueda(primera)
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        self.assertEqual(pagina._inicio, 21)
        buscar.return_value = _respuesta_busqueda([], error="Falla la red")
        pagina.btn_mas.SetFocus()
        pagina._on_mas(None)
        self.assertEqual(pagina.lista.GetItemCount(), 1)
        self.assertTrue(pagina.btn_mas.IsEnabled())
        self.assertEqual(pagina._inicio, 21)
        self.assertEqual(wx.Window.FindFocus(), pagina.lista)
        pagina._on_mas(None)
        self.assertEqual(buscar.call_args.args[2], 21)
        dialogo.Hide()

    def test_url_inicial_deja_texto_sin_encolar(self):
        self._con_busqueda(_respuesta_busqueda([]))
        with mock.patch.object(
                gui_descargas.GestorDescargasDialog, "agregar_urls") as agregar:
            dialogo = self._dialogo(url_inicial="https://youtu.be/inicial")
        self.assertEqual(dialogo.pagina_buscador.campo.GetValue(),
                         "https://youtu.be/inicial")
        agregar.assert_not_called()

    def test_volver_tras_cerrar_no_revienta(self):
        respuesta = _respuesta_busqueda([_resultado_busqueda("a")])
        self._con_busqueda(respuesta)
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue("cumbia")
        pagina._on_buscar(None)
        generacion = pagina._generacion
        destruir(dialogo)
        pagina._al_volver(generacion, respuesta, False)

    def test_recientes_se_guardan_y_recuperan(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "recientes.json"
            self._con_busqueda(_respuesta_busqueda([]))
            marco = wx.Frame(None)
            self.addCleanup(destruir, marco)
            agregar = mock.Mock()
            primera = descargas_buscador.PaginaBuscador(marco, agregar, ruta)
            self.addCleanup(destruir, primera)
            primera.campo.SetValue("Cumbia")
            primera._on_buscar(None)
            agregar.assert_not_called()
            segunda = descargas_buscador.PaginaBuscador(marco, agregar, ruta)
            self.addCleanup(destruir, segunda)
            self.assertIn("Cumbia", segunda.campo.GetStrings())


def _resultado_lista(id="l"):
    return busqueda_youtube.Resultado(
        id=id, url=f"https://www.youtube.com/playlist?list={id.upper()}",
        titulo=f"Título {id}", canal=f"Canal {id}", duracion=None,
        vistas=None, marca_tiempo=None, descripcion=f"Descripción {id}",
        tipo="lista", en_directo=False, programado=False)


def _resultado_canal(id="c"):
    return busqueda_youtube.Resultado(
        id=id, url=f"https://www.youtube.com/channel/{id.upper()}",
        titulo=f"Título {id}", canal=f"Canal {id}", duracion=None,
        vistas=None, marca_tiempo=None, descripcion=f"Descripción {id}",
        tipo="canal", en_directo=False, programado=False)


def _respuesta_contenido(ids=("a", "b"), titulo="Una lista", total=2):
    return busqueda_youtube.RespuestaBusqueda(
        [_resultado_busqueda(i) for i in ids], "", False, titulo, total)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestMenuYVistaBuscador(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        gui_descargas._registrados.clear()

    def tearDown(self):
        descargas.reiniciar_gestor()
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None

    def _dialogo(self, entradas=None, abrir_en_bellbird=None, musica=None):
        parches = list(TestPaginaUnica._sin_disco(self, entradas))
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        dialogo = gui_descargas.GestorDescargasDialog(
            None, abrir_en_bellbird=abrir_en_bellbird, musica=musica)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def _buscar(self, items):
        busco = mock.patch.object(
            descargas_buscador.busqueda_youtube, "buscar",
            return_value=_respuesta_busqueda(items))
        busco.start()
        self.addCleanup(busco.stop)
        hilo = mock.patch.object(
            buscador_tandas.diagnostico, "crear_hilo",
            side_effect=lambda destino, nombre, args=(), **kw:
            _CorreYa(destino, args))
        hilo.start()
        self.addCleanup(hilo.stop)
        entrega = mock.patch.object(
            descargas_buscador.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kw: funcion(*args, **kw))
        entrega.start()
        self.addCleanup(entrega.stop)
        anunciar = mock.patch.object(descargas_buscador, "anunciar")
        anunciar.start()
        self.addCleanup(anunciar.stop)
        anunciar_tanda = mock.patch.object(buscador_tandas, "anunciar")
        anunciar_tanda.start()
        self.addCleanup(anunciar_tanda.stop)
        sonido = mock.patch.object(buscador_tandas._snd, "reproducir")
        sonido.start()
        self.addCleanup(sonido.stop)

    def _pagina_buscada(self, dialogo, items, texto="cumbia"):
        pagina = dialogo.pagina_buscador
        pagina.campo.SetValue(texto)
        pagina._on_buscar(None)
        return pagina

    def _seleccionar_solo(self, pagina, indice):
        actual = pagina.lista.GetFirstSelected()
        while actual != -1:
            pagina.lista.Select(actual, False)
            actual = pagina.lista.GetFirstSelected()
        pagina.lista.Select(indice)

    def _menu_disparado(self, pagina):
        etiquetas = []

        def falso_popup(menu):
            for it in menu.GetMenuItems():
                if it.GetKind() != wx.ITEM_NORMAL:
                    continue
                etiquetas.append(it.GetItemLabel())
                menu.ProcessEvent(
                    wx.CommandEvent(wx.EVT_MENU.typeId, it.GetId()))

        with mock.patch.object(pagina.lista, "PopupMenu", falso_popup):
            pagina._mostrar_menu()
        return etiquetas

    def test_menu_dispara_cada_comando(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo(abrir_en_bellbird=mock.Mock(),
                                musica=mock.Mock())
        dialogo.Show()
        pagina = self._pagina_buscada(dialogo, items)
        espias = {n: mock.Mock() for n in (
            "como_audio", "como_video", "en_bellbird", "a_musica", "copiar",
            "abrir_en_navegador", "ver_sitios")}
        with mock.patch.multiple(pagina._acciones, **espias), \
                mock.patch.object(pagina, "_agregar_urls",
                                  return_value=1) as agregar, \
                mock.patch.object(pagina._escucha, "alternar"), \
                mock.patch.object(buscador_contenido, "contenido",
                                  return_value=_respuesta_busqueda([])), \
                mock.patch.object(buscador_contenido, "anunciar"):
            self._seleccionar_solo(pagina, 0)
            etiquetas = self._menu_disparado(pagina)
        juntos = " ".join(etiquetas).replace("&", "")
        for texto in ("Agregar a la cola", "Escuchar", "Descargar como audio",
                      "Descargar como vídeo", "Abrir en Bellbird",
                      "Agregar a la música", "Copiar enlace",
                      "Abrir en el navegador", "Ver sitios compatibles"):
            self.assertIn(texto, juntos)
        self.assertNotIn("Ver contenido", juntos)
        agregar.assert_called_once_with(["https://www.youtube.com/watch?v=v"],
                                        titulo="Título v")
        resultado = pagina._resultados[0]
        espias["como_audio"].assert_called_once_with([resultado])
        espias["como_video"].assert_called_once_with([resultado])
        espias["en_bellbird"].assert_called_once_with(resultado)
        espias["a_musica"].assert_called_once_with(resultado)
        espias["copiar"].assert_called_once_with(resultado)
        espias["abrir_en_navegador"].assert_called_once_with(resultado)
        espias["ver_sitios"].assert_called_once_with()
        dialogo.Hide()

    def test_menu_de_lista_entra_a_la_vista(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo(abrir_en_bellbird=mock.Mock(),
                                musica=mock.Mock())
        dialogo.Show()
        pagina = self._pagina_buscada(dialogo, items)
        espias = {n: mock.Mock() for n in (
            "como_audio", "como_video", "a_musica", "copiar",
            "abrir_en_navegador", "ver_sitios")}
        with mock.patch.multiple(pagina._acciones, **espias), \
                mock.patch.object(pagina, "_agregar_urls",
                                  return_value=1) as agregar, \
                mock.patch.object(pagina._escucha, "alternar"), \
                mock.patch.object(buscador_contenido, "contenido",
                                  return_value=_respuesta_contenido()), \
                mock.patch.object(buscador_contenido, "anunciar"):
            self._seleccionar_solo(pagina, 1)
            esperada = pagina._resultados[1]
            self._menu_disparado(pagina)
        self.assertTrue(pagina._vista.activa)
        agregar.assert_called_once_with(
            ["https://www.youtube.com/playlist?list=L"], titulo=None)
        espias["a_musica"].assert_called_once_with(esperada)
        dialogo.Hide()

    def test_menu_varios_solo_agrega_si_todos_bajan(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        pagina = self._pagina_buscada(dialogo, items)
        with mock.patch.object(pagina, "_agregar_urls",
                               return_value=2) as agregar, \
                mock.patch.object(buscador_acciones.webbrowser, "open"), \
                mock.patch.object(pagina._acciones,
                                  "como_audio") as como_audio, \
                mock.patch.object(pagina._acciones,
                                  "como_video") as como_video, \
                mock.patch.object(pagina._acciones,
                                  "ver_sitios") as ver_sitios:
            pagina.lista.Select(0)
            pagina.lista.Select(1)
            etiquetas = self._menu_disparado(pagina)
        self.assertEqual(
            [e.replace("&", "") for e in etiquetas],
            ["Agregar a la cola", "Descargar como audio",
             "Descargar como vídeo", "Ver sitios compatibles"])
        agregar.assert_called_once_with(
            ["https://www.youtube.com/watch?v=v",
             "https://www.youtube.com/playlist?list=L"], titulo=None)
        ambos = [pagina._resultados[0], pagina._resultados[1]]
        como_audio.assert_called_once_with(ambos)
        como_video.assert_called_once_with(ambos)
        ver_sitios.assert_called_once_with()

    def test_intro_en_lista_entra_retroceso_vuelve_y_recupera(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = self._pagina_buscada(dialogo, items)
        with mock.patch.object(buscador_contenido, "contenido",
                               return_value=_respuesta_contenido()), \
                mock.patch.object(buscador_contenido,
                                  "anunciar") as anunciar_vista, \
                mock.patch.object(pagina, "_agregar_urls", return_value=1):
            self._seleccionar_solo(pagina, 1)
            pagina._on_activar(None)
        self.assertTrue(pagina._vista.activa)
        self.assertEqual(pagina.lista.GetItemCount(), 2)
        self.assertEqual(pagina.lista.GetItemText(0, 0), "Título a")
        self.assertEqual(wx.Window.FindFocus(), pagina.lista)
        self.assertEqual(pagina.lista.GetFirstSelected(), 0)
        self.assertTrue(pagina.btn_volver.IsShown())
        self.assertTrue(pagina.btn_todo.IsShown())
        dichos = [llamada.args[0]
                  for llamada in anunciar_vista.call_args_list]
        self.assertIn("Una lista: 2 vídeos", dichos)
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_BACK
        pagina._on_key(evento)
        self.assertFalse(pagina._vista.activa)
        self.assertEqual(pagina.lista.GetItemCount(), 2)
        self.assertEqual(pagina.lista.GetItemText(1, 0), "Título l")
        self.assertEqual(pagina.lista.GetFirstSelected(), 1)
        self.assertEqual(wx.Window.FindFocus(), pagina.lista)
        self.assertFalse(pagina.btn_volver.IsShown())
        self.assertFalse(pagina.btn_todo.IsShown())
        dialogo.Hide()

    def test_contenido_sin_total_anuncia_solo_el_titulo(self):
        items = [_resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = self._pagina_buscada(dialogo, items)
        respuesta = busqueda_youtube.RespuestaBusqueda(
            [_resultado_busqueda("a")], "", False, "YouTube - Videos", 0)
        with mock.patch.object(buscador_contenido, "contenido",
                               return_value=respuesta), \
                mock.patch.object(buscador_contenido,
                                  "anunciar") as anunciar_vista, \
                mock.patch.object(pagina, "_agregar_urls", return_value=1):
            self._seleccionar_solo(pagina, 0)
            pagina._on_activar(None)
        dichos = [llamada.args[0]
                  for llamada in anunciar_vista.call_args_list]
        self.assertIn("YouTube - Videos", dichos)
        for dicho in dichos:
            self.assertNotIn("0 vídeos", dicho)
        dialogo.Hide()

    def _sonidos(self, sonido):
        return [llamada.args[0] for llamada in sonido.call_args_list]

    def test_vista_suena_iniciada_y_resultados(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        with mock.patch.object(buscador_tandas._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_contenido, "anunciar"):
            pagina = self._pagina_buscada(dialogo, items)
            with mock.patch.object(buscador_contenido, "contenido",
                                    return_value=_respuesta_contenido()):
                self._seleccionar_solo(pagina, 1)
                pagina._on_activar(None)
        self.assertEqual(
            self._sonidos(sonido),
            ["busqueda_iniciada", "busqueda_resultados",
             "busqueda_iniciada", "busqueda_resultados"])

    def test_vista_con_error_suena_fallida(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        with mock.patch.object(buscador_tandas._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_contenido, "anunciar"):
            pagina = self._pagina_buscada(dialogo, items)
            with mock.patch.object(
                    buscador_contenido, "contenido",
                    return_value=_respuesta_busqueda(
                        [], error="Falla la red")):
                self._seleccionar_solo(pagina, 1)
                pagina._on_activar(None)
        self.assertEqual(
            self._sonidos(sonido),
            ["busqueda_iniciada", "busqueda_resultados",
             "busqueda_iniciada", "busqueda_fallida"])

    def test_vista_vacia_anuncia_sin_resultados(self):
        items = [_resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        vacia = busqueda_youtube.RespuestaBusqueda(
            [], "", False, "Una lista", 0)
        with mock.patch.object(buscador_tandas._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_contenido, "contenido",
                                   return_value=vacia), \
                mock.patch.object(buscador_contenido,
                                   "anunciar") as anunciar_vista:
            pagina = self._pagina_buscada(dialogo, items)
            self._seleccionar_solo(pagina, 0)
            pagina._on_activar(None)
        dichos = [llamada.args[0]
                  for llamada in anunciar_vista.call_args_list]
        self.assertIn("Sin resultados", dichos)
        for dicho in dichos:
            self.assertNotIn("0 vídeos", dicho)
        self.assertEqual(
            self._sonidos(sonido)[-2:],
            ["busqueda_iniciada", "busqueda_sin_resultados"])

    def test_volver_con_boton_recupera_la_lista(self):
        items = [_resultado_busqueda("v"), _resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = self._pagina_buscada(dialogo, items)
        with mock.patch.object(buscador_contenido, "contenido",
                               return_value=_respuesta_contenido()), \
                mock.patch.object(buscador_contenido, "anunciar"),                 mock.patch.object(pagina, "_agregar_urls", return_value=1):
            self._seleccionar_solo(pagina, 1)
            pagina._on_activar(None)
        self.assertTrue(pagina._vista.activa)
        pagina.btn_volver.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, pagina.btn_volver.GetId()))
        self.assertFalse(pagina._vista.activa)
        self.assertEqual(pagina.lista.GetItemCount(), 2)
        self.assertEqual(pagina.lista.GetFirstSelected(), 1)
        dialogo.Hide()

    def test_agregar_sobre_lista_agrega_entera(self):
        items = [_resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        pagina = self._pagina_buscada(dialogo, items)
        pagina.lista.Select(0)
        with mock.patch.object(pagina, "_agregar_urls",
                               return_value=1) as agregar:
            pagina._on_agregar(None)
        agregar.assert_called_once_with(
            ["https://www.youtube.com/playlist?list=L"], titulo=None)

    def test_pegar_lista_entra_sin_encolar(self):
        self._buscar([])
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        with mock.patch.object(pagina, "_agregar_urls") as agregar, \
                mock.patch.object(buscador_contenido, "contenido",
                                  return_value=_respuesta_contenido()), \
                mock.patch.object(buscador_contenido, "anunciar"):
            pagina.campo.SetValue("https://www.youtube.com/playlist?list=PL1")
            pagina._on_buscar(None)
        agregar.assert_not_called()
        self.assertTrue(pagina._vista.activa)
        self.assertFalse(pagina.btn_volver.IsShown())
        self.assertTrue(pagina.btn_todo.IsShown())

    def test_pegar_video_encola_sin_entrar(self):
        self._buscar([])
        dialogo = self._dialogo()
        pagina = dialogo.pagina_buscador
        with mock.patch.object(pagina, "_agregar_urls",
                               return_value=1) as agregar:
            pagina.campo.SetValue("https://www.youtube.com/watch?v=abc")
            pagina._on_buscar(None)
        agregar.assert_called_once_with(["https://www.youtube.com/watch?v=abc"])
        self.assertFalse(pagina._vista.activa)

    def test_boton_todo_encola_la_lista(self):
        items = [_resultado_lista()]
        self._buscar(items)
        dialogo = self._dialogo()
        dialogo.Show()
        pagina = self._pagina_buscada(dialogo, items)
        with mock.patch.object(buscador_contenido, "contenido",
                               return_value=_respuesta_contenido()), \
                mock.patch.object(buscador_contenido, "anunciar"), \
                mock.patch.object(pagina, "_agregar_urls", return_value=1):
            self._seleccionar_solo(pagina, 0)
            pagina._on_activar(None)
        with mock.patch.object(gui_descargas.cfg,
                               "guardar_opciones_descarga"), \
                mock.patch.object(dialogo._gestor, "encolar") as encolar, \
                mock.patch.object(buscador_acciones, "anunciar"):
            pagina.btn_todo.GetEventHandler().ProcessEvent(
                wx.CommandEvent(wx.EVT_BUTTON.typeId, pagina.btn_todo.GetId()))
        encolar.assert_called_once()
        self.assertEqual(encolar.call_args.args[0],
                         "https://www.youtube.com/playlist?list=L")
        dialogo.Hide()

    def test_menu_con_tecla_y_con_texto(self):
        items = [_resultado_busqueda("v")]
        self._buscar(items)
        dialogo = self._dialogo()
        pagina = self._pagina_buscada(dialogo, items)
        pagina.lista.Select(0)
        with mock.patch.object(pagina, "_mostrar_menu") as mostrar:
            evento = mock.Mock()
            evento.GetKeyCode.return_value = wx.WXK_WINDOWS_MENU
            pagina._on_key(evento)
            mostrar.assert_called_once_with()
        with mock.patch.object(pagina, "_mostrar_menu") as mostrar:
            evento = mock.Mock()
            evento.GetKeyCode.return_value = wx.WXK_F10
            evento.ShiftDown.return_value = True
            pagina._on_key(evento)
            mostrar.assert_called_once_with()
        with mock.patch.object(pagina.lista, "PopupMenu"):
            pagina._on_context_menu(None)

    def test_agregar_urls_con_no_solo_los_nuevos(self):
        vieja1 = "https://www.youtube.com/watch?v=una"
        vieja2 = "https://www.youtube.com/watch?v=dos"
        nueva = "https://www.youtube.com/watch?v=nueva"
        entradas = [
            {"id": "una", "nombre": "una.mp4",
             "fecha": "2026-10-29T08:00:00", "estado": "completado",
             "url": vieja1, "carpeta": "", "ruta": ""},
            {"id": "dos", "nombre": "dos.mp4",
             "fecha": "2026-10-29T08:00:00", "estado": "completado",
             "url": vieja2, "carpeta": "", "ruta": ""},
        ]
        dialogo = self._dialogo(entradas)
        with mock.patch.object(gui_descargas.cfg,
                               "guardar_opciones_descarga"), \
                mock.patch.object(dialogo._gestor, "encolar") as encolar, \
                mock.patch.object(gui_descargas.wx, "MessageBox",
                                  return_value=wx.NO) as caja, \
                mock.patch.object(gui_descargas, "anunciar"):
            agregados = dialogo.agregar_urls([vieja1, vieja2, nueva])
        self.assertEqual(
            caja.call_args.args[0],
            "2 ya están en el historial. ¿Agregar de todos modos?")
        encolar.assert_called_once()
        self.assertEqual(encolar.call_args.args[0], nueva)
        self.assertEqual(agregados, 1)

    def test_agregar_urls_formato_audio_encola_y_restaura(self):
        dialogo = self._dialogo()
        fijas = {"formato": "mp4", "bitrate": 192, "resolucion": 0,
                 "carpeta": "/tmp", "enumerar": False}
        formato_visto = dialogo.cho_formato.GetSelection()
        with mock.patch.object(gui_descargas.cfg,
                               "guardar_opciones_descarga"), \
                mock.patch.object(dialogo, "_opciones_actuales",
                                  return_value=dict(fijas)), \
                mock.patch.object(dialogo._gestor, "encolar") as encolar, \
                mock.patch.object(gui_descargas, "anunciar"):
            vistos = []
            original = dialogo._gestor.set_opciones

            def espiar(op):
                vistos.append(dict(op).get("formato"))
                return original(op)

            with mock.patch.object(dialogo._gestor, "set_opciones",
                                   side_effect=espiar):
                agregados = dialogo.agregar_urls(
                    ["https://youtu.be/abc"], formato="audio")
        self.assertEqual(agregados, 1)
        encolar.assert_called_once()
        self.assertEqual(vistos, ["audio_original", "mp4"])
        self.assertEqual(dialogo._gestor._opciones["formato"], "mp4")
        self.assertEqual(dialogo.cho_formato.GetSelection(), formato_visto)

    def test_abrir_en_bellbird_cierra_antes_de_llamar(self):
        callback = mock.Mock()
        dialogo = self._dialogo(abrir_en_bellbird=callback)
        with mock.patch.object(gui_descargas.wx, "CallAfter") as call_after:
            dialogo._al_abrir_en_bellbird("https://youtu.be/x")
        self.assertFalse(dialogo._alive)
        callback.assert_not_called()
        call_after.assert_called_once_with(callback, "https://youtu.be/x")


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestEscuchaPrevia(TestMenuYVistaBuscador):
    """Espacio escucha la previa: pausa la música y la reanuda al terminar."""

    def _musica(self, pausa=True):
        musica = mock.Mock()
        musica.pausar_para_escuchar.return_value = pausa
        musica.ajustes_escucha.return_value = (None, 50)
        return musica

    def _espias_escucha(self):
        parche_anunciar = mock.patch.object(buscador_escucha, "anunciar")
        anunciar = parche_anunciar.start()
        self.addCleanup(parche_anunciar.stop)
        parche_sonido = mock.patch.object(buscador_escucha._snd, "reproducir")
        sonido = parche_sonido.start()
        self.addCleanup(parche_sonido.stop)
        return anunciar, sonido

    def _con_interna_falsa(self):
        fabrica = mock.patch.object(buscador_escucha, "Escucha")
        falsa = fabrica.start()
        self.addCleanup(fabrica.stop)
        interna = mock.Mock()
        interna.url = None
        falsa.return_value = interna
        return interna

    def _evento_espacio(self, ctrl=False, mayus=False, alt=False):
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_SPACE
        evento.ControlDown.return_value = ctrl
        evento.ShiftDown.return_value = mayus
        evento.AltDown.return_value = alt
        return evento

    def _pagina_buscada_con_musica(self, items, musica=None):
        self._buscar(items)
        dialogo = self._dialogo(musica=musica if musica is not None else self._musica())
        return dialogo, self._pagina_buscada(dialogo, items)

    def test_pausa_al_empezar_y_reanuda_en_fin(self):
        musica = self._musica()
        buscador = buscador_escucha.EscuchaBuscador(musica)
        interna = mock.Mock()
        interna.url = None
        with mock.patch.object(buscador_escucha, "Escucha",
                               return_value=interna):
            buscador.alternar(_resultado_busqueda("v"))
        musica.pausar_para_escuchar.assert_called_once_with()
        interna.alternar.assert_called_once_with(
            "https://www.youtube.com/watch?v=v")
        buscador._al_avisar("fin")
        musica.reanudar_tras_escuchar.assert_called_once_with()

    def test_reanuda_en_fallo_y_en_detener(self):
        musica = self._musica()
        buscador = buscador_escucha.EscuchaBuscador(musica)
        interna = mock.Mock()
        interna.url = "https://www.youtube.com/watch?v=v"
        buscador._escucha = interna
        buscador._pauso = True
        anunciar, sonido = self._espias_escucha()
        buscador._al_avisar("fallo", "se cortó")
        anunciar.assert_called_once_with("se cortó")
        sonido.assert_called_once_with("escucha_fallida")
        musica.reanudar_tras_escuchar.assert_called_once_with()
        buscador._pauso = True
        buscador.detener()
        interna.detener.assert_called_once_with()
        self.assertEqual(musica.reanudar_tras_escuchar.call_count, 2)

    def test_no_reanuda_si_no_pauso(self):
        musica = self._musica(pausa=False)
        buscador = buscador_escucha.EscuchaBuscador(musica)
        interna = mock.Mock()
        interna.url = None
        with mock.patch.object(buscador_escucha, "Escucha",
                               return_value=interna):
            buscador.alternar(_resultado_busqueda("v"))
        buscador._al_avisar("fin")
        musica.reanudar_tras_escuchar.assert_not_called()
        buscador.detener()
        musica.reanudar_tras_escuchar.assert_not_called()

    def test_pasar_de_uno_a_otro_no_reanuda_en_medio(self):
        musica = self._musica()
        buscador = buscador_escucha.EscuchaBuscador(musica)
        interna = mock.Mock()
        interna.url = None
        with mock.patch.object(buscador_escucha, "Escucha",
                               return_value=interna):
            buscador.alternar(_resultado_busqueda("a"))
            interna.url = "https://www.youtube.com/watch?v=a"
            buscador.alternar(_resultado_busqueda("b"))
        self.assertEqual(musica.pausar_para_escuchar.call_count, 1)
        interna.alternar.assert_called_with(
            "https://www.youtube.com/watch?v=b")
        musica.reanudar_tras_escuchar.assert_not_called()

    def test_canal_directo_y_programado_no_se_escuchan(self):
        casos = [_resultado_canal(),
                 _resultado_busqueda("d", directo=True),
                 _resultado_busqueda("p", programado=True)]
        for resultado in casos:
            with self.subTest(tipo=resultado.tipo, directo=resultado.en_directo,
                              programado=resultado.programado):
                musica = self._musica()
                buscador = buscador_escucha.EscuchaBuscador(musica)
                anunciar, sonido = self._espias_escucha()
                with mock.patch.object(buscador_escucha, "Escucha") as fabrica:
                    buscador.alternar(resultado)
                fabrica.assert_not_called()
                musica.pausar_para_escuchar.assert_not_called()
                anunciar.assert_called_once_with(
                    "Este resultado no se puede escuchar.")
                sonido.assert_called_once_with("error")

    def test_avisos_de_carga_pausa_y_reproduccion(self):
        musica = self._musica()
        buscador = buscador_escucha.EscuchaBuscador(musica)
        anunciar, sonido = self._espias_escucha()
        buscador._al_avisar("cargando")
        sonido.assert_called_once_with("escucha_cargando")
        anunciar.assert_called_once_with("Cargando vista previa de audio")
        anunciar.reset_mock()
        sonido.reset_mock()
        buscador._al_avisar("pausa")
        anunciar.assert_called_once_with("En pausa")
        sonido.assert_not_called()
        anunciar.reset_mock()
        buscador._al_avisar("reanudada")
        anunciar.assert_called_once_with("Reproduciendo")
        sonido.assert_not_called()
        anunciar.reset_mock()
        buscador._al_avisar("sonando")
        anunciar.assert_not_called()

    def test_aviso_con_pagina_destruida_se_ignora(self):
        musica = self._musica()
        buscador = buscador_escucha.EscuchaBuscador(musica)
        anunciar, sonido = self._espias_escucha()
        buscador.invalidar()
        buscador._al_avisar("cargando")
        anunciar.assert_not_called()
        sonido.assert_not_called()

    def test_espacio_llama_a_alternar_sin_cambiar_seleccion(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a"), _resultado_busqueda("b")])
        self._con_interna_falsa()
        pagina.lista.Focus(1)
        antes = pagina.lista.GetFirstSelected()
        evento = self._evento_espacio()
        with mock.patch.object(pagina._escucha, "alternar") as alternar:
            pagina._on_key(evento)
        alternar.assert_called_once_with(pagina._resultados[1])
        self.assertEqual(pagina.lista.GetFirstSelected(), antes)
        evento.Skip.assert_not_called()

    def test_espacio_con_ctrl_no_escucha(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a")])
        self._con_interna_falsa()
        evento = self._evento_espacio(ctrl=True)
        with mock.patch.object(pagina._escucha, "alternar") as alternar:
            pagina._on_key(evento)
        alternar.assert_not_called()
        evento.Skip.assert_called_once_with()

    def test_espacio_sin_fila_avisa(self):
        dialogo, pagina = self._pagina_buscada_con_musica([])
        self._con_interna_falsa()
        anunciar, sonido = self._espias_escucha()
        pagina._on_key(self._evento_espacio())
        anunciar.assert_called_once_with("Selecciona un resultado.")
        sonido.assert_called_once_with("error")

    def test_mover_seleccion_detiene(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a"), _resultado_busqueda("b")])
        interna = self._con_interna_falsa()
        interna.url = "https://www.youtube.com/watch?v=a"
        pagina._escucha._escucha = interna
        pagina.lista.Focus(1)
        pagina._on_elegir(None)
        interna.detener.assert_called_once_with()

    def test_busqueda_nueva_detiene(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a")])
        interna = self._con_interna_falsa()
        interna.url = "https://www.youtube.com/watch?v=a"
        pagina._escucha._escucha = interna
        pagina.campo.SetValue("otra")
        pagina._on_buscar(None)
        interna.detener.assert_called_once_with()

    def test_cambio_de_pestana_detiene(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a")])
        interna = self._con_interna_falsa()
        interna.url = "https://www.youtube.com/watch?v=a"
        pagina._escucha._escucha = interna
        dialogo.Show()
        dialogo.pestanas.SetSelection(1)
        interna.detener.assert_called_once_with()
        dialogo.Hide()

    def test_cerrar_dialogo_detiene_y_reanuda(self):
        musica = self._musica()
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a")], musica=musica)
        interna = self._con_interna_falsa()
        interna.url = "https://www.youtube.com/watch?v=a"
        pagina._escucha._escucha = interna
        pagina._escucha._pauso = True
        dialogo._on_cerrar(None)
        interna.detener.assert_called_once_with()
        musica.reanudar_tras_escuchar.assert_called_once_with()

    def test_tab_a_detalles_no_detiene(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("a")])
        interna = self._con_interna_falsa()
        interna.url = "https://www.youtube.com/watch?v=a"
        pagina._escucha._escucha = interna
        pagina.txt_detalles.SetFocus()
        interna.detener.assert_not_called()

    def test_menu_llega_a_alternar(self):
        dialogo, pagina = self._pagina_buscada_con_musica(
            [_resultado_busqueda("v")])
        self._seleccionar_solo(pagina, 0)
        resultado = pagina._resultados[0]
        opciones = buscador_acciones.opciones_de(resultado, False, True)
        self.assertIn("escuchar", opciones)
        al_escuchar = mock.Mock()
        menu = buscador_acciones.construir_menu(
            opciones, [resultado], pagina._acciones, mock.Mock(),
            mock.Mock(), al_escuchar)
        try:
            for it in menu.GetMenuItems():
                if it.GetItemLabel().replace("&", "") == "Escuchar":
                    menu.ProcessEvent(wx.CommandEvent(
                        wx.EVT_MENU.typeId, it.GetId()))
        finally:
            menu.Destroy()
        al_escuchar.assert_called_once_with(resultado)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestLetrasMenuBuscador(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def _casos(self):
        video = _resultado_busqueda("v")
        return [
            ([video], True, True),
            ([video], False, False),
            ([_resultado_busqueda("d", directo=True)], True, True),
            ([_resultado_busqueda("p", programado=True)], False, False),
            ([_resultado_lista()], True, True),
            ([_resultado_canal()], False, False),
            ([video, _resultado_lista()], True, True),
            ([video, _resultado_canal()], False, False),
        ]

    def test_letras_del_menu_no_se_repiten(self):
        from tests.letras_acceso import _letra_de_acceso
        acciones = mock.Mock()
        for resultados, hay_bellbird, hay_musica in self._casos():
            opciones = opciones_de(resultados[0] if len(resultados) == 1
                                   else resultados, hay_bellbird, hay_musica)
            with self.subTest(opciones=opciones):
                menu = buscador_acciones.construir_menu(
                    opciones, resultados, acciones, mock.Mock(), mock.Mock())
                try:
                    letras = {}
                    for it in menu.GetMenuItems():
                        if it.GetKind() != wx.ITEM_NORMAL:
                            continue
                        letra = _letra_de_acceso(it.GetItemLabel())
                        self.assertIsNotNone(letra, it.GetItemLabel())
                        self.assertNotIn(letra, letras, it.GetItemLabel())
                        letras[letra] = it.GetItemLabel()
                finally:
                    menu.Destroy()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestLetrasMenuBuscadorEnIngles(TestLetrasMenuBuscador):
    # Gemela en inglés: repite la prueba sin copiarla.

    @classmethod
    def setUpClass(cls):
        from tests.letras_acceso import ingles
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestSonidosDeDescarga(unittest.TestCase):
    """Cada aviso del gestor suena con su sonido propio. Sin ventanas."""

    def setUp(self):
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None
        gui_descargas._finales_seguidos = 0
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
        gui_descargas._finales_seguidos = 0

    def _item(self):
        self._n += 1
        return descargas.ItemDescarga(
            f"item-{self._n}", "https://www.youtube.com/watch?v=abc",
            "video", nombre="video.mp4", carpeta="C:/Descargas")

    def test_cada_fin_suena_con_su_sonido(self):
        casos = [("completado", "", "descarga_completada"),
                 ("parcial", "1 de 2 vídeos", "descarga_parcial"),
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

    def test_procesando_suena_sin_anunciar_ni_registrar(self):
        item = self._item()
        antes = gui_descargas._finales_seguidos
        with mock.patch.object(gui_descargas, "anunciar") as anunciar:
            gui_descargas._fin_descarga_en_gui(
                "procesando", "", item.nombre, item)
        self._sonido.assert_called_once_with("descarga_procesando")
        anunciar.assert_not_called()
        self.assertNotIn(item.id, gui_descargas._registrados)
        self.assertEqual(gui_descargas._finales_seguidos, antes)


class TestAnunciarAgregados(unittest.TestCase):
    """Cada agregado a la cola suena con su sonido propio. Sin ventanas."""

    def test_texto_uno_con_turno_y_titulo(self):
        self.assertEqual(
            buscador_acciones.texto_agregados(1, "Mi vídeo", True),
            "Descargando: Mi vídeo")

    def test_texto_uno_sin_turno_y_titulo(self):
        self.assertEqual(
            buscador_acciones.texto_agregados(1, "Mi vídeo", False),
            "En cola: Mi vídeo")

    def test_texto_uno_sin_titulo(self):
        self.assertEqual(
            buscador_acciones.texto_agregados(1, None, True), "Descargando")
        self.assertEqual(
            buscador_acciones.texto_agregados(1, None, False), "En cola")

    def test_texto_varios(self):
        self.assertEqual(
            buscador_acciones.texto_agregados(3, None, True),
            "3 descargas agregadas")

    def test_sin_entradas_no_suena_ni_anuncia(self):
        with mock.patch.object(buscador_acciones._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_acciones,
                                   "anunciar") as anunciar:
            buscador_acciones.anunciar_agregados(0)
        sonido.assert_not_called()
        anunciar.assert_not_called()

    def test_uno_suena_encolada(self):
        with mock.patch.object(buscador_acciones._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_acciones,
                                   "anunciar") as anunciar:
            buscador_acciones.anunciar_agregados(1, "Mi vídeo", True)
        anunciar.assert_called_once_with("Descargando: Mi vídeo")
        sonido.assert_called_once_with("descarga_encolada")

    def test_uno_sin_turno_suena_encolada(self):
        with mock.patch.object(buscador_acciones._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_acciones,
                                   "anunciar") as anunciar:
            buscador_acciones.anunciar_agregados(1, "Mi vídeo", False)
        anunciar.assert_called_once_with("En cola: Mi vídeo")
        sonido.assert_called_once_with("descarga_encolada")

    def test_varios_suenan_encolada(self):
        with mock.patch.object(buscador_acciones._snd,
                               "reproducir") as sonido, \
                mock.patch.object(buscador_acciones,
                                   "anunciar") as anunciar:
            buscador_acciones.anunciar_agregados(3)
        anunciar.assert_called_once_with("3 descargas agregadas")
        sonido.assert_called_once_with("descarga_encolada")


class TestFinDeCola(unittest.TestCase):
    """El fin de la cola suena y se anuncia una sola vez. Sin ventanas."""

    def setUp(self):
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None
        gui_descargas._finales_seguidos = 0
        self._n = 0
        for parche in (
                mock.patch.object(gui_descargas.historial_descargas,
                                   "cargar", return_value=[]),
                mock.patch.object(gui_descargas.historial_descargas,
                                   "guardar")):
            parche.start()
            self.addCleanup(parche.stop)
        parche_sonido = mock.patch.object(gui_descargas._snd, "reproducir")
        self._sonido = parche_sonido.start()
        self.addCleanup(parche_sonido.stop)
        parche_anunciar = mock.patch.object(gui_descargas, "anunciar")
        self._anunciar = parche_anunciar.start()
        self.addCleanup(parche_anunciar.stop)

    def tearDown(self):
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None
        gui_descargas._finales_seguidos = 0

    def _item(self, nombre, estado="descargando"):
        self._n += 1
        return descargas.ItemDescarga(
            f"cola-{self._n}",
            f"https://www.youtube.com/watch?v=cola{self._n}",
            "video", estado=estado, nombre=nombre, carpeta="C:/Descargas")

    def _con_cola(self, items):
        parche = mock.patch.object(gui_descargas, "gestor")
        gestor_mock = parche.start()
        self.addCleanup(parche.stop)
        gestor_mock.return_value.lista.return_value = items

    def test_cola_de_dos_con_ultimo_completado_suena_cola_y_anuncia_una_vez(
            self):
        primero = self._item("uno.mp4", estado="completado")
        segundo = self._item("dos.mp4", estado="descargando")
        self._con_cola([primero, segundo])
        gui_descargas._fin_descarga_en_gui(
            "completado", "", primero.nombre, primero)
        self._sonido.assert_called_once_with("descarga_completada")
        self._anunciar.assert_called_once_with(
            "Descarga completada: uno.mp4")
        self._sonido.reset_mock()
        self._anunciar.reset_mock()
        segundo.estado = "completado"
        gui_descargas._fin_descarga_en_gui(
            "completado", "", segundo.nombre, segundo)
        self._sonido.assert_called_once_with("cola_descargas_terminada")
        self._anunciar.assert_called_once_with(
            "Descarga completada: dos.mp4. Cola de descargas terminada")
        self.assertEqual(gui_descargas._finales_seguidos, 0)

    def test_cola_de_dos_con_error_final_suena_fallo_y_anuncia_cola(self):
        primero = self._item("uno.mp4", estado="completado")
        segundo = self._item("dos.mp4", estado="descargando")
        self._con_cola([primero, segundo])
        gui_descargas._fin_descarga_en_gui(
            "completado", "", primero.nombre, primero)
        segundo.estado = "error"
        self._sonido.reset_mock()
        self._anunciar.reset_mock()
        gui_descargas._fin_descarga_en_gui(
            "error", "sin espacio", segundo.nombre, segundo)
        self._sonido.assert_called_once_with("descarga_fallida")
        self._anunciar.assert_called_once_with(
            "Error en la descarga: sin espacio. Cola de descargas terminada")
        self.assertEqual(gui_descargas._finales_seguidos, 0)

    def test_una_sola_descarga_no_nombra_la_cola(self):
        unico = self._item("uno.mp4", estado="completado")
        self._con_cola([unico])
        gui_descargas._fin_descarga_en_gui(
            "completado", "", unico.nombre, unico)
        self._sonido.assert_called_once_with("descarga_completada")
        self._anunciar.assert_called_once_with(
            "Descarga completada: uno.mp4")

    def test_dos_descargas_separadas_no_nombran_la_cola(self):
        for nombre in ("uno.mp4", "dos.mp4"):
            unico = self._item(nombre, estado="completado")
            self._con_cola([unico])
            self._sonido.reset_mock()
            self._anunciar.reset_mock()
            gui_descargas._fin_descarga_en_gui(
                "completado", "", unico.nombre, unico)
            with self.subTest(descarga=nombre):
                self._sonido.assert_called_once_with("descarga_completada")
                self._anunciar.assert_called_once_with(
                    f"Descarga completada: {nombre}")
        self.assertEqual(gui_descargas._finales_seguidos, 0)

    def test_dos_colas_seguidas_suenan_cola_cada_vez(self):
        for nombres in (("uno.mp4", "dos.mp4"), ("tres.mp4", "cuatro.mp4")):
            primero = self._item(nombres[0], estado="completado")
            segundo = self._item(nombres[1], estado="descargando")
            self._con_cola([primero, segundo])
            gui_descargas._fin_descarga_en_gui(
                "completado", "", primero.nombre, primero)
            segundo.estado = "completado"
            self._sonido.reset_mock()
            self._anunciar.reset_mock()
            gui_descargas._fin_descarga_en_gui(
                "completado", "", segundo.nombre, segundo)
            with self.subTest(cola=nombres):
                self._sonido.assert_called_once_with(
                    "cola_descargas_terminada")
                self.assertIn(
                    "Cola de descargas terminada",
                    self._anunciar.call_args.args[0])
        self.assertEqual(gui_descargas._finales_seguidos, 0)
        solo = self._item("sola.mp4", estado="completado")
        self._con_cola([solo])
        self._sonido.reset_mock()
        self._anunciar.reset_mock()
        gui_descargas._fin_descarga_en_gui(
            "completado", "", solo.nombre, solo)
        self._sonido.assert_called_once_with("descarga_completada")
        self._anunciar.assert_called_once_with(
            "Descarga completada: sola.mp4")


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestBarraProgresoEnLista(unittest.TestCase):
    """La columna Progreso dibuja la barra junto al texto, sin cambiarlo."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        gui_descargas._registrados.clear()

    def tearDown(self):
        descargas.reiniciar_gestor()
        gui_descargas._registrados.clear()
        gui_descargas._dialogo_activo = None

    def _dialogo(self, entradas=None, activos=()):
        parches = list(TestPaginaUnica._sin_disco(self, entradas))
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        for item in activos:
            dialogo._gestor._items[item.id] = item
            dialogo._gestor._orden.append(item.id)
        dialogo.pagina_descargas.refrescar()
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def _relleno(self):
        import wx as _wx
        if _tema.ALTO_CONTRASTE:
            return _wx.SystemSettings.GetColour(_wx.SYS_COLOUR_HIGHLIGHT)
        return _tema._T.accent

    def _dialogo_con_filas(self):
        item = descargas.ItemDescarga(
            "media", "https://youtu.be/media", "video", nombre="media.mp4")
        item.estado = "descargando"
        item.progreso = 45.0
        return self._dialogo([
            {"id": "hecha", "nombre": "hecha.mp4",
             "fecha": "2026-10-30T08:33:00", "estado": "completado",
             "url": "https://youtu.be/hecha", "carpeta": "C:/D",
             "ruta": "C:/D/hecha.mp4"},
            {"id": "mala", "nombre": "mala.mp4",
             "fecha": "2026-10-29T08:33:00", "estado": "error",
             "url": "https://youtu.be/mala", "carpeta": "C:/D", "ruta": ""}],
            activos=[item])

    def test_lista_de_imagenes_con_21_tramos_de_60_por_12(self):
        pagina = self._dialogo_con_filas().pagina_descargas
        imagenes = pagina.lista.GetImageList(wx.IMAGE_LIST_SMALL)
        self.assertEqual(imagenes.GetImageCount(), 21)
        for indice in (0, 20):
            self.assertEqual(tuple(imagenes.GetBitmap(indice).GetSize()),
                             (60, 12))
        relleno = (self._relleno().Red(), self._relleno().Green(),
                   self._relleno().Blue())
        vacia = imagenes.GetBitmap(0).ConvertToImage()
        for x in range(60):
            for y in range(12):
                self.assertNotEqual(
                    (vacia.GetRed(x, y), vacia.GetGreen(x, y),
                     vacia.GetBlue(x, y)), relleno)
        llena = imagenes.GetBitmap(20).ConvertToImage()
        self.assertEqual(
            (llena.GetRed(30, 6), llena.GetGreen(30, 6),
             llena.GetBlue(30, 6)), relleno)

    def test_filas_con_barra_texto_e_imagen(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        item = descargas.ItemDescarga(
            "media", "https://youtu.be/media", "video", nombre="media.mp4")
        item.estado = "descargando"
        item.progreso = 45.0
        dialogo._gestor._items[item.id] = item
        dialogo._gestor._orden.append(item.id)
        pagina._historial = [
            {"id": "hecha", "nombre": "hecha.mp4",
             "fecha": "2026-10-30T08:33:00", "estado": "completado",
             "url": "https://youtu.be/hecha", "carpeta": "C:/D",
             "ruta": "C:/D/hecha.mp4"},
            {"id": "mala", "nombre": "mala.mp4",
             "fecha": "2026-10-29T08:33:00", "estado": "error",
             "url": "https://youtu.be/mala", "carpeta": "C:/D", "ruta": ""}]
        with mock.patch.object(pagina.lista, "SetItemImage",
                               wraps=pagina.lista.SetItemImage) as fijar:
            pagina.refrescar()
        self.assertEqual(pagina.lista.GetColumnWidth(0), 120)
        self.assertEqual(pagina.lista.GetItemText(0, 0), "45 %")
        self.assertEqual(pagina.lista.GetItemText(1, 0), "100 %")
        self.assertEqual(pagina.lista.GetItemText(2, 0), "")
        self.assertEqual(fijar.call_args_list,
                         [mock.call(0, 9), mock.call(1, 20)])
        fijar.reset_mock()
        pagina.refrescar()
        fijar.assert_not_called()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoVentana(unittest.TestCase):
    """Pseudotraducción de la ventana."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        cargar = mock.patch.object(descargas_listas.historial_descargas, "cargar", return_value=[])
        guardar = mock.patch.object(descargas_listas.historial_descargas, "guardar")
        guardar_acc = mock.patch.object(descargas_acciones.historial_descargas, "guardar")
        cargar_rec = mock.patch.object(descargas_buscador.busquedas_recientes, "cargar",
                                       return_value=[])
        guardar_rec = mock.patch.object(descargas_buscador.busquedas_recientes, "guardar")
        with cargar, guardar, guardar_acc, cargar_rec, guardar_rec, con_pseudo():
            dialogo = gui_descargas.GestorDescargasDialog(None)
            sin_marcar = textos_sin_marcar(
                dialogo, propios=("2160p", "1440p", "1080p", "720p", "480p",
                                  "360p", "128 kbps", "192 kbps", "256 kbps",
                                  "320 kbps", "10", "20", "30", "50"))
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        self.assertEqual([], sin_marcar)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoAvisos(unittest.TestCase):
    """Anuncios y cuadros propios salen marcados."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def _dialogo(self):
        cargar = mock.patch.object(descargas_listas.historial_descargas, "cargar", return_value=[])
        guardar = mock.patch.object(descargas_listas.historial_descargas, "guardar")
        guardar_acc = mock.patch.object(descargas_acciones.historial_descargas, "guardar")
        cargar_rec = mock.patch.object(descargas_buscador.busquedas_recientes, "cargar",
                                       return_value=[])
        guardar_rec = mock.patch.object(descargas_buscador.busquedas_recientes, "guardar")
        cargar.start()
        guardar.start()
        guardar_acc.start()
        cargar_rec.start()
        guardar_rec.start()
        self.addCleanup(cargar.stop)
        self.addCleanup(guardar.stop)
        self.addCleanup(guardar_acc.stop)
        self.addCleanup(cargar_rec.stop)
        self.addCleanup(guardar_rec.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def test_avisos_y_cuadros_propios_salen_marcados(self):
        dialogo = self._dialogo()
        with con_pseudo(), mock.patch.object(descargas_buscador, "anunciar") as anunciar, \
                mock.patch.object(buscador_tandas._snd, "reproducir"):
            dialogo.pagina_buscador.campo.SetValue("")
            dialogo.pagina_buscador._on_buscar(None)
        self.assertTrue(anunciar.call_args.args[0].startswith("[¡"))
        with con_pseudo(), mock.patch.object(descargas_acciones, "anunciar") as anunciar2, \
                mock.patch.object(descargas_acciones._snd, "reproducir"):
            dialogo.pagina_descargas._on_cancelar(None)
        self.assertTrue(anunciar2.call_args.args[0].startswith("[¡"))


if __name__ == "__main__":
    unittest.main()

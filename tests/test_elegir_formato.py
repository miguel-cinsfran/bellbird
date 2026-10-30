"""Elegir el formato exacto de un vídeo del buscador.

Sin ventana: `opciones_de` ofrece «formato» solo para un vídeo descargable
único y en ese orden, y `transitorias_de` con sus tres casos. Abren
ventanas: el cuadro nuevo y la consulta que lo llena.
"""

import unittest
from unittest import mock

from bellbird.downloads import formatos_reales, opciones_formato
from bellbird.downloads.busqueda_youtube import Resultado
from bellbird.ui import buscador_acciones
from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

try:
    from bellbird.ui import elegir_formato
    _HAY_ELEGIR = True
except ImportError:
    elegir_formato = None  # type: ignore
    _HAY_ELEGIR = False


def _res(id="v", tipo="video", directo=False, programado=False):
    return Resultado(
        id=id, url=f"https://www.youtube.com/watch?v={id}",
        titulo=f"Título {id}", canal=f"Canal {id}", duracion=60, vistas=10,
        marca_tiempo=1700000000, descripcion=f"Descripción {id}",
        tipo=tipo, en_directo=directo, programado=programado)


class TestOpcionesDeFormato(unittest.TestCase):
    # Sin ventana: opciones_de es pura, solo mira el Resultado.

    def test_video_unico_con_todo_ofrece_formato_tras_video(self):
        self.assertEqual(
            buscador_acciones.opciones_de(_res(), True, True),
            ("agregar", "escuchar", "audio", "video", "formato", "bellbird",
             "musica", "copiar", "navegador", "sitios"))

    def test_video_unico_sin_nada_ofrece_formato_tras_video(self):
        self.assertEqual(
            buscador_acciones.opciones_de(_res(), False, False),
            ("agregar", "escuchar", "audio", "video", "formato", "copiar",
             "navegador", "sitios"))

    def test_solo_el_video_unico_descargable_lo_ofrece(self):
        casos = [
            [_res("v"), _res("w")],
            [_res(tipo="lista")],
            [_res(tipo="canal")],
            [_res(directo=True)],
            [_res(programado=True)],
        ]
        for entrada in casos:
            with self.subTest(entrada=entrada):
                self.assertNotIn(
                    "formato",
                    buscador_acciones.opciones_de(entrada, True, True))


class TestTransitoriasDe(unittest.TestCase):
    # Sin ventana: transitorias_de es pura.

    def test_audio_da_audio_original(self):
        self.assertEqual(opciones_formato.transitorias_de("audio"),
                         {"formato": "audio_original"})

    def test_video_da_mp4(self):
        self.assertEqual(opciones_formato.transitorias_de("video"),
                         {"formato": "mp4"})

    def test_diccionario_se_devuelve_igual(self):
        dado = {"formato": "exacto", "selector": "299+140",
                "contenedor": "mp4"}
        self.assertEqual(opciones_formato.transitorias_de(dado), dado)


@unittest.skipUnless(_HAY_WX and _HAY_ELEGIR, "wxPython no está instalado")
class TestSonarSinSonido(unittest.TestCase):
    # Sin ventana: _sonar solo registra.

    def test_registra_evento_y_error(self):
        with mock.patch.object(elegir_formato._snd, "reproducir",
                               side_effect=RuntimeError("falla")), \
                mock.patch.object(elegir_formato, "logger") as registro:
            elegir_formato._sonar("formatos_cargando")
        registro.debug.assert_called_once_with(
            "sin sonido de %s: %s", "formatos_cargando", mock.ANY)


def _opciones_dobles():
    return [
        formatos_reales.OpcionFormato(
            etiqueta="1080p, MP4, 100 MB", selector="299+140",
            contenedor="mp4", tamano=100000000),
        formatos_reales.OpcionFormato(
            etiqueta="720p, MP4, 50 MB", selector="22+140",
            contenedor="mp4", tamano=50000000),
        formatos_reales.OpcionFormato(
            etiqueta="Solo audio, M4A, 128 kbps, 5 MB", selector="140",
            contenedor="m4a", tamano=5000000),
    ]


@unittest.skipUnless(_HAY_WX and _HAY_ELEGIR, "wxPython no está instalado")
class TestDialogoFormato(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.opciones = _opciones_dobles()
        self.dialogo = elegir_formato.DialogoFormato(None, self.opciones)
        self.addCleanup(destruir, self.dialogo)

    def test_foco_en_lista_primera_elegida_y_segunda_al_moverse(self):
        self.dialogo.Show()
        try:
            self.assertEqual(wx.Window.FindFocus(), self.dialogo.lista)
        finally:
            self.dialogo.Hide()
        self.assertEqual(self.dialogo.lista.GetCount(), 3)
        self.assertEqual(self.dialogo.lista.GetSelection(), 0)
        self.assertEqual(self.dialogo.elegida(), self.opciones[0])
        self.dialogo.lista.SetSelection(1)
        self.assertEqual(self.dialogo.elegida(), self.opciones[1])

    def test_orden_de_tab_lista_descargar_cancelar(self):
        orden = [c for c in self.dialogo.panel.GetChildren()
                 if c in (self.dialogo.lista, self.dialogo.btn_descargar,
                          self.dialogo.btn_cancelar)]
        self.assertEqual(orden, [self.dialogo.lista,
                                 self.dialogo.btn_descargar,
                                 self.dialogo.btn_cancelar])
        self.assertEqual(self.dialogo.btn_descargar.GetId(), wx.ID_OK)
        self.assertEqual(self.dialogo.btn_cancelar.GetId(), wx.ID_CANCEL)
        self.assertEqual(
            [self.dialogo.lista.GetString(i) for i in range(3)],
            [o.etiqueta for o in self.opciones])

    def test_margen_de_8_entre_descargar_y_cancelar(self):
        vs = self.dialogo.panel.GetSizer()
        fila = vs.GetItem(vs.GetItemCount() - 1).GetSizer()
        self.assertEqual(fila.GetItem(0).GetBorder(), 8)


class _HiloYa:
    """El hilo corre en el acto, como en las pruebas del buscador."""

    def __init__(self, destino, argumentos):
        self._destino = destino
        self._argumentos = argumentos

    def start(self):
        self._destino(*self._argumentos)


@unittest.skipUnless(_HAY_WX and _HAY_ELEGIR, "wxPython no está instalado")
class TestConsultaFormatos(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.resultado = _res()
        self.opciones = _opciones_dobles()[:2]

    def _dobles(self, info=None, opciones=None, respuesta=None,
                padre=None):
        if info is None:
            info = {"formats": []}
        if opciones is None:
            opciones = list(self.opciones)
        if respuesta is None:
            respuesta = wx.ID_OK
        hilo = mock.patch.object(
            elegir_formato.diagnostico, "crear_hilo",
            side_effect=lambda destino, nombre, args=(),
            **kw: _HiloYa(destino, args))
        hilo.start()
        self.addCleanup(hilo.stop)
        entrega = mock.patch.object(
            elegir_formato.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kw: funcion(*args, **kw))
        entrega.start()
        self.addCleanup(entrega.stop)
        activo = mock.patch.object(
            elegir_formato.wx, "GetActiveWindow", return_value=padre)
        activo.start()
        self.addCleanup(activo.stop)
        datos = mock.patch.object(
            elegir_formato.ytdlp_bin, "info_video", return_value=info)
        datos.start()
        self.addCleanup(datos.stop)
        reales = mock.patch.object(
            elegir_formato.formatos_reales, "opciones",
            return_value=opciones)
        reales.start()
        self.addCleanup(reales.stop)
        creados = []

        class _Falso:
            def __init__(self, padre, dadas):
                creados.append((padre, list(dadas)))

            def ShowModal(self):
                return respuesta

            def elegida(self):
                return self._elegida

            def Destroy(self):
                pass

        _Falso._elegida = opciones[1] if opciones else None
        dialogo = mock.patch.object(elegir_formato, "DialogoFormato", _Falso)
        dialogo.start()
        self.addCleanup(dialogo.stop)
        parche_anunciar = mock.patch.object(elegir_formato, "anunciar")
        anunciar = parche_anunciar.start()
        self.addCleanup(parche_anunciar.stop)
        parche_sonido = mock.patch.object(elegir_formato._snd, "reproducir")
        sonido = parche_sonido.start()
        self.addCleanup(parche_sonido.stop)
        return creados, anunciar, sonido

    def test_con_datos_abre_y_agrega_lo_elegido(self):
        creados, anunciar, sonido = self._dobles(padre=mock.sentinel.padre)
        agregar = mock.Mock()
        elegir_formato.ConsultaFormatos(agregar).pedir(self.resultado)
        self.assertEqual(len(creados), 1)
        self.assertIs(creados[0][0], mock.sentinel.padre)
        self.assertEqual([o.selector for o in creados[0][1]],
                         [o.selector for o in self.opciones])
        agregar.assert_called_once_with(
            [self.resultado.url],
            formato=formatos_reales.transitorias(self.opciones[1]),
            titulo=self.resultado.titulo)
        anunciar.assert_called_once_with("Cargando formatos")
        sonido.assert_called_once_with("formatos_cargando")

    def test_sin_datos_anuncia_el_fallo_sin_abrir(self):
        creados, anunciar, sonido = self._dobles(
            info=None, opciones=[], padre=mock.sentinel.padre)
        agregar = mock.Mock()
        elegir_formato.ConsultaFormatos(agregar).pedir(self.resultado)
        self.assertEqual(creados, [])
        agregar.assert_not_called()
        anunciar.assert_called_with("No se pudieron cargar los formatos.")
        sonido.assert_called_with("formatos_fallidos")

    def test_lista_vacia_anuncia_el_fallo(self):
        creados, anunciar, sonido = self._dobles(
            info={"formats": []}, opciones=[],
            padre=mock.sentinel.padre)
        agregar = mock.Mock()
        elegir_formato.ConsultaFormatos(agregar).pedir(self.resultado)
        self.assertEqual(creados, [])
        agregar.assert_not_called()
        sonido.assert_called_with("formatos_fallidos")

    def test_cancelar_no_agrega(self):
        creados, _anunciar, _sonido = self._dobles(
            respuesta=wx.ID_CANCEL, padre=mock.sentinel.padre)
        agregar = mock.Mock()
        elegir_formato.ConsultaFormatos(agregar).pedir(self.resultado)
        self.assertEqual(len(creados), 1)
        agregar.assert_not_called()

    def test_sin_padre_no_abre(self):
        creados, _anunciar, _sonido = self._dobles(padre=None)
        agregar = mock.Mock()
        elegir_formato.ConsultaFormatos(agregar).pedir(self.resultado)
        self.assertEqual(creados, [])
        agregar.assert_not_called()

    def test_dos_pedidos_reusan_la_misma_consulta(self):
        acciones = buscador_acciones.AccionesResultado(mock.Mock())
        with mock.patch.object(elegir_formato.diagnostico,
                               "crear_hilo") as hilo, \
                mock.patch.object(elegir_formato, "anunciar"), \
                mock.patch.object(elegir_formato._snd, "reproducir"):
            acciones.elegir_formato(self.resultado)
            acciones.elegir_formato(self.resultado)
        self.assertEqual(hilo.call_count, 1)

    def test_padre_cerrado_antes_de_volver_no_abre_pero_libera(self):
        admin = mock.Mock()
        admin.__bool__ = mock.Mock(return_value=False)
        otra = mock.Mock()
        estado = {"vivo": True}

        def _activa():
            return admin if estado["vivo"] else otra

        llegadas = []
        creados = []

        class _Falso:
            def __init__(self, padre, dadas):
                creados.append((padre, list(dadas)))

            def ShowModal(self):
                return wx.ID_OK

            def elegida(self):
                return self._opcion

            def Destroy(self):
                pass

        _Falso._opcion = self.opciones[1]
        agregar = mock.Mock()
        with mock.patch.object(elegir_formato.wx, "GetActiveWindow",
                               side_effect=_activa), \
                mock.patch.object(
                    elegir_formato.wx, "CallAfter",
                    side_effect=lambda funcion, *args, **kw: funcion(*args, **kw)), \
                mock.patch.object(
                    elegir_formato.diagnostico, "crear_hilo",
                    side_effect=lambda destino, nombre, args=(), **kw: llegadas.append((destino, args)) or mock.Mock()), \
                mock.patch.object(elegir_formato.ytdlp_bin, "info_video",
                                   return_value={"formats": []}), \
                mock.patch.object(elegir_formato.formatos_reales, "opciones",
                                   return_value=list(self.opciones)), \
                mock.patch.object(elegir_formato, "DialogoFormato", _Falso), \
                mock.patch.object(elegir_formato, "anunciar"), \
                mock.patch.object(elegir_formato._snd, "reproducir"):
            consulta = elegir_formato.ConsultaFormatos(agregar)
            consulta.pedir(self.resultado)
            estado["vivo"] = False
            destino, argumentos = llegadas[0]
            destino(*argumentos)
            self.assertEqual(creados, [])
            agregar.assert_not_called()
            consulta.pedir(self.resultado)
            self.assertEqual(len(llegadas), 2)

    def test_segundo_pedir_en_curso_no_lanza_otra(self):
        llegadas = []
        hilo = mock.patch.object(
            elegir_formato.diagnostico, "crear_hilo",
            side_effect=lambda destino, nombre, args=(),
            **kw: llegadas.append((destino, args)) or mock.Mock())
        hilo.start()
        self.addCleanup(hilo.stop)
        with mock.patch.object(elegir_formato.wx, "CallAfter"), \
                mock.patch.object(elegir_formato, "anunciar"), \
                mock.patch.object(elegir_formato._snd, "reproducir"):
            consulta = elegir_formato.ConsultaFormatos(mock.Mock())
            consulta.pedir(self.resultado)
            consulta.pedir(self.resultado)
        self.assertEqual(len(llegadas), 1)


if __name__ == "__main__":
    unittest.main()

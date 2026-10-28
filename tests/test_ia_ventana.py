"""Pruebas de la ventana Preguntar a la IA.

Con ventana: las corre el advisor en otra PC. No correr aquí, abren
diálogos.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import protocolos
from ytchat.ai import ventana_ia
from ytchat.ui import ia_ventana as ventana
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


def _hilo_directo(target, nombre, **kwargs):
    args = kwargs.get("args", ())
    target(*args)
    hilo = mock.Mock()
    hilo.start.return_value = None
    return hilo


def _ajustes_falsos(privacidad_aceptada=True, decir_analizando=True):
    return SimpleNamespace(proveedor="gemini", modelo="m", direccion="",
                           pregunta="", largo="media", tiempo_espera=60,
                           decir_analizando=decir_analizando,
                           privacidad_aceptada=privacidad_aceptada)


class PortapapelesDoble:
    def __init__(self):
        self.texto = None

    def Open(self):
        return True

    def SetData(self, datos):
        self.texto = datos.GetText()

    def Flush(self):
        return True

    def Close(self):
        pass


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestVentanaIAVentana(unittest.TestCase):
    # Con ventana: las corre el advisor. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        parche_hilo = mock.patch.object(
            ventana.diagnostico, "crear_hilo", side_effect=_hilo_directo)
        parche_hilo.start()
        self.addCleanup(parche_hilo.stop)
        parche_llamada = mock.patch.object(
            ventana.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs: funcion(*args,
                                                                **kwargs))
        parche_llamada.start()
        self.addCleanup(parche_llamada.stop)

    def _ventana(self):
        dialogo = ventana.VentanaIA(None)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_nombres(self):
        dialogo = self._ventana()
        self.assertEqual(dialogo.GetTitle(), "Preguntar a la IA")
        self.assertEqual(dialogo.GetName(), "VentanaIA")
        self.assertEqual(dialogo.lst_conversacion.GetName(), "Conversación")
        self.assertEqual(dialogo.txt_mensaje.GetName(), "Mensaje")
        self.assertEqual(dialogo.btn_enviar.GetName(), "Enviar")
        self.assertEqual(dialogo.btn_captura.GetName(), "Agregar captura")
        self.assertEqual(dialogo.btn_copiar.GetName(), "Copiar respuesta")
        self.assertEqual(dialogo.btn_nueva.GetName(), "Nueva conversación")
        self.assertEqual(dialogo.btn_cerrar.GetName(), "Cerrar")

    def test_instala_busqueda_por_tecleo_en_la_conversacion(self):
        with mock.patch.object(ventana, "instalar_busqueda_tipo") as instalar:
            dialogo = self._ventana()

        instalar.assert_called_once()
        lista, obtener_textos = instalar.call_args.args
        self.assertIs(lista, dialogo.lst_conversacion)
        self.assertEqual(obtener_textos(),
                         list(dialogo.lst_conversacion.GetStrings()))

    def test_orden_de_tab(self):
        dialogo = self._ventana()
        navegables = [hijo.GetName() for hijo in dialogo.GetChildren()
                      if isinstance(hijo, (wx.ListBox, wx.TextCtrl,
                                          wx.CheckBox, wx.Button))]
        self.assertEqual(navegables, ["Conversación", "Mensaje",
                                      "Enviar", "Agregar captura",
                                      "Copiar respuesta",
                                      "Nueva conversación", "Cerrar"])
        self.assertIs(dialogo.FindFocus(), dialogo.txt_mensaje)

    def test_mnemonicos_sin_repetir(self):
        dialogo = self._ventana()
        rotulos = [dialogo.rotulo_conv.GetLabel(),
                   dialogo.rotulo_msg.GetLabel(),
                   dialogo.btn_enviar.GetLabel(),
                   dialogo.btn_captura.GetLabel(),
                   dialogo.btn_copiar.GetLabel(),
                   dialogo.btn_nueva.GetLabel(),
                   dialogo.btn_cerrar.GetLabel()]
        letras = set()
        for rotulo in rotulos:
            posicion = rotulo.find("&")
            self.assertNotEqual(posicion, -1, f"Sin tecla en {rotulo!r}.")
            self.assertLess(posicion + 1, len(rotulo))
            letras.add(rotulo[posicion + 1].lower())
        self.assertEqual(letras, {"v", "m", "e", "c", "o", "n", "r"})

    def test_fila_guia_con_lista_vacia(self):
        dialogo = self._ventana()
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 1)
        self.assertEqual(dialogo.lst_conversacion.GetString(0),
                         ventana_ia.FILA_GUIA)

    def test_detalle_muestra_texto_y_escape_cierra(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo._rehacer_lista()
        dialogo.lst_conversacion.SetSelection(0)
        esperado = dialogo.lst_conversacion.GetString(0)
        visto = {}

        def _falso_mostrar(uno_mismo):
            visto["texto"] = uno_mismo.txt.GetValue()
            return wx.ID_OK

        with mock.patch.object(ventana.DialogoMensaje, "ShowModal",
                               _falso_mostrar):
            dialogo._mostrar_mensaje()
        self.assertEqual(visto.get("texto"), esperado)
        # El detalle se mostró y se destruyó sin romper la ventana.
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 1)

    def test_dialogo_mensaje_accesible_y_escape_cierra(self):
        dialogo = self._ventana()
        detalle = ventana.DialogoMensaje(dialogo, "texto largo")
        self.addCleanup(destruir, detalle)
        self.assertEqual(detalle.txt.GetName(), "Mensaje completo")
        estilo = detalle.txt.GetWindowStyleFlag()
        self.assertTrue(estilo & wx.TE_MULTILINE)
        self.assertTrue(estilo & wx.TE_READONLY)
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(detalle, "EndModal") as fin:
            detalle._al_tecla(evento)
        fin.assert_called_once_with(wx.ID_CANCEL)

    def test_enviar_sin_captura_anuncia_y_no_envia(self):
        dialogo = self._ventana()
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        envio = mock.Mock()
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos()), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   side_effect=conversacion.SinCaptura("x")), \
                mock.patch.object(ventana.envio_ia, "enviar", envio), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_enviar(None)
        anunciar.assert_called_once_with(
            "Agrega una captura antes de preguntar.")
        sonar.assert_called_once_with("ia_error")
        envio.assert_not_called()
        self.assertIs(dialogo.FindFocus(), dialogo.txt_mensaje)

    def test_sin_aceptar_privacidad_no_envia_ni_suena(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos(
                                   privacidad_aceptada=False)), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.wx, "MessageBox",
                                   return_value=wx.NO), \
                mock.patch.object(ventana.ia_privacidad.ajustes_ia,
                                   "guardar_privacidad_aceptada") as guardar, \
                mock.patch.object(ventana.diagnostico,
                                   "crear_hilo") as hilo, \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_enviar(None)
        hilo.assert_not_called()
        guardar.assert_not_called()
        sonar.assert_not_called()
        anunciar.assert_not_called()
        self.assertFalse(dialogo._en_curso)
        self.assertIs(dialogo.FindFocus(), dialogo.txt_mensaje)

    def test_aceptar_privacidad_guarda_y_envia(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        respuesta = protocolos.Respuesta("Se ve bien.", False)
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos(
                                   privacidad_aceptada=False)), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   return_value=respuesta), \
                mock.patch.object(ventana.wx, "MessageBox",
                                   return_value=wx.YES), \
                mock.patch.object(ventana.ia_privacidad.ajustes_ia,
                                   "guardar_privacidad_aceptada",
                                   return_value=True) as guardar, \
                mock.patch.object(ventana, "anunciar"), \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_enviar(None)
        guardar.assert_called_once_with(ventana.paths.config_ini(), True)
        sonar.assert_any_call("ia_enviada")
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 3)

    def test_privacidad_ya_aceptada_no_muestra_aviso(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        respuesta = protocolos.Respuesta("Se ve bien.", False)
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos()), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   return_value=respuesta), \
                mock.patch.object(ventana.wx, "MessageBox") as caja, \
                mock.patch.object(ventana, "anunciar"), \
                mock.patch.object(ventana, "reproducir"):
            dialogo._al_enviar(None)
        caja.assert_not_called()
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 3)

    def test_captura_agregada_aparece_y_se_anuncia(self):
        dialogo = self._ventana()
        captura = SimpleNamespace(jpeg=b"jpg-falso")

        def _pedir(padre, al_terminar):
            al_terminar(("Cámara", captura))

        class _Gestor:
            def conectar(self):
                pass

            def descripcion_escena(self):
                return "Escena con una cámara."

            def cerrar(self):
                pass

        with mock.patch.object(ventana, "pedir_captura",
                               side_effect=_pedir), \
                mock.patch.object(ventana, "GestorPanelObs",
                                   return_value=_Gestor()):
            orden = mock.Mock()
            with mock.patch.object(ventana, "anunciar", orden.anunciar), \
                    mock.patch.object(ventana, "reproducir", orden.sonar):
                dialogo._al_captura(None)
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 1)
        self.assertTrue(dialogo.lst_conversacion.GetString(0).startswith(
            "Captura: Cámara, "))
        self.assertEqual(
            orden.mock_calls,
            [mock.call.sonar("ia_captura"),
             mock.call.anunciar("Captura agregada: Cámara.")])
        self.assertEqual(dialogo._descripcion, "Escena con una cámara.")
        self.assertIs(dialogo.FindFocus(), dialogo.txt_mensaje)

    def test_envio_bueno_deja_dos_filas_anuncia_y_suena(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        respuesta = protocolos.Respuesta("Se ve bien.", False)
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos()), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   return_value=respuesta), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_enviar(None)
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 3)
        self.assertEqual(dialogo.lst_conversacion.GetString(2),
                         "Respuesta: Se ve bien.")
        anunciar.assert_called_once_with("Se ve bien.")
        sonar.assert_any_call("ia_enviada")
        sonar.assert_any_call("ia_respuesta")
        self.assertEqual(dialogo.txt_mensaje.GetValue(), "")
        self.assertEqual(dialogo.lst_conversacion.GetSelection(), 2)

    def test_error_de_cuota_anuncia_su_frase_y_no_agrega(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        fallo = protocolos.ErrorIA(protocolos.CUOTA, "sin saldo")
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos()), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   side_effect=fallo), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_enviar(None)
        anunciar.assert_called_once_with(
            "Se agotó la cuota del proveedor. Espera un rato "
            "o elige otro modelo.")
        self.assertEqual(sonar.mock_calls, [mock.call("ia_enviada"),
                                            mock.call("ia_error")])
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 1)
        self.assertEqual(dialogo.txt_mensaje.GetValue(), "¿qué se ve?")

    def test_resultado_tras_cancelar_no_agrega_ni_anuncia(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        respuesta = protocolos.Respuesta("Tarde.", False)
        guardadas = []

        def _hilo_guardado(target, nombre, **kwargs):
            guardadas.append((target, kwargs.get("args", ())))
            hilo = mock.Mock()
            hilo.start.return_value = None
            return hilo

        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos()), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   return_value=respuesta), \
                mock.patch.object(ventana.diagnostico, "crear_hilo",
                                   side_effect=_hilo_guardado), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_enviar(None)
            self.assertEqual(len(guardadas), 1)
            dialogo._al_tecla(evento)
            fin.assert_not_called()
            destino, args = guardadas[0]
            destino(*args)
        anunciar.assert_called_once_with(ventana_ia.TEXTO_CANCELADA)
        self.assertEqual(sonar.mock_calls, [mock.call("ia_enviada"),
                                            mock.call("ia_cancelada")])
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 1)

    def test_escape_sin_consulta_cierra_sin_sonar(self):
        dialogo = self._ventana()
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(dialogo, "EndModal") as fin, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_tecla(evento)
        fin.assert_called_once_with(wx.ID_CLOSE)
        sonar.assert_not_called()

    def test_copiar_respuesta_pone_texto_y_avisa(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo._charla.confirmar("hola", "respuesta final")
        falso = PortapapelesDoble()
        with mock.patch.object(ventana.wx, "TheClipboard", falso), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_copiar(None)
        self.assertEqual(falso.texto, "respuesta final")
        sonar.assert_called_once_with("copiar")
        anunciar.assert_called_once_with("Respuesta copiada.")

    def test_copiar_si_no_abre_avisa_fallo(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo._charla.confirmar("hola", "respuesta final")

        class _Cerrado:
            def Open(self):
                return False

        with mock.patch.object(ventana.wx, "TheClipboard", _Cerrado()), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_copiar(None)
        sonar.assert_called_once_with("ia_error")
        anunciar.assert_called_once_with(ventana_ia.TEXTO_NO_COPIADA)

    def test_copiar_sin_respuesta_avisa_sin_sonido(self):
        dialogo = self._ventana()
        with mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_copiar(None)
        anunciar.assert_called_once_with(
            "Todavía no hay ninguna respuesta.")
        sonar.assert_not_called()

    def test_nueva_conversacion_vacia_y_anuncia(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo._descripcion = "algo"
        dialogo._rehacer_lista()
        with mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_nueva(None)
        self.assertEqual(dialogo.lst_conversacion.GetCount(), 1)
        self.assertEqual(dialogo.lst_conversacion.GetString(0),
                         ventana_ia.FILA_GUIA)
        self.assertEqual(dialogo._descripcion, "")
        anunciar.assert_called_once_with("Conversación nueva.")
        sonar.assert_not_called()
        self.assertIs(dialogo.FindFocus(), dialogo.txt_mensaje)

    def test_la_ventana_no_tiene_casilla_de_analizando(self):
        dialogo = self._ventana()
        self.assertFalse(hasattr(dialogo, "chk_analizando"))

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._ventana()
            sin_marcar = textos_sin_marcar(dialogo)

        self.assertEqual([], sin_marcar)

    def test_detalle_sin_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._ventana()
            detalle = ventana.DialogoMensaje(dialogo, "texto largo")
            self.addCleanup(destruir, detalle)
            sin_marcar = textos_sin_marcar(detalle)

        self.assertEqual([], sin_marcar)

    def test_pseudo_temporizador_anuncia_marcado(self):
        dialogo = self._ventana()
        with con_pseudo(), \
                mock.patch.object(ventana, "anunciar") as anunciar:
            dialogo._al_temporizador(mock.Mock())
        args, kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])
        self.assertEqual(kwargs, {"urgente": False})

    def test_pseudo_escape_en_curso_anuncia_marcado(self):
        dialogo = self._ventana()
        dialogo._en_curso = True
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with con_pseudo(), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir"):
            dialogo._al_tecla(evento)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])

    def test_pseudo_copiar_sin_respuesta_anuncia_marcado(self):
        dialogo = self._ventana()
        with con_pseudo(), \
                mock.patch.object(ventana, "anunciar") as anunciar:
            dialogo._al_copiar(None)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])

    def test_pseudo_copiar_respuesta_anuncia_marcado(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo._charla.confirmar("hola", "respuesta final")
        with con_pseudo(), \
                mock.patch.object(ventana.wx, "TheClipboard",
                                   PortapapelesDoble()), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir"):
            dialogo._al_copiar(None)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])

    def test_pseudo_nueva_conversacion_anuncia_marcado(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        with con_pseudo(), \
                mock.patch.object(ventana, "anunciar") as anunciar:
            dialogo._al_nueva(None)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])

    def test_pseudo_captura_agregada_anuncia_marcado(self):
        dialogo = self._ventana()
        captura = SimpleNamespace(jpeg=b"jpg-falso")

        def _pedir(padre, al_terminar):
            al_terminar(("Cámara", captura))

        class _Gestor:
            def conectar(self):
                pass

            def descripcion_escena(self):
                return "Escena con una cámara."

            def cerrar(self):
                pass

        with con_pseudo(), \
                mock.patch.object(ventana, "pedir_captura",
                                   side_effect=_pedir), \
                mock.patch.object(ventana, "GestorPanelObs",
                                   return_value=_Gestor()), \
                mock.patch.object(ventana, "anunciar") as anunciar, \
                mock.patch.object(ventana, "reproducir"):
            dialogo._al_captura(None)
        self.assertEqual(anunciar.call_count, 1)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])

    def _enviar_con_ajuste(self, decir_analizando):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        respuesta = protocolos.Respuesta("Se ve bien.", False)
        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos(
                                   decir_analizando=decir_analizando)), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   return_value=respuesta), \
                mock.patch.object(ventana, "anunciar"), \
                mock.patch.object(ventana, "reproducir"):
            dialogo._al_enviar(None)
        return dialogo

    def test_melodia_suena_ia_analizando(self):
        dialogo = self._ventana()
        with mock.patch.object(ventana, "reproducir") as sonar:
            dialogo._al_temporizador_melodia(mock.Mock())
        sonar.assert_called_once_with("ia_analizando")

    def test_el_aviso_analizando_lee_el_ajuste_del_envio(self):
        for valor in (False, True):
            with self.subTest(decir_analizando=valor):
                dialogo = self._enviar_con_ajuste(valor)
                self.assertIs(dialogo._decir_analizando, valor)
                with mock.patch.object(ventana, "anunciar") as anunciar:
                    dialogo._al_temporizador(mock.Mock())
                if valor:
                    anunciar.assert_called_once_with(
                        ventana_ia.TEXTO_ANALIZANDO, urgente=False)
                else:
                    anunciar.assert_not_called()

    def test_enviar_arranca_los_dos_avisos_y_al_llegar_paran(self):
        dialogo = self._ventana()
        dialogo._charla.agregar_captura(b"j", "Fuente", "10:00")
        dialogo.txt_mensaje.ChangeValue("¿qué se ve?")
        preparada = consulta.Preparada(object(), "¿qué se ve?", 60)
        respuesta = protocolos.Respuesta("Se ve bien.", False)
        guardadas = []

        def _hilo_guardado(target, nombre, **kwargs):
            guardadas.append((target, kwargs.get("args", ())))
            hilo = mock.Mock()
            hilo.start.return_value = None
            return hilo

        with mock.patch.object(ventana.ajustes_ia, "leer",
                               return_value=_ajustes_falsos()), \
                mock.patch.object(ventana.catalogo, "cargar",
                                   return_value={}), \
                mock.patch.object(ventana.claves, "leer",
                                   return_value="clave"), \
                mock.patch.object(ventana.consulta, "preparar",
                                   return_value=preparada), \
                mock.patch.object(ventana.envio_ia, "enviar",
                                   return_value=respuesta), \
                mock.patch.object(ventana.diagnostico, "crear_hilo",
                                   side_effect=_hilo_guardado), \
                mock.patch.object(ventana, "anunciar"), \
                mock.patch.object(ventana, "reproducir"):
            dialogo._al_enviar(None)
            self.assertTrue(dialogo._temporizador.IsRunning())
            self.assertTrue(dialogo._temporizador_melodia.IsRunning())
            destino, args = guardadas[0]
            destino(*args)
        self.assertFalse(dialogo._temporizador.IsRunning())
        self.assertFalse(dialogo._temporizador_melodia.IsRunning())


if __name__ == "__main__":
    unittest.main()

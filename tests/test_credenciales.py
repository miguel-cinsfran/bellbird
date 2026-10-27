"""Tests del almacén de credenciales (credenciales.py)."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import paths
from ytchat.youtube import credenciales
from tests.rutas_temporales import redirigir_rutas


class TestCredenciales(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # credenciales.ruta() sale de paths: se redirigen sus raíces.
        self._rutas = redirigir_rutas(self._tmp.name)
        self._rutas.__enter__()
        self.addCleanup(self._rutas.__exit__, None, None, None)

    def test_cargar_sin_archivo_devuelve_defaults(self):
        d = credenciales.cargar()
        self.assertEqual(d["api_key"], "")
        self.assertIsNone(d["token"])

    def test_guardar_y_cargar(self):
        self.assertTrue(credenciales.guardar_campo("api_key", "AIzaTEST"))
        self.assertEqual(credenciales.cargar()["api_key"], "AIzaTEST")

    def test_guardar_campo_desconocido_falla(self):
        self.assertFalse(credenciales.guardar_campo("inexistente", "x"))

    def test_estado_lectura(self):
        self.assertFalse(credenciales.hay_lectura())
        credenciales.guardar_campo("api_key", "AIzaTEST")
        self.assertTrue(credenciales.hay_lectura())

    def test_estado_oauth_configurado(self):
        self.assertFalse(credenciales.hay_oauth_configurado())
        credenciales.guardar_campo("oauth_client_id", "id")
        credenciales.guardar_campo("oauth_client_secret", "secret")
        self.assertTrue(credenciales.hay_oauth_configurado())

    def test_sesion_y_cierre(self):
        self.assertFalse(credenciales.hay_sesion())
        credenciales.guardar_campo("token", '{"refresh_token": "x"}')
        self.assertTrue(credenciales.hay_sesion())
        credenciales.cerrar_sesion()
        self.assertFalse(credenciales.hay_sesion())
        # cerrar_sesion no borra la api_key
        credenciales.guardar_campo("api_key", "AIzaTEST")
        credenciales.guardar_campo("token", '{"refresh_token": "x"}')
        credenciales.cerrar_sesion()
        self.assertEqual(credenciales.cargar()["api_key"], "AIzaTEST")

    def test_archivo_corrupto_no_revienta(self):
        (Path(self._tmp.name) / "credenciales.json").write_text("{roto", encoding="utf-8")
        d = credenciales.cargar()
        self.assertEqual(d["api_key"], "")

    def test_guardar_no_deja_temporales(self):
        credenciales.guardar_campo("api_key", "AIzaTEST")
        self.assertEqual(list(Path(self._tmp.name).glob("*.tmp")), [])

    def test_guardar_campo_desde_varios_hilos_no_pisa_los_otros_campos(self):
        # guardar_campo es leer-modificar-escribir: sin candado, dos hilos que
        # escriben campos distintos a la vez se pisan el uno al otro.
        def escribir(clave, valor):
            for _ in range(15):
                credenciales.guardar_campo(clave, valor)
        hilos = [threading.Thread(target=escribir, args=("api_key", "K")),
                 threading.Thread(target=escribir, args=("oauth_client_id", "ID"))]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        d = credenciales.cargar()
        self.assertEqual((d["api_key"], d["oauth_client_id"]), ("K", "ID"))


class TestClienteApp(unittest.TestCase):
    """El cliente de Google que viaja con la app (cliente_app.json)."""

    VACIO = {"oauth_client_id": "", "oauth_client_secret": "", "api_key": ""}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._rutas = redirigir_rutas(self._tmp.name)
        self._rutas.__enter__()
        self.addCleanup(self._rutas.__exit__, None, None, None)

    def _ruta_app(self):
        return Path(self._tmp.name) / "cliente_app.json"

    def test_ausente_devuelve_vacio(self):
        self.assertEqual(credenciales.cliente_app(), self.VACIO)

    def test_roto_devuelve_vacio(self):
        self._ruta_app().write_text("{roto", encoding="utf-8")
        self.assertEqual(credenciales.cliente_app(), self.VACIO)

    def test_no_dict_devuelve_vacio(self):
        self._ruta_app().write_text('["lista", 1]', encoding="utf-8")
        self.assertEqual(credenciales.cliente_app(), self.VACIO)

    def test_sin_claves_devuelve_vacio(self):
        self._ruta_app().write_text('{"otra": "x"}', encoding="utf-8")
        self.assertEqual(credenciales.cliente_app(), self.VACIO)

    def test_completo_devuelve_las_tres(self):
        self._ruta_app().write_text(json.dumps({
            "oauth_client_id": "ID-APP",
            "oauth_client_secret": "SEC-APP",
            "api_key": "KEY-APP",
            "token": "no-debe-salir",
        }), encoding="utf-8")
        self.assertEqual(credenciales.cliente_app(), {
            "oauth_client_id": "ID-APP",
            "oauth_client_secret": "SEC-APP",
            "api_key": "KEY-APP",
        })

    def test_ruta_apunta_a_la_instalacion(self):
        self.assertEqual(paths.cliente_app(),
                         paths.carpeta_instalacion() / "cliente_app.json")

    def test_nunca_lanza_si_la_ruta_falla(self):
        with mock.patch.object(paths, "cliente_app",
                               side_effect=RuntimeError("disco")):
            self.assertEqual(credenciales.cliente_app(), self.VACIO)


class TestEfectivas(unittest.TestCase):
    """Mezcla de credenciales propias con las de la app, sin escribir nada."""

    APP = {"oauth_client_id": "ID-APP", "oauth_client_secret": "SEC-APP",
           "api_key": "KEY-APP"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._rutas = redirigir_rutas(self._tmp.name)
        self._rutas.__enter__()
        self.addCleanup(self._rutas.__exit__, None, None, None)
        (Path(self._tmp.name) / "cliente_app.json").write_text(
            json.dumps(self.APP), encoding="utf-8")

    def _ruta_usuario(self):
        return Path(self._tmp.name) / "credenciales.json"

    def test_sin_nada_propio_toma_las_tres_de_la_app(self):
        ef = credenciales.efectivas()
        self.assertEqual(ef["oauth_client_id"], "ID-APP")
        self.assertEqual(ef["oauth_client_secret"], "SEC-APP")
        self.assertEqual(ef["api_key"], "KEY-APP")
        self.assertIsNone(ef["token"])

    def test_con_id_y_secreto_propios_solo_completa_la_api_key(self):
        credenciales.guardar_campo("oauth_client_id", "ID-MIO")
        credenciales.guardar_campo("oauth_client_secret", "SEC-MIO")
        ef = credenciales.efectivas()
        self.assertEqual(ef["oauth_client_id"], "ID-MIO")
        self.assertEqual(ef["oauth_client_secret"], "SEC-MIO")
        self.assertEqual(ef["api_key"], "KEY-APP")

    def test_con_solo_el_id_propio_no_mezcla(self):
        credenciales.guardar_campo("oauth_client_id", "ID-MIO")
        ef = credenciales.efectivas()
        self.assertEqual(ef["oauth_client_id"], "ID-MIO")
        self.assertEqual(ef["oauth_client_secret"], "")
        self.assertEqual(ef["api_key"], "KEY-APP")

    def test_con_solo_el_secreto_propio_no_mezcla(self):
        credenciales.guardar_campo("oauth_client_secret", "SEC-MIO")
        ef = credenciales.efectivas()
        self.assertEqual(ef["oauth_client_id"], "")
        self.assertEqual(ef["oauth_client_secret"], "SEC-MIO")

    def test_el_token_se_conserva(self):
        credenciales.guardar_campo("token", '{"refresh_token": "x"}')
        ef = credenciales.efectivas()
        self.assertEqual(ef["token"], '{"refresh_token": "x"}')
        self.assertEqual(ef["api_key"], "KEY-APP")

    def test_no_escribe_el_archivo_del_usuario(self):
        credenciales.efectivas()
        self.assertFalse(self._ruta_usuario().exists())
        credenciales.guardar_campo("api_key", "KEY-MIA")
        antes = self._ruta_usuario().read_text(encoding="utf-8")
        credenciales.efectivas()
        self.assertEqual(self._ruta_usuario().read_text(encoding="utf-8"), antes)

    def test_no_modifica_el_dict_de_entrada(self):
        datos = {"api_key": "", "oauth_client_id": "", "oauth_client_secret": "",
                 "token": None}
        credenciales.efectivas(datos)
        self.assertEqual(datos["api_key"], "")

    def test_hay_lectura_con_solo_la_app(self):
        self.assertTrue(credenciales.hay_lectura())

    def test_hay_oauth_con_solo_la_app(self):
        self.assertTrue(credenciales.hay_oauth_configurado())

    def test_usa_cliente_de_la_app(self):
        self.assertTrue(credenciales.usa_cliente_de_la_app())
        credenciales.guardar_campo("oauth_client_id", "ID-MIO")
        credenciales.guardar_campo("oauth_client_secret", "SEC-MIO")
        self.assertFalse(credenciales.usa_cliente_de_la_app())

    def test_usa_cliente_de_la_app_falso_sin_app(self):
        (Path(self._tmp.name) / "cliente_app.json").unlink()
        self.assertFalse(credenciales.usa_cliente_de_la_app())
        self.assertFalse(credenciales.hay_lectura())
        self.assertFalse(credenciales.hay_oauth_configurado())


def _importar_gui():
    """Importa los módulos de GUI sin crear ventanas. None si no se puede."""
    try:
        import wx  # noqa: F401
        from ytchat.ui import gui  # noqa: F401
        from ytchat.ui import gui_comentarios  # noqa: F401
        from ytchat.ui import gui_preferencias  # noqa: F401
        from ytchat.ui import preferencias_api  # noqa: F401
        from ytchat.youtube import youtube_api  # noqa: F401
    except Exception:
        return None
    import wx
    from ytchat.ui import gui
    from ytchat.ui import gui_comentarios
    from ytchat.ui import gui_preferencias
    from ytchat.ui import preferencias_api
    from ytchat.youtube import youtube_api
    return wx, gui, gui_comentarios, gui_preferencias, preferencias_api, youtube_api


class TestCableadoClienteApp(unittest.TestCase):
    """Los clientes se construyen con las efectivas (llega la app al llamar)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._rutas = redirigir_rutas(self._tmp.name)
        self._rutas.__enter__()
        self.addCleanup(self._rutas.__exit__, None, None, None)
        (Path(self._tmp.name) / "cliente_app.json").write_text(json.dumps({
            "oauth_client_id": "ID-APP", "oauth_client_secret": "SEC-APP",
            "api_key": "KEY-APP"}), encoding="utf-8")
        modulos = _importar_gui()
        if modulos is None:
            self.skipTest("wx no disponible")
        self.wx, self.gui, self.gui_comentarios, self.gui_preferencias, \
            self.preferencias_api, self.youtube_api = modulos

    def test_comentarios_construye_con_las_efectivas(self):
        panel = self.gui_comentarios.ComentariosPanel.__new__(
            self.gui_comentarios.ComentariosPanel)
        with mock.patch.object(self.youtube_api, "ClienteYouTube") as cliente:
            panel._cliente()
        cliente.assert_called_once()
        dados = cliente.call_args.args[0]
        self.assertEqual(dados["oauth_client_id"], "ID-APP")
        self.assertEqual(dados["oauth_client_secret"], "SEC-APP")
        self.assertEqual(dados["api_key"], "KEY-APP")

    def test_supervisar_transmision_youtube_construye_con_las_efectivas(self):
        from ytchat.youtube import emision
        # Sesión iniciada pero sin cliente propio: solo token en el archivo.
        credenciales.guardar_campo("token", '{"refresh_token": "x"}')
        frame = self.gui.YTChatFrame.__new__(self.gui.YTChatFrame)
        frame._config = {}
        frame._supervisor = None
        pedido = {"titulo": "T", "descripcion": "D",
                  "privacidad": emision.PRIVACIDAD_INICIAL}
        with mock.patch.object(self.youtube_api, "ClienteYouTube") as cliente, \
                mock.patch("ytchat.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=dict(pedido)), \
                mock.patch.object(frame, "_guardar_datos_directo_youtube",
                                  return_value=dict(pedido)), \
                 mock.patch.object(emision, "ganchos_youtube",
                                   return_value=(mock.Mock(), mock.Mock(),
                                                 mock.Mock())), \
                mock.patch("ytchat.obs.obs_supervisor.SupervisorTransmision"):
            frame._supervisar_transmision("iniciar", destino="YouTube")
        cliente.assert_called_once()
        dados = cliente.call_args.args[0]
        self.assertEqual(dados["oauth_client_id"], "ID-APP")
        self.assertEqual(dados["oauth_client_secret"], "SEC-APP")
        self.assertEqual(dados["token"], '{"refresh_token": "x"}')


class TestApiLoginClienteApp(unittest.TestCase):
    """Iniciar sesión con campos vacíos usa el cliente de la app, sin ventanas."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._rutas = redirigir_rutas(self._tmp.name)
        self._rutas.__enter__()
        self.addCleanup(self._rutas.__exit__, None, None, None)
        modulos = _importar_gui()
        if modulos is None:
            self.skipTest("wx no disponible")
        self.wx, self.gui, self.gui_comentarios, self.gui_preferencias, \
            self.preferencias_api, self.youtube_api = modulos

    def _dialogo(self, cid="", secret=""):
        api = self.preferencias_api
        pagina = api.PaginaApi.__new__(api.PaginaApi)
        pagina._ventana = mock.Mock()
        pagina._login_en_curso = False
        pagina.txt_cid = mock.Mock()
        pagina.txt_cid.GetValue.return_value = cid
        pagina.txt_secret = mock.Mock()
        pagina.txt_secret.GetValue.return_value = secret
        pagina.btn_api_login = mock.Mock()
        pagina.btn_api_logout = mock.Mock()
        pagina.lbl_estado_api = mock.Mock()
        pagina._api_guardar = mock.Mock()
        return pagina

    def _escribir_app(self):
        (Path(self._tmp.name) / "cliente_app.json").write_text(json.dumps({
            "oauth_client_id": "ID-APP", "oauth_client_secret": "SEC-APP",
            "api_key": "KEY-APP"}), encoding="utf-8")

    def _correr_login(self, pagina):
        """Ejecuta _api_login capturando el hilo, sin navegador ni ventanas."""
        api = self.preferencias_api
        hilos = []
        with mock.patch.object(api.youtube_api, "iniciar_sesion",
                               return_value='{"refresh_token": "x"}') as login, \
                mock.patch.object(api.diagnostico, "crear_hilo",
                                  side_effect=lambda t, n: mock.Mock(
                                      start=lambda: hilos.append(t))), \
                mock.patch.object(api, "anunciar"), \
                mock.patch.object(api.wx, "CallAfter"), \
                mock.patch.object(api.wx, "MessageBox") as aviso:
            pagina._api_login(None)
            for objetivo in hilos:
                objetivo()
        return login, aviso

    def test_campos_vacios_usan_el_cliente_de_la_app_sin_guardar(self):
        self._escribir_app()
        pagina = self._dialogo()
        login, _aviso = self._correr_login(pagina)
        login.assert_called_once_with("ID-APP", "SEC-APP")
        pagina._api_guardar.assert_not_called()
        self.assertEqual(pagina.txt_cid.GetValue.call_count, 1)
        self.assertTrue(credenciales.hay_sesion())

    def test_sin_nadie_avisa_y_no_llama_a_iniciar_sesion(self):
        pagina = self._dialogo()
        login, aviso = self._correr_login(pagina)
        login.assert_not_called()
        aviso.assert_called_once()
        self.assertIn("Rellena el ID", aviso.call_args.args[0])

    def test_campos_propios_guardan_como_hoy(self):
        pagina = self._dialogo(cid="ID-MIO", secret="SEC-MIO")
        login, _aviso = self._correr_login(pagina)
        pagina._api_guardar.assert_called_once_with(None)
        login.assert_called_once_with("ID-MIO", "SEC-MIO")

    def test_estado_anuncia_el_cliente_de_la_app(self):
        self._escribir_app()
        pagina = self._dialogo()
        pagina._api_refrescar_estado()
        texto = pagina.lbl_estado_api.SetLabel.call_args.args[0]
        self.assertIn("Se usa el cliente de Google de la aplicación.", texto)

    def test_estado_sin_app_no_agrega_nada(self):
        pagina = self._dialogo()
        pagina._api_refrescar_estado()
        texto = pagina.lbl_estado_api.SetLabel.call_args.args[0]
        self.assertNotIn("cliente de Google", texto)


if __name__ == "__main__":
    unittest.main()

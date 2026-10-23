import queue
import sys
import threading
import types
import unittest
from unittest import mock

from ytchat.capture.conexion import Conexiones, _VistaNula
from ytchat.capture.sesiones import RegistroSesiones


class RegistroEspia(RegistroSesiones):
    def __init__(self):
        super().__init__()
        self.sesiones = []

    def abrir(self):
        sesion = super().abrir()
        self.sesiones.append(sesion)
        return sesion


class HiloInerte:
    def start(self):
        return None


class HiloEjecuta:
    def __init__(self, objetivo):
        self.objetivo = objetivo

    def start(self):
        self.objetivo()


def crear_hilo_inerte(*args, **kwargs):
    return HiloInerte()


class VistaFalsa:
    """Vista falsa que registra las llamadas (actúa como marco vivo)."""

    conexion_propia = False

    def __init__(self):
        self.llamadas = []
        self.activa = True

    def __getattr__(self, nombre):
        if nombre.startswith("_"):
            raise AttributeError(nombre)

        def registrar(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))
            return True

        return registrar


class PruebasSesiones(unittest.TestCase):
    def test_abrir_dos_veces_para_la_sesion_anterior(self):
        registro = RegistroSesiones()
        anterior = registro.abrir()
        nueva = registro.abrir()
        self.assertTrue(anterior.parada.is_set())
        self.assertFalse(nueva.parada.is_set())

    def test_vigente_solo_acepta_el_gen_recien_abierto(self):
        registro = RegistroSesiones()
        anterior = registro.abrir()
        nueva = registro.abrir()
        self.assertTrue(registro.vigente(nueva.gen))
        self.assertFalse(registro.vigente(anterior.gen))

    def test_cerrar_es_idempotente_y_para_la_vigente(self):
        registro = RegistroSesiones()
        sesion = registro.abrir()
        self.assertTrue(registro.cerrar())
        self.assertTrue(sesion.parada.is_set())
        self.assertFalse(registro.cerrar())

    def test_una_sesion_cerrada_deja_de_ser_vigente(self):
        # El hilo Chat que seguía en yt-dlp tras desconectar no debe pasar
        # el guard y aplicar título, historial o «conectado» del vídeo cancelado.
        registro = RegistroSesiones()
        sesion = registro.abrir()
        self.assertTrue(registro.vigente(sesion.gen))
        registro.cerrar()
        self.assertFalse(registro.vigente(sesion.gen))


class PruebasCableadoConexiones(unittest.TestCase):
    def setUp(self):
        self.registro = RegistroEspia()
        self.vista = VistaFalsa()
        self.conexiones = Conexiones(
            queue.Queue(), {}, mock.Mock(), threading.Event(),
            crear_hilo=crear_hilo_inerte, registro=self.registro,
            vista=self.vista)

    def test_conectar_dos_veces_para_la_sesion_de_youtube(self):
        self.conexiones.conectar("dQw4w9WgXcQ")
        self.conexiones.conectar("9bZkp7q19f0")
        self.assertTrue(self.registro.sesiones[0].parada.is_set())
        self.assertFalse(self.registro.sesiones[1].parada.is_set())

    def test_conectar_youtube_y_tiktok_para_youtube(self):
        self.conexiones.conectar("dQw4w9WgXcQ")
        self.conexiones.conectar("https://www.tiktok.com/@pepe/live")
        self.assertTrue(self.registro.sesiones[0].parada.is_set())
        self.assertFalse(self.registro.sesiones[1].parada.is_set())

    def test_desconectar_para_la_sesion_vigente(self):
        self.conexiones.conectar("dQw4w9WgXcQ")
        self.conexiones.desconectar()
        self.assertTrue(self.registro.sesiones[0].parada.is_set())

    def test_youtube_difunde_solo_despues_del_guard_de_sesion(self):
        import main
        callbacks = {}
        def hilo(objetivo, nombre, **kwargs):
            # Se filtra por nombre para que los hilos auxiliares no bloqueen la prueba.
            return HiloEjecuta(objetivo) if nombre == "Chat" else HiloInerte()
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("Título", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=True), \
                mock.patch.object(main, "captura_con_reconexion", side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir") as difundir:
            self.conexiones._crear_hilo = hilo
            self.conexiones.conectar("dQw4w9WgXcQ")
            callbacks["on_message"]("Ana", "Hola", "12:00", monto="US$ 5")
        difundir.assert_called_once()
        self.assertEqual(difundir.call_args.args[0]["plataforma"], "youtube")
        self.assertEqual(difundir.call_args.args[0]["monto"], "US$ 5")

    def test_tiktok_difunde_el_regalo(self):
        import main
        callbacks = {}
        def hilo(objetivo, nombre, **kwargs):
            # Se filtra por nombre para ejecutar solo el hilo que usa esta prueba.
            return HiloEjecuta(objetivo) if nombre == "TikTok" else HiloInerte()
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        self.conexiones._crear_hilo = hilo
        with mock.patch.object(main, "procesar_entrante", side_effect=lambda *a, **k: k["on_message"](
                "Ana", "Hola", main.TIPO_TEXTO, "regalo", "")), \
                mock.patch("ytchat.capture.tiktok_captura.capturar_con_reconexion", side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir") as difundir:
            self.conexiones._conectar_tiktok("pepe")
            callbacks["on_evento"]("Ana", "Hola", main.TIPO_TEXTO, "regalo", "")
        self.assertEqual(difundir.call_args.args[0]["plataforma"], "tiktok")

    def test_youtube_pasa_el_guard_de_sesion_a_obtener_info_video(self):
        import main
        recibido = {}

        def info(vid, **kwargs):
            recibido.update(kwargs)
            return ("Título", main.deteccion.LIVE, {})
        with mock.patch.object(main, "obtener_info_video", side_effect=info), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=False):
            self.conexiones._crear_hilo = lambda objetivo, nombre, **kwargs: (
                HiloEjecuta(objetivo) if nombre == "Chat" else HiloInerte())
            self.conexiones.conectar("dQw4w9WgXcQ")
        # Mientras la sesión sigue vigente responde True; al abrir otra, False:
        # así obtener_info_video deja de encadenar pasos tras desconectar.
        self.assertTrue(recibido["sesion_activa"]())
        self.registro.abrir()
        self.assertFalse(recibido["sesion_activa"]())

    def test_los_detalles_del_directo_se_consultan_nada_mas_conectar(self):
        import main
        consultas = []
        esperas = []
        hilos = {}

        class ClienteFalso:
            def __init__(self, credenciales):
                pass

            def detalles_directo(self, vid):
                consultas.append(vid)
                return {"espectadores": 42, "comienzo": "12:00"}

        def hilo(objetivo, nombre, **kwargs):
            if nombre == "Chat":
                return HiloEjecuta(objetivo)
            hilos[nombre] = objetivo
            return HiloInerte()

        credenciales_falso = types.SimpleNamespace(hay_lectura=lambda: True,
                                                    cargar=lambda: {},
                                                    efectivas=lambda *a, **k: {})
        youtube_api_falso = types.SimpleNamespace(google_disponible=lambda: True,
                                                  ClienteYouTube=ClienteFalso)
        # `from ytchat.youtube import x` mira primero el atributo del paquete:
        # sin estos parches usaría el módulo real si otra prueba ya lo importó.
        from ytchat import youtube as _paquete_youtube
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("Título", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=True), \
                mock.patch.object(main, "captura_con_reconexion"), \
                mock.patch.dict(sys.modules, {"ytchat.youtube.credenciales": credenciales_falso,
                                              "ytchat.youtube.youtube_api": youtube_api_falso}), \
                mock.patch.object(_paquete_youtube, "credenciales",
                                  credenciales_falso, create=True), \
                mock.patch.object(_paquete_youtube, "youtube_api",
                                  youtube_api_falso, create=True):
            self.conexiones._crear_hilo = hilo
            self.conexiones.conectar("dQw4w9WgXcQ")
            parada = self.registro.sesiones[0].parada

            def esperar(timeout=None):
                # La primera espera ya cierra la sesión: el bucle da UNA vuelta.
                esperas.append(timeout)
                parada.set()
                return True
            with mock.patch.object(parada, "wait", side_effect=esperar):
                hilos["DetallesDirecto"]()

        # Antes se esperaba un minuto entero antes de la primera consulta.
        self.assertEqual(consultas, ["dQw4w9WgXcQ"])
        self.assertEqual(esperas, [60])
        self.assertIn(("set_espectadores", (42,), {}), self.vista.llamadas)

    def test_los_detalles_del_directo_usan_credenciales_efectivas(self):
        import main
        construidos = []
        hilos = {}

        class ClienteRegistra:
            def __init__(self, credenciales):
                construidos.append(credenciales)

            def detalles_directo(self, vid):
                return {"espectadores": 42, "comienzo": "12:00"}

        def hilo(objetivo, nombre, **kwargs):
            if nombre == "Chat":
                return HiloEjecuta(objetivo)
            hilos[nombre] = objetivo
            return HiloInerte()

        credenciales_falso = types.SimpleNamespace(
            hay_lectura=lambda: True,
            cargar=lambda: {"origen": "cargar"},
            efectivas=lambda *a, **k: {"origen": "efectivas"})
        youtube_api_falso = types.SimpleNamespace(google_disponible=lambda: True,
                                                  ClienteYouTube=ClienteRegistra)
        # `from ytchat.youtube import x` mira primero el atributo del paquete:
        # sin estos parches usaría el módulo real si otra prueba ya lo importó.
        from ytchat import youtube as _paquete_youtube
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("Título", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=True), \
                mock.patch.object(main, "captura_con_reconexion"), \
                mock.patch.dict(sys.modules, {"ytchat.youtube.credenciales": credenciales_falso,
                                              "ytchat.youtube.youtube_api": youtube_api_falso}), \
                mock.patch.object(_paquete_youtube, "credenciales",
                                  credenciales_falso, create=True), \
                mock.patch.object(_paquete_youtube, "youtube_api",
                                  youtube_api_falso, create=True):
            self.conexiones._crear_hilo = hilo
            self.conexiones.conectar("dQw4w9WgXcQ")
            parada = self.registro.sesiones[0].parada

            def esperar(timeout=None):
                parada.set()
                return True
            with mock.patch.object(parada, "wait", side_effect=esperar):
                hilos["DetallesDirecto"]()

        self.assertEqual(construidos, [{"origen": "efectivas"}])

    def test_youtube_sesion_vieja_no_difunde(self):
        import main
        callbacks = {}
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("Título", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=True), \
                mock.patch.object(main, "captura_con_reconexion", side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir") as difundir:
            # Se filtra por nombre para que los hilos auxiliares no bloqueen la prueba.
            self.conexiones._crear_hilo = lambda objetivo, nombre, **kwargs: (
                HiloEjecuta(objetivo) if nombre == "Chat" else HiloInerte())
            self.conexiones.conectar("dQw4w9WgXcQ")
            self.registro.abrir()
            callbacks["on_message"]("Ana", "viejo", "12:00")
        difundir.assert_not_called()

    def test_youtube_conectado_muestra_conectado_sin_anunciar(self):
        import main
        callbacks = {}
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("Título", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=True), \
                mock.patch.object(main, "captura_con_reconexion", side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir"):
            # Se filtra por nombre para que los hilos auxiliares no bloqueen la prueba.
            self.conexiones._crear_hilo = lambda objetivo, nombre, **kwargs: (
                HiloEjecuta(objetivo) if nombre == "Chat" else HiloInerte())
            self.conexiones.conectar("dQw4w9WgXcQ")
            self.vista.llamadas.clear()
            callbacks["on_estado"]("conectado", "Conectado al chat en vivo.")
        self.assertIn(("set_conectado", (True,), {}), self.vista.llamadas)
        # set_conectado ya anuncia: el texto genérico no se repite.
        self.assertFalse([n for n, _a, _k in self.vista.llamadas
                          if n == "anunciar"])


class TestPlataformaMensajesChat(unittest.TestCase):
    def setUp(self):
        self.registro = RegistroEspia()
        self.vista = VistaFalsa()
        self.conexiones = Conexiones(
            queue.Queue(), {}, mock.Mock(), threading.Event(),
            crear_hilo=crear_hilo_inerte, registro=self.registro,
            vista=self.vista)

    def test_youtube_entrega_plataforma_youtube_a_gui(self):
        import main
        callbacks = {}
        def hilo(objetivo, nombre, **kwargs):
            return HiloEjecuta(objetivo) if nombre == "Chat" else HiloInerte()
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        with mock.patch.object(main, "obtener_info_video",
                               return_value=("Título", main.deteccion.LIVE, {})), \
                mock.patch.object(main.deteccion, "tiene_chat_en_vivo", return_value=True), \
                mock.patch.object(main, "captura_con_reconexion", side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir"):
            self.conexiones._crear_hilo = hilo
            self.conexiones.conectar("dQw4w9WgXcQ")
            callbacks["on_message"]("Ana", "Hola", "12:00", monto="US$ 5", canal_id="CANAL123")
        # Debe haber llamado a agregar_mensaje con plataforma youtube
        agregados = [(a, kw) for n, a, kw in self.vista.llamadas
                     if n == "agregar_mensaje"]
        self.assertTrue(agregados)
        args, kwargs = agregados[0]
        self.assertEqual(kwargs.get("plataforma"), "youtube")
        # Verificar que canal_id también se entregó
        self.assertIn("CANAL123", args)

    def test_tiktok_entrega_plataforma_tiktok_a_gui(self):
        import main
        from ytchat.capture import tiktok_captura
        callbacks = {}
        def hilo(objetivo, nombre, **kwargs):
            return HiloEjecuta(objetivo) if nombre == "TikTok" else HiloInerte()
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        self.conexiones._crear_hilo = hilo
        with mock.patch.object(main, "procesar_entrante",
                               side_effect=lambda *a, **k: k["on_message"](
                                   "Ana", "Hola", "12:00", main.TIPO_TEXTO, "regalo", "TIKID")), \
                mock.patch.object(tiktok_captura, "capturar_con_reconexion", side_effect=captura), \
                mock.patch("ytchat.obs.overlay_servidor.difundir"):
            self.conexiones._conectar_tiktok("pepe")
            callbacks["on_evento"]("Ana", "Hola", main.TIPO_TEXTO, "regalo", "TIKID")
        agregados = [(a, kw) for n, a, kw in self.vista.llamadas
                     if n == "agregar_mensaje"]
        self.assertTrue(agregados)
        args, kwargs = agregados[0]
        self.assertEqual(kwargs.get("plataforma"), "tiktok")


class PruebasFinDirectoTiktok(unittest.TestCase):
    """«fin_directo» cierra igual que «desconectado»: solo cambia el sonido."""

    def setUp(self):
        self.registro = RegistroEspia()
        self.vista = VistaFalsa()
        self.conexiones = Conexiones(
            queue.Queue(), {}, mock.Mock(), threading.Event(),
            crear_hilo=crear_hilo_inerte, registro=self.registro,
            vista=self.vista)

    def _callbacks_tiktok(self):
        callbacks = {}
        def hilo(objetivo, nombre, **kwargs):
            return HiloEjecuta(objetivo) if nombre == "TikTok" else HiloInerte()
        def captura(*args, **kwargs):
            callbacks.update(kwargs)
        self.conexiones._crear_hilo = hilo
        from ytchat.capture import tiktok_captura
        with mock.patch.object(tiktok_captura, "capturar_con_reconexion",
                               side_effect=captura):
            self.conexiones._conectar_tiktok("pepe")
        return callbacks

    def test_fin_directo_cierra_igual_que_desconectado_con_otro_sonido(self):
        callbacks = self._callbacks_tiktok()
        # El _run de TikTok ya apagó la vista al terminar: solo importan
        # las llamadas de on_estado.
        self.vista.llamadas.clear()
        callbacks["on_estado"](
            "desconectado", "El directo de TikTok ha terminado.")
        llamadas_desc = list(self.vista.llamadas)
        self.vista.llamadas.clear()
        callbacks["on_estado"](
            "fin_directo", "El directo de TikTok ha terminado.")
        llamadas_fin = list(self.vista.llamadas)
        # Los mismos métodos en el mismo orden (cierra sesión, borra
        # título y anuncia con el mismo texto).
        self.assertEqual([n for n, _a, _k in llamadas_desc],
                         [n for n, _a, _k in llamadas_fin])
        self.assertEqual(len(llamadas_desc), 3)
        # La única diferencia: el sonido que se pide a set_conectado.
        self.assertEqual(llamadas_desc[0],
                         ("set_conectado", (False, "desconectado"), {}))
        self.assertEqual(llamadas_fin[0],
                         ("set_conectado", (False, "fin_directo"), {}))
        self.assertEqual(llamadas_desc[1:], llamadas_fin[1:])


class PruebasOfflinePasajeroConexion(unittest.TestCase):
    """El «no está en directo» solo es pasajero si la transmisión conectó."""

    def _offline_pasajero_recibido(self, vista):
        conexiones = Conexiones(
            queue.Queue(), {}, mock.Mock(), threading.Event(),
            crear_hilo=crear_hilo_inerte, registro=RegistroEspia(),
            vista=vista)
        recibido = {}

        def hilo(objetivo, nombre, **kwargs):
            return HiloEjecuta(objetivo) if nombre == "TikTok" else HiloInerte()

        def captura(*args, **kwargs):
            recibido.update(kwargs)
        conexiones._crear_hilo = hilo
        from ytchat.capture import tiktok_captura
        with mock.patch.object(tiktok_captura, "capturar_con_reconexion",
                               side_effect=captura):
            conexiones._conectar_tiktok("pepe")
        return recibido.get("offline_pasajero")

    def test_vista_con_conexion_propia_pasa_true(self):
        vista = VistaFalsa()
        vista.conexion_propia = True
        self.assertIs(self._offline_pasajero_recibido(vista), True)

    def test_vista_nula_pasa_false(self):
        self.assertIs(self._offline_pasajero_recibido(_VistaNula()), False)


if __name__ == "__main__":
    unittest.main()

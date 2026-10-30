"""Tests de la lógica pura de tiktok_captura (detección de URLs y errores)."""

import asyncio
import json
import sys
import threading
import types
import unittest
from unittest import mock

from bellbird.capture import tiktok_captura
from bellbird.capture import tiktok_errores as errores
from bellbird.capture.tiktok_captura import (usuario_de_url,
                            _mejor_flujo, autor_de_evento, es_previo_a_conexion)
from bellbird.capture.tiktok_errores import (mensaje_error as _mensaje_error,
    es_error_permanente as _es_error_permanente)


class TestUsuarioDeUrl(unittest.TestCase):

    def test_url_live_completa(self):
        self.assertEqual(
            usuario_de_url("https://www.tiktok.com/@tv_asahi_news/live"),
            "tv_asahi_news")

    def test_url_sin_live(self):
        self.assertEqual(
            usuario_de_url("https://www.tiktok.com/@usuario.x"), "usuario.x")

    def test_url_sin_esquema_ni_www(self):
        self.assertEqual(usuario_de_url("tiktok.com/@pepe/live"), "pepe")

    def test_url_movil(self):
        self.assertEqual(usuario_de_url("https://m.tiktok.com/@pepe/live"), "pepe")

    def test_con_query(self):
        self.assertEqual(
            usuario_de_url("https://www.tiktok.com/@pepe/live?lang=es"), "pepe")

    def test_usuario_suelto_no_vale(self):
        # Un "@usuario" sin dominio chocaría con los handles de YouTube.
        self.assertEqual(usuario_de_url("@pepe"), "")

    def test_youtube_no_es_tiktok(self):
        self.assertEqual(usuario_de_url("https://www.youtube.com/watch?v=abc"), "")
        self.assertEqual(usuario_de_url("https://youtu.be/dQw4w9WgXcQ"), "")

    def test_vacio_y_basura(self):
        self.assertEqual(usuario_de_url(""), "")
        self.assertEqual(usuario_de_url("   "), "")
        self.assertEqual(usuario_de_url("cualquier cosa"), "")

    def test_dominio_parecido_no_vale(self):
        self.assertEqual(usuario_de_url("https://notiktok.com/@pepe/live"), "")

    def test_url_con_mayusculas_baja_el_usuario(self):
        self.assertEqual(
            usuario_de_url("https://www.tiktok.com/@SzeiryuGaming/live"),
            "szeiryugaming")


class TestMensajesDeError(unittest.TestCase):

    def _exc(self, nombre, texto=""):
        return type(nombre, (Exception,), {})(texto)

    def test_offline_es_permanente_y_amigable(self):
        exc = self._exc("UserOfflineError", "user is offline")
        self.assertTrue(_es_error_permanente(exc))
        self.assertIn("no está en directo", _mensaje_error(exc))

    def test_usuario_inexistente(self):
        exc = self._exc("UserNotFoundError", "user not found")
        self.assertTrue(_es_error_permanente(exc))
        self.assertIn("No se encontró", _mensaje_error(exc))
        self.assertEqual(_mensaje_error(exc),
                         "No se encontró ese usuario de TikTok. Revisa el enlace.")

    def test_error_generico_no_es_permanente(self):
        exc = Exception("connection reset by peer")
        self.assertFalse(_es_error_permanente(exc))
        self.assertIn("No se pudo conectar", _mensaje_error(exc))

    def test_error_de_firma(self):
        exc = self._exc("SignAPIError", "sign server unavailable")
        self.assertFalse(_es_error_permanente(exc))
        self.assertEqual(_mensaje_error(exc),
                         "TikTok no responde por ahora. Espera un momento y "
                         "vuelve a intentarlo.")

    def test_404_del_servidor_de_firmas_no_es_usuario_inexistente(self):
        # httpx: «404 Not Found for url …eulerstream…». Antes, por la subcadena
        # «not found», se anunciaba usuario inexistente y se dejaba de reintentar.
        exc = self._exc("HTTPStatusError",
                        "Client error '404 Not Found' for url "
                        "'https://tiktok.eulerstream.com/webcast/sign_url'")
        self.assertFalse(_es_error_permanente(exc))
        self.assertNotIn("No se encontró", _mensaje_error(exc))
        self.assertEqual(_mensaje_error(exc),
                         "TikTok no responde por ahora. Espera un momento y "
                         "vuelve a intentarlo.")

    def test_error_http_generico_es_transitorio(self):
        exc = self._exc("HTTPStatusError",
                        "Client error '404 Not Found' for url 'https://www.tiktok.com/x'")
        self.assertFalse(_es_error_permanente(exc))
        self.assertIn("TikTok devolvió un error: ", _mensaje_error(exc))

    def test_la_subcadena_sola_no_hace_permanente_un_error(self):
        self.assertFalse(_es_error_permanente(Exception("user not found")))
        self.assertFalse(_es_error_permanente(Exception("stream offline")))


class TestLimiteConsultas(unittest.TestCase):
    """TikTok frena las consultas seguidas con 403 y cuerpo vacío."""

    def _http(self, codigo):
        exc = type("HTTPStatusError", (Exception,), {})(
            f"Client error '{codigo}' for url 'https://www.tiktok.com/x'")
        exc.response = types.SimpleNamespace(status_code=codigo)
        return exc

    def test_json_decode_es_limite(self):
        exc = json.JSONDecodeError("Expecting value", "", 0)
        self.assertTrue(errores.es_limite(exc))

    def test_contexto_failed_parse_room_id_es_limite(self):
        contexto = json.JSONDecodeError("Expecting value", "", 0)
        exc = type("FailedParseRoomIdError", (Exception,), {})("room")
        exc.__context__ = contexto
        self.assertTrue(errores.es_limite(exc))

    def test_http_403_es_limite_y_500_no(self):
        self.assertTrue(errores.es_limite(self._http(403)))
        self.assertFalse(errores.es_limite(self._http(500)))

    def test_usuario_inexistente_no_es_limite(self):
        exc = type("UserNotFoundError", (Exception,), {})("user not found")
        self.assertFalse(errores.es_limite(exc))

    def test_mensaje_con_limite(self):
        exc = json.JSONDecodeError("Expecting value", "", 0)
        self.assertFalse(_es_error_permanente(exc))
        self.assertEqual(
            _mensaje_error(exc),
            "TikTok está limitando las consultas desde esta conexión. "
            "Espera medio minuto y vuelve a intentarlo.")


class TestReconexion(unittest.TestCase):

    def _correr(self, sesion, max_intentos=3, offline_pasajero=False):
        estados = []
        with mock.patch.object(tiktok_captura, "disponible", return_value=True), \
                mock.patch.object(tiktok_captura, "_sesion", side_effect=sesion):
            tiktok_captura.capturar_con_reconexion(
                "pepe", {"max_intentos": max_intentos, "espera_entre_intentos": 0},
                threading.Event(), on_evento=lambda *a: None,
                on_estado=lambda tipo, texto: estados.append((tipo, texto)),
                offline_pasajero=offline_pasajero)
        return estados

    def _exc(self, nombre, texto=""):
        return type(nombre, (Exception,), {})(texto)

    def test_los_intentos_se_reinician_tras_cada_reconexion(self):
        caidas = [0]

        def sesion(usuario, parada, on_evento, on_estado, on_info, on_espectadores,
                   anunciar_entradas=False):
            caidas[0] += 1
            on_estado("conectado", "ok")
            if caidas[0] >= 6:
                parada.set()
            return RuntimeError("microcorte")

        estados = self._correr(sesion, max_intentos=3)
        self.assertEqual(caidas[0], 6)
        self.assertFalse(any("agotaron" in texto for _, texto in estados))

    def test_los_fallos_seguidos_si_agotan_los_intentos(self):
        def sesion(*args, **kwargs):
            return RuntimeError("no conecta")

        estados = self._correr(sesion, max_intentos=3)
        self.assertTrue(any("agotaron los 3" in texto for _, texto in estados))

    def test_offline_pasajero_reintenta_antes_de_la_primera_conexion(self):
        exc = self._exc("UserOfflineError", "user is offline")
        llamadas = [0]

        def sesion(usuario, parada, on_evento, on_estado, on_info,
                   on_espectadores, anunciar_entradas=False):
            llamadas[0] += 1
            if llamadas[0] < 3:
                return exc
            on_estado("conectado", "Conectado al directo de TikTok.")
            return None

        estados = self._correr(sesion, offline_pasajero=True)
        self.assertEqual(
            [tipo for tipo, _texto in estados],
            ["conectando", "reintentando", "conectando", "reintentando",
             "conectando", "conectado", "fin_directo"])
        self.assertEqual(llamadas[0], 3)

    def test_offline_pasajero_cuenta_los_intentos(self):
        exc = self._exc("UserOfflineError", "user is offline")

        def sesion(*args, **kwargs):
            return exc

        estados = self._correr(sesion, max_intentos=2, offline_pasajero=True)
        self.assertTrue(any("agotaron los 2" in texto for _, texto in estados))
        self.assertEqual(estados[-1][0], "error")

    def test_offline_pasajero_tras_conectar_es_permanente(self):
        exc = self._exc("UserOfflineError", "user is offline")

        def sesion(usuario, parada, on_evento, on_estado, on_info,
                   on_espectadores, anunciar_entradas=False):
            on_estado("conectado", "Conectado al directo de TikTok.")
            return exc

        estados = self._correr(sesion, offline_pasajero=True)
        self.assertEqual(estados[-1][0], "error_permanente")
        self.assertIn("no está en directo", estados[-1][1])

    def test_offline_pasajero_tras_un_corte_del_directo_es_permanente(self):
        offline = self._exc("UserOfflineError", "user is offline")
        llamadas = [0]

        def sesion(usuario, parada, on_evento, on_estado, on_info,
                   on_espectadores, anunciar_entradas=False):
            llamadas[0] += 1
            if llamadas[0] == 1:
                on_estado("conectado", "Conectado al directo de TikTok.")
                return RuntimeError("microcorte")
            return offline

        estados = self._correr(sesion, max_intentos=5, offline_pasajero=True)
        self.assertEqual(estados[-1][0], "error_permanente")
        self.assertEqual(llamadas[0], 2)

    def test_por_defecto_el_offline_sigue_siendo_permanente(self):
        exc = self._exc("UserOfflineError", "user is offline")

        def sesion(*args, **kwargs):
            return exc

        estados = self._correr(sesion)
        self.assertEqual(estados[-1],
                         ("error_permanente",
                          "Ese usuario de TikTok no está en directo ahora mismo."))

    def test_usuario_inexistente_es_permanente_con_los_dos_valores(self):
        exc = self._exc("UserNotFoundError", "user not found")

        def sesion(*args, **kwargs):
            return exc

        for offline_pasajero in (False, True):
            estados = self._correr(sesion, offline_pasajero=offline_pasajero)
            self.assertEqual(estados[-1][0], "error_permanente")

    def test_con_limite_el_reintento_espera_el_bloqueo(self):
        err = json.JSONDecodeError("Expecting value", "", 0)
        vistas = []

        def sesion(*args, **kwargs):
            vistas.append(1)
            return err

        estados = []
        parada = mock.Mock()
        parada.is_set.side_effect = lambda: len(vistas) >= 2
        with mock.patch.object(tiktok_captura, "disponible", return_value=True), \
                mock.patch.object(tiktok_captura, "_sesion", side_effect=sesion):
            tiktok_captura.capturar_con_reconexion(
                "pepe", {"max_intentos": 2, "espera_entre_intentos": 10,
                         "reconectar": True},
                parada, on_evento=lambda *a: None,
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        reintentos = [texto for tipo, texto in estados if tipo == "reintentando"]
        self.assertTrue(reintentos)
        self.assertIn(f"{errores.ESPERA_LIMITE} segundos", reintentos[0])
        self.assertEqual(parada.wait.call_args.kwargs["timeout"],
                         errores.ESPERA_LIMITE)



class TestMejorFlujo(unittest.TestCase):
    """Se prefiere el FLV: el HLS de TikTok suele dar timeout en el reproductor."""

    def test_prefiere_flv_hd_sobre_sd_y_hls(self):
        stream = {"flv_pull_url": {"HD1": "http://x/hd.flv", "SD1": "http://x/sd.flv"},
                  "hls_pull_url": "http://x/i.m3u8"}
        self.assertEqual(_mejor_flujo(stream), "http://x/hd.flv")

    def test_cae_a_sd_si_no_hay_hd(self):
        self.assertEqual(_mejor_flujo({"flv_pull_url": {"SD1": "http://x/sd.flv"}}),
                         "http://x/sd.flv")

    def test_cae_a_hls_si_no_hay_flv(self):
        self.assertEqual(_mejor_flujo({"hls_pull_url": "http://x/i.m3u8"}),
                         "http://x/i.m3u8")

    def test_rtmp_como_ultimo_recurso(self):
        self.assertEqual(_mejor_flujo({"rtmp_pull_url": "http://x/s.flv"}),
                         "http://x/s.flv")

    def test_vacio_si_no_hay_nada(self):
        self.assertEqual(_mejor_flujo({}), "")
        self.assertEqual(_mejor_flujo({"flv_pull_url": {}}), "")


class TestAutorDeEvento(unittest.TestCase):
    """Regresión del bug del wrapper .user: el autor debe leerse del proto crudo
    por su campo REAL (nick_name), sin depender del alias `nickname` ni de .user
    (que crashea con betterproto 2.0.0b7)."""

    class _UserInfoPlano:
        # Simula el `User` plano de un evento real: solo el campo real nick_name.
        def __init__(self, nick_name="", username="", ident=0):
            self.nick_name = nick_name
            self.username = username
            self.id = ident
        def __getattr__(self, n):
            # El alias `nickname` (y otros) no existe en un User plano: lanza,
            # como hace betterproto.
            raise AttributeError(n)

    class _EventoComentario:
        def __init__(self, user_info):
            self.user_info = user_info

    class _EventoUserCrash:
        # Regalo/suscripción sin user_info y con .user que revienta.
        user_info = None
        @property
        def user(self):
            raise TypeError("User.__init__() got an unexpected keyword argument 'nickName'")

    def test_lee_nick_name_real(self):
        ev = self._EventoComentario(self._UserInfoPlano(nick_name="María José", ident=7))
        nombre, ident = autor_de_evento(ev)
        self.assertEqual(nombre, "María José")
        self.assertEqual(ident, "7")

    def test_respaldo_username_si_no_hay_nick(self):
        ev = self._EventoComentario(self._UserInfoPlano(username="mariaj"))
        nombre, _ = autor_de_evento(ev)
        self.assertEqual(nombre, "mariaj")

    def test_user_que_crashea_no_tira_el_evento(self):
        # Antes esto reventaba y se perdía el evento; ahora cae a «Usuario».
        nombre, ident = autor_de_evento(self._EventoUserCrash())
        self.assertEqual(nombre, "Usuario")
        self.assertEqual(ident, "")


class TestSinEventosIniciales(unittest.TestCase):
    """Al conectar no se leen los mensajes anteriores: la llamada a
    `connect` ignora el paquete inicial de eventos."""

    class _ClienteFalso:
        room_info = {}

        def __init__(self):
            self.conexion_kwargs = {}

        def on(self, evento):
            def decorar(func):
                return func
            return decorar

        async def connect(self, **kwargs):
            self.conexion_kwargs.update(kwargs)

        async def disconnect(self):
            pass

    def _modulos_falsos(self, cliente):
        mod_eventos = types.ModuleType("TikTokLive.events")
        for nombre in ("ConnectEvent", "CommentEvent", "GiftEvent",
                       "DisconnectEvent", "LiveEndEvent", "RoomUserSeqEvent",
                       "JoinEvent", "SubscribeEvent"):
            setattr(mod_eventos, nombre, type(nombre, (), {}))
        mod_tiktok = types.ModuleType("TikTokLive")
        mod_tiktok.TikTokLiveClient = lambda unique_id: cliente
        mod_tiktok.events = mod_eventos
        return mod_tiktok, mod_eventos

    def test_connect_ignora_los_eventos_iniciales(self):
        cliente = self._ClienteFalso()
        mod_tiktok, mod_eventos = self._modulos_falsos(cliente)
        parada = threading.Event()
        parada.set()
        with mock.patch.dict(sys.modules, {"TikTokLive": mod_tiktok,
                                           "TikTokLive.events": mod_eventos}):
            error = tiktok_captura._sesion(
                "pepe", parada, lambda *a: None, None, None, None)
        self.assertIsNone(error)
        self.assertEqual(cliente.conexion_kwargs.get("process_connect_events"),
                         False)
        self.assertTrue(cliente.conexion_kwargs.get("fetch_room_info"))


class TestEsPrevioAConexion(unittest.TestCase):
    """El filtro descarta lo creado más de 5 s antes de conectar; ante la
    duda (sin hora, hora 0, sin conectar) se lee."""

    CONECTADO = 1750000000.0

    def test_previo_diez_segundos_antes_se_descarta(self):
        self.assertTrue(es_previo_a_conexion((self.CONECTADO - 10) * 1000,
                                             self.CONECTADO))

    def test_dentro_del_margen_tres_segundos_antes_se_lee(self):
        self.assertFalse(es_previo_a_conexion((self.CONECTADO - 3) * 1000,
                                              self.CONECTADO))

    def test_posterior_se_lee(self):
        self.assertFalse(es_previo_a_conexion((self.CONECTADO + 2) * 1000,
                                              self.CONECTADO))

    def test_hora_cero_se_lee(self):
        self.assertFalse(es_previo_a_conexion(0, self.CONECTADO))

    def test_hora_none_se_lee(self):
        self.assertFalse(es_previo_a_conexion(None, self.CONECTADO))

    def test_sin_conectar_se_lee(self):
        self.assertFalse(es_previo_a_conexion((self.CONECTADO - 10) * 1000,
                                              None))

    def test_frontera_exacta_del_margen_se_lee(self):
        # El descarte es estricto (<), no menor o igual.
        self.assertFalse(es_previo_a_conexion((self.CONECTADO - 5.0) * 1000,
                                              self.CONECTADO))


class TestFiltroPrevios(unittest.TestCase):
    """Tras el ConnectEvent, lo viejo no llega a on_evento y lo nuevo sí."""

    CONECTADO = 1750000000.0

    class _ClienteFalso:
        room_info = {}

        def __init__(self):
            self.manejadores = {}
            self.conexion_kwargs = {}

        def on(self, evento):
            def decorar(func):
                self.manejadores[evento] = func
                return func
            return decorar

        async def connect(self, **kwargs):
            self.conexion_kwargs.update(kwargs)

        async def disconnect(self):
            pass

    def _modulos_falsos(self, cliente):
        mod_eventos = types.ModuleType("TikTokLive.events")
        for nombre in ("ConnectEvent", "CommentEvent", "GiftEvent",
                       "DisconnectEvent", "LiveEndEvent", "RoomUserSeqEvent",
                       "JoinEvent", "SubscribeEvent"):
            setattr(mod_eventos, nombre, type(nombre, (), {}))
        mod_tiktok = types.ModuleType("TikTokLive")
        mod_tiktok.TikTokLiveClient = lambda unique_id: cliente
        mod_tiktok.events = mod_eventos
        return mod_tiktok, mod_eventos

    def _sesion_conectada(self):
        cliente = self._ClienteFalso()
        mod_tiktok, mod_eventos = self._modulos_falsos(cliente)
        recibidos = []
        parada = threading.Event()
        parada.set()
        with mock.patch.dict(sys.modules, {"TikTokLive": mod_tiktok,
                                           "TikTokLive.events": mod_eventos}):
            error = tiktok_captura._sesion(
                "pepe", parada, lambda *a: recibidos.append(a),
                lambda *a: None, lambda d: None, None)
        self.assertIsNone(error)
        with mock.patch("time.time", return_value=self.CONECTADO):
            asyncio.run(cliente.manejadores[mod_eventos.ConnectEvent](
                mod_eventos.ConnectEvent()))
        return cliente, mod_eventos, recibidos

    def _comentario(self, creado_ms, texto="hola"):
        comun = types.SimpleNamespace(create_time=creado_ms)
        autor = types.SimpleNamespace(nick_name="Pepe", id="1")
        return types.SimpleNamespace(common=comun, comment=texto,
                                     user_info=autor)

    def _regalo(self, creado_ms):
        comun = types.SimpleNamespace(create_time=creado_ms)
        autor = types.SimpleNamespace(nick_name="Pepe", id="1")
        regalo = types.SimpleNamespace(name="Rosa", diamond_count=1)
        return types.SimpleNamespace(common=comun, gift=regalo,
                                     repeat_count=1, streaking=False,
                                     user_info=autor)

    def test_comentario_viejo_no_llega_y_nuevo_si(self):
        cliente, mod_eventos, recibidos = self._sesion_conectada()
        viejo = self._comentario((self.CONECTADO - 10) * 1000, "viejo")
        nuevo = self._comentario((self.CONECTADO + 1) * 1000, "nuevo")
        asyncio.run(cliente.manejadores[mod_eventos.CommentEvent](viejo))
        self.assertEqual(recibidos, [])
        asyncio.run(cliente.manejadores[mod_eventos.CommentEvent](nuevo))
        self.assertEqual(len(recibidos), 1)
        self.assertIn("nuevo", recibidos[0][1])

    def test_regalo_viejo_no_llega(self):
        cliente, mod_eventos, recibidos = self._sesion_conectada()
        asyncio.run(cliente.manejadores[mod_eventos.GiftEvent](
            self._regalo((self.CONECTADO - 10) * 1000)))
        self.assertEqual(recibidos, [])

    def test_evento_sin_common_llega(self):
        cliente, mod_eventos, recibidos = self._sesion_conectada()
        autor = types.SimpleNamespace(nick_name="Pepe", id="1")
        sin_hora = types.SimpleNamespace(comment="sin hora", user_info=autor)
        asyncio.run(cliente.manejadores[mod_eventos.CommentEvent](sin_hora))
        self.assertEqual(len(recibidos), 1)


class TestUserSeq(unittest.TestCase):
    """La cifra de ahora es `total`; `total_user` es el acumulado que pasó."""

    class _ClienteFalso:
        room_info = {}

        def __init__(self):
            self.manejadores = {}

        def on(self, evento):
            def decorar(func):
                self.manejadores[evento] = func
                return func
            return decorar

        async def connect(self, **kwargs):
            pass

        async def disconnect(self):
            pass

    def _evento(self, *eventos):
        cliente = self._ClienteFalso()
        mod_eventos = types.ModuleType("TikTokLive.events")
        for nombre in ("ConnectEvent", "CommentEvent", "GiftEvent",
                       "DisconnectEvent", "LiveEndEvent", "RoomUserSeqEvent",
                       "JoinEvent", "SubscribeEvent"):
            setattr(mod_eventos, nombre, type(nombre, (), {}))
        mod_tiktok = types.ModuleType("TikTokLive")
        mod_tiktok.TikTokLiveClient = lambda unique_id: cliente
        mod_tiktok.events = mod_eventos
        recibidos = []
        parada = threading.Event()
        parada.set()
        with mock.patch.dict(sys.modules, {"TikTokLive": mod_tiktok,
                                           "TikTokLive.events": mod_eventos}):
            error = tiktok_captura._sesion(
                "pepe", parada, lambda *a: None, lambda *a: None,
                lambda d: None, lambda *a: recibidos.append(a))
        self.assertIsNone(error)
        for evento in eventos:
            asyncio.run(cliente.manejadores[mod_eventos.RoomUserSeqEvent](evento))
        return recibidos

    def test_entrega_los_de_ahora_y_el_acumulado(self):
        evento = types.SimpleNamespace(total=3, total_user=50)
        self.assertEqual(self._evento(evento), [(3, 50)])

    def test_la_cifra_de_ahora_puede_bajar(self):
        alto = types.SimpleNamespace(total=50, total_user=108)
        bajo = types.SimpleNamespace(total=3, total_user=108)
        self.assertEqual(self._evento(alto, bajo), [(50, 108), (3, 108)])

    def test_sin_total_no_llama(self):
        evento = types.SimpleNamespace(total=None, total_user=50)
        self.assertEqual(self._evento(evento), [])

    def test_si_el_total_falla_entrega_none(self):
        evento = types.SimpleNamespace(total=3, total_user=None)
        self.assertEqual(self._evento(evento), [(3, None)])


class TestAvisoConectado(unittest.TestCase):
    """Al conectar se avisa con el texto exacto que oye el usuario."""

    class _ClienteFalso:
        room_info = {}

        def __init__(self):
            self.manejadores = {}

        def on(self, evento):
            def decorar(func):
                self.manejadores[evento] = func
                return func
            return decorar

        async def connect(self, **kwargs):
            pass

        async def disconnect(self):
            pass

    def test_al_conectar_anuncia_conectado_con_texto_exacto(self):
        cliente = self._ClienteFalso()
        mod_eventos = types.ModuleType("TikTokLive.events")
        for nombre in ("ConnectEvent", "CommentEvent", "GiftEvent",
                       "DisconnectEvent", "LiveEndEvent", "RoomUserSeqEvent",
                       "JoinEvent", "SubscribeEvent"):
            setattr(mod_eventos, nombre, type(nombre, (), {}))
        mod_tiktok = types.ModuleType("TikTokLive")
        mod_tiktok.TikTokLiveClient = lambda unique_id: cliente
        mod_tiktok.events = mod_eventos
        estados = []
        parada = threading.Event()
        parada.set()
        with mock.patch.dict(sys.modules, {"TikTokLive": mod_tiktok,
                                           "TikTokLive.events": mod_eventos}):
            error = tiktok_captura._sesion(
                "pepe", parada, lambda *a: None,
                lambda tipo, texto: estados.append((tipo, texto)),
                lambda d: None, None)
        self.assertIsNone(error)
        asyncio.run(cliente.manejadores[mod_eventos.ConnectEvent](
            mod_eventos.ConnectEvent()))
        self.assertIn(("conectado", "Conectado al directo de TikTok."),
                      estados)


class TestFinDirecto(unittest.TestCase):
    def test_fin_del_directo_emite_fin_directo(self):
        estados = []
        parada = threading.Event()
        config = {"reconectar": True, "max_intentos": 0,
                  "espera_entre_intentos": 10,
                  "tiktok_anunciar_entradas": False}
        with mock.patch.object(tiktok_captura, "disponible",
                               return_value=True), \
                mock.patch.object(tiktok_captura, "_sesion",
                                   return_value=None):
            tiktok_captura.capturar_con_reconexion(
                "pepe", config, parada, lambda *a: None,
                on_estado=lambda *a: estados.append(a))
        self.assertIn(
            ("fin_directo", "El directo de TikTok ha terminado."), estados)
        self.assertTrue(parada.is_set())

    def test_parada_durante_la_sesion_sale_callada(self):
        estados = []
        parada = threading.Event()

        def sesion(usuario, parada, on_evento, on_estado, on_info,
                   on_espectadores, anunciar_entradas=False):
            parada.set()
            return None

        with mock.patch.object(tiktok_captura, "disponible",
                               return_value=True), \
                mock.patch.object(tiktok_captura, "_sesion",
                                   side_effect=sesion):
            tiktok_captura.capturar_con_reconexion(
                "pepe", {}, parada, lambda *a: None,
                on_estado=lambda *a: estados.append(a))
        tipos = [tipo for tipo, _texto in estados]
        self.assertEqual(tipos, ["conectando"])

    def test_fin_del_directo_no_suena_desconectado(self):
        estados = []
        parada = threading.Event()
        config = {"reconectar": True, "max_intentos": 0,
                  "espera_entre_intentos": 10,
                  "tiktok_anunciar_entradas": False}
        with mock.patch.object(tiktok_captura, "disponible",
                               return_value=True), \
                mock.patch.object(tiktok_captura, "_sesion",
                                   return_value=None):
            tiktok_captura.capturar_con_reconexion(
                "pepe", config, parada, lambda *a: None,
                on_estado=lambda *a: estados.append(a))
        tipos = [tipo for tipo, _texto in estados]
        self.assertNotIn("desconectado", tipos)


if __name__ == "__main__":
    unittest.main()

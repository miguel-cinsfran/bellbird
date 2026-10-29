import asyncio
import queue
import threading
import unittest
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import main
from tests.pseudo_prueba import con_pseudo


def _config_marcado(**extras):
    base = {
        "usuarios_silenciados": [], "palabras_silenciadas": [],
        "silenciados_ocultar": set(), "silenciados_runtime": set(),
        "silenciar_lectura": False, "limpiar_emojis": False,
        "eliminar_urls": False, "max_longitud_mensaje": 200,
        "umbral_solo_nombre": 0, "formato_prefijo": "nombre_mensaje",
        "estrategia": "todas", "tamanio_maximo": 10,
    }
    base.update(extras)
    return base


class ConexionFalsa:
    def __init__(self, *args, **kwargs):
        self.llamadas = []

    def conectar(self, url):
        self.llamadas.append(("conectar", url))

    def desconectar(self):
        self.llamadas.append(("desconectar",))


class PruebasCableadoMain(unittest.TestCase):
    def test_main_registra_el_entorno_en_un_hilo(self):
        message_box = Mock()
        ctypes_falso = types.SimpleNamespace(
            windll=types.SimpleNamespace(
                user32=types.SimpleNamespace(MessageBoxW=message_box)))
        with patch.object(main, "_verificar_instancia_unica", return_value=False), \
                patch.object(main, "configurar_logging"), \
                patch.object(main.diagnostico, "instalar_capturadores"), \
                patch.object(main.diagnostico, "registrar_entorno_en_hilo") as registrar, \
                patch.object(main.diagnostico, "registrar_entorno") as bloquear, \
                patch.dict(sys.modules, {"ctypes": ctypes_falso}), \
                patch.object(sys, "exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                main.main()

        registrar.assert_called_once_with(main.APP_VERSION)
        bloquear.assert_not_called()

    def test_main_no_registra_el_entorno_de_forma_bloqueante(self):
        message_box = Mock()
        ctypes_falso = types.SimpleNamespace(
            windll=types.SimpleNamespace(
                user32=types.SimpleNamespace(MessageBoxW=message_box)))
        with patch.object(main, "_verificar_instancia_unica", return_value=False), \
                patch.object(main, "configurar_logging"), \
                patch.object(main.diagnostico, "instalar_capturadores"), \
                patch.object(main.diagnostico, "registrar_entorno_en_hilo"), \
                patch.object(main.diagnostico, "registrar_entorno") as bloquear, \
                patch.dict(sys.modules, {"ctypes": ctypes_falso}), \
                patch.object(sys, "exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                main.main()

        bloquear.assert_not_called()

    def test_aviso_de_instancia_usa_banderas_de_primer_plano(self):
        message_box = Mock()
        ctypes_falso = types.SimpleNamespace(
            windll=types.SimpleNamespace(
                user32=types.SimpleNamespace(MessageBoxW=message_box)))

        with patch.object(main, "_verificar_instancia_unica", return_value=False), \
                patch.object(main, "configurar_logging"), \
                patch.object(main.diagnostico, "instalar_capturadores"), \
                patch.object(main.diagnostico, "registrar_entorno_en_hilo"), \
                patch.dict(sys.modules, {"ctypes": ctypes_falso}), \
                patch.object(sys, "exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                main.main()

        banderas = message_box.call_args.args[3]
        self.assertEqual(banderas, 0x40 | 0x00010000 | 0x00040000)

    def test_los_callbacks_comparten_el_registro_de_conexiones(self):
        with patch.object(main.conexion, "Conexiones", ConexionFalsa):
            conectar, desconectar = main.armar_callbacks_captura(
                object(), {}, object(), object())

        conectar("directo")
        desconectar()
        self.assertIs(conectar.__self__, desconectar.__self__)
        self.assertEqual(conectar.__self__.llamadas,
                         [("conectar", "directo"), ("desconectar",)])

    def test_iniciar_interfaz_cierra_sonidos_sin_marcar_limpio_al_volver(self):
        orden = []
        conectar = object()
        desconectar = object()

        def armar(*args):
            orden.append("callbacks")
            return conectar, desconectar

        def iniciar(**kwargs):
            orden.append(("gui", kwargs["iniciar_captura_cb"],
                          kwargs["detener_captura_cb"]))

        with patch.object(main, "armar_callbacks_captura", side_effect=armar), \
                patch.object(main.diagnostico, "registrar_cierre_fallos",
                             side_effect=lambda: orden.append("cierre")), \
                patch.object(main._snd, "cerrar", side_effect=lambda: orden.append("sonido")):
            main.iniciar_interfaz({}, object(), object(), object(), object(), iniciar)

        self.assertEqual(orden, ["callbacks", ("gui", conectar, desconectar),
                                 "sonido"])
        self.assertNotIn("cierre", orden)

    def test_iniciar_interfaz_no_duplica_marca_limpia_y_cierra_sonidos(self):
        conectar = object()
        desconectar = object()
        registro = Mock()

        def gui_falsa(**kwargs):
            registro()

        def armar(*a):
            return conectar, desconectar

        with patch.object(main, "armar_callbacks_captura", side_effect=armar), \
                patch.object(main.diagnostico, "registrar_cierre_fallos", registro), \
                patch.object(main._snd, "cerrar") as cerrar:
            main.iniciar_interfaz({}, object(), object(), object(), object(), gui_falsa)

        self.assertEqual(registro.call_count, 1)
        cerrar.assert_called_once_with()


class PruebasReconexion(unittest.TestCase):
    def _config(self, max_intentos=3):
        return {"reconectar": True, "max_intentos": max_intentos,
                "espera_entre_intentos": 0}

    def _correr(self, captura, config, terminado=False):
        estados = []
        with patch.object(main, "_captura", side_effect=captura), \
                patch.object(main, "_directo_terminado",
                             return_value=terminado), \
                patch.object(main._snd, "reproducir"):
            main.captura_con_reconexion(
                "v", queue.Queue(), config, threading.Event(), main.Stats(),
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        return estados

    def test_los_intentos_se_reinician_tras_cada_reconexion(self):
        caidas = [0]

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            # Cada intento conecta, lee una vuelta y luego sufre un microcorte.
            caidas[0] += 1
            on_estado("conectado", "ok")
            on_estado("leido", "ok")
            if caidas[0] >= 6:
                parada.set()
            return RuntimeError("microcorte")

        estados = self._correr(captura, self._config(max_intentos=3))
        self.assertEqual(caidas[0], 6)
        self.assertFalse(any("agotaron" in texto for _, texto in estados))
        # Y el aviso de reintento vuelve a contar desde 1 cada vez.
        reintentos = [texto for tipo, texto in estados if tipo == "reintentando"]
        self.assertTrue(all("(intento 1 de 3)" in texto for texto in reintentos))

    def test_los_fallos_seguidos_si_agotan_los_intentos(self):
        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            return RuntimeError("no conecta")

        estados = self._correr(captura, self._config(max_intentos=3))
        self.assertTrue(any("agotaron los 3" in texto for _, texto in estados))

    def test_aviso_de_reintento_con_maximo_pasa_la_plantilla_entera(self):
        # La plantilla con {total} tiene que entrar entera en _(): el
        # fragmento " de N" pegado fuera no lo puede ordenar un traductor.
        anotados = []

        def guion(texto):
            anotados.append(texto)
            return texto

        llamadas = []

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            llamadas.append(1)
            if len(llamadas) > 1:
                parada.set()
                return None
            on_estado("conectado", "ok")
            on_estado("leido", "ok")
            return RuntimeError("microcorte")

        estados = []
        with patch.object(main, "_", side_effect=guion), \
                patch.object(main, "_captura", side_effect=captura), \
                patch.object(main, "_directo_terminado", return_value=False), \
                patch.object(main._snd, "reproducir"):
            main.captura_con_reconexion(
                "v", queue.Queue(), self._config(max_intentos=3),
                threading.Event(), main.Stats(),
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        self.assertIn(
            "Se perdió la conexión con el chat. Reintentando en {segundos} "
            "{unidad} (intento {intento} de {total}).", anotados)

    def test_conectado_sin_leido_no_reinicia_los_intentos(self):
        caidas = [0]

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            # «conectado» ya no cuenta como lectura: sin «leido», el contador
            # no se reinicia y el límite de intentos se cumple.
            caidas[0] += 1
            on_estado("conectado", "ok")
            if caidas[0] >= 6:      # tope para no colgarse si el arreglo cae
                parada.set()
            return RuntimeError("corte")

        estados = self._correr(captura, self._config(max_intentos=3))
        self.assertEqual(caidas[0], 3)
        self.assertIn(("error", "Se agotaron los 3 intentos de reconexión."),
                      estados)

    def test_captura_cierra_el_loop_de_asyncio_de_cada_intento(self):
        loops = []

        def en_loop(*args, **kwargs):
            loops.append(asyncio.get_event_loop())
            return None

        with patch.object(main, "_captura_en_loop", side_effect=en_loop):
            main._captura("v", queue.Queue(), {}, threading.Event(), main.Stats())
            main._captura("v", queue.Queue(), {}, threading.Event(), main.Stats())
        self.assertEqual(len(loops), 2)
        self.assertIsNot(loops[0], loops[1])
        self.assertTrue(all(loop.is_closed() for loop in loops))


class _Parada:
    """Parada de prueba: registra las esperas y nunca duerme."""

    def __init__(self):
        self.puesta = False
        self.esperas = []

    def is_set(self):
        return self.puesta

    def set(self):
        self.puesta = True

    def wait(self, timeout=None):
        self.esperas.append(timeout)


class PruebasReconexionSinCerrarSesion(unittest.TestCase):

    def _config(self):
        return {"reconectar": True, "max_intentos": 0,
                "espera_entre_intentos": 15}

    def _correr(self, captura):
        estados = []
        parada = _Parada()
        with patch.object(main, "_captura", side_effect=captura), \
                patch.object(main, "_directo_terminado", return_value=False), \
                patch.object(main._snd, "reproducir"):
            main.captura_con_reconexion(
                "v", queue.Queue(), self._config(), parada, main.Stats(),
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        return estados, parada

    def test_un_corte_con_reintento_no_cierra_la_sesion(self):
        llamadas = []

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            llamadas.append(1)
            on_estado("conectando", "Conectando al directo...")
            if len(llamadas) == 1:
                on_estado("conectado", "Conectado. Esperando mensajes...")
                on_estado("leido", "Chat en lectura.")
                on_estado("error_conexion", "Se perdió la conexión.")
                return RuntimeError("corte")
            on_estado("conectado", "Conectado. Esperando mensajes...")
            on_estado("leido", "Chat en lectura.")
            parada.set()
            return None

        estados, parada = self._correr(captura)
        tipos = [tipo for tipo, _ in estados]
        self.assertNotIn("desconectado", tipos)
        self.assertNotIn("error", tipos)
        self.assertEqual(tipos.count("conectando"), 1)
        self.assertEqual(
            [texto for tipo, texto in estados if tipo == "reintentando"],
            ["Se perdió la conexión con el chat. Reintentando en 1 segundo "
             "(intento 1)."])
        indice = tipos.index("reintentando")
        self.assertEqual(tipos[indice + 1:indice + 2], ["reconectado"])
        self.assertEqual(dict(estados)["reconectado"], "Chat reconectado.")
        self.assertEqual(parada.esperas, [1])

    def test_el_primer_conectado_de_la_sesion_llega_tal_cual(self):
        llamadas = []

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            llamadas.append(1)
            on_estado("conectando", "Conectando al directo...")
            if len(llamadas) == 1:
                on_estado("error_conexion", "Se perdió la conexión.")
                return RuntimeError("corte")
            on_estado("conectado", "Conectado. Esperando mensajes...")
            on_estado("leido", "Chat en lectura.")
            parada.set()
            return None

        estados, _ = self._correr(captura)
        tipos = [tipo for tipo, _ in estados]
        self.assertEqual(tipos.count("conectando"), 2)
        self.assertIn("conectado", tipos)
        self.assertNotIn("reconectado", tipos)

    def test_las_esperas_de_tres_cortes_son_uno_dos_y_cinco(self):
        llamadas = []

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            llamadas.append(1)
            if len(llamadas) <= 3:
                on_estado("error_conexion", "corte")
                return RuntimeError("corte")
            on_estado("leido", "Chat en lectura.")
            parada.set()
            return None

        estados, parada = self._correr(captura)
        self.assertEqual(parada.esperas, [1, 2, 5])
        textos = [texto for tipo, texto in estados if tipo == "reintentando"]
        self.assertIn("en 1 segundo (intento 1)", textos[0])
        self.assertIn("en 2 segundos (intento 2)", textos[1])


class _Lote:
    def __init__(self, items):
        self.items = items

    def sync_items(self):
        return self.items


class _ChatFalso:
    def __init__(self, items):
        self.items = items
        self.vivo = True

    def is_alive(self):
        return self.vivo

    def get(self):
        self.vivo = False
        return _Lote(self.items)

    def raise_for_status(self):
        return None


class PruebasFiltroReconexion(unittest.TestCase):

    def test_dos_intentos_comparten_el_filtro_de_la_sesion(self):
        futuro = int(
            (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1_000)
        creados = []
        corte = []

        def item(ident, mensaje, ts):
            return types.SimpleNamespace(
                id=ident, timestamp=ts, message=mensaje,
                author=types.SimpleNamespace(name="Ana", channelId="canal"),
                type="textMessage", amountString="")

        def crear(**_kwargs):
            if not creados:
                creados.append(1)
                return _ChatFalso([item("uno", "X", futuro)])
            base = corte[0] if corte else datetime.now(timezone.utc)
            entre = int((base + timedelta(seconds=1)).timestamp() * 1_000)
            return _ChatFalso([item("uno", "X", futuro),
                               item("dos", "Y", entre)])

        procesados = []
        parada = _Parada()

        def procesar(autor, mensaje, tipo, monto, canal_id, cola, config, stats,
                     on_message=None, sesion_activa=None, rol=""):
            if mensaje == "X" and not corte:
                corte.append(datetime.now(timezone.utc))
            procesados.append(mensaje)
            if mensaje == "Y":
                parada.set()

        config = {"reconectar": True, "max_intentos": 0,
                  "espera_entre_intentos": 15}
        with patch.dict(sys.modules,
                        {"pytchat": types.SimpleNamespace(create=crear)}), \
                patch.object(main, "_cliente_pytchat",
                             return_value=Mock(close=lambda: None)), \
                patch.object(main, "procesar_entrante", side_effect=procesar), \
                patch.object(main, "_directo_terminado", return_value=False), \
                patch.object(main._snd, "reproducir"):
            main.captura_con_reconexion("v", queue.Queue(), config, parada,
                                        main.Stats())

        self.assertEqual(procesados, ["X", "Y"])

    def test_la_captura_anota_tipo_y_monto_sin_autor_ni_mensaje(self):
        futuro = int(
            (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1_000)
        item = types.SimpleNamespace(
            id="uno", timestamp=futuro, message="mensaje privado de Ana",
            author=types.SimpleNamespace(name="Ana", channelId="canal"),
            type="superChat", amountString="$5")
        parada = _Parada()

        def procesar(autor, mensaje, tipo, monto, canal_id, cola, config, stats,
                     on_message=None, sesion_activa=None, rol=""):
            parada.set()

        config = {"reconectar": True, "max_intentos": 0,
                  "espera_entre_intentos": 15}
        with patch.dict(sys.modules,
                        {"pytchat": types.SimpleNamespace(
                            create=lambda **_kwargs: _ChatFalso([item]))}), \
                patch.object(main, "_cliente_pytchat",
                             return_value=Mock(close=lambda: None)), \
                patch.object(main, "procesar_entrante", side_effect=procesar), \
                patch.object(main, "_directo_terminado", return_value=False), \
                patch.object(main._snd, "reproducir"), \
                self.assertLogs(main.logger, level="DEBUG") as registro:
            main.captura_con_reconexion("v", queue.Queue(), config, parada,
                                        main.Stats())

        eventos = [linea for linea in registro.output if "YOUTUBE_EVENTO" in linea]
        self.assertEqual(
            eventos,
            ["DEBUG:ytchat.main:YOUTUBE_EVENTO tipo=superchat monto=$5"])
        self.assertNotIn("Ana", "".join(registro.output))
        self.assertNotIn("mensaje privado", "".join(registro.output))



class PruebasInfoVideoCancelable(unittest.TestCase):
    def test_no_encadena_mas_pasos_si_la_sesion_ya_no_vale(self):
        modulo = types.SimpleNamespace(YoutubeDL=Mock(side_effect=RuntimeError("fallo")))
        with patch.dict(sys.modules, {"yt_dlp": modulo}), \
                patch.object(main.ytdlp_bin, "info_video") as ejecutable, \
                patch.object(main, "_descargar_watch") as respaldo:
            titulo, tipo, metadatos = main.obtener_info_video(
                "A" * 11, sesion_activa=lambda: False)
        ejecutable.assert_not_called()
        respaldo.assert_not_called()
        self.assertEqual((titulo, tipo, metadatos), ("", main.deteccion.DESCONOCIDO, {}))

    def test_sesion_vigente_sigue_la_cadena_completa(self):
        modulo = types.SimpleNamespace(YoutubeDL=Mock(side_effect=RuntimeError("fallo")))
        with patch.dict(sys.modules, {"yt_dlp": modulo}), \
                patch.object(main.ytdlp_bin, "info_video", return_value=None) as ejecutable, \
                patch.object(main, "_descargar_watch", return_value="") as respaldo, \
                patch.object(main, "_clasificar_por_api", return_value=main.deteccion.DESCONOCIDO):
            main.obtener_info_video("A" * 11, sesion_activa=lambda: True)
        ejecutable.assert_called_once()
        respaldo.assert_called_once()


class TestCableadoClasificarPorApi(unittest.TestCase):
    def test_clasificar_por_api_usa_credenciales_efectivas(self):
        construidos = []

        class LecturaFalsa:
            def videos(self):
                return self

            def list(self, **kwargs):
                return self

            def execute(self):
                return {"items": [{"snippet": {"liveBroadcastContent": "live"}}]}

        class ClienteRegistra:
            def __init__(self, credenciales):
                construidos.append(credenciales)

            def _lectura(self):
                return LecturaFalsa()

        credenciales_falso = types.SimpleNamespace(
            hay_lectura=lambda: True,
            cargar=lambda: {"origen": "cargar"},
            efectivas=lambda *a, **k: {"origen": "efectivas"})
        youtube_api_falso = types.SimpleNamespace(
            google_disponible=lambda: True, ClienteYouTube=ClienteRegistra)
        # `from ytchat.youtube import x` mira primero el atributo del paquete:
        # sin estos parches usaría el módulo real si otra prueba ya lo importó.
        from ytchat import youtube as _paquete_youtube
        with patch.dict(sys.modules, {"ytchat.youtube.credenciales": credenciales_falso,
                                       "ytchat.youtube.youtube_api": youtube_api_falso}), \
                patch.object(_paquete_youtube, "credenciales",
                             credenciales_falso, create=True), \
                patch.object(_paquete_youtube, "youtube_api",
                             youtube_api_falso, create=True):
            tipo = main._clasificar_por_api("A" * 11)
        self.assertEqual(tipo, main.deteccion.LIVE)
        self.assertEqual(construidos, [{"origen": "efectivas"}])


class PruebasPseudoTTS(unittest.TestCase):
    def _tts(self, tipo, mensaje="", monto="", config=None, **kwargs):
        cola = queue.Queue()
        main.procesar_entrante(
            "Ana", mensaje, tipo, monto, "canal", cola,
            config if config is not None else _config_marcado(),
            main.Stats(), on_message=lambda *a, **k: None, **kwargs)
        return cola.get_nowait()["texto_tts"]

    def test_superchat_con_mensaje_marcado(self):
        with con_pseudo():
            texto = self._tts(main.TIPO_SUPERCHAT, "hola", "$5")
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_superchat_sin_mensaje_marcado(self):
        with con_pseudo():
            texto = self._tts(main.TIPO_SUPERCHAT, "", "$5")
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_etiqueta_de_otro_modulo_marcada(self):
        # «Regalo» la arma conexion.py: acá solo se exige que el texto
        # entero salga marcado; traducirla es de ese módulo.
        with con_pseudo():
            texto = self._tts(main.TIPO_SUPERCHAT, "hola", "$5",
                               etiqueta_monto="Regalo")
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_eventos_de_entrada_marcados(self):
        config = _config_marcado(tiktok_aviso_entradas="leer")
        with con_pseudo():
            textos = [
                self._tts(main.TIPO_MIEMBRO, ""),
                self._tts(main.TIPO_ENTRADA, "", config=config),
                self._tts(main.TIPO_SEGUIR, ""),
                self._tts(main.TIPO_COMPARTIR, ""),
                self._tts(main.TIPO_COFRE, ""),
            ]
        for texto in textos:
            self.assertTrue(texto.startswith("[¡"), texto)

    def test_me_gusta_con_y_sin_monto_marcado(self):
        config = _config_marcado(tiktok_aviso_me_gusta="leer")
        with con_pseudo():
            con_monto = self._tts(main.TIPO_ME_GUSTA, "", "15",
                                   config=config)
            sin_monto = self._tts(main.TIPO_ME_GUSTA, "", "",
                                   config=config)
        self.assertTrue(con_monto.startswith("[¡"), con_monto)
        self.assertTrue(sin_monto.startswith("[¡"), sin_monto)

    def test_sin_nombre_marcado(self):
        cola = queue.Queue()
        cola.put({"texto_tts": "anterior", "autor": "Otro"})
        config = _config_marcado(umbral_solo_nombre=1)
        with con_pseudo():
            main.procesar_entrante(
                "", "hola", main.TIPO_TEXTO, "", "canal", cola, config,
                main.Stats(), on_message=lambda *a, **k: None)
            texto = cola.get_nowait()["texto_tts"]
            texto = cola.get_nowait()["texto_tts"]
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_mensaje_comun_marcado(self):
        with con_pseudo():
            texto = self._tts(main.TIPO_TEXTO, "hola")
        self.assertTrue(texto.startswith("[¡"), texto)


class _ChatQueFalla:
    def __init__(self):
        self.vivo = True

    def is_alive(self):
        return self.vivo

    def get(self):
        raise RuntimeError("corte")

    def raise_for_status(self):
        return None


class _ChatUnLote:
    def __init__(self, items):
        self.items = items
        self.vivo = True

    def is_alive(self):
        return self.vivo

    def get(self):
        self.vivo = False
        return _Lote(self.items)

    def raise_for_status(self):
        return None


def _item(ident, mensaje):
    futuro = int(
        (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1_000)
    return types.SimpleNamespace(
        id=ident, timestamp=futuro, message=mensaje,
        author=types.SimpleNamespace(name="Ana", channelId="canal"),
        type="textMessage", amountString="")


class PruebasPseudoCaptura(unittest.TestCase):
    def _correr(self, captura, config, terminado=False):
        estados = []
        with patch.object(main, "_captura", side_effect=captura), \
                patch.object(main, "_directo_terminado",
                             return_value=terminado), \
                patch.object(main._snd, "reproducir"):
            main.captura_con_reconexion(
                "v", queue.Queue(), config, threading.Event(), main.Stats(),
                on_estado=lambda tipo, texto: estados.append((tipo, texto)))
        return estados

    def _config(self, max_intentos=3):
        return {"reconectar": True, "max_intentos": max_intentos,
                "espera_entre_intentos": 0}

    def test_reconexion_desactivada_marcada(self):
        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            return RuntimeError("corte")

        estados = self._correr(
            captura, {"reconectar": False, "max_intentos": 3,
                      "espera_entre_intentos": 0})
        self.assertEqual(len(estados), 1)
        self.assertEqual(estados[0][0], "error")
        with con_pseudo():
            estados = self._correr(
                captura, {"reconectar": False, "max_intentos": 3,
                          "espera_entre_intentos": 0})
        self.assertTrue(estados[0][1].startswith("[¡"), estados[0][1])

    def test_error_permanente_marcado(self):
        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            return RuntimeError("private video")

        with con_pseudo():
            estados = self._correr(captura, self._config())
        self.assertEqual(estados[0][0], "error_permanente")
        self.assertTrue(estados[0][1].startswith("[¡"), estados[0][1])

    def test_directo_terminado_marcado(self):
        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            return RuntimeError("corte")

        with con_pseudo():
            estados = self._correr(captura, self._config(), terminado=True)
        self.assertEqual(estados[0][0], "error_permanente")
        self.assertTrue(estados[0][1].startswith("[¡"), estados[0][1])

    def test_intentos_agotados_marcado(self):
        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            return RuntimeError("no conecta")

        with con_pseudo():
            estados = self._correr(captura, self._config(max_intentos=1))
        textos = [texto for tipo, texto in estados if tipo == "error"]
        self.assertEqual(len(textos), 1)
        self.assertTrue(textos[0].startswith("[¡"), textos[0])

    def test_reintento_marcado(self):
        llamadas = []

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            llamadas.append(1)
            if len(llamadas) > 1:
                parada.set()
                return None
            return RuntimeError("corte")

        with con_pseudo():
            estados = self._correr(captura, self._config(max_intentos=0))
        textos = [texto for tipo, texto in estados if tipo == "reintentando"]
        self.assertEqual(len(textos), 1)
        self.assertTrue(textos[0].startswith("[¡"), textos[0])

    def test_reconectado_marcado(self):
        llamadas = []

        def captura(video_id, cola, cfg, parada, stats, on_message, on_estado,
                    sesion_activa, filtro=None):
            llamadas.append(1)
            on_estado("conectado", "Conectado. Esperando mensajes...")
            on_estado("leido", "Chat en lectura.")
            if len(llamadas) > 1:
                parada.set()
                return None
            return RuntimeError("corte")

        with con_pseudo():
            estados = self._correr(captura, self._config(max_intentos=0))
        self.assertTrue(dict(estados)["reconectado"].startswith("[¡"),
                        dict(estados)["reconectado"])

    def test_error_amigable_marcado(self):
        casos = ["Invalid video id: x", "cannot find channel id",
                 "private video", "members only", "finished",
                 "does not exist", "otro fallo"]
        with con_pseudo():
            textos = [main._mensaje_error_amigable(RuntimeError(caso))
                      for caso in casos]
        self.assertEqual(len(textos), 7)
        for texto in textos:
            self.assertTrue(texto.startswith("[¡"), texto)

    def test_conexion_y_demasiados_errores_marcados(self):
        estados = []
        chat = _ChatQueFalla()
        with patch.dict(sys.modules, {"pytchat": types.SimpleNamespace(
                create=lambda **_kwargs: chat)}), \
                patch.object(main, "_cliente_pytchat",
                             return_value=Mock(close=lambda: None)), \
                patch.object(main._snd, "reproducir"), \
                con_pseudo():
            main._captura_en_loop(
                "v", queue.Queue(), {}, threading.Event(), main.Stats(),
                None, lambda tipo, texto: estados.append((tipo, texto)),
                None)
        self.assertEqual([tipo for tipo, _ in estados],
                         ["conectando", "conectado", "error_conexion"])
        for _, texto in estados:
            self.assertTrue(texto.startswith("[¡"), texto)

    def test_lectura_marcada(self):
        estados = []
        chat = _ChatUnLote([_item("uno", "hola")])
        with patch.dict(sys.modules, {"pytchat": types.SimpleNamespace(
                create=lambda **_kwargs: chat)}), \
                patch.object(main, "_cliente_pytchat",
                             return_value=Mock(close=lambda: None)), \
                patch.object(main._snd, "reproducir"), \
                con_pseudo():
            main._captura_en_loop(
                "v", queue.Queue(), _config_marcado(), threading.Event(),
                main.Stats(), None,
                lambda tipo, texto: estados.append((tipo, texto)), None)
        vistos = dict(estados)
        self.assertTrue(vistos["leido"].startswith("[¡"), vistos["leido"])

    def test_fallo_de_video_marcado(self):
        from ytchat.core import avisos_red
        captados = []
        falso = types.SimpleNamespace(
            anunciar=lambda texto, urgente=True: captados.append(texto))
        with con_pseudo(), patch.dict(
                sys.modules, {"ytchat.ui.accesibilidad": falso}):
            fallo = avisos_red.mensaje_de_fallo("timeout")
            main._anunciar_fallo_video(
                {"fallo": fallo}, lambda f, arg: f(arg))
        self.assertEqual(len(captados), 1)
        self.assertTrue(captados[0].startswith("[¡"), captados[0])

    def test_sin_fallo_no_anuncia(self):
        anunciar = Mock()
        with patch.dict(sys.modules, {"ytchat.ui.accesibilidad":
                        types.SimpleNamespace(anunciar=anunciar)}):
            main._anunciar_fallo_video(
                {}, lambda f, arg: f(arg))
        anunciar.assert_not_called()


class PruebasPseudoCuadros(unittest.TestCase):
    def _ctypes_con_caja(self, captados):
        def caja(hwnd, texto, titulo, tipo):
            captados.append((texto, titulo))
            return 0
        return types.SimpleNamespace(
            windll=types.SimpleNamespace(
                user32=types.SimpleNamespace(MessageBoxW=caja)))

    def test_aviso_de_instancia_marcado(self):
        captados = []
        with con_pseudo(), \
                patch.object(main, "_verificar_instancia_unica",
                             return_value=False), \
                patch.object(main, "configurar_logging"), \
                patch.object(main.diagnostico, "instalar_capturadores"), \
                patch.object(main.diagnostico, "registrar_entorno_en_hilo"), \
                patch.dict(sys.modules,
                           {"ctypes": self._ctypes_con_caja(captados)}), \
                patch.object(sys, "exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                main.main()
        self.assertEqual(len(captados), 1)
        self.assertTrue(captados[0][0].startswith("[¡"), captados[0][0])
        self.assertEqual(captados[0][1], main.APP_NAME)

    def _obra_guesa(self, espera):
        class ObreroFalso:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                pass

            def esperar_inicio(self, timeout=None):
                return espera
        return ObreroFalso

    def _base_voz(self, captados, espera):
        return [
            patch.object(main, "_verificar_instancia_unica",
                         return_value=True),
            patch.object(main, "configurar_logging"),
            patch.object(main.diagnostico, "instalar_capturadores"),
            patch.object(main.diagnostico, "registrar_entorno_en_hilo"),
            patch.object(main, "cargar_configuracion", return_value={}),
            patch.object(main, "cargar_sonidos", return_value={}),
            patch.object(main.alias, "usar"),
            patch.object(main.alias, "cargar", return_value={}),
            patch.object(main._snd, "cargar"),
            patch.object(main._snd, "reproducir"),
            patch.object(main, "TTSWorker", self._obra_guesa(espera)),
            patch.dict(sys.modules,
                       {"ctypes": self._ctypes_con_caja(captados)}),
            patch.object(sys, "exit", side_effect=SystemExit(0)),
        ]

    def test_motor_de_voz_marcado(self):
        captados = []
        parches = self._base_voz(captados, False)
        with con_pseudo():
            for parche in parches:
                parche.start()
            try:
                with self.assertRaises(SystemExit):
                    main.main()
            finally:
                for parche in reversed(parches):
                    parche.stop()
        self.assertEqual(len(captados), 1)
        self.assertTrue(captados[0][0].startswith("[¡"), captados[0][0])
        self.assertEqual(captados[0][1], main.APP_NAME)

    def test_wx_faltante_marcado(self):
        captados = []
        parches = self._base_voz(captados, True)
        with con_pseudo(), patch.dict(sys.modules, {"wx": None}):
            for parche in parches:
                parche.start()
            try:
                with self.assertRaises(SystemExit):
                    main.main()
            finally:
                for parche in reversed(parches):
                    parche.stop()
        self.assertEqual(len(captados), 1)
        self.assertTrue(captados[0][0].startswith("[¡"), captados[0][0])
        self.assertEqual(captados[0][1], main.APP_NAME)


if __name__ == "__main__":
    unittest.main()

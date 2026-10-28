"""Pruebas del supervisor de la transmisión con dobles.

Sin ventanas, sin red y sin dormir de verdad: el gestor es falso, las
esperas son falsas y el reloj y el dormir son falsos. Lo único real es el
hilo, que se espera por sondeo con un plazo corto.
"""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from ytchat.capture.tiktok_vivo import ResultadoEspera
from ytchat.obs import obs_cliente
from ytchat.obs import obs_panel
from ytchat.obs import obs_supervisor
from ytchat.obs.obs_supervisor import SupervisorTransmision, duracion_legible
from ytchat.youtube import emision
from ytchat.youtube import fin_pendiente


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.ahora += segundos


def muestra(activa=True, duracion=0, perdidos=0, totales=0,
            reconectando=False):
    return {"outputActive": activa, "outputDuration": duracion,
            "outputSkippedFrames": perdidos, "outputTotalFrames": totales,
            "outputReconnecting": reconectando}


class GestorFalso:
    """Doble de GestorPanelObs con estados enlatados para la vigilancia."""

    def __init__(self, estados=None, fallo=None, estadisticas=None):
        self.estados = list(estados or [muestra(False)])
        self.fallo = fallo
        self.llamadas = []
        self.conectado = False
        self.cerrado = 0
        self._cliente = self
        self.indice = 0
        self.estadisticas_muestras = list(estadisticas or [{}])
        self.indice_estadisticas = 0

    def conectar(self, parada=None):
        self.llamadas.append("conectar")
        if self.fallo == "conectar":
            raise RuntimeError("boom al conectar")
        self.conectado = True

    def iniciar_transmision(self, parada=None):
        self.llamadas.append("iniciar")
        if self.fallo == "iniciar":
            raise RuntimeError("boom al iniciar")

    def detener_transmision(self, parada=None):
        self.llamadas.append("detener")

    def estado_transmision(self, parada=None):
        self.llamadas.append("estado")
        if self.fallo == "estado":
            raise RuntimeError("boom en estado")
        indice = min(self.indice, len(self.estados) - 1)
        self.indice += 1
        return dict(self.estados[indice])

    def estadisticas(self, parada=None):
        self.llamadas.append("estadisticas")
        if self.fallo == "estadisticas":
            raise RuntimeError("boom en estadisticas")
        indice = min(self.indice_estadisticas,
                     len(self.estadisticas_muestras) - 1)
        self.indice_estadisticas += 1
        return dict(self.estadisticas_muestras[indice])

    def pedir(self, tipo, datos=None, parada=None):
        return {"responseData": {}}

    def cerrar(self):
        self.cerrado += 1


def esperar_condicion(condicion, plazo=2.0):
    inicio = time.monotonic()
    while time.monotonic() - inicio < plazo:
        if condicion():
            return True
        time.sleep(0.005)
    return bool(condicion())


class BaseSupervisor(unittest.TestCase):
    def armar(self, destino="TikTok", usuario="amigo",
              estados=None, fallo=None, veredicto="enviando",
              en_vivo=True, sin_directos=False, intervalo=1000.0,
              estadisticas=None):
        reloj = RelojFalso()
        anuncios = []
        chats = []
        gestores = []
        llamadas_salida = []
        llamadas_vivo = []

        def crear_gestor():
            gestor = GestorFalso(estados, fallo, estadisticas)
            gestores.append(gestor)
            return gestor

        def esperar_salida(cliente, parada=None):
            llamadas_salida.append(parada)
            return veredicto

        def esperar_en_vivo(usuario_pedido, parada=None, limite=None):
            llamadas_vivo.append((usuario_pedido, limite))
            return ResultadoEspera(en_vivo, sin_directos)

        supervisor = SupervisorTransmision(
            destino, usuario,
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=chats.append,
            crear_gestor=crear_gestor,
            esperar_salida=esperar_salida,
            esperar_en_vivo=esperar_en_vivo,
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=intervalo,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        return (supervisor, anuncios, chats, gestores, llamadas_salida,
                llamadas_vivo, reloj)

    def iniciar_y_esperar_fin(self, supervisor, plazo=2.0):
        supervisor.iniciar()
        terminado = esperar_condicion(lambda: not supervisor.activo,
                                      plazo)
        self.assertTrue(terminado, "el hilo no terminó a tiempo")
        # El join ya lo hizo el hilo al terminar; este remata por si acaso.
        hilo = supervisor._hilo
        if hilo is not None:
            hilo.join(1.0)


class CaminoFelizTest(BaseSupervisor):
    def test_tiktok_feliz_con_orden_exactoy_url(self):
        armado = self.armar(estados=[muestra(False)])
        supervisor, anuncios, chats, gestores, _, vivo, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios, [
            ("Comenzando la transmisión.", "conectando"),
            ("OBS está enviando la señal a Restream.", "conectado"),
            ("Esperando a que TikTok muestre el directo.", None),
            ("Tu directo de TikTok ya está al aire.", "al_aire"),
        ])
        self.assertEqual(chats, ["https://www.tiktok.com/@amigo/live"])
        self.assertEqual(vivo, [("amigo", 120.0)])
        self.assertEqual(gestores[0].llamadas[:2],
                         ["conectar", "iniciar"])
        self.assertEqual(gestores[0].cerrado, 1)


class SalidaFallidaTest(BaseSupervisor):
    def test_salida_que_falla_no_espera_a_tiktok(self):
        armado = self.armar(veredicto="sin_salida")
        supervisor, anuncios, chats, _, _, vivo, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios, [
            ("Comenzando la transmisión.", "conectando"),
            ("OBS no empezó a transmitir.", "transmision_problema"),
        ])
        self.assertEqual(chats, [])
        self.assertEqual(vivo, [])


class TikTokAusenteTest(BaseSupervisor):
    def test_cuenta_sin_directos(self):
        armado = self.armar(en_vivo=False, sin_directos=True,
                            estados=[muestra(False)])
        supervisor, anuncios, chats, _, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(chats, [])
        self.assertEqual(anuncios[0],
                         ("Comenzando la transmisión.", "conectando"))
        self.assertEqual(anuncios[1][1], "conectado")
        self.assertEqual(anuncios[2],
                         ("Esperando a que TikTok muestre el directo.", None))
        self.assertEqual(anuncios[3], (
            "OBS está transmitiendo, pero TikTok todavía no muestra "
            "ningún directo de amigo. Revisa que en Restream esté "
            "activado TikTok.", "transmision_problema"))

    def test_sin_noticia_del_directo(self):
        armado = self.armar(en_vivo=False, sin_directos=False,
                            estados=[muestra(False)])
        supervisor, anuncios, chats, _, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(chats, [])
        self.assertEqual(anuncios[-1], (
            "OBS está transmitiendo, pero TikTok todavía no muestra "
            "el directo.", "transmision_problema"))


class DestinoYouTubeTest(BaseSupervisor):
    def test_youtube_no_espera_a_tiktok(self):
        armado = self.armar(destino="YouTube", estados=[muestra(False)])
        supervisor, anuncios, chats, _, _, vivo, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios, [
            ("Comenzando la transmisión.", "conectando"),
            ("OBS está enviando la señal a YouTube.", "conectado"),
        ])
        self.assertEqual(chats, [])
        self.assertEqual(vivo, [])


class SinUsuarioTest(BaseSupervisor):
    def test_tiktok_sin_usuario_sigue(self):
        armado = self.armar(usuario="", estados=[muestra(False)])
        supervisor, anuncios, chats, _, _, vivo, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios, [
            ("Comenzando la transmisión.", "conectando"),
            ("OBS está enviando la señal a Restream.", "conectado"),
            ("No hay usuario de TikTok guardado: conecta el chat a mano.",
             None),
        ])
        self.assertEqual(chats, [])
        self.assertEqual(vivo, [])


class ProblemaRepetidoTest(BaseSupervisor):
    def test_misma_frase_una_vez_por_minuto(self):
        # Cada sondeo suma 100 cuadros con 60 perdidos: siempre 60 %.
        estados = [muestra(True, duracion=10, perdidos=0, totales=1000)]
        for i in range(1, 20):
            estados.append(muestra(True, duracion=10 + i,
                                   perdidos=60 * i, totales=1000 + 100 * i))
        estados.append(muestra(False, duracion=30))
        armado = self.armar(destino="YouTube", estados=estados,
                            intervalo=5.0)
        supervisor, anuncios, _, _, _, _, reloj = armado
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        frase = ("Se están perdiendo cuadros: 60 por ciento. "
                 "La red va lenta.")
        apariciones = [a for a in anuncios if a[0] == frase]
        # 19 sondeos con problema en 95 s de reloj falso: avisa a los 5 s y
        # a los 65 s, y calla las repeticiones de en medio.
        self.assertEqual(len(apariciones), 2)
        self.assertTrue(all(s == "transmision_problema" for _, s in apariciones))
        self.assertTrue(reloj.ahora >= 60.0)


class ReconexionVueltaTest(BaseSupervisor):
    def test_reconexion_y_vuelta_con_sus_sonidos(self):
        estados = [muestra(True, duracion=10),
                   muestra(True, duracion=11, reconectando=True),
                   muestra(True, duracion=12),
                   muestra(False, duracion=13)]
        armado = self.armar(destino="YouTube", estados=estados, intervalo=5.0)
        supervisor, anuncios, _, _, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        self.assertIn(
            ("Se cortó la conexión con el servicio, OBS está reconectando.",
             "transmision_problema"), anuncios)
        self.assertIn(("La conexión con el servicio volvió.",
                       "transmision_recuperada"), anuncios)


class ClienteStreamFalso:
    """Cliente de OBS enlatado para ejercitar el GestorPanelObs real."""

    def __init__(self, estados):
        self._estados = list(estados)
        self._indice = 0
        self.conectado = False

    def conectar(self, parada=None):
        self.conectado = True

    def cerrar(self):
        self.conectado = False

    def pedir(self, tipo, datos=None, parada=None):
        if tipo == "GetStreamStatus":
            indice = min(self._indice, len(self._estados) - 1)
            self._indice += 1
            return {"responseData": dict(self._estados[indice])}
        return {"responseData": {}}


class ReconexionPorEstadoRealTest(unittest.TestCase):
    def test_la_vigilancia_lee_la_reconexion_de_estado_transmision(self):
        # El estado sale del GestorPanelObs de verdad: si estado_transmision
        # deja de exponer outputReconnecting, este cableado deja de avisar.
        estados = [muestra(True, duracion=10),
                   muestra(True, duracion=11, reconectando=True),
                   muestra(False, duracion=30)]
        cliente = ClienteStreamFalso(estados)
        reloj = RelojFalso()
        anuncios = []
        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=lambda: obs_panel.GestorPanelObs(cliente),
            esperar_salida=lambda c, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=5.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        supervisor.iniciar()
        self.assertTrue(esperar_condicion(lambda: not supervisor.activo, 3.0))
        self.assertIn(
            ("Se cortó la conexión con el servicio, OBS está reconectando.",
             "transmision_problema"), anuncios)


class AvisosDeEquipoTest(BaseSupervisor):
    def _estadisticas_con_sobrecarga(self, pasos=9):
        # Al codificar: cada paso suma 100 cuadros totales y una porción cada
        # vez mayor de perdidos, así el porcentaje cambia en cada vuelta.
        muestras = [{"outputSkippedFrames": 0, "outputTotalFrames": 1000,
                     "renderSkippedFrames": 0, "renderTotalFrames": 1000}]
        perdidos = 0
        for paso in range(1, pasos + 1):
            perdidos += 35 + 5 * paso
            muestras.append({"outputSkippedFrames": perdidos,
                             "outputTotalFrames": 1000 + 100 * paso,
                             "renderSkippedFrames": 0,
                             "renderTotalFrames": 1000})
        return muestras

    def test_sobrecarga_se_anuncia_una_vez_en_la_vigilancia(self):
        estados = [muestra(True, duracion=10)] * 9 + [muestra(False, duracion=30)]
        armado = self.armar(destino="YouTube", estados=estados, intervalo=5.0,
                            estadisticas=self._estadisticas_con_sobrecarga())
        supervisor, anuncios, _, _, _, _, reloj = armado
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        frases = [f for f, _ in anuncios if f.startswith("OBS no da abasto")]
        self.assertEqual(len(frases), 1)
        self.assertIn("40 por ciento", frases[0])
        self.assertLess(reloj.ahora, 300.0)

    def test_contador_que_vuelve_a_cero_no_avisa(self):
        estados = [muestra(True, duracion=10)] * 4 + [muestra(False, duracion=30)]
        estadisticas = [
            {"outputSkippedFrames": 500, "outputTotalFrames": 2000,
             "renderSkippedFrames": 500, "renderTotalFrames": 2000},
        ] + [{"outputSkippedFrames": 0, "outputTotalFrames": 0,
              "renderSkippedFrames": 0, "renderTotalFrames": 0}] * 6
        armado = self.armar(destino="YouTube", estados=estados, intervalo=5.0,
                            estadisticas=estadisticas)
        supervisor, anuncios, _, _, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        self.assertFalse(any(f.startswith("OBS no da abasto")
                             for f, _ in anuncios))

    def test_estadisticas_que_fallan_no_cortan_la_vigilancia(self):
        estados = [muestra(True, duracion=10), muestra(False, duracion=30)]
        armado = self.armar(destino="YouTube", estados=estados, intervalo=5.0,
                            fallo="estadisticas")
        supervisor, anuncios, _, _, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        self.assertIn(("La transmisión terminó. Duró 30 segundos.",
                       "transmision_detenida"), anuncios)

    BASE_EST = {"outputSkippedFrames": 0, "outputTotalFrames": 1000,
                "renderSkippedFrames": 0, "renderTotalFrames": 1000}

    def _estadisticas_de_dos_sobrecargas(self):
        return [
            dict(self.BASE_EST),
            {"outputSkippedFrames": 400, "outputTotalFrames": 2000,
             "renderSkippedFrames": 0, "renderTotalFrames": 1000},
            {"outputSkippedFrames": 800, "outputTotalFrames": 3000,
             "renderSkippedFrames": 0, "renderTotalFrames": 1000},
        ]

    def _armar_dos_sobrecargas(self, intervalo):
        estados = ([muestra(True, duracion=10)] * 3
                   + [muestra(False, duracion=30)])
        return self.armar(destino="YouTube", estados=estados,
                          intervalo=intervalo,
                          estadisticas=self._estadisticas_de_dos_sobrecargas())

    def test_sobrecarga_no_se_repite_antes_de_cinco_minutos(self):
        supervisor, anuncios, _, _, _, _, _ = self._armar_dos_sobrecargas(60.0)
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        frases = [f for f, _ in anuncios if f.startswith("OBS no da abasto")]
        self.assertEqual(len(frases), 1)

    def test_sobrecarga_se_repite_a_los_trescientos_un_segundos(self):
        supervisor, anuncios, _, _, _, _, _ = self._armar_dos_sobrecargas(301.0)
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        frases = [f for f, _ in anuncios if f.startswith("OBS no da abasto")]
        self.assertEqual(len(frases), 2)

    def _armar_sobrecarga_y_red(self):
        estados = [muestra(True, duracion=10, perdidos=0, totales=1000)]
        for i in range(1, 4):
            estados.append(muestra(True, duracion=10 + i,
                                   perdidos=60 * i, totales=1000 + 100 * i))
        estados.append(muestra(False, duracion=30))
        return self.armar(destino="YouTube", estados=estados, intervalo=5.0,
                          estadisticas=self._estadisticas_de_dos_sobrecargas())

    def test_avisar_sobrecarga_falso_no_anuncia_sobrecarga_pero_si_red(self):
        supervisor, anuncios, _, _, _, _, _ = self._armar_sobrecarga_y_red()
        supervisor._avisar_sobrecarga = lambda: False
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        self.assertFalse(any(f.startswith("OBS no da abasto")
                             for f, _ in anuncios))
        self.assertTrue(any("Se están perdiendo cuadros" in f
                            for f, _ in anuncios))

    def test_pasar_de_falso_a_verdadero_anuncia_sin_esperar_el_plazo(self):
        supervisor, anuncios, _, _, _, _, _ = self._armar_dos_sobrecargas(60.0)
        llamadas = []

        def avisar():
            llamadas.append(True)
            return len(llamadas) >= 2

        supervisor._avisar_sobrecarga = avisar
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        frases = [f for f, _ in anuncios if f.startswith("OBS no da abasto")]
        self.assertEqual(len(frases), 1)


class FinTransmisionTest(BaseSupervisor):
    def test_fin_anuncia_la_duracion(self):
        estados = [muestra(True, duracion=61),
                   muestra(False, duracion=61)]
        armado = self.armar(destino="YouTube", estados=estados,
                            intervalo=0.01)
        supervisor, anuncios, _, _, _, _, _ = armado
        # Dormir real cortito para este caso: la vigilancia pide dos
        # muestras con una siesta mínima en medio.
        supervisor._dormir = time.sleep
        self.iniciar_y_esperar_fin(supervisor)
        self.assertIn(
            ("La transmisión terminó. Duró 1 minuto y 1 segundo.", "transmision_detenida"),
            anuncios)

    def test_duracion_legible(self):
        self.assertEqual(duracion_legible(5), "5 segundos")
        self.assertEqual(duracion_legible(61), "1 minuto y 1 segundo")
        self.assertEqual(duracion_legible(3661),
                         "1 hora, 1 minuto y 1 segundo")


class DetenerTest(BaseSupervisor):
    def test_detener_para_obs_y_no_duplica(self):
        reloj = RelojFalso()
        anuncios = []
        gestores = []
        vivo = threading.Event()

        def crear_gestor():
            # El primero es el de la vigilancia y sigue activo; el segundo
            # es el de detener() y confirma la parada al segundo sondeo.
            if gestores:
                estados = [muestra(True, duracion=10),
                           muestra(True, duracion=10),
                           muestra(False, duracion=10)]
            else:
                estados = [muestra(True, duracion=10)] * 500
            gestor = GestorFalso(estados)
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: ResultadoEspera(
                False, False),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=1000.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        supervisor.iniciar()
        # Espera a que el hilo entre en vigilancia.
        self.assertTrue(esperar_condicion(
            lambda: gestores and "estado" in gestores[0].llamadas))
        supervisor.detener()
        self.assertFalse(supervisor.activo)
        # El segundo gestor es el propio de detener(): paró OBS.
        self.assertGreaterEqual(len(gestores), 2)
        self.assertIn("detener", gestores[1].llamadas)
        self.assertIn(("Transmisión detenida.", "transmision_detenida"), anuncios)
        self.assertFalse(any(frase.startswith("La transmisión terminó")
                             for frase, _ in anuncios))

    def test_iniciar_dos_veces_no_duplica_el_hilo(self):
        armado = self.armar(destino="YouTube",
                            estados=[muestra(True, duracion=10)] * 500,
                            intervalo=1000.0)
        supervisor, anuncios, _, gestores, _, _, _ = armado
        supervisor.iniciar()
        primero = supervisor._hilo
        supervisor.iniciar()
        self.assertIs(supervisor._hilo, primero)
        supervisor.detener()
        self.assertFalse(supervisor.activo)


class DetenerRapidoTest(BaseSupervisor):
    def test_detener_despierta_la_vigilancia_en_menos_de_dos_segundos(self):
        # Sin dormir inyectado la vigilancia espera con la parada: aunque el
        # intervalo sea de 5 s, detener() deja activo en False enseguida.
        anuncios = []
        gestores = []

        def crear_gestor():
            # El de la vigilancia no para; el de detener() confirma enseguida.
            if gestores:
                estados = [muestra(True, duracion=10),
                           muestra(False, duracion=10)]
            else:
                estados = [muestra(True, duracion=10)] * 500
            gestor = GestorFalso(estados)
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: ResultadoEspera(
                False, False),
            intervalo_salud=5.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        supervisor.iniciar()
        self.assertTrue(esperar_condicion(
            lambda: gestores and "estado" in gestores[0].llamadas))
        inicio = time.monotonic()
        supervisor.detener()
        tardado = time.monotonic() - inicio
        self.assertFalse(supervisor.activo)
        self.assertLess(tardado, 2.0)


class DeteniendoTest(BaseSupervisor):
    """El estado `deteniendo` cubre la espera a que OBS confirme."""

    def test_verdadero_mientras_obs_no_confirma_y_falso_al_volver(self):
        lecturas = []
        terminados = []
        gestores = []

        def crear_gestor():
            # El segundo gestor es el de detener(): cada vez que le
            # contestan el estado, queda anotado si ya se estaba deteniendo.
            if gestores:
                estados = [muestra(True, duracion=10),
                           muestra(True, duracion=10),
                           muestra(False, duracion=10)]
            else:
                estados = [muestra(True, duracion=10)] * 500
            gestor = GestorFalso(estados)
            if gestores:
                original = gestor.estado_transmision

                def estado(parada=None):
                    lecturas.append(supervisor.deteniendo)
                    return original(parada)

                gestor.estado_transmision = estado
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: None,
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=time.sleep, reloj=time.monotonic,
            intervalo_salud=0.05,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            al_terminar=lambda: terminados.append(supervisor.deteniendo))
        supervisor.iniciar()
        self.assertTrue(esperar_condicion(
            lambda: gestores and "estado" in gestores[0].llamadas))
        supervisor.detener()
        self.assertFalse(supervisor.deteniendo)
        self.assertTrue(lecturas)
        self.assertTrue(all(lecturas))
        # El último aviso es el de detener(), después de bajar el estado.
        self.assertEqual(terminados[-1], False)

    def test_no_es_verdadero_si_no_estaba_activo(self):
        terminados = []
        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: None,
            al_conectar_chat=lambda url: None,
            crear_gestor=lambda: GestorFalso([muestra(False)]),
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=time.sleep, reloj=time.monotonic,
            intervalo_salud=1000.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            al_terminar=lambda: terminados.append(supervisor.deteniendo))
        supervisor.detener()
        self.assertFalse(supervisor.deteniendo)
        self.assertEqual(terminados, [False])


class AbandonarTest(BaseSupervisor):
    def test_abandonar_no_detiene_obs_ni_anuncia(self):
        anuncios = []
        gestores = []

        def crear_gestor():
            gestor = GestorFalso([muestra(True, duracion=10)] * 500)
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: ResultadoEspera(
                False, False),
            dormir=time.sleep, reloj=time.monotonic,
            intervalo_salud=0.05,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        supervisor.iniciar()
        self.assertTrue(esperar_condicion(
            lambda: gestores and "estado" in gestores[0].llamadas))
        supervisor.abandonar()
        self.assertFalse(supervisor.activo)
        self.assertEqual(len(gestores), 1)
        self.assertNotIn("detener", gestores[0].llamadas)
        self.assertNotIn(("Transmisión detenida.", "transmision_detenida"), anuncios)


class ExcepcionTest(BaseSupervisor):
    def test_excepcion_del_gestor_se_anuncia_una_vez(self):
        armado = self.armar(fallo="conectar")
        supervisor, anuncios, chats, gestores, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        errores = [a for a in anuncios if a[1] == "transmision_problema"]
        self.assertEqual(len(errores), 1)
        self.assertEqual(chats, [])
        self.assertEqual(gestores[0].cerrado, 1)


class AsegurarObsTest(BaseSupervisor):
    def test_con_obs_cerrado_anuncia_abriendo_antes_de_lo_de_siempre(self):
        armado = self.armar(destino="YouTube", estados=[muestra(False)])
        supervisor, anuncios, _, gestores, _, _, _ = armado

        def asegurar(probar, al_anunciar=None, parada=None):
            probar()
            al_anunciar("Abriendo OBS. Puede tardar hasta un minuto.")
            return True

        supervisor._asegurar = asegurar
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios[0],
                         ("Comenzando la transmisión.", "conectando"))
        self.assertEqual(anuncios[1],
                         ("Abriendo OBS. Puede tardar hasta un minuto.", None))
        self.assertEqual(anuncios[2][1], "conectado")
        # La prueba usó un gestor y el trabajo real otro, ambos cerrados.
        self.assertGreaterEqual(len(gestores), 2)
        self.assertTrue(all(gestor.cerrado == 1 for gestor in gestores))

    def test_sin_obs_anuncia_el_texto_exactoy_no_transmite(self):
        from ytchat.obs.obs_lanzador import ObsNoInstalado
        armado = self.armar(destino="YouTube", estados=[muestra(False)])
        supervisor, anuncios, _, gestores, _, _, _ = armado

        def asegurar(probar, al_anunciar=None, parada=None):
            raise ObsNoInstalado(
                "OBS no está instalado en este equipo. Instálalo desde "
                "obsproject.com y vuelve a intentarlo.")
        supervisor._asegurar = asegurar
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios[0],
                         ("Comenzando la transmisión.", "conectando"))
        self.assertEqual(anuncios[1], (
            "OBS no está instalado en este equipo. Instálalo desde "
            "obsproject.com y vuelve a intentarlo.", "transmision_problema"))
        self.assertFalse(any("iniciar" in gestor.llamadas
                             for gestor in gestores))

    def test_asegurar_abre_obs_antes_del_primer_conectar(self):
        armado = self.armar(destino="YouTube", estados=[muestra(False)])
        supervisor, anuncios, _, gestores, _, _, _ = armado
        abierto = []

        def crear_gestor():
            gestor = GestorFalso([muestra(False)])
            gestores.append(gestor)
            conectar_real = gestor.conectar

            def conectar(parada=None):
                if not abierto:
                    gestor.llamadas.append("conectar")
                    raise obs_cliente.ObsError(
                        "No se pudo conectar con OBS.")
                return conectar_real(parada)

            gestor.conectar = conectar
            return gestor

        def asegurar(probar, al_anunciar=None, parada=None):
            abierto.append(True)
            return True

        supervisor._crear_gestor = crear_gestor
        supervisor._asegurar = asegurar
        self.iniciar_y_esperar_fin(supervisor)
        self.assertTrue(gestores)
        self.assertIn("iniciar", gestores[0].llamadas)


class AlTerminarTest(BaseSupervisor):
    def test_fin_normal_avisa_una_vez(self):
        armado = self.armar(estados=[muestra(False)])
        supervisor, _anuncios, _chats, _gs, _, _, _ = armado
        terminados = []
        supervisor._al_terminar = lambda: terminados.append(True)
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(terminados, [True])

    def test_con_error_avisa_una_vez(self):
        armado = self.armar(fallo="conectar")
        supervisor, _anuncios, _chats, _gs, _, _, _ = armado
        terminados = []
        supervisor._al_terminar = lambda: terminados.append(True)
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(terminados, [True])

    def test_al_detener_avisa_al_salir_y_al_terminar(self):
        gestores = []
        terminados = []

        def crear_gestor():
            # El de la vigilancia no para; el de detener() confirma enseguida.
            if gestores:
                estados = [muestra(True, duracion=10),
                           muestra(False, duracion=10)]
            else:
                estados = [muestra(True, duracion=10)] * 500
            gestor = GestorFalso(estados)
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: None,
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: ResultadoEspera(
                False, False),
            dormir=time.sleep, reloj=time.monotonic,
            intervalo_salud=0.05,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            al_terminar=lambda: terminados.append(True))
        supervisor.iniciar()
        self.assertTrue(esperar_condicion(
            lambda: gestores and "estado" in gestores[0].llamadas))
        supervisor.detener()
        self.assertFalse(supervisor.activo)
        # Una al salir la vigilancia y otra al confirmar OBS el fin de detener.
        self.assertEqual(terminados, [True, True])

    def test_si_avisa_mal_se_traga_la_excepcion(self):
        armado = self.armar(estados=[muestra(False)])
        supervisor, _anuncios, _chats, gestores, _, _, _ = armado

        def _romper():
            raise RuntimeError("boom al avisar")
        supervisor._al_terminar = _romper
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(gestores[0].cerrado, 1)


class FraseEstadoTest(BaseSupervisor):
    def test_vacia_antes_de_iniciar(self):
        supervisor, _, _, _, _, _, _ = self.armar()
        self.assertEqual(supervisor.frase_estado(), "")

    def test_esperando_a_tiktok_repite_la_ultima_frase_sin_punto(self):
        liberado = threading.Event()
        armado = self.armar(estados=[muestra(True, duracion=10)])
        supervisor, anuncios, _, _, _, _, _ = armado
        real = supervisor._esperar_en_vivo

        def esperar_bloqueado(usuario, parada=None, limite=None):
            liberado.wait(2.0)
            return real(usuario, parada, limite)

        supervisor._esperar_en_vivo = esperar_bloqueado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: any(a[0].startswith("Esperando a que TikTok")
                            for a in anuncios)))
            self.assertEqual(
                supervisor.frase_estado(),
                "Esperando a que TikTok muestre el directo")
        finally:
            liberado.set()
            supervisor.abandonar()

    def test_transmitiendo_nombra_el_destino_y_la_duracion(self):
        armado = self.armar(
            estados=[muestra(True, duracion=180)] * 50)
        supervisor, _, _, _, _, _, _ = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: supervisor.frase_estado().startswith(
                    "Directo a TikTok:")))
            frase = supervisor.frase_estado()
            self.assertTrue(frase.startswith(
                "Directo a TikTok: Transmitiendo desde hace"))
            # _duracion(180) se lee «3 min».
            self.assertIn("3 min", frase)
        finally:
            supervisor.abandonar()

    def test_tiktok_confirmado_termina_en_ya_se_ve(self):
        armado = self.armar(
            estados=[muestra(True, duracion=180)] * 50)
        supervisor, _, _, _, _, _, _ = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: supervisor.frase_estado().startswith(
                    "Directo a TikTok:")))
            self.assertTrue(supervisor.frase_estado().endswith(
                ", ya se ve en TikTok"))
        finally:
            supervisor.abandonar()

    def test_tiktok_sin_confirmar_termina_en_aviso(self):
        armado = self.armar(
            en_vivo=False, estados=[muestra(True, duracion=180)] * 50)
        supervisor, _, _, _, _, _, _ = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: supervisor.frase_estado().startswith(
                    "Directo a TikTok:")))
            self.assertTrue(supervisor.frase_estado().endswith(
                ", sin confirmar en TikTok"))
        finally:
            supervisor.abandonar()

    def test_youtube_no_menciona_tiktok(self):
        armado = self.armar(
            destino="YouTube", estados=[muestra(True, duracion=180)] * 50)
        supervisor, _, _, _, _, _, _ = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: supervisor.frase_estado().startswith(
                    "Directo a YouTube:")))
            frase = supervisor.frase_estado()
            self.assertNotIn("TikTok", frase.split(":", 1)[1])
        finally:
            supervisor.abandonar()

    def test_duracion_que_avanza_se_actualiza_en_frase(self):
        estados = [muestra(True, duracion=10)]
        estados += [muestra(True, duracion=180)] * 50
        armado = self.armar(estados=estados)
        supervisor, _, _, _, _, _, _ = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: "3 min" in supervisor.frase_estado()))
        finally:
            supervisor.abandonar()


class YouTubeEmisionTest(BaseSupervisor):
    def armar_con_ganchos(self, estados=None, espera=True,
                          preparar_falla=None, intervalo=1000.0):
        reloj = RelojFalso()
        anuncios = []
        chats = []
        gestores = []
        orden = []
        llamadas_preparar = []
        llamadas_espera = []

        def crear_gestor():
            gestor = GestorFalso(estados)
            gestores.append(gestor)
            original = gestor.iniciar_transmision

            def iniciar(parada=None):
                orden.append("iniciar")
                return original(parada)

            gestor.iniciar_transmision = iniciar
            return gestor

        def preparar(cliente, parada):
            orden.append("preparar")
            llamadas_preparar.append((cliente, parada))
            if preparar_falla is not None:
                raise preparar_falla
            return "vid123"

        def esperar(id_video, parada, limite):
            llamadas_espera.append((id_video, limite))
            return espera

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=chats.append,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=intervalo,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            preparar_emision=preparar, esperar_emision=esperar)
        return (supervisor, anuncios, chats, gestores, orden,
                llamadas_preparar, llamadas_espera)

    def test_youtube_feliz_con_orden_y_url(self):
        armado = self.armar_con_ganchos()
        (supervisor, anuncios, chats, gestores, orden,
         llamadas_preparar, llamadas_espera) = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios, [
            ("Comenzando la transmisión.", "conectando"),
            ("Creando el directo en YouTube.", None),
            ("OBS está enviando la señal a YouTube.", "conectado"),
            ("Esperando a que YouTube muestre el directo.", None),
            ("Tu directo de YouTube ya está al aire.", "al_aire"),
        ])
        self.assertEqual(
            chats, ["https://www.youtube.com/watch?v=vid123"])
        self.assertEqual(orden, ["preparar", "iniciar"])
        self.assertIs(llamadas_preparar[0][0], gestores[0])
        self.assertEqual(llamadas_espera, [("vid123", 120.0)])
        self.assertEqual(gestores[0].cerrado, 1)

    def test_preparar_que_falla_no_inicia(self):
        armado = self.armar_con_ganchos(
            preparar_falla=emision.EmisionError("falla youtube"))
        (supervisor, anuncios, chats, gestores, orden,
         _preparar, espera) = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(anuncios, [
            ("Comenzando la transmisión.", "conectando"),
            ("Creando el directo en YouTube.", None),
            ("falla youtube", "transmision_problema"),
        ])
        self.assertEqual(chats, [])
        self.assertEqual(espera, [])
        self.assertNotIn("iniciar", gestores[0].llamadas)
        self.assertNotIn("iniciar", orden)
        self.assertEqual(gestores[0].cerrado, 1)

    def test_sin_confirmar_avisa_y_frase_lo_dice(self):
        armado = self.armar_con_ganchos(
            estados=[muestra(True, duracion=180)] * 50, espera=False)
        (supervisor, anuncios, chats, _gestores, _orden,
         _preparar, _espera) = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: ("OBS está transmitiendo, pero YouTube todavía "
                         "no muestra el directo.", "transmision_problema") in anuncios))
            self.assertEqual(chats, [])
            self.assertTrue(supervisor.frase_estado().endswith(
                ", sin confirmar en YouTube"))
        finally:
            supervisor.abandonar()


class FinalizarYoutubeTest(BaseSupervisor):
    def armar_youtube(self, estados, intervalo=0.01, espera=True,
                      finalizar=None, estados_detener=None):
        anuncios = []
        gestores = []
        llamadas_finalizar = []

        def crear_gestor():
            # El primer gestor es el de la vigilancia; los siguientes, los
            # que crea detener() para hablar con OBS.
            if estados_detener is not None and gestores:
                gestor = GestorFalso(estados_detener)
            else:
                gestor = GestorFalso(estados)
            gestores.append(gestor)
            return gestor

        def preparar(cliente, parada):
            return "vid123"

        def esperar(id_video, parada, limite):
            return espera

        def finalizar_hook(id_video):
            llamadas_finalizar.append(id_video)
            if finalizar is not None:
                raise finalizar

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=time.sleep, reloj=time.monotonic,
            intervalo_salud=intervalo,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            preparar_emision=preparar, esperar_emision=esperar,
            finalizar_emision=finalizar_hook)
        return supervisor, anuncios, gestores, llamadas_finalizar

    def test_vigilar_cierra_en_youtube_al_apagarse_obs(self):
        estados = [muestra(True, duracion=61),
                   muestra(False, duracion=61)]
        armado = self.armar_youtube(estados)
        supervisor, anuncios, _gestores, llamadas = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(llamadas, ["vid123"])
        self.assertIn(
            ("La transmisión terminó. Duró 1 minuto y 1 segundo.", "transmision_detenida"),
            anuncios)

    def test_reconectando_no_cierra(self):
        estados = [muestra(True, duracion=10, reconectando=True)] * 50
        armado = self.armar_youtube(estados, intervalo=0.01)
        supervisor, anuncios, gestores, llamadas = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: gestores and gestores[0].llamadas.count(
                    "estado") >= 5))
            self.assertEqual(llamadas, [])
            frase = ("Se cortó la conexión con el servicio, "
                     "OBS está reconectando.")
            self.assertTrue(esperar_condicion(
                lambda: frase in [texto for texto, _ in anuncios]))
        finally:
            supervisor.abandonar()
        self.assertEqual(llamadas, [])
        avisos = [texto for texto, _ in anuncios if texto == frase]
        self.assertEqual(len(avisos), 1)

    def test_detener_cierra_una_vez_y_vigilar_no_repite(self):
        estados = [muestra(True, duracion=10)] * 500
        armado = self.armar_youtube(
            estados,
            estados_detener=[muestra(True, duracion=10),
                             muestra(False, duracion=10)])
        supervisor, anuncios, gestores, llamadas = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: gestores and "estado" in gestores[0].llamadas))
            supervisor.detener()
            self.assertEqual(llamadas, ["vid123"])
            self.assertIn(("Transmisión detenida.", "transmision_detenida"), anuncios)
            # La vigilancia ve OBS apagado después: no se vuelve a llamar.
            supervisor._parada.clear()
            supervisor._corte.clear()
            supervisor._vigilar(GestorFalso(
                [muestra(False, duracion=61)]))
            self.assertEqual(llamadas, ["vid123"])
        finally:
            if supervisor.activo:
                supervisor.abandonar()

    def test_abandonar_no_cierra(self):
        estados = [muestra(True, duracion=10)] * 500
        armado = self.armar_youtube(estados)
        supervisor, _anuncios, gestores, llamadas = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: gestores and "estado" in gestores[0].llamadas))
        finally:
            supervisor.abandonar()
        self.assertEqual(llamadas, [])

    def test_sin_id_de_video_no_cierra(self):
        # TikTok nunca fija _id_video: detener no toca YouTube.
        anuncios = []
        gestores = []
        llamadas = []

        def crear_gestor():
            # El de la vigilancia no para; el de detener() confirma enseguida.
            if gestores:
                estados = [muestra(True, duracion=10),
                           muestra(False, duracion=10)]
            else:
                estados = [muestra(True, duracion=10)] * 500
            gestor = GestorFalso(estados)
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "TikTok", "amigo",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(True, False)),
            dormir=time.sleep, reloj=time.monotonic,
            intervalo_salud=0.01,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            finalizar_emision=llamadas.append)
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: gestores and "estado" in gestores[0].llamadas))
            supervisor.detener()
        finally:
            if supervisor.activo:
                supervisor.abandonar()
        self.assertEqual(llamadas, [])
        self.assertIn(("Transmisión detenida.", "transmision_detenida"), anuncios)

    def test_si_youtube_falla_avisa_con_sonido_de_error(self):
        estados = [muestra(True, duracion=10)] * 500
        armado = self.armar_youtube(
            estados, finalizar=RuntimeError("cuota agotada"),
            estados_detener=[muestra(True, duracion=10),
                             muestra(False, duracion=10)])
        supervisor, anuncios, gestores, llamadas = armado
        supervisor.iniciar()
        try:
            self.assertTrue(esperar_condicion(
                lambda: gestores and "estado" in gestores[0].llamadas))
            supervisor.detener()
            self.assertEqual(llamadas, ["vid123"])
        finally:
            if supervisor.activo:
                supervisor.abandonar()
        self.assertIn(
            ("YouTube no confirmó el fin del directo. "
             "Se reintentará durante 10 minutos.", "transmision_problema"),
            anuncios)


class PanelAdelanteTest(BaseSupervisor):
    FRASE = ("El panel de chat estaba detrás de "
             "«Captura de pantalla». Ahora está delante.")

    def armar_con_panel(self, respuestas, estados=None, intervalo=5.0):
        reloj = RelojFalso()
        anuncios = []
        gestores = []
        llamadas = []
        respuestas = list(respuestas)
        estados = list(estados if estados is not None
                       else [muestra(False)])

        def crear_gestor():
            gestor = GestorFalso(estados)
            gestores.append(gestor)

            def traer(parada=None):
                llamadas.append(True)
                if len(llamadas) <= len(respuestas):
                    return respuestas[len(llamadas) - 1]
                return respuestas[-1]

            gestor.traer_panel_adelante = traer
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=intervalo,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        return supervisor, anuncios, gestores, llamadas

    def test_al_salir_al_aire_anuncia_el_panel_tapado(self):
        armado = self.armar_con_panel(["Captura de pantalla"])
        supervisor, anuncios, gestores, llamadas = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertTrue(llamadas)
        self.assertIn((self.FRASE, "aviso"), anuncios)

    def test_vigilar_anuncia_una_vez_por_minuto(self):
        # El panel queda tapado a mitad del directo: la primera llamada es
        # la de antes de transmitir y no hay nada encima todavía.
        estados = [muestra(True, duracion=10)] * 5
        estados.append(muestra(False, duracion=30))
        respuestas = [None] + ["Captura de pantalla"] * 10
        armado = self.armar_con_panel(respuestas, estados=estados)
        supervisor, anuncios, _gestores, llamadas = armado
        self.iniciar_y_esperar_fin(supervisor, plazo=3.0)
        apariciones = [a for a in anuncios if a[0] == self.FRASE]
        self.assertTrue(len(llamadas) >= 3)
        self.assertEqual(len(apariciones), 1)
        self.assertEqual(apariciones[0][1], "aviso")

    def test_si_traer_falla_el_directo_sigue(self):
        reloj = RelojFalso()
        anuncios = []
        gestores = []

        def crear_gestor():
            gestor = GestorFalso([muestra(False)])
            gestores.append(gestor)

            def traer(parada=None):
                raise RuntimeError("boom al traer")

            gestor.traer_panel_adelante = traer
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=1000.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False)
        self.iniciar_y_esperar_fin(supervisor)
        self.assertIn(("OBS está enviando la señal a YouTube.", "conectado"),
                      anuncios)
        self.assertFalse(any(frase.startswith("El panel de chat")
                             for frase, _ in anuncios))


class EsperaObsTest(unittest.TestCase):
    """La espera a que OBS confirme la parada, con reloj falso."""

    def _supervisor(self, estados_detener, finalizar=None, ruta=None,
                    reloj=None):
        reloj = reloj or RelojFalso()
        anuncios = []
        gestores = []

        def crear_gestor():
            gestor = GestorFalso(estados_detener)
            gestores.append(gestor)
            return gestor

        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=crear_gestor,
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=1000.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            finalizar_emision=finalizar,
            ruta_fin_pendiente=ruta)
        supervisor._id_video = "vid123"
        return supervisor, anuncios, gestores, reloj

    def test_anuncia_detenida_solo_cuando_obs_apaga(self):
        estados = [muestra(True)] * 6 + [muestra(False)]
        supervisor, anuncios, gestores, _ = self._supervisor(estados)
        supervisor._detener_obs()
        self.assertEqual(anuncios, [
            ("Deteniendo la transmisión. Esperando a que OBS confirme.",
             None),
            ("Transmisión detenida.", "transmision_detenida"),
        ])
        self.assertEqual(gestores[0].llamadas.count("detener"), 1)
        self.assertEqual(gestores[0].cerrado, 1)

    def test_avisa_una_sola_vez_al_esperar(self):
        estados = [muestra(True)] * 6 + [muestra(False)]
        supervisor, anuncios, _gestores, _ = self._supervisor(estados)
        supervisor._detener_obs()
        avisos = [f for f, _ in anuncios
                  if f == "Deteniendo la transmisión. "
                           "Esperando a que OBS confirme."]
        self.assertEqual(len(avisos), 1)

    def test_a_los_noventa_segundos_no_insiste(self):
        estados = [muestra(True)] * 200
        supervisor, anuncios, _gestores, _ = self._supervisor(estados)
        supervisor._detener_obs()
        self.assertEqual(anuncios[-1], (
            "OBS sigue transmitiendo. Detén la transmisión en OBS.",
            "transmision_problema"))
        self.assertFalse(any(f == "Transmisión detenida." for f, _ in anuncios))
        avisos = [f for f, _ in anuncios
                  if f == "Deteniendo la transmisión. "
                           "Esperando a que OBS confirme."]
        self.assertEqual(len(avisos), 1)

    def test_obs_ya_apagado_avisa_detenida(self):
        supervisor, anuncios, gestores, _ = self._supervisor(
            [muestra(False)])
        supervisor._detener_obs()
        self.assertEqual(anuncios, [("Transmisión detenida.",
                                     "transmision_detenida")])
        self.assertNotIn("detener", gestores[0].llamadas)

    def test_conectar_falla_con_obs_abierto(self):
        supervisor, anuncios, _gestores, _ = self._supervisor(
            [muestra(True)])
        with mock.patch.object(
                obs_supervisor.obs_activacion,
                "obs_esta_en_ejecucion", return_value=True):
            supervisor._crear_gestor = lambda: GestorFalso(
                fallo="conectar")
            supervisor._detener_obs()
        self.assertEqual(anuncios, [(
            "No se pudo conectar con OBS para detener la transmisión.",
            "transmision_problema")])

    def test_conectar_falla_con_obs_cerrado(self):
        supervisor, anuncios, _gestores, _ = self._supervisor(
            [muestra(True)])
        with mock.patch.object(
                obs_supervisor.obs_activacion,
                "obs_esta_en_ejecucion", return_value=False):
            supervisor._crear_gestor = lambda: GestorFalso(
                fallo="conectar")
            supervisor._detener_obs()
        self.assertEqual(anuncios, [("Transmisión detenida.",
                                     "transmision_detenida")])

    def test_estado_que_falla_asume_activa_y_manda_stop(self):
        supervisor, anuncios, _gestores, _ = self._supervisor(
            [muestra(True)])

        class GestorQueFallaAlPreguntar(GestorFalso):
            def estado_transmision(self, parada=None):
                self.llamadas.append("estado")
                intento = self.llamadas.count("estado")
                if intento == 1:
                    raise RuntimeError("boom en estado")
                return muestra(intento <= 3)

        gestor = GestorQueFallaAlPreguntar()
        supervisor._crear_gestor = lambda: gestor
        supervisor._detener_obs()
        self.assertIn("detener", gestor.llamadas)
        self.assertIn(("Transmisión detenida.", "transmision_detenida"),
                      anuncios)


class FinPendienteTest(unittest.TestCase):
    """El fin de directo sin confirmar se anota y se reintenta solo."""

    def _supervisor(self, ruta, finalizar):
        anuncios = []
        reloj = RelojFalso()
        supervisor = SupervisorTransmision(
            "YouTube", "",
            al_anunciar=lambda frase, sonido: anuncios.append(
                (frase, sonido)),
            al_conectar_chat=lambda url: None,
            crear_gestor=lambda: GestorFalso([muestra(False)]),
            esperar_salida=lambda cliente, parada=None: "enviando",
            esperar_en_vivo=lambda u, parada=None, limite=None: (
                ResultadoEspera(False, False)),
            dormir=reloj.dormir, reloj=reloj.reloj,
            intervalo_salud=1000.0,
            asegurar=lambda probar, al_anunciar=None, parada=None: False,
            finalizar_emision=finalizar,
            ruta_fin_pendiente=ruta)
        supervisor._id_video = "vid123"
        return supervisor, anuncios

    def test_anota_reintenta_y_limpia_al_lograr(self):
        llamadas = []

        def finalizar(id_video):
            llamadas.append(id_video)
            if len(llamadas) <= 2:
                raise RuntimeError("sin red")

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "fin_pendiente.json"
            supervisor, anuncios = self._supervisor(ruta, finalizar)
            supervisor._finalizar_youtube_si_toca()
            self.assertTrue(esperar_condicion(
                lambda: any(f == "Directo finalizado en YouTube."
                            for f, _ in anuncios)))
            self.assertEqual(llamadas[0], "vid123")
            self.assertTrue(len(llamadas) >= 3)
            self.assertEqual(fin_pendiente.leer(ruta), [])
        self.assertIn((
            "YouTube no confirmó el fin del directo. "
            "Se reintentará durante 10 minutos.", "transmision_problema"),
            anuncios)
        self.assertIn(("Directo finalizado en YouTube.",
                       "directo_finalizado"), anuncios)

    def test_si_el_reintento_se_rinde_queda_el_pendiente(self):
        def finalizar(id_video):
            raise RuntimeError("sin red")

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "fin_pendiente.json"
            supervisor, anuncios = self._supervisor(ruta, finalizar)
            supervisor._finalizar_youtube_si_toca()
            self.assertTrue(esperar_condicion(
                lambda: any(f == "YouTube sigue sin confirmar el fin del "
                                   "directo. Se intentará de nuevo al abrir "
                                   "Bellbird." for f, _ in anuncios)))
            self.assertEqual([e["id"] for e in fin_pendiente.leer(ruta)],
                             ["vid123"])
        self.assertIn((
            "YouTube sigue sin confirmar el fin del directo. "
            "Se intentará de nuevo al abrir Bellbird.", "transmision_problema"),
            anuncios)

    def test_sin_ruta_no_toca_el_disco_ni_reintenta(self):
        llamadas = []

        def finalizar(id_video):
            llamadas.append(id_video)
            raise RuntimeError("sin red")

        supervisor, anuncios = self._supervisor(None, finalizar)
        supervisor._finalizar_youtube_si_toca()
        time.sleep(0.05)
        self.assertEqual(llamadas, ["vid123"])
        self.assertIn((
            "YouTube no confirmó el fin del directo. "
            "Se reintentará durante 10 minutos.", "transmision_problema"),
            anuncios)
        self.assertFalse(any(f == "Directo finalizado en YouTube."
                             for f, _ in anuncios))


if __name__ == "__main__":
    unittest.main()

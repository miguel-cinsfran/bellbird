"""Pruebas del supervisor de la transmisión con dobles.

Sin ventanas, sin red y sin dormir de verdad: el gestor es falso, las
esperas son falsas y el reloj y el dormir son falsos. Lo único real es el
hilo, que se espera por sondeo con un plazo corto.
"""

import threading
import time
import unittest

from ytchat.capture.tiktok_vivo import ResultadoEspera
from ytchat.obs import obs_cliente
from ytchat.obs import obs_supervisor
from ytchat.obs.obs_supervisor import SupervisorTransmision, duracion_legible


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

    def __init__(self, estados=None, fallo=None):
        self.estados = list(estados or [muestra(False)])
        self.fallo = fallo
        self.llamadas = []
        self.conectado = False
        self.cerrado = 0
        self._cliente = self
        self.indice = 0

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
              en_vivo=True, sin_directos=False, intervalo=1000.0):
        reloj = RelojFalso()
        anuncios = []
        chats = []
        gestores = []
        llamadas_salida = []
        llamadas_vivo = []

        def crear_gestor():
            gestor = GestorFalso(estados, fallo)
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
            ("Tu directo de TikTok ya está al aire.", "conectado"),
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
            ("OBS no empezó a transmitir.", "error"),
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
            "activado TikTok.", "error"))

    def test_sin_noticia_del_directo(self):
        armado = self.armar(en_vivo=False, sin_directos=False,
                            estados=[muestra(False)])
        supervisor, anuncios, chats, _, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(chats, [])
        self.assertEqual(anuncios[-1], (
            "OBS está transmitiendo, pero TikTok todavía no muestra "
            "el directo.", "error"))


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
        self.assertTrue(all(s == "error" for _, s in apariciones))
        self.assertTrue(reloj.ahora >= 60.0)


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
            ("La transmisión terminó. Duró 1 minuto y 1 segundo.", None),
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
        self.assertIn(("Transmisión detenida.", None), anuncios)
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
        self.assertNotIn(("Transmisión detenida.", None), anuncios)


class ExcepcionTest(BaseSupervisor):
    def test_excepcion_del_gestor_se_anuncia_una_vez(self):
        armado = self.armar(fallo="conectar")
        supervisor, anuncios, chats, gestores, _, _, _ = armado
        self.iniciar_y_esperar_fin(supervisor)
        errores = [a for a in anuncios if a[1] == "error"]
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
            "obsproject.com y vuelve a intentarlo.", "error"))
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

    def test_al_detener_avisa_una_vez(self):
        gestores = []
        terminados = []

        def crear_gestor():
            gestor = GestorFalso([muestra(True, duracion=10)] * 500)
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
        self.assertEqual(terminados, [True])

    def test_si_avisa_mal_se_traga_la_excepcion(self):
        armado = self.armar(estados=[muestra(False)])
        supervisor, _anuncios, _chats, gestores, _, _, _ = armado

        def _romper():
            raise RuntimeError("boom al avisar")
        supervisor._al_terminar = _romper
        self.iniciar_y_esperar_fin(supervisor)
        self.assertEqual(gestores[0].cerrado, 1)


if __name__ == "__main__":
    unittest.main()

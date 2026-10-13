"""Tests de obs_destinos con un doble que simula lo medido en OBS real."""

import threading
import unittest

from ytchat.obs import obs_cliente
from ytchat.obs import obs_destinos
from ytchat.obs.obs_destinos import (
    Destino, cambiar_coleccion, coleccion_para, frase_destino_listo,
    preparar_destino, preparar_para_transmitir)


class DobleObsDestinos:
    """OBS responde éxito enseguida pero el cambio se ve N consultas después.

    Como el real, SetCurrentProfile sobre un perfil que aún no aparece
    responde con ObsError.
    """

    def __init__(self, perfiles=(), actual="", transmision=False,
                  demora_creacion=2, demora_cambio=2, fallo_escritura=False,
                  colecciones=(), coleccion_actual="", demora_coleccion=2):
        self.visibles = list(perfiles)
        self.actual = actual
        self.transmision = transmision
        self.demora_creacion = demora_creacion
        self.demora_cambio = demora_cambio
        self.fallo_escritura = fallo_escritura
        self.pendientes_creacion = []
        self.pendientes_cambio = []
        self.colecciones = list(colecciones)
        self.coleccion_actual = coleccion_actual
        self.demora_coleccion = demora_coleccion
        self.pendientes_coleccion = []
        self.servicio = {"server": "", "key": ""}
        self.video = {"baseWidth": 1920, "baseHeight": 1080,
                      "outputWidth": 1920, "outputHeight": 1080}
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        datos = datos or {}
        self.llamadas.append((tipo, dict(datos)))
        if tipo == "GetStreamStatus":
            return {"responseData": {"outputActive": self.transmision}}
        if tipo == "GetProfileList":
            self._avanzar()
            return {"responseData": {"profiles": list(self.visibles),
                                     "currentProfileName": self.actual}}
        if tipo == "CreateProfile":
            self.pendientes_creacion.append(
                [datos["profileName"], self.demora_creacion])
            return {"responseData": {}}
        if tipo == "SetCurrentProfile":
            if datos["profileName"] not in self.visibles \
                    and datos["profileName"] != self.actual:
                raise obs_cliente.ObsError(
                    obs_cliente.mensaje_de_fallo_obs("600 not found"))
            self.pendientes_cambio.append(
                [datos["profileName"], self.demora_cambio])
            return {"responseData": {}}
        if tipo == "SetStreamServiceSettings":
            if not self.fallo_escritura:
                self.servicio = dict(
                    datos.get("streamServiceSettings", {}))
            return {"responseData": {}}
        if tipo == "GetStreamServiceSettings":
            return {"responseData": {
                "streamServiceType": "rtmp_custom",
                "streamServiceSettings": dict(self.servicio)}}
        if tipo == "SetVideoSettings":
            if not self.fallo_escritura:
                self.video = {clave: datos[clave] for clave in (
                    "baseWidth", "baseHeight", "outputWidth", "outputHeight")}
            return {"responseData": {}}
        if tipo == "GetVideoSettings":
            return {"responseData": dict(self.video)}
        if tipo == "GetSceneCollectionList":
            self._avanzar()
            return {"responseData": {
                "sceneCollections": list(self.colecciones),
                "currentSceneCollectionName": self.coleccion_actual}}
        if tipo == "SetCurrentSceneCollection":
            if datos["sceneCollectionName"] not in self.colecciones \
                    and datos["sceneCollectionName"] != self.coleccion_actual:
                raise obs_cliente.ObsError(
                    obs_cliente.mensaje_de_fallo_obs("600 not found"))
            self.pendientes_coleccion.append(
                [datos["sceneCollectionName"], self.demora_coleccion])
            return {"responseData": {}}
        return {"responseData": {}}

    def _avanzar(self):
        for pendiente in self.pendientes_creacion:
            pendiente[1] -= 1
        listos = [p for p in self.pendientes_creacion if p[1] <= 0]
        self.pendientes_creacion = [p for p in self.pendientes_creacion
                                    if p[1] > 0]
        for nombre, _ in listos:
            if nombre not in self.visibles:
                self.visibles.append(nombre)
        for pendiente in self.pendientes_cambio:
            pendiente[1] -= 1
        cambios = [p for p in self.pendientes_cambio if p[1] <= 0]
        self.pendientes_cambio = [p for p in self.pendientes_cambio
                                  if p[1] > 0]
        for nombre, _ in cambios:
            self.actual = nombre
        for pendiente in self.pendientes_coleccion:
            pendiente[1] -= 1
        cambios_coleccion = [p for p in self.pendientes_coleccion if p[1] <= 0]
        self.pendientes_coleccion = [p for p in self.pendientes_coleccion
                                     if p[1] > 0]
        for nombre, _ in cambios_coleccion:
            self.coleccion_actual = nombre

    def tipos(self):
        return [llamada[0] for llamada in self.llamadas]


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0
        self.siestecitas = []

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.siestecitas.append(segundos)
        self.ahora += segundos


class PrepararDestinoTest(unittest.TestCase):
    def preparar(self, doble, destino, **extras):
        reloj = RelojFalso()
        extras.setdefault("dormir", reloj.dormir)
        extras.setdefault("reloj", reloj.reloj)
        preparar_destino(doble, destino, **extras)
        return reloj

    def test_perfil_inexistente_lo_crea_y_cambia_con_esperas(self):
        doble = DobleObsDestinos(perfiles=["Viejo"], actual="Viejo")
        self.preparar(doble, Destino(perfil="Nuevo"))
        tipos = doble.tipos()
        self.assertLess(tipos.index("CreateProfile"),
                        tipos.index("SetCurrentProfile"))
        # Ningún cambio antes de que la lista lo muestre: entre la creación
        # y el cambio hay al menos una consulta a la lista.
        self.assertIn("GetProfileList", tipos[tipos.index("CreateProfile"):
                                             tipos.index("SetCurrentProfile")])
        self.assertEqual(doble.actual, "Nuevo")
        self.assertIn("Nuevo", doble.visibles)

    def test_perfil_ya_activo_no_pide_ni_crear_ni_cambiar(self):
        doble = DobleObsDestinos(perfiles=["Juego"], actual="Juego")
        self.preparar(doble, Destino(perfil="Juego"))
        self.assertNotIn("CreateProfile", doble.tipos())
        self.assertNotIn("SetCurrentProfile", doble.tipos())

    def test_transmitiendo_falla_sin_pedir_nada_mas(self):
        doble = DobleObsDestinos(perfiles=["Juego"], actual="Juego",
                                 transmision=True)
        with self.assertRaisesRegex(obs_cliente.ObsError, "mientras se transmite"):
            self.preparar(doble, Destino(perfil="Otro", servidor="s", clave="c"))
        self.assertEqual(doble.tipos(), ["GetStreamStatus"])

    def test_destino_solo_con_perfil_no_fija_servicio_ni_lienzo(self):
        doble = DobleObsDestinos(perfiles=["Juego"], actual="Juego")
        self.preparar(doble, Destino(perfil="Juego"))
        self.assertNotIn("SetStreamServiceSettings", doble.tipos())
        self.assertNotIn("SetVideoSettings", doble.tipos())

    def test_destino_completo_fija_valores_exactos(self):
        doble = DobleObsDestinos(perfiles=["Juego"], actual="Juego")
        self.preparar(doble, Destino(perfil="Juego", servidor="rtmp://srv/live",
                                     clave="secreto", ancho=1280, alto=720))
        servicio = next(d for t, d in doble.llamadas
                        if t == "SetStreamServiceSettings")
        self.assertEqual(servicio["streamServiceType"], "rtmp_custom")
        self.assertEqual(servicio["streamServiceSettings"],
                         {"server": "rtmp://srv/live", "key": "secreto"})
        video = next(d for t, d in doble.llamadas if t == "SetVideoSettings")
        self.assertEqual(video, {"baseWidth": 1280, "baseHeight": 720,
                                 "outputWidth": 1280, "outputHeight": 720})

    def test_obs_que_no_termina_falla_al_agotar_la_espera(self):
        doble = DobleObsDestinos(perfiles=["Viejo"], actual="Viejo",
                                 demora_creacion=1000, demora_cambio=1000)
        reloj = RelojFalso()
        with self.assertRaisesRegex(obs_cliente.ObsError, "no terminó"):
            preparar_destino(doble, Destino(perfil="Nuevo"), espera=0.3,
                             intervalo=0.05, dormir=reloj.dormir,
                             reloj=reloj.reloj)
        self.assertTrue(reloj.siestecitas)
        self.assertLessEqual(reloj.ahora, 0.3 + 0.05 + 1e-9)

    def test_lectura_de_vuelta_que_no_coincide_falla(self):
        doble = DobleObsDestinos(perfiles=["Juego"], actual="Juego",
                                 fallo_escritura=True)
        with self.assertRaisesRegex(obs_cliente.ObsError, "no aplicó"):
            self.preparar(doble, Destino(perfil="Juego", servidor="rtmp://s",
                                         clave="c"))

    def test_ningun_error_muestra_la_clave(self):
        clave = "CLAVE-SUPER-SECRETA-123"
        with self.subTest(caso="transmitiendo"):
            doble = DobleObsDestinos(transmision=True)
            with self.assertRaises(obs_cliente.ObsError) as contexto:
                self.preparar(doble, Destino(perfil="X", servidor="s",
                                             clave=clave))
            self.assertNotIn(clave, str(contexto.exception))
        with self.subTest(caso="lectura distinta"):
            doble = DobleObsDestinos(perfiles=["Juego"], actual="Juego",
                                     fallo_escritura=True)
            with self.assertRaises(obs_cliente.ObsError) as contexto:
                self.preparar(doble, Destino(perfil="Juego", servidor="s",
                                             clave=clave))
            self.assertNotIn(clave, str(contexto.exception))
        with self.subTest(caso="sin terminar"):
            doble = DobleObsDestinos(demora_creacion=1000, demora_cambio=1000)
            reloj = RelojFalso()
            with self.assertRaises(obs_cliente.ObsError) as contexto:
                preparar_destino(doble, Destino(perfil="N", servidor="s",
                                                clave=clave),
                                 espera=0.2, intervalo=0.05,
                                 dormir=reloj.dormir, reloj=reloj.reloj)
            self.assertNotIn(clave, str(contexto.exception))

    def test_destino_a_medias_es_error_de_programacion(self):
        with self.assertRaises(ValueError):
            Destino(perfil="X", servidor="s")
        with self.assertRaises(ValueError):
            Destino(perfil="X", clave="c")
        with self.assertRaises(ValueError):
            Destino(perfil="X", ancho=1280)
        with self.assertRaises(ValueError):
            Destino(perfil="X", alto=720)

    def test_parada_cancela_la_espera(self):
        doble = DobleObsDestinos(perfiles=["Viejo"], actual="Viejo",
                                 demora_creacion=1000, demora_cambio=1000)
        parada = threading.Event()
        reloj = RelojFalso()

        def dormir(seconds):
            parada.set()
            reloj.dormir(seconds)

        with self.assertRaisesRegex(obs_cliente.ObsError, "cancelada"):
            preparar_destino(doble, Destino(perfil="Nuevo"), parada=parada,
                             espera=10.0, intervalo=0.05, dormir=dormir,
                             reloj=reloj.reloj)


class PrepararParaTransmitirTest(unittest.TestCase):
    def preparar(self, doble, destino, **extras):
        reloj = RelojFalso()
        extras.setdefault("dormir", reloj.dormir)
        extras.setdefault("reloj", reloj.reloj)
        resultado = preparar_para_transmitir(doble, destino, **extras)
        return resultado, reloj

    def doble_medicion(self, **extras):
        # Lo medido el 13/10/2026: perfiles TikTok y YouTube, colecciones
        # «Sin Título» y «TikTok».
        opciones = {"perfiles": ["N5000-Grabacion", "Sin Título", "TikTok",
                                 "YouTube"],
                    "colecciones": ["Sin Título", "TikTok"]}
        opciones.update(extras)
        return DobleObsDestinos(**opciones)

    def test_perfil_inexistente_falla_sin_pedir_ningun_cambio(self):
        doble = self.doble_medicion(actual="YouTube",
                                    coleccion_actual="Sin Título")
        with self.assertRaisesRegex(obs_cliente.ObsError,
                                    "no tiene un perfil llamado niche"):
            self.preparar(doble, "niche")
        for pedido in ("CreateProfile", "SetCurrentProfile",
                       "SetCurrentSceneCollection", "SetVideoSettings"):
            self.assertNotIn(pedido, doble.tipos())

    def test_tiktok_elige_su_coleccion(self):
        doble = self.doble_medicion(actual="YouTube",
                                    coleccion_actual="Sin Título")
        resultado, _ = self.preparar(doble, "TikTok")
        self.assertEqual(doble.coleccion_actual, "TikTok")
        self.assertEqual(resultado["coleccion"], "TikTok")
        self.assertEqual(resultado["perfil"], "TikTok")
        self.assertEqual(resultado["destino"], "TikTok")

    def test_youtube_elige_sin_titulo(self):
        doble = self.doble_medicion(actual="TikTok",
                                    coleccion_actual="TikTok")
        resultado, _ = self.preparar(doble, "YouTube")
        self.assertEqual(doble.coleccion_actual, "Sin Título")
        self.assertEqual(resultado["coleccion"], "Sin Título")

    def test_coleccion_ya_activa_no_pide_cambiarla(self):
        doble = self.doble_medicion(actual="TikTok",
                                    coleccion_actual="TikTok")
        self.preparar(doble, "TikTok")
        self.assertNotIn("SetCurrentSceneCollection", doble.tipos())

    def test_coleccion_que_tarda_se_espera_hasta_verla(self):
        doble = self.doble_medicion(actual="YouTube",
                                    coleccion_actual="Sin Título",
                                    demora_coleccion=3)
        resultado, reloj = self.preparar(doble, "TikTok")
        self.assertEqual(resultado["coleccion"], "TikTok")
        tipos = doble.tipos()
        consultas = tipos[tipos.index("SetCurrentSceneCollection"):]
        self.assertGreaterEqual(consultas.count("GetSceneCollectionList"), 3)
        self.assertTrue(reloj.siestecitas)

    def test_coleccion_que_no_termina_falla(self):
        doble = self.doble_medicion(actual="TikTok",
                                    coleccion_actual="Sin Título",
                                    demora_coleccion=1000)
        reloj = RelojFalso()
        with self.assertRaisesRegex(obs_cliente.ObsError,
                                    "no terminó de cambiar de escenas"):
            cambiar_coleccion(doble, "TikTok", espera=0.3, intervalo=0.05,
                              dormir=reloj.dormir, reloj=reloj.reloj)

    def test_resultado_trae_el_lienzo_leido_al_final(self):
        doble = self.doble_medicion(actual="YouTube",
                                    coleccion_actual="Sin Título")
        doble.video = {"baseWidth": 720, "baseHeight": 1280,
                       "outputWidth": 720, "outputHeight": 1280}
        resultado, _ = self.preparar(doble, "TikTok")
        self.assertEqual((resultado["ancho"], resultado["alto"]),
                         (720, 1280))
        tipos = doble.tipos()
        # El lienzo se lee al final: después de cambiar perfil y colección.
        self.assertLess(tipos.index("SetCurrentProfile"),
                        tipos.index("GetVideoSettings"))
        self.assertLess(tipos.index("SetCurrentSceneCollection"),
                        tipos.index("GetVideoSettings"))

    def test_frase_destino_listo_en_sus_tres_formas(self):
        with self.subTest(forma="vertical"):
            self.assertEqual(
                frase_destino_listo({"destino": "TikTok", "ancho": 720,
                                     "alto": 1280}),
                "Listo para transmitir a TikTok. "
                "Formato vertical, 720 por 1280.")
        with self.subTest(forma="horizontal"):
            self.assertEqual(
                frase_destino_listo({"destino": "YouTube", "ancho": 1280,
                                     "alto": 720}),
                "Listo para transmitir a YouTube. "
                "Formato horizontal, 1280 por 720.")
        with self.subTest(forma="cuadrado"):
            self.assertEqual(
                frase_destino_listo({"destino": "TikTok", "ancho": 800,
                                     "alto": 800}),
                "Listo para transmitir a TikTok. "
                "Formato cuadrado, 800 por 800.")

    def test_coleccion_para(self):
        with self.subTest(caso="mismo nombre"):
            self.assertEqual(
                coleccion_para("TikTok", ["Sin Título", "TikTok"]), "TikTok")
        with self.subTest(caso="primera que no es destino"):
            self.assertEqual(
                coleccion_para("YouTube", ["Sin Título", "TikTok"]),
                "Sin Título")
        with self.subTest(caso="sin colecciones"):
            self.assertIsNone(coleccion_para("TikTok", []))
        with self.subTest(caso="todas son destinos"):
            self.assertIsNone(coleccion_para("YouTube", ["TikTok"]))


if __name__ == "__main__":
    unittest.main()

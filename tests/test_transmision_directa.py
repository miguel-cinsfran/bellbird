"""Pruebas de las decisiones del botón directo, sin ventana ni OBS."""

import unittest

from ytchat.obs import transmision_directa
from ytchat.obs.transmision_directa import (
    FalloCierreYoutube, Preparacion, boton_visible, es_directo_propio,
    etiqueta, finalizar, preparar)


class EsDirectoPropioTest(unittest.TestCase):
    def test_conexion_pedida_por_la_transmision_en_youtube(self):
        self.assertTrue(es_directo_propio(False, "", "", True))

    def test_conexion_pedida_por_la_transmision_en_tiktok(self):
        self.assertTrue(es_directo_propio(True, "otro", "mio", True))

    def test_tiktok_mismo_usuario_sin_importar_mayusculas(self):
        self.assertTrue(es_directo_propio(True, "Amigo", "amigo", False))

    def test_tiktok_con_arroba_coincide_con_el_guardado(self):
        self.assertTrue(es_directo_propio(True, "@amigo", "amigo", False))

    def test_tiktok_directo_de_otro(self):
        self.assertFalse(es_directo_propio(True, "otro", "mio", False))

    def test_tiktok_sin_usuario_en_la_sesion(self):
        self.assertFalse(es_directo_propio(True, "", "mio", False))

    def test_tiktok_sin_usuario_guardado(self):
        self.assertFalse(es_directo_propio(True, "mio", "", False))

    def test_youtube_sin_conexion_pedida_aunque_coincida(self):
        self.assertFalse(es_directo_propio(False, "mio", "mio", False))

    def test_video_grabado_de_youtube_sin_conexion_pedida(self):
        self.assertFalse(es_directo_propio(False, "", "", False))


class BotonVisibleTest(unittest.TestCase):
    def test_pantalla_de_inicio_visible(self):
        self.assertTrue(boton_visible(False, False, False, False))

    def test_pantalla_de_inicio_visible_aunque_se_transmita(self):
        self.assertTrue(boton_visible(False, False, False, True))

    def test_conectando_oculto(self):
        self.assertFalse(boton_visible(False, True, False, False))
        self.assertFalse(boton_visible(False, True, False, True))

    def test_conectando_al_propio_visible(self):
        self.assertTrue(boton_visible(False, True, True, False))

    def test_directo_de_otro_oculto(self):
        self.assertFalse(boton_visible(True, False, False, False))

    def test_directo_de_otro_oculto_mientras_se_transmite(self):
        self.assertFalse(boton_visible(True, False, False, True))

    def test_directo_propio_visible(self):
        self.assertTrue(boton_visible(True, False, True, False))

    def test_directo_propio_visible_mientras_se_transmite(self):
        self.assertTrue(boton_visible(True, False, True, True))


class EtiquetaTest(unittest.TestCase):
    def test_sin_transmitir_invita_a_transmitir(self):
        self.assertEqual(etiqueta(False),
                         ("Transm&itir en directo", "Transmitir en directo"))

    def test_transmitiendo_invita_a_finalizar(self):
        self.assertEqual(etiqueta(True),
                         ("&Finalizar directo", "Finalizar directo"))

    def test_deteniendo_avisa_que_se_espera_a_obs(self):
        self.assertEqual(
            etiqueta(True, deteniendo=True),
            ("Deteniendo el directo",
             "Deteniendo el directo, esperando a OBS"))

    def test_deteniendo_manda_aunque_no_transmita(self):
        self.assertEqual(
            etiqueta(False, deteniendo=True),
            ("Deteniendo el directo",
             "Deteniendo el directo, esperando a OBS"))


class GestorFalso:
    def __init__(self, transmitiendo=False, perfil="TikTok", fallo=None,
                 resultado_preparar=None):
        self.transmitiendo = transmitiendo
        self.perfil = perfil
        self.fallo = fallo
        self.resultado_preparar = resultado_preparar
        self.llamadas = []
        self.cierres = 0

    def conectar(self, *args, **kwargs):
        self.llamadas.append("conectar")

    def estado_transmision(self, *args, **kwargs):
        self.llamadas.append("estado")
        return {"outputActive": self.transmitiendo}

    def perfil_actual(self, *args, **kwargs):
        self.llamadas.append("perfil")
        return self.perfil

    def preparar_destino(self, destino, *args, **kwargs):
        self.llamadas.append(("preparar", destino))
        if self.fallo == "preparar":
            raise RuntimeError("boom al preparar")
        return self.resultado_preparar

    def revisar(self, destino, *args, **kwargs):
        self.llamadas.append(("revisar", destino))
        return ("revision", destino)

    def detener_transmision(self, *args, **kwargs):
        self.llamadas.append("detener")

    def cerrar(self, *args, **kwargs):
        self.llamadas.append("cerrar")
        self.cierres += 1


def _asegurar(registro, conectar, al_anunciar=None, parada=None):
    registro.append(("asegurar", conectar, al_anunciar, parada))


class PrepararTest(unittest.TestCase):
    def _preparar(self, gestor, destino="TikTok", parada=None):
        registro = []
        anuncios = []
        resultado = preparar(
            gestor, destino,
            lambda conectar, al_anunciar=None, parada=None: _asegurar(
                registro, conectar, al_anunciar, parada),
            anuncios.append, parada=parada)
        return resultado, registro, anuncios

    def test_orden_exacta_de_llamadas(self):
        gestor = GestorFalso(transmitiendo=False, perfil="TikTok")
        resultado, registro, anuncios = self._preparar(gestor)
        self.assertFalse(resultado.ya_transmitiendo)
        self.assertEqual(resultado.revision, ("revision", "TikTok"))
        self.assertEqual(len(registro), 1)
        _nombre, conectar, al_anunciar, parada = registro[0]
        self.assertTrue(callable(conectar))
        self.assertTrue(callable(al_anunciar))
        self.assertIsNone(parada)
        self.assertEqual(
            gestor.llamadas,
            ["conectar", "estado", "perfil", ("preparar", "TikTok"),
             ("revisar", "TikTok"), "cerrar"])
        self.assertEqual(anuncios, [])

    def test_ya_transmitiendo_no_prepara_ni_revisa(self):
        gestor = GestorFalso(transmitiendo=True, perfil="YouTube")
        resultado, _registro, anuncios = self._preparar(gestor, "TikTok")
        self.assertTrue(resultado.ya_transmitiendo)
        self.assertIsNone(resultado.revision)
        self.assertEqual(gestor.llamadas, ["conectar", "estado", "cerrar"])
        self.assertEqual(anuncios, [])

    def test_anuncia_solo_cuando_el_perfil_es_otro(self):
        gestor = GestorFalso(transmitiendo=False, perfil="YouTube")
        _resultado, _registro, anuncios = self._preparar(gestor, "TikTok")
        self.assertEqual(anuncios, ["Preparando OBS para TikTok."])

    def test_cierra_aunque_preparar_levante(self):
        gestor = GestorFalso(transmitiendo=False, perfil="TikTok",
                             fallo="preparar")
        with self.assertRaises(RuntimeError):
            self._preparar(gestor)
        self.assertEqual(gestor.llamadas[-1], "cerrar")

    def test_la_parada_llega_a_asegurar(self):
        gestor = GestorFalso()
        parada = object()
        _resultado, registro, _anuncios = self._preparar(
            gestor, parada=parada)
        self.assertIs(registro[0][3], parada)

    def test_perfil_creado_se_anuncia(self):
        gestor = GestorFalso(transmitiendo=False, perfil="Sin Título",
                             resultado_preparar={"perfil_creado": True})
        _resultado, _registro, anuncios = self._preparar(gestor, "YouTube")
        self.assertIn("Se creó en OBS el perfil YouTube.", anuncios)

    def test_sin_perfil_creado_no_hay_anuncio_extra(self):
        with self.subTest(caso="None"):
            gestor = GestorFalso(transmitiendo=False, perfil="YouTube",
                                 resultado_preparar=None)
            _resultado, _registro, anuncios = self._preparar(gestor, "YouTube")
            self.assertNotIn("Se creó en OBS el perfil YouTube.", anuncios)
        with self.subTest(caso="False"):
            gestor = GestorFalso(transmitiendo=False, perfil="YouTube",
                                 resultado_preparar={"perfil_creado": False})
            _resultado, _registro, anuncios = self._preparar(gestor, "YouTube")
            self.assertNotIn("Se creó en OBS el perfil YouTube.", anuncios)


class FinalizarTest(unittest.TestCase):
    def test_transmitiendo_detiene_y_cierra(self):
        gestor = GestorFalso(transmitiendo=True)
        finalizar(gestor)
        self.assertEqual(gestor.llamadas, ["conectar", "estado", "detener",
                                           "cerrar"])

    def test_sin_transmision_solo_cierra(self):
        gestor = GestorFalso(transmitiendo=False)
        finalizar(gestor)
        self.assertEqual(gestor.llamadas, ["conectar", "estado", "cerrar"])

    def test_cierra_aunque_detener_levante(self):
        gestor = GestorFalso(transmitiendo=True)

        def _romper(*args, **kwargs):
            raise RuntimeError("boom al detener")
        gestor.detener_transmision = _romper
        with self.assertRaises(RuntimeError):
            finalizar(gestor)
        self.assertEqual(gestor.llamadas[-1], "cerrar")

    def test_con_perfil_youtube_llama_despues_de_detener(self):
        gestor = GestorFalso(transmitiendo=True, perfil="YouTube")
        llamadas = []
        finalizar(gestor,
                  finalizar_youtube=lambda: llamadas.append("youtube"))
        self.assertEqual(llamadas, ["youtube"])
        self.assertLess(gestor.llamadas.index("detener"),
                        len(gestor.llamadas) - 1)
        self.assertEqual(gestor.llamadas[-1], "cerrar")
        self.assertIn("perfil", gestor.llamadas)
        self.assertLess(gestor.llamadas.index("perfil"),
                        gestor.llamadas.index("detener"))

    def test_con_otro_perfil_no_toca_youtube(self):
        gestor = GestorFalso(transmitiendo=True, perfil="TikTok")
        llamadas = []
        finalizar(gestor,
                  finalizar_youtube=lambda: llamadas.append("youtube"))
        self.assertEqual(llamadas, [])
        self.assertIn("detener", gestor.llamadas)

    def test_sin_callable_no_lee_el_perfil(self):
        gestor = GestorFalso(transmitiendo=True, perfil="YouTube")
        finalizar(gestor)
        self.assertNotIn("perfil", gestor.llamadas)

    def test_fallo_en_youtube_sale_como_fallo_de_cierre(self):
        gestor = GestorFalso(transmitiendo=True, perfil="YouTube")

        def _romper():
            raise RuntimeError("cuota agotada")
        with self.assertRaises(FalloCierreYoutube) as contexto:
            finalizar(gestor, finalizar_youtube=_romper)
        self.assertIn("YouTube no confirmó", str(contexto.exception))
        self.assertEqual(gestor.llamadas[-1], "cerrar")


if __name__ == "__main__":
    unittest.main()

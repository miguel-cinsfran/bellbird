"""Pruebas del sondeo de modelos gratis con la clave del proveedor.

Sin wx y sin red: el envío se inyecta. Leer, guardar y olvidar se prueban
sobre un archivo de verdad en un directorio temporal.
"""

import tempfile
import time
import unittest
from pathlib import Path

from bellbird.ai import catalogo
from bellbird.ai import protocolos
from bellbird.ai import proveedores
from bellbird.ai import sondeo_gratis


def _muestra_de(cantidad):
    base = "https://generativelanguage.googleapis.com/v1beta"
    nombres = ["uno", "dos", "tres", "cuatro",
               "cinco", "seis", "siete", "ocho"]
    modelos = []
    for nombre in nombres[:cantidad]:
        modelos.append({
            "id": f"gemini-{nombre}",
            "nombre": f"Gemini {nombre}",
            "protocolo": protocolos.GEMINI,
            "base": base,
        })
    return {
        "version": catalogo.VERSION,
        "fecha": "2026-10-21",
        "proveedores": {
            "google": {"nombre": "Google", "modelos": modelos},
        },
    }


def _muestra():
    return _muestra_de(3)


class TestClasificar(unittest.TestCase):

    def test_sin_error_es_responde(self):
        self.assertEqual(sondeo_gratis.clasificar(None),
                         sondeo_gratis.RESPONDE)

    def test_cuota_con_el_cero_es_de_pago(self):
        error = protocolos.ErrorIA(
            protocolos.CUOTA, "cuota", sin_nivel_gratuito=True)
        self.assertEqual(sondeo_gratis.clasificar(error),
                         sondeo_gratis.DE_PAGO)

    def test_cuota_sin_el_cero_es_sin_saber(self):
        error = protocolos.ErrorIA(protocolos.CUOTA, "cuota")
        self.assertEqual(sondeo_gratis.clasificar(error),
                         sondeo_gratis.SIN_SABER)

    def test_servidor_es_sin_saber(self):
        error = protocolos.ErrorIA(protocolos.SERVIDOR, "503")
        self.assertEqual(sondeo_gratis.clasificar(error),
                         sondeo_gratis.SIN_SABER)

    def test_clave_rechazada_es_clave_mala(self):
        error = protocolos.ErrorIA(protocolos.CLAVE_RECHAZADA, "no")
        self.assertEqual(sondeo_gratis.clasificar(error),
                         sondeo_gratis.CLAVE_MALA)

    def test_sin_red_y_tiempo_agotado_son_sin_saber(self):
        for tipo in (protocolos.SIN_RED, protocolos.TIEMPO_AGOTADO):
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    sondeo_gratis.clasificar(
                        protocolos.ErrorIA(tipo, "red")),
                    sondeo_gratis.SIN_SABER)

    def test_un_error_ajeno_es_sin_saber(self):
        self.assertEqual(sondeo_gratis.clasificar(ValueError("otro")),
                         sondeo_gratis.SIN_SABER)


class TestMarcas(unittest.TestCase):

    def test_sin_de_pago_la_clave_no_es_gratuita(self):
        resultados = {
            "gemini-uno": sondeo_gratis.RESPONDE,
            "gemini-dos": sondeo_gratis.SIN_SABER,
        }
        self.assertEqual(
            sondeo_gratis.marcas(resultados),
            {"gemini-uno": sondeo_gratis.MARCA_CON_TU_CLAVE})

    def test_con_de_pago_la_clave_es_gratuita(self):
        resultados = {
            "gemini-uno": sondeo_gratis.RESPONDE,
            "gemini-dos": sondeo_gratis.DE_PAGO,
            "gemini-tres": sondeo_gratis.SIN_SABER,
        }
        self.assertEqual(
            sondeo_gratis.marcas(resultados),
            {"gemini-uno": sondeo_gratis.MARCA_GRATIS})

    def test_clave_mala_no_deja_marcas(self):
        self.assertEqual(
            sondeo_gratis.marcas(
                {"gemini-uno": sondeo_gratis.CLAVE_MALA}), {})


class TestSondear(unittest.TestCase):

    def test_recorre_los_modelos_y_clasifica_cada_uno(self):
        def enviar(pedido, clave, tiempo_espera):
            if "gemini-dos" in pedido.url:
                raise protocolos.ErrorIA(
                    protocolos.CUOTA, "cuota", sin_nivel_gratuito=True)
            if "gemini-tres" in pedido.url:
                raise protocolos.ErrorIA(protocolos.SERVIDOR, "503")
            return protocolos.Respuesta("OK")

        resultados = sondeo_gratis.sondear(
            proveedores.por_id("gemini"), _muestra(), "clave", enviar, 20)
        self.assertEqual(resultados, {
            "gemini-uno": sondeo_gratis.RESPONDE,
            "gemini-dos": sondeo_gratis.DE_PAGO,
            "gemini-tres": sondeo_gratis.SIN_SABER,
        })

    def test_el_pedido_es_el_minimo_de_opciones_ia(self):
        from bellbird.ai import opciones_ia
        pedidos = []

        def enviar(pedido, clave, tiempo_espera):
            pedidos.append((pedido, clave, tiempo_espera))
            return protocolos.Respuesta("OK")

        sondeo_gratis.sondear(
            proveedores.por_id("gemini"), _muestra(), "clave", enviar, 20)
        self.assertEqual(len(pedidos), 3)
        for pedido, clave, tiempo_espera in pedidos:
            self.assertEqual(clave, "clave")
            self.assertEqual(tiempo_espera, 20)
            self.assertIn(opciones_ia.TEXTO_PEDIDO_PRUEBA,
                          str(pedido.cuerpo))

    def test_para_en_clave_mala_y_devuelve_solo_ese_resultado(self):
        llamadas = []

        def enviar(pedido, clave, tiempo_espera):
            llamadas.append(pedido.url)
            if "gemini-dos" in pedido.url:
                raise protocolos.ErrorIA(
                    protocolos.CLAVE_RECHAZADA, "no")
            return protocolos.Respuesta("OK")

        resultados = sondeo_gratis.sondear(
            proveedores.por_id("gemini"), _muestra_de(8), "clave",
            enviar, 20)
        self.assertEqual(
            resultados, {"gemini-dos": sondeo_gratis.CLAVE_MALA})
        self.assertEqual(len(llamadas), 4)
        self.assertFalse(any("gemini-cinco" in url for url in llamadas))

    def test_consulta_de_a_cuatro_y_conserva_el_orden_del_catalogo(self):
        modelos = _muestra_de(8)
        esperados = [modelo["id"] for modelo in
                     modelos["proveedores"]["google"]["modelos"]]

        def enviar(pedido, clave, tiempo_espera):
            time.sleep(0.2)
            return protocolos.Respuesta("OK")

        inicio = time.monotonic()
        resultados = sondeo_gratis.sondear(
            proveedores.por_id("gemini"), modelos, "clave", enviar, 20)
        transcurrido = time.monotonic() - inicio
        self.assertLess(transcurrido, 1.0)
        self.assertEqual(list(resultados), esperados)
        self.assertEqual(set(resultados.values()),
                         {sondeo_gratis.RESPONDE})


class TestArchivo(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "gratis_ia.json"

    def test_ausente_se_lee_sin_marcas(self):
        self.assertEqual(sondeo_gratis.leer(self.ruta, "gemini"), {})

    def test_roto_se_lee_sin_marcas(self):
        self.ruta.write_text("{roto", encoding="utf-8")
        self.assertEqual(sondeo_gratis.leer(self.ruta, "gemini"), {})

    def test_guardar_y_leer_conservan_cada_proveedor(self):
        sondeo_gratis.guardar(
            self.ruta, "gemini", {"gemini-uno": "gratis"}, "2026-10-21")
        sondeo_gratis.guardar(
            self.ruta, "openai", {"gpt-uno": "funciona con tu clave"},
            "2026-10-22")
        self.assertTrue(self.ruta.is_file())
        self.assertEqual(
            sondeo_gratis.leer(self.ruta, "gemini"),
            {"gemini-uno": "gratis"})
        self.assertEqual(
            sondeo_gratis.leer(self.ruta, "openai"),
            {"gpt-uno": "funciona con tu clave"})

    def test_olvidar_borra_solo_ese_proveedor(self):
        sondeo_gratis.guardar(
            self.ruta, "gemini", {"gemini-uno": "gratis"}, "2026-10-21")
        sondeo_gratis.guardar(
            self.ruta, "openai", {"gpt-uno": "gratis"}, "2026-10-22")
        sondeo_gratis.olvidar(self.ruta, "gemini")
        self.assertEqual(sondeo_gratis.leer(self.ruta, "gemini"), {})
        self.assertEqual(
            sondeo_gratis.leer(self.ruta, "openai"),
            {"gpt-uno": "gratis"})


if __name__ == "__main__":
    unittest.main()

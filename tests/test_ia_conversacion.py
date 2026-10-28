"""Pruebas de la conversación de IA, sin red ni disco."""

import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.ai import conversacion
from ytchat.ai.conversacion import Conversacion
from ytchat.ai import protocolos

IMAGEN_UNO = b"\xff\xd8\xffuno\xff\xd9"
IMAGEN_DOS = b"\xff\xd8\xffdos\xff\xd9"

BASE_SISTEMA = ("Eres el asistente de un streamer ciego que transmite con OBS. "
                 "Responde siempre en español, en prosa breve, sin markdown, sin "
                 "listas, sin títulos y sin emojis: la respuesta se lee con un "
                 "lector de pantalla. Ve directo a lo que se pregunta. Si algo no "
                 "se distingue en la imagen, dilo en vez de suponer. Cuando "
                 "recibas la lista de fuentes de OBS, usa sus nombres para decir "
                 "qué es cada cosa que se ve.")


def _conversacion_con_dos_turnos():
    charla = Conversacion()
    charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
    primero = charla.preparar("¿Qué se ve?", conversacion.PREGUNTA_INICIAL)
    charla.confirmar(primero[-1].texto, "Se ve algo")
    segundo = charla.preparar("¿Y ahora?", conversacion.PREGUNTA_INICIAL)
    charla.confirmar(segundo[-1].texto, "Se ve otra cosa")
    return charla


def _revisar_invariantes(test, charla):
    imagenes = [m.imagen for m in charla.mensajes if m.imagen is not None]
    test.assertEqual(len(imagenes), len(set(imagenes)))
    for mensaje in charla.mensajes:
        if mensaje.imagen is not None:
            test.assertEqual(mensaje.rol, "usuario")
    capturas = [f for f in charla.filas if f.startswith("Captura: ")]
    esperadas = len(imagenes) + (1 if charla._pendiente is not None else 0)
    test.assertEqual(len(capturas), esperadas)
    if charla._pendiente is not None:
        test.assertEqual(len(capturas), len(imagenes) + 1)
        test.assertEqual(
            capturas[-1],
            "Captura: {}, {}".format(charla._pendiente.fuente,
                                     charla._pendiente.hora))
    for i, mensaje in enumerate(charla.mensajes):
        test.assertEqual(mensaje.rol,
                         "usuario" if i % 2 == 0 else "asistente")
    if charla.mensajes:
        test.assertEqual(charla.mensajes[0].rol, "usuario")
    if charla.hay_captura():
        repetido = charla.preparar("otra", conversacion.PREGUNTA_INICIAL)
        otra_vez = charla.preparar("otra", conversacion.PREGUNTA_INICIAL)
        test.assertEqual(repetido, otra_vez)


class TestPreguntaYPrompt(unittest.TestCase):

    def test_pregunta_inicial_exacta(self):
        self.assertEqual(
            conversacion.PREGUNTA_INICIAL,
            "Revisa esta captura de la transmisión como si fueras el público. "
            "Primero di si hay algún problema: algo en negro, cortado, tapado "
            "por otra cosa, fuera de cuadro, borroso o con texto que no se "
            "lee. Si no hay ninguno, empieza diciendo que todo se ve bien. "
            "Después describe en pocas frases qué se ve y dónde está cada "
            "cosa, con posiciones simples como arriba a la izquierda o en el "
            "centro, y menciona brevemente los colores y los adornos.")

    def test_pregunta_nombra_problema_antes_que_colores(self):
        pregunta = conversacion.PREGUNTA_INICIAL.lower()
        self.assertIn("problema", pregunta)
        self.assertIn("colores", pregunta)
        self.assertLess(pregunta.index("problema"),
                        pregunta.index("colores"))

    def test_largos(self):
        self.assertEqual(
            (conversacion.CORTA, conversacion.MEDIA, conversacion.LARGA),
            ("corta", "media", "larga"))

    def test_prompt_sin_descripcion(self):
        self.assertEqual(conversacion.prompt_sistema(""), BASE_SISTEMA)

    def test_prompt_con_descripcion(self):
        self.assertEqual(
            conversacion.prompt_sistema("Juego al aire"),
            BASE_SISTEMA + "\n\nLo que OBS informa de la escena al aire:\n"
            "Juego al aire")

    def test_prompt_base_en_un_parrafo(self):
        self.assertNotIn("\n", conversacion.prompt_sistema(""))


class TestMaxTokens(unittest.TestCase):

    def test_presupuestos(self):
        self.assertEqual(conversacion.max_tokens("corta", False, None), 400)
        self.assertEqual(conversacion.max_tokens("media", False, None), 900)
        self.assertEqual(conversacion.max_tokens("larga", False, None), 2000)
        self.assertEqual(
            conversacion.max_tokens("rara", False, None), 900)

    def test_piensa_suma_cuatro_mil(self):
        self.assertEqual(conversacion.max_tokens("corta", True, None), 4400)
        self.assertEqual(conversacion.max_tokens("media", True, None), 4900)
        self.assertEqual(conversacion.max_tokens("larga", True, None), 6000)

    def test_tope_recorta(self):
        self.assertEqual(conversacion.max_tokens("larga", False, 64), 64)
        self.assertEqual(conversacion.max_tokens("larga", True, 5000), 5000)
        self.assertEqual(
            conversacion.max_tokens("corta", False, 10000), 400)

    def test_propiedad_de_orden_y_piensa(self):
        for piensa in (False, True):
            for tope in (None, 2001, 2500, 100000):
                with self.subTest(piensa=piensa, tope=tope):
                    corta = conversacion.max_tokens("corta", piensa, tope)
                    media = conversacion.max_tokens("media", piensa, tope)
                    larga = conversacion.max_tokens("larga", piensa, tope)
                    self.assertLessEqual(corta, media)
                    self.assertLessEqual(media, larga)
                    sin_pensar = conversacion.max_tokens(
                        "media", False, tope)
                    con_pensar = conversacion.max_tokens(
                        "media", True, tope)
                    self.assertGreaterEqual(con_pensar, sin_pensar)


class TestPreparar(unittest.TestCase):

    def test_sin_captura_no_gasta(self):
        charla = Conversacion()
        with self.assertRaises(conversacion.SinCaptura):
            charla.preparar("hola", conversacion.PREGUNTA_INICIAL)
        self.assertEqual(charla.mensajes, [])
        self.assertEqual(charla.filas, [])

    def test_vacia_con_pendiente_usa_la_inicial(self):
        charla = Conversacion()
        charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
        for texto in ("", "   "):
            with self.subTest(texto=repr(texto)):
                pedido = charla.preparar(
                    texto, conversacion.PREGUNTA_INICIAL)
                self.assertEqual(len(pedido), 1)
                self.assertEqual(pedido[0].texto,
                                 conversacion.PREGUNTA_INICIAL)
                self.assertIs(pedido[0].imagen, IMAGEN_UNO)

    def test_vacia_sin_pendiente_es_sin_texto(self):
        charla = _conversacion_con_dos_turnos()
        with self.assertRaises(conversacion.SinTexto):
            charla.preparar("  ", conversacion.PREGUNTA_INICIAL)

    def test_no_cambia_nada(self):
        charla = _conversacion_con_dos_turnos()
        charla.agregar_captura(IMAGEN_DOS, "TikTok", "10:01")
        antes_mensajes = list(charla.mensajes)
        antes_filas = list(charla.filas)
        charla.preparar("¿Qué hay?", conversacion.PREGUNTA_INICIAL)
        self.assertEqual(charla.mensajes, antes_mensajes)
        self.assertEqual(charla.filas, antes_filas)
        self.assertIsNotNone(charla._pendiente)

    def test_suma_historial_y_pendiente(self):
        charla = _conversacion_con_dos_turnos()
        charla.agregar_captura(IMAGEN_DOS, "TikTok", "10:01")
        pedido = charla.preparar("¿Qué hay?", conversacion.PREGUNTA_INICIAL)
        self.assertEqual(len(pedido), 5)
        self.assertEqual([m.texto for m in pedido[:4]],
                         ["¿Qué se ve?", "Se ve algo",
                          "¿Y ahora?", "Se ve otra cosa"])
        self.assertEqual(pedido[4].texto, "¿Qué hay?")
        self.assertIs(pedido[4].imagen, IMAGEN_DOS)
        self.assertIs(pedido[0].imagen, IMAGEN_UNO)
        self.assertIsNone(pedido[2].imagen)


class TestFilasYReemplazo(unittest.TestCase):

    def test_filas_de_captura_pregunta_y_respuesta(self):
        charla = Conversacion()
        charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
        self.assertEqual(charla.filas, ["Captura: OBS, 10:00"])
        pedido = charla.preparar("¿Qué se ve?", conversacion.PREGUNTA_INICIAL)
        charla.confirmar(pedido[-1].texto, "Se ve algo")
        self.assertEqual(charla.filas, ["Captura: OBS, 10:00",
                                        "Pregunta: ¿Qué se ve?",
                                        "Respuesta: Se ve algo"])

    def test_reemplazo_quita_la_fila_anterior(self):
        charla = Conversacion()
        charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
        charla.agregar_captura(IMAGEN_DOS, "TikTok", "10:01")
        self.assertEqual(charla.filas, ["Captura: TikTok, 10:01"])
        pedido = charla.preparar("¿Qué hay?", conversacion.PREGUNTA_INICIAL)
        self.assertIs(pedido[-1].imagen, IMAGEN_DOS)

    def test_confirmar_vacia_la_pendiente_y_deja_reintentar(self):
        charla = Conversacion()
        charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
        pedido = charla.preparar("¿Qué se ve?", conversacion.PREGUNTA_INICIAL)
        charla.confirmar(pedido[-1].texto, "Se ve algo")
        self.assertIsNone(charla._pendiente)
        self.assertTrue(charla.hay_captura())
        segundo = charla.preparar("¿Y ahora?", conversacion.PREGUNTA_INICIAL)
        self.assertIsNone(segundo[-1].imagen)

    def test_nueva_vacia_todo_y_cambia_la_sesion(self):
        charla = _conversacion_con_dos_turnos()
        sesion_vieja = charla.sesion
        charla.nueva()
        self.assertEqual(charla.mensajes, [])
        self.assertEqual(charla.filas, [])
        self.assertFalse(charla.hay_captura())
        self.assertNotEqual(charla.sesion, sesion_vieja)
        with self.assertRaises(conversacion.SinCaptura):
            charla.preparar("hola", conversacion.PREGUNTA_INICIAL)

    def test_hay_captura_con_pendiente_o_enviada(self):
        charla = Conversacion()
        self.assertFalse(charla.hay_captura())
        charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
        self.assertTrue(charla.hay_captura())
        pedido = charla.preparar("¿Qué se ve?", conversacion.PREGUNTA_INICIAL)
        charla.confirmar(pedido[-1].texto, "Se ve algo")
        self.assertTrue(charla.hay_captura())


class TestPseudoFilas(unittest.TestCase):
    """Bajo pseudotraducción, las filas marcan sus prefijos propios."""

    def test_filas_marcan_prefijos_y_conservan_datos(self):
        charla = Conversacion()
        with con_pseudo():
            charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
            pedido = charla.preparar("", conversacion.PREGUNTA_INICIAL)
            charla.confirmar(pedido[-1].texto, "Se ve algo")
            filas = list(charla.filas)
        self.assertEqual(len(filas), 3)
        for fila in filas:
            with self.subTest(fila=fila):
                self.assertTrue(fila.startswith("[¡"), fila)
        for dato in ("OBS", "10:00", "Se ve algo"):
            with self.subTest(dato=dato):
                self.assertTrue(any(dato in fila for fila in filas), filas)

class TestInvariantes(unittest.TestCase):

    def test_secuencias(self):
        secuencias = [
            ["captura", "pregunta", "pregunta", "captura-vacia",
             "pregunta"],
            ["captura", "captura", "pregunta"],
            ["captura", "pregunta", "nueva", "captura-vacia"],
        ]
        for numero, pasos in enumerate(secuencias):
            with self.subTest(secuencia=numero):
                charla = Conversacion()
                _revisar_invariantes(self, charla)
                for paso in pasos:
                    if paso == "captura":
                        charla.agregar_captura(
                            IMAGEN_UNO, "OBS", "10:00")
                    elif paso == "captura-vacia":
                        charla.agregar_captura(
                            IMAGEN_DOS, "TikTok", "10:01")
                        pedido = charla.preparar(
                            "  ", conversacion.PREGUNTA_INICIAL)
                        charla.confirmar(pedido[-1].texto, "Otra vista")
                    elif paso == "pregunta":
                        pedido = charla.preparar(
                            "¿Qué se ve?", conversacion.PREGUNTA_INICIAL)
                        charla.confirmar(pedido[-1].texto, "Se ve algo")
                    elif paso == "nueva":
                        charla.nueva()
                    _revisar_invariantes(self, charla)


def _tres_pedidos():
    charla = Conversacion()
    charla.agregar_captura(IMAGEN_UNO, "OBS", "10:00")
    primero = charla.preparar("¿Qué se ve?", conversacion.PREGUNTA_INICIAL)
    charla.confirmar(primero[-1].texto, "Se ve algo")
    segundo = charla.preparar("¿Y ahora?", conversacion.PREGUNTA_INICIAL)
    charla.confirmar(segundo[-1].texto, "Se ve otra cosa")
    charla.agregar_captura(IMAGEN_DOS, "TikTok", "10:01")
    tercero = charla.preparar("   ", conversacion.PREGUNTA_INICIAL)
    charla.confirmar(tercero[-1].texto, "Otra vista")
    return [primero, segundo, tercero]


def _imagenes_y_textos(protocolo, cuerpo):
    if protocolo == protocolos.CHAT:
        turnos = cuerpo["messages"][1:]
        imagenes = [i for i, t in enumerate(turnos)
                    if isinstance(t.get("content"), list)
                    and any(p.get("type") == "image_url"
                            for p in t["content"])]
        textos = [t for t in turnos if t["role"] == "user"]
        sistema = cuerpo["messages"][0]
        lugar_sistema = sistema.get("content", "")
    elif protocolo == protocolos.RESPONSES:
        turnos = cuerpo["input"]
        imagenes = [i for i, t in enumerate(turnos)
                    if any(p.get("type") == "input_image"
                           for p in t["content"])]
        textos = [t for t in turnos if t["role"] == "user"]
        lugar_sistema = cuerpo.get("instructions", "")
    elif protocolo == protocolos.ANTHROPIC:
        turnos = cuerpo["messages"]
        imagenes = [i for i, t in enumerate(turnos)
                    if isinstance(t.get("content"), list)
                    and any(b.get("type") == "image"
                            for b in t["content"])]
        textos = [t for t in turnos if t["role"] == "user"]
        lugar_sistema = cuerpo.get("system", "")
    else:
        turnos = cuerpo["contents"]
        imagenes = [i for i, t in enumerate(turnos)
                    if any("inline_data" in p for p in t["parts"])]
        textos = [t for t in turnos if t["role"] == "user"]
        partes = cuerpo.get("systemInstruction", {}).get("parts", [])
        lugar_sistema = "".join(p.get("text", "") for p in partes)
    return imagenes, textos, lugar_sistema


class TestCableado(unittest.TestCase):

    def test_turnos_usan_lo_que_devuelve_preparar(self):
        pedidos = _tres_pedidos()
        sistema = conversacion.prompt_sistema("Juego al aire")
        esperados = [
            {"largo": 1, "imagenes": [0], "usuarios": ["¿Qué se ve?"]},
            {"largo": 3, "imagenes": [0],
             "usuarios": ["¿Qué se ve?", "¿Y ahora?"]},
            {"largo": 5, "imagenes": [0, 4],
             "usuarios": ["¿Qué se ve?", "¿Y ahora?",
                          conversacion.PREGUNTA_INICIAL]},
        ]
        protocolos_cuatro = (protocolos.CHAT, protocolos.RESPONSES,
                             protocolos.ANTHROPIC, protocolos.GEMINI)
        for numero, (pedido, esperado) in enumerate(zip(pedidos, esperados)):
            with self.subTest(turno=numero + 1):
                self.assertEqual(len(pedido), esperado["largo"])
                for protocolo in protocolos_cuatro:
                    with self.subTest(protocolo=protocolo):
                        armado = protocolos.armar_pedido(
                            protocolo, "https://ejemplo.com/v1", "modelo",
                            "clave", sistema, pedido, 900)
                        imagenes, textos, lugar = _imagenes_y_textos(
                            protocolo, armado.cuerpo)
                        self.assertEqual(imagenes, esperado["imagenes"])
                        self.assertEqual(len(textos), len(esperado["usuarios"]))
                        crudos = [str(t) for t in textos]
                        for crudo, usuario in zip(crudos,
                                                  esperado["usuarios"]):
                            self.assertIn(usuario, crudo)
                        self.assertIn("Eres el asistente de un streamer ciego",
                                      lugar)
                        self.assertIn("Juego al aire", lugar)


if __name__ == "__main__":
    unittest.main()

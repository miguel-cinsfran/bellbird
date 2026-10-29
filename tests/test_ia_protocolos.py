"""Pruebas de los protocolos de IA, sin red ni disco."""

import base64
import json
import unittest

from bellbird.ai import protocolos


IMAGEN = b"\xff\xd8\xfffoto-de-prueba\xff\xd9"
BASE = "https://opencode.ai/inference/go/openai/v1"
MODELO = "modelo-de-prueba"
CLAVE = "clave-de-prueba"
SISTEMA = "Respondé en una palabra."


def _tres_turnos():
    return [
        protocolos.Mensaje("usuario", "¿De qué color es?", IMAGEN),
        protocolos.Mensaje("asistente", "Es una prueba."),
        protocolos.Mensaje("usuario", "¿Y ahora?"),
    ]


def _pedido(protocolo, mensajes=None, modelo=MODELO, base=BASE,
            max_tokens=64):
    return protocolos.armar_pedido(
        protocolo, base, modelo, CLAVE, SISTEMA,
        _tres_turnos() if mensajes is None else mensajes, max_tokens)


class TestPedidoChat(unittest.TestCase):

    def test_direccion_cabeceras_y_cuerpo(self):
        pedido = _pedido(protocolos.CHAT)
        self.assertEqual(pedido.url, f"{BASE}/chat/completions")
        self.assertEqual(pedido.cabeceras["Authorization"],
                         f"Bearer {CLAVE}")
        self.assertEqual(pedido.cabeceras["Content-Type"],
                         "application/json")
        cuerpo = pedido.cuerpo
        self.assertEqual(cuerpo["model"], MODELO)
        self.assertEqual(cuerpo["max_tokens"], 64)
        self.assertEqual(cuerpo["messages"][0],
                         {"role": "system", "content": SISTEMA})
        usuario = cuerpo["messages"][1]
        self.assertEqual(usuario["role"], "user")
        self.assertEqual(usuario["content"][0],
                         {"type": "text", "text": "¿De qué color es?"})
        self.assertEqual(usuario["content"][1]["type"], "image_url")
        self.assertEqual(cuerpo["messages"][2],
                         {"role": "assistant", "content": "Es una prueba."})

    def test_extra_se_suma_al_final(self):
        pedido = protocolos.armar_pedido(
            protocolos.CHAT, BASE, MODELO, CLAVE, SISTEMA, _tres_turnos(),
            64, cabeceras_extra={"x-opencode-session": "abc"})
        self.assertEqual(pedido.cabeceras["x-opencode-session"], "abc")
        self.assertEqual(pedido.cabeceras["Authorization"],
                         f"Bearer {CLAVE}")


class TestPedidoResponses(unittest.TestCase):

    def test_direccion_cabeceras_y_cuerpo(self):
        pedido = _pedido(protocolos.RESPONSES)
        self.assertEqual(pedido.url, f"{BASE}/responses")
        self.assertEqual(pedido.cabeceras["Authorization"],
                         f"Bearer {CLAVE}")
        cuerpo = pedido.cuerpo
        self.assertEqual(cuerpo["model"], MODELO)
        self.assertEqual(cuerpo["instructions"], SISTEMA)
        self.assertEqual(cuerpo["max_output_tokens"], 64)
        self.assertNotIn("detail", json.dumps(cuerpo))
        usuario = cuerpo["input"][0]
        self.assertEqual(usuario["content"][0],
                         {"type": "input_text",
                          "text": "¿De qué color es?"})
        self.assertEqual(usuario["content"][1]["type"], "input_image")
        asistente = cuerpo["input"][1]
        self.assertEqual(asistente["content"],
                         [{"type": "output_text",
                           "text": "Es una prueba."}])


class TestPedidoAnthropic(unittest.TestCase):

    def test_direccion_cabeceras_y_cuerpo(self):
        pedido = _pedido(protocolos.ANTHROPIC)
        self.assertEqual(pedido.url, f"{BASE}/messages")
        self.assertEqual(pedido.cabeceras["x-api-key"], CLAVE)
        self.assertEqual(pedido.cabeceras["anthropic-version"],
                         "2023-06-01")
        cuerpo = pedido.cuerpo
        self.assertEqual(cuerpo["model"], MODELO)
        self.assertEqual(cuerpo["system"], SISTEMA)
        self.assertEqual(cuerpo["max_tokens"], 64)
        usuario = cuerpo["messages"][0]
        self.assertEqual(usuario["content"][0]["type"], "image")
        self.assertEqual(usuario["content"][0]["source"]["media_type"],
                         "image/jpeg")
        self.assertEqual(usuario["content"][1],
                         {"type": "text", "text": "¿De qué color es?"})
        self.assertEqual(cuerpo["messages"][1],
                         {"role": "assistant",
                          "content": "Es una prueba."})


class TestPedidoGemini(unittest.TestCase):

    def test_direccion_cabeceras_y_cuerpo(self):
        pedido = _pedido(protocolos.GEMINI)
        self.assertEqual(pedido.url,
                         f"{BASE}/models/{MODELO}:generateContent")
        self.assertEqual(pedido.cabeceras["x-goog-api-key"], CLAVE)
        cuerpo = pedido.cuerpo
        self.assertNotIn("model", cuerpo)
        self.assertEqual(cuerpo["systemInstruction"],
                         {"parts": [{"text": SISTEMA}]})
        self.assertEqual(cuerpo["generationConfig"],
                         {"maxOutputTokens": 64})
        usuario = cuerpo["contents"][0]
        self.assertEqual(usuario["role"], "user")
        self.assertEqual(usuario["parts"][0]["inline_data"]["mime_type"],
                         "image/jpeg")
        self.assertEqual(usuario["parts"][1], {"text": "¿De qué color es?"})
        self.assertEqual(cuerpo["contents"][1]["role"], "model")


class TestConversacion(unittest.TestCase):

    def test_tres_turnos_en_orden_con_imagen_solo_al_principio(self):
        for protocolo in (protocolos.CHAT, protocolos.RESPONSES,
                          protocolos.ANTHROPIC, protocolos.GEMINI):
            with self.subTest(protocolo=protocolo):
                pedido = _pedido(protocolo)
                if protocolo == protocolos.GEMINI:
                    turnos = pedido.cuerpo["contents"]
                    self.assertEqual(
                        [t["role"] for t in turnos],
                        ["user", "model", "user"])
                    con_imagen = [i for i, t in enumerate(turnos)
                                  if any("inline_data" in p
                                         for p in t["parts"])]
                elif protocolo == protocolos.RESPONSES:
                    turnos = pedido.cuerpo["input"]
                    self.assertEqual(
                        [t["role"] for t in turnos],
                        ["user", "assistant", "user"])
                    con_imagen = [i for i, t in enumerate(turnos)
                                  if any(p.get("type") == "input_image"
                                         for p in t["content"])]
                elif protocolo == protocolos.ANTHROPIC:
                    turnos = pedido.cuerpo["messages"]
                    con_imagen = [i for i, t in enumerate(turnos)
                                  if isinstance(t["content"], list)
                                  and any(b.get("type") == "image"
                                          for b in t["content"])]
                else:
                    turnos = pedido.cuerpo["messages"][1:]
                    con_imagen = [i for i, t in enumerate(turnos)
                                  if isinstance(t["content"], list)
                                  and any(p.get("type") == "image_url"
                                          for p in t["content"])]
                self.assertEqual(con_imagen, [0])

    def test_imagen_decodificable_a_los_mismos_bytes(self):
        for protocolo in (protocolos.CHAT, protocolos.RESPONSES,
                          protocolos.ANTHROPIC, protocolos.GEMINI):
            with self.subTest(protocolo=protocolo):
                pedido = _pedido(protocolo)
                crudo = json.dumps(pedido.cuerpo)
                texto = None
                if protocolo == protocolos.CHAT:
                    texto = pedido.cuerpo["messages"][1][
                        "content"][1]["image_url"]["url"]
                    texto = texto.split("base64,", 1)[1]
                elif protocolo == protocolos.RESPONSES:
                    texto = pedido.cuerpo["input"][0][
                        "content"][1]["image_url"]
                    texto = texto.split("base64,", 1)[1]
                elif protocolo == protocolos.ANTHROPIC:
                    texto = pedido.cuerpo["messages"][0][
                        "content"][0]["source"]["data"]
                else:
                    texto = pedido.cuerpo["contents"][0][
                        "parts"][0]["inline_data"]["data"]
                self.assertNotIn("\n", texto)
                self.assertEqual(base64.b64decode(texto), IMAGEN)
                self.assertIn("data:image/jpeg;base64,", crudo) \
                    if protocolo in (protocolos.CHAT,
                                     protocolos.RESPONSES) else None

    def test_sin_texto_no_lleva_parte_vacia(self):
        mensajes = [protocolos.Mensaje("usuario", "", IMAGEN)]
        for protocolo in (protocolos.CHAT, protocolos.RESPONSES,
                          protocolos.ANTHROPIC, protocolos.GEMINI):
            with self.subTest(protocolo=protocolo):
                crudo = json.dumps(_pedido(protocolo, mensajes).cuerpo)
                self.assertNotIn('"text": ""', crudo)

    def test_protocolo_desconocido(self):
        with self.assertRaises(ValueError):
            protocolos.armar_pedido("otro", BASE, MODELO, CLAVE, SISTEMA,
                                    [], 64)
        with self.assertRaises(ValueError):
            protocolos.leer_respuesta("otro", 200, "{}")


MUESTRA_CHAT = json.dumps({
    "id": "0727cfb6", "object": "chat.completion",
    "model": "minimax-m2.1-free",
    "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": "Red",
                             "reasoning_content":
                             "We need answer image color. One word."}}],
    "usage": {"prompt_tokens": 216, "completion_tokens": 25}})

MUESTRA_RESPONSES = json.dumps({
    "id": "resp_6ad8", "object": "response", "status": "completed",
    "incomplete_details": None, "model": "muse-spark-1.3-contributor",
    "output": [
        {"id": "rs_1", "type": "reasoning", "status": "completed",
         "summary": []},
        {"id": "msg_1", "type": "message", "status": "completed",
         "role": "assistant",
         "content": [{"type": "output_text", "text": "Red",
                      "annotations": []}]}],
    "usage": {"input_tokens": 29, "output_tokens": 57}})

MUESTRA_ANTHROPIC = json.dumps({
    "id": "msg_011C", "type": "message", "role": "assistant",
    "stop_reason": "end_turn", "model": "claude-haiku-5-5",
    "content": [{"type": "text", "text": "Red"}],
    "usage": {"input_tokens": 25, "output_tokens": 4}})

MUESTRA_GEMINI = json.dumps({
    "responseId": "1JzY", "modelVersion": "gemini-4-argon-contributor",
    "candidates": [{"finishReason": "STOP", "index": 0,
                    "content": {"role": "model", "parts": [
                        {"text": "Red",
                         "thoughtSignature": "ElkKVwFpFH0T"}]}}],
    "usageMetadata": {"promptTokenCount": 1133,
                      "candidatesTokenCount": 5}})


class TestMuestras200(unittest.TestCase):

    def test_las_cuatro_muestras_dan_red(self):
        casos = [(protocolos.CHAT, MUESTRA_CHAT),
                 (protocolos.RESPONSES, MUESTRA_RESPONSES),
                 (protocolos.ANTHROPIC, MUESTRA_ANTHROPIC),
                 (protocolos.GEMINI, MUESTRA_GEMINI)]
        for protocolo, muestra in casos:
            with self.subTest(protocolo=protocolo):
                respuesta = protocolos.leer_respuesta(
                    protocolo, 200, muestra)
                self.assertEqual(respuesta.texto, "Red")
                self.assertFalse(respuesta.cortada)


def _cuerpo_de_cuota(limite):
    mensaje = (
        "Quota exceeded for metric: generativelanguage.googleapis.com/"
        "generate_content_free_tier_requests, limit: {}, model: "
        "gemini-3.1-pro\n{}".format(limite, "detalle real " * 40))
    return json.dumps({"error": {"code": 429,
                                 "status": "RESOURCE_EXHAUSTED",
                                 "message": mensaje}})


def _errores_medidos(mensaje):
    chat = json.dumps({"error": {"type": "server_error",
                                 "message": mensaje}})
    anthropic = json.dumps({"type": "error", "error": {
        "type": "api_error", "message": mensaje}})
    gemini = json.dumps({"error": {"code": 401, "status": "UNKNOWN",
                                   "message": mensaje}})
    return [(protocolos.CHAT, chat), (protocolos.RESPONSES, chat),
            (protocolos.ANTHROPIC, anthropic), (protocolos.GEMINI, gemini)]


class TestErroresMedidos(unittest.TestCase):

    def test_clave_mala_da_clave_rechazada(self):
        for protocolo, cuerpo in _errores_medidos(
                "Upstream request failed: Invalid credential"):
            with self.subTest(protocolo=protocolo):
                with self.assertRaises(protocolos.ErrorIA) as salida:
                    protocolos.leer_respuesta(protocolo, 401, cuerpo)
                self.assertEqual(salida.exception.tipo,
                                 protocolos.CLAVE_RECHAZADA)

    def test_modelo_inexistente_da_modelo_inexistente(self):
        for protocolo, cuerpo in _errores_medidos(
                "Upstream request failed: Model is unavailable."):
            with self.subTest(protocolo=protocolo):
                with self.assertRaises(protocolos.ErrorIA) as salida:
                    protocolos.leer_respuesta(protocolo, 400, cuerpo)
                self.assertEqual(salida.exception.tipo,
                                 protocolos.MODELO_INEXISTENTE)


class TestTiposDeError(unittest.TestCase):

    def test_403_tambien_es_clave(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 403, "{}")
        self.assertEqual(salida.exception.tipo,
                         protocolos.CLAVE_RECHAZADA)

    def test_404_es_modelo(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(
                protocolos.CHAT, 404,
                json.dumps({"error": {"message": "no está"}}))
        self.assertEqual(salida.exception.tipo,
                         protocolos.MODELO_INEXISTENTE)

    def test_400_mira_clave_antes_que_modelo(self):
        cuerpo = json.dumps({"error": {"message":
                                       "Invalid credential, Model is unavailable"}})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 400, cuerpo)
        self.assertEqual(salida.exception.tipo,
                         protocolos.CLAVE_RECHAZADA)

    def test_400_sin_marca_es_rechazo(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(
                protocolos.CHAT, 400,
                json.dumps({"error": {"message": "pedido mal armado"}}))
        self.assertEqual(salida.exception.tipo, protocolos.RECHAZO)

    def test_otro_4xx_es_rechazo(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 422, "{}")
        self.assertEqual(salida.exception.tipo, protocolos.RECHAZO)

    def test_500_es_servidor(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 500, "caído")
        self.assertEqual(salida.exception.tipo, protocolos.SERVIDOR)

    def test_cuerpo_no_json_no_revienta(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 401, "puerta")
        self.assertEqual(salida.exception.tipo,
                         protocolos.CLAVE_RECHAZADA)
        self.assertEqual(salida.exception.detalle, "puerta")
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 200, "puerta")
        self.assertEqual(salida.exception.tipo,
                         protocolos.RESPUESTA_VACIA)

    def test_detalle_recortado_a_300(self):
        cuerpo = json.dumps({"error": {"message": "x" * 500}})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 400, cuerpo)
        self.assertLessEqual(len(salida.exception.detalle), 300)

    def test_429_con_limite_cero_marca_sin_nivel_gratuito(self):
        cuerpo = _cuerpo_de_cuota(0)
        mensaje = json.loads(cuerpo)["error"]["message"]
        self.assertGreater(len(mensaje), 300)
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.GEMINI, 429, cuerpo)
        self.assertTrue(salida.exception.sin_nivel_gratuito)
        self.assertLessEqual(len(salida.exception.detalle), 300)

    def test_429_con_limite_mayor_no_marca_sin_nivel_gratuito(self):
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(
                protocolos.GEMINI, 429, _cuerpo_de_cuota(20))
        self.assertFalse(salida.exception.sin_nivel_gratuito)

    def test_200_sin_forma_es_vacia(self):
        for protocolo, cuerpo in ((protocolos.CHAT, "{}"),
                                  (protocolos.RESPONSES, '{"output": []}'),
                                  (protocolos.ANTHROPIC,
                                   '{"content": []}'),
                                  (protocolos.GEMINI, '{"candidates": []}')):
            with self.subTest(protocolo=protocolo):
                with self.assertRaises(protocolos.ErrorIA) as salida:
                    protocolos.leer_respuesta(protocolo, 200, cuerpo)
                self.assertEqual(salida.exception.tipo,
                                 protocolos.RESPUESTA_VACIA)

    def test_responses_incompleto_medicion_real(self):
        cuerpo = json.dumps({"id": "resp_x", "object": "response",
                             "status": "incomplete",
                             "output": [{"id": "rs_1", "type": "reasoning",
                                         "status": "completed",
                                         "summary": []}]})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.RESPONSES, 200, cuerpo)
        self.assertEqual(salida.exception.tipo,
                         protocolos.SIN_TEXTO_POR_TOKENS)

    def test_responses_incompleto_con_texto_es_cortada(self):
        cuerpo = json.dumps({"status": "incomplete", "output": [
            {"type": "message", "content": [
                {"type": "output_text", "text": "  Rojo  "}]}]})
        respuesta = protocolos.leer_respuesta(
            protocolos.RESPONSES, 200, cuerpo)
        self.assertEqual(respuesta.texto, "Rojo")
        self.assertTrue(respuesta.cortada)

    def test_chat_length_sin_texto(self):
        # Forma no medida todavía: finish_reason length con contenido vacío.
        cuerpo = json.dumps({"choices": [
            {"finish_reason": "length",
             "message": {"role": "assistant", "content": ""}}]})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.CHAT, 200, cuerpo)
        self.assertEqual(salida.exception.tipo,
                         protocolos.SIN_TEXTO_POR_TOKENS)

    def test_chat_length_con_texto_es_cortada(self):
        # Forma no medida todavía: length con texto parcial.
        cuerpo = json.dumps({"choices": [
            {"finish_reason": "length",
             "message": {"role": "assistant", "content": "Rojo"}}]})
        respuesta = protocolos.leer_respuesta(protocolos.CHAT, 200, cuerpo)
        self.assertEqual((respuesta.texto, respuesta.cortada),
                         ("Rojo", True))

    def test_anthropic_max_tokens(self):
        # Forma no medida todavía: stop_reason max_tokens sin texto.
        cuerpo = json.dumps({"content": [], "stop_reason": "max_tokens"})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.ANTHROPIC, 200, cuerpo)
        self.assertEqual(salida.exception.tipo,
                         protocolos.SIN_TEXTO_POR_TOKENS)

    def test_gemini_max_tokens(self):
        # Forma no medida todavía: finishReason MAX_TOKENS sin texto.
        cuerpo = json.dumps({"candidates": [
            {"finishReason": "MAX_TOKENS",
             "content": {"role": "model", "parts": []}}]})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.GEMINI, 200, cuerpo)
        self.assertEqual(salida.exception.tipo,
                         protocolos.SIN_TEXTO_POR_TOKENS)

    def test_gemini_bloqueada_por_aviso(self):
        # Forma no medida todavía: promptFeedback con blockReason.
        cuerpo = json.dumps({"promptFeedback": {"blockReason": "SAFETY"},
                             "candidates": []})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.GEMINI, 200, cuerpo)
        self.assertEqual(salida.exception.tipo, protocolos.BLOQUEADA)

    def test_gemini_bloqueada_por_terminacion(self):
        # Forma no medida todavía: finishReason SAFETY sin texto.
        cuerpo = json.dumps({"candidates": [
            {"finishReason": "SAFETY",
             "content": {"role": "model", "parts": []}}]})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.GEMINI, 200, cuerpo)
        self.assertEqual(salida.exception.tipo, protocolos.BLOQUEADA)

    def test_gemini_api_key_invalida(self):
        # Forma no medida todavía: Gemini directo con API_KEY_INVALID.
        cuerpo = json.dumps({"error": {
            "code": 400, "status": "INVALID_ARGUMENT",
            "message": "API key not valid.",
            "details": [{"reason": "API_KEY_INVALID"}]}})
        with self.assertRaises(protocolos.ErrorIA) as salida:
            protocolos.leer_respuesta(protocolos.GEMINI, 400, cuerpo)
        self.assertEqual(salida.exception.tipo,
                         protocolos.CLAVE_RECHAZADA)

    def test_cuota_429(self):
        # Forma no medida todavía: la cuota agotada es 429.
        for protocolo in (protocolos.CHAT, protocolos.RESPONSES,
                          protocolos.ANTHROPIC, protocolos.GEMINI):
            with self.subTest(protocolo=protocolo):
                with self.assertRaises(protocolos.ErrorIA) as salida:
                    protocolos.leer_respuesta(protocolo, 429, "{}")
                self.assertEqual(salida.exception.tipo, protocolos.CUOTA)


class TestRazonamientoIgnorado(unittest.TestCase):

    def test_chat_ignora_reasoning_content(self):
        cuerpo = json.dumps({"choices": [
            {"finish_reason": "stop",
             "message": {"role": "assistant", "content": "Rojo",
                         "reasoning_content": "Pienso en otro color"}}]})
        self.assertEqual(protocolos.leer_respuesta(
            protocolos.CHAT, 200, cuerpo).texto, "Rojo")

    def test_chat_lista_junta_solo_texto(self):
        cuerpo = json.dumps({"choices": [
            {"finish_reason": "stop",
             "message": {"role": "assistant", "content": [
                 {"type": "text", "text": "Ro"},
                 {"type": "otro", "text": "XXX"},
                 {"type": "text", "text": "jo"}]}}]})
        self.assertEqual(protocolos.leer_respuesta(
            protocolos.CHAT, 200, cuerpo).texto, "Rojo")

    def test_responses_ignora_reasoning(self):
        cuerpo = json.dumps({"status": "completed", "output": [
            {"type": "reasoning", "content": "pienso"},
            {"type": "message", "content": [
                {"type": "output_text", "text": "Rojo"}]}]})
        self.assertEqual(protocolos.leer_respuesta(
            protocolos.RESPONSES, 200, cuerpo).texto, "Rojo")

    def test_anthropic_ignora_thinking(self):
        cuerpo = json.dumps({
            "content": [{"type": "thinking", "thinking": "hmm"},
                        {"type": "text", "text": "Rojo"}],
            "stop_reason": "end_turn"})
        self.assertEqual(protocolos.leer_respuesta(
            protocolos.ANTHROPIC, 200, cuerpo).texto, "Rojo")

    def test_gemini_ignora_thought(self):
        cuerpo = json.dumps({"candidates": [
            {"finishReason": "STOP",
             "content": {"role": "model", "parts": [
                 {"text": "ignorado", "thought": True},
                 {"text": "Rojo",
                  "thoughtSignature": "abc123"}]}}]})
        self.assertEqual(protocolos.leer_respuesta(
            protocolos.GEMINI, 200, cuerpo).texto, "Rojo")


def _conversaciones():
    return [
        [protocolos.Mensaje("usuario", "pregunta uno", IMAGEN)],
        [protocolos.Mensaje("usuario", "pregunta dos"),
         protocolos.Mensaje("asistente", "respuesta dos")],
        _tres_turnos(),
        [protocolos.Mensaje("usuario", "primera con foto", IMAGEN),
         protocolos.Mensaje("asistente", "acuse"),
         protocolos.Mensaje("usuario", "segunda con foto", IMAGEN)],
    ]


def _contar_imagenes(protocolo, cuerpo):
    if protocolo == protocolos.CHAT:
        return sum(1 for mensaje in cuerpo["messages"]
                   if isinstance(mensaje.get("content"), list)
                   for parte in mensaje["content"]
                   if parte.get("type") == "image_url")
    if protocolo == protocolos.RESPONSES:
        return sum(1 for turno in cuerpo["input"]
                   for parte in turno["content"]
                   if parte.get("type") == "input_image")
    if protocolo == protocolos.ANTHROPIC:
        return sum(1 for mensaje in cuerpo["messages"]
                   if isinstance(mensaje.get("content"), list)
                   for bloque in mensaje["content"]
                   if bloque.get("type") == "image")
    return sum(1 for contenido in cuerpo["contents"]
               for parte in contenido["parts"]
               if "inline_data" in parte)


class TestPropiedadGeneral(unittest.TestCase):

    def test_imagenes_igual_a_mensajes_con_imagen(self):
        for protocolo in (protocolos.CHAT, protocolos.RESPONSES,
                          protocolos.ANTHROPIC, protocolos.GEMINI):
            for mensajes in _conversaciones():
                with self.subTest(protocolo=protocolo, n=len(mensajes)):
                    cuerpo = _pedido(protocolo, mensajes).cuerpo
                    esperadas = sum(1 for m in mensajes
                                    if m.imagen is not None)
                    self.assertEqual(
                        _contar_imagenes(protocolo, cuerpo), esperadas)

    def test_cada_texto_aparece_una_sola_vez(self):
        for protocolo in (protocolos.CHAT, protocolos.RESPONSES,
                          protocolos.ANTHROPIC, protocolos.GEMINI):
            for mensajes in _conversaciones():
                with self.subTest(protocolo=protocolo, n=len(mensajes)):
                    crudo = json.dumps(
                        _pedido(protocolo, mensajes).cuerpo,
                        ensure_ascii=False)
                    for mensaje in mensajes:
                        if mensaje.texto:
                            self.assertEqual(
                                crudo.count(mensaje.texto), 1,
                                mensaje.texto)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest import mock

from ytchat.obs import obs_panel


def elemento(identificador, nombre, indice, x=32, y=882, ancho=460, alto=620,
             alineacion=9, visible=True, bloqueada=False, ancho_fuente=460,
             alto_fuente=620):
    return {"sceneItemId": identificador, "sourceName": nombre,
            "sceneItemIndex": indice, "sceneItemEnabled": visible,
            "sceneItemLocked": bloqueada,
            "sceneItemTransform": {"positionX": x, "positionY": y,
                                   "width": ancho, "height": alto,
                                   "alignment": alineacion,
                                   "sourceWidth": ancho_fuente,
                                   "sourceHeight": alto_fuente,
                                   "boundsWidth": 0.0, "boundsHeight": 0.0}}


class DobleObs:
    def __init__(self, elementos=None, entradas=(), escena="Escena", escenas=None,
                  silencios=None, grupos=None, perfiles=(), perfil_actual="",
                  estadisticas=None, reconectando=False):
        self.elementos = list(elementos or ())
        self.entradas = list(entradas)
        self.grupos = dict(grupos or {})
        self.escena = escena
        self.escenas = tuple(escenas if escenas is not None else (escena,))
        self.perfiles = list(perfiles)
        self.perfil_actual = perfil_actual
        self.llamadas = []
        self.conectado = True
        self.siguiente_id = 20
        self.silencios = dict(silencios or {})
        self.transmitiendo = False
        self.grabando = False
        self.grabacion_en_pausa = False
        self.reconectando = reconectando
        self.estadisticas = dict(estadisticas or {})

    def conectar(self, parada=None):
        self.conectado = True

    def cerrar(self):
        self.conectado = False

    def pedir(self, tipo, datos=None, parada=None):
        datos = datos or {}
        self.llamadas.append((tipo, datos, parada))
        if tipo == "GetSceneItemList":
            return {"responseData": {"sceneItems": list(self.elementos)}}
        if tipo == "GetGroupSceneItemList":
            return {"responseData": {"sceneItems": list(self.grupos.get(datos["sceneName"], ()))}}
        if tipo == "GetSceneList":
            return {"responseData": {"scenes": [
                {"sceneName": escena} for escena in self.escenas]}}
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetInputMute":
            nombre = datos["inputName"]
            if nombre not in self.silencios:
                raise RuntimeError("No es una fuente de audio")
            return {"responseData": {"inputMuted": self.silencios[nombre]}}
        if tipo == "ToggleInputMute":
            nombre = datos["inputName"]
            if nombre not in self.silencios:
                raise RuntimeError("No es una fuente de audio")
            self.silencios[nombre] = not self.silencios[nombre]
            return {"responseData": {"inputMuted": self.silencios[nombre]}}
        if tipo == "GetStreamStatus":
            return {"responseData": {"outputActive": self.transmitiendo,
                                      "outputDuration": 61000,
                                      "outputSkippedFrames": 2,
                                      "outputTotalFrames": 100,
                                      "outputReconnecting": self.reconectando}}
        if tipo == "GetStats":
            return {"responseData": dict(self.estadisticas)}
        if tipo == "GetRecordStatus":
            return {"responseData": {"outputActive": self.grabando,
                                      "outputPaused": self.grabacion_en_pausa,
                                      "outputTimecode": "00:01:02.000"}}
        if tipo == "ToggleStream":
            self.transmitiendo = not self.transmitiendo
            return {"responseData": {"outputActive": self.transmitiendo}}
        if tipo == "ToggleRecord":
            self.grabando = not self.grabando
            return {"responseData": {"outputActive": self.grabando}}
        if tipo == "ToggleRecordPause":
            self.grabacion_en_pausa = not self.grabacion_en_pausa
            return {"responseData": {"outputPaused": self.grabacion_en_pausa}}
        if tipo == "GetCurrentProgramScene":
            return {"responseData": {"currentProgramSceneName": self.escena}}
        if tipo == "SetCurrentProgramScene":
            self.escena = datos["sceneName"]
            return {"responseData": {}}
        if tipo == "GetVideoSettings":
            return {"responseData": {"baseWidth": 1600, "baseHeight": 900}}
        if tipo == "GetProfileList":
            return {"responseData": {"profiles": list(self.perfiles),
                                     "currentProfileName": self.perfil_actual}}
        if tipo in ("CreateSceneItem", "CreateInput"):
            self.siguiente_id += 1
            nuevo = elemento(self.siguiente_id, obs_panel.NOMBRE_FUENTE, 0)
            self.elementos.append(nuevo)
            return {"responseData": {"sceneItemId": self.siguiente_id}}
        if tipo == "SetSceneItemIndex":
            identificador = datos["sceneItemId"]
            nuevo_indice = datos["sceneItemIndex"]
            for item in self.elementos:
                if item["sceneItemId"] == identificador:
                    item["sceneItemIndex"] = nuevo_indice
            return {"responseData": {}}
        if tipo == "SetSceneItemTransform":
            for item in self.elementos:
                if item["sceneItemId"] == datos["sceneItemId"]:
                    item["sceneItemTransform"] = datos["sceneItemTransform"]
        if tipo == "SetSceneItemEnabled":
            for item in self.elementos:
                if item["sceneItemId"] == datos["sceneItemId"]:
                    item["sceneItemEnabled"] = datos["sceneItemEnabled"]
        if tipo == "SetSceneItemLocked":
            for item in self.elementos:
                if item["sceneItemId"] == datos["sceneItemId"]:
                    item["sceneItemLocked"] = datos["sceneItemLocked"]
        return {"responseData": {}}


class GestorPanelObsTest(unittest.TestCase):
    def gestor(self, doble):
        return obs_panel.GestorPanelObs(doble)

    @mock.patch("ytchat.obs.obs_panel.obs_cliente.leer_ajustes")
    def test_sin_argumentos_lee_los_ajustes_de_obs(self, leer_ajustes):
        ajustes = object()
        leer_ajustes.return_value = ajustes
        with mock.patch("ytchat.obs.obs_panel.obs_cliente.ClienteObs") as cliente_obs:
            gestor = obs_panel.GestorPanelObs()
        leer_ajustes.assert_called_once_with()
        cliente_obs.assert_called_once_with(ajustes)
        self.assertIs(gestor._cliente, cliente_obs.return_value)

    @mock.patch("ytchat.obs.obs_panel.obs_cliente.leer_ajustes")
    def test_con_cliente_no_lee_los_ajustes_de_obs(self, leer_ajustes):
        cliente = object()
        gestor = obs_panel.GestorPanelObs(cliente=cliente)
        leer_ajustes.assert_not_called()
        self.assertIs(gestor._cliente, cliente)

    def test_asegura_adoptando_elemento_de_la_escena(self):
        doble = DobleObs([elemento(3, obs_panel.NOMBRE_FUENTE, 1)])
        identificador = self.gestor(doble).asegurar_fuente("Escena", "http://x", 460, 620)
        self.assertEqual(identificador, 3)
        self.assertNotIn("CreateInput", [llamada[0] for llamada in doble.llamadas])


    def test_asegura_agregando_fuente_existente(self):
        doble = DobleObs(entradas=[{"inputName": obs_panel.NOMBRE_FUENTE}])
        self.assertEqual(self.gestor(doble).asegurar_fuente("Escena", "u", 1, 2), 21)
        self.assertIn("CreateSceneItem", [llamada[0] for llamada in doble.llamadas])

    def test_asegura_creando_fuente_nueva(self):
        doble = DobleObs()
        self.assertEqual(self.gestor(doble).asegurar_fuente("Escena", "u", 1, 2), 21)
        llamada = next(llamada for llamada in doble.llamadas if llamada[0] == "CreateInput")
        self.assertEqual(llamada[1]["inputKind"], "browser_source")

    def test_asegura_no_duplica_el_panel_metido_en_un_grupo(self):
        grupo = dict(elemento(7, "Grupo", 0), isGroup=True)
        doble = DobleObs([grupo],
                         entradas=[{"inputName": obs_panel.NOMBRE_FUENTE,
                                    "inputKind": "browser_source"}],
                         grupos={"Grupo": [elemento(3, obs_panel.NOMBRE_FUENTE, 0)]})
        identificador = self.gestor(doble).asegurar_fuente("Escena", "http://x", 460, 620)
        self.assertEqual(identificador, 3)
        tipos = [llamada[0] for llamada in doble.llamadas]
        self.assertNotIn("CreateSceneItem", tipos)
        self.assertNotIn("CreateInput", tipos)
        self.assertIn("SetInputSettings", tipos)

    def test_asegura_rechaza_una_fuente_ajena_con_el_mismo_nombre(self):
        doble = DobleObs(entradas=[{"inputName": obs_panel.NOMBRE_FUENTE,
                                    "inputKind": "text_gdiplus_v2"}])
        with self.assertRaisesRegex(obs_panel.obs_cliente.ObsError, "no es un navegador"):
            self.gestor(doble).asegurar_fuente("Escena", "u", 1, 2)
        tipos = [llamada[0] for llamada in doble.llamadas]
        self.assertNotIn("CreateSceneItem", tipos)
        self.assertNotIn("SetInputSettings", tipos)

    def test_fuente_desaparecida_da_un_error_de_obs_y_no_un_typeerror(self):
        operaciones = (
            ("posicionar", ("Escena", 10, 20, 5)),
            ("mover", ("Escena", 10, 20)),
            ("escalar", ("Escena", 640, 360)),
            ("mostrar", ("Escena", False)),
            ("fijar", ("Escena", True)),
        )
        for metodo, argumentos in operaciones:
            with self.subTest(metodo=metodo):
                gestor = self.gestor(DobleObs([elemento(2, "Cámara", 0)]))
                with self.assertRaisesRegex(obs_panel.obs_cliente.ObsError,
                                            "no encuentra la escena o la fuente"):
                    getattr(gestor, metodo)(*argumentos)

    def test_fijar_y_al_frente_no_releen_la_escena_despues_de_escribir(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0), elemento(2, "Juego", 4)])
        gestor = self.gestor(doble)
        gestor.fijar("Escena", True)
        gestor.al_frente("Escena")
        tipos = [llamada[0] for llamada in doble.llamadas]
        self.assertEqual(tipos, ["GetSceneItemList", "SetSceneItemLocked",
                                 "GetSceneItemList", "SetSceneItemIndex"])

    def test_instantanea_del_panel_escalado_informa_el_tamano_de_la_entrada(self):
        # width/height llevan la escala; el panel se redimensiona por la
        # entrada, así que ese es el valor que debe volver a los contadores.
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0, ancho=230, alto=310,
                                   ancho_fuente=460, alto_fuente=620)])
        snap = self.gestor(doble).instantanea("Escena")
        self.assertEqual((snap.ancho, snap.alto), (460, 620))

    def test_instantanea_sin_tamano_de_entrada_usa_el_de_pantalla(self):
        panel = elemento(1, obs_panel.NOMBRE_FUENTE, 0, ancho=230, alto=310)
        del panel["sceneItemTransform"]["sourceWidth"]
        del panel["sceneItemTransform"]["sourceHeight"]
        snap = self.gestor(DobleObs([panel])).instantanea("Escena")
        self.assertEqual((snap.ancho, snap.alto), (230, 310))

    def test_instantanea_de_otra_fuente_escalada_informa_el_tamano_en_pantalla(self):
        doble = DobleObs([elemento(2, "Cámara", 0, ancho=640, alto=360,
                                   ancho_fuente=1280, alto_fuente=720)])
        snap = self.gestor(doble).instantanea("Escena", fuente="Cámara")
        self.assertEqual((snap.ancho, snap.alto), (640, 360))

    def test_al_frente_no_manda_si_ya_esta_arriba(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 2), elemento(2, "Juego", 1)])
        self.gestor(doble).al_frente("Escena")
        self.assertNotIn("SetSceneItemIndex", [llamada[0] for llamada in doble.llamadas])

    def test_al_frente_sube_al_indice_mayor(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0), elemento(2, "Juego", 4)])
        self.gestor(doble).al_frente("Escena")
        llamada = next(llamada for llamada in doble.llamadas if llamada[0] == "SetSceneItemIndex")
        self.assertEqual(llamada[1]["sceneItemIndex"], 4)

    def test_fuentes_ordena_del_frente_hacia_atras(self):
        doble = DobleObs([elemento(1, "Juego", 3), elemento(2, "Cámara", 8),
                          elemento(3, obs_panel.NOMBRE_FUENTE, 5)])
        self.assertEqual(self.gestor(doble).fuentes("Escena"),
                         ("Cámara", "Chat YTChat", "Juego"))

    def test_descripcion_escena_pide_escena_elementos_lienzo_y_entradas(self):
        doble = DobleObs(
            [elemento(1, obs_panel.NOMBRE_FUENTE, 0),
             elemento(2, "Juego", 1, x=800, y=450, ancho=1600, alto=900,
                      alineacion=0)],
            entradas=[{"inputName": obs_panel.NOMBRE_FUENTE,
                       "inputKind": "browser_source"},
                      {"inputName": "Juego", "inputKind": "game_capture"}])
        frase = self.gestor(doble).descripcion_escena()
        tipos = [llamada[0] for llamada in doble.llamadas]
        for pedido in ("GetCurrentProgramScene", "GetSceneItemList",
                       "GetVideoSettings", "GetInputList"):
            self.assertIn(pedido, tipos)
        self.assertEqual(
            frase,
            "Escena al aire: Escena. 2 fuentes, de adelante hacia atrás.\n"
            "1: Juego, captura de juego, ocupa toda la imagen, se ve.\n"
            "2: Chat YTChat, navegador, esquina inferior izquierda, "
            "460 por 620 píxeles, visible en OBS, pero no aparece en "
            "la imagen: la tapa entera Juego.")

    def test_descripcion_escena_con_clase_desconocida_no_muestra_la_clase(self):
        doble = DobleObs(
            [elemento(1, "Rara", 0, x=800, y=450, ancho=1600, alto=900,
                      alineacion=0)],
            entradas=[{"inputName": "Rara", "inputKind": "clase_nueva"}])
        frase = self.gestor(doble).descripcion_escena()
        self.assertIn("1: Rara, ocupa toda la imagen, se ve.", frase)
        self.assertNotIn("clase_nueva", frase)

    def test_fuentes_devuelve_vacio_sin_fuentes_o_escena(self):
        self.assertEqual(self.gestor(DobleObs([])).fuentes("Escena"), ())
        self.assertEqual(self.gestor(DobleObs(escenas=())).fuentes("Ausente"), ())

    def test_fuentes_audio_descarta_las_que_obs_no_puede_silenciar(self):
        doble = DobleObs(
            entradas=({"inputName": "Mic/Aux"}, {"inputName": "Cámara"}),
            silencios={"Mic/Aux": False})
        self.assertEqual(self.gestor(doble).fuentes_audio(), ("Mic/Aux",))

    def test_consulta_el_silencio_de_una_fuente_de_audio(self):
        gestor = self.gestor(DobleObs(silencios={"Mic/Aux": True}))
        self.assertTrue(gestor.silenciada("Mic/Aux"))

    def test_alterna_el_silencio_y_devuelve_el_estado_resultante(self):
        doble = DobleObs(silencios={"Mic/Aux": False})
        self.assertTrue(self.gestor(doble).alternar_silencio("Mic/Aux"))
        self.assertTrue(doble.silencios["Mic/Aux"])

    def test_lee_los_estados_de_transmision_y_grabacion(self):
        doble = DobleObs()
        gestor = self.gestor(doble)
        self.assertEqual(gestor.estado_transmision(), {
            "outputActive": False, "outputDuration": 61,
            "outputSkippedFrames": 2, "outputTotalFrames": 100,
            "outputReconnecting": False})
        self.assertEqual(gestor.estado_grabacion(), {
            "outputActive": False, "outputPaused": False,
            "outputTimecode": "00:01:02.000"})

    def test_estado_transmision_devuelve_la_reconexion(self):
        doble = DobleObs(reconectando=True)
        self.assertTrue(self.gestor(doble).estado_transmision()["outputReconnecting"])

    def test_estadisticas_lee_los_cuadros_de_getstats(self):
        doble = DobleObs(estadisticas={
            "renderSkippedFrames": 8, "renderTotalFrames": 120,
            "outputSkippedFrames": 40, "outputTotalFrames": 200})
        self.assertEqual(self.gestor(doble).estadisticas(), {
            "renderSkippedFrames": 8, "renderTotalFrames": 120,
            "outputSkippedFrames": 40, "outputTotalFrames": 200})

    def test_estadisticas_con_campos_ausentes_dan_cero(self):
        self.assertEqual(self.gestor(DobleObs()).estadisticas(), {
            "renderSkippedFrames": 0, "renderTotalFrames": 0,
            "outputSkippedFrames": 0, "outputTotalFrames": 0})

    def test_poner_escena_al_aire_confirma_la_escena_leida(self):
        doble = DobleObs(escena="Principal", escenas=("Principal", "Juego"))
        gestor = self.gestor(doble)
        self.assertEqual(gestor.poner_escena_al_aire("Juego"), "Juego")
        self.assertEqual([llamada[0] for llamada in doble.llamadas],
                         ["SetCurrentProgramScene", "GetCurrentProgramScene"])
        self.assertEqual(doble.llamadas[0][1], {"sceneName": "Juego"})

    def test_las_alternancias_piden_a_obs_y_devuelven_el_estado_resultante(self):
        doble = DobleObs()
        gestor = self.gestor(doble)
        self.assertTrue(gestor.alternar_transmision())
        self.assertTrue(gestor.alternar_grabacion())
        self.assertTrue(gestor.alternar_pausa_grabacion())
        self.assertEqual([llamada[0] for llamada in doble.llamadas[-3:]],
                         ["ToggleStream", "ToggleRecord", "ToggleRecordPause"])

    def test_instantanea_sin_solapes(self):
        snap = self.gestor(DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])).instantanea("Escena")
        self.assertEqual(snap.solapes, ())

    def test_instantanea_con_un_solape(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0, x=0),
                          elemento(2, "Barra", 1, x=0, y=882, ancho=230)])
        self.assertEqual(self.gestor(doble).instantanea("Escena").solapes, (("Barra", 50.0),))

    def test_instantanea_ordena_dos_solapes(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0, x=0),
                          elemento(2, "Mitad", 1, x=0, y=882, ancho=230),
                          elemento(3, "Todo", 2, x=0, y=0, ancho=1600, alto=900, alineacion=5)])
        self.assertEqual(tuple(nombre for nombre, _ in self.gestor(doble).instantanea("Escena").solapes),
                         ("Todo", "Mitad"))

    def test_instantanea_identifica_fuente_delante_que_solapa(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                          elemento(2, "Tapa", 3, x=0, y=0, ancho=1600, alto=900, alineacion=5)])
        self.assertEqual(self.gestor(doble).instantanea("Escena").tapada_por, "Tapa")

    def test_instantanea_ignora_fuente_delante_sin_solape(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                          elemento(2, "Lejos", 3, x=1000, y=0, ancho=100, alto=100, alineacion=5)])
        self.assertEqual(self.gestor(doble).instantanea("Escena").tapada_por, "")

    def test_mover_suma_a_la_posicion_leida(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0, x=40, y=50)])
        self.gestor(doble).mover("Escena", 7, -3)
        transformacion = doble.elementos[0]["sceneItemTransform"]
        self.assertEqual((transformacion["positionX"], transformacion["positionY"]), (47, 47))

    def test_mover_hace_una_lectura_y_una_escritura(self):
        gestor = self.gestor(DobleObs())
        gestor._pedir = mock.Mock(side_effect=[
            {"sceneItems": [elemento(1, obs_panel.NOMBRE_FUENTE, 0)]}, {}])
        gestor.mover("Escena", 7, -3)
        self.assertEqual(gestor._pedir.call_count, 2)
        self.assertEqual([llamada.args[0] for llamada in gestor._pedir.call_args_list],
                         ["GetSceneItemList", "SetSceneItemTransform"])

    def test_colocar_manda_solo_las_claves_de_posicion_y_alineacion(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])
        self.gestor(doble).colocar("Escena", "superior-izquierda")
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(set(llamada[1]["sceneItemTransform"]),
                         {"positionX", "positionY", "alignment"})

    def test_colocar_manda_la_posicion_calculada(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])
        self.gestor(doble).colocar("Escena", "superior-izquierda")
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(llamada[1]["sceneItemTransform"],
                         {"positionX": 32.0, "positionY": 18.0, "alignment": 5})

    def test_transformacion_devuelve_solo_posicion_y_alineacion(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0, x=40, y=50)])
        transformacion = self.gestor(doble).transformacion("Escena")
        self.assertEqual(set(transformacion),
                         {"positionX", "positionY", "alignment"})
        self.assertEqual(transformacion,
                         {"positionX": 40, "positionY": 50, "alignment": 9})

    def test_transformacion_devuelve_vacio_si_no_hay_panel(self):
        doble = DobleObs([])
        self.assertEqual(self.gestor(doble).transformacion("Escena"), {})

    def test_posicionar_manda_la_posicion_y_alineacion_recibidas(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])
        self.gestor(doble).posicionar("Escena", 123.5, 456.25, 7)
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(llamada[1]["sceneItemTransform"],
                         {"positionX": 123.5, "positionY": 456.25,
                          "alignment": 7})

    def test_mover_manda_solo_las_claves_de_posicion(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])
        self.gestor(doble).mover("Escena", 7, -3)
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(set(llamada[1]["sceneItemTransform"]),
                         {"positionX", "positionY"})

    def test_mover_manda_la_posicion_desplazada(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])
        self.gestor(doble).mover("Escena", 7, -3)
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(llamada[1]["sceneItemTransform"],
                         {"positionX": 39, "positionY": 879})

    def test_instantanea_no_guarda_estado(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0)])
        gestor = self.gestor(doble)
        primera = gestor.instantanea("Escena")
        doble.elementos[0]["sceneItemTransform"]["positionX"] = 300
        segunda = gestor.instantanea("Escena")
        self.assertNotEqual(primera.izquierda, segunda.izquierda)

    def test_metodos_con_fuente_operan_sobre_el_elemento_nombrado(self):
        operaciones = (
            ("colocar", ("Escena", "superior-izquierda"), "SetSceneItemTransform"),
            ("posicionar", ("Escena", 10, 20, 5), "SetSceneItemTransform"),
            ("mover", ("Escena", 10, 20), "SetSceneItemTransform"),
            ("mostrar", ("Escena", False), "SetSceneItemEnabled"),
            ("fijar", ("Escena", True), "SetSceneItemLocked"),
            ("al_frente", ("Escena",), "SetSceneItemIndex"),
        )
        for metodo, argumentos, solicitud in operaciones:
            with self.subTest(metodo=metodo):
                doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 1),
                                  elemento(2, "Cámara", 0)])
                getattr(self.gestor(doble), metodo)(*argumentos, fuente="Cámara")
                llamada = next(llamada for llamada in doble.llamadas
                               if llamada[0] == solicitud)
                self.assertEqual(llamada[1]["sceneItemId"], 2)

    def test_lecturas_con_fuente_leen_el_elemento_nombrado(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0, x=10),
                          elemento(2, "Cámara", 1, x=300, ancho=640, alto=480)])
        self.assertEqual(self.gestor(doble).transformacion("Escena", fuente="Cámara")["positionX"], 300)
        self.assertEqual(self.gestor(doble).instantanea("Escena", fuente="Cámara").ancho, 640)

    def test_sin_fuente_sigue_operando_sobre_el_panel(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                          elemento(2, "Cámara", 1)])
        self.gestor(doble).mostrar("Escena", False)
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemEnabled")
        self.assertEqual(llamada[1]["sceneItemId"], 1)

    def test_escalar_manda_solo_las_escalas_de_la_fuente_nombrada(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                          elemento(2, "Cámara", 1, ancho_fuente=1280,
                                   alto_fuente=720)])
        self.assertTrue(self.gestor(doble).escalar("Escena", 640, 360,
                                                   fuente="Cámara"))
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(llamada[1]["sceneItemId"], 2)
        self.assertEqual(llamada[1]["sceneItemTransform"],
                         {"scaleX": 0.5, "scaleY": 0.5})

    def test_escalar_no_manda_nada_si_la_fuente_no_tiene_tamano(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0,
                                  ancho_fuente=0)])
        self.assertFalse(self.gestor(doble).escalar("Escena", 640, 360))
        self.assertNotIn("SetSceneItemTransform",
                         [llamada[0] for llamada in doble.llamadas])

    def test_perfil_actual_devuelve_el_perfil_en_uso(self):
        doble = DobleObs(perfiles=["TikTok", "YouTube"],
                         perfil_actual="TikTok")
        self.assertEqual(self.gestor(doble).perfil_actual(), "TikTok")
        self.assertEqual(doble.llamadas[-1][0], "GetProfileList")

    def test_preparar_destino_delega_en_obs_destinos(self):
        doble = DobleObs()
        gestor = self.gestor(doble)
        parada = object()
        esperado = {"destino": "TikTok"}
        with mock.patch.object(obs_panel.obs_destinos,
                               "preparar_para_transmitir",
                               return_value=esperado) as preparar:
            self.assertIs(gestor.preparar_destino("TikTok", parada), esperado)
        preparar.assert_called_once_with(doble, "TikTok", parada)

    def test_ventanas_delega_en_obs_captura(self):
        doble = DobleObs()
        gestor = self.gestor(doble)
        parada = object()
        esperado = ((("Juego, de juego.exe", "Juego:X:juego.exe"),), "")
        with mock.patch.object(obs_panel.obs_captura, "ventanas",
                               return_value=esperado) as ventanas:
            self.assertIs(gestor.ventanas("Escena", parada), esperado)
        ventanas.assert_called_once_with(doble, "Escena", parada)

    def test_usar_ventana_delega_en_obs_captura(self):
        doble = DobleObs()
        gestor = self.gestor(doble)
        parada = object()
        with mock.patch.object(obs_panel.obs_captura, "usar_ventana",
                               return_value="Ahora se captura Juego.") as usar:
            self.assertEqual(gestor.usar_ventana("Escena", "Juego:X:juego.exe", parada),
                             "Ahora se captura Juego.")
        usar.assert_called_once_with(doble, "Escena", "Juego:X:juego.exe", parada)

    def test_iniciar_transmision_pide_startstream(self):
        doble = DobleObs()
        parada = object()
        self.gestor(doble).iniciar_transmision(parada)
        self.assertEqual(doble.llamadas[-1][0], "StartStream")
        self.assertIs(doble.llamadas[-1][2], parada)

    def test_detener_transmision_pide_stopstream(self):
        doble = DobleObs()
        parada = object()
        self.gestor(doble).detener_transmision(parada)
        self.assertEqual(doble.llamadas[-1][0], "StopStream")
        self.assertIs(doble.llamadas[-1][2], parada)


class FuenteEncimaDelPanelTest(unittest.TestCase):
    def test_panel_arriba_no_devuelve_nada(self):
        elementos = [elemento(1, obs_panel.NOMBRE_FUENTE, 2),
                     elemento(2, "Juego", 1)]
        self.assertIsNone(obs_panel.fuente_encima_del_panel(elementos))

    def test_panel_tapado_por_una_visible_devuelve_su_nombre(self):
        elementos = [elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                     elemento(2, "Captura de pantalla", 1)]
        self.assertEqual(obs_panel.fuente_encima_del_panel(elementos),
                         "Captura de pantalla")

    def test_tapado_solo_por_ocultas_no_devuelve_nada(self):
        elementos = [elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                     elemento(2, "Captura de pantalla", 1, visible=False)]
        self.assertIsNone(obs_panel.fuente_encima_del_panel(elementos))

    def test_panel_oculto_no_devuelve_nada(self):
        elementos = [elemento(1, obs_panel.NOMBRE_FUENTE, 0, visible=False),
                     elemento(2, "Captura de pantalla", 1)]
        self.assertIsNone(obs_panel.fuente_encima_del_panel(elementos))

    def test_sin_panel_no_devuelve_nada(self):
        elementos = [elemento(2, "Captura de pantalla", 1)]
        self.assertIsNone(obs_panel.fuente_encima_del_panel(elementos))

    def test_varias_encima_devuelve_la_de_indice_mas_alto(self):
        elementos = [elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                     elemento(2, "Captura de pantalla", 1),
                     elemento(3, "Captura de ventana", 3),
                     elemento(4, "Aviso", 2)]
        self.assertEqual(obs_panel.fuente_encima_del_panel(elementos),
                         "Captura de ventana")


class TraerPanelAdelanteTest(unittest.TestCase):
    def gestor(self, doble):
        return obs_panel.GestorPanelObs(doble)

    def test_con_algo_encima_pide_subir_y_devuelve_el_nombre(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0),
                          elemento(2, "Captura de pantalla", 1)])
        nombre = self.gestor(doble).traer_panel_adelante()
        self.assertEqual(nombre, "Captura de pantalla")
        self.assertIn("SetSceneItemIndex",
                      [llamada[0] for llamada in doble.llamadas])

    def test_sin_nada_encima_no_pide_nada_y_devuelve_none(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 2),
                          elemento(2, "Juego", 1)])
        self.assertIsNone(self.gestor(doble).traer_panel_adelante())
        self.assertNotIn("SetSceneItemIndex",
                         [llamada[0] for llamada in doble.llamadas])

    def test_sin_panel_no_pide_subir(self):
        doble = DobleObs([elemento(2, "Juego", 1)])
        self.assertIsNone(self.gestor(doble).traer_panel_adelante())
        self.assertNotIn("SetSceneItemIndex",
                         [llamada[0] for llamada in doble.llamadas])

    def test_panel_oculto_no_pide_subir(self):
        doble = DobleObs([elemento(1, obs_panel.NOMBRE_FUENTE, 0,
                                  visible=False),
                          elemento(2, "Captura de pantalla", 1)])
        self.assertIsNone(self.gestor(doble).traer_panel_adelante())
        self.assertNotIn("SetSceneItemIndex",
                         [llamada[0] for llamada in doble.llamadas])


if __name__ == "__main__":
    unittest.main()

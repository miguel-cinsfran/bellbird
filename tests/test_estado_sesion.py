"""Tests del formateo del estado de sesión (F2)."""

import unittest

from bellbird.capture import descartes
from bellbird.capture import estado_sesion
from bellbird.capture.estado_sesion import (SnapshotSesion, formatear_estado, COMPONENTES,
                           ACTIVOS_DEFECTO, ETIQUETAS, _duracion, _render)
from tests.pseudo_prueba import con_pseudo


class TestDuracion(unittest.TestCase):

    def test_cero(self):
        self.assertEqual(_duracion(0), "menos de un minuto")

    def test_cincuenta_y_nueve_segundos(self):
        self.assertEqual(_duracion(59), "menos de un minuto")

    def test_un_minuto(self):
        self.assertEqual(_duracion(60), "1 min")

    def test_veintitres_minutos(self):
        self.assertEqual(_duracion(23 * 60), "23 min")

    def test_una_hora(self):
        self.assertEqual(_duracion(60 * 60), "1 h 0 min")

    def test_una_hora_y_veintitres_minutos(self):
        self.assertEqual(_duracion(83 * 60), "1 h 23 min")

    def test_treinta_horas_y_cinco_minutos(self):
        self.assertEqual(_duracion(30 * 60 * 60 + 5 * 60), "30 h 5 min")

    def test_cuarenta_y_siete_horas_y_cincuenta_y_nueve_minutos(self):
        self.assertEqual(_duracion(47 * 60 * 60 + 59 * 60), "47 h 59 min")

    def test_cuarenta_y_ocho_horas(self):
        self.assertEqual(_duracion(48 * 60 * 60), "2 días")

    def test_seiscientos_noventa_y_siete_dias(self):
        self.assertEqual(_duracion(697 * 24 * 60 * 60), "697 días")

    def test_un_dia(self):
        self.assertEqual(_duracion(24 * 60 * 60), "24 h 0 min")

    def test_el_escalon_nunca_retrocede(self):
        anterior = -1
        for minutos in range(0, 72 * 60 + 1, 10):
            texto = _duracion(minutos * 60)
            if "día" in texto:
                escalon = 2
            elif " h " in texto:
                escalon = 1
            else:
                escalon = 0
            self.assertGreaterEqual(escalon, anterior,
                                    f"retroceso en {minutos} minutos: {texto}")
            anterior = escalon


class TestTiempoDirecto(unittest.TestCase):

    def test_corto(self):
        self.assertEqual(formatear_estado(
            SnapshotSesion(segundos_directo=83 * 60), {"tiempo_directo"}),
            "Lleva 1 h 23 min.")

    def test_largo(self):
        self.assertEqual(formatear_estado(
            SnapshotSesion(segundos_directo=83 * 60), {"tiempo_directo"}, "largo"),
            "Tiempo del directo: 1 h 23 min")

    def test_sin_dato(self):
        self.assertEqual(formatear_estado(
            SnapshotSesion(segundos_directo=None), {"tiempo_directo"}), "")

    def test_negativo(self):
        self.assertEqual(formatear_estado(
            SnapshotSesion(segundos_directo=-1), {"tiempo_directo"}), "")


class TestFormatoBasico(unittest.TestCase):

    def test_desconectado(self):
        s = SnapshotSesion(conectado=False)
        self.assertEqual(formatear_estado(s, {"estado"}), "Desconectado.")

    def test_conectado_tiktok_con_datos(self):
        s = SnapshotSesion(conectado=True, tipo="live_tiktok",
                           titulo="Charla nocturna", canal="Fulano",
                           espectadores=1234, mensajes_leidos=10)
        out = formatear_estado(s, ACTIVOS_DEFECTO)
        self.assertIn("Directo de TikTok", out)
        self.assertIn("Charla nocturna", out)
        self.assertIn("Canal: Fulano", out)
        self.assertIn("1.234 espectadores", out)   # miles con punto
        self.assertIn("10 leídos", out)
        self.assertTrue(out.endswith("."))

    def test_orden_de_componentes(self):
        s = SnapshotSesion(conectado=True, tipo="vod", titulo="T", canal="C")
        out = formatear_estado(s, {"estado", "titulo", "canal"})
        self.assertLess(out.index("Vídeo"), out.index("T"))
        self.assertLess(out.index("T"), out.index("Canal: C"))


class TestOmisiones(unittest.TestCase):

    def test_omite_componentes_sin_dato(self):
        # Sin espectadores ni aportes: esos componentes desaparecen.
        s = SnapshotSesion(conectado=True, tipo="live_youtube", titulo="Hola",
                           espectadores=None, aportes=0)
        out = formatear_estado(s, ACTIVOS_DEFECTO)
        self.assertNotIn("espectadores", out)
        self.assertNotIn("Super Chats", out)

    def test_toggle_desactivado_no_aparece(self):
        s = SnapshotSesion(conectado=True, tipo="vod", titulo="Hola", canal="C")
        out = formatear_estado(s, {"estado"})   # solo estado
        self.assertEqual(out, "Vídeo.")

    def test_lectura_silenciada_solo_si_activa(self):
        s = SnapshotSesion(conectado=True, tipo="vod", lectura_silenciada=False)
        self.assertNotIn("silenciada", formatear_estado(s, {"lectura_silenciada"}))
        s2 = SnapshotSesion(conectado=True, tipo="vod", lectura_silenciada=True)
        self.assertIn("Lectura silenciada", formatear_estado(s2, {"lectura_silenciada"}))


class TestAportes(unittest.TestCase):

    def test_youtube_dice_super_chats(self):
        s = SnapshotSesion(conectado=True, tipo="live_youtube", aportes=3,
                           total_aportes="US$12,50")
        out = formatear_estado(s, {"aportes"})
        self.assertIn("3 Super Chats", out)
        self.assertIn("US$12,50", out)

    def test_tiktok_dice_regalos(self):
        s = SnapshotSesion(conectado=True, tipo="live_tiktok", aportes=5)
        self.assertIn("5 regalos", formatear_estado(s, {"aportes"}))


class TestModoLargo(unittest.TestCase):

    def test_largo_es_multilinea_con_etiquetas(self):
        s = SnapshotSesion(conectado=True, tipo="live_tiktok", titulo="T",
                           espectadores=50)
        out = formatear_estado(s, {"estado", "titulo", "espectadores"}, modo="largo")
        lineas = out.split("\n")
        self.assertEqual(lineas[0], "Directo de TikTok")
        self.assertIn("Título: T", lineas)
        self.assertIn("Espectadores: 50", lineas)

    def test_vacio_si_nada_que_mostrar(self):
        s = SnapshotSesion(conectado=True, tipo="vod")
        self.assertEqual(formatear_estado(s, {"titulo", "canal"}), "")


class TestCoherencia(unittest.TestCase):

    def test_mensajes_programados_se_anuncian_si_hay_dato(self):
        s = SnapshotSesion(programados_proximo=
                           "Próximo mensaje automático en 4 minutos")
        self.assertEqual(formatear_estado(s, {"programados"}),
                         "Próximo mensaje automático en 4 minutos.")

    def test_mensajes_programados_vacios_se_omiten(self):
        self.assertEqual(formatear_estado(SnapshotSesion(), {"programados"}), "")

    def test_descartados_se_anuncian_si_hay_dato(self):
        s = SnapshotSesion(descartados="Mensajes descartados: 3")
        self.assertEqual(formatear_estado(s, {"descartados"}),
                         "Mensajes descartados: 3.")

    def test_descartados_vacios_se_omiten_y_no_son_predeterminados(self):
        s = SnapshotSesion(descartados=descartes.frase_estado(0))
        self.assertEqual(formatear_estado(s, {"descartados"}), "")
        self.assertNotIn("descartados", ACTIVOS_DEFECTO)

    def test_activos_defecto_son_componentes_validos(self):
        for nombre in ACTIVOS_DEFECTO:
            self.assertIn(nombre, COMPONENTES)

    def test_panel_apagado_no_agrega_estado(self):
        s = SnapshotSesion(overlay_puerto=None)
        self.assertEqual(formatear_estado(s, {"overlay"}), "")

    def test_panel_activo_distingue_clientes(self):
        s = SnapshotSesion(overlay_puerto=9000, overlay_clientes=1)
        self.assertEqual(
            formatear_estado(s, {"overlay"}),
            "Panel de chat activo en el puerto 9000, mostrándose.")
        s = SnapshotSesion(overlay_puerto=9000, overlay_clientes=0)
        self.assertEqual(
            formatear_estado(s, {"overlay"}),
            "Panel de chat activo en el puerto 9000, pero nadie lo está mostrando.")


class TestTransmisionSupervisada(unittest.TestCase):

    def test_supervisada_sola_sale_sin_toggles(self):
        s = SnapshotSesion(
            transmision_supervisada="Esperando a que TikTok muestre el directo")
        self.assertEqual(
            formatear_estado(s, set()),
            "Esperando a que TikTok muestre el directo.")

    def test_supervisada_va_primero_y_tapa_a_obs(self):
        s = SnapshotSesion(
            titulo="Charla", obs_transmision="Transmitiendo desde hace 1 min",
            transmision_supervisada="Directo a TikTok: Transmitiendo desde hace 3 min")
        out = formatear_estado(s, {"titulo", "obs_transmision"})
        self.assertTrue(out.startswith(
            "Directo a TikTok: Transmitiendo desde hace 3 min"))
        self.assertIn("Charla", out)
        self.assertNotIn("Transmitiendo desde hace 1 min", out)

    def test_modo_largo_con_etiqueta_propia(self):
        s = SnapshotSesion(
            transmision_supervisada="Esperando a que TikTok muestre el directo")
        out = formatear_estado(s, set(), "largo")
        self.assertTrue(out.split("\n")[0].startswith("Transmisión: "))
        self.assertIn("Esperando a que TikTok muestre el directo", out)

    def test_sin_supervisada_obs_sigue_igual(self):
        s = SnapshotSesion(obs_transmision="Transmitiendo desde hace 1 min")
        self.assertEqual(formatear_estado(s, {"obs_transmision"}),
                         "Transmitiendo desde hace 1 min.")


class TestDesfaseConVuelta(unittest.TestCase):

    def test_con_desfase_y_atajo_de_fabrica(self):
        s = SnapshotSesion(desfase_directo="10 segundos por detrás del directo",
                           atajo_directo="Ctrl+Fin")
        self.assertEqual(
            formatear_estado(s, {"desfase_directo"}),
            "10 segundos por detrás del directo. "
            "Pulsa Ctrl+Fin para volver al directo.")

    def test_largo_agrega_la_vuelta(self):
        s = SnapshotSesion(desfase_directo="10 segundos por detrás del directo",
                           atajo_directo="Ctrl+Fin")
        self.assertEqual(
            formatear_estado(s, {"desfase_directo"}, "largo"),
            "Reproductor: 10 segundos por detrás del directo. "
            "Pulsa Ctrl+Fin para volver al directo.")

    def test_atajo_cambiado_usa_el_configurado(self):
        s = SnapshotSesion(desfase_directo="10 segundos por detrás del directo",
                           atajo_directo="Alt+D")
        self.assertIn("Pulsa Alt+D para volver al directo.",
                      formatear_estado(s, {"desfase_directo"}))

    def test_sin_atajo_da_la_ruta_del_menu(self):
        s = SnapshotSesion(desfase_directo="10 segundos por detrás del directo",
                           atajo_directo="")
        self.assertEqual(
            formatear_estado(s, {"desfase_directo"}),
            "10 segundos por detrás del directo. "
            "Para volver: menú Reproductor, Ir al directo.")

    def test_sin_desfase_no_agrega_nada(self):
        s = SnapshotSesion(desfase_directo="", atajo_directo="Ctrl+Fin")
        self.assertEqual(formatear_estado(s, {"desfase_directo"}), "")


class TestMusica(unittest.TestCase):

    def test_componente_al_final_con_etiqueta(self):
        self.assertEqual(COMPONENTES[-3], "musica")
        self.assertEqual(ETIQUETAS["musica"], "Música que suena")

    def test_se_dibuja_con_dato(self):
        s = SnapshotSesion(musica="Música: Tema 2, canción 2 de 5")
        self.assertEqual(formatear_estado(s, {"musica"}),
                         "Música: Tema 2, canción 2 de 5.")
        self.assertEqual(formatear_estado(s, {"musica"}, "largo"),
                         "Música: Tema 2, canción 2 de 5")

    def test_vacio_no_aparece(self):
        self.assertEqual(formatear_estado(SnapshotSesion(musica=""), {"musica"}), "")
        self.assertEqual(formatear_estado(SnapshotSesion(), {"musica"}), "")

    def test_activo_de_fabrica(self):
        self.assertIn("musica", ACTIVOS_DEFECTO)


class TestIgualando(unittest.TestCase):

    def test_componente_al_final_con_etiqueta(self):
        self.assertEqual(COMPONENTES[-2], "igualando")
        self.assertEqual(ETIQUETAS["igualando"],
                         "Igualación del volumen de la música")

    def test_activo_lo_incluye_apagado_no(self):
        s = SnapshotSesion(igualando="Igualando el volumen: 3 de 10")
        self.assertIn("Igualando el volumen: 3 de 10",
                      formatear_estado(s, {"igualando"}))
        self.assertNotIn("Igualando",
                         formatear_estado(s, {"musica"}))

    def test_vacio_no_aparece(self):
        self.assertEqual(
            formatear_estado(SnapshotSesion(igualando=""), {"igualando"}), "")
        self.assertEqual(formatear_estado(SnapshotSesion(), {"igualando"}), "")

    def test_activo_de_fabrica(self):
        self.assertIn("igualando", ACTIVOS_DEFECTO)


class TestEspectadoresConTotal(unittest.TestCase):

    def test_tiktok_dice_ahora_y_total_en_corto(self):
        s = SnapshotSesion(conectado=True, tipo="live_tiktok",
                           espectadores=12, espectadores_total=108)
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "12 espectadores ahora, 108 en total.")

    def test_tiktok_dice_ahora_y_total_en_largo(self):
        s = SnapshotSesion(conectado=True, tipo="live_tiktok",
                           espectadores=12, espectadores_total=108)
        self.assertEqual(formatear_estado(s, {"espectadores"}, "largo"),
                         "Espectadores: 12 ahora, 108 en total")

    def test_tiktok_con_uno_usa_el_singular_en_corto_y_largo(self):
        s = SnapshotSesion(conectado=True, tipo="live_tiktok",
                           espectadores=1, espectadores_total=108)
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "1 espectador ahora, 108 en total.")
        self.assertEqual(formatear_estado(s, {"espectadores"}, "largo"),
                         "Espectador: 1 ahora, 108 en total")

    def test_youtube_ignora_el_total(self):
        s = SnapshotSesion(conectado=True, tipo="live_youtube",
                           espectadores=12, espectadores_total=108)
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "12 espectadores.")

    def test_youtube_con_uno_usa_el_singular(self):
        s = SnapshotSesion(conectado=True, tipo="live_youtube", espectadores=1)
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "1 espectador.")
        self.assertEqual(formatear_estado(s, {"espectadores"}, "largo"),
                         "Espectador: 1")

    def test_vod_con_una_usa_el_singular(self):
        s = SnapshotSesion(conectado=True, tipo="vod", espectadores=1)
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "1 vista.")
        self.assertEqual(formatear_estado(s, {"espectadores"}, "largo"),
                         "Vista: 1")


class TestEtiquetaEspectadores(unittest.TestCase):

    def test_casilla_dice_ahora_y_en_total(self):
        self.assertEqual(ETIQUETAS["espectadores"],
                         "Espectadores ahora y en total")


class TestRamasSinCubrir(unittest.TestCase):
    """Caracterización de las ramas que la cobertura del 16/10/2026 mostró
    sin ejecutar en _render: se fijan contra el código de hoy."""

    def test_conectado_sin_tipo_dice_conectado(self):
        s = SnapshotSesion(conectado=True, tipo="")
        self.assertEqual(formatear_estado(s, {"estado"}), "Conectado.")

    def test_vistas_en_video_no_en_directo(self):
        s = SnapshotSesion(conectado=True, tipo="vod", espectadores=1000)
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "1.000 vistas.")
        self.assertEqual(formatear_estado(s, {"espectadores"}, "largo"),
                         "Vistas: 1.000")

    def test_espectadores_no_numericos_pasan_como_texto(self):
        s = SnapshotSesion(conectado=True, tipo="live_youtube",
                           espectadores="muchos")
        self.assertEqual(formatear_estado(s, {"espectadores"}),
                         "muchos espectadores.")

    def test_en_cola_corto_y_largo(self):
        s = SnapshotSesion(en_cola=3)
        self.assertEqual(formatear_estado(s, {"en_cola"}), "3 en cola.")
        self.assertEqual(formatear_estado(s, {"en_cola"}, "largo"),
                         "En cola: 3")

    def test_voz_muestra_velocidad_y_volumen(self):
        s = SnapshotSesion(voz_velocidad=0, voz_volumen=0)
        self.assertEqual(formatear_estado(s, {"voz"}),
                         "Voz: velocidad 0, volumen 0%.")

    def test_mensajes_leidos_largo(self):
        s = SnapshotSesion(mensajes_leidos=10)
        self.assertEqual(formatear_estado(s, {"mensajes_leidos"}, "largo"),
                         "Mensajes leídos: 10")

    def test_aportes_youtube_sin_total_corto(self):
        s = SnapshotSesion(conectado=True, tipo="live_youtube", aportes=3)
        self.assertEqual(formatear_estado(s, {"aportes"}), "3 Super Chats.")

    def test_aportes_largo_con_total(self):
        s = SnapshotSesion(conectado=True, tipo="live_youtube", aportes=3,
                           total_aportes="US$12,50")
        self.assertEqual(formatear_estado(s, {"aportes"}, "largo"),
                         "Aportes: 3 Super Chats (US$12,50)")

    def test_desfase_largo_sin_atajo_da_menu(self):
        s = SnapshotSesion(desfase_directo="10 segundos por detrás del directo",
                           atajo_directo="")
        self.assertEqual(
            formatear_estado(s, {"desfase_directo"}, "largo"),
            "Reproductor: 10 segundos por detrás del directo. "
            "Para volver: menú Reproductor, Ir al directo.")

    def test_obs_grabacion_y_escena(self):
        s = SnapshotSesion(obs_grabacion="Grabando desde hace 2 min",
                           obs_escena="Juego")
        self.assertEqual(formatear_estado(s, {"obs_grabacion"}),
                         "Grabando desde hace 2 min.")
        self.assertEqual(formatear_estado(s, {"obs_escena"}), "Juego.")
        self.assertEqual(formatear_estado(SnapshotSesion(),
                                         {"obs_grabacion", "obs_escena"}), "")

    def test_nombre_desconocido_da_vacio(self):
        self.assertEqual(_render("inventado", SnapshotSesion(), False), "")


class TestPseudoF2(unittest.TestCase):
    """Todo texto fijo de F2 pasa por gettext, en largo y en corto."""

    # Componentes con frase propia en estado_sesion (el resto llega armado
    # de otro módulo y dato crudo como el título corto no se marca).
    FIJOS = ("estado", "canal", "espectadores", "tiempo_directo",
             "desfase_directo", "mensajes_leidos", "aportes", "en_cola",
             "voz", "lectura_silenciada", "overlay")

    def _lleno(self, tipo):
        return SnapshotSesion(
            conectado=True, tipo=tipo, titulo="T", canal="C",
            espectadores=12, espectadores_total=108,
            segundos_directo=83 * 60,
            desfase_directo="10 segundos por detrás del directo",
            atajo_directo="Ctrl+Fin", mensajes_leidos=10, aportes=3,
            total_aportes="US$12,50", en_cola=3, voz_velocidad=5,
            voz_volumen=80, lectura_silenciada=True, overlay_puerto=9000,
            overlay_clientes=1)

    def test_fijos_marcados_en_largo_y_corto(self):
        for tipo in ("live_youtube", "live_tiktok"):
            snap = self._lleno(tipo)
            for modo in ("corto", "largo"):
                for comp in self.FIJOS:
                    with self.subTest(tipo=tipo, modo=modo, comp=comp):
                        with con_pseudo():
                            out = formatear_estado(snap, {comp}, modo=modo)
                        self.assertTrue(out, f"{comp} vacío en {tipo} {modo}")
                        self.assertIn("[¡", out, f"{comp} sin marcar en {tipo} {modo}")

    def test_titulo_largo_marcado_y_corto_crudo(self):
        snap = SnapshotSesion(titulo="T")
        with con_pseudo():
            largo = formatear_estado(snap, {"titulo"}, modo="largo")
        self.assertIn("[¡", largo)
        self.assertEqual(formatear_estado(snap, {"titulo"}), "T.")

    def test_supervisada_larga_marcada_y_corta_cruda(self):
        snap = SnapshotSesion(transmision_supervisada="Supervisada")
        with con_pseudo():
            largo = formatear_estado(snap, set(), modo="largo")
        self.assertIn("[¡", largo)
        self.assertEqual(formatear_estado(snap, set()), "Supervisada.")

    def test_etiqueta_de_cada_componente_marcada(self):
        self.assertTrue(callable(getattr(estado_sesion, "etiqueta", None)),
                        "falta estado_sesion.etiqueta")
        for comp in COMPONENTES:
            with self.subTest(comp=comp):
                with con_pseudo():
                    texto = estado_sesion.etiqueta(comp)
                self.assertIn("[¡", texto, f"etiqueta {comp} sin marcar")

    def test_etiqueta_directa_del_catalogo(self):
        from bellbird.capture.componentes_estado import etiqueta as directa
        with con_pseudo():
            texto = directa("estado")
        self.assertIn("[¡", texto)


class TestPluralesTanda2(unittest.TestCase):
    """Cada ngettext de estado_sesion: con 1 singular y con 2 plural."""

    def test_todas_las_ramas_con_uno_y_dos(self):
        for n, singular in ((1, True), (2, False)):
            with self.subTest(n=n):
                # Aportes: YouTube y TikTok, largo y corto, con y sin total.
                for tipo, etiqueta in (("live_tiktok", "regalo"),
                                       ("live_youtube", "Super Chat")):
                    for modo in ("corto", "largo"):
                        for con_total in (False, True):
                            total = "US$%d,00" % n if con_total else ""
                            snap = SnapshotSesion(conectado=True, tipo=tipo,
                                                  aportes=n, total_aportes=total)
                            if etiqueta == "regalo":
                                nombre = "regalo" if n == 1 else "regalos"
                            else:
                                nombre = "Super Chat" if n == 1 else "Super Chats"
                            if modo == "largo":
                                esperado = "Aportes: %d %s" % (n, nombre)
                            else:
                                esperado = "%d %s" % (n, nombre)
                            if con_total:
                                esperado += " (%s)" % total
                            if modo == "corto":
                                esperado += "."
                            with self.subTest(tipo=tipo, modo=modo,
                                              total=con_total):
                                self.assertEqual(
                                    formatear_estado(snap, {"aportes"}, modo),
                                    esperado)
                # Espectadores TikTok con total, largo y corto.
                for modo, esperado in (
                        ("largo", ("Espectador: 1 ahora, 10 en total"
                                   if n == 1 else
                                   "Espectadores: 2 ahora, 10 en total")),
                        ("corto", ("1 espectador ahora, 10 en total."
                                   if n == 1 else
                                   "2 espectadores ahora, 10 en total."))):
                    snap = SnapshotSesion(conectado=True, tipo="live_tiktok",
                                          espectadores=n, espectadores_total=10)
                    with self.subTest(comp="tiktok-total", modo=modo):
                        self.assertEqual(
                            formatear_estado(snap, {"espectadores"}, modo),
                            esperado)
                # Espectadores YouTube y vistas, largo y corto.
                for tipo, largo_s, largo_p, corto_s, corto_p in (
                        ("live_youtube", "Espectador: %d", "Espectadores: %d",
                         "%d espectador.", "%d espectadores."),
                        ("vod", "Vista: %d", "Vistas: %d",
                         "%d vista.", "%d vistas.")):
                    snap = SnapshotSesion(conectado=True, tipo=tipo,
                                          espectadores=n)
                    with self.subTest(comp=tipo, modo="largo"):
                        self.assertEqual(
                            formatear_estado(snap, {"espectadores"}, "largo"),
                            (largo_s if n == 1 else largo_p) % n)
                    with self.subTest(comp=tipo, modo="corto"):
                        self.assertEqual(
                            formatear_estado(snap, {"espectadores"}),
                            (corto_s if n == 1 else corto_p) % n)
                # Leídos y en cola, corto.
                with self.subTest(comp="leidos"):
                    self.assertEqual(
                        formatear_estado(SnapshotSesion(mensajes_leidos=n),
                                         {"mensajes_leidos"}),
                        "1 leído." if n == 1 else "2 leídos.")
                with self.subTest(comp="cola"):
                    self.assertEqual(
                        formatear_estado(SnapshotSesion(en_cola=n), {"en_cola"}),
                        "%d en cola." % n)
                # Días: el singular es inalcanzable por el corte de 48 horas.
                with self.subTest(comp="dias"):
                    self.assertEqual(
                        formatear_estado(
                            SnapshotSesion(segundos_directo=2 * 24 * 3600),
                            {"tiempo_directo"}),
                        "Lleva 2 días.")
                    self.assertEqual(
                        formatear_estado(
                            SnapshotSesion(segundos_directo=2 * 24 * 3600),
                            {"tiempo_directo"}, "largo"),
                        "Tiempo del directo: 2 días")


if __name__ == "__main__":
    unittest.main()

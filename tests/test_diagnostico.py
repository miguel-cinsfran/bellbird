import importlib
import logging
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from bellbird.core import config
from bellbird.core import diagnostico
from tests.rutas_temporales import redirigir_rutas


class DiagnosticoTest(unittest.TestCase):
    def test_obtener_logger_cuelga_del_arbol_de_la_aplicacion(self):
        logger = diagnostico.obtener_logger("descargas")
        self.assertTrue(logger.name.startswith("bellbird."))

    def test_los_loggers_de_la_aplicacion_cuelgan_del_arbol_ytchat(self):
        raiz = Path(__file__).resolve().parent.parent
        descubiertos = 0
        for ruta in sorted((raiz / "bellbird").rglob("*.py")):
            if ruta.name == "__init__.py":
                continue
            descubiertos += 1
            nombre = "bellbird." + ".".join(
                ruta.relative_to(raiz).with_suffix("").parts[1:])
            modulo = importlib.import_module(nombre)
            logger = getattr(modulo, "logger", None)
            if isinstance(logger, logging.Logger):
                self.assertTrue(
                    logger.name.startswith("bellbird."),
                    f"El logger del módulo {nombre} está fuera del árbol bellbird: "
                    f"{logger.name}")
        self.assertGreaterEqual(
            descubiertos, 50,
            f"la guarda recorrió solo {descubiertos} módulos en bellbird/: "
            "si se movieron las carpetas, hay que actualizarla en vez de "
            "dejarla en verde sin mirar nada")

    def test_compone_marcas_de_inicio_y_cierre_con_zona_horaria(self):
        momento = datetime(2026, 8, 25, 21, 52, 9,
                           tzinfo=timezone(timedelta(hours=-4)))
        inicio = diagnostico.componer_cabecera_fallos("2.0.1", momento)
        cierre = diagnostico.componer_cierre_fallos(momento)
        self.assertEqual(inicio,
                         "=== INICIO Bellbird v2.0.1 2026-08-25T21:52:09-04:00 ===\n"
                         "Este archivo anota sucesos internos de Windows; muchos son inofensivos y la aplicación sigue funcionando. Si ves «CIERRE LIMPIO», la sesión terminó bien.")
        self.assertEqual(cierre, "=== CIERRE LIMPIO 2026-08-25T21:52:09-04:00 ===")
        self.assertNotEqual(inicio, cierre)

    def test_manejador_detallado_tiene_nivel_rotacion_y_formato(self):
        with tempfile.TemporaryDirectory() as tmp:
            manejador = diagnostico.crear_manejador_detallado(Path(tmp) / "x.log")
            try:
                self.assertEqual(manejador.level, logging.DEBUG)
                self.assertEqual(manejador.maxBytes, 5 * 1024 * 1024)
                self.assertEqual(manejador.backupCount, 3)
                self.assertIn("%(threadName)s", manejador.formatter._fmt)
                self.assertIn("%(name)s", manejador.formatter._fmt)
            finally:
                manejador.close()

    def test_manejador_detallado_acepta_registro_propio(self):
        with patch.object(diagnostico, "RotatingFileHandler", return_value=logging.Handler()):
            manejador = diagnostico.crear_manejador_detallado("x.log")
        registro = logging.LogRecord(
            "bellbird.loquesea", logging.DEBUG, "", 0, "prueba", (), None)
        self.assertTrue(manejador.filter(registro))

    def test_manejador_detallado_rechaza_registro_de_websockets(self):
        with patch.object(diagnostico, "RotatingFileHandler", return_value=logging.Handler()):
            manejador = diagnostico.crear_manejador_detallado("x.log")
        registro = logging.LogRecord(
            "websockets.client", logging.DEBUG, "", 0, "prueba", (), None)
        self.assertFalse(manejador.filter(registro))

    def test_manejador_detallado_rota_el_registro_anterior_al_arrancar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "x.log"
            ruta.write_text("sesion anterior", encoding="utf-8")
            manejador = diagnostico.crear_manejador_detallado(ruta)
            try:
                self.assertEqual(ruta.read_text(encoding="utf-8"), "")
                self.assertEqual(
                    ruta.with_name("x.log.1").read_text(encoding="utf-8"),
                    "sesion anterior")
            finally:
                manejador.close()

    def test_volcado_incluye_datos_y_faltantes(self):
        texto = diagnostico.componer_volcado_entorno(
            "2.0.0", vlc_version="3.0", ytdlp_version="2025.1", gpu="Placa",
            lector="NVDA")
        self.assertIn("Versión de la aplicación: 2.0.0", texto)
        self.assertIn("Versión de libVLC: 3.0", texto)
        self.assertIn("Placa de vídeo: Placa", texto)
        self.assertIn("ENTORNO inicio", texto)
        self.assertIn("Lector de pantalla activo: NVDA", texto)

    def test_lector_activo_devuelve_el_nombre(self):
        from bellbird.voice import lector as modulo_lector
        falso = MagicMock()
        falso.return_value.nombre.return_value = "NVDA"
        with patch.object(modulo_lector, "Lector", falso):
            self.assertEqual(diagnostico._lector_activo(), ("NVDA", None))

    def test_lector_activo_sin_lector_explica_el_motivo(self):
        from bellbird.voice import lector as modulo_lector
        falso = MagicMock()
        falso.return_value.nombre.return_value = None
        with patch.object(modulo_lector, "Lector", falso):
            self.assertEqual(
                diagnostico._lector_activo(),
                (None, "no se detectó un lector de pantalla activo"))

    def test_placa_video_oculta_la_ventana_del_subproceso(self):
        resultado = MagicMock(stdout="Placa", stderr="")
        with patch.object(diagnostico.os, "name", "nt"), \
                patch.object(diagnostico.subprocess, "CREATE_NO_WINDOW", 134217728), \
                patch.object(diagnostico.subprocess, "run", return_value=resultado) as ejecutar:
            diagnostico._placa_video()
        self.assertEqual(ejecutar.call_args.kwargs["creationflags"], 134217728)

    def test_censo_incluye_hilo_actual(self):
        nombres, _externos = diagnostico.censo_hilos()
        self.assertIn(threading.current_thread().name, nombres)
        self.assertIn("vivos=", diagnostico.componer_censo_hilos())

    def test_vigilante_informa_bloqueo_sobre_umbral(self):
        registrar, activo = diagnostico.decidir_bloqueo_interfaz(10.0, 10.6, False)
        texto = diagnostico.componer_bloqueo_interfaz(600, "pila de interfaz")
        self.assertTrue(registrar)
        self.assertTrue(activo)
        self.assertIn("bloqueada_ms=600", texto)

    def test_vigilante_no_informa_demora_normal(self):
        self.assertEqual(
            diagnostico.decidir_bloqueo_interfaz(10.0, 10.4, False), (False, False))

    def test_latido_sin_cambio_no_esta_vivo(self):
        self.assertFalse(diagnostico.esta_vivo_el_latido(1.0, 1.0, False))

    def test_latido_con_cambio_esta_vivo(self):
        self.assertTrue(diagnostico.esta_vivo_el_latido(1.0, 1.1, False))

    def test_latido_vivo_no_muere_si_deja_de_cambiar(self):
        self.assertTrue(diagnostico.esta_vivo_el_latido(1.0, 1.0, True))

    def test_vigilante_ignora_latido_que_nunca_cambia(self):
        class Parada:
            def __init__(self):
                self.llamadas = 0

            def wait(self, _intervalo):
                self.llamadas += 1
                return self.llamadas > 2

        with patch.object(diagnostico.time, "monotonic", side_effect=[1.0, 2.0]), \
                patch.object(diagnostico.logger, "warning") as registrar:
            diagnostico.vigilar_hilo_interfaz(lambda: 0.0, Parada())
        registrar.assert_not_called()

    def test_vigilante_informa_latido_atrasado_despues_de_moverse(self):
        class Parada:
            def __init__(self):
                self.llamadas = 0

            def wait(self, _intervalo):
                self.llamadas += 1
                return self.llamadas > 2

        marcas = iter((0.0, 0.1))
        with patch.object(diagnostico.time, "monotonic", side_effect=[1.0, 1.1]), \
                patch.object(diagnostico.sys, "_current_frames", return_value={}), \
                patch.object(diagnostico.logger, "warning") as registrar:
            diagnostico.vigilar_hilo_interfaz(lambda: next(marcas), Parada())
        registrar.assert_called_once()

    def test_vigilante_registra_un_solo_bloqueo_largo(self):
        self.assertEqual(
            diagnostico.decidir_bloqueo_interfaz(10.0, 11.0, False), (True, True))
        self.assertEqual(
            diagnostico.decidir_bloqueo_interfaz(10.0, 11.5, True), (False, True))

    def test_pila_del_vigilante_toma_el_marco_del_hilo_principal(self):
        principal = object()
        vigilante = object()
        with patch.object(
                diagnostico.traceback, "format_stack",
                side_effect=lambda marco: ["GUI"] if marco is principal else ["VIGILANTE"]):
            pila = diagnostico.pila_hilo_interfaz({101: principal, 202: vigilante}, 101)
        self.assertEqual(pila, "GUI")

    def test_pila_no_usa_el_marco_del_vigilante(self):
        with patch.object(diagnostico.traceback, "format_stack", return_value=["VIGILANTE"]):
            pila = diagnostico.pila_hilo_interfaz({202: object()}, 101)
        self.assertEqual(pila, "no disponible")

    def test_vigilante_no_repite_un_bloqueo_largo(self):
        class Parada:
            def __init__(self):
                self.llamadas = 0

            def wait(self, _intervalo):
                self.llamadas += 1
                return self.llamadas > 2

        with patch.object(diagnostico.time, "monotonic", side_effect=[1.0, 1.1]), \
                patch.object(diagnostico.sys, "_current_frames", return_value={}), \
                patch.object(diagnostico.logger, "warning") as registrar:
            marcas = iter((0.0, 0.1))
            diagnostico.vigilar_hilo_interfaz(lambda: next(marcas), Parada())
        registrar.assert_called_once()

    def test_vigilante_retrata_el_hilo_principal_desde_otro_hilo(self):
        principal = threading.main_thread().ident
        identificadores = []

        class Parada:
            def __init__(self):
                self.llamadas = 0

            def wait(self, _intervalo):
                self.llamadas += 1
                return self.llamadas > 2

        def recordar(_marcos, identificador):
            identificadores.append(identificador)
            return "pila"

        marcas = iter((0.0, 0.1))
        with patch.object(diagnostico.time, "monotonic", return_value=1.0), \
                patch.object(diagnostico.sys, "_current_frames", return_value={}), \
                patch.object(diagnostico, "pila_hilo_interfaz", side_effect=recordar), \
                patch.object(diagnostico.logger, "warning"):
            hilo = threading.Thread(
                target=diagnostico.vigilar_hilo_interfaz,
                args=(lambda: next(marcas), Parada()))
            hilo.start()
            hilo.join()

        self.assertEqual(identificadores, [principal])
        self.assertNotEqual(principal, hilo.ident)

    def test_hilo_de_aplicacion_registra_inicio_y_fin(self):
        llamadas = []
        with patch.object(diagnostico.logger, "info") as registrar:
            hilo = diagnostico.crear_hilo(lambda: llamadas.append(True), "HiloPrueba")
            hilo.start()
            hilo.join()
        self.assertEqual(llamadas, [True])
        mensajes = [llamada.args[0] for llamada in registrar.call_args_list]
        self.assertEqual(mensajes, ["HILO inicia nombre=%s", "HILO termina nombre=%s"])
        self.assertEqual(registrar.call_args_list[1].args[1], "HiloPrueba")

    def test_marcar_incidencia_escribe_marca_visible(self):
        with patch.object(diagnostico.logger, "warning") as registrar:
            marca = diagnostico.marcar_incidencia()
        self.assertTrue(marca)
        registrar.assert_called_once_with("INCIDENCIA usuario marca=%s", marca)

    def test_configuracion_instala_registro_detallado_si_esta_activado(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.ini").write_text(
                "[diagnostico]\nregistro_detallado = true\n", encoding="utf-8")
            raiz = logging.getLogger()
            previos = list(raiz.handlers)
            for manejador in previos:
                raiz.removeHandler(manejador)
            try:
                with redirigir_rutas(tmp):
                    config.configurar_logging()
                self.assertTrue(any(
                    isinstance(m, logging.handlers.RotatingFileHandler)
                    and Path(m.baseFilename).name == "bellbird-debug.log"
                    for m in raiz.handlers))
            finally:
                for manejador in raiz.handlers[:]:
                    raiz.removeHandler(manejador)
                    manejador.close()
                for manejador in previos:
                    raiz.addHandler(manejador)

    def test_capturadores_registran_excepciones_de_hilos(self):
        anterior_sys = sys.excepthook
        anterior_hilos = threading.excepthook
        try:
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    with patch.object(sys, "excepthook"), \
                         patch.object(threading, "excepthook"), \
                         patch("faulthandler.enable") as activar, \
                         patch.object(diagnostico.logger, "critical") as registrar:
                        diagnostico.instalar_capturadores(Path(tmp) / "fallos.log")
                        error = RuntimeError("prueba")
                        hilo = MagicMock()
                        hilo.name = "HiloPrueba"
                        args = MagicMock(exc_type=RuntimeError, exc_value=error,
                                         exc_traceback=None, thread=hilo)
                        threading.excepthook(args)
                        self.assertIn("HiloPrueba", registrar.call_args.args[1])
                        activar.assert_called_once()
                finally:
                    if diagnostico._ARCHIVO_FALLOS is not None:
                        diagnostico._ARCHIVO_FALLOS.close()
                        diagnostico._ARCHIVO_FALLOS = None
        finally:
            sys.excepthook = anterior_sys
            threading.excepthook = anterior_hilos

    def test_capturadores_escriben_cabecera_antes_de_activar_faulthandler(self):
        anterior = diagnostico._ARCHIVO_FALLOS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ruta = Path(tmp) / "fallos.log"
                with patch("faulthandler.enable"):
                    diagnostico.instalar_capturadores(ruta, version="2.0.1")
                self.assertIn("INICIO Bellbird v2.0.1", ruta.read_text(encoding="utf-8"))
                diagnostico._ARCHIVO_FALLOS.close()
                diagnostico._ARCHIVO_FALLOS = None
        finally:
            if diagnostico._ARCHIVO_FALLOS is not None:
                diagnostico._ARCHIVO_FALLOS.close()
            diagnostico._ARCHIVO_FALLOS = anterior

    def test_hilo_creado_aparece_mientras_corre_y_desaparece_al_terminar(self):
        inicio = threading.Event()
        fin = threading.Event()

        def tarea():
            inicio.set()
            fin.wait()

        hilo = diagnostico.crear_hilo(tarea, "HiloPruebaVivo")
        hilo.start()
        self.assertTrue(inicio.wait(timeout=2))
        self.assertIn("HiloPruebaVivo", diagnostico.hilos_vivos_de_la_aplicacion())
        fin.set()
        hilo.join(timeout=2)
        self.assertNotIn("HiloPruebaVivo", diagnostico.hilos_vivos_de_la_aplicacion())

    def test_hilo_creado_y_no_arrancado_no_aparece(self):
        hilo = diagnostico.crear_hilo(lambda: None, "HiloNoArrancadoUnico")
        self.assertNotIn("HiloNoArrancadoUnico", diagnostico.hilos_vivos_de_la_aplicacion())
        self.assertNotIn(hilo, diagnostico._hilos_vivos)
        # No se arranca a proposito: no debe quedar registrado.
        del hilo

    def test_dos_hilos_con_mismo_nombre_se_cuentan_por_separado(self):
        inicio1 = threading.Event()
        inicio2 = threading.Event()
        fin1 = threading.Event()
        fin2 = threading.Event()

        def tarea1():
            inicio1.set()
            fin1.wait()

        def tarea2():
            inicio2.set()
            fin2.wait()

        hilo1 = diagnostico.crear_hilo(tarea1, "HiloDuplicado")
        hilo2 = diagnostico.crear_hilo(tarea2, "HiloDuplicado")
        try:
            hilo1.start()
            hilo2.start()
            self.assertTrue(inicio1.wait(timeout=2))
            self.assertTrue(inicio2.wait(timeout=2))
            self.assertEqual(
                tuple(
                    n
                    for n in diagnostico.hilos_vivos_de_la_aplicacion()
                    if n == "HiloDuplicado"
                ),
                ("HiloDuplicado", "HiloDuplicado"),
            )
            fin1.set()
            hilo1.join(timeout=2)
            self.assertEqual(
                tuple(
                    n
                    for n in diagnostico.hilos_vivos_de_la_aplicacion()
                    if n == "HiloDuplicado"
                ),
                ("HiloDuplicado",),
            )
            fin2.set()
            hilo2.join(timeout=2)
            self.assertEqual(
                tuple(
                    n
                    for n in diagnostico.hilos_vivos_de_la_aplicacion()
                    if n == "HiloDuplicado"
                ),
                (),
            )
        finally:
            fin1.set()
            fin2.set()
            hilo1.join(timeout=2)
            hilo2.join(timeout=2)

    def test_hilos_distintos_salen_ordenados(self):
        inicio1 = threading.Event()
        inicio2 = threading.Event()
        fin1 = threading.Event()
        fin2 = threading.Event()

        def tarea1():
            inicio1.set()
            fin1.wait()

        def tarea2():
            inicio2.set()
            fin2.wait()

        hilo1 = diagnostico.crear_hilo(tarea1, "ZebraUnicoOrden")
        hilo2 = diagnostico.crear_hilo(tarea2, "AlfaUnicoOrden")
        try:
            hilo1.start()
            hilo2.start()
            self.assertTrue(inicio1.wait(timeout=2))
            self.assertTrue(inicio2.wait(timeout=2))
            self.assertEqual(
                tuple(
                    n
                    for n in diagnostico.hilos_vivos_de_la_aplicacion()
                    if n in ("AlfaUnicoOrden", "ZebraUnicoOrden")
                ),
                ("AlfaUnicoOrden", "ZebraUnicoOrden"),
            )
        finally:
            fin1.set()
            fin2.set()
            hilo1.join(timeout=2)
            hilo2.join(timeout=2)

    def test_crear_hilo_da_de_baja_el_registro_interno_al_terminar(self):
        listo = threading.Event()

        def tarea():
            listo.set()

        hilo = diagnostico.crear_hilo(tarea, "HiloBajaRegistroUnico")
        hilo.start()
        self.assertTrue(listo.wait(timeout=2))
        hilo.join(timeout=2)
        try:
            with diagnostico._bloqueo_hilos:
                self.assertNotIn(hilo, diagnostico._hilos_vivos)
        finally:
            with diagnostico._bloqueo_hilos:
                diagnostico._hilos_vivos.discard(hilo)

    def test_instalar_capturadores_activa_faulthandler_solo_hilo_propio(self):
        anterior_sys = sys.excepthook
        anterior_hilos = threading.excepthook
        anterior = diagnostico._ARCHIVO_FALLOS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    with patch("faulthandler.enable") as activar:
                        diagnostico.instalar_capturadores(Path(tmp) / "fallos.log")
                    self.assertEqual(activar.call_count, 1)
                    self.assertFalse(activar.call_args.kwargs.get("all_threads", True))
                finally:
                    if diagnostico._ARCHIVO_FALLOS is not None:
                        diagnostico._ARCHIVO_FALLOS.close()
                        diagnostico._ARCHIVO_FALLOS = None
        finally:
            sys.excepthook = anterior_sys
            threading.excepthook = anterior_hilos
            diagnostico._ARCHIVO_FALLOS = anterior

    def test_faulthandler_real_solo_vuelca_el_hilo_propio(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            ruta = str(Path(tmp) / "fallos.log")
            guion = (
                "import sys, threading, time, ctypes\n"
                "from bellbird.core import diagnostico\n"
                "ruta = sys.argv[1]\n"
                "diagnostico.instalar_capturadores(ruta, version='prueba')\n"
                "listo = threading.Event()\n"
                "fin = threading.Event()\n"
                "def espera():\n"
                "    listo.set()\n"
                "    fin.wait(timeout=10)\n"
                "hilo = threading.Thread(target=espera, daemon=True)\n"
                "hilo.start()\n"
                "listo.wait(timeout=5)\n"
                "try:\n"
                "    ctypes.windll.kernel32.RaiseException(0x80010108, 0, 0, None)\n"
                "except OSError:\n"
                "    pass\n"
                "time.sleep(1.0)\n"
                "fin.set()\n"
                "hilo.join(timeout=5)\n"
            )
            proceso = subprocess.run(
                [sys.executable, "-c", guion, ruta],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(
                proceso.returncode, 0,
                f"el subproceso falló: returncode={proceso.returncode} "
                f"stderr={proceso.stderr[-2000:]}")
            contenido = Path(ruta).read_text(encoding="utf-8", errors="replace")
            self.assertIn("Windows fatal exception: code 0x80010108", contenido)
            self.assertNotIn("Thread 0x", contenido)


class PruebasCensoHilosSinRepetir(unittest.TestCase):
    """El censo solo sale cuando cambia la lista o pasan diez minutos."""

    def setUp(self):
        parches = (
            patch.object(diagnostico, "_ultimo_censo_nombres", None, create=True),
            patch.object(diagnostico, "_ultimo_censo_momento", 0.0, create=True),
            patch.object(diagnostico, "_ultimo_chequeo", 0.0, create=True),
        )
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)

    def test_la_misma_lista_a_los_30_segundos_no_sale(self):
        with patch.object(diagnostico, "censo_hilos",
                          return_value=(("MainThread", "Sonidos"), 0)):
            primero = diagnostico.debe_censar_hilos(-30.0, 0.0)
            segundo = diagnostico.debe_censar_hilos(0.0, 30.0)

        self.assertIsNotNone(primero)
        self.assertIsNone(segundo)

    def test_un_hilo_nuevo_sale_aunque_no_pasen_diez_minutos(self):
        nombres = [(("MainThread", "Sonidos"), 0),
                   (("MainThread", "Sonidos"), 0),
                   (("MainThread", "Nuevo", "Sonidos"), 0)]
        with patch.object(diagnostico, "censo_hilos", side_effect=nombres):
            primero = diagnostico.debe_censar_hilos(-30.0, 0.0)
            segundo = diagnostico.debe_censar_hilos(0.0, 30.0)
            tercero = diagnostico.debe_censar_hilos(0.0, 60.0)

        self.assertIsNotNone(primero)
        self.assertIsNone(segundo)
        self.assertIsNotNone(tercero)
        self.assertIn("Nuevo", tercero[1])

    def test_la_misma_lista_a_los_diez_minutos_sale(self):
        with patch.object(diagnostico, "censo_hilos",
                          return_value=(("MainThread", "Sonidos"), 0)):
            primero = diagnostico.debe_censar_hilos(-30.0, 0.0)
            segundo = diagnostico.debe_censar_hilos(
                0.0, diagnostico.INTERVALO_CENSO_REPETIDO_S)

        self.assertIsNotNone(primero)
        self.assertIsNotNone(segundo)
        self.assertEqual(primero[1], segundo[1])


class PruebasRotacionFallos(unittest.TestCase):
    def test_mas_de_un_mibi_rota(self):
        self.assertTrue(
            diagnostico.debe_rotar_fallos(diagnostico.TOPE_FALLOS_BYTES + 1))

    def test_justo_un_mibi_no_rota(self):
        self.assertFalse(
            diagnostico.debe_rotar_fallos(diagnostico.TOPE_FALLOS_BYTES))

    def test_instalar_capturadores_rota_el_archivo_de_mas_de_un_mibi(self):
        import faulthandler
        anterior_sys = sys.excepthook
        anterior_hilos = threading.excepthook
        anterior = diagnostico._ARCHIVO_FALLOS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ruta = Path(tmp) / "fallos.log"
                viejo = b"v" * (diagnostico.TOPE_FALLOS_BYTES + 1)
                ruta.write_bytes(viejo)
                diagnostico.instalar_capturadores(ruta, version="prueba")
                try:
                    rotado = ruta.with_name(ruta.name + ".1")
                    self.assertTrue(rotado.exists())
                    self.assertEqual(rotado.read_bytes(), viejo)
                    nuevo = ruta.read_text(encoding="utf-8")
                    self.assertTrue(nuevo.startswith("=== INICIO"))
                finally:
                    faulthandler.disable()
                    if diagnostico._ARCHIVO_FALLOS is not None:
                        diagnostico._ARCHIVO_FALLOS.close()
                        diagnostico._ARCHIVO_FALLOS = None
        finally:
            sys.excepthook = anterior_sys
            threading.excepthook = anterior_hilos
            diagnostico._ARCHIVO_FALLOS = anterior


class PruebasCensoExternos(unittest.TestCase):
    def setUp(self):
        parches = (
            patch.object(diagnostico, "_ultimo_censo_nombres", None, create=True),
            patch.object(diagnostico, "_ultimo_censo_momento", 0.0, create=True),
            patch.object(diagnostico, "_ultimo_chequeo", 0.0, create=True),
        )
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)

    def test_censo_agrupa_los_externos_y_ordena_los_propios(self):
        hilos = []
        for nombre in ("Zebra", "Dummy-9", "Alfa", "Dummy-18"):
            hilo = MagicMock()
            hilo.name = nombre
            hilo.is_alive.return_value = True
            hilos.append(hilo)
        with patch.object(diagnostico.threading, "enumerate", return_value=hilos):
            self.assertEqual(
                diagnostico.censo_hilos(), (("Alfa", "Zebra"), 2))

    def test_componer_muestra_vivos_externos_y_nombres(self):
        texto = diagnostico.componer_censo_hilos((("MainThread", "Sonidos"), 5))
        self.assertEqual(
            texto, "HILOS vivos=7 externos=5 nombres=MainThread, Sonidos")

    def test_componer_sin_externos_no_muestra_externos(self):
        texto = diagnostico.componer_censo_hilos((("MainThread", "Sonidos"), 0))
        self.assertEqual(texto, "HILOS vivos=2 nombres=MainThread, Sonidos")
        self.assertNotIn("externos=", texto)

    def test_cambio_de_numero_externo_no_sale(self):
        censos = [(("MainThread",), 1), (("MainThread",), 1)]
        with patch.object(diagnostico, "censo_hilos", side_effect=censos):
            primero = diagnostico.debe_censar_hilos(-30.0, 0.0)
            segundo = diagnostico.debe_censar_hilos(0.0, 30.0)

        self.assertIsNotNone(primero)
        self.assertIsNone(segundo)

    def test_cambio_de_cantidad_de_externos_si_sale(self):
        censos = [(("MainThread",), 1), (("MainThread",), 2)]
        with patch.object(diagnostico, "censo_hilos", side_effect=censos):
            primero = diagnostico.debe_censar_hilos(-30.0, 0.0)
            segundo = diagnostico.debe_censar_hilos(0.0, 30.0)

        self.assertIsNotNone(primero)
        self.assertIsNotNone(segundo)
        self.assertIn("externos=2", segundo[1])


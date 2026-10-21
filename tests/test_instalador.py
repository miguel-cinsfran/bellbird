"""Pruebas del instalador sobre carpetas temporales reales."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ytchat.core import instalador
from ytchat.core import paths


DESDE = "2.1.0"
HACIA = "2.2.0"
EXE_VIEJO = "Viejo.exe"
EXE_NUEVO = "Nuevo.exe"

GUIÓN_OK = (
    "import sys, time\n"
    "open(sys.argv[1], 'w').write('ok')\n"
)
GUIÓN_MALO = "import time\ntime.sleep(30)\n"
GUIÓN_SALE = "pass\n"


def _foto(carpeta: Path) -> dict:
    foto = {}
    for ruta in sorted(carpeta.rglob("*")):
        if ruta.is_file():
            foto[str(ruta.relative_to(carpeta))] = ruta.read_bytes()
    return foto


def _es_estado(clave: str) -> bool:
    return Path(clave).parts[:2] == ("data", "actualizacion")


def _sin_estado(foto: dict) -> dict:
    return {k: v for k, v in foto.items() if not _es_estado(k)}


def _foto_datos_usuario(carpeta_data: Path) -> dict:
    return {k: v for k, v in _foto(carpeta_data).items()
            if Path(k).parts[0] != "actualizacion"}


class BaseInstalador(unittest.TestCase):
    guion_nuevo = GUIÓN_OK

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._cerrar_registro)
        tmp = Path(self._tmp.name)
        self.instalacion = tmp / "instalacion"
        self.fuente_paquete = tmp / "fuente"
        self.guion_ok = tmp / "guion_ok.py"
        self.guion_ok.write_text(GUIÓN_OK, encoding="utf-8")
        self.guion_malo = tmp / "guion_malo.py"
        self.guion_malo.write_text(GUIÓN_MALO, encoding="utf-8")
        self.guion_sale = tmp / "guion_sale.py"
        self.guion_sale.write_text(GUIÓN_SALE, encoding="utf-8")
        self._armar_instalacion()
        self._armar_paquete()
        self.lanzados = []
        self.matados = []
        self._procesos = []
        self.addCleanup(self._cosechar_procesos)

    def _cerrar_registro(self):
        import logging
        for manejador in list(instalador.logger.handlers):
            instalador.logger.removeHandler(manejador)
            try:
                manejador.close()
            except Exception:
                pass
        logging.shutdown()

    def _armar_instalacion(self, exe_viejo=EXE_VIEJO):
        inst = self.instalacion
        (inst / exe_viejo).parent.mkdir(parents=True, exist_ok=True)
        (inst / exe_viejo).write_bytes(b"viejo-exe")
        (inst / "_internal" / "viejo.dll").parent.mkdir(parents=True)
        (inst / "_internal" / "viejo.dll").write_bytes(b"viejo-dll")
        (inst / "programa.txt").write_bytes(b"programa viejo")
        datos = inst / "data"
        (datos / "config.ini").parent.mkdir(parents=True, exist_ok=True)
        (datos / "config.ini").write_bytes(b"config del usuario")
        (inst / "Descargas" / "video.mp4").parent.mkdir(parents=True)
        (inst / "Descargas" / "video.mp4").write_bytes(b"video")
        (inst / "sounds" / "existe.wav").parent.mkdir(parents=True)
        (inst / "sounds" / "existe.wav").write_bytes(b"sonido viejo")

    def _armar_paquete(self, exe_nuevo=EXE_NUEVO, hacia=HACIA):
        fuente = self.fuente_paquete
        fuente.mkdir(parents=True, exist_ok=True)
        (fuente / exe_nuevo).write_bytes(b"nuevo-exe")
        (fuente / "_internal" / "nuevo.dll").parent.mkdir(parents=True)
        (fuente / "_internal" / "nuevo.dll").write_bytes(b"nuevo-dll")
        (fuente / "programa.txt").write_bytes(b"programa nuevo")
        (fuente / "sounds" / "existe.wav").parent.mkdir(parents=True)
        (fuente / "sounds" / "existe.wav").write_bytes(b"sonido nuevo")
        (fuente / "sounds" / "agregado.wav").write_bytes(b"sonido agregado")
        (fuente / paths.NOMBRE_MANIFIESTO).write_text(
            json.dumps({"version": hacia, "ejecutable": exe_nuevo}),
            encoding="utf-8")

    def _orden_para(self, guion_nuevo=None):
        arranque = str(paths.arranque_confirmado_en(self.instalacion))

        def traducir(ruta):
            self.lanzados.append(Path(ruta).name)
            if Path(ruta).name == EXE_NUEVO:
                guion = self.guion_ok if guion_nuevo is None else guion_nuevo
                return [sys.executable, str(guion), arranque]
            return [sys.executable, str(self.guion_sale)]

        return traducir

    def _lanzar(self, orden):
        proceso = subprocess.Popen(orden)
        self._procesos.append(proceso)
        return proceso

    def _cosechar_procesos(self):
        for proceso in self._procesos:
            try:
                proceso.wait(timeout=10)
            except Exception:
                try:
                    proceso.kill()
                except Exception:
                    pass
        self._procesos = []

    def _matar(self, proceso):
        self.matados.append(proceso)
        try:
            proceso.terminate()
        except Exception:
            pass
        try:
            proceso.wait(timeout=10)
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass

    def test_exito(self):
        foto_datos = _foto(self.instalacion / "data")
        self.assertEqual(set(foto_datos), {"config.ini"})
        foto_descargas = _foto(self.instalacion / "Descargas")
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        # Archivos del programa nuevos.
        self.assertEqual((self.instalacion / EXE_NUEVO).read_bytes(), b"nuevo-exe")
        self.assertEqual((self.instalacion / "programa.txt").read_bytes(),
                         b"programa nuevo")
        self.assertEqual((self.instalacion / "_internal" / "nuevo.dll").read_bytes(),
                         b"nuevo-dll")
        self.assertFalse((self.instalacion / "_internal" / "viejo.dll").exists())
        # Usuario intacto byte a byte.
        self.assertEqual(_foto_datos_usuario(self.instalacion / "data"),
                         foto_datos)
        self.assertEqual(_foto(self.instalacion / "Descargas"), foto_descargas)
        # Sonidos: el existente no se pisa, el nuevo se agrega.
        self.assertEqual((self.instalacion / "sounds" / "existe.wav").read_bytes(),
                         b"sonido viejo")
        self.assertEqual((self.instalacion / "sounds" / "agregado.wav").read_bytes(),
                         b"sonido agregado")
        # Limpieza y resultado.
        self.assertFalse(paths.respaldo_actualizacion_en(self.instalacion).exists())
        self.assertFalse(paths.actualizacion_pendiente_en(self.instalacion).exists())
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(resultado,
                         {"resultado": "ok", "desde": DESDE, "hacia": HACIA})
        self.assertTrue(paths.registro_actualizacion_en(self.instalacion).is_file())

    def test_exito_escribe_resultado_antes_de_borrar_respaldo(self):
        import shutil as shutil_real
        import unittest.mock as mock
        real_rmtree = shutil_real.rmtree
        respaldo = paths.respaldo_actualizacion_en(self.instalacion)
        visto = {}
        def _espiar(ruta, *args, **kwargs):
            if Path(ruta) == respaldo:
                visto["resultado_existe"] = paths.resultado_actualizacion_en(
                    self.instalacion).is_file()
            return real_rmtree(ruta, *args, **kwargs)
        with mock.patch.object(shutil_real, "rmtree", side_effect=_espiar):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertTrue(ok)
        self.assertIn("resultado_existe", visto)
        self.assertTrue(
            visto["resultado_existe"],
            "resultado.json debe existir cuando empieza el borrado del respaldo")

    def test_fallo_sin_confirmacion_escribe_resultado_antes_de_lanzar_viejo(self):
        vistos = []
        def _lanzar_orden(orden):
            if len(orden) > 1 and Path(orden[1]).name == self.guion_sale.name:
                vistos.append(paths.resultado_actualizacion_en(
                    self.instalacion).is_file())
            return self._lanzar(orden)
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=_lanzar_orden, matar=self._matar,
            orden_para=self._orden_para(guion_nuevo=self.guion_malo),
            tope_arranque=2)
        self.assertFalse(ok)
        self.assertTrue(vistos, "el ejecutable viejo debe lanzarse al volver atrás")
        self.assertTrue(
            all(vistos),
            "resultado.json debe existir cuando se lanza el ejecutable viejo")

    def test_fallo_lanzamiento_escribe_resultado_antes_de_lanzar_viejo(self):
        vistos = []
        def _lanzar_orden(orden):
            if len(orden) > 1 and Path(orden[1]).name == self.guion_sale.name:
                vistos.append(paths.resultado_actualizacion_en(
                    self.instalacion).is_file())
            return self._lanzar(orden)
        def traducir(ruta):
            self.lanzados.append(Path(ruta).name)
            if Path(ruta).name == EXE_NUEVO:
                raise RuntimeError("no abre")
            return [sys.executable, str(self.guion_sale)]
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=_lanzar_orden, matar=self._matar,
            orden_para=traducir)
        self.assertFalse(ok)
        self.assertTrue(vistos, "el ejecutable viejo debe lanzarse al volver atrás")
        self.assertTrue(
            all(vistos),
            "resultado.json debe existir cuando se lanza el ejecutable viejo")

    def test_nuevo_no_confirma_vuelve_atras(self):
        foto_programa = _sin_estado(_foto(self.instalacion))
        # Saca data/actualizacion de la foto: el registro y el resultado
        # viven ahí y sí cambian.
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para(guion_nuevo=self.guion_malo),
            tope_arranque=2)
        self.assertFalse(ok)
        ahora = _sin_estado(_foto(self.instalacion))
        self.assertEqual(ahora, foto_programa)
        self.assertEqual((self.instalacion / EXE_VIEJO).read_bytes(), b"viejo-exe")
        self.assertIn(EXE_VIEJO, self.lanzados)
        self.assertFalse(paths.actualizacion_pendiente_en(self.instalacion).exists())
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(resultado["resultado"], "fallo")
        self.assertTrue(resultado["motivo"])

    def test_archivo_que_no_se_puede_mover(self):
        import os
        real_replace = os.replace
        respaldo = paths.respaldo_actualizacion_en(self.instalacion)
        llamadas = {"n": 0}

        def _falla_una(origen, destino):
            if Path(origen).name == "programa.txt" and llamadas["n"] == 0:
                llamadas["n"] += 1
                raise OSError("archivo en uso")
            return real_replace(origen, destino)

        import unittest.mock as mock
        foto_antes = _foto(self.instalacion)
        with mock.patch.object(os, "replace", side_effect=_falla_una):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertFalse(ok)
        ahora = _foto(self.instalacion)
        # Solo puede diferir data/actualizacion (registro y resultado).
        for clave in set(foto_antes) | set(ahora):
            if _es_estado(clave):
                continue
            self.assertEqual(ahora.get(clave), foto_antes.get(clave),
                             f"cambió {clave}")
        self.assertIn(EXE_VIEJO, self.lanzados)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(resultado["resultado"], "fallo")
        self.assertIn("como OBS", resultado["motivo"])
        self.assertIn("Ciérralo y vuelve a intentarlo", resultado["motivo"])

    def test_archivo_en_uso_nombra_obs_en_el_motivo(self):
        import os
        real_replace = os.replace

        def _falla(origen, destino):
            if Path(origen).name == "programa.txt":
                raise OSError("archivo en uso")
            return real_replace(origen, destino)

        import unittest.mock as mock
        with mock.patch.object(os, "replace", side_effect=_falla):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertFalse(ok)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(resultado["resultado"], "fallo")
        self.assertEqual(
            resultado["motivo"],
            "no se pudo mover un archivo de la versión anterior, quizá sigue "
            "abierto en otro programa, como OBS. Ciérralo y vuelve a "
            "intentarlo")

    def test_pid_no_termina_no_toca_nada(self):
        foto_antes = _sin_estado(_foto(self.instalacion))
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: False,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertFalse(ok)
        ahora = _sin_estado(_foto(self.instalacion))
        self.assertEqual(ahora, foto_antes)
        self.assertEqual(self.lanzados, [])
        self.assertFalse(
            paths.resultado_actualizacion_en(self.instalacion).exists())

    def test_renombre_de_app_el_viejo_desaparece(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        self.assertTrue((self.instalacion / EXE_NUEVO).is_file())
        self.assertFalse((self.instalacion / EXE_VIEJO).exists())


class TestTemasSonido(BaseInstalador):
    """Los temas del paquete reemplazan a los instalados, los propios quedan."""

    def _armar_instalacion(self, exe_viejo=EXE_VIEJO):
        super()._armar_instalacion(exe_viejo=exe_viejo)
        (self.instalacion / "sounds" / "themes" / "default").mkdir(
            parents=True, exist_ok=True)
        (self.instalacion / "sounds" / "themes" / "default" / "a.wav"
         ).write_bytes(b"tema viejo a")
        (self.instalacion / "sounds" / "themes" / "default" / "b.wav"
         ).write_bytes(b"b del usuario")
        (self.instalacion / "sounds" / "themes" / "default" / "Bot.wav"
         ).write_bytes(b"agregado por el usuario")
        (self.instalacion / "sounds" / "themes" / "mio").mkdir(
            parents=True, exist_ok=True)
        (self.instalacion / "sounds" / "themes" / "mio" / "x.wav"
         ).write_bytes(b"tema mio x")
        # Manifiesto viejo: a.wav sigue igual al distribuido, b.wav lo
        # cambió el usuario y Bot.wav no figura porque lo agregó él.
        manifiesto = {
            "themes/default/a.wav":
                hashlib.sha256(b"tema viejo a").hexdigest(),
            "themes/default/b.wav":
                hashlib.sha256(b"tema original b").hexdigest(),
        }
        (self.instalacion / paths.NOMBRE_MANIFIESTO_SONIDOS).write_text(
            json.dumps(manifiesto), encoding="utf-8")

    def _armar_paquete(self, exe_nuevo=EXE_NUEVO, hacia=HACIA):
        super()._armar_paquete(exe_nuevo=exe_nuevo, hacia=hacia)
        (self.fuente_paquete / "sounds" / "themes" / "default").mkdir(
            parents=True, exist_ok=True)
        (self.fuente_paquete / "sounds" / "themes" / "default" / "a.wav"
         ).write_bytes(b"tema nuevo a")
        (self.fuente_paquete / "sounds" / "themes" / "default" / "b.wav"
         ).write_bytes(b"tema nuevo b")
        (self.fuente_paquete / "sounds" / "themes" / "default" / "nuevo.wav"
         ).write_bytes(b"tema nuevo")
        manifiesto = {
            "themes/default/a.wav":
                hashlib.sha256(b"tema nuevo a").hexdigest(),
            "themes/default/b.wav":
                hashlib.sha256(b"tema nuevo b").hexdigest(),
            "themes/default/nuevo.wav":
                hashlib.sha256(b"tema nuevo").hexdigest(),
        }
        (self.fuente_paquete / paths.NOMBRE_MANIFIESTO_SONIDOS).write_text(
            json.dumps(manifiesto), encoding="utf-8")

    def test_exito_reemplaza_tema_y_conserva_el_propio(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "a.wav"
             ).read_bytes(), b"tema nuevo a")
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "nuevo.wav"
             ).read_bytes(), b"tema nuevo")
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "mio" / "x.wav"
             ).read_bytes(), b"tema mio x")

    def test_sonido_cambiado_por_el_usuario_sobrevive_byte_a_byte(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "b.wav"
             ).read_bytes(), b"b del usuario")

    def test_sonido_agregado_por_el_usuario_sobrevive(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "Bot.wav"
             ).read_bytes(), b"agregado por el usuario")

    def test_manifiesto_nuevo_queda_instalado(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        instalado = json.loads(
            (self.instalacion / paths.NOMBRE_MANIFIESTO_SONIDOS).read_text(
                encoding="utf-8"))
        esperado = json.loads(
            (self.fuente_paquete / paths.NOMBRE_MANIFIESTO_SONIDOS
             ).read_text(encoding="utf-8"))
        self.assertEqual(instalado, esperado)

    def test_registro_anota_los_sonidos_conservados(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        registro = paths.registro_actualizacion_en(
            self.instalacion).read_text(encoding="utf-8")
        self.assertIn("themes/default/b.wav", registro)
        self.assertIn("themes/default/Bot.wav", registro)
        self.assertNotIn("themes/default/a.wav", registro)

    def test_vuelta_atras_deja_la_mezcla_como_estaba_byte_a_byte(self):
        foto_antes = _sin_estado(_foto(self.instalacion))
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para(guion_nuevo=self.guion_malo),
            tope_arranque=2)
        self.assertFalse(ok)
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_antes)
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "b.wav"
             ).read_bytes(), b"b del usuario")
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "Bot.wav"
             ).read_bytes(), b"agregado por el usuario")

    def test_sin_confirmacion_devuelve_temas(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para(guion_nuevo=self.guion_malo),
            tope_arranque=2)
        self.assertFalse(ok)
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "a.wav"
             ).read_bytes(), b"tema viejo a")
        self.assertFalse(
            (self.instalacion / "sounds" / "themes" / "default" / "nuevo.wav"
             ).exists())
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "mio" / "x.wav"
             ).read_bytes(), b"tema mio x")

    def test_fallo_al_arrancar_lo_nuevo_vuelve_atras(self):
        foto_programa = _sin_estado(_foto(self.instalacion))

        def traducir(ruta):
            self.lanzados.append(Path(ruta).name)
            if Path(ruta).name == EXE_NUEVO:
                raise RuntimeError("no abre")
            return [sys.executable, str(self.guion_sale)]

        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=traducir)
        self.assertFalse(ok)
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_programa)
        respaldo = paths.respaldo_actualizacion_en(self.instalacion)
        self.assertTrue(not respaldo.exists()
                        or not any(respaldo.rglob("*")))
        self.assertIn(EXE_VIEJO, self.lanzados)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(resultado["resultado"], "fallo")
        self.assertTrue(resultado["motivo"])


class TestTemasSinManifiestoViejo(BaseInstalador):
    """Sin manifiesto no hay forma de distinguir: ante la duda se conserva."""

    def _armar_instalacion(self, exe_viejo=EXE_VIEJO):
        super()._armar_instalacion(exe_viejo=exe_viejo)
        (self.instalacion / "sounds" / "themes" / "default").mkdir(
            parents=True, exist_ok=True)
        (self.instalacion / "sounds" / "themes" / "default" / "a.wav"
         ).write_bytes(b"tema viejo a")
        (self.instalacion / "sounds" / "themes" / "default" / "igual.wav"
         ).write_bytes(b"tema igual")
        (self.instalacion / "sounds" / "themes" / "default" / "Bot.wav"
         ).write_bytes(b"agregado por el usuario")

    def _armar_paquete(self, exe_nuevo=EXE_NUEVO, hacia=HACIA):
        super()._armar_paquete(exe_nuevo=exe_nuevo, hacia=hacia)
        (self.fuente_paquete / "sounds" / "themes" / "default").mkdir(
            parents=True, exist_ok=True)
        (self.fuente_paquete / "sounds" / "themes" / "default" / "a.wav"
         ).write_bytes(b"tema nuevo a")
        (self.fuente_paquete / "sounds" / "themes" / "default" / "igual.wav"
         ).write_bytes(b"tema igual")
        (self.fuente_paquete / "sounds" / "themes" / "default" / "nuevo.wav"
         ).write_bytes(b"tema nuevo")

    def test_distinto_sobrevive_identico_queda_nuevo_y_agregado_sobrevive(self):
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertTrue(ok)
        tema = self.instalacion / "sounds" / "themes" / "default"
        self.assertEqual((tema / "a.wav").read_bytes(), b"tema viejo a")
        self.assertEqual((tema / "igual.wav").read_bytes(), b"tema igual")
        self.assertEqual((tema / "Bot.wav").read_bytes(),
                         b"agregado por el usuario")
        self.assertEqual((tema / "nuevo.wav").read_bytes(), b"tema nuevo")
        registro = paths.registro_actualizacion_en(
            self.instalacion).read_text(encoding="utf-8")
        self.assertIn("sin manifiesto viejo", registro)


class TestCaracterizacionFallos(BaseInstalador):
    """Caminos de fallo de `instalar` sin cubrir al 16/10/2026.

    Cada prueba fija el comportamiento de hoy: valor devuelto,
    `resultado.json` exacto, instalación intacta byte a byte y si el
    ejecutable viejo se relanza o no.
    """

    def test_paquete_invalido_no_toca_nada(self):
        (self.fuente_paquete / paths.NOMBRE_MANIFIESTO).write_text(
            json.dumps({"version": HACIA, "ejecutable": "malo.txt"}),
            encoding="utf-8")
        foto_antes = _sin_estado(_foto(self.instalacion))
        ok = instalador.instalar(
            self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO, DESDE,
            esperar_pid=lambda pid, tope: True,
            lanzar=self._lanzar, matar=self._matar,
            orden_para=self._orden_para())
        self.assertFalse(ok)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(
            resultado,
            {"resultado": "fallo",
             "motivo": "el paquete no es válido: "
                       "el ejecutable del paquete no es válido"})
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_antes)
        self.assertEqual(self.lanzados, [])

    def test_respaldo_previo_que_no_se_puede_vaciar(self):
        import shutil as shutil_real
        import unittest.mock as mock
        respaldo = paths.respaldo_actualizacion_en(self.instalacion)
        respaldo.mkdir(parents=True, exist_ok=True)
        (respaldo / "viejo.txt").write_bytes(b"viejo")
        real_rmtree = shutil_real.rmtree

        def _falla(ruta, *args, **kwargs):
            if Path(ruta) == respaldo:
                raise OSError("bloqueado")
            return real_rmtree(ruta, *args, **kwargs)

        foto_antes = _sin_estado(_foto(self.instalacion))
        with mock.patch.object(instalador.shutil, "rmtree",
                               side_effect=_falla):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO,
                DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertFalse(ok)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(
            resultado,
            {"resultado": "fallo",
             "motivo": "no se pudo vaciar el respaldo: bloqueado"})
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_antes)
        self.assertEqual(self.lanzados, [])

    def test_vuelta_atras_devuelve_temas_y_entradas_ya_movidas(self):
        import os
        import unittest.mock as mock
        for base in (self.instalacion, self.fuente_paquete):
            for tema in ("default", "otro"):
                carpeta = base / "sounds" / "themes" / tema
                carpeta.mkdir(parents=True, exist_ok=True)
                (carpeta / "a.wav").write_bytes(
                    b"tema viejo " + tema.encode()
                    if base == self.instalacion
                    else b"tema nuevo " + tema.encode())
        foto_antes = _sin_estado(_foto(self.instalacion))
        real_replace = os.replace

        def _falla_segundo_tema(origen, destino):
            if Path(origen).name == "otro":
                raise OSError("archivo en uso")
            return real_replace(origen, destino)

        with mock.patch.object(os, "replace",
                               side_effect=_falla_segundo_tema):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO,
                DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertFalse(ok)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(
            resultado,
            {"resultado": "fallo",
             "motivo": "no se pudo mover un archivo de la versión anterior, "
                       "quizá sigue abierto en otro programa, como OBS. "
                       "Ciérralo y vuelve a intentarlo"})
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_antes)
        self.assertIn(EXE_VIEJO, self.lanzados)
        self.assertEqual((self.instalacion / "programa.txt").read_bytes(),
                         b"programa viejo")
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "default" / "a.wav"
             ).read_bytes(), b"tema viejo default")
        self.assertEqual(
            (self.instalacion / "sounds" / "themes" / "otro" / "a.wav"
             ).read_bytes(), b"tema viejo otro")

    def test_fallo_al_copiar_vuelve_atras(self):
        import unittest.mock as mock
        foto_antes = _sin_estado(_foto(self.instalacion))
        with mock.patch.object(instalador, "_copiar_entrada",
                               side_effect=OSError("disco lleno")):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO,
                DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertFalse(ok)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(
            resultado,
            {"resultado": "fallo",
             "motivo": "no se pudo copiar la versión nueva"})
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_antes)
        self.assertIn(EXE_VIEJO, self.lanzados)
        self.assertFalse(
            paths.actualizacion_pendiente_en(self.instalacion).exists())

    def test_fallo_al_marcar_pendiente_vuelve_atras(self):
        import unittest.mock as mock
        foto_antes = _sin_estado(_foto(self.instalacion))
        pendiente = paths.actualizacion_pendiente_en(self.instalacion)
        real_write = Path.write_text

        def _falla_escritura(uno_mismo, *args, **kwargs):
            if uno_mismo == pendiente:
                raise OSError("disco lleno")
            return real_write(uno_mismo, *args, **kwargs)

        with mock.patch.object(Path, "write_text", _falla_escritura):
            ok = instalador.instalar(
                self.fuente_paquete, self.instalacion, 1234, EXE_VIEJO,
                DESDE,
                esperar_pid=lambda pid, tope: True,
                lanzar=self._lanzar, matar=self._matar,
                orden_para=self._orden_para())
        self.assertFalse(ok)
        resultado = json.loads(
            paths.resultado_actualizacion_en(self.instalacion).read_text(
                encoding="utf-8"))
        self.assertEqual(
            resultado,
            {"resultado": "fallo",
             "motivo": "no se pudo marcar la actualización pendiente: "
                       "disco lleno"})
        self.assertEqual(_sin_estado(_foto(self.instalacion)), foto_antes)
        self.assertIn(EXE_VIEJO, self.lanzados)
        self.assertFalse(pendiente.exists())


class TestTerminoWindows(unittest.TestCase):
    """En Windows, sin ctypes no se toca os.kill: la señal 0 manda
    CTRL_C_EVENT a la consola en vez de comprobar nada."""

    def test_sin_ctypes_devuelve_falso_sin_llamar_a_os_kill(self):
        import ctypes
        import unittest.mock as mock
        with mock.patch.object(instalador.os, "name", "nt"), \
                mock.patch.object(ctypes, "WinDLL",
                                  side_effect=OSError("sin kernel")), \
                mock.patch.object(instalador.os, "kill",
                                  side_effect=AssertionError(
                                      "no debe llamarse")) as matar:
            self.assertFalse(instalador._termino(1234))
        matar.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "solo Windows")
    def test_vivo_da_falso(self):
        proceso = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self.assertFalse(instalador._termino(proceso.pid))
        finally:
            try:
                proceso.terminate()
            except Exception:
                pass
            try:
                proceso.wait(timeout=10)
            except Exception:
                try:
                    proceso.kill()
                except Exception:
                    pass

    @unittest.skipUnless(os.name == "nt", "solo Windows")
    def test_terminado_con_handle_abierto_da_verdadero(self):
        proceso = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            creationflags=subprocess.CREATE_NO_WINDOW)
        proceso.wait(timeout=10)
        try:
            self.assertTrue(instalador._termino(proceso.pid))
        finally:
            try:
                proceso.wait(timeout=10)
            except Exception:
                pass

    def test_proceso_inexistente_da_verdadero(self):
        import ctypes
        import unittest.mock as mock
        for sin_handle in (0, None):
            nucleo = mock.Mock()
            nucleo.OpenProcess.return_value = sin_handle
            nucleo.WaitForSingleObject.side_effect = AssertionError(
                "sin handle no se espera")
            with mock.patch.object(instalador.os, "name", "nt"), \
                    mock.patch.object(ctypes, "WinDLL",
                                      return_value=nucleo):
                self.assertTrue(instalador._termino(1234))
            nucleo.WaitForSingleObject.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "solo Windows")
    def test_esperar_pid_terminado_responde_enseguida(self):
        proceso = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            creationflags=subprocess.CREATE_NO_WINDOW)
        proceso.wait(timeout=10)
        try:
            inicio = time.monotonic()
            self.assertTrue(instalador.esperar_pid(proceso.pid, 5))
            self.assertLess(time.monotonic() - inicio, 1)
        finally:
            try:
                proceso.wait(timeout=10)
            except Exception:
                pass


class TestPrincipalInstalador(unittest.TestCase):

    def test_argumentos_cortos_devuelve_uno(self):
        self.assertEqual(instalador.principal_instalador([]), 1)
        self.assertEqual(instalador.principal_instalador(
            ["--instalar-actualizacion", "solo"]), 1)

    def test_pid_no_numerico_devuelve_uno(self):
        self.assertEqual(instalador.principal_instalador(
            ["--instalar-actualizacion", "inst", "no-numero", "V.exe", "1.0"]), 1)


if __name__ == "__main__":
    unittest.main()

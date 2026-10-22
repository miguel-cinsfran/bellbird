"""Pruebas de la migración del mapa de atajos por familias.

La decisión (`migrar_atajos`) es pura. La carga real se prueba con un
`config.ini` temporal para comprobar que el archivo queda migrado y con la
versión al día, y que una segunda carga no vuelve a tocar lo cambiado.
"""

import tempfile
import unittest
from pathlib import Path

from tests.rutas_temporales import redirigir_rutas
from ytchat.core import atajos
from ytchat.core import config


VIEJOS = {accion: viejo for accion, (viejo, _nuevo) in atajos._MIGRACION_ATAJOS.items()}
NUEVOS = {accion: nuevo for accion, (_viejo, nuevo) in atajos._MIGRACION_ATAJOS.items()}


def _editables():
    return {accion: valor
            for accion, valor in atajos.todos_los_atajos_default().items()
            if accion not in atajos.ATAJOS_FIJOS}


class TestMigrarAtajos(unittest.TestCase):

    def test_los_nueve_viejos_migran(self):
        self.assertEqual(atajos.migrar_atajos(VIEJOS), NUEVOS)

    def test_valor_cambiado_a_mano_no_se_toca(self):
        valores = dict(VIEJOS)
        valores["conectar"] = "alt+z"
        resultado = atajos.migrar_atajos(valores)
        self.assertNotIn("conectar", resultado)
        self.assertEqual(set(resultado), set(NUEVOS) - {"conectar"})

    def test_valor_vacio_no_se_toca(self):
        valores = dict(VIEJOS)
        valores["ir_lista"] = ""
        resultado = atajos.migrar_atajos(valores)
        self.assertNotIn("ir_lista", resultado)
        self.assertEqual(len(resultado), len(NUEVOS) - 1)

    def test_choque_deja_conectar_y_migra_las_demas(self):
        valores = dict(VIEJOS)
        valores["rep_detener"] = "alt+shift+c"
        resultado = atajos.migrar_atajos(valores)
        self.assertNotIn("conectar", resultado)
        self.assertEqual(set(resultado), set(NUEVOS) - {"conectar"})

    def test_cadena_obs_micro_y_musica_ventana(self):
        resultado = atajos.migrar_atajos(VIEJOS)
        self.assertEqual(resultado["obs_micro"], "alt+shift+m")
        self.assertEqual(resultado["musica_ventana"], "ctrl+shift+m")

    def test_propiedad_sin_choques(self):
        acciones = list(atajos._MIGRACION_ATAJOS)
        base = _editables()
        for mascara in range(1 << len(acciones)):
            valores = dict(base)
            for indice, accion in enumerate(acciones):
                if mascara & (1 << indice):
                    valores[accion] = VIEJOS[accion]
            entrada = {a: config._normalizar_atajo(v) for a, v in valores.items()}
            if len(set(entrada.values())) != len(entrada):
                continue  # la propiedad solo habla de entradas sin choques
            aplicado = dict(valores)
            aplicado.update(atajos.migrar_atajos(valores))
            salida = {a: config._normalizar_atajo(v) for a, v in aplicado.items()}
            self.assertEqual(
                len(set(salida.values())), len(salida),
                f"choque tras migrar la combinación {mascara}: {salida}")


class TestCargaReal(unittest.TestCase):

    def test_ini_viejo_migra_en_disco_y_graba_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            lineas = ["[atajos]\n"]
            lineas.extend(f"{accion} = {valor}\n" for accion, valor in VIEJOS.items())
            (carpeta / "config.ini").write_text("".join(lineas), encoding="utf-8")
            with redirigir_rutas(carpeta):
                config.cargar_configuracion()
            p = config._mk_parser()
            p.read(carpeta / "config.ini", encoding="utf-8")
            for accion, nuevo in NUEVOS.items():
                with self.subTest(accion=accion):
                    self.assertEqual(p.get("atajos", accion).strip(), nuevo)
            self.assertEqual(p.getint("sesion", "version_atajos"), 2)

    def test_version_dos_no_vuelve_a_migrar(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / "config.ini").write_text(
                "[atajos]\nconectar = alt+c\n"
                "[sesion]\nversion_atajos = 2\n",
                encoding="utf-8")
            with redirigir_rutas(carpeta):
                config.cargar_configuracion()
            p = config._mk_parser()
            p.read(carpeta / "config.ini", encoding="utf-8")
            self.assertEqual(p.get("atajos", "conectar").strip(), "alt+c")
            self.assertEqual(p.getint("sesion", "version_atajos"), 2)

    def test_version_uno_con_ctrl_shift_i_migra_y_no_choca(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / "config.ini").write_text(
                "[atajos]\nmarcar_incidencia = ctrl+shift+i\n"
                "[sesion]\nversion_atajos = 1\n",
                encoding="utf-8")
            with redirigir_rutas(carpeta):
                config.cargar_configuracion()
            p = config._mk_parser()
            p.read(carpeta / "config.ini", encoding="utf-8")
            self.assertEqual(
                p.get("atajos", "marcar_incidencia").strip(), "alt+shift+i")
            self.assertEqual(
                p.get("atajos", "preguntar_ia").strip(), "ctrl+shift+i")
            crudo = {clave: valor for clave, valor in p.items("atajos")}
            self.assertEqual(config.detectar_conflictos_atajos(crudo), [])

    def test_ini_sin_consulta_rapida_recibe_la_de_fabrica(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / "config.ini").write_text(
                "[atajos]\npausa = f5\n"
                "[sesion]\nversion_atajos = 2\n",
                encoding="utf-8")
            with redirigir_rutas(carpeta):
                config.cargar_configuracion()
            p = config._mk_parser()
            p.read(carpeta / "config.ini", encoding="utf-8")
            self.assertEqual(
                p.get("atajos", "consulta_rapida_ia").strip(),
                "ctrl+shift+f2")


class TestGramatica(unittest.TestCase):

    def test_alt_shift_vale_en_su_area_y_no_en_alt(self):
        self.assertEqual(atajos.ATAJOS_AREA["conectar"], "alt+shift")
        self.assertTrue(atajos.atajo_valido_para_area("conectar", "alt+shift+c"))
        self.assertFalse(atajos.atajo_valido_para_area("enviar_chat", "alt+shift+c"))

    def test_shift_alt_se_normaliza(self):
        self.assertEqual(config._normalizar_atajo("shift+alt+c"), "alt+shift+c")


if __name__ == "__main__":
    unittest.main()

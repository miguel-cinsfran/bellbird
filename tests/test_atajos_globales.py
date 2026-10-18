"""Pruebas de los atajos globales de música, puras y con dobles.

Nada crea ventanas ni registra un atajo de verdad: la ventana es un doble
que anota las llamadas y falla a pedido. `wx.CallAfter` se reemplaza por
una llamada directa.
"""

import unittest
from unittest import mock

import wx

from ytchat.music import anuncios
from ytchat.ui import atajos_globales
from ytchat.ui.atajos_globales import AtajosGlobales, combinacion_windows


class _VentanaFalsa:
    """Doble de ventana que anota `RegisterHotKey` y falla a pedido."""

    def __init__(self):
        self.llamadas = []
        self.registrados = {}
        self.manejadores = {}
        self.fallan_vk = set()

    def RegisterHotKey(self, ident, mods, vk):
        self.llamadas.append(("registrar", ident, mods, vk))
        if vk in self.fallan_vk:
            return False
        self.registrados[ident] = (mods, vk)
        return True

    def UnregisterHotKey(self, ident):
        self.llamadas.append(("soltar", ident))
        self.registrados.pop(ident, None)
        return True

    def Bind(self, evento, manejador, id=-1):
        self.llamadas.append(("enlazar", id))
        self.manejadores[id] = manejador

    def Unbind(self, evento, id=-1):
        self.llamadas.append(("desenlazar", id))
        self.manejadores.pop(id, None)


MODS = wx.MOD_CONTROL | wx.MOD_ALT


class TestCombinacionWindows(unittest.TestCase):

    def test_flechas_y_espacio_dan_su_vk(self):
        self.assertEqual(combinacion_windows("ctrl+alt+left"), (MODS, 0x25))
        self.assertEqual(combinacion_windows("ctrl+alt+up"), (MODS, 0x26))
        self.assertEqual(combinacion_windows("ctrl+alt+right"), (MODS, 0x27))
        self.assertEqual(combinacion_windows("ctrl+alt+down"), (MODS, 0x28))
        self.assertEqual(combinacion_windows("ctrl+alt+space"), (MODS, 0x20))

    def test_letras_y_digitos_dan_su_ord_en_mayuscula(self):
        self.assertEqual(combinacion_windows("ctrl+alt+t"), (MODS, ord("T")))
        self.assertEqual(combinacion_windows("ctrl+alt+m"), (MODS, ord("M")))
        self.assertEqual(combinacion_windows("ctrl+alt+l"), (MODS, ord("L")))
        self.assertEqual(combinacion_windows("ctrl+alt+5"), (MODS, ord("5")))
        self.assertEqual(combinacion_windows("ctrl+alt+0"), (MODS, ord("0")))

    def test_acepta_mayusculas_espacios_y_orden_alt_ctrl(self):
        self.assertEqual(combinacion_windows("CTRL+ALT+Left"), (MODS, 0x25))
        self.assertEqual(combinacion_windows("  ctrl+alt+t  "), (MODS, ord("T")))
        self.assertEqual(combinacion_windows("alt+ctrl+left"), (MODS, 0x25))

    def test_lo_que_no_es_ctrl_alt_da_none(self):
        for texto in ("ctrl+p", "alt+c", "f5", "ctrl+f2", "ctrl+shift+p",
                      "alt+enter", "ctrl+alt+f5", "ctrl+alt+enter",
                      "ctrl+alt+home", "ctrl+alt", "ctrl+alt+t+r",
                      "", "   ", None, "basura"):
            with self.subTest(texto=texto):
                self.assertIsNone(combinacion_windows(texto))

    def test_los_modificadores_son_wx_mod(self):
        mods, _vk = combinacion_windows("ctrl+alt+t")
        self.assertEqual(mods, wx.MOD_CONTROL | wx.MOD_ALT)


class TestAtajosGlobales(unittest.TestCase):

    def _acciones(self):
        llamadas = []
        acciones = {accion: (lambda a=accion: llamadas.append(a))
                    for accion in atajos_globales.ACCIONES}
        return acciones, llamadas

    def _atajos(self, **cambios):
        base = {
            "musica_play": "ctrl+alt+space",
            "musica_siguiente": "ctrl+alt+right",
            "musica_anterior": "ctrl+alt+left",
            "musica_vol_mas": "ctrl+alt+up",
            "musica_vol_menos": "ctrl+alt+down",
            "musica_que_suena": "ctrl+alt+t",
            "musica_ventana": "ctrl+alt+m",
            "musica_listas": "ctrl+alt+l",
        }
        base.update(cambios)
        return base

    def test_registra_los_traducibles_con_ids_distintos(self):
        ventana = _VentanaFalsa()
        acciones, _llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        self.assertEqual(globales.activar(self._atajos()), [])
        self.assertEqual(len(ventana.registrados), 8)
        ids = [llamada[1] for llamada in ventana.llamadas
               if llamada[0] == "registrar"]
        self.assertEqual(len(set(ids)), 8)
        self.assertTrue(all(0xB000 <= i < 0xB000 + 100 for i in ids))
        self.assertTrue(globales.activos)

    def test_devuelve_los_fallidos_en_legible(self):
        ventana = _VentanaFalsa()
        ventana.fallan_vk = {0x27, ord("T")}
        acciones, _llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        fallidos = globales.activar(self._atajos())
        self.assertEqual(fallidos,
                         ["Ctrl+Alt+Flecha derecha", "Ctrl+Alt+T"])
        self.assertEqual(len(ventana.registrados), 6)
        self.assertTrue(globales.activos)

    def test_lo_no_traducible_no_se_registra_ni_falla(self):
        ventana = _VentanaFalsa()
        acciones, _llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        atajos = self._atajos(musica_play="ctrl+p", musica_listas="")
        self.assertEqual(globales.activar(atajos), [])
        self.assertEqual(len(ventana.registrados), 6)

    def test_desactivar_suelta_todos_y_dos_veces_no_falla(self):
        ventana = _VentanaFalsa()
        acciones, _llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        globales.activar(self._atajos())
        globales.desactivar()
        self.assertEqual(ventana.registrados, {})
        self.assertFalse(globales.activos)
        sueltas = [llamada for llamada in ventana.llamadas
                   if llamada[0] == "soltar"]
        self.assertEqual(len(sueltas), 8)
        globales.desactivar()  # no falla ni registra nada más
        self.assertEqual([llamada for llamada in ventana.llamadas
                          if llamada[0] == "soltar"], sueltas)

    def test_activar_dos_veces_no_duplica(self):
        ventana = _VentanaFalsa()
        acciones, _llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        globales.activar(self._atajos())
        globales.activar(self._atajos())
        self.assertEqual(len(ventana.registrados), 8)
        registros = [llamada for llamada in ventana.llamadas
                     if llamada[0] == "registrar"]
        self.assertEqual(len(registros), 16)
        sueltas = [llamada for llamada in ventana.llamadas
                   if llamada[0] == "soltar"]
        self.assertEqual(len(sueltas), 8)

    def test_el_evento_llama_la_accion_con_callafter(self):
        ventana = _VentanaFalsa()
        acciones, llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        globales.activar(self._atajos())
        ident = next(iter(ventana.manejadores))
        with mock.patch.object(atajos_globales.wx, "CallAfter",
                               side_effect=lambda fn, *a: fn(*a)):
            ventana.manejadores[ident](mock.Mock())
        self.assertEqual(len(llamadas), 1)

    def test_sin_atajos_no_registra_nada(self):
        ventana = _VentanaFalsa()
        acciones, _llamadas = self._acciones()
        globales = AtajosGlobales(ventana, acciones)
        self.assertEqual(globales.activar({}), [])
        self.assertFalse(globales.activos)


class TestFrasesGlobales(unittest.TestCase):
    """Las tres frases viven como constantes en `anuncios`."""

    def test_textos(self):
        self.assertEqual(
            anuncios.TEXTO_ATAJOS_GLOBALES_ACTIVOS,
            "Atajos de música activos en cualquier programa")
        self.assertEqual(
            anuncios.TEXTO_ATAJOS_GLOBALES_SOLO,
            "Atajos de música solo en YTChat")

    def test_fallo_lista_las_combinaciones_y_suena_error(self):
        aviso = anuncios.aviso_atajos_globales_fallo(
            ["Ctrl+Alt+T", "Ctrl+Alt+M"])
        self.assertEqual(
            aviso.texto,
            "No se pudieron usar en cualquier programa: "
            "Ctrl+Alt+T, Ctrl+Alt+M. Las usa otro programa")
        self.assertEqual(aviso.sonido, "error")

    def test_activos_y_solo_no_llevan_sonido(self):
        self.assertIsNone(anuncios.aviso_atajos_globales_activos().sonido)
        self.assertIsNone(anuncios.aviso_atajos_globales_solo().sonido)


if __name__ == "__main__":
    unittest.main()

"""Filtros del micrófono de OBS: lectura, plan y resumen, sin wx."""

import unittest

from bellbird.obs import filtros_microfono
from bellbird.obs.obs_cliente import ObsError


def filtro(nombre, tipo, activo=True, ajustes=None):
    return {"filterName": nombre, "filterKind": tipo,
            "filterEnabled": activo, "filterSettings": ajustes or {}}


class ClienteDoble:

    def __init__(self, filtros=None, error=False):
        self.filtros = list(filtros or ())
        self.error = error
        self.peticiones = []
        self.cerrado = False

    def conectar(self):
        pass

    def pedir(self, tipo, datos=None, parada=None):
        self.peticiones.append((tipo, datos))
        if self.error:
            raise ObsError("fallo")
        if tipo == "GetSourceFilterList":
            return {"responseData": {"filters": list(self.filtros)}}
        return {"responseData": {}}

    def cerrar(self):
        self.cerrado = True


class TestEstadoDe(unittest.TestCase):

    def test_lee_lo_activo_de_cada_tipo(self):
        filtros = [
            filtro("Eliminación de ruido", "noise_suppress_filter_v2"),
            filtro("Puerta anti-ruidos", "noise_gate_filter", False),
            filtro("Ganancia", "gain_filter", True, {"db": 6}),
        ]
        self.assertEqual(
            filtros_microfono.estado_de(filtros),
            filtros_microfono.Estado(True, False, 6))

    def test_sin_filtros_no_hay_nada_activo(self):
        self.assertEqual(
            filtros_microfono.estado_de([]),
            filtros_microfono.Estado(False, False, 0))

    def test_una_ganancia_inactiva_no_cuenta(self):
        filtros = [filtro("Ganancia", "gain_filter", False, {"db": 10})]
        self.assertEqual(
            filtros_microfono.estado_de(filtros),
            filtros_microfono.Estado(False, False, 0))

    def test_la_ganancia_se_redondea_al_valor_mas_cercano(self):
        filtros = [filtro("Ganancia", "gain_filter", True, {"db": 5.5})]
        self.assertEqual(
            filtros_microfono.estado_de(filtros).ganancia_db, 6)
        filtros = [filtro("Ganancia", "gain_filter", True, {"db": 17})]
        self.assertEqual(
            filtros_microfono.estado_de(filtros).ganancia_db, 15)


class TestPlan(unittest.TestCase):

    def _tipos(self, peticiones):
        return [tipo for tipo, _datos in peticiones]

    def test_crea_lo_que_falta_con_los_ajustes_de_obs(self):
        peticiones = filtros_microfono.plan(
            [], filtros_microfono.Estado(True, True, 6))
        self.assertEqual(self._tipos(peticiones), [
            "CreateSourceFilter", "CreateSourceFilter",
            "CreateSourceFilter"])
        ruido, puerta, ganancia = [datos for _tipo, datos in peticiones]
        self.assertEqual(ruido["filterName"], "Eliminación de ruido")
        self.assertEqual(ruido["filterKind"], "noise_suppress_filter_v2")
        self.assertEqual(ruido["filterSettings"], {"method": "rnnoise"})
        self.assertEqual(puerta["filterName"], "Puerta anti-ruidos")
        self.assertEqual(puerta["filterKind"], "noise_gate_filter")
        self.assertEqual(puerta["filterSettings"], {})
        self.assertEqual(ganancia["filterName"], "Ganancia")
        self.assertEqual(ganancia["filterKind"], "gain_filter")
        self.assertEqual(ganancia["filterSettings"], {"db": 6})

    def test_activa_y_desactiva_lo_que_hay_sin_crear_otro(self):
        filtros = [
            filtro("Eliminación de ruido", "noise_suppress_filter_v2"),
            filtro("Puerta anti-ruidos", "noise_gate_filter"),
            filtro("Ganancia", "gain_filter", True, {"db": 6}),
        ]
        peticiones = filtros_microfono.plan(
            filtros, filtros_microfono.Estado(False, True, 0))
        self.assertEqual(self._tipos(peticiones), [
            "SetSourceFilterEnabled", "SetSourceFilterEnabled"])
        self.assertEqual(peticiones[0][1], {
            "filterName": "Eliminación de ruido", "filterEnabled": False})
        self.assertEqual(peticiones[1][1], {
            "filterName": "Ganancia", "filterEnabled": False})
        self.assertNotIn("CreateSourceFilter", self._tipos(peticiones))

    def test_reutiliza_el_primer_filtro_del_tipo(self):
        filtros = [
            filtro("Ruido propio", "noise_suppress_filter_v2", False),
            filtro("Otro ruido", "noise_suppress_filter_v2", False),
        ]
        peticiones = filtros_microfono.plan(
            filtros, filtros_microfono.Estado(True, False, 0))
        self.assertEqual(self._tipos(peticiones),
                         ["SetSourceFilterEnabled"])
        self.assertEqual(peticiones[0][1]["filterName"], "Ruido propio")
        self.assertTrue(peticiones[0][1]["filterEnabled"])

    def test_cambia_el_db_de_una_ganancia_existente(self):
        filtros = [filtro("Ganancia", "gain_filter", True, {"db": 3})]
        peticiones = filtros_microfono.plan(
            filtros, filtros_microfono.Estado(False, False, 10))
        self.assertEqual(self._tipos(peticiones),
                         ["SetSourceFilterSettings"])
        self.assertEqual(peticiones[0][1], {
            "filterName": "Ganancia", "filterSettings": {"db": 10}})

    def test_no_pide_nada_si_ya_esta_como_se_eligio(self):
        filtros = [
            filtro("Eliminación de ruido", "noise_suppress_filter_v2"),
            filtro("Puerta anti-ruidos", "noise_gate_filter"),
            filtro("Ganancia", "gain_filter", True, {"db": 6}),
        ]
        self.assertEqual(
            filtros_microfono.plan(
                filtros, filtros_microfono.Estado(True, True, 6)),
            [])
        apagados = [
            filtro("Eliminación de ruido", "noise_suppress_filter_v2", False),
            filtro("Puerta anti-ruidos", "noise_gate_filter", False),
            filtro("Ganancia", "gain_filter", False, {"db": 6}),
        ]
        self.assertEqual(
            filtros_microfono.plan(
                apagados, filtros_microfono.Estado(False, False, 0)),
            [])

    def test_nunca_borra_filtros(self):
        filtros = [
            filtro("Eliminación de ruido", "noise_suppress_filter_v2"),
            filtro("Puerta anti-ruidos", "noise_gate_filter"),
            filtro("Ganancia", "gain_filter", True, {"db": 3}),
        ]
        for elegido in (
                filtros_microfono.Estado(False, False, 0),
                filtros_microfono.Estado(True, True, 20)):
            tipos = self._tipos(filtros_microfono.plan(filtros, elegido))
            self.assertNotIn("RemoveSourceFilter", tipos)

    def test_elige_un_nombre_libre_si_el_de_obs_esta_tomado(self):
        filtros = [filtro("Eliminación de ruido", "gain_filter")]
        peticiones = filtros_microfono.plan(
            filtros, filtros_microfono.Estado(True, False, 0))
        self.assertEqual(peticiones[0][1]["filterName"],
                         "Eliminación de ruido 2")
        filtros.append(filtro("Eliminación de ruido 2", "gain_filter"))
        peticiones = filtros_microfono.plan(
            filtros, filtros_microfono.Estado(True, False, 0))
        self.assertEqual(peticiones[0][1]["filterName"],
                         "Eliminación de ruido 3")


class TestResumen(unittest.TestCase):

    def test_con_todo_activo(self):
        self.assertEqual(
            filtros_microfono.resumen(
                filtros_microfono.Estado(True, True, 6)),
            "Filtros del micrófono aplicados. Eliminación de ruido "
            "activada. Puerta anti-ruidos activada. Ganancia: Subir 6 dB.")

    def test_solo_con_ganancia(self):
        self.assertEqual(
            filtros_microfono.resumen(
                filtros_microfono.Estado(False, False, -3)),
            "Filtros del micrófono aplicados. Ganancia: Bajar 3 dB.")

    def test_sin_nada_activo(self):
        self.assertEqual(
            filtros_microfono.resumen(
                filtros_microfono.Estado(False, False, 0)),
            "Filtros del micrófono desactivados.")


class TestCliente(unittest.TestCase):

    def test_leer_pide_los_filtros_y_cierra(self):
        cliente = ClienteDoble([
            filtro("Eliminación de ruido", "noise_suppress_filter_v2")])
        estado = filtros_microfono.leer(
            "Mic/Aux", crear_cliente=lambda: cliente)
        self.assertEqual(estado, filtros_microfono.Estado(True, False, 0))
        self.assertEqual(cliente.peticiones,
                         [("GetSourceFilterList", {"sourceName": "Mic/Aux"})])
        self.assertTrue(cliente.cerrado)

    def test_aplicar_manda_el_plan_y_cierra(self):
        cliente = ClienteDoble([])
        filtros_microfono.aplicar(
            "Mic/Aux", filtros_microfono.Estado(True, False, 3),
            crear_cliente=lambda: cliente)
        self.assertEqual(cliente.peticiones[0],
                         ("GetSourceFilterList", {"sourceName": "Mic/Aux"}))
        self.assertEqual(cliente.peticiones[1][0], "CreateSourceFilter")
        self.assertEqual(
            cliente.peticiones[1][1]["sourceName"], "Mic/Aux")
        self.assertTrue(cliente.cerrado)

    def test_leer_cierra_aunque_obs_falle(self):
        cliente = ClienteDoble(error=True)
        with self.assertRaises(ObsError):
            filtros_microfono.leer(
                "Mic/Aux", crear_cliente=lambda: cliente)
        self.assertTrue(cliente.cerrado)

    def test_aplicar_cierra_aunque_obs_falle(self):
        cliente = ClienteDoble(error=True)
        with self.assertRaises(ObsError):
            filtros_microfono.aplicar(
                "Mic/Aux", filtros_microfono.Estado(True, False, 0),
                crear_cliente=lambda: cliente)
        self.assertTrue(cliente.cerrado)


if __name__ == "__main__":
    unittest.main()

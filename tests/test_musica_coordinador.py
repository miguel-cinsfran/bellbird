"""Pruebas del coordinador de música (coordinador.py)."""

import random
import threading
import unittest

from ytchat.music.coordinador import Coordinador
from ytchat.music.modelo import (
    AVANZO, COLA_VACIA, ERROR_MOTOR, FIN_LISTA, INICIO_LISTA, OK,
    SIN_TEMA, TEMA_FALLIDO, VOLUMEN_INVALIDO, Tema,
)


class AdaptadorFalso:
    """Anota cada llamada y puede fallar en cargar para un origen concreto."""

    def __init__(self):
        self.llamadas = []
        self.fallar = set()

    def cargar(self, tema, ficha):
        self.llamadas.append(("cargar", tema.origen, ficha))
        if tema.origen in self.fallar:
            raise RuntimeError("fallo simulado")

    def pausar(self):
        self.llamadas.append(("pausar",))

    def reanudar(self):
        self.llamadas.append(("reanudar",))

    def detener(self):
        self.llamadas.append(("detener",))

    def volumen(self, valor):
        self.llamadas.append(("volumen", valor))

    def cargas(self):
        return [l for l in self.llamadas if l[0] == "cargar"]

    def ultima_ficha(self):
        cargas = self.cargas()
        return cargas[-1][2] if cargas else None


def tema(n, **campos):
    return Tema(f"C:/musica/{n}.mp3", f"Tema {n}", **campos)


class TestOperaciones(unittest.TestCase):

    def test_reproducir_lista(self):
        ad = AdaptadorFalso()
        r = Coordinador(ad).reproducir_lista([tema("a"), tema("b")])
        self.assertTrue(r.ok)
        self.assertEqual(r.codigo, OK)
        self.assertEqual(r.estado.posicion, 0)
        self.assertEqual(ad.llamadas[0], ("cargar", "C:/musica/a.mp3", 1))

    def test_reproducir_lista_vacia(self):
        ad = AdaptadorFalso()
        r = Coordinador(ad).reproducir_lista([])
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, COLA_VACIA)
        self.assertEqual(ad.llamadas, [])

    def test_reproducir_tema(self):
        ad = AdaptadorFalso()
        r = Coordinador(ad).reproducir_tema(tema("solo"))
        self.assertTrue(r.ok)
        self.assertEqual(len(r.estado.cola), 1)
        self.assertEqual(r.estado.posicion, 0)

    def test_agregar_sin_cortar_lo_que_suena(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a")])
        r = c.agregar([tema("b"), tema("c")])
        self.assertTrue(r.ok)
        self.assertEqual(r.estado.posicion, 0)
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/a.mp3", "C:/musica/b.mp3", "C:/musica/c.mp3"])
        self.assertEqual(len(ad.cargas()), 1)

    def test_agregar_desde_vacio_empieza_por_el_primero(self):
        ad = AdaptadorFalso()
        r = Coordinador(ad).agregar([tema("a"), tema("b")])
        self.assertTrue(r.ok)
        self.assertEqual(r.estado.posicion, 0)
        self.assertEqual(ad.llamadas[0], ("cargar", "C:/musica/a.mp3", 1))

    def test_agregar_vacio(self):
        ad = AdaptadorFalso()
        r = Coordinador(ad).agregar([])
        self.assertEqual(r.codigo, COLA_VACIA)
        self.assertEqual(ad.llamadas, [])

    def test_alternar_pausa(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a")])
        self.assertTrue(c.alternar_pausa().estado.pausado)
        self.assertFalse(c.alternar_pausa().estado.pausado)
        self.assertEqual(ad.llamadas[-2][0], "pausar")
        self.assertEqual(ad.llamadas[-1][0], "reanudar")

    def test_alternar_pausa_sin_tema(self):
        c = Coordinador(AdaptadorFalso())
        self.assertEqual(c.alternar_pausa().codigo, SIN_TEMA)

    def test_alternar_pausa_con_lista_terminada(self):
        c = Coordinador(AdaptadorFalso())
        c.reproducir_lista([tema("a")])
        c.siguiente()
        self.assertTrue(c.estado().terminado)
        self.assertEqual(c.alternar_pausa().codigo, SIN_TEMA)

    def test_siguiente_y_anterior(self):
        c = Coordinador(AdaptadorFalso())
        c.reproducir_lista([tema("a"), tema("b"), tema("c")])
        self.assertEqual(c.siguiente().estado.posicion, 1)
        self.assertEqual(c.anterior().estado.posicion, 0)

    def test_siguiente_fin_lista(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a")])
        r = c.siguiente()
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, FIN_LISTA)
        self.assertTrue(r.estado.terminado)
        self.assertEqual(r.estado.posicion, 0)
        self.assertEqual(ad.llamadas[-1][0], "detener")

    def test_anterior_inicio_lista(self):
        c = Coordinador(AdaptadorFalso())
        c.reproducir_lista([tema("a"), tema("b")])
        c.siguiente()
        c.anterior()
        r = c.anterior()
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, INICIO_LISTA)
        self.assertEqual(r.estado.posicion, 0)

    def test_siguiente_y_anterior_sin_tema(self):
        c = Coordinador(AdaptadorFalso())
        self.assertEqual(c.siguiente().codigo, SIN_TEMA)
        self.assertEqual(c.anterior().codigo, SIN_TEMA)

    def test_siguiente_queda_sonando_aunque_estuviera_en_pausa(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        c.alternar_pausa()
        r = c.siguiente()
        self.assertTrue(r.ok)
        self.assertFalse(r.estado.pausado)

    def test_detener_conserva_la_cola(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        r = c.detener()
        self.assertTrue(r.ok)
        self.assertIsNone(r.estado.posicion)
        self.assertEqual(len(r.estado.cola), 2)
        self.assertEqual(ad.llamadas[-1][0], "detener")

    def test_fijar_volumen(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        r = c.fijar_volumen(50)
        self.assertTrue(r.ok)
        self.assertEqual(r.estado.volumen, 50)
        self.assertEqual(ad.llamadas[-1], ("volumen", 50))

    def test_volumen_invalido_no_llama_al_adaptador(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        for valor in (101, -1, True, False, 50.5, "50", None):
            r = c.fijar_volumen(valor)
            self.assertFalse(r.ok, valor)
            self.assertEqual(r.codigo, VOLUMEN_INVALIDO, valor)
        self.assertEqual(ad.llamadas, [])

    def test_error_motor_al_reproducir_lista(self):
        ad = AdaptadorFalso()
        ad.fallar.add("C:/musica/a.mp3")
        r = Coordinador(ad).reproducir_lista([tema("a"), tema("b")])
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, ERROR_MOTOR)
        self.assertEqual(r.tema.origen, "C:/musica/a.mp3")
        self.assertEqual(r.estado.posicion, 0)
        self.assertTrue(r.estado.terminado)
        self.assertEqual(len(ad.cargas()), 1)
        self.assertEqual(ad.llamadas[-1][0], "detener")

    def test_error_motor_al_siguiente(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        ad.fallar.add("C:/musica/b.mp3")
        r = c.siguiente()
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, ERROR_MOTOR)
        self.assertEqual(r.estado.posicion, 1)
        self.assertTrue(r.estado.terminado)


class TestReproducirDesde(unittest.TestCase):

    def test_salta_al_tema_de_la_cola(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b"), tema("c")])
        r = c.reproducir_desde(2)
        self.assertTrue(r.ok)
        self.assertEqual(r.codigo, OK)
        self.assertEqual(r.estado.posicion, 2)
        self.assertEqual(ad.cargas()[-1][1], "C:/musica/c.mp3")

    def test_sin_cola(self):
        ad = AdaptadorFalso()
        r = Coordinador(ad).reproducir_desde(0)
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, COLA_VACIA)
        self.assertEqual(ad.llamadas, [])

    def test_indice_fuera_de_rango(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a")])
        for indice in (-1, 1, 5):
            con = c.reproducir_desde(indice)
            self.assertFalse(con.ok, indice)
            self.assertEqual(con.codigo, SIN_TEMA, indice)
        self.assertEqual(len(ad.cargas()), 1)

    def test_indice_que_no_es_entero(self):
        c = Coordinador(AdaptadorFalso())
        c.reproducir_lista([tema("a")])
        for indice in (None, "0", 0.0, True):
            con = c.reproducir_desde(indice)
            self.assertEqual(con.codigo, SIN_TEMA, indice)

    def test_queda_sonando_aunque_estuviera_en_pausa(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        c.alternar_pausa()
        r = c.reproducir_desde(1)
        self.assertTrue(r.ok)
        self.assertFalse(r.estado.pausado)

    def test_error_motor_deja_la_cola_terminada(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        ad.fallar.add("C:/musica/b.mp3")
        r = c.reproducir_desde(1)
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, ERROR_MOTOR)
        self.assertEqual(r.tema.origen, "C:/musica/b.mp3")
        self.assertEqual(r.estado.posicion, 1)
        self.assertTrue(r.estado.terminado)
        self.assertEqual(ad.llamadas[-1][0], "detener")

    def test_el_mismo_tema_se_puede_saltar_a_si_mismo(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a")])
        r = c.reproducir_desde(0)
        self.assertTrue(r.ok)
        self.assertEqual(len(ad.cargas()), 2)


class TestAContinuacion(unittest.TestCase):

    def test_inserta_detras_del_actual_sin_cortar(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y"), tema("z")])
        r = c.a_continuacion([tema("a")])
        self.assertTrue(r.ok)
        self.assertEqual(r.codigo, OK)
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/x.mp3", "C:/musica/a.mp3",
                          "C:/musica/y.mp3", "C:/musica/z.mp3"])
        self.assertEqual(r.estado.posicion, 0)
        self.assertFalse(r.estado.pausado)
        self.assertEqual(len(ad.cargas()), 1)

    def test_pedidos_seguidos_quedan_en_orden_de_llegada(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y"), tema("z")])
        c.a_continuacion([tema("a")])
        r = c.a_continuacion([tema("b")])
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/x.mp3", "C:/musica/a.mp3",
                          "C:/musica/b.mp3", "C:/musica/y.mp3",
                          "C:/musica/z.mp3"])
        self.assertEqual(len(ad.cargas()), 1)

    def test_al_terminar_suenan_en_orden_los_pendientes(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y"), tema("z")])
        c.a_continuacion([tema("a")])
        c.a_continuacion([tema("b")])
        c.tema_terminado(ad.ultima_ficha(), False)
        c.tema_terminado(ad.ultima_ficha(), False)
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([l[1] for l in ad.cargas()],
                         ["C:/musica/x.mp3", "C:/musica/a.mp3",
                          "C:/musica/b.mp3", "C:/musica/y.mp3"])

    def test_avanzar_consume_un_pendiente(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y"), tema("z")])
        c.a_continuacion([tema("a")])
        c.a_continuacion([tema("b")])
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual(c.estado().posicion, 1)
        r = c.a_continuacion([tema("c")])
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/x.mp3", "C:/musica/a.mp3",
                          "C:/musica/b.mp3", "C:/musica/c.mp3",
                          "C:/musica/y.mp3", "C:/musica/z.mp3"])

    def test_saltar_resetea_y_el_nuevo_va_detras_del_actual(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y"), tema("z")])
        c.a_continuacion([tema("a")])
        c.reproducir_desde(2)
        r = c.a_continuacion([tema("b")])
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/x.mp3", "C:/musica/a.mp3",
                          "C:/musica/y.mp3", "C:/musica/b.mp3",
                          "C:/musica/z.mp3"])

    def test_en_pausa_inserta_y_sigue_en_pausa(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y")])
        c.alternar_pausa()
        r = c.a_continuacion([tema("a")])
        self.assertTrue(r.ok)
        self.assertTrue(r.estado.pausado)
        self.assertEqual(r.estado.posicion, 0)
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/x.mp3", "C:/musica/a.mp3",
                          "C:/musica/y.mp3"])
        self.assertEqual(len(ad.cargas()), 1)

    def test_sin_nada_activo_arranca_como_agregar(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        r = c.a_continuacion([tema("n")])
        self.assertTrue(r.ok)
        self.assertEqual(r.estado.posicion, 0)
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/n.mp3"])
        self.assertEqual(ad.cargas()[-1][1], "C:/musica/n.mp3")

    def test_cola_terminada_arranca_por_el_nuevo(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x")])
        c.siguiente()
        self.assertTrue(c.estado().terminado)
        r = c.a_continuacion([tema("n")])
        self.assertTrue(r.ok)
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/x.mp3", "C:/musica/n.mp3"])
        self.assertEqual(r.estado.posicion, 1)
        self.assertFalse(r.estado.terminado)
        self.assertEqual(ad.cargas()[-1][1], "C:/musica/n.mp3")

    def test_sin_nada_activo_con_fallo_da_error_motor(self):
        ad = AdaptadorFalso()
        ad.fallar.add("C:/musica/n.mp3")
        c = Coordinador(ad)
        r = c.a_continuacion([tema("n")])
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, ERROR_MOTOR)
        self.assertEqual(r.tema.origen, "C:/musica/n.mp3")
        self.assertTrue(r.estado.terminado)

    def test_con_aleatorio_no_remezcla_y_va_detras(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x"), tema("y"), tema("z")])
        c.fijar_aleatorio(True)
        antes = [t.origen for t in c.estado().cola]
        r = c.a_continuacion([tema("a")])
        self.assertEqual([t.origen for t in r.estado.cola],
                         [antes[0], "C:/musica/a.mp3"] + antes[1:])
        self.assertEqual(len(ad.cargas()), 1)

    def test_vacio_da_cola_vacia(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("x")])
        r = c.a_continuacion([])
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, COLA_VACIA)
        self.assertEqual(len(ad.cargas()), 1)

    def test_propiedad_el_pedido_queda_tras_los_pendientes(self):
        rng = random.Random(231)
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        base = [tema(f"p{i}") for i in range(5)]
        contador = 0
        for _ in range(200):
            accion = rng.randrange(7)
            if accion == 0:
                pedido = tema(f"nuevo{contador}")
                contador += 1
                antes = c.estado()
                activo = (antes.posicion is not None
                          and not antes.terminado)
                c.a_continuacion([pedido])
                if activo:
                    estado = c.estado()
                    self.assertEqual(
                        estado.cola[estado.posicion + c._a_continuacion].origen,
                        pedido.origen)
            elif accion == 1:
                c.siguiente()
            elif accion == 2:
                c.anterior()
            elif accion == 3:
                cola = c.estado().cola
                if cola:
                    c.reproducir_desde(rng.randrange(-1, len(cola) + 1))
                else:
                    c.reproducir_desde(0)
            elif accion == 4:
                ficha = ad.ultima_ficha() if ad.cargas() else 0
                c.tema_terminado(ficha, rng.choice([True, False]))
            elif accion == 5:
                c.detener()
            else:
                c.agregar(rng.sample(base, rng.randrange(4)))


class TestAleatorio(unittest.TestCase):

    def test_mezclar_no_se_usa_con_aleatorio_apagado(self):
        usos = []
        c = Coordinador(AdaptadorFalso(), mezclar=lambda l: usos.append(list(l)))
        c.reproducir_lista([tema("a"), tema("b")])
        self.assertEqual(usos, [])

    def test_aleatorio_mezcla_una_copia(self):
        c = Coordinador(AdaptadorFalso(), mezclar=lambda lista: lista.reverse())
        c.fijar_aleatorio(True)
        r = c.reproducir_lista([tema("a"), tema("b"), tema("c")])
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/c.mp3", "C:/musica/b.mp3", "C:/musica/a.mp3"])
        self.assertEqual(r.estado.posicion, 0)

    def test_aleatorio_vale_para_la_proxima_lista(self):
        c = Coordinador(AdaptadorFalso(), mezclar=lambda lista: lista.reverse())
        c.reproducir_lista([tema("a"), tema("b")])
        antes = [t.origen for t in c.estado().cola]
        c.fijar_aleatorio(True)
        despues = [t.origen for t in c.estado().cola]
        self.assertEqual(antes, despues)

    def test_en_orden_no_mezcla_con_aleatorio_activo(self):
        usos = []
        c = Coordinador(AdaptadorFalso(),
                        mezclar=lambda lista: usos.append(list(lista)) or lista.reverse())
        c.fijar_aleatorio(True)
        r = c.reproducir_lista([tema("a"), tema("b"), tema("c")], en_orden=True)
        self.assertEqual([t.origen for t in r.estado.cola],
                         ["C:/musica/a.mp3", "C:/musica/b.mp3", "C:/musica/c.mp3"])
        self.assertEqual(usos, [])

    def test_en_orden_sigue_mezclando_si_no_lo_piden(self):
        c = Coordinador(AdaptadorFalso(), mezclar=lambda lista: lista.reverse())
        c.fijar_aleatorio(True)
        r = c.reproducir_lista([tema("a"), tema("b"), tema("c")])
        self.assertEqual(r.estado.cola[0].origen, "C:/musica/c.mp3")


class TestAvanceAutomatico(unittest.TestCase):

    def test_tema_terminado_avanza(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        ficha = ad.ultima_ficha()
        c.tema_terminado(ficha, False)
        self.assertEqual(c.estado().posicion, 1)
        self.assertFalse(c.estado().terminado)
        self.assertEqual(ad.ultima_ficha(), ficha + 1)

    def test_tema_terminado_fin_de_lista(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a")])
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([a.codigo for a in avisos], [FIN_LISTA])
        self.assertTrue(avisos[0].ok)
        self.assertTrue(c.estado().terminado)
        self.assertEqual(c.estado().posicion, 0)
        self.assertEqual(ad.llamadas[-1][0], "detener")

    def test_tema_terminado_con_fallo_notifica_y_avanza(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a"), tema("b")])
        c.tema_terminado(ad.ultima_ficha(), True)
        self.assertEqual([a.codigo for a in avisos], [TEMA_FALLIDO, AVANZO])
        self.assertEqual(avisos[0].tema.origen, "C:/musica/a.mp3")
        self.assertTrue(avisos[1].ok)
        self.assertEqual(c.estado().posicion, 1)

    def test_ficha_vieja_se_ignora(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a"), tema("b")])
        ficha_vieja = ad.ultima_ficha()
        c.tema_terminado(ficha_vieja, False)
        avisos.clear()
        c.tema_terminado(ficha_vieja, False)
        self.assertEqual(c.estado().posicion, 1)
        self.assertEqual(avisos, [])
        self.assertEqual(len(ad.cargas()), 2)

    def test_mismo_tema_dos_veces_ficha_vieja_no_avanza(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a"), tema("a")])
        ficha_primera = ad.ultima_ficha()
        c.tema_terminado(ficha_primera, False)
        avisos.clear()
        c.tema_terminado(ficha_primera, False)
        self.assertEqual(c.estado().posicion, 1)
        self.assertEqual(avisos, [])
        self.assertEqual(len(ad.cargas()), 2)

    def test_avance_saltea_dos_fallos_seguidos(self):
        ad = AdaptadorFalso()
        ad.fallar.update({"C:/musica/b.mp3", "C:/musica/c.mp3"})
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a"), tema("b"), tema("c"), tema("d")])
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([a.codigo for a in avisos], [TEMA_FALLIDO, TEMA_FALLIDO, AVANZO])
        self.assertEqual(c.estado().posicion, 3)
        self.assertFalse(c.estado().terminado)
        self.assertEqual([l[1] for l in ad.cargas()][-3:],
                         ["C:/musica/b.mp3", "C:/musica/c.mp3", "C:/musica/d.mp3"])

    def test_ultimo_que_falla_termina_en_fin_lista(self):
        ad = AdaptadorFalso()
        ad.fallar.add("C:/musica/b.mp3")
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a"), tema("b")])
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([a.codigo for a in avisos], [TEMA_FALLIDO, FIN_LISTA])
        self.assertTrue(avisos[1].ok)
        self.assertTrue(c.estado().terminado)
        self.assertEqual(c.estado().posicion, 1)
        self.assertEqual(ad.llamadas[-1][0], "detener")

    def test_al_cambiar_que_lanza_no_rompe(self):
        def explota(resultado):
            raise RuntimeError("boom")

        ad = AdaptadorFalso()
        c = Coordinador(ad, al_cambiar=explota)
        c.reproducir_lista([tema("a"), tema("b")])
        with self.assertLogs("ytchat.coordinador", level="ERROR"):
            c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual(c.estado().posicion, 1)

    def test_al_cambiar_con_el_lock_suelto(self):
        ad = AdaptadorFalso()
        vistos = []
        coordinador = None

        def al_cambiar(resultado):
            # Si el coordinador tuviera el lock tomado, estado() colgaría.
            vistos.append(coordinador.estado().posicion)

        coordinador = Coordinador(ad, al_cambiar=al_cambiar)
        coordinador.reproducir_lista([tema("a"), tema("b")])
        ficha = ad.ultima_ficha()
        hilo = threading.Thread(target=coordinador.tema_terminado, args=(ficha, False),
                                daemon=True)
        hilo.start()
        hilo.join(timeout=5)
        self.assertFalse(hilo.is_alive())
        self.assertEqual(vistos, [1])

    def test_tema_terminado_desde_otro_hilo(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        hilo = threading.Thread(target=c.tema_terminado, args=(ad.ultima_ficha(), False),
                                daemon=True)
        hilo.start()
        hilo.join(timeout=5)
        self.assertFalse(hilo.is_alive())
        self.assertEqual(c.estado().posicion, 1)


class TestRepetir(unittest.TestCase):

    def test_propiedad_repetir(self):
        c = Coordinador(AdaptadorFalso())
        self.assertFalse(c.repetir)
        self.assertEqual(c.fijar_repetir(True).codigo, OK)
        self.assertTrue(c.repetir)
        self.assertEqual(c.fijar_repetir(False).codigo, OK)
        self.assertFalse(c.repetir)

    def test_repetir_vuelve_al_primero_tras_el_ultimo(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.fijar_repetir(True)
        c.reproducir_lista([tema("a"), tema("b")])
        c.tema_terminado(ad.ultima_ficha(), False)
        avisos.clear()
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([a.codigo for a in avisos], [AVANZO])
        self.assertEqual(c.estado().posicion, 0)
        self.assertFalse(c.estado().terminado)

    def test_repetir_un_solo_tema_se_vuelve_a_sonar(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.fijar_repetir(True)
        c.reproducir_lista([tema("a")])
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([a.codigo for a in avisos], [AVANZO])
        self.assertEqual(c.estado().posicion, 0)
        self.assertFalse(c.estado().terminado)

    def test_repetir_inactivo_se_comporta_como_hoy(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a")])
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual([a.codigo for a in avisos], [FIN_LISTA])
        self.assertTrue(c.estado().terminado)

    def test_repetir_todos_fallan_termina_en_fin_lista_sin_bucle(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.fijar_repetir(True)
        c.reproducir_lista([tema("a"), tema("b")])
        ad.fallar.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        hilo = threading.Thread(
            target=c.tema_terminado, args=(ad.ultima_ficha(), False), daemon=True)
        hilo.start()
        hilo.join(timeout=5)
        self.assertFalse(
            hilo.is_alive(), "hay bucle: el avance con repetir no terminó")
        self.assertTrue(c.estado().terminado)
        self.assertEqual(avisos[-1].codigo, FIN_LISTA)

    def test_siguiente_en_el_ultimo_con_repetir_vuelve_al_primero(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.fijar_repetir(True)
        c.reproducir_lista([tema("a"), tema("b")])
        self.assertEqual(c.siguiente().estado.posicion, 1)
        r = c.siguiente()
        self.assertTrue(r.ok)
        self.assertEqual(r.codigo, OK)
        self.assertEqual(r.estado.posicion, 0)

    def test_anterior_no_envuelve_aunque_repetir_este_activo(self):
        c = Coordinador(AdaptadorFalso())
        c.fijar_repetir(True)
        c.reproducir_lista([tema("a"), tema("b")])
        r = c.anterior()
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, INICIO_LISTA)

    def test_aleatorio_mas_repetir_conserva_el_orden_al_volver_a_empezar(self):
        usos = []
        ad = AdaptadorFalso()
        c = Coordinador(
            ad,
            mezclar=lambda lista: usos.append(list(lista)) or lista.reverse(),
        )
        c.fijar_aleatorio(True)
        c.fijar_repetir(True)
        c.reproducir_lista([tema("a"), tema("b"), tema("c")])
        orden = [t.origen for t in c.estado().cola]
        c.tema_terminado(ad.ultima_ficha(), False)
        c.tema_terminado(ad.ultima_ficha(), False)
        c.tema_terminado(ad.ultima_ficha(), False)
        self.assertEqual(c.estado().posicion, 0)
        self.assertEqual([t.origen for t in c.estado().cola], orden)
        self.assertEqual(len(usos), 1)


class TestActualizarTemas(unittest.TestCase):

    def test_cambia_el_nombre_en_la_cola(self):
        ad = AdaptadorFalso()
        c = Coordinador(ad)
        c.reproducir_lista([tema("a"), tema("b")])
        nuevos = [Tema("C:/musica/a.mp3", "Tema A", artista="Ana")]
        self.assertEqual(c.actualizar_temas({t.origen: t for t in nuevos}), 1)
        cola = c.estado().cola
        self.assertEqual(cola[0].titulo, "Tema A")
        self.assertEqual(cola[0].artista, "Ana")
        self.assertEqual(cola[1].titulo, "Tema b")

    def test_no_toca_posicion_ficha_ni_adaptador_ni_avisa(self):
        ad = AdaptadorFalso()
        avisos = []
        c = Coordinador(ad, al_cambiar=avisos.append)
        c.reproducir_lista([tema("a"), tema("b")])
        c.siguiente()
        c.alternar_pausa()
        llamadas_antes = list(ad.llamadas)
        ficha_antes = ad.ultima_ficha()
        c.fijar_aleatorio(True)
        cola_antes = [t.origen for t in c.estado().cola]
        nuevos = [Tema("C:/musica/b.mp3", "Tema B", artista="Beto")]
        self.assertEqual(c.actualizar_temas({t.origen: t for t in nuevos}), 1)
        estado = c.estado()
        self.assertEqual(estado.posicion, 1)
        self.assertTrue(estado.pausado)
        self.assertTrue(estado.aleatorio)
        self.assertEqual([t.origen for t in estado.cola], cola_antes)
        self.assertEqual(ad.llamadas, llamadas_antes)
        self.assertEqual(ad.ultima_ficha(), ficha_antes)
        self.assertEqual(avisos, [])

    def test_sin_cola_o_sin_coincidencias_devuelve_cero(self):
        c = Coordinador(AdaptadorFalso())
        self.assertEqual(
            c.actualizar_temas({"C:/musica/a.mp3": tema("a")}), 0)
        c.reproducir_lista([tema("a")])
        self.assertEqual(
            c.actualizar_temas({"C:/musica/fantasma.mp3": tema("x")}), 0)
        self.assertEqual(c.actualizar_temas({}), 0)
        self.assertEqual(c.estado().cola[0].titulo, "Tema a")


class TestPropiedad(unittest.TestCase):

    def test_secuencia_aleatoria_mantiene_invariantes(self):
        rng = random.Random(20261018)
        ad = AdaptadorFalso()
        c = Coordinador(ad, mezclar=lambda lista: rng.shuffle(lista))
        temas = [tema(f"t{i}") for i in range(5)]
        for _ in range(200):
            accion = rng.randrange(11)
            if accion == 0:
                c.reproducir_lista(rng.sample(temas, rng.randrange(6)),
                                   en_orden=rng.random() < 0.5)
            elif accion == 1:
                c.agregar(rng.sample(temas, rng.randrange(6)))
            elif accion == 2:
                c.alternar_pausa()
            elif accion == 3:
                c.siguiente()
            elif accion == 4:
                c.anterior()
            elif accion == 5:
                c.detener()
            elif accion == 6:
                c.fijar_volumen(rng.randrange(-5, 106))
            elif accion == 7:
                c.fijar_aleatorio(rng.choice([True, False]))
            elif accion == 8:
                c.fijar_repetir(rng.choice([True, False]))
            elif accion == 9:
                c.reproducir_desde(rng.randrange(-2, 7))
            else:
                ficha = ad.ultima_ficha() if rng.random() < 0.5 else rng.randrange(-2, 4)
                c.tema_terminado(ficha, rng.choice([True, False]))
            estado = c.estado()
            self.assertTrue(estado.posicion is None
                            or 0 <= estado.posicion < len(estado.cola))
            if estado.terminado:
                indices_detener = [i for i, l in enumerate(ad.llamadas) if l[0] == "detener"]
                indices_cargar = [i for i, l in enumerate(ad.llamadas) if l[0] == "cargar"]
                self.assertTrue(indices_detener, "terminado sin detener")
                if indices_cargar:
                    self.assertGreater(indices_detener[-1], indices_cargar[-1])


if __name__ == "__main__":
    unittest.main()

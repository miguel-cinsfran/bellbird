"""Pruebas de la lógica pura y del control de música, sin ventanas reales.

`ControlMusica` se prueba con un frame falso, `wx.CallAfter` reemplazado por
una llamada directa, un adaptador falso y `diagnostico.crear_hilo` corriendo
en el acto. En ningún caso se crea `wx.App`, ni se abre una ventana, ni suena
nada: el motor de VLC queda reemplazado por un doble.
"""

import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ytchat.music import listas
from ytchat.music import memoria
from ytchat.music.modelo import (AVANZO, FIN_LISTA, TEMA_FALLIDO, EstadoMusica,
                                 Resultado, Tema)
from ytchat.ui import gui_musica
from ytchat.ui.gui_musica import ControlMusica, nuevo_volumen, toca_pausar


class _AdaptadorFalso:
    def __init__(self, salida_audio=None, volumen=100, dispositivo=None):
        self.inicio = {"salida_audio": salida_audio, "volumen": volumen,
                       "dispositivo": dispositivo}
        self.llamadas = []
        self.aviso = None

    def asignar_aviso(self, funcion):
        self.aviso = funcion

    def cargar(self, tema, ficha):
        self.llamadas.append(("cargar", tema.origen, ficha))

    def pausar(self):
        self.llamadas.append(("pausar",))

    def reanudar(self):
        self.llamadas.append(("reanudar",))

    def detener(self):
        self.llamadas.append(("detener",))

    def volumen(self, valor):
        self.llamadas.append(("volumen", valor))

    def cerrar(self):
        self.llamadas.append(("cerrar",))


class _SndFalso:
    def __init__(self):
        self.sonidos = []

    def reproducir(self, evento):
        self.sonidos.append(evento)


class _HiloInmediato:
    def __init__(self, target, args):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


class _HiloDiferido:
    """Hilo que no corre: deja al control en «preparando» para la prueba."""

    def __init__(self, target, args):
        self._target = target
        self._args = args

    def start(self):
        pass


def _crear_hilo_inmediato(target, nombre, *, args=(), daemon=True):
    return _HiloInmediato(target, args)


def _frame(**config):
    base = {
        "musica_carpeta": "", "musica_aleatorio": False, "musica_repetir": False,
        "musica_sonido_tema": True, "musica_decir_titulo": True,
        "musica_incluir_artista": False, "musica_volumen": 50,
        "musica_salida": "",
    }
    base.update(config)
    return SimpleNamespace(_config=base)


@contextlib.contextmanager
def _entorno(fabrica=None):
    """Dobla el motor, los hilos, CallAfter, el lector y los sonidos.

    También manda la memoria de música a un temporal: ninguna prueba escribe
    en la carpeta de datos real.
    """
    snd = _SndFalso()
    creados = []

    def fabrica_por_defecto(**kwargs):
        adaptador = _AdaptadorFalso(**kwargs)
        creados.append(adaptador)
        return adaptador

    fabrica = fabrica or fabrica_por_defecto
    with tempfile.TemporaryDirectory() as tmp:
        ruta_memoria = Path(tmp) / "musica_estado.json"
        with mock.patch.object(gui_musica, "AdaptadorVlc", side_effect=fabrica), \
                mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                  _crear_hilo_inmediato), \
                mock.patch.object(gui_musica.wx, "CallAfter",
                                  side_effect=lambda fn, *a: fn(*a)), \
                mock.patch.object(gui_musica, "anunciar") as anunciar, \
                mock.patch.object(gui_musica.paths, "estado_musica",
                                  return_value=ruta_memoria), \
                mock.patch.object(gui_musica, "_snd", snd):
            yield SimpleNamespace(anunciar=anunciar, snd=snd, creados=creados,
                                  memoria=ruta_memoria)


class TestFuncionesPuras(unittest.TestCase):

    def test_nuevo_volumen_suma_y_recorta(self):
        self.assertEqual(nuevo_volumen(50, 10), 60)
        self.assertEqual(nuevo_volumen(50, -10), 40)
        self.assertEqual(nuevo_volumen(100, 10), 100)
        self.assertEqual(nuevo_volumen(0, -10), 0)

    def test_nuevo_volumen_tolera_valor_no_numerico(self):
        self.assertEqual(nuevo_volumen(None, 10), 10)
        self.assertEqual(nuevo_volumen("50", 10), 60)

    def test_toca_pausar(self):
        estado_sin_tema = _estado(actual=False)
        self.assertFalse(toca_pausar(None))
        self.assertFalse(toca_pausar(estado_sin_tema))
        self.assertTrue(toca_pausar(_estado(actual=True)))
        self.assertFalse(toca_pausar(_estado(actual=True, terminado=True)))


def _estado(actual=False, terminado=False):
    from ytchat.music.modelo import EstadoMusica, Tema

    if actual:
        cola = (Tema("C:/m.mp3", "Tema"),)
        posicion = 0
    else:
        cola, posicion = (), None
    return EstadoMusica(cola, posicion, False, terminado, 100, False)


def _aviso(codigo=AVANZO, tema=None, cola=None, posicion=None, terminado=False):
    from ytchat.music.modelo import EstadoMusica, Tema

    if cola is None:
        cola = (Tema("C:/tema.mp3", "Tema 2", artista="Ana"),)
    return Resultado(True, codigo,
                     EstadoMusica(tuple(cola), posicion, False, terminado,
                                  100, False), tema)


class TestReproducir(unittest.TestCase):

    def test_sin_carpeta_avisa_y_no_prepara_motor(self):
        with _entorno() as env:
            ControlMusica(_frame()).reproducir_o_pausar()
        env.anunciar.assert_called_once_with(
            "No hay carpeta de música. Elige una en Preferencias, página Música")
        self.assertEqual(env.snd.sonidos, ["error"])
        self.assertEqual(env.creados, [])

    def test_con_carpeta_reproduce_la_lista_entera(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            (Path(tmp) / "b.mp3").write_bytes(b"")
            with _entorno() as env:
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.reproducir_o_pausar()
                cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
        self.assertEqual(len(cargas), 1)
        self.assertEqual(cargas[0][1], str((Path(tmp) / "a.mp3").resolve()))
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música", "a"])

    def test_carpeta_inexistente_avisa_con_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            faltante = str(Path(tmp) / "no_existe")
            with _entorno() as env:
                ControlMusica(_frame(musica_carpeta=faltante)).reproducir_o_pausar()
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música",
                          gui_musica.TEXTO_CARPETA_INEXISTENTE])
        self.assertEqual(env.snd.sonidos, ["error"])

    def test_segunda_accion_reproduce_en_vez_de_alternar(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            with _entorno() as env:
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.reproducir_o_pausar()
                env.anunciar.reset_mock()
                control.reproducir_o_pausar()
                llamadas = dict(
                    (l[0], l) for l in env.creados[0].llamadas
                    if l[0] in ("cargar", "pausar", "reanudar"))
        self.assertIn("pausar", llamadas)
        env.anunciar.assert_called_once_with("Música en pausa")


class TestAccionesSinMotor(unittest.TestCase):

    def test_siguiente_sin_motor_avisa_sin_tema(self):
        with _entorno() as env:
            ControlMusica(_frame()).siguiente()
        env.anunciar.assert_called_once_with("No hay música sonando")
        self.assertEqual(env.snd.sonidos, [])

    def test_detener_y_anterior_sin_motor_igual(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.anterior()
            control.detener()
        self.assertEqual(
            [c.args[0] for c in env.anunciar.call_args_list],
            ["No hay música sonando", "No hay música sonando"])

    def test_que_suena_sin_motor(self):
        with _entorno() as env:
            ControlMusica(_frame()).que_suena()
        env.anunciar.assert_called_once_with("No hay música sonando")


class TestVolumen(unittest.TestCase):

    def test_subir_en_el_limite_superior_guarda_igual(self):
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            frame = _frame(musica_volumen=100)
            ControlMusica(frame).subir_volumen()
        self.assertEqual(frame._config["musica_volumen"], 100)
        guardar.assert_called_once_with("volumen", "100")
        env.anunciar.assert_called_once_with("Volumen de la música: 100")

    def test_bajar_en_el_limite_inferior_guarda_igual(self):
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            frame = _frame(musica_volumen=0)
            ControlMusica(frame).bajar_volumen()
        self.assertEqual(frame._config["musica_volumen"], 0)
        guardar.assert_called_once_with("volumen", "0")
        env.anunciar.assert_called_once_with("Volumen de la música: 0")

    def test_paso_intermedio(self):
        with _entorno(), mock.patch.object(ControlMusica, "_guardar"):
            frame = _frame(musica_volumen=40)
            ControlMusica(frame).subir_volumen()
        self.assertEqual(frame._config["musica_volumen"], 50)


class TestAleatorio(unittest.TestCase):

    def test_invierte_guarda_sincroniza_y_anuncia(self):
        item = mock.Mock()
        frame = _frame(musica_aleatorio=False)
        frame.mi_musica_aleatorio = item
        with _entorno() as env:
            with mock.patch.object(ControlMusica, "_guardar") as guardar:
                ControlMusica(frame).alternar_aleatorio()
        self.assertTrue(frame._config["musica_aleatorio"])
        item.Check.assert_called_once_with(True)
        guardar.assert_called_once_with("aleatorio", "true")
        env.anunciar.assert_called_once_with("Orden aleatorio activado")

    def test_apagar_anuncia_lo_contrario(self):
        frame = _frame(musica_aleatorio=True)
        frame.mi_musica_aleatorio = mock.Mock()
        with _entorno() as env, mock.patch.object(ControlMusica, "_guardar"):
            ControlMusica(frame).alternar_aleatorio()
        self.assertFalse(frame._config["musica_aleatorio"])
        env.anunciar.assert_called_once_with("Orden aleatorio desactivado")


class TestAvisoAutomatico(unittest.TestCase):

    def test_al_cambiar_pasa_por_callafter(self):
        llamadas = []
        with mock.patch.object(gui_musica.wx, "CallAfter",
                               side_effect=lambda fn, *a: llamadas.append(fn)), \
                mock.patch.object(gui_musica, "anunciar") as anunciar, \
                mock.patch.object(gui_musica, "_snd") as snd:
            control = ControlMusica(_frame())
            control._al_cambiar(_aviso(posicion=0))
        self.assertEqual(llamadas, [control._aviso_automatico])
        anunciar.assert_not_called()
        snd.reproducir.assert_not_called()

    def test_aviso_automatico_respeta_las_tres_casillas(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=True, musica_decir_titulo=True,
                musica_incluir_artista=True))
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_called_once_with("Tema 2, de Ana")
        self.assertEqual(env.snd.sonidos, ["musica_tema"])

    def test_aviso_automatico_solo_sonido(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=True, musica_decir_titulo=False))
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_not_called()
        self.assertEqual(env.snd.sonidos, ["musica_tema"])

    def test_aviso_automatico_con_las_dos_casillas_apagadas_no_hace_nada(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=False, musica_decir_titulo=False))
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_not_called()
        self.assertEqual(env.snd.sonidos, [])

    def test_aviso_automatico_fin_de_lista_suena_siempre(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=False, musica_decir_titulo=False))
            control._aviso_automatico(Resultado(
                True, FIN_LISTA, _estado(actual=False)))
        env.anunciar.assert_called_once_with("Fin de la lista de música")
        self.assertEqual(env.snd.sonidos, ["musica_fin"])

    def test_aviso_automatico_tema_fallido(self):
        from ytchat.music.modelo import Tema
        with _entorno() as env:
            control = ControlMusica(_frame())
            control._aviso_automatico(Resultado(
                False, TEMA_FALLIDO, _estado(actual=False),
                tema=Tema("C:/m.mp3", "Tema roto")))
        env.anunciar.assert_called_once_with(
            "No se pudo reproducir: Tema roto. Se pasa al siguiente")
        self.assertEqual(env.snd.sonidos, ["musica_fallo"])


class TestMotor(unittest.TestCase):

    def test_motor_no_disponible_avisa_y_no_sigue(self):
        def fabrica(**kwargs):
            raise gui_musica.MotorNoDisponible("sin VLC")

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            with _entorno(fabrica=fabrica) as env:
                ControlMusica(_frame(musica_carpeta=tmp)).reproducir_o_pausar()
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música",
                          "La música no está disponible: no se pudo cargar VLC"])
        self.assertEqual(env.snd.sonidos, ["error"])

    def test_cerrar_sin_motor_no_lanza(self):
        with _entorno():
            ControlMusica(_frame()).cerrar()

    def test_cerrar_con_motor_cierra_el_adaptador(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            with _entorno() as env:
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.reproducir_o_pausar()
                control.cerrar()
        self.assertIn(("cerrar",), env.creados[0].llamadas)


class TestPreparandoLaMusica(unittest.TestCase):

    def test_primera_accion_anuncia_que_prepara(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            with _entorno() as env:
                ControlMusica(_frame(musica_carpeta=tmp)).reproducir_o_pausar()
        self.assertEqual(env.anunciar.call_args_list[0].args[0],
                         "Preparando la música")

    def test_segunda_accion_mientras_prepara_avisa_y_no_repite_hilo(self):
        creados = []

        def fabrica_hilo(target, nombre, *, args=(), daemon=True):
            hilo = _HiloDiferido(target, args)
            creados.append(hilo)
            return hilo

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            with _entorno() as env, \
                    mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                      fabrica_hilo):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.reproducir_o_pausar()
                control.reproducir_o_pausar()
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música",
                          "La música se está preparando"])
        self.assertEqual(len(creados), 1)


class TestAplicarPreferencias(unittest.TestCase):

    def test_con_motor_aplica_las_cuatro_y_sincroniza_la_casilla(self):
        item = mock.Mock()
        frame = _frame(musica_volumen=30, musica_salida="disp-1",
                       musica_aleatorio=True, musica_repetir=True)
        frame.mi_musica_aleatorio = item
        with _entorno() as env:
            control = ControlMusica(frame)
            control._coordinador = mock.Mock()
            control._adaptador = mock.Mock()
            control.aplicar_preferencias()
        control._coordinador.fijar_volumen.assert_called_once_with(30)
        control._adaptador.fijar_dispositivo.assert_called_once_with("disp-1")
        control._coordinador.fijar_aleatorio.assert_called_once_with(True)
        control._coordinador.fijar_repetir.assert_called_once_with(True)
        item.Check.assert_called_once_with(True)
        env.anunciar.assert_not_called()

    def test_salida_vacia_va_como_none(self):
        frame = _frame(musica_salida="")
        with _entorno():
            control = ControlMusica(frame)
            control._coordinador = mock.Mock()
            control._adaptador = mock.Mock()
            control.aplicar_preferencias()
        control._adaptador.fijar_dispositivo.assert_called_once_with(None)

    def test_sin_motor_no_hace_nada_ni_lanza(self):
        frame = _frame(musica_aleatorio=True)
        frame.mi_musica_aleatorio = mock.Mock()
        with _entorno() as env:
            control = ControlMusica(frame)
            control._adaptador = mock.Mock()
            control.aplicar_preferencias()
        control._adaptador.fijar_dispositivo.assert_not_called()
        frame.mi_musica_aleatorio.Check.assert_not_called()
        env.anunciar.assert_not_called()

    def test_no_lanza_aunque_el_coordinador_lance(self):
        with _entorno() as env, \
                mock.patch.object(gui_musica.logger, "exception"):
            control = ControlMusica(_frame())
            control._coordinador = mock.Mock()
            control._coordinador.fijar_volumen.side_effect = RuntimeError("boom")
            control._adaptador = mock.Mock()
            control.aplicar_preferencias()   # no debe propagar la excepción
        env.anunciar.assert_not_called()


class TestBibliotecaCompartida(unittest.TestCase):

    def _control_con_hilos(self, frame):
        hilos = []

        def crear_hilo(target, nombre, *, args=(), daemon=True):
            hilos.append(nombre)
            return _HiloInmediato(target, args)

        return hilos, crear_hilo

    def test_entrega_la_biblioteca_y_no_reindexa(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            hilos, crear_hilo = self._control_con_hilos(None)
            recibidas = []
            with _entorno(), \
                    mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                      crear_hilo):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.biblioteca(recibidas.append)
                control.biblioteca(recibidas.append)
        self.assertEqual(len(recibidas), 2)
        self.assertIs(recibidas[0], recibidas[1])
        self.assertEqual(len(recibidas[0].temas()), 1)
        self.assertEqual(hilos.count("musica-indice"), 1)

    def test_sin_carpeta_entrega_none_sin_indexar(self):
        hilos, crear_hilo = self._control_con_hilos(None)
        recibidas = []
        with _entorno(), \
                mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                  crear_hilo):
            control = ControlMusica(_frame(musica_carpeta=""))
            control.biblioteca(recibidas.append)
        self.assertEqual(recibidas, [None])
        self.assertEqual(hilos, [])

    def test_carpeta_inexistente_entrega_none_sin_anunciar(self):
        with tempfile.TemporaryDirectory() as tmp:
            faltante = str(Path(tmp) / "no_existe")
            with _entorno() as env:
                control = ControlMusica(_frame(musica_carpeta=faltante))
                recibidas = []
                control.biblioteca(recibidas.append)
        self.assertEqual(recibidas, [None])
        env.anunciar.assert_not_called()


class TestCambiarCarpeta(unittest.TestCase):

    def test_guarda_codificada_e_invalida_el_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            ruta = "C:\\Musica\\Rock;100%"
            with _entorno(), \
                    mock.patch.object(ControlMusica, "_guardar") as guardar:
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.biblioteca(lambda _b: None)
                control.cambiar_carpeta(ruta)
        self.assertEqual(control._config["musica_carpeta"], ruta)
        self.assertIsNone(control._biblioteca)
        guardar.assert_called_once_with(
            "carpeta", gui_musica.cfg.codificar_texto_ini(ruta))
        codificado = guardar.call_args.args[1]
        self.assertEqual(gui_musica.cfg.decodificar_texto_ini(codificado), ruta)


class TestAccionesDeLista(unittest.TestCase):

    def test_reproducir_temas_suena_el_primero(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas(temas)
        cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
        self.assertEqual(cargas[0][1], "C:/m/a.mp3")
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música", "A"])

    def test_reproducir_temas_en_orden_no_mezcla(self):
        temas = [Tema(f"C:/m/{n}.mp3", n) for n in ("a", "b", "c", "d")]
        with _entorno():
            control = ControlMusica(_frame(musica_aleatorio=True))
            control.reproducir_temas(temas, en_orden=True)
        self.assertEqual([t.origen for t in control.estado().cola],
                         [t.origen for t in temas])

    def test_reproducir_temas_desde_empieza_por_el_elegido(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B"),
                 Tema("C:/m/c.mp3", "C")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas_desde(temas, 2)
        self.assertEqual(control.estado().posicion, 2)
        cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
        self.assertEqual([c[1] for c in cargas], ["C:/m/a.mp3", "C:/m/c.mp3"])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0], "C")

    def test_agregar_temas_anuncia_en_plural(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_temas(temas)
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música", "2 temas agregados a la cola"])
        self.assertEqual([t.origen for t in control.estado().cola],
                         ["C:/m/a.mp3", "C:/m/b.mp3"])

    def test_agregar_temas_anuncia_en_singular(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_temas([Tema("C:/m/a.mp3", "A")])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "1 tema agregado a la cola")

    def test_agregar_temas_vacio_avisa_cola_vacia(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_temas([])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "No hay temas para reproducir")

    def test_reproducir_desde_salta_en_la_cola(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B"),
                 Tema("C:/m/c.mp3", "C")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas(temas)
            env.anunciar.reset_mock()
            control.reproducir_desde(2)
        self.assertEqual(control.estado().posicion, 2)
        env.anunciar.assert_called_once_with("C")

    def test_reproducir_desde_sin_cola_avisa(self):
        with _entorno() as env:
            ControlMusica(_frame()).reproducir_desde(0)
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "No hay temas para reproducir")


class TestVentanaYAtajos(unittest.TestCase):

    def test_registrar_y_olvidar_la_ventana(self):
        with _entorno():
            control = ControlMusica(_frame())
            ventana = mock.Mock()
            control.registrar_ventana(ventana)
            control._aviso_automatico(_aviso(posicion=0))
            ventana.refrescar_cola.assert_called_once_with()
            control.olvidar_ventana()
            control._aviso_automatico(_aviso(posicion=0))
            self.assertEqual(ventana.refrescar_cola.call_count, 1)

    def test_sin_ventana_no_refresca_nada(self):
        with _entorno():
            control = ControlMusica(_frame())
            control._aviso_automatico(_aviso(posicion=0))

    def test_una_ventana_que_falla_no_rompe_el_aviso(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            ventana = mock.Mock()
            ventana.refrescar_cola.side_effect = RuntimeError("cerrada")
            control.registrar_ventana(ventana)
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_called_once_with("Tema 2")

    def test_combos_atajo_traduce_los_guardados(self):
        from ytchat.player import reproductor
        with _entorno():
            control = ControlMusica(_frame())
            combos = control.combos_atajo()
        self.assertEqual(combos[reproductor._combo_wx("ctrl+alt+space")],
                         "musica_play")
        self.assertEqual(combos[reproductor._combo_wx("ctrl+alt+right")],
                         "musica_siguiente")

    def test_ejecutar_atajo_llama_a_la_accion(self):
        with _entorno():
            control = ControlMusica(_frame())
            control.que_suena = mock.Mock()
            control.ejecutar_atajo("musica_que_suena")
        control.que_suena.assert_called_once_with()

    def test_ejecutar_atajo_desconocido_no_hace_nada(self):
        with _entorno():
            control = ControlMusica(_frame())
            control.ejecutar_atajo("no_existe")   # no debe lanzar


class TestEnlace(unittest.TestCase):
    """`agregar_enlace`: expande en un hilo y suma los temas a la cola."""

    def test_expande_y_suma_los_temas_a_la_cola(self):
        temas = (Tema("https://www.youtube.com/watch?v=uno", "Uno"),
                 Tema("https://www.youtube.com/watch?v=dos", "Dos"))
        with _entorno() as env, \
                mock.patch.object(gui_musica.enlaces, "expandir",
                                  return_value=temas):
            control = ControlMusica(_frame())
            control.agregar_enlace("https://www.youtube.com/playlist?list=PL1")
        self.assertEqual([t.origen for t in control.estado().cola],
                         [t.origen for t in temas])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "2 temas agregados a la cola")

    def test_error_del_enlace_avisa_con_sonido(self):
        from ytchat.music.enlaces import ErrorEnlace
        with _entorno() as env, \
                mock.patch.object(gui_musica.enlaces, "expandir",
                                  side_effect=ErrorEnlace("El enlace no tiene vídeos")):
            control = ControlMusica(_frame())
            control.agregar_enlace("https://youtu.be/x")
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "El enlace no tiene vídeos")
        self.assertEqual(env.snd.sonidos, ["error"])

    def test_error_inesperado_avisa_lo_mismo(self):
        with _entorno() as env, \
                mock.patch.object(gui_musica.enlaces, "expandir",
                                  side_effect=RuntimeError("boom")), \
                mock.patch.object(gui_musica.logger, "exception"):
            control = ControlMusica(_frame())
            control.agregar_enlace("https://youtu.be/x")
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "No se pudo leer el enlace")
        self.assertEqual(env.snd.sonidos, ["error"])


class TestSnapshotMusica(unittest.TestCase):
    """El estado de la música entra en la instantánea de F2."""

    def _frame(self):
        from tests.test_desfase_accesible import _frame_con_panel
        return _frame_con_panel("En el directo", 0)

    def test_la_musica_llega_a_la_instantanea(self):
        from ytchat.ui import gui
        frame = self._frame()
        frame._musica = mock.Mock()
        frame._musica.texto_estado.return_value = "Música: A, tema 1 de 2"
        snap = gui.YTChatFrame._snapshot_sesion(frame)
        self.assertEqual(snap.musica, "Música: A, tema 1 de 2")

    def test_sin_motor_o_con_fallo_da_vacio(self):
        from ytchat.ui import gui
        frame = self._frame()
        frame._musica = mock.Mock()
        frame._musica.texto_estado.side_effect = RuntimeError("boom")
        snap = gui.YTChatFrame._snapshot_sesion(frame)
        self.assertEqual(snap.musica, "")


def _estado_memoria(temas, posicion):
    return EstadoMusica(tuple(temas), posicion, False, False, 100, False)


class TestTextoEstado(unittest.TestCase):

    def test_sin_motor_da_vacio(self):
        with _entorno():
            control = ControlMusica(_frame())
        self.assertEqual(control.texto_estado(), "")

    def test_refleja_el_tema_la_pausa_y_el_final(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno():
            control = ControlMusica(_frame())
            control.reproducir_temas(temas, en_orden=True)
            self.assertEqual(control.texto_estado(), "Música: A, tema 1 de 2")
            control.siguiente()
            self.assertEqual(control.texto_estado(), "Música: B, tema 2 de 2")
            control.reproducir_o_pausar()
            self.assertEqual(control.texto_estado(),
                             "Música en pausa: B, tema 2 de 2")
            control.detener()
        self.assertEqual(control.texto_estado(), "")

    def test_incluye_el_artista_si_esta_marcado(self):
        temas = [Tema("C:/m/a.mp3", "A", artista="Ana")]
        with _entorno():
            control = ControlMusica(_frame(musica_incluir_artista=True))
            control.reproducir_temas(temas)
        self.assertEqual(control.texto_estado(), "Música: A, de Ana, tema 1 de 1")


class TestGuardarMemoria(unittest.TestCase):

    def _temas_reales(self, tmp, nombres=("a.mp3", "b.mp3")):
        temas = []
        for n in nombres:
            ruta = Path(tmp) / n
            ruta.write_bytes(b"")
            temas.append(Tema(str(ruta.resolve()), n))
        return temas

    def test_guarda_tras_reproducir_y_tras_siguiente(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp)
            with _entorno() as env:
                control = ControlMusica(_frame())
                control.reproducir_temas(temas, en_orden=True)
                vivos, posicion = memoria.leer(env.memoria)
                self.assertEqual([t.origen for t in vivos],
                                 [t.origen for t in temas])
                self.assertEqual(posicion, 0)
                control.siguiente()
                vivos, posicion = memoria.leer(env.memoria)
                self.assertEqual(posicion, 1)

    def test_guarda_tras_aviso_automatico(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp)
            with _entorno() as env:
                control = ControlMusica(_frame())
                control.reproducir_temas(temas, en_orden=True)
                env.memoria.unlink()
                control._aviso_automatico(_aviso(posicion=1, cola=temas))
                self.assertTrue(env.memoria.exists())

    def test_detener_borra_la_memoria(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas([Tema("C:/m/a.mp3", "A")])
            self.assertTrue(env.memoria.exists())
            control.detener()
            self.assertFalse(env.memoria.exists())

    def test_con_retomar_apagado_no_guarda_y_borra(self):
        with _entorno() as env:
            env.memoria.write_text("{}", encoding="utf-8")
            ControlMusica(_frame(musica_retomar=False)).reproducir_temas(
                [Tema("C:/m/a.mp3", "A")])
            self.assertFalse(env.memoria.exists())


class TestRetomar(unittest.TestCase):

    def _carpeta_con(self, tmp, nombre):
        carpeta = Path(tmp) / "carpeta"
        carpeta.mkdir(exist_ok=True)
        (carpeta / nombre).write_bytes(b"")
        return carpeta

    def test_retoma_una_sola_vez_y_despues_la_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.mp3"
            b = Path(tmp) / "b.mp3"
            a.write_bytes(b"")
            b.write_bytes(b"")
            carpeta = self._carpeta_con(tmp, "z.mp3")
            temas = [Tema(str(a.resolve()), "A"), Tema(str(b.resolve()), "B")]
            with _entorno() as env:
                memoria.guardar(env.memoria, _estado_memoria(temas, 1))
                control = ControlMusica(_frame(musica_carpeta=str(carpeta)))
                control.reproducir_o_pausar()
                cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
                textos = [c.args[0] for c in env.anunciar.call_args_list]
                self.assertEqual([c[1] for c in cargas],
                                 [str(a.resolve()), str(b.resolve())])
                self.assertIn("Retomando: B", textos)
                control.detener()
                env.anunciar.reset_mock()
                control.reproducir_o_pausar()
                cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
                textos = [c.args[0] for c in env.anunciar.call_args_list]
                self.assertEqual(cargas[-1][1],
                                 str((carpeta / "z.mp3").resolve()))
                self.assertNotIn("Retomando: B", textos)

    def test_sin_memoria_reproduce_la_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            with _entorno() as env:
                ControlMusica(_frame(musica_carpeta=tmp)).reproducir_o_pausar()
                textos = [c.args[0] for c in env.anunciar.call_args_list]
        self.assertEqual(textos, ["Preparando la música", "a"])
        self.assertNotIn("Retomando", " ".join(textos))

    def test_con_retomar_apagado_no_retoma(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.mp3"
            a.write_bytes(b"")
            carpeta = self._carpeta_con(tmp, "z.mp3")
            with _entorno() as env:
                memoria.guardar(env.memoria,
                                _estado_memoria([Tema(str(a.resolve()), "A")], 0))
                control = ControlMusica(_frame(musica_carpeta=str(carpeta),
                                               musica_retomar=False))
                control.reproducir_o_pausar()
                cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
                textos = [c.args[0] for c in env.anunciar.call_args_list]
        self.assertEqual(cargas[0][1], str((carpeta / "z.mp3").resolve()))
        self.assertNotIn("Retomando: A", textos)


class _Evento:
    """Doble mínimo de un evento de teclado de wx."""

    def __init__(self, keycode=0, mods=0):
        self._keycode = keycode
        self._mods = mods
        self.skipped = False

    def GetKeyCode(self):
        return self._keycode

    def GetModifiers(self):
        return self._mods

    def Skip(self):
        self.skipped = True


class TestListasGuardadas(unittest.TestCase):

    def test_abrir_listas_llama_a_la_ventana(self):
        from ytchat.ui import gui_musica_listas
        with _entorno(), mock.patch.object(
                gui_musica_listas, "abrir_ventana") as abrir:
            control = ControlMusica(_frame())
            control.abrir_listas()
        abrir.assert_called_once_with(control)

    def test_reproducir_lista_guardada_carga_y_reproduce(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "listas"
            sonoro = Path(tmp) / "a.mp3"
            sonoro.write_bytes(b"")
            listas.guardar(carpeta, "Mía", (Tema(str(sonoro.resolve()), "A"),))
            with _entorno() as env, \
                    mock.patch.object(gui_musica.paths, "listas_musica",
                                      return_value=carpeta):
                control = ControlMusica(_frame())
                control.reproducir_lista_guardada("Mía")
        cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
        self.assertEqual(cargas[0][1], str(sonoro.resolve()))
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música", "A"])

    def test_reproducir_lista_guardada_avisa_las_saltadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "listas"
            sonoro = Path(tmp) / "a.mp3"
            sonoro.write_bytes(b"")
            listas.crear(carpeta, "Mezcla")
            (carpeta / "Mezcla.m3u8").write_text(
                "#EXTM3U\n#EXTINF:-1,A\n"
                f"{sonoro.resolve()}\nno-existe.mp3\n", encoding="utf-8")
            with _entorno() as env, \
                    mock.patch.object(gui_musica.paths, "listas_musica",
                                      return_value=carpeta):
                ControlMusica(_frame()).reproducir_lista_guardada("Mezcla")
        self.assertEqual(env.anunciar.call_args_list[0].args[0],
                         "Se saltó 1 entrada que no se pudo leer")

    def test_reproducir_lista_inexistente_avisa_con_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "listas"
            with _entorno() as env, \
                    mock.patch.object(gui_musica.paths, "listas_musica",
                                      return_value=carpeta):
                ControlMusica(_frame()).reproducir_lista_guardada("No está")
        self.assertEqual(env.snd.sonidos, ["error"])
        self.assertIn("No existe la lista",
                      env.anunciar.call_args_list[0].args[0])

    def test_cola_actual_sin_motor_vacia(self):
        with _entorno():
            self.assertEqual(ControlMusica(_frame()).cola_actual(), ())

    def test_cola_actual_devuelve_los_temas(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno():
            control = ControlMusica(_frame())
            control.reproducir_temas(temas)
        self.assertEqual([t.origen for t in control.cola_actual()],
                         ["C:/m/a.mp3", "C:/m/b.mp3"])


class TestAtajoDeTeclaComun(unittest.TestCase):

    def test_manejar_atajo_despacha_la_accion(self):
        control = mock.Mock()
        combos = {(gui_musica.wx.MOD_CONTROL | gui_musica.wx.MOD_ALT,
                   ord("T")): "musica_que_suena"}
        evento = _Evento(ord("T"),
                         gui_musica.wx.MOD_CONTROL | gui_musica.wx.MOD_ALT)
        self.assertTrue(
            gui_musica.manejar_atajo_de_tecla(control, combos, evento))
        control.ejecutar_atajo.assert_called_once_with("musica_que_suena")

    def test_manejar_atajo_ignora_lo_que_no_es_atajo(self):
        control = mock.Mock()
        evento = _Evento(gui_musica.wx.WXK_TAB)
        self.assertFalse(
            gui_musica.manejar_atajo_de_tecla(control, {}, evento))
        control.ejecutar_atajo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
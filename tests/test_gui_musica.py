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

from ytchat.music.modelo import AVANZO, FIN_LISTA, TEMA_FALLIDO, Resultado
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
    """Dobla el motor, los hilos, CallAfter, el lector y los sonidos."""
    snd = _SndFalso()
    creados = []

    def fabrica_por_defecto(**kwargs):
        adaptador = _AdaptadorFalso(**kwargs)
        creados.append(adaptador)
        return adaptador

    fabrica = fabrica or fabrica_por_defecto
    with mock.patch.object(gui_musica, "AdaptadorVlc", side_effect=fabrica), \
            mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                              _crear_hilo_inmediato), \
            mock.patch.object(gui_musica.wx, "CallAfter",
                              side_effect=lambda fn, *a: fn(*a)), \
            mock.patch.object(gui_musica, "anunciar") as anunciar, \
            mock.patch.object(gui_musica, "_snd", snd):
        yield SimpleNamespace(anunciar=anunciar, snd=snd, creados=creados)


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


if __name__ == "__main__":
    unittest.main()

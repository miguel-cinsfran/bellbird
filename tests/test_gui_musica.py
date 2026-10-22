"""Pruebas de la lógica pura y del control de música, sin ventanas reales.

`ControlMusica` se prueba con un frame falso, `wx.CallAfter` reemplazado por
una llamada directa, un adaptador falso y `diagnostico.crear_hilo` corriendo
en el acto. En ningún caso se crea `wx.App`, ni se abre una ventana, ni suena
nada: el motor de VLC queda reemplazado por un doble.
"""

import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ytchat.music import anuncios
from ytchat.music import listas
from ytchat.music import memoria
from ytchat.music.modelo import (AVANZO, FIN_LISTA, REINICIADO, TEMA_FALLIDO,
                                 EstadoMusica, Resultado, Tema)
from ytchat.ui import atajos_globales
from ytchat.ui import gui_musica
from ytchat.ui import musica_enlaces
from ytchat.ui import musica_indice
from ytchat.ui import musica_listas_propias
from ytchat.ui import musica_memoria
from ytchat.ui import musica_ventana
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


class _TemporizadorFalso:
    """Temporizador de `wx.CallLater` que solo corre cuando se le pide."""

    def __init__(self, ms, funcion):
        self.ms = ms
        self.funcion = funcion
        self.vivo = True

    def Stop(self):
        self.vivo = False


class _ProgramadorFalso:
    """Doble de `wx.CallLater`: acumula lo programado y lo dispara a mano."""

    def __init__(self):
        self.temporizadores = []

    def __call__(self, ms, funcion):
        temporizador = _TemporizadorFalso(ms, funcion)
        self.temporizadores.append(temporizador)
        return temporizador

    def disparar(self):
        vivos = [t for t in self.temporizadores if t.vivo]
        self.temporizadores = []
        for temporizador in vivos:
            temporizador.vivo = False
            temporizador.funcion()


def _frame(**config):
    base = {
        "musica_carpeta": "", "musica_aleatorio": False, "musica_repetir": False,
        "musica_sonido_tema": True, "musica_decir": "titulo",
        "musica_decir_pausa": True, "musica_volumen": 50,
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
    programador = _ProgramadorFalso()

    def fabrica_por_defecto(**kwargs):
        adaptador = _AdaptadorFalso(**kwargs)
        creados.append(adaptador)
        return adaptador

    fabrica = fabrica or fabrica_por_defecto
    with tempfile.TemporaryDirectory() as tmp:
        ruta_memoria = Path(tmp) / "musica_estado.json"
        ruta_cache = Path(tmp) / "etiquetas_musica.json"
        ruta_sonoridad = Path(tmp) / "sonoridad_musica.json"
        with mock.patch.object(gui_musica, "AdaptadorVlc", side_effect=fabrica), \
                mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                   _crear_hilo_inmediato), \
                mock.patch.object(gui_musica.wx, "CallAfter",
                                   side_effect=lambda fn, *a: fn(*a)), \
                mock.patch.object(gui_musica.wx, "CallLater", programador), \
                mock.patch.object(gui_musica.anuncio_ajuste, "COMPARTIDO",
                                   gui_musica.anuncio_ajuste.AnuncioAjuste()), \
                mock.patch.object(gui_musica, "anunciar") as anunciar, \
                mock.patch.object(musica_memoria.paths, "estado_musica",
                                   return_value=ruta_memoria), \
                mock.patch.object(musica_indice.paths, "cache_etiquetas_musica",
                                   return_value=ruta_cache), \
                mock.patch.object(musica_indice.paths, "cache_sonoridad_musica",
                                   return_value=ruta_sonoridad), \
                mock.patch("ytchat.downloads.ffmpeg_bin.ruta_ffmpeg",
                           return_value=None), \
                mock.patch.object(gui_musica, "_snd", snd):
            yield SimpleNamespace(anunciar=anunciar, snd=snd, creados=creados,
                                    memoria=ruta_memoria, cache=ruta_cache,
                                    sonoridad=ruta_sonoridad,
                                    programador=programador)


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

    def test_que_suena_con_nada_dice_todo(self):
        temas = [Tema("C:/m/a.mp3", "A", artista="Ana")]
        with _entorno() as env:
            control = ControlMusica(_frame(musica_decir="nada"))
            control.reproducir_temas(temas)
            env.anunciar.reset_mock()
            control.que_suena()
        env.anunciar.assert_called_once_with("Sonando: A, de Ana. Canción 1 de 1")

    def test_siguiente_manual_con_nada_dice_el_titulo(self):
        temas = [Tema("C:/m/a.mp3", "A", artista="Ana"),
                 Tema("C:/m/b.mp3", "B", artista="Beto")]
        with _entorno() as env:
            control = ControlMusica(_frame(musica_decir="nada"))
            control.reproducir_temas(temas)
            env.anunciar.reset_mock()
            env.snd.sonidos.clear()
            control.siguiente()
        env.anunciar.assert_called_once_with("B")
        self.assertEqual(env.snd.sonidos, [])

    def test_pausa_con_decir_pausa_en_falso_calla(self):
        temas = [Tema("C:/m/a.mp3", "A")]
        with _entorno() as env:
            control = ControlMusica(_frame(musica_decir_pausa=False))
            control.reproducir_temas(temas)
            env.anunciar.reset_mock()
            env.snd.sonidos.clear()
            control.reproducir_o_pausar()
        env.anunciar.assert_not_called()
        self.assertEqual(env.snd.sonidos, [])


class TestAnteriorReiniciado(unittest.TestCase):

    def test_anterior_reiniciado_anuncia_desde_el_comienzo(self):
        resultado = Resultado(True, REINICIADO, _estado(actual=True))
        with _entorno() as env:
            control = ControlMusica(_frame())
            control._coordinador = mock.Mock()
            control._coordinador.anterior.return_value = resultado
            control.anterior()
        env.anunciar.assert_called_once_with("Desde el comienzo")
        self.assertEqual(env.snd.sonidos, [])


class TestVolumen(unittest.TestCase):

    def test_subir_en_el_limite_superior_guarda_igual(self):
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            frame = _frame(musica_volumen=100)
            ControlMusica(frame).subir_volumen()
            env.programador.disparar()
        self.assertEqual(frame._config["musica_volumen"], 100)
        guardar.assert_called_once_with("volumen", "100")
        env.anunciar.assert_called_once_with("Volumen de la música: 100")

    def test_bajar_en_el_limite_inferior_guarda_igual(self):
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            frame = _frame(musica_volumen=0)
            ControlMusica(frame).bajar_volumen()
            env.programador.disparar()
        self.assertEqual(frame._config["musica_volumen"], 0)
        guardar.assert_called_once_with("volumen", "0")
        env.anunciar.assert_called_once_with("Volumen de la música: 0")

    def test_paso_intermedio(self):
        with _entorno() as env, mock.patch.object(ControlMusica, "_guardar"):
            frame = _frame(musica_volumen=40)
            ControlMusica(frame).subir_volumen()
            env.programador.disparar()
        self.assertEqual(frame._config["musica_volumen"], 50)

    def test_tres_cambios_anuncian_completo_y_dos_numeros_y_guardan_el_ultimo(self):
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            frame = _frame(musica_volumen=40)
            control = ControlMusica(frame)
            control.subir_volumen()
            control.bajar_volumen()
            control.subir_volumen()
            self.assertEqual(
                [c.args[0] for c in env.anunciar.call_args_list],
                ["Volumen de la música: 50", "40", "50"])
            guardar.assert_not_called()
            env.programador.disparar()
        guardar.assert_called_once_with("volumen", "50")

    def test_cerrar_con_volumen_pendiente_lo_escribe(self):
        with _entorno(), \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            control = ControlMusica(_frame(musica_volumen=40))
            control.subir_volumen()
            guardar.assert_not_called()
            control.cerrar()
        guardar.assert_called_once_with("volumen", "50")


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

    def test_aviso_automatico_respeta_modo_y_sonido(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=True, musica_decir="titulo_artista"))
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_called_once_with("Tema 2, de Ana")
        self.assertEqual(env.snd.sonidos, ["musica_tema"])

    def test_aviso_automatico_con_nada_solo_sonido(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=True, musica_decir="nada"))
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_not_called()
        self.assertEqual(env.snd.sonidos, ["musica_tema"])

    def test_aviso_automatico_con_nada_y_sin_sonido_no_hace_nada(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=False, musica_decir="nada"))
            control._aviso_automatico(_aviso(posicion=0))
        env.anunciar.assert_not_called()
        self.assertEqual(env.snd.sonidos, [])

    def test_aviso_automatico_fin_de_lista_suena_siempre(self):
        with _entorno() as env:
            control = ControlMusica(_frame(
                musica_sonido_tema=False, musica_decir="nada"))
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
        control._coordinador.fijar_repetir.assert_called_once_with("todo")
        item.Check.assert_called_once_with(True)
        env.anunciar.assert_not_called()

    def test_con_silencio_aplica_volumen_y_despues_vuelve_a_silenciar(self):
        frame = _frame(musica_volumen=30)
        with _entorno():
            control = ControlMusica(frame)
            coordinador = mock.Mock()
            coordinador.silenciado = True
            control._coordinador = coordinador
            control._adaptador = mock.Mock()
            control.aplicar_preferencias()
        self.assertEqual(coordinador.mock_calls[:2], [
            mock.call.fijar_volumen(30),
            mock.call.fijar_silencio(True),
        ])

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


class TestVigiaMusica(unittest.TestCase):
    """El vigía arranca al indexar y se para al cambiar de carpeta o cerrar."""

    def _vigias_falsos(self, creados):
        def fabrica(carpeta, al_cambiar, espera_s=2.0):
            vigia = mock.Mock()
            vigia.carpeta = carpeta
            vigia.al_cambiar = al_cambiar
            creados.append(vigia)
            return vigia

        return mock.patch.object(musica_indice, "VigiaCarpeta",
                                 side_effect=fabrica)

    def test_indexar_arranca_un_vigia_para_esa_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            creados = []
            with _entorno(), self._vigias_falsos(creados):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
        self.assertEqual(len(creados), 1)
        self.assertEqual(creados[0].carpeta, tmp)
        creados[0].arrancar.assert_called_once_with()
        self.assertIs(control._vigia_musica, creados[0])
        self.assertEqual(len(recibidas[0].temas()), 1)

    def test_cambiar_carpeta_para_el_vigia_viejo(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            creados = []
            with _entorno(), self._vigias_falsos(creados), \
                    mock.patch.object(ControlMusica, "_guardar"):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.biblioteca(lambda _b: None)
                viejo = creados[0]
                control.cambiar_carpeta(str(Path(tmp) / "otra"))
        viejo.parar.assert_called_once_with()
        self.assertIsNone(control._vigia_musica)

    def test_cerrar_para_el_vigia(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            creados = []
            with _entorno(), self._vigias_falsos(creados):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control.biblioteca(lambda _b: None)
                control.cerrar()
        creados[0].parar.assert_called_once_with()

    def test_el_aviso_del_vigia_cambia_la_biblioteca_y_avisa_a_la_ventana(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            creados = []
            ventana = mock.Mock()
            with _entorno(), self._vigias_falsos(creados), \
                    mock.patch.object(musica_indice.motor_vlc,
                                       "disponible", return_value=False):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
                control.registrar_ventana(ventana)
                nuevo = Path(tmp) / "nuevo.mp3"
                nuevo.write_bytes(b"")
                creados[0].al_cambiar({str(nuevo)}, set())
        nombres = [Path(t.origen).name for t in recibidas[0].temas()]
        self.assertEqual(nombres, ["a.mp3", "nuevo.mp3"])
        ventana.refrescar_por_vigia.assert_called_once_with()

    def test_el_aviso_no_toca_nada_si_la_carpeta_cambio(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp3").write_bytes(b"")
            creados = []
            with _entorno(), self._vigias_falsos(creados), \
                    mock.patch.object(ControlMusica, "_guardar"):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
                avisar = creados[0].al_cambiar
                vieja = recibidas[0]
                control.cambiar_carpeta(str(Path(tmp) / "otra"))
                nuevo = Path(tmp) / "nuevo.mp3"
                nuevo.write_bytes(b"")
                avisar({str(nuevo)}, set())
        self.assertEqual(len(vieja.temas()), 1)


class TestEtiquetasSegundoPlano(unittest.TestCase):
    """El hilo «musica-etiquetas»: lee lo pendiente, guarda y aplica el lote."""

    def _carpeta_con(self, tmp, nombres=("a.mp3", "b.mp3")):
        for nombre in nombres:
            (Path(tmp) / nombre).write_bytes(b"audio-" + nombre.encode())
        return tmp

    def test_lee_guarda_y_aplica_al_coordinador_y_la_ventana(self):
        from ytchat.music.etiquetas import CacheEtiquetas

        with tempfile.TemporaryDirectory() as tmp:
            self._carpeta_con(tmp)
            with _entorno() as env, \
                    mock.patch.object(musica_indice.motor_vlc, "disponible",
                                      return_value=True), \
                    mock.patch.object(
                        musica_indice, "leer_etiquetas_vlc",
                        return_value={"titulo": "Tema", "artista": "Ana",
                                      "album": "Disco", "duracion_ms": 1000}):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control._coordinador = mock.Mock()
                ventana = mock.Mock()
                control.registrar_ventana(ventana)
                recibidas = []
                control.biblioteca(recibidas.append)
                biblioteca = recibidas[0]
                por_nombre = {Path(t.origen).name: t
                              for t in biblioteca.temas()}
                self.assertEqual(por_nombre["a.mp3"].titulo, "Tema")
                self.assertEqual(por_nombre["a.mp3"].artista, "Ana")
                control._coordinador.actualizar_temas.assert_called_once()
                ventana.actualizar_nombres.assert_called_once()
                mapa = control._coordinador.actualizar_temas.call_args.args[0]
                self.assertEqual(
                    set(mapa), {t.origen for t in biblioteca.temas()})
                self.assertIs(
                    ventana.actualizar_nombres.call_args.args[0], mapa)
                self.assertTrue(env.cache.is_file())
                releida = CacheEtiquetas(env.cache)
                for tema in biblioteca.temas():
                    info = os.stat(tema.origen)
                    self.assertEqual(
                        releida.buscar(
                            tema.origen, info.st_mtime_ns,
                            info.st_size)["titulo"],
                        "Tema")
                env.anunciar.assert_not_called()

    def test_con_cache_en_disco_no_lee_ni_arranca_hilo(self):
        from ytchat.music.etiquetas import CacheEtiquetas

        hilos = []

        def crear_hilo(target, nombre, *, args=(), daemon=True):
            hilos.append(nombre)
            return _HiloInmediato(target, args)

        with tempfile.TemporaryDirectory() as tmp:
            self._carpeta_con(tmp)
            with _entorno() as env, \
                    mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                      crear_hilo), \
                    mock.patch.object(musica_indice.motor_vlc, "disponible",
                                      return_value=True), \
                    mock.patch.object(
                        musica_indice, "leer_etiquetas_vlc",
                        side_effect=AssertionError("no debe leer")):
                previa = CacheEtiquetas(env.cache)
                for nombre in ("a.mp3", "b.mp3"):
                    ruta = Path(tmp) / nombre
                    info = os.stat(ruta)
                    previa.poner(str(ruta.resolve()), info.st_mtime_ns,
                                 info.st_size,
                                 {"titulo": "Tema", "artista": "Ana",
                                  "duracion_ms": 1000})
                previa.guardar()
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
                biblioteca = recibidas[0]
                por_nombre = {Path(t.origen).name: t
                              for t in biblioteca.temas()}
                self.assertEqual(por_nombre["a.mp3"].titulo, "Tema")
                self.assertEqual(por_nombre["a.mp3"].artista, "Ana")
                self.assertEqual(por_nombre["b.mp3"].titulo, "Tema")
                self.assertEqual(por_nombre["b.mp3"].artista, "Ana")
        self.assertIn("musica-indice", hilos)
        self.assertNotIn("musica-etiquetas", hilos)

    def test_titulo_vacio_conserva_el_nombre_del_archivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._carpeta_con(tmp, ("a.mp3",))
            with _entorno(), \
                    mock.patch.object(musica_indice.motor_vlc, "disponible",
                                      return_value=True), \
                    mock.patch.object(
                        musica_indice, "leer_etiquetas_vlc",
                        return_value={"titulo": "", "artista": "Ana"}):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
        tema = recibidas[0].temas()[0]
        self.assertEqual(tema.titulo, "a")
        self.assertEqual(tema.artista, "Ana")

    def test_cada_50_archivos_guarda_y_aplica(self):
        nombres = tuple(f"t{i:03d}.mp3" for i in range(55))
        with tempfile.TemporaryDirectory() as tmp:
            self._carpeta_con(tmp, nombres)
            with _entorno(), \
                    mock.patch.object(musica_indice.motor_vlc, "disponible",
                                      return_value=True), \
                    mock.patch.object(musica_indice, "leer_etiquetas_vlc",
                                      return_value={"titulo": "T"}):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control._coordinador = mock.Mock()
                control.biblioteca(lambda _b: None)
        self.assertEqual(control._coordinador.actualizar_temas.call_count, 2)
        titulos = {t.titulo for t in control._biblioteca.temas()}
        self.assertEqual(titulos, {"T"})

    def test_si_la_generacion_cambia_a_mitad_no_aplica_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._carpeta_con(tmp, ("a.mp3",))
            with _entorno(), \
                    mock.patch.object(musica_indice.motor_vlc, "disponible",
                                      return_value=True):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                control._coordinador = mock.Mock()
                ventana = mock.Mock()
                control.registrar_ventana(ventana)

                def leer_y_cambiar(_origen, **_kw):
                    control._generacion_etiquetas += 1
                    return {"titulo": "Tema"}

                with mock.patch.object(musica_indice, "leer_etiquetas_vlc",
                                       side_effect=leer_y_cambiar):
                    recibidas = []
                    control.biblioteca(recibidas.append)
        self.assertEqual(recibidas[0].temas()[0].titulo, "a")
        control._coordinador.actualizar_temas.assert_not_called()
        ventana.actualizar_nombres.assert_not_called()

    def test_sin_motor_no_arranca_el_hilo(self):
        hilos = []

        def crear_hilo(target, nombre, *, args=(), daemon=True):
            hilos.append(nombre)
            return _HiloInmediato(target, args)

        with tempfile.TemporaryDirectory() as tmp:
            self._carpeta_con(tmp)
            with _entorno(), \
                    mock.patch.object(gui_musica.diagnostico, "crear_hilo",
                                      crear_hilo), \
                    mock.patch.object(musica_indice.motor_vlc, "disponible",
                                      return_value=False):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
        self.assertIn("musica-indice", hilos)
        self.assertNotIn("musica-etiquetas", hilos)
        self.assertEqual(recibidas[0].temas()[0].titulo, "a")


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
        self.assertEqual([c[1] for c in cargas], ["C:/m/c.mp3"])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0], "C")

    def test_agregar_temas_anuncia_en_plural(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_temas(temas)
        self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                         ["Preparando la música",
                          "2 canciones agregadas a la cola. Sonando: A"])
        self.assertEqual([t.origen for t in control.estado().cola],
                         ["C:/m/a.mp3", "C:/m/b.mp3"])

    def test_agregar_temas_anuncia_en_singular(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_temas([Tema("C:/m/a.mp3", "A")])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "Agregado a la cola, posición 1. Sonando: A")

    def test_agregar_temas_con_musica_sonando_no_dice_lo_que_suena(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas(temas, en_orden=True)
            env.anunciar.reset_mock()
            control.agregar_temas([Tema("C:/m/c.mp3", "C")])
        env.anunciar.assert_called_once_with(
            "Agregado a la cola, posición 3")

    def test_agregar_temas_vacio_avisa_cola_vacia(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_temas([])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "No hay canciones para reproducir")

    def test_iniciar_lista_desde_carga_solo_el_elegido(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B"),
                 Tema("C:/m/c.mp3", "C"), Tema("C:/m/d.mp3", "D")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas(temas, en_orden=True)
            env.creados[0].llamadas.clear()
            control._iniciar_lista_desde(temas, 3)
        cargas = [l for l in env.creados[0].llamadas if l[0] == "cargar"]
        self.assertEqual([c[1] for c in cargas], ["C:/m/d.mp3"])

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
                         "No hay canciones para reproducir")

    def test_reproducir_a_continuacion_anuncia_y_mete_detras(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/c.mp3", "C")]
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas(temas)
            env.anunciar.reset_mock()
            control.reproducir_a_continuacion(Tema("C:/m/b.mp3", "B"))
        env.anunciar.assert_called_once_with("A continuación: B")
        self.assertEqual(env.snd.sonidos, [])
        self.assertEqual([t.origen for t in control.estado().cola],
                         ["C:/m/a.mp3", "C:/m/b.mp3", "C:/m/c.mp3"])


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


class _VentanaFalsa:
    """Ventana de música falsa: cuenta cuántas veces se refresca la cola.

    Guarda cuántos temas tenía la cola en cada llamada, para comprobar
    que el refresco llega DESPUÉS de que el coordinador ya la cambió.
    """

    def __init__(self, control):
        self._control = control
        self.llamadas = 0
        self.tamanos = []

    def refrescar_cola(self):
        self.llamadas += 1
        estado = self._control.estado()
        self.tamanos.append(len(estado.cola) if estado is not None else 0)


class TestRefrescaVentanaAbierta(unittest.TestCase):
    """Cada acción deja la cola de la ventana abierta al día."""

    def test_primera_accion_sin_motor_refresca_con_la_cola_llena(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno():
            control = ControlMusica(_frame())
            ventana = _VentanaFalsa(control)
            control.registrar_ventana(ventana)
            control.reproducir_temas(temas)
        self.assertGreaterEqual(ventana.llamadas, 1)
        self.assertGreater(ventana.tamanos[-1], 0)

    def test_siguiente_anterior_pausa_y_detener_refrescan(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno():
            control = ControlMusica(_frame())
            ventana = _VentanaFalsa(control)
            control.registrar_ventana(ventana)
            control.reproducir_temas(temas, en_orden=True)
            for accion in (control.siguiente, control.anterior,
                           control.reproducir_o_pausar, control.detener):
                ventana.llamadas = 0
                accion()
                self.assertGreaterEqual(
                    ventana.llamadas, 1, f"{accion.__name__} no refrescó")

    def test_siguiente_con_ventana_abierta_refresca_una_sola_vez(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno():
            control = ControlMusica(_frame())
            ventana = _VentanaFalsa(control)
            control.registrar_ventana(ventana)
            control.reproducir_temas(temas, en_orden=True)
            ventana.llamadas = 0
            control.siguiente()
        self.assertEqual(ventana.llamadas, 1)

    def test_sin_ventana_abierta_no_pasa_nada(self):
        temas = [Tema("C:/m/a.mp3", "A"), Tema("C:/m/b.mp3", "B")]
        with _entorno():
            control = ControlMusica(_frame())
            control.reproducir_temas(temas, en_orden=True)
            control.siguiente()
            control.anterior()
            control.reproducir_o_pausar()
            control.detener()   # no debe lanzar
        self.assertIsNone(control.estado().posicion)


class TestEnlace(unittest.TestCase):
    """`agregar_enlace`: expande en un hilo y suma los temas a la cola."""

    def test_expande_y_suma_los_temas_a_la_cola(self):
        temas = (Tema("https://www.youtube.com/watch?v=uno", "Uno"),
                 Tema("https://www.youtube.com/watch?v=dos", "Dos"))
        with _entorno() as env, \
                mock.patch.object(musica_enlaces.enlaces, "expandir",
                                  return_value=temas):
            control = ControlMusica(_frame())
            control.agregar_enlace("https://www.youtube.com/playlist?list=PL1")
        self.assertEqual([t.origen for t in control.estado().cola],
                         [t.origen for t in temas])
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "2 canciones agregadas a la cola. Sonando: Uno")

    def test_error_del_enlace_avisa_con_sonido(self):
        from ytchat.music.enlaces import ErrorEnlace
        with _entorno() as env, \
                mock.patch.object(musica_enlaces.enlaces, "expandir",
                                  side_effect=ErrorEnlace("El enlace no tiene vídeos")):
            control = ControlMusica(_frame())
            control.agregar_enlace("https://youtu.be/x")
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "El enlace no tiene vídeos")
        self.assertEqual(env.snd.sonidos, ["error"])

    def test_error_inesperado_avisa_lo_mismo(self):
        with _entorno() as env, \
                mock.patch.object(musica_enlaces.enlaces, "expandir",
                                  side_effect=RuntimeError("boom")), \
                mock.patch.object(musica_enlaces.logger, "exception"):
            control = ControlMusica(_frame())
            control.agregar_enlace("https://youtu.be/x")
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "No se pudo leer el enlace")
        self.assertEqual(env.snd.sonidos, ["error"])


class TestOperacionesDeCola(unittest.TestCase):
    """Las operaciones nuevas de la cola llaman al coordinador y avisan."""

    @staticmethod
    def _temas(*titulos):
        return [Tema(f"C:/m/{titulo.lower()}.mp3", titulo) for titulo in titulos]

    def _con_cola(self, *titulos, **config):
        control = ControlMusica(_frame(**config))
        control.reproducir_temas(self._temas(*titulos), en_orden=True)
        return control

    def test_reproducir_ahora_mete_detras_y_suena_el_primero(self):
        with _entorno() as env:
            control = self._con_cola("A", "C")
            env.anunciar.reset_mock()
            control.reproducir_ahora(self._temas("B"))
            self.assertEqual([t.titulo for t in control.estado().cola],
                             ["A", "B", "C"])
            self.assertEqual([c.args[0] for c in env.anunciar.call_args_list],
                             ["B"])
        self.assertEqual(env.snd.sonidos, [])

    def test_poner_a_continuacion_uno_anuncia_posicion(self):
        with _entorno() as env:
            control = self._con_cola("A", "D")
            env.anunciar.reset_mock()
            control.poner_a_continuacion(self._temas("B"))
        env.anunciar.assert_called_once_with("A continuación: B, posición 2")
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["A", "B", "D"])
        self.assertEqual(env.snd.sonidos, [])

    def test_poner_a_continuacion_varios_desde_la_primera_posicion(self):
        with _entorno() as env:
            control = self._con_cola("A", "D")
            env.anunciar.reset_mock()
            control.poner_a_continuacion(self._temas("B"))
            control.poner_a_continuacion(self._temas("C", "E"))
            textos = [c.args[0] for c in env.anunciar.call_args_list]
        self.assertEqual(textos, [
            "A continuación: B, posición 2",
            "2 canciones a continuación, desde la posición 3"])
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["A", "B", "C", "E", "D"])

    def test_poner_a_continuacion_sin_nada_activo_empieza_a_sonar(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.poner_a_continuacion(self._temas("A"))
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "Agregado a la cola, posición 1. Sonando: A")
        self.assertEqual([t.titulo for t in control.estado().cola], ["A"])

    def test_agregar_al_final_uno_anuncia_posicion(self):
        with _entorno() as env:
            control = self._con_cola("A", "B")
            env.anunciar.reset_mock()
            control.agregar_al_final(self._temas("C"))
        env.anunciar.assert_called_once_with("Agregado a la cola, posición 3")
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["A", "B", "C"])

    def test_agregar_al_final_varios_usa_el_texto_de_siempre(self):
        with _entorno() as env:
            control = self._con_cola("A")
            env.anunciar.reset_mock()
            control.agregar_al_final(self._temas("B", "C"))
        env.anunciar.assert_called_once_with("2 canciones agregadas a la cola")
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["A", "B", "C"])

    def test_agregar_al_final_sin_nada_activo_empieza_a_sonar(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.agregar_al_final(self._temas("A"))
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "Agregado a la cola, posición 1. Sonando: A")
        self.assertEqual([t.titulo for t in control.estado().cola], ["A"])

    def test_reproducir_desde_aqui_reemplaza_la_cola(self):
        with _entorno() as env:
            control = self._con_cola("A", "B", "C")
            env.anunciar.reset_mock()
            control.reproducir_desde_aqui(self._temas("B", "C"), 1)
        self.assertEqual(env.anunciar.call_args_list[-1].args[0], "C")
        self.assertEqual([t.titulo for t in control.estado().cola], ["B", "C"])
        self.assertEqual(control.estado().posicion, 1)

    def test_quitar_uno_que_no_suena(self):
        with _entorno() as env:
            control = self._con_cola("A", "B", "C")
            env.anunciar.reset_mock()
            control.quitar_de_cola(2)
        env.anunciar.assert_called_once_with("Quitado de la cola: C")
        self.assertEqual([t.titulo for t in control.estado().cola], ["A", "B"])

    def test_quitar_el_que_suena_anuncia_tambien_el_nuevo(self):
        with _entorno() as env:
            control = self._con_cola("A", "B", "C")
            env.anunciar.reset_mock()
            control.quitar_de_cola(0)
        env.anunciar.assert_called_once_with("Quitado de la cola: A. B")
        self.assertEqual(control.estado().actual.titulo, "B")

    def test_quitar_el_unico_suena_fin_de_lista_sin_sonido(self):
        with _entorno() as env:
            control = self._con_cola("A")
            env.anunciar.reset_mock()
            control.quitar_de_cola(0)
        env.anunciar.assert_called_once_with("Fin de la lista de música")
        self.assertEqual(env.snd.sonidos, [])
        self.assertEqual(control.estado().cola, ())

    def test_mover_en_cola_anuncia_la_posicion_nueva(self):
        with _entorno() as env:
            control = self._con_cola("A", "B", "C")
            env.anunciar.reset_mock()
            control.mover_en_cola(0, 1)
        env.anunciar.assert_called_once_with(
            "Canción movida a la posición 2 de 3")
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["B", "A", "C"])

    def test_mover_en_el_borde_anuncia_la_misma_posicion(self):
        with _entorno() as env:
            control = self._con_cola("A", "B", "C")
            env.anunciar.reset_mock()
            control.mover_en_cola(0, -1)
        env.anunciar.assert_called_once_with(
            "Canción movida a la posición 1 de 3")
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["A", "B", "C"])

    def test_vaciar_deja_el_actual_y_lo_dice(self):
        with _entorno() as env:
            control = self._con_cola("A", "B")
            env.anunciar.reset_mock()
            control.vaciar_cola()
        env.anunciar.assert_called_once_with("Cola vaciada, sigue sonando A")
        self.assertEqual([t.titulo for t in control.estado().cola], ["A"])

    def test_vaciar_sin_nada_activo(self):
        with _entorno() as env:
            control = self._con_cola("A", "B")
            control.detener()
            env.anunciar.reset_mock()
            control.vaciar_cola()
        env.anunciar.assert_called_once_with("Cola vaciada")
        self.assertEqual(control.estado().cola, ())

    def test_mezclar_anuncia(self):
        with _entorno() as env:
            control = self._con_cola("A", "B", "C")
            env.anunciar.reset_mock()
            control.mezclar_cola()
        env.anunciar.assert_called_once_with("Cola mezclada")
        self.assertEqual(len(control.estado().cola), 3)


class TestRepetir(unittest.TestCase):

    def test_ciclar_recorre_los_tres_modos_guarda_y_anuncia(self):
        frame = _frame(musica_repetir="no")
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            control = ControlMusica(frame)
            control.ciclar_repetir()
            self.assertEqual(frame._config["musica_repetir"], "todo")
            control.ciclar_repetir()
            self.assertEqual(frame._config["musica_repetir"], "tema")
            control.ciclar_repetir()
            self.assertEqual(frame._config["musica_repetir"], "no")
        self.assertEqual(
            [c.args[0] for c in env.anunciar.call_args_list],
            ["Repetir: toda la cola", "Repetir: esta canción", "Repetir: no"])
        self.assertEqual(
            [c.args for c in guardar.call_args_list],
            [("repetir", "todo"), ("repetir", "tema"), ("repetir", "no")])

    def test_fijar_aplica_al_coordinador_si_hay_motor(self):
        frame = _frame(musica_repetir="no")
        with _entorno() as env, \
                mock.patch.object(ControlMusica, "_guardar") as guardar:
            control = ControlMusica(frame)
            control._coordinador = mock.Mock()
            control.fijar_repetir("tema")
        control._coordinador.fijar_repetir.assert_called_once_with("tema")
        guardar.assert_called_once_with("repetir", "tema")
        env.anunciar.assert_called_once_with("Repetir: esta canción")


class TestAbrirEnlace(unittest.TestCase):
    """`abrir_enlace`: valida, expande en un hilo y aplica el modo pedido."""

    TEMAS = (Tema("https://www.youtube.com/watch?v=uno", "Uno"),
             Tema("https://www.youtube.com/watch?v=dos", "Dos"))

    def _con_cola(self, *titulos):
        control = ControlMusica(_frame())
        control.reproducir_temas(
            [Tema(f"C:/m/{t.lower()}.mp3", t) for t in titulos], en_orden=True)
        return control

    def _abrir(self, modo):
        with _entorno() as env, \
                mock.patch.object(musica_enlaces.enlaces, "expandir",
                                  return_value=self.TEMAS):
            control = self._con_cola("X")
            env.anunciar.reset_mock()
            control.abrir_enlace(
                "https://www.youtube.com/playlist?list=PL1", modo)
            textos = [c.args[0] for c in env.anunciar.call_args_list]
            titulos = [t.titulo for t in control.estado().cola]
        return textos, titulos, env

    def test_modo_final_suma_al_final(self):
        textos, titulos, _env = self._abrir("final")
        self.assertEqual(textos, ["Leyendo el enlace",
                                  "2 canciones agregadas a la cola"])
        self.assertEqual(titulos, ["X", "Uno", "Dos"])

    def test_modo_continuacion_mete_detras(self):
        textos, titulos, _env = self._abrir("continuacion")
        self.assertEqual(textos, [
            "Leyendo el enlace",
            "2 canciones a continuación, desde la posición 2"])
        self.assertEqual(titulos, ["X", "Uno", "Dos"])

    def test_modo_ahora_empieza_por_el_primero(self):
        textos, titulos, _env = self._abrir("ahora")
        self.assertEqual(textos, ["Leyendo el enlace", "Uno"])
        self.assertEqual(titulos, ["X", "Uno", "Dos"])

    def test_enlace_que_no_es_de_youtube_no_expande(self):
        with _entorno() as env, \
                mock.patch.object(musica_enlaces.enlaces, "expandir") as expandir:
            ControlMusica(_frame()).abrir_enlace(
                "https://ejemplo.test/video", "final")
        expandir.assert_not_called()
        env.anunciar.assert_called_once_with(
            "Esa dirección no es de YouTube")
        self.assertEqual(env.snd.sonidos, ["error"])

    def test_agregar_enlace_sigue_siendo_el_modo_final(self):
        with _entorno() as env, \
                mock.patch.object(musica_enlaces.enlaces, "expandir",
                                  return_value=self.TEMAS):
            control = self._con_cola("X")
            env.anunciar.reset_mock()
            control.agregar_enlace("https://youtu.be/uno")
        self.assertEqual(env.anunciar.call_args_list[-1].args[0],
                         "2 canciones agregadas a la cola")
        self.assertEqual([t.titulo for t in control.estado().cola],
                         ["X", "Uno", "Dos"])


class TestListasPropias(unittest.TestCase):
    """Las operaciones nuevas de listas sobre `listas.py` y sus avisos."""

    @staticmethod
    def _temas_reales(tmp, *nombres):
        temas = []
        for nombre in nombres:
            ruta = Path(tmp) / f"{nombre.lower()}.mp3"
            ruta.write_bytes(b"")
            temas.append(Tema(str(ruta.resolve()), nombre))
        return temas

    def _carpeta(self, tmp):
        return Path(tmp) / "listas"

    def test_guardar_cola_como_lista(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp, "A", "B")
            carpeta = self._carpeta(tmp)
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
                                      return_value=carpeta):
                control = ControlMusica(_frame())
                control.reproducir_temas(temas, en_orden=True)
                env.anunciar.reset_mock()
                control.guardar_cola_como_lista("Rock")
                cargados, saltadas = listas.cargar(carpeta, "Rock")
        env.anunciar.assert_called_once_with("Lista guardada: Rock")
        self.assertEqual([t.titulo for t in cargados], ["A", "B"])
        self.assertEqual(saltadas, 0)

    def test_guardar_cola_vacia_avisa(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
                                      return_value=self._carpeta(tmp)):
                ControlMusica(_frame()).guardar_cola_como_lista("Rock")
        env.anunciar.assert_called_once_with("No hay canciones en la cola")

    def test_agregar_y_quitar_de_lista(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp, "A", "B")
            carpeta = self._carpeta(tmp)
            listas.guardar(carpeta, "Rock", (temas[0],))
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
                                      return_value=carpeta):
                control = ControlMusica(_frame())
                control.agregar_a_lista("Rock", [temas[1]])
                textos = [c.args[0] for c in env.anunciar.call_args_list]
                env.anunciar.reset_mock()
                control.quitar_de_lista("Rock", 0)
                quitado = env.anunciar.call_args.args[0]
                restantes, _saltadas = listas.cargar(carpeta, "Rock")
        self.assertEqual(textos, ["Agregado a la lista Rock"])
        self.assertEqual(quitado, "Canción quitada de la lista")
        self.assertEqual([t.titulo for t in restantes], ["B"])

    def test_crear_renombrar_borrar_y_leer(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp, "A")
            carpeta = self._carpeta(tmp)
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
                                      return_value=carpeta):
                control = ControlMusica(_frame())
                control.crear_lista("Rock")
                creada = env.anunciar.call_args.args[0]
                control.agregar_a_lista("Rock", temas)
                env.anunciar.reset_mock()
                control.renombrar_lista("Rock", "Otra")
                renombrada = env.anunciar.call_args.args[0]
                control.borrar_lista("Otra")
                borrada = env.anunciar.call_args.args[0]
                control.crear_lista("Final")
                control.agregar_a_lista("Final", temas)
                env.anunciar.reset_mock()
                devueltos = control.temas_de_lista("Final")
        self.assertEqual(creada, "Lista creada: Rock")
        self.assertEqual(renombrada, "Lista renombrada: Otra")
        self.assertEqual(borrada, "Lista borrada: Otra")
        self.assertEqual([t.titulo for t in devueltos], ["A"])
        env.anunciar.assert_not_called()

    def test_error_de_listas_avisa_con_sonido(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
                                      return_value=self._carpeta(tmp)):
                ControlMusica(_frame()).crear_lista("")
        env.anunciar.assert_called_once_with("Escribe un nombre para la lista")
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
        frame._musica.texto_estado.return_value = "Música: A, canción 1 de 2"
        snap = gui.YTChatFrame._snapshot_sesion(frame)
        self.assertEqual(snap.musica, "Música: A, canción 1 de 2")

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
            self.assertEqual(control.texto_estado(), "Música: A, canción 1 de 2")
            control.siguiente()
            self.assertEqual(control.texto_estado(), "Música: B, canción 2 de 2")
            control.reproducir_o_pausar()
            self.assertEqual(control.texto_estado(),
                             "Música en pausa: B, canción 2 de 2")
            control.detener()
        self.assertEqual(control.texto_estado(), "")

    def test_incluye_el_artista_si_esta_incluido_en_el_modo(self):
        temas = [Tema("C:/m/a.mp3", "A", artista="Ana")]
        with _entorno():
            control = ControlMusica(_frame(musica_decir="titulo_artista"))
            control.reproducir_temas(temas)
        self.assertEqual(control.texto_estado(), "Música: A, de Ana, canción 1 de 1")

    def test_texto_estado_con_nada_dice_todo(self):
        temas = [Tema("C:/m/a.mp3", "A", artista="Ana")]
        with _entorno():
            control = ControlMusica(_frame(musica_decir="nada"))
            control.reproducir_temas(temas)
        self.assertEqual(control.texto_estado(), "Música: A, de Ana, canción 1 de 1")


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
                env.programador.disparar()
                vivos, posicion = memoria.leer(env.memoria)
                self.assertEqual([t.origen for t in vivos],
                                 [t.origen for t in temas])
                self.assertEqual(posicion, 0)
                control.siguiente()
                env.programador.disparar()
                vivos, posicion = memoria.leer(env.memoria)
                self.assertEqual(posicion, 1)

    def test_guarda_tras_aviso_automatico(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp)
            with _entorno() as env:
                control = ControlMusica(_frame())
                control.reproducir_temas(temas, en_orden=True)
                env.programador.disparar()
                env.memoria.unlink()
                control._aviso_automatico(_aviso(posicion=1, cola=temas))
                env.programador.disparar()
                self.assertTrue(env.memoria.exists())

    def test_detener_borra_la_memoria(self):
        with _entorno() as env:
            control = ControlMusica(_frame())
            control.reproducir_temas([Tema("C:/m/a.mp3", "A")])
            env.programador.disparar()
            self.assertTrue(env.memoria.exists())
            control.detener()
            env.programador.disparar()
            self.assertFalse(env.memoria.exists())

    def test_con_retomar_apagado_no_guarda_y_borra(self):
        with _entorno() as env:
            env.memoria.write_text("{}", encoding="utf-8")
            ControlMusica(_frame(musica_retomar=False)).reproducir_temas(
                [Tema("C:/m/a.mp3", "A")])
            env.programador.disparar()
            self.assertFalse(env.memoria.exists())

    def test_cerrar_con_memoria_pendiente_la_escribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            temas = self._temas_reales(tmp)
            with _entorno() as env:
                control = ControlMusica(_frame())
                control.reproducir_temas(temas, en_orden=True)
                self.assertFalse(env.memoria.exists())
                control.cerrar()
                self.assertTrue(env.memoria.exists())


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
                self.assertEqual([c[1] for c in cargas], [str(b.resolve())])
                self.assertIn("Retomando: B", textos)
                control.detener()
                env.programador.disparar()
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

    def test_reproducir_lista_guardada_carga_y_reproduce(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "listas"
            sonoro = Path(tmp) / "a.mp3"
            sonoro.write_bytes(b"")
            listas.guardar(carpeta, "Mía", (Tema(str(sonoro.resolve()), "A"),))
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
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
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
                                      return_value=carpeta):
                ControlMusica(_frame()).reproducir_lista_guardada("Mezcla")
        self.assertEqual(env.anunciar.call_args_list[0].args[0],
                         "Se saltó 1 entrada que no se pudo leer")

    def test_reproducir_lista_inexistente_avisa_con_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "listas"
            with _entorno() as env, \
                    mock.patch.object(musica_listas_propias.paths, "listas_musica",
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


class TestVentanaUnica(unittest.TestCase):
    """Con una ventana de música abierta, abrir otra la trae al frente."""

    def test_abrir_ventana_con_una_abierta_no_crea_otra(self):
        with _entorno() as env, mock.patch.object(
                musica_ventana, "abrir_ventana") as abrir:
            control = ControlMusica(_frame())
            ventana = mock.Mock()
            control.registrar_ventana(ventana)
            control.abrir_ventana()
        abrir.assert_not_called()
        ventana.Raise.assert_called_once_with()
        ventana.enfocar_primer_control.assert_called_once_with()
        env.anunciar.assert_called_once_with(anuncios.TEXTO_VENTANA_ABIERTA)

    def test_sin_ventana_abierta_abre_la_de_musica(self):
        with _entorno(), mock.patch.object(
                musica_ventana, "abrir_ventana") as abrir:
            control = ControlMusica(_frame())
            control.abrir_ventana()
        abrir.assert_called_once_with(control)

    def test_registrar_y_olvidar_la_unica_ventana(self):
        with _entorno():
            control = ControlMusica(_frame())
            ventana = mock.Mock()
            control.registrar_ventana(ventana)
            self.assertIs(control._ventanas.get("musica"), ventana)
            control.olvidar_ventana()
            self.assertNotIn("musica", control._ventanas)

    def test_una_ventana_nueva_reemplaza_la_registrada(self):
        with _entorno():
            control = ControlMusica(_frame())
            vieja = mock.Mock()
            nueva = mock.Mock()
            control.registrar_ventana(vieja)
            control.registrar_ventana(nueva)
            self.assertIs(control._ventanas.get("musica"), nueva)


class _MarcoGlobales:
    """Marco falso con ventana: registra atajos globales sin wx de verdad."""

    def __init__(self, **config):
        self._config = _frame(**config)._config
        self.registrados = {}
        self.soltados = []
        self.fallan_vk = set()

    def RegisterHotKey(self, ident, mods, vk):
        if vk in self.fallan_vk:
            return False
        self.registrados[ident] = (mods, vk)
        return True

    def UnregisterHotKey(self, ident):
        self.soltados.append(ident)
        self.registrados.pop(ident, None)
        return True

    def Bind(self, evento, manejador, id=-1):
        pass

    def Unbind(self, evento, id=-1):
        pass


class TestAtajosGlobalesControl(unittest.TestCase):

    def test_apagado_de_fabrica_no_activa(self):
        with _entorno():
            control = ControlMusica(_MarcoGlobales())
        self.assertFalse(control._globales.activos)

    def test_activa_al_crearse_con_la_preferencia_y_calla(self):
        with _entorno() as env:
            control = ControlMusica(
                _MarcoGlobales(musica_atajos_globales=True))
        self.assertTrue(control._globales.activos)
        self.assertEqual(len(control._globales._registrados),
                         len(atajos_globales.ACCIONES))
        env.anunciar.assert_not_called()
        self.assertEqual(env.snd.sonidos, [])

    def test_fallo_al_arrancar_se_anuncia_con_error(self):
        marco = _MarcoGlobales(musica_atajos_globales=True)
        marco.fallan_vk = {0x27}
        with _entorno() as env:
            ControlMusica(marco)
        env.anunciar.assert_called_once_with(
            "No se pudieron usar en cualquier programa: "
            "Ctrl+Alt+Flecha derecha, Ctrl+Alt+Mayús+Flecha derecha. "
            "Las usa otro programa")
        self.assertEqual(env.snd.sonidos, ["error"])

    def test_aplicar_en_caliente_activa_y_desactiva_con_anuncio(self):
        marco = _MarcoGlobales()
        with _entorno() as env:
            control = ControlMusica(marco)
            marco._config["musica_atajos_globales"] = True
            control.aplicar_preferencias()
            self.assertTrue(control._globales.activos)
            marco._config["musica_atajos_globales"] = False
            control.aplicar_preferencias()
            self.assertFalse(control._globales.activos)
        self.assertEqual(
            [c.args[0] for c in env.anunciar.call_args_list],
            ["Atajos de música activos en cualquier programa",
             "Atajos de música solo en YTChat"])
        self.assertEqual(env.snd.sonidos, [])

    def test_aplicar_dos_veces_no_repite_el_anuncio(self):
        marco = _MarcoGlobales()
        with _entorno() as env:
            control = ControlMusica(marco)
            marco._config["musica_atajos_globales"] = True
            control.aplicar_preferencias()
            control.aplicar_preferencias()
        self.assertTrue(control._globales.activos)
        env.anunciar.assert_called_once_with(
            "Atajos de música activos en cualquier programa")

    def test_reactiva_si_cambiaron_los_atajos(self):
        marco = _MarcoGlobales(musica_atajos_globales=True)
        with _entorno() as env:
            control = ControlMusica(marco)
            env.anunciar.reset_mock()
            marco._config["atajos_raw"] = {"musica_que_suena": "ctrl+alt+y"}
            control.aplicar_preferencias()
        self.assertIn((gui_musica.wx.MOD_CONTROL | gui_musica.wx.MOD_ALT,
                       ord("Y")),
                      marco.registrados.values())
        env.anunciar.assert_called_once_with(
            "Atajos de música activos en cualquier programa")

    def test_fallo_al_aplicar_se_anuncia_con_error(self):
        marco = _MarcoGlobales(musica_atajos_globales=True)
        marco.fallan_vk = {ord("T")}
        with _entorno() as env:
            control = ControlMusica(marco)
        env.anunciar.assert_called_once_with(
            "No se pudieron usar en cualquier programa: "
            "Ctrl+Alt+T. Las usa otro programa")
        self.assertEqual(env.snd.sonidos, ["error"])
        self.assertTrue(control._globales.activos)

    def test_desactiva_al_cerrar(self):
        marco = _MarcoGlobales(musica_atajos_globales=True)
        with _entorno():
            control = ControlMusica(marco)
            self.assertTrue(control._globales.activos)
            control.cerrar()
        self.assertFalse(control._globales.activos)
        self.assertEqual(marco.registrados, {})
        self.assertEqual(len(marco.soltados), len(atajos_globales.ACCIONES))


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


class TestSonoridadCableada(unittest.TestCase):
    """El cableado de la normalización: indexar mide y el motor envuelve."""

    def test_indexar_no_mide_y_con_iniciar_igualacion_si_guarda(self):
        from ytchat.music import sonoridad
        from ytchat.music.sonoridad import CacheSonoridad

        with tempfile.TemporaryDirectory() as tmp:
            for nombre in ("a.mp3", "b.mp3"):
                (Path(tmp) / nombre).write_bytes(b"audio-" + nombre.encode())
            with _entorno() as env, \
                    mock.patch("ytchat.downloads.ffmpeg_bin.ruta_ffmpeg",
                               return_value="ffmpeg"), \
                    mock.patch("ytchat.music.sonoridad.medir",
                               return_value=3.0):
                control = ControlMusica(_frame(musica_carpeta=tmp))
                recibidas = []
                control.biblioteca(recibidas.append)
                self.assertEqual(len(recibidas[0].temas()), 2)
                vacia = CacheSonoridad(env.sonoridad)
                for tema in recibidas[0].temas():
                    info = os.stat(tema.origen)
                    self.assertIsNone(
                        vacia.buscar(tema.origen, info.st_mtime_ns,
                                     info.st_size))
                resultado = control.iniciar_igualacion(recibidas[0])
                self.assertEqual(resultado.codigo, sonoridad.INICIO)
                releida = CacheSonoridad(env.sonoridad)
                for tema in recibidas[0].temas():
                    info = os.stat(tema.origen)
                    self.assertEqual(
                        releida.buscar(tema.origen, info.st_mtime_ns,
                                       info.st_size),
                        3.0)

    def test_motor_envuelve_con_la_ganancia_guardada(self):
        from ytchat.music import sonoridad
        from ytchat.music.sonoridad import CacheSonoridad

        for normalizar, esperado in (
                (True, sonoridad.volumen_efectivo(50, 6.0)), (False, 50)):
            with tempfile.TemporaryDirectory() as tmp:
                ruta = Path(tmp) / "a.mp3"
                ruta.write_bytes(b"audio-a")
                with _entorno() as env:
                    previa = CacheSonoridad(env.sonoridad)
                    info = os.stat(str(ruta.resolve()))
                    previa.poner(str(ruta.resolve()), info.st_mtime_ns,
                                 info.st_size, 6.0)
                    previa.guardar()
                    with mock.patch(
                            "ytchat.downloads.ffmpeg_bin.ruta_ffmpeg",
                            return_value="ffmpeg"):
                        control = ControlMusica(_frame(
                            musica_carpeta=tmp, musica_normalizar=normalizar,
                            musica_volumen=50))
                        control.reproducir_o_pausar()
                    llamadas = env.creados[0].llamadas
            cargas = [l for l in llamadas if l[0] == "cargar"]
            self.assertEqual([c[1] for c in cargas], [str(ruta.resolve())])
            primer_cargar = next(
                i for i, l in enumerate(llamadas) if l[0] == "cargar")
            previos = [l[1] for l in llamadas[:primer_cargar]
                       if l[0] == "volumen"]
            self.assertEqual(previos[-1], esperado)
        self.assertEqual(sonoridad.volumen_efectivo(50, 6.0), 100)


if __name__ == "__main__":
    unittest.main()
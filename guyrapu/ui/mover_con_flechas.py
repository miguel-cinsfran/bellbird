"""Movimiento de una fuente de OBS con las flechas del teclado."""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import ajuste_fino
from guyrapu.obs import consultas_transmision
from guyrapu.obs import obs_cliente
from guyrapu.obs import obs_disposicion
from guyrapu.ui.accesibilidad import anunciar

logger = diagnostico.obtener_logger(__name__)


class MoverConFlechas:
    """Lleva el modo de flechas: entrar, mover, confirmar, deshacer y salir."""

    def __init__(self, lista, gestor, operaciones, restablecimiento,
                 destino, al_mover, al_empezar=None, al_salir=None):
        self._lista = lista
        self._gestor = gestor
        self._operaciones = operaciones
        self._restablecimiento = restablecimiento
        self._destino = destino
        self._al_mover = al_mover
        self._al_empezar = al_empezar or (lambda _escena, _fuente: None)
        self._al_salir = al_salir or (lambda _confirmado: None)
        self._ajuste = ajuste_fino.EstadoAjuste()
        self._anotado = False

    @property
    def en_curso(self):
        return self._ajuste.en_curso

    def iniciar(self):
        if self._ajuste.en_curso:
            return
        escena, fuente = self._destino()
        if not fuente:
            anunciar(_("Sin selección"))
            return
        if self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: consultas_transmision.preparar_ajuste(
                self._gestor, self._restablecimiento, escena, fuente),
            self._iniciado)

    def _iniciado(self, datos):
        transformacion, snap = datos
        if self._operaciones.cerrando:
            return
        self._ajuste.entrar(transformacion)
        self._anotado = False
        self._lista.SetFocus()
        self._al_mover(snap)
        anunciar(ajuste_fino.texto_de_entrada())
        self._anunciar(snap)

    def procesar(self, event):
        """Atiende una tecla del modo de flechas. Devuelve si la consumió."""
        accion, dx, dy = ajuste_fino.resolver(
            event.GetKeyCode(), event.ControlDown(), event.ShiftDown())
        if accion == "mover" and self._ajuste.puede_mover():
            self._mover(dx, dy)
        elif accion == "cancelar":
            self._salir(False)
        elif accion in ("confirmar", "salir"):
            self._salir(True)
            if accion == "salir":
                event.Skip()
        return True

    def _mover(self, dx, dy):
        self._ajuste.empezar_movimiento()
        escena, fuente = self._destino()
        diagnostico.crear_hilo(
            lambda: self._trabajo_mover(escena, fuente, dx, dy),
            "MoverConFlechasOBS").start()

    def _trabajo_mover(self, escena, fuente, dx, dy):
        try:
            if not self._anotado:
                self._al_empezar(escena, fuente)
                self._anotado = True
            snap = consultas_transmision.mover(
                self._gestor, escena, dx, dy, fuente)
            filas = consultas_transmision.leer_filas(self._gestor, escena)
        except Exception as error:
            self._fallo_en_hilo(error)
        else:
            wx.CallAfter(self._terminado, snap, filas)

    def _fallo_en_hilo(self, error):
        if isinstance(error, obs_cliente.ObsError):
            mensaje = str(error)
        else:
            logger.warning("mover con flechas OBS: %r", error)
            mensaje = obs_cliente.mensaje_de_fallo_obs(error)
        wx.CallAfter(self._fallo, mensaje)

    def _terminado(self, snap, filas=None):
        decision = self._ajuste.aterrizar()
        if self._operaciones.cerrando:
            return
        if decision == ajuste_fino.DESHACER:
            self._deshacer()
        elif decision == ajuste_fino.MOSTRAR:
            self._al_mover(snap, filas)
            self._anunciar(snap)

    def _fallo(self, mensaje):
        decision = self._ajuste.aterrizar()
        if self._operaciones.cerrando:
            return
        if decision == ajuste_fino.DESHACER:
            self._deshacer()
        elif decision == ajuste_fino.MOSTRAR:
            self._operaciones.fallo(mensaje)

    def _anunciar(self, snap):
        anunciar(obs_disposicion.describir(
            snap, ("posicion", "solape", "fuera")), "ajuste")

    def _salir(self, confirmar):
        decision = self._ajuste.salir(confirmar)
        if decision == ajuste_fino.NADA:
            return
        if decision == ajuste_fino.CONFIRMADO:
            anunciar(_("Posición confirmada"))
            self._al_salir(True)
        elif decision == ajuste_fino.DESHACER:
            self._deshacer()

    def _deshacer(self):
        transformacion = self._ajuste.tomar_para_deshacer()
        if not transformacion:
            anunciar(_("No se pudo deshacer el movimiento"))
            return
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: self._trabajo_deshacer(transformacion, escena, fuente),
            self._deshacer_mostrado)

    def _trabajo_deshacer(self, transformacion, escena, fuente):
        self._gestor.posicionar(
            escena, transformacion["positionX"],
            transformacion["positionY"], transformacion["alignment"],
            fuente=fuente)
        return consultas_transmision.leer_filas(self._gestor, escena)

    def _deshacer_mostrado(self, filas):
        self._al_mover(None, filas)
        anunciar(_("Movimiento deshecho"))
        self._al_salir(False)

"""Movimiento de una fuente de OBS con las flechas del teclado."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import ajuste_fino
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_cliente
from bellbird.obs import obs_disposicion
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.preferencias_comun import nombre_de_etiqueta

logger = diagnostico.obtener_logger(__name__)


class MoverConFlechas:
    """Lleva el modo de flechas: entrar, mover, confirmar, deshacer y salir."""

    def __init__(self, ventana, boton, gestor, operaciones, restablecimiento,
                 destino, al_mover):
        self._ventana = ventana
        self._boton = boton
        self._gestor = gestor
        self._operaciones = operaciones
        self._restablecimiento = restablecimiento
        self._destino = destino
        self._al_mover = al_mover
        self._etiqueta_base = boton.GetLabel()
        self._ajuste = ajuste_fino.EstadoAjuste()
        boton.Bind(wx.EVT_BUTTON, self._iniciar)
        boton.Bind(wx.EVT_KILL_FOCUS, self._perdio_foco)
        ventana.Bind(wx.EVT_CHAR_HOOK, self._tecla)

    @property
    def en_curso(self):
        return self._ajuste.en_curso

    def _iniciar(self, event):
        if self._ajuste.en_curso:
            return
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.preparar_ajuste(
                self._gestor, self._restablecimiento, escena, fuente),
            self._iniciado)

    def _iniciado(self, datos):
        transformacion, snap = datos
        self._ajuste.entrar(transformacion)
        self._mostrar_etiqueta(True)
        self._al_mover(snap)
        anunciar(ajuste_fino.texto_de_entrada())
        self._anunciar(snap)

    def _mostrar_etiqueta(self, activo):
        etiqueta = ajuste_fino.etiqueta_boton(activo, self._etiqueta_base)
        self._boton.SetLabel(etiqueta)
        self._boton.SetName(nombre_de_etiqueta(etiqueta))

    def _tecla(self, event):
        if not self._ajuste.en_curso:
            event.Skip()
            return
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

    def _mover(self, dx, dy):
        self._ajuste.empezar_movimiento()
        escena, fuente = self._destino()
        diagnostico.crear_hilo(
            lambda: self._trabajo_mover(escena, fuente, dx, dy),
            "MoverConFlechasOBS").start()

    def _trabajo_mover(self, escena, fuente, dx, dy):
        try:
            snap = consultas_transmision.mover(
                self._gestor, escena, dx, dy, fuente)
            filas = consultas_transmision.leer_filas(self._gestor, escena)
        except obs_cliente.ObsError as error:
            wx.CallAfter(self._fallo, str(error))
        except Exception as error:
            logger.warning("mover con flechas OBS: %r", error)
            wx.CallAfter(self._fallo, obs_cliente.mensaje_de_fallo_obs(error))
        else:
            wx.CallAfter(self._terminado, snap, filas)

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
        # Aquí la fuente no cambia y ya se anunció al entrar; los otros anuncios
        # pueden cambiar de fuente y llevan nombre.
        anunciar(obs_disposicion.describir(
            snap, ("posicion", "solape", "fuera")), "ajuste")

    def _perdio_foco(self, event):
        if self._ajuste.en_curso:
            self._salir(True)
        event.Skip()

    def _salir(self, confirmar):
        decision = self._ajuste.salir(confirmar)
        if decision == ajuste_fino.NADA:
            return
        self._mostrar_etiqueta(False)
        if decision == ajuste_fino.CONFIRMADO:
            anunciar(_("Posición confirmada"))
        elif decision == ajuste_fino.DESHACER:
            self._deshacer()

    def _deshacer(self):
        transformacion = self._ajuste.tomar_para_deshacer()
        if not transformacion:
            # transformacion() devuelve {} cuando la fuente ya no está en la
            # escena; no hay a dónde volver.
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

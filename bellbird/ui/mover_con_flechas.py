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
        def mover():
            try:
                snap = consultas_transmision.mover(
                    self._gestor, escena, dx, dy, fuente)
            except obs_cliente.ObsError as error:
                wx.CallAfter(self._fallo, str(error))
            except Exception as error:
                logger.warning("mover con flechas OBS: %r", error)
                wx.CallAfter(self._fallo, obs_cliente.mensaje_de_fallo_obs(error))
            else:
                wx.CallAfter(self._terminado, snap)
        diagnostico.crear_hilo(mover, "MoverConFlechasOBS").start()

    def _terminado(self, snap):
        decision = self._ajuste.aterrizar()
        if self._operaciones.cerrando:
            return
        if decision == ajuste_fino.DESHACER:
            self._deshacer()
        elif decision == ajuste_fino.MOSTRAR:
            self._al_mover(snap)
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
            lambda: self._gestor.posicionar(
                escena, transformacion["positionX"],
                transformacion["positionY"], transformacion["alignment"],
                fuente=fuente),
            lambda resultado: anunciar(_("Movimiento deshecho")))

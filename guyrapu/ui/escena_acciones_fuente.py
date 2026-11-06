"""Acciones sobre una fuente de la pestaña Escena del Panel de OBS."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import (
    consultas_transmision, deshacer, fuentes_obs, tamano_relativo,
    transformar_fuente)
from guyrapu.ui import escena_edicion_fuente, escena_tamano
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.mover_con_flechas import MoverConFlechas


class AccionesFuente:
    """El menú, los atajos y el modo de flechas de la lista de fuentes."""

    def __init__(self, pagina):
        self._pagina = pagina
        self._gestor = pagina._gestor
        self._operaciones = pagina._operaciones
        self._registro = pagina._registro
        self._pila = deshacer.PilaDeshacer()
        self._edicion = escena_edicion_fuente.AccionesEdicion(
            pagina, self._pila)
        self._movimiento_anotado = False
        self._mover = MoverConFlechas(
            pagina.lst_fuentes, self._gestor,
            self._operaciones, self._registro, pagina._destino,
            pagina._mostrar_snap, al_empezar=self._empezar_movimiento,
            al_salir=self._terminar_movimiento)

    @property
    def mover(self):
        return self._mover

    def tecla(self, event):
        """Atiende los atajos de la lista. Devuelve si consumió la tecla."""
        if self._mover.en_curso:
            return self._mover.procesar(event)
        codigo = event.GetKeyCode()
        ctrl = event.ControlDown()
        if ctrl and codigo in (ord("Z"), ord("z")):
            self.deshacer()
            return True
        if ctrl and codigo in (wx.WXK_HOME, wx.WXK_UP, wx.WXK_DOWN,
                               wx.WXK_END):
            self._atajo_de_orden(codigo)
            return True
        if codigo == wx.WXK_SPACE:
            fila = self._fila()
            if fila is None:
                self._sin_seleccion()
            else:
                self.mostrar(not fila.visible)
            return True
        if codigo == wx.WXK_F2:
            self.renombrar()
            return True
        if ctrl and codigo in (ord("D"), ord("d")):
            self.duplicar()
            return True
        if codigo == wx.WXK_DELETE:
            self.eliminar()
            return True
        return False

    def _atajo_de_orden(self, codigo):
        movimientos = {
            wx.WXK_HOME: "frente", wx.WXK_UP: "adelante",
            wx.WXK_DOWN: "atras", wx.WXK_END: "fondo",
        }
        self.ordenar(movimientos[codigo])

    def mostrar(self, visible):
        self._con_pila(
            _("visibilidad"),
            lambda escena, fuente: self._cambiar_y_leer(
                escena, fuente, self._gestor.mostrar, visible),
            self._mostrar_cambio)

    def bloquear(self, fijada):
        self._con_pila(
            _("bloqueo"),
            lambda escena, fuente: self._cambiar_y_leer(
                escena, fuente, self._gestor.fijar, fijada),
            self._mostrar_cambio)

    def ordenar(self, movimiento):
        if movimiento == "frente":
            self._con_pila(
                _("orden"),
                lambda escena, fuente: self._cambiar_y_leer(
                    escena, fuente, self._gestor.al_frente),
                self._frente_mostrado)
            return
        datos = {}

        def mover(escena, capa, fuente):
            datos["movio"], datos["frase"] = self._gestor.mover_capa(
                escena, capa, fuente=fuente)

        def trabajo(escena, fuente):
            return (self._cambiar_y_leer(
                escena, fuente, mover, movimiento), dict(datos))

        self._con_pila(_("orden"), trabajo, self._movimiento_mostrado)

    def _frente_mostrado(self, datos, _escena, fuente):
        self._mostrar_y_anunciar(
            datos[1], fuente,
            _("{fuente} al frente.").format(fuente=fuente))

    def _movimiento_mostrado(self, datos, _escena, fuente):
        (snap, filas), estado = datos
        texto = estado["frase"]
        if estado["movio"]:
            texto = f"{texto} {self._pagina._descripcion_corta(snap)}"
        self._mostrar_y_anunciar(filas, fuente, texto)

    def _mostrar_cambio(self, datos, _escena, fuente):
        snap, filas = datos
        self._pagina.cargar(filas, fuente)
        self._enfocar()
        self._pagina._anunciar_snap(snap)

    def _mostrar_y_anunciar(self, filas, fuente, texto):
        self._pagina.cargar(filas, fuente)
        self._enfocar()
        anunciar(texto)

    def posicion_tamano(self):
        escena, fuente = self._destino()
        if not fuente:
            self._sin_seleccion()
            return
        if self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: self._gestor.instantanea(escena, fuente=fuente),
            lambda snap: self._abrir_posicion_tamano(escena, fuente, snap))

    def _abrir_posicion_tamano(self, escena, fuente, snap):
        if self._operaciones.cerrando:
            return
        porcentajes = tamano_relativo.porcentajes(
            snap.ancho, snap.alto, snap.lienzo_ancho, snap.lienzo_alto)
        if not all(porcentajes):
            self._anunciar_sin_tamano(fuente)
            return
        elegido = escena_tamano.pedir_tamano(self._pagina, *porcentajes)
        self._enfocar()
        if elegido is None:
            return
        pancho, palto, anclaje = elegido
        ancho, alto = tamano_relativo.a_pixeles(
            pancho, palto, snap.lienzo_ancho, snap.lienzo_alto,
            snap.ancho, snap.alto)
        self._operaciones.en_hilo(
            lambda: self._aplicar_posicion_tamano(
                escena, fuente, ancho, alto, anclaje),
            lambda datos: self._tamano_aplicado(datos, fuente))

    def _aplicar_posicion_tamano(self, escena, fuente, ancho, alto, anclaje):
        self._pila.guardar(
            self._gestor, escena, fuente, _("posición y tamaño"))
        try:
            datos = consultas_transmision.aplicar_posicion_y_tamano(
                self._gestor, self._registro, escena, fuente, ancho, alto,
                anclaje)
            filas = consultas_transmision.leer_filas(self._gestor, escena)
        except Exception:
            self._pila.descartar()
            raise
        return datos, filas

    def _tamano_aplicado(self, datos, fuente):
        (snap, aplicado), filas = datos
        self._pagina.cargar(filas, fuente)
        if aplicado:
            self._pagina._anunciar_snap(snap)
        else:
            self._anunciar_sin_tamano(fuente)

    def _anunciar_sin_tamano(self, fuente):
        anunciar(_("{fuente} todavía no informa su tamaño.").format(
            fuente=fuente))

    def mover_con_flechas(self):
        escena, fuente = self._destino()
        if not fuente:
            self._sin_seleccion()
            return
        self._mover.iniciar()

    def centrar(self):
        self.transformar(
            transformar_fuente.centrar, _("posición"), _("centrada"))

    def ajustar(self):
        self.transformar(
            transformar_fuente.ajustar, _("tamaño"),
            _("ajustada al vídeo"))

    def llenar(self):
        self.transformar(
            transformar_fuente.llenar, _("tamaño"),
            _("cubre todo el vídeo"))

    def voltear_horizontal(self):
        self.transformar(
            transformar_fuente.voltear_horizontal, _("volteo"),
            _("volteada horizontalmente"))

    def voltear_vertical(self):
        self.transformar(
            transformar_fuente.voltear_vertical, _("volteo"),
            _("volteada verticalmente"))

    def girar_derecha(self):
        self.transformar(
            lambda forma, _ancho, _alto: transformar_fuente.girar(forma, 90),
            _("giro"), _("girada a la derecha"))

    def girar_izquierda(self):
        self.transformar(
            lambda forma, _ancho, _alto: transformar_fuente.girar(forma, -90),
            _("giro"), _("girada a la izquierda"))

    def restablecer(self):
        self.transformar(
            lambda forma, _ancho, _alto: transformar_fuente.restablecer(forma),
            _("tamaño y posición"),
            _("vuelve a su tamaño y posición originales"))

    def transformar(self, calculo, accion, frase):
        self._con_pila(
            accion,
            lambda escena, fuente: (
                fuentes_obs.aplicar_transformacion(
                    self._gestor, escena, fuente, calculo),
                consultas_transmision.leer_filas(self._gestor, escena)),
            lambda datos, _escena, fuente: self._transformado(
                datos[1], fuente, frase))

    def _transformado(self, filas, fuente, frase):
        self._pagina.cargar(filas, fuente)
        self._enfocar()
        fila = next((fila for fila in filas if fila.nombre == fuente), None)
        if fila is None:
            anunciar(f"{fuente} {frase}.")
            return
        anunciar(transformar_fuente.frase_de_accion(fila, frase))

    def renombrar(self):
        self._edicion.renombrar()

    def duplicar(self):
        self._edicion.duplicar()

    def eliminar(self):
        self._edicion.eliminar()

    def deshacer(self):
        if self._pila.vacia:
            anunciar(_("No hay nada que deshacer."))
            return
        if self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(self._deshacer_en_hilo, self._deshecho)

    def _deshacer_en_hilo(self):
        cambio = self._pila.deshacer(self._gestor)
        actual = self._pagina._escena()
        filas = consultas_transmision.leer_filas(self._gestor, actual)
        return cambio, actual, filas

    def _deshecho(self, datos):
        cambio, actual, filas = datos
        fuente = cambio.fuente if cambio.escena == actual else self._destino()[1]
        self._pagina.cargar(filas, fuente)
        self._enfocar()
        anunciar(_("Deshecho: {accion} de {fuente}.").format(
            accion=cambio.accion, fuente=cambio.fuente))

    def _empezar_movimiento(self, escena, fuente):
        self._pila.guardar(self._gestor, escena, fuente, _("posición"))
        self._movimiento_anotado = True

    def _terminar_movimiento(self, confirmado):
        if not confirmado and self._movimiento_anotado:
            self._pila.descartar()
        self._movimiento_anotado = False

    def _con_pila(self, accion, trabajo, al_terminar):
        escena, fuente = self._destino()
        if not fuente:
            self._sin_seleccion()
            return
        if self._operaciones.en_vuelo:
            return

        def ejecutar():
            self._pila.guardar(self._gestor, escena, fuente, accion)
            try:
                resultado = trabajo(escena, fuente)
            except Exception:
                self._pila.descartar()
                raise
            return resultado

        self._operaciones.en_hilo(
            ejecutar, lambda datos: al_terminar(datos, escena, fuente))

    def _cambiar_y_leer(self, escena, fuente, funcion, *argumentos):
        snap = consultas_transmision.cambiar_y_leer(
            self._gestor, self._registro, escena, fuente, funcion,
            *argumentos)
        return snap, consultas_transmision.leer_filas(self._gestor, escena)

    def _destino(self):
        return self._pagina._destino()

    def _fila(self):
        return self._pagina._fila()

    def _enfocar(self):
        self._pagina.lst_fuentes.SetFocus()

    def _sin_seleccion(self):
        anunciar(_("Sin selección"))

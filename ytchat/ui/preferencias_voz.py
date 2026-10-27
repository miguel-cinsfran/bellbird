"""Página Voces del diálogo de Preferencias.

Dueña de sus controles, de la prueba de voz, de ElevenLabs y de su guardado
propio. El diálogo la construye por composición.
"""

from __future__ import annotations

import wx

from ytchat.youtube import credenciales
from ytchat.ui import clave_elevenlabs
from ytchat.ui.gui import ContadorAccesible, _T, _tc, anunciar
from ytchat.ui.preferencias_comun import crear_panel, fila_label
from ytchat.ui.prueba_voz import PruebaVoz

_SIN_CLAVE_ELEVEN = "(comprueba la clave)"
_NO_HAY_VOCES = "(no hay voces disponibles)"


class PaginaVoz:
    """Página Voces: motor, clave de ElevenLabs, prueba de voz y su guardado."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def construir(self, parent):
        p = crear_panel(parent, "PagVoz")
        self._pag_voz_panel = p
        vs = wx.BoxSizer(wx.VERTICAL)
        from ytchat.voice import motores

        motor_guardado = self._config.get("motor", "sapi")
        self._motor_idx = (motores.MOTORES.index(motor_guardado)
                           if motor_guardado in motores.MOTORES else 0)
        es_eleven = motores.MOTORES[self._motor_idx] == "elevenlabs"

        self._crear_motor(p, vs)
        lbl_clave = self._crear_clave(p, vs)
        vacio_voz = self._crear_voz_lectura(p, vs, es_eleven)
        self._crear_ajustes(p, vs)
        self._crear_eleven(p, vs, lbl_clave)
        self._crear_multivoz(p, vs, vacio_voz)
        self._prueba = PruebaVoz()
        # El motor de prueba se cierra al cerrar el diálogo por cualquier camino.
        # Se escucha en el panel: el diálogo llega al evento como un wx.Window
        # genérico y `is` no lo reconoce (medido el 27/10/2026).
        p.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
        p.SetSizer(vs)
        self._mostrar_controles_eleven(es_eleven)
        if es_eleven and self.txt_clave_eleven.GetValue().strip():
            # Con clave guardada, las voces se comprueban solas en segundo
            # plano y se llenan; sin clave, todo queda a la espera.
            self.btn_comprobar_clave.Disable()
            self._comprobar_clave(anunciar_ok=False)
        return p

    def _crear_motor(self, p, vs):
        from ytchat.voice import motores

        vs.Add(fila_label(p, "&Motor de voz:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_motor = wx.Choice(
            p, choices=[motores.NOMBRES[m] for m in motores.MOTORES],
            name="Motor de voz")
        _tc(self.cho_motor)
        self.cho_motor.SetSelection(self._motor_idx)
        self.cho_motor.Bind(wx.EVT_CHOICE, self._on_motor_cambiado)
        vs.Add(self.cho_motor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _crear_clave(self, p, vs):
        # Clave de ElevenLabs y su comprobación: solo se ven con ese motor.
        lbl_clave = fila_label(p, "Cl&ave de ElevenLabs:")
        self.txt_clave_eleven = wx.TextCtrl(
            p, value=credenciales.cargar().get("elevenlabs_clave", "") or "",
            style=wx.TE_PASSWORD, name="Clave de ElevenLabs")
        _tc(self.txt_clave_eleven)
        vs.Add(lbl_clave, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.txt_clave_eleven, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_comprobar_clave = wx.Button(
            p, label="Compro&bar clave", name="Comprobar clave")
        self.btn_comprobar_clave.SetBackgroundColour(_T.btn)
        self.btn_comprobar_clave.SetForegroundColour(_T.btn_t)
        self.btn_comprobar_clave.Bind(wx.EVT_BUTTON, self._on_comprobar_clave)
        vs.Add(self.btn_comprobar_clave, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        return lbl_clave

    def _crear_voz_lectura(self, p, vs, es_eleven):
        from ytchat.voice import motores

        # Voz del motor elegido. También está en el menú Voz → Seleccionar voz;
        # aquí queda junto al resto de ajustes de lectura para encontrarla más
        # fácil.
        vs.Add(fila_label(p, "&Voz de lectura:"), 0, wx.LEFT | wx.RIGHT, 10)
        if es_eleven:
            # Nunca se va a la red en el hilo de la interfaz: la lista queda
            # vacía hasta que se compruebe la clave.
            self._voces = []
            vacio_voz = _SIN_CLAVE_ELEVEN
        else:
            self._voces = motores.listar_voces(motores.MOTORES[self._motor_idx])
            vacio_voz = _NO_HAY_VOCES
        self.cho_voz = wx.Choice(p, choices=self._voces or [vacio_voz],
                                 name="Voz de lectura")
        _tc(self.cho_voz)
        self._cargar_voces(self.cho_voz, self._config.get("voz"), vacio=vacio_voz)
        vs.Add(self.cho_voz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        return vacio_voz

    def _crear_ajustes(self, p, vs):
        from ytchat.voice import escala_voz

        # Velocidad, volumen y tono como valores absolutos 0..100.
        vs.Add(fila_label(p, "Ve&locidad (0 a 100):"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_velocidad = ContadorAccesible(
            p, min=0, max=100, name="Velocidad de la voz",
            initial=escala_voz.ajustar_velocidad(
                int(self._config.get("velocidad_voz", escala_voz.VELOCIDAD_NORMAL)), 0))
        self.sp_velocidad.SetIncrement(5)
        _tc(self.sp_velocidad)
        vs.Add(self.sp_velocidad, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        try:
            vol_pct = max(0, min(100, int(round(
                float(self._config.get("volumen", 1.0)) * 100))))
        except (TypeError, ValueError):
            vol_pct = 100
        vs.Add(fila_label(p, "Vol&umen (0 a 100):"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_volumen = ContadorAccesible(
            p, min=0, max=100, initial=vol_pct, name="Volumen de la voz")
        self.sp_volumen.SetIncrement(5)
        _tc(self.sp_volumen)
        vs.Add(self.sp_volumen, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(fila_label(p, "&Tono (0 a 100):"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_tono = ContadorAccesible(
            p, min=0, max=100, name="Tono de la voz",
            initial=max(0, min(100, int(self._config.get("tono", 50)))))
        self.sp_tono.SetIncrement(5)
        _tc(self.sp_tono)
        vs.Add(self.sp_tono, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_probar_voz = wx.Button(p, label="&Probar voz", name="Probar voz")
        self.btn_probar_voz.SetBackgroundColour(_T.btn)
        self.btn_probar_voz.SetForegroundColour(_T.btn_t)
        self.btn_probar_voz.Bind(wx.EVT_BUTTON, self._on_probar_voz)
        vs.Add(self.btn_probar_voz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _crear_eleven(self, p, vs, lbl_clave):
        from ytchat.voice import escala_voz
        from ytchat.voice import motores

        # Tope de caracteres por sesión (0 sin tope), «solo lo importante» y
        # la voz de Windows de respaldo. Solo se ven con ElevenLabs.
        lbl_tope = fila_label(p, "T&ope de caracteres por sesión (0 sin tope):")
        self.sp_tope_eleven = ContadorAccesible(
            p, min=0, max=1000000, name="Tope de caracteres de ElevenLabs",
            initial=max(0, int(self._config.get("elevenlabs_tope", 0) or 0)))
        self.sp_tope_eleven.SetIncrement(1000)
        _tc(self.sp_tope_eleven)
        vs.Add(lbl_tope, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.sp_tope_eleven, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_solo_importantes = wx.CheckBox(
            p, name="Solo lo importante con ElevenLabs",
            label="U&sar ElevenLabs solo con Super Chats, miembros, cofres, "
                  "dueño y moderadores")
        self.chk_solo_importantes.SetForegroundColour(_T.text)
        self.chk_solo_importantes.SetValue(
            bool(self._config.get("elevenlabs_solo_importantes", False)))
        vs.Add(self.chk_solo_importantes, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        lbl_respaldo = fila_label(p, "Voz de &Windows de respaldo:")
        self._voces_respaldo = motores.listar_voces("sapi")
        self.cho_voz_respaldo = wx.Choice(
            p, choices=self._voces_respaldo or [_NO_HAY_VOCES],
            name="Voz de Windows de respaldo")
        _tc(self.cho_voz_respaldo)
        if self._voces_respaldo:
            idx_respaldo = escala_voz.resolver_voz(
                self._config.get("voz_respaldo"), self._voces_respaldo)
            self.cho_voz_respaldo.SetSelection(
                0 if idx_respaldo is None else idx_respaldo)
        else:
            self.cho_voz_respaldo.SetSelection(0)
            self.cho_voz_respaldo.Disable()
        vs.Add(lbl_respaldo, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.cho_voz_respaldo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._eleven_ctrls = [
            lbl_clave, self.txt_clave_eleven, self.btn_comprobar_clave,
            lbl_tope, self.sp_tope_eleven, self.chk_solo_importantes,
            lbl_respaldo, self.cho_voz_respaldo,
        ]

    def _crear_multivoz(self, p, vs, vacio_voz):
        # Multi-voz: una voz distinta para los eventos (Super Chats, regalos,
        # miembros, entradas). Desactivada por defecto.
        self.chk_multivoz = wx.CheckBox(
            p, name="MultiVoz",
            label="Usar una voz &distinta para los eventos (Super Chats, regalos, "
                  "miembros y entradas)")
        self.chk_multivoz.SetForegroundColour(_T.text)
        vs.Add(self.chk_multivoz, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        vs.Add(fila_label(p, "Voz para los &eventos:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_voz_eventos = wx.Choice(
            p, choices=self._voces or [vacio_voz], name="Voz para los eventos")
        _tc(self.cho_voz_eventos)
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"),
                           vacio=vacio_voz)
        self.actualizar_eventos()
        self.chk_multivoz.Bind(
            wx.EVT_CHECKBOX,
            lambda e: self.cho_voz_eventos.Enable(bool(self._voces) and e.IsChecked()))
        vs.Add(self.cho_voz_eventos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def actualizar_eventos(self) -> None:
        self.cho_voz_eventos.Enable(
            bool(self._voces) and self.chk_multivoz.GetValue())

    def _mostrar_controles_eleven(self, visible: bool) -> None:
        for ctrl in getattr(self, "_eleven_ctrls", ()):
            ctrl.Show(visible)
        panel = getattr(self, "_pag_voz_panel", None)
        if panel is not None:
            panel.Layout()

    def _preparar_voces_eleven(self, anunciar_ok: bool = False) -> None:
        self._voces = []
        self._cargar_voces(self.cho_voz, self._config.get("voz"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self.cho_voz_eventos.Disable()
        if self.txt_clave_eleven.GetValue().strip():
            self.btn_comprobar_clave.Disable()
            self._comprobar_clave(anunciar_ok)

    def _on_comprobar_clave(self, event) -> None:
        if not self.txt_clave_eleven.GetValue().strip():
            anunciar("Escribe la clave de ElevenLabs.")
            return
        self.btn_comprobar_clave.Disable()
        self._comprobar_clave(anunciar_ok=True)

    def _comprobar_clave(self, anunciar_ok: bool) -> None:
        clave = self.txt_clave_eleven.GetValue().strip()
        clave_elevenlabs.comprobar(
            clave,
            lambda pares, usados, limite: self._clave_ok(
                pares, usados, limite, anunciar_ok),
            self._clave_fallo)

    def _clave_ok(self, pares, usados, limite, anunciar_ok: bool) -> None:
        if not self._ventana:   # el diálogo pudo cerrarse mientras se comprobaba
            return
        self.btn_comprobar_clave.Enable()
        self._voces = [nombre for _id, nombre in pares]
        self._cargar_voces(self.cho_voz, self._config.get("voz"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self.actualizar_eventos()
        if anunciar_ok:
            anunciar(clave_elevenlabs.texto_clave_valida(
                len(self._voces), usados, limite))

    def _clave_fallo(self, mensaje) -> None:
        if not self._ventana:
            return
        self.btn_comprobar_clave.Enable()
        self._voces = []
        self._cargar_voces(self.cho_voz, None, vacio=_SIN_CLAVE_ELEVEN)
        self._cargar_voces(self.cho_voz_eventos, None, vacio=_SIN_CLAVE_ELEVEN)
        self.cho_voz_eventos.Disable()
        anunciar(mensaje)

    def _cargar_voces(self, choice, guardada, vacio=_NO_HAY_VOCES) -> None:
        from ytchat.voice import escala_voz

        if self._voces:
            choice.SetItems(self._voces)
            idx = escala_voz.resolver_voz(guardada, self._voces)
            choice.SetSelection(0 if idx is None else idx)
            choice.Enable(True)
        else:
            choice.SetItems([vacio])
            choice.SetSelection(0)
            choice.Disable()

    def _motor_elegido(self) -> str:
        from ytchat.voice import motores

        i = self.cho_motor.GetSelection()
        return motores.MOTORES[i] if 0 <= i < len(motores.MOTORES) else "sapi"

    def _on_motor_cambiado(self, event) -> None:
        # Repuebla las voces del motor nuevo sin anunciar: el lector ya lee el
        # valor del combinado al recorrerlo. Con ElevenLabs, además, se ocultan
        # o muestran sus controles y se comprueba la clave en segundo plano.
        from ytchat.voice import motores

        motor = self._motor_elegido()
        if motor == "elevenlabs":
            self._mostrar_controles_eleven(True)
            self._preparar_voces_eleven()
            return
        self._mostrar_controles_eleven(False)
        self._voces = motores.listar_voces(motor)
        self._cargar_voces(self.cho_voz, self._config.get("voz"))
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"))
        self.actualizar_eventos()

    def _on_probar_voz(self, event) -> None:
        motor = self._motor_elegido()
        if motor == "elevenlabs":
            self._probar_voz_elevenlabs()
            return
        self._prueba.probar_prism(
            motor, self.cho_voz.GetSelection(), self.sp_velocidad.GetValue(),
            self.sp_volumen.GetValue(), self.sp_tono.GetValue())

    def _probar_voz_elevenlabs(self) -> None:
        if not self._voces:
            anunciar("Primero comprueba la clave.")
            return
        self._prueba.probar_elevenlabs(
            self.txt_clave_eleven.GetValue().strip(),
            self.cho_voz.GetStringSelection(),
            self.sp_velocidad.GetValue(), self.sp_volumen.GetValue())

    def _cerrar_motor_prueba(self) -> None:
        self._prueba.cerrar()

    def _al_destruir(self, event) -> None:
        # El evento sube desde los hijos, así que solo se atiende cuando el
        # panel mismo se destruye.
        if event.GetEventObject() is self._pag_voz_panel:
            self._cerrar_motor_prueba()
        event.Skip()

    def guardar(self, fijar, en_memoria):
        # Si el motor elegido no tiene voces no se guardan motor ni voz (se
        # conservan los anteriores); el resto de las opciones se guarda igual.
        motor_no_disponible = self._guardar_motor_y_voces(fijar, en_memoria)
        self._guardar_clave_elevenlabs(fijar, en_memoria)
        self._guardar_ajustes_voz(fijar, en_memoria)
        return motor_no_disponible

    def _guardar_motor_y_voces(self, fijar, en_memoria):
        motor_no_disponible = False
        if self._voces:
            motor = self._motor_elegido()
            fijar("voz", "motor", motor)
            en_memoria["motor"] = motor
            # Se guarda el nombre, no el número: el índice se corre al instalar
            # una voz y la app hablaría con otra sin avisar.
            nom_voz = self.cho_voz.GetStringSelection()
            fijar("voz", "voz", nom_voz)
            en_memoria["voz"] = nom_voz
            nom_ev = self.cho_voz_eventos.GetStringSelection()
            fijar("voz", "voz_eventos", nom_ev)
            en_memoria["voz_eventos"] = nom_ev
        else:
            motor_no_disponible = True
        return motor_no_disponible

    def _guardar_clave_elevenlabs(self, fijar, en_memoria):
        # Clave de ElevenLabs: es un secreto y va a credenciales.json, nunca al
        # ini. Solo se escribe si cambió.
        clave_eleven = self.txt_clave_eleven.GetValue().strip()
        if clave_eleven != (credenciales.cargar().get("elevenlabs_clave", "") or ""):
            credenciales.guardar_campo("elevenlabs_clave", clave_eleven)
        # Tope, «solo lo importante» y voz de respaldo de ElevenLabs se guardan
        # siempre, haya o no clave comprobada.
        tope_eleven = self.sp_tope_eleven.GetValue()
        fijar("voz", "elevenlabs_tope", str(tope_eleven))
        en_memoria["elevenlabs_tope"] = tope_eleven
        solo_importantes = self.chk_solo_importantes.GetValue()
        fijar("voz", "elevenlabs_solo_importantes",
              "true" if solo_importantes else "false")
        en_memoria["elevenlabs_solo_importantes"] = solo_importantes
        voz_respaldo = (self.cho_voz_respaldo.GetStringSelection()
                        if self._voces_respaldo else "")
        fijar("voz", "voz_respaldo", voz_respaldo)
        en_memoria["voz_respaldo"] = voz_respaldo

    def _guardar_ajustes_voz(self, fijar, en_memoria):
        self._cerrar_motor_prueba()
        from ytchat.voice import escala_voz
        velocidad = escala_voz.ajustar_velocidad(self.sp_velocidad.GetValue(), 0)
        fijar("voz", "velocidad_voz", str(velocidad))
        en_memoria["velocidad_voz"] = velocidad
        volumen = self.sp_volumen.GetValue()
        fijar("voz", "volumen", f"{volumen / 100:.2f}")
        en_memoria["volumen"] = round(volumen / 100.0, 2)
        tono = self.sp_tono.GetValue()
        fijar("voz", "tono", str(tono))
        en_memoria["tono"] = tono

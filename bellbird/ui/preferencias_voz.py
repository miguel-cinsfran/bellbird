"""Página Voces del diálogo de Preferencias.

Dueña de sus controles, de la prueba de voz, de ElevenLabs y de su guardado
propio. El diálogo la construye por composición.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _
from bellbird.youtube import credenciales
from bellbird.ui import clave_elevenlabs
from bellbird.ui.gui import ContadorAccesible, _T, _tc, anunciar
from bellbird.ui.preferencias_comun import crear_panel, fila_label
from bellbird.ui.preferencias_voz_secundaria import BloqueVozSecundaria
from bellbird.ui.prueba_voz import PruebaVoz

_SIN_CLAVE_ELEVEN = N_("(comprueba la clave)")
_NO_HAY_VOCES = N_("(no hay voces disponibles)")


class PaginaVoz:
    """Página Voces: motor, clave de ElevenLabs, prueba de voz y su guardado."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def construir(self, parent):
        p = crear_panel(parent, "PagVoz")
        self._pag_voz_panel = p
        vs = wx.BoxSizer(wx.VERTICAL)
        from bellbird.voice import motores

        motor_guardado = self._config.get("motor", "sapi")
        self._motor_idx = (motores.MOTORES.index(motor_guardado)
                           if motor_guardado in motores.MOTORES else 0)
        es_eleven = motores.MOTORES[self._motor_idx] == "elevenlabs"

        self._crear_motor(p, vs)
        lbl_clave = self._crear_clave(p, vs)
        self._crear_voz_lectura(p, vs, es_eleven)
        self._crear_ajustes(p, vs)
        self._crear_eleven(p, vs, lbl_clave)
        self._voz_secundaria = BloqueVozSecundaria(
            self._config, self._probar_voz_secundaria)
        vs.Add(self._voz_secundaria.construir(
            p, self._voces, self._voces_respaldo), 0, wx.EXPAND | wx.ALL, 10)
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
        from bellbird.voice import motores

        vs.Add(fila_label(p, _("&Motor de voz:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_motor = wx.Choice(
            p, choices=[_(motores.NOMBRES[m]) for m in motores.MOTORES],
            name=_("Motor de voz"))
        _tc(self.cho_motor)
        self.cho_motor.SetSelection(self._motor_idx)
        self.cho_motor.Bind(wx.EVT_CHOICE, self._on_motor_cambiado)
        vs.Add(self.cho_motor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _crear_clave(self, p, vs):
        # Clave de ElevenLabs y su comprobación: solo se ven con ese motor.
        lbl_clave = fila_label(p, _("Cl&ave de ElevenLabs:"))
        self.txt_clave_eleven = wx.TextCtrl(
            p, value=credenciales.cargar().get("elevenlabs_clave", "") or "",
            style=wx.TE_PASSWORD, name=_("Clave de ElevenLabs"))
        _tc(self.txt_clave_eleven)
        vs.Add(lbl_clave, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.txt_clave_eleven, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_comprobar_clave = wx.Button(
            p, label=_("Compro&bar clave"), name=_("Comprobar clave"))
        self.btn_comprobar_clave.SetBackgroundColour(_T.btn)
        self.btn_comprobar_clave.SetForegroundColour(_T.btn_t)
        self.btn_comprobar_clave.Bind(wx.EVT_BUTTON, self._on_comprobar_clave)
        vs.Add(self.btn_comprobar_clave, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        return lbl_clave

    def _crear_voz_lectura(self, p, vs, es_eleven):
        from bellbird.voice import motores

        # Voz del motor elegido. También está en el menú Voz → Seleccionar voz;
        # aquí queda junto al resto de ajustes de lectura para encontrarla más
        # fácil.
        vs.Add(fila_label(p, _("&Voz principal:")), 0, wx.LEFT | wx.RIGHT, 10)
        if es_eleven:
            # Nunca se va a la red en el hilo de la interfaz: la lista queda
            # vacía hasta que se compruebe la clave.
            self._voces = []
            vacio_voz = _SIN_CLAVE_ELEVEN
        else:
            self._voces = motores.listar_voces(motores.MOTORES[self._motor_idx])
            vacio_voz = _NO_HAY_VOCES
        self.cho_voz = wx.Choice(p, choices=self._voces or [vacio_voz],
                                  name=_("Voz principal"))
        _tc(self.cho_voz)
        self._cargar_voces(self.cho_voz, self._config.get("voz"), vacio=vacio_voz)
        vs.Add(self.cho_voz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _crear_ajustes(self, p, vs):
        from bellbird.voice import escala_voz

        # Velocidad, volumen y tono como valores absolutos 0..100.
        vs.Add(fila_label(p, _("Ve&locidad (0 a 100):")), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_velocidad = ContadorAccesible(
            p, min=0, max=100, name=_("Velocidad de la voz"),
            initial=escala_voz.ajustar_velocidad(
                int(self._config.get("velocidad_voz", escala_voz.VELOCIDAD_NORMAL)), 0))
        self.sp_velocidad.SetIncrement(5)
        _tc(self.sp_velocidad)
        vs.Add(self.sp_velocidad, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        try:
            vol_pct = max(0, min(100, int(round(float(self._config.get("volumen", 1.0)) * 100))))
        except (TypeError, ValueError):
            vol_pct = 100
        vs.Add(fila_label(p, _("Vol&umen (0 a 100):")), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_volumen = ContadorAccesible(
            p, min=0, max=100, initial=vol_pct, name=_("Volumen de la voz"))
        self.sp_volumen.SetIncrement(5)
        _tc(self.sp_volumen)
        vs.Add(self.sp_volumen, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(fila_label(p, _("&Tono (0 a 100):")), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_tono = ContadorAccesible(
            p, min=0, max=100, name=_("Tono de la voz"),
            initial=max(0, min(100, int(self._config.get("tono", 50)))))
        self.sp_tono.SetIncrement(5)
        _tc(self.sp_tono)
        vs.Add(self.sp_tono, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_probar_voz = wx.Button(p, label=_("&Probar voz"), name=_("Probar voz"))
        self.btn_probar_voz.SetBackgroundColour(_T.btn)
        self.btn_probar_voz.SetForegroundColour(_T.btn_t)
        self.btn_probar_voz.Bind(wx.EVT_BUTTON, self._on_probar_voz)
        vs.Add(self.btn_probar_voz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _crear_eleven(self, p, vs, lbl_clave):
        from bellbird.voice import escala_voz
        from bellbird.voice import motores

        # Tope de caracteres por sesión (0 sin tope), «solo lo importante» y
        # la voz de Windows de respaldo. Solo se ven con ElevenLabs.
        lbl_tope = fila_label(p, _("Límite de caracteres p&or sesión (0 sin límite):"))
        self.sp_tope_eleven = ContadorAccesible(
            p, min=0, max=1000000, name=_("Límite de caracteres de ElevenLabs"),
            initial=max(0, int(self._config.get("elevenlabs_tope", 0) or 0)))
        self.sp_tope_eleven.SetIncrement(1000)
        _tc(self.sp_tope_eleven)
        vs.Add(lbl_tope, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.sp_tope_eleven, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_solo_importantes = wx.CheckBox(
            p, name=_("Solo lo importante con ElevenLabs"),
            label=_("U&sar ElevenLabs solo con Super Chats, miembros, cofres, "
                    "propietario y moderadores"))
        self.chk_solo_importantes.SetForegroundColour(_T.text)
        self.chk_solo_importantes.SetValue(
            bool(self._config.get("elevenlabs_solo_importantes", False)))
        vs.Add(self.chk_solo_importantes, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        lbl_respaldo = fila_label(p, _("Voz de &Windows de respaldo:"))
        self._voces_respaldo = motores.listar_voces("sapi")
        self.cho_voz_respaldo = wx.Choice(
            p, choices=self._voces_respaldo or [_(_NO_HAY_VOCES)],
            name=_("Voz de Windows de respaldo"))
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

    def _mostrar_controles_eleven(self, visible: bool) -> None:
        for ctrl in getattr(self, "_eleven_ctrls", ()):
            ctrl.Show(visible)
        bloque = getattr(self, "_voz_secundaria", None)
        if bloque is not None:
            bloque.mostrar_respaldo(visible)
        panel = getattr(self, "_pag_voz_panel", None)
        if panel is not None:
            panel.Layout()

    def _preparar_voces_eleven(self, anunciar_ok: bool = False) -> None:
        self._voces = []
        self._cargar_voces(self.cho_voz, self._config.get("voz"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self._voz_secundaria.recargar_voces(self._voces)
        if self.txt_clave_eleven.GetValue().strip():
            self.btn_comprobar_clave.Disable()
            self._comprobar_clave(anunciar_ok)

    def _on_comprobar_clave(self, event) -> None:
        if not self.txt_clave_eleven.GetValue().strip():
            anunciar(_("Escribe la clave de ElevenLabs."))
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
        self._voz_secundaria.recargar_voces(self._voces)
        if anunciar_ok:
            anunciar(clave_elevenlabs.texto_clave_valida(
                len(self._voces), usados, limite))

    def _clave_fallo(self, mensaje) -> None:
        if not self._ventana:
            return
        self.btn_comprobar_clave.Enable()
        self._voces = []
        self._cargar_voces(self.cho_voz, None, vacio=_SIN_CLAVE_ELEVEN)
        self._voz_secundaria.recargar_voces(self._voces)
        anunciar(mensaje)

    def _cargar_voces(self, choice, guardada, vacio=_NO_HAY_VOCES) -> None:
        from bellbird.voice import escala_voz

        if self._voces:
            choice.SetItems(self._voces)
            idx = escala_voz.resolver_voz(guardada, self._voces)
            choice.SetSelection(0 if idx is None else idx)
            choice.Enable(True)
        else:
            choice.SetItems([_(vacio)])
            choice.SetSelection(0)
            choice.Disable()

    def _motor_elegido(self) -> str:
        from bellbird.voice import motores

        i = self.cho_motor.GetSelection()
        return motores.MOTORES[i] if 0 <= i < len(motores.MOTORES) else "sapi"

    def _on_motor_cambiado(self, event) -> None:
        # Repuebla las voces del motor nuevo sin anunciar: el lector ya lee el
        # valor del combinado al recorrerlo. Con ElevenLabs, además, se ocultan
        # o muestran sus controles y se comprueba la clave en segundo plano.
        from bellbird.voice import motores

        motor = self._motor_elegido()
        if motor == "elevenlabs":
            self._mostrar_controles_eleven(True)
            self._preparar_voces_eleven()
            return
        self._mostrar_controles_eleven(False)
        self._voces = motores.listar_voces(motor)
        self._cargar_voces(self.cho_voz, self._config.get("voz"))
        self._voz_secundaria.recargar_voces(self._voces)

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
            anunciar(_("Primero comprueba la clave."))
            return
        self._prueba.probar_elevenlabs(
            self.txt_clave_eleven.GetValue().strip(),
            self.cho_voz.GetStringSelection(),
            self.sp_velocidad.GetValue(), self.sp_volumen.GetValue())

    def _probar_voz_secundaria(self) -> None:
        from bellbird.voice import escala_voz

        motor = self._motor_elegido()
        voz, velocidad, volumen = self._voz_secundaria.datos_de_prueba()
        if motor == "elevenlabs":
            if not self._voces:
                anunciar(_("Primero comprueba la clave."))
                return
            self._prueba.probar_elevenlabs(
                self.txt_clave_eleven.GetValue().strip(),
                voz or self.cho_voz.GetStringSelection(), velocidad, volumen)
            return
        indice = escala_voz.resolver_voz(voz, self._voces) if voz else None
        if indice is None:
            indice = self.cho_voz.GetSelection()
        self._prueba.probar_prism(
            motor, indice, velocidad, volumen, self.sp_tono.GetValue())

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
        self._voz_secundaria.guardar(fijar, en_memoria, bool(self._voces))
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
        from bellbird.voice import escala_voz
        velocidad = escala_voz.ajustar_velocidad(self.sp_velocidad.GetValue(), 0)
        fijar("voz", "velocidad_voz", str(velocidad))
        en_memoria["velocidad_voz"] = velocidad
        volumen = self.sp_volumen.GetValue()
        fijar("voz", "volumen", f"{volumen / 100:.2f}")
        en_memoria["volumen"] = round(volumen / 100.0, 2)
        tono = self.sp_tono.GetValue()
        fijar("voz", "tono", str(tono))
        en_memoria["tono"] = tono

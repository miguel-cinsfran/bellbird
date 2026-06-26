"""PersonasDialog — manage assistant personas (CRUD + apply).

Layout: ListBox (left) + TextCtrl fields (right) + button row at bottom.
StaticText labels precede every control (NVDA UIA z-order rule).
Accessible with NVDA: wx.ListBox + wx.Button natives only.
"""

import wx

from bellbird.core.personas import (
    Persona,
    apply_persona,
    find_by_id,
    get_active_personas,
    load_personas,
    reset_builtin,
    save_personas,
)


class PersonasDialog(wx.Dialog):
    """Dialog for viewing, selecting, creating and editing personas."""

    def __init__(self, parent: wx.Window, config) -> None:
        super().__init__(parent, title="Personas / asistentes", size=(700, 500))
        self._config = config
        self._personas: list[Persona] = load_personas()
        self._dirty = False
        self._build_ui()
        self._populate_list()
        self._select_active()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        # Main area: list + detail panel side by side
        main_row = wx.BoxSizer(wx.HORIZONTAL)

        # Left: list
        left = wx.BoxSizer(wx.VERTICAL)
        lbl_list = wx.StaticText(self, label="&Personas disponibles:")
        self._listbox = wx.ListBox(self, name="personas_list", style=wx.LB_SINGLE)
        self._listbox.Bind(wx.EVT_LISTBOX, self._on_select)
        left.Add(lbl_list, 0, wx.BOTTOM, 4)
        left.Add(self._listbox, 1, wx.EXPAND)
        main_row.Add(left, 1, wx.EXPAND | wx.RIGHT, 8)

        # Right: detail fields
        right = wx.BoxSizer(wx.VERTICAL)

        lbl_nombre = wx.StaticText(self, label="&Nombre:")
        self._txt_nombre = wx.TextCtrl(self, name="persona_nombre")
        right.Add(lbl_nombre, 0, wx.BOTTOM, 2)
        right.Add(self._txt_nombre, 0, wx.EXPAND | wx.BOTTOM, 8)

        lbl_prompt = wx.StaticText(self, label="&System prompt:")
        self._txt_prompt = wx.TextCtrl(
            self, name="persona_prompt", style=wx.TE_MULTILINE, size=(-1, 200)
        )
        right.Add(lbl_prompt, 0, wx.BOTTOM, 2)
        right.Add(self._txt_prompt, 1, wx.EXPAND | wx.BOTTOM, 8)

        lbl_activa = wx.StaticText(self, label="Visibili&dad:")
        self._chk_activa = wx.CheckBox(self, label="Visible en el &menú", name="persona_activa_chk")
        right.Add(lbl_activa, 0, wx.BOTTOM, 2)
        right.Add(self._chk_activa, 0, wx.BOTTOM, 8)

        # Action buttons for the detail panel
        detail_btns = wx.BoxSizer(wx.HORIZONTAL)
        self._btn_guardar = wx.Button(self, label="&Guardar cambios", name="btn_guardar_persona")
        self._btn_restablecer = wx.Button(self, label="&Restablecer original", name="btn_restablecer_persona")
        self._btn_nueva = wx.Button(self, label="&Nueva persona", name="btn_nueva_persona")
        self._btn_eliminar = wx.Button(self, label="&Eliminar", name="btn_eliminar_persona")
        detail_btns.Add(self._btn_guardar, 0, wx.RIGHT, 4)
        detail_btns.Add(self._btn_restablecer, 0, wx.RIGHT, 4)
        detail_btns.Add(self._btn_nueva, 0, wx.RIGHT, 4)
        detail_btns.Add(self._btn_eliminar)
        right.Add(detail_btns, 0)
        main_row.Add(right, 2, wx.EXPAND)
        outer.Add(main_row, 1, wx.EXPAND | wx.ALL, 12)

        # Bottom: Apply + Close
        bottom = wx.BoxSizer(wx.HORIZONTAL)
        self._btn_aplicar = wx.Button(self, label="&Aplicar persona seleccionada", name="btn_aplicar_persona")
        btn_ninguna = wx.Button(self, label="Sin persona (&ninguna)", name="btn_ninguna_persona")
        btn_cerrar = wx.Button(self, id=wx.ID_CANCEL, label="&Cerrar", name="btn_cerrar_personas")
        bottom.Add(self._btn_aplicar, 0, wx.RIGHT, 4)
        bottom.Add(btn_ninguna, 0, wx.RIGHT, 4)
        bottom.Add(btn_cerrar)
        outer.Add(bottom, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(outer)

        # Bindings
        self._btn_guardar.Bind(wx.EVT_BUTTON, self._on_guardar)
        self._btn_restablecer.Bind(wx.EVT_BUTTON, self._on_restablecer)
        self._btn_nueva.Bind(wx.EVT_BUTTON, self._on_nueva)
        self._btn_eliminar.Bind(wx.EVT_BUTTON, self._on_eliminar)
        self._btn_aplicar.Bind(wx.EVT_BUTTON, self._on_aplicar)
        btn_ninguna.Bind(wx.EVT_BUTTON, self._on_ninguna)

    # ── List management ────────────────────────────────────────────────────────

    def _populate_list(self) -> None:
        self._listbox.Clear()
        for p in self._personas:
            label = p.nombre
            if not p.activa:
                label = f"[oculta] {p.nombre}"
            self._listbox.Append(label)

    def _select_active(self) -> None:
        active_id = self._config.persona_activa
        if active_id:
            for i, p in enumerate(self._personas):
                if p.id == active_id:
                    self._listbox.SetSelection(i)
                    self._load_detail(p)
                    return
        if self._personas:
            self._listbox.SetSelection(0)
            self._load_detail(self._personas[0])

    def _current_persona(self) -> Persona | None:
        sel = self._listbox.GetSelection()
        if sel == wx.NOT_FOUND or sel >= len(self._personas):
            return None
        return self._personas[sel]

    def _load_detail(self, p: Persona) -> None:
        self._txt_nombre.SetValue(p.nombre)
        self._txt_prompt.SetValue(p.system_prompt)
        self._chk_activa.SetValue(p.activa)
        is_builtin = p.builtin
        self._btn_restablecer.Enable(is_builtin)
        self._btn_eliminar.Enable(not is_builtin)

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_select(self, _evt) -> None:
        p = self._current_persona()
        if p:
            self._load_detail(p)

    def _on_guardar(self, _evt) -> None:
        p = self._current_persona()
        if p is None:
            return
        p.nombre = self._txt_nombre.GetValue().strip() or p.nombre
        p.system_prompt = self._txt_prompt.GetValue()
        p.activa = self._chk_activa.GetValue()
        sel = self._listbox.GetSelection()
        self._populate_list()
        self._listbox.SetSelection(sel)
        self._dirty = True

    def _on_restablecer(self, _evt) -> None:
        p = self._current_persona()
        if p is None or not p.builtin:
            return
        self._personas = reset_builtin(self._personas, p.id)
        sel = self._listbox.GetSelection()
        self._populate_list()
        self._listbox.SetSelection(sel)
        restored = self._personas[sel]
        self._load_detail(restored)
        self._dirty = True

    def _on_nueva(self, _evt) -> None:
        import uuid
        nueva = Persona(
            id=f"user_{uuid.uuid4().hex[:8]}",
            nombre="Nueva persona",
            system_prompt="",
            builtin=False,
            activa=True,
        )
        self._personas.append(nueva)
        self._populate_list()
        idx = len(self._personas) - 1
        self._listbox.SetSelection(idx)
        self._load_detail(nueva)
        self._txt_nombre.SetFocus()
        self._dirty = True

    def _on_eliminar(self, _evt) -> None:
        p = self._current_persona()
        if p is None or p.builtin:
            return
        sel = self._listbox.GetSelection()
        self._personas.pop(sel)
        self._populate_list()
        new_sel = min(sel, len(self._personas) - 1)
        if new_sel >= 0:
            self._listbox.SetSelection(new_sel)
            self._load_detail(self._personas[new_sel])
        self._dirty = True

    def _on_aplicar(self, _evt) -> None:
        p = self._current_persona()
        apply_persona(self._config, p)
        if self._dirty:
            save_personas(self._personas)
            self._dirty = False
        self.EndModal(wx.ID_OK)

    def _on_ninguna(self, _evt) -> None:
        apply_persona(self._config, None)
        if self._dirty:
            save_personas(self._personas)
            self._dirty = False
        self.EndModal(wx.ID_OK)

    def save_if_dirty(self) -> None:
        if self._dirty:
            save_personas(self._personas)
            self._dirty = False

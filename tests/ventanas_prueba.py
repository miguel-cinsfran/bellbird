"""Libera las ventanas de primer nivel creadas en las pruebas.

En wx, Destroy() de una ventana de primer nivel no la libera en el
momento: queda pendiente hasta que corre el bucle de eventos, que en
las pruebas no corre (medido: unos 235 objetos por diálogo, 2.844 a
los 12; Windows corta en 10.000). SafeYield deja que wx la libere.

Medido el 18/10/2026: liberar de verdad `TransmisionDialog` tumba el
proceso al salir (violación de acceso durante la recolección final), así
que solo `PreferenciasDialog` se libera de verdad; es el diálogo que
agota los objetos de ventana, unos 235 cada uno. Las demás se esconden:
quedan fuera del SafeYield y no se borran de rebote al liberar un
Preferencias.
"""


def destruir(ventana) -> None:
    """Libera la ventana según su tipo; nunca lanza."""
    try:
        import wx
        if not ventana:
            return
        from ytchat.ui.gui_preferencias import PreferenciasDialog
        if isinstance(ventana, PreferenciasDialog):
            ventana.Destroy()
            wx.SafeYield()
            return
        if isinstance(ventana, wx.App):
            ventana.Destroy()
            return
        ventana.Hide()
    except Exception:
        pass

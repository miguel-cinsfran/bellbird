"""Libera las ventanas de primer nivel creadas en las pruebas.

En wx, el Destroy() de una ventana de primer nivel queda pendiente
hasta que corre el bucle de eventos, que en las pruebas no corre y los
objetos USER se acumulan hasta el tope de Windows. Por eso destruir
llama a wx.SafeYield() después del Destroy(), para que wx la libere en
el momento.
"""


def destruir(ventana) -> None:
    """Libera la ventana con Destroy y SafeYield; nunca lanza."""
    try:
        import wx
        if not ventana:
            return
        if isinstance(ventana, wx.App):
            ventana.Destroy()
            return
        ventana.Destroy()
        wx.SafeYield()
    except Exception:
        pass

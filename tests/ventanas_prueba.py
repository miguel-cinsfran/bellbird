"""Libera las ventanas de primer nivel creadas en las pruebas.

En wx, el Destroy() de una ventana de primer nivel queda pendiente
hasta que corre el bucle de eventos, que en las pruebas no corre y los
objetos USER se acumulan hasta el tope de Windows. Por eso destruir
llama a wx.SafeYield() después del Destroy(), para que wx la libere en
el momento.
"""


_APP = None


def app_de_prueba():
    """Devuelve una sola wx.App sostenida hasta el final del proceso.

    unittest suelta cada prueba al terminarla y el App moría con ella.
    """
    global _APP
    import wx
    if _APP is None:
        _APP = wx.App.Get() or wx.App(False)
    return _APP


def destruir(ventana) -> None:
    """Libera la ventana con Destroy y SafeYield; nunca lanza."""
    try:
        import wx
        if not ventana:
            return
        if isinstance(ventana, wx.App):
            ventana.Destroy()
            return
        for nombre in ("_timer", "_diagnostico_timer"):
            temporizador = getattr(ventana, nombre, None)
            if temporizador is not None:
                try:
                    temporizador.Stop()
                except Exception:
                    pass
        if hasattr(ventana, "_alive"):
            ventana._alive = False
        ventana.Destroy()
        wx.SafeYield()
    except Exception:
        pass

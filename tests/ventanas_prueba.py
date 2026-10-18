"""Libera de verdad las ventanas de primer nivel creadas en las pruebas.

En wx, Destroy() de una ventana de primer nivel no la libera en el
momento: queda pendiente hasta que corre el bucle de eventos, que en
las pruebas no corre (medido: unos 235 objetos por diálogo, 2.844 a
los 12; Windows corta en 10.000). SafeYield deja que wx la libere.
"""


def destruir(ventana) -> None:
    """Destruye la ventana y deja que wx la libere; nunca lanza."""
    try:
        import wx
        if ventana:
            ventana.Destroy()
            wx.SafeYield()
    except Exception:
        pass

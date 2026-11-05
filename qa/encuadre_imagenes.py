"""Imágenes vivas para el escenario de encuadre del banco de QA.

La fuente de imagen de OBS entrega el mismo cuadro mientras no cambie su
archivo, y el detector toma una imagen quieta por una cámara congelada. Estas
variantes cambian un solo píxel para que la huella sea distinta sin cambiar lo
que se ve, y el alternador las va mandando mientras la aplicación observa.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

INTERVALO = 0.4


def _bmp_gris(ruta, ancho=160, alto=120, tono=128):
    """Un BMP gris de 24 bits, para tapar el rostro en la prueba."""
    import struct
    fila = bytes([tono, tono, tono]) * ancho
    fila += b"\x00" * ((4 - len(fila) % 4) % 4)
    datos = fila * alto
    cabecera = struct.pack("<2sIHHI", b"BM", 54 + len(datos), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, ancho, alto, 1, 24, 0,
                       len(datos), 0, 0, 0, 0)
    ruta.write_bytes(cabecera + info + datos)


def _dos_variantes(carpeta, imagen, prefijo):
    """Escribe dos BMP de `imagen` que difieren en un solo píxel."""
    import cv2
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    cambiada = imagen.copy()
    valor = int(cambiada[0, 0, 0])
    cambiada[0, 0, 0] = 0 if valor != 0 else 255
    rutas = (carpeta / f"{prefijo}-a.bmp", carpeta / f"{prefijo}-b.bmp")
    for ruta, cuadro in zip(rutas, (imagen, cambiada)):
        _ok, datos = cv2.imencode(".bmp", cuadro)
        if not _ok:
            raise ValueError(f"No se pudo codificar {ruta.name} como BMP")
        ruta.write_bytes(bytes(datos))
    return rutas


def variantes_foto(carpeta, ruta=None):
    """Dos BMP de `rostro.jpg` que difieren en un solo píxel."""
    import cv2
    import numpy
    if ruta is None:
        ruta = (Path(__file__).resolve().parent.parent / "tests" / "datos"
                / "rostro.jpg")
    datos = Path(ruta).read_bytes()
    imagen = cv2.imdecode(numpy.frombuffer(datos, dtype=numpy.uint8),
                          cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError(f"No se pudo decodificar {ruta} como imagen")
    return _dos_variantes(carpeta, imagen, "foto")


def variantes_gris(carpeta):
    """Dos BMP grises que difieren en un solo píxel."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = (carpeta / "gris-a.bmp", carpeta / "gris-b.bmp")
    _bmp_gris(rutas[0])
    _bmp_gris(rutas[1])
    datos = bytearray(rutas[1].read_bytes())
    datos[54] ^= 1
    rutas[1].write_bytes(bytes(datos))
    return rutas


class Alternador:
    """Mantiene viva la fuente de imagen alternando dos variantes.

    `mostrar` elige la imagen en el momento y devuelve el instante del cambio,
    para medir desde ahí lo que tarde el aviso. El hilo cambia de variante cada
    `intervalo` segundos. Si OBS falla, guarda la excepción en `fallo` y sigue.
    """

    def __init__(self, gestor, nombre, variantes, intervalo=INTERVALO):
        self._gestor = gestor
        self._nombre = nombre
        self._variantes = {cual: tuple(rutas)
                           for cual, rutas in variantes.items()}
        self._intervalo = intervalo
        self._cerrojo = threading.Lock()
        self._parar = threading.Event()
        self._actual = next(iter(self._variantes))
        self._indice = 0
        self.fallo = None
        self.hilo = threading.Thread(target=self._bucle, daemon=True,
                                     name="qa-encuadre-imagenes")
        self.hilo.start()

    def mostrar(self, cual):
        """Cambia a `cual` en el momento y devuelve el instante del cambio."""
        with self._cerrojo:
            instante = time.monotonic()
            self._actual = cual
            self._indice = 0
            self._mandar(cual)
        return instante

    def _mandar(self, cual):
        ruta = self._variantes[cual][self._indice]
        try:
            self._gestor._pedir("SetInputSettings",
                                {"inputName": self._nombre,
                                 "inputSettings": {"file": str(ruta)}})
        except Exception as exc:
            if self.fallo is None:
                self.fallo = exc

    def _bucle(self):
        while not self._parar.wait(self._intervalo):
            with self._cerrojo:
                self._indice = ((self._indice + 1)
                                % len(self._variantes[self._actual]))
                self._mandar(self._actual)

    def detener(self):
        """Para el hilo y espera a que termine."""
        self._parar.set()
        self.hilo.join()

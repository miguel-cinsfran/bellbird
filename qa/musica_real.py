"""Estado y atajos del recorrido de música real."""

from __future__ import annotations

import re
import time
from pathlib import Path

try:
    import medidor_sonido
except Exception:
    medidor_sonido = None

# Cuánto puede durar el recorrido entero antes de cortarlo.
_TOPE_RECORRIDO = 6 * 60


class _Corte(Exception):
    """La escena no puede seguir (el fallo ya quedó anotado)."""


def agujas_unicas(nombres, indice, tope=6):
    """Búsquedas cortas que solo encuentran al tema elegido.

    Las candidatas salen de las palabras del nombre sin extensión, de la
    palabra sola al nombre entero. Se comprueban con la misma regla del
    buscador de la aplicación: cada palabra buscada empieza una palabra del
    nombre, título, artista o álbum.
    """
    from bellbird.music.biblioteca import coincide_por_palabras
    if tope <= 0:
        return []
    nombres_sin_extension = [Path(nombre).stem for nombre in nombres]
    palabras = re.findall(r"[^\W_]+", nombres_sin_extension[indice])
    candidatas = []
    for cantidad in range(1, len(palabras) + 1):
        for inicio in range(len(palabras) - cantidad + 1):
            aguja = " ".join(palabras[inicio:inicio + cantidad])
            if aguja not in candidatas:
                candidatas.append(aguja)
    agujas = []
    for aguja in candidatas:
        encontrados = [
            i for i, nombre in enumerate(nombres_sin_extension)
            if coincide_por_palabras(aguja, [nombre])]
        if encontrados == [indice]:
            agujas.append(aguja)
            if len(agujas) >= tope:
                break
    return agujas


def aguja_grupo(nombres, incluidos, excluidos):
    """La palabra común que encuentra a todo el grupo y a ningún excluido.

    Se comprueba con la misma regla del buscador de la aplicación, así una
    palabra que solo es prefijo de otra no sirve para aislar el grupo.
    """
    import re
    from bellbird.music.biblioteca import coincide_por_palabras
    nombres_sin_extension = [Path(nombre).stem for nombre in nombres]
    comunes = set.intersection(*[
        set(re.findall(r"[^\W_]+", nombres_sin_extension[i]))
        for i in incluidos])
    for aguja in sorted(comunes, key=lambda palabra: (-len(palabra), palabra)):
        if len(aguja) < 2:
            continue
        if not all(coincide_por_palabras(aguja, [nombres_sin_extension[i]])
                   for i in incluidos):
            continue
        if any(coincide_por_palabras(aguja, [nombres_sin_extension[i]])
               for i in excluidos):
            continue
        return aguja
    return None


class RecorridoMusica:
    """Estado compartido y atajos de la ventana Música durante el recorrido."""

    def __init__(self, app, args, res):
        self.app = app
        self.args = args
        self.res = res
        self.propia = None
        self.pids = set()
        self.nombres_archivo = []
        self.sin_salida = False
        self.ruta_config = None
        self.ruta_listas = None
        self.ruta_estado = None
        self.ruta_etiquetas = None
        self.tmp_musica = None
        self.tmp_respaldo = None
        self.respaldo_config = None
        self.respaldo_estado = None
        self.respaldo_etiquetas = None
        self.listas_habia = False
        self._tope = None

    def corta(self, texto):
        """Anota el fallo y corta la escena."""
        self.res.fallo(texto)
        raise _Corte()

    def _agujas_unicas(self, indice, tope=6):
        return agujas_unicas(self.nombres_archivo, indice, tope)

    def _aguja_grupo(self, incluidos, excluidos):
        return aguja_grupo(self.nombres_archivo, incluidos, excluidos)

    def _arbol(self, ventana):
        return self.propia.arbol(ventana)

    def _filas(self, ventana, nombre):
        for control in self._arbol(ventana):
            if (control.get("clase") == "ListBox"
                    and (control.get("nombre") or "") == nombre):
                return list(control.get("items", []))
        return None

    def _filas_hasta(self, ventana, nombre, cantidad, segundos):
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            filas = self._filas(ventana, nombre)
            if filas is not None and len(filas) == cantidad:
                return filas
            time.sleep(0.2)
        return self._filas(ventana, nombre)

    def _filas_estables(self, ventana, nombre, segundos=8.0):
        # Las etiquetas se leen en un hilo y cambian los títulos: se
        # espera a que se asienten antes de tomarlos como esperados.
        anteriores = self._filas(ventana, nombre) or []
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            time.sleep(1.2)
            actuales = self._filas(ventana, nombre) or []
            if actuales and actuales == anteriores:
                return actuales
            anteriores = actuales
        return anteriores

    def _titulo_fila(self, fila):
        # Quita el prefijo que pone `bellbird.music.vista.filas_cola`:
        # el estado («Sonando: » o «En pausa: »), el número y el punto.
        # La fila sigue con el título, el artista y la duración separados
        # por «, », así que el título es lo que queda antes de la primera.
        texto = fila
        for prefijo in ("Sonando: ", "En pausa: "):
            if texto.startswith(prefijo):
                texto = texto[len(prefijo):]
                break
        punto = texto.find(". ")
        if punto > 0 and texto[:punto].isdigit():
            texto = texto[punto + 2:]
        return texto.split(", ", 1)[0]

    def _filtrar(self, ventana, texto):
        self.propia.pedir("foco", ventana=ventana,
                          nombre="Buscar en la música")
        self.propia.pedir("texto", valor=texto)

    def _pico(self):
        try:
            return medidor_sonido.pico(self.pids)
        except Exception:
            return None

    def _menu(self, etiqueta):
        try:
            self.propia.abrir_por_menu(etiqueta)
        except Exception as exc:
            self.corta(f"musica_real: el menú no tiene «{etiqueta}»: {exc}")

    def _elegir(self, ventana, nombre, indice):
        self.propia.pedir("elegir", ventana=ventana, nombre=nombre,
                          indice=indice)

    def _menu_contextual(self, ventana, nombre, entrada, responder_ya=False):
        self.propia.pedir("menu_contextual", ventana=ventana, nombre=nombre,
                          entrada=entrada, responder_ya=responder_ya)

    def _aislar(self, indice, esperado):
        for aguja in self._agujas_unicas(indice):
            self._filtrar("Música", aguja)
            filas = self._filas_hasta("Música", "Canciones", 1, 5.0)
            if filas is not None and len(filas) == 1:
                titulo = self._titulo_fila(filas[0])
                if titulo != esperado:
                    self.corta(f"musica_real: el buscador aisló "
                               f"«{filas[0]}» en vez de «{esperado}»")
                return titulo
        self.corta(f"musica_real: no se pudo aislar «{esperado}» "
                   "con el buscador")

    def _boton_aceptar(self, ventana):
        for control in self._arbol(ventana):
            if control.get("clase") not in ("Button", "BitmapButton"):
                continue
            texto = ((control.get("nombre") or "") + " "
                     + (control.get("etiqueta") or "")).lower()
            if ("aceptar" in texto or texto.strip() == "ok"
                    or " ok " in f" {texto} "):
                return (control.get("nombre")
                        or control.get("etiqueta"))
        return None

    def _escribir_cuadro(self, ventana, valor):
        campo = next((c for c in self._arbol(ventana)
                      if c.get("clase") == "TextCtrl"), None)
        if campo is None:
            self.corta(f"musica_real: «{ventana}» no tiene cuadro de texto")
        nombre = campo.get("nombre") or campo.get("etiqueta")
        if nombre:
            try:
                self.propia.pedir("foco", ventana=ventana, nombre=nombre)
            except Exception as exc:
                self.corta(f"musica_real: no se llega al cuadro de "
                           f"«{ventana}»: {exc}")
        self.propia.pedir("texto", valor=valor)
        for control in self._arbol(ventana):
            if control.get("clase") == "TextCtrl":
                if (control.get("valor") or "") == valor:
                    return
                self.corta(f"musica_real: el cuadro de «{ventana}» no tomó "
                           f"«{valor}»")

    def _pulsar_aceptar(self, ventana):
        nombre = self._boton_aceptar(ventana)
        if nombre is None:
            self.corta(f"musica_real: «{ventana}» no ofrece ningún botón "
                       "para aceptar")
        self.propia.pedir("pulsar", nombre=nombre, ventana=ventana)
        if self.propia.esperar_ventana(ventana, segundos=3) is not None:
            self.corta(f"musica_real: «{ventana}» no cerró al aceptar")

    def _pulsar_y_cerrar(self, ventana, boton):
        self.propia.pedir("pulsar", nombre=boton, ventana=ventana)
        if self.propia.esperar_ventana(ventana, segundos=3) is not None:
            self.corta(f"musica_real: «{ventana}» no cerró al pulsar "
                       f"«{boton}»")

    def _aire(self):
        if time.monotonic() > self._tope:
            self.corta("musica_real: se pasó de 6 minutos, "
                       "se corta el recorrido")
        return True

"""Seguimiento y frases de las encuestas de un directo de TikTok.

Puro y sin wx ni TikTokLive. Única razón para cambiar: cómo se sigue y se
nombra una encuesta. Las frases son funciones puras; el registro guarda el
estado con un candado porque lo escribe el hilo de la captura y lo lee F2
desde el hilo de la interfaz.
"""

from __future__ import annotations

import threading

from bellbird.core.idioma import _, ngettext


def _unir(textos: list[str]) -> str:
    """Lista con comas y «y» final, en formatos completos traducibles."""
    if not textos:
        return ""
    if len(textos) == 1:
        return textos[0]
    if len(textos) == 2:
        return _("{a} y {b}").format(a=textos[0], b=textos[1])
    return _("{primeros} y {ultimo}").format(
        primeros=", ".join(textos[:-1]), ultimo=textos[-1])


def _con_votos(opcion: str, votos: int) -> str:
    if votos <= 0:
        return _("{opcion} sin votos").format(opcion=opcion)
    return _("{opcion} con {votos}").format(
        opcion=opcion,
        votos=ngettext("{n} voto", "{n} votos", votos).format(n=votos))


def _cabecera_cierre(titulo: str) -> str:
    titulo = (titulo or "").strip()
    if titulo:
        return _("Encuesta terminada: {titulo}").format(titulo=titulo)
    return _("Encuesta terminada.")


def frase_apertura(titulo: str, opciones) -> str:
    """Frase que se lee al abrirse una encuesta."""
    lista = _unir([texto for texto, _votos in opciones])
    titulo = (titulo or "").strip()
    if titulo:
        # Traductores: {titulo} es la pregunta y {opciones} la lista de opciones.
        return _("Encuesta: {titulo} Opciones: {opciones}").format(
            titulo=titulo, opciones=lista)
    # Traductores: {opciones} es la lista de opciones de la encuesta.
    return _("Encuesta abierta. Opciones: {opciones}").format(opciones=lista)


def _resultado_cierre(opciones) -> str:
    ordenadas = sorted(opciones, key=lambda par: par[1], reverse=True)
    maximo = ordenadas[0][1]
    ganadores = [texto for texto, votos in ordenadas if votos == maximo]
    resto = [(texto, votos) for texto, votos in ordenadas if votos != maximo]
    votos_texto = ngettext("{n} voto", "{n} votos", maximo).format(n=maximo)
    if len(ganadores) == 1:
        principal = _("Ganó {opcion} con {votos}").format(
            opcion=ganadores[0], votos=votos_texto)
    else:
        principal = _("Empate entre {opciones} con {votos}").format(
            opciones=_unir(ganadores), votos=votos_texto)
    if not resto:
        return principal
    return _("{principal}, {resto}").format(
        principal=principal,
        resto=_unir([_con_votos(texto, votos) for texto, votos in resto]))


def frase_cierre(titulo: str, opciones) -> str:
    """Frase que se lee al cerrarse una encuesta, con su resultado."""
    if not opciones:
        resultado = _("Sin votos")
    elif not any(votos for _texto, votos in opciones):
        resultado = _("Sin votos")
    else:
        resultado = _resultado_cierre(opciones)
    return _("{cabecera} {resultado}").format(
        cabecera=_cabecera_cierre(titulo), resultado=resultado)


def frase_en_curso(titulo: str, opciones) -> str:
    """Frase de F2 con los votos de la encuesta abierta."""
    lista = _unir([_con_votos(texto, votos) for texto, votos in opciones])
    titulo = (titulo or "").strip()
    if titulo:
        return _("Encuesta en curso: {titulo} {opciones}").format(
            titulo=titulo, opciones=lista)
    return _("Encuesta en curso. {opciones}").format(opciones=lista)


class RegistroEncuestas:
    """Encuestas vistas, con un candado para captura e interfaz."""

    def __init__(self):
        self._candado = threading.Lock()
        self._encuestas: dict[str, dict] = {}
        self._orden: list[str] = []

    @staticmethod
    def _clave(id_encuesta) -> str:
        return str(id_encuesta if id_encuesta is not None else "").strip()

    def _nueva(self, clave: str) -> dict:
        estado = {"titulo": "", "opciones": [], "abierta": False,
                  "apertura_anunciada": False, "cierre_anunciado": False}
        self._encuestas[clave] = estado
        self._orden.append(clave)
        return estado

    def abrir(self, id_encuesta, titulo, opciones) -> bool:
        """Guarda la apertura. Verdadero solo la primera vez que se anuncia."""
        clave = self._clave(id_encuesta)
        with self._candado:
            estado = self._encuestas.get(clave) or self._nueva(clave)
            if estado["cierre_anunciado"] or estado["apertura_anunciada"]:
                if not estado["cierre_anunciado"]:
                    estado["opciones"] = list(opciones or [])
                    if titulo:
                        estado["titulo"] = titulo
                return False
            if titulo:
                estado["titulo"] = titulo
            estado["opciones"] = list(opciones or [])
            estado["abierta"] = True
            estado["apertura_anunciada"] = True
            return True

    def votos(self, id_encuesta, opciones) -> None:
        """Actualiza los votos sin anunciar nada."""
        clave = self._clave(id_encuesta)
        with self._candado:
            estado = self._encuestas.get(clave) or self._nueva(clave)
            if estado["cierre_anunciado"]:
                return
            estado["abierta"] = True
            estado["opciones"] = list(opciones or [])

    def cerrar(self, id_encuesta, titulo, opciones) -> bool:
        """Guarda el cierre. Verdadero solo la primera vez que se anuncia."""
        clave = self._clave(id_encuesta)
        with self._candado:
            estado = self._encuestas.get(clave) or self._nueva(clave)
            if estado["cierre_anunciado"]:
                return False
            if titulo:
                estado["titulo"] = titulo
            if opciones:
                estado["opciones"] = list(opciones)
            estado["abierta"] = False
            estado["cierre_anunciado"] = True
            return True

    def titulo_de(self, id_encuesta) -> str:
        """Título guardado, para el cierre que no lo trae en su contenido."""
        with self._candado:
            estado = self._encuestas.get(self._clave(id_encuesta))
            return estado["titulo"] if estado else ""

    def en_curso(self) -> str:
        """Frase de la encuesta abierta, o vacío si no hay ninguna."""
        with self._candado:
            for clave in reversed(self._orden):
                estado = self._encuestas[clave]
                if estado["abierta"] and not estado["cierre_anunciado"]:
                    return frase_en_curso(estado["titulo"], estado["opciones"])
            return ""

    def reiniciar(self) -> None:
        """Olvida todo, para una conexión nueva del directo."""
        with self._candado:
            self._encuestas.clear()
            self._orden.clear()


registro = RegistroEncuestas()

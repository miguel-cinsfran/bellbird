"""Cuándo y qué se anuncia del avance de las descargas, sin wx.

Recibe la lista de descargas y el instante en cada vuelta. Guarda, por
descarga, el último múltiplo anunciado y el instante del último aviso de
descarga quieta. Su única razón para cambiar es esa regla.
"""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.core.idioma import _

TIPO_AVANCE = "avance"
TIPO_QUIETA = "quieta"
INTERVALO_QUIETA_S = 15.0
PROGRESO_QUIETO = 1.0


@dataclass(frozen=True)
class Aviso:
    """Lo que hay que decir en esta vuelta y con qué sonido."""

    tipo: str
    texto: str


@dataclass
class _Seguimiento:
    multiplo: int
    inicio: float
    ultimo_quieta: float | None = None
    paso_uno: bool = False


def _en_curso(descarga) -> bool:
    return descarga.estado == "descargando" and not descarga.procesando


def _multiplo_actual(progreso: float) -> int:
    """El último múltiplo de 10 alcanzado, entre 0 y 90."""
    return min(90, max(0, int(progreso // 10) * 10))


def _nombre_propio(descarga) -> str:
    nombre = (descarga.nombre or "").strip()
    if not nombre or nombre == descarga.url:
        return ""
    return nombre


def _texto_avance(porcentaje: int, nombre: str) -> str:
    if nombre:
        # Traductores: {porcentaje} es el múltiplo de 10 que se alcanzó.
        return _("{nombre}: {porcentaje} por ciento").format(
            nombre=nombre, porcentaje=porcentaje)
    # Traductores: {porcentaje} es el múltiplo de 10 que se alcanzó.
    return _("{porcentaje} por ciento").format(porcentaje=porcentaje)


def _texto_quieta(nombre: str) -> str:
    if nombre:
        # Traductores: {nombre} es el título del vídeo que se descarga.
        return _("{nombre}: descarga en curso").format(nombre=nombre)
    return _("Descarga en curso")


class AnunciadorProgreso:
    """Decide los avisos de avance y de descarga quieta de cada vuelta."""

    def __init__(self) -> None:
        self._seguimientos: dict[str, _Seguimiento] = {}

    def reiniciar(self) -> None:
        self._seguimientos.clear()

    def avisos(self, descargas, ahora: float) -> list[Aviso]:
        en_curso = [descarga for descarga in descargas if _en_curso(descarga)]
        vigentes = {descarga.id for descarga in en_curso}
        self._seguimientos = {
            ident: seguimiento
            for ident, seguimiento in self._seguimientos.items()
            if ident in vigentes}
        varios = len(en_curso) > 1
        avisos: list[Aviso] = []
        for descarga in en_curso:
            seguimiento = self._seguimientos.get(descarga.id)
            if seguimiento is None:
                seguimiento = _Seguimiento(
                    multiplo=_multiplo_actual(descarga.progreso), inicio=ahora)
                self._seguimientos[descarga.id] = seguimiento
            aviso = self._avance(descarga, seguimiento, varios)
            if aviso is not None:
                avisos.append(aviso)
            aviso = self._quieta(descarga, seguimiento, ahora, varios)
            if aviso is not None:
                avisos.append(aviso)
        return avisos

    def _avance(self, descarga, seguimiento, varios: bool) -> Aviso | None:
        multiplo = _multiplo_actual(descarga.progreso)
        if multiplo < 10 or multiplo <= seguimiento.multiplo:
            return None
        seguimiento.multiplo = multiplo
        nombre = _nombre_propio(descarga) if varios else ""
        return Aviso(TIPO_AVANCE, _texto_avance(multiplo, nombre))

    def _quieta(self, descarga, seguimiento, ahora: float,
                varios: bool) -> Aviso | None:
        if seguimiento.paso_uno:
            return None
        if descarga.progreso >= PROGRESO_QUIETO:
            seguimiento.paso_uno = True
            return None
        if ahora - seguimiento.inicio < INTERVALO_QUIETA_S:
            return None
        if (seguimiento.ultimo_quieta is not None
                and ahora - seguimiento.ultimo_quieta < INTERVALO_QUIETA_S):
            return None
        seguimiento.ultimo_quieta = ahora
        nombre = _nombre_propio(descarga) if varios else ""
        return Aviso(TIPO_QUIETA, _texto_quieta(nombre))

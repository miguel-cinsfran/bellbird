"""Eventos de Restream, de la respuesta de la API a texto para leer.

Puro: no habla con la red ni con wx. Interpreta las listas de próximos, en
directo e historial, arma la fila de cada evento, su detalle y sus enlaces,
y lee las estadísticas de un evento. La zona horaria entra por parámetro
para que las pruebas no dependan de la hora del equipo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from guyrapu.core.idioma import _
from guyrapu.obs.duraciones import duracion_legible

TIPO_PROXIMOS = "proximos"
TIPO_EN_DIRECTO = "en_directo"
TIPO_HISTORIAL = "historial"
TIPOS = (TIPO_PROXIMOS, TIPO_EN_DIRECTO, TIPO_HISTORIAL)


@dataclass(frozen=True, slots=True)
class DestinoEvento:
    """Un destino del evento, con su canal y su enlace si lo tiene."""

    id: str | None
    canal_id: int | None
    plataforma_id: int | None
    enlace: str


@dataclass(frozen=True, slots=True)
class Evento:
    """Un evento de Restream con sus momentos en segundos Unix."""

    id: str
    estado: str
    titulo: str
    descripcion: str
    programado: float | None
    empezado: float | None
    terminado: float | None
    destinos: tuple[DestinoEvento, ...]


@dataclass(frozen=True, slots=True)
class Estadisticas:
    """Las cifras de espectadores y tiempo visto de un evento."""

    promedio: float
    maximo: float
    vistas: float
    tiempo_visto: float


def _entero(valor):
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def _texto(valor):
    return valor if isinstance(valor, str) else ""


def _identificador(valor):
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    return texto or None


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return valor


def _destino(entrada):
    if not isinstance(entrada, dict):
        return None
    identificador = _identificador(entrada.get("id"))
    canal_id = _entero(entrada.get("channelId"))
    plataforma_id = _entero(entrada.get("streamingPlatformId"))
    if identificador is None and canal_id is None and plataforma_id is None:
        return None
    return DestinoEvento(
        id=identificador,
        canal_id=canal_id,
        plataforma_id=plataforma_id,
        enlace=_texto(entrada.get("externalUrl")),
    )


def _evento(entrada):
    if not isinstance(entrada, dict):
        return None
    identificador = _identificador(entrada.get("id"))
    if identificador is None:
        return None
    destinos = tuple(destino for destino in
                     (_destino(item) for item in entrada.get("destinations") or ())
                     if destino is not None)
    return Evento(
        id=identificador,
        estado=_texto(entrada.get("status")),
        titulo=_texto(entrada.get("title")),
        descripcion=_texto(entrada.get("description")),
        programado=_numero(entrada.get("scheduledFor")),
        empezado=_numero(entrada.get("startedAt")),
        terminado=_numero(entrada.get("finishedAt")),
        destinos=destinos,
    )


def leer_eventos(datos, tipo=TIPO_PROXIMOS) -> list[Evento]:
    """Lee una lista de eventos o el objeto con `items` del historial."""
    if isinstance(datos, dict):
        datos = datos.get("items")
    if not isinstance(datos, list):
        return []
    return [evento for evento in (_evento(entrada) for entrada in datos)
            if evento is not None]


def leer_estadisticas(datos) -> Estadisticas:
    """Lee el bloque `total` de la respuesta de estadísticas."""
    total = datos.get("total") if isinstance(datos, dict) else None
    if not isinstance(total, dict):
        total = {}
    return Estadisticas(
        promedio=_numero(total.get("mean")) or 0,
        maximo=_numero(total.get("max")) or 0,
        vistas=_numero(total.get("viewsTotal")) or 0,
        tiempo_visto=_numero(total.get("watchedTime")) or 0,
    )


def _momento(segundos, zona):
    if segundos is None:
        return None
    return datetime.fromtimestamp(segundos, tz=zona)


def _fecha_hora(segundos, zona):
    momento = _momento(segundos, zona)
    return momento.strftime("%d/%m/%Y %H:%M") if momento else ""


def _hora(segundos, zona):
    momento = _momento(segundos, zona)
    return momento.strftime("%H:%M") if momento else ""


def _duracion(evento):
    if evento.empezado is None or evento.terminado is None:
        return duracion_legible(0)
    return duracion_legible(evento.terminado - evento.empezado)


def fila(evento, tipo=TIPO_PROXIMOS, zona=None) -> str:
    """La fila de la lista: título y el momento que corresponde al tipo."""
    if tipo == TIPO_PROXIMOS:
        if evento.programado is None:
            return _("{titulo}, sin programar").format(titulo=evento.titulo)
        return _("{titulo}, programado para {fecha}").format(
            titulo=evento.titulo,
            fecha=_fecha_hora(evento.programado, zona))
    if tipo == TIPO_EN_DIRECTO:
        hora = _hora(evento.empezado or evento.programado, zona)
        if not hora:
            return _("{titulo}, en directo").format(titulo=evento.titulo)
        return _("{titulo}, en directo desde {hora}").format(
            titulo=evento.titulo, hora=hora)
    inicio = evento.empezado or evento.programado or evento.terminado
    return _("{titulo}, {fecha}, duró {duracion}").format(
        titulo=evento.titulo, fecha=_fecha_hora(inicio, zona),
        duracion=_duracion(evento))


def _estado(evento):
    if evento.estado == "upcoming":
        return _("Próximo")
    if evento.estado in ("live", "in-progress"):
        return _("En directo")
    if evento.estado == "finished":
        return _("Finalizado")
    return evento.estado


def _nombre_destino(destino, nombres):
    texto = nombres.get(destino.canal_id) or nombres.get(destino.id)
    if texto:
        return texto
    return _("Plataforma {id}").format(id=destino.plataforma_id)


def detalle(evento, nombres=None, zona=None) -> str:
    """El detalle del evento, con la descripción completa al final."""
    nombres = nombres or {}
    lineas = [
        _("Título: {titulo}").format(titulo=evento.titulo),
        _("Estado: {estado}").format(estado=_estado(evento)),
    ]
    if evento.programado is not None:
        lineas.append(_("Programado para: {fecha}").format(
            fecha=_fecha_hora(evento.programado, zona)))
    if evento.empezado is not None:
        lineas.append(_("Inició: {fecha}").format(
            fecha=_fecha_hora(evento.empezado, zona)))
    if evento.terminado is not None:
        lineas.append(_("Terminó: {fecha}").format(
            fecha=_fecha_hora(evento.terminado, zona)))
    if evento.destinos:
        lineas.append(_("Destinos:"))
        lineas.extend(_nombre_destino(destino, nombres)
                      for destino in evento.destinos)
    if evento.descripcion:
        lineas.append(_("Descripción:"))
        lineas.append(evento.descripcion)
    return "\n".join(lineas)


def enlaces(evento) -> list[str]:
    """Los enlaces de los destinos que los tienen, en el orden del evento."""
    return [destino.enlace for destino in evento.destinos if destino.enlace]


def _cifra(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "0"
    if numero.is_integer():
        return str(int(numero))
    return f"{numero:.1f}".replace(".", ",")


def frase_estadisticas(estadisticas) -> str:
    """La frase de estadísticas que se lee y se escribe al final."""
    return _("Espectadores: promedio {promedio}, máximo {máximo}. "
             "Vistas: {vistas}. Tiempo visto: {tiempo}.").format(
                 promedio=_cifra(estadisticas.promedio),
                 máximo=_cifra(estadisticas.maximo),
                 vistas=_cifra(estadisticas.vistas),
                 tiempo=duracion_legible(estadisticas.tiempo_visto))

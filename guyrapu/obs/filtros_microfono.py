"""Filtros del micrófono de OBS: qué ofrece la app y cómo se llevan a OBS.

Lee la lista de filtros de la fuente, arma las peticiones que la dejan como
se eligió y compone el anuncio. Respeta los filtros que el usuario ya tenga:
los reutiliza en vez de crear otros iguales y nunca borra ninguno.
"""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.core import diagnostico
from guyrapu.core.idioma import N_, _
from guyrapu.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)

TIPO_RUIDO = "noise_suppress_filter_v2"
TIPO_PUERTA = "noise_gate_filter"
TIPO_GANANCIA = "gain_filter"

GANANCIAS = (
    (0, N_("Sin cambio")),
    (3, N_("Subir 3 dB")),
    (6, N_("Subir 6 dB")),
    (10, N_("Subir 10 dB")),
    (15, N_("Subir 15 dB")),
    (20, N_("Subir 20 dB")),
    (-3, N_("Bajar 3 dB")),
    (-6, N_("Bajar 6 dB")),
)


@dataclass(frozen=True)
class Estado:
    eliminacion: bool
    puerta: bool
    ganancia_db: int


def _activo(filtros, tipo):
    return any(filtro.get("filterKind") == tipo
               and filtro.get("filterEnabled")
               for filtro in filtros)


def _db_de(filtro):
    try:
        return float(filtro.get("filterSettings", {}).get("db", 0))
    except (TypeError, ValueError):
        return 0.0


def _db_mas_cercano(db):
    return min(GANANCIAS, key=lambda par: abs(par[0] - db))[0]


def estado_de(filtros):
    """El estado que muestran las casillas y la lista de ganancia."""
    filtros = list(filtros or ())
    ganancia = 0
    for filtro in filtros:
        if (filtro.get("filterKind") == TIPO_GANANCIA
                and filtro.get("filterEnabled")):
            ganancia = _db_mas_cercano(_db_de(filtro))
            break
    return Estado(_activo(filtros, TIPO_RUIDO), _activo(filtros, TIPO_PUERTA),
                  ganancia)


def _nombre_libre(filtros, base):
    usados = {filtro.get("filterName") for filtro in filtros}
    if base not in usados:
        return base
    numero = 2
    while f"{base} {numero}" in usados:
        numero += 1
    return f"{base} {numero}"


def _peticiones_de_tipo(tipo, nombre, activo, filtros, ajustes):
    """Peticiones para dejar un tipo como se pide, reutilizando el que haya."""
    existente = next((filtro for filtro in filtros
                      if filtro.get("filterKind") == tipo), None)
    if existente is None:
        if not activo:
            return []
        return [("CreateSourceFilter", {
            "filterName": _nombre_libre(filtros, nombre),
            "filterKind": tipo,
            "filterSettings": ajustes,
        })]
    peticiones = []
    if bool(existente.get("filterEnabled")) != activo:
        peticiones.append(("SetSourceFilterEnabled", {
            "filterName": existente.get("filterName"),
            "filterEnabled": activo,
        }))
    return peticiones


def plan(filtros, elegido):
    """Las peticiones que llevan OBS del estado actual al elegido.

    La ganancia activa es la que no vale cero; con «Sin cambio» se desactiva
    la que exista y no se crea ninguna.
    """
    filtros = list(filtros or ())
    peticiones = []
    peticiones += _peticiones_de_tipo(
        TIPO_RUIDO, _("Eliminación de ruido"), elegido.eliminacion, filtros,
        {"method": "rnnoise"})
    peticiones += _peticiones_de_tipo(
        TIPO_PUERTA, _("Puerta anti-ruidos"), elegido.puerta, filtros, {})
    ganancia_activa = elegido.ganancia_db != 0
    peticiones += _peticiones_de_tipo(
        TIPO_GANANCIA, _("Ganancia"), ganancia_activa, filtros,
        {"db": elegido.ganancia_db})
    if ganancia_activa:
        existente = next((filtro for filtro in filtros
                          if filtro.get("filterKind") == TIPO_GANANCIA), None)
        if existente is not None and _db_de(existente) != elegido.ganancia_db:
            peticiones.append(("SetSourceFilterSettings", {
                "filterName": existente.get("filterName"),
                "filterSettings": {"db": elegido.ganancia_db},
            }))
    return peticiones


def _nombre_de_ganancia(db):
    for valor, nombre in GANANCIAS:
        if valor == db:
            return _(nombre)
    return _(GANANCIAS[0][1])


def resumen(elegido):
    """El anuncio posterior a aplicar los filtros."""
    activos = []
    if elegido.eliminacion:
        activos.append(_("Eliminación de ruido activada."))
    if elegido.puerta:
        activos.append(_("Puerta anti-ruidos activada."))
    if elegido.ganancia_db != 0:
        # Traductores: {nombre} es la opción de ganancia elegida.
        activos.append(_("Ganancia: {nombre}.").format(
            nombre=_nombre_de_ganancia(elegido.ganancia_db)))
    if not activos:
        return _("Filtros del micrófono desactivados.")
    # Traductores: {detalle} es lo que quedó activo.
    return _("Filtros del micrófono aplicados. {detalle}").format(
        detalle=" ".join(activos))


def _cliente_por_defecto():
    return obs_cliente.ClienteObs(obs_cliente.leer_ajustes())


def _con_cliente(fuente, accion, crear_cliente=None):
    fabrica = crear_cliente or _cliente_por_defecto
    cliente = None
    try:
        cliente = fabrica()
        cliente.conectar()
        return accion(cliente, fuente)
    finally:
        if cliente is not None:
            try:
                cliente.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión de los filtros "
                             "del micrófono: %s", exc)


def _crudos(cliente, fuente):
    respuesta = cliente.pedir(
        "GetSourceFilterList", {"sourceName": fuente})
    return tuple(respuesta.get("responseData", {}).get("filters", ()))


def leer_filtros(fuente, crear_cliente=None):
    """La lista de filtros de la fuente, tal como la devuelve OBS."""
    return _con_cliente(fuente, _crudos, crear_cliente)


def leer_filtros_de(fuentes, crear_cliente=None):
    """Los filtros de cada fuente, con una sola conexión.

    Devuelve un diccionario con el nombre de la fuente y su lista.
    """

    def accion(cliente, nombres):
        return {nombre: _crudos(cliente, nombre) for nombre in nombres}

    return _con_cliente(tuple(fuentes), accion, crear_cliente)


def leer(fuente, crear_cliente=None):
    """El estado de los filtros del micrófono en OBS."""

    def accion(cliente, nombre):
        return estado_de(_crudos(cliente, nombre))

    return _con_cliente(fuente, accion, crear_cliente)


def aplicar(fuente, elegido, crear_cliente=None):
    """Deja en OBS los filtros elegidos."""

    def accion(cliente, nombre):
        filtros = _crudos(cliente, nombre)
        for tipo, datos in plan(filtros, elegido):
            cliente.pedir(tipo, {"sourceName": nombre, **datos})

    return _con_cliente(fuente, accion, crear_cliente)

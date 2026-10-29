"""Consulta a la IA: valida, arma el pedido, lo manda y confirma.

`preparar` junta todo sin tocar la conversación para que la ventana
pueda cancelar en el medio. `consultar` manda y confirma. Cada falla
llega a la ventana como una frase lista para leer con NVDA.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.ai import ajustes_ia
from ytchat.ai import conversacion
from ytchat.ai import envio_ia
from ytchat.ai import protocolos
from ytchat.ai import proveedores
from ytchat.ai.catalogo import modelos as modelos_de_catalogo
from ytchat.core.idioma import N_, _

FRASE_CORTADA = N_("Respuesta incompleta: alcanzó la longitud máxima "
                   "elegida en Preferencias.")

TEXTO_SIN_NIVEL_GRATUITO = N_("Este modelo no está en el nivel gratuito "
                              "de tu clave. Elige otro modelo.")

_MSG_PROVEEDOR = N_("Elige un proveedor en Preferencias, "
                    "Inteligencia artificial.")
_MSG_MODELO = N_("Elige un modelo en Preferencias, Inteligencia artificial.")
_MSG_DIRECCION = N_("Escribe una dirección válida para el proveedor "
                    "en Preferencias, Inteligencia artificial.")

_ERRORES = {
    protocolos.CLAVE_RECHAZADA: N_("El proveedor rechazó la clave. Revísala "
                                   "en Preferencias, Inteligencia artificial."),
    protocolos.CUOTA: N_("Se agotó la cuota del proveedor. Espera un rato "
                         "o elige otro modelo."),
    protocolos.MODELO_INEXISTENTE: N_("El proveedor no ofrece ese modelo. "
                                      "Elige otro en Preferencias, "
                                      "Inteligencia artificial."),
    protocolos.BLOQUEADA: N_("El proveedor bloqueó la respuesta con su filtro "
                             "de contenido."),
    protocolos.SIN_TEXTO_POR_TOKENS: N_("El modelo gastó todo el espacio "
                                        "pensando y no respondió. Elige una "
                                        "respuesta más larga en Preferencias."),
    protocolos.RESPUESTA_VACIA: N_("El modelo no devolvió ninguna respuesta. "
                                   "Vuelve a intentarlo."),
    protocolos.SERVIDOR: N_("El proveedor tuvo un fallo. Vuelve a intentarlo "
                            "en un rato."),
    protocolos.RECHAZO: N_("El proveedor rechazó la consulta. Puede que el "
                            "modelo ya no esté disponible: en Preferencias, "
                            "Inteligencia artificial, pulsa Actualizar lista "
                            "de modelos o elige otro."),
    protocolos.SIN_RED: N_("No hay conexión con el proveedor. Comprueba "
                           "la conexión a internet."),
    protocolos.TIEMPO_AGOTADO: N_("El proveedor tardó demasiado en responder. "
                                  "Vuelve a intentarlo."),
}


class FaltaConfiguracion(Exception):
    pass


@dataclass(frozen=True)
class Preparada:
    pedido: object
    texto_enviado: str
    tiempo_espera: int


def _modelo_en_catalogo(muestra, proveedor, modelo_id):
    if proveedor.id_catalogo is None:
        return None
    for modelo in modelos_de_catalogo(muestra, proveedor.id_catalogo):
        if modelo.id == modelo_id:
            return modelo
    return None


def preparar(charla, texto, ajustes, catalogo, clave, descripcion) -> Preparada:
    """Valida, arma el pedido y devuelve lo necesario para enviarlo."""
    proveedor = proveedores.por_id(ajustes.proveedor)
    if proveedor is None:
        raise FaltaConfiguracion(_(_MSG_PROVEEDOR))
    modelo_id = (ajustes.modelo or "").strip()
    if not modelo_id:
        raise FaltaConfiguracion(_(_MSG_MODELO))
    if not clave or not str(clave).strip():
        raise FaltaConfiguracion(
            _("Falta la clave de {proveedor}. Guárdala en Preferencias, "
              "Inteligencia artificial.").format(proveedor=proveedor.nombre))
    try:
        protocolo, base = proveedores.resolver(
            proveedor, modelo_id, catalogo, ajustes.direccion)
    except ValueError:
        raise FaltaConfiguracion(_(_MSG_DIRECCION)) from None
    mensajes = charla.preparar(
        texto, ajustes_ia.pregunta_efectiva(ajustes))
    encontrado = _modelo_en_catalogo(catalogo, proveedor, modelo_id)
    if encontrado is None:
        piensa, tope_salida = True, None
    else:
        piensa, tope_salida = encontrado.piensa, encontrado.tope_salida
    tope = conversacion.max_tokens(ajustes.largo, piensa, tope_salida)
    pedido = protocolos.armar_pedido(
        protocolo, base, modelo_id, clave,
        conversacion.prompt_sistema(descripcion), mensajes, tope,
        proveedores.cabeceras(proveedor, charla.sesion))
    return Preparada(pedido, mensajes[-1].texto, ajustes.tiempo_espera)


def consultar(charla, preparada, clave, enviar=envio_ia.enviar) -> str:
    """Manda la preparada y confirma la conversación solo si sale bien."""
    respuesta = enviar(preparada.pedido, clave, preparada.tiempo_espera)
    charla.confirmar(preparada.texto_enviado, respuesta.texto)
    if respuesta.cortada:
        return "{} {}".format(respuesta.texto, _(FRASE_CORTADA))
    return respuesta.texto


def texto_de_error(error) -> str:
    """La frase para el usuario ante cualquier falla de la consulta."""
    if isinstance(error, conversacion.SinCaptura):
        return _("Agrega una captura antes de preguntar.")
    if isinstance(error, conversacion.SinTexto):
        return _("Escribe una pregunta.")
    if isinstance(error, FaltaConfiguracion):
        return str(error)
    if isinstance(error, protocolos.ErrorIA):
        if error.sin_nivel_gratuito:
            return _(TEXTO_SIN_NIVEL_GRATUITO)
        texto = _ERRORES.get(error.tipo)
        if texto is not None:
            return _(texto)
    return _("No se pudo completar la consulta. Vuelve a intentarlo.")

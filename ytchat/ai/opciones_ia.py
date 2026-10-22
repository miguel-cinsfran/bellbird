"""Lógica pura de la página Inteligencia artificial de Preferencias.

Sin wx, sin red y sin el Administrador de credenciales: la página decide
qué se muestra y este módulo decide qué significa. Los textos que oye el
usuario viven acá para copiarlos tal cual.
"""

from __future__ import annotations

import uuid

from ytchat.ai import catalogo
from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import protocolos
from ytchat.ai import proveedores

TEXTO_PEDIDO_PRUEBA = "Responde solo con la palabra OK."
TEXTO_SISTEMA_PRUEBA = "Responde con una sola palabra."
TEXTO_CLAVE_GUARDADA = "Clave guardada."
TEXTO_CLAVE_BORRADA = "Clave borrada."
TEXTO_CLAVE_NO_GUARDADA = ("No se pudo guardar la clave en el "
                           "Administrador de credenciales.")
TEXTO_CLAVE_NO_BORRADA = ("No se pudo borrar la clave del "
                          "Administrador de credenciales.")
TEXTO_FALTA_CLAVE = "Escribe la clave antes de guardarla o probarla."
TEXTO_PROBANDO = "Probando la clave…"
TEXTO_PRUEBA_BIEN = "La clave funciona con {modelo}."
TEXTO_ACTUALIZANDO = "Actualizando la lista de modelos…"
TEXTO_LISTA_ACTUALIZADA = "Lista de modelos actualizada: {n} modelos."
TEXTO_LISTA_FALLO = ("No se pudo actualizar la lista de modelos. "
                     "Revisa la conexión y vuelve a intentarlo.")
TEXTO_PREGUNTA_RESTAURADA = "Pregunta inicial restaurada."
TEXTO_CONTRIBUTOR = "Este modelo entrena con lo que se le envía."
TEXTO_MARCA_CONTRIBUTOR = ", entrena con lo enviado"
TEXTO_SIN_MODELOS = ("Sin modelos en la lista. "
                     "Escribe el modelo en Otro modelo.")


def filas_modelos(muestra, proveedor, solo_gratis):
    """Lista de (id, etiqueta) del proveedor, o vacía sin catálogo.

    La etiqueta es el nombre del modelo, más «, gratis» si lo es y el
    proveedor cobra por uso, más la marca de contributor. Con un proveedor
    que da gratis por clave, «, gratis» no se escribe y `solo_gratis` se
    ignora.
    """
    if proveedor is None or proveedor.id_catalogo is None:
        return []
    filtrar = solo_gratis and not proveedor.gratis_por_clave
    filas = []
    for modelo in catalogo.modelos(
            muestra, proveedor.id_catalogo, filtrar):
        etiqueta = modelo.nombre
        if modelo.gratis and not proveedor.gratis_por_clave:
            etiqueta += ", gratis"
        if modelo.contributor:
            etiqueta += TEXTO_MARCA_CONTRIBUTOR
        filas.append((modelo.id, etiqueta))
    return filas


def modelo_elegido(id_de_lista, otro):
    """El texto de «Otro modelo» sin bordes si no está vacío, si no el de
    la lista, si no "". El marcador de lista vacía cuenta como vacío."""
    texto = (otro or "").strip()
    if texto:
        return texto
    ident = (id_de_lista or "").strip()
    if not ident or ident == TEXTO_SIN_MODELOS:
        return ""
    return ident


def separar_modelo_guardado(guardado, filas):
    """Si el modelo guardado está en las filas, va a la lista; si no, va
    a «Otro modelo». Devuelve (id_para_lista, texto_para_otro)."""
    if guardado and any(ident == guardado for ident, _et in filas):
        return (guardado, "")
    return ("", guardado or "")


def aviso_de_modelo(modelo):
    """TEXTO_CONTRIBUTOR si el modelo usa lo enviado para entrenarse."""
    if modelo is not None and modelo.contributor:
        return TEXTO_CONTRIBUTOR
    return ""


def pedido_de_prueba(ajustes, muestra, clave):
    """Pedido de solo texto con el modelo y el proveedor de `ajustes`.

    El tope sale de max_tokens(CORTA, piensa, tope) según el catálogo,
    como en la consulta real pero sin captura. Sin modelo levanta
    FaltaConfiguracion con el mismo texto que `consulta.preparar`.
    """
    proveedor = proveedores.por_id(ajustes.proveedor)
    if proveedor is None:
        raise consulta.FaltaConfiguracion(consulta._MSG_PROVEEDOR)
    modelo_id = (ajustes.modelo or "").strip()
    if not modelo_id:
        raise consulta.FaltaConfiguracion(consulta._MSG_MODELO)
    try:
        protocolo, base = proveedores.resolver(
            proveedor, modelo_id, muestra, ajustes.direccion)
    except ValueError:
        raise consulta.FaltaConfiguracion(consulta._MSG_DIRECCION) from None
    encontrado = None
    if proveedor.id_catalogo is not None:
        for modelo in catalogo.modelos(muestra, proveedor.id_catalogo):
            if modelo.id == modelo_id:
                encontrado = modelo
                break
    if encontrado is None:
        piensa, tope_salida = True, None
    else:
        piensa, tope_salida = encontrado.piensa, encontrado.tope_salida
    tope = conversacion.max_tokens(
        conversacion.CORTA, piensa, tope_salida)
    mensajes = [protocolos.Mensaje("usuario", TEXTO_PEDIDO_PRUEBA)]
    extra = proveedores.cabeceras(proveedor, str(uuid.uuid4()))
    return protocolos.armar_pedido(
        protocolo, base, modelo_id, clave, TEXTO_SISTEMA_PRUEBA,
        mensajes, tope, extra)

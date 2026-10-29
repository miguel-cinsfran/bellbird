"""Lógica pura de la página Inteligencia artificial de Preferencias.

Sin wx, sin red y sin el Administrador de credenciales: la página decide
qué se muestra y este módulo decide qué significa. Los textos que oye el
usuario viven acá para copiarlos tal cual.
"""

from __future__ import annotations

import uuid

from bellbird.ai import catalogo
from bellbird.ai import consulta
from bellbird.ai import conversacion
from bellbird.ai import protocolos
from bellbird.ai import proveedores
from bellbird.ai import sondeo_gratis
from bellbird.core.idioma import N_, _

TEXTO_PEDIDO_PRUEBA = N_("Responde solo con la palabra OK.")
TEXTO_SISTEMA_PRUEBA = N_("Responde con una sola palabra.")
TEXTO_CLAVE_GUARDADA = N_("Clave guardada.")
TEXTO_CLAVE_BORRADA = N_("Clave borrada.")
TEXTO_CLAVE_NO_GUARDADA = N_("No se pudo guardar la clave en el "
                             "Administrador de credenciales.")
TEXTO_CLAVE_NO_BORRADA = N_("No se pudo borrar la clave del "
                            "Administrador de credenciales.")
TEXTO_FALTA_CLAVE = N_("Escribe la clave antes de guardarla o probarla.")
TEXTO_CLAVE_CORTA = N_("La clave es demasiado corta. Copia la "
                       "clave entera desde la página del proveedor.")
TEXTO_CLAVE_CARACTERES = N_("La clave tiene espacios o caracteres "
                            "que una clave no lleva. Cópiala de nuevo.")
# Traductores: aviso de clave ajena; {proveedor} es su nombre y {prefijo} su inicio.
TEXTO_CLAVE_PREFIJO = N_("Las claves de {proveedor} empiezan con "
                         "{prefijo}. Revisa que sea la clave de "
                         "este proveedor.")
# Traductores: confirmación de borrado; {proveedor} es su nombre.
TEXTO_CONFIRMAR_BORRADO = N_("Borra la clave guardada de {proveedor} del "
                             "Administrador de credenciales. ¿Deseas "
                             "continuar?")
TEXTO_PROBANDO = N_("Probando la clave…")
# Traductores: anuncio de prueba bien; {modelo} es su identificador.
TEXTO_PRUEBA_BIEN = N_("La clave funciona con {modelo}.")
TEXTO_ACTUALIZANDO = N_("Actualizando la lista de modelos…")
# Traductores: anuncio del sondeo; {n} es cuántos modelos se prueban.
TEXTO_SONDEANDO = N_("Comprobando {n} modelos con tu clave.")
# Traductores: anuncio de lista nueva; {n} cuántos y {proveedor} su nombre.
TEXTO_LISTA_ACTUALIZADA = N_("Lista de modelos actualizada: {n} modelos "
                             "de {proveedor}.")
TEXTO_LISTA_ACTUALIZADA_SIN_PROVEEDOR = N_("Lista de modelos actualizada.")
TEXTO_LISTA_FALLO = N_("No se pudo actualizar la lista de modelos. "
                       "Revisa la conexión y vuelve a intentarlo.")
# Traductores: anuncio de lista nueva; {n} modelos, {g} gratis, {proveedor} su nombre.
TEXTO_LISTA_CON_GRATIS = N_("Lista de modelos actualizada: {n} modelos "
                            "de {proveedor}, {g} gratis con tu clave.")
# Traductores: anuncio de lista nueva; {n} modelos, {r} útiles, {proveedor} su nombre.
TEXTO_LISTA_CON_TU_CLAVE = N_("Lista de modelos actualizada: {n} modelos "
                              "de {proveedor}, {r} funcionan con tu clave.")
TEXTO_INSTRUCCION_RESTAURADA = N_("Instrucción restaurada.")
TEXTO_CONTRIBUTOR = N_("Este modelo entrena con lo que se le envía.")
# Traductores: marca de modelo que entrena, se suma a su nombre.
TEXTO_MARCA_CONTRIBUTOR = N_(", entrena con lo enviado")
TEXTO_SIN_MODELOS = N_("Sin modelos en la lista. "
                       "Escribe el modelo en Otro modelo.")


def estado_de_clave(clave):
    """Lo que se muestra de la clave guardada, sin revelarla entera.

    Con ocho caracteres o más se agregan los últimos cuatro, que alcanzan
    para reconocerla sin exponer casi nada. Una clave corta no se muestra.
    """
    if not clave:
        return ""
    if len(clave) >= 8:
        # Traductores: aviso de la clave guardada; {final} son 4 caracteres.
        return _("Guardada, termina en {final}").format(final=clave[-4:])
    return _("Guardada")


_CARACTERES_DE_CLAVE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def problema_de_clave(proveedor, clave):
    """El problema de la clave, o "" si tiene forma de clave.

    Los bordes no cuentan. Se mira primero el largo y después los
    caracteres, para que el mensaje diga qué corregir.
    """
    limpia = (clave or "").strip()
    if not limpia:
        return _(TEXTO_FALTA_CLAVE)
    if len(limpia) < 20:
        return _(TEXTO_CLAVE_CORTA)
    if any(caracter not in _CARACTERES_DE_CLAVE for caracter in limpia):
        return _(TEXTO_CLAVE_CARACTERES)
    prefijo = proveedor.prefijo_clave
    if prefijo and not limpia.startswith(prefijo):
        return _(TEXTO_CLAVE_PREFIJO).format(
            proveedor=proveedor.nombre, prefijo=prefijo)
    return ""


def filas_modelos(muestra, proveedor, solo_gratis, marcas=None):
    """Lista de (id, etiqueta) del proveedor, o vacía sin catálogo.

    La etiqueta es el nombre del modelo, más «, gratis» si lo es y el
    proveedor cobra por uso, más la marca de contributor. Con un proveedor
    que da gratis por clave, la marca sale de `marcas`: «, gratis» si la
    clave resultó gratuita y «, funciona con tu clave» si no, y `solo_gratis`
    deja solo los gratuitos marcados. Sin marcas, igual que antes.
    """
    if proveedor is None or proveedor.id_catalogo is None:
        return []
    filtrar = solo_gratis and not proveedor.gratis_por_clave
    filas = []
    for modelo in catalogo.modelos(
            muestra, proveedor.id_catalogo, filtrar):
        if proveedor.gratis_por_clave and solo_gratis and marcas \
                and marcas.get(modelo.id) != sondeo_gratis.MARCA_GRATIS:
            continue
        etiqueta = modelo.nombre
        if modelo.gratis and not proveedor.gratis_por_clave:
            # Traductores: marca de modelo gratuito, se suma a su nombre.
            etiqueta += _(", gratis")
        if proveedor.gratis_por_clave and marcas:
            marca = marcas.get(modelo.id)
            if marca == sondeo_gratis.MARCA_GRATIS:
                # Traductores: marca de modelo gratuito, se suma a su nombre.
                etiqueta += _(", gratis")
            elif marca == sondeo_gratis.MARCA_CON_TU_CLAVE:
                # Traductores: marca de modelo útil, se suma a su nombre.
                etiqueta += _(", funciona con tu clave")
        if modelo.contributor:
            etiqueta += _(TEXTO_MARCA_CONTRIBUTOR)
        filas.append((modelo.id, etiqueta))
    return filas


def resumen_sondeo(resultados, n, proveedor):
    """La frase del anuncio del sondeo, según la clave sea gratuita o no."""
    marcas = sondeo_gratis.marcas(resultados)
    gratis = sum(1 for valor in marcas.values()
                 if valor == sondeo_gratis.MARCA_GRATIS)
    if gratis:
        return _(TEXTO_LISTA_CON_GRATIS).format(
            n=n, proveedor=proveedor, g=gratis)
    con_clave = sum(1 for valor in marcas.values()
                    if valor == sondeo_gratis.MARCA_CON_TU_CLAVE)
    return _(TEXTO_LISTA_CON_TU_CLAVE).format(
        n=n, proveedor=proveedor, r=con_clave)


def modelo_elegido(id_de_lista, otro):
    """El texto de «Otro modelo» sin bordes si no está vacío, si no el de
    la lista, si no "". El marcador de lista vacía cuenta como vacío."""
    texto = (otro or "").strip()
    if texto:
        return texto
    ident = (id_de_lista or "").strip()
    if not ident or ident == _(TEXTO_SIN_MODELOS):
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
        return _(TEXTO_CONTRIBUTOR)
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
    mensajes = [protocolos.Mensaje("usuario", _(TEXTO_PEDIDO_PRUEBA))]
    extra = proveedores.cabeceras(proveedor, str(uuid.uuid4()))
    return protocolos.armar_pedido(
        protocolo, base, modelo_id, clave, _(TEXTO_SISTEMA_PRUEBA),
        mensajes, tope, extra)

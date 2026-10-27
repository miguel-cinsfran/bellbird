"""Sondeo de qué modelos responde la clave gratuita de un proveedor.

Lo gratis depende de la clave y no del modelo, así que la lista se arma
probando cada modelo con un pedido mínimo. Sin wx y sin red propia: el
envío se inyecta, y del disco solo lee y escribe su archivo.
"""

from __future__ import annotations

import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from ytchat.ai import ajustes_ia
from ytchat.ai import catalogo
from ytchat.ai import protocolos
from ytchat.core import archivos

RESPONDE = "responde"
DE_PAGO = "de_pago"
SIN_SABER = "sin_saber"
CLAVE_MALA = "clave_mala"

MARCA_GRATIS = "gratis"
MARCA_CON_TU_CLAVE = "funciona con tu clave"


def clasificar(error):
    """El resultado del modelo: responde, de pago, sin saber o clave mala."""
    if error is None:
        return RESPONDE
    if isinstance(error, protocolos.ErrorIA):
        if error.sin_nivel_gratuito:
            return DE_PAGO
        if error.tipo == protocolos.CLAVE_RECHAZADA:
            return CLAVE_MALA
    return SIN_SABER


def _resultado(enviar, pedido, clave, tiempo_espera):
    try:
        enviar(pedido, clave, tiempo_espera)
    except Exception as error:
        return clasificar(error)
    return RESPONDE


def sondear(proveedor, muestra, clave, enviar, tiempo_espera):
    """Prueba cada modelo del proveedor y devuelve {id: resultado}.

    Consulta hasta cuatro modelos a la vez y devuelve el diccionario en el
    orden del catálogo. Para en cuanto un modelo responde que la clave no
    sirve: deja terminar los que ya estaban en vuelo, los descarta y
    devuelve solo ese.
    """
    # Import local: `opciones_ia` usa las marcas de este módulo.
    from ytchat.ai import opciones_ia
    modelos = catalogo.modelos(muestra, proveedor.id_catalogo)
    pedidos = {}
    for modelo in modelos:
        ajustes = ajustes_ia.AjustesIA(
            proveedor=proveedor.id, modelo=modelo.id)
        pedidos[modelo.id] = opciones_ia.pedido_de_prueba(
            ajustes, muestra, clave)
    resultados = {}
    mala = None
    with ThreadPoolExecutor(max_workers=4) as ejecutor:
        en_vuelo = {}
        siguiente = 0
        while True:
            while (mala is None and len(en_vuelo) < 4
                   and siguiente < len(modelos)):
                modelo = modelos[siguiente]
                siguiente += 1
                futuro = ejecutor.submit(
                    _resultado, enviar, pedidos[modelo.id], clave,
                    tiempo_espera)
                en_vuelo[futuro] = modelo.id
            if not en_vuelo:
                break
            hechos, _sin_uso = wait(en_vuelo, return_when=FIRST_COMPLETED)
            for futuro in hechos:
                ident = en_vuelo.pop(futuro)
                if mala is not None:
                    continue
                resultado = futuro.result()
                resultados[ident] = resultado
                if resultado == CLAVE_MALA:
                    mala = ident
    if mala is not None:
        return {mala: CLAVE_MALA}
    return {modelo.id: resultados[modelo.id] for modelo in modelos}


def marcas(resultados):
    """{id: marca} de los que responden, según la clave sea gratuita o no."""
    gratuita = any(valor == DE_PAGO for valor in resultados.values())
    salida = {}
    for ident, resultado in resultados.items():
        if resultado != RESPONDE:
            continue
        salida[ident] = MARCA_GRATIS if gratuita else MARCA_CON_TU_CLAVE
    return salida


def _leer_proveedores(ruta):
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}
    try:
        datos = json.loads(texto)
    except ValueError:
        return {}
    if not isinstance(datos, dict):
        return {}
    proveedores = datos.get("proveedores")
    return proveedores if isinstance(proveedores, dict) else {}


def _marcas_validas(crudo):
    if not isinstance(crudo, dict):
        return {}
    return {ident: marca for ident, marca in crudo.items()
            if isinstance(ident, str) and isinstance(marca, str)}


def leer(ruta, proveedor_id):
    """Las marcas guardadas del proveedor, o {} si no hay o está roto."""
    entrada = _leer_proveedores(ruta).get(proveedor_id)
    if not isinstance(entrada, dict):
        return {}
    return _marcas_validas(entrada.get("marcas"))


def _escribir(ruta, proveedores):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps({"proveedores": proveedores},
                       ensure_ascii=False, indent=1) + "\n"
    archivos.escribir_texto_atomico(ruta, texto)


def guardar(ruta, proveedor_id, marcas, fecha):
    """Guarda las marcas del proveedor, sin tocar las de los demás."""
    proveedores = _leer_proveedores(ruta)
    proveedores[proveedor_id] = {"fecha": fecha,
                                 "marcas": _marcas_validas(marcas)}
    _escribir(ruta, proveedores)


def olvidar(ruta, proveedor_id):
    """Borra la entrada del proveedor y conserva las de los demás."""
    proveedores = _leer_proveedores(ruta)
    if proveedor_id not in proveedores:
        return
    del proveedores[proveedor_id]
    _escribir(ruta, proveedores)

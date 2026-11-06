"""Menú Agregar fuente y el recorrido de alta: nombre, propiedades y crear."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import (
    consultas_transmision, fuente_nueva, obs_captura, tipos_fuente)
from guyrapu.ui import (
    agregar_camara, escena_captura_ventana, escena_propiedades)
from guyrapu.ui.accesibilidad import anunciar


def etiquetas_menu() -> tuple:
    return tipos_fuente.etiquetas_menu()


def mostrar_menu(pagina, ancla):
    menu = wx.Menu()
    for tipo in tipos_fuente.CATALOGO:
        identificador = wx.NewIdRef()
        menu.Append(identificador, _(tipo.etiqueta))
        menu.Bind(
            wx.EVT_MENU,
            lambda _evento, clave=tipo.clave: agregar(pagina, clave),
            id=identificador)
    ancla.PopupMenu(menu)
    menu.Destroy()


def agregar(pagina, clave):
    tipo = tipos_fuente.por_clave(clave)
    if tipo is None:
        return
    if clave == "camara":
        _agregar_camara(pagina)
    elif clave == "ventana":
        _capturar_ventana(pagina)
    elif clave == "otra_escena":
        _agregar_de_otra(pagina)
    else:
        _agregar_con_propiedades(pagina, tipo)


def _escena(pagina):
    escena = pagina._escena()
    if not escena:
        anunciar(_("Sin selección"))
    return escena


def _en_vuelo(pagina):
    return pagina._operaciones.en_vuelo


def _enfocar(pagina):
    pagina.lst_fuentes.SetFocus()


def _agregar_con_propiedades(pagina, tipo):
    escena = _escena(pagina)
    if not escena or _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: _leer_para(pagina, escena, tipo),
        lambda datos: _con_datos(pagina, escena, tipo, datos))


def _leer_para(pagina, escena, tipo):
    pedir = pagina._gestor._pedir
    datos = {"ocupados": fuente_nueva.nombres_ocupados(pedir)}
    if tipo.clave in ("pantalla", "juego"):
        propiedad = "monitor_id" if tipo.clave == "pantalla" else "window"
        datos["opciones"] = fuente_nueva.opciones_lista(
            pedir, escena, tipo.clave, propiedad)
    return datos


def _con_datos(pagina, escena, tipo, datos):
    if pagina._operaciones.cerrando:
        return
    nombre = _pedir_nombre(pagina, tipo, datos["ocupados"])
    if nombre is None:
        _enfocar(pagina)
        return
    valores = escena_propiedades.pedir(
        pagina, tipo.clave, datos.get("opciones"), {})
    if valores is None:
        _enfocar(pagina)
        return
    if _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: _crear_y_leer(pagina, escena, tipo, nombre, valores),
        lambda filas: _agregada(pagina, escena, nombre, filas))


def _crear_y_leer(pagina, escena, tipo, nombre, valores):
    fuente_nueva.crear(
        pagina._gestor._pedir, escena, tipo.clave, nombre, valores)
    return consultas_transmision.leer_filas(pagina._gestor, escena)


def _agregada(pagina, escena, nombre, filas):
    pagina._cargar_filas(filas, nombre)
    _enfocar(pagina)
    anunciar(_("{nombre} agregada a la escena {escena}.").format(
        nombre=nombre, escena=escena))


def _dialogo_nombre(pagina, propuesto):
    return wx.TextEntryDialog(
        pagina, _("Nombre de la fuente:"), _("Agregar fuente"), propuesto)


def _pedir_nombre(pagina, tipo, ocupados):
    propuesto = tipos_fuente.nombre_propuesto(tipo, ocupados)
    ocupados = {nombre.casefold() for nombre in ocupados}
    while True:
        with _dialogo_nombre(pagina, propuesto) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            nombre = dialogo.GetValue().strip()
        if not nombre:
            return None
        if nombre.casefold() in ocupados:
            anunciar(_("Ya hay una fuente con ese nombre."))
            propuesto = nombre
            continue
        return nombre


def _agregar_camara(pagina):
    escena = _escena(pagina)
    if not escena or _en_vuelo(pagina):
        return
    tipo = tipos_fuente.por_clave("camara")
    agregar_camara.agregar(
        pagina._ventana,
        lambda _fuentes: _camara_agregada(pagina, escena),
        lambda ocupados: _pedir_nombre(pagina, tipo, ocupados))


def _camara_agregada(pagina, escena):
    if pagina._operaciones.en_vuelo:
        return
    pagina._releer_filas(escena, "")


def _capturar_ventana(pagina):
    escena = _escena(pagina)
    if not escena or _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: (pagina._gestor.ventanas(escena),
                 fuente_nueva.nombres_ocupados(pagina._gestor._pedir)),
        lambda datos: _abrir_ventana(pagina, escena, datos))


def _abrir_ventana(pagina, escena, datos):
    if pagina._operaciones.cerrando:
        return
    opciones, actual = datos[0]
    nombre = ""
    if not tipos_fuente.hay_captura(pagina._filas):
        nombre = _pedir_nombre(
            pagina, tipos_fuente.por_clave("ventana"), datos[1])
        if nombre is None:
            _enfocar(pagina)
            return
    valor = escena_captura_ventana.pedir_valor(
        pagina._ventana, opciones, actual)
    _enfocar(pagina)
    if valor is None or _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: _usar_ventana_y_leer(pagina, escena, valor, nombre),
        lambda datos: _ventana_aplicada(pagina, datos))


def _usar_ventana_y_leer(pagina, escena, valor, nombre):
    cliente = getattr(pagina._gestor, "_cliente", None)
    if cliente is not None:
        frase = obs_captura.usar_ventana(
            cliente, escena, valor, nombre=nombre)
    else:
        frase = pagina._gestor.usar_ventana(escena, valor)
    fuente = consultas_transmision.elegir_fuente(
        pagina._gestor.fuentes(escena))
    filas = consultas_transmision.leer_filas(pagina._gestor, escena)
    return frase, fuente, filas


def _ventana_aplicada(pagina, datos):
    frase, fuente, filas = datos
    pagina._cargar_filas(filas, fuente)
    _enfocar(pagina)
    anunciar(frase)


def _agregar_de_otra(pagina):
    escena = _escena(pagina)
    if not escena or _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: fuente_nueva.fuentes_de_otras(pagina._gestor._pedir, escena),
        lambda opciones: _elegir_de_otra(pagina, escena, opciones))


def _elegir_de_otra(pagina, escena, opciones):
    if pagina._operaciones.cerrando:
        return
    if not opciones:
        anunciar(_("No hay fuentes de otras escenas para agregar."))
        _enfocar(pagina)
        return
    fuente = escena_propiedades.pedir_fuente(pagina, opciones)
    _enfocar(pagina)
    if not fuente or _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: _agregar_de_otra_y_leer(pagina, escena, fuente),
        lambda filas: _agregada(pagina, escena, fuente, filas))


def _agregar_de_otra_y_leer(pagina, escena, fuente):
    fuente_nueva.agregar_de_otra(pagina._gestor._pedir, escena, fuente)
    return consultas_transmision.leer_filas(pagina._gestor, escena)


def abrir_propiedades(pagina):
    _escena, fuente = pagina._destino()
    if not fuente:
        anunciar(_("Sin selección"))
        return
    if _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: _leer_propiedades(pagina, fuente),
        lambda datos: _con_propiedades(pagina, fuente, datos))


def _leer_propiedades(pagina, fuente):
    pedir = pagina._gestor._pedir
    clave, valores = fuente_nueva.propiedades(pedir, fuente)
    propiedad = {"pantalla": "monitor_id", "ventana": "window",
                 "juego": "window", "camara": "video_device_id"}.get(clave)
    opciones = (fuente_nueva.opciones_de(pedir, fuente, propiedad)
                if propiedad else ())
    return clave, valores, opciones


def _con_propiedades(pagina, fuente, datos):
    if pagina._operaciones.cerrando:
        return
    clave, valores, opciones = datos
    if not clave:
        anunciar(_("Esta fuente no tiene propiedades en Guyrapu. "
                   "Cámbialas en OBS."))
        _enfocar(pagina)
        return
    nuevos = escena_propiedades.pedir(pagina, clave, opciones, valores)
    _enfocar(pagina)
    if nuevos is None or _en_vuelo(pagina):
        return
    pagina._operaciones.en_hilo(
        lambda: _aplicar_propiedades(pagina, fuente, clave, nuevos),
        lambda _resultado: _propiedades_aplicadas(pagina, fuente))


def _aplicar_propiedades(pagina, fuente, clave, valores):
    fuente_nueva.aplicar_propiedades(
        pagina._gestor._pedir, fuente, clave, valores)


def _propiedades_aplicadas(pagina, fuente):
    _enfocar(pagina)
    anunciar(_("Propiedades de {fuente} aplicadas.").format(fuente=fuente))

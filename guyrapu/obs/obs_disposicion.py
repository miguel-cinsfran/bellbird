"""Geometría de la disposición del panel en OBS."""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.core.idioma import N_, _


ANCLAJES: dict[str, int] = {
    "superior-izquierda": 5, "superior-centro": 4, "superior-derecha": 6,
    "centro-izquierda": 1, "centro": 0, "centro-derecha": 2,
    "inferior-izquierda": 9, "inferior-centro": 8, "inferior-derecha": 10,
}

_ETIQUETAS_ANCLAJE = {
    "superior-izquierda": N_("Arriba a la izquierda"), "superior-centro": N_("Arriba al centro"),
    "superior-derecha": N_("Arriba a la derecha"), "centro-izquierda": N_("Centro a la izquierda"),
    "centro": N_("Centro"), "centro-derecha": N_("Centro a la derecha"),
    "inferior-izquierda": N_("Abajo a la izquierda"), "inferior-centro": N_("Abajo al centro"),
    "inferior-derecha": N_("Abajo a la derecha"),
}


def etiqueta_anclaje(nombre) -> str:
    """Etiqueta visible de un anclaje para los desplegables."""
    return _ETIQUETAS_ANCLAJE[nombre]


def coordenadas(anclaje, lienzo_ancho, lienzo_alto, margen_pct=2.0):
    if anclaje not in ANCLAJES:
        raise ValueError(f"Anclaje desconocido: {anclaje}")
    margen_x = lienzo_ancho * margen_pct / 100
    margen_y = lienzo_alto * margen_pct / 100
    mascara = ANCLAJES[anclaje]
    x = (margen_x if mascara & 1 else
         lienzo_ancho - margen_x if mascara & 2 else lienzo_ancho / 2)
    y = (margen_y if mascara & 4 else
         lienzo_alto - margen_y if mascara & 8 else lienzo_alto / 2)
    return x, y, mascara


def rectangulo(x, y, ancho, alto, alineacion):
    izquierda = (x if alineacion & 1 else
                 x - ancho if alineacion & 2 else x - ancho / 2)
    arriba = (y if alineacion & 4 else
              y - alto if alineacion & 8 else y - alto / 2)
    return izquierda, arriba, ancho, alto


def escala_para(ancho_deseado, alto_deseado, ancho_fuente, alto_fuente):
    if ancho_fuente <= 0 or alto_fuente <= 0:
        return None
    return ancho_deseado / ancho_fuente, alto_deseado / alto_fuente


def _interseccion(a, b):
    izquierda = max(a[0], b[0])
    arriba = max(a[1], b[1])
    derecha = min(a[0] + a[2], b[0] + b[2])
    abajo = min(a[1] + a[3], b[1] + b[3])
    return max(0.0, derecha - izquierda) * max(0.0, abajo - arriba)


def _area(rect):
    return max(0.0, rect[2]) * max(0.0, rect[3])


def solape(rect_a, rect_b) -> float:
    area_b = _area(rect_b)
    return 0.0 if not area_b else _interseccion(rect_a, rect_b) / area_b * 100


def fuera_del_lienzo(rect, lienzo_ancho, lienzo_alto) -> float:
    area = _area(rect)
    if not area:
        return 0.0
    return (area - _interseccion(rect, (0, 0, lienzo_ancho, lienzo_alto))) / area * 100


def anclaje_de(rect, lienzo_ancho, lienzo_alto, margen_pct=2.0,
               tolerancia_pct=0.5) -> str:
    tolerancia_x = lienzo_ancho * tolerancia_pct / 100
    tolerancia_y = lienzo_alto * tolerancia_pct / 100
    for nombre in ANCLAJES:
        x, y, alineacion = coordenadas(nombre, lienzo_ancho, lienzo_alto, margen_pct)
        esperado = rectangulo(x, y, rect[2], rect[3], alineacion)
        if (abs(rect[0] - esperado[0]) <= tolerancia_x and
                abs(rect[1] - esperado[1]) <= tolerancia_y):
            return nombre
    return ""


@dataclass(frozen=True)
class SnapshotPanel:
    conectado: bool = False
    escena: str = ""
    al_aire: bool = True
    izquierda: float = 0.0
    arriba: float = 0.0
    ancho: int = 0
    alto: int = 0
    lienzo_ancho: int = 0
    lienzo_alto: int = 0
    visible: bool = True
    bloqueada: bool = False
    tapada_por: str = ""
    solapes: tuple = ()
    fuera: float = 0.0
    mensajes_visibles: int = 0
    tamano_letra: int = 0


COMPONENTES = ("conexion", "escena", "posicion", "tamano", "capa",
               "solape", "visible", "bloqueada", "fuera", "aspecto",
               "transparencia")

ACTIVOS_DEFECTO = frozenset({"conexion", "escena", "posicion", "tamano",
                             "capa", "solape", "visible", "bloqueada",
                             "fuera"})


def _porcentaje(valor) -> int:
    return int(round(valor))


# Traductores: cada valor dice dónde está anclado el panel dentro del lienzo.
_LUGARES_ANCLADO = {
    "superior-izquierda": N_("arriba a la izquierda"),
    "superior-centro": N_("arriba al centro"),
    "superior-derecha": N_("arriba a la derecha"),
    "centro-izquierda": N_("centro a la izquierda"),
    "centro": N_("centro"),
    "centro-derecha": N_("centro a la derecha"),
    "inferior-izquierda": N_("abajo a la izquierda"),
    "inferior-centro": N_("abajo al centro"),
    "inferior-derecha": N_("abajo a la derecha"),
}


def _lugar_anclado(nombre):
    return _(_LUGARES_ANCLADO[nombre])


def _salida_horizontal(snap, derecha):
    """Por dónde sale en X y a qué distancia del borde más cercano."""
    if snap.izquierda < 0:
        # Traductores: dice por qué lado se sale del lienzo.
        return _("por la izquierda"), None, None
    if derecha > snap.lienzo_ancho:
        # Traductores: dice por qué lado se sale del lienzo.
        return _("por la derecha"), None, None
    # Traductores: borde más cercano; se compara sin traducir y se traduce al devolver.
    distancia, borde = min([(snap.izquierda, N_("izquierdo")),
                            (snap.lienzo_ancho - derecha, N_("derecho"))])
    return "", distancia, _(borde)


def _salida_vertical(snap, abajo):
    """Por dónde sale en Y y a qué distancia del borde más cercano."""
    if snap.arriba < 0:
        # Traductores: dice por qué lado se sale del lienzo.
        return _("por arriba"), None, None
    if abajo > snap.lienzo_alto:
        # Traductores: dice por qué lado se sale del lienzo.
        return _("por abajo"), None, None
    # Traductores: borde más cercano; se compara sin traducir y se traduce al devolver.
    distancia, borde = min([(snap.arriba, N_("superior")),
                            (snap.lienzo_alto - abajo, N_("inferior"))])
    return "", distancia, _(borde)


def _lugar_libre(snap):
    derecha = snap.izquierda + snap.ancho
    abajo = snap.arriba + snap.alto
    sale_x, distancia_x, borde_x = _salida_horizontal(snap, derecha)
    sale_y, distancia_y, borde_y = _salida_vertical(snap, abajo)
    # Traductores: conjunción entre partes de una frase, con sus espacios.
    salidas = _(" y ").join(salida for salida in (sale_x, sale_y) if salida)
    distancias = []
    if not sale_x:
        # Traductores: {porcentaje} es un número y {borde} uno de los bordes.
        distancias.append(
            _("a {porcentaje}% del borde {borde}").format(
                porcentaje=_porcentaje(distancia_x / snap.lienzo_ancho * 100),
                borde=borde_x))
    if not sale_y:
        # Traductores: {porcentaje} es un número y {borde} uno de los bordes.
        distancias.append(
            _("a {porcentaje}% del borde {borde}").format(
                porcentaje=_porcentaje(distancia_y / snap.lienzo_alto * 100),
                borde=borde_y))
    if salidas and distancias:
        # Traductores: {salidas} son los lados y {distancias} los porcentajes.
        texto = _("se sale del vídeo {salidas}, y {distancias}").format(
            salidas=salidas,
            # Traductores: conjunción entre partes de una frase, con sus espacios.
            distancias=_(" y ").join(distancias))
    elif salidas:
        # Traductores: {salidas} son los lados por donde se sale.
        texto = _("se sale del vídeo {salidas}").format(salidas=salidas)
    else:
        # Traductores: conjunción entre partes de una frase, con sus espacios.
        texto = _(" y ").join(distancias)
    return texto


def _texto_posicion(snap, largo):
    if not snap.ancho or not snap.alto or not snap.lienzo_ancho or not snap.lienzo_alto:
        return ""
    rect = (snap.izquierda, snap.arriba, snap.ancho, snap.alto)
    nombre = anclaje_de(rect, snap.lienzo_ancho, snap.lienzo_alto)
    if nombre:
        texto = _lugar_anclado(nombre)
    else:
        texto = _lugar_libre(snap)
    if not largo:
        texto = texto.capitalize()
    return _("Posición: {texto}").format(texto=texto) if largo else texto


def _conexion(s, largo) -> str:
    return (_("OBS: conectado") if largo and s.conectado
            else (_("Sin conexión con OBS") if not s.conectado else ""))


def _escena(s, largo) -> str:
    if not s.escena:
        return ""
    valor = s.escena + (
        # Traductores: se suma al nombre de la escena cuando no es la actual.
        _(", no es la escena actual") if not s.al_aire else "")
    return _("Escena: {valor}").format(valor=valor) if largo else valor


def _tamano(s, largo) -> str:
    if not s.ancho or not s.alto or not s.lienzo_ancho or not s.lienzo_alto:
        return ""
    pancho = _porcentaje(s.ancho / s.lienzo_ancho * 100)
    palto = _porcentaje(s.alto / s.lienzo_alto * 100)
    if largo:
        return _("Tamaño: {pancho}% del ancho y {palto}% del alto del vídeo "
                 "({ancho} por {alto} píxeles)").format(
                     pancho=pancho, palto=palto, ancho=s.ancho, alto=s.alto)
    return _("{pancho}% del ancho y {palto}% del alto").format(
        pancho=pancho, palto=palto)


def _capa(s, largo) -> str:
    if not s.tapada_por:
        return ""
    return _("La tapa {fuente}").format(fuente=s.tapada_por)


def _solape(s, largo) -> str:
    if not s.solapes:
        return ""
    # El porcentaje de superposición es de la otra fuente; el de recorte, del propio panel.
    # Traductores: {porcentaje} es un número y {fuente} el nombre de la otra fuente.
    partes = [_("al {porcentaje}% de {fuente}").format(
        porcentaje=_porcentaje(porcentaje), fuente=fuente)
              for fuente, porcentaje in s.solapes]
    # Traductores: conjunción entre partes de una frase, con sus espacios.
    return _("Superpone {partes}").format(partes=_(" y ").join(partes))


def _visible(s, largo) -> str:
    return "" if s.visible else _("Oculta en OBS")


def _bloqueada(s, largo) -> str:
    return _("Bloqueada") if s.bloqueada else ""


def _fuera(s, largo) -> str:
    if not s.fuera:
        return ""
    texto = _("queda fuera del vídeo el {porcentaje}% de la fuente").format(
        porcentaje=_porcentaje(s.fuera))
    return texto[:1].upper() + texto[1:]


def _aspecto(s, largo) -> str:
    if not s.mensajes_visibles and not s.tamano_letra:
        return ""
    if largo:
        return _("Entran {mensajes} mensajes, tamaño de letra {letra}").format(
            mensajes=s.mensajes_visibles, letra=s.tamano_letra)
    return _("{mensajes} mensajes, letra {letra}").format(
        mensajes=s.mensajes_visibles, letra=s.tamano_letra)


def _transparencia(s, largo) -> str:
    return (_("El fondo del panel es transparente. Solo se ven las tarjetas "
              "de los mensajes, apiladas contra el borde inferior.")
            if largo else "")


_COMPONENTES_RENDER = {
    "conexion": _conexion,
    "escena": _escena,
    "posicion": _texto_posicion,
    "tamano": _tamano,
    "capa": _capa,
    "solape": _solape,
    "visible": _visible,
    "bloqueada": _bloqueada,
    "fuera": _fuera,
    "aspecto": _aspecto,
    "transparencia": _transparencia,
}


def _render(nombre: str, s: SnapshotPanel, largo: bool) -> str:
    if not s.conectado and nombre != "conexion":
        return ""
    funcion = _COMPONENTES_RENDER.get(nombre)
    if funcion is None:
        return ""
    return funcion(s, largo)


def _se_ve_completa(s: SnapshotPanel) -> bool:
    return bool(s.conectado and s.visible and not s.tapada_por
                and not s.solapes and not s.fuera)


def describir(snap: SnapshotPanel, componentes, modo="corto") -> str:
    partes = []
    revisa_todo = {"capa", "solape", "visible"} <= set(componentes)
    for nombre in COMPONENTES:
        if nombre not in componentes:
            continue
        if nombre == "capa" and revisa_todo and _se_ve_completa(snap):
            partes.append(_("Se ve completa"))
            continue
        texto = _render(nombre, snap, modo == "largo")
        if texto:
            partes.append(texto)
    if not partes:
        return ""
    return "\n".join(partes) if modo == "largo" else "; ".join(partes) + "."


def describir_fuente(nombre, snap, componentes, modo="corto") -> str:
    if not nombre:
        # Sin nombre no hay fuente que describir: «Se ve completa» solo habla
        # del panel y confunde cuando el cuadro describe la escena.
        componentes = tuple(
            componente for componente in componentes if componente != "capa")
    texto = describir(snap, componentes, modo)
    if not nombre:
        return texto
    if modo == "largo":
        # Traductores: {nombre} es el nombre de la fuente.
        return _("Fuente: {nombre}").format(nombre=nombre) + (
            f"\n{texto}" if texto else "")
    # Traductores: {nombre} es el nombre de la fuente; el punto cierra la frase corta.
    return _("{nombre}.").format(nombre=nombre) + (
        f" {texto}" if texto else "")


def describir_preparacion(obs_responde, panel_encendido, puerto, fuente_en_escena):
    if not obs_responde:
        return _("OBS no responde. En OBS, menú Herramientas, Configuración "
                 "del servidor WebSocket, activa el servidor.")
    if panel_encendido and fuente_en_escena:
        return _("Chat en el vídeo activado. La fuente está en esta escena.")
    if not panel_encendido:
        return _("El chat en el vídeo está desactivado.")
    return _("El chat en el vídeo no está en esta escena.")

"""Frases y sonidos de la música, sin interfaz.

Traduce lo que pasa con la música (los códigos del coordinador y las
preferencias) a un `Aviso`: el texto que se anuncia y el sonido que lo
acompaña. Un sonido `None` significa que no se reproduce ninguno. Sin wx y
sin VLC, para poder probarlo solo.
"""

from __future__ import annotations

from dataclasses import dataclass

from bellbird.core import config, musica_decir
from bellbird.core.idioma import N_, _, ngettext
from bellbird.music.modelo import (
    AVANZO,
    COLA_VACIA,
    ERROR_MOTOR,
    FIN_LISTA,
    INICIO_LISTA,
    OK,
    REINICIADO,
    SIN_TEMA,
    TEMA_FALLIDO,
)

SONIDO_TEMA = "musica_tema"
SONIDO_FIN = "musica_fin"
SONIDO_FALLO = "musica_fallo"
SONIDO_ERROR = "error"
SONIDO_ATAJOS_OCUPADOS = "atajos_ocupados"

TEXTO_FIN_LISTA = N_("Fin de la lista de música")
TEXTO_FALLO = N_("No se pudo reproducir: {nombre}. Se pasa al siguiente")
TEXTO_SIN_TEMA = N_("No hay música sonando")
TEXTO_COLA_VACIA = N_("No hay canciones para reproducir")
TEXTO_ULTIMO = N_("Última canción de la lista")
TEXTO_PRIMERO = N_("Primera canción de la lista")
TEXTO_REINICIADO = N_("Desde el comienzo")
TEXTO_PAUSA = N_("Música en pausa")
TEXTO_REANUDADA = N_("Música reanudada")
TEXTO_DETENIDA = N_("Música detenida")
TEXTO_ERROR_MOTOR_TEMA = N_("No se pudo reproducir: {nombre}")
TEXTO_ERROR_MOTOR = N_("No se pudo usar el motor de música")
TEXTO_VOLUMEN = N_("Volumen de la música: {valor}")
TEXTO_QUE_SUENA = N_("Sonando: {nombre}. Canción {posicion} de {total}")
TEXTO_EN_PAUSA = N_("En pausa: {nombre}. Canción {posicion} de {total}")
TEXTO_ESTADO_MUSICA = N_("Música: {nombre}, canción {posicion} de {total}")
TEXTO_ESTADO_MUSICA_PAUSA = N_("Música en pausa: {nombre}, canción {posicion} de {total}")
# Traductores: {cantidad} es cuántas canciones; se oye al retomar la música.
TEXTO_RETOMANDO = N_("Retomando {cantidad}: {nombre}")
TEXTO_ALEATORIO_ON = N_("Orden aleatorio activado")
TEXTO_ALEATORIO_OFF = N_("Orden aleatorio desactivado")
TEXTO_SIN_CARPETA = N_("No hay carpeta de música. Elige una en Preferencias, categoría Música")
TEXTO_MOTOR = N_("La música no está disponible: no se pudo cargar VLC")
TEXTO_PREPARANDO = N_("Preparando la música")
TEXTO_PREPARANDO_OCUPADO = N_("La música se está preparando")
TEXTO_AGREGADOS = N_("{cantidad} canciones agregadas a la cola")
TEXTO_AGREGADO_POSICION = N_("Agregado a la cola, posición {posicion}")
# Traductores: fragmento que se suma a la confirmación, con el tema que suena.
TEXTO_AGREGADO_SUENA = N_(". Sonando: {nombre}")
TEXTO_A_CONTINUACION = N_("A continuación: {nombre}")
TEXTO_A_CONTINUACION_POSICION = N_(
    "A continuación: {nombre}, posición {posicion}")
TEXTO_A_CONTINUACION_VARIOS = N_(
    "{cantidad} canciones a continuación, desde la posición {posicion}")
TEXTO_QUITADO_COLA = N_("Eliminado de la cola: {nombre}")
TEXTO_COLA_VACIADA = N_("Cola vaciada")
TEXTO_COLA_VACIADA_SIGUE = N_("Cola vaciada, sigue sonando {nombre}")
TEXTO_COLA_MEZCLADA = N_("Cola mezclada")
TEXTO_REPETIR_NO = N_("Repetir: no")
TEXTO_REPETIR_TODO = N_("Repetir: toda la cola")
TEXTO_REPETIR_TEMA = N_("Repetir: esta canción")
TEXTO_FALTANTE = N_("No se encontró una canción de la lista: {nombres}")
TEXTO_FALTANTES = N_("No se encontraron {cantidad} canciones de la lista: {nombres}")
TEXTO_AGREGADO_A_LISTA = N_("Agregado a la lista {nombre}")
TEXTO_LISTA_CREADA = N_("Lista creada: {nombre}")
TEXTO_LISTA_RENOMBRADA = N_("Lista renombrada: {nombre}")
TEXTO_LISTA_BORRADA = N_("Lista borrada: {nombre}")
TEXTO_LISTA_GUARDADA = N_("Lista guardada: {nombre}")
TEXTO_TEMA_MOVIDO = N_("Canción movida a la posición {posicion} de {total}")
TEXTO_TEMA_QUITADO = N_("Canción eliminada de la lista")
TEXTO_COLA_SIN_TEMAS = N_("No hay canciones en la cola")
TEXTO_LEYENDO_ENLACE = N_("Leyendo el enlace")
TEXTO_ENLACE_NO_YOUTUBE = N_("Ese enlace no es de YouTube")
# Traductores: {lista} son las combinaciones que otra aplicación ya usa; se oyen.
TEXTO_ATAJOS_GLOBALES_FALLO = N_(
    "No se pudieron usar en cualquier aplicación: {lista}. "
    "Las usa otra aplicación")
TEXTO_ATAJOS_GLOBALES_ACTIVOS = N_("Atajos de música activos en cualquier aplicación")
# Traductores: {app} es el nombre de la aplicación.
_TEXTO_ATAJOS_GLOBALES_SOLO = N_("Atajos de música solo en {app}")
TEXTO_ATAJOS_GLOBALES_SOLO = _TEXTO_ATAJOS_GLOBALES_SOLO.format(app=config.APP_NAME)
TEXTO_VENTANA_ABIERTA = N_("La ventana de música ya está abierta")
TEXTO_BUSQUEDA_BORRADA = N_("Búsqueda borrada")
TEXTO_FILTROS_VISIBLES = N_("Filtros visibles")
TEXTO_FILTROS_OCULTOS = N_("Filtros ocultos")
TEXTO_UN_TEMA_COINCIDE = N_("1 canción coincide")
TEXTO_TEMAS_COINCIDEN = N_("{cantidad} canciones coinciden")
TEXTO_NINGUN_TEMA_COINCIDE = N_("Ninguna canción coincide")
TEXTO_AYUDA_BIBLIOTECA = N_(
    "Intro reproduce ahora, Mayús más Intro a continuación, "
    "Ctrl más Intro al final, tecla de aplicaciones para más opciones")
TEXTO_AYUDA_BIBLIOTECA_LISTA = N_(
    "Intro reproduce ahora, Mayús más Intro a continuación, Ctrl más Intro "
    "al final, tecla de aplicaciones para más opciones. Suprimir elimina de la lista")
TEXTO_AYUDA_COLA = N_(
    "Intro reproduce, Suprimir elimina, Alt más flechas mueve, "
    "tecla de aplicaciones para más opciones")
TEXTO_AYUDA_BUSCAR = N_(
    "Escribe para filtrar, flecha abajo va a las canciones, "
    "Esc borra la búsqueda")
TEXTO_CONFIRMAR_BORRAR_LISTA = N_("¿Borrar la lista {nombre}?")


@dataclass(frozen=True)
class Aviso:
    """Lo que se anuncia por la música: el texto y, si toca, el sonido."""

    texto: str
    sonido: str | None = None


def nombre_tema(tema, incluir_artista: bool) -> str:
    """El título del tema; con artista, «Título, de Artista».
    Un título vacío cae al nombre del archivo sin extensión o, si el origen
    es un enlace, al origen completo.
    """
    titulo = tema.titulo or _titulo_de_origen(tema)
    if incluir_artista and tema.artista:
        # Traductores: {titulo} es la canción y {artista} su artista; filas y avisos.
        return _("{titulo}, de {artista}").format(titulo=titulo, artista=tema.artista)
    return titulo


def _titulo_de_origen(tema) -> str:
    return musica_decir.titulo_respaldo(tema.origen, tema.es_enlace)


def _nombre(resultado, incluir_artista: bool, modo: str | None = None) -> str:
    tema = resultado.tema if resultado.tema is not None else resultado.estado.actual
    if tema is None:
        return ""
    return (musica_decir.texto_tema(tema, musica_decir.modo_manual(modo))
            if modo is not None else nombre_tema(tema, incluir_artista))


def aviso_automatico(resultado, sonido_tema: bool, modo: str) -> Aviso | None:
    """Lo que llega solo por `al_cambiar` del coordinador: «avanzo» respeta el modo;
    «fin_lista» y «tema_fallido» suenan siempre, lo demás no avisa."""
    if resultado.codigo == AVANZO:
        actual = resultado.estado.actual
        texto = musica_decir.texto_tema(actual, modo) if actual is not None else ""
        sonido = SONIDO_TEMA if sonido_tema else None
        if not texto and sonido is None:
            return None
        return Aviso(texto, sonido)
    if resultado.codigo == FIN_LISTA:
        return Aviso(_(TEXTO_FIN_LISTA), SONIDO_FIN)
    if resultado.codigo == TEMA_FALLIDO:
        nombre = nombre_tema(resultado.tema, False) if resultado.tema else ""
        return Aviso(_(TEXTO_FALLO).format(nombre=nombre), SONIDO_FALLO)
    return None


def aviso_accion(accion: str, resultado, incluir_artista: bool,
                 decir_pausa: bool = True, modo: str | None = None) -> Aviso:
    """Lo que pidió el usuario con un atajo o el menú, sin sonido salvo el error,
    porque el usuario lo pidió y está atento.
    """
    codigo = resultado.codigo
    if codigo in (SIN_TEMA, COLA_VACIA):
        return Aviso(_(TEXTO_SIN_TEMA) if codigo == SIN_TEMA else _(TEXTO_COLA_VACIA))
    if codigo == ERROR_MOTOR:
        tema = resultado.tema
        nombre = nombre_tema(tema, incluir_artista) if tema is not None else ""
        texto = (_(TEXTO_ERROR_MOTOR_TEMA).format(nombre=nombre)
                 if nombre else _(TEXTO_ERROR_MOTOR))
        return Aviso(texto, SONIDO_ERROR)
    if codigo == FIN_LISTA and accion == "siguiente":
        return Aviso(_(TEXTO_ULTIMO))
    if codigo == INICIO_LISTA and accion == "anterior":
        return Aviso(_(TEXTO_PRIMERO))
    if codigo == REINICIADO and accion == "anterior":
        return Aviso(_(TEXTO_REINICIADO) if decir_pausa else "")
    if codigo == OK:
        if accion in ("siguiente", "anterior", "reproducir"):
            return Aviso(_nombre(resultado, incluir_artista, modo))
        if accion == "pausa":
            texto = _(TEXTO_PAUSA) if resultado.estado.pausado else _(TEXTO_REANUDADA)
            return Aviso(texto if decir_pausa else "")
        if accion == "detener":
            return Aviso(_(TEXTO_DETENIDA))
    return Aviso("")


def aviso_que_suena(estado, incluir_artista: bool) -> Aviso:
    """Qué está sonando, para el atajo que consulta el estado."""
    actual = estado.actual
    if actual is None or estado.terminado:
        return Aviso(_(TEXTO_SIN_TEMA))
    nombre = nombre_tema(actual, incluir_artista)
    posicion = estado.posicion + 1
    total = len(estado.cola)
    plantilla = _(TEXTO_EN_PAUSA) if estado.pausado else _(TEXTO_QUE_SUENA)
    return Aviso(plantilla.format(nombre=nombre, posicion=posicion, total=total))


def texto_estado_musica(estado, incluir_artista: bool) -> str:
    """Qué suena, para el componente «Música que suena» de F2.

    Vacío sin motor, sin tema o con la lista terminada: en esos casos el
    componente se omite. Función pura.
    """
    if estado is None or estado.actual is None or estado.terminado:
        return ""
    nombre = nombre_tema(estado.actual, incluir_artista)
    plantilla = (_(TEXTO_ESTADO_MUSICA_PAUSA) if estado.pausado
                 else _(TEXTO_ESTADO_MUSICA))
    return plantilla.format(nombre=nombre, posicion=estado.posicion + 1, total=len(estado.cola))


def aviso_retomando(nombre: str, total: int) -> Aviso:
    """Al retomar la música donde quedó, en el primer Reproducir de la sesión."""
    # Traductores: {total} es cuántas canciones; se oye al retomar la música.
    cantidad = ngettext("{total} canción", "{total} canciones", total).format(total=total)
    return Aviso(_(TEXTO_RETOMANDO).format(cantidad=cantidad, nombre=nombre))


def aviso_aleatorio(activo: bool) -> Aviso:
    """Confirmación del orden aleatorio tras el atajo."""
    return Aviso(_(TEXTO_ALEATORIO_ON) if activo else _(TEXTO_ALEATORIO_OFF))


def aviso_sin_carpeta() -> Aviso:
    """No hay carpeta de música elegida en Preferencias."""
    return Aviso(_(TEXTO_SIN_CARPETA), SONIDO_ERROR)


def aviso_motor_no_disponible() -> Aviso:
    """libVLC no se pudo cargar, así que la música no está disponible."""
    return Aviso(_(TEXTO_MOTOR), SONIDO_ERROR)


def aviso_preparando() -> Aviso:
    """Aviso al lanzar la preparación del motor; sin sonido, lo pidió el
    usuario y está atento."""
    return Aviso(_(TEXTO_PREPARANDO))


def aviso_preparando_ocupado() -> Aviso:
    """Una acción llegó mientras el motor todavía se está preparando."""
    return Aviso(_(TEXTO_PREPARANDO_OCUPADO))


def _con_lo_que_suena(texto: str, sonando: str | None) -> str:
    """Suma lo que empezó a sonar a la confirmación de lo agregado."""
    if not sonando:
        return texto
    return texto + _(TEXTO_AGREGADO_SUENA).format(nombre=sonando)


def aviso_agregados(cantidad: int, sonando: str | None = None) -> Aviso:
    """Confirmación de cuántos temas se sumaron a la cola."""
    return Aviso(_con_lo_que_suena(_(TEXTO_AGREGADOS).format(cantidad=cantidad), sonando))


def aviso_a_continuacion(tema, incluir_artista: bool) -> Aviso:
    """Confirmación del tema que sonará al terminar el actual, sin sonido."""
    return Aviso(_(TEXTO_A_CONTINUACION).format(nombre=nombre_tema(tema, incluir_artista)))


def aviso_a_continuacion_posicion(tema, posicion: int,
                                  incluir_artista: bool) -> Aviso:
    """Un tema puesto a continuación, con su posición en la lista visible."""
    return Aviso(_(TEXTO_A_CONTINUACION_POSICION).format(
        nombre=nombre_tema(tema, incluir_artista), posicion=posicion))


def aviso_a_continuacion_varios(cantidad: int, posicion: int) -> Aviso:
    """Varios temas puestos a continuación, desde la primera posición nueva."""
    return Aviso(_(TEXTO_A_CONTINUACION_VARIOS).format(cantidad=cantidad, posicion=posicion))


def aviso_agregado_posicion(posicion: int,
                            sonando: str | None = None) -> Aviso:
    """Un solo tema agregado al final, con su posición nueva."""
    return Aviso(_con_lo_que_suena(_(TEXTO_AGREGADO_POSICION).format(posicion=posicion), sonando))


def aviso_quitado_de_cola(nombre: str) -> Aviso:
    """Confirmación del tema que salió de la cola de reproducción."""
    return Aviso(_(TEXTO_QUITADO_COLA).format(nombre=nombre))


def aviso_cola_vaciada(nombre: str | None = None) -> Aviso:
    """La cola quedó vacía, o quedó solo el tema que sigue sonando."""
    if nombre:
        return Aviso(_(TEXTO_COLA_VACIADA_SIGUE).format(nombre=nombre))
    return Aviso(_(TEXTO_COLA_VACIADA))


def aviso_cola_mezclada() -> Aviso:
    """Confirmación de que la cola visible se reordenó al azar."""
    return Aviso(_(TEXTO_COLA_MEZCLADA))


def aviso_repetir(modo: str) -> Aviso:
    """Confirmación del modo de repetición elegido."""
    textos = {
        "no": _(TEXTO_REPETIR_NO),
        "todo": _(TEXTO_REPETIR_TODO),
        "tema": _(TEXTO_REPETIR_TEMA),
    }
    return Aviso(textos.get(modo, _(TEXTO_REPETIR_NO)))


def aviso_faltantes(nombres) -> Aviso:
    """Las canciones de una lista guardada que no se pudieron leer."""
    lista = tuple(nombres)
    if len(lista) < 2:
        return Aviso(_(TEXTO_FALTANTE).format(nombres=lista[0]) if lista else "")
    if len(lista) > 3:
        # Traductores: {tres} son los tres primeros nombres y {resto} cuántos más hay.
        unidos = _("{tres} y {resto} más").format(
            tres=", ".join(lista[:3]), resto=len(lista) - 3)
    else:
        # Traductores: {anteriores} son los nombres salvo el último y {ultimo} el final.
        unidos = _("{anteriores} y {ultimo}").format(
            anteriores=", ".join(lista[:-1]), ultimo=lista[-1])
    texto = ngettext(TEXTO_FALTANTE, TEXTO_FALTANTES, len(lista))
    return Aviso(texto.format(cantidad=len(lista), nombres=unidos))


def aviso_agregado_a_lista(nombre: str) -> Aviso:
    """Confirmación de que el tema elegido se sumó a una lista."""
    return Aviso(_(TEXTO_AGREGADO_A_LISTA).format(nombre=nombre))


def aviso_lista_creada(nombre: str) -> Aviso:
    """Confirmación de una lista vacía nueva."""
    return Aviso(_(TEXTO_LISTA_CREADA).format(nombre=nombre))


def aviso_lista_renombrada(nombre: str) -> Aviso:
    """Confirmación del nombre nuevo de una lista."""
    return Aviso(_(TEXTO_LISTA_RENOMBRADA).format(nombre=nombre))


def aviso_lista_borrada(nombre: str) -> Aviso:
    """Confirmación de que una lista se eliminó."""
    return Aviso(_(TEXTO_LISTA_BORRADA).format(nombre=nombre))


def aviso_lista_guardada(nombre: str) -> Aviso:
    """Confirmación de que la cola se guardó como lista."""
    return Aviso(_(TEXTO_LISTA_GUARDADA).format(nombre=nombre))


def aviso_tema_movido(posicion: int, total: int) -> Aviso:
    """Confirmación de una reordenación, con la posición nueva y el total."""
    return Aviso(_(TEXTO_TEMA_MOVIDO).format(posicion=posicion, total=total))


def aviso_tema_quitado() -> Aviso:
    """Confirmación de que un tema salió de la lista."""
    return Aviso(_(TEXTO_TEMA_QUITADO))


def aviso_sin_cola() -> Aviso:
    """No hay cola que guardar como lista."""
    return Aviso(_(TEXTO_COLA_SIN_TEMAS))


def aviso_error_listas(mensaje: str) -> Aviso:
    """Fallo al trabajar con las listas: el mensaje y el sonido de error."""
    return Aviso(mensaje, SONIDO_ERROR)


def aviso_leyendo_enlace() -> Aviso:
    """Aviso al empezar a resolver un enlace, sin sonido: lo pidió el usuario."""
    return Aviso(_(TEXTO_LEYENDO_ENLACE))


def aviso_enlace_no_youtube() -> Aviso:
    """La dirección pedida no es de YouTube, con el sonido de error."""
    return Aviso(_(TEXTO_ENLACE_NO_YOUTUBE), SONIDO_ERROR)


def aviso_error_enlace(mensaje: str) -> Aviso:
    """No se pudo leer el enlace: el mensaje y el sonido de error."""
    return Aviso(mensaje, SONIDO_ERROR)


def aviso_atajos_globales_fallo(fallidos) -> Aviso:
    """Combinaciones que otro programa ya tiene, con el tono de ocupado."""
    texto = _(TEXTO_ATAJOS_GLOBALES_FALLO).format(lista=", ".join(fallidos))
    return Aviso(texto, SONIDO_ATAJOS_OCUPADOS)


def aviso_atajos_globales_activos() -> Aviso:
    """Confirmación de que los atajos valen en cualquier programa."""
    return Aviso(_(TEXTO_ATAJOS_GLOBALES_ACTIVOS))


def aviso_atajos_globales_solo() -> Aviso:
    """Confirmación de que los atajos volvieron a valer solo en Bellbird."""
    return Aviso(_(_TEXTO_ATAJOS_GLOBALES_SOLO).format(app=config.APP_NAME))

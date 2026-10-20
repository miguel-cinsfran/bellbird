"""Frases y sonidos de la música, sin interfaz.

Traduce lo que pasa con la música (los códigos del coordinador y las
preferencias) a un `Aviso`: el texto que se anuncia y el sonido que lo
acompaña. Un sonido `None` significa que no se reproduce ninguno. Sin wx y
sin VLC, para poder probarlo solo.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.core import musica_decir
from ytchat.music.modelo import (
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

TEXTO_FIN_LISTA = "Fin de la lista de música"
TEXTO_FALLO = "No se pudo reproducir: {nombre}. Se pasa al siguiente"
TEXTO_SIN_TEMA = "No hay música sonando"
TEXTO_COLA_VACIA = "No hay temas para reproducir"
TEXTO_ULTIMO = "Último tema de la lista"
TEXTO_PRIMERO = "Primer tema de la lista"
TEXTO_REINICIADO = "Desde el comienzo"
TEXTO_PAUSA = "Música en pausa"
TEXTO_REANUDADA = "Música reanudada"
TEXTO_DETENIDA = "Música detenida"
TEXTO_ERROR_MOTOR_TEMA = "No se pudo reproducir: {nombre}"
TEXTO_ERROR_MOTOR = "No se pudo usar el motor de música"
TEXTO_VOLUMEN = "Volumen de la música: {valor}"
TEXTO_QUE_SUENA = "Sonando: {nombre}. Tema {posicion} de {total}"
TEXTO_EN_PAUSA = "En pausa: {nombre}. Tema {posicion} de {total}"
TEXTO_ESTADO_MUSICA = "Música: {nombre}, tema {posicion} de {total}"
TEXTO_ESTADO_MUSICA_PAUSA = "Música en pausa: {nombre}, tema {posicion} de {total}"
TEXTO_RETOMANDO = "Retomando: {nombre}"
TEXTO_ALEATORIO_ON = "Orden aleatorio activado"
TEXTO_ALEATORIO_OFF = "Orden aleatorio desactivado"
TEXTO_SIN_CARPETA = "No hay carpeta de música. Elige una en Preferencias, página Música"
TEXTO_MOTOR = "La música no está disponible: no se pudo cargar VLC"
TEXTO_PREPARANDO = "Preparando la música"
TEXTO_PREPARANDO_OCUPADO = "La música se está preparando"
TEXTO_AGREGADOS = "{cantidad} temas agregados a la cola"
TEXTO_AGREGADO_POSICION = "Agregado a la cola, posición {posicion}"
TEXTO_AGREGADO_SUENA = ". Sonando: {nombre}"
TEXTO_A_CONTINUACION = "A continuación: {nombre}"
TEXTO_A_CONTINUACION_POSICION = "A continuación: {nombre}, posición {posicion}"
TEXTO_A_CONTINUACION_VARIOS = (
    "{cantidad} temas a continuación, desde la posición {posicion}")
TEXTO_QUITADO_COLA = "Quitado de la cola: {nombre}"
TEXTO_COLA_VACIADA = "Cola vaciada"
TEXTO_COLA_VACIADA_SIGUE = "Cola vaciada, sigue sonando {nombre}"
TEXTO_COLA_MEZCLADA = "Cola mezclada"
TEXTO_REPETIR_NO = "Repetir: no"
TEXTO_REPETIR_TODO = "Repetir: toda la cola"
TEXTO_REPETIR_TEMA = "Repetir: este tema"
TEXTO_SALTADAS = "Se saltaron {cantidad} entradas que no se pudieron leer"
TEXTO_SALTADA = "Se saltó 1 entrada que no se pudo leer"
TEXTO_AGREGADO_A_LISTA = "Agregado a la lista {nombre}"
TEXTO_LISTA_CREADA = "Lista creada: {nombre}"
TEXTO_LISTA_RENOMBRADA = "Lista renombrada: {nombre}"
TEXTO_LISTA_BORRADA = "Lista borrada: {nombre}"
TEXTO_LISTA_GUARDADA = "Lista guardada: {nombre}"
TEXTO_TEMA_MOVIDO = "Tema movido a la posición {posicion} de {total}"
TEXTO_TEMA_QUITADO = "Tema quitado de la lista"
TEXTO_COLA_SIN_TEMAS = "No hay temas en la cola"
TEXTO_LEYENDO_ENLACE = "Leyendo el enlace"
TEXTO_ENLACE_NO_YOUTUBE = "Esa dirección no es de YouTube"
TEXTO_ATAJOS_GLOBALES_FALLO = (
    "No se pudieron usar en cualquier programa: {lista}. "
    "Las usa otro programa")
TEXTO_ATAJOS_GLOBALES_ACTIVOS = "Atajos de música activos en cualquier programa"
TEXTO_ATAJOS_GLOBALES_SOLO = "Atajos de música solo en YTChat"
TEXTO_VENTANA_ABIERTA = "La ventana de música ya está abierta"
TEXTO_BUSQUEDA_BORRADA = "Búsqueda borrada"
TEXTO_UN_TEMA_COINCIDE = "1 tema coincide"
TEXTO_TEMAS_COINCIDEN = "{cantidad} temas coinciden"
TEXTO_NINGUN_TEMA_COINCIDE = "Ningún tema coincide"
TEXTO_AYUDA_BIBLIOTECA = (
    "Intro reproduce ahora, Mayús más Intro a continuación, "
    "Control más Intro al final, tecla de aplicaciones para más opciones")
TEXTO_AYUDA_BIBLIOTECA_LISTA = (
    TEXTO_AYUDA_BIBLIOTECA + ", Suprimir quita de la lista")
TEXTO_AYUDA_COLA = (
    "Intro reproduce, Suprimir quita, Alt más flechas mueve, "
    "tecla de aplicaciones para más opciones")
TEXTO_AYUDA_BUSCAR = (
    "Escribe para filtrar, flecha abajo va a los temas, "
    "Escape borra la búsqueda")
TEXTO_CONFIRMAR_BORRAR_LISTA = "¿Borrar la lista {nombre}?"


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
        return f"{titulo}, de {tema.artista}"
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
    """Lo que llega solo por `al_cambiar` del coordinador.

    «avanzo» respeta el modo; «fin_lista» y «tema_fallido» suenan
    siempre. Cualquier otro código no genera aviso.
    """
    if resultado.codigo == AVANZO:
        actual = resultado.estado.actual
        texto = musica_decir.texto_tema(actual, modo) if actual is not None else ""
        sonido = SONIDO_TEMA if sonido_tema else None
        if not texto and sonido is None:
            return None
        return Aviso(texto, sonido)
    if resultado.codigo == FIN_LISTA:
        return Aviso(TEXTO_FIN_LISTA, SONIDO_FIN)
    if resultado.codigo == TEMA_FALLIDO:
        nombre = nombre_tema(resultado.tema, False) if resultado.tema else ""
        return Aviso(TEXTO_FALLO.format(nombre=nombre), SONIDO_FALLO)
    return None


def aviso_accion(accion: str, resultado, incluir_artista: bool,
                 decir_pausa: bool = True, modo: str | None = None) -> Aviso:
    """Lo que pidió el usuario con un atajo o el menú.

    Sin sonido salvo el error, porque el usuario lo pidió y está atento.
    """
    codigo = resultado.codigo
    if codigo in (SIN_TEMA, COLA_VACIA):
        return Aviso(TEXTO_SIN_TEMA if codigo == SIN_TEMA else TEXTO_COLA_VACIA)
    if codigo == ERROR_MOTOR:
        tema = resultado.tema
        nombre = nombre_tema(tema, incluir_artista) if tema is not None else ""
        texto = TEXTO_ERROR_MOTOR_TEMA.format(nombre=nombre) if nombre else TEXTO_ERROR_MOTOR
        return Aviso(texto, SONIDO_ERROR)
    if codigo == FIN_LISTA and accion == "siguiente":
        return Aviso(TEXTO_ULTIMO)
    if codigo == INICIO_LISTA and accion == "anterior":
        return Aviso(TEXTO_PRIMERO)
    if codigo == REINICIADO and accion == "anterior":
        return Aviso(TEXTO_REINICIADO)
    if codigo == OK:
        if accion in ("siguiente", "anterior", "reproducir"):
            return Aviso(_nombre(resultado, incluir_artista, modo))
        if accion == "pausa":
            texto = TEXTO_PAUSA if resultado.estado.pausado else TEXTO_REANUDADA
            return Aviso(texto if decir_pausa else "")
        if accion == "detener":
            return Aviso(TEXTO_DETENIDA)
    return Aviso("")


def aviso_que_suena(estado, incluir_artista: bool) -> Aviso:
    """Qué está sonando, para el atajo que consulta el estado."""
    actual = estado.actual
    if actual is None or estado.terminado:
        return Aviso(TEXTO_SIN_TEMA)
    nombre = nombre_tema(actual, incluir_artista)
    posicion = estado.posicion + 1
    total = len(estado.cola)
    plantilla = TEXTO_EN_PAUSA if estado.pausado else TEXTO_QUE_SUENA
    return Aviso(plantilla.format(nombre=nombre, posicion=posicion, total=total))


def texto_estado_musica(estado, incluir_artista: bool) -> str:
    """Qué suena, para el componente «Música que suena» de F2.

    Vacío sin motor, sin tema o con la lista terminada: en esos casos el
    componente se omite. Función pura.
    """
    if estado is None or estado.actual is None or estado.terminado:
        return ""
    nombre = nombre_tema(estado.actual, incluir_artista)
    plantilla = (TEXTO_ESTADO_MUSICA_PAUSA if estado.pausado
                 else TEXTO_ESTADO_MUSICA)
    return plantilla.format(nombre=nombre, posicion=estado.posicion + 1,
                            total=len(estado.cola))


def aviso_retomando(nombre: str) -> Aviso:
    """Al retomar la música donde quedó, en el primer Reproducir de la sesión."""
    return Aviso(TEXTO_RETOMANDO.format(nombre=nombre))


def aviso_aleatorio(activo: bool) -> Aviso:
    """Confirmación del orden aleatorio tras el atajo."""
    return Aviso(TEXTO_ALEATORIO_ON if activo else TEXTO_ALEATORIO_OFF)


def aviso_sin_carpeta() -> Aviso:
    """No hay carpeta de música elegida en Preferencias."""
    return Aviso(TEXTO_SIN_CARPETA, SONIDO_ERROR)


def aviso_motor_no_disponible() -> Aviso:
    """libVLC no se pudo cargar, así que la música no está disponible."""
    return Aviso(TEXTO_MOTOR, SONIDO_ERROR)


def aviso_preparando() -> Aviso:
    """Aviso al lanzar la preparación del motor; sin sonido, lo pidió el
    usuario y está atento."""
    return Aviso(TEXTO_PREPARANDO)


def aviso_preparando_ocupado() -> Aviso:
    """Una acción llegó mientras el motor todavía se está preparando."""
    return Aviso(TEXTO_PREPARANDO_OCUPADO)


def _con_lo_que_suena(texto: str, sonando: str | None) -> str:
    """Suma lo que empezó a sonar a la confirmación de lo agregado."""
    if not sonando:
        return texto
    return texto + TEXTO_AGREGADO_SUENA.format(nombre=sonando)


def aviso_agregados(cantidad: int, sonando: str | None = None) -> Aviso:
    """Confirmación de cuántos temas se sumaron a la cola."""
    return Aviso(_con_lo_que_suena(
        TEXTO_AGREGADOS.format(cantidad=cantidad), sonando))


def aviso_a_continuacion(tema, incluir_artista: bool) -> Aviso:
    """Confirmación del tema que sonará al terminar el actual, sin sonido."""
    return Aviso(TEXTO_A_CONTINUACION.format(
        nombre=nombre_tema(tema, incluir_artista)))


def aviso_a_continuacion_posicion(tema, posicion: int,
                                  incluir_artista: bool) -> Aviso:
    """Un tema puesto a continuación, con su posición en la lista visible."""
    return Aviso(TEXTO_A_CONTINUACION_POSICION.format(
        nombre=nombre_tema(tema, incluir_artista), posicion=posicion))


def aviso_a_continuacion_varios(cantidad: int, posicion: int) -> Aviso:
    """Varios temas puestos a continuación, desde la primera posición nueva."""
    return Aviso(TEXTO_A_CONTINUACION_VARIOS.format(
        cantidad=cantidad, posicion=posicion))


def aviso_agregado_posicion(posicion: int,
                            sonando: str | None = None) -> Aviso:
    """Un solo tema agregado al final, con su posición nueva."""
    return Aviso(_con_lo_que_suena(
        TEXTO_AGREGADO_POSICION.format(posicion=posicion), sonando))


def aviso_quitado_de_cola(nombre: str) -> Aviso:
    """Confirmación del tema que salió de la cola de reproducción."""
    return Aviso(TEXTO_QUITADO_COLA.format(nombre=nombre))


def aviso_cola_vaciada(nombre: str | None = None) -> Aviso:
    """La cola quedó vacía, o quedó solo el tema que sigue sonando."""
    if nombre:
        return Aviso(TEXTO_COLA_VACIADA_SIGUE.format(nombre=nombre))
    return Aviso(TEXTO_COLA_VACIADA)


def aviso_cola_mezclada() -> Aviso:
    """Confirmación de que la cola visible se reordenó al azar."""
    return Aviso(TEXTO_COLA_MEZCLADA)


def aviso_repetir(modo: str) -> Aviso:
    """Confirmación del modo de repetición elegido."""
    textos = {
        "no": TEXTO_REPETIR_NO,
        "todo": TEXTO_REPETIR_TODO,
        "tema": TEXTO_REPETIR_TEMA,
    }
    return Aviso(textos.get(modo, TEXTO_REPETIR_NO))


def aviso_saltadas(cantidad: int) -> Aviso:
    """Cuántas entradas de una lista guardada no se pudieron leer."""
    if cantidad == 1:
        return Aviso(TEXTO_SALTADA)
    return Aviso(TEXTO_SALTADAS.format(cantidad=cantidad))


def aviso_agregado_a_lista(nombre: str) -> Aviso:
    """Confirmación de que el tema elegido se sumó a una lista."""
    return Aviso(TEXTO_AGREGADO_A_LISTA.format(nombre=nombre))


def aviso_lista_creada(nombre: str) -> Aviso:
    """Confirmación de una lista vacía nueva."""
    return Aviso(TEXTO_LISTA_CREADA.format(nombre=nombre))


def aviso_lista_renombrada(nombre: str) -> Aviso:
    """Confirmación del nombre nuevo de una lista."""
    return Aviso(TEXTO_LISTA_RENOMBRADA.format(nombre=nombre))


def aviso_lista_borrada(nombre: str) -> Aviso:
    """Confirmación de que una lista se eliminó."""
    return Aviso(TEXTO_LISTA_BORRADA.format(nombre=nombre))


def aviso_lista_guardada(nombre: str) -> Aviso:
    """Confirmación de que la cola se guardó como lista."""
    return Aviso(TEXTO_LISTA_GUARDADA.format(nombre=nombre))


def aviso_tema_movido(posicion: int, total: int) -> Aviso:
    """Confirmación de una reordenación, con la posición nueva y el total."""
    return Aviso(TEXTO_TEMA_MOVIDO.format(posicion=posicion, total=total))


def aviso_tema_quitado() -> Aviso:
    """Confirmación de que un tema salió de la lista."""
    return Aviso(TEXTO_TEMA_QUITADO)


def aviso_sin_cola() -> Aviso:
    """No hay cola que guardar como lista."""
    return Aviso(TEXTO_COLA_SIN_TEMAS)


def aviso_error_listas(mensaje: str) -> Aviso:
    """Fallo al trabajar con las listas: el mensaje y el sonido de error."""
    return Aviso(mensaje, SONIDO_ERROR)


def aviso_leyendo_enlace() -> Aviso:
    """Aviso al empezar a resolver un enlace, sin sonido: lo pidió el usuario."""
    return Aviso(TEXTO_LEYENDO_ENLACE)


def aviso_enlace_no_youtube() -> Aviso:
    """La dirección pedida no es de YouTube, con el sonido de error."""
    return Aviso(TEXTO_ENLACE_NO_YOUTUBE, SONIDO_ERROR)


def aviso_error_enlace(mensaje: str) -> Aviso:
    """No se pudo leer el enlace: el mensaje y el sonido de error."""
    return Aviso(mensaje, SONIDO_ERROR)


def aviso_atajos_globales_fallo(fallidos) -> Aviso:
    """Combinaciones que otro programa ya tiene, con el sonido de error."""
    return Aviso(TEXTO_ATAJOS_GLOBALES_FALLO.format(lista=", ".join(fallidos)),
                 SONIDO_ERROR)


def aviso_atajos_globales_activos() -> Aviso:
    """Confirmación de que los atajos valen en cualquier programa."""
    return Aviso(TEXTO_ATAJOS_GLOBALES_ACTIVOS)


def aviso_atajos_globales_solo() -> Aviso:
    """Confirmación de que los atajos volvieron a valer solo en YTChat."""
    return Aviso(TEXTO_ATAJOS_GLOBALES_SOLO)

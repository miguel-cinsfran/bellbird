"""Etapas k a n del recorrido de música real (listas guardadas y enlaces)."""

from __future__ import annotations

import re
import time

from banco_app import VentanaNoActiva
from bellbird.music import anuncios as anuncios_musica
from bellbird.music import enlaces as enlaces_musica
from bellbird.music import listas as listas_musica
from bellbird.music import vista as vista_musica

NOMBRE_LISTA = "QA música real"


def _url_video():
    from tests.test_musica_enlaces import VIDEO
    return f"https://www.youtube.com/watch?v={VIDEO}"


def _url_lista():
    from tests.test_musica_enlaces import LISTA
    return ("https://www.youtube.com/playlist"
            f"?list={LISTA}")


def etapa_k(rec):
    # ── k. Guardar la cola como lista y reproducirla ──

    rec._aire()
    cantidad_cola = _k_guardar_cola(rec)
    cantidad_lista = _k_agregar_tema(rec, cantidad_cola)
    _k_detener(rec)
    indice_qa = _k_indice_qa(rec, cantidad_lista)
    _k_reproducir_lista(rec, cantidad_lista, indice_qa)
    _k_volver(rec)


def _k_guardar_cola(rec):
    cola = rec._filas("Música", "Cola de reproducción") or []
    cantidad_cola = len(cola)
    rec._elegir("Música", "Cola de reproducción", 0)
    try:
        rec._menu_contextual("Música", "Cola de reproducción",
                             "Guardar la cola como lista", responder_ya=True)
    except Exception:
        pass  # el cuadro es modal y se come la respuesta
    if rec.propia.esperar_ventana("Nueva lista", segundos=10) is None:
        rec.corta("musica_real: no abrió «Nueva lista»")
    rec._escribir_cuadro("Nueva lista", NOMBRE_LISTA)
    n = len(rec.propia.anuncios)
    rec._pulsar_aceptar("Nueva lista")
    esperado = anuncios_musica.TEXTO_LISTA_GUARDADA.format(
        nombre=NOMBRE_LISTA)
    if not rec.propia.esperar_dicho(esperado, segundos=10, desde=n):
        rec.res.fallo(f"musica_real: no se anunció «{esperado}»")
    ruta_lista = rec.ruta_listas / (NOMBRE_LISTA + ".m3u8")
    if not ruta_lista.is_file():
        rec.res.fallo("musica_real: no existe el .m3u8 en la carpeta "
                      "de listas")
    else:
        try:
            guardados, _saltadas = listas_musica.cargar(
                rec.ruta_listas, NOMBRE_LISTA)
        except Exception as exc:
            rec.res.fallo(f"musica_real: no se pudo leer la lista "
                          f"guardada: {exc}")
        else:
            if len(guardados) != cantidad_cola:
                rec.res.fallo("musica_real: la lista guardada tiene "
                              f"{len(guardados)} entradas y la cola "
                              f"{cantidad_cola}")
            else:
                rec.res.nota("musica_real: la cola se guarda como lista "
                             f"con {cantidad_cola} entradas")
    return cantidad_cola


def _k_agregar_tema(rec, cantidad_cola):
    # Agregar un tema de la biblioteca a la lista recién guardada, con
    # el submenú del menú de «Canciones».
    rec._elegir("Música", "Colecciones", 0)
    if rec._filas_hasta("Música", "Canciones", 6, 10.0) is None:
        rec.corta("musica_real: la biblioteca no mostró 6 temas para "
                  "agregar a la lista")
    rec._elegir("Música", "Canciones", 0)
    n = len(rec.propia.anuncios)
    rec._menu_contextual("Música", "Canciones",
                         f"Agregar a una lista > {NOMBRE_LISTA}")
    esperado = anuncios_musica.TEXTO_AGREGADO_A_LISTA.format(
        nombre=NOMBRE_LISTA)
    if not rec.propia.esperar_dicho(esperado, segundos=10, desde=n):
        rec.res.fallo(f"musica_real: no se anunció «{esperado}»")
    cantidad_lista = cantidad_cola + 1
    try:
        agregados, _saltadas = listas_musica.cargar(
            rec.ruta_listas, NOMBRE_LISTA)
    except Exception as exc:
        rec.res.fallo(f"musica_real: no se pudo leer la lista tras "
                      f"agregar: {exc}")
    else:
        if len(agregados) != cantidad_lista:
            rec.res.fallo("musica_real: la lista quedó con "
                          f"{len(agregados)} entradas tras agregar y se "
                          f"esperaban {cantidad_lista}")
        else:
            rec.res.nota("musica_real: se agregó un tema de la carpeta a "
                         "la lista")
    return cantidad_lista


def _k_detener(rec):
    n = len(rec.propia.anuncios)
    rec._menu("detener música")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                    segundos=8, desde=n):
        rec.res.fallo("musica_real: detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
    if not rec.sin_salida:
        limite = time.monotonic() + 3
        callado = False
        while time.monotonic() < limite:
            valor = rec._pico()
            if valor is not None and valor < 0.001:
                callado = True
                break
            time.sleep(0.1)
        if not callado:
            rec.res.fallo("musica_real: detenida y el pico no cayó "
                          "bajo 0,001 en 3 s")


def _k_indice_qa(rec, cantidad_lista):
    esperadas = vista_musica.filas_colecciones(
        [NOMBRE_LISTA], cantidad_biblioteca=len(rec.nombres_archivo),
        cantidades={NOMBRE_LISTA: cantidad_lista})
    import musica_colecciones
    fila_biblioteca = esperadas[0]
    fila_qa = esperadas[1]
    # `_filas_hasta` solo espera la cantidad (2) y vuelve enseguida con
    # «Biblioteca» sin contar: se espera la posición real de la lista
    # de QA, con el mismo plazo.
    limite_colecciones = time.monotonic() + 10.0
    elegidas = None
    indice_qa = None
    while time.monotonic() < limite_colecciones:
        elegidas = rec._filas("Música", "Colecciones")
        indice_qa = musica_colecciones.indice_coleccion_qa(
            elegidas, fila_biblioteca, fila_qa)
        if indice_qa is not None:
            break
        time.sleep(0.2)
    if indice_qa is None:
        rec.corta(f"musica_real: «Colecciones» ofrece {elegidas} en vez "
                  f"de {esperadas}")
    rec._elegir("Música", "Colecciones", indice_qa)
    filas = rec._filas_hasta("Música", "Canciones", cantidad_lista, 10.0)
    if filas is None or len(filas) != cantidad_lista:
        rec.corta("musica_real: la lista no trajo "
                  f"{cantidad_lista} temas a «Canciones»")
    return indice_qa


def _k_reproducir_lista(rec, cantidad_lista, indice_qa):
    # El Intro de verdad, como en el paso j, en lugar del menú
    # contextual: reproduce la lista elegida en «Colecciones».
    try:
        rec.propia.pedir("foco", ventana="Música", nombre="Colecciones")
        rec._elegir("Música", "Colecciones", indice_qa)
        rec.propia.teclas("enter")
    except VentanaNoActiva as exc:
        rec.res.no_probado("musica_real: la lista no se pudo reproducir "
                           f"con el teclado real: {exc}")
    else:
        if not rec.sin_salida:
            limite = time.monotonic() + 10
            suena = False
            while time.monotonic() < limite:
                valor = rec._pico()
                if valor is not None and valor > 0.005:
                    suena = True
                    break
                time.sleep(0.1)
            if not suena:
                rec.res.fallo("musica_real: la lista no se oye")
        cola = rec._filas_hasta("Música", "Cola de reproducción",
                                cantidad_lista, 10.0) or []
        if len(cola) != cantidad_lista:
            rec.res.fallo("musica_real: la cola tiene "
                          f"{len(cola)} entradas en vez de {cantidad_lista}")
        else:
            rec.res.nota("musica_real: la lista suena con sus "
                         f"{cantidad_lista} entradas")


def _k_volver(rec):
    rec._elegir("Música", "Colecciones", 0)
    if rec._filas_hasta("Música", "Canciones", 6, 10.0) is None:
        rec.corta("musica_real: al volver a la carpeta no aparecen 6 temas")


def etapa_l(rec):
    # ── l. Agregar el enlace del vídeo: se oye ──

    rec._aire()
    _l_detener(rec)
    _l_agregar_video(rec)


def _l_detener(rec):
    n = len(rec.propia.anuncios)
    rec._menu("detener música")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                    segundos=8, desde=n):
        rec.res.fallo("musica_real: detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
    if not rec.sin_salida:
        limite = time.monotonic() + 3
        callado = False
        while time.monotonic() < limite:
            valor = rec._pico()
            if valor is not None and valor < 0.001:
                callado = True
                break
            time.sleep(0.1)
        if not callado:
            rec.res.fallo("musica_real: detenida y el pico no cayó "
                          "bajo 0,001 en 3 s")


def _l_agregar_video(rec):
    cola_antes = rec._filas("Música", "Cola de reproducción") or []
    try:
        rec.propia.pedir("pulsar", nombre="Abrir enlace", responder_ya=True)
    except Exception:
        pass  # el cuadro es modal y se come la respuesta
    if rec.propia.esperar_ventana("Abrir enlace", segundos=10) is None:
        rec.corta("musica_real: no abrió «Abrir enlace»")
    rec._escribir_cuadro("Abrir enlace", _url_video())
    n = len(rec.propia.anuncios)
    rec._pulsar_y_cerrar("Abrir enlace", "Agregar a la cola")
    if not rec.propia.esperar_dicho(
            anuncios_musica.TEXTO_LEYENDO_ENLACE, segundos=10, desde=n):
        rec.res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_LEYENDO_ENLACE}»")
    prefijo_agregado = anuncios_musica.TEXTO_AGREGADO_POSICION.split(",")[0]
    if not rec.propia.esperar_dicho(prefijo_agregado, segundos=60, desde=n):
        dichos = " ".join(a.get("texto", "")
                          for a in rec.propia.anuncios[n:])[-200:]
        rec.res.fallo("musica_real: el vídeo no se agregó a la cola en "
                      f"60 s; dijo «{dichos}»")
    else:
        _l_juzgar_video(rec, cola_antes)


def _l_juzgar_video(rec, cola_antes):
    cola = rec._filas("Música", "Cola de reproducción") or []
    if len(cola) != len(cola_antes) + 1:
        rec.res.fallo("musica_real: la cola no creció con el enlace")
    else:
        ultimo = rec._titulo_fila(cola[-1])
        if not ultimo:
            rec.res.fallo("musica_real: la última fila de la cola está "
                          "vacía y no se puede comprobar el vídeo")
        else:
            visto = False
            suena = False
            limite = time.monotonic() + 10
            while time.monotonic() < limite:
                actual = (rec._filas("Música",
                                    "Cola de reproducción") or [])
                if (len(actual) == len(cola_antes) + 1 and actual
                        and actual[-1].startswith("Sonando: ")
                        and rec._titulo_fila(actual[-1]) == ultimo):
                    visto = True
                if not rec.sin_salida:
                    valor = rec._pico()
                    if valor is not None and valor > 0.005:
                        suena = True
                if visto and (rec.sin_salida or suena):
                    break
                time.sleep(0.2)
            if not visto:
                rec.res.fallo("musica_real: la última fila de la cola "
                              f"(«{ultimo}») no es lo que suena en 10 s")
            elif rec.sin_salida:
                rec.res.nota("musica_real: el vídeo se agrega a la cola")
            elif not suena:
                rec.res.fallo("musica_real: el vídeo de YouTube no se oye")
            else:
                rec.res.nota("musica_real: el vídeo de YouTube se oye")


def etapa_m(rec):
    # ── m. Agregar el enlace de la lista ──

    rec._aire()
    try:
        rec.propia.pedir("pulsar", nombre="Abrir enlace", responder_ya=True)
    except Exception:
        pass  # el cuadro es modal y se come la respuesta
    if rec.propia.esperar_ventana("Abrir enlace", segundos=10) is None:
        rec.corta("musica_real: no abrió «Abrir enlace» por segunda vez")
    rec._escribir_cuadro("Abrir enlace", _url_lista())
    n = len(rec.propia.anuncios)
    rec._pulsar_y_cerrar("Abrir enlace", "Agregar a la cola")
    limite = time.monotonic() + 90
    agregados = 0
    lista_muerta = False
    patron_agregados = re.compile(
        re.escape(anuncios_musica.TEXTO_AGREGADOS).replace(
            re.escape("{cantidad}"), r"(\d+)"))
    while time.monotonic() < limite:
        for dicho in rec.propia.anuncios[n:]:
            texto = dicho.get("texto", "")
            coincidencia = patron_agregados.search(texto)
            if coincidencia:
                agregados = max(agregados, int(coincidencia.group(1)))
            if (enlaces_musica.TEXTO_NO_SE_PUDO_LEER.lower() in texto.lower()
                    or enlaces_musica.TEXTO_SIN_VIDEOS.lower() in texto.lower()):
                lista_muerta = True
        if agregados >= 2 or lista_muerta:
            break
        time.sleep(0.5)
    if lista_muerta:
        rec.res.no_probado("musica_real: la lista de prueba ya no existe "
                           "en YouTube: cambiarla")
    elif agregados < 2:
        rec.res.fallo("musica_real: la lista no sumó 2 o más temas en 90 s")
    else:
        rec.res.nota(f"musica_real: la lista sumó {agregados} temas")


def etapa_n(rec):
    # ── n. Detener música ──

    rec._aire()
    try:
        rec.propia.pedir("cerrar_ventana", ventana="Música")
    except Exception:
        pass
    n = len(rec.propia.anuncios)
    rec._menu("detener música")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_DETENIDA,
                                    segundos=8, desde=n):
        rec.res.fallo("musica_real: al final detener no anunció "
                      f"«{anuncios_musica.TEXTO_DETENIDA}»")
    if not rec.sin_salida:
        limite = time.monotonic() + 3
        callado = False
        while time.monotonic() < limite:
            valor = rec._pico()
            if valor is not None and valor < 0.001:
                callado = True
                break
            time.sleep(0.1)
        if not callado:
            rec.res.fallo("musica_real: al final el pico no cayó "
                          "bajo 0,001 en 3 s")
    else:
        rec.res.nota("musica_real: recorrido completo sin salida de audio")

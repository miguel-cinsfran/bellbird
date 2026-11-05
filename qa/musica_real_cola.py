"""Etapas a a j del recorrido de música real (la cola y la reproducción)."""

from __future__ import annotations

import time

from banco_app import VentanaNoActiva, subarbol
from guyrapu.music import anuncios as anuncios_musica


def _suena(rec, segundos):
    """Espera a que el pico supere el umbral de sonido audible."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        valor = rec._pico()
        if valor is not None and valor > 0.005:
            return True
        time.sleep(0.1)
    return False


def _callado(rec, segundos):
    """Espera a que el pico caiga por debajo del umbral de silencio."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        valor = rec._pico()
        if valor is not None and valor < 0.001:
            return True
        time.sleep(0.1)
    return False


def etapa_a(rec):
    # ── a. La ventana Música muestra los 6 temas ──

    rec._menu("elegir música")
    if rec.propia.esperar_ventana("Música", segundos=15) is None:
        rec.corta("musica_real: «Elegir música» no abrió la ventana")
    rec.res.nota("musica_real: abre «Música» desde el menú")
    filas = rec._filas_hasta("Música", "Canciones", 6, 30.0)
    if filas is None or len(filas) != 6:
        rec.corta(f"musica_real: la lista de temas tiene "
                  f"{len(filas) if filas is not None else 'nada'} "
                  "elementos en vez de 6")
    # La Cola arranca oculta de fábrica: se la muestra una sola vez con
    # su botón, que así también se prueba, antes de leerla o usarla.
    rec.propia.pedir("pulsar", nombre="Mostrar cola", ventana="Música")
    if rec._filas_hasta("Música", "Cola de reproducción", 0, 1.0) is None:
        rec.corta("musica_real: la Cola no responde tras mostrarla")
    # Los filtros arrancan ocultos y no filtran. Se marca la casilla para
    # comprobar que los dos cuadros aparecen y que se anuncia, y se vuelve
    # a desmarcar para no cambiar lo que ve el resto del recorrido.
    n = len(rec.propia.anuncios)
    rec.propia.pedir("casilla", nombre="Mostrar filtros", ventana="Música",
                     valor=True)
    for nombre in ("Mostrar", "Ordenar por"):
        rama = subarbol(rec._arbol("Música"), nombre)
        if not rama or not rama[0].get("visible"):
            rec.res.fallo("musica_real: al mostrar los filtros no aparece "
                          f"«{nombre}»")
    if not rec.propia.esperar_dicho("Filtros visibles", segundos=5, desde=n):
        rec.res.fallo("musica_real: al mostrar los filtros no se anunció")
    n = len(rec.propia.anuncios)
    rec.propia.pedir("casilla", nombre="Mostrar filtros", ventana="Música",
                     valor=False)
    if not rec.propia.esperar_dicho("Filtros ocultos", segundos=5, desde=n):
        rec.res.fallo("musica_real: al ocultar los filtros no se anunció")
    # Con `--capturas`: la misma ventana, ahora con la cola visible. La
    # apertura con la cola oculta ya la capturó `esperar_ventana`.
    captor_musica = getattr(rec.args, "captor", None)
    if captor_musica is not None:
        captor_musica.capturar(rec.propia, "musica_real", "Música",
                               extra="cola visible")


def etapa_b(rec):
    # ── b. Reproducir todo: anuncia el título y se oye ──

    rec._aire()
    filas = rec._filas_estables("Música", "Canciones")
    titulo_primero = rec._titulo_fila(filas[0]) if filas else ""
    n = len(rec.propia.anuncios)
    rec._elegir("Música", "Canciones", 0)
    rec._menu_contextual("Música", "Canciones",
                         "Reproducir todo desde aquí")
    anunciado = (bool(titulo_primero)
                 and rec.propia.esperar_dicho(titulo_primero, segundos=10,
                                              desde=n))
    suena = False
    todo_none = True
    limite = time.monotonic() + 10
    while time.monotonic() < limite:
        valor = rec._pico()
        if valor is not None:
            todo_none = False
            if valor > 0.005:
                suena = True
                break
        time.sleep(0.1)
    if todo_none:
        rec.sin_salida = True
        rec.res.no_probado("musica_real: sin salida de audio en esta PC; "
                           "se siguen comprobando solo los anuncios y la cola")
    if not anunciado:
        rec.res.fallo("musica_real: no se anunció el título del primer "
                      f"tema («{titulo_primero}»)")
    elif not rec.sin_salida and not suena:
        rec.res.fallo("musica_real: el primer tema no se oye "
                      "(pico bajo 10 s)")
    else:
        rec.res.nota(f"musica_real: suena el primer tema "
                     f"(«{titulo_primero}»)")


def etapa_c(rec):
    # ── c. Pausa y reanudación ──

    rec._aire()
    n = len(rec.propia.anuncios)
    rec._menu("Música > Reproducir o pausar")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_PAUSA, segundos=8,
                                    desde=n):
        rec.res.fallo("musica_real: pausar no anunció "
                      f"«{anuncios_musica.TEXTO_PAUSA}»")
    else:
        rec.res.nota("musica_real: la pausa se anuncia")
    if not rec.sin_salida and not _callado(rec, 3):
        rec.res.fallo("musica_real: pausada y el pico no cayó "
                      "bajo 0,001 en 3 s")
    n = len(rec.propia.anuncios)
    rec._menu("Música > Reproducir o pausar")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_REANUDADA,
                                    segundos=8, desde=n):
        rec.res.fallo("musica_real: reanudar no anunció "
                      f"«{anuncios_musica.TEXTO_REANUDADA}»")
    if not rec.sin_salida and not _suena(rec, 5):
        rec.res.fallo("musica_real: reanudada y no volvió el sonido")


def etapa_d(rec):
    # ── d. Siguiente y anterior, según la cola ──

    rec._aire()
    cola = rec._filas("Música", "Cola de reproducción") or []
    if len(cola) < 2:
        rec.res.fallo("musica_real: la cola no trae dos temas y no se puede "
                      "probar siguiente ni anterior")
    else:
        primero = rec._titulo_fila(cola[0])
        segundo = rec._titulo_fila(cola[1])
        if not primero or not segundo:
            rec.res.fallo("musica_real: la cola trae filas sin título y no "
                          "se puede probar siguiente ni anterior")
        else:
            n = len(rec.propia.anuncios)
            rec._menu("siguiente canción")
            if rec.propia.esperar_dicho(segundo, segundos=8, desde=n):
                rec.res.nota(f"musica_real: siguiente anuncia «{segundo}»")
            else:
                rec.res.fallo("musica_real: «Siguiente canción» no anunció "
                              f"«{segundo}»")
            n = len(rec.propia.anuncios)
            rec._menu("canción anterior")
            reiniciado = False
            limite = time.time() + 8
            while time.time() < limite:
                if rec.propia.dijo(anuncios_musica.TEXTO_REINICIADO,
                                   desde=n):
                    reiniciado = True
                    break
                if rec.propia.dijo(primero, desde=n):
                    break
                time.sleep(0.1)
            if reiniciado:
                rec.res.nota("musica_real: anterior reinició el tema")
                n = len(rec.propia.anuncios)
                rec._menu("canción anterior")
                if rec.propia.esperar_dicho(primero, segundos=8, desde=n):
                    rec.res.nota(f"musica_real: anterior anuncia «{primero}»")
                else:
                    rec.res.fallo("musica_real: «Canción anterior» no anunció "
                                  f"«{primero}»")
            elif rec.propia.dijo(primero, desde=n):
                rec.res.nota(f"musica_real: anterior anuncia «{primero}»")
            else:
                rec.res.fallo("musica_real: «Canción anterior» no anunció "
                              f"«{primero}»")


def etapa_e(rec):
    # ── e. Volumen: sube a 50 y vuelve a 40 ──

    rec._aire()
    n = len(rec.propia.anuncios)
    rec._menu("Música > Subir volumen")
    esperado = anuncios_musica.TEXTO_VOLUMEN.format(valor=50)
    if not rec.propia.esperar_dicho(esperado, segundos=8, desde=n):
        rec.res.fallo(f"musica_real: subir no anunció «{esperado}»")
    n = len(rec.propia.anuncios)
    rec._menu("Música > Bajar volumen")
    esperado = str(40)
    if not rec.propia.esperar_dicho(esperado, segundos=8, desde=n):
        rec.res.fallo(f"musica_real: bajar no anunció «{esperado}»")
    else:
        rec.res.nota("musica_real: el volumen sube a 50 y vuelve a 40")


def etapa_f(rec):
    # ── f. Anunciar canción actual contiene el título actual ──

    rec._aire()
    cola = rec._filas("Música", "Cola de reproducción") or []
    actual = next((f for f in cola if f.startswith("Sonando: ")), "")
    titulo_actual = rec._titulo_fila(actual) if actual else ""
    if not actual or not titulo_actual:
        rec.res.fallo("musica_real: la cola no marca ningún tema actual y "
                      "no se puede probar la canción actual")
    else:
        antes, despues = anuncios_musica.TEXTO_QUE_SUENA.split("{nombre}")
        posicion = cola.index(actual) + 1
        fragmento_titulo = antes + titulo_actual
        fragmento_tema = despues.format(posicion=posicion,
                                        total=len(cola))
        n = len(rec.propia.anuncios)
        rec._menu("anunciar canción actual")
        if not rec.propia.esperar_dicho(fragmento_titulo, segundos=8,
                                        desde=n):
            rec.res.fallo("musica_real: «Anunciar canción actual» no dijo "
                          f"«{fragmento_titulo}»")
        else:
            limite = time.monotonic() + 8
            oido = ""
            while time.monotonic() < limite:
                for dicho in rec.propia.anuncios[n:]:
                    texto = dicho.get("texto", "")
                    if (fragmento_titulo.lower() in texto.lower()
                            and fragmento_tema.lower() in texto.lower()):
                        oido = texto
                        break
                if oido:
                    break
                time.sleep(0.1)
            if oido:
                rec.res.nota(f"musica_real: anunciar canción actual dice «{oido}»")
            elif not any(fragmento_tema.lower()
                         in d.get("texto", "").lower()
                         for d in rec.propia.anuncios[n:]):
                rec.res.fallo("musica_real: «Anunciar canción actual» no dijo "
                              f"«{fragmento_tema}»")
            else:
                rec.res.fallo("musica_real: «Anunciar canción actual» dijo "
                              f"«{fragmento_titulo}» y «{fragmento_tema}» "
                              "pero nunca en el mismo anuncio")


def etapa_f2(rec):
    # ── f2. Atajos globales con otra ventana al frente ──

    import musica_globales
    musica_globales.probar_atajos_globales(rec.propia, rec.res,
                                           rec.tmp_respaldo)


def etapa_g(rec):
    # ── g. Orden aleatorio dos veces ──

    rec._aire()
    n = len(rec.propia.anuncios)
    rec._menu("orden aleatorio")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_ALEATORIO_ON,
                                    segundos=8, desde=n):
        rec.res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_ALEATORIO_ON}»")
    n = len(rec.propia.anuncios)
    rec._menu("orden aleatorio")
    if not rec.propia.esperar_dicho(anuncios_musica.TEXTO_ALEATORIO_OFF,
                                    segundos=8, desde=n):
        rec.res.fallo("musica_real: no se anunció "
                      f"«{anuncios_musica.TEXTO_ALEATORIO_OFF}»")
    else:
        rec.res.nota("musica_real: el orden aleatorio se anuncia "
                     "activado y desactivado")


def etapa_h(rec):
    # ── h. El corto a continuación, suena y avanza solo ──

    rec._aire()
    rec._aislar(5, "06 corto QA")
    cola_antes = rec._filas("Música", "Cola de reproducción") or []
    n = len(rec.propia.anuncios)
    rec.propia.pedir("tecla_en", ventana="Música", nombre="Canciones",
                     tecla="enter", modificadores=["shift"])
    esperado = anuncios_musica.TEXTO_A_CONTINUACION.format(
        nombre="06 corto QA")
    if not rec.propia.esperar_dicho(esperado, segundos=8, desde=n):
        rec.res.fallo(f"musica_real: no se anunció «{esperado}»")
    cola = rec._filas("Música", "Cola de reproducción") or []
    if (len(cola) != len(cola_antes) + 1
            or rec._titulo_fila(cola[1]) != "06 corto QA"):
        rec.res.fallo("musica_real: «06 corto QA» no quedó justo detrás "
                      "del actual en la cola")
    else:
        rec.res.nota("musica_real: el corto queda justo detrás del actual")
    que_seguia = rec._titulo_fila(cola[2]) if len(cola) > 2 else ""
    n = len(rec.propia.anuncios)
    rec._menu("siguiente canción")
    if not rec.propia.esperar_dicho("06 corto QA", segundos=10, desde=n):
        rec.res.fallo("musica_real: «Siguiente canción» no anunció el corto")
    elif que_seguia and rec.propia.esperar_dicho(que_seguia, segundos=15,
                                                 desde=n):
        rec.res.nota(f"musica_real: el corto sonó y avanzó solo "
                     f"a «{que_seguia}»")
    else:
        rec.res.fallo("musica_real: el corto no avanzó solo al tema que "
                      f"seguía («{que_seguia}»)")
    rec._filtrar("Música", "")
    if rec._filas_hasta("Música", "Canciones", 6, 10.0) is None:
        rec.corta("musica_real: al limpiar el buscador no vuelven los 6")


def etapa_i(rec):
    # ── i. El quinto a la cola ──

    rec._aire()
    filas = rec._filas_estables("Música", "Canciones") or []
    if len(filas) != 6:
        rec.corta("musica_real: la lista de temas no tiene 6 elementos")
    quinto = rec._titulo_fila(filas[4])
    rec._aislar(4, quinto)
    cola_antes = rec._filas("Música", "Cola de reproducción") or []
    rec.propia.pedir("tecla_en", ventana="Música", nombre="Canciones",
                     tecla="enter", modificadores=["ctrl"])
    cola = rec._filas("Música", "Cola de reproducción") or []
    if (len(cola) != len(cola_antes) + 1
            or (quinto and rec._titulo_fila(cola[-1]) != quinto)):
        rec.res.fallo("musica_real: la cola no creció en uno con el "
                      f"quinto («{quinto}»)")
    else:
        rec.res.nota("musica_real: el quinto se agrega al final de la cola")
    rec._filtrar("Música", "")
    rec._filas_hasta("Música", "Canciones", 6, 10.0)


def etapa_j(rec):
    # ── j. Reproducir ahora el tercero ──

    rec._aire()
    filas = rec._filas_estables("Música", "Canciones") or []
    if len(filas) != 6:
        rec.corta("musica_real: la lista de temas no tiene 6 elementos")
    tercero = rec._titulo_fila(filas[2])
    cola_antes = rec._filas("Música", "Cola de reproducción") or []
    # `reproducir_ahora` inserta el tema detrás del que suena, así que el
    # contrato está en esa fila y no en que la cola copie la carpeta:
    # comparar contra la carpeta medía el botón viejo «Reproducir este».
    indice_sonando = next((i for i, f in enumerate(cola_antes)
                           if f.startswith("Sonando: ")), None)
    n = len(rec.propia.anuncios)
    # El Intro de verdad, no un EVT_KEY_DOWN armado a mano: el 19/10/2026
    # la lista de temas y la Cola quedaban mudas con el teclado de
    # Windows porque el diálogo se comía la tecla antes del control.
    try:
        rec.propia.pedir("foco", ventana="Música", nombre="Canciones")
        rec._elegir("Música", "Canciones", 2)
        rec.propia.teclas("enter")
    except VentanaNoActiva as exc:
        rec.res.no_probado("musica_real: «Reproducir ahora» no se pudo probar "
                           f"con el teclado real: {exc}")
    else:
        _juzgar_reproducir_ahora(rec, tercero, cola_antes, indice_sonando, n)


def _juzgar_reproducir_ahora(rec, tercero, cola_antes, indice_sonando, n):
    if not tercero:
        rec.res.fallo("musica_real: la tercera fila no tiene título y no "
                      "se puede probar «Reproducir ahora»")
    elif not rec.propia.esperar_dicho(tercero, segundos=10, desde=n):
        rec.res.fallo("musica_real: «Reproducir ahora» no anunció "
                      f"«{tercero}»")
    cola = rec._filas("Música", "Cola de reproducción") or []
    if not cola:
        rec.res.fallo("musica_real: la cola está vacía tras "
                      "«Reproducir ahora»")
    elif len(cola) != len(cola_antes) + 1:
        rec.res.fallo("musica_real: «Reproducir ahora» no agregó un tema "
                      "a la cola")
    elif indice_sonando is None:
        rec.res.fallo("musica_real: antes de «Reproducir ahora» la cola "
                      "no marcaba ningún tema sonando")
    else:
        siguiente = cola[indice_sonando + 1: indice_sonando + 2]
        if (not siguiente or not siguiente[0].startswith("Sonando: ")
                or rec._titulo_fila(siguiente[0]) != tercero):
            rec.res.fallo("musica_real: «Reproducir ahora» no dejó el "
                          "tercero sonando justo detrás del que sonaba")
        elif not rec.sin_salida and not _suena(rec, 10):
            rec.res.fallo("musica_real: el tercero no se oye")

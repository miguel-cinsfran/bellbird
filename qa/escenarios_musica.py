"""Escenarios de música y del reproductor."""

from __future__ import annotations

import time

from banco_app import (
    Aplicacion, DIRECTO_YOUTUBE, OrdenRechazada, Resultado, VentanaNoActiva,
    conectar_de_verdad,
)
from banco_auditoria import auditar_dialogo, recorrer_tab

from musica_real import RecorridoMusica, _Corte
from musica_real_cola import (
    etapa_a, etapa_b, etapa_c, etapa_d, etapa_e, etapa_f, etapa_f2, etapa_g,
    etapa_h, etapa_i, etapa_j,
)
from musica_real_enlaces import etapa_k, etapa_l, etapa_m, etapa_n
from musica_real_preparar import (
    preparar_datos, preparar_origen, restaurar,
)

# Cuánto puede tardar una acción del reproductor antes de que se note. Medio
# segundo no lo percibe nadie; a partir de uno la ventana ya "va dura", y por
# encima de dos, sin ver la pantalla, no se sabe si la tecla entró.
BLOQUEO_SOSPECHOSO = 1.0
BLOQUEO_INACEPTABLE = 2.0
# Y cuánto puede tardar en hablar. Un anuncio que llega tarde es peor que uno
# que no llega: para entonces la persona ya pulsó otra cosa.
VOZ_LENTA = 1.5


def medir_accion(app: Aplicacion, hacer, espera: float = 3.0):
    """Hace algo y mide las dos cosas que producen «torpeza».

    La primera es cuánto tarda la ventana en volver a atender a nadie. Como la
    sonda despacha con `wx.CallAfter`, un `ping` que vuelve es la prueba de que
    el hilo de interfaz está libre otra vez; lo que tarde en volver es tiempo
    en el que la aplicación no responde a una tecla.

    La segunda es cuánto tarda en decir algo. Devuelve
    `(bloqueo, latencia_de_voz, lo_que_dijo)`, con la latencia en `None` si no
    llegó a hablar.
    """
    # Esperar a que la aplicación se calle ANTES de actuar. Si no, el primer
    # anuncio que llegue se le atribuye a la acción, y con una carga en vuelo
    # eso mide la red y no el control. El 21/08/2026 esto produjo tres fallos
    # contra un directo real que en la corrida siguiente no aparecieron.
    quieto = time.time() + 8
    ultimo = len(app.anuncios)
    calma = time.time() + 0.6
    while time.time() < quieto and time.time() < calma:
        if len(app.anuncios) != ultimo:
            ultimo = len(app.anuncios)
            calma = time.time() + 0.6
        time.sleep(0.05)

    antes = len(app.anuncios)
    t0 = time.time()
    hacer()
    app.pedir("ping", tiempo=120)
    bloqueo = time.time() - t0

    latencia = None
    limite = time.time() + espera
    while time.time() < limite:
        if any(a["canal"] == "voz" for a in app.anuncios[antes:]):
            latencia = time.time() - t0
            break
        time.sleep(0.05)
    dichos = [a["texto"] for a in app.anuncios[antes:] if a["canal"] == "voz"]
    return bloqueo, latencia, dichos


def juzgar_accion(res: Resultado, donde: str, que: str, medida) -> bool:
    """Convierte una medida en veredicto. Devuelve si habló."""
    bloqueo, latencia, dichos = medida
    if not dichos:
        res.fallo(f"{donde}: {que} no dice nada")
        hablo = False
    else:
        hablo = True
        detalle = dichos[0][:58]
        if latencia is not None and latencia > VOZ_LENTA:
            res.fallo(f"{donde}: {que} tarda {latencia:.1f} s en decir "
                      f"«{detalle}»")
        else:
            res.nota(f"{donde}: {que} dice «{detalle}»"
                     + (f", a los {latencia:.2f} s" if latencia else ""))

    if bloqueo > BLOQUEO_INACEPTABLE:
        res.fallo(f"{donde}: {que} deja la ventana {bloqueo:.1f} s sin responder")
    elif bloqueo > BLOQUEO_SOSPECHOSO:
        res.nota(f"{donde}: ojo, {que} tarda {bloqueo:.1f} s en devolver la "
                 f"ventana")
    return hablo


# Los seis botones de transporte, por la etiqueta con la que se los encuentra.
BOTONES_REPRODUCTOR = (
    ("Reproducir", "el botón de reproducir"),
    ("Retroceder 1 min", "el botón de retroceder"),
    ("Avanzar 1 min", "el botón de avanzar"),
    ("Detener", "el botón de detener"),
    ("Silenciar audio", "el botón de silenciar"),
    ("Pantalla completa", "el botón de pantalla completa"),
)

# Y los atajos, que son el camino que de verdad usa quien no ve la pantalla:
# `AGENTS.md` cuenta que los botones vienen ocultos justamente porque se maneja
# por teclado. Son los de `config.ATAJOS_DEFAULTS`, área Ctrl.
ATAJOS_REPRODUCTOR = (
    (("p", ["ctrl"]), "Ctrl+P, reproducir o pausa"),
    (("left", ["ctrl"]), "Ctrl+Izquierda, retroceder"),
    (("right", ["ctrl"]), "Ctrl+Derecha, avanzar"),
    (("m", ["ctrl"]), "Ctrl+M, silenciar"),
    (("up", ["ctrl"]), "Ctrl+Arriba, subir volumen"),
    (("down", ["ctrl"]), "Ctrl+Abajo, bajar volumen"),
    (("d", ["ctrl"]), "Ctrl+D, detener"),
)


def bateria_reproductor(app: Aplicacion, res: Resultado, donde: str,
                        hay_medio: bool = False) -> None:
    """Maltrata el reproductor entero y mide cada golpe.

    Se usa dos veces: sin nada cargado, que es como arranca la aplicación, y
    contra un directo de verdad desde `escenario_directo_youtube`. Las dos
    situaciones tienen que hablar; la segunda además tiene que ser rápida.
    `hay_medio` lo dice quien llama, que es quien cargó el medio: sin vídeo
    el volumen con flechas tiene que avisar y no moverse, con vídeo se mueve
    en silencio.
    """
    # ── los seis botones ────────────────────────────────────────────────────
    for etiqueta, quien in BOTONES_REPRODUCTOR:
        medida = medir_accion(app, lambda e=etiqueta: app.pedir("pulsar", nombre=e))
        juzgar_accion(res, donde, quien, medida)

        # Pantalla completa abre una ventana nueva que se queda con el foco y
        # con el teclado. Hay que volver, o todo lo que se mida después se mide
        # sobre la ventana equivocada.
        if etiqueta == "Pantalla completa":
            ctrl = app.foco() or {}
            nombre = (ctrl.get("nombre") or ctrl.get("etiqueta") or "").strip()
            if not nombre:
                res.fallo(f"{donde}: en pantalla completa el foco queda en un "
                          f"control sin nombre ({ctrl.get('clase')})")
            else:
                res.nota(f"{donde}: en pantalla completa el foco va a «{nombre}»")
            medida = medir_accion(
                app, lambda e=etiqueta: app.pedir("pulsar", nombre=e))
            juzgar_accion(res, donde, "salir de pantalla completa", medida)
            ctrl = app.foco() or {}
            nombre = (ctrl.get("nombre") or ctrl.get("etiqueta") or "").strip()
            if not nombre:
                res.fallo(f"{donde}: al salir de pantalla completa el foco "
                          f"queda en el aire ({ctrl.get('clase')})")
            else:
                res.nota(f"{donde}: al salir, el foco vuelve a «{nombre}»")

    # ── dos pulsaciones seguidas, que es lo que hace cualquiera cuando la
    #    primera no contestó ─────────────────────────────────────────────────
    app.pedir("pulsar", nombre="Reproducir")
    medida = medir_accion(app, lambda: app.pedir("pulsar", nombre="Reproducir"))
    if not medida[2]:
        res.fallo(f"{donde}: pulsar reproducir dos veces seguidas deja la "
                  f"segunda muda")
    else:
        res.nota(f"{donde}: la segunda pulsación de reproducir también habla")

    # ── los siete atajos ────────────────────────────────────────────────────
    # Antes de juzgar los atajos hay que saber si el menú que los sostiene está
    # encendido. `gui.py:1769` apaga el menú Reproductor entero mientras no hay
    # conexión (`mb.EnableTop`), y un menú apagado se lleva por delante a sus
    # siete aceleradores aunque cada ítem se declare habilitado. Sin esto, el
    # banco daba siete atajos por rotos cuando lo que pasaba es que estaban
    # apagados a propósito.
    menu_vivo = None
    for m in app.menus():
        if m["camino"].strip().lower() == "reproductor":
            menu_vivo = bool(m.get("habilitado"))
            break
    if menu_vivo is False:
        res.nota(f"{donde}: el menú Reproductor está apagado, así que sus siete "
                 f"atajos no pueden funcionar")
        # Y ahí está lo que sí es un defecto: los botones de la ventana siguen
        # encendidos y respondiendo. Dos caminos para lo mismo, uno vivo y otro
        # muerto, sin que nada se lo diga a quien no ve la pantalla.
        encendidos = [c.get("etiqueta") or c.get("nombre")
                      for c in app.arbol()
                      if c.get("clase") in ("Button", "BitmapButton")
                      and c.get("habilitado") and c.get("en_pantalla")
                      and (c.get("etiqueta") or "") in
                      [e for e, _ in BOTONES_REPRODUCTOR]]
        if encendidos:
            res.fallo(f"{donde}: con el menú Reproductor apagado, sus atajos no "
                      f"hacen nada pero estos botones siguen encendidos y "
                      f"funcionando: " + ", ".join(encendidos))

    # Los aceleradores solo llegan si el foco está DENTRO de un control, no en
    # el frame. Se ancla a propósito para que el resultado no dependa de dónde
    # lo haya dejado la comprobación anterior.
    for candidato in ("Volumen del reproductor", "Enlace del directo o vídeo", "Chat del directo"):
        try:
            app.pedir("foco", nombre=candidato)
            break
        except OrdenRechazada:
            continue

    for combo, quien in ATAJOS_REPRODUCTOR:
        try:
            medida = medir_accion(app, lambda c=combo: app.teclas(c))
        except VentanaNoActiva as exc:
            res.no_probado(f"{donde}: no se pudo probar {quien}, {exc}")
            continue
        if menu_vivo is False:
            if medida[2]:
                res.nota(f"{donde}: {quien} habla aun con el menú apagado")
            continue
        juzgar_accion(res, donde, quien, medida)

    # ── los dos deslizadores, con las flechas ───────────────────────────────
    # La posición anuncia; el volumen NO, a propósito desde el 15/10: NVDA
    # ya lee el valor del deslizador y se oía dos veces. La excepción, a
    # propósito desde el 19/10/2026: sin vídeo cargado `ajustar_volumen`
    # avisa «No hay ningún vídeo cargado» y no cambia nada.
    try:
        app.pedir("foco", nombre="Posición de reproducción")
    except OrdenRechazada as exc:
        res.fallo(f"{donde}: no se llega a la posición, {exc}")
    else:
        for tecla in ("right", "left"):
            try:
                medida = medir_accion(app, lambda t=tecla: app.teclas(t))
            except VentanaNoActiva as exc:
                res.no_probado(f"{donde}: no se pudo probar la posición, {exc}")
                break
            juzgar_accion(res, donde, f"la posición con la flecha {tecla}",
                          medida)
    try:
        app.pedir("foco", nombre="Volumen del reproductor")
    except OrdenRechazada as exc:
        res.fallo(f"{donde}: no se llega al volumen, {exc}")
    else:
        for tecla in ("up", "down"):
            previo = _valor_deslizador(app, "Volumen del reproductor")
            try:
                medida = medir_accion(app, lambda t=tecla: app.teclas(t))
            except VentanaNoActiva as exc:
                res.no_probado(f"{donde}: no se pudo probar el volumen, {exc}")
                break
            _juzgar_volumen_silencioso(app, res, donde, tecla, medida, previo,
                                     hay_medio)


def _valor_deslizador(app: Aplicacion, nombre: str):
    """El valor de un deslizador, leído con la sonda. None si no se pudo."""
    objetivo = (nombre or "").strip().lower()
    try:
        controles = app.arbol()
    except Exception:
        return None
    for c in controles:
        if c.get("clase") != "Slider":
            continue
        junto = ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
        if objetivo in junto.strip().lower():
            return c.get("valor")
    return None


def _juzgar_volumen_silencioso(app: Aplicacion, res: Resultado, donde: str,
                               tecla: str, medida, previo,
                               hay_medio: bool = False) -> None:
    """El volumen con flechas no anuncia y tiene que mover el deslizador.

    Sin vídeo cargado es al revés, a propósito desde el 19/10/2026:
    `ajustar_volumen` avisa «No hay ningún vídeo cargado» y no cambia nada.
    """
    bloqueo, _latencia, dichos = medida
    if hay_medio:
        if dichos:
            res.fallo(f"{donde}: el volumen con la flecha {tecla} anuncia "
                      f"«{dichos[0][:58]}», y no debería: NVDA ya lee el valor "
                      "del deslizador")
        else:
            res.nota(f"{donde}: el volumen con la flecha {tecla} no anuncia, "
                     "a propósito")
    elif any("No hay ningún vídeo cargado" in d for d in dichos):
        res.nota(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                 "avisa «No hay ningún vídeo cargado»")
    elif dichos:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  f"anuncia «{dichos[0][:58]}» en vez de avisar "
                  "«No hay ningún vídeo cargado»")
    else:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  "no avisa «No hay ningún vídeo cargado»")
    if bloqueo > BLOQUEO_INACEPTABLE:
        res.fallo(f"{donde}: el volumen con la flecha {tecla} deja la ventana "
                  f"{bloqueo:.1f} s sin responder")
    elif bloqueo > BLOQUEO_SOSPECHOSO:
        res.nota(f"{donde}: ojo, el volumen con la flecha {tecla} tarda "
                 f"{bloqueo:.1f} s en devolver la ventana")
    posterior = _valor_deslizador(app, "Volumen del reproductor")
    if previo is None or posterior is None:
        res.nota(f"{donde}: la sonda no leyó el valor del deslizador, así que "
                 f"el cambio con la flecha {tecla} queda sin comprobar")
    elif hay_medio:
        if posterior == previo:
            res.fallo(f"{donde}: el volumen con la flecha {tecla} no movió el "
                      f"deslizador (sigue en {previo})")
        else:
            res.nota(f"{donde}: el volumen con la flecha {tecla} mueve el "
                     f"deslizador de {previo} a {posterior}")
    elif posterior != previo:
        res.fallo(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                  f"movió el deslizador de {previo} a {posterior}, "
                  "y no debería")
    else:
        res.nota(f"{donde}: sin vídeo, el volumen con la flecha {tecla} "
                 f"deja el deslizador en {previo}, a propósito")


def escenario_reproductor(app: Aplicacion, args, res: Resultado):
    """El reproductor sin nada cargado, que es como arranca la aplicación.

    Nunca lo probó nadie: `reproductor.py` son 1.059 líneas con cinco pruebas,
    y las cinco son del parser de atajos. El recorrido de Tab lo pasaba de largo
    porque los seis botones vienen ocultos de fábrica.

    Va primero de todos los escenarios y no es capricho: en cuanto `chat` o
    `tiktok` simulan una sesión, el estado «sin nada cargado» no vuelve sin
    reiniciar, y el botón de reproducir pasa la comprobación por el motivo
    equivocado.

    La regla que se comprueba no admite matices: un control que se activa y no
    dice nada es indistinguible, para quien no ve la pantalla, de una
    aplicación colgada. Y uno que tarda dos segundos en contestar, también.
    """
    if not app.al_frente():
        res.nota("reproductor: Windows no puso la ventana al frente")

    # Sin python-vlc el panel no se construye: en su lugar va un aviso de una
    # línea. Juzgar los botones ahí daría seis fallos de accesibilidad que en
    # realidad son una dependencia que falta.
    todo = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                    for c in app.arbol())
    if "AvisoReproductor" in todo or "no disponible" in todo.lower():
        res.nota("reproductor: no hay panel; falta VLC o yt-dlp en este "
                 "entorno, así que no se juzga nada. Correlo con el intérprete "
                 "del proyecto, .venv/Scripts/python.exe")
        return

    # Los botones vienen ocultos («minimalista»), y ocultos wx los saca del
    # recorrido de Tab. Hay que mostrarlos para poder probarlos como los prueba
    # una persona. Se anota cómo estaban para dejarlo igual al terminar.
    # Se pregunta por la etiqueta del propio interruptor, que dice «Ocultar…»
    # cuando están visibles y «Mostrar…» cuando no. Mirar `en_pantalla` de los
    # botones no sirve: `IsShownOnScreen` da falso también cuando la ventana
    # está tapada o minimizada, y entonces el banco creía que estaban ocultos,
    # los ocultaba, y encima le dejaba la preferencia cambiada al dueño.
    estaban_visibles = any(
        (c.get("etiqueta") or "").lower().startswith("ocultar botones")
        for c in app.arbol())
    if not estaban_visibles:
        medida = medir_accion(
            app, lambda: app.pedir("pulsar", nombre="AlternarBotonesReproductor"))
        juzgar_accion(res, "reproductor", "mostrar los botones", medida)

    faltan = []
    visibles = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                        for c in app.arbol()).lower()
    for etiqueta, quien in BOTONES_REPRODUCTOR:
        if etiqueta.lower() not in visibles:
            faltan.append(quien)
    if faltan:
        res.fallo("reproductor: no aparecen " + ", ".join(faltan))
        return

    bateria_reproductor(app, res, "reproductor")

    orden = recorrer_tab(app, res, "reproductor", vueltas=12)
    res.nota("reproductor, orden de Tab, %d paradas: %s"
             % (len(orden), " > ".join(orden)))

    # Dejarlo como estaba: el banco no puede cambiarle la ventana al dueño. La
    # visibilidad de los botones se guarda en `config.ini`, así que sin esto
    # cada corrida le deja la aplicación distinta de como la encontró.
    if not estaban_visibles:
        app.pedir("pulsar", nombre="AlternarBotonesReproductor")


def escenario_musica(app: Aplicacion, args, res: Resultado):
    """La ventana de música, abierta por sus dos entradas del menú.

    Sin carpeta ningún control queda deshabilitado: «Cambiar carpeta» solo
    se apaga mientras carga y `_al_biblioteca` lo vuelve a habilitar, así
    que los ocho entran en el orden de Tab. No se pulsa Reproducir ni
    ningún atajo de reproducción, y si la configuración trae una carpeta de
    música real no se toca: la ventana solo se abre, se audita y se cierra.
    """
    res.nota("Música: no se reproduce nada, la ventana solo se audita")
    esperados = ("Colecciones", "Buscar en la música", "Mostrar filtros",
                  "Canciones", "Mostrar cola", "Abrir enlace", "Nueva lista",
                 "Cambiar carpeta", "Cerrar")
    auditar_dialogo(
        app, res, "Elegir música…", "Música",
        vueltas_tab=14,
        esperados=esperados,
        esperados_en_tab=esperados)


def escenario_musica_real(app: Aplicacion, args, res: Resultado):
    """Música real de punta a punta, con archivos y sonido de verdad.

    Prepara una carpeta temporal con 5 temas de la música del usuario más
    un tono corto generado, respalda la configuración y las listas, fija
    volumen 40 y corre cada comando de música comprobando con el medidor
    de sonido de Windows que de verdad empieza, se pausa, sigue y se
    detiene. Al terminar deja los datos del usuario exactamente como
    estaban. Usa `tecla_en` y `menu_contextual` para disparar las acciones
    de la ventana nueva por su cableado real, filtra por el buscador, que
    deja el tema aislado seleccionado, y elige lo demás por posición por
    defecto.
    Corre ANTES de lanzar la aplicación compartida (como `arranque_frio`),
    porque la configuración se escribe antes de arrancar.
    """
    rec = RecorridoMusica(app, args, res)
    elegidos = preparar_origen(rec)
    if elegidos is None:
        return
    try:
        preparar_datos(rec, elegidos)
        etapa_a(rec)
        etapa_b(rec)
        etapa_c(rec)
        etapa_d(rec)
        etapa_e(rec)
        etapa_f(rec)
        etapa_f2(rec)
        etapa_g(rec)
        etapa_h(rec)
        etapa_i(rec)
        etapa_j(rec)
        etapa_k(rec)
        etapa_l(rec)
        etapa_m(rec)
        etapa_n(rec)
    except _Corte:
        pass
    except Exception as exc:
        res.fallo(f"musica_real: el recorrido reventó: {exc!r}")
    finally:
        restaurar(rec)


# Vídeo grabado para `reproductor_en_marcha`, que se pasa con `--url-vod`.
VOD_YOUTUBE = "https://www.youtube.com/watch?v=j906Pf7n7Sg"


def esperar_reproductor(app: Aplicacion, condicion, segundos: float):
    """Sondea el estado del reproductor hasta que `condicion` se cumpla.

    Devuelve el último estado y si se cumplió. Espera hechos, no relojes.
    """
    ultimo: dict = {}
    limite = time.time() + segundos
    while True:
        try:
            ultimo = app.reproductor() or {}
        except Exception:
            ultimo = {}
        if ultimo and condicion(ultimo):
            return ultimo, True
        if time.time() >= limite:
            return ultimo, False
        time.sleep(0.25)


def _en_marcha_teclas(app: Aplicacion, res: Resultado, donde: str,
                      *pasos) -> bool:
    """Pasa las teclas, y si la ventana no está al frente no juzga nada."""
    try:
        app.teclas(*pasos)
    except VentanaNoActiva as exc:
        res.no_probado(f"{donde}: no se pudo probar, {exc}")
        return False
    return True


def _en_marcha_salto(app: Aplicacion, res: Resultado, donde: str, p0: int,
                     delta_ms: int, dur_ms: int, espera: float = 30.0):
    """Juzga un salto ya pulsado: destino, tolerancia y que siga avanzando.

    Devuelve la posición final, o None si no pasó.
    """
    destino = p0 + delta_ms
    if dur_ms > 0:
        destino = min(max(destino, 0), dur_ms)
    else:
        destino = max(destino, 0)
    t0 = time.time()

    def _cerca(e):
        pos = e.get("pos_ms") or 0
        return (e.get("estado") == "playing"
                and destino - 5000 <= pos <= destino + 20000)

    estado, ok = esperar_reproductor(app, _cerca, espera)
    pos = (estado.get("pos_ms") or 0) if estado else 0
    if not ok:
        res.fallo(f"{donde}: desde {p0 / 1000:.1f} s no quedó cerca de "
                  f"{destino / 1000:.1f} s en {espera:.0f} s; está en "
                  f"{pos / 1000:.1f} s con estado {estado.get('estado')!r}")
        return None
    time.sleep(3.0)
    pos2 = app.reproductor().get("pos_ms") or 0
    if pos2 <= pos:
        res.fallo(f"{donde}: quedó en {pos / 1000:.1f} s pero no avanza desde "
                  f"ahí ({pos2 / 1000:.1f} s 3 s después)")
        return None
    res.nota(f"{donde}: de {p0 / 1000:.1f} s a {pos / 1000:.1f} s "
             f"(destino {destino / 1000:.1f} s) en {time.time() - t0:.1f} s, "
             f"y sigue a {pos2 / 1000:.1f} s")
    return pos2


def _en_marcha_grabado(app: Aplicacion, args, res: Resultado) -> None:
    """Saltos y pausa en un vídeo grabado, con los atajos de verdad."""
    url = getattr(args, "url_vod", None) or VOD_YOUTUBE
    res.nota(f"reproductor en marcha (grabado): {url}")
    n = len(app.anuncios)
    if not conectar_de_verdad(app, res, url, "reproductor en marcha"):
        return
    if not app.esperar_dicho("reproduciendo", segundos=60, desde=n):
        res.fallo("reproductor en marcha: no se oyó «Reproduciendo» en 60 s")
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "playing", 60.0)
    if not ok:
        res.fallo("reproductor en marcha: no llegó a «playing» en 60 s; "
                  f"estado {estado.get('estado')!r}")
        return
    pa = estado.get("pos_ms") or 0
    time.sleep(2.0)
    pb = app.reproductor().get("pos_ms") or 0
    if pb <= pa:
        res.fallo("reproductor en marcha: en «playing» la posición no avanza "
                  f"({pa / 1000:.1f} s y {pb / 1000:.1f} s)")
        return
    res.nota(f"reproductor en marcha: reproduce desde {pa / 1000:.1f} s "
             f"y avanza a {pb / 1000:.1f} s en 2 s")

    # Dos avances seguidos, sin espera entre ellos, como hace cualquiera
    # cuando el primero no contestó.
    p0 = app.reproductor().get("pos_ms") or 0
    dur = app.reproductor().get("dur_ms") or 0
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    _en_marcha_salto(app, res, "reproductor en marcha, salto +2 min",
                     p0, 120000, dur)

    p1 = app.reproductor().get("pos_ms") or 0
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("left", ["ctrl"])):
        return
    _en_marcha_salto(app, res, "reproductor en marcha, salto -1 min",
                     p1, -60000, dur)

    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("p", ["ctrl"])):
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "paused", 5.0)
    if not ok:
        res.fallo("reproductor en marcha: no entró en pausa en 5 s; "
                  f"estado {estado.get('estado')!r}")
        return
    pa = estado.get("pos_ms") or 0
    time.sleep(2.0)
    pb = app.reproductor().get("pos_ms") or 0
    if abs(pb - pa) > 1000:
        res.fallo(f"reproductor en marcha: en pausa se movió de "
                  f"{pa / 1000:.1f} s a {pb / 1000:.1f} s en 2 s")
        return
    res.nota(f"reproductor en marcha: en pausa queda en {pa / 1000:.1f} s "
             f"y no se mueve")

    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("right", ["ctrl"])):
        return
    if not _en_marcha_teclas(app, res, "reproductor en marcha",
                             ("p", ["ctrl"])):
        return
    destino = pa + 60000

    def _reanudado(e):
        pos = e.get("pos_ms") or 0
        return (e.get("estado") == "playing"
                and destino - 5000 <= pos <= destino + 20000)

    estado, ok = esperar_reproductor(app, _reanudado, 30.0)
    pos = (estado.get("pos_ms") or 0) if estado else 0
    if not ok:
        res.fallo(f"reproductor en marcha: tras saltar en pausa desde "
                  f"{pa / 1000:.1f} s no reanudó cerca de "
                  f"{destino / 1000:.1f} s en 30 s; está en "
                  f"{pos / 1000:.1f} s con estado {estado.get('estado')!r}")
    else:
        res.nota(f"reproductor en marcha: salto en pausa y reanudado en "
                 f"{pos / 1000:.1f} s (destino {destino / 1000:.1f} s)")


def _en_marcha_directo(app: Aplicacion, args, res: Resultado) -> None:
    """Retroceso por relevo y vuelta al borde en un directo real."""
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"reproductor en marcha (directo): {url}")
    n = len(app.anuncios)
    if not conectar_de_verdad(app, res, url, "reproductor en marcha "
                                             "(directo)"):
        return
    if not app.esperar_dicho("reproduciendo", segundos=60, desde=n):
        res.fallo("reproductor en marcha (directo): no se oyó "
                  "«Reproduciendo» en 60 s")
        return
    estado, ok = esperar_reproductor(
        app, lambda e: e.get("estado") == "playing", 60.0)
    if not ok:
        res.fallo("reproductor en marcha (directo): no llegó a «playing» "
                  f"en 60 s; estado {estado.get('estado')!r}")
        return
    res.nota("reproductor en marcha (directo): reproduce el directo")

    # Tres flechas seguidas en el deslizador: cada una son 10 s, o sea dos
    # segmentos de 5 s, así que el desfase esperado es 6.
    ventana_corta = False
    try:
        app.pedir("foco", nombre="Posición de reproducción")
    except OrdenRechazada as exc:
        res.fallo("reproductor en marcha (directo): no se llega a la "
                  f"posición, {exc}")
    else:
        n = len(app.anuncios)
        for _ in range(3):
            if not _en_marcha_teclas(app, res,
                                     "reproductor en marcha (directo)",
                                     "left"):
                return
        if app.esperar_dicho("no se puede retroceder más", segundos=5,
                             desde=n):
            res.nota("reproductor en marcha (directo): YouTube da una "
                     "ventana corta de 30 s y no deja retroceder; se sigue "
                     "con la vuelta al directo")
            ventana_corta = True
        else:
            t0 = time.time()

            def _atras(e):
                return (e.get("desfase") == 6
                        and e.get("estado") == "playing")

            estado, ok = esperar_reproductor(app, _atras, 20.0)
            if not ok:
                res.fallo("reproductor en marcha (directo): tras tres "
                          "flechas el desfase no llegó a 6 en 20 s; "
                          f"desfase {(estado.get('desfase') if estado else '?')}, "
                          f"estado {(estado.get('estado') if estado else '?')!r}")
            else:
                res.nota("reproductor en marcha (directo): tres flechas "
                         f"dejan el desfase en 6 en {time.time() - t0:.1f} s")

    if not ventana_corta:
        n = len(app.anuncios)
        if not _en_marcha_teclas(app, res, "reproductor en marcha (directo)",
                                 ("end", ["ctrl"])):
            return
        app.esperar_dicho("en el directo", segundos=8, desde=n)
        t0 = time.time()

        def _al_borde(e):
            return e.get("desfase") == 0 and e.get("estado") == "playing"

        estado, ok = esperar_reproductor(app, _al_borde, 20.0)
        junto = " ".join(a.get("texto", "") for a in app.anuncios[n:]).lower()
        dijo_borde = ("en el directo" in junto
                      and "ya estás en el directo" not in junto)
        if not dijo_borde or not ok:
            res.fallo("reproductor en marcha (directo): Ctrl+Fin no volvió "
                      f"al borde en 20 s; dijo «{junto[:80]}», desfase "
                      f"{(estado.get('desfase') if estado else '?')}, estado "
                      f"{(estado.get('estado') if estado else '?')!r}")
        else:
            res.nota("reproductor en marcha (directo): Ctrl+Fin dice «En el "
                     f"directo» y el desfase vuelve a 0 en "
                     f"{time.time() - t0:.1f} s")

    n = len(app.anuncios)
    if not _en_marcha_teclas(app, res, "reproductor en marcha (directo)",
                             ("end", ["ctrl"])):
        return
    if app.esperar_dicho("ya estás en el directo", segundos=8, desde=n):
        res.nota("reproductor en marcha (directo): Ctrl+Fin en el borde "
                 "dice «Ya estás en el directo»")
    else:
        junto = " ".join(a.get("texto", "") for a in app.anuncios[n:])
        res.fallo("reproductor en marcha (directo): Ctrl+Fin en el borde no "
                  f"avisó; dijo «{junto[:80]}»")


def escenario_reproductor_en_marcha(app: Aplicacion, args, res: Resultado):
    """El reproductor en marcha: saltos, pausa y vuelta al directo, de verdad.

    El banco nunca lo probaba: ningún escenario comprobaba que después de un
    salto el vídeo siga desde el destino, ni la pausa, ni volver al directo.
    Acá se pulsan los atajos de verdad contra un vídeo grabado y un directo
    reales, y se juzga la posición que la aplicación le da al usuario, no
    solo lo que anuncia. La segunda parte corre aunque la primera falle.
    """
    _en_marcha_grabado(app, args, res)
    app.llamar("set_conectado", False)
    _en_marcha_directo(app, args, res)
    app.llamar("set_conectado", False)

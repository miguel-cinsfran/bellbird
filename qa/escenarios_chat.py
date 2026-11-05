"""Escenarios de chat, captura, comentarios y atajos de captura."""

from __future__ import annotations

import time

from banco_app import (
    Aplicacion, DIRECTO_YOUTUBE, Resultado, _candidatas_uia,
    _cerrar_nativo, _textos_de, conectar_de_verdad, dialogo_nativo, subarbol,
)
from banco_auditoria import recorrer_tab, revisar_nombres
from escenarios_musica import bateria_reproductor

def lista_del_chat(controles):
    """La lista donde aterrizan los mensajes. Primero por nombre, si no la
    primera lista con contenido que aparezca."""
    for c in controles:
        if c["clase"] in ("ListBox", "ListCtrl") and "items" in c:
            nombre = ((c.get("nombre") or "") + (c.get("etiqueta") or "")).lower()
            if "chat" in nombre:
                return c
    for c in controles:
        if c["clase"] == "ListBox" and "items" in c:
            return c
    return None




def escenario_chat(app: Aplicacion, args, res: Resultado):
    """Una sesión de YouTube con mensajes, sin tocar la red.

    Se monta con la misma API pública que usa `main.py` desde el hilo de
    captura. Así se prueba la parte conectada de la interfaz sin depender de
    que haya un directo vivo ni de que la red se porte bien.
    """
    app.pedir("frente")

    # Este escenario mide el PASO de desconectado a conectado, asi que si llega
    # con la aplicacion ya conectada no falla por un defecto suyo: falla porque
    # otro escenario dejo puesta una sesion simulada. Se dice asi, con el
    # nombre del culpable a la vista, porque el 26/08/2026 el mismo fallo se
    # leyo como «conectar no anuncia nada» y se busco durante un rato en el
    # sitio equivocado.
    conectado_ya = any(
        i["habilitado"] for i in app.menus()
        if not i.get("submenu")
        and "desconectar" in (i.get("camino") or "").lower())
    if conectado_ya:
        res.fallo("chat: llegue con la aplicacion YA conectada. No es un "
                  "defecto de la aplicacion: algun escenario anterior simulo "
                  "una sesion y no llamo a `restaurar_desconectado`")
        return

    apagados_antes = len([i for i in app.menus()
                          if not i.get("submenu") and not i["habilitado"]])

    n = len(app.anuncios)
    app.simular_sesion_youtube(titulo="Directo de prueba QA", espectadores=137)
    if app.esperar_dicho("conectado", segundos=10, desde=n):
        res.nota("chat: conectar se anuncia")
    else:
        res.fallo("chat: conectar no anunció nada")

    apagados = [i["camino"] for i in app.menus()
                if not i.get("submenu") and not i["habilitado"]]
    res.nota(f"al conectar, los ítems apagados bajan de {apagados_antes} "
             f"a {len(apagados)}")
    if len(apagados) >= apagados_antes:
        res.fallo("chat: conectar no habilitó ningún ítem de menú")
    if apagados:
        res.nota("  siguen apagados: " + ", ".join(apagados))

    muestras = [
        ("Ana", "hola que tal el directo", "text", ""),
        ("Beto", "gracias por todo", "superchat", "5,00 US$"),
        ("Cora", "me hice miembro", "member", ""),
        ("Dani", "un sticker", "sticker", "2,00 US$"),
    ]
    for autor, texto, tipo, monto in muestras:
        app.mensaje(autor, texto, tipo=tipo, monto=monto)

    # El chat se vuelca agrupado, así que se espera a que aparezca en la lista
    # en vez de dar por hecho que ya está.
    limite = time.time() + 12
    lista = None
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and len(lista.get("items", [])) >= len(muestras):
            break
        time.sleep(0.3)

    if not lista:
        res.fallo("chat: no encontré la lista del chat")
        return
    items = lista.get("items", [])
    res.nota(f"chat: la lista tiene {len(items)} entradas tras enviar "
             f"{len(muestras)}")
    if len(items) < len(muestras):
        res.fallo(f"chat: se enviaron {len(muestras)} mensajes y llegaron "
                  f"{len(items)}")
    texto_junto = " ".join(str(i) for i in items).lower()
    for autor, _, _, _ in muestras:
        if autor.lower() not in texto_junto:
            res.fallo(f"chat: «{autor}» no aparece en la lista")
    for entrada in items[:4]:
        res.nota("  lee: " + str(entrada)[:70])

    # El monto del super chat tiene que verse: es el motivo de la función.
    if "5,00" not in texto_junto and "5.00" not in texto_junto:
        res.fallo("chat: el monto del super chat no aparece en la lista")

    orden = recorrer_tab(app, res, "principal conectada", vueltas=16)
    res.nota(f"conectado, Tab da {len(orden)} paradas: "
             + " > ".join(orden))


def escenario_tiktok(app: Aplicacion, args, res: Resultado):
    """La ruta de TikTok, que es distinta y comparte la misma lista."""
    app.pedir("frente")
    n = len(app.anuncios)
    app.simular_sesion_tiktok(usuario="rolon_100")
    if not app.esperar_dicho("conectado", segundos=10, desde=n):
        res.nota("tiktok: no anunció «conectado», puede usar otra frase")

    for autor, texto, tipo in (("Eva", "hola desde tiktok", "text"),
                               ("Fito", "entra al directo", "entrada")):
        app.mensaje(autor, texto, tipo=tipo)

    limite = time.time() + 12
    lista = None
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(0.3)
    if not lista or not lista.get("items"):
        res.fallo("tiktok: no llegó ningún mensaje a la lista")
        return
    res.nota(f"tiktok: {len(lista.get('items'))} entradas en la lista")

    # «Descargar este vídeo» va apagado en TikTok, por diseño.
    item = [i for i in app.menus() if "Descargar este" in i["camino"]]
    if item and item[0]["habilitado"]:
        res.fallo("tiktok: «Descargar este vídeo» quedó habilitado, y el "
                  "diseño dice que en TikTok va apagado")
    elif item:
        res.nota("tiktok: «Descargar este vídeo» correctamente apagado")

    app.restaurar_desconectado()


def escenario_comentarios(app: Aplicacion, args, res: Resultado):
    """El panel de comentarios, que hasta el 26/08/2026 no entraba en el banco.

    Va sin red a propósito: traer comentarios de verdad necesita clave de API y
    sesión iniciada, y eso ya lo cubren las pruebas de `youtube_api`. Lo que
    solo se puede comprobar con la aplicación viva es otra cosa: que los
    controles tengan nombre, que Tab los alcance, y que la lista diga algo
    cuando se pulsa sobre nada.
    """
    app.pedir("frente")

    respuesta = app.pedir("pestanas")
    if not respuesta.get("ok"):
        res.fallo("comentarios: no se pudieron listar las pestañas, "
                  + str(respuesta.get("error", "sin motivo")))
        return
    paginas = respuesta.get("datos", {}).get("paginas", [])
    if "Comentarios" not in paginas:
        res.fallo("comentarios: no hay ninguna pestaña «Comentarios»; hay "
                  + ", ".join(paginas))
        return
    pagina = paginas.index("Comentarios")
    app.pedir("pestanas", indice=pagina)

    visibles = _panel_comentarios(app)
    revisar_nombres(visibles, res, "comentarios")

    lista = _lista_de_comentarios(visibles)
    if lista is None:
        res.fallo("comentarios: no encontré la lista del panel")
        return
    res.nota("comentarios: la lista arranca con %d entradas"
             % len(lista.get("items", [])))

    # «Cargar más» sin ninguna página cargada tiene que estar apagado: si
    # figura encendido, invita a pulsar algo que no puede hacer nada.
    botones = {(c.get("etiqueta") or "").replace("&", ""): c
               for c in visibles if c["clase"] == "Button"}
    mas = botones.get("Cargar más")
    if mas is None:
        res.fallo("comentarios: no está el botón «Cargar más»")
    elif mas["habilitado"]:
        res.fallo("comentarios: «Cargar más» está habilitado sin ninguna "
                  "página cargada")
    else:
        res.nota("comentarios: «Cargar más» correctamente apagado al empezar")

    # Este otro depende de que haya sesión iniciada, que no está en manos del
    # banco. Se anota lo que se encontró, sin juzgarlo.
    comentar = next((c for clave, c in botones.items()
                       if clave.startswith("Comentar en el vídeo")), None)
    if comentar is None:
        res.fallo("comentarios: no está el botón «Comentar en el vídeo»")
    else:
        res.nota("comentarios: «Comentar en el vídeo» "
                 + ("habilitado, hay sesión" if comentar["habilitado"]
                    else "apagado, no hay sesión iniciada"))

    # Tab hay que empezarlo DENTRO de la pagina: desde el marco no recorre
    # nada, igual que en la ventana principal.
    app.pedir("foco", nombre="Lista de comentarios")
    orden = recorrer_tab(app, res, "comentarios", vueltas=12)
    res.nota("comentarios, orden de Tab, %d paradas: %s"
             % (len(orden), " > ".join(orden)))

    # Enter sobre la lista vacía tiene que decir algo. Callarse es lo peor que
    # puede hacer: quien no ve la pantalla no sabe si la tecla llegó.
    app.pedir("foco", nombre="Lista de comentarios")
    n = len(app.anuncios)
    app.teclas("return")
    if app.esperar_dicho("sin comentario", segundos=5, desde=n):
        res.nota("comentarios: Enter sin selección avisa en vez de callarse")
    else:
        res.fallo("comentarios: Enter sobre la lista vacía no anunció nada")

    # El aviso de TikTok es la única entrada que el panel muestra sin red, y
    # existe para que la pestaña vacía no parezca una avería. Esto deja la
    # aplicación en sesión de TikTok, así que el escenario va justo antes de
    # `tiktok` en la corrida completa.
    app.simular_sesion_tiktok()
    app.pedir("pestanas", indice=pagina)
    items = []
    limite = time.time() + 8
    while time.time() < limite:
        actual = _lista_de_comentarios(subarbol(app.arbol(), "PanelComentarios"))
        items = actual.get("items", []) if actual else []
        if items:
            break
        time.sleep(0.3)
    if any("tiktok" in i.lower() for i in items):
        res.nota("comentarios: en TikTok la lista explica por qué está vacía")
    else:
        res.fallo("comentarios: en TikTok la lista no explica por qué está "
                  "vacía; dice %r" % (items,))


def _lista_de_comentarios(controles: list[dict]) -> dict | None:
    for c in controles:
        if (c["clase"] == "ListBox"
                and "comentario" in (c.get("nombre") or "").lower()):
            return c
    return None


def _panel_comentarios(app: Aplicacion, segundos: float = 8.0) -> list[dict]:
    """Espera a que el panel este construido y devuelve solo sus controles."""
    limite = time.time() + segundos
    rama: list[dict] = []
    while time.time() < limite:
        rama = subarbol(app.arbol(), "PanelComentarios")
        if _lista_de_comentarios(rama) is not None:
            return rama
        time.sleep(0.3)
    return rama
DIRECTO_TIKTOK = "https://www.tiktok.com/@rolon_100/live"


def escenario_directo_youtube(app: Aplicacion, args, res: Resultado):
    """Un directo de YouTube de verdad, con la red de por medio."""
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"youtube en vivo: {url}")
    if not conectar_de_verdad(app, res, url, "youtube en vivo"):
        return

    # El título y los espectadores los rellena el hilo de captura, no la GUI:
    # que aparezcan prueba que el cableado entero funciona.
    limite = time.time() + 45
    titulo = ""
    while time.time() < limite:
        for c in app.arbol():
            texto = (c.get("etiqueta") or "").strip()
            if c["clase"] == "StaticText" and len(texto) > 12:
                titulo = texto
        if titulo:
            break
        time.sleep(1.0)
    if titulo:
        res.nota(f"youtube en vivo: la ventana muestra «{titulo[:70]}»")
    else:
        res.fallo("youtube en vivo: conectó pero no apareció ningún texto "
                  "largo en la ventana, o sea ni título ni estado")

    lista = None
    limite = time.time() + 90
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(2.0)
    if lista and lista.get("items"):
        items = lista["items"]
        res.nota(f"youtube en vivo: llegaron {len(items)} mensajes reales")
        for i in items[:3]:
            res.nota("  lee: " + str(i)[:80])
    else:
        res.nota("youtube en vivo: conectó pero no llegó ningún mensaje en "
                 "90 s. Puede ser un chat tranquilo, no es defecto por sí solo")

    # Y ahora lo que ningún escenario había hecho nunca: el reproductor con
    # vídeo de verdad cargado. Hasta el 21/08/2026 la batería solo se había
    # corrido sin nada cargado, que es el caso fácil: con medio real entran en
    # juego la red, el buffer y lo que tarda VLC en responder, y ahí es donde
    # viviría la torpeza de la que se queja quien la usa.
    #
    # Se espera a que termine de cargar antes de medir: juzgar la latencia
    # mientras yt-dlp todavía resuelve la URL mide la red, no la aplicación.
    if app.esperar_dicho("reproduciendo", segundos=60):
        res.nota("youtube en vivo: el reproductor arrancó")
    else:
        res.nota("youtube en vivo: no se oyó «Reproduciendo» en 60 s; se mide "
                 "igual, pero puede que no haya llegado a cargar")
    time.sleep(3.0)

    visibles = " ".join(((c.get("etiqueta") or "") + " " + (c.get("nombre") or ""))
                        for c in app.arbol()).lower()
    if "retroceder 1 min" not in visibles:
        app.pedir("pulsar", nombre="AlternarBotonesReproductor")
    bateria_reproductor(app, res, "youtube en vivo", hay_medio=True)

    app.llamar("set_conectado", False)


def escenario_directo_tiktok(app: Aplicacion, args, res: Resultado):
    """Un directo de TikTok de verdad. Ruta distinta y más frágil."""
    url = getattr(args, "url_tiktok", None) or DIRECTO_TIKTOK
    res.nota(f"tiktok en vivo: {url}")
    if not conectar_de_verdad(app, res, url, "tiktok en vivo", espera=75.0):
        return
    lista = None
    limite = time.time() + 60
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(2.0)
    if lista and lista.get("items"):
        res.nota(f"tiktok en vivo: llegaron {len(lista['items'])} eventos")
    else:
        res.nota("tiktok en vivo: conectó pero no llegó nada en 60 s")
    app.llamar("set_conectado", False)


def _hilos_de_captura(app: Aplicacion) -> list:
    """Los hilos de captura de chat vivos, por nombre."""
    vivos = app.hilos()
    return [h for h in vivos if h in ("Chat", "TikTok")]


def escenario_dos_conexiones(app: Aplicacion, args, res: Resultado):
    """Conectar dos veces sin desconectar no deja el hilo viejo girando.

    El 21/08/2026 los registros de un usuario real mostraron diez hilos `Chat`
    arrancados y nueve terminados: al conectar a otro vídeo, el anterior se
    quedaba pidiendo el chat para siempre porque nadie ponía su evento de
    parada. Esto lo comprueba con la aplicación de verdad, que es donde se vio.

    El camino por el que pasa de verdad, leído en `gui.py:872` el 21/08/2026:
    el botón alterna, así que estando conectado no se puede conectar otra vez.
    Pero un error de red hace `set_conectado(False)` y rehabilita el botón
    MIENTRAS el hilo de captura sigue vivo reintentando, y ahí una pulsación
    abre la segunda sesión. Por eso el escenario llama a `set_conectado(False)`
    en medio: es exactamente lo que la aplicación se hace a sí misma cuando
    pytchat pierde la conexión, y lo que le pasó al usuario a las 12:23 y a las
    12:30.

    Vale con conectar dos veces al MISMO directo: la conexión no compara el
    vídeo, abre una sesión nueva igual.
    """
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"dos conexiones: {url}")

    if not conectar_de_verdad(app, res, url, "dos conexiones (primera)"):
        return
    # Esperar a que el hilo de captura exista de verdad antes de medir: si se
    # mide antes de que arranque, el conteo da cero y el escenario pasa sin
    # haber probado nada.
    limite = time.time() + 30
    while time.time() < limite and not _hilos_de_captura(app):
        time.sleep(0.5)
    primeros = _hilos_de_captura(app)
    if not primeros:
        res.fallo("dos conexiones: la primera no llegó a arrancar ningún hilo "
                  "de captura en 30 s; sin eso no se puede medir nada")
        return
    res.nota(f"dos conexiones: tras la primera hay {len(primeros)} "
             f"({', '.join(primeros)})")

    # Lo que hace la aplicación sola al perder la conexión: apaga la interfaz
    # y deja el hilo reintentando. No mata nada.
    app.llamar("set_conectado", False)
    time.sleep(1.0)
    if not conectar_de_verdad(app, res, url, "dos conexiones (segunda)"):
        return
    # El hilo viejo puede tardar en morir: está dentro de una lectura de red y
    # no ve la parada hasta que vuelve. Se le da margen y se toma el mínimo,
    # porque un solape de un segundo es correcto y quedarse pegado no lo es.
    limite = time.time() + 45
    minimo = 99
    while time.time() < limite:
        minimo = min(minimo, len(_hilos_de_captura(app)))
        if minimo <= 1:
            break
        time.sleep(1.0)

    if minimo <= 1:
        res.nota(f"dos conexiones: el hilo de la primera murió, quedó {minimo}")
    else:
        vivos = _hilos_de_captura(app)
        res.fallo(f"dos conexiones: quedaron {minimo} hilos de captura vivos "
                  f"tras 45 s ({', '.join(vivos)}); el de la sesión vieja no "
                  f"se paró y va a seguir pidiendo el chat hasta que se cierre "
                  f"la aplicación")
    app.llamar("set_conectado", False)


def escenario_conectar(app: Aplicacion, args, res: Resultado):
    """El boton Conectar, que en una corrida rutinaria no se pulsaba nunca.

    Lo pulsaban solo los tres escenarios de directo vivo, que estan fuera de
    `todos`, asi que sus dos caminos de error no los habia visto nadie. Este no
    toca la red: se queda en los dos casos que fallan antes de salir a buscar
    nada.
    """
    app.pedir("frente")

    # 1. Sin URL. Sale un cuadro nativo, no un anuncio: NVDA lo lee al recibir
    # el foco, pero si el cuadro no expone texto no hay nada que leer.
    app.llamar("set_url", "")
    try:
        app.pedir("pulsar", nombre="Conectar", tiempo=3.0, responder_ya=True)
    except Exception:
        pass                      # el cuadro es modal y se come la respuesta
    dlg = dialogo_nativo("Falta el enlace", segundos=8)
    if dlg is None:
        res.fallo("conectar: con la URL vacia no aparecio ningun aviso")
    else:
        textos = _textos_de(dlg)
        res.nota("conectar sin URL abre «Falta el enlace» con %d textos" % len(textos))
        for x in textos[:2]:
            res.nota("  dice: " + x[:70])
        if not textos:
            res.fallo("conectar: el aviso de URL vacia no expone ningun texto, "
                      "asi que un lector de pantalla no tiene que leer")
        _cerrar_nativo(dlg)

    # 2. URL que no es de YouTube ni de TikTok.
    app.llamar("set_url", "esto no es una direccion")
    n = len(app.anuncios)
    try:
        app.pedir("pulsar", nombre="Conectar", tiempo=3.0, responder_ya=True)
    except Exception:
        pass
    dlg = dialogo_nativo("Enlace", segundos=6) or dialogo_nativo("no reconocido", segundos=2)
    if dlg is not None:
        res.nota("conectar con una URL invalida abre un aviso nativo")
        _cerrar_nativo(dlg)
    elif app.dijo("no se reconoce", desde=n):
        res.nota("conectar con una URL invalida se anuncia con voz")
    else:
        res.fallo("conectar: una URL invalida no produjo ni aviso ni anuncio")

    app.llamar("set_url", "")


def escenario_directo_sin_imagen(app: Aplicacion, args, res: Resultado):
    """La pregunta de directo al aire sin imagen, que es un cuadro nativo.

    El diálogo es un `wx.MessageDialog`, invisible para la sonda: se lo
    busca desde fuera con `dialogo_nativo` y se pulsa «Dejarlo en curso»
    por UI Automation, la respuesta segura. Nunca se pulsa
    «Finalizar directo». Escape no sirve acá: el cuadro no tiene Cancelar
    y Windows no lo cierra.
    """
    app.pedir("frente")
    n = len(app.anuncios)
    try:
        app.pedir("directo_sin_imagen", tiempo=6.0)
    except Exception:
        pass                      # el cuadro es modal y se come la respuesta
    dlg = dialogo_nativo("Directo sin imagen", segundos=8)
    if dlg is None:
        res.fallo("directo sin imagen: no apareció la pregunta "
                  "«Directo sin imagen»")
        return
    textos = _textos_de(dlg)
    res.nota("directo sin imagen abre «Directo sin imagen» con %d textos"
             % len(textos))
    for x in textos[:2]:
        res.nota("  dice: " + x[:70])
    if not textos:
        res.fallo("directo sin imagen: la pregunta no expone ningún texto, "
                  "así que un lector de pantalla no tiene qué leer")
        if not _pulsar_dejarlo_en_curso(dlg):
            res.fallo("directo sin imagen: no apareció el botón "
                      "«Dejarlo en curso» para cerrar la pregunta")
            _cerrar_nativo(dlg)
        return
    if not any("prueba del banco" in (x or "").lower() for x in textos):
        res.fallo("directo sin imagen: la pregunta no nombra el directo "
                  "de prueba")
    botones = []
    try:
        for d in dlg.descendants():
            try:
                if d.element_info.control_type == "Button":
                    nombre = (d.element_info.name or "").strip()
                    if nombre:
                        botones.append(nombre)
            except Exception:
                continue
    except Exception:
        pass
    juntos = " ".join(textos + botones).lower()
    res.nota("directo sin imagen ofrece «Finalizar directo»: %s, "
             "«Dejarlo en curso»: %s"
             % ("sí" if "finalizar directo" in juntos else "no",
                "sí" if "dejarlo en curso" in juntos else "no"))
    if not _pulsar_dejarlo_en_curso(dlg):
        res.fallo("directo sin imagen: no apareció el botón «Dejarlo en curso»")
        _cerrar_nativo(dlg)
        if dialogo_nativo("Directo sin imagen", segundos=1.0) is not None:
            res.fallo("directo sin imagen: la pregunta sigue abierta y no se "
                      "pudo cerrar")
        return
    limite = time.time() + 5.0
    cerrado = False
    while time.time() < limite:
        if dialogo_nativo("Directo sin imagen", segundos=1.0) is None:
            cerrado = True
            break
    if not cerrado:
        res.fallo("directo sin imagen: «Dejarlo en curso» no cerró la pregunta")
        _pulsar_dejarlo_en_curso_por_coordenadas(dlg)
        if dialogo_nativo("Directo sin imagen", segundos=1.0) is not None:
            res.fallo("directo sin imagen: la pregunta sigue abierta y no hay "
                      "forma de cerrarla sin arrastrar a los demás escenarios")
            return
    if app.esperar_dicho("El directo sigue en curso", segundos=5.0, desde=n):
        res.nota("directo sin imagen con «Dejarlo en curso» anuncia que sigue "
                 "en curso")
    else:
        res.fallo("directo sin imagen: al dejarlo en curso no se anunció "
                  "«El directo sigue en curso»")


def _boton_dejarlo_en_curso(dlg):
    """El botón «Dejarlo en curso» entre los descendientes. None si no está.

    Se compara sin la marca de mnemónico. NUNCA devuelve el otro botón.
    """
    try:
        for d in dlg.descendants():
            try:
                if d.element_info.control_type != "Button":
                    continue
                nombre = (d.element_info.name or "").replace(
                    "&", "").strip()
            except Exception:
                continue
            if nombre.lower() == "dejarlo en curso":
                return d
    except Exception:
        pass
    return None


def _pulsar_dejarlo_en_curso(dlg) -> bool:
    """Pulsa «Dejarlo en curso» por UI Automation. NUNCA el otro."""
    boton = _boton_dejarlo_en_curso(dlg)
    if boton is None:
        return False
    try:
        if hasattr(boton, "invoke"):
            boton.invoke()
        else:
            boton.click_input()
    except Exception:
        try:
            boton.click_input()
        except Exception:
            return False
    return True


def _pulsar_dejarlo_en_curso_por_coordenadas(dlg) -> bool:
    """Último recurso: el mismo botón, con clic por coordenadas.

    Si ni eso sale, quien llama lo dice y no arrastra el modal abierto a
    los demás escenarios.
    """
    boton = _boton_dejarlo_en_curso(dlg)
    if boton is None:
        return False
    try:
        boton.click_input()
        return True
    except Exception:
        pass
    _cerrar_nativo(dlg)
    return False


def escenario_menu_chat(app: Aplicacion, args, res: Resultado):
    """El menu contextual de la lista del chat, donde vive casi toda la accion.

    Entre siete y nueve entradas segun haya sesion: copiar, copiar todo,
    releer, abrir enlace, silenciar de dos formas, rehabilitar, y con sesion
    expulsar y banear. Nunca se habia abierto en el banco.

    Se abre con la tecla Aplicaciones, que es como llega quien no usa raton.
    """
    app.pedir("frente")
    app.simular_sesion_youtube(titulo="Prueba del menu contextual")
    app.mensaje("Ana", "hola, mira esto https://example.com/algo")

    limite = time.time() + 12
    lista = None
    while time.time() < limite:
        lista = lista_del_chat(app.arbol())
        if lista and lista.get("items"):
            break
        time.sleep(0.3)
    if not lista or not lista.get("items"):
        res.fallo("menu del chat: no llego ningun mensaje a la lista")
        return

    app.pedir("foco", nombre="Chat del directo")
    app.teclas("down")
    time.sleep(0.5)

    # El menu emergente es una ventana nativa: wx no la expone, hay que
    # mirarla desde fuera igual que los cuadros de `wx.MessageBox`.
    try:
        app.teclas("menu")
    except Exception as exc:
        res.nota("menu del chat: la tecla Aplicaciones no se pudo simular, %s" % exc)
        res.fallo("menu del chat: SIN PROBAR, no se pudo abrir")
        return

    entradas = _entradas_de_menu(segundos=8)
    if not entradas:
        res.fallo("menu del chat: la tecla Aplicaciones no abrio ningun menu "
                  "que Windows exponga")
        _escape()
        return

    res.nota("menu del chat: %d entradas" % len(entradas))
    for e in entradas[:9]:
        res.nota("  " + e[:70])

    juntas = " ".join(entradas).lower()
    for esperada in ("copiar", "leer en voz alta", "enlace", "silenciar"):
        if esperada not in juntas:
            res.fallo("menu del chat: no aparece ninguna entrada de «%s»"
                      % esperada)
    sin_nombre = [e for e in entradas if not e.strip()]
    if sin_nombre:
        res.fallo("menu del chat: %d entradas sin texto, mudas para el lector"
                  % len(sin_nombre))
    _escape()


def _entradas_de_menu(segundos: float = 8.0) -> list:
    """Los textos de un menu emergente nativo, mirando desde fuera."""
    try:
        from pywinauto import Desktop
    except ImportError:
        return []
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            for w in _candidatas_uia(Desktop):
                try:
                    if w.element_info.control_type != "Menu":
                        continue
                    textos = []
                    for d in w.descendants():
                        try:
                            if d.element_info.control_type == "MenuItem":
                                textos.append((d.element_info.name or "").strip())
                        except Exception:
                            continue
                    if textos:
                        return textos
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.3)
    return []


def _escape() -> None:
    try:
        from pywinauto import keyboard
        keyboard.send_keys("{ESC}")
    except Exception:
        pass
    time.sleep(0.5)


def escenario_captura_atajo(app: Aplicacion, args, res: Resultado):
    """La pestana Atajos, ahora que la captura ya no abre ninguna ventana.

    Hasta el 26/08/2026 esto pulsaba un boton y esperaba un dialogo «Capturar
    atajo». Ese dialogo se borro: ahora el propio boton entra en modo captura.
    El escenario viejo daba un fallo que parecia de la aplicacion y era del
    banco, y estuvo dos dias en el informe.

    LO QUE ESTE ESCENARIO NO CUBRE, y conviene saberlo: no comprueba que teclas
    de verdad lleguen al boton, porque el simulador de wx escribe en la ventana
    que Windows tenga al frente y el banco trae al frente la ventana PRINCIPAL,
    no el dialogo modal de Preferencias. Esa parte, o sea que Escape cancele,
    que Tab salga y que Alt+Enter se capture en vez de desactivar, la cubren
    las pruebas de `tests/test_atajos_captura.py`, una por rama.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo("atajos: no se pudo abrir Preferencias, %s" % exc)
        return
    if app.esperar_ventana("Preferencias", segundos=15) is None:
        res.fallo("atajos: Preferencias no abrio")
        return

    try:
        respuesta = app.pedir("pestanas", ventana="Preferencias")
        paginas = respuesta.get("datos", {}).get("paginas", [])
        indice = next(i for i, n in enumerate(paginas) if "tajo" in n)
        app.pedir("pestanas", ventana="Preferencias", indice=indice)
        time.sleep(0.8)
    except Exception as exc:
        res.fallo("atajos: no se pudo llegar a la pestana, %s" % exc)
        app.pedir("cerrar_ventana", ventana="Preferencias")
        return

    def boton_de(nombre):
        for c in app.arbol("Preferencias"):
            if (c.get("nombre") or "") == nombre:
                return c
        return None

    # Cada boton dice su atajo en la etiqueta, y eso NO es decoracion: es lo
    # unico que lee un lector de pantalla al recorrer la pestana.
    conectar = boton_de("Atajo_conectar")
    if conectar is None:
        res.fallo("atajos: no encuentro el boton de la accion Conectar")
        app.pedir("cerrar_ventana", ventana="Preferencias")
        return
    etiqueta_inicial = (conectar.get("etiqueta") or "").replace("&", "")
    if ":" not in etiqueta_inicial:
        res.fallo("atajos: el boton se llama «%s» y no dice que atajo tiene"
                  % etiqueta_inicial)
    else:
        res.nota("atajos, el boton dice: " + etiqueta_inicial)

    # Entrar en modo captura tiene que anunciarse Y cambiar la etiqueta. Si
    # solo se anunciara, quien vuelve sobre el control mas tarde no tendria
    # forma de saber que esta esperando una combinacion.
    n = len(app.anuncios)
    # El foco PRIMERO, y no es un adorno: el modo captura se sale al perder el
    # foco, asi que si se entra con un evento sintetico sin foco, el boton
    # nunca lo pierde y la comprobacion de mas abajo da un fallo que parece de
    # la aplicacion. Pasó el 26/08/2026 al escribir este escenario.
    app.pedir("foco", ventana="Preferencias", nombre="Atajo_conectar")
    app.pedir("pulsar", nombre="Atajo_conectar")
    time.sleep(0.5)
    if app.esperar_dicho("combinación", segundos=6, desde=n):
        res.nota("atajos: entrar en captura se anuncia")
    else:
        res.fallo("atajos: pulsar el boton no anuncio nada, asi que nadie sabe "
                  "que la aplicacion esta esperando una combinacion")
    ahora = boton_de("Atajo_conectar")
    texto = (ahora.get("etiqueta") or "").replace("&", "") if ahora else ""
    if "combinación" not in texto.lower():
        res.fallo("atajos: en modo captura el boton sigue diciendo «%s», asi "
                  "que su estado no se puede leer" % texto)
    else:
        res.nota("atajos, en captura el boton dice: " + texto)

    # Se sale del modo por el mismo camino que usaria alguien que se arrepiente
    # sin teclado disponible: mover el foco a otro control.
    app.pedir("foco", ventana="Preferencias", nombre="RestablecerAtajos")
    time.sleep(0.5)
    vuelto = boton_de("Atajo_conectar")
    texto = (vuelto.get("etiqueta") or "").replace("&", "") if vuelto else ""
    if texto != etiqueta_inicial:
        res.fallo("atajos: al perder el foco el boton quedo en «%s» y antes "
                  "decia «%s»" % (texto, etiqueta_inicial))
    else:
        res.nota("atajos: perder el foco devuelve la etiqueta a como estaba")

    restablecer = boton_de("RestablecerAtajos")
    if restablecer is None:
        res.fallo("atajos: no hay boton para restablecer los valores de fabrica")
    elif not restablecer.get("habilitado"):
        res.fallo("atajos: el boton de restablecer esta deshabilitado, asi que "
                  "sale del orden de Tab")
    else:
        n = len(app.anuncios)
        app.pedir("pulsar", nombre="RestablecerAtajos")
        if app.esperar_dicho("restablecid", segundos=6, desde=n):
            res.nota("atajos: restablecer se anuncia")
        else:
            res.fallo("atajos: restablecer no anuncio nada")

    revisar_nombres(subarbol(app.arbol("Preferencias"), "PagAtajos"),
                    res, "atajos")
    app.pedir("cerrar_ventana", ventana="Preferencias")


def escenario_redactar(app: Aplicacion, args, res: Resultado):
    """El cuadro de escritura del chat.

    Lo que se comprueba es el contrato que lo hace usable sin ver: que el
    cuadro y el boton esten SIEMPRE, que el boton diga por que no se puede
    usar, y que activarlo sin poder lo anuncie en vez de callarse.
    """
    app.pedir("frente")

    def controles():
        rama = subarbol(app.arbol(), "PanelRedactar")
        cuadro = next((c for c in rama if c["clase"] == "TextCtrl"), None)
        boton = next((c for c in rama if c["clase"] == "Button"), None)
        return cuadro, boton

    cuadro, boton = controles()
    if cuadro is None or boton is None:
        res.fallo("redactar: no encuentro el cuadro o el boton en el arbol")
        return

    # Sin conectar tienen que seguir estando, y habilitados: deshabilitarlos
    # los sacaria del orden de Tab y el motivo quedaria fuera de alcance.
    for ctrl, comovse in ((cuadro, "el cuadro"), (boton, "el boton")):
        if not ctrl.get("habilitado"):
            res.fallo("redactar: %s esta deshabilitado sin conectar, asi que "
                      "sale del orden de Tab y su motivo no se puede leer"
                      % comovse)
    etiqueta = (boton.get("etiqueta") or "").replace("&", "")
    if "(" not in etiqueta:
        res.fallo("redactar: sin conectar, el boton se llama «%s» y no dice "
                  "por que no se puede usar" % etiqueta)
    else:
        res.nota("redactar, sin conectar el boton se llama: " + etiqueta)

    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Enviar mensaje al chat")
    if app.esperar_dicho("conéctate", segundos=6, desde=n):
        res.nota("redactar: activarlo sin conectar lo anuncia en vez de callarse")
    else:
        res.fallo("redactar: activarlo sin conectar no anuncio nada")

    # Conectado, el motivo desaparece.
    app.simular_sesion_youtube(titulo="Prueba del cuadro")
    time.sleep(1.2)
    _, boton = controles()
    etiqueta = (boton.get("etiqueta") or "").replace("&", "")
    if "(" in etiqueta:
        res.fallo("redactar: conectado, el boton sigue diciendo un motivo: «%s»"
                  % etiqueta)
    else:
        res.nota("redactar, conectado el boton vuelve a llamarse: " + etiqueta)

    # Con el cuadro vacio no se manda nada y se avisa.
    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Enviar mensaje al chat")
    if app.esperar_dicho("escribe un mensaje", segundos=6, desde=n):
        res.nota("redactar: con el cuadro vacio avisa en vez de mandar nada")
    else:
        res.fallo("redactar: con el cuadro vacio no avisa")

    orden = recorrer_tab(app, res, "redactar", vueltas=10)
    res.nota("redactar, orden de Tab: " + " > ".join(orden))
    esperado = ["Chat del directo", "Mensaje para el chat", "Enviar"]
    juntos = " > ".join(orden)
    if not all(x in juntos for x in esperado):
        res.fallo("redactar: el orden de Tab no pasa por lista, cuadro y "
                  "boton; da %s" % juntos)

    # Se deja como se encontro: este escenario necesita el estado SIN conectar
    # para su primera mitad, y el de mas adelante mide el paso de uno al otro.
    app.restaurar_desconectado()
    time.sleep(0.5)


def escenario_enviar_live(app: Aplicacion, args, res: Resultado):
    """Manda un mensaje de verdad al chat de un directo, punta a punta.

    Es el unico que prueba la ruta de ESCRITURA de la API: credenciales, token,
    `liveChatId` y la llamada. Todo lo demas del cuadro se comprueba sin red en
    `redactar`, pero eso no toca la API ni una vez.

    Necesita tres cosas que no dependen del codigo: un directo emitiendo, sesion
    OAuth iniciada y que el directo tenga el chat abierto. Cuando falle, eso es
    lo primero que hay que descartar. Por eso vive fuera de `todos`.

    Manda la palabra «test» y nada mas, en el directo que el dueno eligio para
    esto. No se manda nada que parezca dirigido a nadie.
    """
    url = getattr(args, "url_youtube", None) or DIRECTO_YOUTUBE
    res.nota(f"enviar al chat: {url}")
    if not conectar_de_verdad(app, res, url, "enviar al chat", espera=75.0):
        return

    # El motivo dentro del nombre del boton es el que dice si se puede escribir.
    # Si sigue ahi conectado, no hay sesion o el directo no tiene chat, y eso no
    # es un fallo del cuadro: se dice y se para, en vez de mandar a ciegas.
    boton = None
    limite = time.time() + 30
    while time.time() < limite:
        rama = subarbol(app.arbol(), "PanelRedactar")
        boton = next((c for c in rama if c["clase"] == "Button"), None)
        if boton and "(" not in (boton.get("etiqueta") or ""):
            break
        time.sleep(1.0)
    if boton is None:
        res.fallo("enviar al chat: no encuentro el boton de enviar")
        return
    etiqueta = (boton.get("etiqueta") or "").replace("&", "")
    if "(" in etiqueta:
        res.nota("enviar al chat: NO se manda nada, el boton dice «%s». "
                 "Falta sesion o el directo no tiene chat abierto." % etiqueta)
        return

    app.pedir("foco", nombre="Mensaje para el chat")
    app.pedir("texto", valor="test")
    n = len(app.anuncios)
    app.pedir("pulsar", nombre="Enviar mensaje al chat")

    # Se espera a lo que DICE, no a un reloj: la llamada va en un hilo aparte y
    # tarda lo que tarde la red.
    dicho = ""
    limite = time.time() + 45
    while time.time() < limite:
        dicho = " ".join(a.get("texto", "") for a in app.anuncios[n:]).lower()
        if "enviado" in dicho or "error" in dicho or "no se pudo" in dicho:
            break
        time.sleep(0.5)

    for d in [a.get("texto", "") for a in app.anuncios[n:]][:6]:
        res.nota("  enviar al chat dice: " + d[:90])
    if "enviado" in dicho:
        res.nota("enviar al chat: el mensaje salio y se anuncio")
    elif not dicho:
        res.fallo("enviar al chat: pulse enviar y la aplicacion no dijo nada "
                  "en 45 s. Sin voz, quien no ve no sabe si salio")
    else:
        res.fallo("enviar al chat: no confirmo el envio, dijo: " + dicho[:120])

    # Despues de enviar, el cuadro queda vacio y con el foco: si no, hay que
    # volver a buscarlo con Tab para escribir el siguiente.
    rama = subarbol(app.arbol(), "PanelRedactar")
    cuadro = next((c for c in rama if c["clase"] == "TextCtrl"), None)
    if cuadro is None:
        res.fallo("enviar al chat: el cuadro desaparecio despues de enviar")
    else:
        if (cuadro.get("valor") or "").strip():
            res.fallo("enviar al chat: el cuadro conserva el texto ya enviado, "
                      "asi que el siguiente mensaje saldria repetido")
        else:
            res.nota("enviar al chat: el cuadro queda vacio")

# Novedades de Bellbird

Qué cambia en cada versión, contado en lenguaje llano y pensado para quien usa
la aplicación. El detalle técnico de cada cambio está en el historial de git.

## 3.0.0 beta 1, noviembre de 2026

La aplicación pasa a llamarse Bellbird, por el pájaro campana, que es el ave
nacional de Paraguay. También estrena un panel de transmisión, grabaciones,
encuadre de cámara y un Administrador de descargas nuevo.

### El nombre nuevo

- La versión 2.5.1 no ofrece esta beta por su cuenta, así que se instala a
  mano. Descarga el ZIP, descomprímelo en una carpeta nueva y copia en ella la
  carpeta `data` de la versión anterior, que guarda las preferencias, la
  sesión de YouTube y el historial. Si descargabas en la carpeta `Descargas`
  de la aplicación, cópiala también. Cuando funcione, puedes eliminar la
  carpeta anterior. Desde esta beta, la aplicación ofrece las versiones
  siguientes y las instala.
- La aplicación ahora es `Bellbird.exe`. El ZIP y su carpeta llevan el nombre
  Bellbird con el número de versión.
- Un acceso directo a `YTChatTTS.exe` deja de funcionar después de actualizar.
  Si abrías la aplicación con un acceso directo, elimínalo y crea uno nuevo
  desde `Bellbird.exe`, dentro de la carpeta de la aplicación.
- La fuente del chat en OBS se renombra sola a «Chat en el vídeo» y conserva
  su lugar y su tamaño. Las escenas que ya tienes siguen funcionando.

### Novedades

- El *Panel de transmisión* se organizó de nuevo. *Estado* dice cómo está
  todo. *Transmitir en directo* prepara OBS y revisa la escena con un solo
  botón, igual que el de la ventana principal, y pide confirmación al
  finalizar. Solo se muestran los controles que sirven en ese momento.
- *Organizar escena* es una ventana nueva que se abre desde el panel. Reúne lo
  que ordena una escena: qué ventana se captura y dónde va cada fuente. Elegir
  otra escena ahí no cambia lo que ven los espectadores.
- *Iniciar o detener grabación* (`Alt+Mayús+G`) y *Pausar o reanudar
  grabación* (`Alt+Mayús+P`) están en el menú *Transmisión*. Si OBS no pausa la
  grabación, la aplicación lo dice.
- Al detener la grabación, la aplicación dice «Grabación guardada» con el
  nombre del archivo. *Grabaciones guardadas…*, en el menú *Transmisión* y en
  el panel, permite abrir lo grabado, abrir su carpeta, copiar la ruta y
  eliminarlo de la lista.
- Igualar el volumen tarda menos, porque mide varias canciones a la vez.
- *Canal de actualización*, en *Preferencias*, tiene dos opciones. *Estable*,
  de fábrica, ofrece solo versiones estables. *Beta* ofrece también las de
  prueba.
- Los menús, las *Preferencias* y los avisos usan las palabras de Windows para
  el límite de caracteres y para activar una opción. También dicen anunciar
  canción actual, dejar de silenciar, y bajar y subir velocidad de la voz en el
  menú *Voz*. Si una tecla ya está asignada a otra acción, el aviso al abrir la
  aplicación dice a cuál y qué atajo se desactivó.
- Encuadre de cámara. `Ctrl+F3` dice cómo se te ve en la cámara de la escena al
  aire de OBS: si estás centrado, lejos, fuera del borde o con poca luz, y
  hacia dónde moverte. `Ctrl+Mayús+F3` activa avisos con sonido propio cuando
  el rostro sale del encuadre y cuando vuelve. Si pulsas `Ctrl+F3` dos veces,
  empieza una guía de sonido: cada pitido suena del lado hacia el que tienes que
  moverte y se repite más seguido al acercarte, y en el centro suena un tono
  continuo. La imagen se analiza en el equipo, sin enviarla a ningún sitio. La
  cámara, los avisos, la inversión de izquierda y derecha y el *Sonido de la
  guía* (Normal, Cálido u 8 bits) se eligen en la categoría *Cámara* de
  *Preferencias*.
- `Ctrl+Mayús+O`, o *Mostrar OBS* en el menú *Transmisión*, trae al frente la
  ventana de OBS, también cuando está en el área de notificación. Si OBS espera
  una respuesta, como la pregunta del modo seguro, el foco va a ese cuadro.
- Si OBS está abierto pero no responde, la aplicación ya no pide comprobar que
  esté abierto. Dice que puede estar esperando una respuesta y que elijas
  *Mostrar OBS*.
- *Grabar también al transmitir*, en el menú *Transmisión*, hace que OBS
  empiece a grabar cuando la transmisión empieza bien y deje de grabar cuando
  se detiene. Si ya estabas grabando, esa grabación sigue como estaba. Viene
  desmarcada.
- Iniciar, pausar, reanudar y detener la grabación tienen sonidos propios.
- *Mostrar en el título de la ventana si se transmite o se graba*, en
  *Preferencias, Transmisión*, antepone ese estado al título. Viene
  desmarcada.
- Si la grabación no se puede iniciar, la transmisión sigue y la aplicación lo
  avisa con un sonido propio.
- Con esa casilla marcada, la revisión antes de transmitir avisa si el perfil
  de OBS graba con un codificador propio. En ese caso, transmitir y grabar a
  la vez carga el doble el equipo.
- *Elegir micrófono…*, en el menú *Transmisión*, abre un cuadro con la fuente
  de micrófono de OBS y el dispositivo que usa. Al pulsar *Aplicar*, OBS
  cambia de dispositivo y la aplicación dice si ya entra sonido. El atajo para
  silenciar el micrófono usa desde entonces esa fuente.
- En TikTok, los me gusta se escriben en la lista del chat, una fila por
  persona y con la cantidad de cada una. Antes solo sonaban. *Agrupar me gusta
  durante (segundos)*, en la categoría *Lectura*, decide cuántos segundos se
  juntan los toques de cada persona antes del aviso: de 1 a 120, y 10 de
  fábrica.
- Cada evento de un directo tiene su modo en *Preferencias*, categoría
  *Lectura*: Super Chats y regalos, membresías, entradas, me gusta,
  seguidores, compartidos y cofres. Cada uno puede ser *Voz principal*, *Voz
  secundaria*, *Solo sonido* o *Desactivado*. De fábrica las entradas y los me
  gusta suenan sin leerse, y el resto se lee con la voz principal. Si ya tenías
  marcada la lectura de entradas o de me gusta, se respeta.
- La categoría *Voces* llama *Voz principal* a la de siempre y suma el grupo
  *Voz secundaria*, con su voz, su velocidad, su volumen y su botón de prueba.
  Los eventos que elijas se leen con ella, y el mensaje siguiente vuelve a la
  principal. Los cambios se aplican al guardar, sin reiniciar.
- La lista del chat tiene el filtro *Avisos*, que deja ver solo esos avisos de
  TikTok.
- La aplicación está también en inglés. El idioma se elige en *Preferencias*,
  categoría *General*, y se aplica al reiniciar. Al guardar, un cuadro ofrece
  *Reiniciar ahora* o *Más tarde*. De fábrica usa el idioma de Windows.
- Sin conexión, la ventana principal muestra la lista *Recientes* (`Alt+S`) con
  los diez últimos directos y vídeos, de YouTube y TikTok. `Intro` abre uno,
  `Supr` lo elimina del historial y su menú contextual ofrece abrirlo,
  eliminarlo o abrir el historial completo.
- Con solo el audio, un vídeo largo salta en menos de un segundo. Cuando la
  pista de audio pasa de 10 MB se usa otra fuente, con algo menos de calidad
  de sonido.
- *Reproducir solo el audio, sin imagen* viene marcada de fábrica. Con ella, un
  vídeo grabado salta en menos de un segundo. Con la casilla desmarcada se ve
  la imagen, y cada salto tarda unos segundos. Si ya la habías cambiado, se
  conserva lo que elegiste. En un directo se comporta como antes.
- La opción *Preguntar si se abre la carpeta al terminar la cola*, en
  *Preferencias, Descargas*, hace una sola pregunta cuando termina toda la
  cola, si algo se descargó bien. Viene desmarcada.
- El historial y los directos recientes muestran la fecha corta, como
  27/10/2026, en lugar de 2026-10-27.
- Los textos de la aplicación usan los términos de Windows, como *Eliminar* e
  *Intro*, y frases más cortas. Algunos nombres cambian: *Administrador de
  descargas*, *Leer en voz alta*, *Clave de API*, y *voz* en lugar del nombre
  anterior de la lectura. Cada sección de *Preferencias* se llama categoría,
  como en NVDA.
- Las acciones de moderación del menú contextual del chat se llaman como en
  YouTube. La opción de suspender dura 5 minutos y la de ocultar actúa en el
  canal de YouTube, que se puede deshacer desde YouTube Studio.
- En la ventana de música, el botón que vuelve a leer la carpeta se llama
  *Actualizar carpeta*, con la letra Z. Los avisos dicen enlace, aplicación y
  *Esc* en lugar de las palabras anteriores.
- Con la sesión de YouTube iniciada, `F2` dice cuántas unidades de la cuota
  diaria se usaron hoy desde este equipo. El número es aproximado, y como la
  cuota se comparte entre quienes usan la aplicación, sirve para saber si un
  error de cuota viene de tu uso o del de otros. Se puede eliminar del resumen
  en *Preferencias, Estado (F2)*.
- Si pulsas `F2` dos veces seguidas, el estado se abre en un cuadro con una
  línea por cada parte, para recorrerlo con las flechas.
- Al llegar al tope de la velocidad o el volumen de la voz, el aviso dice
  «máximo» o «mínimo».
- Al asignar un atajo que ya usa otra acción, el aviso dice qué teclas son y
  qué acción las tiene.
- Si entre la versión instalada y la nueva hay otras, la ventana de
  actualización muestra las novedades de todas, de la más nueva a la más
  antigua. Cada una lleva su encabezado y su número de versión.

### El Administrador de descargas, renovado

- La ventana tiene dos pestañas. *Buscar en YouTube* se abre primero, con el
  foco en el campo. *Descargas* tiene la cola y el historial.
- En el campo *Buscar o pegar enlace*, las palabras buscan en YouTube y un
  enlace va a la cola, sea de YouTube o de otro sitio compatible. *Ver sitios
  compatibles* abre la lista de sitios. El campo recuerda las búsquedas
  recientes.
- Los resultados muestran título, canal, duración, vistas y fecha, y el cuadro
  *Detalles* tiene los datos completos del elegido. *Cantidad* elige cuántos
  resultados llegan, y *Mostrar más* trae otra tanda.
- La casilla *Mostrar filtros* agrega tipo (vídeos, listas, canales o directo),
  duración, fecha y orden.
- `Intro` sobre un vídeo lo descarga sin preguntar y dice «Descargando» o «En
  cola» con el título. `Intro` sobre una lista o un canal muestra sus vídeos.
  `Retroceso` vuelve a los resultados, y *Agregar lista entera* la descarga
  completa.
- `Espacio` pone el resultado a sonar en la música, sin descargarlo. Detiene
  solo la canción actual y queda en la cola como una más. Otra vez `Espacio` lo
  pausa.
- *Abrir en Bellbird* deja el sonido libre para el reproductor. Si el resultado
  es la canción que suena, la música se detiene y la canción sale de la cola.
  Si suena otra, queda en pausa.
- El menú contextual de un resultado permite varias acciones. Puedes agregarlo
  a la cola, escucharlo, descargarlo como audio o como vídeo sin cambiar el
  formato elegido, abrirlo en Bellbird o agregarlo a la música. También puedes
  ver su contenido, copiar el enlace y abrirlo en el navegador.
- Antes de agregar algo, la aplicación avisa si ya está en el historial. Un
  directo en curso no se descarga, y la aplicación lo dice.
- La pestaña *Descargas* tiene una sola lista, y *Mostrar* elige qué se ve:
  todas, en curso, en espera, completadas o con errores, cada una con su
  cantidad. Con la tecla Aplicaciones o `Mayús+F10` se abre el menú para abrir
  el archivo o su carpeta, reintentar, volver a descargar, copiar el enlace,
  cancelar y eliminar. `Supr` elimina la descarga elegida de la lista.
- Mientras descarga, la columna *Estado* dice la velocidad y el tiempo que
  falta. En una lista dice también por qué vídeo va, como «vídeo 3 de 10». La
  columna *Progreso* muestra una barra junto al porcentaje.
- *Elegir formato…*, en el menú contextual de un vídeo, muestra las
  resoluciones que tiene ese vídeo con su tamaño, como «1080p 60 fps, MP4,
  255 MB», y una opción de solo audio. La elegida se descarga sin cambiar
  *Formato* ni *Calidad*. Consultar los formatos tarda unos segundos, y la
  aplicación lo avisa con un sonido.
- *Formato* tiene nueve opciones: vídeo original, MP4 o WebM, y audio original,
  MP3, M4A, Opus, FLAC o WAV. *Calidad* cambia según el formato: resolución en
  vídeo y kbps en audio. El archivo guarda el título y los datos del vídeo, y
  la portada cuando el formato la admite.
- El audio se descarga también en sitios que no lo separan del vídeo, como
  Dailymotion o Twitch.
- *Preferencias* tiene la categoría nueva *Descargas*: carpeta, numerar los
  archivos de una lista, descargas simultáneas, límite de velocidad, carpeta
  propia para cada lista y nombre de los archivos.
- Al salir de la aplicación con descargas sin terminar, la pregunta dice
  cuántas se cancelarán. Aparece aunque tengas desactivada la confirmación al
  salir.
- La búsqueda, el agregado a la cola, el procesado, el fin de la cola y una
  descarga que terminó a medias tienen sonidos propios, en los dos temas.
- El paquete trae la herramienta que YouTube pide ahora para leer sus vídeos,
  así que las descargas y el reproductor obtienen todos los formatos. Abrir un
  vídeo o empezar una descarga tarda alrededor de un segundo y medio más.
- En *Preferencias*, categoría *Descargas*, *Canal de actualización de yt-dlp*
  elige entre *Estable* y *Diario*. *Diario* trae los arreglos para YouTube
  unos días antes, y puede traer errores nuevos.
- *Anunciar progreso de las descargas*, en *Preferencias*, categoría
  *Descargas*, dice el avance de cada descarga cada 10 por ciento, con un
  sonido propio. Si una descarga sigue en cero, dice «Descarga en curso» cada
  15 segundos, con otro sonido. Con más de una descarga a la vez, el aviso
  empieza por el nombre del vídeo. Funciona aunque el Administrador de
  descargas esté cerrado. Viene desmarcada.

### Aspecto de la aplicación

- La ventana, el panel de chat de la transmisión y la documentación cambian de
  colores, con una paleta inspirada en el pájaro campana: blanco frío y
  turquesa. Todo texto sigue cumpliendo el contraste mínimo.
- Todas las ventanas usan los mismos colores. Los campos y las listas son
  blancos, el botón principal de cada ventana va en turquesa con texto blanco,
  y los títulos de los grupos también van en turquesa.
- En *Transmisión*, *Preferencias* y *Directo de YouTube*, cada botón está
  junto al campo sobre el que actúa, y los botones de una misma sección van en
  una fila. El *Historial de directos* es más grande y muestra los títulos
  enteros.
- Todas las etiquetas de *Preferencias* terminan en dos puntos. En *Mensajes
  automáticos* la lista tiene su etiqueta, y los intervalos se llaman
  «Intervalo mínimo» e «Intervalo máximo». En *Música*, mostrar los filtros es
  una casilla, como en *Descargas*.
- La barra de estado dice «Velocidad», «Volumen» y «Super Chats» en lugar de
  abreviaturas. En *Transmisión*, el usuario de TikTok solo se puede escribir
  cuando el destino es TikTok.

### Arreglos

- Algunos vídeos de YouTube no se abrían al primer intento, o decían «Fin del
  vídeo» sin haber empezado. Ahora la aplicación espera los pocos segundos que
  YouTube tarda en dejar disponible el vídeo, y si la apertura falla, dice que
  falló.
- Cuando TikTok frena las consultas seguidas, la aplicación ya no lo toma por
  un directo que no aparece. Al transmitir avisa que TikTok está limitando las
  consultas, con un sonido propio. Al conectar al chat lo dice así, en lugar
  de un error técnico, y espera medio minuto antes de reintentar.
- `F2` dice el singular cuando hay uno solo: «1 regalo», «1 Super Chat» y «1
  leído».
- Dos errores de TikTok se entienden mejor: «TikTok no responde por ahora» y
  «TikTok devolvió un error», en lugar de nombrar piezas internas.
- Cancelar una descarga que ya terminó dice «La descarga ya terminó», en lugar
  de anunciar que se canceló.
- Al cerrar *Preferencias* sin guardar después de probar una voz, la voz de
  prueba ya no queda abierta.
- Cuando el chat de TikTok se reconecta, la lista ya no se vacía y el vídeo no
  vuelve a empezar solo.
- En *Descargas*, el estado de una descarga que espera se lee «en cola», sin el
  guion bajo.
- En *Descargas*, el enlace de un vídeo abierto desde una lista de reproducción
  descarga solo ese vídeo, y no la lista entera.
- En *Descargas*, cada descarga que espera su turno usa el formato y la carpeta
  que había al agregarla, aunque después cambies las opciones.
- Ninguna letra de acceso se repite en las categorías de *Preferencias* ni en
  los cuadros de transmisión, comentarios, historial y descargas. *Cancelar
  descarga* pasa a la letra A y vaciar el historial a la H.
- Las letras de acceso de cada categoría de *Preferencias* ya no repiten las de
  *Guardar* y *Cancelar*. Tampoco repiten la de *Enlace o ID* de la ventana
  principal. Cambian *Enviar* en el chat del directo (`Alt+N`), *Leer los
  mensajes recientes con* (`Alt+R`). Además, en *API y sesión* y *Mensajes
  automáticos* cambian los botones de guardar (`Alt+A`), *Clave de API*
  (`Alt+V`), *ID de cliente OAuth* (`Alt+O`) y *Agregar* (`Alt+R`).

## 2.5.1, octubre de 2026

Arreglos de la música y del directo de TikTok, y filtros nuevos para la
biblioteca de canciones.

### Licencia

- La aplicación pasa a la licencia GPL-3.0. Quien use este código en otra
  aplicación tiene que publicar la suya con la misma licencia. Las versiones
  hasta la 2.5.0 siguen con la licencia MIT.

### Música

- La música y el reproductor ya no comparten el volumen. Antes, silenciar el
  vídeo o el directo con `Ctrl+M` callaba también la música, y pausar uno podía
  afectar al otro. Ahora cada uno tiene su volumen.
- La igualación sube también las canciones flojas. Antes solo bajaba las
  fuertes, y con el volumen de la música en 100 no podía subir ninguna. Sube
  cada canción hasta donde lo permite su pico, sin distorsionar.
- El fundido entre canciones ya no da saltos de volumen. La canción que termina
  baja desde su propio volumen. Además, pasar de canción en medio de un fundido
  ya no deja la anterior sonando.
- El buscador filtra por el comienzo de cada palabra. Al escribir «a» salen las
  canciones con una palabra que empieza por «a», no todas las que tienen una a
  en medio. Varias palabras se buscan en cualquier orden: «lou oj» encuentra
  «Ojos» de Lou Cornago.
- La lista de canciones se puede filtrar y ordenar. *Mostrar filtros* abre
  dos cuadros: *Mostrar*, para ver todas las canciones o las de un artista, y
  *Ordenar por*, con el orden de la colección, título, artista, más recientes
  primero o duración. Se combinan con Buscar, dicen cuántas canciones quedan y
  se recuerdan para la próxima vez. Una canción con varios artistas aparece en
  cada uno. Con los filtros ocultos se ven todas las canciones.
- Puedes crear listas propias. En el editor de listas, `Intro` marca y desmarca
  la canción, igual que `Espacio`. *Nueva lista* y *Editar lista* ofrecen las
  canciones de la carpeta aunque esté elegida una lista en Colecciones. Si a
  una lista le falta una canción porque su archivo ya no está, el aviso dice
  cuál, y al recorrer Colecciones no se repite.

### Listas en toda la aplicación

- Escribir varias letras seguidas salta al elemento que empieza así. Antes solo
  funcionaba en el chat y en los comentarios. Ahora también en el historial, la
  conversación con la IA, los mensajes automáticos y las listas de la música.

### TikTok

- Si el directo no se puede abrir, se dice. Antes se oía «Fin del vídeo» aunque
  el directo nunca hubiera empezado a sonar. Ahora se avisa con sonido de error
  que no se pudo abrir, y el registro anota el motivo para poder encontrar la
  causa.

## 2.5.0, octubre de 2026

Preguntar a una inteligencia artificial qué se ve en la transmisión, y
transiciones nuevas entre canciones.

### Preguntar a la IA

- Una ventana nueva con `Ctrl+Mayús+I` permite preguntar qué se ve. Agrega una
  captura de la escena al aire o de una fuente de OBS y pregunta lo que quieras:
  si la cámara está activada, si algo salió en negro, qué texto hay en pantalla.
  La respuesta se lee al llegar y queda en la conversación para seguir
  preguntando.
- La consulta rápida con `Ctrl+Mayús+F2` captura la escena al aire, la envía y
  lee la respuesta sin abrir ninguna ventana. La pregunta de fábrica pide
  primero los problemas de la escena y después la describe.
- En *Preferencias* hay una página nueva, *Inteligencia artificial*. Eliges el
  proveedor (Google Gemini, OpenAI, Anthropic, OpenRouter, OpenCode Go, Command
  Code u otro compatible con OpenAI), guardas la clave y eliges el modelo. La
  clave queda en el Administrador de credenciales de Windows. La lista de
  modelos trae solo los que aceptan imágenes, y con OpenRouter y OpenCode Go
  puede mostrar solo los gratuitos.
- La espera tiene su melodía, y hay sonidos para la consulta enviada, la
  respuesta, el error y la cancelación. Si la captura sale negra, no se envía,
  y se dice por qué: la escena no tiene captura o una fuente no tiene elegido
  qué capturar.
- El primer envío pide confirmación, porque la captura y lo que escribas salen
  de tu equipo hacia el proveedor.

### Música

- Hay un fundido entre canciones. El final de una canción se mezcla con el
  principio de la siguiente, y se salta el silencio que muchos archivos traen al
  principio y al final. Dura 6 segundos de fábrica. Se cambia en
  *Preferencias*, página *Música*, de 0 a 12, y 0 lo desactiva. Pasar de canción
  con el atajo hace un fundido corto, de medio segundo.
- La igualación del volumen corrige en su justa medida. Antes exageraba la
  diferencia entre canciones. Además ya no mide por su cuenta: al abrir la
  ventana *Música* pregunta si medir las canciones pendientes, y la ventana
  tiene un botón para empezar y detener.
- El sonido de cambio de canción viene desactivado de fábrica. Si lo activas,
  es más suave y más grave.
- La carpeta se vigila. Las canciones nuevas aparecen solas en la lista. La
  ventana *Música* tiene el botón *Examinar…*, y la carpeta de fábrica
  es Música, junto a la aplicación.
- Al retomar se dice cuántas canciones tiene la cola, por ejemplo «Retomando 6
  canciones: evergreen». Con la opción de recordar la última lista al abrir, reproducir
  sigue la última cola, que puede ser una búsqueda y no la carpeta entera.
- Hay más formatos: aiff, aif, mka y webm.

### Chat y lectura

- Los diez mensajes más recientes se leen con `Ctrl+Mayús` y un número. 1 lee el
  último y 0 el décimo desde el final. Una casilla de *Preferencias*, página
  *Lectura*, los hace valer en cualquier aplicación.
- Los mensajes se leen con el lector de pantalla o con la voz de la aplicación.
  En la misma página eliges quién los lee. Con la voz, el mensaje pedido suena
  antes que los que esperan, y después esos siguen en su orden.
- Al abrir la aplicación, el campo *Enlace o ID* está vacío. Ya no se recuerda
  el último enlace entre una vez y otra. Para volver a un directo está el
  *Historial de directos*.

### Transmisión

- El micrófono dice qué dispositivo usa al activarlo con `Alt+Mayús+M`, por
  ejemplo: «Micrófono activado: predeterminado de Windows, WO Mic Device». Si
  OBS usa el predeterminado, lo dice, porque ese micrófono cambia cuando
  Windows elige otro.
- Si el micrófono no recibe sonido, hay un aviso. Después de activarlo, la
  aplicación escucha tres segundos. Si no entra nada, suena un sonido propio y
  dice «El micrófono no recibe sonido. Revisa cuál está elegido en Windows o en
  OBS.».
- La ventana *Transmisión* explica qué se ve en el directo: la ventana elegida
  en la ventana que se captura. Esa captura no lleva sonido, que sale del audio
  del escritorio y del micrófono de OBS.
- El panel de chat vuelve a salir en OBS tras reiniciar la aplicación. Si OBS
  se abría antes que la aplicación, el chat no aparecía en el directo hasta
  recargar la fuente a mano. Ahora la aplicación la recarga sola al activar el
  panel.
- El usuario de TikTok funciona con mayúsculas. TikTok solo reconoce el usuario
  en minúsculas, y con una mayúscula la aplicación no encontraba el directo.
  Ahora lo pasa a minúsculas sola, también el que ya estaba guardado.
- El chat de TikTok se conecta aunque el directo tarde en figurar. Al salir al
  aire, TikTok a veces dice unos segundos que no hay directo, y la aplicación se
  rendía. Ahora vuelve a intentarlo hasta que aparece.
- `F2` dice cuántos espectadores hay ahora en TikTok y cuántos pasaron. Antes
  decía como espectadores a todos los que habían entrado desde el principio, y
  el número solo subía. Ahora dice, por ejemplo, «12 espectadores ahora, 108 en
  total».
- Un directo de TikTok no se pausa en el reproductor. TikTok no guarda lo
  emitido, así que al reanudar había que volver a abrirlo y se bloqueaba. Ahora
  la pausa avisa que no se puede y dice el atajo de Silenciar, que calla el
  directo sin interrumpirlo.
- Hay más eventos de TikTok. Se leen los comentarios hechos solo con stickers
  («Ana: sticker») y las preguntas («Ana: Pregunta:»). Cuando TikTok pausa
  el directo o lo retoma, suena un sonido propio para cada caso y se dice. Hay
  una casilla nueva en *Preferencias*, leer quién da corazones: marcada, además
  del sonido se lee «Ana dio 15 corazones». Viene desmarcada porque en directos
  grandes los corazones no paran.

### Sonidos y ventanas

- La página *Sonidos* de *Preferencias* permite silenciar cada sonido por
  separado.
- Suena un tono de ocupado cuando otra aplicación ya usa uno de los atajos que
  valen en cualquier aplicación. Antes sonaba el de error.
- Las ventanas que quedaban grises usan los colores de la ventana principal.
  Son las de *Preferencias*, actualización, *Transmitir a* y la de la IA. Con el
  contraste alto de Windows no cambia nada.
- Los errores de las descargas dicen el motivo en lenguaje llano.
- Algunos textos se veían incompletos. Eran el botón *Enviar* cuando no se puede
  escribir en el chat y la velocidad y el volumen de la voz en la barra de
  estado. También eran los campos del cuadro *Directo de YouTube*, que quedaban
  pegados a la barra de desplazamiento. El texto de ayuda de la ventana principal
  ya no queda incompleto al desconectarse de un directo. En *Preferencias*,
  *Estado (F2)*, la casilla de espectadores dice ahora «Espectadores ahora y en
  total».

### Para encontrar problemas

- El registro de diagnóstico anota qué sonido sonó, qué atajo o comando del
  menú se usó y de qué tipo fue cada evento del chat, sin el texto de los
  mensajes ni quién los escribió. La lista de procesos internos ya no se repite
  cada 30 segundos cuando no cambió.
- El registro detallado viene activado en una instalación nueva. Quien ya lo
  tenía desactivado en *Preferencias* lo conserva desactivado.
- En *Ayuda*, la opción Abrir la carpeta de registros abre la carpeta donde
  están los registros, para mandarlos cuando algo falla.
- El archivo de errores ya no crece sin fin: al pasar de 1 MB se guarda aparte
  y empieza uno nuevo.

## 2.4.1, octubre de 2026

- La actualización automática ya no se detiene al cerrar la versión anterior. El
  instalador esperaba un minuto y mostraba «la aplicación no se cerró a tiempo»
  aunque la versión anterior ya se había cerrado. Pasaba cuando otra aplicación, como el
  lector de pantalla o el antivirus, seguía vigilando el proceso. Ahora detecta
  el cierre en el momento. Desde la 2.3.4 o la 2.4.0 se actualiza de la forma
  habitual.

## 2.4.0, octubre de 2026

Música mientras transmites, sin abrir otra aplicación en el equipo.

### Música

- El menú *Música* tiene sus atajos. Con `Ctrl+Alt+Espacio` puedes reproducir o
  pausar.
  `Ctrl+Alt+Flecha derecha` y `Ctrl+Alt+Flecha izquierda` pasan a la canción
  siguiente o a la anterior. `Ctrl+Alt+Flecha arriba` y `Ctrl+Alt+Flecha abajo`
  suben y bajan el volumen de la música, y `Ctrl+Alt+T` dice qué suena.
  `Ctrl+Alt+M` silencia la música, `Ctrl+Alt+D` la detiene, `Ctrl+Alt+A` cambia
  el orden aleatorio y `Ctrl+Alt+R` cambia la repetición.
  `Ctrl+Alt+Mayús+Flecha derecha` y `Ctrl+Alt+Mayús+Flecha izquierda` adelantan
  y retroceden 10 segundos. La primera vez puede tardar unos segundos en
  prepararse, y lo anuncia.
- Se usa tu carpeta Música de Windows, o la que elijas en *Preferencias*, página
  *Música*, aunque la hayas movido a otro disco. En esa página también están el
  orden aleatorio, repetir toda la cola o la canción actual y el volumen de la
  música. Ese volumen es aparte del de la voz y del reproductor, y ahí se elige
  por qué salida de audio suena.
- Al pasar de canción se puede decir nada, el título, el título y el artista, o
  solo el artista. Con *Nada* solo suena el sonido de cambio de canción, si lo
  dejas activado, pero cuando pasas de canción con el atajo se dice el título,
  porque lo pediste. Otra casilla decide si se anuncian «Música en pausa»,
  «Música reanudada» y «Desde el comienzo».
- La ventana *Música* se abre con `Ctrl+Mayús+M`. Busca en tu carpeta mientras
  escribes, aunque no pongas las tildes. Reproduce la canción elegida o todo el
  resultado, agrégalo a la cola, mira la cola y salta a cualquier canción con
  `Intro`. Con la opción de reproducir a continuación, la canción elegida suena al terminar
  la actual, sin interrumpir nada, y después la cola sigue donde iba. Mientras
  está abierta, los atajos de música siguen funcionando.
- Las canciones aparecen primero con el nombre del archivo y, unos segundos
  después, con el título y el artista que trae el propio archivo, sin que se
  mueva la canción en que estás. La segunda vez que abres la carpeta ya salen
  así desde el principio.
- Hay listas propias en la misma ventana. En la lista *Colecciones*,
  *Biblioteca* es tu carpeta y debajo están tus listas, cada una con cuántas
  canciones tiene. Crea una con la opción de agregar a una lista y *Nueva lista…* del menú
  de una canción. Renómbralas y elimínalas, elimina canciones con `Supr` y
  cámbialas de lugar con `Alt+Flecha arriba` y `Alt+Flecha abajo`. También
  puedes guardar la cola que suena como lista. Se guardan como archivos .m3u8,
  que abren otros reproductores.
- Los enlaces y las listas de YouTube se abren desde la ventana *Música*.
  *Abrir enlace…* acepta un vídeo o una lista entera de YouTube y suma su audio
  a la cola. El orden aleatorio también vale para esas listas.
- La igualación del volumen de las canciones hace que todas suenen parecido,
  como en Spotify. Cada archivo se mide una sola vez, de fondo, y el volumen se
  corrige al empezar cada canción. La primera vez se oye un sonido propio y se
  dice cuántas canciones se van a medir. El avance aparece en la ventana
  *Música* y en `F2`, y se desactiva con una casilla de la página *Música*.
- `F2` dice qué suena, si lo dejas activado en la página *Estado (F2)*.
- Al abrir YTChat y pulsar Reproducir, sigue la última cola desde la canción en
  que estaba. No empieza a sonar sola.
- Los atajos de música pueden funcionar en cualquier aplicación, si marcas la
  casilla de la página *Música*. Así funcionan aunque estés en OBS o en un
  juego. Viene desactivada porque, mientras está activa, esas teclas no llegan a
  las demás aplicaciones. Donde NVDA cree que hay una tabla, como el escritorio,
  se queda con `Ctrl+Alt+flechas`: ahí pulsa `NVDA+F2` antes del atajo.

### Atajos

- Cada familia de teclas tiene un área. `Ctrl` es el reproductor, `Alt` el chat,
  `Ctrl+Mayús` abre ventanas, `Alt+Mayús` es el directo y OBS, las teclas `F` son
  la voz y `Ctrl+Alt` la música. Por eso cambian algunos de fábrica. Conectar y
  desconectar pasan a `Alt+Mayús+C` y `Alt+Mayús+D`, ir a la lista de mensajes a
  `Alt+Mayús+L` y el micrófono de OBS a `Alt+Mayús+M`. Marcar una incidencia pasa
  a `Alt+Mayús+I`, copiar el enlace a `Alt+Mayús+E` y el *Administrador de
  descargas* a `Ctrl+Mayús+D`. Si habías cambiado alguno, se respeta el tuyo.
- Las teclas llevan su nombre en español en la página *Atajos* de *Preferencias*
  y al capturar una combinación.
- Los atajos de música aceptan `Ctrl+Alt` con una letra o un número. Al
  capturarlo, la aplicación revisa tu teclado: si `AltGr` con esa tecla escribe
  algo, como la arroba en el teclado latinoamericano, te lo dice y te pide otra.
  Así puedes seguir escribiendo ese carácter en el chat.

### Chat

- Una pérdida de conexión ya no cierra el directo. Antes, si se interrumpía la conexión
  con el chat, al volver sola la aplicación leía los mensajes pero no dejaba
  escribir ni moderar. Ahora avisa «Se perdió la conexión con el chat», reintenta
  a los 1, 2, 5 y 10 segundos, y después según la *Espera máxima entre intentos, en segundos*
  de *Preferencias*. Al volver dice «Chat reconectado.» y todo sigue como antes
  del corte.
- Los mensajes no se repiten tras un corte. Lo que ya se había leído no se
  vuelve a leer al reconectar.

### Pantallas

- La ventana del directo de YouTube cabe en pantallas de poca altura. En una
  pantalla de 768 píxeles de alto no se veían los botones *Transmitir* y
  *Cancelar*. Ahora
  los campos se desplazan y esos botones quedan siempre a la vista.
- Los campos de solo lectura se alcanzan con `Tab`. El avance de la igualación
  del volumen en la ventana *Música* y la miniatura en la ventana del directo de
  YouTube se saltaban al recorrer con `Tab`.
- Los nombres enteros se ven en *Preferencias*. La lista de páginas ya no corta
  *Cola de lectura*, *Interfaz* ni *Mensajes automáticos*.

## 2.3.4, octubre de 2026

Arreglos que salieron de un directo de prueba con la red inestable.

### Transmisión

- Cuando OBS no da abasto hay un solo aviso, y se puede desactivar. Antes sonaban
  dos frases largas cada minuto mientras se jugaba. Ahora es una sola, «OBS no da
  abasto: se pierde el 16 por ciento de los cuadros», y no se repite antes de
  cinco minutos. `Ctrl+Mayús+A` lo desactiva y lo vuelve a activar, y queda
  guardado. También está en el menú *Transmisión* y en la página *Transmisión*
  de *Preferencias*. Los avisos de red y de reconexión siguen siempre.
- Copiar el enlace de un directo privado funciona. `Ctrl+Mayús+E` ahora copia el
  enlace del directo privado o para niños que crea la aplicación. Antes decía que
  no había ningún directo conectado.

### Chat

- El chat deja de reintentar un directo que ya terminó. Si el chat quedaba
  conectado a un directo que había terminado, repetía sin fin «Desconectado» y
  «Reintentando en 15 segundos (intento 1 de 20)». Ahora la aplicación comprueba
  si el directo sigue en directo. Si terminó, lo dice una vez, «El directo
  terminó. Chat desconectado», con el sonido de fin del directo, y deja de
  intentar. Si sigue en directo, reintenta como antes, y el límite de veinte
  intentos ahora se cumple.

## 2.3.3, octubre de 2026

Un arreglo que completa lo de Detener que se explicó en la versión 2.3.2.

- El botón del directo espera a OBS. Mientras Detener espera a que OBS confirme,
  el botón dice *Deteniendo el directo* en vez de volver a ofrecer *Transmitir
  en directo*. Si lo pulsas en ese rato, avisa que se está esperando a OBS y no
  intenta otra transmisión, que OBS rechazaba con «No se puede cambiar de destino
  mientras se transmite». Lo mismo pasa en la ventana *Transmisión*. Cuando OBS
  confirma, el botón vuelve solo a *Transmitir en directo*.

## 2.3.2, octubre de 2026

Arreglos para transmitir con la red inestable y una opción nueva para que el
reproductor gaste menos recursos del equipo.

### Transmisión

- Detener espera a que OBS confirme. Antes decía «Transmisión detenida» al
  instante, aunque OBS tardara casi un minuto en parar con la red caída. Ahora lo
  dice cuando OBS de verdad paró. Si tarda más de tres segundos, avisa que está
  esperando. Si a los noventa segundos OBS sigue transmitiendo, lo dice para que
  lo detengas en OBS.
- El directo de YouTube se termina aunque falle la red. Si YouTube no confirma
  el fin, la aplicación lo vuelve a intentar sola cada quince segundos durante
  diez minutos, y avisa con un sonido nuevo cuando lo logra. Si no lo logra, lo
  intenta otra vez la próxima vez que abras YTChat, sin preguntarte.
- Hay aviso cuando OBS se reconecta y cuando vuelve. El aviso de reconexión
  existía pero no podía sonar nunca. Ahora suena al cortarse la conexión con el
  servicio y, con otro sonido nuevo, cuando la conexión vuelve.
- Hay aviso cuando el equipo no da abasto. Si se pierden cuadros porque el equipo
  no llega a codificar o a dibujar la escena, lo dice con el porcentaje y te
  sugiere cerrar aplicaciones. Es distinto del aviso de red lenta.
- Cada tipo de aviso se repite como mucho una vez por minuto.

### Reproductor

- La casilla *Reproducir solo el audio, sin imagen*, en *Preferencias*, página
  *Reproductor*, hace que el reproductor no decodifique la imagen de nada de lo
  que reproduce. Vale para directos o vídeos de YouTube y TikTok, y la tarjeta de
  vídeo queda libre para OBS. Viene desmarcada.

### Para encontrar problemas

- El registro guarda cada cosa que la aplicación anuncia, y qué decidió la
  revisión de directos que quedaron al aire al abrir. Los mensajes del chat no se
  guardan.

## 2.3.1, octubre de 2026

Arreglos del actualizador y una página *General* nueva en las *Preferencias* de
la aplicación.

### Actualizaciones

- La segunda actualización ya no falla. Antes de descomprimir una versión nueva,
  la aplicación borra lo que dejó la actualización anterior, y en ese paso fallaba
  siempre. El arreglo viaja dentro de esta versión: para pasar de la 2.3.0 a la
  2.3.1 todavía hay que borrar a mano la carpeta `data\actualizacion\nueva` antes
  de actualizar. Las siguientes ya no lo necesitan.
- La ventana de actualización se ve entera. Quedaba chica, y las novedades y el
  botón *Más tarde* no se veían. Ahora crece con su contenido, pone los botones
  en una fila y se puede agrandar.

### Preferencias

- La página *General* es la primera de la lista. Reúne *Buscar actualizaciones al
  iniciar* y el registro detallado, que estaban en Conexión y en Diagnóstico, y
  suma varias opciones:
  - Preguntar antes de salir si hay un chat conectado o una transmisión en
    curso.
  - Recordar el último enlace: al abrir, el campo trae el último directo al que
    te conectaste.
  - Reproducir el sonido de inicio.
  - Abrir la carpeta de datos.
  - Exportar e importar las preferencias, para pasarlas a otro equipo o guardar
    una copia. Las claves de tus cuentas no se exportan.
  - Restablecer todas las preferencias a los valores de fábrica.
- Antes de importar o restablecer se guarda una copia de las preferencias
  actuales en la carpeta de datos.
- La página Diagnóstico desaparece.

## 2.3.0, octubre de 2026

Más voces para leer el chat y más opciones al crear un directo de YouTube desde
la aplicación.

### Voces

- La página *Voces* de *Preferencias* permite elegir el motor de voz, la voz, la
  velocidad, el volumen y el tono. *Probar voz* te deja reproducir una muestra
  antes de guardar, y al guardar el cambio se aplica sin reiniciar.
- Hay tres motores de voz. Las voces de Windows de siempre (SAPI 5), las voces
  OneCore de Windows, y ElevenLabs, que genera la voz en internet con la clave de
  tu cuenta.
- ElevenLabs no deja el chat mudo. Si falla internet, la clave no sirve o se
  acaba el saldo, el mensaje se lee con la voz de Windows y la aplicación te lo
  avisa una vez. Puedes ponerle un límite de caracteres por sesión y usarlo solo
  con Super Chats, miembros, cofres, el propietario del canal y los moderadores.
  *Comprobar clave* te dice cuántas voces tiene tu cuenta y cuántos caracteres
  usaste este mes.
- Tu voz ya no cambia sola al instalar otra. Antes se guardaba el lugar de la voz
  en la lista, y una voz nueva corría la lista. Ahora se guarda el nombre. La
  primera vez que abras esta versión, tu voz guardada se convierte sola.
- La velocidad va de 0 a 100. `F9` y `F10` la mueven de 5 en 5 y la aplicación
  dice el número. La velocidad que tenías suena igual que antes.
- Los anuncios vuelven solos si reinicias el lector de pantalla. Si abres o
  reinicias NVDA o JAWS con la aplicación ya abierta, los anuncios vuelven a
  sonar a los pocos segundos.

### Preferencias

- Guardar es instantáneo y se oye. Antes tardaba un momento y el aviso se perdía
  al cerrarse la ventana. Ahora guarda todo de una vez, suena el sonido al
  pulsar *Guardar* y, ya de vuelta en la ventana principal, la aplicación dice
  «Preferencias guardadas» junto con cualquier otro aviso.

### Actualizaciones y avisos

- Si hay una versión nueva, se abre su ventana al iniciar la aplicación. Muestra
  las novedades y tiene dos botones: *Descargar e instalar* y *Más tarde*. Con
  *Más tarde* se cierra y la próxima vez que abras la aplicación vuelve a
  preguntar. Antes solo lo decía en voz una vez, y si estabas leyendo otra cosa
  con el lector, te lo perdías.
- Las novedades se leen bien. Ya no empiezan con líneas en blanco ni traen
  asteriscos, cada punto va en una sola línea con su viñeta y el cursor queda al
  comienzo.
- Al terminar una actualización se abre una ventana con el resultado. Si en ese
  momento hay un chat conectado, una transmisión u otra ventana abierta, espera a
  que termines para no interrumpirte.
- Cada aviso tiene su sonido. Descarga iniciada, terminada, con error y
  cancelada; directo al aire, transmisión detenida y problema en la transmisión;
  actualización disponible y lista; y una campanita para los avisos generales,
  como el de mensajes descartados. Antes varios usaban el mismo sonido y había
  que esperar a oír el texto para saber qué pasó.
- El tema *Suave* ya no repite sonidos. Diez eventos que sonaban igual que otro
  tienen ahora su sonido propio.
- Al iniciar ya no dice «Preparando el reproductor» ni «Reproductor listo». El
  reproductor se prepara igual, en silencio.

### Sonidos

- El tema *Suave* vuelve a sonar distinto. Desde la 2.2.0 sus sonidos eran una
  copia de los del tema *Predeterminado*. Ahora son sonidos propios, más cortos y
  tenues. Se elige en *Preferencias, Interfaz*.

### Directo de YouTube

- La ventana del directo tiene más opciones, y todas se recuerdan para la próxima
  vez:
  - latencia normal, baja o ultrabaja. Con ultrabaja el chat llega casi en el
    momento;
  - hecho para niños. Si lo marcas, YouTube desactiva el chat del directo;
  - permitir rebobinar el directo;
  - categoría y etiquetas;
  - miniatura, una imagen JPG o PNG de hasta 2 MB que eliges con el cuadro de
    Windows;
  - lista de reproducción de tu canal, para que el directo quede guardado en
    ella. Las listas se traen con el botón *Cargar listas*.
- Si YouTube no acepta la miniatura, la categoría, las etiquetas o la lista, el
  directo sale igual y la aplicación te dice por qué.

## 2.2.1, octubre de 2026

Arreglos para actualizar sin problemas y un paquete de instalación más liviano.

- OBS ya no bloquea las actualizaciones. El OBS que abría la aplicación usaba
  archivos de la carpeta de YTChat, y mientras siguiera abierto la actualización
  no podía reemplazarlos. Ahora OBS usa los suyos.
- Si una actualización no puede completarse porque un archivo está en uso, el
  aviso dice que puede ser OBS y que lo cierres antes de volver a intentarlo.
  Esto sirve también para pasar de la 2.2.0 a esta versión: si abriste OBS desde
  la 2.2.0, ciérralo antes de actualizar.
- El paquete baja de 175 a 147 MB. Ya no lleva documentos de otros servicios de
  Google ni una biblioteca que la aplicación no usa.

## 2.2.0, octubre de 2026

Esta versión permite empezar y terminar un directo de YouTube o de TikTok desde
la propia aplicación, sin abrir OBS ni la página de Restream. Iniciar sesión con
Google ya no exige crear credenciales propias en Google Cloud. La aplicación se
actualiza sola,
los sonidos son grabaciones nuevas y hay sonidos distintos según quién escribe y
qué pasa en el directo.

### Transmitir en directo

- El botón *Transmitir en directo* de la ventana principal abre la elección de
  destino, YouTube o TikTok, con el de la vez anterior ya seleccionado. La
  aplicación abre OBS si hace falta, sin mover el foco del lector de pantalla,
  pasa al perfil de ese destino y lee una revisión antes de salir al aire. La
  revisión cubre formato, escena, fuentes, audio y cualquier problema, como una
  escena vacía o un micrófono silenciado. Mientras se transmite, el mismo botón
  dice *Finalizar directo*.
- YouTube se configura sin tocar la página de YouTube. Una sola ventana pide el
  título, la descripción y la privacidad (público, no listado o privado), y
  muestra la revisión de OBS. Al pulsar *Transmitir*, la aplicación crea el
  directo en el canal, carga la clave en OBS, empieza a transmitir, espera a que
  YouTube lo muestre y conecta el chat sola. El título y la descripción se
  recuerdan para la próxima vez.
- TikTok se transmite a través de Restream. La aplicación usa el perfil de OBS
  llamado `TikTok`, espera a que TikTok muestre el directo y conecta el chat.
- En la ventana *Transmisión* (`Ctrl+Mayús+T`) se elige la ventana que captura la
  escena, por ejemplo un juego. Esa ventana está ordenada por secciones y sus
  campos dicen qué hacer cuando falta algo.
- `Ctrl+Mayús+E` copia el enlace del directo conectado, para pasárselo a alguien.
- `F2` dice primero en qué está el directo que supervisa la aplicación, y si
  TikTok o YouTube ya lo muestran.
- `F2` dice cómo volver al directo cuando el reproductor va por detrás: «10
  segundos por detrás del directo. Pulsa Ctrl+Fin para volver al directo.», con
  el atajo que tengas configurado.
- Un corte de internet no termina el directo de YouTube. Si OBS pierde la
  conexión, por ejemplo al cambiar de wifi, YouTube espera a que vuelva la señal
  en vez de cerrar el directo, y la aplicación avisa que OBS está reconectando.
  Al finalizar desde la aplicación o desde OBS, la aplicación cierra el directo
  en YouTube.
- El panel de chat no queda tapado. Si otra fuente de la escena queda encima del
  panel, como una captura de pantalla o de la cámara, la aplicación lo pone
  delante al salir al aire y durante el directo. También dice qué fuente lo
  tapaba.
- `Ctrl+F2` describe la escena de OBS: qué fuentes tiene, cuál está delante,
  dónde está cada una, si se ve y qué la tapa. La ventana *Transmisión* muestra
  lo mismo en su propia sección, y el estado del panel tiene su propio rótulo.
- Un directo no queda al aire sin imagen. Al abrir la aplicación, si tienes un
  directo de YouTube al aire mientras OBS no transmite, por ejemplo porque
  cerraste OBS después de cerrar la aplicación, te pregunta si finalizarlo.
- La lista de ventanas para capturar ya no trae ventanas sin título, que se leían
  como «(null)».

### Iniciar sesión con Google

- Ya no hacen falta credenciales propias. Antes había que crear un proyecto en
  Google Cloud y cargar su cliente. Ahora basta con pulsar *Iniciar sesión* en
  *Preferencias, API y sesión*: la aplicación trae su propio cliente. Google
  muestra un aviso de aplicación no verificada, que se pasa con las opciones
  avanzadas y el botón de continuar. Quien ya tenía credenciales propias las
  sigue usando.

### Actualizaciones

- La aplicación se actualiza sola. En *Ayuda, Buscar actualizaciones* una ventana
  dice si hay una versión nueva, muestra sus novedades en un cuadro que se puede
  recorrer, y la descarga e instala con un botón. La aplicación se cierra y
  vuelve a abrirse en alrededor de un minuto. Si la versión nueva no llega a
  abrirse, se vuelve sola a la anterior y lo dice al iniciar. La configuración,
  la sesión, el historial, las descargas y los sonidos que hayas cambiado se
  conservan.
- Si hay una versión nueva, se anuncia una sola vez al iniciar.
- Actualizar yt-dlp tiene ventana propia, con el estado, una barra de progreso y
  cada paso anunciado: buscando, descargando y el resultado.

### Sonidos

- Todos los sonidos son grabaciones nuevas, de dominio público, elegidas una por
  una para que se distingan entre sí. El archivo `sounds/CREDITOS.md` dice de
  dónde salió cada uno.
- Hay un sonido según quién escribe. Los mensajes del propietario del canal, de
  un moderador, de una cuenta verificada y de un miembro suenan distinto del
  mensaje común.
- Al llegar con las flechas al principio o al final de la lista del chat, de los
  comentarios o del historial, suena un golpe sordo.
- Cuando un directo de TikTok termina suena una puerta que se cierra, y no el
  sonido de desconexión.

### Directos de TikTok

- Además del chat y los regalos, se lee quién sigue el canal, quién comparte el
  directo y quién envía un cofre, cada uno con su sonido. Los corazones solo
  suenan, como mucho uno cada tres segundos, para no tapar el chat.
- Los regalos suenan según su tamaño: una moneda los chicos, varias los medianos
  y una lluvia de monedas con una melodía los grandes.
- Quien entra al directo tiene su propio sonido, una puerta que se abre, cuando
  la entrada está activada en *Preferencias, Lectura*.
- No se leen los mensajes anteriores al conectar. TikTok manda al conectar los
  últimos mensajes del directo. Ya se descartaban los de antes de la conexión, y
  ahora también los que TikTok marca como antiguos.

### Otros cambios

- `F3` dice el autor del último mensaje leído.
- La aplicación ya no se cierra sola al finalizar un directo. Lo provocaba el
  propio registro de errores, que anotaba de más.
- Los mensajes automáticos solo se mandan a tu propio directo. Antes se mandaban
  a cualquier directo de YouTube conectado con la sesión iniciada, también al de
  otro canal. Además, lo que cambias en *Preferencias* se aplica sin reiniciar,
  un mensaje nuevo nace activo y el primero no sale de golpe al conectar.
- Al recorrer los temas de sonido en *Preferencias* suena una muestra de cada
  uno, sin cambiar el tema hasta aceptar.
- Al ajustar varias veces el mismo valor se dice solo el número. La primera vez,
  por ejemplo, «Volumen de la voz: 40%», y las siguientes solo «45%», mientras
  sigas con el mismo control dentro del minuto. Al pasar a otro, como la
  velocidad, vuelve a decir el nombre. En el deslizador de volumen del
  reproductor el número ya no se oye dos veces.
- Los sonidos ya no frenan la ventana, y el reproductor tarda menos en iniciarse
  la primera vez.
- La configuración admite `%`, `#` y `;` en los textos, por ejemplo en un título
  de directo, sin que se pierdan al guardar.

## 2.1.0, octubre de 2026

Esta versión incluye un panel de chat para la transmisión, la posibilidad de
escribir en el chat desde la propia aplicación y una ventana para componer la
escena de OBS sin ver la pantalla. El reproductor responde mucho mejor, las
descargas se ordenan y avisan cuando terminan, y los datos de la aplicación pasan
a una carpeta propia.

### Reproductor

- El reproductor obedece al instante. Después de avanzar o retroceder, el
  pausar y el reproducir se perdían durante diez o veinte segundos: se anunciaba
  «pausar» tres veces seguidas y el vídeo seguía reproduciéndose. En los vídeos
  de YouTube el audio viaja por separado del vídeo, y al reproductor le llegaban
  los dos por la red: el audio frenaba todo lo demás. Ahora el audio se guarda
  antes en el disco, en la carpeta `cache-audio` dentro de la carpeta `data`, y
  las órdenes se cumplen todas. De paso, el vídeo empieza a verse en menos de un
  segundo en vez de en seis.
- Los directos ya no se congelan cada minuto y medio. El vídeo y el audio de un
  directo llegaban por separado y el reproductor perdía la sincronía entre ambos
  cada 60 o 90 segundos, quedándose parado entre 25 y 50 segundos. Ahora se
  juntan antes de reproducirse, con ffmpeg, una herramienta que viene incluida
  en la aplicación. Si ffmpeg tarda en iniciarse, el reproductor espera a que esté
  listo en vez de fallar en silencio. Si el directo se interrumpe, lo dice y
  vuelve a conectar solo, hasta dos veces.
- Avanzar y retroceder funcionan en los directos. Los botones de un minuto y
  las flechas de diez segundos no hacían nada cuando el directo llega con las
  pistas separadas. Ahora cada salto reinicia la unión de vídeo y audio unos
  segundos antes del borde del directo, con un corte de dos o tres segundos. Las
  flechas seguidas se acumulan, y cada una anuncia dónde queda: «20 segundos por
  detrás del directo», «En el directo». En los directos con pistas separadas se
  puede retroceder hasta una hora, que es lo que YouTube guarda. Mover el
  deslizador o pedir un porcentaje no está disponible en estos directos, y la
  aplicación lo dice.
- Los directos que YouTube sirve con vídeo y audio juntos también se mueven, con
  menos margen. Solo permiten retroceder unos 30 segundos. Cuando un directo no
  admite saltos, las flechas lo dicen en vez de fallar con un aviso confuso.
- Ir al directo con `Ctrl+Fin`. Después de retroceder, el menú *Reproductor* tiene
  *Ir al directo*, con `Ctrl+Fin`, que vuelve al borde de una vez. Si ya estás en
  el directo, lo dice.
- El deslizador y `F2` dicen cuánto por detrás del directo vas. Antes el
  deslizador decía «En directo» aunque se hubiera retrocedido. Ahora dice «40
  segundos por detrás del directo», y `F2` lo anuncia también cuando vas por
  detrás.
- Retroceder en un directo ya no salta dos horas atrás. El reproductor usaba una
  duración equivocada, y un retroceso de un minuto acababa al principio de la
  ventana del directo.
- Buscar con el vídeo cargando o detenido dice el motivo. Si pides un salto
  mientras el vídeo carga, se dice «Cargando vídeo» y no que no se puede
  avanzar. Con el vídeo detenido se dice «El vídeo está detenido». Vale para
  los directos y para los vídeos grabados.
- Mover el vídeo en pausa guarda el destino. Si mueves el vídeo estando en pausa,
  al reanudar sigue desde la posición nueva y no desde el principio.
- Los vídeos divididos en pistas se reproducen. Algunos vídeos grabados llegan
  con el vídeo y el audio en pistas separadas. Ahora se reproducen, y se puede
  saltar sin esperar a que termine la descarga. Si un vídeo no empieza a sonar,
  se vuelve a cargar una vez antes de avisar de que no se pudo reproducir.
- El vídeo de los directos vuelve a cargarse. YouTube dejó de ofrecer un único
  flujo con imagen y sonido juntos y la aplicación seguía esperándolo. Ahora
  junta el vídeo y el audio cuando llegan por separado, y si aun así no puede,
  deja anotado en el registro qué encontró.
- La caché de vídeo respeta su límite. Un vídeo que no cabe en el límite
  configurado ya no se descarga entero: la descarga se detiene enseguida y no
  deja archivos. La caché descarga los vídeos en 720p, y los restos de descargas
  interrumpidas se eliminan solos.
- La caché de audio ya no puede colgarse. Si la descarga del audio se queda sin
  avanzar, se interrumpe por tiempo.
- Pulsar muchas veces para avanzar ya no desfasa el reproductor. Algunas
  pulsaciones se perdían y el tiempo anunciado retrocedía solo. Y pulsar
  reproducir o pausar mientras el vídeo cargaba lo hacía empezar de cero.
- La reproducción se interrumpe menos. El colchón de red era muy pequeño y
  cualquier fluctuación de la conexión interrumpía la reproducción.

### Chat y voz

- Pausar la lectura (`F5`) pausa de verdad la frase en curso, y mientras está en
  pausa se atienden cambios de voz, velocidad y volumen.
- El primer mensaje tras reconectar ya no se interrumpe. Una orden de callar
  pendiente se aplicaba al mensaje siguiente.
- La voz configurada que ya no existe no impide iniciar la aplicación. Se usa la
  primera disponible y se anota en el registro.
- Los avisos ya no se interrumpen a la mitad, tampoco en los menús. Antes el
  texto de un aviso se perdía si se pulsaba otra tecla enseguida. Ahora se oye
  entero. Los únicos que no interrumpen son los que se repiten solos: el aviso de
  que un vídeo sigue cargando y el de que se está consultando a OBS.
- Los sonidos largos de temas personalizados ya no se interrumpen a los 5
  segundos.
- Los Super Chats en yenes, wones o rupias suman bien. «¥1,000» sumaba 1.
- Al reconectar a un directo distinto, nada del chat anterior llega al nuevo. Los
  mensajes automáticos y el cuadro de escritura ya no pueden acabar en el chat
  que se cerró, ni los comentarios del vídeo anterior en el nuevo.
- Reconectar de verdad cuenta. Con la wifi inestable, cinco microcortes
  repartidos en horas agotaban los intentos aunque cada reconexión hubiera
  funcionado. Ahora solo cuentan los errores seguidos. Los valores de fábrica son
  15 segundos entre intentos y 20 intentos, unos cinco minutos en total, y se
  cambian en *Preferencias, Conexión*.
- Avisa cuando se están perdiendo mensajes. Si entra más chat del que la voz
  puede leer, la aplicación descarta los más anteriores. Ahora lo dice una vez
  por sesión, recuerda que esos mensajes siguen escritos en la lista del chat y
  sugiere activar la lectura solo del nombre, que es lo que hace que la voz
  alcance. `F2` puede decir además cuántos van, si se activa ese dato en
  *Preferencias*.
- Hay una forma más de que te lean el chat: primero el mensaje, después quién lo
  escribió. Está en *Preferencias, Lectura*, junto a las tres que ya había. Se
  oye «hola a todos, de Lucía». Sirve cuando llegan muchos mensajes seguidos: se
  oye el contenido antes que el nombre y puede decidirse si interesa sin esperar.
- Hay alias para los nombres imposibles de escuchar. Muchos nombres de YouTube
  son cadenas de letras y números que la voz lee enteras en cada mensaje. Ahora
  puede ponérseles un nombre corto: en la lista del chat, menú contextual sobre
  un mensaje y la opción de poner alias. Desde ese momento, ese usuario se lee y
  se ve con el alias. Para eliminarlo, se abre lo mismo y se deja el campo vacío.
  El nombre real no se pierde: suspender temporalmente, ocultar, silenciar y
  responder siguen actuando sobre la cuenta de verdad.
- Los errores de la voz quedan anotados. Si el sintetizador falla al anunciar
  algo, antes no quedaba ni rastro.

### TikTok

- Los directos de TikTok vuelven a conectar. Con la versión anterior, la conexión
  se quedaba en «Conectando al directo de TikTok» sin llegar a nada. Ahora
  conecta, y si algo falla al prepararse, lo dice en vez de quedarse callada. Un
  usuario que no está en directo se informa como tal.

### YouTube

- Si la sesión de YouTube caduca, la aplicación lo dice con voz. Antes se leía el
  texto técnico de Google y la aplicación seguía creyendo que había sesión. Ahora
  avisa, borra la sesión caducada y pide volver a entrar en *Preferencias, API y
  sesión*. Si el error vino de algo que hiciste tú, ofrece abrir esa categoría.
  Los mensajes automáticos solo avisan.
- Iniciar sesión otra vez tras cerrarla vuelve a funcionar. Antes Google devolvía
  un permiso incompleto y moderar, comentar o escribir en el chat fallaba con un
  error de formato.
- Moderar actúa sobre el usuario de la fila elegida. Antes la moderación buscaba
  al usuario por el nombre visible.
- Ya se puede escribir en el chat del directo. Debajo de la lista de mensajes hay
  un cuadro de escritura con su botón *Enviar*. `Intro` envía el mensaje y
  `Mayús+Intro` inserta un salto de línea. Tras enviarlo, el cuadro se vacía y el
  foco permanece dentro, de modo que puede escribirse el siguiente sin tabular.
  Cuando falta la conexión o la sesión de Google, el cuadro y el botón siguen
  alcanzándose con el tabulador, y el motivo forma parte del nombre del botón.
- Cuando no se puede escribir en el chat, ahora dice por qué. Distingue si falta
  la clave de la API, si el vídeo no existe, si no es un directo o si el directo
  tiene el chat desactivado.
- Comentar y responder en los vídeos. En la pestaña *Comentarios*, los botones
  *Comentar en el vídeo* y *Responder* abren el mismo cuadro en una ventana.
- Publicar un comentario y responder a uno ya funcionan. No hacían nada: se
  escribía el texto, se pulsaba *Publicar*, la ventana se cerraba y no se enviaba
  ni se avisaba de nada.
- En un vídeo con los comentarios cerrados ya no deja escribir uno. Antes se
  podía redactar entero y solo al publicarlo se descubría que no se podía.
- `Intro` copia el mensaje seleccionado, y `Alt+Intro` abre el cuadro de
  escritura. Antes, en las listas del chat y de comentarios, `Intro` no hacía
  nada.
- Conectarse volvió a ser rápido. Se había vuelto lento, de veinte a treinta
  segundos en algunos equipos.
- Desconectar mientras dice «Conectando…» es posible, y cerrar la aplicación no
  espera a que termine una consulta a YouTube.
- `F2` dice cuánta gente está viendo el directo y cuánto lleva emitiendo. El
  número de espectadores estaba mal y decía cero aunque hubiera gente. Ahora es
  correcto y se actualiza solo cada minuto.
- La guía de configuración de la API está reescrita. Cada paso indica la
  ubicación exacta de la pantalla de Google Cloud correspondiente, y se explican
  los puntos en los que es fácil quedarse atascado con un lector de pantalla.

### OBS y transmisión

- Hay un panel de chat para que lo vean los espectadores. Los mensajes aparecen
  en una página con fondo transparente que puede agregarse a la transmisión, de
  modo que quien mira el directo lee el chat sin salir del vídeo. El panel se
  activa en la ventana *Transmisión*, con la casilla *Chat en el vídeo*, que se
  abre desde el menú *Transmisión, Panel de transmisión…* o con `Ctrl+Mayús+T`.
  Si queda activado al cerrar la aplicación, se activa solo al abrirla de nuevo.
- El panel de chat no repite mensajes ni muestra los anteriores. Al activarlo y
  desactivarlo rápido no se repiten mensajes, y si la aplicación se cierra deja
  de mostrar los que había recibido.
- Componer la escena sin ver la pantalla. En la ventana *Transmisión* se elige la
  escena y cualquiera de sus fuentes (el panel de chat, la cámara, la captura del
  juego). Se la lleva a cualquiera de las nueve posiciones habituales, se cambia
  su tamaño, se muestra u oculta, se bloquea para que no se mueva sin querer y se
  pone por delante de lo demás.

  Cada cambio se anuncia en voz alta con lo que hace falta saber: en qué posición
  quedó, qué tamaño tiene, qué parte de la pantalla ocupa y si se sale del borde.
  Sobre todo, se anuncia si alguna otra fuente lo está tapando y cuánto. Esa es
  justo la pregunta que no puede responderse mirando la pantalla.

  Hay además un modo de ajuste fino para mover el panel con precisión. Se activa
  con un botón y a partir de ahí las flechas mueven el panel, en pasos normales,
  grandes con `Ctrl` o de un píxel con `Mayús`. `Intro` confirma el cambio y `Esc`
  deshace lo que hayas movido. Y un botón guarda una captura de la escena, para
  poder enseñársela a alguien que vea.

  Así puede armarse una escena completa a ciegas: el juego en el centro, la
  cámara en un recuadro más pequeño en una esquina y el chat en otra.
- Transmitir, grabar y poner una escena al aire desde la misma ventana. Hay
  botones para empezar y parar la transmisión y la grabación, pausar, y poner al
  aire la escena elegida. `F2` puede decir también si OBS está transmitiendo,
  grabando o con una escena al aire, si esos datos se activan en *Preferencias,
  Estado (F2)*.
- Silenciar el micrófono de OBS con `Ctrl+Mayús+M`. La aplicación consulta y
  alterna el silencio de la fuente de micrófono que se elige en *Preferencias,
  Transmisión*.
- La casilla del panel de chat funciona aunque OBS no esté. Antes dejaba de
  responder si OBS no contestaba, aunque el panel no necesita OBS para nada.
- El servidor de OBS se activa desde aquí. En *Preferencias, Transmisión*, el
  botón *Activar servidor WebSocket de OBS* lo activa sin tener que buscarlo en
  los menús de OBS.
- Cuando OBS no se puede activar, dice por qué. Antes salía un mensaje vacío de
  contenido.
- Recorrer un desplegable ya no cambia nada. En la ventana *Transmisión*, pasar
  por las nueve posiciones con las flechas movía el panel dentro de OBS una vez
  por flecha, en directo. Ahora se elige la posición y se aplica con su botón.
- La ventana *Transmisión* explica dónde está el panel en lenguaje llano. Antes
  mezclaba tres porcentajes que medían cosas distintas. Hay un botón nuevo que
  explica en qué orden se usa la ventana.
- La ventana *Transmisión* no se queda bloqueada si la fuente elegida ha
  desaparecido en OBS o si OBS cierra la conexión: avisa y deja seguir. Aplicar tamaño sobre un panel escalado ya no lo encoge a la mitad.
- OBS: el tiempo de transmisión era mil veces mayor. Un minuto se anunciaba como
  «16 horas 40 minutos».

### Descargas

- Como mucho hay dos descargas a la vez. Antes, encolar diez descargas las
  lanzaba todas a la vez. Ahora corren dos, las demás esperan en «en cola», en el
  orden en que se pidieron, y se pueden cancelar mientras esperan.
- Cancelar ya no deja aplicaciones abiertas. Al cancelar una descarga, o al
  cerrar la aplicación, las aplicaciones que estaban bajando el archivo, incluido
  ffmpeg, se cierran con ella.
- El nombre de cada descarga es el del archivo final. Antes se anunciaba el de un
  trozo temporal. Y Enumerar ya no pone «NA - » delante de los vídeos sueltos.
- Las descargas terminadas tienen su propio historial. La cola y el historial
  están en dos pestañas del *Administrador de descargas*, y el historial se
  conserva entre sesiones. Al reabrir la ventana, el progreso de las descargas en
  curso sigue ahí.
- Las descargas avisan cuando terminan, esté abierto o cerrado el
  *Administrador de descargas*, y la cola ya no se olvida al cerrar la ventana.
- La carpeta Descargas siempre está junto a la aplicación. Antes dependía de
  desde dónde se abriera la aplicación.
- En las descargas se lee primero el progreso. Las columnas pasaron a ser
  progreso, estado y nombre, que es el orden en que interesan.

### Preferencias y atajos

- *Preferencias* se recorre con una lista de categorías, no con pestañas. Con
  lector de pantalla, las flechas anuncian cada categoría al pasar por ella. Son
  trece, repartidas por tema.
- *Preferencias* guarda de forma segura y avisa si no pudo guardar. Antes
  escribía directamente sobre el archivo de configuración y anunciaba
  «Preferencias guardadas» pasara lo que pasara. Ahora, si el disco no acepta la
  escritura, lo dice con el sonido de error: las opciones siguen aplicadas hasta
  cerrar la aplicación, pero se perderán al cerrarla.
- Los atajos se cambian en un solo paso, y se aplican al pulsar *Guardar*. Se
  activa el botón de la acción y se pulsa la combinación, sin salir de la lista.
  La ventana avisa de que el cambio se aplica al pulsar *Guardar*, y *Cancelar*
  lo descarta. `Intro` a solas deja la acción sin atajo y `Esc` cancela. Si la
  combinación no se reconoce o ya está en uso, se indica el motivo por voz y en
  un aviso en pantalla, y el botón sigue esperando otra.
- Un botón al final de la lista restablece los atajos. Devuelve todas las
  combinaciones personalizables a sus valores originales, y también se aplica al
  pulsar *Guardar*.
- Tres atajos nuevos para abrir ventanas: `Ctrl+Mayús+P` abre *Preferencias*,
  `Ctrl+Mayús+H` el *Historial de directos* y `Ctrl+Mayús+I` marca una incidencia
  en el registro.
- Nueve opciones que existían y no se podían tocar. Son el comportamiento de la
  cola de lectura cuando el chat se acelera, la reconexión automática, el puerto
  del panel de chat y el micrófono de OBS que silencia el atajo. También incluyen
  el registro detallado, que hasta ahora solo se activaba editando un archivo a
  mano.
- Los contadores numéricos se pueden reescribir sin borrar antes. Al entrar en
  uno, su contenido queda seleccionado.
- Nueva paleta clara, de tonos crema y verde salvia. La ventana principal tiene
  ahora un tamaño mínimo, y los avisos largos se ajustan al ancho en vez de
  salirse de la ventana.
- Los textos que lee el lector de pantalla llevan sus tildes. Quince estaban
  escritos sin ellas, así que se oían mal pronunciados: «maxímo» por «máximo»,
  «transmisiòn» por «transmisión».
- En *Preferencias*, la categoría *Atajos* se ve entera. Antes dos tercios de los
  botones quedaban fuera de la ventana. Ahora la ventana se puede agrandar.
- El modo de contraste alto de Windows se respeta. La aplicación dejaba de
  aplicar sus colores fijos encima del tema del sistema.

### Datos e instalación

- Los datos se mudan solos a la carpeta `data`. La configuración, las
  credenciales, el historial, los alias, los mensajes automáticos y los registros
  estaban junto a la aplicación. Al abrir la versión nueva, esos archivos se
  mueven a la carpeta `data` sin hacer nada. La carpeta Descargas sigue junto a
  la aplicación.
- Los archivos que la aplicación guarda se escriben de forma segura. Es el caso
  del historial, las credenciales, los mensajes automáticos y la configuración de
  OBS: un cierre a mitad ya no los deja vacíos.
- Se atacaron dos defectos de los cierres inesperados al salir. El reproductor
  dejaba cabos sueltos al cerrarse, que encajan con los cierres bruscos que
  aparecían en el registro. No se puede dar por curado hasta usarlo un tiempo,
  pero el registro ahora deja rastro de ese cierre en vez de callarse.
- El registro detallado viene desactivado. Es una opción de diagnóstico y estaba
  activa de fábrica, lo que hacía crecer el archivo de registro sin necesidad.
- El registro de diagnóstico dejó de llenarse de ruido. Nueve de cada diez líneas
  eran de bibliotecas internas, y con una sesión larga ese ruido borraba el
  principio del archivo, que es justo donde suele estar el problema.
- El archivo de errores ya no asusta. Recoge sucesos internos de Windows, y
  muchos son inofensivos. Ahora cada inicio escribe una línea que lo explica y
  dice cuál es la señal de que la sesión terminó bien.
- Ya no se abre una ventana negra al iniciar. Aparecía un instante y le robaba el
  foco al lector de pantalla. Ahora la consulta se hace por detrás.

## 2.0.1, agosto de 2026

Esta es una versión de arreglos y de mejoras pequeñas. No trae funciones nuevas
grandes: trae que las que ya había molesten menos y avisen mejor.

- El diagnóstico dejó de hablar solo. Cada treinta segundos anunciaba por voz
  cuántos hilos había vivos. Era información para arreglar problemas, no para
  escucharla mientras miras un directo. Ahora se sigue guardando en el registro,
  pero callado.
- Los controles del reproductor ya no se quedan mudos. Pulsar reproducir,
  silenciar o buscar sin tener un vídeo cargado no hacía absolutamente nada, ni
  siquiera decirlo. Ahora contestan «No hay ningún vídeo cargado» o «El
  reproductor no está disponible», según el caso.
- Los atajos del reproductor funcionan siempre. Estaban desactivados hasta
  conectarte a algo, así que las siete combinaciones de `Ctrl` parecían rotas.
- Avisa al pulsar reproducir. Antes había un silencio largo mientras cargaba, que
  parecía que se había bloqueado. Ahora dice «Cargando vídeo».
- Hay avisos claros cuando falla la red. Antes, si YouTube no contestaba o el
  vídeo era privado, no se oía nada. Ahora lo dice con palabras: que la red no
  responde, que el vídeo no está disponible, o que hay que esperar unos minutos
  porque se hicieron demasiadas consultas.
- Los atajos de *Preferencias* van agrupados. Los veinte botones estaban sueltos.
  Ahora el lector anuncia a qué grupo pertenece cada uno, «Reproductor» o
  «Conexión y chat».
- yt-dlp se puede actualizar desde la aplicación. Está en *Herramientas,
  Actualizar yt-dlp*. Es la pieza que deja de funcionar cuando YouTube cambia
  algo por dentro, y hasta ahora había que esperar a una versión nueva de la
  aplicación.
  Comprueba qué versión hay publicada, la compara con la instalada y la descarga
  solo si hace falta, verificando que el archivo sea el auténtico.
- Las descargas usan ese mismo yt-dlp. Antes el *Administrador de descargas*
  llevaba su propia copia por dentro, que se quedaba anterior aunque actualizaras.
  Ahora todo usa el mismo, y la versión que muestra la aplicación es la de
  verdad.
- Se arregló una fuga que dejaba el chat leyéndose dos veces por dentro. Si te
  reconectabas a otro directo sin desconectar antes, la conexión anterior seguía
  viva pidiéndole mensajes a YouTube para siempre, en silencio, hasta cerrar la
  aplicación.
- La carpeta de descargas ya no se guarda sola. Se escribía en la configuración
  una ruta del equipo donde se compiló la aplicación.
- Se eliminó una entrada de menú que ya no llevaba a ninguna parte, y los avisos
  también salen por línea braille.

## 2.0.0, julio de 2026

- Los directos de TikTok quedan fiables. La primera versión los estrenó y esta
  los deja estables: se leen todos los comentarios con su autor, se reproduce el
  vídeo del directo y `F2` muestra los espectadores en directo. Opcional: leer
  quién entra al directo, desactivado de fábrica, en *Preferencias*, categoría
  *Lectura*.
- El *Historial de directos* está en el menú *Archivo*. Guarda lo que has visto,
  en dos pestañas (YouTube y TikTok), para volver a un directo con `Intro` sin
  recordar el enlace. Los directos se marcan como tales, porque al terminar
  pueden dejar de existir.
- La búsqueda por letras en el chat y los comentarios salta al mensaje que
  empieza con lo que escribes. Escribe unas letras seguidas («mig») y salta al
  mensaje que empieza así, anunciándolo. Da la vuelta a la lista si hace falta y
  avisa si no hay coincidencias.
- Hay una segunda voz para los eventos, opcional. Los Super Chats, regalos y
  miembros nuevos pueden leerse con una voz distinta de la de los mensajes.
- Los atajos se capturan pulsándolos. En *Preferencias*, categoría *Atajos*, ya
  no se escribe la combinación a mano: pulsas el botón de la acción y luego las
  teclas, y la aplicación comprueba sola que sea válida y no choque con otra.
- El estado por voz (`F2`) se configura. Dice los datos del directo (título,
  canal, espectadores, mensajes leídos, aportes…) y en *Preferencias*, *Estado
  (F2)* se elige exactamente qué cuenta.
- El chat es más fluido con el lector de pantalla. Navegar la lista con las
  flechas mientras llegan mensajes ya no se bloquea.
- Los menús son coherentes. Las acciones que necesitan conexión se desactivan
  cuando no la hay, y desconectar es instantáneo. Antes podía congelar la ventana
  unos segundos.
- La reconexión de YouTube es más confiable. Un error de red que dejaba la
  conexión rota hasta reconectar a mano ya se recupera solo.
- El reproductor está pulido. Reanudar un directo tras pausarlo vuelve al momento
  actual, la pantalla completa lleva el título del vídeo, y en los directos se
  indica «En directo» en lugar de una barra de progreso confusa.

## 1.0.0, julio de 2026

Esta es la primera versión de la aplicación. Lee el chat de YouTube Live con
voces SAPI 5 y los comentarios
de los vídeos, con lectura, respuesta y publicación. Incluye un reproductor de
vídeo integrado con pantalla completa manejable por teclado, moderación y envío
al chat con la API oficial, una pestaña de información del vídeo y directos de
TikTok de solo lectura. La interfaz se maneja con el teclado, con anuncios por
voz y braille.

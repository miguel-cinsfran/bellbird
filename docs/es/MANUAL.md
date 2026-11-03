# Bellbird, manual de uso

Bellbird lee en voz alta el chat de los directos de YouTube y TikTok para las
personas ciegas o con baja visión que transmiten. Toda la aplicación se maneja
con el teclado y se prueba con NVDA.

Versión 3.0.0 beta 1 · Windows 10 y 11 · [novedades de cada versión](CHANGELOG.md)

## Índice

- [Qué hace](#qué-hace)
- [Instalación](#instalación)
- [Primeros pasos](#primeros-pasos)
- [El chat](#el-chat)
- [Reproductor](#reproductor)
- [Música](#música)
- [Transmitir en directo](#transmitir-en-directo)
- [Encuadre de cámara](#encuadre-de-cámara)
- [Escena](#escena)
- [Panel de chat para transmitir](#panel-de-chat-para-transmitir)
- [Mensajes automáticos](#mensajes-automáticos)
- [Descargas e historial](#descargas-e-historial)
- [Estado por voz](#estado-por-voz)
- [Preguntar a la IA](#preguntar-a-la-ia)
- [Sesión de Google](#sesión-de-google)
- [Atajos de teclado](#atajos-de-teclado)
- [Accesibilidad](#accesibilidad)
- [Actualizar](#actualizar)
- [Dónde se guardan las preferencias](#dónde-se-guardan-las-preferencias)
- [Problemas frecuentes](#problemas-frecuentes)

## Qué hace

- Lee el chat de un directo de YouTube o de TikTok con las voces de Windows
  o de ElevenLabs, con un sonido distinto para cada tipo de mensaje.
- Lee y publica comentarios en vídeos de YouTube.
- Reproduce el vídeo del directo dentro de la aplicación.
- Pone música de tu carpeta, de tus listas o de YouTube mientras transmites.
- Empieza y termina tu directo con OBS Studio y describe por voz cómo se ve
  la escena.
- Muestra el chat a tus espectadores en un panel para OBS.
- Modera, escribe en el chat y manda mensajes automáticos con tu sesión de
  Google.
- Descarga vídeo y audio.

En TikTok solo lee, porque TikTok no tiene una forma oficial de comentar ni
de moderar.

## Instalación

Descomprime el ZIP en cualquier carpeta y abre `Bellbird.exe`; no hace falta
instalar nada ni tener permisos de administrador, porque el ZIP trae todo lo
necesario.

Hace falta Windows 10 u 11, una conexión a internet y al menos una voz de
Windows, que se elige en *Configuración, Hora e idioma, Voz*; ElevenLabs es
opcional y pide una cuenta propia.

## Primeros pasos

Al abrir la aplicación, el foco está en el campo *Enlace o ID*: pega el enlace
del directo o del vídeo y pulsa `Intro`. Si ya viste otros directos, la ventana
ofrece la lista *Recientes* (`Alt+S`). `Intro` abre uno, `Supr` lo elimina del
historial y el menú contextual ofrece abrirlo, eliminarlo o abrir el historial
completo.

La ventana tiene tres regiones, *Conexión*, *Contenido* y *Reproductor*, y `F6` y
`Mayús+F6` pasan de una a otra, mientras que `Ctrl+Tab` cambia entre las pestañas
de chat, comentarios e información. Cada cambio de región o de pestaña se
anuncia. La tecla de aplicaciones
abre el menú contextual de la lista del chat o de los comentarios.

## El chat

Cada mensaje se lee con la voz elegida y suena distinto según quién escribe:
propietario del canal, moderador, cuenta verificada o miembro. También cambia
según lo que es: Super Chat, membresía o regalo de TikTok.

En TikTok también se leen los stickers y las preguntas del directo. En
*Preferencias*, categoría *Lectura*, el grupo *Eventos del directo* tiene una
lista por evento: *Super Chats y regalos*, *Membresías*, *Entradas al directo*,
*Me gusta*, *Seguidores nuevos*, *Directo compartido* y *Cofres*. Cada lista
elige entre *Voz principal*, *Voz secundaria*, *Solo sonido* y *Desactivado*.
*Voz principal* y *Voz secundaria* lo muestran en la lista, suenan y lo leen;
*Solo sonido* lo muestra y suena sin leerlo; *Desactivado* no lo muestra. De
fábrica, las entradas y los me gusta están en *Solo sonido*, y el resto en
*Voz principal*. Debajo de *Me gusta* hay un contador, *Agrupar me gusta
durante, en segundos*, que decide cuántos segundos se juntan los me gusta de
una misma persona antes de avisar el total. La voz secundaria y sus ajustes
se eligen en *Preferencias*, categoría *Voces*. Si quien transmite pone el
directo en pausa, se oye «El directo de TikTok está en pausa.», y al volver,
«El directo de TikTok continúa.», cada uno con su sonido.

En la lista, las flechas van de mensaje en mensaje y escribir unas letras
salta al primer autor que empieza así. El menú contextual copia el mensaje,
silencia al autor durante la sesión, le pone un alias y, con sesión de Google,
lo suspende temporalmente o lo oculta en el canal de YouTube.

### Formato de lectura

El formato de lectura se elige en *Preferencias*, categoría *Lectura*, y decide
qué parte de cada mensaje se lee.

| Formato | Ejemplo |
|---|---|
| Nombre y mensaje | «Lucía: hola a todos» |
| Mensaje y después el nombre | «hola a todos, de Lucía» |
| Solo el mensaje | «hola a todos» |
| Solo el nombre | «Lucía» |

Las palabras y los usuarios que no se leen se configuran en *Preferencias*,
categoría *Filtros*.

### Voces

Bellbird puede leer el chat con tres motores de voz: SAPI 5 y OneCore, que
vienen con Windows, y ElevenLabs, que necesita una cuenta. Para elegir el
motor, la voz principal, la velocidad, el volumen y el tono, abre
*Preferencias* y ve a la categoría *Voces*. El botón *Probar voz* reproduce una
muestra antes de guardar. El grupo *Voz secundaria* elige la voz de los eventos
que estén en ese modo en *Preferencias*, categoría *Lectura*: *Voz*,
*Velocidad (0 a 100)*, *Volumen (0 a 100)* y *Probar voz secundaria*. Con
*Igual que la voz principal*, la secundaria suena con la voz principal y sus
propios ajustes. Con ElevenLabs, *Voz de Windows de respaldo* elige la voz que
suena si falla la red o se acaba el saldo, y *Igual que el respaldo de la voz
principal* sigue al respaldo de la principal. También puedes poner un límite de
caracteres por sesión o usar ElevenLabs solo con los mensajes importantes. Si
falla la red o se acaba el saldo, la aplicación lee con la voz de Windows y lo
avisa una vez. La clave se guarda en `credenciales.json`.

### Alias

El alias sirve para los nombres que son una combinación de letras y números.
Abre el menú contextual de un mensaje, elige *Poner alias a <autor>…* y escribe
cómo quieres oírlo. El alias vale también para los mensajes que ya estaban, y
la moderación sigue actuando sobre la cuenta real. Para eliminarlo, deja el
campo vacío.

### Escribir en el chat

El cuadro de escritura está después de la lista en el orden de tabulación, y
`Alt+Intro` lleva el foco hasta él desde cualquier parte. `Intro` envía el mensaje
y `Mayús+Intro` inserta un salto de línea. Si falta algo para poder escribir,
como la sesión de Google o un directo de YouTube con chat, el botón *Enviar*
sigue al alcance del tabulador y su nombre dice qué falta. El límite es de 200
caracteres.

### Sonidos

Hay un sonido para cada cosa: mensajes, Super Chats, miembros, regalos de
TikTok por tamaño, seguidores, entradas, la conexión, los errores y el borde
al llegar al principio o al final de una lista. `F7` los silencia todos. Para
silenciar uno solo, desactiva su casilla en *Preferencias*, categoría *Sonidos*,
donde *Reproducir sonido elegido* reproduce cada uno. El tema de sonido se elige
en la misma categoría, antes de la lista de casillas: *Predeterminado*, con
sonidos grabados, o *Suave*, más cortos y tenues. Para hacer uno propio, copia
`sounds/themes/default` con otro nombre y cambia los archivos `.wav`, y
`sounds/CREDITOS.md` dice de dónde sale cada sonido.

### Comentarios de vídeos

Con un vídeo ya publicado, la pestaña de comentarios muestra los comentarios y
los lee. Con sesión de Google puedes comentar y responder.

## Reproductor

El vídeo del directo se reproduce dentro de la aplicación, con libVLC. La
calidad se elige en el menú *Reproductor*, y los botones en pantalla se ocultan
desde ese menú o desde *Preferencias*, categoría *Reproductor*.

En un directo, los saltos de un minuto se acumulan y dicen dónde quedas, por
ejemplo «40 segundos por detrás del directo». Con las pistas separadas de
YouTube se puede retroceder hasta una hora, y `Ctrl+Fin` vuelve al directo. En
un vídeo, las flechas del deslizador de posición mueven diez segundos.

La casilla *Reproducir solo el audio, sin imagen*, en *Preferencias*, categoría
*Reproductor*, viene marcada. Con ella, un vídeo grabado abre un solo enlace y
salta en menos de un segundo, y la calidad no se usa. Si la pista de audio
pasa de 10 MB, ese enlace tiene algo menos de calidad de sonido. Desmarcada,
se ve la imagen y cada salto tarda unos segundos. En un directo no cambia la
forma de conectar: solo deja de mostrarse la imagen.

Un directo de TikTok no se puede pausar: al pulsar reproducir o pausar, la
aplicación lo dice y nombra el atajo de Silenciar, `Ctrl+M`, que lo silencia sin
interrumpirlo.

El audio de cada vídeo de YouTube se guarda en `data/cache-audio`, para que
pausar y saltar respondan al instante, y se conservan los tres últimos.

## Música

Para poner música mientras transmites, sin abrir otra aplicación, usa la
carpeta Música que está junto a la aplicación, o la que elijas en *Preferencias*,
categoría *Música*. La música se maneja desde el menú *Música* o con los atajos de
`Ctrl+Alt` (ver la [tabla](#música-1)).

La ventana *Música* (`Ctrl+Mayús+M`):

- *Colecciones*: *Biblioteca* es tu carpeta y, a continuación, están tus listas,
  cada una con cuántas canciones tiene («Biblioteca: 195»).
- *Buscar*: filtra mientras escribes, aunque no pongas las tildes.
- *Canciones*: `Intro` reproduce. El menú contextual reproduce ahora, a
  continuación de la canción actual y sin interrumpirla, o reproduce desde ahí
  hasta el final. También la agrega a la cola o a una lista, o crea una lista
  nueva.
- *Mostrar cola*: muestra lo que va a sonar, en orden.
- *Abrir enlace…*: abre un vídeo o una lista entera de YouTube, que se suma a
  la cola.
- *Actualizar carpeta*: la recorre de nuevo y dice cuántas canciones nuevas y
  eliminadas encontró.

Las canciones nuevas aparecen solas en la lista, sin volver a elegir la
carpeta: la aplicación vigila la carpeta y la actualiza sin avisar.

Las listas se guardan como archivos `.m3u8`, que abren otros reproductores. Al
reabrir la aplicación, Reproducir sigue la última cola desde donde estaba y
dice cuántas canciones tiene, que pueden no ser la carpeta entera si fue una
búsqueda. Para empezar siempre con toda la carpeta, desactiva Recordar última
lista al abrir en *Preferencias*, categoría *Música*.

En *Preferencias*, categoría *Música*, también eliges el orden aleatorio, la
repetición (nada, toda la cola o la canción actual), el volumen de la música y
la salida de audio. Para elegir qué se dice al pasar de canción, tienes nada,
el título, el título y el artista, o solo el artista. Si eliges nada, pasar de
canción con el atajo igual dice el título. Otra casilla decide si se anuncian
la pausa, la reanudación y el volver al comienzo.

La casilla *Igualar volumen de las canciones*, activada de fábrica, hace que
todas suenen parecido, como en Spotify. Cada archivo se mide una sola vez con
ffmpeg y su volumen se corrige al empezar cada canción. Los archivos no se
modifican: solo se guarda el resultado en una caché. La aplicación nunca mide
por su cuenta, ni al leer la carpeta, ni al guardar las preferencias, ni al
reproducir con un atajo.

Al abrir la ventana *Música*, si quedan canciones sin medir, la aplicación
pregunta cuántas son y cuánto ocupan, con *Sí* y *No*. La casilla
*No volver a preguntar* deja guardado que no pregunte más, y la pregunta se
activa o se desactiva en *Preferencias*, categoría *Música*. La ventana trae el
botón *Igualar volumen*, que empieza la medición; mientras mide, el botón cambia
a *Detener la igualación*. El avance se ve en la ventana o con `F2`, y los
enlaces de YouTube suenan con su volumen.

Al pasar de una canción a la siguiente, el final de una se funde con el
principio de la otra, sin el silencio que muchos archivos traen al principio y
al final. La longitud del fundido se elige en *Preferencias*, categoría *Música*,
en *Fundido entre canciones, en segundos*: de 0 a 12, con 6 de fábrica, y 0 lo
desactiva. Pasar de canción con el atajo hace un fundido corto, de medio
segundo. El sonido de cambio de canción viene desactivado de fábrica y se
activa en la misma categoría.

La casilla *Usar atajos de música en cualquier aplicación* hace que los atajos
funcionen aunque estés en OBS o en un juego. Viene desactivada porque, mientras
está activa, esas teclas no llegan a las demás aplicaciones. Si otra aplicación
ya tiene alguna, la aplicación te dice cuál.

NVDA usa `Ctrl+Alt+flechas` para moverse por las tablas. Donde cree que hay una
tabla, como el escritorio o el Explorador de archivos, NVDA se queda con esas
teclas y la música no las recibe. En ese caso, pulsa `NVDA+F2` y después el
atajo, y NVDA deja pasar la tecla siguiente. En una ventana sin tablas, como
el Bloc de notas, los atajos funcionan sin eso.

## Transmitir en directo

Con OBS Studio, el directo se inicia y se termina desde la aplicación: a
YouTube con tu cuenta de Google, y a TikTok por Restream.

### Antes de transmitir por primera vez

Antes de transmitir por primera vez, activa el servidor WebSocket de OBS desde
*Preferencias*, categoría *Transmisión*. Si OBS está cerrado, la aplicación lo abre
en el área de notificación sin mover el foco del lector de pantalla.

Para TikTok necesitas un perfil de OBS llamado `TikTok` con Restream, y para
YouTube, la sesión de Google iniciada y los directos activados en tu canal; el
perfil `YouTube` de OBS lo crea la aplicación.

En el *Panel de transmisión* (`Ctrl+Mayús+T`), pulsa *Organizar escena…* y elige qué
ventana se captura, por ejemplo un juego. En el directo se ve esa ventana, pero
su captura no lleva sonido: el sonido sale del audio del escritorio y del
micrófono de OBS.

### Para transmitir en directo

Para transmitir, pulsa *Transmitir en directo*, junto a *Conectar*.

1. Elige el destino. El de la vez anterior ya está elegido, así que basta con
   pulsar `Intro`.
2. La aplicación prepara OBS y revisa la escena: destino, formato, fuentes,
   audio y si hay algo mal, como una escena vacía, una imagen en negro o el
   micrófono silenciado. Si encuentra problemas, el botón elegido de entrada
   es *Cancelar*.
3. Para YouTube, en la misma ventana escribes el título, la descripción, la
   privacidad y, si quieres, la latencia, la categoría, las etiquetas, la
   miniatura y la lista de reproducción. La aplicación recuerda todo.
   *No listado* sirve para probar.
4. Cuando se inicia el directo, la aplicación conecta el chat sola y lo
   anuncia: «Tu directo de YouTube ya está en curso».
5. Durante el directo, la aplicación avisa si la conexión falla. Si se pierde
   la conexión a internet, YouTube espera a que vuelva sin terminar el directo.

El botón pasa a *Finalizar directo*, que pide confirmación con
*Seguir transmitiendo* elegido de entrada. Cerrar la aplicación no interrumpe el
directo: al volver, la aplicación lo reconoce, y `Alt+Mayús+E` copia el enlace
del directo.

`Alt+Mayús+M` silencia o activa el micrófono de OBS. Al activarlo, la aplicación
dice qué dispositivo usa, por ejemplo «Micrófono activado: predeterminado de
Windows, WO Mic Device». Si OBS usa el predeterminado, el micrófono es el que
Windows tenga elegido en ese momento y puede no ser el que esperas. Para que no
cambie, elige el dispositivo en las propiedades de la fuente de micrófono en
OBS. Después de activarlo, la aplicación escucha tres segundos. Si no entra
ningún sonido, suena un aviso propio y dice «El micrófono no recibe sonido.
Revisa cuál está elegido en Windows o en OBS.».

`Ctrl+Mayús+O`, o *Mostrar OBS* en el menú *Transmisión*, trae al frente la ventana
de OBS, también cuando está en el área de notificación. Si OBS espera una
respuesta, como la pregunta del modo seguro, el foco va a ese cuadro.

### Grabar el directo

Con *Grabar también al transmitir* marcada, en el menú *Transmisión*, OBS empieza a
grabar cuando la transmisión empieza bien y deja de grabar cuando la
transmisión se detiene. El archivo queda en la carpeta de grabaciones de OBS.
Si ya estabas grabando, esa grabación sigue como estaba, y cerrar la aplicación
no interrumpe ninguna de las dos. Si la grabación no se puede iniciar, la
transmisión sigue y suena un aviso propio con «La transmisión empezó, pero no
se pudo iniciar la grabación.». Si el perfil de OBS graba con un codificador
propio, la revisión antes de transmitir lo avisa al final, porque grabar así
carga el doble el equipo. En ese caso, para que cargue menos, elige en OBS que
la grabación use la misma calidad que la transmisión, y la casilla viene
desmarcada.

Iniciar, pausar, reanudar y detener la grabación tienen sonidos propios. Con
*Mostrar en el título de la ventana si se transmite o se graba*, en *Preferencias*,
categoría *Transmisión*, el título empieza por ese estado, y la casilla viene
desmarcada.

También se puede grabar sin abrir el panel. Para iniciar o detener la
grabación, usa *Iniciar o detener grabación* en el menú *Transmisión* con
`Alt+Mayús+G`. Para pausar o reanudar, usa *Pausar o reanudar grabación* con
`Alt+Mayús+P`, que anuncian y suenan igual que los botones del panel. Si no hay
una grabación en curso, pausar lo dice y no cambia nada en OBS. Si OBS no pausa
la grabación, la aplicación lo dice: algunos perfiles pueden no permitirlo.

Al detener la grabación, desde la aplicación o porque terminó la transmisión,
se oye «Grabación guardada» con el nombre del archivo. *Grabaciones guardadas…*,
en el menú *Transmisión* y en el panel, lista lo grabado así, de lo más nuevo a
lo más antiguo. Desde ahí puedes abrir el archivo con `Intro`, abrir su carpeta,
copiar la ruta o eliminarlo de la lista con `Supr`. Eliminar de la lista no borra
el archivo, y lo que se detiene desde la ventana de OBS no aparece en la lista.

### El panel de transmisión

El campo *Estado* dice si está todo preparado o qué revisar, la escena actual, el
micrófono y la grabación. Desde el panel se inicia y se finaliza el directo por
el mismo camino que el botón de la ventana principal. También se graba, se
silencia o se elige el micrófono y se cambia la escena actual. Solo aparece lo
que sirve en ese momento: *Usuario de TikTok* con TikTok,
*Mostrar chat en el vídeo* con YouTube y *Pausar grabación* mientras se graba, y
`Intro` nunca inicia ni finaliza un directo.

### Organizar escena

La ventana *Organizar escena* se abre desde el panel y permite ajustar las
fuentes de la escena. El campo *Descripción de la escena* dice cada fuente, dónde
está, qué tamaño tiene y si algo la tapa, y lo mismo se oye con `Ctrl+F2`. Aquí
puedes elegir qué ventana se captura y mover una fuente a una de las nueve
posiciones, por ejemplo Centro, o cambiarle el tamaño. También puedes ocultarla,
bloquearla, traerla al frente, moverla con flechas, guardar una imagen de la
escena para que la vea alguien y deshacer todo lo hecho desde que abriste la
ventana. Elegir otra escena no cambia lo que ven los espectadores. Cada cambio
dice dónde quedó la fuente, cuánto se recorta si sale del vídeo y qué la tapa, y
el botón *Ayuda* explica cada control.

Todo se puede seguir haciendo a mano en OBS, y la aplicación no interrumpe el
complemento de OBS para NVDA.

## Encuadre de cámara

Si en la escena actual de OBS hay una cámara, la aplicación dice cómo se te ve
en ella. Informa cuántos rostros hay, si estás centrado, lejos, fuera del borde
superior o inferior, de lado o con la cabeza inclinada, si falta luz delante o
hay contraluz, y si la imagen se congeló. Sirve cualquier cámara que OBS
muestre: webcam, capturadora o el teléfono usado como cámara. La imagen se
analiza en el equipo y no se envía a ningún sitio.

Izquierda y derecha se dicen como el movimiento que tienes que hacer, por
ejemplo «Muévete a tu izquierda.», no como el lado de la imagen.

### Anunciar el encuadre a pedido

Para conocer el encuadre en un momento dado, pulsa `Ctrl+F3` o elige
*Anunciar encuadre de cámara* en el menú *Transmisión*.

### Avisos automáticos

La casilla *Avisar si el rostro sale del encuadre*, en el menú *Transmisión*, o
`Ctrl+Mayús+F3`, activa los avisos. Con los avisos activos, la aplicación avisa
con un sonido propio cuando el rostro sale del encuadre y con otro cuando
vuelve, y no dice nada mientras sigue bien. Si no hay cámara en OBS u OBS está
cerrado, espera sin hacer nada. La casilla se recuerda al volver a abrir la
aplicación, y con los avisos activos, `F2` dice también el estado de la cámara.

### Guía con pitidos

Pulsa `Ctrl+F3` dos veces seguidas. La aplicación pausa la lectura del chat y
emite pitidos que suenan del lado hacia el que tienes que moverte, cada vez más
a ese lado cuanto más lejos estás del centro. La nota sube o baja de forma
continua según la altura de los ojos: más aguda si tienes que subir y más grave
si tienes que bajar. Los pitidos se repiten más seguidos cuanto más cerca
estás, entre 0,08 y 0,6 segundos. Cuando el rostro queda en el centro, suena un
tono seguido; al salir vuelven los pitidos. A los 1,5 segundos seguidos en el
centro, suena una confirmación, se dice el encuadre y la lectura sigue.
`Ctrl+F3` detiene la guía, que también termina sola al minuto.

El timbre de los pitidos se elige en *Preferencias*, categoría *Cámara*, con la
lista *Sonido de la guía*: *Normal*, *Cálido* u *8 bits*. Al elegir uno suena
una muestra con ese timbre.

Si hay más de una cámara en la escena, se usa la que está delante. La cámara se
elige en *Preferencias*, categoría *Cámara*, con *Buscar cámaras en OBS*, sin
escribir nada en `config.ini`. Si las indicaciones de izquierda y derecha salen
al revés, marca *Invertir izquierda y derecha*. El sonido de la guía se elige
en la lista *Sonido de la guía*. Los avisos se activan desde la misma
categoría.

Si OBS no tiene ninguna cámara, *Preferencias*, categoría *Cámara*, la agrega
con *Agregar cámara a OBS…*: usa una cámara de Windows y la deja abajo a la
derecha del vídeo, delante de las demás fuentes. Para moverla, usa *Organizar
escena…* en el *Panel de transmisión*.

## Escena

La ventana *Escena* (`Ctrl+Mayús+E`), en el menú *Transmisión*, reúne lo que se
ve y se oye en OBS en cuatro pestañas.

*Escena* elige qué escena se edita y dice qué tiene. Recorrer la lista no
cambia lo que se emite. *Cambiar escena* cambia la escena que se emite y
*Guardar imagen…* guarda una imagen de ella.

*Fuentes* elige una fuente de la escena y la mueve a una de las nueve
posiciones, la cambia de tamaño, la oculta, la bloquea o cambia su capa: la
trae al frente, la trae adelante, la envía atrás o la envía al fondo.
*Mover con flechas* la mueve en pasos pequeños: `Ctrl` da pasos grandes,
`Mayús` pasos de un píxel, `Intro` confirma y `Esc` deshace. El campo *Detalle
de la fuente*, junto a la lista, dice dónde está, cuánto mide y qué la tapa.
*Deshacer cambios* vuelve a como estaba todo al abrir la ventana.

*Agregar* captura una ventana del equipo o agrega una cámara de Windows a la
escena actual. *Audio* silencia el micrófono de OBS y elige cuál se usa. Al
terminar, las listas de fuentes y la descripción se actualizan solas.

Si OBS está cerrado, la ventana lo abre. Si no responde, lo dice en la
descripción y no se queda congelada. La ayuda de la ventana explica cada
pestaña.

## Panel de chat para transmitir

Muestra el chat en grande, con fondo transparente, para tus espectadores. Se
agrega en OBS (o Streamlabs, o Prism Live Studio) como fuente de navegador con
este enlace:

    http://127.0.0.1:8730/chat

Se activa con *Mostrar chat en el vídeo*, en el *Panel de transmisión*, y si la
escena actual no tiene la fuente, la agrega. Cada mensaje sale en una tarjeta
con la inicial y un color por persona, y las donaciones en dorado con el
importe. Solo se usa con YouTube: TikTok ya muestra los comentarios sobre el
vídeo.

Lo que no cabe en el vídeo no se emite, y una fuente que queda en parte fuera
se recorta sin aviso. OBS llama lienzo a ese rectángulo, y por eso
*Organizar escena* dice cuánto se recorta. Si otra fuente tapa el panel, la aplicación lo
pone delante al estar en la escena actual y te dice cuál lo tapaba. `F2` dice si el panel
está activo y si OBS lo está mostrando, y el servidor solo escucha en tu
equipo.

## Mensajes automáticos

Mandan mensajes al chat cada cierto tiempo, por ejemplo tus redes cada diez
minutos. Se configuran en *Preferencias*, categoría *Mensajes automáticos*: cada
uno con su texto, su intervalo (fijo o variable dentro de un rango, desde cinco
minutos) y una casilla para dejarlo preparado sin enviarlo.

Solo funcionan en tu propio directo de YouTube y con sesión de Google. El
primero sale después del intervalo, no al conectar, y enviar no se anuncia,
porque el mensaje ya se lee en el chat. `F2` dice cuánto falta para el próximo,
y YouTube suele bloquear los enlaces, así que es mejor el nombre de usuario que
el enlace. Si YouTube devuelve un error, los mensajes se detienen y se avisa
una vez, sin reintentar.

## Descargas e historial

### Administrador de descargas

El *Administrador de descargas* (`Ctrl+Mayús+D`) descarga vídeos, audio o listas
enteras, en MP4, WebM, MP3 o M4A, con el audio a 192, 256 o 320 kbps. Baja dos
a la vez, pone las demás en cola y guarda el historial de lo descargado. La
carpeta Descargas está junto a la aplicación, y yt-dlp se actualiza desde
*Herramientas*, *Actualizar yt-dlp*. El canal de esa actualización se elige en
*Preferencias*, categoría *Descargas*: *Estable*, el de fábrica, o *Diario*, con los
arreglos antes y más riesgo de errores.

`Intro` sobre una descarga terminada abre el archivo. Con
*Preguntar si se abre la carpeta al terminar la cola*, en *Preferencias*,
categoría *Descargas*, la aplicación hace una sola pregunta cuando termina toda
la cola, si algo se descargó bien. Viene desmarcada, porque la pregunta se lleva el foco.

Con *Anunciar progreso de las descargas*, en la misma categoría, la aplicación
dice el avance de cada descarga cada 10 por ciento, con un sonido propio. Si
una descarga sigue en cero, dice «Descarga en curso» cada 15 segundos, con
otro sonido. Con más de una descarga a la vez, el aviso empieza por el nombre
del vídeo. Viene desmarcada.

En el buscador, Espacio pone el resultado a sonar en la música sin descargarlo:
interrumpe solo la canción actual y queda en la cola como una más, y otra vez
Espacio lo pausa.

### Historial de directos

El *Historial de directos* (`Ctrl+Mayús+H`) muestra lo que viste, con una pestaña
para YouTube y otra para TikTok, y los directos terminados salen marcados.

## Estado por voz

`F2` resume la situación: conexión, título, canal, espectadores, cuánto lleva en
curso, mensajes leídos, donaciones, el panel de chat y los mensajes automáticos.
Qué entra en el resumen se elige en *Preferencias*, categoría *Estado (F2)*,
incluidos los datos de OBS y la canción que suena. Mientras transmites desde la
aplicación, `F2` empieza por cómo va el directo. Con la sesión de YouTube
iniciada, también dice cuántas unidades de la cuota diaria se usaron hoy desde
este equipo. El número es aproximado y se reinicia a medianoche, hora del
Pacífico, cuando Google repone la cuota. Como la cuota se comparte entre
quienes usan la aplicación, sirve para saber si un error de cuota viene de tu
uso o del de otros.

Si pulsas `F2` dos veces seguidas, antes de medio segundo, se abre la ventana
*Estado de la sesión* con una lista: cada parte del estado en una línea,
incluidas las que no entran en el resumen hablado. Recórrela con las flechas y
ciérrala con `Esc` o con *Cerrar*.

`F3` dice quién mandó el último mensaje leído, y `Ctrl+F2` describe la escena de
OBS.

## Preguntar a la IA

Una inteligencia artificial mira una captura de OBS y te dice qué se ve: si la
cámara está activa, si una fuente salió en negro o qué texto hay en pantalla.
Hace falta OBS abierto y la clave de un proveedor.

### Configurar la inteligencia artificial

En *Preferencias*, categoría *Inteligencia artificial*, eliges el proveedor (Google
Gemini, OpenAI, Anthropic, OpenRouter, OpenCode Go, Command Code u otro
compatible con OpenAI), guardas su clave y eliges el modelo. La clave queda en
el Administrador de credenciales de Windows, no en `config.ini`, y la categoría
nunca la muestra: solo dice que está guardada y sus cuatro últimos caracteres.
El botón *Comprobar clave* manda un pedido corto y dice si funciona.

El botón *Actualizar lista de modelos* trae los modelos que aceptan imágenes. Con
OpenRouter y OpenCode Go, la casilla *Solo gratuitos* deja los que no cobran. Con
Gemini, lo gratis depende de la clave, así que la lista prueba cada modelo con
la tuya y marca los que funcionan. Tarda unos 30 segundos y suena un aviso
mientras tanto.

En la misma categoría se cambia la instrucción que acompaña a cada captura, la
longitud de la respuesta, el tiempo de espera y si se dice «Analizando…»
mientras espera.

### La ventana de Preguntar a la IA

`Ctrl+Mayús+I` abre la ventana, donde el botón *Agregar captura* deja elegir la
escena actual o una fuente suelta. En el campo *Mensaje* escribes la pregunta y
`Intro` la envía. Justo después de agregar una captura puedes dejarlo vacío, y se
usa la instrucción. La respuesta se lee al llegar y queda en *Conversación*,
donde `Intro` abre cada mensaje entero. Puedes seguir preguntando sobre la misma
captura o agregar otra. `Esc` cancela la consulta en curso y, si no hay ninguna,
cierra.

### Consulta rápida

`Ctrl+Mayús+F2` captura la escena actual, la envía con la instrucción y lee la
respuesta sin abrir nada. El siguiente `Ctrl+Mayús+I` abre la ventana con esa
conversación, para seguir preguntando.

### Privacidad

La captura y lo que escribas salen de tu equipo hacia el proveedor. El primer
envío lo avisa y pide confirmación una sola vez. Algunos modelos usan lo que
reciben para entrenar, y la lista lo dice al lado del nombre.

Si la captura está en negro, no se envía, y ocurre con la cortina de pantalla
de NVDA o en un equipo sin monitor conectado. En OBS, cambia el método de
captura de esa fuente a Windows 10.

## Sesión de Google

La sesión de Google hace falta para moderar, escribir en el chat, comentar
vídeos y crear el directo de YouTube. En *Preferencias*, categoría *API y sesión*,
pulsa *Iniciar sesión* y autoriza en el navegador, sin crear nada en Google
Cloud. Mientras Google no termine de verificar la aplicación, muestra un aviso
de aplicación no verificada: abre la opción avanzada y elige continuar.

La cuota diaria de YouTube se comparte entre quienes usan la aplicación. Para
tener la tuya, sigue [la guía de configuración de la API](../CONFIGURACION_API.md),
escrita para leerse con lector de pantalla. Sin sesión, todo lo demás funciona
igual.

## Atajos de teclado

Cada familia de teclas es un área, y se respeta también al personalizar los
atajos. Todos figuran además en la barra de menú, junto a su acción.

### Reproductor (Ctrl)

| Atajo | Acción |
|---|---|
| `Ctrl+P` | Reproducir o pausar |
| `Ctrl+Flecha izquierda` / `derecha` | Retroceder o avanzar 1 minuto |
| `Ctrl+Flecha arriba` / `abajo` | Subir o bajar volumen del reproductor |
| `Ctrl+Fin` | Ir al directo |
| `Ctrl+D` | Detener vídeo |
| `Ctrl+M` | Silenciar o activar audio |
| `Ctrl+F` | Pantalla completa |

### Chat (Alt)

| Atajo | Acción |
|---|---|
| `Alt+Intro` | Ir al cuadro de escritura |

### Ventanas (Ctrl+Mayús)

| Atajo | Acción |
|---|---|
| `Ctrl+Mayús+P` | Abrir Preferencias |
| `Ctrl+Mayús+H` | Abrir el historial de directos |
| `Ctrl+Mayús+T` | Abrir Transmisión |
| `Ctrl+Mayús+R` | Abrir Restream |
| `Ctrl+Mayús+E` | Abrir Escena |
| `Ctrl+Mayús+D` | Abrir Administrador de descargas |
| `Ctrl+Mayús+M` | Abrir la ventana de música |
| `Ctrl+Mayús+I` | Preguntar a la IA sobre la imagen |
| `Ctrl+Mayús+O` | Mostrar OBS |

### Directo y OBS (Alt+Mayús)

| Atajo | Acción |
|---|---|
| `Alt+Mayús+C` | Conectar |
| `Alt+Mayús+D` | Desconectar |
| `Alt+Mayús+L` | Ir a la lista del panel actual |
| `Alt+Mayús+E` | Copiar enlace del directo |
| `Alt+Mayús+I` | Marcar incidencia |
| `Alt+Mayús+M` | Silenciar el micrófono de OBS |
| `Alt+Mayús+G` | Iniciar o detener la grabación |
| `Alt+Mayús+P` | Pausar o reanudar la grabación |
| `Alt+Mayús+A` | Activar o desactivar los avisos de sobrecarga |

### Voz y lectura (teclas F)

| Atajo | Acción |
|---|---|
| `F5` | Pausar o reanudar lectura |
| `F8` | Detener voz actual |
| `F9` / `F10` | Bajar o subir velocidad de la voz |
| `F11` / `F12` | Bajar o subir volumen de la voz |
| `F4` | Silenciar lectura |
| `F7` | Silenciar sonidos |
| `F2` | Anunciar estado. Dos veces seguidas, abrir la lista |
| `F3` | Anunciar autor del último mensaje |
| `Ctrl+F2` | Describir escena de OBS |
| `Ctrl+Mayús+F2` | Preguntar a la IA sobre la escena |
| `Ctrl+F3` | Anunciar encuadre de cámara |
| `Ctrl+Mayús+F3` | Avisar si el rostro sale del encuadre |

Al repetir un ajuste de velocidad o de volumen, la primera vez se dice el
nombre y el valor («Volumen de la voz: 40%») y después solo el valor.

### Música (Ctrl+Alt)

| Atajo | Acción |
|---|---|
| `Ctrl+Alt+Espacio` | Reproducir o pausar la música |
| `Ctrl+Alt+Flecha derecha` / `izquierda` | Siguiente canción o canción anterior |
| `Ctrl+Alt+Flecha arriba` / `abajo` | Subir o bajar el volumen de la música |
| `Ctrl+Alt+Mayús+Flecha derecha` / `izquierda` | Avanzar o retroceder la música 10 segundos |
| `Ctrl+Alt+T` | Anunciar canción actual |
| `Ctrl+Alt+M` | Silenciar o activar el audio de la música |
| `Ctrl+Alt+D` | Detener música |
| `Ctrl+Alt+A` | Orden aleatorio de la música |
| `Ctrl+Alt+R` | Cambiar la repetición de la música |

### Fijos

| Atajo | Acción |
|---|---|
| `F6` / `Mayús+F6` | Región siguiente o anterior |
| `Ctrl+Tab` | Cambiar de pestaña |
| `Alt+F4` | Salir de la aplicación |

### Mensajes recientes del chat (Ctrl+Mayús y número)

`Ctrl+Mayús+1` lee el último mensaje del chat, `Ctrl+Mayús+2` el anterior y así
hasta `Ctrl+Mayús+0`, que lee el décimo desde el final. De fábrica, estos atajos
valen solo con la aplicación al frente; la casilla
*Leer mensajes recientes en cualquier aplicación* de *Preferencias*, categoría
*Lectura* los hace valer en cualquier aplicación, como los atajos de música.

En la misma categoría, *Leer los mensajes recientes con* elige quién los lee: el
lector de pantalla, como viene de fábrica, o la voz de la aplicación. Con la
voz, el mensaje pedido suena en cuanto termina lo que se está leyendo, y
después siguen los mensajes que esperaban, en su orden.

Si otra aplicación ya usa alguna de estas combinaciones, o las de música, suena
un tono de ocupado y la aplicación dice cuáles.

### Cambiar un atajo

En *Preferencias*, categoría *Atajos*, cada acción tiene un botón cuyo nombre
incluye su atajo. Actívalo y pulsa la combinación nueva: `Intro` solo deja la
acción sin atajo y `Esc` cancela. Si la combinación no sirve para esa área o ya
está usada, se dice por qué y el botón sigue esperando. Al capturar un `Ctrl+Alt`
con letra, la aplicación revisa si en tu teclado `AltGr` con esa tecla escribe
algo, como la arroba, y en ese caso te pide otra. El botón
*Restablecer atajos de fábrica* vuelve todo a fábrica, y nada se guarda hasta
pulsar *Guardar*.

## Accesibilidad

La accesibilidad es el criterio principal del proyecto.

- Cada control tiene nombre accesible y se alcanza con Tab o con flechas.
- La barra de menú es la nativa de Windows.
- Lo que la aplicación avisa por su cuenta va por voz, por braille y con un
  sonido propio.
- Se prueba con NVDA en Windows 10 y 11.

El panel de chat para transmitir es la única parte que no recibe foco, porque
es para los espectadores, y el chat accesible es la lista de la ventana
principal.

## Actualizar

El comando *Ayuda*, *Buscar actualizaciones* dice si hay una versión nueva, muestra
sus novedades y la instala. La descarga se comprueba con su firma, y la
aplicación se cierra y vuelve a abrirse sola en alrededor de un minuto. Se
conservan la carpeta `data`, las descargas y tus sonidos, y si la versión nueva
no abre, vuelve sola a la anterior. Al iniciarse, una versión nueva se anuncia
una sola vez. Si entre la versión instalada y la nueva hay otras, la ventana
muestra las novedades de todas, de la más nueva a la más antigua, cada una con
su encabezado.

En *Preferencias*, categoría *General*, *Canal de actualización* elige qué versiones
se ofrecen. *Estable*, la opción de fábrica, ofrece solo versiones estables, y
*Beta* ofrece también las versiones de prueba, que pueden traer defectos.

## Dónde se guardan las preferencias

Casi todo está en *Preferencias*, en el menú *Herramientas*, y se guarda al pulsar
*Guardar*, mientras que *Cancelar* lo descarta. Las preferencias viven en
`data/config.ini` y `data/sounds.ini`, que se pueden editar con el Bloc de
notas y se regeneran si se borran.

## Problemas frecuentes

### No hay voces

Agrega una voz en *Configuración, Hora e idioma, Voz*, o prueba el motor OneCore
en *Preferencias*, categoría *Voces*. Las voces neurales de Windows 11 no salen en
SAPI 5: *TTSVoicePatcher* las expone.

### «Windows protegió tu PC»

Este aviso es SmartScreen, porque el ejecutable no está firmado, así que elige
*Más información, Ejecutar de todos modos*.

### El antivirus avisa

Es un falso positivo común con las aplicaciones que se distribuyen así, sin
instalador, así que agrega la carpeta a las exclusiones.

### El panel de chat no se ve

`F2` dice si el panel está activo y si OBS lo muestra. Si nadie lo muestra,
revisa la fuente de navegador en OBS.

### Si algo no funciona

El comando *Ayuda*, *Abrir carpeta de registros* abre la carpeta `data`, donde
están los registros. Los errores quedan en `data/bellbird.log`, y si la
aplicación se cierra sola, también en `data/bellbird-fallos.log`. El registro
detallado, `data/bellbird-debug.log`, viene activado; se desactiva en
*Preferencias*, categoría *General*, con la casilla
*Guardar un registro detallado para diagnosticar errores*. Para avisar de un
error, reproduce el problema y manda los tres archivos.

## Licencia

Bellbird usa la licencia GPL-3.0 desde la versión 2.5.1, y puedes consultar
[LICENSE](../../LICENSE). Las versiones hasta la 2.5.0 se publicaron con
licencia MIT.

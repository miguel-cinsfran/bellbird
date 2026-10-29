# Bellbird, manual de uso

Lee en voz alta el chat de los directos de YouTube y TikTok, para personas
ciegas o con baja visión que transmiten. Todo se maneja con el teclado y se
prueba con NVDA.

Versión 2.4.0 · Windows 10 y 11 · [novedades de cada versión](CHANGELOG.md)

## Índice

- [Qué hace](#qué-hace)
- [Instalación](#instalación)
- [Primeros pasos](#primeros-pasos)
- [El chat](#el-chat)
- [Reproductor](#reproductor)
- [Música](#música)
- [Transmitir en directo](#transmitir-en-directo)
- [Panel de chat para transmitir](#panel-de-chat-para-transmitir)
- [Mensajes automáticos](#mensajes-automáticos)
- [Descargas e historial](#descargas-e-historial)
- [Estado por voz](#estado-por-voz)
- [Preguntar a la IA](#preguntar-a-la-ia)
- [Sesión de Google](#sesión-de-google)
- [Atajos de teclado](#atajos-de-teclado)
- [Accesibilidad](#accesibilidad)
- [Actualizar](#actualizar)
- [Configuración](#configuración)
- [Problemas frecuentes](#problemas-frecuentes)

## Qué hace

- Lee el chat de un directo de YouTube o de TikTok con las voces de Windows
  o de ElevenLabs, con un sonido distinto para cada tipo de mensaje.
- Lee y publica comentarios en vídeos de YouTube.
- Reproduce el vídeo del directo dentro de la aplicación.
- Pone música de tu carpeta, de tus listas o de YouTube mientras
  transmites.
- Empieza y termina tu directo con OBS Studio, y describe por voz cómo se
  ve la escena.
- Muestra el chat a tus espectadores en un panel para OBS.
- Modera, escribe en el chat y manda mensajes automáticos, con tu sesión
  de Google.
- Descarga vídeo y audio.

En TikTok solo lee: TikTok no tiene una forma oficial de comentar ni de
moderar.

## Instalación

Descomprime el ZIP en cualquier carpeta y abre `Bellbird.exe`. No hace
falta instalar nada ni tener permisos de administrador: el ZIP trae todo
lo necesario.

Hace falta Windows 10 u 11, internet y al menos una voz de Windows (en
*Configuración, Hora e idioma, Voz*). ElevenLabs es opcional y pide una
cuenta propia.

## Primeros pasos

Al abrir, el foco está en el campo de la dirección. Pega el enlace del
directo o del vídeo y pulsa Intro.

La ventana tiene tres regiones: conexión, contenido y reproductor. `F6` y
`Mayús+F6` pasan de una a otra, y `Ctrl+Tab` cambia entre las pestañas de
chat, comentarios e información. Cada cambio se anuncia. La tecla
Aplicaciones abre el menú contextual de la lista del chat o de los
comentarios.

## El chat

Cada mensaje se lee con la voz elegida y suena distinto según quién
escribe (dueño del canal, moderador, cuenta verificada, miembro) y según
lo que es (Super Chat, membresía, regalo de TikTok).

En TikTok también se leen los stickers y las preguntas del directo. En
*Preferencias, Lectura* cada aviso de TikTok (entradas, me gusta,
seguidores, compartidos y cofres) tiene su modo: *Sonido y voz* lo muestra
en la lista, suena y lo lee; *Solo sonido* lo muestra y suena sin leerlo;
*Desactivado* no lo muestra. De fábrica, las entradas y los me gusta están
en *Solo sonido*, y los seguidores, los compartidos y los cofres en *Sonido
y voz*. Si quien transmite pone el directo en pausa, se oye
«El directo de TikTok está en pausa.», y al volver, «El directo de TikTok
continúa.», cada uno con su sonido.

En la lista, las flechas van de mensaje en mensaje y escribir unas letras
salta al primer autor que empieza así. El menú contextual copia el
mensaje, silencia al autor durante la sesión, le pone un alias y, con
sesión de Google, lo expulsa o lo veta.

**Formato de lectura**, en *Preferencias, Lectura*:

| Formato | Ejemplo |
|---|---|
| Nombre y mensaje | «Lucía: hola a todos» |
| Mensaje y después el nombre | «hola a todos, de Lucía» |
| Solo el mensaje | «hola a todos» |
| Solo el nombre | «Lucía» |

En *Preferencias, Filtros* van las palabras y los usuarios que no se leen.

**Voces.** En *Preferencias, Voces* eliges el motor (SAPI 5, OneCore o
ElevenLabs), la voz, la velocidad, el volumen y el tono, y *Probar voz*
deja oírla antes de guardar. Puedes usar una segunda voz para los Super
Chats, los regalos, las membresías y las entradas. Con ElevenLabs puedes
poner un tope de caracteres por sesión o usarlo solo con los mensajes
importantes. Si falla la red o se acaba el saldo, lee la voz de Windows y
lo avisa una vez. La clave se guarda en `credenciales.json`.

**Alias.** Para los nombres que son una tira de letras y números: menú
contextual sobre un mensaje, *Poner alias*, y escribe cómo quieres oírlo.
Vale también para los mensajes que ya estaban. Moderar sigue actuando
sobre la cuenta real. Para quitarlo, deja el campo vacío.

**Escribir en el chat.** Debajo de la lista está el cuadro de escritura,
o `Alt+Intro` desde cualquier parte. `Intro` envía y `Mayús+Intro` hace un
salto de línea. Si falta algo para poder escribir (sesión de Google, un
directo de YouTube con chat), el botón *Enviar* sigue al alcance del
tabulador y su nombre dice qué falta. El límite es de 200 caracteres.

**Sonidos.** Hay uno para cada cosa: mensajes, Super Chats, miembros,
regalos de TikTok por tamaño, seguidores, entradas, la conexión, errores,
y la orilla al llegar al principio o al final de una lista. `F7` los
silencia todos. Para callar uno solo, destilda su casilla en
*Preferencias, Sonidos*, donde *Oír el sonido elegido* deja oír cada uno.
El tema de sonido se elige en la misma página, arriba de la lista:
`default`, con sonidos grabados, o `suave`, más cortos y tenues. Para
hacer uno propio, copia `sounds/themes/default` con otro nombre y cambia
los `.wav`. `sounds/CREDITOS.md` dice de dónde sale cada sonido.

**Comentarios de vídeos.** Con un vídeo ya publicado, la pestaña de
comentarios los muestra y los lee. Con sesión de Google puedes comentar y
responder.

## Reproductor

El vídeo del directo se ve dentro de la aplicación, con libVLC. La calidad
se elige en el menú *Reproductor*, y los botones en pantalla se ocultan
desde ese menú o desde *Preferencias, Reproductor*.

En un directo, los saltos de un minuto se acumulan y dicen dónde quedas:
«40 segundos por detrás del directo». Con las pistas separadas de YouTube
se puede retroceder hasta una hora. `Ctrl+Fin` vuelve al directo. En un
vídeo, las flechas del deslizador de posición mueven diez segundos.

Un directo de TikTok no se puede pausar: al pulsar reproducir o
pausar, la aplicación lo dice y nombra el atajo de Silenciar,
`Ctrl+M`, que lo calla sin cortarlo.

El audio de cada vídeo de YouTube se guarda en `data/cache-audio`, para
que pausar y saltar respondan al instante. Se conservan los tres
últimos.

## Música

Para poner música mientras transmites, sin abrir otro programa. Usa la
carpeta Música junto al programa, o la que elijas en *Preferencias, Música*. Se
maneja desde el menú *Música* o con los atajos de `Ctrl+Alt` (ver la
[tabla](#música-1)).

La ventana *Música* (`Ctrl+Mayús+M`):

- **Colecciones**: *Biblioteca* es tu carpeta, y debajo están tus listas,
  cada una con cuántas canciones tiene («Biblioteca: 195»).
- **Buscar**: filtra mientras escribes, aunque no pongas las tildes.
- **Canciones**: Intro reproduce. El menú contextual reproduce ahora, a
  continuación de la actual sin cortarla, desde ahí hasta el final, la
  agrega a la cola o a una lista, o crea una lista nueva.
- **Mostrar la cola**: lo que va a sonar, en orden.
- **Abrir enlace…**: un vídeo o una lista entera de YouTube, que se suma a
  la cola.
- **Examinar la carpeta**: la recorre de nuevo y dice cuántas canciones
  nuevas y quitadas encontró.

Las canciones nuevas aparecen solas en la lista, sin volver a elegir la
carpeta: la aplicación la vigila y la pone al día en silencio.

Las listas se guardan como archivos `.m3u8`, que abren otros
reproductores. Al reabrir la aplicación, Reproducir sigue la última cola
desde donde estaba, y dice cuántas canciones tiene: si fue una búsqueda,
no es la carpeta entera. Para empezar siempre con toda la carpeta,
desactiva *Recordar la última lista al abrir* en *Preferencias, Música*.

En *Preferencias, Música* también eliges el orden aleatorio, la
repetición (nada, toda la cola o la canción actual), el volumen de la
música, la salida de audio y qué se dice al pasar de canción: nada, el
título, el título y el artista, o solo el artista. Si eliges nada, pasar
de canción con el atajo igual dice el título. Otra casilla decide si se
anuncian la pausa, la reanudación y el volver al comienzo.

La casilla *Igualar el volumen de las canciones*, activada de fábrica,
hace que todas suenen parecido, como en Spotify. Cada archivo se mide
una sola vez con ffmpeg, y su volumen se corrige al empezar cada
canción. Los archivos no se modifican: solo se guarda el resultado en
una caché. La aplicación nunca mide por su cuenta: ni al leer la
carpeta, ni al guardar las preferencias, ni al reproducir con un atajo.

Al abrir la ventana *Música*, si quedan canciones sin medir, la
aplicación pregunta cuántas son y cuánto ocupan, con *Sí* y *No*. La
casilla *No volver a preguntar* deja guardado que no pregunte más, y la
pregunta se activa o se desactiva en *Preferencias, Música*. La ventana
trae el botón *Igualar el volumen*, que empieza la medición; mientras
mide, el botón cambia a *Detener la igualación*. El avance se ve en la
ventana o con F2. Los enlaces de YouTube suenan con su volumen.

Al pasar de una canción a la siguiente, el final de una se funde con el
principio de la otra, sin el silencio que muchos archivos traen al
principio y al final. El largo del fundido se elige en *Preferencias,
Música*, en *Fundido entre canciones, en segundos*: de 0 a 12, con 6 de
fábrica, y 0 lo desactiva. Pasar de canción con el atajo hace un fundido
corto, de medio segundo. El sonido de cambio de canción viene apagado de
fábrica y se activa en la misma página.

La casilla *Usar los atajos de música en cualquier programa* hace que
funcionen aunque estés en OBS o en un juego. Viene apagada porque,
mientras está activa, esas teclas no les llegan a los demás programas.
Si otro programa ya tiene alguna, la aplicación te dice cuál.

NVDA usa `Ctrl+Alt+flechas` para moverse por las tablas. Donde cree que
hay una tabla, como el escritorio o el Explorador de archivos, se queda
con esas teclas y la música no las recibe. Ahí pulsa `NVDA+F2` y
después el atajo: NVDA deja pasar la tecla siguiente. En una ventana
sin tablas, como el Bloc de notas, funcionan sin eso.

## Transmitir en directo

Con OBS Studio, el directo se empieza y se termina desde la aplicación: a
YouTube con tu cuenta de Google, y a TikTok por Restream.

**Una sola vez:**

- Activa el servidor websocket de OBS desde *Preferencias, Transmisión*.
  Si OBS está cerrado, la aplicación lo abre en el área de notificación
  sin quitarle el foco al lector de pantalla.
- Para TikTok, un perfil de OBS llamado `TikTok` con Restream.
- Para YouTube, la sesión de Google iniciada y los directos activados en
  tu canal. El perfil `YouTube` de OBS lo crea la aplicación.
- En la ventana *Transmisión* (`Ctrl+Mayús+T`), sección *Escena*, elige
  qué ventana se captura, por ejemplo un juego. En el directo se ve esa
  ventana, pero su captura no lleva sonido: el sonido sale del audio del
  escritorio y del micrófono de OBS.

**Cada vez:** pulsa **Transmitir en directo**, junto a *Conectar*.

1. Elige el destino. El de la vez anterior ya está elegido, así que basta
   con Intro.
2. La aplicación prepara OBS y revisa la escena: destino, formato,
   fuentes, audio, y si hay algo mal, como una escena vacía, una imagen en
   negro o el micrófono silenciado. Si encuentra problemas, el botón
   elegido de entrada es *Cancelar*.
3. Para YouTube, en la misma ventana pones el título, la descripción, la
   privacidad y, si quieres, la latencia, la categoría, las etiquetas, la
   miniatura y la lista de reproducción. Todo se recuerda. *No listado*
   sirve para probar.
4. Cuando el directo sale al aire, la aplicación conecta el chat sola y lo
   anuncia: «Tu directo de YouTube ya está al aire».
5. Durante el directo avisa si la conexión falla. Si se corta internet,
   YouTube espera a que vuelva sin terminar el directo.

El botón pasa a **Finalizar directo**, que pide confirmación con *seguir
transmitiendo* elegido de entrada. Cerrar la aplicación no corta el
directo: al volver, lo reconoce. `Alt+Mayús+E` copia el enlace del
directo.

`Alt+Mayús+M` silencia o activa el micrófono de OBS. Al activarlo dice
qué dispositivo usa, por ejemplo «Micrófono activado: predeterminado de
Windows, WO Mic Device». Si OBS usa el predeterminado, el micrófono es el
que Windows tenga elegido en ese momento, y puede no ser el que esperas.
Para que no cambie, elige el dispositivo en las propiedades de la fuente
de micrófono en OBS.
Después de activarlo, la aplicación escucha tres segundos. Si no entra
ningún sonido, suena un aviso propio y dice «El micrófono no recibe
sonido. Revisa cuál está elegido en Windows o en OBS.».

`Ctrl+Mayús+O`, o *Mostrar OBS* en el menú *Transmisión*, trae al frente la
ventana de OBS, también cuando está en el área de notificación. Si OBS
espera una respuesta, como la pregunta del modo seguro, el foco va a ese
cuadro.

**Grabar el directo.** Con *Grabar también al transmitir* marcada, en el
menú *Transmisión*, OBS empieza a grabar cuando la transmisión empieza
bien, y deja de grabar cuando la transmisión se detiene. El archivo queda
en la carpeta de grabaciones de OBS. Si ya estabas grabando, esa grabación
sigue como estaba, y cerrar la aplicación no corta ninguna de las dos. Si
la grabación no se puede iniciar, la transmisión sigue y suena un aviso
propio con «La transmisión empezó, pero no se pudo iniciar la grabación.».
Si el perfil de OBS graba con un codificador propio, la revisión antes de
transmitir lo avisa al final, porque grabar así carga el doble el equipo.
En ese caso, para que cargue menos, elige en OBS que la grabación use la
misma calidad que la transmisión. La casilla viene desmarcada.

**Cómo se ve la escena.** La ventana *Transmisión* describe cada fuente de
adelante hacia atrás: dónde está, qué tamaño tiene y si algo la tapa. Lo
mismo se oye con `Ctrl+F2`. Desde ahí puedes mover una fuente a una de
nueve posiciones (por ejemplo, inferior derecha), cambiarle el tamaño,
ocultarla, fijarla, ponerla adelante, moverla con flechas en el ajuste
fino, guardar una captura de la escena para que la vea alguien, grabar, y
deshacer todo lo hecho desde que abriste la ventana. Cada cambio dice
dónde quedó la fuente, cuánto se recorta si sale del borde y cuánto la
tapa otra.

Todo se puede seguir haciendo a mano en OBS, y la aplicación no molesta
al complemento de OBS para NVDA.

## Panel de chat para transmitir

Muestra el chat en grande, con fondo transparente, para tus espectadores.
Se agrega en OBS (o Streamlabs, o Prism Live Studio) como fuente de
navegador con esta dirección:

    http://127.0.0.1:8730/chat

Se activa en la ventana *Transmisión*. Cada mensaje sale en una tarjeta
con la inicial y un color por persona, y las donaciones en dorado con el
importe. Solo se usa con YouTube: TikTok ya muestra los comentarios sobre
el vídeo.

Lo que no cabe en el lienzo de OBS no se emite, y una fuente que queda
en parte fuera se recorta sin aviso. Por eso la ventana *Transmisión* dice cuánto se
recorta. Si otra fuente tapa el panel, la aplicación lo pone delante al
salir al aire y te dice cuál lo tapaba. `F2` dice si el panel está activo
y si OBS lo está mostrando. El servidor solo escucha en tu PC.

## Mensajes automáticos

Mandan mensajes al chat cada cierto tiempo, por ejemplo tus redes cada
diez minutos. Se configuran en *Preferencias, Mensajes automáticos*: cada
uno con su texto, su intervalo (fijo o variable dentro de un rango, desde
cinco minutos) y una casilla para dejarlo preparado sin enviarlo.

Solo funcionan en tu propio directo de YouTube y con sesión de Google. El
primero sale después del intervalo, no al conectar. Enviar no se anuncia,
porque el mensaje ya se lee en el chat. `F2` dice cuánto falta para el
próximo. YouTube suele bloquear los enlaces: mejor el nombre de usuario
que la dirección. Si YouTube devuelve un error, se detienen y se avisa una
vez, sin reintentar.

## Descargas e historial

**Gestor de descargas** (`Ctrl+Mayús+D`): vídeos, audio o listas enteras,
en MP4, WebM, MP3 o M4A, con el audio a 192, 256 o 320 kbps. Baja dos a
la vez y pone las demás en cola. Guarda el historial de lo descargado. La
carpeta Descargas está junto al programa. yt-dlp se actualiza desde
*Herramientas, Actualizar yt-dlp*.

**Historial de directos** (`Ctrl+Mayús+H`): lo que viste, con una pestaña
para YouTube y otra para TikTok. Los directos terminados salen marcados.

## Estado por voz

`F2` resume la situación: conexión, título, canal, espectadores, cuánto
lleva al aire, mensajes leídos, donaciones, el panel de chat y los
mensajes automáticos. Qué entra en el resumen se elige en *Preferencias,
Estado (F2)*, incluidos los datos de OBS y la canción que suena. Mientras
transmites desde la aplicación, `F2` empieza por cómo va el directo.

`F3` dice quién mandó el último mensaje leído, y `Ctrl+F2` describe la
escena de OBS.

## Preguntar a la IA

Una IA mira una captura de OBS y te dice qué se ve: si la cámara está
encendida, si una fuente salió en negro, qué texto hay en pantalla. Hace
falta OBS abierto y la clave de un proveedor.

**Configurar.** En *Preferencias, Inteligencia artificial* eliges el
proveedor (Google Gemini, OpenAI, Anthropic, OpenRouter, OpenCode Go,
Command Code u otro compatible con OpenAI), guardas su clave y eliges el
modelo. La clave queda en el Administrador de credenciales de Windows, no
en `config.ini`, y la página nunca la muestra: solo dice que está
guardada y sus cuatro últimos caracteres. *Probar la clave* manda un
pedido corto y dice si funciona.

*Actualizar la lista de modelos* trae los modelos que aceptan imágenes.
Con OpenRouter y OpenCode Go, *Solo gratuitos* deja los que no cobran.
Con Gemini lo gratis depende de la clave, así que la lista prueba cada
modelo con la tuya y marca los que funcionan. Tarda unos 30 segundos y
suena un aviso mientras tanto.

En la misma página se cambia la instrucción que acompaña a cada captura,
el largo de la respuesta, el tiempo de espera y si se dice «Analizando…»
mientras espera.

**La ventana.** `Ctrl+Mayús+I` la abre. *Agregar captura* deja elegir la
escena al aire o una fuente suelta. En *Mensaje* escribes la pregunta y `Enter`
la envía. Justo después de agregar una captura puedes dejarlo vacío, y se
usa la instrucción. La respuesta
se lee al llegar y queda en *Conversación*, donde `Enter` abre cada
mensaje entero. Puedes seguir preguntando sobre la misma captura o agregar
otra. `Escape` cancela la consulta en curso, y si no hay ninguna, cierra.

**Consulta rápida.** `Ctrl+Mayús+F2` captura la escena al aire, la envía
con la instrucción y lee la respuesta sin abrir nada. El siguiente
`Ctrl+Mayús+I` abre la ventana con esa conversación, para seguir
preguntando.

**Privacidad.** La captura y lo que escribas salen de tu PC hacia el
proveedor. El primer envío lo avisa y pide confirmación una sola vez.
Algunos modelos usan lo que reciben para entrenar, y la lista lo
dice al lado del nombre.

Si la captura sale negra, no se envía. Suele pasar con la cortina de
pantalla de NVDA o en una PC sin monitor conectado. En OBS, cambia el
método de captura de esa fuente a Windows 10.

## Sesión de Google

Hace falta para moderar, escribir en el chat, comentar vídeos y crear el
directo de YouTube. En *Preferencias, API y sesión*, pulsa *Iniciar
sesión* y autoriza en el navegador. No hace falta crear nada en Google
Cloud. Mientras Google no termine de verificar la aplicación, muestra un
aviso de aplicación no verificada: abre la opción avanzada y elige
continuar.

La cuota diaria de YouTube se comparte entre quienes usan la aplicación.
Para tener la tuya, sigue [docs/CONFIGURACION_API.md](docs/CONFIGURACION_API.md),
escrita para leerse con lector de pantalla. Sin sesión, todo lo demás
funciona igual.

## Atajos de teclado

Cada familia de teclas es un área, y se respeta también al
personalizarlos. Todos figuran además en la barra de menú, junto a su
acción.

### Reproductor (Ctrl)

| Atajo | Acción |
|---|---|
| `Ctrl+P` | Reproducir o pausar |
| `Ctrl+Flecha izquierda` / `derecha` | Retroceder o avanzar un minuto |
| `Ctrl+Flecha arriba` / `abajo` | Volumen del reproductor |
| `Ctrl+Fin` | Ir al directo |
| `Ctrl+D` | Detener |
| `Ctrl+M` | Silenciar el audio |
| `Ctrl+F` | Pantalla completa |

### Chat (Alt)

| Atajo | Acción |
|---|---|
| `Alt+Intro` | Ir al cuadro de escritura |

### Ventanas (Ctrl+Mayús)

| Atajo | Acción |
|---|---|
| `Ctrl+Mayús+P` | Preferencias |
| `Ctrl+Mayús+H` | Historial de directos |
| `Ctrl+Mayús+T` | Transmisión |
| `Ctrl+Mayús+D` | Gestor de descargas |
| `Ctrl+Mayús+M` | Música |
| `Ctrl+Mayús+I` | Preguntar a la IA sobre la imagen |
| `Ctrl+Mayús+O` | Mostrar OBS |

### Directo y OBS (Alt+Mayús)

| Atajo | Acción |
|---|---|
| `Alt+Mayús+C` | Conectar |
| `Alt+Mayús+D` | Desconectar |
| `Alt+Mayús+L` | Ir a la lista de mensajes |
| `Alt+Mayús+E` | Copiar el enlace del directo |
| `Alt+Mayús+I` | Marcar una incidencia en el registro |
| `Alt+Mayús+M` | Silenciar o activar el micrófono de OBS |
| `Alt+Mayús+A` | Activar o desactivar los avisos de sobrecarga |

### Voz y lectura (teclas F)

| Atajo | Acción |
|---|---|
| `F5` | Pausar o reanudar la lectura |
| `F8` | Cortar la frase en curso |
| `F9` / `F10` | Velocidad de la voz |
| `F11` / `F12` | Volumen de la voz |
| `F4` | Silenciar la lectura |
| `F7` | Silenciar los sonidos |
| `F2` | Estado |
| `F3` | Autor del último mensaje leído |
| `Ctrl+F2` | Describir la escena de OBS |
| `Ctrl+Mayús+F2` | Consulta rápida a la IA sobre la escena |

Al repetir un ajuste de velocidad o de volumen, la primera vez se dice el
nombre y el valor («Volumen de la voz: 40%») y después solo el valor.

### Música (Ctrl+Alt)

| Atajo | Acción |
|---|---|
| `Ctrl+Alt+Espacio` | Reproducir o pausar |
| `Ctrl+Alt+Flecha derecha` / `izquierda` | Canción siguiente o anterior |
| `Ctrl+Alt+Flecha arriba` / `abajo` | Volumen de la música |
| `Ctrl+Alt+Mayús+Flecha derecha` / `izquierda` | Adelantar o retroceder 10 segundos |
| `Ctrl+Alt+T` | Qué suena |
| `Ctrl+Alt+M` | Silenciar la música |
| `Ctrl+Alt+D` | Detener la música |
| `Ctrl+Alt+A` | Orden aleatorio |
| `Ctrl+Alt+R` | Cambiar la repetición |

### Fijos

| Atajo | Acción |
|---|---|
| `F6` / `Mayús+F6` | Cambiar de región |
| `Ctrl+Tab` | Cambiar de pestaña |
| `Alt+F4` | Salir |

### Mensajes recientes del chat (Ctrl+Mayús y número)

`Ctrl+Mayús+1` lee el último mensaje del chat, `Ctrl+Mayús+2` el anterior
y así hasta `Ctrl+Mayús+0`, que lee el décimo desde el final. De fábrica
valen solo con la aplicación al frente; la casilla *Leer los mensajes
recientes en cualquier programa* de *Preferencias, Lectura* los hace valer
en cualquier programa, como los atajos de música.

En la misma página, *Leer los mensajes recientes con* elige quién los
lee: el lector de pantalla, como viene de fábrica, o la voz de la
aplicación. Con la voz, el mensaje pedido suena en cuanto termina lo que
se está leyendo, y después siguen los mensajes que esperaban, en su
orden.

Si otro programa ya usa alguna de estas combinaciones, o las de música,
suena un tono de ocupado y la aplicación dice cuáles.

### Cambiar un atajo

En *Preferencias, Atajos*, cada acción tiene un botón cuyo nombre incluye
su atajo. Actívalo y pulsa la combinación nueva. `Intro` solo deja la
acción sin atajo y `Escape` cancela. Si la combinación no sirve para esa
área o ya está usada, se dice por qué y el botón sigue esperando. Al
capturar un `Ctrl+Alt` con letra, la aplicación revisa si en tu teclado
`AltGr` con esa tecla escribe algo, como la arroba, y en ese caso te pide
otra. *Restablecer* vuelve todo a fábrica. Nada se guarda hasta pulsar
*Guardar*.

## Accesibilidad

Es el criterio principal del proyecto.

- Cada control tiene nombre accesible y se alcanza con Tab o con flechas.
- La barra de menú es la nativa de Windows.
- Lo que la aplicación avisa por su cuenta va por voz, por braille y con
  un sonido propio.
- Se prueba con NVDA en Windows 10 y 11.

El panel de chat para transmitir es la única parte que no recibe foco,
porque es para los espectadores. El chat accesible es la lista de la
ventana principal.

## Actualizar

*Ayuda, Buscar actualizaciones* dice si hay una versión nueva, muestra sus
novedades y la instala: la descarga se comprueba con su firma, la
aplicación se cierra y vuelve a abrirse sola en alrededor de un minuto. Se
conservan la carpeta `data`, las descargas y tus sonidos. Si la versión
nueva no abre, vuelve sola a la anterior. Al iniciarse, una versión nueva
se anuncia una sola vez.

## Configuración

Casi todo está en *Herramientas, Preferencias*. Se guarda al pulsar
*Guardar* y *Cancelar* lo descarta. Los ajustes viven en `data/config.ini`
y `data/sounds.ini`, que se pueden editar con el Bloc de notas y se
regeneran si se borran.

## Problemas frecuentes

**No hay voces.** Agrega una en *Configuración, Hora e idioma, Voz*, o
prueba el motor OneCore en *Preferencias, Voces*. Las voces neurales de
Windows 11 no salen en SAPI 5: *TTSVoicePatcher* las expone.

**«Windows protegió tu PC».** Es SmartScreen, porque el ejecutable no
está firmado. Elige *Más información, Ejecutar de todos modos*.

**El antivirus avisa.** Es un falso positivo común con los programas
que se distribuyen así, sin instalador. Agrega la carpeta a las exclusiones.

**El panel de chat no se ve.** `F2` dice si el panel está activo y si OBS
lo muestra. Si nadie lo muestra, revisa la fuente de navegador en OBS.

**Algo falla.** *Ayuda, Abrir la carpeta de registros* abre la carpeta
`data`, donde están los registros. Los errores quedan en
`data/ytchat.log`, y si la aplicación se cierra sola, también en
`data/bellbird-fallos.log`. El registro detallado, `data/bellbird-debug.log`,
viene encendido; se apaga en *Preferencias, Diagnóstico*, con la casilla
*Guardar un registro detallado para diagnosticar fallos*. Para avisar de
un fallo, reproduce el problema y manda los tres archivos.

## Licencia

GPL-3.0 desde la 2.5.1. Ver [LICENSE](LICENSE). Las versiones hasta la
2.5.0 se publicaron con licencia MIT.

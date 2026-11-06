# Política de privacidad de Guyrapu

Última actualización: 6 de noviembre de 2026.

Guyrapu es una aplicación de escritorio para Windows que lee en voz alta el
chat de YouTube Live y de TikTok Live. Es software libre y funciona entera en
el equipo de quien la usa. No tiene cuentas de usuario y no recoge
estadísticas de uso. Su único servidor es un servicio pequeño que conecta con
Restream, descrito más abajo, y no guarda nada.

## Qué datos maneja

**Credenciales de la API de YouTube.** La clave de API, el cliente OAuth y el
permiso que se obtiene al iniciar sesión con Google se guardan en el archivo
`credenciales.json`, dentro de la carpeta de la aplicación. No salen de ese
equipo salvo hacia Google, que es quien los emite y los valida.

**Permiso de YouTube.** Al iniciar sesión, la aplicación pide el permiso
`youtube.force-ssl`. Lo usa solo para lo que la persona pide expresamente:
enviar mensajes al chat, responder y publicar comentarios, y moderar un
directo propio o en el que es moderadora. No lo usa para nada más ni lo
comparte con nadie.

**Cuenta de Restream.** Si la persona conecta su cuenta de Restream, la
aplicación guarda el permiso que Restream le da en el mismo
`credenciales.json`. Lo usa para lo que la persona pide desde la ventana de
Restream: mostrar el nombre de la cuenta, la lista de destinos y la de
eventos con sus estadísticas, y quitar un destino cuando la persona lo pide y
lo confirma. Al desconectar la cuenta, la aplicación retira el permiso en
Restream y lo borra del equipo.

**Chat, comentarios y datos de los vídeos.** Se leen de YouTube y de TikTok
para mostrarlos y leerlos en voz alta. Se guardan en el equipo solo el
historial de directos visitados, las preferencias y los registros de
diagnóstico, todo en la carpeta de la aplicación.

## Con quién se comunica

- Con los servicios de Google y YouTube, para leer el chat, los comentarios y
  los datos de los vídeos, y para las acciones que la persona pide.
- Con TikTok, para leer el chat de un directo.
- Con Restream, solo si la persona conecta su cuenta, para las acciones que
  pide desde la ventana de Restream.
- Con el servicio de Guyrapu en Cloudflare
  (`restream-tokens.guyrapu.workers.dev`), solo al conectar la cuenta de
  Restream y cada vez que hay que renovar su permiso. Restream exige una clave
  secreta para esos dos pasos, y esa clave no puede ir dentro de un programa
  que cualquiera descarga. Por eso la aplicación le manda al servicio el
  código de autorización o el token de renovación. El servicio le agrega la
  clave, lo pasa a Restream y le devuelve a la aplicación los tokens que
  Restream entrega. No guarda los datos que recibe, no tiene base de datos y no recibe nada de YouTube ni de
  TikTok.
- Con GitHub, para comprobar si hay una versión nueva del componente que
  descarga los vídeos.

El panel de chat para transmitir y la conexión con OBS funcionan solo dentro
del propio equipo y no aceptan conexiones de fuera.

La aplicación no vende, no cede y no envía datos a terceros aparte de los
servicios que se nombran arriba, que solo reciben lo que necesitan para
funcionar.

## Cómo borrar los datos

Basta con borrar la carpeta de la aplicación. El permiso de Restream se
retira con el botón Desconectar de la ventana de Restream o desde la
configuración de la cuenta de Restream. El permiso concedido a Google se
puede retirar en cualquier momento desde la configuración de seguridad de la
cuenta de Google, en el apartado de aplicaciones de terceros con acceso.

## Uso de los datos de Google

El uso que hace Guyrapu de la información recibida de las API de Google
cumple la Política de Datos de Usuario de los Servicios de API de Google,
incluidos los requisitos de uso limitado.

## Contacto

Para cualquier consulta, se puede abrir una incidencia en el repositorio:
https://github.com/miguel-cinsfran/guyrapu/issues

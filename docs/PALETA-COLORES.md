# Paleta de colores: Bellbird

Referencia de los colores que usa la aplicación y para qué sirve cada uno. Hay
tres superficies distintas, cada una con su paleta: la **ventana** (wxPython,
la que usa quien retransmite), el **panel de chat para la emisión**
(`web/chat.html`, lo que ven los espectadores dentro de OBS) y la
**documentación HTML** (`docs/`). La fuente de verdad es el código; este
documento explica el criterio para que quien toque un color sepa qué está
tocando. La paleta se llama **pájaro campana**.

## Criterio general

- **La accesibilidad manda.** La app está pensada para personas ciegas o con
  baja visión. Todo par texto/fondo real da **4,5:1 o más** (WCAG AA) y se
  comprueba con la fórmula de contraste, no a ojo. Los tonos de marca que no
  llegan se oscurecen lo justo para el texto y se dejan tal cual solo en
  formas sólidas (botones, barras), que no son texto.
- **Contraste alto de Windows tiene prioridad.** Si el sistema tiene activado
  un tema de contraste alto, la ventana no aplica ninguno de estos colores y
  deja mandar al tema (`ALTO_CONTRASTE`, detectado al arrancar con
  `SPI_GETHIGHCONTRAST`). Todo color se aplica a través de `_pintar` o
  `_tc`, que son los que respetan ese interruptor; no llamar a
  `SetBackgroundColour`/`SetForegroundColour` con colores de paleta por fuera.
  `_T`, `_pintar`, `_tc` y `ALTO_CONTRASTE` viven en `bellbird/ui/tema.py`, no
  en `gui`.
- **Pocos colores con papel fijo.** Cada tono significa siempre lo mismo. Nada
  decorativo.
- **Neutros fríos.** Los grises se tiñen hacia el turquesa del ave en lugar de
  hacia el beige, porque la calidez acercaba la interfaz al cliché de una
  pantalla generada con crema y un acento cálido.
- **El color nunca informa solo.** El error y cualquier aviso nunca se
  distinguen únicamente por el color, porque para la deuteranopía un rojo y un
  ámbar de la misma luminosidad son casi iguales; llevan siempre su palabra y
  su sonido.

## Origen

El pájaro campana (*Procnias nudicollis*) es el ave nacional de Paraguay y da
nombre a la app. El macho es blanco con la piel de la cara y la garganta
turquesa verdosa: de ahí el blanco frío y el acento turquesa. Los neutros van
teñidos hacia ese mismo tono, por eso son fríos.

## Ventana (wxPython): `_T` en `bellbird/ui/tema.py`

Modo claro únicamente: wx pinta con el tema nativo de Windows y no hay tema
oscuro propio (con contraste alto se apaga la paleta entera, ver arriba).

| Nombre en código | Hex | Papel |
|---|---|---|
| `bg` | `#F3F6F6` | Blanco frío. Fondo general de la ventana y de los diálogos. |
| `surface` | `#FFFFFF` | Blanco. Paneles, grupos y pestañas. |
| `field` | `#FFFFFF` | Blanco. Campos de texto y listas: se recortan del fondo frío. |
| `text` | `#1C2629` | Pizarra muy oscura. Texto principal y etiquetas de campo. |
| `dim` | `#56656A` | Pizarra media. Texto secundario: notas, estados, subtítulos. |
| `accent` | `#0B6E63` | Turquesa oscuro. Títulos de los recuadros y estados «bien». |
| `red` | `#B42318` | Rojo. Solo texto: errores. |
| `btn` / `btn_t` | `#E2E8E8` / `#1C2629` | Gris verdoso claro. Botones secundarios. |
| `primary` / `primary_t` | `#0B6E63` / `#FFFFFF` | Turquesa oscuro con texto blanco. Un solo botón principal por ventana. |

Contraste medido (WCAG) de los pares que existen de verdad en la ventana:

| Par | Relación |
|---|---|
| `text` sobre `bg` | 14,22 |
| `text` sobre `surface` y `field` | 15,46 |
| `text` sobre `btn` | 12,47 |
| `dim` sobre `bg` | 5,58 |
| `dim` sobre `surface` y `field` | 6,06 |
| `dim` sobre `btn` | 4,89 |
| `accent` sobre `bg` | 5,64 |
| `accent` sobre `surface` y `field` | 6,13 |
| `accent` sobre `btn` | 4,95 |
| `red` sobre `bg` | 6,05 |
| `red` sobre `surface` y `field` | 6,57 |
| `red` sobre `btn` | 5,30 |
| `btn_t` sobre `btn` | 12,47 |
| `primary_t` sobre `primary` | 6,13 |

**Un solo camino de color.** Toda ventana llama a `paleta.pintar_ventana`
al final de su construcción. Pinta el color de base por tipo de control y
respeta el que un control ya tenga con papel propio (una nota en `dim`, un
error en `red`). Dos papeles se aplican siempre: el botón por defecto sale
como principal, y el título de cada recuadro en `accent` y en negrita. Una
ventana sin botón por defecto marca su acción principal con
`tema.boton_principal`. Los deslizadores y las barras de progreso toman el
fondo de su panel.

**Dónde va el turquesa.** Solo en los títulos de los recuadros y en la acción
principal, así el color marca la jerarquía. Las etiquetas de campo van en
`text`.

## Panel de chat para la emisión: `web/chat.html` y `overlay_datos.py`

Lo ven los espectadores dentro de OBS sobre el vídeo, así que es oscuro y con
fondo casi opaco para que el texto aguante cualquier imagen debajo. No es
parte de la interfaz accesible (no recibe foco), pero el texto cumple igual
4,5:1 sobre su tarjeta.

| Nombre en CSS / Python | Hex | Papel |
|---|---|---|
| `--tinta` / `COLOR_CUERPO` | `#EEF3F3` | Texto del mensaje (11,98 sobre el peor fondo). |
| `--caja-alta` | `rgba(26,32,34,.93)` | Carbón frío. Primera parada del degradado de la tarjeta. |
| `--caja-baja` | `rgba(20,25,27,.93)` | Carbón frío. Segunda parada del degradado. |
| `FONDO_PEOR` | `#2A3031` | La caja alta al 93 % sobre blanco puro, para medir el peor caso. |
| `--yt` | `#E8745C` | Marca YouTube. Solo barras y bordes (4,52 sobre la tarjeta). |
| `--yt-txt` / `COLOR_YOUTUBE` | `#ED8068` | Variante de texto de YouTube (5,04). |
| `--tk` | `#2D9D8F` | Marca TikTok. Solo barras y bordes (4,04). |
| `--tk-txt` / `COLOR_TIKTOK` | `#3FB8A8` | Variante de texto de TikTok (5,51). |
| `--oro` / `COLOR_DORADO` | `#E0AE4E` | Super Chat y miembros nuevos (6,60). |

Los colores de plataforma no cambian: el turquesa como acento se confundiría
con el de TikTok. `--borde` conserva su blanco translúcido.

Colores de autor (`PALETA_NOMBRES` en `overlay_datos.py` y `PALETA` en el
HTML): doce tonos claros que se asignan a cada nombre de usuario por un hash
del nombre, de modo que la misma persona tiene siempre el mismo color. El hash
recorre puntos de código (no unidades UTF-16), y Python y JavaScript deben dar
el mismo resultado; hay un test de paridad en `tests/test_overlay_datos.py`.
Si se cambia la lista, cambiarla en los dos sitios. Todos superan 4,5:1 sobre
`FONDO_PEOR`: van de 5,04 a 7,45.

```
#ED8068  #5FBFA8  #E0AE4E  #8FB8E8  #C79BE0  #9CC97E
#F0908A  #6FD0C4  #D8C06A  #B0A8F0  #E3A277  #7FC8E8
```

## Documentación HTML: `scripts/generar_docs.py`

Los HTML de `docs/` (Léeme, Novedades, guía de la API) llevan su propio par
claro/oscuro, elegido por `prefers-color-scheme` del navegador.

| Token | Claro | Oscuro | Papel |
|---|---|---|---|
| `--fondo` | `#FFFFFF` | `#14191B` | Fondo de la página |
| `--texto` | `#1C2629` | `#E4EBEB` | Texto |
| `--tenue` | `#56656A` | `#9AA8AC` | Texto secundario |
| `--acento` | `#0B6E63` | `#45C9B6` | Enlaces y títulos |
| `--borde` | `#E2E8E8` | `#2F393C` | Bordes y separadores |
| `--codigo-fondo` | `#F3F6F6` | `#1C2427` | Fondo de bloques de código |

Contraste medido de cada par real de la documentación:

| Par | Claro | Oscuro |
|---|---|---|
| `texto` sobre `fondo` | 15,46 | 14,67 |
| `tenue` sobre `fondo` | 6,06 | 7,24 |
| `acento` sobre `fondo` | 6,13 | 8,68 |
| `texto` sobre `codigo-fondo` | 14,22 | 13,06 |
| `tenue` sobre `codigo-fondo` | 5,58 | 6,44 |
| `acento` sobre `codigo-fondo` | 5,64 | 7,73 |

## Cómo cambiar un color sin romper nada

1. Cambiarlo en el sitio que manda: `_T` en `bellbird/ui/tema.py` para la
   ventana, `:root` de `web/chat.html` más `overlay_datos.py` para el panel,
   `scripts/generar_docs.py` para la documentación.
2. Recalcular el contraste del par afectado (fórmula WCAG; cualquier
   calculadora en línea sirve) y no bajar de 4,5:1 en texto.
3. Si el color es de texto y no llega, oscurecerlo (ventana) o aclararlo
   (panel) en vez de buscar otro tono: así la familia se mantiene.
4. Regenerar los HTML con `uv run python scripts/generar_docs.py` y actualizar
   este documento.

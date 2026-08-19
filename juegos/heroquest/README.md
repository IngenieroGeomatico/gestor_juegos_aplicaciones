# HeroQuest

Juego de mesa clásico de mazmorras. Esta carpeta contiene los datos y scripts del juego.

## Datos (`data/`)

Ficheros JSON con el contenido del juego:

- `personajes.json` — Héroes (clase, ataque, defensa, cuerpo, mente, movimiento)
- `armas.json` — Armas, armaduras y pociones (ataque, defensa, coste)
- `monstruos.json` — Enemigos (ataque, defensa, cuerpo, mente, movimiento)
- `hechizos.json` — Conjuros y cartas de magia (nombre, escuela, coste_mente, descripcion)
- `misiones.json` — Misiones montables en tablero (con coordenadas en la cuadrícula)
- `tableros.json` — Los tableros del juego: "El Original" (generado desde el SVG
  de Wikipedia, CC BY-SA 4.0 / GFDL) y "Cara B" (pendiente de su SVG). Se genera
  de forma reproducible con `tablero_svg.py` (ver más abajo)
- `impresion3d.json` — Enlaces gratuitos a archivos 3D imprimibles para Hero Quest:
  plataformas de descarga, colecciones y modelos concretos (héroes, monstruos,
  mobiliario, puertas, tablero y dados), con su licencia cuando se conoce
- `impresion3d_warhammer40k.json` — Enlaces gratuitos a archivos 3D imprimibles
  para Warhammer 40K, mismo esquema que `impresion3d.json`. Categorizado por
  facciones: marines del caos, demonios del caos (incluido el Soul Grinder de
  Khorne), tiránidos, eldars/aeldari, t'au, orkos, necrones y marines espaciales
  proxy, además de terreno y plantillas de tablero

### Los tableros y las misiones

Cada misión se monta en uno de los dos tableros del HeroQuest: El Despertar. Las
misiones usan coordenadas globales de la cuadrícula del tablero:

| Campo | Descripción |
|-------|-------------|
| `tablero` | ID del tablero (`original`, `cara-b`) |
| `entrada_heroes` | Casillas de entrada de los héroes `[{x, y}]` |
| `puertas` | Casillas con puerta `[{x, y}]` |
| `salas` | Lista de salas: `{numero, nombre, descripcion, monstruos[], tesoros[]}` donde cada monstruo/tesoro es `{nombre, x, y}` |

Ver el tablero (salas numeradas, `.` = pasillo) con:

```bash
uv run juegos/heroquest/scripts/tablero.py ver --tablero original
```

### Digitalizar un tablero desde su SVG (recomendado)

La forma reproducible de mapear un tablero es a partir de su **SVG vectorial**
(la fuente de verdad). Cada sala es un `<rect>` o `<path>` ortogonal dentro del
grupo `<g id="rooms">`, en coordenadas de la cuadrícula; el `viewBox` fija el
tamaño en casillas. `tablero_svg.py` parsea el SVG (incluidas las salas en L),
numera las salas de forma canónica (orden de lectura por filas), guarda el color
de cada sala y escribe `tableros.json` directamente. Todo lo no cubierto por una
sala es pasillo.

```bash
# El Original (SVG de Wikipedia ya incluido en sources/)
uv run juegos/heroquest/scripts/tablero_svg.py \
  --svg juegos/heroquest/sources/heroquest_board_original.svg --id original

# Cara B: deja su SVG en sources/ y ejecútalo con --id cara-b
uv run juegos/heroquest/scripts/tablero_svg.py \
  --svg juegos/heroquest/sources/heroquest_board_back.svg --id cara-b
```

Después, revisa el resultado:

```bash
uv run juegos/heroquest/scripts/tablero.py ver --tablero cara-b   # render ASCII
uv run juegos/heroquest/scripts/mapa.py --tablero cara-b          # PNG para revisar
```

#### Qué debe cumplir el SVG (contrato de `tablero_svg.py`)

**Obligatorio** (si falta, el script aborta con un error claro):

1. **`viewBox` en el `<svg>`.** El tamaño del tablero se deduce solo:
   `columnas = ancho_viewBox / escala`, `filas = alto_viewBox / escala`. En el
   original es `viewBox="0 0 260 190"` con `transform="scale(10)"` → 26×19
   casillas. No hay que indicar el tamaño a mano; sale del SVG.
2. **Un grupo `<g id="rooms">`** que contenga TODAS las salas. Todo lo dibujado
   fuera de ese grupo (marco, rejilla, texturas, título) se ignora: decora libre.
3. **Cada sala es un `<rect>` o un `<path>` ortogonal** dentro de `#rooms`:
   - `<rect x y width height fill="#rgb"/>` para salas rectangulares.
   - `<path d="M … z" fill="#rgb"/>` para salas en L/compuestas. Solo se admiten
     comandos ortogonales (`M`, `H/h`, `V/v`, `L/l`, `Z/z`); nada de curvas
     (`C`, `Q`, `A`) ni diagonales (darían error "comando de path no soportado").

**A tener en cuenta:**

- **Coordenadas alineadas a la cuadrícula.** Cada valor se redondea al entero más
  cercano; traza los bordes de las salas sobre líneas enteras de la rejilla.
- **0-indexado → 1-indexado automático.** El SVG usa base 0 y el repo base 1; el
  script suma +1 solo. Sigue el mismo criterio de márgenes que el SVG original.
- **Los pasillos no se dibujan.** Todo lo que no cubre una sala es pasillo; no
  añadas rects de pasillo.
- **La numeración es automática** (orden de lectura por filas). Las etiquetas de
  texto del SVG se ignoran, así que no dependas de ellas para el número de sala.
- **El `fill` de cada sala se guarda como su color** para el render (opcional pero
  recomendado: da colores distintos a cada sala para un mapa legible).

**¿De dónde sacar el SVG de la Cara B?** Si hay uno de la comunidad
(p. ej. HeroQuester.eu) que cumpla el contrato, úsalo. Si solo tienes la foto
(`sources/heroquest_board_back.jpg`), trázalo a mano en Inkscape sobre la foto
(rects alineados a la rejilla dentro de un `<g id="rooms">`) o usa la alternativa
para fotos de abajo.

> Alternativa para fotos (sin SVG): el flujo `tablero_calibrar.py` (endereza la
> foto y dibuja una rejilla numerada) → trazar `data/<id>.rooms.txt` a mano →
> `tablero_construir.py`. Es más laborioso; usa el SVG siempre que puedas.

## Agente

Usa el agente **HeroQuest** de este repositorio para generar misiones, personajes,
armas o monstruos coherentes con el juego. La definición canónica del agente vive
en `.opencode/agent/heroquest.md` (necesaria para opencode) y se conserva también
una copia aquí como [AGENT.md](AGENT.md).
También puedes usar los scripts directamente.

## Scripts (`scripts/`)

Ejecutar desde la raíz del repositorio con `uv run`:

```bash
# Listar contenido (héroes, armas, monstruos, misiones)
uv run juegos/heroquest/scripts/listar.py --tipo personajes

# Añadir una nueva carta (personaje, arma, armadura, poción, monstruo o hechizo).
# Un único script para todos los tipos; cada tipo declara sus campos.
uv run juegos/heroquest/scripts/nueva_carta.py --tipo hechizo --nombre "Bola de fuego" \
  --escuela Mago --coste_mente 2 --descripcion "Causa 1 punto de daño a un monstruo adyacente"
uv run juegos/heroquest/scripts/nueva_carta.py --tipo arma --nombre "Espada encantada" --ataque 4 --coste 500
uv run juegos/heroquest/scripts/nueva_carta.py --tipo monstruo --nombre "Basilisco" --ataque 3 --defensa 3 --cuerpo 2 --mente 5
uv run juegos/heroquest/scripts/nueva_carta.py --tipo personaje --nombre "Semielfa" --clase "Ranger" --ataque 2 --defensa 3 --cuerpo 6 --mente 4

# Añadir una nueva misión montable en tablero
# (las salas y sus posiciones van en un JSON, ver esquema más abajo)
uv run juegos/heroquest/scripts/nueva_mision.py --nombre "Las Minas de Karak" --tablero original \
  --objetivo "Salir de la mina" --entrada 13,1 --puerta 9,6 --habitaciones salas.json

# Generar tableros.json desde el SVG de un tablero (fuente de verdad)
uv run juegos/heroquest/scripts/tablero_svg.py --svg juegos/heroquest/sources/heroquest_board_original.svg --id original

# Ver el mapa de un tablero (salas numeradas, '.' = pasillo)
uv run juegos/heroquest/scripts/tablero.py ver --tablero original

# Validar que todas las misiones caben en sus tableros
uv run juegos/heroquest/scripts/tablero.py validar

# Generar una imagen (PNG/SVG) del tablero o de una misión montada
uv run juegos/heroquest/scripts/mapa.py --tablero original --mision "El Refugio del Guardián" --svg

# Ficha de máster de una misión en un único HTML (mapa + salas + stats + casillas de vida)
uv run juegos/heroquest/scripts/mision_html.py --mision "El Refugio del Guardián"

# Preparar los reversos de las cartas a partir de las fotos de sources/
uv run juegos/heroquest/scripts/preparar_reversos.py

# (Re)generar el arte del anverso de las cartas (SVG vectorial -> PNG)
uv run juegos/heroquest/scripts/generar_arte.py                 # todo
uv run juegos/heroquest/scripts/generar_arte.py --solo "Daga"   # solo una

# (Re)generar los fondos de reverso por categoría (SVG vectorial -> PNG)
uv run juegos/heroquest/scripts/generar_fondos.py               # todos
uv run juegos/heroquest/scripts/generar_fondos.py --solo tesoro # solo uno

# Eliminar una entrada por nombre
uv run juegos/heroquest/scripts/eliminar.py --tipo monstruos --nombre "Basilisco"
```

`mapa.py` deja las imágenes en `juegos/heroquest/mapas/` (ignoradas por git); usa
`--salida <ruta>` para elegir dónde guardarlas. Dibuja las salas por colores, los
pasillos, y sobre la misión: entrada (verde), puertas (marrón), monstruos (rojo)
y tesoros (dorado), con su leyenda.

`mision_html.py` es una ficha autocontenida (CSS embebido) lista para abrir en el
navegador o tablet: datos de la misión, mapa en SVG, cada sala con sus monstruos
(stats y casillas para marcar el daño) y tesoros, y tablas de referencia de
héroes, armas y hechizos. Se guarda en `juegos/heroquest/mapas/` (ignorado por
git); usa `--salida <ruta>` para otra ubicación.

`carta_item.py` genera una carta individual con aspecto de carta de HeroQuest
(pergamino, banner de título, ilustración simbólica, tabla de stats y descripción)
para `--tipo arma`, `armadura`, `pocion`, `hechizo`, `personaje` o `monstruo`, p. ej.:

```bash
uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta"
uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego" --formato png
```

Genera un `.html` autocontenido (anverso en SVG + reverso de la carta como imagen)
y/o un `.png` del anverso (dibujado con Pillow). Elige con `--formato html|png|ambos`.
Se guarda en `juegos/heroquest/cartas/` (ignorado por git); usa `--salida <ruta>`
para otra ubicación.

`preparar_reversos.py` recorta y endereza las fotos `*_back.jpg` de `sources/`
(las cartas reales por su cara trasera) y deja los reversos limpios en
`sources/reversos/` (ignorado por git), que `carta_item.py` usa como cara trasera.

### El arte del anverso (`scripts/generar_arte.py` y `sources/arte/`)

La ilustración que aparece dentro de cada carta (la espada, el hacha, la poción…)
se guarda como PNG en `sources/arte/` y `render_carta.py` la localiza **por
convención de nombre**: busca `sources/arte/<slug(nombre)>.png` (p. ej.
`Espada_corta.png`, `Báculo_del_mago.png`). Una entrada también puede declarar su
propio fichero con el campo `"arte": "otro_nombre.png"`.

Ese arte se genera de forma **reproducible y editable** con `generar_arte.py`,
siguiendo la misma filosofía que los tableros (**SVG = fuente de verdad**):

- Cada objeto se dibuja como un **SVG vectorial** de 700×500 sobre el fondo
  degradado morado característico. El volumen (metal biselado, oro, cuero, gemas)
  se consigue con **degradados** (`<linearGradient>`/`<radialGradient>`), un
  reflejo de lustre semitransparente y una **sombra suave** (`feDropShadow`).
- El SVG se **rasteriza a PNG con `resvg`** (`resvg_py`, la misma librería que usa
  `render_carta.py`), así que no hay dependencias ni pasos manuales.
- Los SVG fuente se conservan en `sources/arte_svg/` (versionables y editables);
  los PNG finales van a `sources/arte/` con el nombre que espera `render_carta`.

```bash
uv run juegos/heroquest/scripts/generar_arte.py                  # regenera los 11
uv run juegos/heroquest/scripts/generar_arte.py --solo "Escudo"  # solo uno
uv run juegos/heroquest/scripts/generar_arte.py --svg-solo       # SVG sin PNG
```

Para **añadir o mejorar** un arte, escribe/edita su función de dibujo en
`generar_arte.py` reutilizando las piezas comunes (`_hoja`, `_guarda_recta`,
`_empunadura`, `_pomo`, `_gema`, `_engaste`, …) para mantener un estilo coherente,
y regenéralo. El flujo recomendado es **iterar mirando el PNG**: genéralo, ábrelo,
corrige proporciones/geometría y repite hasta que quede bien.

### El fondo del reverso (`scripts/generar_fondos.py` y `sources/arte_fondos/`)

El reverso de cada carta lleva de fondo una **escena ambiental temática** según
su categoría, y encima la carta dibuja su marco, el banner "HeroQuest" y la
leyenda inferior. Hay un fondo por categoría en `sources/arte_fondos/`:

| Fichero | Categoría | Escena |
|---------|-----------|--------|
| `equipo_back.png` | equipo (armas/armaduras/pociones) | armería: panoplia de armas, escudo, antorchas |
| `tesoro_back.png` | tesoro | cámara del tesoro: cofre con oro, monedas y gemas |
| `enemigo_back.png` | monstruos | mazmorra: reja, cadenas y calavera de ojos rojos |
| `heroe_back.png` | héroes | salón heroico: escudo heráldico y estandartes |
| `magia_back.png` | hechizos | santuario arcano: orbe, círculo rúnico y velas |

Se generan con `generar_fondos.py`, misma filosofía que el anverso (**SVG =
fuente de verdad**, rasterizado a PNG con `resvg`), en formato 1000×1400
(proporción 63×88 de la carta). Cada escena reserva **bandas oscuras arriba y
abajo** para que el banner y la leyenda que pinta la carta encima se lean bien.
Los SVG fuente quedan en `sources/arte_fondos_svg/`.

```bash
uv run juegos/heroquest/scripts/generar_fondos.py               # regenera los 5
uv run juegos/heroquest/scripts/generar_fondos.py --solo magia  # solo uno
uv run juegos/heroquest/scripts/generar_fondos.py --svg-solo    # SVG sin PNG
```

Para usar un fondo en el reverso de una carta, pásalo con `--fondo_verso` (busca
en `sources/arte_fondos/`) junto a `--carta_completa`:

```bash
uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego" \
  --carta_completa --fondo_verso magia_back.png --formato png
```

Para **añadir o mejorar** un fondo, edita su función de escena en
`generar_fondos.py` reutilizando las piezas comunes (`_muro`, `_luz`, `_antorcha`,
`_bandas`, `_vineta`, `_espada`) y regenéralo, iterando mirando el PNG.

### Arquitectura de las cartas (`scripts/tipos_carta/`)

Cada tipo de carta vive en su propio módulo dentro del paquete `tipos_carta/` y
declara su lógica: campos y estadísticas, validación, descripción, arte frontal y
reverso. `nueva_carta.py` (creación) y `carta_item.py` (dibujo, vía `render_carta.py`)
son orquestadores que consumen esas definiciones desde un registro común
(`tipos_carta/registro.py`), sin conocer los detalles de cada tipo. Añadir un tipo
nuevo es crear un módulo y registrarlo. `render_carta.py` dibuja el anverso en dos
familias de maquetación: `stats` (personaje, monstruo) y `descripcion` (arma,
armadura, poción, hechizo), tanto en SVG como en PNG.

Cada script valida que el nombre no exista ya y muestra ayuda con `-h`. `nueva_mision.py`
valida además que cada monstruo/tesoro caiga dentro de la sala indicada y dentro del tablero.

Esquema de las salas de una misión (`salas.json`):

```json
[
  {
    "numero": 5,
    "nombre": "La Forja",
    "descripcion": "Herrería en llamas.",
    "monstruos": [{ "nombre": "Orco", "x": 18, "y": 2 }],
    "tesoros": [{ "nombre": "Hacha de batalla", "x": 20, "y": 1 }]
  }
]
```

## Recursos externos

- [HeroQuester.eu](https://heroquester.eu/) — web fan en español sobre HeroQuest:
  noticias, comunidad, entrevistas y descargas.
- [Archivos y Descargas](https://heroquester.eu/archivos-y-descargas) — recopilación
  de material descargable fanmade alojado en Google Drive: libros de misiones,
  cartas, losetas, héroes y monstruos (expansiones y creaciones de la comunidad).
- [Enlaces](https://heroquester.eu/enlaces) — recursos oficiales y fanmade.

Para incorporar al `data/` una misión, aventura o expansión vista en la web, deja
el material descargado en `juegos/heroquest/sources/` y conviértelo a JSON respetando
el esquema (o pídeselo al agente `heroquest`).
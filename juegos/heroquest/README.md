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

# (Re)generar el arte del anverso de armas/objetos (SVG vectorial -> PNG)
uv run juegos/heroquest/scripts/generar_arte.py                 # todo
uv run juegos/heroquest/scripts/generar_arte.py --solo "Daga"   # solo una

# (Re)generar los retratos de héroes y monstruos (SVG vectorial -> PNG)
uv run juegos/heroquest/scripts/generar_retratos.py             # todos
uv run juegos/heroquest/scripts/generar_retratos.py --solo Orco # solo uno

# (Re)generar los fondos de reverso por categoría (SVG vectorial -> PNG)
uv run juegos/heroquest/scripts/generar_fondos.py               # todos
uv run juegos/heroquest/scripts/generar_fondos.py --solo tesoro # solo uno

# Imprimir cartas: PDF A4 con hojas plegables (anverso|reverso) para recortar
uv run juegos/heroquest/scripts/imprimir_cartas.py --todo
uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml

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

`generar_arte.py` cubre las armas/objetos **y los hechizos** (Bola de fuego,
Curar heridas, Dardo de caos), cada uno con su icono mágico propio (esfera de
llamas, cruz de vida radiante, proyectil de caos).

Los **héroes y monstruos** tienen su propio arte: un **retrato de busto** por
personaje (Bárbaro, Enano, Elfo, Mago; Trasgo, Orco, Fimir, Guerrero del Caos,
Gárgola), generado con `generar_retratos.py`. Van también a `sources/arte/` con
el `slug` del nombre (`Bárbaro.png`, `Guerrero_del_Caos.png`, …), así que
`render_carta` los usa por la misma convención. Comparten `sources/arte_svg/` y
las piezas de dibujo comunes (`_cabeza`, `_ojos`, `_cejas`, `_hombros`, `_cuello`,
`_nariz`), y cada personaje añade sus rasgos distintivos (melena, orejas
puntiagudas, sombrero de mago, ojo único del Fimir, cuernos del Caos, alas de
piedra de la Gárgola). El lienzo del retrato es **vertical (520×600)**, con una
proporción cercana a la del área de arte de la plantilla `anverso_stats.svg`
(que llega hasta el borde inferior de la carta), para que el busto se vea grande
y completo (cabeza arriba, hombros abajo) sin que el recorte "cover" de la carta
lo corte por los lados.

> `generar_arte.py`, `generar_retratos.py` y `generar_fondos.py` comparten
> utilidades comunes en `scripts/arte_comun.py` (`slug` y `rasterizar` con resvg).

```bash
uv run juegos/heroquest/scripts/generar_retratos.py             # los 9
uv run juegos/heroquest/scripts/generar_retratos.py --solo Mago # solo uno
uv run juegos/heroquest/scripts/generar_retratos.py --svg-solo  # SVG sin PNG
```

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
| `magia_back.png` | magia (genérico) | santuario arcano: orbe, círculo rúnico y velas |
| `magia_agua_back.png` | hechizos de **Agua** | santuario acuático: charco reflectante, ondas y el rayo de agua |
| `magia_aire_back.png` | hechizos de **Aire** | santuario eólico: remolinos de viento y plumas |
| `magia_fuego_back.png` | hechizos de **Fuego** | santuario ígneo: brasero y llamas desatadas |
| `magia_tierra_back.png` | hechizos de **Tierra** | santuario telúrico: raíces colgantes, grietas y musgo |
| `magia_terror_back.png` | hechizos de **Terror** | santuario desecrado: niebla, ojos rojos y cuervos |

Las escenas de las distintas escuelas de magia comparten el esqueleto del
santuario arcano (círculo rúnico, pedestal, orbe y velas) pero cambian la paleta,
el orbe y los motivos de cada elemento. El reverso de cada hechizo elige
**automáticamente** el fondo de su escuela a partir del campo `escuela` de la
carta (`Bola de fuego` → `magia_fuego_back.png`, `Dardo de caos` →
`magia_terror_back.png`, ...).

Se generan con `generar_fondos.py`, misma filosofía que el anverso (**SVG =
fuente de verdad**, rasterizado a PNG con `resvg`), en formato 1000×1400
(proporción 63×88 de la carta). Cada escena reserva **bandas oscuras arriba y
abajo** para que el banner y la leyenda que pinta la carta encima se lean bien.
Los SVG fuente quedan en `sources/arte_fondos_svg/`.

**Reverso por defecto según la categoría.** Al generar una carta completa, el
reverso usa **automáticamente** el fondo temático de su categoría (`equipo`,
`tesoro`, `enemigo`, `heroe`, `magia`) si existe en `sources/arte_fondos/`; si no,
cae a la foto estándar del tipo (`sources/reversos/`). Para **forzar otro fondo**,
pasa `--fondo_verso <fichero>.png` a `carta_item.py` (o `--fondo` a
`imprimir_cartas.py`).

```bash
uv run juegos/heroquest/scripts/generar_fondos.py               # regenera todos
uv run juegos/heroquest/scripts/generar_fondos.py --solo magia  # solo uno
uv run juegos/heroquest/scripts/generar_fondos.py --svg-solo    # SVG sin PNG
```

> **Glifos de librerías libres.** Algunas escenas incrustan **paths de iconos de
> librerías libres** (p. ej. el rayo de agua de *Material Design Icons*, Apache
> 2.0, vía [SVG Repo](https://www.svgrepo.com/); también se pueden usar
> [freesvg.org](https://freesvg.org/) o la sección de SVGs gratuitos de
> [Magnific](https://www.magnific.com/free-photos-vectors/free-svg)). El path se
> incrusta directamente en el SVG que genera el script (con su color original y
> su atribución), así la escena sigue siendo reproducible y autocontenida.

Para usar un fondo en el reverso de una carta, pásalo con `--fondo_verso` (busca
en `sources/arte_fondos/`) junto a `--carta_completa`:

```bash
uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego" \
  --carta_completa --fondo_verso magia_back.png --formato png
```

Para **añadir o mejorar** un fondo, edita su función de escena en
`generar_fondos.py` reutilizando las piezas comunes (`_muro`, `_luz`, `_antorcha`,
`_bandas`, `_vineta`, `_espada`) y regenéralo, iterando mirando el PNG.

### Imprimir cartas en PDF (`scripts/imprimir_cartas.py`)

Genera un **PDF A4** con las cartas listas para imprimir en casa. Cada carta se
maqueta como **hoja plegable**: anverso y reverso lado a lado en la misma cara del
papel. Imprimes a una sola cara, recortas por las marcas de corte, **doblas por la
línea de pliegue** central y metes la carta (ya con sus dos caras) en un protector.

- Tamaño **real** 63 × 88 mm por cara (126 × 88 mm la pieza plegable), a 300 DPI.
- **3 piezas por hoja A4**, con marcas de corte en las esquinas y marca de pliegue.
- El **reverso** de cada carta usa automáticamente el fondo temático de su
  categoría (`equipo`/`tesoro`/`enemigo`/`heroe`/`magia`) si existe en
  `sources/arte_fondos/`. Con `--fondo <fichero>.png` fuerzas el mismo fondo para
  todas las cartas del PDF.
- Usa Pillow para el PDF (sin dependencias nuevas de peso); el YAML necesita
  `pyyaml` (ya en `pyproject.toml`).

Tres formas de indicar qué cartas imprimir:

```bash
# 1) Todo el mazo del juego
uv run juegos/heroquest/scripts/imprimir_cartas.py --todo --salida mazo.pdf

# 2) Un listado en YAML (con cantidades opcionales)
uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml

# 3) Cartas sueltas por la línea de comandos (repetible)
uv run juegos/heroquest/scripts/imprimir_cartas.py --carta "arma:Espada corta" --carta "monstruo:Orco"
```

Formato del YAML (ver [mazo_ejemplo.yml](mazo_ejemplo.yml)):

```yaml
cartas:
  - personaje: Bárbaro
  - arma: Espada corta
  - monstruo: Orco
    cantidad: 3        # nº de copias (opcional, por defecto 1)
  - hechizo: Bola de fuego
```

Los PDF se guardan en `juegos/heroquest/cartas/` (ignorado por git); usa
`--salida <ruta>` para otra ubicación.

### Arquitectura de las cartas (`scripts/tipos_carta/`)

Cada tipo de carta vive en su propio módulo dentro del paquete `tipos_carta/` y
declara su lógica: campos y estadísticas, validación, descripción, arte frontal y
reverso. `nueva_carta.py` (creación) y `carta_item.py` (dibujo, vía `render_carta.py`)
son orquestadores que consumen esas definiciones desde un registro común
(`tipos_carta/registro.py`), sin conocer los detalles de cada tipo. Añadir un tipo
nuevo es crear un módulo y registrarlo. `render_carta.py` dibuja el anverso en dos
familias de maquetación: `stats` (personaje, monstruo) y `descripcion` (arma,
armadura, poción, hechizo), tanto en SVG como en PNG.

### Plantillas de carta (`sources/plantillas/` y `scripts/plantillas.py`)

La **estructura completa de la carta** (marco, banners, leyendas "HeroQuest" y de
categoría, tabla de estadísticas, footer) ya **no está hardcodeada en Python**:
vive como ficheros **SVG plantilla editables** (en Inkscape, p. ej.) bajo
`sources/plantillas/`. Igual que con los tableros y el arte, el **SVG es la fuente
de verdad**; `render_carta.py` solo inyecta el contenido dinámico.

Hay una plantilla **por familia**, para anverso y reverso:

| Fichero | Cara | Familia | Contenido |
|---------|------|---------|-----------|
| `anverso_stats.svg` | anverso | stats (héroes, monstruos) | banner de nombre y **arte que llega hasta el borde inferior**, con el cuadro de estadísticas **superpuesto** sobre la parte baja del arte |
| `anverso_descripcion.svg` | anverso | descripcion (armas, armaduras, pociones, hechizos) | título, arte enmarcado, subtítulo, descripción y línea de stats |
| `verso_stats.svg` | reverso | stats | banner "HeroQuest", panel central para la **descripción** (el héroe la muestra aquí; el monstruo la deja vacía) y leyenda de categoría |
| `verso_descripcion.svg` | reverso | descripcion | banner "HeroQuest" y leyenda de categoría (reverso genérico) |
| `stats_cuadro.svg` | — | stats | **cuadro de estadísticas** de 5 columnas (héroe/monstruo) que se coloca dentro del ancla `ph-stats` de `anverso_stats.svg`; celdas semitransparentes que se ven sobre el arte. Marcadores `{{LABEL1..5}}`, `{{VALOR1..5}}`, `{{COLOR}}` |

**Contrato de plantilla** (documentado en cada `.svg` y en `plantillas.py`):

- **Marcadores de texto** `{{CLAVE}}` dentro de `<text>`/`<tspan>` o de atributos:
  `{{NOMBRE}}`, `{{SUBTITULO}}`, `{{LEYENDA}}` y `{{COLOR}}` (color de acento del
  tipo). Se sustituyen por su valor (los textos se escapan; `{{COLOR}}` va tal cual).
- **Elementos "ancla"** con `id="ph-*"`: cajas `<rect>` invisibles cuya **geometría**
  (`x`, `y`, `width`, `height`) lee el código para colocar encima el contenido
  generado. El `<rect>` desaparece de la carta final:
  - `id="ph-arte"` → área de arte (imagen del objeto/personaje; en la familia
    stats llega hasta el borde inferior de la carta),
  - `id="ph-stats"` → en la familia descripcion, la línea de estadísticas; en la
    familia stats, la caja donde se coloca el cuadro `stats_cuadro.svg`
    superpuesto sobre el arte,
  - `id="ph-descripcion"` → bloque de texto de la descripción,
  - `id="ph-fondo"` → imagen de fondo temática del reverso (`sources/arte_fondos/`).

Puedes **mover o redimensionar** cualquier ancla en Inkscape y el contenido se
recoloca solo. Los marcadores `{{...}}` e `id="ph-*"` sobreviven a un guardado de
Inkscape. Tras editar una plantilla, comprueba el resultado regenerando una carta
(`carta_item.py`) y mirando el PNG. El módulo `scripts/plantillas.py` es el loader
(cachea las plantillas, lee las anclas y sustituye los marcadores).

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
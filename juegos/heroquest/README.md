# HeroQuest

Juego de mesa clásico de mazmorras. Esta carpeta contiene los datos y scripts del juego.

## Datos (`data/`)

Ficheros JSON con el contenido del juego:

- `personajes.json` — Héroes (clase, ataque, defensa, cuerpo, mente, movimiento)
- `equipo.json` — Equipo de batalla: armas, armaduras, pociones y herramientas (subtipo, ataque, defensa, coste); los bastones/vara llevan `hechizos_aprendibles` (nº de hechizos que pueden memorizar; 1 por defecto)
- `tesoros.json` — Cartas del mazo de Tesoro (Gema, Oro, Joyas, Peligro, Pociones Heroica/Defensa/Fuerza/Curativa, Monstruo Errante, Nada)
- `artefactos.json` — Artefactos y objetos mágicos (Armadura de Borin, Vara de Telekinesis, Elixir de Vida, Espadas mágicas, Anillos, Talismán, Varita, Capa y Bastón del Mago, etc.)
- `monstruos.json` — Enemigos (ataque, defensa, cuerpo, mente, movimiento)
- `hechizos.json` — Conjuros y cartas de magia (nombre, escuela, coste_mente por carta, coste_aprendido, descripcion)
- `reglas.json` — **Normas canónicas del juego** agrupadas por categorías y
  mecánicas editables (combate, magia, trampas, turnos, tesoros, misiones...).
  Es editable: amplía o ajusta mecánicas libremente y el agente lo consulta como
  referencia de reglas (junto a la V2 de HQ.es)
- `misiones.json` — Misiones montables en tablero (con coordenadas en la cuadrícula)
- `tableros.json` — Los tableros del juego: "El Original" (generado desde el SVG
  de Wikipedia, CC BY-SA 4.0 / GFDL) y "Cara B" (pendiente de su SVG). Se genera
  de forma reproducible con `tablero_svg.py` (ver más abajo)
- `fuentes.json` — Registro del material externo descargable (PDFs de reglas,
  misiones, cartas y expansiones) para el RAG. Filtrable por categoría,
  expansión y prioridad (ver [rag/README.md](rag/README.md)). Aquí se marca la
  **fuente de verdad** de las reglas: la **V2 de HeroQuest.es** (sistema de la
  comunidad, `expansion: "Remake HQ.es"`). El manual oficial de Hasbro 2021 se
  conserva como fuente **secundaria** de consulta
- `impresion3d.json` — Enlaces gratuitos a archivos 3D imprimibles para Hero Quest:
  plataformas de descarga, colecciones y modelos concretos (héroes, monstruos,
  mobiliario, puertas, tablero y dados), con su licencia cuando se conoce
- `impresion3d_warhammer40k.json` — Enlaces gratuitos a archivos 3D imprimibles
  para Warhammer 40K, mismo esquema que `impresion3d.json`. Categorizado por
  facciones: marines del caos, demonios del caos (incluido el Soul Grinder de
  Khorne), tiránidos, eldars/aeldari, t'au, orkos, necrones y marines espaciales
  proxy, además de terreno y plantillas de tablero

### Herramientas IA para generar modelos 3D (STL)

Además de los repositorios de modelos ya imprimidos de `impresion3d.json`, para
**generar un modelo 3D desde cero** —a partir de una imagen o de un prompt— se
pueden usar estas herramientas IA (recopiladas en la
[issue #1](https://github.com/IngenieroGeomatico/gestor_juegos_aplicaciones/issues/1)):

| Herramienta | Enlace | Qué hace |
|-------------|--------|----------|
| **Meshy AI** | https://meshy.ai | Modelos 3D desde texto o imágenes; exporta OBJ/FBX/GLB (convertibles a STL). Plan gratuito |
| **Tripo AI** | https://www.tripo3d.ai | Generación rápida desde texto o imagen; útil para prototipos, figuras y objetos |
| **MakerWorld MakerLab** | https://makerworld.com | Herramientas IA orientadas a impresión 3D; integración Bambu Lab. Gratuito |
| **Spline AI** | https://spline.design | Escenas y objetos 3D mediante prompts; exporta formatos estándar |
| **Luma AI** | https://lumalabs.ai | Modelos 3D desde imágenes y texto; opciones gratuitas con límites |
| **Hunyuan3D** | https://github.com/Tencent/Hunyuan3D | Open source; desde imágenes o texto, ejecutable localmente |
| **Stable Fast 3D** | https://github.com/Stability-AI/stable-fast-3d | Open source (Stability AI); generación rápida desde imágenes, local |
| **OpenSCAD + LLM** | https://openscad.org | Código paramétrico OpenSCAD generado con IA; ideal para piezas funcionales/mecánicas |
| **Fusion 360 (Generative Design)** | https://www.autodesk.com/products/fusion-360 | Ingeniería y piezas mecánicas; exportación directa a STL |
| **Rodin Gen-1** | https://hyper3d.ai | Alta calidad desde imágenes y texto; gaming, miniaturas y activos 3D |
| **Masterpiece X** | https://masterpiecex.com | Plataforma profesional de modelos 3D mediante IA |
| **Kaedim** | https://www.kaedim3d.com | Conversión de conceptos 2D a 3D; producción y videojuegos |

Recomendación por uso: **figuras, miniaturas y objetos decorativos** → Meshy AI,
Tripo AI o Rodin; **piezas mecánicas y funcionales** → OpenSCAD + IA o Fusion 360;
**soluciones open source/locales** → Hunyuan3D o Stable Fast 3D; **impresión 3D
doméstica** → MakerWorld MakerLab.

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

El agente se apoya en:

- **`skills/`** — conocimiento del juego: reglas, narrativa, balance de combate,
  tienda y creación de misiones.
- **`tools/`** — acceso programático a los datos (personajes, armas, monstruos,
  hechizos, misiones, tableros y fuentes).
- **`rag/`** — búsqueda sobre las reglas y el material oficial descargado
  (ver [rag/README.md](rag/README.md)).

> **Fuente de verdad de las reglas.** El agente genera contenido coherente con
> el sistema de la **V2 de HeroQuest.es** (remake de la comunidad, licencia
> CC BY-NC-SA). Ante cualquier conflicto de reglas, prima la V2 sobre el manual
> oficial de Hasbro 2021, que se usa solo como referencia/consulta.

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

# Generar la carta de un héroe, monstruo o item (anverso y/o dorso) en PNG/SVG
uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro" --cara ambas --formato png

# Imprimir cartas de héroe en PDF A4 (junta = pliegue; separada = doble cara, 9/hoja)
uv run juegos/heroquest/scripts/imprimir_cartas.py --todo
uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml --disposicion separada

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

`carta_item.py` genera la carta de un **héroe, monstruo o item** con aspecto de
carta de HeroQuest: los héroes y monstruos usan las plantillas hero-card /
monster-card (motor `render_personaje.py`) y los items —armas, armaduras,
pociones y hechizos— la plantilla generic-card (motor `render_generico.py`).
Elige la cara con `--cara {anverso,dorso,ambas}` y el formato con
`--formato png,svg`:

```bash
uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro"
uv run juegos/heroquest/scripts/carta_item.py --nombre "Trasgo" --cara ambas --formato png,svg
uv run juegos/heroquest/scripts/carta_item.py --nombre "Bola de fuego"
```

Se guarda en `juegos/heroquest/cartas/` (ignorado por git); usa `--salida <ruta>`
para otra ubicación. La receta de la carta (plantillas y assets, para anverso y
dorso) vive en el propio JSON de la entrada (ver "Cartas por plantillas" más
abajo).

`preparar_reversos.py` recorta y endereza las fotos `*_back.jpg` de `sources/`
(las cartas reales por su cara trasera) y deja los reversos limpios en
`sources/reversos/` (ignorado por git).

### El arte del anverso (`scripts/generar_arte.py` y `sources/arte/`)

La ilustración que aparece dentro de cada carta (la espada, el hacha, la poción…)
se guarda como PNG en `sources/arte/` y el motor la localiza **por convención de
nombre**: busca `sources/arte/<slug(nombre)>.png` (p. ej. `Espada_corta.png`,
`Báculo_del_mago.png`). La receta del héroe también puede apuntar a un fichero
concreto con `arte_personaje`.

Ese arte se genera de forma **reproducible y editable** con `generar_arte.py`,
siguiendo la misma filosofía que los tableros (**SVG = fuente de verdad**):

- Cada objeto se dibuja como un **SVG vectorial** de 700×500 sobre el fondo
  degradado morado característico. El volumen (metal biselado, oro, cuero, gemas)
  se consigue con **degradados** (`<linearGradient>`/`<radialGradient>`), un
  reflejo de lustre semitransparente y una **sombra suave** (`feDropShadow`).
- El SVG se **rasteriza a PNG con `resvg`** (`resvg_py`, la misma librería que usa
  el motor de render), así que no hay dependencias ni pasos manuales.
- Los SVG fuente se conservan en `sources/arte_svg/` (versionables y editables);
  los PNG finales van a `sources/arte/` con el nombre de convención.

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
el `slug` del nombre (`Bárbaro.png`, `Guerrero_del_Caos.png`, …), así que el
motor los usa por la misma convención. Comparten `sources/arte_svg/` y
las piezas de dibujo comunes (`_cabeza`, `_ojos`, `_cejas`, `_hombros`, `_cuello`,
`_nariz`), y cada personaje añade sus rasgos distintivos (melena, orejas
puntiagudas, sombrero de mago, ojo único del Fimir, cuernos del Caos, alas de
piedra de la Gárgola). El lienzo del retrato es **vertical (520×600)**, con una
proporción cercana a la del área de arte de la carta del héroe, para que el busto
se vea grande y completo (cabeza arriba, hombros abajo) sin que el recorte
"cover" lo corte por los lados.

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

Estos fondos son la biblioteca de escenas ambientales del repo. En la carta de
héroe, el fondo del dorso se elige en la receta del JSON (`plantillas.dorso.archivos_fondo`).

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

Para **añadir o mejorar** un fondo, edita su función de escena en
`generar_fondos.py` reutilizando las piezas comunes (`_muro`, `_luz`, `_antorcha`,
`_bandas`, `_vineta`, `_espada`) y regenéralo, iterando mirando el PNG.

### Imprimir cartas en PDF (`scripts/imprimir_cartas.py`)

Genera un **PDF A4** con las cartas de **héroe** listas para imprimir, a tamaño
real 63 × 88 mm y 300 DPI, con **cruces negras de corte**. Dos disposiciones con
`--disposicion`:

- **`junta`** (por defecto): anverso y dorso lado a lado en la **misma hoja** con
  línea de pliegue central. Imprimes a una cara, recortas, doblas por el pliegue y
  metes la carta (ya con sus dos caras) en un protector. 3 piezas por hoja.
- **`separada`**: anversos y dorsos en **hojas distintas**, con los dorsos
  espejados para imprimir a **doble cara** (cada dorso queda detrás de su
  anverso). Caben **3×3 = 9 cartas por hoja**.

Solo se imprimen héroes (personajes con receta de plantillas). Tres formas de
indicar qué cartas imprimir:

```bash
# 1) Todos los héroes con carta
uv run juegos/heroquest/scripts/imprimir_cartas.py --todo --salida mazo.pdf

# 2) Un listado en YAML (con cantidades opcionales)
uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml --disposicion separada

# 3) Héroes sueltos por la línea de comandos (repetible)
uv run juegos/heroquest/scripts/imprimir_cartas.py --carta "Bárbaro" --carta "Mago"
```

Formato del YAML (ver [mazo_ejemplo.yml](mazo_ejemplo.yml)):

```yaml
cartas:
  - personaje: Bárbaro
  - personaje: Mago
    cantidad: 2        # nº de copias (opcional, por defecto 1)
```

Los PDF se guardan en `juegos/heroquest/cartas/` (ignorado por git); usa
`--salida <ruta>` para otra ubicación.

## Cartas por plantillas (motor guiado por datos)

Las cartas las compone el motor a partir de una *receta* que vive en el propio
JSON de la entrada —héroe, monstruo o item— bajo la clave `plantillas` (con dos
caras, `cara` y `dorso`). Ejemplo de un héroe:

```json
"plantillas": {
  "cara": {
    "plantilla_padre": "sources/plantillas/hero-card-up.svg",
    "plantilla_estadisticas": "sources/plantillas/hero-stats.svg",
    "plantilla_leyenda": "sources/plantillas/ribbon.svg",
    "arte_personaje": "sources/arte/bárbaro_1.png",
    "arte_icono": "sources/arte_iconos/bárbaro_1.png",
    "archivos_fondo": ["sources/arte_fondos/parchment.png"]
  },
  "dorso": {
    "plantilla_padre": "sources/plantillas/hero-card-down.svg",
    "plantilla_logo": "sources/plantillas/hero-back-just-logo.svg",
    "archivos_fondo": [
      "sources/arte_fondos/parchment_eye.png",
      "sources/plantillas/hero-back-just-border.svg"
    ]
  }
}
```

El motor admite tres familias, todas guiadas por estas plantillas de
`sources/plantillas/`:

- **Héroes** (hero-card, motor `render_personaje.py`)
- **Monstruos** (monster-card, también `render_personaje.py`)
- **Items** —armas, armaduras, pociones y hechizos— (generic-card, motor
  `render_generico.py`)

**El SVG es la fuente de verdad.** Las plantillas de `sources/plantillas/` se
editan a mano (Inkscape); el motor solo inyecta contenido sobre sus **anclas**
`id="ph-*"` (rectángulos invisibles cuya geometría se lee). En las cartas de
héroe, por ejemplo:

- **Anverso:** `ph-arte` (retrato), `ph-ribbon` (nombre), `ph-stats` (cuadro de
  estadísticas), `ph-icon` (icono).
- **Dorso:** `ph-heroquest` (logo) y `ph-texto` (biografía: "Eres el {clase}." en
  negrita + la descripción debajo).
- **`archivos_fondo`** es una lista en orden de renderizado: el primero va **más
  abajo** y cada siguiente se superpone. Admite imágenes (PNG/JPG) y SVG (p. ej.
  el borde), que se incrusta escalado a la carta.

El módulo `scripts/plantillas.py` es el loader (cachea las plantillas, lee las
anclas y sustituye los marcadores `{{...}}`).

> Cualquier entrada nueva de `personajes.json`, `monstruos.json`, `equipo.json`,
> `tesoros.json`, `artefactos.json` o `hechizos.json` necesita su bloque
> `plantillas` para poder renderizar su carta;
> sin él se gestiona como dato (`nueva_carta.py`, `listar.py`, `eliminar.py`)
> pero no tiene carta.

### Dar carta a una entrada nueva

1. Añade la entrada a su JSON (o con `nueva_carta.py --tipo <tipo>`).
2. Añade su bloque `plantillas` con las recetas de `cara` y `dorso`.
3. Coloca sus assets en `sources/` (arte del retrato, icono y fondos).
4. Genera y revisa: `carta_item.py --nombre "<nombre>" --cara ambas`.

Esquema de las salas de una misión (`salas.json`), usado por `nueva_mision.py`
(valida además que cada monstruo/tesoro caiga dentro de la sala y del tablero):

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

### Recursos externos en `sources/`

Además de las fotos y el arte propio, `sources/` contiene librerías externas
(arte de cartas generado con IA, fondos de carta estilo HQ 2021 y la fuente
Amarna, tipografía libre de las cartas). El origen y la licencia de cada una están
documentados en [sources/ATRIBUCIONES.md](sources/ATRIBUCIONES.md); consulta ese
fichero antes de reutilizar cualquier archivo ajeno.
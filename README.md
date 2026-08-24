# gestor_juegos_aplicaciones

Repositorio para gestionar distintos juegos y aplicaciones. Cada juego o
aplicación vive en su propia carpeta, con sus datos (JSON), sus scripts de
Python y, normalmente, un agente de opencode especializado.

## Estructura

```
├── juegos/               # juegos de mesa, videojuegos, ...
│   └── heroquest/        # datos, scripts y README del juego
├── aplicaciones/         # para futuras aplicaciones (pagos, etc.)
├── .opencode/
│   └── agent/            # agentes IA por juego/aplicación
└── pyproject.toml        # proyecto Python (uv)
```

## Puesta en marcha

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.12+.

```bash
uv sync        # crea el entorno virtual en .venv
uv run <script>   # ejecuta cualquier script dentro del entorno
```

## Juegos y aplicaciones

| Nombre | Tipo | Contenido | Agente |
|--------|------|-----------|--------|
| HeroQuest | Juego de mesa | héroes, armas, monstruos, misiones, tableros | `heroquest` |
| Pokémon Champions | Combate competitivo | pokedex, movimientos, equipos, sets | `pokemon-champions` |

Cómo trabajar con **HeroQuest**: ver [juegos/heroquest/README.md](juegos/heroquest/README.md).
Para añadir un nuevo juego o aplicación, sigue el patrón de `juegos/heroquest/`.

## Agentes

Los agentes de opencode (`opencode agent` para seleccionar uno) conocen las
reglas del juego y los datos del repositorio, y generan contenido coherente
con el sistema. Los scripts de Python realizan las tareas concretas
(añadir/borrar/listar contenido en los JSON).

## Creación de cartas de HeroQuest

El sistema genera cartas de HeroQuest usando un flujo basado en plantillas SVG
y datos JSON. Aquí tienes el flujo completo:

### Estructura de datos

Los datos de las cartas viven en `juegos/heroquest/data/` en ficheros JSON:
- `personajes.json` — Héroes (clase, ataque, defensa, cuerpo, mente, movimiento)
- `armas.json` — Armas, armaduras y pociones (tipo, ataque, defensa, coste, descripción)
- `monstruos.json` — Enemigos (ataque, defensa, cuerpo, mente, movimiento)
- `hechizos.json` — Conjuros (nombre, escuela, coste_mente, descripción)

Cada tipo declara sus campos en `scripts/tipos_carta/` (módulos `personaje.py`,
`arma.py`, `monstruo.py`, `hechizo.py`, etc.) y registrados en
`scripts/tipos_carta/registro.py`.

### Plantillas SVG

La estructura visual de la carta (marco, banners, tabla de estadísticas, áreas de arte)
vive en ficheros SVG editables bajo `juegos/heroquest/sources/plantillas/`. Igual que
con los tableros, el **SVG es la fuente de verdad**.

Plantillas disponibles (5 familias principales):

| Fichero | Familia | Descripción |
|---------|---------|-------------|
| `anverso_stats.svg` | stats | Héroes y monstruos: banner, arte que llega al borde inferior, tabla de 5 stats |
| `anverso_descripcion.svg` | descripcion | Armas, armaduras, pociones, hechizos: título, arte enmarcado, subtítulo, descripción, línea de stats |
| `verso_stats.svg` | stats | Reverso para héroes: muestra descripción, leyenda de categoría |
| `verso_descripcion.svg` | descripcion | Reverso para armas/pociones/hechizos: banner "HeroQuest" y leyenda |
| `stats_cuadro.svg` | stats | Cuadro de 5 columnas que se posa sobre el área `ph-stats` del anverso |

Cada plantilla usa dos tipos de marcadores:

1. **Marcadores de texto** `{{CLAVE}}` dentro de `<text>` o `<tspan>`:
   - `{{NOMBRE}}` — Nombre de la carta
   - `{{SUBTITULO}}` — Línea debajo del título (clase/escuela/tipo)
   - `{{LEYENDA}}` — Leyenda inferior (categoría del reverso)
   - `{{COLOR}}` — Color de acento del tipo (en hex, ej `#5d4037`)

2. **Elementos "ancla"** con `id="ph-*"` (elementos `<rect>` invisibles):
   - `id="ph-arte"` — Área donde se coloca el arte/imagen del objeto
   - `id="ph-stats"` — Donde se posiciona el `stats_cuadro.svg` (anverso stats) o la línea de stats (anverso descripción)
   - `id="ph-descripcion"` — Bloque de texto descriptivo
   - `id="ph-fondo"` — Imagen de fondo temático del reverso (en `sources/arte_fondos/`)

El diseñador puede mover o redimensionar cualquier ancla en Inkscape y el contenido
se recoloca automáticamente. Los marcadores `{{...}}` e `id="ph-*"` sobreviven a un
guardado de Inkscape.

### Generando una carta individual

Usa `carta_item.py` desde la raíz del repositorio con `uv run`:

```bash
# Generar anverso PNG de un personaje
uv run juegos/heroquest/scripts/carta_item.py --tipo personaje --nombre "Bárbaro" --output barra.png

# Generar anverso PNG de un hechizo con fondo de fuego
uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego" \
  --fondo_verso magia_fuego_back.png --formato png

# Generar hoja plegable PDF
uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml --salida mazo.pdf
```

### Añadiendo un nuevo tipo de carta

Para añadir un nuevo tipo de carta:

1. Crea un nuevo módulo en `juegos/heroquest/scripts/tipos_carta/` heredando de `TipoCarta`
   e implementando `campos()`, `stats()`, `subtitulo()`, y opcionalmente `familia_fondo()`.

2. Registra el nuevo tipo en `scripts/tipos_carta/registro.py`.

3. Crea o adapta las plantillas SVG en `sources/plantillas/` con los marcadores
   `{{NOMBRE}}`, `{{SUBTITULO}}`, etc. y los `id="ph-*"` apropiados.

4. Añade los datos de ejemplo en los ficheros JSON correspondientes en `data/`.

### Recursos externos

- `sources/arte_fondos_hq2021/` — 15 fondos PNG de carta (fondos parchment, marcos,
  ribbons) descargados de [heroquest-card-creator](https://github.com/alexbernard/heroquest-card-creator).
- `sources/arte/` — Arte del anverso (retratos de héroes, ilustraciones de armas).
- `sources/reversos/` — Reversos de cartas ya recortados/enderezados.
- `sources/ATRIBUCIONES.md` — Licencias y atribución de recursos externos.

Para incorporar arte o fondos de la comunidad, deja el material en `sources/` y
consulta el agente `heroquest` para convertirlo al formato adecuado.
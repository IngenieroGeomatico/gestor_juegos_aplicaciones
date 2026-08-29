# gestor_juegos_aplicaciones

Repositorio para gestionar distintos juegos y aplicaciones. Cada juego o
aplicación vive en su propia carpeta, con sus datos (JSON), sus scripts de
Python y, normalmente, un agente de opencode especializado.

## Estructura

```
├── juegos/               # juegos de mesa, videojuegos, ...
│   └── heroquest/        # datos, scripts, assets y README del juego
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
| HeroQuest | Juego de mesa | héroes, armas, monstruos, misiones, tableros, modelos 3D | `heroquest` |
| Pokémon Champions | Combate competitivo | pokedex, movimientos, equipos, sets | `pokemon-champions` |

Cómo trabajar con **HeroQuest**: ver [juegos/heroquest/README.md](juegos/heroquest/README.md).
Para añadir un nuevo juego o aplicación, sigue el patrón de `juegos/heroquest/`.

## Agentes

Los agentes de opencode (`opencode agent` para seleccionar uno) conocen las
reglas del juego y los datos del repositorio, y generan contenido coherente
con el sistema. Los scripts de Python realizan las tareas concretas
(añadir/borrar/listar contenido en los JSON).

El agente de HeroQuest, además, se apoya en `skills/` (reglas, balance,
narrativa), `tools/` (acceso a datos) y un sistema **RAG** de búsqueda sobre
el material oficial en `rag/` (ver [juegos/heroquest/README.md](juegos/heroquest/README.md)).

## Creación de cartas de HeroQuest

Las **cartas** se generan con un motor guiado por datos: `render_personaje.py`
compone las cartas de **héroes y monstruos**, y `render_generico.py` las de
**items** (armas, armaduras, pociones y hechizos). La *receta* de cada carta
(plantillas SVG y assets, para anverso y dorso) vive en el propio JSON de la
entrada, bajo `plantillas`. El **SVG es la fuente de verdad**; el motor solo
inyecta contenido sobre las anclas `id="ph-*"` de las plantillas de
`juegos/heroquest/sources/plantillas/`.

### Receta de la carta (en `personajes.json`)

Cada héroe declara, bajo la clave `plantillas`, sus dos caras:

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

- **Anclas** `id="ph-*"` (rectángulos invisibles cuya geometría lee el motor).
  Anverso: `ph-arte`, `ph-ribbon` (nombre), `ph-stats`, `ph-icon`. Dorso:
  `ph-heroquest` (logo) y `ph-texto` (biografía: "Eres el {clase}." en negrita +
  la descripción).
- **`archivos_fondo`** es una lista en orden de renderizado: el primero va más
  abajo y cada siguiente se superpone. Admite PNG/JPG y SVG (p. ej. el borde).

### Generando una carta individual

```bash
# Anverso PNG del Bárbaro
uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro"

# Ambas caras (anverso y dorso) en PNG y SVG
uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro" --cara ambas --formato png,svg

# PDF A4 para imprimir (junta = pliegue; separada = doble cara, 9 por hoja)
uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml --disposicion separada
```

### Dando carta a un héroe nuevo

1. Añade el héroe a `personajes.json` (o con `nueva_carta.py --tipo personaje`).
2. Añade su bloque `plantillas` con las recetas de `cara` y `dorso`.
3. Coloca sus assets (arte del retrato, icono, fondos) en `sources/`.
4. Genera y revisa con `carta_item.py --nombre "<héroe>" --cara ambas`.

### Recursos externos

- `sources/arte_fondos_hq2021/` — 15 fondos PNG de carta (fondos parchment, marcos,
  ribbons) descargados de [heroquest-card-creator](https://github.com/alexbernard/heroquest-card-creator).
- `sources/arte/` — Arte del anverso (retratos de héroes, ilustraciones de armas).
- `sources/fuentes/` — Fuente **Amarna** (tipografía libre de las cartas, OFL-1.1).
- `sources/ATRIBUCIONES.md` — Licencias y atribución de recursos externos.

Para incorporar arte o fondos de la comunidad, deja el material en `sources/` y
consulta el agente `heroquest` para convertirlo al formato adecuado.
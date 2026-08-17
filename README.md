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
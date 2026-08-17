# Juegos

Cada juego vive en su propia carpeta. El patrón general es:

```
juegos/<juego>/
├── data/          # contenido del juego en JSON
├── scripts/       # utilidades Python (ejecutar con `uv run ...`)
└── README.md      # documentación del juego y sus scripts
```

Suele acompañarse de un agente de opencode en `.opencode/agent/<juego>.md`
especializado en generar y gestionar el contenido de ese juego.

## Juegos disponibles

- [HeroQuest](heroquest/) — juego de mesa de mazmorras. Agente: `heroquest`.
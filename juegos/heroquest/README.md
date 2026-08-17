# HeroQuest

Juego de mesa clásico de mazmorras. Esta carpeta contiene los datos y scripts del juego.

## Datos (`data/`)

Ficheros JSON con el contenido del juego:

- `personajes.json` — Héroes (clase, ataque, defensa, cuerpo, mente, movimiento)
- `armas.json` — Armas, armaduras y pociones (ataque, defensa, coste)
- `monstruos.json` — Enemigos (ataque, defensa, cuerpo, mente, movimiento)
- `misiones.json` — Misiones montables en tablero (con coordenadas en la cuadrícula)
- `tableros.json` — Los tableros del juego: "El Original" (derivado del SVG de
  Wikipedia, CC BY-SA 4.0 / GFDL) y "Cara B" (pendiente de foto)

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

# Añadir una nueva arma / armadura / poción
uv run juegos/heroquest/scripts/nueva_arma.py --nombre "Espada encantada" --tipo "Arma cuerpo a cuerpo" --ataque 4 --coste 500

# Añadir un nuevo monstruo
uv run juegos/heroquest/scripts/nuevo_monstruo.py --nombre "Basilisco" --ataque 3 --defensa 3 --cuerpo 2 --mente 5

# Añadir un nuevo héroe
uv run juegos/heroquest/scripts/nuevo_personaje.py --nombre "Semielfa" --clase "Ranger" --ataque 2 --defensa 3 --cuerpo 6 --mente 4

# Añadir una nueva misión montable en tablero
# (las salas y sus posiciones van en un JSON, ver esquema más abajo)
uv run juegos/heroquest/scripts/nueva_mision.py --nombre "Las Minas de Karak" --tablero original \
  --objetivo "Salir de la mina" --entrada 13,1 --puerta 9,6 --habitaciones salas.json

# Ver el mapa de un tablero (salas numeradas, '.' = pasillo)
uv run juegos/heroquest/scripts/tablero.py ver --tablero original

# Validar que todas las misiones caben en sus tableros
uv run juegos/heroquest/scripts/tablero.py validar

# Generar una imagen (PNG/SVG) del tablero o de una misión montada
uv run juegos/heroquest/scripts/mapa.py --tablero original --mision "El Refugio del Guardián" --svg

# Eliminar una entrada por nombre
uv run juegos/heroquest/scripts/eliminar.py --tipo monstruos --nombre "Basilisco"
```

`mapa.py` deja las imágenes en `juegos/heroquest/mapas/` (ignoradas por git); usa
`--salida <ruta>` para elegir dónde guardarlas. Dibuja las salas por colores, los
pasillos, y sobre la misión: entrada (verde), puertas (marrón), monstruos (rojo)
y tesoros (dorado), con su leyenda.

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
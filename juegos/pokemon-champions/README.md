# Pokémon Champions

Herramientas para jugar como **entrenador Pokémon legendario** en el juego de
combate competitivo Pokémon Champions: generar sets, construir equipos y
analizar cobertura de tipos.

## Datos (`data/`)

Ficheros JSON en español:

- `pokedex.json` — especies: `{ numero, nombre, tipos[], stats{ps, ataque, defensa,
  ataque_esp, defensa_esp, velocidad}, habilidades[], legendario, movimientos[] }`
- `movimientos.json` — movimientos: `{ nombre, tipo, categoria (Físico/Especial/Estado),
  potencia, precision, pp }`
- `tipos.json` — chart de tipos (18 tipos): `{ tipo, debilidades[], resistencias[], inmunidades[] }`
- `equipos.json` — equipos guardados: `{ nombre, pokemon[] { especie, tipos[], rol } }`
- `meta.json` — ranking actual por formato (Singles/Doubles) con el set
  recomendado de cada especie: `{ posicion, nombre, tipos[], movimientos[],
  objeto, naturaleza, habilidad, companeros[] }`

> `pokedex.json`, `movimientos.json` y `meta.json` se generan desde la API de
> datos reales de championsbattledata.com y se traducen a español con PokeAPI.
> Para regenerarlos o actualizarlos: `uv run
> juegos/pokemon-champions/scripts/importar_datos.py` (usa `--sin-cache` para
> redescargarlo todo). Las respuestas crudas de ambas APIs quedan cacheadas en
> `data/cache/` (ignorado por git).

## Fuentes de datos

- **championsbattledata.com** — API de datos reales de batalla:
  https://championsbattledata.com/api_guide (requiere cabecera `User-Agent`;
  ver `/api/index`, `/api/pokemon/:slug`, `/api/metadata/:slug`,
  `/api/battle/:formato/:slug`).
- **pokebase.app** — base de datos comunitaria de Pokémon Champions (Pokémon,
  movimientos, objetos, habilidades, torneos): https://pokebase.app/pokemon-champions

## Scripts (`scripts/`)

Ejecutar desde la raíz del repositorio con `uv run`:

```bash
# Set competitivo de una especie (naturaleza, EVs, objeto, habilidad, movimientos)
uv run juegos/pokemon-champions/scripts/generador_set.py --pokemon "Groudon"
uv run juegos/pokemon-champions/scripts/generador_set.py --pokemon "Ho-Oh" --rol tanque

# Construir un equipo (hasta 6), guardarlo y ver su cobertura
uv run juegos/pokemon-champions/scripts/constructor_equipos.py \
  --pokemon Groudon --pokemon Rayquaza --pokemon "Ho-Oh" --nombre "Equipo legendario"
uv run juegos/pokemon-champions/scripts/constructor_equipos.py --auto --nombre "Autobot"

# Analizar cobertura de tipos de un equipo o de un grupo
uv run juegos/pokemon-champions/scripts/cobertura_tipos.py --equipo "Equipo legendario"
uv run juegos/pokemon-champions/scripts/cobertura_tipos.py --pokemon Groudon --pokemon Rayquaza

# Mejor equipo actual del meta (ambos formatos, o uno solo)
uv run juegos/pokemon-champions/scripts/mejores_equipos.py --meta
uv run juegos/pokemon-champions/scripts/mejores_equipos.py --meta --formato singles

# Mejores equipos a partir de mis Pokémon (JSON con nombres)
uv run juegos/pokemon-champions/scripts/mejores_equipos.py --mis-pokemon mis_pokemons.json
```

- `generador_set.py` deduce el rol de las stats base (sweeper físico/especial,
  tanque, defensivo, utilidad) y elige naturaleza/EVs acordes.
- `constructor_equipos.py` evita duplicados y con `--auto` elige 6 al azar
  priorizando legendarios.
- `cobertura_tipos.py` muestra qué tipos golpea super-efectivamente el equipo,
  sus debilidades defensivas agregadas y las coberturas que faltan.
- `mejores_equipos.py` construye el mejor equipo de 6 a partir del ranking del
  meta (`--meta`) o de un JSON con los Pokémon del usuario (`--mis-pokemon`,
  acepta `["Garchomp", ...]` o `{"pokemon": [...]}`). Combina posición en el
  ranking con cobertura ofensiva y diversidad de tipos, mostrando el set
  recomendado (movimientos, objeto, naturaleza, habilidad) y compañeros
  habituales de cada miembro.

## Agente

El agente **pokemon-champions** de este repositorio actúa como entrenador
legendario: conoce el juego y el chart de tipos, genera sets y equipos
equilibrados y gestiona estos datos. Definición canónica en
`.opencode/agent/pokemon-champions.md` y copia en [AGENT.md](AGENT.md).
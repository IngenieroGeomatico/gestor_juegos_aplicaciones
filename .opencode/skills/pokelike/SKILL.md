---
name: pokelike
description: Úsala cuando el usuario quiera jugar, ejecutar, testear o depurar runs de Pokelike Story en pokelike.xyz, pedir ver un resultado de run, ganar un gimnasio o revisar el estado del bot. Delega el juego al bot autónomo de Python e informa del resultado.
---

# Pokelike

Roguelike de Pokémon en navegador. Las batallas son **automáticas**: no se
juega durante el combate, todo se decide antes con el **orden del equipo**,
**los objetos** y **el nodo que eliges**.

## Regla principal

**No juegues a mano.** Cada clic manual cuesta un turno de LLM y el bot no lo
necesita. Tú lanzas, esperas, lees el log e informas. La estrategia vive en
`scripts/politica.py` y `scripts/planificador.py`, no en tu cabeza.

## Cómo lanzar

Preferido, y **obligatorio** para más de una run:

```bash
uv run --group dev python juegos/pokelike/scripts/lanzar_tanda.py --runs 2 --region Kanto
```

El lanzador se encarga de lo que siempre se olvida: cerrar navegadores y bots
anteriores, comprobar RAM, hacer un **smoke test** antes de gastar horas, y
limpiar logs viejos (conserva 3).

Una sola run suelta:

```bash
uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py --region Kanto --reset
```

| Flag | Significado |
|---|---|
| `--region` | `Kanto` por defecto. |
| `--reset` | Run **nueva** con perfil temporal. Sin él, continúa la guardada. |
| `--max-pasos` | **`0` = sin presupuesto** (por defecto). La partida acaba sola al ganar, perder o atascarse. Un número positivo corta la partida sin que haya terminado: no es ganar ni perder. |
| `--visible` | Navegador visible, para depurar. |

## Reglas de máquina

- Máximo **2 runs** a la vez. La máquina tiene 7 GiB.
- **No** uses `pkill -f jugar_pokelike.py`: el patrón se empareja con el propio
  shell y lo mata. Usa el lanzador.
- Las runs son largas: cuenta con 10-15 min cada una.

## Resultados

| `resultado` | Significado |
|---|---|
| `CAMPEON` | Run completada. El objetivo. |
| `GAME_OVER` | Se agotó el equipo. Fin de la run. |
| `ATASCADO` | Una pantalla no responde; se repite muchas veces. Suele ser un selector roto tras un cambio del sitio. |
| `ERROR_DE_CODIGO` | Excepción en el bot. Esto **sí** es un bug: hay que arreglarlo, no reintentar. |

Perder **no** es un bug del bot. Casi siempre es nivel o composición de equipo.

Cuando sí suele ser bug, y conviene mirar `CAMINO-POR-PANTALLA.md` antes de
suponer otra cosa: entrar a un entrenador por encima del equipo, capturar sin
avantage de tipos, curar sin invalidar los PS reales, o un nodo que se repite
mucho sin que nada cambie. Los cuatro han pasado.

## La tabla de tipos va aparte, y es lo primero que hay que abrir

**`TABLA-TIPOS.md`** (en esta misma skill) tiene el chart **real del juego**, las
dos mitades —con quién pega y quién le pega— y las tres desviaciones que tiene
respecto al Gen 6 oficial. Se lee antes de elegir el delantero, siempre.

La regla que más se ha olvidado: **elegir delantero es mirar el otro lado**. Delante
va el món que **pega x2** al rival **y no recibe x2**, y las dos mitades se leen
por separado.

**El ejemplo del error, porque es facil de repetir — Bulbasaur contra Fuego:**

- `Planta -> Fuego` = **x1/2**: pega la mitad.
- `Fuego -> Planta` = **x2**: recibe el doble.

**Bulbasaur es el peor emparejamiento posible contra un Charmander.** Se llego a
afirmar lo contrario ("Bulbasaur es x2 contra Fuego") leyendo al reves la fila:
el 2 que aparece junto a Planta en la fila de Fuego significa que **Fuego** le
pega el doble a Planta, no que Planta pegue el doble a Fuego. Contra Fuego al
frente van **Agua, Roca o Acero**.

Y para no extremear: contra un rival de **Planta**, Bulbasaur aguanta bien
(Planta -> Planta es x1/2 por los dos lados), así que **sí** debe abrir ahí. El
delantero se decide con la aritmetica de la tabla, no con "este món es bueno".

## Libro de jugadas (el mismo que usa el humano)

**`pokelike-camino`** es la skill hermana: tiene las **8 reglas de juego** (norma
del usuario, mandan sobre el código) y, en `CAMINO-POR-PANTALLA.md`, el camino
completo pantalla por pantalla con los pesos exactos. Se abre **antes de tocar
`planificador.py` o `politica.py`**, porque cambiar un peso puede invertir una
decisión sin que nada falle.

En este orden, en cada nodo:

1. **Pantalla nueva y equipo pequeño → cazar uno.** El primero que sirva: los
   siguientes son más flojos y de menos nivel.
2. **Falta nivel → entrenador.** Sin entrenador, hierba alta.
3. **Curar** si el pokecenter está en camino al jefe (siempre lo está), y no
   pelear por debajo de ~40% con un centro a mano.
4. **A nivel o por encima del líder → Move Tutor y objetos** para el principal.
5. **A un jefe**, el mejor contragolpe al frente y **los móns por debajo del 50%
   de vida al final** del orden (no fuera del equipo: así siguen ganando exp).

Reglas de la guía que no son negociables: llevar **1+ niveles de ventaja**; el
**trade** es el nodo más fuerte (+3 niveles, vuelve con la vida llena y
conserva el Move Tutor); el **Lucky Egg** (+30% de nivel extra por combate) se
coge en cuanto aparece (zona 5); la tecla **R rerola el mapa** para buscar un
trade o mejor exp.

Catálogo completo de objetos y el resto de la guía: **`GUIA-ESTRATEGIA.md`**.

## La guía de la comunidad

<https://pokelike-guide.fr/> — es **una wiki de fans, no el sitio oficial**
(<https://pokelike.xyz> es el juego). Páginas clave: `/en/basics/getting-started/`,
`/en/normal/`, `/en/normal/route-decisions/`, `/en/normal/improving-your-team/`,
`/en/items/`, `/en/mechanics/team-order/`, `/en/battle-tower/`.

**Trampa importante**: la wiki **esconde contenido según tu progreso** para no
hacer spoiler. Casi todo sale vacío si no lo desbloqueas. Se abre el diálogo de
progreso, se marca "I have finished a story campaign" y se pulsa
**"Show everything"**, que guarda en `localStorage['pokelike-profil']`:
`{"campagneTerminee":true,"regionsBT":["kanto",...],"defini":true}`. Con eso la
wiki devuelve el texto entero.

## Trampas del sitio (no las redescubiertas a costa de una run)

- **Los tipos del grafo vienen en inglés**: el jefe es `boss`, el centro es
  `pokecenter`, el tutor es `move_tutor`. Compararlos con palabras en español
  (`jefe`, `cura`) hace que la rama **nunca se ejecute**, sin error ni aviso.
- **El PS del HUD es un porcentaje**, y en un món caído la barra se queda en
  100: el bot veía "100/100" con 0/19 de vida y por eso no curaba. El valor real
  sale de la pantalla de combate (`estado_batalla` → `"0/19"`).
- **El PS se compara por porcentaje**, nunca por vida cruda: con `ps < 50` un
  món con 46/46 contaba como herido.
- **`botón "auto-battle" está etiquetado "SKIP"`.** En un combate de gimnasio son
  normales 12-13 pulsaciones; el bot compara PS antes de declarar atasco.
- **Los clics sintéticos no siempre surten efecto**: se usa el `data-shortcut`
  del control (`Juego.activar()`).
- **`#map-info` se queda vacío** en el mapa. El tipo del líder sale del sprite
  del nodo o de `data/regiones.json`.
- El chart real del juego está en **`data/chart_juego.json`**, y **no** coincide
  con el Gen 6 oficial: Veneno→Tierra/Roca 0.5x, Acero→Dragón 1x,
  Hada→Dragón 2x. No lo "arregles" al oficial.
- **El MCP Firefox no puede jugar**: ni clic ni teclado avanzan. Solo el Firefox
  del bot (que bloquea las peticiones del consentimiento) entra al juego.

## Antes de tocar código

- Un `GAME_OVER` **no** se arregla reintentando.
- Cada cambio se prueba con una partida corta antes de lanzar una larga.
- Si pierdes siempre en el mismo punto, mira el log: `combinada` de insignias,
  nivel del equipo y contra qué murió. El log va en
  `juegos/pokelike/log/log-AAAA-MM-DD_HH-MM-SS_pPID.txt`.

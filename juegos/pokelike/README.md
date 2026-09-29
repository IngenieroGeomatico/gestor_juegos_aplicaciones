# Pokelike

Roguelike de Pokémon que se juega en el navegador (https://pokelike.xyz): runs
procedimentales sobre un mapa de decisiones ramificado, combates y jefes
regionales. Este directorio contiene los **datos de referencia** y los
**scripts** con los que el agente `pokelike` juega una run entera sola.

> El juego es de navegador y sin cuentas: un bot autónomo en Python juega la
> partida completa por su cuenta y el agente `pokelike` solo lanza el bot y
> explica el resultado. No altera datos de ningún servidor ni de otros
> jugadores.

## Reglas de la máquina (no negociables)

Son de esta máquina, no del juego, y se incumplen sin avisar:

1. **Máximo DOS runs a la vez.** El equipo tiene 7 GB de RAM y cada run abre su
   propio Firefox. Con seis abiertas la sesión se queda sin memoria y las runs
   mueren a los doce pasos por contención, no por juego: los datos que salían
   eran ruido.
2. **Cerrar cualquier Firefox abierto ANTES de lanzar.** Un Firefox ya vivo hace
   que las demás instancias se enganchen a su proceso en vez de abrir el suyo, y
   el bot acaba jugando a medias.

Usa el lanzador, que aplica las dos, comprueba la memoria libre y **baja el
número de runs** si no da:

```bash
uv run --group dev python juegos/pokelike/scripts/lanzar_tanda.py --runs 2
```

Limpieza manual si hace falta. **Ojo: `pkill -f jugar_pokelike.py` mata también
el propio shell**, porque el patrón aparece en la línea de órdenes del `bash`:

```bash
pkill -9 -f "scripts/jugar_pokelike.py"
pkill -9 -x firefox
pkill -9 -f firefox-bin
```

## Cómo funciona el juego (medido, no supuesto)

Esto es lo que hay que tener en la cabeza para escribir la estrategia, y
contrasta con lo que se suele suponer de un juego de Pokémon:

- **Los combates se auto-resuelven.** No hay selección de movimiento: en
  salvaje y en entrenador lo único que hay es `#btn-auto-battle` (tecla
  `Space`). Los `div.poke-move` que se ven en el `catch-screen` son los de los
  *salvajes* ofrecidos, no los del bicho propio. Por eso la única forma de
  subir el daño de un món son los discos.
- **El tier del movimiento depende del mapa** (`getMoveТierForMap`): tier 0 en
  las primeras rutas y tier 2 en las últimas, así que los golpes de un mismo
  tipo se multiplican según el avance. Los movimientos de cada tipo están
  repartidos en tres tiers de menor a mayor potencia.
- **El chart no es el oficial.** En el del juego `Normal vs Rock` es 0.5 (en
  el oficial es 1.0) y `Electric → Ground` es inmunidad (0). Usar el chart
  oficial lleva a decisiones equivocadas, por eso está en
  `data/chart_juego.json`.
- **La experiencia se concentra casi entera en el delantero.** Medido: un món
  cazado en segunda plaza se queda 5-6 niveles por detrás durante toda la ruta.
- **Perder un combate de entrenador termina la run.** Perder un salvaje no.
  Por eso el bot solo entra a un entrenador con el equipo sano y por encima
  del nivel de lo más fuerte que ha visto, contando cuántos móns trae.
- **La UI de `item-screen` solo se cierra con
  `document.getElementById('btn-skip-item').click()`.** Ni la tecla `Space` ni
  el atajo numérico de la carta la avanzan desde el bot; con un clic real en la
  carta y luego `Space` a veces sí. Se prueban varias vías en orden hasta que
  una funciona.

## El nodo del tutor de movimientos

Es el nodo más importante del mapa y el que menos se conoce.

- **Qué es**: un nodo de tipo `move_tutor` (sprite `img/sprites/move-tutor.png`).
  Hay **uno por mapa**, en una capa intermedia del grafo.
- **Qué hace**: enseña un disco (TM) al món que se elija, y eso **sube el tier
  de sus ataques**. Es la única palanca de daño real, ya que los combates se
  auto-resuelven y no se puede elegir movimiento.
- **Cómo se detecta**: por el **estado del juego**, no por el sprite.
  `state.map.nodes` es el grafo de verdad y cada nodo lleva su `type`
  (`catch`, `battle`, `trainer`, `item`, `question`, `trade`, `pokecenter`,
  `move_tutor`, `boss`). El sprite miente: `grass` es un nodo de batalla y
  `question-mark` puede ser un entrenador o un trade.
- **El grafo**: `state.map.edges` es una lista de `{from, to}` sobre un DAG por
  capas, y `state.currentNode.id` dice dónde estamos.
- **Por qué hay que guiarlo**: el bot es codicioso y se iba al entrenador o a la
  batalla de más exp, así que el tutor se quedaba `revealed` pero nunca
  `accessible`: **0 mapas con tutor accesible en una partida entera**. Se
  resuelve con `politica.siguiente_hacia()`, un BFS que calcula la ruta por el
  grafo completo y devuelve el primer salto pulsable; `elegir_nodo` le da
  +8 de puntaje a ese nodo.
- **Cómo se nota que se ha usado**: `state.usedTM` pasa a `true`. El bot lo
  registra en la traza de cada mapa (`| TM usado: ...`) precisamente porque
  pulsar el nodo no cambia el mapa y parece que no pasa nada.
- **Dónde se aplica el disco**: el `elite-prep-screen` (la pantalla "Boss
  Battle / Prepare your team" que sale antes de un jefe o de un rival de élite)
  tiene una sección **BAG** y una ranura de objeto por món
  (`#elite-prep-mon-item`, `#battle-poke-item`). Es el único sitio donde se
  puede usar un objeto, y el bot ahora mismo **no lo hace**: se limitaba a
  pulsar `FIGHT!` (`#btn-elite-prep-continue`). Es la vía pendiente para
  convertir un disco en daño real.
- **La bolsa**: `state.items` es la bolsa real. Se ve vacía tras coger un objeto
  "USABLE ITEM" y solo aparece poblada en el prep de élite, así que los objetos
  no se gastan al cogerlos: se guardan para esa pantalla. No hay UI de
  inventario fuera de ahí: `ITEMS` en el HUD es un `.hud-label` estático sin
  manejador.

Los 54 discos (`data/tms.json`) son 18 `common`, 18 `rare` y 18 `legendary`, y
se reparten por tipo: ahí está, por ejemplo, un `Quick Attack` (Normal, común)
que es justo lo que le faltaba a un Bulbasaur contra un Zubat.

## La escalera de niveles (medida, no estimada)

El listón de combate sale de `politica.nivel_del_jefe()`, que lee los datos
reales del juego, no una fórmula inventada. Antes se usaba `9 + 5×insignia`, que
daba 14 con la primera insignia: seis niveles por debajo de Misty, y por eso el
bot se lanzaba al gimnasio 2 antes de tiempo y lo perdía siempre.

Kanto, de principio a fin:

| Etapa | Necesitas | Niveles del rival |
|---|---|---|
| Brock (Roca) | 14 | 12, 14 |
| Misty (Agua) | 20 | 18, 20 |
| Lt. Surge (Electrico) | 25 | 20, 23, 25 |
| Erika (Fuego) | 32 | 26, 31, 32 |
| Koga (Veneno) | 44 | 38, 38, 40, 44 |
| Sabrina (Fantasma) | 44 | 40, 41, 42, 44 |
| Blaine (Psiquico) | 53 | 47, 47, 48, 53 |
| Giovanni (Tierra) | 60 | 55, 53, 54, 56, 60 |
| Lorelei | 56 | 54, 53, 54, 56, 56 |
| Bruno | 58 | 53, 55, 55, 54, 58 |
| Agatha | 58 | 54, 54, 56, 56, 58 |
| Lance | 62 | 56, 56, 58, 60, 62 |
| Gary (campeón) | 65 | 61, 59, 61, 61, 65 |

El campeón se llama **Gary** en el juego, no Azul. Los miembros del Alta Mando
llevan objeto (`gen1AceOnlyHeldItems`), y en algunas regiones aparecen objetos
que no sonlegal en un ACE trainer normal.

**El Alta Mando reutiliza la pantalla `elite-prep-screen`** (`doElite4` llama a
`showElitePrepScreen`), y entre miembros pasa por `transition-screen` con
`showEliteTransition`. El bot ya tenía handlers para las dos, así que la parte
del flujo está cubierta; lo que faltaba era el listón de nivel, que ya está.

El hueco real aquí no son las pantallas, es la **experiencia**: cada combate da
aproximadamente un nivel, así que para llegar a los 65 del campeón hay que
ganar los 8 gimnasios seguidos sin perder a nadie.

## Estructura

```
juegos/pokelike/
├── README.md        # este documento
├── AGENT.md         # copia del agente de opencode (`pokelike`)
├── data/
│   ├── tipos.json           # chart de 18 tipos (ES/EN) para consultas
│   ├── chart_juego.json     # chart real del juego (18x18) — el que cuenta
│   ├── regiones.json        # Kanto…Unova: jefes, Elite Four, campeón
│   ├── pokemon.json         # starters y pool de capturas con stats
│   ├── items.json           # consumibles y pasivos
│   ├── pokedex.json         # 767 especies con tipos y stats base
│   ├── movimientos.json     # MOVE_POOL: 18 tipos x fisico/especial x 3 tiers
│   ├── tms.json             # 54 discos con tipo, power, rareza y efectos
│   ├── especialidades.json  # 34 especialidades de entrenador y sus tipos
│   ├── leyenda.json         # movimientos firma de los legendarios
│   └── runs/                # estado de cada run (JSON)
└── scripts/
    ├── jugar_pokelike.py      # el bot: juega la run entera solo
    ├── navegador.py           # Playwright, lectura del DOM y de `state`
    ├── politica.py            # estrategia: nodos, capturas, jefe, tutor
    ├── pkl_movimientos.py     # multiplicadores y mejor movimiento
    ├── pkl_tipos.py           # normalización de tipos ES/EN
    ├── extraer_datos.py       # vuelca los datasets del juego a data/
    ├── data_store.py          # utilidades compartidas
    ├── cobertura_equipo.py    # cobertura vs jefes de una región
    └── registrar_run.py       # crear/actualizar/marcar resultado de una run
```

Los datasets de `data/` se sacan del propio cliente con `extraer_datos.py`: el
juego los tiene en globales legibles (`__POKEDEX__`, `MOVE_POOL`,
`TM_OVERDRIVE_BY_ID`, `LEGENDARY_SIGNATURE_MOVES`, `TYPE_CHART`,
`TRAINER_SPECIALTIES`) y `state` es legible en caliente. Solo se leen; no se
toca nada del juego.

```bash
uv run --group dev python juegos/pokelike/scripts/extraer_datos.py
```

## Jugar

```bash
uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
  --region Kanto --reset --max-pasos 1600 --pausa 0.3
```

- `--reset` usa un perfil temporal y arranca una run nueva; sin él continúa la
  guardada. El juego no expone ningún botón de "Reset Run", así que un perfil
  desechable es la única forma fiable de empezar de cero.
- `--max-equipo N` limita el tamaño del equipo (`1` = sin capturas, solo el
  starter), útil para medir cosas.
- `--seguir N` enseña el log en directo refrescando la pantalla cada `N` pasos.

### Ver la partida en directo

Tres formas, de menos a más cómoda:

```bash
# 1. Refrescando la pantalla cada 5 pasos (lo cómodo para una run larga)
uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
  --region Kanto --reset --max-pasos 1600 --seguir 5

# 2. Mirando la partida: ventana de verdad (Firefox visible)
uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
  --region Kanto --reset --visible

# 3. El log del bot en vivo, aunque la partida corra en segundo plano
tail -f juegos/pokelike/log/log-<pid>.txt

# 4. Guardando además la salida en fichero
uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
  --region Kanto --reset 2>&1 | tee /tmp/run.log
```

### Navegador y ventana

| Parámetro | Efecto |
|-----------|--------|
| `--navegador firefox\|chromium\|webkit` | Motor del navegador. Por defecto `firefox`. |
| `--visible` (alias `--headful`) | Abre la ventana de verdad para **ver los movimientos**. |
| (sin nada) | Headless: sin ventana, es lo que se usa para las tandas de pruebas. |

La cabecera de cada ejecución dice con qué se está jugando, para no confundir
`firefox (headless)` con `firefox (visible)`.

El bot escribe en `log/log-<pid>.txt` con la hora en cada línea, así que
`tail -f` funciona aunque el proceso esté en background. Cada ejecución crea el
suyo y lo trunca al empezar, así que no crece sin límite (acumulaba 11 MB y
120.000 líneas) y dos partidas simultáneas no se entrelazan. Para ver cuál es el
tuyo:

```bash
ls -t juegos/pokelike/log/ | head -1
tail -f "juegos/pokelike/log/$(ls -t juegos/pokelike/log/ | head -1)"
```

Cada línea lleva la decisión y su razón, para no tener que mirar la pantalla
del juego. Los combates se anotan al terminar (`COMBATE GANADO` / `COMBATE
PERDIDO`, con el parcial) y cada run cierra con una tabla resumen:

```
[nodo -> 1] entrenador score=10.5 (entrenador: mucha exp y el equipo está sano y a
  nivel; deja 3 combate(s) por delante) | mapa: Nugget Bridge
[prep -> Krabby] rival Rock/Ground -> ['Krabby', 'Bulbasaur', 'Pidgey']
```

`deja N combate(s) por delante` es el cálculo de ruta: el mapa es un DAG y el bot
elige la rama, así que puntúa cada nodo por los combates que deja hacia el jefe
en lugar de aceptar la que toque. Eso va contra la varianza que medi, donde una
partida ofrecía 35 nodos y llegaba al gimnasio 4 y otra 13 y no llegaba al
primero.

- Devuelve un JSON con el resultado (`CHAMPION`, `GAME_OVER`, `ATASCADO` o
  `PRESUPUESTO_AGOTADO`), las insignias y el equipo final.

Desde opencode se usa la herramienta `pokelike_bot`, que hace lo mismo y
devuelve solo ese resumen. La estrategia vive en `scripts/politica.py`.

## La estrategia, en corto

- **Starter**: se puntúa cada gimnasio de la apertura por `ofensiva x
  aguante` (que es lo que decide un combate) y **no se admite ningún 0.5x
  contra los tres primeros**. En Kanto sale Bulbasaur: 2x contra Roca y 2x
  contra Agua, mientras que Squirtle es 0.5x contra el Agua de Mt Moon, que es
  contra lo que se perdían las runs una y otra vez.
- **Primera captura**: se elige por cobertura de **toda la región**
  (`cobertura_region`), no por el gimnasio que viene. Premia 2x en la apertura,
  luego 2x en la región y no tener ni un 0.5x.
- **Resto de capturas**: 2x contra el primer gimnasio que el equipo no cubra ya
  y a la altura del equipo. Se cuenta lo que está **en pie**, no lo que ocupa
  plaza: un món caído es un hueco que hay que rellenar.
- **Contragolpe de entrenador**: la especialidad del rival se lee del estado
  (`trainerSpecialtyTypes`) **antes** de pelear, y se pone al frente el món que
  mejor le responde por el peor caso. Un hiker trae Roca/Tierra/Lucha y uno que
  solo aplasta a la Roca se come al de Lucha después.
- **Orden del equipo**: el mejor món va **al frente contra el jefe** y
  **reservado en segundo** mientras se explora, porque cada pelea de la ruta es
  un desgaste que se pierde si no se recupera.
- **Tutor**: BFS por el grafo para llegar al nodo de discos (ver arriba).
- **Nodos**: `cura` es lo primero si hay caídos; el entrenador solo con el
  equipo sano y por encima del nivel del rival; `question`/`trade` por debajo
  de todo, porque un trade vacío no da exp.

## Referencias

- Juego: https://pokelike.xyz
- Guías comunitarias: pokelike.online, pokelike.org

# Camino a seguir, pantalla por pantalla

Este es el **contrato de juego** del bot: qué se decide en cada pantalla y con
qué criterio. Está extraído del código (`jugar_pokelike.py`, `planificador.py`,
`politica.py`) con los pesos y umbrales reales, no de memoria.

Sirve para dos cosas:

1. **Refactorizar sin romper la estrategia.** La mitad de los bugs que aparecen
   al tocar el bot son desacuerdos entre lo que el comentario de una rama dice y
   lo que la rama hace. Si cambias un peso, comprueba contra esta tabla qué
   decisiones se invierten.
2. **Diagnosticar una run.** El log dice qué pantalla se repetió y con qué
   razón; aquí está qué decisión correspondía.

## Los tres vocabularios, que no son el mismo

El error más repetido de todo el bot es comparar un identificador contra el
vocabulario equivocado. Son **tres** y ninguno coincide con los otros dos:

| Nivel | Valores | Ejemplo |
|---|---|---|
| **Id de pantalla** (`#id` en el DOM) | `map-screen`, `battle-screen`, `catch-screen`, `trade-screen`, `item-screen`, `swap-screen`, `badge-screen`, `elite-prep-screen`, `stat-buff-screen`, `passive-screen`, `shiny-screen`, `trainer-screen`, `starter-screen`, `title-screen`, `transition-screen`, `history-region-select` | `jugar_pokelike.MANEJADORES` |
| **Tipo de nodo del juego** (lo emite `state.map`) | `wild`, `trainer`, `boss`, `pokecenter`, `move_tutor`, `item`, … **en inglés** | `navegador.mapa()` |
| **Tipo de decisión** (interno, ya traducido) | `batalla`, `entrenador`, `jefe`, `cura`, `tutor`, `item`, `trade`, `capturar`, `incognita`, `passive` | `politica.tipo_de_estado()` / `tipo_de_nodo()` |

`politica.tipo_de_estado` traduce `pokecenter → cura`. Por eso el código que
gestiona una curación debe mirar `d.tipo == "cura"` y **nunca**
`("centro", "pokecenter")`: esa comparación no se cumple nunca y la rama queda
muerta sin error. Es el mismo bug que la skill principal ya marca para el jefe
(`boss`, no `jefe`).

## Camino de arranque

```
title-screen      -> _title        continuar run guardada o nueva
history-region-select -> _region  elegir región (o continuar la de la run)
trainer-screen    -> _trainer      elegir el avatar
starter-screen    -> _starter      elegir starter por ventaja de tipos
```

En `starter-screen` se puntúa cada starter con el chart real contra los
**gimnasios que tocará**, y se coge el de mejor `media` y peor caso. No se elige
el que "pega más": se elige el que no tiene agujeros.

## `map-screen`: el nodo, que es la decisión que más importa

Aquí es donde se gana o se pierde la partida. El orden de la partida completa
lo decide `planificador.elegir`, y no es "el nodo más valuable": es **qué falta**.

### Orden de ejecución dentro de `_mapa`

Este orden importa, porque cambiarlo invierte las decisiones:

1. Leer mapa, insignias, equipo, PS real.
2. **Reiniciar `capturas_pantalla` si cambió el nodo** (no la ruta: `m["info"]`
   no cambia al recorrer los nodos de una ruta).
3. Buscar trade: **1 reroll por nodo** como mucho, y solo si no hay nodo de
   trade a la vista y aún no se ha hecho un trade.
4. Reroll por "jefe como única salida sin exp": 3 por partida.
5. `planificador.elegir` → `Decision` con `valor` = atajo del nodo.
6. **Reordenar el equipo** para ese nodo, antes de entrar.
7. Pulsar el atajo.

### Pesos reales

| Nodo | Peso | Cuándo gana |
|---|---|---|
| `cura` | **50** con caídos | waypoint obligatorio: siempre hay pokecenter antes de un líder |
| `cura` | 25 | equipo por debajo del 75% |
| `cura` | 2 | equipo sano |
| `capturar` | **60** | primera captura de la pantalla |
| `trade` | **45** | siempre que falte nivel |
| `entrenador` | **34** | mucha exp, y nivel del rival <= mejor del equipo + 2 |
| `batalla` | 15 | cazar por nivel |
| `item` | 12 | normal |
| `jefe` | 12 | listo |
| `tutor` | 9 / 1 | con nivel / sin nivel |
| `incognita` | 9 | relleno |
| `batalla` | 4 | ya a nivel |

Sobre el peso se suma el **valor de la rama**: `combates_por_delante × 3.5`
cuando falta nivel, `entrenadores_por_delante × 4`, y `centros_por_delante × 12`
si el equipo está por debajo del 75% o tiene caídos. El factor de ruta es lo que
hace que el bot no se meta en un callejón sin salida: el mapa es un DAG y **lo
que no se elige en la bifurcación no se recupera después**.

### Reglas de la puerta de curation

- **Corte de emergencia**: si hay pokecenter accesible y hay caídos, o el
  equipo esta <= 75%, o el carry esta < 50%, todo lo que no sea curar puntúa
  **-5**. Sin pokecenter delante el corte no se aplica (dejaría al bot sin
  opciones).
- **Camino obligatorio**: el grafo siempre pone un pokecenter entre el nodo
  actual y el líder. No es "curar o no": es que hay que pasar por ahí, y al pasar
  se cura entero. Por eso `en_camino_al_jefe` se calcula con BFS inverso desde
  el jefe, y hay que pasarlo **desde el bot** (`jugar_pokelike._mapa`): si no
  llega, la rama queda muerta.

### Veto de entrenador (no negociable)

Un entrenador se veta, con peso **-4**, si:

- El **nivel del rival** supera al mejor món del equipo + 2, o
- Queda **un solo món en pie**, hay caídos y **no hay cura** accesible.

La referencia es el **equipo**, no el jefe. Comparar contra el nivel del líder
deja pasar al Ace Trainer Nv15 con el equipo en Nv11, y eso es una derrota
medida. El nivel del rival llega por `navegador.mapa()` →
`trainerFightLevel(nodo)`; si devuelve `-1` es "no se sabe", y `-1` **no** debe
compararse como si fuera un nivel.

## `battle-screen`: sin decisiones

Todo es automático. El bot solo hace tres cosas:

1. Pulsar **auto-battle** (etiquetado `SKIP` en el DOM).
2. Leer `estado_batalla()` para el **PS real** (`"0/19"`), que es el único dato
   fiable: el HUD da un porcentaje y un món caído muestra 100.
3. Cerrar: `pulsar continuar` hasta salir a `map-screen` / `badge-screen` /
   `pokecenter-screen`.

Ninguna decisión de combate ocurre aquí. Si el bot tiene que "elegir" un movimiento
en pleno combate, es un bug: la estrategia es el **orden del equipo** de antes.

`_cerrar_combate` deduce el resultado de la pantalla de salida: salir a mapa,
insignia o centro es victoria; caer en `gameover-screen` es derrota.

## `catch-screen`

`politica.elegir_captura` filtra por:

- Debe tener **ventaja de tipos** contra al menos uno de los **tres próximos
  gimnasios**, y ser **0.5x contra ninguno** de los tres.
- `nivel_minimo`: no entra un món de relleno si el equipo va por debajo del
  listón del líder. **Hay que pasarlo** (`_nivel_minimo_para_lider`), o el veto es
  código muerto.
- Con el equipo lleno, solo entra si mejora **claramente** al **peor** miembro
  (`nivel+3` o `stats×1.15`).

Equipo con 2 móns o menos: entra el primer candidato aunque no tenga ventaja, con
el criterio de "hacen falta cuerpos antes que nivel".

## `item-screen` y `passive-screen`

- Se coge **un objeto por nodo** (`_ya_cogido_item`), y la bandera tiene que
  limpiarse en **toda** vía de salida, o el bot no coge nada en el resto de la
  partida.
- Se filtran los objetos con `usable: false` (los de efecto en batalla): no se
  pueden equipar.
- `elite-prep-screen`: repartir con `pkl_items.elegir_objetos` y equipar por
  **id**, releyendo la bolsa en cada uso. Los índices del reparto son de un
  snapshot y se desplazan en cuanto se gasta el primero.
- Un fallo de clic **no** veta el objeto para siempre: hacen falta dos fallos
  seguidos.

## `swap-screen` (equipo lleno al capturar, o subida de nivel)

La misma pantalla llega por **dos** motivos:

1. **Captura con equipo lleno.** El objetivo se fija en `catch-screen`
   (`_swap_objetivo`).
2. **Subida de nivel**: el juego pregunta a quién sacar. Aquí no hay captura
   detrás, así que `_swap_objetivo` llega a `None` y el código caía en el
   fallback genérico, que elige **la primera opción** — un món arbitrario.
   Ahora `_peor_para_sustituir()` lo calcula: primero el **muerto** (a 0 PS no
   aporta nada y ocupa una de las seis plazas), y si no hay caídos, el peor por
   nivel y estadísticas.

Un món sin `baseStats` resuelto **no** puede ser el sacrificado: sumaría 0 y
ganaría el `min()`.

## `trade-screen`

Es el nodo más rentable (+3 niveles, PS llenos, conserva el Move Tutor).

1. Ofrecer el **peor** món no-starter (el de menos `baseStats` resueltos).
2. Si la fila del món elegido **no aparece** en la lista, **no se sacrifica a
   nadie**: se declina. Clic a la primera fila = sacar un món arbitrario.
3. Continuar. Aceptado, se invalidan los PS reales y **no** se reordena aquí
   (ya se reordena en el siguiente nodo del mapa).

## `badge-screen` y `elite-prep-screen`

La insignia se registra y se invalidan los PS reales. En `elite-prep-screen` es
donde se gastan los objetos: es la última ventana antes de la Liga, así que un
objeto mal repartido se nota en la Elite Four.

## `stat-buff-screen`

Aceptar el buff y cerrar. Sin decisión de juego: solo se llega aquí tras un
gimnasio.

## Pantallas de fin de run

| Pantalla | `resultado` |
|---|---|
| `win-screen` | `CHAMPION` |
| `gameover-screen` | `GAME_OVER` (cuenta la derrota antes de cortar) |
| `endless-stage-select` / `complete` | `FUERA_DE_ALCANCE` (Tower) |
| `ERROR_DE_CODIGO` | excepción real: cortar, no reintentar |

## Reglas transversales

- **La run no se corta sola**: solo por `GAME_OVER` o `CHAMPION`. Un atasco
  escala la recuperación (teclas → recargar página) en vez de rendirse, y el
  tope son `MAX_INTENTOS_ATASCO = 3`. La **única** excepción es
  `ERROR_DE_CODIGO`: si el bot lanza una excepción real, el bot está roto y
  reintentar solo daría un proceso colgado sin resultado.
- **Caché de PS real**: se invalida en pokecenter, insignia, swap, trade y uso de
  objetos. Olvidarla hace que el bot crea que tiene móns caídos que ya están
  vivos, y todo lo que depende de `vivos` / `caidos` decide mal.
- **Detector de atasco**: cuenta repeticiones **consecutivas** de
  pantalla + acción. Acumuladas cortaba runs sanas (en `map-screen` la
  acción es siempre `nodo N`, el valor normal de cada visita).
- **Errores de código** (`NameError`, `AttributeError`, `UnboundLocalError`,
  `TypeError`, `KeyError`, `IndexError`) cortan la run: reintentar no arregla un
  bug. Los transitorios se reintentan 3 veces.
- **Orden importa más que el nivel**: el carry en la posición equivocada pierde
  su ventaja aunque tenga más stats.
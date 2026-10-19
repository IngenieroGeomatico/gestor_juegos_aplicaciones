---
name: pokelike-reglas
description: Úsala cuando el usuario dé una regla de juego para Pokelike, pregunte por qué el bot juega como juega, o haya que cambiar una prioridad del bot. Contiene las reglas de juego fijadas por el usuario y el camino a seguir en cada pantalla. Úsala ANTES de tocar politica.py o planificador.py.
---

# Reglas de juego de Pokelike

Estas reglas son las que el usuario ha fijado para el bot. Vienen **por
encima** de cualquier lectura de la guía de la comunidad cuando se contradigan:
si la guía dice una cosa y aquí dice otra, gana esta skill.

Las reglas van acompañadas del **camino por pantalla** y de la tabla de pesos,
para que al implementarlas se sepa dónde tocar y qué se invierte.

## Las reglas

| # | Regla | Dónde vive en el código |
|---|---|---|
| 1 | **La run nunca se corta automáticamente.** Solo acaba por pérdida (`GAME_OVER`) o por completar la región (`CHAMPION`). | `jugar()`: el bucle no lleva tope de pasos, y un atasco escala recuperación en lugar de cortar. |
| 2 | **Al inicio de cada pantalla se captura un Pokémon, una sola vez y solo si el candidato vale.** Vale si aporta contra el **gimnasio actual o el siguiente** (tipos de `regiones.json` × `tipos.json`) o si **equilibra los tipos** del equipo (aporta un tipo que no hay, o quita una doble debilidad). Con **menos de 3 vivos manda el cuerpo**: cualquier candidato vale, porque la plaza vacía es peor que un tipo repetido. Si el candidato **no vale, no se captura**, y el descarte **deja traza** (`razon_captura=descartado: …`): un veto silencioso es indistinguible de un bug. Con 6 en el equipo sigue la comparación de antes (nivel +3 o stats ×1,15 contra el peor). | `politica.elegir_captura` + `capturas_pantalla` (se reinicia **por nodo**). |
| 3 | **Reordenar antes de cada combate** por efectividad; con menos del 50% de vida, el món va **último** (sigue jugando y ganando exp, no se le expulsa). | `politica.orden_deseado` + `_reservar_heridos`. |
| 4 | **Las MT van al Pokémon principal**; si ya no se le pueden añadir más, al siguiente de **más nivel**. | `puntuar_objeto` / reparto de la bolsa. |
| 5 | **Los objetos van al Pokémon que mejor les viene**: un objeto que mejora ataques de Planta, a un Pokémon de Planta. | `pkl_items.elegir_objetos` puntúa cada objeto contra los **tipos de cada món**. |
| 6 | **Si aparece un cambio de Pokémon, se cambia al peor**: primero el **caído**, luego, si hay dos del mismo tipo, el **peor de los repetidos**, y si no, el peor por stats y nivel. | `jugar_pokelike._peor_para_sustituir` (cubierto por `test_sacar_el_tipo_repetido`). |
| 7 | **Priorizar los combates de entrenador** para ganar nivel: son la única fuente que sube a todo el equipo. El entrenador **anuncia su tipo**, así que su peso se modula por **emparejamiento** (sube si el mejor món del equipo le pega ×2 y no recibe ×2, baja si es al revés), y la rama vale más si **desemboca en el pokecenter**: el grafo óptimo es el de más entrenadores ganables hasta la cura. | `PESO_ENTRENADOR_SANO`, el emparejamiento, `entrenadores_por_delante` y `centros_por_delante`, y el veto que impide pelear trainers por encima del equipo. |
| 8 | **Pasar por el pokecenter obligatoriamente** si hay caídos, o el equipo está ≤ 75%, o el carry está < 50%. | El corte de emergencia de `puntuar` (peso −5) y `UMBRAL_PUERTA_JEFE`. |
| 9 | **Tipo repetido, plaza desperdiciada.** Dos móns del mismo tipo: el segundo no aporta nada que el primero no tenga. Al sustituir, sale el repetido para liberar la diversidad. El caído manda sobre esta regla. | `_peor_para_sustituir`, con `navegador.mons_en_swap` para saber qué món entra. |
| 10 | **Necesidad de captura, y reestructurar el grafo cuando no se cubre.** Hay necesidad si (a) falta cobertura contra el **gimnasio actual o el siguiente**, (b) ha **caído un món** en el grafo hacia el gimnasio y no se ha repuesto, o (c) hay **menos de 3 vivos**. Con necesidad, el nodo de captura conserva su peso alto y las ramas que **llevan a un nodo de captura** suben de valor: reestructurar el grafo es **elegir la ruta hacia otra captura**, no gastar el reroll del mapa. Sin necesidad (o con la captura de la pantalla ya hecha), `capturar` cae a peso de relleno y el bot prefiere pelear. | `planificador`: término de necesidad de captura en el peso del nodo y valor de rama hacia capturas; `politica.elegir_captura` decide la validez. |
| 11 | **Con repetidos en el equipo, el trade sube de peso.** Si hay dos móns del mismo tipo, el nodo de `trade` gana valor para cambiar la plaza repetida por diversidad (es la vía de arreglar el R9 sin gastar una captura). El caído sigue mandando: primero se repone la plaza, luego se canjea. | Peso del nodo `trade` en `planificador.py`, condicionado a los tipos repetidos del equipo. |
| 12 | **Los objetos de poder por tipo y las MT son prioridad alta.** Un objeto que sube el tipo (`miracle_seed`, `charcoal`…) no es un +40%: hace **atacar con ese tipo**, y vale mucho más que un plus genérico — a un món de ese tipo (R5). La MT es daño **permanente que no depende del nivel**, así que su nodo (`tutor`) no debe quedar por debajo de un objeto suelto. | `pkl_items.tipo_de_boost` y `P_BOOST_PROPIO`; pesos `PESO_TUTOR_*` en `planificador.py`. |

## Pendiente de implementar (fijado por el usuario el 19-10-2026)

Estas reglas están **fijadas** (filas 2, 7, 10, 11 y 12 de la tabla) pero
**todavía no están en el código**: el bot juega hoy con R2 sin puerta de validez,
el entrenador sin emparejamiento, la captura sin término de necesidad, el trade
fijo y el tutor por debajo del objeto.

Orden de trabajo acordado, una palanca por vez y con bandera reversible
(`PKL_*=0` deshace), probando cada una con partida corta antes de lote de 200:

1. **R2 + R10**: puerta de validez en `politica.elegir_captura` con **traza
   obligatoria** del descarte, y término de necesidad de captura en el peso del
   nodo y en el valor de rama hacia capturas. Cuerpos primero con <3 vivos.
2. **R12**: revisar el desajuste ya visible — el comentario de
   `planificador.py` dice que el tutor va **por encima** de los objetos, pero
   los números dicen lo contrario: `item` = 12 contra `PESO_TUTOR_CON_NIVEL` = 9,
   y `PESO_TUTOR_SIN_NIVEL` = 1.0 (demasiado bajo para "las MT son muy
   importantes"). Y la tabla de pesos de esta skill **no tiene fila de `tutor`**,
   que es lo que dejó pasar el desajuste.
3. **R11**: peso del `trade` condicionado a tipos repetidos en el equipo.
4. **R7 (emparejamiento)**: el entrenador anuncia su tipo; sube el peso si el
   mejor món le pega ×2 y no recibe ×2.

## Reglas que salieron de medir

*(Ninguna todavía. Ver "Por qué esta sección está vacía" más abajo.)*

### Por qué esta sección está vacía

Porque se llenó una vez con datos **no válidos** y hubo que vaciarla. La
medición que había (`medir_hipotesis.py` sobre 228 partidas) mezclaba partidas
jugadas por **versiones distintas del bot**: unas con bucles infinitos, otras
con la captura rota, otras sin los vetos. Sobre ese混合物 se Conclusions
tipo "el nivel es el cuello" que no se sostienen:

- Una correlación leída como causal. Un equipo llega por debajo del listón
  *porque antes tomó malas decisiones*: el hueco es síntoma, no causa.
- La medida no era la que pedía la hipótesis. H2 preguntaba por las peleas
  **ganadas** por debajo del listón; se[midió cuántas veces se llega por debajo.

**Regla para esta sección**: una hipótesis solo entra aquí con **A/B
controlado** (una variable, bot congelado, asignación aleatoria, tamaño de
muestra declarado) y con el criterio de falsación escrito **antes** de mirar los
datos. Hasta entonces va en `HIPOTESIS.md` como abierta, que es donde están.

### Estado actual

Media **1,14 insignias** por partida sobre 284 runs (8 posibles), y hay
**1 `CHAMPION`** en el repo: la run que ganó pasó los 8 gimnasios y el Elite
Four con 239 pasos y **0 combates perdidos**. Objetivo: que el `CHAMPION` deje
de ser un accidente.

Lo que separa ganar de perder **no es el nivel**: de 934 peleas con foto de PS
reales, entrar con el equipo al 0-50% de vida gana el **25%** y al 95-100%
gana el **99,7%**. Y el déficit de nivel no lo cierra nadie, porque el rival
más fuerte que el juego ofrece está 8-11 niveles por debajo del listón y solo
está por encima del equipo en el 2% de las pantallas.

Por tanto la regla que gobierna el bot es: **entrar por debajo de nivel sí,
entrar gastado no**. Detalle y método en `juegos/pokelike/HIPOTESIS.md`.

### R1 tiene una única excepción

Un **error de código** (`NameError`, `TypeError`, …) sí corta la run, y eso no
es una decisión de juego: es que el bot está roto. Si no se corta, el mismo
error se repite para siempre y la run ni gana ni pierde. Cuando se corta, se
escribe un volcado con archivo y línea, que es lo que hace el bug arreglable.
Un presupuesto de pasos agotado **no** corta: solo avisa.

## Camino por pantalla

El orden de `_mapa` importa, porque cambiarlo invierte las decisiones:

1. Leer mapa, insignias, equipo y **PS real**.
2. Reiniciar `capturas_pantalla` si cambió el **nodo** (no la ruta).
3. Buscar trade: **un reroll por nodo** como mucho.
4. Reroll por "jefe como única salida sin exp": 3 por partida.
5. `planificador.elegir` → nodo y su puntuación.
6. **Reordenar el equipo** para ese nodo.
7. Pulsar el atajo.

`battle-screen` no decide nada: es automático. Todo se decide en el **orden del
equipo** de antes, y el bot solo pulsa auto-battle y lee el PS real.

## Pesos de los nodos

| Nodo | Peso |
|---|---|
| `cura` con caídos | 50 |
| `cura` equipo bajo | 25 |
| `capturar` (primera de la pantalla) | 60 |
| `trade` | 45 |
| `entrenador` | 34 |
| `batalla` cazando nivel | **20** |
| `batalla` ya a nivel | 4 |
| `jefe` listo | 12 |
| `item` | 12 |
| `incognita` | 9 |

Sobre el peso se suma el valor de la rama: `combates_por_delante × 3.5` si
falta nivel, `entrenadores_por_delante × 4`, `centros_por_delante × 12` si hay
caídos o el equipo está bajo. El mapa es un DAG: **lo que no se elige en la
bifurcación no se recupera después**, y por eso el valor de la ruta pesa más que
el valor del nodo suelto.

## Trampa: no inventar reglas que la regla no dice

Hubo un veto por nivel en la captura ("no cazar si el equipo va por debajo del
listón del líder"). Sonaba razonable, Lo deduje de un comentario viejo del
código, y **no lo pidió nadie**. Con un solo món en pie descartaba **todos** los
salvajes de la ruta: el planificador elegía el nodo de captura, `elegir_captura`
lo rechazaba en silencio, y la run terminaba `GAME_OVER` con un único Pokémon y
cero capturas.

La lección no es solo "no lo inventes", sino que **un veto silencioso es
indistinguible de un bug**: no sale ningún error, el nodo se gasta igual y la
pérdida se atribuye a la mala suerte. Si un filtro puede descartar una acción,
que deje rastro en el log.

## Los tres vocabularios, que no son el mismo

El error más repetido del bot es comparar un identificador contra el
vocabulario equivocado. Son tres y ninguno coincide con los otros:

| Nivel | Valores |
|---|---|
| Id de pantalla (DOM) | `map-screen`, `battle-screen`, `catch-screen`, `trade-screen`, `item-screen`, `swap-screen`, `badge-screen`, `elite-prep-screen`, `stat-buff-screen`, `passive-screen`, `shiny-screen` |
| Tipo de nodo (lo emite el juego, **en inglés**) | `wild`, `trainer`, `boss`, `pokecenter`, `move_tutor`, `item` |
| Tipo de decisión (interno, ya traducido) | `batalla`, `entrenador`, `jefe`, `cura`, `tutor`, `item`, `trade`, `capturar`, `incognita` |

Comparar contra el vocabulario equivocado deja la rama **muerta sin error**.
Pasa con el pokecenter (`cura`, no `pokecenter`) y con el jefe (`boss`, no
`jefe`).

## Vetos que no se negocian

- **Entrenador por encima del equipo.** Se veta si el nivel del rival supera al
  mejor món del equipo + 2. La referencia es **el equipo**, no el jefe: comparar
  contra el nivel del líder deja entrar a un entrenador 4 niveles por encima.
- **Entrenador con un solo món en pie, caídos y sin cura** a mano. Ahí pelear no
  es una fuente de exp, es perder la run.
- **Captura de relleno con el equipo en deuda de nivel**: `nivel_minimo` tiene
  que pasarse, o el veto es código muerto.

## Pendiente

**R6/R9 están implementadas pero sin verificar en partida.** El manejador de
`swap-screen` ya existía y cubría el caso "un món sube de nivel y el juego pide
a quién sacar", pero elegía **la primera opción de la lista**, que es un món
arbitrario: justo lo contrario de la regla. Ahora `_peor_para_sustituir` decide
por valor (caído → repetido más débil → peor por stats y nivel).

Lo que **no** está verificado es la otra mitad: `navegador.mons_en_swap` tiene
que acertar con el món que entra, y eso se lee del texto de la pantalla porque
no se conoce el HTML. **Si esa lectura falla o confunde a un miembro del
equipo con el entrante, la regla del tipo repetido se aplicaría sobre datos
falsos.** El primer log con `⋯ swap ofrece:` dice si la lectura acierta; si el
nombre que sale es uno de los seis del equipo, la lectura está mal y hay que
corregirla antes de fiarse de la regla.

## Antes de tocar el bot

- Cada cambio se prueba con una partida corta antes de lanzar una larga.
- `--max-pasos` ya **no** corta la run (R1): es solo informativo.
- Los pesos y umbrales de esta skill se comprueban contra el código con
  `test_integridad.py::test_la_skill_del_camino_no_se_desincroniza`. Si cambias
  un peso, actualiza la skill o el test falla.

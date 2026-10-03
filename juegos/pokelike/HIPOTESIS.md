# Hipótesis: qué falta por aprender y cómo se comprueba

Cada línea es una hipótesis **falsable** sobre el juego o sobre el bot, con la
medida que la confirma o la tumba. Se van tachando con el resultado real de las
partidas. Nada aquí es una opinión: o hay un número que lo sostiene o se cae.

Cómo leer una línea:

- **Medida**: qué se cuenta exactamente, de qué log.
- **Si sale X**: la hipótesis queda **confirmada**.
- **Si sale Y**: queda **rechazada**, y se apunta qué hacer después.

## Controles ya resueltos (no volver a mirar)

| # | Cuestión | Respuesta | Cómo se resolvió |
|---|---|---|---|
| **V1** | **¿Veto de entrenador por tipo?** | **NO — es contraproducente. Quitar.** | **CERRADA con evidencia.** 111 runs, 3 brazos, Kanto. Solo la ventana de **código homogéneo** (posterior a 19:32, tras la última edición): A(veto) n=11, B(sin veto) n=21, C(sin veto+cobertura) n=35. Media de insignias: A **0,64** / B **1,62** / C **1,43**. A vs B insignias **p=0,020**; A vs C **p=0,024** (Mann-Whitney, rechazan H0). Llegada al 1er gym: 55% / 67% / 83%. **B vs C p=0,837 → indistinguibles**: el flag de cobertura no aporta nada medible, así que no se enciende. `PKL_VETO_TIPO=0` es el default. |
|---|---|---|---|
| R1 | ¿El PS está normalizado por nivel? | **NO** | `PS = floor(2·baseHP·nivel/100) + nivel + 10`, sacada de `calcHp()` en el bundle del juego. Verificada con Nidoran-m Lv2=13, Bulbasaur Lv5=19, Clefairy Lv4=19. |
| R2 | ¿La experiencia es del delantero o del equipo? | **Del equipo** | Guía: +2 niveles todos contra entrenador, +1 contra salvaje. |
| R3 | ¿Qué tipos emite el mapa? | `start, catch, battle, trainer, item, question, trade, pokecenter, move_tutor, boss` | Traducidos y con test de que los 10 mapean bien. |
| R4 | ¿Con qué frecuencia sale un trade? | Peso 5 frente a 30 de entrenador | Tablas de pesos del bundle. |
| R5 | ¿Por qué fallaban los clics de objeto? | Eran **sintéticos** | El juego no atiende `el.click()` de JS; hace falta `locator.click()`. |
| R6 | ¿Por qué se colgaba el prep? | Modal de equipar que no escucha Escape | Hay que cerrar con `#btn-equip-cancel` y con clic real. |

## Hipótesis abiertas

### H1b · ¿Cuánto listón hace falta de verdad? (nueva)
- **Medida**: con `MARGEN_TIPO_BONUS = 1`, ¿sube la media de insignias? Y con 0,
  ¿sube más?
- **Si sale X**: bajar el listón sube la media → el nivel es todo.
- **Si sale Y**: no se mueve → el listón no era el_binding constraint y hay que
  mirar composición de equipo.

### H1c · ¿La varianza del mapa explica más que la política? (nueva)
- **Medida**: desviación de las 87 derrotas de H1 (de -10 a +7 es enorme para una
  media de -4,2). Si dos partidas con el **mismo** listón y casi el mismo nivel
  pierden y ganan, entonces el mapa manda más que la política.
- **Por qué importa**: si es verdad, la palanca no es "jugar mejor" sino "no
  perder más runs": reducir la varianza mala vale más que mejorar la media.

### H1 · El nivel es el cuello, y se mide en la entrada al gimnasio
- **Medida**: para cada derrota contra gimnasio, el nivel del equipo en el paso
  anterior frente al rival (`niveles rivales` del log).
- **Estado**: **RECHAZADA** en el diagnóstico de 94 muertes: el 71% de las
  derrotas tenía al menos un món **2+ niveles por encima** del rival. No es el
  cuello.
- **Si sale X**: la diferencia media es **≥3 niveles** → confirmada.
- **Si sale Y**: la diferencia media es **<2** → rechazada. **Ya salió Y.**

### H2 · Llegar por debajo del listón no compensa aunque haya ventaja de tipo
- **Medida**: combates de gimnasio ganados con el equipo **2+ niveles por
  debajo** del rival.
- **Si sale X**: ≥25% de los victorias entran por debajo → el margen de 2 niveles
  es **demasiado optimista** y hay que exigir paridad estricta.
- **Si sale Y**: casi ninguno entra por debajo → el margen actual es correcto.

### H3 · Curar antes del jefe es lo que decide, más que el nivel
- **Medida**: derrotas contra gimnasio con el `carry` por debajo del 60% frente
  a las ganadas con el `carry` por encima del 90%.
- **Si sale X**: las derrotas se concentran con el carry bajo → hay que **forzar
  más las curaciones** (subir el peso del pokecenter).
- **Si sale Y**: la vida del carry no discrimina → el problema es de composición.

### H4 · Un solo món en pie es la causa real de perder
- **Medida**: proportion de derrotas donde el equipo tenía **1 món vivo** al
  entrar, frente a 2-3.
- **Si sale X**: la mayoría de las derrotas son con 1 vivo → la regla de cazar
  con equipo corto está mal puesta y hay que cazar **más**.
- **Si sale Y**: se pierde con equipo completo → no es un problema de cantidad.

### H5 · Los objetos de tipo cambian el resultado de los gimnasio
- **Medida**: proportion de victorias contra gimnasio con un objeto de tipo
  **bien elegido** (el que multiplica al rival) frente a sin objeto.
- **Si sale X**: la diferencia es apreciable → el reparto de objetos es la palanca.
- **Si sale Y**: no se distingue → el objeto de tipo no compensa al mal matchup.

### H6 · El trade es el atajo de nivel que falta
- **Medida**: nivel del equipo en el paso **después** de un trade, comparado con
  el de antes.
- **Si sale X**: el salto es de **+3** → confirmada, y hay que Perseguir trades
  con más ahínco (más rerolls, más peso).
- **Si sale Y**: el salto es menor o el trade no se completa → el flujo sigue
  roto y hay que terminarlo.

### H7 · El Lucky Egg compensa y hay que cogerlo de inmediato
- **Medida**: ritmo de subida de nivel en las runs **con** Lucky Egg frente a las
  que van **sin** él.
- **Si sale X**: la diferencia es de **≥1 nivel por gimnasio** → hay que
  desviarse por los nodos de objeto aunque elersea lento.
- **Si sale Y**: no se distingue → el objeto no compensa lo que cuesta el desvío.

### H8 · El Pokésort es resoluble con los datos del repo
- **Medida**: se montan los 6 móns del puzzle de hoy y se busca el orden que
  cumple las 5 condiciones.
- **Bloqueo actual**: de las cuatro condiciones (misma etapa de evolución, mismo
  color, comparten tipo, muy eficaz contra), el repo solo tiene **tipos**. Faltan
  **color** y **etapa de evolución**, que hay que extraer del juego.

## Cómo se recogen los datos

Cada partida deja su log en `juegos/pokelike/log/log-*.txt` y la copia de la
tanda en `/tmp/opencode/tanda*.log`. Lo que se usa de cada uno:

- `>>> COMBATE PERDIDO contra ...` → contra qué y con qué vida quedó el equipo.
- `niveles rivales a-b` y `mios=[...]` → la diferencia de nivel en el choque.
- `· Ruta: vs Líder (tipo) | equipo N (vivos N) niv a-b` → el estado en la entrada.
- `objeto EQUIPADO ->` / `objeto NO usado ->` → el reparto de objetos.
- `trade aceptado` / `trade: se ofrece` → H6.

> Ojo: `/tmp/opencode` se limpia solo. Lo que hay que conservar está en el repo
> (`GUIA-ESTRATEGIA.md`); los volcados de DOM hay que copiarlos cuando salen.

## Trampas de método que ya han costado datos

Estas son las que hay que evitar en la **siguiente** tanda, y la razón es
concreta: en este experimento las tres passportaron y el resultado salió
inconcluso pese a tener 111 runs.

1. **No tocar el bot mientras corre un lote.** Es lo que arruinó este
   experimento: se editó `jugar_pokelike.py` a mitad y 56 de las 111 runs
   quedaron con código distinto. Solo son comparables las de una misma versión
   (aquí, las posteriores a las 19:32), y eso tiró la mitad de la muestra.
   **El código se congela mientras corre un lote, sin excepciones.**
2. **Repartir los brazos entrelazados, no por bloques.** Aquí los bloques
   dejaron al brazo C **2 h 14 min después** que A y B, así que "C es mejor"
   podía ser solo "C corrió más tarde". Intercalar los brazos dentro del mismo
   bloque de tiempo hace ese confound imposible por construcción.
3. **Contar las runs antes de lanzar, no después.** El launcher pedía 150 y
   entregó 111 por un `i % 2` mal puesto. El plan y la realidad se separaron y
   no hubo forma de saberlo hasta el final.

## La métrica primaria hay que revisarla

La primaria elegida era "llega al primer gimnasio" (binaria), y **no tiene
potencia**: 55% / 67% / 83% con n=11/21/35 no llegan a p<0,05. La diferencia
que sí sale es en **insignias** (p=0,020 y 0,024). Las insignias son la métrica
que de verdad responde y la que separa las manos. Para la próxima tanda la
primaria debe ser **insignias por partida**, y "llega al primer gym" pasa a
secundaria.

## La pregunta ya no es qué flag gana

Con el veto apagado (línea base) la pregunta es **qué impide llegar a la 6.ª
insignia y de ahí al Elite Four**. Nadie ha pasado de 5 insignias. Las 100 runs
siguientes miden eso, y sobre todo miden **dónde se mueren** las que no llegan.

## Cobertura actual de los datos

111 runs del experimento de flags (Kanto), de las que **56 son comparables**
por versión de código. Techo: **5 insignias** (brazo B). Cero `CHAMPION`.
Pendiente: 100 runs de línea base con el veto apagado, bot congelado.

## Nueva tanda: línea base (veto apagado, bot congelado)

**Qué mide**: por qué el bot se queda en 4-5 insignias y no pasa de ahí. Ya no
es "¿qué flag gana?", porque eso está respondido. Los logs sirven para **contar
dónde mueren** las runs que no llegan.

**Protocolo, y por qué cada punto** (los tres primeros son_errors que ya
costaron el experimento anterior):

| Punto | Motivo |
|---|---|
| **Bot congelado** mientras corre | Editar a mitad dejó 56/111 runs con versión distinta y hubo que tirar la mitad de la muestra. |
| **Hash de código en cada log** (`codigo=9f81f89a`) | Para no depender de acordarse de *cuándo* se editó: los logs se separan solos. |
| **Timeout 25 min por run** | Una run colgada-paró 10 h el lote anterior y se perdieron 82 runs. |
| **Número exacto de runs** | El launcher anterior pedía 150 y entregó 111 sin que nadie lo notara. |
| **Kanto, 100 runs, 2 en paralelo** | ~11 h. Volumen bruto: la varianza del mapa manda más que la política. |
| **Primaria = insignias** | "Llega al primer gym" no tiene potencia (55/67/83% no llegan a p<0,05). Pasa a secundaria. |
| **Los timeouts cuentan como fracaso** | Si no, se truncan los datos hacia el éxito. |

**Qué NO se toca mientras corre**: `juegos/pokelike/scripts/`. Cualquier
cambio, por pequeño que parezca, espera a que termine.

---

# Diagnóstico de la línea base (100 runs, `codigo=9f81f89a`)

Resultado del embudo, y **la pregunta abierta cambió**: ya no es qué flag
gana, es **por qué se mueren las runs**.

## El embudo

| Insignia | Llegan | Muerten con esa exacta |
|---|---|---|
| 0 | 95/100 | 26 |
| 1 | 69/100 | **42** |
| 2 | 27/100 | 15 |
| 3 | 12/100 | 8 |
| 4 | 4/100 | 2 |
| 5 | 2/100 | 1 |

## Dónde mueren

De 95 muertes con final de partida: **30 en gimnasio (32%) y 65 fuera (68%)**,
y de esas 65, **54 contra entrenadores** y 11 contra salvajes.

## Corrección: el "32,7% de PS al entrar" estaba contaminado

Se concluyo que el equipo entraba a las peleas de entrenador con un 33% de PS, y
que eso era la causa. **Ese número no vale y hay que tirar el dato entero.**
El volcado `mios=` sale solo cada 4 llamadas del manejador de batalla
(`_n_batalla % 4 == 0`), así que puede caer **a mitad de la pelea** y ya no es
el estado de entrada. El caso que lo delata:

```
>>> COMBATE PERDIDO contra Scientist ... | nos quedan: Bulbasaur(100/100), Spearow(100/100), Goldeen(41/100)
mios=[Bulbasaur Lv15 '0/38', Spearow Lv12 '0/31', Goldeen Lv14 '15/36']
```

La línea de mapa de 10 s antes decía `equipo 3 (vivos 3)`, o sea que los dos
"0/38" se quedaron asi **durante** la pelea. Dos medidas anteriores salieron
por el mismo camino (la del `mios=` post-pelea). **La medición fiable del estado
del equipo al decidir es `equipo N (vivos V)`, no `mios=`.**

## H8 · El bot entra a entrenadores con el equipo desmontado (nueva)

- **Medida**: en la línea de mapa inmediatamente anterior a elegir el nodo,
  cuántos móns en pie (`equipo N (vivos V)`), en las 54 muertes de entrenador.
- **Resultado**: eligió con el equipo entero vivo 31 veces, con **2 o menos 33
  veces (61%)** y con **1 solo 15 veces (28%)**. Al perder, 21 de 54 se
  quedaron con un único món en pie.
- **Código responsable**: la rama
  `if caidos and not ctx.carry_debil and not ctx.hay_cura_disponible:`
  devolvía `PESO_ENTRENADOR_SANO` = **34, el puntaje más alto de la pantalla,
  en el estado más peligroso**. Esa rama era una corrección contra un atasco
  (con el entrenador vetado el bot se quedaba sin nodos) y sobrecorrigió.
- **Por qué no se arregla vetando**: en **21 de 49** (43%) de esas muertes la
  pantalla **solo tenía el entrenador**, y la más frecuente era
  `entrenador + entrenador` (19 casos). Un veto duro allí no evita la muerte:
  el bot pelea al segundo. Por eso el arreglo es una **escalera que nunca
  puntúa negativo**: gana cualquier alternativa si la hay, y si no la hay
  pelea igual, que es lo único que puede hacer.
- **Medida de resultado**: insignias/partida, A (escalera) vs B (control
  literal), 50+50 **intercalados**.

## H9 · La cura del juego es solo el pokecenter (nueva)

- **Medida**: qué objetos entrega el juego en 100 runs.
- **Resultado**: **14 tipos de objeto, todos equipables competitivos**
  (eviolite, red_card, assault_vest, choice_scarf, quick_claw, pixie_plate,
  mystic_water, wide_lens, rare_candy, miracle_seed, shell_bell, leftovers,
  rocky_helmet, choice_specs). **Cero consumibles curativos: ni una poción en
  100 runs.** La cura de la partida depende por tanto del pokecenter y nada
  más.
- **Consecuencia**: la hipótesis "usar las pociones antes de pelear" era una
  palanca inexistente.
- **Bug de datos adjunto**: `data/items.json` describe 8 consumibles y 8
  pasivos en español, y **ninguno salvo `Restos` aparece en el juego**. El
  catálogo del repo es ficción respecto al juego real y `elegir_objetos`
  decide sobre objetos que no existen.

## H10 · Ninguna penalización de `puntuar` funcionaba (nueva, y es la de fondo)

Este es el hallazgo que explica por qué H8 no se movía, y es **arquitectónico**:
no un peso mal puesto, sino un orden de sumas.

En el bucle de puntuación de `elegir` el score se compone en dos pasos:

```python
s, razon = puntuar(tipo, ctx_n)      # <- aquí entran TODOS los vetos
...
s += extra * peso_ruta               # <- y aquí el bono de ruta, 60-300
```

El bono de ruta es `n_ent*4` (entrenadores por delante) y `n_centro*12`
(pokecenters por delante), multiplicado por `peso_ruta = 3.5` mientras falte
nivel. O sea que vale **entre 60 y 300**, y se suma **después**. Un veto que
devuelve `-4.0` no pierde nunca contra eso.

**Medido en 24 runs reales**, no supuesto: la escalera de riesgo marcó
"entrenador de riesgo" **13 veces** y el bot eligió ese entrenador **13 de 13**,
exactamente igual que el brazo de control (12 de 12). El flag no cambiaba
nada. El lote se paró a los 24 runs: gastar cuatro horas midiendo un no-op ya
conocido no es una inversión, es un error.

Las cinco ramas negativas de `puntuar` (`-5, -1, -3, -3, -4`) tienen el mismo
defecto. La más grave es el **veto por nivel**: marcó 8 pantallas en 24 runs y
el bot eligió al entrenador las 8 veces. En el test de regresión se ve el
número crudo: el veto devuelve `-4.0` y el nodo gana con `160.5`.

- **Arreglo aplicado (solo a la escalera)**: `riesgo_entrenador()` devuelve
  `(peso, penalización, motivo)` y la penalización **se suma al final**, con el
  bono de ruta ya dentro. La escalera pasa a restar 110-400 puntos, que sí
  pierden contra un bono de 210.
- **Lo que queda sin arreglar a proposito**: el veto por nivel sigue siendo un
  no-op. Arreglarlo en el mismo commit mezclaría dos intervenciones y el
  experimento dejaría de medir una sola cosa. Es la siguiente hipótesis (H11).
- **Test de regresión**: `test_la_escalera_gana_al_bono_de_ruta` monta la
  pantalla exacta del fallo (entrenador con 10 entrenadores y 20 combates por
  delante) y comprueba que A elige `batalla` y B elige `entrenador`.

### Trampa de método: dos errores al medir lo mismo

1. **`[nodo -> N] tipo score=…` es una decisión, no un candidato.** Se
   agruparon por "líneas de puntuación consecutivas" para saber cuántos nodos
   había en pantalla, y salió "el 94% de las pantallas tiene un solo nodo", lo
   que parece una propiedad del juego. Era mentira: cada línea es **una
   decisión tomada**, una por pantalla. La verdad de qué había en pantalla está
   en el campo `disponibles` de la línea de estado
   (`disponibles ['batalla', 'batalla']`).
2. **La secundaria que parecía medir la escalera no podía medirla.** Contaba
   "peleas de entrenador con ≤2 móns en pie" después de cada muerte. Como la
   escalera **no es un veto**, cuando el entrenador es el nodo único se pelea
   igual y la cifra no baja nunca. La métrica útil es otra: de las pantallas
   marcadas como de riesgo **que tenían alternativa en pantalla**, cuantas se
   pelearon igual. Con la métrica vieja el brazo escalera salía *peor* (41% vs
   33%) y parecía que el flag empeoraba al bot; no era eso, era que la métrica
   no discrimina.

### Y el techo sí existe: no eran peleas forzadas

Con `disponibles` como fuente: de 130 peleas de entrenador, **92 (71%) tenían
alternativa**; de las 72 peleas con el equipo a ≤2 móns en pie, **50 tenían
alternativa** (27 eran tutor, 8 item, 8 batalla). Y de las 17 pantallas que
marcó la escalera, 15 tenían alternativa. La escalera **puede** cambiar la
decisión en dos de cada tres casos. El ERROR fue el sitio donde se aplicaba.

## Lo que queda cerrado en esta tanda

| Cuestión | Respuesta | Cómo |
|---|---|---|
| ¿El chart del bot es el del juego? | **Sí, 324/324 celdas idénticas** | Se descifró el bundle (`FsJ(0x…)`, tabla rotada por checksum) y se extrajo el `TYPE_CHART`. Difiere del oficial solo en `Normal→Roca` y `Normal→Acero` (x0.5), que es el chart de **generación 6**. |
| ¿Funciona la búsqueda de efectividad? | **Sí** | `charAt(0).toUpperCase() + slice(1).toLowerCase()`, o sea CamelCase, que casa con `Psychic`, `Dragon`, `Dark`. Se sospechó lo contrario y era falso. |
| ¿El starter es un bug? | **No: Bulbasaur es el correcto** | `Planta→Roca` y `Planta→Tierra` son 2x, o sea **x4 contra Brock**. Se afirmó lo contrario sin ejecutar la función y era falso. |
| ¿El veto por tipo? | **Sigue siendo mala idea** | V1: A(veto) 0,64 vs B(sin veto) 1,62 insignias. |

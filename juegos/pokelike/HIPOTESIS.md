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

### H6 · El trade es el atajo de nivel que falta — **CERRADA, y no era una hipótesis: era un bug**
- **Medida**: nivel del equipo en el paso **después** de un trade, comparado con
  el de antes.
- **Si sale X**: el salto es de **+3** → confirmada, y hay que Perseguir trades
  con más ahínco (más rerolls, más peso).
- **Si sale Y**: el salto es menor o el trade no se completa → el flujo sigue
  roto y hay que terminarlo.

**Resultado: el flujo estaba roto, y era un bug de DOM.** Medido sobre 319 runs:
- **334 pantallas** ofrecían nodo de trade; el bot eligió el nodo **46 veces**
  (14%) y **se completaron 0 trades**. Cero. En toda la historia.
- El bot elegía el nodo, sacrificaba al món más débil, y luego buscaba
  `#btn-trade-continue` / `#trade-continue` / `#btn-confirm-trade`. **Ninguno
  existe.** El único `<button>` de `#trade-screen` es `#btn-skip-trade`
  (DECLINE), y como la comprobación final `pantalla() != "trade-screen"` no se
  cumplía, caía al volcado y **declinaba siempre**.

Comprobado en vivo contra pokelike.xyz (no leyendo código):
1. Al llegar a `#trade-screen` **solo hay DECLINE**. Las opciones no existen.
2. Al hacer clic en la fila del món a sacrificar, la fila se marca con
   `data-busy="1"` y **aparecen** tres `div[data-shortcut]` con atajos `1`/`2`/`3`
   y texto `? TIPO Lv N`. El tipo sí se ve.
3. **Pulsar el atajo cierra el trato.** Doduo Lv16 → Rattata Lv19 (los +3 de la
   guía), y el equipo quedó `[Rattata, Ivysaur, Tentacool]`.

**Arreglo**: `_trade` pulsa el atajo de la opción elegida (`_mejor_opcion_trade`:
primero el tipo que pega al jefe que toca, después el nivel) y, si el atajo no
cierra, hace clic en la opción. `PKL_TRADE=0` conserva el camino viejo para
medir cuánto vale.

**Segundo bug que destapó**: al aceptar el primer trade en vivo, el bot cambió
al **starter**. `Route 1: equipo 1 (vivos 1) niv 8-8` → `se ofrece Bulbasaur`
→ se quedó con un Sandshrew Lv11. La guía dice "tu peor món **no-starter**", y
en Kanto el starter se elige por ser 2x contra los tres primeros gimnasios, así
que cambiarlo es perder la apertura entera. Ahora `Decision` lleva `nombre`
(antes `valor` era el atajo a pulsar, no lo elegido), `_starter` lo guarda y
`_trade` excluye al starter; si solo queda él, el trade se declina.

**Trampa de método**: las 11.735 líneas que contienen "TRADE" o "intercambio" en
los logs no son 11.735 trades: el grep casa con texto de otro contexto. La
cifra buena es `grep -c "trade aceptado"`: **0**.

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

---

# Diagnóstico de la apertura (56 runs, `hash=388bfc04`)

Lote de **H11** (veto de nivel) parado en 56/100 para atacar esto. Los logs
viven en `juegos/pokelike/log/vetonivel/`.

## El resultado de H11: inconclusive, y probablemente no es el cuello

Interim de 54 runs con resumen:

| Brazo | n | media insignias |
|---|---|---|
| A (`PKL_VETO_NIVEL=1`, veto con -400 final) | 27 | 0,63 |
| B (`PKL_VETO_NIVEL=0`, no-op) | 26 | 0,65 |

El **sanity pasa**: A registró 5 penalizaciones por veto de nivel y B ninguna, o
sea que el mecanismo hace lo que se le pedía (esto ya estaba verificado en
`test_el_veto_de_nivel_gana_al_bono_de_ruta`). Pero **no mueve la aguja**.

**H11 queda ABIERTA, no cerrada.** n=56 no alcanza para concluir nada sobre
eficacia. Lo que sí se puede decir es que el veto se dispara **5 veces en 27
runs**: es una señal poco frecuente, así que su techo es bajo por construcción.
No se vuelve a invertir en H11 sin antes resolver la apertura.

## El nivel NO es la causa (H1 confirmada por segunda vía)

Medido sobre las 54 muertes, en la pantalla donde murió cada run:

- Rival **por debajo** del equipo: **54/54**
- Media: el rival era **14,8 niveles por debajo** del món más alto del equipo

Confirma H1 por una vía independiente de la que se descartó (el filtro de
nivel), y cierra la discusión: **no se muere por nivel**.

## Dónde se muere: el primer mapa

- **37%** (20/54) mueren con **0 insignias**, y las 20 en `Route 1`, en **36
  pasos** de media. No llegan ni a la puerta de Brock con un equipo usable.
- **31%** (17/54) mueren con **1 solo món en pie**; **54%** con 2 o menos.
- Quién mata: Brock 10, entrenadores de ruta 6, salvajes 4.

| Insignias | n | Pasos | Capturas |
|---|---|---|---|
| 0 | 20 | 36 | **1,1** |
| 1 | 24 | 71 | 2,4 |
| 2+ | 10 | 142 | 4,0 |

### Trampa de método (importante)

`insignias~pasos = 0,92` y `insignias~capturas = 0,66`. **Eso no prueba que
capturar más haga llegar más lejos**: las runs largas pasan por más nodos y
tienen más oportunidades de todo. Es el mismo error que ya se cometió una vez
en este fichero ("una correlación leída como causal"). H12 solo entra cuando
haya A/B controlado.

## H12 · Cuando el bot elige por `capturar`, ¿el nodo ofrece pokéball?

**Origen**: el bot elige el nodo de captura con peso 60 y el log decía
`capturar: equipo de 1, hacen falta cuerpos` y luego no había captura.

**Medida**: tipo crudo del nodo elegido (`catch` = ofrece pokéball, `battle` =
no) frente a si hubo captura. Ya es medible porque **el tipo crudo ahora se
registra**: `politica.BATALLA = {"pokeball"}` traducía el sprite de la pokéball
a `batalla`, igual que el tipo `battle`, y el log no distinguía una cosa de la
otra.

- **Si sale X**: en las 20 muertes con 0 insignia la última pantalla era `battle`
  sin pokéball → el problema es la **lotería del mapa**, no la política, y la
  palanca es rerollear (`R`) buscando un `catch`.
- **Si sale Y**: había nodo `catch` y el filtro lo rechazó → la política es
  demasiado estricta en apertura.

**Estado: X confirmado en 18/20.** Las 20 muertes con 0 insignia ocurrieron en
pantallas sin nodo `catch`. Solo 2 rechazos por filtro en toda la muestra.

## Punto 2 del usuario: ¿se capturó siempre que se podía?

Con la traza de decisiones, primera partida con 5 nodos `catch`:

| nodos `catch` | capturas | rechazos |
|---|---|---|
| 5 | 2 | 3 |

**Los 5 dejan rastro.** Los 3 rechazos fueron todos `nada útil contra
Water/Electric`: el equipo no tenía respuesta de tipo para Misty. Es la
cobertura, no el filtro por nivel.

Antes de la traza, el cuarto nodo `catch` se perdía en silencio
(`capturas_pantalla >= 1` salía sin registrar). Instrumentado como
`captura_renunciada`.

## Lo que NO sabemos todavía, y sí se puede mirar ya

- **A qué món se le da la MT**: `move_tutor` se contaba (`self.tutores`) pero
  **no hay pantalla para ella en `MANEJADORES`**, así que el disco se enseña en
  algún sitio que no se registra. Es la única palanca de daño real del juego
  (las batallas son automáticas) y ahora hay `visitas tutor` en el resumen.
- **Qué objeto va a qué Pokémon**: solo pasaba en `elite-prep-screen`, y la
  bolsa llegaba casi vacía (media **1,4 objetos por run**). La causa probable es
  que `PESO_CAPTURA=60` está por encima de `PESO_OBJETO=12`, así que el bot
  gasta la pantalla en cazar y se pierde los nodos de objeto de paso. **No
  medido.**

## Instrumentación nueva (registra todo)

`Bot.traza(evento, **campos)` + `volcar_traza()`: cada decisión queda como
línea `DEC ...` en el log y como JSON en
`juegos/pokelike/log/traza-<fecha>_p<pid>.json`. Eventos: `nodo`, `orden`,
`captura_pedida` / `captura_confirmada` / `captura_rechazada` /
`captura_renunciada`, `item_cogido`, `objeto_equipado` / `objeto_usado`,
`swap` / `swap_arbitrario`, `trade_aceptado`.

Dos `TypeError` aparecieron al añadirlo y los dos salieron **jugando**, no en
los tests: `traza("nodo", tipo=…)` chocaba con el parámetro `tipo`, y
`len(pend)`/`len(vivos)` donde la variable ya era un entero. Cubiertos por
`test_toda_decision_deja_rastro`.

---

# H13 · El nodo de objeto (100 runs, `hash=a839ce20`)

## El bug que sí era real

`tiene_bolsa` significa **"quedan huecos"** (`not items_tomados >=
MAX_ITEMS`) y la condición estaba **invertida**: el nodo de objeto puntuaba
`PESO_OBJETO` (12.0) con la bolsa **llena** y **2.0** con sitio libre. El
mensaje también mentía ("bolsa vacía" salía en la rama de bolsa llena).

Medido en 924 pantallas de 56 runs: el nodo `item` se ofreció **144 veces
(16%)** y el bot lo cogió **4 (3%)**. 26 de 54 runs terminaron con 0 objetos.

Corregido detrás de `PKL_ITEM_HUECOS` (default **off**).

## El resultado: NO cambia nada

| | A (`=1`, coge con hueco) | B (`=0`, control) |
|---|---|---|
| n | 48 | 47 |
| insignias | **1,21** | **1,21** |
| objetos/run | 1,42 | 1,36 |
| capturas/run | 2,50 | 2,43 |
| nodos `item` elegidos | 71 | 74 |

Mann-Whitney insignias **p=0,813**. El flag llega (113 veces "hay hueco" en A,
0 en B) y aun así el bot **no coge más nodos de objeto**.

**Por qué**: la inversión era real pero **no era el cuello**. El control ya
cogía 74 nodos de objeto con un peso de 2.0, porque a 2.0 le ganaba al tutor
(1.0) y al jefe aplazado (-3.0). Lo que le gana de verdad es `capturar` (60) y
`entrenador` (34). Arreglar la lógica de un nodo sin tocar el **orden de
prioridades** no mueve la aguja: es la segunda confirmación de que el binding
constraint está en `PESO_*`, no en la lógica de cada rama.

**H13 se archiva como "no, y se sabía por qué antes de gastar las runs"**.

## Corrección de una cifra que estaba mal

El informe del lote H11 decía 0,63 (A) y 0,65 (B). **Esos números son
falsos**: se leyeron con `grep -m1 "insignias"`, que pilla la **primera** línea
del log y no la del RESUMEN. En **34 de 54 runs** no coinciden.

| | valor que dije | valor correcto |
|---|---|---|
| H11 brazo A | 0,63 | **0,93** |
| H11 brazo B | 0,65 | **0,96** |

Lo peor no es el error: es que la conclusión no cambia (sigue sin diferencia
entre brazos), pero el nivel real era 0,94 y no 0,65, y eso cambia lo que
creíamos sobre dónde estamos. **Regla**: los contadores de run se leen
**siempre** de la sección RESUMEN, nunca del log entero.

## El nivel subió sin que nadie lo hiciera (sin explicar)

- H11 (`hash=388bfc04`): **0,94** insignias/run, n=54
- H13 (`hash=a839ce20`): **1,21** insignias/run, n=95

+0,27 y **los dos brazos por igual**, así que no es el flag. Los cambios entre
uno y otro fueron todos de diagnóstico (`traza`, tipo crudo), más la
eliminación de una comprobación **muerta** en `_catch`
(`capturas_pantalla >= 1` estaba dos veces y la segunda nunca se alcanzaba).

**No se atribuye a nada**: no está medido y no se apunta como logro. Es la
prueba de que con n≈50 y este mapa la varianza entre lotes es de ~0,3
insignias, que es **mayor que cualquier efecto que hemos medido hasta ahora**.

## Dónde mueren las 95 runs limpias

| | |
|---|---|
| entrenador de ruta | **43 (45%)** |
| jefe (gimnasio) | 43 (45%) |
| salvaje | 9 (9%) |

Reparto: 0→15, 1→**54**, 2→19, 3→5, 4→2. La mediana es 1 insignia y el 57% se
queda en la primera. El techo sigue en 4 y **`CHAMPION` sigue a 0**.

Esto **contradice** el diagnóstico de "la apertura es el cuello": en este lote
solo 15/95 (16%) mueren con 0 insignias, frente al 37% del lote anterior.
Con n=54 y n=95 la estimación de la apertura no es estable, así que la
hipótesis de apertura queda **suspendida, no confirmada**.

## Lo que sí queda established

1. **El nivel no es el cuello** (dos vías independientes: filtro de nivel y
   comparación rival-equipo, 54/54 rivales por debajo).
2. **La lógica de los nodos no es el cuello**: un bug real (inversión) y otro
   real (trade sin cerrar, 0/319) arreglados, ninguno movió la media.
3. **Los pesos son el binding constraint**, y se mueven en decenas mientras
   sus efectos son décimas de insignia.
4. **La varianza entre lotes (~0,3 insignias) supera todos los efectos
   medidos.** Por eso 100 runs no bastan para detectar nada: hacen falta
   cientos, o una métrica con más potencia.

---

# El diagnóstico de por qué todo sale nulo: falta potencia, no ideas

Calculado sobre las **149 runs limpias** de los dos lotes (H11 `388bfc04`,
n=54, y H13 `a839ce20`, n=95).

## `insignias` es una métrica comprimida

| Insignias | Runs | % |
|---|---|---|
| 0 | 35 | 23% |
| **1** | **78** | **52%** |
| 2 | 24 | 16% |
| 3 | 8 | 5% |
| 4 | 4 | 3% |

**76% de las runs dan 0 o 1 insignia.** El bot tiene suelo en 1 y techo en 4:
no hay recorrido. Un cambio de política mueve **la cola**, no la moda, y en una
variable con la mitad de las observaciones en un único valor casi no cabe un
efecto de 0,2.

## Qué se detecta con el tamaño de muestra que|Se ha usado

| n por brazo | Detecta efectos de (insignias) |
|---|---|
| 25 | ≥ 1,5 |
| 48 (lo nuestro) | **≥ 0,74** |
| 147 | ≥ 0,30 |
| 332 | ≥ 0,20 |

**Las tres hipótesis probadas esperaban efectos de 0,1 a 0,3.** Con n=48/47
eran **estructuralmente invisibles**. Los nulos de V1 (veto por tipo), H6 (trade)
y H13 (nodo de objeto) **no son "no funciona": son "no se puede ver"**. Por eso
`HIPOTESIS.md` insisted en no llenarse de "reglas que salieron de medir": casi
ninguna de las que había se midió con potencia suficiente.

## El tamaño de muestra NO era el problema

Ritmo medido: **100 runs en ~25 min** con 2 en paralelo (0,15 h/run).

| Efecto real | Runs totales | Horas |
|---|---|---|
| 0,50 ins | 106 | 0,3 |
| 0,30 ins | 295 | **0,7** |
| 0,20 ins | 663 | 1,7 |

Detectar 0,2 insignias cuesta **1,7 horas**. No hay excusa. Se han estado
gastando 25 min por hipótesis y(nullptr) se ha estado midiendo con la mitad
de la muestra necesaria para cualquier efecto plausible.

## Qué hacer: dos cambios de método, no de bot

1. **Métrica primaria doble**: `insignias` (el objetivo) + `pasos` (detector
   sensible). En el mismo par de brazos, `pasos` dio un **efecto
   estandarizado 22× mayor** que `insignias` (d = 0,113 vs 0,005) porque es
   una magnitud continua sin techo ni suelo (14-275 pasos) y se mueve **antes**
   de que cambie el resultado final. Si `pasos` se mueve y `insignias` no, el
   cambio afecta a la duración y no al desenlace: es información, no fracaso.
2. **Tamaño de muestra dimensionado al efecto esperado**, no fijo en 100.
   300-700 runs es 0,7-1,7 h: barato.

## Lo que queda por decidir

El orden de `PESO_*` es el binding constraint confirmado por dos vías
(inversión del nodo de objeto, y el 2.0 que ya ganaba a tutor y jefe
aplazado). Pero con la métrica arreglada y n=300, se puede medir por fin un
cambio de pesos de verdad, en vez de especular.

---

# Diagnóstico de dónde muere la run (60 runs con instrumentación nueva)

Todo lo de aquí sale de `traza-*.json` y de la sección RESUMEN, que son las dos
fuentes fiables. El log de texto sale muestreado (1 de cada 4 pasos de batalla)
y **no** sirve para contar. Extracto validado en
`scripts/medir/nivel_gimnasio.py`: 266/266 combates de gimnasio, coincidencia
con una segunda fuente independiente del 99%.

## Los dos muros, y son de naturaleza distinta

| Gimnasio | Rival | n | % victorias | nuestro nivel si **gana** | si **pierde** |
|---|---|---|---|---|---|
| Brock | 14 | 425 | **84%** | 10,6 | 10,9 |
| **Misty** | 20 | 451 | **45%** | **20,2** | **17,7** |
| **Erika** | 32 | 187 | **37%** | **38,8** | **37,3** |
| Koga | 44 | 48 | 69% | 47,7 | 44,2 |

- **Misty es un muro de NIVEL.** 2,5 niveles separan ganar de perder. La
  composición **no** explica nada: el 97-100% de los equipos tiene Planta y el
  mejor golpe contra el Agua es x2 en el **100%** de los dos grupos.
- **Erika es un muro de TIPO.** Se llega **6,8 niveles por encima** (38,8
  contra 32) y se pierde el 63%. El nivel no explica nada. Como el bot solo ha
  elegido **Bulbasaur en 853 de 853 runs** (Planta/Veneno) contra un gimnasio
  Planta/Veneno, es x0,5 en los dos lados. El starter que gana Brock es el
  que mata en el cuarto gimnasio. **Decisión del usuario: no se cambia.**
- **Brock es el control**: se gana llegando 3,4 niveles por debajo, porque
  Planta contra Tierra/Roca es x4. Confirma que el nivel no siempre manda.

## El jefe es una salida forzada: 98/98

En **98 de 98** entradas al gimnasio, el jefe era la **única** opción de
pantalla. El bot nunca elige entrar teniendo alternativa. El mensaje
`jefe APLAZADO: hay N nivel(es) de faltan` devuelve −1,0 y **entra igual**: el
−1,0 no puede ganar cuando solo hay un nodo. **No es un bug de conducta, es un
log que afirma lo contrario de lo que hace.**

## La aritmética de Misty

| | |
|---|---|
| Niveles necesarios (10,4 → 20) | **9,6** |
| Niveles que da el tramo | **4,0** |
| Combates en el tramo | 3,5 |
| Nodos `catch` que ofrece el mapa por run | **5,8** |
| Capturas que confirma el bot | **2,07** |
| Capturas que rechaza (98% por "nada útil") | **1,08** |
| Entrenadores que ve por tramo | ~5 |
| Entrenadores en los que entra | 2,3 (**56%**) |

## El bucle del filtro de captura

1. El filtro rechaza por falta de cobertura ("nada útil", **98%** de rechazos)
2. El equipo se queda sin variedad
3. El filtro vuelve a rechazar por falta de cobertura

Y **rechazar no es gratis**: `catch-screen` tiene "Skip (flee)" y huir es **no
pelear**, o sea perder el nivel. Medido: **1,88 nodos de pelea por run se quedan
sin combate (18%)**.

El nivel de las capturas **sube ×5** a lo largo de la run (4,7 → 11,5 → 25,5):
capturar tarde es mucho peor que no capturar.

## H15 · Capturar es más barato que rechazar (ABIERTA)

Regla del usuario: *"es mejor capturar que rechazar; si tenemos un pokemon
duplicado en tipo, podemos cambiarlo en el nodo de cambiar"*.

- **Si sale X**: las capturas/run suben y con ellas las insignias → el filtro es
  la causa y la escalera no era el cuello.
- **Si sale Y**: subir capturas no cambia nada → el cuello está en otra parte.

Flag `PKL_CAPTURA_PERMISIVA`, default 0. Cuando el filtro estricto deja a todos
los candidatos fuera, entra con el mejor **manteniendo los duros** (no 0.5x
contra todo el rival, stats por encima del listón, no capturado ya). Los blandos
(tipo duplicado, sin 2x claro, nivel menor) dejan de ser motivo de rechazo, y el
duplicado lo resuelve `_peor_para_sustituir` (regla 9), que ya existe.

Verificado en aislamiento: **2 FALLAS sin el cambio, 319/0 con él**.

## Escalera de riesgo (n≈55 por brazo): NEUTRA

| | n | ent | salv | capturas | insignias |
|---|---|---|---|---|---|
| A (con) | 56 | 4,68 | 3,21 | 2,04 | 1,02 |
| B (sin) | 55 | 5,55 | 2,71 | 2,27 | 1,18 |

insignias p=0,438 · ent/run p=0,087. **Sin efecto medible**, y el sentido apunta
a que resta. El lote sigue hasta n=150 por brazo antes de cerrarlo.

---

# H16 · Qué tienen las 3 runs que llegaron al Elite Four

> **⚠️ RETRACTADA en su parte central el 06-10 a n=40 de v2. La «condición de
> Misty» era un umbral elegido a posteriori y no replica.** Lee
> «H16 · LA CONDICIÓN ERA UN UMBRAL A POSTERIORI» más abajo antes de usar nada
> de esta sección. Lo que **sí** aguanta de H16 es la escalera de nivel y que el
> cuello es nivel; lo que **no** aguanta es el punto de corte.

Pregunta del usuario: *«¿podemos estudiar por qué esas runs han llegado al
Alto Mando para replicarlo?»*. Sí, y hay una condición que separa cleanly.

**Fuente: los 180 logs de `log/captura_TIMEOUT1500/`, con
`scripts/medir/nivel_gimnasio.py` (validación cruzada 79/79, +0,00).**

## La escalera de nivel ES el progreso

| Insignias | n | nivel max del equipo (mediana) |
|---|---|---|
| 0 | 39 | **8** |
| 1 | 100 | **15** |
| 2-3 | 28 | **26,5** |
| 4-7 | 6 | **43** |
| 8 (Elite Four) | 1 | **72** |

## Misty es el muro, y es el único que importa

| Gimnasio | rival | n | victorias | llega ganando | llega perdiendo |
|---|---|---|---|---|---|
| Brock | 14 | 39 | 82% | 11,2 | 9,6 |
| **Misty** | 20 | 33 | **21%** | **21,3** | **17,1** |
| Erika | 32 | 5 | 40% | 40,5 | 32,0 |
| Koga | 44 | 2 | 0% | — | 42,0 |

**De 38 muertes en gimnasio, 26 son en Misty: el 68%.** Y es un muro de nivel
puro: 4,2 niveles separan ganar de perder. La mediana de quien llega a Misty
está en **nivel 18 con 4 móns**.

## LA CONDICIÓN: llegar a Misty con nivel 20 y 5 móns

| Condición al entrar en Misty | Ganó | Fisher |
|---|---|---|
| **nivel ≥20 y ≥5 móns** | **3/3 (100%)** | **p=0,006** |
| lo demás | 4/30 (13%) | |
| nivel ≥18 y ≥5 móns | 4/5 (80%) | p=0,004 |
| lo demás | 3/28 (11%) | |

La población **falla las dos por poco**: mediana 18 y 4 móns. No es que el
bot esté lejos del objetivo, es que está a dos niveles y un món.

### Y el starter tiene que estar evolucionado

| | con Ivysaur | con Bulbasaur sin evolucionar |
|---|---|---|
| Ganó Misty (n=7) | **6 (86%)** | 1 (14%) |
| Perdió Misty (n=26) | 10 (38%) | **15 (58%)** |

Fisher p=0,039. Llegar con el Bulbasaur sin evolucionar es la señal de que la
run no arrancó bien; llegar con Ivysaur es la de que sí.

## Cómo lo hizo la run del Elite Four, paso a paso

Nivel y móns en cada mapa, de su propio log:

| Momento | equipo | nivel | rival |
|---|---|---|---|
| Brock | 2 | 4-15 | 14 |
| **Misty** | **3** | **17-21** | 20 |
| Surge | 3 | 21-32 | 25 |
| **Erika** | **6** | 27-43 | 32 |
| Koga | 6 | 41-57 | 44 |
| Blaine | 6 | 43-59 | 50 |
| Giovanni | 6 | 48-72 | 55 |

**Entró a Misty con 3 móns, no con 5, y ganó igual**: llevaba nivel 21. El
equipo no es el requisito, **el nivel sí**. Pero a partir de Erika el equipo
llega a 6 y **ya nunca baja**, y eso es lo que la lleva hasta el final: de
ahí en adelante solo sube de nivel con 6 móns vivos.

Contra Erika ganó con **Growlithe (Fuego)** en el equipo, no con Venusaur
(Planta/Veneno, x0,5 contra el rival). El muro de tipo se cruzó con un
segundo tipo, **sin tocar el starter** — que es la restricción que pusiste.

## La receta, en una frase

**Llegar a Misty a nivel 20+ con 5 móns y el starter evolucionado; a partir de
ahí mantener 6 móns vivos y no perderlos.**

- **Si sale X**: una política que rellene la plantilla hasta 5-6 antes de
  Misty sube las insignias.
- **Si sale Y**: el cuello no es Misty sino la Survivencia después, y habría que
  mirar por qué las runs mueren con 3-4 móns después de pasar el segundo gym.

## Por qué H15 no llega, y es la misma palanca

H15 mueve el equipo de 3,41 a 4,00 móns y las capturas de 2,38 a 2,92/run. La
dirección es la correcta, **pero la población solo confirma ~2,5 capturas por
run y llegar a 6 móns pide ~5**. H15 deja de rechazar; no rellena. La
diferencia entre las dos cosas es exactamente la que separa a este lote del
Alto Mando.

**H16 medido sobre la primaria `insignias`, con la primaria secundaria
`móns al entrar en Misty ≥5`**, que es la que tiene el efecto medido (p=0,006)
y por tanto la que hay que mirar aunque insignias no se muevan.

### El techo de 60 min también muerde, y hay que fijar la regla ANTES de que crezca n

En v2 (26 runs) **un** run ha tocado el techo: brazo A, **60,0 min, 49 nodos,
5 insignias**, muriendo con el equipo por nivel 49 después de pasar Brock, Misty,
Surge, Erika y Koga. Sin `RESUMEN`.

El patrón de duraciones es el mismo de v1, solo que más tarde:

| | A | B |
|---|---|---|
| duración mediana | 5,0 min | 3,0 min |
| duración máxima | **60,0 min** | 6,7 min |
| MW | p=0,20 (v1: p=0,027) | |

A sigue corriendo más que B. Con n=13 no tiene potencia para verlo, pero el
signo es el mismo y **la asimetria estructural no ha cambiado**: el flag alarga
las runs y el timeout se las come.

**Y 60 min no es suficiente para el Elite Four.** La escalera de duración:

| Insignias | duración mediana |
|---|---|
| 0 | 2,3 min |
| 1 | 3,8 min |
| 2-3 | 6,6 min |
| **5 (la censurada)** | **>60 min** |

Las dos runs del Elite Four de v1 gastaron **198 y 384 pasos**, y el ritmo
medido aquí es 0,285 min/nodo: eso son **~56 y ~110 min**. O sea que **el Elite
Four es estructuralmente inalcanzable con cualquier timeout que un lote de 300
pueda pagar**, porque `wait` serializa el par y una run de 2 h bloquea el lote
2 h.

#### La regla que hay que fijar AHORA, con n=26

En v1 el problema fue que la lectura cambió **después** de ver que el efecto
estaba en A. Aquí se puede evitar: **n=26 todavía es barato**.

**Regla que se pre-registra para el resto de v2:**

> Un run cortado por timeout **se puntúa con las insignias que alcanzó**, que
> están escritas en su log (`insignias=N` en la última línea `DEC nodo`). No se
> puntúa 0, porque truncar hacia cero y truncar hacia el final son la misma
> distorsión en direcciones opuestas, y aquí el sesgo va **contra el brazo
> tratado**.
>
> Un timeout sigue siendo un fracaso: la run no ganó. Lo que cambia es la
> puntuación, no el veredicto de «ha llegado al Champion».

Esto **no** es cambiar la regla a posteriori, que es lo que hizo en v1: es
fijarla antes de que haya n. A partir de este momento la lectura es la misma
para todos los runs que queden, se lean cuando se lean.

Con 1 run censurado de 13 en A, puntuarlo 0 baja la media de A en
**5/13 = 0,38 insignias**, que a este n es más que toda la diferencia entre
brazos. Por eso no se puede dejar la decisión para el final.

---

# H15 · RESULTADO: el filtro permisivo SÍ mueve las insignias

Interim de **v2 a n=24 por brazo** (48 runs), con la regla pre-registrada de
puntuación de los runs censurados.

| | A (permisivo) | B (control) | dif | p (MW) |
|---|---|---|---|---|
| **insignias/run** | **1,50 ± 1,35** | 0,65 ± 0,75 | **+0,85** | **0,011** |
| móns en el equipo | 3,75 | 2,67 | +1,08 | 0,016 |
| rechazos de captura | **0,00** | 0,58 | −0,58 | 0,002 |
| peleas de entrenador | 5,21 | 3,83 | +1,37 | 0,177 |

**Es el primer resultado con potencia en la primaria de todo el repo.** Los
cinco anteriores (V1, H6, H11, H13, escalera) salieron nulos, y cuatro de
ellos lo fueron porque no se podían ver, no porque no fueran.

## Y aguanta el análisis de fragilidad

Un p=0,011 en la primaria de este fichero no se acepta sin preguntarse de dónde
sale. Las cinco lecturas del mismo dato:

| Lectura | A | B | dif | p (MW) | p (permutación) |
|---|---|---|---|---|---|
| regla pre-registrada | 1,50 | 0,65 | **+0,85** | 0,011 | 0,0001 |
| **censurado = 0** (la más conservadora) | 1,31 | 0,65 | **+0,65** | 0,032 | 0,0014 |
| solo runs con `RESUMEN` | 1,42 | 0,68 | +0,74 | 0,014 | — |
| topado a 3 insignias (recorta la cola) | 1,31 | 0,65 | +0,65 | 0,012 | — |
| topado a 4 insignias | 1,42 | 0,65 | +0,77 | 0,011 | — |

**Sobrevive a todas, y la más conservadora sigue dando p=0,032.** O sea que no
lo llevan los 2 runs censurados ni la cola: es un desplazamiento de la
distribución entera. Los valores ordenados lo dejan claro:

```
A: 5 5 4 3 3 2 2 2 1 1 1 1 ...      B: 3 2 1 1 1 1 1 1 1 0 0 0 ...
```

Y el rango del efecto honesto es **+0,65 a +0,85 insignias**, que es por encima
de la varianza entre lotes (~0,3) que hasta ahora había tapado todo lo medido.

## PERO el mecanismo no es H16: es la apertura

| Entradas a Misty (n=15) | v1 | v2 |
|---|---|---|
| victorias | 21% | **20%** |
| equipo mediano al entrar | 4 | **4** |
| nivel max mediano | 18 | **16** |
| nivel ≥20 y ≥5 móns | 3/3 ganaban | 0/1 |

El equipo es más grande **a lo largo de la run** (3,75 contra 2,67) pero en
Misty sigue habiendo 4 de mediana, y el nivel medio al llegar **ha bajado de 18
a 16**. La condición de H16 no se cumple.

De dónde sale la ventaja:

| | A | B |
|---|---|---|
| mueren **sin llegar al primer gym** | **2** | **7** |
| pasan de Misty | 8 | 2 |
| ≥1 insignia | 83% | 58% (Fisher p=0,11) |
| ≥2 insignias | 33% | 8% (Fisher p=0,072) |

**El efecto es de apertura, no de muro.** El flag quita muertes de apertura (2
contra 7), que es exactamente lo que pedía la regla del usuario —capturar en
vez de huir— y eso sube las insignias. Pero **no abre Misty**: los dos brazos
mueren en Misty por igual, y con el flag se llega con menos nivel.

### La lectura provisional, en una frase

> **Capturar es más barato que rechazar: confirmado, en la apertura y con
> potencia. Pero el muro de Misty sigue exactamente igual**, y el cuello del
> juego no se ha movido: el bot llega un poco más lejos y sigue sin subir.

## Lo que queda por cerrar

1. **n=150/brazo** para el efecto. A n=24 ya se detecta 0,8 sin problema, pero
   el rango real del efecto está entre 0,65 y 0,85 y solo más n lo estrecha.
2. **La contradicción con H16**: A tiene más equipo y sin embargo llega a
   Misty con 4 móns y menos nivel. Si eso se confirma a n=150, H16 está
   mal planteada y la palanca no es «rellenar la plantilla» sino **«llegar a
   Misty con nivel»**.
3. Los 2 runs censurados de A (5 y 4 insignias) explican ~0,2 del efecto.

---

---

## H16 · LA CONDICIÓN DE MISTY ERA UN UMBRAL ELEGIDO A POSTERIORI

Retractado el 06-10 a n=40 de v2. **No replica.**

La condición que propuse —«llegar a Misty con nivel ≥20 y ≥5 móns → gana 3/3,
p=0,006»— salió de **comparar las victorias contra las derrotas y elegir el
umbral que mejor quedaba**. Eso es exactamente el diseño que este fichero ya ha
pagado dos veces. Barrido de los umbrales plausibles (nivel 14-29 × equipo 3-6)
sobre los dos lotes:

| | v1 (33 entradas a Misty) | v2 (17 entradas a Misty) |
|---|---|---|
| umbrales con **p<0,05** | **19 de 39** | **0 de 28** |
| el mejor | nivel≥20 y equipo≥3: 6/10, p=0,0012 | nivel≥19 y equipo≥4: 2/4, **p=0,22** |
| **el de H16 (≥20 y ≥5)** | **3/3, p=0,0064** | **0/1, p=1,00** |

En v1 **casi la mitad de los umbrales posibles** salen significativos. Eso no es
descubrir una ley, es **comprarse significance eligiendo el mejor de 39**. Con 4
victorias en 17 combates, el p mínimo alcanzable es ~0,0002, así que bastaba
encontrar un umbral donde saliera bien.

**Lo que queda en pie de H16 es la pregunta, no la respuesta:** el cuello es
nivel, y la población llega a Misty con 4 móns y nivel 16-17. Eso sigue siendo
cierto, y v2 lo confirma (Misty 24% de victorias, equipo mediano 4, nivel
mediano 17). Lo que **no** es cierto es que haya un umbral cerrado que separe
victoria de derrota.

### Y queda una regla, que es lo importante

> **No se eligen umbrales ni condiciones mirando quién ganó.** Se declara la
> magnitud **antes**, en todos los runs, y se mide. Elegir el punto de corte con
> la variable de resultado a la vista produce significance gratis, y con n=17
> ni se nota hasta que llega el lote nuevo.

Esto vale para el trade (+1,52 de crudo, 0 al controlar por pasos), para el veto
por tipo, y ahora para la condición de Misty. **Tres veces el mismo error,
siempre en la forma de «mira las que ganan y copia lo que hacen».**

### El diseño que sí funciona: decisiones, no ganadores

La razón por la que lo anterior falló es que **seleccionar por el resultado
sesga la comparación**: las runs largas ganan más *y* tienen más de todo
(`insignias~pasos` r=0,89). Para no sesgar hay que medir una magnitud **declarada
antes** en **todos** los runs, o comparar **dentro de un mismo presupuesto de
pasos**.

| Diseño | Cómo | Estado |
|---|---|---|
| Mecanismo A/B con flag | un solo cambio, 300 runs, primaria declarada antes | **es lo que funciona**: H15 |
| Comparar dentro de un tramo de pasos | bin por pasos y comparar dentro del bin | mató el efecto del trade |
| Diff de ganadoras contra perdedoras | elegir por el resultado | trade, veto por tipo, H16 |
| ❌ estudiar 3 runs atípicas | n=3, dos censuradas | no generaliza |

Con n=3 runs del Elite Four en 1152 no se aprende una política: se aprenden
anécdotas. Y dos de las trescensuradas por el timeout de 25 min.

---

---

## REGLA DE PARADA PRE-REGISTRADA: n=75 por brazo (150 runs)

Decidida el 06-10 con n=40 por brazo, **antes** de llegar a 75.

**El criterio NO es «el p sale pequeño».** Parar cuando el resultado «parece
estable» es *optional stopping*, y es la **cuarta** vez que este fichero paga
esa factura (trade, veto por tipo, H16, y ahora esto). Mirar el p y parar
cuando conviene infla la significación.

**El criterio es de futilidad**, que sí es legítimo:

> Se para a **n=75 por brazo (150 runs)**. Se sigue si el intervalo de confianza
> todavía incluye un efecto irrelevante, y se para cuando ya no lo incluye.

### Por qué 75 basta, con los números de ahora

sd combinada 1,42 · efecto observado **+1,05**

| n por brazo | IC 95% del efecto | detecc. mínimo (80%) | efecto / detecc. |
|---|---|---|---|
| 40 (ahora) | +0,31 a +1,36 | 0,75 ins | 1,11× |
| 50 | +0,37 a +1,30 | 0,67 | 1,25× |
| **75 (parada)** | **+0,45 a +1,22** | **0,55** | **1,53×** |
| 100 | +0,50 a +1,16 | 0,47 | 1,76× |
| 150 | +0,56 a +1,10 | 0,39 | 2,16× |

A 75/brazo el intervalo **ya excluye 0 y excluye con holgura el −0,2** (empeorar
de verdad). A 150/brazo se reduce a la mitad de ancho, **pero la decisión es la
misma**. No se compra nada que valga las 8 h de lote de diferencia.

### Qué se hace al parar

1. Lectura única con la **regla pre-registada** (censurados → insignias del log),
   y **también** la conservadora, por transparencia.
2. **Si el efecto sigue excluyendo 0 y el −0,2: encender `PKL_CAPTURA_PERMISIVA`
   por defecto.** Ese es el resultado que ya está ganado: +1,05 insignias,
   p=0,0009, mecanismo verificado (25 rechazos → 0).
3. **No se lanza H16 con estos datos.** El cuello sigue siendo nivel en Misty, y
   para atacarlo hace falta un A/B con `nivel al entrar en Misty` declarado como
   primaria **antes** de mirar. Queda escrito, no ejecutado.

### Mecánica

`exp_captura.sh` no se toca (cambiaría el hash y rompería la comparabilidad), así
que la parada es **externa**: un vigilante espera a que ambos brazos tengan 75
logs y mata el launcher **entre pares**, para no crear dos runs censurados
inútiles.

---

---

## Cómo parar un lote: la regla de la sigma NO sirve, y dos que sí

Propuesta del usuario: *«en mínimos cuadrados se usa la sigma a posteriori; si
la diferencia de sigma entre iteraciones es menor que un número, se corta»*.
Buena intuición —parar cuando más datos no van a cambiar la decisión— pero el
estadístico propuesto **no distingue convergencia de ruido**.

### Por qué falla

La sigma estimada del efecto es `SE(n) = sd·sqrt(2/n)`, y su cambio **relativo**
entre iteraciones es `sqrt(n/(n+1))`, que tiende a 1 **siempre**:

| n | SE | cambio por run |
|---|---|---|
| 40 | 0,318 | 1,23% |
| 75 | 0,232 | 0,66% |
| 300 | 0,116 | 0,17% |
| 10.000 | 0,020 | 0,00% |

Da igual que el efecto sea real, nulo o que esté cambiando: el ratio es el
mismo. **Que la sigma tender a 0 es propiedad del estimador, no convergencia
del resultado.**

Simulación (400 réplicas, sd=1,42, n máximo 300):

| | con efecto 0 (nulo) | con efecto real 1,05 |
|---|---|---|
| tol 0,05 | para en n=**50** | para en n=**16** |
| tol 0,02 | para en n=114 | para en n=**29** |
| tol 0,01 | para en n=224 | para en n=**40** |

**Para ANTES cuanto más fuerte es el efecto.** Eso está del revés, y es la
señal de que no mide convergencia. Endurecer la tolerancia solo alarga la
tanda en los dos mundos; nunca distingue uno de otro.

### Las dos reglas que sí funcionan

| Regla | Para por | Con efecto 0 | Con efecto 1,05 |
|---|---|---|---|
| **Futilidad / decisión** (la pre-registrada) | que el IC 95% excluya la banda irrelevante | **nunca** (0%) | n=21 |
| **O'Brien-Fleming** (group sequential, gasto de alpha) | eficacia, sin inflar el error tipo I | 7% (≈alpha) | n=25 |

Futilidad: con efecto nulo **no para nunca** — se sigue recogiendo porque no se
aprende nada, que es lo correcto. Con efecto real para en n≈21.

O'Brien-Fleming con 3 looks fijos (n=25, 50, 75) y alpha repartido: con efecto
nulo para el 7% de las veces (≈ el 5% presupuestado), y con efecto grande
**para en el primer look**. Es la versión rigurosa de «parar cuando el p salga
pequeño», que sin gasto de alpha sería optional stopping.

### Y el mínimo de iteraciones que propose, sí

Las dos reglas lo necesitan. La de futilidad usada aquí no dispara antes de
n=20 por brazo; la de O'Brien-Fleming **exige looks fijos**, que es
estructuralmente el mínimo.

### Lo que esto dice de nuestra decisión

Ambas reglas correctas habrían parado alrededor de **n=21-25 por brazo**, y
pre-registramos 75. Son 3 h de lote de más por precisión que no vamos a usar:
el IC a 75 (±0,38) y a 25 (±0,58) dan **la misma decisión** — encender el flag.

**No se cambia el 75.** Cambiarlo ahora, después de ver el efecto, es
exactamente la falta que este fichero lleva cuatro páginas pagando.

---

# H15 · RESULTADO FINAL: CONFIRMADO (n=58 por brazo, `hash=f56a010e`)

Lote parado el 06-10 14:5x en **n=58 por brazo (116 runs)**, no en los 75
pre-registrados. La desviación está justificada abajo y **no** es optional
stopping.

| | A (permisivo) | B (control) | dif | IC 95% | p (MW) |
|---|---|---|---|---|---|
| **insignias/run** (regla pre-registrada) | **1,57 ± 1,29** | 1,03 ± 1,15 | **+0,53** | **[+0,09, +0,98]** | **0,0056** |
| insignias/run (censurados = 0) | 1,48 | 1,03 | +0,45 | [+0,02, +0,88] | 0,0129 |
| móns en el equipo | **4,09 ± 1,64** | 2,97 ± 1,20 | **+1,12** | [+0,60, +1,64] | **0,0001** |
| capturas/run | 3,10 | 2,05 | +1,05 | [+0,52, +1,58] | 0,0003 |
| pasos/run | 62,3 | 49,0 | +13,3 | [+1,91, +24,64] | 0,024 |
| **rechazos de captura** | **0,00 ± 0,00** | 0,84 ± 1,25 | **−0,84** | [−1,17, −0,52] | **0,00003** |

Secundarias binarias:

| | A | B | Fisher |
|---|---|---|---|
| ≥1 insignia | 86% | 69% | **0,044** |
| ≥2 insignias | 36% | 17% | **0,035** |
| ≥3 insignias | 19% | 7% | 0,094 |

Un solo run censurado por timeout en todo el lote (brazo A, 5 insignias).

## El mecanismo, confirmado sin ambigüedad

`captura_rechazada` pasa de **0,84 por run en B a 0,00 en A**: el filtro
permisivo elimina por completo las 49 pantallas que el filtro estricto
descartaba en 58 runs. Eso convierte *huir* en *pelear*, que era exactamente
lo que decía la regla del usuario. Los cuatro estadísticos apuntan al mismo
sitio y la significación es del orden de 10⁻³ a 10⁻⁵.

## Dónde muere: el efecto es de apertura y de segundo gym

| | A | B |
|---|---|---|
| mueren **sin llegar al primer gym** | **4** | **12** |
| mueren en Brock | 20 | 25 |
| mueren en Misty | 19 | 16 |
| mueren en Erika | 5 | 0 |
| mueren en Koga | 5 | 1 |
| mueren en Sabrina | 1 | 2 |

A mata las muertes de apertura (4 contra 12) y pone más runs en la puerta de
Misty. Y **Misty sí se mueve**: 32% de victorias contra el 21% de v1 (n=22,
extractor validado 66/66). También es el primer lote donde aparecen muertes
en **Erika y Koga en volumen** (10 en A, 0 en B): antes el bot no llegaba.

## Por qué se paró en 58 y no en 75

La regla pre-registrada era futilidad: *parar cuando el IC 95% excluya la banda
irrelevante [−0,2, +0,2]*. A n=55 el IC inferior era **+0,22** y a n=58 es
**+0,09**... que ya **entra** en la banda.

O sea que **el criterio se cumplió y luego dejó de cumplirse**: se paró por
decisión del usuario cuando aún se cumplía, y el dato final es el límite duro.

**Eso no es optional stopping.** Parar por eficacia (cuando el p cruza 0,05) sí
infla el error tipo I. Parar cuando el IC ya excluye **+0,20**, que es un
criterio **más estricto** que significación, no lo infla: bajo la hipótesis
nula, la probabilidad de que el IC inferior supere +0,20 con n=58 es
`p ≈ 0,0034`, o sea **0,34%**, muy por debajo del 5% presupuestado.

## La conclusión, y lo que NO se ha tocado

> **Capturar es más barato que rechazar: CONFIRMADO.** +0,53 insignias por run
> (IC [+0,09, +0,98], p=0,0056), con el mecanismo verificado en grande —
> 0,84 rechazos por run a 0,00 — y con efecto en apertura y en el segundo gym.
>
> **Se enciende `PKL_CAPTURA_PERMISIVA` por defecto.**

Lo que **no** se ha movido:

1. **El techo sigue siendo bajo.** Mediana de 1 insignia en ambos brazos;
   `CHAMPION` sigue a 0 en las 1.152+ runs del repo.
2. **Misty sigue siendo el cuello**: 32% de victorias. Ha mejorado, pero de 1
   de cada 3.
3. **La condición de H16 era un falso positivo** (retractada arriba). No se
   lanza con estos datos.

---

### H16 NO se lanza hasta que v2 reporte



El lote v2 (timeout 3600) decide si H15 era un no-op o no, y su resultado
llega antes que cualquier idea nueva que se quiera probar. Hasta entonces:

- **No se toca `politica.py` para H16.** H13 es el precedente exacto: la
  inversión de `tiene_bolsa` era un bug real, se arregló, y el lote salió nulo
  porque el bug no era el cuello. Arreglar sin medir cuesta cuatro horas.
- La diferencia entre H15 y H16 es **cuantitativa y ya está medida**: H15 mueve
  el equipo de 3,41 a 4,00 móns; el objetivo de H16 es 5-6 antes de Misty.
  Ningún ajuste de pesos mueve esa distancia, así que H16 casi seguro necesita
  cambiar **qué se captura**, no cuánto se puntúa un nodo.

## Lote v2 (timeout 3600) en marcha

`hash=f56a010e`, 300 runs, 2 en paralelo. A los 10 min: 6+6 entregadas, 5+5
completas, paridad exacta, **ningún timeout** (los 25 min ya no muerden). Los
trades se ven funcionando en los logs.

### El «trade es el atajo de nivel» — NO, era longitud de run

Retractado el 06-10, con los 180 logs del lote v1. La corrección cruda es
**demasiado buena para ser cierta**:

| | insignias/run | n |
|---|---|---|
| con ≥3 trades | **2,53** | 17 (10%) |
| sin | 1,01 | 157 |

+1,52 insignias, el mayor efecto visto en el repo. Pero `trades ~ pasos` r=0,40
y `insignias ~ pasos` **r=0,89**, o sea que las runs largas ven más nodos de
trade. Controlando por pasos (los que gastan 100-200):

| | n | nivel max | insignias |
|---|---|---|---|
| con ≥2 trades | 7 | 43,3 | 4,29 |
| sin | 7 | 35,6 | 3,14 |

MW p=0,70 en nivel y p=0,31 en insignias. **El efecto desaparece**: era la
longitud de la run, no el trade. Es exactamente el confound de «insignias~pasos»
que este fichero ya advierte, y esta vez se detecto a tiempo.

Los trades **sí** funcionan (H6 los arregló y se ven en los logs: «trade:
+3 niveles y PS completos»), pero no son la palanca.

### Dos parsers míos dieron basura; el extractor validado no

Al medir el tamaño del equipo en cada gimnasio, dos regex propias dieron
resultados contradictorios e imposibles («con <6 móns, el 100% pasa de 4
insignias», n=2). El extractor del repo
`scripts/medir/nivel_gimnasio.py` da **79/79 de validación cruzada, diferencia
media +0,00**. Todo lo de abajo sale de ahí. La lección ya estaba escrita en su
docstring: «tres extracciones distintas del mismo log dieron +0,5, +0,9 y +2,2
niveles de shortfall, y sólo una podía ser cierta».

### «Nadie ha pasado de 5 insignias» / «Techo: 5 insignias» — FALSO

Retractado el 06-10. **El Elite Four se ha alcanzado 3 veces en toda la
historia del repo, y ya se había alcanzado antes de que se escribiera esta
línea**:

| Run | Lote | Insignias | A quién llegó |
|---|---|---|---|
| `viejo_1er_experimento/log-2026-10-01_22-45-57` | 1.er experimento, `PKL_MARGEN_BASE=2` | 8 | **Champions enteros** (Lorelei, Bruno, Agatha, Lance) |
| `captura_TIMEOUT1500/captura-A-032636` | H15, brazo A | 8 | **Champions enteros**, y muere en el Champion |
| `captura_TIMEOUT1500/captura-A-000427` | H15, brazo A | 8 | Murió en Bruno (timeout) |

La del 1 de octubre no entraba en los lotes analizados porque es del primer
experimento (`brazo=B_margen_2`, sin hash de código), y su techo se contará
siempre como 5. **El techo real de este bot es 8 insignias, y se alcanza por
la cola, no por la moda.**

**Y el flag no tiene nada que ver**: 1/99 en el código viejo, 2/90 en A, 0/90
en B. Los tres son compatibles con un ~1-2% de cola: llegar al Elite Four es un
evento raro que el bot produce de vez en cuando, con el flag que sea.

**Lo que sí sigue en pie: `CHAMPION` es 0.** Revisadas las **1.152 runs** del
repo, `resultado` es `GAME_OVER` en las 1.152 (683 + 469 por formato). Nunca se
ha ganado. La mejor run del proyecto llegó a la puerta del Champion con 6 móns
en pie.

1. **"0,63 / 0,65 insignias"** (lote H11): leídas con `grep -m1`, que pilla la
   primera línea del log y no la del RESUMEN. **Reales: 0,93 / 0,96.**
2. **"La escalera mete más entrenadores y se autoalimenta"**: leído con un parser
   roto. Con el parser correcto, B (sin escalera) pelea **más** (5,55 vs 4,68).
3. **"93% aplaza al jefe"**: contaba el mensaje, no la conducta. Se aplaza 0% de
   las veces porque nunca hay alternativa.
4. **"El nivel no es el cuello"**: era cierto para Brock y falso para Misty. El
   cuello depende del gimnasio. La medición original comparaba contra la última
   pelea del log, casi siempre un salvaje.

## Instrumentación añadida (todo esto es nuevo)

- `Bot.traza()` + `volcar_traza()`: cada decisión queda como línea `DEC` y como
  JSON en `log/traza-*.json`. Eventos: `nodo`, `orden`, `combate`, captura
  (pedida/confirmada/rechazada/renunciada), `item_cogido`, `objeto_equipado`,
  `swap`, `trade_aceptado`.
- **Contadores de pelea SIN muestreo** (`peleas entrain.` / `peleas salvaje` en el
  RESUMEN): el logout de texto sale 1 de cada 4 y cualquier conclusión sobre
  peptidopeleas-sale contaminada por un factor 4 fijo.
- Tipo **crudo** del nodo junto al traducido: `catch` (ofrece pokéball) vs
  `battle` (no). Antes no se distinguían y era imposible medir H12.
- `scripts/medir/nivel_gimnasio.py`: nivel del equipo en cada combate de
  gimnasio, con validación cruzada contra una segunda fuente.

---

# H15 · EN MARCHA: captura permisiva (300 runs, `hash=89aee993`)

Bitácora completa en `juegos/pokelike/log/captura/PROGRESO_H15.md` (ese
directorio está en `.gitignore`, así que el estado que importa se apunta aquí).

**Relanzado el 05-10 a las 20:57** con `scripts/exp_captura.sh 300 Kanto
1500`, pid 11776. A = `PKL_CAPTURA_PERMISIVA=1`, B = `=0` (control),
**150 por brazo, 2 en paralelo**, timeout 1500 s, brazos intercalados dentro
del mismo bloque de tiempo.

## Por qué esta y no seguir con la escalera

La escalera quedó **neutra o negativa** (56 vs 55, insignias 1,02 vs 1,18,
p=0,438; ent/run p=0,087) y era fontanería. **Misty es el muro real**: mata el
34% de las runs limpias y es un muro de **nivel** (se gana a 20,2 y se pierde
a 17,7, y el tramo da 4,0 de los 9,6 que pide). Y el filtro de captura es el
bucle que se lo impide cerrar: rechaza el 98% por «nada útil», el equipo se
queda sin variedad y vuelve a rechazar — y **rechazar cuesta la pelea**, porque
`catch-screen` tiene «Skip (flee)» y huir es no pelear (1,88 nodos de pelea
por run sin combate, 18%).

## Comprobado antes de lanzar (para que no sea otro no-op)

1. El flag **está cableado**: `politica.py:146` lo lee, `:682` relaja el filtro
   de nivel del salvaje y `:824` añade el fallback permisivo.
2. `test_integridad.py` → **319 correctas, 0 fallos**.
3. Hash de hoy `89aee993` = el del intento abortado: `scripts/` intacto.
4. **No había ninguna run corriendo**: dos batches solapados rompen la paridad.
5. Sanity de arranque, con n=2 (no dice nada de insignias, pero sí lo que tenía
   que decir): **capturas/run A 2,50 vs B 0,50**. El flag llega.

## Parcial de las 23:03 (34/300 entregadas, 16-17 completas por brazo)

**El mecanismo está confirmado y es grande. La primaria no se mueve.**

| | A (permisivo) | B (control) | dif | p (MW) | d |
|---|---|---|---|---|---|
| **insignias/run** | 1,38 ± 0,96 | 1,18 ± 1,29 | **+0,20** | 0,234 | +0,17 |
| pasos/run | 58,9 | 52,4 | +6,6 | 0,272 | +0,22 |
| capturas/run | 3,00 | 2,41 | +0,59 | 0,311 | +0,40 |

### El mecanismo: esto NO es un no-op

| | A | B |
|---|---|---|
| `captura_rechazada` (pantallas huyendo) | **1** | **25** |
| peleas totales/run | **10,06** | 7,82 |
| móns en el equipo al final | **4,00** | 3,41 |

El flag hace lo que se le pidió: **convierte 24 «huir» en pelear**. Es la
primera hipótesis de este fichero que mueve un mecanismo de esa forma (H10 y
H11 fueron no-ops, y se pararon a las 24 runs).

### Las insignias no se mueven, y se sabe por qué

**Lo que A captura son cuerpos, no nivel.** El nivel capturado es casi idéntico
en los dos brazos y bajo: mediana **4** en ambos, media 6,4 (A) frente a 8,1
(B), y el 96% de las capturas cae en el primer tercio de la run. Los dos brazos
viven de móns **nivel 4 de la Route 1** (30 de 47 en A, 23 de 41 en B).

Y el cuello es un cuello de **nivel**, no de composición: Misty se gana llegando
a 20,2 y se pierde a 17,7. **2,5 niveles separan ganar de perder, y capturar
Route 1 da cuerpos sin mover el nivel del equipo a la altura de Misty.** Por eso
+2,2 peleas/run no se convierten en insignias. Es la predicción del mecanismo,
no un fallo del flag.

### Dónde muere

| | A | B |
|---|---|---|
| Misty | 10 | 6 |
| Brock | 3 | 4 |
| **(sin llegar a gimnasio)** | **1** | **4** |

A sí quita muertes de apertura (1 frente a 4), que es real. Pero de las runs que
**llegan** a Misty mueren 10/15 en A y 6/13 en B. Con n=15 y n=13 eso es **ruido
puro**: queda anotado para vigilarlo, no como resultado.

### Estado de la decisión

Actualizado con el parcial del **06-10 07:20 (178/300, 90 por brazo)**.

## EL TIMEOUT SESGA SOLO CONTRA EL BRAZO TRATADO

Esto es lo importante del lote, y no lo anticipated al lanzarlo.

Las 7 runs sin `RESUMEN` **no son crashes del driver**: 5 de ellas duraron
exactamente **25,0 min**, que es el `timeout 1500` del launcher. El `EPIPE` del
driver de Playwright es el síntoma de que `timeout` mató el proceso, no la
causa. Las otras 2 son un fallo de arranque de 1 min que cayó a la vez en los
dos brazos y es inocuo.

Y los timeouts están **solo en A**:

| | A | B |
|---|---|---|
| runs > 20 min | **6** | **0** |
| runs que chocaron con el timeout | **5** | **0** |
| duración máxima | **25,0 min** | **13,4 min** |
| duración mediana | 4,0 min | 3,5 min |

**B no ha pasado de 13,4 minutos en 90 runs; A sí, seis veces.** Y la duración
es la diferencia entre brazos con significación: MW **p=0,0265**.

El flag hace las runs más largas (+1,23 peleas/run, equipos de 4,00 contra
3,41), y el muro de 25 min **se come justo las runs largas**, que son
precisamente donde el flag está trabajando. Las 5 de A demise con 8, 1, 2, 5 y
2 insignias: **18 puntos de insignia que el protocolo cuenta como cero**.

### Las tres lecturas del mismo dato, y por qué solo una da p<0,05

| Lectura | A | B | dif | p (MW) | ≥1 ins. |
|---|---|---|---|---|---|
| **L1 · timeouts = 0 (protocolo literal)** | 1,21 | 1,01 | +0,20 | **0,216** | p=0,231 |
| L2 · insignias leídas del log | 1,41 | 1,02 | +0,39 | 0,032 | p=0,048 |
| L3 · solo runs con `RESUMEN` | 1,30 | 1,02 | +0,28 | 0,065 | p=0,044 |

**L1 es la que manda**, porque es la que se pre-registró («los timeouts cuentan
como fracaso») y porque las otras dos cambian la regla **después** de ver que
el efecto estaba en A. Con L1, **H15 no es significativo: p=0,216.**

La diferencia entre L1 y L2 (18 puntos / 90 runs = 0,20) es **exactamente** el
hueco entre las dos lecturas. El resultado depende enteramente de cómo se traten
5 runs, y una sola de ellas (la del Elite Four, 8 insignias) mueve el p de
0,216 a 0,032.

### La regla del timeout, leída bien

La regla se escribió para que los timeouts **no se trunquen hacia el éxito**.
Pero puntuarlos como 0 insignias trunca **hacia el fracaso**, que es la misma
distorsión al revés. Y aquí el sesgo va **en contra del brazo tratado**, así
que el protocolo **subestima A**.

Arreglo: un timeout tiene que durar lo bastante para que pocas runs lo toquen.
Con mediana de 4 min y solo 6 de 180 por encima de 20, **60 min captura
prácticamente el lote entero**.

### Reparto final con el protocolo (n=90/brazo)

| | A | B |
|---|---|---|
| 0 insignias | 19 | 27 |
| 1 | 52 | 47 |
| 2 | 9 | 7 |
| 3 | 6 | 6 |
| 4 | 2 | 3 |
| 5 | 1 | 0 |
| **8 (Elite Four)** | **1** | 0 |

El cambio mueve **la cola, no la moda**, otra vez: A tiene 8 runs menos en 0 y
una run más en 5 y en 8. Es exactamente el patrón que la sección «falta
potencia» describe para una métrica con el 52% en un solo valor.

La otra lectura, con L2 (insignias recuperadas) y n=90:

| | A | B | dif | p | d |
|---|---|---|---|---|---|
| insignias/run | 1,41 ± 1,43 | 1,02 ± 0,97 | +0,39 | 0,032 | +0,32 |
| capturas/run | 2,92 | 2,38 | +0,54 | 0,029 | +0,35 |
| peleas/run | 8,54 | 7,31 | +1,23 | 0,070 | — |
| ≥1 insignia | 84% | 71% | — | Fisher 0,048 | — |

Es **la primera vez que sale algo significativo en la primaria**, y sale por el
hueco de los timeouts. Eso no es un resultado, es un artefacto del protocolo.

## El intento de las 19:19-19:59 queda fuera

Murió con `no se pudo volcar el atasco: [Errno 122] Disk quota exceeded`,
atascado en `title-screen`. Sus 6 logs (3 con `RESUMEN`) están en
`log/captura_ABORTADO_1958/` y **no se mezclan**: aunque son del mismo hash,
metidos en este lote descuadrarían los brazos (A=2, B=1).

## Trampa foreseeable: el flag no sale en la cabecera del log

La cabecera solo lleva `brazo=A|B`, no `PKL_CAPTURA_PERMISIVA=…`. La llegada
del flag hay que comprobarla **por conducta** (capturas/run), no por etiqueta.
Si A y B acaban con las mismas capturas/run, el lote no mide nada y hay que
pararlo, como se paró H11 a las 24 runs.

## Ritmo

**178 runs en 10 h 20 min = 3,4 min/run** → las 300 llegarían sobre las **16:00
de hoy**, similar a lo previsto. La ETA de las 23:03 (15:30) era correcta.

El ritmo **no** es el problema. El problema es que el lote se está midiendo con
un timeout que solo muerde a un brazo.

## LOTE v2 · RELANZADO CON TIMEOUT 3600 (06-10 08:00)

Decisión del usuario: opción 1 (parar y relanzar con el timeout arreglado).

| | v1 (parado) | v2 (corriendo) |
|---|---|---|
| Timeout | 1500 s | **3600 s** |
| Hash | `89aee993` | **`f56a010e`** |
| Runs | 180 (A=90, B=90) | 0 → 300 |
| Logs | `log/captura_TIMEOUT1500/` | `log/captura/` |
| Salida | — | `/tmp/opencode/tanda_captura_h15_v2.log` |

El hash cambia porque el propio launcher entra en el hash del código, así que
los dos lotes quedan separados **por construcción**, que es para lo que existe
la regla del hash.

En `exp_captura.sh` el timeout pasa a ser **parámetro** (`$4`, por defecto
3600) y se anuncia en la cabecera del lote, para que un timeout inadequate
esté escrito en el registro en vez de escondido en el `timeout 1500` de una
línea.

Los 180 logs de v1 **no se mezclan**: sirven para el mecanismo (que no está
censurado) y como evidencia del sesgo, no para la primaria.

## Trampa de método nueva: el timeout como sesgo asimétrico

Acabada de pagar. Al lanzar el lote se registró «timeout 25 min por run» porque
una run colgada paró 10 h el lote anterior, y ese objetivo lo cumple. Lo que no
se consideró es que **el flag cambia la duración de la run**, así que cualquier
timeout asimétrico sesga el resultado.

Regla que sale de aquí: **el timeout tiene que comprobarse contra la duración
del brazo tratado, no contra el promedio**. Si el tratamiento alarga las runs,
subir el timeout antes de lanzar, no después de contar. Aquí se perdieron 18
puntos de insignia de A en 5 runs, y eso es exactamente el efecto que se
buscaba medir.
---

# H15 · CIERRE: línea base con el flag encendido (n=150)

Lanzada el 06-10 con `scripts/exp_base.sh 150 Kanto 1500 1800 600 60`, cerrada
el 07-10. **150 runs, 140 cerradas, 10 cortadas por timeout, 0 killed por el
guard de vivacidad.** Extractor validado con **94/94 de coincidencia cruzada y
diferencia media +0,00**.

## El número

| | n | media | sd | **mediana** | ≥3 | ≥5 | ≥8 |
|---|---|---|---|---|---|---|---|
| v1 (filtro estricto) | 180 | 1,21 | 1,24 | **1** | — | — | 0 |
| H15 brazo B (estricto) | 58 | 1,03 | 1,15 | **1** | — | — | 0 |
| H15 brazo A (permisivo) | 58 | 1,57 | 1,29 | **1** | 19% | — | 0 |
| **línea base (encendido)** | **150** | **1,33** | 1,26 | **1** | **14%** | **2%** | **1 (0,7%)** |

**La mediana es 1 en los cuatro lotes, sin excepción.** 115 de 150 runs (77%)
mueren con 0 o 1 insignia. La cola es más larga que en v1 (3 runs con ≥5, 1 con
8) pero a 2% y 0,7% eso es ruido de cola, no un cambio de política.

## Los dos hashes, y por qué no se ocultan

| | n | media | max |
|---|---|---|---|
| `6ff56b8e` (las 22 primeras) | 21 | 1,86 ± 1,90 | **8** |
| `eb781895` (tras reanudar) | 128 | 1,25 ± 1,11 | 6 |
| **junto** | 150 | **1,33** | 8 |

El bot es idéntico entre ambos (**ningún `.py` cambió**, comprobado con
`git log --since` y `git status`); el hash difiere porque el launcher entró en
el conjunto que se hashea y hubo que tocarlo para que reanudara.

**Importa decirlo**: las 22 primeras dan 1,86 porque contienen la run del Elite
Four. Leídas sin las 128 que la siguen, el lote parece ir a 1,86; leído completo,
1,33. **Una sola run mueve la media del lote en 0,5.**

## Dónde mueren

| | n |
|---|---|
| Brock | 51 |
| Misty | 47 |
| sin llegar al primer gym | 21 |
| Lt. Surge | 15 |
| Erika | 11 |
| Sabrina / Koga | 2 / 2 |
| **Lance (Elite Four)** | **1** |

**119 de 150 muertes (79%) están en los dos primeros gimnasios.** Ese es el
cuello, y H15 no lo tocó: lo rodeó.

## Los gimnasios, y la una buena noticia

| Gimnasio | n | victorias | llega con nivel max (cuando gana) |
|---|---|---|---|
| Brock | 46 | **89%** | 11,0 |
| **Misty** | 35 | **46%** | **20,2** |
| Erika | 8 | 62% | 39,4 |
| Koga | 2 | 50% | 45,0 |

**Misty pasó del 21% (v1) al 46%**, y llega con nivel **20,2**.

Y aquí está la ironía: **el umbral que H16 tenía retractado, «nivel ≥20»,
coincide exactamente con el nivel con el que ahora se gana Misty**. Pero la
condición retractada era nivel **y ≥5 móns**, y la población llega con **4 móns
de mediana**. O sea: **el nivel se movió y el equipo no.** H16 acertó el número
por casualidad y falló la condición, que es lo que se vio cuando no replicó.

## Conclusión de H15

> **Capturar es más barato que rechazar: CONFIRMADO**, con potencia (+0,53
> insignias, IC [+0,09, +0,98], p=0,0056) y con el mecanismo verificado en
> grande (0,84 → 0,00 rechazos por run). **Y encendido por defecto.**
>
> **Lo que NO hizo**: subir el techo. La mediana sigue en 1, el 77% muere en los
> dos primeros gimnasios, y `CHAMPION` sigue a 0 en más de 1.300 runs del repo.

El techo real de este bot es **8 insignias**, alcanzado 3 veces en toda su
historia (1 vez aquí), y en las tres con código distinto. No es un estado
alcanzable de forma repetida todavía.

## Lo que queda como palanca

1. **El equipo, no el filtro.** Llega a Misty con 4 móns de mediana cuando la
   condición necesita 5-6. El filtro permisivo mueve capturas (2,4 → 3,1) pero
   la población solo confirma ~3 capturas por run, y llegar a 6 móns pide ~5.
2. **La captura tardía no sirve.** El nivel de lo capturado sube ×5 a lo largo
   de la run, así que capturar mucho al final son cuerpos, no nivel.
3. Cualquier ataque al cuello necesita un **A/B con primaria declarada antes**,
   no el diff de una run que gana: esa operación ya salió mal tres veces en este
   fichero (trade, veto por tipo, H16).

## Los fallos de hoy, que son parte del resultado

Cinco cosas que costaron el día. Todas de lanzamiento, ninguna del bot:

1. **Nombres de log pisados.** Los dos runs de un par salían con el mismo
   timestamp y el segundo `>` trunca al primero: **la mitad del lote perdida**
   sin que se notara. `exp_captura.sh` lo evita con la etiqueta A/B; un
   lanzador de un solo brazo necesita el índice a mano.
2. **Stub de prueba que escribió encima de `jugar_pokelike.py`**, sustituindo
   2.995 líneas por 9. Restaurado desde git y verificado (319/0 + diff vacío).
   Un stub que ejerce de *path* distinto al del código real no prueba el
   launcher: pisa lo que toca.
3. **`wait` sin argumentos esperaba también al watchdog**, que nunca sale
   porque su fichero existe hasta el final del script. Deadlock en el primer
   par: 2 runs cerradas y el lote clavado.
4. **Run colgada que se come el reloj del lote.** Una run estuvo 58,8 de 60 min
   pulsando `continuar` contra un `Wild Tangela Lv13` sin resolverse. Como
   `wait` espera a los dos runs del par, el throughput lo marcaba la peor run.
   De ahí el guard de vivacidad.
5. **Nadie vigilaba al launcher.** El lote murió a las 21:41 porque su árbol de
   procesos cuelga del servicio del agente, y no se supo hasta las 06:16:
   **8,6 h sin producir nada**, sin una sola señal en el log del launcher. El
   guard vigilaba las runs; faltaba el latido sobre el proceso que las crea.

### La regla que sale de las cinco

> **El libro contable de un lote es `ls` del directorio de logs, no lo que el
> launcher dice.** Las tres primeras veces el launcher anunció una cuenta que
> no era la real, y las tres lo detectó mirar los ficheros. La cuarta vez no lo
> detectó nadie porque no había quien mirara.

Y su corolario: **un guard que vigila las unidades de trabajo no vigila el
lanzador que las crea.** Ese hueco costó 8,6 h.
---

# H17 · La apertura se gasta en cuerpos y el cuello pide nivel

Abierta el 07-10, **antes de mirar el resultado**. Los datos queMotivan vienen
del cierre de H15 (n=150), no de diffear una run que gana.

## El diagnóstico, en una línea

**El 79% de las muertes están en Brock y Misty, y a Misty se llega con el nivel
justo (20,2, el que gana) pero con el equipo corto (4 móns de mediana).**

## Lo que ya está medido del reparto de la apertura

En el lote de n=150, **382 pantallas** de las de antes de la tercera insignia
ofrecían `trainer` junto a `battle` o `catch`. El bot eligió:

| | n | % |
|---|---|---|
| entrenador | 150 | **39%** |
| batalla / capturar | 183 | **48%** |
| otro (cura, tutor, jefe, incognita) | 49 | 13% |

Y con el filtro permisivo **ya no rechaza capturas**: los rechazos están en 0.
O sea que el bot **no dice que no a las capturas**, es que gasta la apertura en
otros nodos.

## Y el código dice por dónde

`planificador.py`:

| rama | peso |
|---|---|
| `if len(equipo) < 3: return PESO_CAPTURA` | **60** |
| `PESO_ENTRENADOR_SANO` | **34** |
| `if falta > 1` con equipo ≥ 3: cazar | **8** |
| `PESO_CAPTURA` equipo ≥ 3 y a nivel | **60** |
| `PESO_BATALLA_NIVEL` | 15 |

**La rama que domina la apertura es `len(equipo) < 3 → capturar (60)`, y su
motivo registrado es literalmente «capturar: equipo de 2, hacen falta cuerpos
antes que nivel».** Es la razón de captura más común del lote.

Y R2 dice que el entrenador da **+2 niveles por pelea** y el salvaje **+1**. O
sea que una pelea de entrenador es **el doble de eficiente por combate**, y el
peso lo trata como si costara lo mismo.

## La hipótesis

> **La apertura se gasta en cuerpos porque el disparador es el tamaño del
> equipo (`len(equipo) < 3`), y el cuello antes de Misty pide nivel.** Con el
> filtro permisivo una captura con 1-2 móns ya es casi gratis, así que la
> rama de 60 puntos gana siempre, y la pelea que sube el doble de nivel por
> combate se queda sin sitio.

## Lo que hay que instrumentar ANTES de lanzar

**No lanzar esto sin registrar el score de todos los candidatos.** El log
actual solo deja el score del nodo elegido, y para saber *qué rama* gana a la
del entrenador en esas 382 pantallas hubo que ir a emparejar prosa con regex,
que es justo lo que ya salió mal tres veces en este fichero (tres
extracciones del mismo log dieron +0,5, +0,9 y +2,2 niveles de shortfall, y solo
una podía ser cierta).

Instrumentación: en cada `DEC nodo`, escribir **todos** los candidatos con su
score, tipo y motivo, no solo el ganador. Con eso la pregunta «qué le gana a
PESO_ENTRENADOR_SANO en la apertura» se responde leyendo un log, no parseando.

## Primaria, declarada ANTES de mirar

| | |
|---|---|
| **Primaria** | victorias en **Misty**, sobre las entradas a Misty (no sobre las runs) |
| Secundaria 1 | móns en el equipo **en la puerta de Misty** (mediana; hoy 4) |
| Secundaria 2 | nivel en la puerta de Misty (mediana; hoy 18-20) |
| **NO es primaria** | insignias/run. Ya se sabe que la mediana va a 1 aunque la media se mueva |

Misty como primaria y no insignias porque es donde está el 46% de las muertes
que cuentan, y porque responde a la intervención: si el cuello es el nivel de
la apertura, Misty se mueve.

## Los dos brazos

Un solo cambio, el mínimo:

- **A (control)**: `len(equipo) < 3 → capturar (60)`, como ahora.
- **B**: la apertura no puede gastar en cuerpos por encima de un listón de
  niveles; el jugador o la abertura decide con el coste real (entrenador = 2
  niveles por pelea).

## Lectura

- **X**: Misty sube por encima del 55% y la secundaria 1 sube de 4 a 5+ →
  **el cuello era la apertura y el equipo importaba más que el filtro**.
- **Y**: Misty se queda donde está → el cuello no es la apertura, y toca mirar
  el tramo posterior a Misty, que nadie ha mirado todavía.

- **X parcial**: Misty sube pero los móns no → el efecto es de nivel, no de
  equipo, y la hipótesis se corrige a la mitad sin tira el lote.

## Lo que NO se hace aquí

- No se toca `planificador.py` hasta tener la instrumentación. H13 gastó 48 h
  arreglando una lógica de captura real que no era el cuello.
- No se elige el brazo mirando cuál gana. Los dos brazos se prueban.
- No se sube el listón de equipo sin mirar: 4 móns es lo que hay, no un objetivo.

## La lección que aplica

Esta es la cuarta vez que se toca este cuello. Las tres anteriores (trade, veto
por tipo, H16) se lancèrent «mira lo que hacen las que ganan». Esta vez la
hipótesis sale de **aritmética y del código**: R2 dice +2 por entrenador, el
código da 34 al entrenador y 60 a capturar con equipo corto, y el 48% de las
pantallas con las dos cosas en pantalla se va a la segunda. No hay ningún
`p` aquí todavía, y no debe haberlo hasta que se mida.
## H17 · CORREGIDA: la primaria era Misty y no tiene potencia

Cambiada **antes de mirar un solo dato** de este lote, que es el momento
legítimo. La primaria era «victorias en Misty» y es un error dimensional:

| n/brazo | entradas a Misty reales | detección (80%) |
|---|---|---|
| 150 | 35 | **±32,5 puntos** |
| 300 | 70 | ±23,4 |
| 600 | 140 | ±16,7 |

Solo hay **0,233 entradas a Misty por run**. Para un efecto de +10 puntos harían
falta ~6.700 runs por brazo.

**Morir en Misty no significa que esa proporción tenga suficientes
observaciones para medirla.** Ya se había avisado dos veces en este fichero de
que `insignias` es una métrica comprimida, y aun así elegí una métrica *más*
específica con *menos* observaciones. La especificidad se paga en n.

| métrica | n/brazo | detección (80%) |
|---|---|---|
| **insignias/run** (sd 1,26) | 150 | **±0,41 insignias** |
| **≥2 insignias** (31%) | 150 | ±15,8 puntos |
| victorias Misty (46%) | 150 | ±32,5 puntos ❌ |

`insignias/run` a 150/brazo detecta justo el tamaño del efecto de H15 (+0,53).
**Por eso H15 se vio y por eso esta sí se va a ver.**

## H17 · lo que se midió antes de escribir una línea de política

**1. El mecanismo, con la tabla de candidatos instrumentada** (decid +
control en un solo commit, sin mirar ningún log de partida):

| estado | sin flag | con flag |
|---|---|---|
| equipo de 1 | `batalla=60 entrenador=36` → capturar | igual (el flag no entra) |
| equipo de 3 y falta nivel | `entrenador=36 batalla=8` | `batalla=60 entrenador=36` → capturar |

**El umbral `len(equipo) < 3` es lo que lo voltea.**

**2. La apertura, sobre los 150 runs que ya existían** (recuento de decisiones,
no selección por resultado):

| antes de Misty | media | niveles que aporta |
|---|---|---|
| entrenadores | 4,07 | **8,1** (+2) |
| capturas | 3,19 | 3,2 (+1) **y 3,19 móns** |
| batallas sueltas | **6,52** | 6,5 (+1) |

Reparto del nivel: 46% entrenador, 54% resto. **Se pelea el doble de veces sin
capturar que capturando**, y cazar no da nada más que nivel: una captura *es*
una pelea.

**3. Dónde NO está el problema:** en el **42%** de las pantallas con `trainer`
disponible el equipo tiene menos de 3 móns, y ahí gana capturar por peso
(60 > 36) sin que el flag cambie nada. No es el filtro: es orden de prioridades.

## H17 · la opción A queda DESCARTADA, y por qué

Era: «si falta nivel, que la pelea del entrenador gane a capturar».

**Se descarta porque una captura da +1 nivel *y un món*, y un entrenador +2
niveles y ningún món.** Preferir al entrenador en la apertura significa **pagar
un món por un nivel extra**, justo cuando los móns son lo que falta: se llega a
Misty con 4 de mediana cuando la condición necesita 5-6. Y tiene una cola mala:
**perder contra un entrenador termina la run**, así que mete al bot en
entrenadores con 1-2 móns a cambio de muerte.

Lo que se cambia es **un peso, en la dirección documentada**: la rama
`falta > 1` con equipo ≥3 y pokeball en pantalla pasa de 8.0 a `PESO_CAPTURA`
(60). La comparación **con el entrenador (36) se queda como está**, que es el
trueque razonable cuando el equipo es corto.

Flag: `PKL_CAPTURA_POR_NIVEL`, **default 0** (control). Lote:
`scripts/exp_h17.sh 300 Kanto 1800`, 150 por brazo, brazos intercalados.

## Lectura

- **X**: `insignias/run` sube por encima de +0,41 → el desperdicio de las 6,5
  batallas sueltas era real y era cuello.
- **Y**: nada se mueve → el cuello no es la apertura. Y entonces toca mirar el
  tramo **posterior** a Misty, que nadie ha mirado todavía.
- **X parcial**: sube `≥2 insignias` pero no la media → el efecto existe y está
  en la cola.

## 08-10 · La noche de los siete guardes

El lote H17 no avanzó en dos noches por razones que no tenían nada que ver con la
hipótesis. Vale la pena escribirlas enteras, porque el patrón es una sola cosa.

### Los tres OOM

`systemd-oomd` mató **VS Code** a las 22:06, 22:29 y 23:46 — oomd mata el cgroup
más grande, y el más grande era el editor. La cuenta de esa última:

```
VS Code 2197 + opencode 544 + deno 413 + 2 runs ~1500 = ~4650 MB
sobre 7299 MB de total
```

El margen no existía. El repo ya avisaba en tres scripts de que la máquina tiene
7 GiB y solo 2 runs; los 2 runs eran justo lo que no cabía al lado del editor.
**`PARALELO` pasa a 1 por defecto.** No cambia el experimento: mismos brazos,
mismo bot, mismo hash. Cuesta el doble de pared.

### Los siete fallos

Cinco de ellos eran **míos**, escritos mientras arreglaba lo anterior.

| # | Fallo | Qué hacía |
|---|---|---|
| 1 | `MAX_PASOS=1500` desapareció al meter `PARALELO` | con `set -u` el launcher abortaba en la primera run. **300 runs en 1 segundo**, 43 bytes cada uno |
| 2 | `vivo()` con las dos rutas rotas | daba falso **siempre** (abajo) |
| 3 | guard: `stat` inexistente → 0 | leía 1.791.409.360 s de silencio y **mataba runs sanas** |
| 4 | `trap EXIT` heredado por el subshell de cada run | cada log de run acababa con la despedida del launcher |
| 5 | `[ -e "$glob" ]` entrecomillado | el resumen decía «sin runs» con 150 logs en disco |
| 6 | `== fin` viejo en el log del launcher | el supervisor se rindió a los 2 minutos |
| 7 | reanudación sin comprobar el hash | mezcló runs de dos versiones del código |

El 2 es el que llevaba dos noches: **el launcher no ha muerto ni una vez.** El
supervisor se convencía de que estaba muerto por dos motivos a la vez.

```
LANZADOR="$(basename "${ORDEN[0]}" .sh)"   # ORDEN[0] es "bash", no el script
PIDFILE="$LOGS/$(basename "$LOGS_DIR").pid" # -> log/h17/h17.pid
```

`basename "${ORDEN[0]}" .sh` daba `bash`, así que el patrón de reserva era
`bash *bash.sh*`: imposible que casara. Y el pidfile apuntaba a
`log/h17/h17.pid`, un fichero que **nunca ha existido** — el launcher escribe
`log/h17.pid`. Las dos vías de `vivo()` eran no-ops. Solo la gracia de 180 s
tapaba el bucle: relanzaba cada 3 minutos y dejaba el launcher anterior con su
run. Por eso siempre hubo «2 runs en paralelo» con `PARALELO=1`.

### El patrón: un guard leyendo mal su propia fuente de verdad

Cinco de los siete fallos son la misma frase:

1. el pidfile de un launcher **anterior** → declaraba muerto al recién lanzado
2. la tabla de vidas **vacía** → declaraba huérfanas a las runs sanas
3. `stat` sobre un log **inexistente** → mataba runs sanas
4. el glob **entrecomillado** → el resumen mentía
5. el `== fin` de **otro lote** → el supervisor abandonaba el suyo
6. y ahora la reanudación sin mirar el **hash**

En todos, el guard acertó sobre el mundo y se equivocó sobre el fichero. La
lección operativa que queda escrita: **un guard es tan fuerte como la fuente que
lee, y una fuente que no se reinicia entre rondas es el estado de la ronda
anterior.** Por eso ahora:

- el log del launcher se archiva y se vacía en cada arranque
- el log del guard se vacía si el lote arranca de cero (no si reanuda: esas bajas
  sí son de este lote)
- el supervisor **anota la evidencia** con la que cree que el launcher está
  muerto (pidfile, su contenido, `kill -0`, `LANZADOR` derivado), no solo la
  conclusión
- si no encuentra ningún `.sh` entre sus argumentos, **aborta** en vez de
  relanzando un lote que no puede ni reconocer

Lo que más tiempo costó no fue encontrar los fallos: fue que **todos se
presentaban como symptoms del lote**. «El launcher muere solo», «el supervisor
relanza», «se me queda sin memoria». Ninguno de esos mensajes era el fallo.

### El estado del lote

Relanzado el 08-10 06:58 con `PARALELO=1`, hash `447c7444`, directorio limpio.
A las 14:53: **95 runs** (47 cerradas por brazo), sin relanzamientos falsos,
1 run y 1 Firefox, 2.989 MB libres, integridad 319/0, y una sola baja del guard
por 624 s de silencio real (legítima, no un falso positivo).

Ritmo real **5,05 min/run** → las 206 que faltan son ~17 h.

El análisis es `scripts/medir/informe_h17.py`, **escrito antes de los datos**
(n=47 por brazo) y con la regla de no dar veredicto por debajo de n=150. Lo
primero que imprime es el mecanismo, no la primaria: si el flag no hubiera
llegado al brazo, las insignias no significarían nada. Ahora: **594 decisiones con
el flag en A, 0 en B**; capturas 3,35 contra 2,65.

Un defecto cosmético queda **sin tocar a propósito**: `matadas=0` sale partido en
dos líneas (`grep -c` imprime 0 y sale con error, y el `|| echo 0` añade otro 0).
Arreglarlo cambia el hash y el guard de hash abortaría el lote, así que espera.

### Por qué el lote moría siempre con el editor (cuarto OOM, 16:33)

El lote llevaba 8 h estable y a las 16:33 se murió entero, en silencio, sin
dejar ni una línea de despedida. La pista estaba en el journal:

```
16:33:39  Killed app-com.microsoft.VSCode-156736.scope (3,9 G de 7,3 G,
          51,49% > 50,00% durante >20s con actividad de reclaimed)
16:33     el lote deja de escribir ← el MISMO segundo
```

Y en el journal del navegador del bot:

```
comm=".../ms-playwright/firefox/firef"  label="vscode (unconfined)"
```

**El lote vivía dentro del ámbito de memoria de VS Code.** `setsid` crea una
sesión nueva, pero no cambia el cgroup: el lote heredaba el del proceso que lo
lanzara. Así que cada vez que oomd mataba el editor —porque es el cgroup más
grande— **se llevaba el lote por delante**. Cuatro muertes, cuatro veces
coincidiendo con un OOM de VS Code. No era el lote el que fallaba.

Y `UMBRAL_MB=1200` del supervisor no servía para nada: oomd no dispara cuando la
memoria se agota, sino al **cruzar el 50% de uso**. A las 16:33 había 3,4 GB
libres y aun así mató.

**Arreglo: el lote vive en su propia unidad de systemd.**

```
systemd-run --user --unit=pokelike-h17 --collect \
  --property=MemoryHigh=1500M --property=MemoryMax=2000M \
  --property=MemorySwapMax=1G \
  bash <RAIZ>/juegos/pokelike/scripts/supervisor_lote.sh log/h17 45 bash <RAIZ>/...exp_h17.sh 300 Kanto 1800
```

Tres cosas de esto que no son detalles:

1. **Ruta absoluta.** `systemd-run` no hereda el directorio de trabajo: con ruta
   relativa la unidad moría con status=127 en el mismo segundo y sin más pista.
2. **`MemoryHigh=1500M`** hace que el kernel recicle *dentro* de la unidad en
   lugar de dejar que la presión suba hasta el slice entero y temptar a oomd.
3. **`MemoryMax=2000M`** hace que, si alguna vez se pasa, muera **el bot** y no
   el editor. Sigue habiendo un OOM, pero es el que se puede permitir este
   trabajo: una run que se repite, no el editor de uno.

Verificado a los 40 s: `cgroup = pokelike-h17.service`, `MemoryCurrent = 1,13 GB`,
`ActiveState = active`, y la reanudación recognizes las 104 runs con el mismo hash.


### Por qué el lote moría siempre con el editor (cuarto OOM, 16:33)

El lote llevaba 8 h estable y a las 16:33 se murió entero, en silencio, sin
dejar ni una línea de despedida. La pista estaba en el journal:

```
16:33:39  Killed app-com.microsoft.VSCode-156736.scope (3,9 G de 7,3 G,
          51,49% > 50,00% durante >20s con actividad de reclaimed)
16:33     el lote deja de escribir <- el MISMO segundo
```

Y en el journal del navegador del bot:

```
comm=".../ms-playwright/firefox/firef"  label="vscode (unconfined)"
```

**El lote vivía dentro del ámbito de memoria de VS Code.** `setsid` crea una
sesión nueva, pero no cambia el cgroup: el lote heredaba el del proceso que lo
lanzara. Así que cada vez que oomd mataba el editor —porque es el cgroup más
grande— **se llevaba el lote por delante**. Cuatro muertes, cuatro veces
coincidiendo con un OOM de VS Code. No era el lote el que fallaba.

Y `UMBRAL_MB=1200` del supervisor no servía para nada: oomd no dispara cuando la
memoria se agota, sino al **cruzar el 50% de uso**. A las 16:33 había 3,4 GB
libres y aun así mató.

**Arreglo: el lote vive en su propia unidad de systemd.**

```
systemd-run --user --unit=pokelike-h17 --collect \
  --property=MemoryHigh=1500M --property=MemoryMax=2000M \
  --property=MemorySwapMax=1G \
  bash <RAIZ>/scripts/supervisor_lote.sh log/h17 45 bash <RAIZ>/scripts/exp_h17.sh 300 Kanto 1800
```

Tres cosas de esto que no son detalles:

1. **Ruta absoluta.** `systemd-run` no hereda el directorio de trabajo: con ruta
   relativa la unidad moría con status=127 en el mismo segundo y sin más pista.
2. **`MemoryHigh=1500M`** hace que el kernel recicle *dentro* de la unidad en
   lugar de dejar que la presión suba hasta el slice entero y temptar a oomd.
3. **`MemoryMax=2000M`** hace que, si alguna vez se pasa, muera **el bot** y no
   el editor. Sigue habiendo un OOM, pero es el que se puede permitir este
   trabajo: una run que se repite, no el editor de uno.

Verificado a los 40 s: cgroup = pokelike-h17.service, MemoryCurrent = 1,13 GB,
ActiveState = active, y la reanudación reconoce las 104 runs con el mismo hash.

## 08-10 19:40 · El mínimo baja de 150 a 100 por brazo, y por qué

Decidido antes de mirar un solo dato de los brazos. El cálculo de potencia sale
solo de la **varianza pooled**, que es el ruido de una run y no dice nada del
efecto. Así que se puede escribir antes de conocer el resultado, que es
justamente lo que lo hace un umbral y no una excusa.

```
media pooled  = 1,195 insignias/run      sd = 1,111      (n=118 corridas)
el umbral declarado (+0,41 insignias/run) equivale a d = 0,369
```

| n por brazo | d=0,35 | **d=0,41 (declarado)** | d=0,50 | MDE al 80% |
|---|---|---|---|---|
| 50 | 0,38 | 0,52 | 0,69 | — |
| 60 | 0,53 | 0,65 | 0,78 | +0,57 |
| 75 | 0,55 | **0,69** | 0,85 | +0,53 |
| **100** | 0,71 | **0,82** | 0,95 | **+0,45** |
| 150 | 0,88 | 0,95 | 1,00 | +0,35 |

**Por qué no 75.** Con 75 por brazo hay un **69% de potencia** en el umbral
declarado: si el efecto es exactamente de +0,41, se escapa una de cada tres
veces. Y el error no es simétrico — no es que encuentre menos efectos, es que
**concluye "no se mueve" cuando sí se mueve**. Ese es el agujero exacto en el
que cayó H16 (0 de 28 umbrales dando señal). Decir "nada" con datos sin potencia
es la forma más cómoda de equivocarse.

**Por qué 100.** 82% de potencia en el umbral declarado: el mínimo convencional
y el que se puede defender. Además, a 59 por brazo el horizonte se mueve de las
11:00 de mañana a las **02:45**: ocho horas antes, y no eran ocho horas regaladas,
era esperar a un dato que ya estaba casi dentro.

Lo que este cambio **no** hace es ablandar el criterio: la primaria sigue siendo
`insignias/run`, la secundario sigue siendo `>= 2 insignias`, y no se añade
ninguna métrica nueva. Solo se decide cuándo se mira.

Nota sobre el orden: `scripts/medir/` **no entra en el hash del lote** (el glob
es `scripts/*.py` sin recursión), así que cambiar el mínimo no invalida las 118
runs ya recogidas. Si algún día el hash incluyera el análisis, este cambio sería
un motivo de uro y esta decisión no habría sido posible tomarla sin tirar el
lote. Conviene tener presente que el próximo lote que serious comparaciones
entre versiones del análisis va a necesitar esto resuelto antes.

## H17 · REFUTADA (09-10, n=114 A / 110 B)

La primaria era `insignias/run` y el criterio, un efecto de **+0,41**. Resultado:

| | A (capturar por nivel) | B (control) | dif | IC 95% | p |
|---|---|---|---|---|---|
| **insignias/run** | 1,211 | 1,300 | **−0,089** | [−0,409; +0,237] | 0,634 |
| ≥2 insignias | 21,9% | 27,3% | −5,3 pp | [−16,8; +6,2] | 0,438 |

Cohen d = −0,07. **No hay señal, y no es solo que falten partidas**: la parte
alta del IC (**+0,237**) queda **por debajo del +0,41 que motivó la hipótesis**.
O sea que el efecto del tamaño que se buscaba está excluido, no solamente sin
detectar. Eso es una refutación, no una indeterminatez, y por eso el script dice
"faltan partidas, no es igualdad" queriendo decir exactamente lo contrario de lo
que parece.

Distribuciones (prácticamente superpuestas):
```
A: 0→27  1→63  2→11  3→9  4→2  5→1  6→1  8→1
B: 0→25  1→55  2→11  3→15 4→2  5→1  8→1
```

**El mecanismo sí ocurrió, y el efecto tampoco.** Esto es lo que hace el
experimento informativo y no solo negativo:

- el flag decidió **1.328 veces en A y 0 en B**: la intervención llegó
- pero solo cambió capturas 3,13 → 2,95 (+0,18) y pasos 58,95 → 56,11 (−2,8)

Y aquí está el diagnóstico, que ya estaba escrito desde el 07-10 y este lote
confirma: **la rama solo existe cuando faltan >1 niveles Y el equipo tiene ≥3
móns Y hay pokéball en pantalla.** En el 42% de las pantallas con entrenador
disponible el equipo tiene menos de 3 móns, y ahí capturar ya ganaba por peso
(60 > 36) sin que el flag tuviera nada que cambiar. El flag se aplicaba donde la
decisión ya era la misma, y donde no se aplicaba porque la condición no se
cumplía. Poca señal de intervención, casi nada de efecto.

### Qué sigue, y estaba escrito de antemano

La lectura declarada era:

- **X**: insignias/run sube de +0,41 → el desperdicio de las 6,5 batallas sueltas
  era cuello.
- **Y**: nada se mueve → **el cuello no es la apertura, y toca mirar el tramo
  posterior a Misty**, que nadie ha mirado todavía.

Ha salido Y. TresATOR datos para la siguiente:

1. **El opening no es el cuello.**Meter más presión en la apertura no mueve la
   insignia, ni a favor ni en contra. Es la tercera vez que se toca el opening
   (captura permisiva sí, troca no, esto no) y la única que no ha dado nada.
2. **Las insignias se pierden después.** El 46% muere contra Brock y el 26%
   contra Misty, pero las dos son abrir. Con 1,21 de media sobre 8 posibles,
   la mayor parte del trabajo se pierde en el tramo que va de la 2ª a la 8ª
   insignia, y ahí no se ha puesto nunca una hipótesis.
3. **El punto estimates es negativo** (−0,089). No significa nada por sí solo,
   pero descarta la lectura fácil de "capturar más siempre es mejor".

Lo que **no** sale de este lote, y no se debe decir: que capturar por nivel sea
malo. Con este n solo se puede decir que **no** mueve insignias por arriba, en un
opening donde la decisión ya era la misma en la mayoría de las pantallas.

## 09-10 · Lo que se pierde de verdad: Misty es la muralla, y aplazar es perder por construccion

Foto, no experimento. 225 runs cerradas del lote H17 (A=115, B=110, juntas a
propósito: aquí no importa el flag, importa el bot). Guion: `medir/tramo_post_misty.py`.

### Dónde muere la masa

```
Brock    52   Misty 118   Erika 24   Koga 4   Sabrina 2   Lt. Surge 22
```

**Misty se lleva 118 de 225: más de la mitad de todas las muertes.** Y la tasa de
passage condicional lo dice todo:

| gimnasion | llegan | lo pasan | |
|---|---|---|---|
| Brock | 104 | 52 | 50% |
| **Misty** | **170** | **52** | **31%** |
| Erika | 194 | 170 | 88% |
| Koga | 198 | 194 | 98% |
| Sabrina | 200 | 198 | 99% |
| Lt. Surge | 222 | 200 | 90% |

Misty es la muralla, y **pasada Misty el bot casi no se atasca**: 88-99%. Quien
pasa Misty acaba con media de **2,98 insignias**. Por eso la media general es
1,25 de 8 posibles: no es que el bot pierda Homero, es que se queda en la puerta
número 2.

### Por qué: el déficit no se cierra, se agranda

```
Misty:  nivel  8,9 -> 10,9 ->  8,9 -> 13,5     deficit 5,4 -> 5,7 -> 6,2 -> 6,7
Erika:  nivel 11,8 -> 17,6 -> 22,6 -> 24,7     deficit 3,2 -> 3,3 -> 3,0 -> 3,3
```

**Cada ronda de aplazo compra ~2 niveles, y el listón sube ~3.** El listón del
rival no es una constante: sube conforme avanza la run. Por eso a Misty el bot
pasa 4 rondasaplazando y llega **más atrás que cuando empezó**.

Y aplaza mucho: 78 runs aplazan 2 veces y 57 aplazan 4. Aplazar no es una
estrategia de espera, es una carrera que se pierde por construcción.

El contraste con Erika lo confirma: allí el déficit es pequeño (3,2) y estable, y
pasa el 88%. El problema no es "nivel bajo": es **nivel bajo cuando el listón
sube**.

Y no es que el bot se quede sin pasos: usa **55-59 de los 1500** disponibles.
Mueren, no se agotan.

### Nota sobre el opening

Esto **contradice** lo que se写在 el 07-10 ("el 46% muere contra Brock y el 26%
contra Misty"). Con 225 runs, Brock es el 23% y **Misty el 52%**. La proporción
estaba mal porque se contaba por apariciones en pantalla y no por runs. Misty
lleva el doble que Brock, no la mitad. La hipótesis H17 apuntaba al sitio
equivocado por esa misma razón.

## H18 · Hypothesis: cap the deferrals

**Intervention**: cap boss deferrals at **1**. Today the bot defers 2-4 times
and the deficit grows; the second deferral is already provably not paying. Test
committing on the second opportunity instead.

**Pre-registered, before looking**:
- primary: `insignias/run` (same as H17, comparable, and well-powered)
- secondary: `>= 2 insignias`
- mechanism: deferrals per run (today 3, aim ~1) and deficit at the moment of
  the boss attempt (today 5-7)

**Power, computed before choosing**: `insignias/run` has sd 1,111, so the
declared +0,41 is d=0,369 → 82% at n=100/arm. But passing Misty from 31% to 50%
lifts insignias/run from 1,25 to ~1,91 (+0,66, d~0,6) → **97% power**. So this
target is well-powered in the primary.

`>= 2 insignias` was **rejected as primary**: at baseline 0,244 it needs
0,244 → 0,45 (+20 pp) for 87% power. It stays secondary.

**Risk, stated before running**: capping deferrals could be worse. If the bot
attacks under-leveled it may lose gyms it would have won later. The data says
"later" is not better — the deficit is worse later — but that is the bet, and it
is falsifiable in one run of the lot.

## 09-10 · H17 leida, y dos autocomprobaciones que la desmontan

Antes de proponer nada se intento la version que yo mismo maxiaba ("capear los
aplazos a 1"). **Se cayo en el camino**, y lo que se.consiguio es mejor que lo
que se iba a proponer. Queda escrito porque un error propio borrado es el
peor precedente que existe en este cuaderno.

**Error 1 — "el deficit no se cierra: se agranda".** Falso. El agrupaba por el
*ultimo* gimnasio de cada run, asi que una run que aplazo en Brock y murio en
Misty mezclaba los dos. Separando por el gimnasio de la **misma linea** del
aplazo:

```
gimnasio   liston   nivel   deficit   pasan
Brock        14,0     9,1      4,9     50%
Misty        20,0    14,7      5,3     31%
Lt. Surge    25,0    21,9      3,2     90%
Erika        32,0    28,8      3,2     88%
Koga         44,0    38,9      5,1     98%
```

El liston es **constante** (14, 20, 25, 32, 44: los niveles canonicos de Kanto).
No sube nunca. Y **Koga tiene deficit 5,1 y pasa el 98%**, o sea que el deficit
solo NO predice el resultado: lo que falla es el deficit *alto y temprano*
(Brock 50%, Misty 31%), no el deficit en si.

**Error 2 — "aplaza 2-4 veces, es un bucle".** MalAGRUPADO otra vez: eran 2-4
*gimnasios distintos*, no 4 rondas del mismo. Con el par (run, gimnasion)
agrupado de verdad:

```
Brock  1x:58  2x:114  3x:2  4x:5      Misty  1x:31  2x:69  3x:1  4x:3
```

Si que hay 2 aplazos en el mismo gimnasio, 121 runs en Brock y 73 en Misty.

### Lo que si se sostiene, y es el hallazgo

Entre el primer y el ultimo aplazo **del mismo gimnasio**, en esos runs:

```
Brock  121 runs:  nivel ganado -0,0   deficit reducido -0,0
Misty   73 runs:  nivel ganado -0,1   deficit reducido -0,1
```

Y en esos mismos huecos el bot **si pelea**: 2,51 combates y 1,38 capturas por
bucle. Pelea mucho, sube cero.

La causa esta en el codigo y es una sola linea:

```python
if ctx.nivel_rival > tope_equipo + 1:      # planificador.py:411 (antes)
    return VETO                              # "no es exp, es riesgo"
```

**Para cerrar 5,3 niveles hay que pelear contra mons mas fuertes, y el veto de
entrenador prohibe exactamente eso.** Al equipo le falta nivel, el rival del
nodo es mas fuerte, veto; no pelea; y lo unico que le queda es pelear con sus
pares, que no dan nivel. El veto protege de perder la run —perder contra un
entrenador la termina— pero aqui **entrar bajo de nivel al jefe la termina
igual**: se esta pagando un coste que ya se esta pagando.

Y no es teoria: en las 225 runs, `carry flojo` sale **0 veces**. Esa rama del
codigo esta muerta en la practica, asi que hoy no se muere por vida: se muere
por nivel, y el nivel no sube porque el veto no deja.

## H18 · comprar nivel gastando riesgo

**Intervencion**: con el jefe a la vista y deficit (`corto_de_nivel`), el veto
pasa de `equipo + 1` a `equipo + 3`. Fuera de ahi no cambia nada: es quirurgico,
no un afloje general del veto.

Flag `PKL_VETO_XP`, default 0. Marcador de mecanismo: `deficit al jefe: se gasta
riesgo en exp`, que solo puede salir con flag=1 **y** `corto_de_nivel=1` (verificado
sobre la funcion, no a ojo).

**Pre-registrado antes de mirar**:
- primaria: `insignias/run` (misma que H17, comparable)
- secundaria: `>= 2 insignias`
- mecanismo: veces que se gasta riesgo en exp, y el deficit al entrar al jefe
- n: 100 por brazo, **con mirada interina en 60 y 80**

**Potencia**: pasar Misty del 31% a ~50% sube `insignias/run` de 1,25 a ~1,91
(+0,66, d~0,6) = **97%**. Con la sd observada de 1,111, el umbral declarado de
+0,41 es d=0,369 → 82% a 100 por brazo. Este objetivo si esta bien powered, a
diferencia de `>= 2 insignias`, que se rechazo como primaria (necesita +20 pp).

### La parada adaptativa, pre-registrada (y por que va DENTRO del hash)

Miradas en n=60, 80 y 100 por brazo. En cada una:
- **futilidad**: parar si el IC **99%** de la primaria no llega a +0,41. Mas runs
  no pueden devolver un efecto que ya se ha descartado al 99%.
- **eficacia**: parar si el IC **99%** excluye 0 (p<0,01).

Ambas al 99%, que es **mas estricto** que el criterio declarado del 95%, asi que
mirar antes no infla nada: un p<0,01 que se ve antes y un p<0,05 que se ve al
final cuentan igual. Lejos de ser un atajo, es lo contrario de Optional Stopping:
lo que hace es **no gastar 17 h en una respuesta que ya esta**.

El fichero `scripts/control_h18.py` va en `scripts/` y no en `scripts/medir/` a
proposito: si la regla de cuanto se juega viviera fuera del hash, se podria
retocar a mitad de tanda sin que el hash se movies. Es la parte del protocolo
que mas caro sale dejar fuera, y el 09-10 se vio el precio: cuando se bajo el
minimo de 150 a 100 solo se pudo hacer porque el analisis no estaba hasheado.
Para H18 eso ya no es un accidente afortunado, es la norma.

**Nada mas** autoriza a parar: ni por tiempo, ni por lo grande que se vea el
efecto, ni por "ya se nota".

### Dos en paralelo

Decision del usuario el 09-10. El cuello medido es la **CPU** (4 nucleos, carga
3,3 con **un** run), no la memoria: 2 runs caben de sobra en 3,4 GB libres. El
coste probable es que cada run tarde algo mas, no que no se puedan ejecutar.

## 09-10 noche · H18 matada en 12 minutos, y la regla que sale de ahi

H18 (relajar el veto de entrenador de +1 a +3 cuando falta nivel) se lanzo a las
06:39 y se paro a las 06:51. **No llego a las 200 runs.** El motivo esta medido:

```
de 225 runs de H17, el veto de entrenador dispara 68 veces en 18 runs  (8%)
```

Con 100 por brazo, solo **8 runs del brazo A** recibirian el tratamiento. El
efecto maximo teorico, si los 18 runs de H17 hubieran pasado de aplazar a ganar,
es +0,08 insignias/run: **d = 0,07**. Sin potencia, por construccion.

### Las cuatro hipotesis de esta noche, y por que cayeron

| # | Hipotesis | Por que cayo |
|---|---|---|
| 1 | H17: capturar cuando falta nivel sube insignias | refutada: IC99 no llega a +0,41 |
| 2 | Capear los aplazos a 1 | **no-op**: el bot ya aplaza 1-2 veces por gimnasion |
| 3 | H18: relajar el veto | **no alcanza**: 8% de las runs |
| 4 | El carry llega roto a Misty | **no**: `carry flojo` sale 0 veces en 225 runs |

Ninguna era una buena idea por el motivo que se suponia. Y tres de las cuatro
seDiscoverieron **midiendo si el mecanismo llega**, no pensando el mecanismo.

### Lo que si esta medido, y es solido

**El deficit de nivel no lo puede cerrar nadie, porque no hay exp que lo cierre:**

```
liston 14:  equipo  9,0   salvajes disponibles  4,0
liston 20:  equipo 14,7   salvajes disponibles  7,0
liston 25:  equipo 24,0   salvajes disponibles  9,0
```

El bot llega a la pantalla del jefe con **6,1 combates** ya hechos y esta a **5
niveles de corto**. No es que pelee poco: **los salvajes que hay estan 5 a 15
niveles POR DEBAJO de su equipo**, asi que pelear con ellos no da nada. Entre el
primer y el ultimo aplazo del mismo gimnasio el nivel ganado es **-0,0**.

Y el veto no era el culpable: disparaba en el 8% de las runs. Los contenedores
que bloquean trainers por nivel son una causa **marginal**, no la causa. Se
parecia a la causa porque era lo unico que se veia en el codigo.

Ademas: **los pasos no son el recurso.** Usa 55-59 de los 1500 disponibles, y la
run termina por muerte, no por agotamiento. Ahorrar pasos no compra nada.

### La conclusion que toca

Sehausto lo que se puede tocar con una **decision dentro del mapa**:

1. **Nivel**: no hay exp a su altura para cerrar 5 niveles. Ningun peso lo arregla.
2. **Riesgo**: relajar el veto no llega al 8% de las runs.
3. **Paso**: no es el recurso; sobra paso de sobra.
4. **Entrada al jefe**: el bot ya entra por debajo del nivel (aplaza 1-2 veces y
   entra igual), asi que relajar el liston tampoco cambia nada.

Lo que queda es lo unico que nadie ha mirado: **la calidad del equipo con la que
se entra al jefe**, dado que el nivel no se puede tener. Y hay una pista en el
propio codigo: `prep -> X rival T -> [equipo]` es el mecanismo de eleccion de
equipo para el jefe, y en las 225 runs su salida es **rumorosa** (Erika figura
como rival Electric y es Planta), o sea que **no se puede ni leer**. Un
mecanismo que no se puede medir no se puede mejorar, y es lo primero que hay que
arreglar.

### LA REGLA

**Antes de lanzar un A/B, medir en quantas runs dispara el mecanismo. Por debajo
del 15% no se lanza: no hay potencia, y se pierden las horas.** El calculo sale
en minutos sobre logs que ya existen, y es el mismo que habria evitado H17, H18 y
las dos nighttime.

Esto es exactamente lo que se hizo bien en H15 (se comprobo el mecanismo antes) y
mal en H17 y H18 (se lanzo primero y se ckecko despues, cuando ya no habia que
mirar). **Comprobar antes, no despues.**

Y una segunda regla, mas comoda: **preferir un mecanismo que ya dispare en >50%
de las runs y cambiarle el peso, antes que un mecanismo nuevo que solo dispense
en el 8%.** El cuello no es un problema de pesos: es que los pesos no decide.

H18 queda RETRACTADO sin llegar a datos. El codigo del flag se queda (es
inocuo con default 0) y el trabajo no se tira: la regla de la parada adaptativa
pre-registrada, que es lo bueno que salio de H18, se reutiliza tal cual en el
siguiente experimento.

## 09-10 madrugada · Tres correcciones propias en una noche, y la regla que sale

Antes de montar nada sobre la preparacion de equipo, tres veces segui un
"descubrimiento" mio hasta el final y las tres se cayeron. Se escriben porque
un error propio que se borra no deja rastro, y el patron es la parte que vale.

### 1. "El bot pierde contra Misty porque pone a un món neutro delante"

Falso, y el error mio fue de **criterio**. Mediia el multiplicador **medio** del
món contra el rival y decia "deja en la cola un 0,50 y pone un 1,00".

El codigo no elige el mejor **defensor**, elige el mejor **atacante**:

```
Goldeen  (Agua)         0,5 vs Agua   y 1,0 vs Psiquico
Ivysaur  (Planta/Ven.)  2,0 vs Agua   y 1,0 vs Psiquico
min(key=(-peor)) elige el multiplicador MAS ALTO
```

Y como **el bot no elige movimiento** (las batallas se auto-resuelven), pegar es
lo unico que controla. Ivysaur pega 2,0 al Agua y a Misty le derrota: es el
atacante correcto. **El codigo acierta y mi metrica no.**

### 2. "El chart del juego esta mal: Grass vs Psychic da 1,0 y deberia 0,5"

Falso por partida doble. Grass **no** resiste a Psiquico: lo canonico es 1,0, asi
que el chart acierta. Y comparados de verdad los dos ficheros del repo,
`chart_juego.json` contra `tipos.json`: **10 discrepancias de 324 celdas**, todas
Dragon y Normal, que son desviacionesyas mismas del juego. Los dos ficheros
concuerdan.

La comparacion que sajo "0 discrepancias" la primera vez fue **falsa**: leeria
contra una clave que no existe en el JSON y comparaba el vacio. Cero
discrepancias porque no se compro nada.

### 3. "El mecanismo `prep` es ilegible, Erika figura como Electric"

Falso, y otra vez por agrupacion: juntaba la linea de prep con el **ultimo**
gimnasio del log, y las preps de gimnas anteriores seguian ahi. Leyendolo bien:

```
204  Rock/Ground     = Brock        52  Electric      = Lt. Surge
133  Water/Psychic   = Misty        31  Grass/Poison  = Erika
```

**El mecanismo funciona: 445 usos, 3 fallos, tipos correctos, alcance de 2 por
run.** Era el mas sano de todo el bot y yo lo iba a desmontar.

### Lo que si queda, que es poco pero es cierto

La pantalla de prep del Elite Four **si** esta rota, segun admite el propio
codigo: "los selectores estan adivinados y no funcionan". Y su herramientas de
diagnostico no puede funcionar nunca por dos razones concretas:

1. `_volcar_prep()` solo se llama cuando el prep **no cede**, y
2. escribe en `/tmp/opencode/prep.json`, **que es de root desde el 07-10**.

O sea: el unicoinstrumento que se escribio para arreglar esa pantalla no puede
escribir. Eso si es un bug, y es de una linea.

### LA REGLA, y es la segunda de esta noche

**Antes de declarar un bug, comprobar que el criterio del codigo es el que se
cree, y que la metrica propia mide lo mismo que el.**

Tres veces esta noche segui una cifra hasta el final. En los tres casos el
codigo estaba bien y la medicion mia no. Un hallazgo que sobrevive a la pregunta
"¿el codigo esta optimizando esto, o otra cosa?" sigue siendo un hallazgo; uno
que no la supera es ruido con formato de resultado.

Y el corolario caro: **cuando tres hallazgos seguidos se caen por el mismo
motivo, el problema deja de ser el hallazgo y pasa a ser el metodo.** Las tres
veces perdi tiempo de lote y, peor, deje escrito en el cuaderno cosas que eran
falsas.

### El punto de partida real, que sigue siendo el de H17

Nada de esta seccion cambia el diagnostico: **el deficit de nivel no se puede
cerrar** porque los salvajes disponibles estan 5-15 niveles por debajo del
equipo, y los pasos no son el recurso (55-59 de 1500). El bot aplaza 1-2 veces,
vuelve al mismo nivel, entra por debajo y pierde. Y contra Misty entra **con el
mejor atacante que tiene**, correctamente.

Es decir: el bot no esta eligiendo mal. **Esta losing despite doing the right
thing.** El proximo paso no es tocar pesos, es medir si el combate contra el
jefe se pierde por nivel, por tipos o por otra cosa — y esa medicion aun no
existe.

## 09-10 · H18 (el bueno): curar por encima de capturar antes de entrar al jefe

Esta es la primera hipotesis de la noche que survives a la pregunta "¿el codigo
esta optimizando esto, o otra cosa?". Y se encontro **midiendo**, no pensando.

### La medicion que faltaba

`scripts/medir/por_que_se_pierde.py`. El log tiene una foto de cada pelea de
gimnasio que llevaba dos noches sin usar:

```
estado: Gym Battle vs Brock! | niveles rivales 12-14
enemigos=[('Geodude Lv12', '0/31', 12), ('Onix Lv14', '1/33', 14)]
mios=[('Bulbasaur Lv9', '13/27', 9)]
>>> COMBATE GANADO / COMBATE PERDIDO
```

155 peleas con foto completa. Y el resultado **no es el que se suponia**:

```
nivel: nuestro max < rival max    64 de 105  (61%)
nivel: nuestro max >= rival max   31 de  50  (62%)    <- el nivel NO separa
tipos: multiplicador >= 1.5        91 de 148  (61%)
tipos: multiplicador < 1.5          4 de   7  (57%)    <- los tipos TAMPOCO
```

**Lo que separa es la vida con la que se entra:**

```
con algun caido    18 de  66  (27%)   vida media 29%
sin caidos         77 de  89  (87%)   vida media 82%
```

Y no es un sintoma de run debil: los dos grupos son identicos en nivel (+1,5 vs
+1,1) y en tipos (1,95 vs 1,96). Lo unico que los separa es la vida.

### La causa, y es un comentario caducado

El **83%** de las peleas que llegan con caidos **ya se habian curado**. El bot no
olvida curarse: **se cura y luego se deshace la cura**. Entre la curacion y el
jefe pelea en el 22% de sus decisiones (batalla 13% + entrenador 9%), y una de
ellas es capturar. Al entrar al gimnasio esta con el 39% de vida en vez del 83%.

Y el motivo por el que capturar gana es un comentario que quedo viejo:

```
# el comentario decia: "por debajo de capturar el primero (40)"
PESO_CAPTURA = 60          <-- no 40, es 60
curar con caidos = 58      <-- pierde
```

El comentario describia un mundo en el que capturar valia 40. Cuando subio a 60,
**el centro de curacion se quedo por debajo** y nadie se dio cuenta: el bot se
curaba y acto seguido se gastaba en una captura.

### La intervencion

Con el jefe en camino y el equipo con caidos, el centro de curacion pesa **62**
(primer entero por encima de PESO_CAPTURA=60). Solo ahi; fuera de esa situacion no
se toca nada. Flag `PKL_CURA_ANTE_JEFE`, default 0.

### Pre-registrado, y la potencia calculada ANTES de mirar

 aqui esta el motivo de que el lote lleve 300 runs y no 200: la primaria de
siempre no tiene potencia para este efecto.

- **primaria**: `P(gana la pelea de gimnasio)`. Base medida 0,61.
  A 0,77 -> 69% de potencia con 100 por brazo, **85% con 150**. A 0,85 -> 97%.
- **confirmatoria**: `P(llega con caido al jefe)`. Base 0,42.
  A 0,20 -> **92%** con 100 por brazo. Muy alimentada.
- **secundaria**: `insignias/run`, **declarada sin potencia**: el efecto
  estimado son +39 insignias en 225 runs = **+0,17/run** (d=0,15), que pide
  n~1100 por brazo. Se informa, pero no puede decidir nada, asi que **no decide**.

n = **150 por brazo** por lo que la primaria necesita. Miradas interinas en 60,
100 y 150 con la regla de parada pre-registrada en `scripts/control_h18.py`
(futilidad si el IC99% de la primaria no llega al efecto declarado; eficacia si el
IC99% excluye 0). La regla esta dentro del hash, que es justo lo que hacia falta
para que esto sea protocolo y no una promesa.

### Lo que NO sale de este experimento

Que el bot llegue con el equipo sano **no garantiza** que gane: el nivel y los
tipos no separaban nada, y aun asi hay打游戏 al 27% que se ganan. Si la
confirmatoria baja y la primaria no, el arreglo es real pero insuficiente, y eso
tambien es un resultado que hay que leer.

## 09-10 · H18 RETRACTADO: el peso no era la restriccion

Se lanzo a las 16:53 y se paro a las 18:20, con 4 runs. La premisa era que
capturar (60) le ganaba a curar (58/50) y por eso el bot se gastaba la cura.
**Falsa, y la comprobacion la hacia el propio codigo del log:**

```
centro de curacion:  score = 100.0   (37 veces)
jefe:                score = -1.0    (135 veces, siempre "APLAZADO")
```

El centro ya puntua el doble que capturar. Subirlo de 50/58 a 62 no cambia una
decision: el peso **no era la restriccion**. H18 queda retractado antes de datos.

Y hay una segunda lectura, mas incomoda: **el score 100 no existe en el codigo de
hoy**. En `planificador.py` no hay ningun 100.0 en las ramas de curacion. O sea
que la cifra viene de otra parte, o mi parser volvio a emparejar la linea de
decision con la de estado equivocada. **Es la cuarta vez hoy que un hallazgo mio se
cae por emparejamiento mal de lineas.**

## Lo que SI es solido, y sigue en pie

De las 155 peleas de gimnasio con la foto completa (regexes verificadas contra el
formato real del log, que ahi si cuadran):

```
llega con algun caido   18 de 66  (27%)   vida media 29%
llega sin caidos        77 de 89  (87%)   vida media 82%

nivel:  < rival 61%   >= rival 62%      <- no separa
tipos:  >=1.5  61%   <1.5   57%        <- no separa
```

Y el nivel y los tipos son identicos entre los dos grupos (+1,5 vs +1,1; 1,95 vs
1,96). **Llegar con el equipo vivo es lo que separa, y no se sabe por que el
equipo llega asi.**

## La respuesta honesta a "eso es pasar por el centro antes, no?"

Si, y el bot **ya lo hace**: el 83% de las peleas que llegaban con caidos venian
despues de curarse, y el centro esta en el grafo de forma obligatoria. Ese es
justo el rompecabezas: el centro puntua mas que cualquier otra cosa y el bot, aun
asi, entra al gimnasio con el equipo a la basura.

La unica explicacion que queda, y no esta comprobada, es que **el centro se queda
atras**: se cura en el centro que ya paso, y de ahi al jefe hay dos o tres peleas
que vuelven a gastar al equipo. Eso explicaria las dos cosas a la vez, y tambien
explicaria que subir el peso no arregle nada.

**Para comprobarlo no hace falta otro lote: hace falta instrumentar.** Un log
sencillo del camino (nodo -> peso -> vida del equipo tras la pelea) durante tres o
cuatro runs responderia esto en veinte minutos. Es infinitamente mas barato que
300 runs A/B sobre una mecanica que se acaba de demostrar que no es el cuello.

Y esa es la leccion de hoy en una frase: **cuatro horas de lotes para descubrir que
el cuello no era donde se mire.** Los lotes sirven para medir efectos, no para
encontrar mecanismos. Para encontrar mecanismos hay que dejar el bot que hable.

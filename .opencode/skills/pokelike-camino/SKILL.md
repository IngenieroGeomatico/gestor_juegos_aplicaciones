---
name: pokelike-camino
description: Úsala al cambiar el camino de juego del bot de Pokelike (qué nodo elige en cada pantalla, cuándo cura, cuándo pelea, cuándo captura y a quién sustituye) o al diagnosticar por qué una run pierde. Contiene las 8 reglas de juego del usuario y el mapa de pesos del planificador.
---

# Camino de juego del bot de Pokelike

Las 8 reglas de este documento son **norma de juego**, no sugerencias: vienen
del usuario y mandan sobre cualquier intuición del código. La sección
`CAMINO-POR-PANTALLA.md` de esta misma skill tiene el detalle por pantalla, los
pesos exactos y los selectores.

## Reglas

### 1. La run nunca se corta sola

Solo termina por **perder** (`GAME_OVER`) o por **completar la región**
(`CHAMPION`). Ninguna decisión de juego, ninguna espera y ningún presupuesto de
pasos cortan una partida.

- **Atasco**: no se rinde. La recuperación escala: teclas → recargar la página →
  (último escalón) aceptar que el juego no responde. Antes declaraba `ATASCADO`
  tras dos intentos y tiraba la partida.
- **Única excepción: `ERROR_DE_CODIGO`**. Si el bot lanza un `NameError`,
  `TypeError` o similar, **el bot está roto, no la partida**. Reintentar daría
  un proceso colgado sin resultado ni victoria ni derrota, que es peor que
  cortar. La regla es: **corta y se arregla**, y el corte tiene que dejar el
  error **localizado** — tipo, mensaje, `archivo:línea`, región, paso y traza
  completa — porque arreglarlo es trabajo de quien lee, no del bot.

  El volcado va a `log/crash-<fecha>.txt`, que `lanzar_tanda.py` **no** borra
  (a diferencia de los logs, de los que solo conserva 3). Por eso el error
  sobrevive a las runs siguientes.

  Cuando salga ese resultado, el orden es: leer `crash-*.txt` → `grep` del
  `archivo:línea` que indica → corregir → probar con una partida corta. Nunca
  reintentar.

`--max-pasos` con un número positivo **sí** corta, pero es una decisión
explícita de quien lo lanza, no un corte automático.

### 2. Al inicio de cada pantalla, capturar un Pokémon

Cada pantalla (nodo del mapa) ofrece **una** captura antes de nada. Si ya hay 6
en el equipo, se captura solo si el món **completa el equipo** o tiene **mejores
atributos** que alguno de los actuales — nunca para sustituir por sustitución.

Con el equipo lleno, la comparación es contra el **peor** miembro: nivel +3 o
stats ×1,15.

### 3. Reordenar antes de cada combate, por efectividad

El delantero va primero **por efectividad**, no por nivel: el que pega ×2 al
rival y no recibe ×2. Se leen las dos mitades de la tabla por separado.

Un món con **menos del 50% de vida** va **al final del orden**, no fuera del
equipo: así sigue ganando experiencia. El corte es por **porcentaje**
(`ps / ps_max`), nunca por PS crudos.

### 4. Las MT van al Pokémon principal

Si el principal ya no puede llevar más, al **siguiente de más nivel**.

### 6. Cada objeto al Pokémon que le viene bien

Un objeto que mejora ataques de Planta, a un món tipo Planta. La asignación se
hace con `pkl_items.puntuar_objeto`, que recibe los **tipos del món**.

### 7. Cambio por subida de nivel → el peor o el muerto

Cuando un món sube de nivel y hay que decidir a quién sacar, sale el **muerto**
primero (no aporta nada y ocupa plaza) y, si no hay caídos, el **peor por nivel
y estadísticas**.

Ojo: la pantalla `swap-screen` llega por **dos** motivos —captura con equipo
lleno, y subida de nivel— y solo el primero traía objetivo calculado. Sin
objetivo, el código elegía la primera opción de la lista, o sea un món
arbitrario.

### 8. Priorizar los combates de entrenador para ganar nivel

El entrenador es la **única fuente de exp que sube a todo el equipo**: es
prioridad sobre cazar salvajes.

Su rival es la regla 9: si hay cura a mano y el equipo está mal, curar primero.
La regla 9 manda, porque el pokecenter es **obligatorio**. Los dos casos juntos
—entrenador con caídos y **sin** cura accesible— no son un conflicto: es la
única jugada disponible.

### 9. Pokecenter obligatorio

Se pasa por él **siempre** que haya **caídos**, o el equipo esté **≤ 75%**, o el
**carry esté < 50%**.

El carry se mira aparte y a propósito: un solo món al 13% se va a morir aunque
la media del equipo pase del 75%, y perder un món es peor que perder un paso.

Si no hay pokecenter accesible, el corte **no** se aplica: sin cura delante,
quedarse sin opciones es peor que pelear con lo que haya.

## El error que más se repite

Comparar un identificador contra el **vocabulario equivocado**. Son tres, y
ninguno coincide con los otros dos:

| Nivel | Valores |
|---|---|
| Id de pantalla | `map-screen`, `battle-screen`, `catch-screen`, `swap-screen`, `trade-screen`, `item-screen`, `badge-screen`, `elite-prep-screen`, `passive-screen`, `stat-buff-screen`, `shiny-screen` |
| Tipo de nodo del juego (**inglés**) | `wild`, `trainer`, `boss`, `pokecenter`, `move_tutor`, `item` |
| Tipo de decisión (interno, traducido) | `batalla`, `entrenador`, `jefe`, `cura`, `tutor`, `item`, `trade`, `capturar`, `incognita` |

`politica.tipo_de_estado` traduce `pokecenter → cura`. El código que gestiona
una curación debe mirar `d.tipo == "cura"` y **nunca** `("centro",
"pokecenter")`: esa comparación no se cumple nunca, la rama queda muerta y no
sale ningún error. **Ha pasado nueve veces** en este bot.

## Antes de cambiar un peso

Los pesos del planificador están en `planificador.py` (`PESO_*`) y
`UMBRAL_PUERTA_JEFE`. Cambiarlos puede **invertir** una decisión sin que nada
falle: no hay excepción, no hay test que falle, simplemente el bot juega peor.

Hay un test que falla si esta skill y el código dejan de coincidir:
`test_la_skill_del_camino_no_se_desincroniza`. Si cambias un peso, actualiza
también la tabla de `CAMINO-POR-PANTALLA.md`.
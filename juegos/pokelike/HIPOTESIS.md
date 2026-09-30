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
| R1 | ¿El PS está normalizado por nivel? | **NO** | `PS = floor(2·baseHP·nivel/100) + nivel + 10`, sacada de `calcHp()` en el bundle del juego. Verificada con Nidoran-m Lv2=13, Bulbasaur Lv5=19, Clefairy Lv4=19. |
| R2 | ¿La experiencia es del delantero o del equipo? | **Del equipo** | Guía: +2 niveles todos contra entrenador, +1 contra salvaje. |
| R3 | ¿Qué tipos emite el mapa? | `start, catch, battle, trainer, item, question, trade, pokecenter, move_tutor, boss` | Traducidos y con test de que los 10 mapean bien. |
| R4 | ¿Con qué frecuencia sale un trade? | Peso 5 frente a 30 de entrenador | Tablas de pesos del bundle. |
| R5 | ¿Por qué fallaban los clics de objeto? | Eran **sintéticos** | El juego no atiende `el.click()` de JS; hace falta `locator.click()`. |
| R6 | ¿Por qué se colgaba el prep? | Modal de equipar que no escucha Escape | Hay que cerrar con `#btn-equip-cancel` y con clic real. |

## Hipótesis abiertas

### H1 · El nivel es el cuello, y se mide en la entrada al gimnasio
- **Medida**: para cada derrota contra gimnasio, el nivel del equipo en el paso
  anterior frente al rival (`niveles rivales` del log).
- **Si sale X**: la diferencia media es **≥3 niveles** → confirmada. Es el
  cuello, y todo lo demás es secundario.
- **Si sale Y**: la diferencia media es **<2** → rechazada. Entonces se pierde
  por **tipo o por composicion del equipo**, no por nivel, y toca rehacer la cobertura.

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

## Cobertura actual de los datos

Para responder a estas hipótesis hacen falta **unas 100 partidas**. Con 2 en
paralelo y ~12 minutos por tanda, son unas 50 tandas (~10 horas). Es volumen
bruto a propósito: la varianza del mapa manda más que la política, así que
cuantas más partidas, antes se separa "esto funciona" de "esto es ruido".

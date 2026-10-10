# Hipótesis: qué se sabe del bot y qué falta por aprender

Este es el documento **vivo**. Se abre para decidir qué hacer a continuación.
El detalle histórico de cada lote está en [`CUADERNO.md`](CUADERNO.md).

Cada línea es una hipótesis **falsable** con la medida que la confirma o la
tumba. Nada aquí es una opinión: o hay un número detrás o no entra.

---

## 1. Lo que está medido del bot

Todo lo de esta sección sale de las ~1.900 runs de `log/h1[5-9]/`. Los guiones
que lo reproducen están en `scripts/medir/` y **solo miran logs**: no lanzan
nada y se pueden ejecutar mientras corre un lote.

| Pregunta | Respuesta | Cómo se mide |
|---|---|---|
| ¿Cuánto gana el bot? | **1,14 insignias/run** de 8 posibles | `perfil_winner.py` |
| ¿Cuándo muere? | salvajes **34,6%**, gimnasios **33,9%**, resto 31% | `perfil_winner.py` |
| ¿Qué separa ganar de perder? | **la vida del equipo**, no el nivel | `derrota_por_derrota.py` |
| ¿Se puede cerrar el déficit de nivel? | **No. No hay exp a esa altura.** | `hay_exp_que_sirva.py` |
| ¿El bot se come la vida al entrar al jefe? | **No es una decisión: es distancia** | `entrar_roto.py` |

### 1.1 La vida es el único separador que existe

934 peleas con foto completa de PS reales (`derrota_por_derrota.py`):

| Vida con la que entra | n | Gana |
|---|---|---|
| 0–50% | 132 | **25,0%** |
| 50–75% | 122 | **88,5%** |
| 75–95% | 340 | **92,1%** |
| 95–100% | 340 | **99,7%** |

Y el corte está entre "con algún caído" (45,9%) y "sin caídos" (95,9%).

El nivel, al lado, **casi no separa**:

| | n | Gana |
|---|---|---|
| nuestro máximo por debajo del rival | 151 | 56,3% |
| nuestro máximo al nivel o más | 783 | 90,4% |

**Conclusión operativa**: entrar por debajo de nivel se acepta; entrar **gastado**
no. Ese es el cuello, y es el único sitio donde hay algo que hacer.

### 1.2 El déficit de nivel no lo cierra ninguna política de pesos

1.830 pantallas por debajo del listón (`hay_exp_que_sirva.py`):

| Gimnasio | n | Déficit del equipo | Rival más fuerte − listón |
|---|---|---|---|
| Brock | 1.117 | **+6,5** | **−10,8** |
| Misty | 698 | **+4,6** | **−8,1** |
| Koga | 49 | +0,7 | −10,6 |
| Lt. Surge | — | — | −8,1 |

El rival que el juego ofrece está **8 a 11 niveles por debajo del listón**, y
solo el **2%** de las veces está siquiera por encima del propio equipo.

> El nivel no se recupera jugando. La partida se decide en **si el equipo llega
> entero al gimnasio**, y el listón de nivel es un número que ya no se puede
> mover desde dentro del mapa.

### 1.3 El equipo llega roto por distancia, no por mal criterio

`entrar_roto.py` empareja cada pelea con la pantalla que la decidió:

```
peladas empezadas con el equipo roto   : 178
  ...con un pokecenter en pantalla     :   0     (0,0%)
  ...sin pokecenter en pantalla        : 178     (100%)
pantallas con cura a la vista → fue a curar : 493 de 493
```

El bot **cura siempre que puede**. Lo que hace mal es lo que viene después:
entre el pokecenter y el gimnasio hay uno a doce nodos de pelea obligatoria, y
no hay vuelta atrás. Y el bono de ruta (`combates_por_delante × 3.5 +
entrenadores × 4`) es **incondicional**: premia la rama larga aunque el equipo
no pueda pagarla.

Eso es exactamente lo que ataca **H20**.

### 1.4 Lo que el bot hace bien y no hay que tocar

- **473 pantallas con cura disponible → fue a curar las 473.** El corte de
  emergencia (`caidos or ratio ≤ 75% or carry < 50%`) funciona.
- El **trade** funciona: 1.499 trades aceptados, +3 niveles y PS completos.
  Es el único nodo del juego que salta el muro de nivel.
- La curated **captura permisiva** (H15) está confirmada con n=150.
- La regla de la Apertura (starter que gana a Brock y a Misty) es correcta.

### 1.5 Alcance de cada mecanismo (la puerta antes de lanzar)

`alcance_mecanismo.py` sobre 342 runs. **Por debajo del 15% no se lanza**: no hay
potencia y se pierden las horas.

| Mecanismo | Runs | % | |
|---|---|---|---|
| captura por equipo corto | 336 | 98,2% | lanzable |
| búsqueda de trade (tecla R) | 337 | 98,5% | lanzable |
| reroll por jefe sin exp | 276 | 80,7% | lanzable |
| cura en camino al jefe | 190 | 55,6% | lanzable |
| objeto (`PKL_ITEM_HUECOS`) | 173 | 50,6% | lanzable |
| captura por nivel (H17) | 118 | 34,5% | lanzable |
| entrenador de riesgo | 109 | 31,9% | lanzable |
| **veto de entrenador por nivel** | 24 | **7,0%** | **NO SE LANZA** |
| **H19 (no gastar reroll en balde)** | 4 | **1,2%** | **NO SE LANZA** |

> H17 y H18 se gastaron horas en mecanismo del 8% y del 1%. Este cuadro sale
> en **minutos** sobre logs que ya existen.

---

## 2. Controles ya resueltos

| # | Cuestión | Respuesta |
|---|---|---|
| **V1** | ¿Veto de entrenador por tipo? | **NO, contraproducente. Apagado.** 111 runs: 0,64 insignias con veto / 1,62 sin él (p=0,020) |
| **V2** | ¿Arma de captura permisiva (H15)? | **SÍ, confirmada.** n=150 por brazo, efecto real |
| **V3** | ¿`insignias/run` como primaria? | **Sí**, y solo ella: es la única con potencia declarada |
| R1 | ¿El PS está normalizado por nivel? | **No**: `PS = floor(2·baseHP·nivel/100) + nivel + 10` |
| R2 | ¿La experiencia es del delantero o del equipo? | **Del equipo**: +2 por entrenador, +1 por salvaje |
| R3 | ¿Qué tipos emite el mapa? | `start, catch, battle, trainer, item, question, trade, pokecenter, move_tutor, boss` |
| R4 | ¿Con qué frecuencia sale un trade? | Peso 5 frente a 30 de entrenador en las tablas del juego |
| R5 | ¿Por qué fallaban los clics de objeto? | Eran **sintéticos**: el juego no atiende `el.click()` de JS |
| R6 | ¿Por qué se colgaba el prep? | Modal que no escucha Escape: cerrar con `#btn-equip-cancel` |

---

## 3. Hipótesis cerradas

Se conservan con su veredicto porque **saber que algo no funciona es un
resultado**, y volver a intentarlo cuesta un lote entero.

| # | Hipótesis | Veredicto | Por qué |
|---|---|---|---|
| H1 | El nivel es el cuello | **Rechazada** | §1.2: no hay exp a la altura del listón |
| H1b | Bajar el listón sube las insignias | **Rechazada** | Consecuencia directa de H1 |
| H1c | La varianza del mapa manda más que la política | **Abandonada** | absorbeda por la medida de potencia |
| H2 | Llegar por debajo no compensa | **Rechazada** | Se gana el 56% por debajo; el listón no es el problema |
| H3 | Curar antes del jefe es lo que decide | **Rechazada como tal** | El bot ya cura; el problema es la distancia (§1.3) |
| H4 | Un solo món en pie es la causa | **Rechazada** | El corte de emergencia lo cubre y nunca dispara |
| H5 | Los objetos de tipo cambian los gimnasios | **Sin efecto medido** | La rama está apagada: el objeto puntúa 2,0 |
| H6 | El trade es el atajo de nivel | **Era un bug de DOM** | Arreglado: 1.499 trades, el más rentable del juego |
| H7 | El Lucky Egg compensa | **Abierta, sin medir** | `pkl_items` lo prioriza; nunca se ha comparado |
| H10 | Ninguna penalización de `puntuar` funcionaba | **Cerrada** | El bono de ruta las tapaba; ahora se suman al final |
| H12 | ¿El nodo de captura ofrece pokéball? | **Cerrada** | Sí, y el filtro permisivo lo toma |
| H13 | El nodo de objeto sube las insignias | **Sin efecto** | `PESO_OBJETO` sin flag nunca se ha encendido |
| H16 | "Llegar a Misty con nivel 20 y 5 móns" | **Retractada** | El umbral era a posteriori; H15 lo объясaba |
| H17 | Capturar cuando falta nivel | **Refutada** | n=114/110, IC excluye el efecto declarado |
| H18 | Capear los aplazos / curar por encima de capturar / relajar el veto | **Las tres no-op** | La restricción nunca fue el peso: §1.3 |
| H19 | Gastar el reroll solo con el equipo roto | **Retractada antes de datos** | Su marcador sale en el 1,2% de las runs |

> **H19 es el ejemplo que manda**: la hipótesis sonaba razonable, el flag se
> implementó, y la medición previa de alcance la mató en minutos. Por eso el
> paso 1 de cualquier lote nuevo es `alcance_mecanismo.py`.

---

## 4. Hipótesis abierta

### H20 · Con el equipo roto, la rama que gasta menos debe ganar

**RETRACTADA a los 26 runs.** No es una hipótesis refutada: es una hipótesis
**al revés de lo que hacía falta**, y su prevision se cumplió.

La premisa era que el bono de ruta (incondicional) metía al bot en ramas que
gastaban la vida del equipo antes del jefe. Lo que pasó es que la regla se
cumplió **literalmente** y por eso quedó mal:

| | A (H20) | B (control) |
|---|---|---|
| pasos por run | **10** | 21 |
| paso al morir (mediana) | **29** | 52 |
| nivel máximo | **11,8** | 18,7 |
| muere sin 1ª insignia | **62%** | 31% |
| trainers elegidos | **1,7/run** | 5,2/run |
| insignias/run | 0,46 | 1,23 (p=0,070) |

El bot **recorría el mapa al doble de velocidad**, llegaba antes a los jefes y
moría antes. Y el motivo está medido: **una pelea contra un entrenador da
+2,00 niveles y contra un salvaje +1,00** (154 peleas ganadas, medianas).
H20 restaba `combates_por_delante` a los dos **por igual**, o sea que le decía
al bot «descarta también los entrenadores» — que son el doble de exp. Y §1.2
ya dice que la exp **no se recupera**: el rival está 8-11 niveles por debajo
del listón, siempre.

> **Lo que H20 sí acertó, y se conserva**: la cura por delante **nunca** se
> resta. Ese era el bug de las 8 primeras runs (§H20-a) y el arreglo se queda.

### H21 · Con el equipo roto, dejar de premiar al salvaje

**RETRACTADA antes de mirar el resultado: mecanismo inerte.** No es una
hipótesis refutada, es una intervención que **no puede cambiar nada** en el
escenario que pretendía atacar.

Se paró a las 2 runs. El marcador del flag salía (73 pantallas), pero el
marcador dice **cuántos salvajes hay por delante**, y en el 89% eran cero:
la rama iba a un entrenador, no a un salvaje. Con el equipo roto la pantalla
es:

| tipo de nodo | % |
|---|---|
| **entrenador** | **41,4%** |
| **cura** | **41,4%** |
| batalla (salvaje) | 7,1% |
| item | 5,7% |
| tutor | 4,3% |

**Alcance real**: gate `roto` (36,9%) × ramas con salvajes (11%) = **4,1%**.
Muy por debajo del 15% de §1.5, en la misma franja que H18 (8%), el veto por
nivel (7%) y H19 (1,2%) — los tres que gastaron horas para nada.

**Lo que sí queda de H21**, y se conserva:
- `salvajes_por_delante` en `politica.py`, que faltaba y separa lo que
  `combates_por_delante` mezclaba.
- El arreglo del bug de la cura: **la cura por delante nunca se resta**.

**Por qué se falló**, que es la parte que importa: monté la intervención
sobre una medición correcta pero mal preguntada. Es cierto que el
entrenador da **+2,00 niveles** y el salvaje **+1,00** (154 peleas
ganadas). Pero la tasa de trainers de H20 (1,7/run vs 5,2) era un síntoma
de otra cosa: el bot **corría más rápido**, no es que evitasse la exp. La
exp no era el cuello.

> **La medición que de verdad separa, con n=155 peleas y foto de PS reales**
> (`log/h17`, parser por bloques). En cubos de 10 puntos, que es como hay que
> mirarla — agrupada en tres tramos, la curva parecía plana por encima del
> 75% y no lo era:
>
> | vida de entrada | n | gana |
> |---|---|---|
> | 0–9% | 31 | **0,0%** |
> | 20–29% | 4 | 0,0% |
> | 30–39% | 4 | 50,0% |
> | 40–49% | 7 | 71,4% |
> | 50–59% | 10 | 70,0% |
> | 60–69% | 14 | **92,9%** |
> | 70–79% | 29 | 75,9% |
> | 80–89% | 21 | 76,2% |
> | 90–99% | 34 | **88,2%** |
>
> Es monótona y el cuello sigue siendo la vida (§1.1 confirmado con dato
> fresco), pero **el salto grande está en 60-69%**, no en 75%. Con 0-9% el
> bot gana **ninguna** de 31.

**Y la vía de la cura está cerrada**: con trainer **y** cura en pantalla y el
equipo roto, el bot eligió cura **26 de 26 veces (100%)**. No hay decisión
que arreglar ahí; §1.4 decía que cura bien y es cierto.

### H23 · Qué hace el bot ENTRE una cura y el gimnasio

**Abierta el 10-10, y es la que toca. Instrumentar, no lanzar.**

Tres mediciones cierran las vías que quedan, y por eso no hay hipótesis de
política que lanzar ahora mismo:

| vía | medición | veredicto |
|---|---|---|
| elegir la cura | 26 de 26 con trainer+cura a la vista y el equipo roto | **cerrada**: acierta el 100% |
| castigar la exp (H21) | 4,1% de alcance, 89% inerte | **cerrada**: no puede fires |
| subir el nivel (H1) | el rival está 8-11 por debajo del listón (§1.2) | **cerrada**: no hay exp |

Queda una, y es la de §1.3: **no es una decisión, es la distancia**. Entre
el pokecentro y el gimnasio hay nodos de pelea obligatoria y no hay vuelta
atrás. El bot cura bien y aun así llega gastado.

**Lo que falta es el dato, y sale instrumentando** (§5.10: los lotes miden
efectos, no encuentran mecanismos). Una línea por paso que ya existe
(`TRAZA_CAMINO`) tiene todo lo necesario y **no se está usando**: falta
emparejarla con la pelea de gimnasio, que es donde se rompe.

La pregunta, en una frase: **entre la última cura y la pelea de gimnasio,
¿cuántos pasos hay y qué tipo de nodo se elige en cada uno?**

Instrumentación que hace falta (nueve líneas, una por paso, sin lote):
- `d_gym = paso_ultima_cura -> paso_gimnasio` y el tipo de nodo de cada paso
  intermedio
- vida del equipo **antes y después** de cada nodo intermedio
- si el pokecentro estaba en la rama pero se pasó de largo

Con eso se responde en **veinte minutos** sobre las 26 runs que ya existen,
sin lanzar nada.

### H22 · El trade es el único atajo de nivel (abierta, sin tocar): ¿y si se busca más?

**Abierta, sin intervención todavía.** Es la pregunta con más rendimiento
esperado y la menos medida.

- El trade da **+3 niveles y PS completos** en un nodo (§2, R2, H6).
- Solo el **50%** de las runs consigue uno: 126 de 252, con 0,73 de media.
- El bot **ya rerollea** para buscarlo (98,5% de las runs disparan el
  marcador) y casi nunca lo encuentra.

El cálculo sale en minutos sobre `log/`:

```bash
grep -c "trade aceptado" log/h1[5-9]/*.txt
```

Antes de tocar nada, hay que responder **una** pregunta: ¿de las 124 runs sin
trade, cuántas Offerían el nodo y el bot no lo eligió, frente a cuántas
simplemente no salió? Si es lo segundo, no es un problema de política y no hay
nada que arreglar.

---

## 5. Reglas de método

Estas son las únicas reglas que se aplican a cualquier lote. Cada una se pagan
con horas o con un lote entero.

1. **El bot se congela mientras corre un lote.** Editar a mitad dejó 56 de 111
   runs con código distinto y hubo que tirar la mitad de la muestra. El
   launcher **aborta** si el hash del código no es el mismo.

2. **Antes de lanzar un A/B, mide en cuántas runs dispara el mecanismo**
   (`alcance_mecanismo.py`). **Por debajo del 15% no se lanza.** H17 (34% pero
   mal aplicado), H18 (8%) y H19 (1,2%) se gastaron en esto.

3. **La primaria se declara antes de mirar, y tiene que tener potencia.**
   `insignias/run` es la única que la tiene con n razonable. "Llega al primer
   gimnasio" con 35 entradas no llega a p<0,05 ni con 150 por brazo.

4. **Los brazos van intercalados, no por bloques.** Por bloques, el brazo C
   terminó 2 h 14 min después y "C es mejor" podía ser solo "C corrió más
   tarde".

5. **Un guard es tan fuerte como la fuente que lee.** Siete fallos seguidos
   —casi todos de él— foram siempre el mismo error: el guard acertaba sobre el
   mundo y se equivocaba sobre el fichero.

6. **El lote vive en su propia unidad de systemd**, no en el cgroup del editor.
   `setsid` crea sesión pero **no cambia el cgroup**: cuatro lotes murieron
   porque `oomd` mataba a VS Code y se llevaba el lote por delante.

7. **Un marcador que no se puede ver desde fuera no verifica nada.** El "no lo
   hago" va **fuera** del `if` que lo salta, y el peso va **dentro** del
   motivo: si el brazo A y el B imprimen la misma línea, no hay medida.
   **Y al revés**: un marcador con una cifra **imposible** delata un bug más
   rápido que cualquier test. El de H20 salió por aquí (`extra` valía 105
   "combates" con un tope de 8), no leyendo el código.


8. **Antes de declarar un bug, comprobar que el criterio del código es el que
   se cree, y que la medida propia mide lo mismo que él.** Tres hallazgos
   seguidos cayeron por esto, y en los tres el código estaba bien.

   **Y al escribir un guard: que mire la estructura, no la cifra.** El guard
   que detecta el código viejo se puso como "más de 40 es imposible" y abortó
   contra el código **bueno**, porque el coste es `peleas (tope 8) + 4 ×
   entrenadores` y los entrenadores no llevan tope: hay una rama legítima de
   52. Un guard que topa por un supuesto equivocado es peor que no tener
   guard, porque además de no avisar **tira el trabajo que sí vale**.

9. **Cuando tres hallazgos seguidos se caen por el mismo motivo, el problema
   deja de ser el hallazgo y pasa a ser el método.**

10. **Los lotes miden efectos; no encuentran mecanismos.** Cuatro horas de
    lote para descubrir que el cuello no era donde se miraba. Para encontrar un
    mecanismo, instrumentar: nueve líneas por run y veinte minutos.

11. **Un test que monta el caso fácil tapa el bug difícil.** Los tests de H20
    ponían el pokecentro como nodo **clicable**, donde el corte de emergencia
    cortocircuita la lógica nueva. El caso que de verdad ocurre es el
    pokecenter **por delante de una rama**, no en pantalla. Un test que pasa no
    es un test que cubre: pregunta *qué caso del mundo* monta, no *qué línea
    ejecuta*. Y antes de fiarse de una suite entera, comprobar **qué caso
    monta**: 336 comprobaciones en verde y un bug de 42 puntos en producción.

---

## 6. Cómo lanzar un lote

```bash
# 1. Alcance: ¿el mecanismo dispara lo suficiente?
uv run --group dev python juegos/pokelike/scripts/medir/alcance_mecanismo.py

# 2. Integridad: ¿el bot sigue vivo después del refactor?
uv run --group dev python juegos/pokelike/scripts/test_integridad.py

# 3. Unidade propia, con techo de memoria (nunca en el cgroup del editor)
systemd-run --user --unit=pokelike-<lote> --collect \
  --property=MemoryHigh=1500M --property=MemoryMax=2000M \
  --property=MemorySwapMax=1G \
  bash $RAIZ/juegos/pokelike/scripts/supervisor_lote.sh \
       log/<lote> 45 bash $RAIZ/juegos/pokelike/scripts/exp_<lote>.sh 300 Kanto 1800
```

**Antes de nada: matar el lote anterior.** Si ya hay un Firefox vivo, las
instancias nuevas se enganchan a su proceso y el bot juega a medias:

```bash
pkill -9 -f "scripts/jugar_pokelike.py"; pkill -9 -x firefox; pkill -9 -f firefox-bin
```

**Nunca con `pkill -f jugar_pokelike.py`**: el patrón está en la línea de órdenes
del propio shell y se mata a sí mismo.

Máquina: 7 GB y 4 núcleos. **Un run en paralelo**, nunca dos: con dos, el lote
vive en el margen de memoria justo donde `oomd` empieza a matar.

La cuenta de verdad es `ls log/<lote>/*.txt | wc -l`, **no** lo que el launcher
diga. Las tres primeras veces el launcher anunció una cuenta que no era la
real; la cuarta no lo detectó nadie porque no había quien mirara.

### Los ficheros que entran en el hash

El hash del lote se calcula sobre `scripts/*.py` y `scripts/*.sh`, **y el glob no
es recursivo**. Por eso el código de las hipótesis cerradas está en
`scripts/archivo/`: fuera del hash, sin poder invalidar un lote en curso, y sin
borrar el guion con el que se lanzó cada tanda. El `README.md` de `archivo/`
dice qué es cada cosa y por qué ya no se usa.
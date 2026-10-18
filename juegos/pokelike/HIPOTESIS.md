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

### 1.1-bis El cuello NO es la vida media: es tener un món a 0

**§1.1 estaba mal, y el error era de agregación.** Decía "la vida del equipo
es lo único que separa" con 934 peleas de `log/h17`. Con **1.229 peleas de
todo el corpus** y el PS real de **cada món**, no:

**Por la vida media del equipo** (lo que decía §1.1):

| media al entrar | n | gana |
|---|---|---|
| < 75% | 685 | 49,5% |
| ≥ 75% | 544 | **82,2%** |

**Por el món que abre, medido como mínimo:**

| mínimo por món | n | gana |
|---|---|---|
| 0–9% | 618 | 41,9% |
| 10–19% | 42 | 85,7% |
| 30–39% | 46 | 95,7% |
| 60–69% | 64 | 73,4% |
| 90–99% | 108 | 92,6% |

La curva del mínimo es **casi plana por encima del 10%** (83-92%) y solo se
hunde en el tramo 0-9%. Ese tramo tiene 618 peleas, la mitad de la muestra, y
casi todo dentro es "hay un món a 0".

**Por número de móns a 0**, que es lo que queda limpio:

| caídos al entrar | n | gana |
|---|---|---|
| **0** | 636 | **85,7%** |
| 1 | 257 | 65,4% |
| 2 | 115 | 39,1% |
| 3 | 95 | 21,1% |
| 4 | 70 | 10,0% |
| 5 | 30 | 3,3% |
| 6 | 26 | **0,0%** |

Sin caídos contra 1 caído: **+20,3 puntos**, se = 3,3, o sea **d = 6,2** con
636 contra 257. Es el separador más fuerte medido en este repo, y no es el que
se estaba mirando.

**Y el control que lo confirma**: dentro de cada número de caídos, la vida
media **no** explica nada, y sale incluso al revés:

| caídos | media <75% | media ≥75% | diferencia |
|---|---|---|---|
| 0 | 91,2% (n=137) | 84,2% (n=499) | **−7,1** |
| 1 | 68,8% (n=77) | 63,9% (n=180) | **−4,9** |
| 2 | 36,2% (n=58) | 42,1% (n=57) | +5,9 |

Con más vida media se gana **peor** en dos de los tres tramos. O sea que la
media del equipo es una **mala статистика de resumen**: diluye al món que
decide. Un equipo con cinco móns llenos y uno a 5/23 tiene media alta y es
una pelea perdida.

> **Lo que esto cambia**: `UMBRAL_PUERTA_JEFE` y `equipo_roto()` usan
> `ratio <= 0.75` **y** `caidos >= 1`, o sea que ya miran el caído. Pero
> `derrota_por_derrota.py` y todo lo escrito en §1.1 está en clave de
> **media**, y por esougen la conclusión de "la vida" cuando lo que separa es
> **el caído**. La próxima hipótesis que se abra tiene que ir contra el caído,
> no contra la media.

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

### 1.3 CORREGIDA · El tramo pokecentro→gimnasio no ofrece elección

Lo que decía esta sección (`entrar_roto.py`: 178 peleas empezadas con el equipo
roto, 0 con un pokecenter en pantalla, luego "es distancia") **estaba mal medido**,
y por dos motivos distintos que se han ido cayendo uno detrás de otro:

1. **No hay distancia que recorrer.** `tramo_al_jefe.py` mide el mapa de verdad:
   entre el último pokecentro y la pelea de gimnasio hay **1 pantalla**, y en
   **1096 de 1099 (99,7%)** esa pantalla ofrecía **un solo nodo: el jefe**. No
   hay rama larga, ni pelea obligatoria intermedia, ni nada que elegir. La frase
   "uno a doce nodos de pelea obligatoria" era falsa: la rama larga que el bono
   de ruta premia está **antes** del pokecentro, no después.
2. **El "equipo roto" se medía con la barra del HUD, que miente.** Ver §1.6. La
   traza saca `caidos` de `equipo()` (`#team-bar .hp-bar-fill`), y esa barra
   marca **100% a móns que están al 0**: leído el texto de `#player-side` en el
   mismo volcado, 11 de 76 móns discrepan y **las 11 veces en la misma
   dirección**. Encima, al perder, `nos quedan:` lista cinco móns al 100% en una
   derrota 13-1. Por tanto **todo `caidos` que salga de la traza es un suelo**,
   no una medida.

Medido así, el estado de **entrada** no es ni el 48,3% de `mios` ni el 12,4% de
la traza:

```
entrada con >=1 caído (traza, barra)   :  12,4%   (12 de 97)  <- suelo
entrada con >=1 caído (texto, mapa)    :  31%     ( 9 de 29)  <- sonda, 1 run
mios (combate)                         :  48,3%   <- techo: incluye bajas de la pelea
```

Con tres avisos honestos: las muestras son pequeñas y de lotes distintos (97
peleas de gimnasio de 5 lotes con traza, y **todas ganadas**, así que no sirven
para medir victoria); **el 48,3% de `76ee140` sigue en pie como predictor** —lo
que no se sostiene es el relato causal "llega roto al gimnasio"—; y `mios` sigue
sin estar caracterizado del todo, porque el propio bot anota en `ps_cierra`:
`nota=estado ya empezada: no es el PS de despues`.

Lo que **sí** queda demostrado y es lo que ataca H20 (§4): la puerta de curación
no se dispara cuando debería. En `log-2026-10-11_10-39-37_p14744.txt` el bot
entra a un gimnasio con **3 caídos** y elige `batalla` porque no hay cura a la
vista; cuando por fin aparece (`disponibles=['cura','entrenador']`) la toma y la
cura sana **3 caídos → 6/6 al 100% en un solo paso**.


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

### 1.6 La barra del HUD MIENTE, y es la fuente de toda la traza

#### El hallazgo

El bot tiene **dos** lecturas de vida:

| fuente | de dónde sale | quién la usa |
|---|---|---|
| **la barra** | `#team-bar .hp-bar-fill`, un **ancho en %** | `navegador.equipo()` → toda la política, y la traza (`vida`, `caidos`) |
| **el texto** | el texto de `#player-side` (`"0/35"`) | `mios`, `DEC ps_abre`, y el `lado` de la sonda |

`sonda_dom` (en `jugar_pokelike.py`, apagada por defecto, se abre con
`PKL_SONDA_DOM=<dir>`) lee **las dos a la vez** y guarda el HTML crudo. En 48
volcados de una run real, leídas en el mismo instante:

```
48 volcados: 29 en map-screen y 19 en battle-screen
mons leídos a la vez: 76
  discrepan: 11 (14%)  -> y las 11 SIEMPRE en la misma dirección:
                          la barra dice 100% y el texto dice otra cosa
```

Ejemplos, y son de las **dos** pantallas:

```
mapa  paso 54   Ivysaur   barra=100%   texto=0/49   (0%)
mapa  paso 76   Omanyte   barra=100%   texto=6/64   (9%)
mapa  paso 76   Staryu    barra=100%   texto=0/37   (0%)
pelea paso 78   Staryu    barra=100%   texto=0/37   (0%)
```

**La barra marca 100% a móns que están al 0.** No es que una lectura esté en
otro instante: están en el **mismo volcado**. Y hay una segunda prueba, fuera de
la sonda: al perder, el log escribe `nos quedan:` con la barra, y en una derrota
**13-1** lista los cinco móns **al 100%**.

Que la barra *a veces* sí diga 0 (hay 11 lecturas al 0% en los mismos volcados)
solo significa que el fallo es **intermitente**, que es la peor forma de fallar.

#### Consecuencia 1: la traza no sirve para medir cómo llega el equipo

`TRAZA_CAMINO` saca `vida` y `caidos` de `equipo()`, o sea **de la barra**. Si la
barra esconde un caído, la traza lo esconde también. Medido en los mismos
volcados, con el texto como referencia:

```
entrada con >=1 caído (traza, barra):   12,4%   <- lo que se venía usando
entrada con >=1 caído (texto, mapa):      31%   (9 de 29 volcados)
mios (combate, mezcla bajas de la pelea): 48,3%
```

Los tres números son de muestras distintas y pequeñas, pero van en el orden que
dice el mecanismo: **la traza es un suelo y `mios` un techo.** El §1.3 corregido
hay que leerlo con esto en la mano.

#### Consecuencia 2: el bot no sabe que va roto

La política decide con `equipo()`. Si `equipo()` le dice que todos están al 100%,
`equipo_roto()` no ve nada roto y la **puerta de curación no se dispara**. Esto
es una **hipótesis viva**, no un hecho —hay que medir cuántas decisiones
cambiarían si `equipo()` leyera el texto— pero es coherente con lo que se ve en
los logs: el bot entra a pelear con tres caídos y elige `batalla`.

Lo que **sí** queda claro del texto (`#player-side`), que es la lectura que sigue
a la realidad:

- **No está congelado**: 3 de 4740 pares de peleas consecutivas tienen el `mios`
  idéntico (0,1%).
- **Refleja la cura**: 0 de 961 pares con un pokecentro entre medias repiten
  `mios` (0,0%).
- En la pantalla de mapa trae **el equipo entero**, no solo al que peleó.

#### El arreglo: la traza ya lee el equipo corregido

Cambio en `f995ee3`: `_traza_camino` usa `equipo_con_tipos()` (el mismo equipo
que usa la política, con `_ps_real` y `_caidos_conocidos`) en vez de
`self.j.equipo()`. No toca el comportamiento del bot ni un byte —solo lo que
registra—, pero **todas las trazas anteriores al cambio están sesgadas**: el
`caidos` y la `vida_media` que hay en `corpus.db` hasta ese commit salen de la
barra mentirosa.

Validado en una run real de la sonda (`log-2026-10-11_11-48-28_p45614.txt`),
paso a paso contra el texto de la misma run:

```
paso  traza corregida                  texto (#player-side)         coincide
 16   Bulbasaur:28%  media=64          Bulbasaur 7/25               SI
 25   caidos=2 Clefairy:0% Paras:0%    Clefairy 0/19, Paras 0/20    SI
      media=12
 9 pasos comparados: 9 coinciden (100%)
```


#### La cura: 100% y revive (incluye heridos)

`log-2026-10-11_10-39-37_p14744.txt`, en un solo paso:

```
paso 22:  Bulbasaur:0%, Staryu:68%   → 1 caído, 1 herido
paso 27:  Bulbasaur:100%, Staryu:100% → ¡curó al herido!
```

**La cura es completa: revive caídos Y cura heridos.** El "36% → 36%" de
`curlena.py` era un artefacto del emparejamiento (traza[k] vs traza[k+1] con
peleas intermedias) y de usar la barra que miente.

#### H20: el pokecenter está lejos, no es "curar justo antes"

Medido sobre el corpus (3153 batallas de gimnasio):

| métrica | valor |
|---|---|
| gimnasios sin pokecenter en toda la run | 1127 (36%) |
| distancia del último pokecenter al gimnasio (mediana) | 16 nodos |
| gimnasios con pokecenter en los 5 nodos previos | 0% |

**El cuello no es "el bot no elige curar antes del gimnasio" — es que el
pokecenter está a ~16 nodos.** El bot tiene que gestionar la vida a lo largo de
todo ese tramo. No hay decisión "curar justo antes" porque no hay pokecenter
justo antes.

El 100% de "sin_pokecenter" en el script anterior era un artefacto: solo miraba
5 nodos antes. La realidad es que el pokecenter está a 10-20 nodos.

**Pregunta abierta:** ¿cuánto gasta el bot en esos 16 nodos? ¿Elige bien los
combates para minimizar el gasto? Eso requiere la traza nueva (corregida) que
solo está en 2 runs.

#### Veredicto: H20 es falso

Medido con la traza nueva (corregida, ground truth) en 5 runs con sonda:

| gimnasio | pokecenter → gym | vida_media post-cura | vida_media pre-gym | gasto |
|---|---|---|---|---|
| Brock (p90668) | 16 pasos | 100% | 100% | **0** |
| Misty (p90896) | 19 pasos | 100% | 100% | **0** |
| Brock (p103828) | 16 pasos | 100% | 100% | **0** |
| Misty (p104075) | 12 pasos | 100% | 100% | **0** |

**El bot llega al gimnasio al 100% de vida.** El "96.6% entrada rota" de
`h20_al_gimnasio.py` era un artefacto: usaba `mios`/`ps_abre` que se leen
"ya empezada" e incluyen el daño de la pelea del gimnasio misma.

La sonda en pantalla de mapa **no es fiable**: lee `#player-side` que puede
mostrar valores viejos de la última pelea. En p90896, la sonda muestra 2 caídos
en el paso 47, pero la traza (ground truth) muestra 0 caídos y 100%.

**Consecuencia:** el cuello del gimnasio no es la entrada rota. Es otra cosa
(quizá el nivel, la cobertura de tipos, o la gestión de la pelea misma).

#### El cuello real: caídos al abrir la pelea

Medido sobre el corpus (3153 batallas de gimnasio):

| gimnasio | victorias | diff_nivel | caidos_al_abrir |
|---|---|---|---|
| Blaine | 100% | +7.5 | **0.4** |
| Brock | 87% | -3.4 | **0.6** |
| Giovanni | 88% | +6.5 | **1.2** |
| Koga | 74% | +1.5 | **1.5** |
| Lt. Surge | 73% | +2.6 | **1.8** |
| Misty | 54% | -1.8 | **1.5** |
| Erika | 51% | +4.1 | **2.3** |
| Sabrina | 66% | +9.5 | **2.5** |

**El cuello no es el nivel — es cuántos móns caídos hay al abrir la pelea.**

Brock tiene el peor nivel (-3.4) pero 87% victorias (solo 0.6 caídos).
Sabrina tiene el mejor nivel (+9.5) pero 66% victorias (2.5 caídos).

**La pelea del gimnasio mata a 1-3 móns en los primeros turnos.** Eso es el
cuello. El bot llega sano al gimnasio, pero la pelea misma es difícil.

La cobertura de tipos no es medible con los datos disponibles (el pool del
corpus solo tiene 20 Pokémon).

#### El cuello real: Bulbasaur abre la pelea y es débil

En las derrotas contra Misty y Erika:

| quién abre la pelea | veces |
|---|---|
| **Bulbasaur (caído)** | **71** |
| Bulbasaur (sano) | 31 |
| Venonat (caído) | 27 |
| Ivysaur (caído) | 25 |

**Bulbasaur siempre abre la pelea** (es el primer món del equipo). En las
derrotas, Bulbasaur cae en los primeros turnos (71 veces).

Bulbasaur (Planta/Veneno) es débil contra:
- Misty (Agua): Planta es débil contra Agua (x2)
- Erika (Planta): Veneno es débil contra Planta (x2)

#### "Bulbasaur abre y es débil" queda REFUTADO por el chart del juego

El chart de Pokelike NO es el oficial Gen6. Medido fila a fila, Bulbasaur
(Planta/Veneno) contra los jefes de Kanto:

| Jefe | Multiplicadores | ¿Ventaja? |
|---|---|---|
| Brock (Roca) | Grass x2 | ✅ |
| Misty (Agua) | **Grass x2** | ✅ |
| Lt. Surge (Eléctrico) | x1 | ❌ |
| Erika (Planta) | **Poison x2** | ✅ |
| Koga (Veneno) | x0.5 | ❌ |
| Sabrina (Psíquico) | x1 | ❌ |
| Blaine (Fuego) | Grass x0.5 | ❌ |
| Giovanni (Tierra) | Grass x2 | ✅ |

Bulbasaur tiene ventaja **exactamente contra los dos cuellos medidos** (Misty,
Erika). La premisa "abre y es débil contra el líder" es falsa en tipos; el
cuello del gimnasio no es la ventaja de tipos del abridor.

#### La estrategia "solo pelear con ventaja": alcance real medido

El usuario propuso reservar a Bulbasaur cuando no tiene ventaja. Implementado
en `politica.py`: `_reservar_sin_ventaja()` (pone al final a los móns sin
ventaja de tipos contra el rival), integrado en `orden_para_entrenador` y con
test en `test_integridad.py` (387 correctas).

Medido sobre el corpus (derrotas de gimnasio con Bulbasaur en `mios`, caído
al abrir):

| métrica | valor |
|---|---|
| derrotas Gym con Bulbasaur | 199 |
| **caído al abrir** | **131** |
| de esas, contra Brock/Misty (Bulbasaur con ventaja x2) | **129** |
| contra líderes sin ventaja (Koga/Blaine…) | 2 |

**La reserva por ventaja no habría salvado 129 de las 131 caídas**: Bulbasaur
cae *teniendo* ventaja de tipos. Dos lecturas posibles, ambas medibles:

- *H-a*: el abridor sufre el primer golpe aunque tenga ventaja ofensiva → la
  cura no es el orden, es quién aguanta el 2x de vuelta (ver §1.6 "caídos al
  abrir" por gimnasio y nivel).
- *H-b*: el cuello real es el nivel/aguante del equipo al llegar, no el abridor.

### 1.7 El cuello del gimnasio, medido sobre 513 peleas de Kanto

Las tres mediciones juntas cierran el diagnóstico:

**(1) El equipo llega entero casi siempre.** De las 513 peleas de gimnasio con
Bulbasaur en el equipo, en **442 (86,2%) el equipo estaba entero en pie** al
elegir el nodo. De esas, gana el 67,0%. El bot no llega al gimnasio roto: el
cuello **no** es llegar gastado.

**(2) Cuando Bulbasaur cae, cae sin motivo de tipos.** En 80 de esas 442
(18,1%), Bulbasaur cae al abrir **a pesar de que el equipo entero estaba en
pie** y de tener ventaja x2 contra el líder.

**(3) La ventaja de tipos del abridor casi siempre ya está cubierta.** En las
peleas de gimnasio donde se sabe el tipo del líder, el abridor tiene x2 en 486
casos y gana el 64,6%; tiene x1 en 33 casos y gana el 51,5%. Es decir: casi
todas las peleas ya se pelean "con ventaja", y aun así el 35% se pierde.

**Conclusión operativa**: la reserva por ventaja de tipos (implementada) es
correcta como principio de orden pero **inerte contra el cuello real**, porque
la ventaja ya está ahí en el 93% de los casos. Lo que decide es lo que ocurre
dentro del combate (aguante, vida real al entrar, turnos), no quién abre ni el
tipos de quien abre.

### 1.8 El PS real al entrar al gimnasio (151 peleas, runs modernos)

Cruzando cada pelea de gimnasio con la vida media real del paso anterior
(`paso.vida_media`, el único dato de PS fiable):

| vida media al entrar | n | gana |
|---|---|---|
| 95–100% | 105 | 76,2% |
| 75–95% | 13 | 100% |
| 50–75% | 14 | 64,3% |
| 0–50% | 19 | 36,8% |

| caídos al entrar | n | gana |
|---|---|---|
| sin caídos | 127 | **76,4%** |
| con caídos | 24 | **50,0%** |

**Hay dos cuellos, no uno**:

1. El conocido de §1.1: entrar con caídos (o muy gastado) → se pierde la mitad.
   El pokecenter antes del gimnasio ya está resuelto (el bot lo elige el 100%
   de las veces que está disponible), así que este cuello es residual.
2. **El nuevo**: con el equipo entero y al 95–100% de vida se sigue perdiendo
   el 24%. No es vida, no es nivel, no es el orden, no son los tipos. Es la
   pelea automática en sí, y **no se mide desde fuera**: el bot solo pulsa
   auto-battle y lee el resultado. Para cerrarlo harían falta los turnos
   (daño por turno), que es lo que aún no se ha instrumentado en el log.

**Siguiente paso medible**: instrumentar el primer turno de cada pelea de
gimnasio (con qué abre el rival, cuánto daño entra al abridor) para separar
"el rival pega un 2x" de "el abridor aguanta poco". Esa es la medición que
falta para decidir si el cuello 2 es de orden defensivo (quién abre) o de
nivel dentro del combate.

### 1.9 Lote de 100 runs (línea base, no validación)

Decisión del usuario: lanzar 100 runs con la estrategia actual (reserva por
ventaja) para ver "hasta dónde llega". Lo que sale **no valida la estrategia**
— §1.7 dice que es inerte contra el cuello — sino que fija la **línea base**
del bot con ella puesta, contra la que comparar cualquier cambio futuro.

Se lanza con `scripts/medir/lote_100.py`, que encadena ~50 tandas de 2 (el
tope de `lanzar_tanda.py`; con más la sesión se queda sin memoria y las runs
mueren por el entorno). Cada tanda pasa integridad (387 checks) y prueba de
humo antes de gastar juego, espera a las 2 runs, ingiere en `corpus.db` y va
imprimiendo la media de insignias. Detalle por run en `data/medidas.json`.

**Referencia histórica**: 1,14 insignias/run sobre 284 runs (8 posibles), con
1 `CHAMPION`. Si el lote de 100 no mejora de forma clara ese 1,14, la
estrategia de reserva no aporta al resultado global (lo esperable: es inerte
en el cuello) y el cuello 2 (§1.8, equipo entero y aun así perder) sigue sin
explicación.

Queda descartado que el orden por ventaja de tipos arregle Misty/Erika: los
jefes donde Bulbasaur no tiene ventaja (Surge, Koga, Sabrina, Blaine) no son
los cuellos (Erika 51%, Misty 54% son los peores y tienen ventaja).

#### El HUD miente con los caídos (el docstring tenía razón)

Al perder, el log escribe `nos quedan:` con el **porcentaje del HUD**, y ahí se
ve el fallo:

```
Gym Battle vs Lt. Surge!   marcador 13-1
  nos quedan: Butterfree(100/100), Venonat(100/100), Jigglypuff(100/100),
              Ivysaur(100/100), Pikachu(100/100)
```

Una derrota **13-1**, con el equipo entero caído, y el HUD marca **100% a los
cinco**. Es exactamente lo que avisa `_apuntar_ps_real`: el porcentaje del HUD no
sirve para un món caído.

#### Dónde se pierde de verdad (Kanto, 18.871 peleas)

| gimnasio | G / P | victoria |
|---|---|---|
| Brock | 1384 / 207 | **87,0%** |
| Misty | 498 / 427 | **53,8%** |
| Lt. Surge | 241 / 88 | **73,3%** |
| Erika | 92 / 90 | **50,5%** |
| Koga | 50 / 18 | **73,5%** |
| Sabrina | 21 / 11 | **65,6%** |

Los dos muros son **Misty (53,8%)** y **Erika (50,5%)**, dos monedas al aire. Y en
las derrotas contra Misty los móns que más aparecen son los que peor encajan:
**Bulbasaur (179), Ivysaur (68)** —Planta es 2x débil a Psíquico— y **Sandshrew
(68)** —Tierra es 2x débil a Agua—. Es literalmente el caso de "móns inútiles
contra ese tipo" que describe la guía del bot.

#### El corpus en SQLite

`pkl_corpus.py` hace el parseo **una vez** y lo deja consultable:

```
uv run --group dev python juegos/pokelike/scripts/pkl_corpus.py
```

Tablas: `run` (2190) · `paso` (1708, las trazas) · `nodo` (30798) · `pelea`
(18871) · `evento` (291085, con la **línea cruda** de todo lo demás) · `sonda`.

Cada `run` lleva `lote`, `valido` y `tiene_traza`: `valido` sale del nombre del
directorio (`_ABORTADO_`, `_ROTO`, `TIMEOUT`…), y es lo que impide que un lote
`ABORTADO` vuelva a colarse en una media como hizo `h21`.

Elegir SQLite no fue por velocidad (94 MB y 600k líneas son calderilla) sino
porque **el parseo se escribe una vez y se testea**, en lugar de reescribir un
parser en cada pregunta —que es de donde salieron los cuatro fallos de una sola
sesión: el `parents[3]`, el `dist = len(prev) - k`, el `placeholder` vacío y el
lote `h21` en la media—.

**Aviso, y es el importante:** una base de datos **congela el parseo**. Si un
campo se lee mal, se guarda mal y encima parece autoritativo. Prueba de ello: la
primera versión de la ingesta daba **16.929 victorias y 0 derrotas** porque la
derrota tiene otro formato (`>>> COMBATE PERDIDO contra X | nos quedan: ... | 6-1`)
y el regex solo casaba la victoria. Se arregló y salieron las 1.942 derrotas, que
cuadran exactamente con los 1.942 `GAME_OVER` del corpus. Sin esa comprobación,
la BBDD habría mentido con toda la autoridad de una BBDD.

**No consultar `corpus.db` mientras hay un lote en marcha.** `lote_100.py`
ingiere cada run al terminarla, así que lanza escrituras sobre el mismo fichero
que se está leyendo. Medido el 16-10: la misma consulta devolvió filas y luego
cero filas sin cambiar nada, y un `where insignias >= 4` que debía casar con 50
runs devolvió 0. Las lecturas inconsistentes se confunden con un hallazgo. Se
espera a que el lote cierre.

### 1.10 El muro es Misty, y las capturas son un síntoma (16-10)

Medición sobre las 958 runs que terminan con **1 insignia** (el escalón que se
come el 76% de las partidas):

| último rival | runs |
|---|---|
| **Gym Battle vs Misty!** | **416** |
| Bug Catcher / Ace Trainer / Officer (sumados) | 176 |

La caída 1→2 insignias (958 → 225) es el precipicio real del juego, muy por
encima del salto a la Liga. Y cuadra con §1.9: Misty es el muro más bajo (53,8%).

**Lo que NO hay que concluir: que capturar más sea la palanca.** Los datos
invitan a ello y es una trampa:

| capturas en la run | n | media insignias | champions |
|---|---|---|---|
| 0–1 | 531 | 0,20 | 0 |
| 2–3 | 949 | 1,04 | 0 |
| **4–6** | **524** | **2,22** | **11 (todos)** |
| 7+ | 29 | 2,07 | 0 |

Los 11 campeones del corpus capturaron 4-6 veces y ninguno 2-3, así que parece
la palanca obvia. **Pero las capturas son un síntoma de haber sobrevivido**, no
la causa: medido en los logs vivos, el bot **captura en el 100% de las pantallas
de captura que ve** (`sin candidatos: huyo` = 0 en 4 runs; cada run ve 2 pantallas
y hace 2 capturas). No hay huidas que arreglar. Lo que limita las capturas es
que la run **muere antes de llegar a más pantallas**: 2 pantallas en 40-90 pasos.
Subir el peso de la captura no cambia nada; lo que cambia el número de capturas
es durar más.

**El patrón de muerte, en crudo** (`log-2026-10-16_22-54-33_p178681.txt`):

```
step 32-34  3/3 vivos al 100%  -> elige entrenador (score 193.5) -> GANA pero pierde Bulbasaur
step 36     2/3 vivos, 48%     -> disp=['entrenador','item']      -> elige item (score 90.5)
step 38-39  2/3 vivos, 48%     -> disp=['entrenador']  ¡única salida! -> score -49.5 -> GAME_OVER
```

No es una mala decisión: es una **espiral sin salida**. El bot sabía que el
entrenador era suicida (`-49.5`, penalización `-140` por "2 móns en pie, 1
caído y sin cura a mano") y lo peleó porque era el único nodo. Cuando el
entrenador es la única salida, la §2 del módulo ya lo dice: la puerta correcta
no es "no entres". El daño estaba hecho al perder el món, y con un equipo de 3
un solo caído ya es media run.

**Hipótesis abierta (H21), pendiente de A/B:**

> La escalera de riesgo del entrenador **no cambia la decisión** cuando el
> entrenador es el único nodo, así que la única palanca es no llegar ahí: el
> bot debe **no pelear entrenadores con el equipo ya tocado aunque el combate
> esté por delante en el mapa**, priorizando la rama con centro.

- **Criterio de falsación, escrito antes de mirar los datos**: si el brazo con
  la rama-centro priorizada no baja el número de runs que mueren con **caídos al
  abrir la pelea**, H21 es falsa.
- **Brazo de control**: el bot actual. **Un solo cambio**: el peso de la rama
  que lleva a centro cuando hay caídos.
- **Aviso de trampa ya medida** (§1.3): el pokecenter antes del gimnasio ya se
  elige el 100% de las veces que está disponible, así que el margen está en las
  pantallas donde **no** hay centro, no en las que sí.

**H22 · El filtro de captura no miraba la defensa (implementada, en medida).**

El hallazgo es de código, no de pesos: en `politica.elegir_captura`, la rama que
**siempre** se ejecuta (`region` se pasa siempre desde `_elegir_captura`) llama a
`cobertura_region`, que es **solo ofensiva** — cuenta los gimnasios a los que el
candidato pega 2x y nunca los que le pegan 2x a él. La defensa existía, pero en
la rama `else` de `region`: **código muerto**. Y `utilidad_contra` ya devolvía la
defensiva como segundo valor; el llamador solo usaba `[0]`.

El caso que lo motivó, con los datos reales de `data/regiones.json`:

| candidato contra Misty (`tipos_equipo` = Psíquico/Agua) | pega 2x | recibe 2x |
|---|---|---|
| Bulbasaur (Planta/Veneno) | al Agua ✅ | **del Psíquico** ✗ |
| Voltorb (Eléctrico) | al Agua ✅ | de nada ✅ |

Ofensivamente empatan, así que el filtro los veía iguales y decidía por variedad.

Arreglo: `debilidad_region(tipos, region, n_gimnasios=3)` cuenta los gimnasios de
la apertura que le pegan 2x, y `PESO_DEBILIDAD_REGION` los resta.

- **Criterio de falsación, escrito antes del lote**: si el brazo con la defensa
  no **baja la tasa de derrota contra Misty y Erika** (§1.9: 53,8% y 50,5%), H22
  es falsa y el término se quita.
- **Aviso de que puede ser inerte, y por qué se lanza igual**: comprobado a mano,
  con peso 12 (castigo 24 en Bulbasaur) **la decisión emblemática NO se
  invierte**. Bulbasaur saca 2x en la apertura=2 (Brock *y* Misty) y dobla en
  variedad (dos tipos nuevos valen 24), así que sigue ganando. Si el término no
  cambia ninguna captura, el lote saldrá clavado a la línea base y lo sabremos
  por eso.
- **La otra mitad sin tocar**: el **starter** no pasa por `elegir_captura`, así
  que si el starter es el Bulbasaur, el món débil contra Misty sigue entrando
  por ahí. Es el siguiente sitio a mirar si H22 sale inerte.

**H23 · La defensiva de `utilidad_contra` devuelve el mejor caso, no el peor
(documentada, sin tocar todavía).**

`utilidad_contra` docstring: *"**Defensiva = peor caso**, porque ahí sí es el
peor: el ataque rival es de tipo desconocido y un solo món con una debilidad real
se lo lleva."* El código hace lo contrario:

```python
de = min(T.mejor_efectividad([objetivo], [t]) for t in tipos)   # min = MEJOR caso
```

Un `min` sobre el daño recibido elige el tipo que **menos** sufre, o sea esconde
la debilidad. Medido (tipos reales de `data/`):

| món | tipos | objetivo | `de` hoy (min) | peor caso real (max) |
|---|---|---|---|---|
| Bulbasaur | Planta/Veneno | Psíquico | 1.00 | **2.00** |
| Bulbasaur | Planta/Veneno | Agua | 0.50 | 1.00 |
| Squirtle | Agua | Psíquico | 1.00 | 1.00 |
| Charmander | Fuego | Roca | 2.00 | 2.00 |

La fila que importa es la primera: el Veneno de Bulbasaur es **2x débil al
Psíquico de Starmie**, y la cuenta devuelve 1.00 — "neutro".

**Por qué llega hasta el starter.** `elegir_starter` puntúa con
`ventaja = ofensiva × aguante_bueno(defensiva)`, y `aguante_bueno` (=`2.0/de` para
`de>=1`) convierte un `de` falso de 1.00 en factor 2.0 en vez de 1.0. Resultado
contra el Psíquico de Misty:

| starter | hoy | corregido |
|---|---|---|
| Bulbasaur (Planta/Veneno) | 2.00 | **1.00** |
| Squirtle (Agua) | 2.00 | 2.00 |
| Voltorb (Eléctrico) | 2.00 | 2.00 |

O sea: **hoy el starter que gana el gimnasio y el que lo pierde puntúan
idénticos.** No es que la defensa no se mirase en `elegir_starter` — se mira, y
devuelve una cifra que no distingue. Eso explica el docstring de `elegir_starter`
("En Kanto sale Bulbasaur") sin necesidad de suponer nada más.

**Alcance: no es un cambio de una letra.** Cuatro sitios leen `[1]`, y dos son de
ordenación, no de starter: `348` (`ventaja` → starter), `929`, `1159` y `1175`
(los dos últimos, ayudas de orden). Los que solo usan `[0]` (471, 540, 542, 712,
722, 740, 742) no cambian.

- **Criterio de falsación, antes de lanzar**: si el brazo corregido no **baja la
  derrota contra Misty y Erika** (§1.9: 53,8% y 50,5%), H23 es falsa.
- **No se toca hasta que cierre el lote de H22**, y luego se mide **sola**: H22
  (filtro de captura) y H23 (starter y orden) son las dos mitades de la misma
  ceguera, y lanzarlas juntas deja sin saber cuál de las dos movió la aguja.
- **Aviso de riesgo**: `aguante_bueno(2.0)=1.0` y `aguante_bueno(1.0)=2.0`, así
  que corregir parte por la mitad `ventaja` de **todo món con un 2x** contra la
  apertura. En Kanto eso probablemente **cambia el starter de Bulbasaur a
  Squirtle**, que es un cambio grande en la apertura de toda run. Por eso se
  mide, no se razona.

**H24 · En el mapa de la Liga el bot caza, y entra al Alto Mando tocado.**

Primera vez en cuatro lotes que llegan runs a la Liga (3 de 51, lote
`lote_defensa2`), así que esto ya no es teoría. El bot **lo dice él mismo**:

```
DEC nodo mapa=Elite Four & Champion nodo=n7_0 tipo=jefe razon=jefe score=4.0
(jefe: única salida, se entra igual (1 caído(s), carry flojo (41%)))
```

Y con qué entró, medido en los `ps_abre` de los dos casos:

| run | entra a la Liga con | resultado |
|---|---|---|
| 1 | Aerodactyl `0/168`, Golduck `78/186` | gana Lorelei, Bruno y Agatha → muere en **Lance** con 2 vivos |
| 3 | Gengar `47/135` | Lorelei le mata **5 de 6** → muere en **Bruno** |

**El Alto Mando son 4 combates consecutivos sin cura entre ellos** (~14 s entre
uno y otro). El PS es un recurso que no se recupera dentro: llegar tocado es
llegar muerto. Y el bot se pasa el mapa de la Liga como si fuera una ruta normal:

```
n2_0 batalla score=112.0 (capturar: equipo de 6 y ya a nivel, ampliar...)
n6_0 batalla score=5.0 (cazar: ya en pie y a nivel; deja 1 combate(s) al jefe)
```

**29 batallas y 29 entrenadores en una sola run del mapa de la Liga.** El nodo
de cura existe ahí (`n6_2 tipo=cura crudo=pokecenter`) pero no se reserva para
el final. Detalle que lo clava: en `n6_0` el marcador ya dice `deja 1 combate(s)
al jefe`, el score es `5.0` —y aun así pelea, porque el score es **positivo**—.
Ninguna regla dice "en este mapa cada pelea cuesta PS y no da nada".

- **Arreglo propuesto**: en el mapa de la Liga (`insignias >= len(jefes)`), las
  peleas no ganan nivel (ya se va por encima del rival) y solo gastan PS, así que
  pasan a penalizarse, y la cura se prioriza **inmediatamente antes del jefe**.
- **Criterio de falsación**: si una run sigue entrando al Alto Mando con algún
  món a 0 PS, el arreglo no está funcionando. La prueba es directa y no
  estadística: **el `ps_abre` de Lorelei tiene que salir sin ningún `0/`**.
- **Nota**: el reparto por miembro **sí funciona**. Run 1 ganó Lorelei, Bruno y
  Agatha con el orden estático de `orden_para_elite_four` (posición 1→Lorelei,
  2→Bruno, 3→Agatha, 4→Lance). Lo que falla no es el orden, es con qué llega.
- **Segunda mitad, subordinada**: los reserva (posiciones 5-6) son los que acaban
  peleando contra Lance —en run 1, Gyarados y Golduck, los dos Agua, que pegan
  **0,5x** al Agua de Lance—. Pero eso solo importa si se llega entero; con 5 de 6
  en pie pelea la posición 4 (Venusaur, 2x al Agua). **Primero H24, luego esto.**

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
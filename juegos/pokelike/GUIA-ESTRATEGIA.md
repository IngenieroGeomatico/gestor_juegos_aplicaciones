# Reglas de estrategia extraídas de la guía

Todo lo de aquí sale de leer la wiki de la comunidad (**no** del código del
juego). Fuente: <https://pokelike-guide.fr/> (ver `AGENT.md` para la lista de
páginas). Cuando la guía y el comportamiento medido choque, gana lo medido y
esta lista se corrige.

> La wiki **esconde el contenido según tu progreso** para no hacer spoiler. Se
> desbloquea marcando "I have finished a story campaign" y luego "Show
> everything" en el diálogo de progreso, que guarda en
> `localStorage['pokelike-profil']`:
> `{"campagneTerminee":true,"regionsBT":[...],"defini":true}`.

## Qué decide una run (resumen de la wiki)

1. **Ventaja de nivel**: llevar **1+ niveles por encima** del rival. Es la palanca
   más fiable; incluso un món con mal matchup gana con ese colchón.
2. **Routing**: los nodos de item ganan a los de combate al principio; las
   curaciones ganan a las tiendas al final.
3. **Economía**: la **base** ya reparte experiencia a **todo el equipo**:
   **+2 niveles tras un combate contra entrenador y +1 tras un salvaje**. El
   Lucky Egg sube al portador a **+3 / +2** con un 30% de probabilidad extra.
   Esto explica por qué los entrenadores son tan valiosos: **doblan la
   experiencia** y la dan al equipo entero, no solo al delantero. El Lucky Egg
   solo aparece a partir de la **zona 5** (nodo de mapa 4+), no se puede
   apuntar (los nodos de item ofrecen 3 opciones al azar) y cuanto antes mejor,
   porque su valor crece con cada nodo que queda.
4. **Drafting**: los type bonuses ya cuentan en Normal, no solo en Battle Tower.
5. **Tiers y evoluciones son sistemas separados**: subir el tier del ataque no
   evoluciona, y evolucionar no sube el tier.

## Nodos

- **Trade: el nodo más fuerte del juego.** Cambias un món por uno aleatorio que
  viene con **+3 niveles**, vuelve **a tope de vida** y **conserva el Move
  Tutor** que le hayas subida. Se sacrifica el món que menos aporte.
- **Curación**: siempre hay un pokecenter en el camino al líder, así que pasar
  por él cura gratis. No es opcional.
- **?**: aleatorio, con probabilidad de shiny y de recompensa sorpresa, pero
  también puede dar una situación peor. **Se entra con el equipo por delante de
  la curva** (por ejemplo con un arranque de Lucky Egg) o cuando la alternativa
  segura no aporta nada. **Se salta justo antes de un jefe** y en Nuzlocke,
  donde lo malo es permanente.
- **Reroll**: la tecla **R vuelve a tirar el mapa**. Sirve para buscar un trade o
  un camino de exp mejor.

## Equipo

- Los combates son **automáticos**: no se actúa en combate. Todo se decide antes
  con el **orden del equipo** y **dónde va cada objeto**, que son gratis.
- **Lead into the matchup**: abrir con el que gana el primer intercambio, no con
  el que más quieres proteger.
- **Proteger el carry**: si el equipo gira en torno a un daño principal, ordenar
  el resto para que llegue vivo a su turno.
- **No apilar la misma debilidad delante**: si los dos primeros se doblan
  contra el mismo tipo, un mal matchup se desborda antes de que lleguen
  respuestas.
- **No apostar todo a un solo món** (aun así es error de principiante: un carry
  solo se dobla con un mal matchup y acaba la run).
- Heridos por debajo del 50%: **al final del orden**, no fuera del equipo. Así
  siguen ganando experiencia y no se matan.
- Evoluciones por nivel: empujar al món más allá del umbral **compensa**, y el
  Pokédex tiene los niveles.

## Objetos

| Grupo | Objetos |
|---|---|
| Tipo (+40%, y **cambia el tipo del ataque**) | Silk Scarf (Normal), Charcoal (Fire), Mystic Water (Water), Magnet (Eléctrico), Miracle Seed (Planta), Twisted Spoon (Psíquico), Soft Sand (Tierra), Hard Stone (Roca), Sharp Beak (Volador), Poison Barb (Veneno), Spell Tag (Fantasma), Dragon Fang (Dragón), Black Glasses (Siniestro), Metal Coat (Acero), Pixie Plate (Hada) |
| Daño | **Expert Belt (+100% en golpes muy superficientes)**, Choice Specs, Choice Band, Wide Lens, **Metronome (el doble tipo ataca con el otro; +20% todo)**, Lagging Tail, Scope Lens |
| Supervivencia | Assault Vest, **Rocky Helmet (12% del HP máx al atacante)**, Red Card, Leftovers, Shell Bell, Eviolite |
| Utilidad | Quick Claw, Choice Scarf, King's Rock, **Lucky Egg (+30% nivel extra/combate)** |
| Consumibles | **Sacred Ash** (cura y revive), **Rare Candy (+3 niveles)**, Moon Stone (fuerza evolución), TM (+1 tier) |

Prioridad: el objeto que **cubra el agujero actual** vale más que un plus de
daño. Los escalables van en quien se queda en el equipo, los defensivos en el
carry, y Lucky Egg en el món que más Battles pelea.

## Kanto (Gen I)

- Es la región **más indulgente** y la mejor para la primera pasada completa.
- **Bulbasaur** es el starter más fácil con diferencia: ventaja de tipo contra
  Brock **y** Misty, y aguanta contra Lt. Surge. **El orden de gimnasios es el
  del juego base** (Brock → Misty → Lt. Surge…), así que se planifica.
  Squirtle es seguro y redondeado. Charmander es el más difícil al principio
  (desventaja contra los primeros gimnasios); solo para quien confidently sabe,
  y con Spike de insecto + Rocky Helmet.
- **No intercambiar el starter demasiado pronto**: mantiene su ventaja sobre
  los 2-4 primeros gimnasios.
- Para llegar al Elite Four: hoja de 8 insignias y luego el campeón, que es donde
  de verdad se decide la run.

## Battle Tower (para después de la Story)

- El type bonus corre sobre puntos y 12 tiers: cada món da 1 punto por cada tipo
  que lleva, un shiny da +1, y **cada 2 puntos = 1 tier** (2/4/6…/24).
- Los bonuses fuertes: **Bug da +1 nivel tras el combate** (nivel garantizado en
  tier 10) — es el motor de niveles; Steel reduce daño hasta −90%; Dark es
  crítico; Electric da ataques extra.
- Un equipo de seis del mismo tipo = 6 puntos = tier 3; los duales y los shinies
  suben más.
- Arrancadores de la torre: cualquier món con el que hayas **terminado una run**
  en cualquier modo.

## Cómo se juega esto en la práctica

El bot NO microgestiona combates. Su trabajo es el mismo que el del humano:
elegir nodo, ordenar el equipo y colocar los objetos. El libro de jugadas que
se usa, en este orden:

1. Si es pantalla nueva y el equipo es pequeño, **cazar uno** (el primero que
   sirva: los siguientes son más flojos y de menos nivel).
2. Si falta nivel, **entrenador**; si no hay, **hierba alta**.
3. **Curar** cuando el pokecenter está en camino al líder, y si no hay centro a
   mano, no pelear por debajo de ~40% de vida con el equipo.
4. A **nivel o por encima** del líder,mtutor y objetos para el principal.
5. A un jefe se entra con el mejor contragolpe al frente, móns heridos al final.


## Correcciones y datos que.cuesta adivinar (leídos, no deducidos)

- **La experiencia es de equipo, no del delantero**: +2 niveles todos contra
  entrenador, +1 todos contra salvaje. Por eso "entrenador > hierba alta" no es
  una preferencia, es el doble de niveles para los seis.
- **Lucky Egg**: el equipo entero ya sube; el huevo da al **portador** un 30%
  de probabilidad de **un nivel extra** (3 en vez de 2, o 2 en vez de 1). Se
  pone en un món que se va a quedar en la run entera.
- **Los nodos de item no se compran**: eliges **1 de 3** al azar. Nada de
  tienda a mitad de partida.
- **Story solo paga si la run termina** (abandonar o perder no da nada). Kanto
  Classic = ₽200. El Poké Mart es **entre runs**: Shiny Egg ₽2.000, Legendary
  Egg ₽10.000, Vitaminas ₽200 (EVs permanentes).
- **Los legendarios** solo pasan a la Battle Tower si salen de Legendary Egg.
- **Sin cuenta, todo es local al navegador.** Con cuenta se sincroniza la run
  entre dispositivos.
- **Type chart**: la guía dice que es el **Gen 6 completo** (18 tipos, Fairy
  incluido). El chart que extraje del juego es casi el Gen 6, con excepciones
  medidas. Donde discrepan, el juego manda: `data/chart_juego.json`.
- **EVs / Vitaminas** son de Battle Tower/entre-runs, no de una partida suelta.
- **Type bonuses**: Battle Tower y Challenge. En Story no aplican (aunque la
  página de Normal los menciona de pasada, la página de traits los limita a
  esos dos modos).

## Páginas leídas (las 68 descargadas y revisadas)

Están en `/tmp/opencode/guias/` como texto plano, una por página, junto a
`/tmp/opencode/en.txt` con el índice. Para volver a bajarlas:

```bash
cd /tmp/opencode && python3 bajar2.py
```

Índice: `https://pokelike-guide.fr/sitemap-index.xml` → `sitemap-0.xml` da las
71 páginas. **El bloqueo por progreso es solo de cliente**: el texto completo
viene en el HTML plano, se extrae con `curl` + regex sin necesidad de navegador.

---

## Secciones completas (leídas de las 68 páginas)

### Nuzlocke
- Permadeath + **una captura por zona**: sin red de seguridad, el banquillo
  fino no absorbe errores, así que proteger lo que hay supera perseguir daño.
- El **delantero debe ser el món más gastable y fiable**, no el mejor: se lleva
  el primer intercambio, el más impredecible. El carry va más profundo, donde
  el matchup ya se conoce.
- Priorizar volumen y tipado limpio sobre daño bruto. Evitar apilar la misma
  debilidad. Dejar siempre un **pivote neutro** paraliderar a ciegas.
- Antes de cada jefe: comprobar matchups, que la respuesta lidere, y que **ningún
  solo faint acabe la run**.

### Battle Tower (Kanto = etapa 1)
- Etapa 1 solo Gen I (hasta #151), niveles más bajos de toda la torre: ideal para
  aprender el sistema de type bonuses sin castigo.
- Jefe final: **Ash Ketchum**, equipo mixto (Snorlax, Espeon, Venusaur,
  Blastoise, Charizard, Pikachu) niveles **63-73**, con el **Pikachu en el
  último slot con +5 niveles** y `traitBonus +1` (cada tier se activa con un
  món menos).-counter: llevar bonus de **Fantasma o Psíquico** y tumbar al Pikachu primero.
- Scalars: R1-3 Flint (Fuego 24-26), R2-1 Falkner (Volador 30-32), R2-2 Bugsy
  (Bicho 42-45), R2-3 Lorelei (Hielo/Eléctrico 46-50), R3-1 Sabrina
  (Psíquico/Planta 51-56), R3-2 Agatha (Fantasma/Veneno 58-63).
- **Arranque**: cualquier món con el que se haya **terminado una run**. Para
  Kanto/Johto basta un **Scyther**; de Hoenn en adelante mejor **Mr. Mime o
  Aerodactyl** (los bichos se doblan antes).
- **Comps fuertes**: Bug al principio (Scyther/Pinsir con boost de Bicho),
  Alakazam + Arcanine (Fuego+Psíquico), Lagarto/Dragón al final, Acero en Sinnoh
  (Dialga, Heatran, Empoleon) hasta −90% daño recibido.
- **EVs**: se compran con Vitaminas (₽200), +10% por estadística, máx. 10 por
  stat, y persisten entre runs. Ya no se gratis.

### Challenge Mode
- **La mejor granja del juego**: run completada ₽1.000; derrota paga 10% por
  mapa. Runs cortas y repetibles, ideal para ahorrar para Legendary Eggs.
- Slaking carry (~511 ATK), Weavile con motor Bicho/Hielo, y Bicho con pasivos
  (Silver Powder, Insect Plate, Shed Shell, Tanga Berry) que **nivela el mapa
  entero a mitad de run**.

### Objetos (matices)
- **El objeto de tipo elige con qué atacas**: un dual con el objeto de su
  segundo tipo ataca con ese tipo, +40%. Ya no estás atado a su tipo por
  defecto. **Lucha, Bicho y Hielo no tienen objeto**: el único cambio para esos
  es el **Metronome**.
- **Expert Belt: +100% en golpes muy eficaces**: en un món que ya acierta por
  tipo. **Choice Specs** +30% especial sin contraindicación (default segura).
  **Choice Band** +40% físico a cambio de −20% Def. **Wide Lens** +20% a todo
  cuando el tipo por defecto ya es el correcto. **Lagging Tail** dobla daño pero
  ataca el último: solo en un tanque.
- **Supervivencia**: Assault Vest (muro especial), Rocky Helmet (12% del HP máx
  al atacante, canónico contra multi-golpe), **Red Card** (mitad de daño en golpes muy eficaces, el contraataque de un jefe que te mata de un golpe),
  Leftovers, Shell Bell (cura 15% del daño hecho,colgado del ofensivo),
  **Eviolite** (trampa y herramienta: impide evolucionar, pero da +50% Def y
  Sp. Def si no está evolucionado).
- **Consumibles**: TM (tier +1, en el carry firme), **Moon Stone** (fuerza
  evolución sin nivel), **Rare Candy** (+3 niveles planos, al carry antes de un
  jefe), **Sacred Ash** (cura y revive: el botón de emergencia).

# Tabla de tipos (la del juego, no la oficial)

Chart real de pokelike.xyz, extraido del juego a `data/chart_juego.json`.
**No** es el Gen 6 oficial: hay tres desviaciones medidas que ya estan
en la tabla de aqui abajo. Para elegir el delantero hay que leer las dos
mitades: con quien **pega** y quien le **pega**.

## 1. Ofensivo: este tipo pega x2 a estos

| Ataca | x2 contra | x1/2 contra | x0 (inmune) |
|---|---|---|---|
| **Normal** | — | Roca, Acero | Fantasma |
| **Fuego** | Planta, Hielo, Bicho, Acero | Fuego, Agua, Roca, Dragón | — |
| **Agua** | Fuego, Tierra, Roca | Agua, Planta, Dragón | — |
| **Eléctrico** | Agua, Volador | Eléctrico, Planta, Dragón | Tierra |
| **Planta** | Agua, Tierra, Roca | Fuego, Planta, Veneno, Volador, Bicho, Dragón, Acero | — |
| **Hielo** | Planta, Tierra, Volador, Dragón | Fuego, Agua, Hielo, Acero | — |
| **Lucha** | Normal, Hielo, Roca, Siniestro, Acero | Veneno, Volador, Psíquico, Bicho, Hada | Fantasma |
| **Veneno** | Planta, Hada | Veneno, Tierra, Roca, Fantasma | Acero |
| **Tierra** | Fuego, Eléctrico, Veneno, Roca, Acero | Planta, Bicho | Volador |
| **Volador** | Planta, Lucha, Bicho | Eléctrico, Roca, Acero | — |
| **Psíquico** | Lucha, Veneno | Psíquico, Acero | Siniestro |
| **Bicho** | Planta, Psíquico, Siniestro | Fuego, Lucha, Veneno, Volador, Fantasma, Acero, Hada | — |
| **Roca** | Fuego, Hielo, Volador, Bicho | Lucha, Tierra, Acero | — |
| **Fantasma** | Psíquico, Fantasma | Siniestro | Normal |
| **Dragón** | Dragón | Acero | Hada |
| **Siniestro** | Psíquico, Fantasma | Lucha, Siniestro, Hada | — |
| **Acero** | Hielo, Roca, Hada | Fuego, Agua, Eléctrico, Acero | — |
| **Hada** | Lucha, Dragón, Siniestro | Fuego, Veneno, Acero | — |

## 2. Defensivo: este tipo recibe x2 de estos

| Tipo | Le pegan x2 | Le resisten x1/2 | Inmune a |
|---|---|---|---|
| **Normal** | Lucha | — | Fantasma |
| **Fuego** | Agua, Tierra, Roca | Fuego, Planta, Hielo, Bicho, Acero, Hada | — |
| **Agua** | Eléctrico, Planta | Fuego, Agua, Hielo, Acero | — |
| **Eléctrico** | Tierra | Eléctrico, Volador, Acero | — |
| **Planta** | Fuego, Hielo, Veneno, Volador, Bicho | Agua, Eléctrico, Planta, Tierra | — |
| **Hielo** | Fuego, Lucha, Roca, Acero | Hielo | — |
| **Lucha** | Volador, Psíquico, Hada | Bicho, Roca, Siniestro | — |
| **Veneno** | Tierra, Psíquico | Planta, Lucha, Veneno, Bicho, Hada | — |
| **Tierra** | Agua, Planta, Hielo | Veneno, Roca | Eléctrico |
| **Volador** | Eléctrico, Hielo, Roca | Planta, Lucha, Bicho | Tierra |
| **Psíquico** | Bicho, Fantasma, Siniestro | Lucha, Psíquico | — |
| **Bicho** | Fuego, Volador, Roca | Planta, Lucha, Tierra | — |
| **Roca** | Agua, Planta, Lucha, Tierra, Acero | Normal, Fuego, Veneno, Volador | — |
| **Fantasma** | Fantasma, Siniestro | Veneno, Bicho | Normal, Lucha |
| **Dragón** | Hielo, Dragón, Hada | Fuego, Agua, Eléctrico, Planta | — |
| **Siniestro** | Lucha, Bicho, Hada | Fantasma, Siniestro | Psíquico |
| **Acero** | Fuego, Lucha, Tierra | Normal, Planta, Hielo, Volador, Psíquico, Bicho, Roca, Dragón, Acero, Hada | Veneno |
| **Hada** | Veneno, Acero | Lucha, Bicho, Siniestro | Dragón |

## 3. Desviaciones del Gen 6 oficial (medidas en el juego)

Estas tres NO son un error: son lo que hace el juego. La guia de la comunidad
las tiene como Gen 6 estandar, y se equivoca en estas.

- **Veneno -> Tierra y Veneno -> Roca = x1/2** (en el oficial es x1).
- **Acero -> Dragon = x1** (en el oficial Dragon es x2 contra Acero).
- **Hada -> Dragon = x2** (en el oficial Dragon es x0 contra Hada).

## 4. Como elegir quien va primero

Se mira **el otro lado de la batalla**, y hay que leer las dos mitades. Delante
va el món que **pega x2** al rival **y no se lleva x2**. Ojo: que un tipo sea
bueno atacando y malo defendiendo es lo normal, no una excepcion.

Ejemplo real y facil de equivocar — **Bulbasaur (Planta/Veneno) contra Fuego**:

- Ataque: Planta -> Fuego = **x1/2** (pega la mitad).
- Defensa: Fuego -> Planta = **x2** (recibe el doble).

O sea que **Bulbasaur es el peor emparejamiento posible contra un Charmander**:
pegando la mitad y recibiendo el doble. Delante contra Fuego va **Agua, Roca o
Acero**, que pegan x2 y ademas resisten.

**Y el caso contrario, para no-learn la cosa al reves**: Bulbasaur contra un
rival de **Planta**:
- Ataque: Planta -> Planta = **x1/2**.
- Defensa: Fuego -> Planta no aplica; el rival es Planta y Planta -> Planta es
  x1/2, asi que los dos se castigan igual y Bulbasaur aguanta.

Conclusion: **el delantero no es "el món mas fuerte", es el món que la
aritmetica de la fila y la columna de la tabla deja en mejor posicion.** Con
tipos duales hay que mirar los dos: un Veneno/Tierra contra Bicho aguanta doble
por el segundo tipo.

## 5. Errores que ya se han cometido

- **Confundir ofensiva con defensiva, y de paso invertir la fila**: se llego a
  decir "Bulbasaur es x2 contra Fuego". Falso por partida doble: Planta -> Fuego
  es **x1/2** y Fuego -> Planta es **x2**. Bulbasaur contra un Charmander es el
  peor emparejamiento, no el mejor. La fila se lee "este tipo pega x2 a estos";
  el 2 del lado de Fuego significa que **Fuego** le pega el doble a Planta, no
  al reves.
- **Asumir el chart oficial**: el del juego tiene tres desviaciones.
- **Mirar solo el tipo primario de un món dual**: tambien cuenta el segundo
  (Veneno/Tierra, Veneno/Roca).
- **Olvidar que el objeto de tipo cambia con que atacas**: un Bulbasaur con
  Semilla Milagrosa pega como Planta y ya no con Veneno.

Fuente de verdad para el bot: `juegos/pokelike/data/chart_juego.json`.
Si este archivo y el JSON discrepan, **manda el JSON** (es lo que lee el juego).

# Skill: Reglas de HeroQuest

Consultorio de reglas canónicas. Usa esta información para resolver dudas,
explicar mecánicas y asegurar que el contenido generado sea válido.

---

## Sistema de dados

### Dados de Ataque (rojos)
- **Cara negra (calavera)** = golpe acertado
- Cara blanca = fallo
- Se tiran según la stat de Ataque del personaje (1-3 dados)

### Dados de Defensa (azules)
- **Escudo** = bloqueo
- Cara sin escudo = fallo
- Se tiran según la stat de Defensa + bonificación de armadura

### Resolución
```
Golpes = Dados_ataque (negras) - Dados_defensa (escudos)
Mínimo 0 golpes.
```

---

## Puntos de personaje

### Cuerpo (Cu) — Vida física
- **Valores típicos**: 4-8 según clase
- **0 Cuerpo** = héroe cae inconsciente (no muere automáticamente)
- Si todos los héroes caen → fin de la aventura

### Mente (Me) — Resistencia mental
- **Valores típicos**: 2-6 según clase
- **0 Mente** = héroe atontado, no puede actuar un turno
- Se gasta para lanzar hechizos (según coste)
- Los monstruos también tienen Mente para resistir hechizos hostiles

### Movimiento
- **Casillas por turno** que el héroe puede desplazarse
- No se puede dividir (todo o nada)
- Se puede gastar en combate cuerpo a cuerpo (carga)

---

## Orden de combate

1. **Fase de héroes** (todos actúan en orden que elijan)
   - Moverse + Actuar (atacar, lanzar hechizo, abrir puerta, etc.)
   - Un héroe puede: moverse → atacar, O atacar → moverse
2. **Fase de monstruos**
   - Se mueven hacia el héroe más cercano
   - Atacan si están en casilla adyacente
   - Prioridad: atacan al herido primero (si están en rango)

---

## Combate cuerpo a cuerpo

1. Héroe elige objetivo (casilla adyacente)
2. Tira dados de Ataque → cuenta negras
3. Monstruo tira dados de Defensa → cuenta escudos
4. Golpes = negras - escudos (mín. 0)
5. Restar golpes al Cuerpo del monstruo
6. Si Cuerpo = 0 → monstruo derrotado

**Combate a distancia** (Ballesta):
- Misma mecánica pero sin necesidad de casilla adyacente
- Algunas armas tienen rango limitado

---

## Magia

### Quién puede lanzar
- Solo el **Mago** (y Elfo con hechizos de Agua/Aire)

### Cómo funciona
1. Elegir hechizo (ver `hechizos.json`)
2. Pagar coste en Puntos de Mente
3. El hechizo se activa automáticamente (no hay tirada)

### Hechizos hostiles vs. monstruos
- El monstruo tira 1 dado de Mente
- Si saca **cara negra** → resiste el hechizo
- Si falla → recibe el efecto completo

### Hechizos de curación
- No requieren tirada
- Devuelven Cuerpo al máximo posible

---

## Escuelas elementales

| Escuela | Tipo | Ejemplo |
|---------|------|---------|
| **Fuego** | Ofensivo | Bola de fuego |
| **Tierra** | Curación | Curar heridas |
| **Aire** | Utilidad | (pendiente) |
| **Agua** | Utilidad | (pendiente) |
| **Terror** | Ofensivo | Dardo de caos |

---

## Interacción con el entorno

### Puertas
- Se abren con acción (sin tirada)
- Algunas pueden estar cerradas con llave (requiere buscarla)

### Trampas
- Se activan al pisar la casilla
- El máster debe advertir antes ("¿Estáis seguros de pisar ahí?")
- Efectos: daño directo, veneno, dardos, etc.

### Tesoros
- Se recogen con acción
- Las pociones se consumen al usarlas
- Las armas se equipan inmediatamente

---

## Economy (entre misiones)

- **Oro ganado**: recompensa de la misión + tesoros encontrados
- **Tienda**: comprar armas/armaduras/pociones (ver `equipo.json`)
- **Límite**: máx. 10 items por personaje
- **Pociones**: máx. 2 por héroe (ocupan espacio)

---

## Referencia rápida de stats

### Héroes (caja base)
| Clase | Ataque | Defensa | Cuerpo | Mente | Mov. |
|-------|--------|---------|--------|-------|------|
| Bárbaro | 3 | 3 | 8 | 2 | 2 |
| Enano | 3 | 4 | 7 | 3 | 2 |
| Elfo | 2 | 3 | 6 | 4 | 2 |
| Mago | 1 | 2 | 4 | 6 | 2 |

### Monstruos básicos
| Monstruo | Ataque | Defensa | Cuerpo | Mente | Mov. |
|----------|--------|---------|--------|-------|------|
| Trasgo | 2 | 1 | 1 | 1 | 8 |
| Orco | 2 | 2 | 1 | 1 | 2 |
| Esqueleto | 3 | 2 | 1 | 1 | 4 |
| Zombi | 2 | 2 | 1 | 1 | 2 |
| Momia | 3 | 3 | 2 | 1 | 2 |
| Fimir | 3 | 3 | 2 | 2 | 2 |
| Gárgola | 3 | 4 | 1 | 3 | 2 |
| Guerrero del Caos | 4 | 3 | 2 | 5 | 2 |
| Abominación | 3 | 3 | 3 | 1 | 2 |
| Guerrero del Terror | 4 | 3 | 2 | 3 | 2 |

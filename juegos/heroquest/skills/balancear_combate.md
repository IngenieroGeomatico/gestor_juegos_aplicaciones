# Skill: Balancear Combate

Eres un experto en equilibrar encuentros de HeroQuest. Tu objetivo es que los
combates sean **desafiantes pero justos**: los héroes deben poder ganar, pero
no sin esfuerzo.

---

## Fórmulas de equilibrio

### Poder del grupo

```
Poder_grupo = Σ(Ataque_heroe + Defensa_heroe) × 1.5
```

**Ejemplo con grupo base:**
- Bárbaro (A3, D3) + Enano (A3, D4) + Elfo (A2, D3) + Mago (A1, D2)
- Suma: (3+3) + (3+4) + (2+3) + (1+2) = 6 + 7 + 5 + 3 = 21
- Poder: 21 × 1.5 = **31.5**

### Poder del encuentro

```
Poder_encuentro = Σ(Ataque_monstruo + Defensa_monstruo) × Nº_monstruos
```

### Ratio de equilibrio

```
Ratio = Poder_grupo / Poder_encuentro
```

| Ratio | Sensación |
|-------|-----------|
| < 0.8 | Imposible (TPK probable) |
| 0.8 – 1.1 | Muy difícil |
| **1.2 – 1.5** | **Ideal** |
| 1.6 – 2.0 | Fácil |
| > 2.0 | Trivial |

---

## Tabla de referencia por nivel

| Nivel | Monstruos/sala | Tipos sugeridos | Poder enemigo aprox. |
|-------|----------------|-----------------|----------------------|
| 1 | 2-3 | Trasgos, Esqueletos | 8-15 |
| 2 | 3-4 | Orcos, Zombis | 15-22 |
| 3 | 3-5 | Orcos con escudo, Momias | 22-32 |
| 4 | 4-6 | Fimir, Guerreros del Caos | 30-45 |
| 5+ | 5-8 | Gárgolas, Abominaciones | 40-60+ |

---

## Stats de referencia (monstruos)

| Monstruo | Ataque | Defensa | Cuerpo | Poder (A+D) |
|----------|--------|---------|--------|-------------|
| Trasgo | 2 | 1 | 1 | 3 |
| Esqueleto | 3 | 2 | 1 | 5 |
| Zombi | 2 | 2 | 1 | 4 |
| Orco | 2 | 2 | 1 | 4 |
| Momia | 3 | 3 | 2 | 6 |
| Fimir | 3 | 3 | 2 | 6 |
| Gárgola | 3 | 4 | 1 | 7 |
| Guerrero del Caos | 4 | 3 | 2 | 7 |
| Abominación | 3 | 3 | 3 | 6 |
| Guerrero del Terror | 4 | 3 | 2 | 7 |

---

## Ajustes situacionales

Multiplicadores al Poder_enemigo según contexto:

| Situación | Multiplicador |
|-----------|---------------|
| Emboscada (los héroes entran a una sala llena) | ×1.3 |
| Puente estrecho / paso de 1 casilla | ×1.2 |
| Trampas activadas previamente | ×0.8 |
| Héroes heridos (media Cu < 50%) | ×1.2 |
| Monstruos en terreno ventajoso | ×1.1 |

---

## Ejemplo práctico

**Misión nivel 2, 3 salas, grupo base (Poder = 31.5)**

Ratio objetivo: 1.3 → Poder enemigo total = 31.5 / 1.3 ≈ 24.2

- Sala 1: 2 Orcos (4×2=8) + 1 Zombi (4) = 12
- Sala 2: 3 Orcos (4×3=12) + 1 Trasgo (3) = 15  
- Sala 3 (jefe): 2 Fimir (6×2=12) + 1 Momia (6) = 18

Total: 45 / 3 salas ≈ 15 por sala → Ratio = 31.5/15 ≈ 2.1 (fácil)

**Ajuste:** Subir a 3-4 por sala o añadir un Guerrero del Caos en la sala final.

---

## Reglas de oro

1. **Nunca más de 8 monstruos por sala** (se atasca el juego).
2. **La sala final siempre tiene 1 "jefe"** (Guerrero del Caos, Gárgola, etc.).
3. **Alternar tipos**: no poner solo Trasgos (aburrido) ni solo Guerreros del Caos (imposible).
4. **Reservar tesoros buenos** para salas difíciles.
5. **El Mago es clave**: los hechizos rompen encuentros contra grupos numerosos.

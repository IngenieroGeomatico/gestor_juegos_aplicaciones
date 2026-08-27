# Skill: Tienda y Equipamiento

Sugerencias de compra entre misiones. Ayuda al máster a recomendar equipamiento
coherente con el nivel y el presupuesto del grupo.

---

## Presupuesto típico por nivel

| Nivel | Oro por héroe | Total grupo (4 héroes) |
|-------|---------------|------------------------|
| 1 | 100-200 | 400-800 |
| 2 | 200-350 | 800-1400 |
| 3 | 350-500 | 1400-2000 |
| 4 | 500-700 | 2000-2800 |
| 5+ | 700+ | 2800+ |

---

## Catálogo de precios (ver `armas.json`)

### Armas cuerpo a cuerpo
| Arma | Ataque | Coste | Nota |
|------|--------|-------|------|
| Daga | +1 | 25g | Básica, ocultable |
| Espada corta | +2 | 75g | Equilibrada |
| Hacha de batalla | +3 | 100g | Potente |
| Mandoble | +3 | 150g | Requiere fuerza |
| Báculo del mago | +1 | 10g | Para canalizar hechizos |
| Espada de gemas | +3 | 400g | Especial (3 gemas) |

### Armas a distancia
| Arma | Ataque | Coste | Nota |
|------|--------|-------|------|
| Ballesta | +3 | 175g | Ataque a distancia |

### Armaduras
| Armadura | Defensa | Coste | Nota |
|----------|---------|-------|------|
| Yelmo | +1 | 100g | Protege cabeza |
| Escudo | +1 | 200g | Bloquea ataques |
| Armadura de placas | +2 | 400g | Máxima protección |

### Pociones
| Poción | Efecto | Coste |
|--------|--------|-------|
| Poción de curación | +1 Cuerpo | 300g |

---

## Prioridades por clase

| Clase | Primero | Luego | Guardar para |
|-------|---------|-------|--------------|
| **Bárbaro** | Escudo (200g) | Armadura de placas (400g) | Mandoble (150g) |
| **Enano** | Yelmo (100g) | Escudo (200g) | Armadura (400g) |
| **Elfo** | Hacha de batalla (100g) | Ballesta (175g) | Escudo (200g) |
| **Mago** | Nada (guardar oro) | Báculo (10g) | Hechizos (si hubiera tienda) |

---

## Reglas de la tienda

### Límites
- **Máx. 10 items** por personaje (incluyendo equipamiento inicial)
- **Máx. 2 pociones** por héroe (ocupan espacio)
- **Armadura**: solo 1 activa a la vez (no se apilan)
- **Armas**: se pueden llevar varias, pero solo 1 activa en combate

### Disponibilidad
- Las tiendas en pueblos/ciudades tienen **todo el catálogo**
- Tiendas en mazmorras: solo pociones y armas básicas (Daga, Espada corta)
- Mercaderes ambulantes: catálogo limitado, precios +25%

### Reglas de venta
- Vender a mitad de precio (redondear arriba)
- No se pueden vender pociones usadas
- Las armas especiales (Espada de gemas) no se venden

---

## Ejemplo de recomendación

**Grupo nivel 1, 200g por héroe:**

| Héroe | Compra | Coste | Oro restante |
|-------|--------|-------|--------------|
| Bárbaro | Escudo | 200g | 0g |
| Enano | Yelmo | 100g | 100g (guardar) |
| Elfo | Hacha de batalla | 100g | 100g (guardar) |
| Mago | Nada | 0g | 200g (guardar) |

**Grupo nivel 3, 400g por héroe:**

| Héroe | Compra | Coste | Oro restante |
|-------|--------|-------|--------------|
| Bárbaro | Armadura de placas | 400g | 0g |
| Enano | Escudo | 200g | 200g |
| Elfo | Ballesta | 175g | 225g |
| Mago | Báculo | 10g | 390g |

---

## Errores comunes

| Error | Cómo evitarlo |
|-------|---------------|
| Recomendar objeto que no existe | Consultar `armas.json` siempre |
| Exceder presupuesto | Sumar costes antes de sugerir |
| Poner armadura a dos personajes | Solo 1 armadura activa por héroe |
| Olvidar que el Mago no necesita armas | Su fuerza es la magia |
| Dar tesoros en la tienda | Los tesoros se encuentran, no se compran |

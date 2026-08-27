# Skill: Crear Misión

Genera misiones coherentes y equilibradas para HeroQuest. Cada misión debe ser
**autocontenida** (todo lo que el máster necesita en una sola ficha).

---

## Estructura obligatoria

Toda misión debe tener estos campos (coherentes con `misiones.json`):

```json
{
  "nombre": "string — evocador y descriptivo",
  "tablero": "string — 'original' o 'cara-b'",
  "nivel": "int — 1 a 5",
  "introduccion": "string — 2-3 frases ambientando la situación",
  "objetivo": "string — qué deben hacer los héroes",
  "recompensa": "string — oro/objetos al completar",
  "entrada_heroes": [{"x": int, "y": int}],
  "puertas": [{"x": int, "y": int}],
  "salas": [{
    "numero": "int — número de sala en el tablero",
    "nombre": "string — nombre evocador",
    "descripcion": "string — 1-2 frases descriptivas",
    "monstruos": [{"nombre": "string", "x": int, "y": int}],
    "tesoros": [{"nombre": "string", "x": int, "y": int}]
  }]
}
```

---

## Flujo de creación

### 1. Preguntar al usuario (si no especifica)

- **¿Qué tono?** (aventura, terror, misterio, rescate, exploración)
- **¿Qué nivel?** (1=fácil, 3=medio, 5=jefe final)
- **¿Qué tablero?** (original=22 salas, cara-b=19 salas)
- **¿Algún monstruo concreto?** (ej. "quiero un Fimir como jefe")

### 2. Seleccionar salas del tablero

```python
from tools.datos import tablero_por_id
tablero = tablero_por_id("original")
# tablero["salas"] → lista de salas con sus rects
```

**Criterios de selección:**
- Sala 1: cerca de la entrada (habitación inicial)
- Salas intermedias: configuración lineal o ramificada
- Sala final: la más alejada o protegida (sala del jefe)

### 3. Distribuir monstruos (ver skill balancear_combate)

```python
from tools.misiones import sugerir_monstruos, sugerir_tesoro
monstruos = sugerir_monstruos(nivel=2, n_salas=3)
tesoros = sugerir_tesoro(nivel=2)
```

### 4. Asignar coordenadas

**Reglas:**
- Las coordenadas son **globales** del tablero (columna x de 1..26, fila y de 1..19)
- Cada monstruo/tesoro debe estar **DENTRO** de su sala (comprobar con `sala_pertenece`)
- Entrada de héroes: casillas libres cerca de la sala 1
- Puertas: en las paredes entre salas (consultar tablero)

### 5. Escribir narrativa

Ver skill `narrativa.md` para ambientación.

### 6. Validar

```python
from tools.mapas import validar_mision
resultado = validar_mision("Nombre de la misión")
assert resultado["valida"]
```

---

## Ejemplo de misión nivel 1

```json
{
  "nombre": "La Maldición del Poço",
  "tablero": "original",
  "nivel": 1,
  "introduccion": "Un pueblerino os ha narrado que de un pozo abandonado emanan lamentos. Algo espera en las profundidades.",
  "objetivo": "Explora el pozo y derrota a la criatura que lo habita.",
  "recompensa": "150 monedas de oro y una poción de curación.",
  "entrada_heroes": [{"x": 14, "y": 2}],
  "puertas": [{"x": 6, "y": 5}],
  "salas": [
    {
      "numero": 1,
      "nombre": "La Entrada",
      "descripcion": "Escaleras de piedra descienden a una sala húmeda. El aire huele a humedad y podrido.",
      "monstruos": [
        {"nombre": "Trasgo", "x": 3, "y": 3},
        {"nombre": "Trasgo", "x": 4, "y": 4}
      ],
      "tesoros": []
    },
    {
      "numero": 8,
      "nombre": "La Cámara del Poço",
      "descripcion": "Un pozo negro domina el centro. Algo brilla en el fondo.",
      "monstruos": [
        {"nombre": "Orco", "x": 8, "y": 7}
      ],
      "tesoros": [
        {"nombre": "Poción de curación", "x": 9, "y": 8}
      ]
    }
  ]
}
```

---

## Errores comunes

| Error | Cómo evitarlo |
|-------|---------------|
| Coordenada fuera del tablero | Usar `punto_valido()` antes de asignar |
| Monstruo fuera de su sala | Usar `sala_pertenece()` para verificar |
| Ratio de poder muy bajo/alto | Usar las fórmulas de balancear_combate |
| Sin recompensa | Siempre dar oro + 0-1 objeto |
| Introducción genérica | Incluir un gancho (¿por qué los héroes van ahí?) |

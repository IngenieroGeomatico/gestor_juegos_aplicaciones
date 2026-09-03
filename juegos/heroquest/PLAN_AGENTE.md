# HeroQuest Agent - Plan de Mejora

## Estructura Propuesta

```
.opencode/
├── agent/
│   └── heroquest.md          # Agente principal (existente)
├── skills/
│   ├── balancear_combate.md   # Skill: equilibrar encuentros
│   ├── crear_mision.md        # Skill: generar misiones
│   ├── narrativa.md           # Skill: ambientación y_roleplay
│   ├── reglas.md              # Skill: consultar reglas canónicas
│   └── tienda.md              # Skill: sugerir equipamiento
├── tools/
│   ├── __init__.py
│   ├── datos.py               # Lectura de JSONs (armas, monstruos, etc.)
│   ├── cartas.py              # Generación de cartas
│   ├── mapas.py               # Generación de mapas
│   └── misiones.py            # Creación/validación de misiones
└── rag/
    ├── chroma_db/             # Base de datos de embeddings
    ├── documentos/            # PDFs y textos indexados
    ├── indexar.py             # Script de indexación
    └── busqueda.py            # Búsqueda semántica
```

---

## 1. Tools (Herramientas)

### 1.1 `tools/datos.py`

```python
"""Herramientas de acceso a datos del juego."""

def listar_personajes() -> list[dict]:
    """Devuelve todos los personajes jugadores."""

def listar_armas() -> list[dict]:
    """Lista todas las armas con stats."""

def listar_monstruos() -> list[dict]:
    """Lista todos los monstruos disponibles."""

def listar_hechizos() -> list[dict]:
    """Lista todos los hechizos por escuela."""

def buscar_item(nombre: str) -> dict | None:
    """Busca un arma/armadura/poción por nombre."""

def estadisticas_grupo() -> dict:
    """Resumen de stats medios del grupo actual."""
```

### 1.2 `tools/cartas.py`

```python
"""Herramientas de generación de cartas."""

def generar_carta(nombre: str, cara: str = "ambas") -> str:
    """Genera PNG de una carta. Devuelve ruta del fichero."""

def listar_cartas_generadas() -> list[str]:
    """Lista cartas ya generadas en cartas/"""
```

### 1.3 `tools/mapas.py`

```python
"""Herramientas de generación de mapas."""

def ver_tablero(tablero: str = "original") -> str:
    """Muestra el tablero en ASCII."""

def generar_mapa_mision(nombre: str) -> str:
    """Genera PNG del mapa de una misión."""

def validar_mision(nombre: str) -> dict:
    """Valida coordenadas de una misión contra su tablero."""
```

### 1.4 `tools/misiones.py`

```python
"""Herramientas de creación de misiones."""

def crear_mision(
    nombre: str,
    tablero: str,
    nivel: int,
    introduccion: str,
    objetivo: str,
    recompensa: str,
    entrada_heroes: list[dict],
    puertas: list[dict],
    salas: list[dict]
) -> dict:
    """Crea una misión completa y la guarda en JSON."""

def sugerir_monstruos(nivel: int, n_salas: int) -> list[dict]:
    """Sugiere distribución de monstruos según nivel."""
```

---

## 2. Skills (Habilidades)

### 2.1 `skills/balancear_combate.md`

```markdown
# Skill: Balancear Combate

Eres un experto en equilibrar encuentros de HeroQuest.

## Fórmulas
- **Poder del grupo** = Σ(Ataque_heroe + Defensa_heroe) × 1.5
- **Poder del encuentro** = Σ(Ataque_monstruo + Defensa_monstruo) × Nº_monstruos
- **Ratio ideal** = Poder_grupo / Poder_encuentro ≈ 1.2 - 1.5

## Reglas por nivel
| Nivel | Monstruos por sala | Tipos sugeridos |
|-------|-------------------|-----------------|
| 1 | 2-3 | Trasgos, Esqueletos |
| 2 | 3-4 | Orcos, Zombis |
| 3 | 3-5 | Orcos con escudo, Momias |
| 4 | 4-6 | Fimir, Guerreros del Caos |
| 5+ | 5-8 | Gárgolas, Abominaciones |

## Ejemplo
Grupo: Bárbaro(A3,D3) + Enano(A3,D4) + Elfo(A2,D3) + Mago(A1,D2)
Poder = (3+3+3+4+2+2) × 1.5 = 25.5
Encuentro ideal: 25.5 / 1.3 ≈ 19.6 de poder enemigo
→ 4 Orcos (A2,D2) = 16 + 1 Trasgo (A2,D1) = 3 → Total: 19 ✓
```

### 2.2 `skills/crear_mision.md`

```markdown
# Skill: Crear Misión

Genera misiones coherentes para HeroQuest.

## Estructura obligatoria
1. **Nombre** - Evocador y descriptivo
2. **Tablero** - "original" o "cara_b" (comprobar disponibilidad)
3. **Nivel** - 1-5 (determina dificultad)
4. **Introducción** - 2-3 frases ambientando
5. **Objetivo** - Qué deben hacer los héroes
6. **Recompensa** - Oro/objetos al completar
7. **Salas** - Con monstruos y tesoros posicionados

## Coordenadas
- Usar sistema de cuadrícula del tablero
- Verificar con `validar_mision()` que todas las salas existen
- Monstruos/tesoros deben estar DENTRO de su sala

## Distribución típica
- Sala 1: Enemigos fáciles + tesoro menor
- Sala 2-3: Enemigos medios
- Sala final: Jefe o grupo difícil + tesoro importante
```

### 2.3 `skills/narrativa.md`

```markdown
# Skill: Narrativa y Ambientación

Eres el narrador de HeroQuest. Tu tono es:
- **Épico** pero accesible (no novela, sí juego de mesa)
- **Descriptivo** en momentos clave (combate, tesoros)
- **Breve** en transiciones (pasillos, puertas)

## Estructura de sala
1. **Al entrar**: descripción visual (2 frases)
2. **Enemigos**: cómo reaccionan al ver héroes
3. **Combate**: narrar golpes críticos (dados de 6)
4. **Tras combate**: qué queda, tesoros, pistas

## Ejemplo
> Al cruzar la puerta, el olor a podrido os golpea.
> Tres esqueletos giran sus cráneos vacíos hacia vosotros,
> levantando espadas oxidadas. ¡Preparaos!
```

### 2.4 `skills/reglas.md`

```markdown
# Skill: Reglas de HeroQuest

Consultorio de reglas canónicas.

## Sistema de dados
- **Ataque**: dados rojos (cara negra = hit)
- **Defensa**: dados azules (escudo = bloque)
- 1-3 dados según arma/estadística

## Puntos
- **Cuerpo (Cu)**: vida física. 0 = muerte
- **Mente (Me)**: resistencia mental. 0 = atontado
- **Movimiento**: casillas por turno

## Combate
1. Héroe ataca → tira dados de ataque
2. Monstruo defiende → tira dados de defensa
3. Golpes = Atacados - Bloqueados (mín. 0)
4. Restar al Cuerpo del objetivo

## Magia
- Solo el Mago lanza hechizos
- Gasta Puntos de Mente según coste
- Hechizos hostiles: víctima gasta 1 Me para resistir
```

### 2.5 `skills/tienda.md`

```markdown
# Skill: Tienda y Equipamiento

Sugerencias de compra entre misiones.

## Presupuesto típico
- Nivel 1: 100-200 oro por héroe
- Nivel 2: 200-350 oro
- Nivel 3+: 350-500 oro

## Prioridades por clase
| Clase | Primero | Luego |
|-------|---------|-------|
| Bárbaro | Escudo (200) | Armadura (400) |
| Enano | Yelmo (100) | Escudo (200) |
| Elfo | Arma mejor (150) | Escudo (200) |
| Mago | Nada (guardar oro) | - |

## Regla de oro
- No recomendar objetos que no existan en equipo.json
- Respetar límite de 10 items por personaje
- Poções: máx. 2 por héroe (ocupan espacio)
```

---

## 3. RAG (Retrieval-Augmented Generation)

### 3.1 Fuentes de datos (HeroQuester.eu)

| Fuente | Enlace | Tipo | Prioridad |
|--------|--------|------|-----------|
| **Libro de reglas HeroQuest** | [Manual](https://drive.google.com/file/d/18zlEFaKQNMMMDnEEbMVq0LUD4mwuUcJr/view) | Rules | 🔴 Alta |
| **Libro de reglas AHQ** | [Compendio AHQ](https://drive.google.com/drive/folders/1kohbUfbFFNFqtQCaSxrSxJpN4f3y6_AY/view) | Rules | 🟡 Media |
| **Juego Base - Libro de misiones** | [Misiones](https://drive.google.com/file/d/10y6gKUobO_mSaSH0DzYIQ726xYTTaAPh/view) | Adventures | 🔴 Alta |
| **Cartas del juego base** | [Cartas](https://drive.google.com/file/d/1aPgtbgNzAlkejntAaV-W4vfMIiWJDypS/view) | Cards | 🔴 Alta |
| **Alquimia (expansión)** | [Pack completo](https://drive.google.com/file/d/1gU9L7S3gPApbLuzaPWrLiGim6c189EAw/view) | Expansion | 🟡 Media |
| **La Compañía Tenebrosa** | [Libro misiones](https://drive.google.com/file/d/12CVL0snFbC27-NJrwHpWtnYVzU3boqxD/view) | Adventure | 🟢 Baja |
| **FetenQuest (sistema avanzado)** | [Sistema](https://drive.google.com/open?id=1-Um4LwTVY3I6fQzspw5uKNP2uHgJ_YYb) | System | 🟢 Baja |
| **Wizard Quest 1993** | [Aventura inédita](https://drive.google.com/drive/folders/1KOa02SqdO92Z3DFLhZe0XJKOPL-6vnR2) | Adventure | 🟢 Baja |
| **Misiones online** | [Libro misiones](https://drive.google.com/file/d/1CV4OynLgL1st6WCwcqGXOxQ964nk17z-/view) | Adventures | 🟡 Media |
| **Cartas FanMade** | [Cartas](https://drive.google.com/file/d/1C99ZdrnC0C96o2GiDZbSrD3XQ7Z78kG1/view) | Cards | 🟢 Baja |

### 3.2 Repositorio de Google Drive organizado

```
HeroQuester.eu Downloads/
├── 01_Reglas/
│   ├── manual_heroquest_2021.pdf
│   ├── compendio_ahq.pdf
│   └── wizard_quest_1993.pdf
├── 02_Misiones/
│   ├── juego_base/
│   ├── la_torre_de_kellar/
│   ├── la_profecia_de_telor/
│   └── ... (expansiones)
├── 03_Cartas/
│   ├── cartas_base.pdf
│   ├── cartas_fanmade.pdf
│   └── cartas_expansiones/
└── 04_Expansiones/
    ├── alquimia/
    ├── compania_tenebrosa/
    └── ...
```

### 3.3 Indexación

```bash
# Indexar PDF del manual
uv run rag/indexar.py --fuente manual_heroquest.pdf

# Indexar web de HeroQuester
uv run rag/indexar.py --url https://heroquester.eu/archivos

# Buscar
uv run rag/busqueda.py "¿cómo funcionan las trampas?"
```

### 3.3 Embeddings

```python
# Modelo recomendado (español, rápido)
model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ChromaDB como almacén
import chromadb
client = chromadb.PersistentClient(path="rag/chroma_db")
collection = client.get_or_create_collection("heroquest_rules")
```

### 3.4 Ejemplo de uso

```python
# En el agente
resultado = rag.buscar("reglas de combate cuerpo a cuerpo")
# → "En combate cuerpo a cuerpo, el atacante tira dados de ataque rojos..."
```

### 3.5 Enlaces descubiertos (HeroQuester.eu)

**Manuales de reglas:**
- Manual HeroQuest 2021: `18zlEFaKQNMMMDnEEbMVq0LUD4mwuUcJr`
- Compendio AHQ: `1kohbUfbFFNFqtQCaSxrSxJpN4f3y6_AY`
- Wizard Quest 1993: `1KOa02SqdO92Z3DFLhZe0XJKOPL-6vnR2`

**Cartas:**
- Cartas juego base: `1aPgtbgNzAlkejntAaV-W4vfMIiWJDypS`
- Cartas FanMade: `1C99ZdrnC0C96o2GiDZbSrD3XQ7Z78kG1`

**Misiones:**
- Libro misiones base: `10y6gKUobO_mSaSH0DzYIQ726xYTTaAPh`
- Misiones online: `1CV4OynLgL1st6WCwcqGXOxQ964nk17z-`

**Expansiones:**
- Alquimia completo: `1gU9L7S3gPApbLuzaPWrLiGim6c189EAw`
- La Compañía Tenebrosa: `1rb0v83LmhNlspp0rM5rmMzOedz4P6jaQ`

---

## 4. Integración con opencode

### 4.1 Configurar tools en `opencode.json`

```json
{
  "agent": {
    "heroquest": {
      "skills": ["skills/balancear_combate.md", "skills/narrativa.md"],
      "tools": ["tools/datos.py", "tools/cartas.py", "tools/misiones.py"]
    }
  }
}
```

### 4.2 Flujo típico

```
Usuario: "Crea una misión nivel 2 en el tablero original"

Agente:
1. [tool] listar_monstruos() → ve qué hay disponible
2. [skill] crear_mision.md → sigue la estructura
3. [tool] sugerir_monstruos(2, 3) → distribución
4. [tool] validar_mision() → verifica coordenadas
5. [tool] generar_mapa_mision() → crea PNG
6. Responde con la misión completa + mapa
```

---

## 5. Orden de implementación

| Fase | Tiempo | Contenido |
|------|--------|-----------|
| **1** | 1-2 días | Tools de datos (lectura JSON) |
| **2** | 1 día | Skills básicos (reglas, narrativa) |
| **3** | 2-3 días | Tools de cartas/mapas |
| **4** | 3-5 días | RAG con PDF del manual |
| **5** | 2-3 días | Skills avanzados (balance, tienda) |

---

## 6. Pendiente

- [ ] Obtener PDF del manual de reglas
- [ ] Decidir modelo de embeddings
- [ ] Diseñar prompts de cada skill
- [ ] Implementar tools de acceso a datos
- [ ] Configurar ChromaDB
- [ ] Test de integración completa

### 6.1 Pendientes visuales Misión 1 (La Fortaleza Fronteriza de In-Gulden)

- [ ] **Salida**: no se ve bien en el mapa. Revisar el marcador/gliifo de la salida trasera de la fortaleza (puerta secreta [9,18]-[10,18]) y mejorar su representación.
- [ ] **Rocas / pasajes intransitables**: las rocas y zonas por las que no se puede pasar no se distinguen bien. Revisar cómo se pintan (probablemente como pasillo) y darles un aspecto diferenciado que comunique que son intransitables.
- [ ] Revisar el icono "F" / marcadores de exploradores caídos del mapa (señalado en sesiones previas).
- [ ] Generar los 3 iconos de héroes que faltan (Enana, Elfo, Elfa) en `sources/arte_iconos/`.
- [ ] Generar plantillas/arte para los 21 hechizos nuevos, tesoros y artefactos (hoy el render falla con `ValueError: ... no declara plantillas.cara.plantilla_padre`).

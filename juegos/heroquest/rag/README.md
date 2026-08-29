# HeroQuest - RAG (búsqueda sobre documentos)

Sistema de búsqueda sobre el material de HeroQuest (reglas, misiones, cartas y
expansiones) para apoyar al agente a la hora de generar contenido coherente.

**Implementación recomendada: TF-IDF + SQLite** (`indexar_lite.py` /
`busqueda_lite.py`) con la **sola biblioteca estándar** (re, unicodedata, math,
sqlite3): sin numpy, scipy ni sklearn, consume ~20 MB de RAM y cabe en cualquier
equipo. Se conserva una alternativa pesada con ChromaDB + sentence-transformers
(`indexar.py` / `busqueda.py`).

## Flujo

1. **Descargar** el material: `rag/descargar_fuentes.py` lee el registro de
   `juegos/heroquest/data/fuentes.json` (IDs de Google Drive) y descarga los
   PDFs organizados por expansión en `rag/documentos/`.
2. **Indexar**: `rag/indexar_lite.py` extrae el texto de cada PDF (pymupdf, con
   OCR si el documento está escaneado), lo divide en chunks y lo guarda en
   `rag/chroma_db_lite/heroquest.db`. El TF-IDF es esparso: `chunks.terms`
   guarda `"fid:tf;"` por chunk y `doc_terms` registra en qué documentos aparece
   cada término, de modo que la IDF es **siempre global** aunque se indexe de
   forma incremental (--documento / --directorio).
3. **Buscar**: `rag/busqueda_lite.py` vectoriza la consulta y recorre los chunks
   calculando la similitud de coseno en streaming (un chunk en RAM por
   iteración).

## Uso (desde la raíz del repositorio)

```bash
# Ver las fuentes registradas en data/fuentes.json sin descargar
uv run juegos/heroquest/rag/descargar_fuentes.py --listar
uv run juegos/heroquest/rag/descargar_fuentes.py --listar --categoria Reglas

# Descargar PDFs a rag/documentos/<Expansión>/
uv run juegos/heroquest/rag/descargar_fuentes.py
uv run juegos/heroquest/rag/descargar_fuentes.py --prioridad alta

# Indexar (--documento, --directorio o --todo)
uv run juegos/heroquest/rag/indexar_lite.py --todo
uv run juegos/heroquest/rag/indexar_lite.py --documento juegos/heroquest/rag/documentos/Juego_Base/manual.pdf
uv run juegos/heroquest/rag/indexar_lite.py --directorio juegos/heroquest/rag/documentos/reglas

# Buscar
uv run juegos/heroquest/rag/busqueda_lite.py "¿cómo funcionan las trampas en HeroQuest?" --top 5
```

## Estructura

```
rag/
├── descargar_fuentes.py   # descarga PDFs desde data/fuentes.json (gdown)
├── tokenizar.py           # tokenización compartida (stdlib: re, unicodedata)
├── indexar_lite.py        # indexación TF-IDF → SQLite (recomendado, stdlib)
├── busqueda_lite.py       # búsqueda por similitud de coseno (recomendado, stdlib)
├── indexar.py             # alternativas pesadas: ChromaDB + sentence-transformers
├── busqueda.py
├── documentos/            # PDFs descargados por expansión (ignorados por git)
│   └── <Expansión>/*.pdf
└── chroma_db_lite/        # SQLite (generado; ignorado por git)
    └── heroquest.db
```

> `rag/documentos/` y `rag/chroma_db_lite/` se generan y son grandes, por eso no
> viajan en el repositorio. El registro canónico del material (con categoría,
> expansión, prioridad y licencias) es `juegos/heroquest/data/fuentes.json`.

## Licencia

El material de HeroQuester.eu es fan-made y de uso gratuito para la comunidad.
Créditos: [HeroQuester.eu](https://heroquester.eu)

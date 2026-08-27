# HeroQuest - Fuentes de Datos para RAG

## Descarga de Material

### Script de descarga
```bash
uv run descargar_fuentes.py
```

### Fuentes principales

| # | Fuente | Enlace | Uso en RAG |
|---|--------|--------|------------|
| 1 | **Libro de reglas HeroQuest** | [PDF](https://drive.google.com/file/d/18zlEFaKQNMMMDnEEbMVq0LUD4mwuUcJr/view) | Reglas canónicas |
| 2 | **Cartas del juego base** | [PDF](https://drive.google.com/file/d/1aPgtbgNzAlkejntAaV-W4vfMIiWJDypS/view) | Stats de items/hechizos |
| 3 | **Libro de misiones base** | [PDF](https://drive.google.com/file/d/10y6gKUobO_mSaSH0DzYIQ726xYTTaAPh/view) | Estructura de aventuras |
| 4 | **Compendio AHQ** | [Carpeta](https://drive.google.com/drive/folders/1kohbUfbFFNFqtQCaSxrSxJpN4f3y6_AY) | Reglas avanzadas |
| 5 | **Alquimia (expansión)** | [PDF](https://drive.google.com/file/d/1gU9L7S3gPApbLuzaPWrLiGim6c189EAw/view) | Sistema de alquimia |

### Estructura de directorios

```
juegos/heroquest/rag/
├── documentos/              # PDFs descargados
│   ├── reglas/
│   ├── misiones/
│   ├── cartas/
│   └── expansiones/
├── chroma_db/               # Base de embeddings
├── descargas/               # PDFs originales
├── descargar_fuentes.py     # Script de descarga
├── indexar.py               # Indexación a ChromaDB
└── busqueda.py              # Búsqueda semántica
```

## Uso

### 1. Descargar material
```bash
cd juegos/heroquest
uv run rag/descargar_fuentes.py
```

### 2. Indexar documentos
```bash
uv run rag/indexar.py --documento documentos/reglas/manual.pdf
# O indexar todo:
uv run rag/indexar.py --todo
```

### 3. Buscar información
```bash
uv run rag/busqueda.py "¿cómo funcionan las trampas en HeroQuest?"
```

## Licencia

El material de HeroQuester.eu es fan-made y de uso gratuito para la comunidad.
Créditos: [HeroQuester.eu](https://heroquester.eu)

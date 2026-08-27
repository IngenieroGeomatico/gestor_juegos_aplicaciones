"""Indexa documentos PDF en ChromaDB para búsqueda semántica.

Uso:
    uv run indexar.py --documento reglas/manual.pdf
    uv run indexar.py --directorio reglas/
    uv run indexar.py --todo
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Intentar importar dependencias, instalar si faltan
try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "chromadb", "sentence-transformers"], check=True)
    import chromadb
    from sentence_transformers import SentenceTransformer

# Configuración
DB_DIR = Path(__file__).parent / "chroma_db"
DOCS_DIR = Path(__file__).parent / "documentos"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

# Chunk size para dividir documentos
CHUNK_SIZE = 500  # caracteres
CHUNK_OVERLAP = 50


def _cargar_modelo() -> SentenceTransformer:
    """Carga el modelo de embeddings."""
    print(f"Cargando modelo {MODELO_EMBEDDINGS}...")
    return SentenceTransformer(MODELO_EMBEDDINGS)


def _dividir_texto(texto: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Divide el texto en chunks para indexación."""
    chunks = []
    palabras = texto.split()
    chunk_actual = []
    tamano_actual = 0
    
    for palabra in palabras:
        if tamano_actual + len(palabra) + 1 > chunk_size and chunk_actual:
            chunks.append(" ".join(chunk_actual))
            # Mantener overlap
            overlap_words = chunk_actual[-10:]  # Últimas 10 palabras
            chunk_actual = overlap_words
            tamano_actual = sum(len(w) for w in overlap_words)
        
        chunk_actual.append(palabra)
        tamano_actual += len(palabra) + 1
    
    if chunk_actual:
        chunks.append(" ".join(chunk_actual))
    
    return chunks


def indexar_documento(ruta: Path, modelo: SentenceTransformer, collection) -> int:
    """Indexa un documento PDF en ChromaDB."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        import subprocess
        subprocess.run(["uv", "pip", "install", "PyMuPDF"], check=True)
        import fitz
    
    print(f"Indexando: {ruta.name}")
    
    doc = fitz.open(str(ruta))
    chunks_indexados = 0
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        texto = page.get_text()
        
        if not texto.strip():
            continue
        
        chunks = _dividir_texto(texto)
        
        for i, chunk in enumerate(chunks):
            # Generar embedding
            embedding = modelo.encode(chunk).tolist()
            
            # Guardar en ChromaDB
            collection.add(
                ids=[f"{ruta.stem}_p{page_num}_c{i}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "fuente": str(ruta),
                    "pagina": page_num + 1,
                    "chunk": i,
                }]
            )
            chunks_indexados += 1
    
    doc.close()
    print(f"  → {chunks_indexados} chunks indexados")
    return chunks_indexados


def indexar_directorio(directorio: Path, modelo: SentenceTransformer, collection) -> int:
    """Indexa todos los PDFs de un directorio."""
    total = 0
    for pdf in directorio.glob("*.pdf"):
        total += indexar_documento(pdf, modelo, collection)
    return total


def indexar_todo(modelo: SentenceTransformer, collection) -> int:
    """Indexa todos los documentos de todas las categorías."""
    total = 0
    for subdir in DOCS_DIR.iterdir():
        if subdir.is_dir():
            total += indexar_directorio(subdir, modelo, collection)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexa documentos HeroQuest en ChromaDB")
    parser.add_argument("--documento", help="Ruta al PDF a indexar")
    parser.add_argument("--directorio", help="Directorio con PDFs a indexar")
    parser.add_argument("--todo", action="store_true", help="Indexar todo")
    args = parser.parse_args()
    
    if not args.documento and not args.directorio and not args.todo:
        parser.error("Especifica --documento, --directorio o --todo")
    
    # Crear directorio de DB
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    # Inicializar ChromaDB
    client = chromadb.PersistentClient(path=str(DB_DIR))
    collection = client.get_or_create_collection(
        name="heroquest_rules",
        metadata={"hnsw:space": "cosine"}
    )
    
    # Cargar modelo
    modelo = _cargar_modelo()
    
    # Indexar
    if args.documento:
        ruta = Path(args.documento)
        if not ruta.exists():
            print(f"No existe: {ruta}")
            return
        indexar_documento(ruta, modelo, collection)
    elif args.directorio:
        dir_path = Path(args.directorio)
        if not dir_path.exists():
            print(f"No existe: {dir_path}")
            return
        indexar_directorio(dir_path, modelo, collection)
    elif args.todo:
        indexar_todo(modelo, collection)
    
    print(f"\n✅ Indexación completada. Total en DB: {collection.count()} chunks")


if __name__ == "__main__":
    main()

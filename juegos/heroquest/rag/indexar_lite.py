"""Indexación ligera de documentos PDF usando TF-IDF + SQLite.

Alternativa ligera a ChromaDB + sentence-transformers.

Uso:
    uv run indexar_lite.py --documento reglas/manual.pdf
    uv run indexar_lite.py --directorio reglas/
    uv run indexar_lite.py --todo
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

# Configuración
DB_DIR = Path(__file__).parent / "chroma_db_lite"
DOCS_DIR = Path(__file__).parent / "documentos"
DB_PATH = DB_DIR / "heroquest.db"
VECTORIZER_PATH = DB_DIR / "vectorizer.pkl"

# Chunk size
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _dividir_texto(texto: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Divide el texto en chunks."""
    chunks = []
    palabras = texto.split()
    chunk_actual = []
    tamano_actual = 0
    
    for palabra in palabras:
        if tamano_actual + len(palabra) + 1 > chunk_size and chunk_actual:
            chunks.append(" ".join(chunk_actual))
            overlap_words = chunk_actual[-10:]
            chunk_actual = overlap_words
            tamano_actual = sum(len(w) for w in overlap_words)
        
        chunk_actual.append(palabra)
        tamano_actual += len(palabra) + 1
    
    if chunk_actual:
        chunks.append(" ".join(chunk_actual))
    
    return chunks


def _crear_db() -> sqlite3.Connection:
    """Crea la base de datos SQLite."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            documento TEXT,
            pagina INTEGER,
            chunk INTEGER,
            texto TEXT,
            tfidf_vector TEXT
        )
    """)
    conn.commit()
    return conn


def _extraer_texto_pdf(ruta: Path) -> list[tuple[int, str]]:
    """Extrae texto de un PDF página a página. Usa OCR si es escaneado."""
    try:
        import pymupdf
    except ImportError:
        import subprocess
        subprocess.run(["uv", "pip", "install", "pymupdf"], check=True)
        import pymupdf
    
    doc = pymupdf.open(str(ruta))
    paginas = []
    es_escaneado = False
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        texto = page.get_text()
        
        # Si no hay texto, intentar OCR
        if not texto.strip():
            es_escaneado = True
            try:
                tp = page.get_textpage_ocr()
                texto = tp.extractText()
            except:
                pass
        
        if texto.strip():
            paginas.append((page_num + 1, texto))
    
    doc.close()
    
    if es_escaneado and not paginas:
        print(f"  ⚠️  PDF escaneado detectado. Necesita OCR.")
        print(f"     Instala tesseract: sudo apt install tesseract-ocr tesseract-ocr-spa")
    
    return paginas


def _calcular_tfidf(textos: list[str]) -> tuple[list[str], list[list[float]], object]:
    """Calcula TF-IDF para una lista de textos."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np
    
    vectorizer = TfidfVectorizer(
        max_features=1000,
        stop_words=None,
        ngram_range=(1, 2)
    )
    
    tfidf_matrix = vectorizer.fit_transform(textos)
    feature_names = vectorizer.get_feature_names_out()
    
    return feature_names.tolist(), tfidf_matrix.toarray().tolist(), vectorizer


def indexar_documento(ruta: Path, conn: sqlite3.Connection) -> int:
    """Indexa un documento PDF."""
    import pickle
    
    print(f"Indexando: {ruta.name}")
    
    paginas = _extraer_texto_pdf(ruta)
    chunks_totales = []
    metadatas = []
    
    for page_num, texto in paginas:
        chunks = _dividir_texto(texto)
        for i, chunk in enumerate(chunks):
            chunks_totales.append(chunk)
            metadatas.append({
                "fuente": str(ruta),
                "pagina": page_num,
                "chunk": i
            })
    
    if not chunks_totales:
        print(f"  → 0 chunks (documento vacío)")
        return 0
    
    # Calcular TF-IDF
    print(f"  Calculando TF-IDF para {len(chunks_totales)} chunks...")
    _, tfidf_vectors, vectorizer = _calcular_tfidf(chunks_totales)
    
    # Guardar vectorizer
    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)
    
    # Guardar en SQLite
    for idx, (chunk, metadata, vector) in enumerate(zip(chunks_totales, metadatas, tfidf_vectors)):
        chunk_id = f"{ruta.stem}_p{metadata['pagina']}_c{metadata['chunk']}"
        conn.execute(
            "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            (chunk_id, metadata["fuente"], metadata["pagina"], 
             metadata["chunk"], chunk, json.dumps(vector))
        )
    
    conn.commit()
    print(f"  → {len(chunks_totales)} chunks indexados")
    return len(chunks_totales)


def indexar_directorio(directorio: Path, conn: sqlite3.Connection) -> int:
    """Indexa todos los PDFs de un directorio."""
    total = 0
    for pdf in directorio.glob("*.pdf"):
        total += indexar_documento(pdf, conn)
    return total


def indexar_todo(conn: sqlite3.Connection) -> int:
    """Indexa todos los documentos."""
    total = 0
    for subdir in DOCS_DIR.iterdir():
        if subdir.is_dir():
            total += indexar_directorio(subdir, conn)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexación ligera de HeroQuest (TF-IDF + SQLite)")
    parser.add_argument("--documento", help="Ruta al PDF")
    parser.add_argument("--directorio", help="Directorio con PDFs")
    parser.add_argument("--todo", action="store_true", help="Indexar todo")
    args = parser.parse_args()
    
    if not args.documento and not args.directorio and not args.todo:
        parser.error("Especifica --documento, --directorio o --todo")
    
    conn = _crear_db()
    
    if args.documento:
        ruta = Path(args.documento)
        if not ruta.exists():
            print(f"No existe: {ruta}")
            return
        indexar_documento(ruta, conn)
    elif args.directorio:
        dir_path = Path(args.directorio)
        if not dir_path.exists():
            print(f"No existe: {dir_path}")
            return
        indexar_directorio(dir_path, conn)
    elif args.todo:
        indexar_todo(conn)
    
    # Contar total
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n✅ Indexación completada. Total: {total} chunks en {DB_PATH}")


if __name__ == "__main__":
    main()

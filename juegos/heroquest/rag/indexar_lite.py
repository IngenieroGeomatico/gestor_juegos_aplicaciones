# -*- coding: utf-8 -*-
"""Indexación ligera de documentos PDF usando TF-IDF + SQLite (solo stdlib).

Alternativa ligera a ChromaDB y a sklearn: la tokenización, el TF-IDF y la
búsqueda se calculan con la biblioteca estándar (`re`, `unicodedata`, `math`,
`sqlite3`). No requiere numpy, scipy ni sklearn, así que cabe en equipos con
poca RAM. El índice esparso se guarda en `rag/chroma_db_lite/heroquest.db`.

El TF-IDF se guarda en dos piezas para que la IDF SIEMPRE sea global y
coherente aunque se añadan documentos de forma incremental:

- `chunks.terms`   → "fid:tf;"  (tf = 1 + log(frecuencia) por chunk)
- `doc_terms`      → (doc, fid) para derivar la df y la IDF globales

Uso:
    uv run juegos/heroquest/rag/indexar_lite.py --documento <pdf>
    uv run juegos/heroquest/rag/indexar_lite.py --directorio <dir>
    uv run juegos/heroquest/rag/indexar_lite.py --todo
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from collections import Counter
from pathlib import Path

import tokenizar

# Configuración
DB_DIR = Path(__file__).parent / "chroma_db_lite"
DOCS_DIR = Path(__file__).parent / "documentos"
DB_PATH = DB_DIR / "heroquest.db"

# Tamaño de chunk (en caracteres) y solape entre chunks
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

_TABLAS = ("chunks", "terms", "doc_terms")
_ESQUEMA_VERSION = "2"


def _dividir_texto(texto: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Divide el texto en chunks por palabras con un pequeño solape."""
    chunks: list[str] = []
    palabras = texto.split()
    chunk_actual: list[str] = []
    tamano_actual = 0

    for palabra in palabras:
        if tamano_actual + len(palabra) + 1 > chunk_size and chunk_actual:
            chunks.append(" ".join(chunk_actual))
            solape = chunk_actual[-10:]
            chunk_actual = solape
            tamano_actual = sum(len(p) for p in solape)

        chunk_actual.append(palabra)
        tamano_actual += len(palabra) + 1

    if chunk_actual:
        chunks.append(" ".join(chunk_actual))

    return chunks


def _crear_db() -> sqlite3.Connection:
    """Crea la base de datos (rebuild incluido si el esquema no es el actual)."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))

    version = None
    tabs = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "meta" in tabs:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave = 'schema_version'").fetchone()
        version = row[0] if row else None

    # El esquema v1 (sklearn) y el primer intento del v2 tenían doc_terms con
    # PRIMARY KEY (doc) en vez de (doc, termo): se reconstruye sin más.
    if tabs and version != _ESQUEMA_VERSION:
        print("  → Esquema antiguo detectado; se reconstruye el índice.")
        for tabla in ("meta", *_TABLAS):
            conn.execute(f"DROP TABLE IF EXISTS {tabla}")
        conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO meta (clave, valor) VALUES ('schema_version', ?)",
        (_ESQUEMA_VERSION,))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS terms (
            termo TEXT PRIMARY KEY,
            fid   INTEGER UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doc_terms (
            doc   TEXT,
            termo INTEGER,
            frec  INTEGER,
            PRIMARY KEY (doc, termo)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id        TEXT PRIMARY KEY,
            documento TEXT,
            pagina    INTEGER,
            chunk     INTEGER,
            texto     TEXT,
            terms     TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(documento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_terms_termo ON doc_terms(termo)")
    conn.commit()
    return conn


def _extraer_texto_pdf(ruta: Path) -> list[tuple[int, str]]:
    """Extrae texto de un PDF página a página. Usa OCR si está escaneado."""
    try:
        import pymupdf
    except ImportError:
        import subprocess
        subprocess.run(["uv", "pip", "install", "pymupdf"], check=True)
        import pymupdf

    doc = pymupdf.open(str(ruta))
    paginas: list[tuple[int, str]] = []
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
            except Exception:
                pass

        if texto.strip():
            paginas.append((page_num + 1, texto))

    doc.close()

    if es_escaneado and not paginas:
        print("  ⚠️  PDF escaneado detectado. Necesita OCR.")
        print("     Instala tesseract: sudo apt install tesseract-ocr tesseract-ocr-spa")

    return paginas


def _guardar_terms(conn: sqlite3.Connection, terminos: set[str]) -> dict[str, int]:
    """Garantiza los términos en la tabla y devuelve el mapa termo → fid.

    El `fid` es el rowid de la tabla (asignado por SQLite al insertar).
    """
    mapa: dict[str, int] = {}
    for termo in terminos:
        fila = conn.execute(
            "SELECT fid FROM terms WHERE termo = ?", (termo,)).fetchone()
        if fila is not None:
            mapa[termo] = fila[0]
        else:
            fid = conn.execute(
                "INSERT INTO terms (termo) VALUES (?)", (termo,)).lastrowid
            conn.execute("UPDATE terms SET fid = ? WHERE termo = ?", (fid, termo))
            mapa[termo] = fid
    return mapa


def indexar_documento(ruta: Path, conn: sqlite3.Connection) -> int:
    """Indexa un documento PDF completo: actualiza df y chunks."""
    print(f"Indexando: {ruta.name}")
    doc_id = str(ruta)

    paginas = _extraer_texto_pdf(ruta)
    if not paginas:
        return 0

    # (chunk_id, pagina, chunk, texto, Counter de términos) de todo el doc
    filas: list[tuple[str, int, int, str, Counter[str]]] = []
    for page_num, texto in paginas:
        for i, chunk in enumerate(_dividir_texto(texto)):
            terminos = Counter(tokenizar.tokenizar(chunk))
            if terminos:
                filas.append((f"{ruta.stem}_p{page_num}_c{i}",
                              page_num, i, chunk, terminos))

    if not filas:
        print("  → 0 chunks (documento vacío)")
        return 0

    # Términos presentes en TODO el documento (df por documento)
    terminos_doc = {t for _, _, _, _, c in filas for t in c}
    terminos_ids = _guardar_terms(conn, terminos_doc)

    # Reemplazar la aportación previa de este documento (re-indexado)
    conn.execute("DELETE FROM doc_terms WHERE doc = ?", (doc_id,))
    conn.execute("DELETE FROM chunks WHERE documento = ?", (doc_id,))

    # df por documento: un término cuenta una vez por documento
    conn.executemany(
        "INSERT OR REPLACE INTO doc_terms (doc, termo, frec) VALUES (?, ?, ?)",
        [(doc_id, terminos_ids[t], 1) for t in terminos_doc])

    # Chunks con tf esparso "fid:tf;" (1 + log(frecuencia))
    for chunk_id, page_num, i, texto, contador in filas:
        partes = [f"{terminos_ids[t]}:{1.0 + math.log(n):.4f}"
                  for t, n in contador.items()]
        conn.execute(
            "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            (chunk_id, doc_id, page_num, i, texto, ";".join(partes)))

    conn.commit()
    print(f"  → {len(filas)} chunks | {len(terminos_doc)} términos")
    return len(filas)


def indexar_directorio(directorio: Path, conn: sqlite3.Connection) -> int:
    """Indexa todos los PDFs de un directorio."""
    total = 0
    for pdf in sorted(directorio.glob("*.pdf")):
        total += indexar_documento(pdf, conn)
    return total


def indexar_todo(conn: sqlite3.Connection) -> int:
    """Indexa todos los documentos de rag/documentos/."""
    if not DOCS_DIR.exists():
        print(f"No existe {DOCS_DIR} (descarga antes con descargar_fuentes.py)")
        return 0
    total = 0
    for subdir in sorted(DOCS_DIR.iterdir()):
        if subdir.is_dir():
            total += indexar_directorio(subdir, conn)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexación ligera de HeroQuest (TF-IDF + SQLite, stdlib)")
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
        else:
            indexar_documento(ruta, conn)
    elif args.directorio:
        dir_path = Path(args.directorio)
        if not dir_path.exists():
            print(f"No existe: {dir_path}")
        else:
            indexar_directorio(dir_path, conn)
    else:
        indexar_todo(conn)

    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_terms = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
    conn.close()

    print(f"\n✅ Indexación completada. {total_chunks} chunks, "
          f"{total_terms} términos en {DB_PATH}")


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""Búsqueda ligera en la base de conocimiento de HeroQuest (solo stdlib).

Cargar la consulta con el mismo vocabulario del índice y recorrer los chunks
de la base de datos calculando la similitud de coseno en streaming: solo el
vector de la consulta y un chunk a la vez viven en RAM. Sin numpy ni sklearn.

La IDF se deriva en el momento de buscar desde `doc_terms`, así que siempre
refleja el estado global del corpus (aunque se haya indexado incrementalmente).

Uso:
    uv run juegos/heroquest/rag/busqueda_lite.py "¿cómo funcionan las trampas?"
    uv run juegos/heroquest/rag/busqueda_lite.py "stats del Bárbaro" --top 5
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from collections import Counter
from pathlib import Path

import tokenizar

DB_DIR = Path(__file__).parent / "chroma_db_lite"
DB_PATH = DB_DIR / "heroquest.db"


def _cargar_idf(conn: sqlite3.Connection) -> tuple[dict[int, float], dict[int, str]]:
    """Devuelve (idf por fid, fid → termo) derivados de doc_terms (global)."""
    fila = conn.execute(
        "SELECT COUNT(DISTINCT doc) FROM doc_terms").fetchone()
    n_docs = fila[0] if fila else 0
    if not n_docs:
        return {}, {}

    filas = conn.execute(
        "SELECT termo, COUNT(DISTINCT doc) FROM doc_terms "
        "GROUP BY termo").fetchall()
    idf = {fid: math.log((n_docs + 1) / (df + 1)) + 1.0
           for fid, df in filas}

    terms = {termo: fid for termo, fid in
             conn.execute("SELECT termo, fid FROM terms")}
    fid_a_termo = {fid: termo for termo, fid in terms.items()}
    return idf, fid_a_termo


def _vectorizar(query: str, termo_a_fid: dict[str, int],
                idf: dict[int, float]) -> tuple[dict[int, float], float]:
    """Vectoriza la consulta (tf-idf esparso) y devuelve (vector, norma)."""
    vector: dict[int, float] = {}
    for termo, n in Counter(tokenizar.tokenizar(query)).items():
        fid = termo_a_fid.get(termo)
        if fid is not None and fid in idf:
            vector[fid] = (1.0 + math.log(n)) * idf[fid]
    norma = math.sqrt(sum(v * v for v in vector.values()))
    return vector, norma


def _parse_vector(terms_raw: str | None) -> dict[int, float]:
    """Convierte "fid:tf;fid:tf;" en {fid: tf}."""
    vector: dict[int, float] = {}
    if not terms_raw:
        return vector
    for par in terms_raw.split(";"):
        if not par:
            continue
        fid_txt, tf_txt = par.split(":")
        vector[int(fid_txt)] = float(tf_txt)
    return vector


def buscar(query: str, top_k: int = 3) -> list[dict]:
    if not DB_PATH.exists():
        print("⚠️  Base de datos no indexada. Ejecuta:")
        print("   uv run juegos/heroquest/rag/indexar_lite.py --todo")
        return []

    conn = sqlite3.connect(str(DB_PATH))
    idf, _ = _cargar_idf(conn)
    termo_a_fid = {termo: fid for termo, fid in
                   conn.execute("SELECT termo, fid FROM terms")}

    if not idf:
        conn.close()
        print("⚠️  El índice está vacío. Indexa antes con indexar_lite.py")
        return []

    q_vec, q_norma = _vectorizar(query, termo_a_fid, idf)
    if not q_vec or q_norma == 0:
        conn.close()
        return []

    # Recorrido en streaming: un chunk en RAM por iteración
    candidatos: list[tuple[float, tuple]] = []
    cursor = conn.execute(
        "SELECT id, documento, pagina, texto, terms FROM chunks")
    for fila in cursor:
        v = _parse_vector(fila[4])
        # Ponderar con la IDF actual y hacer el producto escalar con la consulta
        dot = 0.0
        norm_v = 0.0
        for fid, tf in v.items():
            p = tf * idf.get(fid, 0.0)
            norm_v += p * p
            if fid in q_vec:
                dot += p * q_vec[fid]
        if dot == 0.0:
            continue
        norm_v = math.sqrt(norm_v)
        if norm_v == 0.0:
            continue
        sim = dot / (q_norma * norm_v)
        if sim > 0:
            candidatos.append((sim, fila))

    conn.close()
    candidatos.sort(key=lambda x: x[0], reverse=True)

    return [
        {"id": fila[0], "documento": fila[1], "pagina": fila[2],
         "texto": fila[3], "similitud": sim}
        for sim, fila in candidatos[:top_k]
    ]


def mostrar_resultados(query: str, resultados: list[dict]) -> None:
    print(f"\n🔍 Query: \"{query}\"\n")

    if not resultados:
        print("No se encontraron resultados.")
        return

    for i, r in enumerate(resultados, 1):
        print(f"{'=' * 60}")
        print(f"  Resultado {i} | Relevancia: {r['similitud']:.1%}")
        print(f"{'=' * 60}")
        print(f"  📄 Fuente: {Path(r['documento']).name}")
        print(f"  📃 Página: {r['pagina']}")
        texto = r['texto']
        if len(texto) > 300:
            texto = texto[:300] + "..."
        print("\n  📝 Fragmento:")
        for linea in texto.split("\n"):
            if linea.strip():
                print(f"     {linea.strip()}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Búsqueda ligera en HeroQuest (TF-IDF, stdlib)")
    parser.add_argument("query", help="Texto a buscar")
    parser.add_argument("--top", type=int, default=3,
                        help="Número de resultados")
    args = parser.parse_args()

    resultados = buscar(args.query, top_k=args.top)
    mostrar_resultados(args.query, resultados)


if __name__ == "__main__":
    main()
"""Búsqueda ligera en la base de conocimiento de HeroQuest.

Uso:
    uv run busqueda_lite.py "¿cómo funcionan las trampas?"
    uv run busqueda_lite.py "stats del Bárbaro" --top 5
"""

from __future__ import annotations

import argparse
import json
import pickle
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent / "chroma_db_lite"
DB_PATH = DB_DIR / "heroquest.db"
VECTORIZER_PATH = DB_DIR / "vectorizer.pkl"


def buscar(query: str, top_k: int = 3) -> list[dict]:
    """Busca usando similitud coseno con TF-IDF."""
    import numpy as np
    
    if not DB_PATH.exists():
        print("⚠️  Base de datos no indexada. Ejecuta:")
        print("   uv run indexar_lite.py --todo")
        return []
    
    # Cargar vectorizer
    if not VECTORIZER_PATH.exists():
        print("⚠️  Vectorizer no encontrado. Re-indexa con:")
        print("   uv run indexar_lite.py --todo")
        return []
    
    with open(VECTORIZER_PATH, "rb") as f:
        vectorizer = pickle.load(f)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("SELECT id, documento, pagina, chunk, texto, tfidf_vector FROM chunks")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("⚠️  La base de datos está vacía.")
        return []
    
    # Preparar datos
    ids = [r[0] for r in rows]
    documentos = [r[1] for r in rows]
    paginas = [r[2] for r in rows]
    textos = [r[4] for r in rows]
    vectores = [np.array(json.loads(r[5])) for r in rows]
    
    # Vectorizar la query con el mismo vectorizer
    query_vector = vectorizer.transform([query]).toarray()[0]
    
    # Ajustar dimensiones si es necesario
    dim_query = len(query_vector)
    
    # Calcular similitud coseno
    similitudes = []
    for i, vector in enumerate(vectores):
        # Recortar o rellenar vector al mismo tamaño
        if len(vector) > dim_query:
            vector = vector[:dim_query]
        elif len(vector) < dim_query:
            vector = np.pad(vector, (0, dim_query - len(vector)))
        
        norm_vec = np.linalg.norm(vector)
        norm_query = np.linalg.norm(query_vector)
        
        if norm_vec > 0 and norm_query > 0:
            sim = np.dot(vector, query_vector) / (norm_vec * norm_query)
        else:
            sim = 0
        similitudes.append((sim, i))
    
    # Ordenar por similitud
    similitudes.sort(reverse=True)
    
    # Devolver top_k
    resultados = []
    for sim, idx in similitudes[:top_k]:
        resultados.append({
            "id": ids[idx],
            "documento": documentos[idx],
            "pagina": paginas[idx],
            "texto": textos[idx],
            "similitud": float(sim)
        })
    
    return resultados


def mostrar_resultados(query: str, resultados: list[dict]) -> None:
    """Muestra los resultados formateados."""
    print(f"\n🔍 Query: \"{query}\"\n")
    
    if not resultados:
        print("No se encontraron resultados.")
        return
    
    for i, r in enumerate(resultados, 1):
        print(f"{'='*60}")
        print(f"  Resultado {i} | Relevancia: {r['similitud']:.1%}")
        print(f"{'='*60}")
        print(f"  📄 Fuente: {Path(r['documento']).name}")
        print(f"  📃 Página: {r['pagina']}")
        
        texto = r['texto']
        if len(texto) > 300:
            texto = texto[:300] + "..."
        
        print(f"\n  📝 Fragmento:")
        for linea in texto.split("\n"):
            if linea.strip():
                print(f"     {linea.strip()}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Búsqueda ligera en HeroQuest (TF-IDF)")
    parser.add_argument("query", help="Texto a buscar")
    parser.add_argument("--top", type=int, default=3, help="Número de resultados")
    args = parser.parse_args()
    
    resultados = buscar(args.query, top_k=args.top)
    mostrar_resultados(args.query, resultados)


if __name__ == "__main__":
    main()

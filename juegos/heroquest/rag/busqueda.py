"""Búsqueda semántica en la base de conocimiento de HeroQuest.

Uso:
    uv run busqueda.py "¿cómo funcionan las trampas?"
    uv run busqueda.py "stats del Bárbaro" --top 5
    uv run busqueda.py "hechizos de fuego" --verbose
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "chromadb", "sentence-transformers"], check=True)
    import chromadb
    from sentence_transformers import SentenceTransformer

DB_DIR = Path(__file__).parent / "chroma_db"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"


def buscar(
    query: str,
    top_k: int = 3,
    verbose: bool = False
) -> list[dict]:
    """Busca en ChromaDB y devuelve los resultados más relevantes."""
    
    if not DB_DIR.exists():
        print("⚠️  Base de datos no indexada. Ejecuta primero:")
        print("   uv run indexar.py --todo")
        return []
    
    # Cargar modelo
    modelo = SentenceTransformer(MODELO_EMBEDDINGS)
    
    # Conectar a ChromaDB
    client = chromadb.PersistentClient(path=str(DB_DIR))
    collection = client.get_or_create_collection("heroquest_rules")
    
    if collection.count() == 0:
        print("⚠️  La base de datos está vacía. Indexa documentos primero.")
        return []
    
    # Generar embedding de la query
    query_embedding = modelo.encode(query).tolist()
    
    # Buscar
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    
    # Formatear resultados
    resultados = []
    for i in range(len(results["ids"][0])):
        resultados.append({
            "id": results["ids"][0][i],
            "documento": results["documents"][0][i],
            "fuente": results["metadatas"][0][i].get("fuente", ""),
            "pagina": results["metadatas"][0][i].get("pagina", 0),
            "distancia": results["distances"][0][i],
        })
    
    return resultados


def mostrar_resultados(query: str, resultados: list[dict], verbose: bool = False) -> None:
    """Muestra los resultados formateados."""
    print(f"\n🔍 Query: \"{query}\"\n")
    
    if not resultados:
        print("No se encontraron resultados.")
        return
    
    for i, r in enumerate(resultados, 1):
        # Calcular relevancia (1 - distancia)
        relevancia = max(0, 1 - r["distancia"])
        
        print(f"{'='*60}")
        print(f"  Resultado {i} | Relevancia: {relevancia:.1%}")
        print(f"{'='*60}")
        print(f"  📄 Fuente: {Path(r['fuente']).name}")
        print(f"  📃 Página: {r['pagina']}")
        
        if verbose:
            print(f"  🆔 ID: {r['id']}")
            print(f"  📏 Distancia: {r['distancia']:.4f}")
        
        # Mostrar fragmento del documento
        doc = r["documento"]
        if len(doc) > 300:
            doc = doc[:300] + "..."
        
        print(f"\n  📝 Fragmento:")
        for linea in doc.split("\n"):
            if linea.strip():
                print(f"     {linea.strip()}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Búsqueda semántica en base de conocimiento HeroQuest")
    parser.add_argument("query", help="Texto a buscar")
    parser.add_argument("--top", type=int, default=3, help="Número de resultados")
    parser.add_argument("--verbose", action="store_true", help="Mostrar detalles extra")
    args = parser.parse_args()
    
    resultados = buscar(args.query, top_k=args.top, verbose=args.verbose)
    mostrar_resultados(args.query, resultados, verbose=args.verbose)


if __name__ == "__main__":
    main()

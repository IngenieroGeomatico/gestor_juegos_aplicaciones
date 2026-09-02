"""Descarga fuentes de HeroQuest para indexar en el RAG.

Lee las fuentes desde data/fuentes.json y descarga los PDFs de Google Drive.

Uso:
    uv run descargar_fuentes.py                         # Descarga todo
    uv run descargar_fuentes.py --prioridad alta         # Solo prioridad alta
    uv run descargar_fuentes.py --categoria Reglas       # Solo reglas
    uv run descargar_fuentes.py --expansion "Alquimia"   # Solo expansión Alquimia
    uv run descargar_fuentes.py --nombre "manual"        # Buscar por nombre
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

# Rutas
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DESTINO = Path(__file__).parent / "documentos"


def _cargar_fuentes() -> list[dict]:
    """Carga las fuentes desde fuentes.json."""
    ruta = _DATA_DIR / "fuentes.json"
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def _descargar_gdrive(file_id: str, destino: Path) -> bool:
    """Descarga un fichero de Google Drive usando gdown."""
    try:
        import gdown
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, str(destino), quiet=False)
        return True
    except ImportError:
        print("  Instalando gdown...")
        subprocess.run(["uv", "pip", "install", "gdown"], check=True)
        import gdown
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, str(destino), quiet=False)
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def _descargar_url(url: str, destino: Path) -> bool:
    """Descarga un fichero desde una URL directa.

    Intenta HTTPS y, si falla por SSL, reintenta con HTTP.
    """
    import requests
    for proto in ("https://", "http://"):
        if url.startswith("https://") or url.startswith("http://"):
            full = url
        else:
            full = f"{proto}{url}"
        try:
            print(f"  Descargando desde {full[:70]}...")
            resp = requests.get(full, timeout=60, allow_redirects=True)
            resp.raise_for_status()
            destino.write_bytes(resp.content)
            print(f"  OK: {len(resp.content):,} bytes")
            return True
        except Exception as e:
            print(f"  Error ({proto.rstrip(':')}): {e}")
    return False


def _slug(nombre: str) -> str:
    """Convierte un nombre en slug seguro para ficheros."""
    return "".join(c if c.isalnum() else "_" for c in nombre).strip("_")


def descargar_fuentes(
    prioridad: str | None = None,
    categoria: str | None = None,
    expansion: str | None = None,
    nombre: str | None = None,
) -> None:
    """Descarga las fuentes filtradas."""
    fuentes = _cargar_fuentes()
    if not fuentes:
        print("No se encontraron fuentes en data/fuentes.json")
        return

    # Aplicar filtros
    if prioridad:
        fuentes = [f for f in fuentes if f.get("prioridad") == prioridad]
    if categoria:
        fuentes = [f for f in fuentes if f.get("categoria") == categoria]
    if expansion:
        fuentes = [f for f in fuentes if f.get("expansion") == expansion]
    if nombre:
        nombre_lower = nombre.lower()
        fuentes = [f for f in fuentes if nombre_lower in f.get("nombre", "").lower()]

    # Filtrar solo las descargables (con file_id o url)
    descargables = [f for f in fuentes if f.get("file_id") or f.get("url")]

    if not descargables:
        print("No se encontraron fuentes descargables con los filtros aplicados.")
        return

    print(f"\n{'='*60}")
    print(f"  Descargando {len(descargables)} fuentes")
    print(f"{'='*60}\n")

    for fuente in descargables:
        nombre_fuente = fuente["nombre"]
        file_id = fuente.get("file_id")
        url = fuente.get("url")
        expansion_fuente = fuente.get("expansion", "General")
        slug_expansion = _slug(expansion_fuente)

        # Crear directorio por expansión
        dir_expansion = _DESTINO / slug_expansion
        dir_expansion.mkdir(parents=True, exist_ok=True)

        # Nombre del fichero (extensión según tipo)
        slug_nombre = _slug(nombre_fuente)
        ext = ".pdf" if ".pdf" in str(fuente.get("url", "")).lower() or file_id else ".html"
        destino = dir_expansion / f"{slug_nombre}{ext}"

        print(f"→ {nombre_fuente}")
        print(f"  Expansión: {expansion_fuente}")
        print(f"  Prioridad: {fuente.get('prioridad', 'N/A')}")

        if destino.exists():
            print(f"  Ya existe: {destino.name}")
            continue

        if file_id:
            _descargar_gdrive(file_id, destino)
        elif url:
            _descargar_url(url, destino)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga fuentes de HeroQuest para RAG")
    parser.add_argument(
        "--prioridad", choices=["alta", "media", "baja"],
        help="Filtrar por prioridad")
    parser.add_argument(
        "--categoria",
        help="Filtrar por categoría (Reglas, Misiones, Cartas, etc.)")
    parser.add_argument(
        "--expansion",
        help="Filtrar por expansión (Alquimia, Juego Base, etc.)")
    parser.add_argument(
        "--nombre",
        help="Buscar por nombre (búsqueda parcial)")
    parser.add_argument(
        "--listar", action="store_true",
        help="Listar fuentes disponibles sin descargar")
    args = parser.parse_args()

    if args.listar:
        fuentes = _cargar_fuentes()
        if args.prioridad:
            fuentes = [f for f in fuentes if f.get("prioridad") == args.prioridad]
        if args.categoria:
            fuentes = [f for f in fuentes if f.get("categoria") == args.categoria]
        if args.expansion:
            fuentes = [f for f in fuentes if f.get("expansion") == args.expansion]
        if args.nombre:
            nombre_lower = args.nombre.lower()
            fuentes = [f for f in fuentes if nombre_lower in f.get("nombre", "").lower()]

        print(f"\nFuentes encontradas: {len(fuentes)}\n")
        for f in fuentes:
            pri = f.get("prioridad", "?")
            cat = f.get("categoria", "?")
            has_id = "✓" if f.get("file_id") else "✗"
            print(f"  [{pri:5}] [{cat:12}] {has_id} {f['nombre']}")
        return

    descargar_fuentes(
        prioridad=args.prioridad,
        categoria=args.categoria,
        expansion=args.expansion,
        nombre=args.nombre,
    )
    print("\n✅ Descarga completada")


if __name__ == "__main__":
    main()

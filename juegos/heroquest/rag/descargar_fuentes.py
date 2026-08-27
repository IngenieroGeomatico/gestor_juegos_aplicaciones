"""Descarga fuentes de HeroQuest para indexar en el RAG.

Uso:
    uv run descargar_fuentes.py                    # Descarga todo
    uv run descargar_fuentes.py --solo reglas      # Solo manuales
    uv run descargar_fuentes.py --solo misiones    # Solo aventuras
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

# Directorio de destino
DESTINO = Path(__file__).parent / "documentos"

# Enlaces a PDFs de Google Drive
FUENTES = {
    "reglas": {
        "manual_heroquest_2021": "18zlEFaKQNMMMDnEEbMVq0LUD4mwuUcJr",
        "compendio_ahq": "1kohbUfbFFNFqtQCaSxrSxJpN4f3y6_AY",
        "wizard_quest_1993": "1KOa02SqdO92Z3DFLhZe0XJKOPL-6vnR2",
    },
    "cartas": {
        "cartas_juego_base": "1aPgtbgNzAlkejntAaV-W4vfMIiWJDypS",
        "cartas_fanmade": "1C99ZdrnC0C96o2GiDZbSrD3XQ7Z78kG1",
    },
    "misiones": {
        "libro_misiones_base": "10y6gKUobO_mSaSH0DzYIQ726xYTTaAPh",
        "misiones_online": "1CV4OynLgL1st6WCwcqGXOxQ964nk17z-",
    },
    "expansiones": {
        "alquimia_completo": "1gU9L7S3gPApbLuzaPWrLiGim6c189EAw",
        "compania_tenebrosa": "1rb0v83LmhNlspp0rM5rmMzOedz4P6jaQ",
    },
}


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


def descargar_fuentes(categorias: list[str] | None = None) -> None:
    """Descarga las fuentes solicitadas."""
    cat_a_descargar = categorias or list(FUENTES.keys())
    
    for cat in cat_a_descargar:
        if cat not in FUENTES:
            print(f"Categoría desconocida: {cat}")
            continue
        
        print(f"\n{'='*60}")
        print(f"  {cat.upper()}")
        print(f"{'='*60}")
        
        dir_cat = DESTINO / cat
        dir_cat.mkdir(parents=True, exist_ok=True)
        
        for nombre, file_id in FUENTES[cat].items():
            print(f"\n→ {nombre}")
            destino = dir_cat / f"{nombre}.pdf"
            
            if destino.exists():
                print(f"  Ya existe: {destino}")
                continue
            
            _descargar_gdrive(file_id, destino)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga fuentes de HeroQuest para RAG")
    parser.add_argument(
        "--solo", choices=list(FUENTES.keys()),
        help="Descargar solo una categoría")
    args = parser.parse_args()
    
    cats = [args.solo] if args.solo else None
    descargar_fuentes(cats)
    print("\n✅ Descarga completada")


if __name__ == "__main__":
    main()

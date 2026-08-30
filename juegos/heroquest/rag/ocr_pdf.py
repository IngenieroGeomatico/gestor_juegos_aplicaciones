"""Convierte un PDF escaneado de HeroQuest a texto usando tesseract OCR.

El Libro de misiones de "El Despertar" es un escaneado (sin capa de texto), así
que se rasteriza cada página a una imagen y se le aplica tesseract con el idioma
español. El resultado se guarda como un fichero .txt por página en un directorio
de salida.

Requisitos:
    sudo apt-get install -y tesseract-ocr tesseract-ocr-spa

Uso:
    python ocr_pdf.py --pdf <ruta.pdf> --salida <dir_salida>
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None


def _tesseract(ruta_img: Path, lang: str) -> str:
    """Devuelve el texto OCR de una imagen usando tesseract."""
    proc = subprocess.run(
        ["tesseract", str(ruta_img), "stdout", "-l", lang],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract falló: {proc.stderr}")
    return proc.stdout


def ocr_pdf(pdf: Path, salida: Path, lang: str = "spa", dpi: int = 300) -> None:
    if pymupdf is None:
        raise SystemExit("Falta pymupdf: uv run o uv pip install pymupdf")

    salida.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf))
    print(f"Procesando {len(doc)} páginas...")

    for i, page in enumerate(doc):
        # Rasterizar la página a alta resolución para un OCR de calidad
        pix = page.get_pixmap(dpi=dpi)
        ruta_img = salida / f"pag_{i+1:02d}.png"
        pix.save(str(ruta_img))

        try:
            texto = _tesseract(ruta_img, lang)
        except RuntimeError as e:
            print(f"  pág {i+1}: ERROR {e}")
            continue

        ruta_txt = salida / f"pag_{i+1:02d}.txt"
        ruta_txt.write_text(texto, encoding="utf-8")
        print(f"  pág {i+1}: {len(texto)} caracteres")
        ruta_img.unlink()  # no conservamos los PNG intermedios

    doc.close()
    print(f"\nListo. Texto en {salida}/*.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR de un PDF escaneado de HeroQuest")
    parser.add_argument("--pdf", required=True, help="Ruta al PDF escaneado")
    parser.add_argument("--salida", required=True, help="Directorio de salida del texto")
    parser.add_argument("--lang", default="spa", help="Idioma tesseract (por defecto spa)")
    parser.add_argument("--dpi", type=int, default=300, help="Resolución del OCR (300)")
    args = parser.parse_args()
    ocr_pdf(Path(args.pdf), Path(args.salida), args.lang, args.dpi)

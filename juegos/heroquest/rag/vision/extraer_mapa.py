#!/usr/bin/env python3
"""Extrae la página de mapa de una misión del PDF de El Despertar a PNG.

El libro usa 1 página de mapa por misión. La Misión 1 es la página 10 (índice 9),
la Misión 2 la 12, etc. (páginas pares: índice = 8 + 2*n).

Uso: python extraer_mapa.py <pdf> <mision> --salida mapa.png [--dpi 200]
"""
import argparse
import pymupdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("mision", type=int)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    # Misión n -> página de mapa (índice 0-based)
    idx = 8 + 2 * args.mision
    if idx >= doc.page_count:
        raise SystemExit(f"página {idx} fuera de rango (solo {doc.page_count} páginas)")
    pix = doc[idx].get_pixmap(dpi=args.dpi)
    pix.save(args.salida)
    print(f"Misión {args.mision} -> página {idx + 1} -> {args.salida} ({pix.width}x{pix.height})")


if __name__ == "__main__":
    main()

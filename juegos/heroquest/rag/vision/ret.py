#!/usr/bin/env python3
"""Genera una imagen del mapa con la retícula del tablero (26x19) superpuesta y
cada casilla numerada con su (col,fila), para validar visualmente posiciones.
"""
import argparse
import json
import os
from PIL import Image, ImageDraw
import numpy as np

BASE = os.path.dirname(__file__)
COLS, FILAS = 26, 19


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapa")
    ap.add_argument("mision")
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(BASE, "misiones_vision.json")))
    m = cfg.get(args.mision)
    if not m:
        raise SystemExit(f"sin config para {args.mision}")
    e = m["esquinas_tablero_px"]
    (x1, y1), (x2, _), (_, _), (_, y4) = e["si"], e["sd"], e["ii"], e["id"]

    a = COLS / (x2 - x1)
    c = -a * x1
    e_ = FILAS / (y4 - y1)
    f = -e_ * y1

    def c2p(col, fila):
        return ((col - 0.5 - c) / a, (fila - 0.5 - f) / e_)

    img = Image.open(args.mapa).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # borde exterior del tablero
    draw.rectangle([x1, y1, x2, y4], outline=(255, 0, 0, 255), width=4)

    # retícula
    for col in range(COLS + 1):
        px = (col - c) / a
        draw.line([(px, y1), (px, y4)], fill=(255, 0, 0, 160), width=2)
    for fila in range(FILAS + 1):
        py = (fila - f) / e_
        draw.line([(x1, py), (x2, py)], fill=(255, 0, 0, 160), width=2)

    # numeración de cada casilla (centro)
    cw = (x2 - x1) / COLS
    ch = (y4 - y1) / FILAS
    for col in range(1, COLS + 1):
        for fila in range(1, FILAS + 1):
            px, py = c2p(col, fila)
            tx, ty = px, py
            draw.text((tx, ty), f"{col},{fila}", fill=(0, 0, 255, 255),
                      stroke_width=2, stroke_fill=(255, 255, 255, 255))

    img.save(args.salida)
    print("imagen:", args.salida)


if __name__ == "__main__":
    main()

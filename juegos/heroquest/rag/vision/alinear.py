#!/usr/bin/env python3
"""Alinea el mapa real con la cuadrícula 26x19 del tablero usando 4 esquinas.

Resuelve una transformación afín (rotación + escala X/Y + desplazamiento) que mapea
los 4 puntos dados (esquinas del tablero en píxeles) a las 4 esquinas de la cuadrícula.
Genera una imagen de validación con la retícula superpuesta.

Uso:
  python alinear.py <mapa.png> --esquinas "supizq supder infizq infder" --salida out.png

  cada esquina = x,y  (píxeles del mapa)
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw

COLS, FILAS = 26, 19


def build(corners, mapa, salida):
    img = Image.open(mapa).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # puntos en píxeles (esquinas EXTERIORES del tablero), orden: SI, SD, II, ID
    P = np.array([corners[0], corners[1], corners[2], corners[3]], dtype=float)
    # correspondientes esquinas del tablero en coordenadas de casilla:
    # la esquina SI es la esquina de la casilla (1,1) -> (0,0); la ID es la
    # esquina de la casilla (26,19) -> (COLS, FILAS).
    Q = np.array([
        [0.0, 0.0],        # esquina sup-izq
        [COLS, 0.0],       # esquina sup-der
        [0.0, FILAS],      # esquina inf-izq
        [COLS, FILAS],     # esquina inf-der
    ])

    # resolver afín: Q = P @ A + t  -> mínimo cuadrados
    # Modelo: px = a*col + b*fila + c ; py = d*col + e*fila + f
    # montamos matrices
    A = np.c_[P, np.ones(4)]  # 4x3
    M, res, rank, sv = np.linalg.lstsq(A, Q, rcond=None)  # M: 3x2
    # px = M[0,0]*x + M[1,0]*y + M[2,0]
    print("matriz afín (px -> col,fila):")
    print(M)
    print("proporción escala X/Y:", round(M[0, 0] / M[1, 1], 3))

    def px_to_cf(x, y):
        cf = M[0] * x + M[1] * y + M[2]
        return cf[0], cf[1]

    def cf_to_px(c, f):
        # invertir
        MM = np.array([[M[0, 0], M[1, 0]], [M[0, 1], M[1, 1]]])  # 2x2
        t = np.array([M[2, 0], M[2, 1]])
        p = np.linalg.inv(MM) @ (np.array([c, f]) - t)
        return p[0], p[1]

    def px_a_casilla(x, y):
        cf = M[0] * x + M[1] * y + M[2]  # coords de esquina de casilla
        col = int(np.floor(cf[0])) + 1
        fila = int(np.floor(cf[1])) + 1
        return col, fila

    # dibujar retícula (líneas en coords de esquina 0..COLS, 0..FILAS)
    for c in range(COLS + 1):
        x0, y0 = cf_to_px(c, 0.0)
        x1, y1 = cf_to_px(c, FILAS)
        draw.line([(x0, y0), (x1, y1)], fill=(255, 0, 0, 130), width=2)
    for f in range(FILAS + 1):
        x0, y0 = cf_to_px(0.0, f)
        x1, y1 = cf_to_px(COLS, f)
        draw.line([(x0, y0), (x1, y1)], fill=(255, 0, 0, 130), width=2)

    for c in range(COLS):
        for f in range(FILAS):
            px, py = cf_to_px(c + 0.5, f + 0.5)
            draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(0, 0, 255, 220))
            draw.text((px + 4, py + 4), f"{c+1},{f+1}", fill=(0, 0, 255, 255))

    img.save(salida)
    print("guardado:", salida)


def parse_pt(s):
    x, y = s.split(",")
    return float(x), float(y)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mapa")
    ap.add_argument("--esquinas", required=True,
                    help="SI SD II ID  (x,y x,y x,y x,y)")
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()
    parts = args.esquinas.split()
    if len(parts) != 4:
        raise SystemExit("se esperaban 4 esquinas")
    corners = [parse_pt(p) for p in parts]
    build(corners, args.mapa, args.salida)

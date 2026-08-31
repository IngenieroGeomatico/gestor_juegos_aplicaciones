#!/usr/bin/env python3
"""Genera la imagen de validación de MONSTRUOS de una misión.

Detecta por visión por computadora los iconos de monstruos (casillas rellenas
de verde) sobre el mapa y pinta cada casilla numerada V1..Vn con su
coordenada (col,fila), para que el usuario valide visualmente posición y tipo.

Uso:
  python validar_monstruos.py <imagen_mapa.png> --key M1 [--salidas dir]
"""
import argparse
import json
import os
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(__file__)
COLS, FILAS = 26, 19
VERDE = {"r": 160, "g": 190, "b": 150}
COLOR = (0, 150, 0, 255)
COLOR_PENDIENTE = (220, 30, 30, 255)


def componentes(mask, min_n, wmin, hmin, wmax, hmax):
    h, w = mask.shape
    vis = np.zeros_like(mask)
    out = []
    for yy in range(h):
        for xx in range(w):
            if mask[yy, xx] and not vis[yy, xx]:
                q = deque([(xx, yy)])
                vis[yy, xx] = True
                pts = []
                while q:
                    cx, cy = q.popleft()
                    pts.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not vis[ny, nx]:
                            vis[ny, nx] = True
                            q.append((nx, ny))
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                n = len(pts)
                wc = max(xs) - min(xs) + 1
                hc = max(ys) - min(ys) + 1
                if n >= min_n and wmin <= wc <= wmax and hmin <= hc <= hmax:
                    out.append((min(xs), min(ys), wc, hc, n))
    return out


def transformar(cfg):
    esq = cfg["esquinas_tablero_px"]
    (x1, y1), (x2, _), (_, _), (_, y4) = esq["si"], esq["sd"], esq["ii"], esq["id"]
    a = COLS / (x2 - x1)
    e = FILAS / (y4 - y1)
    c = -a * x1
    f = -e * y1

    def casilla_a_px(col, fila):
        x = (col - 0.5 - c) / a
        y = (fila - 0.5 - f) / e
        return x, y

    def px_a_casilla(x, y):
        return int(np.floor(a * x + c)) + 1, int(np.floor(e * y + f)) + 1

    return casilla_a_px, px_a_casilla, (x1, y1, x2, y4)


def cargar_fuentes():
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
    except Exception:
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapa")
    ap.add_argument("--key", required=True)
    ap.add_argument("--salidas", default=None)
    args = ap.parse_args()

    F_BOLD = cargar_fuentes()

    with open(os.path.join(BASE, "misiones_vision.json")) as f:
        cfg = json.load(f)[args.key]

    c2p, p2c, (x1, y1, x2, y4) = transformar(cfg)
    img = Image.open(args.mapa).convert("RGB")
    arr = np.array(img)
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)

    verde = (g > r + 5) & (g > b + 5) & (g > 150) & (r < 240) & (b < 240)
    verdes = componentes(verde, 50, 25, 25, 70, 70)

    dr = ImageDraw.Draw(img, "RGBA")
    # retícula
    for col in range(COLS + 1):
        px = x1 + (x2 - x1) * col / COLS
        dr.line([(px, y1), (px, y4)], fill=(255, 0, 0, 120), width=1)
    for fila in range(FILAS + 1):
        py = y1 + (y4 - y1) * fila / FILAS
        dr.line([(x1, py), (x2, py)], fill=(255, 0, 0, 120), width=1)

    items = []
    for i, (mx, my, wc, hc, n) in enumerate(verdes):
        cx, cy = mx + wc // 2, my + hc // 2
        col, fila = p2c(cx, cy)
        x, y = c2p(col, fila)
        dx = (c2p(col + 1, fila)[0] - x) / 2
        dy = (c2p(col, fila + 1)[1] - y) / 2
        box = (x - dx, y - dy, x + dx, y + dy)
        items.append((i + 1, col, fila, box))

    # Tipo confirmado por el usuario (véase clasificación de M1)
    tipos = {
        (17, 7): "goblin", (16, 4): "goblin", (9, 8): "goblin", (20, 6): "goblin",
        (12, 5): "goblin", (8, 12): "goblin", (10, 7): "goblin", (17, 4): "goblin",
        (19, 9): "orco", (11, 4): "orco", (7, 9): "orco", (20, 11): "orco", (9, 11): "orco",
        (19, 12): "orco", (15, 14): "orco", (18, 14): "orco", (15, 15): "orco",
        (9, 14): "zombie", (8, 16): "zombie", (6, 16): "zombie",
        (12, 16): "abominacion", (11, 17): "abominacion",
        (17, 15): "final",
    }

    for i, col, fila, box in items:
        t = tipos.get((col, fila))
        color = COLOR if t else COLOR_PENDIENTE
        dr.rectangle(box, outline=color, width=5)
        etiq = f"V{i} ({col},{fila})" + (f" ?={t}" if t else " ?")
        dr.text((box[0] + 4, box[1] + 2), etiq, fill=color,
                font=F_BOLD, stroke_width=2, stroke_fill=(255, 255, 255, 255))

    outdir = args.salidas or os.path.dirname(args.mapa)
    os.makedirs(outdir, exist_ok=True)
    sal = os.path.join(outdir, "monstruos_detectados.png")
    img.save(sal)
    print(f"{len(items)} monstruos detectados -> {sal}")
    for i, col, fila, _ in items:
        print(f"  V{i:2d}: ({col},{fila}) -> {tipos.get((col, fila), '?')}")
    print("\n(clasificación ? = pendiente de catalogar por el usuario)")


if __name__ == "__main__":
    main()

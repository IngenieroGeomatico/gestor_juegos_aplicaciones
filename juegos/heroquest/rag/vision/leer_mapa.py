#!/usr/bin/env python3
"""Lee los elementos de un mapa de misión y los convierte a casillas.

Usa la config de misión (misiones_vision.json) para la alineación y detecta:
 - LETRAS rojas (A/B/C/D...) por centroide de componentes rojas compactas
 - CALAVERAS (exploradores caídos) por componente de fondo negro
 - TRAMPAS por componentes rojas pequeñas
Genera una imagen de validación en /tmp con numeración estable y colores por tipo.

Uso: python leer_mapa.py <mapa.png> <mision> [--salida out.png]
"""
import argparse
import json
import os
from collections import deque
from PIL import Image, ImageDraw
import numpy as np

BASE = os.path.dirname(__file__)
COLS, FILAS = 26, 19


def cargar_config(mision):
    with open(os.path.join(BASE, "misiones_vision.json")) as f:
        d = json.load(f)
    m = d.get(mision)
    if not m:
        raise SystemExit(f"no hay config para {mision}")
    e = m["esquinas_tablero_px"]
    return e["si"], e["sd"], e["ii"], e["id"]


def transformar(esq):
    """Devuelve closures px->casilla y casilla->px (afín, sin rotación)."""
    (x1, y1), (x2, _), (_, _), (_, y4) = esq
    a = (COLS) / (x2 - x1)
    e = (FILAS) / (y4 - y1)
    c = -a * x1
    f = -e * y1

    def px_a_casilla(x, y):
        col = int(np.floor(a * x + c)) + 1
        fila = int(np.floor(e * y + f)) + 1
        return col, fila

    def casilla_a_px(col, fila):
        x = (col - 0.5 - c) / a
        y = (fila - 0.5 - f) / e
        return x, y

    return px_a_casilla, casilla_a_px


def componentes(mask, area, min_n, wmin, hmin, wmax, hmax):
    x0t, y0t, x1t, y1t = area
    m = np.zeros_like(mask); m[y0t:y1t + 1, x0t:x1t + 1] = mask[y0t:y1t + 1, x0t:x1t + 1]
    h, w = m.shape; vis = np.zeros_like(m); out = []
    for yy in range(h):
        for xx in range(w):
            if m[yy, xx] and not vis[yy, xx]:
                q = deque([(xx, yy)]); vis[yy, xx] = True; pts = []
                while q:
                    cx, cy = q.popleft(); pts.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and m[ny, nx] and not vis[ny, nx]:
                            vis[ny, nx] = True; q.append((nx, ny))
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                n = len(pts); wc = max(xs) - min(xs) + 1; hc = max(ys) - min(ys) + 1
                if min_n <= n and wmin <= wc <= wmax and hmin <= hc <= hmax:
                    out.append((min(xs), min(ys), wc, hc))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapa")
    ap.add_argument("mision")
    ap.add_argument("--salida", default=None)
    args = ap.parse_args()

    esq = cargar_config(args.mision)
    px2c, c2p = transformar(esq)
    xmin, ymin = esq[0]
    xmax, ymax = esq[3]
    area = (xmin, ymin, xmax, ymax)

    a = np.array(Image.open(args.mapa).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rojo = (r > 120) & (r < 230) & (g < 90) & (b < 90)
    negro = (r < 90) & (g < 90) & (b < 90)
    verde = (g > 100) & (r < 120) & (b < 120)

    calaveras = componentes(negro, area, 400, 40, 40, 80, 80)
    rojos = componentes(rojo, area, 200, 20, 20, 70, 70)
    verdes = componentes(verde, area, 300, 30, 30, 80, 80)

    img = Image.open(args.mapa).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    print("== Calaveras (exploradores caídos) ==")
    for i, (mx, my, wc, hc) in enumerate(calaveras, 1):
        col, fila = px2c(mx + wc / 2, my + hc / 2)
        draw.rectangle([mx, my, mx + wc, my + hc], outline=(200, 0, 200, 255), width=3)
        draw.text((mx + 2, my - 18), f"C{i}({col},{fila})", fill=(180, 0, 180, 255))
        print(f"  C{i}: casilla({col},{fila})")

    print("== Componentes rojas (letras/trampas/tesoro-borde, revisar) ==")
    for i, (mx, my, wc, hc) in enumerate(rojos, 1):
        col, fila = px2c(mx + wc / 2, my + hc / 2)
        draw.rectangle([mx, my, mx + wc, my + hc], outline=(0, 200, 0, 255), width=2)
        draw.text((mx + 2, my - 18), f"R{i}({col},{fila})", fill=(0, 180, 0, 255))
        print(f"  R{i}: casilla({col},{fila}) tamaño {wc}x{hc}")

    print("== Componentes verdes (monstruos) ==")
    for i, (mx, my, wc, hc) in enumerate(verdes, 1):
        col, fila = px2c(mx + wc / 2, my + hc / 2)
        draw.rectangle([mx, my, mx + wc, my + hc], outline=(0, 255, 0, 255), width=3)
        draw.text((mx + 2, my - 18), f"V{i}({col},{fila})", fill=(0, 255, 0, 255))
        print(f"  V{i}: casilla({col},{fila}) tamaño {wc}x{hc}")

    # letras configuradas
    cfg = json.load(open(os.path.join(BASE, "misiones_vision.json")))
    for L in cfg[args.mision].get("elementos", {}).get("letras", []):
        for col, fila in L["casillas"]:
            x, y = c2p(col, fila)
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(0, 0, 255, 255))
            draw.text((x + 6, y + 4), L["letra"], fill=(0, 0, 255, 255))

    salida = args.salida or f"/tmp/opencode/leer_{args.mision}.png"
    img.save(salida)
    print("imagen:", salida)


if __name__ == "__main__":
    main()

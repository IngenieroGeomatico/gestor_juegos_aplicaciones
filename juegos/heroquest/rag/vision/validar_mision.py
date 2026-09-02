#!/usr/bin/env python3
"""Genera imágenes de validación de una misión sobre el mapa real del libro.

Para cada misión produce varias imágenes independientes, cada una con UN tipo
de detección, para que sea fácil validar visualmente cada clase de elemento:

  * <slug>_rejilla.png  - mapa con la retícula y el ID/coordenada (col,fila)
                          de CADA casilla dibujado en el centro de la casilla.
  * <slug>_monstruos.png, _tesoros.png, _trampas.png, _marcadores.png,
    _puertas.png, _entrada.png, _letras.png, _calaveras.png
    - cada una pinta SOLO su tipo, con un CUADRADO que enmarca la casilla.

Los elementos de la misión salen de `data/misiones.json`; la referencia de
visión (letras del libro + calaveras de exploradores detectadas) sale de
`misiones_vision.json`. Con `--por-sala` las imágenes de monstruos/tesoros/
trampas/marcadores se generan una por sala.

Uso:
  python validar_mision.py <imagen_mapa.png> --key M1 --mision "<nombre>" [--salidas dir]
"""
import argparse
import json
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(__file__)
ROOT = os.path.normpath(os.path.join(BASE, "..", "..", "..", ".."))
COLS, FILAS = 26, 19

TIPOS = {
    "monstruos": ("M", (200, 30, 30, 255)),
    "tesoros": ("T", (212, 175, 55, 255)),
    "trampas": ("TR", (180, 0, 255, 255)),
    "marcadores": ("MAR", (0, 120, 200, 255)),
    "puertas": ("P", (139, 90, 43, 255)),
    "entrada": ("IN", (30, 160, 60, 255)),
    "letras": ("LETRA", (0, 0, 255, 255)),
    "calaveras": ("CAL", (255, 0, 200, 255)),
}

COLOR_SECRETA = (90, 60, 140, 255)


def cargar_config(key):
    with open(os.path.join(BASE, "misiones_vision.json")) as f:
        d = json.load(f)
    m = d.get(key)
    if not m:
        raise SystemExit(f"no hay config de visión para {key}")
    return m


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

    return casilla_a_px, (x1, y1, x2, y4)


def celda(c2p, col, fila):
    """Devuelve el cuadrado de la casilla (x0,y0,x1,y1)."""
    x, y = c2p(col, fila)
    dx = ((c2p(col + 1, fila)[0] - c2p(col, fila)[0])) / 2
    dy = ((c2p(col, fila + 1)[1] - c2p(col, fila)[1])) / 2
    return (x - dx, y - dy, x + dx, y + dy)


def cargar_fuentes():
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        fonts = ImageFont.truetype("DejaVuSans.ttf", 14)
        return font, fonts
    except Exception:
        f = ImageFont.load_default()
        return f, f


def nueva(img_base, salida):
    img = img_base.copy()
    return img, ImageDraw.Draw(img, "RGBA"), salida


def retícula(draw, x1, y1, x2, y4):
    for col in range(COLS + 1):
        px = x1 + (x2 - x1) * col / COLS
        draw.line([(px, y1), (px, y4)], fill=(255, 0, 0, 130), width=1)
    for fila in range(FILAS + 1):
        py = y1 + (y4 - y1) * fila / FILAS
        draw.line([(x1, py), (x2, py)], fill=(255, 0, 0, 130), width=1)
    draw.rectangle([x1, y1, x2, y4], outline=(255, 0, 0, 255), width=4)


def cuadro(draw, c2p, col, fila, color, label=None, relleno=70):
    x0, y0, x1, y1 = celda(c2p, col, fila)
    draw.rectangle([x0, y0, x1, y1], fill=color[:3] + (relleno,), outline=color, width=5)
    if label:
        draw.text((x0 + 4, y0 + 2), label, fill=color, font=F_BOLD,
                  stroke_width=2, stroke_fill=(255, 255, 255, 255))


def rect_etiquetado(draw, c2p, c1, f1, c2, f2, color, texto, relleno=80):
    """Dibuja un rectángulo sobre el rango de casillas y la palabra DEBAJO."""
    top = c2p(min(c1, c2), min(f1, f2))
    x0 = top[0] - ((c2p(min(c1, c2) + 1, min(f1, f2))[0] - top[0]) / 2)
    y0 = top[1] - ((c2p(min(c1, c2), min(f1, f2) + 1)[1] - top[1]) / 2)
    bot = c2p(max(c1, c2), max(f1, f2))
    x1 = bot[0] + ((c2p(max(c1, c2) + 1, max(f1, f2))[0] - bot[0]) / 2)
    y1 = bot[1] + ((c2p(max(c1, c2), max(f1, f2) + 1)[1] - bot[1]) / 2)
    draw.rectangle([x0, y0, x1, y1], fill=color[:3] + (relleno,), outline=color, width=6)
    bb = draw.textbbox((0, 0), texto, font=F_BOLD)
    tw, th = (bb[2] - bb[0]), (bb[3] - bb[1])
    draw.text(((x0 + x1) / 2 - tw / 2, y1 + 8), texto, fill=color,
              font=F_BOLD, stroke_width=3, stroke_fill=(255, 255, 255, 255))


def parse_rect(s):
    a, b = s.split(":")
    c1, f1 = map(int, a.split(","))
    c2, f2 = map(int, b.split(","))
    return c1, f1, c2, f2


def slug(x):
    return x.lower().replace(" ", "_").replace("/", "_").replace("-", "_")


def _puerta_punto(p, label):
    """Devuelve (col, fila, label) para una puerta {x,y} o umbral {de,a}.
    Para un umbral usa el punto medio de las dos casillas."""
    if "de" in p and "a" in p:
        de, a = p["de"], p["a"]
        col = (de[0] + a[0]) / 2
        fila = (de[1] + a[1]) / 2
    else:
        col, fila = p["x"], p["y"]
    return col, fila, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapa")
    ap.add_argument("--key", required=True, help="clave de config de visión (p. ej. M1)")
    ap.add_argument("--mision", required=True, help="nombre de la misión en misiones.json")
    ap.add_argument("--salidas", default=None, help="carpeta de salida (por defecto junto al mapa)")
    ap.add_argument("--por-sala", action="store_true")
    ap.add_argument("--entrada", default=None,
                    help="rect de entrada como 'c1,f1:c2,f2' (p. ej. '13,1:14,3')")
    ap.add_argument("--salida", default=None,
                    help="rect de salida como 'c1,f1:c2,f2'")
    args = ap.parse_args()

    global F_BOLD, F_SMALL
    F_BOLD, F_SMALL = cargar_fuentes()

    cfg = cargar_config(args.key)
    c2p, (x1, y1, x2, y4) = transformar(cfg)
    cfgm = cfg.get("elementos", {})

    with open(os.path.join(ROOT, "juegos/heroquest/data/misiones.json")) as f:
        misiones = json.load(f)
    mision = next((m for m in misiones if m["nombre"] == args.mision), None)
    if not mision:
        raise SystemExit(f"misón no encontrada: {args.mision}")

    outdir = args.salidas or os.path.dirname(args.mapa)
    os.makedirs(outdir, exist_ok=True)
    base = Image.open(args.mapa).convert("RGB")
    pre = slug(args.mision)
    guardadas = []

    # ---- Imagen maestra: rejilla con el ID de cada casilla ----
    grid, gd, gridpath = nueva(base, os.path.join(outdir, f"{pre}_rejilla.png"))
    retícula(gd, x1, y1, x2, y4)
    for col in range(1, COLS + 1):
        for fila in range(1, FILAS + 1):
            x, y = c2p(col, fila)
            txt = f"{col},{fila}"
            bb = gd.textbbox((0, 0), txt, font=F_SMALL)
            gd.text((x - (bb[2] - bb[0]) / 2, y - (bb[3] - bb[1]) / 2), txt,
                    fill=(0, 0, 255, 255), font=F_SMALL,
                    stroke_width=2, stroke_fill=(255, 255, 255, 255))
    grid.save(gridpath)
    guardadas.append(gridpath)

    # elemento -> [(col,fila,label)]
    tipos = {t: [] for t in TIPOS}
    for p in mision.get("entrada_heroes", []):
        tipos["entrada"].append((p["x"], p["y"], "IN"))
    for p in mision.get("puertas", []):
        tipos["puertas"].append(_puerta_punto(p, "P"))
    for p in mision.get("puertas_secretas", []):
        tipos["puertas"].append(_puerta_punto(p, "PS"))
    for sala in mision.get("salas", []):
        for m in sala.get("monstruos", []):
            tipos["monstruos"].append((m["x"], m["y"], f"M:{m['nombre']}"))
        for t in sala.get("tesoros", []):
            tipos["tesoros"].append((t["x"], t["y"], f"T:{t['nombre']}"))
        for t in sala.get("trampas", []):
            tipos["trampas"].append((t["x"], t["y"], f"TR:{t['nombre']}"))
        for mark in sala.get("marcadores", []):
            tipos["marcadores"].append((mark["x"], mark["y"], f"MAR:{mark['nombre']}"))
    for tipo_clave, tipo in (("monstruos", "monstruos"), ("tesoros", "tesoros"),
                             ("trampas", "trampas"), ("marcadores", "marcadores")):
        for it in mision.get("pasillos", {}).get(tipo_clave, []):
            tipos[tipo].append((it["x"], it["y"], f"{TIPOS[tipo][0]}:{it.get('nombre','')}"))
    for L in cfgm.get("letras", []):
        prefijo = TIPOS["letras"][0]
        for col, fila in L["casillas"]:
            tipos["letras"].append((col, fila, f"LETRA-{L['letra']}"))
    for col, fila in cfgm.get("exploradores_caidos", []):
        tipos["calaveras"].append((col, fila, "CALAVERA"))

    # ---- Una imagen por tipo ----
    for t, (pref, color) in TIPOS.items():
        if not tipos[t]:
            continue
        img, dr, path = nueva(base, os.path.join(outdir, f"{pre}_{t}.png"))
        retícula(dr, x1, y1, x2, y4)
        for col, fila, label in tipos[t]:
            if t == "puertas":
                col2 = color if label != "PS" else COLOR_SECRETA
            else:
                col2 = color
            cuadro(dr, c2p, col, fila, col2, label)
        img.save(path)
        guardadas.append(path)

    # ---- Entrada y salida como rectángulo de casillas con palabra debajo ----
    if args.entrada:
        c1, f1, c2, f2 = parse_rect(args.entrada)
        img, dr, path = nueva(base, os.path.join(outdir, f"{pre}_entrada_rect.png"))
        retícula(dr, x1, y1, x2, y4)
        rect_etiquetado(dr, c2p, c1, f1, c2, f2, TIPOS["entrada"][1], "ENTRADA")
        img.save(path)
        guardadas.append(path)
    if args.salida:
        c1, f1, c2, f2 = parse_rect(args.salida)
        img, dr, path = nueva(base, os.path.join(outdir, f"{pre}_salida_rect.png"))
        retícula(dr, x1, y1, x2, y4)
        rect_etiquetado(dr, c2p, c1, f1, c2, f2, (150, 0, 0, 255), "SALIDA")
        img.save(path)
        guardadas.append(path)

    # ---- Si --por-sala, imágenes separadas por sala para los tipos de sala ----
    if args.por_sala:
        for sala in mision.get("salas", []):
            n = sala.get("numero")
            for t in ("monstruos", "tesoros", "trampas", "marcadores"):
                items = []
                for m in sala.get(t, []):
                    items.append((m["x"], m["y"], f"{TIPOS[t][0]}:{m.get('nombre', '')}"))
                if not items:
                    continue
                pref, color = TIPOS[t]
                img, dr, path = nueva(base, os.path.join(
                    outdir, f"{pre}_sala{n:02d}_{t}.png"))
                retícula(dr, x1, y1, x2, y4)
                for col, fila, label in items:
                    cuadro(dr, c2p, col, fila, color, label)
                img.save(path)
                guardadas.append(path)

    print(f"{len(guardadas)} imágenes en {outdir}:")
    for p in guardadas:
        print("  ", p)


if __name__ == "__main__":
    main()

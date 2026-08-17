"""Genera una carta individual de HeroQuest (arma, armadura, poción, hechizo,
personaje o monstruo) en HTML y/o imagen PNG.

La carta imita el aspecto de las cartas de tesoro/hechizo del juego: borde
ornamentado, ilustración, estadísticas y coste.

Ejemplos:
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta"
    uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego" --formato png
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta" --formato ambos --salida /tmp/carta
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import tablero
from PIL import Image, ImageDraw, ImageFont

DATA_DIR = tablero.DATA_DIR
CARTAS_DIR = DATA_DIR.parent / "cartas"

TIPOS = ("arma", "armadura", "pocion", "hechizo", "personaje", "monstruo")
FORMATOS = ("html", "png", "ambos")

# Paleta de carta por tipo (fondos de la franja decorativa)
COLOR_BANDA = {
    "arma": "#5d4037",
    "armadura": "#3e5f8a",
    "pocion": "#2e7d32",
    "hechizo": "#6a3d8a",
    "personaje": "#9c2b2b",
    "monstruo": "#1f1f1f",
}

COLOR_BANDA_RGB = {
    "arma": (93, 64, 55),
    "armadura": (62, 95, 138),
    "pocion": (46, 125, 50),
    "hechizo": (106, 61, 138),
    "personaje": (156, 43, 43),
    "monstruo": (31, 31, 31),
}

# Colores usados en la carta
COLOR_FONDO_CLARO = (247, 240, 221)
COLOR_FONDO_OSCURO = (234, 223, 200)
COLOR_BORDE = (138, 109, 59)
COLOR_TEXTO_OSCURO = (93, 64, 55)
COLOR_STAT_BG = (251, 246, 234)
COLOR_STAT_BORDE = (138, 109, 59)


def _cargar(tipo: str) -> list[dict]:
    ruta = DATA_DIR / f"{tipo}.json"
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def _buscar(tipo: str, nombre: str) -> dict:
    fichero = {
        "arma": "armas",
        "armadura": "armas",
        "pocion": "armas",
        "hechizo": "hechizos",
        "personaje": "personajes",
        "monstruo": "monstruos",
    }[tipo]
    for e in _cargar(fichero):
        if e["nombre"] == nombre:
            return e
    print(f"Error: no existe '{nombre}' en {fichero}.json")
    sys.exit(1)


def _slug(nombre: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in nombre).strip("_")


def _pieza_central(entrada: dict, tipo: str) -> str:
    """SVG decorativo para el recuadro de la carta (sustituye a la ilustración)."""
    color = COLOR_BANDA[tipo]
    simbolo = {
        "arma": "⚔",
        "armadura": "🛡",
        "pocion": "⚗",
        "hechizo": "✦",
        "personaje": "🜄",
        "monstruo": "☠",
    }[tipo]
    return f"""
    <div class="arte" role="img" aria-label="Ilustración de {html.escape(entrada['nombre'])}">
      <svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="{color}"/>
            <stop offset="1" stop-color="#111"/>
          </linearGradient>
        </defs>
        <rect width="200" height="120" fill="url(#g)"/>
        <circle cx="100" cy="60" r="34" fill="none" stroke="#f4e9d2" stroke-width="2" opacity=".5"/>
        <text x="100" y="78" font-size="52" text-anchor="middle">{simbolo}</text>
      </svg>
    </div>"""


def _cuerpo(entrada: dict, tipo: str) -> str:
    if tipo in ("arma", "armadura", "pocion"):
        stats = []
        if entrada.get("ataque"):
            stats.append(f'<div class="stat"><span class="svalor">{entrada["ataque"]}</span><span class="srotulo">Ataque</span></div>')
        if entrada.get("defensa"):
            stats.append(f'<div class="stat"><span class="svalor">{entrada["defensa"]}</span><span class="srotulo">Defensa</span></div>')
        stats.append(f'<div class="stat"><span class="svalor">{entrada["coste"]}</span><span class="srotulo">Coste</span></div>')
        return (
            f'<div class="tipo">{html.escape(entrada["tipo"])}</div>'
            f'<div class="stats">{"" .join(stats)}</div>'
            f'<p class="texto">{html.escape(entrada.get("descripcion", ""))}</p>'
        )
    if tipo == "hechizo":
        return (
            f'<div class="tipo">Hechizo de {html.escape(entrada["escuela"])}</div>'
            f'<div class="stats"><div class="stat"><span class="svalor">{entrada["coste_mente"]}</span><span class="srotulo">Mente</span></div></div>'
            f'<p class="texto">{html.escape(entrada.get("descripcion", ""))}</p>'
        )
    if tipo == "personaje":
        return (
            f'<div class="tipo">Héroe · {html.escape(entrada["clase"])}</div>'
            f'<div class="stats">'
            f'<div class="stat"><span class="svalor">{entrada["ataque"]}</span><span class="srotulo">Ataque</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["defensa"]}</span><span class="srotulo">Defensa</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["cuerpo"]}</span><span class="srotulo">Cuerpo</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["mente"]}</span><span class="srotulo">Mente</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["movimiento"]}</span><span class="srotulo">Mov</span></div>'
            f'</div>'
            f'<p class="texto">{html.escape(entrada.get("descripcion", ""))}</p>'
        )
    if tipo == "monstruo":
        return (
            f'<div class="tipo">Monstruo</div>'
            f'<div class="stats">'
            f'<div class="stat"><span class="svalor">{entrada["ataque"]}</span><span class="srotulo">Ataque</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["defensa"]}</span><span class="srotulo">Defensa</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["cuerpo"]}</span><span class="srotulo">Cuerpo</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["mente"]}</span><span class="srotulo">Mente</span></div>'
            f'<div class="stat"><span class="svalor">{entrada["movimiento"]}</span><span class="srotulo">Mov</span></div>'
            f'</div>'
            f'<p class="texto">{html.escape(entrada.get("descripcion", ""))}</p>'
        )
    return ""


def _render(entrada: dict, tipo: str) -> str:
    """Render HTML representation of a card (unchanged)."""
    nombre = html.escape(entrada["nombre"])
    return f"""<!DOCTYPE html>
<html lang=\"es\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{nombre} · Carta HeroQuest</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:#333 url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"60\" height=\"60\"><path d=\"M0 30h60M30 0v60\" stroke=\"%23444\" stroke-width=\"1\"/></svg>');
    font-family:Georgia,'Times New Roman',serif;
  }}
  .carta {{
    width:340px; min-height:480px; background:linear-gradient(180deg,#f7f0dd,#eadfc8);
    border:10px double #8a6d3b; border-radius:14px; padding:14px 16px 18px;
    box-shadow:0 10px 30px rgba(0,0,0,.5); display:flex; flex-direction:column; gap:10px;
  }}
  .nombre {{ text-align:center; font-size:1.35rem; font-weight:bold; letter-spacing:.5px; }}
  .tipo {{ text-align:center; font-size:.85rem; color:#8a6d3b; text-transform:uppercase; letter-spacing:1px; }}
  .arte {{ border:3px solid #5d4037; border-radius:8px; overflow:hidden; }}
  .arte svg {{ display:block; width:100%; height:auto; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }}
  .stat {{
    background:#fbf6ea; border:2px solid #8a6d3b; border-radius:8px;
    padding:6px 12px; min-width:56px; text-align:center;
  }}
  .svalor {{ display:block; font-size:1.4rem; font-weight:bold; line-height:1; }}
  .srotulo {{ display:block; font-size:.68rem; text-transform:uppercase; letter-spacing:.5px; color:#8a6d3b; }}
  .texto {{ margin:0; font-size:.95rem; font-style:italic; text-align:center; line-height:1.45; }}
  .marco {{ border-top:2px solid #8a6d3b; border-bottom:2px solid #8a6d3b; padding:8px 0; text-align:center; font-size:.8rem; color:#5d4037; margin-top:auto; }}
</style>
</head>
<body>
  <div class="carta">
    <div class="nombre">{nombre}</div>
    {_pieza_central(entrada, tipo)}
    {_cuerpo(entrada, tipo)}
    <div class="marco">Hero Quest · Ficha de juego</div>
  </div>
</body>
</html>"""


def _render_image(entrada: dict, tipo: str) -> Image.Image:
    """Render a PNG image of the card using Pillow."""
    # Card dimensions (px) – match the HTML layout
    ancho, alto = 340, 480
    # Create base image with gradient background
    img = Image.new("RGB", (ancho, alto), COLOR_FONDO_CLARO)
    draw = ImageDraw.Draw(img)
    # Vertical gradient from claro to oscuro
    for y in range(alto):
        ratio = y / alto
        r = int(COLOR_FONDO_CLARO[0] * (1 - ratio) + COLOR_FONDO_OSCURO[0] * ratio)
        g = int(COLOR_FONDO_CLARO[1] * (1 - ratio) + COLOR_FONDO_OSCURO[1] * ratio)
        b = int(COLOR_FONDO_CLARO[2] * (1 - ratio) + COLOR_FONDO_OSCURO[2] * ratio)
        draw.line([(0, y), (ancho, y)], fill=(r, g, b))
    # Double border – two rounded rectangles to mimic HTML double border
    radius = 14
    # Outer rounded border
    draw.rounded_rectangle([0, 0, ancho - 1, alto - 1], radius=radius, outline=COLOR_BORDE, width=10)
    # Inner rounded border (inset by 5px)
    inset = 5
    draw.rounded_rectangle([inset, inset, ancho - 1 - inset, alto - 1 - inset], radius=radius-2, outline=COLOR_BORDE, width=2)
    # Load a basic font (fallback to default)
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except Exception:
        font_title = ImageFont.load_default()
        font_small = ImageFont.load_default()
    # Title (nombre) centered near top
    title = entrada.get("nombre", "")
    bbox = draw.textbbox((0, 0), title, font=font_title)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((ancho - w) / 2, 8), title, fill=COLOR_TEXTO_OSCURO, font=font_title)
    # Central band (simulated) – 200x120 rectangle centered
    banda_w, banda_h = 200, 120
    banda_x = (ancho - banda_w) // 2
    banda_y = 60
    # Gradient for band using its specific color to dark (#111)
    band_color = COLOR_BANDA_RGB[tipo]
    for yy in range(banda_h):
        ratio = yy / banda_h
        r = int(band_color[0] * (1 - ratio) + 17 * ratio)
        g = int(band_color[1] * (1 - ratio) + 17 * ratio)
        b = int(band_color[2] * (1 - ratio) + 17 * ratio)
        draw.line([(banda_x, banda_y + yy), (banda_x + banda_w, banda_y + yy)], fill=(r, g, b))
    # Symbol in center of band
    simbolo = {
        "arma": "⚔",
        "armadura": "🛡",
        "pocion": "⚗",
        "hechizo": "✦",
        "personaje": "🜄",
        "monstruo": "☠",
    }[tipo]
    bbox_sym = draw.textbbox((0, 0), simbolo, font=font_small)
    sw, sh = bbox_sym[2] - bbox_sym[0], bbox_sym[3] - bbox_sym[1]
    draw.text((banda_x + (banda_w - sw) // 2, banda_y + (banda_h - sh) // 2), simbolo, fill=(255, 255, 255), font=font_small)
    # Stats – render as rounded boxes similar to HTML
    stats_lines = []
    if tipo in ("arma", "armadura", "pocion"):
        if entrada.get("ataque"):
            stats_lines.append(("Ataque", str(entrada['ataque'])))
        if entrada.get("defensa"):
            stats_lines.append(("Defensa", str(entrada['defensa'])))
        stats_lines.append(("Coste", str(entrada['coste'])))
    elif tipo == "hechizo":
        stats_lines.append(("Mente", str(entrada['coste_mente'])))
    elif tipo == "personaje":
        stats_lines.extend([
            ("Ataque", str(entrada['ataque'])),
            ("Defensa", str(entrada['defensa'])),
            ("Cuerpo", str(entrada['cuerpo'])),
            ("Mente", str(entrada['mente'])),
            ("Mov", str(entrada['movimiento'])),
        ])
    elif tipo == "monstruo":
        stats_lines.extend([
            ("Ataque", str(entrada['ataque'])),
            ("Defensa", str(entrada['defensa'])),
            ("Cuerpo", str(entrada['cuerpo'])),
            ("Mente", str(entrada['mente'])),
            ("Mov", str(entrada['movimiento'])),
        ])
    # Prepare boxes layout (centered horizontally)
    gap = 8
    boxes = []
    for label, value in stats_lines:
        text = f"{value}"
        # Measure text size
        tb = draw.textbbox((0, 0), text, font=font_small)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        # Box size with padding similar to HTML (horizontal padding ~12, vertical ~6)
        box_w = tw + 24
        box_h = th + 12
        boxes.append((text, box_w, box_h, tw, th))
    total_width = sum(bw for _, bw, _, _, _ in boxes) + gap * (len(boxes) - 1)
    start_x = (ancho - total_width) // 2
    y_box = banda_y + banda_h + 20
    for (text, bw, bh, tw, th), (label, _) in zip(boxes, stats_lines):
        # Draw rounded rectangle for each stat
        draw.rounded_rectangle([
            (start_x, y_box),
            (start_x + bw, y_box + bh)
        ], radius=8, fill=COLOR_STAT_BG, outline=COLOR_STAT_BORDE, width=2)
        # Center text inside the box
        txt_x = start_x + (bw - tw) // 2
        txt_y = y_box + (bh - th) // 2
        draw.text((txt_x, txt_y), text, fill=COLOR_TEXTO_OSCURO, font=font_small)
        start_x += bw + gap
    # Footer – same style as HTML (simple centered text)
    footer = "Hero Quest · Ficha de juego"
    # Draw decorative frame similar to HTML .marco (top and bottom borders)
    marco_y_top = alto - 30
    marco_y_bottom = alto - 22
    draw.line([(20, marco_y_top), (ancho - 20, marco_y_top)], fill=COLOR_BORDE, width=2)
    draw.line([(20, marco_y_bottom), (ancho - 20, marco_y_bottom)], fill=COLOR_BORDE, width=2)
    # Centered footer text between the lines
    bbox_f = draw.textbbox((0, 0), footer, font=font_small)
    fw, fh = bbox_f[2] - bbox_f[0], bbox_f[3] - bbox_f[1]
    draw.text(((ancho - fw) // 2, marco_y_top + (marco_y_bottom - marco_y_top - fh) // 2),
              footer, fill=COLOR_TEXTO_OSCURO, font=font_small)
    return img



def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una carta individual de HeroQuest en HTML y/o PNG")
    parser.add_argument("--tipo", required=True, choices=TIPOS, help="Tipo de carta")
    parser.add_argument("--nombre", required=True, help="Nombre de la entrada")
    parser.add_argument("--salida", default=None, help="Ruta base de salida (sin extensión). Por defecto en cartas/ con nombre auto‑generado")
    parser.add_argument("--formato", choices=FORMATOS, default="ambos", help="Formato(s) a generar: html, png o ambos (predeterminado)")
    args = parser.parse_args()

    entrada = _buscar(args.tipo, args.nombre)
    # Determine base path (without extension)
    base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{args.tipo}__{_slug(args.nombre)}"
    base.parent.mkdir(parents=True, exist_ok=True)
    # Generate HTML if requested
    if args.formato in ("html", "ambos"):
        html_path = base.with_suffix('.html')
        html_path.write_text(_render(entrada, args.tipo), encoding="utf-8")
        print(f"HTML: {html_path}")
    # Generate PNG if requested
    if args.formato in ("png", "ambos"):
        png_path = base.with_suffix('.png')
        img = _render_image(entrada, args.tipo)
        img.save(png_path)
        print(f"PNG: {png_path}")


if __name__ == "__main__":
    main()
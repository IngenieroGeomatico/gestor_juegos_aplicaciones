"""Genera una carta individual de HeroQuest (arma, armadura, poción, hechizo,
personaje o monstruo) en un HTML autocontenido.

La carta imita el aspecto de las cartas de tesoro/hechizo del juego: borde
ornamentado, ilustración, estadísticas y coste.

Ejemplos:
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta"
    uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego"
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta" --salida /tmp/carta.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import tablero

DATA_DIR = tablero.DATA_DIR
CARTAS_DIR = DATA_DIR.parent / "cartas"

TIPOS = ("arma", "armadura", "pocion", "hechizo", "personaje", "monstruo")

# Paleta de carta por tipo (fondos de la franja decorativa)
COLOR_BANDA = {
    "arma": "#5d4037",
    "armadura": "#3e5f8a",
    "pocion": "#2e7d32",
    "hechizo": "#6a3d8a",
    "personaje": "#9c2b2b",
    "monstruo": "#1f1f1f",
}


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
    nombre = html.escape(entrada["nombre"])
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{nombre} · Carta HeroQuest</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:#333 url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><path d="M0 30h60M30 0v60" stroke="%23444" stroke-width="1"/></svg>');
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una carta individual de HeroQuest en HTML")
    parser.add_argument("--tipo", required=True, choices=TIPOS, help="Tipo de carta")
    parser.add_argument("--nombre", required=True, help="Nombre de la entrada")
    parser.add_argument("--salida", default=None, help="Ruta HTML de salida (por defecto en cartas/)")
    args = parser.parse_args()

    entrada = _buscar(args.tipo, args.nombre)
    ruta = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{args.tipo}__{_slug(args.nombre)}.html"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(_render(entrada, args.tipo), encoding="utf-8")
    print(f"HTML: {ruta}")


if __name__ == "__main__":
    main()
"""Genera una carta individual de HeroQuest (arma, armadura, poción, hechizo,
personaje o monstruo) con aspecto de carta de juego.

Este script es un orquestador: no conoce el diseño ni los campos de cada tipo.
Cada tipo de carta vive en el paquete `tipos_carta/` y el dibujo lo hace
`render_carta.py` (anverso en SVG y en PNG). Aquí solo se localiza la entrada,
se pide el render y se escribe el fichero.

Formatos:
- `html`: ficha autocontenida con el anverso (SVG, nítido y escalable) y, si
  existe, el reverso de la carta como imagen.
- `png`: imagen del anverso dibujada con Pillow.
- `doble`: hoja plegable (anverso | reverso lado a lado) en SVG y PNG, para
  imprimir, doblar por la línea central y obtener la carta completa.
- `ambos` (por defecto): genera los dos.

Ejemplos:
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta"
    uv run juegos/heroquest/scripts/carta_item.py --tipo hechizo --nombre "Bola de fuego" --formato doble
"""

from __future__ import annotations

import argparse
import base64
import html
import sys
from pathlib import Path

import data_store
import render_carta
import tipos_carta

CARTAS_DIR = data_store.DATA_DIR.parent / "cartas"

FORMATOS = ("html", "png", "doble", "ambos")


def _buscar(tipo: tipos_carta.TipoCarta, nombre: str) -> dict:
    """Localiza la entrada por nombre dentro del fichero del tipo."""
    for entrada in data_store.cargar(tipo.fichero):
        if entrada.get("nombre") == nombre:
            # En ficheros compartidos (armas.json) confirmamos el subtipo.
            if tipos_carta.tipo_de_entrada(tipo.fichero, entrada).id != tipo.id:
                continue
            return entrada
    print(f"Error: no existe '{nombre}' de tipo '{tipo.id}' en {tipo.fichero}.json")
    sys.exit(1)


def _reverso_data_uri(tipo: tipos_carta.TipoCarta) -> str | None:
    """Devuelve el reverso como data URI base64, o None si no hay imagen."""
    ruta = tipo.reverso()
    if not ruta.exists():
        return None
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    sufijo = ruta.suffix.lower().lstrip(".")
    mime = "jpeg" if sufijo in ("jpg", "jpeg") else sufijo
    return f"data:image/{mime};base64,{datos}"


def _html(tipo: tipos_carta.TipoCarta, entrada: dict) -> str:
    """Ficha HTML autocontenida con anverso (SVG), reverso (imagen) y hoja plegable."""
    svg = render_carta.render_svg(tipo, entrada)
    doble = render_carta.render_svg_doble(tipo, entrada)
    reverso = _reverso_data_uri(tipo)
    reverso_html = (
        f'<figure><img src="{reverso}" alt="Reverso de la carta"><figcaption>Reverso</figcaption></figure>'
        if reverso
        else ""
    )
    titulo = html.escape(entrada.get("nombre", ""))
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo} · Carta HeroQuest</title>
<style>
  body {{ margin:0; min-height:100vh; display:flex; gap:24px; flex-wrap:wrap;
    align-items:center; justify-content:center; background:#2b2b2b; padding:24px;
    font-family:Georgia,'Times New Roman',serif; }}
  figure {{ margin:0; text-align:center; color:#e8d9b8; }}
  .anverso, figure img {{ width:340px; height:auto; border-radius:12px;
    box-shadow:0 10px 30px rgba(0,0,0,.5); background:#f3ecdd; }}
  .doble svg {{ width:680px; height:auto; border-radius:12px;
    box-shadow:0 10px 30px rgba(0,0,0,.5); }}
  figcaption {{ margin-top:8px; font-size:.9rem; letter-spacing:.5px; }}
</style>
</head>
<body>
  <figure>
    <div class="anverso">{svg}</div>
    <figcaption>Anverso</figcaption>
  </figure>
  {reverso_html}
  <figure>
    <div class="doble">{doble}</div>
    <figcaption>Hoja plegable: imprime, dobla por la línea central y recórtala</figcaption>
  </figure>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera una carta individual de HeroQuest en HTML y/o PNG",
    )
    parser.add_argument("--tipo", required=True, choices=list(tipos_carta.TIPOS), help="Tipo de carta")
    parser.add_argument("--nombre", required=True, help="Nombre de la entrada")
    parser.add_argument("--salida", default=None,
                        help="Ruta base de salida (sin extensión). Por defecto en cartas/")
    parser.add_argument("--formato", choices=FORMATOS, default="ambos",
                        help="Formato(s) a generar: html, png, doble o ambos (predeterminado)")
    args = parser.parse_args()

    tipo = tipos_carta.obtener(args.tipo)
    entrada = _buscar(tipo, args.nombre)

    base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{tipo.id}__{data_store.slug(args.nombre)}"
    base.parent.mkdir(parents=True, exist_ok=True)

    if args.formato in ("html", "ambos"):
        ruta_html = base.with_suffix(".html")
        ruta_html.write_text(_html(tipo, entrada), encoding="utf-8")
        print(f"HTML: {ruta_html}")

    if args.formato in ("png", "ambos"):
        ruta_png = base.with_suffix(".png")
        render_carta.render_png(tipo, entrada).save(ruta_png)
        print(f"PNG: {ruta_png}")

    if args.formato in ("doble",):
        base_doble = Path(str(base) + "__doble")
        (base_doble.with_suffix(".svg")).write_text(
            render_carta.render_svg_doble(tipo, entrada), encoding="utf-8")
        render_carta.render_png_doble(tipo, entrada).save(base_doble.with_suffix(".png"))
        print(f"Hoja plegable: {base_doble.with_suffix('.svg')} y {base_doble.with_suffix('.png')}")


if __name__ == "__main__":
    main()

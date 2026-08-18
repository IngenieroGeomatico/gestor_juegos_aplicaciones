"""Genera una carta individual de HeroQuest (arma, armadura, poción, hechizo,
personaje o monstruo) con aspecto de carta de juego.

Este script es un orquestador: no conoce el diseño ni los campos de cada tipo.
Cada tipo de carta vive en el paquete `tipos_carta/` y el dibujo lo hace
`render_carta.py` (anverso en SVG y en PNG). Aquí solo se localiza la entrada,
se pide el render y se escribe el fichero.

Formatos (`--formato`, varios separados por coma):
- `png`: imagen del anverso (o de la carta completa si `--carta_completa`).
- `svg`: vector del anverso (o de la carta completa si `--carta_completa`).
- `html`: ficha de previsualización (opcional) con anverso, reverso y hoja
  plegable.

`--carta_completa`: genera la carta con sus dos caras (anverso | reverso lado a
lado en una hoja plegable); sin él se genera solo la cara delantera.

Ejemplos:
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta"
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta" --carta_completa
    uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta" --formato svg,png --carta_completa
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

FORMATOS = ("png", "svg", "html")


def _formato_lista(valor: str) -> list[str]:
    """Parsea '--formato svg,png' a una lista de formatos válidos."""
    formatos = [f.strip().lower() for f in valor.split(",") if f.strip()]
    invalidos = [f for f in formatos if f not in FORMATOS]
    if invalidos:
        raise argparse.ArgumentTypeError(
            f"Formato(s) no válidos: {', '.join(invalidos)}. Válidos: {', '.join(FORMATOS)}")
    return formatos


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


def _reverso_data_uri(tipo: tipos_carta.TipoCarta, fondo_verso: str | None = None) -> str | None:
    """Devuelve el reverso como data URI base64, o None si no hay imagen.

    `fondo_verso` (nombre de fichero en sources/arte_fondos/) sustituye la foto
    estándar del reverso del tipo.
    """
    ruta = render_carta._ruta_reverso(tipo, fondo_verso)
    if not ruta.exists():
        return None
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    sufijo = ruta.suffix.lower().lstrip(".")
    mime = "jpeg" if sufijo in ("jpg", "jpeg") else sufijo
    return f"data:image/{mime};base64,{datos}"


def _html(tipo: tipos_carta.TipoCarta, entrada: dict, fondo_verso: str | None = None) -> str:
    """Ficha HTML autocontenida con anverso (SVG), reverso (imagen) y hoja plegable."""
    svg = render_carta.render_svg(tipo, entrada)
    doble = render_carta.render_svg_doble(tipo, entrada, fondo_verso=fondo_verso)
    reverso = _reverso_data_uri(tipo, fondo_verso)
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
    parser.add_argument("--formato", type=_formato_lista, default=["png"],
                        help="Formato(s) a generar, separados por coma: png, svg, html (predeterminado: png)")
    parser.add_argument("--carta_completa", action="store_true",
                        help="Genera la carta con las dos caras (anverso | reverso; solo png/svg)")
    parser.add_argument("--fondo_verso", default=None,
                        help="Imagen de fondo para el reverso, buscada en sources/arte_fondos/ "
                             "(p. ej. 'armario_armas.png'); por defecto usa la foto estándar del tipo")
    args = parser.parse_args()

    tipo = tipos_carta.obtener(args.tipo)
    entrada = _buscar(tipo, args.nombre)

    if args.fondo_verso:
        fondo = render_carta.FONDOS_DIR / args.fondo_verso
        if not fondo.exists():
            print(f"Error: no existe el fondo de reverso '{args.fondo_verso}' en {render_carta.FONDOS_DIR}")
            sys.exit(1)

    base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{tipo.id}__{data_store.slug(args.nombre)}"
    base.parent.mkdir(parents=True, exist_ok=True)

    if "html" in args.formato:
        ruta_html = base.with_suffix(".html")
        ruta_html.write_text(_html(tipo, entrada, args.fondo_verso), encoding="utf-8")
        print(f"HTML: {ruta_html}")

    if "svg" in args.formato:
        base_salida = Path(str(base) + ("__completa" if args.carta_completa else ""))
        ruta = base_salida.with_suffix(".svg")
        svg = (render_carta.render_svg_doble(tipo, entrada, fondo_verso=args.fondo_verso)
               if args.carta_completa else render_carta.render_svg(tipo, entrada))
        ruta.write_text(svg, encoding="utf-8")
        print(f"SVG: {ruta}")

    if "png" in args.formato:
        base_salida = Path(str(base) + ("__completa" if args.carta_completa else ""))
        ruta = base_salida.with_suffix(".png")
        img = (render_carta.render_png_doble(tipo, entrada, fondo_verso=args.fondo_verso)
               if args.carta_completa else render_carta.render_png(tipo, entrada))
        img.save(ruta)
        print(f"PNG: {ruta}")


if __name__ == "__main__":
    main()

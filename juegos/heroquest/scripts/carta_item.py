"""Genera la carta individual de un héroe/personaje de HeroQuest.

El dibujo lo hace el motor guiado por datos `render_personaje.py`: la *receta*
de la carta (plantillas y assets, para anverso y dorso) vive en el propio JSON
del personaje, bajo la clave `plantillas`. Aquí solo se localiza la entrada, se
pide el render de la cara solicitada y se escribe el fichero.

Solo se soporta el tipo `personaje` (héroes). Se puede generar el anverso, el
dorso o ambas caras, en PNG y/o SVG.

Ejemplos:
    uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro"
    uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro" --cara dorso
    uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro" --cara ambas --formato svg,png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import data_store
import render_personaje

CARTAS_DIR = data_store.DATA_DIR.parent / "cartas"

FORMATOS = ("png", "svg")
CARAS = ("anverso", "dorso", "ambas")

FICHERO_PERSONAJES = "personajes"


def _formato_lista(valor: str) -> list[str]:
    """Parsea '--formato svg,png' a una lista de formatos válidos."""
    formatos = [f.strip().lower() for f in valor.split(",") if f.strip()]
    invalidos = [f for f in formatos if f not in FORMATOS]
    if invalidos:
        raise argparse.ArgumentTypeError(
            f"Formato(s) no válidos: {', '.join(invalidos)}. Válidos: {', '.join(FORMATOS)}")
    return formatos


def _buscar(nombre: str) -> dict:
    """Localiza la entrada del personaje por nombre en personajes.json."""
    for entrada in data_store.cargar(FICHERO_PERSONAJES):
        if entrada.get("nombre") == nombre:
            return entrada
    print(f"Error: no existe el héroe '{nombre}' en {FICHERO_PERSONAJES}.json")
    sys.exit(1)


def _escribir_cara(entrada: dict, sufijo: str, base: Path, formatos: list[str],
                   render_svg, render_png) -> None:
    """Genera los ficheros (svg/png) de una cara con las funciones de render dadas."""
    destino = Path(f"{base}__{sufijo}") if sufijo else base
    if "svg" in formatos:
        ruta = destino.with_suffix(".svg")
        ruta.write_text(render_svg(entrada), encoding="utf-8")
        print(f"SVG: {ruta}")
    if "png" in formatos:
        ruta = destino.with_suffix(".png")
        render_png(entrada).save(ruta)
        print(f"PNG: {ruta}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera la carta de un héroe de HeroQuest (anverso/dorso) en PNG y/o SVG",
    )
    parser.add_argument("--nombre", required=True, help="Nombre del héroe")
    parser.add_argument("--cara", choices=CARAS, default="anverso",
                        help="Cara a generar: anverso, dorso o ambas (predeterminado: anverso)")
    parser.add_argument("--salida", default=None,
                        help="Ruta base de salida (sin extensión). Por defecto en cartas/")
    parser.add_argument("--formato", type=_formato_lista, default=["png"],
                        help="Formato(s) a generar, separados por coma: png, svg (predeterminado: png)")
    args = parser.parse_args()

    entrada = _buscar(args.nombre)

    base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_personaje__{data_store.slug(args.nombre)}"
    base.parent.mkdir(parents=True, exist_ok=True)

    # Con una sola cara y --salida, no se añade sufijo (respeta la ruta exacta);
    # con 'ambas' siempre se distingue anverso/dorso.
    if args.cara in ("anverso", "ambas"):
        sufijo = "anverso" if args.cara == "ambas" else ""
        _escribir_cara(entrada, sufijo, base, args.formato,
                       render_personaje.render_svg, render_personaje.render_png)
    if args.cara in ("dorso", "ambas"):
        sufijo = "dorso" if args.cara == "ambas" else ""
        _escribir_cara(entrada, sufijo, base, args.formato,
                       render_personaje.render_svg_verso, render_personaje.render_png_verso)


if __name__ == "__main__":
    main()

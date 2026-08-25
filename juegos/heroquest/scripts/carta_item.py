"""Genera la carta individual de un héroe o monstruo de HeroQuest.

El dibujo lo hace el motor guiado por datos `render_personaje.py`: la *receta*
de la carta (plantillas y assets, para anverso y dorso) vive en el propio JSON
de la entrada, bajo la clave `plantillas`. Aquí solo se localiza la entrada (en
`personajes.json` y, si no está, en `monstruos.json`), se pide el render de la
cara solicitada y se escribe el fichero.

Se puede generar el anverso, el dorso o ambas caras, en PNG y/o SVG.

Ejemplos:
    uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro"
    uv run juegos/heroquest/scripts/carta_item.py --nombre "Bárbaro" --cara dorso
    uv run juegos/heroquest/scripts/carta_item.py --nombre "Trasgo" --cara ambas --formato svg,png
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

FICHEROS_TIPO = ("personajes", "monstruos")


def _formato_lista(valor: str) -> list[str]:
    """Parsea '--formato svg,png' a una lista de formatos válidos."""
    formatos = [f.strip().lower() for f in valor.split(",") if f.strip()]
    invalidos = [f for f in formatos if f not in FORMATOS]
    if invalidos:
        raise argparse.ArgumentTypeError(
            f"Formato(s) no válidos: {', '.join(invalidos)}. Válidos: {', '.join(FORMATOS)}")
    return formatos


def _buscar(nombre: str) -> tuple[str, dict]:
    """Localiza la entrada por nombre (personajes.json, luego monstruos.json).

    Devuelve (fichero, entrada) para poder nombrar la salida
    (carta_personaje__…/carta_monstruo__…).
    """
    for fichero in FICHEROS_TIPO:
        for entrada in data_store.cargar(fichero):
            if entrada.get("nombre") == nombre:
                return fichero, entrada
    print(f"Error: no existe '{nombre}' en personajes.json ni en monstruos.json")
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
        description="Genera la carta de un héroe o monstruo de HeroQuest (anverso/dorso) en PNG y/o SVG",
    )
    parser.add_argument("--nombre", required=True, help="Nombre del héroe o monstruo")
    parser.add_argument("--cara", choices=CARAS, default="anverso",
                        help="Cara a generar: anverso, dorso o ambas (predeterminado: anverso)")
    parser.add_argument("--salida", default=None,
                        help="Ruta base de salida (sin extensión). Por defecto en cartas/")
    parser.add_argument("--formato", type=_formato_lista, default=["png"],
                        help="Formato(s) a generar, separados por coma: png, svg (predeterminado: png)")
    args = parser.parse_args()

    fichero, entrada = _buscar(args.nombre)

    tipo_carta = fichero[:-1]  # "personajes" → "personaje", "monstruos" → "monstruo"
    base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{tipo_carta}__{data_store.slug(args.nombre)}"
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

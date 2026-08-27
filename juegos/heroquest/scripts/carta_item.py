"""Genera la carta individual de un héroe, monstruo o item de HeroQuest.

Para héroes y monstruos usa las plantillas hero-card/monster-card.
Para items (armas, pociones, hechizos) usa la plantilla generic-card.

Ejemplos:
    uv run carta_item.py --nombre "Bárbaro"
    uv run carta_item.py --nombre "Daga"
    uv run carta_item.py --nombre "Bola de fuego"
    uv run carta_item.py --nombre "Trasgo" --cara ambas --formato svg,png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import data_store
import render_personaje
import render_generico

CARTAS_DIR = data_store.DATA_DIR.parent / "cartas"

FORMATOS = ("png", "svg")
CARAS = ("anverso", "dorso", "ambas")

# JSONs de items (usan plantilla genérica)
FICHEROS_ITEMS = ("armas", "hechizos")

# JSONs de personajes/monstruos (usan plantillas específicas)
FICHEROS_TIPO = ("personajes", "monstruos")


def _formato_lista(valor: str) -> list[str]:
    """Parsea '--formato svg,png' a una lista de formatos válidos."""
    formatos = [f.strip().lower() for f in valor.split(",") if f.strip()]
    invalidos = [f for f in formatos if f not in FORMATOS]
    if invalidos:
        raise argparse.ArgumentTypeError(
            f"Formato(s) no válidos: {', '.join(invalidos)}. Válidos: {', '.join(FORMATOS)}")
    return formatos


def _buscar(nombre: str) -> tuple[str, dict, bool]:
    """Localiza la entrada por nombre en todos los JSONs.
    
    Devuelve (fichero, entrada, es_item).
    """
    # Primero buscar en items
    for fichero in FICHEROS_ITEMS:
        for entrada in data_store.cargar(fichero):
            if entrada.get("nombre") == nombre:
                return fichero, entrada, True
    
    # Luego en personajes/monstruos
    for fichero in FICHEROS_TIPO:
        for entrada in data_store.cargar(fichero):
            if entrada.get("nombre") == nombre:
                return fichero, entrada, False
    
    print(f"Error: no existe '{nombre}' en ningún JSON")
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
        description="Genera cartas de HeroQuest (héroes, monstruos, items)",
    )
    parser.add_argument("--nombre", required=True, help="Nombre del elemento")
    parser.add_argument("--cara", choices=CARAS, default="anverso",
                        help="Cara a generar: anverso, dorso o ambas (predeterminado: anverso)")
    parser.add_argument("--salida", default=None,
                        help="Ruta base de salida (sin extensión). Por defecto en cartas/")
    parser.add_argument("--formato", type=_formato_lista, default=["png"],
                        help="Formato(s) a generar, separados por coma: png, svg (predeterminado: png)")
    args = parser.parse_args()

    fichero, entrada, es_item = _buscar(args.nombre)

    if es_item:
        # Items: usar plantilla genérica
        tipo_carta = fichero  # "armas", "hechizos"
        base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{tipo_carta}__{data_store.slug(args.nombre)}"
        base.parent.mkdir(parents=True, exist_ok=True)

        if args.cara in ("anverso", "ambas"):
            sufijo = "anverso" if args.cara == "ambas" else ""
            _escribir_cara(entrada, sufijo, base, args.formato,
                           render_generico.render_svg, render_generico.render_png)
        if args.cara in ("dorso", "ambas"):
            sufijo = "dorso" if args.cara == "ambas" else ""
            _escribir_cara(entrada, sufijo, base, args.formato,
                           render_generico.render_svg_verso, render_generico.render_png_verso)
    else:
        # Héroes/monstruos: usar plantillas específicas
        tipo_carta = "personaje" if fichero == "personajes" else "monstruo"
        base = Path(args.salida) if args.salida else CARTAS_DIR / f"carta_{tipo_carta}__{data_store.slug(args.nombre)}"
        base.parent.mkdir(parents=True, exist_ok=True)

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

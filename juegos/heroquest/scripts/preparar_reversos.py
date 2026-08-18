"""Prepara los reversos de las cartas a partir de las fotos de `sources/`.

Las imágenes `*_back.jpg` de `sources/` son fotos de las cartas reales sobre una
mesa. Este script las recorta (quitando el fondo de la mesa por detección de
bordes) y las endereza a orientación vertical (retrato), guardando un reverso
limpio en `sources/reversos/` listo para componer con el anverso.

Solo usa Pillow (sin OpenCV): el recorte es una heurística por diferencia de
color respecto al fondo de las esquinas; suficiente para fotos con la carta
razonablemente centrada y contrastada contra la mesa.

Ejemplos:
    uv run juegos/heroquest/scripts/preparar_reversos.py            # todos
    uv run juegos/heroquest/scripts/preparar_reversos.py --ver enemigo_back.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"
REVERSOS_DIR = SOURCES_DIR / "reversos"

# Reversos conocidos en sources/ (fotos de las cartas reales por su cara trasera).
REVERSOS = [
    "heroe_back.jpg",
    "enemigo_back.jpg",
    "equipo_back.jpg",
    "tesoro_back.jpg",
    "magia_agua_back.jpg",
    "magia_aire_back.jpg",
    "magia_fuego_back.jpg",
    "magia_terror_back.jpg",
    "magia_tierra_back.jpg",
]

# Umbral de diferencia (0-255) sobre el que un píxel se considera "carta" y no
# "mesa/fondo". Valor moderado: tolera sombras suaves del fondo.
UMBRAL_FONDO = 34


def _color_fondo(img: Image.Image) -> tuple[int, int, int]:
    """Color medio de las cuatro esquinas: aproxima el fondo de la mesa."""
    w, h = img.size
    m = max(4, min(w, h) // 40)
    muestras = [
        img.crop((0, 0, m, m)),
        img.crop((w - m, 0, w, m)),
        img.crop((0, h - m, m, h)),
        img.crop((w - m, h - m, w, h)),
    ]
    r = g = b = 0
    for parche in muestras:
        pr, pg, pb = parche.resize((1, 1)).getpixel((0, 0))[:3]
        r, g, b = r + pr, g + pg, b + pb
    n = len(muestras)
    return (r // n, g // n, b // n)


def _caja_carta(img: Image.Image) -> tuple[int, int, int, int]:
    """Calcula la caja (izq, arriba, der, abajo) que contiene la carta.

    Resta el color de fondo, umbraliza y toma el bounding box de lo que queda.
    Cae con seguridad al recorte central si la heurística no encuentra nada.
    """
    rgb = img.convert("RGB")
    fondo = Image.new("RGB", rgb.size, _color_fondo(rgb))
    dif = ImageChops.difference(rgb, fondo).convert("L")
    dif = dif.filter(ImageFilter.MedianFilter(size=5))
    mascara = dif.point(lambda p: 255 if p > UMBRAL_FONDO else 0)
    caja = mascara.getbbox()
    if caja is None:
        w, h = img.size
        margen_x, margen_y = int(w * 0.1), int(h * 0.1)
        return (margen_x, margen_y, w - margen_x, h - margen_y)
    return caja


def _a_retrato(img: Image.Image) -> Image.Image:
    """Gira la imagen a orientación vertical (retrato) si viene apaisada."""
    if img.width > img.height:
        return img.rotate(-90, expand=True)
    return img


def preparar(nombre: str) -> Path | None:
    """Recorta y endereza un reverso; devuelve la ruta de salida o None."""
    origen = SOURCES_DIR / nombre
    if not origen.exists():
        print(f"  (omitido, no existe: {nombre})")
        return None
    with Image.open(origen) as img:
        img = img.convert("RGB")
        caja = _caja_carta(img)
        recorte = img.crop(caja)
        recorte = _a_retrato(recorte)
        REVERSOS_DIR.mkdir(parents=True, exist_ok=True)
        salida = REVERSOS_DIR / f"{Path(nombre).stem}.png"
        recorte.save(salida)
    return salida


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara los reversos de las cartas de HeroQuest")
    parser.add_argument("--solo", metavar="FICHERO", default=None,
                        help="Procesar solo un fichero de sources/ (p. ej. enemigo_back.jpg)")
    args = parser.parse_args()

    objetivos = [args.solo] if args.solo else REVERSOS
    hechos = 0
    for nombre in objetivos:
        salida = preparar(nombre)
        if salida:
            print(f"Reverso: {salida}")
            hechos += 1
    print(f"Listos {hechos} reversos en {REVERSOS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

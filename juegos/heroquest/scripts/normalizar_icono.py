"""Normaliza el tamaño de los iconos para las cartas.

Ajusta todos los iconos a un lienzo cuadrado estándar con aire uniforme,
independientemente de la eliminación de fondo.

Ejemplos:

    uv run .../normalizar_icono.py foto.png
    uv run .../normalizar_icono.py foto.png --tamano 500 --aire 0.15
    uv run .../normalizar_icono.py iconos/ --en-sitio
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp"}


def normalizar_icono(
    img: Image.Image,
    tamano: int = 500,
    aire: float = 0.15,
) -> Image.Image:
    """Ajusta la imagen a un lienzo cuadrado con aire alrededor.

    - Recorta al contenido opaco
    - Escala para que el contenido ocupe (1 - 2*aire) del lienzo
    - Centra en el lienzo cuadrado de tamaño `tamano`
    """
    # Si tiene canal alfa, recortar al contenido opaco
    if img.mode == "RGBA":
        alpha = img.split()[3]
        caja = alpha.getbbox()
        if caja:
            img = img.crop(caja)
    else:
        # Para RGB, detectar contenido no-blanco
        rgb = img.convert("RGB")
        # Buscar bbox del contenido (asumir fondo blanco)
        bbox = rgb.getbbox()
        if bbox:
            img = img.crop(bbox)

    # Escalar para que el contenido quepa con aire
    w, h = img.size
    factor = (tamano * (1 - 2 * aire)) / max(w, h)
    nuevo_w = max(1, round(w * factor))
    nuevo_h = max(1, round(h * factor))
    img = img.resize((nuevo_w, nuevo_h), Image.Resampling.LANCZOS)

    # Centrar en el lienzo cuadrado
    lienzo = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    x = (tamano - nuevo_w) // 2
    y = (tamano - nuevo_h) // 2
    lienzo.alpha_composite(img.convert("RGBA"), (x, y))

    return lienzo


def procesar(entrada: Path, salida: Path, tamano: int, aire: float) -> None:
    with Image.open(entrada) as img:
        resultado = normalizar_icono(img, tamano, aire)
    salida.parent.mkdir(parents=True, exist_ok=True)
    resultado.save(salida)
    print(f"{entrada.name} -> {salida}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("entradas", nargs="+", type=Path, help="imágenes o carpetas")
    parser.add_argument("--salida", type=Path, default=None, help="carpeta destino")
    parser.add_argument("--en-sitio", action="store_true", help="sobreescribe cada entrada")
    parser.add_argument("--tamano", type=int, default=500, help="tamaño del lienzo cuadrado (defecto %(default)s)")
    parser.add_argument("--aire", type=float, default=0.15, help="fracción de aire alrededor del contenido (defecto %(default)s)")
    args = parser.parse_args(argv)

    if args.en_sitio and args.salida is not None:
        parser.error("--en-sitio y --salida son excluyentes")

    ficheros = []
    for ruta in args.entradas:
        if ruta.is_dir():
            ficheros.extend(sorted(p for p in ruta.iterdir() if p.suffix.lower() in EXTENSIONES))
        else:
            ficheros.append(ruta)

    for f in ficheros:
        if args.en_sitio:
            destino = f.with_suffix(".png")
        elif args.salida is not None:
            destino = args.salida / f.stem
        else:
            destino = f.with_name(f"{f.stem}_icono.png")

        try:
            procesar(f, destino, args.tamano, args.aire)
            if args.en_sitio and f.suffix.lower() != ".png" and f.exists():
                f.unlink()
        except Exception as e:
            print(f"ERROR con {f}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

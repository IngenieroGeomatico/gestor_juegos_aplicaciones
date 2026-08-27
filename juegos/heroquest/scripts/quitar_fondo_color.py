"""Quita un fondo de color uniforme de las ilustraciones para las cartas.

Versión simplificada de quitar_fondo_blanco.py: solo elimina el color de fondo
(especificado o detectado automáticamente) y lo convierte en transparencia,
sin procesar huecos interiores ni des-mezclar bordes.

Ejemplos:

    uv run .../quitar_fondo_color.py foto.png --color green
    uv run .../quitar_fondo_color.py foto.png --color "70,154,85"
    uv run .../quitar_fondo_color.py foto.png --color auto
    uv run .../quitar_fondo_color.py foto.png --umbral 40 --en-sitio

Por defecto escribe `<nombre>_sin_fondo.png` junto a cada entrada; `--en-sitio`
sobreescribe cada entrada con su versión transparente (siempre en PNG) y
`--salida <dir>` guarda todos los resultados en una carpeta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops

# Extensiones de imagen que acepta el script.
EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp"}


def _parsear_color(valor: str) -> tuple[int, int, int]:
    """Parsea un color: nombre ('green'), hex ('#00ff00') o RGB ('0,255,0')."""
    NOMBRES = {
        "white": (255, 255, 255), "blanco": (255, 255, 255),
        "green": (0, 177, 64), "verde": (0, 177, 64),
        "blue": (0, 128, 255), "azul": (0, 128, 255),
        "red": (255, 0, 0), "rojo": (255, 0, 0),
        "black": (0, 0, 0), "negro": (0, 0, 0),
        "chroma-green": (0, 177, 64), "croma-verde": (0, 177, 64),
    }
    v = valor.strip().lower()
    if v in NOMBRES:
        return NOMBRES[v]
    if v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    if "," in v:
        partes = [int(x.strip()) for x in v.split(",")]
        if len(partes) == 3:
            return tuple(partes)
    raise ValueError(f"Color no reconocido: '{valor}'. Usa nombre, #hex o R,G,B.")


def detectar_color_fondo(img: Image.Image, radio_muestra: int = 10) -> tuple[int, int, int]:
    """Detecta el color de fondo muestreando píxeles de las 4 esquinas."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    esquinas = [
        (0, 0),
        (w - radio_muestra, 0),
        (0, h - radio_muestra),
        (w - radio_muestra, h - radio_muestra),
    ]
    colores = []
    for x, y in esquinas:
        caja = (x, y, x + radio_muestra, y + radio_muestra)
        recorte = rgb.crop(caja)
        pixels = list(recorte.getdata())
        if not pixels:
            continue
        r_medio = sum(p[0] for p in pixels) // len(pixels)
        g_medio = sum(p[1] for p in pixels) // len(pixels)
        b_medio = sum(p[2] for p in pixels) // len(pixels)
        colores.append((r_medio, g_medio, b_medio))
    if not colores:
        return (255, 255, 255)
    return colores[0]


def distancia_al_color(img: Image.Image, color_fondo: tuple[int, int, int]) -> Image.Image:
    """Distancia de cada píxel al color de fondo (Chebyshov: máx. |diferencia| de canal)."""
    bandas = img.split()
    dist = Image.new("L", img.size, 0)
    for i, banda in enumerate(bandas):
        objetivo = Image.new("L", img.size, color_fondo[i])
        diff_pos = ImageChops.subtract(banda, objetivo)
        diff_neg = ImageChops.subtract(objetivo, banda)
        dist = ImageChops.lighter(dist, ImageChops.lighter(diff_pos, diff_neg))
    return dist


def quitar_fondo(
    img: Image.Image,
    color_fondo: tuple[int, int, int],
    umbral: int = 32,
) -> Image.Image:
    """Devuelve la imagen en RGBA con el color de fondo convertido en alpha."""
    rgb = img.convert("RGB")
    dist = distancia_al_color(rgb, color_fondo)

    # Máscara de píxeles "casi del color del fondo"
    mask = dist.point(lambda d: 0 if d <= umbral else 255)

    # Convertir a RGBA y aplicar máscara como alpha
    rgba = rgb.convert("RGBA")
    rgba.putalpha(mask)

    return rgba


def _pad_a_proporcion(img: Image.Image, ratio: float) -> Image.Image:
    """Lienzo transparente con la proporción pedida (ancho/alto), contenido centrado."""
    w, h = img.size
    if w / h > ratio:
        ancho, alto = w, round(w / ratio)
    else:
        ancho, alto = round(h * ratio), h
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    lienzo.alpha_composite(img, ((ancho - w) // 2, (alto - h) // 2))
    return lienzo


def _ajustar_icono(img: Image.Image, tamano: int = 500, aire: float = 0.1) -> Image.Image:
    """Ajusta la imagen a un lienzo cuadrado con aire alrededor.

    - Recorta al contenido opaco
    - Escala para que el contenido ocupe (1 - 2*aire) del lienzo
    - Centra en el lienzo cuadrado de tamaño `tamano`
    """
    # Recortar al contenido opaco
    alpha = img.split()[3]
    caja = alpha.getbbox()
    if caja:
        img = img.crop(caja)

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
    lienzo.alpha_composite(img, (x, y))

    return lienzo


def procesar(
    entrada: Path,
    salida: Path,
    color_fondo: tuple[int, int, int],
    umbral: int,
    recortar: bool = True,
    lienzo_proporcion: float | None = None,
    icono: int | None = None,
    aire: float = 0.1,
) -> None:
    with Image.open(entrada) as img:
        resultado = quitar_fondo(img, color_fondo, umbral)
    if recortar:
        alpha = resultado.split()[3]
        caja = alpha.getbbox()
        if caja:
            resultado = resultado.crop(caja)
    if icono:
        resultado = _ajustar_icono(resultado, icono, aire)
    elif lienzo_proporcion:
        resultado = _pad_a_proporcion(resultado, lienzo_proporcion)
    salida.parent.mkdir(parents=True, exist_ok=True)
    resultado.save(salida)
    print(f"{entrada.name} -> {salida}")


def reunir_entradas(rutas: list[Path]) -> list[Path]:
    """Expande carpetas a ficheros de imagen; omite salidas de ejecuciones previas."""
    ficheros: list[Path] = []
    for ruta in rutas:
        if ruta.is_dir():
            candidatos = sorted(p for p in ruta.iterdir() if p.suffix.lower() in EXTENSIONES)
        else:
            candidatos = [ruta]
        for f in candidatos:
            if f.stem.endswith("_sin_fondo"):
                continue
            ficheros.append(f)
    return ficheros


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("entradas", nargs="+", type=Path, help="imágenes o carpetas con imágenes")
    parser.add_argument("--salida", type=Path, default=None, help="carpeta destino para todos los resultados")
    parser.add_argument("--en-sitio", action="store_true", help="sobreescribe cada entrada con su versión transparente (PNG)")
    parser.add_argument("--color", default="auto", help="color de fondo a eliminar: nombre, #hex o R,G,B (defecto: auto)")
    parser.add_argument("--umbral", type=int, default=32, help="tolerancia al color, 0-255 (defecto %(default)s)")
    parser.add_argument("--lienzo-proporcion", type=float, default=None, help="remata en un lienzo transparente con esta proporción ancho/alto, contenido centrado (p. ej. 1 para los iconos)")
    parser.add_argument("--icono", type=int, default=None, help="ajustar a lienzo cuadrado para icono de carta (tamaño en px, p. ej. 500)")
    parser.add_argument("--aire", type=float, default=0.1, help="fracción de aire alrededor del contenido con --icono (defecto %(default)s)")
    parser.add_argument("--sin-recortar", action="store_true", help="no recorta al contenido opaco")
    args = parser.parse_args(argv)

    if args.en_sitio and args.salida is not None:
        parser.error("--en-sitio y --salida son excluyentes")

    ficheros = reunir_entradas(args.entradas)
    if not ficheros:
        print("No hay imágenes que procesar.", file=sys.stderr)
        return 1

    for f in ficheros:
        # Detectar color por imagen si --color auto
        if args.color.lower() == "auto":
            with Image.open(f) as img_temp:
                color = detectar_color_fondo(img_temp)
            print(f"  Color detectado en {f.name}: rgb{color}")
        else:
            color = _parsear_color(args.color)

        if args.en_sitio:
            destino = f.with_suffix(".png")
        elif args.salida is not None:
            destino = args.salida / f.stem
        else:
            destino = f.with_name(f"{f.stem}_sin_fondo.png")

        try:
            procesar(f, destino, color, args.umbral, not args.sin_recortar, args.lienzo_proporcion, args.icono, args.aire)
            if args.en_sitio and f.suffix.lower() != ".png" and f.exists():
                f.unlink()
        except Exception as e:
            print(f"ERROR con {f}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Corrige la perspectiva de una foto de tablero y la normaliza a la cuadrícula.

A partir de las 4 esquinas del **área jugable** (las casillas de la cuadrícula,
sin el marco decorativo) de una foto, aplica una transformación de perspectiva
con Pillow y produce una imagen "plana" (vista cenital) de exactamente
`columnas x filas` casillas, en orientación apaisada canónica (26x19 por
defecto, como el HeroQuest real y como esperan las misiones existentes).

Las esquinas se dan como píxeles de la foto original, en este orden lógico del
tablero **ya orientado apaisado** (columna 1..26 de izquierda a derecha, fila
1..19 de arriba a abajo):

    --esquinas TLx,TLy TRx,TRy BRx,BRy BLx,BLy

donde TL/TR/BR/BL son las esquinas jugables que quedarán arriba-izq, arriba-der,
abajo-der y abajo-izq en la imagen final. Así, aunque la foto esté en retrato o
girada 180º, basta con elegir qué esquina física corresponde a cada esquina
lógica para normalizar orientación y perspectiva a la vez.

Ejemplos:
    # cara A (foto vertical): la esquina jugable de arriba-izq del tablero
    # apaisado es, en la foto vertical, la de arriba-derecha, etc.
    uv run juegos/heroquest/scripts/tablero_calibrar.py \
        --imagen juegos/heroquest/sources/heroquest_board_original.jpg \
        --id original \
        --esquinas 150,200 1240,180 1225,3450 150,3470

    uv run juegos/heroquest/scripts/tablero_calibrar.py --id original --rejilla
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent.parent
CAL_DIR = BASE / "_cal"
SOURCES = BASE / "sources"

# Píxeles por casilla en la imagen plana de salida (resolución de trabajo).
PX_CASILLA = 48


def _parse_punto(txt: str) -> tuple[float, float]:
    x, y = txt.split(",")
    return float(x), float(y)


def corregir_perspectiva(
    imagen: Path,
    esquinas: list[tuple[float, float]],
    columnas: int,
    filas: int,
    px: int = PX_CASILLA,
) -> Image.Image:
    """Endereza el área jugable de la foto a una imagen cenital de columnas x filas.

    `esquinas` es [TL, TR, BR, BL] en píxeles de la foto, correspondiendo a las
    esquinas lógicas del tablero apaisado (arriba-izq, arriba-der, abajo-der,
    abajo-izq). El resultado siempre sale apaisado y a escala uniforme.
    """
    im = Image.open(imagen).convert("RGB")
    ancho_dst = columnas * px
    alto_dst = filas * px

    tl, tr, br, bl = esquinas
    # PIL.Image.transform(PERSPECTIVE) mapea cada píxel de DESTINO a ORIGEN, con
    # coeficientes (a..h) tales que:
    #   x_src = (a*x_dst + b*y_dst + c) / (g*x_dst + h*y_dst + 1)
    #   y_src = (d*x_dst + e*y_dst + f) / (g*x_dst + h*y_dst + 1)
    # Resolvemos el sistema con las 4 correspondencias destino->origen.
    coeffs = _coeffs_perspectiva(
        [(0, 0), (ancho_dst, 0), (ancho_dst, alto_dst), (0, alto_dst)],
        [tl, tr, br, bl],
    )
    return im.transform(
        (ancho_dst, alto_dst),
        Image.Transform.PERSPECTIVE,
        coeffs,
        resample=Image.Resampling.BICUBIC,
    )


def _coeffs_perspectiva(
    destino: list[tuple[float, float]],
    origen: list[tuple[float, float]],
) -> list[float]:
    """Coeficientes de la transformación de perspectiva destino->origen.

    Resuelve el sistema lineal 8x8 sin numpy (eliminación de Gauss).
    """
    matriz: list[list[float]] = []
    vector: list[float] = []
    for (xd, yd), (xs, ys) in zip(destino, origen):
        matriz.append([xd, yd, 1, 0, 0, 0, -xd * xs, -yd * xs])
        vector.append(xs)
        matriz.append([0, 0, 0, xd, yd, 1, -xd * ys, -yd * ys])
        vector.append(ys)
    return _resolver(matriz, vector)


def _resolver(a: list[list[float]], b: list[float]) -> list[float]:
    """Eliminación gaussiana con pivoteo parcial para un sistema n x n."""
    n = len(b)
    m = [fila[:] + [b[i]] for i, fila in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("Esquinas degeneradas: no se puede resolver la perspectiva")
        m[col], m[piv] = m[piv], m[col]
        p = m[col][col]
        m[col] = [v / p for v in m[col]]
        for r in range(n):
            if r != col:
                factor = m[r][col]
                m[r] = [v - factor * m[col][k] for k, v in enumerate(m[r])]
    return [m[i][n] for i in range(n)]


def dibujar_rejilla(
    plano: Image.Image,
    columnas: int,
    filas: int,
    px: int = PX_CASILLA,
) -> Image.Image:
    """Superpone la rejilla columnas x filas numerada sobre la imagen plana."""
    img = plano.copy()
    d = ImageDraw.Draw(img)
    for c in range(columnas + 1):
        x = c * px
        d.line([(x, 0), (x, filas * px)], fill=(255, 0, 255), width=1)
    for f in range(filas + 1):
        y = f * px
        d.line([(0, y), (columnas * px, y)], fill=(255, 0, 255), width=1)
    # etiquetas de columna (1..columnas) arriba y fila (1..filas) a la izquierda
    for c in range(columnas):
        d.text((c * px + 3, 2), str(c + 1), fill=(255, 255, 0))
    for f in range(filas):
        d.text((2, f * px + 3), str(f + 1), fill=(255, 255, 0))
    return img


def main() -> None:
    p = argparse.ArgumentParser(description="Calibra y endereza una foto de tablero")
    p.add_argument("--id", required=True, help="ID del tablero (original, cara-b)")
    p.add_argument("--imagen", help="Ruta de la foto de origen")
    p.add_argument("--columnas", type=int, default=26)
    p.add_argument("--filas", type=int, default=19)
    p.add_argument(
        "--esquinas",
        nargs=4,
        metavar=("TL", "TR", "BR", "BL"),
        help="Esquinas jugables x,y de la foto en orden TL TR BR BL (apaisado)",
    )
    p.add_argument(
        "--rejilla",
        action="store_true",
        help="Regenera solo la rejilla numerada sobre el plano ya calibrado",
    )
    args = p.parse_args()

    CAL_DIR.mkdir(exist_ok=True)
    plano_path = CAL_DIR / f"{args.id}_plano.png"
    rejilla_path = CAL_DIR / f"{args.id}_rejilla.png"

    if not args.rejilla:
        if not args.imagen or not args.esquinas:
            p.error("hace falta --imagen y --esquinas (o usa --rejilla)")
        esquinas = [_parse_punto(t) for t in args.esquinas]
        plano = corregir_perspectiva(
            Path(args.imagen), esquinas, args.columnas, args.filas
        )
        plano.save(plano_path)
        print(f"Plano guardado: {plano_path} ({plano.size[0]}x{plano.size[1]})")
    else:
        plano = Image.open(plano_path)

    rejilla = dibujar_rejilla(plano, args.columnas, args.filas)
    rejilla.save(rejilla_path)
    print(f"Rejilla guardada: {rejilla_path}  ({args.columnas}x{args.filas} casillas)")


if __name__ == "__main__":
    main()

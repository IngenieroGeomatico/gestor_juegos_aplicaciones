# -*- coding: utf-8 -*-
"""Genera un PDF A4 con cartas de HeroQuest listas para imprimir y montar.

Cada carta se maqueta como **hoja plegable**: anverso y reverso lado a lado en la
misma cara del papel. Se imprime a una sola cara, se recorta por las marcas de
corte, se **dobla por la línea de pliegue** central y la carta (ya con sus dos
caras) se guarda en un protector.

Las cartas van a **tamaño real** (63 × 88 mm cada cara → 126 × 88 mm la pieza
plegable) con marcas de corte. En A4 (210 × 297 mm) entran 3 piezas por hoja.

Formas de indicar qué cartas imprimir (elige una):
  --lista mazo.yml     Fichero YAML con la lista (ver formato abajo).
  --carta "TIPO:Nombre"  Una carta suelta; repetible. Ej: --carta "arma:Daga".
  --todo               Todo el mazo del juego (todas las entradas de los datos).

Formato del YAML (`--lista`):

    # mazo.yml
    cartas:
      - arma: Espada corta
      - arma: Mandoble
        cantidad: 2          # nº de copias (opcional, por defecto 1)
      - monstruo: Orco
        cantidad: 4
      - personaje: Mago
      - hechizo: Bola de fuego

También se admite una lista simple de cadenas "tipo: nombre":

    cartas:
      - "arma: Daga"
      - "monstruo: Orco"

Ejemplos:
    uv run juegos/heroquest/scripts/imprimir_cartas.py --todo
    uv run juegos/heroquest/scripts/imprimir_cartas.py --lista mazo.yml --salida mazo.pdf
    uv run juegos/heroquest/scripts/imprimir_cartas.py --carta "arma:Espada corta" --carta "monstruo:Orco"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# La consola de Windows suele usar cp1252 y rompe con caracteres como '✗' o las
# tildes del texto de ayuda. Forzamos UTF-8 en la salida para evitar
# UnicodeEncodeError al imprimir mensajes o el --help.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

import data_store
import render_carta
import tipos_carta

CARTAS_DIR = data_store.DATA_DIR.parent / "cartas"

# --- Geometría de impresión (todo a 300 DPI) ---
DPI = render_carta.DPI_CARTA  # 300
MM = DPI / 25.4  # píxeles por milímetro

A4_ANCHO_MM, A4_ALTO_MM = 210, 297
A4_ANCHO = round(A4_ANCHO_MM * MM)
A4_ALTO = round(A4_ALTO_MM * MM)

# Pieza plegable: dos caras de 63×88 mm una al lado de la otra.
CARA_ANCHO = render_carta.PX_CARTA_ANCHO          # 744 px (63 mm)
CARA_ALTO = render_carta.PX_CARTA_ALTO            # 1039 px (88 mm)
PIEZA_ANCHO = render_carta.PX_CARTA_DOBLE_ANCHO   # 1488 px (126 mm)
PIEZA_ALTO = CARA_ALTO                            # 1039 px (88 mm)

MARGEN = round(8 * MM)          # margen de la hoja
SEP = round(6 * MM)             # separación entre piezas
MARCA = round(4 * MM)           # longitud de las marcas de corte
COLOR_MARCA = (120, 120, 120)
COLOR_PLIEGUE = (170, 170, 170)


# --- Selección de cartas ---

def _resolver(spec_tipo: str, nombre: str) -> tuple[tipos_carta.TipoCarta, dict] | None:
    """Localiza (TipoCarta, entrada) por tipo y nombre; None si no existe."""
    tipo = tipos_carta.obtener(spec_tipo)
    if tipo is None:
        print(f"  Aviso: tipo no válido: '{spec_tipo}' (válidos: {', '.join(tipos_carta.TIPOS)})")
        return None
    for entrada in data_store.cargar(tipo.fichero):
        if entrada.get("nombre") == nombre:
            deducido = tipos_carta.tipo_de_entrada(tipo.fichero, entrada)
            if deducido and deducido.id != tipo.id:
                continue
            return tipo, entrada
    print(f"  Aviso: no existe '{nombre}' de tipo '{spec_tipo}'")
    return None


def _parse_item(item) -> tuple[str, str, int] | None:
    """Convierte una entrada del YAML en (tipo, nombre, cantidad).

    Admite:  {arma: "Daga", cantidad: 2}  |  "arma: Daga"
    """
    if isinstance(item, str):
        if ":" not in item:
            print(f"  Aviso: entrada sin tipo: {item!r} (usa 'tipo: nombre')")
            return None
        tipo, nombre = item.split(":", 1)
        return tipo.strip(), nombre.strip(), 1
    if isinstance(item, dict):
        cantidad = int(item.get("cantidad", 1))
        for clave, valor in item.items():
            if clave in tipos_carta.TIPOS:
                return clave, str(valor).strip(), cantidad
        print(f"  Aviso: entrada sin un tipo válido: {item!r}")
    return None


def _desde_yaml(ruta: Path) -> list[tuple[str, str, int]]:
    import yaml
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    items = datos.get("cartas", datos) if isinstance(datos, dict) else datos
    if not isinstance(items, list):
        raise SystemExit("El YAML debe tener una lista 'cartas:' (ver ayuda con -h)")
    out = []
    for it in items:
        parsed = _parse_item(it)
        if parsed:
            out.append(parsed)
    return out


def _desde_args(specs: list[str]) -> list[tuple[str, str, int]]:
    out = []
    for s in specs:
        parsed = _parse_item(s)
        if parsed:
            out.append(parsed)
    return out


def _todo_el_mazo() -> list[tuple[str, str, int]]:
    """Todas las entradas de los datos, con su tipo CLI correcto."""
    out: list[tuple[str, str, int]] = []
    for fichero in ("personajes", "monstruos", "armas", "hechizos"):
        for entrada in data_store.cargar(fichero):
            tipo = tipos_carta.tipo_de_entrada(fichero, entrada)
            if tipo:
                out.append((tipo.id, entrada.get("nombre", ""), 1))
    return out


# --- Composición de páginas ---

def _piezas_por_pagina() -> tuple[int, int, int, int]:
    """Cuántas columnas y filas de piezas caben y el hueco disponible."""
    util_ancho = A4_ANCHO - 2 * MARGEN
    util_alto = A4_ALTO - 2 * MARGEN
    cols = max(1, (util_ancho + SEP) // (PIEZA_ANCHO + SEP))
    filas = max(1, (util_alto + SEP) // (PIEZA_ALTO + SEP))
    return int(cols), int(filas), util_ancho, util_alto


def _marcas_corte(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    """Dibuja marcas de corte en las 4 esquinas de una pieza."""
    for (px, py) in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        draw.line([(px - MARCA, py), (px, py)], fill=COLOR_MARCA, width=2)
        draw.line([(px, py - MARCA), (px, py)], fill=COLOR_MARCA, width=2)


def _render_pieza(tipo: tipos_carta.TipoCarta, entrada: dict) -> Image.Image:
    """Imagen 1488×1039 de la pieza plegable (anverso | reverso)."""
    fondo = _fondo_verso_de(tipo)
    return render_carta.render_png_doble(tipo, entrada, fondo_verso=fondo)


def _fondo_verso_de(tipo: tipos_carta.TipoCarta) -> str | None:
    """Elige el fondo temático de reverso por categoría, si existe.

    equipo/tesoro/enemigo/heroe/magia -> <categoria>_back.png en arte_fondos/.
    Si no hay fondo temático, devuelve None (usa el reverso estándar del tipo).
    """
    categoria = render_carta._categoria_verso(tipo)  # 'equipo', 'enemigo', ...
    candidato = render_carta.FONDOS_DIR / f"{categoria}_back.png"
    return candidato.name if candidato.exists() else None


def _nueva_pagina() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    pagina = Image.new("RGB", (A4_ANCHO, A4_ALTO), "white")
    return pagina, ImageDraw.Draw(pagina)


def componer(cartas: list[tuple[tipos_carta.TipoCarta, dict]]) -> list[Image.Image]:
    cols, filas, util_ancho, util_alto = _piezas_por_pagina()
    por_pagina = cols * filas
    # Centrar la rejilla en la zona útil.
    rejilla_ancho = cols * PIEZA_ANCHO + (cols - 1) * SEP
    rejilla_alto = filas * PIEZA_ALTO + (filas - 1) * SEP
    off_x = MARGEN + (util_ancho - rejilla_ancho) // 2
    off_y = MARGEN + (util_alto - rejilla_alto) // 2

    paginas: list[Image.Image] = []
    pagina = draw = None
    for i, (tipo, entrada) in enumerate(cartas):
        pos = i % por_pagina
        if pos == 0:
            pagina, draw = _nueva_pagina()
            paginas.append(pagina)
        col, fila = pos % cols, pos // cols
        x = off_x + col * (PIEZA_ANCHO + SEP)
        y = off_y + fila * (PIEZA_ALTO + SEP)
        pieza = _render_pieza(tipo, entrada)
        if pieza.size != (PIEZA_ANCHO, PIEZA_ALTO):
            pieza = pieza.resize((PIEZA_ANCHO, PIEZA_ALTO), Image.LANCZOS)
        pagina.paste(pieza, (x, y))
        _marcas_corte(draw, x, y, PIEZA_ANCHO, PIEZA_ALTO)
        # Línea de pliegue central (discontinua) entre anverso y reverso.
        cx = x + CARA_ANCHO
        for yy in range(y, y + PIEZA_ALTO, 24):
            draw.line([(cx, yy), (cx, min(yy + 12, y + PIEZA_ALTO))],
                      fill=COLOR_PLIEGUE, width=2)
    return paginas


def generar_pdf(cartas: list[tuple[tipos_carta.TipoCarta, dict]], salida: Path) -> None:
    paginas = componer(cartas)
    if not paginas:
        raise SystemExit("No hay cartas válidas que imprimir.")
    salida.parent.mkdir(parents=True, exist_ok=True)
    paginas[0].save(
        salida, "PDF", resolution=DPI, save_all=True,
        append_images=paginas[1:],
    )
    cols, filas, _, _ = _piezas_por_pagina()
    print(f"PDF: {salida}")
    print(f"  {len(cartas)} cartas · {len(paginas)} página(s) A4 · "
          f"{cols}×{filas} por hoja · caras 63×88 mm (pliegue central)")


def _expandir(specs: list[tuple[str, str, int]]) -> list[tuple[tipos_carta.TipoCarta, dict]]:
    """Resuelve tipos/nombres y expande por 'cantidad'."""
    cartas: list[tuple[tipos_carta.TipoCarta, dict]] = []
    for spec_tipo, nombre, cantidad in specs:
        r = _resolver(spec_tipo, nombre)
        if r:
            cartas.extend([r] * max(1, cantidad))
    return cartas


def main() -> None:
    p = argparse.ArgumentParser(
        description="Genera un PDF A4 con cartas de HeroQuest para imprimir y plegar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lista", metavar="ARCHIVO.yml", help="Fichero YAML con las cartas")
    g.add_argument("--carta", action="append", metavar='"TIPO:Nombre"',
                   help="Una carta (repetible). Ej: --carta \"arma:Daga\"")
    g.add_argument("--todo", action="store_true", help="Todo el mazo del juego")
    p.add_argument("--salida", default=None, help="Ruta del PDF (por defecto en cartas/)")
    args = p.parse_args()

    if args.todo:
        specs = _todo_el_mazo()
        nombre_defecto = "mazo_completo.pdf"
    elif args.lista:
        specs = _desde_yaml(Path(args.lista))
        nombre_defecto = Path(args.lista).with_suffix(".pdf").name
    else:
        specs = _desde_args(args.carta)
        nombre_defecto = "cartas.pdf"

    cartas = _expandir(specs)
    if not cartas:
        print("No se resolvió ninguna carta. Revisa los nombres/tipos.")
        sys.exit(1)

    salida = Path(args.salida) if args.salida else CARTAS_DIR / nombre_defecto
    generar_pdf(cartas, salida)


if __name__ == "__main__":
    main()

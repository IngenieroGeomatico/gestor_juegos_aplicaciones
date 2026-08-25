# -*- coding: utf-8 -*-
"""Genera un PDF A4 con cartas de héroe de HeroQuest listas para imprimir.

El dibujo lo hace el motor guiado por datos `render_personaje.py` (anverso y
dorso). Solo se imprimen HÉROES (personajes con receta de plantillas en su JSON).

Dos disposiciones de impresión (`--disposicion`):

  junta     (por defecto) Anverso y dorso lado a lado en la MISMA hoja, con línea
            de pliegue central. Se imprime a una cara, se recorta la pieza, se
            dobla por el pliegue y queda la carta con sus dos caras.

  separada  Anversos y dorsos en HOJAS DISTINTAS (el estándar de la comunidad).
            Se imprime a DOBLE CARA: las páginas de dorso llevan las columnas
            ESPEJADAS para que cada dorso quede detrás de su anverso. Cada
            anverso va inmediatamente seguido de su página de dorsos.

Selección de cartas (elige una):
  --lista mazo.yml     Fichero YAML con la lista (formato abajo).
  --carta "Nombre"     Un héroe suelto; repetible. Ej: --carta "Bárbaro".
  --todo               Todos los héroes con carta (receta de plantillas).

Formato del YAML (`--lista`), admite "personaje: Nombre" o solo "Nombre":

    cartas:
      - personaje: Bárbaro
      - personaje: Mago
        cantidad: 2          # nº de copias (opcional, por defecto 1)

Ejemplos:
    uv run juegos/heroquest/scripts/imprimir_cartas.py --todo
    uv run juegos/heroquest/scripts/imprimir_cartas.py --lista juegos/heroquest/mazo_ejemplo.yml
    uv run juegos/heroquest/scripts/imprimir_cartas.py --carta "Bárbaro" --disposicion separada
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# La consola de Windows suele usar cp1252 y rompe con tildes o '✗'. Forzamos
# UTF-8 en la salida para evitar UnicodeEncodeError al imprimir o con --help.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

import data_store
import render_personaje

CARTAS_DIR = data_store.DATA_DIR.parent / "cartas"
FICHERO_PERSONAJES = "personajes"

# --- Geometría de impresión (todo a 300 DPI) ---
DPI = render_personaje.DPI_CARTA  # 300
MM = DPI / 25.4  # píxeles por milímetro

A4_ANCHO_MM, A4_ALTO_MM = 210, 297
A4_ANCHO = round(A4_ANCHO_MM * MM)
A4_ALTO = round(A4_ALTO_MM * MM)

CARA_ANCHO = render_personaje.PX_CARTA_ANCHO   # 744 px (63 mm)
CARA_ALTO = render_personaje.PX_CARTA_ALTO     # 1039 px (88 mm)
# Pieza plegable de la disposición 'junta': dos caras una al lado de la otra.
PIEZA_JUNTA_ANCHO = CARA_ANCHO * 2             # 1488 px (126 mm)

MARGEN = round(5 * MM)          # margen de la hoja
SEP = 0                         # separación entre piezas (0 = cartas pegadas → 3×3=9)
MARCA = round(3 * MM)           # longitud de cada brazo de la cruz de corte
COLOR_MARCA = (0, 0, 0)         # cruces de corte en negro
COLOR_PLIEGUE = (170, 170, 170)


# --- Selección de héroes ---

def _entrada_por_nombre(nombre: str) -> dict | None:
    """Devuelve la entrada del héroe por nombre, o None si no existe."""
    for entrada in data_store.cargar(FICHERO_PERSONAJES):
        if entrada.get("nombre") == nombre:
            return entrada
    return None


def _tiene_carta(entrada: dict) -> bool:
    """True si el héroe declara la receta de plantillas (cara) para renderizar."""
    cara = (entrada.get("plantillas") or {}).get("cara") or {}
    return bool(cara.get("plantilla_padre"))


def _resolver(nombre: str) -> dict | None:
    """Localiza un héroe imprimible por nombre; avisa si falta o no tiene carta."""
    entrada = _entrada_por_nombre(nombre)
    if entrada is None:
        print(f"  Aviso: no existe el héroe '{nombre}' en {FICHERO_PERSONAJES}.json")
        return None
    if not _tiene_carta(entrada):
        print(f"  Aviso: el héroe '{nombre}' no tiene receta de carta (plantillas.cara)")
        return None
    return entrada


def _parse_item(item) -> tuple[str, int] | None:
    """Convierte una entrada del YAML en (nombre, cantidad).

    Admite:  {personaje: "Bárbaro", cantidad: 2}  |  "personaje: Bárbaro"  |  "Bárbaro"
    """
    if isinstance(item, str):
        nombre = item.split(":", 1)[1].strip() if ":" in item else item.strip()
        return (nombre, 1) if nombre else None
    if isinstance(item, dict):
        cantidad = int(item.get("cantidad", 1))
        for clave, valor in item.items():
            if clave == "cantidad":
                continue
            # Se admite cualquier clave (p. ej. 'personaje'); el valor es el nombre.
            return str(valor).strip(), cantidad
    print(f"  Aviso: entrada no válida en el YAML: {item!r}")
    return None


def _desde_yaml(ruta: Path) -> list[tuple[str, int]]:
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


def _desde_args(specs: list[str]) -> list[tuple[str, int]]:
    out = []
    for s in specs:
        parsed = _parse_item(s)
        if parsed:
            out.append(parsed)
    return out


def _todos_los_heroes() -> list[tuple[str, int]]:
    """Todos los héroes que tienen receta de carta."""
    return [(e.get("nombre", ""), 1)
            for e in data_store.cargar(FICHERO_PERSONAJES) if _tiene_carta(e)]


def _expandir(specs: list[tuple[str, int]]) -> list[dict]:
    """Resuelve nombres y expande por 'cantidad' en una lista de entradas."""
    cartas: list[dict] = []
    for nombre, cantidad in specs:
        entrada = _resolver(nombre)
        if entrada:
            cartas.extend([entrada] * max(1, cantidad))
    return cartas


# --- Render de caras (cacheado por nombre para no repetir trabajo) ---

class _RenderCache:
    """Cachea el anverso y el dorso ya rasterizados de cada héroe por nombre."""

    def __init__(self) -> None:
        self._anverso: dict[str, Image.Image] = {}
        self._dorso: dict[str, Image.Image] = {}

    def anverso(self, entrada: dict) -> Image.Image:
        nombre = entrada.get("nombre", "")
        if nombre not in self._anverso:
            self._anverso[nombre] = _ajustar(render_personaje.render_png(entrada))
        return self._anverso[nombre]

    def dorso(self, entrada: dict) -> Image.Image:
        nombre = entrada.get("nombre", "")
        if nombre not in self._dorso:
            self._dorso[nombre] = _ajustar(render_personaje.render_png_verso(entrada))
        return self._dorso[nombre]


def _ajustar(img: Image.Image) -> Image.Image:
    """Asegura que la imagen tenga el tamaño exacto de una cara (CARA_ANCHO×ALTO)."""
    if img.size != (CARA_ANCHO, CARA_ALTO):
        img = img.resize((CARA_ANCHO, CARA_ALTO), Image.LANCZOS)
    return img


# --- Composición de páginas ---

def _piezas_por_pagina(pieza_ancho: int, pieza_alto: int) -> tuple[int, int, int, int]:
    """Cuántas columnas y filas de piezas caben y el hueco útil disponible."""
    util_ancho = A4_ANCHO - 2 * MARGEN
    util_alto = A4_ALTO - 2 * MARGEN
    cols = max(1, (util_ancho + SEP) // (pieza_ancho + SEP))
    filas = max(1, (util_alto + SEP) // (pieza_alto + SEP))
    return int(cols), int(filas), util_ancho, util_alto


def _nueva_pagina() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    pagina = Image.new("RGB", (A4_ANCHO, A4_ALTO), "white")
    return pagina, ImageDraw.Draw(pagina)


def _cruces_corte(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    """Dibuja una cruz '+' negra en cada esquina de la pieza (guías de corte).

    Cada cruz se centra en la esquina, con brazos que sobresalen en las cuatro
    direcciones, para marcar por dónde pasa el corte. Con las cartas pegadas
    (separación 0) las cruces de esquinas adyacentes coinciden en el corte común.
    """
    for (px, py) in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        draw.line([(px - MARCA, py), (px + MARCA, py)], fill=COLOR_MARCA, width=2)
        draw.line([(px, py - MARCA), (px, py + MARCA)], fill=COLOR_MARCA, width=2)


def _origen_rejilla(cols: int, filas: int, pieza_ancho: int, pieza_alto: int,
                    util_ancho: int, util_alto: int) -> tuple[int, int]:
    """Desplazamiento para centrar la rejilla de piezas en la zona útil."""
    rejilla_ancho = cols * pieza_ancho + (cols - 1) * SEP
    rejilla_alto = filas * pieza_alto + (filas - 1) * SEP
    off_x = MARGEN + (util_ancho - rejilla_ancho) // 2
    off_y = MARGEN + (util_alto - rejilla_alto) // 2
    return off_x, off_y


def componer_junta(cartas: list[dict], cache: _RenderCache) -> list[Image.Image]:
    """Disposición 'junta': por cada carta, anverso|dorso con pliegue central."""
    cols, filas, util_ancho, util_alto = _piezas_por_pagina(PIEZA_JUNTA_ANCHO, CARA_ALTO)
    por_pagina = cols * filas
    off_x, off_y = _origen_rejilla(cols, filas, PIEZA_JUNTA_ANCHO, CARA_ALTO,
                                   util_ancho, util_alto)

    paginas: list[Image.Image] = []
    pagina = draw = None
    for i, entrada in enumerate(cartas):
        pos = i % por_pagina
        if pos == 0:
            pagina, draw = _nueva_pagina()
            paginas.append(pagina)
        col, fila = pos % cols, pos // cols
        x = off_x + col * (PIEZA_JUNTA_ANCHO + SEP)
        y = off_y + fila * (CARA_ALTO + SEP)
        pagina.paste(cache.anverso(entrada), (x, y))
        pagina.paste(cache.dorso(entrada), (x + CARA_ANCHO, y))
        _cruces_corte(draw, x, y, PIEZA_JUNTA_ANCHO, CARA_ALTO)
        # Línea de pliegue central (discontinua) entre anverso y dorso.
        cx = x + CARA_ANCHO
        for yy in range(y, y + CARA_ALTO, 24):
            draw.line([(cx, yy), (cx, min(yy + 12, y + CARA_ALTO))],
                      fill=COLOR_PLIEGUE, width=2)
    return paginas


def _pagina_de_caras(caras: list[Image.Image], cols: int, filas: int,
                     off_x: int, off_y: int, espejar: bool) -> Image.Image:
    """Compone una página con hasta cols×filas caras.

    `espejar` invierte el orden horizontal de las columnas (para que los dorsos
    casen con los anversos al imprimir a doble cara).
    """
    pagina, draw = _nueva_pagina()
    for pos, cara in enumerate(caras):
        col, fila = pos % cols, pos // cols
        if espejar:
            col = cols - 1 - col
        x = off_x + col * (CARA_ANCHO + SEP)
        y = off_y + fila * (CARA_ALTO + SEP)
        pagina.paste(cara, (x, y))
        _cruces_corte(draw, x, y, CARA_ANCHO, CARA_ALTO)
    return pagina


def componer_separada(cartas: list[dict], cache: _RenderCache) -> list[Image.Image]:
    """Disposición 'separada': página de anversos seguida de página de dorsos.

    Los dorsos van con las columnas espejadas para que, al imprimir a doble cara,
    cada dorso quede detrás de su anverso.
    """
    cols, filas, util_ancho, util_alto = _piezas_por_pagina(CARA_ANCHO, CARA_ALTO)
    por_pagina = cols * filas
    off_x, off_y = _origen_rejilla(cols, filas, CARA_ANCHO, CARA_ALTO,
                                   util_ancho, util_alto)

    paginas: list[Image.Image] = []
    for inicio in range(0, len(cartas), por_pagina):
        grupo = cartas[inicio:inicio + por_pagina]
        anversos = [cache.anverso(e) for e in grupo]
        dorsos = [cache.dorso(e) for e in grupo]
        paginas.append(_pagina_de_caras(anversos, cols, filas, off_x, off_y, espejar=False))
        paginas.append(_pagina_de_caras(dorsos, cols, filas, off_x, off_y, espejar=True))
    return paginas


def generar_pdf(cartas: list[dict], salida: Path, disposicion: str) -> None:
    cache = _RenderCache()
    if disposicion == "separada":
        paginas = componer_separada(cartas, cache)
    else:
        paginas = componer_junta(cartas, cache)
    if not paginas:
        raise SystemExit("No hay cartas válidas que imprimir.")
    salida.parent.mkdir(parents=True, exist_ok=True)
    paginas[0].save(salida, "PDF", resolution=DPI, save_all=True,
                    append_images=paginas[1:])
    print(f"PDF: {salida}")
    print(f"  {len(cartas)} carta(s) · {len(paginas)} página(s) A4 · "
          f"disposición '{disposicion}' · caras 63×88 mm")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Genera un PDF A4 con cartas de héroe de HeroQuest para imprimir",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lista", metavar="ARCHIVO.yml", help="Fichero YAML con los héroes")
    g.add_argument("--carta", action="append", metavar='"Nombre"',
                   help="Un héroe (repetible). Ej: --carta \"Bárbaro\"")
    g.add_argument("--todo", action="store_true", help="Todos los héroes con carta")
    p.add_argument("--disposicion", choices=("junta", "separada"), default="junta",
                   help="junta: anverso|dorso en la misma hoja (pliegue); "
                        "separada: anversos y dorsos en hojas distintas a doble cara "
                        "(predeterminado: junta)")
    p.add_argument("--salida", default=None, help="Ruta del PDF (por defecto en cartas/)")
    args = p.parse_args()

    if args.todo:
        specs = _todos_los_heroes()
        nombre_defecto = "mazo_completo.pdf"
    elif args.lista:
        specs = _desde_yaml(Path(args.lista))
        nombre_defecto = Path(args.lista).with_suffix(".pdf").name
    else:
        specs = _desde_args(args.carta)
        nombre_defecto = "cartas.pdf"

    cartas = _expandir(specs)
    if not cartas:
        print("No se resolvió ninguna carta. Revisa los nombres.")
        sys.exit(1)

    salida = Path(args.salida) if args.salida else CARTAS_DIR / nombre_defecto
    generar_pdf(cartas, salida, args.disposicion)


if __name__ == "__main__":
    main()

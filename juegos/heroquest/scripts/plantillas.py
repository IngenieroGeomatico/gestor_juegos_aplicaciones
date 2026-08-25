# -*- coding: utf-8 -*-
"""Carga y rellena las plantillas SVG de las cartas de HeroQuest.

Las plantillas viven en `sources/plantillas/` como ficheros `.svg` editables
(en Inkscape, por ejemplo). La estructura de la carta (marco, banners,
leyendas, tabla de estadisticas...) ya no esta hardcodeada en Python: vive en
esas plantillas. Este modulo las carga y sustituye su contenido dinamico.

Contrato de plantilla (ver los comentarios de cada `.svg`):

- **Marcadores de texto** `{{CLAVE}}` dentro de `<text>`/`<tspan>` o de
  atributos (p. ej. `fill="{{COLOR}}"`). Se sustituyen por su valor de texto,
  ya escapado para XML. `{{COLOR}}` es el color de acento del tipo de carta.

- **Elementos "ancla"** con `id="ph-*"` (p. ej. `id="ph-arte"`,
  `id="ph-stats"`, `id="ph-descripcion"`, `id="ph-fondo"`). Son cajas
  (`<rect>`) invisibles cuya GEOMETRIA (`x`, `y`, `width`, `height`) lee el
  codigo para colocar contenido generado (una imagen, la tabla de stats, el
  texto de la descripcion...). El propio `<rect>` se elimina del SVG final y
  se sustituye por el fragmento SVG que genera el codigo llamador. Asi el
  diseñador puede mover/redimensionar el ancla en Inkscape y el contenido se
  recoloca solo.

El flujo tipico desde `render_personaje.py`:

    tpl = plantillas.cargar("hero-card-up")
    arte = plantillas.ancla(tpl, "ph-arte")          # {x,y,width,height}
    cuerpo = plantillas.render(
        tpl,
        textos={"NOMBRE": nombre, "COLOR": color, ...},
        bloques={"ph-arte": svg_arte, "ph-stats": svg_stats},
    )   # -> contenido interior del <svg> (sin la etiqueta raiz)

`render` devuelve el INTERIOR del SVG (todo lo que hay entre `<svg ...>` y
`</svg>`), para que `render_personaje.py` lo envuelva en el `<svg>` raiz con el
tamaño fisico que corresponda.
"""

from __future__ import annotations

import re
import xml.sax.saxutils
from pathlib import Path

# Carpeta con las plantillas SVG de las cartas.
PLANTILLAS_DIR = Path(__file__).resolve().parent.parent / "sources" / "plantillas"

# Cache de contenido de plantillas ya leidas (nombre -> texto SVG crudo).
_CACHE: dict[str, str] = {}


def escapar(texto: str) -> str:
    """Escapa caracteres especiales de XML en un texto para insertarlo seguro."""
    return xml.sax.saxutils.escape(texto or "")


def cargar(nombre: str) -> str:
    """Devuelve el SVG crudo de la plantilla `<nombre>.svg`, cacheado.

    `nombre` es el nombre del fichero sin extension, p. ej.
    "anverso_descripcion", "anverso_stats", "verso_descripcion",
    "verso_stats".
    """
    if nombre not in _CACHE:
        ruta = PLANTILLAS_DIR / f"{nombre}.svg"
        if not ruta.exists():
            raise FileNotFoundError(f"No existe la plantilla: {ruta}")
        _CACHE[nombre] = ruta.read_text(encoding="utf-8")
    return _CACHE[nombre]


def limpiar_cache() -> None:
    """Vacia la cache de plantillas (util al iterar el diseño en desarrollo)."""
    _CACHE.clear()


# --- Lectura de anclas (cajas ph-*) --------------------------------------

# Un elemento <rect ... id="ph-arte" ...> con sus atributos geometricos.
def ancla(svg: str, id_ancla: str) -> dict[str, float] | None:
    """Devuelve la geometria del ancla `id_ancla`, o None si no esta.

    Busca el `<rect>` con `id="<id_ancla>"` (los atributos pueden ir en
    cualquier orden) y devuelve `{"x","y","width","height"}` como floats.
    """
    # Localiza la etiqueta <rect ...> que contiene id="id_ancla".
    patron_rect = re.compile(r"<rect\b[^>]*\bid=\"" + re.escape(id_ancla) + r"\"[^>]*/?>")
    m = patron_rect.search(svg)
    if not m:
        return None
    etiqueta = m.group(0)
    geom: dict[str, float] = {}
    for attr in ("x", "y", "width", "height"):
        am = re.search(r"\b" + attr + r"=\"([-\d.]+)\"", etiqueta)
        geom[attr] = float(am.group(1)) if am else 0.0
    return geom


def _eliminar_ancla(svg: str, id_ancla: str, reemplazo: str = "") -> str:
    """Sustituye el `<rect id="ph-...">` por `reemplazo` (por defecto, lo borra)."""
    patron_rect = re.compile(r"<rect\b[^>]*\bid=\"" + re.escape(id_ancla) + r"\"[^>]*/?>")
    return patron_rect.sub(lambda _m: reemplazo, svg, count=1)


# --- Extraccion del interior del <svg> raiz ------------------------------

def interior(svg: str) -> str:
    """Devuelve todo lo que hay entre `<svg ...>` y `</svg>` (sin esas etiquetas).

    Tambien descarta la declaracion `<?xml ...?>` y los comentarios de cabecera
    que haya antes del `<svg>` raiz. Los `<defs>` internos se conservan.
    """
    inicio = svg.find("<svg")
    if inicio == -1:
        return svg
    apertura_fin = svg.find(">", inicio)
    cierre = svg.rfind("</svg>")
    if apertura_fin == -1 or cierre == -1:
        return svg
    return svg[apertura_fin + 1:cierre]


# --- Render: sustitucion de textos y bloques -----------------------------

def render(
    plantilla: str,
    textos: dict[str, str] | None = None,
    bloques: dict[str, str] | None = None,
) -> str:
    """Rellena una plantilla y devuelve el INTERIOR de su SVG.

    Args:
        plantilla: SVG crudo de la plantilla (lo que devuelve `cargar`).
        textos: mapa CLAVE -> valor para los marcadores `{{CLAVE}}`. Los valores
            se escapan para XML salvo `COLOR` (y cualquier clave que empiece por
            `RAW_`), que se insertan tal cual (p. ej. un color hex `#aabbcc`).
        bloques: mapa `id_ancla` -> fragmento SVG. Cada `<rect id="id_ancla">`
            de la plantilla se sustituye por su fragmento. Un ancla no incluida
            aqui simplemente se elimina (no deja rastro en la carta final).

    Returns:
        El contenido interior del SVG (sin la etiqueta `<svg>` raiz).
    """
    textos = textos or {}
    bloques = bloques or {}

    svg = plantilla

    # 1) Sustituir bloques estructurales (anclas). Primero los que tienen
    #    fragmento; el resto de anclas ph-* se limpian despues.
    for id_ancla, fragmento in bloques.items():
        svg = _eliminar_ancla(svg, id_ancla, fragmento or "")

    # 2) Eliminar cualquier ancla ph-* que quede sin rellenar (guias de diseño).
    for id_ancla in re.findall(r'<rect\b[^>]*\bid="(ph-[\w-]+)"', svg):
        svg = _eliminar_ancla(svg, id_ancla, "")

    # 3) Sustituir marcadores de texto {{CLAVE}}.
    def _valor(clave: str) -> str:
        bruto = clave == "COLOR" or clave.startswith("RAW_")
        valor = textos.get(clave, "")
        return valor if bruto else escapar(valor)

    def _sub(m: re.Match) -> str:
        return _valor(m.group(1))

    svg = re.sub(r"\{\{\s*([\w]+)\s*\}\}", _sub, svg)

    # 4) Devolver solo el interior del <svg> (para componer/envolver fuera).
    return interior(svg)

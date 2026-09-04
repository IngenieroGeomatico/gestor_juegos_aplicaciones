# -*- coding: utf-8 -*-
"""Utilidades comunes de los motores de composición de cartas de HeroQuest.

Reúne lo que ``render_personaje.py`` (héroes/monstruos) y ``render_generico.py``
(items) tenían duplicado: constantes de la carta física, embebido de la fuente
Amarna, lectura del ``viewBox``, limpieza de prefijos que resvg no entiende,
incrustado de imágenes/SVG en las anclas ``ph-*`` y el rasterizado con resvg.

Los helpers son *puros* (reciben el SVG/geometría como argumentos y no dependen
de estado del módulo llamante), así que ambos motores los comparten sin cambiar
su comportamiento.
"""

from __future__ import annotations

import base64
import io
import re
import xml.sax.saxutils
from pathlib import Path

from PIL import Image, ImageOps

import plantillas

# Raíz del juego (…/juegos/heroquest), para resolver rutas relativas del JSON.
JUEGO_DIR = Path(__file__).resolve().parent.parent

# --- Fuente de la carta (Amarna, OFL-1.1) ---------------------------------
FUENTE_DIR = JUEGO_DIR / "sources" / "fuentes"
FUENTE_REGULAR = FUENTE_DIR / "Amarna-Regular.ttf"
FUENTE_BOLD = FUENTE_DIR / "Amarna-Bold.ttf"
# Reserva: la fuente variable original, si no existen las instancias estáticas.
FUENTE_TTF = FUENTE_DIR / "Amarna[wght].ttf"
FONT_FAMILY = "Amarna"

# --- Tamaño físico de la carta (63 × 88 mm a 300 DPI) ---------------------
MM_CARTA_ANCHO = 63
MM_CARTA_ALTO = 88
DPI_CARTA = 300
PX_CARTA_ANCHO = round(MM_CARTA_ANCHO / 25.4 * DPI_CARTA)   # 744
PX_CARTA_ALTO = round(MM_CARTA_ALTO / 25.4 * DPI_CARTA)     # 1039

# Mínimo de seguridad del factor viewBox -> px físicos al incrustar imágenes.
FACTOR_RES_MIN = 1.0


# --------------------------------------------------------------------------
# Rutas y assets
# --------------------------------------------------------------------------

def resolver(ruta: str) -> Path:
    """Resuelve una ruta del JSON (relativa a la carpeta del juego) a Path."""
    p = Path(ruta)
    return p if p.is_absolute() else JUEGO_DIR / p


def cargar_svg_texto(ruta: Path) -> str:
    """Lee un fichero SVG de disco (plantillas/assets referenciados por el JSON)."""
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la plantilla/asset: {ruta}")
    return ruta.read_text(encoding="utf-8")


def imagen_data_uri(
    ruta: Path, ancho: int, alto: int, preferir_jpeg: bool = True
) -> str:
    """Incrusta una imagen recortada "cover" (xMid/yMid slice) como data URI.

    Las imágenes con canal alfa (PNG con transparencia) se preservan como PNG,
    así el fondo transparente del arte NO se vuelve negro. Para las opacas:

    - ``preferir_jpeg=True`` (por defecto): se usan JPEG (más ligero). Es el
      comportamiento del motor de personajes.
    - ``preferir_jpeg=False``: se usan PNG sin pérdida. Es el comportamiento del
      motor genérico (items), que exige PNG siempre.
    """
    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im)
        tiene_alpha = im.mode in ("RGBA", "LA") or (
            im.mode == "P" and "transparency" in im.info
        )
        im = im.convert("RGBA" if tiene_alpha else "RGB")
        im = ImageOps.fit(im, (max(1, ancho), max(1, alto)), Image.LANCZOS)
        buf = io.BytesIO()
        if tiene_alpha or not preferir_jpeg:
            im.save(buf, format="PNG")
            mime = "png"
        else:
            im.save(buf, format="JPEG", quality=88)
            mime = "jpeg"
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# --------------------------------------------------------------------------
# Fuente embebida (@font-face)
# --------------------------------------------------------------------------

def _face(ruta: Path, peso: str) -> str:
    """Un bloque @font-face para `ruta` con el `font-weight` indicado."""
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{FONT_FAMILY}';font-style:normal;"
        f"font-weight:{peso};src:url('data:font/ttf;base64,{datos}')"
        " format('truetype');}"
    )


def font_face() -> str:
    """Devuelve un <style> con las caras Regular y Bold de la fuente embebidas.

    Embeber la fuente como @font-face con data URI garantiza que resvg la use.
    Se embeben caras estáticas Regular (400) y Bold (700) porque resvg no
    interpola la variable original y `font-weight:bold` no se aplicaría.
    """
    caras: list[str] = []
    if FUENTE_REGULAR.exists():
        caras.append(_face(FUENTE_REGULAR, "normal"))
    elif FUENTE_TTF.exists():
        caras.append(_face(FUENTE_TTF, "normal"))
    if FUENTE_BOLD.exists():
        caras.append(_face(FUENTE_BOLD, "bold"))
    if not caras:
        return ""
    return "<style>" + "".join(caras) + "</style>"


# --------------------------------------------------------------------------
# viewBox / limpieza para resvg
# --------------------------------------------------------------------------

def viewbox(svg: str) -> tuple[float, float, float, float]:
    """Devuelve (min_x, min_y, ancho, alto) del viewBox de un SVG."""
    m = re.search(r'viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"', svg)
    if not m:
        # Sin viewBox: usa width/height como tamaño y origen 0,0.
        aw = re.search(r'\bwidth="([-\d.eE]+)"', svg)
        ah = re.search(r'\bheight="([-\d.eE]+)"', svg)
        return (0.0, 0.0, float(aw.group(1)) if aw else 100.0,
                float(ah.group(1)) if ah else 100.0)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))


# Atributos y elementos con prefijos de Inkscape/sodipodi: resvg no los conoce
# y aborta con "unknown namespace prefix". Se eliminan del SVG compuesto final.
_RE_ATTR_NS = re.compile(r'\s+(?:inkscape|sodipodi|svg):[\w-]+="[^"]*"')
_RE_ELEM_NS = re.compile(r"<(?:inkscape|sodipodi):[\w-]+\b[^>]*/?>")


def limpiar_para_resvg(svg: str) -> str:
    """Quita atributos/elementos con prefijos que resvg no reconoce."""
    svg = _RE_ELEM_NS.sub("", svg)
    svg = _RE_ATTR_NS.sub("", svg)
    return svg


# --------------------------------------------------------------------------
# Colocación de contenido en las anclas ph-*
# --------------------------------------------------------------------------

def colocar_subsvg(sub_svg: str, geom: dict[str, float]) -> str:
    """Devuelve el interior de `sub_svg` escalado/trasladado al ancla `geom`.

    El sub-SVG (ribbon, hero-stats, borde…) se dibuja en sus propias
    coordenadas de viewBox; aquí lo posamos dentro de la caja del ancla
    respetando su origen.
    """
    min_x, min_y, vb_w, vb_h = viewbox(sub_svg)
    if vb_w <= 0 or vb_h <= 0:
        return ""
    escala_x = geom["width"] / vb_w
    escala_y = geom["height"] / vb_h
    interior = plantillas.interior(sub_svg)
    return (
        f'<g transform="translate({geom["x"]}, {geom["y"]}) '
        f'scale({escala_x}, {escala_y}) translate({-min_x}, {-min_y})">'
        f"{interior}</g>"
    )


def frag_imagen(
    ruta: Path, geom: dict[str, float], factor_res: float = 1.0,
    preferir_jpeg: bool = True,
) -> str:
    """Imagen recortada "cover" que llena exactamente el ancla `geom`.

    `factor_res` multiplica la resolución a la que se incrusta la imagen (los
    píxeles reales del data URI) sin cambiar su tamaño en el lienzo, para evitar
    el pixelado al rasterizar la carta a su resolución física. `preferir_jpeg`
    se propaga a `imagen_data_uri` (ver su docstring).
    """
    px_w = max(1, round(geom["width"] * factor_res))
    px_h = max(1, round(geom["height"] * factor_res))
    uri = imagen_data_uri(ruta, px_w, px_h, preferir_jpeg)
    return (
        f'<image x="{geom["x"]}" y="{geom["y"]}" '
        f'width="{geom["width"]}" height="{geom["height"]}" '
        f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
    )


def frag_fondo_svg(ruta: Path, geom: dict[str, float]) -> str:
    """Incrusta un SVG de fondo (p. ej. el borde) escalado a la caja `geom`."""
    svg = limpiar_para_resvg(cargar_svg_texto(ruta))
    return colocar_subsvg(svg, geom)


def frag_fondo(
    archivos: list[str], padre: str, factor_res: float = 1.0,
    preferir_jpeg: bool = True,
) -> str:
    """Fondo(s) ajustados al rectángulo de la carta (rect 'carta').

    Usa la geometría del `<rect id="carta">` de la plantilla padre como límite
    del fondo, para que encaje exactamente con la carta visible (y no con el
    viewBox completo, que incluye margen sobrante). Si no existe ese rect, cae
    al viewBox. `factor_res` multiplica la resolución de incrustado de las
    imágenes PNG/JPG. `preferir_jpeg` se propaga a `imagen_data_uri`.

    `archivos` es una lista en ORDEN DE RENDERIZADO: el primero va MÁS ABAJO
    (se pinta primero) y cada siguiente se superpone. Cada entrada puede ser una
    imagen (`.png`, `.jpg`, …) o un SVG (`.svg`, p. ej. el borde decorativo).
    """
    if not archivos:
        return ""

    caja = plantillas.ancla(padre, "carta")
    if caja and caja.get("width") and caja.get("height"):
        x, y, w, h = caja["x"], caja["y"], caja["width"], caja["height"]
    else:
        x, y, w, h = viewbox(padre)
    geom = {"x": x, "y": y, "width": w, "height": h}

    px_w = max(1, round(w * factor_res))
    px_h = max(1, round(h * factor_res))
    partes: list[str] = []
    for archivo in archivos:
        ruta = resolver(archivo)
        if not ruta.exists():
            continue
        if ruta.suffix.lower() == ".svg":
            partes.append(frag_fondo_svg(ruta, geom))
        else:
            uri = imagen_data_uri(ruta, px_w, px_h, preferir_jpeg)
            partes.append(
                f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
                f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
            )
    return "".join(partes)


def inyectar_fondo(cuerpo: str, fondo_frag: str) -> str:
    """Inserta el fondo como primer hijo del primer grupo <g ...> del cuerpo.

    Así el fondo hereda el mismo transform del grupo padre (donde viven las
    anclas y el rect 'carta') y queda detrás de todo el contenido.
    """
    if not fondo_frag:
        return cuerpo
    m = re.search(r"<g\b[^>]*>", cuerpo)
    if not m:
        return fondo_frag + cuerpo
    pos = m.end()
    return cuerpo[:pos] + fondo_frag + cuerpo[pos:]


def documento_svg(padre: str, cuerpo: str) -> str:
    """Envuelve `cuerpo` en el documento SVG final con viewBox y fuente embebida."""
    min_x, min_y, vb_w, vb_h = viewbox(padre)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{min_x} {min_y} {vb_w} {vb_h}" '
        f'width="{PX_CARTA_ANCHO}" height="{PX_CARTA_ALTO}">'
        f"{font_face()}{cuerpo}</svg>"
    )


def factor_res(padre: str) -> float:
    """Factor viewBox -> px físicos para incrustar imágenes a resolución real."""
    _, _, vb_w, _ = viewbox(padre)
    return max(FACTOR_RES_MIN, PX_CARTA_ANCHO / vb_w) if vb_w else FACTOR_RES_MIN


# --------------------------------------------------------------------------
# Rasterizado a PNG (resvg)
# --------------------------------------------------------------------------

def rasterizar(svg: str) -> Image.Image:
    """Rasteriza un SVG (str) a PNG (744 × 1039 px) con resvg."""
    import resvg_py

    datos = resvg_py.svg_to_bytes(
        svg_string=limpiar_para_resvg(svg),
        width=PX_CARTA_ANCHO,
        height=PX_CARTA_ALTO,
        background="#ffffff",
    )
    return Image.open(io.BytesIO(datos)).convert("RGB")

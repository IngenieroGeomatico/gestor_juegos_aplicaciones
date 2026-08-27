# -*- coding: utf-8 -*-
"""Motor de renderizado de cartas genéricas (armas, pociones, hechizos).

Usa la plantilla generic-card-up.svg / generic-card-down.svg.
Lee la receta de plantillas desde el campo "plantillas" del JSON.
"""

from __future__ import annotations

import base64
import io
import re
import xml.sax.saxutils
from pathlib import Path

from PIL import Image

import plantillas

# Raíz del juego (…/juegos/heroquest), para resolver rutas relativas.
JUEGO_DIR = Path(__file__).resolve().parent.parent

FUENTE_DIR = JUEGO_DIR / "sources" / "fuentes"
FUENTE_REGULAR = FUENTE_DIR / "Amarna-Regular.ttf"
FUENTE_BOLD = FUENTE_DIR / "Amarna-Bold.ttf"
FUENTE_TTF = FUENTE_DIR / "Amarna[wght].ttf"
FONT_FAMILY = "Amarna"

# --- Tamaño físico de la carta (idéntico al del sistema clásico) ---
MM_CARTA_ANCHO = 63
MM_CARTA_ALTO = 88
DPI_CARTA = 300
PX_CARTA_ANCHO = round(MM_CARTA_ANCHO / 25.4 * DPI_CARTA)
PX_CARTA_ALTO = round(MM_CARTA_ALTO / 25.4 * DPI_CARTA)

_COLOR_VALOR = "#3a2416"
_TAM_FUENTE_TITULO = 12
_TAM_FUENTE_TEXTO = 9
_TAM_FUENTE_VALOR = 10
_STROKE_TITULO = 0.3

# Tamaño del nombre en el ribbon (en coords del viewBox del ribbon)
_TAM_FUENTE_NOMBRE = 56


def _resolver(ruta: str) -> Path:
    """Resuelve una ruta (relativa a la carpeta del juego) a Path."""
    p = Path(ruta)
    return p if p.is_absolute() else JUEGO_DIR / p


def _imagen_data_uri(ruta: Path, ancho: int, alto: int) -> str:
    """Incrusta una imagen recortada "cover" como data URI PNG."""
    from PIL import ImageOps
    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im)
        tiene_alpha = im.mode in ("RGBA", "LA") or (
            im.mode == "P" and "transparency" in im.info
        )
        im = im.convert("RGBA" if tiene_alpha else "RGB")
        im = ImageOps.fit(im, (max(1, ancho), max(1, alto)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _face(ruta: Path, peso: str) -> str:
    """Un bloque @font-face para `ruta` con el `font-weight` indicado."""
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{FONT_FAMILY}';font-style:normal;"
        f"font-weight:{peso};src:url('data:font/ttf;base64,{datos}')"
        " format('truetype');}"
    )


def _font_face() -> str:
    """Devuelve un <style> con las caras Regular y Bold de la fuente embebidas."""
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


def _viewbox(svg: str) -> tuple[float, float, float, float]:
    """Devuelve (min_x, min_y, ancho, alto) del viewBox de un SVG."""
    m = re.search(r'viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"', svg)
    if not m:
        aw = re.search(r'\bwidth="([-\d.eE]+)"', svg)
        ah = re.search(r'\bheight="([-\d.eE]+)"', svg)
        return (0.0, 0.0, float(aw.group(1)) if aw else 100.0,
                float(ah.group(1)) if ah else 100.0)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))


def _colocar_subsvg(sub_svg: str, geom: dict[str, float]) -> str:
    """Devuelve el interior de `sub_svg` escalado/trasladado al ancla `geom`."""
    min_x, min_y, vb_w, vb_h = _viewbox(sub_svg)
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


def _limpiar_para_resvg(svg: str) -> str:
    """Quita atributos/elementos con prefijos que resvg no reconoce."""
    _RE_ATTR_NS = re.compile(r'\s+(?:inkscape|sodipodi|svg):[\w-]+="[^"]*"')
    _RE_ELEM_NS = re.compile(r"<(?:inkscape|sodipodi):[\w-]+\b[^>]*/?>")
    svg = _RE_ELEM_NS.sub("", svg)
    svg = _RE_ATTR_NS.sub("", svg)
    return svg


def _envolver_texto(texto: str, max_chars: int = 30) -> list[str]:
    """Envuelve el texto para que quepa en el ancho."""
    palabras = texto.split()
    lineas = []
    linea_actual = ""
    for palabra in palabras:
        if len(linea_actual) + len(palabra) + 1 <= max_chars:
            linea_actual += (" " if linea_actual else "") + palabra
        else:
            if linea_actual:
                lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)
    return lineas


def _frag_imagen(ruta: Path, geom: dict[str, float], factor_res: float) -> str:
    """Imagen recortada "cover" que llena exactamente el ancla `geom`."""
    px_w = max(1, round(geom["width"] * factor_res))
    px_h = max(1, round(geom["height"] * factor_res))
    uri = _imagen_data_uri(ruta, px_w, px_h)
    return (
        f'<image x="{geom["x"]}" y="{geom["y"]}" '
        f'width="{geom["width"]}" height="{geom["height"]}" '
        f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
    )


def _frag_fondo_svg(ruta: Path, geom: dict[str, float]) -> str:
    """Incrusta un SVG de fondo escalado a la caja `geom`."""
    svg = _limpiar_para_resvg(ruta.read_text(encoding="utf-8"))
    return _colocar_subsvg(svg, geom)


def _frag_fondo(entrada: dict, padre: str, factor_res: float) -> str:
    """Fondo(s) ajustados al rectángulo de la carta."""
    cara = entrada.get("plantillas", {}).get("cara", {})
    archivos = cara.get("archivos_fondo", [])
    if not archivos:
        return ""
    
    caja = plantillas.ancla(padre, "carta")
    if caja and caja.get("width") and caja.get("height"):
        x, y, w, h = caja["x"], caja["y"], caja["width"], caja["height"]
    else:
        x, y, w, h = _viewbox(padre)
    geom = {"x": x, "y": y, "width": w, "height": h}
    
    px_w = max(1, round(w * factor_res))
    px_h = max(1, round(h * factor_res))
    partes: list[str] = []
    for archivo in archivos:
        ruta = _resolver(archivo)
        if not ruta.exists():
            continue
        if ruta.suffix.lower() == ".svg":
            partes.append(_frag_fondo_svg(ruta, geom))
        else:
            uri = _imagen_data_uri(ruta, px_w, px_h)
            partes.append(
                f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
                f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
            )
    return "".join(partes)


def _frag_texto(texto: str, geom: dict[str, float]) -> str:
    """Bloque de texto centrado dentro del ancla `geom`."""
    if not texto:
        return ""
    cx = geom["x"] + geom["width"] / 2
    cy = geom["y"] + geom["height"] / 2
    lineas = _envolver_texto(texto)
    interlineado = _TAM_FUENTE_TEXTO * 1.3
    alto_bloque = interlineado * (len(lineas) - 1)
    y0 = cy + _TAM_FUENTE_TEXTO / 3 - alto_bloque / 2
    tspans = "".join(
        f'<tspan x="{cx}" '
        f'{"" if i == 0 else f"""dy="{interlineado}" """}>'
        f"{xml.sax.saxutils.escape(linea)}</tspan>"
        for i, linea in enumerate(lineas)
    )
    return (
        f'<text x="{cx}" y="{y0}" font-family="{FONT_FAMILY}" '
        f'font-size="{_TAM_FUENTE_TEXTO}" '
        f'text-anchor="middle" fill="{_COLOR_VALOR}">{tspans}</text>'
    )


def _frag_valor(valor: int, es_mente: bool, geom: dict[str, float]) -> str:
    """Texto del valor (oro o coste de mente) centrado en el ancla `geom`."""
    if valor <= 0:
        return ""
    cx = geom["x"] + geom["width"] / 2
    cy = geom["y"] + geom["height"] / 2 + _TAM_FUENTE_VALOR / 3
    texto = f"Coste: {valor} mente" if es_mente else f"Oro: {valor}"
    return (
        f'<text x="{cx}" y="{cy}" font-family="{FONT_FAMILY}" '
        f'font-size="{_TAM_FUENTE_VALOR}" font-weight="bold" '
        f'stroke="{_COLOR_VALOR}" stroke-width="{_STROKE_TITULO}" '
        f'paint-order="stroke" '
        f'text-anchor="middle" fill="{_COLOR_VALOR}">'
        f'{xml.sax.saxutils.escape(texto)}</text>'
    )


def _frag_titulo(nombre: str, geom: dict[str, float]) -> str:
    """Texto del título centrado en el ancla `geom`."""
    cx = geom["x"] + geom["width"] / 2
    cy = geom["y"] + geom["height"] / 2 + _TAM_FUENTE_TITULO / 3
    return (
        f'<text x="{cx}" y="{cy}" font-family="{FONT_FAMILY}" '
        f'font-size="{_TAM_FUENTE_TITULO}" font-weight="bold" '
        f'stroke="{_COLOR_VALOR}" stroke-width="{_STROKE_TITULO}" '
        f'paint-order="stroke" '
        f'text-anchor="middle" fill="{_COLOR_VALOR}">'
        f'{xml.sax.saxutils.escape(nombre)}</text>'
    )


def _frag_ribbon(ruta: Path, geom: dict[str, float], nombre: str) -> str:
    """La plantilla de leyenda (ribbon.svg) con {{NOMBRE}}, posada en `geom`."""
    import re as re_mod
    svg = _limpiar_para_resvg(ruta.read_text(encoding="utf-8"))
    svg = re_mod.sub(
        r"\{\{\s*NOMBRE\s*\}\}",
        lambda _m: xml.sax.saxutils.escape(nombre or ""),
        svg,
    )
    svg = svg.replace("font-size:12px", f"font-size:{_TAM_FUENTE_NOMBRE}px")
    svg = svg.replace("font-weight:normal", "font-weight:bold")
    return _colocar_subsvg(svg, geom)


def _receta_cara(entrada: dict) -> dict:
    """Devuelve la receta de la cara delantera."""
    plantillas_ent = entrada.get("plantillas") or {}
    cara = plantillas_ent.get("cara") or {}
    if not cara.get("plantilla_padre"):
        raise ValueError(
            f"El item '{entrada.get('nombre')}' no declara "
            "plantillas.cara.plantilla_padre en su JSON."
        )
    return cara


def _receta_dorso(entrada: dict) -> dict:
    """Devuelve la receta del dorso."""
    plantillas_ent = entrada.get("plantillas") or {}
    dorso = plantillas_ent.get("dorso") or {}
    if not dorso.get("plantilla_padre"):
        raise ValueError(
            f"El item '{entrada.get('nombre')}' no declara "
            "plantillas.dorso.plantilla_padre en su JSON."
        )
    return dorso


# --------------------------------------------------------------------------
# Rasterizado a PNG (resvg)
# --------------------------------------------------------------------------

def _rasterizar(svg: str) -> Image.Image:
    """Rasteriza un SVG (str) a PNG con resvg."""
    import resvg_py

    svg_limpio = _limpiar_para_resvg(svg)
    datos = resvg_py.svg_to_bytes(
        svg_string=svg_limpio,
        width=PX_CARTA_ANCHO,
        height=PX_CARTA_ALTO,
        background="#ffffff",
    )
    return Image.open(io.BytesIO(datos)).convert("RGB")


def render_svg(entrada: dict) -> str:
    """Compone el anverso de la carta genérica como SVG."""
    cara = _receta_cara(entrada)
    
    padre_ruta = _resolver(cara["plantilla_padre"])
    padre = padre_ruta.read_text(encoding="utf-8")

    _, _, vb_w, vb_h = _viewbox(padre)
    factor_res = max(1.0, PX_CARTA_ANCHO / vb_w) if vb_w else 1.0

    geom_arte = plantillas.ancla(padre, "ph-arte")
    geom_texto = plantillas.ancla(padre, "ph-texto")
    geom_dineros = plantillas.ancla(padre, "ph-dineros")
    geom_titulo = plantillas.ancla(padre, "ph-titulo")

    bloques: dict[str, str] = {}

    # ph-titulo <- nombre del item
    if geom_titulo:
        bloques["ph-titulo"] = _frag_titulo(entrada["nombre"], geom_titulo)

    # ph-arte <- imagen del item + marco SVG encima
    if geom_arte and cara.get("arte"):
        ruta = _resolver(cara["arte"])
        if ruta.exists():
            arte_frag = _frag_imagen(ruta, geom_arte, factor_res)
            # Si hay marco_arte, superponerlo encima del arte
            if cara.get("marco_arte"):
                marco_ruta = _resolver(cara["marco_arte"])
                if marco_ruta.exists():
                    svg_marco = _limpiar_para_resvg(marco_ruta.read_text(encoding="utf-8"))
                    marco_frag = _colocar_subsvg(svg_marco, geom_arte)
                    arte_frag = arte_frag + marco_frag
            bloques["ph-arte"] = arte_frag

    # ph-texto <- descripción
    if geom_texto and entrada.get("descripcion"):
        bloques["ph-texto"] = _frag_texto(entrada["descripcion"], geom_texto)

    # ph-dineros <- valor (oro o coste_mente)
    if geom_dineros:
        valor = entrada.get("coste", entrada.get("coste_mente", 0))
        es_mente = "coste_mente" in entrada
        bloques["ph-dineros"] = _frag_valor(valor, es_mente, geom_dineros)

    cuerpo = plantillas.render(padre, textos={}, bloques=bloques)
    
    # Añadir fondo como primer elemento del grupo principal
    fondo_frag = _frag_fondo(entrada, padre, factor_res)
    if fondo_frag:
        m = re.search(r"<g\b[^>]*>", cuerpo)
        if m:
            pos = m.end()
            cuerpo = cuerpo[:pos] + fondo_frag + cuerpo[pos:]

    min_x, min_y, vb_w, vb_h = _viewbox(padre)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{min_x} {min_y} {vb_w} {vb_h}" '
        f'width="{PX_CARTA_ANCHO}" height="{PX_CARTA_ALTO}">'
        f"{_font_face()}{cuerpo}</svg>"
    )


def _texto_ribbon(entrada: dict) -> str:
    """Devuelve el texto del ribbon según el tipo de item."""
    # Si es un hechizo, usar "Hechizo de {escuela}"
    escuela = entrada.get("escuela")
    if escuela:
        return f"Hechizo de {escuela}"
    # Para armas, pociones y otros: "Equipo"
    return "Equipo"


def render_svg_verso(entrada: dict) -> str:
    """Compone el dorso de la carta genérica como SVG."""
    dorso = _receta_dorso(entrada)
    
    padre_ruta = _resolver(dorso["plantilla_padre"])
    padre = padre_ruta.read_text(encoding="utf-8")

    geom_ribbon = plantillas.ancla(padre, "ph-ribbon")
    
    bloques: dict[str, str] = {}

    # ph-ribbon <- plantilla_leyenda con texto según tipo
    if geom_ribbon and dorso.get("plantilla_leyenda"):
        ruta_ribbon = _resolver(dorso["plantilla_leyenda"])
        if ruta_ribbon.exists():
            texto_ribbon = _texto_ribbon(entrada)
            bloques["ph-ribbon"] = _frag_ribbon(ruta_ribbon, geom_ribbon, texto_ribbon)

    _, _, vb_w, vb_h = _viewbox(padre)
    factor_res = max(1.0, PX_CARTA_ANCHO / vb_w) if vb_w else 1.0

    cuerpo = plantillas.render(padre, textos={}, bloques=bloques)
    
    # Añadir fondos del dorso
    archivos_fondo = dorso.get("archivos_fondo", [])
    if archivos_fondo:
        caja = plantillas.ancla(padre, "carta")
        if caja and caja.get("width") and caja.get("height"):
            x, y, w, h = caja["x"], caja["y"], caja["width"], caja["height"]
        else:
            x, y, w, h = _viewbox(padre)
        geom = {"x": x, "y": y, "width": w, "height": h}
        
        px_w = max(1, round(w * factor_res))
        px_h = max(1, round(h * factor_res))
        partes_fondo: list[str] = []
        for archivo in archivos_fondo:
            ruta = _resolver(archivo)
            if not ruta.exists():
                continue
            if ruta.suffix.lower() == ".svg":
                partes_fondo.append(_frag_fondo_svg(ruta, geom))
            else:
                uri = _imagen_data_uri(ruta, px_w, px_h)
                partes_fondo.append(
                    f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
                    f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
                )
        fondo_frag = "".join(partes_fondo)
        if fondo_frag:
            m = re.search(r"<g\b[^>]*>", cuerpo)
            if m:
                pos = m.end()
                cuerpo = cuerpo[:pos] + fondo_frag + cuerpo[pos:]

    min_x, min_y, vb_w, vb_h = _viewbox(padre)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{min_x} {min_y} {vb_w} {vb_h}" '
        f'width="{PX_CARTA_ANCHO}" height="{PX_CARTA_ALTO}">'
        f"{_font_face()}{cuerpo}</svg>"
    )


def render_png(entrada: dict) -> Image.Image:
    """Rasteriza el anverso de la carta genérica a PNG."""
    return _rasterizar(render_svg(entrada))


def render_png_verso(entrada: dict) -> Image.Image:
    """Rasteriza el dorso de la carta genérica a PNG."""
    return _rasterizar(render_svg_verso(entrada))

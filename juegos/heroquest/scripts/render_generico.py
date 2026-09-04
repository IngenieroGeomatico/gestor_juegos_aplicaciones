# -*- coding: utf-8 -*-
"""Motor de renderizado de cartas genéricas (armas, pociones, hechizos).

Usa la plantilla generic-card-up.svg / generic-card-down.svg.
Lee la receta de plantillas desde el campo "plantillas" del JSON.
"""

from __future__ import annotations

import re
import xml.sax.saxutils
from pathlib import Path

from PIL import Image

import plantillas
from render_utils import (
    FONT_FAMILY,
    PX_CARTA_ANCHO,
    colocar_subsvg as _colocar_subsvg,
    documento_svg as _documento_svg,
    factor_res as _factor_res,
    frag_fondo as _frag_fondo_util,
    frag_imagen as _frag_imagen,
    imagen_data_uri as _imagen_data_uri,
    inyectar_fondo as _inyectar_fondo,
    limpiar_para_resvg as _limpiar_para_resvg,
    rasterizar as _rasterizar,
    resolver as _resolver,
    viewbox as _viewbox,
)

_COLOR_VALOR = "#3a2416"
_TAM_FUENTE_TITULO = 12
_TAM_FUENTE_TEXTO = 9
_TAM_FUENTE_VALOR = 10
_STROKE_TITULO = 0.3

# Tamaño del nombre en el ribbon (en coords del viewBox del ribbon)
_TAM_FUENTE_NOMBRE = 56


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


def _frag_fondo(entrada: dict, padre: str, factor_res: float) -> str:
    """Fondo(s) de la cara delantera ajustados al rectángulo de la carta.

    El motor genérico incrusta siempre en PNG (sin pérdida), de ahí
    ``preferir_jpeg=False``.
    """
    cara = entrada.get("plantillas", {}).get("cara", {})
    return _frag_fondo_util(
        cara.get("archivos_fondo", []), padre, factor_res, preferir_jpeg=False
    )


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
    svg = _limpiar_para_resvg(ruta.read_text(encoding="utf-8"))
    svg = re.sub(
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


def render_svg(entrada: dict) -> str:
    """Compone el anverso de la carta genérica como SVG."""
    cara = _receta_cara(entrada)
    
    padre_ruta = _resolver(cara["plantilla_padre"])
    padre = padre_ruta.read_text(encoding="utf-8")

    factor_res = _factor_res(padre)

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
            arte_frag = _frag_imagen(ruta, geom_arte, factor_res, preferir_jpeg=False)
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

    # Añadir fondo como primer elemento del grupo principal (detrás de todo).
    fondo_frag = _frag_fondo(entrada, padre, factor_res)
    cuerpo = _inyectar_fondo(cuerpo, fondo_frag)

    return _documento_svg(padre, cuerpo)


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

    factor_res = _factor_res(padre)

    cuerpo = plantillas.render(padre, textos={}, bloques=bloques)

    # Añadir fondos del dorso (detrás de todo el contenido). PNG sin pérdida.
    fondo_frag = _frag_fondo_util(
        dorso.get("archivos_fondo", []), padre, factor_res, preferir_jpeg=False
    )
    cuerpo = _inyectar_fondo(cuerpo, fondo_frag)

    return _documento_svg(padre, cuerpo)


def render_png(entrada: dict) -> Image.Image:
    """Rasteriza el anverso de la carta genérica a PNG."""
    return _rasterizar(render_svg(entrada))


def render_png_verso(entrada: dict) -> Image.Image:
    """Rasteriza el dorso de la carta genérica a PNG."""
    return _rasterizar(render_svg_verso(entrada))

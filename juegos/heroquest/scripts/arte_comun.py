# -*- coding: utf-8 -*-
"""Utilidades compartidas por los generadores de arte de HeroQuest.

Reúne lo común a `generar_arte.py`, `generar_retratos.py` y `generar_fondos.py`:
- `slug`: nombre de fichero seguro (mismo criterio que `data_store.slug`).
- `rasterizar`: convierte un SVG (str) en un PNG con `resvg` (resvg_py), la misma
  librería que usa `render_carta.py`. El SVG es la fuente de verdad; el PNG es
  su rasterización.
"""

from __future__ import annotations

from pathlib import Path

from data_store import slug  # reexportado: único punto de importación para el arte

__all__ = ["slug", "rasterizar"]


def rasterizar(svg: str, ruta_png: Path, ancho: int, alto: int) -> None:
    """Rasteriza un SVG a PNG (ancho×alto) y lo escribe en `ruta_png`."""
    import resvg_py

    datos = resvg_py.svg_to_bytes(svg_string=svg, width=ancho, height=alto)
    if not isinstance(datos, (bytes, bytearray)):
        datos = bytes(datos)
    ruta_png.write_bytes(datos)

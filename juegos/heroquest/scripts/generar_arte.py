# -*- coding: utf-8 -*-
"""Genera el arte de anverso de las cartas de HeroQuest de forma reproducible.

Cada objeto (espada, hacha, poción, ...) se dibuja como un SVG vectorial
detallado sobre el fondo degradado morado característico y se rasteriza a PNG
con resvg (la misma librería que usa el motor de render `render_personaje.py`).

- Los SVG (fuente de verdad, editables) se guardan en `sources/arte_svg/`.
- Los PNG finales se guardan en `sources/arte/` con el nombre de convención
  (el `slug` del nombre de la carta, p. ej.
  `Espada_corta.png`, `Báculo_del_mago.png`).

Uso:
    uv run juegos/heroquest/scripts/generar_arte.py            # genera todo
    uv run juegos/heroquest/scripts/generar_arte.py --solo Daga
    uv run juegos/heroquest/scripts/generar_arte.py --svg-solo # solo SVG, sin PNG
"""

from __future__ import annotations

import argparse
from pathlib import Path

from arte_comun import rasterizar as _rasterizar_png
from arte_comun import slug as _slug

ARTE_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte"
ARTE_SVG_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_svg"

ANCHO, ALTO = 700, 500


# ---------------------------------------------------------------------------
# Bloques comunes: fondo, halo, degradados de materiales y filtro de sombra.
# ---------------------------------------------------------------------------

DEFS = """
  <defs>
    <radialGradient id="fondo" cx="50%" cy="55%" r="65%">
      <stop offset="0%" stop-color="#3a3350"/>
      <stop offset="55%" stop-color="#211d33"/>
      <stop offset="100%" stop-color="#14111f"/>
    </radialGradient>
    <radialGradient id="halo" cx="50%" cy="48%" r="52%">
      <stop offset="0%" stop-color="#ffdca8" stop-opacity="0.34"/>
      <stop offset="45%" stop-color="#e8b878" stop-opacity="0.11"/>
      <stop offset="100%" stop-color="#e8b878" stop-opacity="0"/>
    </radialGradient>

    <linearGradient id="acero" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#7f889b"/>
      <stop offset="28%" stop-color="#d4dae4"/>
      <stop offset="50%" stop-color="#ffffff"/>
      <stop offset="60%" stop-color="#c3cbd8"/>
      <stop offset="100%" stop-color="#646c7d"/>
    </linearGradient>
    <linearGradient id="acero-h" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#7f889b"/>
      <stop offset="28%" stop-color="#d4dae4"/>
      <stop offset="50%" stop-color="#ffffff"/>
      <stop offset="60%" stop-color="#c3cbd8"/>
      <stop offset="100%" stop-color="#646c7d"/>
    </linearGradient>
    <linearGradient id="acero-lustre" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95"/>
      <stop offset="35%" stop-color="#ffffff" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>

    <linearGradient id="oro" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="#f6d98a"/>
      <stop offset="45%" stop-color="#c99a3f"/>
      <stop offset="100%" stop-color="#7d5a1e"/>
    </linearGradient>
    <radialGradient id="oro-pomo" cx="38%" cy="32%" r="72%">
      <stop offset="0%"  stop-color="#ffe9ad"/>
      <stop offset="55%" stop-color="#c99a3f"/>
      <stop offset="100%" stop-color="#6f4e18"/>
    </radialGradient>

    <linearGradient id="cuero" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#5c3a1e"/>
      <stop offset="50%" stop-color="#8a5a2f"/>
      <stop offset="100%" stop-color="#42280f"/>
    </linearGradient>

    <linearGradient id="madera" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#5a3a1c"/>
      <stop offset="45%" stop-color="#9a6b3a"/>
      <stop offset="55%" stop-color="#84592e"/>
      <stop offset="100%" stop-color="#3f2711"/>
    </linearGradient>

    <radialGradient id="gema-azul" cx="38%" cy="30%" r="75%">
      <stop offset="0%" stop-color="#cfe4ff"/>
      <stop offset="40%" stop-color="#5b8be0"/>
      <stop offset="100%" stop-color="#1f3f8a"/>
    </radialGradient>
    <radialGradient id="gema-roja" cx="38%" cy="30%" r="75%">
      <stop offset="0%" stop-color="#ffd0cf"/>
      <stop offset="40%" stop-color="#e0555b"/>
      <stop offset="100%" stop-color="#8a1f2a"/>
    </radialGradient>
    <radialGradient id="gema-verde" cx="38%" cy="30%" r="75%">
      <stop offset="0%" stop-color="#d4ffdf"/>
      <stop offset="40%" stop-color="#4fbf7a"/>
      <stop offset="100%" stop-color="#1a6b3a"/>
    </radialGradient>
    <radialGradient id="pocion-roja" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#ff9a8f"/>
      <stop offset="45%" stop-color="#e23b46"/>
      <stop offset="100%" stop-color="#8f1420"/>
    </radialGradient>
    <linearGradient id="vidrio" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.55"/>
      <stop offset="30%" stop-color="#cfe0e6" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#7d9aa6" stop-opacity="0.30"/>
    </linearGradient>

    <!-- Hechizos -->
    <radialGradient id="fuego" cx="50%" cy="58%" r="60%">
      <stop offset="0%" stop-color="#fff3c0"/>
      <stop offset="35%" stop-color="#ffd23a"/>
      <stop offset="70%" stop-color="#f06a1e"/>
      <stop offset="100%" stop-color="#a01f10"/>
    </radialGradient>
    <radialGradient id="curacion" cx="50%" cy="45%" r="60%">
      <stop offset="0%" stop-color="#eafff0"/>
      <stop offset="45%" stop-color="#7fe6a2"/>
      <stop offset="100%" stop-color="#2a9a5a"/>
    </radialGradient>
    <radialGradient id="caos" cx="45%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#e0b0ff"/>
      <stop offset="45%" stop-color="#8a3fd0"/>
      <stop offset="100%" stop-color="#3a1060"/>
    </radialGradient>

    <filter id="sombra" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>
"""


def _lienzo(cuerpo: str, halo=("350", "240", "235", "205")) -> str:
    cx, cy, rx, ry = halo
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" '
        f'viewBox="0 0 {ANCHO} {ALTO}">{DEFS}'
        f'<rect width="{ANCHO}" height="{ALTO}" fill="url(#fondo)"/>'
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#halo)"/>'
        f'<g filter="url(#sombra)">{cuerpo}</g>'
        f"</svg>\n"
    )


# ---------------------------------------------------------------------------
# Piezas reutilizables (en coordenadas locales; usar dentro de un <g transform>)
# ---------------------------------------------------------------------------

def _envoltura(x0, x1, y_ini, n, paso):
    """Líneas diagonales de cuero envuelto en una empuñadura."""
    out = []
    for i in range(n):
        y = y_ini + i * paso
        out.append(f'<path d="M {x0} {y+6} L {x1} {y}" stroke="#2e1a09" stroke-width="3" opacity="0.7"/>')
    return "".join(out)


def _empunadura(cx, y, w, h, envolturas):
    """Empuñadura de cuero centrada en cx, desde y, con envoltura diagonal."""
    x0, x1 = cx - w / 2, cx + w / 2
    return (
        f'<rect x="{x0}" y="{y}" width="{w}" height="{h}" rx="{w*0.27:.1f}" '
        f'fill="url(#cuero)" stroke="#2e1a09" stroke-width="2"/>'
        + _envoltura(x0, x1, y + 12, envolturas, 12)
        + f'<rect x="{cx-w*0.3:.1f}" y="{y+4}" width="{w*0.18:.1f}" height="{h-8}" '
          f'rx="2.2" fill="#b07a42" opacity="0.5"/>'
    )


def _pomo(cx, cy, r):
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#oro-pomo)" '
        f'stroke="#5c4413" stroke-width="2.5"/>'
        f'<circle cx="{cx-r*0.32:.1f}" cy="{cy-r*0.32:.1f}" r="{r*0.28:.1f}" '
        f'fill="#fff2cf" opacity="0.75"/>'
    )


def _guarda_recta(cx, y, semiancho, alto):
    """Guarda cruzada horizontal con remates redondeados y brillo."""
    x = cx - semiancho
    w = semiancho * 2
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{alto}" rx="{alto/2}" '
        f'fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
        f'<circle cx="{x}" cy="{y+alto/2}" r="{alto*0.6:.1f}" fill="url(#oro-pomo)" '
        f'stroke="#5c4413" stroke-width="2"/>'
        f'<circle cx="{x+w}" cy="{y+alto/2}" r="{alto*0.6:.1f}" fill="url(#oro-pomo)" '
        f'stroke="#5c4413" stroke-width="2"/>'
        f'<rect x="{x+8}" y="{y+3}" width="{w-16}" height="{alto*0.28:.1f}" '
        f'rx="3" fill="#ffe9ad" opacity="0.6"/>'
    )


def _hoja(cx, punta_y, hombro_y, base_y, semiancho, fuller=True):
    """Hoja de espada: punta triangular arriba, cuerpo recto, con bisel y lustre."""
    l, r = cx - semiancho, cx + semiancho
    partes = [
        f'<path d="M {cx} {punta_y} L {r} {hombro_y} L {r} {base_y} '
        f'L {l} {base_y} L {l} {hombro_y} Z" fill="url(#acero)" '
        f'stroke="#454b5b" stroke-width="2" stroke-linejoin="round"/>',
        # lado derecho sombreado (volumen)
        f'<path d="M {cx} {punta_y} L {r} {hombro_y} L {r} {base_y} '
        f'L {cx+semiancho*0.35:.1f} {base_y} L {cx+semiancho*0.35:.1f} {hombro_y+4} Z" '
        f'fill="#5b6376" opacity="0.5"/>',
    ]
    if fuller:
        partes.append(
            f'<rect x="{cx-semiancho*0.17:.1f}" y="{hombro_y+8}" '
            f'width="{semiancho*0.34:.1f}" height="{base_y-hombro_y-12}" '
            f'rx="2.5" fill="#67707f" opacity="0.6"/>'
        )
    partes.append(
        f'<path d="M {cx-semiancho*0.66:.1f} {hombro_y+4} '
        f'L {cx-semiancho*0.22:.1f} {hombro_y+4} '
        f'L {cx-semiancho*0.22:.1f} {base_y-10} L {cx-semiancho*0.5:.1f} {base_y} '
        f'L {cx-semiancho*0.66:.1f} {base_y-10} Z" fill="url(#acero-lustre)"/>'
    )
    # brillo cerca de la punta
    partes.append(
        f'<path d="M {cx} {punta_y+6} L {cx+semiancho*0.45:.1f} {hombro_y-4} '
        f'L {cx-semiancho*0.45:.1f} {hombro_y-4} Z" fill="#ffffff" opacity="0.8"/>'
    )
    return "".join(partes)


def _gema(cx, cy, rx, ry, fill):
    return (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" '
        f'stroke="#3a2a10" stroke-width="2"/>'
        f'<ellipse cx="{cx-rx*0.3:.1f}" cy="{cy-ry*0.35:.1f}" rx="{rx*0.32:.1f}" '
        f'ry="{ry*0.28:.1f}" fill="#ffffff" opacity="0.6"/>'
    )


def _engaste(cx, cy, r):
    """Aro dorado alrededor de una gema."""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="url(#oro)" stroke-width="5"/>'
    )


# ---------------------------------------------------------------------------
# Objetos
# ---------------------------------------------------------------------------

def espada_corta() -> str:
    g = f'<g transform="translate(350 0)">'
    g += _hoja(0, 40, 78, 315, 15)
    g += _guarda_recta(0, 312, 88, 22)
    g += _empunadura(0, 334, 26, 86, 6)
    g += _pomo(0, 430, 19)
    g += "</g>"
    return _lienzo(g)


def daga() -> str:
    # Hoja más corta y ancha; empuñadura proporcionalmente mayor.
    g = f'<g transform="translate(350 0)">'
    g += _hoja(0, 120, 158, 300, 17)
    g += _guarda_recta(0, 298, 60, 20)
    g += _empunadura(0, 318, 26, 74, 5)
    g += _pomo(0, 400, 17)
    g += "</g>"
    return _lienzo(g)


def mandoble() -> str:
    # Hoja larga y ancha, guarda amplia, empuñadura larga a dos manos.
    g = f'<g transform="translate(350 0)">'
    g += _hoja(0, 22, 66, 300, 22)
    g += _guarda_recta(0, 296, 110, 24)
    g += _empunadura(0, 320, 30, 120, 8)
    g += _pomo(0, 452, 22)
    g += "</g>"
    return _lienzo(g)


def hacha_de_batalla() -> str:
    g = '<g transform="translate(350 0)">'
    # Mango de madera vertical
    g += ('<rect x="-11" y="80" width="22" height="350" rx="10" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2"/>')
    g += '<rect x="-6" y="86" width="4" height="338" rx="2" fill="#c69a5f" opacity="0.4"/>'
    # Refuerzo inferior del mango
    g += ('<rect x="-14" y="418" width="28" height="16" rx="6" fill="url(#oro)" '
          'stroke="#5c4413" stroke-width="2"/>')
    # Cabeza de hacha de doble filo (geometría recta, dos hojas en media luna).
    # Hoja izquierda
    hoja_izq = ('M -6 118 '
                'L -46 104 L -128 120 '
                'L -150 176 '
                'L -128 232 L -46 248 L -6 234 Z')
    # Hoja derecha (espejo)
    hoja_der = ('M 6 118 '
                'L 46 104 L 128 120 '
                'L 150 176 '
                'L 128 232 L 46 248 L 6 234 Z')
    for hoja in (hoja_izq, hoja_der):
        g += (f'<path d="{hoja}" fill="url(#acero-h)" stroke="#454b5b" '
              'stroke-width="2.5" stroke-linejoin="round"/>')
    # Filos exteriores brillantes (borde afilado)
    g += ('<path d="M -128 120 L -150 176 L -128 232" fill="none" '
          'stroke="#ffffff" stroke-width="4" opacity="0.55" stroke-linecap="round"/>')
    g += ('<path d="M 128 120 L 150 176 L 128 232" fill="none" '
          'stroke="#ffffff" stroke-width="4" opacity="0.55" stroke-linecap="round"/>')
    # Bisel interior sombreado
    g += '<path d="M -6 128 L -44 116 L -44 236 L -6 224 Z" fill="#5b6376" opacity="0.4"/>'
    g += '<path d="M 6 128 L 44 116 L 44 236 L 6 224 Z" fill="#8fa0b5" opacity="0.35"/>'
    # Cubo central (ojo del hacha) que envuelve el mango
    g += ('<rect x="-16" y="112" width="32" height="128" rx="8" fill="url(#acero-h)" '
          'stroke="#454b5b" stroke-width="2.5"/>')
    g += '<rect x="-11" y="118" width="6" height="116" rx="3" fill="#ffffff" opacity="0.4"/>'
    # Anillos de refuerzo del cubo
    g += '<rect x="-18" y="120" width="36" height="8" rx="4" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    g += '<rect x="-18" y="224" width="36" height="8" rx="4" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    # Remate superior del mango
    g += _pomo(0, 92, 13)
    g += "</g>"
    return _lienzo(g, halo=("350", "185", "255", "180"))


def ballesta() -> str:
    g = '<g transform="translate(350 250)">'
    # Cureña (cuerpo horizontal de madera)
    g += ('<rect x="-30" y="-16" width="210" height="32" rx="10" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2"/>')
    g += '<rect x="-24" y="-12" width="196" height="6" rx="3" fill="#c69a5f" opacity="0.4"/>'
    # Culata trasera
    g += ('<path d="M 150 -16 L 200 -30 L 210 6 L 150 16 Z" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2"/>')
    # Arco de acero (curvo, vertical) al frente
    g += ('<path d="M -40 -110 C -95 -60 -95 60 -40 110" fill="none" '
          'stroke="url(#acero-h)" stroke-width="16" stroke-linecap="round"/>')
    g += ('<path d="M -40 -110 C -95 -60 -95 60 -40 110" fill="none" '
          'stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.4"/>')
    # Cuerda tensada
    g += ('<path d="M -58 -96 L 40 0 L -58 96" fill="none" '
          'stroke="#e8e2d0" stroke-width="3.5" stroke-linejoin="round"/>')
    # Virote (flecha) cargado sobre la cureña
    g += ('<rect x="20" y="-3.5" width="150" height="7" rx="3" fill="#6a4a26" '
          'stroke="#2e1a09" stroke-width="1.5"/>')
    g += '<path d="M 20 0 L 42 -12 L 42 12 Z" fill="url(#acero-h)" stroke="#454b5b" stroke-width="1.5"/>'
    # Plumas del virote
    g += '<path d="M 160 0 L 178 -12 L 172 0 L 178 12 Z" fill="#b5453f" stroke="#5c1c18" stroke-width="1"/>'
    # Gatillo
    g += ('<path d="M 96 16 L 90 40 L 104 40 L 108 16 Z" fill="url(#oro)" '
          'stroke="#5c4413" stroke-width="1.5"/>')
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "255", "175"))


def baculo_del_mago() -> str:
    g = '<g transform="translate(350 0)">'
    # Vara de madera con nudos
    g += ('<rect x="-9" y="150" width="18" height="300" rx="9" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2"/>')
    g += '<rect x="-5" y="156" width="3.5" height="288" rx="2" fill="#c69a5f" opacity="0.4"/>'
    for y in (215, 285, 355):
        g += f'<ellipse cx="0" cy="{y}" rx="12" ry="7" fill="#5a3a1c" stroke="#2e1a09" stroke-width="1.5"/>'
    # Corona de garras que sujeta la gema
    g += ('<path d="M -26 150 C -30 118 -14 108 0 110 C 14 108 30 118 26 150 '
          'C 12 140 -12 140 -26 150 Z" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>')
    # Gema superior brillante
    g += _gema(0, 100, 30, 38, "url(#gema-azul)")
    # Destellos alrededor de la gema
    g += ('<g stroke="#dfeaff" stroke-width="3" stroke-linecap="round" opacity="0.8">'
          '<path d="M 0 46 L 0 30"/><path d="M -46 100 L -62 100"/>'
          '<path d="M 46 100 L 62 100"/><path d="M -34 66 L -46 54"/>'
          '<path d="M 34 66 L 46 54"/></g>')
    g += "</g>"
    return _lienzo(g, halo=("350", "150", "230", "210"))


def armadura_de_placas() -> str:
    g = '<g transform="translate(350 0)">'
    # Peto (coraza)
    coraza = ('M -95 150 '
              'C -110 145 -120 158 -116 178 '
              'L -104 320 C -100 372 -54 405 0 408 '
              'C 54 405 100 372 104 320 '
              'L 116 178 C 120 158 110 145 95 150 '
              'C 60 168 -60 168 -95 150 Z')
    g += (f'<path d="{coraza}" fill="url(#acero-h)" stroke="#454b5b" '
          'stroke-width="3" stroke-linejoin="round"/>')
    # Sombra lateral derecha
    g += ('<path d="M 0 168 C 40 168 78 162 104 150 L 116 178 '
          'C 120 158 110 145 95 150 C 66 165 33 168 0 168 Z" '
          'fill="#5b6376" opacity="0.4"/>')
    # Reflejo central
    g += ('<path d="M -20 175 C -24 260 -18 340 0 395 C 6 340 4 260 6 175 Z" '
          'fill="#ffffff" opacity="0.28"/>')
    # Línea central esternón
    g += '<path d="M 0 172 L 0 400" stroke="#3a4150" stroke-width="2.5" opacity="0.6"/>'
    # Rebordes dorados (cuello y cintura)
    g += ('<path d="M -92 156 C -55 172 55 172 92 156" fill="none" '
          'stroke="url(#oro)" stroke-width="8" stroke-linecap="round"/>')
    g += ('<path d="M -104 300 C -55 330 55 330 104 300" fill="none" '
          'stroke="url(#oro)" stroke-width="7" stroke-linecap="round"/>')
    # Hombreras (pauldrons)
    for sgn in (-1, 1):
        cx = sgn * 108
        g += (f'<path d="M {cx-46*sgn} 150 C {cx-52*sgn} 118 {cx+8*sgn} 110 {cx+30*sgn} 138 '
              f'C {cx+34*sgn} 156 {cx+20*sgn} 172 {cx-6*sgn} 172 Z" '
              'fill="url(#acero-h)" stroke="#454b5b" stroke-width="2.5" stroke-linejoin="round"/>')
        g += (f'<path d="M {cx-40*sgn} 150 C {cx-44*sgn} 130 {cx-4*sgn} 124 {cx+16*sgn} 140" '
              'fill="none" stroke="#ffffff" stroke-width="3" opacity="0.45" stroke-linecap="round"/>')
    # Remache central
    g += _gema(0, 250, 12, 14, "url(#gema-roja)")
    g += "</g>"
    return _lienzo(g, halo=("350", "260", "245", "195"))


def yelmo() -> str:
    g = '<g transform="translate(350 0)">'
    # Cúpula del casco
    g += ('<path d="M -96 250 C -96 150 -50 96 0 96 C 50 96 96 150 96 250 Z" '
          'fill="url(#acero-h)" stroke="#454b5b" stroke-width="3" stroke-linejoin="round"/>')
    # Sombra derecha y reflejo
    g += ('<path d="M 0 100 C 44 104 82 156 90 244 L 96 250 '
          'C 96 150 50 96 0 96 Z" fill="#5b6376" opacity="0.4"/>')
    g += ('<path d="M -46 130 C -66 160 -74 210 -72 248" fill="none" '
          'stroke="#ffffff" stroke-width="6" opacity="0.4" stroke-linecap="round"/>')
    # Banda frontal y nasal
    g += '<rect x="-96" y="240" width="192" height="22" rx="8" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    g += ('<path d="M -14 250 L -14 340 C -14 350 14 350 14 340 L 14 250 Z" '
          'fill="url(#acero-h)" stroke="#454b5b" stroke-width="2.5"/>')
    # Ranuras de los ojos
    g += '<rect x="-70" y="200" width="46" height="16" rx="8" fill="#20242e"/>'
    g += '<rect x="24" y="200" width="46" height="16" rx="8" fill="#20242e"/>'
    # Cimera (penacho)
    g += ('<path d="M 0 96 C -6 60 -2 40 10 26 C 6 46 12 62 18 80 '
          'C 26 60 40 52 54 50 C 40 66 34 86 24 100 Z" '
          'fill="url(#gema-roja)" stroke="#8a1f2a" stroke-width="2" stroke-linejoin="round"/>')
    # Remaches
    for x in (-78, -40, 40, 78):
        g += f'<circle cx="{x}" cy="251" r="4.5" fill="#6f4e18" stroke="#3a2a10" stroke-width="1"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "215", "235", "195"))


def escudo() -> str:
    g = '<g transform="translate(350 0)">'
    # Silueta de escudo heráldico (heater)
    forma = ('M 0 90 L 128 118 L 118 250 '
             'C 110 330 60 388 0 418 '
             'C -60 388 -110 330 -118 250 '
             'L -128 118 Z')
    # Borde metálico
    g += f'<path d="{forma}" fill="url(#oro)" stroke="#5c4413" stroke-width="3" stroke-linejoin="round"/>'
    # Campo interior (blasón)
    campo = ('M 0 108 L 110 132 L 101 246 '
             'C 94 318 52 368 0 396 '
             'C -52 368 -94 318 -101 246 '
             'L -110 132 Z')
    g += f'<path d="{campo}" fill="url(#acero-h)" stroke="#454b5b" stroke-width="2"/>'
    # División y reflejo
    g += '<path d="M 0 112 L 0 392" stroke="#3a4150" stroke-width="2" opacity="0.4"/>'
    g += ('<path d="M -96 140 L -8 122 L -8 388 C -52 362 -88 316 -96 250 Z" '
          'fill="#ffffff" opacity="0.16"/>')
    # Umbo central con gema
    g += _engaste(0, 250, 40)
    g += _gema(0, 250, 30, 30, "url(#gema-roja)")
    # Remaches del borde
    for (x, y) in [(-90, 140), (90, 140), (-70, 300), (70, 300), (0, 380)]:
        g += f'<circle cx="{x}" cy="{y}" r="6" fill="url(#oro-pomo)" stroke="#5c4413" stroke-width="1.5"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "230", "205"))


def pocion_de_curacion() -> str:
    g = '<g transform="translate(350 0)">'
    # Cuerpo bulboso del frasco
    cuerpo = ('M -34 230 '
              'C -70 250 -84 300 -84 340 '
              'C -84 400 -40 440 0 440 '
              'C 40 440 84 400 84 340 '
              'C 84 300 70 250 34 230 Z')
    # Líquido rojo (recortado dentro del cuerpo)
    g += '<clipPath id="clip-pocion"><path d="' + cuerpo + '"/></clipPath>'
    g += f'<path d="{cuerpo}" fill="#0d1420" opacity="0.5"/>'
    g += ('<g clip-path="url(#clip-pocion)">'
          '<rect x="-90" y="300" width="180" height="160" fill="url(#pocion-roja)"/>'
          # burbujas
          '<circle cx="-24" cy="360" r="7" fill="#ffb0a6" opacity="0.7"/>'
          '<circle cx="14" cy="392" r="10" fill="#ffb0a6" opacity="0.6"/>'
          '<circle cx="34" cy="350" r="5" fill="#ffd6cf" opacity="0.7"/>'
          # menisco
          '<path d="M -90 302 C -30 292 30 292 90 302 L 90 318 L -90 318 Z" fill="#ff8478" opacity="0.8"/>'
          '</g>')
    # Vidrio (borde y reflejo)
    g += f'<path d="{cuerpo}" fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>'
    g += ('<path d="M -50 268 C -66 296 -70 330 -66 360" fill="none" '
          'stroke="#ffffff" stroke-width="9" opacity="0.5" stroke-linecap="round"/>')
    # Cuello
    g += ('<path d="M -22 236 L -18 176 L 18 176 L 22 236 Z" '
          'fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>')
    # Corcho
    g += '<rect x="-24" y="150" width="48" height="34" rx="6" fill="url(#madera)" stroke="#2e1a09" stroke-width="2"/>'
    g += '<rect x="-24" y="150" width="48" height="10" rx="5" fill="#c69a5f" opacity="0.5"/>'
    # Etiqueta con cruz de curación
    g += '<circle cx="0" cy="360" r="26" fill="#f3ecdd" opacity="0.92" stroke="#c99a3f" stroke-width="3"/>'
    g += '<rect x="-5" y="345" width="10" height="30" rx="3" fill="#c0303a"/>'
    g += '<rect x="-15" y="355" width="30" height="10" rx="3" fill="#c0303a"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "330", "220", "185"))


def espada_de_gemas() -> str:
    g = '<g transform="translate(350 0)">'
    g += _hoja(0, 34, 74, 315, 18)
    # Tres gemas incrustadas en la hoja
    g += _engaste(0, 110, 15)
    g += _gema(0, 110, 11, 11, "url(#gema-azul)")
    g += _engaste(0, 170, 15)
    g += _gema(0, 170, 11, 11, "url(#gema-roja)")
    g += _engaste(0, 230, 15)
    g += _gema(0, 230, 11, 11, "url(#gema-verde)")
    # Guarda ornamentada
    g += _guarda_recta(0, 312, 96, 24)
    # Gema central en la guarda
    g += _gema(0, 324, 9, 9, "url(#gema-azul)")
    g += _empunadura(0, 336, 28, 84, 6)
    g += _pomo(0, 430, 20)
    # Gema en el pomo
    g += _gema(0, 430, 8, 8, "url(#gema-roja)")
    g += "</g>"
    return _lienzo(g)


def bola_de_fuego() -> str:
    """Hechizo: esfera de fuego con llamas y chispas."""
    g = '<g transform="translate(350 250)">'
    # resplandor
    g += '<circle cx="0" cy="0" r="150" fill="#f06a1e" opacity="0.18"/>'
    # lenguas de fuego alrededor del núcleo
    llamas = [
        "M 0 -150 C 26 -96 24 -70 0 -60 C -24 -70 -26 -96 0 -150 Z",
        "M 132 -70 C 96 -40 74 -30 60 -46 C 58 -70 84 -92 132 -70 Z",
        "M 132 70 C 96 40 74 30 60 46 C 58 70 84 92 132 70 Z",
        "M 0 150 C 26 96 24 70 0 60 C -24 70 -26 96 0 150 Z",
        "M -132 70 C -96 40 -74 30 -60 46 C -58 70 -84 92 -132 70 Z",
        "M -132 -70 C -96 -40 -74 -30 -60 -46 C -58 -70 -84 -92 -132 -70 Z",
    ]
    for d in llamas:
        g += f'<path d="{d}" fill="url(#fuego)" opacity="0.85"/>'
    # núcleo incandescente
    g += '<circle cx="0" cy="0" r="72" fill="url(#fuego)" stroke="#a01f10" stroke-width="3"/>'
    g += '<circle cx="-20" cy="-22" r="22" fill="#fff3c0" opacity="0.85"/>'
    # chispas
    g += ('<g fill="#ffd23a">'
          '<circle cx="96" cy="-108" r="7"/><circle cx="-110" cy="86" r="6"/>'
          '<circle cx="118" cy="96" r="5"/><circle cx="-92" cy="-96" r="5"/></g>')
    g += "</g>"
    return _lienzo(g)


def curar_heridas() -> str:
    """Hechizo: cruz de vida radiante sobre un halo verde."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#2a9a5a" opacity="0.18"/>'
    # rayos de luz
    g += '<g stroke="#bff2cf" stroke-width="7" stroke-linecap="round" opacity="0.7">'
    import math
    for i in range(12):
        ang = math.radians(i * 30)
        x1, y1 = 96 * math.cos(ang), 96 * math.sin(ang)
        x2, y2 = 132 * math.cos(ang), 132 * math.sin(ang)
        g += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"/>'
    g += '</g>'
    # disco central
    g += '<circle cx="0" cy="0" r="86" fill="url(#curacion)" stroke="#1f7a44" stroke-width="3"/>'
    g += '<circle cx="-24" cy="-26" r="20" fill="#eafff0" opacity="0.7"/>'
    # cruz de curación
    g += '<rect x="-16" y="-52" width="32" height="104" rx="8" fill="#ffffff" stroke="#1f7a44" stroke-width="2"/>'
    g += '<rect x="-52" y="-16" width="104" height="32" rx="8" fill="#ffffff" stroke="#1f7a44" stroke-width="2"/>'
    g += "</g>"
    return _lienzo(g)


def dardo_de_caos() -> str:
    """Hechizo: proyectil oscuro de caos con estela de energía."""
    g = '<g transform="translate(350 250)">'
    g += '<ellipse cx="0" cy="0" rx="180" ry="90" fill="#8a3fd0" opacity="0.15"/>'
    # estela (de izquierda a derecha)
    g += ('<path d="M -180 0 C -120 -34 -60 -30 -10 -14 L -10 14 C -60 30 -120 34 -180 0 Z" '
          'fill="url(#caos)" opacity="0.55"/>')
    g += ('<g stroke="#c98fff" stroke-width="4" stroke-linecap="round" opacity="0.7" fill="none">'
          '<path d="M -170 -24 C -120 -30 -80 -26 -40 -16"/>'
          '<path d="M -170 24 C -120 30 -80 26 -40 16"/></g>')
    # punta del dardo (proyectil)
    g += ('<path d="M 130 0 L 40 -46 C 10 -30 10 30 40 46 Z" '
          'fill="url(#caos)" stroke="#3a1060" stroke-width="3" stroke-linejoin="round"/>')
    # núcleo brillante
    g += '<circle cx="46" cy="0" r="26" fill="url(#caos)"/>'
    g += '<circle cx="38" cy="-8" r="9" fill="#e0b0ff" opacity="0.85"/>'
    # runa/chispa de caos en la punta
    g += ('<g stroke="#e0b0ff" stroke-width="3" stroke-linecap="round" opacity="0.85">'
          '<path d="M 120 -26 L 132 -14 M 132 -26 L 120 -14"/>'
          '<path d="M 96 40 L 108 52 M 108 40 L 96 52"/></g>')
    g += "</g>"
    return _lienzo(g)


OBJETOS = {
    "Espada corta": espada_corta,
    "Daga": daga,
    "Mandoble": mandoble,
    "Hacha de batalla": hacha_de_batalla,
    "Ballesta": ballesta,
    "Báculo del mago": baculo_del_mago,
    "Armadura de placas": armadura_de_placas,
    "Yelmo": yelmo,
    "Escudo": escudo,
    "Poción de curación": pocion_de_curacion,
    "Espada de gemas": espada_de_gemas,
    "Bola de fuego": bola_de_fuego,
    "Curar heridas": curar_heridas,
    "Dardo de caos": dardo_de_caos,
}


def _rasterizar(svg: str, ruta_png: Path) -> None:
    _rasterizar_png(svg, ruta_png, ANCHO, ALTO)


def generar(solo: str | None, svg_solo: bool) -> None:
    ARTE_SVG_DIR.mkdir(parents=True, exist_ok=True)
    ARTE_DIR.mkdir(parents=True, exist_ok=True)

    objetos = OBJETOS
    if solo:
        if solo not in OBJETOS:
            raise SystemExit(f"'{solo}' no existe. Válidos: {', '.join(OBJETOS)}")
        objetos = {solo: OBJETOS[solo]}

    for nombre, fn in objetos.items():
        slug = _slug(nombre)
        svg = fn()
        ruta_svg = ARTE_SVG_DIR / f"{slug}.svg"
        ruta_svg.write_text(svg, encoding="utf-8")
        if svg_solo:
            print(f"SVG  {ruta_svg.relative_to(ARTE_SVG_DIR.parent.parent.parent)}")
            continue
        ruta_png = ARTE_DIR / f"{slug}.png"
        _rasterizar(svg, ruta_png)
        print(f"OK   {nombre}  ->  {ruta_png.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="Genera el arte de las cartas de HeroQuest")
    p.add_argument("--solo", default=None, help="Genera solo un objeto por su nombre exacto")
    p.add_argument("--svg-solo", action="store_true", help="Genera solo los SVG, sin rasterizar a PNG")
    args = p.parse_args()
    generar(args.solo, args.svg_solo)


if __name__ == "__main__":
    main()

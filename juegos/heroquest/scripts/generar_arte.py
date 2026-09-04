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
    python juegos/heroquest/scripts/generar_arte.py            # genera todo
    python juegos/heroquest/scripts/generar_arte.py --solo Daga
    python juegos/heroquest/scripts/generar_arte.py --svg-solo # solo SVG, sin PNG
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
    <radialGradient id="pocion-azul" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#a8dcff"/>
      <stop offset="45%" stop-color="#3b7fe2"/>
      <stop offset="100%" stop-color="#16308f"/>
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
    <radialGradient id="aire" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#ffffff"/>
        <stop offset="50%" stop-color="#d8e8f0"/>
        <stop offset="100%" stop-color="#a0b8c8"/>
     </radialGradient>
     <radialGradient id="agua" cx="50%" cy="45%" r="60%">
        <stop offset="0%" stop-color="#e0f8ff"/>
        <stop offset="45%" stop-color="#60c8f0"/>
        <stop offset="100%" stop-color="#1060a0"/>
     </radialGradient>
     <radialGradient id="tierra" cx="50%" cy="45%" r="60%">
        <stop offset="0%" stop-color="#f0e8d0"/>
        <stop offset="45%" stop-color="#80a040"/>
        <stop offset="100%" stop-color="#405020"/>
     </radialGradient>
     <linearGradient id="oxido" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#8b4513"/>
        <stop offset="50%" stop-color="#b22222"/>
        <stop offset="100%" stop-color="#d2691e"/>
     </linearGradient>

    <!-- NUEVOS GRADIENTES PARA ARTEFACTOS -->
    <linearGradient id="hueso" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FDF5E6"/>
      <stop offset="50%" stop-color="#E8DDCB"/>
      <stop offset="100%" stop-color="#D7C7B7"/>
    </linearGradient>
    <radialGradient id="filo-espectral" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#E0F8FF" stop-opacity="0.8"/>
      <stop offset="70%" stop-color="#A0D8EF" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#5B8BE0" stop-opacity="0.2"/>
    </radialGradient>
    <radialGradient id="tela-magica" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#4A4AFF"/>
      <stop offset="60%" stop-color="#0A0A2A"/>
      <stop offset="100%" stop-color="#05051A"/>
    </radialGradient>
    <radialGradient id="elixir-perlado" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#FFF0F5"/>
      <stop offset="50%" stop-color="#FFDDF0"/>
      <stop offset="100%" stop-color="#E0B0C0"/>
    </radialGradient>

    <!-- NUEVOS GRADIENTES PARA TESOROS -->
    <radialGradient id="pocion-heroica" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#fff3c0"/>
      <stop offset="45%" stop-color="#ffd23a"/>
      <stop offset="100%" stop-color="#a06f10"/>
    </radialGradient>
    <radialGradient id="pocion-defensa" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#e4e8f0"/>
      <stop offset="45%" stop-color="#98a4b8"/>
      <stop offset="100%" stop-color="#545c6d"/>
    </radialGradient>
    <radialGradient id="pocion-fuerza" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#e0b0ff"/>
      <stop offset="45%" stop-color="#8a3fd0"/>
      <stop offset="100%" stop-color="#3a1060"/>
    </radialGradient>
    <radialGradient id="pocion-curativa-tesoro" cx="42%" cy="30%" r="80%">
      <stop offset="0%" stop-color="#a8dcff"/>
      <stop offset="45%" stop-color="#3b7fe2"/>
      <stop offset="100%" stop-color="#16308f"/>
    </radialGradient>

    <filter id="sombra" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
    <filter id="textura-roca">
        <feTurbulence type="fractalNoise" baseFrequency="0.1" numOctaves="2" result="turbulence"/>
        <feDiffuseLighting in="turbulence" lighting-color="#d2b48c" surfaceScale="5" result="lighting">
            <feDistantLight azimuth="225" elevation="60"/>
        </feDiffuseLighting>
        <feComposite in="lighting" in2="SourceGraphic" operator="in" result="composite"/>
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


def _empunadura(cx, y, w, h, envolturas, fill="url(#cuero)"):
    """Empuñadura centrada en cx, desde y, con envoltura diagonal."""
    x0, x1 = cx - w / 2, cx + w / 2
    return (
        f'<rect x="{x0}" y="{y}" width="{w}" height="{h}" rx="{w*0.27:.1f}" '
        f'fill="{fill}" stroke="#2e1a09" stroke-width="2"/>'
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


def _hoja(cx, punta_y, hombro_y, base_y, semiancho, fuller=True, fill="url(#acero)"):
    """Hoja de espada: punta triangular arriba, cuerpo recto, con bisel y lustre."""
    l, r = cx - semiancho, cx + semiancho
    partes = [
        f'<path d="M {cx} {punta_y} L {r} {hombro_y} L {r} {base_y} '
        f'L {l} {base_y} L {l} {hombro_y} Z" fill="{fill}" '
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


def pocion_de_mente() -> str:
    g = '<g transform="translate(350 0)">'
    # Cuerpo bulboso del frasco (mismo perfil que la poción de curación)
    cuerpo = ('M -34 230 '
              'C -70 250 -84 300 -84 340 '
              'C -84 400 -40 440 0 440 '
              'C 40 440 84 400 84 340 '
              'C 84 300 70 250 34 230 Z')
    # Líquido azul (recortado dentro del cuerpo)
    g += '<clipPath id="clip-pocion-mente"><path d="' + cuerpo + '"/></clipPath>'
    g += f'<path d="{cuerpo}" fill="#0d1420" opacity="0.5"/>'
    g += ('<g clip-path="url(#clip-pocion-mente)">'
          '<rect x="-90" y="300" width="180" height="160" fill="url(#pocion-azul)"/>'
          # burbujas
          '<circle cx="-24" cy="360" r="7" fill="#bfe4ff" opacity="0.7"/>'
          '<circle cx="14" cy="392" r="10" fill="#bfe4ff" opacity="0.6"/>'
          '<circle cx="34" cy="350" r="5" fill="#e2f2ff" opacity="0.7"/>'
          # menisco
          '<path d="M -90 302 C -30 292 30 292 90 302 L 90 318 L -90 318 Z" fill="#78b0ff" opacity="0.8"/>'
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
    # Etiqueta con espiral mental (símbolo de la mente, en azul)
    g += '<circle cx="0" cy="360" r="26" fill="#f3ecdd" opacity="0.92" stroke="#c99a3f" stroke-width="3"/>'
    g += ('<path d="M 0 348 C 9 348 12 358 6 362 C 1 365 -4 361 -3 356 '
          'C -2 352 2 353 2 356" fill="none" stroke="#2a56c0" stroke-width="3.4" '
          'stroke-linecap="round"/>')
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


def tempestad() -> str:
    """Hechizo de Aire: tormenta/rayos en remolino."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#a0b8c8" opacity="0.18"/>'
    # Remolino de nubes
    g += ('<path d="M 0 -140 Q 70 -140 70 -70 T 0 0 T -70 70 T 0 140" '
          'fill="none" stroke="url(#aire)" stroke-width="40" stroke-linecap="round" opacity="0.6"/>')
    g += ('<path d="M 0 -120 Q -60 -120 -60 -60 T 0 0 T 60 60 T 0 120" '
          'fill="none" stroke="#ffffff" stroke-width="25" stroke-linecap="round" opacity="0.4"/>')
    # Rayo central
    g += ('<path d="M 0 -80 L -20 -40 L 10 -40 L -10 0 L 20 0 L -20 60 L 0 20 L 0 80" '
          'fill="none" stroke="#ffd700" stroke-width="12" stroke-linejoin="round" stroke-linecap="round"/>')
    g += ('<path d="M 0 -80 L -20 -40 L 10 -40 L -10 0 L 20 0 L -20 60 L 0 20 L 0 80" '
          'fill="none" stroke="#ffffff" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>')
    g += "</g>"
    return _lienzo(g)


def rafaga() -> str:
    """Hechizo de Aire: ráfaga de viento, líneas curvas veloces."""
    g = '<g transform="translate(350 250)">'
    g += '<ellipse cx="0" cy="0" rx="200" ry="120" fill="#a0b8c8" opacity="0.15"/>'
    # Líneas de viento
    g += ('<g fill="none" stroke-width="18" stroke-linecap="round" opacity="0.7">'
          '<path d="M -180 -50 C -60 -80 60 40 180 20" stroke="url(#aire)"/>'
          '<path d="M -160 0 C -40 -20 80 80 200 60" stroke="#ffffff" stroke-width="12"/>'
          '<path d="M -180 50 C -60 80 60 -40 180 -20" stroke="url(#aire)"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def genio() -> str:
    """Hechizo de Aire: genio de humo azul saliendo de una lámpara dorada."""
    g = '<g transform="translate(350 250)">'

    # --- Lámpara de Aladino (dorada) en la parte inferior ---
    # Cuerpo bulboso de la lámpara.
    g += ('<path d="M -110 150 C -130 120 -120 95 -80 90 '
          'C -30 84 30 84 80 90 C 120 95 130 120 110 150 Z" '
          'fill="url(#oro)" stroke="#7d5a1e" stroke-width="3.5"/>')
    # Base (pie) de la lámpara.
    g += '<ellipse cx="0" cy="152" rx="95" ry="16" fill="url(#oro-pomo)" stroke="#7d5a1e" stroke-width="2.5"/>'
    # Pitorro/pico a la derecha.
    g += ('<path d="M 100 108 C 165 96 185 120 150 130 C 175 128 160 112 108 122 Z" '
          'fill="url(#oro)" stroke="#7d5a1e" stroke-width="2.5"/>')
    # Tapa con perilla.
    g += '<ellipse cx="0" cy="90" rx="46" ry="12" fill="url(#oro-pomo)" stroke="#7d5a1e" stroke-width="2"/>'
    g += '<circle cx="0" cy="74" r="10" fill="url(#oro-pomo)" stroke="#7d5a1e" stroke-width="2"/>'
    # Lustre en la lámpara.
    g += '<ellipse cx="-40" cy="110" rx="26" ry="12" fill="#fff3c0" opacity="0.45"/>'

    # --- Voluta de humo azul que asciende y se ensancha (capas suaves) ---
    g += ('<path d="M -8 88 C -60 40 40 20 6 -30 C -40 -70 60 -95 20 -150 '
          'C 0 -178 -30 -186 -52 -172 C -14 -168 6 -150 -6 -120 '
          'C -40 -70 44 -40 8 4 C -24 40 34 56 -8 88 Z" '
          'fill="#7fbfff" opacity="0.30"/>')
    g += ('<path d="M 6 88 C -34 44 44 24 14 -22 C -20 -62 56 -88 24 -138 '
          'C 6 -166 -20 -172 -40 -160 C -8 -156 8 -140 -2 -112 '
          'C -30 -66 46 -34 14 6 C -12 40 36 58 6 88 Z" '
          'fill="#a8dcff" opacity="0.45"/>')

    # --- Silueta del genio en lo alto del humo (cabeza + torso + brazos cruzados) ---
    # Cabeza.
    g += '<circle cx="0" cy="-150" r="30" fill="#cfeaff" opacity="0.95"/>'
    # Turbante.
    g += ('<path d="M -30 -158 C -20 -190 20 -190 30 -158 C 10 -172 -10 -172 -30 -158 Z" '
          'fill="#7fbfff" opacity="0.95"/>')
    g += '<circle cx="0" cy="-178" r="7" fill="#ffe9ad"/>'
    # Torso que se funde con el humo.
    g += ('<path d="M -26 -126 C -44 -104 -48 -70 -34 -52 '
          'C -12 -66 12 -66 34 -52 C 48 -70 44 -104 26 -126 '
          'C 12 -108 -12 -108 -26 -126 Z" fill="#cfeaff" opacity="0.92"/>')
    # Brazos cruzados sobre el pecho.
    g += ('<path d="M -40 -78 C -8 -96 8 -96 40 -78 C 8 -66 -8 -66 -40 -78 Z" '
          'fill="#a8dcff" opacity="0.95"/>')
    g += "</g>"
    return _lienzo(g, halo=("350", "150", "250", "230"))


def fuego_de_la_ira() -> str:
    """Hechizo de Fuego: llamarada furiosa."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="160" fill="#f06a1e" opacity="0.2"/>'
    # Llamas agresivas
    g += ('<g fill="url(#fuego)" opacity="0.9">'
          '<path d="M 0 100 C -80 40 -60 -80 0 -150 C 60 -80 80 40 0 100 Z"/>'
          '<path transform="rotate(45)" d="M 0 90 C -70 30 -50 -70 0 -130 C 50 -70 70 30 0 90 Z"/>'
          '<path transform="rotate(-45)" d="M 0 90 C -70 30 -50 -70 0 -130 C 50 -70 70 30 0 90 Z"/>'
          '</g>')
    # Núcleo
    g += '<circle cx="0" cy="-20" r="60" fill="url(#fuego)" stroke="#a01f10" stroke-width="3"/>'
    g += '<circle cx="0" cy="-30" r="20" fill="#fff3c0"/>'
    g += "</g>"
    return _lienzo(g)


def valentia() -> str:
    """Hechizo de Fuego: corazón en llamas."""
    g = '<g transform="translate(350 250)">'
    # Corazón
    corazon_path = ('M 0 20 C -40 -30 -80 10 -80 50 C -80 100 -40 120 0 160 C 40 120 80 100 80 50 C 80 10 -40 -30 0 20 Z')
    # Llamas emanando del corazón
    g += ('<g filter="url(#sombra)">'
          f'<path d="{corazon_path}" fill="url(#fuego)" stroke="#a01f10" stroke-width="4"/>'
          '<path d="M 0 -120 C -30 -80 -20 -50 0 -30 C 20 -50 30 -80 0 -120 Z" fill="url(#fuego)" opacity="0.8"/>'
          '<path d="M -80 -20 C -100 -40 -110 0 -90 20 C -70 40 -60 0 -80 -20 Z" fill="url(#fuego)" opacity="0.7" transform="rotate(20)"/>'
          '<path d="M 80 -20 C 100 -40 110 0 90 20 C 70 40 60 0 80 -20 Z" fill="url(#fuego)" opacity="0.7" transform="rotate(-20)"/>'
          '</g>')
    # Brillo interior
    g += '<circle cx="0" cy="60" r="30" fill="#fff3c0" opacity="0.7"/>'
    g += "</g>"
    return _lienzo(g)


def agua_milagrosa() -> str:
    """Hechizo de Agua: gota brillante de agua."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#1060a0" opacity="0.18"/>'
    # Gota de agua
    g += ('<path d="M 0 -140 C -100 -140 -120 40 0 140 C 120 40 100 -140 0 -140 Z" '
          'fill="url(#agua)" stroke="#1060a0" stroke-width="4"/>')
    # Reflejos
    g += ('<ellipse cx="-40" cy="-50" rx="25" ry="40" fill="#e0f8ff" opacity="0.8"/>'
          '<circle cx="30" cy="20" r="15" fill="#e0f8ff" opacity="0.6"/>')
    # Ondas en la base
    g += ('<g fill="none" stroke="#60c8f0" stroke-width="5" opacity="0.7">'
          '<path d="M -80 120 C -40 100 40 100 80 120"/>'
          '<path d="M -100 140 C -50 120 50 120 100 140"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def niebla() -> str:
    """Hechizo de Agua: bruma/niebla envolvente en capas suaves superpuestas.

    Sin filtros de desenfoque (resvg no siempre los aplica); la sensación de
    bruma se logra con muchas volutas/óvalos semitransparentes solapados.
    """
    import math
    g = '<g transform="translate(350 250)">'

    def voluta(cx, cy, w, h, color, op):
        # Nube alargada compuesta por lóbulos redondeados.
        s = f'<g opacity="{op}" fill="{color}">'
        s += f'<ellipse cx="{cx}" cy="{cy}" rx="{w}" ry="{h}"/>'
        s += f'<ellipse cx="{cx-w*0.55:.0f}" cy="{cy+h*0.3:.0f}" rx="{w*0.55:.0f}" ry="{h*0.7:.0f}"/>'
        s += f'<ellipse cx="{cx+w*0.55:.0f}" cy="{cy+h*0.3:.0f}" rx="{w*0.55:.0f}" ry="{h*0.7:.0f}"/>'
        s += f'<ellipse cx="{cx-w*0.3:.0f}" cy="{cy-h*0.4:.0f}" rx="{w*0.4:.0f}" ry="{h*0.6:.0f}"/>'
        s += f'<ellipse cx="{cx+w*0.3:.0f}" cy="{cy-h*0.4:.0f}" rx="{w*0.4:.0f}" ry="{h*0.6:.0f}"/>'
        s += '</g>'
        return s

    # Resplandor de fondo tenue (halo acuático).
    g += '<ellipse cx="0" cy="0" rx="290" ry="180" fill="#3b7fe2" opacity="0.10"/>'
    # Capas de bruma en distintas alturas, colores fríos y baja opacidad.
    bandas = [
        (-30, -110, 150, 34, "#dff4ff", 0.30),
        (60,  -70, 175, 40, "#bfe4ff", 0.34),
        (-70,  -30, 165, 42, "#e8f8ff", 0.32),
        (40,   20, 190, 46, "#a8d8f0", 0.36),
        (-50,  70, 170, 42, "#d0f0ff", 0.34),
        (55,  120, 160, 38, "#c8e8f8", 0.40),
        (-20, 155, 150, 32, "#eaf9ff", 0.30),
    ]
    for cx, cy, w, h, color, op in bandas:
        g += voluta(cx, cy, w, h, color, op)
    # Unos velos amplios que unifican todo.
    g += '<ellipse cx="0" cy="10" rx="270" ry="150" fill="#ffffff" opacity="0.10"/>'
    g += '<ellipse cx="0" cy="90" rx="250" ry="110" fill="#cfeeff" opacity="0.12"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "0.1", "0.1"))


def dormir() -> str:
    """Hechizo de Terror: símbolo de sueño, Zzz."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#3a1060" opacity="0.2"/>'
    # Ojo cerrado
    g += ('<path d="M -100 0 C -50 -80 50 -80 100 0 C 50 80 -50 80 -100 0 Z" '
          'fill="#211d33" stroke="#e0b0ff" stroke-width="4"/>')
    g += '<path d="M -90 0 C -40 -70 40 -70 90 0" fill="none" stroke="#e0b0ff" stroke-width="6"/>'
    # Zzz
    g += ('<g font-family="serif" font-size="80" font-weight="bold" fill="#e0b0ff" '
          'stroke="#3a1060" stroke-width="2" opacity="0.8">'
          '<text x="80" y="-50">Z</text>'
          '<text x="100" y="10" font-size="60">z</text>'
          '<text x="120" y="60" font-size="40">z</text>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def piel_de_roca() -> str:
    """Hechizo de Tierra: piel/escudo de roca."""
    g = '<g transform="translate(350 250)">'
    forma_escudo = ('M 0 -140 L 120 -100 L 100 80 C 80 140 0 160 0 160 '
                    'C 0 160 -80 140 -100 80 L -120 -100 Z')
    g += (f'<path d="{forma_escudo}" fill="url(#tierra)" stroke="#405020" '
          'stroke-width="5" filter="url(#textura-roca)"/>')
    # Grietas
    g += ('<g fill="none" stroke="#405020" stroke-width="3" opacity="0.8">'
          '<path d="M 0 -140 L -10 -80 L 20 -40 L 0 20"/>'
          '<path d="M 20 -40 L 60 -30"/>'
          '<path d="M -10 -80 L -50 -70"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def cura_corporal() -> str:
    """Hechizo de Tierra: cruz verde de curación con hojas."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#405020" opacity="0.18"/>'
    # Cruz
    g += ('<rect x="-20" y="-70" width="40" height="140" rx="10" fill="url(#curacion)"/>'
          '<rect x="-70" y="-20" width="140" height="40" rx="10" fill="url(#curacion)"/>')
    # Hojas
    g += ('<g fill="url(#tierra)" stroke="#405020" stroke-width="2">'
          '<path transform="translate(60 60) rotate(45)" d="M 0 0 C 20 -40 60 -30 60 0 C 60 30 20 40 0 0 Z"/>'
          '<path transform="translate(-60 60) rotate(135)" d="M 0 0 C 20 -40 60 -30 60 0 C 60 30 20 40 0 0 Z"/>'
          '<path transform="translate(60 -60) rotate(-45)" d="M 0 0 C 20 -40 60 -30 60 0 C 60 30 20 40 0 0 Z"/>'
          '<path transform="translate(-60 -60) rotate(-135)" d="M 0 0 C 20 -40 60 -30 60 0 C 60 30 20 40 0 0 Z"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def a_traves_de_la_roca() -> str:
    """Hechizo de Tierra: figura atravesando un muro de roca."""
    g = '<g transform="translate(350 250)">'
    # Muro de roca
    g += ('<rect x="-150" y="-100" width="300" height="200" fill="url(#tierra)" '
          'stroke="#405020" stroke-width="4" filter="url(#textura-roca)"/>')
    # Agujero
    g += ('<path d="M -20 -80 C -80 -60 -90 60 -10 80 L 10 80 C 90 60 80 -60 20 -80 Z" '
          'fill="#14111f"/>')
    # Figura atravesando
    g += ('<g fill="#e0f8ff" opacity="0.8">'
          '<circle cx="0" cy="-20" r="30"/>'
          '<path d="M -50 80 L -40 10 L 40 10 L 50 80 Z"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def invocar_muertos_vivientes() -> str:
    """Hechizo de Terror: calaveras surgiendo."""
    g = '<g transform="translate(350 250)">'
    # Niebla en el suelo
    g += '<ellipse cx="0" cy="120" rx="200" ry="60" fill="url(#caos)" opacity="0.5"/>'
    # Calaveras
    calavera = ('<path d="M -30 0 C -40 -40 40 -40 30 0 L 30 30 C 30 50 -30 50 -30 30 Z" '
                'fill="#e0e0e0" stroke="#404040" stroke-width="2"/>'
                '<g fill="#111"><circle cx="-15" cy="-10" r="8"/><circle cx="15" cy="-10" r="8"/>'
                '<path d="M -10 15 L 10 15 L 5 25 L -5 25 Z"/></g>')
    g += f'<g transform="translate(0 40) scale(1.2)">{calavera}</g>'
    g += f'<g transform="translate(-80 70) scale(0.9) rotate(-15)">{calavera}</g>'
    g += f'<g transform="translate(80 70) scale(0.9) rotate(15)">{calavera}</g>'
    g += "</g>"
    return _lienzo(g)


def invocar_orcos() -> str:
    """Hechizo de Terror: silueta de orco / colmillos."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#3a1060" opacity="0.2"/>'
    # Silueta de cabeza de orco
    g += ('<path d="M 0 -120 L -80 -80 L -70 40 C -60 100 60 100 70 40 L 80 -80 Z" '
          'fill="#206020" stroke="#103010" stroke-width="4"/>')
    # Ojos rojos
    g += '<g fill="#ff4040"><circle cx="-30" cy="-20" r="10"/><circle cx="30" cy="-20" r="10"/></g>'
    # Colmillos
    g += ('<g fill="#f0f0e0">'
          '<path d="M -40 50 C -40 70 -20 70 -20 50 Z"/>'
          '<path d="M 20 50 C 20 70 40 70 40 50 Z"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def oxidacion() -> str:
    """Hechizo de Tierra: espada oxidada/corroída."""
    g = '<g transform="translate(350 250)">'
    # Espada rota y oxidada
    g += ('<g transform="rotate(25)">'
          + _hoja(0, -180, -142, 100, 15)
          + _guarda_recta(0, 98, 70, 18)
          + _empunadura(0, 116, 22, 70, 4)
          + _pomo(0, 192, 15)
          + '</g>')
    # Capa de óxido
    g += ('<g transform="rotate(25)" fill="url(#oxido)" opacity="0.7" filter="url(#textura-roca)">'
          '<path d="M 0 -180 L 15 -142 L 15 50 L -15 50 L -15 -142 Z"/>'
          '<path d="M 10 -180 L 15 -170 L 15 -100 L 5 -90 Z"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def rayo_mortifero() -> str:
    """Hechizo de Terror: rayo oscuro mortal."""
    g = '<g transform="translate(350 250)">'
    # Rayo
    g += ('<path d="M 0 -160 L -20 -80 L 20 -60 L -30 20 L 30 40 L -40 120 L 40 160" '
          'fill="none" stroke="url(#caos)" stroke-width="25" stroke-linecap="round"/>')
    # Aura
    g += ('<path d="M 0 -160 L -20 -80 L 20 -60 L -30 20 L 30 40 L -40 120 L 40 160" '
          'fill="none" stroke="#e0b0ff" stroke-width="8" stroke-linecap="round" opacity="0.7"/>')
    # Chispas
    g += ('<g fill="#e0b0ff">'
          '<path d="M -50 -120 L -70 -100 L -50 -80 Z"/>'
          '<path d="M 50 80 L 70 100 L 50 120 Z"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def bola_en_llamas() -> str:
    """Hechizo de Fuego: variante de bola de fuego."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#f06a1e" opacity="0.18"/>'
    # Núcleo rocoso
    g += '<circle cx="0" cy="0" r="80" fill="url(#tierra)" filter="url(#textura-roca)"/>'
    # Llamas envolventes
    g += ('<g fill="url(#fuego)" opacity="0.8">'
          '<path d="M 0 -140 C 80 -120 80 120 0 140" transform="rotate(15)"/>'
          '<path d="M 0 -140 C -80 -120 -80 120 0 140" transform="rotate(-15)"/>'
          '<path d="M -140 0 C -120 -80 120 -80 140 0" transform="rotate(15)"/>'
          '<path d="M -140 0 C -120 80 120 80 140 0" transform="rotate(-15)"/>'
          '</g>')
    g += '<circle cx="0" cy="0" r="40" fill="#fff3c0" opacity="0.5"/>'
    g += "</g>"
    return _lienzo(g)


def nube_de_terror() -> str:
    """Hechizo de Terror: nube oscura con rostros/ojos."""
    g = '<g transform="translate(350 250)">'
    # Nube
    g += ('<g opacity="0.9">'
          '<ellipse cx="0" cy="0" rx="180" ry="100" fill="url(#caos)"/>'
          '<ellipse cx="-80" cy="20" rx="100" ry="60" fill="#3a1060"/>'
          '<ellipse cx="80" cy="20" rx="100" ry="60" fill="#3a1060"/>'
          '</g>')
    # Ojos rojos
    g += ('<g fill="#ff2020">'
          '<circle cx="-90" cy="-10" r="12"/><circle cx="-60" cy="-10" r="12"/>'
          '<circle cx="70" cy="0" r="10"/><circle cx="100" cy="0" r="10"/>'
          '<circle cx="0" cy="30" r="15"/><circle cx="-30" cy="30" r="15"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def dominacion() -> str:
    """Hechizo de Terror: ojo hipnótico."""
    g = '<g transform="translate(350 250)">'
    # Ojo
    g += ('<ellipse cx="0" cy="0" rx="140" ry="90" fill="#fff" stroke="#3a1060" stroke-width="4"/>'
          '<circle cx="0" cy="0" r="50" fill="url(#caos)"/>'
          '<circle cx="0" cy="0" r="20" fill="#111"/>')
    # Espirales hipnóticas
    g += ('<g fill="none" stroke="url(#caos)" stroke-width="8" stroke-linecap="round">'
          '<path d="M 60 0 A 60 60 0 0 1 0 60 A 60 60 0 0 1 -60 0 A 60 60 0 0 1 0 -60"/>'
          '<path d="M 0 -60 A 60 60 0 0 1 52 -30"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def huida_fugaz() -> str:
    """Hechizo de Aire: figura desvaneciéndose."""
    g = '<g transform="translate(350 250)">'
    # Figura base
    figura = ('<circle cx="0" cy="-80" r="30"/>'
              '<path d="M -40 -60 L -20 60 L 20 60 L 40 -60 Z"/>')
    # Instancias con opacidad decreciente
    g += f'<g fill="#e0f8ff" transform="translate(80 0)" opacity="0.2">{figura}</g>'
    g += f'<g fill="#e0f8ff" transform="translate(0 0)" opacity="0.5">{figura}</g>'
    g += f'<g fill="#e0f8ff" transform="translate(-80 0)" opacity="1">{figura}</g>'
    # Líneas de movimiento
    g += ('<g stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.6">'
          '<path d="M -160 0 L -100 0"/><path d="M -40 0 L 20 0"/><path d="M 100 0 L 160 0"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g)


def miedo() -> str:
    """Hechizo de Terror: rostro aterrado / grito."""
    g = '<g transform="translate(350 250)">'
    g += '<circle cx="0" cy="0" r="150" fill="#3a1060" opacity="0.2"/>'
    # Cara
    g += '<circle cx="0" cy="0" r="100" fill="#e0b0ff" stroke="#3a1060" stroke-width="3"/>'
    # Ojos y boca de pánico
    g += ('<g fill="#111">'
          '<circle cx="-40" cy="-20" r="20"/>'
          '<circle cx="40" cy="-20" r="20"/>'
          '<ellipse cx="0" cy="50" rx="40" ry="60"/>'
          '</g>')
    # Pupilas pequeñas
    g += '<g fill="#fff"><circle cx="-40" cy="-20" r="8"/><circle cx="40" cy="-20" r="8"/></g>'
    g += "</g>"
    return _lienzo(g)


def tormenta_de_fuego() -> str:
    """Hechizo de Fuego: lluvia de meteoros."""
    g = '<g transform="translate(350 250)">'
    g += '<rect x="-250" y="-200" width="500" height="400" fill="#a01f10" opacity="0.2"/>'
    # Meteoros cayendo
    meteoro = ('<path d="M 0 0 L -10 -40 L 10 -40 Z" fill="url(#fuego)"/>'
               '<path d="M 0 0 C -10 20 10 20 0 0" fill="url(#fuego)" opacity="0.8"/>')
    g += f'<g transform="translate(-120 -80) rotate(15) scale(1.2)">{meteoro}</g>'
    g += f'<g transform="translate(50 -120) rotate(5) scale(1.0)">{meteoro}</g>'
    g += f'<g transform="translate(150 -50) rotate(-10) scale(1.1)">{meteoro}</g>'
    g += f'<g transform="translate(-80 50) rotate(20) scale(0.9)">{meteoro}</g>'
    g += f'<g transform="translate(100 80) rotate(-5) scale(1.3)">{meteoro}</g>'
    g += "</g>"
    return _lienzo(g)

# ---------------------------------------------------------------------------
# ARTEFACTOS MÁGICOS
# ---------------------------------------------------------------------------

def armadura_de_borin() -> str:
    """Armadura mágica acorazada brillante."""
    g = '<g transform="translate(350 250)">'
    # Usamos una forma de peto más elaborada que la armadura de placas
    coraza = ('M -120 -150 '
              'C -140 -120 -150 0 -130 100 '
              'L -110 180 C -80 220 80 220 110 180 '
              'L 130 100 C 150 0 140 -120 120 -150 '
              'C 80 -180 -80 -180 -120 -150 Z')
    g += f'<path d="{coraza}" fill="url(#acero-h)" stroke="#454b5b" stroke-width="3"/>'
    # Reflejos y brillos para dar aspecto mágico
    g += f'<path d="{coraza}" fill="url(#acero-lustre)" opacity="0.7"/>'
    # Rebordes dorados ornamentados
    g += ('<path d="M -120 -150 C -80 -180 80 -180 120 -150" fill="none" '
          'stroke="url(#oro)" stroke-width="12" stroke-linecap="round"/>')
    g += ('<path d="M -110 180 C -80 220 80 220 110 180" fill="none" '
          'stroke="url(#oro)" stroke-width="10" stroke-linecap="round"/>')
    # Gema central
    g += _engaste(0, 20, 35)
    g += _gema(0, 20, 28, 32, "url(#gema-roja)")
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "280", "240"))

def vara_de_telekinesis() -> str:
    """Vara/cetro con gema flotante."""
    g = '<g transform="translate(350 250)">'
    # Vara de madera oscura
    g += ('<rect x="-8" y="-100" width="16" height="300" rx="8" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2"/>')
    # Remates de oro
    g += '<rect x="-12" y="-110" width="24" height="15" rx="5" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    g += '<rect x="-12" y="195" width="24" height="15" rx="5" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    # Gema flotante
    g += _gema(0, -180, 25, 35, "url(#gema-azul)")
    # Aura telekinética alrededor de la gema
    g += ('<ellipse cx="0" cy="-180" rx="45" ry="55" fill="url(#gema-azul)" '
          'opacity="0.3" filter="url(#sombra)"/>')
    g += ('<path d="M 0 -110 C -30 -130 -30 -150 0 -170" fill="none" '
          'stroke="#cfe4ff" stroke-width="3" opacity="0.8"/>')
    g += ('<path d="M 0 -110 C 30 -130 30 -150 0 -170" fill="none" '
          'stroke="#cfe4ff" stroke-width="3" opacity="0.8"/>')
    g += "</g>"
    return _lienzo(g, halo=("350", "180", "230", "200"))

def elixir_de_vida() -> str:
    """Poción especial en un frasco ornamentado."""
    g = '<g transform="translate(350 250)">'
    # Frasco de cristal tallado
    cuerpo = ('M 0 -120 L -60 -80 L -80 80 C -80 150 80 150 80 80 L 60 -80 Z')
    g += f'<path d="{cuerpo}" fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>'
    # Líquido perlado
    g += f'<clipPath id="clip-elixir"><path d="{cuerpo}"/></clipPath>'
    g += ('<g clip-path="url(#clip-elixir)">'
          '<rect x="-80" y="0" width="160" height="150" fill="url(#elixir-perlado)"/>'
          '</g>')
    # Tapón de oro con gema
    g += '<rect x="-30" y="-140" width="60" height="25" rx="8" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    g += _gema(0, -140, 15, 18, "url(#gema-verde)")
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "240", "220"))

def anillo_de_hechizos() -> str:
    """Anillo con gema azul mágica y runas."""
    g = '<g transform="translate(350 250)">'
    # Banda con runas
    g += '<circle cx="0" cy="0" r="100" fill="url(#oro)" stroke="#7d5a1e" stroke-width="25"/>'
    g += '<circle cx="0" cy="0" r="84" fill="url(#fondo)"/>'
    # Runas (texto)
    g += ('<text font-family="monospace" font-size="20" fill="#7d5a1e" text-anchor="middle">'
          '<textPath href="#anillo-runas">~*~*~*~*~*~*~*~*~*~</textPath></text>')
    g += '<path id="anillo-runas" d="M -80 0 A 80 80 0 1 1 80 0 A 80 80 0 1 1 -80 0" fill="none"/>'
    # Gema
    g += _engaste(0, -100, 35)
    g += _gema(0, -100, 28, 32, "url(#gema-azul)")
    g += "</g>"
    return _lienzo(g, halo=("350", "150", "200", "180"))

def varita_magica() -> str:
    """Varita con punta brillante de estrella/gema."""
    g = '<g transform="translate(350 250)">'
    # Cuerpo de la varita
    g += ('<rect x="-5" y="-150" width="10" height="300" rx="5" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2"/>')
    # Punta de estrella
    star = "M 0 -200 L 12 -180 L 30 -180 L 18 -168 L 24 -150 L 0 -162 L -24 -150 L -18 -168 L -30 -180 L -12 -180 Z"
    g += f'<path d="{star}" fill="url(#oro-pomo)" stroke="#c99a3f" stroke-width="2"/>'
    g += f'<path d="{star}" fill="#fff" opacity="0.5"/>'
    # Empuñadura
    g += '<ellipse cx="0" cy="120" rx="15" ry="8" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    g += '</g>'
    return _lienzo(g, halo=("350", "100", "180", "220"))

def espada_larga_de_la_fortuna() -> str:
    """Espada larga mágica con gema."""
    g = f'<g transform="translate(350 0)">'
    g += _hoja(0, 20, 60, 340, 19)
    g += _guarda_recta(0, 338, 100, 24)
    g += _gema(0, 350, 10, 12, "url(#gema-verde)")
    g += _empunadura(0, 362, 28, 90, 6)
    g += _pomo(0, 462, 21)
    g += "</g>"
    return _lienzo(g)

def azote_de_orcos() -> str:
    """Espada corta mágica con filo brillante."""
    g = f'<g transform="translate(350 0)">'
    g += _hoja(0, 80, 120, 320, 16)
    # Filo brillante
    g += ('<path d="M 0 82 L 15.5 120 L 15.5 320 L 0 320 Z" '
          'fill="url(#acero-lustre)" opacity="0.8"/>')
    g += _guarda_recta(0, 318, 80, 20)
    g += _empunadura(0, 338, 24, 80, 5)
    g += _pomo(0, 428, 18)
    g += "</g>"
    return _lienzo(g)

def filo_del_fantasma() -> str:
    """Daga ornamentada espectral, filo translúcido azulado."""
    g = f'<g transform="translate(350 0)">'
    # Hoja espectral
    g += _hoja(0, 120, 158, 300, 17, fill="url(#filo-espectral)")
    g += ('<path d="M 0 120 L 17 158 L 17 300 L -17 300 L -17 158 Z" '
          'fill="url(#filo-espectral)" opacity="0.5"/>')
    # Guarda ornamentada oscura
    g += ('<path d="M -70 308 L -60 290 L 60 290 L 70 308 L 60 326 L -60 326 Z" '
          'fill="#2a2340" stroke="#1f1a30" stroke-width="2"/>')
    g += _empunadura(0, 318, 26, 74, 5, fill="#2a2340")
    g += _pomo(0, 400, 17)
    g += _gema(0, 400, 8, 8, "url(#gema-azul)")
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "230", "210"))

def anillo_de_retorno() -> str:
    """Anillo de oro con gema."""
    g = '<g transform="translate(350 250)">'
    # Banda del anillo
    g += '<circle cx="0" cy="0" r="100" fill="url(#oro)" stroke="#7d5a1e" stroke-width="20"/>'
    g += '<circle cx="0" cy="0" r="88" fill="url(#fondo)"/>'
    # Engaste y gema
    g += _engaste(0, -100, 32)
    g += _gema(0, -100, 25, 30, "url(#gema-azul)")
    g += "</g>"
    return _lienzo(g)

def anillo_de_fortaleza() -> str:
    """Anillo de oro robusto con gema roja."""
    g = '<g transform="translate(350 250)">'
    # Banda robusta
    g += '<circle cx="0" cy="0" r="100" fill="url(#oro)" stroke="#7d5a1e" stroke-width="30"/>'
    g += '<circle cx="0" cy="0" r="80" fill="url(#fondo)"/>'
    # Engaste cuadrado
    g += ('<rect x="-35" y="-135" width="70" height="70" rx="10" fill="url(#oro)" '
          'stroke="#7d5a1e" stroke-width="4"/>')
    g += _gema(0, -100, 28, 28, "url(#gema-roja)")
    g += "</g>"
    return _lienzo(g)

def filo_del_espiritu() -> str:
    """Espada mágica con mango de hueso tallado."""
    g = f'<g transform="translate(350 0)">'
    g += _hoja(0, 40, 78, 315, 17)
    g += _guarda_recta(0, 312, 88, 22)
    # Empuñadura de hueso
    g += _empunadura(0, 334, 26, 86, 0, fill="url(#hueso)")
    # Tallas en el hueso
    g += ('<g stroke="#5a4a3a" stroke-width="1.5" fill="none">'
          '<path d="M -8 350 C 0 360 8 370 0 380"/>'
          '<path d="M -8 390 C 0 400 8 410 0 420"/>'
          '</g>')
    g += _pomo(0, 430, 19)
    g += "</g>"
    return _lienzo(g)

def talisman_de_la_sabiduria() -> str:
    """Medallón/amuleto de oro con gema azul en cadena."""
    g = '<g transform="translate(350 250)">'
    # Cadena
    g += ('<path d="M -120 -100 C -80 -150 80 -150 120 -100" fill="none" '
          'stroke="url(#oro)" stroke-width="8" stroke-linecap="round"/>')
    # Medallón
    g += '<circle cx="0" cy="0" r="80" fill="url(#oro-pomo)" stroke="#7d5a1e" stroke-width="4"/>'
    g += _engaste(0, 0, 50)
    g += _gema(0, 0, 42, 42, "url(#gema-azul)")
    # Anilla para la cadena
    g += '<circle cx="0" cy="-80" r="12" fill="url(#oro)" stroke="#7d5a1e" stroke-width="4"/>'
    g += '</g>'
    return _lienzo(g)

def capa_de_mago() -> str:
    """Capa de tela brillante con runas místicas."""
    g = '<g transform="translate(350 250)">'
    # Forma de la capa
    capa_path = ('M -200 -200 Q 0 -250 200 -200 L 150 220 Q 0 280 -150 220 Z')
    g += f'<path d="{capa_path}" fill="url(#tela-magica)" stroke="#05051A" stroke-width="3"/>'
    # Broche
    g += _pomo(0, -200, 25)
    g += _gema(0, -200, 12, 12, "url(#gema-roja)")
    # Runas doradas
    g += ('<g fill="url(#oro)" opacity="0.7">'
          '<text x="0" y="50" font-size="60" text-anchor="middle" font-family="serif">ᛗ</text>'
          '<text x="-80" y="150" font-size="50" text-anchor="middle" font-family="serif" transform="rotate(-15 -80 150)">ᛟ</text>'
          '<text x="80" y="150" font-size="50" text-anchor="middle" font-family="serif" transform="rotate(15 80 150)">ᛉ</text>'
          '</g>')
    g += '</g>'
    return _lienzo(g)

def baston_del_mago() -> str:
    """Bastón de mago grueso y centrado con una gema azul luminosa en la punta."""
    g = '<g transform="translate(350 250)">'

    # Resplandor de la gema (halo azul) detrás de la punta.
    g += '<circle cx="0" cy="-150" r="90" fill="#3b7fe2" opacity="0.28"/>'
    g += '<circle cx="0" cy="-150" r="55" fill="#a8dcff" opacity="0.30"/>'

    # Vara de madera gruesa, ligeramente nudosa, centrada en x=0.
    g += ('<path d="M -16 -110 '
          'C -22 -40 -10 40 -14 120 '
          'C -15 160 -13 200 -12 224 '
          'L 12 224 '
          'C 13 200 15 160 14 120 '
          'C 10 40 22 -40 16 -110 Z" '
          'fill="url(#madera)" stroke="#2e1a09" stroke-width="3.5" stroke-linejoin="round"/>')
    # Vetas y nudos de la madera.
    g += '<path d="M -6 -90 C -12 0 8 90 2 210" fill="none" stroke="#2e1a09" stroke-width="2" opacity="0.5"/>'
    g += '<ellipse cx="-2" cy="40" rx="7" ry="11" fill="#2e1a09" opacity="0.35"/>'
    g += '<ellipse cx="4" cy="150" rx="6" ry="10" fill="#2e1a09" opacity="0.3"/>'
    # Lustre de la madera.
    g += '<path d="M -10 -100 C -14 -20 -6 100 -8 220 L -3 220 C -1 100 -8 -20 -4 -100 Z" fill="#e8c99a" opacity="0.35"/>'

    # Engarce dorado que sujeta la gema (garras).
    g += ('<path d="M -26 -108 C -18 -118 18 -118 26 -108 '
          'L 18 -84 C 6 -92 -6 -92 -18 -84 Z" '
          'fill="url(#oro)" stroke="#7d5a1e" stroke-width="2.5"/>')
    g += '<path d="M -22 -104 L -30 -128 M 0 -110 L 0 -138 M 22 -104 L 30 -128" stroke="url(#oro)" stroke-width="6" stroke-linecap="round"/>'

    # Gema azul GRANDE luminosa en la punta.
    g += _gema(0, -158, 44, 58, "url(#gema-azul)")
    # Brillo interior de la gema.
    g += '<ellipse cx="-12" cy="-176" rx="12" ry="16" fill="#ffffff" opacity="0.55"/>'

    # Destellos alrededor de la gema.
    g += ('<g stroke="#cfe4ff" stroke-width="5" stroke-linecap="round" opacity="0.9">'
          '<path d="M 0 -232 L 0 -252"/>'
          '<path d="M 70 -158 L 92 -158"/>'
          '<path d="M -70 -158 L -92 -158"/>'
          '<path d="M 52 -206 L 66 -220"/>'
          '<path d="M -52 -206 L -66 -220"/>'
          '</g>')
    g += '</g>'
    return _lienzo(g, halo=("350", "120", "260", "250"))

# ---------------------------------------------------------------------------
# CARTAS DE TESORO
# ---------------------------------------------------------------------------

def gema_tesoro() -> str:
    """Una única gema brillante."""
    g = '<g transform="translate(350 250)">'
    g += _gema(0, 0, 80, 100, "url(#gema-roja)")
    # Destellos
    g += ('<g stroke="#ffd0cf" stroke-width="4" stroke-linecap="round" opacity="0.8">'
          '<path d="M 0 -110 L 0 -130"/>'
          '<path d="M 85 0 L 105 0"/>'
          '<path d="M -85 0 L -105 0"/>'
          '<path d="M 60 -78 L 75 -90"/>'
          '<path d="M -60 -78 L -75 -90"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "240", "220"))


def oro_15() -> str:
    """Un montón de monedas de oro con el número 15."""
    g = '<g transform="translate(350 250)">'
    # Montón de monedas
    monedas = [
        (0, 40, 40), (-50, 50, 40), (50, 50, 40),
        (-20, 80, 40), (30, 80, 40), (80, 90, 40), (-70, 90, 40)
    ]
    for x, y, r in monedas:
        g += f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#oro-pomo)" stroke="#6f4e18" stroke-width="2"/>'
    # Texto "15"
    g += ('<text x="0" y="-10" font-family="Amarna, serif" font-size="120" font-weight="bold" '
          'fill="#f6d98a" stroke="#7d5a1e" stroke-width="4" text-anchor="middle">15</text>')
    g += "</g>"
    return _lienzo(g, halo=("350", "280", "250", "210"))


def oro_25() -> str:
    """Un montón de monedas de oro más grande con el número 25."""
    g = '<g transform="translate(350 250)">'
    # Montón de monedas más grande
    monedas = [
        (0, 20, 45), (-60, 30, 45), (60, 30, 45),
        (-30, 70, 45), (30, 70, 45), (90, 70, 45), (-90, 70, 45),
        (0, 110, 45), (-60, 110, 45), (60, 110, 45)
    ]
    for x, y, r in monedas:
        g += f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#oro-pomo)" stroke="#6f4e18" stroke-width="2"/>'
    # Texto "25"
    g += ('<text x="0" y="-30" font-family="Amarna, serif" font-size="120" font-weight="bold" '
          'fill="#f6d98a" stroke="#7d5a1e" stroke-width="4" text-anchor="middle">25</text>')
    g += "</g>"
    return _lienzo(g, halo=("350", "280", "260", "220"))


def joyas() -> str:
    """Cofre del tesoro abierto con joyas."""
    g = '<g transform="translate(350 250)">'
    # Base del cofre
    g += ('<rect x="-100" y="20" width="200" height="100" rx="10" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="3"/>')
    # Tapa abierta
    g += ('<path d="M -100 20 C -100 -50 100 -50 100 20 L 110 30 C 110 -60 -110 -60 -110 30 Z" '
          'fill="url(#madera)" stroke="#2e1a09" stroke-width="3"/>')
    # Cierre dorado
    g += '<rect x="-20" y="10" width="40" height="30" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    # Joyas dentro
    g += _gema(-40, 50, 20, 25, "url(#gema-roja)")
    g += _gema(10, 40, 25, 20, "url(#gema-azul)")
    g += _gema(50, 55, 18, 22, "url(#gema-verde)")
    g += '<circle cx="-10" cy="80" r="15" fill="url(#oro-pomo)"/>'
    g += '<circle cx="30" cy="85" r="12" fill="url(#oro-pomo)"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "260", "220"))


def _pocion_tesoro(liquido_fill: str, simbolo: str = "") -> str:
    """Función helper para las pociones de tesoro."""
    g = '<g transform="translate(350 250)">'
    cuerpo = ('M -34 -20 '
              'C -70 0 -84 50 -84 90 '
              'C -84 150 -40 190 0 190 '
              'C 40 190 84 150 84 90 '
              'C 84 50 70 0 34 -20 Z')
    g += f'<clipPath id="clip-pocion-tesoro"><path d="{cuerpo}"/></clipPath>'
    g += f'<path d="{cuerpo}" fill="#0d1420" opacity="0.5"/>'
    g += ('<g clip-path="url(#clip-pocion-tesoro)">'
          f'<rect x="-90" y="50" width="180" height="160" fill="{liquido_fill}"/>'
          '</g>')
    g += f'<path d="{cuerpo}" fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>'
    g += ('<path d="M -50 18 C -66 46 -70 80 -66 110" fill="none" '
          'stroke="#ffffff" stroke-width="9" opacity="0.5" stroke-linecap="round"/>')
    g += ('<path d="M -22 -14 L -18 -74 L 18 -74 L 22 -14 Z" '
          'fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>')
    g += '<rect x="-24" y="-100" width="48" height="34" rx="6" fill="url(#madera)" stroke="#2e1a09" stroke-width="2"/>'
    if simbolo:
        g += simbolo
    g += "</g>"
    return _lienzo(g, halo=("350", "280", "220", "185"))


def pocion_heroica() -> str:
    """Poción dorada brillante."""
    simbolo = ('<path d="M 0 50 L -15 80 L 15 80 Z" fill="#f6d98a" stroke="#7d5a1e" stroke-width="2"/>'
               '<circle cx="0" cy="100" r="12" fill="#f6d98a" stroke="#7d5a1e" stroke-width="2"/>')
    return _pocion_tesoro("url(#pocion-heroica)", simbolo)


def pocion_de_defensa() -> str:
    """Poción plateada con un escudo."""
    simbolo = ('<path d="M 0 60 L 25 70 L 20 100 C 10 120 -10 120 -20 100 L -25 70 Z" '
               'fill="#c3cbd8" stroke="#646c7d" stroke-width="3"/>')
    return _pocion_tesoro("url(#pocion-defensa)", simbolo)


def pocion_de_fuerza() -> str:
    """Poción púrpura con un símbolo de 'brazo fuerte'."""
    simbolo = ('<path d="M -10 70 C -25 70 -25 100 -10 100 L 10 100 C 25 100 25 125 10 125" '
               'fill="none" stroke="#e0b0ff" stroke-width="5" stroke-linecap="round"/>')
    return _pocion_tesoro("url(#pocion-fuerza)", simbolo)


def pocion_curativa_tesoro() -> str:
    """Poción azulada suave."""
    simbolo = ('<rect x="-5" y="80" width="10" height="30" rx="3" fill="#a8dcff"/>'
               '<rect x="-15" y="90" width="30" height="10" rx="3" fill="#a8dcff"/>')
    return _pocion_tesoro("url(#pocion-curativa-tesoro)", simbolo)


def peligro_agujero() -> str:
    """Un agujero oscuro en el suelo."""
    g = '<g transform="translate(350 250)">'
    g += '<ellipse cx="0" cy="0" rx="150" ry="80" fill="#111"/>'
    g += '<ellipse cx="0" cy="0" rx="120" ry="60" fill="#000"/>'
    # Perspectiva
    g += ('<g stroke="#333" stroke-width="2">'
          '<line x1="-150" y1="0" x2="-120" y2="0"/>'
          '<line x1="150" y1="0" x2="120" y2="0"/>'
          '<line x1="0" y1="80" x2="0" y2="60"/>'
          '<line x1="0" y1="-80" x2="0" y2="-60"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "260", "180"))


def peligro_flecha() -> str:
    """Una flecha siendo disparada desde una trampa en la pared."""
    g = '<g transform="translate(350 250)">'
    # Muro de ladrillos
    g += '<rect x="-250" y="-200" width="500" height="400" fill="#6a4a26"/>'
    # Agujero de la trampa
    g += '<rect x="-200" y="-20" width="80" height="40" fill="#111"/>'
    # Flecha
    g += ('<g transform="translate(-100 0)">'
          '<rect x="0" y="-3.5" width="250" height="7" rx="3" fill="#6a4a26" stroke="#2e1a09" stroke-width="1.5"/>'
          '<path d="M 250 0 L 220 -12 L 220 12 Z" fill="url(#acero-h)" stroke="#454b5b" stroke-width="1.5"/>'
          '<path d="M 0 0 L 20 -12 L 14 0 L 20 12 Z" fill="#b5453f" stroke="#5c1c18" stroke-width="1"/>'
          '</g>')
    # Líneas de movimiento
    g += ('<g stroke="#fff" stroke-width="3" opacity="0.7">'
          '<line x1="-120" y1="-10" x2="-40" y2="-10"/>'
          '<line x1="-120" y1="10" x2="-40" y2="10"/>'
          '</g>')
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "280", "180"))


def monstruo_errante() -> str:
    """Silueta amenazante de un monstruo con ojos rojos."""
    g = '<g transform="translate(350 250)">'
    # Silueta
    g += ('<path d="M 0 -150 C -50 -140 -80 -100 -100 -50 '
          'L -120 50 C -100 120 -40 150 0 150 '
          'C 40 150 100 120 120 50 L 100 -50 '
          'C 80 -100 50 -140 0 -150 Z" fill="#111"/>')
    # Cuernos
    g += '<path d="M -40 -140 C -60 -180 -20 -180 0 -150" fill="#111"/>'
    g += '<path d="M 40 -140 C 60 -180 20 -180 0 -150" fill="#111"/>'
    # Ojos rojos
    g += '<circle cx="-30" cy="-80" r="10" fill="#c0303a"/>'
    g += '<circle cx="30" cy="-80" r="10" fill="#c0303a"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "250", "220"))


def nada() -> str:
    """Una bolsa de cuero vacía y desatada."""
    g = '<g transform="translate(350 250)">'
    # Cuerpo de la bolsa
    g += ('<path d="M -80 -50 C -100 50 100 50 80 -50 L 60 -80 L -60 -80 Z" '
          'fill="url(#cuero)" stroke="#2e1a09" stroke-width="3"/>')
    # Abertura vacía
    g += '<ellipse cx="0" cy="-75" rx="65" ry="20" fill="#14111f"/>'
    # Cuerda desatada
    g += ('<path d="M -70 -70 C -20 -110 20 -110 70 -70" fill="none" '
          'stroke="#8a5a2f" stroke-width="5" stroke-linecap="round"/>')
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "240", "200"))


# ---------------------------------------------------------------------------
# REGISTRO DE OBJETOS
# ---------------------------------------------------------------------------

def brazaletes() -> str:
    g = '<g transform="translate(350 250)">'
    # Par de brazaletes, uno ligeramente adelantado
    for i, offset_x in enumerate([-100, 100]):
        transform = f'transform="translate({offset_x} 0) rotate({-5 + i*10})"'
        g += f'<g {transform}>'
        # Cuerpo de cuero
        g += ('<path d="M -50 -80 L 50 -70 L 55 70 L -55 80 Z" '
              'fill="url(#cuero)" stroke="#2e1a09" stroke-width="2.5"/>')
        # Refuerzos metálicos
        g += '<rect x="-40" y="-55" width="80" height="20" rx="5" fill="url(#acero)" stroke="#454b5b" stroke-width="1.5"/>'
        g += '<rect x="-40" y="35" width="80" height="20" rx="5" fill="url(#acero)" stroke="#454b5b" stroke-width="1.5"/>'
        # Hebillas doradas
        g += '<rect x="-15" y="-20" width="30" height="40" rx="4" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
        g += '<rect x="-5" y="-15" width="10" height="30" fill="#42280f"/>'
        g += '</g>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "280", "190"))

def espada_larga() -> str:
    g = f'<g transform="translate(350 0)">'
    # Hoja más larga que la espada corta
    g += _hoja(0, 20, 60, 360, 18)
    g += _guarda_recta(0, 357, 92, 22)
    g += _empunadura(0, 379, 28, 90, 6)
    g += _pomo(0, 479, 20)
    g += "</g>"
    return _lienzo(g)

def cota_de_malla() -> str:
    # Patrón de anillas claro sobre base de acero brillante (buen contraste).
    defs_extra = '''
    <pattern id="malla" patternUnits="userSpaceOnUse" width="11" height="11">
      <rect width="11" height="11" fill="#aeb7c6"/>
      <circle cx="3" cy="3" r="3.4" fill="none" stroke="#e8edf4" stroke-width="1.6"/>
      <circle cx="8.5" cy="8.5" r="3.4" fill="none" stroke="#e8edf4" stroke-width="1.6"/>
      <circle cx="3" cy="3" r="3.4" fill="none" stroke="#5b6376" stroke-width="0.5"/>
      <circle cx="8.5" cy="8.5" r="3.4" fill="none" stroke="#5b6376" stroke-width="0.5"/>
    </pattern>
    '''
    g = '<g transform="translate(350 250)">'
    # Camisote de malla: cuerpo central + dos mangas cortas + cuello redondo.
    cuerpo = ('M -70 -120 L 70 -120 L 82 -80 L 82 140 '
              'C 82 152 72 160 60 160 L -60 160 '
              'C -72 160 -82 152 -82 140 L -82 -80 Z')
    manga_izq = 'M -70 -112 L -150 -60 L -132 -6 L -82 -44 Z'
    manga_der = 'M 70 -112 L 150 -60 L 132 -6 L 82 -44 Z'
    for d in (manga_izq, manga_der, cuerpo):
        g += f'<path d="{d}" fill="url(#malla)" stroke="#3c414e" stroke-width="3.5" stroke-linejoin="round"/>'
    # Escote redondo del cuello (hueco oscuro).
    g += ('<path d="M -34 -120 C -34 -84 34 -84 34 -120 Z" '
          'fill="#1a1626" stroke="#3c414e" stroke-width="3"/>')
    # Lustre diagonal que recorre el torso (volumen metálico).
    g += ('<path d="M -60 -70 C -30 40 -10 110 30 150 L 60 150 '
          'C 20 90 -10 0 -20 -70 Z" fill="#ffffff" opacity="0.20"/>')
    # Sombra lateral derecha.
    g += ('<path d="M 40 -70 C 55 30 60 100 55 150 L 60 150 '
          'C 72 160 82 150 82 130 L 82 -60 Z" fill="#1a2030" opacity="0.28"/>')
    # Cinturón de cuero en la cintura.
    g += ('<rect x="-84" y="60" width="168" height="26" rx="5" '
          'fill="url(#cuero)" stroke="#2e1a09" stroke-width="2.5"/>')
    g += '<rect x="-14" y="60" width="28" height="26" rx="4" fill="url(#oro)" stroke="#6f4e18" stroke-width="2"/>'
    g += "</g>"
    return _lienzo(defs_extra + g, halo=("350", "250", "260", "210"))

def espada_ancha() -> str:
    g = f'<g transform="translate(350 0)">'
    # Hoja más ancha que la espada corta
    g += _hoja(0, 60, 100, 340, 28)
    g += _guarda_recta(0, 337, 100, 24)
    g += _empunadura(0, 361, 30, 80, 5)
    g += _pomo(0, 451, 21)
    g += "</g>"
    return _lienzo(g)

def hacha_enana() -> str:
    g = '<g transform="translate(350 250)">'
    # Mango corto y robusto
    g += ('<rect x="-12" y="-120" width="24" height="240" rx="8" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2.5"/>')
    g += _envoltura(-12, 12, -40, 6, 14)
    # Cabeza de hacha de doble filo, estilo enano
    hoja_izq = 'M -8 -90 L -60 -100 L -140 -60 L -140 60 L -60 100 L -8 90 Z'
    hoja_der = 'M 8 -90 L 60 -100 L 140 -60 L 140 60 L 60 100 L 8 90 Z'
    for hoja in (hoja_izq, hoja_der):
        g += (f'<path d="{hoja}" fill="url(#acero-h)" stroke="#454b5b" '
              'stroke-width="3" stroke-linejoin="round"/>')
    # Filos brillantes
    g += ('<path d="M -140 -60 L -140 60" fill="none" '
          'stroke="#ffffff" stroke-width="5" opacity="0.6" stroke-linecap="round"/>')
    g += ('<path d="M 140 -60 L 140 60" fill="none" '
          'stroke="#ffffff" stroke-width="5" opacity="0.6" stroke-linecap="round"/>')
    # Engarce dorado
    g += ('<rect x="-20" y="-95" width="40" height="190" rx="10" fill="url(#oro)" '
          'stroke="#5c4413" stroke-width="2"/>')
    g += _gema(0, 0, 14, 14, "url(#gema-roja)")
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "260", "200"))

def agua_bendita() -> str:
    # Perfil de frasco de poción
    cuerpo = ('M -34 230 C -70 250 -84 300 -84 340 C -84 400 -40 440 0 440 '
              'C 40 440 84 400 84 340 C 84 300 70 250 34 230 Z')
    # Gradiente para el líquido
    defs_extra = '''
    <radialGradient id="agua-bendita-grad" cx="50%" cy="40%" r="80%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="50%" stop-color="#fffde4"/>
      <stop offset="100%" stop-color="#f0e6a8"/>
    </radialGradient>
    '''
    g = '<g transform="translate(350 0)">'
    # Líquido
    g += f'<clipPath id="clip-agua"><path d="{cuerpo}"/></clipPath>'
    g += ('<g clip-path="url(#clip-agua)">'
          '<rect x="-90" y="290" width="180" height="170" fill="url(#agua-bendita-grad)"/>'
          # Destellos
          '<path d="M -20 350 l 10 -20 l 10 20 l 20 10 l -20 10 l -10 20 l -10 -20 l -20 -10 Z" fill="#ffffff" opacity="0.8"/>'
          '</g>')
    # Vidrio
    g += f'<path d="{cuerpo}" fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>'
    g += ('<path d="M -50 268 C -66 296 -70 330 -66 360" fill="none" '
          'stroke="#ffffff" stroke-width="9" opacity="0.5" stroke-linecap="round"/>')
    # Cuello y tapón de plata
    g += ('<path d="M -22 236 L -18 176 L 18 176 L 22 236 Z" '
          'fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>')
    g += '<rect x="-24" y="150" width="48" height="34" rx="6" fill="url(#acero)" stroke="#454b5b" stroke-width="2"/>'
    # Símbolo sagrado (sol)
    g += '<circle cx="0" cy="360" r="22" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
    g += '<circle cx="0" cy="360" r="12" fill="url(#oro-pomo)"/>'
    g += "</g>"
    return _lienzo(defs_extra + g, halo=("350", "330", "220", "185"))

def coraza() -> str:
    g = '<g transform="translate(350 250)">'
    # Hombreras (pauldrons) a ambos lados, para leerse como armadura de torso.
    g += ('<path d="M -150 -60 C -150 -120 -95 -140 -70 -120 L -70 -60 '
          'C -95 -40 -130 -30 -150 -60 Z" fill="url(#acero)" '
          'stroke="#3c414e" stroke-width="3" stroke-linejoin="round"/>')
    g += ('<path d="M 150 -60 C 150 -120 95 -140 70 -120 L 70 -60 '
          'C 95 -40 130 -30 150 -60 Z" fill="url(#acero)" '
          'stroke="#3c414e" stroke-width="3" stroke-linejoin="round"/>')
    # Peto anatómico: hombros anchos, cintura estrecha, faldón inferior.
    peto = ('M -96 -118 C -40 -134 40 -134 96 -118 '
            'L 104 -40 C 104 10 92 46 78 78 '
            'L 40 150 L -40 150 L -78 78 '
            'C -92 46 -104 10 -104 -40 Z')
    g += (f'<path d="{peto}" fill="url(#acero-h)" stroke="#3c414e" '
          'stroke-width="3.5" stroke-linejoin="round"/>')
    # Escote/cuello en V.
    g += ('<path d="M -34 -122 L 0 -78 L 34 -122 Z" fill="#1a1626" '
          'stroke="#3c414e" stroke-width="2.5"/>')
    # Pectorales: dos placas abombadas separadas por el esternón.
    g += ('<path d="M -12 -70 C -60 -66 -92 -40 -92 10 C -92 44 -70 66 -14 62 '
          'C -14 20 -12 -30 -12 -70 Z" fill="#c3cbd8" opacity="0.55"/>')
    g += ('<path d="M 12 -70 C 60 -66 92 -40 92 10 C 92 44 70 66 14 62 '
          'C 14 20 12 -30 12 -70 Z" fill="#9aa3b3" opacity="0.55"/>')
    # Línea del esternón y de la cintura (placas del abdomen).
    g += '<line x1="0" y1="-70" x2="0" y2="150" stroke="#5b6376" stroke-width="3"/>'
    for y in (78, 104, 128):
        g += f'<path d="M -70 {y} C -30 {y+12} 30 {y+12} 70 {y}" fill="none" stroke="#5b6376" stroke-width="2.5"/>'
    # Lustre y sombra de volumen.
    g += ('<path d="M -80 -100 C -60 -20 -50 60 -40 120 L -20 120 '
          'C -34 40 -50 -30 -56 -104 Z" fill="#ffffff" opacity="0.22"/>')
    g += (f'<path d="M 40 -110 C 80 -90 100 -40 100 10 C 100 60 84 110 60 150 '
          'L 40 150 L 78 78 C 96 30 96 -40 90 -104 Z" fill="#1a2030" opacity="0.20"/>')
    # Remaches de oro por el borde.
    for y in (-96, -30, 40):
        g += f'<circle cx="-86" cy="{y}" r="5" fill="url(#oro)" stroke="#6f4e18" stroke-width="1.5"/>'
        g += f'<circle cx="86" cy="{y}" r="5" fill="url(#oro)" stroke="#6f4e18" stroke-width="1.5"/>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "270", "220"))

def pocion_de_velocidad() -> str:
    # Perfil de frasco
    cuerpo = ('M -34 230 C -70 250 -84 300 -84 340 C -84 400 -40 440 0 440 '
              'C 40 440 84 400 84 340 C 84 300 70 250 34 230 Z')
    # Gradiente para el líquido
    defs_extra = '''
    <radialGradient id="pocion-velocidad-grad" cx="50%" cy="40%" r="80%">
      <stop offset="0%" stop-color="#e8ffb8"/>
      <stop offset="50%" stop-color="#b8e03c"/>
      <stop offset="100%" stop-color="#6a8a1e"/>
    </radialGradient>
    '''
    g = '<g transform="translate(350 0)">'
    # Líquido
    g += f'<clipPath id="clip-velocidad"><path d="{cuerpo}"/></clipPath>'
    g += ('<g clip-path="url(#clip-velocidad)">'
          '<rect x="-90" y="290" width="180" height="170" fill="url(#pocion-velocidad-grad)"/>'
          '</g>')
    # Vidrio
    g += f'<path d="{cuerpo}" fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>'
    g += ('<path d="M -50 268 C -66 296 -70 330 -66 360" fill="none" '
          'stroke="#ffffff" stroke-width="9" opacity="0.5" stroke-linecap="round"/>')
    # Cuello y corcho
    g += ('<path d="M -22 236 L -18 176 L 18 176 L 22 236 Z" '
          'fill="url(#vidrio)" stroke="#b9c7cd" stroke-width="3"/>')
    g += '<rect x="-24" y="150" width="48" height="34" rx="6" fill="url(#madera)" stroke="#2e1a09" stroke-width="2"/>'
    # Símbolo de velocidad (rayo)
    g += ('<path d="M 10 340 L -15 365 L 5 365 L -10 390 L 20 360 L 0 360 Z" '
          'fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>')
    g += "</g>"
    return _lienzo(defs_extra + g, halo=("350", "330", "220", "185"))

def baston() -> str:
    g = '<g transform="translate(350 250) rotate(-20)">'
    # Vara de madera
    g += ('<rect x="-10" y="-200" width="20" height="400" rx="10" fill="url(#madera)" '
          'stroke="#2e1a09" stroke-width="2.5"/>')
    # Reflejo de barniz
    g += ('<rect x="-4" y="-190" width="5" height="380" rx="2.5" '
          'fill="#c69a5f" opacity="0.4"/>')
    # Refuerzos metálicos en los extremos
    g += ('<rect x="-14" y="-210" width="28" height="25" rx="8" fill="url(#acero)" '
          'stroke="#454b5b" stroke-width="2"/>')
    g += ('<rect x="-14" y="185" width="28" height="25" rx="8" fill="url(#acero)" '
          'stroke="#454b5b" stroke-width="2"/>')
    # Envoltura de cuero en el centro
    g += _envoltura(-10, 10, -50, 8, 12)
    g += "</g>"
    return _lienzo(g)

def conjunto_de_herramientas() -> str:
    g = '<g transform="translate(350 250)">'
    # Paño de cuero extendido
    g += ('<path d="M -200 -120 L 180 -110 C 220 -100 230 100 190 130 '
          'L -170 140 C -210 130 -240 -80 -200 -120 Z" '
          'fill="url(#cuero)" stroke="#2e1a09" stroke-width="3"/>')
    # Herramientas de metal dispuestas sobre el paño
    g += '<g fill="url(#acero)" stroke="#454b5b" stroke-width="2">'
    # Ganzúa
    g += '<path d="M -140 -30 L 20 -25 L 25 -40 L 35 -38 Z" transform="rotate(10)"/>'
    # Palanca
    g += '<path d="M -120 20 L 40 30 C 50 32 55 45 45 50 L 35 48 Z" transform="rotate(-5)"/>'
    # Llave
    g += ('<g transform="translate(100 0) rotate(25)">'
          '<circle cx="0" cy="0" r="25"/>'
          '<rect x="-5" y="20" width="10" height="50" />'
          '<rect x="-15" y="70" width="30" height="8" />'
          '<rect x="-15" y="85" width="30" height="8" />'
          '<circle cx="0" cy="0" r="15" fill="url(#cuero)"/>'
          '</g>')
    g += '</g>'
    g += "</g>"
    return _lienzo(g, halo=("350", "250", "300", "210"))


OBJETOS = {
    "Yelmo": yelmo,
    "Escudo": escudo,
    "Hacha de Batalla": hacha_de_batalla,
    "Brazaletes": brazaletes,
    "Espada Larga": espada_larga,
    "Cota de Malla": cota_de_malla,
    "Ballesta": ballesta,
    "Espada Ancha": espada_ancha,
    "Daga": daga,
    "Hacha Enana": hacha_enana,
    "Agua Bendita": agua_bendita,
    "Coraza": coraza,
    "Poción de Velocidad": pocion_de_velocidad,
    "Espada Corta": espada_corta,
    "Bastón": baston,
    "Conjunto de Herramientas": conjunto_de_herramientas,
    "Mandoble": mandoble,
    "Báculo del mago": baculo_del_mago,
    "Armadura de placas": armadura_de_placas,
    "Poción de curación": pocion_de_curacion,
    "Poción de mente": pocion_de_mente,
    "Espada de gemas": espada_de_gemas,
    "Curar heridas": curar_heridas,
    "Dardo de caos": dardo_de_caos,
    "Tempestad": tempestad,
    "Ráfaga": rafaga,
    "Genio": genio,
    "Fuego de la Ira": fuego_de_la_ira,
    "Valentía": valentia,
    "Bola de Fuego": bola_de_fuego,
    "Agua Milagrosa": agua_milagrosa,
    "Niebla": niebla,
    "Dormir": dormir,
    "Piel de Roca": piel_de_roca,
    "Cura Corporal": cura_corporal,
    "A Través de la Roca": a_traves_de_la_roca,
    "Invocar Muertos Vivientes": invocar_muertos_vivientes,
    "Invocar Orcos": invocar_orcos,
    "Oxidación": oxidacion,
    "Rayo Mortífero": rayo_mortifero,
    "Bola en Llamas": bola_en_llamas,
    "Nube de Terror": nube_de_terror,
    "Dominación": dominacion,
    "Huída Fugaz": huida_fugaz,
    "Miedo": miedo,
    "Tormenta de Fuego": tormenta_de_fuego,
    "Gema!": gema_tesoro,
    "Oro! (15)": oro_15,
    "Oro! (25)": oro_25,
    "Joyas!": joyas,
    "Poción Heroica": pocion_heroica,
    "Poción de Defensa": pocion_de_defensa,
    "Poción de Fuerza": pocion_de_fuerza,
    "Poción Curativa": pocion_curativa_tesoro,
    "Peligro! (Agujero)": peligro_agujero,
    "Peligro! (Flecha)": peligro_flecha,
    "Monstruo Errante": monstruo_errante,
    "Nada!": nada,
    "Armadura de Borin": armadura_de_borin,
    "Vara de Telekinesis": vara_de_telekinesis,
    "Elixir de Vida": elixir_de_vida,
    "Espada Larga de la Fortuna": espada_larga_de_la_fortuna,
    "Azote de Orcos": azote_de_orcos,
    "Filo del Fantasma": filo_del_fantasma,
    "Anillo de Retorno": anillo_de_retorno,
    "Anillo de Fortaleza": anillo_de_fortaleza,
    "Anillo de Hechizos": anillo_de_hechizos,
    "Filo del Espíritu": filo_del_espiritu,
    "Talismán de la Sabiduría": talisman_de_la_sabiduria,
    "Varita Mágica": varita_magica,
    "Capa de Mago": capa_de_mago,
    "Bastón del Mago": baston_del_mago,
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

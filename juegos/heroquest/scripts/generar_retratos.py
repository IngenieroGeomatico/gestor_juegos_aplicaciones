# -*- coding: utf-8 -*-
"""Genera los retratos de anverso de héroes y monstruos de HeroQuest.

Cada héroe (Bárbaro, Enano, Elfo, Mago) y cada monstruo (Trasgo, Orco, Fimir,
Guerrero del Caos, Gárgola) se dibuja como un retrato de busto en SVG vectorial
y se rasteriza a PNG con `resvg`. Reemplaza el arte genérico (espadas cruzadas
para héroes, calavera para monstruos) por un retrato propio de cada personaje.

- Los SVG (fuente de verdad, editables) van a `sources/arte_svg/`.
- Los PNG finales van a `sources/arte/` con el nombre de convención
  (el `slug` del nombre, p. ej. `Bárbaro.png`, `Guerrero_del_Caos.png`).

Uso:
    uv run juegos/heroquest/scripts/generar_retratos.py            # todos
    uv run juegos/heroquest/scripts/generar_retratos.py --solo Orco
    uv run juegos/heroquest/scripts/generar_retratos.py --svg-solo # solo SVG
"""

from __future__ import annotations

import argparse
from pathlib import Path

from arte_comun import rasterizar as _rasterizar_png
from arte_comun import slug as _slug

ARTE_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte"
ARTE_SVG_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_svg"

# Lienzo VERTICAL para encajar el área de arte a 4/5 de la plantilla
# el área de arte de la plantilla (ratio ≈ 0.87). Usamos un lienzo
# de la misma proporción (520×600, ratio ≈ 0.867) para que el recorte "cover"
# del motor de render no recorte el busto. El busto se dibuja con las mismas
# coordenadas de siempre (centrado en x=0, de y≈-20 a y≈500) y se recoloca con
# un `translate` para quedar grande y con la cabeza arriba.
ANCHO, ALTO = 520, 600
# Centro horizontal del busto y desplazamiento vertical (cabeza arriba).
CENTRO_X = ANCHO / 2
DESPLAZA_Y = 44


# ---------------------------------------------------------------------------
# Defs y bloques comunes
# ---------------------------------------------------------------------------

DEFS = """
  <defs>
    <radialGradient id="fondo" cx="50%" cy="52%" r="65%">
      <stop offset="0%" stop-color="#3a3350"/>
      <stop offset="55%" stop-color="#211d33"/>
      <stop offset="100%" stop-color="#14111f"/>
    </radialGradient>
    <radialGradient id="halo" cx="50%" cy="45%" r="52%">
      <stop offset="0%" stop-color="#ffdca8" stop-opacity="0.30"/>
      <stop offset="55%" stop-color="#e8b878" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#e8b878" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="piel" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#e8b083"/>
      <stop offset="55%" stop-color="#c88a5c"/>
      <stop offset="100%" stop-color="#8f5c38"/>
    </linearGradient>
    <linearGradient id="piel-palida" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f2ddc4"/>
      <stop offset="55%" stop-color="#dcc0a2"/>
      <stop offset="100%" stop-color="#b0906e"/>
    </linearGradient>
    <linearGradient id="piel-verde" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#9cc16a"/>
      <stop offset="55%" stop-color="#6f9a41"/>
      <stop offset="100%" stop-color="#3f6122"/>
    </linearGradient>
    <linearGradient id="piel-verde-osc" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#6f8f4a"/>
      <stop offset="55%" stop-color="#4a6b2c"/>
      <stop offset="100%" stop-color="#293f18"/>
    </linearGradient>
    <linearGradient id="piedra" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#9aa2ac"/>
      <stop offset="55%" stop-color="#6d757f"/>
      <stop offset="100%" stop-color="#42484f"/>
    </linearGradient>
    <linearGradient id="pelo" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#7a4a1e"/>
      <stop offset="100%" stop-color="#3f2610"/>
    </linearGradient>
    <linearGradient id="pelo-blanco" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#c3c8d0"/>
    </linearGradient>
    <linearGradient id="pelo-rojo" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#c9642a"/>
      <stop offset="100%" stop-color="#7a3312"/>
    </linearGradient>
    <linearGradient id="cuero" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#7a4f28"/>
      <stop offset="100%" stop-color="#3a2410"/>
    </linearGradient>
    <linearGradient id="acero" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#7f889b"/>
      <stop offset="50%" stop-color="#eef2f7"/>
      <stop offset="100%" stop-color="#646c7d"/>
    </linearGradient>
    <linearGradient id="acero-osc" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#2a2e36"/>
      <stop offset="50%" stop-color="#565d68"/>
      <stop offset="100%" stop-color="#1c2026"/>
    </linearGradient>
    <linearGradient id="tela-azul" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3a5bbf"/>
      <stop offset="100%" stop-color="#1f2f6a"/>
    </linearGradient>
    <linearGradient id="tela-verde" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3f7a4a"/>
      <stop offset="100%" stop-color="#204028"/>
    </linearGradient>
    <linearGradient id="tela-roja" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#a5342f"/>
      <stop offset="100%" stop-color="#5c1613"/>
    </linearGradient>
    <radialGradient id="oro" cx="40%" cy="32%" r="72%">
      <stop offset="0%" stop-color="#ffe9ad"/>
      <stop offset="55%" stop-color="#c99a3f"/>
      <stop offset="100%" stop-color="#6f4e18"/>
    </radialGradient>
    <radialGradient id="gema-azul" cx="40%" cy="30%" r="75%">
      <stop offset="0%" stop-color="#d8ecff"/>
      <stop offset="45%" stop-color="#5b8be0"/>
      <stop offset="100%" stop-color="#1f3f8a"/>
    </radialGradient>
    <filter id="sombra" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>
"""


def _lienzo(cuerpo: str) -> str:
    # El busto se dibuja centrado en x=0 (de ahí el translate a CENTRO_X) y con
    # un desplazamiento vertical para que la cabeza quede arriba y los hombros
    # lleguen casi al borde inferior (encuadre "busto grande").
    halo_cy = DESPLAZA_Y + 210
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" '
        f'viewBox="0 0 {ANCHO} {ALTO}">{DEFS}'
        f'<rect width="{ANCHO}" height="{ALTO}" fill="url(#fondo)"/>'
        f'<ellipse cx="{CENTRO_X}" cy="{halo_cy}" rx="250" ry="240" fill="url(#halo)"/>'
        f'<g filter="url(#sombra)" transform="translate({CENTRO_X} {DESPLAZA_Y})">{cuerpo}</g>'
        f'</svg>\n'
    )


def _cabeza(piel="url(#piel)", trazo="#5c3a20", ancho=78, arriba=110, barbilla=306):
    """Óvalo de cabeza centrado en x=0. Devuelve (svg, medidas)."""
    return (
        f'<path d="M -{ancho} 190 C -{ancho} {arriba} {ancho} {arriba} {ancho} 190 '
        f'C {ancho} 250 {ancho*0.6:.0f} {barbilla-6} 0 {barbilla} '
        f'C -{ancho*0.6:.0f} {barbilla-6} -{ancho} 250 -{ancho} 190 Z" '
        f'fill="{piel}" stroke="{trazo}" stroke-width="3"/>'
        f'<path d="M {ancho} 190 C {ancho} 250 {ancho*0.6:.0f} {barbilla-6} 0 {barbilla} '
        f'C {ancho*0.4:.0f} {barbilla-16} {ancho*0.58:.0f} 250 {ancho*0.6:.0f} 196 Z" '
        f'fill="#000000" opacity="0.14"/>'
    )


def _cuello(piel="url(#piel)", trazo="#5c3a20", y=292):
    return f'<rect x="-30" y="{y}" width="60" height="60" rx="14" fill="{piel}" stroke="{trazo}" stroke-width="2"/>'


def _ojos(cx=32, cy=196, r=9, color="#2a2a2a", brillo=True):
    s = (f'<ellipse cx="-{cx}" cy="{cy}" rx="{r}" ry="{r*0.78:.1f}" fill="{color}"/>'
         f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r*0.78:.1f}" fill="{color}"/>')
    if brillo:
        s += (f'<circle cx="-{cx-3}" cy="{cy-3}" r="2.4" fill="#ffffff" opacity="0.85"/>'
              f'<circle cx="{cx+3}" cy="{cy-3}" r="2.4" fill="#ffffff" opacity="0.85"/>')
    return s


def _cejas(y=176, color="#3f2610", fieras=True):
    if fieras:
        return (f'<path d="M -52 {y-2} L -16 {y+6}" stroke="{color}" stroke-width="8" stroke-linecap="round"/>'
                f'<path d="M 16 {y+6} L 52 {y-2}" stroke="{color}" stroke-width="8" stroke-linecap="round"/>')
    return (f'<path d="M -50 {y} L -18 {y-2}" stroke="{color}" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M 18 {y-2} L 50 {y}" stroke="{color}" stroke-width="6" stroke-linecap="round"/>')


def _nariz(y0=200, y1=232, w=8, color="#a06a44"):
    return f'<path d="M 0 {y0} L -{w} {y1} L {w} {y1} Z" fill="{color}" opacity="0.6"/>'


def _hombros(fill, trazo, y=322):
    return (f'<path d="M -150 500 C -150 384 -96 {y+8} -30 {y} L 30 {y} '
            f'C 96 {y+8} 150 384 150 500 Z" fill="{fill}" stroke="{trazo}" stroke-width="3"/>')


# ---------------------------------------------------------------------------
# HÉROES
# ---------------------------------------------------------------------------

def barbaro() -> str:
    c = _hombros("url(#piel)", "#5c3a20")
    # correa cruzada de cuero + hombrera de acero
    c += '<path d="M -140 470 L 110 330 L 140 360 L -110 500 Z" fill="url(#cuero)" stroke="#2e1a09" stroke-width="2"/>'
    c += ('<path d="M -150 360 C -180 330 -150 300 -108 306 C -84 322 -84 356 -104 372 Z" '
          'fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>')
    c += '<path d="M -60 360 C -40 392 -14 400 0 400 C 14 400 40 392 60 360" fill="none" stroke="#7a4a2c" stroke-width="4" opacity="0.6"/>'
    c += _cuello()
    c += _cabeza()
    # melena sólida
    c += ('<path d="M -86 214 C -100 150 -96 92 -60 62 C -34 40 34 40 60 62 '
          'C 96 92 100 150 86 214 C 80 176 70 158 58 150 L 58 132 C 40 120 -40 120 -58 132 '
          'L -58 150 C -70 158 -80 176 -86 214 Z" fill="url(#pelo)" stroke="#2e1a09" stroke-width="2.5" stroke-linejoin="round"/>')
    c += ('<g stroke="#5a3616" stroke-width="4" opacity="0.5" stroke-linecap="round" fill="none">'
          '<path d="M -60 90 C -66 130 -70 170 -72 200"/><path d="M 60 90 C 66 130 70 170 72 200"/></g>')
    c += _cejas()
    c += _ojos()
    c += _nariz()
    # barba
    c += ('<path d="M -46 236 C -40 286 -20 312 0 312 C 20 312 40 286 46 236 '
          'C 30 258 -30 258 -46 236 Z" fill="url(#pelo)" stroke="#2e1a09" stroke-width="2"/>')
    c += '<path d="M -16 246 L 16 246" stroke="#5c2a20" stroke-width="3.5" stroke-linecap="round"/>'
    c += '<path d="M -22 236 C -12 242 -4 242 0 240 C 4 242 12 242 22 236" fill="none" stroke="#3f2610" stroke-width="5" stroke-linecap="round"/>'
    # diadema
    c += '<rect x="-80" y="150" width="160" height="18" rx="8" fill="url(#cuero)" stroke="#2e1a09" stroke-width="2"/>'
    c += '<circle cx="0" cy="159" r="9" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    return _lienzo(c)


def enano() -> str:
    c = _hombros("url(#tela-verde)", "#204028")
    # placas de armadura en los hombros
    c += ('<path d="M -150 366 C -170 336 -140 314 -104 320 C -84 336 -86 366 -104 380 Z" '
          'fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>')
    c += ('<path d="M 150 366 C 170 336 140 314 104 320 C 84 336 86 366 104 380 Z" '
          'fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>')
    c += _cuello()
    # cabeza más ancha y baja
    c += _cabeza(ancho=82, arriba=120, barbilla=300)
    # gran barba pelirroja trenzada (rasgo principal del enano)
    c += ('<path d="M -70 210 C -84 300 -40 400 0 400 C 40 400 84 300 70 210 '
          'C 50 250 -50 250 -70 210 Z" fill="url(#pelo-rojo)" stroke="#5a2410" stroke-width="2.5"/>')
    # trenzas
    c += ('<g stroke="#7a3312" stroke-width="4" opacity="0.6" fill="none" stroke-linecap="round">'
          '<path d="M -30 300 C -34 330 -32 360 -28 384"/><path d="M 30 300 C 34 330 32 360 28 384"/>'
          '<path d="M 0 300 L 0 396"/></g>')
    # anillos dorados en las trenzas
    c += '<rect x="-38" y="372" width="20" height="10" rx="4" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    c += '<rect x="18" y="372" width="20" height="10" rx="4" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    # yelmo de acero con cuernos cortos
    c += ('<path d="M -84 176 C -84 108 84 108 84 176 L 60 176 C 60 150 -60 150 -60 176 Z" '
          'fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>')
    c += '<rect x="-84" y="168" width="168" height="18" rx="6" fill="url(#acero-osc)" stroke="#1c2026" stroke-width="2"/>'
    # cuernos
    c += ('<path d="M -84 172 C -120 160 -128 130 -120 112 C -108 132 -96 150 -76 162 Z" '
          'fill="#e8e2d0" stroke="#8a8272" stroke-width="2"/>')
    c += ('<path d="M 84 172 C 120 160 128 130 120 112 C 108 132 96 150 76 162 Z" '
          'fill="#e8e2d0" stroke="#8a8272" stroke-width="2"/>')
    c += '<circle cx="0" cy="177" r="8" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    c += _cejas(y=196, color="#7a3312")
    c += _ojos(cy=214)
    c += _nariz(y0=222, y1=246, w=10)
    return _lienzo(c)


def elfo() -> str:
    c = _hombros("url(#tela-verde)", "#204028")
    # capa con broche
    c += '<path d="M -150 500 C -150 400 -120 350 -70 336 L -70 500 Z" fill="url(#tela-verde)" stroke="#183020" stroke-width="2"/>'
    c += '<circle cx="-58" cy="352" r="12" fill="url(#oro)" stroke="#5c4413" stroke-width="1.5"/>'
    c += _cuello(piel="url(#piel-palida)", trazo="#a8886a")
    c += _cabeza(piel="url(#piel-palida)", trazo="#a8886a", ancho=72, arriba=118, barbilla=304)
    # orejas puntiagudas
    c += ('<path d="M -72 190 C -104 176 -112 150 -108 132 C -94 150 -80 168 -66 176 Z" '
          'fill="url(#piel-palida)" stroke="#a8886a" stroke-width="2.5"/>')
    c += ('<path d="M 72 190 C 104 176 112 150 108 132 C 94 150 80 168 66 176 Z" '
          'fill="url(#piel-palida)" stroke="#a8886a" stroke-width="2.5"/>')
    # cabello largo rubio liso
    c += ('<path d="M -80 210 C -96 150 -92 96 -60 70 C -34 48 34 48 60 70 '
          'C 92 96 96 150 80 210 L 66 210 C 74 150 66 118 54 108 '
          'C 40 120 -40 120 -54 108 C -66 118 -74 150 -66 210 Z" '
          'fill="#e8cf72" stroke="#b89a3a" stroke-width="2.5" stroke-linejoin="round"/>')
    c += ('<g stroke="#c9ab48" stroke-width="3" opacity="0.5" fill="none" stroke-linecap="round">'
          '<path d="M -70 110 C -78 150 -80 180 -78 206"/><path d="M 70 110 C 78 150 80 180 78 206"/></g>')
    # circlet élfico
    c += '<path d="M -68 132 C -30 118 30 118 68 132" fill="none" stroke="url(#oro)" stroke-width="6" stroke-linecap="round"/>'
    c += '<path d="M 0 122 l 10 14 l -10 8 l -10 -8 Z" fill="url(#gema-azul)" stroke="#1f3f8a" stroke-width="1.5"/>'
    c += _cejas(y=178, color="#b89a3a", fieras=False)
    c += _ojos(cx=30, cy=194, color="#2f6b4a")
    c += _nariz(y0=198, y1=228, w=7, color="#c8a888")
    c += '<path d="M -14 248 C -4 252 4 252 14 248" fill="none" stroke="#a86a5c" stroke-width="3" stroke-linecap="round"/>'
    return _lienzo(c)


def mago() -> str:
    c = _hombros("url(#tela-azul)", "#1a2550")
    # estrellas en la túnica
    c += ('<g fill="url(#oro)" opacity="0.85">'
          '<polygon points="-96,430 -90,446 -74,446 -87,456 -82,472 -96,462 -110,472 -105,456 -118,446 -102,446"/>'
          '<polygon points="96,450 101,463 114,463 104,471 108,484 96,476 84,484 88,471 78,463 91,463"/></g>')
    c += _cuello(piel="url(#piel-palida)", trazo="#a8886a")
    c += _cabeza(piel="url(#piel-palida)", trazo="#a8886a", ancho=70, arriba=150, barbilla=300)
    # larga barba blanca (rasgo principal)
    c += ('<path d="M -60 220 C -80 340 -30 470 0 470 C 30 470 80 340 60 220 '
          'C 42 262 -42 262 -60 220 Z" fill="url(#pelo-blanco)" stroke="#b7bcc6" stroke-width="2.5"/>')
    c += ('<g stroke="#c3c8d0" stroke-width="3" opacity="0.6" fill="none" stroke-linecap="round">'
          '<path d="M -24 300 C -28 360 -24 420 -14 456"/><path d="M 24 300 C 28 360 24 420 14 456"/>'
          '<path d="M 0 300 L 0 466"/></g>')
    # bigote
    c += '<path d="M -30 236 C -16 248 -4 248 0 244 C 4 248 16 248 30 236" fill="none" stroke="#e8ecf2" stroke-width="7" stroke-linecap="round"/>'
    c += _cejas(y=190, color="#d8dce4", fieras=False)
    c += _ojos(cx=28, cy=204, r=8)
    c += _nariz(y0=208, y1=236, w=8, color="#c8a888")
    # sombrero puntiagudo de mago
    c += ('<path d="M -92 156 C -70 150 70 150 92 156 C 84 130 40 120 0 -20 '
          'C -40 120 -84 130 -92 156 Z" fill="url(#tela-azul)" stroke="#141d3c" stroke-width="3" stroke-linejoin="round"/>')
    # ala del sombrero
    c += '<path d="M -100 158 C -40 172 40 172 100 158 C 40 148 -40 148 -100 158 Z" fill="url(#tela-azul)" stroke="#141d3c" stroke-width="2"/>'
    # banda y estrella del sombrero
    c += '<path d="M -74 128 C -30 138 30 138 66 122" fill="none" stroke="url(#oro)" stroke-width="7"/>'
    c += '<polygon points="0,44 9,68 34,68 14,84 22,110 0,94 -22,110 -14,84 -34,68 -9,68" fill="url(#oro)"/>'
    # punta caída del gorro
    c += '<path d="M 0 -20 C 20 6 40 20 58 18 C 44 34 22 34 6 22 Z" fill="url(#tela-azul)" stroke="#141d3c" stroke-width="2.5"/>'
    return _lienzo(c)


# ---------------------------------------------------------------------------
# MONSTRUOS
# ---------------------------------------------------------------------------

def trasgo() -> str:
    c = _hombros("url(#cuero)", "#2e1a09", y=330)
    c += _cuello(piel="url(#piel-verde)", trazo="#3f6122")
    # cabeza pequeña y puntiaguda
    c += _cabeza(piel="url(#piel-verde)", trazo="#3f6122", ancho=64, arriba=150, barbilla=300)
    # orejas enormes puntiagudas (rasgo del trasgo/goblin)
    c += ('<path d="M -60 176 C -128 150 -150 100 -150 78 C -120 110 -90 140 -56 156 Z" '
          'fill="url(#piel-verde)" stroke="#3f6122" stroke-width="2.5"/>')
    c += ('<path d="M 60 176 C 128 150 150 100 150 78 C 120 110 90 140 56 156 Z" '
          'fill="url(#piel-verde)" stroke="#3f6122" stroke-width="2.5"/>')
    c += '<path d="M -120 96 C -100 120 -80 138 -60 150" fill="none" stroke="#2f4a1a" stroke-width="3" opacity="0.5"/>'
    c += '<path d="M 120 96 C 100 120 80 138 60 150" fill="none" stroke="#2f4a1a" stroke-width="3" opacity="0.5"/>'
    # capucha andrajosa
    c += '<path d="M -64 168 C -50 150 50 150 64 168 C 40 154 -40 154 -64 168 Z" fill="url(#cuero)" stroke="#2e1a09" stroke-width="2"/>'
    # ojos amarillos amenazantes
    c += _cejas(y=190, color="#2f4a1a")
    c += _ojos(cx=28, cy=206, r=10, color="#e8c020")
    c += '<ellipse cx="-28" cy="206" rx="4" ry="7" fill="#1a1a00"/><ellipse cx="28" cy="206" rx="4" ry="7" fill="#1a1a00"/>'
    # nariz ganchuda
    c += '<path d="M 0 210 C 8 226 10 240 0 248 C -6 242 -6 232 -4 224 Z" fill="#4a6b2c" stroke="#2f4a1a" stroke-width="1.5"/>'
    # boca con dientes
    c += '<path d="M -22 264 C -8 274 8 274 22 264 L 16 272 L 8 266 L 0 274 L -8 266 L -16 272 Z" fill="#20140a" stroke="#2f4a1a" stroke-width="1.5"/>'
    c += '<polygon points="-16,264 -12,274 -8,264" fill="#e8e2d0"/><polygon points="8,264 12,274 16,264" fill="#e8e2d0"/>'
    return _lienzo(c)


def orco() -> str:
    c = _hombros("url(#acero-osc)", "#1c2026", y=328)
    # hombreras claveteadas
    c += ('<path d="M -150 360 C -178 326 -144 300 -104 308 C -82 326 -84 360 -104 376 Z" '
          'fill="url(#acero-osc)" stroke="#1c2026" stroke-width="3"/>')
    c += '<circle cx="-128" cy="336" r="5" fill="#8a919c"/><circle cx="-110" cy="356" r="5" fill="#8a919c"/>'
    c += _cuello(piel="url(#piel-verde-osc)", trazo="#293f18", y=296)
    # cabeza grande y cuadrada
    c += _cabeza(piel="url(#piel-verde-osc)", trazo="#293f18", ancho=86, arriba=120, barbilla=300)
    # orejas puntiagudas medianas
    c += '<path d="M -84 186 C -116 172 -122 150 -118 136 C -104 152 -92 168 -78 176 Z" fill="url(#piel-verde-osc)" stroke="#293f18" stroke-width="2.5"/>'
    c += '<path d="M 84 186 C 116 172 122 150 118 136 C 104 152 92 168 78 176 Z" fill="url(#piel-verde-osc)" stroke="#293f18" stroke-width="2.5"/>'
    # ceño prominente
    c += '<path d="M -70 168 C -30 156 30 156 70 168 L 70 182 C 30 172 -30 172 -70 182 Z" fill="#293f18" opacity="0.6"/>'
    c += _cejas(y=182, color="#1f3010")
    c += _ojos(cx=34, cy=200, r=9, color="#e83b20")
    # nariz chata ancha
    c += '<path d="M -12 210 C -18 232 -8 244 0 244 C 8 244 18 232 12 210 Z" fill="#3a5522" stroke="#293f18" stroke-width="1.5"/>'
    c += '<ellipse cx="-6" cy="236" rx="3" ry="5" fill="#1a2a0e"/><ellipse cx="6" cy="236" rx="3" ry="5" fill="#1a2a0e"/>'
    # boca con grandes colmillos hacia arriba
    c += '<path d="M -34 262 C -12 276 12 276 34 262 L 34 270 C 12 282 -12 282 -34 270 Z" fill="#20140a" stroke="#293f18" stroke-width="1.5"/>'
    c += '<polygon points="-30,268 -22,238 -14,268" fill="#e8e2d0" stroke="#b8b2a0" stroke-width="1.5"/>'
    c += '<polygon points="30,268 22,238 14,268" fill="#e8e2d0" stroke="#b8b2a0" stroke-width="1.5"/>'
    return _lienzo(c)


def fimir() -> str:
    c = _hombros("url(#piel-verde-osc)", "#1f3010", y=330)
    # piel escamosa reptiliana
    c += ('<g fill="#3a5522" opacity="0.4">'
          '<circle cx="-90" cy="420" r="10"/><circle cx="-60" cy="450" r="10"/><circle cx="60" cy="440" r="10"/>'
          '<circle cx="96" cy="410" r="10"/><circle cx="0" cy="460" r="10"/></g>')
    c += _cuello(piel="url(#piel-verde-osc)", trazo="#1f3010", y=296)
    # cabeza reptiliana alargada
    c += ('<path d="M -76 196 C -76 120 76 120 76 196 C 76 258 44 306 0 312 '
          'C -44 306 -76 258 -76 196 Z" fill="url(#piel-verde-osc)" stroke="#1f3010" stroke-width="3"/>')
    # cresta de púas en la cabeza
    c += ('<g fill="#2f4a1a" stroke="#1f3010" stroke-width="1.5">'
          '<polygon points="0,128 -12,150 12,150"/>'
          '<polygon points="-30,138 -40,162 -18,158"/>'
          '<polygon points="30,138 40,162 18,158"/></g>')
    # UN solo ojo central (el Fimir es cíclope)
    c += '<ellipse cx="0" cy="196" rx="30" ry="26" fill="#e8e2c0" stroke="#1f3010" stroke-width="3"/>'
    c += '<ellipse cx="0" cy="198" rx="12" ry="18" fill="#c02a1a"/>'
    c += '<ellipse cx="0" cy="198" rx="4" ry="12" fill="#1a0a08"/>'
    c += '<circle cx="-8" cy="188" r="4" fill="#ffffff" opacity="0.8"/>'
    # ceja/pliegue sobre el ojo
    c += '<path d="M -34 166 C -14 156 14 156 34 166" fill="none" stroke="#1f3010" stroke-width="6" stroke-linecap="round"/>'
    # hocico con dientes
    c += '<path d="M -30 250 C -14 244 14 244 30 250 C 20 270 -20 270 -30 250 Z" fill="#2f4a1a" stroke="#1f3010" stroke-width="2"/>'
    c += '<path d="M -24 254 L -18 266 L -12 254 L -6 266 L 0 254 L 6 266 L 12 254 L 18 266 L 24 254" fill="none" stroke="#e8e2d0" stroke-width="3"/>'
    # cola/aletas laterales sugeridas
    c += '<path d="M -76 200 C -104 196 -116 210 -112 226 C -96 216 -84 212 -74 214 Z" fill="url(#piel-verde-osc)" stroke="#1f3010" stroke-width="2"/>'
    c += '<path d="M 76 200 C 104 196 116 210 112 226 C 96 216 84 212 74 214 Z" fill="url(#piel-verde-osc)" stroke="#1f3010" stroke-width="2"/>'
    return _lienzo(c)


def guerrero_del_caos() -> str:
    c = _hombros("url(#acero-osc)", "#141014", y=326)
    # hombreras de placas negras con pinchos
    for sgn in (-1, 1):
        cx = sgn * 120
        c += (f'<path d="M {cx-40*sgn} 356 C {cx-52*sgn} 320 {cx+6*sgn} 300 {cx+28*sgn} 330 '
              f'C {cx+32*sgn} 350 {cx+18*sgn} 372 {cx-8*sgn} 372 Z" '
              'fill="url(#acero-osc)" stroke="#0e0a0e" stroke-width="3"/>')
        c += f'<polygon points="{cx},300 {cx-8*sgn},322 {cx+8*sgn},322" fill="#8a919c" stroke="#0e0a0e" stroke-width="1.5"/>'
    c += _cuello(piel="#3a2e2e", trazo="#0e0a0e")
    # yelmo cerrado negro (sin cara visible, solo ranura de ojos brillante)
    c += ('<path d="M -80 200 C -80 118 80 118 80 200 C 80 250 60 290 0 300 '
          'C -60 290 -80 250 -80 200 Z" fill="url(#acero-osc)" stroke="#0e0a0e" stroke-width="3"/>')
    c += '<path d="M 80 200 C 80 250 60 290 0 300 C 34 288 50 250 52 200 Z" fill="#000000" opacity="0.3"/>'
    # reflejo del metal
    c += '<path d="M -48 150 C -64 180 -68 220 -64 256" fill="none" stroke="#8a919c" stroke-width="5" opacity="0.5" stroke-linecap="round"/>'
    # ranura de los ojos con brillo rojo
    c += '<path d="M -56 206 L -14 200 L -14 216 L -56 220 Z" fill="#0a0708"/>'
    c += '<path d="M 56 206 L 14 200 L 14 216 L 56 220 Z" fill="#0a0708"/>'
    c += '<circle cx="-36" cy="210" r="7" fill="#ff2a20"/><circle cx="36" cy="210" r="7" fill="#ff2a20"/>'
    c += '<circle cx="-36" cy="210" r="14" fill="#ff2a20" opacity="0.3"/><circle cx="36" cy="210" r="14" fill="#ff2a20" opacity="0.3"/>'
    # respiradero/rejilla de la boca
    c += ('<g stroke="#0a0708" stroke-width="3">'
          '<line x1="-20" y1="252" x2="-20" y2="276"/><line x1="0" y1="254" x2="0" y2="280"/>'
          '<line x1="20" y1="252" x2="20" y2="276"/></g>')
    # grandes cuernos curvos (rasgo del Caos)
    c += ('<path d="M -70 150 C -120 120 -140 60 -128 20 C -108 60 -96 100 -60 128 Z" '
          'fill="url(#acero-osc)" stroke="#0e0a0e" stroke-width="3" stroke-linejoin="round"/>')
    c += ('<path d="M 70 150 C 120 120 140 60 128 20 C 108 60 96 100 60 128 Z" '
          'fill="url(#acero-osc)" stroke="#0e0a0e" stroke-width="3" stroke-linejoin="round"/>')
    c += '<path d="M -76 140 C -110 116 -126 74 -122 40" fill="none" stroke="#8a919c" stroke-width="3" opacity="0.4"/>'
    c += '<path d="M 76 140 C 110 116 126 74 122 40" fill="none" stroke="#8a919c" stroke-width="3" opacity="0.4"/>'
    # runa del caos en la frente
    c += '<circle cx="0" cy="170" r="12" fill="none" stroke="#ff2a20" stroke-width="3" opacity="0.8"/>'
    c += '<path d="M 0 160 L 0 180 M -9 165 L 9 175 M 9 165 L -9 175" stroke="#ff2a20" stroke-width="2.5" opacity="0.8"/>'
    return _lienzo(c)


def gargola() -> str:
    c = _hombros("url(#piedra)", "#33383e", y=328)
    # textura de piedra en los hombros
    c += ('<g stroke="#4a5058" stroke-width="3" opacity="0.5" fill="none">'
          '<path d="M -110 400 L -80 410"/><path d="M 70 420 L 110 412"/><path d="M -40 450 L 30 452"/></g>')
    # grandes alas de piedra detrás
    c += ('<path d="M -70 340 C -180 260 -210 180 -196 150 C -170 200 -150 230 -120 250 '
          'C -150 200 -160 160 -152 140 C -128 190 -108 230 -74 300 Z" '
          'fill="url(#piedra)" stroke="#33383e" stroke-width="3" stroke-linejoin="round" opacity="0.9"/>')
    c += ('<path d="M 70 340 C 180 260 210 180 196 150 C 170 200 150 230 120 250 '
          'C 150 200 160 160 152 140 C 128 190 108 230 74 300 Z" '
          'fill="url(#piedra)" stroke="#33383e" stroke-width="3" stroke-linejoin="round" opacity="0.9"/>')
    c += _cuello(piel="url(#piedra)", trazo="#33383e")
    # cabeza demoníaca de piedra
    c += ('<path d="M -80 196 C -80 124 80 124 80 196 C 80 252 48 300 0 306 '
          'C -48 300 -80 252 -80 196 Z" fill="url(#piedra)" stroke="#33383e" stroke-width="3"/>')
    c += '<path d="M 80 196 C 80 252 48 300 0 306 C 34 294 50 252 52 198 Z" fill="#000000" opacity="0.2"/>'
    # cuernos de carnero
    c += ('<path d="M -60 150 C -104 130 -112 92 -96 72 C -96 104 -78 128 -50 140 Z" '
          'fill="url(#piedra)" stroke="#33383e" stroke-width="2.5"/>')
    c += ('<path d="M 60 150 C 104 130 112 92 96 72 C 96 104 78 128 50 140 Z" '
          'fill="url(#piedra)" stroke="#33383e" stroke-width="2.5"/>')
    # orejas puntiagudas
    c += '<path d="M -78 186 C -100 170 -104 150 -100 138 C -88 152 -78 166 -68 174 Z" fill="url(#piedra)" stroke="#33383e" stroke-width="2"/>'
    c += '<path d="M 78 186 C 100 170 104 150 100 138 C 88 152 78 166 68 174 Z" fill="url(#piedra)" stroke="#33383e" stroke-width="2"/>'
    # ceño pétreo
    c += '<path d="M -58 176 L -16 184" stroke="#2a2e33" stroke-width="8" stroke-linecap="round"/>'
    c += '<path d="M 16 184 L 58 176" stroke="#2a2e33" stroke-width="8" stroke-linecap="round"/>'
    # ojos vacíos brillando
    c += '<ellipse cx="-32" cy="200" rx="12" ry="10" fill="#0e1013"/><ellipse cx="32" cy="200" rx="12" ry="10" fill="#0e1013"/>'
    c += '<circle cx="-32" cy="200" r="5" fill="#c9d6e8"/><circle cx="32" cy="200" r="5" fill="#c9d6e8"/>'
    # nariz ancha y hocico
    c += '<path d="M 0 210 C 10 228 12 242 0 250 C -8 244 -8 234 -6 224 Z" fill="#4a5058" stroke="#2a2e33" stroke-width="1.5"/>'
    # boca gruñona con colmillos
    c += '<path d="M -34 268 C -12 280 12 280 34 268 C 22 288 -22 288 -34 268 Z" fill="#0e1013" stroke="#2a2e33" stroke-width="2"/>'
    c += '<polygon points="-26,270 -20,284 -14,270" fill="#c9d6e8"/><polygon points="26,270 20,284 14,270" fill="#c9d6e8"/>'
    c += '<polygon points="-10,276 -6,266 -2,276" fill="#c9d6e8"/><polygon points="10,276 6,266 2,276" fill="#c9d6e8"/>'
    return _lienzo(c)


OBJETOS = {
    "Bárbaro": barbaro,
    "Enano": enano,
    "Elfo": elfo,
    "Mago": mago,
    "Trasgo": trasgo,
    "Orco": orco,
    "Fimir": fimir,
    "Guerrero del Caos": guerrero_del_caos,
    "Gárgola": gargola,
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
            print(f"SVG  {ruta_svg.name}")
            continue
        ruta_png = ARTE_DIR / f"{slug}.png"
        _rasterizar(svg, ruta_png)
        print(f"OK   {nombre}  ->  {ruta_png.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="Genera los retratos de héroes y monstruos de HeroQuest")
    p.add_argument("--solo", default=None, help="Genera solo un personaje por su nombre exacto")
    p.add_argument("--svg-solo", action="store_true", help="Genera solo los SVG, sin rasterizar a PNG")
    args = p.parse_args()
    generar(args.solo, args.svg_solo)


if __name__ == "__main__":
    main()

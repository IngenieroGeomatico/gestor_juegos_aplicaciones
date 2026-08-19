# -*- coding: utf-8 -*-
"""Genera los fondos de reverso de las cartas de HeroQuest de forma reproducible.

Cada categoría de carta (equipo, héroe, enemigo, tesoro, magia) tiene una escena
ambiental temática que se dibuja como SVG vectorial y se rasteriza a PNG con
`resvg` (la misma librería que `render_carta.py`).

- Los SVG (fuente de verdad, editables) se guardan en `sources/arte_fondos_svg/`.
- Los PNG finales se guardan en `sources/arte_fondos/`, listos para usarse como
  fondo del reverso con `carta_item.py --fondo_verso <fichero.png>`.

Sobre esos fondos la carta dibuja ENCIMA su marco, el banner "HeroQuest" y la
leyenda inferior, así que las escenas reservan bandas oscuras arriba y abajo para
que el texto se lea bien. El formato es 1000×1400 (proporción 63×88 de la carta).

Uso:
    uv run juegos/heroquest/scripts/generar_fondos.py             # genera todos
    uv run juegos/heroquest/scripts/generar_fondos.py --solo equipo
    uv run juegos/heroquest/scripts/generar_fondos.py --svg-solo  # solo SVG
"""

from __future__ import annotations

import argparse
from pathlib import Path

from arte_comun import rasterizar as _rasterizar_png

FONDOS_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_fondos"
FONDOS_SVG_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_fondos_svg"

ANCHO, ALTO = 1000, 1400


# ---------------------------------------------------------------------------
# Bloques comunes: degradados de ambiente y materiales.
# ---------------------------------------------------------------------------

def _defs(luz: str, piedra_top: str, piedra_mid: str, piedra_bot: str) -> str:
    """Defs con una tonalidad de piedra y de luz por escena."""
    return f"""
  <defs>
    <linearGradient id="piedra" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{piedra_top}"/>
      <stop offset="50%" stop-color="{piedra_mid}"/>
      <stop offset="100%" stop-color="{piedra_bot}"/>
    </linearGradient>
    <radialGradient id="luz" cx="50%" cy="52%" r="55%">
      <stop offset="0%" stop-color="{luz}" stop-opacity="0.45"/>
      <stop offset="45%" stop-color="{luz}" stop-opacity="0.16"/>
      <stop offset="100%" stop-color="{luz}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="vineta" cx="50%" cy="50%" r="72%">
      <stop offset="55%" stop-color="#000000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.72"/>
    </radialGradient>
    <linearGradient id="madera" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#4a2f16"/>
      <stop offset="50%" stop-color="#7a4f28"/>
      <stop offset="100%" stop-color="#3a2410"/>
    </linearGradient>
    <linearGradient id="acero" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#5a626f"/>
      <stop offset="45%" stop-color="#aab2c0"/>
      <stop offset="55%" stop-color="#c8cfdb"/>
      <stop offset="100%" stop-color="#454b57"/>
    </linearGradient>
    <radialGradient id="llama" cx="50%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#fff3c0"/>
      <stop offset="40%" stop-color="#ffb03a"/>
      <stop offset="100%" stop-color="#e0521a" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="oro" cx="40%" cy="32%" r="72%">
      <stop offset="0%" stop-color="#ffe9ad"/>
      <stop offset="55%" stop-color="#c99a3f"/>
      <stop offset="100%" stop-color="#6f4e18"/>
    </radialGradient>
    <radialGradient id="gema" cx="40%" cy="32%" r="75%">
      <stop offset="0%" stop-color="#d8ecff"/>
      <stop offset="45%" stop-color="#5b8be0"/>
      <stop offset="100%" stop-color="#1f3f8a"/>
    </radialGradient>
    <linearGradient id="banda" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#000000" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
    </linearGradient>
  </defs>
"""


def _muro(juntas: str = "#160f0a") -> str:
    """Muro de piedra con sillería y vetas de textura."""
    return (
        f'<rect width="{ANCHO}" height="{ALTO}" fill="url(#piedra)"/>'
        f'<g stroke="{juntas}" stroke-width="4" opacity="0.55">'
        '<line x1="0" y1="300" x2="1000" y2="300"/>'
        '<line x1="0" y1="560" x2="1000" y2="560"/>'
        '<line x1="0" y1="820" x2="1000" y2="820"/>'
        '<line x1="0" y1="1080" x2="1000" y2="1080"/>'
        '<line x1="250" y1="300" x2="250" y2="560"/>'
        '<line x1="620" y1="300" x2="620" y2="560"/>'
        '<line x1="130" y1="560" x2="130" y2="820"/>'
        '<line x1="500" y1="560" x2="500" y2="820"/>'
        '<line x1="820" y1="560" x2="820" y2="820"/>'
        '<line x1="360" y1="820" x2="360" y2="1080"/>'
        '<line x1="700" y1="820" x2="700" y2="1080"/>'
        '</g>'
        '<g stroke="#5a4128" stroke-width="2" opacity="0.22">'
        '<line x1="60" y1="380" x2="200" y2="378"/>'
        '<line x1="700" y1="420" x2="880" y2="424"/>'
        '<line x1="120" y1="640" x2="300" y2="642"/>'
        '<line x1="560" y1="700" x2="760" y2="698"/>'
        '<line x1="300" y1="940" x2="520" y2="944"/>'
        '<line x1="640" y1="1000" x2="860" y2="998"/>'
        '</g>'
    )


def _antorcha(x: float, y: float) -> str:
    return (
        f'<g transform="translate({x} {y})">'
        '<rect x="-10" y="0" width="20" height="180" rx="6" fill="url(#madera)" stroke="#211307" stroke-width="2"/>'
        '<ellipse cx="0" cy="-30" rx="46" ry="70" fill="url(#llama)"/>'
        '<path d="M 0 -78 C -14 -46 -20 -20 0 -6 C 20 -20 14 -46 0 -78 Z" fill="#ffd86a"/>'
        '</g>'
    )


def _luz() -> str:
    return f'<ellipse cx="500" cy="720" rx="520" ry="560" fill="url(#luz)"/>'


def _bandas() -> str:
    """Bandas oscuras arriba/abajo para que el banner y la leyenda se lean."""
    return (
        f'<rect x="0" y="0" width="{ANCHO}" height="330" fill="url(#banda)"/>'
        f'<rect x="0" y="0" width="{ANCHO}" height="330" fill="url(#banda)" '
        f'transform="translate(0 {ALTO}) scale(1 -1)"/>'
    )


def _vineta() -> str:
    return f'<rect width="{ANCHO}" height="{ALTO}" fill="url(#vineta)"/>'


def _espada(rot: float) -> str:
    """Espada estilizada (silueta metálica) inclinada `rot` grados."""
    return (
        f'<g transform="rotate({rot})">'
        '<rect x="-14" y="-300" width="28" height="470" rx="6" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>'
        '<polygon points="0,-330 14,-300 -14,-300" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>'
        '<rect x="-70" y="168" width="140" height="24" rx="10" fill="url(#madera)" stroke="#211307" stroke-width="2"/>'
        '<rect x="-18" y="190" width="36" height="90" rx="8" fill="#3a2410" stroke="#211307" stroke-width="2"/>'
        '<circle cx="0" cy="288" r="18" fill="url(#madera)" stroke="#211307" stroke-width="2"/>'
        '</g>'
    )


def _lienzo(defs: str, cuerpo: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" '
        f'viewBox="0 0 {ANCHO} {ALTO}">{defs}{cuerpo}</svg>\n'
    )


# ---------------------------------------------------------------------------
# Escenas por categoría
# ---------------------------------------------------------------------------

def equipo() -> str:
    """Armería: panoplia de armas colgadas, escudo, antorchas."""
    defs = _defs("#ffcf8a", "#2a2018", "#3a2c20", "#241a12")
    c = _muro()
    c += _luz()
    # Estante de madera
    c += ('<rect x="120" y="1040" width="760" height="34" rx="6" fill="url(#madera)" stroke="#211307" stroke-width="3"/>'
          '<rect x="120" y="1044" width="760" height="8" fill="#a06a34" opacity="0.35"/>'
          '<rect x="150" y="1074" width="26" height="60" fill="url(#madera)" stroke="#211307" stroke-width="2"/>'
          '<rect x="824" y="1074" width="26" height="60" fill="url(#madera)" stroke="#211307" stroke-width="2"/>')
    # Escudo redondo al fondo
    c += ('<g transform="translate(500 560)" opacity="0.55">'
          '<circle cx="0" cy="0" r="120" fill="url(#acero)" stroke="#1c2026" stroke-width="6"/>'
          '<circle cx="0" cy="0" r="34" fill="#3a4048" stroke="#20242b" stroke-width="4"/>'
          '<g stroke="#20242b" stroke-width="4" opacity="0.6">'
          '<line x1="0" y1="-120" x2="0" y2="120"/><line x1="-120" y1="0" x2="120" y2="0"/></g></g>')
    # Espadas cruzadas
    c += f'<g opacity="0.9" transform="translate(500 720)">{_espada(24)}{_espada(-24)}</g>'
    # Hacha y lanza apoyadas
    c += ('<g transform="translate(250 830) rotate(-12)" opacity="0.8">'
          '<rect x="-8" y="-40" width="16" height="300" rx="6" fill="url(#madera)" stroke="#211307" stroke-width="2"/>'
          '<path d="M -8 -40 C -70 -30 -96 10 -96 40 C -60 44 -20 40 -8 30 Z" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/></g>')
    c += ('<g transform="translate(770 780) rotate(10)" opacity="0.8">'
          '<rect x="-6" y="-120" width="12" height="380" rx="5" fill="url(#madera)" stroke="#211307" stroke-width="2"/>'
          '<polygon points="0,-180 22,-120 -22,-120" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/></g>')
    c += _antorcha(70, 620) + _antorcha(930, 620)
    c += _bandas() + _vineta()
    return _lienzo(defs, c)


def tesoro() -> str:
    """Cámara del tesoro: cofre rebosante de oro, monedas, gemas."""
    defs = _defs("#ffd76a", "#241d10", "#382a12", "#1e160a")
    c = _muro()
    c += _luz()
    # Montón de monedas de oro bajo el cofre
    c += '<ellipse cx="500" cy="1030" rx="360" ry="90" fill="#7a5410" opacity="0.6"/>'
    monedas = ""
    import math
    puntos = [(360, 1000, 22), (440, 1030, 26), (540, 1020, 24), (620, 1000, 20),
              (400, 1060, 20), (500, 1058, 24), (600, 1055, 22), (300, 1035, 18),
              (700, 1030, 18), (470, 990, 16), (560, 985, 16)]
    for (x, y, r) in puntos:
        monedas += (f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r*0.5:.1f}" fill="url(#oro)" '
                    f'stroke="#5c4413" stroke-width="1.5"/>')
    c += monedas
    # Cofre abierto
    c += ('<g transform="translate(500 780)">'
          # tapa abierta
          '<path d="M -180 -30 L 180 -30 L 150 -150 L -150 -150 Z" fill="#5a3a1c" stroke="#211307" stroke-width="4"/>'
          '<path d="M -150 -150 L 150 -150 L 130 -120 L -130 -120 Z" fill="#7a4f28" opacity="0.6"/>'
          # cuerpo
          '<rect x="-180" y="-30" width="360" height="180" rx="12" fill="url(#madera)" stroke="#211307" stroke-width="5"/>'
          # herrajes dorados
          '<rect x="-180" y="10" width="360" height="20" fill="url(#oro)" opacity="0.8"/>'
          '<rect x="-30" y="-30" width="60" height="180" fill="url(#oro)" opacity="0.7"/>'
          '<circle cx="0" cy="60" r="20" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/>'
          # brillo interior (oro dentro del cofre)
          '<ellipse cx="0" cy="-30" rx="150" ry="30" fill="#ffdf8a" opacity="0.5"/>'
          '</g>')
    # Gemas destacadas
    c += ('<circle cx="410" cy="1000" r="16" fill="url(#gema)" stroke="#1f2f5a" stroke-width="2"/>'
          '<ellipse cx="600" cy="1010" rx="15" ry="15" fill="#e0555b" stroke="#8a1f2a" stroke-width="2"/>'
          '<ellipse cx="520" cy="1035" rx="14" ry="14" fill="#4fbf7a" stroke="#1a6b3a" stroke-width="2"/>')
    c += _antorcha(70, 560) + _antorcha(930, 560)
    c += _bandas() + _vineta()
    return _lienzo(defs, c)


def enemigo() -> str:
    """Mazmorra tenebrosa: reja, calavera, ojos rojos en la oscuridad."""
    defs = _defs("#8fd0ff", "#161a20", "#20262e", "#0e1116")
    c = _muro(juntas="#0a0d12")
    # Luz fría tenue
    c += '<ellipse cx="500" cy="720" rx="520" ry="560" fill="url(#luz)"/>'
    # Reja de mazmorra al fondo
    c += '<g stroke="#20262e" stroke-width="14" opacity="0.7">'
    for x in range(260, 780, 90):
        c += f'<line x1="{x}" y1="360" x2="{x}" y2="1000"/>'
    c += '<line x1="240" y1="440" x2="760" y2="440"/><line x1="240" y1="900" x2="760" y2="900"/></g>'
    c += '<g stroke="#3a434e" stroke-width="4" opacity="0.5">'
    for x in range(260, 780, 90):
        c += f'<line x1="{x-4}" y1="360" x2="{x-4}" y2="1000"/>'
    c += '</g>'
    # Calavera central (más angulosa y siniestra)
    c += ('<g transform="translate(500 690)">'
          # bóveda craneal + pómulos, estrechándose hacia la mandíbula
          '<path d="M -100 -40 '
          'C -104 -150 -60 -178 0 -178 '
          'C 60 -178 104 -150 100 -40 '
          'C 96 6 78 24 58 40 '
          'C 54 58 48 74 40 92 '
          'L 24 100 L 12 122 L 0 104 L -12 122 L -24 100 '
          'L -40 92 C -48 74 -54 58 -58 40 '
          'C -78 24 -96 6 -100 -40 Z" '
          'fill="#cfc7b6" stroke="#6f685a" stroke-width="4" stroke-linejoin="round"/>'
          # sombreado lateral para dar volumen
          '<path d="M 0 -178 C 60 -178 104 -150 100 -40 C 96 6 78 24 58 40 '
          'C 40 30 30 -60 20 -170 Z" fill="#a59c8a" opacity="0.5"/>'
          # frente: leve sutura/grieta
          '<path d="M 0 -170 L -6 -120 L 4 -80" fill="none" stroke="#8a8272" stroke-width="2.5" opacity="0.6"/>'
          # cuencas hundidas, angulosas
          '<path d="M -78 -70 C -60 -84 -30 -80 -22 -54 C -26 -20 -54 -8 -74 -22 C -86 -40 -86 -58 -78 -70 Z" fill="#080a0e"/>'
          '<path d="M 78 -70 C 60 -84 30 -80 22 -54 C 26 -20 54 -8 74 -22 C 86 -40 86 -58 78 -70 Z" fill="#080a0e"/>'
          # ojos rojos brillando en el fondo de las cuencas
          '<circle cx="-50" cy="-46" r="11" fill="#ff2a20"/><circle cx="50" cy="-46" r="11" fill="#ff2a20"/>'
          '<circle cx="-50" cy="-46" r="22" fill="#ff2a20" opacity="0.28"/>'
          '<circle cx="50" cy="-46" r="22" fill="#ff2a20" opacity="0.28"/>'
          # nariz triangular invertida
          '<path d="M 0 -20 L -18 26 L 0 14 L 18 26 Z" fill="#080a0e"/>'
          # arco cigomático / mejilla marcada
          '<path d="M -58 -8 C -40 6 -20 10 0 10 C 20 10 40 6 58 -8" fill="none" stroke="#8a8272" stroke-width="2" opacity="0.5"/>'
          # dentadura (encaje superior)
          '<g fill="#cfc7b6" stroke="#6f685a" stroke-width="1.5">'
          '<rect x="-42" y="60" width="15" height="30" rx="3"/>'
          '<rect x="-24" y="62" width="15" height="34" rx="3"/>'
          '<rect x="-6" y="62" width="12" height="36" rx="3"/>'
          '<rect x="9" y="62" width="15" height="34" rx="3"/>'
          '<rect x="27" y="60" width="15" height="30" rx="3"/>'
          '</g>'
          '<g stroke="#080a0e" stroke-width="2" opacity="0.7">'
          '<line x1="-27" y1="60" x2="-27" y2="90"/><line x1="-9" y1="62" x2="-9" y2="96"/>'
          '<line x1="9" y1="62" x2="9" y2="96"/><line x1="27" y1="60" x2="27" y2="90"/></g>'
          '</g>')
    # Cadenas colgando
    for cx in (200, 800):
        c += f'<g transform="translate({cx} 360)" stroke="#3a434e" stroke-width="8" fill="none" opacity="0.6">'
        for i in range(6):
            c += f'<ellipse cx="0" cy="{40+i*46}" rx="12" ry="22"/>'
        c += '</g>'
    c += _bandas() + _vineta()
    return _lienzo(defs, c)


def heroe() -> str:
    """Salón heroico: estandartes, escudo heráldico, espada de honor."""
    defs = _defs("#ffdd9a", "#241c16", "#382b20", "#1c150e")
    c = _muro()
    c += _luz()
    # Dos estandartes colgando
    for (cx, col) in ((280, "#8a1f2a"), (720, "#1f3f8a")):
        c += (f'<g transform="translate({cx} 300)">'
              f'<rect x="-70" y="0" width="140" height="620" fill="{col}" opacity="0.82"/>'
              f'<path d="M -70 620 L 0 560 L 70 620 Z" fill="{col}" opacity="0.82"/>'
              f'<rect x="-70" y="0" width="140" height="24" fill="url(#oro)"/>'
              # emblema (estrella) en el estandarte
              f'<g transform="translate(0 300)" fill="url(#oro)" opacity="0.9">'
              f'<polygon points="0,-46 13,-14 46,-14 19,8 29,42 0,22 -29,42 -19,8 -46,-14 -13,-14"/></g>'
              f'</g>')
    # Escudo heráldico central
    c += ('<g transform="translate(500 680)">'
          '<path d="M 0 -150 L 150 -110 L 138 90 C 128 200 70 270 0 300 '
          'C -70 270 -128 200 -138 90 L -150 -110 Z" fill="url(#oro)" stroke="#5c4413" stroke-width="6"/>'
          '<path d="M 0 -128 L 128 -94 L 117 84 C 108 184 58 246 0 272 '
          'C -58 246 -108 184 -117 84 L -128 -94 Z" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>'
          '<path d="M 0 -120 L 0 268" stroke="#2c313b" stroke-width="3" opacity="0.4"/>'
          # emblema león/estrella
          '<g transform="translate(0 80)" fill="url(#oro)">'
          '<polygon points="0,-70 20,-22 70,-22 30,12 44,64 0,34 -44,64 -30,12 -70,-22 -20,-22"/></g>'
          '</g>')
    # Espada de honor cruzada por detrás (vertical, hacia arriba)
    c += ('<g transform="translate(500 680)" opacity="0.7">'
          '<rect x="-12" y="-330" width="24" height="240" rx="6" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>'
          '<polygon points="0,-360 12,-330 -12,-330" fill="url(#acero)" stroke="#2c313b" stroke-width="3"/>'
          '<rect x="-70" y="-96" width="140" height="20" rx="8" fill="url(#oro)" stroke="#5c4413" stroke-width="2"/></g>')
    c += _antorcha(70, 560) + _antorcha(930, 560)
    c += _bandas() + _vineta()
    return _lienzo(defs, c)


def magia() -> str:
    """Santuario arcano: círculo rúnico, orbe flotante, velas y humo azul."""
    defs = _defs("#a9c8ff", "#161426", "#241f3a", "#0f0d1c")
    c = _muro(juntas="#0c0a16")
    # Resplandor mágico frío
    c += '<ellipse cx="500" cy="700" rx="540" ry="560" fill="url(#luz)"/>'
    # Círculo rúnico en el suelo/pared
    c += ('<g transform="translate(500 720)" fill="none" stroke="#6f8fe0" stroke-width="4" opacity="0.6">'
          '<circle cx="0" cy="0" r="230"/><circle cx="0" cy="0" r="196"/>'
          '<circle cx="0" cy="0" r="120" stroke-dasharray="10 14"/></g>')
    # Runas alrededor del círculo
    import math
    runas = ""
    glifos = ["M -10 -14 L 10 -14 M 0 -14 L 0 14", "M -12 -14 L 0 14 L 12 -14",
              "M -10 -14 L -10 14 M -10 0 L 10 -8", "M 0 -14 L 0 14 M -10 -6 L 10 6",
              "M -10 14 L 0 -14 L 10 14 M -6 4 L 6 4", "M -10 -14 L 10 -14 L -10 14 L 10 14",
              "M -8 -14 L -8 14 M 8 -14 L 8 14 M -8 0 L 8 0", "M 0 -14 L -10 8 L 10 8 Z"]
    for i, g in enumerate(glifos):
        ang = math.radians(i * 45 - 90)
        x = 500 + 213 * math.cos(ang)
        y = 720 + 213 * math.sin(ang)
        runas += (f'<g transform="translate({x:.0f} {y:.0f})" stroke="#9fb6f0" '
                  f'stroke-width="4" fill="none" opacity="0.85" stroke-linecap="round">'
                  f'<path d="{g}"/></g>')
    c += runas
    # Pedestal
    c += ('<g transform="translate(500 900)">'
          '<rect x="-70" y="0" width="140" height="120" rx="8" fill="url(#madera)" stroke="#211307" stroke-width="3"/>'
          '<rect x="-90" y="-16" width="180" height="24" rx="8" fill="#2b2440" stroke="#141024" stroke-width="2"/></g>')
    # Orbe arcano flotante con brillo
    c += ('<g transform="translate(500 720)">'
          '<circle cx="0" cy="0" r="130" fill="#6f8fe0" opacity="0.18"/>'
          '<circle cx="0" cy="0" r="86" fill="url(#gema)" stroke="#2b3f80" stroke-width="4"/>'
          '<ellipse cx="-28" cy="-30" rx="26" ry="18" fill="#ffffff" opacity="0.6"/>'
          # destellos
          '<g stroke="#dfeaff" stroke-width="5" stroke-linecap="round" opacity="0.85">'
          '<path d="M 0 -128 L 0 -100"/><path d="M 0 128 L 0 100"/>'
          '<path d="M -128 0 L -100 0"/><path d="M 128 0 L 100 0"/></g></g>')
    # Velas laterales (llama azul)
    for cx in (150, 850):
        c += (f'<g transform="translate({cx} 940)">'
              '<rect x="-16" y="0" width="32" height="120" rx="6" fill="#e8e2d0" opacity="0.85"/>'
              '<ellipse cx="0" cy="-18" rx="20" ry="34" fill="#8fb6ff" opacity="0.8"/>'
              '<path d="M 0 -42 C -8 -22 -10 -8 0 0 C 10 -8 8 -22 0 -42 Z" fill="#dfeaff"/></g>')
    c += _bandas() + _vineta()
    return _lienzo(defs, c)


ESCENAS = {
    "equipo": equipo,
    "tesoro": tesoro,
    "enemigo": enemigo,
    "heroe": heroe,
    "magia": magia,
}


def _rasterizar(svg: str, ruta_png: Path) -> None:
    _rasterizar_png(svg, ruta_png, ANCHO, ALTO)


def generar(solo: str | None, svg_solo: bool) -> None:
    FONDOS_SVG_DIR.mkdir(parents=True, exist_ok=True)
    FONDOS_DIR.mkdir(parents=True, exist_ok=True)

    escenas = ESCENAS
    if solo:
        if solo not in ESCENAS:
            raise SystemExit(f"'{solo}' no existe. Válidos: {', '.join(ESCENAS)}")
        escenas = {solo: ESCENAS[solo]}

    for nombre, fn in escenas.items():
        svg = fn()
        ruta_svg = FONDOS_SVG_DIR / f"{nombre}_back.svg"
        ruta_svg.write_text(svg, encoding="utf-8")
        if svg_solo:
            print(f"SVG  {ruta_svg.name}")
            continue
        ruta_png = FONDOS_DIR / f"{nombre}_back.png"
        _rasterizar(svg, ruta_png)
        print(f"OK   {nombre}  ->  {ruta_png.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="Genera los fondos de reverso de las cartas de HeroQuest")
    p.add_argument("--solo", default=None, help="Genera solo una escena (equipo, tesoro, enemigo, heroe, magia)")
    p.add_argument("--svg-solo", action="store_true", help="Genera solo los SVG, sin rasterizar a PNG")
    args = p.parse_args()
    generar(args.solo, args.svg_solo)


if __name__ == "__main__":
    main()

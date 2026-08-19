# -*- coding: utf-8 -*-
"""Genera los fondos de reverso de las cartas de HeroQuest de forma reproducible.

Cada categoría de carta (equipo, héroe, enemigo, tesoro, magia) tiene una escena
ambiental temática que se dibuja como SVG vectorial y se rasteriza a PNG con
`resvg` (la misma librería que `render_carta.py`). La **magia** se desglosa en sus
**escuelas elementales** (`magia_agua`, `magia_aire`, `magia_fuego`,
`magia_tierra`, `magia_terror`), que comparten el esqueleto del santuario arcano
pero con paleta, orbe y motivos propios de cada elemento.

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

def _defs(luz: str, piedra_top: str, piedra_mid: str, piedra_bot: str,
          extra: str = "") -> str:
    """Defs con una tonalidad de piedra y de luz por escena.

    `extra` permite a cada escena añadir degradados propios (p. ej. el del orbe
    elemental) antes del cierre de `<defs>`.
    """
    base = f"""
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
"""
    if extra:
        base += f"    {extra}\n"
    return base + "  </defs>\n"


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
# Santuario arcano: piezas compartidas por la escena genérica de magia y por
# las escenas elementales (agua, aire, fuego, tierra, terror).
# ---------------------------------------------------------------------------

GLIFOS_RUNAS = [
    "M -10 -14 L 10 -14 M 0 -14 L 0 14", "M -12 -14 L 0 14 L 12 -14",
    "M -10 -14 L -10 14 M -10 0 L 10 -8", "M 0 -14 L 0 14 M -10 -6 L 10 6",
    "M -10 14 L 0 -14 L 10 14 M -6 4 L 6 4", "M -10 -14 L 10 -14 L -10 14 L 10 14",
    "M -8 -14 L -8 14 M 8 -14 L 8 14 M -8 0 L 8 0", "M 0 -14 L -10 8 L 10 8 Z",
]


def _runas(cx: float, cy: float, r: float, color: str) -> str:
    """Glifos rúnicos dispuestos alrededor de un círculo de radio `r`."""
    import math
    runas = ""
    for i, g in enumerate(GLIFOS_RUNAS):
        ang = math.radians(i * 45 - 90)
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        runas += (f'<g transform="translate({x:.0f} {y:.0f})" stroke="{color}" '
                  f'stroke-width="4" fill="none" opacity="0.85" stroke-linecap="round">'
                  f'<path d="{g}"/></g>')
    return runas


def _circulo_runa(cx: float, cy: float, color: str) -> str:
    """Tres círculos concéntricos rúnicos."""
    return (f'<g transform="translate({cx} {cy})" fill="none" stroke="{color}" '
            f'stroke-width="4" opacity="0.6">'
            '<circle cx="0" cy="0" r="230"/><circle cx="0" cy="0" r="196"/>'
            '<circle cx="0" cy="0" r="120" stroke-dasharray="10 14"/></g>')


def _pedestal(cx: float, cy: float) -> str:
    """Pedestal de piedra del orbe."""
    return (f'<g transform="translate({cx} {cy})">'
            '<rect x="-70" y="0" width="140" height="120" rx="8" fill="url(#madera)" stroke="#211307" stroke-width="3"/>'
            '<rect x="-90" y="-16" width="180" height="24" rx="8" fill="#2b2440" stroke="#141024" stroke-width="2"/></g>')


def _orbe(cx: float, cy: float, relleno: str, borde: str, destello: str,
          halo: str, radio: int = 86) -> str:
    """Orbe arcano flotante sobre el pedestal, con halo y destellos."""
    return (f'<g transform="translate({cx} {cy})">'
            f'<circle cx="0" cy="0" r="{radio + 44}" fill="{halo}" opacity="0.18"/>'
            f'<circle cx="0" cy="0" r="{radio}" fill="{relleno}" stroke="{borde}" stroke-width="4"/>'
            f'<ellipse cx="{-radio * 0.33:.0f}" cy="{-radio * 0.35:.0f}" '
            f'rx="{radio * 0.30:.0f}" ry="{radio * 0.21:.0f}" fill="#ffffff" opacity="0.6"/>'
            f'<g stroke="{destello}" stroke-width="5" stroke-linecap="round" opacity="0.85">'
            f'<path d="M 0 {-radio - 42} L 0 {-radio - 14}"/>'
            f'<path d="M 0 {radio + 42} L 0 {radio + 14}"/>'
            f'<path d="M {-radio - 42} 0 L {-radio - 14} 0"/>'
            f'<path d="M {radio + 42} 0 L {radio + 14} 0"/></g></g>')


def _vela(cx: float, cy: float, llama: str, nucleo: str) -> str:
    """Vela de pie con llama de color configurable."""
    return (f'<g transform="translate({cx} {cy})">'
            '<rect x="-16" y="0" width="32" height="120" rx="6" fill="#e8e2d0" opacity="0.85"/>'
            f'<ellipse cx="0" cy="-18" rx="20" ry="34" fill="{llama}" opacity="0.8"/>'
            f'<path d="M 0 -42 C -8 -22 -10 -8 0 0 C 10 -8 8 -22 0 -42 Z" fill="{nucleo}"/></g>')


def _santuario_elemental(luz: str, piedra: tuple[str, str, str], juntas: str,
                         runa: str, glifo: str, orbe_defs: str, orbe_relleno: str,
                         orbe_borde: str, orbe_halo: str, vela_llama: str,
                         vela_nucleo: str, inserto: str) -> str:
    """Santuario arcano con la identidad de un elemento.

    Mismo esqueleto que `magia()` (muro, círculo rúnico, pedestal, orbe y velas)
    pero con la paleta, el orbe y los motivos del elemento. `inserto` son las
    decoraciones propias del elemento dibujadas entre el orbe y las velas.
    """
    defs = _defs(luz, *piedra, extra=orbe_defs)
    c = _muro(juntas=juntas)
    c += _luz()
    c += _circulo_runa(500, 720, runa)
    c += _runas(500, 720, 213, glifo)
    c += _pedestal(500, 900)
    c += _orbe(500, 720, orbe_relleno, orbe_borde, glifo, orbe_halo)
    c += inserto
    c += _vela(150, 940, vela_llama, vela_nucleo) + _vela(850, 940, vela_llama, vela_nucleo)
    c += _bandas() + _vineta()
    return _lienzo(defs, c)


def _orbe_gradiente(id_, c1: str, c2: str, c3: str) -> str:
    return (f'<radialGradient id="{id_}" cx="38%" cy="30%" r="75%">'
            f'<stop offset="0%" stop-color="{c1}"/>'
            f'<stop offset="45%" stop-color="{c2}"/>'
            f'<stop offset="100%" stop-color="{c3}"/></radialGradient>')


# ---------------------------------------------------------------------------
# Glifos reutilizados de librerías libres (el path se incrusta en la escena).
#
# Rayo de agua: icono "water-bolt" de Material Design Icons (Apache 2.0),
# vía SVG Repo (https://www.svgrepo.com/svg/321681/water-bolt). Se incrusta
# en la escena de magia de agua con su relleno cian y su trazo azul originales.
GLIFO_AGUA = (
    "M16.656 13.78v101.626C24.09 156.98 37.52 198.146 58.72 234c-10.608 4.22-18.095 14.576-18.095 26.688 0 15.858 12.83 28.687 28.688 28.687 9.17 0 17.337-4.306 22.593-11 31.064 32.862 72.3 56.826 126.03 65.5 1.762-19.596-.38-43.662-7.03-70-.153-.606-.312-1.208-.47-1.813-49.262 3.933-112.35-46.09-155.405-128.03 14.51-4.115 25.564-25.078 25.564-50.313 0-19.337-6.505-36.154-16.063-44.814 61.958-27.854 164.946-1.763 227.22 33.782-48.7-42.11-91.218-65-162.938-68.907H16.656zM383 24.25c-9.352 0-16.938 7.586-16.938 16.938 0 9.35 7.586 16.937 16.938 16.937 9.352 0 16.938-7.586 16.938-16.938 0-9.35-7.586-16.937-16.938-16.937zm30.97 36.78c-17.564 0-31.783 14.25-31.783 31.814 0 17.563 14.22 31.78 31.782 31.78 17.562 0 31.81-14.217 31.81-31.78 0-17.563-14.248-31.813-31.81-31.813zm-240.19 1.814c-23.255.037-43.425 6.88-56.655 21-26.065 38.438-14.82 82.045 10.5 115.062 13.28 17.317 35.624 20.438 44.97 11.094 4.852-4.853 5.86-12.614 3.53-21.125l.906 1.28c26.775 20.566 52.716 59.879 66.345 104.657 19.984 65.66 6.223 118.565-30.72 118.094-13.853-.177-28.85-8.127-43.436-21.094 3.344 1.275 6.57 2.298 9.81 2.657 13.533 1.502 23.973-5.532 30.72-18.72-22.275 9.978-56.66.58-94.656-21.75 11.065 14.657 23.428 29.71 37.125 43.406 103.223 103.225 240.478 132.925 306.686 66.72 66.208-66.207 36.506-203.495-66.72-306.72-13.695-13.697-28.745-26.028-43.405-37.094 22 37.434 31.45 71.36 22.19 93.657-9.23-32.292-33.12-67.81-68.72-97.407-41.758-34.72-89.71-53.773-128.47-53.72zm21.22 56.25c1.46 0 2.952.04 4.438.094-10.142 20.03 1.824 47.9 28.406 64.187 28.2 17.28 62.132 14.965 75.78-5.188 3.377-4.983 5.195-10.59 5.595-16.468 4.746 3.446 9.443 7.065 14.06 10.905 17.895 14.878 32.534 31.425 44.033 48.156-.3.442-.587.885-.907 1.314-28.493 38.214-120.112 11.177-207.625-59.625-.09-.076-.188-.145-.28-.22-1.39-1.226-2.813-2.405-4.25-3.47-.01-.008-.02-.02-.03-.03-.013-.01-.02-.023-.032-.03-1.388-1.15-2.772-2.3-4.157-3.47.41.482.815.955 1.22 1.438-6.606-4.294-13.447-6.837-19.53-7.407 1.99-3.338 4.274-6.435 7-9.343 13.23-14.118 33.094-20.86 56.28-20.843zM411.03 271.53c10.32 5.475 20.25 12.5 29 21.25 44.725 44.727 46.48 115.272 4.314 157.44-42.167 42.166-112.618 39.724-157.344-5-8.59-8.592-15.223-18.3-20.656-28.408 42.458 22.617 94.995 17.724 129.062-16.343 3.287-3.288 6.263-6.743 9-10.345-16.205-.64-29.156-13.982-29.156-30.344 0-16.77 13.604-30.342 30.375-30.342 7.28 0 13.957 2.572 19.188 6.843 1.82-21.772-2.845-44.393-13.782-64.75zm-26.53 8.75c10.948 0 19.813 8.897 19.813 19.845 0 10.948-8.865 19.813-19.813 19.813-10.948 0-19.844-8.865-19.844-19.813 0-10.948 8.896-19.844 19.844-19.844zM60.906 326.564c-9.352 0-16.937 7.554-16.937 16.906 0 9.35 7.584 16.936 16.936 16.936s16.907-7.585 16.907-16.937c0-9.353-7.555-16.908-16.907-16.908z"
)

RAYO_AGUA = (
    '<path d="'
    + GLIFO_AGUA
    + '" fill="#09ecdd" stroke="#1e00ff" stroke-width="3.83" stroke-linejoin="round"/>'
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


def magia_agua() -> str:
    """Santuario arcano de magia de agua: charco reflectante, ondas, gotas y el
    rayo de agua (glifo de Material Design Icons) flotando junto al orbe."""
    orbe = _orbe_gradiente("orbe-agua", "#dff4ff", "#3aa6d8", "#11456e")
    inserto = (
        # Charco bajo el pedestal con ondas
        '<ellipse cx="500" cy="1050" rx="330" ry="78" fill="#1f5a8a" opacity="0.30"/>'
        '<g fill="none" stroke="#7fc4e8" stroke-width="3" opacity="0.55">'
        '<ellipse cx="500" cy="1050" rx="250" ry="56"/>'
        '<ellipse cx="500" cy="1050" rx="160" ry="36" stroke-dasharray="18 12"/></g>'
        # Rayo de agua flotando junto al orbe (con halo)
        '<ellipse cx="700" cy="585" rx="96" ry="86" fill="#3aa6d8" opacity="0.22"/>'
        f'<g transform="translate(700 585) scale(0.34) rotate(7)">{RAYO_AGUA}</g>'
        # Ondas flotando
        '<g fill="none" stroke="#9fd4ff" stroke-width="4" opacity="0.55" stroke-linecap="round">'
        '<path d="M 220 420 C 250 400 270 440 300 420"/>'
        '<path d="M 620 380 C 650 400 680 360 710 380"/>'
        '<path d="M 330 880 C 360 862 390 900 420 882"/>'
        '<path d="M 660 860 C 690 880 720 850 750 868"/></g>'
        # Gotas flotando
        '<g fill="#bfe6ff" opacity="0.75">'
        '<ellipse cx="210" cy="640" rx="7" ry="10"/>'
        '<ellipse cx="792" cy="700" rx="6" ry="9" opacity="0.7"/>'
        '<ellipse cx="760" cy="430" rx="5" ry="7" opacity="0.6"/></g>'
    )
    return _santuario_elemental(
        "#7fd4ff", ("#122036", "#1c2f4a", "#0a1424"), "#0a1120",
        "#5aa6d8", "#9fd4ff", orbe, "url(#orbe-agua)", "#123f6e", "#7fc4e8",
        "#8fb6ff", "#dff4ff", inserto,
    )


def magia_aire() -> str:
    """Santuario arcano de magia de aire: remolinos de viento y plumas."""
    orbe = _orbe_gradiente("orbe-aire", "#f2fbff", "#9fcff0", "#3a6a94")
    inserto = (
        # Corrientes de viento en espiral
        '<g fill="none" stroke="#dff2ff" stroke-width="5" opacity="0.5" stroke-linecap="round">'
        '<path d="M 150 470 C 130 360 210 320 250 400 C 270 450 240 500 200 480"/>'
        '<path d="M 840 520 C 870 420 790 370 750 450 C 730 500 760 550 810 530"/>'
        '<path d="M 300 620 C 320 600 340 612 360 602"/></g>'
        # Plumas flotando
        '<g fill="#eef8ff" opacity="0.75">'
        '<ellipse cx="240" cy="660" rx="24" ry="9" transform="rotate(-18 240 660)"/>'
        '<ellipse cx="768" cy="600" rx="22" ry="8" transform="rotate(14 768 600)"/>'
        '<ellipse cx="180" cy="800" rx="18" ry="7" transform="rotate(-30 180 800)"/></g>'
    )
    return _santuario_elemental(
        "#d6f1ff", ("#1e232b", "#2c3440", "#12161c"), "#0d1016",
        "#9fc4e8", "#dff2ff", orbe, "url(#orbe-aire)", "#2a5a86", "#cfeaff",
        "#bfe0ff", "#f2fbff", inserto,
    )


def magia_fuego() -> str:
    """Santuario arcano de magia de fuego: brasero y llamas desatadas."""
    orbe = _orbe_gradiente("orbe-fuego", "#fff3c0", "#ff8a2a", "#8f1a08")
    inserto = (
        # Brasero con grandes llamas frente al pedestal
        '<g transform="translate(500 1010)">'
        '<ellipse cx="0" cy="0" rx="92" ry="28" fill="#2e1006" stroke="#7a2a10" stroke-width="4"/>'
        '<ellipse cx="0" cy="-22" rx="56" ry="96" fill="url(#llama)"/>'
        '<path d="M -36 -52 C -46 -8 -10 30 0 42 C 10 30 46 -8 36 -52 '
        'C 18 -30 6 -10 0 -2 C -6 -10 -18 -30 -36 -52 Z" fill="#ff9a3a" opacity="0.9"/>'
        '<path d="M -18 -78 C -22 -36 -5 -4 0 4 C 5 -4 22 -36 18 -78 '
        'C 8 -44 2 -30 0 -30 Z" fill="#ffd86a"/></g>'
        # Chispas ascendentes
        '<g fill="#ffcf6a">'
        '<circle cx="430" cy="880" r="5" opacity="0.9"/><circle cx="560" cy="850" r="4" opacity="0.8"/>'
        '<circle cx="470" cy="920" r="3" opacity="0.7"/><circle cx="540" cy="900" r="4" opacity="0.85"/></g>'
    )
    return _santuario_elemental(
        "#ffb03a", ("#2a1512", "#3d1f18", "#180b08"), "#120807",
        "#d8783a", "#ffd28a", orbe, "url(#orbe-fuego)", "#6e1506", "#ffb03a",
        "#ff8a2a", "#ffd86a", inserto,
    )


def magia_tierra() -> str:
    """Santuario arcano de magia de tierra: raíces, grietas y musgo."""
    orbe = _orbe_gradiente("orbe-tierra", "#e6ffd2", "#5f9a3c", "#1d4a1a")
    inserto = (
        # Raíces colgando del techo
        '<g fill="none" stroke="#3f5a2f" stroke-width="7" stroke-linecap="round" opacity="0.7">'
        '<path d="M 250 330 C 275 430 240 470 295 540"/>'
        '<path d="M 750 330 C 725 430 760 475 705 545"/>'
        '<path d="M 500 332 C 478 400 522 445 505 505"/></g>'
        # Grietas en la piedra
        '<g fill="none" stroke="#0c0f08" stroke-width="3" opacity="0.6">'
        '<path d="M 90 330 L 110 400 L 96 460"/>'
        '<path d="M 900 360 L 886 420 L 902 480"/></g>'
        # Musgo
        '<g fill="#2e4a1e" opacity="0.30">'
        '<ellipse cx="180" cy="520" rx="40" ry="30"/>'
        '<ellipse cx="820" cy="640" rx="46" ry="32"/>'
        '<ellipse cx="260" cy="760" rx="34" ry="26"/></g>'
    )
    return _santuario_elemental(
        "#cfe8b0", ("#1d2015", "#2c3320", "#10130b"), "#0c0f08",
        "#7f9a4a", "#d0e8a8", orbe, "url(#orbe-tierra)", "#16380f", "#b8d68a",
        "#d8e8b8", "#f4ffe0", inserto,
    )


def magia_terror() -> str:
    """Santuario desecrado de magia del terror: niebla, ojos rojos y cuervos."""
    orbe = _orbe_gradiente("orbe-terror", "#d9b4ff", "#6a2a9a", "#180b22")
    inserto = (
        # Niebla baja con ojos rojos que brillan
        '<ellipse cx="500" cy="1140" rx="430" ry="110" fill="#0a0510" opacity="0.55"/>'
        '<g fill="#120820" opacity="0.6">'
        '<ellipse cx="380" cy="1120" rx="180" ry="60"/>'
        '<ellipse cx="650" cy="1150" rx="170" ry="55"/></g>'
        '<g fill="#ff2a20">'
        '<circle cx="360" cy="1100" r="6"/><circle cx="640" cy="1120" r="6"/>'
        '<circle cx="520" cy="1140" r="5" opacity="0.85"/><circle cx="470" cy="1110" r="4" opacity="0.7"/>'
        '<circle cx="760" cy="1150" r="4" opacity="0.7"/></g>'
        # Cuervos en silueta
        '<g fill="#120820" opacity="0.8">'
        '<path transform="translate(180 620)" d="M 0 0 Q 8 -8 16 0 Q 24 -8 32 0 Q 24 4 16 -1 Q 8 4 0 0 Z"/>'
        '<path transform="translate(760 560) scale(0.8)" d="M 0 0 Q 8 -8 16 0 Q 24 -8 32 0 Q 24 4 16 -1 Q 8 4 0 0 Z"/>'
        '<path transform="translate(220 540) scale(0.6)" d="M 0 0 Q 8 -8 16 0 Q 24 -8 32 0 Q 24 4 16 -1 Q 8 4 0 0 Z"/></g>'
    )
    return _santuario_elemental(
        "#a06fd0", ("#160b1a", "#241030", "#0a050d"), "#050208",
        "#5a2a8a", "#c9a0ff", orbe, "url(#orbe-terror)", "#2a0e3c", "#9a6ac0",
        "#a05ac0", "#e0c0ff", inserto,
    )


ESCENAS = {
    "equipo": equipo,
    "tesoro": tesoro,
    "enemigo": enemigo,
    "heroe": heroe,
    "magia": magia,
    "magia_agua": magia_agua,
    "magia_aire": magia_aire,
    "magia_fuego": magia_fuego,
    "magia_tierra": magia_tierra,
    "magia_terror": magia_terror,
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
    p.add_argument("--solo", default=None,
                   help="Genera solo una escena (equipo, tesoro, enemigo, heroe, magia, "
                        "magia_agua, magia_aire, magia_fuego, magia_tierra, magia_terror)")
    p.add_argument("--svg-solo", action="store_true", help="Genera solo los SVG, sin rasterizar a PNG")
    args = p.parse_args()
    generar(args.solo, args.svg_solo)


if __name__ == "__main__":
    main()

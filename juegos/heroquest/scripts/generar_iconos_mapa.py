# -*- coding: utf-8 -*-
"""Genera los iconos cuadrados (220x220, fondo transparente) que se usan en los
mapas de misión: puertas (abiertas/cerradas), trampas, muebles, entrada y salida.

Salida: juegos/heroquest/sources/arte_iconos/mapa/<slug>.png

Uso:
    uv run juegos/heroquest/scripts/generar_iconos_mapa.py
    uv run juegos/heroquest/scripts/generar_iconos_mapa.py --solo puerta_abierta
    uv run juegos/heroquest/scripts/generar_iconos_mapa.py --svg-solo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from arte_comun import rasterizar

N = 220  # lienzo cuadrado
BORDE = "#1a1a1a"

ICONOS_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_iconos" / "mapa"
SVG_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_svg" / "mapa"

DEFS = """
  <defs>
    <linearGradient id="madera" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#5a3a1c"/>
      <stop offset="45%" stop-color="#a06a35"/>
      <stop offset="60%" stop-color="#8a5828"/>
      <stop offset="100%" stop-color="#3f2711"/>
    </linearGradient>
    <linearGradient id="madera-verde" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="#2e5d34"/>
      <stop offset="50%" stop-color="#4d8a4a"/>
      <stop offset="100%" stop-color="#2a4f2c"/>
    </linearGradient>
    <linearGradient id="madera-roja" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="#7c2621"/>
      <stop offset="45%" stop-color="#a0402f"/>
      <stop offset="100%" stop-color="#5e1f1a"/>
    </linearGradient>
    <linearGradient id="piedra" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="#9aa0a8"/>
      <stop offset="50%" stop-color="#747c88"/>
      <stop offset="100%" stop-color="#4d545e"/>
    </linearGradient>
    <linearGradient id="piedra-clara" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="#d9d4c8"/>
      <stop offset="100%" stop-color="#9a9180"/>
    </linearGradient>
    <linearGradient id="oro" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"  stop-color="#f6d98a"/>
      <stop offset="50%" stop-color="#c99a3f"/>
      <stop offset="100%" stop-color="#8a641f"/>
    </linearGradient>
    <linearGradient id="fuego" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#ffd54f"/>
      <stop offset="50%" stop-color="#ff8f00"/>
      <stop offset="100%" stop-color="#d84315"/>
    </linearGradient>
  </defs>
"""


def _svg(cuerpo: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{N}" height="{N}" '
        f'viewBox="0 0 {N} {N}">{DEFS}{cuerpo}</svg>\n'
    )


def _sombra(x, y, rx, ry, op="0.18") -> str:
    return f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="#000" opacity="{op}"/>'


def puerta_cerrada() -> str:
    """Puerta cerrada de madera rojiza con planchas y cerrojo (timbre rojo)."""
    c = [_sombra(110, 200, 80, 12)]
    c += ['<rect x="30" y="18" width="160" height="180" rx="6" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="12" y="30" width="18" height="156" rx="4" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="190" y="30" width="18" height="156" rx="4" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<path d="M 30 18 Q 110 -12 190 18 Z" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="46" y="36" width="128" height="146" rx="5" fill="url(#madera-roja)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="56" y="52" width="108" height="42" rx="3" fill="none" stroke="#3d1410" stroke-width="3"/>']
    c += ['<rect x="56" y="106" width="108" height="42" rx="3" fill="none" stroke="#3d1410" stroke-width="3"/>']
    c += ['<rect x="96" y="46" width="4" height="126" fill="#3d1410"/>']
    c += ['<rect x="86" y="78" width="48" height="16" rx="3" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<circle cx="130" cy="86" r="5" fill="url(#oro)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="82" y="128" width="56" height="18" rx="4" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="96" y="118" width="28" height="22" rx="3" fill="#5e1f1a" stroke="' + BORDE + '" stroke-width="2"/>']
    return _svg("".join(c))


def puerta_abierta() -> str:
    """Puerta doble abierta mostrando un paso libre teñido de verde."""
    c = [_sombra(110, 200, 80, 12)]
    c += ['<rect x="18" y="30" width="184" height="170" rx="5" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 18 30 Q 110 -14 202 30 Z" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="52" y="42" width="116" height="146" rx="4" fill="#1e3a22" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="66" y="54" width="88" height="122" rx="6" fill="#27492c" stroke="#12331a" stroke-width="2"/>']
    # Hoja izquierda abierta
    c += ['<path d="M 48 42 L 6 58 L 4 186 L 48 188 Z" fill="url(#madera-verde)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<line x1="8" y1="82" x2="44" y2="74" stroke="#1d3a20" stroke-width="3"/>']
    c += ['<line x1="7" y1="130" x2="44" y2="122" stroke="#1d3a20" stroke-width="3"/>']
    # Hoja derecha abierta
    c += ['<path d="M 172 42 L 214 58 L 216 186 L 172 188 Z" fill="url(#madera-verde)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<line x1="212" y1="82" x2="176" y2="74" stroke="#1d3a20" stroke-width="3"/>']
    c += ['<line x1="213" y1="130" x2="176" y2="122" stroke="#1d3a20" stroke-width="3"/>']
    return _svg("".join(c))


def trampa_pozo() -> str:
    """Trampa de pozo: agujero oscuro en el suelo bordeado de tablas."""
    c = [_sombra(110, 176, 78, 12)]
    c += ['<rect x="20" y="120" width="180" height="70" fill="#8a7a5e" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 20 120 L 200 120 L 190 150 L 30 150 Z" fill="#6b5b40"/>']
    c += ['<path d="M 34 160 L 186 160" stroke="#5a4a30" stroke-width="3"/>']
    # Boca del pozo
    c += ['<ellipse cx="110" cy="120" rx="78" ry="34" fill="#2b2b2b" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<ellipse cx="110" cy="120" rx="62" ry="25" fill="#0c0c0c"/>']
    c += ['<path d="M 74 112 L 90 128 M 128 108 L 140 120 M 104 100 L 108 114" stroke="#3a3a3a" stroke-width="3"/>']
    # Tablas alrededor
    c += ['<rect x="20" y="108" width="30" height="14" rx="2" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="170" y="108" width="30" height="14" rx="2" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="78" y="84" width="64" height="14" rx="2" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<path d="M 82 84 L 82 96 M 118 84 L 118 96" stroke="#3f2711" stroke-width="2"/>']
    return _svg("".join(c))


def trampa_lanza() -> str:
    """Trampa de lanza: muro de ladrillo con una lanza disparada en diagonal."""
    c = [_sombra(110, 192, 82, 12)]
    # Muro
    p = []
    for i in range(4):
        for j in range(3):
            x = 14 + j * 64
            y = 96 + i * 26
            p.append(f'<rect x="{x}" y="{y}" width="58" height="20" rx="2" fill="url(#piedra)" stroke="#333a44" stroke-width="2"/>')
    c += ["".join(p)]
    c += ['<rect x="10" y="84" width="200" height="24" rx="4" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="10" y="180" width="200" height="24" rx="4" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    # Ranura
    c += ['<rect x="80" y="110" width="12" height="60" rx="4" fill="#1c1c1c" stroke="' + BORDE + '" stroke-width="2"/>']
    # Lanza en diagonal (apuntando abajo-derecha)
    c += ['<rect x="78" y="120" width="96" height="9" rx="4" transform="rotate(-32 78 124)" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<path d="M 168 88 L 188 112 L 172 122 Z" fill="#b03a2e" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<path d="M 158 96 L 174 108" stroke="#e8edf2" stroke-width="2"/>']
    return _svg("".join(c))


def trampa_derrumbe() -> str:
    """El derrumbe: rocas cayendo que aplastan el suelo."""
    c = [_sombra(110, 188, 82, 12)]
    c += ['<rect x="14" y="168" width="192" height="30" rx="3" fill="#4b5561" stroke="' + BORDE + '" stroke-width="2.5"/>']
    bloques = [
        (54, 92, 62, 60, "#8f9aa6"), (120, 116, 70, 52, "#6b7684"),
        (40, 136, 66, 44, "#757f8c"), (104, 30, 58, 40, "#9aa5b1"),
        (152, 58, 44, 52, "#808b98"), (14, 70, 44, 60, "#8a94a0"),
        (86, 8, 34, 40, "#a3adb8"),
    ]
    for x, y, a, b, fill in bloques:
        c += [
            f'<path d="M {x} {y + b} L {x} {y + b * 0.35} L {x + a * 0.5} {y} L {x + a} {y + b * 0.35} L {x + a} {y + b} Z" '
            f'fill="{fill}" stroke="{BORDE}" stroke-width="2.5"/>'
        ]
        c += [f'<path d="M {x + a * 0.18} {y + b * 0.55} L {x + a * 0.82} {y + b * 0.55}" stroke="#3a4149" stroke-width="2"/>']
    return _svg("".join(c))


def mueble_mesa() -> str:
    """Mesa de madera con un jarro encima."""
    c = [_sombra(110, 190, 76, 12)]
    c += ['<rect x="60" y="136" width="14" height="48" rx="3" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="146" y="136" width="14" height="48" rx="3" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="34" y="112" width="152" height="28" rx="6" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="34" y="122" width="152" height="5" fill="#3f2711" opacity="0.5"/>']
    c += ['<rect x="96" y="60" width="30" height="54" rx="6" fill="#8a5a2f" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<path d="M 96 60 L 111 44 L 126 60 Z" fill="#6e4322" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<line x1="88" y1="84" x2="134" y2="84" stroke="#e8e3d5" stroke-width="4" opacity="0.85"/>']
    c += ['<ellipse cx="111" cy="70" rx="6" ry="4" fill="#d8a848"/>']
    return _svg("".join(c))


def mueble_alacena() -> str:
    """Alacena alta de madera con dos puertas y estante interior."""
    c = [_sombra(110, 192, 66, 12)]
    c += ['<rect x="52" y="34" width="116" height="156" rx="6" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="60" y="42" width="100" height="18" rx="3" fill="#3f2711" stroke="#2e1a09" stroke-width="2"/>']
    c += ['<rect x="58" y="170" width="104" height="12" rx="3" fill="#3f2711"/>']
    c += ['<rect x="68" y="66" width="38" height="98" rx="3" fill="#a06a35" stroke="#3f2711" stroke-width="2.5"/>']
    c += ['<rect x="114" y="66" width="38" height="98" rx="3" fill="#a06a35" stroke="#3f2711" stroke-width="2.5"/>']
    c += ['<circle cx="87" cy="112" r="4" fill="url(#oro)" stroke="' + BORDE + '" stroke-width="1.5"/>']
    c += ['<circle cx="133" cy="112" r="4" fill="url(#oro)" stroke="' + BORDE + '" stroke-width="1.5"/>']
    return _svg("".join(c))


def mueble_chimenea() -> str:
    """Chimenea de piedra con brasas encendidas."""
    c = [_sombra(110, 176, 76, 12)]
    # Base de piedra
    c += ['<rect x="30" y="120" width="160" height="72" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="42" y="128" width="36" height="56" rx="3" fill="url(#piedra)" stroke="#333a44" stroke-width="2"/>']
    c += ['<rect x="142" y="128" width="36" height="56" rx="3" fill="url(#piedra)" stroke="#333a44" stroke-width="2"/>']
    # Horno
    c += ['<path d="M 90 192 L 90 130 Q 110 100 130 130 L 130 192 Z" fill="#1c1c1c" stroke="' + BORDE + '" stroke-width="3"/>']
    # Fuego
    c += ['<path d="M 110 108 Q 122 124 110 138 Q 100 128 110 108 Z" fill="url(#fuego)" stroke="#b02a12" stroke-width="2"/>']
    c += ['<path d="M 108 116 Q 116 128 108 138 Q 102 126 108 116 Z" fill="#ffeb9e"/>']
    c += ['<path d="M 90 142 Q 96 150 110 150 Q 124 150 130 142 L 132 150 L 88 150 Z" fill="#3a1c0e"/>']
    # Dintel
    c += ['<rect x="24" y="104" width="172" height="20" rx="4" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 30 104 L 110 76 L 190 104" fill="none" stroke="' + BORDE + '" stroke-width="5" stroke-linejoin="round"/>']
    c += ['<path d="M 30 104 L 110 76 L 190 104" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3" stroke-linejoin="round"/>']
    return _svg("".join(c))


def mueble_tumba() -> str:
    """Tumba de piedra con losa superior y una cruz tallada."""
    c = [_sombra(110, 180, 76, 12)]
    c += ['<rect x="36" y="110" width="148" height="62" rx="6" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 36 110 L 54 92 L 180 92 L 184 110 Z" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 44 172 L 64 92" stroke="#6b6352" stroke-width="3"/>']
    c += ['<line x1="110" y1="52" x2="110" y2="112" stroke="#5a5347" stroke-width="6" stroke-linecap="round"/>']
    c += ['<line x1="90" y1="72" x2="130" y2="72" stroke="#5a5347" stroke-width="6" stroke-linecap="round"/>']
    c += ['<circle cx="110" cy="126" r="10" fill="none" stroke="#9a9180" stroke-width="3"/>']
    return _svg("".join(c))


def mueble_cofre() -> str:
    """Cofre del tesoro de madera con refuerzos dorados."""
    c = [_sombra(110, 186, 72, 12)]
    c += ['<rect x="46" y="108" width="128" height="66" rx="8" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 46 108 C 46 76 174 76 174 108 Z" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 76 128 L 76 158 M 144 128 L 144 158 M 106 96 L 106 174" stroke="url(#oro)" stroke-width="6"/>']
    c += ['<rect x="96" y="128" width="28" height="22" rx="4" fill="url(#oro)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="110" y="122" width="8" height="14" rx="2" fill="#c99a3f" stroke="' + BORDE + '" stroke-width="1.5"/>']
    c += ['<circle cx="102" cy="146" r="4" fill="#3a2820"/>']
    return _svg("".join(c))


def mueble_banco_alquimista() -> str:
    """Banco de alquimista: mesa con frascos y manual."""
    c = [_sombra(110, 190, 76, 12)]
    c += ['<rect x="56" y="136" width="14" height="48" rx="3" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="150" y="136" width="14" height="48" rx="3" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="32" y="108" width="156" height="32" rx="6" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="3"/>']
    # Frasco morado
    c += ['<path d="M 88 44 L 84 94 Q 84 104 96 104 L 106 104 Q 118 104 118 94 L 114 44 Z" fill="#4a3a6e" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="92" y="34" width="28" height="10" rx="3" fill="#2e1a09"/>']
    # Frasco verde
    c += ['<rect x="128" y="56" width="26" height="52" rx="6" fill="#2f6a3d" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<rect x="134" y="46" width="14" height="10" rx="3" fill="#2e1a09"/>']
    # Manual
    c += ['<rect x="46" y="74" width="30" height="36" rx="3" fill="#b7a26c" stroke="' + BORDE + '" stroke-width="2.5"/>']
    c += ['<line x1="50" y1="84" x2="72" y2="84" stroke="#5a4a30" stroke-width="2"/>']
    c += ['<line x1="50" y1="94" x2="72" y2="94" stroke="#5a4a30" stroke-width="2"/>']
    return _svg("".join(c))


def entrada() -> str:
    """Entrada: arco de piedra con escalones que bajan a la penumbra."""
    c = [_sombra(110, 196, 80, 12)]
    c += ['<rect x="18" y="26" width="184" height="170" rx="6" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 18 26 Q 110 -16 202 26 Z" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<path d="M 54 30 Q 110 6 166 30 L 166 196 L 54 196 Z" fill="#1d2a20" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="70" y="120" width="80" height="14" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="78" y="142" width="80" height="14" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="86" y="164" width="80" height="14" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="2"/>']
    # Elipse verde de entrada
    c += ['<ellipse cx="110" cy="102" rx="16" ry="8" fill="#2e8b57"/>']
    return _svg("".join(c))


def salida() -> str:
    """Salida: escalera de piedra que sube hacia la puerta de salida."""
    c = [_sombra(110, 196, 80, 12)]
    c += ['<rect x="18" y="30" width="184" height="166" rx="6" fill="url(#piedra)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="52" y="44" width="116" height="140" rx="5" fill="#dfd9c9" stroke="' + BORDE + '" stroke-width="3"/>']
    # Escalones ascendiendo hacia atrás
    c += ['<rect x="66" y="100" width="88" height="14" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="70" y="78" width="88" height="14" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="2"/>']
    c += ['<rect x="74" y="56" width="88" height="14" fill="url(#piedra-clara)" stroke="' + BORDE + '" stroke-width="2"/>']
    # Flecha ascendente
    c += ['<path d="M 110 128 L 110 44 M 92 62 L 110 44 L 128 62" fill="none" stroke="#455a64" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>']
    c += ['<rect x="56" y="122" width="108" height="54" rx="4" fill="url(#madera)" stroke="' + BORDE + '" stroke-width="3"/>']
    c += ['<rect x="66" y="132" width="88" height="34" rx="3" fill="none" stroke="#2e1a09" stroke-width="3"/>']
    c += ['<circle cx="120" cy="149" r="5" fill="url(#oro)" stroke="' + BORDE + '" stroke-width="2"/>']
    return _svg("".join(c))


OBJETOS = {
    "puerta_abierta": puerta_abierta,
    "puerta_cerrada": puerta_cerrada,
    "trampa_pozo": trampa_pozo,
    "trampa_lanza": trampa_lanza,
    "trampa_derrumbe": trampa_derrumbe,
    "mueble_mesa": mueble_mesa,
    "mueble_alacena": mueble_alacena,
    "mueble_chimenea": mueble_chimenea,
    "mueble_tumba": mueble_tumba,
    "mueble_cofre": mueble_cofre,
    "mueble_banco_alquimista": mueble_banco_alquimista,
    "entrada": entrada,
    "salida": salida,
}


def generar(solo: str | None, svg_solo: bool) -> None:
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    ICONOS_DIR.mkdir(parents=True, exist_ok=True)
    objetos = OBJETOS
    if solo:
        if solo not in OBJETOS:
            raise SystemExit(f"'{solo}' no existe. Válidos: {', '.join(OBJETOS)}")
        objetos = {solo: OBJETOS[solo]}
    for slug, fn in objetos.items():
        svg = fn()
        (SVG_DIR / f"{slug}.svg").write_text(svg, encoding="utf-8")
        if svg_solo:
            print(f"SVG  sources/arte_svg/mapa/{slug}.svg")
            continue
        ruta_png = ICONOS_DIR / f"{slug}.png"
        rasterizar(svg, ruta_png, N, N)
        print(f"OK   {slug}  ->  {ruta_png.relative_to(ICONOS_DIR.parent.parent.parent)}")


def main() -> None:
    p = argparse.ArgumentParser(description="Genera los iconos de los mapas de misión")
    p.add_argument("--solo", default=None, help="Genera solo un icono (por nombre de archivo)")
    p.add_argument("--svg-solo", action="store_true", help="Genera solo los SVG, sin rasterizar")
    args = p.parse_args()
    generar(args.solo, args.svg_solo)


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Módulo para renderizar cartas de HeroQuest a formato SVG.

Este módulo proporciona funciones para generar una representación SVG de varias
tarjetas de juego, imitando el estilo de las cartas físicas originales.
Utiliza un sistema de tipos de carta para determinar el diseño y el contenido.
"""
from __future__ import annotations
import xml.sax.saxutils
import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Evita la importación circular y permite el tipado
    from tipos_carta import TipoCarta

# --- Constantes de Estilo ---
FONT_FAMILY_SERIF = "Georgia, 'Times New Roman', serif"
COLOR_BORDE = "#4d2c1b"
COLOR_PERGAMINO_CLARO = "#f3ecdd"
COLOR_PERGAMINO_OSCURO = "#eadfc8"
COLOR_TEXTO_PRINCIPAL = "#3a2416"
COLOR_BANNER = "#f4e9d2"
COLOR_CELDA_STAT = "#fbf6ea"

# --- Constantes de Tamaño de Carta ---
# Tamaño estándar de carta de juego (póker/magic): 63 × 88 mm.
MM_CARTA_ANCHO = 63
MM_CARTA_ALTO = 88
# Resolución de impresión estándar para el PNG.
DPI_CARTA = 300
# Dimensiones en píxeles a 300 DPI: 63 mm ≈ 744 px, 88 mm ≈ 1039 px.
PX_CARTA_ANCHO = round(MM_CARTA_ANCHO / 25.4 * DPI_CARTA)
PX_CARTA_ALTO = round(MM_CARTA_ALTO / 25.4 * DPI_CARTA)
# Rejilla interna de diseño: las coordenadas del dibujo se definen en esta
# escala y la salida final se ajusta al tamaño físico de la carta.
DISENO_ANCHO = 500
DISENO_ALTO = 700


def _escape(texto: str) -> str:
    """Escapa caracteres especiales de XML en un string."""
    return xml.sax.saxutils.escape(texto or "")

def _envolver_texto(texto: str, max_ancho: int) -> list[str]:
    """Envuelve un texto largo en múltiples líneas."""
    return textwrap.wrap(texto, width=max_ancho)

def _fondo_pergamino(ancho: int, alto: int) -> str:
    """Genera el fondo de pergamino con un gradiente."""
    return f'''
    <defs>
        <linearGradient id="grad-pergamino" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:{COLOR_PERGAMINO_CLARO};stop-opacity:1" />
            <stop offset="100%" style="stop-color:{COLOR_PERGAMINO_OSCURO};stop-opacity:1" />
        </linearGradient>
    </defs>
    <rect width="{ancho}" height="{alto}" fill="url(#grad-pergamino)" />
    '''

def _marco(ancho: int, alto: int) -> str:
    """Genera el marco exterior de la carta."""
    return f'<rect x="15" y="15" width="{ancho - 30}" height="{alto - 30}" fill="none" stroke="{COLOR_BORDE}" stroke-width="4" />'

def _footer(ancho: int, alto: int) -> str:
    """Genera el texto del pie de página."""
    return f'<text x="{ancho / 2}" y="{alto - 25}" font-family="{FONT_FAMILY_SERIF}" font-size="12" fill="{COLOR_BORDE}" text-anchor="middle" font-variant="small-caps">HeroQuest · Ficha de juego</text>'

def _render_stats(
    tipo: TipoCarta,
    entrada: dict,
    ancho: int,
    alto: int
) -> str:
    """Renderiza una carta con la plantilla de estadísticas (personajes, monstruos)."""
    nombre = _escape(entrada.get("nombre", ""))
    subtitulo = _escape(tipo.subtitulo(entrada))
    descripcion = _escape(tipo.descripcion(entrada))
    stats = tipo.stats(entrada)
    simbolo = _escape(tipo.simbolo)

    # --- Banner del Título ---
    banner_svg = f'''
        <g>
            <path d="M 30 40 H {ancho - 30} L {ancho - 40} 75 L {ancho - 30} 110 H 30 L 40 75 Z" fill="{COLOR_BANNER}" stroke="{COLOR_BORDE}" stroke-width="1.5" />
            <text x="{ancho / 2}" y="82" font-family="{FONT_FAMILY_SERIF}" font-size="32" font-weight="bold" fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle">{nombre}</text>
        </g>
    '''

    # --- Área de Arte ---
    arte_y = 125
    arte_alto = 280
    arte_svg = f'''
    <defs>
        <radialGradient id="grad-arte-stats">
            <stop offset="10%" stop-color="{tipo.color}" stop-opacity="0.4" />
            <stop offset="95%" stop-color="{COLOR_BORDE}" stop-opacity="0.2" />
        </radialGradient>
    </defs>
    <rect x="50" y="{arte_y}" width="{ancho - 100}" height="{arte_alto}" fill="url(#grad-pergamino)" stroke="{COLOR_BORDE}" stroke-width="1.5" />
    <circle cx="{ancho/2}" cy="{arte_y + arte_alto/2}" r="120" fill="url(#grad-arte-stats)" />
    <circle cx="{ancho/2}" cy="{arte_y + arte_alto/2}" r="100" fill="none" stroke="{COLOR_BORDE}" stroke-width="1" stroke-opacity="0.5" />
    <text x="{ancho/2}" y="{arte_y + arte_alto/2 + 40}" font-family="serif" font-size="160" fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle" opacity="0.5">{simbolo}</text>
    '''

    # --- Tabla de Estadísticas ---
    stats_y = arte_y + arte_alto + 20
    num_stats = len(stats)
    ancho_col = (ancho - 100) / num_stats if num_stats > 0 else 0
    tabla_svg = '<g transform="translate(50, ' + str(stats_y) + ')">'
    for i, (label, value) in enumerate(stats):
        x_col = i * ancho_col
        # Celda y bordes
        tabla_svg += f'<rect x="{x_col}" y="0" width="{ancho_col}" height="35" fill="{COLOR_CELDA_STAT}" stroke="{COLOR_BORDE}" stroke-width="1" />'
        tabla_svg += f'<rect x="{x_col}" y="35" width="{ancho_col}" height="50" fill="{COLOR_CELDA_STAT}" stroke="{COLOR_BORDE}" stroke-width="1" />'
        # Textos
        tabla_svg += f'<text x="{x_col + ancho_col / 2}" y="22" font-family="{FONT_FAMILY_SERIF}" font-size="14" font-weight="bold" text-anchor="middle" fill="{COLOR_TEXTO_PRINCIPAL}" font-variant="small-caps">{_escape(label)}</text>'
        tabla_svg += f'<text x="{x_col + ancho_col / 2}" y="72" font-family="{FONT_FAMILY_SERIF}" font-size="36" font-weight="bold" text-anchor="middle" fill="{COLOR_TEXTO_PRINCIPAL}">{_escape(value)}</text>'
    tabla_svg += "</g>"

    # --- Descripción y Subtítulo ---
    desc_y = stats_y + 85 + 30
    desc_svg = f'<text x="{ancho / 2}" y="{desc_y - 15}" font-family="{FONT_FAMILY_SERIF}" font-size="16" text-anchor="middle" fill="{COLOR_TEXTO_PRINCIPAL}">{subtitulo}</text>'
    lineas_desc = _envolver_texto(descripcion, 45)
    for i, linea in enumerate(lineas_desc):
        desc_svg += f'<text x="{ancho / 2}" y="{desc_y + 10 + i * 20}" font-family="{FONT_FAMILY_SERIF}" font-style="italic" font-size="15" text-anchor="middle" fill="{COLOR_TEXTO_PRINCIPAL}">{_escape(linea)}</text>'

    return banner_svg + arte_svg + tabla_svg + desc_svg

def _render_descripcion(
    tipo: TipoCarta,
    entrada: dict,
    ancho: int,
    alto: int
) -> str:
    """Renderiza una carta con la plantilla de descripción (objetos, hechizos)."""
    nombre = _escape(entrada.get("nombre", ""))
    subtitulo = _escape(tipo.subtitulo(entrada))
    descripcion = _escape(tipo.descripcion(entrada))
    stats = tipo.stats(entrada)
    simbolo = _escape(tipo.simbolo)

    # --- Título ---
    titulo_svg = f'<text x="{ancho / 2}" y="75" font-family="{FONT_FAMILY_SERIF}" font-size="34" font-weight="bold" fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle">{nombre}</text>'

    # --- Área de Arte ---
    arte_y = 100
    arte_alto = 220
    arte_svg = f'''
        <g>
            <rect x="80" y="{arte_y}" width="{ancho - 160}" height="{arte_alto}" fill="{COLOR_PERGAMINO_CLARO}" stroke="{COLOR_BORDE}" stroke-width="3" />
            <rect x="88" y="{arte_y + 8}" width="{ancho - 176}" height="{arte_alto - 16}" fill="none" stroke="{COLOR_BORDE}" stroke-width="1" />
            <text x="{ancho/2}" y="{arte_y + arte_alto/2 + 45}" font-family="serif" font-size="180" fill="{tipo.color}" text-anchor="middle" opacity="0.8">{simbolo}</text>
        </g>
    '''

    # --- Subtítulo y Descripción ---
    desc_y = arte_y + arte_alto + 45
    desc_svg = f'<text x="{ancho / 2}" y="{desc_y - 15}" font-family="{FONT_FAMILY_SERIF}" font-size="15" text-anchor="middle" fill="{tipo.color}" font-variant="small-caps" font-weight="bold">{subtitulo}</text>'
    lineas_desc = _envolver_texto(descripcion, 38)
    for i, linea in enumerate(lineas_desc):
        desc_svg += f'<text x="60" y="{desc_y + 20 + i * 22}" font-family="{FONT_FAMILY_SERIF}" font-size="18" fill="{COLOR_TEXTO_PRINCIPAL}">{_escape(linea)}</text>'

    # --- Stats inferiores (Coste, etc.) ---
    stats_y = alto - 80
    stats_svg = '<g transform="translate(0, ' + str(stats_y) + ')">'
    if stats:
        # Renderizar como una línea de texto simple
        stat_text = " · ".join([f"{_escape(l)}: {_escape(v)}" for l, v in stats])
        stats_svg += f'<text x="{ancho / 2}" y="0" font-family="{FONT_FAMILY_SERIF}" font-size="16" font-weight="bold" text-anchor="middle" fill="{COLOR_TEXTO_PRINCIPAL}">{stat_text}</text>'
    stats_svg += "</g>"

    return titulo_svg + arte_svg + desc_svg + stats_svg

def render_svg(tipo: TipoCarta, entrada: dict, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO) -> str:
    """
    Devuelve el SVG (str) del anverso de la carta según su familia.

    El dibujo usa las coordenadas de diseño (`ancho` `alto`) y el SVG declara su
    tamaño físico de carta (63 × 88 mm) en píxeles a 300 DPI, para que se
    represente y se imprima con las proporciones reales de una carta de juego.

    Args:
        tipo: La instancia de TipoCarta que define el diseño.
        entrada: Un diccionario con los datos específicos de la carta (nombre, etc.).
        ancho: El ancho de la rejilla de diseño.
        alto: El alto de la rejilla de diseño.

    Returns:
        Un string con el código SVG completo de la carta.
    """
    # Escala del tamaño físico (px) respecto a la rejilla de diseño.
    px_ancho = round(ancho * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" width="{px_ancho}" height="{px_alto}">',
        _fondo_pergamino(ancho, alto),
        _marco(ancho, alto)
    ]

    # Dispatcher de familia de renderizado
    match tipo.familia:
        case "stats":
            svg_parts.append(_render_stats(tipo, entrada, ancho, alto))
        case "descripcion":
            svg_parts.append(_render_descripcion(tipo, entrada, ancho, alto))
        case _:
            # Fallback por si hay una familia no reconocida
            error_msg = f"Familia de carta desconocida: {tipo.familia}"
            svg_parts.append(f'<text x="50" y="50" fill="red">{error_msg}</text>')

    svg_parts.append(_footer(ancho, alto))
    svg_parts.append("</svg>")

    return "\n".join(svg_parts)


# ============================================================================
# Render a PNG rasterizando el SVG con resvg (resvg_py)
# ============================================================================
#
# El SVG es la única fuente de verdad del diseño de la carta; el PNG se obtiene
# rasterizándolo a la resolución física real de la carta (63 × 88 mm a 300 DPI).

def render_png(tipo: TipoCarta, entrada: dict, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO) -> Image.Image:
    """Devuelve una imagen Pillow del anverso de la carta rasterizando su SVG.

    El SVG se dibuja en la rejilla de diseño y se rasteriza al tamaño físico de
    la carta (63 × 88 mm, 744 × 1039 px a 300 DPI) con resvg (resvg_py).
    """
    import io
    from PIL import Image
    import resvg_py

    svg = render_svg(tipo, entrada, ancho, alto)
    px_ancho = round(ancho * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    datos = resvg_py.svg_to_bytes(
        svg_string=svg,
        width=px_ancho,
        height=px_alto,
        background="#ffffff",
    )
    return Image.open(io.BytesIO(datos)).convert("RGB")


if __name__ == "__main__":
    """
    Punto de entrada para pruebas y demostración.
    Genera ejemplos de cartas y muestra la longitud de su SVG.
    """
    # Para ejecutar este script directamente, necesitamos asegurarnos de que
    # el paquete `tipos_carta` esté en el path. Se asume que se ejecuta
    # desde el directorio `scripts`.
    import tipos_carta as tc

    print("--- Iniciando smoke test de render_carta.py ---")

    # 1. Personaje (familia: stats)
    try:
        entrada_heroe = {
            'nombre': 'Bárbaro',
            'clase': 'Bárbaro',
            'ataque': 3,
            'defensa': 3,
            'cuerpo': 8,
            'mente': 2,
            'movimiento': 2,
            'descripcion': 'Guerrero salvaje de las lejanas y yermas tierras del norte. Su habilidad en el combate es legendaria.'
        }
        tipo_personaje = tc.obtener('personaje')
        svg_heroe = render_svg(tipo_personaje, entrada_heroe)
        # with open("test_personaje.svg", "w", encoding="utf-8") as f:
        #     f.write(svg_heroe)
        print(f"OK Personaje 'Bárbaro', longitud SVG: {len(svg_heroe)}")
        assert svg_heroe.startswith('<svg') and svg_heroe.strip().endswith('</svg>')
    except Exception as e:
        print(f"ERROR al renderizar Personaje: {e}")

    # 2. Arma (familia: descripcion)
    try:
        entrada_arma = {
            'nombre': 'Espada Larga',
            'tipo': 'Arma cuerpo a cuerpo',
            'ataque': 3,
            'defensa': 0,
            'coste': 350,
            'descripcion': 'Mientras la empuñas, tiras 3 dados de ataque en combate cuerpo a cuerpo. Es una hoja de excelente calidad forjada por enanos.'
        }
        tipo_arma = tc.obtener('arma')
        svg_arma = render_svg(tipo_arma, entrada_arma)
        # with open("test_arma.svg", "w", encoding="utf-8") as f:
        #     f.write(svg_arma)
        print(f"OK Arma 'Espada Larga', longitud SVG: {len(svg_arma)}")
        assert svg_arma.startswith('<svg') and svg_arma.strip().endswith('</svg>')
    except Exception as e:
        print(f"ERROR al renderizar Arma: {e}")

    # 3. Hechizo (familia: descripcion)
    try:
        entrada_hechizo = {
            'nombre': 'Bola de Fuego',
            'escuela': 'Fuego',
            'coste_mente': 2,
            'descripcion': 'Lanza una bola de fuego a cualquier monstruo que puedas ver. El monstruo sufre 2 puntos de daño (no se tira dado de defensa).'
        }
        tipo_hechizo = tc.obtener('hechizo')
        svg_hechizo = render_svg(tipo_hechizo, entrada_hechizo)
        # with open("test_hechizo.svg", "w", encoding="utf-8") as f:
        #     f.write(svg_hechizo)
        print(f"OK Hechizo 'Bola de Fuego', longitud SVG: {len(svg_hechizo)}")
        assert svg_hechizo.startswith('<svg') and svg_hechizo.strip().endswith('</svg>')
    except Exception as e:
        print(f"ERROR al renderizar Hechizo: {e}")

    # 4. Rasterizado del SVG a PNG (tamaño físico real de carta)
    try:
        img = render_png(tipo_arma, entrada_arma)
        print(f"OK PNG Arma 'Espada Larga': {img.size}, modo {img.mode}")
        assert img.size == (PX_CARTA_ANCHO, PX_CARTA_ALTO), img.size
    except Exception as e:
        print(f"ERROR al rasterizar PNG: {e}")

    print("--- Smoke test finalizado ---")

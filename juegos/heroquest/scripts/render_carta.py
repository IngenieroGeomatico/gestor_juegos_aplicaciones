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
from pathlib import Path
from typing import TYPE_CHECKING

import data_store

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

# Hoja plegable (anverso | reverso lado a lado): el doble de ancho.
DISENO_DOBLE_ANCHO = DISENO_ANCHO * 2
PX_CARTA_DOBLE_ANCHO = PX_CARTA_ANCHO * 2

# Categoría del reverso por defecto: se deriva del grupo de la foto
# (p. ej. 'equipo_back.jpg' -> 'equipo'). Overridable por parámetro.
LEYENDA_VERSO: str | None = None

# Carpeta con el arte de los anversos: una imagen por carta.
ARTE_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte"
# Extensiones admitidas para el arte embebido (por orden de prioridad).
ARTE_EXTENSIONES = ("png", "jpg", "jpeg", "webp")
# Carpeta con fondos alternativos para el reverso de la carta.
FONDOS_DIR = Path(__file__).resolve().parent.parent / "sources" / "arte_fondos"


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
        <defs>
            <linearGradient id="grad-banner" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#fbf4e3" />
                <stop offset="100%" stop-color="#ecdcc0" />
            </linearGradient>
        </defs>
        <g>
            <path d="M 30 40 H {ancho - 30} L {ancho - 40} 75 L {ancho - 30} 110 H 30 L 40 75 Z" fill="url(#grad-banner)" stroke="{COLOR_BORDE}" stroke-width="1.5" />
            <text x="{ancho / 2}" y="82" font-family="{FONT_FAMILY_SERIF}" font-size="32" font-weight="bold" fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle">{nombre}</text>
            <rect x="150" y="112" width="{ancho - 300}" height="3" fill="{tipo.color}" opacity="0.6" />
        </g>
    '''

    # --- Área de Arte ---
    arte_x = 50
    arte_y = 125
    arte_alto = 280
    arte_ancho = ancho - 100
    radio = 16
    # Zona interior por debajo de la franja de acento.
    img_x = arte_x + 4
    img_y = arte_y + 20
    img_ancho = arte_ancho - 8
    img_alto = arte_alto - 24
    ruta_arte = _ruta_arte(tipo, entrada)
    if ruta_arte:
        interior = (f'<image x="{img_x}" y="{img_y}" width="{img_ancho}" height="{img_alto}" '
                    f'href="{_imagen_data_uri(ruta_arte, img_ancho, img_alto)}" />')
    else:
        interior = (f'<circle cx="{ancho / 2}" cy="{arte_y + (arte_alto + 20) / 2}" '
                    f'r="105" fill="{tipo.color}" fill-opacity="0.28" />'
                    f'<text x="{ancho / 2}" y="{arte_y + (arte_alto + 20) / 2 + 55}" '
                    f'font-family="serif" font-size="150" fill="#ecd9a8" text-anchor="middle">{simbolo}</text>')
    # Degradado de profundidad sobre el interior.
    interior += (f'<linearGradient id="grad-humo" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="60%" stop-color="#000000" stop-opacity="0" />'
                 f'<stop offset="100%" stop-color="#000000" stop-opacity="0.35" /></linearGradient>'
                 f'<rect x="{img_x}" y="{img_y}" width="{img_ancho}" height="{img_alto}" fill="url(#grad-humo)" />')
    arte_svg = f'''
    <defs>
        <linearGradient id="grad-arte-stats" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#24150d" />
            <stop offset="100%" stop-color="{tipo.color}" />
        </linearGradient>
        <clipPath id="clip-arte-stats"><rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" /></clipPath>
    </defs>
    <rect x="{arte_x + 6}" y="{arte_y + 7}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" fill="#000000" opacity="0.20" />
    <rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" fill="url(#grad-arte-stats)" stroke="{COLOR_BORDE}" stroke-width="2.5" />
    <rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="18" rx="9" fill="{tipo.color}" />
    <g clip-path="url(#clip-arte-stats)">
        {interior}
    </g>
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
    titulo_svg = (f'<text x="{ancho / 2}" y="75" font-family="{FONT_FAMILY_SERIF}" '
                  f'font-size="34" font-weight="bold" fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle">{nombre}</text>'
                  f'<rect x="170" y="88" width="{ancho - 340}" height="3" fill="{tipo.color}" opacity="0.6" />')

    # --- Área de Arte ---
    arte_x = 80
    arte_y = 105
    arte_alto = 220
    arte_ancho = ancho - 160
    radio = 16
    img_x = arte_x + 4
    img_y = arte_y + 18
    img_ancho = arte_ancho - 8
    img_alto = arte_alto - 22
    ruta_arte = _ruta_arte(tipo, entrada)
    if ruta_arte:
        interior = (f'<image x="{img_x}" y="{img_y}" width="{img_ancho}" height="{img_alto}" '
                    f'href="{_imagen_data_uri(ruta_arte, img_ancho, img_alto)}" />')
    else:
        interior = (f'<text x="{ancho / 2}" y="{arte_y + (arte_alto + 18) / 2 + 15}" '
                    f'font-family="serif" font-size="150" fill="{tipo.color}" fill-opacity="0.85" '
                    f'text-anchor="middle">{simbolo}</text>')
    interior += (f'<linearGradient id="grad-humo-desc" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="60%" stop-color="#000000" stop-opacity="0" />'
                 f'<stop offset="100%" stop-color="#000000" stop-opacity="0.30" /></linearGradient>'
                 f'<rect x="{img_x}" y="{img_y}" width="{img_ancho}" height="{img_alto}" fill="url(#grad-humo-desc)" />')
    arte_svg = f'''
        <defs>
            <linearGradient id="grad-arte-desc" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#24150d" />
                <stop offset="100%" stop-color="{tipo.color}" />
            </linearGradient>
            <clipPath id="clip-arte-desc"><rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" /></clipPath>
        </defs>
        <g>
            <rect x="{arte_x + 6}" y="{arte_y + 7}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" fill="#000000" opacity="0.20" />
            <rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" fill="url(#grad-arte-desc)" stroke="{COLOR_BORDE}" stroke-width="2.5" />
            <rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="16" rx="8" fill="{tipo.color}" />
            <g clip-path="url(#clip-arte-desc)">
                {interior}
            </g>
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

def _contenido_svg(tipo: TipoCarta, entrada: dict, ancho: int, alto: int) -> str:
    """Devuelve el interior del SVG del anverso (sin la etiqueta <svg> raíz)."""
    svg_parts = [
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
    return "\n".join(svg_parts)

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
        _contenido_svg(tipo, entrada, ancho, alto),
        "</svg>",
    ]
    return "\n".join(svg_parts)


def _ruta_arte(tipo: TipoCarta, entrada: dict) -> Path | None:
    """Localiza la imagen de arte del anverso para una carta, o None.

    Orden de búsqueda:
    1. La entrada puede declarar `arte` con el nombre de un fichero en
       `sources/arte/` (p. ej. `"arte": "espada_corta.png"`).
    2. Convención por nombre: `sources/arte/<slug(nombre)>.png|jpg|jpeg|webp`.
    """
    candidatos: list[str] = []
    declarado = entrada.get("arte")
    if declarado:
        candidatos.append(str(declarado))
    candidatos.append(data_store.slug(entrada.get("nombre", "")))
    for nombre in candidatos:
        for ext in ARTE_EXTENSIONES:
            ruta = ARTE_DIR / f"{nombre}.{ext}"
            if ruta.exists():
                return ruta
    return None


def _imagen_data_uri(ruta: Path, ancho: int, alto: int) -> str:
    """Incrusta una imagen recortada "cover" a la rejilla como data URI."""
    import base64
    import io
    from PIL import Image, ImageOps

    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im = ImageOps.fit(im, (ancho, alto), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def _ruta_reverso(tipo: TipoCarta, fondo_verso: str | None = None) -> Path:
    """Ruta de la imagen de fondo del reverso.

    Prioridad:
    1. `fondo_verso` explícito → ese fichero de `sources/arte_fondos/` (override).
    2. Por defecto: el fondo temático de la categoría de la carta
       (`sources/arte_fondos/<categoria>_back.png`, p. ej. `enemigo_back.png`),
       si existe.
    3. Si no hay fondo temático: el reverso estándar del tipo (`tipo.reverso()`,
       la foto de la carta real en `sources/reversos/`).
    """
    if fondo_verso:
        ruta = FONDOS_DIR / fondo_verso
        if not ruta.exists():
            raise FileNotFoundError(f"No existe el fondo de reverso: {ruta}")
        return ruta
    tematico = FONDOS_DIR / f"{_categoria_verso(tipo)}_back.png"
    if tematico.exists():
        return tematico
    return tipo.reverso()


def _reverso_data_uri(tipo: TipoCarta, ancho: int, alto: int,
                      fondo_verso: str | None = None) -> str | None:
    """Foto del reverso como data URI, recortada y reescalada a la rejilla.

    Hace un recorte "cover" para llenar exactamente el panel de la carta
    (proporción 63 × 88) y la reescala a la resolución de diseño, para que el
    SVG incrustado sea ligero. `fondo_verso` permite elegir un fondo de
    `sources/arte_fondos/` en lugar de la foto estándar del tipo.
    """
    ruta = _ruta_reverso(tipo, fondo_verso)
    if not ruta.exists():
        return None
    return _imagen_data_uri(ruta, ancho, alto)


def _categoria_verso(tipo: TipoCarta) -> str:
    """Categoría del reverso: el grupo de la carta ('equipo', 'enemigo', ...).

    Se deriva del nombre de la foto de reverso: 'equipo_back.jpg' -> 'equipo'.
    """
    return Path(tipo.reverso_img).stem.split("_")[0]


def _contenido_verso(tipo: TipoCarta, ancho: int, alto: int, leyenda: str | None = LEYENDA_VERSO,
                     fondo_verso: str | None = None) -> str:
    """Interior del SVG del reverso: imagen como fondo + capa vectorial.

    `leyenda` es la leyenda inferior; si es None se usa la categoría del tipo
    de carta ('equipo', 'enemigo', 'heroe', 'tesoro', ...). `fondo_verso`
    selecciona un fondo de `sources/arte_fondos/` en lugar de la foto estándar.
    """
    if not leyenda:
        leyenda = _categoria_verso(tipo)
    foto = _reverso_data_uri(tipo, ancho, alto, fondo_verso)
    if foto:
        fondo = (f'<image x="0" y="0" width="{ancho}" height="{alto}" '
                 f'href="{foto}" preserveAspectRatio="xMidYMid slice" />')
    else:
        fondo = _fondo_pergamino(ancho, alto)
    banner = (f'<path d="M {ancho / 2 - 140} 40 H {ancho / 2 + 140} '
              f'L {ancho / 2 + 120} 75 L {ancho / 2 + 140} 110 '
              f'H {ancho / 2 - 140} L {ancho / 2 - 120} 75 Z" '
              f'fill="{COLOR_BANNER}" fill-opacity="0.92" stroke="{COLOR_BORDE}" stroke-width="1.5" />')
    titulo = (f'<text x="{ancho / 2}" y="82" font-family="{FONT_FAMILY_SERIF}" '
              f'font-size="34" font-weight="bold" fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle">HeroQuest</text>')
    # Leyenda inferior en una banda similar a la superior.
    bajo_y = alto - 120
    leyenda_banda = (f'<path d="M {ancho / 2 - 130} {bajo_y} H {ancho / 2 + 130} '
                     f'L {ancho / 2 + 108} {bajo_y + 22} L {ancho / 2 + 130} {bajo_y + 44} '
                     f'H {ancho / 2 - 130} L {ancho / 2 - 108} {bajo_y + 22} Z" '
                     f'fill="{COLOR_BANNER}" fill-opacity="0.92" stroke="{COLOR_BORDE}" stroke-width="1.5" />')
    leyenda_texto = (f'<text x="{ancho / 2}" y="{bajo_y + 26}" font-family="{FONT_FAMILY_SERIF}" '
                     f'font-size="14" font-weight="bold" font-variant="small-caps" '
                     f'fill="{COLOR_TEXTO_PRINCIPAL}" text-anchor="middle">{_escape(leyenda)}</text>')
    return "\n".join([
        fondo,
        f'<rect x="12" y="12" width="{ancho - 24}" height="{alto - 24}" fill="none" '
        f'stroke="{COLOR_BORDE}" stroke-width="3" />',
        f'<rect x="20" y="20" width="{ancho - 40}" height="{alto - 40}" fill="none" '
        f'stroke="{COLOR_BORDE}" stroke-width="1" />',
        banner,
        titulo,
        leyenda_banda,
        leyenda_texto,
    ])


def render_verso_svg(tipo: TipoCarta, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO,
                     leyenda: str | None = LEYENDA_VERSO, fondo_verso: str | None = None) -> str:
    """Devuelve el SVG (str) del reverso de la carta."""
    px_ancho = round(ancho * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" width="{px_ancho}" height="{px_alto}">',
        _contenido_verso(tipo, ancho, alto, leyenda, fondo_verso),
        "</svg>",
    ])


def render_svg_doble(tipo: TipoCarta, entrada: dict, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO,
                     leyenda: str | None = LEYENDA_VERSO, fondo_verso: str | None = None) -> str:
    """SVG de la hoja plegable: anverso | reverso lado a lado (126 × 88 mm).

    Se dobla por la línea vertical central para obtener la carta completa con
    el anverso por un lado y el reverso por el otro. Ambos paneles se dibujan
    con su orientación normal (las letras del reverso se ven bien).
    """
    ancho_doble = ancho * 2
    frente = f'<g transform="translate(0,0)">{_contenido_svg(tipo, entrada, ancho, alto)}</g>'
    verso = f'<g transform="translate({ancho},0)">{_contenido_verso(tipo, ancho, alto, leyenda, fondo_verso)}</g>'
    pliegue = "\n".join([
        f'<line x1="{ancho}" y1="0" x2="{ancho}" y2="{alto}" stroke="{COLOR_BORDE}" '
        f'stroke-width="1.5" stroke-dasharray="8 6" />',
        f'<text x="{ancho}" y="{alto - 12}" font-family="{FONT_FAMILY_SERIF}" font-size="11" '
        f'fill="{COLOR_BORDE}" text-anchor="middle">— pliegue —</text>',
    ])
    px_ancho = round(ancho_doble * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho_doble} {alto}" width="{px_ancho}" height="{px_alto}">',
        frente,
        verso,
        pliegue,
        "</svg>",
    ])


# ============================================================================
# Render a PNG rasterizando el SVG con resvg (resvg_py)
# ============================================================================
#
# El SVG es la única fuente de verdad del diseño de la carta; el PNG se obtiene
# rasterizándolo a la resolución física real de la carta (63 × 88 mm a 300 DPI).

def _rasterizar(svg: str, px_ancho: int, px_alto: int) -> Image.Image:
    """Rasteriza un SVG a PNG con resvg y lo devuelve como imagen Pillow."""
    import io
    from PIL import Image
    import resvg_py

    datos = resvg_py.svg_to_bytes(
        svg_string=svg,
        width=px_ancho,
        height=px_alto,
        background="#ffffff",
    )
    return Image.open(io.BytesIO(datos)).convert("RGB")


def render_png(tipo: TipoCarta, entrada: dict, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO) -> Image.Image:
    """Devuelve una imagen Pillow del anverso de la carta rasterizando su SVG.

    El SVG se dibuja en la rejilla de diseño y se rasteriza al tamaño físico de
    la carta (63 × 88 mm, 744 × 1039 px a 300 DPI) con resvg (resvg_py).
    """
    svg = render_svg(tipo, entrada, ancho, alto)
    px_ancho = round(ancho * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    return _rasterizar(svg, px_ancho, px_alto)


def render_png_verso(tipo: TipoCarta, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO,
                     leyenda: str | None = LEYENDA_VERSO, fondo_verso: str | None = None) -> Image.Image:
    """Devuelve una imagen Pillow del reverso de la carta (744 × 1039 px)."""
    svg = render_verso_svg(tipo, ancho, alto, leyenda, fondo_verso)
    px_ancho = round(ancho * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    return _rasterizar(svg, px_ancho, px_alto)


def render_png_doble(tipo: TipoCarta, entrada: dict, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO,
                     leyenda: str | None = LEYENDA_VERSO, fondo_verso: str | None = None) -> Image.Image:
    """Devuelve la hoja plegable (anverso | reverso) a 126 × 88 mm (1488 × 1039 px)."""
    svg = render_svg_doble(tipo, entrada, ancho, alto, leyenda, fondo_verso)
    px_ancho = round(ancho * 2 * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    return _rasterizar(svg, px_ancho, px_alto)


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

    # 5. Reverso y hoja plegable (anverso | reverso)
    try:
        svg_verso = render_verso_svg(tipo_arma)
        print(f"OK Reverso SVG, longitud: {len(svg_verso)}")
        assert svg_verso.startswith('<svg') and svg_verso.strip().endswith('</svg>')
        img_doble = render_png_doble(tipo_arma, entrada_arma)
        print(f"OK Hoja plegable PNG: {img_doble.size}")
        assert img_doble.size == (PX_CARTA_DOBLE_ANCHO, PX_CARTA_ALTO), img_doble.size
    except Exception as e:
        print(f"ERROR al generar reverso/hoja plegable: {e}")

    print("--- Smoke test finalizado ---")

# -*- coding: utf-8 -*-
"""
Módulo para renderizar cartas de HeroQuest a formato SVG.

Este módulo proporciona funciones para generar una representación SVG de varias
tarjetas de juego, imitando el estilo de las cartas físicas originales.
Utiliza un sistema de tipos de carta para determinar el diseño y el contenido.
"""
from __future__ import annotations
import re
import xml.sax.saxutils
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import data_store
import plantillas

if TYPE_CHECKING:
    # Evita la importación circular y permite el tipado
    from tipos_carta import TipoCarta

# --- Constantes de Estilo ---
# El "chrome" de la carta (fondo, marco, banners, leyendas) vive ahora en las
# plantillas SVG de sources/plantillas/ (ver plantillas.py). Aquí solo quedan
# los colores que usa el contenido dinámico que Python genera (arte, tabla de
# stats, descripción), que se incrustan dentro de las anclas de la plantilla.
# Familia tipográfica de la carta. Albert Sans (libre, OFL-1.1, ver
# sources/fuentes/) da el estilo humanista de las cartas HQ 2021; Georgia actúa
# de reserva si no está instalada en el sistema que rasteriza el SVG.
FONT_FAMILY_CARTA = "'Albert Sans', Georgia, 'Times New Roman', serif"
COLOR_BORDE = "#4d2c1b"
COLOR_TEXTO_PRINCIPAL = "#3a2416"
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

def _frag_arte(
    tipo: TipoCarta,
    entrada: dict,
    geom: dict[str, float],
    sufijo: str,
    radio: int = 16,
    franja: int = 18,
    fallback_circulo: bool = True,
) -> str:
    """Genera el fragmento SVG del área de arte para el ancla `geom`.

    Dibuja la sombra, el recuadro con degradado (de #24150d al color del tipo),
    la franja de acento superior y, recortada, la imagen del arte (o un símbolo
    de reserva). `sufijo` hace únicos los ids de defs para evitar colisiones al
    componer varias cartas en un mismo SVG.
    """
    arte_x = geom["x"]
    arte_y = geom["y"]
    arte_ancho = geom["width"]
    arte_alto = geom["height"]
    simbolo = _escape(tipo.simbolo)

    # Zona interior por debajo de la franja de acento.
    img_x = arte_x + 4
    img_y = arte_y + franja + 2
    img_ancho = arte_ancho - 8
    img_alto = arte_alto - (franja + 6)
    cx = arte_x + arte_ancho / 2

    ruta_arte = _ruta_arte(tipo, entrada)
    if ruta_arte:
        interior = (f'<image x="{img_x}" y="{img_y}" width="{img_ancho}" height="{img_alto}" '
                    f'href="{_imagen_data_uri(ruta_arte, round(img_ancho), round(img_alto))}" />')
    elif fallback_circulo:
        cy = arte_y + (arte_alto + franja) / 2
        interior = (f'<circle cx="{cx}" cy="{cy}" '
                    f'r="105" fill="{tipo.color}" fill-opacity="0.28" />'
                    f'<text x="{cx}" y="{cy + 55}" '
                    f'font-family="serif" font-size="150" fill="#ecd9a8" text-anchor="middle">{simbolo}</text>')
    else:
        interior = (f'<text x="{cx}" y="{arte_y + (arte_alto + franja) / 2 + 15}" '
                    f'font-family="serif" font-size="150" fill="{tipo.color}" fill-opacity="0.85" '
                    f'text-anchor="middle">{simbolo}</text>')

    # Degradado de profundidad sobre el interior.
    interior += (f'<linearGradient id="grad-humo-{sufijo}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="60%" stop-color="#000000" stop-opacity="0" />'
                 f'<stop offset="100%" stop-color="#000000" stop-opacity="0.35" /></linearGradient>'
                 f'<rect x="{img_x}" y="{img_y}" width="{img_ancho}" height="{img_alto}" fill="url(#grad-humo-{sufijo})" />')

    return f'''
    <defs>
        <linearGradient id="grad-arte-{sufijo}" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#24150d" />
            <stop offset="100%" stop-color="{tipo.color}" />
        </linearGradient>
        <clipPath id="clip-arte-{sufijo}"><rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" /></clipPath>
    </defs>
    <rect x="{arte_x + 6}" y="{arte_y + 7}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" fill="#000000" opacity="0.20" />
    <rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{arte_alto}" rx="{radio}" fill="url(#grad-arte-{sufijo})" stroke="{COLOR_BORDE}" stroke-width="2.5" />
    <rect x="{arte_x}" y="{arte_y}" width="{arte_ancho}" height="{franja}" rx="{franja / 2}" fill="{tipo.color}" />
    <g clip-path="url(#clip-arte-{sufijo})">
        {interior}
    </g>
    '''


# Tamaño de diseño de la plantilla stats_cuadro.svg (su viewBox).
_STATS_CUADRO_ANCHO = 420
_STATS_CUADRO_ALTO = 60


def _frag_tabla_stats(tipo: TipoCarta, entrada: dict, geom: dict[str, float]) -> str:
    """Coloca el cuadro de estadísticas (plantilla `stats_cuadro.svg`) en `geom`.

    El cuadro es una plantilla editable de 5 columnas (héroe/monstruo siempre
    tienen 5 stats). Se rellena con las etiquetas/valores y se posiciona dentro
    del ancla `ph-stats`, escalándolo a esa caja para que quede superpuesto
    sobre el arte.
    """
    stats = tipo.stats(entrada)
    if not stats:
        return ""

    textos: dict[str, str] = {"COLOR": tipo.color}
    # Rellena hasta 5 columnas; si sobran stats se ignoran, si faltan se vacían.
    for i in range(1, 6):
        if i <= len(stats):
            label, value = stats[i - 1]
        else:
            label, value = "", ""
        textos[f"LABEL{i}"] = label
        textos[f"VALOR{i}"] = value

    tpl = plantillas.cargar("stats_cuadro")
    cuadro = plantillas.render(tpl, textos=textos)

    # El cuadro usa su propio viewBox (420×60); lo posicionamos y escalamos al
    # ancla ph-stats.
    escala_x = geom["width"] / _STATS_CUADRO_ANCHO
    escala_y = geom["height"] / _STATS_CUADRO_ALTO
    return (f'<g transform="translate({geom["x"]}, {geom["y"]}) '
            f'scale({escala_x}, {escala_y})">{cuadro}</g>')


def _frag_descripcion(
    descripcion: str,
    geom: dict[str, float],
    ancho_wrap: int,
    tam_fuente: int,
    interlineado: int,
    centrado: bool,
    cursiva: bool = False,
) -> str:
    """Genera las líneas de texto de una descripción dentro del ancla `geom`."""
    if not descripcion:
        return ""
    lineas = _envolver_texto(descripcion, ancho_wrap)
    x = geom["x"] + (geom["width"] / 2 if centrado else 0)
    anchor = "middle" if centrado else "start"
    estilo = ' font-style="italic"' if cursiva else ""
    partes = []
    for i, linea in enumerate(lineas):
        y = geom["y"] + tam_fuente + i * interlineado
        partes.append(
            f'<text x="{x}" y="{y}" font-family="{FONT_FAMILY_CARTA}" font-size="{tam_fuente}"{estilo} '
            f'text-anchor="{anchor}" fill="{COLOR_TEXTO_PRINCIPAL}">{_escape(linea)}</text>')
    return "".join(partes)


def _frag_stats_linea(tipo: TipoCarta, entrada: dict, geom: dict[str, float]) -> str:
    """Genera la línea única de estadísticas (Coste, etc.) para el ancla `geom`."""
    stats = tipo.stats(entrada)
    if not stats:
        return ""
    x = geom["x"] + geom["width"] / 2
    y = geom["y"] + geom["height"] / 2 + 6
    texto = " · ".join(f"{_escape(l)}: {_escape(v)}" for l, v in stats)
    return (f'<text x="{x}" y="{y}" font-family="{FONT_FAMILY_CARTA}" font-size="16" '
            f'font-weight="bold" text-anchor="middle" fill="{COLOR_TEXTO_PRINCIPAL}">{texto}</text>')


def _render_stats(tipo: TipoCarta, entrada: dict, ancho: int, alto: int) -> str:
    """Renderiza el anverso de la familia 'stats' (héroes, monstruos).

    Usa la plantilla `hero-stats.svg` para el chrome (marco, banner, banda de
    stats) y rellena las anclas ph-arte (arte a 4/5) y ph-stats (tabla).
    """
    tpl = plantillas.cargar("hero-stats")
    geom_arte = plantillas.ancla(tpl, "ph-arte") or {"x": 40, "y": 120, "width": 420, "height": 500}
    geom_stats = plantillas.ancla(tpl, "ph-stats") or {"x": 40, "y": 620, "width": 420, "height": 55}

    arte = _frag_arte(tipo, entrada, geom_arte, sufijo="stats", franja=20)
    tabla = _frag_tabla_stats(tipo, entrada, geom_stats)

    return plantillas.render(
        tpl,
        textos={
            "NOMBRE": entrada.get("nombre", ""),
            "SUBTITULO": tipo.subtitulo(entrada),
            "COLOR": tipo.color,
        },
        bloques={"ph-arte": arte, "ph-stats": tabla},
    )


def _render_hero_card(tipo: TipoCarta, entrada: dict, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO) -> str:
    """Renderiza la cara delantera de un héroe usando hero-card-up.svg como plantilla padre.

    Apila las capas en el orden especificado:
    1. Fondo (parchment.png) - se busca en sources/arte_fondos/ por defecto o se usa el de la categoría
    2. Arte (ph-arte) - imagen del héroe
    3. Stats (ph-stats) - tabla de 5 estadísticas
    4. Ribbon (pg-ribbon) - banda con tipo de héroe
    5. Icono (ph-icon) - ícono de clase

    Cada capa es opcional: si no existe un elemento ph-* correspondiente, se omite.
    """
    tpl = plantillas.cargar("hero-card-up")

    # Geometría de las anclas de la plantilla padre
    geom_arte = plantillas.ancla(tpl, "ph-arte") or {"x": -46, "y": 28, "width": 227, "height": 279}
    geom_stats = plantillas.ancla(tpl, "ph-stats") or {"x": -32, "y": 256, "width": 197, "height": 97}

    # 1. Generar fragmento de arte
    arte_fragment = None
    if entrada.get("arte") or entrada.get("nombre"):
        arte_fragment = _frag_arte(tipo, entrada, geom_arte, sufijo="hero", franja=20)

    # 2. Generar fragmento de stats
    stats_fragment = None
    if True:  # Los héroes siempre tienen stats
        stats = tipo.stats(entrada)
        textos_stats: dict[str, str] = {"COLOR": tipo.color}
        # Rellena hasta 5 columnas
        for i in range(1, 6):
            if i <= len(stats):
                label, value = stats[i - 1]
            else:
                label, value = "", ""
            textos_stats[f"LABEL{i}"] = label
            textos_stats[f"VALOR{i}"] = value
        tpl_stats = plantillas.cargar("stats_cuadro")
        cuadro = plantillas.render(tpl_stats, textos=textos_stats)
        escala_x = geom_stats["width"] / 420
        escala_y = geom_stats["height"] / 60
        stats_fragment = (f'<g transform="translate({geom_stats["x"]}, {geom_stats["y"]}) '
                         f'scale({escala_x}, {escala_y})">{cuadro}</g>')

    # 3. Generar fragmento de ribbon (tipo de héroe)
    ribbon_fragment = None
    subtitulo = tipo.subtitulo(entrada)
    if subtitulo:
        tpl_ribbon = plantillas.cargar("ribbon")
        # Buscar ancla ph-ribbon o ph-titulo en la plantilla ribbon
        geom_ribbon = plantillas.ancla(tpl_ribbon, "ph-ribbon") or \
                      plantillas.ancla(tpl_ribbon, "ph-titulo") or \
                      {"x": 0, "y": 0, "width": 300, "height": 40}
        # Insertar el subtítulo en la plantilla
        # El ribbon SVG usa marcadores o texto directo; insertamos el texto
        ribbon_fragment = f'<text x="{geom_ribbon["x"] + 10}" y="{geom_ribbon["y"] + 20}" font-family="Albert Sans" font-size="14" fill="#3a2416">{__import__("xml").sax.saxutils.escape(subtitulo)}</text>'

    # 4. Generar fragmento de icono (ph-icon)
    icon_fragment = None
    geom_icon = plantillas.ancla(tpl, "ph-icon") or {"x": 0, "y": 0, "width": 64, "height": 64}
    # Buscar arte del icono - usar símbolo del tipo o arte declarado
    simbolo = tipo.simbolo
    if simbolo:
        icon_fragment = (f'<text x="{geom_icon["x"] + geom_icon["width"] / 2}" y="{geom_icon["y"] + geom_icon["height"] / 2 + 15}" '
                        f'font-family="serif" font-size="32" fill="{tipo.color}" text-anchor="middle">{__import__("xml").sax.saxutils.escape(simbolo)}</text>')

    # Construir el SVG final sustituyendo las anclas
    resultado = tpl

    # Sustituir bloques (anclas ph-*)
    bloques = {}
    if arte_fragment:
        bloques["ph-arte"] = arte_fragment
    if stats_fragment:
        bloques["ph-stats"] = stats_fragment
    if ribbon_fragment:
        bloques["ph-ribbon"] = ribbon_fragment
    if icon_fragment:
        bloques["ph-icon"] = icon_fragment

    # Aplicar sustitución de bloques
    for id_ancla, fragmento in bloques.items():
        resultado = plantillas._eliminar_ancla(resultado, id_ancla, fragmento or "")

    # Eliminar anclas no utilizadas
    for id_ancla in re.findall(r'<rect\b[^>]*\bid="(ph-[\w-]+)"', resultado):
        if id_ancla not in bloques:
            resultado = plantillas._eliminar_ancla(resultado, id_ancla, "")

    # Sustituir marcadores de texto si la plantilla los usa (aunque hero-card-up no los tiene)
    # por si hay compatibilidad futura
    textos = {
        "NOMBRE": entrada.get("nombre", ""),
        "SUBTITULO": tipo.subtitulo(entrada),
        "COLOR": tipo.color,
    }
    resultado = _render_text_markers(resultado, textos)

    # Devolver solo el interior del <svg>
    # Buscar inicio y fin de svg
    inicio = resultado.find("<svg")
    if inicio == -1:
        return resultado
    apertura_fin = resultado.find(">", inicio)
    cierre = resultado.rfind("</svg>")
    if apertura_fin == -1 or cierre == -1:
        return resultado
    return resultado[apertura_fin + 1:cierre]


def _render_descripcion(tipo: TipoCarta, entrada: dict, ancho: int, alto: int) -> str:
    """Renderiza el anverso de la familia 'descripcion' (armas, hechizos...).

    Usa la plantilla `anverso_descripcion.svg` para el chrome y rellena las
    anclas ph-arte, ph-descripcion y ph-stats.
    """
    tpl = plantillas.cargar("anverso_descripcion")
    geom_arte = plantillas.ancla(tpl, "ph-arte") or {"x": 80, "y": 105, "width": 340, "height": 220}
    geom_desc = plantillas.ancla(tpl, "ph-descripcion") or {"x": 60, "y": 375, "width": 380, "height": 230}
    geom_stats = plantillas.ancla(tpl, "ph-stats") or {"x": 60, "y": 608, "width": 380, "height": 24}

    arte = _frag_arte(tipo, entrada, geom_arte, sufijo="desc", franja=16, fallback_circulo=False)
    desc = _frag_descripcion(
        tipo.descripcion(entrada), geom_desc,
        ancho_wrap=38, tam_fuente=18, interlineado=22, centrado=False)
    stats = _frag_stats_linea(tipo, entrada, geom_stats)

    return plantillas.render(
        tpl,
        textos={
            "NOMBRE": entrada.get("nombre", ""),
            "SUBTITULO": tipo.subtitulo(entrada),
            "COLOR": tipo.color,
        },
        bloques={"ph-arte": arte, "ph-descripcion": desc, "ph-stats": stats},
    )


def _render_text_markers(svg: str, textos: dict[str, str]) -> str:
    """Sustituye marcadores {{CLAVE}} en el SVG."""
    def _valor(clave: str) -> str:
        valor = textos.get(clave, "")
        return valor

    def _sub(m: re.Match) -> str:
        return _valor(m.group(1))

    return re.sub(r"\{\{\s*([\w]+)\s*\}\}", _sub, svg)


def _contenido_svg(tipo: TipoCarta, entrada: dict, ancho: int, alto: int) -> str:
    """Renderiza el anverso de la familia 'descripcion' (armas, hechizos...).

    Usa la plantilla `anverso_descripcion.svg` para el chrome y rellena las
    anclas ph-arte, ph-descripcion y ph-stats.
    """
    tpl = plantillas.cargar("anverso_descripcion")
    geom_arte = plantillas.ancla(tpl, "ph-arte") or {"x": 80, "y": 105, "width": 340, "height": 220}
    geom_desc = plantillas.ancla(tpl, "ph-descripcion") or {"x": 60, "y": 375, "width": 380, "height": 230}
    geom_stats = plantillas.ancla(tpl, "ph-stats") or {"x": 60, "y": 608, "width": 380, "height": 24}

    arte = _frag_arte(tipo, entrada, geom_arte, sufijo="desc", franja=16, fallback_circulo=False)
    desc = _frag_descripcion(
        tipo.descripcion(entrada), geom_desc,
        ancho_wrap=38, tam_fuente=18, interlineado=22, centrado=False)
    stats = _frag_stats_linea(tipo, entrada, geom_stats)

    return plantillas.render(
        tpl,
        textos={
            "NOMBRE": entrada.get("nombre", ""),
            "SUBTITULO": tipo.subtitulo(entrada),
            "COLOR": tipo.color,
        },
        bloques={"ph-arte": arte, "ph-descripcion": desc, "ph-stats": stats},
    )


def _contenido_svg(tipo: TipoCarta, entrada: dict, ancho: int, alto: int) -> str:
    """Devuelve el interior del SVG del anverso (sin la etiqueta <svg> raíz).

    Delega en la plantilla de la familia del tipo (`anverso_stats.svg` o
    `anverso_descripcion.svg`), o usa la plantilla hero-card-up.svg para héroes.
    """
    match tipo.familia:
        case "stats":
            # Si es un héroe, usar la plantilla hero-card-up.svg
            if tipo.id == "personaje":
                return _render_hero_card(tipo, entrada, ancho, alto)
            # Para otros tipos stats (monstruos), usar la plantilla original
            return _render_stats(tipo, entrada, ancho, alto)
        case "descripcion":
            return _render_descripcion(tipo, entrada, ancho, alto)
        case _:
            return f'<text x="50" y="50" fill="red">Familia de carta desconocida: {tipo.familia}</text>'

def _ensure_svg_namespaces(svg: str) -> str:
    """Asegura que el SVG tenga los namespaces necesarios para que resvg lo acepte.
    
    Este función reemplaza el xmlns base por uno completo que incluye xlink,
    inkscape y sodipodi, que son necesarios cuando el SVG contiene referencias
    a data URIs o viene de plantillas Inkscape.
    """
    # Reemplazar cualquier xmlns existente por uno completo
    svg = svg.replace(
        'xmlns="http://www.w3.org/2000/svg"',
        'xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"'
    )
    # Eliminar duplicados del xmlns base (dejar solo el primero)
    # Buscar y remover segundas ocurrencias de xmlns="..."
    import re
    svg = re.sub(r'xmlns="http://www\.w3\.org/2000/svg"[^>]*', 'xmlns="http://www.w3.org/2000/svg"', svg, count=1)
    
    return svg


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
    
    # Generar contenido SVG interior
    contenido = _contenido_svg(tipo, entrada, ancho, alto)
    
    # Verificar si el contenido necesita namespaces especiales (data URIs, etc.)
    needs_xlink = "xlink:href" in contenido
    needs_inkscape = "id=" in contenido  # Las plantillas Inkscape suelen tener ids
    needs_sodipodi = "sodipodi:" in contenido
    
    # Construir la etiqueta <svg> inicial con los namespaces necesarios
    svg_start = '<?xml version="1.0" encoding="UTF-8"?>'
    svg_namespace = 'xmlns="http://www.w3.org/2000/svg"'
    attrs = [svg_namespace, f'viewBox="0 0 {ancho} {alto}"', f'width="{px_ancho}"', f'height="{px_alto}']
    
    if needs_xlink:
        svg_namespace += ' xmlns:xlink="http://www.w3.org/1999/xlink"'
    if needs_inkscape:
        svg_namespace += ' xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"'
    if needs_sodipodi:
        svg_namespace += ' xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"'
    
    # El SVG completo: declaración XML + etiqueta de apertura + contenido + cierre
    svg = f'{svg_start}<svg {svg_namespace}>'
    svg += contenido
    svg += "</svg>"
    
    return svg


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


def _categorias_verso(tipo: TipoCarta, entrada: dict | None = None) -> list[str]:
    """Candidatas de fondo temático del reverso, de más específica a más genérica.

    Primero la categoría específica de la entrada (p. ej. un hechizo de fuego
    devuelve `magia_fuego`), después la categoría del tipo (`magia`).
    """
    categorias: list[str] = []
    especifica = tipo.familia_fondo(entrada)
    if especifica:
        categorias.append(especifica)
    base = _categoria_verso(tipo)
    if base not in categorias:
        categorias.append(base)
    return categorias


def _ruta_reverso(tipo: TipoCarta, fondo_verso: str | None = None,
                  entrada: dict | None = None) -> Path:
    """Ruta de la imagen de fondo del reverso.

    Prioridad:
    1. `fondo_verso` explícito → ese fichero de `sources/arte_fondos/` (override).
    2. Por defecto: el fondo temático de la categoría de la carta
       (`sources/arte_fondos/<categoria>_back.png`, p. ej. `enemigo_back.png`),
       primero la específica de la entrada (p. ej. `magia_fuego_back.png` para
       un hechizo de fuego) y luego la genérica del tipo, si existen.
    3. Si no hay fondo temático: el reverso estándar del tipo (`tipo.reverso()`,
       la foto de la carta real en `sources/reversos/`).
    """
    if fondo_verso:
        ruta = FONDOS_DIR / fondo_verso
        if not ruta.exists():
            raise FileNotFoundError(f"No existe el fondo de reverso: {ruta}")
        return ruta
    for categoria in _categorias_verso(tipo, entrada):
        tematico = FONDOS_DIR / f"{categoria}_back.png"
        if tematico.exists():
            return tematico
    return tipo.reverso()


def _reverso_data_uri(tipo: TipoCarta, ancho: int, alto: int,
                      fondo_verso: str | None = None,
                      entrada: dict | None = None) -> str | None:
    """Foto del reverso como data URI, recortada y reescalada a la rejilla.

    Hace un recorte "cover" para llenar exactamente el panel de la carta
    (proporción 63 × 88) y la reescala a la resolución de diseño, para que el
    SVG incrustado sea ligero. `fondo_verso` permite elegir un fondo de
    `sources/arte_fondos/` en lugar de la foto estándar del tipo.
    """
    ruta = _ruta_reverso(tipo, fondo_verso, entrada)
    if not ruta.exists():
        return None
    return _imagen_data_uri(ruta, ancho, alto)


def _categoria_verso(tipo: TipoCarta) -> str:
    """Categoría del reverso: el grupo de la carta ('equipo', 'enemigo', ...).

    Se deriva del nombre de la foto de reverso: 'equipo_back.jpg' -> 'equipo'.
    """
    return Path(tipo.reverso_img).stem.split("_")[0]


def _contenido_verso(tipo: TipoCarta, ancho: int, alto: int, leyenda: str | None = LEYENDA_VERSO,
                     fondo_verso: str | None = None, entrada: dict | None = None) -> str:
    """Interior del SVG del reverso, usando la plantilla de la familia del tipo.

    Familia 'descripcion' -> `verso_descripcion.svg` (banner + leyenda).
    Familia 'stats'       -> `verso_stats.svg` (además, muestra la descripción
    de la carta si `tipo.descripcion_en_reverso` es True y se pasa `entrada`;
    p. ej. héroes. Los monstruos dejan esa zona vacía).

    `leyenda` es la leyenda inferior; si es None se usa la categoría del tipo
    de carta ('equipo', 'enemigo', 'heroe', 'tesoro', ...). `fondo_verso`
    selecciona un fondo de `sources/arte_fondos/` en lugar de la foto estándar.
    `entrada` son los datos de la carta: permiten elegir el fondo temático
    específico de esa carta (p. ej. la escuela elemental de un hechizo) y
    dibujar la descripción en el reverso de los héroes.
    """
    if not leyenda:
        leyenda = _categoria_verso(tipo)

    nombre_tpl = "verso_stats" if tipo.familia == "stats" else "verso_descripcion"
    tpl = plantillas.cargar(nombre_tpl)

    # Fondo temático (imagen) que reemplaza el ancla ph-fondo.
    geom_fondo = plantillas.ancla(tpl, "ph-fondo") or {"x": 0, "y": 0, "width": ancho, "height": alto}
    foto = _reverso_data_uri(tipo, round(geom_fondo["width"]), round(geom_fondo["height"]), fondo_verso, entrada)
    if foto:
        fondo_frag = (f'<image x="{geom_fondo["x"]}" y="{geom_fondo["y"]}" '
                      f'width="{geom_fondo["width"]}" height="{geom_fondo["height"]}" '
                      f'href="{foto}" preserveAspectRatio="xMidYMid slice" />')
    else:
        fondo_frag = ""  # queda el fondo de pergamino de respaldo de la plantilla

    bloques: dict[str, str] = {"ph-fondo": fondo_frag}

    # Descripción en el reverso (solo familia stats con descripcion_en_reverso).
    if tipo.familia == "stats":
        desc_frag = ""
        if tipo.descripcion_en_reverso and entrada:
            geom_desc = (plantillas.ancla(tpl, "ph-descripcion")
                         or {"x": 75, "y": 255, "width": 350, "height": 250})
            desc_frag = _frag_descripcion(
                tipo.descripcion(entrada), geom_desc,
                ancho_wrap=34, tam_fuente=18, interlineado=26, centrado=True, cursiva=True)
        bloques["ph-descripcion"] = desc_frag

    return plantillas.render(
        tpl,
        textos={"LEYENDA": leyenda, "COLOR": tipo.color},
        bloques=bloques,
    )


def render_verso_svg(tipo: TipoCarta, ancho: int = DISENO_ANCHO, alto: int = DISENO_ALTO,
                     leyenda: str | None = LEYENDA_VERSO, fondo_verso: str | None = None,
                     entrada: dict | None = None) -> str:
    """Devuelve el SVG (str) del reverso de la carta.

    `entrada` (opcional) permite elegir el fondo temático de la carta (p. ej. la
    escuela de un hechizo) y dibujar la descripción en el reverso de los héroes.
    """
    px_ancho = round(ancho * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" width="{px_ancho}" height="{px_alto}">',
        _contenido_verso(tipo, ancho, alto, leyenda, fondo_verso, entrada),
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
    
    # Generar contenidos
    frente_contenido = _contenido_svg(tipo, entrada, ancho, alto)
    verso_contenido = _contenido_verso(tipo, ancho, alto, leyenda, fondo_verso, entrada)
    
    # Verificar si los contenidos necesitan namespaces especiales
    needs_xlink = "xlink:href" in frente_contenido or "xlink:href" in verso_contenido
    needs_inkscape = "id=" in frente_contenido or "id=" in verso_contenido
    needs_sodipodi = "sodipodi:" in frente_contenido or "sodipodi:" in verso_contenido
    
    # Construir namespaces
    svg_namespace = 'xmlns="http://www.w3.org/2000/svg"'
    if needs_xlink:
        svg_namespace += ' xmlns:xlink="http://www.w3.org/1999/xlink"'
    if needs_inkscape:
        svg_namespace += ' xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"'
    if needs_sodipodi:
        svg_namespace += ' xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"'
    
    px_ancho = round(ancho_doble * PX_CARTA_ANCHO / DISENO_ANCHO)
    px_alto = round(alto * PX_CARTA_ALTO / DISENO_ALTO)
    
    frente = '<g transform="translate(0,0)">' + frente_contenido + '</g>'
    verso = '<g transform="translate(' + str(ancho) + ',0)">' + verso_contenido + '</g>'
    pliegue = "\n".join([
        '<line x1="' + str(ancho) + '" y1="0" x2="' + str(ancho) + '" y2="' + str(alto) + '" stroke="' + COLOR_BORDE + '" '
        'stroke-width="1.5" stroke-dasharray="8 6" />',
        '<text x="' + str(ancho) + '" y="' + str(alto - 12) + '" font-family="' + FONT_FAMILY_CARTA + '" font-size="11" '
        'fill="' + COLOR_BORDE + '" text-anchor="middle">— pliegue —</text>',
    ])
    
    return "\n".join([
        '<svg ' + svg_namespace + ' viewBox="0 0 ' + str(ancho_doble) + ' ' + str(alto) + '" width="' + str(px_ancho) + '" height="' + str(px_alto) + '">',
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
                     leyenda: str | None = LEYENDA_VERSO, fondo_verso: str | None = None,
                     entrada: dict | None = None) -> Image.Image:
    """Devuelve una imagen Pillow del reverso de la carta (744 × 1039 px)."""
    svg = render_verso_svg(tipo, ancho, alto, leyenda, fondo_verso, entrada)
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

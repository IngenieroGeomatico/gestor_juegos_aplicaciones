# -*- coding: utf-8 -*-
"""Motor de composición de cartas de HeroQuest guiado por datos (personajes).

Filosofía nueva: la *receta* de la carta vive en el propio JSON del personaje,
no en el código. Cada entrada de `personajes.json` declara, bajo la clave
`plantillas`, qué plantillas SVG y qué assets componen su carta:

    "plantillas": {
      "cara": {
        "plantilla_padre":        "sources/plantillas/hero-card-up.svg",
        "plantilla_estadisticas": "sources/plantillas/hero-stats.svg",
        "plantilla_leyenda":      "sources/plantillas/ribbon.svg",
        "arte_personaje":         "sources/arte/bárbaro_1.png",
        "arte_icono":             "sources/arte_iconos/bárbaro_1.png",
        "archivos_fondo":         ["sources/arte_fondos/parchment.png"]
      },
      "dorso": { "plantilla_padre": "" }
    }

Este módulo solo *compone*: carga la plantilla padre, y sobre sus anclas
`id="ph-*"` (rectángulos invisibles cuya geometría se lee) coloca el contenido:

  - `ph-arte`   -> la imagen `arte_personaje` (recorte "cover" a la caja).
  - `ph-ribbon` -> la plantilla_leyenda (ribbon.svg) con `{{NOMBRE}}`.
  - `ph-stats`  -> la plantilla_estadisticas (hero-stats.svg) con los stats.
  - `ph-icon`   -> la imagen `arte_icono`.
  - fondo       -> `archivos_fondo` detrás de todo (dentro de la carta).

El SVG es la fuente de verdad; el PNG se obtiene rasterizando con resvg a la
resolución física real de la carta (63 × 88 mm a 300 DPI). El diseñador puede
mover/redimensionar cualquier ancla en Inkscape y el contenido se recoloca solo.

Contrato de datos que consumen las plantillas (además de los stats numéricos):

  hero-stats.svg  usa los marcadores de texto:
    {{PUNTOS_INICIALES}}  <- entrada["puntos_iniciales"]
    {{MOVIMIENTO}}        <- entrada["movimiento"]
    {{ARMA_INICIAL}}      <- entrada["arma_inicial"]
    {{ARMADURA_INICIAL}}  <- entrada["armadura_inicial"]
  y las anclas de valor (se dibuja el número centrado en cada caja):
    ph-valor-ataque       <- entrada["ataque"]
    ph-valor-defensa      <- entrada["defensa"]
    ph-valor-corporales   <- entrada["cuerpo"]
    ph-valor-mentales     <- entrada["mente"]

  ribbon.svg      usa {{NOMBRE}} <- entrada["nombre"].
"""

from __future__ import annotations

import base64
import io
import re
import xml.sax.saxutils
from pathlib import Path

from PIL import Image, ImageOps

import plantillas

# Raíz del juego (…/juegos/heroquest), para resolver rutas relativas del JSON.
JUEGO_DIR = Path(__file__).resolve().parent.parent

# Fuente de la carta (libre, OFL). Se embebe en el SVG como @font-face para que
# resvg la use de forma consistente (si no, cae a una fuente por defecto y los
# textos no casan con los números). Se usa **Amarna** (glyphic humanist sans,
# OFL-1.1), una alternativa libre a la Carter Sans original de las cartas HQ
# 2021: ambas son "flare/glyphic sans" inspiradas en Albertus, con serifas
# suaves en las mayúsculas. Se embeben instancias estáticas Regular/Bold (resvg
# no interpola fuentes variables, así que necesitamos una cara bold real).
FUENTE_DIR = JUEGO_DIR / "sources" / "fuentes"
FUENTE_REGULAR = FUENTE_DIR / "Amarna-Regular.ttf"
FUENTE_BOLD = FUENTE_DIR / "Amarna-Bold.ttf"
# Reserva: la variable original, si no existen las instancias estáticas.
FUENTE_TTF = FUENTE_DIR / "Amarna[wght].ttf"
FONT_FAMILY = "Amarna"

# --- Tamaño físico de la carta (idéntico al del sistema clásico) ---
MM_CARTA_ANCHO = 63
MM_CARTA_ALTO = 88
DPI_CARTA = 300
PX_CARTA_ANCHO = round(MM_CARTA_ANCHO / 25.4 * DPI_CARTA)   # 744
PX_CARTA_ALTO = round(MM_CARTA_ALTO / 25.4 * DPI_CARTA)     # 1039

# Factor de resolución para incrustar imágenes: las anclas están en coordenadas
# del viewBox de la plantilla (~189 px de ancho), pero la carta se rasteriza a
# 744 px. Incrustar al tamaño del ancla dejaría el arte pixelado; se multiplica
# por este factor (viewBox -> px físicos) para incrustar a resolución real.
# Se calcula por SVG en tiempo de render; este es un mínimo de seguridad.
_FACTOR_RES_MIN = 1.0

# Estilo del número de stat que se pinta sobre las anclas ph-valor-*.
COLOR_VALOR = "#3a2416"
TAM_FUENTE_VALOR = 52
# Estilo de las etiquetas de stat (Ataque/Defensa/...) sobre las anclas título.
TAM_FUENTE_TITULO = 28
# Tamaños reducidos para la plantilla de monstruo (monster-stats.svg), que tiene
# las 5 columnas (con Movimiento) y necesita menos espacio por celda.
TAM_FUENTE_VALOR_MONSTRUO = 48
TAM_FUENTE_TITULO_MONSTRUO = 22
# "Faux bold": resvg solo tiene la cara Bold (700); para engrosar más los textos
# se les añade un contorno (stroke) del mismo color que el relleno. El ancho se
# expresa en coords del viewBox de hero-stats (~638 de ancho), donde 0.6 da un
# trazo perceptible sin emborronar las letras.
STROKE_TITULO = 0.6
STROKE_VALOR = 0.9

# Mapea cada ancla de VALOR de hero-stats.svg al campo del JSON del personaje.
# monster-stats.svg añade la columna de movimiento (ph-valor-movimiento); al no
# existir esa ancla en hero-stats.svg, el mapa puede convivir para ambas.
ANCLAS_VALOR = {
    "ph-valor-ataque": "ataque",
    "ph-valor-defensa": "defensa",
    "ph-valor-corporales": "cuerpo",
    "ph-valor-mentales": "mente",
    "ph-valor-movimiento": "movimiento",
}

# Mapea cada ancla de TÍTULO de hero-stats.svg a su etiqueta legible.
ANCLAS_TITULO = {
    "ph-dados-ataque": "Dados de Ataque",
    "ph-dados-defensa": "Dados de Defensa",
    "ph-corporales-titulo": "Corporales",
    "ph-mentales-titulo": "Mentales",
}

# Etiquetas extra de monster-stats.svg, que nombra sus anclas de título sin el
# sufijo "-titulo" del hero-stats y añade la de movimiento. NO pueden convivir
# en ANCLAS_TITULO: hero-stats.svg también trae un ancla ph-movimiento (que hoy
# se limpia, con el texto real en el marcador {{MOVIMIENTO}}), y pintarla
# cambiaría las cartas de héroe ya aprobadas. Se activan solo cuando la
# plantilla de stats es de monstruo (tiene ancla de valor de movimiento).
ANCLAS_TITULO_MONSTRUO = {
    "ph-corporales": "Puntos Corporales",
    "ph-mentales": "Puntos Mentales",
    "ph-movimiento": "Casillas de Movimiento",
}


def _lineas_etiqueta(etiqueta: str) -> list[str]:
    """Parte una etiqueta de título en varias líneas para que quepa en su celda.

    Reglas de split:
    - "X de Y" → ["X de", "Y"]  (Dados de Ataque → Dados de / Ataque)
    - Dos palabras → [primera, segunda]  (Puntos Corporales → Puntos / Corporales)
    - Una palabra → [etiqueta]  (sin salto)
    """
    palabras = etiqueta.split()
    if len(palabras) >= 3 and " de " in etiqueta.lower():
        idx = etiqueta.lower().index(" de ") + 4
        return [etiqueta[:idx].rstrip(), etiqueta[idx:].lstrip()]
    if len(palabras) == 2:
        return list(palabras)
    return [etiqueta]


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def _resolver(ruta: str) -> Path:
    """Resuelve una ruta del JSON (relativa a la carpeta del juego) a Path."""
    p = Path(ruta)
    return p if p.is_absolute() else JUEGO_DIR / p


def _imagen_data_uri(ruta: Path, ancho: int, alto: int) -> str:
    """Incrusta una imagen recortada "cover" (x/y-mid slice) como data URI.

    Si la imagen tiene canal alfa (PNG con transparencia) se preserva usando
    PNG; así el fondo transparente del arte NO se vuelve negro. Si es opaca, se
    usa JPEG (más ligero).
    """
    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im)
        tiene_alpha = im.mode in ("RGBA", "LA") or (
            im.mode == "P" and "transparency" in im.info
        )
        im = im.convert("RGBA" if tiene_alpha else "RGB")
        im = ImageOps.fit(im, (max(1, ancho), max(1, alto)), Image.LANCZOS)
        buf = io.BytesIO()
        if tiene_alpha:
            im.save(buf, format="PNG")
            mime = "png"
        else:
            im.save(buf, format="JPEG", quality=88)
            mime = "jpeg"
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _face(ruta: Path, peso: str) -> str:
    """Un bloque @font-face para `ruta` con el `font-weight` indicado."""
    datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{FONT_FAMILY}';font-style:normal;"
        f"font-weight:{peso};src:url('data:font/ttf;base64,{datos}')"
        " format('truetype');}"
    )


def _font_face() -> str:
    """Devuelve un <style> con las caras Regular y Bold de la fuente embebidas.

    Embeber la fuente como @font-face con data URI garantiza que resvg la use.
    Se embeben caras estáticas Regular (400) y Bold (700) porque resvg no
    interpola la variable original y `font-weight:bold` no se aplicaría.
    """
    caras: list[str] = []
    if FUENTE_REGULAR.exists():
        caras.append(_face(FUENTE_REGULAR, "normal"))
    elif FUENTE_TTF.exists():
        caras.append(_face(FUENTE_TTF, "normal"))
    if FUENTE_BOLD.exists():
        caras.append(_face(FUENTE_BOLD, "bold"))
    if not caras:
        return ""
    return "<style>" + "".join(caras) + "</style>"


def _cargar_svg_texto(ruta: Path) -> str:
    """Lee un fichero SVG de disco (para plantillas referenciadas por el JSON)."""
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la plantilla/asset: {ruta}")
    return ruta.read_text(encoding="utf-8")


# Atributos y elementos con prefijos de Inkscape/sodipodi: resvg no los conoce
# y aborta con "unknown namespace prefix". Se eliminan del SVG compuesto final.
_RE_ATTR_NS = re.compile(r'\s+(?:inkscape|sodipodi|svg):[\w-]+="[^"]*"')
_RE_ELEM_NS = re.compile(r"<(?:inkscape|sodipodi):[\w-]+\b[^>]*/?>")


def _limpiar_para_resvg(svg: str) -> str:
    """Quita atributos/elementos con prefijos que resvg no reconoce."""
    svg = _RE_ELEM_NS.sub("", svg)
    svg = _RE_ATTR_NS.sub("", svg)
    return svg


def _viewbox(svg: str) -> tuple[float, float, float, float]:
    """Devuelve (min_x, min_y, ancho, alto) del viewBox de un SVG."""
    m = re.search(r'viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"', svg)
    if not m:
        # Sin viewBox: usa width/height como tamaño y origen 0,0.
        aw = re.search(r'\bwidth="([-\d.eE]+)"', svg)
        ah = re.search(r'\bheight="([-\d.eE]+)"', svg)
        return (0.0, 0.0, float(aw.group(1)) if aw else 100.0,
                float(ah.group(1)) if ah else 100.0)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))


def _colocar_subsvg(sub_svg: str, geom: dict[str, float]) -> str:
    """Devuelve el interior de `sub_svg` escalado/trasladado al ancla `geom`.

    El sub-SVG (ribbon, hero-stats) se dibuja en sus propias coordenadas de
    viewBox; aquí lo posamos dentro de la caja del ancla respetando su origen.
    """
    min_x, min_y, vb_w, vb_h = _viewbox(sub_svg)
    if vb_w <= 0 or vb_h <= 0:
        return ""
    escala_x = geom["width"] / vb_w
    escala_y = geom["height"] / vb_h
    interior = plantillas.interior(sub_svg)
    return (
        f'<g transform="translate({geom["x"]}, {geom["y"]}) '
        f'scale({escala_x}, {escala_y}) translate({-min_x}, {-min_y})">'
        f"{interior}</g>"
    )


# --------------------------------------------------------------------------
# Fragmentos de contenido para cada ancla de la plantilla padre
# --------------------------------------------------------------------------

def _frag_imagen(ruta: Path, geom: dict[str, float], factor_res: float = 1.0) -> str:
    """Imagen recortada "cover" que llena exactamente el ancla `geom`.

    `factor_res` multiplica la resolución a la que se incrusta la imagen (los
    píxeles reales del data URI) sin cambiar su tamaño en el lienzo, para evitar
    el pixelado al rasterizar la carta a su resolución física.
    """
    px_w = max(1, round(geom["width"] * factor_res))
    px_h = max(1, round(geom["height"] * factor_res))
    uri = _imagen_data_uri(ruta, px_w, px_h)
    return (
        f'<image x="{geom["x"]}" y="{geom["y"]}" '
        f'width="{geom["width"]}" height="{geom["height"]}" '
        f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
    )


# Tamaño de fuente del nombre en el ribbon (en coords del viewBox del ribbon,
# 564×144). La plantilla lo trae a 12px, que al escalar queda diminuto.
TAM_FUENTE_NOMBRE = 56


def _frag_ribbon(ruta: Path, geom: dict[str, float], nombre: str) -> str:
    """La plantilla de leyenda (ribbon.svg) con {{NOMBRE}}, posada en `geom`.

    Además de sustituir {{NOMBRE}}, agranda y fija la tipografía del elemento
    `id="ph-nombre"` para que el nombre se lea grande y con la fuente de la carta.
    """
    svg = _cargar_svg_texto(ruta)
    svg = re.sub(
        r"\{\{\s*NOMBRE\s*\}\}",
        lambda _m: xml.sax.saxutils.escape(nombre or ""),
        svg,
    )
    # Reemplaza el font-size del texto del nombre (tanto en atributo `style` como
    # en atributo `font-size`) por el tamaño grande deseado.
    svg = svg.replace("font-size:12px", f"font-size:{TAM_FUENTE_NOMBRE}px")
    # La plantilla trae `font-weight:normal` en el `style` inline del nombre, que
    # tiene prioridad sobre el atributo font-weight="bold". Se fuerza a bold en el
    # propio style para que el nombre salga en negrita (como en las cartas
    # originales de HeroQuest).
    svg = svg.replace("font-weight:normal", "font-weight:bold")
    # Nombre en negrita (atributo font-weight + faux-bold con stroke).
    svg = _forzar_negrita(svg)
    return _colocar_subsvg(svg, geom)


def _frag_stats(ruta: Path, geom: dict[str, float], entrada: dict) -> str:
    """La plantilla de estadísticas (hero-stats.svg) rellena, posada en `geom`.

    Sustituye los marcadores de texto {{...}} y pinta el número de cada stat
    centrado sobre sus anclas ph-valor-*.
    """
    svg = _cargar_svg_texto(ruta)

    # 1) Marcadores de texto de la plantilla de stats.
    # El movimiento del héroe se mide en "Dados Rojos": se anexa la unidad tras
    # el valor numérico (p. ej. "2 Dados Rojos").
    mov = str(entrada.get("movimiento", "")).strip()
    movimiento = f"{mov} Dados Rojos" if mov else ""
    textos = {
        "PUNTOS_INICIALES": str(entrada.get("puntos_iniciales", "")),
        "MOVIMIENTO": movimiento,
        "ARMA_INICIAL": str(entrada.get("arma_inicial", "")),
        "ARMADURA_INICIAL": str(entrada.get("armadura_inicial", "")),
        "NOMBRE": str(entrada.get("nombre", "")),
    }

    def _sub_texto(m: re.Match) -> str:
        return xml.sax.saxutils.escape(textos.get(m.group(1), ""))

    svg = re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub_texto, svg)

    # 2) Etiquetas de stat (Ataque/Defensa/...) sobre sus anclas título. Si la
    # plantilla es de monstruo (lleva ancla de valor de movimiento), se suman
    # sus etiquetas propias (ver ANCLAS_TITULO_MONSTRUO) y se usan tamaños
    # reducidos para que quepan las 5 columnas. Para alinear los textos, se
    # calcula un y común basado en el centro medio de todas las anclas.
    es_monstruo = plantillas.ancla(svg, "ph-valor-movimiento") is not None
    anclas_titulo = dict(ANCLAS_TITULO)
    if es_monstruo:
        anclas_titulo.update(ANCLAS_TITULO_MONSTRUO)
    tam_titulo = TAM_FUENTE_TITULO_MONSTRUO if es_monstruo else TAM_FUENTE_TITULO
    tam_valor = TAM_FUENTE_VALOR_MONSTRUO if es_monstruo else TAM_FUENTE_VALOR

    for id_ancla, etiqueta in anclas_titulo.items():
        g = plantillas.ancla(svg, id_ancla)
        if not g:
            continue
        cx = g["x"] + g["width"] / 2
        lineas = _lineas_etiqueta(etiqueta)
        interlineado = tam_titulo * 1.05
        alto_bloque = interlineado * (len(lineas) - 1)
        y0 = g["y"] + g["height"] / 2 + tam_titulo / 3 - alto_bloque / 2
        tspans = "".join(
            f'<tspan x="{cx}" '
            f'{"" if i == 0 else f"""dy="{interlineado}" """}>'
            f"{xml.sax.saxutils.escape(linea)}</tspan>"
            for i, linea in enumerate(lineas)
        )
        texto = (
            f'<text x="{cx}" y="{y0}" font-family="{FONT_FAMILY}" '
            f'font-size="{tam_titulo}" font-weight="bold" '
            f'stroke="{COLOR_VALOR}" stroke-width="{STROKE_TITULO}" '
            f'paint-order="stroke" '
            f'text-anchor="middle" fill="{COLOR_VALOR}">{tspans}</text>'
        )
        svg = plantillas._eliminar_ancla(svg, id_ancla, texto)

    for id_ancla, campo in ANCLAS_VALOR.items():
        g = plantillas.ancla(svg, id_ancla)
        if not g:
            continue
        valor = xml.sax.saxutils.escape(str(entrada.get(campo, "")))
        cx = g["x"] + g["width"] / 2
        cy = g["y"] + g["height"] / 2 + tam_valor / 3
        texto = (
            f'<text x="{cx}" y="{cy}" font-family="{FONT_FAMILY}" '
            f'font-size="{tam_valor}" font-weight="bold" '
            f'stroke="{COLOR_VALOR}" stroke-width="{STROKE_VALOR}" '
            f'paint-order="stroke" '
            f'text-anchor="middle" fill="{COLOR_VALOR}">{valor}</text>'
        )
        svg = plantillas._eliminar_ancla(svg, id_ancla, texto)

    # 4) Cualquier ancla ph-* restante de la plantilla de stats se limpia.
    for id_ancla in re.findall(r'<rect\b[^>]*\bid="(ph-[\w-]+)"', svg):
        svg = plantillas._eliminar_ancla(svg, id_ancla, "")

    # 5) Todos los textos de la plantilla en negrita y con la fuente de la carta.
    svg = _forzar_negrita(svg)

    return _colocar_subsvg(svg, geom)


def _forzar_negrita(svg: str) -> str:
    """Fuerza negrita en todos los <text> de un fragmento SVG.

    Añade `font-weight="bold"` a cada `<text ...>` que no lo declare ya, y un
    contorno ("faux bold") del color del texto para engrosarlo aún más, para que
    los textos que trae la plantilla (Movimiento, Arma inicial, Puntos
    Iniciales...) se rendericen gruesos con la cara Bold embebida.
    """
    def _color_fill(etiqueta: str) -> str:
        m = re.search(r'fill="([^"]+)"', etiqueta)
        return m.group(1) if m and m.group(1) != "none" else COLOR_VALOR

    def _añadir_peso(m: re.Match) -> str:
        etiqueta = m.group(0)
        if "font-weight" not in etiqueta:
            etiqueta = etiqueta[:-1] + ' font-weight="bold">'
        if "stroke=" not in etiqueta:
            color = _color_fill(etiqueta)
            etiqueta = (etiqueta[:-1]
                        + f' stroke="{color}" stroke-width="{STROKE_TITULO}"'
                          ' paint-order="stroke">')
        return etiqueta

    return re.sub(r"<text\b[^>]*>", _añadir_peso, svg)


# --------------------------------------------------------------------------
# Composición de la carta
# --------------------------------------------------------------------------

def _receta_cara(entrada: dict) -> dict:
    """Devuelve la receta de la cara delantera, o error si falta."""
    plantillas_ent = entrada.get("plantillas") or {}
    cara = plantillas_ent.get("cara") or {}
    if not cara.get("plantilla_padre"):
        raise ValueError(
            f"El personaje '{entrada.get('nombre')}' no declara "
            "plantillas.cara.plantilla_padre en su JSON."
        )
    return cara


def render_svg(entrada: dict) -> str:
    """Compone la cara delantera de la carta de un personaje como SVG (str).

    Lee la receta (`entrada['plantillas']['cara']`), carga la plantilla padre y
    coloca sobre sus anclas el fondo, el arte, la leyenda, los stats y el icono.
    """
    cara = _receta_cara(entrada)

    padre_ruta = _resolver(cara["plantilla_padre"])
    padre = _cargar_svg_texto(padre_ruta)

    # Factor viewBox -> px físicos, para incrustar imágenes a resolución real.
    _, _, vb_w, _ = _viewbox(padre)
    factor_res = max(_FACTOR_RES_MIN, PX_CARTA_ANCHO / vb_w) if vb_w else _FACTOR_RES_MIN

    # Anclas de la plantilla padre (geometría en sus coordenadas de grupo).
    geom_arte = plantillas.ancla(padre, "ph-arte")
    geom_ribbon = plantillas.ancla(padre, "ph-ribbon")
    geom_stats = plantillas.ancla(padre, "ph-stats")
    geom_icon = plantillas.ancla(padre, "ph-icon")

    bloques: dict[str, str] = {}

    # ph-arte <- arte_personaje
    if geom_arte and cara.get("arte_personaje"):
        ruta = _resolver(cara["arte_personaje"])
        if ruta.exists():
            bloques["ph-arte"] = _frag_imagen(ruta, geom_arte, factor_res)

    # ph-ribbon <- plantilla_leyenda con {{NOMBRE}}
    if geom_ribbon and cara.get("plantilla_leyenda"):
        ruta = _resolver(cara["plantilla_leyenda"])
        bloques["ph-ribbon"] = _frag_ribbon(ruta, geom_ribbon, entrada.get("nombre", ""))

    # ph-stats <- plantilla_estadisticas rellena
    if geom_stats and cara.get("plantilla_estadisticas"):
        ruta = _resolver(cara["plantilla_estadisticas"])
        bloques["ph-stats"] = _frag_stats(ruta, geom_stats, entrada)

    # ph-icon <- arte_icono
    if geom_icon and cara.get("arte_icono"):
        ruta = _resolver(cara["arte_icono"])
        if ruta.exists():
            bloques["ph-icon"] = _frag_imagen(ruta, geom_icon, factor_res)

    # El fondo va DENTRO del mismo grupo transformado que las anclas (para que
    # comparta el transform del <g> padre y encaje con el rect 'carta'). Se
    # inyecta como primer hijo del grupo, justo tras la etiqueta <g ...>.
    fondo_frag = _frag_fondo(cara, padre, factor_res)

    # Sustituye anclas por sus fragmentos (las que no tengan fragmento se limpian).
    cuerpo = plantillas.render(padre, textos={"NOMBRE": entrada.get("nombre", "")},
                               bloques=bloques)
    # El rect guía 'carta' (marco de referencia) no debe dibujarse.
    cuerpo = plantillas._eliminar_ancla(cuerpo, "carta", "")
    if fondo_frag:
        cuerpo = _inyectar_fondo(cuerpo, fondo_frag)

    min_x, min_y, vb_w, vb_h = _viewbox(padre)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{min_x} {min_y} {vb_w} {vb_h}" '
        f'width="{PX_CARTA_ANCHO}" height="{PX_CARTA_ALTO}">'
        f"{_font_face()}{cuerpo}</svg>"
    )


def _inyectar_fondo(cuerpo: str, fondo_frag: str) -> str:
    """Inserta el fondo como primer hijo del primer grupo <g ...> del cuerpo.

    Así el fondo hereda el mismo transform del grupo padre (donde viven las
    anclas y el rect 'carta') y queda detrás de todo el contenido.
    """
    m = re.search(r"<g\b[^>]*>", cuerpo)
    if not m:
        return fondo_frag + cuerpo
    pos = m.end()
    return cuerpo[:pos] + fondo_frag + cuerpo[pos:]


# --------------------------------------------------------------------------
# Dorso (reverso) de la carta de personaje
# --------------------------------------------------------------------------

# Imágenes con href a rutas locales de disco (bocetos que deja Inkscape, p. ej.
# "../../Downloads/Captura....png"). resvg no puede resolverlas y no deben salir
# en la carta final; se eliminan del SVG compuesto.
_RE_IMAGEN_LOCAL = re.compile(
    r'<image\b(?:[^>]*\b(?:xlink:href|href)="(?!data:)[^"]*")[^>]*/?>',
    re.IGNORECASE,
)

# Estilo del texto de la biografía del dorso (coords del viewBox de la carta).
TAM_FUENTE_TEXTO = 13
INTERLINEADO_TEXTO = 1.35
ANCHO_WRAP_TEXTO = 34  # caracteres aprox. por línea


def _quitar_imagenes_locales(svg: str) -> str:
    """Elimina los <image> con href a ficheros locales (bocetos de Inkscape)."""
    return _RE_IMAGEN_LOCAL.sub("", svg)


def _receta_dorso(entrada: dict) -> dict:
    """Devuelve la receta del dorso, o error si falta."""
    plantillas_ent = entrada.get("plantillas") or {}
    dorso = plantillas_ent.get("dorso") or {}
    if not dorso.get("plantilla_padre"):
        raise ValueError(
            f"El personaje '{entrada.get('nombre')}' no declara "
            "plantillas.dorso.plantilla_padre en su JSON."
        )
    return dorso


def _texto_dorso(entrada: dict) -> tuple[str, str]:
    """Devuelve (intro, descripción) de la biografía del dorso.

    - intro: 'Eres el {clase}.' (va en una sola línea, en negrita).
    - descripción: el campo `descripcion` del personaje (va debajo).
    """
    clase = str(entrada.get("clase", "")).strip()
    descripcion = str(entrada.get("descripcion", "")).strip()
    intro = f"Eres el {clase}." if clase else ""
    return intro, descripcion


def _frag_texto(intro: str, descripcion: str, geom: dict[str, float]) -> str:
    """Bloque de texto del dorso, centrado dentro del ancla `geom`.

    La `intro` ('Eres el {clase}.') va en una sola línea y en NEGRITA; debajo,
    la `descripción` envuelta en varias líneas con peso normal. Todo el bloque se
    centra vertical y horizontalmente dentro de la caja.
    """
    if not intro and not descripcion:
        return ""
    import textwrap

    cx = geom["x"] + geom["width"] / 2
    interlineado = TAM_FUENTE_TEXTO * INTERLINEADO_TEXTO

    # (texto, es_negrita) por línea: intro en una línea; descripción envuelta.
    lineas: list[tuple[str, bool]] = []
    if intro:
        lineas.append((intro, True))
    for linea in textwrap.wrap(descripcion, width=ANCHO_WRAP_TEXTO):
        lineas.append((linea, False))
    if not lineas:
        return ""

    # Centra verticalmente el bloque dentro de la caja.
    alto_bloque = interlineado * (len(lineas) - 1)
    y0 = geom["y"] + geom["height"] / 2 + TAM_FUENTE_TEXTO / 3 - alto_bloque / 2
    tspans = "".join(
        f'<tspan x="{cx}" '
        f'{"" if i == 0 else f"""dy="{interlineado}" """}'
        f'font-weight="{"bold" if negrita else "normal"}">'
        f"{xml.sax.saxutils.escape(txt)}</tspan>"
        for i, (txt, negrita) in enumerate(lineas)
    )
    return (
        f'<text x="{cx}" y="{y0}" font-family="{FONT_FAMILY}" '
        f'font-size="{TAM_FUENTE_TEXTO}" '
        f'text-anchor="middle" fill="{COLOR_VALOR}">{tspans}</text>'
    )


def render_svg_verso(entrada: dict) -> str:
    """Compone el dorso de la carta de un personaje como SVG (str).

    Lee la receta (`entrada['plantillas']['dorso']`), carga la plantilla padre y
    coloca el fondo (pergamino + borde), el logo HeroQuest (ancla ph-heroquest)
    y el texto de biografía (ancla ph-texto).
    """
    dorso = _receta_dorso(entrada)

    padre_ruta = _resolver(dorso["plantilla_padre"])
    padre = _cargar_svg_texto(padre_ruta)
    # Quita el boceto de referencia (imagen local) que pueda traer la plantilla.
    padre = _quitar_imagenes_locales(padre)

    geom_heroquest = plantillas.ancla(padre, "ph-heroquest")
    geom_texto = plantillas.ancla(padre, "ph-texto")

    bloques: dict[str, str] = {}

    # ph-heroquest <- plantilla_logo (SVG escalado a la caja del ancla)
    if geom_heroquest and dorso.get("plantilla_logo"):
        ruta = _resolver(dorso["plantilla_logo"])
        if ruta.exists():
            svg_logo = _limpiar_para_resvg(_cargar_svg_texto(ruta))
            bloques["ph-heroquest"] = _colocar_subsvg(svg_logo, geom_heroquest)

    # ph-texto <- 'Eres el {clase}.' (negrita) + descripción debajo
    if geom_texto:
        intro, descripcion = _texto_dorso(entrada)
        bloques["ph-texto"] = _frag_texto(intro, descripcion, geom_texto)

    fondo_frag = _frag_fondo(dorso, padre)

    cuerpo = plantillas.render(padre, textos={"NOMBRE": entrada.get("nombre", "")},
                               bloques=bloques)
    cuerpo = plantillas._eliminar_ancla(cuerpo, "carta", "")
    if fondo_frag:
        cuerpo = _inyectar_fondo(cuerpo, fondo_frag)

    min_x, min_y, vb_w, vb_h = _viewbox(padre)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{min_x} {min_y} {vb_w} {vb_h}" '
        f'width="{PX_CARTA_ANCHO}" height="{PX_CARTA_ALTO}">'
        f"{_font_face()}{cuerpo}</svg>"
    )


def _frag_fondo_svg(ruta: Path, geom: dict[str, float]) -> str:
    """Incrusta un SVG de fondo (p. ej. el borde) escalado a la caja `geom`.

    El SVG se dibuja en sus propias coordenadas de viewBox; aquí se escala
    (X e Y por separado) para llenar exactamente la caja de la carta, como
    hacen ribbon/hero-stats. Se limpia de prefijos que resvg no reconoce.
    """
    svg = _limpiar_para_resvg(_cargar_svg_texto(ruta))
    return _colocar_subsvg(svg, geom)


def _frag_fondo(cara: dict, padre: str, factor_res: float = 1.0) -> str:
    """Fondo(s) ajustados al rectángulo de la carta (rect 'carta').

    Usa la geometría del `<rect id="carta">` de la plantilla padre como límite
    del fondo, para que encaje exactamente con la carta visible (y no con el
    viewBox completo, que incluye margen sobrante). Si no existe ese rect, cae
    al viewBox. `factor_res` multiplica la resolución de incrustado de las
    imágenes PNG/JPG.

    `archivos_fondo` es una lista en ORDEN DE RENDERIZADO: el primero es el que
    va MÁS ABAJO (se pinta primero) y cada siguiente se superpone encima. Cada
    entrada puede ser una imagen (`.png`, `.jpg`, ...) o un SVG (`.svg`, p. ej.
    el borde decorativo), que se incrusta como vector escalado a la carta.
    """
    archivos = cara.get("archivos_fondo") or []
    if not archivos:
        return ""

    caja = plantillas.ancla(padre, "carta")
    if caja and caja.get("width") and caja.get("height"):
        x, y, w, h = caja["x"], caja["y"], caja["width"], caja["height"]
    else:
        x, y, w, h = _viewbox(padre)
    geom = {"x": x, "y": y, "width": w, "height": h}

    px_w = max(1, round(w * factor_res))
    px_h = max(1, round(h * factor_res))
    partes: list[str] = []
    for archivo in archivos:
        ruta = _resolver(archivo)
        if not ruta.exists():
            continue
        if ruta.suffix.lower() == ".svg":
            partes.append(_frag_fondo_svg(ruta, geom))
        else:
            uri = _imagen_data_uri(ruta, px_w, px_h)
            partes.append(
                f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
                f'href="{uri}" preserveAspectRatio="xMidYMid slice" />'
            )
    return "".join(partes)


# --------------------------------------------------------------------------
# Rasterizado a PNG (resvg)
# --------------------------------------------------------------------------

def _rasterizar(svg: str) -> Image.Image:
    """Rasteriza un SVG (str) a PNG (744 × 1039 px) con resvg."""
    import resvg_py

    datos = resvg_py.svg_to_bytes(
        svg_string=_limpiar_para_resvg(svg),
        width=PX_CARTA_ANCHO,
        height=PX_CARTA_ALTO,
        background="#ffffff",
    )
    return Image.open(io.BytesIO(datos)).convert("RGB")


def render_png(entrada: dict) -> Image.Image:
    """Rasteriza el anverso de la carta del personaje a PNG con resvg."""
    return _rasterizar(render_svg(entrada))


def render_png_verso(entrada: dict) -> Image.Image:
    """Rasteriza el dorso de la carta del personaje a PNG con resvg."""
    return _rasterizar(render_svg_verso(entrada))

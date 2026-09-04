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

import re
import xml.sax.saxutils
from pathlib import Path

from PIL import Image

import plantillas
import render_utils
from render_utils import (
    FONT_FAMILY,
    JUEGO_DIR,
    PX_CARTA_ANCHO,
    PX_CARTA_ALTO,
    colocar_subsvg as _colocar_subsvg,
    documento_svg as _documento_svg,
    factor_res as _factor_res,
    frag_fondo as _frag_fondo_util,
    frag_imagen as _frag_imagen,
    inyectar_fondo as _inyectar_fondo,
    limpiar_para_resvg as _limpiar_para_resvg,
    rasterizar as _rasterizar,
    resolver as _resolver,
    viewbox as _viewbox,
)

_cargar_svg_texto = render_utils.cargar_svg_texto

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
# Fragmentos de contenido para cada ancla de la plantilla padre
# --------------------------------------------------------------------------

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

    # Para monstruos, alinea todos los títulos a un y común (las 5 columnas
    # tienen anclas a distintas alturas y necesitan alinearse entre sí).
    cy_medio_titulos = None
    if es_monstruo:
        geom_titulos = [g for id_a in anclas_titulo if (g := plantillas.ancla(svg, id_a))]
        if geom_titulos:
            cy_medio_titulos = sum(g["y"] + g["height"] / 2 for g in geom_titulos) / len(geom_titulos)

    for id_ancla, etiqueta in anclas_titulo.items():
        g = plantillas.ancla(svg, id_ancla)
        if not g:
            continue
        cx = g["x"] + g["width"] / 2
        lineas = _lineas_etiqueta(etiqueta)
        interlineado = tam_titulo * 1.05
        alto_bloque = interlineado * (len(lineas) - 1)
        if cy_medio_titulos is not None:
            y0 = cy_medio_titulos + tam_titulo / 3 - alto_bloque / 2
        else:
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

    # Para monstruos, alinea los valores a un y común.
    cy_medio_valores = None
    if es_monstruo:
        geom_valores = [g for id_a in ANCLAS_VALOR if (g := plantillas.ancla(svg, id_a))]
        if geom_valores:
            cy_medio_valores = sum(g["y"] + g["height"] / 2 for g in geom_valores) / len(geom_valores)

    for id_ancla, campo in ANCLAS_VALOR.items():
        g = plantillas.ancla(svg, id_ancla)
        if not g:
            continue
        valor = xml.sax.saxutils.escape(str(entrada.get(campo, "")))
        cx = g["x"] + g["width"] / 2
        if cy_medio_valores is not None:
            cy = cy_medio_valores + tam_valor / 3
        else:
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
    factor_res = _factor_res(padre)

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
    cuerpo = _inyectar_fondo(cuerpo, fondo_frag)

    return _documento_svg(padre, cuerpo)


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
    cuerpo = _inyectar_fondo(cuerpo, fondo_frag)

    return _documento_svg(padre, cuerpo)


def _frag_fondo(cara: dict, padre: str, factor_res: float = 1.0) -> str:
    """Fondo(s) de la cara `cara` ajustados al rectángulo de la carta.

    Delega en `render_utils.frag_fondo`, pasando la lista `archivos_fondo` de la
    receta. Ver la utilidad para el detalle del orden de renderizado.
    """
    return _frag_fondo_util(cara.get("archivos_fondo") or [], padre, factor_res)


# --------------------------------------------------------------------------
# Rasterizado a PNG (resvg)
# --------------------------------------------------------------------------

def render_png(entrada: dict) -> Image.Image:
    """Rasteriza el anverso de la carta del personaje a PNG con resvg."""
    return _rasterizar(render_svg(entrada))


def render_png_verso(entrada: dict) -> Image.Image:
    """Rasteriza el dorso de la carta del personaje a PNG con resvg."""
    return _rasterizar(render_svg_verso(entrada))

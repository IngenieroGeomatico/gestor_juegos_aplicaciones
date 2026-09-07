"""Genera una imagen del tablero y/o de una misión de HeroQuest.

Salida PNG (Pillow) y opcionalmente SVG, en juegos/heroquest/mapas/.

Ejemplos:
    uv run juegos/heroquest/scripts/mapa.py --tablero original
    uv run juegos/heroquest/scripts/mapa.py --tablero original --mision "El Refugio del Guardián"
    uv run juegos/heroquest/scripts/mapa.py --tablero original --mision "El Refugio del Guardián" --salida /tmp/mapa.png --svg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import base64
import io

from PIL import Image, ImageDraw, ImageFont

import data_store
import tablero

DATA_DIR = tablero.DATA_DIR
MAPAS_DIR = DATA_DIR.parent / "mapas"

# ── Carga de estilo.json ─────────────────────────────────────────────────────
_ESTILO_PATH = DATA_DIR / "estilo.json"

def _cargar_estilo() -> dict:
    with open(_ESTILO_PATH, encoding="utf-8") as f:
        return json.load(f)

_est = _cargar_estilo()

ICONOS_MAPA_DIR = DATA_DIR.parent / _est["sprite_dir"]

MUEBLE_GLIFO = _est["glifos"]
TRAMPA_ICONO = _est["trampas"]
MUEBLE_ICONO = _est["muebles"]
PUERTA_ICONO = _est["puertas"]["cerrada"]
PUERTA_ABIERTA_ICONO = _est["puertas"]["abierta"]
PUERTA_SECRETA_ICONO = _est["puertas"]["secreta"]
ENTRADA_ICONO = _est["entrada_salida"]["entrada"]
SALIDA_ICONO = _est["entrada_salida"]["salida"]
_CALAVERA_SLUG = _est["calavera"]

_c = _est["colores"]
COLOR_ENTRADA = _c["entrada"]
COLOR_ENTRADA_FONDO = _c["entrada_fondo"]
COLOR_PUERTA_ABIERTA = _c["puerta_abierta"]
COLOR_PUERTA_CERRADA = _c["puerta_cerrada"]
COLOR_SALIDA = _c["salida"]
COLOR_SALIDA_FONDO = _c["salida_fondo"]
COLOR_TESORO = _c["tesoro"]
COLOR_PASILLO = _c["pasillo"]
COLOR_ROCA = _c["roca"]
COLOR_ROCA_TRAMA = _c["roca_trama"]
COLOR_ROCA_FICHA = _c["roca_ficha"]

FUENTE_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PALETA = [
    "#e8b07a", "#d98c8c", "#8cc8d9", "#d99c86", "#c6c9e8",
    "#f2c66b", "#8fa8b8", "#b8d98c", "#d98ca8", "#9cb8d9",
    "#e0a66b", "#86c6a0", "#d8a0c6", "#a8b8e0", "#e8b86b",
    "#93b8d8", "#c98c98", "#b8a0e0", "#d0c090", "#98d0b0",
    "#e8a8a8", "#9cd0d0",
]


def _roca_textura(color: str) -> str:
    """Devuelve una variante clara del color de roca para los puntos de textura."""
    r, g, b = _hex_rgb(color)
    lum = int(0.299 * r + 0.587 * g + 0.114 * b)
    for i, c in enumerate((r, g, b)):
        n = min(255, c + (40 if lum > 100 else 60))
        if i == 0:
            r = n
        elif i == 1:
            g = n
        else:
            b = n
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex_rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = _hex_rgb(color)
    return r, g, b, alpha
MARCADORES = {
    "entrada": ("E", "#2e8b57"),
    "puerta": ("P", "#7a5230"),
    "puerta_secreta": ("S", "#5a3a8e"),
    "monstruo": ("M", "#c62828"),
    "tesoro": ("T", "#ffc107"),
    "trampa": ("X", "#b71c1c"),
    "marcador": ("F", "#37474f"),
}


def _fuente(tamano: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FUENTE_TTF, tamano)
    except OSError:
        return ImageFont.load_default()


def _color_celda(numero: int | None) -> str:
    if numero is None:
        return COLOR_PASILLO
    return PALETA[(numero - 1) % len(PALETA)]


def _icono_monstruo(nombre: str) -> str | None:
    """Devuelve la ruta absoluta al icono/retrato de un monstruo (plantillas.cara.arte_icono),
    o None si no hay registro o no se puede resolver."""
    for m in data_store.cargar("monstruos"):
        if m["nombre"] == nombre:
            ruta = m.get("plantillas", {}).get("cara", {}).get("arte_icono")
            if ruta:
                cand = (DATA_DIR.parent / ruta).resolve()
                if cand.exists():
                    return str(cand)
            return None
    return None


def _icono_mapa(slug: str | None) -> str | None:
    """Ruta absoluta a un icono de mapa en sources/arte_iconos/mapa/, o None.

    Resolución: si existe `{slug}_1.*` se usa ese; si no, `{slug}_0.*`.
    """
    if not slug:
        return None
    for sufijo in ("_1", "_0"):
        for ext in (".png", ".jpeg", ".jpg"):
            ruta = (ICONOS_MAPA_DIR / f"{slug}{sufijo}{ext}").resolve()
            if ruta.exists():
                return str(ruta)
    return None


def _icono_puerta(punto: dict) -> str | None:
    """Icono de puerta según su estado (abierta/cerrada)."""
    if _estado_puerta(punto) == "abierta":
        return _icono_mapa(PUERTA_ABIERTA_ICONO)
    return _icono_mapa(PUERTA_ICONO)


def _estado_puerta(punto: dict) -> str:
    return punto.get("estado", "cerrada")


def _orientacion_sprite(ruta_icono: str | None) -> str | None:
    """Devuelve 'HORIZ' o 'VERT' según el tamaño intrínseco del sprite, o None."""
    if not ruta_icono:
        return None
    try:
        with Image.open(ruta_icono) as im:
            w, h = im.size
        return "HORIZ" if w >= h else "VERT"
    except OSError:
        return None


def _orientacion_arte(elemento: dict, ruta_icono: str | None) -> str | None:
    """Orientación con la que el arte está dibujado ('HORIZ'/'VERT').

    La declara la misión en `elemento["arte"]["orientacion"]`
    ("horizontal"/"vertical"); si no se declara, se infiere del sprite."""
    decl = (elemento.get("arte") or {}).get("orientacion")
    if decl == "horizontal":
        return "HORIZ"
    if decl == "vertical":
        return "VERT"
    if decl == "auto" or decl is None:
        return _orientacion_sprite(ruta_icono)
    return None


def _gira_sprite(elemento: dict, ruta_icono: str | None,
                 pwx: float | int, ph: float | int) -> int:
    """Ángulo (0/90/180/270) para que el eje largo del arte coincida con el
    eje largo del rectángulo del elemento, más la inversión opcional (+180°).

    La orientación del arte y el invertir se leen de `elemento["arte"]`
    (transversal a todos los tipos de pieza)."""
    orient = _orientacion_arte(elemento, ruta_icono)
    rect_horiz = pwx >= ph
    angulo = 0
    if orient == "VERT" and rect_horiz:
        angulo = 90
    elif orient == "HORIZ" and not rect_horiz:
        angulo = 90
    if (elemento.get("arte") or {}).get("invertir"):
        angulo += 180
    return angulo % 360


def _pega_icono(img: Image.Image, ruta_icono: str, cx: float, cy: float,
                w: int, h: int, angulo: int = 0) -> None:
    """Pega un icono en (cx, cy) dentro de una caja w×h. Rota el sprite si
    procede y luego lo escala para LLENAR la caja (recortando el sobrante)."""
    im = Image.open(ruta_icono).convert("RGBA")
    if angulo:
        im = im.rotate(angulo, expand=True, resample=Image.BICUBIC)
    escala = max(w / im.width, h / im.height)
    nuevo = (max(1, int(im.width * escala)), max(1, int(im.height * escala)))
    im = im.resize(nuevo, Image.LANCZOS)
    lienzo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = (w - im.width) // 2
    y = (h - im.height) // 2
    lienzo.paste(im, (x, y), im)
    img.paste(lienzo, (int(cx - w / 2), int(cy - h / 2)), lienzo)


def _icono_orientado_peq(ruta: str, angulo: int, tamano: int) -> str:
    """Rota realmente el sprite y lo reduce a un cuadrado pequeño comprimido,
    devolviendo un data URI. Se usa para incrustarlo ya girado en el SVG."""
    im = Image.open(ruta).convert("RGBA")
    if angulo:
        im = im.rotate(angulo, expand=True, resample=Image.BICUBIC)
    im.thumbnail((tamano, tamano), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _icono_data_uri(ruta: str) -> str:
    """Convierte una imagen PNG en un data URI base64 para incrustar en SVG."""
    with open(ruta, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _icono_data_uri_peq(ruta: str, tamano: int) -> str:
    """Igual que _icono_data_uri pero reduciendo la imagen a un cuadrado pequeño
    (tamaño de celda) y comprimiéndola, para no inflar el SVG embebido."""
    im = _imagen_escala(ruta, tamano)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _imagen_escala(ruta: str, tamano: int) -> Image.Image:
    """Carga una imagen y la ajusta a un cuadrado de 'tamano' px con fondo transparente."""
    im = Image.open(ruta).convert("RGBA")
    im.thumbnail((tamano, tamano), Image.LANCZOS)
    lienzo = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    x = (tamano - im.width) // 2
    y = (tamano - im.height) // 2
    lienzo.paste(im, (x, y), im)
    return lienzo


def _cargar_mision(nombre: str | None) -> dict | None:
    if not nombre:
        return None
    for m in data_store.cargar("misiones"):
        if m["nombre"] == nombre:
            return m
    print(f"Error: no existe la misión '{nombre}'")
    sys.exit(1)


def _nombre_archivo(tablero_id: str, mision: dict | None, ext: str) -> Path:
    base = tablero_id if not mision else f"{tablero_id}__{data_store.slug(mision['nombre'])}"
    return MAPAS_DIR / f"{base}.{ext}"


def _nombre_archivo_coordenadas(tablero_id: str, mision: dict | None, ext: str) -> Path:
    """Nombre del mapa con etiquetas de coordenadas por celda (en vez de IDs de sala)."""
    base = tablero_id if not mision else f"{tablero_id}__{data_store.slug(mision['nombre'])}"
    return MAPAS_DIR / f"{base}__coordenadas.{ext}"


def _puntos_mision(mision: dict) -> list[tuple[str, dict]]:
    """Devuelve los marcadores de una misión: (tipo, punto) en coordenadas de la cuadrícula."""
    puntos: list[tuple[str, dict]] = []
    for p in mision.get("entrada_heroes", []):
        puntos.append(("entrada", p))
    for p in mision.get("puertas", []):
        puntos.append(("puerta", p))
    for p in mision.get("puertas_secretas", []):
        puntos.append(("puerta_secreta", p))
    for sala in mision.get("salas", []):
        for m in sala.get("monstruos", []):
            puntos.append(("monstruo", m))
        for tr in sala.get("tesoros", []):
            puntos.append(("tesoro", tr))
        for tr in sala.get("trampas", []):
            puntos.append(("trampa", tr))
        for ma in sala.get("marcadores", []):
            puntos.append(("marcador", ma))
    # Elementos en pasillo (fuera de sala)
    for tipo_clave, tipo in (("monstruos", "monstruo"), ("tesoros", "tesoro"),
                             ("trampas", "trampa"), ("marcadores", "marcador")):
        for it in mision.get("pasillos", {}).get(tipo_clave, []):
            puntos.append((tipo, it))
    return puntos


def _muebles_mision(mision: dict) -> list[tuple[int, dict]]:
    """Devuelve los muebles de una misión: (numero_sala, mueble) en coordenadas de cuadrícula."""
    resultado: list[tuple[int, dict]] = []
    for sala in mision.get("salas", []):
        for mu in sala.get("muebles", []):
            resultado.append((sala["numero"], mu))
    return resultado


def _render_png(t: dict, mision: dict | None, w: int, h: int, titulo: int, margen: int, celda: int, ruta: Path) -> Path:
    img = Image.new("RGB", (w, h), "#f7f3ea")
    d = ImageDraw.Draw(img)
    nombre = t["nombre"] if not mision else f"{t['nombre']} · {mision['nombre']}"
    d.text((w // 2, 14), nombre, fill="#1a1a1a", font=_fuente(22), anchor="mm")
    ox, oy = margen, titulo + margen
    for y in range(1, t["filas"] + 1):
        for x in range(1, t["columnas"] + 1):
            num = tablero.sala_en(t, x, y)
            roca = tablero.es_no_jugable(t, x, y)
            px, py = ox + (x - 1) * celda, oy + (y - 1) * celda
            if roca:
                color_roca = _color_roca_celda(t, x, y)
                d.rectangle([px, py, px + celda, py + celda], fill=color_roca, outline="#000")
                d.point([(px + int(celda * 0.35), py + int(celda * 0.4)),
                         (px + int(celda * 0.6), py + int(celda * 0.65))], fill=_roca_textura(color_roca))
            else:
                d.rectangle([px, py, px + celda, py + celda], fill=_color_celda(num), outline="#000")
                if num is not None:
                    d.text((px + celda / 2, py + celda / 2), str(num), fill="#333",
                           font=_fuente(int(celda * 0.5)), anchor="mm")
    _salas_no_jugables_png(img, t, mision, ox, oy, celda, w, h)
    _salida_png(img, mision, ox, oy, celda)
    _entrada_png(img, mision, ox, oy, celda)
    resaltes: list = []
    _muebles_png(img, resaltes, mision, ox, oy, celda)
    _marcadores_png(img, resaltes, mision, ox, oy, celda)
    if resaltes:
        d2 = ImageDraw.Draw(img)
        for r in resaltes:
            px, py, qx, qy, color, grosor = r
            d2.rectangle([px, py, qx, qy], outline=color, width=grosor)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    img.save(ruta)
    return ruta


def _rect_salida(salida) -> tuple[int, int, int, int]:
    """Devuelve el rectángulo (c1, f1, c2, f2) que envuelve las casillas de salida.
    Acepta una lista de casillas {x, y} o un umbral {de: [x, y], a: [x, y]}."""
    if isinstance(salida, dict) and "de" in salida:
        de, a = salida["de"], salida["a"]
        xs, ys = (de[0], a[0]), (de[1], a[1])
    else:
        salida = [salida] if isinstance(salida, dict) else salida
        xs = [p["x"] for p in salida]
        ys = [p["y"] for p in salida]
    return min(xs), min(ys), max(xs), max(ys)


def _color_roca_celda(t: dict, x: int, y: int) -> str:
    """Color de roca de una casilla: pieza suelta (ficha) si está dentro del
    tablero (no en el marco), roca dura de fondo si está en el borde."""
    if 1 < x < t["columnas"] and 1 < y < t["filas"]:
        return COLOR_ROCA_FICHA
    return COLOR_ROCA


def _salas_no_jugables_png(img: Image.Image, t: dict, mision: dict | None,
                           ox: int, oy: int, celda: int, w: int, h: int) -> None:
    """Raya en diagonal semitransparente (50%) las celdas no jugables: la roca dura
    del tablero siempre, y además las salas no usadas en la misión (si hay misión)."""
    rects: list[tuple[int, int, int, int]] = []
    for y in range(1, t["filas"] + 1):
        for x in range(1, t["columnas"] + 1):
            if tablero.es_no_jugable(t, x, y):
                px = ox + (x - 1) * celda
                py = oy + (y - 1) * celda
                rects.append((px, py, px + celda, py + celda))
    if mision:
        usadas = {s["numero"] for s in mision.get("salas", [])}
        for sala in t["salas"]:
            if sala["numero"] in usadas:
                continue
            for r in sala["rects"]:
                px = ox + (r["x"] - 1) * celda
                py = oy + (r["y"] - 1) * celda
                rects.append((px, py, px + r["ancho"] * celda, py + r["alto"] * celda))
    if not rects:
        return
    # Trama diagonal global continua (50% de opacidad)
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    linea = _hex_rgba(COLOR_ROCA_TRAMA, 128)
    espacio = 8
    for k in range(-(h // espacio) - 1, (w + h) // espacio + 1):
        dc.line([(k * espacio, 0 - h), (k * espacio + h, h)], fill=linea, width=3)
    # Máscara con las zonas no jugables
    mascara = Image.new("L", img.size, 0)
    dm = ImageDraw.Draw(mascara)
    for px, py, qx, qy in rects:
        dm.rectangle([px, py, qx, qy], fill=255)
    img.paste(capa, (0, 0), mascara)


def _salida_png(img: Image.Image, mision: dict | None, ox: int, oy: int, celda: int) -> None:
    """Marca la escalera de salida como un CUADRADO con peldaños y su icono."""
    d = ImageDraw.Draw(img)
    salida = (mision or {}).get("salida_heroes") or []
    if not salida:
        return
    c1, f1, c2, f2 = _rect_salida(salida)
    px = ox + (c1 - 1) * celda
    py = oy + (f1 - 1) * celda
    pwx = (c2 - c1 + 1) * celda
    ph = (f2 - f1 + 1) * celda
    lado = min(pwx, ph)
    sx = px + (pwx - lado) / 2
    sy = py + (ph - lado) / 2
    d.rectangle([sx, sy, sx + lado, sy + lado], fill=COLOR_SALIDA_FONDO,
                outline=COLOR_SALIDA, width=max(3, celda // 6))
    for i in range(1, f2 - f1 + 1):
        yy = py + i * celda
        if sy + 3 < yy < sy + lado - 3:
            d.line([(sx + 3, yy), (sx + lado - 3, yy)], fill=COLOR_SALIDA, width=2)
    icono = _icono_mapa(SALIDA_ICONO)
    if icono:
        _pega_icono(img, icono, sx + lado / 2, sy + lado / 2, int(lado * 0.82), int(lado * 0.82))
    else:
        d.text((sx + lado / 2, sy + lado / 2), "S", fill=COLOR_SALIDA,
               font=_fuente(int(lado * 0.6)), anchor="mm")


def _entrada_png(img: Image.Image, mision: dict | None, ox: int, oy: int, celda: int) -> None:
    """Marca la entrada de héroes como un único CUADRADO con su icono."""
    entrada = (mision or {}).get("entrada_heroes", [])
    if not entrada:
        return
    d = ImageDraw.Draw(img)
    c1, f1, c2, f2 = _rect_salida(entrada)
    px = ox + (c1 - 1) * celda
    py = oy + (f1 - 1) * celda
    pwx = (c2 - c1 + 1) * celda
    ph = (f2 - f1 + 1) * celda
    lado = min(pwx, ph)
    sx = px + (pwx - lado) / 2
    sy = py + (ph - lado) / 2
    d.rectangle([sx, sy, sx + lado, sy + lado], fill=COLOR_ENTRADA_FONDO,
                outline=COLOR_ENTRADA, width=max(3, celda // 6))
    icono = _icono_mapa(ENTRADA_ICONO)
    if icono:
        _pega_icono(img, icono, sx + lado / 2, sy + lado / 2, int(lado * 0.86), int(lado * 0.86))
    else:
        d.text((sx + lado / 2, sy + lado / 2), "E", fill=COLOR_SALIDA,
               font=_fuente(int(lado * 0.6)), anchor="mm")


def _muebles_png(img: Image.Image, resaltes: list, mision: dict | None,
                 ox: int, oy: int, celda: int) -> None:
    if not mision:
        return
    d = ImageDraw.Draw(img)
    for num_sala, mu in _muebles_mision(mision):
        x1, y1 = mu["desde"]
        x2, y2 = mu["hasta"]
        px = ox + (x1 - 1) * celda
        py = oy + (y1 - 1) * celda
        pwx = (x2 - x1 + 1) * celda
        ph = (y2 - y1 + 1) * celda
        # Cuerpo del mueble (tono madera, semi)
        d.rounded_rectangle([px, py, px + pwx, py + ph], radius=5,
                            fill=(180, 140, 90, 255), outline=(90, 60, 30))
        # Borde amarillo si contiene tesoro del Reto (se pinta encima al final)
        if mu.get("tesoro"):
            resaltes.append((px, py, px + pwx, py + ph, COLOR_TESORO, max(3, celda // 8)))
        icono = _icono_mapa(MUEBLE_ICONO.get(mu.get("tipo", "")))
        if icono:
            angulo = _gira_sprite(mu, icono, pwx, ph)
            _pega_icono(img, icono, px + pwx / 2, py + ph / 2,
                        int(pwx * 0.86), int(ph * 0.86), angulo)
        else:
            glifo = MUEBLE_GLIFO.get(mu.get("tipo", ""), "?")
            d.text((px + pwx / 2, py + ph / 2), glifo, fill=(60, 35, 10),
                   font=_fuente(int(min(pwx, ph) * 0.7)), anchor="mm")


def _marcadores_png(img: Image.Image, resaltes: list, mision: dict | None,
                    ox: int, oy: int, celda: int) -> None:
    if not mision:
        return
    d = ImageDraw.Draw(img)
    r = int(celda * 0.36)
    for tipo, punto in _puntos_mision(mision):
        gx, gy = _centro(punto)
        cx, cy = ox + (gx - 0.5) * celda, oy + (gy - 0.5) * celda
        letra, color = MARCADORES[tipo]
        if tipo == "monstruo":
            icono = _icono_monstruo(punto.get("nombre", ""))
            if icono:
                tam = int(celda * 0.82)
                im = _imagen_escala(icono, tam)
                img.paste(im, (int(cx - tam / 2), int(cy - tam / 2)), im)
                if punto.get("tesoro"):
                    resaltes.append((cx - tam / 2 - 2, cy - tam / 2 - 2,
                                     cx + tam / 2 + 2, cy + tam / 2 + 2,
                                     COLOR_TESORO, max(3, celda // 8)))
                continue
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
            d.text((cx, cy), _inicial(punto, tipo), fill="#fff",
                   font=_fuente(int(r * 1.2)), anchor="mm")
        elif tipo == "tesoro":
            d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=color, outline="#000")
            d.text((cx, cy), _inicial(punto, tipo), fill="#000", font=_fuente(int(r)), anchor="mm")
        elif tipo == "puerta":
            x1, y1, x2, y2 = _rect_puerta(punto, cx, cy, r, celda)
            ancho, alto = x2 - x1, y2 - y1
            icono = _icono_puerta(punto)
            if icono:
                angulo = _gira_sprite(punto, icono, ancho, alto)
                caja_w, caja_h = ancho + 8, alto + 8
                _pega_icono(img, icono, cx, cy, int(caja_w), int(caja_h), angulo)
            else:
                d.rectangle([x1, y1, x2, y2], fill=color, outline="#000")
                d.text((cx, cy), letra, fill="#fff", font=_fuente(int(r)), anchor="mm")
        elif tipo == "puerta_secreta":
            x1, y1, x2, y2 = _rect_puerta(punto, cx, cy, r, celda)
            ancho, alto = x2 - x1, y2 - y1
            icono = _icono_mapa(PUERTA_SECRETA_ICONO)
            if icono:
                angulo = _gira_sprite(punto, icono, ancho, alto)
                _pega_icono(img, icono, cx, cy, int(max(ancho, alto) + 8), int(max(ancho, alto) + 8), angulo)
            else:
                d.rectangle([x1, y1, x2, y2], fill=color, outline="#000")
                d.text((cx, cy), letra, fill="#fff", font=_fuente(int(r)), anchor="mm")
        elif tipo == "trampa":
            icono = _icono_mapa(TRAMPA_ICONO.get(punto.get("nombre", "")))
            if icono:
                _pega_icono(img, icono, cx, cy, celda, celda)
            else:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
                m = int(r * 0.7)
                d.line([(cx - m, cy - m), (cx + m, cy + m)], fill="#fff", width=2)
                d.line([(cx - m, cy + m), (cx + m, cy - m)], fill="#fff", width=2)
        elif tipo == "marcador":
            icono = None
            if "calavera" in (punto.get("nombre") or "").lower():
                icono = _icono_mapa(_CALAVERA_SLUG)
            if icono:
                _pega_icono(img, icono, cx, cy, celda, celda)
            else:
                d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=color, outline="#000")
                d.text((cx, cy), "F", fill="#fff", font=_fuente(int(r)), anchor="mm")
        elif tipo == "entrada":
            continue  # se dibuja como cuadrado único con _entrada_png
        else:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
            d.text((cx, cy), _inicial(punto, tipo), fill="#fff",
                   font=_fuente(int(r * 1.2)), anchor="mm")


def _inicial(punto: dict, tipo: str) -> str:
    nombre = punto.get("nombre", "")
    return nombre[0].upper() if nombre else "?"


def _centro(punto: dict) -> tuple[float, float]:
    """Devuelve el centro (cx, cy) en coordenadas de casilla (enteras) de un punto.
    Acepta {x, y} (casilla) o {de, a} (umbral: devuelve el punto medio)."""
    if "de" in punto and "a" in punto:
        de, a = punto["de"], punto["a"]
        return (de[0] + a[0]) / 2, (de[1] + a[1]) / 2
    return punto["x"], punto["y"]


def _rect_puerta(punto: dict, cx: float, cy: float, r: float,
                 celda: int | None = None) -> tuple[float, float, float, float]:
    """Devuelve las 4 coordenadas (x1, y1, x2, y2) del rectángulo de una puerta.

    La puerta se centra en el muro que une las dos celdas:
    - celdas lado a lado (misma fila Y, X varía) -> muro vertical -> rect VERTICAL
    - celdas apiladas (misma columna X, Y varía)  -> muro horizontal -> rect HORIZONTAL
    - sin {de/a} -> por defecto horizontal.

    Con `celda` (recomendado) el eje largo se limita para que el arte embebido
    (que añade +8 px de margen de recorte en el render) no sobresalga de la
    celda. El grueso se mantiene como `r * 0.5`.
    """
    vertical = False
    if "de" in punto and "a" in punto:
        de, a = punto["de"], punto["a"]
        vertical = de[1] == a[1]  # misma fila Y -> lado a lado -> rect vertical
    if celda:
        medio_largo = max(4.0, (celda - 10) / 2)  # arte (rect + 8) dentro de la celda
    else:
        medio_largo = r * 1.5
    medio_ancho = r * 0.5
    if vertical:
        return cx - medio_ancho, cy - medio_largo, cx + medio_ancho, cy + medio_largo
    return cx - medio_largo, cy - medio_ancho, cx + medio_largo, cy + medio_ancho


def _render_svg(t: dict, mision: dict | None, w: int, h: int, titulo: int, margen: int, celda: int,
                mostrar: str = "salas", sufijo_id: str = "") -> str:
    """Renderiza el SVG del tablero.

    `mostrar` controla la etiqueta de cada celda jugable:
      - "salas": el número de la sala (comportamiento original).
      - "coordenadas": las coordenadas x,y de la celda, manteniendo el color de
        fondo de la sala a la que pertenece.
    Las piezas/fondos del tablero se dibujan igual en ambas variantes.
    """
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    nombre = t["nombre"] if not mision else f"{t['nombre']} · {mision['nombre']}"
    partes.append(f'<text x="{w/2}" y="{titulo-12}" font-family="sans-serif" font-size="20" font-weight="bold" text-anchor="middle">{nombre}</text>')
    ox, oy = margen, titulo + margen
    for y in range(1, t["filas"] + 1):
        for x in range(1, t["columnas"] + 1):
            num = tablero.sala_en(t, x, y)
            roca = tablero.es_no_jugable(t, x, y)
            px, py = ox + (x - 1) * celda, oy + (y - 1) * celda
            if roca:
                color_roca = _color_roca_celda(t, x, y)
                partes.append(
                    f'<rect x="{px}" y="{py}" width="{celda}" height="{celda}" '
                    f'fill="{color_roca}" stroke="#000" stroke-width="0.8"/>'
                )
                texto = _roca_textura(color_roca)
                partes.append(f'<circle cx="{px + celda * 0.35}" cy="{py + celda * 0.4}" r="2" fill="{texto}"/>')
                partes.append(f'<circle cx="{px + celda * 0.6}" cy="{py + celda * 0.65}" r="2" fill="{texto}"/>')
            else:
                partes.append(
                    f'<rect x="{px}" y="{py}" width="{celda}" height="{celda}" '
                    f'fill="{_color_celda(num)}" stroke="#000" stroke-width="0.8"/>'
                )
                if num is not None:
                    if mostrar == "coordenadas":
                        etiqueta = f"{x},{y}"
                        tam_txt = max(6, int(celda * 0.38))
                    else:
                        etiqueta = str(num)
                        tam_txt = int(celda * 0.55)
                    partes.append(
                        f'<text x="{px+celda/2}" y="{py+celda/2+6}" font-family="sans-serif" '
                        f'font-size="{tam_txt}" text-anchor="middle" fill="#333">{etiqueta}</text>'
                    )
                elif mostrar == "coordenadas":
                    partes.append(
                        f'<text x="{px+celda/2}" y="{py+celda/2+4}" font-family="sans-serif" '
                        f'font-size="{max(6, int(celda * 0.34))}" text-anchor="middle" '
                        f'fill="#333">{x},{y}</text>'
                    )
    _salas_no_jugables_svg(partes, t, mision, ox, oy, celda, sufijo_id)
    _salida_svg(partes, mision, ox, oy, celda)
    _entrada_svg(partes, mision, ox, oy, celda)
    resaltes: list[str] = []
    _muebles_svg(partes, resaltes, mision, ox, oy, celda)
    _marcadores_svg(partes, resaltes, mision, ox, oy, celda)
    if resaltes:
        partes.append('<g id="resaltes">')
        partes.extend(resaltes)
        partes.append('</g>')
    partes.append("</svg>")
    return "\n".join(partes)


def _salas_no_jugables_svg(partes: list[str], t: dict, mision: dict | None,
                           ox: int, oy: int, celda: int,
                           sufijo_id: str = "") -> None:
    """Cubre con roca semitransparente (50%) las celdas no jugables: la roca dura
    del tablero siempre, y además las salas no usadas en la misión (si hay misión)."""
    rects: list[tuple[int, int, int, int]] = []
    for y in range(1, t["filas"] + 1):
        for x in range(1, t["columnas"] + 1):
            if tablero.es_no_jugable(t, x, y):
                px = ox + (x - 1) * celda
                py = oy + (y - 1) * celda
                rects.append((px, py, celda, celda))
    if mision:
        usadas = {s["numero"] for s in mision.get("salas", [])}
        for sala in t["salas"]:
            if sala["numero"] in usadas:
                continue
            for r in sala["rects"]:
                px = ox + (r["x"] - 1) * celda
                py = oy + (r["y"] - 1) * celda
                rects.append((px, py, r["ancho"] * celda, r["alto"] * celda))
    if not rects:
        return
    patron_id = f"rayas-roca{sufijo_id}"
    partes.append(
        f'<defs>'
        f'<pattern id="{patron_id}" width="8" height="8" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="8" y2="8" stroke="{COLOR_ROCA_TRAMA}" stroke-width="4" '
        f'stroke-opacity="0.5"/>'
        f'</pattern>'
        f'</defs>'
    )
    for px, py, ancho, alto in rects:
        partes.append(
            f'<rect x="{px}" y="{py}" width="{ancho}" height="{alto}" '
            f'fill="url(#{patron_id})"/>'
        )


def _salida_svg(partes: list[str], mision: dict | None, ox: int, oy: int, celda: int) -> None:
    """Marca la escalera de salida de la misión como un CUADRADO con peldaños."""
    salida = (mision or {}).get("salida_heroes") or []
    if not salida:
        return
    c1, f1, c2, f2 = _rect_salida(salida)
    px = ox + (c1 - 1) * celda
    py = oy + (f1 - 1) * celda
    pwx = (c2 - c1 + 1) * celda
    ph = (f2 - f1 + 1) * celda
    lado = min(pwx, ph)
    sx = px + (pwx - lado) / 2
    sy = py + (ph - lado) / 2
    g = max(3, celda // 6)
    partes.append(
        f'<rect x="{sx}" y="{sy}" width="{lado}" height="{lado}" fill="{COLOR_SALIDA_FONDO}" '
        f'stroke="{COLOR_SALIDA}" stroke-width="{g}"/>'
    )
    for i in range(1, f2 - f1 + 1):
        yy = py + i * celda
        if sy + 3 < yy < sy + lado - 3:
            partes.append(
                f'<line x1="{sx + 3}" y1="{yy}" x2="{sx + lado - 3}" y2="{yy}" '
                f'stroke="{COLOR_SALIDA}" stroke-width="2"/>'
            )
    if not _imagen_svg(partes, SALIDA_ICONO, sx + lado / 2, sy + lado / 2, int(lado * 0.82)):
        partes.append(
            f'<text x="{sx + lado / 2}" y="{sy + lado / 2 + 6}" font-family="sans-serif" '
            f'font-size="{int(lado * 0.55)}" font-weight="bold" text-anchor="middle" '
            f'fill="{COLOR_SALIDA}">S</text>'
        )


def _entrada_svg(partes: list[str], mision: dict | None, ox: int, oy: int, celda: int) -> None:
    """Marca la entrada de héroes como un único CUADRADO con su icono."""
    entrada = (mision or {}).get("entrada_heroes", [])
    if not entrada:
        return
    c1, f1, c2, f2 = _rect_salida(entrada)
    px = ox + (c1 - 1) * celda
    py = oy + (f1 - 1) * celda
    pwx = (c2 - c1 + 1) * celda
    ph = (f2 - f1 + 1) * celda
    lado = min(pwx, ph)
    sx = px + (pwx - lado) / 2
    sy = py + (ph - lado) / 2
    g = max(3, celda // 6)
    partes.append(
        f'<rect x="{sx}" y="{sy}" width="{lado}" height="{lado}" fill="{COLOR_ENTRADA_FONDO}" '
        f'stroke="{COLOR_ENTRADA}" stroke-width="{g}"/>'
    )
    _imagen_svg(partes, ENTRADA_ICONO, sx + lado / 2, sy + lado / 2, int(lado * 0.86))


def _muebles_svg(partes: list[str], resaltes: list[str], mision: dict | None,
                 ox: int, oy: int, celda: int) -> None:
    if not mision:
        return
    for num_sala, mu in _muebles_mision(mision):
        x1, y1 = mu["desde"]
        x2, y2 = mu["hasta"]
        px = ox + (x1 - 1) * celda
        py = oy + (y1 - 1) * celda
        pwx = (x2 - x1 + 1) * celda
        ph = (y2 - y1 + 1) * celda
        partes.append(
            f'<rect x="{px}" y="{py}" width="{pwx}" height="{ph}" rx="5" '
            f'fill="#b48c5a" stroke="#5a3c1e" stroke-width="1.5"/>'
        )
        if mu.get("tesoro"):
            t = max(4, celda // 6)
            resaltes.append(
                f'<rect x="{px - t}" y="{py - t}" width="{pwx + 2 * t}" height="{ph + 2 * t}" rx="7" '
                f'fill="none" stroke="{COLOR_TESORO}" stroke-width="{t}"/>'
            )
        cxm, cym = px + pwx / 2, py + ph / 2
        icono_mueble = MUEBLE_ICONO.get(mu.get("tipo", ""))
        angulo = _gira_sprite(mu, _icono_mapa(icono_mueble), pwx, ph)
        if not _imagen_svg(partes, icono_mueble,
                           cxm, cym, min(pwx, ph) * 0.86, angulo=angulo,
                           caja_w=pwx * 0.86, caja_h=ph * 0.86):
            glifo = MUEBLE_GLIFO.get(mu.get("tipo", ""), "?")
            tam_txt = int(min(pwx, ph) * 0.6)
            partes.append(
                f'<text x="{cxm}" y="{cym + tam_txt / 3}" font-family="sans-serif" font-size="{tam_txt}" '
                f'font-weight="bold" text-anchor="middle" fill="#3c230a">{glifo}</text>'
            )


def _imagen_svg(partes: list[str], slug: str | None, cx: float | int, cy: float | int,
                tam: float | int, angulo: int = 0, caja_w: float | int | None = None,
                caja_h: float | int | None = None) -> bool:
    """Embebe un icono de mapa centrado en (cx, cy) llenando la caja w×h;
    devuelve False si no existe. Rotación aplicada de verdad a los píxeles
    (no a un <g>), de modo que el recorte 'slice' sea correcto."""
    icono = _icono_mapa(slug)
    if not icono:
        return False
    w = caja_w if caja_w is not None else tam
    h = caja_h if caja_h is not None else tam
    uri = _icono_orientado_peq(icono, angulo % 360, 180)
    img = (
        f'<image x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" '
        f'href="{uri}" preserveAspectRatio="xMidYMid slice"/>'
    )
    partes.append(img)
    return True


def _marcadores_svg(partes: list[str], resaltes: list[str], mision: dict | None,
                    ox: int, oy: int, celda: int) -> None:
    if not mision:
        return
    r = celda * 0.36
    for tipo, punto in _puntos_mision(mision):
        gx, gy = _centro(punto)
        cx, cy = ox + (gx - 0.5) * celda, oy + (gy - 0.5) * celda
        letra, color = MARCADORES[tipo]
        if tipo == "monstruo":
            icono = _icono_monstruo(punto.get("nombre", ""))
            if icono:
                tam = int(celda * 0.82)
                uri = _icono_data_uri_peq(icono, int(tam * 3))
                x0, y0 = cx - tam / 2, cy - tam / 2
                partes.append(
                    f'<image x="{x0}" y="{y0}" width="{tam}" height="{tam}" href="{uri}" '
                    f'preserveAspectRatio="xMidYMid meet"/>'
                )
                if punto.get("tesoro"):
                    t = max(4, celda // 6)
                    resaltes.append(
                        f'<rect x="{x0 - t}" y="{y0 - t}" width="{tam + 2 * t}" height="{tam + 2 * t}" '
                        f'rx="4" fill="none" stroke="{COLOR_TESORO}" stroke-width="{t}"/>'
                    )
                continue
            partes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="#000"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#fff" font-weight="bold">{_inicial(punto, tipo)}</text>')
        elif tipo == "tesoro":
            partes.append(f'<polygon points="{cx},{cy-r} {cx+r},{cy} {cx},{cy+r} {cx-r},{cy}" fill="{color}" stroke="#000"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#000" font-weight="bold">{_inicial(punto, tipo)}</text>')
        elif tipo == "puerta":
            x1, y1, x2, y2 = _rect_puerta(punto, cx, cy, r, celda)
            ancho, alto = x2 - x1, y2 - y1
            estado = _estado_puerta(punto)
            slug_puerta = PUERTA_ABIERTA_ICONO if estado == "abierta" else PUERTA_ICONO
            icono_puerta = _icono_mapa(slug_puerta)
            angulo = _gira_sprite(punto, icono_puerta, ancho, alto)
            idx_puerta = len([p for p in partes if 'class="puerta' in p])
            partes.append(f'<g id="puerta-{idx_puerta}" class="puerta-interactiva" '
                         f'data-estado="{estado}" data-de="{punto["de"]}" data-a="{punto["a"]}" '
                         f'data-angulo="{angulo}" '
                         f'style="cursor:pointer">')
            if not _imagen_svg(partes, slug_puerta, cx, cy, max(ancho, alto) + 8,
                               angulo=angulo, caja_w=ancho + 8, caja_h=alto + 8):
                partes.append(f'<rect x="{x1}" y="{y1}" width="{ancho}" height="{alto}" fill="{color}" stroke="#000"/>')
                partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#fff" font-weight="bold">{letra}</text>')
            partes.append('</g>')
        elif tipo == "puerta_secreta":
            x1, y1, x2, y2 = _rect_puerta(punto, cx, cy, r, celda)
            ancho, alto = x2 - x1, y2 - y1
            icono_psecreta = _icono_mapa(PUERTA_SECRETA_ICONO)
            angulo = _gira_sprite(punto, icono_psecreta, ancho, alto)
            if not _imagen_svg(partes, PUERTA_SECRETA_ICONO, cx, cy, max(ancho, alto) + 8,
                               angulo=angulo, caja_w=ancho + 8, caja_h=alto + 8):
                partes.append(f'<rect x="{x1}" y="{y1}" width="{ancho}" height="{alto}" fill="{color}" stroke="#000"/>')
                partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#fff" font-weight="bold">{letra}</text>')
        elif tipo == "trampa":
            if not _imagen_svg(partes, TRAMPA_ICONO.get(punto.get("nombre", "")),
                               cx, cy, celda):
                partes.append(f'<circle cx="{cx}" cy="{cy}" r="{int(r*0.9)}" fill="{color}" stroke="#000"/>')
                m = int(r * 0.7)
                for dx, dy in ((-1, -1), (1, 1)):
                    partes.append(f'<line x1="{cx+dx*m}" y1="{cy+dy*m}" x2="{cx-dx*m}" y2="{cy-dy*m}" stroke="#fff" stroke-width="2"/>')
        elif tipo == "marcador":
            if "calavera" in (punto.get("nombre") or "").lower():
                if _imagen_svg(partes, _CALAVERA_SLUG, cx, cy, celda):
                    continue
            partes.append(f'<rect x="{cx-r}" y="{cy-r}" width="{2*r}" height="{2*r}" fill="{color}" stroke="#000" transform="rotate(45 {cx} {cy})"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.8)}" text-anchor="middle" fill="#fff" font-weight="bold">F</text>')
        elif tipo == "entrada":
            continue  # se dibuja como cuadrado único con _entrada_svg
        else:
            partes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="#000"/>')
            texto = _inicial(punto, tipo)
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#fff" font-weight="bold">{texto}</text>')


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una imagen del tablero/misión de HeroQuest")
    parser.add_argument("--tablero", required=True, help="ID del tablero (original, cara-b)")
    parser.add_argument("--mision", default=None, help="Nombre de la misión a dibujar encima")
    parser.add_argument("--svg", action="store_true", help="Escribir también el SVG")
    parser.add_argument("--salida", default=None, help="Ruta PNG de salida (por defecto en mapas/)")
    args = parser.parse_args()

    mision = _cargar_mision(args.mision)
    t = tablero.cargar_tablero(args.tablero)
    if not t["salas"]:
        print(f"Error: el tablero '{args.tablero}' aún no está modelado ({t['nota']})")
        sys.exit(1)

    celda = 34 if mision else 30
    margen = titulo = 40
    w = margen * 2 + t["columnas"] * celda
    h = titulo + margen * 2 + t["filas"] * celda

    if args.svg:
        ruta_svg = _nombre_archivo(args.tablero, mision, "svg")
        ruta_svg.parent.mkdir(parents=True, exist_ok=True)
        ruta_svg.write_text(_render_svg(t, mision, w, h, titulo, margen, celda),
                            encoding="utf-8")
        print(f"SVG: {ruta_svg}")
        if not mision:
            ruta_coords = _nombre_archivo_coordenadas(args.tablero, mision, "svg")
            ruta_coords.write_text(
                _render_svg(t, mision, w, h, titulo, margen, celda, mostrar="coordenadas"),
                encoding="utf-8")
            print(f"SVG: {ruta_coords}")

    ruta_png = Path(args.salida) if args.salida else _nombre_archivo(args.tablero, mision, "png")
    _render_png(t, mision, w, h, titulo, margen, celda, ruta_png)
    print(f"PNG: {ruta_png}")


if __name__ == "__main__":
    main()
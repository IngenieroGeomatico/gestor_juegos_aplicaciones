"""Genera una imagen del tablero y/o de una misión de HeroQuest.

Salida PNG (Pillow) y opcionalmente SVG, en juegos/heroquest/mapas/.

Ejemplos:
    uv run juegos/heroquest/scripts/mapa.py --tablero original
    uv run juegos/heroquest/scripts/mapa.py --tablero original --mision "El Refugio del Guardián"
    uv run juegos/heroquest/scripts/mapa.py --tablero original --mision "El Refugio del Guardián" --salida /tmp/mapa.png --svg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import base64
import io

from PIL import Image, ImageDraw, ImageFont

import data_store
import tablero

DATA_DIR = tablero.DATA_DIR
MAPAS_DIR = DATA_DIR.parent / "mapas"

# Iconos de muebles: glifo (o imagen) por tipo
MUEBLE_GLIFO = {
    "Mesa": "M",
    "Alacena": "A",
    "Chimenea": "C",
    "Tumba": "T",
    "Cofre": "C",
    "Banco de Alquimista": "B",
}
COLOR_TESORO = "#f6c700"  # borde amarillo para contenedor con tesoro del Reto

FUENTE_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PALETA = [
    "#e8b07a", "#d98c8c", "#8cc8d9", "#d99c86", "#c6c9e8",
    "#f2c66b", "#8fa8b8", "#b8d98c", "#d98ca8", "#9cb8d9",
    "#e0a66b", "#86c6a0", "#d8a0c6", "#a8b8e0", "#e8b86b",
    "#93b8d8", "#c98c98", "#b8a0e0", "#d0c090", "#98d0b0",
    "#e8a8a8", "#9cd0d0",
]
COLOR_PASILLO = "#eadfc8"
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


def _render_png(t: dict, mision: dict | None, w: int, h: int, titulo: int, margen: int, celda: int, leyenda: int, ruta: Path) -> Path:
    img = Image.new("RGB", (w, h), "#f7f3ea")
    d = ImageDraw.Draw(img)
    nombre = t["nombre"] if not mision else f"{t['nombre']} · {mision['nombre']}"
    d.text((w // 2, 14), nombre, fill="#1a1a1a", font=_fuente(22), anchor="mm")
    ox, oy = margen, titulo + margen
    for y in range(1, t["filas"] + 1):
        for x in range(1, t["columnas"] + 1):
            num = tablero.sala_en(t, x, y)
            px, py = ox + (x - 1) * celda, oy + (y - 1) * celda
            d.rectangle([px, py, px + celda, py + celda], fill=_color_celda(num), outline="#000")
            if num is not None:
                d.text((px + celda / 2, py + celda / 2), str(num), fill="#333", font=_fuente(int(celda * 0.5)), anchor="mm")
    _muebles_png(img, mision, ox, oy, celda)
    _marcadores_png(img, mision, ox, oy, celda)
    _leyenda_png(d, mision, w, h, leyenda)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    img.save(ruta)
    return ruta


def _muebles_png(img: Image.Image, mision: dict | None, ox: int, oy: int, celda: int) -> None:
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
        # Borde amarillo si contiene tesoro del Reto
        if mu.get("tesoro"):
            d.rectangle([px, py, px + pwx, py + ph], outline=COLOR_TESORO, width=max(3, celda // 8))
        glifo = MUEBLE_GLIFO.get(mu.get("tipo", ""), "?")
        d.text((px + pwx / 2, py + ph / 2), glifo, fill=(60, 35, 10),
               font=_fuente(int(min(pwx, ph) * 0.7)), anchor="mm")


def _marcadores_png(img: Image.Image, mision: dict | None, ox: int, oy: int, celda: int) -> None:
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
                    d.rectangle([cx - tam / 2 - 2, cy - tam / 2 - 2,
                                 cx + tam / 2 + 2, cy + tam / 2 + 2],
                                outline=COLOR_TESORO, width=max(3, celda // 8))
                continue
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
            d.text((cx, cy), _inicial(punto, tipo), fill="#fff",
                   font=_fuente(int(r * 1.2)), anchor="mm")
        elif tipo == "tesoro":
            d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=color, outline="#000")
            d.text((cx, cy), _inicial(punto, tipo), fill="#000", font=_fuente(int(r)), anchor="mm")
        elif tipo in ("puerta", "puerta_secreta"):
            d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
            d.text((cx, cy), letra, fill="#fff", font=_fuente(int(r)), anchor="mm")
        elif tipo == "trampa":
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
            m = int(r * 0.7)
            d.line([(cx - m, cy - m), (cx + m, cy + m)], fill="#fff", width=2)
            d.line([(cx - m, cy + m), (cx + m, cy - m)], fill="#fff", width=2)
        elif tipo == "marcador":
            d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=color, outline="#000")
            d.text((cx, cy), "F", fill="#fff", font=_fuente(int(r)), anchor="mm")
        else:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline="#000")
            d.text((cx, cy), letra if tipo == "entrada" else _inicial(punto, tipo), fill="#fff",
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


def _leyenda_png(d: ImageDraw.ImageDraw, mision: dict | None, w: int, h: int, leyenda: int) -> None:
    if not mision:
        return
    y = h - leyenda + 18
    nombres = {"entrada": "Entrada", "puerta": "Puerta", "puerta_secreta": "Puerta secret.",
               "monstruo": "Monstruo", "tesoro": "Tesoro", "trampa": "Trampa", "marcador": "Ficha"}
    # Fila 1: marcadores
    x = 20
    for tipo, (letra, color) in MARCADORES.items():
        d.rectangle([x, y - 16, x + 16, y], fill=color, outline="#000")
        d.text((x + 8, y - 8), letra, fill="#fff", font=_fuente(11), anchor="mm")
        d.text((x + 24, y - 8), nombres[tipo], fill="#000", font=_fuente(13), anchor="lm")
        x += 24 + 108
    # Fila 2: mueble + tesoro del reto
    y2 = y + 22
    d.rounded_rectangle([20, y2 - 16, 36, y2], radius=3, fill="#b48c5a", outline=(90, 60, 30))
    d.text((44, y2 - 8), "Mueble", fill="#000", font=_fuente(13), anchor="lm")
    x = 44 + 90
    d.rectangle([x, y2 - 16, x + 16, y2], outline=COLOR_TESORO, width=3)
    d.text((x + 24, y2 - 8), "Tesoro del Reto", fill="#000", font=_fuente(13), anchor="lm")


def _leyenda_svg(partes: list[str], mision: dict | None, w: int, h: int, leyenda: int) -> None:
    if not mision:
        return
    y = h - leyenda + 18
    nombres = {"entrada": "Entrada", "puerta": "Puerta", "puerta_secreta": "Puerta secret.",
               "monstruo": "Monstruo", "tesoro": "Tesoro", "trampa": "Trampa", "marcador": "Ficha"}
    # Fila 1: marcadores
    x = 20
    for tipo, (letra, color) in MARCADORES.items():
        partes.append(f'<rect x="{x}" y="{y-16}" width="16" height="16" fill="{color}" stroke="#000"/>')
        partes.append(f'<text x="{x+8}" y="{y-8}" font-family="sans-serif" font-size="11" text-anchor="middle" fill="#fff" font-weight="bold">{letra}</text>')
        partes.append(f'<text x="{x+24}" y="{y-8}" font-family="sans-serif" font-size="13" fill="#000">{nombres[tipo]}</text>')
        x += 24 + 108
    # Fila 2: mueble + tesoro del reto
    y2 = y + 22
    partes.append(f'<rect x="20" y="{y2-16}" width="16" height="16" rx="3" fill="#b48c5a" stroke="#5a3c1e"/>')
    partes.append(f'<text x="44" y="{y2-8}" font-family="sans-serif" font-size="13" fill="#000">Mueble</text>')
    x = 44 + 90
    partes.append(f'<rect x="{x}" y="{y2-16}" width="16" height="16" fill="none" stroke="{COLOR_TESORO}" stroke-width="3"/>')
    partes.append(f'<text x="{x+24}" y="{y2-8}" font-family="sans-serif" font-size="13" fill="#000">Tesoro del Reto</text>')


def _render_svg(t: dict, mision: dict | None, w: int, h: int, titulo: int, margen: int, celda: int, leyenda: int) -> str:
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    nombre = t["nombre"] if not mision else f"{t['nombre']} · {mision['nombre']}"
    partes.append(f'<text x="{w/2}" y="{titulo-12}" font-family="sans-serif" font-size="20" font-weight="bold" text-anchor="middle">{nombre}</text>')
    ox, oy = margen, titulo + margen
    for y in range(1, t["filas"] + 1):
        for x in range(1, t["columnas"] + 1):
            num = tablero.sala_en(t, x, y)
            px, py = ox + (x - 1) * celda, oy + (y - 1) * celda
            partes.append(f'<rect x="{px}" y="{py}" width="{celda}" height="{celda}" fill="{_color_celda(num)}" stroke="#000" stroke-width="0.8"/>')
            if num is not None:
                partes.append(f'<text x="{px+celda/2}" y="{py+celda/2+6}" font-family="sans-serif" font-size="{int(celda*0.55)}" text-anchor="middle" fill="#333">{num}</text>')
    _muebles_svg(partes, mision, ox, oy, celda)
    _marcadores_svg(partes, mision, ox, oy, celda)
    _leyenda_svg(partes, mision, w, h, leyenda)
    partes.append("</svg>")
    return "\n".join(partes)


def _muebles_svg(partes: list[str], mision: dict | None, ox: int, oy: int, celda: int) -> None:
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
            partes.append(
                f'<rect x="{px - t}" y="{py - t}" width="{pwx + 2 * t}" height="{ph + 2 * t}" rx="7" '
                f'fill="none" stroke="{COLOR_TESORO}" stroke-width="{t}"/>'
            )
        glifo = MUEBLE_GLIFO.get(mu.get("tipo", ""), "?")
        cxm, cym = px + pwx / 2, py + ph / 2
        tam_txt = int(min(pwx, ph) * 0.6)
        partes.append(
            f'<text x="{cxm}" y="{cym + tam_txt / 3}" font-family="sans-serif" font-size="{tam_txt}" '
            f'font-weight="bold" text-anchor="middle" fill="#3c230a">{glifo}</text>'
        )


def _marcadores_svg(partes: list[str], mision: dict | None, ox: int, oy: int, celda: int) -> None:
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
                    partes.append(
                        f'<rect x="{x0 - t}" y="{y0 - t}" width="{tam + 2 * t}" height="{tam + 2 * t}" '
                        f'rx="4" fill="none" stroke="{COLOR_TESORO}" stroke-width="{t}"/>'
                    )
                continue
            partes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="#000"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#fff" font-weight="bold">{_inicial(punto, tipo)}</text>')
        elif tipo == "tesoro":
            partes.append(f'<polygon points="{cx},{cy-r} {cx+r},{cy} {cx},{cy+r} {cx-r},{cy}" fill="{color}" stroke="#000"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#000" font-weight="bold">{_inicial(punto, tipo)}</text>')
        elif tipo in ("puerta", "puerta_secreta"):
            partes.append(f'<rect x="{cx-r}" y="{cy-r}" width="{2*r}" height="{2*r}" fill="{color}" stroke="#000"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.9)}" text-anchor="middle" fill="#fff" font-weight="bold">{letra}</text>')
        elif tipo == "trampa":
            partes.append(f'<circle cx="{cx}" cy="{cy}" r="{int(r*0.9)}" fill="{color}" stroke="#000"/>')
            m = int(r * 0.7)
            for dx, dy in ((-1, -1), (1, 1)):
                partes.append(f'<line x1="{cx+dx*m}" y1="{cy+dy*m}" x2="{cx-dx*m}" y2="{cy-dy*m}" stroke="#fff" stroke-width="2"/>')
        elif tipo == "marcador":
            partes.append(f'<rect x="{cx-r}" y="{cy-r}" width="{2*r}" height="{2*r}" fill="{color}" stroke="#000" transform="rotate(45 {cx} {cy})"/>')
            partes.append(f'<text x="{cx}" y="{cy+4}" font-family="sans-serif" font-size="{int(r*0.8)}" text-anchor="middle" fill="#fff" font-weight="bold">F</text>')
        else:
            partes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="#000"/>')
            texto = letra if tipo == "entrada" else _inicial(punto, tipo)
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
    leyenda = 60 if mision else 30
    margen = titulo = 40
    w = margen * 2 + t["columnas"] * celda
    h = titulo + margen * 2 + t["filas"] * celda + leyenda

    if args.svg:
        ruta_svg = _nombre_archivo(args.tablero, mision, "svg")
        ruta_svg.parent.mkdir(parents=True, exist_ok=True)
        ruta_svg.write_text(_render_svg(t, mision, w, h, titulo, margen, celda, leyenda), encoding="utf-8")
        print(f"SVG: {ruta_svg}")

    ruta_png = Path(args.salida) if args.salida else _nombre_archivo(args.tablero, mision, "png")
    _render_png(t, mision, w, h, titulo, margen, celda, leyenda, ruta_png)
    print(f"PNG: {ruta_png}")


if __name__ == "__main__":
    main()
"""Genera un manual de reglas de HeroQuest en HTML autocontenido.

Vista de un solo archivo, lista para pantalla e impresión, con:
- portada e índice navegable por categorías
- tarjetas de cada mecánica (descripción, valores y detalle)
- render genérico de los valores (int, str, bool, list) con nombres legibles
- pie con la fuente de verdad (reglas V2 de HeroQuest.es)

Ejemplos:
    uv run juegos/heroquest/scripts/reglas_html.py
    uv run juegos/heroquest/scripts/reglas_html.py --salida /tmp/reglas.html
    uv run juegos/heroquest/scripts/reglas_html.py --categoria combate --salida /tmp/combate.html
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import data_store
import tablero

DATA_DIR = tablero.DATA_DIR
HTML_DIR = DATA_DIR.parent / "mapas"

# Correcciones ortográficas para palabras clave que pierden tildes en snake_case
_ACENTOS = {
    "Heroes": "Héroes", "Heroe": "Héroe", "Muerte": "Muerte",
    "Dados": "Dados", "Distancia": "Distancia", "Linea": "Línea",
    "Vision": "Visión", "Eleccion": "Elección", "Hechizos": "Hechizos",
    "Juego": "Juego", "Mágico": "Mágico", "Mágicos": "Mágicos",
    "Abismo": "Abismo", "Indice": "Índice", "Descripción": "Descripción",
    "Activacion": "Activación", "Desactivar": "Desactivar", "Pozo": "Pozo",
    "Piedra": "Piedra", "Escaleras": "Escaleras", "Resbaladizas": "Resbaladizas",
    "Gran": "Gran", "Bola": "Bola", "Corazas": "Corazas",
    "Armadura": "Armadura", "Casco": "Casco", "Yelmo": "Yelmo",
    "Hacha": "Hacha", "Cofres": "Cofres", "Cofre": "Cofre",
    "Mobiliario": "Mobiliario", "Tinieblas": "Tinieblas",
    "Cota": "Cota", "Malla": "Malla", "Coraza": "Coraza",
    "Buscar": "Buscar", "Tesoros": "Tesoros", "Monedas": "Monedas",
    "Oro": "Oro", "Tienda": "Tienda", "Equipo": "Equipo", "Batalla": "Batalla",
    "Reto": "Reto", "Retos": "Retos", "Misiones": "Misiones",
    "Preparacion": "Preparación", "Tablero": "Tablero", "Tableros": "Tableros",
    "Oracion": "Oración", "Oraculo": "Oráculo", "Bendicion": "Bendición",
    "Bendiciones": "Bendiciones", "Maldicion": "Maldición",
    "Pergamino": "Pergamino", "Destruir": "Destruir", "Simbolos": "Símbolos",
    "Cuerno": "Cuerno", "Forjados": "Forjados", "Esqueleto": "Esqueleto",
    "Mago": "Mago", "Elfo": "Elfo", "Enano": "Enano", "Barbaro": "Bárbaro",
    "Medio": "Medio", "Mediana": "Mediana", "Media": "Media",
    "Pesada": "Pesada", "Escudo": "Escudo", "Escudos": "Escudos",
    "Negro": "Negro", "Negros": "Negros", "Blanco": "Blanco",
    "Blancos": "Blancos", "Calavera": "Calavera", "Calaveras": "Calaveras",
    "Envenenamiento": "Envenenamiento", "Aturdir": "Aturdir",
    "Aturdimiento": "Aturdimiento", "Doble": "Doble", "Dobles": "Dobles",
    "Ataques": "Ataques", "Arrojadizas": "Arrojadizas", "Contundentes": "Contundentes",
    "Clasificacion": "Clasificación", "Cartas": "Cartas", "Personajes": "Personajes",
    "Turno": "Turno", "Turnos": "Turnos", "Movimiento": "Movimiento",
    "Amenazas": "Amenazas", "Intercambio": "Intercambio", "Objetos": "Objetos",
    "Con": "Con", "Kit": "Kit", "Herramientas": "Herramientas",
    "Saltar": "Saltar", "Trampa": "Trampa", "Trampas": "Trampas",
    "Sanacion": "Sanación", "Hogar": "Hogar", "Almacenamiento": "Almacenamiento",
    "Astuto": "Astuto", "Baul": "Baúl", "Partes": "Partes", "Monstruos": "Monstruos",
    "Grandes": "Grandes", "Comienzo": "Comienzo", "Final": "Final",
    "Escuelas": "Escuelas", "Elementales": "Elementales", "Coste": "Coste",
    "Mente": "Mente", "Estado": "Estado", "Shock": "Shock",
    "Psiquica": "Psíquica", "Monstruo": "Monstruo", "Terror": "Terror",
    "Sin": "Sin", "Armas": "Armas", "Jugadores": "Jugadores",
    "Componentes": "Componentes", "Preparacion": "Preparación",
}


def _humano(key: str) -> str:
    """Convierte una clave snake_case en un rótulo legible."""
    palabras = key.replace("-", "_").split("_")
    human = " ".join(p.capitalize() for p in palabras)
    for origen, corregida in _ACENTOS.items():
        human = human.replace(origen, corregida)
    return human


def _formatear_valor(dato):
    """Convierte un valor de la mecánica en HTML legible."""
    if isinstance(dato, bool):
        return '<span class="dato-val">Sí</span>' if dato else '<span class="dato-val">No</span>'
    if isinstance(dato, (int, float)):
        return f'<span class="dato-val num">{dato}</span>'
    if isinstance(dato, (list, tuple)):
        items = "".join(f"<li>{html.escape(str(x))}</li>" for x in dato)
        return f"<ul class='dato-lista'>{items}</ul>"
    if isinstance(dato, dict):
        items = "".join(
            f"<li><b>{html.escape(_humano(k))}:</b> {_formatear_valor(v)}</li>"
            for k, v in dato.items()
        )
        return f"<ul class='dato-lista'>{items}</ul>"
    return f'<span class="dato-val">{html.escape(str(dato))}</span>'


def _tarjeta_mecanica(nombre: str, mec: dict) -> str:
    """Render de una tarjeta de mecánica."""
    valores = mec.get("valores", {})
    detalle = mec.get("detalle", "")
    nota = mec.get("nota", "")
    norma_propia = mec.get("norma_propia", False)
    bloques = ""
    if valores:
        filas = ""
        for k, v in valores.items():
            filas += (
                f"<tr><th scope='row'>{html.escape(_humano(k))}</th>"
                f"<td>{_formatear_valor(v)}</td></tr>"
            )
        bloques += f"<table class='valores'><tbody>{filas}</tbody></table>"
    badge = '<span class="badge-casa">🏠 REGLA DE CASA</span>' if norma_propia else ""
    nota_html = f'<div class="nota">{html.escape(nota)}</div>' if nota else ""
    detalle_html = (
        f'<details class="detalle"><summary>Detalle</summary><p>{html.escape(detalle)}</p></details>'
        if detalle
        else ""
    )
    return f"""
    <article class="mecanica">
      <h3 class="mec-titulo">{html.escape(_humano(nombre))}{badge}</h3>
      <p class="mec-desc">{html.escape(mec.get("descripcion", ""))}</p>
      {nota_html}
      {bloques}
      {detalle_html}
    </article>"""


def _categoria(cat_id: str, nombre: str, cat: dict) -> str:
    """Render de una sección de categoría."""
    tarjetas = "".join(_tarjeta_mecanica(k, m) for k, m in cat.get("mecanicas", {}).items())
    return f"""
    <section class="categoria" id="cat-{cat_id}">
      <header class="cat-cab">
        <a class="cat-ancla" href="#top">↑</a>
        <h2>{html.escape(nombre)}</h2>
        <span class="cat-n">{len(cat.get('mecanicas', {}))} mecánicas</span>
      </header>
      <div class="mecanicas">{tarjetas}</div>
    </section>"""


def _grafico_dados() -> str:
    """Dados decorativos para la portada."""
    dado = lambda cara: (
        f"<div class='dado'><span>{cara}</span>"
        f"<i class='p1'></i><i class='p2'></i></div>"
    )
    return (
        f"<div class='dados'>{dado('💀')}{dado('🛡')}{dado('💀')}"
        f"{dado('🛡')}{dado('⚔')}{dado('💀')}</div>"
    )


def _render(reglas: dict) -> str:
    """Compone el HTML final."""
    version = reglas.get("version", "—")
    nota = reglas.get("nota", "")
    fuente = reglas.get("fuente_de_verdad", "")
    categorias = reglas.get("categorias", {})

    # Nombres humanos de categoría (si no hay, se genera desde el id)
    nombres = {
        "componentes_y_preparacion": "Componentes y preparación",
        "turnos_y_movimiento": "Turnos y movimiento",
        "combate": "Combate",
        "magia": "Magia",
        "trampas": "Trampas",
        "tesoros_y_tienda": "Tesoros y tienda",
        "misiones": "Misiones",
        "bendiciones_y_maldiciones": "Bendiciones y maldiciones",
    }
    for cid in categorias:
        if cid not in nombres:
            nombres[cid] = _humano(cid)

    cat_ids = list(categorias.keys())
    secciones = ""
    for cid in cat_ids:
        secciones += _categoria(cid, nombres[cid], categorias[cid])

    idx = "<nav class='indice'><ul>"
    for cid in cat_ids:
        idx += (
            f"<li><a href='#cat-{cid}'>{html.escape(nombres[cid])}"
            f"<span class='idx-n'>{len(categorias[cid].get('mecanicas', {}))}</span></a></li>"
        )
    idx += "</ul></nav>"

    total_mec = sum(len(c.get("mecanicas", {})) for c in categorias.values())

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reglas de HeroQuest · Manual de referencia</title>
<style>
  :root {{
    --papel:#f3ecdd; --tinta:#241a12; --bronce:#8a6d3b; --rojo:#9c2b2b;
    --madera:#5d4037; --claro:#fffdf7; --borde:#d8c9a8;
    --azul:#3b5b92; --verde:#2e7d32;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; padding:0; font-family:Georgia,'Times New Roman',serif;
    background:var(--papel); color:var(--tinta); line-height:1.5;
  }}
  .portada {{
    background:linear-gradient(145deg,#3a2620 0%,#5d4037 55%,#4a3630 100%);
    color:#f4e9d2; padding:38px 32px 28px; text-align:center;
    border-bottom:4px solid var(--bronce); box-shadow:0 3px 14px rgba(0,0,0,.35);
  }}
  .portada .kicker {{ letter-spacing:4px; font-size:.8rem; text-transform:uppercase; color:#c9a96a; }}
  .portada h1 {{ margin:8px 0 4px; font-size:2.6rem; letter-spacing:2px; }}
  .portada .sub {{ font-style:italic; color:#e8d9b8; margin:0 0 16px; }}
  .portada .meta {{ display:flex; justify-content:center; gap:26px; flex-wrap:wrap; font-size:.9rem; color:#e8d9b8; }}
  .portada .meta b {{ color:#fff; }}
  .dados {{ display:flex; justify-content:center; gap:10px; margin-top:18px; }}
  .dado {{
    width:44px; height:44px; background:#f4e9d2; border-radius:10px;
    display:flex; align-items:center; justify-content:center;
    font-size:1.25rem; position:relative; box-shadow:0 3px 8px rgba(0,0,0,.4);
    border:1px solid #c9a96a;
  }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:22px 18px 40px; }}
  .indice {{
    background:var(--claro); border:1px solid var(--borde); border-radius:12px;
    padding:14px 18px; margin:20px 0 26px; box-shadow:0 2px 8px rgba(0,0,0,.06);
  }}
  .indice::before {{ content:"Índice · categorías"; font-weight:bold; color:var(--bronce); text-transform:uppercase; letter-spacing:.5px; font-size:.85rem; display:block; margin-bottom:8px; }}
  .indice ul {{ list-style:none; margin:0; padding:0; display:flex; flex-wrap:wrap; gap:8px; }}
  .indice li a {{
    display:inline-flex; align-items:center; gap:8px;
    background:var(--papel); border:1px solid var(--borde); border-radius:20px;
    padding:5px 14px; color:var(--tinta); text-decoration:none; font-size:.92rem;
    transition:background .15s, color .15s;
  }}
  .indice li a:hover {{ background:var(--madera); color:#f4e9d2; }}
  .idx-n {{ background:var(--bronce); color:#fff; font-size:.72rem; border-radius:10px; padding:1px 8px; }}
  .categoria {{ margin-bottom:26px; scroll-margin-top:14px; }}
  .cat-cab {{
    display:flex; align-items:center; gap:12px;
    border-bottom:3px solid var(--bronce); padding-bottom:8px; margin-bottom:14px;
  }}
  .cat-cab h2 {{ margin:0; font-size:1.5rem; color:var(--madera); }}
  .cat-n {{ margin-left:auto; font-size:.8rem; color:var(--bronce); text-transform:uppercase; letter-spacing:.5px; }}
  .cat-ancla {{
    background:var(--madera); color:#f4e9d2; text-decoration:none; font-size:.85rem;
    width:28px; height:28px; display:flex; align-items:center; justify-content:center; border-radius:50%;
  }}
  .mecanicas {{
    display:grid; grid-template-columns:repeat(auto-fill,minmax(310px,1fr)); gap:14px;
  }}
  .mecanica {{
    background:var(--claro); border:1px solid var(--borde); border-radius:12px;
    padding:14px 16px; box-shadow:0 2px 6px rgba(0,0,0,.06); break-inside:avoid;
  }}
  .mec-titulo {{ margin:0 0 6px; font-size:1.05rem; color:var(--madera); display:flex; align-items:center; gap:8px; }}
  .mec-titulo::before {{
    content:"▸"; color:var(--bronce); font-size:.95rem;
  }}
  .mec-desc {{ margin:.2em 0 .7em; font-size:.94rem; }}
  .badge-casa {{
    display:inline-block; background:linear-gradient(135deg,#f4e3b8,#e8c868);
    color:#4a3a1e; font-size:.7rem; font-weight:700; padding:2px 8px;
    border-radius:10px; border:1px solid #c9a738; vertical-align:middle;
    margin-left:6px; letter-spacing:.3px;
    box-shadow:0 1px 3px rgba(138,109,59,.18);
  }}
  .valores {{
    width:100%; border-collapse:collapse; font-size:.88rem; margin:6px 0;
    background:#f9f4e8; border-radius:8px; overflow:hidden;
  }}
  .valores th {{
    text-align:left; padding:4px 10px; color:var(--bronce); font-weight:bold;
    border-bottom:1px solid var(--borde); white-space:nowrap; vertical-align:top;
    width:38%;
  }}
  .valores td {{ padding:4px 10px; border-bottom:1px solid var(--borde); }}
  .valores tr:last-child th, .valores tr:last-child td {{ border-bottom:none; }}
  .dato-val {{ font-weight:bold; }}
  .dato-val.num {{ color:var(--azul); }}
  .dato-lista {{ margin:2px 0; padding-left:18px; }}
  .dato-lista li {{ margin:1px 0; }}
  .nota {{
    margin:8px 0; padding:10px 12px;
    background:linear-gradient(135deg,#fbf3d9,#f4e3b8);
    border:1px solid #d9bc7a; border-left:5px solid var(--bronce);
    border-radius:8px; font-size:.9rem; color:#4a3a1e; line-height:1.45;
    box-shadow:0 1px 4px rgba(138,109,59,.18);
  }}
  .nota::before {{
    content:"•"; color:var(--bronce); font-weight:bold; margin-right:6px;
  }}
  .detalle {{ margin-top:8px; border-top:1px dashed var(--borde); padding-top:6px; }}
  .detalle summary {{ cursor:pointer; font-size:.85rem; color:var(--bronce); font-weight:bold; }}
  .detalle p {{ margin:.4em 0 0; font-size:.9rem; color:#4a3d2e; font-style:italic; }}
  .footer {{
    margin-top:30px; padding-top:14px; border-top:2px solid var(--bronce);
    font-size:.82rem; color:#6b5638;
  }}
  .footer b {{ color:var(--rojo); }}
  @media print {{
    body {{ background:#fff; }}
    .portada {{ box-shadow:none; }}
    .indice, .mecanica, .categoria {{ box-shadow:none; break-inside:avoid; }}
    .cat-ancla {{ display:none; }}
  }}
  @media (max-width:640px) {{
    .portada h1 {{ font-size:1.9rem; }}
    .mecanicas {{ grid-template-columns:1fr; }}
  }}
</style>
</head>
<body id="top">
  <header class="portada">
    <div class="kicker">HeroQuest · Manual de referencia</div>
    <h1>LAS REGLAS</h1>
    <p class="sub">Normas de juego, combate, magia, trampas y tesoros</p>
    <div class="meta">
      <span>Versión de datos: <b>{html.escape(str(version))}</b></span>
      <span>Mecánicas: <b>{total_mec}</b></span>
      <span>Categorías: <b>{len(categorias)}</b></span>
    </div>
    {_grafico_dados()}
  </header>

  <div class="wrap">
    {idx}

    {f'<p style="margin:-10px 0 20px; font-style:italic; color:#6b5638; font-size:.92rem;">{html.escape(nota)}</p>' if nota else ''}

    {secciones}

    <footer class="footer">
      <p><b>Fuente de verdad:</b> {html.escape(fuente or "Reglas de HeroQuest.es V2 (Remake, CC BY-NC-SA)")}.</p>
      <p>Complementada con las normas del pack de misión HeroQuest: El Despertar y el Reglamento original (1989) como referencia.</p>
    </footer>
  </div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el manual de reglas de HeroQuest en HTML")
    parser.add_argument("--categoria", default=None, help="Solo una categoría (id)")
    parser.add_argument("--salida", default=None, help="Ruta HTML de salida (por defecto en mapas/)")
    args = parser.parse_args()

    reglas = data_store.cargar_json("reglas")

    if args.categoria:
        # Modo: un solo archivo por categoría
        cat = reglas.get("categorias", {}).get(args.categoria)
        if not cat:
            print(f"Error: no existe la categoría '{args.categoria}'. Disponibles:{list(reglas.get('categorias', {}))}")
            raise SystemExit(1)
        reglas = {"version": reglas.get("version", "1.0"),
                  "fuente_de_verdad": reglas.get("fuente_de_verdad", ""),
                  "nota": f"Sección: {args.categoria}",
                  "categorias": {args.categoria: cat}}

    out = Path(args.salida) if args.salida else HTML_DIR / "reglas_de_heroquest.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render(reglas), encoding="utf-8")
    print(f"HTML: {out}")


if __name__ == "__main__":
    main()
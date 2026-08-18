"""Genera la ficha de máster de una misión en HTML.

Vista autocontenida (un solo archivo) optimizada para pantalla, con:
- datos de la misión (nivel, introducción, objetivo, recompensa)
- mapa de la misión (SVG embebido, reutiliza mapa.py)
- cada sala con sus monstruos (stats + casillas de vida) y tesoros
- referencia rápida: héroes, armas/equipo y hechizos

Ejemplos:
    uv run juegos/heroquest/scripts/mision_html.py --mision "El Refugio del Guardián"
    uv run juegos/heroquest/scripts/mision_html.py --mision "El Refugio del Guardián" --salida /tmp/mision.html
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import data_store
import mapa
import tablero

DATA_DIR = tablero.DATA_DIR
HTML_DIR = DATA_DIR.parent / "mapas"


def _cargar_mision(nombre: str) -> dict:
    for m in data_store.cargar("misiones"):
        if m["nombre"] == nombre:
            return m
    print(f"Error: no existe la misión '{nombre}'")
    sys.exit(1)


def _stats_monstruo(nombre: str) -> dict | None:
    for m in data_store.cargar("monstruos"):
        if m["nombre"] == nombre:
            return m
    return None


def _stat_tesoro(nombre: str) -> dict | None:
    for a in data_store.cargar("armas"):
        if a["nombre"] == nombre:
            return a
    return None


def _mapa_svg(mision: dict, t: dict) -> str:
    celda, leyenda, margen, titulo = 34, 60, 40, 40
    w = margen * 2 + t["columnas"] * celda
    h = titulo + margen * 2 + t["filas"] * celda + leyenda
    return mapa._render_svg(t, mision, w, h, titulo, margen, celda, leyenda)


def _casillas_vida(cuerpo: int) -> str:
    return " ".join(f'<label class="vida"><input type="checkbox" aria-label="Punto de cuerpo {i + 1}"></label>'
                    for i in range(max(cuerpo, 1)))


def _ficha_monstruo(m: dict | None, nombre: str) -> str:
    if not m:
        return (
            f'<div class="card monstruo"><div class="mtitulo">{html.escape(nombre)}</div>'
            f'<div class="monotenue">Sin stats registradas</div></div>'
        )
    return f"""
    <div class="card monstruo">
      <div class="mtitulo">{html.escape(m["nombre"])}
        <span class="stats">A{m["ataque"]} D{m["defensa"]} Cu{m["cuerpo"]} Me{m["mente"]} Mov{m["movimiento"]}</span>
      </div>
      <details open>
        <summary>Vida</summary>
        <div class="vidas">{_casillas_vida(m["cuerpo"])}</div>
      </details>
    </div>"""


def _ficha_tesoro(t: dict | None, nombre: str) -> str:
    if not t:
        return f'<span class="tesoro">{html.escape(nombre)}</span>'
    extras = ""
    if t.get("tipo"):
        extras += f' {html.escape(t["tipo"])}'
    if t.get("ataque") or t.get("defensa"):
        extras += f' · A{t["ataque"]} D{t["defensa"]}'
    if t.get("coste") is not None:
        extras += f' · {t["coste"]} monedas'
    return f'<span class="tesoro">{html.escape(nombre)}{extras}</span>'


def _tabla_referencia(registros: list[dict], columnas: tuple[str, ...]) -> str:
    filas = []
    for r in registros:
        celdas = "".join(f"<td>{cell}</td>" for cell in columnas)
        filas.append(f"<tr>{celdas}</tr>")
    return (
        "<div class='tabla-wrap'><table><thead><tr>"
        + "".join(f"<th>{c}</th>" for c in columnas)
        + "</tr></thead><tbody>"
        + "".join(filas)
        + "</tbody></table></div>"
    )


def _referencia() -> str:
    secciones = []

    personajes = data_store.cargar("personajes")
    filas_p = "".join(
        f'<tr><td>{html.escape(p["nombre"])}</td><td>{html.escape(p["clase"])}</td>'
        f'<td>A{p["ataque"]}</td><td>D{p["defensa"]}</td><td>Cu{p["cuerpo"]}</td>'
        f'<td>Me{p["mente"]}</td><td>{p["movimiento"]}</td></tr>'
        for p in personajes
    )
    secciones.append(f"""
    <section class="panel">
      <h3>Héroes</h3>
      <div class="tabla-wrap"><table>
        <thead><tr><th>Nombre</th><th>Clase</th><th>Ataque</th><th>Defensa</th><th>Cuerpo</th><th>Mente</th><th>Mov</th></tr></thead>
        <tbody>{filas_p}</tbody>
      </table></div>
    </section>""")

    armas = data_store.cargar("armas")
    filas_a = "".join(
        f'<tr><td>{html.escape(a["nombre"])}</td><td>{html.escape(a["tipo"])}</td>'
        f'<td>{"A" + str(a["ataque"]) if a.get("ataque") else "—"}</td>'
        f'<td>{"D" + str(a["defensa"]) if a.get("defensa") else "—"}</td>'
        f'<td>{a["coste"]}</td></tr>'
        for a in armas
    )
    secciones.append(f"""
    <section class="panel">
      <h3>Armas y equipo</h3>
      <div class="tabla-wrap"><table>
        <thead><tr><th>Nombre</th><th>Tipo</th><th>Ataque</th><th>Defensa</th><th>Coste</th></tr></thead>
        <tbody>{filas_a}</tbody>
      </table></div>
    </section>""")

    hechizos = data_store.cargar("hechizos")
    if hechizos:
        filas_h = "".join(
            f'<tr><td>{html.escape(h["nombre"])}</td><td>{html.escape(h["escuela"])}</td>'
            f'<td>{h["coste_mente"]}</td><td>{html.escape(h["descripcion"])}</td></tr>'
            for h in hechizos
        )
        secciones.append(f"""
        <section class="panel">
          <h3>Hechizos</h3>
          <div class="tabla-wrap"><table>
            <thead><tr><th>Nombre</th><th>Escuela</th><th>Coste mente</th><th>Efecto</th></tr></thead>
            <tbody>{filas_h}</tbody>
          </table></div>
        </section>""")

    return "\n".join(secciones)


def _render(mision: dict, t: dict) -> str:
    titulo = html.escape(mision["nombre"])
    tablero_data = data_store.cargar_json("tableros")
    tablero_nombre = next((tb["nombre"] for tb in tablero_data if tb["id"] == t["id"]), t["id"])

    salas_html = []
    for sala in mision.get("salas", []):
        monstruos = sala.get("monstruos", [])
        tesoros = sala.get("tesoros", [])
        mons = "".join(
            f'<div class="col">{_ficha_monstruo(_stats_monstruo(m["nombre"]), m["nombre"])}</div>'
            for m in monstruos
        )
        tes = "".join(f'<li>{_ficha_tesoro(_stat_tesoro(x["nombre"]), x["nombre"])}</li>' for x in tesoros)
        salas_html.append(f"""
        <section class="sala">
          <header class="salacab">
            <span class="salnum">Sala {sala["numero"]}</span>
            <span class="salanom">{html.escape(sala["nombre"])}</span>
          </header>
          <p class="saladesc">{html.escape(sala.get("descripcion", ""))}</p>
          <div class="grid">{mons}</div>
          <ul class="tesoros">{tes}</ul>
        </section>""")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo} · Ficha de máster</title>
<style>
  :root {{
    --papel:#f3ecdd; --tinta:#241a12; --bronce:#8a6d3b; --rojo:#9c2b2b;
    --madera:#5d4037; --claro:#fffdf7; --borde:#d8c9a8; --verde:#2e7d32;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; padding:24px; font-family:Georgia,'Times New Roman',serif;
    background:var(--papel); color:var(--tinta); line-height:1.45;
  }}
  .portada {{
    background:linear-gradient(135deg,#3a2620,#5d4037); color:#f4e9d2;
    padding:22px 28px; border-radius:12px; margin-bottom:22px; box-shadow:0 3px 10px rgba(0,0,0,.25);
  }}
  .portada h1 {{ margin:0 0 6px; font-size:1.7rem; }}
  .meta {{ display:flex; gap:16px; flex-wrap:wrap; font-size:.95rem; color:#e8d9b8; }}
  .meta b {{ color:#fff; }}
  .datos {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; margin-bottom:22px; }}
  .dato {{ background:var(--claro); border:1px solid var(--borde); border-radius:10px; padding:14px 16px; }}
  .dato h2 {{ font-size:1rem; margin:0 0 6px; color:var(--bronce); text-transform:uppercase; letter-spacing:.5px; }}
  .dato p {{ margin:0; }}
  .mapa-wrap {{
    background:var(--claro); border:1px solid var(--borde); border-radius:12px;
    padding:16px; overflow:auto; margin-bottom:22px;
  }}
  .mapa-wrap h2 {{ margin:0 0 10px; font-size:1.1rem; color:var(--bronce); }}
  .mapa-wrap svg {{ display:block; margin:0 auto; max-width:100%; height:auto; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:10px; }}
  .salas {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:16px; }}
  .sala {{ background:var(--claro); border:1px solid var(--borde); border-radius:12px; padding:14px 16px; box-shadow:0 2px 6px rgba(0,0,0,.06); }}
  .salacab {{ display:flex; align-items:baseline; gap:10px; border-bottom:2px solid var(--bronce); padding-bottom:6px; margin-bottom:8px; }}
  .salnum {{ background:var(--madera); color:#f4e9d2; font-weight:bold; border-radius:6px; padding:2px 8px; font-size:.9rem; }}
  .salanom {{ font-size:1.15rem; font-weight:bold; color:var(--tinta); }}
  .saladesc {{ font-style:italic; color:#5a4a38; margin:.2em 0 .8em; }}
  .card {{ background:#fbf6ea; border:1px solid var(--borde); border-radius:8px; padding:10px; }}
  .monstruo .mtitulo {{ font-weight:bold; }}
  .monstruo .stats {{ display:block; font-weight:normal; font-size:.85rem; color:var(--bronce); margin-top:2px; }}
  .vidas {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }}
  .vida input {{ width:20px; height:20px; accent-color:var(--verde); cursor:pointer; }}
  .tesoros {{ margin:.6em 0 0; padding-left:1.1em; }}
  .tesoros li {{ margin-bottom:2px; }}
  .tesoro {{ background:#eaf3ea; border:1px solid #bcd8bc; border-radius:5px; padding:1px 7px; font-size:.9rem; }}
  .panel {{ background:var(--claro); border:1px solid var(--borde); border-radius:12px; padding:14px 18px; margin-bottom:16px; }}
  .panel h3 {{ margin:0 0 8px; font-size:1.05rem; color:var(--bronce); text-transform:uppercase; letter-spacing:.5px; }}
  .tabla-wrap {{ overflow:auto; }}
  table {{ border-collapse:collapse; width:100%; font-size:.92rem; }}
  th, td {{ border:1px solid var(--borde); padding:5px 9px; text-align:left; }}
  th {{ background:#efe3c8; }}
  details summary {{ cursor:pointer; font-size:.88rem; color:var(--bronce); }}
  .monotenue {{ color:#999; font-style:italic; }}
  @media print {{
    body {{ background:#fff; }}
    .portada, .sala, .panel, .mapa-wrap {{ box-shadow:none; }}
  }}
</style>
</head>
<body>
  <header class="portada">
    <h1>{titulo}</h1>
    <div class="meta">
      <span>Tablero: <b>{html.escape(tablero_nombre)}</b></span>
      <span>Nivel: <b>{mision.get("nivel", "—")}</b></span>
    </div>
  </header>

  <div class="datos">
    <div class="dato"><h2>Introducción</h2><p>{html.escape(mision.get("introduccion", ""))}</p></div>
    <div class="dato"><h2>Objetivo</h2><p>{html.escape(mision.get("objetivo", ""))}</p></div>
    <div class="dato"><h2>Recompensa</h2><p>{html.escape(mision.get("recompensa", ""))}</p></div>
  </div>

  <div class="mapa-wrap">
    <h2>Mapa de la misión</h2>
    {_mapa_svg(mision, t)}
  </div>

  <div class="salas">
    {''.join(salas_html)}
  </div>

  <h2 style="color:var(--bronce); margin-bottom:10px;">Referencia del máster</h2>
  {_referencia()}
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera la ficha de máster de una misión en HTML")
    parser.add_argument("--mision", required=True, help="Nombre de la misión")
    parser.add_argument("--salida", default=None, help="Ruta HTML de salida (por defecto en mapas/)")
    args = parser.parse_args()

    mision = _cargar_mision(args.mision)
    t = tablero.cargar_tablero(mision["tablero"])
    if not t["salas"]:
        print(f"Error: el tablero '{t['id']}' aún no está modelado ({t.get('nota', '')})")
        sys.exit(1)

    ruta = Path(args.salida) if args.salida else HTML_DIR / f"mision__{data_store.slug(mision['nombre'])}.html"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(_render(mision, t), encoding="utf-8")
    print(f"HTML: {ruta}")


if __name__ == "__main__":
    main()
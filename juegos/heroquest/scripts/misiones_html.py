"""Genera el HTML 'padre' (índice) de misiones de HeroQuest.

El hub lista todas las misiones de `misiones.json` agrupadas por campaña
(campo opcional `campana`; por defecto "El Despertar"), enlaza cada ficha
de misión generada con `mision_html.py` y muestra la hoja de ruta de El
Despertar (las misiones del libreto escaneado aún no modeladas).

Ejemplos:
    uv run juegos/heroquest/scripts/misiones_html.py
    uv run juegos/heroquest/scripts/misiones_html.py --salida /tmp/index.html
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import data_store
import tablero

DATA_DIR = tablero.DATA_DIR
HTML_DIR = DATA_DIR.parent / "html"

CAMPAÑA_DEFECTO = "El Despertar"

# El Despertar: las misiones del libreto oficial en orden, con un resumen
# corto del objetivo. Las que ya están en misiones.json se renderizan desde
# sus datos; el resto aparecen como pendientes en la hoja de ruta.
EL_DESPERTAR = [
    ("La Fortaleza Fronteriza de In-Gulden",
     "Penetrar en la fortaleza asolada, inspeccionar a los exploradores "
     "caídos y acabar con el Capitán del Terror Sha-Del."),
    ("El Brujo de Tuel-Vor",
     "Cruzar los Portales del Terror en el retiro del brujo y desvelar los "
     "primeros pasos de su Sincroforma."),
    ("El Oráculo de Morledis",
     "Liberar al Alto Sacerdote capturado y recuperar \"Las Visiones del Rey "
     "Agrain\" para el Príncipe Magnus."),
    ("La Fortaleza del Rey del Fuego",
     "Hallar en las ruinas enanas el Pasadizo Secreto de la montaña y el "
     "Mapa de Glordrin, mientras la Reina Kessandria acecha."),
    ("Los Horrores de la Sideroforima",
     "Investigar las celdas de los experimentos de Qwindrak y deshacer sus "
     "criaturas antes de alcanzar su altar."),
    ("El Anillo de Retorno",
     "Encontrar el Anillo de Retorno en la sala del trono del brujo en plena "
     "batalla con los Guerreros del Terror."),
    ("La Tumba del Rey del Fuego",
     "Invocar con el anillo el espíritu del Rey Forgrin en su tumba y "
     "recuperar el Cuerno de los Forjados."),
    ("Los Tesoros del Rey Forgrin",
     "Rescatar los legendarios Tesoros de las Minas del Rey Forgrin y "
     "resolver el acertijo de la Enciclopedia de Galik."),
    ("El Sonido del Cuerno de los Forjados",
     "Atravesar los cinco Salones de la Ordalía y derrotar al general "
     "Abraxus en Los Salones con el Cuerno de los Forjados."),
    ("El Poder de la Sideroforima",
     "Batalla final contra Qwindrak en todas sus formas y testigos del "
     "despertar de Alousen, la última Vidente de Escamas."),
]


def _mision_html_existe(slug: str) -> bool:
    return (HTML_DIR / f"mision__{slug}.html").exists()


def _resumen_mision(mision: dict) -> str:
    partes = []
    n_salas = len(mision.get("salas", []))
    n_monstruos = sum(len(s.get("monstruos", [])) for s in mision.get("salas", []))
    n_monstruos += len(mision.get("pasillos", {}).get("monstruos", []))
    n_tesoros = sum(len(s.get("tesoros", [])) for s in mision.get("salas", []))
    if n_salas:
        partes.append(f"{n_salas} sala{'s' if n_salas != 1 else ''}")
    if n_monstruos:
        partes.append(f"{n_monstruos} monstruo{'s' if n_monstruos != 1 else ''}")
    if n_tesoros:
        partes.append(f"{n_tesoros} tesoro{'s' if n_tesoros != 1 else ''}")
    return " · ".join(partes) or "Sin salas modeladas"


def _tarjeta_mision(mision: dict, camino: Path | None, descripcion: str | None = None) -> str:
    nombre = html.escape(mision["nombre"])
    nivel = mision.get("nivel")
    tablero_nombre = mision.get("tablero", "")
    objetivo = html.escape(descripcion or mision.get("objetivo", ""))
    extra = html.escape(_resumen_mision(mision))
    meta = f"<span>Tablero: <b>{html.escape(tablero_nombre)}</b></span>"
    if nivel:
        meta += f"<span>Nivel: <b>{nivel}</b></span>"
    recompensa = mision.get("recompensa")
    recompensa_html = (
        f'<div class="reco"><b>Recompensa</b>{html.escape(recompensa)}</div>'
        if recompensa else ""
    )
    if camino:
        cuerpo = f"""
        <a class="tarjeta" href="{camino}">
          <h3>{nombre}</h3>
          <div class="meta">{meta}</div>
          <p>{objetivo}</p>
          <div class="pie"><span class="etiqueta">{extra}</span>
            <span class="estado listo">Ficha del máster →</span></div>
          {recompensa_html}
        </a>"""
    else:
        cuerpo = f"""
        <div class="tarjeta pendiente">
          <h3>{nombre}</h3>
          <div class="meta">{meta}</div>
          <p>{objetivo}</p>
          <div class="pie"><span class="etiqueta">{extra}</span>
            <span class="estado falta">Pendiente de modelar</span></div>
          {recompensa_html}
        </div>"""
    return f'<div class="col">{cuerpo}</div>'


def _seccion(campana: str, misiones: list[tuple[dict | None, dict | None]]) -> str:
    tarjetas = []
    for mision, pendiente in misiones:
        if mision is None:
            # Hoja de ruta: misión del libreto aún sin modelar
            nombre, objetivo = pendiente  # type: ignore[misc]
            tarjetas.append(
                f'<div class="col"><div class="tarjeta pendiente">'
                f'<h3>{html.escape(nombre)}</h3><div class="meta">'
                f'<span class="zdg">Libreto · sin datos</span></div>'
                f'<p>{html.escape(objetivo)}</p><div class="pie">'
                f'<span class="estado falta">Pendiente de modelar</span></div>'
                f'</div></div>'
            )
            continue
        nombre = mision["nombre"]
        slug = data_store.slug(nombre)
        camino = Path(f"mision__{slug}.html") if _mision_html_existe(slug) else None
        tarjetas.append(_tarjeta_mision(mision, camino))

    return f"""
    <section class="campana">
      <h2>{html.escape(campana)}</h2>
      <div class="grid">{''.join(tarjetas)}</div>
    </section>"""


def _render() -> str:
    misiones = data_store.cargar("misiones")

    # Agrupamiento por campaña, conservando el orden de aparición
    orden: list[str] = []
    por_campana: dict[str, list[dict]] = {}
    for m in misiones:
        campana = m.get("campana") or CAMPAÑA_DEFECTO
        if campana not in por_campana:
            por_campana[campana] = []
            orden.append(campana)
        por_campana[campana].append(m)

    if CAMPAÑA_DEFECTO not in por_campana:
        por_campana[CAMPAÑA_DEFECTO] = []
        orden.insert(0, CAMPAÑA_DEFECTO)

    # Hoja de ruta de El Despertar: en orden, completadas o pendientes
    nombres_libreto = {nombre for nombre, _ in EL_DESPERTAR}

    secciones = []
    for campana in orden:
        if campana == CAMPAÑA_DEFECTO:
            entradas: list[tuple[dict | None, dict | None]] = []
            for nombre, objetivo in EL_DESPERTAR:
                mision = next((m for m in por_campana[campana] if m["nombre"] == nombre), None)
                entradas.append((mision, None if mision else (nombre, objetivo)))
            for m in por_campana[campana]:
                if m["nombre"] in nombres_libreto:
                    continue
                # Misiones de la campaña fuera del libreto (e.j. tutoriales)
                entradas.append((m, None))
        else:
            entradas = [(m, None) for m in por_campana[campana]]
        secciones.append(_seccion(campana, entradas))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HeroQuest · Misiones</title>
<style>
  :root {{
    --papel:#f3ecdd; --tinta:#241a12; --bronce:#8a6d3b; --rojo:#9c2b2b;
    --madera:#5d4037; --claro:#fffdf7; --borde:#d8c9a8; --verde:#2e7d32;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; padding:24px; font-family:Georgia,'Times New Roman',serif;
    background:var(--papel); color:var(--tinta); line-height:1.5;
  }}
  .portada {{
    background:linear-gradient(135deg,#3a2620,#5d4037); color:#f4e9d2;
    padding:26px 30px; border-radius:12px; margin-bottom:22px;
    box-shadow:0 3px 10px rgba(0,0,0,.25);
  }}
  .portada h1 {{ margin:0 0 8px; font-size:1.9rem; }}
  .portada p {{ margin:0; color:#e8d9b8; max-width:72ch; }}
  .campana {{ margin-bottom:26px; }}
  .campana h2 {{
    font-size:1.15rem; color:var(--madera); text-transform:uppercase;
    letter-spacing:.6px; border-bottom:2px solid var(--bronce);
    padding-bottom:6px; margin:0 0 12px;
  }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }}
  .tarjeta {{
    display:flex; flex-direction:column; gap:8px; text-decoration:none;
    background:var(--claro); border:1px solid var(--borde); border-radius:12px;
    padding:14px 16px; min-height:100%; color:var(--tinta);
    box-shadow:0 2px 6px rgba(0,0,0,.06);
  }}
  a.tarjeta:hover {{ border-color:var(--bronce); box-shadow:0 4px 12px rgba(0,0,0,.12); }}
  .tarjeta h3 {{ margin:0; font-size:1.12rem; color:var(--madera); }}
  .tarjeta p {{ margin:0 0 auto; font-size:.95rem; color:#4a3a28; }}
  .meta {{ display:flex; gap:12px; flex-wrap:wrap; font-size:.85rem; color:#7a6a50; }}
  .meta b {{ color:var(--tinta); }}
  .pie {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:8px; }}
  .etiqueta {{ color:var(--bronce); font-size:.82rem; }}
  .estado {{
    font-size:.78rem; font-weight:bold; padding:3px 9px; border-radius:12px;
    white-space:nowrap;
  }}
  .estado.listo {{ background:#e6f1e6; color:var(--verde); border:1px solid #bcd8bc; }}
  .estado.falta {{ background:#f5e6e6; color:var(--rojo); border:1px solid #e0c0c0; }}
  .reco {{ margin-top:6px; border-top:1px dashed var(--borde); padding-top:6px; font-size:.85rem; color:#5a4a38; }}
  .reco b {{ display:block; font-size:.75rem; color:#9c6b00; text-transform:uppercase; letter-spacing:.4px; }}
  .zdg {{ font-style:italic; color:#9a8570; }}
  .nota {{
    background:var(--claro); border:1px dashed var(--borde); border-radius:10px;
    padding:12px 16px; font-size:.9rem; color:#5a4a38; margin-top:20px;
  }}
  @media print {{
    body {{ background:#fff; }}
    .portada, .tarjeta {{ box-shadow:none; }}
    a.tarjeta {{ color:var(--tinta); }}
  }}
</style>
</head>
<body>
  <header class="portada">
    <h1>HeroQuest · Misiones</h1>
    <p>Índice de misiones por campaña. Qwindrak, la Reina Kessandria y la
    Sincroforma aguardan en El Despertar; el propio libreto puede crecer con
    otras campañas, como las misiones originales de Las Mazmorras de Morcar.</p>
  </header>

  {''.join(secciones)}

  <div class="nota">
    <b>Cómo crece este índice:</b> cada ficha de misión se genera con
    <code>mision_html.py --mision "Nombre"</code> y el hub se regenera con
    <code>misiones_html.py</code>. Para agrupar misiones de otra campaña,
    añade a la misión el campo opcional <code>"campana": "Nombre"</code> en
    <code>data/misiones.json</code>. Las misiones del libreto escaneado que
    aún no tienen datos aparecen marcadas como pendientes en la hoja de ruta.
  </div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el índice (hub) de misiones de HeroQuest")
    parser.add_argument("--salida", default=None, help="Ruta HTML de salida (por defecto en html/)")
    args = parser.parse_args()

    ruta = Path(args.salida) if args.salida else HTML_DIR / "index.html"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(_render(), encoding="utf-8")
    print(f"HTML: {ruta}")


if __name__ == "__main__":
    main()
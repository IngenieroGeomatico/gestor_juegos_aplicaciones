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
HTML_DIR = DATA_DIR.parent / "html"


def _sprite_data_uri(slug: str, angulo: int = 0) -> str:
    """Data URI base64 del icono de mapa `slug` YA rotado a `angulo` grados.

    Usa exactamente el mismo procedimiento que el render inicial del SVG
    (`_icono_orientado_peq`), de modo que al conmutar el estado en el toggle
    la orientación y el recorte quedan idénticos a la puerta original."""
    ruta = mapa._icono_mapa(slug)
    if not ruta:
        return ""
    return mapa._icono_orientado_peq(ruta, angulo % 360, 180)


def _angulos_puertas(mision: dict) -> set[int]:
    """Ángulos de giro de las puertas normales de la misión (0/90/…).

    Replica la lógica de `mapa._marcadores_svg` para incrustar en el toggle
    los sprites pre-rotados que coinciden con el render inicial."""
    angulos: set[int] = set()
    slug = mapa.PUERTA_ICONO or mapa.PUERTA_ABIERTA_ICONO
    ruta_icono = mapa._icono_mapa(slug)
    r = 1.0  # la proporción del rect no depende del tamaño de celda
    for punto in mision.get("puertas", []):
        if "de" not in punto or "a" not in punto:
            continue
        x1, y1, x2, y2 = mapa._rect_puerta(punto, 0, 0, r, 34)  # misma celda que _mapa_svg
        angulos.add(mapa._gira_sprite(punto, ruta_icono, x2 - x1, y2 - y1))
    return angulos or {0}


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
    for fichero in ("equipo", "tesoros", "artefactos", "hechizos"):
        for a in data_store.cargar(fichero):
            if a["nombre"] == nombre:
                return a
    return None


def _mapa_svg(mision: dict, t: dict, mostrar: str = "salas", sufijo_id: str = "") -> str:
    celda, margen, titulo = 34, 40, 40
    w = margen * 2 + t["columnas"] * celda
    h = titulo + margen * 2 + t["filas"] * celda
    return mapa._render_svg(t, mision, w, h, titulo, margen, celda,
                            mostrar=mostrar, sufijo_id=sufijo_id)


def _lanzador_dados() -> str:
    """Lanzador de dados de combate HeroQuest (ataque rojo / defensa blanco).

    La probabilidad real del HeroQuest: el dado de ataque tiene 3 calaveras,
    1 escudo blanco y 2 escudos negros; el de defensa, 3 escudos blancos,
    1 escudo negro y 2 calaveras. El cuadro contabiliza calaveras en ataque y
    escudos blancos en defensa (los escudos negros no cuentan).
    """
    return """
    <div class="lanzador-dados">
      <h4>Lanzador de dados</h4>
      <div class="banco-dados">
        <div class="grupo">
          <div class="control">
            <span class="etiqueta etq-ataque">Ataque</span>
            <button type="button" onclick="cambiar('ataque',-1)" title="Menos dados">&minus;</button>
            <span id="num-ataque" class="cantidad">4</span>
            <button type="button" onclick="cambiar('ataque',1)" title="Más dados">+</button>
            <button type="button" class="lanzar" onclick="lanzar('ataque')">Lanzar</button>
          </div>
          <div id="res-ataque" class="resultado"></div>
          <div id="total-ataque" class="total"></div>
        </div>
        <div class="grupo">
          <div class="control">
            <span class="etiqueta etq-defensa">Defensa</span>
            <button type="button" onclick="cambiar('defensa',-1)" title="Menos dados">&minus;</button>
            <span id="num-defensa" class="cantidad">2</span>
            <button type="button" onclick="cambiar('defensa',1)" title="Más dados">+</button>
            <button type="button" class="lanzar" onclick="lanzar('defensa')">Lanzar</button>
          </div>
          <div id="res-defensa" class="resultado"></div>
          <div id="total-defensa" class="total"></div>
        </div>
      </div>
    </div>"""


# Caretas SVG de los dados de combate (48x48). La calavera clara se usa en el
# dado de ataque (rojo) y la oscura en el de defensa (blanco).
_DADO_CALAVERA_CLARA = (
    '<svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">'
    '<path fill="#fdf6e3" d="M24 9c-6.4 0-11.5 5-11.5 11.1 0 3.4 1.5 6.4 3.9 8.6.7.6 1.1 1.5 '
    '1.1 2.4v3.1c0 1.2 1 2.2 2.2 2.2h8.6c1.2 0 2.2-1 2.2-2.2v-3.1c0-.9.4-1.8 1.1-2.4 '
    '2.4-2.2 3.9-5.2 3.9-8.6C35.5 14 30.4 9 24 9z"/>'
    '<circle cx="19.2" cy="20.2" r="2.5" fill="#c0392b"/>'
    '<circle cx="28.8" cy="20.2" r="2.5" fill="#c0392b"/>'
    '<path d="M22.9 26.5h2.2L24 30l-1.1-3.5z" fill="#c0392b"/></svg>'
)
_DADO_CALAVERA_OSCURA = (
    '<svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">'
    '<path fill="#3a3024" d="M24 9c-6.4 0-11.5 5-11.5 11.1 0 3.4 1.5 6.4 3.9 8.6.7.6 1.1 1.5 '
    '1.1 2.4v3.1c0 1.2 1 2.2 2.2 2.2h8.6c1.2 0 2.2-1 2.2-2.2v-3.1c0-.9.4-1.8 1.1-2.4 '
    '2.4-2.2 3.9-5.2 3.9-8.6C35.5 14 30.4 9 24 9z"/>'
    '<circle cx="19.2" cy="20.2" r="2.5" fill="#f1e7d2"/>'
    '<circle cx="28.8" cy="20.2" r="2.5" fill="#f1e7d2"/>'
    '<path d="M22.9 26.5h2.2L24 30l-1.1-3.5z" fill="#f1e7d2"/></svg>'
)
_DADO_ESCUDO_BLANCO = (
    '<svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">'
    '<path fill="#fdf6e3" stroke="#b7a583" stroke-width="1.6" '
    'd="M24 5.6 10 12v13.4c0 9.4 6.2 16.2 14 17.6 7.8-1.4 14-8.2 14-17.6V12Z"/></svg>'
)
_DADO_ESCUDO_NEGRO = (
    '<svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">'
    '<path fill="#2f2a24" stroke="#1d1813" stroke-width="1.6" '
    'd="M24 5.6 10 12v13.4c0 9.4 6.2 16.2 14 17.6 7.8-1.4 14-8.2 14-17.6V12Z"/></svg>'
)


def _js_dados() -> str:
    """JavaScript del lanzador de dados (dados de combate HeroQuest).

    Se construye con concatenación y json.dumps para no chocar con las llaves
    del f-string del HTML. Sale como cadena plana dentro del IIFE de la página.
    """
    import json

    caras = {
        "ataque": {
            "calavera": _DADO_CALAVERA_CLARA,
            "escudo-blanco": _DADO_ESCUDO_BLANCO,
            "escudo-negro": _DADO_ESCUDO_NEGRO,
        },
        "defensa": {
            "calavera": _DADO_CALAVERA_OSCURA,
            "escudo-blanco": _DADO_ESCUDO_BLANCO,
            "escudo-negro": _DADO_ESCUDO_NEGRO,
        },
    }
    return (
        "/* ── Lanzador de dados ── */\n"
        "var CARAS = " + json.dumps(caras) + ";\n"
        "var CARAS_LISTA = {"
        "'ataque': ['calavera','calavera','calavera','escudo-blanco','escudo-negro','escudo-negro'],"
        "'defensa': ['escudo-blanco','escudo-blanco','escudo-blanco','escudo-negro','calavera','calavera']};\n"
        "function cambiar(tipo, delta) {\n"
        "  var spa = document.getElementById('num-' + tipo);\n"
        "  var n = Math.min(8, Math.max(1, parseInt(spa.textContent, 10) + delta));\n"
        "  spa.textContent = n;\n"
        "  pintarPendiente(tipo);\n"
        "}\n"
        "function pintarPendiente(tipo) {\n"
        "  var n = parseInt(document.getElementById('num-' + tipo).textContent, 10);\n"
        "  var res = document.getElementById('res-' + tipo);\n"
        "  var cont = [];\n"
        "  for (var i = 0; i < n; i++) {\n"
        "    cont.push('<span class=\"dado dado-' + tipo + ' pendiente\"></span>');\n"
        "  }\n"
        "  res.innerHTML = cont.join('');\n"
        "  avisar(tipo);\n"
        "}\n"
        "function avisar(tipo) {\n"
        "  document.getElementById('res-' + tipo).closest('.grupo').classList.add('aviso');\n"
        "  var tt = document.getElementById('total-' + tipo);\n"
        "  tt.textContent = 'Lanza la tirada';\n"
        "  tt.className = 'total aviso';\n"
        "}\n"
        "function lanzar(tipo) {\n"
        "  var n = parseInt(document.getElementById('num-' + tipo).textContent, 10);\n"
        "  var caras = CARAS_LISTA[tipo];\n"
        "  var res = document.getElementById('res-' + tipo);\n"
        "  var cont = []; var golpes = 0; var escudos = 0;\n"
        "  for (var i = 0; i < n; i++) {\n"
        "    var f = caras[Math.floor(Math.random() * 6)];\n"
        "    if (f === 'calavera') { golpes++; }\n"
        "    if (f === 'escudo-blanco') { escudos++; }\n"
        "    cont.push('<span class=\"dado dado-' + tipo + '\">' + CARAS[tipo][f] + '</span>');\n"
        "  }\n"
        "  res.innerHTML = cont.join('');\n"
        "  document.getElementById('res-' + tipo).closest('.grupo').classList.remove('aviso');\n"
        "  var total = tipo === 'ataque'\n"
        "    ? (golpes + ' golpe' + (golpes === 1 ? '' : 's'))\n"
        "    : (escudos + ' escudo' + (escudos === 1 ? '' : 's'));\n"
        "  var tt = document.getElementById('total-' + tipo);\n"
        "  tt.textContent = total;\n"
        "  tt.className = 'total';\n"
        "}\n"
        "function abrirDados() {\n"
        "  document.getElementById('modal-dados').hidden = false;\n"
        "}\n"
        "function cerrarDados() {\n"
        "  document.getElementById('modal-dados').hidden = true;\n"
        "}\n"
        "document.addEventListener('keydown', function (e) {\n"
        "  if (e.key === 'Escape' && !document.getElementById('modal-dados').hidden) { cerrarDados(); }\n"
        "});\n"
        "window.cambiar = cambiar; window.lanzar = lanzar; window.abrirDados = abrirDados; window.cerrarDados = cerrarDados;\n"
        "lanzar('ataque'); lanzar('defensa');\n"
    )


def _leyenda_mapa(mision: dict) -> str:
    """Leyenda pegajosa del mapa: los sprites dibujados y los rectángulos de color."""
    items: list[str] = []

    def swatch(slug: str) -> str:
        uri = _sprite_data_uri(slug, 0)
        return f'<img class="leyendaimg" src="{uri}" alt="">' if uri else ""

    # Rectángulos de color (siempre presentes en el mapa)
    colores = [
        (mapa.COLOR_ENTRADA, "Entrada"),
        (mapa.COLOR_SALIDA, "Salida"),
        (mapa.COLOR_TESORO, "Tesoro"),
        (mapa.COLOR_PASILLO, "Pasillo"),
        (mapa.COLOR_ROCA, "Roca dura"),
    ]
    for color, nombre in colores:
        items.append(
            f'<span class="leyenda-item"><span class="chip" style="background:{color}"></span>{nombre}</span>'
        )

    # Sprites presentes en esta misión
    sprites: list[tuple[str, str]] = []
    if mision.get("puertas"):
        sprites.append((mapa.PUERTA_ICONO, "Puerta cerrada"))
        sprites.append((mapa.PUERTA_ABIERTA_ICONO, "Puerta abierta"))
    if mision.get("puertas_secretas"):
        sprites.append((mapa.PUERTA_SECRETA_ICONO, "Puerta secreta"))
    entrada, salida = mision.get("entrada_heroes"), mision.get("salida_heroes")
    if mapa.ENTRADA_ICONO == mapa.SALIDA_ICONO:
        if entrada and salida:
            sprites.append((mapa.ENTRADA_ICONO, "Entrada / Salida"))
        elif entrada:
            sprites.append((mapa.ENTRADA_ICONO, "Entrada"))
        elif salida:
            sprites.append((mapa.SALIDA_ICONO, "Salida"))
    else:
        if entrada:
            sprites.append((mapa.ENTRADA_ICONO, "Entrada"))
        if salida:
            sprites.append((mapa.SALIDA_ICONO, "Salida"))
    for _, mu in mapa._muebles_mision(mision):
        slug = (mapa.MUEBLE_ICONO or {}).get(mu.get("tipo", ""))
        if slug:
            sprites.append((slug, mu["nombre"]))
    for sala in mision.get("salas", []):
        for tr in sala.get("trampas", []):
            slug = (mapa.TRAMPA_ICONO or {}).get(tr.get("nombre", ""))
            if slug:
                sprites.append((slug, tr["nombre"]))
    for grupo in (mision.get("pasillos", {}).get("marcadores", []),):
        for it in grupo:
            if "calavera" in (it.get("nombre") or "").lower():
                sprites.append((mapa._CALAVERA_SLUG, it.get("nombre", "Calavera")))

    vistos: set[str] = set()
    for slug, nombre in sprites:
        if not slug or slug in vistos:
            continue
        vistos.add(slug)
        items.append(f'<span class="leyenda-item">{swatch(slug)}<span>{html.escape(nombre)}</span></span>')

    return f"""
    <div class="leyenda">
      <h3>Leyenda del mapa</h3>
      <div class="leyenda-items">{"".join(items)}</div>
    </div>"""


def _casillas_vida(cuerpo: int) -> str:
    return " ".join(f'<label class="vida"><input type="checkbox" aria-label="Punto de cuerpo {i + 1}"></label>'
                    for i in range(max(cuerpo, 1)))


def _ficha_monstruo(m: dict | None, nombre: str, tesoro: str | None = None) -> str:
    if not m:
        return (
            f'<div class="card monstruo"><div class="mtitulo">{html.escape(nombre)}</div>'
            f'<div class="monotenue">Sin stats registradas</div></div>'
        )
    reto = ""
    if tesoro:
        reto = (f'<div class="reto"><b>Tesoro del Reto</b><span class="heck">🔍 buscado</span>'
                f'<span>{html.escape(tesoro)}</span></div>')
    return f"""
    <div class="card monstruo{' conreto' if tesoro else ''}">
      <div class="mtitulo">{html.escape(m["nombre"])}
        <span class="stats">A{m["ataque"]} D{m["defensa"]} Cu{m["cuerpo"]} Me{m["mente"]} Mov{m["movimiento"]}</span>
      </div>
      {reto}
      <details open>
        <summary>Vida</summary>
        <div class="vidas">{_casillas_vida(m["cuerpo"])}</div>
      </details>
    </div>"""


def _ficha_mueble(mu: dict) -> str:
    """Tarjeta de un mueble: checkbox 'buscado' y borde amarillo si tiene tesoro del Reto."""
    caja = '<input type="checkbox" class="chequeo" aria-label="Tesoro buscado">'
    reto = ""
    if mu.get("tesoro"):
        reto = f'<div class="reto"><span>{html.escape(mu["tesoro"])}</span></div>'
    return f"""
    <div class="card mueble{' conreto' if mu.get('tesoro') else ''}">
      <div class="mtitulo">
        <span class="icono-mueble">{html.escape(mu.get('tipo', 'Mueble'))}</span>
        <span class="nombre-mueble">{html.escape(mu['nombre'])}</span>
        <label class="check">{caja} buscado</label>
      </div>
      {reto}
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


def _formato_punto(p: dict) -> str:
    """Devuelve la representación de un punto: casilla {x,y} o umbral {de,a}."""
    if "de" in p and "a" in p:
        de, a = p["de"], p["a"]
        return f"({de[0]},{de[1]})–({a[0]},{a[1]})"
    return f'({p.get("x","?")},{p.get("y","?")})'


def _formato_mueble(mu: dict) -> str:
    """Representación del rectángulo de un mueble: (desde)-(hasta)."""
    d, h2 = mu.get("desde", []), mu.get("hasta", [])
    if len(d) == 2 and len(h2) == 2:
        return f"({d[0]},{d[1]})–({h2[0]},{h2[1]})"
    return "—"


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

    def _fila_item(a):
        subtipo = a.get("subtipo") or a.get("tipo", "")
        return (
            f'<tr><td>{html.escape(a["nombre"])}</td><td>{html.escape(subtipo)}</td>'
            f'<td>{"A" + str(a["ataque"]) if a.get("ataque") else "—"}</td>'
            f'<td>{"D" + str(a["defensa"]) if a.get("defensa") else "—"}</td>'
            f'<td>{a.get("coste", "—")}</td></tr>'
        )

    equipos = data_store.cargar("equipo")
    tesoros = data_store.cargar("tesoros")
    artefactos = data_store.cargar("artefactos")
    filas_a = "".join(_fila_item(a) for a in (equipos + tesoros + artefactos))
    secciones.append(f"""
    <section class="panel">
      <h3>Armas y equipo, tesoros y artefactos</h3>
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


def _panel_voz_alta(mision: dict) -> str:
    """Panel con las instrucciones de Zargon para leer en voz alta (bloque 'instrucciones_voz_alta')."""
    insts = mision.get("instrucciones_voz_alta", [])
    if not insts:
        return ""
    items = "".join(
        f'<li><div class="vocabada-momento">{html.escape(i.get("momento", ""))}</div>'
        f'<div class="vocabada-texto">{html.escape(i.get("texto", ""))}</div></li>'
        for i in insts
    )
    return f"""
    <section class="panel vozalta">
      <h3>Lectura en voz alta <span class="zg">(para Zargon)</span></h3>
      <ol class="vocabada">{items}</ol>
    </section>"""


def _render(mision: dict, t: dict) -> str:
    titulo = html.escape(mision["nombre"])
    tablero_data = data_store.cargar_json("tableros")
    tablero_nombre = next((tb["nombre"] for tb in tablero_data if tb["id"] == t["id"]), t["id"])

    salas_html = []
    for sala in mision.get("salas", []):
        monstruos = sala.get("monstruos", [])
        tesoros = sala.get("tesoros", [])
        mons = "".join(
            f'<div class="col">{_ficha_monstruo(_stats_monstruo(m["nombre"]), m["nombre"], m.get("tesoro"))}'
            f'<div class="pos">en {m.get("x", "?")},{m.get("y", "?")}</div></div>'
            for m in monstruos
        )
        tes = "".join(
            f'<li>{_ficha_tesoro(_stat_tesoro(x["nombre"]), x["nombre"])}'
            f'<span class="pos"> · {x.get("x","?")},{x.get("y","?")}</span></li>'
            for x in tesoros
        )
        muebles = "".join(
            f'<div class="col">{_ficha_mueble(mu)}'
            f'<div class="pos">{_formato_mueble(mu)}</div></div>'
            for mu in sala.get("muebles", [])
        )
        trampas = "".join(
            f'<li><b>{html.escape(tr["nombre"])}</b> ({tr.get("x","?")},{tr.get("y","?")}). '
            f'{html.escape(tr.get("descripcion", ""))}</li>'
            for tr in sala.get("trampas", [])
        )
        marcadores = "".join(
            f'<li><b>{html.escape(ma["nombre"])}</b> ({ma.get("x","?")},{ma.get("y","?")}). '
            f'{html.escape(ma.get("descripcion", ""))}</li>'
            for ma in sala.get("marcadores", [])
        )
        extras = ""
        if muebles:
            extras += f'<div class="subtipo">Muebles</div><div class="grid">{muebles}</div>'
        if trampas:
            extras += f'<div class="subtipo">Trampas</div><ul class="tesoros">{trampas}</ul>'
        if marcadores:
            extras += f'<div class="subtipo">Fichas / marcadores</div><ul class="tesoros">{marcadores}</ul>'
        salas_html.append(f"""
        <section class="sala">
          <header class="salacab">
            <span class="salnum">Sala {sala["numero"]}</span>
            <span class="salanom">{html.escape(sala["nombre"])}</span>
          </header>
          <p class="saladesc">{html.escape(sala.get("descripcion", ""))}</p>
          <div class="grid">{mons}</div>
          <ul class="tesoros">{tes}</ul>
          {extras}
          {f'<div class="notas">{html.escape(sala["notas"])}</div>' if sala.get("notas") else ""}
        </section>""")

    # Elementos en pasillo (fuera de sala)
    pasillos = mision.get("pasillos", {})
    if pasillos:
        bloques = []
        for etiqueta, clave in (("Monstruos", "monstruos"), ("Tesoros", "tesoros"),
                                ("Trampas", "trampas"), ("Fichas / marcadores", "marcadores")):
            items = pasillos.get(clave, [])
            if not items:
                continue
            lis = []
            for it in items:
                pos = _formato_punto(it)
                if clave == "monstruos":
                    lis.append(f'<li>{_ficha_monstruo(_stats_monstruo(it["nombre"]), it["nombre"])}'
                               f'<span class="pos"> · {pos}</span></li>')
                elif clave in ("trampas", "marcadores"):
                    lis.append(f'<li><b>{html.escape(it["nombre"])}</b> ({pos}). '
                               f'{html.escape(it.get("descripcion", ""))}</li>')
                else:
                    lis.append(f'<li>{_ficha_tesoro(_stat_tesoro(it["nombre"]), it["nombre"])}'
                               f'<span class="pos"> · {pos}</span></li>')
            bloques.append(f'<div class="subtipo">{etiqueta}</div><ul class="tesoros">{"".join(lis)}</ul>')
        pasillos_html = f"""
        <section class="sala">
          <header class="salacab">
            <span class="salnum">Pasillos</span>
            <span class="salanom">Elementos fuera de las salas</span>
          </header>
          <p class="saladesc">Refuerzos y trampas que ocupan los corredores y pasillos del tablero.</p>
          {"".join(bloques)}
        </section>"""
    else:
        pasillos_html = ""

    # Sprites de puertas incrustados (base64) pre-rotados por ángulo, para el
    # toggle: coinciden con el render inicial del SVG y evitan depender de
    # rutas absolutas de ICONOS_DIR al abrir el HTML desde cualquier sitio.
    slug_cerrada = mapa.PUERTA_ICONO
    slug_abierta = mapa.PUERTA_ABIERTA_ICONO
    sprites: dict[str, str] = {}
    for slug in (slug_abierta, slug_cerrada):
        if not slug:
            continue
        for angulo in sorted(_angulos_puertas(mision)):
            sprites[f"{slug}_{angulo}"] = _sprite_data_uri(slug, angulo)
    sprites_js = "{" + ", ".join(f"'{k}': '{v}'" for k, v in sprites.items()) + "}"

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
    padding:16px; overflow:auto; margin-bottom:12px;
  }}
  .mapa-titular {{ display:flex; align-items:center; justify-content:space-between; gap:10px;
    margin-bottom:10px; }}
  .mapa-titular h2 {{ margin:0; font-size:1.1rem; color:var(--bronce); }}
  .btn-dados {{ background:var(--madera); color:#f4e9d2; border:1px solid var(--madera);
    border-radius:20px; padding:5px 14px; font-size:.85rem; font-family:inherit;
    cursor:pointer; letter-spacing:.3px; }}
  .btn-dados:hover {{ background:#6d4a3f; }}
  .mapa-wrap svg {{ display:block; margin:0 auto; max-width:100%; height:auto; }}
  .mapa-switch {{ display:flex; gap:8px; margin-bottom:12px; }}
  .switch-btn {{
    background:transparent; border:1px solid var(--borde); color:var(--tinta);
    padding:6px 14px; border-radius:20px; cursor:pointer; font-size:.9rem;
  }}
  .switch-btn.active {{ background:var(--madera); color:#f4e9d2; border-color:var(--madera); font-weight:bold; }}
  .mapa-panel svg {{ display:none; }}
  .mapa-panel.visible svg {{ display:block; }}
  .leyenda {{
    position:sticky; bottom:0; z-index:20; background:rgba(243,236,221,.97);
    border:1px solid var(--borde); border-radius:12px; padding:10px 14px;
    margin-bottom:22px; box-shadow:0 -2px 12px rgba(0,0,0,.14);
  }}
  .leyenda h3 {{ margin:0 0 8px; font-size:.8rem; color:var(--bronce); text-transform:uppercase; letter-spacing:.5px; }}
  .leyenda-items {{ display:flex; flex-wrap:wrap; gap:6px 16px; align-items:center; }}
  .leyenda-item {{ display:inline-flex; align-items:center; gap:6px; font-size:.85rem; color:#3c2f1f; }}
  .chip {{ width:18px; height:18px; border-radius:4px; border:1px solid rgba(0,0,0,.25); display:inline-block; flex:none; }}
  .leyendaimg {{ height:30px; width:auto; object-fit:contain; }}
  .lanzador-dados {{ background:linear-gradient(135deg,#3a2620,#5d4037); color:#f4e9d2;
    border:1px solid #2e1f19; border-radius:12px; padding:8px 10px;
    box-shadow:0 2px 8px rgba(0,0,0,.25); }}
  .lanzador-dados h4 {{ margin:0 0 6px; font-size:.72rem; color:#e8d9b8;
    text-transform:uppercase; letter-spacing:.5px; }}
  .banco-dados {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .grupo {{ flex:1; min-width:170px; background:rgba(0,0,0,.18); border-radius:8px; padding:6px 8px; }}
  .control {{ display:flex; align-items:center; gap:5px; }}
  .etiqueta {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.3px; margin-right:2px; }}
  .etq-ataque {{ color:#ff9d87; font-weight:bold; }}
  .etq-defensa {{ color:#cfb893; font-weight:bold; }}
  .control button {{ width:22px; height:22px; border-radius:6px; border:1px solid rgba(255,255,255,.35);
    background:rgba(255,255,255,.12); color:#f4e9d2; font-size:.85rem; line-height:1; cursor:pointer; }}
  .control button:hover {{ background:rgba(255,255,255,.25); }}
  .control .lanzar {{ width:auto; padding:0 10px; font-size:.72rem; text-transform:uppercase;
    letter-spacing:.4px; background:var(--bronce); border-color:var(--bronce); color:#fff; font-weight:bold; }}
  .cantidad {{ min-width:20px; text-align:center; font-size:.95rem; font-weight:bold; }}
  .resultado {{ min-height:42px; display:flex; flex-wrap:wrap; align-items:center; }}
  .dado {{ display:inline-flex; width:36px; height:36px; margin:0 3px 3px 0; border-radius:8px;
    align-items:center; justify-content:center; }}
  .dado svg {{ width:24px; height:24px; }}
  .dado-ataque {{ background:linear-gradient(135deg,#d64541,#96281b); border:1px solid #7d1f14;
    box-shadow:inset 0 -3px 0 rgba(0,0,0,.28); }}
  .dado-defensa {{ background:linear-gradient(135deg,#fdfcf7,#e6dcc2); border:1px solid #b7a583;
    box-shadow:inset 0 -3px 0 rgba(0,0,0,.12); }}
  .total {{ font-size:.78rem; font-weight:bold; color:#f4e9d2; }}
  .total.aviso {{ color:#ffd27f; font-style:italic; }}
  .grupo.aviso {{ outline:2px solid #e0a020; outline-offset:-2px; }}
  .dado.pendiente {{ opacity:.6; }}
  .dado-ataque.pendiente {{ color:#fdf6e3; }}
  .dado-defensa.pendiente {{ color:#3a3024; }}
  .dado.pendiente::after {{ content:'?'; font-family:Georgia,serif; font-size:17px; font-weight:bold; }}
  .modal-dados {{ position:fixed; inset:0; z-index:100; display:flex;
    align-items:center; justify-content:center; }}
  .modal-dados[hidden] {{ display:none; }}
  .modal-fondo {{ position:absolute; inset:0; background:rgba(24,14,8,.55); }}
  .modal-caja {{ position:relative; width:min(620px,92vw); background:var(--claro);
    border:1px solid var(--borde); border-radius:14px; padding:18px 18px 14px;
    box-shadow:0 8px 30px rgba(0,0,0,.4); }}
  .modal-cerrar {{ position:absolute; top:8px; right:10px; width:28px; height:28px; border-radius:50%;
    border:1px solid var(--borde); background:transparent; color:var(--tinta);
    font-size:1.15rem; line-height:1; cursor:pointer; }}
  .modal-cerrar:hover {{ background:var(--borde); }}
  .modal-pie {{ margin:10px 0 0; font-size:.78rem; color:#6b563a; font-style:italic; }}
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
  .notas {{ margin-top:.8em; border-top:1px dashed var(--borde); padding-top:.6em; }}
  .notas::before {{ content:"Notas de Zargon: "; font-weight:bold; color:var(--rojo); font-size:.85rem; text-transform:uppercase; letter-spacing:.4px; }}
  .pos {{ color:#8a6d3b; font-size:.82rem; }}
  .subtipo {{ margin-top:.6em; font-weight:bold; color:var(--bronce); font-size:.85rem; text-transform:uppercase; letter-spacing:.4px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:10px; }}
  .mueble .mtitulo {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .icono-mueble {{ background:#b48c5a; color:#fff; border-radius:6px; padding:2px 7px; font-size:.75rem; font-weight:bold; }}
  .check {{ margin-left:auto; font-size:.85rem; color:#555; display:flex; align-items:center; gap:4px; }}
  .check input {{ accent-color:var(--verde); width:16px; height:16px; cursor:pointer; }}
  .card.conreto {{ border:3px solid #f6c700; }}
  .reto {{ margin-top:6px; border-top:1px dashed var(--borde); padding-top:6px; font-size:.88rem; }}
  .reto b {{ display:block; color:#9c6b00; font-size:.8rem; text-transform:uppercase; letter-spacing:.4px; }}
  .vozalta h3 {{ display:flex; gap:8px; align-items:baseline; }}
  .vozalta .zg {{ font-size:.7rem; color:#7a5230; font-weight:normal; letter-spacing:.3px; }}
  .vocabada {{ margin:0; padding-left:1.3em; display:grid; gap:12px; }}
  .vocabada li {{ margin:0; }}
  .vocabada-momento {{ font-weight:bold; color:var(--rojo); font-size:.87rem; }}
  .vocabada-texto {{ font-style:italic; color:#3c2f1f; }}
  @media print {{
    body {{ background:#fff; }}
    .portada, .sala, .panel, .mapa-wrap {{ box-shadow:none; }}
    .leyenda {{ position:static; box-shadow:none; }}
    .modal-dados {{ display:none !important; }}
    .btn-dados {{ display:none; }}
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

  {f'<div class="panel"><h3>Notas del máster</h3><p>{html.escape(mision["notas"])}</p></div>' if mision.get("notas") else ""}

  {_panel_voz_alta(mision)}

  <div class="mapa-seccion">
  <div class="mapa-wrap">
    <div class="mapa-titular">
      <h2>Mapa de la misión</h2>
      <button type="button" class="btn-dados" onclick="abrirDados()">Lanzador de dados</button>
    </div>
    <div class="mapa-switch" role="tablist">
      <button class="switch-btn active" data-mapa="salas" role="tab" aria-selected="true">Nº de sala</button>
      <button class="switch-btn" data-mapa="coordenadas" role="tab" aria-selected="false">Coordenadas</button>
    </div>
    <div class="mapa-panel" id="mapa-salas">
      {_mapa_svg(mision, t, mostrar="salas", sufijo_id="-salas")}
    </div>
    <div class="mapa-panel oculto" id="mapa-coordenadas">
      {_mapa_svg(mision, t, mostrar="coordenadas", sufijo_id="-coord")}
    </div>
  </div>

  {_leyenda_mapa(mision)}
  </div>

  <div class="salas">
    {''.join(salas_html)}
  </div>

  {pasillos_html}

  <h2 style="color:var(--bronce); margin-bottom:10px;">Referencia del máster</h2>
  {_referencia()}

  <div class="modal-dados" id="modal-dados" hidden>
    <div class="modal-fondo" onclick="cerrarDados()"></div>
    <div class="modal-caja" role="dialog" aria-modal="true" aria-label="Lanzador de dados">
      <button type="button" class="modal-cerrar" onclick="cerrarDados()" aria-label="Cerrar">&times;</button>
      {_lanzador_dados()}
      <p class="modal-pie">Escudo negro: sin efecto. Calavera = golpe en ataque; escudo blanco = bloqueo en defensa.</p>
    </div>
  </div>
  <script>
    (function () {{
      var panelSalas = document.getElementById('mapa-salas');
      var panelCoords = document.getElementById('mapa-coordenadas');
      function mostrar(nombre) {{
        panelSalas.classList.toggle('visible', nombre === 'salas');
        panelCoords.classList.toggle('visible', nombre === 'coordenadas');
        document.querySelectorAll('.switch-btn').forEach(function (b) {{
          var activo = b.getAttribute('data-mapa') === nombre;
          b.classList.toggle('active', activo);
          b.setAttribute('aria-selected', activo ? 'true' : 'false');
        }});
      }}
      document.querySelectorAll('.switch-btn').forEach(function (b) {{
        b.addEventListener('click', function () {{ mostrar(b.getAttribute('data-mapa')); }});
      }});

      /* ── Toggle de puertas ── */
      var COLOR_ABIERTA = '{mapa.COLOR_PUERTA_ABIERTA}';
      var COLOR_CERRADA = '{mapa.COLOR_PUERTA_CERRADA}';
      var SLUG_ABIERTA = '{mapa.PUERTA_ABIERTA_ICONO}';
      var SLUG_CERRADA = '{mapa.PUERTA_ICONO}';
      /* Sprites incrustados en base64, pre-rotados por ángulo: {sprites_js} */
      var SPRITES = {sprites_js};

      function resolverIcono(slug, angulo) {{
        return SPRITES[slug + '_' + angulo] || SPRITES[slug + '_0'] || '';
      }}

      function pintarPuerta(g, nueva, slug, borde) {{
        g.setAttribute('data-estado', nueva);
        var angulo = parseInt(g.getAttribute('data-angulo') || '0', 10);
        /* Actualizar imagen: la rotación ya está en los píxeles del sprite,
           así que el recorte 'slice' queda igual que en el render inicial */
        var img = g.querySelector('image');
        if (img) {{
          img.setAttribute('href', resolverIcono(slug, angulo));
          img.removeAttribute('transform');
        }}
        /* Actualizar borde */
        var rect = g.querySelector('rect[stroke]');
        if (rect && rect.getAttribute('fill') === 'none') {{
          rect.setAttribute('stroke', borde);
        }}
      }}

      function togglePuerta(g) {{
        var de = g.getAttribute('data-de');
        var a = g.getAttribute('data-a');
        var actual = g.getAttribute('data-estado');
        var nueva = actual === 'abierta' ? 'cerrada' : 'abierta';
        var slug = nueva === 'abierta' ? SLUG_ABIERTA : SLUG_CERRADA;
        var borde = nueva === 'abierta' ? COLOR_ABIERTA : COLOR_CERRADA;
        /* Sincronizar todas las vistas (salas y coordenadas) */
        document.querySelectorAll('.puerta-interactiva').forEach(function (otra) {{
          if (otra.getAttribute('data-de') === de && otra.getAttribute('data-a') === a) {{
            pintarPuerta(otra, nueva, slug, borde);
          }}
        }});
      }}

      document.querySelectorAll('.puerta-interactiva').forEach(function (g) {{
        g.addEventListener('click', function () {{ togglePuerta(g); }});
      }});

      {_js_dados()}

      mostrar('salas');
    }})();
  </script>
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
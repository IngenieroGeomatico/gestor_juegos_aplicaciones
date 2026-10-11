"""Ingesta canonica de los logs de Pokelike a SQLite.

## Por que existe

Medir sobre los logs a pelo significa **reescribir el parser en cada
pregunta**, y cada reescritura puede equivocarse de una forma nueva. En una
sola sesion se han cometido cuatro fallos de este tipo: un `parents[3]` que
apuntaba a un directorio inexistente, un `dist = len(prev) - k` que
"calculaba" la distancia a la curacion dando el numero de decisiones, un
`placeholder` que dejo un bucle vacio, y un lote `ABORTADO` colandose en una
media y metiendo un artefacto de bucle.

Aqui el parseo se hace **una vez**, con el resultado en una base de datos, y
cada pregunta pasa a ser una consulta. Ademas queda **auditable**: la tabla
`evento` guarda la linea cruda de todo lo que no tiene tabla propia, de modo
que no se pierde ningun campo por el camino.

## Aviso, y es importante

Una base de datos **congela el parseo**. Si un campo se lee mal, se guarda mal
y encima parece autoritativo. Esto NO decide si un campo es fiable: eso es una
pregunta sobre el DOM del juego (ver `_sonda_dom` en `jugar_pokelike.py`).

## Que guarda

  run      una fila por fichero de log: cabecera, resumen final y metadata
  paso     cada `TRAZA_CAMINO` (la vida por paso de mapa, en porcentaje)
  nodo     cada `DEC nodo` (el nodo elegido, con que opciones y por que)
  pelea    cada combate: rivales, `mios`, `enemigos` y **las dos** lecturas
           de PS (`ps_abre` del texto de combate y `paso.vida` del HUD)
  evento   todo lo demas con forma `k=v` o `[algo -> x]`, con la linea cruda
  sonda    el volcado crudo de `_sonda_dom`, si existe

Uso:

    uv run --group dev python juegos/pokelike/scripts/pkl_corpus.py
    uv run --group dev python juegos/pokelike/scripts/pkl_corpus.py --db /tmp/x.db
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
LOGS = RAIZ / "juegos/pokelike/log"
DB_POR_DEFECTO = LOGS / "corpus.db"

# El prefijo de hora solo esta en los logs nuevos: los viejos empiezan por el
# contenido. Se quita si esta, y no se toca el contenido.
HORA = re.compile(r"^\s*\[(\d{1,2}:\d{2}:\d{2})\]\s*")

# Un lote cuenta como valido salvo que su nombre lo marque como abortado: el
# `h21` es `ABORTADO` y su bucle metia 25 curas falsas en una media.
NO_VALIDO = re.compile(r"ABORTADO|ROTO|TIMEOUT|STUCK|TESTLOOP|SANITY|CRUZADO")

RGX = {
    "run_cabecera": re.compile(r"^==\s*(?:brazo=(?P<brazo>\S+)\s*\|)?(.*?)==$"),
    "resumen": re.compile(r"^RESUMEN\s+(?P<region>\S+)"),
    "tiene_traza": re.compile(r"TRAZA_CAMINO "),
    "traza": re.compile(
        r"^TRAZA_CAMINO paso=(?P<paso>\d+) mapa='(?P<mapa>.*?)' "
        r"ins=(?P<ins>\d+) disp=\[(?P<disp>[^\]]*)\] "
        r"vivos=(?P<vivos>\d+)/(?P<n>\d+) caidos=(?P<caidos>\d+) "
        r"vida_media=(?P<media>-?\d+)% vida=\[(?P<vida>[^\]]*)\] "
        r"niveles=\[(?P<niveles>[^\]]*)\] elige=(?P<elige>\S+) peso=(?P<peso>\S+)"),
    "nodo": re.compile(
        r"^DEC nodo mapa=(?P<mapa>.*?) nodo=(?P<nodo>\S+) tipo=(?P<tipo>\w+) "
        r"crudo=(?P<crudo>\S+) atajo=(?P<atajo>\S+) equipo=(?P<equipo>\d+) "
        r"vivos=(?P<vivos>\d+) niv=(?P<niv_min>\d+)-(?P<niv_max>\d+) "
        r"insignias=(?P<insignias>\d+) disponibles=(?P<disp>[^ ]*) "
        r"capturas_pantalla=(?P<capturas>\d+) razon=(?P<razon>\w+) "
        r"score=(?P<score>-?[\d.]+)(?P<motivo>\s*\(.*)?$"),
    "nodo_el": re.compile(
        r"^\[\s*nodo -> (?P<elige>\d+)\]\s+(?P<tipo>\w+)\s+"
        r"score=(?P<score>-?[\d.]+)\s+\((?P<motivo>.*)\)\s*"
        r"(?:\|\s*mapa:\s*(?P<mapa>.*?)\s*\|\s*plan: insignias (?P<insignias>\d+)"
        r"\s*\|\s*(?P<ciudad>.*?)\s*\|\s*opc:\s*(?P<opc>.*))?$"),
    "contexto": re.compile(
        r"^(?P<mapa>.*?)\s*\|\s*equipo (?P<equipo>\d+) \(vivos (?P<vivos>\d+)\) "
        r"niv (?P<niv_min>\d+)-(?P<niv_max>\d+)\s*\|\s*lider (?P<lider>\S+) "
        r"\|\s*insignias (?P<insignias>\d+)\s*\|\s*disponibles \[(?P<disp>[^\]]*)\]"
        r" \(crudo \[(?P<crudo>[^\]]*)\]\)\s*\|\s*rivales (?P<rivales>\S+)"
        r"\s*\|\s*total (?P<tot>\S+)\s*\|\s*TM usado: (?P<tm>\w+), "
        r"bolsa: \[(?P<bolsa>[^\]]*)\]"),
    "estado": re.compile(
        r"^estado: (?P<rival>.*?) \| niveles rivales (?P<niv_min>\d+)-(?P<niv_max>\d+)"),
    "lista": re.compile(r"^(?P<clave>enemigos|mios)=\[(?P<cuerpo>.*)\]$"),
    "combate": re.compile(
        r"^>>> COMBATE (?P<res>GANADO|PERDIDO)"
        r"(?: contra (?P<rival_perdido>.*?))?"
        r"(?: \(continuamos en (?P<pantalla>[\w-]+)\))?"
        r"\s*\|\s*(?P<resto>.*)$"),
    "ps": re.compile(r"^DEC ps_(?P<momento>abre|cierra) (?P<resto>.*)$"),
    "dec": re.compile(r"^DEC (?P<evento>\w+) (?P<resto>.*)$"),
    "captura_ok": re.compile(
        r"^>>> CAPTURA confirmada \(equipo (?P<antes>\d+)->(?P<despues>\d+)\)"
        r" \| total (?P<total>\d+)"),
    "insignia": re.compile(
        r"^\[\s*insignia -> True\] insignia conseguida \(total (?P<total>\d+)\)"),
    "insignias_delta": re.compile(r"^>> insignias: (?P<antes>\d+) -> (?P<despues>\d+)"),
    "evento_corchete": re.compile(r"^\[\s*(?P<clave>\w+) -> (?P<valor>[^\]]*)\] ?(?P<cola>.*)$"),
    "resumen_campo": re.compile(r"^(?P<clave>[\w. á]+?)\s*:\s*(?P<valor>.*)$"),
    "errores": re.compile(r"^(?P<texto>!!.*|no se pudo .*|.*no legible.*)$"),
    "reroll": re.compile(r"^[↻→]\s*(?P<texto>.*)$|^->\s*(?P<texto2>.*)$"),
    "ps_real_invalidado": re.compile(r"^· PS real invalidado \((?P<motivo>.*)\)$"),
}

_PARES = re.compile(r"(\w+)\s*=\s*(.*?)(?=\s+\w+\s*=|$)")

ESQUEMA = """
CREATE TABLE run (
  id INTEGER PRIMARY KEY, ruta TEXT UNIQUE, archivo TEXT, lote TEXT, valido INTEGER,
  hora TEXT, tiene_traza INTEGER, tiene_ps_abre INTEGER, tiene_resumen INTEGER,
  region TEXT, navegador TEXT, pokedex_especies INTEGER, ajustes TEXT,
  brazo TEXT, flags TEXT, codigo TEXT, presupuesto INTEGER,
  resumen_json TEXT, fin_json TEXT,
  resultado TEXT, pasos INTEGER, insignias INTEGER,
  combates_ganados INTEGER, combates_perdidos INTEGER,
  peleas_entrenador INTEGER, nv_entrenador INTEGER,
  peleas_salvaje INTEGER, nv_salvaje INTEGER,
  capturas INTEGER, tutores INTEGER, objetos INTEGER, centros INTEGER,
  equipo_final TEXT, equipo_final_rango TEXT, traza_path TEXT
);
CREATE TABLE paso (
  id INTEGER PRIMARY KEY, run_id INTEGER, orden INTEGER,
  paso INTEGER, mapa TEXT, ins INTEGER, disp TEXT,
  vivos INTEGER, total INTEGER, caidos INTEGER, vida_media INTEGER,
  vida TEXT, niveles TEXT, elige TEXT, peso TEXT
);
CREATE TABLE nodo (
  id INTEGER PRIMARY KEY, run_id INTEGER, orden INTEGER, linea INTEGER,
  mapa TEXT, nodo TEXT, tipo TEXT, crudo TEXT, equipo INTEGER, vivos INTEGER,
  niv_min INTEGER, niv_max INTEGER, insignias INTEGER,
  disponibles TEXT, capturas_pantalla INTEGER, razon TEXT, score REAL,
  motivo TEXT, elige INTEGER, ciudad TEXT, opc TEXT
);
CREATE TABLE pelea (
  id INTEGER PRIMARY KEY, run_id INTEGER, orden INTEGER, linea INTEGER,
  n_pelea INTEGER, tipo TEXT, rival TEXT, nivel_min INTEGER, nivel_max INTEGER,
  insignias INTEGER, nuestro_niv INTEGER, rival_niv INTEGER,
  nuestros INTEGER, suyo INTEGER, enemigos TEXT, mios TEXT,
  enemigos_n INTEGER, mios_n INTEGER, mios_ps_total INTEGER,
  resultado TEXT, continuamos_en TEXT, rival_perdido TEXT, nos_quedan TEXT,
  marcador_a INTEGER, marcador_b INTEGER,
  ps_abre_total INTEGER, ps_abre_equipo TEXT,
  ps_cierra_total INTEGER, ps_cierra_equipo TEXT,
  paso_traza INTEGER, paso_vida_media INTEGER, paso_vida TEXT,
  paso_caidos INTEGER, paso_vivos INTEGER
);
CREATE TABLE evento (
  id INTEGER PRIMARY KEY, run_id INTEGER, orden INTEGER, linea INTEGER,
  hora TEXT, tipo TEXT, clave TEXT, valor TEXT, cola TEXT, crudo TEXT
);
CREATE TABLE sonda (
  id INTEGER PRIMARY KEY, run_id INTEGER, etiqueta TEXT, paso INTEGER,
  pantalla TEXT, hora TEXT, barra TEXT, lado TEXT, enemigos TEXT,
  barra_html TEXT, lado_html TEXT
);
CREATE INDEX idx_paso_run ON paso(run_id);
CREATE INDEX idx_nodo_run ON nodo(run_id);
CREATE INDEX idx_pelea_run ON pelea(run_id);
CREATE INDEX idx_evento_run_tipo ON evento(run_id, tipo);
"""


def _pares(texto: str) -> dict[str, str]:
    """Pares `clave=valor` de una linea, respetando valores con espacios."""
    return {m.group(1): m.group(2).strip() for m in _PARES.finditer(texto)}


def _int(x, por_defecto=None):
    try:
        return int(x)
    except (TypeError, ValueError):
        return por_defecto


def _float(x, por_defecto=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return por_defecto


def _literal(texto: str, por_defecto=None):
    """`ast.literal_eval` de un `mios=[...]`/`enemigos=[...]`."""
    try:
        return ast.literal_eval(f"[{texto}]")
    except (ValueError, SyntaxError):
        return por_defecto


def lineas_vivas(ruta: Path):
    """(n_linea, hora, texto) de las lineas utiles del log.

    Se descartan dos cosas que ensuciarian el parseo:

      - el **eco JSON** del final: el bot vuelca su diario y las decisiones
        aparecen entrecomilladas (`"[nodo -> 1] ..."`), que si no se cuela
        como una decision de verdad duplicada;
      - los bloques JSON a pelo (`{`, `"lv": 5,`), que son volcados de DOM.
    """
    try:
        bruto = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    dentro_json = False
    for n, ln in enumerate(bruto, 1):
        txt = ln.rstrip()
        m = HORA.match(txt)
        hora = m.group(1) if m else None
        if hora:
            txt = txt[m.end():]
        s = txt.strip()
        if not s:
            continue
        # eco entrecomillado
        if s.startswith('"'):
            continue
        # bloques JSON pretty-printed
        if s == "{":
            dentro_json = True
            continue
        if dentro_json:
            if s == "}":
                dentro_json = False
            continue
        if s in ("}", "},", "],", "]", "[", "{"):
            continue
        yield n, hora, txt.strip()


def _vida_por_nombre(texto: str) -> list[dict]:
    """`['Bulbasaur:100%', 'Pikachu:0%']` -> [{nombre, pct, nivel?}]."""
    out = []
    for trozo in (texto or "").split(","):
        if ":" not in trozo:
            continue
        nom, pct = trozo.rsplit(":", 1)
        nom = nom.strip().strip("'\"")
        pct = re.sub(r"[^0-9-]", "", pct)
        if nom:
            out.append({"nombre": nom, "pct": _int(pct)})
    return out


def _niveles(texto: str) -> list[int]:
    return [_int(x) for x in (texto or "").split(",") if x.strip()]


def _miembros(cuerpo: str) -> list[dict]:
    """`('Pikachu Lv15', '0/35', 15)` -> nombre, ps, max, nivel."""
    crudo = _literal(cuerpo)
    if not crudo:
        return []
    out = []
    for fila in crudo:
        if not isinstance(fila, (list, tuple)) or len(fila) < 2:
            continue
        nom = str(fila[0])
        mm = re.match(r"^(.*?)\s*Lv\.?\s*(\d+)$", nom)
        nivel = _int(fila[2]) if len(fila) > 2 else None
        if mm:
            nom, nivel = mm.group(1).strip(), _int(mm.group(2))
        ps = str(fila[1])
        m2 = re.match(r"^(\d+)\s*/\s*(\d+)$", ps)
        out.append({
            "nombre": nom, "nivel": nivel, "ps_texto": ps,
            "ps": _int(m2.group(1)) if m2 else None,
            "ps_max": _int(m2.group(2)) if m2 else None,
        })
    return out


def parsear(ruta: Path) -> dict:
    """Todo lo de un log, en estructuras listas para insertar."""
    rel = ruta.relative_to(LOGS)
    lote = rel.parts[0] if len(rel.parts) > 1 else "(suelto)"
    run = {
        "ruta": str(rel), "archivo": ruta.name, "lote": lote,
        "valido": 0 if NO_VALIDO.search(lote or ruta.name) else 1,
        "hora": None, "tiene_traza": 0, "tiene_ps_abre": 0,
        "tiene_resumen": 0, "region": None, "navegador": None,
        "pokedex_especies": None, "ajustes": None, "brazo": None,
        "flags": None, "codigo": None, "presupuesto": None,
        "resumen_json": None, "fin_json": None, "resultado": None,
        "pasos": None, "insignias": None, "combates_ganados": None,
        "combates_perdidos": None, "peleas_entrenador": None,
        "nv_entrenador": None, "peleas_salvaje": None, "nv_salvaje": None,
        "capturas": None, "tutores": None, "objetos": None, "centros": None,
        "equipo_final": None, "equipo_final_rango": None, "traza_path": None,
    }
    pasos, nodos, peleas, eventos = [], [], [], []
    orden = 0
    # Contexto de la pelea que se va cerrando
    abierta = None

    for n, hora, txt in lineas_vivas(ruta):
        orden += 1
        if run["hora"] is None and hora:
            run["hora"] = hora

        if txt.startswith("navegador:"):
            run["navegador"] = txt.split(":", 1)[1].strip()
            continue
        if txt.startswith("pokedex cargado:"):
            run["pokedex_especies"] = _int(re.sub(r"\D", "", txt.split(":", 1)[1]))
            continue
        if txt.startswith("ajustes:"):
            run["ajustes"] = txt.split(":", 1)[1].strip()
            continue
        if txt.startswith("== run "):
            m = re.search(r"presupuesto (\d+)", txt)
            run["presupuesto"] = _int(m.group(1)) if m else None
            continue
        if txt.startswith("== brazo=") or txt.startswith("== brazo"):
            run["brazo"] = txt
            m = re.search(r"codigo=(\w+)", txt)
            if m:
                run["codigo"] = m.group(1)
            run["flags"] = txt
            continue

        m = RGX["traza"].match(txt)
        if m:
            run["tiene_traza"] = 1
            g = m.groupdict()
            pasos.append({
                "orden": orden, "paso": _int(g["paso"]), "mapa": g["mapa"],
                "ins": _int(g["ins"]), "disp": g["disp"],
                "vivos": _int(g["vivos"]), "total": _int(g["n"]),
                "caidos": _int(g["caidos"]), "vida_media": _int(g["media"]),
                "vida": g["vida"], "niveles": g["niveles"],
                "elige": g["elige"], "peso": g["peso"],
            })
            continue

        m = RGX["nodo"].match(txt)
        if m:
            g = m.groupdict()
            nodos.append({
                "orden": orden, "linea": n, "mapa": g["mapa"], "nodo": g["nodo"],
                "tipo": g["tipo"], "crudo": g["crudo"], "equipo": _int(g["equipo"]),
                "vivos": _int(g["vivos"]), "niv_min": _int(g["niv_min"]),
                "niv_max": _int(g["niv_max"]), "insignias": _int(g["insignias"]),
                "disponibles": g["disp"], "capturas_pantalla": _int(g["capturas"]),
                "razon": g["razon"], "score": _float(g["score"]),
                "motivo": (g["motivo"] or "").strip().strip("()"),
                "elige": None, "ciudad": None, "opc": None,
            })
            continue

        m = RGX["nodo_el"].match(txt)
        if m:
            g = m.groupdict()
            if nodos:
                nodos[-1].update({
                    "elige": _int(g["elige"]), "ciudad": g["ciudad"],
                    "opc": g["opc"],
                    "score": _float(g["score"]) or nodos[-1]["score"],
                })
            continue

        m = RGX["ps"].match(txt)
        if m:
            run["tiene_ps_abre"] = 1
            if abierta is None:
                abierta = {}
            campos = _pares(m.group("resto"))
            abierta[f"ps_{m.group('momento')}_total"] = _int(campos.get("ps_total"))
            abierta[f"ps_{m.group('momento')}_equipo"] = campos.get("equipo")
            if abierta.get("rival") is None:
                abierta["rival"] = campos.get("rival")
                abierta["tipo"] = campos.get("tipo")
            continue

        m = RGX["dec"].match(txt)
        if m:
            campos = _pares(m.group("resto"))
            if m.group("evento") == "combate":
                if abierta is None:
                    abierta = {}
                abierta["rival"] = campos.get("rival")
                abierta["tipo"] = campos.get("tipo")
                abierta["nuestro_niv"] = _int(campos.get("nuestro_niv"))
                abierta["rival_niv"] = _int(campos.get("rival_niv"))
                abierta["nuestros"] = _int(campos.get("nuestros"))
                abierta["suyo"] = _int(campos.get("suyo"))
                abierta["insignias"] = _int(campos.get("insignias"))
            eventos.append({
                "orden": orden, "linea": n, "hora": hora, "tipo": f"DEC {m.group('evento')}",
                "clave": None, "valor": None, "cola": None,
                "crudo": txt, "campos": campos,
            })
            continue

        m = RGX["estado"].match(txt)
        if m:
            if abierta is None:
                abierta = {}
            abierta["rival"] = abierta.get("rival") or m.group("rival")
            abierta["nivel_min"] = _int(m.group("niv_min"))
            abierta["nivel_max"] = _int(m.group("niv_max"))
            abierta["linea"] = abierta.get("linea") or n
            continue

        m = RGX["lista"].match(txt)
        if m:
            if abierta is None:
                abierta = {}
            mie = _miembros(m.group("cuerpo"))
            abierta[m.group("clave")] = json.dumps(mie, ensure_ascii=False)
            continue

        m = RGX["combate"].match(txt)
        if m:
            b = abierta or {}
            mie = json.loads(b.get("mios") or "[]")
            ene = json.loads(b.get("enemigos") or "[]")
            resto = m.group("resto") or ""
            # El marcador va al final de la linea: en la victoria es `14-0` y en
            # la derrota `nos quedan: ... | 6-1`. Se coge el ULTIMO `a-b` para no
            # confundirlo con un porcentaje de vida tipo `(100/100)`.
            mar = re.findall(r"(\d+)\s*-\s*(\d+)\s*$", resto)
            nq = re.search(r"nos quedan:\s*(.*?)\s*\|\s*\d+\s*-\s*\d+\s*$", resto)
            peleas.append({
                "orden": orden, "linea": b.get("linea") or n,
                "tipo": b.get("tipo"), "rival": b.get("rival"),
                "nivel_min": b.get("nivel_min"), "nivel_max": b.get("nivel_max"),
                "insignias": b.get("insignias"), "nuestro_niv": b.get("nuestro_niv"),
                "rival_niv": b.get("rival_niv"), "nuestros": b.get("nuestros"),
                "suyo": b.get("suyo"),
                "enemigos": json.dumps(ene, ensure_ascii=False),
                "mios": json.dumps(mie, ensure_ascii=False),
                "enemigos_n": len(ene), "mios_n": len(mie),
                "mios_ps_total": sum(x["ps"] or 0 for x in mie),
                "resultado": m.group("res"), "continuamos_en": m.group("pantalla"),
                "rival_perdido": m.group("rival_perdido"),
                "nos_quedan": nq.group(1) if nq else None,
                "marcador_a": _int(mar[-1][0]) if mar else None,
                "marcador_b": _int(mar[-1][1]) if mar else None,
                "ps_abre_total": b.get("ps_abre_total"),
                "ps_abre_equipo": b.get("ps_abre_equipo"),
                "ps_cierra_total": b.get("ps_cierra_total"),
                "ps_cierra_equipo": b.get("ps_cierra_equipo"),
            })
            abierta = None
            continue

        m = RGX["insignia"].match(txt)
        if m:
            eventos.append({"orden": orden, "linea": n, "hora": hora,
                            "tipo": "insignia", "clave": "total",
                            "valor": m.group("total"), "cola": None, "crudo": txt})
            continue

        m = RGX["insignias_delta"].match(txt)
        if m:
            eventos.append({"orden": orden, "linea": n, "hora": hora,
                            "tipo": "insignias_delta", "clave": None,
                            "valor": None, "cola": None, "crudo": txt,
                            "campos": m.groupdict()})
            continue

        m = RGX["captura_ok"].match(txt)
        if m:
            eventos.append({"orden": orden, "linea": n, "hora": hora,
                            "tipo": "captura_ok", "clave": None, "valor": None,
                            "cola": None, "crudo": txt, "campos": m.groupdict()})
            continue

        m = RGX["evento_corchete"].match(txt)
        if m:
            eventos.append({"orden": orden, "linea": n, "hora": hora,
                            "tipo": f"[{m.group('clave')}]",
                            "clave": m.group("clave"), "valor": m.group("valor"),
                            "cola": m.group("cola"), "crudo": txt})
            continue

        m = RGX["contexto"].match(txt)
        if m:
            eventos.append({"orden": orden, "linea": n, "hora": hora,
                            "tipo": "contexto", "clave": None, "valor": None,
                            "cola": None, "crudo": txt, "campos": m.groupdict()})
            continue

        m = RGX["resumen_campo"].match(txt)
        if m and run["tiene_resumen"]:
            _resumen_campo(run, m.group("clave").strip(), m.group("valor").strip())
            continue

        m = RGX["resumen"].match(txt)
        if m:
            run["tiene_resumen"] = 1
            run["region"] = m.group("region")
            continue

        eventos.append({"orden": orden, "linea": n, "hora": hora,
                        "tipo": _tipo_generico(txt), "clave": None, "valor": None,
                        "cola": None, "crudo": txt})

    # **Cierre de la run.** El bloque `RESUMEN` manda cuando esta. Cuando no
    # esta (run matada a medias: el caso de la prueba de humo y de cualquier
    # `timeout`), el resultado y el equipo final se sacan del JSON que el bot
    # escribe al final. Sin esto, las runs cortadas quedan con `resultado`
    # nulo y desaparecen de cualquier consulta que filtre por resultado.
    if run["resultado"] is None or run["pasos"] is None:
        fin = _json_final(ruta)
        if fin:
            run["fin_json"] = json.dumps(fin, ensure_ascii=False)
            for campo, clave in (("resultado", "resultado"),
                                 ("region", "region"), ("pasos", "pasos"),
                                 ("insignias", "insignias")):
                if run[campo] is None and fin.get(clave) is not None:
                    run[campo] = fin[clave]
            eq = fin.get("equipo") or []
            if run["equipo_final"] is None and eq:
                run["equipo_final"] = len(eq)
                lv = [m.get("lv") for m in eq if m.get("lv") is not None]
                if lv:
                    run["equipo_final_rango"] = f"{min(lv)}-{max(lv)}"
    return {"run": run, "pasos": pasos, "nodos": nodos, "peleas": peleas,
            "eventos": eventos}


def _tipo_generico(txt: str) -> str:
    pref = re.split(r"[ :]", txt, maxsplit=1)[0]
    return (pref or "?")[:24]


def _resumen_campo(run: dict, clave: str, valor: str) -> None:
    """Una linea del bloque `RESUMEN`, campo a campo.

    El bloque trae mas de lo que parece y todo es util: `combates` da el
    ganado/perdido, y `peleas entrain. : 3 (+7 nv)` da a la vez cuantas peleas
    de entrenador hubo y cuanta experiencia dieron, que es justo lo que hace
    falta para saber si la run llego corta de nivel.
    """
    k = clave.strip().lower().rstrip(".")
    if k == "resultado":
        run["resultado"] = valor
    elif k == "pasos":
        run["pasos"] = _int(valor)
    elif k == "insignias":
        run["insignias"] = _int(valor)
    elif k in ("capturas", "tutores", "objetos", "centros"):
        run[k] = _int(valor)
    elif k == "traza":
        run["traza_path"] = valor
    elif k == "equipo":
        m = re.match(r"(\d+)\s*\((\d+)-(\d+)\)", valor)
        if m:
            run["equipo_final"] = _int(m.group(1))
            run["equipo_final_rango"] = f"{m.group(2)}-{m.group(3)}"
    elif k == "combates":
        m = re.match(r"(\d+)\s*ganados\s*/\s*(\d+)\s*perdidos", valor)
        if m:
            run["combates_ganados"] = _int(m.group(1))
            run["combates_perdidos"] = _int(m.group(2))
    elif k == "peleas entrain":
        m = re.match(r"(\d+)\s*\(\+?(-?\d+)\s*nv\)", valor)
        if m:
            run["peleas_entrenador"] = _int(m.group(1))
            run["nv_entrenador"] = _int(m.group(2))
    elif k == "peleas salvaje":
        m = re.match(r"(\d+)\s*\(\+?(-?\d+)\s*nv\)", valor)
        if m:
            run["peleas_salvaje"] = _int(m.group(1))
            run["nv_salvaje"] = _int(m.group(2))


def _json_final(ruta: Path) -> dict:
    """El JSON estructurado con el que el bot cierra el log, si esta.

    Es la unica parte del log que ya viene en formato: resultado, region,
    pasos, insignias, equipo con nivel y PS, tipos y las ultimas decisiones.
    Vale mas parsearlo que rederivarlo de las lineas, y es lo que permite
    tener runs **sin bloque RESUMEN** (las que se matan a medias) con su
    resultado y su equipo final.
    """
    try:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for i in range(len(lineas) - 1, -1, -1):
        if lineas[i].strip() == "{":
            try:
                return json.loads("\n".join(lineas[i:]))
            except json.JSONDecodeError:
                return {}
    return {}


def construir(db: Path, logs: Path = LOGS) -> dict:
    """Construye (o rehace) la base de datos completa."""
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.executescript(ESQUEMA)
    cur = con.cursor()
    cont = {"runs": 0, "pasos": 0, "nodos": 0, "peleas": 0, "eventos": 0,
            "sondas": 0}
    # Dos sitios: los lotes en subcarpetas y los logs sueltos de arriba
    # (`log-<fecha>_<hora>_p<pid>.txt`). Los sueltos son runs que nunca se
    # archivaron en un lote; dejarlos fuera perdia 500 runs de un plumazo.
    rutas = sorted(logs.glob("*/*.txt")) + sorted(logs.glob("*.txt"))
    for ruta in rutas:
        p = parsear(ruta)
        run = p["run"]
        cols = list(run.keys())
        cur.execute(f"INSERT INTO run ({','.join(cols)}) "
                    f"VALUES ({','.join('?' * len(cols))})",
                    [run[k] for k in cols])
        rid = cur.lastrowid
        cont["runs"] += 1
        cur.executemany(
            "INSERT INTO paso (run_id,orden,paso,mapa,ins,disp,vivos,total,"
            "caidos,vida_media,vida,niveles,elige,peso) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(rid, x["orden"], x["paso"], x["mapa"], x["ins"], x["disp"],
              x["vivos"], x["total"], x["caidos"], x["vida_media"], x["vida"],
              x["niveles"], x["elige"], x["peso"]) for x in p["pasos"]])
        cont["pasos"] += len(p["pasos"])
        cur.executemany(
            "INSERT INTO nodo (run_id,orden,linea,mapa,nodo,tipo,crudo,equipo,"
            "vivos,niv_min,niv_max,insignias,disponibles,capturas_pantalla,"
            "razon,score,motivo,elige,ciudad,opc) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(rid, x["orden"], x["linea"], x["mapa"], x["nodo"], x["tipo"],
              x["crudo"], x["equipo"], x["vivos"], x["niv_min"], x["niv_max"],
              x["insignias"], x["disponibles"], x["capturas_pantalla"],
              x["razon"], x["score"], x["motivo"], x["elige"], x["ciudad"],
              x["opc"]) for x in p["nodos"]])
        cont["nodos"] += len(p["nodos"])
        cur.executemany(
            "INSERT INTO pelea (run_id,orden,linea,tipo,rival,nivel_min,"
            "nivel_max,insignias,nuestro_niv,rival_niv,nuestros,suyo,enemigos,"
            "mios,enemigos_n,mios_n,mios_ps_total,resultado,continuamos_en,"
            "rival_perdido,nos_quedan,marcador_a,marcador_b,ps_abre_total,"
            "ps_abre_equipo,ps_cierra_total,ps_cierra_equipo) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(rid, x["orden"], x["linea"], x["tipo"], x["rival"],
              x["nivel_min"], x["nivel_max"], x["insignias"], x["nuestro_niv"],
              x["rival_niv"], x["nuestros"], x["suyo"], x["enemigos"],
              x["mios"], x["enemigos_n"], x["mios_n"], x["mios_ps_total"],
              x["resultado"], x["continuamos_en"], x["rival_perdido"],
              x["nos_quedan"], x["marcador_a"], x["marcador_b"],
              x["ps_abre_total"], x["ps_abre_equipo"], x["ps_cierra_total"],
              x["ps_cierra_equipo"]) for x in p["peleas"]])
        cont["peleas"] += len(p["peleas"])
        cur.executemany(
            "INSERT INTO evento (run_id,orden,linea,hora,tipo,clave,valor,cola,"
            "crudo) VALUES (?,?,?,?,?,?,?,?,?)",
            [(rid, x["orden"], x["linea"], x.get("hora"), x["tipo"],
              x.get("clave"), x.get("valor"), x.get("cola"), x["crudo"])
             for x in p["eventos"]])
        cont["eventos"] += len(p["eventos"])

    # La sonda de DOM, si la hay, se mete aparte: no sale del log.
    sonda_dir = Path(os.environ.get("PKL_SONDA_DOM") or "/tmp/opencode/sonda")
    if sonda_dir.exists():
        for f in sorted(sonda_dir.glob("*.jsonl")):
            for ln in f.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                cur.execute(
                    "INSERT INTO sonda (run_id,etiqueta,paso,pantalla,hora,"
                    "barra,lado,enemigos,barra_html,lado_html) VALUES "
                    "(?,?,?,?,?,?,?,?,?,?)",
                    (None, r.get("etiqueta"), r.get("paso"), r.get("pantalla"),
                     r.get("hora"),
                     json.dumps(r.get("barra"), ensure_ascii=False),
                     json.dumps(r.get("lado"), ensure_ascii=False),
                     json.dumps(r.get("enemigos"), ensure_ascii=False),
                     r.get("barra_html"), r.get("lado_html")))
                cont["sondas"] += 1

    con.commit()
    con.close()
    return cont


def main() -> int:
    ap = argparse.ArgumentParser(description="Logs de Pokelike -> SQLite.")
    ap.add_argument("--db", type=Path, default=DB_POR_DEFECTO)
    ap.add_argument("--logs", type=Path, default=LOGS)
    a = ap.parse_args()
    c = construir(a.db, a.logs)
    print(f"corpus en {a.db}")
    for k, v in c.items():
        print(f"   {k:<8}{v:>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

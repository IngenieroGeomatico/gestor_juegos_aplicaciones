#!/usr/bin/env python3
"""Recolecta resultados de las partidas y responde a las hipótesis.

Solo mira logs: no lanza nada. Se ejecuta mientras las runs van por su cuenta y
va rellenando HIPOTESIS.md con los numeros reales.

    uv run --group dev python juegos/pokelike/scripts/medir_hipotesis.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

LOGS = Path("juegos/pokelike/log")
DATOS = Path("juegos/pokelike/data/medidas.json")

RE_PERDIDA = re.compile(r"COMBATE PERDIDO contra (.+?)\s*\|")
RE_MIOS = re.compile(r"mios=\[(.*)\]\s*$")
RE_ENEMIGOS = re.compile(r"enemigos=\[(.*)\]\s*$")
RE_MAP = re.compile(
    r"·\s*(?P<ruta>[^:]+):\s*vs\s+(?P<lider>[^(]+)\((?P<tipo>[^)]+)\)\s*\|"
    r"\s*equipo (?P<n>\d+) \(vivos (?P<vivos>\d+)\)"
    r"\s*niv (?P<lo>\d+)-(?P<hi>\d+).*?insignias (?P<ins>\d+)")
RE_OBJ = re.compile(r"objeto (EQUIPADO|NO usado) -> (\w+): (.{0,40})")
RE_TRADE = re.compile(r"trade: se ofrece (\w+)")
# El resumen son TRES lineas sueltas, no una:
#   resultado : GAME_OVER
#   pasos     : 16
#   insignias : 0
RE_RESULTADO = re.compile(r"resultado\s*:\s*(\S+)")
RE_PASOS = re.compile(r"\bpasos\s*:\s*(\d+)")
RE_INSIG = re.compile(r"\binsignias\s*:\s*(\d+)")
RE_MUERTOS = re.compile(r"vivos (\d+) niv")


def nivel_de(entrada: str) -> int:
    """`('Bulbasaur Lv5', '19/19', '5')` -> 5"""
    m = re.findall(r"'(\d+)'", entrada)
    return int(m[-1]) if m else 0


def ps_de(entrada: str) -> float:
    """`('Bulbasaur Lv5', '19/19', '5')` -> 1.0 (proporción)"""
    m = re.findall(r"'(\d+)/(\d+)'", entrada)
    if not m:
        return 0.0
    a, b = m[0]
    return int(a) / max(int(b), 1)


def analizar(log: Path) -> dict:
    d = {"log": log.name, "resultado": None, "pasos": 0, "insignias": 0,
         "victorias_gimnasio": 0, "derrotas": [], "objetos_ok": 0,
         "objetos_fallo": 0, "trades": 0, "niveles_entrada": []}
    lineas = log.read_text(encoding="utf-8", errors="replace").splitlines()
    estado = None
    for ln in lineas:
        m = RE_MAP.search(ln)
        if m:
            estado = {
                "ruta": m.group("ruta").strip(), "lider": m.group("lider").strip(),
                "tipo": m.group("tipo").strip(), "n": int(m.group("n")),
                "vivos": int(m.group("vivos")),
                "lo": int(m.group("lo")), "hi": int(m.group("hi")),
                "insignias": int(m.group("ins")),
            }
            d["niveles_entrada"].append(estado)
        m = RE_OBJ.search(ln)
        if m:
            d["objetos_ok" if m.group(1) == "EQUIPADO" else "objetos_fallo"] += 1
        if RE_TRADE.search(ln):
            d["trades"] += 1
        m = RE_PERDIDA.search(ln)
        if m:
            rival = m.group(1).strip()
            d["derrotas"].append({"rival": rival, "nivel": estado})
        m = RE_RESULTADO.search(ln)
        if m:
            d["resultado"] = m.group(1)
        m = RE_PASOS.search(ln)
        if m:
            d["pasos"] = int(m.group(1))
        m = RE_INSIG.search(ln)
        if m:
            d["insignias"] = int(m.group(1))
    return d


def cargar() -> dict:
    if DATOS.exists():
        return json.loads(DATOS.read_text(encoding="utf-8"))
    return {"partidas": {}}


# --------------------------------------------------------------------------
# Veredictos. Cada hipotesis de HIPOTESIS.md tiene aqui su medida y su
# criterio, para que se resuelvan solas segun se acumulen partidas.
# --------------------------------------------------------------------------

# Niveles que impone el juego por gimnasio de Kanto, extraidos del juego.
LISTON = {0: 12, 1: 18, 2: 25, 3: 32, 4: 44, 5: 44, 6: 53, 7: 60}


def veredictos(datos: dict) -> str:
    ps = [p for p in datos["partidas"].values()
          if p.get("resultado") not in (None, "EN_CURSO")]
    out = [f"partidas terminadas: {len(ps)}"]

    # H1: diferencia de nivel en la derrota.
    difs = []
    for p in ps:
        for d in p.get("derrotas") or []:
            n = d.get("nivel")
            if not n:
                continue
            rival = d.get("rival", "")
            # El rival de gimnasio trae "Gym Battle"; el resto son de ruta.
            if "Gym" in rival:
                # El liston va por insignias. Antes se usaba el numero de mons
                # del equipo como indice y salia un "-17" sin sentido.
                difs.append(n["lo"] - LISTON.get(n.get("insignias", 0), 12))
    if difs:
        media = sum(difs) / len(difs)
        out.append(f"H1 diferencia de nivel al entrar en gimnasio: "
                   f"media {media:+.1f}, min {min(difs)}, max {max(difs)} "
                   f"({len(difs)} derrotas en gimnasio)")
        out.append("  -> CONFIRMADA (>=3 por debajo)" if media <= -3 else
                   "  -> RECHAZADA, se pierde por otra cosa" if media > -2 else
                   "  -> INCONCLUSA (entre -2 y -3)")
    else:
        out.append("H1 sin datos: todavia no se ha perdido en un gimnasio")

    # H2/H3/H4: estado del equipo en cada entrada a mapa con jefe a la vista.
    entradas = [n for p in ps for n in p.get("niveles_entrada") or []]
    if entradas:
        # "con jefe a la vista" = insignias < 8, o sea todavia queda gimnasio.
        con_jefe = [n for n in entradas if n.get("insignias", 0) < 8]
        flojos = [n for n in con_jefe if n.get("vivos", 9) <= 1]
        if con_jefe:
            out.append(f"H4 entrada con 1 solo vivo: {len(flojos)} de "
                       f"{len(con_jefe)} mapas con jefe a la vista")
        bajos = [n for n in con_jefe
                 if n.get("lo", 99) < LISTON.get(n.get("insignias", 0), 12)]
        if con_jefe:
            out.append(f"H1/H2 llega bajo el liston en {len(bajos)} de "
                       f"{len(con_jefe)} entradas con jefe a la vista")

    # H5: objetos.
    ok = sum(p.get("objetos_ok", 0) for p in ps)
    mal = sum(p.get("objetos_fallo", 0) for p in ps)
    out.append(f"H5 objetos: {ok} equipados, {mal} fallidos "
               f"({'flujo OK' if ok else 'el flujo sigue roto'})")

    # H6: trades.
    tr = sum(p.get("trades", 0) for p in ps)
    out.append(f"H6 trades vistos: {tr} "
               f"({'se alcanzan' if tr else 'ningunoTodavia'})")

    # Media de insignias.
    if ps:
        media_ins = sum(p.get("insignias", 0) for p in ps) / len(ps)
        mejor = max(p.get("insignias", 0) for p in ps)
        out.append(f"resultado: media {media_ins:.2f} insignias, mejor {mejor}")
    return "\n".join(out)


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    datos = cargar()
    nuevos = 0
    for log in sorted(LOGS.glob("log-*.txt")):
        if log.name in datos["partidas"]:
            continue
        try:
            datos["partidas"][log.name] = analizar(log)
            nuevos += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  no se pudo leer {log.name}: {exc}")
    DATOS.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"partidas registradas: {len(datos['partidas'])} (+{nuevos} nuevas)")
    print(veredictos(datos))
    return 0


if __name__ == "__main__":
    sys.exit(main())

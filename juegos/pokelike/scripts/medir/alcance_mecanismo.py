#!/usr/bin/env python3
"""Mide en quantas runs dispara un mecanismo, ANTES de lanzar su A/B.

La regla del cuaderno (09-10): **por debajo del 15% no se lanza, porque no hay
potencia**. El calculo sale en minutos sobre logs que ya existen y es el mismo
que habria evitado H17, H18 y las dos noches.

    uv run --group dev python juegos/pokelike/scripts/medir/alcance_mecanismo.py

Solo mira logs. No lanza nada.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

LOGS = Path("juegos/pokelike/log")

# Cada mecanismo que se ha querido testear, con el marcador que lo delata en el
# log. Si el marcador no sale, el flag no llego y las insignias no significan
# nada: por eso esto va antes que cualquier comparacion de brazos.
MARCADORES: dict[str, re.Pattern[str]] = {
    "reroll por jefe sin exp": re.compile(r"reroll del mapa \(\d+/3\)"),
    "busqueda de trade (tecla r)": re.compile(r"buscando trade \(intento"),
    "veto de entrenador por nivel": re.compile(r"entrenador vetado: rival"),
    "entrenador de riesgo": re.compile(r"entrenador de riesgo:"),
    "captura por nivel (H17)": re.compile(r"cazar \d+ nivel\(es\) por encima"),
    "captura por equipo corto": re.compile(r"capturar: equipo de \d+"),
    "cura en camino al jefe": re.compile(r"curar: paso obligatorio hacia el jefe"),
    "H19 no gasta presupuesto": re.compile(r"H19: NO se gasta presupuesto"),
    "PESO_OBJETO (flag item_huecos)": re.compile(r"objeto: hay hueco.*prioridad"),
}

# La misma decision, leida por el lado del nodo que el planner eligio.
RE_DEC = re.compile(r"DEC nodo .*? (\w+) score=")
RE_TRAZA = re.compile(
    r"TRAZA_CAMINO paso=(\d+).*?vivos=(\d+)/(\d+) caidos=(\d+) vida_media=(\d+)%")


def medir(log: Path) -> dict:
    txt = log.read_text(encoding="utf-8", errors="replace")
    d: dict = {"mecanismos": [], "elecciones": Counter(), "n_pasos": 0,
               "trazas": []}
    for nombre, rx in MARCADORES.items():
        if rx.search(txt):
            d["mecanismos"].append(nombre)
    for m in RE_DEC.finditer(txt):
        d["elecciones"][m.group(1)] += 1
    for m in RE_TRAZA.finditer(txt):
        d["n_pasos"] = max(d["n_pasos"], int(m.group(1)))
        d["trazas"].append({
            "vivos": int(m.group(2)), "n": int(m.group(3)),
            "caidos": int(m.group(4)), "vida": int(m.group(5)) / 100,
        })
    return d


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    logs = sorted(p for p in LOGS.rglob("h1[5-9]-*.txt"))
    if not logs:
        logs = sorted(LOGS.rglob("*.txt"))
    if not logs:
        print("no hay runs que medir")
        return 0

    runs = [medir(p) for p in logs]
    n = len(runs)
    print(f"runs con traza: {n}\n")

    print("== ALCANCE DE CADA MECANISMO (regla: por debajo del 15% no se lanza) ==")
    for nombre in MARCADORES:
        k = sum(1 for r in runs if nombre in r["mecanismos"])
        pct = 100 * k / n
        marca = "NO SE LANZA" if pct < 15 else "lanzable"
        print(f"  {nombre:34s} {k:4d}/{n}  {pct:5.1f}%  {marca}")

    print("\n== REPARTO DE DECISIONES (que elige el bot, no que hay en pantalla) ==")
    tot = sum(sum(r["elecciones"].values()) for r in runs) or 1
    todos: Counter = Counter()
    for r in runs:
        todos.update(r["elecciones"])
    for tipo, k in todos.most_common():
        print(f"  {tipo:12s} {k:6d}  {100*k/tot:5.1f}%")

    print("\n== ESTADO DEL EQUIPO EN CADA PASO DE MAPA ==")
    t = [x for r in runs for x in r["trazas"]]
    if t:
        caidos = [x for x in t if x["caidos"] > 0]
        vida_baja = [x for x in t if x["vida"] <= 0.75]
        print(f"  pasos con traza        : {len(t)}")
        print(f"  ...con algun caido     : {len(caidos):5d}  {100*len(caidos)/len(t):5.1f}%")
        print(f"  ...con vida <= 75%     : {len(vida_baja):5d}  {100*len(vida_baja)/len(t):5.1f}%")
        print(f"  vida media             : {sum(x['vida'] for x in t)/len(t):5.1%}")
        print(f"  pasos medios por run   : {len(t)/n:5.1f}")

    print("\n== INSIGNIAS ==")
    ins = []
    for p in logs:
        m = re.search(r"^\s*insignias\s*:\s*(\d+)", p.read_text(
            encoding="utf-8", errors="replace"), re.MULTILINE)
        res = re.search(r'resultado"\s*:\s*"(\w+)"', p.read_text(
            encoding="utf-8", errors="replace"))
        if m:
            ins.append(int(m.group(1)))
        if res and res.group(1) == "CHAMPION":
            print(f"  CHAMPION en {p.name}")
    if ins:
        print(f"  media {sum(ins)/len(ins):.2f}  max {max(ins)}  n={len(ins)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
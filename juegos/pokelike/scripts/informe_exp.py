#!/usr/bin/env python3
"""Informe de avance del experimento de 3 brazos. Solo lee, no lanza.

    uv run --group dev python juegos/pokelike/scripts/informe_exp.py

Dice cuantos lleva de cada brazo, cuantos timeouts ha habido, y cuando toca
el proximo informe de 10. Los timeouts cuentan como fracasos.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
LOGS = RAIZ / "juegos/pokelike/log"
TIEMPOS = Path("/tmp/opencode/exp3_tiempos.log")
PAT_BRAZO = re.compile(r"brazo=([\w-]+)")
RE_RES = re.compile(r"resultado\s*:\s*(\S+)")
RE_INS = re.compile(r"insignias\s*:\s*(\d+)")
RE_PAS = re.compile(r"pasos\s*:\s*(\d+)")
OBJETIVO = 50


def main() -> int:
    brazos: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "gym": 0, "ins": [], "pas": [], "cont": []})
    for log in sorted(LOGS.glob("log-*.txt")):
        txt = log.read_text(encoding="utf-8", errors="ignore")
        m = PAT_BRAZO.search(txt)
        if not m:
            continue
        b = m.group(1)
        d = brazos[b]
        d["n"] += 1
        # una pantalla de batalla que no avanza mucho tiempo es sintoma de bucle
        d["cont"].append(txt.count("[continuar -> True]"))
        if "Gym Battle vs" in txt:
            d["gym"] += 1
        if "RESUMEN" in txt:
            bloque = txt[txt.rindex("RESUMEN"):]
            g = RE_INS.search(bloque)
            p = RE_PAS.search(bloque)
            if g:
                d["ins"].append(int(g.group(1)))
            if p:
                d["pas"].append(int(p.group(1)))
    if not brazos:
        print("todavia no hay runs con etiqueta de brazo")
        return 1

    timeouts: dict[str, int] = defaultdict(int)
    if TIEMPOS.exists():
        for linea in TIEMPOS.read_text(encoding="utf-8").splitlines():
            p = linea.split()
            if len(p) == 3 and p[2] == "timeout":
                timeouts[p[0]] += 1

    print(f"{'brazo':20} {'n':>4} {'gym':>8} {'ins':>6} {'pas':>6} "
          f"{'bucle':>6} {'timeout':>8}")
    total = 0
    for b in sorted(brazos):
        d = brazos[b]
        n = d["n"]
        total += n
        gym = f"{d['gym']}/{n}" + (f" {100*d['gym']//max(n,1)}%" if n else "")
        ins = sum(d["ins"]) / len(d["ins"]) if d["ins"] else float("nan")
        pas = sum(d["pas"]) / len(d["pas"]) if d["pas"] else float("nan")
        bucles = sum(1 for c in d["cont"] if c >= 40)
        print(f"  {b:18} {n:4} {gym:>8} {ins:6.2f} {pas:6.0f} "
              f"{bucles:6} {timeouts[b]:8}")
    print(f"\n  total {total}/150  |  faltan {150 - total}")

    siguiente = (total // 10 + 1) * 10
    if siguiente > 150:
        siguiente = 150
    faltan_brazo = [b for b in brazos if brazos[b]["n"] < OBJETIVO]
    print(f"  proximo informe: en la run {siguiente}"
          f"  |  brazos por debajo de {OBJETIVO}: "
          f"{', '.join(sorted(faltan_brazo)) if faltan_brazo else 'ninguno'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
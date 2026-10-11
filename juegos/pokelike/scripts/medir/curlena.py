"""¿El pokecentro cura al 100% o solo lo que ve?

Si cura a tope y el equipo aun asi sale gastado, el cuello NO es una decision
de politica y no queda nada que declarar. Si cura menos, si.

Emparejamiento por bloques (nunca por indice de linea, §5.8): cada
TRAZA_CAMINO va seguida de su DEC nodo. Si el nodo elegido es `cura`, la
vida de esa traza es la de ANTES de curar, y la vida de la traza siguiente
la de DESPUES.

    uv run --group dev python juegos/pokelike/scripts/medir/curlena.py
"""
from __future__ import annotations

import re
import statistics as st
from collections import Counter
from pathlib import Path

# `scripts/medir/` esta cuatro niveles por debajo de la raiz del repo.
RAIZ = Path(__file__).resolve().parents[4]
LOGS = RAIZ / "juegos/pokelike/log"

TR = re.compile(r"TRAZA_CAMINO paso=(\d+) .*?vivos=(\d+)/(\d+) caidos=(\d+) "
                r"vida_media=(\d+)% vida=\[([^\]]*)\]")
DEC = re.compile(r"DEC nodo .*?tipo=(\w+)")


def pasos_de(ls):
    """[(linea, vida_media, caidos, n_nodos, dict_vida)] de cada traza."""
    out = []
    for i, ln in enumerate(ls):
        m = TR.search(ln)
        if not m:
            continue
        vida = {}
        for trozo in m.group(6).split(","):
            if ":" in trozo:
                nom, pct = trozo.split(":")
                vida[nom.strip().strip("'")] = int(re.sub(r"[^0-9]", "", pct))
        out.append((i, int(m.group(5)), int(m.group(4)),
                    len(vida), vida))
    return out


def main() -> int:
    antes, despues, ceros_antes, ceros_despues = [], [], 0, 0
    por_run = []
    n_curas = 0

    for p in sorted(LOGS.glob("*/*.txt")):
        try:
            ls = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        pasos = pasos_de(ls)
        for k, (i, vida, caidos, _n, vdict) in enumerate(pasos):
            # el nodo elegido en esta pantalla
            tipo = None
            for x in ls[i:i + 8]:
                d = DEC.search(x)
                if d:
                    tipo = d.group(1)
                    break
            if tipo != "cura":
                continue
            n_curas += 1
            antes.append(vida)
            ceros_antes += sum(1 for v in vdict.values() if v <= 0)
            if k + 1 < len(pasos):
                despues.append(pasos[k + 1][1])
                ceros_despues += sum(1 for v in pasos[k + 1][4].values() if v <= 0)
                por_run.append((vida, pasos[k + 1][1]))

    print(f"pantallas que eligieron pokecentro: {n_curas}")
    if not (antes and despues):
        print("sin datos suficientes")
        return 0

    print(f"\nvida del equipo ANTES de curar:   mediana {st.median(antes):5.0f}%  "
          f"media {st.mean(antes):5.1f}%")
    print(f"vida del equipo DESPUES de curar:  mediana {st.median(despues):5.0f}%  "
          f"media {st.mean(despues):5.1f}%")
    print(f"\nmóns a 0 antes de curar:   {ceros_antes}")
    print(f"móns a 0 despues de curar: {ceros_despues}")

    print("\nreparto de la vida DESPUES de curar (todos los pasos):")
    c = Counter(despues)
    for k in sorted(c):
        print(f"   {k:>3}%  {c[k]:>4}  ({100 * c[k] / len(despues):5.1f}%)")

    print("\nreparto de la vida DESPUES de curar, solo cuando HABIA un 0 antes:")
    d2 = [d for a, d in por_run if a < 100]
    c2 = Counter(d2)
    for k in sorted(c2):
        if k <= 20 or k >= 90:
            print(f"   {k:>3}%  {c2[k]:>4}  ({100 * c2[k] / len(d2):5.1f}%)")
    if d2:
        print(f"   mediana en ese subconjunto: {st.median(d2):.0f}%")

    med = st.median(despues)
    print(f"\nVEREDICTO: mediana tras curar = {med:.0f}%  ->",
          "cura a TOPE" if med >= 95 else f"NO llega a tope, se queda en {med:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""¿De qué se compone el tramo entre el pokecentro y el gimnasio?

Contesta a la pregunta que decide si hay intervencion posible: **entre la
ultima curacion y la pelea de jefe, ¿el bot puede elegir?**

Salida: cuantas pantallas hay, que nodo ofrece cada una y cuantos nodos
ofrece la pantalla intermedia. Solo lee logs.

    uv run --group dev python juegos/pokelike/scripts/medir/tramo_al_jefe.py
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

# `scripts/medir/` esta dos niveles por debajo de la raiz del repo.
RAIZ = Path(__file__).resolve().parents[4]
LOGS = RAIZ / "juegos/pokelike/log"

pat_dec = re.compile(r"DEC nodo .*?tipo=(\w+) .*?disponibles=([a-z_,]+)")
pat_gym = re.compile(r"^\s*estado: Gym Battle vs")


def main() -> int:
    pantallas_entre = Counter()
    nodo_primera = Counter()
    opciones = Counter()
    total = 0

    for p in sorted(LOGS.glob("*/*.txt")):
        try:
            ls = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        eventos: list[tuple[int, str, str]] = []
        for i, ln in enumerate(ls):
            d = pat_dec.search(ln)
            if d:
                eventos.append((i, d.group(1), d.group(2)))
            if not pat_gym.match(ln):
                continue
            curas = [e for e in eventos if e[1] == "cura"]
            if not curas:
                continue
            ultimo = curas[-1][0]
            entre = [e for e in eventos if e[0] > ultimo]
            if not entre:
                continue
            total += 1
            pantallas_entre[len(entre)] += 1
            nodo_primera[entre[0][1]] += 1
            opciones[len(entre[0][2].split(","))] += 1

    if not total:
        print("sin peleas de gimnasio con un pokecentro anterior")
        return 0

    print(f"peleas de gimnasio con un pokecentro antes: {total}\n")
    print("PANTALLAS entre el ultimo pokecentro y la pelea de gimnasio:")
    for k in sorted(pantallas_entre):
        if k <= 5:
            print(f"   {k} pantalla(s): {pantallas_entre[k]:>5}")
    print("\nQUE HABIA en la primera pantalla tras el pokecentro:")
    for k, v in nodo_primera.most_common(6):
        print(f"   {k:<12} {v:>5}")
    print("\nCUANTOS NODOS ofrecía esa pantalla:")
    tot = sum(opciones.values())
    for k in sorted(opciones):
        print(f"   {k} nodo(s): {opciones[k]:>5}  ({100 * opciones[k] / tot:5.1f}%)")
    unico = 100 * opciones.get(1, 0) / tot
    print(f"\nVEREDICTO: en el {unico:.0f}% de los casos habia UN SOLO nodo.")
    print("Si era el jefe, no habia decision que tomar y la politica no tiene")
    print("nada que hacer ahi: la pelea se entra porque es lo unico que hay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

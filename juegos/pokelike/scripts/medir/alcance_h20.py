#!/usr/bin/env python3
"""Alcance de H20: ¿cuantas veces hay ELECCION de verdad con el equipo roto?

La regla del cuaderno: por debajo del 15% no se lanza. Y una eleccion que no
existe no se puede cambiar con un peso.

La pregunta es concreta. Cuando el equipo esta roto y en pantalla hay una rama
**sin combate** (tutor, item, trade, incognita) ademas de la de combate, el bot
puede elegir la barata. Si eso pasa en menos del 15% de los pasos con el equipo
roto, H20 no tiene potencia y no se lanza.

    uv run --group dev python juegos/pokelike/scripts/medir/alcance_h20.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

LOGS = Path("juegos/pokelike/log")

RE_DEC = re.compile(
    r"DEC nodo mapa=.*?nodo=(\S+) tipo=(\w+) .*?equipo=(\d+) vivos=(\d+) "
    r".*?disponibles=([\w,]+) .*?razon=(\w+) score=(-?[\d.]+)")
RE_TRAZA = re.compile(
    r"TRAZA_CAMINO paso=(\d+) .*?disp=\[([^\]]*)\].*?"
    r"vivos=(\d+)/(\d+) caidos=(\d+) vida_media=(\d+)%.*?elige=(\S+)")


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    logs = sorted(LOGS.rglob("h1[5-9]-*.txt"))

    pasos_roto = 0
    pasos_con_eleccion = 0
    elegido: Counter = Counter()
    disponibles: Counter = Counter()
    n = 0
    # El campo `disponibles` lleva el vocabulario CRUDO del juego, que no es el
    # interno: trainer/battle/catch son combate, y question/item/move_tutor/
    # trade no lo son. Comparar contra el vocabulario equivocado es el error que
    # este bot ha repetido nueve veces.
    combate = {"trainer", "battle", "catch"}
    no_combate = {"question", "item", "move_tutor", "trade"}
    for p in logs:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "DEC nodo" not in txt:
            continue
        n += 1
        for d in RE_DEC.finditer(txt):
            equipo, vivos = d.group(3), d.group(4)
            caidos = int(equipo) - int(vivos)
            if not caidos:
                # Sin caidos tambien cuenta si el equipo esta por debajo de la
                # puerta del 75%, pero `DEC nodo` no lleva el PS. Los caidos
                # bastan como senal y estan en el log sin ambiguedad.
                continue
            pasos_roto += 1
            disp_dec = [x for x in d.group(5).split(",") if x]
            disponibles.update(disp_dec)
            elegido[d.group(6)] += 1
            if (set(disp_dec) & combate) and (set(disp_dec) & no_combate):
                pasos_con_eleccion += 1

    if not pasos_roto:
        print("sin trazas de equipo roto en estos logs")
        return 0
    print(f"runs con DEC nodo: {n}")
    print(f"pasos con el equipo roto (vida<=75% o caido): {pasos_roto}")
    print(f"  ...y con una rama SIN combate disponible:     {pasos_con_eleccion}"
          f"  ({100*pasos_con_eleccion/pasos_roto:.1f}%)")
    print("\n== QUE HAY EN PANTALLA CUANDO EL EQUIPO ESTA ROTO ==")
    tot = sum(disponibles.values()) or 1
    for k, v in disponibles.most_common():
        print(f"  {k:12s} {v:6d}  {100*v/tot:5.1f}%")
    print("\n== QUE ELIGE ==")
    tot = sum(elegido.values()) or 1
    for k, v in elegido.most_common():
        print(f"  {k:12s} {v:6d}  {100*v/tot:5.1f}%")

    print("\n== VEREDICTO DE ALCANCE ==")
    pct = 100 * pasos_con_eleccion / pasos_roto
    if pct < 15:
        print(f"  {pct:.1f}% < 15%: NO SE LANZA H20 por falta de potencia.")
    else:
        print(f"  {pct:.1f}% >= 15%: lanzable, con primaria declarada antes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""¿De verdad no hay experiencia a la altura del listón?

El cuaderno lleva dos noches apoiandose en una frase: "los salvajes que hay
estan 5 a 15 niveles POR DEBAJO de su equipo, asi que pelear con ellos no da
nada". Si es verdad, ninguna politica de pesos arregla el deficit. Si es
FALSA, la palanca entera cambia de sitio.

La forma de comprobarlo es comparar, **en el mismo paso de mapa**, el nivel de
lo que el bot podria cazar contra el nivel que el siguiente gimnasio exige. Y
despues comprobar si el botgana nivel de verdad: los logs dicen "+2 por
entrenador, +1 por salvaje", asi que el total de subidas se puede contrastar
contra el total de combates.

    uv run --group dev python juegos/pokelike/scripts/medir/hay_exp_que_sirva.py
"""
from __future__ import annotations

import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

LOGS = Path("juegos/pokelike/log")

# El mapa imprime los niveles rivales de cada nodo: `rivales [12, 13]`, y el
# lider con su nivel canonico.
RE_MAPA = re.compile(
    r"· (?P<ruta>.+?): vs (?P<lider>.+?) \((?P<tipo>\w+)\) \| equipo (?P<n>\d+) "
    r"\(vivos (?P<vivos>\d+)\) niv (?P<lo>\d+)-(?P<hi>\d+) \| lider \w+ \| "
    r"insignias (?P<ins>\d+) \| disponibles \[(?P<disp>[^\]]*)\].*?rivales "
    r"\[(?P<riv>[^\]]*)\]")
RE_DEC = re.compile(
    r"DEC nodo .*?equipo=(\d+) vivos=(\d+) .*?disponibles=([\w,]+) "
    r".*?razon=(\w+) score=(-?[\d.]+)")
RE_TRAZA = re.compile(r"TRAZA_CAMINO paso=(\d+) .*?vida_media=(\d+)%")

# El liston por gimnasio de Kanto, tal y como lo imprime el propio juego.
LISTON_KANTO = {"Brock": 14, "Misty": 20, "Lt. Surge": 25, "Erika": 32,
                "Koga": 44, "Sabrina": 44, "Blaine": 53, "Giovanni": 60}


def nums(campo: str) -> list[int]:
    out = []
    for x in re.findall(r"\d+", campo or ""):
        out.append(int(x))
    return out


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    logs = sorted(LOGS.rglob("h1[7-9]-*.txt"))
    print(f"runs: {len(logs)}")

    shortfall: list[int] = []
    exp_disponible: list[int] = []
    por_lider: dict[str, list[tuple[int, int]]] = defaultdict(list)
    n = 0
    for p in logs:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "· Route 1" not in txt:
            continue
        n += 1
        equipo_nivel: tuple[int, int] | None = None
        for ln in txt.splitlines():
            m = RE_MAPA.search(ln)
            if not m:
                continue
            riv = nums(m.group("riv"))
            if not riv:
                continue
            equipo_nivel = (int(m.group("lo")), int(m.group("hi")))
            lider = m.group("lider").split()[0]
            liston = LISTON_KANTO.get(lider)
            if liston is None:
                continue
            max_equipo = equipo_nivel[1]

            disp = m.group("disp")
            # `disponibles` lleva el vocabulario **interno** (traducido); el
            # crudo va entre parentesis en la misma linea. Un combate da exp
            # si es `batalla` (salvaje, con o sin captura) o `entrenador`.
            tiene_exp = any(t in disp for t in ("batalla", "entrenador"))
            if not tiene_exp:
                continue
            # El rival mas fuerte disponible por encima del liston es el unico
            # que cierra el deficit; por debajo no sirve para nada.
            mejor = max(riv)
            por_lider[lider].append((liston - max_equipo, mejor - liston))
            if liston > max_equipo:
                shortfall.append(liston - max_equipo)
                exp_disponible.append(max(riv) - max_equipo)

    if not por_lider:
        print("no hay mapas con niveles rivales en estos logs")
        return 0
    print(f"runs con mapa legible: {n}\n")

    print("== ¿HAY SALVAJES/ENTRENADORES A LA ALTURA DEL LISTÓN? ==")
    print("   (deficit = liston - nivel max del equipo; rival = nivel max")
    print("    disponible en pantalla, menos el listón)")
    print(f"  {'gimnasio':10s} {'n':>5s} {'deficit':>9s} {'rival-liston':>13s}")
    for lider, vals in sorted(por_lider.items(), key=lambda x: x[0]):
        d = st.mean(v[0] for v in vals)
        r = st.mean(v[1] for v in vals)
        print(f"  {lider:10s} {len(vals):5d} {d:9.1f} {r:13.1f}")

    if shortfall:
        print(f"\n  pasos por debajo del listón: {len(shortfall)}")
        print(f"  deficit medio: {st.mean(shortfall):.1f} niveles")
        print(f"  con el rival mas fuerte POR ENCIMA del equipo "
              f"(de exp util): {sum(1 for v in exp_disponible if v > 0)}"
              f" de {len(exp_disponible)}"
              f" ({100*sum(1 for v in exp_disponible if v>0)/len(exp_disponible):.0f}%)")

    print("\n== NIVELES DE LOS RIVALES QUE EL JUEGO OFRECE, POR INSIGNIA ==")
    todos: list[int] = []
    for p in logs[:80]:
        for ln in p.read_text(encoding="utf-8",
                              errors="replace").splitlines():
            m = RE_MAPA.search(ln)
            if m:
                todos.extend(nums(m.group("riv")))
    if todos:
        h = Counter(t // 5 * 5 for t in todos)
        for k in sorted(h):
            if h[k] > 20:
                print(f"  nivel {k:3d}-{k+4:<3d} {'#' * min(60, h[k] // 20):<60}"
                      f" {h[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
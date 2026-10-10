"""¿Qué separa ganar de perder: la vida MEDIA o tener un món a 0?

Contesta a la pregunta que §1.1 dio por resuelta con 934 peleas de un solo
lote, con **1.229 peleas de todo el corpus** y el PS real de **cada món**.

La clave es que la media del equipo es una mala estadística: con cinco móns
llenos y uno a 5/23 la media sale alta, y la pelea está perdida igual. Por
eso se separa por número de caídos, que es lo que el corte de emergencia
del bot ya mira (`caidos >= 1`).

Se ejecuta mientras corre un lote: **solo lee logs**.

    uv run --group dev python juegos/pokelike/scripts/medir/cuello_caido.py
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

# `scripts/medir/` son dos niveles por debajo de la raiz del repo: `juegos/pokelike/scripts/medir`. Con `parents[3]` salia a `juegos/` y el directorio no existia.
RAIZ = Path(__file__).resolve().parents[4]
LOGS = RAIZ / "juegos/pokelike/log"

pat_gym = re.compile(r"^\s*estado: Gym Battle vs (.+?)! \| niveles rivales")
pat_mios = re.compile(r"mios=\[(.*?)\]")
pat_mio = re.compile(r"'([^']+?)\s*Lv(\d+)',\s*'(\d+)/(\d+)'")
pat_out = re.compile(r">>> COMBATE (GANADO|PERDIDO)")


def peleas() -> list[tuple[int, int, int, int, int]]:
    """(media, minimo, maximo, caidos, gana) por pelea de gimnasio."""
    out = []
    for p in sorted(LOGS.glob("*/*.txt")):
        try:
            ls = p.read_text(encoding="utf-8",
                             errors="replace").splitlines()
        except OSError:
            continue
        for i, ln in enumerate(ls):
            if not pat_gym.match(ln):
                continue
            # **Bloque, no indice de linea**: se lee desde la linea del
            # gimnasio hasta el desenlace. Emparejar por posicion ya salio
            # mal varias veces en este repo (§5.8).
            vida = None
            res = None
            for l2 in ls[i + 1:i + 14]:
                if vida is None:
                    m = pat_mios.search(l2)
                    if m:
                        rr = [int(ps) * 100 // int(mx)
                              for _n, _l, ps, mx in pat_mio.findall(m.group(1))
                              if int(mx) > 0]
                        if rr:
                            vida = rr
                o = pat_out.search(l2)
                if o:
                    res = int(o.group(1) == "GANADO")
                    break
            if not vida or res is None:
                continue
            vivos = [v for v in vida if v > 0]
            out.append((sum(vida) // len(vida), min(vida), max(vida),
                        sum(1 for v in vida if v <= 0), res))
    return out


def _pct(v):
    return f"{100 * v:5.1f}%"


def main() -> int:
    filas = peleas()
    if not filas:
        print("sin peleas de gimnasio con PS real")
        return 0
    print(f"peleas de gimnasio con PS real por mon: {len(filas)}")

    print("\n=== POR LA VIDA MEDIA DEL EQUIPO (lo que decia §1.1) ===")
    t = defaultdict(list)
    for m, _mn, _mx, _c, g in filas:
        t["bajo (<75)" if m < 75 else "alto (>=75)"].append(g)
    for k in ("bajo (<75)", "alto (>=75)"):
        if t[k]:
            print(f"   {k:<14} n={len(t[k]):>5}   gana {_pct(sum(t[k]) / len(t[k]))}")

    print("\n=== POR EL MINIMO POR MON ===")
    t = defaultdict(list)
    for _m, mn, _mx, _c, g in filas:
        t[min(mn // 10, 9)].append(g)
    for k in sorted(t):
        if len(t[k]) >= 5:
            print(f"   {k * 10:>2}-{k * 10 + 9:<2}%  n={len(t[k]):>5}   gana "
                  f"{_pct(sum(t[k]) / len(t[k]))}")

    print("\n=== POR NUMERO DE CAIDOS (lo que separa de verdad) ===")
    t = defaultdict(list)
    for _m, _mn, _mx, c, g in filas:
        t[c].append(g)
    for k in sorted(t):
        if len(t[k]) >= 10:
            etq = "(nadie caido)" if k == 0 else f"({k} caido{'s' if k > 1 else ''})"
            print(f"   {etq:<16} n={len(t[k]):>5}   gana "
                  f"{_pct(sum(t[k]) / len(t[k]))}")

    a, b = t.get(0, []), t.get(1, [])
    if a and b:
        pa, pb = sum(a) / len(a), sum(b) / len(b)
        se = math.sqrt(pa * (1 - pa) / len(a) + pb * (1 - pb) / len(b))
        print(f"\n=== d sin caidos vs 1 caido = {abs(pa - pb) / se:.2f} "
              f"(n={len(a)} vs {len(b)}) ===")

    print("\n=== CONTROL: dentro de cada numero de caidos, ¿importa la media? ===")
    t = defaultdict(list)
    for m, _mn, _mx, c, g in filas:
        t[(c, m >= 75)].append(g)
    for c in (0, 1, 2):
        lo, hi = t.get((c, False), []), t.get((c, True), [])
        if len(lo) >= 10 and len(hi) >= 10:
            d = 100 * (sum(hi) / len(hi) - sum(lo) / len(lo))
            print(f"   {c} caido(s):  media<75 n={len(lo):>4} gana "
                  f"{_pct(sum(lo) / len(lo))}  |  media>=75 n={len(hi):>4} gana "
                  f"{_pct(sum(hi) / len(hi))}  ->  {d:+.1f} puntos")
    print("\nSi sale NEGATIVO, la vida media no es el cuello: el caido lo es.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

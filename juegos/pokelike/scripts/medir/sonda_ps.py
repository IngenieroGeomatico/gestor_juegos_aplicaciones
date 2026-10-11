"""Cual de las DOS lecturas de PS esta viva, y en que pantalla.

El bot lee la vida de dos sitios que **no son la misma medida**:

  - `#team-bar .hp-bar-fill` -> un ancho en `%` (`navegador.equipo()`), el que
    usa la traza de mapa (`TRAZA_CAMINO ... vida=[...]`);
  - el texto de `#player-side` (`"0/35"`), el que usa `mios` y `DEC ps_abre`.

La hipotesis es que cada elemento solo esta fresco **en su propia pantalla**: en
el mapa manda la barra y el texto se queda con la pelea anterior; en la batalla
manda el texto y la barra se queda al 100%. Si eso es verdad, emparejar traza y
`mios` compara **dos instantes**, y todo lo medido asi hay que rehacerlo.

Esto lo comprueba sobre el volcado crudo de `_sonda_dom`, que lee las dos cosas
**en el mismo instante** (ver `PKL_SONDA_DOM` en `jugar_pokelike.py`).

    PKL_SONDA_DOM=/tmp/opencode/sonda uv run --group dev python \\
        juegos/pokelike/scripts/medir/sonda_ps.py /tmp/opencode/sonda
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ANCHO = re.compile(r"width:\s*([\d.]+)%")
PS = re.compile(r"^(\d+)\s*/\s*(\d+)$")


def _pct(ancho: str):
    m = ANCHO.search(ancho or "")
    return float(m.group(1)) if m else None


def _nombre(n: str) -> str:
    """`Bulbasaur Lv6` y `Bulbasaur` son el mismo món."""
    return re.sub(r"\s*Lv\.?\s*\d+\s*$", "", (n or "").strip())


def cargar(carpetas: list[Path]) -> list[dict]:
    filas = []
    for c in carpetas:
        for f in sorted(c.glob("*.jsonl")):
            for ln in f.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    try:
                        r = json.loads(ln)
                    except json.JSONDecodeError:
                        continue
                    r["_fich"] = f.name
                    filas.append(r)
    return filas


def discrepancias(filas: list[dict]) -> None:
    """Barra vs texto, món a món, **en el mismo volcado**."""
    print("=" * 72)
    print("1. BARRA (ancho %)  vs  TEXTO (ps/ps_max), en el MISMO instante")
    print("=" * 72)
    por = {}
    for r in filas:
        clave = (r.get("etiqueta"), r.get("pantalla"))
        barra = {_nombre(b.get("nombre")): _pct(b.get("ancho"))
                 for b in (r.get("barra") or [])}
        for x in (r.get("lado") or []):
            m = PS.match((x.get("hp") or "").strip())
            if not m:
                continue
            ps, mx = int(m.group(1)), int(m.group(2))
            p = barra.get(_nombre(x.get("nombre")))
            if p is None or mx == 0:
                continue
            d = por.setdefault(clave, {"n": 0, "mal": 0, "ej": []})
            d["n"] += 1
            if abs(p - 100 * ps / mx) > 1.5:
                d["mal"] += 1
                if len(d["ej"]) < 4:
                    d["ej"].append((r.get("paso"), _nombre(x.get("nombre")), p,
                                    ps, mx))
    for (etq, pant), d in sorted(por.items(), key=lambda kv: str(kv[0])):
        if not d["n"]:
            continue
        print(f"\n  etiqueta={etq!r}  pantalla={pant!r}")
        print(f"    discrepan {d['mal']} de {d['n']} mones "
              f"({100 * d['mal'] / d['n']:.0f}%)")
        for paso, nom, p, ps, mx in d["ej"]:
            print(f"      paso={paso:>4} {nom:<12} barra={p:>5}%  "
                  f"texto={ps}/{mx} = {100 * ps / mx:.1f}%")


def pantallas(filas: list[dict]) -> None:
    print()
    print("=" * 72)
    print("2. EN QUE PANTALLA SE LEE CADA ETIQUETA")
    print("=" * 72)
    c = Counter((r.get("etiqueta"), r.get("pantalla")) for r in filas)
    for (etq, pant), n in sorted(c.items(), key=lambda kv: str(kv[0])):
        print(f"  {str(etq):<8} en {str(pant):<18} {n}")


def transiciones(filas: list[dict]) -> None:
    """Mapa -> pelea: la barra dice una cosa y el texto de la pelea, otra."""
    print()
    print("=" * 72)
    print("3. MAPA -> PELEA: ¿cambia el equipo entre los dos volcados?")
    print("=" * 72)
    for fich in sorted({r["_fich"] for r in filas}):
        de_este = [r for r in filas if r["_fich"] == fich]
        for a, b in zip(de_este, de_este[1:]):
            if a.get("etiqueta") != "mapa" or b.get("etiqueta") != "pelea":
                continue
            mapa = {_nombre(x.get("nombre")): x.get("hp")
                    for x in (a.get("lado") or [])}
            pelea = {_nombre(x.get("nombre")): x.get("hp")
                     for x in (b.get("lado") or [])}
            comunes = {k for k in mapa if k in pelea}
            if not comunes:
                continue
            distintos = {k for k in comunes if mapa[k] != pelea[k]}
            marca = "CAMBIA" if distintos else "igual  "
            print(f"  {fich} mapa@paso{a.get('paso'):>4} ({a.get('pantalla')})"
                  f" -> pelea@paso{b.get('paso'):>4} ({b.get('pantalla')})  "
                  f"{marca}")
            for k in sorted(distintos):
                print(f"      {k:<12} mapa={mapa[k]:<9} pelea={pelea[k]}")


def main() -> int:
    carpetas = [Path(a) for a in sys.argv[1:]] or [Path("/tmp/opencode/sonda")]
    carpetas = [c for c in carpetas if c.exists()]
    if not carpetas:
        print("no hay volcados de sonda. Activa `PKL_SONDA_DOM=<dir>` al jugar.")
        return 1
    filas = cargar(carpetas)
    if not filas:
        print(f"sin registros en {[str(c) for c in carpetas]}")
        return 1
    print(f"{len(filas)} volcados de sonda en "
          f"{[str(c) for c in carpetas]}\n")
    pantallas(filas)
    discrepancias(filas)
    transiciones(filas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compara la run que llego a CHAMPION con el resto, campo por campo.

Una sola run winner no es una hypothesis, pero **si es un contraejemplo**: dice
que el techo no es fijo y por lo tanto algo del bot puede llegar mas alto. Este
script responde a la unica pregunta que importa: **en que se diferencia de la
mediana**, sin mirar ninguna variable a la que yo haya apuntado antes.

    uv run --group dev python juegos/pokelike/scripts/medir/perfil_winner.py
"""
from __future__ import annotations

import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path

LOGS = Path("juegos/pokelike/log")

RE_CAB = re.compile(r"^== brazo=(\S+) .*codigo=([0-9a-f]+) ==", re.MULTILINE)
RE_STARTER = re.compile(r"\[starter -> \d+\] (\w+)")
RE_DEC = re.compile(r"DEC nodo .*? tipo=(\w+) .*?razon=(\w+) score=(-?[\d.]+)")
RE_CAIDA = re.compile(r"COMBATE PERDIDO contra (.+?) \|")
RE_COMB = re.compile(r"peleas entrain\. : (\d+)")
RE_SALV = re.compile(r"peleas salvaje\s*: (\d+)")
RE_CAP = re.compile(r"capturas\s*: (\d+)")
RE_TUT = re.compile(r"tutores\s*: (\d+)")
RE_OBJ = re.compile(r"objetos\s*: (\d+)")
RE_CEN = re.compile(r"centros\s*: (\d+)")
RE_PAS = re.compile(r"^\s*pasos\s*: (\d+)", re.MULTILINE)
RE_INS = re.compile(r"^\s*insignias\s*: (\d+)", re.MULTILINE)
RE_RES = re.compile(r'^\s*resultado\s*: (\w+)', re.MULTILINE)
RE_GAN = re.compile(r"combates\s*: (\d+) ganados / (\d+) perdidos")
RE_EQUIPO = re.compile(r"^\s*equipo\s+: (\d+) \((\d+)-(\d+)\)", re.MULTILINE)
RE_DECISION_P = re.compile(r"\[nodo -> \d\] (\w+) score=(-?[\d.]+)")

# Motivos de decision: el campo `razon` de DEC nodo. Es la intencion del bot
# leida del propio codigo, no una etiqueta mia.
MOTIVOS = Counter()


def perfil(path: Path) -> dict | None:
    txt = path.read_text(encoding="utf-8", errors="replace")
    res = RE_RES.search(txt)
    if not res or res.group(1) not in ("CHAMPION", "GAME_OVER"):
        return None
    d: dict = {"log": path.name, "resultado": res.group(1),
               "code": path.stat().st_mtime}
    cab = RE_CAB.search(txt)
    d["brazo"] = cab.group(1) if cab else "?"
    d["codigo"] = cab.group(2) if cab else "?"
    m = RE_STARTER.search(txt)
    d["starter"] = m.group(1) if m else "?"
    for key, rx in (("entrenadores", RE_COMB), ("salvajes", RE_SALV),
                    ("capturas", RE_CAP), ("tutores", RE_TUT),
                    ("objetos", RE_OBJ), ("centros", RE_CEN),
                    ("ganados", RE_GAN), ("equipo_n", RE_EQUIPO)):
        m = rx.search(txt)
        if key == "ganados" and m:
            d["ganados"], d["perdidos"] = int(m.group(1)), int(m.group(2))
        elif key == "equipo_n" and m:
            d["equipo_n"] = int(m.group(1))
            d["niv_min"], d["niv_max"] = int(m.group(2)), int(m.group(3))
        elif m:
            d[key] = int(m.group(1))
    for key, rx in (("pasos", RE_PAS), ("insignias", RE_INS)):
        m = rx.search(txt)
        d[key] = int(m.group(1)) if m else 0
    d["motivos"] = Counter(m.group(2) for m in RE_DEC.finditer(txt))
    d["tipos_elegidos"] = Counter(m.group(1) for m in RE_DECISION_P.finditer(txt))
    d["caidas"] = [m.group(1).strip() for m in RE_CAIDA.finditer(txt)]
    return d


def linea(nombre: str, winner: dict, otros: list[dict], key: str,
          formato: str = "{:.2f}") -> str:
    vs = [o[key] for o in otros if key in o]
    if key not in winner or not vs:
        return f"  {nombre:16s} {'-':>8s}   {'-':>8s}   {'-':>7s}"
    return (f"  {nombre:16s} {formato.format(winner[key]):>8s}   "
            f"{formato.format(st.mean(vs)):>8s}   "
            f"{formato.format(st.median(vs)):>7s}")


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    runs = [p for p in LOGS.rglob("*.txt")
            if "h15" in p.name or "h16" in p.name or "h17" in p.name
            or "h18" in p.name or "h19" in p.name]
    datos = [d for d in (perfil(p) for p in runs) if d]
    if not datos:
        print("no hay runs cerradas")
        return 0

    winners = [d for d in datos if d["resultado"] == "CHAMPION"]
    losers = [d for d in datos if d["resultado"] != "CHAMPION"]
    print(f"runs cerradas: {len(datos)} | CHAMPION: {len(winners)} | "
          f"GAME_OVER: {len(losers)}")
    if not winners:
        print("ninguna CHAMPION todavia: no hay contraejemplo que mirar")
        return 0

    print("\n== LAS RUNS CHAMPION ==")
    for w in winners:
        print(f"  {w['log']}  brazo={w['brazo']} codigo={w['codigo']} "
              f"starter={w['starter']}")

    # Comparacion contra las runs de 8 insignias: si las hubiera, serian el
    # contraejemplo mas informativo. Si no, se usa el percentil 95.
    otras = [d for d in losers]
    print(f"\n== CHAMPION vs las {len(otras)} GAME_OVER ==")
    print(f"  {'':16s} {'CHAMPION':>8s}   {'media':>8s}   {'mediana':>7s}")
    for nombre, key, fmt in (
            ("pasos", "pasos", "{:.0f}"),
            ("insignias", "insignias", "{:.0f}"),
            ("pel. entrenador", "entrenadores", "{:.2f}"),
            ("pel. salvaje", "salvajes", "{:.2f}"),
            ("capturas", "capturas", "{:.2f}"),
            ("tutores", "tutores", "{:.2f}"),
            ("objetos", "objetos", "{:.2f}"),
            ("visitas centro", "centros", "{:.2f}"),
            ("combates ganados", "ganados", "{:.2f}"),
            ("combates perdidos", "perdidos", "{:.2f}"),
            ("tamano equipo", "equipo_n", "{:.2f}"),
            ("nivel min final", "niv_min", "{:.2f}"),
            ("nivel max final", "niv_max", "{:.2f}")):
        w = winners[0]
        print(linea(nombre, w, otras, key, fmt))

    print("\n== MOTIVOS DE DECISION: winner vs el resto (cuenta y proporcion) ==")
    tw = sum(winners[0]["motivos"].values()) or 1
    to = sum(sum(o["motivos"].values()) for o in otras) or 1
    print(f"  {'motivo':16s} {'winner':>10s}   {'resto':>10s}   {'x':>6s}")
    for mot in sorted(set(winners[0]["motivos"]) | {m for o in otras for m in o["motivos"]}):
        a = sum(w["motivos"][mot] for w in winners)
        b = sum(o["motivos"][mot] for o in otras)
        pa, pb = a / tw, b / to
        x = f"{pa/pb:.1f}x" if pb else "  inf"
        print(f"  {mot:16s} {a:4d} {100*pa:4.1f}%   {b:6d} {100*pb:5.1f}%   {x:>6s}")

    print("\n== TIPO DE NODO QUE ELIGE (lo que pulsa, no lo que hay) ==")
    tw = sum(winners[0]["tipos_elegidos"].values()) or 1
    to = sum(sum(o["tipos_elegidos"].values()) for o in otras) or 1
    print(f"  {'tipo':16s} {'winner':>10s}   {'resto':>10s}   {'x':>6s}")
    for t in sorted(set(winners[0]["tipos_elegidos"])
                    | {m for o in otras for m in o["tipos_elegidos"]}):
        a = sum(w["tipos_elegidos"][t] for w in winners)
        b = sum(o["tipos_elegidos"][t] for o in otras)
        pa, pb = a / tw, b / to
        x = f"{pa/pb:.1f}x" if pb else "  inf"
        print(f"  {t:16s} {a:4d} {100*pa:4.1f}%   {b:6d} {100*pb:5.1f}%   {x:>6s}")

    print("\n== DONDE MUERE EL RESTO ==")
    mc = Counter()
    for o in otras:
        for c in o["caidas"]:
            mc[c.split()[0]] += 1
    tot = sum(mc.values()) or 1
    for r, k in mc.most_common(12):
        print(f"  {r:22s} {k:5d}  {100*k/tot:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
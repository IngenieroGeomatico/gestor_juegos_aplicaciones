#!/usr/bin/env python3
"""Nivel del equipo en los combates de gimnasio, con validación cruzada.

Por qué existe: tres extracciones distintas del mismo log dieron +0,5, +0,9 y
+2,2 niveles de shortfall, y sólo una podía ser cierta. La fiable es la que lee
las **dos líneas contiguas del propio combate**:

    estado: Gym Battle vs Misty! | niveles rivales 18-20
    mios=[('Venonat Lv15', '0/43', 15), ('Ivysaur Lv16', '0/45', 16), ...]

El nivel del rival y el nivel de cada món nuestro están en la misma ventana y no
hay que emparejar la pantalla de decisión con la del combate, que es donde se
rompían los tres intentos anteriores.

Se valida contra una **fuente independiente** (la línea de mapa
`equipo N (vivos V) niv X-Y`): 266/266 combates, diferencia media +0,01 y sd
0,12. Si algún día el juego cambia el formato, esas dos fuentes dejan de
coincidir y el script avisa en vez de dar un número falso.

    uv run --group dev python juegos/pokelike/scripts/medir/nivel_gimnasio.py
    uv run --group dev python juegos/pokelike/scripts/medir/nivel_gimnasio.py --pat 'log/escalera/*.txt'

**Va en `scripts/medir/` y no en `scripts/` a propósito**: el hash de versión de
las tandas es `scripts/*.py`, sin recursión, para detectar cambios *del bot*.
Una herramienta de medición no es un cambio del bot, y meterla ahí haría que las
tandas futures no fueran comparables con las anteriores.
"""
from __future__ import annotations

import argparse
import glob
import re
import statistics as st
import sys
from pathlib import Path

# scripts/medir/x.py -> [0]=medir [1]=scripts [2]=pokelike [3]=juegos [4]=raiz
RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "juegos/pokelike/scripts"))

RE_RIVAL = re.compile(r"estado: Gym Battle vs (\w+)! \| niveles rivales (\d+)-(\d+)")
RE_MIOS = re.compile(r"mios=\[(.*?)\]\s*$")
RE_MON = re.compile(r"\('([^']+) Lv(\d+)'")
RE_MAP = re.compile(r"equipo (\d+) \(vivos (\d+)\) niv (\d+)-(\d+)")


def casos(pat: str) -> list[dict]:
    """Un registro por combate de gimnasio, con su veredicto."""
    out = []
    for f in sorted(glob.glob(pat)):
        t = Path(f).read_text(encoding="utf-8", errors="replace")
        if "RESUMEN" not in t:
            continue
        L = t.splitlines()
        for i, l in enumerate(L):
            mr = RE_RIVAL.search(l)
            if not mr:
                continue
            rival, rmax = mr.group(1), int(mr.group(3))
            mios = None
            for j in range(i + 1, min(i + 6, len(L))):
                mm = RE_MIOS.search(L[j].strip())
                if mm:
                    mios = [(n, int(v)) for n, v in RE_MON.findall(mm.group(1))]
                    break
            if not mios:
                continue
            # Veredicto: ¿se ganó ese gimnasio? Solo cuenta hasta la insignia
            # siguiente; más allá ya se mezclan combates posteriores.
            gana = any("insignia conseguida" in x for x in L[i:i + 40])
            # Fuente independiente para la validación cruzada.
            f2 = None
            for k in range(i - 1, max(0, i - 45), -1):
                mm = RE_MAP.search(L[k])
                if mm:
                    f2 = mm
                    break
            out.append(dict(
                fichero=f, gym=rival, rival_max=rmax,
                nuestro_max=max(v for _, v in mios),
                nuestro_medio=st.mean(v for _, v in mios),
                vivos=len(mios), gana=gana,
                mapa_max=int(f2.group(4)) if f2 else None,
                mios=[n for n, _ in mios]))
    return out


def validar(c: list[dict]) -> None:
    """Las dos fuentes deben coincidir, o el número no sirve."""
    con2 = [x for x in c if x["mapa_max"] is not None]
    if not con2:
        print("  (sin segunda fuente: no se puede validar)")
        return
    d = [x["nuestro_max"] - x["mapa_max"] for x in con2]
    ok = sum(1 for v in d if abs(v) <= 1)
    print(f"  fought con dos fuentes: {len(con2)}")
    print(f"  diferencia media: {st.mean(d):+.2f}  sd {st.stdev(d):.2f}")
    print(f"  coinciden en +-1 nivel: {ok}/{len(con2)} ({ok/len(con2):.0%})")
    if ok / len(con2) < 0.95:
        print("  !! AVISO: las fuentes ya no coinciden. El formato del juego")
        print("     ha cambiado o la extraction se ha roto. NO uses los")
        print("     niveles de este informe hasta arreglarlo.")
        raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pat", default=str(
        RAIZ / "juegos/pokelike/log/*/*.txt"))
    args = ap.parse_args()

    c = casos(args.pat)
    print(f"combates de gimnasio: {len(c)}\n")
    print("VALIDACION CRUZADA")
    validar(c)

    print("\nPOR GIMNASIO: gana o pierde segun nuestro nivel")
    for g in sorted({x["gym"] for x in c}):
        s = [x for x in c if x["gym"] == g]
        a = [x for x in s if x["gana"]]
        b = [x for x in s if not x["gana"]]
        riv = st.mean(x["rival_max"] for x in s)
        print(f"  {g:<10} rival Nv{riv:<4.0f} n={len(s):>3}  "
              f"victorias {len(a):>3} ({len(a)/len(s):>3.0%})")
        if a:
            print(f"    llega con nuestro max "
                  f"{st.mean(x['nuestro_max'] for x in a):.1f}")
        if b:
            print(f"    llega con nuestro max "
                  f"{st.mean(x['nuestro_max'] for x in b):.1f}  <- se muere")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
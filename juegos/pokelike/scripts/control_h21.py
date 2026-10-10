"""H21 · Miradas interinas y regla de parada. **PRE-REGISTRADO.**

Va en `scripts/` y no en `scripts/medir/` por la misma razón que `control_h20`:
el hash del lote se calcula sobre `scripts/*.py` sin recursión, y si la regla
de cuánto se juega viviera fuera del hash se podría retocar a mitad de tanda.

## Qué mide

**Primaria**: `insignias/run`. Es la única con potencia declarada (§5.3), y es
la que H20 dejó a medias al salir en la dirección contraria. Con la sd de
**0,44** medida sobre 26 runs, ~150 por brazo detecta un efecto de **+0,4/run**.

Lo que se informa pero NO decide:

- trainers elegidos por run. Es el mecanismo de H21 en el mundo: el bot tiene
  que dejar de descartar los entrenadores. Si la primaria sube y los trainers
  no, el efecto viene de otro sitio y la explicación de §H20 es falsa.
- pasos por run y paso al morir. H20 falló precisamente por ahí (llegaba
  antes y moría antes), así que hay que poder comprobar que no se repite.

## El mecanismo se mide primero

El marcador `H21: sin -N salvaje(s) por delante` aparece **solo** con el flag a
1, e incluye la cuenta de trainers intactos. Si no sale, el flag no llegó y los
números de abajo no significan nada.

## La regla de parada, escrita antes de tener un solo dato

**Miradas**: n = 50, 100 y 150 runs por brazo.

**Futilidad**: parar si el extremo superior del **IC 99%** de la diferencia
queda por debajo de **+0,15** insignias/run. Es menos de la mitad de la brecha
que H20 dejó abierta (+0,87), o sea que el efecto no se ha recuperado.

**Eficiencia**: parar si el extremo inferior del IC 99% queda por encima de
**+0,02**.

Ambas al 99%, más estricto que el criterio declarado del 95%, así que mirar
antes no infla el error de tipo I.

**Nada más autoriza a parar**: ni por tiempo, ni por lo grande que se vea.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "juegos/pokelike/scripts"))
from estadistica import p_permutacion

LOGS = RAIZ / "juegos/pokelike/log/h21"

# --- lo pre-registrado. No tocar sin invalidar el lote. ---
MIRADAS = (50, 100, 150)
EFECTO_MINIMO = 0.15
PISO = 0.02

pat_cab = re.compile(r"==\s*brazo=(\w)\s*\|.*?codigo=([0-9a-f]+)")
pat_ins = re.compile(r"^  insignias\s*:\s*(\d+)", re.M)
pat_trainer = re.compile(r"DEC nodo .*?tipo=entrenador")
pat_dec = re.compile(r"DEC nodo ")
pat_paso = re.compile(r"TRAZA_CAMINO paso=(\d+)")
pat_h21 = re.compile(r"H21: sin -(\d+) salvaje\(s\)")
pat_ent = re.compile(r"(\d+) entrenador\(es\) intactos")


def leer():
    a_ins: list[float] = []
    b_ins: list[float] = []
    hashes: set[str] = set()
    marcador = 0
    sin_entrenadores = 0
    pasos_a: list[float] = []
    pasos_b: list[float] = []
    for p in sorted(LOGS.glob("h21-*.txt")):
        m = re.match(r"h21-([AB])-", p.name)
        if not m:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        cab = pat_cab.search(t)
        if not cab:
            continue
        hashes.add(cab.group(2))
        if cab.group(1) != m.group(1):
            continue
        ins = pat_ins.search(t)
        if ins:
            (a_ins if m.group(1) == "A" else b_ins).append(float(ins.group(1)))
        if pat_h21.search(t):
            marcador += 1
            if "0 entrenador(es) intactos" in t:
                sin_entrenadores += 1
        ps = pat_paso.findall(t)
        if ps:
            (pasos_a if m.group(1) == "A" else pasos_b).append(len(ps))
    if len(hashes) > 1:
        raise SystemExit(f"ABORTA: varios codigos en la muestra: {sorted(hashes)}")
    return a_ins, b_ins, marcador, sin_entrenadores, pasos_a, pasos_b


def ic(a: list[float], b: list[float]):
    import numpy as np
    rng = np.random.default_rng(20261010)
    ia = np.array(a)[rng.integers(0, len(a), (20000, len(a)))].mean(axis=1)
    ib = np.array(b)[rng.integers(0, len(b), (20000, len(b)))].mean(axis=1)
    d = ia - ib
    lo, hi = np.percentile(d, [0.5, 99.5])
    return float(ia.mean() - ib.mean()), float(lo), float(hi)


def main() -> int:
    a, b, marcador, sin_ent, pa, pb = leer()
    print(f"[control] runs por brazo: A={len(a)} B={len(b)}  "
          f"(miradas en {MIRADAS} runs)")
    print(f"[control] MECANISMO: {marcador} runs de A con 'H21: sin -N salvaje(s)'")
    print(f"[control]   de esos, {sin_ent} sin trainer por delante: "
          f"alli H21 no puede cambiar nada")
    if not a or not b:
        print("[control] aun no hay runs de los dos brazos")
        return 0

    print(f"[control] pasos por run (informa): A={sum(pa)/len(pa):.0f} "
          f"B={sum(pb)/len(pb):.0f}  -- H20 murio por llegar antes, se vigila")

    n = min(len(a), len(b))
    hito = max([m for m in MIRADAS if n >= m], default=0)
    if hito == 0:
        print(f"[control] todavia no es una de las miradas {MIRADAS}")
        return 0
    if n != hito and hito != max(MIRADAS):
        print(f"[control] n={n} no es hito; solo decide en {MIRADAS}")
        return 0

    dif, lo, hi = ic(a, b)
    p = p_permutacion(a, b).get("p")
    print(f"[control] MIRADA n={n} runs | PRIMARIA insignias/run B-A={dif:+.3f} "
          f"IC99 [{lo:+.3f}; {hi:+.3f}] p={p:.4f}")
    print(f"[control]          base A={sum(a)/len(a):.3f} B={sum(b)/len(b):.3f}")

    if lo > PISO:
        print(f"[control] PARAR por eficacia: el IC99 entero queda sobre {PISO:+.2f}")
        print("PARAR")
        return 0
    if hi < EFECTO_MINIMO:
        print(f"[control] PARAR por futilidad: el IC99 no llega a {EFECTO_MINIMO:+.2f} "
              f"ni con los datos que faltan")
        print("PARAR")
        return 0
    print("[control] seguir: la respuesta aun no esta, y ningun otro motivo "
          "para parar esta autorizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())

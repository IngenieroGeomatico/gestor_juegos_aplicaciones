"""H19 · Miradas interinas y regla de parada. PRE-REGISTRADO.

Este fichero decide **cuanto se juega**, asi que va en `scripts/` y no en
`scripts/medir/`: el hash del lote se calcula sobre `juegos/pokelike/scripts/*.py`
sin recursion, y si la regla de parada viviera fuera del hash se podria retocar a
mitad de tanda sin que nadie se enterase.

## Que mide

La primaria de H19 es el **mecanismo**, no el resultado:

`P(al entrar a la pelea de gimnasio hay algun món a 0 PS)`

Base medida **0,42**. Motivo de que sea el mecanismo y no el resultado: el efecto
esperado es pequeno (un reroll salvado por run afectada), y con ese efecto
`P(gana la pelea de gimnasio)` solo tiene 69% de potencia a 100 por brazo,
mientras que el mecanismo tiene **92% a 0,20**. Elegir la primaria por potencia y
no por costumbre.

Que el resultado no se mire para decidir no significa que no se mire: se calcula
`P(gana la pelea de gimnasio)` y se informa, marcado como confirmatorio.

## La regla de parada, escrita antes de tener un solo dato

**Miradas**: n = 60, 100 y 150 por brazo. La unidad es la **pelea de gimnasio**,
no la run, porque la intervencion actua en el camino al jefe y medirlo en la
pelea es medir donde ocurre el efecto. Con ~0,7 peleas por run, 60 por brazo salen
de unas 85 runs por brazo.

**Futilidad**: parar si el extremo superior del **IC 99%** de la diferencia queda
por encima de **+0,15**. Razon: el efecto minimo que se ha declarado que merece la
pena es bajar la proportion a 0,27; si ya no hay forma ni de llegar ahi con los
datos que quedan, seguir no compra nada.

**Eficiencia**: parar si el extremo inferior del IC 99% queda por debajo de
**−0,15**, o sea si el mecanismo ha bajado de forma ya concluyente.

Ambas al **99%**, que es mas estricto que el criterio declarado, asi que mirar
antes **no infla** el error de tipo I respecto a leer una sola vez al final. Un
p<0,01 que se ve antes y un p<0,05 que se ve al final cuentan igual.

**Nada mas** autoriza a parar: ni por tiempo, ni por lo grande que se vea, ni por
"ya se nota".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path('/home/radi/Proyectos/Github/gestor_juegos_aplicaciones')
sys.path.insert(0, str(RAIZ / 'juegos/pokelike/scripts'))
from estadistica import p_permutacion  # noqa: E402

LOGS = RAIZ / 'juegos/pokelike/log/h19'

# --- lo pre-registrado. No tocar sin invalidar el lote. ---
MIRADAS = (60, 100, 150)
EFECTO_MINIMO = -0.15          # bajar 0,42 -> 0,27 es lo que merece la pena
NIVEL_IC = 0.99

pat_cab = re.compile(r'==\s*brazo=(\w)\s*\|.*?codigo=([0-9a-f]+)')
pat_gym = re.compile(r'estado: Gym Battle vs ')
pat_mios = re.compile(r'mios=\[(.*?)\]')
pat_mio = re.compile(r"'([^']+?)\s*Lv(\d+)',\s*'(\d+)/(\d+)'")
pat_out = re.compile(r'>>> COMBATE (GANADO|PERDIDO)')


def _peleas(t: str) -> list[tuple[int, int]]:
    """(llego_con_caido, gano) por pelea de gimnasio de este log."""
    out: list[tuple[int, int]] = []
    ls = t.splitlines()
    for i, ln in enumerate(ls):
        if not pat_gym.search(ln):
            continue
        caido = 0
        res = -1
        for l2 in ls[i + 1:i + 12]:
            if not caido:
                m = pat_mios.search(l2)
                if m:
                    mis = pat_mio.findall(m.group(1))
                    if mis:
                        caido = int(any(int(ps) <= 0 for _, _, ps, _ in mis))
            o = pat_out.search(l2)
            if o:
                res = int(o.group(1) == 'GANADO')
                break
        if res >= 0:
            out.append((caido, res))
    return out


def leer() -> tuple[list[float], list[float], list[float], list[float]]:
    a_cai: list[float] = []
    b_cai: list[float] = []
    a_gan: list[float] = []
    b_gan: list[float] = []
    hashes: set[str] = set()
    for p in sorted(LOGS.glob('h19-*.txt')):
        m = re.match(r'h19-([AB])-', p.name)
        if not m:
            continue
        t = p.read_text(encoding='utf-8', errors='replace')
        cab = pat_cab.search(t)
        if not cab:
            continue
        hashes.add(cab.group(2))
        if cab.group(1) != m.group(1):
            continue
        for caido, gano in _peleas(t):
            (a_cai if m.group(1) == 'A' else b_cai).append(float(caido))
            (a_gan if m.group(1) == 'A' else b_gan).append(float(gano))
    if len(hashes) > 1:
        raise SystemExit(f'ABORTA: varios codigos en la muestra: {sorted(hashes)}')
    return a_cai, b_cai, a_gan, b_gan


def ic(a: list[float], b: list[float]) -> tuple[float, float, float]:
    import numpy as np  # noqa: PLC0415
    rng = np.random.default_rng(20261009)
    ia = np.array(a)[rng.integers(0, len(a), (20000, len(a)))].mean(axis=1)
    ib = np.array(b)[rng.integers(0, len(b), (20000, len(b)))].mean(axis=1)
    d = ia - ib
    lo, hi = np.percentile(d, [0.5, 99.5])
    return float(ia.mean() - ib.mean()), float(lo), float(hi)


def main() -> int:
    a_c, b_c, a_g, b_g = leer()
    n = min(len(a_c), len(b_c))
    print(f'[control] peleas por brazo: A={len(a_c)} B={len(b_c)}  '
          f'(miradas en {MIRADAS} peleas)')
    if n == 0:
        return 0
    hito = max([m for m in MIRADAS if n >= m], default=0)
    if hito == 0:
        print(f'[control] todavia no es una de las miradas {MIRADAS}')
        return 0
    if n != hito and hito != max(MIRADAS):
        print(f'[control] n={n} no es hito; solo decide en {MIRADAS}')
        return 0

    dif, lo, hi = ic(a_c, b_c)
    p = p_permutacion(a_c, b_c).get('p')
    print(f'[control] MIRADA n={n} peleas | PRIMARIA llega-con-caido A-B={dif:+.3f} '
          f'IC99 [{lo:+.3f}; {hi:+.3f}] p={p:.4f}')
    print(f'[control]          base A={sum(a_c) / len(a_c):.3f} '
          f'B={sum(b_c) / len(b_c):.3f}')
    if a_g and b_g:
        print(f'[control]          CONFIRMATORIA gana-pelea A={sum(a_g) / len(a_g):.3f} '
              f'B={sum(b_g) / len(b_g):.3f}  (no decide)')

    # Eficiencia: el IC99 entero queda por debajo del efecto minimo declarado.
    if hi < EFECTO_MINIMO:
        print(f'[control] PARAR por eficacia: el IC99 entero queda bajo '
              f'{EFECTO_MINIMO:+.2f}. El mecanismo bajo de forma concluyente.')
        print('PARAR')
        return 0
    # Futilidad: a falta de n ya no queda margen para llegar al efecto minimo.
    if lo > EFECTO_MINIMO:
        print(f'[control] PARAR por futilidad: el IC99 no baja de {EFECTO_MINIMO:+.2f} '
              f'ni con los datos que faltan. Mas peleas no lo pueden traer.')
        print('PARAR')
        return 0
    print(f'[control] seguir: la respuesta aun no esta, y ningun otro motivo '
          f'para parar esta autorizado.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
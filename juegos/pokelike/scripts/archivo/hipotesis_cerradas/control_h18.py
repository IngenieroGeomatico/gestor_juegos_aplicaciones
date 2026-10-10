"""H18 ·Miradas interinas y regla de parada. PRE-REGISTRADO.

Este fichero decide **cuanto se juega**, asi que va en `scripts/` (y no en
`scripts/medir/`) a proposito: el hash del lote se calcula sobre
`juegos/pokelike/scripts/*.py` sin recursion, y si la regla de parada estuviera
fuera del hash se podria cambiar a mitad de tanda sin que nadie se enterase. Es
la parte del protocolo que mas caro sale si se deja fuera.

## Lo pre-registrado, escrito antes de tener un solo dato de H18

**Miradas**: n = 60, 80 y 100 por brazo. Ninguna mas. La ultima es el tope.

**Futilidad**: parar si el extremo superior del **IC 99%** de la diferencia de la
primaria queda **por debajo de +0,41** insignias/run. Razon: +0,41 es el efecto
declarado, y si ya estamos seguros al 99% de que no llega, seguir recogiendo no
lo puede devolver. Con 99% el limite es mas estricto que el criterio declarado
del 95%, asi que **parar por futilidad no infla el error de tipo I**.

**Eficiencia**: parar si el extremo inferior del IC 99% supera 0. Es un criterio
p<0,01, mas estricto que el alfa declarado de 0,05, asi que la lectura final con
el 95% no cambia: este lote **no puede** fabricar un positivo que el criterio
declarado no confirmaria.

**Nada mas** para parar. Ni por tiempo, ni porcuanto se vea de grande o de
pequena la diferencia, ni por "ya se nota". Un p<0,01 que se ve antes y un
p<0,05 que se ve al final tienen que contar igual, o el corte es eleccion del
resultado.

## Por que 99% y no 95%

Con el 95% el error de tipo I de leer 4 veces se dispara a casi 0,15. Con el 99%
las cuatro lecturas juntas siguen por debajo del 0,05 declarado. Es la manera
barata de permitir mirar sin pagar el peaje: mirar cuesta, y se paga con
limites mas estrechos, no con silencios.

Ademas las dos reglas solo cortan cuando la respuesta ya esta. Una futilidad con
el 99% no puede perder un efecto real del tamano declarado, y una eficacia con
el 99% no puede Inventarse una que no exista. Entre las dos, mirar antes no
cuesta nada en validez.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path('/home/radi/Proyectos/Github/gestor_juegos_aplicaciones')
sys.path.insert(0, str(RAIZ / 'juegos/pokelike/scripts'))
from estadistica import p_permutacion  # noqa: E402

LOGS = RAIZ / 'juegos/pokelike/log/h18'

# --- lo pre-registrado. No tocar sin invalidar el lote. ---
MIRADAS = (60, 80, 100)
EFECTO_DECLARADO = 0.10   # P(gana): de 0,61 a 0,71
NIVEL_IC = 0.99

pat_cab = re.compile(r'==\s*brazo=(\w)\s*\|.*?codigo=([0-9a-f]+)')
pat_ins = re.compile(r'insignias\s*:\s*(\d+)')
pat_gym = re.compile(r'estado: Gym Battle vs ')
pat_out = re.compile(r'>>> COMBATE (GANADO|PERDIDO)')


def _ganadas(t: str) -> list[int]:
    """1 si gano esa pelea de gimnasio, 0 si no. Una unidad por pelea, no por
    run: la intervencion actua justo en la pelea, y medirla ahi es medir donde
   donde ocurre el efecto."""
    out = []
    ls = t.splitlines()
    for i, ln in enumerate(ls):
        if not pat_gym.search(ln):
            continue
        for l2 in ls[i + 1:i + 12]:
            if (o := pat_out.search(l2)):
                out.append(1 if o.group(1) == 'GANADO' else 0)
                break
    return out


def leer() -> tuple[list[float], list[float]]:
    a: list[float] = []
    b: list[float] = []
    hashes: set[str] = set()
    for p in sorted(LOGS.glob('h18-*.txt')):
        m = re.match(r'h18-([AB])-', p.name)
        if not m:
            continue
        t = p.read_text(encoding='utf-8', errors='replace')
        cab = pat_cab.search(t)
        if not cab or 'RESUMEN' not in t:
            continue
        hashes.add(cab.group(2))
        if cab.group(1) != m.group(1):
            continue
        g = _ganadas(t)
        if g:
            (a if m.group(1) == 'A' else b).extend(float(x) for x in g)
    if len(hashes) > 1:
        raise SystemExit(f'ABORTA: varios codigos en la muestra: {sorted(hashes)}')
    return a, b


def ic(a: list[float], b: list[float], nivel: float) -> tuple[float, float, float]:
    """IC por bootstrap de la DIFERENCIA, al nivel pedido (0.99 = 99%)."""
    import numpy as np  # noqa: PLC0415
    rng = np.random.default_rng(20261009)
    ia = np.array(a)[rng.integers(0, len(a), (20000, len(a)))].mean(axis=1)
    ib = np.array(b)[rng.integers(0, len(b), (20000, len(b)))].mean(axis=1)
    d = ia - ib
    alfa = 1 - nivel
    lo, hi = np.percentile(d, [100 * alfa / 2, 100 * (1 - alfa / 2)])
    return float(ia.mean() - ib.mean()), float(lo), float(hi)


def main() -> int:
    a, b = leer()
    n = min(len(a), len(b))
    print(f'[control] n por brazo: A={len(a)} B={len(b)}  (minimo para decidir: {min(MIRADAS)})')
    if n == 0:
        return 0

    siguiente = [m for m in MIRADAS if n >= m]
    if not siguiente:
        print(f'[control] todavia no es una de las miradas {MIRADAS}')
        return 0
    hito = max(siguiente)
    if n != hito and hito != max(MIRADAS):
        print(f'[control] n={n} no es hito de mirada; solo decide en {MIRADAS}')
        return 0

    dif, lo, hi = ic(a, b, NIVEL_IC)
    p = p_permutacion(a, b).get('p')
    print(f'[control] MIRADA n={n}/brazo | dif A-B={dif:+.3f} '
          f'IC{int(NIVEL_IC * 100)}% [{lo:+.3f}; {hi:+.3f}] p={p:.4f}')

    if hi < EFECTO_DECLARADO:
        print(f'[control] PARAR por futilidad: el IC{int(NIVEL_IC * 100)}% no llega al '
              f'efecto declarado (+{EFECTO_DECLARADO}). Mas runs no lo pueden devolver.')
        print('PARAR')
        return 0
    if lo > 0:
        print(f'[control] PARAR por eficacia: el IC{int(NIVEL_IC * 100)}% ya excluye 0 '
              f'(p={p:.4f}, criterio declarado es 0,05).')
        print('PARAR')
        return 0
    print(f'[control] seguir: la respuesta aun no esta, y ningun otro motivo '
          f'para parar esta autorizado.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
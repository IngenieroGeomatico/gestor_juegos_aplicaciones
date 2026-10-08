"""Informe de H17: capturar cuando falta nivel, contra pelear con el entrenador.

A = PKL_CAPTURA_POR_NIVEL=1 (la rama que pondera capturar por nivel).
B = 0 (control literal).

**Este script se escribio ANTES de tener los datos** (n=47 por brazo, 08-10 14:53).
Eso no es un detalle de forma: es lo que hace que las cifras que salen de aqui
sean un test y no una lectura. Si el codigo de analisis se escribe despues de
mirar el lote, siempre encuentra algo: un umbral, un recorte, un subgrupo. Por eso
aqui solo estan la primaria y las secundarias declaradas el 07-10, y no hay mas.

  primaria  : insignias por partida, por brazo
  secundaria : proporcion de partidas con >= 2 insignias

Y dos cosas que NO estan, a proposito:
  - Misty no es primaria. Solo hay 0,233 entradas a Misty por run, o sea ~35 por
    brazo, y detectarla exigiria un salto de +29 puntos. La especificidad se paga
    en n, y con 35 por brazo es una moneda de cambio prohibitive.
  - ningun umbral posterior. El "nivel >= 20 y equipo >= 5 gana Misty" de H16
    era exactamente eso, y salio con 19 de 39 umbrales p<0,05 en v1 y 0 de 28 en
    v2. Un umbral elegido mirando los datos no es una hipotesis.

**El script no se pronuncia antes de n=150 por brazo.** Antes de eso imprime el
progreso y sale. Un veredicto con 47 por brazo seria ruido con forma de
conclusion.

Vive en `scripts/medir/` a proposito: el hash del lote se calcula sobre
`juegos/pokelike/scripts/*.py` **sin recursión**, asi que escribir este fichero
mientras el lote corre no cambia el hash y no aborta la reanudacion.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path('/home/radi/Proyectos/Github/gestor_juegos_aplicaciones')
sys.path.insert(0, str(RAIZ / 'juegos/pokelike/scripts'))
from estadistica import (  # noqa: E402
    ic_bootstrap, mann_whitney, p_permutacion, veredicto,
)

LOGS = RAIZ / 'juegos/pokelike/log/h17'
# El minimo declarado el 07-10: 150 por brazo. Antes de esto no hay veredicto.
MINIMO_POR_BRAZO = 150

pat_cab = re.compile(r'==\s*brazo=(\w)\s*\|.*?codigo=([0-9a-f]+)')
pat_res = re.compile(r'resultado\s*:\s*(\w+)')
pat_ins = re.compile(r'insignias\s*:\s*(\d+)')
pat_pas = re.compile(r'pasos\s*:\s*(\d+)')
pat_cap = re.compile(r'capturas\s*:\s*(\d+)')
pat_gan = re.compile(r'combates\s*:\s*(\d+)\s*ganados\s*/\s*(\d+)\s*perdidos')
# El mecanismo: la razon con la que la rama de H17 cambia el peso del nodo.
# En el brazo A deberia salir; en el B, nunca. Si sale en B, el flag no llego.
pat_fuego = re.compile(r'capturar tambien sube nivel')


def leer(path: Path) -> dict | None:
    """Una run, o None si no esta cerrada o no es de este codigo."""
    t = path.read_text(encoding='utf-8', errors='replace')
    cab = pat_cab.search(t)
    if not cab:
        return None
    brazo, codigo = cab.group(1), cab.group(2)
    r = t[t.rindex('RESUMEN'):] if 'RESUMEN' in t else ''
    mi = pat_ins.search(r)
    if not mi:
        return None
    d = {
        'brazo': brazo,
        'codigo': codigo,
        'fichero': path.name,
        'resultado': (pat_res.search(r) or [None, '?'])[1],
        'insignias': int(mi.group(1)),
        'fuego': len(pat_fuego.findall(t)),
    }
    m = pat_pas.search(r)
    d['pasos'] = int(m.group(1)) if m else None
    m = pat_cap.search(r)
    d['capturas'] = int(m.group(1)) if m else None
    m = pat_gan.search(r)
    d['ganados'], d['perdidos'] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return d


def carga() -> tuple[dict, dict]:
    """Reparte las runs por brazo y anota lo que se queda fuera y por que."""
    dentro, fuera = {'A': [], 'B': []}, []
    hashes = set()
    for p in sorted(LOGS.glob('h17-*.txt')):
        m = re.match(r'h17-([AB])-', p.name)
        if not m:
            fuera.append((p.name, 'nombre sin brazo'))
            continue
        brazo = m.group(1)
        d = leer(p)
        if d is None:
            fuera.append((p.name, 'sin RESUMEN (run sin cerrar)'))
            continue
        hashes.add(d['codigo'])
        if d['brazo'] != brazo:
            fuera.append((p.name, f"brazo del nombre {brazo} != del log {d['brazo']}"))
            continue
        dentro[brazo].append(d)
    # Mas de un codigo en la misma muestra es motivo para no publicar nada: seria
    # el fallo que el guard de hash del launcher ya impide, pero si aparece aqui
    # significa que alguien metio logs a mano.
    if len(hashes) > 1:
        fuera.append(('*', f'varios codigos en la muestra: {sorted(hashes)}'))
    return dentro, fuera


def medias(d: list[dict], k: str) -> list[float]:
    return [float(x[k]) for x in d if x.get(k) is not None]


def linea(a: list[float], b: list[float], etiq: str) -> None:
    ia, ib = sum(a) / len(a), sum(b) / len(b)
    dif = ia - ib
    # IC del DIFERENCIA: se remuestrea cada brazo por separado y se resta, que es
    # lo que hace falta para "la diferencia entre brazos", no para "la media de A".
    import numpy as np  # noqa: PLC0415
    rng = np.random.default_rng(20261008)
    ia_b = np.array(a)[rng.integers(0, len(a), (20000, len(a)))].mean(axis=1)
    ib_b = np.array(b)[rng.integers(0, len(b), (20000, len(b)))].mean(axis=1)
    d = ia_b - ib_b
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = p_permutacion(a, b).get('p')
    mw = mann_whitney(a, b)
    print(f'\n== {etiq} ==')
    print(f'   A: {ia:.3f} (n={len(a)})    B: {ib:.3f} (n={len(b)})    dif A-B: {dif:+.3f}')
    print(f'   IC 95% de la diferencia: [{lo:+.3f}; {hi:+.3f}]')
    print(f'   p (permutacion): {_fmt(p)}    Mann-Whitney: {_fmt(mw.get("p"))} (U={mw.get("U")})')
    print(f'   Cohen d: {_cohen(a, b):+.3f}')


def _fmt(v) -> str:
    return '?' if v is None else f'{v:.4f}'


def _cohen(a: list[float], b: list[float]) -> float:
    import statistics as st  # noqa: PLC0415
    va, vb = st.variance(a), st.variance(b)
    s = (((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2)) ** 0.5
    return (sum(a) / len(a) - sum(b) / len(b)) / s if s else 0.0


def main() -> int:
    dentro, fuera = carga()
    a, b = dentro['A'], dentro['B']
    print('=' * 66)
    print('H17 · capturar cuando falta nivel (A) contra entrenador (B)')
    print(f'cerradas: A={len(a)}  B={len(b)}   minima declarada: {MINIMO_POR_BRAZO} por brazo')
    print('=' * 66)

    # --- mecanismo primero: si el flag no llego, las cifras de arriba no significan
    print('\n-- mecanismo: ¿llego el flag? --')
    print(f'   veces que A peso capturar por nivel: A={sum(x["fuego"] for x in a)}  '
          f'B={sum(x["fuego"] for x in b)}')
    print(f'   capturas por run:                    A={_m([x["capturas"] for x in a])}  '
          f'B={_m([x["capturas"] for x in b])}')
    print(f'   pasos por run:                       A={_m([x["pasos"] for x in a])}  '
          f'B={_m([x["pasos"] for x in b])}')
    if sum(x['fuego'] for x in b) > 0:
        print('   AVISO: el brazo B decidio con el flag. El lote no es A/B.')

    fuera_bien = [f for f in fuera if f[1] == 'sin RESUMEN (run sin cerrar)']
    if fuera:
        print(f'\n-- fuera del analisis: {len(fuera)} ficheros --')
        for n, m in fuera_bien[:3]:
            print(f'   {n}: {m}')
        if len(fuera) > len(fuera_bien):
            for n, m in fuera:
                if m != 'sin RESUMEN (run sin cerrar)':
                    print(f'   {n}: {m}')

    if min(len(a), len(b)) < MINIMO_POR_BRAZO:
        print(f'\nAUN NO HAY MONTE. Faltan {MINIMO_POR_BRAZO - len(a)} por el brazo mas corto.')
        print('No se publica veredicto por debajo del minimo declarado: un p<0,05 con')
        print('47 por brazo sale solo, y repetir esa comprobacion con 20 metricas es')
        print('como se fabrican los falsos positivos.')
        return 0

    print('\n' + '=' * 66)
    linea(medias(a, 'insignias'), medias(b, 'insignias'), 'PRIMARIA: insignias por run')
    ga = [1.0 if x['insignias'] >= 2 else 0.0 for x in a]
    gb = [1.0 if x['insignias'] >= 2 else 0.0 for x in b]
    linea(ga, gb, 'SECUNDARIA: proporcion con >= 2 insignias')
    p = p_permutacion(medias(a, 'insignias'), medias(b, 'insignias')).get('p')
    print(f'\nveredicto sobre la primaria: {veredicto(p)}')
    return 0


def _m(v: list) -> str:
    v = [x for x in v if x is not None]
    return f'{sum(v) / len(v):.2f}' if v else '?'


if __name__ == '__main__':
    raise SystemExit(main())
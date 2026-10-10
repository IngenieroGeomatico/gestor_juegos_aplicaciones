"""Informe del experimento de la escalera de riesgo del entrenador.

A = escalera nueva (de-prioriza el entrenador con el equipo desmontado).
B = control literal (la rama vieja que devuelve PESO_ENTRENADOR_SANO).

Los dos brazos salen del MISMO codigo, solo cambia `PKL_ESCALERA_RIESGO`, y el
hash va en la cabecera de cada log: si algun log no coincide, es de otra tanda y
no cuenta.

Métrica primaria: insignias por partida (la que se fijó tras el experimento
anterior, porque "llega al primer gym" no tenia potencia). Secundarias:
llegada al primer gym, y muertes de entrenador elegidas con el equipo
desmontado, que es justo lo que la escalera deberia reducir.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path('/home/radi/Proyectos/Github/gestor_juegos_aplicaciones')
sys.path.insert(0, str(RAIZ / 'juegos/pokelike/scripts'))
from estadistica import (  # noqa: E402
    ic_bootstrap, mann_whitney, p_permutacion, veredicto,
)

LOGS = RAIZ / 'juegos/pokelike/log/esc_riesgo'

pat_brazo = re.compile(r'== brazo=(\w) \|.*PKL_ESCALERA_RIESGO=(\d)')
pat_hash = re.compile(r'codigo=([0-9a-f]+)')
pat_res = re.compile(r'resultado\s*:\s*(\w+)')
pat_ins = re.compile(r'insignias\s*:?\s*(\d+)')
pat_vivos = re.compile(r'equipo (\d+) \(vivos (\d+)\)')
pat_dec = re.compile(r'\[nodo -> \d+\] (\w+) score=')
pat_perdida = re.compile(r'COMBATE PERDIDO')
pat_estado = re.compile(r'equipo (\d+) \(vivos (\d+)\)')


def _p(res: dict) -> str:
    """El p-valor de `p_permutacion`, que devuelve dict y no float."""
    v = res.get('p')
    return '?' if v is None else f'{v:.4f}'


def insignias_de(t: str) -> int | None:
    r = t[t.rindex('RESUMEN'):] if 'RESUMEN' in t else ''
    m = pat_ins.search(r)
    return int(m.group(1)) if m else None


pat_disp = re.compile(r'disponibles \[([^\]]*)\]')
pat_riesgo = re.compile(r'entrenador de riesgo:')
pat_aplazado = re.compile(r'entrenador aplazado:.*sin cura delante')
pat_viejo = re.compile(r'unica fuente de exp|única fuente de exp')


def tipos_de(estado: str) -> list[str]:
    """Lo que el juego ofrecio en esa pantalla, leido del campo `disponibles`."""
    m = pat_disp.search(estado)
    if not m:
        return []
    return [t.strip().strip("'\"") for t in m.group(1).split(',') if t.strip()]


def mecanismo(lineas: list[str]) -> dict:
    """Pantallas de riesgo y si el bot dejo al entrenador en la cuneta.

    Devuelve: `marcadas` (la escalera/la rama vieja marco al entrenador),
    `evitables` (de esas, las que tenian otro tipo de nodo en pantalla, o sea
    donde la decision era de verdad), y `elegido` (las evitables en las que el
    bot peleó igual). Que `elegido` valga 0 en el brazo escalera es lo unico
    que demuestra que la penalizacion llega a timepo.
    """
    out = {'marcadas': 0, 'evitables': 0, 'elegido': 0}
    for i, ln in enumerate(lineas):
        md = pat_dec.search(ln)
        if not md or md.group(1) != 'entrenador':
            continue
        if not (pat_riesgo.search(ln) or pat_aplazado.search(ln)
                or pat_viejo.search(ln)):
            continue
        out['marcadas'] += 1
        estado = ''
        for j in range(i, min(i + 8, len(lineas))):
            if pat_vivos.search(lineas[j]):
                estado = lineas[j]
                break
        if any(d != 'entrenador' for d in tipos_de(estado)):
            out['evitables'] += 1
            out['elegido'] += 1      # se eligio: es el nodo de la decision
    return out


def recoge() -> dict:
    out: dict = {'A': [], 'B': []}
    hashes: Counter = Counter()
    sucios = 0
    for f in sorted(LOGS.glob('*.txt')):
        t = f.read_text(encoding='utf-8', errors='ignore')
        mb = pat_brazo.search(t)
        if not mb:
            continue
        brazo, escalera = mb.group(1), mb.group(2)
        h = pat_hash.search(t)
        if h:
            hashes[h.group(1)] += 1
        res = pat_res.search(t)
        if not res:
            sucios += 1
            continue                      # timeout: cuenta como fracaso, no se tira
        out[brazo].append({
            'insignias': insignias_de(t) or 0,
            'champion': res.group(1) == 'CHAMPION',
            'desmontado': mecanismo(t.splitlines())['elegido'],
            'mec': mecanismo(t.splitlines()),
            'escalera': escalera,
        })
    return out, hashes, sucios


def main() -> int:
    if not LOGS.exists():
        print(f'aun no hay logs en {LOGS}')
        return 1
    datos, hashes, sucios = recoge()
    A, B = datos['A'], datos['B']
    print(f'== escalera de riesgo ==')
    print(f'   A (escalera)   n={len(A)}')
    print(f'   B (control)    n={len(B)}')
    print(f'   hashes en los logs: {dict(hashes)}')
    if sucios:
        print(f'   {sucios} sin resultado (timeout: cuentan como 0 insignias)')
    if hashes and len(hashes) > 1:
        print('   AVISO: mas de un hash. Los brazos tienen que salir del mismo '
              'codigo; si no, la comparacion no vale.')
    if len(A) < 10 or len(B) < 10:
        print('   (aun no hay muestra suficiente para un p-valor)')
        return 0

    print()
    print('=== PRIMARIA: insignias por partida ===')
    ia = [d['insignias'] for d in A]
    ib = [d['insignias'] for d in B]
    ma = sum(ia) / len(ia)
    mb = sum(ib) / len(ib)
    print(f'   A: media={ma:.2f}  mediana={sorted(ia)[len(ia)//2]}  '
          f'max={max(ia)}  CHAMPION={sum(d["champion"] for d in A)}')
    print(f'   B: media={mb:.2f}  mediana={sorted(ib)[len(ib)//2]}  '
          f'max={max(ib)}  CHAMPION={sum(d["champion"] for d in B)}')
    print(f'   diferencia = {ma - mb:+.2f} insignias')
    # `mann_whitney` y `p_permutacion` devuelven dict, no float: el p-valor va
    # dentro. Escribirlo como float revienta el informe a mitad, que es
    # justo cuando mas falta hace.
    mw = mann_whitney(ia, ib)
    pp = p_permutacion(ia, ib)
    pmw = mw.get('p')
    print(f"   Mann-Whitney p={_p(mw)}  (U={mw.get('u', '?')})")
    print(f"   permutacion p={_p(pp)}")
    # Cuantita tambien, no solo si hay diferencia: con esta metrica un p bajo
    # puede querer decir "+0,02 insignias", que no compensa el cambio.
    try:
        ca, cb = ic_bootstrap(ia), ic_bootstrap(ib)
        print(f'   IC 95% media  A=[{ca[0]:.2f}, {ca[1]:.2f}]  '
              f'B=[{cb[0]:.2f}, {cb[1]:.2f}]')
    except Exception as exc:  # noqa: BLE001
        print(f"   (sin IC de bootstrap: {exc})")
    print(f"   -> {veredicto(pmw)}")

    print()
    print('=== SECUNDARIA 1: llega al menos a 1 insignia ===')
    ga = sum(1 for x in ia if x >= 1)
    gb = sum(1 for x in ib if x >= 1)
    print(f'   A {ga}/{len(A)}   B {gb}/{len(B)}')
    pa = p_permutacion([1] * ga + [0] * (len(A) - ga),
                       [1] * gb + [0] * (len(B) - gb))
    print(f"   permutacion p={_p(pa)}")

    print()
    print('=== SECUNDARIA 2: eligio entrenador con <=2 mons en pie ===')
    da = sum(d['desmontado'] for d in A)
    db = sum(d['desmontado'] for d in B)
    print(f'   A {da}/{len(A)} ({100*da//max(len(A),1)}%)   '
          f'B {db}/{len(B)} ({100*db//max(len(B),1)}%)')

    # El mecanismo, que es lo que tiene que moverse. Si aqui no se ve nada,
    # el primario no significa nada: se estaria comparando el bot consigo mismo.
    ma = sum(d['mec']['marcadas'] for d in A)
    ea = sum(d['mec']['evitables'] for d in A)
    xa = sum(d['mec']['elegido'] for d in A)
    mb_ = sum(d['mec']['marcadas'] for d in B)
    eb = sum(d['mec']['evitables'] for d in B)
    xb = sum(d['mec']['elegido'] for d in B)
    print(f'   marcadas:        A={ma}  B={mb_}')
    print(f'   con alternativa: A={ea}  B={eb}   <- las que si eran evitable')
    print(f'   peleadas igual:  A={xa}  B={xb}')
    if ea == 0:
        print('   AVISO: el brazo escalera no tuvo ni una pantalla de riesgo '
              'evitable. Sin eso no hay nada que comparar.')
    elif xa == 0:
        print('   OK: la escalera respetada 0 veces de las evitables: la '
              'penalizacion llega al score final.')
    else:
        print(f'   AVISO: la escalera se salto {xa} pantallas evitable(s). '
              f'El bono de ruta sigue tapando la penalizacion.')
    if xb == 0 and eb:
        print('   AVISO: el control tambien esquivo todas las evitables: los '
              'dos brazos hacen lo mismo.')
    return 0

if __name__ == '__main__':
    sys.exit(main())

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
from estadistica import mann_whitney, p_permutacion, veredicto  # noqa: E402

LOGS = RAIZ / 'juegos/pokelike/log/esc_riesgo'

pat_brazo = re.compile(r'== brazo=(\w) \|.*PKL_ESCALERA_RIESGO=(\d)')
pat_hash = re.compile(r'codigo=([0-9a-f]+)')
pat_res = re.compile(r'resultado\s*:\s*(\w+)')
pat_ins = re.compile(r'insignias\s*:?\s*(\d+)')
pat_vivos = re.compile(r'equipo (\d+) \(vivos (\d+)\)')
pat_dec = re.compile(r'\[nodo -> \d+\] (\w+) score=')
pat_perdida = re.compile(r'COMBATE PERDIDO')
pat_estado = re.compile(r'equipo (\d+) \(vivos (\d+)\)')


def insignias_de(t: str) -> int | None:
    r = t[t.rindex('RESUMEN'):] if 'RESUMEN' in t else ''
    m = pat_ins.search(r)
    return int(m.group(1)) if m else None


def entrenador_desmontado(lineas: list[str]) -> bool:
    """¿Eligió un entrenador con 2 o menos móns en pie?

    Se mide en la linea de mapa anterior a la decision, que es el estado real
    al elegir. `mios=` no sirve: sale cada 4 llamadas y puede ser a mitad de
    pelea (ver la correccion en HIPOTESIS.md).
    """
    for i, ln in enumerate(lineas):
        if not pat_perdida.search(ln) or 'Gym Battle' in ln or 'Wild' in ln:
            continue
        for j in range(i, max(0, i - 40), -1):
            if pat_dec.search(lineas[j]) and 'entrenador' in lineas[j]:
                for k in range(j, max(0, j - 25), -1):
                    m = pat_estado.search(lineas[k])
                    if m:
                        return int(m.group(2)) <= 2
                return False
    return False


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
            'desmontado': entrenador_desmontado(t.splitlines()),
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
    p = mann_whitney(ia, ib)
    print(f'   Mann-Whitney p={p:.4f}  (0,05 es el listón)')
    print(f'   permutacion p={p_permutacion(ia, ib):.4f}')
    print(f'   -> {veredicto(p)}')

    print()
    print('=== SECUNDARIA 1: llega al menos a 1 insignia ===')
    ga = sum(1 for x in ia if x >= 1)
    gb = sum(1 for x in ib if x >= 1)
    print(f'   A {ga}/{len(A)}   B {gb}/{len(B)}')
    pa = p_permutacion([1] * ga + [0] * (len(A) - ga),
                       [1] * gb + [0] * (len(B) - gb))
    print(f'   permutacion p={pa:.4f}')

    print()
    print('=== SECUNDARIA 2: eligio entrenador con <=2 mons en pie ===')
    da = sum(d['desmontado'] for d in A)
    db = sum(d['desmontado'] for d in B)
    print(f'   A {da}/{len(A)} ({100*da//len(A)}%)   '
          f'B {db}/{len(B)} ({100*db//len(B)}%)')
    print('   (esta es la que la escalera deberia bajar; si no baja, el flag '
          'no esta cambiando la decision)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

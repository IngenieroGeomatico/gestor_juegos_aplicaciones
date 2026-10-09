"""Donde se pierden las insignias despues de Misty. Pooled, sin brazos.

H17 quedo refutada (insignias/run -0,09; IC [-0,41; +0,24]), y su lectura declarada
decia que el cuello no era la apertura sino el tramo posterior a Misty. Esto es
ese tramo: no es un experimento, es una foto. No propone nada y no compara nada;
solo cuenta donde muere la masa y que la ata.

Se lee de los 225 logs cerrados que dejo el lote (A=115, B=110). Los dos brazos
se juntan a proposito: aqui no importa el flag, importa el bot.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

LOGS = Path('/home/radi/Proyectos/Github/gestor_juegos_aplicaciones'
            '/juegos/pokelike/log/h17')

GIMNASIAS = ['Brock', 'Misty', 'Erika', 'Koga', 'Sabrina', 'Lt. Surge']

pat_ins = re.compile(r'insignias\s*:\s*(\d+)')
pat_mapa = re.compile(r'mapa: .*?:\s*vs\s+([A-Za-z. ]+?)\s*\(([A-Za-z]+)\)')
pat_perdida = re.compile(r'>>> COMBATE PERDIDO contra (.+?)(?:\s*\||$)')
pat_aplazado = re.compile(
    r'jefe APLAZADO: hay (\d+) nivel\(es\) de faltan \(listón (\d+), rival (\d+)\);'
    r'[^|]*\|\s*medio (\d+) < listón (\d+)')
pat_caidos = re.compile(r'caido\(s\)|hay (\d+) caido\(s\)')
pat_equipo = re.compile(r'equipo\s+(\d+) \((?:vivos )?(\d+)\)')
pat_capturas = re.compile(r'capturas\s*:\s*(\d+)')
pat_pasos = re.compile(r'pasos\s*:\s*(\d+)')
pat_prep = re.compile(r'\[prep -> (.+?)\] (.+?) -> \[(.+?)\]')
pat_final = re.compile(r'\[nodo -> \d\] (\w+) score=')


def leer(p: Path) -> dict | None:
    t = p.read_text(encoding='utf-8', errors='replace')
    if 'RESUMEN' not in t:
        return None
    r = t[t.rindex('RESUMEN'):]
    mi = pat_ins.search(r)
    if not mi:
        return None
    insignias = int(mi.group(1))
    mapas = pat_mapa.findall(t)
    gym = mapas[-1][0].strip() if mapas else '(ninguno)'
    tipo = mapas[-1][1] if mapas else '?'
    perd = pat_perdida.findall(t)
    muerte = 'sana'
    if perd:
        muerte = 'entrenador' if 'wants to battle' in perd[-1] else 'salvaje'
    ap = pat_aplazado.findall(t)
    return {
        'fichero': p.name,
        'insignias': insignias,
        'gym': gym,
        'tipo': tipo,
        'muerte': muerte,
        'faltan': int(ap[-1][0]) if ap else None,
        'liston': int(ap[-1][1]) if ap else None,
        'medio': int(ap[-1][3]) if ap else None,
        'capturas': int((pat_capturas.search(r) or [0, 0])[1]),
        'pasos': int((pat_pasos.search(r) or [0, 0])[1]),
        'nodos': Counter(pat_final.findall(t)),
    }


def main() -> None:
    runs = [d for d in (leer(p) for p in sorted(LOGS.glob('h17-*.txt'))) if d]
    n = len(runs)
    print(f'POOLED: {n} runs cerradas (A=115, B=110 juntas a proposito)')
    print(f'  insignias/run = {sum(x["insignias"] for x in runs) / n:.3f} '
          f'de 8 posibles')

    # --- 1. donde muere la masa ---
    print('\n-- 1. en que gimnasion se queda cada run --')
    dist = Counter(x['gym'] for x in runs)
    orden = [g for g in GIMNASIAS if g in dist] + \
            [g for g in dist if g not in GIMNASIAS]
    print(f'   {"gimnasion":<14}{"muere ahi":>10}{"acumulado pasa":>16}')
    pasan = 0
    for g in orden:
        llegan = sum(1 for x in runs if x['gym'] in orden[:orden.index(g) + 1])
        pasan = llegan
        print(f'   {g:<14}{dist[g]:>10}{llegan:>10} de {n}  ({100 * llegan / n:.0f}%)')

    # --- 2. tasa de passage condicional ---
    print('\n-- 2. de las que llegan a un gimnasion, cuantas pasan el anterior --')
    for i, g in enumerate(orden):
        llega_a_g = sum(1 for x in runs if x['gym'] in orden[:i + 1])
        if llega_a_g == 0:
            continue
        pasa_este = llega_a_g - dist[g]
        print(f'   {g:<14} llegan {llega_a_g:>3}  lo pasan {pasa_este:>3}  '
              f'({100 * pasa_este / llega_a_g:>3.0f}%)')

    # --- 3. como mueren los que pasan de Misty ---
    print('\n-- 3. los que pasan de Misty: que los mata --')
    tras = [x for x in runs if x['insignias'] >= 2]
    print(f'   runs con >=2 insignias: {len(tras)} ({100 * len(tras) / n:.0f}%)')
    print(f'   de esas, como mueren: {dict(Counter(x["muerte"] for x in tras))}')
    print(f'   insignias/run de ese grupo: '
          f'{sum(x["insignias"] for x in tras) / max(len(tras), 1):.2f}')
    tarde = [x for x in tras if x['insignias'] >= 3]
    print(f'   y las que llegan a 3 o mas: {len(tarde)} '
          f'({100 * len(tarde) / n:.0f}% de todas)')

    # --- 4. el handicap de nivel cuando aplaza al jefe ---
    print('\n-- 4. cuando el jefe APLAZADO aplaza, de cuanto va el deficit --')
    for etiqueta, sel in (('todas', runs), ('>=2 insignias', tras)):
        ap = [x for x in sel if x['faltan'] is not None]
        if not ap:
            continue
        print(f'   {etiqueta:<14} aplazos={len(ap):>4}  '
              f'deficit medio={sum(x["faltan"] for x in ap) / len(ap):>5.1f} niveles  '
              f'nivel medio del equipo={sum(x["medio"] for x in ap) / len(ap):>5.1f}  '
              f'liston medio={sum(x["liston"] for x in ap) / len(ap):>5.1f}')

    # --- 5. que nodo eligio el bot justo antes de morir ---
    print('\n-- 5. que nodo elige el bot en las 3 pantallas previas a la muerte --')
    ult = Counter()
    for x in runs:
        for k, v in x['nodos'].most_common(0):
            pass
    # recuento de la ultima decision registrada de cada run
    for p in sorted(LOGS.glob('h17-*.txt')):
        t = p.read_text(encoding='utf-8', errors='replace')
        if 'RESUMEN' not in t:
            continue
        d = pat_final.findall(t)
        if d:
            ult[d[-1]] += 1
    for k, v in ult.most_common(8):
        print(f'   {k:<14}{v:>5}  ({100 * v / n:.0f}%)')


if __name__ == '__main__':
    main()
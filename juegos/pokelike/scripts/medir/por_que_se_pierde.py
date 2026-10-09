"""Por que se pierde el combate contra el jefe. Medicion, no hipotesis.

Este script responde a la pregunta que llevaba dos noches abierta: el bot llega
bajo de nivel, aplaza, vuelve al mismo nivel, entra por debajo y pierde. **Pero no
se sabe si pierde por el nivel, por los tipos o por como llega el equipo.**

La respuesta esta en el log y no se estaba usando. Cada pelea deja:

    estado: Gym Battle vs Brock! | niveles rivales 12-14
    enemigos=[('Magnemite Lv14', '18/29', 14), ...]
    mios=[('Bulbasaur Lv15', '0/38', 15), ('Sandshrew Lv12', '31/34', 12)]
    >>> COMBATE GANADO / COMBATE PERDIDO contra ...

Con eso se puede separar el por que en tres categorias que no se confunden:

- **nivel**: nuestro mejor món esta por debajo del rival mas alto
- **tipos**: ningun món nuestro pega bien a los tipos del rival
- **estado**: llegamos con el equipo deteriorado (caidos, PS bajos)

Que antes no se supiera WHICH es el punto: se sabia que se perdia, y se estan
inventando hipotesis sobre el COMO. Esto mide el como antes de tocar nada.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path('/home/radi/Proyectos/Github/gestor_juegos_aplicaciones')
sys.path.insert(0, str(RAIZ / 'juegos/pokelike/scripts'))
import pkl_movimientos as PM  # noqa: E402
from pkl_tipos import multiplicador as MULT  # noqa: E402

LOGS = RAIZ / 'juegos/pokelike/log/h17'

pat_estado = re.compile(r'estado: Gym Battle vs ([^!]+)! \| niveles rivales (\d+)-(\d+)')
pat_enem = re.compile(r'enemigos=\[(.*?)\]')
pat_mios = re.compile(r'mios=\[(.*?)\]')
pat_out = re.compile(r'>>> COMBATE (GANADO|PERDIDO)')
# OJO: el nombre y el nivel van DENTRO del mismo texto entrecomillado,
# ("'Geodude Lv12'"), no en dos comillas separadas. Con el patron equivocado no
# parsea ni un enemigo y el script sale con cero peleas sin decir por que.
pat_rival = re.compile(r"'([^']+?)\s*Lv(\d+)'")
pat_mio_ps = re.compile(r"'([^']+?)\s*Lv(\d+)',\s*'(\d+)/(\d+)'")


def _nivel_de(nombre: str, rival_lv: int, texto_mio: bool) -> int:
    return rival_lv


def mult_contra(tipos_mios: list[tuple[list[str], int]], tipos_rival: list[str]) -> float:
    """Mejor multiplicador de ATAQUE que tenemos contra el equipo rival."""
    mejor = 0.0
    for tm, _ in tipos_mios:
        for t in tm:
            for r in tipos_rival:
                v = MULT(t, r)
                if v is not None and v > mejor:
                    mejor = v
    return mejor


def recolectar() -> list[dict]:
    salida = []
    for p in sorted(LOGS.glob('h17-*.txt')):
        lineas = p.read_text(encoding='utf-8', errors='replace').splitlines()
        for i, ln in enumerate(lineas):
            m = pat_estado.search(ln)
            if not m:
                continue
            gym = m.group(1).strip()
            rmin, rmax = int(m.group(2)), int(m.group(3))
            # las dos lineas siguientes con la foto del combate
            enem = mios = None
            res = None
            for l2 in lineas[i + 1:i + 12]:
                if enem is None and (e := pat_enem.search(l2)):
                    enem = e.group(1)
                if mios is None and (e := pat_mios.search(l2)):
                    mios = e.group(1)
                if (o := pat_out.search(l2)):
                    res = o.group(1)
                    break
            if not enem or not mios or res is None:
                continue
            riv = [(n, int(lv)) for n, lv in pat_rival.findall(enem)]
            # los mios llevan el PS a continuacion del nivel, en otro grupo
            mis_ps = [(n, int(lv), int(ps), int(pm))
                      for n, lv, ps, pm in pat_mio_ps.findall(mios)]
            if not riv:
                continue
            tipos_r = sorted({t for n, _ in riv for t in PM.tipos_de(n)})
            info_mios = [(PM.tipos_de(n), lv) for n, lv, _, _ in mis_ps]
            mult = mult_contra(info_mios, tipos_r) if tipos_r else 1.0
            niv_nuestro_max = max((lv for _, lv, _, _ in mis_ps), default=0)
            niv_rival_max = max(lv for _, lv in riv)
            caidos = sum(1 for _, _, ps, _ in mis_ps if ps <= 0)
            vida_media = (sum(ps / max(pm, 1) for _, _, ps, pm in mis_ps) / len(mis_ps)
                          if mis_ps else 0.0)
            salida.append({
                'gym': gym, 'res': res,
                'dif_nivel': niv_rival_max - niv_nuestro_max,
                'mult': mult,
                'caidos': caidos,
                'vida': vida_media,
                'n_mios': len(mis_ps),
                'rival_niv': (rmin, rmax),
            })
    return salida


def main() -> None:
    d = recolectar()
    print(f'peleas de gimnasio con foto completa: {len(d)}')
    if not d:
        return
    g = sum(1 for x in d if x['res'] == 'GANADO')
    print(f'  ganadas {g} ({100 * g / len(d):.0f}%)   perdidas {len(d) - g}')

    print('\n-- ¿POR QUE SE PIERDE? separa nivel, tipos y estado --')
    print(f'   {"categoria":<34}{"ganadas":>18}{"perdidas":>18}')
    for etiqueta, cond in (
        ('nivel: nuestro max < rival max',
         lambda x: x['dif_nivel'] > 0),
        ('nivel: nuestro max >= rival max',
         lambda x: x['dif_nivel'] <= 0),
        ('tipos: mejor multiplicador >= 1.5',
         lambda x: x['mult'] >= 1.5),
        ('tipos: mejor multiplicador < 1.5',
         lambda x: x['mult'] < 1.5),
        ('estado: hay caidos al entrar',
         lambda x: x['caidos'] > 0),
        ('estado: sin caidos al entrar',
         lambda x: x['caidos'] == 0),
    ):
        sel = [x for x in d if cond(x)]
        if not sel:
            continue
        w = sum(1 for x in sel if x['res'] == 'GANADO')
        print(f'   {etiqueta:<34}{w:>8} de {len(sel):<4} ({100 * w / len(sel):>3.0f}%)'
              f'{100 * w / len(sel):>9}')

    print('\n-- por gimnasio: nivel con el que se entra y como sale --')
    print(f'   {"gimnasion":<12}{"n":>5}{"gana":>8}{"dif nivel":>11}'
          f'{"mult medio":>12}{"vida media":>12}')
    por = defaultdict(list)
    for x in d:
        por[x['gym']].append(x)
    for gym, sel in sorted(por.items(), key=lambda kv: -len(kv[1]))[:9]:
        w = sum(1 for x in sel if x['res'] == 'GANADO')
        dn = sum(x['dif_nivel'] for x in sel) / len(sel)
        mu = sum(x['mult'] for x in sel) / len(sel)
        vi = sum(x['vida'] for x in sel) / len(sel)
        print(f'   {gym[:11]:<12}{len(sel):>5}{100 * w / len(sel):>7.0f}%'
              f'{dn:>+11.1f}{mu:>12.2f}{vi:>11.0%}')

    print('\n-- el corte que mas separa: nivel y tipo a la vez --')
    print(f'   {"":<28}{"gana":>8}{"n":>6}')
    for etiqueta, cond in (
        ('bajo de nivel Y mal tipado', lambda x: x['dif_nivel'] > 0 and x['mult'] >= 1.5),
        ('bajo de nivel Y bien tipado', lambda x: x['dif_nivel'] > 0 and x['mult'] < 1.5),
        ('a nivel Y mal tipado', lambda x: x['dif_nivel'] <= 0 and x['mult'] >= 1.5),
        ('a nivel Y bien tipado', lambda x: x['dif_nivel'] <= 0 and x['mult'] < 1.5),
    ):
        sel = [x for x in d if cond(x)]
        if sel:
            w = sum(1 for x in sel if x['res'] == 'GANADO')
            print(f'   {etiqueta:<28}{100 * w / len(sel):>7.0f}%{len(sel):>6}')


if __name__ == '__main__':
    main()
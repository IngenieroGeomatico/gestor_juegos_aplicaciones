"""H20 · Miradas interinas y regla de parada. **PRE-REGISTRADO.**

Este fichero decide **cuánto se juega**, así que va en `scripts/` y no en
`scripts/medir/`: el hash del lote se calcula sobre
`juegos/pokelike/scripts/*.py` sin recursión, y si la regla de parada viviera
fuera del hash se podría retocar a mitad de tanda sin que nadie se enterase.

## Qué mide

La unidad es la **pelea de gimnasio**, no la run, porque la intervención actúa
en el camino al jefe y medirlo en la pelea es medir donde ocurre el efecto.
Con ~0,7 peleas de gimnasio por run, 100 por brazo salen de unas 145 runs.

**Primaria**: `P(entra a la pelea de gimnasio con vida > 75%)`.
Base medida **0,65**: en 764 peleas emparejadas con su pantalla, 178 entran con
algún món a 0 o por debajo del 50%, y el corte de emergencia del bot cubre el
resto.

Se elige la primaria **por potencia y no por costumbre**, que es lo que salió
mal en H17: `P(gana la pelea de gimnasio)` tiene base 0,61 pero es la
*consecuencia* de la primaria, así que se informa y no decide.

**El mecanismo se mide aparte y primero**: el marcador `H20: rama sin gasto`
aparece en el motivo de la decisión **solo** con el flag a 1. Si no sale, la
intervención no llegó y el resto de números no significan nada. Ya ha pasado
dos veces: H17 gastó 300 runs con un flag que decidía en el 34% de las pantallas
y en la mayoría de ellas no cambiaba nada, y H19 gastó las suyas con un
mecanismo que salía en el 1,2%.

## La regla de parada, escrita antes de tener un solo dato

**Miradas**: n = 60, 100 y 150 peleas por brazo.

**Futilidad**: parar si el extremo superior del **IC 99%** de la diferencia
queda por debajo de **+0,08**. Razón: el cuello medido (vida 0-50% → gana el
25%) está en juego en aproximadamente el 23% de las peleas, así que el techo
teórico del efecto es de unos +0,23 puntos de proportion. Un IC que ya no
llega a +0,08 descarta el efecto a un nivel donde más runs no compran nada.

**Eficiencia**: parar si el extremo inferior del IC 99% queda por encima de
**+0,02**, o sea si la entrada entera ha mejorado de forma ya concluyente.

Ambas al **99%**, que es más estricto que el criterio declarado, así que mirar
antes **no infla** el error de tipo I respecto a leer una sola vez al final. Un
p<0,01 que se ve antes y un p<0,05 que se ve al final cuentan igual.

**Nada más autoriza a parar**: ni por tiempo, ni por lo grande que se vea el
efecto, ni por "ya se nota".

## Lo que se informa pero NO decide

- `P(gana la pelea de gimnasio)`. Es la consecuencia de la primaria.
- `P(llega con algún món a 0)`. Es el mismo hecho medido por el otro lado.
- `insignias/run`. Se calcula y se dice, con su potencia al lado. Con el efecto
  esperado en la primaria, la mejora en insignias puede no llegar al umbral que
  haría falta; declararla primaria sería mentir, que es exactamente lo que pasó
  en H19.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "juegos/pokelike/scripts"))
from estadistica import p_permutacion

LOGS = RAIZ / "juegos/pokelike/log/h20"

# --- lo pre-registrado. No tocar sin invalidar el lote. ---
MIRADAS = (60, 100, 150)
EFECTO_MINIMO = 0.08        # el techo teorico del efecto es ~0,23
PISO = 0.02                 # por debajo de esto el efecto es despreciable
NIVEL_IC = 0.99

pat_cab = re.compile(r"==\s*brazo=(\w)\s*\|.*?codigo=([0-9a-f]+)")
pat_gym = re.compile(r"estado: Gym Battle vs ")
pat_mios = re.compile(r"mios=\[(.*?)\]")
pat_mio = re.compile(r"'([^']+?)\s*Lv(\d+)',\s*'(\d+)/(\d+)'")
pat_out = re.compile(r">>> COMBATE (GANADO|PERDIDO)")
pat_h20 = re.compile(r"H20: rama sin gasto")
# El mecanismo correcto imprime **cuantos pokecenters hay por delante** en el
# mismo motivo. Con el bug, el marcador reporting `extra` entero (que incluia
# 12 por cada centro) y restaba la cura: los valores llegaban a 88, 105 y 56
# siendo `combates_por_delante` un maximo de 8. Si aqui sale un numero que no
# cabe en un tope de 8, el lote es del codigo viejo y no mide nada.
pat_cura = re.compile(r"\+(\d+) pokecenter\(s\) por delante")
pat_coste = re.compile(r"H20: rama sin gasto \((\d+(?:\.\d+)?) combate")


def _peleas(t: str) -> list[tuple[int, int, int]]:
    """(vida_media_100, gano, hay_caido) por pelea de gimnasio de este log.

    La **foto de PS reales** es lo que hace esto fiable: el HUD marca 100 a un
    món caído, y H19 construyó su instrumento sobre el HUD, así que su marcador
    decía "equipo entero, vida 100%, vivos 2/2" en el mismo paso en que la
    traza decía `Bulbasaur:0%`. Un instrumento que describe mal el mundo hace
    que toda la medida posterior sea basura.
    """
    out: list[tuple[int, int, int]] = []
    ls = t.splitlines()
    for i, ln in enumerate(ls):
        if not pat_gym.search(ln):
            continue
        ratios: list[int] = []
        caido = 0
        res = -1
        for l2 in ls[i + 1:i + 12]:
            if not ratios:
                m = pat_mios.search(l2)
                if m:
                    for _nom, _lv, ps, mx in pat_mio.findall(m.group(1)):
                        if int(mx) > 0:
                            ratios.append(int(ps) * 100 // int(mx))
                            if int(ps) <= 0:
                                caido = 1
            o = pat_out.search(l2)
            if o:
                res = int(o.group(1) == "GANADO")
                break
        if res >= 0 and ratios:
            out.append((sum(ratios) // len(ratios), res, caido))
    return out


def leer() -> tuple[list[float], list[float], list[float], list[float], int,
                 int, int]:
    a_vida: list[float] = []
    b_vida: list[float] = []
    a_gan: list[float] = []
    b_gan: list[float] = []
    hashes: set[str] = set()
    marcador = 0
    coste_imposible = 0
    cura_delante = 0
    for p in sorted(LOGS.glob("h20-*.txt")):
        m = re.match(r"h20-([AB])-", p.name)
        if not m:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        cab = pat_cab.search(t)
        if not cab:
            continue
        hashes.add(cab.group(2))
        if cab.group(1) != m.group(1):
            continue
        if pat_h20.search(t):
            marcador += 1
        # El numero de peleas por delante **no puede pasar de 8**: es el tope de
        # `combates_por_delante`, mas 4 por entrenador. Un valor mayor solo cabe
        # si el acumulador arrastraba los pokecenters, que era el bug.
        for cm in pat_coste.findall(t):
            if float(cm) > 40.0:
                coste_imposible += 1
        cura_delante += len(pat_cura.findall(t))
        for vida, gano, _caido in _peleas(t):
            # La primaria: entrar con el equipo por encima de la puerta del 75%.
            entero = 1.0 if vida > 75 else 0.0
            (a_vida if m.group(1) == "A" else b_vida).append(entero)
            (a_gan if m.group(1) == "A" else b_gan).append(float(gano))
    if len(hashes) > 1:
        raise SystemExit(f"ABORTA: varios codigos en la muestra: {sorted(hashes)}")
    return a_vida, b_vida, a_gan, b_gan, marcador, coste_imposible, cura_delante


def ic(a: list[float], b: list[float]) -> tuple[float, float, float]:
    import numpy as np
    rng = np.random.default_rng(20261010)
    ia = np.array(a)[rng.integers(0, len(a), (20000, len(a)))].mean(axis=1)
    ib = np.array(b)[rng.integers(0, len(b), (20000, len(b)))].mean(axis=1)
    d = ia - ib
    lo, hi = np.percentile(d, [0.5, 99.5])
    return float(ia.mean() - ib.mean()), float(lo), float(hi)


def main() -> int:
    a_v, b_v, a_g, b_g, marcador, imposibles, cura = leer()
    n = min(len(a_v), len(b_v))
    print(f"[control] peleas por brazo: A={len(a_v)} B={len(b_v)}  "
          f"(miradas en {MIRADAS} peleas)")
    print(f"[control] MECANISMO: {marcador} runs de A con el marcador "
          f"'H20: rama sin gasto'")
    print(f"[control]   cura por delante sumada en el motivo: {cura} decisiones")
    # El guard de integridad del arreglo: con el bug, `extra` arrastraba los
    # pokecenters y salia en decenas. Si aparece, el lote mezcla el codigo
    # viejo con el nuevo y no mide nada (ver §1.3 de HIPOTESIS.md).
    if imposibles:
        print(f"[control] ABORTA: {imposibles} decisiones con mas de 40 "
              f"combates por delante. `combates_por_delante` esta topado en 8: "
              f"eso solo cabe si el acumulador arrastra los pokecenters, que es "
              f"el bug ya corregido. El lote es del codigo viejo.")
        return 2
    if n == 0:
        return 0
    hito = max([m for m in MIRADAS if n >= m], default=0)
    if hito == 0:
        print("[control] todavia no es una de las miradas {MIRADAS}")
        return 0
    if n != hito and hito != max(MIRADAS):
        print(f"[control] n={n} no es hito; solo decide en {MIRADAS}")
        return 0

    dif, lo, hi = ic(a_v, b_v)
    p = p_permutacion(a_v, b_v).get("p")
    print(f"[control] MIRADA n={n} peleas | PRIMARIA entra-entero A-B={dif:+.3f} "
          f"IC99 [{lo:+.3f}; {hi:+.3f}] p={p:.4f}")
    print(f"[control]          base A={sum(a_v) / len(a_v):.3f} "
          f"B={sum(b_v) / len(b_v):.3f}")
    if a_g and b_g:
        print(f"[control]          INFORMA gana-pelea A={sum(a_g) / len(a_g):.3f} "
              f"B={sum(b_g) / len(b_g):.3f}  (no decide)")

    # Eficiencia: el IC99 entero queda por encima del piso.
    if lo > PISO:
        print(f"[control] PARAR por eficacia: el IC99 entero queda sobre "
              f"{PISO:+.2f}. El cuello se ha cerrado de forma concluyente.")
        print("PARAR")
        return 0
    # Futilidad: a falta de n ya no queda margen para llegar al efecto minimo.
    if hi < EFECTO_MINIMO:
        print(f"[control] PARAR por futilidad: el IC99 no llega a "
              f"{EFECTO_MINIMO:+.2f} ni con los datos que faltan. Mas peleas no "
              f"lo pueden traer.")
        print("PARAR")
        return 0
    print("[control] seguir: la respuesta aun no esta, y ningun otro motivo "
          "para parar esta autorizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
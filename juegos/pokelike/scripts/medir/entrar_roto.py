#!/usr/bin/env python3
"""Las peleas que se pierden entering roto: ¿forzadas o elegidas?

La medicion anterior (`derrota_por_derrota.py`) deja el dato duro:

    vida 0-50%  -> gana el 25%
    vida 50-75% -> gana el 88%
    vida >95%   -> gana el 99,7%

O sea que la vida es el separador, y el corte de emergencia del planificador
(`ratio <= 0.75 or carry_ps < 50`) esta justo donde esta el precipicio. Pero el
corte **solo se aplica si hay un pokecenter a la vista**. Este script mide si las
peelas que se pierden rotoorfueron porque no habia cura, o porque el botTenia
cura en pantalla y aun asi entro.

Si hay cura y entra roto, el cuello es una **decision**. Si no hay cura, el cuello
es la **distancia** al centro, que ya no se arregla con un peso.

    uv run --group dev python juegos/pokelike/scripts/medir/entrar_roto.py
"""
from __future__ import annotations

import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path

LOGS = Path("juegos/pokelike/log")

# El log escupe una linea `DEC nodo` antes de cada decision de mapa, con los
# tipos que habia en pantalla. Es la unica fuente de "habia cura a la vista".
RE_DEC_NODO = re.compile(
    r"DEC nodo .*? disponibles=([\w,]+) .*?razon=(\w+) score=(-?[\d.]+)")
RE_TRAZA = re.compile(
    r"TRAZA_CAMINO paso=(\d+) .*?disp=\[([^\]]*)\].*?vida_media=(\d+)%")
RE_FIN = re.compile(r">>> COMBATE (GANADO|PERDIDO)")
RE_ESTADO = re.compile(r"^\s*estado: (.+?) \| niveles rivales ([\d-]+)$")
RE_ENEMIGOS = re.compile(r"^\s*enemigos=\[(.*)\]\s*$")
RE_MIOS = re.compile(r"^\s*mios=\[(.*)\]\s*$")
RE_COMBATE = re.compile(r"DEC combate .*?tipo=(\w+)")
RE_OBJ = re.compile(r"bolsa: (\[.*\])")


def foto(linea: str) -> list[tuple[str, int, int]]:
    return [(n, int(ps), int(mx)) for n, ps, mx, _ in
            re.findall(r"\('([^']+)', '(\d+)/(\d+)', (\d+)'?\)?", linea)]


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    logs = sorted(LOGS.rglob("h1[7-9]-*.txt"))
    if not logs:
        logs = sorted(LOGS.rglob("*.txt"))

    # Cada decision de nodo, en orden. Se guardan los tipos disponibles para
    # poder mirar "habia cura en la pantalla que decidio esta pelea".
    pasos: list[dict] = []
    peleas: list[dict] = []
    for p in logs:
        txt = p.read_text(encoding="utf-8", errors="replace")
        actual: dict | None = None
        combate_tipo = "?"
        for ln in txt.splitlines():
            m = RE_DEC_NODO.search(ln)
            if m:
                actual = {"disp": set(m.group(1).split(",")),
                          "razon": m.group(2), "log": p.name}
                pasos.append(actual)
                continue
            m = RE_COMBATE.search(ln)
            if m:
                combate_tipo = m.group(1)
            m = RE_ESTADO.match(ln)
            if m:
                actual = dict(actual or {})
                actual["estado"] = m.group(1)
                continue
            m = RE_MIOS.match(ln)
            if m and actual:
                actual["mios"] = foto(m.group(1))
            m = RE_FIN.search(ln)
            if m and actual and actual.get("mios"):
                actual["ganada"] = m.group(1) == "GANADO"
                actual["tipo_rival"] = combate_tipo
                peleas.append(actual)
                actual = None

    if not peleas:
        print("no hay peleas emparejadas con su decision")
        return 0
    print(f"peleas emparejadas con la pantalla que las decidio: {len(peleas)}")

    for p in peleas:
        vida = [ps / mx for _, ps, mx in p["mios"] if mx]
        p["vida"] = st.mean(vida) if vida else 0.0
        p["caidos"] = sum(1 for _, ps, _ in p["mios"] if ps <= 0)

    rotas = [p for p in peleas if p["vida"] < 0.5 or p["caidos"]]
    sanas = [p for p in peleas if p["vida"] >= 0.95 and not p["caidos"]]
    print(f"  entran rotas (<50% o con caido): {len(rotas)}")
    print(f"  entran enteras (>95%):           {len(sanas)}")

    print("\n== AL ENTRAR ROTO: ¿HABA UN POKECENTER EN PANTALLA? ==")
    con_cura = [p for p in rotas if "cura" in p["disp"] or
                "pokecenter" in p["disp"]]
    sin_cura = [p for p in rotas if p not in con_cura]
    print(f"  con cura a la vista   : {len(con_cura):5d}  "
          f"gana {sum(1 for p in con_cura if p['ganada'])/max(len(con_cura),1):6.1%}")
    print(f"  sin cura a la vista  : {len(sin_cura):5d}  "
          f"gana {sum(1 for p in sin_cura if p['ganada'])/max(len(sin_cura),1):6.1%}")

    print("\n== QUE ELIGIO EL BOT EN PANTALLA QUE TENIA CURA Y AUN ASI ==")
    print("   (si aqui gana 'cura' o 'jefe', el corte funciona y no hay cuello)")
    r = Counter(p["razon"] for p in con_cura)
    tot = sum(r.values()) or 1
    for k, v in r.most_common():
        print(f"  {k:12s} {v:5d}  {100*v/tot:5.1f}%")

    print("\n== EL CORTE DE EMERGENCIA, VISTO DESDE SU PROPIA CONDICION ==")
    # El corte dice: si hay cura Y (caidos o ratio<=0.75 o carry<50) -> -5
    # Aqui se mide cuantos pasos cumplieron la condicion con cura disponible.
    fired = [s for s in pasos
             if ("cura" in s["disp"] or "pokecenter" in s["disp"])
             and s["razon"] == "cura"]
    print(f"  pantallas con cura y el bot fue a curar: {len(fired)}")

    print("\n== EL TRAMO ENTRE LA ULTIMA CURA Y LA PELEA ROTA ==")
    print("   (si casi siempre son 0 pasos, es distancia; si son muchos, es gasto)")
    pasos_por_decision = Counter()
    for i, s in enumerate(pasos):
        if s["razon"] == "cura":
            pasos_por_decision[i] = True
    dist = Counter()
    for i, p in enumerate(peleas):
        if p in rotas:
            d = 0
            for j in range(i - 1, max(-1, i - 12), -1):
                if pasos[j].get("razon") == "cura":
                    d = i - j
                    break
            else:
                d = None
            dist[d if d is not None else ">12"] += 1
    for k in sorted(dist, key=lambda x: (isinstance(x, str), x)):
        print(f"  {k!s:>4s} pasos desde la ultima cura: {dist[k]:5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
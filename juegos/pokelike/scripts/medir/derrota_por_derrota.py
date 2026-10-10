#!/usr/bin/env python3
"""Por que se pierde cada pelea, con el estado REAL del equipo en ese momento.

El log guarda una foto de cada combate: los PS de los mones de cada lado. Con
esa foto se responde a la pregunta que el cuaderno dejo abierta ("el nivel y los
tipos no separaban nada"): **que separa ganar de perder**.

A diferencia de `por_que_se_pierde.py`, aqui cada derrota se empareja con la
**victoria inmediatamente anterior del mismo archivo y del mismo rival**, no con
el estado del log en ese instante. Y se separa salvaje de entrenador, porque son
dos poblaciones distintas y mezclarlas ya ha dado una conclusion falsa dos veces.

    uv run --group dev python juegos/pokelike/scripts/medir/derrota_por_derrota.py
"""
from __future__ import annotations

import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

LOGS = Path("juegos/pokelike/log")
RAIZ = Path(__file__).resolve().parents[3]

import sys as _sys

_sys.path.insert(0, str(RAIZ / "juegos/pokelike/scripts"))

# Una pelea: la linea "estado:", sus dos listas y el veredicto que viene despues.
RE_ESTADO = re.compile(r"^\s*estado: (.+?) \| niveles rivales ([\d-]+)$")
RE_ENEMIGOS = re.compile(r"^\s*enemigos=\[(.*)\]\s*$")
RE_MIOS = re.compile(r"^\s*mios=\[(.*)\]\s*$")
RE_FIN = re.compile(r">>> COMBATE (GANADO|PERDIDO)")
RE_DEC_COMBATE = re.compile(r"DEC combate rival=(.+?) wants to battle! "
                            r"tipo=(\w+) nuestro_niv=(\d+) rival_niv=(\d+)")
RE_TIPO_MAPA = re.compile(r"· (.+?): vs (.+?) \((\w+)\) \|")


def foto_bonita(linea: str) -> list[tuple[str, int, int, int]]:
    out = []
    for nombre, ps, max_, niv in re.findall(
            r"\('([^']+)', '(\d+)/(\d+)', (\d+)'?\)?", linea):
        out.append((nombre, int(ps), int(max_), int(niv)))
    return out


def peleas_de(txt: str) -> list[dict]:
    """Saca cada pelea con su foto y su veredicto."""
    peleas = []
    pendiente: dict = {}
    rival_tipo = None
    rival_nombre = ""
    for ln in txt.splitlines():
        m = RE_ESTADO.match(ln)
        if m:
            pendiente = {"estado": m.group(1), "niv_rival": m.group(2)}
            continue
        m = RE_ENEMIGOS.match(ln)
        if m and pendiente:
            pendiente["enemigos"] = foto_bonita(m.group(1))
            continue
        m = RE_MIOS.match(ln)
        if m and pendiente:
            pendiente["mios"] = foto_bonita(m.group(1))
            continue
        m = RE_FIN.search(ln)
        if m and pendiente:
            pendiente["ganada"] = m.group(1) == "GANADO"
            if pendiente.get("mios") and pendiente.get("enemigos"):
                peleas.append(pendiente)
            pendiente = {}
            continue
        m = RE_DEC_COMBATE.search(ln)
        if m:
            rival_tipo = m.group(2)
            rival_nombre = m.group(1)
    for p in peleas:
        p["tipo"] = rival_tipo or "?"
        p["rival"] = rival_nombre
    return peleas


def resumen(p: dict) -> dict:
    mios = p["mios"]
    enemigos = p["enemigos"]
    vida = [ps / max_ for _, ps, max_, _ in mios if max_]
    niveles = [n for _, _, _, n in mios]
    niv_enem = [n for _, _, _, n in enemigos]
    d = {
        "vida_media": st.mean(vida) if vida else 0.0,
        "caidos": sum(1 for _, ps, _, _ in mios if ps <= 0),
        "n_mios": len(mios),
        "niv_max": max(niveles) if niveles else 0,
        "niv_min": min(niveles) if niveles else 0,
        "rival_max": max(niv_enem) if niv_enem else 0,
        "rival_min": min(niv_enem) if niv_enem else 0,
    }
    # Cuantos enemigos sobreviven: la foto de un combate ganado esta a medias
    # porque el log se corta al terminar la pantalla.
    d["enemigos_ps"] = [ps / max_ for _, ps, max_, _ in enemigos if max_]
    return d


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    logs = sorted(p for p in LOGS.rglob("h1[5-9]-*.txt"))
    todas: list[dict] = []
    for p in logs:
        txt = p.read_text(encoding="utf-8", errors="replace")
        for pelea in peleas_de(txt):
            pelea.update(resumen(pelea))
            pelea["log"] = p.name
            todas.append(pelea)

    if not todas:
        print("no hay peleas con foto completa")
        return 0

    print(f"peleas con foto completa: {len(todas)}")
    ganadas = [p for p in todas if p["ganada"]]
    perdidas = [p for p in todas if not p["ganada"]]
    print(f"  ganadas {len(ganadas)}   perdidas {len(perdidas)}")

    print("\n== QUE SEPARA GANAR DE PERDER (todo junto, no por separado) ==")
    print(f"  {'':28s} {'ganadas':>18s}   {'perdidas':>18s}")
    etiquetas = [
        ("vida media del equipo", "vida_media", "{:.1%}"),
        ("caidos en el equipo", "caidos", "{:.2f}"),
        ("niveles de nuestro", "niv_max", "{:.1f}"),
        ("nivel del rival (max)", "rival_max", "{:.1f}"),
        ("diferencia de nivel", "_dif", "{:+.1f}"),
        ("nosotros - rival", "_who", "{:.2f}"),
    ]
    for nombre, key, fmt in etiquetas:
        for grupo in (ganadas, perdidas):
            for p in grupo:
                p["_dif"] = p["niv_max"] - p["rival_max"]
                p["_who"] = (p["niv_max"] >= p["rival_max"])
        a = [p[key] for p in ganadas if key in p]
        b = [p[key] for p in perdidas if key in p]
        if nombre == "niveles de nuestro":
            continue
        if not a or not b:
            continue
        if nombre == "nosotros - rival":
            pa = 100 * sum(a) / len(a) / 1
            pb = 100 * sum(b) / len(b)
            print(f"  {nombre:28s} {pa:17.1f}%   {pb:17.1f}%")
        else:
            print(f"  {nombre:28s} {fmt.format(st.mean(a)):>18s}   "
                  f"{fmt.format(st.mean(b)):>18s}")

    print("\n== VIDA DEL EQUIPO AL EMPEZAR, POR TIPO DE RIVAL ==")
    print(f"  {'':14s} {'n':>5s} {'ganadas':>10s} {'perdidas':>10s} "
          f"{'vida g':>9s} {'vida p':>9s}")
    por_tipo = defaultdict(list)
    for p in todas:
        por_tipo[p["tipo"]].append(p)
    for tipo, grupo in sorted(por_tipo.items(), key=lambda x: -len(x[1])):
        g = [p for p in grupo if p["ganada"]]
        d_ = [p for p in grupo if not p["ganada"]]
        if len(grupo) < 8:
            continue
        vg = st.mean([p["vida_media"] for p in g]) if g else 0
        vp = st.mean([p["vida_media"] for p in d_]) if d_ else 0
        print(f"  {tipo:14s} {len(grupo):5d} {len(g)/len(grupo):9.1%} "
              f"{len(d_)/len(grupo):9.1%} {vg:9.1%} {vp:9.1%}")

    print("\n== EL CORTE DE VIDA REAL: entrar roto = death, entrar sano = no ==")
    print("   (agrupado por la vida media con la que empieza la pelea)")
    cortes = [(0.0, 0.5), (0.5, 0.75), (0.75, 0.95), (0.95, 1.01)]
    print(f"  {'tramo de vida':>16s} {'n':>5s} {'ganadas':>10s}")
    for lo, hi in cortes:
        g = [p for p in todas if lo <= p["vida_media"] < hi]
        if not g:
            continue
        print(f"  {f'{lo:.0%}-{hi:.0%}':>16s} {len(g):5d} "
              f"{sum(1 for p in g if p['ganada'])/len(g):9.1%}")

    print("\n== CON CAIDOS vs SIN CAIDOS ==")
    con = [p for p in todas if p["caidos"] > 0]
    sin = [p for p in todas if p["caidos"] == 0]
    for nombre, g in (("con algun caido", con), ("sin caidos", sin)):
        if g:
            print(f"  {nombre:18s} n={len(g):5d}  gana "
                  f"{sum(1 for p in g if p['ganada'])/len(g):5.1%}  "
                  f"vida media {st.mean([p['vida_media'] for p in g]):5.1%}")

    print("\n== NIVEL: POR DEBAJO O POR ENCIMA DEL RIVAL ==")
    print(f"  {'nuestro max vs rival max':>26s} {'n':>5s} {'gana':>8s}")
    for cond, nombre in ((lambda p: p["niv_max"] < p["rival_max"], "por debajo"),
                         (lambda p: p["niv_max"] >= p["rival_max"], "al nivel o mas")):
        g = [p for p in todas if cond(p)]
        if g:
            print(f"  {nombre:>26s} {len(g):5d} "
                  f"{sum(1 for p in g if p['ganada'])/len(g):7.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
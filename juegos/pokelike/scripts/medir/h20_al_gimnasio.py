"""H20: ¿por qué el bot llega roto al gimnasio?

Fuentes de datos:
  - `ps_abre_equipo` (23 gimnasios): ground truth del texto al abrir la pelea.
  - `mios` de la pelea de gimnasio (todos): texto del combate, pero leído
    "ya empezada" — incluye daño de los primeros turnos. Es un proxy con
    sesgo: un equipo sano que pierde un món rápido parece "entrada rota".

Estrategia: medir con ps_abre donde haya, calibrar el sesgo con mios en los
mismos 23, y extrapolar al resto con el proxy advertido.

    uv run --group dev python juegos/pokelike/scripts/medir/h20_al_gimnasio.py
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[4] / "juegos/pokelike/log/corpus.db"

PS = re.compile(r"^(\d+)\s*/\s*(\d+)$")


def parsear_mios(mios: str) -> list[tuple[str, int, int]]:
    """Del campo `mios=[...]` saca [(nombre, ps, ps_max), ...]."""
    import ast
    try:
        lista = ast.literal_eval(mios)
    except (ValueError, SyntaxError):
        return []
    out = []
    for item in lista:
        # item = {'nombre': 'Bulbasaur Lv5', 'ps': 19, 'ps_max': 19}
        ps = item.get("ps", 0)
        mx = item.get("ps_max", 0)
        nom = item.get("nombre", "")
        out.append((nom, int(ps), int(mx)))
    return out


def parsear_ps_abre(equipo: str) -> list[tuple[str, int, int]]:
    """Del campo `equipo=` de ps_abre saca [(nombre, ps, ps_max), ...]."""
    out = []
    for trozo in equipo.split(","):
        m = PS.search(trozo.strip())
        if not m:
            continue
        nom = trozo.strip()[: m.start()].strip()
        out.append((nom, int(m.group(1)), int(m.group(2))))
    return out


def resumen(ps: list[tuple[str, int, int]]) -> dict:
    if not ps:
        return {"pct": 0, "heridos": 0, "caidos": 0, "n": 0}
    total = sum(p for _, p, _ in ps)
    maximo = sum(m for _, _, m in ps)
    return {
        "pct": round(100 * total / maximo, 1) if maximo else 0,
        "heridos": sum(1 for _, p, m in ps if m > 0 and p < m),
        "caidos": sum(1 for _, p, m in ps if m > 0 and p == 0),
        "n": len(ps),
    }


def main() -> int:
    if not DB.exists():
        print("no hay corpus.db. Ejecuta pkl_corpus.py primero.")
        return 1
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    gimnasios = con.execute("""
        SELECT id, run_id, orden, rival, ps_abre_equipo, mios
        FROM pelea WHERE rival LIKE '%Gym Battle%' ORDER BY run_id, orden
    """).fetchall()
    print(f"batallas de gimnasio en el corpus: {len(gimnasios)}")
    if not gimnasios:
        return 0

    # --- Medición con ps_abre (ground truth) ---
    con_ps = [g for g in gimnasios if g["ps_abre_equipo"]]
    print(f"con ps_abre (ground truth): {len(con_ps)}")

    rotas_ps = 0
    for g in con_ps:
        ps = parsear_ps_abre(g["ps_abre_equipo"])
        r = resumen(ps)
        if r["pct"] < 99 or r["caidos"] > 0:
            rotas_ps += 1
    if con_ps:
        print(f"  entrada rota según ps_abre: {rotas_ps} ({100*rotas_ps/len(con_ps):.1f}%)")

    # --- Medición con mios (proxy con sesgo) ---
    con_mios = [g for g in gimnasios if g["mios"]]
    print(f"con mios (proxy): {len(con_mios)}")

    rotas_mios = 0
    for g in con_mios:
        ps = parsear_mios(g["mios"])
        r = resumen(ps)
        if r["pct"] < 99 or r["caidos"] > 0:
            rotas_mios += 1
    if con_mios:
        print(f"  entrada rota según mios: {rotas_mios} ({100*rotas_mios/len(con_mios):.1f}%)")

    # --- Calibración: sesgo del proxy en los que tienen ambos ---
    ambos = [g for g in gimnasios if g["ps_abre_equipo"] and g["mios"]]
    print(f"\ncalibración (tienen ambos): {len(ambos)}")
    if ambos:
        rotas_ps2 = sum(1 for g in ambos
                        if resumen(parsear_ps_abre(g["ps_abre_equipo"]))["pct"] < 99)
        rotas_mios2 = sum(1 for g in ambos
                          if resumen(parsear_mios(g["mios"]))["pct"] < 99)
        print(f"  rotas según ps_abre: {rotas_ps2}")
        print(f"  rotas según mios:   {rotas_mios2}")
        if rotas_mios2 > rotas_ps2:
            print(f"  sesgo del proxy: +{100*(rotas_mios2-rotas_ps2)/len(ambos):.1f} puntos "
                  f"(el mios marca 'rota' cuando el ps_abre dice sana)")

    # --- Causas: ¿eligió cura antes del gimnasio? ---
    print(f"\ncausas de entrada rota:")
    causa_counter = Counter()
    for g in gimnasios:
        ps = parsear_mios(g["mios"]) if g["mios"] else parsear_ps_abre(g["ps_abre_equipo"] or "")
        r = resumen(ps)
        if r["pct"] >= 99 and r["caidos"] == 0:
            continue

        rid, orden = g["run_id"], g["orden"]
        nodos_antes = con.execute("""
            SELECT disponibles, razon FROM nodo
            WHERE run_id=? AND orden < ? ORDER BY orden DESC LIMIT 5
        """, (rid, orden)).fetchall()

        habia_cura = any("cura" in (n["disponibles"] or "") for n in nodos_antes)
        eligio_cura = any("cura" in (n["razon"] or "") for n in nodos_antes)

        if habia_cura and not eligio_cura:
            causa_counter["no_elige_cura"] += 1
        elif not habia_cura:
            causa_counter["sin_pokecenter"] += 1
        else:
            causa_counter["cura_insuficiente"] += 1

    for k, v in causa_counter.most_common():
        print(f"  {k:<20} {v:>4}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

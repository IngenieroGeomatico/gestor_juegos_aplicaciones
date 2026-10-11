"""¿Cuál es el cuello de la pelea del gimnasio?

Ya sabemos que el bot llega sano al gimnasio (H20 cerrada). Ahora medimos
qué causa las derrotas: nivel insuficiente, mala cobertura de tipos, o
gestión de la pelea.

Mide sobre el corpus:
  1. Diferencia de nivel: nuestro_niv vs rival_niv
  2. Cobertura de tipos: quién del equipo contraataca al líder
  3. Resultado: GANADO vs PERDIDO
  4. Correlación entre nivel/cobertura y resultado

    uv run --group dev python juegos/pokelike/scripts/medir/cuello_gimnasio.py
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[4] / "juegos/pokelike/log/corpus.db"

# Cargar el chart del juego (NO es el oficial Gen6)
RAIZ = Path(__file__).resolve().parents[4]
CHART = RAIZ / "juegos/pokelike/data/chart_juego.json"
SCRIPTS = RAIZ / "juegos/pokelike/scripts"
sys.path.insert(0, str(SCRIPTS))

from data_store import tipos_de_especie  # noqa: E402


def cargar_chart() -> dict:
    """Chart del juego: tipo -> {debilidades, resistencias, inmunidades}."""
    data = json.loads(CHART.read_text(encoding="utf-8"))
    # data puede ser dict tipo->dict o lista de {tipo, debilidades...}
    if isinstance(data, dict):
        return data
    return {x["tipo"]: x for x in data}


def cargar_tipos() -> dict:
    """Nombre de tipo -> nombre canónico."""
    data = json.loads(TIPOS.read_text(encoding="utf-8"))
    return data


def parsear_tipos_equipo(mios: str) -> list[list[str]]:
    """Del campo mios=[...] saca los tipos de cada món usando data_store."""
    try:
        lista = ast.literal_eval(mios)
    except (ValueError, SyntaxError):
        return []
    out = []
    for item in lista:
        nombre = item.get("nombre", "")
        tipos = tipos_de_especie(nombre)
        if tipos:
            out.append(tipos)
    return out


def main() -> int:
    if not DB.exists():
        print("no hay corpus.db. Ejecuta pkl_corpus.py primero.")
        return 1

    chart = cargar_chart()
    gimnasios_data = json.loads(
        (RAIZ / "juegos/pokelike/data/regiones.json").read_text(encoding="utf-8")
    )

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Batallas de gimnasio
    gimnasios = con.execute("""
        SELECT id, run_id, rival, nuestro_niv, rival_niv, resultado, mios,
               nivel_min, nivel_max
        FROM pelea WHERE rival LIKE '%Gym Battle%'
    """).fetchall()

    print(f"batallas de gimnasio: {len(gimnasios)}")
    if not gimnasios:
        return 0

    # 1. Diferencia de nivel
    print("\n=== 1. Diferencia de nivel (nuestro vs rival) ===")
    diff_nivel = []
    for g in gimnasios:
        if g["nuestro_niv"] and g["rival_niv"]:
            diff_nivel.append(g["nuestro_niv"] - g["rival_niv"])

    if diff_nivel:
        print(f"  media: {sum(diff_nivel)/len(diff_nivel):+.1f}")
        print(f"  min: {min(diff_nivel)}  max: {max(diff_nivel)}")
        # Por resultado
        ganados = [g["nuestro_niv"] - g["rival_niv"] for g in gimnasios
                   if g["resultado"] == "GANADO" and g["nuestro_niv"] and g["rival_niv"]]
        perdidos = [g["nuestro_niv"] - g["rival_niv"] for g in gimnasios
                    if g["resultado"] == "PERDIDO" and g["nuestro_niv"] and g["rival_niv"]]
        if ganados:
            print(f"  GANADO: media {sum(ganados)/len(ganados):+.1f} (n={len(ganados)})")
        if perdidos:
            print(f"  PERDIDO: media {sum(perdidos)/len(perdidos):+.1f} (n={len(perdidos)})")

    # 2. Resultados por gimnasio
    print("\n=== 2. Resultados por gimnasio ===")
    por_gimnasio = {}
    for g in gimnasios:
        r = g["rival"]
        if r not in por_gimnasio:
            por_gimnasio[r] = {"GANADO": 0, "PERDIDO": 0}
        por_gimnasio[r][g["resultado"]] = por_gimnasio[r].get(g["resultado"], 0) + 1

    for r, counts in sorted(por_gimnasio.items()):
        total = counts.get("GANADO", 0) + counts.get("PERDIDO", 0)
        pct = 100 * counts.get("GANADO", 0) / total if total else 0
        print(f"  {r:<35} {counts.get('GANADO', 0):>4}/{total:<4} ({pct:.0f}%)")

    # 3. Cobertura de tipos (simplificada: ¿hay algún món que contraataca?)
    print("\n=== 3. Cobertura de tipos (¿hay quien contraataque?) ===")
    # Necesitamos el tipo del líder. Para Kanto:
    kanto_jefes = {
        "Gym Battle vs Brock!": "Rock",
        "Gym Battle vs Misty!": "Water",
        "Gym Battle vs Lt. Surge!": "Electric",
        "Gym Battle vs Erika!": "Grass",
        "Gym Battle vs Koga!": "Poison",
        "Gym Battle vs Sabrina!": "Psychic",
        "Gym Battle vs Blaine!": "Fire",
        "Gym Battle vs Giovanni!": "Ground",
    }

    cobertura_counter = Counter()
    for g in gimnasios:
        tipo_lider = kanto_jefes.get(g["rival"], "")
        if not tipo_lider:
            continue

        mios_tipos = parsear_tipos_equipo(g["mios"] or "")
        if not mios_tipos:
            continue

        # ¿Hay algún món cuyo tipo contraataca al líder?
        # chart[atacante][defensor] = multiplicador de daño
        # Si chart[t][tipo_lider] > 1, el tipo t contraataca al líder
        contraataca = False
        for tipos_m in mios_tipos:
            for t in tipos_m:
                if chart.get(t, {}).get(tipo_lider, 1) > 1:
                    contraataca = True
                    break
            if contraataca:
                break

        resultado = g["resultado"]
        if contraataca:
            cobertura_counter[("contraataca", resultado)] += 1
        else:
            cobertura_counter[("no_contraataca", resultado)] += 1

    print("  cobertura × resultado:")
    for (cobertura, resultado), n in sorted(cobertura_counter.items()):
        print(f"    {cobertura:<15} {resultado:<8} {n:>4}")

    # ¿Diferencia de éxito?
    tot_contra = cobertura_counter.get(("contraataca", "GANADO"), 0) + cobertura_counter.get(("contraataca", "PERDIDO"), 0)
    tot_sin = cobertura_counter.get(("no_contraataca", "GANADO"), 0) + cobertura_counter.get(("no_contraataca", "PERDIDO"), 0)
    if tot_contra and tot_sin:
        pct_contra = 100 * cobertura_counter.get(("contraataca", "GANADO"), 0) / tot_contra
        pct_sin = 100 * cobertura_counter.get(("no_contraataca", "GANADO"), 0) / tot_sin
        print(f"  éxito con cobertura: {pct_contra:.0f}%  sin cobertura: {pct_sin:.0f}%")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

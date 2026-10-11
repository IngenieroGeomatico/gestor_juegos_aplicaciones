"""Alcance de la estrategia "solo pelear con ventaja".

El usuario propone: Bulbasaur solo debería abrir la pelea cuando tenga
ventaja clara contra el rival. Si no, otro món abre.

Esto es más conservador que la política actual (orden_para_jefe), que pone
al món que más pega y aguante — incluido Bulbasaur si tiene ventaja.

Mide sobre el corpus:
  1. ¿Cuántas peleas de entrenador hay donde Bulbasaur está en el equipo?
  2. ¿Cuántas de esas ganó el bot?
  3. ¿Cuántas de esas perdió con Bulbasaur caído al abrir?
  4. Estimación: si Bulbasaur solo abriera con ventaja, ¿cuántas más ganaría?

    uv run --group dev python juegos/pokelike/scripts/medir/alcance_reservar.py
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[4] / "juegos/pokelike/log/corpus.db"
RAIZ = Path(__file__).resolve().parents[4]
CHART = RAIZ / "juegos/pokelike/data/chart_juego.json"


def parsear_mios(mios: str) -> list[dict]:
    """Del campo mios=[...] saca la lista de móns."""
    try:
        lista = ast.literal_eval(mios)
    except (ValueError, SyntaxError):
        return []
    out = []
    for item in lista:
        out.append({
            "nombre": item.get("nombre", ""),
            "ps": int(item.get("ps", 0)),
            "ps_max": int(item.get("ps_max", 0)),
        })
    return out


def tiene_ventaja(tipos_m: list[str], tipos_rival: list[str], chart: dict) -> bool:
    """¿Tiene ventaja el món contra el rival?"""
    for t in tipos_m:
        for r in tipos_rival:
            if chart.get(t, {}).get(r, 1) > 1:
                return True
    return False


def main() -> int:
    if not DB.exists():
        print("no hay corpus.db")
        return 1

    chart = json.loads(CHART.read_text(encoding="utf-8"))

    # Tipos de Bulbasaur (Planta/Veneno)
    tipos_bulbasaur = ["Grass", "Poison"]

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Todas las peleas de entrenador (no salvajes)
    peleas = con.execute("""
        SELECT id, rival, resultado, mios, tipo
        FROM pelea WHERE tipo='entrenador'
    """).fetchall()

    print(f"peleas de entrenador: {len(peleas)}")

    # Contadores
    total_con_bulbasaur = 0
    ganadas_con_bulbasaur = 0
    perdidas_con_bulbasaur = 0
    perdidas_con_bulbasaur_caido = 0
    ganadas_con_bulbasaur_caido = 0

    # Para la estimación: peleas donde Bulbasaur NO tiene ventaja (usamos tipos del rival)
    # Como no tenemos los tipos del rival directamente, usamos el nombre del rival
    # para inferir el tipo en gimnasios, y para entrenadores normales asumimos
    # que Bulbasaur tiene ventaja si el rival no es de tipo Agua/Roca/Hielo/Volador

    # Contadores para la estimación
    peleas_sin_ventaja = 0
    perdidas_sin_ventaja = 0

    for p in peleas:
        mios = parsear_mios(p["mios"] or "")
        if not mios:
            continue

        # ¿Bulbasaur está en el equipo?
        bulbasaur = None
        for m in mios:
            if "Bulbasaur" in m["nombre"] or "Ivysaur" in m["nombre"] or "Venusaur" in m["nombre"]:
                bulbasaur = m
                break

        if not bulbasaur:
            continue

        total_con_bulbasaur += 1
        if p["resultado"] == "GANADO":
            ganadas_con_bulbasaur += 1
            if bulbasaur["ps"] == 0:
                ganadas_con_bulbasaur_caido += 1
        else:
            perdidas_con_bulbasaur += 1
            if bulbasaur["ps"] == 0:
                perdidas_con_bulbasaur_caido += 1

        # Estimación: ¿Bulbasaur tiene ventaja contra el rival?
        # Si el rival es un gimnasio, sabemos el tipo
        rival_lower = p["rival"].lower()
        tipos_rival = []
        if "brock" in rival_lower:
            tipos_rival = ["Rock"]
        elif "misty" in rival_lower:
            tipos_rival = ["Water"]
        elif "surge" in rival_lower:
            tipos_rival = ["Electric"]
        elif "erika" in rival_lower:
            tipos_rival = ["Grass"]
        elif "koga" in rival_lower:
            tipos_rival = ["Poison"]
        elif "sabrina" in rival_lower:
            tipos_rival = ["Psychic"]
        elif "blaine" in rival_lower:
            tipos_rival = ["Fire"]
        elif "giovanni" in rival_lower:
            tipos_rival = ["Ground"]
        else:
            # Entrenador normal: asumimos tipos comunes
            # Bulbasaur (Planta) es fuerte contra: Water, Ground, Rock
            # Bulbasaur (Veneno) es fuerte contra: Grass, Fairy
            # No podemos saberlo sin los tipos del rival, así que contamos
            # solo las peleas donde sabemos que Bulbasaur NO tiene ventaja
            # (contra Misty/Agua y Erika/Planta/Veneno)
            if "misty" in rival_lower or "erika" in rival_lower:
                tipos_rival = ["Water"] if "misty" in rival_lower else ["Grass"]
                if not tiene_ventaja(tipos_bulbasaur, tipos_rival, chart):
                    peleas_sin_ventaja += 1
                    if p["resultado"] == "PERDIDO":
                        perdidas_sin_ventaja += 1

    print(f"\npeleas con Bulbasaur en el equipo: {total_con_bulbasaur}")
    print(f"  ganadas: {ganadas_con_bulbasaur} ({100*ganadas_con_bulbasaur/total_con_bulbasaur:.1f}%)")
    print(f"  perdidas: {perdidas_con_bulbasaur} ({100*perdidas_con_bulbasaur/total_con_bulbasaur:.1f}%)")
    print(f"  perdidas con Bulbasaur caído al abrir: {perdidas_con_bulbasaur_caido}")
    print(f"  ganadas con Bulbasaur caído al abrir: {ganadas_con_bulbasaur_caido}")

    print(f"\nestimación (solo gimnasios con tipo conocido):")
    print(f"  peleas donde Bulbasaur NO tiene ventaja: {peleas_sin_ventaja}")
    print(f"  perdidas en esas peleas: {perdidas_sin_ventaja}")
    if peleas_sin_ventaja:
        print(f"  tasa de derrota sin ventaja: {100*perdidas_sin_ventaja/peleas_sin_ventaja:.1f}%")

    print(f"\nestimación de alcance:")
    print(f"  Si Bulbasaur solo abriera con ventaja, se ahorraría caer en")
    print(f"  {perdidas_con_bulbasaur_caido} derrotas donde cayó al abrir.")
    print(f"  Si el bot ganara la mitad de esas, serían ~{perdidas_con_bulbasaur_caido//2} victorias extra.")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

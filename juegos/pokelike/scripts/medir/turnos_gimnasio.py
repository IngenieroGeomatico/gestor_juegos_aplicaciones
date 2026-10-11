"""¿Qué pasa en los primeros turnos de la pelea del gimnasio?

La sonda registra el estado del equipo en cada paso. Para una pelea de
gimnasio, hay tres registros clave:
  1. mapa ANTES del gimnasio → estado al llegar (sano)
  2. pelea del gimnasio → estado al abrir (ya empezada, con daño de primeros turnos)
  3. mapa DESPUÉS del gimnasio → estado después de la pelea

La diferencia entre (1) y (2) es el daño de los primeros turnos.
La diferencia entre (2) y (3) es el daño del resto de la pelea.

    uv run --group dev python juegos/pokelike/scripts/medir/turnos_gimnasio.py <dir_sonda>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PS = re.compile(r"^(\d+)\s*/\s*(\d+)$")


def cargar_sonda(dir_sonda: Path) -> list[dict]:
    """Carga todos los registros de sonda de un directorio."""
    out = []
    for f in sorted(dir_sonda.glob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            r["_fich"] = f.name
            out.append(r)
    return out


def estado_de(registro: dict) -> dict:
    """Estado del equipo desde el campo `lado` (texto, ground truth)."""
    out = {}
    for x in registro.get("lado") or []:
        m = PS.match((x.get("hp") or "").strip())
        if not m:
            continue
        nom = re.sub(r"\s*Lv\.?\s*\d+\s*$", "", (x.get("nombre") or "").strip())
        ps, mx = int(m.group(1)), int(mroup(2))
        if mx > 0:
            out[nom] = (ps, mx)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: turnos_gimnasio.py <dir_sonda>")
        return 1

    dir_sonda = Path(sys.argv[1])
    if not dir_sonda.exists():
        print(f"no existe {dir_sonda}")
        return 1

    sonda = cargar_sonda(dir_sonda)
    if not sonda:
        print(f"sin registros en {dir_sonda}")
        return 1

    print(f"{len(sonda)} registros de sonda en {dir_sonda}")
    print()

    # Encontrar peleas de gimnasio y sus registros mapa antes/después
    for i, r in enumerate(sonda):
        if r.get("etiqueta") != "pelea":
            continue

        # ¿Es una pelea de gimnasio? Buscar en los enemigos o en el fichero
        es_gym = any("Gym" in str(e) for e in (r.get("enemigos") or []))
        if not es_gym:
            # Buscar en el log por el PID
            continue

        # Registro mapa antes (el más cercano antes de esta pelea)
        mapa_antes = None
        for j in range(i - 1, -1, -1):
            if sonda[j].get("etiqueta") == "mapa":
                mapa_antes = sonda[j]
                break

        # Registro mapa después (el más cercano después de esta pelea)
        mapa_después = None
        for j in range(i + 1, len(sonda)):
            if sonda[j].get("etiqueta") == "mapa":
                mapa_después = sonda[j]
                break

        estado_pelea = estado_de(r)
        estado_antes = estado_de(mapa_antes) if mapa_antes else {}
        estado_desp = estado_de(mapa_después) if mapa_después else {}

        print(f"pelea paso={r.get('paso')} ({r.get('pantalla')})")
        print(f"  al llegar:   {len(estado_antes)} móns, "
              f"caidos={sum(1 for p, m in estado_antes.values() if p == 0)}")
        print(f"  al abrir:    {len(estado_pelea)} móns, "
              f"caidos={sum(1 for p, m in estado_pelea.values() if p == 0)}")
        print(f"  al cerrar:   {len(estado_desp)} móns, "
              f"caidos={sum(1 for p, m in estado_desp.values() if p == 0)}")

        # Daño de los primeros turnos
        if estado_antes and estado_pelea:
            comunes = set(estado_antes) & set(estado_pelea)
            if comunes:
                daño = sum(estado_antes[k][0] - estado_pelea[k][0]
                           for k in comunes if estado_antes[k][0] > estado_pelea[k][0])
                print(f"  daño primeros turnos: {daño} PS")

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

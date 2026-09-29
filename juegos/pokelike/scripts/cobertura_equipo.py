"""Analiza la cobertura de un equipo de Pokelike frente a una región.

Tipos de golpe de cada miembro (por sus tipos) contra cada jefe de gimnasio de
la región, y reporta: jefes mal cubiertos (sin golpe superefectivo) y el mejor
contraataque disponible. Ayuda al agente a decidir capturas/trades y orden de
equipo antes de un jefe.

Uso:
  uv run juegos/pokelike/scripts/cobertura_equipo.py --pokemon Gyarados --pokemon Arcanine [--region Hoenn]
"""

from __future__ import annotations

import argparse

from data_store import (
    efectividad_total,
    jefes_de_region,
    regiones,
    tipos_de_especie,
)


def principal() -> int:
    parser = argparse.ArgumentParser(description="Cobertura de equipo de Pokelike frente a una región.")
    parser.add_argument("--pokemon", action="append", default=[], help="Miembro del equipo (nombre del pool).")
    parser.add_argument("--region", default=None, help="Región a preparar (Kanto, Johto, Hoenn, Sinnoh, Unova).")
    args = parser.parse_args()

    if not args.pokemon:
        print("Indica el equipo con --pokemon (repetible).")
        return 2

    especies: list[tuple[str, list[str]]] = []
    desconocidos = []
    for nombre in args.pokemon:
        tipos = tipos_de_especie(nombre)
        if tipos is None:
            desconocidos.append(nombre)
        else:
            especies.append((nombre, tipos))
    for d in desconocidos:
        print(f"aviso: '{d}' no está en data/pokemon.json (no se evalúa su cobertura).")

    jefes = jefes_de_region(args.region)
    if not jefes:
        print(f"aviso: región '{args.region}' no encontrada. Regiones: {', '.join(sorted(regiones()))}.")

    if not especies:
        return 1

    print("Cobertura ofensiva por jefe:")
    for tipo_jefe in jefes:
        mejor = (1.0, None)
        presentes: list[str] = []
        for nombre, tipos in especies:
            mult = max(efectividad_total(t, [tipo_jefe]) for t in tipos)
            presentes.append(f"{nombre}:{mult:g}")
            if mult > mejor[0]:
                mejor = (mult, nombre)
        etiqueta = f"-> {mejor[1]}" if mejor[1] and mejor[0] > 1 else "sin golpe fuerte"
        print(f"  {tipo_jefe:<10} {', '.join(presentes)} | {etiqueta}")

    notas = [
        f"  {nombre} ({'/'.join(tipos)})" for nombre, tipos in especies
    ]
    print("\nEquipo analizado:")
    print("\n".join(notas))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
"""Generador de sets competitivos para Pokémon Champions.

Recomienda naturaleza, EVs, objeto, habilidad y rol para una especie a partir
de sus stats base y tipos. Los datos salen de data/pokedex.json y los
movimientos recomendados de data/movimientos.json (si existen).

Ejemplo:
    uv run juegos/pokemon-champions/scripts/generador_set.py --pokemon "Groudon"
    uv run juegos/pokemon-champions/scripts/generador_set.py --pokemon "Rayquaza" --rol tanque
"""

from __future__ import annotations

import argparse
import sys

import data_store as ds

NATURALEZAS = {
    "sweeper_fisico_rapido": ("Alegre", "+Velocidad, -Atq.Esp."),
    "sweeper_fisico_potente": ("Firme", "+Atq., -Atq.Esp."),
    "sweeper_especial_rapido": ("Miedo", "+Velocidad, -Atq."),
    "sweeper_especial_potente": ("Modesto", "+Atq.Esp., -Atq."),
    "tanque_fisico": ("Agitado", "+Def., -Atq.Esp."),
    "tanque_especial": ("Sereno", "+Def.Esp., -Atq."),
    "defensivo": ("Cauteloso", "+Def.Esp., -Atq.Esp."),
    "utilidad": ("Sereno", "+Def.Esp., -Atq."),
    "mixto": ("Serio", "neutral"),
}


def _naturaleza(rol: str, s: dict) -> tuple[str, str]:
    vel = s.get("velocidad", 0)
    if rol == "sweeper_fisico":
        return NATURALEZAS["sweeper_fisico_rapido" if vel >= 100 else "sweeper_fisico_potente"]
    if rol == "sweeper_especial":
        return NATURALEZAS["sweeper_especial_rapido" if vel >= 100 else "sweeper_especial_potente"]
    if rol == "tanque":
        fisico = s.get("defensa", 0)
        especial = s.get("defensa_esp", 0)
        return NATURALEZAS["tanque_fisico" if fisico >= especial else "tanque_especial"]
    return NATURALEZAS[rol]

OBJETOS = {
    "sweeper_fisico": ["Orbe Vital", "Cinta Elegida", "Pañuelo Elegido"],
    "sweeper_especial": ["Orbe Vital", "Gafas Elegidas", "Pañuelo Elegido"],
    "tanque": ["Restos", "Chaleco Asalto", "Botas Pesadas"],
    "defensivo": ["Restos", "Casco Dentado", "Botas Pesadas"],
    "utilidad": ["Botas Pesadas", "Baya Zidra"],
}

ROLES = ("sweeper_fisico", "sweeper_especial", "tanque", "defensivo", "utilidad")


def _analizar(especie: dict) -> dict:
    s = ds.stats(especie)
    fisico = s.get("ataque", 0)
    especial = s.get("ataque_esp", 0)
    vel = s.get("velocidad", 0)
    ps = s.get("ps", 0)
    if max(fisico, especial) < 80:
        return "tanque" if ps >= 90 else "utilidad"
    if vel >= 100:
        return "sweeper_fisico" if fisico >= especial else "sweeper_especial"
    if fisico >= especial:
        return "sweeper_fisico" if vel >= 75 else "tanque"
    return "sweeper_especial" if vel >= 75 else "tanque"


def _evs(rol: str, s: dict) -> dict[str, int]:
    if rol in ("sweeper_fisico",):
        return {"ps": 0, "ataque": 252, "defensa": 4, "ataque_esp": 0, "defensa_esp": 0, "velocidad": 252}
    if rol == "sweeper_especial":
        return {"ps": 0, "ataque": 0, "defensa": 4, "ataque_esp": 252, "defensa_esp": 0, "velocidad": 252}
    if rol == "tanque":
        return {"ps": 252, "ataque": 0, "defensa": 252, "ataque_esp": 0, "defensa_esp": 4, "velocidad": 0}
    if rol == "defensivo":
        return {"ps": 252, "ataque": 0, "defensa": 4, "ataque_esp": 0, "defensa_esp": 252, "velocidad": 0}
    return {"ps": 252, "ataque": 0, "defensa": 4, "ataque_esp": 0, "defensa_esp": 0, "velocidad": 252}


def _movimientos(especie: dict, rol: str) -> list[str]:
    movs = [m for m in ds.movimientos() if m.get("nombre") in especie.get("movimientos", [])]
    stab = especie.get("tipos", [])
    movs.sort(key=lambda m: 0 if m.get("tipo") in stab else 1)
    sugeridos: list[str] = []
    for m in movs:
        if m.get("categoria") == "Estado" and rol == "sweeper_fisico":
            continue
        sugeridos.append(m.get("nombre", ""))
        if len(sugeridos) == 4:
            break
    if len(sugeridos) < 4:
        print("  Nota: rellena los movimientos restantes desde la lista de movimientos del Pokémon.")
    return sugeridos


def generar(nombre: str, rol: str | None) -> int:
    especie = ds.buscar_especie(nombre)
    if especie is None:
        print(f"Error: '{nombre}' no está en data/pokedex.json")
        return 1
    if not especie.get("tipos"):
        print(f"Error: '{nombre}' no tiene tipos definidos en la pokedex")
        return 1

    rol = rol or _analizar(especie)
    if rol not in ROLES:
        print(f"Error: rol '{rol}' no válido. Válidos: {', '.join(ROLES)}")
        return 1

    s = ds.stats(especie)
    naturaleza = _naturaleza(rol, s)
    objetos = OBJETOS.get(rol, ["Restos"])
    evs = _evs(rol, s)

    print(f"\n=== Set competitivo: {especie['nombre']} ===")
    print(f"Tipos: {'/'.join(especie['tipos'])}")
    if especie.get("legendario"):
        print("Estatus: LEGENDARIO")
    print(f"Rol: {rol}")
    print(f"Naturaleza: {naturaleza[0]} ({naturaleza[1]})")
    print("IVs: 31 en todas las stats (o 0 en ataque si es especial y no usa Fuerza Bruta)")
    ev_txt = ", ".join(f"{k.capitalize()}: {v}" for k, v in evs.items() if v)
    print(f"EVs: {ev_txt}")
    print(f"Objeto: {', '.join(objetos)}")
    if especie.get("habilidades"):
        print(f"Habilidad: {', '.join(especie['habilidades'])}")

    movs = _movimientos(especie, rol)
    if movs:
        print(f"Movimientos: {', '.join(movs)}")

    if rol.startswith("sweeper"):
        print(f"Resumen: aprovecha la velocidad {'(base ' + str(s.get('velocidad')) + ')' if s.get('velocidad') else ''} "
              f"para golpear primero y eliminar rivales. Cuida de entrar contra enemigos que le resistan.")
    else:
        print("Resumen: aguanta golpes, apoya al equipo y castiga con su rol defensivo.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera un set competitivo para una especie")
    parser.add_argument("--pokemon", required=True, help="Nombre del Pokémon")
    parser.add_argument("--rol", default=None, choices=ROLES, help="Rol (por defecto se deduce de las stats)")
    args = parser.parse_args()
    sys.exit(generar(args.pokemon, args.rol))


if __name__ == "__main__":
    main()
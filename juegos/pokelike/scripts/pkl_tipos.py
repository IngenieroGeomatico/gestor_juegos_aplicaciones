"""Chart de tipos de Pokelike,Traducido al inglés que usa el juego.

El repo guarda el chart en español (`data/tipos.json`); el juego lo muestra en
inglés (`Grass`, `Poison`…). Este módulo traduce y normaliza para poder razonar
sobre la cobertura del equipo.

El tipo de un Pokémon **no se inventa**: sale de `window.__POKEDEX__` del
propio juego, que es la misma fuente que usa la UI.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "tipos.json"

# Español (repo) -> inglés (juego)
ES_A_EN = {
    "Normal": "Normal",
    "Fuego": "Fire",
    "Agua": "Water",
    "Planta": "Grass",
    "Electrico": "Electric",
    "Eléctrico": "Electric",
    "Hielo": "Ice",
    "Lucha": "Fighting",
    "Veneno": "Poison",
    "Tierra": "Ground",
    "Volador": "Flying",
    "Psiquico": "Psychic",
    "Bicho": "Bug",
    "Roca": "Rock",
    "Fantasma": "Ghost",
    "Dragon": "Dragon",
    # Sinestro y Oscuro son el mismo tipo. El nombre canónico en español de
    # Pokémon es "Siniestro", pero en la tabla del repo y en el fichero de
    # regiones aparecía "Oscuro", y `normalizar` no lo traducía: devolvía la
    # palabra tal cual, que no está en el chart, así que **todo** el cálculo de
    # tipos contra un jefe Siniestro salía como multiplicador neutro (1.0).
    "Siniestro": "Dark",
    "Oscuro": "Dark",
    "Acero": "Steel",
    "Hada": "Fairy",
}
EN_A_ES = {v: k for k, v in ES_A_EN.items()}

MULTIPLICADORES = {2.0: "super", 0.5: "resist", 0.0: "inmune"}


def normalizar(tipo: str) -> str:
    """Acepta 'Planta' o 'Grass' y devuelve el nombre canónico inglés."""
    t = (tipo or "").strip()
    if t in EN_A_ES:
        return t
    for es, en in ES_A_EN.items():
        if t.lower() == es.lower():
            return en
    return t  # sin traducir: se devuelve tal cual y se ignora en el cálculo


@lru_cache(maxsize=1)
def _chart() -> dict[str, dict[str, set[str]]]:
    """{tipo_defensor: {'super': set, 'resist': set, 'inmune': set}} en inglés."""
    datos = json.loads(DATA.read_text(encoding="utf-8"))["tipos"]
    out: dict[str, dict[str, set[str]]] = {}
    for fila in datos:
        d = normalizar(fila["tipo"])
        out[d] = {
            "super": {normalizar(x) for x in fila.get("debilidades", [])},
            "resist": {normalizar(x) for x in fila.get("resistencias", [])},
            "inmune": {normalizar(x) for x in fila.get("inmunidades", [])},
        }
    return out


def tipos_que_derrotan(tipo_defensor: str) -> set[str]:
    """Tipos de ataque Effectiveness 2x contra `tipo_defensor`."""
    return set(_chart().get(normalizar(tipo_defensor), {}).get("super", ()))


def tipos_resistidos_por(tipo_defensor: str) -> set[str]:
    """Tipos de ataque que `tipo_defensor` bloquea a 0.5x."""
    return set(_chart().get(normalizar(tipo_defensor), {}).get("resist", ()))


def tipos_inmunes_contra(tipo_defensor: str) -> set[str]:
    """Tipos de ataque inmutables contra `tipo_defensor`."""
    return set(_chart().get(normalizar(tipo_defensor), {}).get("inmune", ()))


def multiplicador(tipo_ataque: str, tipo_defensor: str) -> float:
    """Efectividad de un tipo de ataque contra un tipo defensor."""
    a, d = normalizar(tipo_ataque), normalizar(tipo_defensor)
    fila = _chart().get(d)
    if not fila:
        return 1.0
    if a in fila["inmune"]:
        return 0.0
    if a in fila["super"]:
        return 2.0
    if a in fila["resist"]:
        return 0.5
    return 1.0


def mejor_efectividad(tipos_ataque: list[str], tipos_defensor: list[str]) -> float:
    """Peor caso para el atacante: el defensor elige su mejor tipo contra nosotros.

    Se usa para puntuar si un món puede con un jefe sin conocer sus movimientos.
    """
    if not tipos_ataque or not tipos_defensor:
        return 1.0
    return min(multiplicador(a, d) for a in tipos_ataque for d in tipos_defensor)


def resumen_cobertura(tipos_equipo: list[str]) -> dict[str, int]:
    """Cuántos miembros del equipo cubren cada tipo (para evitar agujeros dobles)."""
    cuenta: dict[str, int] = {}
    for t in tipos_equipo:
        cuenta[t] = cuenta.get(t, 0) + 1
    return cuenta


def etiqueta(m: float) -> str:
    return MULTIPLICADORES.get(m, "neutral")

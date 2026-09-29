"""Utilidades compartidas para los datos de Pokelike (roguelike web).

Capa específica del juego sobre ``comun/json_store.py``: cachés de los datos de
referencia (tipos, regiones, pokemon, items) y consultas de efectividad para
preparar runs (jefes regionales, cobertura de equipo).
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RUNS_DIR = DATA_DIR / "runs"


def _cargar_json_store():
    """Carga ``comun/json_store.py`` por ruta, sin tocar ``sys.path``."""
    raiz = Path(__file__).resolve().parents[3]
    ruta = raiz / "comun" / "json_store.py"
    spec = importlib.util.spec_from_file_location("comun.json_store", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_js = _cargar_json_store()


def cargar(nombre: str):
    return _js.cargar_json(DATA_DIR, nombre)


@lru_cache(maxsize=1)
def tipos() -> dict[str, dict]:
    """Chart de tipos indexado por nombre."""
    bruto = cargar("tipos")
    lista = bruto.get("tipos", []) if isinstance(bruto, dict) else []
    return {t["tipo"]: t for t in lista}


@lru_cache(maxsize=1)
def regiones() -> dict[str, dict]:
    """Regiones indexadas por nombre (Kanto, Johto, Hoenn, Sinnoh, Unova)."""
    bruto = cargar("regiones")
    lista = bruto.get("regiones", []) if isinstance(bruto, dict) else []
    return {r["region"]: r for r in lista}


@lru_cache(maxsize=1)
def pokemon() -> dict[str, dict]:
    """Pool de especies (starters + captures) indexado por nombre en minúsculas."""
    bruto = cargar("pokemon")
    entradas = bruto.get("pool", []) if isinstance(bruto, dict) else []
    entradas += bruto.get("starters", []) if isinstance(bruto, dict) else []
    return {e["nombre"].lower(): e for e in entradas}


def items_pasivos() -> list[dict]:
    bruto = cargar("items")
    if isinstance(bruto, dict):
        return bruto.get("pasivos", [])
    return []


def efectividad(atacante: str, defensor: str) -> float:
    """Multiplicador de un ataque de tipo ``atacante`` contra un tipo ``defensor``."""
    info = tipos().get(defensor, {})
    if atacante in info.get("inmunidades", []):
        return 0.0
    if atacante in info.get("resistencias", []):
        return 0.5
    if atacante in info.get("debilidades", []):
        return 2.0
    return 1.0


def efectividad_total(atacante: str, defensores: list[str]) -> float:
    """Multiplicador contra un Pokémon de uno o dos tipos."""
    mult = 1.0
    for tipo in defensores:
        mult *= efectividad(atacante, tipo)
    return mult


def jefes_de_region(region: str | None) -> list[str]:
    """Tipos de los jefes (gimnasios) de una región, o vacío si no se indica."""
    if region is None:
        return []
    datos = regiones().get(region)
    if not datos:
        return []
    return [g["tipo"] for g in datos.get("jefes", [])]


def tipos_de_especie(nombre: str) -> list[str] | None:
    """Tipos de una especie del pool (starters o captures), o None si no existe."""
    especie = pokemon().get(nombre.lower())
    return especie.get("tipos") if especie else None
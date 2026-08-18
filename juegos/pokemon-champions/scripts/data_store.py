"""Utilidades compartidas para los datos de Pokémon Champions."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CLAVES_ESPECIE = ("numero", "nombre", "tipos", "stats", "habilidades", "legendario", "movimientos")


def cargar(nombre: str) -> list[dict]:
    ruta = DATA_DIR / f"{nombre}.json"
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar(nombre: str, datos: list[dict]) -> None:
    ruta = DATA_DIR / f"{nombre}.json"
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    _invalidar_cache()


def _invalidar_cache() -> None:
    """Vacía las cachés de datos tras una escritura (p. ej. importar_datos.py)."""
    for fn in (pokedex, movimientos, _tipos, _indice_tipos,
               _indice_especies, _indice_movimientos, tipos_orden):
        fn.cache_clear()


# Los datos de referencia (pokedex, movimientos, tipos) son de solo lectura en
# tiempo de ejecución de los scripts de consulta, así que se cachean para evitar
# releer y reindexar el JSON en cada llamada (clave para los algoritmos que
# recorren todo el meta en bucles anidados).


@lru_cache(maxsize=1)
def pokedex() -> list[dict]:
    return cargar("pokedex")


@lru_cache(maxsize=1)
def movimientos() -> list[dict]:
    return cargar("movimientos")


@lru_cache(maxsize=1)
def _tipos() -> tuple[dict, ...]:
    """Chart de tipos cacheado (data/tipos.json es de solo lectura en runtime)."""
    return tuple(cargar("tipos"))


@lru_cache(maxsize=1)
def _indice_tipos() -> dict[str, dict]:
    return {t["tipo"]: t for t in _tipos()}


@lru_cache(maxsize=1)
def _indice_especies() -> dict[str, dict]:
    return {e.get("nombre", "").lower(): e for e in pokedex()}


@lru_cache(maxsize=1)
def _indice_movimientos() -> dict[str, dict]:
    return {m.get("nombre", "").lower(): m for m in movimientos()}


@lru_cache(maxsize=1)
def tipos_orden() -> list[str]:
    """Los 18 tipos en el orden canónico definido en data/tipos.json."""
    return [t["tipo"] for t in _tipos()]


def efectividad(atacante: str, defensor: str) -> float:
    """Multiplicador de un ataque (atacante) contra un único tipo (defensor)."""
    info = _indice_tipos().get(defensor, {})
    if atacante in info.get("inmunidades", []):
        return 0.0
    if atacante in info.get("resistencias", []):
        return 0.5
    if atacante in info.get("debilidades", []):
        return 2.0
    return 1.0


def efectividad_total(atacante: str, defensores: list[str]) -> float:
    """Multiplicador de un ataque contra un Pokémon de uno o dos tipos."""
    mult = 1.0
    for tipo in defensores:
        mult *= efectividad(atacante, tipo)
    return mult


def buscar_especie(nombre: str) -> dict | None:
    return _indice_especies().get(nombre.lower())


def buscar_movimiento(nombre: str) -> dict | None:
    return _indice_movimientos().get(nombre.lower())


def resolver_especies(nombres: list[str]) -> tuple[list[dict], list[str]]:
    """Resuelve una lista de nombres a especies de la pokedex.

    Devuelve (especies_encontradas, errores) donde cada error describe un
    nombre que no está en data/pokedex.json.
    """
    especies: list[dict] = []
    errores: list[str] = []
    for nombre in nombres:
        especie = buscar_especie(nombre)
        if especie is None:
            errores.append(f"'{nombre}' no está en data/pokedex.json")
        else:
            especies.append(especie)
    return especies, errores


def stats(especie: dict) -> dict:
    return especie.get("stats", {})
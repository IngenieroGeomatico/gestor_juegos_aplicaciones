"""Utilidades compartidas para los datos de Pokémon Champions."""

from __future__ import annotations

import json
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


def pokedex() -> list[dict]:
    return cargar("pokedex")


def movimientos() -> list[dict]:
    return cargar("movimientos")


def _indice_tipos() -> dict[str, dict]:
    return {t["tipo"]: t for t in cargar("tipos")}


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
    for e in pokedex():
        if e.get("nombre", "").lower() == nombre.lower():
            return e
    return None


def buscar_movimiento(nombre: str) -> dict | None:
    for m in movimientos():
        if m.get("nombre", "").lower() == nombre.lower():
            return m
    return None


def stats(especie: dict) -> dict:
    return especie.get("stats", {})
"""Almacén JSON genérico compartido por los distintos juegos/aplicaciones.

Centraliza el bucle "cargar JSON de una carpeta data/ → procesar → guardar
JSON" que cada juego repetía en su propio ``data_store.py``. Cada juego crea su
capa específica (validación de tipos, cachés, índices, etc.) encima de estas
funciones genéricas, pasando su propia ``DATA_DIR``.

Se importa sin necesidad de instalar el repo como paquete: los ``data_store.py``
de cada juego lo cargan por ruta con ``importlib`` (ver ``_cargar_json_store``),
así que sigue funcionando con ``uv run <ruta>.py``.
"""

from __future__ import annotations

import json
from pathlib import Path


def ruta_json(data_dir: Path, nombre: str) -> Path:
    """Devuelve la ruta del fichero ``<data_dir>/<nombre>.json``."""
    return data_dir / f"{nombre}.json"


def cargar_json(data_dir: Path, nombre: str) -> list[dict]:
    """Carga ``<data_dir>/<nombre>.json``. Devuelve ``[]`` si no existe."""
    ruta = ruta_json(data_dir, nombre)
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar_json(data_dir: Path, nombre: str, datos: list[dict]) -> None:
    """Escribe ``datos`` en ``<data_dir>/<nombre>.json`` (UTF-8, indent 2)."""
    ruta = ruta_json(data_dir, nombre)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")


def slug(nombre: str) -> str:
    """Convierte un nombre en un identificador seguro para ficheros.

    'Espada Larga' -> 'Espada_Larga'; conserva alfanuméricos y sustituye el
    resto por '_', recortando los '_' de los extremos.
    """
    return "".join(c if c.isalnum() else "_" for c in nombre).strip("_")

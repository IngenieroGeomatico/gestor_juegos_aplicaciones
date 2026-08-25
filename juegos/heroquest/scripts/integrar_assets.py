# -*- coding: utf-8 -*-
"""Integra arte externo en la carpeta de convención de arte de HeroQuest.

El arte del anverso se localiza por convención de nombre
(`sources/arte/<slug(nombre)>.png`). Este script reemplaza el retrato SVG
generado por `generar_retratos.py` por el arte real descargado, siguiendo el
mapa declarado en `ARTE`.

El script es re-ejecutable: en cada invocación sobrescribe el destino con la
versión actual del origen y muestra el estado de cada entrada (`OK`/`FALTA`).

Ejemplos:
    uv run juegos/heroquest/scripts/integrar_assets.py --lista   # dry-run
    uv run juegos/heroquest/scripts/integrar_assets.py           # aplica
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from data_store import slug

SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"
ARTE_DIR = SOURCES_DIR / "arte"
ORIGEN_DIR = SOURCES_DIR / "Artwork"

# Mapa nombre de carta (repo) -> asset externo dentro de `sources/Artwork/`.
# El destino será sources/arte/<slug(nombre)>.png.
ARTE: dict[str, str] = {
    "Trasgo": "Characters/Goblin.png",
    "Orco": "Characters/Orc.png",
    "Gárgola": "Characters/Gargoyle - 1 - altered.png",
    "Guerrero del Caos": "Characters/Chaos Warrior.png",
}


def iter_tareas() -> list[tuple[Path, Path]]:
    return [(ORIGEN_DIR / asset, ARTE_DIR / f"{slug(nombre)}.png")
            for nombre, asset in ARTE.items()]


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lista", action="store_true", help="solo muestra el plan")
    args = p.parse_args()

    errores = 0
    for origen, destino in iter_tareas():
        if not origen.exists():
            print(f"[FALTA] {destino.name}:      origen inexistente {origen}")
            errores += 1
            continue
        if args.lista:
            print(f"[plan ] {destino.name}:      {origen.relative_to(ORIGEN_DIR.parent)}")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        print(f"[OK   ] {destino.name}  <-  {origen.name}")

    if args.lista:
        return
    if errores:
        print(f"\n{errores} origen(es) no encontrado(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
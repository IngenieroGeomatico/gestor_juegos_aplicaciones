"""Gestiona el estado de una run de Pokelike en data/runs/.

Cada run es un JSON con modo (Classic/Nuzlocke), región, starter, equipo,
objetos, insignias y resultado. Es el registro que el agente actualiza en cada
nodo de decisión mientras juega la run.

Uso:
  # Listar runs existentes
  uv run juegos/pokelike/scripts/registrar_run.py --list

  # Crear una run
  uv run juegos/pokelike/scripts/registrar_run.py --nueva --modo Classic --region Sinnoh --starter Chimchar

  # Actualizar estado
  uv run juegos/pokelike/scripts/registrar_run.py --estado chimchar-sinnoh --badges 4 --equipo Infernape --equipo Lucario --item "Cinturón Negro"

  # Registrar resultado final
  uv run juegos/pokelike/scripts/registrar_run.py --resultado chimchar-sinnoh CHAMPION
"""

from __future__ import annotations

import argparse

from data_store import (
    RUNS_DIR,
    _js,
    regiones,
)

MODOS = ("Classic", "Nuzlocke", "Battle Tower", "Challenge")


def _slug(nombre: str) -> str:
    return _js.slug(nombre).lower()


def _nueva(args: argparse.Namespace) -> int:
    if args.modo not in MODOS:
        print(f"modo inválido '{args.modo}' (válidos: {', '.join(MODOS)})")
        return 2
    if args.region not in regiones():
        print(f"región inválida '{args.region}' (válidas: {', '.join(sorted(regiones()))})")
        return 2
    run_id = _slug(f"{args.starter}-{args.region}")
    ruta = RUNS_DIR / f"{run_id}.json"
    if ruta.exists():
        print(f"ya existe una run con id '{run_id}' ({ruta})")
        return 2
    datos = {
        "id": run_id,
        "modo": args.modo,
        "region": args.region,
        "starter": args.starter,
        "equipo": [args.starter],
        "objetos": [],
        "insignias": 0,
        "pasos": [],
        "resultado": "EN_CURSO",
    }
    _js.guardar_json(RUNS_DIR, run_id, datos)
    print(f"run creada: {run_id} -> {ruta}")
    return 0


def _estado(args: argparse.Namespace) -> int:
    ruta = RUNS_DIR / f"{_slug(args.estado)}.json"
    if not ruta.exists():
        print(f"no existe la run '{args.estado}'")
        return 2
    datos = _js.cargar_json(RUNS_DIR, _slug(args.estado))
    if args.equipo:
        datos["equipo"] = args.equipo
    if args.item:
        datos["objetos"].append(args.item)
    if args.badges is not None:
        datos["insignias"] = args.badges
    if args.paso:
        datos["pasos"].append(args.paso)
    _js.guardar_json(RUNS_DIR, _slug(args.estado), datos)
    print(_resumen(datos))
    return 0


def _resultado(args: argparse.Namespace) -> int:
    run_id = _slug(args.resultado)
    ruta = RUNS_DIR / f"{run_id}.json"
    if not ruta.exists():
        print(f"no existe la run '{args.resultado}'")
        return 2
    datos = _js.cargar_json(RUNS_DIR, run_id)
    if args.resultado_val not in ("CHAMPION", "GAME_OVER", "EN_CURSO"):
        print("resultado inválido (CHAMPION | GAME_OVER | EN_CURSO)")
        return 2
    datos["resultado"] = args.resultado_val
    _js.guardar_json(RUNS_DIR, run_id, datos)
    print(_resumen(datos))
    return 0


def _listar() -> int:
    runs = sorted(RUNS_DIR.glob("*.json"))
    if not runs:
        print("no hay runs registradas.")
        return 0
    for ruta in runs:
        datos = _js.cargar_json(RUNS_DIR, ruta.stem)
        print(_resumen(datos))
    return 0


def _resumen(datos: dict) -> str:
    return (
        f"[{datos.get('resultado', 'EN_CURSO')}] {datos.get('id')}: "
        f"{datos.get('modo')} · {datos.get('region')} · starter {datos.get('starter')} "
        f"· {len(datos.get('equipo', []))}/6 · {datos.get('insignias', 0)} insignias"
    )


def principal() -> int:
    parser = argparse.ArgumentParser(description="Estado de las runs de Pokelike.")
    parser.add_argument("--list", action="store_true", help="listar runs")
    parser.add_argument("--nueva", action="store_true", help="crear run")
    parser.add_argument("--modo", default="Classic")
    parser.add_argument("--region", default=None)
    parser.add_argument("--starter", default=None)
    parser.add_argument("--estado", default=None, help="id de run a actualizar")
    parser.add_argument("--equipo", action="append", default=[], help="nombre de miembro (repetible)")
    parser.add_argument("--item", default=None)
    parser.add_argument("--badges", type=int, default=None)
    parser.add_argument("--paso", default=None, help="decisión apuntada (p. ej. 'catch Gyarados')")
    parser.add_argument("--resultado", default=None, help="id de run; junto a RESULTADO final")
    parser.add_argument("resultado_val", nargs="?", default=None)
    args = parser.parse_args()

    if args.list:
        return _listar()
    if args.nueva:
        return _nueva(args)
    if args.resultado:
        return _resultado(args)
    if args.estado:
        return _estado(args)
    print(parser.format_help())
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
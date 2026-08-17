"""Sugiere los mejores equipos competitivos de Pokémon Champions.

Construye un equipo de 6 a partir del ranking actual del meta (data/meta.json)
o, si se pasa --mis-pokemon, a partir de los Pokémon que el usuario posee.

El algoritmo combina tres factores para cada candidato:
  - posición en el ranking del formato (Singles/Doubles)
  - cobertura ofensiva: tipos que golpea super-efectivamente y aún cubre el equipo
  - diversidad: penaliza compartir tipos con los miembros ya elegidos

Ejemplos:
    uv run juegos/pokemon-champions/scripts/mejores_equipos.py --meta
    uv run juegos/pokemon-champions/scripts/mejores_equipos.py --meta --formato singles
    uv run juegos/pokemon-champions/scripts/mejores_equipos.py --mis-pokemon mis_pokemons.json
"""

from __future__ import annotations

import argparse
import json
import sys

import cobertura_tipos as ct
import data_store as ds

FORMATOS = ("Doubles", "Singles")


def _cargar_meta() -> dict:
    ruta = ds.DATA_DIR / "meta.json"
    if not ruta.exists():
        print("Error: no existe data/meta.json. Ejecuta importar_datos.py primero.")
        sys.exit(1)
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def _leer_mis_pokemon(ruta: str) -> list[str]:
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    if isinstance(datos, list):
        ítems = datos
    elif isinstance(datos, dict):
        ítems = datos.get("pokemon") or datos.get("especies") or []
    else:
        ítems = []
    nombres: list[str] = []
    for it in ítems:
        if isinstance(it, str):
            nombres.append(it)
        elif isinstance(it, dict):
            nombres.append(it.get("nombre") or it.get("especie") or "")
    return [n for n in nombres if n]


def _en_mis_pokemon(nombre: str, mis: list[str]) -> bool:
    return any(nombre.lower() == m.lower() for m in mis)


def _tipos_ataque_meta(entrada: dict) -> list[str]:
    """Tipos ofensivos según el set recomendado del meta (STAB + movimientos)."""
    tipos = list(entrada.get("tipos", []))
    for nombre in entrada.get("movimientos", []):
        m = ds.buscar_movimiento(nombre)
        if m and m.get("categoria") not in (None, "", "Estado"):
            t = m.get("tipo")
            if t and t not in tipos:
                tipos.append(t)
    return tipos


def _puntuar(entrada: dict, elegidos: list[dict], cubiertos: set[str]) -> tuple[float, int]:
    """Puntuación de un candidato: ranking + cobertura nueva - redundancia."""
    score = 100.0 / entrada["posicion"] ** 0.75
    extra = _tipos_ataque_meta(entrada)
    nuevos = sum(1 for t in extra if t in ct.TIPOS_ORDEN and t not in cubiertos)
    score += 14.0 * min(nuevos, 5)
    ya_elegidos = {t for e in elegidos for t in e.get("tipos", [])}
    compartidos = len(set(entrada.get("tipos", [])) & ya_elegidos)
    score -= 6.0 * compartidos
    return score, nuevos


def _construir(candidatos: list[dict], tope: int = 6) -> list[dict]:
    elegidos: list[dict] = []
    cubiertos: set[str] = set()
    pool = list(candidatos)
    while pool and len(elegidos) < tope:
        mejor, mejor_tupla = None, None
        for c in pool:
            tupla = _puntuar(c, elegidos, cubiertos)
            if mejor_tupla is None or tupla[0] > mejor_tupla[0]:
                mejor, mejor_tupla = c, tupla
        elegidos.append(mejor)
        cubiertos.update(_tipos_ataque_meta(mejor))
        pool.remove(mejor)
    return elegidos


def _mostrar(formato: str, equipo: list[dict]) -> None:
    print(f"\n=== Mejor equipo ({formato}) — {len(equipo)} miembros ===")
    for i, e in enumerate(equipo, 1):
        tipos = "/".join(e.get("tipos", []))
        print(f"  #{i} {e['nombre']} ({tipos}) — ranking {e['posicion']}")
        set_str = " / ".join(e.get("movimientos", [])[:4])
        print(f"      Set: {set_str} | {e.get('objeto', '')} | "
              f"{e.get('naturaleza', '')} | {e.get('habilidad', '')}")
        if e.get("companeros"):
            print(f"      Compañeros habituales: {', '.join(e['companeros'][:3])}")


def _analizar_cobertura(equipo: list[dict]) -> None:
    names = [e["nombre"] for e in equipo]
    especies, errores = ct._resolver_especies(names)
    if errores:
        for err in errores:
            print(f"  ✗ {err}")
        return
    if especies:
        ct.analizar(especies)


def run(formato: str, mis: list[str] | None = None) -> int:
    meta = _cargar_meta()
    formatos = [formato] if formato else FORMATOS
    for fmt in formatos:
        orden = meta.get("formato", {}).get(fmt, [])
        if not orden:
            print(f"  (sin datos para {fmt})")
            continue
        candidatos = [e for e in orden if not mis or _en_mis_pokemon(e["nombre"], mis)]
        equipo = _construir(candidatos)
        if not equipo:
            print(f"\n({fmt}) ningún Pokémon disponible del meta.")
            continue
        _mostrar(fmt, equipo)
        _analizar_cobertura(equipo)
    return 0


def _alias_formato(valor: str) -> str:
    alias = {"singles": "Singles", "single": "Singles", "solo": "Singles",
             "doubles": "Doubles", "double": "Doubles", "dobles": "Doubles",
             "doble": "Doubles", "parejas": "Doubles"}
    return alias.get(valor.lower(), valor.title())


def main() -> int:
    parser = argparse.ArgumentParser(description="Sugiere los mejores equipos de Pokémon Champions")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--meta", action="store_true",
                       help="Usar los mejores del ranking actual (default)")
    grupo.add_argument("--mis-pokemon", metavar="ARCHIVO", default=None,
                       help="JSON con mis Pokémon: ['Garchomp', ...] o {\"pokemon\": [...]}")
    parser.add_argument("--formato", default=None,
                        help="Solo un formato (singles/dobles o singles/doubles); si no, ambos")
    args = parser.parse_args()

    formato = _alias_formato(args.formato) if args.formato else None
    mis = _leer_mis_pokemon(args.mis_pokemon) if args.mis_pokemon else None
    return run(formato, mis)


if __name__ == "__main__":
    sys.exit(main())
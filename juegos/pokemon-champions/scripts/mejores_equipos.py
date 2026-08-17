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
    uv run juegos/pokemon-champions/scripts/mejores_equipos.py --mis-pokemon mis_pokemons.json --sets
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
        ítems = (datos.get("pokemon") or datos.get("especies")
                 or datos.get("fijos", []) + datos.get("temporales", []))
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


def _rol_especie(nombre: str) -> str:
    especie = ds.buscar_especie(nombre)
    if not especie:
        return "general"
    s = ds.stats(especie)
    fis = s.get("ataque", 0)
    esp = s.get("ataque_esp", 0)
    vel = s.get("velocidad", 0)
    ps = s.get("ps", 0)
    if max(fis, esp) < 80:
        return "tanque" if ps >= 90 else "apoyo"
    if vel >= 100 and fis >= esp:
        return "sweeper físico rápido"
    if vel >= 100 and esp >= fis:
        return "sweeper especial rápido"
    if fis >= esp:
        return "sweeper físico"
    return "sweeper especial"


def _estrategia(entrada: dict, rol: str, velocidad: int) -> str:
    l = [f"Rol: {rol}."]
    if velocidad < 80:
        l.append("Poco veloz: necesita Espacio Raro, lluvia/sol aliados o Priority para actuar.")
    elif velocidad >= 100:
        l.append(f"Rápido (Vel base {velocidad}): suele actuar primero.")
    if "Protección" in entrada.get("movimientos", []):
        l.append("Lleva Protección: clave en dobles para posicionarse junto a un aliado.")
    if entrada.get("companeros"):
        l.append("Sinergia habitual: " + ", ".join(entrada["companeros"][:3]) + ".")
    return " ".join(l)


def _sets_de_caja(meta: dict, mis: list[str]) -> None:
    for formato in FORMATOS:
        orden = meta.get("formato", {}).get(formato, [])
        print(f"\n########## SETS DEL META — {formato} ##########")
        for e in orden:
            if not _en_mis_pokemon(e["nombre"], mis):
                continue
            especie = ds.buscar_especie(e["nombre"]) or {}
            velocidad = ds.stats(especie).get("velocidad", 0)
            rol = _rol_especie(e["nombre"])
            e = dict(e)
            e["movimientos"] = (e.get("movimientos") or [])[:4]
            print(f"\n—— {e['nombre']} ({'/'.join(e.get('tipos', []))}) — ranking {e['posicion']} ——")
            print(f"  Movimientos: {' / '.join(e['movimientos'])}")
            print(f"  Objeto: {e.get('objeto', '—')} | Naturaleza: {e.get('naturaleza', '—')} | "
                  f"Habilidad: {e.get('habilidad', '—')}")
            if e.get("evs"):
                print(f"  EVs: {e['evs'][0]}  (alt.: {e['evs'][1]})")
            if e.get("companeros"):
                print(f"  Compañeros: {', '.join(e['companeros'][:5])}")
            print(f"  Estrategia: {_estrategia(e, rol, velocidad)}")


def run(formato: str, mis: list[str] | None = None, sets: bool = False) -> int:
    meta = _cargar_meta()
    if sets:
        if not mis:
            print("Error: --sets requiere --mis-pokemon (un archivo o --py ...).")
            return 1
        _sets_de_caja(meta, mis)
        return 0
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
    parser.add_argument("--mis-pokemon", metavar="ARCHIVO", default=None,
                        help="JSON con mis Pokémon: ['Garchomp', ...] o {\"pokemon\": [...]}")
    parser.add_argument("--sets", action="store_true",
                        help="Mostrar el set del meta (movimientos, objeto, naturaleza, "
                             "habilidad, EVs, compañeros y estrategia) de cada Pokémon de mis-pokemon")
    parser.add_argument("--formato", default=None,
                        help="Solo un formato (singles/dobles o singles/doubles); si no, ambos")
    args = parser.parse_args()

    formato = _alias_formato(args.formato) if args.formato else None
    mis = _leer_mis_pokemon(args.mis_pokemon) if args.mis_pokemon else None
    return run(formato, mis, sets=args.sets)


if __name__ == "__main__":
    sys.exit(main())
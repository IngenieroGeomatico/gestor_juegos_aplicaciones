"""Vuelca a `data/` los datasets del juego: especies, movimientos y discos.

Los datos salen del propio cliente, que los tiene en globales legibles
(`__POKEDEX__`, `MOVE_POOL`, `TM_OVERDRIVE_BY_ID`, `LEGENDARY_SIGNATURE_MOVES`,
`TYPE_CHART`). Solo se leen; no se toca nada del juego.

    MOVE_POOL[tipo][physical|special][tier] = {name, power, desc}
    TM_OVERDRIVE_BY_ID[id]                 = {id, name, type, power, rarity, effects}

El `tier` depende del mapa (`getMoveТierForMap`): tier 0 en los primeros mapas y
tier 2 en los últimos, así que los golpes de un mismo tipo se multiplican
siguiendo el avance. El chart es el del juego y NO el oficial: aquí
`Normal vs Rock` es 0.5 y `Electric -> Ground` es inmunidad (0).

Uso:

    uv run --group dev python juegos/pokelike/scripts/extraer_datos.py
"""

from __future__ import annotations

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import navegador as nb  # noqa: E402

DATOS = RAIZ / "data"

EXPRESION = """() => ({
  pool:  eval('MOVE_POOL'),
  tms:   eval('TM_OVERDRIVE_BY_ID'),
  sig:   eval('LEGENDARY_SIGNATURE_MOVES'),
  chart: eval('TYPE_CHART'),
  dex:   eval('__POKEDEX__'),
})"""


def main() -> int:
    juego, ctx, pw = nb.abrir(headless=True, perfil=None)
    try:
        # Los datasets están en el bundle de la página, así que no hace falta
        # ni empezar una run: con la home cargada ya se pueden leer.
        juego.page.wait_for_timeout(2500)
        datos = juego.page.evaluate(EXPRESION)
    finally:
        nav = getattr(ctx, "_navegador_propio", None)
        try:
            ctx.close()
        finally:
            if nav is not None:
                nav.close()
            pw.stop()

    destino = {
        "movimientos.json": datos["pool"],
        "tms.json": datos["tms"],
        "leyenda.json": datos["sig"],
        "chart_juego.json": datos["chart"],
        "pokedex.json": datos["dex"],
    }
    for nombre, contenido in destino.items():
        (DATOS / nombre).write_text(
            json.dumps(contenido, ensure_ascii=False, indent=1), encoding="utf-8")
        if isinstance(contenido, dict):
            print(f"  {nombre:20} {len(contenido)} entradas")
        else:
            print(f"  {nombre:20} {len(contenido)} elementos")
    print("datasets guardados en", DATOS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Los movimientos del juego y cuándo conviene usar cada uno.

Los datos salen del propio cliente (`MOVE_POOL`, `TM_OVERDRIVE_BY_ID`) y se
vuelcan a `data/movimientos.json` y `data/tms.json` con
`scripts/extraer_datos.py`. La estructura es:

    MOVE_POOL[tipo][physical|special][tier] = {name, power, desc}

El `tier` depende del mapa (`getMoveТierForMap`): en los primeros mapas sale el
tier 0 y en los últimos el 2, así que un món ve como sus golpes se multiplican
simply con la ruta. Por eso el tier se fuerza a 0 al elegir movimiento: no
sabemos en qué tier está el món, y entre las Cartas que el juego reparte
siempre hay una de 40-60 de potencia para el tipo del rival, así que elegir la
menor nunca sale mal.

El chart también es el del juego, no el oficial: `Normal vs Rock` es 0.5 aquí y
`Electric -> Ground` es inmunidad (0). Usar el chart oficial daría decisiones
equivocadas, por eso está en `data/chart_juego.json`.
"""

from __future__ import annotations

import json
import pathlib

from pkl_tipos import normalizar

DATOS = pathlib.Path(__file__).resolve().parent.parent / "data"


def _carga(nombre: str) -> dict:
    with open(DATOS / nombre, encoding="utf-8") as fh:
        return json.load(fh)


_POOL: dict | None = None
_CHART: dict | None = None
_TMS: dict | None = None
_INDICE: dict[str, dict] | None = None


def pool() -> dict:
    global _POOL
    if _POOL is None:
        _POOL = _carga("movimientos.json")
    return _POOL


def tabla_chart() -> dict:
    global _CHART
    if _CHART is None:
        _CHART = _carga("chart_juego.json")
    return _CHART


def tms() -> dict:
    global _TMS
    if _TMS is None:
        _TMS = _carga("tms.json")
    return _TMS


def multiplicador(tipo_ataque: str, tipo_defensa: str) -> float:
    """Daño que hace `tipo_ataque` contra `tipo_defensa`, según el juego."""
    filas = tabla_chart()
    fila = filas.get(normalizar(tipo_ataque))
    if not fila:
        return 1.0
    return float(fila.get(normalizar(tipo_defensa), 1.0))


def mejor_efectividad(tipos_ataque: list[str], tipo_defensa: str) -> float:
    """Peor caso del atacante: el defensor elige su mejor tipo contra nosotros.

    Se usa para puntuar si un món puede con un jefe sin conocer sus movimientos.
    """
    if not tipos_ataque or not tipo_defensa:
        return 1.0
    return min(multiplicador(t, tipo_defensa) for t in tipos_ataque)


def movimientos_de(tipo: str, especial: bool, tier: int = 0) -> list[dict]:
    """Los tres movimientos que el juego da a un tipo en una categoría y tier."""
    datos = pool().get(normalizar(tipo))
    if not datos:
        return []
    clave = "special" if especial else "physical"
    return list(datos.get(clave, [])[:3])


def mejor_movimiento(tipos_rival: list[str], movimientos: list[dict]) -> dict | None:
    """De los movimientos que el bicho tiene en pantalla, el que más pega.

    Se puntúa `power x multiplicador` y se descarta lo que no haga daño
    (multiplicador 0: inmunidad, y contra un tipo donde solo hay 0.5x la
    batalla se alarga hasta morir). Entre los que quedan gana el de mayor
    potencia efectiva, que es lo que decide contra un rival de nivel parejo.

    `movimientos` son los `div.poke-move` leídos del DOM, con `tipo` y `power`.
    """
    if not movimientos:
        return None
    mejor, mejor_puntaje = None, -1.0
    for m in movimientos:
        tipo = normalizar(m.get("tipo") or "")
        power = m.get("power") or 0
        if not tipo or not power:
            continue
        mult = max((multiplicador(tipo, t) for t in tipos_rival), default=1.0)
        if mult <= 0:
            continue
        # El segundo bicho del rival (si lo hay) también cuenta: en Trainer
        # con dos móns, un movimiento que solo aplaste al primero se paga
        # después contra el segundo.
        if len(tipos_rival) > 1:
            mult *= 0.5 + 0.5 * min(
                (multiplicador(tipo, t) for t in tipos_rival), default=1.0)
        puntaje = power * mult
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = m, puntaje
    if mejor is None:
        # Todos los movimientos son inútiles (0.5x o inmunidad): se usa el de
        # más potencia, que al menos hace daño.
        utiles = [m for m in movimientos if (m.get("power") or 0) > 0]
        return max(utiles, key=lambda m: m["power"]) if utiles else None
    return mejor


def resumen_movimiento(m: dict | None) -> str:
    if not m:
        return "sin movimientos"
    return f"{m.get('nombre')} ({m.get('tipo')} {m.get('power')})"


def _indice_por_nombre() -> dict[str, dict]:
    global _INDICE
    if _INDICE is None:
        with open(DATOS / "pokedex.json", encoding="utf-8") as fh:
            dex = json.load(fh)
        # Las claves del JSON son índices; el nombre va en "name".
        _INDICE = {v["name"]: v for v in dex.values() if v.get("name")}
    return _INDICE


def tipos_de(nombre: str) -> list[str]:
    """Tipos de un món por nombre, sacados del Pokédex.

    El DOM del rival solo trae nombre, nivel y PS, así que cualquier
    razonamiento de tipos en batalla tiene que pasar por aquí. Sin esto se
    acababa tratando "Zubat" como si fuera un tipo.
    """
    if not nombre:
        return []
    entrada = _indice_por_nombre().get(nombre.strip())
    # La clave del JSON es "types" en inglés, no "tipos".
    return [normalizar(t) for t in (entrada or {}).get("types", [])]


def entradas_pokedex() -> list[dict]:
    """Todas las especies con sus stats base, para elegir capturas."""
    return list(_indice_por_nombre().values())

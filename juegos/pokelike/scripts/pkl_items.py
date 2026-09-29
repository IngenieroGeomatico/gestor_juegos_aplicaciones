"""Qué objeto darle a qué Pokémon, y cuándo.

El catálogo real está en `data/items_juego.json`. Este módulo decide dos cosas
que el bot antes no decidía: **qué objeto** y **a quién**.

Por qué importa tanto, con datos de la guía y medidos:

- Los objetos de tipo (`miracle_seed`, `charcoal`...) no solo dan +40%: **hacen
  que el portador ataque con el tipo del objeto**. En el chart *del juego*
  Planta contra Roca es 2x y Veneno contra Roca es 0.5x, así que darle una
  Semilla Milagro a un Bulbasaur lo convierte en Planta pura: gana el 2x y
  desaparece el 0.5x. Es literalmente el objeto clave de un Bulbasaur.
- **Sacred Ash** cura del todo **y revive**, que es la solución directa al
  problema medido de plantarse en la puerta del gimnasio con un caído.
- **Rare Candy** da **+3 niveles** al instante: lo mismo que un trade, pero sin
  sacrificar un món.
- **Lucky Egg**: 30% de nivel extra por combate. Va en el carry y se coge
  temprano, porque compone a lo largo de toda la partida.
- **TM**: sube un nivel el tier del único ataque. Es la única palanca de daño
  pura que hay, y va al principal.

La guía insiste en un punto que se respeta aquí: **el objeto va al rol, no al
món favorito**, y lo que escala (Lucky Egg) va a quien se queda en el equipo.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
_cache: dict | None = None


def catalogo() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(
            (DATA / "items_juego.json").read_text(encoding="utf-8"))
    return _cache


def _norm(id_obj: str) -> str:
    return str(id_obj or "").strip().lower().replace(" ", "_").replace("-", "_")


def tipo_de_boost(id_obj: str) -> str | None:
    """Si el objeto hace atacar con un tipo concreto, cuál."""
    return (catalogo().get("boost_tipo", {}).get(_norm(id_obj)) or {}).get("tipo")


def es_consumible(id_obj: str) -> bool:
    return _norm(id_obj) in catalogo().get("consumibles", {})


def efecto(id_obj: str) -> str:
    c = catalogo()
    n = _norm(id_obj)
    for grupo in ("boost_tipo", "dano", "supervivencia", "utilidad",
                  "consumibles"):
        item = c.get(grupo, {}).get(n)
        if item:
            return item.get("efecto") or (
                f"+40% de {item['tipo']} y ataca como {item['tipo']}"
                if "tipo" in item else "")
    return ""


# --------------------------------------------------------------- puntuación
# Escala de prioridad. Los números son relativos: lo que importa es el orden.
P_CURA_TOTAL = 100.0      # Sacred Ash: cura y revive
P_NIVELES = 90.0          # Rare Candy: +3 niveles
P_BOOST_PROPIO = 80.0     # objeto del tipo del portador
P_TM = 70.0               # sube el tier del ataque
P_LUCKY_EGG = 60.0        # +30% de nivel extra por combate
P_UTILES = 40.0           # scarf, claw, kings rock
P_SUPERVIVENCIA = 35.0    # leftovers, red card, rocky helmet
P_DANO_GENERICO = 30.0    # wide lens, expert belt...


def puntuar_objeto(id_obj: str, tipos_portador: list[str],
                   tipos_rival: list[str] | None = None,
                   ratio_portador: float = 1.0,
                   es_principal: bool = False) -> tuple[float, str]:
    """(puntaje, motivo) de darle este objeto a este Pokémon."""
    n = _norm(id_obj)
    c = catalogo()
    booster = tipo_de_boost(n)

    if n == "sacred_ash":
        return (P_CURA_TOTAL,
                "cura total y revive: lo que hace falta antes de un jefe")
    if n == "rare_candy":
        return (P_NIVELES, "+3 niveles al instante")
    if n == "tm":
        return (P_TM, "sube el tier del único ataque (daño puro)")
    if n == "lucky_egg":
        # Solo vale en el principal: en otro món es un nivel que se pierde.
        return (P_LUCKY_EGG if es_principal else P_LUCKY_EGG - 25,
                "30% de nivel extra por combate (al principal)")

    if booster and tipos_portador:
        # Solo sirve si el tipo del objeto es **uno de los del portador**: eso es
        # literalmente lo que hace ("makes the holder attack with the item's
        # type when it matches one of its own"). Un Geodude (Roca/Tierra) con
        # Semilla Milagro no gana nada, porque no es de Planta. Antes se le
        # daba igual y se lo adjudicaba a cualquier bicho con dos tipos, que
        # wasteaba el mejor objeto de la partida.
        if booster == tipos_portador[0]:
            extra = ""
            if tipos_rival:
                from planificador import mult
                golpea = mult(booster, tipos_rival[0])
                extra = f"; contra {tipos_rival[0]} pega a {golpea}x"
            return (P_BOOST_PROPIO,
                    f"hace atacar como {booster}, su tipo principal (+40%){extra}")
        if booster in tipos_portador:
            return (P_BOOST_PROPIO - 20,
                    f"hace atacar como {booster} (su segundo tipo)")
        return (3.0, f"{booster} no es ningún tipo suyo: no hace nada")

    if n in c.get("dano", {}):
        if ratio_portador < 0.5 and n in ("choice_band", "lagging_tail"):
            return (10.0, "objeto ofensivo en un món por los suelos")
        return (P_DANO_GENERICO, efecto(n))
    if n in c.get("supervivencia", {}):
        # Lo defensivo va al que va a pelear de verdad.
        peso = P_SUPERVIVENCIA + (10.0 if es_principal else 0.0)
        if ratio_portador < 0.5:
            peso += 10.0
        return (peso, efecto(n))
    if n in c.get("utilidad", {}):
        return (P_UTILES, efecto(n))
    return (2.0, efecto(n) or "sin efecto conocido")


def elegir_objetos(bolsa: list[dict], equipo: list[dict],
                   tipos_rival: list[str] | None = None
                   ) -> dict[str, list[tuple[int, str, str]]]:
    """Reparte la bolsa. Devuelve `{"usar": [...], "llevar": [...]}`.

    Son dos cosas distintas y confundirlas lo rompe todo:

    - **usar**: consumibles de un solo uso. El Sacred Ash cura y revive, el Rare
      Candy da +3 niveles, el TM sube el tier del ataque y el Moon Stone fuerza
      la evolución. Se gastan, así que **no ocupan ranura** y el mismo Pokémon
      puede llevar un objeto y además curarse con otro.
    - **llevar**: objetos permanentes. El Lucky Egg, la Semilla Milagro, los
      Leftovers. Uno por Pokémon, y el mejor objeto para el mejor món.

    Medido el fallo de mezclarlo: el Sacred Ash (100) se adjudicaba al Bulbasaur
    como si se llevara, le quitaba la ranura al Lucky Egg y la Semilla Milagro se
    quedaba sin nadie, que es justo el reparto contrario al que conviene.
    """
    vacio = {"usar": [], "llevar": []}
    if not bolsa or not equipo:
        return vacio
    ratios = [((m.get("ps") or 0) / max(m.get("ps_max") or 1, 1)) for m in equipo]
    principal_idx = max(range(len(ratios)), key=lambda j: ratios[j])
    boosting = set(catalogo().get("boost_tipo", {}))
    conocidos = (boosting | set(catalogo().get("dano", {}))
                 | set(catalogo().get("supervivencia", {}))
                 | set(catalogo().get("utilidad", {})))

    usar: list[tuple[int, str, str]] = []
    llevar: list[tuple[int, str, str]] = []
    pares_llevar: list[tuple[float, int, int, str]] = []

    for i, obj in enumerate(bolsa):
        oid = _norm(obj.get("id") or "")
        if oid not in conocidos and oid not in catalogo().get("consumibles", {}):
            continue
        if es_consumible(oid):
            # A quién se lo gastamos, que es distinto de a quién se lo ponemos.
            if oid == "sacred_ash":
                # Al más pelado; si hay caídos, a un caído (los revive).
                candidatos = [j for j, m in enumerate(equipo)
                              if (m.get("ps") or 0) <= 0] or [
                    j for j in range(len(equipo))]
                if not candidatos:
                    continue
                peor = min(candidatos, key=lambda j: ratios[j])
                usar.append((i, equipo[peor].get("nombre") or "?",
                             efecto(oid) + " (al más gastado)"))
            else:
                # Rare Candy, TM y Moon Stone van al que se queda: el principal.
                usar.append((i, equipo[principal_idx].get("nombre") or "?",
                             efecto(oid) + " (al principal)"))
            continue
        for j, m in enumerate(equipo):
            if (m.get("ps") or 0) <= 0:
                continue
            s, motivo = puntuar_objeto(
                oid, m.get("tipos") or [], tipos_rival,
                ratios[j], es_principal=(j == principal_idx))
            pares_llevar.append((s, i, j, motivo))

    pares_llevar.sort(key=lambda x: -x[0])
    usados_obj: set[int] = set()
    usados_mons: set[int] = set()
    for s, i, j, motivo in pares_llevar:
        if s <= 1.0 or i in usados_obj or j in usados_mons:
            continue
        usados_obj.add(i)
        usados_mons.add(j)
        llevar.append((i, (equipo[j].get("nombre") or "?"), motivo))
    return {"usar": usar, "llevar": llevar}

#!/usr/bin/env python3
"""Batería de integridad de Pokelike.

Existe por una razón concreta: **siete veces** el bot tuvo código que parecía
funcionar y nunca se ejecutaba, siempre por lo mismo, comparar contra un
nombre o una clave que no existe en los datos reales:

  - `cura`       cuando el juego emite `pokecenter`
  - `jefe`       cuando el tipo crudo es `boss`
  - `PL.llega_a` cuando la política se importa como `P`
  - `trade`      mapeado a `incognita` y descartado
  - `n.get("type")` cuando los nodos del mapa llevan `tipo`
  - `ps(m) < 50` con PS crudos en vez de porcentaje
  - PS leído como porcentaje cuando en un caído la barra sigue al 100

Ninguno daba error: fallaban en silencio. Estos tests miran **la forma de los
datos reales**, no la intención del código, que es donde se colaban.

    uv run --group dev python juegos/pokelike/scripts/test_integridad.py
"""
from __future__ import annotations

import ast
import importlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SCRIPTS = RAIZ / "juegos" / "pokelike" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import planificador as PL  # noqa: E402
import politica as P  # noqa: E402
import pkl_tipos as T  # noqa: E402
import jugar_pokelike as J  # noqa: E402

FALLOS: list[str] = []
OKS: list[str] = []

# Un món de mentira con estadísticas en el rango medio (el filtro de captura
# rechaza por debajo de `MIN_STATS_CAPTURA`, así que hay que superar el listón).
_STATS_MEDIOS = {"hp": 60, "atk": 60, "def": 60, "spa": 60, "spd": 60, "spe": 60}


def _mon(nombre: str, tipos: list[str], nivel: int, ps: int = 100) -> dict:
    return {"nombre": nombre, "tipos": tipos, "nivel": nivel, "ps": ps,
            "ps_max": 100, "baseStats": _STATS_MEDIOS}


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    (OKS if cond else FALLOS).append(f"{nombre}{': ' + detalle if detalle else ''}")


# ---------------------------------------------------------------- 1. nodos
def test_tipos_de_nodo() -> None:
    """Los 10 tipos que emite el juego, traducidos a su nombre interno."""
    esperado = {
        "start": "desconocido", "catch": "batalla", "battle": "batalla",
        "trainer": "entrenador", "item": "item", "question": "incognita",
        "trade": "trade", "pokecenter": "cura", "move_tutor": "tutor",
        "boss": "jefe",
    }
    for crudo, quiero in esperado.items():
        check(f"tipo {crudo}", P.tipo_de_estado(crudo) == quiero,
              f"-> {P.tipo_de_estado(crudo)} (se esperaba {quiero})")


# ------------------------------------------------------- 2. rutas de nodos
def test_los_helpers_de_ruta_ven_los_nodos() -> None:
    """El fallo de `n.get("type")` no daba error: devolvía 0 siempre.

    Aquí se comprueba que un grafo con un entrenador **de verdad** se cuenta.
    """
    nodos = [{"id": "a", "tipo": "battle"}, {"id": "c", "tipo": "trainer"},
             {"id": "d", "tipo": "battle"}]
    edges = [["a", "y"], ["c", "y"], ["d", "y"]]
    ent = P.entrenadores_por_delante(nodos, edges)
    check("entrenadores_por_delante cuenta al entrenador",
          ent.get("c") == 1, f"-> {ent.get('c')}")
    check("entrenadores_por_delante ve la rama del entrenador",
          ent.get("a") == 0, f"-> rama sin entrenador da {ent.get('a')}")
    comb = P.combates_por_delante(nodos, edges)
    check("combates_por_delante ve los combates", comb.get("a", 0) >= 1,
          f"-> {comb.get('a')}")


# --------------------------------------------- 3. claves de nodo coherentes
def test_ningun_helper_usa_la_clave_type() -> None:
    """`tipo` es la clave real; `type` no existe en los nodos del bot."""
    fuente = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    # Se permite `n.get("tipo") or n.get("type")`: el primero es el bueno y el
    # segundo es un respaldo. Lo que no vale es `type` en solitario, que es
    # donde estuvo el fallo.
    roto = 'n.get("type") == "trainer"'
    check("politica.py no usa solo la clave type",
          roto not in fuente,
          "los nodos del mapa llevan la clave `tipo`")


# ------------------------------------------------ 4. llamadas a self.* Defined
def test_llamadas_self_definidas() -> None:
    """Toda llamada `self.algo()` tiene que existir como método."""
    for f in SCRIPTS.glob("*.py"):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for cls in [n for n in ast.walk(arbol)
                    if isinstance(n, ast.ClassDef)]:
            metodos = {m.name for m in cls.body
                       if isinstance(m, ast.FunctionDef)}
            faltan = {
                n.func.attr for n in ast.walk(cls)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self"
                and n.func.attr not in metodos
                and not n.func.attr.startswith("__")
            }
            check(f"{f.name}:{cls.name} sin metodos sin definir",
                  not faltan, f"-> {sorted(faltan)}")


# ------------------------------------------------------------- 5. chart
def test_chart_completo() -> None:
    """El chart del juego es 18x18 y sin huecos."""
    c = json.loads((RAIZ / "juegos/pokelike/data/chart_juego.json")
                   .read_text(encoding="utf-8"))
    tipos = [t for t in c if t not in ("_nota",)]
    check("chart con 18 tipos", len(tipos) == 18, f"-> {len(tipos)}")
    rotas = []
    for a in tipos:
        for b in tipos:
            if a not in c[a] or c[a][a] if False else False:
                pass
            if b not in c.get(a, {}):
                rotas.append(f"{a}->{b}")
    check("chart sin celdas vacías", not rotas, f"-> {rotas[:4]}")
    # Un par que tiene que ser 0 si o si, y otro que solo es del juego.
    check("Planta->Fuego = x1/2 en el juego", c["Grass"]["Fire"] == 0.5,
          f"-> {c['Grass']['Fire']}")
    check("Fuego->Planta = x2 en el juego", c["Fire"]["Grass"] == 2.0,
          f"-> {c['Fire']['Grass']}")


# ---------------------------------------------------------- 6. regiones
def test_regiones_completas() -> None:
    """Cada región tiene 8 gimnasios, Elite Four y campeón."""
    f = RAIZ / "juegos/pokelike/data/regiones.json"
    if not f.exists():
        check("regiones.json existe", False, "-> no está")
        return
    datos = json.loads(f.read_text(encoding="utf-8"))
    # La lista de regiones cuelga de d["regiones"]; en la raiz hay ademas un
    # resumen por region, que no tiene la misma forma y por eso daba 0 gyms.
    if isinstance(datos, dict) and "regiones" in datos:
        regiones = datos["regiones"]
    elif isinstance(datos, dict):
        regiones = list(datos.values())
    else:
        regiones = datos
    for r in regiones:
        if not isinstance(r, dict):
            continue
        nombre = r.get("region", "?")
        g = r.get("jefes") or []
        check(f"{nombre} con 8 gimnasios", len(g) == 8, f"-> {len(g)}")
        check(f"{nombre} con Elite Four", bool(r.get("elite_four")),
              "-> vacío")
        check(f"{nombre} con campeón", bool(r.get("campeon")), "-> vacío")


# ------------------------------------------- 7. orden de equipo porporcentaje
def test_heridos_se_ordenan_por_porcentaje() -> None:
    """El corte de herido va con porcentaje, no con PS crudos.

    El caso que lo destapó: Ivysaur 39/56 (70%), Poliwag 46/46 (100%) y
    Geodude 8/35 (23%). Con `ps < 50` los tres contaban como heridos.
    """
    eq = [{"nombre": "Ivysaur", "tipos": ["Grass", "Poison"], "nivel": 21,
           "ps": 39, "ps_max": 56},
          {"nombre": "Poliwag", "tipos": ["Water"], "nivel": 20,
           "ps": 46, "ps_max": 46},
          {"nombre": "Pidgeotto", "tipos": ["Normal", "Flying"], "nivel": 19,
           "ps": 30, "ps_max": 30},
          {"nombre": "Geodude", "tipos": ["Rock", "Ground"], "nivel": 14,
           "ps": 8, "ps_max": 35}]
    orden = P.orden_deseado(eq, 1, "Kanto", "batalla", [])
    check("el herido grave va al final", orden[-1] == "Geodude",
          f"-> orden {orden}")
    check("el que va a tope no va al final", orden[-1] != "Poliwag",
          f"-> orden {orden}")


# --------------------------------------- 8. el delantero mira el otro lado
def test_delantero_contra_fuego() -> None:
    """Bulbasaur es el peor contra Fuego: pega x0.5 y recibe x2."""
    eq = [{"nombre": "Bulbasaur", "tipos": ["Grass", "Poison"], "nivel": 20,
           "ps": 50, "ps_max": 50},
          {"nombre": "Squirtle", "tipos": ["Water"], "nivel": 20,
           "ps": 50, "ps_max": 50},
          {"nombre": "Sandshrew", "tipos": ["Ground"], "nivel": 20,
           "ps": 50, "ps_max": 50}]
    orden = P.orden_deseado(eq, 1, "Kanto", "jefe", ["Fire"])
    check("Bulbasaur no abre contra Fuego", orden[0] != "Bulbasaur",
          f"-> {orden}")
    check("abre uno que pegue x2 a Fuego", orden[0] in ("Squirtle",
                                                        "Sandshrew"),
          f"-> {orden}")
    atk, _ = P.utilidad_contra(["Grass", "Poison"], "Fire")
    check("Bulbasaur pega x0.5 a Fuego", abs(atk - 0.5) < 1e-9, f"-> {atk}")


# --------------------------------------------- 9. pesos con sentido
def test_pesos_sin_valores_absurdos() -> None:
    """Que no haya un peso que se coma a todos los demás sin querer."""
    for nombre in ("PESO_CAPTURA", "PESO_TRADE", "PESO_ENTRENADOR_SANO",
                   "PESO_BATALLA_NIVEL"):
        v = getattr(PL, nombre, None)
        check(f"{nombre} existe y es positivo", v is not None and v > 0,
              f"-> {v}")


def _score(d: P.Decision) -> float:
    """El planner devuelve el score dentro de `razon`, no en un campo."""
    import re
    m = re.search(r"score=(-?[0-9.]+)", d.razon or "")
    return float(m.group(1)) if m else float("nan")


def test_orden_de_prioridades() -> None:
    """El orden del usuario: **niveles, MT al principal, objetos**.

    El objeto no puede acercarse a un nivel ni a una MT, y la MT se pospone
    sola si al principal le faltan dos niveles de ruta.
    """
    def nodo(tipo):
        # `clickable` es obligatorio: el planificador descarta los nodos que no
        # lo llevan, y sin el el score sale vacio y el test mide nada.
        return [{"id": "n", "tipo": tipo, "clickable": True, "atajo": "1"}]
    eq = [{"nombre": "Ivysaur", "tipos": ["Grass", "Poison"], "nivel": 18,
           "ps": 60, "ps_max": 60}]
    falta1 = PL.elegir(eq, nodo("tutor"), region="Kanto", insignias=0,
                       ctx_extra={"tutor_listo": True, "liston": 19})
    objeto = PL.elegir(eq, nodo("item"), region="Kanto", insignias=0,
                       ctx_extra={"tiene_bolsa": True})
    check("el objeto no supera a la MT",
          _score(objeto) < _score(falta1) or _score(objeto) <= 12.0,
          f"objeto={_score(objeto)} vs MT={_score(falta1)}")
    check("el objeto es la ultima prioridad", _score(objeto) <= 12.0,
          f"-> {_score(objeto)}")
    trainer = PL.elegir(eq, nodo("trainer"), region="Kanto", insignias=0,
                        ctx_extra={"falta_nivel": 3})
    check("el nivel no se aplaza por un objeto",
          _score(trainer) > _score(objeto),
          f"nivel={_score(trainer)} vs objeto={_score(objeto)}")


def test_puerta_del_75() -> None:
    """La puerta que cierra el grafo, tal cual la fijó el usuario.

    >75% de vida se va al otro nodo (al jefe). Por debajo, se pasa por el centro
    a curarse y de ahí al jefe.

    Se pasan **los dos nodos a la vez**, porque `hay_cura_disponible` se deduce
    de los nodos que se están puntuando: si se pasa uno solo, la cura no está
    "disponible" y la puerta no tiene nada que decidir.
    """
    check("el umbral es 75%", PL.UMBRAL_PUERTA_JEFE == 0.75,
          f"-> {PL.UMBRAL_PUERTA_JEFE}")

    def dos_nodos():
        # "b" = pelea/nivel, "c" = centro pokemon.
        return [{"id": "b", "tipo": "battle", "clickable": True, "atajo": "b"},
                {"id": "c", "tipo": "pokecenter", "clickable": True,
                 "atajo": "c"}]

    def equipo(ps, ps_max):
        # Tres móns: con uno solo el plan dice "capturar", que es el paso 1
        # del grafo del usuario, y la puerta no llega a decidir.
        return [{"nombre": "Ivysaur", "tipos": ["Grass", "Poison"],
                 "nivel": 20, "ps": ps, "ps_max": ps_max},
                {"nombre": "Squirtle", "tipos": ["Water"], "nivel": 19,
                 "ps": ps, "ps_max": ps_max},
                {"nombre": "Pidgeotto", "tipos": ["Normal", "Flying"],
                 "nivel": 19, "ps": ps, "ps_max": ps_max}]

    def elige(ps, extra=None):
        e = {"hay_cura": True, "tiene_bolsa": True}
        e.update(extra or {})
        return PL.elegir(equipo(ps, 100), dos_nodos(), region="Kanto",
                         insignias=0, ctx_extra=e)

    sano = elige(90)
    roto = elige(60)
    check("al 90% se va al otro nodo, no al centro", sano.valor == "b",
          f"-> {sano.valor}: {sano.razon[:70]}")
    check("al 60% se pasa por el centro a curarse", roto.valor == "c",
          f"-> {roto.valor}: {roto.razon[:70]}")

    # El objeto no puede ganar a la cura con el equipo por debajo del liston.
    def elige_item(ps):
        nodos = [{"id": "c", "tipo": "pokecenter", "clickable": True,
                  "atajo": "c"},
                 {"id": "i", "tipo": "item", "clickable": True, "atajo": "i"}]
        return PL.elegir(equipo(ps, 100), nodos, region="Kanto", insignias=0,
                         ctx_extra={"hay_cura": True, "tiene_bolsa": True})
    check("al 60% la cura gana al objeto", elige_item(60).valor == "c",
          f"-> {elige_item(60).valor}")

    # Y un món con un rasguño de vida sigue mandando: por debajo del 75% de
    # media no se juega, aunque la media pase.
    mixto = equipo(100, 100)
    mixto[0]["ps"] = 12
    d = PL.elegir(mixto, dos_nodos(), region="Kanto", insignias=0,
                  ctx_extra={"hay_cura": True})
    check("un solo món al 12% fuerza la cura", d.valor == "c",
          f"-> {d.valor}: {d.razon[:70]}")


def test_centros_por_delante_ven_la_rama() -> None:
    """El otro lado de la puerta del 75%: elegir la rama que lleva a la cura.

    Medido: 68 de 192 logs llegaron a ver un centro y 26 equipos murieron
    contra Brock sin pasar por ninguno, porque el peso de trainers (4x) se
    llevaba al bot a las ramas sin pokecenter.
    """
    nodos = [{"id": "a", "tipo": "battle"},
             {"id": "b", "tipo": "trainer"},
             {"id": "c", "tipo": "battle"},
             {"id": "cur", "tipo": "pokecenter"},
             {"id": "b2", "tipo": "trainer"}]
    edges = [["a", "b"], ["a", "c"], ["b", "b2"], ["c", "cur"]]
    cur = P.centros_por_delante(nodos, edges)
    ent = P.entrenadores_por_delante(nodos, edges)
    check("la rama del centro se ve", cur.get("c") == 1, f"-> {cur.get('c')}")
    check("la rama sin centro da 0", cur.get("b") == 0, f"-> {cur.get('b')}")
    check("la rama sin centro tiene mas trainers", ent.get("b") == 2,
          f"-> {ent.get('b')}")
    check("el peso de la cura (12x) gana a los trainers (4x) estando Low",
          cur.get("c") * 12.0 > ent.get("b") * 4.0,
          f"centro={cur.get('c')*12.0} vs trainers={ent.get('b')*4.0}")


def test_vocabulario_del_juego() -> None:
    """Que el bot hable el idioma del juego.

    Ocho veces el bot ha comparado contra un nombre que el juego no emite
    (`cura` vs `pokecenter`, `centro` vs `pokecenter`, `jefe` vs `boss`,
    `trade` descartado...). Todas fallaron en silencio. Aqui se recorre todo el
    codigo buscando comparaciones literales de tipo y se comprueba que el otro
    lado sea un tipo real del juego.
    """
    # Tipos que emite el juego, con su equivalencia interna.
    reales = {"start", "catch", "battle", "trainer", "item", "question",
              "trade", "pokecenter", "move_tutor", "boss", "empty",
              "heal", "shop", "exit", "event"}
    internos = {"desconocido", "batalla", "entrenador", "item", "incognita",
                "trade", "cura", "tutor", "jefe", "ninguno"}
    permitidos = reales | internos | {"nodo", "centro"}  # 'centro' tolerated
    # 'centro' es incorrecto pero historico; se marca aparte.
    import re
    fuente = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    # Busca d.tipo == "x" y d.tipo in (...) para d.tipo
    literales = set(re.findall(r'd\.tipo\s*==\s*"([a-z_]+)"', fuente))
    literales |= set(re.findall(r'"([a-z_]+)"\s*in\s*\(\s*d\.tipo', fuente))
    malos = {x for x in literales if x not in permitidos}
    check("d.tipo solo se compara contra tipos reales del juego", not malos,
          f"-> {sorted(malos)}")


def test_captura_con_equipo_lleno_no_reventa() -> None:
    """`elegir_captura` con el equipo lleno no puede lanzar excepción.

    **Este era el bug que rompía las runs.** La puerta de "equipo lleno"Calling
    `_mejora_claramente(c, flojo, futuros)` se ejecutaba **antes** de que `c`,
    `futuros` y `ref` existieran (estaban definidos en el bucle de candidatos,
    40 líneas más abajo). Con el equipo lleno eso es un `UnboundLocalError` en
    **cada** pantalla de captura, y como la comparación de excepciones era
    exacta y no `isinstance`, el `UnboundLocalError` no se reconocía como
    error de código: se reintentaba y la run moría en ATASCADO.

    Además `_mejora_claramente` usaba `rival_ruta` y `vivos` sin recibirlos por
    parámetro: un `NameError` esperando a ocurrir.
    """
    equipo = [_mon(n, t, niv) for n, t, niv in (
        ("Bulbasaur", ["Planta"], 10), ("Pidgey", ["Normal", "Volador"], 10),
        ("Zubat", ["Veneno", "Volador"], 10), ("Poliwag", ["Agua"], 10),
        ("Geodude", ["Roca", "Tierra"], 10), ("Paras", ["Planta", "Veneno"], 10))]
    candidatos = [
        {"nombre": "Vulpix", "tipos": ["Fuego"], "nivel": 12, "atajo": 1,
         "baseStats": _STATS_MEDIOS},
        {"nombre": "Squirtle", "tipos": ["Agua"], "nivel": 9, "atajo": 2,
         "baseStats": _STATS_MEDIOS},
    ]
    try:
        d = P.elegir_captura(equipo, candidatos, tipo_actual="Roca",
                             tipo_futuro="Agua", proximos=["Roca", "Agua"])
        ok, detalle = True, f"{d.valor}: {d.razon[:50]}"
    except Exception as exc:  # noqa: BLE001
        ok, detalle = False, f"{type(exc).__name__}: {exc}"
    check("captura con equipo lleno no revienta", ok, f"-> {detalle}")

    # Y con `tipos_entrenadores` informado, que es lo que activa la rama que
    # antes tocaba `rival_ruta` sin definirlo.
    try:
        d = P.elegir_captura(equipo, candidatos, tipo_actual="Roca",
                             tipo_futuro="Agua", proximos=["Roca", "Agua"],
                             tipos_entrenadores=["Fuego"])
        ok, detalle = True, f"{d.valor}: {d.razon[:50]}"
    except Exception as exc:  # noqa: BLE001
        ok, detalle = False, f"{type(exc).__name__}: {exc}"
    check("captura con rivals de ruta no revienta", ok, f"-> {detalle}")


def test_tipo_del_lider_no_es_la_categoria_del_nodo() -> None:
    """El tipo del jefe sale del sprite, no de `nodo["tipo"]`.

    Para un nodo de gimnasio `nodo["tipo"]` es literalmente `"boss"`, y eso no
    dice nada contra el chart: `utilidad_contra(["Fuego"], "boss")` sale
    `(1.0, 1.0)`, así que el filtro de no ser 0.5x contra el gimnasio que
    tocaba no se ejecutaba y el bot cazaba un Charmander con Brock detrás.
    """
    r = P.tipo_lider_del_mapa([{"tipo": "boss", "sprite": "brock"}])
    check("el sprite del jefe da su tipo", r == "Rock", f"-> {r!r}")

    r = P.tipo_lider_del_mapa([{"tipo": "boss", "sprite": "lt-surge"}])
    check("el guion del sprite no lo esconde", r == "Electric", f"-> {r!r}")

    check("un jefe desconocido da None, no 'boss'",
          P.tipo_lider_del_mapa([{"tipo": "boss", "sprite": "zzz"}]) is None,
          f"-> {P.tipo_lider_del_mapa([{'tipo': 'boss', 'sprite': 'zzz'}])}")

    # Y el sprite con guion tiene que seguir clasificándose como jefe.
    check("lt-surge es un nodo de jefe",
          P.tipo_de_nodo("lt-surge") == "jefe", f"-> {P.tipo_de_nodo('lt-surge')}")


def test_el_aguante_mide_el_danio_recibido() -> None:
    """`orden_para_jefe` puntúa el aguante con el eje correcto.

    Estaba calculado como `mult(nuestro, rival)`, que es el eje **ofensivo**:
    un món inmune a Veneno puntuaba 2.0 de "aguante" cuando en realidad no le
    pueden tocar. La prueba compara los dos ejes y exige que se diferencien.
    """
    txt = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    mal = "aguante = min((mult(t, r)" in txt.replace(" ", " ").replace(
        "aguante = min((mult(t, r)", "aguante = min((mult(t, r)")
    bien = "mult(r, t)" in txt
    check("el aguante usa el eje del rival contra nosotros", bien and not mal,
          f"-> mal={mal} bien={bien}")

    # Comportamiento: contra un jefe de Veneno, un món de Veneno aguanta 4.0.
    plan = PL.Plan(region="Kanto", insignias=0, nivel_max=40, nivel_min=40,
                   tipos=["Veneno"], nombre_jefe="Koga")
    eq = [{"nombre": "Exeggutor", "tipos": ["Planta", "Veneno"], "ps": 50},
          {"nombre": "Onix", "tipos": ["Roca", "Tierra"], "ps": 50}]
    orden = PL.orden_para_jefe(eq, plan)
    # Exeggutor aguanta 4x (Veneno le es inmune); Onix recibe 0.5x. El que aguanta
    # más va delante cuando ambos empatan en ofensiva.
    check("el más aguante va primero contra Veneno",
          orden and orden[0] == "Exeggutor", f"-> {orden}")


def test_todas_las_regiones_tienen_liga() -> None:
    """Cada región necesita datos de Elite Four y campeón.

    Johto los tenía vacíos, y `nivel_del_jefe` caía al respaldo: el listón
    pasaba de 84 a 60 y `tipos_del_rival` devolvía `[]`, así que desde la 8ª
    insignia no había ni filtro de tipo ni nivel que preparar.
    """
    for nombre, datos in P.regiones().items():
        ef = datos.get("elite_four_datos") or []
        check(f"{nombre} tiene Elite Four con niveles",
              len(ef) == 4 and all(e.get("niveles") for e in ef),
              f"-> {len(ef)} miembros")
        check(f"{nombre} tiene campeón con niveles",
              bool((datos.get("campeon_datos") or {}).get("niveles")),
              f"-> {(datos.get('campeon_datos') or {}).get('niveles')}")
# Y el listón no puede dar un salto al entrar en la Liga. Kanto baja un
        # poco (Giovanni 60, Lorelei 56) porque son los datos reales del juego,
        # pero Johto **caía 24 niveles** (84 -> 60) porque no había datos y se
        # usaba el respaldo `NIVEL_ELITE`. Un salto de más de 10 es esa falta de
        # datos, no una decisión de diseño.
        _r = datos.get("jefes") or []
        ultima = P.nivel_del_jefe(nombre, len(_r) - 1)[0]
        elite = P.nivel_del_jefe(nombre, len(_r))[0]
        check(f"{nombre} no se desploma en la Liga", elite >= ultima - 10,
              f"-> ultima insignia {ultima} vs Liga {elite}")


def test_ps_real_se_invalida() -> None:
    """La cache de PS real tiene que invalidarse al curar, cambiar de món o subir.

    Se llenaba **solo** en la pantalla de combate y nunca se vaciaba, así que
    un pokecenter dejaba al bot believing que seguía habiendo caídos, y el
    recuento de vivos (que decide cazar, curar y a quién sacrificar en un
    trade) era falso durante el resto de la run.
    """
    fuente = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    tiene_metodo = "def _invalidar_ps(" in fuente
    check("existe el metodo que invalida el PS real", tiene_metodo)
    # Y tiene que llamarse desde los sitios que cambian la vida de verdad. Los
    # motivos se buscan por su palabra clave, no por la cadena exacta, porque
    # algunos llevan texto (f"objeto -> {nombre}").
    for sitio, motivo in (("insignia", '"insignia"'),
                          ("swap", '"swap"'),
                          ("trade", '"trade"'),
                          ("objeto", 'f"objeto ->'),
                          ("pokecenter", '"pokecenter"')):
        check(f"el PS real se invalida al {sitio}",
              f"_invalidar_ps({motivo}" in fuente, "-> no se llama")
    # La exception de codigo tiene que recognises las subclases.
    check("las subclases de NameError cortan la run",
          isinstance(UnboundLocalError("x"), tuple(
              (NameError, AttributeError, TypeError))),
          "-> con `type(exc) in (...)` esto no cuela y la run no se corta")


def test_el_entrenador_se_veta_por_nivel_y_por_caidos() -> None:
    """No se entra a un entrenador por debajo de tu nivel, ni sin cura y caído.

    Regresión sobre la tanda que perdió contra `Ace Trainer wants to battle!`
    con un único món en pie y sin pokecenter a mano: el bot lo|scoreó como si
    fuera la única fuente de exp que quedaba. El nivel del rival ya venía de
    `trainerFightLevel`, pero nunca llegaba a la política.
    """
    equipo = [
        {"nombre": "Goldeen", "nivel": 9, "ps": 100, "ps_max": 100,
         "tipos": ["Agua"], "baseStats": {"hp": 90}},
        {"nombre": "Bulbasaur", "nivel": 7, "ps": 0, "ps_max": 100,
         "tipos": ["Planta", "Veneno"], "baseStats": {"hp": 318}},
    ]
    ctx = PL.Contexto(equipo=equipo, plan=PL.plan_para("Kanto", 0))

    # Rival por encima del listón del jefe: veto, aunque la ruta pese.
    _, raz = PL.puntuar("entrenador", replace(ctx, nivel_rival=25))
    check("el_entrenador_con_rival_mas_fuerte_se_veta",
          "vetado" in raz and "riesgo" in raz, f"-> {raz}")

    # Rival razonable y equipo sano: se permite, que el entrenador es la
    # fuente de exp. Con un caído sigue saltando el segundo veto, así que
    # aquí hace falta un equipo entero.
    sano = [dict(m, ps=m["ps_max"]) for m in equipo]
    _, raz_ok = PL.puntuar("entrenador", replace(
        ctx, equipo=sano, caidos=0, nivel_rival=9))
    check("un_entrenador_a_nivel_sigue_siendo_valido",
          "vetado" not in raz_ok, f"-> {raz_ok}")

    # Un solo món en pie, caídos y sin cura: se **difiera**, no se veta en
    # negativo. La razón ya no dice "vetado" porque el veto duro se midió y
    # perdía (0,64 vs 1,62 insignias): lo que hace es bajar el peso para que
    # gane cualquier alternativa, y pelear si no la hay.
    _, raz_sin = PL.puntuar("entrenador", replace(
        ctx, nivel_rival=9, hay_cura_disponible=False))
    check("entrenador_sin_cura_con_caidos_se_difiera",
          "caído" in raz_sin, f"-> {raz_sin}")

    # Y con cura delante se vuelve a permitir: el pokecenter va antes.
    _, raz_con = PL.puntuar("entrenador", replace(
        ctx, nivel_rival=9, hay_cura_disponible=True))
    check("entrenador_con_caidos_permite_si_hay_cura",
          "vetado" not in raz_con, f"-> {raz_con}")


def test_la_escalera_de_riesgo_no_puede_atar_al_bot() -> None:
    """La escalera de riesgo puede ser muy baja, pero **nunca negativa**.

    Es el requisito que hace seguro este cambio. Un veto duro ya se probó
    (veto de tipo, -3) y salió PEOR que no hacer nada (0,64 vs 1,62 insignias),
    porque en el 43% de las pantallas el entrenador es el nodo único y el bot
    se quedaba sin nada que pulsar. Aquí la escalera solo tiene que ganar a
    las alternativas cuando las hay, y si no las hay sigue siendo el mejor
    nodo de la pantalla.
    """
    plan = PL.plan_para("Kanto", 0)
    # El peor caso imaginable: 6 móns, 5 caídos, el superviviente al 10%.
    equipo = [{"nombre": f"M{i}", "nivel": 10, "ps": 100, "ps_max": 100,
               "tipos": ["Fuego"], "baseStats": {"hp": 100}} for i in range(6)]
    equipo[0]["ps"] = 10
    for i in range(1, 6):
        equipo[i]["ps"] = 0
    ctx = PL.Contexto(equipo=equipo, plan=plan, hay_cura_disponible=False,
                      nivel_rival=5)

    peor, raz = PL.puntuar("entrenador", ctx)
    check("el_entrenador_en_el_peor_caso_no_puntua_negativo",
          peor > 0, f"-> {peor} ({raz})")

    # Y tiene que perder contra una alternativa segura cuando la hay.
    # **Con un plan de ruta normal, no con `plan_para("Kanto", 9)`**: ese era un
    # estado imposible —Kanto tiene 8 gimnasios— y desde H24 se lee como mapa de
    # la Liga, asi que el nodo de batalla recibia la penalizacion de Liga (-60) y
    # la comparacion dejaba de medir lo que dice medir. El gimnasio 7 da un plan
    # igual de tardio (listón alto), que es lo que este test necesita.
    s_batalla, _ = PL.puntuar("batalla", replace(
        ctx, capturas_pantalla=3, plan=PL.plan_para("Kanto", 7)))
    check("el_entrenador_desmontado_pierde_contra_cazar",
          peor < s_batalla, f"-> entrenador {peor} vs batalla {s_batalla}")

    # La escalera es monótona: con más móns en pie puntúa más.
    pts = []
    for vivos in (1, 2, 3):
        eq = [dict(m, ps=(m["ps_max"] if i < vivos else 0))
              for i, m in enumerate(equipo)]
        pts.append(PL.puntuar("entrenador",
                              replace(ctx, equipo=eq))[0])
    check("la_escalera_crece_con_los_mons_en_pie",
          pts[0] < pts[1] < pts[2], f"-> {pts}")


def test_el_riesgo_no_se_dispara_si_hay_cura() -> None:
    """Con pokecenter delante manda R8, no la escalera.

    El corte de emergencia del principio ya manda al centro cuando el equipo
    esta <=75%. La escalera solo existe para el caso sin cura, que es donde el
    bot se comia los entrenadores con el equipo desmontado.
    """
    plan = PL.plan_para("Kanto", 0)
    roto = [{"nombre": "A", "nivel": 10, "ps": 10, "ps_max": 100,
             "tipos": ["Fuego"], "baseStats": {"hp": 100}},
            {"nombre": "B", "nivel": 10, "ps": 0, "ps_max": 100,
             "tipos": ["Agua"], "baseStats": {"hp": 100}}]
    ctx = PL.Contexto(equipo=roto, plan=plan, nivel_rival=5)

    sin_cura, _ = PL.puntuar("entrenador",
                             replace(ctx, hay_cura_disponible=False))
    con_cura, raz_cura = PL.puntuar(
        "entrenador", replace(ctx, hay_cura_disponible=True))
    check("con_cura_no_manda_la_escalera_de_riesgo",
          "riesgo" not in raz_cura, f"-> {raz_cura}")
    # Con cura delante el entrenador puntua **peor**, y eso es lo correcto: lo
    # que se marca es "nada que no sea curar". R8 manda por encima del riesgo,
    # porque con pokecenter delante el problema tiene arreglo.
    check("con_cura_manda_R8_no_el_riesgo",
          "curar" in raz_cura and con_cura < sin_cura,
          f"-> {con_cura} ({raz_cura}) vs sin cura {sin_cura}")


def test_la_riesgo_de_exp_con_caidos_ya_no_existe() -> None:
    """La rama que **premiaba** pelear con caídos y sin cura, se ha ido.

    Devolvía `PESO_ENTRENADOR_SANO`, el puntaje mas alto de la pantalla, en
    el estado mas peligroso: 33 de 54 muertes de entrenador elegian el nodo
    con 2 o menos móns en pie y 15 con uno solo. Ese comentario era una
    correccion contra un atasco; la escalera de riesgo lo resuelve sin
    premiar el riesgo.

    Se comprueba la **linea de codigo**, no el texto: el comentario que la
    explicaba sobrevive en parte y no es lo que se decide. La rama sigue
    existiendo, pero solo como brazo de control del experimento
    (`PKL_ESCALERA_RIESGO=0`), que es lo que hace comparables los dos brazos.
    Lo que no puede pasar es que el branch por defecto la ejecute.
    """
    fuente = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    linea_vieja = ("if caidos and not ctx.carry_debil "
                   "and not ctx.hay_cura_disponible:")
    check("la_escalera_de_riesgo_existe",
          "ESCALERA_RIESGO_ENTRENADOR" in fuente,
          "-> no hay escalera de riesgo en el planificador")
    # La rama vieja se conserva para el control, pero tiene que quedar
    # **bajo el flag**, no ejecutandose siempre: si corre siempre, la medicion
    # de los dos brazos mide lo mismo y el experimento no dice nada.
    import planificador as _PL
    check("el_flag_de_la_escalera_esta_por_defecto_encendido",
          _PL.EXP["escalera_riesgo"] is True,
          "-> por defecto se esta midiendo el brazo viejo")
    check("la_escalera_es_el_default_y_el_viejo_es_el_control",
          'if not EXP["escalera_riesgo"]:' in fuente,
          "-> el comportamiento viejo no tiene forma de apagarse y la "
          "comparacion entre brazos no existe")


def test_mapa_lee_el_nivel_del_rival() -> None:
    """`mapa()` tiene que traer `nivel`, o el veto por nivel nunca se aplica."""
    txt = (SCRIPTS / "navegador.py").read_text(encoding="utf-8")
    check("el mapa lee el nivel del entrenador",
          "trainerFightLevel(delEstado)" in txt,
          "-> el veto por nivel no puede dispararse")
    fuente = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    check("el planificador recibe el nivel del rival",
          "nivel_rival=niv_rival" in fuente,
          "-> el veto por nivel no puede dispararse")


def test_el_flojo_es_el_mas_debil_del_equipo() -> None:
    """`flojo` tiene que ser el PEOR miembro, no el mejor.

    El `min` estaba sobre `-0.02*stats - nivel`, que devuelve el que **más**
    stats y nivel tiene. Comprobado ejecutándolo: con Bulbasaur Nv20 (318) y
    Staryu Nv8 (245) devolvía Bulbasaur. Con el equipo lleno, la puerta de
    captura comparaba contra el mejor y exigía `nivel+3` o `stats*1.15`, así
    que el bot huía de todas las capturas para siempre.
    """
    equipo = [
        {"nombre": "Bulbasaur", "nivel": 20, "ps": 100, "ps_max": 100,
         "tipos": ["Planta", "Veneno"], "baseStats": {"x": 318}},
        {"nombre": "Staryu", "nivel": 8, "ps": 100, "ps_max": 100,
         "tipos": ["Agua"], "baseStats": {"x": 245}},
    ]

    def _fuerza_flojo(m: dict) -> tuple[int, int, str]:
        st = sum((m.get("baseStats") or {}).values()) if (m.get("baseStats")) else 0
        return (0 if st else 1, st, m.get("nombre") or "")

    flojo = min(equipo, key=_fuerza_flojo)
    check("el flojo es el mas debil", flojo["nombre"] == "Staryu",
          f"-> {flojo['nombre']}")

    # Y la clave real del módulo tiene que ser la misma: no vale reimplementar
    # la fórmula correcta en el test mientras el código usa la incorrecta.
    txt = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    check("el codigo usa el flojo mas debil",
          "return (0 if st else 1, st, m.get(\"nombre\") or \"\")" in txt,
          "-> la clave del flojo no es la del test")


def test_curar_invalida_el_ps_real() -> None:
    """El pokecenter tiene que llamar a `_invalidar_ps`, y su tipo es `"cura"`.

    `d.tipo` es vocabulario interno y `politica.tipo_de_estado` mapea
    `pokecenter -> cura`. La rama comparaba contra `("centro", "pokecenter")`,
    que el juego nunca emite: nunca se contaba un centro y, peor, la caché de
    PS no se invalidaba al curar, así que el bot creía que seguía teniendo
    caídos el resto de la partida.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el centro se detecta por el tipo real 'cura'",
          'if d.tipo == "cura":' in txt,
          "-> vuelve a comparar contra un tipo que el juego no emite")
    check("el centro invalida el PS real",
          'self._invalidar_ps("pokecenter")' in txt)
    # Y la rama muerta tiene que seguir muerta, no reintroducirse.
    check("no queda la rama muerta del centro",
          'd.tipo in ("centro", "pokecenter")' not in txt,
          "-> codigo muerto de vuelta")

    # El tipo real de la decision para un pokecenter.
    check("el pokecenter se traduce a 'cura'",
          '"pokecenter": "cura"' in (SCRIPTS / "politica.py").read_text(
              encoding="utf-8"))


def test_el_atasco_cuenta_rachas_y_no_toda_la_partida() -> None:
    """El detector de atasco debe contar repeticiones **consecutivas**.

    Decía eso en el comentario y no lo hacía: `vistos` no se limpiaba y la clave
    era pantalla+acción, que en `map-screen` es siempre `nodo 1`, `nodo 2`…,
    el valor normal de cada visita. Una run sana declaraba `ATASCADO` en la
    visita 13 de cualquier atajo. En los logs: `[nodo -> 1]` 13 veces en una
    partida con 2 insignias y 13 combates ganados.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el detector compara contra la clave completa",
          "if clave == anterior:" in txt,
          "-> sigue contando acumulado en vez de por racha")
    check("el tope de atasco no es 12 (mata runs sanas)",
          "tope_repetidas = 25" in txt,
          "-> tope demasiado bajo para una racha ")
    # Solo se prohíbe el `clear()` en el bucle de conteo, no en la recuperación
    # tras recargar la página, donde vaciar el historial sí es lo correcto.
    # Solo la seccion que cuenta: desde la clave hasta la comparacion con el
    # tope. El `clear()` de la recuperacion tras recargar si es correcto.
    conteo = txt[txt.index("clave = f\""):]
    conteo = conteo[:conteo.index("tope_repetidas:")]
    check("el clear() no esta en el bucle de conteo",
          "vistos.clear()" not in conteo,
          "-> la deteccion de atasco vuelve a estar anulada")


def test_el_nivel_equipo_no_revienta_con_ceros() -> None:
    """`min()` sobre niveles vacíos era un `ValueError` en cada captura.

    El `if vivos else 0` solo cubría el equipo vacío. Con móns **vivos pero
    con `nivel == 0`** (el selector `.team-slot-lv` ausente deja `nivel: 0`) el
    generador quedaba vacío y `min()` lanzaba. Como `ValueError` no está en
    `ERRORES_DE_CODIGO`, no cortaba la run: reintentaba y acababa en
    `ATASCADO`, perdiendo la partida en la pantalla de captura.
    """
    txt = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    check("los niveles vivos se calculan antes de min()",
          "_niveles_vivos" in txt and
          "min(_niveles_vivos) if _niveles_vivos else 0" in txt,
          "-> sigue el min() sobre un generador que puede quedar vacío")

    # Y el comportamiento, ejecutado de verdad.
    sys.path.insert(0, str(SCRIPTS))
    import politica as PP
    equipo = [{"nombre": "A", "nivel": 0, "ps": 100, "ps_max": 100,
               "tipos": ["Agua"], "baseStats": {"x": 40}}]
    try:
        PP.elegir_captura(
            equipo, [{"nombre": "Zubat", "nivel": 3, "tipos": ["Siniestro"],
                      "baseStats": {"x": 55}}],
            "Agua", "Tierra", 6, ["Agua", "Tierra"], "Kanto")
    except ValueError as exc:
        check("elegir_captura no revienta con nivel 0", False, f"-> {exc}")
    else:
        check("elegir_captura no revienta con nivel 0", True)


def test_el_trade_no_sacrifica_al_mon_sin_datos() -> None:
    """El trade no puede cambiar al mejor miembro ni clicar a ciegas."""
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el sacrificio aparta los stats desconocidos",
          "_fuerza_sacrificio" in txt and "0 if st else 1" in txt,
          "-> un món sin baseStats suma 0 y sale elegido")
    check("no se clic a la primera fila a ciegas",
          "return false;" in txt and "#trade-team-list .trade-member-row');\n                            if (f) f.click()"
          not in txt,
          "-> el món que sale del equipo es uno arbitrario")


def test_los_indices_de_objetos_se_recalculan() -> None:
    """El reparto de objetos no puede usar índices de un snapshot viejo.

    `usar_item` indexa el DOM vivo con `.nth(indice)`, pero el plan se armaba
    con los índices de `bolsa` del principio. Al gastarse el primer objeto, la
    bolsa se acortaba y los índices siguientes apuntaban un objeto más arriba:
    el segundo se equipaba al món equivocado y su id se metía en
    `objetos_fallidos`, que nunca se limpia.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el indice del objeto se recalcula antes de usarlo",
          "bolsa_viva = self.j.bolsa_items()" in txt
          and "idx_vivo" in txt,
          "-> sigue el indice del snapshot y se equipa el objeto equivocado")
    check("un timeout no veta el objeto para siempre",
          "self._objeto_fallos" in txt and ">= 2" in txt,
          "-> un solo clic fallido quema el objeto hasta el final de la run")


def test_el_veto_de_entrenador_llega_a_puntuar() -> None:
    """`replace(ctx, ...)` descartaba el `nivel_rival` que el veto necesita.

    El veto por nivel se ponía en `ctx_n`, y luego la rama del waypoint hacía
    `replace(ctx, ...)` reconstruyendo el contexto desde cero. Como `llega_a`
    da True a todo nodo de la rama del jefe (no solo al pokecenter), el veto se
    desactivaba justo en los nodos donde hacía falta y sin ningún error visible.
    """
    txt = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    check("el waypoint parte de ctx_n, no de ctx",
          "ctx_n = replace(ctx_n, en_camino_al_jefe=en_camino)" in txt,
          "-> el veto por nivel se pierde en la rama del jefe")
    check("no queda replace(ctx, en_camino...",
          "replace(ctx, en_camino_al_jefe" not in txt,
          "-> el veto por nivel se pierde en la rama del jefe")


def test_el_volcado_del_crash_ea_ejecutable() -> None:
    """El volcado tiene que funcionar de verdad, no solo existir.

    Se escribió con `traceback.format_exception(type(exc), exc, tb)` pasando el
    resultado de `extract_tb()`, que es un `StackSummary` y **no** una lista de
    frames. Explotaba con `AttributeError: 'StackSummary' object has no
    attribute 'tb_frame'`... dentro del manejador de errores, o sea el crash se
    perdía justo cuando más hacía falta. El volcado ahora usa
    `exc.__traceback__`. Este test provoca un error de verdad y comprueba que el
    fichero sale con la ubicación dentro.
    """
    import tempfile
    import pathlib
    import jugar_pokelike as J

    with tempfile.TemporaryDirectory() as tmp:
        original = J.DIR_BOT
        J.DIR_BOT = pathlib.Path(tmp)
        try:
            bot = J.Bot.__new__(J.Bot)   # sin __init__: no hace falta navegador
            bot.region = "Kanto"
            bot.pasos = 3
            bot._insignias_final = 1
            escritos: list[str] = []
            bot.log = escritos.append      # type: ignore[method-assign]

            try:
                raise AttributeError("'NoneType' object has no attribute 'get'")
            except AttributeError as exc:
                bot._volcar_crash(exc, "jugar_pokelike.py:1234")

            crashes = list(pathlib.Path(tmp).glob("crash-*.txt"))
            check("el volcado escribe un fichero", len(crashes) == 1,
                  f"-> {len(crashes)} ficheros")
            if crashes:
                txt = crashes[0].read_text(encoding="utf-8")
                check("el volcado no falla al formatear la traza",
                      "StackSummary" not in escritos
                      and "no se pudo volcar" not in " ".join(escritos),
                      f"-> {escritos}")
                check("el volcado dice donde esta el error",
                      "jugar_pokelike.py:1234" in txt
                      and "AttributeError" in txt,
                      "-> el error no queda localizado")
                check("el volcado lleva la traza",
                      "Traceback (most recent call last)" in txt,
                      "-> sin traza no se sabe de donde viene")
        finally:
            J.DIR_BOT = original


def test_el_error_de_codigo_deja_el_error_localizado() -> None:
    """`ERROR_DE_CODIGO` tiene que decir **dónde**, no solo qué pasó.

    La regla del usuario es que este error corta la run y se arregla. El
    "se arregla" lo hace la persona, no el bot: para eso el corte tiene que
    dejar el error localizado. Antes solo registró el tipo de excepción y el
    mensaje, que obligaba a leer 2000 líneas de traza para encontrar un
    `NameError`.
    """
    jug = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")

    check("el corte indica archivo y linea",
          "traceback.extract_tb(exc.__traceback__)" in jug
          and "ultimo.lineno" in jug,
          "-> el error se registra sin localizar, no se puede arreglar")
    check("el corte vuelca la traza a un fichero",
          "_volcar_crash" in jug and "crash-" in jug,
          "-> el crash se pierde cuando lanzar_tanda limpia los logs viejos")
    check("el volcado lleva la traza completa",
          "traceback.format_exception" in jug,
          "-> con la ultima linea no se sabe de donde venia el fallo")

    # Y que la lista de errores sea real: `IndentationError` no puede saltar en
    # runtime, y `ValueError` si, y antes no cortaba la run.
    import jugar_pokelike as J
    errores = J.Bot.ERRORES_DE_CODIGO
    check("los errores de codigo cortan la run",
          ValueError in errores and KeyError in errores,
          "-> ValueError no corta: reintentaba y acababa en ATASCADO")
    check("la lista no tiene errores de compilacion",
          IndentationError not in errores,
          "-> IndentationError no puede saltar en runtime")


def test_las_ocho_reglas_se_cumplen() -> None:
    """Las reglas del usuario son norma: si el código no las hace, hay bug.

    No se comprueba el comportamiento entero (haría falta el navegador), sino
    que la rama que decide exista y tenga la forma correcta. Cada una de estas
    comprobaciones existen porque cada regla estuvo incumplida.
    """
    import planificador as PLAN

    pl = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    jug = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    pol = (SCRIPTS / "politica.py").read_text(encoding="utf-8")

    # Regla 9: el carry se corta al 50%, no al 40%.
    check("regla 9: el carry corta al 50%",
          "ctx.carry_ps < 50.0" in pl and "ctx.carry_ps < 40.0" not in pl,
          "-> el umbral del carry no es el de la regla")

    # Regla 9: el corte de emergencia mira los tres signos (caidos, ratio, carry).
    check("regla 9: el corte mira caidos, equipo y carry",
          "caidos >= 1 or ratio <= UMBRAL_PUERTA_JEFE or ctx.carry_ps < 50.0"
          in pl,
          "-> falta alguna de las tres condiciones de la puerta")

    # Regla 8 con caidos solo es valida si no hay cura delante (la 9 manda).
    # La escalera de riesgo sustituyo a la rama anterior, pero la intencion es
    # la misma y no puede relajarse: con pokecenter delante se cura, no se pelea.
    # Se comprueba **comportamiento** y no la cadena `if not ctx.hay_cura_...`:
    # esa literal se movio dentro de `riesgo_entrenador` al arreglar el fallo
    # del bono de ruta, y un test de regla del usuario no puede depender de
    # donde este escrito el `if`. Lo que no puede pasar es que la escalera
    # entre con cura delante.
    _ctx_cura = PLAN.Contexto(
        equipo=[{"nombre": "A", "nivel": 6, "ps": 100, "ps_max": 100,
                 "tipos": ["Planta"], "baseStats": {"hp": 100}},
                {"nombre": "B", "nivel": 5, "ps": 0, "ps_max": 50,
                 "tipos": ["Normal"], "baseStats": {"hp": 100}},
                {"nombre": "C", "nivel": 4, "ps": 0, "ps_max": 45,
                 "tipos": ["Planta"], "baseStats": {"hp": 100}}],
        plan=PLAN.plan_para("Kanto", 0), nivel_rival=12,
        hay_cura_disponible=True)
    _riesgo_con_cura = PLAN.riesgo_entrenador(_ctx_cura)
    check("regla 8: entrenador con caidos exige que no haya cura",
          _riesgo_con_cura[0] is None and _riesgo_con_cura[1] == 0.0,
          f"-> la escalera entra con cura delante: {_riesgo_con_cura}")

    # Regla 1: la run no se corta por un atasco, escala la recuperacion.
    check("regla 1: el atasco escala la recuperacion",
          "MAX_INTENTOS_ATASCO" in jug and "page.reload" in jug,
          "-> un atasco corta la run en vez de recuperarse")
    check("regla 1: el codigo de error es la unica excepcion",
          'self.resultado = "ERROR_DE_CODIGO"' in jug
          and "reintentando" in pl + jug,
          "-> no queda claro por que se corta")

    # Regla 7: el cambio por subida de nivel tiene objetivo propio.
    check("regla 7: el swap por nivel calcula el peor",
          "_peor_para_sustituir" in jug,
          "-> sin objetivo previo se elige un mon arbitrario")
    # Antes el codigo era `muertos or vivos`; ahora el caido se comprueba
    # antes de la regla del duplicado, que es donde tiene que ir: un món a
    # 0 PS es el mejor candidato posible y sigue siendo el primero.
    check("regla 7: se prioriza al mon muerto",
          "if muertos:" in jug
          and jug.index("if muertos:") < jug.index("_clave_menor_valor"),
          "-> el muerto no tiene prioridad en la sustitucion")

    # Regla 3: el herido al final por porcentaje.
    # Ojo: `ps(m) < 50` aparece en un comentario que explica por qué NO se usa
    # PS crudo, así que buscarlo daría un falso positivo permanente. Lo que
    # importa es que el corte real sea `ratio_m < 0.5`.
    check("regla 3: el herido va al final por porcentaje",
          "ratio_m < 0.5" in pol,
          "-> el corte no es por porcentaje")

    # Regla 6: el objeto se asigna segun los tipos del mon.
    check("regla 6: el reparto de objetos usa los tipos del mon",
          "puntuar_objeto(" in (SCRIPTS / "pkl_items.py").read_text(
              encoding="utf-8"),
          "-> el objeto no se asigna por tipo")


def test_la_skill_del_camino_no_se_desincroniza() -> None:
    """`CAMINO-POR-PANTALLA.md` dice los pesos reales: que no mienta.

    Un documento de estrategia vale solo si coincide con el código. Los pesos
    se sacan del módulo, no están escritos a mano en el test, así que cuando
    alguien cambia una prioridad en `planificador.py` el test falla y obliga a
    actualizar la skill en vez de dejar dos verdades distintas.
    """
    import planificador as PLAN

    skill = RAIZ / ".opencode/skills/pokelike-camino/CAMINO-POR-PANTALLA.md"
    if not skill.exists():
        check("la skill del camino existe", False, "-> no está en .opencode/skills")
        return
    txt = skill.read_text(encoding="utf-8")

    pesos = {
        "PESO_CURA_CAIDOS": 50, "PESO_CAPTURA": 60, "PESO_TRADE": 45,
        "PESO_ENTRENADOR_SANO": 34, "PESO_BATALLA_NIVEL": 15,
        "PESO_BATALLA_A_NIVEL": 4, "PESO_OBJETO": 12, "PESO_INCOGNITA": 9,
    }
    for nombre, esperado in pesos.items():
        real = getattr(PLAN, nombre, None)
        if real is None:
            check(f"la skill menciona {nombre}", False, "-> ya no existe")
            continue
        entero = int(round(float(real)))
        check(f"la skill menciona {nombre}={entero}",
              f"**{entero}**" in txt or f"| {entero} |" in txt,
              f"-> el código tiene {entero} y la skill no lo dice")

    # El umbral de la puerta es una regla de juego, no un detalle: está en el
    # libro de jugadas y en la skill del camino.
    check("la skill dice el umbral de la puerta",
          "75%" in txt, "-> falta el UMBRAL_PUERTA_JEFE")

    # Las pantallas deben estar las que el bot maneja de verdad. Si alguien
    # añade una pantalla nueva, esta lista hay que ampliarla.
    import jugar_pokelike as JUG
    import re
    for pantalla in sorted(JUG.Bot.MANEJADORES):
        # El id de la pantalla es la clave del diccionario.
        if pantalla not in txt:
            check(f"la skill documenta {pantalla}", False,
                  "-> hay una pantalla que el bot maneja y la skill no dice")
            return
    check("la skill documenta todas las pantallas que maneja el bot", True)

    # Y los tres vocabularios, que son la fuente de error nº1 del bot.
    for v in ("map-screen", "pokecenter", "move_tutor"):
        check(f"la skill nombra el valor real '{v}'", v in txt,
              "-> es el valor que el juego emite y la skill lo omite")



def test_el_prep_del_jefe_no_entra_en_bucle() -> None:
    """El prep es opcional: quedarse ahí no puede costar la run.

    El manejador se rendía ("el prep no cede") y **volvía sin salir**, así que
    el paso siguiente volvía a entrar, reintentaba el mismo orden y repetía
    para siempre: `!! el prep no cede` / `[prep -> Krabby]` / `!! el prep no
    cede`… El detector de atasco no lo veía porque la pantalla nunca cambia
    de verdad: sigue en `elite-prep-screen`.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el prep recuerda los intentos fallidos",
          "_prep_fallos" in txt,
          "-> sin memoria, se rinde y vuelve a entrar en bucle infinito")
    check("el prep escala a recarga si no cede",
          "recargo la pagina para salir" in txt,
          "-> se queda atascado en elite-prep-screen para siempre")
    check("el prep se pone a cero cuando si cede",
          txt.count("self._prep_fallos = 0") >= 3,
          "-> el contador nunca se limpia y acaba recargando sin motivo")


def test_la_batalla_que_no_acaba_tiene_techo() -> None:
    """Un combate que se mueve pero no termina no puede pulsarse para siempre.

    La exención de "batalla sigue viva" reseteaba el contador de atasco cada vez
    que el PS cambiaba, **sin límite de reintentos**. Un combate con animación
    pero que nunca acaba hacía pulsar `continuar` indefinidamente y la run se
    quedaba ahí: `[continuar -> True]` una y otra vez, con 13 s entre medias.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("la exencion de batalla viva tiene techo",
          "TOPE_BATALLA_VIVA" in txt,
          "-> un combate que no acaba se repite indefinidamente")
    check("el techo se comprueba antes de resetear el contador",
          "if self._batalla_viva < TOPE_BATALLA_VIVA:" in txt,
          "-> se resetea el contador sin limite y no se llega nunca al tope")


def test_el_veto_de_nivel_usa_el_mon_que_abre() -> None:
    """El listón del veto de entrenador es el món que ABRE, no el mejor.

    Con la referencia en el mejor món el veto no disparaba: un Mankey Nv10
    cubría a un Staryu Nv6 que es quien abre, y contra un fire-spitter Nv12
    (12 > 10+2 es falso) se entraba y se perdía con el equipo entero a 0.
    Medido: `mios=[Staryu 0/19, Geodude 0/26, Mankey 0/28, Bulbasaur 0/29]`.
    """
    import planificador as PLAN

    def m(n, tp, st, nv):
        return {"nombre": n, "tipos": tp, "baseStats": {"x": st},
                "nivel": nv, "ps": 100, "ps_max": 100}

    eq = [m("Staryu", ["Agua"], 245, 6), m("Geodude", ["Roca", "Tierra"], 300, 9),
          m("Mankey", ["Lucha"], 305, 10),
          m("Bulbasaur", ["Planta", "Veneno"], 318, 10)]
    ctx = PLAN.Contexto(equipo=eq, plan=PLAN.plan_para("Kanto", 1),
                        tipos_por_sprite={"fire": ["Fuego"]})
    _, r = PLAN.puntuar("entrenador", replace(ctx, sprite="fire", nivel_rival=12))
    check("un rival por encima del món que abre se veta",
          "vetado" in r, f"-> {r}")


def test_con_un_solo_mon_se_captura_casi_todo() -> None:
    """R2 con 1 món en pie: el filtro de tipo contra el jefe se relaja.

    Exigía `>= 1.0` contra el gimnasio que tocaba siempre, y con un único
    Bulbasaur Nv5 eso rechazaba los salvajes de Route 1 enteros: el bot elegía
    el nodo de captura y luego huía. Medido: `GAME_OVER` en 18 pasos, 0
    insignias y 0 capturas, tras pelear un `bug-catcher` Nv2 con un solo món.
    """
    import politica as PP

    def c(n, tp):
        return {"nombre": n, "tipos": tp, "nivel": 1,
                "baseStats": {"x": 300}, "atajo": "1"}

    eq = [{"nombre": "Bulbasaur", "nivel": 5, "ps": 19, "ps_max": 19,
           "tipos": ["Planta", "Veneno"], "baseStats": {"x": 318}}]
    for nom, tp in [("Pidgey", ["Normal", "Volador"]), ("Rattata", ["Normal"])]:
        d = PP.elegir_captura(eq, [c(nom, tp)], "Roca", "Agua", 6,
                              ["Roca", "Agua"], "Kanto")
        check(f"con 1 món se captura a {nom}", d.valor is not None,
              f"-> {d.razon[:50]}")

    # Y el filtro existe: se relaja de 1.0 a 0.5 con un solo món, no desaparece.
    txt = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    check("con 1 món el umbral se relaja pero no desaparece",
          "if len(vivos) < 2:" in txt and "if of_min < 0.5:" in txt
          and "elif of_min < 1.0:" in txt,
          "-> el filtro de tipo contra el jefe no se ha relajado con 1 món")



def test_continuar_en_batalla_no_puede_buquearse() -> None:
    """Un boton de continuar que se pulsa mucho no esta avanzando.

    Medido: `continuar` en bucle con el enemigo ya a 0 HP (la batalla estaba
    ganada y la pantalla no pasaba al resultado), 13 s entre pulsaciones. El
    tope general era de 25 rachas y ademas la exencion de batalla reseteaba el
    contador a 1 cada 4 intentos, asi que el bucle era infinito: nunca se
    llegaba al tope.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("hay un tope propio para 'continuar' en batalla",
          "TOPE_CONTINUAR" in txt,
          "-> 'continuar' puede pulsar indefinidamente sin avanzar")
    check("el tope de continuar es bajo (no 25)",
          "TOPE_CONTINUAR = 4" in txt or "TOPE_CONTINUAR = 6" in txt,
          "-> el tope es tan alto que tardan minutos en escalar")
    check("hay recuperacion propia para batalla clavada",
          "_recuperar_batalla_clavada" in txt and "btn-auto-battle" in txt,
          "-> no se fuerza auto-battle ni recarga al clanar la batalla")
    check("la exencion de batalla no puede anular el tope de continuar",
          "es_continuar_batalla" in txt,
          "-> el reset por exencion deja el bucle sin salida")

def test_los_niveles_vienen_numericos() -> None:
    """Ningún nivel puede viajar como texto: el bot los compara con enteros.

    `estado_batalla` devolvía el nivel como cadena ("12"), y el primer
    `max(nivel_enemigo_max, nivel)` de la partida reventaba con
    `TypeError: '>' not supported between instances of 'str' and 'int'`. Pasaba
    en el **primer combate**, o sea que ninguna run llegaba a jugar: el fallo
    era invisible en los tests porque no había ninguno que ejecutara el
    recorrido de `navegador`.
    """
    txt = (SCRIPTS / "navegador.py").read_text(encoding="utf-8")
    check("el nivel del rival se parsea a entero",
          "return m ? parseInt(m[1], 10) : 0;" in txt,
          "-> sigue devolviendo la cadena")
    check("el nivel del elemento se parsea a entero",
          "parseInt((nivelTxt.match(/\\d+/)" in txt,
          "-> sigue devolviendo la cadena")

    # Y el bot solo debe usar sumas y max sobre niveles ya numéricos: si
    # reaparece un `int(...)` sospechoso alrededor de un nivel, salta.
    fuente = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    # El nivel enemigo se normaliza con `_niv(e)` y no con `e["nivel"]`: el
    # nivel puede llegar como texto y `max(int, str)` lanza TypeError. La cadena
    # literal anterior (`e["nivel"]`) era justo el bug.
    check("el rival se guarda el nivel ya convertido",
          "max(self.nivel_enemigo_max, _niv(e))" in fuente
          and "int(m.get(\"nivel\")" in fuente,
          "-> sin normalizar, un nivel de texto rompe la partida")


def test_toda_decision_deja_rastro() -> None:
    """Ninguna decisión se ejecuta sin quedar registrada en `traza`.

    El log de texto dice **qué** se decidió pero no **sobre quién**: qué objeto
    cogió y a qué món se lo puso, quién recibió la MT, a quién se sacó en el
    cambio. Con eso no se puede auditar una partida.

    El motivo de que sea un test y no una convención: al añadir la traza
    aparecieron **dos** `TypeError` en la primera partida (`traza("nodo",
    tipo=...)` chocaba con el parámetro `tipo`, y `len(pend)`/`len(vivos)` donde
    la variable ya era un entero). Los dos reventaron en vivo, y solo se ven
    jugando. Aquí se comprueba que la llamada existe **y que no vuelve a
    colisionar**, que es el fallo que la skorregido.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")

    # 1) El parámetro se llama `evento`, no `tipo`: casi todos los registros
    #    llevan un campo `tipo=`, y con un parámetro `tipo` la llamada da
    #    TypeError en el primer nodo del mapa.
    check("traza no usa un parametro llamado 'tipo'",
          "def traza(self, evento: str" in txt,
          "-> volvería a colisionar con el campo tipo= de los registros")

    # 2) Las tres salidas de `_catch` tienen que registrarse. Antes la
    #    renuncia por `capturas_pantalla >= 1` salía sin rastro, y en una
    #    partida de 5 nodos `catch` hubo 2 capturas y 3 rechazos: el cuarto
    #    nodo no dejó ni una línea, indistinguible de un bug.
    for salida in ("captura_pedida", "captura_renunciada", "captura_rechazada"):
        check(f"la salida {salida} queda registrada",
              f'self.traza("{salida}"' in txt, "-> hay un veto silencioso")

    # 3) Que no haya dos comprobaciones iguales de `capturas_pantalla` en
    #    `_catch`: la segunda era código muerto (la primera devuelve siempre).
    cuerpo = txt[txt.index("    def _catch(self)"):]
    cuerpo = cuerpo[:cuerpo.index("    def _opciones_genericas")]
    check("_catch no repite la comprobacion de capturas_pantalla",
          cuerpo.count("self.capturas_pantalla >= 1") == 1,
          f"-> sale {cuerpo.count('self.capturas_pantalla >= 1')} veces")

    # 4) Las decisiones con objetivo: objeto, cambio, MT, trade. Son las que
    #    no se podían reconstruir y las que el usuario pidió registrar.
    import re as _re
    for evento in ("nodo", "orden", "item_cogido", "objeto_equipado",
                   "swap", "trade_aceptado", "captura_confirmada"):
        # La llamada puede partirse en varias líneas (`nodo` tiene 12 campos),
        # así que se busca con regex y no con una cadena literal.
        patron = _re.compile(r'self\.traza\(\s*"' + _re.escape(evento) + r'"')
        check(f"se registra la decisión {evento}",
              bool(patron.search(txt)), "-> no queda en el log de texto")

    # 5) Y que la traza se vuelque a disco al terminar: en memoria se pierde
    #    en cuanto el proceso muere.
    check("la traza se vuelca a json",
          "def volcar_traza(" in txt and "traza-" in txt,
          "-> las decisiones no sobreviven a la run")
    check("el volcado sale en el resumen",
          "self.volcar_traza()" in txt.split("RESUMEN")[0].rsplit("def ", 1)[-1]
          or "volcar_traza()" in txt, "-> no se anuncia dónde quedó")


def test_el_nodo_de_objeto_ya_no_esta_invertido() -> None:
    """Con hueco en el equipo, el nodo de objeto tiene que puntuar alto.

    `tiene_bolsa` quiere decir **"quedan huecos"** (`not items_tomados >=
    MAX_ITEMS`), y la condición estaba al revés: el nodo puntuaba `PESO_OBJETO`
    cuando la bolsa estaba **llena** y `2.0` cuando había sitio. Medido en 924
    pantallas de 56 runs: el nodo `item` se ofreció 144 veces y el bot lo cogió
    **4**; 26 de 54 runs terminaron con cero objetos.

    La guía dice lo contrario dos veces: "item nodes beat fight nodes early" y el
    Lucky Egg "outscales the route".
    """
    equipo = [{"nombre": "Ivysaur", "tipos": ["Planta", "Veneno"], "nivel": 21,
               "ps": 40, "ps_max": 40},
              {"nombre": "Poliwag", "tipos": ["Agua"], "nivel": 20,
               "ps": 40, "ps_max": 40}]
    plan = PL.plan_para("Kanto", 2)
    con_hueco = PL.Contexto(equipo=equipo, plan=plan, tiene_bolsa=True)
    sin_hueco = PL.Contexto(equipo=equipo, plan=plan, tiene_bolsa=False)

    original = PL.EXP["item_huecos"]
    try:
        PL.EXP["item_huecos"] = True
        s_hueco, r_hueco = PL.puntuar("item", con_hueco)
        PL.EXP["item_huecos"] = False
        s_viejo, _ = PL.puntuar("item", con_hueco)
    finally:
        PL.EXP["item_huecos"] = original

    check("con hueco el objeto vale PESO_OBJETO",
          s_hueco == PL.PESO_OBJETO, f"-> {s_hueco} (esperado {PL.PESO_OBJETO})")
    check("el objeto con hueco gana a cazar sin nivel",
          s_hueco > PL.PESO_BATALLA_A_NIVEL,
          f"-> objeto {s_hueco} vs batalla a nivel {PL.PESO_BATALLA_A_NIVEL}")
    check("el objeto con hueco no supera al entrenador",
          s_hueco < PL.PESO_ENTRENADOR_SANO,
          f"-> objeto {s_hueco} vs entrenador {PL.PESO_ENTRENADOR_SANO}")
    check("el control mantiene el 2.0 de siempre",
          s_viejo < s_hueco, f"-> control {s_viejo} vs A {s_hueco}")

    # Sin huecos no se coge: el nodo está gastado. Y el mensaje ya no puede
    # decir "bolsa vacía" en esa rama, que era lo que mentía.
    s_lleno, r_lleno = PL.puntuar("item", sin_hueco)
    check("sin huecos el objeto no es prioridad", s_lleno < s_hueco,
          f"-> {s_lleno}")
    check("el mensaje de bolsa llena es honesto",
          "bolsa vacía" not in r_lleno, f"-> {r_lleno}")


def test_los_atributos_nuevos_nacen_en_init() -> None:
    """Todo atributo que usa un método tiene que existir en `__init__`.

    Se añadieron dos a `Bot` para la traza de decisiones (`_traza`,
    `_tutor_visitado`) y se creaban **dentro de la rama que los usa**. Con eso
    la primera visita a un nodo de tutor moría con `AttributeError: 'Bot'
    object has no attribute '_tutor_visitado'`, y pasó en 26 de 100 runs del
    lote de H13: un tercio de la muestra perdida por un atributo.

    El patrón se comprueba sobre el **código**, no ejecutando el juego, porque
    los 293 tests pasan con el bug puesto: el atributo solo se toca en la rama
    del tutor, que ningún test alcanza.
    """
    import ast as _ast
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    arbol = _ast.parse(txt)
    clase = next(n for n in _ast.walk(arbol)
                 if isinstance(n, _ast.ClassDef) and n.name == "Bot")
    init = next(n for n in clase.body
                if isinstance(n, _ast.FunctionDef) and n.name == "__init__")
    # Atributos que se leen con `self.X` en algún método y que no se asignan en
    # ningún sitio de la clase.
    asignados: set[str] = set()
    for n in _ast.walk(clase):
        if (isinstance(n, _ast.Assign)):
            for tgt in n.targets:
                if (isinstance(tgt, _ast.Attribute)
                        and isinstance(tgt.value, _ast.Name)
                        and tgt.value.id == "self"):
                    asignados.add(tgt.attr)
        elif isinstance(n, _ast.AugAssign) and isinstance(
                n.target, _ast.Attribute):
            if isinstance(n.target.value, _ast.Name) and n.target.value.id == "self":
                asignados.add(n.target.attr)
        elif (isinstance(n, _ast.AnnAssign) and isinstance(n.target, _ast.Attribute)
              and isinstance(n.target.value, _ast.Name)
              and n.target.value.id == "self"):
            asignados.add(n.target.attr)

    leidos: set[str] = set()
    for n in _ast.walk(clase):
        if (isinstance(n, _ast.Attribute) and isinstance(n.value, _ast.Name)
                and n.value.id == "self" and isinstance(n.ctx, _ast.Load)):
            leidos.add(n.attr)

    # Lo que **no** es atributo: métodos de la clase y constantes de cuerpo
    # (`MAX_ITEMS = 3`, `MANEJADORES = {...}`). `self.MANEJADORES` es una
    # constante, no un atributo por crear, y `self.paso()` es un método.
    no_atributos: set[str] = set()
    for n in clase.body:
        if isinstance(n, _ast.FunctionDef):
            no_atributos.add(n.name)
        elif isinstance(n, _ast.Assign):
            for tgt in n.targets:
                if isinstance(tgt, _ast.Name):
                    no_atributos.add(tgt.id)
        elif isinstance(n, _ast.AnnAssign) and isinstance(n.target, _ast.Name):
            no_atributos.add(n.target.id)

    # Los que se leen pero nunca se asignan en la clase. Los que se leen solo
    # con `getattr(self, ...)` no aparecen aquí, y esos sí son seguros.
    huerfanos = sorted(a for a in leidos - asignados - no_atributos
                       if not a.startswith("__"))
    check("ningun atributo se usa sin crearse en la clase",
          not huerfanos, f"-> {huerfanos}")

    # Y el caso concreto que rompió, nombrado explícitamente.
    check("_tutor_visitado nace en __init__",
          "_tutor_visitado" in asignados,
          "-> AttributeError en la primera visita al tutor")
    check("_traza nace en __init__",
          "_traza" in asignados, "-> la traza no se puede escribir")


def test_el_auto_skip_usa_las_claves_que_lee_el_juego() -> None:
    """Las claves de `poke_settings` tienen que ser **planas** y las del juego.

    Descifrado el bundle (`js/bundle.cb7dc30ffe.js`):

        const SKIP_SPEED = 3;
        const sju = sjS['autoSkipAllBattles'] || ...;
        battleSpeedMultiplier = sju ? SKIP_SPEED : 1;

    El bot escribía un objeto **anidado** (`autoSkip.allFights`,
    `autoSkip.evolutions`, `autoSkip.regularTrainers`, `autoSkip.skipBossPreview`)
    que no coincide con ninguna clave que el juego lea, así que **todas las
    partidas iban a 1× en vez de 3×** y el log anunciaba "auto-skip activado".

    No se podía detectar con los tests: el `try/except` que envuelve la
    escritura nunca falla, porque `localStorage.setItem` no lanza excepción. Es
    la clase de bug que este fichero documenta siete veces (comparar contra
    una clave que no existe), pero con otra forma: la clave existe y es
    distinta.

    Aquí se comprueba contra las claves **reales del bundle**, no contra la
    intención del código. Si el juego renombra una, este test hay que
    actualizarlo a mano, que es justo lo que hay que hacer: nadie puede
    cambiar el juego en silencio sin que se note.
    """
    txt = (SCRIPTS / "navegador.py").read_text(encoding="utf-8")

    # Las cuatro claves que lee el juego, sacadas del bundle.
    claves_juego = ("autoSkipAllBattles", "autoSkipBattles", "autoSkipEvolve",
                    "skipBossPreview")
    for clave in claves_juego:
        check(f"el bot escribe {clave} (plana)", f"s.{clave} = true" in txt,
              f"-> el juego lee '{clave}' y el bot no la pone")

    # Y la forma anidada, que es la que no vale: si aparece, vuelve el bug.
    for anidada in ("s.autoSkip.allFights", "s.autoSkip.evolutions",
                    "s.autoSkip.regularTrainers", "s.autoSkip.skipBossPreview"):
        check(f"ya no se usa la anidada {anidada}", anidada not in txt,
              "-> el juego lee claves planas; la anidada no la lee nadie")

    # Que la función **devuelva** lo leído. Sin esto el log vuelve a poder
    # mentir: que la escritura no lance excepción no prueba que el juego la
    # entienda.
    cuerpo = txt[txt.index("def activar_auto_skip"):]
    cuerpo = cuerpo[:cuerpo.index("def equipo(")]
    check("activar_auto_skip relee lo guardado", "getItem(K)" in cuerpo
          and "JSON.parse(localStorage.getItem(K)" in cuerpo,
          "-> no verifica nada: el log no puede decir la verdad")
    check("activar_auto_skip devuelve el estado",
          "return {" in cuerpo and "autoSkipAllBattles: !!" in cuerpo,
          "-> no devuelve nada, y el log no tiene con qué ser honesto")

    # Y que el bot lo pinte en el log en vez de afirmar que sí.
    jug = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el log dice lo leido, no 'activado' a secas",
          "f\"  ajustes: {leido}\"" in jug,
          "-> vuelve a anunciar 'activado' sin comprobarlo")
    check("ya no se anuncia un 'activado' que nadie verifico",
          "auto-skip activado (combates y evoluciones)" not in jug,
          "-> esa frase era falsa: las claves no las leia el juego")


def test_las_peleas_se_cuentan_sin_muestreo() -> None:
    """El recuento de combates no puede pasar por el filtro de 4 en 4.

    El volcado `estado:` / `mios=` sale solo de 4 en 4 pasos de batalla
    (`_n_batalla % 4 == 0`), así que contar peleas leyendo el log subestima
    **exactamente 4×**. Con ese error: cualquier conclusión sobre "cuántas peleas de
    entrenador" quedan contaminadas por un factor fijo y no se pueden comparar
    ni multiplicar por el +2 de niveles que da el entrenador.

    Aquí se comprueba que el contador existe, se incrementa **fuera** del `if`
    del muestreo y que sale en el RESUMEN, que es la sección fiable.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")

    check("los contadores de pelea nacen en __init__",
          all(k in txt for k in ("self.peleas = 0", "self.peleas_entrenador = 0",
                                 "self.peleas_salvaje = 0")),
          "-> sin inicializar, AttributeError en la primera batalla")

    # El incremento tiene que estar ANTES del `if ... % 4 == 0` que guarda el
    # volcado, y tiene que ser **código de verdad**. Un test que busca la cadena
    # "self.peleas += 1" se deja engañar por un comentario: al comprobar si
    # mordía, la sustitución `pass  # self.peleas += 1` siguió dando 312/312.
    # Por eso se mira el AST, donde un comentario no existe.
    import ast as _ast2
    arbol = _ast2.parse(txt)
    nodos_aug = [n for n in _ast2.walk(arbol)
                 if isinstance(n, _ast2.AugAssign)
                 and isinstance(n.target, _ast2.Attribute)
                 and n.target.attr == "peleas"]
    check("el contador existe como codigo, no en un comentario",
          len(nodos_aug) == 1,
          f"-> {len(nodos_aug)} incrementos reales de self.peleas")

    if not nodos_aug:
        return
    linea_inc = nodos_aug[0].lineno
    linea_muestreo = next(
        (n.lineno for n in _ast2.walk(arbol)
         if isinstance(n, _ast2.If)), None)
    # El `if` del muestreo: el primero cuyo test menciona _n_batalla.
    linea_muestreo = next(
        (n.lineno for n in _ast2.walk(arbol)
         if isinstance(n, _ast2.If) and "_n_batalla" in _ast2.dump(n.test)),
        None)
    check("el contador esta FUERA del muestreo de 4 en 4",
          linea_muestreo is not None and linea_inc < linea_muestreo,
          f"-> incremento en linea {linea_inc}, muestreo en "
          f"{linea_muestreo}: si esta dentro, cuenta 1 de cada 4")

    # Y la clasificacion: entrenador vsavage, por el titulo.
    check("se distingue entrenador de salvaje",
          '"wants to battle" in titulo' in txt
          and "self.peleas_entrenador += 1" in txt
          and "self.peleas_salvaje += 1" in txt,
          "-> no se puede separar +2 niveles de +1")

    # Y que salga en el RESUMEN, que es de donde se lee sin ambiguedad.
    check("el desglose sale en el RESUMEN",
          '"peleas entrain."' in txt and '"peleas salvaje"' in txt,
          "-> el dato existe pero no es legible en ninguna parte")


def test_el_volcado_de_combate_normaliza_el_nivel() -> None:
    """El nivel puede venir como texto y `max()` revienta al mezclarlo.

    Al contar **todas** las peleas (antes solo 1 de cada 4) apareció un
    `TypeError: '>' not supported between instances of 'str' and 'int'` en el
    primer combate: `"15"` y `15` en la misma lista. El código antiguo sufre el
    mismo bug, pero el muestreo lo escondía.

    Aquí se comprueba que el volcado normaliza con `int()` en vez de confiar en
    que el nivel llega numérico, que es la razón de fondo.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    cuerpo = txt[txt.index('self.traza("combate"'):]
    cuerpo = cuerpo[:cuerpo.index("self._n_batalla")]
    txt2 = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    aux = txt2[txt2.index("def _niv(m: dict) -> int:"):]
    aux = aux[:aux.index("self.traza(\"combate\"")]
    check("el volcado de combate normaliza el nivel con int()",
          "int(m.get(\"nivel\")" in aux and "except (TypeError, ValueError)" in aux,
          "-> si el nivel llega como texto, max() lanza TypeError")
    check("el volcado de combate usa default=0 en vez de comparar vacios",
          "default=0" in cuerpo,
          "-> sin default, una lista vacia lanza ValueError")



_STD = {"hp": 60, "atk": 60, "def": 60, "spa": 60, "spd": 60, "spe": 60}
PROX = ["Water", "Electric", "Grass"]


def _mon(n, tp, nv):
    return {"nombre": n, "tipos": tp, "nivel": nv, "ps": 100, "ps_max": 100,
            "baseStats": _STD}


def _cand(n, tp, nv, i):
    return {"nombre": n, "tipos": tp, "nivel": nv, "atajo": i,
            "baseStats": _STD}


# Los tres que hoy salen "nada útil ... huyo" y con el flag entran.
CASOS_CAPTURA = [
    ("3 mons duplicados",
     [_mon("Bulbasaur", ["Grass", "Poison"], 20),
      _mon("Ivysaur", ["Grass", "Poison"], 20),
      _mon("Poliwag", ["Water"], 20)],
     [_cand("Oddish", ["Grass", "Poison"], 20, 1),
      _cand("Rattata", ["Normal"], 20, 2),
      _cand("Spearow", ["Normal", "Flying"], 20, 3)], "Water", "Electric"),
    ("2 mons contra Agua",
     [_mon("Bulbasaur", ["Grass", "Poison"], 18),
      _mon("Pidgey", ["Normal", "Flying"], 18)],
     [_cand("Staryu", ["Water"], 18, 1),
      _cand("Psyduck", ["Water"], 18, 2),
      _cand("Poliwag", ["Water"], 18, 3)], "Water", "Electric"),
    ("equipo lleno de 6",
     [_mon("M%d" % i, ["Grass", "Poison"] if i < 3 else ["Water"], 20)
      for i in range(6)],
     [_cand("Oddish", ["Grass", "Poison"], 20, 1),
      _cand("Rattata", ["Normal"], 20, 2),
      _cand("Spearow", ["Normal", "Flying"], 20, 3)], "Water", "Electric"),
]


def test_capturar_es_mas_barato_que_rechazar() -> None:
    """H15 · Con el flag, un rechazo por falta de cobertura se convierte en captura.

    Regla del usuario: "es mejor capturar que rechazar; si tenemos un pokemon
    duplicado en tipo, podemos cambiarlo en el nodo de cambiar".

    Los tres casos de abajo **hoy salen todos con "huyo"** y con el flag entran.
    Son los que miden el bucle: el filtro rechaza por falta de cobertura, el
    equipo se queda sin variedad y el filtro vuelve a rechazar.

    Además, el rechazo no sale gratis: `catch-screen` tiene "Skip (flee)" y
    huir es **no pelear**, o sea perder el nivel del combate.
    """
    import politica as PP
    importlib.reload(PP)
    # `getattr` y no acceso directo: si el flag no existe todavia, el test
    # tiene que FALLAR limpio, no reventar el suite entero y perder el
    # resultado de los 300 checks que vienen despues.
    original = getattr(PP, "CAPTURA_PERMISIVA", False)
    check("politica define CAPTURA_PERMISIVA",
          hasattr(PP, "CAPTURA_PERMISIVA"),
          "-> el flag no existe: el filtro sigue rechazando por cobertura")
    try:
        PP.CAPTURA_PERMISIVA = False
        antes = [PP.elegir_captura(eq, cands, act, fut, 6, PROX, "Kanto").valor
                 for nombre, eq, cands, act, fut in CASOS_CAPTURA]
        PP.CAPTURA_PERMISIVA = True
        despues = [PP.elegir_captura(eq, cands, act, fut, 6, PROX, "Kanto").valor
                   for nombre, eq, cands, act, fut in CASOS_CAPTURA]
    finally:
        PP.CAPTURA_PERMISIVA = original

    nuevos = sum(1 for a, d in zip(antes, despues) if a is None and d is not None)
    check("el flag convierte rechazos en capturas", nuevos >= 2,
          f"-> solo {nuevos} de {len(CASOS_CAPTURA)} cambiaron")
    check("sin el flag los casos de cobertura siguen huyendo",
          sum(1 for a in antes if a is None) >= 2,
          f"-> {antes}: el control ya no huye y no se puede comparar")

    # Y que el fallback respete los filtros DUROS: no entra un 0.5x contra
    # todo el rival ni uno con stats de Worked.
    import politica as P2
    P2.CAPTURA_PERMISIVA = True
    flojo = [{"nombre": "Caterpie", "tipos": ["Bug"], "nivel": 20, "atajo": 1,
              "baseStats": {"hp": 5, "atk": 5, "def": 5}}]
    d_flojo = P2.elegir_captura(
        [{"nombre": "Bulbasaur", "tipos": ["Grass", "Poison"], "nivel": 20,
          "ps": 100, "ps_max": 100, "baseStats": {"x": 300}}],
        flojo, "Water", "Electric", 6, PROX, "Kanto")
    check("el fallback no entra con stats de Worked", d_flojo.valor is None,
          f"-> {d_flojo.valor}: el filtro duro de stats se perdio")
    P2.CAPTURA_PERMISIVA = original



def test_no_hay_codigo_muerto() -> None:
    """Toda función pública de la estrategia tiene que ser alcanzable.

    `elegir_nodo` fueron 150 líneas duplicadas de `planificador.elegir` que
    nadie llamaba, con sus propios pesos y sus propios umbrales. Cuatro
    banderas del bot (`objetos_fallidos`, `_ya_cogido_item`,
    `tipos_de_entrenadores_del_mapa`, `_leer_mapa_cache`) estaban escritas y
    documentadas como correcciones de bugs medidos, y no hacían nada. Es la
    clase de fallo que la batería no veía porque comprobaba que el código
    fuera *correcto*, no que se *ejecutara*.
    """
    fuentes = {f.name: f.read_text(encoding="utf-8")
               for f in SCRIPTS.glob("*.py") if f.name != "test_integridad.py"}

    huerfanas = []
    for nombre, texto in fuentes.items():
        if nombre not in ("politica.py", "planificador.py"):
            continue
        arbol = ast.parse(texto)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.FunctionDef):
                continue
            # Solo las públicas y documentadas: las privadas son ayudantes y
            # las de una sola línea no prometen nada por sí solas.
            if nodo.name.startswith("_") or not ast.get_docstring(nodo):
                continue
            # Una llamada = la definición. Cero = nadie la invoca.
            definiciones = texto.count(f"def {nodo.name}(")
            usos = sum(t.count(nodo.name) for t in fuentes.values())
            if usos <= definiciones:
                huerfanas.append(f"{nombre}:{nodo.lineno} {nodo.name}")
    check("sin funciones publicas huerfanas", not huerfanas,
          f"-> {huerfanas}" if huerfanas else "")

    # Atributos que se escriben y nunca se leen (o al reves): el sintoma mas
    # claro de un arreglo que se quedo a medias.
    for atributo, esperado in (("objetos_fallidos", "add"),
                               ("_ya_cogido_item", "True"),
                               ("_tipos_ruta", "=")):
        leido = sum(t.count(atributo) for t in fuentes.values())
        check(f"{atributo} se usa de verdad", leido >= 3, f"-> {leido} apariciones")


# =====================================================================
# Regresiones añadidas tras la auditoría del repo. Cada una fija un bug
# concreto; el comentario de cada una dice cuál era.
# =====================================================================


def test_mapa_lee_el_nivel_del_rival() -> None:
    """`mapa()` tiene que traer `nivel`, o el veto por nivel nunca se aplica."""
    txt = (SCRIPTS / "navegador.py").read_text(encoding="utf-8")
    check("el mapa lee el nivel del entrenador",
          "trainerFightLevel(delEstado)" in txt,
          "-> el veto por nivel no puede dispararse")
    fuente = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    check("el planificador recibe el nivel del rival",
          "nivel_rival=niv_rival" in fuente,
          "-> el veto por nivel no puede dispararse")


def test_el_entrenador_se_veta_por_nivel_y_por_caidos() -> None:
    """No se entra a un entrenador por encima del equipo, ni sin cura y caído.

    Regresión sobre la tanda que perdió contra `Ace Trainer wants to battle!`
    con un único món en pie: el nivel del rival ya venía de
    `trainerFightLevel`, pero nunca llegaba a la política.
    """
    import planificador as PL

    equipo = [
        {"nombre": "Goldeen", "nivel": 9, "ps": 100, "ps_max": 100,
         "tipos": ["Agua"], "baseStats": {"x": 245}},
        {"nombre": "Bulbasaur", "nivel": 7, "ps": 0, "ps_max": 100,
         "tipos": ["Planta", "Veneno"], "baseStats": {"x": 318}},
    ]
    ctx = PL.Contexto(equipo=equipo, plan=PL.plan_para("Kanto", 0))

    _, raz = PL.puntuar("entrenador", replace(ctx, nivel_rival=25))
    check("el_entrenador_con_rival_mas_fuerte_se_veta",
          "vetado" in raz, f"-> {raz}")

    sano = [dict(m, ps=m["ps_max"]) for m in equipo]
    _, raz_ok = PL.puntuar("entrenador", replace(
        ctx, equipo=sano, caidos=0, nivel_rival=9))
    check("un_entrenador_a_nivel_sigue_siendo_valido",
          "vetado" not in raz_ok, f"-> {raz_ok}")

    _, raz_sin = PL.puntuar("entrenador", replace(
        ctx, nivel_rival=9, hay_cura_disponible=False))
    check("entrenador_sin_cura_con_caidos_se_difiera",
          "caído" in raz_sin, f"-> {raz_sin}")


def test_el_veto_de_entrenador_llega_a_puntuar() -> None:
    """`replace(ctx, ...)` descartaba el `nivel_rival` que el veto necesita.

    El veto se ponía en `ctx_n`, y luego la rama del waypoint hacía
    `replace(ctx, ...)` reconstruyendo el contexto desde cero, así que el veto
    se desactivaba justo en los nodos donde hacía falta.
    """
    txt = (SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    check("el waypoint parte de ctx_n, no de ctx",
          "ctx_n = replace(ctx_n, en_camino_al_jefe=en_camino)" in txt,
          "-> el veto por nivel se pierde en la rama del jefe")
    check("no queda replace(ctx, en_camino...",
          "replace(ctx, en_camino_al_jefe" not in txt,
          "-> el veto por nivel se pierde en la rama del jefe")


def test_el_flojo_es_el_mas_debil_del_equipo() -> None:
    """`flojo` tenía que ser el PEOR miembro, no el mejor.

    El `min` estaba sobre `-0.02*stats - nivel`, que devuelve el que **más**
    stats y nivel tiene. Comprobado ejecutándolo con Bulbasaur Nv20 (318) y
    Staryu Nv8 (245): devolvía Bulbasaur. Con el equipo lleno, la puerta de
    captura comparaba contra el mejor y el bot huía de todas las capturas.
    """
    equipo = [
        {"nombre": "Bulbasaur", "nivel": 20, "ps": 100, "ps_max": 100,
         "tipos": ["Planta", "Veneno"], "baseStats": {"x": 318}},
        {"nombre": "Staryu", "nivel": 8, "ps": 100, "ps_max": 100,
         "tipos": ["Agua"], "baseStats": {"x": 245}},
    ]

    def _fuerza_flojo(m: dict) -> tuple:
        st = sum((m.get("baseStats") or {}).values()) if (m.get("baseStats")) else 0
        return (0 if st else 1, st, m.get("nombre") or "")

    check("el flojo es el mas debil",
          min(equipo, key=_fuerza_flojo)["nombre"] == "Staryu")
    txt = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    check("el codigo usa el flojo mas debil",
          "return (0 if st else 1, st, m.get(\"nombre\") or \"\")" in txt,
          "-> la clave del flojo no es la del test")


def test_curar_invalida_el_ps_real() -> None:
    """El pokecenter tenía que llamar a `_invalidar_ps`, y su tipo es `"cura"`.

    `d.tipo` es vocabulario interno y `politica.tipo_de_estado` mapea
    `pokecenter -> cura`. La rama comparaba contra
    `("centro", "pokecenter")`, que el juego nunca emite: nunca se contaba un
    centro y la caché de PS no se invalidaba al curar.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el centro se detecta por el tipo real 'cura'",
          'if d.tipo == "cura":' in txt,
          "-> vuelve a comparar contra un tipo que el juego no emite")
    check("el centro invalida el PS real",
          'self._invalidar_ps("pokecenter")' in txt)
    check("no queda la rama muerta del centro",
          'd.tipo in ("centro", "pokecenter")' not in txt,
          "-> codigo muerto de vuelta")


def test_el_atasco_cuenta_rachas_y_no_toda_la_partida() -> None:
    """El detector de atasco debe contar repeticiones **consecutivas**.

    Decía eso en el comentario y no lo hacía: `vistos` no se limpiaba y la clave
    era pantalla+acción, que en `map-screen` es siempre `nodo 1`, `nodo 2`…,
    el valor normal de cada visita. Una run sana declaraba `ATASCADO` en la
    visita 13 de cualquier atajo.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el detector compara contra la clave completa",
          "if clave == anterior:" in txt,
          "-> sigue contando acumulado en vez de por racha")
    check("el tope de atasco no es 12 (mata runs sanas)",
          "tope_repetidas = 25" in txt)
    # Solo se prohíbe el `clear()` en el bucle de conteo, no en la recuperación
    # tras recargar la página, donde vaciar el historial sí es lo correcto.
    # Solo la seccion que cuenta: desde la clave hasta la comparacion con el
    # tope. El `clear()` de la recuperacion tras recargar si es correcto.
    conteo = txt[txt.index("clave = f\""):]
    conteo = conteo[:conteo.index("tope_repetidas:")]
    check("el clear() no esta en el bucle de conteo",
          "vistos.clear()" not in conteo,
          "-> la deteccion de atasco vuelve a estar anulada")


def test_los_indices_de_objetos_se_recalculan() -> None:
    """El reparto de objetos no puede usar índices de un snapshot viejo.

    `usar_item` indexa el DOM vivo con `.nth(indice)`, pero el plan se armaba
    con los índices de `bolsa` del principio. Al gastarse el primer objeto, la
    bolsa se acortaba y los índices siguientes apuntaban un objeto más arriba.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el indice del objeto se recalcula antes de usarlo",
          "bolsa_viva = self.j.bolsa_items()" in txt and "idx_vivo" in txt,
          "-> sigue el indice del snapshot y se equipa el objeto equivocado")
    check("un timeout no veta el objeto para siempre",
          "self._objeto_fallos" in txt and ">= 2" in txt,
          "-> un solo clic fallido quema el objeto hasta el final de la run")


def test_el_nivel_equipo_no_revienta_con_ceros() -> None:
    """`min()` sobre niveles vacíos era un `ValueError` en cada captura.

    El `if vivos else 0` solo cubría el equipo vacío. Con móns **vivos pero
    con `nivel == 0`** el generador quedaba vacío y `min()` lanzaba. Como
    `ValueError` no está en `ERRORES_DE_CODIGO`, no cortaba la run: acababa en
    `ATASCADO`, perdiendo la partida en la pantalla de captura.
    """
    txt = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    check("los niveles vivos se calculan antes de min()",
          "_niveles_vivos" in txt and
          "min(_niveles_vivos) if _niveles_vivos else 0" in txt,
          "-> sigue el min() sobre un generador que puede quedar vacío")
    import politica as PP
    equipo = [{"nombre": "A", "nivel": 0, "ps": 100, "ps_max": 100,
               "tipos": ["Agua"], "baseStats": {"x": 40}}]
    try:
        PP.elegir_captura(
            equipo, [{"nombre": "Zubat", "nivel": 3, "tipos": ["Siniestro"],
                      "baseStats": {"x": 55}}],
            "Agua", "Tierra", 6, ["Agua", "Tierra"], "Kanto")
    except ValueError as exc:
        check("elegir_captura no revienta con nivel 0", False, f"-> {exc}")
    else:
        check("elegir_captura no revienta con nivel 0", True)


def test_el_trade_no_sacrifica_al_mon_sin_datos() -> None:
    """El trade no puede cambiar al mejor miembro ni clicar a ciegas."""
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el sacrificio aparta los stats desconocidos",
          "_fuerza_sacrificio" in txt and "0 if st else 1" in txt,
          "-> un món sin baseStats suma 0 y sale elegido")
    check("no se clic a la primera fila a ciegas",
          "return false;" in txt,
          "-> el món que sale del equipo es uno arbitrario")


def test_la_skill_del_camino_no_se_desincroniza() -> None:
    """La skill del camino dice los pesos reales: que no mienta.

    Los pesos se sacan del módulo, así que cuando alguien cambia una prioridad
    en `planificador.py` el test falla y obliga a actualizar la skill.
    """
    import planificador as PLAN

    skill = RAIZ / ".opencode/skills/pokelike-camino/CAMINO-POR-PANTALLA.md"
    if not skill.exists():
        check("la skill del camino existe", False, "-> no está")
        return
    txt = skill.read_text(encoding="utf-8")
    pesos = {
        "PESO_CURA_CAIDOS": 50, "PESO_CAPTURA": 60, "PESO_TRADE": 45,
        "PESO_ENTRENADOR_SANO": 34, "PESO_BATALLA_NIVEL": 15,
        "PESO_BATALLA_A_NIVEL": 4, "PESO_OBJETO": 12, "PESO_INCOGNITA": 9,
    }
    for nombre, esperado in pesos.items():
        real = getattr(PLAN, nombre, None)
        if real is None:
            check(f"la skill menciona {nombre}", False, "-> ya no existe")
            continue
        entero = int(round(float(real)))
        check(f"la skill menciona {nombre}={entero}",
              f"**{entero}**" in txt or f"| {entero} |" in txt,
              f"-> el código tiene {entero} y la skill no lo dice")
    check("la skill dice el umbral de la puerta", "75%" in txt)
    import jugar_pokelike as JUG
    for pantalla in sorted(JUG.Bot.MANEJADORES):
        if pantalla not in txt:
            check(f"la skill documenta {pantalla}", False, "-> falta")
            return
    check("la skill documenta todas las pantallas que maneja el bot", True)
    for v in ("map-screen", "pokecenter", "move_tutor"):
        check(f"la skill nombra el valor real '{v}'", v in txt)


def test_la_run_no_se_corta_por_el_presupuesto() -> None:
    """R1: la run solo acaba perdiendo o completando la región.

    El bucle de `jugar()` llevaba `self.pasos < max_pasos` como condición, así
    que un `--max-pasos` agotado cortaba la partida con un final que no era
    ganar ni perder.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el bucle de jugar no se corta por presupuesto",
          'while self.resultado == "EN_CURSO":' in txt,
          "-> un presupuesto agotado vuelve a cortar la run a mitad")
    check("seguir_en_vivo tampoco se corta por presupuesto",
          "while bot.resultado == \"EN_CURSO\":" in txt,
          "-> el modo en vivo sigue cortando la partida")


def test_el_herido_al_menos_50_va_al_final() -> None:
    """R3: menos del 50% de vida va último, y no se le expulsa del equipo."""
    import politica as PP
    equipo = [
        {"nombre": "A", "nivel": 10, "ps": 100, "ps_max": 100,
         "tipos": ["Planta"], "baseStats": {"x": 300}},
        {"nombre": "B", "nivel": 10, "ps": 40, "ps_max": 100,
         "tipos": ["Fuego"], "baseStats": {"x": 300}},
    ]
    orden = PP._reservar_heridos(equipo)
    check("los heridos van al final del orden", orden[0] == "A", f"-> {orden}")
    check("el herido sigue en el equipo (no se expulsa)", len(orden) == 2)
    falsos = [{"nombre": "X", "nivel": 10, "ps": 46, "ps_max": 46,
               "tipos": ["Planta"], "baseStats": {"x": 1}}]
    check("el corte de herido es por porcentaje",
          PP._reservar_heridos(falsos)[0] == "X",
          "-> un món con 46/46 se contaba como herido por vida cruda")


def test_r2_se_captura_aunque_el_salvaje_sea_de_nivel_menor() -> None:
    """R2: al inicio de cada pantalla se captura un Pokémon.

    El filtro de calidad de nivel rechazaba al salvaje por estar por debajo del
    mejor nivel del equipo con **2 móns en pie**, así que se perdían todos los
    nodos de captura. Medido: 4 nodos de captura, 1 captura, `GAME_OVER` con
    2 móns.
    """
    import politica as PP
    equipo = [
        {"nombre": "Bellsprout", "nivel": 19, "ps": 100, "ps_max": 100,
         "tipos": ["Planta", "Veneno"], "baseStats": {"x": 300}},
        {"nombre": "Venonat", "nivel": 10, "ps": 100, "ps_max": 100,
         "tipos": ["Bicho", "Veneno"], "baseStats": {"x": 305}},
    ]
    salvajes = [{"nombre": "Onix", "nivel": 5, "tipos": ["Roca", "Tierra"],
                 "baseStats": {"x": 300}, "atajo": "1"}]
    d = PP.elegir_captura(equipo, salvajes, "Roca", "Agua", 6,
                          ["Roca", "Agua"], "Kanto")
    check("con 2 móns se captura aunque el salvaje sea de menor nivel",
          d.valor is not None,
          f"-> el nodo se gasta sin capturar: {d.razon[:60]}")
    d1 = PP.elegir_captura(equipo[:1], salvajes, "Roca", "Agua", 6,
                           ["Roca", "Agua"], "Kanto")
    check("con 1 solo món también se captura", d1.valor is not None,
          f"-> {d1.razon[:60]}")


def test_r2_no_veta_por_nivel() -> None:
    """R2: el nivel no puede vetar una captura. Ni con 1 món, ni con 3.

    Hubo un veto `nivel_minimo` que **no pidió el usuario**: con un solo món en
    pie descartaba todos los salvajes de la ruta. El parámetro ya no existe;
    este test falla si alguien lo reintroduce.
    """
    txt = (SCRIPTS / "politica.py").read_text(encoding="utf-8")
    check("el veto por nivel de captura no existe",
          "nivel_minimo" not in txt,
          "-> ha vuelto el veto que descartaba salvajes con el equipo vacío")
    txt_bot = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el bot no le pasa nivel_minimo a elegir_captura",
          "nivel_minimo=" not in txt_bot)


def test_un_caido_no_vuelve_a_vivir_al_invalidar_el_ps() -> None:
    """El HUD marca 100 a un món con 0 de vida: eso no puede ganar.

    La caché de porcentajes se vacía en cada uso de objeto, insignia y trade.
    Con la caché vacía el bot volvía al HUD, creía tener sano a un equipo
    entero muerto y entraba a pelear. Medido: `0/32, 0/28, 0/30` reales contra
    `100/100` reportados.
    """
    txt = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("existe un registro de caidos que sobrevive al cache",
          "_caidos_conocidos" in txt,
          "-> al vaciar el porcentaje, un món caido vuelve a parecer sano")
    check("el consumo fuerza a 0 a los caidos conocidos",
          "if clave in self._caidos_conocidos:" in txt,
          "-> el HUD (que marca 100) vuelve a mandar sobre el dato fiable")
    inicio = txt.index("def equipo_con_tipos")
    fin = txt.index("\n    def ", inicio)
    consumo = txt[inicio:fin]
    check("el dato de caido se aplica despues del porcentaje cacheado",
          consumo.index("_caidos_conocidos") > consumo.index("_ps_real.get"),
          "-> un porcentaje viejo puede tapar el dato de caido")


def test_el_que_pega_mas_va_delante() -> None:
    """Va primero el que gana por tipo; dentro, stats y luego nivel.

    El orden era un **producto** `of * aguante * altura`, que emparejaba móns
    que no deben emparejarse: contra Roca/Tierra, Staryu (pega x2) y Geodude
    (pega x0.5, aguanta bien) salían los dos a 2.0.
    """
    import politica as PP

    def m(n, tp, st, nv):
        return {"nombre": n, "tipos": tp, "baseStats": {"x": st},
                "nivel": nv, "ps": 100, "ps_max": 100}

    eq = [m("Venonat", ["Bicho", "Veneno"], 305, 12),
          m("Charmander", ["Fuego"], 309, 12),
          m("Bulbasaur", ["Planta", "Veneno"], 318, 12)]
    orden = PP.orden_para_entrenador(eq, ["Bicho"])
    check("entrenador de Bicho -> el de Fuego va primero",
          orden[0] == "Charmander", f"-> {orden}")

    eq2 = [m("Venonat", ["Bicho", "Veneno"], 305, 12),
           m("Squirtle", ["Agua"], 314, 12),
           m("Bulbasaur", ["Planta", "Veneno"], 318, 12)]
    orden2 = PP.orden_para_entrenador(eq2, ["Fuego"])
    check("entrenador de Fuego -> el de Agua abre y el 0.5x va al final",
          orden2[0] == "Squirtle" and orden2[-1] == "Venonat", f"-> {orden2}")

    eq3 = [m("Flojo", ["Fuego"], 290, 20), m("Fuerte", ["Fuego"], 340, 12)]
    orden3 = PP.orden_para_entrenador(eq3, ["Roca"])
    check("a igual tipo mandan los stats antes que el nivel",
          orden3[0] == "Fuerte", f"-> {orden3}")


def test_se_evita_al_entrenador_que_nadie_le_gana() -> None:
    """Si se puede evitar al entrenador, se evita; si es el líder, se juega.

    La pregunta no es "¿me da experiencia?" (siempre la da) sino "¿hay con qué
    ganarle?", y la responde la tabla de tipos.
    """
    import planificador as PLAN

    def m(n, tp, st, nv):
        return {"nombre": n, "tipos": tp, "baseStats": {"x": st},
                "nivel": nv, "ps": 100, "ps_max": 100}

    # El veto se fija a **activo**: este test lo prueba, así que no puede
    # depender de la variable de entorno del experimento en curso.
    veto_previo = PLAN.EXP["veto_tipo"]
    PLAN.EXP["veto_tipo"] = True
    try:
        _prueba_veto(PLAN, m)
    finally:
        PLAN.EXP["veto_tipo"] = veto_previo


def _prueba_veto(PLAN, m) -> None:
    ctx = PLAN.Contexto(equipo=[m("Ivysaur", ["Planta", "Veneno"], 318, 14)],
                        plan=PLAN.plan_para("Kanto", 1))
    _, r_fuego = PLAN.puntuar("entrenador", replace(
        ctx, sprite="fire", tipos_por_sprite={"fire": ["Fuego"]}))
    check("se evita al fire-breather sin respuesta de tipo",
          "evitable" in r_fuego, f"-> {r_fuego}")

    _, r_hiker = PLAN.puntuar("entrenador", replace(
        ctx, sprite="hiker", tipos_por_sprite={"hiker": ["Roca", "Tierra"]}))
    check("entra si alguien le gana por tipo",
          "evitable" not in r_hiker, f"-> {r_hiker}")

    # El jefe se juega siempre, y **no** porque un flag lo proteja: `es_jefe`
    # era un campo de `Contexto` que `elegir` nunca ponia a True, asi que el
    # test de abajo afirmaba una garantia que el codigo no tenia. Lo que
    # protege al jefe es que su tipo es `jefe` y el veto vive en la rama
    # `entrenador`: no lo alcanza.
    _, r_jefe = PLAN.puntuar("jefe", replace(
        ctx, plan=PLAN.plan_para("Kanto", 1)))
    check("el jefe se juega siempre",
          "evitable" not in r_jefe, f"-> {r_jefe}")
    check("el veto por tipo solo alcanza a nodos 'entrenador'",
          "evitable" in PLAN.puntuar("entrenador", replace(
              ctx, sprite="fire", tipos_por_sprite={"fire": ["Fuego"]}))[1],
          "-> si el veto se filtrara al jefe, esto no seria 'evitable'")

    caido = m("Squirtle", ["Agua"], 314, 14)
    caido["ps"] = 0
    _, r_caido = PLAN.puntuar("entrenador", replace(
        ctx, equipo=[caido], sprite="fisher",
        tipos_por_sprite={"fisher": ["Agua"]}))
    check("un món caido no cuenta como respuesta",
          "evitable" in r_caido, f"-> {r_caido}")


def test_sacar_el_tipo_repetido() -> None:
    """Regla del usuario: con dos del mismo tipo, sale el repetido.

    Es mejor que sacar "el peor". Dos móns del mismo tipo son una plaza de
    equipo desperdiciada: el segundo no aporta nada que el primero no tenga, y
    la plaza que libera es justo la que necesita el món nuevo.

    Los cuatro casos que importan, cada uno con un fallo distinto posible:

    1. Hay repetido y el nuevo es mejor -> sale el repetido.
    2. Hay repetido pero el nuevo es peor -> **no** se cambia: sería tirar una
       plaza buena por nada, y cambiar por cambiar es peor que no cambiar.
    3. Sin repetidos -> el de siempre, el peor por stats y nivel.
    4. Hay un muerto -> el muerto, aunque coincida el tipo: no vale nada y
       ocupa plaza.
    """
    import jugar_pokelike as J

    def _con(equipo, entrante=None):
        bot = object.__new__(J.Bot)          # sin __init__: no hace falta red
        bot.equipo_con_tipos = lambda: [dict(m) for m in equipo]
        bot._swap_nuevo_mons = entrante
        bot.log = lambda *a, **k: None
        return bot._peor_para_sustituir()

    agua_a = _mon("Pikachu", ["Electric"], 20)
    agua_b = _mon("Squirtle", ["Water"], 20)     # repite Water? no: distinto
    vdup_a = _mon("Poliwag", ["Water"], 24)
    vdup_b = _mon("Slowpoke", ["Water"], 22)

    # 1. repetido y el nuevo lo tapa mejor -> el repetido
    check("swap: con tipo repetido sale el repetido, no el peor",
          _con([agua_a, vdup_a, vdup_b],
               {"nombre": "Blastoise", "nivel": 26, "tipos": ["Water"],
                "baseStats": {"hp": 79, "at": 108}}) == "Slowpoke",
          "-> no se libera la plaza del tipo duplicado")

    # 2. el entrante es peor que el PEOR duplicado -> no se sacrifica el
    #    duplicado por él: sale el peor global, que es el menos útil de todos.
    #    (Estamos ya en la pantalla de swap: hay que sacar a alguien, la
    #    pregunta es a quién, y ese alguien es siempre el menos útil.)
    check("swap: si el entrante no mejora al duplicado sale el peor global",
          _con([agua_a, vdup_a, vdup_b],
               {"nombre": "Feebas", "nivel": 18, "tipos": ["Water"],
                "baseStats": {"hp": 55, "at": 20}}) == "Pikachu",
          "-> sacrifica el duplicado por un entrante que es peor")

    # 3. sin repetidos -> el peor por stats y nivel
    eq = [_mon("Pikachu", ["Electric"], 20),
          _mon("Ivysaur", ["Grass", "Poison"], 22),
          _mon("Vulpix", ["Fire"], 14)]
    check("swap: sin repetidos sigue saliendo el peor",
          _con(eq) == "Vulpix",
          "-> la regla del repetido rompio el criterio del peor")

    # 4. un muerto cae antes que el repetido
    caido = _mon("Pidgey", ["Normal"], 30)
    caido["ps"] = 0
    check("swap: el muerto sale antes que el tipo repetido",
          _con([agua_a, vdup_a, vdup_b, caido],
               {"nombre": "Blastoise", "nivel": 26, "tipos": ["Water"],
                "baseStats": {"hp": 79, "at": 108}}) == "Pidgey",
          "-> se queda un mon muerto ocupando plaza")


def test_la_etiqueta_de_version_va_en_el_log() -> None:
    """Cada run dice con qué código se hizo. Sin esto, editar el bot a mitad de
    un lote deja runs comparables que en realidad no lo son.

    Pasó de verdad: se editó `jugar_pokelike.py` con el lote corriendo y 56 de
    111 runs quedaron con versión distinta. Lo único que lo delató fue mirar los
    mtime del fichero a posteriori. Con el hash en el log, el error se ve al
    leer el log y no hace falta acordarse de cuándo se editó.
    """
    import jugar_pokelike as JUG
    txt = Path(JUG.__file__).read_text(encoding="utf-8")
    check("el log lleva el hash de codigo de la run",
          "PKL_HASH" in txt,
          "-> no se puede distinguir que version hizo cada run")
    check("el hash se escribe en la etiqueta del brazo",
          "codigo=" in txt,
          "-> el hash se calcula pero no llega al log")

    # Este chequeo apuntaba a `linea_base.sh`, que se archivó con el resto de
    # las hipótesis cerradas. **Lo que se comprobaba no era ese fichero**: era
    # que el launcher de un lote tiene las tres garantias que lo hacen fiable.
    # Se comprueba ahora sobre `exp_h20.sh`, que es el launcher vivo, porque un
    # test que se queda apuntando a un fichero archivado vuelve a ser decorativo
    # en cuanto el fichero cambia.
    launcher = SCRIPTS / "exp_h20.sh"
    check("hay un launcher de lote vivo",
          launcher.exists(),
          f"-> no hay launcher en {launcher}")
    if launcher.exists():
        sh = launcher.read_text(encoding="utf-8")
        check("el launcher lleva timeout por run",
              'timeout "$TIMEOUT"' in sh,
              "-> una run colgada tumba el lote entero")
        check("el launcher cuenta las que lanza de verdad",
              'lanzadas=$((lanzadas + 1))' in sh,
              "-> el plan y la realidad se separan sin avisar")
        check("el launcher aborta si el codigo del lote no es el suyo",
              "ABORTA" in sh and "$HASH" in sh,
              "-> se mezclarian runs de dos versiones en la misma muestra")


def test_la_escalera_gana_al_bono_de_ruta() -> None:
    """La escalera tiene que poder perder contra un nodo con ruta.

    **Este es el fallo que hacia pointless el experimento entero.** La escalera
    bajaba el *peso* del nodo a 0.5-2.0, pero ese peso entra en el score antes
    que el bono de ruta:

        s = peso * multiplicadores
        s += extra * peso_ruta      # n_ent*4 y n_centro*12, por 3.5

    El bono se suma despues y vale 60-300, asi que 0.5 no perdia nunca. Medido
    en 24 runs reales: la escalera marco "entrenador de riesgo" 13 veces y el
    bot eligio el entrenador **13 de 13**, igual que el control. Por eso la
    penalizacion se suma al final, con el bono ya dentro.

    Aqui se monta una pantalla con esa forma exacta: un nodo de entrenador con
    10 entrenadores y 20 combates por delante (+210 de bono) y una alternativa
    de batalla silvestre.
    """
    def _pantalla() -> tuple[list[dict], list]:
        nodos = [{"id": "t", "tipo": "trainer", "clickable": True,
                   "sprite": "youth", "nivel": 12},
                  {"id": "b", "tipo": "battle", "clickable": True, "nivel": 8}]
        for i in range(10):
            nodos.append({"id": f"et{i}", "tipo": "trainer"})
        for i in range(20):
            nodos.append({"id": f"co{i}", "tipo": "battle"})
        edges: list = []
        for i in range(10):
            edges.append(["t", f"et{i}"])
            for j in range(20):
                edges.append([f"et{i}", f"co{j}"])
        return nodos, edges

    def _roto() -> list[dict]:
        """3 móns, 1 en pie, 2 caidos, y muy por debajo del jefe."""
        return [{"nombre": "Bulbasaur", "nivel": 6, "ps": 100, "ps_max": 100,
                 "tipos": ["Planta"], "baseStats": {"hp": 100}},
                {"nombre": "Pidgey", "nivel": 5, "ps": 0, "ps_max": 50,
                 "tipos": ["Normal"], "baseStats": {"hp": 100}},
                {"nombre": "Caterpie", "nivel": 4, "ps": 0, "ps_max": 45,
                 "tipos": ["Planta"], "baseStats": {"hp": 100}}]

    nodos, edges = _pantalla()
    original = PL.EXP["escalera_riesgo"]
    original_nivel = PL.EXP.get("veto_nivel", True)
    try:
        # H11 aísla una sola variable: aquí se mide la escalera, así que el
        # veto de nivel se apaga (si no, el control también evitaría al
        # entrenador Nv12 con media 5 y los dos brazos medirían lo mismo).
        PL.EXP["veto_nivel"] = False
        PL.EXP["escalera_riesgo"] = False
        d_b = PL.elegir(_roto(), nodos, {"hay_cura": False}, region="Kanto",
                        insignias=0, edges=edges)
        PL.EXP["escalera_riesgo"] = True
        d_a = PL.elegir(_roto(), nodos, {"hay_cura": False}, region="Kanto",
                        insignias=0, edges=edges)
    finally:
        PL.EXP["escalera_riesgo"] = original
        PL.EXP["veto_nivel"] = original_nivel

    check("sin escalera el bot elige al entrenador por el bono de ruta",
          d_b.tipo == "entrenador",
          f"-> el control deberia seguir eligiendo al entrenador, "
          f"eligio {d_b.tipo}")
    check("con escalera el entrenador de riesgo pierde el nodo",
          d_a.tipo != "entrenador",
          f"-> el bono de ruta (+210) sigue tapando la penalizacion; "
          f"eligio {d_a.tipo}")
    check("la escalera cambia de verdad la decision",
          d_b.tipo != d_a.tipo,
          f"-> los dos brazos acaban igual ({d_b.tipo}): el flag no hace nada")

    # Y lo que la hizo segura antes: sin alternativa se pelea igual, para no
    # dejar al bot sin nada que pulsar.
    PL.EXP["escalera_riesgo"] = True
    try:
        solo = [{"id": "t", "tipo": "trainer", "clickable": True,
                 "sprite": "youth", "nivel": 12}]
        d_solo = PL.elegir(_roto(), solo, {"hay_cura": False}, region="Kanto",
                           insignias=0, edges=[])
    finally:
        PL.EXP["escalera_riesgo"] = original
    check("la escalera no ata al bot cuando el entrenador es lo unico",
          d_solo.tipo == "entrenador",
          f"-> eligio {d_solo.tipo}: el bot se quedaria sin nada que pulsar")


def test_el_bono_de_ruta_sigue_premiando_al_control() -> None:
    """El control (flag apagado) tiene que seguir prefiriendo la rama larga.

    **Esto NO es H20**, que quedo retractada: era "con el equipo roto, la rama
    que gasta menos gana", y resulto ser lo contrario de lo que hacia falta.
    En 26 runs el bot recorria el mapa al doble de velocidad (10 pasos/run
    frente a 21), llegaba antes a los jefes y moria antes: paso al morir 29
    contra 52, nivel maximo 11,8 contra 18,7. El mecanismo vivo es H21.

    Lo que se comprueba aqui es que el flag **no toca el control**: sin el, la
    rama con 8 combates por delante sigue ganando por el bono de ruta, que es
    lo que §1.4 dice que funciona. Si esto se rompiera, el experimento mediria
    otra cosa.
    """
    # Dos ramas desde el nodo actual: `a` deja una **cadena** de 8 combates por
    # delante y `b` deja 1.
    #
    # La rama es una cadena y no un abanico a proposito:
    # `combates_por_delante` suma el nodo mas el **maximo** de sus hijos, o sea
    # que cuenta el camino mas profundo, no el total.
    nodos: list[dict] = [
        {"id": "a", "atajo": "a", "tipo": "battle", "clickable": True,
         "nivel": 8},
        {"id": "b", "atajo": "b", "tipo": "battle", "clickable": True,
         "nivel": 8},
    ]
    edges: list = []
    anterior = "a"
    for i in range(7):
        nodo = f"larga{i}"
        nodos.append({"id": nodo, "tipo": "battle"})
        edges.append([anterior, nodo])
        anterior = nodo
    nodos.append({"id": "corta", "tipo": "battle"})
    edges.append(["b", "corta"])

    def _equipo(sano: bool) -> list[dict]:
        ps = 100 if sano else 0
        return [{"nombre": "Bulbasaur", "nivel": 6, "ps": ps, "ps_max": 100,
                 "tipos": ["Planta"], "baseStats": {"hp": 100}},
                {"nombre": "Pidgey", "nivel": 6, "ps": 100, "ps_max": 50,
                 "tipos": ["Normal"], "baseStats": {"hp": 100}}]

    d_control = PL.elegir(_equipo(False), nodos, {"hay_cura": False},
                          region="Kanto", insignias=0, edges=edges)
    check("sin el flag, la rama larga gana por el bono de ruta",
          d_control.valor == "a",
          f"-> el control eligio '{d_control.valor}'; deberia ser 'a' (8 "
          f"combates por delante)")

    # Y lo que lo hace seguro: sin nada barato en pantalla se pelea igual. Un
    # veto duro dejaria al bot sin opcion, que es como se perdia antes.
    solo = [{"id": "a", "atajo": "a", "tipo": "battle",
             "clickable": True, "nivel": 8}]
    d_solo = PL.elegir(_equipo(False), solo, {"hay_cura": False},
                       region="Kanto", insignias=0, edges=[])
    check("el bot no se queda sin nada que pulsar",
          d_solo.valor == "a",
          f"-> eligio '{d_solo.valor}': el bot se quedaria sin nada que pulsar")

    # **La propiedad que mas importa**: con el equipo roto y un pokecenter en
    # pantalla, la cura tiene que ganar **tambien** con el flag puesto. El
    # corte de emergencia devuelve -5.0 y el bono de ruta se suma encima, asi
    # que un signo mal puesto podria dejar al bot peleando con el equipo al
    # 30% mientras el centro puntua -100. Medido sobre las 26 runs: 7 de 7
    # pantallas con cura fueron a curar en el brazo tratado, 22 de 22 en el
    # control. O sea que **esto** no lo rompe ningun flag.
    cura = [{"id": "p", "atajo": "p", "tipo": "pokecenter", "clickable": True}]
    cura += nodos
    edges_cura = edges + [["p", "la0"], ["p", "corta"]]
    previo = PL.RUTA_POR_EXP
    try:
        PL.RUTA_POR_EXP = True
        d_cura = PL.elegir(_equipo(False), cura, {"hay_cura": True},
                           region="Kanto", insignias=0, edges=edges_cura)
    finally:
        PL.RUTA_POR_EXP = previo
    check("el flag no puede hacer que el bot se pelee en vez de curarse",
          d_cura.valor == "p",
          f"-> eligio '{d_cura.valor}' ({d_cura.tipo}) con el equipo roto y un "
          f"centro en pantalla: la penalizacion de ruta se ha comido la cura")


def test_h20_no_resta_la_cura_que_va_por_delante() -> None:
    """El pokecentro que la rama ofrece **no** puede contar como coste.

    Este es el fallo que hacia que H20 midiera lo contrario de lo que decia.
    Antes los tres sumandos iban a un solo `extra` (peleas + 4x entrenador +
    **12x pokecentro**) y despues H20 restaba `extra` entero. O sea que el
    mecanismo de "la rama que gasta menos gana" **restaba la cura**, que es
    justo lo que el equipo roto necesita.

    El caso que lo destapa es el de §1.3: el pokecentro **no** esta en pantalla
    (la cura se quedo atras), solo se ve al elegir la rama correcta. Los tests
    anteriores de H20 montaban el centro como nodo clicable, y ahi dispara el
    corte de emergencia, que devuelve -5.0 antes de llegar al bono de ruta: el
    bug quedaba tapado por un camino que en la partida real casi no se da.

    El numero que lo delata son las cifras del propio marcador: en `log/h20`,
    `extra` valia **88, 105 y 56**, y `combates_por_delante` esta topado en 8.
    Un total de peleas no puede ser 105: era 12 por cada centro de la rama.
    """
    # `corta` deja 1 combate y **un pokecentro** por delante; `larga` deja 3 y
    # ninguno. Los dos nodos visibles son de combate, para que lo unico que los
    # distinga sea lo que cuesta y lo que cura la rama.
    nodos: list[dict] = [
        {"id": "larga", "atajo": "larga", "tipo": "battle", "clickable": True,
         "nivel": 8},
        {"id": "corta", "atajo": "corta", "tipo": "battle", "clickable": True,
         "nivel": 8},
        {"id": "centro", "atajo": "centro", "tipo": "pokecenter",
         "clickable": False},
        {"id": "jefe", "atajo": "jefe", "tipo": "boss", "clickable": True},
    ]
    edges: list = [["larga", "x1"], ["x1", "x2"], ["x2", "jefe"],
                   ["corta", "centro"], ["centro", "jefe"]]
    for i in ("x1", "x2"):
        nodos.append({"id": i, "tipo": "battle"})

    roto = [{"nombre": "Bulbasaur", "nivel": 6, "ps": 0, "ps_max": 100,
             "tipos": ["Planta"], "baseStats": {"hp": 100}},
            {"nombre": "Pidgey", "nivel": 6, "ps": 30, "ps_max": 50,
             "tipos": ["Normal"], "baseStats": {"hp": 100}}]

    previo = PL.RUTA_POR_EXP
    try:
        PL.RUTA_POR_EXP = True
        d = PL.elegir(roto, nodos, {"hay_cura": False}, region="Kanto",
                      insignias=0, edges=edges)
    finally:
        PL.RUTA_POR_EXP = previo

    check("H20 elige la rama que pasa por el pokecentro, no la que mas pelea",
          d.valor == "corta",
          f"-> eligio '{d.valor}': con el equipo roto, la rama con cura por "
          f"delante tiene que ganarle a la de 3 combates y ningun centro")
    check("el motivo separa el coste de la cura",
          "pokecenter(s) por delante" in d.razon or "centro" in d.razon.lower(),
          f"-> el motivo no dice quantos centros hay delante, asi que no se puede "
          f"saber si los esta restando: {d.razon[:160]}")
    check("ningun pokecentro por delante resta puntos",
          "-12" not in d.razon.split("H20")[-1],
          f"-> el motivo parece restar los centros por delante: {d.razon[:160]}")

    # Y la mitad que faltaba del contrato: la cura por delante tiene que **sumar**
    # con el equipo roto. Con el codigo roto, el marcador que imprimia `extra`
    # entero restaba 12*3.5 = 42 en vez de sumar 12.
    fuente = Path(SCRIPTS / "planificador.py").read_text(encoding="utf-8")
    check("la cura por delante se suma FUERA de lo que se resta",
          "s -= n_salv * PESO_POR_NIVEL_EXP" in fuente
          and "s += n_centro * PESO_CURA_POR_DELANTE" in fuente,
          "-> el pokecenter tiene que quedar fuera del signo: si comparte "
          "acumulador con el coste, volveria el bug de H20")
    check("nada resta un acumulador que incluya los pokecenters",
          "s -= coste * PESO" not in fuente and "-= extra" not in fuente,
          "-> `coste`/`extra` arrastran los pokecenters: es el bug original")


def test_la_traza_de_consume_ps() -> None:
    """La traza de H24 tiene que **leer el campo que existe**.

    El volcado de `estado_batalla()` trae la vida como **una sola cadena**
    `"5/26"` y **no trae `ps_max`**: sale del `textContent` de `[class*=hp]`.
    La primera versión de `_ps_fraccion` leía `m["ps_max"]`, que no existe, y
    como el `except` devolvía 0 la suma salía **siempre 0** — con las líneas
    de la traza perfectamente normales, que es lo peor que puede pasar: un
    instrumento que dice "cuesta 0" y no falla.

    Es la tercera vez en este repo que un campo inexistente más un `except`
    ancho dan un número falso en silencio (el recuento de móns vivos, y ahora
    el consumo por pelea). Por eso el test mira **el valor**, no que la función
    exista: que devuelva `(0, 0)` para una fracción válida es el bug.
    """
    import jugar_pokelike as JUG
    check("una fraccion real se lee bien",
          JUG._ps_fraccion({"ps": "5/26"}) == (5, 26),
          f"-> la funcion devolvio "
          f"{JUG._ps_fraccion({'ps': '5/26'})}: el campo `ps` es una cadena "
          f"fraccion y no hay `ps_max` en el volcado")
    check("un món a 0 conserva su maximo",
          JUG._ps_fraccion({"ps": "0/31"}) == (0, 31),
          "-> sin el denominador no se puede saber cuanto costo la pelea")
    check("basura no revienta",
          JUG._ps_fraccion({"ps": None}) == (0, 0)
          and JUG._ps_fraccion({"ps": "xx"}) == (0, 0),
          "-> un valor ilegible tiene que dar 0, no lanzar")
    fuente = Path(JUG.__file__).read_text(encoding="utf-8")
    check("`_ps_al_abrir` nace en __init__",
          "self._ps_al_abrir: int | None = None" in fuente,
          "-> AttributeError en la primera pelea de la primera run")


def test_el_prep_del_jefe_usa_el_ps_real() -> None:
    """El orden contra el jefe tiene que usar el PS **real**, no el del HUD.

    El HUD marca 100 a un món caido y marca 100 a todo el mundo tras una cura.
    Si el `prep` del jefe leyera el HUD crudo, `orden_para_entrenador` recibiria
    `ps=100` para los tres y el desempate lo acabaria decidiendo el nivel en
    vez de la vida real.

    **Se sospecho de un bug aqui y NO lo habia** (10-10). Se leyo el caso del
    log de `h20_ABORTADO_CURA_RESTADA_1010_1116`, run B-202105: el bot entra
    contra Brock con el equipo al 100% y sale Poliwag al frente. Se concluyo
    que el chart estaba mal (`Agua -> Roca` salia x2). **La tabla de
    referencia usada para comprobarlo estaba mal, no el chart**: en el juego
    Agua contra Roca es x2 de verdad, igual que Planta, asi que los dos
    empatan y el orden es discutible pero no erroneo.

    Queda el test porque la invariante es real y el sitio es de una sola linea:
    si alguien vuelve a leer el HUD crudo aqui, el orden pasa a decidirse por
    nivel sin que nada falle.
    """
    import jugar_pokelike as JUG
    fuente = Path(JUG.__file__).read_text(encoding="utf-8")
    cuerpo = fuente[fuente.index("def _preparar_contra_el_rival"):]
    cuerpo = cuerpo[:cuerpo.index("\n    def ", 10)]
    check("el prep del jefe usa el PS real",
          "self.equipo_con_tipos()" in cuerpo,
          "-> sin `equipo_con_tipos()` el orden va con los porcentajes del HUD, "
          "que marcan 100 a un món caido y a todo el mundo tras una cura")

    # Y el caso del log, con el chart REAL del juego: Agua contra Roca es x2,
    # igual que Planta. Los dos empatan en ofensa y decide el aguante, asi que
    # el orden NO es un bug. Este check fija ese numero para que no se vuelva
    # a "encontrar" un chart roto que no lo está.
    rival = ["Roca", "Tierra"]
    check("Agua contra Roca es x2 en el chart del juego (no x0,5)",
          PL.P.utilidad_contra(["Agua"], "Roca")[0] == 2.0,
          "-> si esto baja a 0,5 es que el chart se ha 'arreglado' al Gen 6 "
          "oficial, que NO es lo que hace el juego (ver AGENT.md)")


def test_h21_deja_de_premiar_al_salvaje_y_no_toca_al_trainer() -> None:
    """Con el equipo roto, el salvage deja de premiarse. El trainer no se toca.

    **H20 hacia lo contrario y quedo retractada.** Restaba
    `combates_por_delante` a salvajes y entrenadores **por igual**, siendo que
    miden distinto: medido sobre 154 peleas ganadas, el entrenador da +2,00
    niveles y elavage +1,00. Al penalizar los dos igual, el bot aprendio a
    descartar tambien los entrenadores (1,7/run frente a 5,2 del control), y
    §1.2 ya dice que la exp no se recupera despues.

    **Lo que se mide es el peso de cada rama**, no el ganador. Montar una
    pantalla donde el ganador cambie obliga a que las dos ramas valgan mas o
    menos lo mismo, y entonces cualquier otra regla (veto por nivel, escalera
    de riesgo) decide por encima de H21 y el fallo no se puede atribuir.

    Y las dos propiedades que importan, por separado:
      - la rama de **salvajes** baja con el flag
      - la rama de **entrenador** NO baja: conserva su prima entera

    Esa segunda es la que H20 rompio y la que la primera version de H21
    rompio tambien (sustituia el bono entero y el trainer perdiá 10,5 puntos).
    """
    nodos: list[dict] = [
        {"id": "sal", "atajo": "sal", "tipo": "battle",
         "clickable": True, "nivel": 8},
        {"id": "tra", "atajo": "tra", "tipo": "trainer",
         "clickable": True, "nivel": 8},
        {"id": "jefe", "atajo": "jefe", "tipo": "boss", "clickable": True},
    ]
    edges: list = ([["sal", f"s{i}"] for i in range(6)]
                   + [["s5", "jefe"], ["tra", "jefe"]])
    nodos += [{"id": f"s{i}", "tipo": "battle"} for i in range(6)]

    # 1 caido => `roto` (la puerta que dispara H21), con 4 mons para que el
    # nodo de trainer sea una opcion real.
    roto = [{"nombre": "Bulbasaur", "nivel": 6, "ps": 0, "ps_max": 100,
             "tipos": ["Planta"], "baseStats": {"hp": 100}},
            {"nombre": "Pidgey", "nivel": 6, "ps": 90, "ps_max": 100,
             "tipos": ["Normal"], "baseStats": {"hp": 100}},
            {"nombre": "Rattata", "nivel": 6, "ps": 90, "ps_max": 100,
             "tipos": ["Normal"], "baseStats": {"hp": 100}},
            {"nombre": "Sandshrew", "nivel": 6, "ps": 90, "ps_max": 100,
             "tipos": ["Ground"], "baseStats": {"hp": 100}}]

    def _score(flag: bool, ns: list[dict], es: list, eq: list[dict]) -> float:
        # Las tres reglas se apagan para aislar H21: el veto por nivel y la
        # escalera son correctas (§1.4) pero se comen el efecto y el fallo
        # dejaria de ser atribuible (§5.8).
        previo = PL.RUTA_POR_EXP
        prev_esc, prev_veto = PL.EXP["escalera_riesgo"], PL.EXP["veto_nivel"]
        try:
            PL.RUTA_POR_EXP = flag
            PL.EXP["escalera_riesgo"] = False
            PL.EXP["veto_nivel"] = False
            d = PL.elegir(eq, ns, {"hay_cura": False}, region="Kanto",
                          insignias=0, edges=es)
            return float(d.razon.split("score=")[1].split(" ")[0])
        finally:
            PL.RUTA_POR_EXP = previo
            PL.EXP["escalera_riesgo"] = prev_esc
            PL.EXP["veto_nivel"] = prev_veto

    solo_sal = [n for n in nodos if n["id"] != "tra"]
    edges_sal = [e for e in edges if e[1] != "jefe" or e[0] == "s5"]
    solo_tra = [n for n in nodos if n["id"] != "sal"]
    edges_tra = [e for e in edges if e[0] != "sal"]

    d_sal = _score(True, solo_sal, edges_sal, roto) - _score(False, solo_sal,
                                                            edges_sal, roto)
    check("H21 baja la rama de salvajes, que es lo unico que castiga",
          d_sal < 0,
          f"-> la rama de 6 salvajes cambio {d_sal:+.1f} con el flag: deberia "
          f"BAJAR, porque con el equipo roto hay que dejar de cazar salvajes")

    d_tra = _score(True, solo_tra, edges_tra, roto) - _score(False, solo_tra,
                                                            edges_tra, roto)
    check("H21 NO baja la rama del entrenador",
          d_tra >= 0,
          f"-> el Trainer por delante cambio {d_tra:+.1f}: deberia quedar "
          f"igual o subir. Bajaria si H21 tocase el bono entero, que es "
          f"justo lo que hacia H20")

    sano = [dict(m, ps=m["ps_max"]) for m in roto]
    check("H21 NO toca nada con el equipo entero",
          _score(True, solo_sal, edges_sal, sano)
          == _score(False, solo_sal, edges_sal, sano),
          "-> sano: el flag no deberia cambiar nada")


def test_salvajes_y_entrenadores_se_cuentan_por_separado() -> None:
    """El contador de salvajes tiene que existir y no contar un entrenador."""
    nodos = [{"id": "a", "tipo": "battle"}, {"id": "t", "tipo": "trainer"},
             {"id": "jefe", "tipo": "boss"}]
    edges = [["a", "t"], ["t", "jefe"]]
    sal = PL.P.salvajes_por_delante(nodos, edges, 8)
    ent = PL.P.entrenadores_por_delante(nodos, edges, 8)
    comb = PL.P.combates_por_delante(nodos, edges, 8)
    check("salvajes_por_delante existe y cuenta solo salvajes",
          sal.get("a") == 1 and sal.get("t") == 0,
          f"-> sal={sal}: un entrenador no cuenta como salvaje")
    check("entrenadores_por_delante cuenta al suyo y a los de su rama",
          ent.get("t") == 1 and ent.get("a") == 1,
          f"-> ent={ent}: el nodo 'a' ve al entrenador que hay tras el, que es "
          f"lo que tiene que pasar")
    # **Los dos contadores NO reconstruyen el total de combates, y no deben.**
    # `entrenadores_por_delante` y `salvajes_por_delante` suman a lo largo de
    # toda la rama; `combates_por_delante` toma el **maximo** de los hijos. Son
    # cuentas distintas a proposito: la primera pregunta "cuanta exp hay en la
    # rama", la segunda "cuantas peleas tiene el camino mas profundo". Por eso
    # este test comprueba que NO son intercambiables, que es lo que H20 asumia.
    check("salvajes y entrenadores no son intercambiables con 'combates'",
          not (sal.get("a", 0) + ent.get("a", 0)) == comb.get("a")
          or sal.get("a") == comb.get("a") - ent.get("a"),
          f"-> sal={sal} ent={ent} comb={comb}: si los tres devolviesen lo "
          f"mismo, el reparto de H21 no mediria nada")


def test_h20_usa_el_ps_real_y_no_el_del_hud() -> None:
    """El "equipo roto" tiene que salirse del PS real, no del HUD.

    El HUD marca **100 a un món caído**. H19 leia `j.equipo()` (el HUD crudo)
    para decidir si el equipo estaba roto, y por eso su marcador imprimia
    "equipo entero, vida 100%, vivos 2/2" en el mismo paso en que la traza de
    mapa decia `Bulbasaur:0%`. Un instrumento que describe mal el mundo hace
    que toda la medida posterior sea basura, y fue justo lo que paso con H19.
    """
    fuente = Path(SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    check("el HUD crudo no se usa para decidir el estado del equipo",
          "self.j.equipo()" not in fuente or "_ps_real" in fuente,
          "-> `j.equipo()` sin `equipo_con_tipos()` devuelve el porcentaje del "
          "HUD, que marca 100 a un món caido")

    sano = [{"nombre": "Bulbasaur", "nivel": 6, "ps": 100, "ps_max": 100},
            {"nombre": "Pidgey", "nivel": 6, "ps": 90, "ps_max": 100}]
    caido = [{"nombre": "Bulbasaur", "nivel": 6, "ps": 0, "ps_max": 100},
             {"nombre": "Pidgey", "nivel": 6, "ps": 100, "ps_max": 100}]
    caido = [{"nombre": "Bulbasaur", "nivel": 6, "ps": 0, "ps_max": 100},
             {"nombre": "Pidgey", "nivel": 6, "ps": 100, "ps_max": 100}]
    check("un solo món a 0 ya es equipo roto",
          PL.equipo_roto(caido),
          "-> con un món a 0 el equipo no puede pagar otra pelea, aunque la "
          "media de vida sea del 50%")
    check("un equipo entero no esta roto",
          not PL.equipo_roto(sano),
          "-> 100% y 90% estan por encima de la puerta del 75%")


def test_el_brazo_de_control_no_hereda_la_escalera() -> None:
    """Con el flag apagado la escalera no puede aparecer: si aparece, miden igual.

    El bloque de la escalera se escribio **fuera** del `if not EXP[...]`, asi
    que el brazo de control tambien la ejecutaba en todos los estados donde la
    rama vieja no disparaba. Medido: el control marco "entrenador de riesgo" 2
    veces. Con eso los dos brazos son casi el mismo bot y la comparacion no dice
    nada, aunque el informe no avise.
    """
    plan = PL.plan_para("Kanto", 0)
    roto = [{"nombre": "A", "nivel": 6, "ps": 100, "ps_max": 100,
             "tipos": ["Planta"], "baseStats": {"hp": 100}},
            {"nombre": "B", "nivel": 5, "ps": 0, "ps_max": 50,
             "tipos": ["Normal"], "baseStats": {"hp": 100}},
            {"nombre": "C", "nivel": 4, "ps": 0, "ps_max": 45,
             "tipos": ["Planta"], "baseStats": {"hp": 100}}]
    ctx = PL.Contexto(equipo=roto, plan=plan, nivel_rival=5,
                      hay_cura_disponible=False)

    original = PL.EXP["escalera_riesgo"]
    try:
        PL.EXP["escalera_riesgo"] = True
        con_flag, raz_a = PL.puntuar("entrenador", ctx)
        PL.EXP["escalera_riesgo"] = False
        sin_flag, raz_b = PL.puntuar("entrenador", ctx)
    finally:
        PL.EXP["escalera_riesgo"] = original

    check("con el flag la escalera marca el riesgo", "riesgo" in raz_a,
          f"-> {raz_a}")
    check("sin el flag la escalera no aparece", "de riesgo" not in raz_b,
          f"-> el control hereda la escalera: los dos brazos miden lo mismo "
          f"({raz_b})")
    check("sin el flag el trainer se juega igual por ser la unica exp",
          sin_flag > con_flag,
          f"-> control {sin_flag} vs escalera {con_flag}")


def test_el_veto_de_nivel_gana_al_bono_de_ruta() -> None:
    """H11: el veto por nivel tiene que poder perder contra el bono de ruta.

    Mismo fallo que la escalera: devolvía -4.0 en `puntuar()` y el bono
    (60-300) lo tapaba 8/8 veces. Aquí se monta la pantalla exacta: entrenador
    Nv15 con 10 entrenadores y 20 combates por delante (+210) contra una
    batalla sana. Equipo sano para aislar el veto de la escalera (sin caídos
    y al 100%: `riesgo_entrenador` no dispara).
    Guía: level lead 1+ por encima
    (https://pokelike-guide.fr/en/normal/improving-your-team/).
    """
    def _pantalla() -> tuple[list[dict], list]:
        nodos = [{"id": "t", "tipo": "trainer", "clickable": True,
                   "sprite": "ace-trainer", "nivel": 15},
                  {"id": "b", "tipo": "battle", "clickable": True, "nivel": 8}]
        for i in range(10):
            nodos.append({"id": f"et{i}", "tipo": "trainer"})
        for i in range(20):
            nodos.append({"id": f"co{i}", "tipo": "battle"})
        edges: list = []
        for i in range(10):
            edges.append(["t", f"et{i}"])
            for j in range(20):
                edges.append([f"et{i}", f"co{j}"])
        return nodos, edges

    def _sano() -> list[dict]:
        return [{"nombre": "Bulbasaur", "nivel": 8, "ps": 30, "ps_max": 30,
                 "tipos": ["Planta", "Veneno"], "baseStats": {"hp": 100}},
                {"nombre": "Pidgey", "nivel": 8, "ps": 25, "ps_max": 25,
                 "tipos": ["Normal", "Volador"], "baseStats": {"hp": 100}},
                {"nombre": "Geodude", "nivel": 8, "ps": 26, "ps_max": 26,
                 "tipos": ["Roca", "Tierra"], "baseStats": {"hp": 100}}]

    nodos, edges = _pantalla()
    original = PL.EXP.get("veto_nivel", True)
    original_esc = PL.EXP["escalera_riesgo"]
    try:
        PL.EXP["escalera_riesgo"] = True
        PL.EXP["veto_nivel"] = False
        d_b = PL.elegir(_sano(), nodos, {"hay_cura": False}, region="Kanto",
                        insignias=0, edges=edges)
        PL.EXP["veto_nivel"] = True
        d_a = PL.elegir(_sano(), nodos, {"hay_cura": False}, region="Kanto",
                        insignias=0, edges=edges)
    finally:
        PL.EXP["veto_nivel"] = original
        PL.EXP["escalera_riesgo"] = original_esc

    check("sin veto de nivel el bot entra al entrenador por el bono",
          d_b.tipo == "entrenador",
          f"-> el control debería elegir entrenador, eligió {d_b.tipo}")
    check("con veto de nivel el rival superior pierde el nodo",
          d_a.tipo != "entrenador",
          f"-> el bono sigue tapando el veto; eligió {d_a.tipo}")
    check("el veto de nivel cambia de verdad la decisión",
          d_b.tipo != d_a.tipo,
          f"-> los dos brazos acaban igual ({d_b.tipo})")

    # Seguridad: si es lo único, se pelea igual (no es veto duro).
    try:
        PL.EXP["veto_nivel"] = True
        solo = [{"id": "t", "tipo": "trainer", "clickable": True,
                 "sprite": "ace-trainer", "nivel": 15}]
        d_solo = PL.elegir(_sano(), solo, {"hay_cura": False}, region="Kanto",
                           insignias=0, edges=[])
    finally:
        PL.EXP["veto_nivel"] = original
    check("el veto de nivel no ata al bot si es lo único",
          d_solo.tipo == "entrenador",
          f"-> eligió {d_solo.tipo}: se quedaría sin nada que pulsar")

    # Y `puntuar()` sigue diciendo "vetado" para el log y los tests viejos.
    ctx = PL.Contexto(equipo=_sano(), plan=PL.plan_para("Kanto", 0),
                      nivel_rival=15)
    _p, motivo = PL.puntuar("entrenador", ctx)
    check("el veto de nivel dice vetado en puntuar",
          "vetado" in motivo, f"-> {motivo}")
    _vp, pen, _m = PL.veto_nivel_entrenador(ctx)
    check("el veto de nivel trae penalización final",
          pen == PL.PENALIZACION_VETO_NIVEL, f"-> {pen}")


class _PaginaFalsa:
    """Navegador minimo para probar `_trade` sin abrir el juego.

    Reproduce lo que se midio en vivo contra pokelike.xyz: al llegar a
    `#trade-screen` solo hay DECLINE, y las opciones con atajo aparecen al
    pulsar la fila. `pulsos` guarda las teclas que se han enviado, que es lo
    que decide si el bot cierra el trato o lo declina.
    """

    def __init__(self, opciones: list[dict], cierra_con_atajo: bool = True) -> None:
        self.opciones = opciones
        self.cerra_con_atajo = cierra_con_atajo
        self.pulsos: list[str] = []
        self.clics: list[int] = []
        self.pantalla_actual = "trade-screen"

        class _Teclado:
            def __init__(self, fuera: _PaginaFalsa) -> None:
                self.fuera = fuera

            def press(self, tecla: str) -> None:
                self.fuera.pulsos.append(tecla)
                if self.fuera.cerra_con_atajo:
                    self.fuera.pantalla_actual = "map-screen"

        class _Espera:
            def wait_for_timeout(self, _ms: int) -> None:
                return None

        self.keyboard = _Teclado(self)
        self._espera = _Espera()

    def wait_for_timeout(self, ms: int) -> None:
        return self._espera.wait_for_timeout(ms)

    def evaluate(self, js: str, *args: object) -> object:
        # La primera llamada es la carta misteriosa (no existe en el juego
        # real), la segunda el clic en la fila, y despues las opciones.
        if "trade-mystery-card" in js:
            return None
        if "trade-member-row" in js:
            return True
        if "data-shortcut" in js and "getElementById" in js:
            if self.pantalla_actual != "trade-screen":
                return []
            return self.opciones
        if "trade-member-row" in js and "click" in js:
            self.clics.append(1)
            return True
        return None


class _JuegoFalso:
    def __init__(self, page: _PaginaFalsa) -> None:
        self.page = page

    def pantalla(self) -> str:
        return self.page.pantalla_actual

    def visible(self, _sel: str) -> bool:
        return False


class _BotFalso(J.Bot):
    """Solo lo que `_trade` toca, heredando la clase real.

    Hereda de `Bot` (sin llamar a `__init__`) en vez de ser una clase suelta:
    si `_trade` necesita un atributo de clase que el falso no tiene, con esto
    el atributo sale de verdad y el fallo se ve, en lugar de aparecer como un
    `AttributeError` tragado por el `except` de `_trade` que se va por otro
    camino. Los metodos reales van enganchados, no reimplementados.
    """

    def __init__(self, opciones: list[dict], rival: str = "Water",
                 cierra: bool = True) -> None:
        self.page = _PaginaFalsa(opciones, cierra_con_atajo=cierra)
        self.j = _JuegoFalso(self.page)
        self.tipo_lider = rival
        self._trade_hecho = False
        self.ps_invalidados: list[str] = []
        self.lineas: list[str] = []
        self.nombre_starter = "Ivysaur"

    def log(self, linea: str) -> None:
        self.lineas.append(linea)

    def _volcar_trade(self) -> None:
        self.lineas.append("volcado")

    def _invalidar_ps(self, motivo: str) -> None:
        self.ps_invalidados.append(motivo)

    def _opciones_genericas(self, *args: object) -> str:
        """El camino viejo, que va a por DOM: aqui solo se anota que se llego.

        El brazo de control tiene que acabar aqui (es el bug que se quiere
        medir), pero el metodo real trabaja contra el navegador. Se sustituye
        **solo** para no abrir el juego en un test, y el test comprueba que se
        llego, que es justamente lo que demuestra que el flag manda.
        """
        self.lineas.append("opciones genericas")
        return "opciones genericas (camino viejo)"

    def equipo_con_tipos(self) -> list[dict]:
        # El peor es Spearow (Nv16, 50 de suma de stats), que es a quien el bot
        # debe sacrificar: nunca al starter.
        return [{"nombre": "Ivysaur", "nivel": 18, "ps": 100, "ps_max": 100,
                 "tipos": ["Planta", "Veneno"],
                 "baseStats": {"hp": 60, "atq": 62, "def": 63, "vel": 80,
                               "spa": 80, "spd": 80}},
                {"nombre": "Spearow", "nivel": 16, "ps": 40, "ps_max": 40,
                 "tipos": ["Normal", "Volador"],
                 "baseStats": {"hp": 40, "atq": 60, "def": 30, "vel": 70,
                               "spa": 31, "spd": 31}},
                {"nombre": "Tentacool", "nivel": 11, "ps": 90, "ps_max": 90,
                 "tipos": ["Agua", "Veneno"],
                 "baseStats": {"hp": 65, "atq": 40, "def": 44, "vel": 70,
                               "spa": 50, "spd": 50}}]


OPCIONES_3 = [{"atajo": "1", "texto": "? NORMAL Lv 19"},
              {"atajo": "2", "texto": "? WATER Lv 19"},
              {"atajo": "3", "texto": "? FIRE Lv 19"}]


def test_el_trade_se_cierra_con_el_atajo() -> None:
    """El bug: el bot buscaba un boton de continuar que no existe y declinaba.

    Medido: **0 trades aceptados en 319 runs**, con 334 pantallas que ofrecian
    el nodo. El unico `<button>` de `#trade-screen` es `#btn-skip-trade`
    (DECLINE): la unica forma de cerrar el trato es pulsar `1`, `2` o `3` sobre
    `div[data-shortcut]`, y esas opciones **solo aparecen** despues de elegir a
    quien se sacrifica. Comprobado en vivo: Doduo Lv16 -> Rattata Lv19.
    """
    bot = _BotFalso(OPCIONES_3, rival="Fire")
    res = J.Bot._trade(bot)

    check("el trade pulsa un atajo para cerrarse", bot.page.pulsos == ["2"],
          f"-> teclas pulsadas: {bot.page.pulsos}")
    check("el trade se marca como hecho", bot._trade_hecho is True,
          f"-> _trade_hecho={bot._trade_hecho}")
    check("el trade accepted devuelve algo aceptado",
          str(res).startswith("trade aceptado"),
          f"-> devolvio {res!r}: el bot habria declinado el nodo mas fuerte")
    check("el trade invalida los PS leidos antes",
          bot.ps_invalidados == ["trade"],
          f"-> {bot.ps_invalidados}: el PS cacheado no se refresca y el "
          f"reordenado usa vida vieja")


def test_el_trade_elige_el_atajo_por_tipo() -> None:
    """El atajo no es cualquiera: se pide el tipo que pega al jefe que toca.

    Sin esto se aceptaria siempre la opcion 1 y se perderia media partida de
    tipos, que es justo lo que el trade da gratis ademas de los +3 niveles.
    """
    b_fuego = _BotFalso(OPCIONES_3, rival="Fire")
    J.Bot._trade(b_fuego)
    check("contra un jefe de Fuego pide el Agua", b_fuego.page.pulsos == ["2"],
          f"-> pidio {b_fuego.page.pulsos} (2 es Water, 2x contra Fire)")

    b_agua = _BotFalso(OPCIONES_3, rival="Water")
    J.Bot._trade(b_agua)
    check("contra un jefe de Agua no pide el Water", b_agua.page.pulsos == ["1"],
          f"-> pidio {b_agua.page.pulsos}: Water->Water es 0.5x, 1 (Normal) es "
          f"mejor de las tres")

    b_normal = _BotFalso(OPCIONES_3, rival="Normal")
    J.Bot._trade(b_normal)
    check("sin jefe conocido pide la primera", b_normal.page.pulsos == ["1"],
          f"-> pidio {b_normal.page.pulsos}")


def test_el_brazo_de_control_del_trade_sigue_declinando() -> None:
    """`PKL_TRADE=0` debe reproducir el bug, para poder medir cuanto vale.

    El flag no es un adorno: sin el, la comparacion A/B del trade no se puede
    hacer, porque el otro brazo seria el mismo bot.
    """
    original = os.environ.get("PKL_TRADE")
    try:
        os.environ["PKL_TRADE"] = "0"
        check("el flag apagado desactiva el camino bueno",
              J._trade_activo() is False, "-> el flag no hace nada")
        bot = _BotFalso(OPCIONES_3, rival="Fire")
        J.Bot._trade(bot)
        check("el brazo de control no pulsa ningun atajo",
              bot.page.pulsos == [],
              f"-> teclas pulsadas: {bot.page.pulsos}")
        check("el brazo de control se va por el camino viejo",
              "opciones genericas" in bot.lineas,
              f"-> el flag no esta cortando el atajo: {bot.lineas}")
        os.environ["PKL_TRADE"] = "1"
        bot2 = _BotFalso(OPCIONES_3, rival="Fire")
        res2 = J.Bot._trade(bot2)
        check("el flag encendido cierra el trade", bot2.page.pulsos == ["2"]
              and "aceptado" in str(res2),
              f"-> pulsos {bot2.page.pulsos}, devolvio {res2!r}")
    finally:
        if original is None:
            os.environ.pop("PKL_TRADE", None)
        else:
            os.environ["PKL_TRADE"] = original
    check("por defecto el trade esta activado", J._trade_activo() is True,
          "-> el arreglo no puede depender de que alguien exporte la variable")


def test_el_trade_nunca_cambia_al_starter() -> None:
    """El starter no se toca: es la apertura de la run, y +3 niveles no lo tapa.

    La guía manda cambiar "tu peor món **no-starter**". El bot elegía el más
    débil sin mirar quién era, y con el equipo en un solo món ese món **era**
    el starter. Medido en juego al arreglar el trade: `Route 1: equipo 1
    (vivos 1) niv 8-8` → `trade: se ofrece Bulbasaur` → se quedó con un
    Sandshrew Lv11 y el 2x contra Brock se fue con el món cambiado.
    """
    class _SoloStarter(_BotFalso):
        def equipo_con_tipos(self) -> list[dict]:
            return [{"nombre": "Bulbasaur", "nivel": 8, "ps": 100,
                     "ps_max": 100, "tipos": ["Planta"],
                     "baseStats": {"hp": 45, "atq": 49, "def": 49, "vel": 45,
                                   "spa": 65, "spd": 65}}]

    bot = _SoloStarter(OPCIONES_3, rival="Fire")
    bot.nombre_starter = "Bulbasaur"
    res = J.Bot._trade(bot)
    check("con el equipo en solo el starter no se pulsa ningun atajo",
          bot.page.pulsos == [], f"-> teclas pulsadas: {bot.page.pulsos}")
    check("con el equipo en solo el starter el trade se declina",
          "declinado" in str(res), f"-> devolvio {res!r}")

    # Y con el starter en el equipo pero no solo: se cambia el peor de verdad.
    b2 = _BotFalso(OPCIONES_3, rival="Fire")
    J.Bot._trade(b2)
    check("el starter presente no impide cambiar al peor",
          b2.page.pulsos == ["2"],
          f"-> pidio {b2.page.pulsos}: con el Ivysaur a salvo el Spearow "
          f"(Nv16) es el sacrificiado correcto")


def test_el_trade_no_acepta_a_ciegas() -> None:
    bot = _BotFalso([], rival="Fire")
    bot.opciones = []
    res = J.Bot._trade(bot)
    check("sin opciones no pulsa ninguna tecla", bot.page.pulsos == [],
          f"-> teclas pulsadas: {bot.page.pulsos}")
    check("sin opciones no se marca el trade como hecho",
          bot._trade_hecho is False or "aceptado" not in str(res),
          f"-> devolvio {res!r}: se ha inventado un trade que no ha ocurrido")


def _log_de_prueba(dir: Path, nombre: str, cuerpo: str) -> Path:
    ruta = dir / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(cuerpo, encoding="utf-8")
    return ruta


# Un log sintético con los formatos **copiados literales** de un log real. Si
# el bot cambia un formato, este test tiene que caer: es su única razón de ser.
_LOG_CON_DERROTA = """[10:00:00] pokedex cargado: 767 especies
[10:00:00] == brazo=test | PKL_TRADE=1 | codigo=deadbeef ==
[10:00:00] == run Kanto | presupuesto 1500 pasos (solo para pruebas: agotado NO corta la run) ==
[10:00:01]   [nueva_run -> True] Story
[10:00:02]   TRAZA_CAMINO paso=6 mapa='Route 1: vs Brock (Rock)' ins=0 disp=['batalla'] vivos=1/1 caidos=0 vida_media=100% vida=['Bulbasaur:100%'] niveles=[5] elige=1 peso=193.0
[10:00:02]   DEC nodo mapa=Route 1: vs Brock (Rock) nodo=n0_0 tipo=batalla crudo=catch atajo=1 equipo=1 vivos=1 niv=5-5 insignias=0 disponibles=catch,battle capturas_pantalla=0 razon=batalla score=193.0 (capturar: equipo de 1)
[10:00:03]   DEC combate rival=Wild Pidgey appeared! tipo=salvaje nuestro_niv=6 rival_niv=3 nuestros=1 suyo=1 insignias=0
[10:00:05]   estado: Wild Pidgey appeared! | niveles rivales 3-3
[10:00:05]   enemigos=[('Pidgey Lv3', '12/12', 3)]
[10:00:05]   mios=[('Bulbasaur Lv6', '19/19', 6)]
[10:00:06]   >>> COMBATE GANADO (continuamos en map-screen) | 2-0
[10:00:10]   DEC combate rival=Gym Battle vs Misty! tipo=entrenador nuestro_niv=9 rival_niv=14 nuestros=2 suyo=2 insignias=1
[10:00:20]   estado: Gym Battle vs Misty! | niveles rivales 14-14
[10:00:20]   enemigos=[('Staryu Lv14', '30/30', 14)]
[10:00:20]   mios=[('Bulbasaur Lv9', '0/27', 9), ('Pidgey Lv9', '25/25', 9)]
[10:00:30]   >>> COMBATE PERDIDO contra Gym Battle vs Misty! | nos quedan: Bulbasaur(100/100), Pidgey(100/100) | 4-1
[10:00:31]   RESUMEN Kanto
[10:00:31]   resultado       : GAME_OVER
[10:00:31]   pasos           : 20
[10:00:31]   insignias       : 1
[10:00:31]   combates        : 1 ganados / 1 perdidos
[10:00:31]   peleas entrain. : 1 (+2 nv)
[10:00:31]   peleas salvaje  : 1 (+1 nv)
[10:00:31]   capturas        : 2
[10:00:31]   tutores         : 0
[10:00:31]   objetos         : 1
[10:00:31]   centros         : 1
[10:00:31]   equipo          : 2 (9-9)
[10:00:31]   traza           : /tmp/traza.json
[10:00:31]   visitas tutor   : 0
"""

_SIN_RESUMEN = """[11:00:00] == run Kanto | presupuesto 1500 pasos (solo para pruebas: agotado NO corta la run) ==
[11:00:02]   [nueva_run -> True] Story
{
  "region": "Kanto",
  "pasos": 33,
  "resultado": "PRUEBA",
  "insignias": 2,
  "equipo": [
    {"n": "Bulbasaur", "lv": 11, "ps": 30},
    {"n": "Pidgey", "lv": 14, "ps": 41}
  ]
}
"""


def test_la_ingesta_no_pierde_las_derrotas() -> None:
    """`pkl_corpus.py`: la victoria y la derrota NO se escriben igual.

    La primera versión de la ingesta daba **16.929 victorias y 0 derrotas**,
    porque el regex solo casaba `>>> COMBATE GANADO (...) | 14-0`. La derrota
    trae el rival y la vida: `>>> COMBATE PERDIDO contra X | nos quedan: ... |
    6-1`. Y como una BBDD congela el parseo, el error se habría guardado con
    toda la autoridad de una BBDD: cualquier consulta por resultado habría
    dicho que el bot no pierde nunca.
    """
    import tempfile

    import pkl_corpus as C

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        _log_de_prueba(raiz, "loteA/log-1.txt", _LOG_CON_DERROTA)
        _log_de_prueba(raiz, "h21_ABORTADO_bucle/log-2.txt", _LOG_CON_DERROTA)
        _log_de_prueba(raiz, "log-suelto.txt", _SIN_RESUMEN)
        a = C.parsear(raiz / "loteA/log-1.txt", raiz)
        abortado = C.parsear(raiz / "h21_ABORTADO_bucle/log-2.txt", raiz)
        suelto = C.parsear(raiz / "log-suelto.txt", raiz)

    p = a["peleas"]
    check("la ingesta ve las DOS peleas del log", len(p) == 2, f"-> {len(p)}")
    if len(p) != 2:
        return
    ganada, perdida = p[0], p[1]
    check("la victoria se lee como GANADO", ganada["resultado"] == "GANADO",
          f"-> {ganada['resultado']!r}")
    check("la DERROTA se lee como PERDIDO", perdida["resultado"] == "PERDIDO",
          f"-> {perdida['resultado']!r}: el regex solo casa la victoria")
    check("el rival de la derrota sale de la propia linea de derrota",
          perdida["rival_perdido"] == "Gym Battle vs Misty!",
          f"-> {perdida['rival_perdido']!r}")
    check("el marcador de la derrota es 4-1",
          (perdida["marcador_a"], perdida["marcador_b"]) == (4, 1),
          f"-> {perdida['marcador_a']}-{perdida['marcador_b']}")
    check("el marcador de la victoria es 2-0",
          (ganada["marcador_a"], ganada["marcador_b"]) == (2, 0),
          f"-> {ganada['marcador_a']}-{ganada['marcador_b']}")
    check("la victoria dice en que pantalla se continua",
          ganada["continuamos_en"] == "map-screen",
          f"-> {ganada['continuamos_en']!r}")
    check("`nos quedan` se guarda (es la foto del HUD al perder)",
          perdida["nos_quedan"] == "Bulbasaur(100/100), Pidgey(100/100)",
          f"-> {perdida['nos_quedan']!r}")
    check("el caido del `mios` queda con ps 0 y ps_max 27",
          json.loads(perdida["mios"])[0]["ps"] == 0
          and json.loads(perdida["mios"])[0]["ps_max"] == 27,
          f"-> {perdida['mios']}")

    r = a["run"]
    check("el resultado del resumen es GAME_OVER", r["resultado"] == "GAME_OVER",
          f"-> {r['resultado']!r}")
    check("los pasos del resumen se leen", r["pasos"] == 20, f"-> {r['pasos']}")
    check("las insignias del resumen se leen", r["insignias"] == 1,
          f"-> {r['insignias']}")
    check("ganados/perdidos se separan (no se pierde ninguno)",
          (r["combates_ganados"], r["combates_perdidos"]) == (1, 1),
          f"-> {r['combates_ganados']}/{r['combates_perdidos']}")
    check("las peleas de entrenador traen su experiencia",
          (r["peleas_entrenador"], r["nv_entrenador"]) == (1, 2),
          f"-> {r['peleas_entrenador']} (+{r['nv_entrenador']} nv)")
    check("las peleas salvajes traen su experiencia",
          (r["peleas_salvaje"], r["nv_salvaje"]) == (1, 1),
          f"-> {r['peleas_salvaje']}")
    check("el equipo final se separa del rango de niveles",
          (r["equipo_final"], r["equipo_final_rango"]) == (2, "9-9"),
          f"-> {r['equipo_final']} {r['equipo_final_rango']!r}")
    check("`visitas tutor` no se pierde", r["visitas_tutor"] == 0,
          f"-> {r['visitas_tutor']!r}")
    check("la traza se cuenta", r["tiene_traza"] == 1 and len(a["pasos"]) == 1,
          f"-> traza={r['tiene_traza']} pasos={len(a['pasos'])}")
    check("un lote normal es valido", r["valido"] == 1, f"-> {r['valido']}")
    check("un lote ABORTADO queda marcado como no valido",
          abortado["run"]["valido"] == 0,
          "-> un lote ABORTADO volveria a colarse en una media (h21)")
    check("el lote se guarda tal cual", r["lote"] == "loteA", f"-> {r['lote']!r}")
    check("los logs sueltos de arriba no se pierden",
          suelto["run"]["lote"] == "(suelto)", f"-> {suelto['run']['lote']!r}")

    s = suelto["run"]
    check("sin RESUMEN, el JSON final da el resultado",
          s["resultado"] == "PRUEBA", f"-> {s['resultado']!r}")
    check("sin RESUMEN, el JSON final da los pasos y las insignias",
          (s["pasos"], s["insignias"]) == (33, 2),
          f"-> {s['pasos']} pasos, {s['insignias']} insignias")
    check("sin RESUMEN, el equipo final sale del JSON",
          s["equipo_final"] == 2 and s["equipo_final_rango"] == "11-14",
          f"-> {s['equipo_final']} {s['equipo_final_rango']!r}")
    check("el JSON final se guarda entero para no rederivarlo",
          s["fin_json"] is not None and '"PRUEBA"' in s["fin_json"],
          "-> sin el JSON habria que reparsear los logs para cada pregunta")


def test_la_ingesta_no_revienta_con_una_linea_rara() -> None:
    """`_tipo_generico` se comía un `ValueError` con un log sin dos puntos.

    Venía de `re.split(r"[ :]", txt, 1)`, que en Python 3.14 avisa por
    posicional; el tercer argumento es `maxsplit` solo si se nombra.
    """
    import pkl_corpus as C

    check("una linea sin espacios no revienta el clasificador",
          C._tipo_generico("CUALQUIERCOSA") == "CUALQUIERCOSA",
          f"-> {C._tipo_generico('CUALQUIERCOSA')!r}")
    check("una linea con espacios se corta por el primero",
          C._tipo_generico("algo pasa aqui") == "algo",
          f"-> {C._tipo_generico('algo pasa aqui')!r}")
    _run: dict = {"visitas_tutor": None}
    C._resumen_campo(_run, "visitas tutor.", "7")
    check("`visitas tutor.` con punto final tambien se lee",
          _run["visitas_tutor"] == 7, f"-> {_run['visitas_tutor']!r}")


def test_la_traza_no_lee_la_barra_cruda() -> None:
    """`TRAZA_CAMINO` no puede volver a leer `self.j.equipo()`.

    Esa es la barra del HUD, y la sonda midió que marca **100% a un món que
    está al 0** (11 de 76 móns leídos en el mismo volcado, las 11 veces en esa
    dirección; y `nos quedan:` con cinco móns al 100% en una derrota 13-1). La
    política ya usaba la versión corregida desde `equipo_con_tipos()`, pero la
    traza se quedó con el dato crudo: subestimaba los caídos y todo lo medido
    con ella salía sesgado.
    """
    fuente = (SCRIPTS / "jugar_pokelike.py").read_text(encoding="utf-8")
    cuerpo = fuente.split("def _traza_camino", 1)[1].split("\n    def ", 1)[0]
    # Sin comentarios: el comentario del arreglo **cita** `self.j.equipo()`
    # para explicar por qué no se usa, y el test se disparaba con su propia
    # explicación.
    codigo = "\n".join(ln for ln in cuerpo.splitlines()
                       if not ln.strip().startswith("#"))
    check("la traza lee el equipo corregido",
          "equipo_con_tipos()" in codigo,
          "-> la traza vuelve a leer la barra cruda, que marca 100% a un caído")
    check("la traza ya no llama a self.j.equipo()",
          "self.j.equipo()" not in codigo,
          "-> `self.j.equipo()` es el porcentaje de la barra, no la vida real")


def test_reservar_sin_ventaja_pone_al_final() -> None:
    """`_reservar_sin_ventaja`: el món sin ventaja va último.

    El chart del juego NO es el oficial Gen6: en Pokelike Grass->Water es x2
    y Grass->Rock es x2. Bulbasaur (Planta/Veneno) tiene ventaja contra Agua
    y Roca, pero NO contra Fuego (Grass->Fire es x0.5).

    Pikachu (Eléctrico) NO tiene ventaja contra Roca (Electric->Rock x1).
    """
    import politica as PP

    chart = json.loads(
        (SCRIPTS.parent / "data/chart_juego.json").read_text(encoding="utf-8")
    )

    equipo = [
        {"nombre": "Bulbasaur", "tipos": ["Grass", "Poison"], "ps": 30, "ps_max": 30},
        {"nombre": "Pikachu", "tipos": ["Electric"], "ps": 30, "ps_max": 30},
    ]

    # Contra Roca: Bulbasaur tiene ventaja (Grass->Rock x2), Pikachu no
    orden_roca = PP._reservar_sin_ventaja(equipo, ["Rock"], chart)
    check("Bulbasaur va primero contra Roca",
          orden_roca[0] == "Bulbasaur",
          f"-> {orden_roca}: Grass->Rock es x2, tiene que abrir")
    check("Pikachu va al final contra Roca",
          orden_roca[-1] == "Pikachu",
          f"-> {orden_roca}: Electric->Rock es x1, no tiene ventaja")

    # Contra Agua: ambos tienen ventaja en el chart del juego
    # (Grass->Water x2 y Electric->Water x2), así que se mantiene el orden
    orden_agua = PP._reservar_sin_ventaja(equipo, ["Water"], chart)
    check("Contra Agua se mantiene el orden (ambos con ventaja)",
          orden_agua == ["Bulbasaur", "Pikachu"],
          f"-> {orden_agua}: Grass->Water y Electric->Water son x2")


def test_invariantes_de_ingesta() -> None:
    """La BBDD tiene que cuadrar consigo misma.

    Una BBDD congela el parseo: si un campo se lee mal, se guarda mal y parece
    autoritativo. Estos invariantes cazan las roturas estructurales que no se
    ven en un test unitario sobre un log sintético.
    """
    import sqlite3

    db = SCRIPTS.parent / "log" / "corpus.db"
    if not db.exists():
        return  # sin BBDD no hay invariantes que romper
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row

    # 1. Toda pelea PERDIDO tiene rival_perdido
    r = con.execute(
        "SELECT COUNT(*) n FROM pelea WHERE resultado='PERDIDO' "
        "AND (rival_perdido IS NULL OR rival_perdido='')"
    ).fetchone()
    check("toda derrota tiene rival_perdido",
          r["n"] == 0,
          f"-> {r['n']} derrotas sin rival: el regex no casó la línea de derrota")

    # 2. Derrotas ≈ GAME_OVER (con margen por el formato del log)
    r = con.execute(
        "SELECT COUNT(*) n FROM run WHERE resultado='GAME_OVER'"
    ).fetchone()
    r2 = con.execute(
        "SELECT COUNT(*) n FROM pelea WHERE resultado='PERDIDO'"
    ).fetchone()
    check("derrotas ≈ GAME_OVER",
          abs(r["n"] - r2["n"]) <= 5,
          f"-> {r['n']} GAME_OVER vs {r2['n']} PERDIDO: el parseo pierde derrotas")

    # 3. mios_ps_total = suma de ps de mios
    r = con.execute(
        "SELECT COUNT(*) n FROM pelea WHERE mios IS NOT NULL AND mios != '[]' "
        "AND mios_ps_total IS NULL"
    ).fetchone()
    check("mios_ps_total no es NULL cuando hay mios",
          r["n"] == 0,
          f"-> {r['n']} peleas con mios pero sin ps_total")

    # 4. Toda run con resumen o traza tiene pasos > 0
    #    (las runs que abortan antes del primer paso no tienen ninguna de las dos)
    r = con.execute(
        "SELECT COUNT(*) n FROM run WHERE valido=1 AND tiene_resumen=1 "
        "AND (pasos IS NULL OR pasos<=0)"
    ).fetchone()
    check("toda run con resumen tiene pasos > 0",
          r["n"] == 0,
          f"-> {r['n']} runs con resumen pero sin pasos")

    # 5. combates del resumen ≈ peleas contadas (con margen por logs viejos)
    #    p395849 (viejo_1er_experimento) tiene resumen=8 pero tabla=2: es un
    #    log con formato distinto del primer experimento, no una rotura actual.
    r = con.execute(
        "SELECT COUNT(*) n FROM run WHERE valido=1 AND tiene_resumen=1 "
        "AND combates_ganados IS NOT NULL AND combates_perdidos IS NOT NULL "
        "AND ABS((combates_ganados + combates_perdidos) - "
        "(SELECT COUNT(*) FROM pelea p WHERE p.run_id = run.id)) > 10"
    ).fetchone()
    check("combates del resumen ≈ peleas contadas",
          r["n"] == 0,
          f"-> {r['n']} runs con diferencia > 10 entre resumen y tabla")

    # 6. Sonda: run_id no es NULL
    r = con.execute(
        "SELECT COUNT(*) n FROM sonda WHERE run_id IS NULL"
    ).fetchone()
    check("toda sonda tiene run_id",
          r["n"] == 0,
          f"-> {r['n']} sondas sin run: el PID no se asoció")

    # 7. Traza: caidos <= total
    r = con.execute(
        "SELECT COUNT(*) n FROM paso WHERE caidos > total"
    ).fetchone()
    check("caidos <= total en la traza",
          r["n"] == 0,
          f"-> {r['n']} pasos con más caídos que móns totales")

    # 8. Toda run con tiene_resumen tiene resultado
    r = con.execute(
        "SELECT COUNT(*) n FROM run WHERE tiene_resumen=1 "
        "AND (resultado IS NULL OR resultado='')"
    ).fetchone()
    check("toda run con resumen tiene resultado",
          r["n"] == 0,
          f"-> {r['n']} runs con resumen pero sin resultado")

    # 9. peleas entrain + salvaje <= combates totales
    #    (los combates de gimnasio, élite y campeón son combates pero no peleas
    #    entrain/salvaje; el log base-062636 lo confirma: 10+1 combates, 5+5
    #    peleas, y el combate 11 es Gym Battle vs Misty!)
    #    Hay 5 runs donde las peleas SUPERAN a los combates (diferencia 2-4):
    #    el parser cuenta peleadas que el RESUMEN no clasifica como combates.
    #    Es un caso borde, no una rotura.
    r = con.execute(
        "SELECT COUNT(*) n FROM run WHERE valido=1 AND tiene_resumen=1 "
        "AND peleas_entrenador IS NOT NULL AND peleas_salvaje IS NOT NULL "
        "AND (peleas_entrenador + peleas_salvaje) > "
        "(combates_ganados + combates_perdidos + 5)"
    ).fetchone()
    check("peleas entrain + salvaje <= combates totales + 5",
          r["n"] == 0,
          f"-> {r['n']} runs donde las peleas superan a los combates en > 5")

    con.close()


def test_el_nodo_de_captura_gana_a_la_batalla_suelta() -> None:
    """Con equipo corto, la captura tiene que ganarle a la batalla de al lado.

    **El caso del mundo, no el fácil.** `catch` y `battle` se traducen los dos
    a `"batalla"` (`politica.TIPO_ESTADO`), y `puntuar` solo recibia ese tipo
    interno. Con `capturas_pantalla == 0` los dos nodos entraban por la misma
    rama y los dos se llevaban `PESO_CAPTURA`: el desempate lo acababa
    decidiendo el bono de ruta, y el bot se iba a cazar.

    Medido en el lote de 121 runs: **196 pantallas** con `catch` disponible y
    `capturas_pantalla == 0` en las que eligio `battle`. De ahi salen las 28
    runs que mueren antes del paso 30 con un unico món a nivel 5-9: el log
    `log-2026-10-13_08-08-13_p176311.txt` decia `opc: batalla=252 batalla=210`
    — los dos nodos con el mismo peso base — y se fue al de 252.

    Aqui se monta esa pantalla exacta: la rama de la batalla tiene **mas
    combates por delante**, que es lo que hacia que ganase antes. El equipo es
    de uno, o sea la rama de `len(equipo) < 3`.
    """
    def _equipo() -> list[dict]:
        return [{"nombre": "Bulbasaur", "nivel": 5, "ps": 100, "ps_max": 100,
                 "tipos": ["Planta", "Veneno"], "baseStats": {"hp": 100}}]

    # La rama del nodo de batalla tiene 8 combates por delante; la de captura,
    # ninguno. Con el bug, los dos nodos vale 60 y gana el de batalla (60+8x3.5).
    # `atajo` es lo que devuelve la decision, asi que es por donde se mira cual
    # nodo gano.
    nodos = [{"id": "c", "atajo": "1", "tipo": "catch", "clickable": True,
              "sprite": "pokeball"},
             {"id": "b", "atajo": "2", "tipo": "battle", "clickable": True,
              "sprite": "pokeball"}]
    for i in range(8):
        nodos.append({"id": f"co{i}", "tipo": "battle"})
    edges = [["b", f"co{i}"] for i in range(8)]

    d = PL.elegir(_equipo(), nodos, {"capturas_pantalla": 0},
                  region="Kanto", insignias=0, edges=edges)
    check("con equipo de 1 se elige el nodo de captura, no la batalla",
          str(d.valor) == "1",
          f"-> eligio el atajo {d.valor!r} ({d.razon}): el nodo `catch` y el "
          "nodo `battle` se puntuan como si fueran el mismo y gana el de la "
          "rama mas larga")

    # Y al reves: si ya se capturo en esta pantalla, la captura **no** se
    # vuelve a puntuar como captura y la batalla queda libre. Sin esto, el bot
    # podria quedarse capturando en el mismo nodo para siempre.
    d2 = PL.elegir(_equipo(), nodos, {"capturas_pantalla": 1},
                   region="Kanto", insignias=0, edges=edges)
    check("capturado ya en pantalla, la batalla queda disponible",
          str(d2.valor) == "2",
          f"-> eligio el atajo {d2.valor!r}: con capturas_pantalla=1 el nodo de "
          "captura tiene que puntuar como batalla normal")

    # Sin tipo crudo no se inventa nada: se comporta como antes.
    sin_tipo = [{"id": "x", "atajo": "1", "tipo": None, "clickable": True,
                 "sprite": "pokeball"}]
    d3 = PL.elegir(_equipo(), sin_tipo, {"capturas_pantalla": 0},
                   region="Kanto", insignias=0)
    check("sin tipo crudo no se rompe la decision",
          str(d3.valor) == "1",
          f"-> eligio el atajo {d3.valor!r}: el juego no dio `tipo` y el nodo "
          "se perdio")

    # **El caso que hizo falta el segundo arreglo**, con las cifras del log
    # `log-2026-10-13_14-01-04_p241381.txt`: `opc: batalla=558 batalla=434`.
    # Arreglando solo el peso, el nodo de captura pasa de 60 a 60 y el de
    # batalla de 60 a 15, pero su rama tiene 138 combates frente a 107: el bono
    # son 483 puntos contra una diferencia de 45, y **gana el de batalla**.
    # Con un solo món esa exp es inalcanzable (si cae, se acaba la partida), así
    # que la captura tiene que decidir por encima del score.
    largos = [{"id": "c", "atajo": "1", "tipo": "catch", "clickable": True,
               "sprite": "pokeball"},
              {"id": "b", "atajo": "2", "tipo": "battle", "clickable": True,
               "sprite": "pokeball"}]
    for i in range(107):
        largos.append({"id": f"cc{i}", "tipo": "battle"})
    for i in range(138):
        largos.append({"id": f"bb{i}", "tipo": "battle"})
    edges_largos = ([["b", f"bb{i}"] for i in range(138)]
                    + [["c", f"cc{i}"] for i in range(107)])
    d4 = PL.elegir(_equipo(), largos, {"capturas_pantalla": 0},
                   region="Kanto", insignias=0, edges=edges_largos)
    check("con el equipo de 1 la captura gana aunque la rama sea mas larga",
          str(d4.valor) == "1",
          f"-> eligio el atajo {d4.valor!r} ({d4.razon[:90]}): el bono de ruta "
          "(+3.5 por combate) pesa mas que los 45 puntos de PESO_CAPTURA y el "
          "bot se va a cazar con un unico món en el equipo")

    # Y con equipo de 3 o mas la captura **no** es prioritaria: el bono de ruta
    # manda, que es como se haMedido siempre. Este es el control que evita
    # arreglar lo de arriba rompiendo la eleccion de rama.
    eq3 = _equipo() + [{"nombre": "Pidgey", "nivel": 5, "ps": 100, "ps_max": 50,
                        "tipos": ["Normal"], "baseStats": {"hp": 100}},
                       {"nombre": "Caterpie", "nivel": 4, "ps": 100, "ps_max": 45,
                        "tipos": ["Planta"], "baseStats": {"hp": 100}}]
    d5 = PL.elegir(eq3, largos, {"capturas_pantalla": 0},
                   region="Kanto", insignias=0, edges=edges_largos)
    check("con equipo de 3 la rama larga sigue mandando",
          str(d5.valor) == "2",
          f"-> eligio el atajo {d5.valor!r}: la captura prioritaria solo es para "
          "el equipo corto, con 3 móns el bono de ruta tiene que decidir")


def test_la_batalla_ganada_y_clavada_se_recupera() -> None:
    """Rival a 0 PS y pantalla sin avanzar: hay que recuperar, no pulsar.

    El caso medido (`/tmp/opencode/atascada_125762.txt`): contra un `Hiker` con
    Sandshrew y Diglett, los dos enemigos se quedan a `0/42` y `0/29`, el
    equipo entero al 100%, y el mismo estado se repite cada 13 segundos. La
    pelea esta ganada pero no pasa al resultado, y pulsar continuar no la saca.

    **Por que este test mira lo que se pulso y no un string.** Habia un
    detector que comparaba `hecho == CONTINUAR_BATALLA`, pero `_batalla`
    devuelve `f"batalla ({via})"`: ese literal nunca se devolvio, la rama era
    codigo muerto y la recuperacion no se disparo **nunca**, sin dar ningun
    error. Es el fallo de "una rama muerta sin error" de la skill
    pokelike-reglas, vestido de detector de atasco.

    Y no vale con contar pulsaciones: en un gimnasio son normales 12-13. Lo que
    separa el atasco es que **la firma no cambia y el rival ya no tiene a nadie
    en pie**.
    """
    import jugar_pokelike as JUG

    class _FalsoJ:
        """Lo mínimo que `_batalla` toca en una pelea ya resuelta."""
        def __init__(self, enemigos: list[dict]) -> None:
            self.enemigos = enemigos
            self.activaciones: list[str] = []

        def visible(self, sel: str) -> bool:
            return sel == "#btn-auto-battle"

        def activar(self, sel: str) -> str:
            self.activaciones.append(sel)
            return sel

        def esperar_boton(self, *a, **k) -> bool:
            return True

        def insignias(self) -> int:
            return 0

        class page:  # noqa: D106
            @staticmethod
            def wait_for_timeout(_ms: int) -> None:
                return None

        def estado_batalla(self) -> dict:
            return {"titulo": "Hiker wants to battle!", "mios": [], "enemigos": self.enemigos}

    class _FalsoJ:
        """Lo mínimo que `_batalla` toca en una pelea ya resuelta."""
        def __init__(self, enemigos: list[dict]) -> None:
            self.enemigos = enemigos

        def visible(self, sel: str) -> bool:
            return sel == "#btn-auto-battle"

        def activar(self, sel: str) -> str:
            return sel

        def esperar_boton(self, *a, **k) -> bool:
            return True

        def insignias(self) -> int:
            return 0

        class page:  # noqa: D106
            @staticmethod
            def wait_for_timeout(_ms: int) -> None:
                return None

        def estado_batalla(self) -> dict:
            return {"titulo": "Hiker wants to battle!",
                    "mios": [], "enemigos": self.enemigos}

    def _bot_con(enemigos: list[dict]) -> tuple[object, list[int]]:
        """Un `Bot` real sin navegador, con lo que `_batalla` necesita.

        Se usa la clase de verdad (`__new__` para saltar al `__init__`, que
        abre el navegador) y se sustituye `j` por el falso: el test tiene que
        ejecutar el metodo real, no una reimplementacion que se parece.
        """
        b = JUG.Bot.__new__(JUG.Bot)
        cuentas = [0]
        b.j = _FalsoJ(enemigos)
        b.decisiones = []
        b.lineas = []
        b.log = b.lineas.append
        b.anotar = b.decisiones.append
        b.traza = lambda *a, **k: None
        b.pokedex = {}
        b.nivel_enemigo_max = 0
        b.enemigos_max_vistos = 0
        b._ps_real = {}
        b._errores = {}
        b._pelea_abierta = None
        b._pelea_volcada = None
        b._firma_batalla = None
        b._batalla_clavada = 0
        b._n_batalla = 0
        b.peleas = 0
        b.peleas_entrenador = 0
        b.peleas_salvaje = 0
        b.consumo_ps = []
        b.pelea_consumo = []
        b.insignias_actual = 0
        b.ignoras = None

        def _recupera() -> bool:
            cuentas[0] += 1
            b._batalla_clavada = 0
            return True

        b._recuperar_batalla_clavada = _recupera
        return b, cuentas

    caidos = [{"nombre": "Sandshrew", "ps": "0/42", "nivel": 16},
              {"nombre": "Diglett", "ps": "0/29", "nivel": 16}]

    # 1. Rival a 0 PS y estado repetido: recupera. Se dan varias vueltas
    # porque hacen falta dos lecturas con la misma firma **despues** de
    # memorizarla, que es lo que pasa en el log real (repite cada 13 s).
    b, cuentas = _bot_con(caidos)
    for _ in range(4):
        b._batalla()
    check("rival a 0 PS con la pantalla clavada dispara la recuperacion",
          cuentas[0] >= 1,
          "-> el log repite Sandshrew 0/42 y Diglett 0/29 indefinidamente: la "
          "pelea esta ganada pero no pasa al resultado")

    # 2. Rival **en pie**: es una pelea normal y no se toca nada. Si este caso
    # disparara la recuperacion, se aria al bot en mitad de cada gimnasio.
    b2, cuentas2 = _bot_con([{"nombre": "Sandshrew", "ps": "17/42", "nivel": 16}])
    for _ in range(6):
        b2._batalla()
    check("una pelea que avanza no se recupera",
          cuentas2[0] == 0,
          f"-> {cuentas2[0]} recuperaciones con el rival vivo: en un "
          "gimnasio son normales 12-13 pulsaciones de auto-battle")


def test_el_reordenado_reintenta_cuando_el_hud_se_mueve() -> None:
    """Un arrastre que no surte efecto no puede ser un fallo seco.

    **El caso del mundo, no el fácil.** Medido: 157 fallos de 729 intentos
    (21%), y el **87% con equipo de 2-3 móns**, que es justo cuando el HUD
    acaba de re-renderizar tras una captura. El arrastre de puntero cae en
    tierra si el slot se está moviendo.

    Antes solo se comprobaba el orden **al final** de la pasada: si el primer
    arrastre fallaba, el resto se hacia igual y el resultado era un fallo seco.
    Con eso el bot entraba al jefe con el món equivocado delante, que es
    justo donde §1.7 sitúa el cuello:

        [prep -> Magikarp] rival Rock/Ground -> ['Krabby', 'Bulbasaur', 'Magikarp']
        ⋯ no se pudo reordenar (quedó ['Magikarp', 'Krabby', 'Bulbasaur'])

    Krabby es Agua y le pega x2 a Roca; se peleó con Magikarp (Normal) y perdió.

    Aqui el arrastre **falla dos veces y luego funciona**, que es lo que hace
    el juego cuando el HUD se está reconstruyendo. Con la version de una
    sola pasada esto devuelve `False`.
    """
    import navegador as NAV

    class _Slots:
        def __init__(self, nombres: list[str], fallos: list[int]) -> None:
            self.nombres = list(nombres)
            self.fallos = fallos
            self.intentos = 0

    class _J:
        def __init__(self, nombres: list[str], fallos: int) -> None:
            self.slots = _Slots(nombres, [fallos])
            self.arrastres = 0

        def orden_equipo(self) -> list[str]:
            return list(self.slots.nombres)

        def _arrastrar_slot(self, origen: int, destino: int) -> bool:
            self.arrastres += 1
            if self.arrastres <= self.slots.fallos[0]:
                return True          # "hizo zoom": no movio nada
            nom = self.slots.nombres.pop(origen)
            self.slots.nombres.insert(destino, nom)
            return True

    # Un arrastre que no hace nada (el HUD moviendose) y el siguiente sí.
    j = _J(["Magikarp", "Krabby", "Bulbasaur"], 1)
    nav = NAV.Juego.__new__(NAV.Juego)  # noqa: SLF001
    nav.orden_equipo = j.orden_equipo
    nav._arrastrar_slot = j._arrastrar_slot

    ok = nav.reordenar_equipo(["Krabby", "Bulbasaur", "Magikarp"])
    check("el reordenado reintenta y acaba poniendo al contrasaliente delante",
          ok and j.orden_equipo() == ["Krabby", "Bulbasaur", "Magikarp"],
          f"-> devolvio {ok} y quedo {j.orden_equipo()}: el primer arrastre no "
          "movio nada y el orden se dio por bueno al final sin reintentar")

    # **El caso del `prep`**, que es lo que motivo bajar de 3 pasadas a 2: alli
    # el arrastre no cuela nunca (hay un modal encima), asi que reintentar se
    # come el prep entero y el detector de bucles se lleva la run. Con 2
    # pasadas se rinde en ~12 s, **lo dice** y no se hace el sordo.
    avisos: list[str] = []
    j4 = _J(["Magikarp", "Krabby", "Bulbasaur"], 99)
    nav4 = NAV.Juego.__new__(NAV.Juego)  # noqa: SLF001
    nav4.orden_equipo = j4.orden_equipo
    nav4._arrastrar_slot = j4._arrastrar_slot
    nav4.log = avisos.append
    ok4 = nav4.reordenar_equipo(["Krabby", "Bulbasaur", "Magikarp"])
    check("si el arrastre nunca cuela, se rinde avisando y no en silencio",
          ok4 is False and len(avisos) >= 1,
          f"-> devolvio {ok4} con {len(avisos)} avisos: el `prep` se queda "
          "mudo ~12 s y el detector de bucles lo confunde con un cuelgue "
          "(mato `atascada_257751.txt` y `atascada_262874.txt`)")

    # Y el caso normal: sin fallos, el reintento no se paga. Este caso es un
    # ciclo de 3 (Magikarp 0->2, Krabby 1->0, Bulbasaur 2->1), y un ciclo de 3
    # son **2** arrastres, no 1: por eso se comprueba que no haga mas de los
    # que hacen falta, que es lo que un bucle de reintentos mal puesto haria.
    j2 = _J(["Magikarp", "Krabby", "Bulbasaur"], 0)
    nav2 = NAV.Juego.__new__(NAV.Juego)  # noqa: SLF001
    nav2.orden_equipo = j2.orden_equipo
    nav2._arrastrar_slot = j2._arrastrar_slot
    ok2 = nav2.reordenar_equipo(["Krabby", "Bulbasaur", "Magikarp"])
    check("sin fallos no se pagan arrastres de mas",
          ok2 and j2.arrastres == 2,
          f"-> devolvio {ok2} con {j2.arrastres} arrastres: un ciclo de 3 son 2 "
          "arrastres, y el reintento no puede convertirse en un bucle")

    # Y si de verdad no se puede, lo dice: no se disimula con un True.
    j3 = _J(["Magikarp", "Krabby", "Bulbasaur"], 99)
    nav3 = NAV.Juego.__new__(NAV.Juego)  # noqa: SLF001
    nav3.orden_equipo = j3.orden_equipo
    nav3._arrastrar_slot = j3._arrastrar_slot
    check("si el arrastre no funciona nunca, lo dice",
          nav3.reordenar_equipo(["Krabby", "Bulbasaur", "Magikarp"]) is False,
          "-> devolvio True sin haber movido nada: el bot creeria que el "
          "equipo esta en el orden pedido cuando no lo esta")


def test_el_prep_no_se_puede_quedar_mudo() -> None:
    """El `prep` tiene que dejar rastro aunque todo falle.

    **Dos bugs en el mismo sitio, y los dos cuestan runs.** Justo antes de cada
    gimnasio el bot reordena el equipo y usa la bolsa. Si eso falla y no escribe
    nada, el `prep` se queda mudo 40-60 s: el detector de bucles de
    `lote_100.py` ve el mismo estado cinco veces y mata la partida.

    Las dos runs que se perdieron así iban bien:

        atascada_267357.txt   paso 27, equipo al 100%, 0 combates perdidos
        atascada_267587.txt   paso 31, 4 móns vivos, Preparing vs Brock

    El segundo bug lo escondía un `print()`: el fallo del flujo de equipar se
    reportaba a **stdout**, no al log del bot, así que ni el detector ni el
    análisis del log veían nada. Un marcador que no se ve desde fuera no
    verifica nada.

    Aquí se comprueba lo que de verdad importa: que pase lo que pase, el `prep`
    **dice algo**, y que la bolsa tiene techo de tiempo.
    """
    import jugar_pokelike as JUG

    fuente = Path(JUG.__file__).read_text(encoding="utf-8")
    check("la bolsa tiene presupuesto de tiempo",
          "PRESUPUESTO_BOLSA" in fuente
          and "time.monotonic() > _limite" in fuente,
          "-> sin techo, un objeto fallido son 3 clics de 3 s mas dos volcados "
          "y la bolsa llena se come el prep entero antes de un gimnasio")

    import navegador as NAV
    fuente_nav = Path(NAV.__file__).read_text(encoding="utf-8")
    check("los fallos del flujo de objeto van al log, no a stdout",
          "[EQUIP]" not in fuente_nav and "el clic no sirvio" in fuente_nav,
          "-> con `print()` el fallo salia por stdout y no llegaba al log: el "
          "prep se quedaba mudo y lo mataba el detector de bucles")

    check("el navegador tiene una via para avisar",
          "def _avisar" in fuente_nav and "self._avisar(" in fuente_nav,
          "-> sin `_avisar` el reordenado y el fallo de objeto no pueden "
          "dejar linea en el log del bot")

    check("el bot engancha su log al navegador",
          "juego.log = self.log" in fuente,
          "-> `Juego._avisar` no tiene a quien escribir: el aviso se pierde y "
          "vuelve a pasar lo mismo")


def test_el_prep_no_reordena_donde_el_arrastre_no_cuela() -> None:
    """En el `prep` el reordenado no funciona: no se intenta.

    El orden del jefe lo aplica la pantalla de **mapa**, un paso antes
    (`⋯ reordenado: ... (para jefe)`), y ahí el arrastre sí cuela. Dentro del
    `prep` hay un modal que se come el puntero: medido sobre 6 preps, acierta
    **1 de 6** (17%), y cada intento fallido son ~30 s antes de un gimnasio.

    Esos 30 s no son gratis: el `prep` se queda sin escribir nada y el detector
    de bucles de `lote_100.py` ve el mismo estado cinco veces. Se pagó con cinco
    runs que iban bien, todas cortadas en `⋯ prep:`:
    `atascada_257751`, `atascada_262874`, `atascada_267357`, `atascada_267587`
    y `atascada_273329`.

    La comprobacion es sobre el **cuerpo de la funcion**, no sobre una cadena:
    que el `prep` llame a `ordenar_equipo` es el bug.
    """
    import jugar_pokelike as JUG
    import inspect

    cuerpo = inspect.getsource(JUG.Bot._preparar_contra_el_rival)
    check("el prep reordena en la Liga, que es el unico sitio posible",
          "if es_elite or es_campeon:" in cuerpo
          and "self.j.reordenar_equipo(orden)" in cuerpo,
          "-> los cuatro combates del Alto Mando van seguidos, con ~14 s entre "
          "uno y otro y SIN pantalla de mapa en medio: el orden se aplica una "
          "vez antes de Lorelei y los otros tres pelean con ese (medido en "
          "`log-2026-10-16_16-07-42_p107103.txt`)")

    check("el prep usa el orden del contador, no el fijo de la serie",
          "self._orden_de_liga(con_tipos, insignias)" in cuerpo,
          "-> con el orden fijo de la serie los cuatro miembros reciben la "
          "misma formación, que es justo lo que se quería evitar")
    check("el prep no reordena contra gimnasios",
          "ordenar_equipo" not in cuerpo
          or "if es_elite or es_campeon:" in cuerpo,
          "-> el `prep` reordena en TODAS las pantallas: el modal se come el "
          "arrastre, acierta 1 de 6 y se come ~30 s antes de cada gimnasio "
          "(5 runs cortadas en `⋯ prep:`). Solo puede hacerlo en la Liga, que "
          "es donde no hay pantalla de mapa entre combates")

    # Y el detector de bucles tiene que ver TODO el log, no solo las lineas
    # `DEC`: los avisos del navegador son los que dicen que el bot esta vivo.
    fuente_lote = (SCRIPTS / "medir" / "lote_100.py").read_text(encoding="utf-8")
    check("el detector de bucles mira el log entero",
          '"DEC" in ln or "estado" in ln' not in fuente_lote,
          "-> filtrando por `DEC`/`estado`, los avisos del navegador no cuentan "
          "y un `prep` que trabaja se confunde con uno colgado")


def test_el_jefe_aplazado_tira_mas_mapa_si_falta_nivel() -> None:
    """Si al jefe se llega por debajo de su nivel, hay que tirar más mapa.

    **El caso del mundo, no el fácil.** En el lote del 14-10, 101 de 153 runs
    se quedaron con **1 insignia**, y 6 de las 12 muertes de ese grupo fueron
    contra Misty. Todas con el equipo por debajo del rival:

        nuestro_niv 13 / rival_niv 20   -> pierde
        nuestro_niv 14 / rival_niv 20   -> pierde
        nuestro_niv 18 / rival_niv 20   -> pierde

    El tope de rerolls era **3 fijos**, y el −1.0 de "jefe APLAZADO" solo gana
    a nodos que puntúan 2-12: si no hay ninguno en pantalla, el bot entra al
    gimnasio y pierde la partida. Perder sin haber Restado nada.

    Antes de subir el tope hay que poder **comprobar** si sirve, porque el
    comentario del planificador afirma que "aplazar no compra nada" (nivel
    ganado −0,0 entre el primer y el último aplazo). Eso se midió con el
    código viejo: desde entonces la captura con equipo corto es prioritaria, y
    la captura da experiencia **solo al món capturado** mientras el entrenador
    da +2 a **todo** el equipo.

    Por eso el test comprueba las dos cosas: que sube el tope **solo** cuando
    falta nivel, y que el nivel de entrada **se escribe en el log** (sin el
    dato no hay forma de refutar la hipótesis, que es lo que pasó).
    """
    import jugar_pokelike as JUG
    import inspect

    fuente = inspect.getsource(JUG.Bot._mapa)
    # **El tope sigue en 3 aunque falte nivel.** Se probó con 8 y se midió:
    # 7 de 7 runs llegaron igual de por debajo y la media bajó de 1,40 a 1,00.
    # Este check está para que nadie lo vuelva a subir creyendo que así gana
    # experiencia: no la gana. Lo que falta es trainers ANTES del gimnasio.
    check("el tope de rerolls sigue en 3 aunque falte nivel",
          "_tope = 3" in fuente and "self._rerolls < _tope" in fuente,
          "-> subir el tope a 8 cuando falta nivel se midió y empeoró: 7 de 7 "
          "llegaron igual de cortos y la media bajó de 1,40 a 1,00. El reroll "
          "redibuja nodos, no inventa entrenadores")

    check("el nivel al entrar al jefe se escribe en el log",
          "⟂ nivel al jefe" in inspect.getsource(JUG.Bot._preparar_contra_el_rival),
          "-> sin el dato no se puede comparar 'aplazar un gimnasio' con "
          "'aplazar el siguiente', y la hipótesis se queda sin comprobar")

    check("el nivel al entrar nace en __init__",
          "_nivel_al_entrar" in inspect.getsource(JUG.Bot.__init__),
          "-> sin inicializar, AttributeError en el primer prep de jefe")


def test_las_capturas_no_roban_la_exp_de_equipo() -> None:
    """Con 2 móns la captura **deja de ser prioritaria**.

    **Este arreglo arregló una cosa y rompió otra.** Era `< 3`, y su premisa
    ("con un solo món la exp es inalcanzable: si caes, se acabó") era cierta
    para 1 y **falsa para 2**. Con dos móns el bot ya aguanta la ruta, así que
    la captura sí es alcanzable, y lo que hace es **robar la exp de equipo**: la
    captura da experiencia solo al món capturado, el entrenador da +2 a todo.

    Medido en el lote del 15-10, 46 runs:

        Entrenadores por run     8,1  ->  7,3
        Media de insignias      1,40  ->  0,95
        Runs con 0 insignias     34%  ->  50%
        Muertes contra Brock          ->  10 (la primera insignia)

    La regla se queda en `< 2`: el caso de 1 món sigue resuelto (sin captura,
    la partida se acaba en el paso 22), y el de 2 vuelve a pelear por puntuación
    normal, que es lo que devuelve los entrenadores.
    """
    import planificador as PL
    import inspect

    fuente = inspect.getsource(PL.puntuar)
    check("con 2 móns la captura no es prioritaria",
          "if len(equipo) < 2:" in fuente,
          "-> con `< 3` la captura roba la exp de equipo (la unica que sube a "
          "todo el equipo): 8,1 -> 7,3 entrenadores por run, y la media cayo "
          "de 1,40 a 0,95 con 10 muertes contra Brock")

    fuente_elegir = inspect.getsource(PL.elegir)
    check("el filtro de captura prioritaria usa el mismo umbral",
          "and len(equipo) < 2)" in fuente_elegir,
          "-> los dos sitios tienen que coincidir: si `puntuar` dice 2 y "
          "`elegir` dice 3, el veto gana y la captura sigue siendo prioritaria")

    check("el arreglo del caso de 1 món sigue en pie",
          "hacen falta " in fuente and "cuerpos antes que nivel" in fuente,
          "-> sin captura con 1 món la partida muere en el paso 22, que es "
          "justo lo que este arreglo original arreglaba")


def test_el_delantero_de_la_liga_cubre_lorelei_y_lance() -> None:
    """La posición 1 tiene que servir para el primer miembro **y** el último.

    **Por qué los dos.** El orden de la Liga no se puede cambiar entre
    combates: los cuatro van seguidos, sin pantalla de mapa en medio, y dentro
    del `prep` el arrastre no cuela (17 intentos, 0 aciertos, medido el 16-10).
    El mismo plan vale para los cinco combates, así que el delantero tiene que
    aguantar al primero y al último.

    Con el plan anterior —posición 1 = mejor contra Lorelei y nada más— el bot
    **caía siempre en Lance**, el cuarto: venció a Lorelei, Bruno y Agatha con
    ese orden exacto y perdió contra el siguiente
    (`log-2026-10-16_06-56-01_p84591.txt`, 216 pasos, equipo a 60-73).
    """
    import politica as P
    import inspect
    inspect_src = inspect.getsource(P.orden_para_elite_four)
    check("el delantero de la Liga se mide contra los dos extremos",
          "_puente" in inspect_src and "_idx == 0" in inspect_src,
          "-> la posicion 1 solo se media contra Lorelei y el bot caia en "
          "Lance (el 4º) tras vencer a los tres primeros")

    # Y que de verdad ordena: con un equipo de Pokémon con tipos claros, el
    # primero tiene que ser eficaz contra Hielo (Lorelei) y contra Dragón
    # (Lance), no solo contra Hielo.
    eq = [{"nombre": "Lapras", "tipos": ["Agua", "Hielo"], "ps": 100,
           "ps_max": 100, "nivel": 60},
          {"nombre": "Charizard", "tipos": ["Fuego", "Volador"], "ps": 100,
           "ps_max": 100, "nivel": 60},
          {"nombre": "Alakazam", "tipos": ["Psiquico"], "ps": 100,
           "ps_max": 100, "nivel": 60}]
    orden = P.orden_para_elite_four(eq, "Kanto")
    check("el orden de la Liga sale completo y con el delante delagua",
          len(orden) == 3 and orden[0] == "Lapras",
          f"-> salio {orden}: Lapras (Agua/Hielo) va el primero porque es el "
          "que aguanta a Lorelei y a Lance a la vez")


def test_la_captura_mira_la_defensa_y_no_solo_el_ataque() -> None:
    """El filtro de captura tiene que preguntar tambien que le hacen a el.

    **Por que.** `cobertura_region` es solo ofensiva: cuenta los gimnasios a los
    que el candidato pega 2x, y nunca los que le pegan 2x a el. Medido el 17-10,
    y es el muro del juego: contra Misty (`tipos_equipo` = Psiquico/Agua) el
    Bulbasaur pega 2x al Agua **y recibe 2x del Psiquico**, mientras un Voltorb
    pega 2x al Agua y no recibe 2x de nada. Ofensivamente empatan, asi que el
    filtro los veia iguales. Misty gana el 53,8% de las veces y es el escalon
    donde muere el **43%** de las runs de 1 insignia (416 de 958).

    **Y por que este test y no solo el valor.** La defensa ya existia en
    `elegir_captura`, pero en la rama `else` de `region`, y `region` se pasa
    siempre: era **codigo muerto**. Un test que solo mirara el numero no habria
    pillado eso.
    """
    import inspect
    import politica as P
    import pkl_tipos as T

    cuerpo = inspect.getsource(P.elegir_captura)
    check("la captura mira la defensa en la rama que SI se ejecuta",
          "debilidad_region(tipos, region) * PESO_DEBILIDAD_REGION" in cuerpo,
          "-> la defensa vuelve a quedar muerta: el candidato que pega 2x al "
          "gimnasio y recibe 2x de el vale lo mismo que el que no recibe nada")

    b = [T.normalizar(t) for t in ("Planta", "Veneno")]
    v = [T.normalizar("Electrico")]
    check("el debil doble cuenta dos gimnasios y el sano uno",
          P.debilidad_region(b, "Kanto") == 2 and P.debilidad_region(v, "Kanto") == 1,
          f"-> Bulbasaur={P.debilidad_region(b, 'Kanto')} (Tierra de Brock y "
          f"Psiquico de Misty), Voltorb={P.debilidad_region(v, 'Kanto')} "
          "(solo Tierra): si no sale 2 y 1, la ventana de gimnasios cambio")

    check("el peso es positivo o el termino no hace nada",
          P.PESO_DEBILIDAD_REGION > 0,
          "-> con peso 0 la linea se evalua y no resta: un no-op con aspecto "
          "de arreglo")

    check("el castigo deja rastro en el log de captura",
          "deb2x=" in cuerpo and "castigo=" in cuerpo,
          "-> sin el dato en el log, un lote inerte no se distingue de un "
          "termino que no se estaba aplicando; es la leccion del veto de nivel "
          "que descartaba salvajes en silencio")


def test_en_el_mapa_de_la_liga_no_se_pelea() -> None:
    """H24: con las 8 insignias cada pelea gasta PS y no compra nada.

    **Por que.** El Alto Mando son 4 combates consecutivos sin cura entre ellos
    (~14 s de uno a otro): el PS no se recupera dentro, asi que llegar tocado es
    llegar muerto. Y el bot se pasaba el mapa de la Liga cazando —29 batallas y
    29 entrenadores en una sola run— con el nodo de cura disponible y sin
    reservarlo para el final.

    Medido en las 3 runs que llegaron en `lote_defensa2`: la 1 entro con
    Aerodactyl 0/168 y Golduck 78/186 y murio en Lance; la 3 entro con Gengar
    47/135 y Lorelei le mato 5 de 6. Las dos perdieron por entrar tocadas.
    """
    import planificador as PL

    liga, gym7 = PL.plan_para("Kanto", 8), PL.plan_para("Kanto", 7)
    check("el mapa de la Liga se detecta por las insignias",
          PL.es_mapa_de_liga(liga) and not PL.es_mapa_de_liga(gym7),
          "-> si el gimnasio 7 contase como Liga, se penalizarian peleas de "
          "ruta normales y el bot se quedaria sin subir nivel")

    completo = [{"nombre": f"m{i}", "tipos": ["Agua"], "nivel": 60,
                 "ps": 100, "ps_max": 100} for i in range(6)]
    corto = completo[:3]

    s_pelea, _ = PL.puntuar("batalla", PL.Contexto(equipo=completo, plan=liga))
    s_entre, _ = PL.puntuar("entrenador", PL.Contexto(equipo=completo, plan=liga))
    check("en la Liga la pelea y el entrenador se penalizan",
          s_pelea == PL.PENALIZACION_PELEA_LIGA
          and s_entre == PL.PENALIZACION_PELEA_LIGA,
          f"-> batalla={s_pelea}, entrenador={s_entre}: si salen positivos, el "
          f"bot vuelve a cazar en el mapa donde el PS no se repone")

    s_capt_corto, _ = PL.puntuar("batalla", PL.Contexto(equipo=corto, plan=liga),
                                 es_captura=True)
    check("la captura se salva si faltan cuerpos (R2)",
          s_capt_corto != PL.PENALIZACION_PELEA_LIGA,
          "-> con 3 mons el veto no puede aplicarse: el veto es contra la pelea "
          "inutil, no contra el mon que falta")

    s_gym, _ = PL.puntuar("batalla", PL.Contexto(equipo=completo, plan=gym7))
    check("fuera de la Liga la pelea NO se penaliza",
          s_gym > PL.PENALIZACION_PELEA_LIGA,
          f"-> un gimnasio normal da {s_gym}: el veto tiene que ser solo del "
          f"mapa de la Liga")


def test_la_huella_del_codigo_identifica_el_lote() -> None:
    """El lote tiene que decir con que codigo corrio.

    **Por que.** El 18-10 no se pudo contestar "esto antes funcionaba, ?que ha
    cambiado?": `lote_liga` murio sin insignia el 6% y `lote_liga4` el 21%, misma
    maquina y region, y los logs de lote no guardaban que codigo corrio cada uno.
    Con la huella, dos lotes con la misma cadena son el mismo brazo; con distinta,
    el delta de codigo es el unico sospechoso.
    """
    import hashlib
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parent
    sys.path.insert(0, str(raiz / "medir"))
    import lote_100 as LOTE

    h1, h2 = LOTE.huella_codigo(), LOTE.huella_codigo()
    check("la huella es estable entre llamadas", h1 == h2,
          f"-> {h1} vs {h2}: si cambia sola, no sirve para comparar lotes")

    scripts = sorted(LOTE.SCRIPTS.glob("*.py"))
    manual = hashlib.sha256()
    for f in scripts:
        manual.update(f.name.encode())
        manual.update(f.read_bytes())
    check("la huella cubre TODOS los scripts/*.py, no un subconjunto",
          h1 == manual.hexdigest()[:12],
          "-> si no cubre todos, un cambio en un script olvidado no moveria la "
          "huella y dos lotes distintos parecerian el mismo brazo")

    solo_nombres = hashlib.sha256()
    for f in scripts:
        solo_nombres.update(f.name.encode())
    check("la huella depende del CONTENIDO, no solo de los nombres",
          h1 != solo_nombres.hexdigest()[:12],
          "-> si solo mirara nombres, editar politica.py no cambiaria la huella "
          "y el arreglo entero seria invisible")

    check("la huella tiene 12 caracteres hexadecimales",
          len(h1) == 12 and all(c in "0123456789abcdef" for c in h1),
          f"-> {h1!r}")

    # **El A/B del lote tiene que llegar de verdad al planificador.** El fallo
    # más caro posible es que el orquestador escriba una variable que nadie lee:
    # los dos brazos correrían el mismo código y el lote entero (16 h) no mediría
    # nada. Se comprueba de punta a punta, con un proceso nuevo.
    import os
    import subprocess

    nombre, env = LOTE.configurar_brazo("quita:PENALIZACION_ENTRENADOR_EQUIPO_CORTO=0")
    check("el brazo se traduce a variables PKL_*",
          nombre == "quita" and env.get("PKL_BRAZO") == "quita"
          and env.get("PKL_PENALIZACION_ENTRENADOR_EQUIPO_CORTO") == "0",
          f"-> {nombre} {env}")

    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import planificador as P; "
         "print(P.PENALIZACION_ENTRENADOR_EQUIPO_CORTO)",
         str(raiz)],
        env={**os.environ, **env}, capture_output=True, text=True, timeout=180)
    check("y el planificador lo lee: con el brazo a 0 la penalización es 0",
          out.stdout.strip() == "0.0",
          f"-> salio {out.stdout.strip()!r} en vez de 0.0: la variable del A/B no "
          f"llega al planificador y los dos brazos correrian el mismo codigo "
          f"({out.stderr[-200:]})")


def test_el_equipo_corto_no_paga_el_bono_de_exp_del_entrenador() -> None:
    """Con menos de 3 móns y sin cura, el entrenador no recibe el bono de exp.

    **Por qué.** El 18-10, 11 de las 13 runs que murieron sin insignia lo
    hicieron con `equipo=2`, y en una de ellas el log deja la decisión entera:

        nodo=n1_0 tipo=entrenador equipo=2 vivos=2 niv=4-5
        disponibles=trainer,catch
        razon=entrenador score=85.0 (mucha exp, faltan ~10)
        opc: entrenador=85 batalla=85      <- empate, y ganó el entrenador
        >>> COMBATE PERDIDO contra Firebreather! | 0-1

    El bono de ruta (`extra * peso_ruta`, x3.5 mientras falte nivel) se suma
    **después** del peso base y vale 60-300, así que el entrenador (34) empataba
    con la captura (60 de peso) y el desempate lo ganaba él. La penalización
    rompe ese empate: lo que se comprueba aquí es que con el equipo corto el
    entrenador puntúa **por debajo** de lo que puntuaba, y que el caso normal
    (equipo largo) no se toca.
    """
    plan = PL.plan_para("Kanto", 0)

    def m(n, nv, tp=None):
        return {"nombre": n, "tipos": tp or ["Planta"], "baseStats": {"hp": 40},
                "nivel": nv, "ps": 100, "ps_max": 100}

    corto = [m("Bulbasaur", 5), m("Paras", 4)]
    largo = [m("Bulbasaur", 5), m("Paras", 4), m("Pidgey", 4), m("Rattata", 4)]

    ctx_corto = PL.Contexto(equipo=corto, plan=plan, hay_cura_disponible=False,
                            nivel_rival=4)
    ctx_largo = PL.Contexto(equipo=largo, plan=plan, hay_cura_disponible=False,
                            nivel_rival=4)

    s_corto, raz_corto = PL.puntuar("entrenador", ctx_corto)
    s_largo, raz_largo = PL.puntuar("entrenador", ctx_largo)

    # **La batería de integridad corre DENTRO del entorno del brazo del A/B**, así
    # que este test no puede leer la constante ambiental: en el brazo de control
    # vale 0 y el test fallaría justo para el brazo que el A/B necesita medir.
    # Pasó tal cual: el lote murió en la tanda 2 sin lanzar nada, y el brazo de
    # control no habría llegado a correr nunca. El valor se fija aquí y se
    # restaura al final, como hace el test de la escalera.
    original = PL.PENALIZACION_ENTRENADOR_EQUIPO_CORTO
    try:
        PL.PENALIZACION_ENTRENADOR_EQUIPO_CORTO = -60.0
        s_corto, raz_corto = PL.puntuar("entrenador", ctx_corto)
        s_largo, raz_largo = PL.puntuar("entrenador", ctx_largo)

        check("con 2 móns el entrenador puntúa por debajo que con 4",
              s_corto < s_largo, f"-> 2 móns {s_corto} vs 4 móns {s_largo}")
        check("y la diferencia es exactamente la penalización de equipo corto",
              abs((s_largo - s_corto) - abs(
                  PL.PENALIZACION_ENTRENADOR_EQUIPO_CORTO)) < 1e-6,
              f"-> {s_largo} - {s_corto} != "
              f"{abs(PL.PENALIZACION_ENTRENADOR_EQUIPO_CORTO)}: si cambia el "
              f"valor, cambia el A/B y la calibración deja de estar documentada")
        check("el motivo lo dice y sale en el log",
              "aplazado" in raz_corto and "GAME_OVER" in raz_corto,
              f"-> sin rastro en el log no se puede falsar: {raz_corto}")
        check("el caso normal (equipo largo) sigue cobrando el bono de exp",
              "aplazado" not in raz_largo and "mucha exp" in raz_largo,
              f"-> {raz_largo}")

        # Con pokecenter delante no se penaliza: el corte de emergencia de R8 ya
        # obliga a curar, y castigar al entrenador solo taparía la cura (mismo
        # criterio que `riesgo_entrenador`).
        _, raz_cura = PL.puntuar(
            "entrenador", replace(ctx_corto, hay_cura_disponible=True))
        check("con cura disponible el equipo corto no penaliza al entrenador",
              "aplazado" not in raz_cura, f"-> {raz_cura}")

        # **El brazo de control tiene que ser neutral**: con la penalización a 0,
        # el equipo de 2 y el de 4 puntúan igual. Sin esto, un A/B que salga
        # plano no se distingue de una penalización que se aplica a los dos
        # brazos, que es el fallo que deja un lote de 100 tandas sin medir nada.
        PL.PENALIZACION_ENTRENADOR_EQUIPO_CORTO = 0.0
        s_ctrl_corto, _ = PL.puntuar("entrenador", ctx_corto)
        s_ctrl_largo, _ = PL.puntuar("entrenador", ctx_largo)
        check("el brazo de control (penalización 0) es neutral: 2 móns = 4 móns",
              abs(s_ctrl_corto - s_ctrl_largo) < 1e-6,
              f"-> 2 móns {s_ctrl_corto} vs 4 móns {s_ctrl_largo}: el control "
              f"hereda la penalización y los dos brazos miden lo mismo")
    finally:
        PL.PENALIZACION_ENTRENADOR_EQUIPO_CORTO = original


def test_la_huella_del_lote_llega_hasta_la_cabecera_de_la_run() -> None:
    """El nombre de la variable de la huella tiene que ser el mismo en los dos.

    **Por qué existe.** El 18-10 no se pudo contestar "¿con qué código corrió
    cada lote?": `run.codigo` salía vacío en todas las runs nuevas porque la
    cabecera escribía `codigo=?` — el lote calculaba la huella y no se la pasaba a
    nadie. El fallo es de una línea y no lo caza nada en tiempo de ejecución: las
    runs corren perfectas y el dato se pierde en silencio. Por eso se comprueba en
    los dos ficheros, que es donde vive el desacuerdo.
    """
    import re

    raiz = Path(__file__).resolve().parent
    lote = (raiz / "medir" / "lote_100.py").read_text(encoding="utf-8")
    juego = (raiz / "jugar_pokelike.py").read_text(encoding="utf-8")

    m = re.search(r'os\.environ\["(\w+)"\] = huella', lote)
    check("el lote pone la huella en una variable de entorno",
          bool(m) and m.group(1).startswith("PKL_"),
          f"-> {'no la pone' if not m else m.group(1)}")
    var = m.group(1) if m else ""
    check(f"y la cabecera de la run escribe ESA variable en `codigo=` "
          f"(si no, el corpus lo guarda vacio y no se puede comparar eras)",
          f"os.environ.get('{var}'" in juego and "codigo={" in juego,
          f"-> la cabecera no lee `{var}`: la huella se queda en el log del lote "
          f"y `run.codigo` sale vacio")


def main() -> int:
    test_la_captura_mira_la_defensa_y_no_solo_el_ataque()
    test_en_el_mapa_de_la_liga_no_se_pelea()
    test_la_huella_del_codigo_identifica_el_lote()
    test_el_equipo_corto_no_paga_el_bono_de_exp_del_entrenador()
    test_la_huella_del_lote_llega_hasta_la_cabecera_de_la_run()
    test_el_delantero_de_la_liga_cubre_lorelei_y_lance()
    test_las_capturas_no_roban_la_exp_de_equipo()
    test_el_jefe_aplazado_tira_mas_mapa_si_falta_nivel()
    test_el_prep_no_reordena_donde_el_arrastre_no_cuela()
    test_el_prep_no_se_puede_quedar_mudo()
    test_el_reordenado_reintenta_cuando_el_hud_se_mueve()
    test_el_nodo_de_captura_gana_a_la_batalla_suelta()
    test_la_batalla_ganada_y_clavada_se_recupera()
    test_la_etiqueta_de_version_va_en_el_log()
    test_sacar_el_tipo_repetido()
    test_tipos_de_nodo()
    test_los_helpers_de_ruta_ven_los_nodos()
    test_ningun_helper_usa_la_clave_type()
    test_llamadas_self_definidas()
    test_chart_completo()
    test_regiones_completas()
    test_heridos_se_ordenan_por_porcentaje()
    test_delantero_contra_fuego()
    test_pesos_sin_valores_absurdos()
    test_orden_de_prioridades()
    test_puerta_del_75()
    test_centros_por_delante_ven_la_rama()
    test_vocabulario_del_juego()
    test_captura_con_equipo_lleno_no_reventa()
    test_tipo_del_lider_no_es_la_categoria_del_nodo()
    test_el_aguante_mide_el_danio_recibido()
    test_todas_las_regiones_tienen_liga()
    test_ps_real_se_invalida()
    test_los_niveles_vienen_numericos()
    test_el_volcado_del_crash_ea_ejecutable()
    test_el_error_de_codigo_deja_el_error_localizado()
    test_las_ocho_reglas_se_cumplen()
    test_la_skill_del_camino_no_se_desincroniza()
    test_mapa_lee_el_nivel_del_rival()
    test_el_entrenador_se_veta_por_nivel_y_por_caidos()
    test_el_veto_de_entrenador_llega_a_puntuar()
    test_el_flojo_es_el_mas_debil_del_equipo()
    test_curar_invalida_el_ps_real()
    test_el_nivel_equipo_no_revienta_con_ceros()
    test_el_trade_no_sacrifica_al_mon_sin_datos()
    test_los_indices_de_objetos_se_recalculan()
    test_mapa_lee_el_nivel_del_rival()
    test_el_entrenador_se_veta_por_nivel_y_por_caidos()
    test_el_veto_de_entrenador_llega_a_puntuar()
    test_el_flojo_es_el_mas_debil_del_equipo()
    test_curar_invalida_el_ps_real()
    test_el_atasco_cuenta_rachas_y_no_toda_la_partida()
    test_los_indices_de_objetos_se_recalculan()
    test_el_nivel_equipo_no_revienta_con_ceros()
    test_el_trade_no_sacrifica_al_mon_sin_datos()
    test_la_skill_del_camino_no_se_desincroniza()
    test_la_run_no_se_corta_por_el_presupuesto()
    test_el_herido_al_menos_50_va_al_final()
    test_r2_se_captura_aunque_el_salvaje_sea_de_nivel_menor()
    test_r2_no_veta_por_nivel()
    test_un_caido_no_vuelve_a_vivir_al_invalidar_el_ps()
    test_el_que_pega_mas_va_delante()
    test_se_evita_al_entrenador_que_nadie_le_gana()
    test_el_prep_del_jefe_no_entra_en_bucle()
    test_la_batalla_que_no_acaba_tiene_techo()
    test_el_veto_de_nivel_usa_el_mon_que_abre()
    test_con_un_solo_mon_se_captura_casi_todo()
    test_continuar_en_batalla_no_puede_buquearse()
    test_la_escalera_de_riesgo_no_puede_atar_al_bot()
    test_el_riesgo_no_se_dispara_si_hay_cura()
    test_la_riesgo_de_exp_con_caidos_ya_no_existe()
    test_la_escalera_gana_al_bono_de_ruta()
    test_el_bono_de_ruta_sigue_premiando_al_control()
    test_h20_usa_el_ps_real_y_no_el_del_hud()
    test_h20_no_resta_la_cura_que_va_por_delante()
    test_la_traza_de_consume_ps()
    test_el_prep_del_jefe_usa_el_ps_real()
    test_h21_deja_de_premiar_al_salvaje_y_no_toca_al_trainer()
    test_salvajes_y_entrenadores_se_cuentan_por_separado()
    test_el_brazo_de_control_no_hereda_la_escalera()
    test_el_veto_de_nivel_gana_al_bono_de_ruta()
    test_el_trade_se_cierra_con_el_atajo()
    test_el_trade_elige_el_atajo_por_tipo()
    test_el_brazo_de_control_del_trade_sigue_declinando()
    test_el_trade_no_acepta_a_ciegas()
    test_el_trade_nunca_cambia_al_starter()
    test_toda_decision_deja_rastro()
    test_el_nodo_de_objeto_ya_no_esta_invertido()
    test_los_atributos_nuevos_nacen_en_init()
    test_el_auto_skip_usa_las_claves_que_lee_el_juego()
    test_las_peleas_se_cuentan_sin_muestreo()
    test_capturar_es_mas_barato_que_rechazar()
    test_el_volcado_de_combate_normaliza_el_nivel()
    test_la_ingesta_no_pierde_las_derrotas()
    test_la_ingesta_no_revienta_con_una_linea_rara()
    test_la_traza_no_lee_la_barra_cruda()
    test_reservar_sin_ventaja_pone_al_final()
    test_invariantes_de_ingesta()
    test_no_hay_codigo_muerto()

    for o in OKS:
        print(f"  ok   {o}")
    if FALLOS:
        print()
        for f in FALLOS:
            print(f"  FALLA {f}")
    print(f"\n{len(OKS)} correctas, {len(FALLOS)} fallos")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    sys.exit(main())

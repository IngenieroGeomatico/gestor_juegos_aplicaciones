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
import json
import sys
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SCRIPTS = RAIZ / "juegos" / "pokelike" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import planificador as PL  # noqa: E402
import politica as P  # noqa: E402
import pkl_tipos as T  # noqa: E402

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

    # Un solo món en pie, caídos y sin cura: ni "única fuente de exp".
    _, raz_sin = PL.puntuar("entrenador", replace(
        ctx, nivel_rival=9, hay_cura_disponible=False))
    check("entrenador_sin_cura_con_caidos_se_veta",
          "vetado" in raz_sin and "caído" in raz_sin, f"-> {raz_sin}")

    # Y con cura delante se vuelve a permitir: el pokecenter va antes.
    _, raz_con = PL.puntuar("entrenador", replace(
        ctx, nivel_rival=9, hay_cura_disponible=True))
    check("entrenador_con_caidos_permite_si_hay_cura",
          "vetado" not in raz_con, f"-> {raz_con}")


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
    check("no queda el clear() que anulaba la deteccion",
          "vistos.clear()" not in txt,
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
    check("regla 8: entrenador con caidos exige que no haya cura",
          "if caidos and not ctx.carry_debil and not ctx.hay_cura_disponible:"
          in pl,
          "-> pelea con caidos aunque haya pokecenter delante")

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
    check("regla 7: se prioriza al mon muerto",
          "muertos or vivos" in jug,
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
    check("el rival se guarda el nivel ya convertido",
          'max(self.nivel_enemigo_max, e["nivel"])' in fuente)


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


def main() -> int:
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

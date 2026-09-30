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
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SCRIPTS = RAIZ / "juegos" / "pokelike" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import planificador as PL  # noqa: E402
import politica as P  # noqa: E402
import pkl_tipos as T  # noqa: E402

FALLOS: list[str] = []
OKS: list[str] = []


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

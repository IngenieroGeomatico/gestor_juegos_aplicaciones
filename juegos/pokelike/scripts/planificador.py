"""Planificador de run: la política que gana la región.

Todo lo que hay aquí sale de medir ~40 partidas, no de teoría. Las tres
conclusiones que gobiernan el diseño:

**1. Se muere en el gimnasio, no en los combates sueltos.** Todas las runs
terminaban en `GAME_OVER` con `0 perdidas`. El equipo llegaba a la puerta del
líder con 1-3 móns por debajo de nivel y con caídos. Los combates sueltos se
ganan; el jefe es donde la run se decide.

**2. El jefe es una salida forzada.** En `d2` y `d5` las únicas opciones del
mapa eran `[jefe]`: no se puede no-entrar. `listo_para_jefe` marcaba "no entres"
y el bot entraba igual, a ciegas. La puerta correcta no es "no entres", es
"entra con lo que tengas, y hazlo con el mejor orden posible".

**3. El listón exacto al nivel del rival es inalcanzable.** Contra Erika
(nivel 32) el bot llegó a 31 y el filtro dijo "no preparado" porque exigía 32.
Un margen de 2-3 niveles por debajo es la zona real de victoria (el rival gana
por tipos, no por nivel, cuando hay un 2x). El listón debe ser un rango, no un
número exacto.

El planificador no reemplaza `politica`: la usa para los datos (niveles de
jefe, tipos del rival, chart). Solo decide **qué nodo del mapa visitar** y con
**qué orden de equipo**, que es donde estaban los fallos.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import politica as P  # noqa: E402
import pkl_tipos as T  # noqa: E402


# --------------------------------------------------------------- chart real
_chart_cache: dict | None = None


def chart() -> dict:
    global _chart_cache
    if _chart_cache is None:
        _chart_cache = json.loads(
            (DATA / "chart_juego.json").read_text(encoding="utf-8"))
    return _chart_cache


def mult(atk: str, de: str) -> float:
    """Multiplicador del chart **real** del juego (no el oficial)."""
    return float(chart().get(atk, {}).get(de, 1.0))


PL_MUL = mult


# ------------------------------------------------------------- plan por insignia
@dataclass
class Plan:
    """Lo que hay que tener antes de pelear al siguiente líder.

    `nivel_min` es el listón con margen (el rival − margen, porque por encima
    del nivel del rival es imposible llegar). `nivel_max` es el listón del
    rival, que se usa para saber cuándo "ya no crece más en esta pantalla".
    """

    region: str
    insignias: int
    nivel_max: int          # el más alto del equipo rival
    nivel_min: int          # listón con margen para entrar
    tipos: list[str]        # tipos del equipo rival (no la fachada)
    nombre_jefe: str

    def resumen(self) -> str:
        return (f"insignias {self.insignias} | {self.nombre_jefe} "
                f"nv{self.nivel_min}-{self.nivel_max} "
                f"[{'/'.join(self.tipos) or '?'}]")

    def __str__(self) -> str:  # pragma: no cover - solo para logs
        return self.resumen()


# Margen de nivel por debajo del rival. Medido: con 31 contra un 32 se ganaba
# por tipos; con 26-31 y 4 caídos se perdía. El margen va con el tipo: si hay
# un 2x claro, se puede ir más abajo; si el rival es neutral, hace falta más.
# La guia es explicita: "aim to keep your Pokemon one or more levels ABOVE the
# opponent". Antes el liston estaba 2 por debajo del rival, asi que el bot creía
# estar preparado yendo 4 niveles por debajo. Ahora el liston es la PARIDAD (el
# nivel maximo del rival) y solo se perdona si hay un 2x claro.
# Regla del usuario, literal: hay que llegar **como minimo al mismo nivel** que
# los Pokemon del lider de gimnasio. El liston es el nivel mas alto de su equipo,
# sin rebajas. Antes iba uno por debajo y el bot llegaba 3 niveles corto.
#
# Sin descuentos: la regla es paridad estricta, incluso con un 2x a favor. Se
# dejo un margen de 3 niveles cuando hay ventaja de tipo y hacia que el bot
# entrara 3 por debajo en todas las Details, que es justo lo que hay que
# evitar. Si un 2x no basta para ganar 3 niveles de disadvantage, no es un 2x
# que valga.
# Nivel frente al lider de gimnasio. Lo que acordo el usuario: hay que llegar a
# su nivel, y se **asume que un 2x compensa 2 niveles por debajo**. Asi que la
# base es la paridad exacta y el unico margen es por ventaja de tipo.
#
# La paridad estricta sin margen (lo que hubo antes) era inalcanzable en la
# practica: el bot llegaba a la puerta del jefe 4 niveles corto y, como el jefe
# es salida forzada, o entraba y perdia o se quedaba atascado.
MARGEN_BASE = 0

# Flags de experimento, leidos del entorno. Van en un diccionario y no en
# variables sueltas porque sobreescribir `globals()[nombre]` desde un bucle
# era fragil (un nombre mal escrito creaba un atributo fantasma en vez de
# fallar). Ver `experimento.py`.
def _flags_entorno() -> dict:
    out = {"veto_tipo": False, "cobertura": False, "escalera_riesgo": True,
           "veto_nivel": True, "item_huecos": False,
           "captura_por_nivel": False}
    for k in out:
        v = os.environ.get(f"PKL_{k.upper()}")
        if v is None:
            continue
        if isinstance(out[k], bool):
            out[k] = v.strip().lower() in ("1", "true", "si", "yes")
        else:
            out[k] = float(v)
    return out

EXP = _flags_entorno()
def plan_para(region: str, insignias: int) -> Plan:
    """Construye el plan para el líder siguiente."""
    nivel_max, niveles = P.nivel_del_jefe(region, insignias)
    tipos = P.tipos_del_rival(region, insignias)
    nombre = nombre_jefe(region, insignias)
    # El margen depende de si el equipo puede con el rival por tipo. Si el
    # equipo tiene un 2x, se aguanta más abajo; si es neutral, hace falta más
    # nivel. Como no se conoce aún el equipo aquí, se usa el margen base y se
    # ajusta en `nivel_min_para(equipo)`.
    return Plan(region=region, insignias=insignias, nivel_max=nivel_max,
                nivel_min=max(1, nivel_max - MARGEN_BASE), tipos=tipos,
                nombre_jefe=nombre)


def nombres_jefes(region: str) -> list[str]:
    d = P.regiones().get(region, {})
    return [g.get("gimnasio", "?") for g in d.get("jefes", [])]


def nombre_jefe(region: str, insignias: int) -> str:
    nombres = nombres_jefes(region)
    if insignias < len(nombres):
        return nombres[insignias]
    elite = P.regiones().get(region, {}).get("elite_four_datos") or []
    i = insignias - len(nombres)
    if i < len(elite):
        return (elite[i].get("nombre")
                or elite[i].get("gimnasio")
                or f"Alta Mando {i+1}")
    return "Campeón"


def nivel_min_para(plan: Plan, equipo: list[dict]) -> int:
    """Listón ajustado por tipo: si hay un 2x claro, se puede ir más abajo.

    Con un món que pegue a 2x contra el rival, 3 niveles por debajo gana igual
    que a nivel. Con todo neutral, hacen falta los 2 niveles de margen.
    """
    if not equipo:
        return plan.nivel_min
    combos = []
    for m in equipo:
        tipos = m.get("tipos") or []
        if tipos:
            combos.append(tipos)
    if not combos or not plan.tipos:
        return plan.nivel_min
    mejor = max((max((mult(t, r) for t in c for r in plan.tipos), default=1.0)
                 for c in combos), default=1.0)
    if mejor >= 2.0:
        # Con un 2x claro se puede pelear por debajo del nivel del rival.
        return max(1, plan.nivel_min - MARGEN_BASE)
    if mejor <= 0.5:
        # Todo el equipo a 0.5x o menos: sin atajo de tipo hace falta MAS nivel
        # que la paridad, que es lo unico que puede compensar.
        return plan.nivel_min + 2
    return plan.nivel_min


# --------------------------------------------------------------- puntuación
# La prioridad que fijó el usuario, en orden estricto:
#   1. nivel igual o superior al del líder
#   2. tutor de movimientos
#   3. objetos
# La vida (cura) va por encima de todo porque el jefe es forzado: entrar con un
# caído es perder, y no siempre hay cura a mano.
PESO_CURA_CAIDOS = 50.0
PESO_CURA_BAJO = 25.0
PESO_CURA_SANO = 2.0
PESO_JEFE_LISTO = 12.0
PESO_JEFE_AUTOSADO = 4.0     # forzado, se entra (es la única salida)
# Un entrenador es, con diferencia, el mejor nodo del mapa: sube **a todo el
# equipo** a la vez. Medido, uno solo llevo al equipo de 8-9 a 10-11, mientras
# que ocho nodos contra salvajes de nivel 2-4 solo lo llevaron de 5 a 9.
# La primera captura de la pantalla. Va por encima del entrenador a proposito:
# es el paso 1 del libro de jugadas y sin un segundo món no hay equipo.
PESO_CAPTURA = 60.0
# El trade es el nodo más rentable del juego: +3 niveles y PS completos, y la
# guía lo llama "la mecánica más fuerte". Solo aparece con peso 5 frente a 30
# de los entrenadores, así que es raro y hay que quererlo.
PESO_TRADE = 45.0
PESO_ENTRENADOR_SANO = 34.0
PESO_BATALLA_NIVEL = 15.0    # cazar sube nivel: es la prioridad maxima
PESO_BATALLA_A_NIVEL = 4.0
# El tutor va segundo: por debajo de nivel y por encima de los objetos. Solo
# tiene sentido a nivel, que es cuando se aplica.
PESO_TUTOR_SIN_NIVEL = 1.0
PESO_TUTOR_CON_NIVEL = 9.0
# Los objetos van por detrás del nivel y del tutor, como pidió el usuario, pero
# **por delante de la batalla que no aporta nivel**: si no, nunca se coge ninguno
# y la bolsa queda vacía toda la partida. Medido: con el objeto en 3.0 y la
# batalla en 4.0 el bot elegía siempre pelear y la bolsa daba `[]` en todas las
# runs, así que el sistema de objetos (la segunda palanca según la guía) estaba
# muerto de nascimiento.
# Por encima de la pelea. La razón: un nodo de objeto **no es una pelea**, es
# un nodo que da un objeto permanente, y mientras falte nivel siempre hay algo
# que bate a 7.0, así que el bot no cogía ninguno: medido, 3 nodos de objeto
# disponibles y 0 cogidos, bolsa `[]` en todas las partidas. La guía lo dice
# igual ("item nodes beat fight nodes early"). El coste real es un paso hacia
# el jefe, y un +40% de daño o un Lucky Egg lo compensan de sobra.
PESO_OBJETO = 12.0

# La puerta que cierra el grafo, fijada por el usuario:
#   "...acabar en el nodo anterior a centro pokemon y si los pokemon tienen mas
#    del 75% de la vida ir al otro nodo y si no, ir al centro para curarse".
# Es el unico corte de vida del plan. Antes estaba al 55%, y H1 seguia dando
# -5 niveles de media: no era falta de nivel sino entrar al jefe gastado.
UMBRAL_PUERTA_JEFE = 0.75
# Escalera de riesgo del entrenador **sin cura delante**. La cura del juego es
# solo el pokecenter: en 100 runs el bot no vio ni una poción, así que entrar
# weakening sin cura a mano no se recupera, se pierde la run. Cada peldaño
# puntúa **por encima de cero a propósito**: un veto duro ya se probó (veto de
# tipo, -3) y salió PEOR, 0,64 frente a 1,62 insignias, porque en el 43% de las
# pantallas el entrenador es el único nodo y el veto lo dejaba sin opciones.
# Con la escalera, si no hay nada mejor pelea igual, pero con alternativa la
# gana.
UMBRAL_RIESGO_ALTO = 0.50    # equipo por debajo: ni cazar ni objeto
UMBRAL_RIESGO_MEDIO = 0.75
# (móns en pie como máximo, peso del nodo, penalización sobre el score final)
ESCALERA_RIESGO_ENTRENADOR = (
    (1, 0.5, -400.0),   # 1 món en pie: pelear es perder la run
    (2, 2.0, -140.0),   # 2 en pie: se gana de milagro
)
# Lo mismo por PS: (umbral de ratio del equipo, peso, penalización). Los
# umbrales van **primero** que la tabla que los usa: al revés, NameError al
# importar y los 24 runs de test no lo pillan porque el fallo es al arrancar.
ESCALERA_RIESGO_EQUIPO = (
    (UMBRAL_RIESGO_ALTO, 3.0, -300.0),
    (UMBRAL_RIESGO_MEDIO, 6.0, -110.0),
)
# Veto por nivel (H11): si el rival supera a la media del equipo + 1, no es
# exp, es riesgo. La guía lo pide literal ("1+ niveles por encima del rival"):
# https://pokelike-guide.fr/en/normal/improving-your-team/ — level lead.
# Era un no-op medido: devolvía -4.0 en `puntuar()` y el bono de ruta (60-300)
# lo tapaba siempre (8/8 veces en 24 runs). Mismo arreglo que la escalera:
# peso bajo en `puntuar()` + penalización final en `elegir()` que sí gana al
# bono. Nunca es veto duro: si el entrenador es el único nodo se pelea igual.
PENALIZACION_VETO_NIVEL = -400.0
PESO_VETO_NIVEL = -4.0
# El nodo `?` es aleatorio y trae shiny, pasivo o **trade**. El trade es la
# mecanica mas fuerte del juego segun la guia: cambias tu peor món por uno
# aleatorio **con +3 niveles y PS completo**, y las mejoras del Move Tutor se
# conservan al traded. Antes este nodo puntuaba 2.0, casi el peor, y se perdian
# niveles gratis por el camino.
PESO_INCOGNITA = 9.0


@dataclass
class Contexto:
    """Lo que el plan necesita saber del estado actual."""

    equipo: list[dict]
    plan: Plan
    hay_cura: bool = False      # hay un nodo de cura disponible ahora
    tiene_bolsa: bool = True    # el bot lleva objetos sin usar
    tutor_listo: bool = False   # el nodo del tutor está disponible
    # El jefe es la única salida del mapa: no se puede seguir subiendo nivel
    # sin entrar. Medido: en varias rutas las únicas opciones eran [jefe], y
    # entrar a ciegas (con caídos y por debajo de nivel) era la muerte.
    es_jefe_unica_salida: bool = False
    # ¿Hay un gimnasio al alcance? Si lo hay, curar sube por encima de buscar
    # exp: entrar al jefe medio muerto es la forma más fácil de perder la run.
    jefe_cerca: bool = False
    # ¿Este nodo está en el camino obligatorio al jefe? (waypoint tipo pokecenter)
    en_camino_al_jefe: bool = False
    # ¿Hay algún pokecenter accesible ahora mismo?
    hay_cura_disponible: bool = False
    caidos: int = 0
    # El mejor contragolpe contra el rival que toca, y con qué vida llega. Si
    # viene por debajo del 40% de PS, el món que puede ganar la pelea entra
    # roto: se nota y se avisa en la traza del jefe.
    carry_ps: float = 100.0
    carry_debil: bool = False
    # ¿El equipo está por debajo del listón del jefe que toca? Decide que la
    # ruta pese mucho: es la única palanca de exp que queda.
    corto_de_nivel: bool = False
    # Nivel real del rival del nodo (`trainerFightLevel`). Solo tiene sentido en
    # nodos de entrenador; 0 cuando el juego no lo expone. Antes no lo pasaba
    # nadie, y sin él la política no puede distinguir a un `youth` de nivel 9
    # de un `ace-trainer` de nivel 14+.
    nivel_rival: int = 0
    # Sprite -> tipos de los entrenadores del mapa. Es lo que permite el veto
    # "si se puede evitar a este entrenador, se evita".
    tipos_por_sprite: dict = field(default_factory=dict)
    # Sprite del nodo que se está puntuando.
    sprite: str = ""
    # ¿El nodo es un jefe? El jefe no entra en el veto de evitar.
    es_jefe: bool = False
    # ¿Ya se ha cazado en esta pantalla? El libro de jugadas es
    # "captura uno al principio y luego a por nivel", asi que la primera captura
    # tiene prioridad sobre cualquier otra cosa, incluso sobre el entrenador.
    capturas_pantalla: int = 0
    # Tipos del mapa a los que el equipo NO tiene respuesta (brazo C). Vive en
    # el Contexto porque lo consume `puntuar`, que no ve las locals de `elegir`.
    sin_respuesta: list = field(default_factory=list)


def _niveles(equipo: list[dict]) -> list[int]:
    return [m.get("nivel") or 0 for m in equipo]


def _estado(equipo: list[dict]) -> tuple[float, int, int]:
    """(ratio medio de PS, caídos, vivos) del equipo."""
    ratios = [(m.get("ps") or 0) / max(m.get("ps_max") or 1, 1) for m in equipo]
    caidos = sum(1 for m in equipo if (m.get("ps") or 0) <= 0)
    vivos = sum(1 for m in equipo if (m.get("ps") or 0) > 0)
    return (sum(ratios) / len(ratios) if ratios else 0.0, caidos, vivos)


def riesgo_entrenador(ctx: Contexto) -> tuple[float | None, float, str]:
    """Peldaños de la escalera de riesgo de un nodo de entrenador.

    Devuelve `(peso_del_nodo, penalización, motivo)`. Peso y penalizacion son 0
    o `None` cuando el riesgo no aplica. Solo tiene sentido pedirla para nodos
    de tipo `entrenador`: los jefes de gimnasio son tipo `jefe` y quedan fuera,
    que es justo donde el diagnostico dice que no hay que tocar nada (68% de las
    muertes son fuera de gimnasio).

    **Por qué dos cantidades y no una.** La primera versión solo bajaba el peso
    del nodo a 0.5 o 2.0, y fue un no-op medido, no hipotético: en 24 runs la
    escalera marcó "entrenador de riesgo" 13 veces y el bot lo eligió **13 de
    13**, igual que el brazo de control. La causa es el orden de las sumas en el
    bucle de puntuación:

        s = peso * multiplicadores
        s += extra * peso_ruta     # bono de ruta: n_ent*4 y n_centro*12,
                                   # por 3.5 mientras falte nivel

    El bono se suma **después** y vale 60-300, de modo que un peso de 0.5 no
    pierde nunca contra él. La penalizacion se suma al final, con el bono ya
    dentro, y ahí sí puede ganar.

    Sigue sin ser un veto duro: si el entrenador es el nodo único de la
    pantalla se pelea igual. Lo único que cambia es el orden cuando hay
    alternativa, que es lo que se quería medir.
    """
    if ctx.hay_cura_disponible:
        # Con pokecenter delante, el corte de emergencia de R8 ya obliga a
        # curar y penalizar el entrenador solo taparía la cura.
        return None, 0.0, ""
    ratio, caidos, vivos = _estado(ctx.equipo)
    if caidos >= 1:
        # El `caidos >= 1` no es cosmetico: un equipo de **un solo món sano**
        # es el inicio normal de la partida y ahí pelear es justo lo que hay
        # que hacer. Lo que mata es perder móns, así que la escalera por móns
        # en pie solo aplica cuando ya se ha perdido alguno. El `ratio` de
        # abajo recoge el caso "entero pero gastado": los caidos cuentan como 0
        # en la media.
        for min_vivos, peso, pen in ESCALERA_RIESGO_ENTRENADOR:
            if vivos <= min_vivos:
                return (peso, pen,
                        f"entrenador de riesgo: {vivos} món(s) en pie, "
                        f"{caidos} caído(s) y sin cura a mano")
    for umbral, peso, pen in ESCALERA_RIESGO_EQUIPO:
        if ratio < umbral:
            etiqueta = ("aplazado" if peso <= 3.0 else "de riesgo")
            return (peso, pen,
                    f"entrenador {etiqueta}: equipo al {ratio*100:.0f}% "
                    f"y sin cura delante")
    return None, 0.0, ""


def veto_nivel_entrenador(ctx: Contexto) -> tuple[float | None, float, str]:
    """Veto por nivel en dos tiempos (H11): peso + penalización final.

    Devuelve `(peso_del_nodo, penalización, motivo)`. La referencia es la
    **media del equipo + 1**, misma que `puntuar()` usaba antes: no se cambia
    el umbral en este cambio, solo el sitio donde se aplica, para medir una
    sola variable (ver HIPOTESIS.md H11).

    Guía: "aim to keep your Pokémon one or more levels ABOVE the opponent"
    (https://pokelike-guide.fr/en/normal/improving-your-team/). Un rival por
    encima de media+1 no es exp, es el Ace Trainer Nv15 que mata runs en Nv11.

    No es veto duro: si el entrenador es el único nodo se pelea igual, igual
    que la escalera de riesgo.
    """
    niveles = _niveles(ctx.equipo)
    tope_equipo = (sum(niveles) / len(niveles)) if niveles else 0
    if ctx.nivel_rival > 0 and tope_equipo and ctx.nivel_rival > tope_equipo + 1:
        return (PESO_VETO_NIVEL, PENALIZACION_VETO_NIVEL,
                f"entrenador vetado: rival Nv{ctx.nivel_rival} supera al "
                f"el nivel del equipo (Nv{tope_equipo:.0f}+1) — no es exp, "
                f"es riesgo")
    return None, 0.0, ""


def _equipo_responde_a(equipo: list[dict], tipo: str) -> bool:
    """¿Algún món vivo tiene respuesta de tipo a ese tipo? `>= 1.0` cuenta.

    Se mira el **tipo principal** de cada món, que es el tipo de su único
    ataque. Un món caído no cuenta: no puede pelear.
    """
    from pkl_movimientos import multiplicador as _mult

    for m in equipo or []:
        if (m.get("ps") or 0) <= 0:
            continue
        tipos = [T.normalizar(t) for t in (m.get("tipos") or []) if t]
        if not tipos:
            continue
        if _mult(tipos[0], tipo) >= 1.0:
            return True
    return False


def _tipos_del_entrenador(ctx: Contexto) -> list[str]:
    """Tipos del entrenador de **este** nodo, si se conocen.

    Vienen en `Contexto.tipos_por_sprite`, indexado por sprite, porque el
    veto es "si se puede evitar a **este** entrenador": un equipo puede
    ganarle a un hiker y perder contra un fire-spitter, y con el conjunto de
    la ruta esa distinción no existe.
    """
    sprite = (getattr(ctx, "sprite", "") or "").lower().replace("-", "")
    tabla = getattr(ctx, "tipos_por_sprite", None) or {}
    for clave in (ctx.sprite, sprite, ctx.sprite.lower() if ctx.sprite else ""):
        if clave and clave in tabla:
            return list(tabla[clave])
    return []


def _alguien_le_gana(ctx: Contexto, tipos_rival: list[str]) -> bool:
    """¿Hay algún món vivo que le gane a este entrenador por tipo?

    Se mira el **tipo principal** de cada món, que es el tipo de su único
    ataque (el Move Tutor sube el tier de ese ataque, no le añade un segundo
    tipo). Se considera que "le gana" con x1 o mejor: por debajo de x1 es
    perderlo de todas formas.

    Se ignoran los caídos: no pueden pelear, así que no cuentan como
    respuesta.
    """
    from pkl_movimientos import multiplicador as _mult

    for m in ctx.equipo or []:
        if (m.get("ps") or 0) <= 0:
            continue
        tipos = [T.normalizar(t) for t in (m.get("tipos") or []) if t]
        if not tipos:
            continue
        peor = min((_mult(tipos[0], r) for r in tipos_rival if r), default=0.0)
        if peor >= 1.0:
            return True
    return False


def puntuar(tipo: str, ctx: Contexto) -> tuple[float, str]:
    """Puntúa un tipo de nodo con el plan a la vista.

    La idea es no mirar "qué es este nodo" sino "qué me falta": nivel, vida o
    el listón del jefe. Por eso el mismo nodo `batalla` vale 10 con el equipo
    por debajo de nivel y 4 con el equipo a nivel.
    """
    equipo, plan = ctx.equipo, ctx.plan
    if not equipo:
        return (PESO_BATALLA_NIVEL, "equipo vacío: que caiga algo")

    ratio, caidos, vivos = _estado(equipo)
    liston = nivel_min_para(plan, equipo)
    niveles = _niveles(equipo)
    medio = sum(niveles) / len(niveles) if niveles else 0
    falta = liston - medio

    # OJO: el tipo que emite el juego es `pokecenter`, no `cura`. Con `cura`
    # esta rama **nunca se ejecutó** y por eso todos los runs acababan con
    # `centros : 0`: la lógica de curar estaba muerta sin dar ningún error.
    # **Corte de emergencia.** Antes de puntuar nada: si el equipo esta @
    # raspar, cualquier otra cosa es secundario. Medido: el bot estaba con
    # Geodude 8/26 y Bulbasaur 8/29 y en vez de ir al centro se puso a cazar,
    # porque el nodo de captura puntuaba 61 (40 de base + 21 por el bonus de
    # ruta con 6 combates) y le ganaba al centro. Murio ahi. Un equipo al 30%
    # no puede permitirse gastar un paso en nada que no sea recuperar vida.
    # Solo se aplica **si hay un centro accesible**: sin centro delante, el
    # corte no puede dejar al bot sin opciones (ponia a todos los nodos al
    # mismo -5 y por ahi colaba entrar al jefe moribundo). Sin pokecenter a la
    # vista se juega con lo que haya, que es la unica opcion.
    if tipo not in ("cura", "pokecenter") and ctx.hay_cura_disponible:
        # Se mira el **equipo**, no solo el carry: medido, el bot peleo un
        # Ponyta con Bulbasaur a 100 y Spearow a 13 y perdio. El carry estaba
        # sano, asi que mirar solo su vida no disparaba nada. Un món a 13 con
        # otro a 100 es un equipo al borde.
        # El usuario lo fijo de forma explicita: **más del 75% de vida se va al
        # otro nodo**, por debajo se pasa por el centro a curarse y luego al
        # jefe. Antes el corte era al 55%, o sea que se entraba al lider con el
        # equipo al 60% por mucho que hubiera centro a mano. Con el 75% la
        # puerta decide con la misma regla que la persona.
        # El carry se mira aparte a proposito: un solo món al 13% se va a morir
        # aunque la media del equipo pase del 75%, y perder un món es peor que
        # perder un paso.
        # El umbral es el **50%**, no el 40%: es la regla del usuario ("el carry
        # esta < 50%") y la asimetría lo hace más seguro: con 40, un carry al 45%
        # entraba a pelear y se le terminaba la vida antes de decidir; con 50 se
        # cura antes. Entrar al pokecenter cuesta **un paso**, y perder un món
        # cuesta la run.
        if caidos >= 1 or ratio <= UMBRAL_PUERTA_JEFE or ctx.carry_ps < 50.0:
            return (-5.0,
                    f"nada que no sea curar: {caidos} caido(s), equipo al "
                    f"{ratio*100:.0f}%, carry al {ctx.carry_ps:.0f}%")

    if tipo in ("cura", "pokecenter"):
        # **Curar a tope antes de un jefe, siempre.** Medido: el bot aplaza el
        # gimnasio para buscar exp, se desgasta peleando entrenadores y acaba
        # entrando a Misty con el carry al 45% y sin haber pasado por un centro
        # en 72 pasos. Se pierde por vida, no por nivel. La guía lo dice igual:
        # "heal to full before a boss". Un centro de curacion es un nodo y un
        # paso, y recuperar toda la vida vale mas que un nivel.
        # **Waypoint obligatorio.** El grafo siempre pone un pokecenter entre
        # el nodo actual y el líder, asi que no es "curar o no": es que hay que
        # pasar por ahi, y al pasar se cura entero. Antes el bot lo saltaba y
        # llegaba al gimnasio con el carry al 19%.
        # Prioridad de paso obligatorio: por encima del entrenador (36) y del
        # cazar por nivel, y por debajo de capturar el primero (40), que es el
        # paso 1 del libro de jugadas.
        if ctx.en_camino_al_jefe:
            if caidos:
                return (58.0,
                        f"curar: paso obligatorio hacia el jefe y hay "
                        f"{caidos} caido(s)")
            if ctx.carry_ps < 98.0:
                return (52.0,
                        f"curar: paso obligatorio hacia el jefe, carry al "
                        f"{ctx.carry_ps:.0f}% (a tope, sale gratis)")
            return (50.0,
                    "pokecenter: paso obligatorio hacia el jefe, ya se va "
                    "entero pero se pasa por aqui igualmente")
        # Se cura por el **carry**, no por la media del equipo. El carry es el
        # único que tiene que llegar entero al jefe, y un món flojo arrastra a
        # la media: medido, el equipo estaba al 40% de media y aun así el
        # principal llegaba con 10 de 49 PS al gimnasio.
        if caidos:
            return (PESO_CURA_CAIDOS,
                    f"curar {caidos} caído(s): el jefe es salida forzada")
        if ctx.carry_ps < 65.0:
            return (PESO_CURA_BAJO + 8.0,
                    f"curar: el carry está al {ctx.carry_ps:.0f}% "
                    "(es el que tiene que llegar entero)")
        return (PESO_CURA_SANO,
                f"curar: carry al {ctx.carry_ps:.0f}%, no hace falta")

    if tipo == "jefe":
        # El listón es un rango con margen, y por encima del nivel del rival
        # es imposible: se considera "listo" si el equipo alcanza el listón con
        # margen y no hay caídos.
        #
        # Pero estar "listo" no es motivo para pelear YA. El jefe solo se
        #zekepea cuando es la única salida que queda; si hay Trainer o batalla
        # disponibles, se sigue subiendo nivel, porque la prioridad pedida es
        # "nivel igual o superior al del líder" y cada combate de más sube más
        # el listón de la siguiente insignia.
        if ctx.es_jefe_unica_salida:
            if not ctx.caidos and medio >= liston:
                return (PESO_JEFE_LISTO,
                        f"jefe: única salida y listo (medio {medio:.0f} "
                        f">= listón {liston})")
            motivo = []
            if ctx.caidos:
                motivo.append(f"{ctx.caidos} caído(s)")
            if medio < liston:
                motivo.append(f"medio {medio:.0f} < listón {liston}")
            elif medio < plan.nivel_max:
                motivo.append(f"medio {medio:.0f} < nivel del rival "
                              f"{plan.nivel_max}")
            if ctx.carry_debil:
                # El mejor contragolpe por los suelos. Es la causa medida de
                # morir en el segundo gimnasio: el Goldeen (único 2x contra el
                # Agua de Misty) entraba con 10 de 49 PS porque el bot lo sacaba
                # al frente en todas las batallas de la ruta para nakedearlo.
                motivo.append(f"carry flojo ({ctx.carry_ps:.0f}%)")
            if medio < liston:
                # **Por debajo del nivel del rival no se entra**, ni aunque sea
                # la unica salida. Es la regla que fijo el usuario y la razon
                # de que se perdia: entrar a ciegas contra un lider mas alto
                # es perder la partida, mientras que buscar un nodo mas de
                # experiencia solo cuesta un paso del mapa. Si el mapa no
                # ofrece nada mas, se acepta el Empate tecnico (ATASCADO) en
                # vez de regalar la insignia.
                return (-1.0,
                        f"jefe APLAZADO: hay {liston - medio:.0f} nivel(es) de "
                        f"faltan (listón {liston}, rival {plan.nivel_max}); "
                        f"se busca más exp"
                        + (f" | {', '.join(motivo)}" if motivo else ""))
            return (PESO_JEFE_AUTOSADO,
                    f"jefe: única salida, se entra igual ({', '.join(motivo)})")
        # Hay alternativas: el jefe espera. Solo se antepone si el listón ya
        # está superado con holgura, que entonces ya no hay nada
        # mejor que hacer y entrar cierra la pantalla.
        if medio >= plan.nivel_max and not ctx.caidos:
            return (PESO_JEFE_LISTO - 2.0,
                    f"jefe: a nivel del rival ({medio:.0f}) y no hay nada mejor")
        return (-3.0,
                f"jefe aplazado: hay alternativas y falta nivel "
                f"({medio:.0f} < {liston})")

    if tipo == "batalla":
        # **Paso 1 del libro de jugadas: capturar UNO al principio.** Va por
        # encima del entrenador incluso faltando nivel, porque un equipo de uno
        # solo pierde contra cualquier trainer. Antes el bot lo vetaba por
        # falta de nivel y se quedaba con un unico món: medido, perdiendo
        # contra un Grunt del Team Rocket con el món a 100 de PS.
        if ctx.capturas_pantalla == 0:
            # Cazar uno por pantalla, pero **con la condición que evita la
            # trampa**: cada captura avanza de pantalla y pone el contador a
            # cero, asi que con la captura sin condiciones el bot caza, avanza,
            # caza otra vez y **no llega nunca a pelear con nadie**. Medido:
            # llegó al gimnasio con Bulbasaur 7 y Doduo 8 contra un Brock de
            # 12-14, que es perder por nivel con total seguridad.
            #
            # Las dos reglas del usuario se combinan asi:
            #   - sin móns suficientes, cazar (un equipo de dos no gana nada),
            #   - con equipo suficiente y **por debajo de nivel**, entrenar,
            #   - a nivel, cazar para ampliar.
            # El filtro de calidad (nivel y stats) vive en `elegir_captura`, asi
            # que cazar no significa coger basura: significa coger el primero
            # que sirva de verdad.
            if len(equipo) < 3:
                return (PESO_CAPTURA,
                        f"capturar: equipo de {len(equipo)}, hacen falta "
                        f"cuerpos antes que nivel")
            # **La cobertura de tipos va POR DELANTE del nivel.** Con un
            # equipo al nivel correcto pero sin respuesta de tipo, cazar es la
            # unica palanca: es lo que evita pelear a x0.5. El veto de
            # entrenador por tipo ya quedo probado insuficiente, porque el
            # problema no es elegir la pelea sino no tener el món.
            if ctx.sin_respuesta:
                return (PESO_CAPTURA,
                        f"capturar: falta respuesta de tipo para "
                        f"{', '.join(ctx.sin_respuesta[:3])}; el nivel se recupera "
                        f"después, el agujero de tipo no")
            if falta > 1:
                if EXP["captura_por_nivel"]:
                    # **H17: cuando falta nivel y esta pantalla ofrece
                    # pokeball, capturar DOMINA a cazar.**
                    #
                    # Medido en el lote de 150 runs, en la ventana antes de
                    # Misty: 6,52 batallas sueltas frente a 3,19 capturas. O sea
                    # que se pelea el doble de veces sin capturar que
                    # capturando.
                    #
                    # Y cazar no es mejor que capturar: R2 da +1 nivel a la
                    # pelea, y una captura **es** una pelea. O sea que capturar
                    # da el mismo nivel **y ademas un món**. Este 8.0 estaba
                    # por debajo del entrenador (36), asi que cuando la pantalla
                    # tenia captura y faltaba nivel, el bot se iba al
                    # entrenador y la pantalla de captura no se llegaba a ver.
                    #
                    # Lo que NO se toca es la comparacion con el entrenador
                    # (36): una captura da +1 nivel y un món, un entrenador +2
                    # niveles y ningun món, y ademas perder contra un entrenador
                    # termina la run. Con el equipo corto —que es el caso aquí,
                    # que solo entra por encima de 3 móns— ese trueque es
                    # razonable y arriesgado tocarlo.
                    #
                    # La opcion de preferir SIEMPRE al entrenador por sobre la
                    # captura se descarto antes de escribir esto: significaba
                    # pagar un món por un nivel extra justo cuando los móns son
                    # lo que falta (se llega a Misty con 4 de mediana cuando la
                    # condicion necesita 5-6).
                    return (PESO_CAPTURA,
                            f"capturar tambien sube nivel: faltan "
                            f"{falta:.0f} y una captura es una pelea que deja "
                            f"un món de más")
                return (8.0,
                        f"cazar {falta:.0f} nivel(es) por encima del entrenador: "
                        f"el equipo ya tiene {len(equipo)} móns, ahora toca "
                        f"ganar experiencia")
            return (PESO_CAPTURA,
                    f"capturar: equipo de {len(equipo)} y ya a nivel, ampliar "
                    f"con el mas alto de esta pantalla")
        if caidos and ratio < 0.35 and not ctx.hay_cura:
            return (3.0, "cazar: equipo medio muerto y sin cura, arriesgado")
        if falta > 1:
            return (PESO_BATALLA_NIVEL,
                    f"cazar sube nivel (faltan ~{falta:.0f} al listón {liston})")
        return (PESO_BATALLA_A_NIVEL, "cazar: ya en pie y a nivel")

    if tipo == "entrenador":
        # **Veto por tipo: si se puede evitar al entrenador, se evita.**
        #
        # Regla del usuario, literal: "si podemos evitar al entrenador, lo
        # evitamos, si es el lider, jugamos". O sea que la pregunta no es
        # "¿me da experiencia?" (siempre la da) sino "¿hay con qué ganarle?".
        # Y aquí la respuesta la da la **tabla de tipos**: si ningún món del
        # equipo llega a x1 contra su especialidad, la pelea se pierde por
        # tipos, no por nivel, y no hay nivel que la arregle.
        #
        # El jefe **no** entra en este veto: contra el líder se juega siempre,
        # porque no se puede evitar y porque es la única forma de pasar.
        #
        # Antes entraba a ciegas: medido, se perdió contra un
        # `team-rocket (Poison/Normal)` con Krabby x1, Ivysaur x0.5 y Clefairy,
        # sin nada que le ganara.
        tipos_riv = _tipos_del_entrenador(ctx)
        # El veto por tipo es el experimento "desactivar_veto_tipo". Ver
        # `experimento.py`: se midio que con el veto el bot pierde igual, pero
        # sus.muertes tienen al equipo en x0.5 contra el rival, o sea que la
        # regla le alejaba de la unica fuente de exp sin arreglar el problema
        # de fondo (el equipo no tiene respuesta de tipo).
        if tipos_riv and not ctx.es_jefe and EXP["veto_tipo"]:
            if not _alguien_le_gana(ctx, tipos_riv):
                return (-3.0,
                        f"entrenador evitable: nadie le gana por tipo "
                        f"({'/'.join(tipos_riv)})")
        # **Veto por nivel del rival, y la referencia es el EQUIPO.**
        # `trainerFightLevel` ya decía el nivel del entrenador y ese dato no
        # llegaba a la política. Lo que además estaba mal era la referencia:
        # se comparaba contra el nivel del **jefe**, así que un Ace Trainer
        # Nv15 no se vetaba con el listón en Nv14 (margen de uno) y el bot
        # entraba con el equipo en Nv11 y dos caídos. Medido en la tanda que
        # perdió: `Ace Trainer wants to battle!` con `[Mankey 12, Rattata 12,
        # Staryu 17, Ivysaur 16]` y nivel enemigo 13.
        # Lo que decide si una pelea se gana es el **equipo que la pelea**:
        # mejor món del equipo + 2 de margen, para no ser tan estricto que
        # bloquee la única fuente de exp.
        # **El listón es el món que ABRE, no el mejor del equipo.** Con la
        # referencia en el mejor món el veto no disparaba: un Mankey Nv10
        # cubría a un Staryu Nv6 que es quien abre, y contra un fire-spitter
        # Nv12 (12 > 10+2 es falso) se entraba y se perdía con el equipo entero
        # a 0. Medido: `mios=[Staryu 0/19, Geodude 0/26, Mankey 0/28,
        # Bulbasaur 0/29]` contra rival Nv12.
        # Se usa el **menor** de los que pueden abrir, que es el que de verdad
        # tiene que aguantar el combate: si el que va delante está 4 niveles
        # por debajo, la pelea se pierde aunque el equipo tenga un món alto
        # detrás. El margen de 1 (no 2) es porque aquí la referencia ya es
        # conservadora.
        # Con el mínimo un solo món flojo (el que va detrás y no pega)
        # bloqueaba toda la exp; con el máximo un món alto tapaba al que abre.
        # La media es el nivel con el que pelea el equipo de verdad, y deja
        # pasar a un rival del mismo nivel: media de [9,7] es 8, y 9>8+1 falso.
        # H11: el peso solo es el suelo; la parte que decide va en `elegir()`
        # con `veto_nivel_entrenador(ctx)[1]`, igual que la escalera. Sin eso
        # el -4.0 lo tapaba el bono de ruta (60-300) 8/8 veces.
        vn_peso, _, vn_motivo = veto_nivel_entrenador(ctx)
        if vn_peso is not None:
            return (vn_peso, vn_motivo)
        # ---- Riesgo: como llega el equipo a esta pelea -------------
        # Medido en 100 runs: de 54 muertes de entrenador, **33 eligieron el
        # nodo con 2 o menos móns en pie y 15 con uno solo**, y 21 se
        # quedaron con un único món al perder. No es el nivel (el bot va +5)
        # ni el tipo (el veto de tipo ya se midio y perdio): es llegar a
        # pelear con el equipo desmontado y sin cura a mano.
        #
        # Solo aplica **sin cura disponible**. Con pokecenter delante el corte
        # de emergencia del principio ya obliga a curar y esto no harian falta:
        # la regla del usuario (R8) dice que con el equipo <=75% se va al
        # centro, y eso ya esta implementado arriba.
        # Brazo de control del experimento de la escalera: el comportamiento
        # **literal** de antes, con su rama que premia pelear con caidos. Se
        # conserva a proposito hasta tener veredicto; el dia que se cierre la
        # hipotesis, esta rama y el flag se borran juntos.
        if not EXP["escalera_riesgo"]:
            if caidos and not ctx.carry_debil and not ctx.hay_cura_disponible:
                return (PESO_ENTRENADOR_SANO,
                        f"entrenador con {caidos} caído(s) y sin cura a mano: "
                        f"se juega igual, es la única fuente de exp")
            if ratio < 0.25:
                return (3.0, f"entrenador aplazado: equipo al {ratio*100:.0f}%, "
                             f"demasiado expuesto")
        else:
            # El peso de la escalera es solo el suelo: entra en `s` antes del
            # bono de ruta y por eso no decide casi nunca. La parte que
            # decide se aplica despues, en el bucle de puntuacion, con
            # `riesgo_entrenador(ctx)[1]`.
            riesgo = riesgo_entrenador(ctx)
            if riesgo[0] is not None:
                return (riesgo[0], riesgo[2])
        if falta > 1:
            return (PESO_ENTRENADOR_SANO + 2.0,
                    f"entrenador: mucha exp, faltan ~{falta:.0f} de nivel")
        # Ya se esta al nivel del lider: el entrenador deja de ser la fuente de
        # exp y pasa a ser un **riesgo**. Medido con el foco trainers arriba: el
        # bot subio a 23-28, vencio a Misty y luego perdio contra un Bug Catcher
        # de ruta con Ivysaur a 100 PS. Peleados por costumbre, no por nivel.
        return (6.0, "entrenador: ya a nivel, no hace falta arriesgar")

    if tipo in ("trade", "intercambio"):
        # Siempre que falte nivel, el trade es lo mejor que hay: +3 niveles para
        # el equipo y el món vuelve con la vida llena. Por encima del
        # entrenador (36) y muy por encima de cazar por nivel.
        if falta > 0:
            return (PESO_TRADE,
                    f"trade: +3 niveles y PS completos, faltan "
                    f"~{falta:.0f} de nivel (el nodo más fuerte del juego)")
        return (12.0, "trade: a nivel ya, no hace falta")

    if tipo == "tutor":
        # Segunda prioridad, y **solo para el principal**: una MT a un món que
        # no va a llevar el combate no vale el paso. El nivel va primero, asi
        # que con dos niveles de diferencia la MT se pospone sola.
        if falta > 1:
            return (PESO_TUTOR_SIN_NIVEL,
                    "MT pospuesta: el nivel va primero (1er criterio)")
        if not ctx.carry_ps or ctx.carry_ps < 25.0:
            return (PESO_TUTOR_SIN_NIVEL,
                    "MT pospuesta: el principal esta demasiado flojo para "
                    "que le sirva el tier")
        if ctx.tutor_listo:
            return (PESO_TUTOR_CON_NIVEL,
                    "MT: 2a prioridad y el nodo esta disponible, sube el "
                    "tier del principal")
        return (PESO_TUTOR_CON_NIVEL - 1.0, "MT: sin nodo accesible ahora")

    if tipo == "item":
        # El objeto es **la tercera** prioridad del orden del usuario
        # (niveles, MT al principal, objetos), asi que no puede acercarse ni a
        # un nivel ni a una MT: si no, el bot gastaba pasos en la bolsa con el
        # equipo por debajo del liston.
        #
        # H13: la condición estaba **invertida**. `tiene_bolsa` quiere decir
        # "quedan huecos" (`not items_tomados >= MAX_ITEMS`), así que el código
        # puntúa el nodo con 12.0 cuando la bolsa está **llena** y con **2.0**
        # cuando hay sitio: exactamente al revés. Medido en 924 pantallas de
        # mapa (56 runs): el nodo `item` se ofreció 144 veces (16%) y el bot
        # lo cogió **4** (3%); 26 de 54 runs terminaron con 0 objetos y la
        # media fue 0,89. La guia dice lo contrario dos veces ("item nodes beat
        # fight nodes early" y el Lucky Egg "outscales the route").
        # El mensaje también mentía: "bolsa vacía" salía en la rama de bolsa
        # llena.
        if not ctx.tiene_bolsa:
            # Sin huecos: coger el objeto es tirar un nodo, pero no hace daño.
            return (2.0, "objeto: sin huecos en el equipo, no se coge")
        if EXP["item_huecos"]:
            return (PESO_OBJETO,
                    "objeto: hay hueco y es la 3a prioridad (nivel > MT > "
                    "objeto)")
        return (2.0, "objeto: hay hueco pero no es prioridad (flag apagado)")

    if tipo == "incognita":
        return (PESO_INCOGNITA, "nodo sin identificar (trade o pasivo)")

    return (2.0, f"nodo {tipo}")


def elegir(equipo: list[dict], nodos: list[dict], ctx_extra: dict | None = None,
           *, region: str, insignias: int, ids_disponibles: set | None = None,
           info_mapa: str = "", edges: list | None = None,
           nodo_actual: str | None = None,
           limpio: int = 8) -> P.Decision:
    """Elige el nodo a visitar según el plan.

    `ctx_extra` puede pasar `hay_cura` (bool), `tiene_bolsa` (bool) y
    `tutor_listo` (bool) para afinar la decisión; si falta, se deducen del
    equipo y de los nodos disponibles.
    """
    plan = plan_para(region, insignias)
    extra = ctx_extra or {}

    if ids_disponibles is None:
        ids_disponibles = {str(n.get("id")) for n in nodos if n.get("clickable")}

    # Se deduce si hay cura a mano, para puntuar bien la batalla con caídos.
    hay_cura = extra.get("hay_cura")
    if hay_cura is None:
        hay_cura = any(
            (P.tipo_de_estado(n.get("tipo")) if n.get("tipo")
             else P.tipo_de_nodo(n.get("sprite", ""))) == "cura"
            and str(n.get("id")) in ids_disponibles
            for n in nodos)

    # El jefe solo se toma si es la **única** salida. Si hay Trainer o batalla
    # disponibles, se sigue subiendo nivel: la prioridad pedida es nivel, y cada
    # combate de más acerca el listón de la insignia siguiente. Se cuentan solo
    # los nodos que dan experiencia, no los de objeto ni los de tutor.
    def _tipo(n) -> str:
        return (P.tipo_de_estado(n.get("tipo")) if n.get("tipo")
                else P.tipo_de_nodo(n.get("sprite", "")))

    tipos_disponibles = [_tipo(n) for n in nodos
                         if n.get("clickable")
                         and str(n.get("id")) in ids_disponibles]

    # **Cobertura de tipos (brazo C del experimento).**
    # La medicion de 97 runs dio que en 21 de 26 muertes el mejor món del
    # equipo era x0.5 contra el rival: el equipo no tenia respuesta de tipo.
    # Este flag sube el peso del nodo de captura cuando al equipo le faltan
    # respuestas para los tipos que hay en el mapa, para tapar el agujero antes
    # de pelear en lugar de perder la pelea.
    sin_respuesta: list[str] = []
    if EXP["cobertura"] and "capturar" in tipos_disponibles:
        por_sprite = extra.get("tipos_por_sprite") or {}
        tipos_ruta = {t for ts in por_sprite.values() for t in ts}
        sin_respuesta = sorted(t for t in tipos_ruta
                               if not _equipo_responde_a(equipo, t))

    es_jefe_unica_salida = extra.get("es_jefe_unica_salida")
    if es_jefe_unica_salida is None:
        hay_exp = any(t in ("batalla", "entrenador")
                      for t in tipos_disponibles)
        es_jefe_unica_salida = ("jefe" in tipos_disponibles
                                and not hay_exp)

    # El carry es el món que mejor responde al rival que toca, y su vida decide
    # si la pelea es viable.
    carry_ps = 100.0
    if plan.tipos:
        con_t = [m for m in equipo if m.get("tipos") and (m.get("ps") or 0) > 0]
        if con_t:
            mejor_m = min(
                con_t,
                key=lambda m: sum(
                    PL_MUL(m["tipos"][0], r) for r in plan.tipos) / len(plan.tipos))
            ratio = ((mejor_m.get("ps") or 0)
                     / max(mejor_m.get("ps_max") or 1, 1) * 100)
            carry_ps = ratio

    niveles_eq = [m.get("nivel") or 0 for m in equipo if (m.get("nivel") or 0) > 0]
    medio_eq = (sum(niveles_eq) / len(niveles_eq)) if niveles_eq else 0

    # Id del jefe alcanzable: sirve para detectar los nodos que estan en el
    # camino obligatorio hasta el (el pokecenter de siempre, segun el grafo).
    # OJO: el tipo crudo del juego es `boss`; `jefe` es la traducción de
    # `tipo_de_estado`. Comparar contra la palabra en española hacia `None` y
    # dejaba el waypoint desactivado sin avisar.
    jefe_alcanzable = next(
        (str(n.get("id")) for n in nodos
         if P.tipo_de_estado(n.get("tipo")) == "jefe" and n.get("clickable")
         and str(n.get("id")) in ids_disponibles),
        None,
    )

    ctx = Contexto(
        equipo=equipo, plan=plan,
        carry_ps=carry_ps,
        carry_debil=bool(plan.tipos and carry_ps < 50.0),
        corto_de_nivel=(medio_eq < nivel_min_para(plan, equipo) - 1),
        capturas_pantalla=int(extra.get("capturas_pantalla", 0) or 0),
        hay_cura=bool(hay_cura),
        tiene_bolsa=bool(extra.get("tiene_bolsa", True)),
        tutor_listo=bool(extra.get("tutor_listo", False)),
        es_jefe_unica_salida=bool(es_jefe_unica_salida),
        jefe_cerca=bool("jefe" in tipos_disponibles),
        en_camino_al_jefe=bool(extra.get("en_camino_al_jefe")),
        hay_cura_disponible=("cura" in tipos_disponibles),
        caidos=_estado(equipo)[1],
        tipos_por_sprite=dict(extra.get("tipos_por_sprite") or {}),
        sin_respuesta=sin_respuesta,
    )

    punt: list[tuple[float, dict, str]] = []
    # Si el filtro de alcanzables deja la lista vacía se reintenta sin él, y si
    # tampoco hay nada se coge el primer nodo clicable. Devolver una decisión
    # sin nodo (`valor=None`) hacía que el bot no pulsara nada y se colgara:
    # medido, seis runs de prueba morían con `ATASCADO` en `map-screen|nodo None`
    # tras 13 vueltas sin avanzar.
    for filtro in (ids_disponibles, None):
        for n in nodos:
            if not n.get("clickable"):
                continue
            if filtro is not None and str(n.get("id")) not in filtro:
                continue
            tipo = (P.tipo_de_estado(n.get("tipo")) if n.get("tipo")
                    else P.tipo_de_nodo(n.get("sprite", "")))
            # Contexto propio de este nodo: si desde el se llega al jefe, es
            # un waypoint obligatorio (el pokecenter de en medio) y curar sale
            # gratis de paso.
            ctx_n = ctx
            # El nivel del rival es **por nodo**: un mismo mapa puede tener un
            # `youth` de nivel 9 y un `ace-trainer` de nivel 15, y se puntúan
            # distinto. Antes `nivel_rival` no llegaba a la política y ambos
            # puntuaban exactamente igual.
            if tipo == "entrenador":
                # Sprite y si es jefe, para el veto de evitar.
                ctx_n = replace(ctx_n, sprite=str(n.get("sprite") or ""))
                niv_rival = n.get("nivel") or 0
                try:
                    niv_rival = int(niv_rival)
                except (TypeError, ValueError):
                    niv_rival = 0
                if niv_rival > 0 and niv_rival != ctx.nivel_rival:
                    ctx_n = replace(ctx_n, nivel_rival=niv_rival)
            if jefe_alcanzable and edges:
                # OJO: la política se importa como `P`, no como `PL`. Con `PL`
                # esto lanzaba AttributeError y el `except` lo converting en
                # False en silencio, dejando **toda** la logica del waypoint
                # desactivada sin ningun error visible. Un `except` ancho que
                # se traga la excepcion es peor que no tener la linea.
                try:
                    en_camino = P.llega_a(
                        nodos, edges, str(n.get("id")), jefe_alcanzable)
                except Exception as exc:  # noqa: BLE001
                    self_debug = f"waypoint fallo: {exc}"
                    en_camino = False
                    if __import__("os").environ.get("PL_DEBUG"):
                        import sys as _sys
                        print(f"[PL] {self_debug}", file=_sys.stderr)
                if en_camino != ctx_n.en_camino_al_jefe:
                    # `replace(ctx_n, ...)`, no `replace(ctx, ...)`: partir de
                    # `ctx` reconstruye el contexto desde cero y **descarta** el
                    # `nivel_rival` puesto arriba. Como `llega_a` da True a
                    # todo nodo de la rama del jefe (no solo al pokecenter),
                    # el veto de entrenador por nivel se desactivaba justo en
                    # los nodos donde hacía falta, sin ningún error visible.
                    ctx_n = replace(ctx_n, en_camino_al_jefe=en_camino)
            s, razon = puntuar(tipo, ctx_n)
            # Cuántos combates deja la rama hacia el jefe. El mapa es un DAG y
            # solo se recorre un camino, así que **elegir la rama con más
            # combates es la palanca de exp más grande que hay**: medido, una
            # partida ofrece 35 nodos y 20 combates y llega al gimnasio 4, y
            # otra ofrece 13 y 4 y no llega ni al primero. Sin esto el bot elige
            # nodos uno a uno sin mirar la rama y se queda sin nivel.
            if edges:
                delante = P.combates_por_delante(nodos, edges, limpio)
                extra = delante.get(str(n.get("id")), 0)
                # Los entrenadores pesan mas que cualquier otra cosa en la
                # eleccion de rama, porque son lo unico que sube a todo el
                # equipo. Una rama con dos entrenadores vale mas que una con
                # diez salvajes.
                ent = P.entrenadores_por_delante(nodos, edges, limpio)
                n_ent = ent.get(str(n.get("id")), 0)
                if n_ent:
                    extra += n_ent * 4.0
                # **La cura va por delante de los levels cuando el equipo esta
                # por debajo de la puerta del 75%.** Es la instruccion del
                # usuario (pasar por el centro antes del lider) y medido era
                # justo lo que no se cumplia: el peso de trainers (4x) se
                # llevaba al bot a las ramas sin pokecenter, y 26 equipos
                # morian contra Brock sin haber pasado por uno. Por encima del
                # 75% manda el nivel, que es la otra mitad de la regla.
                _ratio_actual, _caidos_actual, _ = _estado(equipo)
                if _ratio_actual <= UMBRAL_PUERTA_JEFE or _caidos_actual:
                    n_cur = P.centros_por_delante(nodos, edges, limpio)
                    n_centro = n_cur.get(str(n.get("id")), 0)
                    if n_centro:
                        extra += n_centro * 12.0
                if extra:
                    # El peso de la ruta tiene que **dominar** cuando falta
                    # nivel, no solo sumar. Con 1.2 por combate noembly: un
                    # entrenador puntúa 9-11, así que una rama con 5 combates
                    # extra (+6) no ganaba a un entrenador tres pasos por
                    # delante, y el bot se metía en un callejón sin salida
                    # moría en el gimnasio por 3 niveles. El mapa es un DAG: lo
                    # que no se elige en la bifurcación no se puede recuperar
                    # después. Con el equipo al nivel, la ruta deja de importar
                    # y el peso baja para no arrastrar al bot por rutas largas
                    # que ya no necesita.
                    peso_ruta = 3.5 if ctx.corto_de_nivel else 1.0
                    s += extra * peso_ruta
                    razon += f"; deja {extra} combate(s) al jefe"
            # Escalera de riesgo sobre el score **final**, ya con el bono de
            # ruta dentro. Sin esto el unico efecto era bajar un peso de
            # 0.5-2.0 que el bono de 60-300 tapaba siempre: medido en 24 runs,
            # el bot elegia el entrenador de riesgo 13 de 13 veces, igual que
            # el control. Los jefes son tipo `jefe`, no `entrenador`, asi que
            # esto no toca los gimnasio.
            if EXP["escalera_riesgo"] and tipo == "entrenador":
                _peso_ri, pen_ri, _motivo_ri = riesgo_entrenador(ctx_n)
                if pen_ri:
                    s += pen_ri
                    # Solo la cifra: el **por que** ya esta en el motivo de
                    # `puntuar`, y escribirlo otra vez salia duplicado en el log
                    # ("... deja 34.0 combate(s) al jefe; entrenador de riesgo:
                    # 2 món(s) en pie -140; entrenador de riesgo: 2 món(s) ...").
                    razon += f"; -{abs(pen_ri):.0f} de penalización por riesgo"
            # H11: veto por nivel sobre el score final, misma causa que la
            # escalera. El -4.0 de `puntuar()` no perdía nunca contra el bono
            # de ruta; el -400 sí. Guía: level lead 1+ por encima
            # (https://pokelike-guide.fr/en/normal/improving-your-team/).
            # No es veto duro: si es el único nodo se pelea igual.
            if EXP.get("veto_nivel", True) and tipo == "entrenador":
                _vn_peso, pen_nv, _mot_nv = veto_nivel_entrenador(ctx_n)
                if pen_nv:
                    s += pen_nv
                    razon += (f"; -{abs(pen_nv):.0f} de penalización "
                              f"por veto de nivel")
            punt.append((s, n, razon))
        if punt:
            break

    if not punt:
        primero = next((n for n in nodos if n.get("clickable")), None)
        if primero is not None:
            return P.Decision("nodo", primero.get("atajo"),
                              "nodo clicable por descarte (sin ruta conocida)",
                              tipo=(P.tipo_de_estado(primero.get("tipo"))
                                    if primero.get("tipo")
                                    else P.tipo_de_nodo(primero.get("sprite", ""))))
        return P.Decision("nodo", None, "no hay nodos clicables", tipo="ninguno")

    mejor_s, mejor, mejor_razon = max(punt, key=lambda x: x[0])
    tipo_mejor = (P.tipo_de_estado(mejor.get("tipo")) if mejor.get("tipo")
                  else P.tipo_de_nodo(mejor.get("sprite", "")))
    # **H17: la tabla de TODOS los candidatos, no solo el ganador.**
    #
    # Antes el log de una pantalla de decisión traia un único score, el del nodo
    # elegido. Preguntar *"qué rama le gana al entrenador en la apertura"* con
    # eso obligaba a emparejar prosa con regex para reconstruir los candidatos,
    # y eso ya salió mal tres veces en este repo: tres extracciones del mismo log
    # dieron +0,5, +0,9 y +2,2 niveles de shortfall, y solo una podía ser cierta.
    #
    # Aqui se escribe la tabla entera en el propio motivo de la decisión, con el
    # score **final** de cada nodo (ya con el bono de ruta dentro, y con la
    # escalera de riesgo y el veto de nivel aplicados). Se ordenan de mayor a
    # menor y se recortan a 6: las pantallas del juego ofrecen 2-5 nodos, asi que
    # el recorte no pierde nada, y en el peor caso (un mapa con muchos) lo que se
    # pierde es el mas bajo, que no es el que gana.
    _opc = " ".join(
        f"{_tipo(n)}={s:.0f}"
        for s, n, _r in sorted(punt, key=lambda x: -x[0])[:6])
    return P.Decision("nodo", mejor.get("atajo"),
                      f"{tipo_mejor} score={mejor_s:.1f} ({mejor_razon})"
                      + (f" | mapa: {info_mapa}" if info_mapa else "")
                      + f" | plan: {plan.resumen()}"
                      + f" | opc: {_opc}",
                      tipo=tipo_mejor)


# -------------------------------------------------------------- orden de equipo
def orden_para_jefe(equipo: list[dict], plan: Plan) -> list[str]:
    """Orden contra el jefe: mejor contragolpe y mejor aguante, al frente.

    Va por delante el món que (a) pegue a 2x contra el rival y (b) más aguante.
    En cabeza, y no solo el mejor en tipo, porque contra un líder lo que mata es
    la vida que aguanta mientras los demás pegan.
    """
    if not equipo:
        return []
    con_poder = []
    for m in equipo:
        tipos = m.get("tipos") or []
        if not tipos or (m.get("ps") or 0) <= 0:
            continue
        atk = max((mult(t, r) for t in tipos for r in plan.tipos), default=1.0)
        # El aguante se mide con el eje **del rival contra nosotros**, o sea
        # `mult(r, t)`: lo que nos pegan. Estaba como `mult(t, r)`, que es el
        # eje ofensivo, y con eso un món inmune a Veneno puntuaba 2.0 de
        # "aguante" cuando en realidad no le pueden tocar. Como el orden se
        # decide por `(atk, aguante, vida)`, un error en el aguante colocaba al
        # delantero equivocado justo contra los jefes de tipo único.
        aguante = min((mult(r, t) for t in tipos for r in plan.tipos), default=1.0)
        vida = (m.get("ps") or 0)
        con_poder.append((atk, aguante, vida, m.get("nombre")))
    if not con_poder:
        return [m.get("nombre") for m in equipo if m.get("nombre")]
    # Prioridad: que pegue (atk desc), que aguante (aguante desc), y luego los
    # que conserven más vida. El Principal va al frente si puede con el rival.
    con_poder.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    orden = [x[3] for x in con_poder if x[3]]
    # Los caídos y los que no tienen tipo al final, en su orden original.
    for m in equipo:
        n = m.get("nombre")
        if n and n not in orden:
            orden.append(n)
    return orden

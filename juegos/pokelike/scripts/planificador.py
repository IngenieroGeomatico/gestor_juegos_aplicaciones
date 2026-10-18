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

**3. El listón no se puede alcanzar, y eso ya no es un ajuste de codigo.**
Medido sobre 1830 pantallas por debajo del listón (`medir/hay_exp_que_sirva.py`):
el rival más fuerte que el juego ofrece está de media **8 a 11 niveles por debajo
del listón**, y solo el 2% de las veces está siquiera por encima del propio
equipo. O sea que el deficit de ~5,9 niveles **no lo cierra ninguna politica de
pesos**: no hay experiencia a esa altura. Consecuencia practica, y es la que
gobierna el bot: **entrar al gimnasio por debajo de nivel pero entero**. La
vida es el unico separador medido; el nivel es ruido al lado.

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
# entrara 3 por debajo en todas las details, que es justo lo que hay que
# evitar. Si un 2x no basta para ganar 3 niveles de disadvantage, no es un 2x
# que valga.
#
# Con `MARGEN_BASE = 0` el liston es la **paridad exacta** y no un rango:
# `nivel_min == nivel_max` siempre, y el unico ajuste que existe es el +2 de
# `nivel_min_para` cuando *todo* el equipo esta a x0.5 o menos contra el rival
# (ahi el 2x esta del lado equivocado). Los comentarios que describen un margen
# por tipo de 3 niveles describen un comportamiento que este codigo **no**
# tiene: la rama que lo implementaba era un no-op con `MARGEN_BASE = 0`.
#
# Y la paridad estricta es inalcanzable en la practica, pero el arreglo no es
# bajar el liston: es que **no hay experiencia a esa altura** (ver punto 3 del
# modulo). El deficit no lo cierra ningun peso; lo que se decide es si se entra
# con el equipo entero o gastado.
MARGEN_BASE = 0

# Flags de experimento, leidos del entorno. Van en un diccionario y no en
# variables sueltas porque sobreescribir `globals()[nombre]` desde un bucle
# era fragil (un nombre mal escrito creaba un atributo fantasma en vez de
# fallar). Ver `experimento.py`.
#
# Todos son **booleanos**. La rama `else: float(v)` era inalcanzable (los
# defaults son `bool`, asi que `isinstance` siempre era cierto) y hacia creer
# que se podia declarar un flag numerico aqui; no se puede. Para un peso
# numerico hay una constante con `os.environ` propio.
def _flags_entorno() -> dict:
    out = {"veto_tipo": False, "cobertura": False, "escalera_riesgo": True,
           "veto_nivel": True, "item_huecos": False,
           "captura_por_nivel": False}
    for k in out:
        v = os.environ.get(f"PKL_{k.upper()}")
        if v is None:
            continue
        out[k] = v.strip().lower() in ("1", "true", "si", "yes")
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
    """Listón de entrada al jefe, ajustado **solo a la baja del lado malo**.

    Lo que hace hoy, con `MARGEN_BASE = 0`:

    - hay un 2x claro contra el rival -> listón = paridad (sin descuento)
    - **todo** el equipo a 0.5x o menos -> listón = paridad + 2
    - cualquier otro caso           -> listón = paridad

    El descuento por 2x que describe la version anterior de este comentario
    (3 niveles por debajo) **nunca estuvo activo**: `plan.nivel_min -
    MARGEN_BASE` con margen 0 es `plan.nivel_min`, identico al `return` de
    abajo. O sea que la rama era un no-op que solo existia para explicar un
    margen que el codigo no concedia. Se conserva la rama (es explicita y no
    cuesta nada) pero sin prometer un descuento que no ocurre.
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

# **H25: con el equipo corto y sin cura, al entrenador no se le da el bono de
# exp.** El bono de ruta (`extra * peso_ruta`, ×3,5 mientras falte nivel) se
# suma **después** del peso base, y vale 60-300; por eso el entrenador (34) le
# gana a la captura (60) en la puntuación final aunque su peso sea menor: el 18-10
# el entrenador que mató la run salió con `score=85.0` con la captura en la misma
# pantalla. Un equipo de 2 que pierde una pelea no tiene red: es GAME_OVER.
# El valor es una constante con `os.environ` propio (los `EXP` son booleanos) para
# poder hacer el A/B con 0 en el brazo de control sin tocar código.
PENALIZACION_ENTRENADOR_EQUIPO_CORTO = float(
    os.environ.get("PKL_PENALIZACION_ENTRENADOR_EQUIPO_CORTO", "-60")
)
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
UMBRAL_RIESGO_ALTO = 0.50    # riesgo: 1 món en pie, pelear es perder la run
UMBRAL_RIESGO_MEDIO = 0.75   # riesgo: 2 en pie, se gana de milagro
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


# **H18 · RETRACTADO antes de mirar datos. La premisa era falsa.**
#
# La idea era subir el peso de curar (50/58) por encima de capturar (60). Pero
# el log del propio bot dice `centro score = 100.0` en 37 pantallas y
# `jefe score = -1.0` en 135: el centro **ya** puntuaba mas que cualquier otra
# cosa, y subirlo no cambia ninguna decision. El peso no era la restriccion.
# El flag y su peso se conservan apagados (`default 0`) porque son inocuos y
# permiten repetir la medida; la rama vive en `puntuar`.
CURA_ANTE_JEFE = os.environ.get("PKL_CURA_ANTE_JEFE", "0").strip().lower() in (
    "1", "true", "si", "yes")
# Por encima de PESO_CAPTURA (60) a proposito. **No** sube solo si
# PESO_CAPTURA sube: es un literal, y el comentario anterior decia lo
# contrario. Mantenerlos separados evita el acoplamiento silencioso.
PESO_CURA_ANTE_JEFE = float(os.environ.get("PKL_CURA_ANTE_JEFE_PESO", "62"))


# **H18-b · RETRACTADO antes de mirar datos.** Relajar el veto de entrenador de
# +1 a +3 cuando falta nivel. El veto dispara en el **7%** de las runs (medido
# con `medir/alcance_mecanismo.py`), o sea que como maximo 8 del lote lo
# recibirian y el efecto teorico era d=0,07. Sin potencia por construccion: es
# un mecanismo marginal, no una causa. Se deja el flag apagado.
VETO_XP = os.environ.get("PKL_VETO_XP", "0").strip().lower() in ("1", "true", "si", "yes")
# Margen que se concede sobre el nivel del equipo. +1 es el veto de siempre; +3
# deja entrar al Ace Trainer dos niveles por encima del equipo.
VETO_XP_MARGEN = int(os.environ.get("PKL_VETO_XP_MARGEN", "3"))


# Cuanto vale un pokecenter que la rama deja por delante. Va **aparte** del
# coste, y con cualquier flag nunca se resta: el pokecentro es lo que el
# equipo roto necesita, asi que restarlo era penalizar la unica salida buena.
#
# Antes valia 12 y estaba **sumado dentro de `extra`**, junto a los costes. Con
# el flag se invertia el total, de modo que un centro por delante restaba
# 12 * 3.5 = 42 puntos. Medido en `log/h20`: el pokecenter en pantalla caia de
# 100 a 16, y la rama con cura perdia frente a la rama sin cura.
PESO_CURA_POR_DELANTE = float(
    os.environ.get("PKL_CURA_POR_DELANTE_PESO", "12"))


# **H20 · RETRACTADA tras 26 runs.**
#
# La hipotesis era "con el equipo roto, la rama que gasta menos tiene que
# ganar". Lo que paso es que se cumplio **al reves de lo que hacia falta**: el
# bot recorre el mapa al doble de velocidad (10 pasos/run frente a 21), llega
# antes a los jefes y muere antes.
#
# Medido sobre las 26 runs, la prevision que se declaro antes de mirar:
#
#                      A (H20)   B (control)
#   paso al morir (med)     29          52
#   nivel maximo          11,8        18,7
#   muere sin 1a insignia   62%         31%
#   trainers elegidos   1,7/run     5,2/run
#   insignias/run          0,46        1,23   (p=0,070)
#
# Y el motivo esta medido tambien: **una pelea contra un entrenador da +2,00
# niveles y contra un salvaje +1,00** (154 peleas ganadas, medianas). H20
# restaba `combates_por_delante` a LOS DOS POR IGUAL, o sea que le decia al
# bot "descarta tambien los entrenadores", que son el doble de exp. Y §1.2 ya
# dice que la exp no se recupera: el rival esta 8-11 niveles por debajo del
# liston siempre.
#
# Lo que H20 **si** acertó: la cura por delante nunca se resta. Esa parte se
# queda y es la que arregla el bug de las 8 runs anteriores.
RUTA_POR_EXP = os.environ.get("PKL_RUTA_POR_EXP", "0").strip().lower() in (
    "1", "true", "si", "yes")
# Cuanto vale un **salvaje** por delante cuando el equipo esta roto. Se usa la
# misma escala que el bono de siempre (`peso_ruta = 3.5` por combate cuando
# falta nivel), para que las dos ramas hablen el mismo idioma: con 3.5 el
# definitivo es `coste - 3,5 x salvajes`, y el trainer conserva su prima
# entera (4x, que ya va dentro de `coste`).
PESO_POR_NIVEL_EXP = float(os.environ.get("PKL_POR_NIVEL_EXP", "3.5"))


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
    # ¿Este nodo está en el camino obligatorio al jefe? (waypoint tipo pokecenter)
    en_camino_al_jefe: bool = False
    # ¿Hay algún pokecenter accesible ahora mismo?
    hay_cura_disponible: bool = False
    caidos: int = 0
    # El mejor contragolpe contra el rival que toca, y con qué vida llega. Si
    # viene por debajo del **50 %** de PS, el món que puede ganar la pelea entra
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
    # ¿Ya se ha cazado en esta pantalla? El libro de jugadas es
    # "captura uno al principio y luego a por nivel", asi que la primera captura
    # tiene prioridad sobre cualquier otra cosa, incluso sobre el entrenador.
    capturas_pantalla: int = 0


def _niveles(equipo: list[dict]) -> list[int]:
    return [m.get("nivel") or 0 for m in equipo]


def _estado(equipo: list[dict]) -> tuple[float, int, int]:
    """(ratio medio de PS, caídos, vivos) del equipo.

    **El PS que llega aquí tiene que ser el REAL**, no el porcentaje del HUD.
    El HUD marca 100 a un món caído, y H19 cometió justo eso: leía el equipo
    crudo para decidir si el equipo estaba roto, de modo que el instrumento
    decía "equipo entero" en el mismo paso en que la traza decía
    `Bulbasaur:0%`. Un instrumento que describe mal el mundo es peor que no
    tenerlo. El bot llama a `equipo_con_tipos()` por eso.
    """
    ratios = [(m.get("ps") or 0) / max(m.get("ps_max") or 1, 1) for m in equipo]
    caidos = sum(1 for m in equipo if (m.get("ps") or 0) <= 0)
    vivos = sum(1 for m in equipo if (m.get("ps") or 0) > 0)
    return (sum(ratios) / len(ratios) if ratios else 0.0, caidos, vivos)


def equipo_roto(equipo: list[dict]) -> bool:
    """¿El equipo no puede pagar más peleas? Caído, o por debajo de la puerta.

    El corte es el mismo que el de emergencia de `puntuar` (`caidos >= 1 or
    ratio <= UMBRAL_PUERTA_JEFE`), y **no** una-media-corta: un solo món a 0
    deja al equipo con cinco líneas de vida, y la pelea se decide por el món
    que entra primero, no por la media.
    """
    ratio, caidos, _ = _estado(equipo)
    return bool(caidos >= 1 or ratio <= UMBRAL_PUERTA_JEFE)


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
    # **H18: el veto se relaja SOLO cuando el jefe ofrece y falta nivel.**
    #
    # Medido en 225 runs: con el jefe a la vista y deficit de 5,3 niveles, el
    # bot aplaza, se va a buscar exp y VUELVE CON EL MISMO NIVEL (-0,0). No es
    # que expire mal: es que no puede ganar nivel, porque la unica fuente de
    # exp de verdad son los entrenadores por encima del equipo y este veto los
    # prohibe. Pelea solo con sus pares (2,5 combates por bucle) y no saca nada.
    #
    # La cadena entera esta medida:
    #   jefe pide liston 20 -> equipo en 14,7 -> aplaza
    #   -> para cerrar 5,3 haria falta pelear 5 niveles por encima
    #   -> el veto (equipo+1) lo impide -> exp ~0
    #   -> entra igual, al mismo nivel, y pierde el 69% de las veces
    #
    # El veto protege de perder la run, pero cuando el jefe es la unica salida
    # y el deficit no se cierra, entrar por debajo del nivel ES perder la run.
    # Se esta pagando un coste que ya se esta pagando. Ahi el veto esta
    # estorbando, y este es el unico sitio donde se relaja: con deficit
    # (`corto_de_nivel`). Fuera de ahi el veto se queda como estaba.
    margen = VETO_XP_MARGEN if (VETO_XP and ctx.corto_de_nivel) else 1
    if ctx.nivel_rival > 0 and tope_equipo and ctx.nivel_rival > tope_equipo + margen:
        return (PESO_VETO_NIVEL, PENALIZACION_VETO_NIVEL,
                f"entrenador vetado: rival Nv{ctx.nivel_rival} supera al "
                f"el nivel del equipo (Nv{tope_equipo:.0f}+{margen})"
                + (" | deficit al jefe: se gasta riesgo en exp" if margen > 1
                   else " — no es exp, es riesgo"))
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


def tipos_sin_respuesta(equipo: list[dict], tipos_ruta: set[str]) -> list[str]:
    """Tipos que hay en la ruta y contra los que el equipo no tiene respuesta.

    Vive fuera de `elegir` a proposito: la version anterior de esto estaba
    **dentro** de `if EXP["cobertura"] and "capturar" in tipos_disponibles`, y
    `tipos_disponibles` solo contiene valores del vocabulario **interno**
    (`batalla`, `entrenador`, `cura`...), entre los que `"capturar"` no existe.
    La condicion era por lo tanto siempre falsa y toda la rama de cobertura
    estaba muerta sin dar error. El filtro de V1 (veto por tipo) ya dio
    p=0,020 a favor de desactivarlo, asi que esto no se usa todavia: se deja
    como funcion medible, no como ramaWeights que nadie puede alcanzar.
    """
    return sorted(t for t in tipos_ruta if not _equipo_responde_a(equipo, t))


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


# Lo que resta pelear en el mapa de la Liga. Va muy negativo a proposito: en ese
# mapa los nodos de pelea sacan 53-138 y los de cura 50, asi que un descuento
# suave los dejaria ganando igual. -60 los manda por debajo de `item` (34) y de
# `cura` (50) sin llegar al rango de las penalizaciones por riesgo (-110, -140),
# que son para casos de vida o muerte.
PENALIZACION_PELEA_LIGA = -60.0


def es_mapa_de_liga(plan: Plan) -> bool:
    """¿Estamos en el mapa del Alto Mando? (las insignias ya no suben de 8).

    El `>=` es deliberado: si el contador leyera 9 por un desfase, la regla
    tiene que seguir activa en el mapa donde mas duele, no apagarse justo ahi.
    """
    return plan.insignias >= len(nombres_jefes(plan.region))


def puntuar(tipo: str, ctx: Contexto, es_captura: bool = False) -> tuple[float, str]:
    """Puntúa un tipo de nodo con el plan a la vista.

    La idea es no mirar "qué es este nodo" sino "qué me falta": nivel, vida o
    el listón del jefe. Por eso el mismo nodo `batalla` vale 10 con el equipo
    por debajo de nivel y 4 con el equipo a nivel.

    `es_captura` dice si **este** nodo es el de captura (`catch` del juego).
    Hace falta porque `catch` y `battle` se traducen los dos a `"batalla"`
    (ver `politica.TIPO_ESTADO`) y sin esto los dos entraban por la misma rama
    y los dos recibian `PESO_CAPTURA`: el desempate lo acababa decidiendo el
    bono de ruta y el bot se iba a cazar en vez de a capturar. Medido en el
    lote de 121 runs: 196 pantallas con `catch` disponible y
    `capturas_pantalla == 0` en las que eligio `battle`. De ahi salen las 28
    runs que mueren antes del paso 30 con un unico món a nivel 5-9.

    `None` = el juego no dio el tipo crudo, y se puntúa como antes.
    """
    equipo, plan = ctx.equipo, ctx.plan
    if not equipo:
        return (PESO_BATALLA_NIVEL, "equipo vacío: que caiga algo")

    # **H24: en el mapa de la Liga, pelear es perder.**
    #
    # El Alto Mando son 4 combates **consecutivos y sin cura entre ellos** (~14 s
    # de uno a otro): el PS no se recupera dentro, asi que cada pelea de este
    # mapa se paga en la unica moneda que no se puede reponer. Y no compra nada,
    # porque se llega por encima del rival (el mapa es el ultimo y el plan ya
    # pide paridad).
    #
    # Medido en las 3 runs que llegaron a la Liga en `lote_defensa2`, y es lo que
    # las mato. No fue el orden —run 1 gano Lorelei, Bruno y Agatha con el orden
    # estatico—, fue con que llegaron:
    #   run 1: entra con Aerodactyl 0/168 y Golduck 78/186 -> muere en Lance
    #   run 3: entra con Gengar 47/135 -> Lorelei le mata 5 de 6 -> muere en Bruno
    # Y el bot lo decia al pasar: "se entra igual (1 caido(s), carry flojo (41%))".
    # Se pasaba el mapa cazando: 29 batallas y 29 entrenadores en una sola run,
    # con el nodo de cura disponible y sin reservar para el final.
    #
    # **La captura se salva si faltan cuerpos** (R2: no se veta por tener pocos
    # mons): el veto es contra la pelea inutil, no contra el món que falta.
    if tipo in ("batalla", "entrenador") and es_mapa_de_liga(plan):
        if not (es_captura and len(equipo) < 4):
            return (PENALIZACION_PELEA_LIGA,
                    "liga: pelear gasta PS y no da nivel; se va al jefe")

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
        # **La medicion que importa, y que H18 leyo al reves.** De 934 peleas con
        # foto completa (no 155; estas son todas, tambien de ruta):
        #
        #   vida 0-50%  -> gana el 25,0%
        #   vida 50-75% -> gana el 88,5%
        #   vida >95%   -> gana el 99,7%
        #
        # Y con algun món a 0 la victoria baja del 95,9% al 45,9%. El nivel y
        # los tipos **no** separan casi nada (por debajo del rival se gana el
        # 56,3%, al nivel o mas el 90,4%): lo que separa es llegar entero.
        #
        # **El peso de curar no es la restriccion.** H18 lo subiria por encima
        # de capturar y resulto ser un no-op: el log da `centro score = 100.0`
        # en 37 pantallas, o sea que el centro ya gana a todo. Lo que hace que
        # el equipo llegue roto es la **distancia**: de las 178 peleas
        # empezadas con el equipo roto, **0 de 178 tenian un pokecenter en
        # pantalla**. El bot cura bien cuando el centro esta a la vista (493
        # pantallas con cura, 493 veces fue a curar) y luego se gasta el
        # equipo en el tramo de peleas hasta el gimnasio. Eso lo ataca H20.
        if ctx.en_camino_al_jefe:
            if caidos:
                # **H18, retractado**: subir este peso por encima de capturar
                # era la solucion y resulto ser un no-op (el centro ya
                # puntua 100 y gana a todo). Se conserva la rama porque el
                # camino con jefe delante y caidos es real; lo que no se puede
                # es creer que 62 frente a 58 cambia algo.
                #
                # **El peso va en el mensaje**: sin la marca, el brazo A y el B
                # imprimen la misma linea y no hay forma de comprobar por el log
                # que el flag llego. Un mecanismo que no se puede verificar no se
                # puede dar por bueno, y ya se ha perdido una tanda entera asi.
                peso = PESO_CURA_ANTE_JEFE if CURA_ANTE_JEFE else 58.0
                marca = " | H18: cura por encima de capturar" if CURA_ANTE_JEFE else ""
                return (peso,
                        f"curar: paso obligatorio hacia el jefe y hay "
                        f"{caidos} caido(s) (peso {peso:.0f}){marca}")
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
            # **Segunda rama de curacion, y tambien estaba por debajo de
            # capturar.** PESO_CURA_CAIDOS=50 frente a PESO_CAPTURA=60. La otra
            # rama (la del waypoint) pesaba 58, y las dos perdian. Arreglar solo
            # una habria dejado el bug en la otra mitad de los casos.
            peso = PESO_CURA_ANTE_JEFE if CURA_ANTE_JEFE else PESO_CURA_CAIDOS
            marca = " | H18: cura por encima de capturar" if CURA_ANTE_JEFE else ""
            return (peso,
                    f"curar {caidos} caído(s): el jefe es salida forzada "
                    f"(peso {peso:.0f}){marca}")
        if ctx.carry_ps < 65.0:
            return (PESO_CURA_BAJO + 8.0,
                    f"curar: el carry está al {ctx.carry_ps:.0f}% "
                    "(es el que tiene que llegar entero)")
        return (PESO_CURA_SANO,
                f"curar: carry al {ctx.carry_ps:.0f}%, no hace falta")

    if tipo == "jefe":
        # "Listo" = sin caidos y con la media de nivel en el listón (paridad
        # exacta: con `MARGEN_BASE = 0`, listón == nivel del rival).
        #
        # Pero estar "listo" no es motivo para pelear YA. El jefe solo se
        # acepta cuando es la unica salida que queda; si hay Trainer o batalla
        # disponibles se sigue subiendo nivel.
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
            if ctx.carry_debil:
                # El mejor contragolpe por los suelos.
                motivo.append(f"carry flojo ({ctx.carry_ps:.0f}%)")
            if medio < liston:
                # **"APLAZADO" no significa que no se entre.** El jefe es
                # salida forzada y lo mas que puede hacer el -1.0 es ganar a
                # los nodos que puntúan menos (2-12) cuando hay alguno en
                # pantalla. El log decia "se busca mas exp" y el bot entraba en
                # el 98% de los casos: el texto afirmaba lo contrario de lo que
                # hacia. Ademas,aplazar no compra nada: entre el primer y el
                # ultimo aplazo del mismo gimnasio el nivel ganado es **-0,0**.
                # Lo que de verdad separa ganar de perder es llegar entero.
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
        # `es_captura is not False` y no `es_captura`: `None` significa que el
        # juego no dio el tipo crudo, y en ese caso se puntua como se puntuaba
        # antes. La diferencia entre `False` (es una batalla suelta) y `None`
        # (no se sabe) es la que arregla el empate sin romper los mapas sin
        # tipo.
        if ctx.capturas_pantalla == 0 and es_captura is not False:
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
            if len(equipo) < 2:
                # **Con UN món sí, con dos no.** Este era `< 3` y fue un
                # desastre medido. La premisa del arreglo original —"con un
                # solo món la exp es inalcanzable: si caes, se acabó"— era
                # cierta para 1 y **falsa para 2**: con dos móns el bot ya
                # aguanta la ruta, así que la captura sí es alcanzable y lo que
                # hace es **robar la exp de equipo**, que es la única que sube
                # a todo el equipo a la vez.
                #
                # La captura da experiencia **solo al món capturado**; el
                # entrenador da **+2 a todo el equipo**. Forzar capturas con
                # equipo de 2-3 metió al bot en la economía mala, y se ve:
                #
                #     entrenadores/run   8,1 -> 7,3
                #     media insignias   1,40 -> 0,95
                #     nivel al gimnasio -3 a -8   (7 de 7 mediciones)
                #     0 insignias       34% -> 50% de las runs
                #
                # y las muertes se Concentraron donde tiene sentido: **10 de las
                # muertes fueron contra Brock**, el primer gimnasio.
                #
                # El arreglo que sigue haciendo falta es el suyo: con 1 món, sin
                # captura, la partida se acaba en el paso 22. Ese caso se
                # conserva; el de 2 móns, no. Lo que hay que vigilar es que el
                # equipo de 2 no vuelva a ser 1 món empobrecido: eso lo vigila
                # `elegir_captura` por nivel y stats.
                return (PESO_CAPTURA,
                        f"capturar: equipo de {len(equipo)}, hacen falta "
                        f"cuerpos antes que nivel")
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
        # porque no se puede evitar y porque es la única forma de pasar. El
        # veto solo llega a nodos `entrenador`, que por definición no son jefe.
        #
        # Antes entraba a ciegas: medido, se perdió contra un
        # `team-rocket (Poison/Normal)` con Krabby x1, Ivysaur x0.5 y Clefairy,
        # sin nada que le ganara.
        tipos_riv = _tipos_del_entrenador(ctx)
        # **V1 lo cerró como contraproducente y `PKL_VETO_TIPO` esta apagado por
        # defecto.** 111 runs en tres brazos: media de insignias 0,64 con el
        # veto contra 1,62 sin el (p=0,020) y 1,43 con el veto mas cobertura
        # (p=0,024). El veto apartaba al bot de la unica fuente de exp que sube
        # a todo el equipo y no arreglaba el problema de fondo. La rama se
        # conserva apagada para poder repetir la medida, no como regla activa.
        if tipos_riv and EXP["veto_tipo"]:
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
            # **H25: con el equipo corto, el entrenador no.**
            #
            # El 18-10, **11 de las 13 runs que murieron sin insignia lo hicieron
            # con `equipo=2`**, y el patrón entero se ve en el log de una:
            #
            #     DEC nodo nodo=n1_0 tipo=entrenador equipo=2 vivos=2 niv=4-5
            #              disponibles=trainer,catch
            #              razon=entrenador score=85.0 (mucha exp, faltan ~10)
            #     >>> COMBATE PERDIDO contra Firebreather! | 0-1
            #     resultado : GAME_OVER
            #
            # Tenía una captura en la misma pantalla y eligió al entrenador. Su
            # peso base (34) **pierde** contra el de la captura (60), pero el bono
            # de ruta se suma después y mientras falte nivel va por 3,5: el
            # entrenador acabó en 85 y la captura no llegó. Y el bucle se refuerza
            # solo: con 2 móns la captura pierde, así que no se ganan cuerpos, así
            # que se sigue en 2 hasta que una pelea perdida termina la run.
            #
            # `riesgo_entrenador` no cubre este caso **a propósito**: su escalera
            # pide `caidos >= 1` y su nota razona que "un equipo de un solo món
            # sano es el inicio normal de la partida y ahí pelear es justo lo que
            # hay que hacer". Es verdad para pelear en general y falso para elegir
            # **entrenador habiendo captura**: la captura da el mismo nivel de pelea
            # y además un món, y R1 dice que si se puede evitar al entrenador, se
            # evita. Perder con 3+ móns deja equipo; perder con 2 no.
            #
            # No es veto y no toca `captura_por_nivel`: esto **resta al
            # entrenador**, no empuja a la captura, así que la pelea salvaje sigue
            # siendo la fuente de exp normal y si el entrenador es el único nodo de
            # la pantalla se pelea igual. Lo que se mide es solo el orden cuando
            # hay alternativa.
            if len(equipo) < 3 and not ctx.hay_cura_disponible:
                return (PESO_ENTRENADOR_SANO + 2.0
                        + PENALIZACION_ENTRENADOR_EQUIPO_CORTO,
                        f"entrenador aplazado: {len(equipo)} món(s) y una pelea "
                        f"perdida es GAME_OVER (faltan ~{falta:.0f} de nivel, y la "
                        f"captura de esta pantalla da el món que falta)")
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

    def _es_captura(n) -> bool | None:
        """¿Este nodo concreto es el de captura, y no una batalla suelta?

        `catch` y `battle` se traducen los dos a `"batalla"`, así que el tipo
        interno no los distingue. Se mira el **crudo del juego** (`tipo`), que
        es lo unico que sabe cual de los dos es.

        Devuelve `None` cuando el juego no dio tipo, y `puntuar` lo trata como
        "no lo sé": se comporta como antes. Un dato que falta no debe cambiar
        la decisión, porque aqui lo que falta es lo que hace el bot.
        """
        crudo = str(n.get("tipo") or "").strip().lower()
        if not crudo:
            return None
        return crudo == "catch"

    tipos_disponibles = [_tipo(n) for n in nodos
                         if n.get("clickable")
                         and str(n.get("id")) in ids_disponibles]

    # **Cobertura de tipos.** El flag `PKL_COBERTURA` esta apagado por defecto: V1
    # lo midio contra el veto por tipo (p=0,020 a favor de desactivar) y B vs C
    # fue p=0,837, o sea que el brazo de cobertura no aportaba nada medible.
    # Se queda la funcion `tipos_sin_respuesta` para poder medirla, pero **no**
    # hay rama en `puntuar` que la consuma: una rama inalcanzable es peor que
    # ninguna, porque parece una regla y no lo es.

    # ¿El equipo roto? Se calcula **una vez**, con el PS real, antes del bucle:
    # el valor no cambia dentro de la pantalla (no se pelea al puntuarla) y
    # H19_leía el HUD crudo aquí, por lo que daba "sano" con un món a 0.
    roto = equipo_roto(equipo)

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
        en_camino_al_jefe=bool(extra.get("en_camino_al_jefe")),
        hay_cura_disponible=("cura" in tipos_disponibles),
        caidos=_estado(equipo)[1],
        tipos_por_sprite=dict(extra.get("tipos_por_sprite") or {}),
    )

    punt: list[tuple[float, dict, str]] = []
    # **Regla 2 como prioridad, no como puntuacion.** Con el equipo corto la
    # captura no compite: es un paso previo. El motivo es que el bono de ruta
    # (`coste * 3.5`, hasta +500 con una rama larga) se leia como "mas exp",
    # pero con un solo món esa exp es **inalcanzable**: si el bot cae, la
    # partida se acaba y no hay nadie que la gaste. Medido el 14-10 con el
    # peso ya arreglado: `opc: batalla=558 batalla=434` — el nodo de captura
    # puntua 60 y el de batalla 15, y aun asi gana el de batalla porque su
    # rama tiene 138 combates mas (483 puntos de bono por 45 de diferencia).
    #
    # De ahi salen las 28 runs que mueren antes del paso 30 con un unico món
    # a nivel 5-9. Se marca aqui y se decide despues del bucle, que es donde
    # se sabe si habia un nodo de captura pendiente.
    captura_prioritaria: tuple[dict, str] | None = None
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
            s, razon = puntuar(tipo, ctx_n, es_captura=_es_captura(n))
            if (_es_captura(n) is True and ctx.capturas_pantalla == 0
                    and len(equipo) < 2):
                captura_prioritaria = (n, razon)
            # Cuántos combates deja la rama hacia el jefe. El mapa es un DAG y
            # solo se recorre un camino, así que **elegir la rama con más
            # combates es la palanca de exp más grande que hay**: medido, una
            # partida ofrece 35 nodos y 20 combates y llega al gimnasio 4, y
            # otra ofrece 13 y 4 y no llega ni al primero. Sin esto el bot elige
            # nodos uno a uno sin mirar la rama y se queda sin nivel.
            #
            # **PERO solo si al equipo le sirve la exp.** El bono es
            # incondicional, y con el equipo roto premia una rama que le va a
            # gastar la vida antes de llegar al jefe. Ver `bono_ruta`.
            if edges:
                # **COSTE y BENEFICIO van separados, y no es cosmetico.**
                #
                # Antes los tres se sumaban en un solo `extra` y despues el signo
                # de `extra` se invertia con H20. Como un pokecenter por delante
                # estaba **sumado** ahi, invertir el total venia a restar la
                # cura: la rama que passa por el centro salia penalizada. O
                # sea que el mecanismo que se escribio para "elegir la rama que
                # gasta menos" hacia justo lo contrario en el caso que mas le
                # importaba, que es el equipo roto.
                #
                # El dato que lo delata son las cifras del propio marcador: los
                # valores de `extra` en `log/h20` llegaban a **88, 105 y 56**, y
                # `combates_por_delante` esta topado en 8. Un numero de peleas
                # no puede ser 105: era 12 por cada pokecenter de la rama.
                # Los dos pesos mezclados son 4.0 (entrenador) y 12.0 (centro), y
                # el 12 solo puede venir de un pokecentro.
                #
                # - `coste` = peleas que el equipo tiene que **pagar** para llegar
                #   al jefe. Es lo unico que H20 puede restar.
                # - `cura` = pokecenters que la rama **ofrece**. Es un
                #   beneficio, y con el equipo roto vale mas que nunca, asi que
                #   **nunca** se resta: se suma siempre, y mas fuerte roto.
                delante = P.combates_por_delante(nodos, edges, limpio)
                coste = delante.get(str(n.get("id")), 0)
                # Los entrenadores pesan mas que cualquier otra cosa en la
                # eleccion de rama, porque son lo unico que sube a todo el
                # equipo. Una rama con dos entrenadores vale mas que una con
                # diez salvajes.
                ent = P.entrenadores_por_delante(nodos, edges, limpio)
                n_ent = ent.get(str(n.get("id")), 0)
                if n_ent:
                    coste += n_ent * 4.0
                # **Los salvajes van aparte**, porque H21 los penaliza y a los
                # entrenadores no: dan distinta exp (+1 nivel contra +2).
                sal = P.salvajes_por_delante(nodos, edges, limpio)
                n_salv = sal.get(str(n.get("id")), 0)
                # **La cura va por delante de los niveles cuando el equipo esta
                # por debajo de la puerta del 75%.** Es la instruccion del
                # usuario (pasar por el centro antes del lider) y medido era
                # justo lo que no se cumplia: el peso de trainers (4x) se
                # llevaba al bot a las ramas sin pokecenter, y 26 equipos
                # morian contra Brock sin haber pasado por uno. Por encima del
                # 75% manda el nivel, que es la otra mitad de la regla.
                _ratio_actual, _caidos_actual, _ = _estado(equipo)
                n_centro = 0
                if _ratio_actual <= UMBRAL_PUERTA_JEFE or _caidos_actual:
                    n_cur = P.centros_por_delante(nodos, edges, limpio)
                    n_centro = n_cur.get(str(n.get("id")), 0)
                if coste or n_centro or n_salv:
                    # El peso de la ruta tiene que **dominar** cuando falta
                    # nivel, no solo sumar: un entrenador puntúa 34, así que
                    # una rama con 5 combates extra (peso 3.5) no ganaba a un
                    # entrenador tres pasos por delante, y el bot se metía en
                    # un callejón sin salida y moría en el gimnasio por 3
                    # niveles. El mapa es un DAG: lo que no se elige en la
                    # bifurcación no se puede recuperar después.
                    #
                    # **H21 · con el equipo roto, la exp pesa mas que el gasto.**
                    #
                    # H20 hacia lo contrario y quedo retractada. Restaba
                    # `combates_por_delante` a salvo y entrenador por igual, y
                    # **no valen lo mismo**: medido sobre 154 peleas ganadas,
                    # el entrenador da +2,00 niveles y el salvaje +1,00. Al
                    # penalizar los dos igual, el bot aprendio a descartar
                    # tambien los entrenadores: 1,7/run frente a 5,2 del
                    # control, con el equipo al 60% de nivel. Y §1.2 ya dice
                    # que la exp no se recupera despues.
                    #
                    # **Lo unico que H21 toca es el SALVAJE.** El bono de ruta
                    # se aplica igual que en el control y encima se resta el
                    # salvage por delante, asi que la prima del trainer (los
                    # 4.0 por entrenador que ya van dentro de `coste`) se
                    # conserva **entera**. Medido con el flag, rama de 5 nodos:
                    #
                    #   5 salvajes   29,0 ->  8,0   (-21,0)
                    #   5 trainers   31,0 -> 13,5   (-17,5)
                    #   rama limpia  11,5 ->  8,0   ( -3,5)
                    #
                    # El trainer baja solo cuando la rama **tiene salvajes**, y
                    # baja justo lo que valen: es el mismo bonus con los
                    # salvajes descontados. Rama limpia de trainers: 0,0.
                    #
                    # La primera version hacia otra cosa: sustituia el bono
                    # entero por `n_salv*-3,5 + n_ent*+7`, con lo que el
                    # trainer **perdia 10,5 puntos** frente al control. Eso
                    # contradecía la hipotesis de frente: H21 no quiere castigar
                    # al trainer, quiere dejar de premiar al salvaje (§5.8).
                    peso_ruta = 3.5 if ctx.corto_de_nivel else 1.0
                    s += coste * peso_ruta
                    if RUTA_POR_EXP and roto:
                        s -= n_salv * PESO_POR_NIVEL_EXP
                        razon += (f"; H21: sin -{n_salv} salvaje(s) por delante "
                                  f"x{PESO_POR_NIVEL_EXP:.1f} (equipo roto; "
                                  f"{n_ent} entrenador(es) intactos)")
                    else:
                        razon += f"; deja {coste} combate(s) al jefe"
                    s += n_centro * PESO_CURA_POR_DELANTE
                    if n_centro:
                        razon += (f"; +{n_centro} pokecenter(s) por delante "
                                  f"x{PESO_CURA_POR_DELANTE:.0f}")
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

    # **La captura del equipo corto manda sobre el score.** Se comprueba que el
    # nodo marcado sea de los que se llegaron a puntuar (o sea, que la pantalla
    # lo ofrecía de verdad) antes de tomarlo.
    if captura_prioritaria is not None:
        _n, _razon = captura_prioritaria
        _id = str(_n.get("id"))
        if any(str(x[1].get("id")) == _id for x in punt):
            _opc_c = " ".join(f"{_tipo(n)}={s:.0f}" for s, n, _r
                              in sorted(punt, key=lambda x: -x[0])[:6])
            return P.Decision(
                "nodo", _n.get("atajo"),
                f"capturar {_razon} | equipo de {len(equipo)}: la captura va antes "
                f"que la ruta, porque su experiencia es inalcanzable sin equipo"
                + (f" | mapa: {info_mapa}" if info_mapa else "")
                + f" | plan: {plan.resumen()}"
                + f" | opc: {_opc_c}",
                tipo="batalla")

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

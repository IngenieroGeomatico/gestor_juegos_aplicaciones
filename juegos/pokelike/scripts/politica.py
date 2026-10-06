"""Política del bot: decide en Python, sin gastar tokens.

Cada función devuelve una `Decision` con la acción, su valor y una razón en
texto plano. La razón va al log de la run, así que la partida queda
documentada sin que un modelo tenga que leerla paso a paso.

Lo que hay que tener en la cabeza, todo medido contra el juego:

* **Los combates se auto-resuelven.** No hay selección de movimiento, ni en
  salvaje ni en entrenador: lo único que hay es `#btn-auto-battle` (tecla
  `Space`). La única forma de subir el daño de un món son los discos.
* **El chart no es el oficial.** En el del juego `Normal vs Rock` es 0.5 y
  `Electric -> Ground` es inmunidad (0). `data/chart_juego.json`.
* **Todos los golpes son especiales**: `usesSpecialAttack` compara
  `baseStats.special` contra `baseStats.spAtk` y el Pokédex no tiene `spAtk`,
  así que siempre sale `special >= 0`. El stat que pega es `special`.
* **El tipo del líder es solo la fachada.** Misty es "Agua" pero lleva
  Staryu+Starmie (Agua y Psíquico); Erika es "Fuego" pero lleva
  Tangela+Victreebel+Vileplume (Planta y Veneno). Todo se puntúa contra los
  tipos del **equipo** del rival, sacados del Pokédex.
* **Perder contra un entrenador o un líder termina la run.** Perder contra un
  salvaje no. De ahí tanto el cuidado con entrar a entrenador como el
   - trainer y jefe: perder termina la run, perder contra un salvaje no.
* **La experiencia va casi entera al delantero** y se reparte poco, así que
   - Importante quién va primero en cada pelea.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pkl_tipos as T

DATA = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------- mapa
# Sprites del mapa -> tipo de nodo. Son solo una pista: el tipo fiable es el
# que da `state.map.nodes`, y `tipo_de_estado()` lo traduce.
BATALLA = {"pokeball"}
ITEM = {"item-icon"}
CURA = {"poke-center"}
# Nodo del tutor: enseña discos (TM) y sube el tier de los ataques. No es un
# entrenador, así que antes caía en el `default` y el bot lo pelaba.
TUTOR = {"move-tutor", "move_tutor"}
INCOGNITA = {"question-mark"}
# El resto de sprites con nombre propio (brock, scientist, hiker, old-guy,
# ace-trainer, grass, fire-spitter…) son combates de entrenador.
JEFES_CONOCIDOS = {
    "brock", "misty", "lt-surge", "ltsurge", "erika", "koga", "blaine",
    "giovanni", "lance",
}

# Tipo del líder por sprite, en el **nombre canónico en español** del tipo.
# Hace falta porque el nodo de gimnasio solo trae la categoría (`"boss"`), que
# no dice nada contra el chart. Las claves van YA normalizadas: los sprites
# llevan guion (`lt-surge`) y `_norm_sprite` los quita, así que la comparación
# tiene que hacerse sobre las dos formas.
#
# Estos son los líderes de Kanto, en el mismo orden que `regiones.json`
# (Roca, Agua, Eléctrico, Planta, Veneno, *Fantasma*, Fuego, Tierra). El
# sexto no aparece en la lista de sprites del bot, y no se inventa: si el juego
# lo dibuja con otro nombre, `tipo_lider_del_mapa` devuelve `None` y quien
# llama usa `regiones.json`.
TIPO_POR_LIDER = {
    "brock": "Roca",
    "misty": "Agua",
    "ltsurge": "Electrico",
    "lt-surge": "Electrico",
    "erika": "Planta",
    "koga": "Veneno",
    "blaine": "Fuego",
    "giovanni": "Tierra",
    "lance": "Dragon",
}

# Los tipos del estado del juego tienen otros nombres que los internos. El
# estado es la fuente autoritativa (el sprite miente: "grass" es una batalla y
# "question-mark" puede ser un entrenador o un trade).
TIPO_ESTADO = {
    "start": "desconocido",
    "catch": "batalla",
    "battle": "batalla",
    "trainer": "entrenador",
    "item": "item",
    "question": "incognita",
    # El trade NO es una incógnita: es el nodo más rentable del juego (+3 niveles
    # y PS completos, lo llama "la mecánica más fuerte" la guía). Estaba
    # mapeado a `incognita` y por eso el planificador lo descartaba sin querer,
    # el mismo tipo de fallo que `cura` vs `pokecenter`.
    "trade": "trade",
    "pokecenter": "cura",
    "move_tutor": "tutor",
    "boss": "jefe",
    # El nodo `legendary` (Wegener) sí aparece en los mapas del juego y no
    # estaba mapeado: caía en `"otro"` y el planificador lo puntuaba con 2.0, la
    # nota más baja de todas. Es un combate gratis contra un món fuerte.
    "legendary": "legendario",
    # Los que salen en los estados de la Elite Four y el campeón. Antes caían
    # en `"otro"` y se trataban como nodos sin puntuación conocida.
    "rival": "jefe",
    "evilteam": "entrenador",
    "silver": "entrenador",
    "moonstone": "item",
    "levelup": "batalla",
    "magma": "entrenador",
    "mutation": "incognita",
    "reward": "item",
    "underground": "otro",
    "distortion": "incognita",
    "subexit": "otro",
}

# Tamaño máximo del equipo. Sube solo al capturar: `state.maxTeamSize` crece
# 1->2->3 en la primera ruta, sin insignias de por medio.
# El equipo es de SEIS, no de tres. La guia de la comunidad lo dice sin
# rodeos ("spreading your resources across six", y la pantalla de campeon
# muestra seis Pokemon), y el juego confirma que `maxTeamSize` crece al
# capturar. Estarlo limitando a 3 era probablemente el mayor motivo de que
# los equipos fueran tan pobres: un tercio de la cobertura posible.
MAX_EQUIPO = 6
# Tamaño mínimo del núcleo antes de dejar de cazar. El equipo se mantiene
# corto a propósito: la exp se la lleva casi toda el delantero, así que un
# cuarto món de relleno roba nivel a los que sí pegan 2x.
MIN_NUCLEO = 2
# Cuántos niveles de diferencia tolera la rotación de delantero: un món más
# bajo que esto no llega a sobrevivir una batalla y no gana exp.
NIVEL_ROTACION_MAX = 2
# Stat mínimo de un candidato para entrar en el equipo.
MIN_STATS_CAPTURA = 220

# H15 · Capturar es mas barato que rechazar. Regla del usuario: "es mejor
# capturar que rechazar"; si hay un tipo duplicado, el nodo de cambio lo saca
# fuera. La medicion que lo motivates:
#   - el mapa ofrece **5,8 nodos `catch` por run** y el bot confirma **2,07**
#     (y rechaza 1,08). Se pierde el 65% de la oportunidad.
#   - el **98% de los rechazos** son `nada util contra X`: el filtro exige
#     cobertura y el equipo no la tiene, asi que se cierra en bucle.
#   - ademas el rechazo **cuesta la pelea**: `catch-screen` tiene "Skip (flee)",
#     y huirse es no pelear, o sea perder el nivel del combate. Medido: 1,88
#     nodos de pelea por run sin combate (18%).
# El filtro de tipo se conserva como PREFERENCIA (ordena a los candidatos), no
# como rechazo: con este flag, un 0.5x entra igualmente.
CAPTURA_PERMISIVA = os.environ.get("PKL_CAPTURA_PERMISIVA", "0").strip().lower() in (
    "1", "true", "si", "yes")
# Listones antiguos, solo como respaldo si faltaran los datos reales.
NIVEL_OBJETIVO_BASE = 9
NIVEL_POR_INSIGNIA = 5
NIVEL_ELITE = 60


def tipo_de_estado(t: str | None) -> str:
    return TIPO_ESTADO.get(str(t or ""), "otro")


def proximos_jefes(region: str, insignias: int, cuantos: int = 2) -> list[str]:
    """Tipos de los próximos rivales a partir de las insignias ya ganadas.

    Devuelve el primer tipo de cada equipo, que es el que se usa como etiqueta
    cuando no se desglosa por subtipo. Para razonar en serio está
    `tipos_del_rival()`, que devuelve la lista entera.
    """
    out = []
    for i in range(insignias, insignias + cuantos):
        tipos = tipos_del_rival(region, i)
        out.append(tipos[0] if tipos else None)
    return [t for t in out if t]


def tipos_conocidos() -> list[str]:
    """Los 18 tipos del chart del juego, para reconocerlos en un texto."""
    from pkl_movimientos import tabla_chart
    return sorted(tabla_chart().keys())


def _norm_sprite(s) -> str:
    s = str(s or "").lower()
    for sep in ("-", "_", " "):
        s = s.replace(sep, "")
    return s


def tipo_de_nodo(sprite: str) -> str:
    s = (sprite or "").lower()
    if s in BATALLA:
        return "batalla"
    if s in ITEM:
        return "item"
    if s in CURA:
        return "cura"
    if s in TUTOR:
        return "tutor"
    if s in INCOGNITA:
        return "incognita"
    # Normalizado: los sprites de jefe llevan guion (`lt-surge`) y sin
    # normalizar nunca se habría encontrado con los jefes de la lista.
    if s in JEFES_CONOCIDOS or _norm_sprite(s) in JEFES_CONOCIDOS:
        return "jefe"
    return "entrenador" if s else "desconocido"


def tipo_lider_del_mapa(nodos: list[dict]) -> str | None:
    """El tipo del líder que aparece en este mapa.

    Sale del sprite del nodo de gimnasio (`brock`, `misty`, `lt-surge`…). Si el
    sprite no está en la tabla se devuelve `None`, **nunca la categoría del
    nodo**: antes aquí se hacía `n.get("tipo")`, y para un gimnasio eso es
    literalmente `"boss"`. Con `"boss"` como "tipo" el chart no dice nada
    (`utilidad_contra(["Fuego"], "boss")` devuelve `(1.0, 1.0)`), así que el
    filtro de no ser 0.5x contra el gimnasio que tocaba **no se ejecutaba** y el
    bot cazaba un Charmander con Brock detrás.

    Un `None` es la respuesta honesta: el llamador recurre a los datos de
    `regiones.json`, que son la fuente autoritativa.
    """
    for n in nodos:
        sprite = _norm_sprite(n.get("sprite"))
        if sprite in JEFES_CONOCIDOS:
            tipo = TIPO_POR_LIDER.get(sprite)
            if tipo:
                return T.normalizar(tipo)
    return None


@dataclass
class Decision:
    accion: str
    valor: str | int | None = None
    razon: str = ""
    # Para los nodos del mapa: qué tipo de nodo es. Antes el tipo solo vivía
    # dentro de `razon` y `accion` era siempre "nodo", así que el bot nunca
    # sabía con qué se enfrentaba y las ramas por tipo no se activaban nunca.
    tipo: str = ""
    # El **nombre** de lo elegido, cuando hay nombre. `valor` guarda lo que hay
    # que pulsar (un atajo), que no siempre es lo que se eligió: la guía manda
    # no cambiar el starter nunca, y sin su nombre el bot no puede cumplirlo.
    nombre: str = ""

    def __str__(self) -> str:
        v = "" if self.valor is None else f" -> {self.valor}"
        return f"[{self.accion}{v}] {self.razon}"


# ---------------------------------------------------------------- regiones
def regiones() -> dict[str, dict]:
    datos = json.loads((DATA / "regiones.json").read_text(encoding="utf-8"))["regiones"]
    return {r["region"]: r for r in datos}


def tipos_del_rival(region: str, insignias: int) -> list[str]:
    """Los tipos que trae de verdad el rival que toca (equipo, no fachada)."""
    region_datos = regiones().get(region, {})
    jefes = region_datos.get("jefes", [])
    if insignias < len(jefes):
        entrada = jefes[insignias]
    else:
        elite = region_datos.get("elite_four_datos") or []
        i = insignias - len(jefes)
        entrada = elite[i] if i < len(elite) else (region_datos.get("campeon_datos") or {})
    if not entrada:
        return []
    equipo = entrada.get("tipos_equipo") or []
    if equipo:
        return [T.normalizar(t) for t in equipo]
    return [T.normalizar(entrada["tipo"])] if entrada.get("tipo") else []


def nivel_del_jefe(region: str, insignias: int) -> tuple[int, list[int]]:
    """Nivel máximo (y todos) del rival que toca.

    El listón sale de los datos reales, no de una fórmula. Kanto: Brock 12-14,
    Misty 18-20, Lt. Surge 20-25, Erika 26-32, Koga 38-44, Sabrina 40-44,
    Blaine 47-53, Giovanni 53-60; luego el Alta Mando (Lorelei 56, Bruno 58,
    Agatha 58, Lance 62) y el campeón Gary 65. La fórmula antigua (9 + 5 por
    insignia) daba 14 con la primera insignia, seis por debajo de Misty, y por
    eso el bot entraba al gimnasio dos antes de tiempo y lo perdía siempre.
    """
    region_datos = regiones().get(region, {})
    jefes = region_datos.get("jefes", [])
    entrada = None
    if insignias < len(jefes):
        entrada = jefes[insignias]
    else:
        elite = region_datos.get("elite_four_datos") or []
        i = insignias - len(jefes)
        entrada = elite[i] if i < len(elite) else (region_datos.get("campeon_datos") or {})
    if not entrada:
        return NIVEL_ELITE, []
    niveles = entrada.get("niveles") or []
    if niveles:
        return max(niveles), niveles
    return NIVEL_OBJETIVO_BASE + insignias * NIVEL_POR_INSIGNIA, []


# ---------------------------------------------------------------- eficacia
def utilidad_contra(tipos: list[str], objetivo: str) -> tuple[float, float]:
    """(ofensiva, defensiva) de un món de esos tipos contra `objetivo`.

    **Ofensiva = solo el tipo principal.** Cada Pokémon tiene **un único
    ataque**, y el Move Tutor le sube el tier a ese ataque (Bubble -> Surf), no
    le añade un segundo tipo. Así que el daño que hace depende del tipo de ese
    ataque, que es el primero de la lista, y no del mejor ni del peor de sus
    tipos.

    Que importe se ve con el chart del juego, que **no es el oficial**: aquí
    Planta contra Tierra y contra Roca es 2x, y Veneno contra ambos es 0.5x. Un
    Bulbasaur (Planta/Veneno) contra Brock es 2x con su ataque de Planta, que
    es justo por lo que la guía lo recomienda como starter. Puntuando el peor
    caso (0.5x, el del Veneno) el bot descartaba al mejor món posible.

    **Defensiva = peor caso**, porque ahí sí es el peor: el ataque rival es de
    tipo desconocido y un solo món con una debilidad real se lo lleva.
    """
    if not tipos or not objetivo:
        return 1.0, 1.0
    principal = tipos[0]
    of = T.mejor_efectividad([principal], [objetivo])
    de = min(T.mejor_efectividad([objetivo], [t]) for t in tipos)
    return of, de


def aguante_bueno(de: float) -> float:
    """Convierte "cuánto aguanto" en una cifra donde más es mejor.

    La defensiva es un multiplicador de daño recibido: 0.0 es inmunidad, 0.5 es
    resistido, 2.0 es lo peor. Sumarla tal cual al puntaje premiaba morir más y
    castigaba la inmunidad, que es el mejor resultado posible.
    """
    return 4.0 if de <= 0 else max(0.25, 2.0 / de)


def ventaja(tipos: list[str], objetivo: str) -> float:
    """Calidad de un enfrentamiento: pega mucho y aguanta poco."""
    of, de = utilidad_contra(tipos, objetivo)
    return of * aguante_bueno(de) if of > 0 else 0.0



def suma_stats(d: dict | None) -> int:
    return sum((d or {}).values()) if d else 0


# ---------------------------------------------------------------- capstone
_ENTRENADORES: dict[str, float] | None = None


def pesos_entrenadores() -> dict[str, float]:
    """Cuántas especialidades de entrenador usan cada tipo.

    Es lo que hace que una captura sirva para lo que viene y no solo para el
    gimnasio de al lado. De `TRAINER_SPECIALTIES`: Normal x6, Water x5,
    Poison x5, y el resto x3 o x1.
    """
    global _ENTRENADORES
    if _ENTRENADORES is None:
        cuentas: dict[str, float] = {}
        ruta = DATA / "especialidades.json"
        if ruta.exists():
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            for v in (datos.get("TRAINER_SPECIALTIES") or {}).values():
                for t in (v.get("tipos") or []):
                    n = T.normalizar(t)
                    cuentas[n] = cuentas.get(n, 0.0) + 1.0
        _ENTRENADORES = cuentas
    return _ENTRENADORES


def cobertura_entrenadores(tipos: list[str]) -> float:
    """Cuán útil es un tipo contra los entrenadores de la partida."""
    from pkl_movimientos import multiplicador as _mult

    pesos = pesos_entrenadores()
    if not pesos or not tipos:
        return 1.0
    total = sum(pesos.values())
    if total <= 0:
        return 1.0
    return sum(p * max((_mult(t, d) for t in tipos), default=1.0)
               for d, p in pesos.items()) / total


def cobertura_region(tipos: list[str], region: str,
                     n_gimnasios: int = 8) -> tuple[int, int, int]:
    """`(2x en la apertura, 2x en toda la región, sin 0.5x)`.

    Se puntúa contra el EQUIPO de cada gimnasio, no contra el tipo del líder.
    La apertura pesa el doble de largo porque es donde el equipo llega débil y
    es donde se mueren las runs.
    """
    from pkl_movimientos import multiplicador as _mult

    equipos = [e for e in (tipos_del_rival(region, i)
                           for i in range(n_gimnasios)) if e]
    if not equipos:
        return 0, 0, 0
    valores = [max((_mult(t, r) for t in tipos for r in equipo), default=1.0)
               for equipo in equipos]
    apertura = valores[:3]
    return (sum(1 for v in apertura if v >= 2.0),
            sum(1 for v in valores if v >= 2.0),
            sum(1 for v in valores if v >= 1.0))


def _stats_clave(c: dict) -> tuple[int, int]:
    """(special, hp): los dos stats que deciden, porque todos los golpes son
    especiales y la vida decide si aguanta la pelea."""
    s = c.get("baseStats") or {}
    return (s.get("special") or 0, s.get("hp") or 0)


def _mejora_a(c: dict, equipo: list[dict]) -> dict | None:
    """El món al que este candidato le puede sustituir.

    Dos móns del mismo tipo tienen **exactamente los mismos movimientos** (el
    juego los saca de `MOVE_POOL[tipo][tier]`, sin mirar la especie), así que
    "mejores ataques" entre iguales es más `special` y más vida.
    """
    tipos_c = {T.normalizar(t) for t in (c.get("tipos") or [])}
    if not tipos_c:
        return None
    sp_c, hp_c = _stats_clave(c)
    for m in equipo:
        if {T.normalizar(t) for t in (m.get("tipos") or [])} != tipos_c:
            continue
        sp_m, hp_m = _stats_clave(m)
        if sp_c >= sp_m + 4 or (sp_c >= sp_m and hp_c >= hp_m + 6):
            return m
    return None



def elegir_starter(candidatos: list[dict], region: str,
                   n_gimnasios: int = 5) -> Decision:
    """Elige starter por cobertura de la apertura.

    Se puntúa cada gimnasio por `ofensiva x aguante` (que es lo que decide un
    combate) y no se admite ningún 0.5x contra los tres primeros: el equipo
    llega más débil precisamente ahí, así que un 0.5x temprano no es "un
    gimnasio difícil", es un muro. En Kanto sale Bulbasaur: 2x contra Roca y 2x
    contra Agua, mientras que Squirtle es 0.5x contra el Agua de Mt Moon.
    """
    equipos = [e for e in (tipos_del_rival(region, i)
                           for i in range(n_gimnasios)) if e]
    apertura = equipos[:3]
    if not equipos:
        equipos = [[T.normalizar(g["tipo"])] for g in
                   regiones().get(region, {}).get("jefes", [])][:n_gimnasios]
        apertura = equipos[:3]

    mejor, mejor_puntaje, detalle = None, -1e9, ""
    for c in candidatos:
        tipos = [T.normalizar(t) for t in (c.get("tipos") or c.get("tipos", []))]
        if not tipos:
            continue
        # El rival de la apertura es el primer tipo de cada equipo: si con ese
        # no se llega a neutro, se descarta el candidato entero.
        if apertura and any(utilidad_contra(tipos, equipo[0])[0] < 1.0
                            for equipo in apertura):
            continue
        valores = [ventaja(tipos, e[0]) for e in equipos] or [1.0]
        media = sum(valores) / len(valores)
        peor = min(valores)
        stats = suma_stats(c.get("baseStats") or c.get("estadisticas"))
        # El peor caso pesa lo mismo que la media: evita starters con un 2x
        # inicial y un 0.5x justo en el gimnasio que viene después.
        puntaje = media * 8 + peor * 8 + stats / 1000
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = c, puntaje
            detalle = (f"{c['nombre']} {tipos} vs {equipos} "
                       f"ventaja={['%.2f' % v for v in valores]} "
                       f"media={media:.2f} peor={peor:.2f} stats={stats}")
    if mejor is None:
        for c in candidatos:
            tipos = [T.normalizar(t) for t in c.get("tipos") or c.get("tipos", [])]
            if not tipos:
                continue
            valores = [ventaja(tipos, e[0]) for e in equipos] or [1.0]
            media = sum(valores) / len(valores)
            stats = suma_stats(c.get("baseStats") or c.get("estadisticas"))
            puntaje = media * 8 + min(valores) * 8 + stats / 1000
            if puntaje > mejor_puntaje:
                mejor, mejor_puntaje = c, puntaje
                detalle = (f"{c['nombre']} {tipos} (sin filtro duro) "
                           f"media={media:.2f}")
    if mejor is None:
        c = (candidatos or [{}])[0]
        return Decision("starter", 1, "sin candidatos: elijo el primero",
                        nombre=c.get("nombre", ""))
    return Decision("starter", mejor.get("atajo", 1), detalle,
                    nombre=mejor.get("nombre", ""))


def _mejora_claramente(candidato: dict, m: dict,
                       futuros: list[str] | None = None,
                       rival_ruta: list[str] | None = None,
                       nivel_equipo: int = 0) -> bool:
    """¿Este salvaje merece la plaza del món `m`?

    Tres formas de ser mejor, y todas importan: mejor nivel (que es lo que gana
    gimnasios), más estadísticas, o cubrir un tipo que el equipo no tiene para un
    gimnasio que viene.

    `rival_ruta` son los tipos de los **entrenadores del mapa actual**. Antes
    esta función los usaba sin recibirlos por parámetro: era un `NameError`
    esperando a ocurrir en cuanto un candidato sin ventaja contra el gimnasio
    que viene llegaba a esta línea, y eso cortaba la run entera.
    """
    tipos = [T.normalizar(t) for t in (candidato.get("tipos") or [])]
    if not tipos:
        return False
    nivel_c = candidato.get("nivel") or 0
    nivel_m = m.get("nivel") or 0
    if nivel_c >= nivel_m + 3:
        return True
    stats_c = suma_stats(candidato.get("baseStats"))
    stats_m = suma_stats(m.get("baseStats"))
    if stats_c >= stats_m * 1.15 and nivel_c >= nivel_m:
        return True
    if futuros:
        tipos_m = {T.normalizar(t) for t in (m.get("tipos") or [])}
        if not (set(tipos) & tipos_m):
            # Un 2x contra un entrenador **de este mapa** cuenta tanto como
            # uno contra el proximo jefe: es un combate que va a venir igual y
            # puede ser el que acaba la run.
            aporta = max(
                [max((utilidad_contra(tipos, r)[0] for r in futuros),
                     default=1.0)]
                + [max((utilidad_contra(tipos, r)[0] for r in (rival_ruta or [])),
                       default=0.0) if rival_ruta else 0.0],
                default=1.0)
            # **R2: el nivel no veta la captura.** Solo hace falta que aporte
            # una ventaja contra algún jefe o entrenador. Antes esta función
            # también rechazaba por nivel, que era una regla inventada
            # inventada; con un solo món en pie descartaba todos los salvajes.
            return aporta >= 2.0
    return False


def elegir_captura(equipo: list[dict], candidatos: list[dict],
                   tipo_actual: str | None = None,
                   tipo_futuro: str | None = None,
                   max_miembros: int = MAX_EQUIPO,
                   proximos: list[str] | None = None,
                   region: str | None = None,
                   ignorar_nivel: bool = False,
                   tipos_entrenadores: list[str] | None = None,
                 ) -> Decision:
    """Elige con qué salvaje pelear (el bot no puede lanzar la bola aquí).

    La captura es la decisión más cara de la partida: cuesta un nodo y un món.
    Por eso se puntúa por lo que cubre de aquí al campeón y no solo por el
    rival que está a la puerta:

    1. nunca 0.5x contra lo que hay delante (filtro duro),
    2. 2x contra los equipos de gimnasio de la región, apertura primero,
    3. tipos que aporta de verdad, para no acabar monocromo,
    4. lo que cubre de los entrenadores, que es lo que se repite cada fase,
    5. solo entra un tipo ya presente si el candidato es una mejora clara.

    Se cuenta lo que está **en pie**, no lo que ocupa plaza: un món caído es un
    hueco que hay que rellenar, porque los salvajes de las rutas siguientes
    traen mejores ataques que el que se ha perdido.

    **R2: siempre se captura uno al inicio de la pantalla.** La comparación
    "completar el equipo o tener mejores ataques" es solo para cuando ya hay
    `max_miembros`; con menos, entra el primer candidato con ventaja. El nivel
    no veta la captura en ningún caso.
    """
    if not candidatos:
        return Decision("capturar", None, "sin candidatos: huyo")

    vivos = [m for m in equipo if (m.get("ps") or 0) > 0]

    # Para la diversidad se cuenta TODO el roster, también los caídos: si no,
    # al caer un Geodude se podía volver a capturar otro y acabar con
    # "Geodude 4 + Geodude 10 + Bulbasaur 12", dos de tres plazas del mismo tipo.
    tipos_equipo = {T.normalizar(t) for m in equipo for t in (m.get("tipos") or [])}
    ya_capturados = {(m.get("nombre") or "").strip().lower() for m in equipo}
    arranque = len(vivos) < 2
    # OJO: el `if vivos else 0` de antes solo cubría el equipo vacío. Con el
    # equipo lleno de móns **vivos pero con `nivel == 0`** (el selector
    # `.team-slot-lv` ausente o sin dígitos deja `nivel: 0`) el generador se
    # queda vacío y `min()` revienta con
    # `ValueError: min() iterable argument is empty`. `ValueError` no está en
    # `ERRORES_DE_CODIGO`, así que no cortaba la run: reintentaba 3 veces y
    # acababa en `ATASCADO`, o sea se perdía la partida en la pantalla de
    # captura. Se calcula la lista primero y se cae a 0 si no hay niveles.
    _niveles_vivos = [(m.get("nivel") or 0) for m in vivos
                      if (m.get("nivel") or 0) > 0]
    nivel_equipo = min(_niveles_vivos) if _niveles_vivos else 0

    # **Un rival a la vez.** Antes el filtro exigía no ser 0.5x contra los tres
    # próximos gimnasios *a la vez*, y eso descartaba justo al món que hacía
    # falta: un Goldeen (Agua) se iba porque el Agua es floja contra Eléctrico
    # y contra Planta, que son de gimnasios posteriores. Resultado medido: el
    # equipo se llenaba de Pidgey, Zubat y Meowth y se llegaba a Misty sin nada
    # de Agua.
    #
    # Ahora el objetivo es el gimnasio que toca de verdad. Lo que viene después
    # se puntúa como cobertura de futuro, no como filtro: habrá más capturas.
    objetivo = [T.normalizar(tipo_actual)] if tipo_actual else []
    if tipo_futuro and T.normalizar(tipo_futuro) not in objetivo:
        objetivo.append(T.normalizar(tipo_futuro))
    futuros = [T.normalizar(t) for t in (proximos or []) if t]
    ref = list(objetivo)

    # **Especialidades de los entrenadores de este mapa.** Se leen del estado
    # del juego sin entrar en combate, asi que son informacion gratis, y son el
    # agujero mas caro: tener 2x contra el jefe no sirve si el mapa esta lleno
    # de Firebreather y el equipo entero es 0.5x contra Fuego. Medido: el bot
    # peléo contra un Firebreather con Bulbasaur (0.5x) y Paras (0.5x) porque no
    # tenia nada contra Fuego.
    rival_ruta = [T.normalizar(t) for t in (tipos_entrenadores or []) if t]
    rival_ruta = [t for t in rival_ruta if t and t not in ref]

    # Con el equipo lleno **no se deja de cazar**: lo que hay en las rutas
    # siguientes trae móns con más nivel y mejores ataques, y un bicho que ya
    # no aporta se puede cambiar por uno mejor. Es lo que dice la guía
    # ("replace weak picks; keeping underperforming Pokémon can block
    # stronger catches") y lo que pidió el usuario: tener un Rattata y salir
    # un Dragonite, se cambia el Rattata.
    #
    # El candidato se compara con el **peor** del equipo y solo entra si es
    # claramente mejor. Si no, se huye: cambiar por cambio gastaría el nodo
    # para nada. Esto se resuelve DENTRO del bucle de candidatos, que es donde
    # se sabe cuál es `c`: antes era una puerta antes del bucle que usaba una
    # variable que aún no existía.
    equipo_lleno = len(vivos) >= max_miembros
    # El "flojo" es el miembro **más débil**, y aquí estaba al revés: la clave
    # era `-0.02*stats - nivel`, y tomar el `min` de eso devuelve el **mejor**
    # del equipo (maximiza `stats` y nivel). Comprobado ejecutándolo con
    # Bulbasaur Nv20 (318 stats) y Staryu Nv8 (245): devolvía Bulbasaur.
    # Consecuencia medida: con el equipo lleno la puerta `_mejora_claramente`
    # se comparaba contra el mejor miembro, exigía `nivel+3` o `stats*1.15`, y
    # el bot **huía de todas las capturas** para siempre: el equipo nunca se
    # renovaba. Aquí se puntúa al revés y se toma el mínimo de verdad, que es
    # el peor. Los móns sin `baseStats` no se pueden comparar, así que se
    # se apartan para que no salgan elegidos como "flojos" por un 0 ficticio.
    def _fuerza_flojo(m: dict) -> tuple[int, int, str]:
        st = sum((m.get("baseStats") or {}).values()) if (m.get("baseStats")) else 0
        return (0 if st else 1, st, m.get("nombre") or "")

    flojo = (min(vivos, key=_fuerza_flojo)
             if vivos else None)

    mejor, mejor_puntaje, detalle = None, -1e9, ""
    for c in candidatos:
        tipos = [T.normalizar(t) for t in (c.get("tipos") or [])]
        if not tipos:
            continue
        stats = suma_stats(c.get("baseStats"))
        if stats < MIN_STATS_CAPTURA:
            continue
        # Nunca dos del mismo bicho: repetir especie es perder la plaza.
        if (c.get("nombre") or "").strip().lower() in ya_capturados:
            continue
        if equipo_lleno and flojo is not None and not _mejora_claramente(
                c, flojo, futuros or ref, rival_ruta, nivel_equipo):
            continue
        nuevos = {x for x in tipos} - tipos_equipo
        if not nuevos and not _mejora_a(c, equipo):
            continue
        # **Calidad de nivel.** Este filtro faltaba y era la causa de perder
        # con la vida intacta: el bot perdia contra entrenadores de ruta con
        # tres móns a 100 PS porque el equipo era Pidgey + Rattata + Poliwag de
        # nivel 5-8 junto a un carries de 12. Tres plazas muertas que no pegan
        # nada. Un món por debajo del mejor nivel del equipo solo entra si
        # aporta un tipo que el equipo no tiene; si no, se huye y el nodo se
        # gasta en nivel, que es lo que urge.
        mejor_nivel = max((m.get("nivel") or 0) for m in vivos) if vivos else 0
        # **R2: al inicio de cada pantalla se captura.** Este filtro solo
        # aplica con un equipo ya formado: rechazaba al salvaje por estar por
        # debajo del mejor nivel del equipo, y con un equipo de 1-2 móns eso
        # tiraba **todos** los salvajes de la ruta (nivel 1 contra un Nv5). El
        # planificador elegía el nodo ("equipo de 1, hacen falta cuerpos") y
        # luego aquí se rechazaba en silencio: se perdían 3 nodos seguidos y se
        # llegaba al primer gimnasio con un solo món. Medido: GAME_OVER con
        # equipo de 2.
        if (len(vivos) >= 3 and (c.get("nivel") or 0) < mejor_nivel
                and not nuevos and not CAPTURA_PERMISIVA):
            continue
        if objetivo:
            # Contra el gimnasio que toca: no puede ser 0.5x contra **todo** su
            # equipo (filtro duro), pero sí tiene que poder **aplastar a alguien**.
            # Con el peor caso para ambas cosas se exigía 2x contra cada món del
            # rival, y contra Misty (Agua/Psíquico) eso solo lo cumple un tipo
            # imposible: por eso se acababa cazando Pidgeys. Lo que se busca es
            # "aplasta al más peligroso y no lo pierde ninguno".
            #
            # **Con un solo món en pie este filtro se relaja.** Antes exigía
            # `>= 1.0` siempre, y con 1Bulbasaur Nv5 eso rechazaba a los
            # salvajes de Route 1 enteros: el bot elegía el nodo ("hacen
            # falta cuerpos") y luego huía, dos nodos seguidos, y acababa
            # peleando un `bug-catcher` Nv2 con el único món del equipo. Medido:
            # `GAME_OVER` en 18 pasos, 0 insignias, 0 capturas. R2 dice que con
            # menos de 6 no se veta nada: con un món, cualquier candidato que
            # no sea actively malo se coge.
            of_min = min((utilidad_contra(tipos, r)[0] for r in objetivo),
                          default=1.0)
            if len(vivos) < 2:
                if of_min < 0.5:
                    continue
            elif of_min < 1.0:
                continue
        if futuros:
            # Los futuros solo penalizan si el món es actively malo contra
            # ellos: se acepta que sea flojo, no que lo pierda.
            of_futuro = min((utilidad_contra(tipos, r)[0] for r in futuros),
                            default=1.0)
            if of_futuro < 0.5:
                continue
            # Y tiene que **aportar algo**: un 2x contra alguno de los próximos
            # gimnasios. Antes, cuando nada tenía ventaja, se cazaba igual y el
            # equipo se llenaba de trapos: medido, Meowth, Doduo y Ponyta
            # entraron con "2x apertura=0", o sea sin ninguna ventaja contra
            # nada, y con tres móns así se perdía contra Brock.
            #
            # La captura es el recurso más caro que hay (cuesta un nodo, que es
            # un paso de nivel, y una plaza), así que solo se gasta en algo que
            # conteste a un jefe. La guía lo dice igual: "only take a catch if it
            # improves the route you actually have".
            # Un 2x contra un entrenador **de este mapa** cuenta tanto como
            # uno contra el proximo jefe: es un combate que va a venir igual y
            # puede ser el que acaba la run.
            aporta = max(
                [max((utilidad_contra(tipos, r)[0] for r in futuros),
                     default=1.0)]
                + [max((utilidad_contra(tipos, r)[0] for r in rival_ruta),
                       default=0.0) * 1.0 if rival_ruta else 0.0],
                default=1.0)
            # Exigir un 2x siempre deja al equipo en 2-3 móns, y con dos no se
            # gana un gimnasio: medido, la mejor run capturó un Goldeen
            # (contragolpe de Brock, y lo venció) y arrived a Misty con solo
            # Ivysaur y Goldeen, donde el Agua es 0.5x contra el Staryu.
            #
            # Con **menos de 3 en pie** se acepta un món neutro, pero con dos
            # condiciones: que no pierda por 0.5x contra el gimnasio que viene y
            # que tenga estadísticas decentes. Es rellenar el equipo, no elegir
            # a ciegas.
            # Con el equipo lleno manda la comparación con el peor miembro: un
            # Dragonite de nivel 26 es mejor Nash Though a Rattata, aunque no
            # tenga un 2x contra el rival de ahora. Sin esta excepción se
            # rechazaba la sustitución y el equipo se quedaba congelado.
            #
            # **R2: no se veta por tener pocos móns.** La comprobación de
            # "completar el equipo o tener mejores ataques" es para cuando ya
            # hay 6; con menos, se captura y ya está. El veto por nivel
            # por nivel que había aquí era una regla inventada que
            # descartaba al salvaje cuando el equipo iba por debajo del listón
            # del líder, y con un solo món en pie eso descartaba **todos** los
            # salvajes de la ruta. Ahora el nivel no veta: solo decide a quién
            # se sustituye cuando el equipo está lleno.
            if aporta < 2.0 and len(vivos) >= 3 and not ignorar_nivel:
                flojo_para_cambio = min(
                    vivos,
                    key=lambda m: (m.get("nivel") or 0,
                                   -sum((m.get("baseStats") or {}).values()),
                                   m.get("nombre") or ""))
                if not _mejora_claramente(c, flojo_para_cambio, futuros,
                                          rival_ruta,
                                          nivel_equipo):
                    continue
        region_score = 0.0
        if region:
            apertura, total, ok = cobertura_region(tipos, region)
            region_score = 3.0 * apertura + total + ok * 0.3
        else:
            of, de = utilidad_contra(tipos, ref[0] if ref else None)
            region_score = of * 10 + aguante_bueno(de) * 2

        nivel_cand = c.get("nivel") or 0
        if nivel_equipo and nivel_cand:
            delta = nivel_cand - nivel_equipo
            nivel_score = 2.0 if delta >= 0 else max(0.0, 2.0 + delta * 0.4)
        else:
            nivel_score = 1.0
        if arranque:
            nivel_score += 2.0

        # Contrafolpe contra el gimnasio que toca. Es lo que decide la captura:
        # un 2x aqui vale mas que cualquier electiva de variedad.
        if objetivo:
            of_obj = max((utilidad_contra(tipos, r)[0] for r in objetivo),
                         default=1.0)
            if of_obj >= 2.0:
                # Pesa mucho a proposito: un 2x contra el gimnasio que toca es lo
                # que gana la pelea, y antes la variedad (25 por tipo nuevo)
                # se lo comia: con un equipo de uno solo, Pidgey (Normal +
                # Volador, dos tipos nuevos, +50) ganaba a un Pikachu que
                # pegaba a 2x al Agua de Staryu.
                region_score += 40.0
            elif of_obj >= 1.0:
                region_score += 6.0

        # La variedad es lo que gana las peleas de dos en dos, y la cobertura de
        # región sola agrupa: medido, equipos que acababan en Sandslash +
        # Venusaur + Gloom (tres de Planta/Tierra) sin una gota de Agua. Por eso
        # un tipo nuevo pesa más que la cobertura, y repetir lo que ya hay se
        # penaliza de verdad.
        repetidos = tipos_equipo & set(tipos)
        # La variedad sigue contando, pero por debajo del contragolpe: 12 por
        # tipo nuevo frente a los 40 de un 2x contra el rival que viene.
        variedad = len(nuevos) * 12.0 - len(repetidos) * 12.0

        puntaje = (variedad
                   + region_score
                   + cobertura_entrenadores(tipos) * 6.0
                   + stats / 500.0
                   + nivel_score)
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = c, puntaje
            cobertura_txt = ""
            if region:
                apertura, total, ok = cobertura_region(tipos, region)
                cobertura_txt = (f"2x apertura={apertura} 2x region={total} "
                                 f"sin 0.5x={ok} ")
            detalle = (f"{c['nombre']} {tipos}: {cobertura_txt}"
                       f"entrenadores={cobertura_entrenadores(tipos):.2f} "
                       f"nuevos={sorted(nuevos) or '-'} stats={stats} "
                       f"nivel={nivel_cand}")

    if mejor is None and CAPTURA_PERMISIVA:
        # **Regla del usuario: "es mejor capturar que rechazar".**
        #
        # Si el filtro estricto deja a todos los candidatos fuera, aqui se
        # entra igualmente con el que mejor puntue entre los que solo
        # incumplen los filtros **blandos** (tipo duplicado, sin 2x claro,
        # nivel por debajo). Se mantienen los duros: que no sea 0.5x contra
        # todo el rival, que tenga stats y que no se haya capturado ya.
        #
        # Por que el rechazo es caro y no gratis:
        #   - `catch-screen` tiene "Skip (flee)": huir es NO pelear, o sea
        #     perder el nivel del combate. Medido: 1,88 nodos de pelea por run
        #     se quedan sin combate (18% de los nodos de pelea).
        #   - el nodo de cambio ya sabe sacar al tipo repetido
        #     (`_peor_para_sustituir`, regla 9), o sea que capturar un
        #     duplicado no ocupa plaza: la libera.
        #   - el 98% de los rechazos eran "nada util", o sea el filtro
        #     esperando cobertura que el propio filtro impide conseguir.
        for c in candidatos:
            tipos = [T.normalizar(x) for x in (c.get("tipos") or []) if x]
            if not tipos:
                continue
            st = sum((c.get("baseStats") or {}).values()) or 0
            if st < MIN_STATS_CAPTURA:
                continue
            if (c.get("nombre") or "").strip().lower() in ya_capturados:
                continue
            # Duro: que no pierda por 0.5x contra **todo** el rival de ahora.
            if objetivo and min((utilidad_contra(tipos, r)[0]
                                 for r in objetivo), default=1.0) < 0.5:
                continue
            ref_t = {T.normalizar(t) for t in ref if t}
            if ref_t and all(utilidad_contra(tipos, r)[1] < 0.5 for r in ref_t):
                continue
            return Decision(
                "capturar", c.get("atajo"),
                f"permisiva: {c['nombre']} {tipos} aunque noMejore "
                f"(nivel={c.get('nivel')}, stats={st}); si el tipo esta "
                f"repetido, el nodo de cambio saca al anterior")
    if mejor is None:
        return Decision("capturar", None,
                        f"nada útil contra {'/'.join(ref) or '?'} "
                        f"con {len(vivos)} món(s) en pie: huyo")
    return Decision("capturar", mejor.get("atajo"), detalle)


# ---------------------------------------------------------------- lineup
def mejor_contragolpe(equipo: list[dict], tipos_rival: list[str]) -> str | None:
    """Qué món poner al frente contra esos tipos.

    Se elige por el PEOR caso, porque un entrenador de "Roca/Tierra/Lucha"
    trae móns de los tres y uno que solo aplasta a la Roca se come al de Lucha
    después.
    """
    from pkl_movimientos import multiplicador as _mult

    vivos = [m for m in equipo if (m.get("ps") or 0) > 0] or list(equipo)
    if not vivos or not tipos_rival:
        return None

    def clave(m: dict) -> tuple:
        tipos = [T.normalizar(t) for t in (m.get("tipos") or [])]
        peor = min((_mult(t, r) for t in tipos for r in tipos_rival), default=0.0)
        return (-peor, -(m.get("ps") or 0), -(m.get("nivel") or 0),
                m.get("nombre") or "")

    return min(vivos, key=clave).get("nombre")


def _aguante_contra(tipos: list[str], tipos_rival: list[str]) -> float:
    """Cuánto aguanta un tipo contra el rival. Más es mejor."""
    from pkl_movimientos import multiplicador as _mult

    peor = min((_mult(r, t) for t in tipos for r in tipos_rival), default=1.0)
    return 4.0 if peor <= 0 else max(0.25, 2.0 / peor)


def valor_contra_entrenador(m: dict, tipos_rival: list[str],
                            nivel_enemigo: int | None = None) -> tuple:
    """Puntuación de un món para pelear contra un entrenador. Más es mejor.

    Se combinan tres cosas porque pelear es ganar rápido y salir entero:
    cuánto pega (peor caso, que un entrenador de "Roca/Tierra/Lucha" trae de
    los tres), cuánto aguanta de menos, y cómo llega de gastado. Con eso el que
    sale delante es el que aguanta la pelea, no solo el que pega más fuerte, y
    el que va detrás es el que más fácil se cae.
    """
    tipos = [T.normalizar(t) for t in (m.get("tipos") or [])]
    # **Peor caso en las dos caras**, y no es conservadurismo gratuito: el bot no elige
    # movimiento (las batallas se auto-resuelven), así que no puede contar con
    # acertar con el tipo bueno del món.
    #
    # Puntuar el ataque con el *mejor* de los tipos del món es lo que metió a
    # Bulbasaur delante de Eevee contra un entrenador de Fuego: el Veneno de
    # Bulbasaur es 1x, así que el "mejor" era 1.0 y empataba con Eevee, y el
    # desempate alfabético lo ponía delante. Peor caso: Bulbasaur pega con
    # Planta a 0.5x contra Fuego y Eevee a 1x, que es la verdad.
    of = min((utilidad_contra(tipos, r)[0] for r in tipos_rival), default=1.0)
    aguante = _aguante_contra(tipos, tipos_rival)
    ps = (m.get("ps") or 0)
    ps_max = (m.get("ps_max") or 0) or 100
    vida = ps / max(ps_max, 1)
    nivel = m.get("nivel") or 0
    # Ventaja de nivel contra el rival, si se conoce.
    if nivel_enemigo:
        delta = nivel - nivel_enemigo
        altura = 1.0 if delta >= 0 else max(0.3, 1.0 + delta * 0.1)
    else:
        altura = 1.0
    # **El ataque NO se multiplica con la defensa.** Se devuelven por separado
    # y el orden los usa como claves sucesivas. El producto se cancelaba solo:
    # un Bicho/Veneno contra Fuego pega 0.5x y recibe 2x, y `0.5 * 2 = 1.0`,
    # exactamente igual que un món neutro. O sea, el peor contragolpe posible
    # puntuaba como uno neutro y se colaba por el desempate. Medido: contra un
    # `fire-spitter` el bot puso a Venonat (pega 0.5, recibe 2) **delante** de
    # Bellsprout.
    # La regla es la del usuario, literal: "si te sale un entrenador tipo bicho
    # y nosotros tenemos un pokemon tipo fuego, lo pones primero". O sea, lo
    # que decide quién abre es **cuánto pega**, y `aguante` solo desempata
    # entre dos que pegan igual.
    return (of, -aguante, altura, vida)


def orden_para_entrenador(equipo: list[dict], tipos_rival: list[str],
                          nivel_enemigo: int | None = None) -> list[str]:
    """Orden para un combate de entrenador: el mejor contragolpe al frente.

    No basta con el mejor tipo: hay que poner delante al que además aguanta y
    llega entero, que es el que se asegura la victoria, y detrás al que está
    más justo de vida para que sea el último en caerse. Todos los caídos
    pierden contra 0 y se quedan al final de la cola.
    """
    if not tipos_rival:
        return []
    con_puntos = []
    for m in equipo:
        of, neg_aguante, altura, vida = valor_contra_entrenador(
            m, tipos_rival, nivel_enemigo)
        stats = sum((m.get("baseStats") or {}).values())
        nivel = m.get("nivel") or 0
        # Un caído no puede pelear: vale -infinito para que quede el último.
        if (m.get("ps") or 0) <= 0:
            of = float("-inf")
        con_puntos.append((of, stats, nivel, neg_aguante, altura, vida,
                           m.get("nombre") or "", m))
    # **El ataque manda, y dentro de él stats y luego nivel.**
    #
    # Orden de claves, según la regla del usuario ("si te sale un entrenador
    # tipo bicho y tenemos un pokemon tipo fuego, lo pones primero", y "en la
    # ponderación primero stats y luego nivel"):
    #
    # 1. `of`      cuánto pega contra el rival. Es lo que decide.
    # 2. `stats`   sus estadísticas base: a igual tipo, el más fuerte.
    # 3. `nivel`   y el nivel, que es lo que el món pierde contra el rival.
    # 4. `aguante` (va negado) solo desempata entre dos que pegan igual.
    # 5. `vida`    llegar entero.
    #
    # Antes era un **producto** `of * aguante * altura`, y eso emparejaba casos
    # que no deben emparejarse: contra un entrenador de Roca/Tierra, Staryu
    # (Agua, pega x2, encaja mal) y Geodude (Roca, pega x0.5, aguanta bien)
    # salían los dos a 2.0, y el desempate los ponía casi al azar. Con el
    # producto, un món que mata el doble de rápido pierde la vez contra uno
    # que aguanta más.
    #
    # El nombre **no** desempata nunca: el alfabeto yadecisionó que Bulbasaur
    # (2x de Fuego) se plantara delante de Eevee (1x).
    con_puntos.sort(
        key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5], x[6]),
        reverse=True)
    return [x[7].get("nombre") or "" for x in con_puntos if x[7].get("nombre")]


def _reservar_heridos(candidatos: list[dict]) -> list[str]:
    """Mete al final a los móns por debajo de la mitad de la vida.

    No los aparta: siguen en el equipo y siguen ganando experiencia, solo
    entran **últimos** en el combate, que es justo lo que pedía el usuario
    ("reservamos en los últimos puestos a los que tengan menos de la mitad de
    la vida, así pueden seguir ganando experiencia y no los matamos").

    El corte es por **porcentaje** (ps / ps_max), nunca por PS crudos: con
    `ps(m) < 50` un món con 46/46 de vida se contaba como herido y la
    partición no separaba nada.
    """
    sanos_orden: list[dict] = []
    heridos_orden: list[dict] = []
    for m in candidatos:
        if not m or m in sanos_orden or m in heridos_orden:
            continue
        ratio_m = (m.get("ps") or 0) / max(m.get("ps_max") or 0, 1)
        (heridos_orden if ratio_m < 0.5 else sanos_orden).append(m)
    return [m.get("nombre") or "" for m in sanos_orden + heridos_orden]


def orden_deseado(equipo: list[dict], insignias: int, region: str,
                  tipo_nodo: str = "otro",
                  tipos_rival: list[str] | None = None) -> list[str]:
    """Orden del equipo (el primero es el delantero).

    - Contra el jefe, el mejor al frente: de eso depende pasar de mapa.
    - Explorando, el principal queda **reservado en segundo**, para que cada
      pelea de la ruta sea un desgaste que no se pierde.
    - Si el entrenador es de tipo "Diversos" no hay contragolpe que calcular y
      esta es la única pista: se protege al principal en segundo.

    `tipos_rival` es el tipo del rival **cuando se sabe** (jefe, entrenador, o
    el tipo del líder del mapa como mejor pista para un salvaje). Es la
    diferencia entre la versión buena y la que rompía partidas: sin esto, un
    Doduo (Normal/Volador) se ponía al frente contra Brock (Roca/Estierra) y
    se comía un 2x en el primer golpe. Adelantar "al que peor pega" creyendo
    que aguanta es justo lo contrario: el que menos da es el que antes muere.
    """
    if not equipo:
        return []
    if tipos_rival is None:
        tipos_rival = tipos_del_rival(region, insignias)
    objetivo = [T.normalizar(t) for t in (tipos_rival or [])]
    sanos = [m for m in equipo if (m.get("ps") or 0) > 0] or list(equipo)

    def of(m: dict) -> float:
        if not objetivo:
            return 1.0
        tipos = [T.normalizar(t) for t in (m.get("tipos") or [])]
        return min((utilidad_contra(tipos, r)[0] for r in objetivo), default=1.0)

    def aguante(m: dict) -> float:
        """Peor caso defensivo: 1.0 neutral, <1.0 se lo llevan de vuelta."""
        if not objetivo:
            return 1.0
        tipos = [T.normalizar(t) for t in (m.get("tipos") or [])]
        return min((utilidad_contra(tipos, r)[1] for r in objetivo), default=1.0)

    def effectiveness(m: dict) -> float:
        """Cuánto rinde contra **todo** el equipo rival, de media.

        No el peor caso: con un rival de dos tipos (Tierra/Roca) el peor caso de
        Bulbasaur y de Doduo es el mismo 0.5 y no los distingue. La media de
        `pega x aguanta` sí los separa.
        """
        if not objetivo:
            return 1.0
        tipos = [T.normalizar(t) for t in (m.get("tipos") or [])]
        if not tipos:
            return 1.0
        valores = []
        for r in objetivo:
            atk, de = utilidad_contra(tipos, r)
            valores.append(atk * de)
        return sum(valores) / len(valores)

    def nivel(m: dict) -> int:
        return m.get("nivel") or 0

    def ps(m: dict) -> int:
        return m.get("ps") or 0

    if tipo_nodo in ("jefe", "tutor"):
        # En el jefe, y también en el Move Tutor, el mejor va **delante**. En el
        # tutor porque sube el tier del único ataque de un món y el recurso es
        # escaso: va al principal, que es el que tiene que ganar los gimnasios
        # (petición explícita del usuario).
        return _reservar_heridos(
            sorted(sanos, key=lambda m: (-of(m), -nivel(m),
                                         m.get("nombre") or "")))

    if objetivo:
        # **Se sabe** contra quién se pelea: manda la effectiveness y punto.
        # El "principal en segundo" es solo para cuando el rival es un
        # "Diversos" sin ninguna pista. Aplicarlo con el tipo conocido fue
        # justo lo que puso a Doduo contra Brock, que se come un 2x de Roca en
        # el primer golpe.
        candidatos = sorted(sanos, key=lambda m: (-effectiveness(m), -nivel(m),
                                                  m.get("nombre") or ""))
    else:
        # Sin tipo conocido: el principal se reserva en segundo y delante va el
        # que más aguante, nunca el que peor pega (ese es el que muere antes).
        principal = max(sanos, key=lambda m: (nivel(m), ps(m),
                                              m.get("nombre") or ""))
        resto = [m for m in sanos if m is not principal] or list(sanos)
        seguros = [m for m in resto if aguante(m) >= 1.0] or \
                  [m for m in resto if aguante(m) >= 0.5] or resto
        primero = max(seguros,
                      key=lambda m: (aguante(m), ps(m) / max(nivel(m), 1),
                                     nivel(m), m.get("nombre") or ""))
        candidatos = [primero, principal, *resto]

    # Al final, los que están por debajo de la mitad de la vida: un herido
    # delega, sigue ganando experiencia y se cura subiendo de nivel, que es más
    # rápido que gastar el único centro del mapa en ello. Los caídos no cuentan:
    # no ganan experiencia, así que no son ni buenos ni malos para esto.
    return _reservar_heridos(candidatos)
def siguiente_hacia(actual: str | None, nodos: list[dict], edges: list,
                    tipo_destino: str = "tutor") -> str | None:
    """Id del primer nodo al que hay que moverse para llegar a `tipo_destino`.

    El grafo es un DAG por capas y hay un nodo del tutor por mapa (el único que
    sube el tier de los ataques). El bot es codicioso y se iba al entrenador o
    a la batalla de más exp, así que el tutor se quedaba `revealed` pero nunca
    `accessible`: 0 mapas con tutor accesible en una partida entera.

    El BFS recorre el grafo ENTERO, no solo los nodos pulsables (el tutor está
    unas capas más allá), y luego se devuelve el primer salto pulsable de la
    ruta, excluyendo el nodo en el que ya estamos.
    """
    if not actual or not edges:
        return None
    por_id = {n.get("id"): n for n in nodos if n.get("id")}
    abiertos = {n["id"] for n in nodos if n.get("id") and n.get("clickable")}
    if not abiertos:
        return None
    adyacentes: dict[str, list[str]] = {}
    for e in edges:
        if isinstance(e, dict):
            origen, destino = e.get("from"), e.get("to")
        else:
            origen = e[0] if len(e) > 0 else None
            destino = e[1] if len(e) > 1 else None
        if origen and destino:
            adyacentes.setdefault(origen, []).append(destino)
    cola = [actual]
    vistos = {actual}
    ruta: dict[str, str | None] = {actual: None}
    destino_final = None
    while cola and destino_final is None:
        nodo = cola.pop(0)
        for sig in adyacentes.get(nodo, []):
            if sig in vistos:
                continue
            vistos.add(sig)
            ruta[sig] = nodo
            if tipo_de_estado((por_id.get(sig) or {}).get("tipo")) == tipo_destino:
                destino_final = sig
                break
            cola.append(sig)
    if destino_final is None:
        return None
    camino: list[str] = []
    paso = destino_final
    while paso is not None and paso != actual:
        camino.append(paso)
        paso = ruta.get(paso)
    for nodo in reversed(camino):
        if nodo in abiertos:
            return nodo
    return None


def entrenadores_por_delante(nodos: list[dict], edges: list,
                             tope: int = 8) -> dict[str, int]:
    """Cuántos **entrenadores** deja cada rama hacia el jefe.

    Se cuenta aparte de los combates porque valen mucho mas. Medido: un solo
    entrenador subió el equipo entero de nivel 8-9 a 10-11, mientras que ocho
    nodos de combate contra salvajes de nivel 2-4 solo lo llevaron de 5 a 9. Los
    salvajes de la ruta estan por debajo del equipo y apenas dan experiencia;
    el entrenador es la unica fuente que mueve a **todo el equipo** a la vez.
    """
    por_id = {n["id"]: n for n in nodos if n.get("id")}
    hijos: dict[str, list[str]] = {}
    for e in edges:
        if isinstance(e, dict):
            origen, destino = e.get("from"), e.get("to")
        else:
            origen = e[0] if len(e) > 0 else None
            destino = e[1] if len(e) > 1 else None
        if origen and destino:
            hijos.setdefault(origen, []).append(destino)

    memo: dict[str, int] = {}

    def valor(nid: str, prof: int = 0) -> int:
        if prof > tope or nid in memo:
            return memo.get(nid, 0)
        n = por_id.get(nid)
        # La clave es `tipo`, no `type`: en los nodos del mapa el tipo va en
        # `tipo` (en inglés) y `type` no existe. Con `type` esta función
        # devolvía 0 en todas las ramas, o sea que la preferencia de ruta por
        # trainers **nunca se ejecutó**. Es la misma clase de fallo que
        # `cura` vs `pokecenter`: comparar contra un nombre que no está.
        propio = 1 if (n and tipo_de_estado(n.get("tipo") or n.get("type"))
                       == "entrenador") else 0
        total = propio + sum(valor(h, prof + 1) for h in hijos.get(nid, []))
        memo[nid] = total
        return total

    return {str(nid): valor(str(nid)) for nid in por_id}


def centros_por_delante(nodos: list[dict], edges: list,
                       limpio: int = 8) -> dict[str, int]:
    """Cuántos pokecenters hay en la ruta que sale de cada nodo.

    Existe porque faltaba el otro lado de la puerta del 75%. El bot solo
    curaba cuando el centro le salia ya entre los nodos clicables: medido,
    **solo 68 de 192 logs llegaron a ver un centro**, y 26 equipos murieron
    contra Brock sin haber pasado por ninguno. La rama con el pokecenter
    existe, pero hay que **elegirla**: `entrenadores_por_delante` pesaba 4x y
    arrastraba al bot a las ramas sin cura, con lo cual la Instruccion de
    "pasar por el centro antes del lider" no se cumplia en la mitad de las
    partidas.
    """
    por_id = {str(n.get("id")): n for n in nodos if n.get("id") is not None}
    hijos: dict[str, list[str]] = {}
    for e in edges:
        if isinstance(e, dict):
            o, d = e.get("from"), e.get("to")
        else:
            o = e[0] if len(e) > 0 else None
            d = e[1] if len(e) > 1 else None
        if o is None or d is None:
            continue
        # `edges` va de padre a hijo.
        hijos.setdefault(str(o), []).append(str(d))

    memo: dict[str, int] = {}

    def valor(nid: str, prof: int) -> int:
        if prof > limpio:
            return 0
        if nid in memo:
            return memo[nid]
        memo[nid] = 0
        n = por_id.get(nid)
        propio = 1 if (n and tipo_de_estado(n.get("tipo") or n.get("type"))
                       == "cura") else 0
        total = propio + sum(valor(h, prof + 1) for h in hijos.get(nid, []))
        memo[nid] = total
        return total

    return {nid: valor(nid, 0) for nid in por_id}


def camino_al_jefe(nodos: list[dict], edges: list,
                   jefe_id: str | None) -> set[str]:
    """Nodos que están **en el camino** al jefe (BFS inverso desde el jefe).

    El grafo tiene una estructura fija: **siempre hay un pokecenter antes de un
    líder de gimnasio**. Es decir, el pokecenter no compite con el jefe: es el
    tramo obligatorio para llegar a él. Por eso la decisión no es "curar o no",
    es "pasar por el pokecenter", y al pasar se cura gratis. Antes de esto el
    bot se saltaba los pokecenter y llegaba al gimnasio con el carry al 19%.

    Se recorre el grafo al revés desde el jefe: todo nodo que puede llegar a él
    forma parte de la ruta.
    """
    if not jefe_id:
        return set()
    por_id = {str(n.get("id")): n for n in nodos if n.get("id") is not None}
    hijos: dict[str, list[str]] = {}
    for e in edges:
        if isinstance(e, dict):
            origen, destino = e.get("from"), e.get("to")
        else:
            origen = e[0] if len(e) > 0 else None
            destino = e[1] if len(e) > 1 else None
        if origen is None or destino is None:
            continue
        # `edges` va de padre a hijo, así que para el BFS inverso se invierte.
        hijos.setdefault(str(destino), []).append(str(origen))
    vistos: set[str] = set()
    pila = [str(jefe_id)]
    while pila:
        act = pila.pop()
        if act in vistos or act not in por_id:
            continue
        vistos.add(act)
        pila.extend(hijos.get(act, []))
    return vistos


def llega_a(nodos: list[dict], edges: list, origen: str,
            destino: str, tope: int = 24) -> bool:
    """¿Se puede ir de `origen` a `destino` siguiendo el grafo?

    Sirve para lo del pokecenter: si desde este nodo se llega al jefe, este nodo
    está en el camino obligatorio y hay que pasar por él (y de paso curar).
    """
    if not origen or not destino or origen == destino:
        return bool(destino)
    por_id = {str(n.get("id")): n for n in nodos if n.get("id") is not None}
    hijos: dict[str, list[str]] = {}
    for e in edges:
        if isinstance(e, dict):
            o, d = e.get("from"), e.get("to")
        else:
            o = e[0] if len(e) > 0 else None
            d = e[1] if len(e) > 1 else None
        if o is None or d is None:
            continue
        hijos.setdefault(str(o), []).append(str(d))
    vistos = {str(origen)}
    cola = [str(origen)]
    while cola:
        act = cola.pop(0)
        if act == str(destino):
            return True
        if len(vistos) > tope:
            return False
        for h in hijos.get(act, []):
            if h in por_id and h not in vistos:
                vistos.add(h)
                cola.append(h)
    return False


def combates_por_delante(nodos: list[dict], edges: list,
                         tope: int = 8) -> dict[str, int]:
    """Cuántos combates (entrenador o batalla) quedan por delante, por nodo.

    El bot elige la rama del mapa y cada rama lleva a una mezcla distinta de
    nodos. Medido: una partida ofrece 35 nodos y 20 combates y llega al
    gimnasio 4; otra ofrece 13 y 4 y no llega ni al primero. Esto puntúa cada
    rama por lo que deja, para elegir la que da más experiencia.
    """
    por_id = {n["id"]: n for n in nodos if n.get("id")}
    hijos: dict[str, list[str]] = {}
    for e in edges:
        if isinstance(e, dict):
            origen, destino = e.get("from"), e.get("to")
        else:
            origen = e[0] if len(e) > 0 else None
            destino = e[1] if len(e) > 1 else None
        if origen and destino:
            hijos.setdefault(origen, []).append(destino)
    memo: dict[str, int] = {}
    en_curso: set[str] = set()

    def valor(nid: str, prof: int = 0) -> int:
        if nid in memo:
            return memo[nid]
        if nid in en_curso or prof > 14:
            return 0
        en_curso.add(nid)
        t = tipo_de_estado((por_id.get(nid) or {}).get("tipo"))
        propio = 1 if t in ("entrenador", "batalla") else 0
        mejor = max((valor(h, prof + 1) for h in hijos.get(nid, [])), default=0)
        en_curso.discard(nid)
        memo[nid] = propio + mejor
        return memo[nid]

    for nid in por_id:
        valor(nid)
    return {nid: min(v, tope) for nid, v in memo.items()}


# ---------------------------------------------------------------- decisiones triviales

def decidir_batalla(tiene_auto: bool) -> Decision:
    """El juego se auto-resuelve solo; no se puede elegir movimiento."""
    if tiene_auto:
        return Decision("auto_battle", True, "el juego ofrece auto-battle: lo uso")
    return Decision("continuar", True, "pulso continuar hasta el final")

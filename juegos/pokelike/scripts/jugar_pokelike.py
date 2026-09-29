"""Bot autónomo de Pokelike: juega la run entera en Python, sin gastar tokens.

Reemplaza al bot anterior, que actuaba como un actuador tonto: capturaba una
pantalla, esperaba a que un modelo escribiera una acción en `accion.json` y la
ejecutaba. Eso costaba un turno de LLM (captura + razonamiento + acción) *por
clic*, y una run son cientos de clics. Aquí la decisión vive en `politica.py` y
la ejecución en `navegador.py`: el bucle corre entero sin intervención del
modelo.

Cómo funciona:
  1. Detecta la pantalla activa (`.screen.active`).
  2. Lee el estado desde el DOM público (equipo, PS, insignia, bolsa, mapa).
  3. Decide con la política y ejecuta **un** clic.
  4. Repite hasta campeón, derrota o presupuesto de pasos agotado.

El juego trae autoplay (`#btn-auto-battle`), así que la batalla se resuelve sola;
el bot solo avanza los diálogos. Al final imprime un resumen compacto para que
el modelo no tenga que releer la partida.

Uso:
  uv run juegos/pokelike/scripts/jugar_pokelike.py --region Kanto
  uv run juegos/pokelike/scripts/jugar_pokelike.py --region Sinnoh --headful --max-pasos 400
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import navegador as nb  # noqa: E402
import pkl_items as PI  # noqa: E402
import planificador as PL  # noqa: E402
import politica as P  # noqa: E402
import pkl_tipos as T  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent.parent
DIR_BOT = RAIZ / "juegos" / "pokelike" / "log"
# Un log por proceso. Con un único archivo fijo, dos ejecuciones simultáneas
# se entrelazan y el log deja de ser legible (pasó al solapar una prueba con una
# tanda: aparecía un Persian de nivel 42 en mitad de una partida en nivel 6).
# El nombre lleva fecha y hora: al logarithm many runs in parallel the PID
# only tells you which is which, not when each was. Format `AAAA-MM-DD_HH-MM-SS`.
_MOMENTO = time.strftime("%Y-%m-%d_%H-%M-%S")
LOG_BOT = DIR_BOT / f"log-{_MOMENTO}_p{os.getpid()}.txt"

REGIONES_DOM = {
    "Kanto": "KANTO", "Johto": "JOHTO", "Hoenn": "HOENN",
    "Sinnoh": "SINNOH", "Unova": "UNOVA",
}


class Bot:
    def __init__(self, juego: nb.Juego, region: str, verbose: bool = True,
                 reset: bool = False) -> None:
        self.j = juego
        self.reset = reset
        self.tipo_lider: str | None = None
        # Rerolls de mapa usados en la run (la guía los recomienda para buscar
        # un trade o un mejor camino de exp).
        self._rerolls = 0
        self._rerolls_busqueda = 0
        # ¿Ya hemos hecho algún trade en esta run?
        self._trade_hecho = False
        # PS real por món, aprendido en la pantalla de combate ("0/19").
        self._ps_real: dict[str, tuple[int, int]] = {}
        self.items_tomados = 0
        # Nivel más alto de enemigo que se ha visto en la ruta.
        self.nivel_enemigo_max = 0
        self.enemigos_max_vistos = 1
        self.region = region
        self.verbose = verbose
        self.pasos = 0
        self.decisiones: list[str] = []
        self.pokedex: dict = {}
        self.resultado = "EN_CURSO"
        self.ultima_insignia = 0
        self.nodos_vistos: set[tuple[str, str]] = set()
        # Contadores de combate, para decir en el log si se gana o se pierde y
        # cerrar con una tabla resumen.
        self._en_combate = False
        self.combates = 0
        self.victorias = 0
        self.derrotas = 0
        self.capturas = 0
        # Una captura por pantalla, como pidió el usuario. Cazar para llenar el
        # equipo salía carísimo: cada caza es un nodo de nivel que se gasta en
        # un miembro, y lo que mata las runs es quedarse corto de nivel para el
        # jefe. Con el equipo a 3 y subiendo nivel, se llega; con 5 capturas por
        # pantalla, no.
        self.capturas_pantalla = 0
        self.pantalla_actual = None
        self.tutores = 0
        self.objetos = 0
        # Un objeto que ya se ha intentado equipar y no ha entrado **no se
        # vuelve a intentar**. Sin esto la partida se colgaba en un bucle: el
        # equip fallaba, la bolsa no bajaba, y en la siguiente pantalla de
        # preparación se volvía a probar el mismo objeto indefinidamente.
        self.objetos_fallidos: set[str] = set()
        # Errores por pantalla: un manejador roto se repite y para la run.
        self._errores: dict[str, int] = {}
        # Contenido del último combate, para nombrar la derrota con detalle.
        self._ultimo_rival = "?"
        self.centros = 0
        self._equipo_final: list[dict] = []
        self._insignias_final = 0
        # Tras coger un pasivo la pantalla sigue activa: hay que pulsar
        # SKIP para salir, si no se vuelve a elegir carta y no avanza.
        self._ya_cogido_item = False
        # El arrastre de slots puede fallar si el HUD cambia; se reintenta
        # unas pocas veces y luego se sigue jugando sin reordenar.
        self._reordenes_fallidos = 0

    def log(self, linea: str) -> None:
        if self.verbose:
            print(linea, flush=True)
        try:
            LOG_BOT.parent.mkdir(parents=True, exist_ok=True)
            with LOG_BOT.open("a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {linea}\n")
        except OSError:
            pass

    def anotar(self, d: P.Decision) -> None:
        self.decisiones.append(str(d))
        self.log(f"  {d}")

    # ------------------------------------------------------------ helpers
    def tipos_equipo(self, equipo: list[dict]) -> list[str]:
        out: list[str] = []
        for m in equipo:
            info = self.pokedex.get(m.get("id") or "") or {}
            out.extend(info.get("types") or [])
        return out

    def equipo_con_tipos(self) -> list[dict]:
        """Equipo con el **PS real** si se conoce.

        El HUD solo da el porcentaje de la barra, y en un món caido ese
        porcentaje sigue marcando 100. Cuando se ha visto al món en la pantalla
        de combate se sabe su vida exacta, y esa manda: sin esto, el bot
        creía estar sano con 0/19 y no iba a curar.
        """
        eq = self._equipo_con_tipos_base()
        if not self._ps_real:
            return eq
        for m in eq:
            real = self._ps_real.get((m.get("nombre") or "").strip().lower())
            if real:
                m["ps"], m["ps_max"] = real
        return eq

    def _equipo_con_tipos_base(self) -> list[dict]:
        """Equipo del HUD + los tipos que salen del `__POKEDEX__`.

        Sin los tipos no se puede ordenar el equipo, y el fallo es silencioso y
        gravísimo: `orden_para_entrenador` con móns sin tipos los puntúa a todos
        igual y el orden de salida acaba siendo **alfabético**, que es
        exactamente como se llegó a poner a Bulbasaur (2x de Fuego) delante de
        Eevee contra un entrenador de Fuego.

        Se busca por `id` del HUD y, si no aparece, **por nombre**. El Pokédex
        está indexado por número de la Pokédex ("1" es Bulbasaur, "133" es
        Eevee) y lo que da el HUD depende de cómo el juego nombre el sprite, así
        que el respaldo por nombre es lo que hace que esto no dependa de ello.
        """
        eq = self.j.equipo()
        por_nombre = self._pokedex_por_nombre()
        for m in eq:
            clave = str(m.get("id") or "")
            info = self.pokedex.get(clave) or por_nombre.get(m.get("nombre") or "")
            m["tipos"] = (info or {}).get("types") or []
            m["baseStats"] = (info or {}).get("baseStats") or {}
        sin_tipos = [m.get("nombre") for m in eq if not m.get("tipos")]
        if sin_tipos and getattr(self, "_sin_tipos_aviso", 0) < 3:
            # Se avisa, y solo tres veces: el orden del equipo depende de esto
            # y sin tipos el bot juega a ciegas.
            self._sin_tipos_aviso = getattr(self, "_sin_tipos_aviso", 0) + 1
            self.log(f"  !! sin tipos en el Pokédex: {sin_tipos} "
                     f"(id del HUD: {[m.get('id') for m in eq]}) "
                     f"-> el orden del equipo no puede ser correcto")
        return eq

    def cartas_con_datos(self, contenedor: str) -> list[dict]:
        """`.poke-card` de un selector, con tipos y stats del dex.

        Los tipos se sacan por el índice del sprite (`img/sprites/pokemon/N.png`),
        pero eso es una carrera: si la imagen todavía no ha cargado el `src` está
        vacío y el món se quedaba **sin tipos**, que es como se acababa
        eligiendo de Squirtle en vez de a Bulbasaur (el filtro de 2x de la
        apertura lo descartaba por no tener tipo con el que puntuar). Por eso
        hay dos respaldos: índice por nombre y, en último caso, los tipos
        leídos del texto de la carta.
        """
        from pkl_tipos import normalizar as _norm

        # En minúsculas porque en la carta los tipos van en MAYÚSCULAS
        # ("GRASS POISON") y `normalizar` no los baja. El chart los tiene en
        # mayúscula, así que de minúscula a canónico con un mapa.
        canonico = {_norm(t.lower()): _norm(t) for t in P.tipos_conocidos()}
        cartas = self.j.opciones_pokemon(contenedor)
        for c in cartas:
            info = self.pokedex.get(c.get("dex") or "") or {}
            if not info.get("types"):
                info = self._pokedex_por_nombre().get(c.get("nombre") or "") or {}
            tipos = info.get("types") or []
            if not tipos:
                # "Bulbasaur Lv. 5 GRASS POISON SP.A 11 ..." -> los tipos son
                # las palabras conocidas que salen antes de las estadísticas.
                cab = (c.get("txt") or "").split("SP.A")[0].split("SP.D")[0]
                cab = cab.split("CRIT")[0]
                palabras = cab.replace("/", " ").split()
                tipos = []
                for i, w in enumerate(palabras):
                    n = canonico.get(w.lower())
                    if n and n not in tipos and i > 0:
                        tipos.append(n)
                        # Un segundo tipo va justo detrás: "GRASS POISON".
                        if len(palabras) > i + 1:
                            segundo = canonico.get(palabras[i + 1].lower())
                            if segundo and segundo != n:
                                tipos.append(segundo)
            c["tipos"] = [_norm(t) for t in tipos]
            c["baseStats"] = info.get("baseStats") or {}
        return cartas

    def _pokedex_por_nombre(self) -> dict:
        if getattr(self, "_por_nombre", None) is None:
            self._por_nombre = {v.get("name"): v for v in self.pokedex.values()
                                if v.get("name")}
        return self._por_nombre

    MAX_ITEMS = 3

    # Excepciones que son **fallos del código** y no del entorno. Un timeout
    # agotado se reintenta; un `NameError` no se arregla reintentando.
    ERRORES_DE_CODIGO = (NameError, AttributeError, TypeError, IndentationError,
                         KeyError, IndexError)

    def bolsa_vacia(self) -> bool:
        """¿Sigue mereciendo la pena ir a por objetos?

        No se puede fiar de `#item-bar`: tras coger un objeto la barra se queda
        sin contenido y es indistinguible de "no hay nada", así que el DOM
        mentía y el bot iba a por doce Scope Lens seguidos. Se cuenta a mano.
        """
        return self.items_tomados >= self.MAX_ITEMS

    # ------------------------------------------------------------ pantallas
    def _title(self) -> str:
        # El juego no ofrece "Reset Run": con `--reset` se entra con perfil
        # temporal, así que aquí nunca hay una run guardada que continuar.
        if not self.reset and self.j.visible("#btn-continue-run"):
            self.anotar(P.Decision("continuar_run", True, "hay una run guardada"))
            self.j.activar("#btn-continue-run")
        else:
            self.anotar(P.Decision("nueva_run", True, "Story"))
            self.j.activar("#btn-history-run")
        return "arrancando run"

    def _region(self) -> str:
        objetivo = REGIONES_DOM.get(self.region, self.region.upper())
        self.j.activar("#btn-history-classic")  # modo Classic
        cards = self.j.page.locator(".history-region-btn")
        for i in range(cards.count()):
            if objetivo in (cards.nth(i).inner_text() or "").upper():
                cards.nth(i).click(timeout=8000)
                self.anotar(P.Decision("region", self.region, f"elige {objetivo}"))
                return f"región {self.region}"
        self.j.clic(".history-region-btn")
        self.anotar(P.Decision("region", self.region, "sin coincidencia; tomo la primera"))
        return "región (por defecto)"

    def _trainer(self) -> str:
        self.j.activar("#trainer-boy")
        self.anotar(P.Decision("trainer", "boy", "avatar"))
        return "avatar"

    def _starter(self) -> str:
        cands = self.cartas_con_datos("#starter-choices")
        d = P.elegir_starter(cands, self.region)
        self.anotar(d)
        # Traza de los candidatos: la lista de starters que ofrece la región es
        # corta y decide el techo de la run entera, así que conviene verla.
        self.log(f"  starters: {[(c['nombre'], c.get('tipos')) for c in cands]}")
        # Las cartas son `tabindex=0` con `data-shortcut`: la vía fiable es la
        # tecla, no el clic (el clic no siempre dispara el manejador).
        if d.valor:
            self.j.clic_por_atajo(str(d.valor))
        else:
            self.j.clic("#starter-choices .poke-card")
        return f"starter {d.razon}"

    def diagnostico_estado(self) -> str:
        """`| TM usado: N, bolsa: [...]` para ver si los discos se aplican.

        El nodo del tutor se elegía y se pulsaba, pero el mapa no cambiaba y
        no se sabía si el disco se enseñaba o no. `state.usedTM` y
        `state.items` lo dicen sin adivinar.
        """
        try:
            info = self.j.page.evaluate(
                "() => (typeof state === 'undefined') ? null"
                " : {usedTM: state.usedTM, items: state.items}")
        except Exception:  # noqa: BLE001
            return ""
        if not info:
            return ""
        # Se registran las claves del estado donde algo parezca un objeto. La
        # bolsa (`state.items`) salía SIEMPRE vacía pese a coger objetos, así
        # que los objetos se guardan en otra clave del estado: esto lo deja claro.
        pista = {k: v for k, v in (info.get("todo") or {}).items()
                 if re.search(r"item|passiv|bag|held|invent", k, re.I)}
        return (f" | TM usado: {info['usedTM']}, bolsa: {info['items']}"
                + (f" | donde hay objetos: {pista}" if pista else ""))

    def orden_contragolpe(self, equipo: list[dict], mapa: dict,
                          atajo_elegido) -> list[str]:
        """Orden del equipo para el entrenador elegido, según su especialidad.

        Se lee la especialidad del rival con `trainerSpecialtyTypes` a partir
        del sprite del nodo, y se pone delante al món que mejor le responde
        **y mejor aguanta**: contra un entrenador se juega a ganar rápido y
        salir entero, así que el orden no mira solo el tipo sino también cuánto
        aguanta cada uno y cómo llega de vida.

        Si el entrenador es de tipo "Diversos" no hay tipos que mirar: se
        devuelve la lista vacía y el orden por defecto se queda como estaba,
        que en ese caso deja al principal en segundo.
        """
        sprite = None
        for n in mapa.get("nodos", []):
            if str(n.get("atajo")) == str(atajo_elegido):
                sprite = n.get("sprite")
                break
        if not sprite:
            return []
        tipos: list[str] = []
        nivel_rival = None
        try:
            tipos = self.j.trainer_tipos(sprite) or []
            for n in self.j.nodos_del_estado():
                if n.get("type") != "trainer":
                    continue
                if self._mismo_sprite(n.get("sprite"), sprite):
                    nivel_rival = n.get("nivel")
                    break
        except Exception as exc:  # noqa: BLE001
            self.log(f"  no se pudo leer la especialidad del entrenador: {exc}")
            tipos = []
        if not tipos:
            self.log(f"  ⋯ {sprite} es de tipo 'Diversos': sin contragolpe posible")
            return []
        orden = P.orden_para_entrenador(equipo, tipos, nivel_rival)
        if orden:
            self.log(f"  ⋯ contragolpe contra {sprite} "
                     f"({'/'.join(tipos)}, Nv{nivel_rival or '?'}): {orden}")
        return orden

    @staticmethod
    def _mismo_sprite(a, b) -> bool:
        """Los sprites no coinciden en formato: `bug-catcher` en el SVG y
        `bugCatcher` en el estado."""
        def norm(s):
            s = str(s or "").lower()
            for sep in ("-", "_", " "):
                s = s.replace(sep, "")
            return s
        return bool(a) and norm(a) == norm(b)

    def ids_alcanzables(self, mapa: dict) -> set[str]:
        """Ids de los nodos a los que se puede ir desde el nodo actual.

        Ojo con la forma: `mapa["actual"]` es el **id** del nodo actual (un
        string) y `mapa["edges"]` es una lista de pares `[desde, hasta]`. No es
        un dict, y asumirlo reventaba la run entera con un `AttributeError` en
        cada paso.
        """
        actual = mapa.get("actual")
        destino = set()
        for e in (mapa.get("edges") or []):
            if isinstance(e, (list, tuple)) and len(e) == 2:
                desde, hasta = e
                if str(desde) == str(actual):
                    destino.add(str(hasta))
            elif isinstance(e, dict):
                if str(e.get("from")) == str(actual):
                    destino.add(str(e.get("to")))
        return destino

    def hay_cura_disponible(self, mapa: dict) -> bool:
        """¿Hay un nodo de curación entre los que se puede ir ahora?

        Lo necesita el planificador: un equipo medio muerto tiene que ir a curar
        antes que a pelear, y la decisión depende de que haya cura a mano.
        """
        ids = self.ids_alcanzables(mapa)
        if not ids:
            return False
        for n in mapa.get("nodos", []):
            if str(n.get("id")) not in ids:
                continue
            tipo = (P.tipo_de_estado(n.get("tipo")) if n.get("tipo")
                    else P.tipo_de_nodo(n.get("sprite", "")))
            if tipo == "cura":
                return True
        return False

    def _mapa(self) -> str:
        m = self.j.mapa()
        # Con tipos, no en crudo: el orden del equipo y la elección de captura
        # los calculan funciones que necesitan los tipos de cada món, y sin ellos
        # todos empatan a 1.0 y el orden de salida es alfabético. Medido:
        # `contragolpe contra fire-spitter (Fire)`sSacaba a Bulbasaur (Planta, 2x
        # de Fuego) delante de Geodude (Roca/Tierra, 2x de Fuego) porque el
        # equipo llegaba sin tipos.
        equipo = self.equipo_con_tipos()
        # Se confirma aquí la captura pendiente y no en `catch-screen`: tras
        # pelear por un món se vuelve al mapa y no se pasa otra vez por la
        # pantalla de captura, así que allí nunca se arrive a contarla (medido:
        # equipo de 2 y "capturas: 0").
        pend = getattr(self, "_catch_pendiente", None)
        if pend is not None:
            if len(equipo) > pend:
                self.capturas += 1
                self.capturas_pantalla += 1
                self.log(f"  >>> CAPTURA confirmada "
                         f"(equipo {pend}->{len(equipo)}) | total {self.capturas}")
            self._catch_pendiente = None
        insignias = self.j.insignias()
        # Reinicio del contador de capturas por pantalla. Se hace al **cambiar de
        # ruta**, que es lo que pediste ("capturar uno por pantalla"): antes el
        # contador se poveía pero no se reiniciaba nunca, así que tras la primera
        # captura el bot no cazaba **en toda la partida** y acababa con dos
        # Pokémon sin cobertura (contra Misty caía con Bulbasaur y Doduo, sin
        # nada de Agua). Medido en seis runs: 0-1 insignias y 1 captura.
        if self.pantalla_actual != (m.get("info") or ""):
            self.pantalla_actual = m.get("info") or ""
            self.capturas_pantalla = 0
        # Si el tutor de movimientos no está accesible todavía, se busca el
        # primer salto hacia él: sin esto nunca se llegaba (0 mapas con tutor
        # accesible en una partida entera) y es la única palanca de daño.
        tutor_hacia = P.siguiente_hacia(m.get("actual"), m["nodos"],
                                         m.get("edges") or [])
        if tutor_hacia and tutor_hacia != getattr(self, "_tutor_visto", None):
            self._tutor_visto = tutor_hacia
            self.log(f"  → buscando el tutor de movimientos por {tutor_hacia}")
        # El planificador puntúa los nodos según lo que **falta** (nivel, vida,
        # listón del jefe) en vez de según lo que es el nodo. Es el cambio que
        # decide las runs: antes, contra Erika (nv32), el bot llegaba a 26-31 y
        # el filtro exacto decía "no preparado" y entraba a ciegas.
        alcanzables = self.ids_alcanzables(m)
        tipos_alcanzables = [
            (P.tipo_de_estado(n.get("tipo")) if n.get("tipo")
             else P.tipo_de_nodo(n.get("sprite", "")))
            for n in m["nodos"]
            if str(n.get("id")) in alcanzables
        ]
        # **Reroll del mapa (tecla R).** La guía lo recomienda expressly para
        # "apuntar a un trade o a un mejor camino de exp", que son justo las dos
        # cosas que faltan: sin trainers cerca y con el jefe como única salida.
        # Solo se rerollea en ese caso y como mucho 3 veces por partida: tirar el
        # mapa sin parar puede perder el progreso del momento.
        # **Buscar un trade a proposito.** El trade sale con peso 5 frente a 30
        # de los entrenadores, asi que sale rarisimo por azar. Pero la guia dice
        # justo eso: "re-roll the map with the R key to pull a different set of
        # nodes - useful to aim for a trade". Como es el nodo mas rentable del
        # juego (+3 niveles, vida llena), buscarlo a proposito es la jugada
        # correcta, no un truco. Se hace una vez por mapa como maximo.
        if (not self._trade_hecho and self._rerolls_busqueda < 2
                and "trade" not in tipos_alcanzables
                and len(self.nodos_vistos) < 12):
            self._rerolls_busqueda += 1
            self.log(f"  ↻ buscando trade (intento {self._rerolls_busqueda}/2): "
                     f"no hay nodo de trade a la vista y la guia dice tirar el "
                     f"mapa para buscarlo")
            try:
                self.j.page.keyboard.press("r")
                self.j.page.wait_for_timeout(600)
                return "buscando trade: reroll del mapa"
            except Exception as exc:  # noqa: BLE001
                self.log(f"  !! busqueda de trade fallo: {exc}")

        if (self._rerolls < 3
                and "jefe" in tipos_alcanzables
                and not ({"entrenador", "batalla"} & set(tipos_alcanzables))):
            self._rerolls += 1
            self.log(f"  ↻ reroll del mapa ({self._rerolls}/3): sin trainer ni "
                     f"combate y el jefe como única salida, la guía dice tirar "
                     f"el mapa para buscar trade o exp")
            try:
                self.j.page.keyboard.press("r")
                self.j.page.wait_for_timeout(600)
                self._leer_mapa_cache = None
                return "reroll: buscando un trade o un camino de exp"
            except Exception as exc:  # noqa: BLE001
                self.log(f"  !! reroll falló: {exc}")

        d = PL.elegir(equipo, m["nodos"],
                      ctx_extra={
                          "hay_cura": self.hay_cura_disponible(m),
                          "tiene_bolsa": not self.bolsa_vacia(),
                          "tutor_listo": bool(tutor_hacia),
                          "capturas_pantalla": self.capturas_pantalla,
                          # El jefe es inevitable solo cuando no queda nada que
                          # dé experiencia. Es el caso que mataba las runs:
                          # entrar a ciegas por ser "la única salida".
                          "es_jefe_unica_salida": (
                              "jefe" in tipos_alcanzables
                              and not any(t in ("batalla", "entrenador")
                                          for t in tipos_alcanzables)),
                      },
                      region=self.region, insignias=insignias,
                      ids_disponibles=alcanzables,
                      info_mapa=m.get("info", ""),
                      edges=m.get("edges") or [],
                      nodo_actual=m.get("actual"))
        self.anotar(d)
        # Registro de qué nodos del mapa han ido apareciendo, para poder ver si
        # la ruta se queda sin nodos de exp o si simplemente no hay más.
        self.nodos_vistos.add((m.get("info") or "ruta?", str(d.valor)))
        # El tipo del líder es **por ruta**: se recalcula en cada mapa a partir
        # del sprite del nodo de gimnasio. Cachearlo sin más hacía que, tras
        # vencer a Brock (Roca), el bot siguiera cazando para Roca en Mt Moon
        # donde el rival es Misty (Agua), y el equipo se cerraba en un tipo.
        # En `catch-screen` sí se reutiliza el valor del último mapa.
        lider_mapa = P.tipo_lider_del_mapa(m["nodos"]) or self.tipo_lider_actual()
        if lider_mapa:
            self.tipo_lider = lider_mapa
        if insignias != self.ultima_insignia:
            self.log(f"  >> insignias: {self.ultima_insignia} -> {insignias}")
            self.ultima_insignia = insignias
        # Traza de progresión: ruta, niveles y tipo de líder. Sirve para ver si
        # el equipo llega con nivel suficiente o se queda corto siempre.
        niv = [m_["nivel"] for m_ in equipo if m_.get("nivel")]
        vivos = sum(1 for m_ in equipo if (m_.get("ps") or 0) > 0)
        # El adelanto del equipo decide contra los jefes: se reordena arrastrando
        # los slots. La exp se concentra en el delantero, así que quién va
        # primero decide cuánto sube cada món (ver `politica.orden_deseado`).
        #
        # Contra un entrenador se puede ir más allá: la especialidad del rival
        # se lee del estado del juego ANTES de pelear, así que se pone al
        # frente el món que mejor le responde. Antes entraba con lo que tocara
        # y se comía trainers a 0.5x.
        orden = None
        if d.tipo == "entrenador":
            orden = self.orden_contragolpe(equipo, m, d.valor)
        elif d.tipo == "jefe":
            # Contra el jefe el orden sale del planificador: al frente el món que
            # pegue a 2x **y** más aguante, porque contra un líder lo que mata es
            # la vida que aguanta mientras los demás pegan.
            con_tipos = [{**m, "tipos": self._tipos_de_m(m.get("nombre"))}
                         for m in equipo]
            orden = PL.orden_para_jefe(con_tipos, PL.plan_para(self.region, insignias))
            if orden:
                self.log(f"  ⋯ orden contra {d.tipo}: {orden}")
        if d.tipo == "centro":
            self.centros += 1
        elif d.tipo == "tutor":
            self.tutores += 1
        # A qué tipo se ordena el equipo. Solo en los combates donde el rival es
        # **conocido**: entrenador (su especialidad) y jefe (su equipo). En las
        # batallas sueltas no se sabe qué sale, y aun así se le pasaba el tipo del
        # gimnasio como pista... y eso tenía un coste caro: el contragolpe
        # (Goldeen contra el Agua de Misty) iba al frente en todas las peleas de
        # la ruta, se gastaba y llegaba al gimnasio con 10 de 49 PS. Medido: así
        # moría en el segundo gimnasio con el mejor món del equipo medio muerto.
        # En el salvaje, sin tipo, el principal se reserva en segundo.
        # El principal **va delante también en las batallas sueltas**, y el
        # motivo es la experiencia: va casi entera al delantero, así que con el
        # principal en segundo el equipo llega al gimnasio por debajo de nivel
        # (medido: principal 15-17 y capturas 9-13 contra un rival de 18-20).
        # El desgaste de llevarlo delante se paga curando, no escondiéndolo.
        tipos_para_ordenar = None
        if not orden and d.tipo in ("batalla", "incognita", "otro", None):
            tipos_para_ordenar = P.tipos_del_rival(self.region, insignias)
        self.ordenar_equipo(equipo, insignias, d.tipo or "otro", orden,
                            tipos_para_ordenar)
        clica = [n for n in m["nodos"] if n.get("clickable")]
        tipos_disponibles = [P.tipo_de_estado(n.get("tipo")) if n.get("tipo")
                             else P.tipo_de_nodo(n.get("sprite")) for n in clica]
        self.log(f"  · {m.get('info') or 'ruta?'} | equipo {len(equipo)} (vivos {vivos}) "
                 f"niv {min(niv) if niv else 0}-{max(niv) if niv else 0} "
                 f"| lider {self.tipo_lider} | insignias {insignias} "
                 f"| disponibles {tipos_disponibles} "
                 f"| total {len(m['nodos'])}/{len(self.nodos_vistos)}"
                 + self.diagnostico_estado())
        if d.valor:
            self.j.clic_por_atajo(str(d.valor))
        return f"nodo {d.valor}"

    def firma_batalla(self) -> str:
        """Huella barata del estado de la batalla, para distinguir avance de atasco."""
        try:
            eb = self.j.estado_batalla()
        except Exception:  # noqa: BLE001
            return ""
        return "|".join(
            f"{e['nombre']}:{e['ps']}" for e in eb["enemigos"]
        ) + "#" + "|".join(f"{m['nombre']}:{m['ps']}" for m in eb["mios"] if m["ps"])

    def volcar_atasco(self, pantalla: str) -> None:
        """Guarda el HTML de la pantalla atascada para poder diagnosticarla.

        Sin esto un atasco solo produce "no avanza" y obliga a adivinar qué
        botón falta. Se vuelcan también los botones ocultos o deshabilitados:
        el fallo típico es un botón presente en el DOM pero no pulsable.
        """
        try:
            datos = self.j.page.evaluate(
                r"""(id) => {
                    const s = document.getElementById(id);
                    const todos = [...document.querySelectorAll('#' + id + ' button')]
                      .map(b => ({
                        id: b.id || null,
                        shortcut: b.dataset.shortcut || null,
                        texto: (b.innerText || '').trim().slice(0, 30),
                        visible: !!b.offsetParent,
                        disabled: b.disabled === true,
                        clase: b.className || null,
                      }));
                    return { html: s ? s.outerHTML : '(sin pantalla)',
                             botones: todos };
                }""",
                pantalla,
            )
            destino = Path(f"/tmp/opencode/atasco_{pantalla}.html")
            destino.write_text(datos["html"], encoding="utf-8")
            self.log(f"  volcado -> {destino}")
            for b in datos["botones"]:
                self.log(f"    boton id={b['id']} atajo={b['shortcut']} "
                         f"visible={b['visible']} disabled={b['disabled']} "
                         f"texto={b['texto']!r}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"  no se pudo volcar el atasco: {exc}")

    def _desbloquear(self) -> str:
        """Saca al bot de una pantalla en la que se atasca.

        Sin conocer de antemano el HTML de cada aviso (cambia món desmayado,
        confirmaciones, diálogos), se prueban las salidas habituales: Escape,
        botones visibles con atajo que no sean "skip", y la primera opción de
        cualquier capa superior abierta.
        """
        for _ in range(2):
            self.j.page.keyboard.press("Escape")
            self.j.page.wait_for_timeout(300)
            info = self.j.page.evaluate(
                """() => {
                  const vis = (e) => e && e.offsetParent !== null;
                  const capas = [...document.querySelectorAll(
                    '[class*=modal],[class*=overlay],[class*=dialog],[class*=popup]')]
                    .filter(vis);
                  const capa = capas[capas.length - 1];
                  const botones = [...document.querySelectorAll('button,[role=button],.btn')]
                    .filter(vis)
                    .map((b) => ({
                      id: b.id || '',
                      atajo: b.dataset.shortcut || '',
                      txt: (b.innerText || '').trim().slice(0, 30),
                      deshabilitado: !!b.disabled,
                    }))
                    .filter((b) => !b.deshabilitado);
                  return {
                    hay_capa: !!capa,
                    opciones_capa: capa
                      ? [...capa.querySelectorAll('[data-shortcut],.poke-card,button')]
                          .filter(vis)
                          .map((e) => ({ atajo: e.dataset.shortcut || '',
                                         txt: (e.innerText || '').trim().slice(0, 30) }))
                      : [],
                    botones: botones.slice(0, 12),
                  };
                }"""
            )
            if info["hay_capa"] and info["opciones_capa"]:
                op = info["opciones_capa"][0]
                if op["atajo"]:
                    self.j.clic_por_atajo(str(op["atajo"]))
                else:
                    self.j.clic_texto(op["txt"][:12])
                self.log(f"  desbloqueo: capa con {len(info['opciones_capa'])} opciones")
                return "desbloqueado (capa)"
            utiles = [b for b in info["botones"]
                      if b["atajo"] and "skip" not in b["txt"].lower()]
            if utiles:
                self.j.clic_por_atajo(str(utiles[0]["atajo"]))
                self.log(f"  desbloqueo: boton {utiles[0]['id'] or utiles[0]['txt'][:20]}")
                return "desbloqueado (boton)"
            self.j.page.wait_for_timeout(500)
        return "desbloqueo sin efecto"

    def _batalla(self) -> str:
        d = P.decidir_batalla(self.j.visible("#btn-auto-battle"))
        self.anotar(d)
        # Volcado del estado para poder diagnosticar hasta dónde llega el equipo.
        if getattr(self, "_n_batalla", 0) % 4 == 0:
            try:
                eb = self.j.estado_batalla()
                niv_enem = [e["nivel"] for e in eb["enemigos"] if e.get("nivel")]
                self._ultimo_rival = eb["titulo"]
                self.log(f"  estado: {eb['titulo']} | niveles rivales "
                         f"{min(niv_enem) if niv_enem else '?'}-"
                         f"{max(niv_enem) if niv_enem else '?'}")
                self.log(f"  enemigos={[(e['nombre'], e['ps'], e['nivel']) for e in eb['enemigos']]}")
                self.log(f"  mios={[(m['nombre'], m['ps'], m['nivel']) for m in eb['mios'] if m['ps']]}")
                # **PS real.** La barra del HUD (`equipo()`) da un porcentaje que
                # en un món caido se queda clavado en 100: por eso el bot veía
                # "Bulbasaur(100/100)" con 0/19 de vida y por eso nunca.curaba.
                # La pantalla de combate si trae el valor real ("0/19"), asi que
                # se guarda aqui y se aplica encima del porcentaje.
                import re as _re
                for m in eb["mios"]:
                    t = str(m.get("ps") or "")
                    mm = _re.match(r"\s*(\d+)\s*/\s*(\d+)\s*$", t)
                    if mm:
                        self._ps_real[(m.get("nombre") or "").strip().lower()] = (
                            int(mm.group(1)), int(mm.group(2)))
            except Exception as exc:  # noqa: BLE001
                self.log(f"  estado no legible: {exc}")
        # Se recuerda el nivel más alto que se ha visto: sirve para decidir si
        # un entrenador es arriesgado (perder una pelea de entrenador termina
        # la run). Los de Route 1 medían 3-4 y eran ganados de sobra; en rutas
        # posteriores suben.
        try:
            eb = self.j.estado_batalla()
            for e in eb["enemigos"]:
                if e.get("nivel"):
                    self.nivel_enemigo_max = max(self.nivel_enemigo_max, e["nivel"])
            # Cuántos móns trae el rival: a igual nivel, un entrenador de dos
            # móns contra un equipo de uno es imposible de ganar. En Mt Moon un
            # Firebreather (Charmander+Ponyta, 0.5x los dos) tumba a un
            # Bulbasaur solo del mismo nivel, y perderunes battle de
            # entrenador termina la run.
            self.enemigos_max_vistos = max(self.enemigos_max_vistos, len(eb["enemigos"]))
        except Exception:  # noqa: BLE001
            pass
        self._n_batalla = getattr(self, "_n_batalla", 0) + 1
        # `btn-continue-battle` y `btn-auto-battle` llevan data-shortcut="Space".
        for sel in ("#btn-continue-battle", "#btn-auto-battle"):
            if self.j.visible(sel):
                via = self.j.activar(sel)
                return f"batalla ({via})"
        # Sin botones visibles el juego está animando. Eso no es un atasco: se
        # espera a que aparezca uno y se devuelve `None` para que el bucle no lo
        # cuente como paso repetido (antes provocativeaba ATASCADO falso en
        # contra cualquier animación larga).
        if self.j.esperar_boton("#btn-continue-battle, #btn-auto_battle", 12):
            return self._batalla()
        return self.ESPERA

    def ordenar_equipo(self, equipo: list[dict], insignias: int,
                       tipo_nodo: str = "otro",
                       orden: list[str] | None = None,
                       tipos_rival: list[str] | None = None) -> None:
        """Reordena el equipo arrastrando los slots del HUD.

        Los slots son `.team-slot-reorder` (arrastre por puntero). El reparto de
        experiencia sigue al delantero, así que la posición decide cuánto sube
        cada món; si el arrastre falla se sigue jugando igual, solo se pierde
        esa optimización.

        `orden` es un orden ya decidido (el contragolpe contra un entrenador) y
        tiene prioridad sobre el que saldría de `politica.orden_deseado`.
        """
        if len(equipo) < 2 or not self.j.equipo():
            return
        orden_actual = self.j.orden_equipo()
        if not orden_actual:
            return
        # `tipos_rival` es lo que arregla el caso Doduo-contra-Brock: sin el
        # tipo del rival, `orden_deseado` trata la pelea como si fuera a ciegas y
        # reserva al principal en segundo, dejando al frente un món que se come
        # un 2x. El tipo del líder del mapa es la mejor pista disponible para un
        # combate salvaje, así que se le pasa.
        deseado = orden or P.orden_deseado(equipo, insignias, self.region,
                                            tipo_nodo, tipos_rival)
        deseado = [n for n in deseado if n]
        if not deseado or deseado == orden_actual:
            return
        if self.j.reordenar_equipo(deseado):
            self.log(f"  ⋯ reordenado: {orden_actual} -> "
                     f"{self.j.orden_equipo()} (para {tipo_nodo})")
        elif self._reordenes_fallidos < 3:
            self._reordenes_fallidos += 1
            self.log(f"  ⋯ no se pudo reordenar (quedó {self.j.orden_equipo()})")

    def tipo_lider_actual(self) -> str | None:
        """`#map-info` dice "Route 1: vs Brock (Rock)"; de ahí sale el tipo."""
        import re as _re
        m = _re.search(r"\(([A-Za-zÁÉÍÓÚáéíóúñ /]+)\)\s*$", self.j.texto("#map-info") or "")
        return m.group(1).strip() if m else None

    def _falta_nivel_para_jefe(self) -> float:
        """Niveles que le faltan al equipo para igualar al líder que toca.

        Sin cazar mientras falte nivel. La captura es un nodo, y ese nodo es
        justo el nivel que falta: medido, cazando un Rattata sin ninguna
        ventaja se perdía contra Brock por 4 niveles de diferencia.
        """
        try:
            insignias = self.j.insignias()
            plan = PL.plan_para(self.region, insignias)
            niveles = [m.get("nivel") or 0 for m in self.equipo_con_tipos()
                       if (m.get("nivel") or 0) > 0]
            if not niveles:
                return 0.0
            return max(0.0, plan.nivel_min - (sum(niveles) / len(niveles)))
        except Exception:  # noqa: BLE001
            return 0.0

    def _catch(self) -> str:
        # La captura no se resuelve aquí: se pelea, y el equipo crece una
        # pantalla o dos después. Se guarda la marca y se comprueba al volver al
        # mapa, que es cuando ya se sabe si entró. Medirlo dentro de
        # `catch-screen` daba 0 capturas con el equipo claramente llenado.
        if not hasattr(self, "_catch_pendiente"):
            self._catch_pendiente = None
        # Sin cazar si el equipo va corto de nivel: la captura es un nodo que
        # se pierde, y ese nodo es exactamente el nivel que falta.
        vivos = sum(1 for m in self.equipo_con_tipos() if (m.get("ps") or 0) > 0)
        if self.capturas_pantalla >= 1:
            self.j.activar("#btn-skip-catch")
            return "huyo: ya se cazó uno en esta pantalla (prioridad es nivel)"
        # Con **menos de 3 en pie** se caza siempre, sea cual sea el nivel.
        # El veto por nivel era demasiadoRotundo: medido, el bot se quedó con
        # un solo Bulbasaur y perdía contra un Grunt del Team Rocket con el
        # món a 100 PS. Un equipo de uno no gana nada; con dos ya se puede.
        # Sin veto por nivel: el libro de jugadas es "captura uno al principio
        # y luego a por nivel", no "solo captura si vas sobrado".
        self._catch_ignora_nivel = vivos < 3
        if self.capturas_pantalla >= 1:
            # Ya se cazó en esta pantalla: el resto de móns son nivel disfrazado.
            self.j.activar("#btn-skip-catch")
            return "huyo: ya se cazó uno en esta pantalla (prioridad es nivel)"
        equipo = self.equipo_con_tipos()
        cands = self.cartas_con_datos("#catch-choices")
        insignias = self.j.insignias()
        # Dos referencias y no una: el gimnasio de la ruta que se está jugando
        # es lo urgente, el siguiente es a lo que hay que anticiparse. Se cazaba
        # solo para el siguiente y por eso entraba un Ponyta (0.5x contra
        # Misty) por ser 1x contra el gimnasio tres, y se perdía en Mt Moon.
        actual = self.tipo_lider or self.tipo_lider_actual()
        # [actual, siguiente, el de después]: la captura tiene que tapar el
        # primer gimnasio que el equipo no cubra ya con un 2x, que no siempre es
        # el actual ni el siguiente.
        proximos = P.proximos_jefes(self.region, insignias, 3)
        d = P.elegir_captura(equipo, cands, actual,
                             (proximos[1:2] or [None])[0],
                             P.MAX_EQUIPO, proximos, self.region,
                             ignorar_nivel=bool(getattr(self, "_catch_ignora_nivel", False)))
        self._catch_ignora_nivel = False
        self.anotar(d)
        if d.valor:
            # Si el equipo está lleno, el juego abrirá `swap-screen` para elegir
            # a quién se sustituye. Se apunta el objetivo ahora (el peor
            # miembro) porque en la pantalla siguiente ya no sabemos cuál de los
            # candidatos salió.
            vivos = [m for m in equipo if (m.get("ps") or 0) > 0]
            if len(vivos) >= P.MAX_EQUIPO:
                flojo = min(vivos, key=lambda m: (
                    (m.get("nivel") or 0),
                    -sum((m.get("baseStats") or {}).values()),
                    m.get("nombre") or ""))
                self._swap_objetivo = flojo.get("nombre")
                self.log(f"  ⋯ equipo lleno: sustituiré a {self._swap_objetivo}"
                         f" por {self.log}")
            self._catch_pendiente = len(self.j.equipo())
            self.j.clic_por_atajo(str(d.valor))
            return f"peleo por {d.razon}"
        self.j.activar("#btn-skip-catch")
        return f"huyo: {d.razon}"

    def _opciones_genericas(self, cont: str, fallback: str, etiqueta: str) -> str:
        ops = self.j.opciones(cont)
        self.log(f"  {etiqueta}: {[o['txt'] for o in ops] or 'sin opciones'}")
        # Las opciones con `data-shortcut` se activan por tecla; el resto, por clic.
        elegidas = [o for o in ops if o.get("atajo") and o["sel"] != f"#{fallback.lstrip('#')}"]
        if elegidas:
            self.j.clic_por_atajo(str(elegidas[0]["atajo"]))
            return f"{etiqueta} (tecla {elegidas[0]['atajo']})"
        if ops:
            self.j.clic(ops[0]["sel"])
            return f"{etiqueta} (clic)"
        self.j.activar(fallback)
        return f"{etiqueta} (fallback {fallback})"

    def _badge(self) -> str:
        self.anotar(P.Decision("insignia", True,
                               f"insignia conseguida (total {self.j.insignias()})"))
        self.j.activar("#btn-next-map")
        return "mapa siguiente"

    def _item(self) -> str:
        """Los nodos de item de Pokelike dan pasivos, no curas.

        Curar solo se puede en `poke-center`, así que saltarse la opción
        desperdicia el nodo: se elige el pasivo más útil y punto.

        La secuencia importa y no es la intuitiva, medido sobre el sitio:
        con un clic real sobre la carta y luego `Space` la pantalla avanza; con
        el atajo numérico solo, o con `Space` solo, el modal se queda igual y
        la run se cuelga. El clic real es lo que "despierta" el modal.
        """
        self.objetos += 1
        ops = self.j.opciones("#item-choices")
        self.log(f"  item: {[o['txt'] for o in ops] or 'sin opciones'}")
        # Volcado del DOM: la bolsa llegaba **siempre vacía** pese a que el bot
        # elegía un objeto, que apunta a que la vía de salida estaba pulsando
        # "Skip" y tirando lo elegido. Con el DOM se ven los selectores reales.
        self._volcar_item()
        if not ops:
            self.j.clic("#btn-skip-item")
            self.j.page.keyboard.press("Space")
            return "item (sin opciones, saltado)"
        # Prioridad: los discos (TM) primero, porque suben el tier de los
        # ataques y es la única palanca real de daño que tiene el bot: las
        # batallas se auto-resuelven y no se puede elegir movimiento. Después
        # los caramelos de nivel, que suben puntos de golpe, y por último los
        # pasivos, que no cambian el desenlace de una pelea.
        # Prioridad de objeto, de la guía de la comunidad y medida:
        #   1. **Lucky Egg**: +30% de probabilidad de nivel extra en cada
        #      combate. Es el mejor objeto de la primera mitad porque el
        #      bonus compone a lo largo de toda la run, y el nivel es
        #      exactamente lo que decide loserlandos. No estaba en la lista.
        #   2. Discos / tier de movimiento: suben el único ataque del món.
        #   3. Semillas y objetos que quitan el tipo secundario (la Semilla
        #      Milagro deja a Bulbasaur en Planta puro y le quita tres
        #      debilidades, que son las del Veneno): al principal.
        #   4. Caramelos de nivel, y luego pasivos defensivos.
        # Prioridad que marca la guia, y esta vez en su orden:
        #   1. **Lucky Egg**: 30% de nivel extra por combate. La guia lo llama
        #      "rompedor al principio de la partida" porque compone en cada
        #      nodo. Es lo que mas nivel da y el nivel es lo que mata.
        #   2. **Objetos de tipo que coincidan con el equipo**: hacen atacar con
        #      ese tipo y dan +40%. En el chart del juego Planta contra Roca es
        #      2x, asi que la Semilla Milagro sobre un Bulbasaur es lo que le
        #      quita el 0.5x del Veneno.
        #   3. **Defensivos en el carry**: Rocky Helmet, Red Card, Leftovers.
        #   4. Lo demas. Y **descartar los de estadistica de un solo uso**
        #      (Wide Lens, Choice Band), que la guia dice que no vale la pena.
        orden = ("lucky egg", "huevo sorta",
                 "miracle seed", "charcoal", "mystic water", "silk scarf",
                 "sharp beak", "magnet", "twisted spoon", "soft sand",
                 "hard stone", "poison barb", "spell tag", "black glasses",
                 "metal coat", "pixie plate", "dragon fang",
                 "rocky helmet", "red card", "leftovers", "shell bell",
                 "assault vest",
                 "quick claw", "choice scarf", "king's rock",
                 "wide lens", "choice specs", "expert belt", "scope lens")
        elegido = min(
            ops,
            key=lambda o: next((i for i, k in enumerate(orden)
                                if k in (o.get("txt") or "").lower()), 99),
        )
        # **Por atajo, no por clic.** Las cartas de esta pantalla son
        # `.item-card` con `data-shortcut="1|2|3"`, igual que los starters, y
        # con un clic normal el objeto **no se guarda**: la bolsa daba `[]` en
        # todas las partidas, o sea que el bot llevaba cincuenta nodos de
        # objeto desperdiciados en silencio.
        if elegido.get("atajo"):
            self.j.clic_por_atajo(str(elegido["atajo"]))
            via = f"tecla {elegido['atajo']}"
        else:
            self.j.clic(elegido["sel"])
            via = "clic"
        self.j.page.wait_for_timeout(400)
        self.items_tomados += 1
        self.anotar(P.Decision("item", elegido.get("txt", "")[:40],
                               f"tomo {self.items_tomados}/{self.MAX_ITEMS} por {via}"))
        # Salir de la pantalla probando vías, de la más barata a la más fuerte.
        # Medido: el clic real "despierta" el modal, pero según el momento ni
        # siquiera con él avanza, y quedarse aquí bloquea la run entera.
        vias = (
            ("tecla Space", lambda: self.j.page.keyboard.press("Space")),
            ("tecla Space", lambda: self.j.page.keyboard.press("Space")),
            ("clic JS en SKIP", lambda: self.j.page.evaluate(
                "() => { const b = document.getElementById('btn-skip-item');"
                " if (!b) return false; b.click(); return true; }")),
            ("tecla Enter", lambda: self.j.page.keyboard.press("Enter")),
            ("tecla Escape", lambda: self.j.page.keyboard.press("Escape")),
            ("clic forzado en SKIP", lambda: self.j.clic("#btn-skip-item", 2)),
        )
        for intento, (nombre, via) in enumerate(vias):
            via()
            self.j.page.wait_for_timeout(500)
            if self.j.pantalla() != "item-screen":
                self.log(f"  item: salida con '{nombre}' (intento {intento + 1})")
                return f"item {elegido.get('txt', '')[:40]}"
            self.log(f"  item: '{nombre}' no funcionó")
        return self.ESPERA

    def _pasivo(self) -> str:
        return self._opciones_genericas("#passive-choices", "#btn-skip-item", "pasivo")

    def _swap(self) -> str:
        """Sustituye al món indicado en `_catch`, no al primero que encuentre.

        Llega aquí cuando el equipo está lleno y sale un món mejor: el juego
        pregunta a quién se cambia. Se sustituye al **peor** (menor nivel y
        estadísticas), que es lo que libera la plaza para el que entra.
        """
        objetivo = getattr(self, "_swap_objetivo", None)
        if objetivo:
            ops = self.j.opciones("#swap-choices")
            elegido = next(
                (o for o in ops if objetivo.lower() in (o.get("txt") or "").lower()),
                None)
            if elegido:
                if elegido.get("atajo"):
                    self.j.clic_por_atajo(str(elegido["atajo"]))
                else:
                    self.j.clic(elegido["sel"])
                self._swap_objetivo = None
                self.log(f"  ⋯ sustituido: sale {objetivo}")
                return f"swap: fuera {objetivo}"
        return self._opciones_genericas("#swap-choices", "#btn-cancel-swap", "swap")

    def _trade(self) -> str:
        """Acepta el trade: +3 niveles y PS completos, el nodo más rentable.

        Ids reales sacados del bundle del juego (jugar contra `trade-choices` a
        pelo no funcionaba, y el botón de acepta **no** es `Space`):

        - `#trade-screen` — la pantalla
        - `#trade-mystery-card` — el món que se recibe, **con su tipo**
        - `#trade-team-list` / `.trade-member-row` — a quién se sacrifica
        - `#btn-trade-continue` — confirmar
        - `#btn-skip-trade` — declinar

        El món que llega trae tipo, así que después toca **reordenar al más
        efectivo**, y solo si el nuevo tiene más de la mitad de la vida (viene
        con la vida llena, así que normalmente la tiene): por debajo del 50% se
        reserva al final, que es la regla general de heridos.

        Mientras no se consiga cerrar el trade, se vuelca la pantalla a
        `/tmp/opencode/trade.json` para leer los selectores de verdad en vez de
        adivinar: es el nodo más rentable del juego y no se puede seguir
        ignorando.
        """
        try:
            recibido = self.j.page.evaluate(
                """() => {
                    const c = document.querySelector('#trade-mystery-card');
                    if (!c) return null;
                    return (c.innerText || '').replace(/\\s+/g, ' ').trim();
                }"""
            )
            if recibido:
                self.log(f"  trade ofrece: {recibido[:90]}")

            # A quién se sacrifica: el que menos aporta. La guía dice
            # claramente "cambia tu peor món no-starter".
            #
            # OJO: aquí NO se reordena. `ordenar_equipo()` ya se llama en cada
            # nodo del mapa, así que el món que llega por trade entra con la
            # vida llena y se coloca solo como el más efectivo. Llamar a un
            # método inexistente aquí reventaba el trade entero.
            equipo = self.equipo_con_tipos()
            vivos = [m for m in equipo if (m.get("ps") or 0) > 0]
            if vivos:
                victimario = min(
                    vivos,
                    key=lambda m: (
                        sum((m.get("baseStats") or {}).values())
                        if m.get("baseStats") else 0,
                        -(m.get("nivel") or 0),
                        m.get("nombre") or ""),
                )
                self.log(f"  trade: se ofrece {victimario.get('nombre')}")
                fila = self.j.page.evaluate(
                    """(nombre) => {
                        const filas = [...document.querySelectorAll(
                            '#trade-team-list .trade-member-row')];
                        const f = filas.find(x => (x.innerText || '')
                                    .indexOf(nombre) >= 0);
                        if (f) { f.click(); return true; }
                        return filas.length > 0;
                    }""",
                    str(victimario.get("nombre") or ""),
                )
                if not fila:
                    # Sin lista de equipo, al menos se pulsa la primera fila.
                    self.j.page.evaluate(
                        """() => {
                            const f = document.querySelector(
                                '#trade-team-list .trade-member-row');
                            if (f) f.click();
                        }"""
                    )
                self.j.page.wait_for_timeout(350)

            for sel in ("#btn-trade-continue", "#trade-continue",
                        "#btn-confirm-trade"):
                if self.j.visible(sel):
                    self.j.activar(sel)
                    self.j.page.wait_for_timeout(600)
                    break

            if self.j.pantalla() != "trade-screen":
                # El trade se acepta aqui, y el reordenado se hace solo en el
                # siguiente paso del mapa, que ya pasa por _reordenar para el
                # combate que toque. Se registra para poder medirlo.
                self._trade_hecho = True
                self.log("  ✓ trade aceptado (+3 niveles, PS completos) — "
                         "se reordena al más efectivo en el próximo nodo")
                return f"trade aceptado ({recibido or '?'})"
        except Exception as exc:  # noqa: BLE001
            self.log(f"  !! trade falló: {exc}")

        self._volcar_trade()
        if self.j.visible("#btn-skip-trade"):
            self.j.activar("#btn-skip-trade")
            return "trade declinado (no se pudo completar)"
        return self._opciones_genericas("#trade-choices", "#btn-skip-trade", "trade")

    def _volcar_trade(self) -> None:
        """Vuelca `#trade-screen` a disco para leer su DOM de verdad."""
        try:
            datos = self.j.page.evaluate(
                r"""() => {
                    const vis = e => e && e.offsetParent !== null;
                    const t = document.getElementById('trade-screen');
                    const out = {pantalla: null, card: '', filas: [],
                                 botones: [], nota: ''};
                    if (!t) { out.nota = 'no hay #trade-screen'; return out; }
                    out.pantalla = document.body.className;
                    const c = document.querySelector('#trade-mystery-card');
                    if (c) out.card = (c.innerText || '').replace(/\s+/g,' ').trim();
                    out.filas = [...document.querySelectorAll(
                        '#trade-team-list .trade-member-row')].map(f => ({
                        texto: (f.innerText || '').replace(/\s+/g,' ').trim(),
                        onclick: !!f.onclick,
                        dataset: Object.assign({}, f.dataset),
                    }));
                    out.botones = [...t.querySelectorAll('button, [role=button], '
                        + '[data-shortcut]')].filter(vis).map(b => ({
                        id: b.id || '', tag: b.tagName,
                        texto: (b.innerText || '').replace(/\s+/g,' ').trim().slice(0,40),
                        shortcut: b.dataset ? (b.dataset.shortcut || '') : '',
                    }));
                    return out;
                }"""
            )
            import json as _json
            import pathlib as _pl
            _pl.Path("/tmp/opencode/trade.json").write_text(
                _json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
            self.log(f"  · volcado de trade -> /tmp/opencode/trade.json "
                     f"({len(datos.get('botones') or [])} botones, "
                     f"{len(datos.get('filas') or [])} filas)")
        except Exception as exc:  # noqa: BLE001
            self.log(f"  !! volcado de trade fallo: {exc}")

    def _shiny(self) -> str:
        # Un shiny encontrado no aporta nada a una run por niveles: se rechaza.
        # El botón real es `#btn-skip-shiny` ("SKIP (FLEE)") y **no** tiene
        # data-shortcut, así que hay que pulsarlo por selector; buscar
        # `#btn-continue-battle` aquí dejaba la run bloqueada para siempre.
        if self.j.visible("#btn-skip-shiny"):
            return f"shiny (rechazado: {self.j.activar('#btn-skip-shiny')})"
        if self.j.visible("#btn-continue-battle"):
            return f"shiny ({self.j.activar('#btn-continue-battle')})"
        return self._opciones_genericas("#shiny-content", "#btn-skip-shiny", "shiny")

    def _stat_buff(self) -> str:
        return self._opciones_genericas("#stat-buff-choices", "#btn-continue-battle",
                                        "stat-buff")

    def _transicion(self) -> str:
        self.j.clic_por_atajo("Enter")
        return "transicion"

    def _elite_prep(self) -> str:
        """Prepara el combate contra un rival de élite y ** sale.

        Aquí se ve el equipo real del rival, se ordena al mejor contragolpe y
        se da el objeto de la bolsa al món que va a pelear. Es la última
        información buena que hay antes de pelear.

        Lo importante es que la pantalla tiene que **marcharse**. Medido: tras
        equipar un objeto el prep se quedaba 13 vueltas sin avanzar y la run
        acababa en ATASCADO, porque el overlay tapaba el botón de pelear. Por
        eso se insiste varias veces y se termina a lo bruto si hace falta:
        quedarse en la puerta es peor que pelear sin preparar.
        """
        try:
            info = self._preparar_contra_el_rival()
        except Exception as exc:  # noqa: BLE001
            info = f"error preparando ({exc})"
            self.log(f"  !! prep falló: {exc}")

        botones = ("#btn-elite-prep-continue", "#btn-elite-prep-fight",
                   "#elite-prep-choices button", "#elite-prep-choices .choice",
                   "#btn-elite-prep-fight-confirm")
        for intento in range(4):
            self.j.cerrar_modal_item()
            for sel in botones:
                if self.j.visible(sel):
                    via = self.j.activar(sel)
                    self.j.page.wait_for_timeout(500)
                    if self.j.pantalla() != "elite-prep-screen":
                        return (f"elite prep [{info}] -> {self.j.pantalla()} "
                                f"({via})")
            # Último recurso: si sigue aquí, se manda Enter y Escape.
            self.j.page.keyboard.press("Enter")
            self.j.page.wait_for_timeout(400)
            if self.j.pantalla() != "elite-prep-screen":
                return f"elite prep [{info}] -> {self.j.pantalla()} (Enter)"

        self.log("  !! el prep no cede: se fuerza la salida")
        for sel in ("#btn-elite-prep-fight", "#btn-elite-prep-continue",
                    "#elite-prep-screen button"):
            try:
                self.j.clic(sel, 1.5)
                self.j.page.wait_for_timeout(400)
                if self.j.pantalla() != "elite-prep-screen":
                    return f"elite prep [{info}] -> {self.j.pantalla()} (forzado)"
            except Exception:  # noqa: BLE001
                pass
        return f"elite prep [{info}] (no se pudo salir)"

    def _tipos_del_rival_en_prep(self) -> list[str]:
        """Los tipos del equipo enemigo que el prep enseña, vía el Pokédex."""
        from pkl_movimientos import tipos_de

        nombres = self.j.nombres_prep_rival()
        tipos: list[str] = []
        for n in nombres:
            for t in tipos_de(n):
                if t not in tipos:
                    tipos.append(t)
        return tipos

    def _preparar_contra_el_rival(self) -> str:
        tipos = self._tipos_del_rival_en_prep()
        if not tipos:
            return "sin datos del rival"
        equipo = self.j.equipo()
        nombres = [m.get("nombre") for m in equipo]
        con_tipos = [{**m, "tipos": self._tipos_de_m(m.get("nombre"))}
                     for m in equipo]
        elegido = P.mejor_contragolpe(con_tipos, tipos)
        destino = nombres.index(elegido) if elegido in nombres else 0
        orden = P.orden_para_entrenador(con_tipos, tipos)
        self.anotar(P.Decision("prep", elegido,
                               f"rival {'/'.join(tipos)} -> {orden}"))
        self.log(f"  ⋯ prep: rival {'/'.join(tipos)} -> {orden}")
        # Reordenar en el prep: los slots del HUD también salen en esta pantalla.
        self.ordenar_equipo(con_tipos, self.j.insignias(), "jefe", orden)
        objeto = self._usar_bolsa(destino, nombres)
        return f"rival {'/'.join(tipos)}, delante {elegido}, {objeto}"

    def _tipos_de_m(self, nombre: str) -> list[str]:
        from pkl_movimientos import tipos_de
        return tipos_de(nombre or "")

    def _usar_bolsa(self, destino: int, nombres: list[str] | None = None,
                    tipos_rival: list[str] | None = None) -> str:
        """Usa o equipa los objetos de la bolsa con criterio.

        Antes esta función **nunca** había equipado nada: el log decía "objeto NO
        equipado" las 43 veces que se intentó, y sin objetos el bot va a ciegas.
        Es la segunda palanca grande según la guía, y hay dos consumibles que
        son playthrough puro: el Sacred Ash (cura total y revive) y el Rare Candy
        (+3 niveles).

        La reparto decide `pkl_items.elegir_objetos`, que separa **usar**
        (consumibles, van al más gastado o al principal) de **llevar** (un
        objeto permanente por Pokémon, y el mejor para el mejor).
        """
        try:
            bolsa = self.j.bolsa_items()
        except Exception as exc:  # noqa: BLE001
            return f"bolsa ilegible: {exc}"
        equipo = self.equipo_con_tipos()
        if not equipo:
            return "equipo vacío"
        reparto = PI.elegir_objetos(bolsa, equipo, tipos_rival)
        plan = []
        for indice, nombre, motivo in reparto["usar"] + reparto["llevar"]:
            j = next((k for k, m in enumerate(equipo)
                      if m.get("nombre") == nombre), None)
            oid = str((bolsa[indice].get("id") or indice)).lower()
            if oid in self.objetos_fallidos:
                continue
            if j is not None:
                plan.append((indice, j, nombre, motivo))
        if not plan:
            return f"bolsa: {len(bolsa)} sin objetos conocidos"

        antes_total = len(bolsa)
        hechos: list[str] = []
        for indice, j, nombre, motivo in plan:
            antes = len(self.j.bolsa_items())
            self.j.usar_item(indice, j, nombre)
            despues = len(self.j.bolsa_items())
            # **Verificación de verdad**: el objeto aparece debajo del món, en
            # su `div.team-slot.team-slot-reorder`. Antes solo se miraba si la
            # bolsa bajaba, y eso no distingue un equip de un objeto gastado.
            puesto = self.j.objeto_del_mons(nombre)
            if puesto:
                hechos.append(f"{nombre} <- {puesto}")
                self.log(f"  ⋯ objeto EQUIPADO -> {nombre}: {puesto} ({motivo})")
            elif despues < antes:
                hechos.append(f"{nombre}: {motivo} (usado)")
                self.log(f"  ⋯ objeto USADO -> {nombre}: {motivo} "
                         f"(bolsa {antes}->{despues})")
            else:
                # Falla: se vuelca el DOM de la pantalla para poder ajustar los
                # selectores con datos, en vez de adivinar. Es lo que ha
                # permitido cerrar la majority de los huecos de esta sesion.
                self.log(f"  ✗ objeto NO usado -> {nombre}: {motivo} "
                         f"(bolsa {antes}->{despues})")
                self._volcar_bolsa()
        if not hechos:
            return f"bolsa: {len(bolsa)} objetos, ninguno se pudo usar"
        return "; ".join(hechos)

    def _volcar_item(self) -> None:
        """Vuelca la pantalla de objetos para ver cómo se **confirma**."""
        try:
            datos = self.j.page.evaluate(
                r"""() => {
                    const vis = e => e && e.offsetParent !== null;
                    const s = document.getElementById('item-screen');
                    if (!s) return null;
                    return {
                      texto: (s.innerText || '').replace(/\s+/g,' ').slice(0,160),
                      opciones: [...s.querySelectorAll(
                          '[data-shortcut], .poke-card, button, .item-card')]
                          .filter(vis).map(e => ({
                            id: e.id || null,
                            clase: (e.className||'').toString().slice(0,34),
                            atajo: e.dataset.shortcut || null,
                            txt: (e.innerText||'').trim().slice(0,26)})),
                    };
                }"""
            )
            if datos:
                self.log(f"    item DOM: {json.dumps(datos, ensure_ascii=False)[:400]}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"    no se pudo volcar item: {exc}")

    def _volcar_bolsa(self) -> None:
        """Vuelca la pantalla de objetos a disco para poder leer los selectores."""
        try:
            datos = self.j.page.evaluate(
                r"""() => {
                    const vis = e => e && e.offsetParent !== null;
                    const out = {pantalla: null, bolsa: [], equipo: [], botones: []};
                    const s = [...document.querySelectorAll('[id$=-screen]')].find(vis);
                    if (s) out.pantalla = s.id;
                    for (const el of document.querySelectorAll(
                            '[class*=item], #item-bar *')) {
                        if (!vis(el) || !el.dataset) continue;
                        out.bolsa.push({
                            id: el.id || null,
                            clase: (el.className || '').toString().slice(0, 40),
                            atajo: el.dataset.shortcut || null,
                            txt: (el.innerText || '').trim().slice(0, 24),
                        });
                    }
                    for (const el of document.querySelectorAll('#team-bar .team-slot')) {
                        if (!vis(el)) continue;
                        out.equipo.push({
                            id: el.id || null,
                            clase: (el.className || '').toString().slice(0, 40),
                            atajo: el.dataset.shortcut || null,
                            nombre: (el.querySelector('.team-slot-name')?.innerText
                                     || el.querySelector('img')?.getAttribute('alt')
                                     || '').trim(),
                        });
                    }
                    for (const b of document.querySelectorAll('button')) {
                        if (vis(b)) out.botones.push({
                            id: b.id || null,
                            atajo: b.dataset.shortcut || null,
                            txt: (b.innerText || '').trim().slice(0, 24)});
                    }
                    return out;
                }"""
            )
            destino = Path("/tmp/opencode/bolsa.json")
            destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                               encoding="utf-8")
            self.log(f"    volcado de bolsa -> {destino} "
                     f"(pantalla={datos.get('pantalla')}, "
                     f"{len(datos.get('bolsa') or [])} items, "
                     f"{len(datos.get('botones') or [])} botones)")
        except Exception as exc:  # noqa: BLE001
            self.log(f"    no se pudo volcar la bolsa: {exc}")

    # ------------------------------------------------------------ bucle
        # Centinela para "aun no hay nada que pulsar" (el juego anima). No cuenta
    # como paso ni dispara el detector de atasco, pero consume presupuesto.
    ESPERA = "\x00espera\x00"

    MANEJADORES = {
        "title-screen": "_title",
        "history-region-select": "_region",
        "trainer-screen": "_trainer",
        "starter-screen": "_starter",
        "map-screen": "_mapa",
        "battle-screen": "_batalla",
        "catch-screen": "_catch",
        "item-screen": "_item",
        "passive-screen": "_pasivo",
        "swap-screen": "_swap",
        "trade-screen": "_trade",
        "shiny-screen": "_shiny",
        "badge-screen": "_badge",
        "transition-screen": "_transicion",
        "elite-prep-screen": "_elite_prep",
        "stat-buff-screen": "_stat_buff",
    }

    def paso(self) -> str | None:
        """Un paso. Devuelve una descripción, o None si la run terminó."""
        self.pasos += 1
        pantalla = self.j.pantalla()
        if pantalla is None:
            self.j.page.wait_for_timeout(400)
            return "esperando"
        if pantalla == "gameover-screen":
            # Aquí hay que contar la derrota **antes** de cortar. Antes se
            # detectaba aquí y se saltaba `_cerrar_combate`, así que ninguna
            # derrota se contaba nunca: todas las runs decían "0 perdidas" y
            # morían igual. Se estaba depurando a ciegas.
            if self._en_combate:
                self._en_combate = False
                self.derrotas += 1
                rival = getattr(self, "_ultimo_rival", "?")
                propios = ", ".join(
                    f"{m.get('nombre')}({m.get('ps')}/{m.get('ps_max')})"
                    for m in self.j.equipo() if (m.get("ps") or 0) > 0) or "ninguno"
                self.log(f"  >>> COMBATE PERDIDO contra {rival} | "
                         f"nos quedan: {propios} | {self.victorias}-{self.derrotas}")
            else:
                self.log("  >>> partida perdida (sin combate en curso)")
            self.resultado = "GAME_OVER"
            return None
        if pantalla == "win-screen":
            self.resultado = "CHAMPION"
            return None
        if pantalla in ("endless-stage-select", "endless-stage-complete"):
            self.resultado = "FUERA_DE_ALCANCE"
            return None

        nombre = self.MANEJADORES.get(pantalla)
        if nombre is None:
            self.log(f"  ?? pantalla sin manejar: {pantalla}")
            self.j.page.wait_for_timeout(600)
            return f"desconocida:{pantalla}"
        if pantalla == "battle-screen":
            if not self._en_combate:
                self._en_combate = True
                self.combates += 1
        hecho = getattr(self, nombre)()
        self._cerrar_combate(pantalla)
        return hecho

    _SALIDA_DE_COMBATE = ("map-screen", "badge-screen", "pokemon-center-screen",
                          "pokecenter-screen", "gameover-screen", "win-screen",
                          "item-screen")

    def _cerrar_combate(self, pantalla: str) -> None:
        """Anota en el log si el combate se ha ganado o se ha perdido.

        El juego no avisa del resultado: se deduce de a dónde lleva la
        pantalla. Salir de `battle-screen` hacia el mapa, la insignia o el
        centro es victoria; caer en `gameover-screen` es derrota. Es la única
        señal fiable sin leer el DOM de la animación, que va cuadro a cuadro.
        """
        if not self._en_combate:
            return
        if pantalla not in self._SALIDA_DE_COMBATE:
            return
        self._en_combate = False
        if pantalla == "gameover-screen":
            self.derrotas += 1
            self.log(f"  >>> COMBATE PERDIDO (caemos en gameover) | "
                     f"{self.victorias}-{self.derrotas}")
        else:
            self.victorias += 1
            self.log(f"  >>> COMBATE GANADO (continuamos en {pantalla}) | "
                     f"{self.victorias}-{self.derrotas}")

    def tabla_resumen(self) -> str:
        """Tabla resumen de la run, para el final del log.

        Se lee de un vistazo: cómo acabó, y en qué se fue el presupuesto (combates
        ganados y perdidos, capturas, tutores, objetos y curaciones).
        """
        e = self._equipo_final
        nivel = (f"{min(m['nivel'] for m in e)}-{max(m['nivel'] for m in e)}"
                 if e else "-")
        filas = [
            ("resultado", self.resultado),
            ("pasos", str(self.pasos)),
            ("insignias", str(self._insignias_final)),
            ("combates", f"{self.victorias} ganados / {self.derrotas} perdidos"),
            ("capturas", str(self.capturas)),
            ("tutores", str(self.tutores)),
            ("objetos", str(self.objetos)),
            ("centros", str(self.centros)),
            ("equipo", f"{len(e)} ({nivel})"),
        ]
        ancho = max(len(k) for k, _ in filas)
        lineas = ["", "-" * (ancho + 26), f"  RESUMEN {self.region}"]
        lineas += [f"  {k.ljust(ancho)} : {v}" for k, v in filas]
        lineas += ["-" * (ancho + 26), ""]
        return "\n".join(lineas)

    def _activar_ajustes(self) -> None:
        """Auto-skip al entrar, antes de tocar nada (ver `navegador`)."""
        try:
            self.j.activar_auto_skip()
            self.log("  ajustes: auto-skip activado (combates y evoluciones)")
        except Exception as exc:  # noqa: BLE001
            self.log(f"  !! no se pudieron activar los ajustes: {exc}")

    def jugar(self, max_pasos: int, pausa: float = 0.5) -> None:
        # `max_pasos <= 0` significa **sin presupuesto**: la partida se juega
        # hasta que acabe de verdad (victoria, derrota o atasco real). Antes
        # ponia un limite de pasos y salia `PRESUPUESTO_AGOTADO`, que no es
        # ganar ni perder: es la partida cortada por mi, y su unico efecto era
        # tirar runs que iban bien. El limite de verdad ya existe y es el
        # detectors de atasco (pantalla repetida muchas veces -> ATASCADO).
        self._activar_ajustes()
        if max_pasos and max_pasos > 0:
            self.log(f"== run {self.region} | presupuesto {max_pasos} pasos ==")
        else:
            self.log(f"== run {self.region} | sin presupuesto de pasos "
                     f"(corta solo si acaba o si se atasca) ==")
        # Guardia anti-bucle: si la misma pantalla se repite muchas veces sin que
        # cambie nada, el clic no está surtiendo efecto y seguir es tirar CPU.
        vistos: dict[str, int] = {}
        tope_repetidas = 12
        anterior = None
        # Sin presupuesto, la condicion de salida es `resultado != EN_CURSO`,
        # que cambia al ganar, perder o detectar el atasco.
        while ((self.pasos < max_pasos or max_pasos <= 0)
               and self.resultado == "EN_CURSO"):
            try:
                hecho = self.paso()
            except Exception as exc:  # noqa: BLE001
                # Un error repetido en la misma pantalla no se reintenta
                # indefinidamente: se para la run. Antes un `NameError` en el
                # manejador de trades lanzaba el mismo error cientos de veces y
                # la partida se arrastraba sin avanzar (4 nodos en 700 s).
                # **Los errores de código cortan la run en el acto**, a
                # diferencia de los transitorios (tiempos de espera agotados),
                # que se reintentan. Un `NameError` o un `AttributeError` no se
                # arregla reintentando:-cutting evita gastar media tanda en una
                # partida que no va a ningún sitio. Medido: un typo en el
                # manejador de trades dejó una partida en 4 nodos de 700 s.
                if type(exc) in self.ERRORES_DE_CODIGO:
                    self.log(f"  !! error de CÓDIGO ({type(exc).__name__}): {exc}")
                    self.log("  !! la run se corta: hay que corregirlo")
                    self.resultado = "ERROR_DE_CODIGO"
                    return
                clave_err = f"{self.j.pantalla()}|{type(exc).__name__}:{exc}"
                self._errores[clave_err] = self._errores.get(clave_err, 0) + 1
                if self._errores[clave_err] >= 5:
                    self.log(f"  !! 5 errores iguales en {clave_err}: "
                             f"la run no puede seguir")
                    self.resultado = "ATASCADO"
                    return
                self.log(f"  !! error en paso: {type(exc).__name__}: {exc}")
                tb = traceback.format_exc().strip().splitlines()
                for linea in tb[-6:]:
                    self.log(f"     | {linea}")
                self.j.page.wait_for_timeout(800)
                continue
            if hecho is None:
                break
            if hecho == self.ESPERA:
                # Animacion en curso: ni cuenta como repetido ni cierra la run.
                self.j.page.wait_for_timeout(500)
                continue
            donde = self.j.pantalla()
            # Solo cuentan las repeticiones *consecutivas*: alternar entre
            # pantallas (p. ej. mapa -> item -> mapa) es juego normal, no un bucle.
            if donde != anterior:
                vistos.clear()
                anterior = donde
            clave = f"{donde}|{hecho[:40]}"
            vistos[clave] = vistos.get(clave, 0) + 1
            if vistos[clave] > tope_repetidas:
                # En batalla, muchas pulsaciones de SKIP son normales: antes de
                # declarar atasco se comprueba que el estado de verdad no cambia.
                if donde == "battle-screen":
                    f1 = self.firma_batalla()
                    self.j.activar("#btn-auto-battle")
                    self.j.page.wait_for_timeout(1800)
                    f2 = self.firma_batalla()
                    if f1 and f1 != f2:
                        self.log(f"  batalla sigue viva (cambio de PS), continúo")
                        vistos[clave] = 0
                        continue
                self.log(f"  !! atascado en {clave} x{vistos[clave]}: intento desbloquear")
                self.volcar_atasco(donde)
                for _ in range(2):
                    self._desbloquear()
                    if self.j.pantalla() != donde:
                        break
                if self.j.pantalla() == donde:
                    self.resultado = "ATASCADO"
                    break
                vistos.clear()
                self.log(f"  desbloqueado -> {self.j.pantalla()}")
                continue
            if pausa:
                self.j.page.wait_for_timeout(int(pausa * 1000))
        # `PRESUPUESTO_AGOTADO` ya no se usa: solo queda si alguien pasa un
        # presupuesto explicito, y en ese caso avisa en vez de fingir un final.
        if self.resultado == "EN_CURSO" and max_pasos > 0 \
                and self.pasos >= max_pasos:
            self.log(f"  !! partida cortada por el presupuesto de "
                     f"{max_pasos} pasos (no es una derrota)")
        # Se cachea el estado final: la tabla se pinta aunque la página ya haya
        # caído, y `resumen()` sigue siendo la fuente de verdad para el JSON.
        try:
            self._equipo_final = self.j.equipo()
            self._insignias_final = self.j.insignias()
        except Exception:  # noqa: BLE001
            self._equipo_final = getattr(self, "_equipo_final", [])
            self._insignias_final = getattr(self, "_insignias_final", 0)
        self.log(self.tabla_resumen())

    # ------------------------------------------------------------ salida
    def resumen(self) -> dict:
        equipo = self.j.equipo()
        insignias = self.j.insignias()
        return {
            "resultado": self.resultado,
            "region": self.region,
            "pasos": self.pasos,
            "insignias": insignias,
            "equipo": [{"n": m["nombre"], "lv": m["nivel"], "ps": m["ps"]} for m in equipo],
            "tipos_equipo": self.tipos_equipo(equipo),
            "decisiones": self.decisiones[-25:],
        }


def _barra(i: int, total: int, ancho: int = 24) -> str:
    llenos = int(ancho * i / max(total, 1))
    return "#" * llenos + "-" * (ancho - llenos)


def seguir_en_vivo(bot, max_pasos: int, pausa: float, cada: int) -> None:
    """Juega la partida enseñando el log en directo, pantalla a pantalla.

    No es un `tail -f`: el bot va escribiendo en `juegos/pokelike/log/log-<pid>.txt` y aquí se
    imprime lo último y se limpia la pantalla cada `cada` segundos. Es lo
    cómodo para mirar una run larga sin que el terminal se llene de líneas.
    """
    import subprocess

    visto = 0
    while (bot.resultado == "EN_CURSO"
           and (bot.pasos < max_pasos or max_pasos <= 0)):
        bot.paso()
        if bot.pasos % max(1, cada) != 0 and bot.resultado == "EN_CURSO":
            time.sleep(pausa)
            continue
        try:
            lineas = LOG_BOT.read_text(encoding="utf-8").splitlines()
        except OSError:
            lineas = []
        nuevas = lineas[visto:]
        visto = len(lineas)
        subprocess.run(["clear"], check=False)
        print(f"== {bot.region} | paso {bot.pasos}/{max_pasos} "
              f"| {_barra(bot.pasos, max_pasos)} ==", flush=True)
        print("\n".join(nuevas[-35:]), flush=True)
        if bot.resultado != "EN_CURSO":
            break
        time.sleep(pausa)


def _reiniciar_log() -> None:
    """Deja el log limpio para esta ejecución.

    Se trunca en vez de añadir: el log crece con cada run (una ejecución puede
    tener varias) y Guardarlo indefinido solo acumula peso de pruebas
    antiguas. Ahora mismo eran 11 MB y 120.000 líneas.
    """
    try:
        LOG_BOT.parent.mkdir(parents=True, exist_ok=True)
        LOG_BOT.write_text("", encoding="utf-8")
    except OSError:
        pass


def principal() -> int:
    ap = argparse.ArgumentParser(description="Bot autónomo de Pokelike (juega en Python).")
    ap.add_argument("--region", default="Kanto", choices=sorted(REGIONES_DOM))
    ap.add_argument("--navegador", default=nb.NAVEGADOR,
                    choices=("firefox", "chromium", "webkit", "remoto"),
                    help="motor: `remoto` controla TU Firefox por WebDriver "
                         "BiDi, con tu perfil y tu cuenta (por defecto: "
                         "%(default)s)")
    ap.add_argument("--perfil", default=None,
                    help="perfil de Firefox a usar, para jugar con tu cuenta y "
                         "no con un perfil desechable. Con `--reset` se ignora, "
                         "porque una run nueva necesita un perfil limpio.")
    ap.add_argument("--visible", "--headful", dest="visible",
                    action="store_true",
                    help="abre la ventana de verdad para ver los movimientos "
                         "(modo normal en el bot: sin ventana, en headless)")
    ap.add_argument("--max-pasos", type=int, default=0,
                    help="0 = sin presupuesto: la partida acaba sola "
                         "(ganar, perder o atascarse). Un numero positivo es "
                         "un tope de pasos que corta la partida sin que esta "
                         "haya terminado.")
    ap.add_argument("--pausa", type=float, default=0.5, help="segundos entre pasos")
    ap.add_argument("--silencioso", action="store_true", help="no imprime el progreso")
    ap.add_argument("--reset", action="store_true",
                    help="juega en un perfil temporal: run nueva desde cero")
    ap.add_argument("--max-equipo", type=int, default=None,
                    help="cuántos móns caben (1 = sin capturas, solo el starter)")
    ap.add_argument("--seguir", type=int, default=0, metavar="SEG",
                    help="enseña el log en directo refrescando la pantalla cada "
                         "SEG segundos (0 = salida normal, la de siempre)")
    args = ap.parse_args()
    _reiniciar_log()

    if args.max_equipo is not None:
        if args.max_equipo < 1:
            ap.error("--max-equipo tiene que ser >= 1")
        P.MAX_EQUIPO = args.max_equipo
        P.MIN_NUCLEO = min(P.MIN_NUCLEO, args.max_equipo)

    # `--perfil` manda sobre el perfil del bot: es lo que permite jugar con la
    # cuenta guardada en el perfil real de Firefox. `--reset` lo anula, porque
    # una run desde cero necesita un perfil limpio y no se toca el del usuario.
    if args.reset:
        perfil = None
    elif args.perfil:
        perfil = Path(args.perfil)
        if not perfil.is_dir():
            ap.error(f"no existe el perfil: {perfil}")
    else:
        perfil = nb.PERFIL
    juego, ctx, pw = nb.abrir(headless=not args.visible, perfil=perfil,
                              motor=args.navegador)
    modo = "visible" if args.visible else "headless"
    print(f"navegador: {args.navegador} ({modo})", file=sys.stderr)
    try:
        bot = Bot(juego, args.region, verbose=not args.silencioso,
                  reset=args.reset)
        bot.pokedex = juego.pokedex()
        bot.log(f"pokedex cargado: {len(bot.pokedex)} especies")
        if args.seguir:
            seguir_en_vivo(bot, args.max_pasos, args.pausa, args.seguir)
        else:
            bot.jugar(args.max_pasos, args.pausa)
        print(json.dumps(bot.resumen(), ensure_ascii=False, indent=2))
        return 0 if bot.resultado == "CHAMPION" else 1
    finally:
        nav = getattr(ctx, "_navegador_propio", None)
        try:
            ctx.close()
        finally:
            if nav is not None:
                nav.close()
            # En modo remoto no hay Playwright detrás (`pw` es None), y además
            # cerrar la sesión BiDi es obligatorio: Firefox solo admite una por
            # instancia y si se cuelga la siguiente conexión falla.
            if pw is not None:
                pw.stop()


if __name__ == "__main__":
    raise SystemExit(principal())

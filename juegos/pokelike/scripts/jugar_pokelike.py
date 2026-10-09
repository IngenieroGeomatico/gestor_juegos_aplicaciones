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
# "12/30" -> el PS absoluto que solo aparece en la pantalla de combate.
_RE_PS = re.compile(r"\s*(\d+)\s*/\s*(\d+)\s*$")

REGIONES_DOM = {
    "Kanto": "KANTO", "Johto": "JOHTO", "Hoenn": "HOENN",
    "Sinnoh": "SINNOH", "Unova": "UNOVA",
}


def _trade_activo() -> bool:
    """Brazo de control del experimento del trade.

    `PKL_TRADE=0` deja el camino viejo (buscar un boton de continuar que no
    existe y declinar), que es lo que ha hecho el bot **siempre**: 0 trades
    en 319 runs. Se conserva solo para poder medir cuanto vale el arreglo;
    cuando se tenga veredicto, este flag y el camino viejo se borran juntos.
    """
    return os.environ.get("PKL_TRADE", "1").strip().lower() in (
        "1", "true", "si", "yes")


class Bot:
    # Intentos de recuperar un atasco **antes** de aceptar que la partida está
    # muerta. La run no se corta por un atasco: se escala el desbloqueo (teclas,
    # recargar, reiniciar). 3 es un tope prudente: con más, un fallo de selector
    # del sitio se traduce en minutos de recarga sin resultado.
    # Va **al principio de la clase**, y no junto al bucle, porque `jugar()` está
    # definido antes que esa sección del archivo: en runtime funcionaría igual
    # (los métodos se ejecutan con la clase ya montada), pero ruff marca la
    # referencia como nombre no definido y ese aviso esconde bugs reales.
    MAX_INTENTOS_ATASCO = 3

    def __init__(self, juego: nb.Juego, region: str, verbose: bool = True,
                 reset: bool = False) -> None:
        self.j = juego
        self.reset = reset
        self.tipo_lider: str | None = None
        # Nombre del starter elegido. Vacío hasta que se elija. El trade nunca
        # debe llevárselo: la guía lo dice ("tu peor món **no-starter**") y en
        # Kanto el starter se elige por ser 2x contra los tres primeros
        # gimnasios, así que cambiarlo es perder la apertura de la run.
        self.nombre_starter: str = ""
        # Rerolls de mapa usados en la run (la guía los recomienda para buscar
        # un trade o un mejor camino de exp).
        self._rerolls = 0
        self._rerolls_busqueda = 0
        # Nodo en el que se gastaron los rerolls de búsqueda de trade: al
        # cambiar de nodo se vuelve a poder buscar (antes se gastaban en la
        # primera pantalla de la partida y no volvían a activarse nunca).
        self._rerolls_nodo: str | None = None
        # Intentos de recuperación del último atasco. La run no se corta por un
        # atasco: se reintenta con teclas, luego recargando la página.
        self._atasco_intentos = 0
        # Tipos de los entrenadores del mapa actual (para la captura).
        self._tipos_ruta: list[str] = []
        # Sprite -> tipos de cada entrenador del mapa (para el veto de evitar).
        self._tipos_por_sprite: dict[str, list[str]] = {}
        # Intentos fallidos de salir del prep del jefe (ver _elite_prep): sin
        # memoria, el manejador se rendia y Volvia a entrar en bucle infinito.
        self._prep_fallos = 0
        # Intentos de "la batalla sigue viva" antes de rendirse.
        self._batalla_viva = 0
        # ¿Ya hemos hecho algún trade en esta run?
        self._trade_hecho = False
        # PS real por món, aprendido en la pantalla de combate ("0/19").
        self._ps_real: dict[str, tuple[int, int]] = {}
        # Quién se ha visto CAÍDO. Sobrevive a la invalidación del
        # porcentaje: un món a 0 sigue a 0 hasta que lo curan.
        self._caidos_conocidos: set[str] = set()
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
        # Contadores de combate **sin muestreo**. El volcado de texto sale
        # de 4 en 4, así que contar por el log subestima 4x.
        self.peleas = 0
        self.peleas_entrenador = 0
        self.peleas_salvaje = 0
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
        # Contador de fallos por objeto: un clic fallido no veta el objeto
        # para siempre, hace falta que falle dos veces seguidas.
        self._objeto_fallos: dict[str, int] = {}
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
        # Diario de decisiones. El log de texto dice **qué** se decidió pero no
        # **sobre quién**: que objeto se cogió y a qué món se equipó, a quién
        # se le dio la MT, a quién se sacó en el cambio. Sin eso no se puede
        # auditar una partida ni responder "¿por qué se perdió esto?": se
        # tomaban las decisiones y había que reconstruir el motivo leyendo el
        # código. Va como lista de dicts y se vuelca a JSON al final.
        self._traza: list[dict] = []
        # Visitas al nodo del tutor, para el resumen. **Inicializado aquí y no
        # en la rama que lo usa**: se creaba dentro del `elif d.tipo ==
        # "tutor"` y por eso la PRIMERA visita a un tutor reventaba con
        # `AttributeError`, matando 26 de 100 runs del lote de H13. Se puede
        # comprobar con `test_los_atributos_nuevos_nacen_en_init`.
        self._tutor_visitado: list[dict] = []

    def traza(self, evento: str, **campos: object) -> None:
        """Registra una decisión con su objetivo y su motivo.

        El nombre (`evento`) es corto y estable para poder grepear, y los
        campos son clave=valor. Sale en el log con prefijo `DEC` y además se
        acumula para el volcado JSON, que es lo que permite medir sin releer
        texto.

        El primer parámetro se llama `evento` y no `tipo` **a propósito**: casi
        todos los registros llevan un campo `tipo=` (el tipo del nodo), y con
        un parámetro llamado `tipo` la llamada `traza("nodo", tipo=...)` daba
        `TypeError: got multiple values for argument 'tipo'` en el primer nodo
        del mapa. El error lo localizó el corte de `ERROR_DE_CODIGO`.
        """
        reg = {"paso": self.pasos, "evento": evento}
        reg.update(campos)
        self._traza.append(reg)
        try:
            self.log("  DEC " + evento + " " + " ".join(
                f"{k}={v}" for k, v in campos.items() if v not in (None, "")))
        except Exception:  # noqa: BLE001, S110
            # La traza nunca puede tumbar la partida: es diagnóstico, no lógica.
            pass

    def volcar_traza(self) -> str:
        """Escribe el diario de decisiones a JSON y devuelve la ruta."""
        try:
            destino = DIR_BOT / f"traza-{_MOMENTO}_p{os.getpid()}.json"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(
                {"region": self.region, "pasos": self.pasos,
                 "insignias": self._insignias_final,
                 "resultado": self.resultado,
                 "decisiones": self._traza},
                ensure_ascii=False, indent=1), encoding="utf-8")
            return str(destino)
        except OSError:
            return ""

    def log(self, linea: str) -> None:
        if self.verbose:
            print(linea, flush=True)
        try:
            LOG_BOT.parent.mkdir(parents=True, exist_ok=True)
            with LOG_BOT.open("a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {linea}\n")
        except OSError:
            pass

    def _traza_camino(self, m: dict, d, disponibles: list[str],
                       insignias: int) -> None:
        """UNA linea autocontenida por paso de mapa. Solo observa.

        Existe por una razon concreta: cuatro veces esta noche un hallazgo se ha
        caído porque el analisis emparejaba la linea de decision con la de estado
        suponiendo que eran contiguas. Aqui no hay nada que emparejar: cada linea
        lleva su propio contexto.

        Lo que se quiere ver, y es la pregunta abierta desde H17: **por que llega
        al gimnasio con el equipo gastado si el centro de curacion puntua mas que
        ninguna otra cosa.** Con esto se responde mirando, sin lote.

        Se registra SIEMPRE, no solo cuando hay caidos: el caso interesante es ver
        la vida justo despues de curar y cuanto se gasta despues.
        """
        equipo = self.j.equipo()
        vida = []
        niveles = []
        caidos = 0
        for m2 in equipo:
            ps = float(m2.get("ps") or 0)
            psmax = float(m2.get("ps_max") or 0) or 1.0
            vida.append(f"{(m2.get('nombre') or '?')}:{ps / psmax * 100:.0f}%")
            niveles.append(int(m2.get("nivel") or 0))
            if ps <= 0:
                caidos += 1
        media = (sum(float((m2.get('ps') or 0) /
                           (float(m2.get('ps_max') or 0) or 1.0) * 100)
                    for m2 in equipo) / len(equipo)) if equipo else 0.0
        # El peso vive en `razon` con el formato "tipo score=W (motivo)". Se saca
        # de ahi porque `Decision` no lo guarda como campo, y parsear el `__str__`
        # entero era justo el tipo de emparejamiento fragil que esta traza viene a
        # evitar. Si no esta, se deja como "?": una traza a medias vale mas que
        # una traza con un numero inventado.
        peso = "?"
        try:
            _c = d.razon.split("score=")[-1].split(" ")[0].strip("(")
            float(_c)
            peso = _c
        except Exception:  # noqa: BLE001, S110
            pass
        self.log(
            f"  TRAZA_CAMINO paso={self.pasos} mapa={m.get('info', '?')!r} "
            f"ins={insignias} disp={sorted(set(disponibles))} "
            f"vivos={len(equipo) - caidos}/{len(equipo)} caidos={caidos} "
            f"vida_media={media:.0f}% vida={vida} niveles={niveles} "
            f"elige={d.valor} peso={peso}")

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
        for m in eq:
            clave = (m.get("nombre") or "").strip().lower()
            real = self._ps_real.get(clave)
            if real:
                m["ps"], m["ps_max"] = real
            # Un món que se vio caído sigue a 0 aunque no sepamos el
            # porcentaje. **Va después** del `real` a propósito: si la caché
            # se acaba de llenar con un valor viejo, el dato de caído es el
            # más reciente y fiable.
            if clave in self._caidos_conocidos:
                m["ps"] = 0
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
    #
    # La comparación tiene que ser con `isinstance` y no `type(exc) in (...)`:
    # `UnboundLocalError` y `KeyError` son subclases de `NameError`/`LookupError`
    # y con la comparación exacta se colaban. Eso costaba una run entera: el
    # `UnboundLocalError` de `elegir_captura` se reintentaba 5 veces y la partida
    # acababa en ATASCADO, cuando la respuesta correcta era cortar y arreglar.
    # Excepciones que **siempre** son un bug del bot, nunca un fallo del juego o
    # del navegador. Cortan la run y hay que corregir el código.
    # OJO: `IndentationError` estuvo aquí y sobra: es un error de compilación,
    # Python ni siquiera llega a importar el módulo, así que no puede saltar en
    # runtime. Una entrada que no puede dispararse da una falsa sensación de
    # cobertura. `UnboundLocalError` sí va, y va como tal, porque hereda de
    # `NameError` pero `type(exc) in (...)` no lo habría pillado.
    ERRORES_DE_CODIGO = (NameError, AttributeError, TypeError,
                         KeyError, IndexError, ValueError)

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
        # El nombre del starter se guarda aparte porque `valor` es el atajo que
        # hay que pulsar, no lo elegido. Lo necesita el trade: la guía manda
        # cambiar "tu peor món **no-starter**", y sin este nombre el bot no
        # puede saber a quién no tocar.
        self.nombre_starter = str(d.nombre or "")
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
                self.traza("captura_confirmada", equipo_antes=pend,
                           equipo_despues=len(equipo),
                           nuevos="|".join(
                               f"{m.get('nombre')}:{m.get('nivel')}"
                               # `pend` YA es un entero: es el `len()` del
                               # equipo del momento en que se pidió la captura.
                               # Con `len(pend)` reventaba en el primer
                               # `catch` real.
                               for m in equipo[pend:]) or "?")
            self._catch_pendiente = None
        insignias = self.j.insignias()
        # Reinicio del contador de capturas por pantalla. La clave es el **nodo** en el
        # que se está (`m["actual"]`), no `m["info"]`: `info` es
        # `#map-info` = "Route 1: vs Brock (Rock)" y **no cambia** al recorrer
        # los ~23 nodos de la ruta (los logs muestran `total 23/23` con la
        # misma info). Con la clave por ruta el contador se ponía a 1 con la
        # primera captura y ya no se cazaba **en toda la ruta**: 3 capturas en
        # 115 pasos con 2 insignias, y un equipo de 3-4 móns para la Elite Four.
        # "Uno por pantalla" quiere decir uno por visita a nodo, que es lo que
        # puntúa `PESO_CAPTURA` cuando `capturas_pantalla == 0`.
        if self.pantalla_actual != (m.get("actual") or m.get("info") or ""):
            self.pantalla_actual = m.get("actual") or m.get("info") or ""
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
        # **Especialidades de los entrenadores de este mapa.** Esta llamada
        # estaba definida y documentada, pero **nunca se ejecutaba**: el
        # atributo `self._tipos_ruta` se quedaba en `[]` para siempre, así que
        # `elegir_captura` recibía siempre lista vacía y la corrección que
        # describía el comentario era inerte. El bot seguía cazando sin mirar
        # contra qué se iba a pelear dos nodos después.
        self._tipos_ruta = self.tipos_de_entrenadores_del_mapa(m)
        # **Índice sprite -> tipos de cada entrenador del mapa.** Hace falta
        # por nodo, no en bloque: la regla del usuario es "si podemos evitar
        # al entrenador, lo evitamos; si es el líder, jugamos", y para saber si
        # se puede evitar hay que mirar **ese** entrenador concreto contra
        # **este** equipo. Con el conjunto de la ruta no se puede decidir, y
        # el veto queda sin datos.
        self._tipos_por_sprite = self.tipos_entrenadores_por_sprite(m)
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
        # El contador se reinicia **al cambiar de nodo**, no al cambiar de ruta: el
        # gate era `len(self.nodos_vistos) < 12`, un conjunto que solo crece y
        # se llena en cada paso de mapa, así que los dos intentos se gastaban
        # en la **primera pantalla** de la partida (los logs lo confirman:
        # `intento 1/2` y `intento 2/2` a los 20 segundos de empezar) y el
        # mecanismo quedaba muerto para el resto de la run, aunque el
        # planificador puntúe el trade con 45. Se perdía el nodo más rentable
        # del juego en casi todas las regiones.
        nodo_actual_mapa = str(m.get("actual") or "")
        if self._rerolls_nodo != nodo_actual_mapa:
            self._rerolls_nodo = nodo_actual_mapa
            self._rerolls_busqueda = 0
        # **Un intento por nodo, no dos.** Con 2 el bot gastaba los dos antes
        # de puntuar nada, y como los rerolls ocurren en *cada* nodo donde no
        # hay trade, se perdían ~14 pasos de la partida (medido: los pares
        # "intento 1/2, intento 2/2" salen 5 veces seguidas en el log) sin
        # llegar nunca a elegir un nodo. El trade es muy raro por peso, así que
        # insistir dos veces en el mismo sitio no lo hace aparecer: solo gasta
        # pasos y exp.
        if (not self._trade_hecho and self._rerolls_busqueda < 1
                and "trade" not in tipos_alcanzables
                and len(self.nodos_vistos) < 12):
            self._rerolls_busqueda += 1
            self.log(f"  ↻ buscando trade (intento {self._rerolls_busqueda}/1): "
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
                          "tipos_por_sprite": self._tipos_por_sprite,
                          "capturas_pantalla": self.capturas_pantalla,
                          # El jefe es inevitable solo cuando no queda nada que
                          # dé experiencia. Es el caso que mataba las runs:
                          # entrar a ciegas por ser "la única salida".
                          "es_jefe_unica_salida": (
                              "jefe" in tipos_alcanzables
                              and not any(t in ("batalla", "entrenador")
                                          for t in tipos_alcanzables)),
                          # **Waypoint del pokecenter.** El planificador tiene la
                          # rama que da 50-58 al centro cuando esta en camino al
                          # jefe, pero `en_camino_al_jefe` **nunca se pasaba desde
                          # aqui**: el flag se quedaba en False y esa rama estaba
                          # tan muerta como las otras siete. Se calcula con el
                          # grafo real (BFS inverso desde el jefe) y no con una
                          # suposicion.
                          "en_camino_al_jefe": self.en_camino_al_jefe(m),
                      },
                      region=self.region, insignias=insignias,
                      ids_disponibles=alcanzables,
                      info_mapa=m.get("info", ""),
                      edges=m.get("edges") or [],
                      nodo_actual=m.get("actual"))
        self.anotar(d)
        self._traza_camino(m, d, tipos_alcanzables, insignias)
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
        # El tipo que emite el juego es `pokecenter`. Con `centro` el
        # contador se quedaba en 0 en todas las partidas, y como el resumen
        # "centros : N" era la unica prueba de que se pasaba por la curacion,
        # daba igual curar o no: parecia que nunca se curaba. Octavo caso de la
        # misma clase: comparar contra un nombre que no esta en el vocabulario
        # del juego.
        # OJO: el tipo de la decisión es **vocabulario interno**, y para el
        # pokecenter ese vocabulario es `"cura"` (`politica.tipo_de_estado`
        # mapea `"pokecenter" -> "cura"`). Antes se comparaba contra
        # `("centro", "pokecenter")`, que el juego nunca emite: la rama entera
        # era código muerto, `centros` salía a 0 en todas las partidas y
        # **`_invalidar_ps("pokecenter")` no se llamaba nunca**. Con la caché de
        # PS sucia, el bot creía que seguían teniendo caídos después de curar.
        if d.tipo == "cura":
            self.centros += 1
            # pokecenter cura al equipo entero: el PS real cacheado de la
            # última batalla pasa a ser mentira (dice 0 de un món que ya está
            # vivo). Sin esto, `equipo_con_tipos()` seguía contando caídos y el
            # bot se comporte como si tuviera menos móns de los que tiene.
            self._invalidar_ps("pokecenter")
        elif d.tipo == "tutor":
            self.tutores += 1
            # **El nodo del tutor no tiene pantalla propia en `MANEJADORES`.**
            # Se visitaba, se contaba como `tutores` y no había forma de saber
            # **a qué món se le enseñó el disco**, que es la única palanca de
            # daño real del juego (las batallas son automáticas). Aquí queda la
            # visita registrada con el `usedTM` de antes y después; si el disco
            # no se aplica en este nodo, se verá como `usado_antes=usado_despues`
            # y habrá que buscar dónde se consume.
            self._tutor_visitado.append({
                "nodo": m.get("actual"), "equipo": len(equipo),
                "principales": [m.get("nombre") for m in
                                (orden or [])[:3]] or
                               [x.get("nombre") for x in equipo[:3]],
            })
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
        # **El tipo CRUDO al lado del traducido.** Los dos se imprimían igual y
        # por eso no se podía distinguir un nodo de captura de una pelea normal:
        # `BATALLA = {"pokeball"}` traduce el sprite de la pokéball a `batalla`,
        # igual que el tipo `battle` del juego. Medido: un nodo con motivo
        # `capturar: equipo de 1` terminó en `COMBATE GANADO` sin captura
        # (falta la pokéball) y dos nodos idénticos sí la ofrecieron. Sin esto
        # la métrica de capturas no distingue "el filtro la rechazó" de
        # "el mapa no la ofreció", y por eso la muerte con 1 solo món no se
        # podía atribuir a la política ni a la lotería del mapa.
        crudos_disponibles = [str(n.get("tipo") or n.get("type")
                                  or P.tipo_de_nodo(n.get("sprite")))
                              for n in clica]
        self.log(f"  · {m.get('info') or 'ruta?'} | equipo {len(equipo)} (vivos {vivos}) "
                 f"niv {min(niv) if niv else 0}-{max(niv) if niv else 0} "
                 f"| lider {self.tipo_lider} | insignias {insignias} "
                 f"| disponibles {tipos_disponibles} "
                 f"(crudo {crudos_disponibles}) "
                 f"| rivales {[n.get('nivel') for n in clica if n.get('nivel') is not None] or '?'} "
                 f"| total {len(m['nodos'])}/{len(self.nodos_vistos)}"
                 + self.diagnostico_estado())
        if d.valor:
            self.j.clic_por_atajo(str(d.valor))
        # **Nodo elegido, con su tipo CRUDO.** El tipo traducido funde `catch`
        # y `battle` en `batalla`, y sin el crudo no se puede saber si el bot
        # entró a un nodo que ofrecía pokéball o a uno que no: medido, 18 de 20
        # muertes con 0 insignia ocurrieron en pantallas sin nodo `catch`.
        self.traza(
            "nodo",
            mapa=m.get("info") or "?",
            nodo=m.get("actual") or "?",
            tipo=d.tipo,
            crudo=(next((str(x.get("tipo")) for x in clica
                         if str(x.get("atajo")) == str(d.valor)), "?")),
            atajo=d.valor,
            equipo=len(equipo),
            vivos=vivos,
            niv=f"{min(niv) if niv else 0}-{max(niv) if niv else 0}",
            insignias=insignias,
            disponibles=",".join(crudos_disponibles),
            capturas_pantalla=self.capturas_pantalla,
            razon=(d.razon or "").split("|")[0].strip(),
        )
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

    def _volcar_crash(self, exc: BaseException, lugar: str) -> None:
        """Deja el error de código en un fichero **que no se limpia**.

        `lanzar_tanda.py` conserva solo los 3 logs más recientes, así que un
        crash de hace tres runs puede desaparecer antes de arreglarlo. Este
        volcado va a `crash-<fecha>.txt` y se **sobrescribe** en cada crash:
        interesa el último, que es el que sigue roto.

        Lleva la traza entera, no solo la última línea, porque un
        `AttributeError` en un método puede venir de un `None` puesto tres
        niveles más arriba.
        """
        try:
            destino = DIR_BOT / f"crash-{_MOMENTO}.txt"
            lineas = [
                f"=== error de codigo: {type(exc).__name__} ===",
                f"mensaje : {exc}",
                f"lugar   : {lugar or '?'}",
                f"region  : {self.region}",
                f"paso    : {self.pasos}",
                f"insignias: {self._insignias_final}",
                f"log     : {LOG_BOT.name}",
                "",
                "traza completa:",
                "".join(traceback.format_exception(type(exc), exc,
                                                  exc.__traceback__)),
            ]
            destino.write_text("\n".join(lineas), encoding="utf-8")
            self.log(f"  !! volcado del crash -> {destino}")
        except Exception as exc2:  # noqa: BLE001
            # Si ni esto se puede escribir, no se debe tapar el error original.
            self.log(f"  (no se pudo volcar el crash: {exc2})")

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

    def _apuntar_ps_real(self, mios: list[dict]) -> None:
        """Guarda el PS absoluto que muestra la pantalla de combate ("12/30").

        Este es el único dato fiable de vida: la barra del HUD es un
        porcentaje que en un món caído sigue marcando 100.
        """
        for m in mios or []:
            t = str(m.get("ps") or "")
            mm = _RE_PS.match(t)
            if mm:
                clave = (m.get("nombre") or "").strip().lower()
                actual, maximo = int(mm.group(1)), int(mm.group(2))
                self._ps_real[clave] = (actual, maximo)
                # **Quién está caído, aparte del porcentaje.** Ver
                # `_caidos_conocidos`: un món a 0 sigue a 0 hasta que lo curan,
                # y eso hay que recordarlo aunque se vacíe la caché de
                # porcentajes.
                if actual <= 0:
                    self._caidos_conocidos.add(clave)
                else:
                    self._caidos_conocidos.discard(clave)

    def _invalidar_ps(self, motivo: str = "") -> None:
        """Olvida el PS real cacheado.

        La caché se llenaba **solo** en la pantalla de combate y nunca se
        vaciaba, con lo que cualquier cosa que cambiara la vida fuera de un
        combate dejaba al bot creyendo lo contrario:

        - un pokecenter cura al equipo entero y la caché seguía diciendo que
          el món que se cayó hace dos nodos seguía a 0,
        - una poción lo sube al máximo,
        - subir de nivel incrementa `ps_max`, y con el valor viejo el món
          parecía al 100% cuando en realidad había perdido proportionally.

        Y el efecto era **permanente** hasta que ese món volviera a salir en
        otro combate, porque no había ninguna reconciliación. Como
        `equipo_con_tipos()` alimenta el recuento de vivos, que decide si se
        caza, si se cura y a quién se sacrifica en un trade, el bot jugaba con
        datos de vida falsos.
        """
        if self._ps_real and motivo and getattr(self, "_ps_aviso", 0) < 3:
            self._ps_aviso = getattr(self, "_ps_aviso", 0) + 1
            self.log(f"  · PS real invalidado ({motivo})")
        self._ps_real = {}
        # **Los caídos NO se olvidan al invalidar el porcentaje.** El bug: la
        # caché de porcentajes se vacía en cada uso de objeto, insignia y
        # trade, y al vaciarse `equipo_con_tipos()` volvía al HUD, que marca
        # 100 a un món con 0 de vida. Con la caché vacía el bot creía tener el
        # equipo entero sano, la puerta de curación no se disparaba, y se
        # entraba a pelear con el equipo **entero muerto**. Medido:
        # `mios=[Sandshrew 0/32, Eevee 0/28, Bulbasaur 0/30]` y a la vez
        # `nos quedan: 87/100, 100/100, 100/100`; se perdió ese combate.
        # Un món a 0 sigue a 0 hasta que alguien lo cura, así que ese dato
        # sobrevive a la invalidación del porcentaje. Solo lo borra una cura
        # real (pokecenter) o un cambio de equipo (swap), que son los dos
        # casos en los que puede volver a estar vivo.
        if motivo in ("pokecenter", "swap"):
            self._caidos_conocidos.clear()

    def _batalla(self) -> str:
        d = P.decidir_batalla(self.j.visible("#btn-auto-battle"))
        self.anotar(d)
        # El estado se lee **una vez por paso** y se usan dos cosas de él. Antes
        # se leía dos veces, y el PS real solo se muestreaba de 4 en 4 pasos: al
        # salir del combate la caché tenía el dato de hasta 4 pasos antes, así
        # que un món que acabó al 15% podía quedar cacheado al 80%.
        try:
            eb = self.j.estado_batalla()
        except Exception as exc:  # noqa: BLE001
            self.log(f"  estado no legible: {exc}")
            eb = None
        if eb:
            # **PS real.** La barra del HUD (`equipo()`) da un porcentaje que
            # en un món caido se queda clavado en 100: por eso el bot veía
            # "Bulbasaur(100/100)" con 0/19 de vida y por eso nunca.curaba.
            # La pantalla de combate si trae el valor real ("0/19"), asi que
            # se guarda aqui y se aplica encima del porcentaje.
            self._apuntar_ps_real(eb["mios"])
            # **Contador de combates, sin muestreo.** El volcado de texto sale
            # solo de 4 en 4 (`% 4 == 0`, más abajo), así que contar peleas
            # leyendo el log subestima 4x y cualquier conclusión sobre "cuántas
            # peleas de entrenador" sale mal por un factor fijo. Aquí se cuenta
            # **todas**, en estructura, y el texto sigue muestreado.
            #
            # Por qué importa: el entrenador da +2 niveles a todo el equipo y el
            # salvaje +1, y la diferencia entre ganar y perder el 2.º gimnasio es
            # de 2,5 niveles (medido sobre 451 combates). Sin este contador no
            # se puede ni plantear la pregunta.
            titulo = str(eb.get("titulo") or "")
            # Una pelea ocupa VARIOS pasos (auto-battle, continuar, cerrar) y
            # `estado_batalla()` se relee en cada uno. Contando cada lectura
            # salía 19 combates donde hubo 18. Se cuenta **una vez por pelea**,
            # detectando el cambio de rival+nivel.
            es_entrenador = "wants to battle" in titulo or "Battle vs" in titulo
            primer_niv = 0
            for _m in eb["mios"]:
                try:
                    primer_niv = int(_m.get("nivel") or 0)
                except (TypeError, ValueError):
                    primer_niv = 0
                break
            firma = (titulo, primer_niv, len(eb["enemigos"]))
            if firma != getattr(self, "_pelea_abierta", None):
                self._pelea_abierta = firma
                self.peleas += 1
                if es_entrenador:
                    self.peleas_entrenador += 1
                else:
                    self.peleas_salvaje += 1

            # El nivel puede viajar como TEXTO: `max()` sobre una mezcla de
            # `"15"` y `15` lanza `'>' not supported between 'str' and 'int'`.
            # Pasaba antes, pero solo 1 de cada 4 veces (el volcado viejo solo
            # corría con `% 4 == 0`); al contar todas las peleas salía en el
            # primer combate. Por eso el volcado nuevo **no** debe reutilizar
            # esos valores: se normalizan aquí.
            def _niv(m: dict) -> int:
                """El nivel puede viajar como texto: `"15"` y `15` en la misma
                lista hacen que `max()` lance TypeError."""
                try:
                    return int(m.get("nivel") or 0)
                except (TypeError, ValueError):
                    return 0

            def _ps(m: dict) -> int:
                """El PS llega como **fracción** `"0/43"`, no como entero.

                `int("0/43")` lanza ValueError y con un `except` que devuelve 0
                el recuento de móns vivos salía **siempre a 0**, en silencio. Se
                queda con la parte de antes de la barra.
                """
                v = m.get("ps")
                if isinstance(v, str):
                    v = v.split("/")[0].strip()
                try:
                    return int(v or 0)
                except (TypeError, ValueError):
                    return 0

            if firma == getattr(self, "_pelea_volcada", None):
                ficha = None
            else:
                self._pelea_volcada = firma
                ficha = True
            if ficha:
                self.traza("combate",
                           rival=titulo[:44],
                           tipo="entrenador" if es_entrenador else "salvaje",
                           nuestro_niv=max((_niv(m) for m in eb["mios"]),
                                           default=0),
                           rival_niv=max((_niv(e) for e in eb["enemigos"]),
                                         default=0),
                           nuestros=len([m for m in eb["mios"]
                                         if _ps(m) > 0]),
                           suyo=len(eb["enemigos"]),
                           insignias=self.j.insignias())
            # Se recuerda el nivel más alto que se ha visto: sirve para decidir si
            # un entrenador es arriesgado (perder una pelea de entrenador termina
            # la run). Los de Route 1 medían 3-4 y eran ganados de sobra; en rutas
            # posteriores suben.
            for e in eb["enemigos"]:
                if e.get("nivel"):
                    # `_niv`, no `e["nivel"]`: el nivel puede llegar como texto y
                    # `max(int, str)` lanza `TypeError: '>' not supported between
                    # instances of 'str' and 'int'`. Aquí estaba en el volcado
                    # viejo y solo se veía 1 de cada 4 veces; al contar todas las
                    # peleas saltó en el primer combate. La causa de fondo es que
                    # se comparaba contra `self.nivel_enemigo_max` (int) sin
                    # normalizar el otro lado.
                    self.nivel_enemigo_max = max(self.nivel_enemigo_max, _niv(e))
            # Cuántos móns trae el rival: a igual nivel, un entrenador de dos
            # móns contra un equipo de uno es imposible de ganar. En Mt Moon un
            # Firebreather (Charmander+Ponyta, 0.5x los dos) tumba a un
            # Bulbasaur solo del mismo nivel, y perder un battle de
            # entrenador termina la run.
            self.enemigos_max_vistos = max(self.enemigos_max_vistos,
                                           len(eb["enemigos"]))
            # El volcado al log se sigue haciendo de 4 en 4 pasos, que es lo que
            # hace falta para no llenar el log.
            if getattr(self, "_n_batalla", 0) % 4 == 0:
                niv_enem = [_niv(e) for e in eb["enemigos"] if e.get("nivel")]
                self._ultimo_rival = eb["titulo"]
                self.log(f"  estado: {eb['titulo']} | niveles rivales "
                         f"{min(niv_enem) if niv_enem else '?'}-"
                         f"{max(niv_enem) if niv_enem else '?'}")
                self.log(f"  enemigos={[(e['nombre'], e['ps'], e['nivel']) for e in eb['enemigos']]}")
                self.log(f"  mios={[(m['nombre'], m['ps'], m['nivel']) for m in eb['mios'] if m['ps']]}")
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
            # El reordenado decide la pelea entera: el delantero se lleva casi
            # toda la experiencia y el que va detrás llega gastado. Sin este
            # registro no se puede reconstruir por qué un món iba primero.
            self.traza("orden", para=tipo_nodo, rival=",".join(tipos_rival or []),
                       antes=",".join(orden_actual),
                       despues=",".join(deseado))
        elif self._reordenes_fallidos < 3:
            self._reordenes_fallidos += 1
            self.log(f"  ⋯ no se pudo reordenar (quedó {self.j.orden_equipo()})")

    def tipo_lider_actual(self) -> str | None:
        """`#map-info` dice "Route 1: vs Brock (Rock)"; de ahí sale el tipo."""
        import re as _re
        m = _re.search(r"\(([A-Za-zÁÉÍÓÚáéíóúñ /]+)\)\s*$", self.j.texto("#map-info") or "")
        return m.group(1).strip() if m else None

    def en_camino_al_jefe(self, mapa: dict) -> bool:
        """¿Estamos en un nodo que lleva al jefe? (y por tanto a su centro).

        El grafo siempre mete un pokecenter antes del lider, asi que "estar en
        camino al jefe" y "tener la cura en el tramo obligatorio" son la misma
        cosa. Se responde con el BFS inverso de `camino_al_jefe` sobre los
        nodos reales del mapa.
        """
        nodos = mapa.get("nodos") or []
        edges = mapa.get("edges") or []
        jefe = None
        for n in nodos:
            if P.tipo_de_estado(n.get("tipo") or n.get("type")) == "jefe":
                jefe = n.get("id")
                break
        if jefe is None:
            return False
        camino = P.camino_al_jefe(nodos, edges, jefe)
        actual = mapa.get("actual")
        return str(actual) in camino if actual is not None else False

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
            # Renuncia que **no** es del filtro de captura sino del contador de
            # pantalla, y antes no dejaba rastro. Medido: en una partida con 4
            # nodos `catch` hubo 3 capturas y la cuarta se fue por aquí sin
            # dejar ni una línea, que es indistinguible de un bug.
            self.traza("captura_renunciada", causa="ya se cazó en esta pantalla",
                       capturas_pantalla=self.capturas_pantalla,
                       equipo=vivos)
            return "huyo: ya se cazó uno en esta pantalla (prioridad es nivel)"
        # Con **menos de 3 en pie** se caza siempre, sea cual sea el nivel.
        # El veto por nivel era demasiadoRotundo: medido, el bot se quedó con
        # un solo Bulbasaur y perdía contra un Grunt del Team Rocket con el
        # món a 100 PS. Un equipo de uno no gana nada; con dos ya se puede.
        # Sin veto por nivel: el libro de jugadas es "captura uno al principio
        # y luego a por nivel", no "solo captura si vas sobrado".
        self._catch_ignora_nivel = vivos < 3
        # (La comprobación de `capturas_pantalla >= 1` estaba **dos veces** en
        # este método, y la segunda era código muerto: la primera devuelve
        # siempre. Se deja una sola, con su registro en `traza`.)
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
        # **R2, tal y como la fijó el usuario: siempre se captura uno
        # al inicio de la pantalla; la comprobación (completar el equipo o
        # mejores ataques) es solo para cuando ya hay 6.** No se veta nada por
        # tener pocos móns. Aquí no se pasa `nivel_minimo` a propósito: había
        # un veto por nivel que descartaba al salvaje cuando el equipo iba por
        # debajo del listón del líder, y con un solo món en pie eso descartaba
        # **todos** los salvajes de la ruta. Medido: se elegía el nodo de
        # captura ("hacen falta cuerpos") y luego se rechazaba en silencio,
        # con 0 capturas y `GAME_OVER` con un único Pokémon.
        d = P.elegir_captura(equipo, cands, actual,
                             (proximos[1:2] or [None])[0],
                             P.MAX_EQUIPO, proximos, self.region,
                             ignorar_nivel=bool(getattr(self, "_catch_ignora_nivel", False)),
                             tipos_entrenadores=list(self._tipos_ruta))
        self._catch_ignora_nivel = False
        self.anotar(d)
        if d.valor:
            # Si el equipo está lleno, el juego abrirá `swap-screen` para elegir
            # a quién se sustituye. Se apunta el objetivo ahora (el peor
            # miembro) porque en la pantalla siguiente ya no sabemos cuál de los
            # candidatos salió.
            vivos_lista = [m for m in equipo if (m.get("ps") or 0) > 0]
            if len(vivos_lista) >= P.MAX_EQUIPO:
                flojo = min(vivos_lista, key=lambda m: (
                    (m.get("nivel") or 0),
                    -sum((m.get("baseStats") or {}).values()),
                    m.get("nombre") or ""))
                self._swap_objetivo = flojo.get("nombre")
                self.log(f"  ⋯ equipo lleno: sustituiré a {self._swap_objetivo}"
                         f" por {d.valor}")
            self._catch_pendiente = len(self.j.equipo())
            self.j.clic_por_atajo(str(d.valor))
            self.traza("captura_pedida", objetivo=d.valor,
                       equipo=len(equipo), vivos=len(vivos_lista),
                       candidatos="|".join(
                           f"{c.get('nombre')}:{c.get('nivel')}"
                           for c in cands) or "ninguno",
                       motivo=d.razon)
            return f"peleo por {d.razon}"
        # **Captura rechazada.** Es una decisión y se perdía: el log solo decía
        # "huyo" con el motivo en texto. Aquí queda el candidato concreto, el
        # rival que se tapaba y el motivo, que es lo que permite distinguir un
        # filtro demasiado estricto de un mapa que no daba pokéball.
        self.j.activar("#btn-skip-catch")
        # OJO: aquí `vivos` es el **entero** de arriba (solo la rama elegida lo
        # reescribe como lista), así que va sin `len()`. Con `len(vivos)` el
        # bot reventaba en cada captura rechazada.
        self.traza("captura_rechazada", equipo=len(equipo), vivos=vivos,
                   candidatos="|".join(
                       f"{c.get('nombre')}:{c.get('nivel')}" for c in cands) or "ninguno",
                   rival=",".join(x for x in (actual,) if x),
                   motivo=d.razon)
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
        # Insignia = el equipo sube de nivel, y al subir de nivel `ps_max` crece.
        # El PS absoluto cacheado queda desfasado para siempre (mismo PS, más
        # vida máxima), y el món parece más sano de lo que está.
        self._invalidar_ps("insignia")
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
        # Ya se cogió un objeto en este nodo y la pantalla sigue aquí: eso
        # significa que la salida no surtió efecto. Elegir otra carta no avanza
        # nada y gasta la partida en el mismo sitio, así que solo se intenta
        # salir. La bandera existía y documentaba este bug desde hacía tiempo,
        # pero **nunca se consultaba** en ningún sitio, así que el bug seguía
        # vivo.
        if self._ya_cogido_item:
            self.log("  item: ya se cogió uno aquí, solo intento salir")
            for nombre, via in (("tecla Space",
                                 lambda: self.j.page.keyboard.press("Space")),
                                ("clic JS en SKIP", lambda: self.j.page.evaluate(
                                    "() => { const b = document"
                                    ".getElementById('btn-skip-item');"
                                    " if (!b) return false; b.click();"
                                    " return true; }")),
                                ("clic forzado en SKIP",
                                 lambda: self.j.clic("#btn-skip-item", 2))):
                via()
                self.j.page.wait_for_timeout(500)
                if self.j.pantalla() != "item-screen":
                    self.log(f"  item: salida con '{nombre}'")
                    self._ya_cogido_item = False
                    return "item: solo salir"
            return self.ESPERA
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
        # Se marca que este nodo ya dio su objeto: si la pantalla no avanza, el
        # siguiente paso tiene que limitarse a salir.
        self._ya_cogido_item = True
        self.anotar(P.Decision("item", elegido.get("txt", "")[:40],
                               f"tomo {self.items_tomados}/{self.MAX_ITEMS} por {via}"))
        # Qué objeto y **por qué este**. El nodo de item no asigna el objeto a
        # ningún món (eso pasa en `elite-prep-screen`, más adelante), así que
        # sin este registro no se puede enlazar "cogí Expert Belt aquí" con
        # "se equipó a Bulbasaur". `idx` es la posición en la lista de
        # prioridad: 99 significa que ninguna palabra clave casó, o sea que el
        # bot cogió el objeto **sin criterio de prioridad**.
        self.traza("item_cogido", objeto=(elegido.get("txt", "")[:40]).replace("\n", " "),
                   atajo=elegido.get("atajo"),
                   prioridad=next((i for i, k in enumerate(orden)
                                   if k in (elegido.get("txt") or "").lower()), 99),
                   opciones="|".join((o.get("txt") or "").replace("\n", " ")[:28]
                                     for o in ops))
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
                self._ya_cogido_item = False
                return f"item {elegido.get('txt', '')[:40]}"
            self.log(f"  item: '{nombre}' no funcionó")
        return self.ESPERA

    def _pasivo(self) -> str:
        return self._opciones_genericas("#passive-choices", "#btn-skip-item", "pasivo")

    def _swap(self) -> str:
        """Sustituye al món indicado, no al primero que encuentre.

        Llega aquí en **dos** casos distintos, y esa distinción es la razón de
        que este método lleve objetivo propio:

        1. El equipo está lleno y sale un món mejor de una captura. Entonces
           `_catch` ya ha fijado `_swap_objetivo` con el peor miembro.
        2. Un món **sube de nivel** y el juego pide a quién sacar. Aquí no hay
           captura detrás: `_swap_objetivo` viene a `None` y el código caía
           en `_opciones_genericas`, que elige **la primera opción de la
           lista**. Eso es un món arbitrario, y es justo lo contrario de la
           regla: se sustituye al **peor**, o al que ya está muerto, que no
           aporta nada y sigue ocupando una plaza.

        En los dos casos la salida es la misma: fuera el món que menos vale.
        """
        objetivo = getattr(self, "_swap_objetivo", None)
        if not objetivo:
            # Qué món ofrece el juego. Va **antes** de elegir a quién sacar:
            # sin saberlo no se puede aplicar la regla del tipo repetido.
            try:
                entrante = self.j.mons_en_swap()
                if entrante and entrante.get("nombre"):
                    info = self._pokedex_por_nombre().get(
                        str(entrante["nombre"]).strip()) or {}
                    entrante = {
                        "nombre": entrante["nombre"],
                        "nivel": entrante.get("nivel") or 0,
                        "tipos": (info or {}).get("types")
                                 or entrante.get("tipos") or [],
                        "baseStats": (info or {}).get("baseStats") or {},
                    }
                    self.log(f"  ⋯ swap ofrece: {entrante['nombre']} "
                             f"Nv{entrante['nivel']} "
                             f"{'/'.join(entrante['tipos'])}")
                    self._swap_nuevo_mons = entrante
            except Exception as exc:  # noqa: BLE001
                self.log(f"  !! no se pudo leer el món del swap: {exc}")
        if not objetivo:
            # Sin objetivo previo: lo calcula aquí. Prioriza al **muerto**
            # (no aporta nada y ocupa plaza) y, si no hay caídos, al peor por
            # nivel y estadísticas. Es la regla de "se cambia el peor, el que
            # menos nos valga o el que esté muerto".
            objetivo = self._peor_para_sustituir()
            if objetivo:
                self.log(f"  ⋯ cambio por nivel: fuera {objetivo}")
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
                # El equipo cambia: el PS real cacheado ya no se refiere al
                # mismo conjunto de móns.
                self._invalidar_ps("swap")
                self.log(f"  ⋯ sustituido: sale {objetivo}")
                # Cambio de Pokémon: quién entra, quién sale y por qué. Es la
                # decisión que más caro sale si se equivoca (se pierde un món
                # con su nivel) y solo quedaba en texto suelto.
                ent = getattr(self, "_swap_nuevo_mons", None) or {}
                self.traza("swap", sale=objetivo,
                           entra=ent.get("nombre") or "?",
                           nivel_entra=ent.get("nivel") or 0,
                           causa="equipo_lleno" if getattr(
                               self, "_catch_pendiente", None) is not None
                           else "subida_nivel",
                           atajo=elegido.get("atajo"))
                self._swap_nuevo_mons = None
                return f"swap: fuera {objetivo}"
        # Sin objetivo: el código elegía la primera opción, o sea un món
        # arbitrario. Queda registrado como tal, porque si alguna vez se ve en
        # los logs significa que la regla del peor no se pudo aplicar.
        self.traza("swap_arbitrario", motivo="sin objetivo calculado")
        return self._opciones_genericas("#swap-choices", "#btn-cancel-swap", "swap")

    def _peor_para_sustituir(self) -> str | None:
        """Nombre del món que menos vale, para sustituirlo.

        Prioriza al **muerto**: un món a 0 PS no aporta nada al equipo y ocupa
        una de las seis plazas, así que es el primero en caer. Solo si no hay
        caídos se va al peor por nivel y estadísticas.

        Se usa en el cambio por subida de nivel, donde no hay captura detrás que
        haya calculado ya el objetivo.
        """
        equipo = self.equipo_con_tipos()
        vivos = [m for m in equipo if (m.get("ps") or 0) > 0]
        muertos = [m for m in equipo if (m.get("ps") or 0) <= 0]

        # El **caído** va primero, y por encima de la regla del duplicado. Un
        # món a 0 PS no aporta nada y ocupa plaza, así que es el mejor
        # candidato posible. Y liberar su plaza no pierde cobertura: su tipo
        # sigue estando en el món vivo del mismo tipo.
        if muertos:
            return min(muertos, key=self._clave_menor_valor).get("nombre")

        # **Regla del usuario: si hay dos del mismo tipo, sale el repetido.**
        # Dos móns del mismo tipo son una plaza desperdiciada: el segundo no
        # aporta nada que el primero no tenga, y la plaza que libera es justo
        # la que necesita el món que entra.
        #
        # Dos detalles que importan y que se hicieron mal a la primera:
        #
        # 1. De los duplicados hay que sacar al **peor**, no al primero que
        #    aparece en la lista. Si hay dos Agua y uno es Nv24 y el otro Nv22,
        #    sale el Nv22: sacar el Nv24 perdería el món bueno del tipo.
        # 2. Solo se sustituye si el entrante es **mejor que el peor
        #    duplicado**. Si ni siquiera lo mejora, el cambio no aporta nada y
        #    se cae al peor global, que siempre es el menos útil de todos.
        nuevo = getattr(self, "_swap_nuevo", None) or self._món_que_entra()
        if nuevo:
            tipos_nuevo = {str(t).lower() for t in (nuevo.get("tipos") or [])}
            poder_nuevo = self._clave_poder(nuevo)
            duplicados = [
                m for m in vivos
                if tipos_nuevo & {str(t).lower() for t in (m.get("tipos") or [])}
            ]
            if duplicados:
                peor_dup = min(duplicados, key=self._clave_menor_valor)
                if poder_nuevo > self._clave_poder(peor_dup):
                    tipos = "/".join(sorted(
                        str(t).lower() for t in (peor_dup.get("tipos") or [])))
                    self.log(f"  ⋯ tipo repetido ({tipos}): sale "
                             f"{peor_dup.get('nombre')} (Nv"
                             f"{peor_dup.get('nivel')}) y entra "
                             f"{nuevo.get('nombre')} (Nv"
                             f"{nuevo.get('nivel')})")
                    return peor_dup.get("nombre")

        if not vivos:
            return None
        return min(vivos, key=self._clave_menor_valor).get("nombre")

    @staticmethod
    def _clave_menor_valor(m: dict) -> tuple:
        """Orden para quedarse con el **menos** útil: menos stats, menos nivel.

        El desempate por nombre solo hace la orden determinista, que si no el
        `min` dependería del orden del HUD y la misma run decidiría distinto
        dos veces seguidas.
        """
        return (
            sum((m.get("baseStats") or {}).values()),
            (m.get("nivel") or 0),
            m.get("nombre") or "",
        )

    @staticmethod
    def _clave_poder(m: dict) -> tuple:
        """Poder simple: (nivel, stats). Para comparar entrante con el equipo."""
        return (
            (m.get("nivel") or 0),
            sum((m.get("baseStats") or {}).values()),
        )

    def _món_que_entra(self) -> dict | None:
        """El món que el juego ofrece para entrar, si se puede saber.

        Solo se usa para la regla del duplicado de tipo: si no lo conocemos,
        `_peor_para_sustituir` cae al "peor" de siempre, que es el
        comportamiento correcto cuando no hay información.
        """
        return getattr(self, "_swap_nuevo_mons", None)

    def tipos_entrenadores_por_sprite(self, mapa: dict) -> dict[str, list[str]]:
        """Sprite -> tipos de cada entrenador del mapa, **por nodo**.

        Lo necesita la regla "si podemos evitar al entrenador, lo evitamos; si
        es el líder, jugamos": para saber si se puede evitar hay que comparar
        **ese** entrenador con **este** equipo, no el conjunto de la ruta. Un
        equipo puede ganarle a un hiker y perder contra un fire-spitter, y con
        la lista plana esa distinción no existe.

        Se guarda con varias claves por sprite (`bug-catcher`, `bugCatcher`,
        `bugcatcher`) porque el SVG y el estado no coinciden en el formato, que
        es la misma trampa de `_mismo_sprite`.
        """
        out: dict[str, list[str]] = {}
        for n in mapa.get("nodos", []):
            if n.get("tipo") != "entrenador" and n.get("type") != "trainer":
                continue
            sprite = n.get("sprite")
            if not sprite:
                continue
            try:
                tipos = [str(t) for t in (self.j.trainer_tipos(sprite) or [])
                         if str(t) and str(t).lower() != "diversos"]
            except Exception:  # noqa: BLE001
                continue
            if not tipos:
                continue
            # Tres claves por sprite, porque el SVG y el estado no coinciden en
            # el formato: `bug-catcher` contra `bugCatcher`.
            out.setdefault(str(sprite), tipos)
            out.setdefault(str(sprite).lower(), tipos)
            out.setdefault(str(sprite).replace("-", "").lower(), tipos)
        return out

    def tipos_de_entrenadores_del_mapa(self, mapa: dict) -> list[str]:
        """Tipos de los entrenadores accesibles en este mapa.

        Es informacion **gratis y Adelante**: la especialidad de cada
        entrenador se lee del estado del juego, sin entrar en combate. Pasa a
        ser objetivo de la captura, porque de nada sirve tener un 2x contra el
        jefe si luego aparece un Firebreather y el equipo entero es 0.5x
        contra el.

        Medido: el bot peleaba contra un Firebreather con Bulbasaur (0.5x) y
        Paras (0.5x) porque su equipo no tenia nada contra Fuego. Con esto la
        captura puede tapar ese agujero.
        """
        out: list[str] = []
        for n in mapa.get("nodos", []):
            if n.get("tipo") != "entrenador" and n.get("type") != "trainer":
                continue
            sprite = n.get("sprite")
            if not sprite:
                continue
            try:
                for t in (self.j.trainer_tipos(sprite) or []):
                    t = str(t)
                    if t and t not in out and t.lower() != "diversos":
                        out.append(t)
            except Exception:  # noqa: BLE001
                continue
        return out

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
            # El starter **no** se cambia nunca. La guía lo dice ("tu peor món
            # no-starter") y en Kanto el starter se elige por ser 2x contra los
            # tres primeros gimnasios, así que el trade se lo llevaría y con él
            # la apertura de la run entera. Medido: con el equipo en 1 solo món
            # el trade cambiaba al starter y la run seguía con un Nv+3 cualquiera.
            no_starter = [m for m in vivos
                          if (m.get("nombre") or "") != self.nombre_starter]
            if not no_starter:
                self.log(f"  trade: solo queda el starter ({self.nombre_starter or '?'})"
                         f" o esta caido; no se cambia el starter")
                if self.j.visible("#btn-skip-trade"):
                    self.j.activar("#btn-skip-trade")
                return "trade declinado (el starter no se cambia)"
            vivos = no_starter
            if vivos:
                # **El món sin `baseStats` resuelto NO puede ser el sacrificiado.**
                # Antes la clave era `sum(baseStats) if baseStats else 0`, así
                # que un món con el dex sin resolver sumaba 0 y ganaba el `min`:
                # el bot cambiaba al **mejor** miembro del equipo. Confirmado en
                # un log: `se ofrece Bulbasaur` con `[Bulbasaur(318), Staryu(245)]`,
                # y el resultado fue cambiar el starter por un Weedle Nv4. El
                # peor del equipo era Staryu. El `1` de delante saca los stats
                # desconocidos de la carrera: solo entran si no hay nadie
                # comparable.
                def _fuerza_sacrificio(m: dict) -> tuple[int, int, str]:
                    st = (sum((m.get("baseStats") or {}).values())
                          if (m.get("baseStats")) else 0)
                    return (0 if st else 1, st, m.get("nombre") or "")

                victimario = min(vivos, key=_fuerza_sacrificio)
                self.log(f"  trade: se ofrece {victimario.get('nombre')}")
                # El JS devuelve `true` solo si ha encontrado y pulsado la fila
                # del món pedido. Antes devolvía `filas.length > 0` cuando no la
                # encontraba, y el llamante pulsaba la primera fila con un clic
                # a ciegas: el món que se iba del equipo no era el elegido, era
                # uno arbitrario. Ahora, si no encuentra la fila, **no se
                # sacrifica a nadie**: es preferible no aceptar el trade (y el
                # bot conserva a su món) antes que perder un buen miembro por
                # un clic sin comprobar.
                fila = self.j.page.evaluate(
                    """(nombre) => {
                        const filas = [...document.querySelectorAll(
                            '#trade-team-list .trade-member-row')];
                        const f = filas.find(x => (x.innerText || '')
                                    .indexOf(nombre) >= 0);
                        if (f) { f.click(); return true; }
                        return false;
                    }""",
                    str(victimario.get("nombre") or ""),
                )
                if not fila:
                    self.log(f"  trade: no aparece la fila de "
                             f"{victimario.get('nombre')} en la lista; no se "
                             f"sacrifica a nadie")
                    self._volcar_trade()
                    if self.j.visible("#btn-skip-trade"):
                        self.j.activar("#btn-skip-trade")
                        return "trade declinado (fila no encontrada)"
                self.j.page.wait_for_timeout(350)

            # ---- Aceptar de verdad: el atajo, no un boton ----------------
            # Las opciones **solo existen despues** de elegir a quien se
            # sacrifica (al llegar solo hay DECLINE), y no hay ningun boton de
            # continuar: la unica forma de cerrar el trato es pulsar `1`, `2` o
            # `3` sobre `div[data-shortcut]`. Comprobado en vivo: con la fila
            # marcada aparece "? NORMAL Lv 19 / ? FAIRY Lv 19 / ? FIRE Lv 19"
            # y pulsar 1 cambia el equipo.
            if _trade_activo():
                elegido = self._opciones_trade()
                if elegido:
                    atajo, texto = elegido
                    self.j.page.keyboard.press(str(atajo))
                    self.j.page.wait_for_timeout(900)
                    if self.j.pantalla() != "trade-screen":
                        self._trade_hecho = True
                        self._invalidar_ps("trade")
                        self.log(f"  ✓ trade aceptado con el atajo {atajo} "
                                 f"({texto}): +3 niveles y PS completos")
                        return f"trade aceptado ({texto}) con atajo {atajo}"
                    # Ni con atajo ni con clic: no se insista, que insistir
                    # sobre una pantalla que no cambia es el atasco clasico.
                    self.log("  trade: el atajo no cerro el trato; se "
                             "intenta con clic")
                    self.j.page.evaluate(
                        r"""(atajo) => {
                            const t = document.getElementById('trade-screen');
                            if (!t) return false;
                            const o = [...t.querySelectorAll('[data-shortcut]')]
                                .filter(e => e.offsetParent !== null &&
                                             e.dataset.shortcut === atajo)[0];
                            if (o) { o.click(); return true; }
                            return false;
                        }""",
                        str(atajo))
                    self.j.page.wait_for_timeout(900)
                    if self.j.pantalla() != "trade-screen":
                        self._trade_hecho = True
                        self._invalidar_ps("trade")
                        self.log(f"  ✓ trade aceptado con clic en la opción "
                                 f"{atajo}")
                        return f"trade aceptado ({texto}) con clic"

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
                # El trade deja el equipo con PS completos: la cache de PS
                # absoluto es doblemente falsa (el món que salió ya no está y
                # los que quedan están llenos).
                self._invalidar_ps("trade")
                self.log("  ✓ trade aceptado (+3 niveles, PS completos) — "
                         "se reordena al más efectivo en el próximo nodo")
                # El trade es el nodo más fuerte del juego (+3 niveles y PS
                # completos) y se pierde un món. Sin registrar a quién se
                # sacrificó no se puede evaluar si fue una buena decisión.
                self.traza("trade_aceptado", recibido=recibido or "?",
                           equipo="|".join(
                               f"{m.get('nombre')}:{m.get('nivel')}"
                               for m in self.equipo_con_tipos()))
                return f"trade aceptado ({recibido or '?'})"
        except Exception as exc:  # noqa: BLE001
            self.log(f"  !! trade falló: {exc}")

        self._volcar_trade()
        if self.j.visible("#btn-skip-trade"):
            self.j.activar("#btn-skip-trade")
            return "trade declinado (no se pudo completar)"
        return self._opciones_genericas("#trade-choices", "#btn-skip-trade", "trade")

    # Al llegar a la pantalla solo hay DECLINE: las opciones **se dibujan al
    # vuelo** cuando se elige a quién se sacrifica, así que se relee una vez
    # tras una espera corta por si el DOM iba tarde (pintura, no lógica).
    JS_OPCIONES_TRADE = r"""() => {
        const t = document.getElementById('trade-screen');
        if (!t) return [];
        return [...t.querySelectorAll('[data-shortcut]')]
            .filter(e => e.offsetParent !== null
                         && e.dataset.shortcut !== 'Space')
            .map(e => ({
                atajo: e.dataset.shortcut,
                texto: (e.innerText || '').replace(/\s+/g, ' ').trim(),
            }));
    }"""

    def _opciones_trade(self) -> tuple[str, str] | None:
        """Qué opción del trade aceptar: `(atajo, texto)`, o `None`.

        Se leen las tres que aparecen tras elegir a quién se sacrifica y decide
        `_mejor_opcion_trade`, que es donde vive el criterio (por tipo contra el
        jefe que toca, después por nivel).
        """
        opciones: list[dict] = []
        for intento in range(2):
            try:
                opciones = self.j.page.evaluate(self.JS_OPCIONES_TRADE)
            except Exception as exc:  # noqa: BLE001
                self.log(f"  trade: no se pudieron leer las opciones: {exc}")
                return None
            if opciones:
                break
            if intento == 0:
                self.j.page.wait_for_timeout(500)
        if not opciones:
            self.log("  trade: no hay opciones a la vista; el nodo es "
                     "inesperado y no se acepta a ciegas")
            return None

        elegido = self._mejor_opcion_trade(opciones, self.tipo_lider or "")
        if elegido is None:
            return None
        self.log(f"  trade: opciones {[(o['atajo'], o['texto'][:18]) for o in opciones]}"
                 f" -> se pide la {elegido['atajo']} ({elegido['texto'][:30]})")
        return (str(elegido["atajo"]), elegido["texto"][:40])

    def _mejor_opcion_trade(self, opciones: list[dict],
                            rival: str) -> dict | None:
        """Cuál de las tres opciones pedir, o `None` si no hay ninguna.

        Función **pura**, sin DOM: las tres opciones enseñan el tipo y el nivel
        (`? Fairy Lv 19`), y el criterio es el mismo que usa la captura: primero
        un tipo que pegue al jefe que toca, después el de más nivel, y si
        ninguna convence, la primera (que es lo que haría un jugador sin
        criterio).

        Sin esto se aceptaría siempre la opción 1 y se perdería media partida
        de tipos: el trade es +3 niveles **y** un tipo nuevo, y el tipo es justo
        lo que sale gratis.
        """
        if not opciones:
            return None
        tipo_rival = T.normalizar(rival.strip()) if rival and rival.strip() else ""

        def _tipo_de(texto: str) -> str:
            for t in ("Bug", "Dark", "Dragon", "Electric", "Fairy", "Fighting",
                      "Fire", "Flying", "Ghost", "Grass", "Ground", "Ice",
                      "Normal", "Poison", "Psychic", "Rock", "Steel", "Water"):
                if t.lower() in texto.lower():
                    return t
            return "Normal"

        def _nivel_de(texto: str) -> int:
            m = re.search(r"Lv\s*(\d+)", texto)
            return int(m.group(1)) if m else 0

        def _puntuacion(o: dict) -> tuple:
            tipo = T.normalizar(_tipo_de(o.get("texto") or ""))
            nv = _nivel_de(o.get("texto") or "")
            mult = 1.0
            if tipo_rival:
                try:
                    mult = T.multiplicador(tipo, tipo_rival)
                except Exception:  # noqa: BLE001
                    mult = 1.0
            # Un 2x al jefe que toca vale mucho más que dos niveles: es la
            # diferencia entre pelear y perder contra el líder. Un 0.5 es lo
            # peor que puede pasar, así que baja por debajo de cualquier neutro.
            return (mult, nv)

        return max(opciones, key=_puntuacion)

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
                        self._prep_fallos = 0
                        return (f"elite prep [{info}] -> {self.j.pantalla()} "
                                f"({via})")
            # Último recurso: si sigue aquí, se manda Enter y Escape.
            self.j.page.keyboard.press("Enter")
            self.j.page.wait_for_timeout(400)
            if self.j.pantalla() != "elite-prep-screen":
                self._prep_fallos = 0
                return f"elite prep [{info}] -> {self.j.pantalla()} (Enter)"

        self.log("  !! el prep no cede: se fuerza la salida")
        self._prep_fallos = getattr(self, "_prep_fallos", 0) + 1
        self._volcar_prep()
        for sel in ("#btn-elite-prep-fight", "#btn-elite-prep-continue",
                    "#elite-prep-screen button"):
            try:
                self.j.clic(sel, 1.5)
                self.j.page.wait_for_timeout(400)
                if self.j.pantalla() != "elite-prep-screen":
                    self._prep_fallos = 0
                    return f"elite prep [{info}] -> {self.j.pantalla()} (forzado)"
            except Exception:  # noqa: BLE001
                pass
        # **Bucle infinito corregido.** Este manejador se rendía y **volvía
        # sin salir**, así que el paso siguiente volvía a entrar, reintentaba
        # el mismo orden, fallaba igual y repetía para siempre:
        #   `!! el prep no cede` / `[prep -> Krabby]` / `!! el prep no cede` …
        # El detector de atasco no lo veía porque la pantalla no cambia de
        # verdad: se queda en `elite-prep-screen` todo el rato.
        # El prep es **opcional** (es solo preparar el equipo antes del jefe),
        # así que quedarse ahí no puede ser una razón para perder la run.
        # Segundo fallo: se salta directamente a la recarga, que devuelve la
        # partida al mapa sin perder progreso.
        if self._prep_fallos >= 2:
            self.log(f"  !! el prep no cede tras {self._prep_fallos} intentos: "
                     f"recargo la pagina para salir de aqui (es opcional)")
            try:
                self.j.page.reload(wait_until="domcontentloaded")
                self.j.page.wait_for_timeout(2500)
                self._leer_mapa_cache = None
                self._ps_real.clear()
                self._activar_ajustes()
                self._prep_fallos = 0
                return (f"elite prep [{info}] -> recarga para salir "
                        f"-> {self.j.pantalla()}")
            except Exception as exc:  # noqa: BLE001
                self.log(f"  !! la recarga no funciono: {exc}")
        return f"elite prep [{info}] (no se pudo salir)"

    def _volcar_prep(self) -> None:
        """Vuelca los controles reales de `elite-prep-screen`.

        Los selectores del bot están adivinados y no funcionan: la pantalla se
        queda ahí sin poder salir. En vez de seguir adivinando, se escribe lo
        que **de verdad** hay —botones, enlaces y su `id`/`class`/texto— para
        ajustar el selector con datos y no con suposiciones.
        """
        try:
            datos = self.j.page.evaluate(
                r"""() => {
                  const s = document.getElementById('elite-prep-screen');
                  if (!s) return { error: 'no existe #elite-prep-screen' };
                  const vis = e => e && e.offsetParent !== null;
                  const info = (e) => ({
                    tag: e.tagName.toLowerCase(),
                    id: e.id || null,
                    cls: e.className || null,
                    texto: (e.innerText || e.textContent || '').trim().slice(0, 40),
                    shortcut: e.getAttribute('data-shortcut'),
                    visible: vis(e),
                  });
                  return {
                    botones: [...s.querySelectorAll('button')].map(info),
                    enlaces: [...s.querySelectorAll('a,[role=button]')].map(info),
                    hijos_tocables: [...s.querySelectorAll(
                      '[data-shortcut],[onclick],[class*=btn],[class*=choice]')]
                      .map(info).slice(0, 30),
                    texto_pantalla: (s.innerText || '').trim().slice(0, 400),
                  };
                }"""
            )
            destino = Path("/tmp/opencode/prep.json")
            destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                               encoding="utf-8")
            nb = len(datos.get("botones", []) or [])
            self.log(f"  ⟂ volcado del prep -> {destino} "
                     f"({nb} boton(es), "
                     f"{len(datos.get('hijos_tocables', []) or [])} tocable(s))")
        except Exception as exc:  # noqa: BLE001
            self.log(f"  !! no se pudo volcar el prep: {exc}")

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
            # El estado del juego marca `usable: false` en los objetos que no
            # se pueden equipar (los de efecto en batalla, tipo Red Card). No se
            # intenta: equiparlos falla siempre, y cada fallo quemaba el mismo
            # nodo. Antes solo se filtraba por `objetos_fallidos`, que no se
            # rellenaba nunca, así que esta vía no existía.
            if bolsa[indice].get("usable") is False:
                continue
            if j is not None:
                plan.append((indice, j, nombre, motivo))
        if not plan:
            return f"bolsa: {len(bolsa)} sin objetos conocidos"

        hechos: list[str] = []
        for indice, j, nombre, motivo in plan:
            # **El índice se recalcula en cada uso.** `plan` guarda índices
            # sobre el snapshot de `bolsa` del principio, pero `usar_item`
            #-indexa el DOM **vivo** (`#elite-prep-items .item-badge`).nth(i)).
            # En cuanto el primer objeto se gasta, la bolsa se acorta y todos
            # los índices siguientes apuntan un objeto más arriba: con dos o
            # más objetos en la bolsa, el segundo se equipaba al món equivocado,
            # la verificación fallaba y el id previsto se metía en
            # `objetos_fallidos`, que nunca se limpia. O sea: se perdía el
            # objeto para el resto de la partida, en silencio.
            # Aquí se busca por **id** en la bolsa viva, y solo si no aparece
            # se recurre al índice original.
            bolsa_viva = self.j.bolsa_items()
            oid_plan = str((bolsa[indice].get("id") or indice)).lower()
            idx_vivo = next(
                (k for k, o in enumerate(bolsa_viva)
                 if str((o.get("id") or k)).lower() == oid_plan),
                None)
            idx_uso = idx_vivo if idx_vivo is not None else indice
            antes = len(bolsa_viva)
            self.j.usar_item(idx_uso, j, nombre)
            despues = len(self.j.bolsa_items())
            # Una cura o una subida de nivel cambian la vida: la cache de PS
            # absoluto deja de valer para ese món.
            self._invalidar_ps(f"objeto -> {nombre}")
            # **Verificación de verdad**: el objeto aparece debajo del món, en
            # su `div.team-slot.team-slot-reorder`. Antes solo se miraba si la
            # bolsa bajaba, y eso no distingue un equip de un objeto gastado.
            puesto = self.j.objeto_del_mons(nombre)
            # **Qué objeto va a qué Pokémon y con qué motivo.** Es la segunda
            # palanca del juego según la guía y era el punto ciego: la bolsa
            # llegaba casi vacía (media 1,4 objetos por run) y cuando había
            # algo no se anotaba el reparto, así que no se podía saber si el
            # equipo iba equipado o desnudo.
            self.traza("objeto_equipado" if puesto else "objeto_usado",
                       objeto=str(oid_plan)[:28], mon=nombre,
                       puesto=str(puesto or "")[:28],
                       motivo=motivo, bolsa=f"{antes}->{despues}")
            if puesto:
                hechos.append(f"{nombre} <- {puesto}")
                self.log(f"  ⋯ objeto EQUIPADO -> {nombre}: {puesto} ({motivo})")
            elif despues < antes:
                hechos.append(f"{nombre}: {motivo} (usado)")
                self.log(f"  ⋯ objeto USADO -> {nombre}: {motivo} "
                         f"(bolsa {antes}->{despues})")
            else:
                # Falla: se apunta para no reintentarlo en la siguiente visita a
                # la bolsa (antes el set se leia y nunca se escribia, asi que el
                # comentario que lo justifica era mentira), y se vuelca el DOM
                # de la pantalla para poder ajustar los selectores con datos.
                oid = oid_plan
                # Un clic puede fallar por un timeout (animación, overlay,
                # strict mode) sin que el objeto sea inusable. Con el veto
                # permanente, **un solo timeout dejaba el objeto sin usar
                # hasta el final de la partida**, sin rastro en el log de que
                # fuera reversible. Ahora solo se veta si el objeto ha fallado
                # dos veces: primero se reintenta, y a la segunda se da por
                # bueno que no funciona.
                self._objeto_fallos[oid] = self._objeto_fallos.get(oid, 0) + 1
                if self._objeto_fallos[oid] >= 2:
                    self.objetos_fallidos.add(oid)
                self.log(f"  ✗ objeto NO usado -> {nombre}: {motivo} "
                         f"(bolsa {antes}->{despues}) [no se reintenta]")
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
    # Lo que devuelve el manejador de batalla cuando solo hay que seguir
    # pulsando continuar. Se compara literal porque es lo que detecta el
    # bucle de "continuar" sin avanzar.
    CONTINUAR_BATALLA = "[continuar -> True] pulso continuar hasta el final"

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
            # **Desglose sin muestreo.** El logout de texto sale de 4 en 4, así
            # que "cuántas peleas de entrenador" no se puede sacar del log: sale
            # un cuarto de la realidad. Estos contadores no pasan por ese filtro.
            # El entrenador da +2 niveles a todo el equipo y el salvaje +1, que
            # es justo lo que decide el 2.º gimnasio (medido: 2,5 niveles).
            ("peleas entrain.", f"{self.peleas_entrenador} "
                               f"(+{self.peleas_entrenador * 2} nv)"),
            ("peleas salvaje", f"{self.peleas_salvaje} "
                              f"(+{self.peleas_salvaje} nv)"),
            ("capturas", str(self.capturas)),
            ("tutores", str(self.tutores)),
            ("objetos", str(self.objetos)),
            ("centros", str(self.centros)),
            ("equipo", f"{len(e)} ({nivel})"),
        ]
        ancho = max(len(k) for k, _ in filas)
        lineas = ["", "-" * (ancho + 26), f"  RESUMEN {self.region}"]
        lineas += [f"  {k.ljust(ancho)} : {v}" for k, v in filas]
        # El diario de decisiones se vuelca aquí, con la run ya terminada, para
        # que exista aunque el proceso muera o se corte. Sin esto las decisiones
        # solo vivían en el log de texto, del que no se puede medir nada.
        destino = self.volcar_traza()
        if destino:
            lineas.append(f"  {'traza'.ljust(ancho)} : {destino}")
            # Las visitas al nodo del tutor: no hay pantalla para ellas y sin
            # este dato no se sabe a quién se le dio el disco.
            if getattr(self, "_tutor_visitado", None):
                lineas.append(f"  {'visitas tutor'.ljust(ancho)} : "
                              f"{len(self._tutor_visitado)}")
        lineas += ["-" * (ancho + 26), ""]
        return "\n".join(lineas)

    def _activar_ajustes(self) -> None:
        """Auto-skip al entrar, antes de tocar nada (ver `navegador`).

        El log dice **lo que el juego ha leido**, no lo que el bot ha escrito.
        Antes decía "activado" sin más y era falso: se escribian claves
        anidadas (`autoSkip.allFights`) y el juego lee planas
        (`autoSkipAllBattles`), con lo que las partidas iban a 1× en vez de 3×.
        """
        try:
            leido = self.j.activar_auto_skip()
            self.log(f"  ajustes: {leido}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"  !! no se pudieron activar los ajustes: {exc}")

    def _recuperar_batalla_clavada(self) -> bool:
        """Saca al bot de una batalla que no avanza. Devuelve si lo consegue.

        El caso medido: `continuar` con el enemigo ya a 0 HP, o sea la batalla
        esta ganada pero la pantalla no pasa al resultado. Pulsar continuar no
        sirve; hay que forzar **auto-battle** y, si tampoco, recargar la pagina.
        """
        self._batalla_clavada = getattr(self, "_batalla_clavada", 0) + 1
        for _ in range(3):
            try:
                self.j.activar("#btn-auto-battle")
                self.j.page.wait_for_timeout(900)
                if self.j.pantalla() != "battle-screen":
                    self.log(f"  batalla desbloqueada con auto-battle -> "
                             f"{self.j.pantalla()}")
                    self._batalla_clavada = 0
                    return True
                self.j.activar("#btn-continue")
                self.j.page.wait_for_timeout(900)
                if self.j.pantalla() != "battle-screen":
                    self.log(f"  batalla desbloqueada con continue -> "
                             f"{self.j.pantalla()}")
                    self._batalla_clavada = 0
                    return True
            except Exception as exc:  # noqa: BLE001
                self.log(f"  !! recuperar batalla fallo: {exc}")
        # Ultimo recurso: recargar. La partida se guarda sola en el navegador.
        if self._batalla_clavada >= 2:
            self.log("  batalla realmente clavada: recargo la pagina")
            try:
                self.j.page.reload(wait_until="domcontentloaded")
                self.j.page.wait_for_timeout(2500)
                self._leer_mapa_cache = None
                self._ps_real.clear()
                self._activar_ajustes()
                self._batalla_clavada = 0
                return True
            except Exception as exc:  # noqa: BLE001
                self.log(f"  !! recarga fallo: {exc}")
        return False

    def jugar(self, max_pasos: int, pausa: float = 0.5) -> None:
        # **R1 (regla del usuario): la run nunca se corta automaticamente.**
        # Solo termina por perdida (`GAME_OVER`) o por completar la region
        # (`CHAMPION`). Ni el presupuesto de pasos ni un atasco la cortan: un
        # presupuesto agotado es solo una prueba corta, y un atasco se intenta
        # **recuperar** (desbloquear, recargar la pagina) antes de rendirse.
        self._activar_ajustes()
        # **Rama del experimento.** Si hay un brazo asignado, se escribe en el
        # log ANTES de jugar. Es lo unico que permite despues agrupar las
        # partidas por brazo y sacar un p-valor: sin la etiqueta en el log, los
        # 100 runs son 100 numeros sin grupo de control. Ver `experimento.py`.
        brazo = os.environ.get("PKL_BRAZO")
        if brazo:
            self.log(f"== brazo={brazo} | "
                     f"PKL_MARGEN_BASE={os.environ.get('PKL_MARGEN_BASE', '?')} | "
                     f"PKL_ESCALERA_RIESGO={os.environ.get('PKL_ESCALERA_RIESGO', '1')} | "
                     f"PKL_TRADE={os.environ.get('PKL_TRADE', '1')} | "
                     f"codigo={os.environ.get('PKL_HASH', '?')} ==")
        if max_pasos and max_pasos > 0:
            # R1: el presupuesto es solo informativo y para las pruebas cortas.
            # Agotado **no** termina la run: se avisa una vez y se sigue jugando
            # sin límite, hasta ganar o perder.
            self.log(f"== run {self.region} | presupuesto {max_pasos} pasos "
                     f"(solo para pruebas: agotado NO corta la run) ==")
        else:
            self.log(f"== run {self.region} | sin presupuesto de pasos ==")
        # Guardia anti-bucle: si la misma pantalla se repite muchas veces sin que
        # cambie nada, el clic no está surtiendo efecto y seguir es tirar CPU.
        vistos: dict[str, int] = {}
        # Antes 12, y como el contador acumulaba toda la partida en vez de
        # contar la racha, mataba partidas sanas. Ahora que cuenta repeticiones
        # **consecutivas**, 25 es un bucle de verdad (mismo clic, misma
        # pantalla, 25 veces sin avanzar) y margen de sobra para las
        # animaciones y las transiciones lentas.
        tope_repetidas = 25
        # Techo de intentos de batalla "viva": sin el, un combate que se
        # mueve pero no acaba pulsaba continuar indefinidamente.
        TOPE_BATALLA_VIVA = 4
        # Tope de "continuar" seguidos en batalla (ver mas abajo).
        TOPE_CONTINUAR = 4
        anterior = None
        # **R1: la run nunca se corta sola.** Solo termina por `GAME_OVER`
        # (perdida) o por `CHAMPION` (region completada). El presupuesto de
        # pasos, si se pasa, **no** termina la partida: deja de contar pasos y
        # sigue jugando. Antes `--max-pasos` cortaba la partida a mitad con
        # `PRESUPUESTO_AGOTADO`, que no es ganar ni perder.
        while self.resultado == "EN_CURSO":
            try:
                hecho = self.paso()
            except Exception as exc:  # noqa: BLE001
                # Un error repetido en la misma pantalla no se reintenta
                # indefinidamente: se para la run. Antes un `NameError` en el
                # manejador de trades lanzaba el mismo error cientos de veces y
                # la partida se arrastraba sin avanzar (4 nodos en 700 s).
                # **Los errores de código cortan la run**, a diferencia de los transitorios
                # (tiempos de espera agotados), que se reintentan. Un
                # `NameError` o un `TypeError` no se arregla reintentando: cortar
                # evita gastar media tanda en una partida que no va a ningún
                # sitio. Medido: un typo en el manejador de trades dejó una
                # partida en 4 nodos de 700 s.
                #
                # OJO, esta es la **única** excepción a la regla de que la run
                # nunca se corta sola. No es una decisión de juego: es que el bot
                # es quien está roto. Si se reintentara, el mismo error se
                # repetiría para siempre y la run no acabaría nunca ni ganando ni
                # perdiendo, que es peor que cortarla: un `ERROR_DE_CODIGO`
                # registrado se arregla en el código; un proceso colgado solo se
                # mata a mano.
                if isinstance(exc, self.ERRORES_DE_CODIGO):
                    # La regla del usuario: **este error corta la run y hay que
                    # arreglarlo**. El bot no puede arreglar código, así que lo
                    # que le toca es dejar el error **localizado**: tipo,
                    # mensaje, archivo, línea y dónde en el bot se múltiple. Sin
                    # archivo y línea hay que leer 2000 líneas de traza para
                    # encontrar un `NameError`, y eso es lo que hacia que un
                    # bug pasara sin arreglar durante varias runs.
                    tb = traceback.extract_tb(exc.__traceback__)
                    lugar = ""
                    if tb:
                        ultimo = tb[-1]
                        lugar = f"{ultimo.filename}:{ultimo.lineno}"
                    self.log(f"  !! error de CÓDIGO ({type(exc).__name__}): {exc}")
                    self.log(f"  !! en: {lugar or '?'} | "
                             f"pantalla: {self.j.pantalla()} | paso: {self.pasos}")
                    self.log("  !! la run se corta: el bot está roto, no la "
                             f"partida. Arreglar en el código.")
                    # Se escribe aparte porque el log se conserva 3 runs
                    # (`lanzar_tanda.py` limpia los viejos): si el crash está
                    # en el log y el log se borra, el bug se pierde.
                    self._volcar_crash(exc, lugar)
                    self.resultado = "ERROR_DE_CODIGO"
                    return
                clave_err = f"{self.j.pantalla()}|{type(exc).__name__}:{exc}"
                self._errores[clave_err] = self._errores.get(clave_err, 0) + 1
                if self._errores[clave_err] >= 3:
                    self.log(f"  !! 3 errores iguales en {clave_err}: "
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
            clave = f"{donde}|{hecho[:40]}"
            # **Consecutivas de verdad.** El comentario de aquí decía "solo
            # cuentan las repeticiones consecutivas" y el código no lo hacia:
            # `anterior` solo guardaba la pantalla y `vistos` no se limpiaba,
            # así que el contador **acumulaba toda la partida**. En
            # `map-screen` la acción es siempre `nodo 1`, `nodo 2`… (el atajo
            # pulsado), o sea el valor normal de cada visita: una run sana
            # declaraba `ATASCADO` en la visita 13 de cualquier atajo. Medido
            # en los logs: `[nodo -> 1]` aparece 13 veces y `[nodo -> 2]` 12 en
            # una partida con 2 insignias y 13 combates ganados, o sea una run
            # que iba bien y se habría cortado por el detector.
            # Ahora se cuenta la racha: al cambiar de pantalla+acción, el
            # contador vuelve a cero. Un bucle real (mismo clic, misma
            # pantalla, sin avanzar) sí llega al tope, y una partida que
            # progresa nunca se cuenta dos veces por separado.
            if clave == anterior:
                vistos[clave] = vistos.get(clave, 0) + 1
            else:
                anterior = clave
                vistos[clave] = 1
            # **Tope especifico para 'continuar' en batalla.** Un boton de
            # continuar que se pulsa muchas veces no esta avanzando: el log
            # mostraba `continuar` con el enemigo a 0 HP, o sea la batalla ya
            # estaba ganada y el bot seguia pulsando sin que la pantalla
            # cambiara. Antes el tope era 25 para todo y ademas la exencion de
            # batalla reseteaba el contador a 1 cada 4 intentos, con lo que el
            # bucle era infinito. Aqui un tope de 4, sin exencion.
            es_continuar_batalla = (hecho == self.CONTINUAR_BATALLA
                                    and donde == "battle-screen")
            if es_continuar_batalla:
                if vistos[clave] > TOPE_CONTINUAR:
                    self.log(f"  !! 'continuar' en batalla x{vistos[clave]}: "
                             f"la pantalla no avanza, recupero")
                    vistos.pop(clave, None)
                    anterior = None
                    if self._recuperar_batalla_clavada():
                        continue
            elif vistos[clave] > tope_repetidas:
                # En batalla, muchas pulsaciones de SKIP son normales: antes de
                # declarar atasco se comprueba que el estado de verdad no cambia.
                if donde == "battle-screen":
                    # **Con techo.** Esta exencion reseteaba el contador cada
                    # vez que el PS cambiaba, sin limite de reintentos, asi que
                    # un combate que se mueve pero no acaba pulsaba `continuar`
                    # para siempre y la run se quedaba ahi. Ahora hay tope.
                    self._batalla_viva = getattr(self, "_batalla_viva", 0) + 1
                    if self._batalla_viva < TOPE_BATALLA_VIVA:
                      f1 = self.firma_batalla()
                      self.j.activar("#btn-auto-battle")
                      self.j.page.wait_for_timeout(1800)
                      f2 = self.firma_batalla()
                      if f1 and f1 != f2:
                        self.log("  batalla sigue viva (cambio de PS), "
                                 f"intento {self._batalla_viva}/"
                                 f"{TOPE_BATALLA_VIVA}, continúo")
                        # La racha se reinicia a 1: es la misma clave, asi que
                        # el paso siguiente cuenta 2.
                        vistos[clave] = 1
                        continue
                self.log(f"  !! atascado en {clave} x{vistos[clave]}: "
                         f"intento {self._atasco_intentos + 1}/"
                         f"{self.MAX_INTENTOS_ATASCO} desbloquear")
                self.volcar_atasco(donde)
                self._atasco_intentos += 1
                # **Regla: la run no se corta nunca por un atasco.** Solo se
                # acaba por perder (`GAME_OVER`) o por completar la región
                # (`CHAMPION`). Antes, tras fallar dos intentos de
                # desbloqueo, el bot declaraba `ATASCADO` y terminaba la run:
                # un fallo de selector del sitio (un cambio en el HTML, una
                # animación más lenta) Tiraba la partida entera, y con ella
                # el trabajo de dos insignias.
                # Ahora la recuperación **escala**: primero pulsas teclas,
                # luego recarga la página, y en el último escalón reinicia la
                # run. Solo si fallan los tres se acepta que la partida está
                # muerta, porque a partir de ahí ya no es "no cortar": es que
                # el juego no responde.
                for _ in range(2):
                    self._desbloquear()
                    if self.j.pantalla() != donde:
                        break
                if self.j.pantalla() != donde:
                    # Solo se limpia la clave desbloqueada, no todo el
                    # historial: si el bucle volvía a aparecer, tiene que
                    # volver a acumular.
                    vistos.pop(clave, None)
                    anterior = None
                    self._atasco_intentos = 0
                    self.log(f"  desbloqueado -> {self.j.pantalla()}")
                    continue
                # Escalón 2: recargar la página. Un estado a medias en el DOM
                # es la causa más común de quedarse clavado.
                if self._atasco_intentos < self.MAX_INTENTOS_ATASCO:
                    self.log(f"  · recargo la pagina (intento "
                             f"{self._atasco_intentos}/"
                             f"{self.MAX_INTENTOS_ATASCO})")
                    try:
                        self.j.page.reload(wait_until="domcontentloaded")
                        self.j.page.wait_for_timeout(2500)
                        self._leer_mapa_cache = None
                        self._ps_real.clear()
                        vistos.clear()
                        anterior = None
                        continue
                    except Exception as exc:  # noqa: BLE001
                        self.log(f"  !! la recarga fallo: {exc}")
                self.resultado = "ATASCADO"
                break
            if pausa:
                self.j.page.wait_for_timeout(int(pausa * 1000))
        # R1: aqui ya solo se sale por perdida o por region completada. Un
        # presupuesto agotado **no** corta la partida: el bucle de arriba no
        # tiene ese tope, asi que este `if` es solo un aviso por si acaso.
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
    # R1: en vivo tampoco se corta por presupuesto, igual que `jugar()`.
    while bot.resultado == "EN_CURSO":
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

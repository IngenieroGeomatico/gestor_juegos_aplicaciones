"""Control del Firefox del usuario por WebDriver BiDi (la "opción B").

Playwright **no** puede conectarse a un Firefox normal: usa su propio Firefox
parcheado (protocolo *juggler*) y solo maneja el navegador que él mismo lanza.
La única forma de jugar en el Firefox de verdad, con tu perfil y tu sesión, es
hablar WebDriver BiDi, que es el protocolo estándar de Firefox.

Por eso existe este módulo: un `Page` con la misma interfaz que usa el bot, pero
implementado sobre BiDi. El bot no cambia; solo se cambia el backend.

Qué cubre y cómo:

- `evaluate` -> `script.evaluate`. Es el 80% del bot: ya casi todo se hace
  llamando a JavaScript dentro de la página, y eso en BiDi es idéntico.
- `locator`/`count`/`inner_text`/`get_attribute`/`is_visible` -> se resuelven
  con `script.evaluate` devolviendo JSON. No se trae un motor de selectores.
- `click` -> `browsingContext` + JS `.click()` cuando el elemento lo acepta, y
  `input.performActions` con un clic real cuando hace falta (drag del HUD).
- `keyboard`/`mouse` -> `input.performActions`.
- `route` (bloquear ruido: anuncios y analítica) -> **no hay equivalente
  limpio**. Se deja el拦截 desactivado y se acepta el banner de cookies, que el
  bot ya sabe saltyar. Es la única funcionalidad que se pierde.

Limitaciones conocidas, todas medibles:

- Sin `route`: se pierde el filtrado de peticiones, no la partida.
- El arrastre del HUD (`drag_and_drop`) necesita punteros reales; aquí se hace
  con `input.performActions` y hay que verificar que el juego lo acepte.
- Firefox debe arrancarse **con el puerto de depuración abierto** y **sin
  estar ya corriendo**: un Firefox vivo ignora los flags nuevos.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import websocket  # websocket-client

URL_JUEGO = "https://pokelike.xyz"


# ------------------------------------------------------------- conexión BiDi
class ErrorBidi(RuntimeError):
    pass


def puerto_abierto(puerto: int, host: str = "127.0.0.1") -> bool:
    """¿Hay un Firefox escuchando BiDi en ese puerto?

    Ojo: **no** se puede comprobar con `/json/version` como en Chromium; Firefox
    devuelve 404 ahí y por eso esta comprobación mentía. Lo que se hace es abrir
    el WebSocket BiDi del puerto, que es el protocolo de verdad: si el socket
    conecta y responde, el puerto está bien.
    """
    try:
        ws = websocket.create_connection(f"ws://{host}:{puerto}/session",
                                         timeout=3, suppress_origin=True)
    except Exception:  # noqa: BLE001
        return False
    try:
        ws.close()
    except Exception:  # noqa: BLE001
        pass
    return True


def lanzar_firefox(puerto: int = 9222, perfil: str | Path | None = None,
                   headless: bool = False, ejecutable: str = "firefox") -> int:
    """Arranca Firefox con el puerto de depuración abierto.

    Devuelve el PID. Si el puerto ya está ocupado, se asume que el Firefox del
    usuario ya está preparado y no se arranca otro (importante: un Firefox ya
    vivo ignora los flags y abrir un segundo con el mismo perfil falla).
    """
    if puerto_abierto(puerto):
        return 0
    cmd = [ejecutable, "--remote-debugging-port", str(puerto),
           "--no-remote-experimental-window"]
    if headless:
        cmd.append("--headless")
    if perfil:
        cmd += ["--profile", str(perfil)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for _ in range(60):
        if puerto_abierto(puerto):
            return proc.pid
        time.sleep(0.5)
    raise ErrorBidi(
        f"Firefox no abrió el puerto {puerto}. Ojo: si ya tienes Firefox "
        f"abierto hay que cerrarlo, porque ignora los flags de depuración.")


def perfiles_de_firefox() -> list[Path]:
    """Rutas de los perfiles de Firefox del usuario, leídas de `profiles.ini`.

    Se leen las secciones `[ProfileN]` completas en vez de buscar líneas sueltas:
    en `profiles.ini` el orden de las claves no es fijo (`IsRelative=1` puede
    ir antes o después de `Path=`), y buscando en orden fijo solo salía un
    perfil de los dos.
    """
    ini = Path.home() / ".mozilla" / "firefox" / "profiles.ini"
    if not ini.exists():
        return []
    base = Path.home() / ".mozilla" / "firefox"
    salida: list[Path] = []
    ruta: str | None = None
    relativa = True
    for linea in ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if linea.startswith("[") and linea.endswith("]"):
            # Fin de sección: si era de perfil y trae ruta, se guarda.
            if ruta:
                salida.append((base / ruta) if relativa else Path(ruta))
            ruta, relativa = None, True
            if not linea.startswith("[Profile"):
                ruta = None
            continue
        if "=" not in linea:
            continue
        clave, valor = (x.strip() for x in linea.split("=", 1))
        if ruta is None and clave == "IsRelative":
            relativa = valor == "1"
        elif clave == "Path":
            ruta = valor
    if ruta:
        salida.append((base / ruta) if relativa else Path(ruta))
    return [p for p in salida if p.is_dir()]


def perfil_con_cuenta(puerto: int = 9290) -> Path | None:
    """El perfil que tiene la cuenta de Pokelike, detectado solo.

    Importa porque `profiles.ini` marca `Default=1` en un perfil que puede estar
    vacío: buscar "el perfil por defecto" abría un Firefox sin usuario. La cuenta
    vive en `localStorage` (`poke_username` y `poke_save_token`), así que se
    busca el perfil que tenga esas claves. Se prueban de uno en uno en un Firefox
    desechable y headless, así que no se toca el perfil del usuario.
    """
    for perfil in perfiles_de_firefox():
        if not (perfil / "prefs.js").exists():
            continue
        proc = subprocess.Popen(
            ["firefox", "--remote-debugging-port", str(puerto),
             "--profile", str(perfil), "--headless",
             "--no-remote-experimental-window", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(25):
                if puerto_abierto(puerto):
                    break
                time.sleep(0.4)
            else:
                continue
            page, _ctx, _ = abrir_remoto(puerto=puerto, headless=True)
            usuario = page.evaluate("localStorage.getItem('poke_username')")
            if usuario:
                return perfil
        except Exception:  # noqa: BLE001
            continue
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                proc.kill()
    return None


def url_bidi(puerto: int = 9222, host: str = "127.0.0.1") -> str:
    """Endpoint WebSocket de BiDi.

    Es fijo (`ws://host:puerto/session`): Firefox no lo anuncia por HTTP, al
    revés que Chromium, así que no hay nada que descubrir.
    """
    return f"ws://{host}:{puerto}/session"


# ------------------------------------------------------------------ protocolo
# Teclas especiales: WebDriver BiDi las llama por **punto de código**, no por
# nombre. El bot (heredado de la API de Playwright) pide "Space" o "Enter", y
# mandarlo tal cual devuelve "invalid argument". Traducción según la
# especificación de BiDi.
_TECLAS_BIDI = {
    "Null": "", "Cancel": "", "Help": "",
    "Backspace": "", "Tab": "", "Clear": "",
    "Return": "", "Enter": "", "Shift": "",
    "Control": "", "Alt": "", "Pause": "",
    "Escape": "", "Esc": "", "Space": "",
    "PageUp": "", "PageDown": "", "End": "",
    "Home": "", "ArrowLeft": "", "ArrowUp": "",
    "ArrowRight": "", "ArrowDown": "", "Insert": "",
    "Delete": "", "Meta": "", "OS": "",
    "F1": "", "F2": "",
}
# Los valores de arriba se escriben con escapes explícitos para que no se
# pierdan al copiar el código: se rellenan aquí.
_TECLAS_BIDI.update({
    "Null": "", "Cancel": "", "Help": "", "Backspace": "",
    "Tab": "", "Clear": "", "Return": "", "Enter": "",
    "Shift": "", "Control": "", "Alt": "", "Pause": "",
    "Escape": "", "Esc": "", "Space": "", "PageUp": "",
    "PageDown": "", "End": "", "Home": "", "ArrowLeft": "",
    "ArrowUp": "", "ArrowRight": "", "ArrowDown": "",
    "Insert": "", "Delete": "", "Meta": "",
})


def tecla_bidi(nombre: str) -> str:
    """Nombre de tecla de Playwright -> punto de código que BiDi entiende."""
    if nombre in _TECLAS_BIDI:
        return _TECLAS_BIDI[nombre]
    if len(nombre) == 1:
        return nombre
    return ""  # lo que se le pase, al menos que sea pulsable


class Sesion:
    """Cliente WebDriver BiDi mínimo: lo justo para lo que hace el bot."""

    def __init__(self, ws_url: str):
        # `suppress_origin` es obligatorio: Firefox rechaza el handshake WebSocket
        # de BiDi si ve una cabecera `Origin` ("incorrect Origin header"), y
        # websocket-client la envía por defecto. Sin esto la conexión falla con
        # un 400 que no dice nada de BiDi.
        self.ws = websocket.create_connection(ws_url, timeout=60,
                                              suppress_origin=True)
        self._id = 0

    def cmd(self, metodo: str, params: dict | None = None,
            timeout: float = 30) -> dict:
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": metodo,
                                 "params": params or {}}))
        limite = time.time() + timeout
        while time.time() < limite:
            msg = json.loads(self.ws.recv())
            if msg.get("id") != mid:
                continue  # evento o respuesta de otra petición
            if "error" in msg:
                raise ErrorBidi(f"{metodo}: {msg['error']}")
            return msg.get("result", {})
        raise ErrorBidi(f"{metodo}: sin respuesta")

    def cerrar(self) -> None:
        # Importante: Firefox solo admite **una** sesión BiDi por instancia. Si
        # se cierra el socket sin `session.end`, la sesión queda colgada y la
        # siguiente conexión recibe "session not created" para siempre.
        try:
            self.cmd("session.end", timeout=5)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.ws.close()
        except Exception:  # noqa: BLE001
            pass


# -------------------------------------------------------------- page y locator
class Locator:
    """Selectores resueltos con `script.evaluate`; sin motor de selectores."""

    def __init__(self, page: "Page", selector: str):
        self.page = page
        self.selector = selector

    def _contar(self) -> int:
        return int(self.page.evaluate(
            "(s) => document.querySelectorAll(s).length", self.selector) or 0)

    def count(self) -> int:
        return self._contar()

    def first(self) -> "Elemento":
        return Elemento(self.page, self.selector, 0)

    def nth(self, i: int) -> "Elemento":
        return Elemento(self.page, self.selector, i)

    def all(self) -> list["Elemento"]:
        return [Elemento(self.page, self.selector, i)
                for i in range(self._contar())]


class Elemento:
    def __init__(self, page: "Page", selector: str, indice: int):
        self.page = page
        self.selector = selector
        self.indice = indice

    def _js(self, cuerpo: str, *args) -> object:
        """Ejecuta `cuerpo` sobre el elemento n-ésimo que casa con el selector."""
        return self.page.evaluate(
            """([s, i, cuerpo]) => {
                const el = document.querySelectorAll(s)[i];
                if (!el) return null;
                return (new Function('el', 'return ' + cuerpo))(el);
            }""",
            [self.selector, self.indice, cuerpo])

    def is_visible(self) -> bool:
        return bool(self._js("!!(el.offsetParent !== null || el.getClientRects().length)"))

    def inner_text(self) -> str:
        return (self._js("(el.innerText || '').trim()") or "")

    def get_attribute(self, nombre: str) -> str | None:
        return self._js(f"el.getAttribute({json.dumps(nombre)})")

    def click(self) -> None:
        # Clic por JS: el juego engancha listeners en el DOM, así que
        # `el.click()` dispara los handlers igual que un clic real. Es más
        # fiable que sintetizar el puntero para botones normales.
        ok = self._js("(() => { el.click(); return true; })()")
        if not ok:
            raise ErrorBidi(f"no se pudo pulsar {self.selector}[{self.indice}]")

    def bounding_box(self) -> dict | None:
        return self._js(
            "(() => { const r = el.getBoundingClientRect();"
            " return r.width ? {x: r.x + r.width/2, y: r.y + r.height/2,"
            " w: r.width, h: r.height} : null; })()")


class Teclado:
    def __init__(self, page: "Page"):
        self.page = page

    def press(self, tecla: str) -> None:
        self.page.acciones_teclado(tecla)


class Raton:
    def __init__(self, page: "Page"):
        self.page = page

    def down(self) -> None:
        self.page._raton("down")

    def up(self) -> None:
        self.page._raton("up")

    def move(self, x: float, y: float) -> None:
        self.page._raton("move", x, y)


class Page:
    """Implementación de `Page` sobre BiDi, con la interfaz que usa el bot."""

    def __init__(self, sesion: Sesion, contexto: str, url: str = URL_JUEGO):
        self.s = sesion
        self.contexto = contexto
        self.keyboard = Teclado(self)
        self.mouse = Raton(self)
        self.url_actual = url
        # El bot fija timeouts cortos; aquí solo se registran, porque BiDi
        # espera de forma distinta.
        self._timeout = 30_000

    def _como_expresion(self, script: str, arg) -> str:
        """Convierte el script del bot en algo invocable dentro de `await`.

        El bot escribe siempre una función (`"() => ..."`, `"async () => ..."`),
        porque así lo espera la API de Playwright. Aquí hay que distinguir una
        función de una expresión normal e invocarla solo en el primer caso.
        """
        s = (script or "").strip()
        es_funcion = bool(re.match(r"^(async\s+)?(function\b|\(|[A-Za-z_$][\w$]*\s*=>)",
                                   s))
        if es_funcion:
            return (f"({s})({json.dumps(arg)})" if arg is not None else f"({s})()")
        if arg is not None:
            return f"({s})({json.dumps(arg)})"
        return f"({s})"

    # ---- evaluate: el corazón del bot
    def evaluate(self, script: str, arg=None):
        """Ejecuta JS en la página y devuelve el valor como Python.

        Ojo con el envoltorio, y son tres trampas encadenadas:

        1. Playwright **llama** a la función que se le pasa; BiDi no. El bot
           escribe `"() => document.querySelector(...)"` y aquí hay que
           invocarla, o `JSON.stringify` de una función da `undefined` y el
           resultado llega vacío. Solo las pruebas que usaban IIFE pasaban,
           y por eso el fallo no se veía.
        2. BiDi **no** devuelve JSON plano, sino un "valor remoto": un objeto
           llega como `{type:'object', value:[[clave, valorRemoto], ...]}`.
           Todo pasa por `JSON.stringify` y se parsea aquí.
        3. `JSON.stringify` de una promesa devuelve `undefined`, así que el
           `await` va **dentro** del envoltorio.
        """
        llamada = self._como_expresion(script, arg)
        expr = "(async () => JSON.stringify(await " + llamada + "))()"
        res = self.s.cmd("script.evaluate", {
            "expression": expr,
            "target": {"context": self.contexto},
            "awaitPromise": True,
        })
        crudo = res.get("result", {}).get("value")
        if crudo is None:
            return None
        try:
            return json.loads(crudo)
        except (TypeError, ValueError):
            # `JSON.stringify(undefined)` no es JSON válido: es un undefined.
            return None

    def set_default_timeout(self, ms: int) -> None:
        self._timeout = ms

    def wait_for_timeout(self, ms: int) -> None:
        time.sleep(ms / 1000.0)

    # ---- navegación
    def goto(self, url: str, wait_until: str = "domcontentloaded",
             timeout: int = 60_000) -> None:
        self.s.cmd("browsingContext.navigate",
                   {"context": self.contexto, "url": url, "wait": "complete"})
        self.url_actual = url

    @property
    def url(self) -> str:
        return self.url_actual

    # ---- selectores
    def locator(self, selector: str) -> Locator:
        return Locator(self, selector)

    def get_by_text(self, texto: str, exact: bool = False) -> Locator:
        return self.locator(
            f"//*[contains(text(), {json.dumps(texto)})]")

    def wait_for_selector(self, selector: str, timeout: int = 30_000,
                          state: str = "attached") -> "Elemento | None":
        limite = time.time() + timeout / 1000.0
        while time.time() < limite:
            loc = Locator(self, selector)
            if loc.count() > 0:
                return loc.first()
            time.sleep(0.15)
        return None

    # ---- acciones de entrada
    def acciones_teclado(self, tecla: str) -> None:
        """Pulsa y suelta una tecla.

        Hay que traducir el nombre a punto de código: el bot pide "Space" y
        "Enter" (la API de Playwright) y BiDi responde "invalid argument" si le
        llega el nombre tal cual.
        """
        valor = tecla_bidi(tecla)
        self.s.cmd("input.performActions", {
            "context": self.contexto,
            "actions": [{
                "type": "key",
                "id": "teclado",
                "actions": [
                    {"type": "keyDown", "value": valor},
                    {"type": "keyUp", "value": valor},
                ],
            }],
        })

    def type(self, texto: str, delay: int = 0) -> None:
        for ch in texto:
            self.acciones_teclado(ch)

    def _raton(self, accion: str, x: float = 0, y: float = 0) -> None:
        base = {"type": "pointer", "id": "raton",
                "parameters": {"pointerType": "mouse"}}
        paso = {accion: x, "y": y} if accion == "move" else {accion: 0}
        self.s.cmd("input.performActions", {
            "context": self.contexto,
            "actions": [dict(base, actions=[paso])],
        })

    def clic_real(self, x: float, y: float, botones: int = 1) -> None:
        """Clic de verdad, por coordenadas.

        Hace falta porque el juego **ignora los eventos sintéticos**: tanto un
        `element.click()` desde JavaScript como la pulsación de una tecla sin
        foco dejan la pantalla igual. Con `pointerMove` + `pointerDown` +
        `pointerUp` llega un evento de puntero de verdad, que es lo que el juego
        escucha. El botón va en el campo `button`, que es un número, no un
        objeto.
        """
        self.s.cmd("input.performActions", {
            "context": self.contexto,
            "actions": [{
                "type": "pointer", "id": "raton",
                "parameters": {"pointerType": "mouse"},
                "actions": [
                    {"type": "pointerMove", "x": int(x), "y": int(y)},
                    {"type": "pointerDown", "button": botones},
                    {"type": "pause", "duration": 40},
                    {"type": "pointerUp", "button": botones},
                ],
            }],
        })

    def clic_selector(self, selector: str) -> bool:
        """Clic real sobre el centro del primer elemento que case."""
        caja = self.evaluate(
            """(s) => {
                const el = document.querySelector(s);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height) return null;
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }""", selector)
        if not caja:
            return False
        self.clic_real(caja["x"], caja["y"])
        return True


# ------------------------------------------------------------------ contexto
class ContextRemoto:
    """Aparenta un `BrowserContext` de Playwright, que es lo que pide `abrir`."""

    def __init__(self, page: Page, sesion: Sesion, proceso):
        self.page = page
        self._sesion = sesion
        self._proceso = proceso
        self._navegador_propio = None
        self.pages = [page]

    def new_page(self) -> Page:
        return self.page

    def route(self, patron: str, manejador) -> None:
        """No-op declarado: BiDi no expone filtrado de peticiones equivalente.

        Se documenta en vez de fingir que filtra. Pierde el bloqueo de anuncios
        y analítica, no la partida.
        """

    def on(self, evento: str, manejador) -> None:
        pass

    def close(self) -> None:
        self._sesion.cerrar()
        # El Firefox del usuario **no** se cierra: es su navegador. Solo se
        # cierra si lo arrancó esta función.

    def _cerrar_proceso(self) -> None:
        if self._proceso and self._proceso.poll() is None:
            self._proceso.terminate()


def abrir_remoto(puerto: int = 9222, perfil: str | Path | None = None,
                 headless: bool = False, url: str = URL_JUEGO) -> tuple:
    """Abre (o se conecta a) tu Firefox y devuelve `(page, context, None)`.

    `perfil` es la ruta de tu perfil de Firefox, para jugar con **tu** sesión y
    no con un perfil desechable. Ojo: Firefox ignora los flags si ya está
    corriendo, así que hay que cerrarlo antes (si no, se conecta al que ya
    esté escuchando en el puerto).

    El tercer valor es `None` a propósito: no hay Playwright detrás, así que
    quien llama no debe llamar a `pw.stop()`.
    """
    proceso = lanzar_firefox(puerto=puerto, perfil=perfil, headless=headless)
    sesion = Sesion(url_bidi(puerto))
    # `session.new` es lo que crea la sesión BiDi; sin ella todo lo demás
    # responde "invalid session id". Las capacidades vacías son lo que acepta
    # Firefox sin preguntar nada.
    sesion.cmd("session.new", {"capabilities": {"alwaysMatch": {}}})
    # Pestaña nueva en vez de reutilizar la que hay: con un perfil de verdad el
    # primer contexto que devuelve `getTree` no siempre es una pestaña
    # navegable, y `navigate` sobre él responde "unknown error".
    contexto = sesion.cmd("browsingContext.create", {"type": "tab"})["context"]
    # Sin activar la pestaña, el foco se queda en la anterior y **las teclas no
    # llegan**: el bot va casi todo por atajos de teclado (`data-shortcut`), así
    # que sin esto se quedaba pulsando botones que no se enteraban.
    try:
        sesion.cmd("browsingContext.activate", {"context": contexto})
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: no se pudo activar la pestaña: {exc}")
    page = Page(sesion, contexto, url)
    page.goto(url)
    page.wait_for_timeout(2500)
    ctx = ContextRemoto(page, sesion, proceso)
    # Se devuelve un `Juego` igual que `navegador.abrir`, para que el bot no
    # sepa cual de los dos motores esta detrás: solo usa `page`.
    import navegador as _nb
    return _nb.Juego(page), ctx, None

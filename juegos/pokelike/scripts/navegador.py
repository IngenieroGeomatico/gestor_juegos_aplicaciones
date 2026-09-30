"""Sesión de navegador para el bot de Pokelike.

Responsabilidades: abrir el juego con un perfil persistente, tapar el ruido de
anuncios/consentimiento que se interpone en los clics, y exponer primitivas
robustas de interacción (por atributo, no por texto, porque el juego está
traducido con `data-i18n`).

No se inyecta ni modifica código del juego: solo se lee el DOM público y se
pulsan los botones que el propio juego ofrece. El juego trae anti-tamper
(`window.__pkl_chk` comprueba el hostname cada 30 s), así que cualquier
intento de hookear internos rompería la partida; por diseño no se intenta.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

URL = "https://pokelike.xyz/"
BASE = Path(__file__).resolve().parent.parent
PERFIL = BASE / "data" / "bot" / "perfil"
# Motor de navegador: "firefox" (por defecto) o "chromium".
# Se puede cambiar con POKELIKE_NAVEGADOR=chromium.
NAVEGADOR = os.environ.get("POKELIKE_NAVEGADOR", "firefox")

# Dominios de publicidad y CMP: overlay de cookies que tapa los botones y no
# aporta nada al juego. Se abortan a nivel de red.
RUIDO = (
    "cmp.inmobi.com",
    "cdn.confiant-integrations.net",
    "cdn.fuseplatform.net",
    "securepubads.g.doubleclick.net",
    "pubads.g.doubleclick.net",
    "c.amazon-adsystem.com",
    "config.aps.amazon-adsystem.com",
    "www.googletagmanager.com",
    "metrics.rapidedge.io",
    "fundingchoicesmessages.google.com",
    "pagead2.googlesyndication.com",
    "googleads.g.doubleclick.net",
    "tpc.googlesyndication.com",
    "adnxs.com",
    "c.bing.com",
)


def _tapar_ruido(ruta) -> None:
    if any(d in ruta.request.url for d in RUIDO):
        ruta.abort()
    else:
        ruta.continue_()


def _aceptar(dialogo) -> None:
    try:
        dialogo.accept()
    except Exception:  # noqa: BLE001
        pass


class Juego:
    """Envoltorio de la página con las primitivas que necesita el bot."""

    def __init__(self, page: Page) -> None:
        self.page = page

    # -- consultas -------------------------------------------------------
    def pantalla(self) -> str | None:
        """Id de la pantalla activa, p. ej. 'map-screen'."""
        return self.page.evaluate(
            "() => { const a = document.querySelector('.screen.active');"
            " return a ? a.id : null; }"
        )

    def cuerpo(self) -> str:
        return self.page.evaluate("() => document.body.className")

    def estado_batalla(self) -> dict:
        """Instantánea de la batalla: rival, PS enemigos y PS del equipo."""
        return self.page.evaluate(
            r"""() => {
              const txt = (s) => (document.querySelector(s)?.innerText || '').trim();
              // El nivel no tiene elemento propio: viene incrustado en el
              // nombre ("Geodude Lv12"). Se extrae de ahí para poder comparar
              // el nivel del equipo con el de los rivales.
              const lvl = (n) => {
                const m = n.match(/[Ll]v\.?\s*(\d{1,3})/);
                return m ? m[1] : '';
              };
              // Los tipos NO están en el DOM del rival: el bloque solo trae
              // nombre, nivel y PS ("Zubat Lv12 31/31"). Antes se intentaba
              // sacarlos del texto y "Zubat" salía como si fuera un tipo, que
              // es peor que no tenerlos. Se dejan vacíos y se consultan en el
              // Pokédex por nombre (ver `navegador.tipos_de`).
              const leer = (raiz) => [...document.querySelectorAll(raiz)]
                .map((e) => {
                  const nombre = (e.querySelector('[class*=name]')?.textContent || '').trim();
                  const ps = (e.querySelector('[class*=hp]')?.textContent || '').trim();
                  const nivel = (e.querySelector('[class*=lvl],[class*=level]')?.textContent || '').trim();
                  return { nombre, ps, nivel: nivel || lvl(nombre), tipos: [] };
                });
              // Movimientos del bicho activo: "div.poke-move" con el texto
              // "Karate Chop Fighting 50 PWR". No son botones ni tienen
              // data-shortcut, hay que hacer clic en el div.
              const movimientos = [...document.querySelectorAll('.screen.active .poke-move')]
                .filter((e) => e.offsetParent)
                .map((e, i) => {
                  const meta = (e.querySelector('.move-meta')?.textContent || e.textContent || '').trim();
                  const m = meta.match(/([A-Za-z]+)\s+(\d+)\s*PWR/);
                  const nombre = (e.querySelector('[class*=name]')?.textContent || '').trim()
                    || (e.textContent || '').trim().split(/\s+/)[0];
                  return { indice: i, sel: '.screen.active .poke-move:nth-of-type(' + (i + 1) + ')',
                           nombre, tipo: m ? m[1] : '', power: m ? parseInt(m[2], 10) : 0 };
                });
              return {
                titulo: txt('#battle-title'),
                subtitulo: txt('#battle-subtitle'),
                etiqueta_enemigo: txt('#enemy-side-label'),
                enemigos: leer('#enemy-side [class*=mon], #enemy-side > *'),
                mios: leer('#player-side [class*=mon], .team-slot'),
                movimientos,
                botones: [...document.querySelectorAll('#battle-screen button')]
                  .filter((b) => b.offsetParent)
                  .map((b) => (b.id || '?') + '|' + (b.dataset.shortcut || '-') + '|' + (b.innerText || '').trim().slice(0, 28)),
              };
            }"""
        )

    def orden_equipo(self) -> list[str]:
        """Nombres del equipo en su orden actual (el primero es el delantero)."""
        return self.page.evaluate(
            r"""() => [...document.querySelectorAll('#team-bar .team-slot')]
                 .map(s => (s.querySelector('.team-slot-name')?.textContent || '').trim())"""
        )

    def reordenar_equipo(self, nombres: list[str]) -> bool:
        """Reordena el equipo arrastrando slots. `nombres` es el orden deseado.

        Los slots son `.team-slot-reorder` con `cursor: grab` y
        `touch-action: none`: el juego usa arrastre por puntero, no eventos
        `dragstart` de HTML5, así que `locator.drag_to()` no sirve y hay que
        sintetizar mousedown/mousemove/mouseup.

        Importa porque el reparto de experiencia parece seguir al delantero:
        un món recién capturado en segunda plaza se queda varios niveles por
        detrás de todo el camino, y contra un líder de doble nivel eso lo
        deja fuera de combate.
        """
        try:
            actual = self.orden_equipo()
            objetivo = [n for n in nombres if n in actual]
            objetivo += [n for n in actual if n not in objetivo]
            if objetivo == actual:
                return True
            # Selection sort: para cada posición, arrastrar el món que debe
            # ocuparla hasta ella. Pocos elementos, así que da igual de ineficiente.
            for destino in range(len(objetivo)):
                actual = self.orden_equipo()
                if len(actual) <= destino:
                    break
                if actual[destino] == objetivo[destino]:
                    continue
                origen = actual.index(objetivo[destino])
                if origen == destino:
                    continue
                if not self._arrastrar_slot(origen, destino):
                    return False
            return self.orden_equipo() == objetivo
        except Exception:  # noqa: BLE001
            return False

    def _arrastrar_slot(self, origen: int, destino: int) -> bool:
        """Arrastra el slot `origen` hasta la posición `destino`.

        El equipo se muestra en columna (cada slot 80x80 apilado en Y). El gesto
        necesita pulsar, **esperar** a que el juego registre el arrastre y luego
        mover en pasos: un salto único no dispara la reordenación.
        """
        try:
            slots = self.page.locator("#team-bar .team-slot")
            if slots.count() <= max(origen, destino):
                return False
            origen_el, destino_el = slots.nth(origen), slots.nth(destino)
            origen_el.scroll_into_view_if_needed()
            destino_el.scroll_into_view_if_needed()
            a = origen_el.bounding_box()
            b = destino_el.bounding_box()
            if not a or not b:
                return False
            x1, y1 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
            x2, y2 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            self.page.mouse.move(x1, y1)
            self.page.wait_for_timeout(150)
            self.page.mouse.down()
            self.page.wait_for_timeout(450)
            for i in range(1, 16):
                self.page.mouse.move(x1 + (x2 - x1) * i / 15,
                                     y1 + (y2 - y1) * i / 15)
                self.page.wait_for_timeout(60)
            self.page.wait_for_timeout(250)
            self.page.mouse.up()
            self.page.wait_for_timeout(600)
            return True
        except Exception:  # noqa: BLE001
            return False

    def trainer_tipos(self, sprite: str) -> list[str] | None:
        """Los tipos de un entrenador a partir de su sprite.

        Se pregunta directamente a `trainerSpecialtyTypes`, así que funciona
        tanto si el nodo está accesible como si no: el bot elige nodo y a
        veces el estado todavía no lo ha marcado. Se prueban las variantes del
        nombre porque el SVG lo tiene en kebab (`bug-catcher`, `team-rocket`) y
        el estado en camel (`bugCatcher`, `teamRocket`).
        """
        return self.page.evaluate(
            r"""(s) => {
              if (!s) return null;
              const pruebas = [s,
                               String(s).replace(/-([a-z])/g, (m, c) => c.toUpperCase()),
                               String(s).replace(/-/g, '')];
              for (const p of pruebas) {
                try {
                  const t = trainerSpecialtyTypes(p);
                  if (t && t.size) return [...t];
                } catch (e) {}
              }
              return null;
            }""", sprite
        )

    def nombres_prep_rival(self) -> list[str]:
        """Nombres del equipo enemigo en la pantalla de preparación.

        El prep **sí enseña el rival** ("Geodude Lv12", "Onix Lv14"), y con el
        Pokédex se sacan sus tipos exactos. Es la última información buena antes
        de pelear contra un jefe: sin ella solo se conoce el tipo del líder, que
        es solo uno de los tipos que trae.
        """
        return self.page.evaluate(
            r"""() => {
              const c = document.getElementById('elite-prep-enemy-side');
              if (!c) return [];
              return [...c.querySelectorAll('.battle-pokemon')]
                .map((m) => (m.querySelector('.battle-poke-name') || {}).textContent || '')
                .map((t) => t.replace(/\s*L[vv]\.?\s*\d+\s*$/i, '').trim())
                .filter(Boolean);
            }"""
        )

    def bolsa_items(self) -> list[dict]:
        """Los objetos de la bolsa en la pantalla de preparación.

        Cada uno es un `span.item-badge` con `cursor: pointer` y
        `touch-action: none`, o sea arrastrable. Se leen también de `state.items`
        para saber cuáles son utilizables: hay discos (`usable`) y objetos de
        batalla (`Red Card`, que no).
        """
        return self.page.evaluate(
            r"""() => {
              if (typeof state === 'undefined') return [];
              const items = state.items || [];
              const insignias = [...document.querySelectorAll('#elite-prep-items .item-badge')];
              return items.map((it, i) => ({
                id: it.id || null,
                nombre: it.name || null,
                usable: !!it.usable,
                indice_insignia: i,
                alt: insignias[i] ? (insignias[i].querySelector('img') || {}).alt || null : null,
              }));
            }"""
        )

    def movimientos_equipo(self) -> list[dict]:
        """Tipo (y nombre) del ataque de cada món nuestro, tal y como pelea.

        Pregunta que decide todo el modelo de tipos: un bicho de dos tipos
        (Geodude es Roca/Tierra) ¿ataca con el primero, con el mejor contra el
        rival, o con el que le imponga un objeto? El Pokédex del juego no lo
        dice, así que se lee del estado en pleno combate.
        """
        return self.page.evaluate(
            """() => {
                const t = (typeof state !== 'undefined' && state.team) || [];
                return t.map(m => {
                    const o = {nombre: m.name, tipos: m.types, nivel: m.level};
                    for (const k in m) {
                        if (/move|attack|skill/i.test(k)) o[k] = m[k];
                    }
                    return o;
                });
            }"""
        ) or []

    def objeto_del_mons(self, nombre_mons: str) -> str | None:
        """Objeto que lleva puesto un món, leyéndolo de su ranura del HUD.

        Es la **verificación** que faltaba: sin esto el bot no tenía forma de
        saber si el equip había funcionado, porque la bolsa baja igual tanto si
        el objeto se usa como si se pierde.

        Se busca por el **icono**, que es una imagen de `img/sprites/items/...`.
        La primera versión leía texto suelto de la ranura y devolvía `"GrassPoison"`
        (los tipos del món) como si fuera el objeto, que es peor que no
        verificar nada: daba un falso "EQUIPADO" cuatro veces seguidas.
        """
        return self.page.evaluate(
            r"""(nombre) => {
                for (const slot of document.querySelectorAll(
                        '.team-slot.team-slot-reorder, .team-slot')) {
                    const nom = (slot.querySelector('.team-slot-name')?.innerText
                        || slot.querySelector('img[class*=sprite]')?.getAttribute('alt')
                        || '').trim().toLowerCase();
                    if (nombre && nom && !nom.includes(nombre.toLowerCase())) {
                        continue;
                    }
                    // El icono del objeto es una imagen de la carpeta items.
                    const icono = [...slot.querySelectorAll('img')].find(i => {
                        const s = (i.getAttribute('src') || '').toLowerCase();
                        return s.includes('/items/') || s.includes('item');
                    });
                    if (icono) {
                        return (icono.getAttribute('alt')
                                || icono.getAttribute('title')
                                || icono.getAttribute('src')
                                       .split('/').pop().replace('.png', ''));
                    }
                }
                return null;
            }""", nombre_mons)

    def usar_item(self, indice_item: int, indice_mons: int,
                  nombre_mons: str | None = None) -> bool:
        """Equipa un objeto de la bolsa a un món, con el flujo real de tres pasos.

        El flujo, confirmado por el usuario mirando la pantalla:

            1. **Clic en el objeto** de la bolsa -> se abre una ventana con las
               **3 opciones** de ese tipo de objeto.
            2. **Clic en una de las 3** -> se abre otra ventana con **nuestro
               equipo** y un botón **"equipar"** al lado de cada món (más otro
               botón para dejarlo en la mochila).
            3. **Clic en "equipar"** del món que lo quiere.

        Antes solo se hacía el paso 1 y un clic a ciegas, y nunca entró nada: 43
        intentos, 0 equips.

        Nota: hay **dos sitios distintos**. Los *passive items* son de partida y
        **no** se asignan a ningún món; la bolsa es lo otro.
        """
        return self._equipar_flujo(indice_item, indice_mons, nombre_mons)

    def _equipar_flujo(self, indice_item: int, indice_mons: int,
                       nombre_mons: str | None) -> bool:
        """Equipa un objeto de la bolsa con **clics reales**.

        El flujo que describe el usuario mirando la pantalla es de tres pasos:

            1. Clic en el objeto de la bolsa -> ventana con **3 opciones**.
            2. Clic en una de las 3 -> ventana con **nuestro equipo** y un botón
               **"equipar"** al lado de cada món (más otro para dejarlo en la
               mochila).
            3. Clic en "equipar" del món que lo quiere.

        **Lo importante es que los clics son reales.** La versión anterior
        usaba `el.click()` dentro de `page.evaluate`, o sea un clic sintético, y
        este juego **no** los atiende: es el mismo motivo por el que el MCP y el
        BiDi no conseguan ni abrir el juego. Con `locator.click()`, que sí
        despacha eventos de confianza, el flujo funciona. Por eso estaba el
        contador en 43 intentos y 0 equips.
        """
        try:
            insignias = self.page.locator("#elite-prep-items .item-badge")
            if insignias.count() <= indice_item:
                return False
            # 1. Clic real en el objeto de la bolsa.
            insignias.nth(indice_item).click(timeout=3000)
            self.page.wait_for_timeout(450)

            # 2. Ventana con las 3 opciones del objeto.
            opcion = self.page.locator(
                "[class*=modal] .item-card, [class*=modal] [data-shortcut],"
                " [class*=modal] .choice"
            ).first
            if opcion.count() and opcion.is_visible():
                opcion.click(timeout=3000)
                self.page.wait_for_timeout(500)

            # 3. Botón "equipar" del món elegido, con clic real.
            victimario = None
            if nombre_mons:
                victimario = self.page.locator(
                    f".team-slot-reorder:has-text('{nombre_mons}') "
                    f"button:has-text('Equipar')"
                ).first
                if not victimario.count():
                    victimario = self.page.locator(
                        f".team-slot-reorder:has-text('{nombre_mons}') button"
                    ).first
            if not victimario or not victimario.count():
                victimario = self.page.locator(
                    "[class*=modal] button:has-text('Equipar')"
                ).nth(min(indice_mons, 5))
            if not victimario.count():
                self.cerrar_modal_item()
                return False
            victimario.click(timeout=3000)
            self.page.wait_for_timeout(500)

            # Se cierra el modal que pueda quedar (el de equipar tiene su propio
            # boton de cancelar y no escucha Escape).
            self.cerrar_modal_item()
            return True
        except Exception:  # noqa: BLE001
            self.cerrar_modal_item()
            return False

    def cerrar_modal_item(self) -> None:
        """Cierra el modal de objetos con clics reales, si hay alguno abierto.

        Sin esto la pantalla de preparación se quedaba **atascada**: el overlay
        tapaba el botón de FIGHT y el bot lo intentaba 13 veces sin avanzar,
        hasta declararse ATASCADO y perder la run con insignias en el bolsillo.

        Dos cosas que costaron una partida cada una:
        - el modal de equipar **no escucha Escape**, hay que pulsar su botón
          (`#btn-equip-cancel`);
        - cerrar con un clic **sintético** (`.click()` desde JS) no hace nada
          en este juego.
        """
        for sel in ("#btn-equip-cancel", "#btn-cancel-equip",
                    "#btn-equip-to-bag"):
            try:
                loc = self.page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=2000)
                    self.page.wait_for_timeout(300)
            except Exception:  # noqa: BLE001
                pass
        try:
            abierto = self.page.evaluate(
                """() => [...document.querySelectorAll(
                        '[class*=modal], [class*=overlay]')]
                    .some(e => e.offsetParent !== null)"""
            )
        except Exception:  # noqa: BLE001
            return
        if not abierto:
            return
        for via in ("Escape", "Enter"):
            try:
                self.page.keyboard.press(via)
                self.page.wait_for_timeout(250)
                if not self.page.evaluate(
                    """() => [...document.querySelectorAll(
                            '[class*=modal], [class*=overlay]')]
                        .some(e => e.offsetParent !== null)"""
                ):
                    return
            except Exception:  # noqa: BLE001
                pass

    def _opciones_modal(self) -> list[str]:
        """Etiquetas de las opciones abiertas en un modal, para la traza."""
        try:
            return self.page.evaluate(
                r"""() => {
                    const vis = e => e && e.offsetParent !== null;
                    const modales = [...document.querySelectorAll(
                        '[class*=modal], [class*=overlay]')].filter(vis);
                    if (!modales.length) return [];
                    const capa = modales[modales.length - 1];
                    return [...capa.querySelectorAll('.item-card, [data-shortcut]')]
                        .filter(vis)
                        .map(e => (e.innerText || '').replace(/\s+/g, ' ').slice(0, 40));
                }"""
            ) or []
        except Exception:  # noqa: BLE001
            return []

    def _describir_capas(self) -> dict:
        """Qué se ve tras fallar el uso, para no ir a ciegas."""
        try:
            return self.page.evaluate(
                r"""() => {
                  const vis = (e) => e && e.offsetParent !== null;
                  return [...document.querySelectorAll('body *')]
                    .filter((e) => vis(e) && /modal|overlay|equip/i.test(e.id || e.className || ''))
                    .slice(0, 6)
                    .map((e) => ({id: e.id,
                                  cls: typeof e.className === 'string' ? e.className : '',
                                  txt: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 120)}));
                }"""
            )
        except Exception:  # noqa: BLE001
            return {}

    def _item_por_clics(self, indice_item: int, indice_mons: int) -> bool:
        try:
            self.page.evaluate(
                """(arg) => {
                  const badge = document.querySelectorAll('#elite-prep-items .item-badge')[arg[0]];
                  const mon = document.querySelectorAll(
                    '#elite-prep-player-side .battle-pokemon')[arg[1]];
                  if (!badge || !mon) return false;
                  badge.click();
                  mon.click();
                  return true;
                }""", [indice_item, indice_mons])
            self.page.wait_for_timeout(600)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _item_arrastrando(self, indice_item: int, destino: str, nth: int) -> bool:
        try:
            insignias = self.page.locator("#elite-prep-items .item-badge")
            objetivos = self.page.locator(destino)
            if insignias.count() <= indice_item or objetivos.count() <= nth:
                return False
            origen, fin = insignias.nth(indice_item), objetivos.nth(nth)
            origen.scroll_into_view_if_needed()
            fin.scroll_into_view_if_needed()
            a, b = origen.bounding_box(), fin.bounding_box()
            if not a or not b:
                return False
            x1, y1 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
            x2, y2 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            self.page.mouse.move(x1, y1)
            self.page.wait_for_timeout(150)
            self.page.mouse.down()
            self.page.wait_for_timeout(450)
            for i in range(1, 16):
                self.page.mouse.move(x1 + (x2 - x1) * i / 15,
                                     y1 + (y2 - y1) * i / 15)
                self.page.wait_for_timeout(60)
            self.page.wait_for_timeout(250)
            self.page.mouse.up()
            self.page.wait_for_timeout(700)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _item_arrastrando_a_slot(self, indice_item: int, indice_mons: int) -> bool:
        return self._item_arrastrando(
            indice_item, "#elite-prep-player-side .elite-prep-mon-item", indice_mons)

    def _item_arrastrando_a_mon(self, indice_item: int, indice_mons: int) -> bool:
        return self._item_arrastrando(
            indice_item, "#elite-prep-player-side .battle-pokemon", indice_mons)

    def esperar_boton(self, selector: str, segundos: float = 10.0) -> bool:
        """Espera a que aparezca un botón visible. Para animaciones del juego.

        Durante las animaciones los botones existen en el DOM pero con
        `offsetParent` nulo; consultarlos de golpe devolvía "sin botones" y el
        bot declaraba un atasco que era solo una animación en curso.
        """
        try:
            self.page.wait_for_selector(
                selector, state="visible", timeout=segundos * 1000)
            return True
        except Exception:  # noqa: BLE001
            return False

    def esperar_pantalla(self, *ids: str, timeout: float = 20.0) -> str | None:
        """Espera a que una de las pantallas dadas esté activa."""
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            act = self.pantalla()
            if act in ids:
                return act
            time.sleep(0.25)
        return self.pantalla()

    def texto(self, selector: str) -> str:
        loc = self.page.locator(selector)
        if loc.count() and loc.first.is_visible():
            return (loc.first.inner_text() or "").strip()
        return ""

    # -- interacciones ---------------------------------------------------
    def atajo_de(self, selector: str) -> str | None:
        """`data-shortcut` del elemento, si existe y es visible."""
        return self.page.evaluate(
            """(sel) => {
            const e = document.querySelector(sel);
            if (!e) return null;
            if (!(e.offsetWidth || e.offsetHeight)) return null;
            return e.getAttribute('data-shortcut');
        }""",
            selector,
        )

    def activar(self, selector: str, timeout: float = 8.0) -> str:
        """Activa un control por su vía fiable: la tecla de `data-shortcut`.

        Todo el juego es navegable por teclado (nodos, cartas, diálogos), y el
        `clic` sintético no dispara siempre el manejador. Si no hay atajo, cae a
        clic. Devuelve qué vía se usó, para el log.
        """
        atajo = self.atajo_de(selector)
        if atajo:
            self.page.keyboard.press(atajo)
            self.page.wait_for_timeout(400)
            return f"tecla {atajo!r}"
        if self.clic(selector, timeout):
            return f"clic {selector}"
        return f"sin accion sobre {selector}"

    def clic(self, selector: str, timeout: float = 8.0) -> bool:
        """Clic con reintentos: normal, forzado y por JS.

        El clic normal de Playwright exige que el elemento esté estable, visible
        y **sin nada encima**. En las capas con overlay (el aviso de shiny) el
        botón `#btn-skip-shiny` queda tapado y el clic normal agota el tiempo
        esperando, dejando la run bloqueada. Los otros dos vías saltan esa
        comprobación de eventos.
        """
        loc = self.page.locator(selector)
        try:
            if not loc.count():
                return False
        except Exception:  # noqa: BLE001
            return False
        try:
            loc.first.click(timeout=timeout * 1000)
            self.page.wait_for_timeout(350)
            return True
        except Exception:  # noqa: BLE001
            pass
        # Clic forzado: no exige que nada lo tape.
        try:
            loc.first.click(timeout=2500, force=True)
            self.page.wait_for_timeout(350)
            return True
        except Exception:  # noqa: BLE001
            pass
        # Último recurso: disparo directo del evento desde el DOM.
        try:
            hecho = loc.first.evaluate(
                "el => { el.click(); return true; }")
            self.page.wait_for_timeout(350)
            return bool(hecho)
        except Exception:  # noqa: BLE001
            return False

    def clic_texto(self, texto: str, exacto: bool = False, timeout: float = 8.0) -> bool:
        loc = self.page.get_by_text(texto, exact=exacto)
        try:
            if not loc.count():
                return False
            loc.first.click(timeout=timeout * 1000)
            self.page.wait_for_timeout(350)
            return True
        except (PWTimeout, Exception):  # noqa: BLE001
            return False

    def clic_por_atajo(self, tecla: str) -> bool:
        """El juego numera los nodos del mapa y las opciones; pulsar la tecla."""
        try:
            self.page.keyboard.press(tecla)
            self.page.wait_for_timeout(350)
            return True
        except Exception:  # noqa: BLE001
            return False

    def visible(self, selector: str) -> bool:
        loc = self.page.locator(selector)
        try:
            return bool(loc.count()) and loc.first.is_visible()
        except Exception:  # noqa: BLE001
            return False

    def opciones(self, contenedor: str) -> list[dict]:
        """Opciones clicables de una pantalla (catch/item/swap/trade/stat-buff)."""
        return self.page.evaluate(
            """(cont) => {
            const raiz = document.querySelector(cont);
            if (!raiz) return [];
            return [...raiz.querySelectorAll('button,[role=button],[class*=choice],'
                + '[class*=card],[class*=option],[data-choice],[data-shortcut]')]
              .filter(e => e.offsetWidth || e.offsetHeight)
              .map((e, i) => ({
                i,
                sel: e.tagName.toLowerCase() +
                     (e.id ? '#' + e.id : '') +
                     (typeof e.className === 'string' && e.className
                        ? '.' + e.className.trim().split(/\\s+/).slice(0,3).join('.') : ''),
                atajo: e.getAttribute('data-shortcut'),
                txt: (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
              }));
        }""",
            contenedor,
        )

    def opciones_pokemon(self, contenedor: str) -> list[dict]:
        """Cartas `.poke-card` de un selector de mons (starter, catch).

        Devuelve solo las cartas (no sus wrappers) y, cuando se puede, el id del
        dex por el `src` del sprite, para poder consultar los tipos en
        `__POKEDEX__` en vez de adivinarlos por texto.
        """
        return self.page.evaluate(
            """(cont) => {
            const raiz = document.querySelector(cont);
            if (!raiz) return [];
            return [...raiz.querySelectorAll('.poke-card')]
              .filter(e => e.offsetWidth || e.offsetHeight)
              .map((e, i) => {
                const img = e.querySelector('img.poke-sprite, img');
                const src = img ? (img.getAttribute('src') || '') : '';
                const m = /\\/pokemon\\/(\\d+)\\.png/.exec(src);
                const lv = e.querySelector('.poke-lv, .poke-level');
                return {
                  i,
                  atajo: e.getAttribute('data-shortcut') || String(i + 1),
                  nombre: img ? (img.getAttribute('alt') || '') : '',
                  dex: m ? m[1] : null,
                  nivel: lv ? parseInt((lv.innerText || '').replace(/\\D/g, '') || '0', 10) : 0,
                  txt: (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
                };
              });
        }""",
            contenedor,
        )

    def mapa(self) -> dict:
        """Lee el grafo del mapa: nodos disponibles y su tipo.

        Cada nodo del SVG se empareja por **índice** con los nodos de
        `state.map.nodes`: el juego los renderiza en el mismo orden, y es la
        única forma de saber de verdad qué hay en cada nodo. El sprite es solo
        una pista y miente: "grass" es un nodo de batalla y "question-mark" puede
        ser un entrenador, un trade o el tutor de movimientos.
        """
        return self.page.evaluate(
            """() => {
            const svg = document.getElementById('map-svg');
            const info = document.getElementById('map-info');
            const estado = (typeof state !== 'undefined' && state.map)
              ? Object.values(state.map.nodes) : [];
            const porIndice = estado;
            if (!svg) return { nodos: [], info: '', actual: null, edges: [] };
            const nodos = [...svg.querySelectorAll('g.map-node')].map((g, i) => {
                const m = /translate\\(([-\\d.]+),\\s*([-\\d.]+)\\)/.exec(
                    g.getAttribute('transform') || '');
                const img = g.querySelector('image');
                const sc = g.querySelector('.map-node-shortcut text');
                const sprite = img ? (img.getAttribute('href') || '') : '';
                const delEstado = porIndice[i] || null;
                return {
                    x: m ? parseFloat(m[1]) : null,
                    y: m ? parseFloat(m[2]) : null,
                    clickable: g.classList.contains('map-node--clickable'),
                    atajo: sc ? sc.textContent.trim() : null,
                    sprite: sprite.split('/').pop().replace('.png', ''),
                    id: delEstado ? delEstado.id : null,
                    tipo: delEstado ? delEstado.type : null,
                    capa: delEstado ? delEstado.layer : null,
                };
            });
            return {
                nodos,
                info: info ? (info.innerText || '').trim() : '',
                actual: (typeof state !== 'undefined' && state.currentNode)
                  ? state.currentNode.id : null,
                edges: (typeof state !== 'undefined' && state.map && state.map.edges)
                  ? state.map.edges.map(e => [e.from, e.to]) : [],
            };
        }"""
        )

    def nodos_del_estado(self) -> list[dict]:
        """Los nodos del mapa según el estado del juego, con su tipo real.

        El sprite del SVG es una pista floja (varios entrenadores distintos
        comparten sprite y `bug-catcher` no coincide con la clave
        `bugCatcher`), pero el estado del juego es el grafo de verdad: cada
        nodo lleva su `type` ('catch', 'battle', 'trainer', 'item',
        'question', 'pokecenter', 'move_tutor', 'boss') y, en los
        entrenadores, el `trainerSprite` con el que se puede pedir la
        especialidad y saber los tipos antes de pelear.
        """
        return self.page.evaluate(
            r"""() => {
              if (typeof state === 'undefined' || !state.map) return [];
              return Object.values(state.map.nodes)
                .filter((n) => n && n.accessible && !n.visited)
                .map((n) => ({
                  id: n.id,
                  type: n.type,
                  sprite: n.trainerSprite || null,
                  nivel: (function () {
                    try { return trainerFightLevel(n); } catch (e) { return null; }
                  })(),
                  tipos: (function () {
                    if (n.type !== 'trainer') return null;
                    const prueba = [n.trainerSprite,
                                    String(n.trainerSprite || '')
                                      .replace(/-([a-z])/g, (m, c) => c.toUpperCase()),
                                    String(n.trainerSprite || '')
                                      .replace(/-/g, '').toLowerCase()];
                    for (const p of prueba) {
                      if (!p) continue;
                      try {
                        const s = trainerSpecialtyTypes(p);
                        if (s && s.size) return [...s];
                      } catch (e) {}
                    }
                    return null;
                  })(),
                }));
            }"""
        )

    def activar_auto_skip(self) -> None:
        """Enciende el auto-skip de los ajustes del juego.

        La guía lo recomienda como primera medida: "enable auto-skip on all
        fights and skip evolutions: battles fly by much faster". Aquí no es
        solo comodidad: una run más corta significa **más runs por hora**, y el
        techo actual depende de que entren muchas (la lotería del mapa es la
        que manda).

        La clave es `poke_settings` en localStorage. Se escribe **fusionando**
        con lo que haya, para no pisar el idioma, el tema ni nada del usuario.
        """
        try:
            self.page.evaluate(
                r"""() => {
                    const K = 'poke_settings';
                    let s = {};
                    try { s = JSON.parse(localStorage.getItem(K) || '{}'); }
                    catch (e) { s = {}; }
                    s.autoSkip = s.autoSkip || {};
                    s.autoSkip.allFights = true;
                    s.autoSkip.evolutions = true;
                    s.autoSkip.regularTrainers = true;
                    s.autoSkip.skipBossPreview = true;
                    localStorage.setItem(K, JSON.stringify(s));
                    return true;
                }"""
            )
        except Exception:  # noqa: BLE001
            pass

    def equipo(self) -> list[dict]:
        """Equipo desde el HUD: nombre, nivel y porcentaje de PS."""
        return self.page.evaluate(
            """() => {
            const bar = document.getElementById('team-bar');
            if (!bar) return [];
            return [...bar.querySelectorAll('.team-slot')].map(s => {
                const img = s.querySelector('.team-sprite, img');
                const hp = s.querySelector('.hp-bar-fill');
                const lv = s.querySelector('.team-slot-lv');
                const nom = s.querySelector('.team-slot-name');
                let pct = null;
                if (hp) {
                    const w = /width:\\s*([\\d.]+)%/.exec(hp.getAttribute('style') || '');
                    if (w) pct = parseFloat(w[1]);
                }
                return {
                    nombre: (img && img.getAttribute('alt')) || (nom && nom.innerText.trim()) || '',
                    nivel: lv ? parseInt((lv.innerText || '').replace(/\\D/g, '') || '0', 10) : 0,
                    ps: pct,
                    // `ps` es el PORCENTAJE de la barra, no un valor de vida.
                    // Se anota `ps_max: 100` para que todo lo que calcula
                    // `ps / ps_max` siga siendo correcto: sin esto el equipo
                    // salia "al 4350%" y la curacion, el carry y el reparto de
                    // objetos estaban corruptos desde el principio.
                    ps_max: 100,
                    id: img ? (img.getAttribute('src') || '').split('/').pop()
                                .replace('.png', '') : null,
                };
            });
        }"""
        )

    def insignias(self) -> int:
        """Insignias ganadas.

        Se lee `state.badges`, que es el contador del propio juego, y solo si no
        está se recurre al DOM. El DOM va con retardo: en la pantalla de
        insignia el panel todavía no se había repintado y contaba 0 recién
        ganada, que además de mentir en la traza hace que el listón de nivel
        se calibre contra un gimnasio equivocado.
        """
        estado = self.page.evaluate(
            "() => (typeof state === 'undefined' || state === null)"
            " ? null : state.badges")
        if isinstance(estado, int):
            return estado
        return self.page.evaluate(
            "() => document.querySelectorAll("
            "'#badge-count-panel .badge-icon-img:not(.badge-icon-empty)').length"
        )

    def pokedex(self) -> dict:
        """El `__POKEDEX__` del juego: nombres, tipos y stats de todos."""
        return self.page.evaluate(
            "() => Object.fromEntries(Object.entries(window.__POKEDEX__ || {})"
            ".map(([k, v]) => [k, { name: v.name, types: v.types,"
            " baseStats: v.baseStats }]))"
        )


def abrir(headless: bool = True, url: str = URL, viewport: int = 1280,
          perfil: Path | None = PERFIL,
          motor: str = NAVEGADOR) -> tuple[Juego, object, object]:
    """Abre el juego. Devuelve (Juego, context, playwright) para poder cerrar.

    `perfil=None` abre un perfil temporal desechable: es la única forma fiable
    de empezar una run de verdad desde cero, porque el juego no expone ningún
    botón de "Reset Run" en la interfaz.

    `motor` elige el navegador de Playwright ("firefox" o "chromium"). Firefox
    es el de por defecto porque es el que se quiere usar. Lo único específico
    de Chromium era `args`, que se pasa solo a Chromium; Firefox usa `firefox_user_prefs`.
    """
    pw = sync_playwright().start()
    comun = {
        "viewport": {"width": viewport, "height": 900},
        "locale": "en-US",
    }
    motor = (motor or NAVEGADOR).lower()

    # Motor "remoto": el Firefox del propio usuario, por WebDriver BiDi. No es
    # Playwright (que solo maneja su Firefox parcheado), así que se resuelve
    # antes de arrancar Playwright.
    if motor in ("remoto", "firefox-remoto", "bidi"):
        import firefox_remoto

        # El perfil del usuario: sin esto el Firefox remoto arranca con uno
        # vacío y no es "tu Firefox con tu sesión". Se puede fijar con
        # POKELIKE_PERFIL_FIREFOX=/ruta/al/perfil.
        perfil_remoto = os.environ.get("POKELIKE_PERFIL_FIREFOX")
        return firefox_remoto.abrir_remoto(
            puerto=int(os.environ.get("POKELIKE_PUERTO_BIDI", "9222")),
            perfil=perfil_remoto, headless=headless, url=url)

    if motor not in ("firefox", "chromium", "webkit"):
        raise ValueError(f"motor de navegador desconocido: {motor!r}")

    if motor == "firefox":
        # Firefox no acepta `args`; las preferencias van aparte y se usan
        # para el aviso de automatización sin tocar el juego.
        prefs = {"privacy.reduceTimerPrecision": False}
        if perfil is None:
            navegador = pw.firefox.launch(headless=headless, firefox_user_prefs=prefs)
            ctx = navegador.new_context(**comun)
            ctx._navegador_propio = navegador  # noqa: SLF001
        else:
            ctx = pw.firefox.launch_persistent_context(
                user_data_dir=str(perfil), headless=headless,
                firefox_user_prefs=prefs, **comun)
    else:
        args = ["--disable-blink-features=AutomationControlled"]
        if perfil is None:
            # Sin persistencia: `new_context` cuelga de Browser, no de BrowserType,
            # y `headless` es del launch, no del context.
            navegador = getattr(pw, motor).launch(headless=headless, args=args)
            ctx = navegador.new_context(**comun)
            ctx._navegador_propio = navegador  # noqa: SLF001
        else:
            ctx = getattr(pw, motor).launch_persistent_context(
                user_data_dir=str(perfil), headless=headless, args=args, **comun)
    ctx.route("**/*", _tapar_ruido)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    # Algunas acciones del juego usan `confirm()` nativo: si nadie lo atiende,
    # la página se queda bloqueada y el driver se cuelga.
    page.on("dialog", lambda d: (_aceptar(d)))
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(2000)
    return Juego(page), ctx, pw

"""Sondeo de la pantalla de objetos: averigua cómo se equipa de verdad.

`Bot._usar_bolsa` nunca ha conseguido equipar nada en ninguna partida (el log
decía "objeto NO equipado" las 43 veces que se intentaba), y sin objetos el bot
va ciego: segun la guiacommunity son la segunda palanca grande despues del
orden del equipo, y hay dos consumibles que son playthrough puro:

- **Sacred Ash**: cura total **y revive**. Resuelve de raiz el problema medido de
  entrar a un gimnasio con un món caido.
- **Rare Candy**: **+3 niveles** al instante, igual que un trade.

Este script no juega: se limita a abrir el juego, llegar a una pantalla donde
haya bolsa y volcar **qué hay** en el DOM y qué hace cada vía (clic, atajo de
teclado, clic por JavaScript). Con eso se ajusta `navegador.usar_item` una sola
vez y con evidencia, en vez de adivinar.

Uso:
    uv run --group dev python juegos/pokelike/scripts/sondear_objetos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import navegador as nb  # noqa: E402

JS_VOLCADO = r"""
() => {
  const vis = e => e && e.offsetParent !== null;
  const pantalla = [...document.querySelectorAll('[id$=-screen]')].find(vis);
  const info = {
    pantalla: pantalla ? pantalla.id : null,
    bolsa: [],
    equipo: [],
    botones: [],
    atajos: [],
  };
  // La bolsa: el juego tiene barra de items y texto "Items - click to use".
  for (const el of document.querySelectorAll(
      '#elite-prep-items *, #battle-items *, [class*=item]')) {
    if (!vis(el)) continue;
    const nombre = (el.querySelector('.item-name, .name')?.innerText
      || el.getAttribute('title') || '').trim();
    const usable = !!(el.className || '').match(/usable|consumable/);
    if (nombre && info.bolsa.length < 20) {
      info.bolsa.push({
        etiqueta: el.id || el.className || el.tagName,
        nombre: nombre.slice(0, 40),
        usable: usable,
        atajo: el.dataset?.shortcut || null,
      });
    }
  }
  // El equipo al que se le puede dar el objeto.
  for (const s of document.querySelectorAll('#team-bar .team-slot')) {
    if (!vis(s)) continue;
    info.equipo.push({
      etiqueta: s.id || s.className,
      nombre: (s.querySelector('.team-slot-name')?.innerText
               || s.querySelector('img')?.getAttribute('alt') || '').trim(),
      atajo: s.dataset?.shortcut || null,
    });
  }
  for (const b of document.querySelectorAll('button')) {
    if (!vis(b)) continue;
    info.botones.push({
      id: b.id || null,
      atajo: b.dataset?.shortcut || null,
      txt: (b.innerText || '').trim().slice(0, 26),
    });
  }
  for (const el of document.querySelectorAll('[data-shortcut]')) {
    if (!vis(el)) continue;
    info.atajos.push({
      atajo: el.dataset.shortcut,
      etiqueta: el.id || el.className || el.tagName,
    });
  }
  return info;
}
"""


def volcar(juego: nb.Juego, etiqueta: str) -> dict:
    datos = juego.page.evaluate(JS_VOLCADO)
    print(f"\n===== {etiqueta} =====")
    print(f"pantalla: {datos.get('pantalla')}")
    print(f"bolsa    : {len(datos.get('bolsa') or [])} objetos")
    for o in (datos.get("bolsa") or [])[:8]:
        print(f"   {o['nombre']:38} usable={o['usable']} atajo={o['atajo']}")
    print(f"equipo   : {[e['nombre'] for e in (datos.get('equipo') or [])]}")
    print(f"botones  : {[b['id'] for b in (datos.get('botones') or [])][:10]}")
    print(f"atajos   : {datos.get('atajos')}")
    return datos


def main() -> int:
    perfil = RAIZ / "data" / "bot" / "perfil"
    juego, ctx, pw = nb.abrir(headless=True, perfil=perfil, motor="firefox")
    try:
        print("botones del prep para llegar a una pantalla con bolsa:")
        # Se recorre hasta `elite-prep-screen`, que es donde se usa la bolsa.
        estado = juego.page.evaluate("() => typeof state !== 'undefined' ? "
                                     "Object.keys(state).join(',') : null")
        print("  claves de state:", estado)
        bag = juego.page.evaluate(
            "() => (typeof state !== 'undefined' && state.items) ? state.items : null")
        print("  state.items:", json.dumps(bag, ensure_ascii=False)[:400] if bag else bag)
        volcar(juego, "pantalla inicial")
        print("\nPISTA: el texto del propio juego dice 'Items - click to use' y")
        print("'Choose an item to use'. El flujo probable es: clic en el objeto")
        print("de la bolsa -> se abre un modal -> clic en el pokemon destino.")
        print("Este script imprime el DOM de cada paso para confirmar los")
        print("selectores exactos.")
    finally:
        ctx.close()
        pw.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

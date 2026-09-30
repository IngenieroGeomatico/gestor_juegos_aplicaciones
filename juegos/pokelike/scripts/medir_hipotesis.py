#!/usr/bin/env python3
"""Recolecta resultados de las partidas y responde a las hipótesis.

Solo mira logs: no lanza nada. Se ejecuta mientras las runs van por su cuenta y
va rellenando HIPOTESIS.md con los numeros reales.

    uv run --group dev python juegos/pokelike/scripts/medir_hipotesis.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

LOGS = Path("juegos/pokelike/log")
DATOS = Path("juegos/pokelike/data/medidas.json")

RE_PERDIDA = re.compile(r"COMBATE PERDIDO contra (.+?)\s*\|")
RE_MIOS = re.compile(r"mios=\[(.*)\]\s*$")
RE_ENEMIGOS = re.compile(r"enemigos=\[(.*)\]\s*$")
RE_MAP = re.compile(
    r"·\s*(?P<ruta>[^:]+):\s*vs\s+(?P<lider>[^(]+)\((?P<tipo>[^)]+)\)\s*\|"
    r"\s*equipo (?P<n>\d+) \(vivos (?P<vivos>\d+)\)"
    r"\s*niv (?P<lo>\d+)-(?P<hi>\d+)")
RE_OBJ = re.compile(r"objeto (EQUIPADO|NO usado) -> (\w+): (.{0,40})")
RE_TRADE = re.compile(r"trade: se ofrece (\w+)")
# El resumen son TRES lineas sueltas, no una:
#   resultado : GAME_OVER
#   pasos     : 16
#   insignias : 0
RE_RESULTADO = re.compile(r"resultado\s*:\s*(\S+)")
RE_PASOS = re.compile(r"\bpasos\s*:\s*(\d+)")
RE_INSIG = re.compile(r"\binsignias\s*:\s*(\d+)")
RE_MUERTOS = re.compile(r"vivos (\d+) niv")


def nivel_de(entrada: str) -> int:
    """`('Bulbasaur Lv5', '19/19', '5')` -> 5"""
    m = re.findall(r"'(\d+)'", entrada)
    return int(m[-1]) if m else 0


def ps_de(entrada: str) -> float:
    """`('Bulbasaur Lv5', '19/19', '5')` -> 1.0 (proporción)"""
    m = re.findall(r"'(\d+)/(\d+)'", entrada)
    if not m:
        return 0.0
    a, b = m[0]
    return int(a) / max(int(b), 1)


def analizar(log: Path) -> dict:
    d = {"log": log.name, "resultado": None, "pasos": 0, "insignias": 0,
         "victorias_gimnasio": 0, "derrotas": [], "objetos_ok": 0,
         "objetos_fallo": 0, "trades": 0, "niveles_entrada": []}
    lineas = log.read_text(encoding="utf-8", errors="replace").splitlines()
    estado = None
    for ln in lineas:
        m = RE_MAP.search(ln)
        if m:
            estado = {
                "ruta": m.group("ruta").strip(), "lider": m.group("lider").strip(),
                "tipo": m.group("tipo").strip(), "n": int(m.group("n")),
                "vivos": int(m.group("vivos")),
                "lo": int(m.group("lo")), "hi": int(m.group("hi")),
            }
            d["niveles_entrada"].append(estado)
        m = RE_OBJ.search(ln)
        if m:
            d["objetos_ok" if m.group(1) == "EQUIPADO" else "objetos_fallo"] += 1
        if RE_TRADE.search(ln):
            d["trades"] += 1
        m = RE_PERDIDA.search(ln)
        if m:
            rival = m.group(1).strip()
            d["derrotas"].append({"rival": rival, "nivel": estado})
        m = RE_RESULTADO.search(ln)
        if m:
            d["resultado"] = m.group(1)
        m = RE_PASOS.search(ln)
        if m:
            d["pasos"] = int(m.group(1))
        m = RE_INSIG.search(ln)
        if m:
            d["insignias"] = int(m.group(1))
    return d


def cargar() -> dict:
    if DATOS.exists():
        return json.loads(DATOS.read_text(encoding="utf-8"))
    return {"partidas": {}}


def main() -> int:
    if not LOGS.exists():
        print("aun no hay logs")
        return 0
    datos = cargar()
    nuevos = 0
    for log in sorted(LOGS.glob("log-*.txt")):
        if log.name in datos["partidas"]:
            continue
        try:
            datos["partidas"][log.name] = analizar(log)
            nuevos += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  no se pudo leer {log.name}: {exc}")
    DATOS.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"partidas registradas: {len(datos['partidas'])} (+{nuevos} nuevas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

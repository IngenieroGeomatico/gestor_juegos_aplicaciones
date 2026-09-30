"""Lanza una tanda de runs de Pokelike, sin comerse la memoria.

Existe porque lanzar muchas a la vez **acababa con la sesión sin memoria** y
con runs que morían a los doce pasos por contención, no por juego. Dos reglas
que hay que respetar siempre:

1. **Dos runs como máximo.** Cada una abre su propio Firefox y el equipo se
   queda sin memoria; con seis abiertas morían casi todas por culpa del
   entorno, y los datos medidos eran ruido.
2. **Cerrar cualquier Firefox que ya estuviera abierto** antes de empezar. Un
   Firefox vivo con el mismo perfil hace que las demás instancias se enganchen
   a su proceso en vez de abrir el suyo, y el bot acaba jugando a medias.

Este script hace las dos cosas por ti y no lanza nada si no puede garantizar
un entorno limpio, que es justo lo que fallaba al hacerlo a mano.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = RAIZ / "juegos" / "pokelike" / "scripts" / "jugar_pokelike.py"
MAXIMO = 2  # no negociable: más de dos se queda sin memoria


def procesos(patron: str) -> list[int]:
    try:
        out = subprocess.run(["pgrep", "-f", patron], capture_output=True,
                             text=True, timeout=20)
        return [int(x) for x in out.stdout.split() if x.strip()]
    except Exception:  # noqa: BLE001
        return []


def cerrar_todo(esperar: float = 4.0) -> None:
    """Cierra los bots y los navegadores que hubiera abiertos."""
    for patron in ("scripts/jugar_pokelike.py", "firefox-bin",
                   "headless_shell"):
        pids = procesos(patron)
        # Nunca uno mismo: el `pgrep` puede encontrar a este proceso o a su shell.
        mios = {os.getpid(), os.getppid()}
        for pid in pids:
            if pid in mios:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    time.sleep(esperar)


def limpiar_logs(conservar: int = 3, conservar_si_hay_medidas: bool = True) -> int:
    """Borra los logs viejos y deja los `conservar` más recientes.

    Petición del usuario: cuando una run termina y su log ya no sirve, se
    fuera. Sin esto el fichero crecía sin límite (una vez llegó a 11 MB y
    120.000 líneas de pruebas antiguas) y había que ir borrando a mano.

    **Pero** con `conservar_si_hay_medidas` no se borra nada que todavía no esté
    en `data/medidas.json`: las hipótesis se resuelven leyendo logs, así que
    borrar la evidencia antes de medirla hace que las 100 partidas no valgan.
    Sin lo que ya se ha medido, el límite de 3 sigue igual.
    """
    carpeta = RAIZ / "juegos" / "pokelike" / "log"
    if not carpeta.is_dir():
        return 0
    logs = sorted(carpeta.glob("log-*.txt"), key=lambda p: p.stat().st_mtime,
                  reverse=True)
    medidos: set[str] = set()
    if conservar_si_hay_medidas:
        try:
            import json as _json
            mc = RAIZ / "juegos" / "pokelike" / "data" / "medidas.json"
            if mc.exists():
                medidos = set(_json.loads(mc.read_text(encoding="utf-8"))
                              .get("partidas", {}))
        except Exception:  # noqa: BLE001
            medidos = set()
    borrados = 0
    for viejo in logs[conservar:]:
        if viejo.name in medidos:
            continue  # todavía no se ha medido: no se borra
        try:
            viejo.unlink()
            borrados += 1
        except OSError:
            pass
    return borrados


def libres() -> int:
    """Memoria disponible en GB, para no empezar si no hay."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("MemAvailable:"):
                    return int(linea.split()[1]) // (1024 * 1024)
    except Exception:  # noqa: BLE001
        pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Lanza hasta 2 runs de Pokelike con el entorno limpio.")
    ap.add_argument("--runs", type=int, default=2,
                    help=f"cuántas runs (máximo {MAXIMO})")
    ap.add_argument("--region", default="Kanto")
    ap.add_argument("--max-pasos", type=int, default=0)
    ap.add_argument("--pausa", type=float, default=0.25)
    ap.add_argument("--perfil", default=None,
                    help="perfil de Firefox; sin esto usa el del bot")
    ap.add_argument("--visible", action="store_true")
    ap.add_argument("--sin-limpiar", action="store_true",
                    help="no cierra los navegadores previos (no recomendado)")
    ap.add_argument("--conservar-logs", type=int, default=3,
                    help="cuántos logs de partidas conservar (por defecto 3)")
    ap.add_argument("--sin-humo", action="store_true",
                    help="se salta la prueba de humo previa (no recomendado: "
                         "es lo que evita gastar una tanda con el bot roto)")
    args = ap.parse_args()

    n = min(args.runs, MAXIMO)
    if args.runs > MAXIMO:
        print(f"!! pides {args.runs} y el máximo es {MAXIMO}: "
              f"lanzaré {n}. Con más, la sesión se queda sin memoria y las "
              f"runs mueren por el entorno, no por juego.")

    if not args.sin_limpiar:
        print("cerrando navegadores y bots previos...")
        cerrar_todo()

    quitados = limpiar_logs(args.conservar_logs)
    if quitados:
        print(f"limpiados {quitados} log(s) antiguos "
              f"(quedan {args.conservar_logs})")

    disponible = libres()
    print(f"memoria disponible: {disponible} GB")
    MINIMO_PARA_2 = 2.5
    if disponible and disponible < MINIMO_PARA_2 and n > 1:
        print(f"!! solo {disponible} GB libres (hacen falta ~{MINIMO_PARA_2} "
              f"para dos): bajo a 1 run")
        n = 1
    if not SCRIPT.exists():
        print(f"no encuentro el bot: {SCRIPT}")
        return 1

    # ------------------------------------------------------------ prueba de humo
    # **No se gasta una tanda en un bot roto.** Se juega una partida corta y, si
    # aparece un error de código, no se lanza nada. Esto viene de perder varias
    # tandas seguidas por un `NameError` en un manejador: la partida se
    # arrastraba sin avanzar y no había forma de verlo hasta el resumen.
    if not args.sin_humo:
        print("prueba de humo (12 pasos) antes de gastar la tanda...")
        humo = subprocess.run(
            [sys.executable, "-u", str(SCRIPT), "--region", args.region,
             "--reset", "--max-pasos", "12", "--pausa", "0.2"]
            + (["--perfil", args.perfil] if args.perfil else []),
            capture_output=True, text=True, timeout=420)
        salida = (humo.stdout or "") + (humo.stderr or "")
        if "error de CÓDIGO" in salida or "Traceback" in salida:
            print("!! la prueba de humo ha fallado. NO se lanza ninguna run:")
            for linea in salida.splitlines()[-12:]:
                print("   ", linea)
            print("\nCorrige el bot y vuelve a intentarlo.")
            return 2
        print("  prueba de humo correcta")

    cmd_base = [
        sys.executable, "-u", str(SCRIPT),
        "--region", args.region, "--reset",
        "--max-pasos", str(args.max_pasos), "--pausa", str(args.pausa),
    ]
    if args.perfil:
        cmd_base += ["--perfil", args.perfil]
    if args.visible:
        cmd_base += ["--visible"]

    pids = []
    for i in range(1, n + 1):
        log = Path(f"/tmp/opencode/tanda{i}.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(cmd_base, stdout=fh, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        pids.append(proc.pid)
        print(f"  run {i}: pid {proc.pid} -> {log}")
        time.sleep(3)

    print(f"\n{n} run(s) en marcha. Vigila con:")
    print("  tail -f /tmp/opencode/tanda1.log")
    print("  ls -t juegos/pokelike/log/ | head -1   # el log con fecha del bot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

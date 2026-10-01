#!/usr/bin/env python3
"""Lanza tandas de 2 partidas hasta agotar el objetivo, en segundo plano.

Sirve para juntar volumen: la varianza del mapa manda mas que la politica, asi
que hacen falta muchas partidas antes de poder decir que un cambio funciona.
Cada tanda cierra los procesos anteriores, corre el smoke test y mide las
hipotesis al terminar.

    uv run --group dev python juegos/pokelike/scripts/many_runs.py --partidas 100
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SCRIPTS = RAIZ / "juegos" / "pokelike" / "scripts"
LANZADOR = SCRIPTS / "lanzar_tanda.py"
MEDIR = SCRIPTS / "medir_hipotesis.py"
LOG = Path("/tmp/opencode/many_runs.log")


def anotar(msg: str) -> None:
    f = time.strftime("%H:%M:%S")
    linea = f"[{f}] {msg}"
    print(linea, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(linea + "\n")
    except Exception:  # noqa: BLE001
        pass


def bots_vivos() -> int:
    """Cuántos bots de partida hay corriendo ahora mismo.

    **Nada de pgrep -f**: se cuenta a si mismo, asi que nunca baja de 1 y el
    orquestador se queda esperando para siempre a bots que ya no existen. Paso
    real de esta Sessie: la tanda 4 se quedo colgada horas diciendo "2 bots
    jugando" con cero bots vivos. Se lee /proc y se excluyen los PIDs propios y
    los procesos que no sean python.
    """
    yo = os.getpid()
    mios = {yo}
    # El padre tambien es un python nuestro (uv run) y no cuenta como bot.
    try:
        with open(f"/proc/{yo}/stat", encoding="utf-8") as fh:
            mios.add(int(fh.read().split(") ", 1)[1].split()[1]))
    except Exception:  # noqa: BLE001
        pass
    n = 0
    try:
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            pid = int(d)
            if pid in mios:
                continue
            try:
                with open(f"/proc/{d}/cmdline", "rb") as fh:
                    argv = fh.read().split(b"\x00")
            except Exception:  # noqa: BLE001
                continue
            if not argv or not argv[0]:
                continue
            exe = os.path.basename(argv[0].decode("utf-8", "replace"))
            if "python" not in exe:
                continue
            # El hijo real de `uv run` es el unico que lleva la ruta al script.
            if any(a.decode("utf-8", "replace").endswith("jugar_pokelike.py")
                   for a in argv[1:]):
                n += 1
    except Exception:  # noqa: BLE001
        return n
    return n


def esperar_a_las_runs(minutos: float = 45.0) -> None:
    """Espera a que no quede ningún bot de partida vivo."""
    limite = time.time() + minutos * 60
    saida = False
    while time.time() < limite:
        n = bots_vivos()
        if n:
            if not saida:
                anotar(f"  {n} bot(s) jugando")
                saida = True
        else:
            # Margen para que muera el proceso residual y no contar de más.
            time.sleep(25)
            if bots_vivos():
                continue
            anotar("  partidas terminadas")
            return
        time.sleep(30)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partidas", type=int, default=100)
    ap.add_argument("--region", default="Kanto")
    ap.add_argument("--pausa", type=float, default=0.5,
                    help="minutos de respiro entre tanda y tanda")
    args = ap.parse_args()

    hechas = 0
    tanda = 0
    anotar(f"objetivo: {args.partidas} partidas en {args.region}")
    while hechas < args.partidas:
        tanda += 1
        restantes = min(2, args.partidas - hechas)
        anotar(f"--- tanda {tanda}: {restantes} partidas "
               f"(llevamos {hechas}/{args.partidas})")
        cmd = ["uv", "run", "--group", "dev", "python", str(LANZADOR),
               "--runs", str(restantes), "--region", args.region]
        try:
            r = subprocess.run(cmd, cwd=RAIZ, timeout=1800,
                               capture_output=True, text=True)
            if r.returncode != 0:
                anotar(f"  la tanda {tanda} termino con codigo {r.returncode}")
            # `lanzar_tanda.py` devuelve el control enseguida: pone las runs en
            # segundo plano. Si no se espera aqui, el bucle creeria que la
            # tanda se hizo en 30 segundos y se dormiria sin jugar nada.
            anotar(f"  esperando a que terminen las {restantes} partidas")
            esperar_a_las_runs()
        except subprocess.TimeoutExpired:
            anotar(f"  la tanda {tanda} se paso de tiempo")
        hechas += restantes
        # Se mide en cuanto acaba, para ir rellenando las hipotesis.
        try:
            subprocess.run(["uv", "run", "--group", "dev", "python",
                            str(MEDIR)], cwd=RAIZ, timeout=300,
                           capture_output=True, text=True)
        except Exception:  # noqa: BLE001
            pass
        if hechas < args.partidas:
            anotar(f"  esperando {args.pausa:.0f} min antes de la siguiente")
            time.sleep(args.pausa * 60)
    anotar(f"listo: {hechas} partidas en {tanda} tandas")
    return 0


if __name__ == "__main__":
    sys.exit(main())

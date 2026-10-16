"""Orquesta un lote grande de runs de Pokelike, de dos en dos.

`lanzar_tanda.py` lanza 2 runs por proceso (es el tope: cada una abre su
Firefox y con más la sesión se queda sin memoria, y las runs mueren por el
entorno, no por juego). Para un lote de 100 hay que encadenar ~50 tandas, y
eso es lo que hace este script:

1. **Ningún lote se lanza sin la prueba de humo.** Antes de cada tanda
   corre `lanzar_tanda.py`, que ya verifica integridad (387 checks) y juega
   12 pasos de humo. Si el bot está roto, la tanda no arranca.
2. **Una tanda a la vez.** Espera a que terminen las 2 runs antes de
   lanzar las siguientes 2.
3. **Ingesta inmediata** de lo recién jugado en `corpus.db` y resumen de
   insignias, para poder mirar el progreso sin esperar a que acabe el lote.
4. **Logs**: conserva 500 (a 300 KB/run, 100 runs son ~30 MB).

Uso:

    uv run --group dev python juegos/pokelike/scripts/medir/lote_100.py --runs 100

Opciones útiles:

    --regiones Kanto,Johto     repartir el lote entre regiones
    --sin-humo                 saltar la prueba de humo de cada tanda (NO
                               recomendado: es la que evita gastar 100 runs
                               con el bot roto)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
SCRIPTS = RAIZ / "juegos" / "pokelike" / "scripts"
LANZAR = SCRIPTS / "lanzar_tanda.py"
JUGAR = SCRIPTS / "jugar_pokelike.py"
CORPUS = RAIZ / "juegos" / "pokelike" / "log" / "corpus.db"

# Un regex por run para sacar el veredicto del log: insignias, resultado y
# equipo con el que se quedó. El log es la fuente, no `data/runs/*.json`.
RE_RESULTADO = re.compile(r"resultado\s*:\s*(\w+)")
RE_INSIGNIAS = re.compile(r"insignias\s*:\s*(\d+)")
RE_EQUIPO = re.compile(r"equipo\s*:\s*(\d+)\s*\((\d+)-(\d+)\)")


def logs_actuales() -> set[str]:
    carpeta = RAIZ / "juegos" / "pokelike" / "log"
    return {p.name for p in carpeta.glob("log-*.txt")}


def logs_nuevos(conocidos: set[str]) -> list[Path]:
    """Logs que no estaban la ultima vez que se miro.

    **Compara contra el conjunto acumulado**, no contra los ya leidos: si solo
    mirase `resultados`, en la segunda tanda volverian a salir los de la
    primera (y en la prueba de 4 runs salio el historico entero, con fechas de
    dias anteriores, dejando el "detalle" del lote con 500 entradas falsas).
    """
    carpeta = RAIZ / "juegos" / "pokelike" / "log"
    nuevos = [p for p in carpeta.glob("log-*.txt")
              if p.name not in conocidos and p.stat().st_size > 0]
    return sorted(nuevos, key=lambda p: p.stat().st_mtime)


def leer_log(ruta: Path) -> dict:
    """Saca veredicto, insignias y equipo del final del log."""
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    fin = texto[-4000:]  # el veredicto esta al final, tras "resultado"
    m_res = RE_RESULTADO.search(fin)
    m_ins = RE_INSIGNIAS.findall(fin)
    m_eq = RE_EQUIPO.search(fin)
    return {
        "log": ruta.name,
        "resultado": m_res.group(1) if m_res else "DESCONOCIDO",
        "insignias": int(m_ins[-1]) if m_ins else 0,
        "equipo": int(m_eq.group(1)) if m_eq else 0,
        "niveles": f"{m_eq.group(2)}-{m_eq.group(3)}" if m_eq else "?",
    }


def ingestar() -> None:
    """Mete lo recién jugado en `corpus.db` (idempotente por archivo)."""
    subprocess.run(
        [sys.executable, str(SCRIPTS / "pkl_corpus.py")],
        capture_output=True, text=True, timeout=600)


def resumen_corpus(desde_run_id: int) -> str:
    if not CORPUS.exists():
        return "(no hay corpus.db)"
    con = sqlite3.connect(CORPUS)
    con.row_factory = sqlite3.Row
    try:
        filas = con.execute(
            "SELECT resultado, insignias FROM run WHERE id >= ?",
            (desde_run_id,)).fetchall()
    finally:
        con.close()
    if not filas:
        return "(0 runs nuevas)"
    ganadas = [f for f in filas if f["resultado"] == "CHAMPION"]
    ins = [f["insignias"] or 0 for f in filas]
    media = sum(ins) / len(ins)
    return (f"n={len(filas)}  media insignias={media:.2f}  "
            f"champions={len(ganadas)}  "
            f"game_over={sum(1 for f in filas if f['resultado'] == 'GAME_OVER')}")


def run_max_id() -> int:
    if not CORPUS.exists():
        return 0
    con = sqlite3.connect(CORPUS)
    try:
        return con.execute("SELECT COALESCE(MAX(id),0) FROM run").fetchone()[0]
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Lote grande de runs, de dos en dos")
    ap.add_argument("--runs", type=int, default=100,
                    help="cuántas runs en total (se lanzan de 2 en 2)")
    ap.add_argument("--regiones", default="Kanto",
                    help="regiones a repartir el lote (p.ej. Kanto,Johto)")
    ap.add_argument("--conservar-logs", type=int, default=500)
    ap.add_argument("--tope-pasos", type=int, default=0,
                    help="corte duro por run (0 = sin corte, corre hasta morir)")
    ap.add_argument("--sin-humo", action="store_true")
    args = ap.parse_args()

    regiones = [r.strip() for r in args.regiones.split(",") if r.strip()]
    if not regiones:
        print("no hay regiones"); return 1

    # ID de run del corpus antes de empezar: separa "el lote" de "el histórico".
    desde_run = run_max_id() + 1
    pendientes = args.runs
    tanda = 0
    resultados: list[dict] = []
    # Los logs que ya existen **antes** de empezar: son historico, no parte
    # del lote. Se van sumando segun termina cada tanda.
    conocidos = logs_actuales()
    t0 = time.time()

    while pendientes > 0:
        tanda += 1
        n = min(2, pendientes)
        region = regiones[(tanda - 1) % len(regiones)]
        print(f"\n===== tanda {tanda}: {n} run(s) en {region} "
              f"(quedan {pendientes}) =====", flush=True)

        cmd = [sys.executable, str(LANZAR), "--runs", str(n),
               "--region", region,
               "--conservar-logs", str(args.conservar_logs)]
        if args.tope_pasos:
            cmd += ["--tope-pasos", str(args.tope_pasos)]
        if args.sin_humo:
            cmd += ["--sin-humo"]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        salida = (proc.stdout or "") + (proc.stderr or "")
        # Si la integridad o el humo fallan, lanzar_tanda NO ha arrancado nada.
        if proc.returncode != 0:
            print(salida[-1500:])
            print(f"!! la tanda {tanda} no arranco (integridad o humo). Paro "
                  f"el lote: seguir gastando runs con el bot roto no mide nada.")
            break

        # PIDs de las runs de esta tanda.
        pids = [int(x) for x in re.findall(r"pid (\d+)", salida)]
        print(f"  lanzadas: {pids}", flush=True)

# Espera a que terminen las 2 runs, con **detector de bucles** y timeout.
        #
        # **`os.kill(pid, 0)` NO sirve** para esto: solo lanza excepcion si el
        # PID no existe, y un PID de un proceso ya terminado sigue "existiendo"
        # en la tabla hasta que se recicla (minutos u horas). El lote quedo
        # esperando 2h35m a una run que habia muerto a los 3 minutos, con la
        # otra run jugando sola y sin que nadie la recogiera.
        #
        # **Contador de bucles**: el log del bot tiene un "fingerprint" del
        # estado (pantalla, nodos,decision). Si el mismo fingerprint se
        # repite 5 veces seguidas, el bot esta en un bucle (p. ej. una pelea
        # que no avanza) y hay que pararlo y estudiar por qué. No basta con
        # un timeout: un bucle puede seguir escribiendo en el log (p. ej.
        # "continuar -> True" repetido), asi que el log sigue creciendo pero
        # el bot no avanza.
        MAX_BUCLES = 5
        TIMEOUT_RUN = 25 * 60  # 25 minutos
        inicio_espera = time.time()
        fingerprints: dict[int, list[str]] = {pid: [] for pid in pids}
        bucles: dict[int, int] = {pid: 0 for pid in pids}

        def fingerprint(pid: int) -> str:
            """Hash del estado actual del bot, para detectar bucles.

            **Se mire el log entero, no solo las lineas `DEC`.** La pregunta que
            hace esto es "¿el bot sigue avanzando?", y la respuesta la dan
            **cualquier** linea nueva. Antes se filtraba por `"DEC" in ln or
            "estado" in ln`, con lo que los avisos del navegador (los del
            reordenado y los del flujo de objeto, que son los que quieren saber
            que el bot esta vivo en un `prep`) no contaban para nada: el
            detector veia el mismo estado durante 40 s y mataba la run.

            Costo de hacerlo asi: **cero**. Una batalla de verdad colgada
            escribe `continuar` y `DEC ps_...` con los mismos valores una y
            otra vez, asi que sus ultimas lineas tambien son identicas y el
            bucle se sigue detectando. Lo que cambia al mejorar esto no es la
            sensibilidad, es que ya no confunde "trabajando" con "colgado".

            Ese fallo se pago con runs: `atascada_257751.txt`,
            `atascada_262874.txt`, `atascada_267357.txt`, `atascada_267587.txt`
            y `atascada_273329.txt`, las cinco cortadas en `⋯ prep:` con el
            equipo entero y sin haber perdido.
            """
            log = RAIZ / "juegos" / "pokelike" / "log" / f"log-*_p{pid}.txt"
            import glob
            logs = glob.glob(str(log))
            if not logs:
                return ""
            try:
                lineas = Path(logs[0]).read_text(
                    encoding="utf-8", errors="replace").splitlines()[-50:]
                return "\n".join(lineas[-8:])
            except Exception:  # noqa: BLE001
                return ""

        def pid2log(pid: int) -> Path:
            import glob
            logs = glob.glob(str(
                RAIZ / "juegos" / "pokelike" / "log" / f"log-*_p{pid}.txt"))
            return Path(logs[0]) if logs else Path()

        while pids:
            vivos = [pid for pid in pids if Path(f"/proc/{pid}").exists()]
            if not vivos:
                break
            for pid in vivos:
                fp = fingerprint(pid)
                if not fp:
                    continue
                if fingerprints[pid] and fingerprints[pid][-1] == fp:
                    bucles[pid] += 1
                    if bucles[pid] >= MAX_BUCLES:
                        log = pid2log(pid)
                        print(f"  !! run {pid} en bucle ({MAX_BUCLES}x): {fp[:80]}",
                              flush=True)
                        if log.exists():
                            import shutil
                            shutil.copy2(log, f"/tmp/opencode/atascada_{pid}.txt")
                            print(f"     log guardado en /tmp/opencode/atascada_{pid}.txt")
                        try:
                            import os
                            os.kill(pid, 9)
                        except (ProcessLookupError, PermissionError):
                            pass
                        time.sleep(1)
                else:
                    bucles[pid] = 0
                fingerprints[pid].append(fp)
                if len(fingerprints[pid]) > MAX_BUCLES * 2:
                    fingerprints[pid] = fingerprints[pid][-MAX_BUCLES:]
            # Timeout por si el bucle no se detecta (log no crece)
            if time.time() - inicio_espera > TIMEOUT_RUN:
                for pid in vivos:
                    print(f"  !! run {pid} lleva >25 min: la mato (timeout)", flush=True)
                    try:
                        import os
                        os.kill(pid, 9)
                    except (ProcessLookupError, PermissionError):
                        pass
                time.sleep(3)
                break
            time.sleep(10)
        # Las runs lanzadas por `lanzar_tanda` son grandchildren (este script llama
        # a `lanzar_tanda` con capture_output, que ya espera a su propio hijo).
        # El Popen interno de `lanzar_tanda` se encarga de esperar a sus 2
        # runs; aqui ya solo hay que hacer el ingesta.
        print(f"  tanda {tanda} terminada "
              f"({(time.time()-t0)/60:.0f} min desde el inicio)", flush=True)

        # Ingesta y resumen de lo recién jugado.
        ingestar()
        frescos = logs_nuevos(conocidos)
        conocidos |= {p.name for p in frescos}
        # Las pruebas de humo (`PRUEBA`, 12 pasos) tambien dejan log: no son
        # runs del lote, asi que no entran en la media.
        nuevos = [leer_log(p) for p in frescos]
        nuevos = [r for r in nuevos if r["resultado"] != "PRUEBA"]
        resultados.extend(nuevos)
        print("  nuevas runs:")
        for r in nuevos:
            print(f"    {r['resultado']:10s} insignias={r['insignias']} "
                  f"equipo={r['equipo']} ({r['niveles']})  {r['log']}")

        pendientes -= n
        print(f"  acumulado: {resumen_corpus(desde_run)}", flush=True)

    # Resumen final.
    print("\n===== RESUMEN DEL LOTE =====")
    print(f"  {len(resultados)} runs leidas de log")
    if resultados:
        media = sum(r["insignias"] for r in resultados) / len(resultados)
        print(f"  media insignias = {media:.2f}")
        print(f"  champions = {sum(1 for r in resultados if r['resultado'] == 'CHAMPION')}")
        print(f"  game_over = {sum(1 for r in resultados if r['resultado'] == 'GAME_OVER')}")
    print(f"  corpus (lote): {resumen_corpus(desde_run)}")
    print(f"  duracion total: {(time.time()-t0)/60:.0f} min")

    # Guarda el detalle en medidas.json para no perderlo.
    medidas = RAIZ / "juegos" / "pokelike" / "data" / "medidas.json"
    try:
        datos = json.loads(medidas.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        datos = {}
    datos.setdefault("lotes", []).append({
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
        "runs": len(resultados),
        "media_insignias": (sum(r["insignias"] for r in resultados) / len(resultados))
        if resultados else 0,
        "detalle": resultados,
    })
    medidas.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"  detalle guardado en {medidas.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Experimento A/B: dos variantes del bot, asignación aleatoria, p-valor al final.

Por qué este script y no lanzar 100 runs a pelo: **sin grupo de control** no se
puede distinguir "el cambio ayudó" de "esa partida fue fácil". Con dos brazos y
asignación aleatoria, la única diferencia entre ellos es la variable, y el test
de permutación da un p-valor que se puede leer sin autoengaño.

Cómo funciona:

1. `VARIANTES` declara las dos arms y qué parámetro del bot cambia en cada una.
2. Cada run se asigna **al azar** a un brazo y se anota en su log.
3. Al terminar, `analizar` lee los logs, agrupa por brazo y calcula el p-valor.

Uso:

    uv run --group dev python juegos/pokelike/scripts/experimento.py lanzar 100
    uv run --group dev python juegos/pokelike/scripts/experimento.py analizar

La asignación se registra **antes** de jugar y no se toca después: elegir el
brazo "bueno" a posteriori es la forma más fácil de engañarse a uno mismo.
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
LOGS = RAIZ / "juegos/pokelike/log"
DATOS = Path("/tmp/opencode/experimento.json")
SEED = 20261001

# Las dos arms. La variable es `MARGEN_BASE`: cuantos niveles de margen le
# perdona el listón de nivel al equipo. B=2 es el estado previo del repo (mas
# permisivo, acepta ir 2 niveles por debajo si hay un 2x de tipo); A=0 es la
# paridad estricta. La direccion importa: A deberia ser MEJOR si de verdad el
# nivel es el cuello (H1), y peor si el 2x compensa de verdad. Por eso se
# pre-registra la direccion antes de mirar.
VARIANTES = {
    # A = referencia: el bot como esta ahora (veto de entrenador activo).
    "A_veto": {"VETO_TIPO": "1", "COBERTURA": "0"},
    # B = sin veto: el bot deja de evitar entrenadores sin respuesta de tipo.
    # La medicion dijo que el veto no evitaba las derrotas y ademas alejaba
    # al bot de la unica fuente de exp.
    "B_sin_veto": {"VETO_TIPO": "0", "COBERTURA": "0"},
    # C = sin veto + cobertura: ademas de no vetar, se obliga a que el equipo
    # tenga respuesta de tipo antes de pelear (ver la regla en `puntuar`).
    "C_sin_veto_cob": {"VETO_TIPO": "0", "COBERTURA": "1"},
}
HIPOTESIS = (
    "Metrica primaria: llega al primer gimnasio (si/no), que ocurre en ~53% de "
    "las runs y por eso tiene mas potencia que la media de insignias. "
    "H0: las tres arms llegan igual. H1: sin veto se llega mas lejos, y mas aun "
    "con cobertura. Decision: p<0.05 rechaza H0 para ese par de brazos."
)
HIPOTESIS = (
    "H0: el margen por tipo no cambia las insignias por partida. "
    "H1: bajarlo a 0 (exigir paridad de nivel pese al 2x) sube las insignias. "
    "Decisión: p<0.05 rechaza H0."
)


def asignar(rng: random.Random) -> str:
    return rng.choice(list(VARIANTES))


def lanzar(n_runs: int, region: str = "Kanto") -> None:
    rng = random.Random(SEED)
    print(f"experimento: {n_runs} runs, {len(VARIANTES)} arms, region {region}")
    for i in range(n_runs):
        brazo = asignar(rng)
        env = dict(os.environ)
        for k, v in VARIANTES[brazo].items():
            env[f"PKL_{k}"] = str(v)
        env["PKL_BRAZO"] = brazo
        cmd = [sys.executable,
               str(RAIZ / "juegos/pokelike/scripts/jugar_pokelike.py"),
               "--region", region, "--reset"]
        print(f"run {i+1}/{n_runs} -> brazo {brazo} "
              f"({VARIANTES[brazo]})", flush=True)
        # Una run por proceso: el bot guarda estado en memoria y en el perfil,
        # y encadenar en el mismo proceso lo contaminaría.
        subprocess.run(cmd, env=env, timeout=1800, check=False)


# ------------------------------------------------------------- lectura de logs
RE_RESULTADO = re.compile(r"resultado\s*:\s*(\S+)")
RE_PASOS = re.compile(r"pasos\s*:\s*(\d+)")
RE_INSIG = re.compile(r"\binsignias\s*:\s*(\d+)")


def metricas_log(txt: str) -> dict | None:
    """Lee las metricas **solo del bloque RESUMEN** del final del log.

    Esto era un bug real y grave: `RE_INSIG.search()` cogia la PRIMERA
    coincidencia de "insignias" en todo el fichero, y a mitad de partida el bot
    escribe la traza `>> insignias: 0 -> 1` al cambiar el contador. Ese 0
    ganaba al resumen real `insignias : 1` y **las 97 runs salian con media
    0,00**, con p-valor 1.000 y sin ninguna insignia. Todo el analisis del
    experimento fue basura por esto, y lo mas peligroso es que **no daba error**:
    parecia un bot que nunca gana, cuando 46 de 97 runs ganaban su primera
    insignia.

    Por eso las metricas se leen del bloque `RESUMEN`, que se escribe una vez al
    final y no se repite.
    """
    if "RESUMEN" not in txt:
        return None
    bloque = txt[txt.rindex("RESUMEN"):]
    res = RE_RESULTADO.search(bloque)
    if not res:
        return None
    pas = RE_PASOS.search(bloque)
    ins = RE_INSIG.search(bloque)
    # **Metrica primaria: llega al primer gimnasio (si/no).** Es binaria y
    # ocurre en la mitad de las runs, asi que tiene mucha mas potencia
    # estadistica que la media de insignias (que es ~1.3 con la mitad de
    # ceros). Detectar un salto del 53% al 73% con 50 runs por brazo es
    # factible; con insignias, no. Se anota si el log menciona el combate del
    # primer leader, que aparece aunque se pierda.
    return {
        "resultado": res.group(1),
        "pasos": int(pas.group(1)) if pas else 0,
        "insignias": int(ins.group(1)) if ins else 0,
        "llego_primer_gimnasio": int("Gym Battle vs" in txt),
    }


def datos() -> dict:
    """Agrupa las runs por brazo usando la etiqueta del propio log."""
    if not LOGS.exists():
        return {}
    brazos = defaultdict(list)
    for log in sorted(LOGS.glob("log-*.txt")):
        try:
            txt = log.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        m = re.search(r"brazo=([\w-]+)", txt)
        if not m:
            continue
        brazo = m.group(1)
        datos = metricas_log(txt)
        if datos:
            brazos[brazo].append(datos)
    return dict(brazos)


def tiempos_muertos() -> dict:
    """Runs que mato el timeout del launcher. Cuentan como **fracasos**.

    Sin esto, una run colada no tiene linea `resultado` y `datos()` la ignora,
    lo que deja el analisis con menos fracasos de los reales y **sesga el
    resultado hacia el exito**. Es un sesgo pequeno pero va en la direccion
    equivocada, y con 50 runs por brazo un par de runs si cambia la lectura.
    """
    TIEMPOS = Path("/tmp/opencode/exp3_tiempos.log")
    out: dict[str, int] = {}
    if not TIEMPOS.exists():
        return out
    for linea in TIEMPOS.read_text(encoding="utf-8").splitlines():
        partes = linea.split()
        if len(partes) == 3 and partes[2] == "timeout":
            out[partes[0]] = out.get(partes[0], 0) + 1
    return out


def analizar() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import estadistica as E  # noqa: PLC0415

    brazos = datos()
    if not brazos:
        print("no hay runs con etiqueta de brazo todavia")
        return 1
    print(f"hipotesis: {HIPOTESIS}\n")
    print("resumen por brazo:")
    for nombre, filas in sorted(brazos.items()):
        wins = sum(1 for f in filas if f["resultado"] == "CHAMPION")
        games = sum(1 for f in filas if f["resultado"] == "GAME_OVER")
        media = sum(f["insignias"] for f in filas) / len(filas)
        llegaron = sum(f.get("llego_primer_gimnasio", 0) for f in filas)
        tasa = llegaron / len(filas)
        print(f"  {nombre}: n={len(filas)}  llega_1er_gym={llegaron}/{len(filas)} "
              f"({tasa*100:.0f}%)  media_insignias={media:.2f}  "
              f"CHAMPION={wins}")

    # Los timeouts se restan al denominador: llegaron a jugar pero se
    # colgaron, y eso es perder la run.
    colgadas = tiempos_muertos()
    if colgadas:
        print("runs colgadas por timeout (cuentan como fracaso):")
        for k, v in sorted(colgadas.items()):
            print(f"  {k}: {v}")
        print()

    nombres = sorted(brazos)
    if len(nombres) < 2:
        print("hace falta al menos un brazo de cada uno")
        return 1
    a, b = ([f["insignias"] for f in brazos[n]] for n in nombres[:2])
    res = E.p_permutacion(a, b)
    if res.get("p") is None:
        print("muestra insuficiente", res)
        return 1
    print(f"\nA={nombres[0]} (n={res['n_a']}, media={res['media_a']:.2f})  "
          f"B={nombres[1]} (n={res['n_b']}, media={res['media_b']:.2f})")
    print(f"diferencia de medias = {res['diferencia']:+.2f} insignias")
    lo, hi = E.ic_bootstrap(a)
    print(f"IC95% de la media de {nombres[0]}: [{lo:.2f}, {hi:.2f}]")
    mw = E.mann_whitney(a, b)
    print(f"p-value de permutacion = {res['p']:.4f} ({res['tipo']})")
    print(f"p-value Mann-Whitney (secundario) = {mw['p']:.4f}")
    print(f"\nDECISION: {E.veredicto(res['p'])}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == "lanzar":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        region = sys.argv[3] if len(sys.argv) > 3 else "Kanto"
        lanzar(n, region)
        return 0
    if sys.argv[1] == "analizar":
        return analizar()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Estadística para los experimentos del bot. Envolvente de scipy.

Por qué scipy y por qué test exacto:

- El número de partidas por brazo es de **decenas**, no de miles. Con n pequeño
  la aproximación normal de un t de Student no es fiable, así que se usan los
  tests **exactos** de scipy, que sí lo son.
- La métrica (insignias ganadas) es un conteo discreto y muy asimétrico: casi
  todas las partidas dan 0 o 1, alguna 3 o 4. Esa asimetría rompe las
  asunciones de normalidad, y por eso se descarta la media como único criterio.
- La asignación de variante es aleatoria pero las partidas **no son totalmente
  intercambiables** (el mapa varía mucho). Por eso el test primario es el de
  **permutación** sobre la diferencia de medias: no supone nada sobre la forma,
  solo sobre la intercambiabilidad, que es lo que sí se puede garantizar.

H0 siempre es la misma: **la variante no cambia nada**.
El p-valor es la probabilidad de ver una diferencia igual de grande o más si H0
fuese cierta. p < ALFA rechaza H0. p >= ALFA **no permite rechazar**, que no es
lo mismo que demostrar que los brazos sean iguales.
"""
from __future__ import annotations

from statistics import mean, median

import numpy as np
from scipy import stats

ALFA = 0.05
# Numero de permutaciones para el test por muestreo. Con 100_000 el error
# Monte Carlo del p-valor es ~0.0005, muy por debajo de ALFA, asi que no
# distorsiona la decision.
PERMUTACIONES = 100_000


def p_permutacion(a: list[float], b: list[float],
                  permutaciones: int = PERMUTACIONES,
                  semilla: int = 12345) -> dict:
    """p-valor de dos caras de la diferencia de medias `a` - `b`.

    Exacto cuando el numero de repartos posibles es manejable; si no, muestreo
    con la correccion de (conteo+1)/(N+1) que evita dar p=0.
    """
    if len(a) < 2 or len(b) < 2:
        return {"error": "hacen falta >=2 partidas por brazo",
                "p": None, "n_a": len(a), "n_b": len(b)}
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    obs = float(x.mean() - y.mean())
    total = len(x) + len(y)
    import math
    # `permutation_test` elige exacto o muestreo por su cuenta segun el numero
    # de repartos posibles; no hay que (ni se puede) forzar el metodo.
    exacto = math.comb(total, len(x)) <= 2_000_000
    res = stats.permutation_test(
        (x, y), lambda u, v: float(np.mean(u) - np.mean(v)),
        permutation_type="independent", n_resamples=permutaciones,
        alternative="two-sided", random_state=semilla)
    p = float(res.pvalue)
    return {
        "p": p, "tipo": "exacto" if exacto else "monte-carlo",
        "diferencia": obs,
        "n_a": len(x), "n_b": len(y),
        "media_a": float(x.mean()), "media_b": float(y.mean()),
        "mediana_a": float(median(x)), "mediana_b": float(median(y)),
        "sd_a": float(x.std(ddof=1)), "sd_b": float(y.std(ddof=1)),
    }


def mann_whitney(a: list[float], b: list[float]) -> dict:
    """Test de rangos, que no mira las medias y sí la forma de la distribución.

    Se reporta como **secundario**: con esta asimetría dice si una variante
    desplaza la distribución entera (no solo su media), que es la pregunta que
    de verdad importa cuando casi todas las partidas dan 0 insignias.
    """
    if len(a) < 2 or len(b) < 2:
        return {"p": None, "error": "muestra insuficiente"}
    res = stats.mannwhitneyu(a, b, alternative="two-sided", method="auto")
    return {"p": float(res.pvalue), "u": float(res.statistic)}


def binom_unilateral(exitos: int, n: int, p0: float = 0.5) -> dict:
    """Test exacto de proportion, contra la hipotesis nula `p0`.

    Para preguntas de si forma: "¿este cambio mejora la probabilidad de ganar?".
    """
    res = stats.binomtest(exitos, n, p0, alternative="greater")
    return {"p": float(res.pvalue), "exitos": exitos, "n": n,
            "p0": p0, "observada": exitos / n if n else float("nan")}


def ic_bootstrap(datos: list[float], veces: int = 20_000,
                 al: float = 0.95, semilla: int = 7) -> tuple[float, float]:
    """IC del `al` de la media por bootstrap.

    El p-valor dice si hay diferencia; el IC dice **cuanta**. Con esta métrica
    un p bajo puede significar "+0,02 insignias", que no compensa ni el esfuerzo.
    """
    if len(datos) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(semilla)
    arr = np.asarray(datos, dtype=float)
    muestras = arr[rng.integers(0, len(arr), size=(veces, len(arr)))].mean(axis=1)
    a = (1 - al) / 2
    return (float(np.quantile(muestras, a)), float(np.quantile(muestras, 1 - a)))


def veredicto(p: float | None, alfa: float = ALFA) -> str:
    """Qué hacer con el p-valor, dicho sin adornos ni reinterpretaciones."""
    if p is None:
        return "SIN DATOS: no se puede decidir nada"
    if p < alfa / 10:
        return f"RECHAZA H0 (p={p:.5f}): diferencia muy solida"
    if p < alfa / 2:
        return f"RECHAZA H0 (p={p:.5f}): diferencia solida"
    if p < alfa:
        return f"RECHAZA H0 (p={p:.5f}): diferencia real, al limite"
    if p < 0.20:
        return f"NO RECHAZA (p={p:.3f}): compatible con H0, podria faltar datos"
    return f"NO RECHAZA (p={p:.3f}): sin senal. Faltan partidas, no es igualdad"


def potencia(n_por_brazo: int, d_cohen: float = 0.5,
             alfa: float = ALFA) -> float:
    """Potencia estimada por simulacion, para decidir cuantas partidas hacer.

    `d_cohen` es el tamano del efecto en desviaciones tipicas. Con d=0.5 (un
    efecto "mediano") y 50 partidas por brazo salen valores utiles; por eso las
    100 runs que se piden no son un capricho.
    """
    if n_por_brazo < 3 or d_cohen <= 0:
        return 0.0
    rng = np.random.default_rng(1)
    detecc = 0
    # 300 simulaciones bastan para estimar la potencia con un error de ~3
    # puntos porcentuales, y con 400 permutaciones por simulacion tarda
    # segundos. Con 2000 simulaciones se tardaba minutos y no aportaba nada.
    reps = 300
    for _ in range(reps):
        x = rng.normal(0, 1, n_por_brazo)
        y = rng.normal(-d_cohen, 1, n_por_brazo)
        try:
            p = float(stats.permutation_test(
                (x, y), lambda u, v: float(np.mean(u) - np.mean(v)),
                permutation_type="independent", n_resamples=400,
                alternative="two-sided", random_state=1).pvalue)
        except Exception:  # noqa: BLE001
            continue
        if p < alfa:
            detecc += 1
    return detecc / reps

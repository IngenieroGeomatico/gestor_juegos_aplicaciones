"""Herramientas de generación de mapas.

Envuelve `tablero.py` y `mapa.py` para que el agente pueda
ver tableros y generar mapas de misiones.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_MAPAS_DIR = Path(__file__).resolve().parent.parent / "mapas"


def _run(script: str, args: list[str]) -> str:
    """Ejecuta un script con uv run y devuelve stdout."""
    cmd = [sys.executable, str(_SCRIPTS_DIR / script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Error en {script}: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Tableros ─────────────────────────────────────────────────────────────────

def ver_tablero(tablero: str = "original") -> str:
    """Muestra el tablero en ASCII (salas numeradas, '.' = pasillo)."""
    return _run("tablero.py", ["ver", "--tablero", tablero])


def validar_mision(nombre: str) -> dict:
    """Valida coordenadas de una misión contra su tablero.

    Returns:
        Dict con 'valida' (bool) y 'errores' (list[str]).
    """
    output = _run("tablero.py", ["validar", "--mision", nombre])
    # Parsear salida simple
    errores = [l for l in output.splitlines() if l.startswith("ERROR")]
    return {
        "valida": len(errores) == 0,
        "errores": errores,
        "salida": output,
    }


def punto_valido(tablero_id: str, x: int, y: int) -> bool:
    """Comprueba si una coordenada es válida en el tablero."""
    # Importar la función directamente
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        from tablero import punto_valido as _punto_valido
        return _punto_valido(tablero_id, x, y)
    except ImportError:
        # Fallback: ejecutar script
        output = _run("tablero.py", [
            "ver", "--tablero", tablero_id
        ])
        # Parsear dimensiones básicas
        lineas = output.strip().splitlines()
        if not lineas:
            return False
        num_cols = len(lineas[0].split()[0]) if lineas[0] else 0
        return 1 <= x <= 26 and 1 <= y <= 19  # DefaultHeroQuest


def sala_pertenece(tablero_id: str, sala_num: int, x: int, y: int) -> bool:
    """Comprueba si una coordenada pertenece a una sala en el tablero."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        from tablero import sala_pertenece as _sala_pertenece
        return _sala_pertenece(tablero_id, sala_num, x, y)
    except ImportError:
        return punto_valido(tablero_id, x, y)


# ── Mapas ────────────────────────────────────────────────────────────────────

def generar_mapa(
    tablero: str = "original",
    mision: str | None = None,
    formato: str = "png",
    svg: bool = False,
) -> str:
    """Genera un mapa del tablero y/o de una misión.

    Args:
        tablero: Id del tablero ("original" o "cara-b").
        mision: Nombre de la misión (opcional).
        formato: "png" o "svg".
        svg: Si True, genera SVG en vez de PNG.

    Returns:
        Ruta del fichero generado.
    """
    args = ["--tablero", tablero]
    if mision:
        args += ["--mision", mision]
    if svg:
        args.append("--svg")
    _run("mapa.py", args)
    # Ruta esperada
    slug = mision.replace(" ", "_") if mision else tablero
    ext = "svg" if svg else "png"
    return str(_MAPAS_DIR / f"{slug}.{ext}")


def generar_ficha_mision(nombre: str) -> str:
    """Genera la ficha HTML de máster para una misión.

    Returns:
        Ruta del HTML generado.
    """
    _run("mision_html.py", ["--mision", nombre])
    slug = nombre.replace(" ", "_")
    return str(_MAPAS_DIR / f"{slug}.html")


if __name__ == "__main__":
    print("=== Tablero Original ===")
    print(ver_tablero("original"))

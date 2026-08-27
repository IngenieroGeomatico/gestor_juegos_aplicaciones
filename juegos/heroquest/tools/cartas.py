"""Herramientas de generación de cartas.

Envuelve los scripts existentes (`carta_item.py`, `imprimir_cartas.py`)
para que el agente pueda generar cartas sin construir comandos raw.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_CARTAS_DIR = Path(__file__).resolve().parent.parent / "cartas"


def _run(script: str, args: list[str]) -> str:
    """Ejecuta un script con uv run y devuelve stdout."""
    cmd = [sys.executable, str(_SCRIPTS_DIR / script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Error en {script}: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Cartas de héroe ──────────────────────────────────────────────────────────

def generar_carta(
    nombre: str,
    cara: str = "ambas",
    formato: str = "png",
) -> str:
    """Genera la carta de un héroe.

    Args:
        nombre: Nombre del personaje (ej. "Bárbaro").
        cara: "anverso", "dorso" o "ambas".
        formato: "png", "svg" o "png,svg".

    Returns:
        Ruta del fichero generado.
    """
    _run("carta_item.py", [
        "--nombre", nombre,
        "--cara", cara,
        "--formato", formato,
    ])
    # Devolver ruta esperada
    slug = nombre.replace(" ", "_")
    if "," in formato:
        return str(_CARTAS_DIR / f"{slug}.png")
    ext = formato if formato in ("png", "svg") else "png"
    return str(_CARTAS_DIR / f"{slug}.{ext}")


def generar_cartas_todas(cara: str = "ambas", formato: str = "png") -> list[str]:
    """Genera cartas de todos los personajes registrados."""
    from .datos import listar_personajes
    rutas = []
    for p in listar_personajes():
        try:
            ruta = generar_carta(p["nombre"], cara=cara, formato=formato)
            rutas.append(ruta)
        except Exception as e:
            print(f"⚠ No se pudo generar carta de {p['nombre']}: {e}")
    return rutas


# ── Impresión PDF ────────────────────────────────────────────────────────────

def imprimir_cartas(
    cartas: list[str] | None = None,
    disposicion: str = "junta",
) -> str:
    """Genera un PDF A4 para imprimir cartas.

    Args:
        cartas: Lista de nombres de cartas. Si None, imprime todas.
        disposicion: "junta" (anverso|dorso doblable) o "separada" (doble cara).

    Returns:
        Ruta del PDF generado.
    """
    args = ["--disposicion", disposicion]
    if cartas:
        for c in cartas:
            args += ["--carta", c]
    else:
        args.append("--todo")
    _run("imprimir_cartas.py", args)
    slug_disp = "junta" if disposicion == "junta" else "separada"
    return str(_CARTAS_DIR / f"mision_{slug_disp}.pdf")


def listar_cartas_generadas() -> list[str]:
    """Lista cartas ya generadas en cartas/."""
    if not _CARTAS_DIR.exists():
        return []
    return sorted(f.name for f in _CARTAS_DIR.iterdir() if f.suffix == ".png")


if __name__ == "__main__":
    print("Cartas generadas:", listar_cartas_generadas())

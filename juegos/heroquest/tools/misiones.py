"""Herramientas de creación de misiones.

Envuelve `nueva_mision.py` y añade lógica de sugerencia de monstruos
basada en el nivel de la misión.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from data_store import cargar, cargar_json  # noqa: E402


def _run(script: str, args: list[str]) -> str:
    """Ejecuta un script con uv run y devuelve stdout."""
    cmd = [sys.executable, str(_SCRIPTS_DIR / script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Error en {script}: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Crear misión ─────────────────────────────────────────────────────────────

def crear_mision(
    nombre: str,
    tablero: str,
    nivel: int,
    introduccion: str,
    objetivo: str,
    recompensa: str,
    entrada_heroes: list[dict],
    puertas: list[dict],
    salas: list[dict],
) -> dict:
    """Crea una misión completa y la guarda en JSON.

    Args:
        nombre: Nombre evocador de la misión.
        tablero: Id del tablero ("original" o "cara-b").
        nivel: Dificultad 1-5.
        introduccion: Texto ambiental (2-3 frases).
        objetivo: Qué deben hacer los héroes.
        recompensa: Recompensa al completar.
        entrada_heroes: Lista de {x, y} de entrada.
        puertas: Lista de {x, y} de puertas.
        salas: Lista de {numero, nombre, descripcion, monstruos[], tesoros[]}.

    Returns:
        Dict con la misión creada.
    """
    mision = {
        "nombre": nombre,
        "tablero": tablero,
        "nivel": nivel,
        "introduccion": introduccion,
        "objetivo": objetivo,
        "recompensa": recompensa,
        "entrada_heroes": entrada_heroes,
        "puertas": puertas,
        "salas": salas,
    }

    # Guardar directamente en JSON
    misiones = cargar("misiones")
    if any(m.get("nombre") == nombre for m in misiones):
        raise ValueError(f"Ya existe una misión llamada '{nombre}'")
    misiones.append(mision)
    ruta = _DATA_DIR / "misiones.json"
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(misiones, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return mision


# ── Sugerencia de monstruos ──────────────────────────────────────────────────

_TABLA_MONSTRUOS = {
    1: {  # Nivel 1: fáciles
        "monstruos": ["Trasgo", "Esqueleto"],
        "por_sala": (2, 3),
        "peso_ataque": 2,  # Media de A del pool
        "peso_defensa": 1,
    },
    2: {  # Nivel 2: medios
        "monstruos": ["Orco", "Zombi", "Esqueleto"],
        "por_sala": (3, 4),
        "peso_ataque": 2,
        "peso_defensa": 2,
    },
    3: {  # Nivel 3: difíciles
        "monstruos": ["Orco", "Momia", "Fimir"],
        "por_sala": (3, 5),
        "peso_ataque": 3,
        "peso_defensa": 3,
    },
    4: {  # Nivel 4: muy difíciles
        "monstruos": ["Fimir", "Guerrero del Caos", "Momia"],
        "por_sala": (4, 6),
        "peso_ataque": 3,
        "peso_defensa": 3,
    },
    5: {  # Nivel 5+:精英
        "monstruos": ["Gárgola", "Abominación", "Guerrero del Terror"],
        "por_sala": (5, 8),
        "peso_ataque": 3,
        "peso_defensa": 4,
    },
}


def sugerir_monstruos(nivel: int, n_salas: int) -> list[dict]:
    """Sugiere distribución de monstruos según nivel y número de salas.

    Returns:
        Lista de dicts [{sala: int, monstruos: [{nombre, x, y}]}]
        con posiciones estimadas (el agente debe ajustar a coordenadas reales).
    """
    nivel = max(1, min(5, nivel))
    config = _TABLA_MONSTRUOS[nivel]
    min_n, max_n = config["por_sala"]
    tipos = config["monstruos"]

    resultado = []
    for i in range(1, n_salas + 1):
        import random
        n_monstruos = random.randint(min_n, max_n)
        monstruos_sala = []
        for _ in range(n_monstruos):
            tipo = random.choice(tipos)
            monstruos_sala.append({
                "nombre": tipo,
                "x": 0,  # El agente debe ajustar
                "y": 0,
            })
        resultado.append({
            "sala": i,
            "monstruos": monstruos_sala,
        })

    return resultado


def sugerir_tesoro(nivel: int) -> list[str]:
    """Sugiere tesoros según el nivel de la misión.

    Returns:
        Lista de nombres de tesoros sugeridos.
    """
    tesoros_nivel = {
        1: ["Poción de curación", "Daga"],
        2: ["Poción de curación", "Espada corta", "Yelmo"],
        3: ["Poción de curación", "Hacha de batalla", "Escudo"],
        4: ["Poción de curación", "Mandoble", "Ballesta"],
        5: ["Poción de curación", "Armadura de placas", "Espada de gemas"],
    }
    nivel = max(1, min(5, nivel))
    return tesoros_nivel.get(nivel, ["Poción de curación"])


if __name__ == "__main__":
    print("=== Sugerencia nivel 1, 3 salas ===")
    import json
    print(json.dumps(sugerir_monstruos(1, 3), indent=2, ensure_ascii=False))

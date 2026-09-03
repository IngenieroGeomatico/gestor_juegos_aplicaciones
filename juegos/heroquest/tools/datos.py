"""Herramientas de acceso a datos del juego.

Reutiliza `data_store.py` (ya existente en scripts/) como backend.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Añadir scripts/ al path para reutilizar data_store
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from data_store import cargar, cargar_json, slug  # noqa: E402


# ── Personajes ───────────────────────────────────────────────────────────────

def listar_personajes() -> list[dict]:
    """Devuelve todos los personajes jugadores."""
    return cargar("personajes")


def buscar_personaje(nombre: str) -> dict | None:
    """Busca un personaje por nombre exacto."""
    for p in cargar("personajes"):
        if p.get("nombre") == nombre:
            return p
    return None


def estadisticas_grupo() -> dict:
    """Resumen de stats medios del grupo actual (todos los personajes).

    Útil para balancear encuentros rápidamente.
    """
    personajes = cargar("personajes")
    if not personajes:
        return {"media_ataque": 0, "media_defensa": 0, "media_cuerpo": 0,
                "media_mente": 0, "n": 0}
    n = len(personajes)
    return {
        "n": n,
        "media_ataque": round(sum(p.get("ataque", 0) for p in personajes) / n, 1),
        "media_defensa": round(sum(p.get("defensa", 0) for p in personajes) / n, 1),
        "media_cuerpo": round(sum(p.get("cuerpo", 0) for p in personajes) / n, 1),
        "media_mente": round(sum(p.get("mente", 0) for p in personajes) / n, 1),
    }


# ── Armas / Equipo ──────────────────────────────────────────────────────────

def listar_armas() -> list[dict]:
    """Lista todas las armas con stats (desde equipo.json)."""
    return cargar("equipo")


def buscar_item(nombre: str) -> dict | None:
    """Busca un arma/armadura/poción por nombre exacto en equipo, tesoros y artefactos."""
    for fichero in ("equipo", "tesoros", "artefactos"):
        for a in cargar(fichero):
            if a.get("nombre") == nombre:
                return a
    return None


def listar_por_tipo(tipo_item: str) -> list[dict]:
    """Filtra equipo por subtipo: 'Arma cuerpo a cuerpo', 'Armadura', 'Poción', etc."""
    return [a for a in cargar("equipo") if (a.get("subtipo") or a.get("tipo")) == tipo_item]


# ── Monstruos ────────────────────────────────────────────────────────────────

def listar_monstruos() -> list[dict]:
    """Lista todos los monstruos disponibles."""
    return cargar("monstruos")


def buscar_monstruo(nombre: str) -> dict | None:
    """Busca un monstruo por nombre exacto."""
    for m in cargar("monstruos"):
        if m.get("nombre") == nombre:
            return m
    return None


# ── Hechizos ─────────────────────────────────────────────────────────────────

def listar_hechizos() -> list[dict]:
    """Lista todos los hechizos por escuela."""
    return cargar("hechizos")


def hechizos_por_escuela(escuela: str) -> list[dict]:
    """Filtra hechizos por escuela elemental (Fuego, Tierra, Terror, etc.)."""
    return [h for h in cargar("hechizos") if h.get("escuela") == escuela]


# ── Misiones ─────────────────────────────────────────────────────────────────

def listar_misiones() -> list[dict]:
    """Lista todas las misiones disponibles."""
    return cargar("misiones")


def buscar_mision(nombre: str) -> dict | None:
    """Busca una misión por nombre exacto."""
    for m in cargar("misiones"):
        if m.get("nombre") == nombre:
            return m
    return None


# ── Tableros ─────────────────────────────────────────────────────────────────

def listar_tableros() -> list[dict]:
    """Lista todos los tableros disponibles."""
    return cargar_json("tableros")


def tablero_por_id(tablero_id: str) -> dict | None:
    """Busca un tablero por su id ('original', 'cara-b', etc.)."""
    for t in cargar_json("tableros"):
        if t.get("id") == tablero_id:
            return t
    return None


# ── Fuentes / Enlaces ────────────────────────────────────────────────────────

def listar_fuentes() -> list[dict]:
    """Lista todas las fuentes (enlaces a PDFs, expansions, etc.)."""
    return cargar_json("fuentes")


def fuentes_por_categoria(categoria: str) -> list[dict]:
    """Filtra fuentes por categoría (Reglas, Misiones, Cartas, Losetas, etc.)."""
    return [f for f in cargar_json("fuentes") if f.get("categoria") == categoria]


def fuentes_por_expansion(expansion: str) -> list[dict]:
    """Filtra fuentes por expansión (Juego Base, Alquimia, etc.)."""
    return [f for f in cargar_json("fuentes") if f.get("expansion") == expansion]


def fuentes_por_prioridad(prioridad: str) -> list[dict]:
    """Filtra fuentes por prioridad (alta, media, baja)."""
    return [f for f in cargar_json("fuentes") if f.get("prioridad") == prioridad]


def buscar_fuente(nombre: str) -> dict | None:
    """Busca una fuente por nombre (búsqueda parcial, case-insensitive)."""
    nombre_lower = nombre.lower()
    for f in cargar_json("fuentes"):
        if nombre_lower in f.get("nombre", "").lower():
            return f
    return None


def fuentes_descargables() -> list[dict]:
    """Devuelve solo fuentes con file_id (descargables de Google Drive)."""
    return [f for f in cargar_json("fuentes") if f.get("file_id")]


# ── Utilidades ───────────────────────────────────────────────────────────────

def slug_nombre(nombre: str) -> str:
    """Convierte un nombre en slug seguro para ficheros."""
    return slug(nombre)


if __name__ == "__main__":
    # Demo rápida
    print("=== Personajes ===")
    for p in listar_personajes():
        print(f"  {p['nombre']} (A{p['ataque']} D{p['defensa']} Cu{p['cuerpo']} Me{p['mente']})")

    print("\n=== Armas ===")
    for a in listar_armas():
        print(f"  {a['nombre']} — A+{a['ataque']} D+{a['defensa']} ({a['coste']}g)")

    print("\n=== Monstruos ===")
    for m in listar_monstruos():
        print(f"  {m['nombre']} — A{m['ataque']} D{m['defensa']} Cu{m['cuerpo']}")

    print("\n=== Estadísticas del grupo ===")
    print(estadisticas_grupo())

    print("\n=== Fuentes (primeras 5) ===")
    for f in listar_fuentes()[:5]:
        print(f"  {f['nombre']} [{f['prioridad']}] — {f['categoria']}")

    print(f"\n  Total: {len(listar_fuentes())} fuentes")
    print(f"  Descargables: {len(fuentes_descargables())}")

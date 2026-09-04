"""Utilidades compartidas para leer y escribir los datos JSON de HeroQuest.

La E/S JSON genérica vive en ``comun/json_store.py`` (a nivel de repo). Este
módulo añade encima la capa específica de HeroQuest: la validación de `tipo`
contra ``TIPOS`` y las operaciones de alto nivel (añadir/eliminar/listar).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _cargar_json_store():
    """Carga ``comun/json_store.py`` por ruta, sin tocar ``sys.path``.

    Funciona con ``uv run <ruta>.py`` aunque el repo no esté instalado como
    paquete: sube hasta la raíz del repo (donde está ``comun/``) y lo importa
    con ``importlib``.
    """
    raiz = Path(__file__).resolve().parents[3]
    ruta = raiz / "comun" / "json_store.py"
    spec = importlib.util.spec_from_file_location("comun.json_store", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_js = _cargar_json_store()
slug = _js.slug

TIPOS = (
    "personajes",
    "monstruos",
    "hechizos",
    "tesoros",
    "equipo",
    "artefactos",
    "misiones",
)


def _ruta(tipo: str) -> Path:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo '{tipo}' no válido. Válidos: {', '.join(TIPOS)}")
    return DATA_DIR / f"{tipo}.json"


def cargar_json(nombre: str) -> list[dict]:
    """Carga un fichero JSON de data/ por nombre (sin extensión).

    A diferencia de `cargar`, no valida `nombre` contra TIPOS, por lo que
    sirve para ficheros auxiliares como `tableros`. Devuelve [] si no existe.
    """
    return _js.cargar_json(DATA_DIR, nombre)


def cargar(tipo: str) -> list[dict]:
    """Devuelve la lista de entradas de un tipo de dato."""
    _ruta(tipo)  # valida el tipo contra TIPOS
    return _js.cargar_json(DATA_DIR, tipo)


def guardar(tipo: str, datos: list[dict]) -> None:
    """Escribe la lista de entradas de un tipo de dato."""
    _ruta(tipo)  # valida el tipo antes de escribir
    _js.guardar_json(DATA_DIR, tipo, datos)


def existe(tipo: str, nombre: str) -> bool:
    """Comprueba si ya existe una entrada con ese nombre."""
    return any(e.get("nombre") == nombre for e in cargar(tipo))


def añadir(tipo: str, entrada: dict) -> None:
    """Añade una entrada si el nombre no existe ya."""
    nombre = entrada.get("nombre", "")
    if existe(tipo, nombre):
        raise ValueError(f"Ya existe '{nombre}' en {tipo}.json")
    datos = cargar(tipo)
    datos.append(entrada)
    guardar(tipo, datos)


def eliminar(tipo: str, nombre: str) -> bool:
    """Elimina una entrada por nombre. Devuelve True si se eliminó algo."""
    datos = cargar(tipo)
    restantes = [e for e in datos if e.get("nombre") != nombre]
    if len(restantes) == len(datos):
        return False
    guardar(tipo, restantes)
    return True


def listar(tipo: str) -> None:
    """Muestra por consola todas las entradas de un tipo."""
    datos = cargar(tipo)
    if not datos:
        print(f"No hay entradas en {tipo}.json")
        return
    print(f"\n=== {tipo.upper()} ({len(datos)}) ===")
    for e in datos:
        campos = [f"{k}: {v}" for k, v in e.items() if isinstance(v, (str, int, float))]
        print(f"- {e.get('nombre')}: " + " | ".join(campos))
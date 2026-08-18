"""Utilidades compartidas para leer y escribir los datos JSON de HeroQuest."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TIPOS = ("personajes", "armas", "monstruos", "hechizos", "misiones")


def _ruta(tipo: str) -> Path:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo '{tipo}' no válido. Válidos: {', '.join(TIPOS)}")
    return DATA_DIR / f"{tipo}.json"


def cargar_json(nombre: str) -> list[dict]:
    """Carga un fichero JSON de data/ por nombre (sin extensión).

    A diferencia de `cargar`, no valida `nombre` contra TIPOS, por lo que
    sirve para ficheros auxiliares como `tableros`. Devuelve [] si no existe.
    """
    ruta = DATA_DIR / f"{nombre}.json"
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def slug(nombre: str) -> str:
    """Convierte un nombre en un identificador seguro para ficheros.

    'Espada Larga' -> 'Espada_Larga'; conserva alfanuméricos y sustituye el
    resto por '_', recortando los '_' de los extremos.
    """
    return "".join(c if c.isalnum() else "_" for c in nombre).strip("_")


def cargar(tipo: str) -> list[dict]:
    """Devuelve la lista de entradas de un tipo de dato."""
    ruta = _ruta(tipo)
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar(tipo: str, datos: list[dict]) -> None:
    """Escribe la lista de entradas de un tipo de dato."""
    ruta = _ruta(tipo)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")


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
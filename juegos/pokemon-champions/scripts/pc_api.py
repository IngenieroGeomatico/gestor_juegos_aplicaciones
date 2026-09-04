"""Cliente HTTP y traducción de especies para la importación de datos.

Aísla el acceso a red (championsbattledata.com y PokeAPI) y el cacheado en disco
del resto de la lógica de ``importar_datos.py``. Todas las respuestas crudas se
cachean bajo ``configurar_cache(...)`` para poder regenerar los ficheros sin
volver a golpear la red.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

API_BASE = "https://championsbattledata.com"
POKEAPI = "https://pokeapi.co/api/v2"
UA = {"User-Agent": "gestor-juegos-bot/1.0"}

# Directorio de caché; se fija con configurar_cache() antes de descargar.
_CACHE_DIR: Path | None = None


def configurar_cache(cache_dir: Path) -> None:
    """Fija el directorio donde se cachean las respuestas crudas de las APIs."""
    global _CACHE_DIR
    _CACHE_DIR = cache_dir


def bajar(url: str, cache: str) -> dict:
    """Descarga JSON de una URL y lo cachea en ``<cache_dir>/<cache>``."""
    if _CACHE_DIR is None:
        raise RuntimeError("Llama a configurar_cache(...) antes de bajar(...).")
    ruta = _CACHE_DIR / cache
    if ruta.exists():
        with ruta.open(encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        datos = json.loads(resp.read().decode())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    time.sleep(0.1)
    return datos


def nombre_es(names: list | None) -> str:
    """Nombre en español de la lista `names` de PokeAPI ("" si no existe)."""
    for n in names or []:
        if n.get("language", {}).get("name") == "es":
            return n.get("name", "")
    return ""


def slug(nombre: str) -> str:
    """'Aura Sphere' -> 'aura-sphere'; 'King's Shield' -> 'kings-shield'."""
    s = nombre.strip().lower()
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def traducir_especie(slug_especie: str) -> dict:
    """Nombre en español, número y estatus legendario vía PokeAPI.

    Intenta /pokemon-species/{slug} y, si falla (formas regionales), /pokemon/{slug}
    resolviendo la especie base desde el enlace species.
    """
    for ruta in (f"pokemon-species/{slug_especie}",
                 f"pokemon/{slug_especie}",
                 f"pokemon-form/{slug_especie}"):
        try:
            raw = bajar(f"{POKEAPI}/{ruta}", f"pokeapi/{ruta}.json")
            if not isinstance(raw, dict) or "id" not in raw:
                continue
            if ruta.startswith("pokemon-species"):
                return {
                    "numero": raw.get("id"),
                    "nombre_es": nombre_es(raw.get("names")) or raw.get("name", ""),
                    "legendario": bool(raw.get("is_legendary") or raw.get("is_mythical")),
                }
            # pokemon o pokemon-form: resolver la especie base.
            sp_url = raw.get("species", {}).get("url")
            if not sp_url:
                sp_url = raw.get("pokemon", {}).get("url")  # pokemon-form
            if not sp_url:
                continue
            sp_key = sp_url.split("/api/v2/")[-1]
            sp = bajar(sp_url, f"pokeapi/{sp_key}")
            return {
                "numero": sp.get("id"),
                "nombre_es": nombre_es(sp.get("names")) or raw.get("name", ""),
                "legendario": bool(sp.get("is_legendary") or sp.get("is_mythical")),
            }
        except Exception:
            continue
    return {}

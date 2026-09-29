"""Prepara un perfil de Firefox del usuario para que lo use el bot.

Por qué hace falta: el Firefox de Playwright va por detrás del del sistema, y
Firefox se niega a abrir un perfil usado por una versión más nueva. El refusal
es explícito y corta el arranque antes de abrir nada:

    This profile was last used with a newer version of this application.
    Please create a new profile.

En esta máquina el Firefox de Playwright es el 155 y el del perfil, el 156. No
hay variable de entorno que lo esquive (se comprobó: no existe
`MOZ_ALLOW_LEGACY_PROFILES` en ese binario), pero el registro de versión está a
la vista en `compatibility.ini` del propio perfil:

    [Compatibility]
    LastVersion=156.0.1_20260921121718/20260921121718

Bajar ese número a la versión del Firefox de Playwright hace que lo acepte, y
probado: el bot entra y lee la cuenta `Radi__7` con su partida guardada.

Por seguridad se **copia** el perfil en vez de escribir en el original. Es
importante por dos motivos:

- El Firefox del usuario puede estar abierto y su perfil tiene bloqueos; tocarlo
  en caliente es pedir que se corrompa.
- Un perfil de más de 200 MB con la sesión guardada no es un sitio donde dejar
  que el bot lo malgaste experimenting.

El riesgo de bajar la versión sería que el Firefox antiguo estropeara el perfil,
pero aquí el caso es al revés de lo worrying: dentro de unos días tu Firefox 156
abrirá algo que escribió el 155, y eso es avanzar de versión, no retroceder.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

# El destino por defecto: fuera del perfil del usuario, y ya está en el
# `.gitignore` (son cachés de cientos de MB).
DESTINO_DEFECTO = Path(__file__).resolve().parent.parent / "data" / "bot" / "perfil-usuario"


def version_firefox_playwright() -> str:
    """Versión del Firefox que trae Playwright (p. ej. `155.0`)."""
    try:
        import playwright  # noqa: F401
        from pathlib import Path as _P

        raiz = _P(playwright.__file__).parent
        cand = sorted(raiz.glob("firefox-*/firefox/firefox"))
        if not cand:
            cand = sorted(raiz.glob("firefox-*/firefox/firefox.exe"))
        if cand:
            out = subprocess.run([str(cand[0]), "--version"],
                                 capture_output=True, text=True, timeout=30)
            m = re.search(r"(\d+)\.(\d+)", out.stdout)
            if m:
                return f"{m.group(1)}.{m.group(2)}"
    except Exception:  # noqa: BLE001
        pass
    return "155.0"


def ajustar_compatibilidad(perfil: Path, version: str | None = None) -> bool:
    """Baja `LastVersion` en `compatibility.ini`. Devuelve si lo cambió."""
    ini = perfil / "compatibility.ini"
    if not ini.exists():
        return False
    version = version or version_firefox_playwright()
    texto = ini.read_text(encoding="utf-8", errors="ignore")
    nuevo, n = re.subn(r"^LastVersion=.*$", f"LastVersion={version}",
                       texto, flags=re.M)
    if n:
        ini.write_text(nuevo, encoding="utf-8")
    return bool(n)


def preparar(origen: Path, destino: Path = DESTINO_DEFECTO,
            forzar: bool = False) -> Path:
    """Copia el perfil y lo deja compatible. Devuelve la ruta del destino."""
    origen = Path(origen).expanduser()
    destino = Path(destino)
    if not origen.is_dir():
        raise SystemExit(f"el perfil de origen no existe: {origen}")
    if destino.exists():
        if not forzar:
            return destino
        shutil.rmtree(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # `copytree` con symlinks preservados: el perfil tiene enlaces como
    # `lock -> 127.0.1.1:+...` y `cookies.sqlite-wal`, y resolverlos como
    # ficheros sueltos deja el perfil inconsistente.
    shutil.copytree(origen, destino, symlinks=True)
    # Los bloqueos son del Firefox que estuviera abierto: en la copia estorban.
    for sucio in ("lock", ".parentlock", "parent.lock", "SingletonLock"):
        (destino / sucio).unlink(missing_ok=True)
    ajustar_compatibilidad(destino)
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Copia un perfil de Firefox y lo deja utilizable por el bot.")
    ap.add_argument("origen", help="ruta del perfil de Firefox a copiar")
    ap.add_argument("--destino", default=str(DESTINO_DEFECTO))
    ap.add_argument("--forzar", action="store_true",
                    help="reemplaza el destino si ya existe")
    args = ap.parse_args()

    origen = Path(args.origen)
    destino = preparar(origen, Path(args.destino), args.forzar)
    tamaño = subprocess.run(["du", "-sh", str(destino)],
                            capture_output=True, text=True).stdout.split()[0]
    print(f"perfil preparado: {destino} ({tamaño})")
    print(f"  origen:  {origen}")
    print(f"  version Firefox de Playwright: {version_firefox_playwright()}")
    print()
    print("Para jugar con esta cuenta:")
    print(f"  uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \\")
    print(f"    --region Kanto --perfil {destino} --visible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

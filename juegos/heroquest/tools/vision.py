"""Herramientas de visión de mapas del libreto.

Envuelve los scripts de `rag/vision/` para digitalizar una misión desde el PDF
escaneado: extraer la página de mapa, alinearla con la cuadrícula 26x19 del
tablero y detectar/validar sus elementos (monstruos, letras, calaveras, etc.).

Flujo por misión:
  1. extraer_pagina_mapa()   -> mapa_m<N>.png
  2. dibujar_reticula()      -> validación visual de la cuadrícula
  3. leer_mapa()/detectar_monstruos() -> detección automática por color
  4. validar_montaje()       -> imágenes de validación contra misiones.json
  5. (usuario)               -> promueve detecciones a ground_truth

Detalles del pipeline en `skills/vision_mapa.md`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_HEROQUEST = _ROOT.parent
_VISION_DIR = _HEROQUEST / "rag" / "vision"
_IMAGENES_DIR = _VISION_DIR / "imagenes"
_PDF = (
    _HEROQUEST
    / "mapas"
    / "Libreto_de_Misiones_El_Despertar_First_Light_HQ21_Español_Heval.pdf"
)


def _run(script: str, args: list[str]) -> str:
    """Ejecuta un script de rag/vision con el intérprete actual."""
    cmd = [sys.executable, str(_VISION_DIR / script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"Error en {script}: {result.stderr.strip()}")
    return result.stdout.strip()


def automatico_extraer_mapa(
    mision: int,
    pdf: str | Path | None = None,
    dpi: int = 200,
    salidas: str | Path | None = None,
) -> str:
    """1) Extrae la página de mapa de la misión desde el PDF del libreto.

    La página viene determinada por la numeración del libreto (los mapas están
    en las páginas pares). Los mapas extraídos miden 1687x1198 px a 200 DPI.
    """
    salidas_dir = Path(salidas) if salidas else _IMAGENES_DIR
    salidas_dir.mkdir(parents=True, exist_ok=True)
    salida = salidas_dir / f"mapa_m{mision}.png"
    _run("extraer_mapa.py", [
        str(pdf or _PDF),
        str(mision),
        "--salida", str(salida),
        "--dpi", str(dpi),
    ])
    return str(salida)


def dibujar_reticula(
    mapa: str | Path,
    mision: str | None = None,
    salidas: str | Path | None = None,
) -> str:
    """2) Pinta la retícula 26x19 sobre el mapa para validar la alineación.

    La retícula cae sobre las esquinas leídas de `misiones_vision.json` para
    la clave de esa misión (si la clave no existe, reporta el error).
    """
    salidas_dir = Path(salidas) if salidas else _IMAGENES_DIR
    salidas_dir.mkdir(parents=True, exist_ok=True)
    nombre = Path(mapa).stem
    salida = salidas_dir / f"ret_{nombre}.png"
    _run("ret.py", [str(mapa), mision or nombre, "--salida", str(salida)])
    return str(salida)


def leer_mapa(
    mapa: str | Path,
    mision: str | None = None,
    salidas: str | Path | None = None,
) -> str:
    """3a) Detecta por color letras (rojo), calaveras (negro) y monstruos (verde).

    Devuelve la imagen con las detecciones dibujadas; los datos quedan en
    `misiones_vision.json` bajo `detecciones` para la clave de la misión.
    """
    salidas_dir = Path(salidas) if salidas else _IMAGENES_DIR
    salidas_dir.mkdir(parents=True, exist_ok=True)
    nombre = Path(mapa).stem
    salida = salidas_dir / f"leer_{nombre}.png"
    _run("leer_mapa.py", [str(mapa), mision or nombre, "--salida", str(salida)])
    return str(salida)


def detectar_monstruos(
    mapa: str | Path,
    key: str | None = None,
    salidas: str | Path | None = None,
) -> str:
    """3b) Localiza los iconos de monstruo (celdas verdes) y los numera V1..Vn."""
    salidas_dir = Path(salidas) if salidas else _IMAGENES_DIR
    salidas_dir.mkdir(parents=True, exist_ok=True)
    nombre = Path(mapa).stem
    _run("validar_monstruos.py", [
        str(mapa),
        "--key", key or f"M{nombre[-1]}",
        "--salidas", str(salidas_dir),
    ])
    return str(salidas_dir / f"monstruos_{nombre}.png")


def validar_montaje(
    mapa: str | Path,
    key: str,
    mision: str,
    entrada: str | None = None,
    salida: str | None = None,
    por_sala: bool = False,
    salidas: str | Path | None = None,
) -> list[str]:
    """5) Genera imágenes de validación pintando el montaje de misiones.json.

    Compara lo modelado en `data/misiones.json` contra el mapa real, una imagen
    por tipo de elemento (monstruos, tesoros, puertas, letras, etc.).
    """
    salidas_dir = Path(salidas) if salidas else _IMAGENES_DIR
    salidas_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(mapa),
        "--key", key,
        "--mision", mision,
        "--salidas", str(salidas_dir),
    ]
    if entrada:
        args += ["--entrada", entrada]
    if salida:
        args += ["--salida", salida]
    if por_sala:
        args.append("--por-sala")
    _run("validar_mision.py", args)
    pre = mision.replace(" ", "_")
    # Imágenes generadas: pre_<tipo>.png; la rejilla siempre existe.
    rejilla = salidas_dir / f"{pre}_rejilla.png"
    return [str(p) for p in salidas_dir.glob(f"{pre}_*.png")] or [str(rejilla)]


if __name__ == "__main__":
    print("Vision pipeline:", list(sorted(_VISION_DIR.glob("*.py"))))
    print("Imagenes:", list(sorted(_IMAGENES_DIR.glob("mapa_*.png")))[-5:])
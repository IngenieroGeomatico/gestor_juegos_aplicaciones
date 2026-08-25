"""Exporta cada capa de un fichero .xcf de GIMP a su propio PNG.

Usa GIMP en modo headless (`gimp -i`) como motor de decodificación, así que
soporta cualquier versión de XCF que soporte el GIMP instalado. Para cada capa
se crea una imagen temporal de una sola capa (vía `gimp-layer-new-from-drawable`,
la forma correcta de copiar entre imágenes en GIMP 3) y se exporta como PNG,
conservando la transparencia. Los ficheros se nombran con el `slug` del nombre
de la capa (`Hechizo de aire` -> `hechizo_de_aire.png`).

Ejemplos:

    uv run juegos/heroquest/scripts/exportar_xcf.py "fuentes/cartas.xcf"
    uv run juegos/heroquest/scripts/exportar_xcf.py cartas.xcf --salida dorsos/
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from data_store import slug

# Plantilla Scheme que ejecuta GIMP: exporta cada capa como PNG y escribe en
# stderr líneas "MAPEO|<índice>|<nombre de capa>" para que Python las renombre.
SCM = """(define (exportar imagen capa idx dir)
  (let* ((nombre (car (gimp-item-get-name capa)))
         (nueva (car (gimp-image-new
                        (car (gimp-drawable-get-width capa))
                        (car (gimp-drawable-get-height capa))
                        (car (gimp-image-get-base-type imagen)))))
         (copia (car (gimp-layer-new-from-drawable capa nueva))))
    (gimp-image-insert-layer nueva copia 0 -1)
    (gimp-layer-set-offsets copia 0 0)
    (file-png-export RUN-NONINTERACTIVE nueva
                     (string-append dir "/capa-" (number->string idx) ".png"))
    (gimp-message (string-append "MAPEO|" (number->string idx) "|" nombre))))

(let* ((imagen (car (gimp-file-load RUN-NONINTERACTIVE "{xcf}" "capas.xcf")))
       (capas (vector->list (car (gimp-image-get-layers imagen)))))
  (let bucle ((resto capas) (i 1))
    (if (pair? resto)
        (begin (exportar imagen (car resto) i "{dir}")
               (bucle (cdr resto) (+ i 1))))))
"""


def _escapar(ruta: str) -> str:
    """Escapa una ruta para incrustarla como literal de cadena de Scheme."""
    return ruta.replace("\\", "\\\\").replace('"', '\\"')


def exportar_capas(xcf: Path, salida: Path, gimp: str) -> list[Path]:
    """Exporta las capas de `xcf` a `salida` y devuelve la lista de PNG creados."""
    salida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        scm = Path(tmp) / "exportar.scm"
        scm.write_text(SCM.format(xcf=_escapar(str(xcf)), dir=_escapar(str(salida))))
        proceso = subprocess.run(
            [
                gimp, "-i", "-d", "-f",
                "--batch-interpreter=plug-in-script-fu-eval",
                "-b", f'(load "{_escapar(str(scm))}")',
                # En GIMP 3 el fiable es --quit (CLI), no (gimp-quit 0).
                "--quit",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # Del registro de GIMP nos quedamos con el mapeo índice -> nombre.
        mapeo: dict[str, str] = {}
        for linea in (proceso.stdout + proceso.stderr).splitlines():
            if m := re.search(r"MAPEO\|(\d+)\|(.*)$", linea):
                mapeo[m.group(1)] = m.group(2).strip()

        if not mapeo:
            sys.stderr.write(proceso.stderr[-2000:])
            raise RuntimeError("GIMP no exportó ninguna capa (¿ruta correcta?)")

        creados: list[Path] = []
        usados: set[str] = set()
        for indice, nombre in sorted(mapeo.items(), key=lambda kv: int(kv[0])):
            origen = salida / f"capa-{indice}.png"
            if not origen.exists():
                print(f"AVISO: falta {origen}", file=sys.stderr)
                continue
            destino_base = slug(nombre) or f"capa_{indice}"
            destino, sufijo = destino_base, 2
            while destino in usados:
                destino = f"{destino_base}_{sufijo}"
                sufijo += 1
            usados.add(destino)
            final = salida / f"{destino}.png"
            origen.rename(final)
            creados.append(final)
            print(f"{nombre} -> {final.name}")
        return creados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("xcf", type=Path, help="fichero .xcf de GIMP")
    parser.add_argument("--salida", type=Path, default=None, help="carpeta destino (defecto: junto al .xcf, en <nombre>_capas/)")
    parser.add_argument("--gimp", default="gimp", help="ejecutable de GIMP (defecto: %(default)s)")
    args = parser.parse_args(argv)

    if not args.xcf.is_file():
        parser.error(f"no existe {args.xcf}")
    salida = args.salida or args.xcf.with_name(f"{args.xcf.stem}_capas")
    exportar_capas(args.xcf, salida, args.gimp)
    return 0


if __name__ == "__main__":
    sys.exit(main())

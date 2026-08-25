"""Quita el fondo blanco a las ilustraciones para las cartas (IA, p. ej. nanobanana).

Las imágenes generadas con IA vienen sobre fondo blanco opaco; para componerlas
en las cartas hace falta un PNG con transparencia. Este script convierte el
blanco del fondo en alpha conservando los blancos INTERIORES de la ilustración
(ojos, dientes, brillos...), que no deben volverse transparentes.

Método (solo Pillow, sin dependencias nuevas):

1. Distancia al blanco por píxel (Chebyshov: la mayor diferencia de canal).
2. Máscara de píxeles "casi blancos" (distancia <= --umbral).
3. Se inunda esa máscara desde el borde del lienzo: lo alcanzado es el FONDO
   (alpha 0 en su núcleo); los blancos rodeados por la ilustración quedan
   intactos.
4. Los huecos de blanco que la figura cierra sin conectar con el borde (brazos
   cruzados, hueco entre piernas...) no los alcanza la inundación; se detectan
   como manchas grandes de blanco neutro interiores (los brillos del arte
   están teñidos y se quedan fuera) y se unen al fondo. Los blancos pequeños
   (ojos, perlas, brillos) se conservan: las semillas se erosionan y se exige
   un área mínima (--area-huecos, 0 para desactivar).
4. En una banda fina alrededor del fondo (--radio, los bordes antialiaseados)
   el alpha es parcial (proporcional a la distancia al blanco) y el color se
   "des-mezcla" (el píxel era mezcla de ilustración sobre blanco), para que no
   quede un halo lechoso al volverse transparente.
5. Se recorta al contenido opaco (sobra mucho lienzo vacío alrededor de la
   figura); se desactiva con --sin-recortar.

Ejemplos:

    uv run juegos/heroquest/scripts/quitar_fondo_blanco.py fuentes/bárbaro_ia.png
    uv run juegos/heroquest/scripts/quitar_fondo_blanco.py fuentes/ia/           # carpeta
    uv run juegos/heroquest/scripts/quitar_fondo_blanco.py a.png b.png --sin-recortar
    uv run juegos/heroquest/scripts/quitar_fondo_blanco.py a.png --umbral 40 --en-sitio

Por defecto escribe `<nombre>_sin_fondo.png` junto a cada entrada; `--en-sitio`
sobreescribe cada entrada con su versión transparente (siempre en PNG: si la
entrada era JPEG u otro formato sin alpha, queda sustituida por su `.png`) y
`--salida <dir>` guarda todos los resultados en una carpeta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Extensiones de imagen que acepta el script.
EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp"}

# Umbral por defecto de "casi blanco" (distancia máxima de canal al blanco).
UMBRAL_DEFECTO = 32

# Para los huecos interiores: blanco tan tolerante como el del borde (los
# huecos suelen estar algo sombreados), NEUTRO de color (los brillos del arte
# están teñidos: verde de la armadura, cálido de la piel...) y área mínima
# como % del lienzo, para no comerse ojos ni perlas.
UMBRAL_HUECOS_DEFECTO = 32
AREA_HUECOS_DEFECTO = 0.01
DISPERSION_HUECOS_DEFECTO = 12


def aplanar_sobre_blanco(img: Image.Image) -> Image.Image:
    """Aplana la imagen a RGB; si ya tenía alpha, la compone sobre blanco."""
    if img.mode in ("RGBA", "LA", "PA"):
        base = Image.new("RGBA", img.size, (255, 255, 255, 255))
        base.alpha_composite(img.convert("RGBA"))
        return base.convert("RGB")
    return img.convert("RGB")


def distancia_al_blanco(img: Image.Image) -> Image.Image:
    """Distancia de cada píxel al blanco (Chebyshov: máx. diferencia de canal)."""
    bandas = img.split()
    blanco = Image.new("L", img.size, 255)
    dist = ImageChops.subtract(blanco, bandas[0])
    for banda in bandas[1:]:
        dist = ImageChops.lighter(dist, ImageChops.subtract(blanco, banda))
    return dist


def fondo_desde_borde(mascara: Image.Image) -> Image.Image:
    """Región casi-blanca conectada con el borde del lienzo (el fondo real).

    `mascara` es L: 255 = casi blanco. Se rellena por inundación desde fuera;
    para sembrar todo el perímetro de golpe se añade un marco de 1 px antes.
    """
    w, h = mascara.size
    lienzo = Image.new("L", (w + 2, h + 2), 0)
    lienzo.paste(mascara, (1, 1))
    ImageDraw.Draw(lienzo).rectangle([0, 0, w + 1, h + 1], outline=255)
    ImageDraw.floodfill(lienzo, (0, 0), 128)
    # 128 = alcanzado por la inundación (fondo); el resto de casi-blancos son
    # blancos interiores de la ilustración y deben seguir opacos.
    return lienzo.crop((1, 1, w + 1, h + 1)).point(lambda v: 255 if v == 128 else 0)


def _desmezclar(v: int, a: int) -> int:
    """Color real de un píxel que era una mezcla `a/255` sobre blanco."""
    f = max(a, 24) / 255.0
    real = (v - (1.0 - f) * 255.0) / f
    return max(0, min(255, round(real)))


def detectar_huecos(
    rgb: Image.Image,
    dist: Image.Image,
    fondo: Image.Image,
    umbral_huecos: int,
    area_min_px: int,
    erosion: int = 1,
    dispersion_max: int = DISPERSION_HUECOS_DEFECTO,
) -> Image.Image:
    """Manchas grandes de blanco neutro cerradas por la figura (huecos).

    La inundación desde el borde no alcanza los blancos encerrados entre
    brazos, piernas, armas... Se detectan aquí: casi-blancos interiores de
    color neutro (dispersión de canales <= --dispersion-huecos: los brillos
    del arte están teñidos y se quedan fuera), cuya mancha tras la apertura
    morfológica sigue viva —así los detalles finos (ojos, perlas) no
    siembran— y con área mínima por mancha. Devuelve la máscara a unir al
    fondo.
    """
    r, g, b = rgb.split()
    dispersion = ImageChops.subtract(
        ImageChops.lighter(ImageChops.lighter(r, g), b),
        ImageChops.darker(ImageChops.darker(r, g), b),
    )
    casi = ImageChops.multiply(
        dist.point(lambda d: 255 if d <= umbral_huecos else 0),
        dispersion.point(lambda s: 255 if s <= dispersion_max else 0),
    )
    candidato = ImageChops.subtract(casi, fondo)
    semillas = candidato.filter(ImageFilter.MinFilter(2 * erosion + 1))
    semillas = semillas.filter(ImageFilter.MaxFilter(2 * erosion + 1))
    caja = semillas.getbbox()
    if caja is None:
        return Image.new("L", dist.size, 0)

    restante = candidato.crop(caja)
    rpx = restante.load()
    spx = semillas.crop(caja).load()
    ancho, alto = restante.size
    huecos = Image.new("L", restante.size, 0)
    for y in range(alto):
        for x in range(ancho):
            if spx[x, y] != 255 or rpx[x, y] != 255:
                continue
            ImageDraw.floodfill(restante, (x, y), 128)
            mancha = restante.point(lambda v: 255 if v == 128 else 0)
            if mancha.histogram()[255] >= area_min_px:
                huecos = ImageChops.lighter(huecos, mancha)
            restante.paste(0, None, mancha)

    resultado = Image.new("L", dist.size, 0)
    resultado.paste(huecos, caja[:2])
    return resultado


def desmezclar_bandas(
    rgb: Image.Image, alpha: Image.Image, zona: Image.Image
) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Bandas RGB con el color recomuesto en el borde antialiaseado.

    Un píxel semicubierto del borde era una mezcla sobre blanco:
    observado = f·real + (1−f)·255, con f = alpha/255. Despejar `real` evita el
    halo lechoso cuando el píxel pasa a transparente. Solo se toca la banda
    `zona` y solo los píxeles con alpha parcial.
    """
    # Píxeles a recomponer: dentro de la zona y con alpha ni pleno ni nulo.
    parcial = ImageChops.multiply(zona, alpha.point(lambda v: 255 if 8 <= v <= 247 else 0))
    caja = parcial.getbbox()
    if caja is None:
        return tuple(rgb.split())

    tamano = (caja[2] - caja[0], caja[3] - caja[1])
    mbytes = parcial.crop(caja).tobytes()
    abytes = alpha.crop(caja).tobytes()
    nuevas = []
    for banda in rgb.split():
        vbytes = banda.crop(caja).tobytes()
        fuera = bytearray(vbytes)
        for i, (m, a, v) in enumerate(zip(mbytes, abytes, vbytes)):
            if m:
                fuera[i] = _desmezclar(v, a)
        recorte = Image.frombytes(banda.mode, tamano, bytes(fuera))
        nueva = banda.copy()
        nueva.paste(recorte, caja[:2])
        nuevas.append(nueva)
    return tuple(nuevas)


def _pad_a_proporcion(img: Image.Image, ratio: float) -> Image.Image:
    """Lienzo transparente con la proporción pedida (ancho/alto), contenido centrado.

    Con la imagen ya encajada en ese lienzo, un recorte "cover" a la misma
    proporción (el del ancla de la carta) no corta nada: encaje "contain".
    """
    w, h = img.size
    if w / h > ratio:
        ancho, alto = w, round(w / ratio)
    else:
        ancho, alto = round(h * ratio), h
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    lienzo.alpha_composite(img, ((ancho - w) // 2, (alto - h) // 2))
    return lienzo


def _aire_superior(img: Image.Image, ratio: float, holgura: float = 0.2) -> Image.Image:
    """Aire transparente arriba: el justo para que un "cover" centrado a
    `ratio` (el del ancla de la carta) deje `holgura` de ventana vacía por
    encima de la cabeza — si no, el ribete del nombre tapa la cara.

    El recorte centrado a `ratio` deja una ventana de alto V = w/ratio; para
    que la cabeza quede a `holgura`·V del borde superior de la ventana hay que
    añadir arriba p = h - (1 - 2·holgura)·V. El recorte se lleva los pies.
    """
    w, h = img.size
    exceso = round(h - (1 - 2 * holgura) * w / ratio)
    if exceso <= 0:
        return img
    lienzo = Image.new("RGBA", (w, h + exceso), (0, 0, 0, 0))
    lienzo.alpha_composite(img, (0, exceso))
    return lienzo


def sin_fondo(
    img: Image.Image,
    umbral: int = UMBRAL_DEFECTO,
    ganancia: float = 1.5,
    radio_borde: int = 2,
    recortar: bool = True,
    umbral_huecos: int = UMBRAL_HUECOS_DEFECTO,
    area_huecos: float = AREA_HUECOS_DEFECTO,
    erosion_huecos: int = 1,
    dispersion_huecos: int = DISPERSION_HUECOS_DEFECTO,
    lienzo_proporcion: float | None = None,
    aire_superior: float | None = None,
    aire_holgura: float = 0.2,
) -> Image.Image:
    """Devuelve la imagen en RGBA con el fondo blanco convertido en alpha."""
    rgb = aplanar_sobre_blanco(img)

    dist = distancia_al_blanco(rgb)
    casi_blanco = dist.point(lambda d: 255 if d <= umbral else 0)
    fondo = fondo_desde_borde(casi_blanco)

    # Huecos de blanco cerrados por la figura (no conectan con el borde).
    if area_huecos > 0:
        area_min_px = max(1, round(rgb.width * rgb.height * area_huecos / 100))
        huecos = detectar_huecos(
            rgb, dist, fondo, umbral_huecos, area_min_px, erosion_huecos, dispersion_huecos
        )
        fondo = ImageChops.lighter(fondo, huecos)

    # Núcleo del fondo (a >= 1 px del motivo): alpha 0, sin velos por el ruido
    # del blanco. Solo la banda que rodea al motivo gradúa el alpha (borde
    # antialiaseado); con --radio 0 queda una banda mínima de 1 px.
    nucleo = fondo.filter(ImageFilter.MinFilter(3))
    zona = fondo.filter(ImageFilter.MaxFilter(2 * radio_borde + 1)) if radio_borde > 0 else fondo
    zona = ImageChops.subtract(zona, nucleo)

    rampa = dist.point(lambda d: min(255, round(d * ganancia)))
    alpha = Image.composite(rampa, Image.new("L", rgb.size, 255), zona)
    alpha = Image.composite(Image.new("L", rgb.size, 0), alpha, nucleo)
    r, g, b = desmezclar_bandas(rgb, alpha, zona)

    resultado = Image.merge("RGBA", (r, g, b, alpha))

    if recortar:
        caja = alpha.getbbox()
        if caja:
            resultado = resultado.crop(caja)
    if lienzo_proporcion:
        resultado = _pad_a_proporcion(resultado, lienzo_proporcion)
    if aire_superior:
        resultado = _aire_superior(resultado, aire_superior, aire_holgura)
    return resultado


def procesar(entrada: Path, salida: Path, opciones: dict) -> None:
    with Image.open(entrada) as img:
        resultado = sin_fondo(img, **opciones)
    salida.parent.mkdir(parents=True, exist_ok=True)
    resultado.save(salida)
    print(f"{entrada.name} -> {salida}")


def reunir_entradas(rutas: list[Path]) -> list[Path]:
    """Expande carpetas a ficheros de imagen; omite salidas de ejecuciones previas."""
    ficheros: list[Path] = []
    for ruta in rutas:
        if ruta.is_dir():
            candidatos = sorted(p for p in ruta.iterdir() if p.suffix.lower() in EXTENSIONES)
        else:
            candidatos = [ruta]
        for f in candidatos:
            if f.stem.endswith("_sin_fondo"):
                continue
            ficheros.append(f)
    return ficheros


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("entradas", nargs="+", type=Path, help="imágenes o carpetas con imágenes")
    parser.add_argument("--salida", type=Path, default=None, help="carpeta destino para todos los resultados")
    parser.add_argument("--en-sitio", action="store_true", help="sobreescribe cada entrada con su versión transparente (PNG)")
    parser.add_argument("--umbral", type=int, default=UMBRAL_DEFECTO, help="tolerancia al blanco, 0-255 (defecto %(default)s)")
    parser.add_argument("--ganancia", type=float, default=1.5, help="dureza del alpha en el borde (defecto %(default)s)")
    parser.add_argument("--radio", type=int, default=2, help="px de banda antialiaseada alrededor del fondo (defecto %(default)s)")
    parser.add_argument("--umbral-huecos", type=int, default=UMBRAL_HUECOS_DEFECTO, help="blanco exigido a los huecos interiores, 0-255 (defecto %(default)s)")
    parser.add_argument("--area-huecos", type=float, default=AREA_HUECOS_DEFECTO, help="área mínima del hueco interior, en %% del lienzo; 0 la desactiva (defecto %(default)s)")
    parser.add_argument("--erosion-huecos", type=int, default=1, help="px de apertura morfológica de las semillas de hueco (defecto %(default)s)")
    parser.add_argument("--dispersion-huecos", type=int, default=DISPERSION_HUECOS_DEFECTO, help="neutralidad de color exigida al hueco: máx. diferencia entre canales (defecto %(default)s)")
    parser.add_argument("--lienzo-proporcion", type=float, default=None, help="remata en un lienzo transparente con esta proporción ancho/alto, contenido centrado (p. ej. 1 para los iconos)")
    parser.add_argument("--aire-superior", type=float, default=None, help="aire transparente arriba para que un cover a esta proporción (p. ej. 0.814, la de ph-arte) respete la cabeza")
    parser.add_argument("--holgura-arriba", type=float, default=0.2, help="con --aire-superior: fracción de la ventana que queda vacía sobre la cabeza, para no quedar bajo el ribete (defecto %(default)s)")
    parser.add_argument("--sin-recortar", action="store_true", help="no recorta al contenido opaco")
    args = parser.parse_args(argv)

    if args.en_sitio and args.salida is not None:
        parser.error("--en-sitio y --salida son excluyentes")

    ficheros = reunir_entradas(args.entradas)
    if not ficheros:
        print("No hay imágenes que procesar.", file=sys.stderr)
        return 1

    opciones = dict(
        umbral=args.umbral,
        ganancia=args.ganancia,
        radio_borde=args.radio,
        recortar=not args.sin_recortar,
        umbral_huecos=args.umbral_huecos,
        area_huecos=args.area_huecos,
        erosion_huecos=args.erosion_huecos,
        dispersion_huecos=args.dispersion_huecos,
        lienzo_proporcion=args.lienzo_proporcion,
        aire_superior=args.aire_superior,
        aire_holgura=args.holgura_arriba,
    )

    for f in ficheros:
        if args.en_sitio:
            destino = f.with_suffix(".png")
        elif args.salida is not None:
            destino = args.salida / f.name
        else:
            destino = f.with_name(f"{f.stem}_sin_fondo.png")
        try:
            procesar(f, destino, opciones)
            if args.en_sitio and f.suffix.lower() != ".png":
                f.unlink()  # el JPEG original queda sustituido por su PNG
        except Exception as e:  # noqa: BLE001 - seguir con el resto de imágenes
            print(f"ERROR con {f}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

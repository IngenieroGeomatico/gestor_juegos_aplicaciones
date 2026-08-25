# Origen y licencia de los recursos de `sources/`

Este fichero documenta de dónde viene cada recurso externo incorporado a esta
carpeta y bajo qué licencia se reutiliza. Todo lo que lleve el sello gráfico de
HeroQuest™ pertenece a sus propietarios (Hasbro / Avalon Hill / Milton Bradley)
y se usa aquí únicamente con fines de fan-made y no comerciales.

## Arte de cartas (AI artwork) — Mark Forster

Carpetas `Artwork/` y `all-testing-assets/`.

- **Origen:** HeroQuest Card Creator (https://mark-forster.itch.io/heroquest-card-creator),
  hilos de la comunidad "More Free HeroQuest-style artwork for anyone who wants it"
  (https://itch.io/t/5729783) y "Sharing My Personal Card Creator Library"
  (https://itch.io/t/5776376).
- **Autor:** Mark Forster (@markforster), autor de la herramienta.
- **Licencia:** el autor declara explícitamente que este arte es **gratuito y de
  uso libre** ("Everything is still free to use"). Es arte generado con IA a
  partir de su GPT personal, compartido para la comunidad como material de
  partida. No comercial; se usa para contenido fan.
- **Contenido:** personajes/monstruos/héroes (íconos y perfiles), bestias,
  encuentros, arte de hechizos, set de Zargon y 19 reversos temáticos
  (`Artwork/Back Artwork/`).

## Fondos de carta HQ 2021 — HeroQuest Card Creator (código)

Carpeta `arte_fondos_hq2021/`.

- **Origen:** repositorio del proyecto HeroQuest Card Creator
  (https://github.com/markforster/heroquest-card-creator), carpeta `src/assets/card-backgrounds/`.
- **Autor:** Mark Forster.
- **Licencia:** el proyecto es **GNU GPL v3.0**; los PNG se redistribuyen bajo los
  términos de esa licencia. En su mayoría son fondos de carta imitando el estilo
  de las cartas de HeroQuest 2021 (pergamino, marcos con lino, reversos con el
  "ojo"), a 750×1050 px (misma proporción que la carta 63×88 mm).

## Fuente Amarna (tipografía de las cartas)

Carpeta `fuentes/` (`Amarna-Regular.ttf`, `Amarna-Bold.ttf`, `Amarna-OFL.txt`).

- **Origen:** proyecto Amarna de Ian van Loon
  (https://github.com/ijvanl/Amarna), instancias estáticas TTF Regular y Bold.
- **Licencia:** **SIL Open Font License 1.1** (ver `fuentes/Amarna-OFL.txt`).
- **Por qué está aquí:** alternativa **libre** a la fuente comercial Carter Sans
  (ITC/Monotype, no redistribuible) que usan las cartas de HeroQuest 2021. Amarna
  es una **glyphic humanist sans** inspirada en *Albertus* — el mismo antepasado
  que influyó a Carter Sans —, con las serifas suaves ("flare") en las mayúsculas
  que caracterizan a la original, así que casa mucho mejor que una sans geométrica.
  Se embebe en el SVG como `@font-face` (data URI) para que resvg la use al
  rasterizar; se usan instancias estáticas Regular/Bold porque resvg no interpola
  fuentes variables.

> **Nota sobre Carter Sans:** era la fuente de los textos de carta del editor de
> Mark Forster, pero es **comercial** (ITC, "may not copy or distribute"). No se
> incluye en este repositorio; se usa Amarna como sustituta libre.

## Fuente Albert Sans (obsoleta)

- Sustituta anterior (geométrica humanista, OFL-1.1). Se reemplazó por Amarna,
  que se parece más a la Carter Sans original (serifas glyphic/flare). Los
  ficheros `AlbertSans*.ttf` pueden conservarse como reserva o eliminarse.
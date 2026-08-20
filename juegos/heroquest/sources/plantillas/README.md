# Plantillas de carta (SVG)

Las plantillas SVG de esta carpeta son la **fuente de verdad del diseño** de las
cartas de HeroQuest. `render_carta.py` las carga y solo inyecta el contenido
dinámico (nombre, arte, estadísticas, descripción). Puedes editarlas en
Inkscape y el resultado se refleja al regenerar las cartas.

## Índice

| Fichero | Cara | Maquetación | Tipos que la usan |
|---------|------|-------------|-------------------|
| [`anverso_stats.svg`](anverso_stats.svg) | anverso | stats | personaje, monstruo |
| [`anverso_descripcion.svg`](anverso_descripcion.svg) | anverso | descripcion | arma, armadura, poción, hechizo |
| [`verso_stats.svg`](verso_stats.svg) | reverso | stats | personaje (descripción en el reverso), monstruo |
| [`verso_descripcion.svg`](verso_descripcion.svg) | reverso | descripcion | arma, armadura, poción, hechizo |
| [`stats_cuadro.svg`](stats_cuadro.svg) | — | stats | cuadro de 5 stats que se coloca dentro de `ph-stats` |
| [`ficha_personaje.svg`](ficha_personaje.svg) | — | — | **esqueleto de ficha de personaje** para apuntar en la partida: retrato, cuerpo/mente (pips), armas y oro. Aún no la consume el pipeline; se rediseña en Inkscape |

Rejilla de diseño de todas las plantillas: **500 × 700** (`viewBox="0 0 500 700"`),
que corresponde a 63 × 88 mm reales a 300 DPI. `stats_cuadro` es la excepción:
usa su propio `viewBox="0 0 420 60"` y `render_carta.py` lo escala para
encajarlo en el ancla `ph-stats`.

## Contrato de plantilla

Ver el detalle completo en `scripts/plantillas.py`. Hay dos mecanismos:

1. **Marcadores de texto** `{{CLAVE}}` dentro de `<text>`/`<tspan>` o de
   atributos. Se sustituyen por su valor (los textos se escapan para XML;
   `{{COLOR}}` se inserta tal cual por ser un color hex):

   | Marcador | Plantilla(s) | Valor |
   |----------|--------------|-------|
   | `{{NOMBRE}}` | anversos | nombre de la carta |
   | `{{SUBTITULO}}` | anversos | tipo/clase/escuela bajo el título |
   | `{{LEYENDA}}` | versos | categoría del reverso (equipo, tesoro, enemigo, heroe, magia) |
   | `{{COLOR}}` | todas | color de acento del tipo de carta |
   | `{{LABEL1..5}}` | `stats_cuadro` | etiqueta de cada estadística |
   | `{{VALOR1..5}}` | `stats_cuadro` | valor de cada estadística |

2. **Anclas** `id="ph-*"`: cajas `<rect>` invisibles cuya geometría
   (`x`, `y`, `width`, `height`) lee el código para colocar encima el contenido
   generado. El `<rect>` desaparece de la carta final; puedes **moverlas y
   redimensionarlas en Inkscape** y el contenido se recoloca solo.

   | Ancla | Plantilla(s) | Contenido que coloca |
   |-------|--------------|----------------------|
   | `ph-arte` | anversos | imagen del arte (campo `arte` o `sources/arte/<slug>.png`) |
   | `ph-stats` | anversos | `stats_cuadro` (familia stats) o línea de stats (familia descripcion) |
   | `ph-descripcion` | `anverso_descripcion`, `verso_stats` | texto de la descripción (multilínea) |
   | `ph-fondo` | versos | imagen de fondo temática del reverso (`sources/arte_fondos/`) |
   | `ph-retrato`, `ph-cuerpo`, `ph-mente`, `ph-armas`, `ph-oro` | `ficha_personaje` | retrato y zonas de la ficha (pips de cuerpo/mente, lista de armas, caja de oro) |

## Cómo añadir más plantillas

Cuando digitalices las cartas de `sources/arte_fondos_hq2021/` (fondos de carta
HQ 2021) o quieras variantes por tipo, añade aquí un `.svg` nuevo y actualiza el
índice. La familia (`stats`/`descripcion`) decide qué plantilla usa cada tipo;
para que una plantilla nueva tenga efecto sobre el pipeline hay que enlazarla en
`scripts/render_carta.py` (o dar soporte a plantilla por tipo), cosa que se
decide cuando esté diseñada la nueva.

Reglas al crear una plantilla:

- Mantén siempre `viewBox="0 0 500 700"` (620×880 mm reales) salvo en fragmentos
  que se muestran escalados (`stats_cuadro`).
- Documenta en un comentario de cabecera qué contienen los marcadores `{{...}}`
  y el propósito de cada ancla `ph-*`.
- Los rects de las anclas deben llevar `id="ph-..."` exacto; Inkscape los
  conserva al guardar.
- Los `<defs>` internos se conservan en la carta final (`plantillas.py`
  extrae solo el interior del `<svg>`), así que los degradados/id únicos
  puedes definirlos dentro de la plantilla.

Tras editar cualquier plantilla, regenera una carta de cada familia para
comprobar el resultado:

```bash
uv run juegos/heroquest/scripts/carta_item.py --tipo personaje --nombre "Bárbaro" --carta_completa --formato png
uv run juegos/heroquest/scripts/carta_item.py --tipo arma --nombre "Espada corta" --carta_completa --formato png
```
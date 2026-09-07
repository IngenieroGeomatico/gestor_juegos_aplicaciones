# Skill: Digitalizar una misión desde el PDF del libreto

El libreto de **El Despertar** (y otros libros escaneados) trae las misiones como
**páginas escaneadas sin capa de texto**: el mapa va en la página par y el texto
(intro, notas de Zargon, recompensas) en la impar siguiente. Todo el material
vive en `juegos/heroquest/mapas/Libreto_de_Misiones_El_Despertar_First_Light_HQ21_Español_Heval.pdf`.
Para montar esas misiones en `misiones.json` se usa el pipeline de **visión por
computadora** de `juegos/heroquest/rag/vision/`, que alinea la imagen del mapa
con la cuadrícula 26×19 del tablero, detecta los elementos por color y guarda el
**ground-truth** validado junto a cada misión.

> **Importante:** este modelo (big-pickle) **no puede ver imágenes**. El flujo se
> hace en *colaboración*: el agente genera imágenes de validación numeradas y el
> **usuario valida visualmente** cada clase de elemento (posiciones y tipos).

## Flujo completo (orden obligatorio)

### 1. Extraer la página de mapa del PDF

```bash
python juegos/heroquest/rag/vision/extraer_mapa.py \
  "juegos/heroquest/mapas/Libreto_de_Misiones_El_Despertar_First_Light_HQ21_Español_Heval.pdf" \
  <mision> --salida juegos/heroquest/rag/vision/imagenes/mapa_m<N>.png --dpi 200
```

- **Numeración de páginas**: la misión 1 tiene el mapa en la página **10** y el
  texto en la 11; la misión 2 el mapa en la 12 y el texto en la 13; así
  sucesivamente. Es decir, **los mapas van en las páginas pares** y los textos en
  las impares siguientes. En el script la fórmula (índice 0-based) es
  `idx = 7 + 2 * mision` (el script devuelve la página `idx + 1`).
- Cada mapa extraído mide `1687×1198` px a 200 DPI (página A4 del PDF).

### 2. Alinear el mapa con la cuadrícula del tablero

Se necesitan las coordenadas de píxel de las **4 esquinas del tablero** en la
imagen (el marco exterior del tablero impreso). Para la misión 1 están
validadas en `rag/vision/misiones_vision.json`:

```json
"esquinas_tablero_px": { "si": [166, 54], "sd": [1544, 54], "ii": [166, 1128], "id": [1544, 1128] }
```

- Los mapas de misiones distintas pueden tener el tablero en distinta posición
  y rotación; **hay que re-validar las esquinas por misión**.
- Para validar, genera una imagen con la retícula y el número de cada casilla:

```bash
python juegos/heroquest/rag/vision/ret.py <mapa_m<N>.png> <mision> \
  --salida juegos/heroquest/rag/vision/imagenes/ret_<N>.png
```

El usuario confirma que la retícula coincide con el tablero impreso.
Alternativamente, `alinear.py` acepta las 4 esquinas por línea de comandos y
dibuja la retícula + numeración:

```bash
python juegos/heroquest/rag/vision/alinear.py <mapa_m<N>.png> \
  --esquinas "166,54 1544,54 166,1128 1544,1128" --salida ret_<N>.png
```

### 3. Detectar elementos por color (automático)

```bash
python juegos/heroquest/rag/vision/leer_mapa.py <mapa_m<N>.png> <mision> \
  --salida juegos/heroquest/rag/vision/imagenes/leer_<N>.png

python juegos/heroquest/rag/vision/validar_monstruos.py <mapa_m<N>.png> \
  --key <mision> --salidas juegos/heroquest/rag/vision/imagenes
```

Detecciones por umbral de color en el área del tablero:

| Color | Elemento | Detalle |
|-------|----------|---------|
| Rojo compacto | Letras (A/B/C/…) y trampas | `componentes(rojo, ...)` |
| Negro | Calaveras (exploradores caídos) | `componentes(negro, ...)` |
| Verde (celda rellena) | Monstruos | `validar_monstruos.py` numera `V1..Vn (col,fila)` |

La clave `misiones_vision.json` contiene por misión: `esquinas_tablero_px`,
`transformacion_px_a_casilla`, `detecciones` (automáticas) y `ground_truth`
(posiciones validadas manualmente). **La misión 1 es la plantilla completa.**

### 4. Modelar la misión en `misiones.json`

Con las posiciones detectadas/validadas y el texto del OCR del libreto
(intros, notas de Zargon, recompensas y letras A-F de eventos), se construye la
misión con el esquema de `misiones.json` (ver `skills/crear_mision.md`). El
tablero objetivo de las misiones 2-10 es **`cara-b`** (el libreto manda dar la
vuelta al tablero). Cada monstruo/tesoro/trampa/mueble/puerta con sus
coordenadas **globales** (1..26 × 1..19).

### 5. Validar visualmente el montaje contra el libro

```bash
python juegos/heroquest/rag/vision/validar_mision.py <mapa_m<N>.png> \
  --key <mision> --mision "<nombre en misiones.json>" \
  --entrada "c1,f1:c2,f2" --salida "c1,f1:c2,f2" \
  --salidas juegos/heroquest/rag/vision/imagenes [--por-sala]
```

Genera una imagen por tipo (`_monstruos.png`, `_tesoros.png`, `_puertas.png`,
`_letras.png`, `_calaveras.png`, ...) pintando sobre el mapa real lo que hay en
`misiones.json`. El usuario confirma que coincide.

### 6. Generar fichas y hub

```bash
python juegos/heroquest/scripts/mapa.py --tablero original --mision "..." --svg
python juegos/heroquest/scripts/mision_html.py --mision "..."
python juegos/heroquest/scripts/misiones_html.py        # regenera el hub index.html
python juegos/heroquest/scripts/tablero.py validar      # todas las misiones OK
```

## Comandos cortos desde `tools/`

Desde Python (el agente):

```python
from tools.vision import (
    extraer_pagina_mapa,   # paso 1
    dibujar_reticula,      # paso 2 (ret.py)
    leer_mapa,             # paso 3
    detectar_monstruos,    # paso 3
    validar_montaje,       # paso 5 (validar_mision.py)
)
```

## Notas

- `rag/vision/misiones_vision.json` es el **ground-truth** por misión
  (esquema `mision_mapa_v2`). Cada detección automática se promueve a
  `ground_truth` solo cuando el usuario la valida sobre el mapa a 200 DPI.
- El PDF original está en Google Drive (ver `pdf` en `misiones_vision.json`);
  la copia local vive en `juegos/heroquest/mapas/`.
- Los PNGs extraídos y las imágenes de validación van a
  `juegos/heroquest/rag/vision/imagenes/` (ignorados por git).
- Clave de misión en `misiones_vision.json`: `M1`, `M2`, ... `M10`.
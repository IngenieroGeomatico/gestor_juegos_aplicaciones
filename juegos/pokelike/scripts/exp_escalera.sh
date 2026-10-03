#!/usr/bin/env bash
# Experimento de la ESCALERA DE RIESGO del entrenador.
#
# Que mide: si el bot pierde menos runs cuando deja de premiar pelear con el
# equipo desmontado y sin cura delante.
#
# El dato que lo motiva (100 runs de linea base): de 54 muertes de
# entrenador, 33 elegian el nodo con 2 o menos mons en pie y 15 con uno solo, y
# 21 se quedaron con un unico mon al perder. El codigo devolvia
# PESO_ENTRENADOR_SANO (34, el maximo de la pantalla) precisamente en ese caso.
#
# DISENO, y por que es asi:
#   - **Dos brazos intercalados**, no bloques. En el experimento anterior los
#     brazos se lanzaron seguidos y el confound de tiempo fue una de las tres
#     trampas que arruinaron el resultado. Aqui se alterna en cada tanda.
#   - **Mismo codigo**, armado por `PKL_ESCALERA_RIESGO`. Asi el hash de
#     version es identico en los dos brazos y solo cambia la decision.
#   - El brazo de control reproduce el comportamiento **literal** de antes,
#     rama vieja incluida. No es "el codigo sin la escalera": es el baseline.
#   - Paridad exacta: se entregan las `pedidas` runs, sin el bug de `i % 2` que
#     dejo 111 de 150 sin avisar.
#   - Maximo 2 runs simultaneas: la maquina tiene 7 GiB.
set -u

PEDIDAS="${1:-100}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-0}"

# El script vive en `juegos/pokelike/scripts/`, asi que la raiz del repo esta
# **tres** niveles arriba, no dos. Con `../..` se creaba un `juegos/juegos/`
# anidado y las 100 runs se lanzaban contra un directorio de mas y terminaban
# al instante sin dioxe nada.
RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"
# La huella tiene que ser del **contenido**, no del ultimo commit. Con
# `git rev-parse HEAD` el lote entero comparte hash aunque se edite el arbol de
# trabajo a mitad, que es exactamente lo que este experimento existe para
# evitar: los dos brazos tienen que poder compararse solo si salieron del mismo
# codigo. Se concatena todo lo que el bot puede leer y se resume en sha.
#
# La lista es **explicita** y no un glob de `data/*.json`, porque ahi vive
# `medidas.json`, que el bot **escribe** durante las partidas: incluirlo haria
# que la huella cambiase sola a mitad de lote.
ENTRADA=(
  "$RAIZ"/juegos/pokelike/scripts/*.py
  "$RAIZ"/juegos/pokelike/scripts/*.sh
  "$RAIZ"/juegos/pokelike/data/pokemon.json
  "$RAIZ"/juegos/pokelike/data/items.json
  "$RAIZ"/juegos/pokelike/data/regiones.json
  "$RAIZ"/juegos/pokelike/data/tipos.json
  "$RAIZ"/juegos/pokelike/data/chart_juego.json
  "$RAIZ"/juegos/pokelike/data/especialidades.json
)
HASH="$( { for f in "${ENTRADA[@]}"; do
            [ -f "$f" ] && printf '%s\n' "${f#$RAIZ/}" && cat "$f"
          done; } | sha256sum | cut -c1-8 )"
cd "$RAIZ"

# La escalera se midio contra la rama vieja; con el hash basta, pero el
# experimento se archiva aparte para no mezclarse con la linea base.
ETIQUETA="esc_riesgo"
mkdir -p "$LOGS/$ETIQUETA"

echo "== experimento escalera de riesgo =="
echo "   region=$REGION pedidas=$PEDIDAS hash=$HASH"
echo "   A=escalera(1)  B=control(0)  intercalados, 2 simultaneas"
echo "   raiz=$RAIZ"
echo "   logs en $LOGS/$ETIQUETA"

# Comprobaciones ANTES de lanzar 100 runs. Un `while` que itera 50 veces con una
# ruta mal puesta entrega 100 "runs" en 45 segundos y no produce ni un dato:
# eso es exactamente lo que paso la primera vez.
if [ ! -f "$RAIZ/juegos/pokelike/scripts/jugar_pokelike.py" ]; then
  echo "ABORTA: no encuentro jugar_pokelike.py bajo $RAIZ" >&2
  exit 1
fi
if ! command -v uv > /dev/null 2>&1; then
  echo "ABORTA: no hay `uv` en el PATH" >&2
  exit 1
fi

lanzadas=0
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  # El par simultaneo es SIEMPRE un A y un B, y como se suman 2 al contador la
  # serie sale A,B,A,B...: intercalada de verdad, no en bloques.
  #
  # La primera version decidia el brazo **fuera** del par con
  # `lanzadas % 2` y, como aqui el contador avanza de dos en dos, la paridad
  # no cambiaba nunca y las 100 runs salian etiquetadas `brazo=A`. Lo pillo
  # mirando las etiquetas del log, que para eso estan.
  for k in 0 1; do
    if [ "$k" -eq 0 ]; then BRAZO="A"; ESCALA=1; else BRAZO="B"; ESCALA=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_ESCALERA_RIESGO="$ESCALA" \
    PKL_HASH="$HASH" \
    timeout 1500 uv run --group dev python \
      juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --max-pasos "$MAX_PASOS" --reset \
      > "$SALIDA" 2>&1 &
  done
  lanzadas=$((lanzadas + 2))
  wait
  A=$(grep -lc "brazo=A" "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | wc -l)
  B=$(grep -lc "brazo=B" "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | wc -l)
  echo "   entregadas $lanzadas/$PEDIDAS  (A=$A B=$B)"
done

echo "== fin: $PEDIDAS runs en $LOGS/$ETIQUETA =="
echo "== control de paridad: A=$A B=$B (deben ser iguales) =="

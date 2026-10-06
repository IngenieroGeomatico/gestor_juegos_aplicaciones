#!/usr/bin/env bash
# Experimento del NODO DE OBJETO (H13): mide si corregir la inversión vale algo.
#
# Que mide: insignias por partida cogiendo el nodo de objeto cuando hay hueco
# (A, PKL_ITEM_HUECOS=1) frente al comportamiento de siempre (B, =0), que solo
# lo puntua alto cuando la bolsa ya esta LLENA.
#
# El dato que lo motiva (924 pantallas de mapa, 56 runs, hash=388bfc04):
#   - el nodo `item` se ofrecio 144 veces (16% de las pantallas)
#   - el bot lo cogio **4** (3%)
#   - 26 de 54 runs terminaron con 0 objetos; media 0,89 por run
# La causa era una condicion invertida en `planificador.puntuar`:
# `tiene_bolsa` significa "quedan huecos", y el codigo puntuaba 12.0 cuando la
# bolsa estaba llena y 2.0 cuando habia sitio. La guia dice lo contrario:
# "item nodes beat fight nodes early" y el Lucky Egg "outscales the route".
#
# DISENO, igual que exp_vetonivel.sh:
#   - **Dos brazos intercalados** (A,B,A,B...), no bloques.
#   - **Mismo codigo**, armado por `PKL_ITEM_HUECOS`. Hash del contenido.
#   - Default OFF: la correction no se enciende hasta tener veredicto, porque
#     esta vez no es un arreglo de bug demostrado sino un cambio de politica que
#     puede salir mal.
#   - Solo cambia `PKL_ITEM_HUECOS`.
#   - Maximo 2 runs simultaneas: la maquina tiene 7 GiB.
#   - Bot CONGELADO mientras corre.
set -u

PEDIDAS="${1:-100}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-1500}"

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"

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

ETIQUETA="itemhueco"
mkdir -p "$LOGS/$ETIQUETA"

echo "== experimento del nodo de objeto (H13) =="
echo "   region=$REGION pedidas=$PEDIDAS hash=$HASH"
echo "   A=coge objeto con hueco(1)  B=control invertido(0)  intercalados"
echo "   raiz=$RAIZ"
echo "   logs en $LOGS/$ETIQUETA"

if [ ! -f "$RAIZ/juegos/pokelike/scripts/jugar_pokelike.py" ]; then
  echo "ABORTA: no encuentro jugar_pokelike.py bajo $RAIZ" >&2
  exit 1
fi
if ! command -v uv > /dev/null 2>&1; then
  echo "ABORTA: no hay \`uv\` en el PATH" >&2
  exit 1
fi

lanzadas=0
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  for k in 0 1; do
    if [ "$k" -eq 0 ]; then BRAZO="A"; ITEM=1; else BRAZO="B"; ITEM=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_ITEM_HUECOS="$ITEM" \
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

# Sanity: el brazo A tiene que coger muchos mas objetos. Si no, el flag no
# hace nada en juego y el experimento no dice nada.
echo "== sanity: objetos cogidos por brazo (lineas 'objetos   : N') =="
for B in A B; do
  echo "   $B: $(grep -h "objetos   :" "$LOGS/$ETIQUETA"/${ETIQUETA}-$B-*.txt 2>/dev/null |
      awk '{s+=$3; n++} END {printf "media %.2f en %d runs", (n?s/n:0), n}')"
done
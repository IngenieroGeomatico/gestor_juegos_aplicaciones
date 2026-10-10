#!/usr/bin/env bash
# Experimento del VETO DE NIVEL (H11): mide si el veto efectivo vale algo.
#
# Que mide: insignias por partida con veto efectivo (A, PKL_VETO_NIVEL=1)
# frente al veto no-op de siempre (B, PKL_VETO_NIVEL=0, solo -4.0 que el bono
# de ruta tapa 8/8 veces).
#
# DISENO, igual que exp_trade.sh:
#   - **Dos brazos intercalados** (A,B,A,B...), no bloques.
#   - **Mismo codigo**, armado por `PKL_VETO_NIVEL`. Hash del contenido.
#   - La escalera de riesgo queda **encendida en los dos brazos**.
#   - Solo cambia `PKL_VETO_NIVEL`. Una variable, o el experimento no dice nada.
#   - Maximo 2 runs simultaneas: la maquina tiene 7 GiB.
#   - Bot CONGELADO mientras corre. Nada de editar scripts/ a mitad.
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

ETIQUETA="vetonivel"
mkdir -p "$LOGS/$ETIQUETA"

echo "== experimento del veto de nivel (H11) =="
echo "   region=$REGION pedidas=$PEDIDAS hash=$HASH"
echo "   A=veto efectivo(1)  B=control no-op(0)  intercalados, 2 simultaneas"
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
  # El par simultaneo es SIEMPRE un A y un B: serie A,B,A,B... intercalada.
  for k in 0 1; do
    if [ "$k" -eq 0 ]; then BRAZO="A"; NIVEL=1; else BRAZO="B"; NIVEL=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_VETO_NIVEL="$NIVEL" \
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

# Sanity: el brazo A tiene que mostrar penalizaciones por veto, el B ninguna.
# Si A marca 0, el flag no hace nada en juego y el experimento no dice nada.
echo "== sanity: penalizaciones por veto de nivel por brazo =="
echo "   A: $(grep -c 'penalización por veto de nivel' "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')"
echo "   B: $(grep -c 'penalización por veto de nivel' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')"

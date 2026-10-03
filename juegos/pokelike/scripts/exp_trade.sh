#!/usr/bin/env bash
# Experimento del TRADE: mide si cerrar el trade vale algo.
#
# Que mide: insignias por partida con el trade aceptado (A) frente al
# comportamiento de siempre (B), que elegia el nodo, sacrificaba al món mas
# debil y luego declinaba el trato.
#
# El dato que lo motiva (319 runs, 2026-10-03):
#   - 334 pantallas ofrecian nodo de trade; el bot eligio el nodo 46 veces (14%).
#   - 0 trades completados. Cero. `_trade` buscaba #btn-trade-continue, que no
#     existe, y como el unico <button> real es #btn-skip-trade (DECLINE),
#     acababa declinando siempre.
#   - El trade da +3 niveles y PS completos, que es justo de lo que mueren las
#     runs: el embudo de 100 runs de linea base da 26/42/15/8/2/1 muertes por
#     insignia y el 68% son fuera de gimnasio.
#
# DISENO, y por que es asi:
#   - **Dos brazos intercalados**, no bloques: el confound de tiempo ya arruino
#     un experimento anterior. Aqui se alterna en cada tanda.
#   - **Mismo codigo**, armado por `PKL_TRADE`. El hash de version sale del
#     contenido, no de `git rev-parse HEAD` (que no cambia al editar el arbol de
#     trabajo a mitad de lote, justo lo que este experimento debe evitar).
#   - El brazo B reproduce el bug **literalmente**, no "el codigo sin el trade".
#     Sin el flag, el otro brazo seria el mismo bot y la comparacion no diria
#     nada.
#   - La escalera de riesgo se queda **encendida en los dos brazos**: ya esta
#     commiteada y no se midio, pero mezclarla con el trade haria el
#     experimento ilegible. Solo cambia `PKL_TRADE`.
#   - Maximo 2 runs simultaneas: la maquina tiene 7 GiB.
set -u

PEDIDAS="${1:-100}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-1500}"

# El script vive en `juegos/pokelike/scripts/`, asi que la raiz del repo esta
# **tres** niveles arriba, no dos. Con `../..` se creaba un `juegos/juegos/`
# anidado y las 100 runs se lanzaban contra un directorio de mas y terminaban
# al instante sin dioxe nada.
RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"

# La huella tiene que ser del **contenido**, no del ultimo commit: con
# `git rev-parse HEAD` el lote entero comparte hash aunque se edite el arbol de
# trabajo a mitad, que es exactamente lo que este experimento existe para
# evitar: los dos brazos tienen que poder compararse solo si salieron del mismo
# codigo.
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

ETIQUETA="trade"
mkdir -p "$LOGS/$ETIQUETA"

echo "== experimento del trade =="
echo "   region=$REGION pedidas=$PEDIDAS hash=$HASH"
echo "   A=trade(1)  B=control(0)  intercalados, 2 simultaneas"
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
  for k in 0 1; do
    if [ "$k" -eq 0 ]; then BRAZO="A"; TRADE=1; else BRAZO="B"; TRADE=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_TRADE="$TRADE" \
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

# El resultado del experimento no es el codigo: es cuantas insignias por
# partida. `trade_aceptados` es la comprobacion de que el brazo A hizo lo que
# dice hacer, y la que da el valor minimo aceptable: si es 0, el flag no hace
# nada en juego aunque el codigo este bien, y el experimento no dice nada.
echo "== sanity: trades aceptados por brazo =="
echo "   A: $(grep -c 'trade aceptado' "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')"
echo "   B: $(grep -c 'trade aceptado' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')"
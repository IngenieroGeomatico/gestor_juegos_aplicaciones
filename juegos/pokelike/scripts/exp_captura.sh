#!/usr/bin/env bash
# H15 · Capturar es mas barato que rechazar (n=150 por brazo).
#
# Que mide: insignias por partida, y sobre todo **capturas por run**, con el
# filtro de captura permisivo (A, PKL_CAPTURA_PERMISIVA=1) frente al filtro
# estricto de siempre (B, =0).
#
# Regla del usuario: "es mejor capturar que rechazar. Si tenemos algun pokemon
# duplicado en tipo, podemos cambiarlo en el nodo de cambiar".
#
# POR QUE esta y no seguir con la escalera:
#   - la escalera quedo en 114 runs con insignias 1,02 (con) vs 1,18 (sin),
#     p=0,438, y ent/run 4,68 vs 5,55 p=0,087: **neutra o negativa**, y es
#     fontaneria. No es el cuello.
#   - **Misty mata el 34% de las runs** (72 de 212 limpias) y es un muro de
#     NIVEL: se gana llegando a 20,2 y se pierde a 17,7. El tramo da 4,0
#     niveles y Misty pide 9,6.
#   - el filtro de captura es el bucle: rechaza el **98%** de las capturas por
#     "nada util", el equipo se queda sin variedad y vuelve a rechazar. Y
#     rechazar **cuesta la pelea**: `catch-screen` tiene "Skip (flee)" y huir
#     es no pelear (1,88 nodos de pelea por run sin combate, 18%).
#
# SECUNDARIA: capturas/run. Es donde el cambio tiene que verse aunque las
# insignias no se muevan: si suben las capturas y no las insignias, el cambio
# funciona y el cuello esta en otro sitio (eso tambien es informacion).
#
# TAMAÑO: n=150 por brazo detecta 0,3 insignias con potencia 80% (sd=0,92
# medida sobre 149 runs limpias). 300 runs a ~40 runs/h son unas 7,5 h.
set -u

PEDIDAS="${1:-300}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-1500}"
# Timeout por run, en segundos.
#
# **Por que es un parametro y no un 1500 escrito en el script**: el primer lote
# de H15 (timeout 1500) resulto ilegible, no por falta de potencia sino porque
# el timeout **solo mordera al brazo tratado**. El flag hace las runs mas largas
# (+1,23 peleas/run, equipo final 4,00 contra 3,41) y con 25 min de techo:
#
#   |            | A          | B          |
#   | runs >20min| 6          | 0          |
#   | timeouts   | 5/90       | 0/90       |
#   | duracion max | 25,0 min | 13,4 min   |
#
# La duracion separa los brazos con MW p=0,0265. Las 5 runs de A que chocaron
# demise con 8+1+2+5+2 insignias, y el protocolo ("los timeouts cuentan como
# fracaso") las puntuo como cero: 18 puntos de insignia que son exactamente el
# efecto que se venia a medir. Con el protocolo, p=0,216; leyendo las insignias
# del log, p=0,032. Se eligio p=0,216 porque cambiar la regla despues de ver
# que el efecto estaba en A es exactamente el error que este fichero ya ha
# pagado dos veces.
#
# REGLA que sale de ahi: **el timeout se comprueba contra la duracion del brazo
# tratado, no contra el promedio**. Con mediana de 4 min y solo 6 de 180 por
# encima de 20, 3600 s captura practicamente el lote entero.
TIMEOUT="${4:-3600}"

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

ETIQUETA="captura"
mkdir -p "$LOGS/$ETIQUETA"

echo "== H15 · captura permisiva: A=permisiva(1) B=estricto(0), n=$PEDIDAS, hash=$HASH =="
echo "   region=$REGION  logs en $LOGS/$ETIQUETA"
echo "   timeout=${TIMEOUT}s  max_pasos=$MAX_PASOS"
echo "   primaria: insignias | secundaria: capturas/run"

if [ ! -f "$RAIZ/juegos/pokelike/scripts/jugar_pokelike.py" ]; then
  echo "ABORTA: no encuentro jugar_pokelike.py" >&2
  exit 1
fi
if ! command -v uv > /dev/null 2>&1; then
  echo "ABORTA: no hay \`uv\` en el PATH" >&2
  exit 1
fi

lanzadas=0
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  for k in 0 1; do
    if [ "$k" -eq 0 ]; then BRAZO="A"; CAP=1; else BRAZO="B"; CAP=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_CAPTURA_PERMISIVA="$CAP" \
    PKL_HASH="$HASH" \
    timeout "$TIMEOUT" uv run --group dev python \
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
echo "== paridad: A=$A B=$B =="
echo "== sanity: capturas/run por brazo (el flag tiene que verse AQUI) =="
for Z in A B; do
  echo "   $Z: $(grep -h "capturas *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-$Z-*.txt 2>/dev/null |
      awk '{s+=$3; n++} END {printf "media %.2f en %d runs", (n?s/n:0), n}')"
done
echo "== sanity: rechazos 'nada util' por brazo =="
for Z in A B; do
  echo "   $Z: $(grep -h "nada útil" "$LOGS/$ETIQUETA"/${ETIQUETA}-$Z-*.txt 2>/dev/null | wc -l)"
done
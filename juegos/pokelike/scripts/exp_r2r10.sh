#!/usr/bin/env bash
# R2 + R10 · La captura solo cuando tapa un hueco, y el grafo que lleva a ella.
#
# QUÉ MIDE: si la puerta estricta de captura (R2) deja de ser el brazo perdedor
# cuando se le da la otra mitad (R10): peso de captura condicionado a la
# necesidad y valor de rama hacia las capturas por delante.
#
# EL DATO QUE OBLIGA A MEDIR LAS DOS JUNTAS (comentario de CAPTURA_PERMISIVA):
#   A (permisivo) 1,57 insignias/run | B (estricto) 1,03  p=0,0056
#   rechazos de captura 0,84 -> 0,00 por run (p=0,00003): el mecanismo
# El filtro estricto SOLO pierde porque rechaza sin reestructurar. R10 es la
# reestructuración. Si el brazo B no bate al control, lo que se retira es la
# puerta (R2) y se queda R10, no al revés.
#
# BRAZOS
#   A control: PKL_CAPTURA_EXIGENTE=0 PKL_CAPTURA_NECESIDAD=0  (comportamiento de siempre)
#   B regla  : PKL_CAPTURA_EXIGENTE=1 PKL_CAPTURA_NECESIDAD=1  (R2 + R10)
#
# SIN REGLA DE PARADA a propósito: 200 runs fijas. Mirar a mitad y parar según
# lo que se ve es lo que convierte un lote en una anécdota; aquí no hay script
# de parada, así que no se para.
#
# Uso: bash exp_r2r10.sh [runs] [region] [timeout_s]
set -u

PEDIDAS="${1:-200}"
REGION="${2:-Kanto}"
TIMEOUT="${3:-2700}"
PARALELO="${PARALELO:-2}"
VIVACIDAD=600
TICK=60

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"
ETIQUETA="r2r10"

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
          done; } | sha256sum | cut -c1-8)"
cd "$RAIZ"

mkdir -p "$LOGS/$ETIQUETA"

VIVOS="$LOGS/${ETIQUETA}.vivos"
LOG_GUARD="$LOGS/${ETIQUETA}_guard.log"
PIDFILE="$LOGS/${ETIQUETA}.pid"
SALIDA="${SALIDA:-$LOGS/${ETIQUETA}.lanzador.log}"
touch "$SALIDA" 2>/dev/null || true

# El lote no mezcla dos códigos en la misma muestra.
MARCA="$LOGS/$ETIQUETA.hash"
if [ -f "$MARCA" ]; then
  _previo="$(cat "$MARCA" 2>/dev/null)"
  if [ "$_previo" != "$HASH" ]; then
    echo "ABORTA: $LOGS/$ETIQUETA tiene runs del codigo $_previo y ahora es $HASH." >&2
    echo "        Mueve el directorio fuera de ahi y relanza (eso es una decision)." >&2
    exit 1
  fi
else
  echo "$HASH" > "$MARCA"
fi

echo "== R2+R10 · captura con hueco | A=control B=regla | n=$PEDIDAS (~$((PEDIDAS/2)) por brazo) | $REGION | hash=$HASH =="
echo "   timeout=${TIMEOUT}s vivacidad=${VIVACIDAD}s | en paralelo: $PARALELO | logs en $LOGS/$ETIQUETA"
echo "   PRIMARIA: % de runs con 0 insignias (menos es mejor) e insignias/run"
echo "   MECANISMO: 'descartes ->' (R2) y 'capturar de relleno' / 'captura(s) por delante' (R10)"

if [ ! -f "$RAIZ/juegos/pokelike/scripts/jugar_pokelike.py" ]; then
  echo "ABORTA: no encuentro jugar_pokelike.py" >&2
  rm -f "$VIVOS"; exit 1
fi
if ! command -v uv > /dev/null 2>&1; then
  echo "ABORTA: no hay \`uv\` en el PATH" >&2
  rm -f "$VIVOS"; exit 1
fi

matar_arbol() {
  local pid="$1" hijo
  for hijo in $(pgrep -P "$pid" 2>/dev/null); do matar_arbol "$hijo"; done
  kill -9 "$pid" 2>/dev/null
}

watchdog() {
  while [ -f "$VIVOS" ]; do
    sleep "$TICK"
    ahora=$(date +%s)
    while read -r pid log; do
      [ -n "${pid:-}" ] || continue
      kill -0 "$pid" 2>/dev/null || continue
      # Si `stat` no puede leer el log, NO se toca la run: un guard que no
      # puede leer no puede afirmar que está muerta.
      [ -f "$log" ] || continue
      ultima=$(stat -c %Y "$log" 2>/dev/null) || continue
      [ -n "$ultima" ] || continue
      if [ $((ahora - ultima)) -ge "$VIVACIDAD" ]; then
        echo "[$(date '+%d/%m %H:%M')] run pid=$pid lleva $((ahora - ultima))s sin escribir: se mata. $(basename "$log")" >> "$LOG_GUARD"
        matar_arbol "$pid"
      fi
    done < "$VIVOS"
  done
}
: > "$VIVOS"
if [ ! -w "$VIVOS" ]; then
  echo "ABORTA: no puedo escribir $VIVOS, y sin el no hay guard de vivacidad." >&2
  exit 1
fi
watchdog & WD_PID=$!

registrar_salida() {
  # Solo el launcher, no los subshells de las runs.
  [ "$BASHPID" = "$$" ] || return 0
  local codigo=$?
  kill -9 "$WD_PID" 2>/dev/null
  rm -f "$VIVOS" "$PIDFILE"
}
trap registrar_salida EXIT
trap 'registrar_salida; exit 130' INT TERM

echo $$ > "$PIDFILE"

resumen_brazo() {
  local Z="$1"
  compgen -G "$LOGS/$ETIQUETA/${ETIQUETA}-${Z}-"* > /dev/null 2>&1 || {
    echo "   $Z: sin runs"; return; }
  local f n m cero dos
  f=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-${Z}-*.txt 2>/dev/null)
  n=$(grep -h "^  insignias *:" $f 2>/dev/null | wc -l)
  m=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '{s+=$3} END {printf "%.2f", (NR?s/NR:0)}')
  cero=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '$3==0' | wc -l)
  dos=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '$3>=2' | wc -l)
  echo "   $Z: n=$n  insignias/run=$m  0 insignias: $cero ($((100*cero/(n>0?n:1)))%)  >=2: $dos ($((100*dos/(n>0?n:1)))%)"
}

lanzadas=0
entrega=0
for Z in A B; do
  n=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-${Z}-*.txt 2>/dev/null | wc -l)
  lanzadas=$((lanzadas + n))
done
entrega=$lanzadas
if [ "$lanzadas" -eq 0 ]; then
  : > "$LOG_GUARD"
fi
if [ "$lanzadas" -gt 0 ]; then
  echo "   reanudando: $lanzadas runs ya en disco (hash $HASH), quedan $((PEDIDAS - lanzadas))"
fi

PIDS=()
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  while [ "${#PIDS[@]}" -lt "$PARALELO" ] && [ "$lanzadas" -lt "$PEDIDAS" ]; do
    lanzadas=$((lanzadas + 1))
    entrega=$((entrega + 1))
    if [ "$((entrega % 2))" -eq 1 ]; then BRAZO="A"; else BRAZO="B"; fi
    SALIDA_RUN="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$-$lanzadas.txt"
    if [ "$BRAZO" = "B" ]; then
      PKL_CAPTURA_EXIGENTE=1 PKL_CAPTURA_NECESIDAD=1 \
      PKL_BRAZO="r2r10-B" PKL_HASH="$HASH" \
      timeout "$TIMEOUT" uv run --group dev python \
        juegos/pokelike/scripts/jugar_pokelike.py \
        --region "$REGION" --max-pasos 0 --reset \
        > "$SALIDA_RUN" 2>&1 &
    else
      PKL_CAPTURA_EXIGENTE=0 PKL_CAPTURA_NECESIDAD=0 \
      PKL_BRAZO="r2r10-A" PKL_HASH="$HASH" \
      timeout "$TIMEOUT" uv run --group dev python \
        juegos/pokelike/scripts/jugar_pokelike.py \
        --region "$REGION" --max-pasos 0 --reset \
        > "$SALIDA_RUN" 2>&1 &
    fi
    PID_RUN="$!"
    echo "$PID_RUN $SALIDA_RUN" >> "$VIVOS"
    PIDS+=("$PID_RUN")
  done
  if [ "${#PIDS[@]}" -gt 0 ]; then
    # **`wait -n` SIN lista de PIDs.** Con la lista, si alguno ya no es hijo
    # (lo recogio un `wait` anterior) bash devuelve error y el `|| wait` de
    # respaldo espera a TODOS los que quedan: el lote se queda a un run por
    # vez sin decir nada. Medido el 19-10: 44 runs en 2 h y una sola viva.
    # Sin argumentos espera a cualquier hijo y siempre acierta.
    wait -n 2>/dev/null || true
    _VIVOS=()
    for _p in "${PIDS[@]}"; do
      # Un hijo terminado pero aun sin recoger esta en estado Z y `kill -0` lo
      # daria por vivo: se quedaria en la lista ocupando plaza para siempre.
      [ -d "/proc/$_p" ] || continue
      [ "$(awk '/^State:/{print $2}' "/proc/$_p/status" 2>/dev/null)" = "Z" ] && continue
      _VIVOS+=("$_p")
    done
    PIDS=("${_VIVOS[@]}")
  fi
  A=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | wc -l)
  B=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | wc -l)
  MAT=$(grep -c 'sin escribir' "$LOG_GUARD" 2>/dev/null || echo 0)
  echo "   entregadas $lanzadas/$PEDIDAS  (A=$A B=$B matadas=$MAT)"
  # El mecanismo primero: si los flags no llegan, las insignias no significan nada.
  M_DESC=$(grep -h -c 'descartes ->' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  M_RELL=$(grep -h -c 'capturar de relleno' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  M_RAMA=$(grep -h -c 'captura(s) por delante' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  echo "   marcadores en B: descartes=$M_DESC relleno=$M_RELL reestructuracion=$M_RAMA"
done

# Drenar lo que quede vivo antes de dar el lote por terminado.
while [ "${#PIDS[@]}" -gt 0 ]; do
  wait -n 2>/dev/null || break
  _VIVOS=()
  for _p in "${PIDS[@]}"; do
    [ -d "/proc/$_p" ] || continue
    [ "$(awk '/^State:/{print $2}' "/proc/$_p/status" 2>/dev/null)" = "Z" ] && continue
    _VIVOS+=("$_p")
  done
  PIDS=("${_VIVOS[@]}")
done

kill -9 "$WD_PID" 2>/dev/null
rm -f "$VIVOS"
echo "== fin | A=$A B=$B | matadas por el guard: $(grep -c 'sin escribir' "$LOG_GUARD" 2>/dev/null || echo 0) =="
resumen_brazo A
resumen_brazo B
echo "== mecanismo =="
echo "  descartes de R2 en B: $(grep -h -c 'descartes ->' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')"
echo "  capturas de relleno en B: $(grep -h -c 'capturar de relleno' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')"
echo "  ramas con captura en B: $(grep -h -c 'captura(s) por delante' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')"

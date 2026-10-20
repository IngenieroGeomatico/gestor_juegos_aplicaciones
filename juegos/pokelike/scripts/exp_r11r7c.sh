#!/usr/bin/env bash
# R11 + R7 · El trade con tipos repetidos y el entrenador emparejado.
#
# QUÉ MIDE: si el trade sube cuando hay tipos repetidos (R11) y si el peso del
# entrenador se modula por el emparejamiento de su tipo anunciado (R7).
#
# R11: dos móns del mismo tipo son una plaza desperdiciada (R9), y el trade es
# la vía de canjearla sin gastar una captura. Sube a 45 solo con el equipo sano
# (el caído manda: primero se repone la plaza).
# R7: +34 (un PESO_ENTRENADOR_SANO) si algún vivo le pega x2 sin recibirlo,
# -17 si es al revés. La otra mitad de la regla —la rama que desemboca en el
# pokecenter— ya está en `centros_por_delante` x12.
#
# Si B no bate a A, las dos palancas se quedan apagadas por defecto y se pasa a
# la siguiente regla; no se reintenta.
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
ETIQUETA="r11r7c"

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

# Restos de un lanzador anterior: solo los TMPDIR viejos, nunca los de una run
# viva (el supervisor puede relanzar mientras quedan hijos).
find "$LOGS/$ETIQUETA" -maxdepth 1 -name '.tmp-*' -mmin +90 -exec rm -rf {} + 2>/dev/null || true

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

echo "== R11+R7 · trade con repetidos y entrenador emparejado | A=control B=regla | n=$PEDIDAS (~$((PEDIDAS/2)) por brazo) | $REGION | hash=$HASH =="
echo "   timeout=${TIMEOUT}s vivacidad=${VIVACIDAD}s | en paralelo: $PARALELO | logs en $LOGS/$ETIQUETA"
echo "   PRIMARIA: % de runs con 0 insignias (menos es mejor) e insignias/run"
echo "   MECANISMO: 'tipo repetido en el equipo' (R11) y 'R7 x2 a favor' / 'R7 el entrenador pega x2' (R7)"

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
    # **Cada run con su propio TMPDIR.** Playwright tira el perfil de Firefox
    # a $TMPDIR; si la run se mata, el directorio se queda huérfano. Medido el
    # 20-10: 274 perfiles, /tmp al 81% y 130 runs cortadas por páginas caídas.
    # Con el perfil dentro del lote y `trap` al salir, no se acumula nada.
    TMPDIR_RUN="$LOGS/$ETIQUETA/.tmp-$lanzadas"
    rm -rf "$TMPDIR_RUN"
    mkdir -p "$TMPDIR_RUN"
    if [ "$BRAZO" = "B" ]; then
      (
        export TMPDIR="$TMPDIR_RUN"
        trap 'rm -rf "$TMPDIR_RUN"' EXIT
        PKL_TRADE_REPETIDO=1 PKL_ENTRENADOR_EMPAREJAMIENTO=1 \
        PKL_BRAZO="r11r7-B" PKL_HASH="$HASH" \
        timeout "$TIMEOUT" uv run --group dev python \
          juegos/pokelike/scripts/jugar_pokelike.py \
          --region "$REGION" --max-pasos 0 --reset
      ) > "$SALIDA_RUN" 2>&1 &
    else
      (
        export TMPDIR="$TMPDIR_RUN"
        trap 'rm -rf "$TMPDIR_RUN"' EXIT
        PKL_TRADE_REPETIDO=0 PKL_ENTRENADOR_EMPAREJAMIENTO=0 \
        PKL_BRAZO="r11r7-A" PKL_HASH="$HASH" \
        timeout "$TIMEOUT" uv run --group dev python \
          juegos/pokelike/scripts/jugar_pokelike.py \
          --region "$REGION" --max-pasos 0 --reset
      ) > "$SALIDA_RUN" 2>&1 &
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
  M_REP=$(grep -h -c 'tipo repetido en el equipo' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  M_BUEN=$(grep -h -c 'R7 x2 a favor' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  M_MAL=$(grep -h -c 'R7 el entrenador pega x2' "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  echo "   marcadores en B: trade_repetido=$M_REP emparejamiento_bueno=$M_BUEN emparejamiento_malo=$M_MAL"
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
echo "  trade con tipo repetido: $(grep -h -c 'tipo repetido en el equipo' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')"
echo "  R7 a favor (x2): $(grep -h -c 'R7 x2 a favor' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')"
echo "  R7 en contra: $(grep -h -c 'R7 el entrenador pega x2' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')"

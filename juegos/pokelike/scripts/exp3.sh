#!/usr/bin/env bash
# 150 runs: 3 brazos x 50, 2 en paralelo, CON TIMEOUT POR RUN.
#
# Por qué el timeout es imprescindible (no es opcional): sin él, una run que
# se cuelga bloquea el lote entero. Pasó de verdad: una run se quedó 6,8 horas
# pulsando "continuar" con el enemigo a 0 HP, el script la esperaba para
# siempre y de 150 runs solo se hicieron 68 en 10 horas.
#
# `timeout` mata el proceso del bot, y el `pkill` de firefox se lleva al
# navegador que el bot dejo abierto, que si no se acumula.
#
# Las runs que matan el timeout NO tienen linea `resultado` en su log, asi que
# `experimento.py` no las cuenta. Eso seriaTrucar el resultado hacia el exito,
# asi que `contar_tiempos_muerto.sh` las registra aparte y el analisis las
# reporta como fracasos.
set -u
RAIZ=/home/radi/Proyectos/Github/gestor_juegos_aplicaciones
cd "$RAIZ" || exit 1
POR_BRAZO="${1:-50}"
REGION="${2:-Kanto}"
# 25 min: una run sana tarda 12-15. Es holgado a proposito, para no matar runs
# legitimas en una maquina con 2 navegadores.
SEGUNDOS="${3:-1500}"
LOG=/tmp/opencode/exp3.log
TIEMPOS=/tmp/opencode/exp3_tiempos.log
mkdir -p /tmp/opencode
: > "$TIEMPOS"
echo "== 3 brazos x $POR_BRAZO | $REGION | timeout ${SEGUNDOS}s/run | $(date) ==" > "$LOG"

# Lanzar N runs de un brazo, emparejando con un segundo brazo para usar los
# dos nucleos. $1=etiqueta $2=veto $3=cobertura $4=cuantas
# $5=etiqueta2 $6=veto2 $7=cobertura2
bloque() {
  local et="$1" veto="$2" cob="$3" n="$4"
  local et2="$5" veto2="$6" cob2="$7"
  local i=0
  while [ "$i" -lt "$n" ]; do
    local log1 log2 pid1 pid2
    log1=$(mktemp /tmp/opencode/runlog.XXXX)
    PKL_BRAZO="$et" PKL_VETO_TIPO="$veto" PKL_COBERTURA="$cob" \
      timeout -k 30 "$SEGUNDOS" \
      uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
        --region "$REGION" --reset --max-pasos 400 > "$log1" 2>&1 &
    pid1=$!
    pid2=""
    if [ $((i % 2)) -eq 0 ] && [ "$i" -lt $((n - 1)) ]; then
      log2=$(mktemp /tmp/opencode/runlog.XXXX)
      PKL_BRAZO="$et2" PKL_VETO_TIPO="$veto2" PKL_COBERTURA="$cob2" \
        timeout -k 30 "$SEGUNDOS" \
        uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
          --region "$REGION" --reset --max-pasos 400 > "$log2" 2>&1 &
      pid2=$!
    fi
    wait $pid1 2>/dev/null
    [ -n "$pid2" ] && wait $pid2 2>/dev/null
    # Si el proceso termino por el signal de timeout (124), es un cuelgue.
    echo "$et $(grep -c . "$log1") $(grep -q 'resultado *:' "$log1" && echo ok || echo timeout)" >> "$TIEMPOS"
    [ -n "$pid2" ] && echo "$et2 $(grep -c . "$log2") $(grep -q 'resultado *:' "$log2" && echo ok || echo timeout)" >> "$TIEMPOS"
    rm -f "$log1" ${log2:-}
    # El firefox del bot puede quedar vivo y acumular memoria.
    pkill -f "firefox.*profile" 2>/dev/null
    i=$((i+1))
  done
}

bloque A_veto         1 0 $((POR_BRAZO/2))  B_sin_veto      0 0
echo "== bloque 1 (A+B) | $(date) | $(grep -c timeout "$TIEMPOS") timeouts ==" >> "$LOG"
uv run --group dev python juegos/pokelike/scripts/experimento.py analizar >> "$LOG" 2>&1

bloque C_sin_veto_cob 0 1 $((POR_BRAZO/2))  A_veto          1 0
echo "== bloque 2 (C+A) | $(date) | $(grep -c timeout "$TIEMPOS") timeouts ==" >> "$LOG"
uv run --group dev python juegos/pokelike/scripts/experimento.py analizar >> "$LOG" 2>&1

bloque B_sin_veto      0 0 $((POR_BRAZO/2))  C_sin_veto_cob 0 1
echo "== bloque 3 (B+C) | $(date) | $(grep -c timeout "$TIEMPOS") timeouts ==" >> "$LOG"
uv run --group dev python juegos/pokelike/scripts/experimento.py analizar >> "$LOG" 2>&1

pkill -f "firefox.*profile" 2>/dev/null
echo "== fin $(date) | timeouts: $(grep -c timeout "$TIEMPOS") ==" >> "$LOG"
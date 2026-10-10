#!/usr/bin/env bash
# Lanzador del experimento A/B: 100 runs, 2 en paralelo, anotando el brazo.
#
# Por qué 2 y no mas: la maquina tiene 7 GiB y cada Firefox con su bot se lleva
# bastante. Con mas de 2 en paralelo se empieza a tirar runs por OOM, y una run
# muerta es un dato perdido.
#
# Por qué `setsid`: las runs duran ~10 h en total. Sin desvincularse de la
# terminal, al cerrarse el shell mueren las runs en marcha (pasa).
set -u
RAIZ=/home/radi/Proyectos/Github/gestor_juegos_aplicaciones
cd "$RAIZ" || exit 1
OBJETIVO="${1:-100}"
REGION="${2:-Kanto}"
LOG=/tmp/opencode/experimento_loop.log
mkdir -p /tmp/opencode

echo "== experimento A/B: $OBJETIVO runs, region $REGION, $(date) ==" > "$LOG"

# Reparto alterno: mitad y mitad, en vez de azar. Con 100 runs y 2 arms el
# azar puede desequilibrar (p.ej. 54/46) y eso resta potencia. Alternar da
# exactamente 50/50 y sigue siendo aleatorio en el orden, que es lo que evita
# que el momento del dia se confunda con el efecto.
lanzar_un_brazo() {
  local brazo="$1" margen="$2"
  echo "-- brazo=$brazo PKL_MARGEN_BASE=$margen" >> "$LOG"
  PKL_BRAZO="$brazo" PKL_MARGEN_BASE="$margen" \
    uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --reset --max-pasos 400 \
      >> "/tmp/opencode/run_${brazo}_$$.log" 2>&1
}

i=0
while [ "$i" -lt "$OBJETIVO" ]; do
  if [ $((i % 2)) -eq 0 ]; then A=A_margen_0; B=B_margen_2; else A=B_margen_2; B=A_margen_0; fi
  lanzar_un_brazo "$A" "$( [ "$A" = A_margen_0 ] && echo 0 || echo 2 )" &
  pidA=$!
  lanzar_un_brazo "$B" "$( [ "$B" = A_margen_0 ] && echo 0 || echo 2 )" &
  pidB=$!
  wait $pidA $pidB
  i=$((i + 2))
  echo "== $i/$OBJETIVO completadas | $(date +%H:%M:%S) ==" >> "$LOG"
  # Medir entre tanda y tanda: solo lee logs.
  uv run --group dev python juegos/pokelike/scripts/medir_hipotesis.py \
      >> "$LOG" 2>&1
  uv run --group dev python juegos/pokelike/scripts/experimento.py analizar \
      >> "$LOG" 2>&1
  # Cerrar navegadores que se hayan quedado vivos: 100 runs seguidas acumulan.
  pkill -f "firefox.*headless" 2>/dev/null
  sleep 15
done
echo "== fin del experimento $(date) ==" >> "$LOG"

#!/usr/bin/env bash
# Encadena tandas de 2 runs hasta llegar a `objetivo` partidas RESUELTAS.
#
# Por qué un bucle y no una tanda de 100: la maquina tiene 7 GiB y solo 2 runs
# caben, y `lanzar_tanda.py` limpia los navegadores anteriores entre tanda y
# tanda. Lanzar 100 de golpe no cabria.
#
# Uso:  bash culmination.sh [objetivo] [region]
set -u
RAIZ=/home/radi/Proyectos/Github/gestor_juegos_aplicaciones
cd "$RAIZ" || exit 1
OBJETIVO="${1:-100}"
REGION="${2:-Kanto}"
LOG=/tmp/opencode/culminacion.log

cuenta() {
  grep -l "resultado *:" juegos/pokelike/log/*.txt 2>/dev/null | wc -l
}

for tanda in $(seq 1 60); do
  hecho=$(cuenta)
  if [ "$hecho" -ge "$OBJETIVO" ]; then
    echo "== $hecho partidas resueltas: objetivo alcanzado ==" >> "$LOG"
    break
  fi
  echo "== tanda $tanda | $hecho/$OBJETIVO partidas | $(date +%H:%M:%S) ==" >> "$LOG"
  uv run --group dev python juegos/pokelike/scripts/lanzar_tanda.py \
      --runs 2 --region "$REGION" --sin-limpiar --conservar-logs 100 \
      >> /tmp/opencode/tanda_loop.log 2>&1
  # Mide entre tandas: solo lee logs, no lanza nada.
  uv run --group dev python juegos/pokelike/scripts/medir_hipotesis.py \
      >> "$LOG" 2>&1
  sleep 10
done
echo "== fin ==" >> "$LOG"

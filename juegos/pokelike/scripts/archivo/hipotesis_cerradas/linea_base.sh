#!/usr/bin/env bash
# Línea base: 100 runs del bot actual, sin flags experimentales.
#
# Para qué sirve esto: el experimento de flags ya respondió (el veto de tipo es
# contraproducente, la cobertura no aporta nada medible). La pregunta que queda
# ya no es "¿qué flag gana?" sino **"qué impide pasar la región"**. Nadie ha
# llegado de 5 insignias, así que lo que hace falta es volumen de línea base
# sobre el bot bueno, y de esos logs sacar **dónde se mueren** las que no
# llegan.
#
# REGLAS QUE ESTE SCRIPT RESPETA, porque las tres se incumplieron la vez
# anterior y por eso ese experimento salió inconcluso con 111 runs:
#
# 1. **Timeout por run.** Sin él, una run colgada tumba el lote entero. Pasó:
#    una run estuvo 6,8 h pulsando "continuar" y de 150 runs se hicieron 68.
# 2. **Nº de runs exacto.** Se cuenta lo que se lanza, no lo que se espera. El
#    `i % 2` del script anterior entregaba 111 de 150 sin que nadie lo notara
#    hasta el final. Aquí el bucle es "while lanzadas < pedidas" y el número de
#   Equals es explícito.
# 3. **CÓDIGO CONGELADO.** No editar `juegos/pokelike/scripts/` mientras corre.
#    Editar a mitad dejó 56 de 111 runs con versión distinta y hubo que tirar la
#    mitad de la muestra. Está KLAS: si cambia el hash del código a mitad, el
#    log lo anota para que el análisis pueda separar.
#
# Uso:  bash linea_base.sh [runs] [region] [segundos_timeout]
set -u
RAIZ=/home/radi/Proyectos/Github/gestor_juegos_aplicaciones
cd "$RAIZ" || exit 1
PEDIDAS="${1:-100}"
REGION="${2:-Kanto}"
SEGUNDOS="${3:-1500}"
LOG=/tmp/opencode/linea_base.log
TIEMPOS=/tmp/opencode/linea_base_tiempos.log
mkdir -p /tmp/opencode
: > "$TIEMPOS"

# El hash del código va al log de cada run. Si alguien edita el bot a mitad, los
# logs de antes y después quedan distinguibles **sin tener que acordarse de la
# hora de la edición**, que es como se colaron los 56 datos malos la vez
# anterior.
HASH=$(cat juegos/pokelike/scripts/*.py | md5sum | cut -c1-8)

echo "== linea base | $PEDIDAS runs | $REGION | timeout ${SEGUNDOS}s | codigo $HASH | $(date) ==" > "$LOG"

lanzadas=0
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  loga=$(mktemp /tmp/opencode/lb.XXXXXX)
  logb=$(mktemp /tmp/opencode/lb.XXXXXX)

  PKL_BRAZO=base PKL_VETO_TIPO=0 PKL_COBERTURA=0 PKL_HASH="$HASH" \
    timeout -k 30 "$SEGUNDOS" \
    uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --reset --max-pasos 400 > "$loga" 2>&1 &
  pida=$!

  # Solo dos en paralelo (la maquina tiene 7 GiB), y solo si aún queda trabajo:
  # con esto la paridad es exacta, no "la mitad de las veces".
  pida2=""
  if [ $((lanzadas + 1)) -lt "$PEDIDAS" ]; then
    PKL_BRAZO=base PKL_VETO_TIPO=0 PKL_COBERTURA=0 PKL_HASH="$HASH" \
      timeout -k 30 "$SEGUNDOS" \
      uv run --group dev python juegos/pokelike/scripts/jugar_pokelike.py \
        --region "$REGION" --reset --max-pasos 400 > "$logb" 2>&1 &
    pida2=$!
  fi

  wait "$pida" 2>/dev/null
  [ -n "$pida2" ] && wait "$pida2" 2>/dev/null

  # `resultado :` solo aparece si la run terminó sola. Sin eso es un cuelgue, y
  # un cuelgue es una run **perdida**, no una run que se ignora: contarla como
  # fracaso es lo honesto, porque Así la pasó de verdad.
  if grep -q 'resultado *:' "$loga"; then echo "base ok" >> "$TIEMPOS"; else echo "base timeout" >> "$TIEMPOS"; fi
  if [ -n "$pida2" ]; then
    if grep -q 'resultado *:' "$logb"; then echo "base ok" >> "$TIEMPOS"; else echo "base timeout" >> "$TIEMPOS"; fi
  fi
  rm -f "$loga" ${logb:-}

  pkill -f "firefox.*profile" 2>/dev/null
  lanzadas=$((lanzadas + 2))
  echo "== $lanzadas/$PEDIDAS | $(date +%H:%M) | timeouts: $(grep -c timeout "$TIEMPOS") ==" >> "$LOG"
done

pkill -f "firefox.*profile" 2>/dev/null
echo "== fin | lanzadas $lanzadas | timeouts $(grep -c timeout "$TIEMPOS") | $(date) ==" >> "$LOG"
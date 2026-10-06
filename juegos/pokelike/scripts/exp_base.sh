#!/usr/bin/env bash
# Línea base con el bot ya encendido (H15 confirmado). Sin brazos: aquí no hay
# nada que comparar, se quiere saber **dónde está el techo ahora**.
#
# Por qué un lanzador nuevo y no `linea_base.sh`: aquel es de la era previa a
# H15 y tiene tres fallos que ya han costado datos en este repo:
#   1. escribe los logs en `/tmp/opencode/`, que se limpia solo. Los logs de un
#      lote tienen que vivir en el repo, o el trabajo se pierde.
#   2. hashea con `md5sum` sobre `scripts/*.py` solo, así que un cambio en un
#      `.sh` no cambia el hash y dos lotes distintos salen con el mismo sello.
#      El hash tiene que cubrir lo que ejecuta, y el launcher se ejecuta.
#   3. `--max-pasos 400`, que es un techo de pruebas: recorta las runs largas,
#      que son justo las que interestan para medir el techo.
#
# Lo que este sí cumple, y son las reglas del protocolo:
#   - **nº de runs exacto**: bucle `while lanzadas < pedidas`, y se cuenta lo
#     lanzado, no lo esperado. Además avisa si `entregados < lanzadas`.
#   - **hash de código en la cabecera de cada log**, para separar lotes sin
#     acordarse de cuándo se editó.
#   - **guard de vivacidad**, que mata la run colgada antes de que se coma el
#     reloj del lote.
#   - **timeout por run**, que cuenta como fracaso.
#
# Uso:  bash exp_base.sh [runs] [region] [max_pasos] [timeout] [vivacidad_s]
set -u

PEDIDAS="${1:-150}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-1500}"
TIMEOUT="${4:-1800}"

# **Guard de vivacidad**: una run que lleva VIVACIDAD segundos sin escribir una
# sola línea en su log está colgada, y se mata aunque no haya llegado al
# timeout.
#
# Por qué hace falta, medido el 06-10: una run se quedó 58,8 de sus 60 min
# escribiendo `[continuar -> True] pulso continuar hasta el final` tres veces
# seguidas sin cambio de estado, contra un `Wild Tangela Lv13` que no se
# resolvía. Nivel 19-21 con un Tangela de 13 al cabo de casi una hora.
#
# Y como `wait` espera a LOS DOS runs del par, **una run colgada come media hora
# del reloj del lote entero**. El throughput lo marca la peor run del par, no la
# mediana: en ese lote la mediana de duración era 3,8 min y el máximo 58,8.
#
# Por qué 600 s y no menos: el log crece en cada escritura, y una run larga
# pero sana sigue escribiendo. Con mediana de 3,8 min, 10 min de silencio no
# se confunde con una run que está trabajando.
#
# Por qué 1800 s de timeout y no 3600: con el guard en pie, el timeout es solo la
# red de seguridad para el caso raro, no el mecanismo normal. Y este lote es de
# UN SOLO BRAZO, así que la censura ya no sesga ninguna comparación A/B. Lo que
# sí hace es recortar las runs profundas, que son las que miden el techo: por eso
# baja el timeout, pero se mantiene la regla de puntuación pre-registrada (un
# run cortado se puntúa con las insignias que alcanzó).
VIVACIDAD="${5:-600}"
# Cada cuánto mira el guard. **Escala con la vivacidad**: con `sleep 60` fijo,
# una vivacidad de 600 s no se nota hasta los 600-660 s, y una vivacidad
# pequeña es imposible de probar en un test. El guard solo duerme TICK.
# Invariante: VIVACIDAD >= 3*TICK, para que el margen de deteccion sea holgado
# y no dependa de donde caiga la run dentro del ciclo.
TICK="${6:-60}"
if [ "$VIVACIDAD" -lt $((3 * TICK)) ]; then
  TICK=$((VIVACIDAD / 3))
  [ "$TICK" -lt 1 ] && TICK=1
fi

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"
ETIQUETA="base"
VIVOS="$(mktemp /tmp/opencode/vivos.XXXXXX)"
LOG_GUARD="$LOGS/${ETIQUETA}_guard.log"

# Mismo conjunto de entradas que el resto de lanzadores, para que los hashes
# sean comparables entre sí.
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

echo "== línea base | n=$PEDIDAS | $REGION | timeout=${TIMEOUT}s | vivacidad=${VIVACIDAD}s (tick ${TICK}s) | max_pasos=$MAX_PASOS | hash=$HASH =="
echo "   logs en $LOGS/$ETIQUETA"
echo "   guard de vivacidad: $LOG_GUARD"
echo "   PKL_CAPTURA_PERMISIVA sin tocar -> default 1 (H15 encendido)"

if [ ! -f "$RAIZ/juegos/pokelike/scripts/jugar_pokelike.py" ]; then
  echo "ABORTA: no encuentro jugar_pokelike.py" >&2
  rm -f "$VIVOS"
  exit 1
fi
if ! command -v uv > /dev/null 2>&1; then
  echo "ABORTA: no hay \`uv\` en el PATH" >&2
  rm -f "$VIVOS"
  exit 1
fi

# --- Guard de vivacidad ------------------------------------------------------
# Watchdog independiente, NO dentro del bucle: así sigue vigilando aunque el
# `wait` esté bloqueado, que es justo cuando hace falta.
#
# $VIVOS lleva una línea por run viva: "pid logFile". Para matar hay que bajar
# por el árbol de hijos: el PID guardado es el de `timeout`, y matando solo ese
# el `uv`/`python` de debajo se queda huérfano con su firefox.
matar_arbol() {
  local pid="$1" hijo
  for hijo in $(pgrep -P "$pid" 2>/dev/null); do
    matar_arbol "$hijo"
  done
  kill -9 "$pid" 2>/dev/null
}

watchdog() {
  while [ -f "$VIVOS" ]; do
    sleep "$TICK"
    ahora=$(date +%s)
    while read -r pid log; do
      [ -n "${pid:-}" ] || continue
      kill -0 "$pid" 2>/dev/null || continue
      ultima=$(stat -c %Y "$log" 2>/dev/null || echo 0)
      silencio=$((ahora - ultima))
      if [ "$silencio" -ge "$VIVACIDAD" ]; then
        echo "[$(date '+%d/%m %H:%M')] run pid=$pid lleva ${silencio}s sin escribir (>= ${VIVACIDAD}s): se mata. log=$(basename "$log")" >> "$LOG_GUARD"
        matar_arbol "$pid"
      fi
    done < "$VIVOS"
  done
}

: > "$VIVOS"
watchdog &
WD_PID=$!
# Si el launcher muere, el watchdog también.
trap 'kill -9 "$WD_PID" 2>/dev/null; rm -f "$VIVOS"' EXIT INT TERM

# --- Lote --------------------------------------------------------------------
lanzadas=0
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  PIDS=()
  for _ in 1 2; do
    [ "$lanzadas" -ge "$PEDIDAS" ] && break
    lanzadas=$((lanzadas + 1))
    # El nombre lleva el índice de la run, NO solo el timestamp. Los dos runs
    # de un par salen en el mismo segundo, y el segundo `>` trunca al primero:
    # se perdía la mitad del lote sin que se notara (el launcher anunciaba
    # "entregadas 4" con 2 ficheros en disco). En `exp_captura.sh` esto lo evita
    # la etiqueta A/B del nombre; aquí, que no hay brazos, hay que poner el
    # índice a mano. `$$` (pid del launcher) + el índice es único, y se conoce
    # ANTES de lanzar, así que no hay carrera con la redirección.
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-$(date +%H%M%S)-$$-$lanzadas.txt"
    PKL_BRAZO=base \
    PKL_HASH="$HASH" \
    timeout "$TIMEOUT" uv run --group dev python \
      juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --max-pasos "$MAX_PASOS" --reset \
      > "$SALIDA" 2>&1 &
    PID_RUN="$!"
    echo "$PID_RUN $SALIDA" >> "$VIVOS"
    PIDS+=("$PID_RUN")
  done
  # **`wait` CON LOS PIDS DE LAS RUNS, nunca `wait` a secas.**
  # Sin argumentos, `wait` espera a TODOS los hijos del launcher, y uno de
  # ellos es el watchdog, que no sale nunca: su bucle es `while [ -f "$VIVOS" ]`
  # y ese fichero no se borra hasta el final del script. O sea que el watchdog
  # se espera a si mismo y el lote se queda clavado en el primer par. Pasó el
  # 06-10: 2 runs cerradas a las 18:38 y el launcher sigue en `wait` a las
  # 19:45, sin lanzar el par siguiente.
  [ "${#PIDS[@]}" -gt 0 ] && wait "${PIDS[@]}"
  ENTREGADOS=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null | wc -l)
  COMPLETOS=$(grep -l "resultado *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null | wc -l)
  MATADOS=$(grep -c 'VIVO' "$LOG_GUARD" 2>/dev/null || echo 0)
  # Si entregados < lanzadas, se están pisando: avisar, no seguir en silencio.
  # Es la regla "cuenta las runs antes de lanzar" hecha comprobación.
  if [ "$ENTREGADOS" -lt "$lanzadas" ]; then
    echo "   !! AVISO: lanzadas $lanzadas pero solo $ENTREGADOS ficheros en disco."
  fi
  echo "   entregadas $lanzadas/$PEDIDAS  (en disco $ENTREGADOS, cerradas $COMPLETOS, matadas $MATADOS)"
done

kill -9 "$WD_PID" 2>/dev/null
rm -f "$VIVOS"

echo "== fin: $lanzadas runs en $LOGS/$ETIQUETA =="
echo "== resumen del lote (leer de RESUMEN, nunca del log entero) =="
grep -h "^  insignias *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null |
  awk '{s+=$3; n++; if($3>m) m=$3} END {printf "   media %.2f en %d runs | maximo %d\n", (n?s/n:0), n, m}'
grep -h "^  capturas *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null |
  awk '{s+=$3; n++} END {printf "   capturas/run %.2f\n", (n?s/n:0)}'
grep -h "^  equipo *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null |
  awk '{s+=$3; n++} END {printf "   mons en el equipo %.2f\n", (n?s/n:0)}'
echo "== runs matadas por el guard de vivacidad: $(grep -c 'VIVO' "$LOG_GUARD" 2>/dev/null || echo 0) =="
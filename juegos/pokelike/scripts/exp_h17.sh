#!/usr/bin/env bash
# H17 · Capturar por nivel (n=300 en total, ~150 por brazo).
#
# QUÉ MIDE: si capturar en la apertura cuando falta nivel sube las insignias.
# El cambio es **un peso**: la rama `falta > 1` con equipo >= 3 y pokeball en
# pantalla pasa de 8.0 (por debajo del entrenador, 36) a PESO_CAPTURA (60).
#
# POR QUÉ ESTA Y NO "PREFERIR SIEMPRE AL ENTRENADOR":
# una captura **es** una pelea (R2 da +1 nivel a la pelea), así que capturar da
# el mismo nivel **y además un món**. Un entrenador da +2 niveles y ningún món,
# y perder contra un entrenador **termina la run**. Con el equipo corto —que es
# el caso, que la rama solo entra por encima de 3 móns— ese trueque es razonable
# y arriesgado tocarlo. Se queda como está.
#
# El desperdicio real está medido: en la ventana antes de Misty, 6,52 batallas
# sueltas frente a 3,19 capturas. Se pelea el doble de veces sin capturar que
# capturando, y cazar no da nada más que nivel.
#
# Y hay un dato de por qué NO era "el filtro": en el 42% de las pantallas con
# `trainer` disponible el equipo tiene menos de 3 móns, y ahí el.bot elige
# capturar por peso (60 > 36) sin que el flag cambie nada. Esos rechazos no son
# del filtro, son de orden de prioridades.
#
# PRIMARIA: `insignias/run` (sd 1,26 → detecta ±0,41 a 150/brazo, que es el
# tamaño del efecto de H15: +0,53). SECUNDARIA: `>=2 insignias` (31% → ±15,8
# puntos) y `>=3`.
#
# **NO es primaria las victorias en Misty**, aunque es donde muere el 46% de las
# runs: solo hay 0,233 entradas a Misty por run, o sea 35 por brazo, y detecting
# eso exigiría un salto de +29 puntos. La especificidad se paga en n. Cambiar
# la primaria de H17 antes de mirar un solo dato es el momento legítimo para
# hacerlo.
#
# Lo que se sabe ya, sin mirar este lote:
#   - equipo de 1 → `batalla=60 entrenador=36` (gana capturar, el flag da igual)
#   - equipo de 3 y falta nivel → sin flag `entrenador=36 batalla=8`;
#     con flag `batalla=60 entrenador=36`
#
# Uso: bash exp_h17.sh [runs_por_brazo] [region] [timeout]
set -u

PEDIDAS="${1:-300}"
REGION="${2:-Kanto}"
TIMEOUT="${3:-1800}"
MAX_PASOS=1500

# **Runs simultaneos: 1, no 2.**
#
# Tres OOM en una noche, los tres matando a VS Code (oomd mata el cgroup mas
# grande, y el mas grande era el editor). La cuenta del 07-10 a las 23:46:
#   VS Code 2197 + opencode 544 + deno 413 + 2 runs ~1500 = ~4650 MB
# sobre 7299 MB totales. El margen no existia.
#
# Bajar a 1 run NO cambia el experimento: los brazos siguen siendo A y B, el
# mismo bot, el mismo hash. Solo cambia cuando se ejecutan. El coste es doble
# de pared (26 h en vez de13) y el beneficio es que el lote no le mata el
# editor a uno.
PARALELO="${PARALELO:-1}"
VIVACIDAD=600
TICK=60

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"
ETIQUETA="h17"

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
# **El fichero de runsvivas va en el repo, no en `/tmp`.**
# El 07-10 `/tmp/opencode` paso a ser de root sin escritura, el `mktemp`
# fallo con "Permission denied" y el fichero quedo VACIO: el guard de
# vivacidad arranca con `while [ -f "$VIVOS" ]`, asi que con un fichero
# inexistente **no se lanza y no avisa**: el lote corria sin red de
# seguridad. Y `/tmp` se limpia solo, que ya hacia falta no depender de
# el para el estado de un lote.
VIVOS="$LOGS/${ETIQUETA}.vivos"
LOG_GUARD="$LOGS/${ETIQUETA}_guard.log"
PIDFILE="$LOGS/${ETIQUETA}.pid"
# Log del launcher: lo pone el supervisor, y si no existe se crea aqui para que el
# trap de salida tenga donde escribir.
SALIDA="${SALIDA:-$LOGS/${ETIQUETA}.lanzador.log}"
touch "$SALIDA" 2>/dev/null || true

echo "== H17 · captura por nivel | A=1 B=0 | n=$PEDIDAS en total (~$((PEDIDAS/2)) por brazo) | $REGION | hash=$HASH =="
echo "   timeout=${TIMEOUT}s vivacidad=${VIVACIDAD}s (tick ${TICK}s) | en paralelo: $PARALELO | logs en $LOGS/$ETIQUETA"
echo "   primaria: insignias/run | secundaria: >=2 insignias"

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
      # **Si `stat` no puede leer el log, NO se toca la run.** Antes:
      #     ultima=$(stat -c %Y "$log" 2>/dev/null || echo 0)
      # `stat` imprime 0 cuando el fichero no existe, o sea que "no existe" y
      # "escribio en 1970" eran lo mismo. El guard leia entonces 1.791.409.360 s
      # de silencio y mataba una run perfectamente sana. Sucedio de verdad:
      #   "run pid=149559 lleva 1791409360s sin escribir: se mata"
      # Un guard que no puede leer no puede afirmar nada, y lo que hace ahora es
      # callarse. Matar por un dato que no tiene es peor que no vigilar.
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
# **Si el fichero de runsvivas no se puede escribir, el lote NO arranca.**
# Así falló el guard el 07-10: el `mktemp` dio "Permission denied" porque
# `/tmp/opencode` pasó a ser de root, `$VIVOS` quedó vacío, el
# `while [ -f "$VIVOS" ]` del watchdog no entró nunca, y el lote corría **sin
# red de seguridad y sin decir nada**. Un guard que no puede vigilar tiene que
# fallar aquí, no esperar a que se le eche de menos.
if [ ! -w "$VIVOS" ]; then
  echo "ABORTA: no puedo escribir $VIVOS, y sin el no hay guard de vivacidad." >&2
  echo "        Un guard que no puede vigilar debe fallar aqui, no en silencio." >&2
  exit 1
fi
watchdog & WD_PID=$!
# **El launcher dice por que se va.** Se llevaba horas muriendo en silencio:
# el supervisor veia el proceso desaparecer, relanzaba, y no habia ni una linea
# en el log que explicase por que. Con `trap ... EXIT` se imprime el codigo de
# salida y la senal recibida.
#   - Si sale con codigo 0 y sin senal: el bucle termino de verdad (imprime "== fin").
#   - Si aparece CODIGO= o SENAL=, ya no hay que adivinar.
registrar_salida() {
  # **Solo en el launcher, nunca en los subshells de las runs.** `cmd &` crea un
  # subshell que hereda este trap, y cada run escribia en su propio log la
  # despedida del launcher —que ni era suya ni la merecia—. En un subshell
  # `$$` es el PID del proceso padre (el launcher) y `BASHPID` el suyo propio:
  # si no coinciden, aqui no es el launcher y no hay nada que registrar.
  [ "$BASHPID" = "$$" ] || return 0
  local codigo=$?
  local senal=""
  [ "$codigo" -gt 128 ] && senal=" senal=$((codigo - 128))"
  [ "$codigo" -ne 0 ] && echo "[$(date '+%d/%m %H:%M:%S')] el launcher SALE codigo=$codigo$senal" >> "$SALIDA"
  kill -9 "$WD_PID" 2>/dev/null
  rm -f "$VIVOS" "$PIDFILE"
}
trap registrar_salida EXIT
trap 'registrar_salida; exit 130' INT TERM

# **Pidfile.** El supervisor comprueba este PID en vez de hacer `pgrep -f` por el
# nombre del script, porque el supervisor **se pasa el nombre del launcher como
# argumento**: `bash supervisor_lote.sh log/h17 45 bash exp_h17.sh ...`. O sea
# que `pgrep -f exp_h17` encuentra al propio supervisor, que empieza igual por
# "bash ", y se creería vivo un launcher muerto para siempre. El pidfile no
# admite esa ambigüedad.
echo $$ > "$PIDFILE"

# Se reanuda: las runs ya en disco cuentan como entregadas de su brazo.
resumen_brazo() {
  local Z="$1"
  # Ojo: `[ -e "$glob" ]` NUNCA expande el glob (un `*` dentro de comillas es un
  # `*` literal), asi que el test era falso siempre y este resumen decia "sin
  # runs" aunque hubiera 150 logs en disco. Se pregunta con `compgen -G`, que si
  # expande, y se cuenta con un glob que si se expande en el `ls`.
  # El `*` va FUERA de las comillas a proposito: `compgen -G` exige que el
  # patron case completo, y `h17prueba-A-` no es el nombre de ningun fichero
  # (los hay `h17prueba-A-063126-172335-1.txt`). Sin ese `*` no encuentra nada y
  # vuelve a decir "sin runs" con 150 logs en disco.
  compgen -G "$LOGS/$ETIQUETA/${ETIQUETA}-${Z}-"* > /dev/null 2>&1 || {
    echo "   $Z: sin runs"; return; }
  local n; n=$(grep -h "^  insignias *:" $f 2>/dev/null | wc -l)
  local m; m=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '{s+=$3} END {printf "%.2f", (NR?s/NR:0)}')
  local g; g=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '$3>=2' | wc -l)
  echo "   $Z: n=$n  insignias/run=$m  >=2 insignias: $g ($((100*g/(n>0?n:1)))%)"
}

lanzadas=0
entrega=0
# **Reanuda.** Las runs ya en disco cuentan como entregadas. Sin esto, cada
# relanzamiento del supervisor empezaba en `lanzadas=0` y el launcher anunciaba
# "entregadas 2/300" con 28 ficheros en disco: la contabilidad del launcher
# mentia, que es justo lo que este protocolo no permite. Los nombres llevan
# timestamp y PID, asi que al reanudar no se pisa ningun log anterior.
for Z in A B; do
  n=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-${Z}-*.txt 2>/dev/null | wc -l)
  lanzadas=$((lanzadas + n))
done
entrega=$lanzadas
if [ "$lanzadas" -gt 0 ]; then
  echo "   reanudando: $lanzadas runs ya en disco (hash $HASH), quedan $((PEDIDAS - lanzadas))"
fi
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  PIDS=()
  for _K in $(seq 1 "$PARALELO"); do
    [ "$lanzadas" -ge "$PEDIDAS" ] && break
    lanzadas=$((lanzadas + 1))
    # El brazo lo decide el contador de entregas, no el indice del hueco: con
    # PARALELO=1 los brazos tienen que alternar A,B,A,B. Si el brazo dependiera
    # del indice, con 1 en paralelo salen todos A primero y el lote entero es
    # del mismo grupo hasta que A se agota.
    entrega=$((entrega + 1))
    if [ "$((entrega % 2))" -eq 1 ]; then BRAZO="A"; CPN=1; else BRAZO="B"; CPN=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$-$lanzadas.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_CAPTURA_POR_NIVEL="$CPN" \
    PKL_HASH="$HASH" \
    timeout "$TIMEOUT" uv run --group dev python \
      juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --max-pasos "$MAX_PASOS" --reset \
      > "$SALIDA" 2>&1 &
    PID_RUN="$!"
    echo "$PID_RUN $SALIDA" >> "$VIVOS"
    PIDS+=("$PID_RUN")
  done
  # `wait` SOLO con los PIDs de las runs: sin argumentos esperaria tambien al
  # watchdog, que no sale nunca porque su fichero existe hasta el final.
  [ "${#PIDS[@]}" -gt 0 ] && wait "${PIDS[@]}"
  A=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | wc -l)
  B=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | wc -l)
  MAT=$(grep -c 'sin escribir' "$LOG_GUARD" 2>/dev/null || echo 0)
  # La cuenta buena es la de ficheros en disco, no la del launcher.
  if [ "$((A + B))" -lt "$lanzadas" ]; then
    echo "   !! AVISO: lanzadas $lanzadas pero solo $((A+B)) ficheros en disco."
  fi
  echo "   entregadas $lanzadas/$PEDIDAS  (A=$A B=$B matadas=$MAT)"
done

kill -9 "$WD_PID" 2>/dev/null
rm -f "$VIVOS"
echo "== fin | A=$A B=$B | matadas por el guard: $(grep -c 'sin escribir' "$LOG_GUARD" 2>/dev/null || echo 0) =="
echo "== primaria: insignias/run por brazo =="
resumen_brazo A
resumen_brazo B
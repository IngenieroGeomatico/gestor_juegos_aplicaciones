#!/usr/bin/env bash
# H21 · Con el equipo roto, la rama que gasta menos tiene que GANAR.
#
# QUÉ MIDE: si dejar de premiar las ramas largas cuando el equipo no puede
# pagarlas sube la proportion de peleas de gimnasio a las que se entra entero.
#
# EL DIAGNÓSTICO, ya medido antes de escribir una línea de política
# (`scripts/medir/derrota_por_derrota.py`, 934 peleas con foto de PS reales):
#
#   vida 0-50%  -> gana el 25,0%
#   vida 50-75% -> gana el 88,5%
#   vida >95%   -> gana el 99,7%
#
# La vida es el separador. El nivel, al lado, casi no separa: por debajo del
# rival se gana el 56,3% y al nivel el 90,4%.
#
# Y POR QUÉ NO SE PUEDE SUBIR EL NIVEL (`medir/hay_exp_que_sirva.py`, 1.830
# pantallas por debajo del listón): el rival más fuerte que el juego ofrece
# está 8-11 niveles POR DEBAJO del listón, y solo el 2% de las veces está
# siquiera por encima del propio equipo. El déficit de ~5,9 niveles no lo
# cierra ninguna política de pesos. **Se entra por debajo de nivel; lo que no
# se negocia es entrar entero.**
#
# POR QUÉ NO ES OTRO PESO. El bono de ruta (`combates_por_delante` y
# `entrenadores_por_delante`) es **incondicional**: premia la rama larga
# aunque el equipo no pueda pagarla. Con el flag, y solo con el equipo roto, ese
# término cambia de signo. Fuera de esa situación el comportamiento es idéntico
# al control, byte a byte en el motivo de la decisión.
#
# Y POR QUÉ NO ES "SUBIR EL PESO DE CURAR" (H18, ya falló dos veces): el bot
# ya cura. De las 178 peleas empezadas con el equipo roto, **0 de 178** tenían
# un pokecenter en pantalla (`medir/entrar_roto.py`), y de 493 pantallas con
# cura a la vista fue a curar las 493. No era una decisión: la cura se quedó
# atrás y el tramo hasta el gimnasio son peleas obligatorias. El peso nunca
# fue la restricción, y por eso H18 fue un no-op las dos veces que se probó.
#
# ALCANCE MEDIDO ANTES DE LANZAR (`scripts/medir/alcance_h20.py`, 336 runs):
# el 31,2% de los pasos con el equipo roto tienen a la vez un nodo de combate
# y una rama sin combate. Por encima del 15% mínimo de la regla, con holgura.
#
# LA PARADA va en `scripts/control_h21.py`, dentro del hash a propósito.
#
# Uso: bash exp_h20.sh [runs] [region] [timeout]
set -u

PEDIDAS="${1:-300}"
REGION="${2:-Kanto}"
TIMEOUT="${3:-1800}"
MAX_PASOS=1500

# **Un run en paralelo, no dos.** La máquina tiene 7 GiB y 4 núcleos. Con dos,
# el lote vive en el margen exacto donde `oomd` empieza a matar, y las cuatro
# veces que murió un lote fue porque `oomd` mató a VS Code y se lo llevó por
# delante: el lote hereda el cgroup del proceso que lo lanza, y `setsid` crea
# sesión pero **no cambia el cgroup**. Por eso además va en su propia unidad de
# systemd (ver §6 de HIPOTESIS.md). Bajar a 1 no cambia el experimento: mismos
# brazos, mismo bot, mismo hash. Solo cambia cuándo se ejecuta.
PARALELO="${PARALELO:-1}"
VIVACIDAD=600
TICK=60

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"
ETIQUETA="h21"

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

# El fichero de runs vivas va en el repo, no en `/tmp`: el 07-10 `/tmp` pasó a
# ser de root, el fichero quedó vacío y el guard arrancaba con
# `while [ -f "$VIVOS" ]`, así que **no se lanzaba y no avisaba**.
VIVOS="$LOGS/${ETIQUETA}.vivos"
LOG_GUARD="$LOGS/${ETIQUETA}_guard.log"
PIDFILE="$LOGS/${ETIQUETA}.pid"
SALIDA="${SALIDA:-$LOGS/${ETIQUETA}.lazador.log}"
touch "$SALIDA" 2>/dev/null || true

# --- El código está congelado: solo se reanuda si el hash sigue siendo el mismo ---
#
# La cuenta de reanudación suma los logs que ya hay en disco, pero hasta ahora no
# miraba DE QUÉ CÓDIGO eran: el directorio conservaba 4 runs de un hash y el
# launcher reanudó diciendo "4 runs ya en disco (hash nuevo)", como si fueran de
# este. Al final se mezclan runs de dos versiones en la misma muestra y el
# resultado no significa nada. Ante un hash distinto, ABORTA: vaciar el directorio
# sería lo cómodo y lo peligroso, porque se pierde una tanda entera sin que
# nadie lo decida. Que lo decida quien lanza.
MARCA="$LOGS/$ETIQUETA.hash"
if [ -f "$MARCA" ]; then
  _previo="$(cat "$MARCA" 2>/dev/null)"
  if [ "$_previo" != "$HASH" ]; then
    echo "ABORTA: $LOGS/$ETIQUETA contiene runs del codigo $_previo y ahora el codigo es $HASH." >&2
    echo "        No se reanuda un lote cambiandole el codigo a mitad: se" >&2
    echo "        mezclarian runs de dos versiones en la misma muestra." >&2
    echo "        Mueve el directorio fuera de ahi y relanza (eso es una decision)." >&2
    exit 1
  fi
else
  echo "$HASH" > "$MARCA"
fi

echo "== H21 · ruta por exp con el equipo roto | A=1 B=0 | n=$PEDIDAS en total (~$((PEDIDAS/2)) por brazo) | $REGION | hash=$HASH =="
echo "   timeout=${TIMEOUT}s vivacidad=${VIVACIDAD}s (tick ${TICK}s) | en paralelo: $PARALELO | logs en $LOGS/$ETIQUETA"
echo "   PRIMARIA: insignias/run (A-B) | sd medida 0,44 | 150 por brazo detectan +0,4"
echo "   INFORMA: trainers/run y pasos/run -- H20 fallo por llegar antes y morir antes,"
echo "           asi que el mecanismo exacto de H21 esta en si vuelve a pasar"
echo "   El mecanismo se comprueba por el marcador 'H21: sin -N salvaje(s)' en el"
echo "   motivo de la decision: si no sale, el flag no llego y nada se mide."

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
      # **Si `stat` no puede leer el log, NO se toca la run.** `stat` imprime 0
      # cuando el fichero no existe, o sea que "no existe" y "escribió en 1970"
      # eran lo mismo: el guard leía 1.791.409.360 s de silencio y mataba runs
      # perfectamente sanas. Un guard que no puede leer no puede afirmar nada, y
      # lo que hace es callarse. Matar por un dato que no tiene es peor que no
      # vigilar.
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
# **Si el fichero de runs vivas no se puede escribir, el lote NO arranca.** Así
# falló el guard el 07-10: `mktemp` dio "Permission denied" porque `/tmp` pasó a
# ser de root, `$VIVOS` quedó vacío, el `while [ -f "$VIVOS" ]` no entró nunca,
# y el lote corría **sin red de seguridad y sin decir nada**. Un guard que no
# puede vigilar tiene que fallar aquí, no en silencio.
if [ ! -w "$VIVOS" ]; then
  echo "ABORTA: no puedo escribir $VIVOS, y sin el no hay guard de vivacidad." >&2
  echo "        Un guard que no puede vigilar debe fallar aqui, no en silencio." >&2
  exit 1
fi
watchdog & WD_PID=$!

registrar_salida() {
  # **Solo en el launcher, nunca en los subshells de las runs.** `cmd &` crea un
  # subshell que hereda este trap, y cada run escribía en su propio log la
  # despedida del launcher. En un subshell `$$` es el PID del proceso padre y
  # `BASHPID` el suyo propio: si no coinciden, aquí no es el launcher.
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

# **Pidfile.** El supervisor comprueba este PID en vez de hacer `pgrep -f` por
# el nombre del script, porque el supervisor **se pasa el nombre del launcher
# como argumento**: `bash supervisor_lote.sh log/h21 45 bash exp_h20.sh ...`.
# O sea que `pgrep -f exp_h20` encuentra al propio supervisor, que empieza igual
# por "bash ", y se creería vivo un launcher muerto para siempre.
echo $$ > "$PIDFILE"

resumen_brazo() {
  local Z="$1"
  # `[ -e "$glob" ]` NUNCA expande el glob (un `*` entre comillas es un `*`
  # literal), así que el test era falso siempre y el resumen decía "sin runs"
  # aunque hubiera 150 logs en disco. Se pregunta con `compgen -G`, que sí
  # expande, y se cuenta con un glob que sí se expande en el `ls`.
  compgen -G "$LOGS/$ETIQUETA/${ETIQUETA}-${Z}-"* > /dev/null 2>&1 || {
    echo "   $Z: sin runs"; return; }
  local f n m g
  f=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-${Z}-*.txt 2>/dev/null)
  n=$(grep -h "^  insignias *:" $f 2>/dev/null | wc -l)
  m=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '{s+=$3} END {printf "%.2f", (NR?s/NR:0)}')
  g=$(grep -h "^  insignias *:" $f 2>/dev/null | awk '$3>=2' | wc -l)
  echo "   $Z: n=$n  insignias/run=$m  >=2 insignias: $g ($((100*g/(n>0?n:1)))%)"
}

lanzadas=0
entrega=0
# **Reanuda.** Las runs ya en disco cuentan como entregadas. Sin esto, cada
# relanzamiento del supervisor empezaba en `lanzadas=0` y el launcher anunciaba
# "entregadas 2/300" con 28 ficheros en disco: la contabilidad del launcher
# mentía, que es justo lo que este protocolo no permite. Los nombres llevan
# timestamp y PID, así que al reanudar no se pisa ningún log anterior.
for Z in A B; do
  n=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-${Z}-*.txt 2>/dev/null | wc -l)
  lanzadas=$((lanzadas + n))
done
entrega=$lanzadas
# El log del guard también es estado de ESTA ronda. Si el lote arranca de cero
# se vacía: si no, `matadas` suma las bajas de la ronda anterior y el recuento
# final no es el de este lote.
if [ "$lanzadas" -eq 0 ]; then
  : > "$LOG_GUARD"
fi
if [ "$lanzadas" -gt 0 ]; then
  echo "   reanudando: $lanzadas runs ya en disco (hash $HASH), quedan $((PEDIDAS - lanzadas))"
fi

# **Lanzar a reponer, no a por tandas.** Antes era: lanzar PARALELO runs, hacer
# `wait` de las PARALELO, y solo entonces lanzar la tanda siguiente. Con eso, una
# run que se cuelga 30 minutos (el `timeout` la mata) deja a **su pareja parada
# los 30 minutos**, porque el `wait` espera a las dos. El producto se va a medias.
# Ahora se mantiene el cupo lleno: en cuanto una run acaba —gane, pierda o la
# mate el guard— se lanza la siguiente. El brazo lo decide el contador de
# entregas, así que el reparto no se altera: sigue siendo A,B,A,B.
PIDS=()
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  while [ "${#PIDS[@]}" -lt "$PARALELO" ] && [ "$lanzadas" -lt "$PEDIDAS" ]; do
    lanzadas=$((lanzadas + 1))
    # El brazo lo decide el contador de entregas, no el indice del hueco: con
    # PARALELO=1 los brazos tienen que alternar A,B,A,B. Si el brazo dependiera
    # del indice, con 1 en paralelo salen todos A primero y el lote entero es
    # del mismo grupo hasta que A se agota.
    entrega=$((entrega + 1))
    if [ "$((entrega % 2))" -eq 1 ]; then BRAZO="A"; FLAG=1; else BRAZO="B"; FLAG=0; fi
    SALIDA_RUN="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$-$lanzadas.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_RUTA_POR_EXP="$FLAG" \
    PKL_HASH="$HASH" \
    timeout "$TIMEOUT" uv run --group dev python \
      juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --max-pasos "$MAX_PASOS" --reset \
      > "$SALIDA_RUN" 2>&1 &
    PID_RUN="$!"
    echo "$PID_RUN $SALIDA_RUN" >> "$VIVOS"
    PIDS+=("$PID_RUN")
  done
  # **Esperar a CUALQUIERA de las que siguen vivas**, no a todas. `wait -n` con
  # la lista de PIDs: en cuanto una termina, el bucle vuelve a lanzar la que
  # falta. Si se usara `wait` a secas, no habría forma de saber cuál se liberó.
  if [ "${#PIDS[@]}" -gt 0 ]; then
    wait -n "${PIDS[@]}" 2>/dev/null || wait "${PIDS[@]}" 2>/dev/null || true
    _VIVOS=()
    for _p in "${PIDS[@]}"; do
      kill -0 "$_p" 2>/dev/null && _VIVOS+=("$_p")
    done
    PIDS=("${_VIVOS[@]}")
  fi
  A=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | wc -l)
  B=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | wc -l)
  MAT=$(grep -c 'sin escribir' "$LOG_GUARD" 2>/dev/null || echo 0)
  # La cuenta buena es la de ficheros en disco, no la del launcher.
  if [ "$((A + B))" -lt "$lanzadas" ]; then
    echo "   !! AVISO: lanzadas $lanzadas pero solo $((A+B)) ficheros en disco."
  fi
  echo "   entregadas $lanzadas/$PEDIDAS  (A=$A B=$B matadas=$MAT"
  echo -n ")"
  # **El mecanismo, primero.** Si el flag no llegó, las insignias no significan
  # nada. H17 gastó una tanda entera así y H19 otra.
  M=$(grep -h -c 'H21: rama sin gasto' "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | awk '{s+=$1} END {printf "%d", (NR?s:0)}')
  echo "  marcador H21 en A: $M"
  # **Mirada interina.** La regla de parada esta pre-registrada en
  # `scripts/control_h21.py`, que esta DENTRO del hash a proposito: si la regla
  # de cuanto se juega viviera fuera del hash, se podria retocar a mitad de
  # tanda sin que el hash se movies. Aqui solo se para por futilidad o por
  # eficacia, ambas al IC 99%, que es mas estricto que el criterio declarado del
  # 95%. Por ningun otro motivo.
  if [ $((lanzadas % 10)) -eq 0 ]; then
    PARAR="$(uv run --group dev python juegos/pokelike/scripts/control_h21.py 2>&1)"
    echo "$PARAR" | sed 's/^/   /'
    if echo "$PARAR" | grep -q '^PARAR$'; then
      echo "== parada por regla pre-registrada en $lanzadas/$PEDIDAS runs =="
      break
    fi
  fi
done

# Vaciar lo que quede vivo. Cuando `lanzadas` llega a PEDIDAS el bucle de arriba
# sale, pero pueden quedar runs en marcha, y sin este drenaje el lote se declara
# terminado con runs a medias. Que es como se pierden las últimas.
while [ "${#PIDS[@]}" -gt 0 ]; do
  wait -n "${PIDS[@]}" 2>/dev/null || break
  _VIVOS=()
  for _p in "${PIDS[@]}"; do
    kill -0 "$_p" 2>/dev/null && _VIVOS+=("$_p")
  done
  PIDS=("${_VIVOS[@]}")
done

kill -9 "$WD_PID" 2>/dev/null
rm -f "$VIVOS"
echo "== fin | A=$A B=$B | matadas por el guard: $(grep -c 'sin escribir' "$LOG_GUARD" 2>/dev/null || echo 0) =="
resumen_brazo A
resumen_brazo B
echo "== mecanismo =="
grep -h -c 'H21: rama sin gasto' "$LOGS/$ETIQUETA"/*.txt 2>/dev/null | awk '{s+=$1} END {printf "  decisiones con el marcador: %d\n", (NR?s:0)}'
echo "== primaria =="
uv run --group dev python juegos/pokelike/scripts/control_h21.py 2>&1 | sed 's/^/  /'
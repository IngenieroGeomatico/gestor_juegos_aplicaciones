#!/usr/bin/env bash
# Supervisor de un lote: relanza el launcher si muere o si se queda mudo.
#
# POR QUÉ EXISTE, y es la razón de ser de todo este fichero:
# el 06-10 el lote base se murió a las 21:41 (su árbol de procesos cuelga del
# servicio del agente y lo limpiaron) y **nadie se enteró hasta las 06:16**:
# 8,6 h sin producir nada. El guard de vivacidad vigilaba las **runs**, pero
# **nadie vigilaba al launcher que las lanza** — y como dejó de imprimir, su
# propio log tampoco daba ninguna señal de que estuviera muerto.
#
# Un guard que vigila las unidades de trabajo no vigila el proceso que las crea.
#
# Qué mira, cada 60 s:
#   1. ¿el launcher sigue vivo?
#   2. ¿entran runs nuevas? (detecta un launcher vivo pero colgado)
#   3. ¿el lote terminó de verdad? (el launcher imprime su línea de fin)
#
# Uso:
#   bash supervisor_lote.sh <dir_de_logs> <segundos_de_silencio_max> \
#                           <orden_de_lanzamiento...>
# Por ejemplo:
#   bash supervisor_lote.sh log/h17 45 \
#     bash scripts/exp_h17.sh 300 Kanto 1800
set -u

LOGS_DIR="${1:?falta el directorio de logs}"
SILENCIO_LIMITE="${2:?falta el limite de silencio en segundos}"
shift 2
ORDEN=("$@")

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$RAIZ"

# **El log del launcher se deriva del directorio de logs.** La version anterior
# lo llevaba hardcodeado, y al hacer el sed para reutilizarla cambio el
# directorio pero no el log: dos lotes distintos escribieron en el mismo fichero
# y no se podia saber cual era cual. Es la tercera vez que un launcher dice una
# cosa y hace otra.
LOGS="$RAIZ/juegos/pokelike/$LOGS_DIR"
SALIDA="$RAIZ/juegos/pokelike/log/$(basename "$LOGS_DIR").lanzador.log"
SUP_LOG="$RAIZ/juegos/pokelike/log/$(basename "$LOGS_DIR").supervisor.log"

# El nombre del launcher, para reconocer sus procesos.
LANZADOR="$(basename "${ORDEN[0]}" .sh)"
# **El PID se lee de un pidfile, no de `pgrep -f` por el nombre.**
#
# El supervisor se pasa el nombre del launcher como argumento, o sea que su
# propia linea de comandos contiene `exp_h17.sh` y empieza igual por "bash ".
# Un `pgrep -f exp_h17` lo encuentra a EL, y `vivo()` se creería siempre que el
# launcher esta vivo: el lote podría Stay muerto indefinidamente sin que nadie
# se enterara, que es exactamente el fallo que este supervisor viene a tapar.
#
# El pidfile lo escribe el launcher al arrancar y lo borra al terminar. Si no
# existe, se deduce por nombre **excluyendo** al propio supervisor.
PIDFILE="$LOGS/$(basename "$LOGS_DIR").pid"
pat_lanz="$(printf '%s' "$LANZADOR" | cut -c1-4)""$(printf '%s' "$LANZADOR" | cut -c5-)"

: > "$SUP_LOG"
nota() { echo "[$(date '+%d/%m %H:%M')] $*" >> "$SUP_LOG"; }

contar() { ls "$LOGS"/*.txt 2>/dev/null | wc -l; }

vivo() {
  local pid
  # 1) pidfile: la via fiable, si el launcher lo escribe.
  if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    return 1
  fi
  # 2) sin pidfile: buscar por nombre, **excluyendo al propio supervisor**.
  local p c
  for p in $(pgrep -f "$pat_lanz" 2>/dev/null); do
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null)
    case "$c" in
      *"supervisor_lote"*) continue;;
      "bash "*"$LANZADOR.sh"*) return 0;;
    esac
  done
  return 1
}

matar_lanzador() {
  local pid
  if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE" 2>/dev/null)
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null
    rm -f "$PIDFILE"
  fi
  local p c
  for p in $(pgrep -f "$pat_lanz" 2>/dev/null); do
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null)
    case "$c" in
      *"supervisor_lote"*) continue;;
      "bash "*"$LANZADOR.sh"*) kill -9 "$p" 2>/dev/null;;
    esac
  done
}

lanzar() {
  setsid nohup "${ORDEN[@]}" >> "$SALIDA" 2>&1 < /dev/null &
  nota "lanzado: ${ORDEN[*]}  (log en $SALIDA)"
}

nota "arranca. silencio maximo ${SILENCIO_LIMITE}s. dir=$LOGS_DIR"
nota "orden: ${ORDEN[*]}"
vivo || lanzar

ultimo=$(contar)
ultimo_cambio=$(date +%s)
while true; do
  sleep 60
  ahora=$(date +%s)

  # El lote ha terminado de verdad: el launcher imprime su linea de fin.
  if grep -q "^== fin" "$SALIDA" 2>/dev/null; then
    nota "el lote termino. Salida."
    exit 0
  fi

  n=$(contar)
  if [ "$n" -gt "$ultimo" ]; then
    ultimo=$n
    ultimo_cambio=$ahora
    nota "$n runs"
    continue
  fi

  if ! vivo; then
    nota "el launcher NO esta vivo con $n runs. Relanzo."
    lanzar
    ultimo=$n
    ultimo_cambio=$ahora
    continue
  fi

  if [ $((ahora - ultimo_cambio)) -ge "$SILENCIO_LIMITE" ]; then
    nota "launcher vivo pero $((ahora - ultimo_cambio))s sin runs nuevas. Lo mato y relanzo."
    matar_lanzador
    sleep 5
    lanzar
    ultimo=$n
    ultimo_cambio=$ahora
  fi
done
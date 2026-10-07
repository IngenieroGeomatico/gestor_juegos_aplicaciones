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
#   bash supervisor_lote.sh <dir_de_logs> <MINUTOS_de_silencio_max> \
#                           <orden_de_lanzamiento...>
# Por ejemplo (45 MINUTOS de silencio):
#   bash supervisor_lote.sh log/h17 45 \
#     bash scripts/exp_h17.sh 300 Kanto 1800
set -u

LOGS_DIR="${1:?falta el directorio de logs}"
# **EN MINUTOS, y se multiplica por 60 al comparar.** El 07-10 esta comprobación
# comparaba segundos contra un `45` que yo pasé esperando minutos: el supervisor
# mataba el launcher cada 45 s, siete veces seguidas, y dejó 13 de 30 runs
# huérfanas sin RESUMEN. Un parámetro de tiempo sin la unidad en el nombre es una
# bomba; por eso el nombre la lleva y el uso la repite.
MINUTOS_SILENCIO="${2:?falta el limite de silencio en MINUTOS}"
SILENCIO_LIMITE=$((MINUTOS_SILENCIO * 60))
# MB libres por debajo de los cuales se recogehuerfanos y se avisa. 1200 MB con la
# maquina en 7,3 GB: dos runs en paralelo mas el editor y el agente estan justos.
UMBRAL_MB="${UMBRAL_MB:-1200}"
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

matar_arbol() {
  local pid="$1" hijo
  for hijo in $(pgrep -P "$pid" 2>/dev/null); do matar_arbol "$hijo"; done
  kill -9 "$pid" 2>/dev/null
}

matar_lanzador() {
  # **Bajar por el arbol de hijos, no matar solo el launcher.**
  #
  # La cadena es launcher(bash) -> timeout -> uv -> python -> firefox, y cada
  # firefox se lleva unos 400 MB. Matar solo el launcher deja a los cuatro
  # huerfanos y **siguen corriendo**. Con los siete relanzamientos del bug de
  # unidades del 07-10 eso apilo navegadores huerfanos hasta que systemd-oomd
  # mato **VS Code** dos veces por presion de memoria (22:06 y 22:29), no el bot:
  # el oomd mata el cgroup mas grande, y era el editor.
  local pid
  if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE" 2>/dev/null)
    if [ -n "$pid" ]; then matar_arbol "$pid"; fi
    rm -f "$PIDFILE"
  fi
  local p c
  for p in $(pgrep -f "$pat_lanz" 2>/dev/null); do
    c=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null)
    case "$c" in
      *"supervisor_lote"*) continue;;
      "bash "*"$LANZADOR.sh"*) matar_arbol "$p";;
    esac
  done
}

# **Recolector de huerfanos.** Un firefox o un python del bot cuyo PID no esta en
# el fichero de runs vivas es huerfano por definicion, y se lleva hundreds of MB.
memoria_disponible_mb() {
  awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo
}

recoger_huerfanos() {
  local vivos="$LOGS/$(basename "$LOGS_DIR").vivos"
  local p cmd pid huerfano total=0
  for p in $(pgrep -f "ms-play""wright" 2>/dev/null) $(pgrep -f "jugar_po""kelike.py" 2>/dev/null); do
    cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null)
    [ -n "$cmd" ] || continue
    huerfano=1
    while read -r pid _log; do
      [ "${pid:-}" = "$p" ] && huerfano=0 && break
    done < "$vivos"
    if [ "$huerfano" = "1" ]; then
      kill -9 "$p" 2>/dev/null && total=$((total + 1))
    fi
  done
  [ "$total" -gt 0 ] && nota "recogidos $total procesos huerfanos del bot"
  return 0
}

lanzar() {
  setsid nohup "${ORDEN[@]}" >> "$SALIDA" 2>&1 < /dev/null &
  nota "lanzado: ${ORDEN[*]}  (log en $SALIDA)"
}

nota "arranca. silencio maximo ${MINUTOS_SILENCIO} min (${SILENCIO_LIMITE}s), umbral memoria ${UMBRAL_MB} MB. dir=$LOGS_DIR"
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
    continue
  fi

  # **Memoria.** El 07-10 systemd-oomd mato **VS Code** dos veces (22:06 y 22:29)
  # por presion de memoria: no el bot, el cgroup mas grande, que era el editor.
  # El bot no era inocente: apilaba firefox huerfanos de los relanzamientos.
  # Aqui se recoge lo huerfano de verdad y, si la memoria sigue justa, se dice.
  LIBRE=$(memoria_disponible_mb)
  if [ "${LIBRE:-0}" -lt "$UMBRAL_MB" ]; then
    recoger_huerfanos
    LIBRE=$(memoria_disponible_mb)
    if [ "${LIBRE:-0}" -lt "$UMBRAL_MB" ] && [ "${AVISOS:-0}" -eq 0 ]; then
      AVISOS=1
      nota "AVISO: solo ${LIBRE} MB libres (< ${UMBRAL_MB}) y no basta con recoger huerfanos."
      nota "  -> el lote sigue; no se para por esto. Pero el OOM mata el cgroup"
      nota "     mas grande y ese no es el bot: si el editor se cae otra vez, la"
      nota "     causa somos los runs en paralelo."
    fi
  else
    AVISOS=0
    # Aunque la memoria este bien, se recogen los huerfanos: es la condicion que
    # los genero y no cuesta nada.
    recoger_huerfanos
  fi
done
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
  local pid c p
  # **1) pidfile, pero solo si su PID sigue vivo.** Si el PID esta muerto NO se
  # devuelve falso aqui: se cae al plan B por nombre. Un pidfile obsoleto (el de
  # un launcher anterior, que sigue en disco hasta que el nuevo lo escribe)
  # hacia que el supervisor declarase muerto a un launcher **vivo**, y se
  # relanzaba en bucle.
  if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi

  # **2) plan B: buscar por nombre, excluyendo al supervisor y a los ancestros.**
  # Hace falta porque `setsid nohup bash ... &` crea subshells que heredan la
  # linea de ordenes del launcher, asi que `pgrep -f` devuelve mas de un PID y
  # solo UNO es el launcher de verdad. El ancestorsco descarta al supervisor
  # (lleva el nombre del launcher como argumento) y al shell del agente.
  local PROPIOS=" "
  local w q
  PROPIOS="$PROPIOS$$ "
  w=$(awk '/^PPid:/{print $2}' "/proc/$$/status" 2>/dev/null)
  while [ -n "$w" ] && [ "$w" -gt 1 ] 2>/dev/null; do
    case "$PROPIOS" in *" $w "*) break;; esac
    PROPIOS="$PROPIOS$w "
    q=$(awk '/^PPid:/{print $2}' "/proc/$w/status" 2>/dev/null)
    [ "$q" = "$w" ] && break
    w="$q"
  done

  for p in $(pgrep -f "$pat_lanz" 2>/dev/null); do
    case "$PROPIOS" in *" $p "*) continue;; esac
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

memoria_disponible_mb() {
  awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo
}

# El fichero de runs vivas. El launcher lo escribe en `log/<etiqueta>.vivos`,
# o sea **fuera** del directorio del lote. Buscarlo por glob evita tener que
# reconstruir esa ruta, que ya se equivoco una vez: el recolector miraba
# `log/h17/h17.vivos` y el fichero real es `log/h17.vivos`, asi que no recogia a
# nadie y los huerfanos se acumulaban.
fichero_vivos() { ls "$RAIZ"/juegos/pokelike/log/*.vivos 2>/dev/null | head -1; }

# **Recolector de huerfanos.**
#
# Un firefox o un python del bot cuyo PID no esta en el fichero de runs vivas es
# huerfano por definicion, y se lleva cientos de MB.
#
# **Falla al reves**: si no se puede leer la lista de vivas, NO mata nada. El
# error de esta funcion en la otra direccion seria matar las runs legitimas,
# que es una perdida de lote; dejar un huerfano 400 MB es solo una molestia.
recoger_huerfanos() {
  local vivos total=0
  vivos="$(fichero_vivos)"
  if [ -z "$vivos" ] || [ ! -r "$vivos" ]; then
    return 0
  fi
  # **Tabla vacia = no se toca nada.** El launcher hace `: > "$VIVOS"` al
  # arrancar, y entre ese instante y el primer `echo pid log` hay una ventana
  # en la que la tabla esta vacia. Leyendola en esa ventana, no se encuentra
  # ningun PID vivo y se concluye que TODO es huerfano: se matan las runs que
  # acaban de lanzarse. Sucedio a las 23:13.
  #
  # Una tabla vacia significa "todavia no se ha escrito nada", no "no queda
  # nadie vivo".
  if [ ! -s "$vivos" ]; then
    return 0
  fi

  # **Firma precisa del run, NO un `pgrep` flojo.**
  #
  # `pgrep -f jugar_pokelike.py` encuentra a CUALQUIER proceso cuya linea de
  # comandos contenga ese nombre, incluido el shell del propio agente cuando
  # escribe un comando que lo menciona. Cuatro veces seguidas hoy: la primera
  # mato mi shell, y esta vez la mato el recolector que acababa de escribir, que
  # se llevo por delante un proceso inocente. Un `pgrep` flojo aqui mata gente.
  #
  # La firma real de un run es la invocacion completa: `timeout N uv run --group
  # dev python juegos/pokelike/scripts/jugar_pokelike.py`. Un shell no la tiene.
  local SIG="uv run --group dev python juegos/pokelike/scripts/jugar""_pokelike.py"
  local raiz huerfano pid

  # **Nunca matar a un ancestro propio.** La firma no basta: si el shell del
  # agente escribe un comando que la contiene, ese shell la tiene en su linea de
  # comandos y es indistinguible de un run. Aqui ya lo hizo: al PROBAR el
  # recolector con la firma escrita en el comando, ese comando se mato a si
  # mismo.
  #
  # La unica distincion fiable es genealogica: el supervisor no puede matar a
  # quien lo puso en marcha. Se listan el propio PID y todos sus ancestros, y
  # cualquier PID de esa lista queda fuera siempre.
  local PROPIOS=" "
  local w q
  PROPIOS="$PROPIOS$$ "
  w=$(awk '/^PPid:/{print $2}' "/proc/$$/status" 2>/dev/null)
  while [ -n "$w" ] && [ "$w" -gt 1 ] 2>/dev/null; do
    case "$PROPIOS" in *" $w "*) break;; esac
    PROPIOS="$PROPIOS$w "
    q=$(awk '/^PPid:/{print $2}' "/proc/$w/status" 2>/dev/null)
    [ "$q" = "$w" ] && break
    w="$q"
  done

  # Raices: procesos `timeout` cuya linea contiene la firma. Cada run es uno.
  for raiz in $(pgrep -f "timeout" 2>/dev/null); do
    case "$PROPIOS" in *" $raiz "*) continue;; esac
    grep -qF "$SIG" "/proc/$raiz/cmdline" 2>/dev/null || continue
    # Si esta raiz esta viva segun la tabla, todo su arbol es legitimo.
    local es_vivo=0
    while read -r pid _log; do
      [ "${pid:-}" = "$raiz" ] && es_vivo=1 && break
    done < "$vivos"
    [ "$es_vivo" = "1" ] && continue
    # Raiz huerfana: se lleva su arbol entero.
    total=$((total + 1))
    matar_arbol "$raiz"
  done
  [ "$total" -gt 0 ] && nota "recogidas $total runs huerfanas (raices sin cerrar)"
  return 0
}

# Gracia tras lanzar: no se declara muerto a un launcher durante estos segundos.
# El pidfile del launcher ANTERIOR sigue en disco mientras el nuevo arranca, asi
# que `vivo()` lee un PID muerto y declara muerto al recien lanzado: a los 60 s
# de arrancar se relanzaba solo, en bucle.
GRACIA_SEG="${GRACIA_SEG:-180}"
arrancado_en=0

lanzar() {
  # **SALIDA se le pasa al launcher por entorno**, para que su trap de salida
  # escriba en el MISMO log que el supervisor. Si cada uno escribiera en el suyo,
  # el diagnostico de por que se muere quedaria en un fichero aparte y habria que
  # ir a buscarlo.
  SALIDA="$SALIDA" setsid nohup "${ORDEN[@]}" >> "$SALIDA" 2>&1 < /dev/null &
  arrancado_en=$(date +%s)
  nota "lanzado: ${ORDEN[*]}  (log en $SALIDA). Gracia ${GRACIA_SEG}s."
}

nota "arranca. silencio maximo ${MINUTOS_SILENCIO} min (${SILENCIO_LIMITE}s), umbral memoria ${UMBRAL_MB} MB. dir=$LOGS_DIR"
nota "orden: ${ORDEN[*]}"
if ! vivo; then lanzar; fi

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

  if ! vivo && [ $((ahora - arrancado_en)) -ge "$GRACIA_SEG" ]; then
    nota "el launcher NO esta vivo con $n runs. Recojo sus huerfanos y relanzo."
    recoger_huerfanos
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
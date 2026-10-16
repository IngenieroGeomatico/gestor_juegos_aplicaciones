#!/usr/bin/env bash
# Limpieza manual de los bots de Pokelike y de los navegadores que abren.
#
# Por que existe este script y no un `pkill` suelto: los navegadores se buscan
# por su línea de órdenes, y el servidor MCP de Firefox de OpenCode
# (`node .../firefox-devtools-mcp`) lleva la palabra "firefox" en la suya. Con
#
#     ps -eo pid,args | grep -E "firefox" | grep -v grep | awk '{print $1}' | xargs -r kill -9
#
# se le envía SIGKILL al servidor MCP. El SIGKILL no se puede capturar, así que
# su cierre ordenado nunca corre y OpenCode marca el servidor como *failed*
# ("Connection closed: MCP server process exited"), con el último stdout que
# alcanzó a escribir. Ver AGENT.md.
#
# Aquí los navegadores se matan por **nombre de proceso** (`-x firefox`), que no
# casa con `node`, y los bots por patrón de línea de órdenes **excluyendo** el
# propio script, sus antepasados y cualquier herramienta de MCP.
#
# Uso:
#   bash juegos/pokelike/scripts/matar_bot.sh              # bots + navegadores
#   bash juegos/pokelike/scripts/matar_bot.sh --bots       # solo los bots
#   bash juegos/pokelike/scripts/matar_bot.sh --navegadores
#
# Sale con 0 siempre, aunque no hubiera nada que matar.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# El perfil que abre el bot (navegador.py: PERFIL). Con ruta absoluta y
# relativa, porque el argv del Firefox lleva la que usara el proceso.
PAT_PERFIL="$RAIZ/juegos/pokelike/data/bot/perfil|data/bot/perfil"

# Línea de órdenes que contiene esto = herramienta del editor, no navegador.
readonly HERRAMIENTAS='firefox-devtools-mcp|@playwright/mcp|ms-playwright/mcp|playwright-mcp'
readonly SENAL=9
readonly PAT_FF="ms-playwright/firefox-[0-9]*/firefox/firefox"

solo_bots=0
solo_navegadores=0
case "${1:-}" in
  --bots) solo_bots=1; solo_navegadores=0 ;;
  --navegadores) solo_bots=0; solo_navegadores=1 ;;
  "") ;;
  *) echo "uso: $0 [--bots|--navegadores]" >&2; exit 2 ;;
esac

# Este script y sus antepasados. Sin esto, `pgrep -f` encuentra al propio shell
# que lo invocó (el patrón aparece en su línea de órdenes) y se suicidea.
ancestros() {
  local pid=$$
  while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null; do
    printf '%s\n' "$pid"
    pid="$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null)" || break
  done
}

cmdline() {
  # El proceso puede morir entre `pgrep` y la lectura: sin `-r` el shell avisa.
  [ -r "/proc/$1/cmdline" ] || return 1
  tr '\0' ' ' < "/proc/$1/cmdline"
}

es_propio() {
  local pid=$1 a
  while read -r a; do
    [ "$a" = "$pid" ] && return 0
  done < <(ancestros)
  case "$(cmdline "$pid" 2>/dev/null)" in
    *matar_bot.sh*) return 0 ;;
  esac
  return 1
}

es_herramienta() {
  cmdline "$1" 2>/dev/null | grep -qE "$HERRAMIENTAS"
}

matar() {
  local pid=$1 etiqueta=$2
  # El proceso puede morir entre `pgrep` y aquí: se ignora en silencio.
  [ -d "/proc/$pid" ] || return 0
  es_propio "$pid" && { echo "  = $pid $etiqueta (yo mismo, se respeta)"; return 0; }
  es_herramienta "$pid" && { echo "  - $pid $etiqueta (herramienta MCP, se respeta)"; return 0; }
  if kill -"$SENAL" "$pid" 2>/dev/null; then
    echo "  x $pid $etiqueta"
  fi
}

matar_patron() {
  local patron=$1 etiqueta=$2 pid
  for pid in $(pgrep -f -- "$patron" 2>/dev/null); do
    matar "$pid" "$etiqueta"
  done
}

matar_navegadores() {
  # 1) Los del bot con perfil persistente: firma exacta, cero falsos positivos.
  matar_patron "$PAT_PERFIL" "firefox(bot, perfil)"
  # 2) Los de perfil temporal de Playwright: `firefox` en la ruta del binario.
  matar_patron "$PAT_FF" "firefox(bot, temporal)"
  # 3) Por nombre de proceso. `pgrep -x` compara el `comm` de /proc, no la línea
  #    de órdenes: el MCP de Firefox es `node`/`npm exec`/`sh`, así que no se ve
  #    afectado aunque su argv lleve "firefox-devtools-mcp".
  for pid in $(pgrep -x firefox 2>/dev/null) $(pgrep -x headless_shell 2>/dev/null) \
             $(pgrep -f -- "firefox-bin" 2>/dev/null); do
    matar "$pid" "firefox(nombre)"
  done
}

if [ "$solo_bots" -eq 0 ]; then matar_navegadores; fi

if [ "$solo_navegadores" -eq 0 ]; then
  matar_patron "scripts/jugar_pokelike.py" "bot"
  matar_patron "scripts/lanzar_tanda.py" "lanzador"
  matar_patron "scripts/supervisor_lote.sh" "supervisor"
  matar_patron "scripts/exp_h2[01].sh" "experimento"
fi

sleep 2

# Informe: qué queda vivo y si el navegador del bot está limpio (regla 3 de
# AGENT.md: cerrar cualquier Firefox abierto antes de lanzar). Los shells
# ancestors no cuentan: si el patrón está en su línea de órdenes es que los
# escribió el propio comando que invocó este script.
sobran() {
  local pid
  for pid in $(pgrep -f -- "$PAT_PERFIL|$PAT_FF" 2>/dev/null); do
    es_propio "$pid" && continue
    [ -d "/proc/$pid" ] || continue
    printf '%s %s\n' "$pid" "$(cmdline "$pid" 2>/dev/null | cut -c1-90)"
  done
}
if [ -n "$(sobran)" ]; then
  echo "AVISO: quedan navegadores del bot vivos:" >&2
  sobran >&2
  exit 1
fi

echo "Limpio. Memoria libre: $(awk '/MemAvailable/ {printf "%.1f GB", $2/1048576}' /proc/meminfo)"

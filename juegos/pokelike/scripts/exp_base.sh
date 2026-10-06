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
# Lo que este sí cumple, y son las tres reglas del protocolo:
#   - **nº de runs exacto**: bucle `while lanzadas < pedidas`, y se cuenta lo
#     lanzado, no lo esperado.
#   - **hash de código en la cabecera de cada log**, para separar lotes sin
#     acordarse de cuándo se editó.
#   - **timeout por run**, que cuenta como fracaso. 3600 s, no 1500: con 1500 el
#     techo se comía solo las runs largas y solo del brazo tratado (5 timeouts
#     en A contra 0 en B, 18 puntos de insignia de diferencia).
#
# Uso:  bash exp_base.sh [runs] [region] [max_pasos] [timeout]
set -u

PEDIDAS="${1:-150}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-1500}"
TIMEOUT="${4:-3600}"

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"
ETIQUETA="base"

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

echo "== línea base | n=$PEDIDAS | $REGION | timeout=${TIMEOUT}s | max_pasos=$MAX_PASOS | hash=$HASH =="
echo "   logs en $LOGS/$ETIQUETA"
echo "   PKL_CAPTURA_PERMISIVA sin tocar -> default 1 (H15 encendido)"

if [ ! -f "$RAIZ/juegos/pokelike/scripts/jugar_pokelike.py" ]; then
  echo "ABORTA: no encuentro jugar_pokelike.py" >&2
  exit 1
fi
if ! command -v uv > /dev/null 2>&1; then
  echo "ABORTA: no hay \`uv\` en el PATH" >&2
  exit 1
fi

lanzadas=0
while [ "$lanzadas" -lt "$PEDIDAS" ]; do
  for _ in 1 2; do
    [ "$lanzadas" -ge "$PEDIDAS" ] && break
    lanzadas=$((lanzadas + 1))
    # El nombre lleva el indice de la run, NO solo el timestamp. Los dos runs
    # de un par salen en el mismo segundo, y el segundo `>` trunca al primero:
    # se perdia la mitad del lote sin que se notara (el launcher anunciaba
    # "entregadas 4" con 2 ficheros en disco). En `exp_captura.sh` esto lo
    # evita la etiqueta A/B del nombre; aqui, que no hay brazos, hay que poner
    # el indice a mano. `$$` (pid del launcher) + el indice es unico, y se
    # conoce ANTES de lanzar, asi que no hay carrera con el `>`.
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-$(date +%H%M%S)-$$-$lanzadas.txt"
    PKL_BRAZO=base \
    PKL_HASH="$HASH" \
    timeout "$TIMEOUT" uv run --group dev python \
      juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --max-pasos "$MAX_PASOS" --reset \
      > "$SALIDA" 2>&1 &
  done
  wait
  ENTREGADOS=$(ls "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null | wc -l)
  COMPLETOS=$(grep -l "resultado *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null | wc -l)
  # Si entregados < lanzadas, se estan pisando: avisar, no seguir en silencio.
  # Es la regla "cuenta las runs antes de lanzar" hecha comprobacion.
  if [ "$ENTREGADOS" -lt "$lanzadas" ]; then
    echo "   !! AVISO: lanzadas $lanzadas pero solo $ENTREGADOS ficheros en disco."
  fi
  echo "   entregadas $lanzadas/$PEDIDAS  (en disco $ENTREGADOS, cerradas $COMPLETOS)"
done

echo "== fin: $lanzadas runs en $LOGS/$ETIQUETA =="
echo "== resumen del lote (leer de RESUMEN, nunca del log entero) =="
grep -h "^  insignias *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null |
  awk '{s+=$3; n++; if($3>m) m=$3} END {printf "   media %.2f en %d runs | maximo %d\n", (n?s/n:0), n, m}'
grep -h "^  capturas *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null |
  awk '{s+=$3; n++} END {printf "   capturas/run %.2f\n", (n?s/n:0)}'
grep -h "^  equipo *:" "$LOGS/$ETIQUETA"/${ETIQUETA}-*.txt 2>/dev/null |
  awk '{s+=$1; n++} END {printf "   mons en el equipo %.2f\n", (n?s/n:0)}'

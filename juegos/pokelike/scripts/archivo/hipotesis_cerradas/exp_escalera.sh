#!/usr/bin/env bash
# ESCALERA DE RIESGO: la pregunta pendiente desde hace semanas (n=300).
#
# Que mide: insignias por partida CON la escalera de riesgo
# (A, PKL_ESCALERA_RIESGO=1, el default actual) frente a SIN ella
# (B, =0, el comportamiento literal de antes, que premia pelear con caidos).
#
# Por que esta y no otra:
#   - La escalera esta **encendida por defecto** desde que se implemento y
#     **nunca se ha medido**. El unico lote que la midio (24 runs) se paro
#     pronto porque el flag era un no-op; despues se arreglo el sitio donde se
#     aplicaba y ya no se volvio a medir.
#   - Es la causa documentada de la mitad de las muertes: de 95 runs limpias
#     (H13), **45% mueren contra un entrenador de ruta** (43 de 95), y de las
#     72 peleas con <=2 mons en pie, 50 tenian alternativa en pantalla.
#   - Ya se sabe que **gana** a la alternativa cuando la hay
#     (`test_la_escalera_gana_al_bono_de_ruta`), asi que la duda no es si
#     cambia la decision sino si mejora el resultado.
#
# TAMANO DE MUESTRA, que es lo que faltaba en los experimentos anteriores:
#   sd(insignias) = 0.92 medida sobre 149 runs limpias. Para detectar 0,3
#   insignias con potencia 80% y alpha 0.05 hacen falta **147 por brazo**
#   (295 en total); para 0,2, 332 por brazo. A 2 en paralelo y ~0,15 h/run,
#   300 runs son ~0,7 h. Con n=48 (lo de antes) solo se detectan efectos de
#   >=0,74: los tres nulos anteriores fueron "no se puede ver", no "no funciona".
#
# SECUNDARIA: capturas por insignia, no `pasos`. `pasos` es nuestro y premia
# morir rapido: una estrategia que avoida trainers alarga la run sin ganarla.
# Las capturas SI son un coste explicito (un nodo gastado), asi que suben las
# insignias y bajan las capturas por insignia =_selectividad real.
set -u

PEDIDAS="${1:-300}"
REGION="${2:-Kanto}"
MAX_PASOS="${3:-1500}"

RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$RAIZ/juegos/pokelike/log"

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
          done; } | sha256sum | cut -c1-8 )"
cd "$RAIZ"

ETIQUETA="escalera"
mkdir -p "$LOGS/$ETIQUETA"

echo "== escalera de riesgo: A=con(1) B=sin(0), n=$PEDIDAS, hash=$HASH =="
echo "   region=$REGION  logs en $LOGS/$ETIQUETA"
echo "   primaria: insignias | secundaria: capturas por insignia"

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
  for k in 0 1; do
    if [ "$k" -eq 0 ]; then BRAZO="A"; ESC=1; else BRAZO="B"; ESC=0; fi
    SALIDA="$LOGS/$ETIQUETA/${ETIQUETA}-${BRAZO}-$(date +%H%M%S)-$$.txt"
    PKL_BRAZO="$BRAZO" \
    PKL_ESCALERA_RIESGO="$ESC" \
    PKL_ITEM_HUECOS=1 \
    PKL_HASH="$HASH" \
    timeout 1500 uv run --group dev python \
      juegos/pokelike/scripts/jugar_pokelike.py \
      --region "$REGION" --max-pasos "$MAX_PASOS" --reset \
      > "$SALIDA" 2>&1 &
  done
  lanzadas=$((lanzadas + 2))
  wait
  A=$(grep -lc "brazo=A" "$LOGS/$ETIQUETA"/${ETIQUETA}-A-*.txt 2>/dev/null | wc -l)
  B=$(grep -lc "brazo=B" "$LOGS/$ETIQUETA"/${ETIQUETA}-B-*.txt 2>/dev/null | wc -l)
  echo "   entregadas $lanzadas/$PEDIDAS  (A=$A B=$B)"
done

echo "== fin: $PEDIDAS runs en $LOGS/$ETIQUETA =="
echo "== paridad: A=$A B=$B =="
echo "== sanity: muertes por entrenador, por brazo =="
for Z in A B; do
  echo "   $Z: $(grep -h "COMBATE PERDIDO contra" "$LOGS/$ETIQUETA"/${ETIQUETA}-$Z-*.txt 2>/dev/null |
      grep -c "wants to battle") losses to route trainers"
done
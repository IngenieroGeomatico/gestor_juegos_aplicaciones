# `archivo/` — código de experimentos ya cerrados

Nada de esto se ejecuta. Está aquí por **traza**, no por uso.

## Por qué en un subdirectorio y no borrado

El hash de cada lote se calcula sobre `juegos/pokelike/scripts/*.py` y
`scripts/*.sh`, y ese glob **no es recursivo**. Mover un fichero aquí lo saca
del hash, que es justo lo que se quiere: un experimento cerrado no debe poder
invalidar el lote que se está lanzando ahora por haber tocado un fichero que
nadie va a ejecutar.

Borrarlos tiraría la única copia del guion con la que se lanzo cada tanda. El
histórico de lo que se midió está en [`CUADERNO.md`](../../CUADERNO.md); aquí
está el código, que es lo que no se puede reconstruir desde un resumen.

## Qué hay aquí y por qué ya no se usa

| Fichero | Hipótesis | Por qué se archivó |
|---|---|---|
| `exp_h17.sh` | H17 · capturar cuando falta nivel | **Refutada** (n=114/110) |
| `control_h18.py` | H18 · parar por futilidad/eficacia | H18 **retractada** antes de datos: el peso no era la restricción |
| `exp_h18.sh` | ídem | ídem |
| `control_h19.py` | H19 · reroll solo con el equipo roto | H19 **retractada**: el mecanismo salía en el 1,2% de las runs |
| `exp_h19.sh` | ídem | ídem |
| `exp_escalera.sh` | escalera de riesgo | **V1**: el veto duro salió contraproducente (p=0,020) |
| `exp_captura.sh` | captura permisiva (H15) | **V2**: confirmada, ya no hace falta el A/B |
| `exp_trade.sh` | Búsqueda de trade (H6) | era un bug de DOM, ya arreglado |
| `exp_vetonivel.sh` | veto por nivel | mecanismo del **7%**: por debajo del 15% no se lanza (§1.5) |
| `exp_itemhueco.sh` | objeto en el hueco | `PESO_OBJETO` nunca se encendió |
| `exp_base.sh`, `linea_base.sh` | línea base de insignias/run | la línea base ya está medida (`perfil_winner.py`) |
| `exp3.sh` | barrido de flags inicial | anterior a `EXP`, que ya es el diccionario de flags |
| `many_runs.py` | lanzamiento en paralelo | sustituido por `exp_h20.sh` |
| `medir_hipotesis.py` | medición agregada inicial | sustituido por `scripts/medir/` |
| `informe_escalera.py`, `informe_exp.py` | informes de lotes antiguos | esos lotes ya se hicieron; sus datos siguen en `log/` |

### `launchers_previos/`

| Fichero | Por qué se archivó |
|---|---|
| `culminacion.sh` | encadenaba tandas **fuera** de una unidad de systemd. Cuatro lotes murieron porque `oomd` mataba a VS Code y se llevaba el lote: el lote hereda el cgroup de quien lo lanza. Hoy el lote vive en `systemd-run --user` (§5.6) |
| `experimento_loop.sh` | antecesor de `supervisor_lote.sh`, que además mira la marca de hash y aborta si el código no es el del lote |

Los que quedan **vivos** en `scripts/` son los que se ejecutan hoy:
`jugar_pokelike.py`, `planificador.py`, `politica.py`, `navegador.py`,
`firefox_remoto.py`, `test_integridad.py`, `data_store.py`,
`estadistica.py`, `control_h20.py`, `exp_h20.sh`, `supervisor_lote.sh`,
`lanzar_tanda.py`, y los de datos (`registrar_run.py`, `cobertura_equipo.py`,
`preparar_perfil.py`, `sondear_objetos.py`, `extraer_datos.py`).

## Si hay que resucitar algo de aquí

Se copia de vuelta a `scripts/` **y se vuelve a lanzar entero**. El hash lo
comprueba: si el directorio del lote no tiene la misma marca, `exp_h20.sh`
aborta en vez de mezclar versiones (§5.1).
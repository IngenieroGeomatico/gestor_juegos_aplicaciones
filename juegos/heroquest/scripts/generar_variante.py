#!/usr/bin/env python3
"""Genera una variante «alterada» de una misión existente.

La variante mantiene los mismos elementos (monstruos, tesoros, trampas,
marcadores, muebles) pero los reubica en disposición distinta sobre el
tablero.  La narrativa (introducción, objetivo, recompensa, instrucciones
de voz alta) se preserva intacta.

Uso::

    uv run juegos/heroquest/scripts/generar_variante.py \\
        --mision "La Fortaleza Fronteriza de In-Gulden" --semilla 42

    # Guardar directamente en misiones.json:
    uv run juegos/heroquest/scripts/generar_variante.py \\
        --mision "La Fortaleza Fronteriza de In-Gulden" --semilla 7 --guardar
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── E/S JSON ────────────────────────────────────────────────────────────────


def _cargar(nombre: str) -> list[dict]:
    with (DATA_DIR / f"{nombre}.json").open(encoding="utf-8") as f:
        return json.load(f)


def _guardar(nombre: str, datos: list[dict]) -> None:
    with (DATA_DIR / f"{nombre}.json").open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _celdas_prohibidas(mision: dict) -> set[tuple[int, int]]:
    """Celdas que ningún elemento puede ocupar: puertas (ambos extremos),
    puertas secretas, entrada de héroes y salida.

    La salida se trata como un rectángulo completo: salida_heroes usa
    ``{"de": [x1,y1], "a": [x2,y2]}`` con esquinas opuestas, así que toda
    el área entre ambas esquinas es zona de salida."""
    prohibidas: set[tuple[int, int]] = set()

    def _rect_esquinas(desde: list[int], hasta: list[int]) -> set[tuple[int, int]]:
        return {
            (x, y)
            for x in range(desde[0], hasta[0] + 1)
            for y in range(desde[1], hasta[1] + 1)
        }

    for p in mision.get("puertas", []):
        if "de" in p:
            prohibidas.add(tuple(p["de"]))
            prohibidas.add(tuple(p["a"]))
        else:
            prohibidas.add((p["x"], p["y"]))

    for p in mision.get("puertas_secretas", []):
        prohibidas.add(tuple(p["de"]))
        prohibidas.add(tuple(p["a"]))

    for e in mision.get("entrada_heroes", []):
        prohibidas.add((e["x"], e["y"]))

    salida = mision.get("salida_heroes", {})
    if isinstance(salida, dict) and "de" in salida:
        prohibidas |= _rect_esquinas(salida["de"], salida["a"])
    elif isinstance(salida, list):
        for s in salida:
            if isinstance(s, dict) and "de" in s:
                prohibidas |= _rect_esquinas(s["de"], s["a"])

    return prohibidas


# ── Utilidades de cuadrícula ────────────────────────────────────────────────


def _celdas_rect(rect: dict) -> set[tuple[int, int]]:
    """Todas las celdas (x, y) dentro de un rectángulo."""
    return {
        (x, y)
        for x in range(rect["x"], rect["x"] + rect["ancho"])
        for y in range(rect["y"], rect["y"] + rect["alto"])
    }


def _celdas_sala(board_room: dict) -> set[tuple[int, int]]:
    """Unión de celdas de todos los rects de una sala del tablero."""
    celdas: set[tuple[int, int]] = set()
    for rect in board_room["rects"]:
        celdas |= _celdas_rect(rect)
    return celdas


def _sala_de_casilla(tablero: dict, x: int, y: int) -> int | None:
    """Número de sala del tablero a la que pertenece (x, y), o None si es
    pasillo/roca dura."""
    for s in tablero["salas"]:
        for rect in s["rects"]:
            if (
                rect["x"] <= x < rect["x"] + rect["ancho"]
                and rect["y"] <= y < rect["y"] + rect["alto"]
            ):
                return s["numero"]
    return None


def _salas_esenciales(mision: dict, tablero: dict) -> set[int]:
    """Salas físicas que contienen la entrada o la salida de héroes: no
    pueden convertirse en roca dura, o la misión sería inaccesible."""
    esencial: set[int] = set()
    for e in mision.get("entrada_heroes", []):
        s = _sala_de_casilla(tablero, e["x"], e["y"])
        if s is not None:
            esencial.add(s)
    salida = mision.get("salida_heroes", {})
    if isinstance(salida, dict) and "de" in salida:
        s = _sala_de_casilla(tablero, salida["de"][0], salida["de"][1])
        if s is not None:
            esencial.add(s)
    elif isinstance(salida, list):
        for sal in salida:
            if isinstance(sal, dict) and "de" in sal:
                s = _sala_de_casilla(tablero, sal["de"][0], sal["de"][1])
                if s is not None:
                    esencial.add(s)
    return esencial


def _demanda_contenido(contenido: dict) -> int:
    """Celdas mínimas que necesita un contenido (muebles + items)."""
    demanda = 0
    for m in contenido.get("muebles", []):
        d, h = m["desde"], m["hasta"]
        demanda += (h[0] - d[0] + 1) * (h[1] - d[1] + 1)
    for tipo in ("monstruos", "tesoros", "trampas", "marcadores"):
        demanda += len(contenido.get(tipo, []))
    return demanda


def _capacidad_sala(
    tablero: dict, num_sala: int, prohibidas: set[tuple[int, int]]
) -> int:
    """Celdas jugables de la sala (fuera de puertas/entrada/salida)."""
    br = next(s for s in tablero["salas"] if s["numero"] == num_sala)
    return len(_celdas_sala(br) - prohibidas)


def _mueble_cabe_en_sala(
    mueble: dict, num_sala: int, tablero: dict
) -> bool:
    """True si el rectángulo del mueble cabe en algún rect de la sala."""
    br = next(s for s in tablero["salas"] if s["numero"] == num_sala)
    ancho = mueble["hasta"][0] - mueble["desde"][0] + 1
    alto = mueble["hasta"][1] - mueble["desde"][1] + 1
    for rect in br["rects"]:
        if ancho <= rect["ancho"] and alto <= rect["alto"]:
            return True
    return False


def _emparejar_contenidos(
    contenidos: list[dict],
    salas_destino: list[int],
    tablero: dict,
    prohibidas: set[tuple[int, int]],
) -> list[int] | None:
    """Asigna cada contenido a una sala física (best-fit: el contenido más
    grande a la sala más pequeña que pueda albergarlo).

    Devuelve la lista de salas en el mismo orden que *contenidos*, o None
    si no hay emparejamiento posible."""
    orden = sorted(range(len(contenidos)), key=lambda i: -_demanda_contenido(contenidos[i]))
    salas_libres = list(salas_destino)
    salas_por_demanda: list[tuple[int, int]] = []
    for s in salas_libres:
        cap = _capacidad_sala(tablero, s, prohibidas)
        salas_por_demanda.append((s, cap))
    salas_por_demanda.sort(key=lambda sc: sc[1])  # de menor a mayor capacidad

    resultado: list[int | None] = [None] * len(contenidos)
    for i in orden:
        contenido = contenidos[i]
        demanda = _demanda_contenido(contenido)
        objetivo = None
        # Buscar la sala más pequeña que pueda con el contenido
        for j, (s, cap) in enumerate(salas_por_demanda):
            if cap >= demanda and all(
                _mueble_cabe_en_sala(m, s, tablero)
                for m in contenido.get("muebles", [])
            ):
                objetivo = j
                break
        if objetivo is None:
            return None
        s, _ = salas_por_demanda.pop(objetivo)
        resultado[i] = s

    return [s for s in resultado if s is not None]


def _escoger_salas(
    tablero: dict,
    n: int,
    fijas: list[int] | None,
    esenciales: set[int],
    rng: random.Random,
) -> list[int]:
    """Elige las *n* salas físicas donde se montará la variante.

    Las salas en *esenciales* (entrada/salida de héroes) siempre se
    conservan.  Si *fijas* se da (--salas), se usa tal cual siempre que
    contenga a las esenciales (si falta alguna, se añade).  Sin *fijas*,
    se completan *n* salas al azar de entre las del tablero."""
    todas = [s["numero"] for s in tablero["salas"]]
    if fijas is not None:
        elegidas = list(dict.fromkeys(fijas))  # elimina duplicados, respeta orden
        for e in sorted(esenciales):
            if e not in elegidas:
                elegidas.append(e)
        return elegidas
    resto = [x for x in todas if x not in esenciales]
    rng.shuffle(resto)
    elegidas = sorted(esenciales) + resto[: max(0, n - len(esenciales))]
    return elegidas


def _es_pasillo(tablero: dict, x: int, y: int) -> bool:
    """True si (x, y) es jugable y no pertenece a ninguna sala."""
    if [x, y] in tablero.get("no_jugables", []):
        return False
    for sala in tablero["salas"]:
        for rect in sala["rects"]:
            if (
                rect["x"] <= x < rect["x"] + rect["ancho"]
                and rect["y"] <= y < rect["y"] + rect["alto"]
            ):
                return False
    return True


# ── Colocación aleatoria ───────────────────────────────────────────────────


def _colocar_mobiliario(
    muebles: list[dict],
    board_room: dict,
    ocupadas: set[tuple[int, int]],
    rng: random.Random,
    prohibidas: set[tuple[int, int]] = frozenset(),
) -> list[dict]:
    """Coloca cada mueble en una posición válida dentro de *algún* rect de
    la sala (sin solapar con lo ya ocupado ni con celdas prohibidas).
    Si no cabe, se omite."""
    resultado: list[dict] = []
    for mueble in muebles:
        desde = mueble["desde"]
        hasta = mueble["hasta"]
        ancho = hasta[0] - desde[0] + 1
        alto = hasta[1] - desde[1] + 1

        candidatas: list[tuple[int, int]] = []
        for rect in board_room["rects"]:
            for x in range(rect["x"], rect["x"] + rect["ancho"] - ancho + 1):
                for y in range(rect["y"], rect["y"] + rect["alto"] - alto + 1):
                    celdas_m = {
                        (x + dx, y + dy)
                        for dx in range(ancho)
                        for dy in range(alto)
                    }
                    if not (celdas_m & ocupadas) and not (celdas_m & prohibidas):
                        candidatas.append((x, y))

        if candidatas:
            nx, ny = rng.choice(candidatas)
            nuevo = copy.deepcopy(mueble)
            nuevo["desde"] = [nx, ny]
            nuevo["hasta"] = [nx + ancho - 1, ny + alto - 1]
            resultado.append(nuevo)
            ocupadas |= {
                (nx + dx, ny + dy) for dx in range(ancho) for dy in range(alto)
            }
        # else: mueble demasiado grande para la sala → se omite silenciosamente

    return resultado


def _colocar_items(
    items: list[dict],
    celdas_sala: set[tuple[int, int]],
    ocupadas: set[tuple[int, int]],
    rng: random.Random,
    prohibidas: set[tuple[int, int]] = frozenset(),
) -> list[dict]:
    """Coloca cada item en una celda libre distinta de la sala, sin pisar
    celdas prohibidas."""
    libres = list(celdas_sala - ocupadas - prohibidas)
    rng.shuffle(libres)
    resultado: list[dict] = []
    for i, item in enumerate(items):
        if i < len(libres):
            x, y = libres[i]
            nuevo = copy.deepcopy(item)
            nuevo["x"] = x
            nuevo["y"] = y
            resultado.append(nuevo)
            ocupadas.add((x, y))
        # else: no queda hueco → el item se pierde (caso extremo, no debería ocurrir)
    return resultado


# ── Generación de variante ─────────────────────────────────────────────────


def _filtra_puertas(
    puertas: list[dict],
    tablero: dict,
    salas_usadas: set[int],
) -> list[dict]:
    """Conserva solo las puertas cuyos dos extremos quedan en zona jugable
    (pasillo o sala usada).  Las que dan a una sala ahora cerrada (roca
    dura) se eliminan."""
    resultado: list[dict] = []
    for p in puertas:
        extremos = [p["de"], p["a"]] if "de" in p else [[p["x"], p["y"]]]
        valida = True
        for x, y in extremos:
            sala = _sala_de_casilla(tablero, x, y)
            if sala is not None and sala not in salas_usadas:
                valida = False
                break
            if [x, y] in tablero.get("no_jugables", []):
                valida = False
                break
        if valida:
            resultado.append(p)
    return resultado


def _filtra_mision(
    mision: dict, tablero: dict, salas_usadas: set[int]
) -> dict:
    """Elimina de la misión los elementos que quedan en roca dura."""
    copia = copy.deepcopy(mision)
    copia["puertas"] = _filtra_puertas(
        mision.get("puertas", []), tablero, salas_usadas
    )
    copia["puertas_secretas"] = _filtra_puertas(
        mision.get("puertas_secretas", []), tablero, salas_usadas
    )
    return copia


def _celda_es_jugable(tablero: dict, x: int, y: int) -> bool:
    """True si (x, y) está dentro del tablero y no es roca dura física."""
    if not (1 <= x <= tablero["columnas"] and 1 <= y <= tablero["filas"]):
        return False
    return [x, y] not in tablero.get("no_jugables", [])


def _derivar_puerta_sala(
    tablero: dict,
    num_sala: int,
    salas_usadas: set[int],
) -> list[list[int]] | None:
    """Busca el primer acceso del borde del rect de la sala hacia una zona
    jugable: pasillo puro o una sala abierta vecina.

    Devuelve [desde, hasta] (ambas celdas adyacentes: una dentro de la
    sala y otra en pasillo/sala abierta) o None si no hay acceso."""
    br = next(s for s in tablero["salas"] if s["numero"] == num_sala)
    zonas: dict[tuple[int, int], tuple[int, int]] = {}
    for rect in br["rects"]:
        x0, y0 = rect["x"], rect["y"]
        x1, y1 = x0 + rect["ancho"] - 1, y0 + rect["alto"] - 1
        # Celdas del borde del rect y su vecino exterior ortogonal
        for x in range(x0, x1 + 1):
            for y in (y0, y1):
                for vx, vy in ((x, y - 1), (x, y + 1)):
                    if _celda_es_jugable(tablero, vx, vy):
                        zonas[(vx, vy)] = (x, y)
        for y in range(y0, y1 + 1):
            for x in (x0, x1):
                for vx, vy in ((x - 1, y), (x + 1, y)):
                    if _celda_es_jugable(tablero, vx, vy):
                        zonas[(vx, vy)] = (x, y)
    for vecina, interior in zonas.items():
        sala_vec = _sala_de_casilla(tablero, vecina[0], vecina[1])
        if sala_vec is None or sala_vec in salas_usadas:
            return [list(vecina), list(interior)]
    return None


def _mision_conexa(
    mision: dict,
    tablero: dict,
    salas_usadas: set[int],
) -> bool:
    """BFS desde la entrada de héroes: comprueba que toda sala usada y la
    salida son alcanzables atravesando pasillos, salas abiertas y puertas.
    Las salas no usadas se tratan como roca dura (inaccesibles)."""
    from collections import deque

    celdas_sala = {
        n: _celdas_sala(board_rooms_n(n, tablero)) for n in salas_usadas
    }
    jugable = {
        (x, y)
        for y in range(1, tablero["filas"] + 1)
        for x in range(1, tablero["columnas"] + 1)
        if _celda_es_jugable(tablero, x, y)
    } - _celdas_de_salas_no_usadas(tablero, salas_usadas)

    inicio = next(
        ((e["x"], e["y"]) for e in mision.get("entrada_heroes", [])), None
    )
    if inicio is None:
        return False

    # Las puertas conectan sus dos extremos (son transitables).
    puentes: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for p in mision.get("puertas", []) + mision.get("puertas_secretas", []):
        if "de" in p:
            puentes.add((tuple(p["de"]), tuple(p["a"])))

    alcanzables: set[tuple[int, int]] = set()
    cola = deque([inicio])
    alcanzables.add(inicio)
    while cola:
        x, y = cola.popleft()
        vecinos = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        for v in vecinos:
            if v in jugable and v not in alcanzables:
                alcanzables.add(v)
                cola.append(v)
            # Atravesar puertas: aunque un extremo esté en roca dura no
            # debería ocurrir (las puertas ya se filtraron).
            if ( (x, y), v ) in puentes or ( v, (x, y) ) in puentes:
                if v not in alcanzables:
                    alcanzables.add(v)
                    cola.append(v)

    # Comprobar: todas las salas usadas deben tener alguna celda alcanzable
    for n, celdas in celdas_sala.items():
        if not celdas & alcanzables:
            return False

    # La salida debe ser alcanzable
    salida = mision.get("salida_heroes", {})
    if isinstance(salida, dict) and "de" in salida:
        if tuple(salida["de"]) not in alcanzables:
            return False
    elif isinstance(salida, list):
        for s in salida:
            if isinstance(s, dict) and "de" in s:
                if tuple(s["de"]) not in alcanzables:
                    return False

    return True


def board_rooms_n(n: int, tablero: dict) -> dict:
    return next(s for s in tablero["salas"] if s["numero"] == n)


def _celdas_de_salas_no_usadas(
    tablero: dict, salas_usadas: set[int]
) -> set[tuple[int, int]]:
    """Celdas de las salas del tablero que NO se usan en la variante:
    son roca dura a efectos de accesibilidad."""
    return {
        c
        for s in tablero["salas"]
        if s["numero"] not in salas_usadas
        for c in _celdas_sala(s)
    }


def generar_variante(
    mision: dict,
    tablero: dict,
    semilla: int,
    salas: list[int] | None = None,
    salas_aleatorias: bool = False,
) -> dict:
    """Devuelve una copia alterada de *mision* con la *semilla* dada.

    *salas* (opcional) fija los números de sala físicos que se usarán.
    *salas_aleatorias* elige al azar (con la semilla) qué salas quedan
    abiertas y cuáles de roca dura.  Sin ninguno de los dos, se usan las
    mismas salas que la misión original y solo se permuta el contenido."""
    rng = random.Random(semilla)
    salas_originales = [s["numero"] for s in mision["salas"]]
    esenciales = _salas_esenciales(mision, tablero)

    for intento in range(60):
        variante = copy.deepcopy(mision)

        variante["nombre"] = f"{mision['nombre']} (Variante #{semilla})"
        variante["variante_de"] = mision["nombre"]
        variante["semilla"] = semilla
        variante["alterada"] = True

        # ── 0. Elegir salas físicas de destino ─────────────────────────
        if salas_aleatorias:
            salas_destino = _escoger_salas(
                tablero, len(salas_originales), None, esenciales, rng
            )
        else:
            salas_destino = _escoger_salas(
                tablero, len(salas_originales), salas, esenciales, rng
            )
            if salas is None:
                salas_destino = list(salas_originales)
        salas_usadas = set(salas_destino)
        variante["salas_usadas"] = salas_destino

        # ── 1. Si cambia el conjunto de salas, filtrar puertas/secretas ──
        # que dan a roca dura antes de calcular las celdas prohibidas.
        if set(salas_originales) != salas_usadas:
            variante = _filtra_mision(variante, tablero, salas_usadas)
            # Garantizar una puerta de acceso para cada sala sin ella.
            con_puerta: set[int] = set()
            for p in variante.get("puertas", []):
                for x, y in (
                    [p["de"], p["a"]]
                    if "de" in p
                    else [[p["x"], p["y"]]]
                ):
                    s = _sala_de_casilla(tablero, x, y)
                    if s is not None:
                        con_puerta.add(s)
            for p in variante.get("puertas_secretas", []):
                for x, y in ([p["de"], p["a"]] if "de" in p else [[p["x"], p["y"]]]):
                    s = _sala_de_casilla(tablero, x, y)
                    if s is not None:
                        con_puerta.add(s)
            puertas_nuevas = []
            for s in salas_destino:
                if s in con_puerta:
                    continue
                acceso = _derivar_puerta_sala(tablero, s, salas_usadas)
                if acceso is not None:
                    puertas_nuevas.append(
                        {
                            "de": acceso[0],
                            "a": acceso[1],
                            "descripcion": "Acceso derivado para la variante",
                            "estado": "cerrada",
                        }
                    )
            variante["puertas"] = variante.get("puertas", []) + puertas_nuevas

        # ── 2. Conectividad: si el montaje deja salas inaccesibles, ─────
        # descartar este intento (solo aplica a --salas-aleatorias).
        if salas_aleatorias and set(salas_originales) != salas_usadas:
            if not _mision_conexa(variante, tablero, salas_usadas):
                continue

        # Celdas que ningún elemento puede pisar (puertas, entrada, salida…)
        prohibidas = _celdas_prohibidas(variante)

        # Lookup rápido: número de sala → datos del tablero
        board_rooms = {s["numero"]: s for s in tablero["salas"]}

        # ── 3. Permutar contenido de salas ──────────────────────────────
        # El contenido se baraja y luego se empareja con las salas de
        # destino por demanda (best-fit): el contenido más grande va a la
        # sala más pequeña que pueda albergarlo.  Si no hay emparejamiento
        # posible, el intento se descarta.
        contenidos = [copy.deepcopy(s) for s in mision["salas"]]
        rng.shuffle(contenidos)

        emparejamiento = _emparejar_contenidos(
            contenidos, salas_destino, tablero, prohibidas
        )
        if emparejamiento is None:
            continue

        nuevas_salas: list[dict] = []
        for i, room_original in enumerate(mision["salas"]):
            num = emparejamiento[i]  # sala física del tablero
            src = contenidos[i]  # contenido desplazado
            board_room = board_rooms[num]
            celdas = _celdas_sala(board_room)
            ocupadas: set[tuple[int, int]] = set()

            nuevos_muebles = _colocar_mobiliario(
                src.get("muebles", []), board_room, ocupadas, rng, prohibidas
            )
            nuevos_monstruos = _colocar_items(
                src.get("monstruos", []), celdas, ocupadas, rng, prohibidas
            )
            nuevos_tesoros = _colocar_items(
                src.get("tesoros", []), celdas, ocupadas, rng, prohibidas
            )
            nuevas_trampas = _colocar_items(
                src.get("trampas", []), celdas, ocupadas, rng, prohibidas
            )
            nuevos_marcadores = _colocar_items(
                src.get("marcadores", []), celdas, ocupadas, rng, prohibidas
            )

            sala: dict = {
                "numero": num,
                "nombre": src["nombre"],
                "descripcion": src.get("descripcion", ""),
                "monstruos": nuevos_monstruos,
                "tesoros": nuevos_tesoros,
                "trampas": nuevas_trampas,
                "marcadores": nuevos_marcadores,
            }
            if nuevos_muebles:
                sala["muebles"] = nuevos_muebles
            if src.get("notas"):
                sala["notas"] = src["notas"]
            nuevas_salas.append(sala)

        variante["salas"] = nuevas_salas

        # ── 4. Reubicar elementos de pasillo ────────────────────────────
        celdas_pasillo = {
            (x, y)
            for y in range(1, tablero["filas"] + 1)
            for x in range(1, tablero["columnas"] + 1)
            if _es_pasillo(tablero, x, y)
        }

        # Excluir celdas ocupadas por puertas / entrada / salida
        # (prohibidas ya incluye puertas, secretas, entrada y salida).
        libres_pasillo = list(celdas_pasillo - prohibidas)
        rng.shuffle(libres_pasillo)

        idx = 0
        nuevos_p_monstruos: list[dict] = []
        for m in mision.get("pasillos", {}).get("monstruos", []):
            if idx < len(libres_pasillo):
                x, y = libres_pasillo[idx]
                idx += 1
                n = copy.deepcopy(m)
                n["x"], n["y"] = x, y
                nuevos_p_monstruos.append(n)
            else:
                nuevos_p_monstruos.append(copy.deepcopy(m))

        nuevos_p_trampas: list[dict] = []
        for t in mision.get("pasillos", {}).get("trampas", []):
            if idx < len(libres_pasillo):
                x, y = libres_pasillo[idx]
                idx += 1
                n = copy.deepcopy(t)
                n["x"], n["y"] = x, y
                nuevos_p_trampas.append(n)
            else:
                nuevos_p_trampas.append(copy.deepcopy(t))

        variante["pasillos"] = {
            "monstruos": nuevos_p_monstruos,
            "tesoros": [],
            "trampas": nuevos_p_trampas,
            "marcadores": [],
        }

        # ── 5. Preservación: ningún elemento debe perderse. Si algún item
        # no cupo en la sala asignada, descartar el intento y reintentar.
        if not _contenido_ok(mision, variante):
            continue

        return variante

    raise RuntimeError(
        f"No se encontró una disposición conexa en 60 intentos "
        f"(semilla {semilla})."
    )


# ── Validación ─────────────────────────────────────────────────────────────


def _contenido_ok(original: dict, variante: dict) -> bool:
    """True si la variante conserva la misma cantidad de elementos que la
    misión original (monstruos, tesoros, trampas, marcadores y muebles)."""
    def _contar(m: dict):
        tot = {"monstruos": 0, "tesoros": 0, "trampas": 0, "marcadores": 0,
               "muebles": 0}
        for sala in m.get("salas", []):
            tot["monstruos"] += len(sala.get("monstruos", []))
            tot["tesoros"] += len(sala.get("tesoros", []))
            tot["trampas"] += len(sala.get("trampas", []))
            tot["marcadores"] += len(sala.get("marcadores", []))
            tot["muebles"] += len(sala.get("muebles", []))
        pas = m.get("pasillos", {})
        for k in ("monstruos", "tesoros", "trampas", "marcadores"):
            tot[k] += len(pas.get(k, []))
        return tot

    return _contar(original) == _contar(variante)


def validar_variante(variante: dict, tablero: dict) -> list[str]:
    errs: list[str] = []
    col_max = tablero["columnas"]
    fil_max = tablero["filas"]
    no_jug = {tuple(c) for c in tablero.get("no_jugables", [])}
    prohibidas = _celdas_prohibidas(variante)

    def _en_tablero(x: int, y: int) -> bool:
        return 1 <= x <= col_max and 1 <= y <= fil_max

    # Entrada héroes
    for e in variante.get("entrada_heroes", []):
        x, y = e.get("x"), e.get("y")
        if not _en_tablero(x, y):
            errs.append(f"entrada_heroes: ({x},{y}) fuera del tablero")
        elif (x, y) in no_jug:
            errs.append(f"entrada_heroes: ({x},{y}) en roca dura")

    # Salas
    for sala in variante.get("salas", []):
        num = sala["numero"]
        br = next((s for s in tablero["salas"] if s["numero"] == num), None)
        if br is None:
            errs.append(f"sala {num}: no existe en el tablero")
            continue
        celdas = _celdas_sala(br)
        ocupadas_local: dict[tuple[int, int], str] = {}

        # Muebles primero: reservan su huella completa
        for mueble in sala.get("muebles", []):
            desde, hasta = mueble.get("desde"), mueble.get("hasta")
            if not (isinstance(desde, list) and isinstance(hasta, list)):
                errs.append(
                    f"sala {num}.mueble '{mueble.get('nombre')}': "
                    "formato 'desde'/'hasta' inválido"
                )
                continue
            huella = {
                (x, y)
                for x in range(desde[0], hasta[0] + 1)
                for y in range(desde[1], hasta[1] + 1)
            }
            for pt in (desde, hasta):
                x, y = pt[0], pt[1]
                if (x, y) not in celdas:
                    errs.append(
                        f"sala {num}.mueble '{mueble.get('nombre')}': "
                        f"({x},{y}) fuera de la sala {num}"
                    )
            for c in huella:
                if c in prohibidas:
                    errs.append(
                        f"sala {num}.mueble '{mueble.get('nombre')}': "
                        f"pisa casilla prohibida {c} (puerta/entrada/salida)"
                    )
                if c in ocupadas_local:
                    errs.append(
                        f"sala {num}: solape de mueble '{mueble.get('nombre')}' "
                        f"con {ocupadas_local[c]} en {c}"
                    )
            for c in huella:
                ocupadas_local[c] = f"mueble '{mueble.get('nombre')}'"

        for tipo in ("monstruos", "tesoros", "trampas", "marcadores"):
            for item in sala.get(tipo, []):
                x, y = item.get("x"), item.get("y")
                c = (x, y)
                if not _en_tablero(x, y):
                    errs.append(
                        f"sala {num}.{tipo} '{item.get('nombre')}': "
                        f"({x},{y}) fuera del tablero"
                    )
                elif c not in celdas:
                    errs.append(
                        f"sala {num}.{tipo} '{item.get('nombre')}': "
                        f"({x},{y}) fuera de la sala {num}"
                    )
                if c in prohibidas:
                    errs.append(
                        f"sala {num}.{tipo} '{item.get('nombre')}': "
                        f"pisa casilla prohibida {c} (puerta/entrada/salida)"
                    )
                if c in ocupadas_local:
                    errs.append(
                        f"sala {num}: solape de {tipo[:-1]} "
                        f"'{item.get('nombre')}' con {ocupadas_local[c]} en {c}"
                    )
                ocupadas_local[c] = f"{tipo[:-1]} '{item.get('nombre')}'"

    # Pasillos
    ocupadas_pasillo: dict[tuple[int, int], str] = {}
    for tipo in ("monstruos", "trampas", "tesoros", "marcadores"):
        for item in variante.get("pasillos", {}).get(tipo, []):
            x, y = item.get("x"), item.get("y")
            c = (x, y)
            if not _en_tablero(x, y):
                errs.append(
                    f"pasillos.{tipo} '{item.get('nombre')}': "
                    f"({x},{y}) fuera del tablero"
                )
            elif not _es_pasillo(tablero, x, y):
                errs.append(
                    f"pasillos.{tipo} '{item.get('nombre')}': "
                    f"({x},{y}) no es pasillo"
                )
            if c in prohibidas:
                errs.append(
                    f"pasillos.{tipo} '{item.get('nombre')}': "
                    f"pisa casilla prohibida {c} (puerta/entrada/salida)"
                )
            if c in ocupadas_pasillo:
                errs.append(
                    f"pasillo: solape de {tipo[:-1]} '{item.get('nombre')}' "
                    f"con {ocupadas_pasillo[c]} en {c}"
                )
            ocupadas_pasillo[c] = f"{tipo[:-1]} '{item.get('nombre')}'"

    return errs


# ── CLI ────────────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Genera una variante alterada de una misión existente",
    )
    p.add_argument("--mision", required=True, help="Nombre exacto de la misión")
    p.add_argument(
        "--semilla",
        type=int,
        required=True,
        help="Semilla aleatoria (misma semilla = misma variante)",
    )
    p.add_argument(
        "--guardar",
        action="store_true",
        help="Añade la variante a misiones.json (sin esto solo imprime el JSON)",
    )
    p.add_argument(
        "--salas",
        type=str,
        default=None,
        help="Números de sala físicos a usar (separados por coma). "
        "Las demás salas del tablero quedan como roca dura. "
        "Las salas de entrada/salida de héroes se conservan siempre.",
    )
    p.add_argument(
        "--salas-aleatorias",
        action="store_true",
        help="Elige al azar (con la semilla) qué salas quedan abiertas. "
        "Las demás salas del tablero son roca dura.",
    )
    args = p.parse_args()

    misiones = _cargar("misiones")
    mision = next((m for m in misiones if m["nombre"] == args.mision), None)
    if mision is None:
        print(f"Error: misión '{args.mision}' no encontrada.", file=sys.stderr)
        print("Misiones disponibles:", file=sys.stderr)
        for m in misiones:
            print(f"  • {m['nombre']}", file=sys.stderr)
        sys.exit(1)

    tableros = _cargar("tableros")
    tablero = next((t for t in tableros if t["id"] == mision["tablero"]), None)
    if tablero is None:
        print(f"Error: tablero '{mision['tablero']}' no encontrado.", file=sys.stderr)
        sys.exit(1)

    salas_lista: list[int] | None = None
    if args.salas:
        try:
            salas_lista = [
                int(x.strip())
                for x in args.salas.split(",")
                if x.strip()
            ]
        except ValueError:
            print("Error: --salas debe ser una lista de números, p. ej. '3,4,8'.", file=sys.stderr)
            sys.exit(1)
        numeros_tablero = {s["numero"] for s in tablero["salas"]}
        invalidas = [n for n in salas_lista if n not in numeros_tablero]
        if invalidas:
            print(
                f"Error: las salas {invalidas} no existen en el tablero "
                f"'{mision['tablero']}'. Salas: {sorted(numeros_tablero)}",
                file=sys.stderr,
            )
            sys.exit(1)

    variante = generar_variante(
        mision,
        tablero,
        args.semilla,
        salas=salas_lista,
        salas_aleatorias=args.salas_aleatorias,
    )

    errores = validar_variante(variante, tablero)
    if errores:
        print("✗ Errores de validación:", file=sys.stderr)
        for e in errores:
            print(f"  • {e}", file=sys.stderr)
        sys.exit(1)

    # Resumen de la alteración (solo a stderr)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  Variante #{args.semilla} de: {mision['nombre']}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print("  Mapeo de salas (contenido → sala física):", file=sys.stderr)
    for orig, nueva in zip(mision["salas"], variante["salas"]):
        marcardor = " *" if orig["numero"] != nueva["numero"] else ""
        print(
            f"    Sala {orig['numero']:>2} {orig['nombre'][:25]:<25}"
            f"  →  Sala {nueva['numero']:>2} {nueva['nombre'][:25]}{marcardor}",
            file=sys.stderr,
        )
    print(f"\n  * = el contenido cambió de sala física", file=sys.stderr)

    n_mon = sum(len(s.get("monstruos", [])) for s in variante["salas"])
    n_tes = sum(len(s.get("tesoros", [])) for s in variante["salas"])
    n_trp = sum(len(s.get("trampas", [])) for s in variante["salas"])
    n_mue = sum(len(s.get("muebles", [])) for s in variante["salas"])
    p_mon = len(variante.get("pasillos", {}).get("monstruos", []))
    p_trp = len(variante.get("pasillos", {}).get("trampas", []))
    print(
        f"  Totales: {n_mon} monstruos, {n_tes} tesoros, "
        f"{n_trp} trampas (sala) + {p_mon} mon/pasillo + {p_trp} trp/pasillo, "
        f"{n_mue} muebles",
        file=sys.stderr,
    )
    print(f"{'='*60}\n", file=sys.stderr)

    if args.guardar:
        misiones.append(variante)
        _guardar("misiones", misiones)
        print(
            f"✓ Variante guardada: {variante['nombre']}",
            file=sys.stderr,
        )
    else:
        # JSON a stdout para pipe / inspección
        json.dump(variante, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()

"""Registro central de los tipos de carta de HeroQuest.

Reúne todas las definiciones y ofrece dos búsquedas:
- `obtener(id)`: por identificador de CLI ('arma', 'monstruo', ...).
- `tipo_de_entrada(fichero, entrada)`: dado un JSON ya guardado, deduce su tipo
  (necesario para renderizar cartas existentes).
"""

from __future__ import annotations

from .base import TipoCarta
from .equipo import ARMA, ARMADURA, POCION
from .hechizo import HECHIZO
from .monstruo import MONSTRUO
from .personaje import PERSONAJE

_TIPOS: list[TipoCarta] = [PERSONAJE, MONSTRUO, ARMA, ARMADURA, POCION, HECHIZO]

TIPOS: dict[str, TipoCarta] = {t.id: t for t in _TIPOS}


def obtener(tipo_id: str) -> TipoCarta | None:
    """Devuelve el tipo de carta por su identificador de CLI, o None."""
    return TIPOS.get(tipo_id)


def tipo_de_entrada(fichero: str, entrada: dict) -> TipoCarta | None:
    """Deduce el tipo de una entrada JSON ya existente.

    Para ficheros con un único tipo (personajes, monstruos, hechizos) basta la
    identidad del fichero. Para `armas.json`, que mezcla arma/armadura/poción,
    se usa el campo discriminador `tipo`; cualquier valor "Arma ..." es un arma.
    """
    candidatos = [t for t in _TIPOS if t.fichero == fichero]
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]

    # Fichero compartido: discriminar por el campo `tipo` de la entrada.
    valor = str(entrada.get("tipo", ""))
    for t in candidatos:
        if t.valor_discriminador and valor == t.valor_discriminador:
            return t
    # Cualquier "Arma ..." (cuerpo a cuerpo, a distancia) es un arma.
    if valor.lower().startswith("arma"):
        return ARMA
    return candidatos[0]

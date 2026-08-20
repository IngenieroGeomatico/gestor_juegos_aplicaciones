"""Tipo de carta: personaje (héroe jugable)."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Campo, TipoCarta


@dataclass(frozen=True)
class Personaje(TipoCarta):
    def campos(self) -> list[Campo]:
        return [
            Campo("nombre", "Nombre del héroe"),
            Campo("clase", "Clase (Bárbaro, Mago, Ranger, ...)"),
            Campo("ataque", "Dados de ataque", tipo=int),
            Campo("defensa", "Dados de defensa", tipo=int),
            Campo("cuerpo", "Puntos de cuerpo", tipo=int),
            Campo("mente", "Puntos de mente", tipo=int),
            Campo("movimiento", "Casillas de movimiento", tipo=int, requerido=False, default=2),
            Campo("descripcion", "Descripción opcional", requerido=False, default=""),
        ]

    def stats(self, entrada: dict) -> list[tuple[str, str]]:
        return [
            ("Ataque", str(entrada.get("ataque", 0))),
            ("Defensa", str(entrada.get("defensa", 0))),
            ("Cuerpo", str(entrada.get("cuerpo", 0))),
            ("Mente", str(entrada.get("mente", 0))),
            ("Mov", str(entrada.get("movimiento", 0))),
        ]

    def subtitulo(self, entrada: dict) -> str:
        return f"Héroe · {entrada.get('clase', '')}"


PERSONAJE = Personaje(
    id="personaje",
    fichero="personajes",
    singular="Héroe",
    familia="stats",
    reverso_img="heroe_back.jpg",
    color="#9c2b2b",
    simbolo="⚔",
    descripcion_en_reverso=True,
)

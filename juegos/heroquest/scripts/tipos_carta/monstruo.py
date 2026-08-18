"""Tipo de carta: monstruo (enemigo)."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Campo, TipoCarta


@dataclass(frozen=True)
class Monstruo(TipoCarta):
    def campos(self) -> list[Campo]:
        return [
            Campo("nombre", "Nombre del monstruo"),
            Campo("ataque", "Dados de ataque", tipo=int),
            Campo("defensa", "Dados de defensa", tipo=int),
            Campo("cuerpo", "Puntos de cuerpo", tipo=int),
            Campo("mente", "Puntos de mente", tipo=int),
            Campo("movimiento", "Casillas de movimiento", tipo=int, requerido=False, default=2),
            Campo("descripcion", "Descripción opcional", requerido=False, default=""),
        ]

    def stats(self, entrada: dict) -> list[tuple[str, str]]:
        return [
            ("Mov", str(entrada.get("movimiento", 0))),
            ("Ataque", str(entrada.get("ataque", 0))),
            ("Defensa", str(entrada.get("defensa", 0))),
            ("Cuerpo", str(entrada.get("cuerpo", 0))),
            ("Mente", str(entrada.get("mente", 0))),
        ]

    def subtitulo(self, entrada: dict) -> str:
        return "Monstruo"


MONSTRUO = Monstruo(
    id="monstruo",
    fichero="monstruos",
    singular="Monstruo",
    familia="stats",
    reverso_img="enemigo_back.jpg",
    color="#1f1f1f",
    simbolo="☠",
)

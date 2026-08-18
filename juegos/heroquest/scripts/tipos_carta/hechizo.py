"""Tipo de carta: hechizo (conjuro de magia)."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Campo, TipoCarta


@dataclass(frozen=True)
class Hechizo(TipoCarta):
    def campos(self) -> list[Campo]:
        return [
            Campo("nombre", "Nombre del hechizo"),
            Campo("escuela", "Escuela (Mago o Hechicero)"),
            Campo("coste_mente", "Coste en puntos de mente", tipo=int),
            Campo("descripcion", "Descripción del efecto", requerido=False, default=""),
        ]

    def stats(self, entrada: dict) -> list[tuple[str, str]]:
        return [("Mente", str(entrada.get("coste_mente", 0)))]

    def subtitulo(self, entrada: dict) -> str:
        return f"Hechizo de {entrada.get('escuela', '')}"


HECHIZO = Hechizo(
    id="hechizo",
    fichero="hechizos",
    singular="Hechizo",
    familia="descripcion",
    reverso_img="magia_fuego_back.jpg",
    color="#6a3d8a",
    simbolo="✦",
)

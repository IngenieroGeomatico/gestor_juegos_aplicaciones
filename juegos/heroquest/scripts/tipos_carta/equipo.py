"""Tipos de carta de equipo que comparten armas.json: arma, armadura y poción.

Los tres viven en `armas.json` y se distinguen por el campo `tipo`
(discriminador). Comparten los campos base (nombre, coste, descripción) pero
fijan valores distintos y muestran estadísticas distintas.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Campo, TipoCarta


@dataclass(frozen=True)
class Arma(TipoCarta):
    def campos(self) -> list[Campo]:
        return [
            Campo("nombre", "Nombre del arma"),
            Campo("ataque", "Dados de ataque que otorga", tipo=int, requerido=False, default=0),
            Campo("defensa", "Dados de defensa que otorga", tipo=int, requerido=False, default=0),
            Campo("coste", "Coste en monedas de oro", tipo=int),
            Campo("descripcion", "Descripción opcional", requerido=False, default=""),
        ]

    def construir_entrada(self, args: dict) -> dict:
        return {
            "nombre": args.get("nombre"),
            "tipo": self.valor_discriminador,
            "ataque": args.get("ataque") or 0,
            "defensa": args.get("defensa") or 0,
            "coste": args.get("coste"),
            "descripcion": args.get("descripcion") or "",
        }

    def stats(self, entrada: dict) -> list[tuple[str, str]]:
        pares: list[tuple[str, str]] = []
        if entrada.get("ataque"):
            pares.append(("Ataque", str(entrada["ataque"])))
        if entrada.get("defensa"):
            pares.append(("Defensa", str(entrada["defensa"])))
        pares.append(("Coste", str(entrada.get("coste", 0))))
        return pares

    def subtitulo(self, entrada: dict) -> str:
        return str(entrada.get("tipo", self.singular))


@dataclass(frozen=True)
class Armadura(Arma):
    def campos(self) -> list[Campo]:
        return [
            Campo("nombre", "Nombre de la armadura"),
            Campo("defensa", "Dados de defensa que otorga", tipo=int, requerido=False, default=0),
            Campo("coste", "Coste en monedas de oro", tipo=int),
            Campo("descripcion", "Descripción opcional", requerido=False, default=""),
        ]

    def construir_entrada(self, args: dict) -> dict:
        return {
            "nombre": args.get("nombre"),
            "tipo": self.valor_discriminador,
            "ataque": 0,
            "defensa": args.get("defensa") or 0,
            "coste": args.get("coste"),
            "descripcion": args.get("descripcion") or "",
        }


@dataclass(frozen=True)
class Pocion(Arma):
    def campos(self) -> list[Campo]:
        return [
            Campo("nombre", "Nombre de la poción"),
            Campo("coste", "Coste en monedas de oro", tipo=int),
            Campo("descripcion", "Descripción opcional", requerido=False, default=""),
        ]

    def construir_entrada(self, args: dict) -> dict:
        return {
            "nombre": args.get("nombre"),
            "tipo": self.valor_discriminador,
            "ataque": 0,
            "defensa": 0,
            "coste": args.get("coste"),
            "descripcion": args.get("descripcion") or "",
        }

    def stats(self, entrada: dict) -> list[tuple[str, str]]:
        return [("Coste", str(entrada.get("coste", 0)))]


ARMA = Arma(
    id="arma",
    fichero="armas",
    singular="Arma",
    familia="descripcion",
    reverso_img="equipo_back.jpg",
    campo_discriminador="tipo",
    valor_discriminador="Arma cuerpo a cuerpo",
    color="#5d4037",
    simbolo="⚔",
)

ARMADURA = Armadura(
    id="armadura",
    fichero="armas",
    singular="Armadura",
    familia="descripcion",
    reverso_img="equipo_back.jpg",
    campo_discriminador="tipo",
    valor_discriminador="Armadura",
    color="#3e5f8a",
    simbolo="🛡",
)

POCION = Pocion(
    id="pocion",
    fichero="armas",
    singular="Poción",
    familia="descripcion",
    reverso_img="tesoro_back.jpg",
    campo_discriminador="tipo",
    valor_discriminador="Poción",
    color="#2e7d32",
    simbolo="⚗",
)

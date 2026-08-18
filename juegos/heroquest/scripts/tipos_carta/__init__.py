"""Definiciones de los tipos de carta de HeroQuest.

Cada tipo de carta (arma, armadura, poción, personaje, monstruo, hechizo) sabe:
- sus campos y estadísticas (`campos`, `stats`),
- cómo validarse (`validar`),
- su descripción (`descripcion`),
- su arte frontal y su imagen de reverso (`arte_svg`, `reverso`).

El registro (`registro.py`) los reúne y permite localizar el tipo tanto por su
`id` como a partir de una entrada JSON ya existente.
"""

from .base import Campo, TipoCarta
from .registro import TIPOS, obtener, tipo_de_entrada

__all__ = ["Campo", "TipoCarta", "TIPOS", "obtener", "tipo_de_entrada"]

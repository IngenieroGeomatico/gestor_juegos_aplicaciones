# -*- coding: utf-8 -*-
"""Tokenización ligera del RAG (solo stdlib).

Normaliza a minúsculas, elimina acentos y parte el texto en tokens
(palabras/IDs) sin *stopwords* ni tokens de una letra. Sin dependencias:
`re`, `unicodedata` y `math` de la biblioteca estándar.
"""

from __future__ import annotations

import re
import unicodedata

# Stopwords básicas en español (las más frecuentes; el resto del filtrado lo
# hace la propia similitud TF-IDF).
_STOPWORDS = frozenset(
    """
    de la el en y a los del se las por un para con no una su al lo como mas
    pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me
    hasta hay donde quien desde todo nos durante todos uno les ni contra otros
    ese eso ante ellos e esto mi antes algunos que unos yo otro otras otra el
    tanto esa estos mucho quienes nada muchos cual poco ella estar estas
    algunas algo nosotros mis tu te ti tus ellas todas esto asi aquel aquella
    aquellos aquellas
    """.split()
)

# Quita los diacríticos (à/á/ä → a) tras el NFD: permite "como" == "cómo".
# El bloque U+0300–U+036F (Combining Diacritical Marks) cubre todos los
# acentos del español (á é í ó ú ü ñ).
_COMBINANDO = re.compile(r"[\u0300-\u036f]")

_TOKEN_REGEX = re.compile(r"[a-z0-9ñ]+")


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos (para igualar variantes acentuadas)."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return _COMBINANDO.sub("", texto)


def tokenizar(texto: str) -> list[str]:
    """Tokeniza: normaliza, quita *stopwords* y tokens de una letra."""
    palabras = _TOKEN_REGEX.findall(normalizar(texto))
    return [p for p in palabras if len(p) > 1 and p not in _STOPWORDS]
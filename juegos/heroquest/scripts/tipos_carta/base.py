"""Abstracción base de los tipos de carta de HeroQuest.

`TipoCarta` es la clase base: cada tipo concreto (arma, monstruo, ...) hereda de
ella y declara sus campos, estadísticas, validación, descripción, arte frontal y
reverso. Es una `dataclass` con métodos: ligera, sin ceremonia, pero permitiendo
que cada tipo "posea" su propia lógica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Carpeta con las fotos originales (para los reversos) y las plantillas.
SOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "sources"
# Carpeta con los reversos ya recortados/enderezados (los genera preparar_reversos.py).
REVERSOS_DIR = SOURCES_DIR / "reversos"

# Familia de maquetación de la carta:
# - "stats": banner de título, arte a color y tabla de estadísticas (personaje, monstruo)
# - "descripcion": título, arte recuadrado y bloque de texto (arma, armadura, poción, hechizo)
Familia = Literal["stats", "descripcion"]


@dataclass(frozen=True)
class Campo:
    """Describe un campo de un tipo de carta para el CLI y la validación."""

    nombre: str
    ayuda: str
    tipo: type = str
    requerido: bool = True
    default: object | None = None


@dataclass(frozen=True)
class TipoCarta:
    """Definición base de un tipo de carta.

    Los tipos concretos heredan y sobrescriben los métodos que necesiten. Los
    atributos declaran su identidad y dónde/cómo se almacena y se dibuja.
    """

    id: str
    """Identificador del tipo en el CLI, p. ej. 'arma'."""

    fichero: str
    """Nombre del JSON en data/ donde vive (sin extensión), p. ej. 'armas'."""

    singular: str
    """Etiqueta legible en singular, p. ej. 'Arma'."""

    familia: Familia
    """Familia de maquetación de la carta ('stats' o 'descripcion')."""

    reverso_img: str
    """Nombre del fichero de reverso en sources/, p. ej. 'equipo_back.jpg'."""

    # Discriminador para los tipos que comparten fichero (armas.json):
    # personaje/monstruo/hechizo dejan estos campos a None (fichero == tipo).
    campo_discriminador: str | None = None
    valor_discriminador: str | None = None

    # Color de acento de la carta (banda/arte), en hex.
    color: str = "#5d4037"
    simbolo: str = "✦"

    def campos(self) -> list[Campo]:
        """Campos que definen la carta (para construir el CLI y validar)."""
        raise NotImplementedError

    def stats(self, entrada: dict) -> list[tuple[str, str]]:
        """Pares (etiqueta, valor) para la tabla de estadísticas."""
        return []

    def descripcion(self, entrada: dict) -> str:
        """Texto descriptivo principal de la carta."""
        return str(entrada.get("descripcion", ""))

    def subtitulo(self, entrada: dict) -> str:
        """Línea bajo el título (tipo/clase/escuela). Vacío si no aplica."""
        return self.singular

    def reverso(self) -> Path:
        """Ruta a la imagen de reverso de la carta.

        Prefiere el reverso ya recortado en sources/reversos/ (PNG); si no se ha
        generado todavía, cae a la foto original de sources/.
        """
        limpio = REVERSOS_DIR / f"{Path(self.reverso_img).stem}.png"
        return limpio if limpio.exists() else SOURCES_DIR / self.reverso_img

    def familia_fondo(self, entrada: dict | None = None) -> str | None:
        """Categoría del fondo temático del reverso según la entrada.

        Devuelve el prefijo del fichero en `sources/arte_fondos/` (`<prefijo>_back.png`).
        None significa "sin especificidad": se usa la categoría genérica del tipo.
        """
        return None

    def valor_campo(self, args: dict, campo: Campo) -> object | None:
        """Valor de un campo: usa el default declarado si el arg viene vacío."""
        valor = args.get(campo.nombre)
        return campo.default if valor is None else valor

    def construir_entrada(self, args: dict) -> dict:
        """Construye la entrada JSON a partir de los argumentos ya parseados.

        Por defecto toma exactamente los campos declarados; los tipos que fijan
        valores implícitos (p. ej. armadura con tipo='Armadura') lo sobrescriben.
        """
        return {campo.nombre: self.valor_campo(args, campo) for campo in self.campos()}

    def validar(self, entrada: dict) -> list[str]:
        """Comprueba campos obligatorios presentes. Devuelve lista de errores."""
        errores: list[str] = []
        for campo in self.campos():
            if campo.requerido and entrada.get(campo.nombre) in (None, ""):
                errores.append(f"El campo '{campo.nombre}' es obligatorio.")
        return errores

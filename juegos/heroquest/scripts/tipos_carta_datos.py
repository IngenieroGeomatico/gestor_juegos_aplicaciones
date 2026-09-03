"""Definición de campos y validación de los tipos de datos de HeroQuest.

Módulo ligero, SOLO datos: describe qué campos tiene cada tipo de carta
(personaje, arma, armadura, poción, monstruo, hechizo), cómo se construye su
entrada JSON y cómo se valida. No sabe nada de renderizado ni de plantillas;
lo consume `nueva_carta.py` para construir su CLI y guardar entradas.

El dibujo de las cartas lo hace el motor guiado por datos `render_personaje.py`
(la receta de la carta vive en el propio JSON de cada personaje).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Campo:
    """Describe un campo de un tipo de carta para el CLI y la validación."""

    nombre: str
    ayuda: str
    tipo: type = str
    requerido: bool = True
    default: object | None = None


@dataclass(frozen=True)
class TipoDatos:
    """Definición de datos de un tipo de carta (sin lógica de render).

    - `id`: identificador de CLI ('arma', 'monstruo', ...).
    - `fichero`: nombre del JSON en data/ (sin extensión), p. ej. 'equipo'.
    - `campos`: lista de campos declarados.
    - `discriminador`: para los tipos que comparten fichero (equipo.json), el
      valor fijo del campo `tipo` que los distingue (None si el fichero es
      exclusivo del tipo).
    """

    id: str
    fichero: str
    campos: list[Campo]
    discriminador: str | None = None
    fijos: dict | None = None
    """Campos con valor fijo que se guardan siempre (p. ej. ataque=0 en armaduras)."""

    def valor_campo(self, args: dict, campo: Campo) -> object | None:
        """Valor de un campo: usa el default declarado si el arg viene vacío."""
        valor = args.get(campo.nombre)
        return campo.default if valor is None else valor

    def construir_entrada(self, args: dict) -> dict:
        """Construye la entrada JSON a partir de los argumentos ya parseados.

        Toma los campos declarados; si el tipo comparte fichero (tiene
        discriminador), añade el campo `tipo` con su valor fijo.
        """
        campos = {campo.nombre: self.valor_campo(args, campo) for campo in self.campos}
        entrada: dict = {"nombre": campos.get("nombre")}
        if self.discriminador is not None:
            entrada["tipo"] = self.discriminador
        if self.fijos:
            entrada.update(self.fijos)
        entrada.update({k: v for k, v in campos.items() if k != "nombre"})
        return entrada

    def validar(self, entrada: dict) -> list[str]:
        """Comprueba campos obligatorios presentes. Devuelve lista de errores."""
        errores: list[str] = []
        for campo in self.campos:
            if campo.requerido and entrada.get(campo.nombre) in (None, ""):
                errores.append(f"El campo '{campo.nombre}' es obligatorio.")
        return errores


# --- Definiciones de cada tipo -------------------------------------------

PERSONAJE = TipoDatos(
    id="personaje",
    fichero="personajes",
    campos=[
        Campo("nombre", "Nombre del héroe"),
        Campo("clase", "Clase (Bárbaro, Mago, Ranger, ...)"),
        Campo("ataque", "Dados de ataque", tipo=int),
        Campo("defensa", "Dados de defensa", tipo=int),
        Campo("cuerpo", "Puntos de cuerpo", tipo=int),
        Campo("mente", "Puntos de mente", tipo=int),
        Campo("movimiento", "Casillas de movimiento", tipo=int, requerido=False, default=2),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)

MONSTRUO = TipoDatos(
    id="monstruo",
    fichero="monstruos",
    campos=[
        Campo("nombre", "Nombre del monstruo"),
        Campo("ataque", "Dados de ataque", tipo=int),
        Campo("defensa", "Dados de defensa", tipo=int),
        Campo("cuerpo", "Puntos de cuerpo", tipo=int),
        Campo("mente", "Puntos de mente", tipo=int),
        Campo("movimiento", "Casillas de movimiento", tipo=int, requerido=False, default=2),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)

ARMA = TipoDatos(
    id="arma",
    fichero="equipo",
    discriminador="Arma cuerpo a cuerpo",
    campos=[
        Campo("nombre", "Nombre del arma"),
        Campo("ataque", "Dados de ataque que otorga", tipo=int, requerido=False, default=0),
        Campo("defensa", "Dados de defensa que otorga", tipo=int, requerido=False, default=0),
        Campo("coste", "Coste en monedas de oro", tipo=int),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)

ARMADURA = TipoDatos(
    id="armadura",
    fichero="equipo",
    discriminador="Armadura",
    fijos={"ataque": 0},
    campos=[
        Campo("nombre", "Nombre de la armadura"),
        Campo("defensa", "Dados de defensa que otorga", tipo=int, requerido=False, default=0),
        Campo("coste", "Coste en monedas de oro", tipo=int),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)

POCION = TipoDatos(
    id="pocion",
    fichero="equipo",
    discriminador="Poción",
    fijos={"ataque": 0, "defensa": 0},
    campos=[
        Campo("nombre", "Nombre de la poción"),
        Campo("coste", "Coste en monedas de oro", tipo=int),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)

HECHIZO = TipoDatos(
    id="hechizo",
    fichero="hechizos",
    campos=[
        Campo("nombre", "Nombre del hechizo"),
        Campo("escuela", "Escuela elemental (Agua, Aire, Fuego, Tierra, Terror)"),
        Campo("coste_mente", "Coste en puntos de mente por carta (0 = gratis)"),
        Campo("coste_aprendido", "Coste en puntos de mente al usarlo aprendido", tipo=int, requerido=False, default=1),
        Campo("descripcion", "Descripción del efecto", requerido=False, default=""),
    ],
)

TESORO = TipoDatos(
    id="tesoro",
    fichero="tesoros",
    campos=[
        Campo("nombre", "Nombre de la carta de tesoro"),
        Campo("subtipo", "Subtipo (Gema, Oro, Joyas, Poción, Peligro, Monstruo, ...)", requerido=False, default=""),
        Campo("coste", "Coste en monedas de oro (precio de venta)", tipo=int, requerido=False, default=0),
        Campo("descripcion", "Descripción del tesoro", requerido=False, default=""),
    ],
)

EQUIPO = TipoDatos(
    id="equipo",
    fichero="equipo",
    campos=[
        Campo("nombre", "Nombre del equipo"),
        Campo("subtipo", "Subtipo (Arma, Armadura, Herramienta, Poción, Bastón, ...)"),
        Campo("ataque", "Dados de ataque que otorga", tipo=int, requerido=False, default=0),
        Campo("defensa", "Dados de defensa que otorga", tipo=int, requerido=False, default=0),
        Campo("coste", "Coste en monedas de oro", tipo=int),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)

ARTEFACTO = TipoDatos(
    id="artefacto",
    fichero="artefactos",
    campos=[
        Campo("nombre", "Nombre del artefacto"),
        Campo("subtipo", "Subtipo (Arma, Armadura, Anillo, Varita, Capa, Bastón, ...)"),
        Campo("ataque", "Dados de ataque que otorga", tipo=int, requerido=False, default=0),
        Campo("defensa", "Dados de defensa que otorga", tipo=int, requerido=False, default=0),
        Campo("coste", "Coste en monedas de oro (precio de venta)", tipo=int, requerido=False, default=0),
        Campo("descripcion", "Descripción opcional", requerido=False, default=""),
    ],
)


_TIPOS: list[TipoDatos] = [PERSONAJE, MONSTRUO, ARMA, ARMADURA, POCION, HECHIZO, TESORO, EQUIPO, ARTEFACTO]

TIPOS: dict[str, TipoDatos] = {t.id: t for t in _TIPOS}


def obtener(tipo_id: str) -> TipoDatos | None:
    """Devuelve el tipo de datos por su identificador de CLI, o None."""
    return TIPOS.get(tipo_id)

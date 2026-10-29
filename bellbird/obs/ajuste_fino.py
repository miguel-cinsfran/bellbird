"""Decisiones y textos del ajuste fino del panel de OBS."""

from bellbird.core.idioma import _


PASO_NORMAL = 10
PASO_GRANDE = 50
PASO_FINO = 1

NADA = "nada"
MOSTRAR = "mostrar"
DESHACER = "deshacer"
CONFIRMADO = "confirmado"
ESPERAR = "esperar"


class EstadoAjuste:
    """Guarda si el ajuste fino sigue en curso y qué vuelo espera."""

    def __init__(self):
        """Crea el estado con el ajuste detenido y sin vuelo."""
        self.en_curso = False
        self.en_vuelo = False
        self.deshacer_pendiente = False
        self.transformacion = None

    def entrar(self, transformacion):
        """Guarda la transformación inicial y marca el ajuste en curso."""
        self.transformacion = transformacion
        self.en_curso = True

    def puede_mover(self) -> bool:
        """Dice si se puede iniciar un movimiento con las flechas."""
        return self.en_curso and not self.en_vuelo

    def empezar_movimiento(self):
        """Marca un movimiento de flecha en vuelo."""
        self.en_vuelo = True

    def aterrizar(self) -> str:
        """Apaga el vuelo y decide qué hacer al aterrizar."""
        self.en_vuelo = False
        if self.deshacer_pendiente:
            return DESHACER
        if not self.en_curso:
            return NADA
        return MOSTRAR

    def salir(self, confirmar) -> str:
        """Cierra el ajuste y decide qué hacer al salir."""
        if not self.en_curso:
            return NADA
        self.en_curso = False
        if confirmar:
            return CONFIRMADO
        if self.en_vuelo:
            # Deshacer mientras una flecha sigue en vuelo manda dos
            # peticiones a la vez por el mismo socket; se espera a que aterrice.
            self.deshacer_pendiente = True
            return ESPERAR
        return DESHACER

    def tomar_para_deshacer(self):
        """Toma la transformación guardada para deshacer el ajuste."""
        self.deshacer_pendiente = False
        return self.transformacion


def resolver(codigo, ctrl, shift) -> tuple:
    """Decide la acción y el desplazamiento para una tecla."""
    if codigo in (13, 370):
        return "confirmar", 0, 0
    if codigo == 27:
        return "cancelar", 0, 0
    if codigo == 9:
        return "salir", 0, 0

    paso = PASO_GRANDE if ctrl else PASO_FINO if shift else PASO_NORMAL
    movimientos = {
        314: (-paso, 0), 316: (paso, 0),
        315: (0, -paso), 317: (0, paso),
    }
    dx, dy = movimientos.get(codigo, (0, 0))
    return ("mover", dx, dy) if codigo in movimientos else ("ignorar", 0, 0)


def etiqueta_boton(activo, etiqueta_base) -> str:
    """Devuelve la etiqueta que corresponde al estado del modo."""
    return "Ajustando, flechas para mover" if activo else etiqueta_base


def texto_de_entrada() -> str:
    """Devuelve el anuncio al entrar en el modo."""
    # Traductores: anuncio al entrar en el ajuste fino; dice qué teclas mueven, confirman y salen.
    return _("Ajuste fino. Flechas para mover, Control para pasos grandes, "
             "Mayúsculas para pasos de un píxel. Intro confirma, Escape deshace, "
             "Tab sale.")

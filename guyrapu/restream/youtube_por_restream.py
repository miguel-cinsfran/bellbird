"""Cómo se manda YouTube a través de Restream.

Puro salvo lo inyectado: la cuenta de Restream y el restaurador entran por
parámetro. La única razón para cambiar de este módulo es el destino manual
que representa el directo de YouTube de la sesión de Google.
"""

from __future__ import annotations

from guyrapu.core.idioma import N_

# El nombre no se traduce nunca: así se reconocen los manuales que dejó un cierre inesperado, en cualquier idioma.
NOMBRE_MANUAL = N_("YouTube de Guyrapu")
PLATAFORMA_MANUAL = 29


def borrar_sobrantes(cuenta_mod, canales):
    """Borra los manuales de Guyrapu que quedaron y devuelve los demás.

    Los borrados no vuelven a la lista: ya no existen para activarlos ni
    desactivarlos al preparar el perfil.
    """
    restantes = []
    for canal in canales or ():
        if getattr(canal, "nombre", "") == NOMBRE_MANUAL:
            cuenta_mod.eliminar_canal(canal.id)
        else:
            restantes.append(canal)
    return restantes


def preparar_destino(cuenta_mod, restaurador):
    """Devuelve el destino para `emision.preparar_en_youtube`.

    Agrega el manual con el servidor y la clave de la emisión, lo deja
    anotado para borrarlo al terminar y lo activa, porque nace desactivado.
    """

    def preparar(cliente_obs, destino, parada=None):
        del cliente_obs, parada
        canal = cuenta_mod.agregar_canal_manual(
            PLATAFORMA_MANUAL, NOMBRE_MANUAL, destino.servidor,
            destino.clave)
        if restaurador is not None:
            restaurador.anotar_manual(canal.id)
        cuenta_mod.activar_canal(canal.id, True)
        return canal.id

    return preparar

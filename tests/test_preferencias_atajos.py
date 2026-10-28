"""Pseudotraducción de la página Atajos de Preferencias.

Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
Comprueba que ningún texto visible propio de la página queda sin pasar
por gettext.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import config
from ytchat.ui import gui, gui_preferencias
from ytchat.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


# Textos que arma otro módulo y esta página solo muestra, con valores de
# fábrica: la nota de `ytchat/ui/atajos_captura.py` (NOTA_PAGINA), los
# títulos de grupo de `ytchat/core/config.py` (ATAJOS_GRUPOS) y las
# etiquetas de los botones no fijos (`etiqueta_de_accion` y
# `etiqueta_boton` de `atajos_captura`). La comparación es exacta en los
# dos sentidos: falla si aparece un texto nuevo sin envolver y si un
# pendiente ya no está en el recorrido, para vaciar la lista cuando esos
# módulos pasen por gettext.
PENDIENTES_ATAJOS = (
    "Cada familia de atajos tiene su modificador: Ctrl para el "
    "reproductor, Alt para el chat, Ctrl+Mayús para abrir ventanas, "
    "Alt+Mayús para el directo y OBS, Ctrl+Alt para la música y las "
    "teclas F para la voz. Pulsa un botón y luego la combinación que "
    "quieras: se comprueba sola que sirva para esa familia y que no "
    "choque con otra. F6, Mayús+F6, F9 a F12 y Alt+F4 son fijas y se "
    "muestran para que no se puedan pisar.",
    "Reproductor (Ctrl)",
    "Chat (Alt)",
    "Ventanas (Ctrl+Mayús)",
    "Directo y OBS (Alt+Mayús)",
    "Voz y lectura (teclas F)",
    "Música (Ctrl+Alt)",
    "Ventana y navegación (fijos)",
    "Mensajes recientes del chat (fijos)",
    "Reproducir o pausa: Ctrl+P",
    "Retroceder 1 minuto: Ctrl+Flecha izquierda",
    "Avanzar 1 minuto: Ctrl+Flecha derecha",
    "Ir al directo: Ctrl+Fin",
    "Detener vídeo: Ctrl+D",
    "Silenciar o activar audio: Ctrl+M",
    "Bajar volumen del reproductor: Ctrl+Flecha abajo",
    "Subir volumen del reproductor: Ctrl+Flecha arriba",
    "Abrir el gestor de descargas: Ctrl+Mayús+D",
    "Pantalla completa: Ctrl+F",
    "Abrir Preferencias: Ctrl+Mayús+P",
    "Abrir el historial de directos: Ctrl+Mayús+H",
    "Marcar incidencia: Alt+Mayús+I",
    "Abrir Transmisión: Ctrl+Mayús+T",
    "Mostrar OBS: Ctrl+Mayús+O",
    "Copiar enlace del directo: Alt+Mayús+E",
    "Silenciar el micrófono de OBS: Alt+Mayús+M",
    "Activar o desactivar los avisos de sobrecarga: Alt+Mayús+A",
    "Conectar: Alt+Mayús+C",
    "Desconectar: Alt+Mayús+D",
    "Enviar mensaje al chat: Alt+Intro",
    "Ir a la lista del panel actual: Alt+Mayús+L",
    "Pausar o reanudar lectura: F5",
    "Detener voz actual: F8",
    "Silenciar lectura TTS: F4",
    "Silenciar sonidos: F7",
    "Anunciar estado: F2",
    "Anunciar autor del último mensaje: F3",
    "Describir la escena de OBS: Ctrl+F2",
    "Consulta rápida a la IA sobre la escena: Ctrl+Mayús+F2",
    "Reproducir o pausar la música: Ctrl+Alt+Espacio",
    "Siguiente canción: Ctrl+Alt+Flecha derecha",
    "Canción anterior: Ctrl+Alt+Flecha izquierda",
    "Subir el volumen de la música: Ctrl+Alt+Flecha arriba",
    "Bajar el volumen de la música: Ctrl+Alt+Flecha abajo",
    "Qué suena: Ctrl+Alt+T",
    "Silenciar o devolver el sonido de la música: Ctrl+Alt+M",
    "Orden aleatorio de la música: Ctrl+Alt+A",
    "Cambiar la repetición de la música: Ctrl+Alt+R",
    "Detener la música: Ctrl+Alt+D",
    "Adelantar la música 10 segundos: Ctrl+Alt+Mayús+Flecha derecha",
    "Retroceder la música 10 segundos: Ctrl+Alt+Mayús+Flecha izquierda",
    "Abrir la ventana de música: Ctrl+Mayús+M",
    "Preguntar a la IA sobre la imagen: Ctrl+Mayús+I",
)


# Wrap parte la nota en varias líneas: se comparan los espacios normalizados.
def _normalizar(texto): return " ".join(texto.split())


class TestAtajosSinTextosSinEnvolver(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pagina(self, dialogo):
        return next(dialogo.nb.GetPage(i)
                    for i in range(dialogo.nb.GetPageCount())
                    if dialogo.nb.GetPage(i).GetName() == "PagAtajos")

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(self._pagina(dialogo))

        self.assertEqual(sorted(map(_normalizar, sin_marcar)),
                         sorted(map(_normalizar, PENDIENTES_ATAJOS)))


if __name__ == "__main__":
    unittest.main()

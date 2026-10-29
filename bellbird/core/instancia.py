"""Asegura que haya una sola instancia de la aplicación."""

from __future__ import annotations

from bellbird.core import paths

# Mutex de Windows para impedir que se abran dos ventanas a la vez. Se usa
# ctypes (en vez de win32event) para no añadir otra dependencia.

_mutex_handle = None

_ERROR_ACCESS_DENIED = 5      # el mutex existe pero es de otro usuario / instancia elevada
_ERROR_ALREADY_EXISTS = 183   # el mutex ya lo tiene otra instancia de este usuario

_NOMBRE_MUTEX = "Bellbird_SingleInstance_Mutex"

_SYNCHRONIZE = 0x00100000
_TOPE_ESPERA_MS = 20000


def orden_reabrir(pid, orden=None):
    """Orden para abrir otra instancia que espere a que termine `pid`.

    Sin `orden` se usa la de la aplicación en curso.
    """
    if orden is None:
        orden = paths.orden_de_la_app()
    return [*orden, "--esperar-pid", str(pid)]


def _pid_a_esperar(argv):
    """El pid de `--esperar-pid N` en la línea de órdenes, o None."""
    argumentos = list(argv or [])
    try:
        posicion = argumentos.index("--esperar-pid")
        return int(argumentos[posicion + 1])
    except (ValueError, IndexError, TypeError):
        return None


def _kernel32():
    """WinDLL de kernel32 con los tipos de las funciones de la espera."""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [
        ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.WaitForSingleObject.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    return kernel32


def esperar_proceso(pid, tope=20.0) -> None:
    """Espera a que termine `pid`, como mucho `tope` segundos."""
    try:
        kernel32 = _kernel32()
        handle = kernel32.OpenProcess(_SYNCHRONIZE, False, int(pid))
        # Si el pid ya no existe, OpenProcess falla y se vuelve enseguida.
        if not handle:
            return
        kernel32.WaitForSingleObject(handle, int(tope * 1000))
        kernel32.CloseHandle(handle)
    except Exception:
        # Fuera de Windows o sin permiso, no se bloquea el arranque.
        return


def hay_otra_instancia(error: int) -> bool:
    """Decide, a partir de GetLastError tras CreateMutexW, si ya hay otra
    instancia. ACCESS_DENIED también cuenta: el mutex existe (lo creó una
    instancia elevada o de otro usuario) aunque no nos dejen abrirlo."""
    return error in (_ERROR_ALREADY_EXISTS, _ERROR_ACCESS_DENIED)


def _esperar_si_hace_falta(argv) -> None:
    """Espera al pid de `--esperar-pid`, si lo hay, antes de tomar el mutex."""
    pid = _pid_a_esperar(argv)
    if pid is not None:
        # La instancia anterior todavía está cerrando y tiene el mutex.
        esperar_proceso(pid, _TOPE_ESPERA_MS / 1000)


def _crear_mutex(nombre):
    """Crea el mutex y devuelve (handle, GetLastError); (None, None) sin Windows."""
    try:
        import ctypes
        # use_last_error + get_last_error: leer GetLastError «a mano» tras una
        # llamada ctypes no es fiable (el propio ctypes puede pisarlo entre medias).
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Sin restype ctypes devuelve un int de 32 bits y trunca el HANDLE en x64.
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, nombre)
        return handle, ctypes.get_last_error()
    except Exception:
        return None, None  # fuera de Windows, dejamos que arranque igualmente


def verificar_instancia_unica(argv=None, nombre: str = _NOMBRE_MUTEX) -> bool:
    global _mutex_handle
    _esperar_si_hace_falta(argv)
    _mutex_handle, error = _crear_mutex(nombre)
    if error is None:
        return True
    return not hay_otra_instancia(error)

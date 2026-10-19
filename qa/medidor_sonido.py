"""Medidor del sonido real que sale por los altavoces, sin hacer sonar nada.

Lee el medidor de pico de Windows (`IAudioMeterInformation`) para las
sesiones de audio de unos procesos dados. Lo usa la escena `musica_real`
de `qa/conducir.py` para comprobar que la música de verdad empieza, se
pausa, sigue y se detiene. Nunca reproduce ni genera sonido: solo mira.

Sin dispositivo de salida o sin sesiones de esos procesos (la sesión puede
no existir hasta el primer sonido), devuelve `None`. Cualquier error de
COM también es `None` y se registra con `logging`, nunca lanza.

Solo funciona en Windows con `comtypes` (ya está en el `.venv`). En otro
sistema el módulo igual se importa, pero `DISPONIBLE` es falso y todo
devuelve `None`.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

try:
    import comtypes
    import comtypes.client
    from comtypes import CLSCTX_ALL, COMMETHOD, GUID, HRESULT, IUnknown
    from ctypes import POINTER, c_float, c_int, c_ulong, c_void_p, c_wchar_p
    _HAY_COM = os.name == "nt"
except Exception:
    _HAY_COM = False

DISPONIBLE = _HAY_COM

if _HAY_COM:
    _CLSID_ENUMERADOR = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")

    class _IAudioMeterInformation(IUnknown):
        _iid_ = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetPeakValue",
                      (["out"], POINTER(c_float), "pico")),
        ]

    class _IAudioSessionControl(IUnknown):
        _iid_ = GUID("{F4B1A599-7266-4319-A8CA-E70ACB11E8CD}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetState",
                      (["out"], POINTER(c_int), "estado")),
            COMMETHOD([], HRESULT, "GetDisplayName",
                      (["out"], POINTER(c_wchar_p), "nombre")),
            COMMETHOD([], HRESULT, "SetDisplayName",
                      (["in"], c_wchar_p, "nombre"),
                      (["in"], POINTER(GUID), "contexto")),
            COMMETHOD([], HRESULT, "GetIconPath",
                      (["out"], POINTER(c_wchar_p), "ruta")),
            COMMETHOD([], HRESULT, "SetIconPath",
                      (["in"], c_wchar_p, "ruta"),
                      (["in"], POINTER(GUID), "contexto")),
            COMMETHOD([], HRESULT, "GetGroupingParam",
                      (["out"], POINTER(GUID), "grupo")),
            COMMETHOD([], HRESULT, "SetGroupingParam",
                      (["in"], GUID, "grupo"),
                      (["in"], GUID, "contexto")),
            COMMETHOD([], HRESULT, "RegisterAudioSessionNotification",
                      (["in"], c_void_p, "aviso")),
            COMMETHOD([], HRESULT, "UnregisterAudioSessionNotification",
                      (["in"], c_void_p, "aviso")),
        ]

    class _IAudioSessionControl2(_IAudioSessionControl):
        _iid_ = GUID("{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6A}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetSessionIdentifier",
                      (["out"], POINTER(c_wchar_p), "identificador")),
            COMMETHOD([], HRESULT, "GetSessionInstanceIdentifier",
                      (["out"], POINTER(c_wchar_p), "identificador")),
            COMMETHOD([], HRESULT, "GetProcessId",
                      (["out"], POINTER(c_ulong), "pid")),
            COMMETHOD([], HRESULT, "IsSystemSoundsSession"),
            COMMETHOD([], HRESULT, "SetDuckingPreferences",
                      (["in"], c_int, "preferencia")),
        ]

    class _IAudioSessionEnumerator(IUnknown):
        _iid_ = GUID("{E2F5BB11-0570-40CA-ACDD-3AA01277DEE8}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount",
                      (["out"], POINTER(c_int), "cantidad")),
            COMMETHOD([], HRESULT, "GetSession",
                      (["in"], c_int, "indice"),
                      (["out"], POINTER(POINTER(_IAudioSessionControl)),
                       "sesion")),
        ]

    class _IAudioSessionManager2(IUnknown):
        # Hereda de `IAudioSessionManager`: sus dos métodos van primero en
        # la tabla, aunque acá nunca se llamen. Ojo: `RegisterSessionNotification`
        # NO es del base, es de esta interfaz (así lo declara pycaw y lo
        # confirma audiopolicy.h): ponerla en el base corre el resto un
        # lugar y `GetSessionEnumerator` termina llamando a otra cosa.
        _iid_ = GUID("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetAudioSessionControl",
                      (["in"], POINTER(GUID), "sesion"),
                      (["in"], c_ulong, "banderas"),
                      (["out"], POINTER(POINTER(_IAudioSessionControl)),
                       "control")),
            COMMETHOD([], HRESULT, "GetSimpleAudioVolume",
                      (["in"], POINTER(GUID), "sesion"),
                      (["in"], c_ulong, "banderas"),
                      (["out"], POINTER(c_void_p), "volumen")),
            COMMETHOD([], HRESULT, "GetSessionEnumerator",
                      (["out"], POINTER(POINTER(_IAudioSessionEnumerator)),
                       "enumerador")),
            COMMETHOD([], HRESULT, "RegisterSessionNotification",
                      (["in"], c_void_p, "aviso")),
            COMMETHOD([], HRESULT, "UnregisterSessionNotification",
                      (["in"], c_void_p, "aviso")),
            COMMETHOD([], HRESULT, "RegisterDuckNotification",
                      (["in"], c_void_p, "origen"),
                      (["in"], c_void_p, "aviso")),
            COMMETHOD([], HRESULT, "UnregisterDuckNotification",
                      (["in"], c_void_p, "aviso")),
        ]

    class _IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Activate",
                      (["in"], POINTER(GUID), "iid"),
                      (["in"], c_ulong, "contexto"),
                      (["in"], c_void_p, "parametros"),
                      (["out"], POINTER(POINTER(_IAudioSessionManager2)),
                       "interfaz")),
            COMMETHOD([], HRESULT, "OpenPropertyStore",
                      (["in"], c_ulong, "acceso"),
                      (["out"], POINTER(c_void_p), "tienda")),
            COMMETHOD([], HRESULT, "GetId",
                      (["out"], POINTER(c_wchar_p), "identificador")),
            COMMETHOD([], HRESULT, "GetState",
                      (["out"], POINTER(c_ulong), "estado")),
        ]

    class _IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints",
                      (["in"], c_int, "flujo"),
                      (["in"], c_ulong, "mascara"),
                      (["out"], POINTER(c_void_p), "dispositivos")),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                      (["in"], c_int, "flujo"),
                      (["in"], c_int, "rol"),
                      (["out"], POINTER(POINTER(_IMMDevice)), "dispositivo")),
            COMMETHOD([], HRESULT, "GetDevice",
                      (["in"], c_wchar_p, "identificador"),
                      (["out"], POINTER(c_void_p), "dispositivo")),
            COMMETHOD([], HRESULT, "RegisterEndpointNotificationCallback",
                      (["in"], c_void_p, "aviso")),
            COMMETHOD([], HRESULT, "UnregisterEndpointNotificationCallback",
                      (["in"], c_void_p, "aviso")),
        ]


def _sesiones() -> list:
    """Pares `(pid, pico)` de cada sesión del dispositivo de salida."""
    comtypes.CoInitialize()
    try:
        enumerador = comtypes.client.CreateObject(
            _CLSID_ENUMERADOR, clsctx=CLSCTX_ALL,
            interface=_IMMDeviceEnumerator)
        # Salida (`eRender`) para multimedia: lo que suena por defecto.
        dispositivo = enumerador.GetDefaultAudioEndpoint(0, 1)
        gestor = dispositivo.Activate(
            _IAudioSessionManager2._iid_, CLSCTX_ALL, None)
        lista = gestor.GetSessionEnumerator()
        cantidad = lista.GetCount()
        pares = []
        for indice in range(cantidad):
            try:
                control = lista.GetSession(indice)
                pid = control.QueryInterface(
                    _IAudioSessionControl2).GetProcessId()
            except Exception:
                continue
            try:
                valor = control.QueryInterface(
                    _IAudioMeterInformation).GetPeakValue()
            except Exception:
                continue
            pares.append((int(pid), float(valor)))
        return pares
    finally:
        comtypes.CoUninitialize()


def pico(pids) -> float | None:
    """El mayor pico entre las sesiones cuyo proceso está en `pids`.

    `None` si no hay dispositivo de salida, ninguna sesión es de esos
    procesos, o COM falla por el motivo que sea. Nunca lanza.
    """
    try:
        objetivos = {int(pid) for pid in (pids or [])}
    except Exception:
        return None
    if not objetivos or not DISPONIBLE:
        return None
    try:
        pares = _sesiones()
    except Exception as exc:
        logger.debug("medidor: sin lectura del sonido: %r", exc)
        return None
    mejor = None
    for pid, valor in pares:
        if pid in objetivos and (mejor is None or valor > mejor):
            mejor = valor
    return mejor


def pico_maximo(pids, segundos: float = 1.5, cada: float = 0.05) -> float | None:
    """El mayor pico durante `segundos`, leyendo cada `cada` segundos.

    `None` si todas las lecturas fueron `None`. Nunca lanza: una lectura
    que falla cuenta como `None` y se sigue con la siguiente.
    """
    objetivos = list(pids or [])
    try:
        tope = time.monotonic() + max(0.0, float(segundos))
    except Exception:
        return None
    try:
        intervalo = float(cada)
    except Exception:
        intervalo = 0.05
    if intervalo <= 0:
        intervalo = 0.01
    mejor = None
    while True:
        try:
            valor = pico(objetivos)
        except Exception:
            valor = None
        if valor is not None and (mejor is None or valor > mejor):
            mejor = valor
        if time.monotonic() >= tope:
            break
        queda = tope - time.monotonic()
        time.sleep(intervalo if queda > intervalo else max(0.0, queda))
    return mejor

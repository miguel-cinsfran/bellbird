"""Nombre del dispositivo de captura predeterminado de Windows.

Usa COM con ctypes puro: comtypes y pycaw no forman parte del paquete.
Cualquier fallo devuelve un texto vacío para que la app anuncie lo de
siempre.
"""

from __future__ import annotations

import ctypes
import uuid
from ctypes import wintypes

from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

COINIT_MULTITHREADED = 0x0
CLSCTX_ALL = 0x17
STGM_READ = 0
VT_LPWSTR = 31
EDATAFLOW_CAPTURE = 1
EROLE_CONSOLE = 0

_VTABLE_RELEASE = 2
_VTABLE_GETDEFAULTENDPOINT = 4
_VTABLE_OPENPROPERTYSTORE = 4
_VTABLE_GETVALUE = 5


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("_datos", ctypes.c_byte * 16),
    ]

    def texto(self) -> str:
        if self.vt != VT_LPWSTR:
            return ""
        puntero = ctypes.cast(
            ctypes.byref(self, PROPVARIANT._datos.offset),
            ctypes.POINTER(ctypes.c_wchar_p))
        return puntero.contents.value or ""


def _guid(texto: str) -> GUID:
    return GUID.from_buffer_copy(uuid.UUID(texto).bytes_le)


CLSID_MMDEVICE_ENUMERATOR = _guid("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDEVICE_ENUMERATOR = _guid("A95664D2-9614-4F35-A746-DE8DB63617E6")
PKEY_DEVICE_FRIENDLY_NAME = PROPERTYKEY(
    _guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)


def _llamar(interfaz, indice, tipos, *argumentos):
    vtable = ctypes.cast(
        interfaz, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototipo = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *tipos)
    funcion = prototipo(vtable[indice])
    return funcion(interfaz, *argumentos)


def _soltar(interfaz) -> None:
    if not interfaz:
        return
    try:
        _llamar(interfaz, _VTABLE_RELEASE, [])
    except Exception as exc:
        logger.debug("No se pudo liberar una interfaz COM: %s", exc)


def microfono_predeterminado() -> str:
    """Nombre amigable del dispositivo de captura predeterminado."""
    try:
        return _leer_predeterminado()
    except Exception as exc:
        logger.debug("No se pudo leer el micrófono predeterminado: %s", exc)
        return ""


def _leer_predeterminado() -> str:
    ole32 = ctypes.WinDLL("ole32")
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
    ole32.PropVariantClear.restype = ctypes.c_long

    resultado = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    if resultado < 0:
        logger.debug("CoInitializeEx falló: %#x", resultado & 0xFFFFFFFF)
        return ""
    try:
        return _nombre_del_predeterminado(ole32)
    finally:
        ole32.CoUninitialize()


def _nombre_del_predeterminado(ole32) -> str:
    enumerador = ctypes.c_void_p()
    resultado = ole32.CoCreateInstance(
        ctypes.byref(CLSID_MMDEVICE_ENUMERATOR), None, CLSCTX_ALL,
        ctypes.byref(IID_IMMDEVICE_ENUMERATOR), ctypes.byref(enumerador))
    if resultado < 0 or not enumerador:
        logger.debug("CoCreateInstance del enumerador falló: %#x",
                     resultado & 0xFFFFFFFF)
        return ""
    try:
        return _nombre_del_enumerador(ole32, enumerador)
    finally:
        _soltar(enumerador)


def _nombre_del_enumerador(ole32, enumerador) -> str:
    dispositivo = ctypes.c_void_p()
    resultado = _llamar(
        enumerador, _VTABLE_GETDEFAULTENDPOINT,
        [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
        EDATAFLOW_CAPTURE, EROLE_CONSOLE, ctypes.byref(dispositivo))
    if resultado < 0 or not dispositivo:
        logger.debug("GetDefaultAudioEndpoint falló: %#x",
                     resultado & 0xFFFFFFFF)
        return ""
    try:
        return _nombre_del_dispositivo(ole32, dispositivo)
    finally:
        _soltar(dispositivo)


def _nombre_del_dispositivo(ole32, dispositivo) -> str:
    almacen = ctypes.c_void_p()
    resultado = _llamar(
        dispositivo, _VTABLE_OPENPROPERTYSTORE,
        [wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)],
        STGM_READ, ctypes.byref(almacen))
    if resultado < 0 or not almacen:
        logger.debug("OpenPropertyStore falló: %#x", resultado & 0xFFFFFFFF)
        return ""
    try:
        return _nombre_del_almacen(ole32, almacen)
    finally:
        _soltar(almacen)


def _nombre_del_almacen(ole32, almacen) -> str:
    valor = PROPVARIANT()
    resultado = _llamar(
        almacen, _VTABLE_GETVALUE,
        [ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT)],
        ctypes.byref(PKEY_DEVICE_FRIENDLY_NAME), ctypes.byref(valor))
    try:
        if resultado < 0:
            logger.debug("GetValue del nombre amigable falló: %#x",
                         resultado & 0xFFFFFFFF)
            return ""
        return valor.texto()
    finally:
        ole32.PropVariantClear(ctypes.byref(valor))

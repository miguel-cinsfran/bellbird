"""Claves de proveedores de IA en el Administrador de credenciales."""

from __future__ import annotations

import ctypes
import os

PREFIJO = "Bellbird/ia/"

_TIPO_GENERICO = 1
_PERSISTENCIA_LOCAL = 2
_NO_ENCONTRADO = 1168
_TOPE_BLOB = 2560


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", ctypes.c_ulong),
        ("CredentialBlob", ctypes.c_void_p),
        ("Persist", ctypes.c_ulong),
        ("AttributeCount", ctypes.c_ulong),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


def _destino(proveedor, prefijo):
    if not isinstance(proveedor, str) or not proveedor \
            or "/" in proveedor:
        raise ValueError("nombre de proveedor no admitido")
    return f"{prefijo}{proveedor}"


def _exigir_windows():
    if os.name != "nt":
        raise OSError("las claves de IA solo se guardan en Windows")


def _advapi32():
    biblioteca = ctypes.WinDLL("advapi32", use_last_error=True)
    biblioteca.CredWriteW.argtypes = (ctypes.POINTER(CREDENTIALW),
                                      ctypes.c_ulong)
    biblioteca.CredWriteW.restype = ctypes.c_bool
    biblioteca.CredReadW.argtypes = (ctypes.c_wchar_p, ctypes.c_ulong,
                                     ctypes.c_ulong,
                                     ctypes.POINTER(
                                         ctypes.POINTER(CREDENTIALW)))
    biblioteca.CredReadW.restype = ctypes.c_bool
    biblioteca.CredDeleteW.argtypes = (ctypes.c_wchar_p, ctypes.c_ulong,
                                       ctypes.c_ulong)
    biblioteca.CredDeleteW.restype = ctypes.c_bool
    biblioteca.CredFree.argtypes = (ctypes.c_void_p,)
    biblioteca.CredFree.restype = None
    return biblioteca


def guardar(proveedor, clave, prefijo=PREFIJO):
    """Crea o reemplaza la clave del proveedor."""
    destino = _destino(proveedor, prefijo)
    if not isinstance(clave, str):
        raise ValueError("la clave no puede quedar vacía")
    limpia = clave.strip()
    if not limpia:
        raise ValueError("la clave no puede quedar vacía")
    datos = limpia.encode("utf-16-le")
    if len(datos) > _TOPE_BLOB:
        raise ValueError("la clave supera el tope de Windows")
    _exigir_windows()
    biblioteca = _advapi32()
    memoria = ctypes.create_string_buffer(datos, len(datos))
    credencial = CREDENTIALW()
    credencial.Flags = 0
    credencial.Type = _TIPO_GENERICO
    credencial.TargetName = destino
    credencial.Comment = ""
    credencial.CredentialBlobSize = len(datos)
    credencial.CredentialBlob = ctypes.addressof(memoria)
    credencial.Persist = _PERSISTENCIA_LOCAL
    credencial.AttributeCount = 0
    credencial.Attributes = None
    credencial.TargetAlias = None
    credencial.UserName = proveedor
    if not biblioteca.CredWriteW(ctypes.byref(credencial), 0):
        codigo = ctypes.get_last_error()
        raise OSError(f"no se pudo guardar la clave, código {codigo}")


def leer(proveedor, prefijo=PREFIJO):
    """Devuelve la clave guardada o None si no hay ninguna."""
    destino = _destino(proveedor, prefijo)
    _exigir_windows()
    biblioteca = _advapi32()
    puntero = ctypes.POINTER(CREDENTIALW)()
    if not biblioteca.CredReadW(destino, _TIPO_GENERICO, 0,
                                 ctypes.byref(puntero)):
        codigo = ctypes.get_last_error()
        if codigo == _NO_ENCONTRADO:
            return None
        raise OSError(f"no se pudo leer la clave, código {codigo}")
    try:
        tamano = puntero.contents.CredentialBlobSize
        direccion = puntero.contents.CredentialBlob
        if not tamano or not direccion:
            return ""
        crudo = ctypes.string_at(direccion, tamano)
        return crudo.decode("utf-16-le")
    finally:
        biblioteca.CredFree(puntero)


def borrar(proveedor, prefijo=PREFIJO):
    """Borra la clave guardada. Dice si había una."""
    destino = _destino(proveedor, prefijo)
    _exigir_windows()
    biblioteca = _advapi32()
    if biblioteca.CredDeleteW(destino, _TIPO_GENERICO, 0):
        return True
    codigo = ctypes.get_last_error()
    if codigo == _NO_ENCONTRADO:
        return False
    raise OSError(f"no se pudo borrar la clave, código {codigo}")

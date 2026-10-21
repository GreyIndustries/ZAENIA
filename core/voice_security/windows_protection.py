"""Windows-account-bound protection; never persist an owner passphrase."""
from __future__ import annotations
import ctypes
import os
from ctypes import wintypes


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != 'nt':
        raise RuntimeError('Voice-only startup requires this Windows account.')
    if not isinstance(data, bytes) or not 0 < len(data) <= 2_000_000:
        raise ValueError('Invalid protected voice data.')
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = Blob(len(data), buffer), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        # UI forbidden, current-user scope. Never CRYPTPROTECT_LOCAL_MACHINE.
        if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(output.data, output.size)
        finally:
            if output.data:
                ctypes.memset(output.data, 0, output.size)
                kernel.LocalFree(output.data)
    finally:
        ctypes.memset(buffer, 0, len(data))

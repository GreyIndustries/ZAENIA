"""Atomic private writes and cross-process locks; no plaintext-vault staging."""
from __future__ import annotations
from contextlib import contextmanager
import csv
import ctypes
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time

def reject_link(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise PermissionError("A protected path contains a symbolic link.")
        if os.name == "nt" and part.exists():
            attributes = getattr(part.lstat(), "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise PermissionError("A protected path contains a reparse point.")

def atomic_write(path: Path, data: bytes, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_link(path)
    if not overwrite:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return
    descriptor, name = tempfile.mkstemp(prefix=".zaenia-write-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        reject_link(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

@contextmanager
def file_lock(path: Path, timeout: float = 10.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_link(path)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(descriptor, "r+b", buffering=0)
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Protected storage is busy; retry the operation.")
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

def protect_storage(directory: Path) -> str:
    """Restrict the security directory to this OS account and Windows SYSTEM."""
    directory.mkdir(parents=True, exist_ok=True)
    reject_link(directory)
    if os.name != "nt":
        directory.chmod(0o700)
        for path in directory.rglob("*"):
            reject_link(path)
            path.chmod(0o700 if path.is_dir() else 0o600)
        return "POSIX owner permissions applied"
    rows = csv.reader(subprocess.check_output(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        text=True, encoding="utf-8", errors="replace",
    ).splitlines())
    sid = next((row[-1].strip() for row in rows if row and row[-1].strip().startswith("S-1-")), None)
    if sid is None:
        raise RuntimeError("Could not resolve the current Windows account SID.")
    from ctypes import wintypes
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = api.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    convert.restype = wintypes.BOOL
    get_dacl = api.GetSecurityDescriptorDacl
    get_dacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    get_dacl.restype = wintypes.BOOL
    apply = api.SetNamedSecurityInfoW
    apply.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    apply.restype = wintypes.DWORD
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    for path in (directory, *directory.rglob("*")):
        reject_link(path)
        inheritance = "OICI" if path.is_dir() else ""
        sddl = f"D:P(A;{inheritance};FA;;;{sid})(A;{inheritance};FA;;;SY)"
        descriptor = ctypes.c_void_p()
        if not convert(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            present, defaulted, dacl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
            if not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not present.value or not dacl.value:
                raise RuntimeError("A private non-null Windows DACL is required.")
            result = apply(str(path), 1, 0x00000004 | 0x80000000, None, None, dacl, None)
            if result:
                raise ctypes.WinError(result)
        finally:
            kernel.LocalFree(descriptor)
    return "Windows owner and SYSTEM permissions applied"

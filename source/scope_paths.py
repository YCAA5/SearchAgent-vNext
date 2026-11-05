"""Canonical Windows scopes; mapped drives resolve to UNC when available."""
import ctypes
import ntpath
import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def mapped_drive(drive):
    try:
        if ctypes.windll.kernel32.GetDriveTypeW(drive + '\\') != 4:
            return None
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_string_buffer(size.value)
        if ctypes.windll.mpr.WNetGetUniversalNameW(drive + '\\', 1, buffer, ctypes.byref(size)) == 0:
            return ctypes.cast(buffer, ctypes.POINTER(ctypes.c_wchar_p)).contents.value.rstrip('\\')
    except (OSError, AttributeError):
        pass
    return None


def canonical_path(value):
    value = os.path.abspath(os.path.expanduser(str(value)))
    if os.name == 'nt' and len(value) >= 2 and value[1] == ':':
        universal = mapped_drive(value[:2].upper())
        if universal:
            value = universal + value[2:]
    normalized = os.path.normpath(value)
    return normalized.rstrip('\\') if normalized.startswith('\\\\') else normalized


def path_key(value):
    return os.path.normcase(canonical_path(value))


def within(path, root):
    child, parent = path_key(path), path_key(root)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def normalize_roots(roots):
    mapped_drive.cache_clear()
    selected = {}
    for root in roots:
        path = canonical_path(root)
        selected.setdefault(path_key(path), Path(path))
    values = sorted(selected.values(), key=lambda p: (len(str(p)), path_key(p)))
    result = []
    for value in values:
        if not any(within(value, parent) for parent in result):
            result.append(value)
    return result


def volume_identity(root):
    if os.name != 'nt' or str(root).startswith('\\\\'):
        return None
    try:
        serial = ctypes.c_ulong()
        drive = ntpath.splitdrive(str(root))[0] + '\\'
        if ctypes.windll.kernel32.GetVolumeInformationW(drive, None, 0, ctypes.byref(serial), None, None, None, 0):
            return str(serial.value)
    except (OSError, AttributeError):
        pass
    return None

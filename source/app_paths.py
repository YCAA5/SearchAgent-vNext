import os
import shutil
import sys
import hashlib
import tempfile
from pathlib import Path


FROZEN = bool(getattr(sys, 'frozen', False))
APP_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', APP_ROOT))


def data_directory():
    if os.environ.get('SEARCH_AGENT_HOME'):
        return Path(os.environ['SEARCH_AGENT_HOME']).expanduser().resolve()
    if not FROZEN:
        return APP_ROOT
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'SearchAgent-vNext'


DATA_ROOT = data_directory()
RUNTIME_ROOT = Path(os.environ.get('SEARCH_AGENT_RUNTIME', APP_ROOT / ('runtime' if FROZEN else '.runtime'))).resolve()


def resource_path(name):
    return RESOURCE_ROOT / name


def ocr_runtime_directory(directory):
    directory = Path(directory).resolve()
    if os.name != 'nt' or str(directory).isascii():
        return directory
    # This Windows Tesseract build cannot open its runtime from a Unicode path.
    import ctypes
    short_path = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(str(directory), short_path, len(short_path)) and short_path.value.isascii():
        return Path(short_path.value)
    identifier = hashlib.sha256(str(directory).encode('utf-8')).hexdigest()[:12]
    for base in (DATA_ROOT / 'cache', Path(tempfile.gettempdir()) / 'SearchAgent'):
        target = base / 'ocr' / identifier
        if not str(target).isascii():
            continue
        try:
            for source in directory.rglob('*'):
                if source.is_file():
                    destination = target / source.relative_to(directory)
                    info = source.stat()
                    if destination.is_file():
                        existing = destination.stat()
                        if existing.st_size == info.st_size and existing.st_mtime_ns == info.st_mtime_ns:
                            continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
            return target
        except OSError:
            continue
    raise RuntimeError('OCR needs a writable runtime location without non-ASCII characters. Set SEARCH_AGENT_RUNTIME to such a location.')


def find_tesseract():
    explicit = os.environ.get('TESSERACT_CMD')
    if explicit:
        return explicit
    executable = RUNTIME_ROOT / 'tesseract' / 'tesseract.exe'
    if executable.is_file():
        executable = ocr_runtime_directory(executable.parent) / executable.name
        os.environ['TESSDATA_PREFIX'] = str(executable.parent / 'tessdata')
        return str(executable)
    return shutil.which('tesseract')

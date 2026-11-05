import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def migrate(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    target_settings = destination / 'config' / 'desktop.json'
    if target_settings.exists() or any((destination / 'data' / 'indexes').glob('*.db')):
        raise FileExistsError('The target profile already contains user data; nothing was overwritten.')
    settings = json.loads((source / 'config' / 'desktop.json').read_text(encoding='utf-8'))
    target_settings.parent.mkdir(parents=True, exist_ok=True)
    output_indexes = destination / 'data' / 'indexes'
    output_indexes.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ('desktop.db', 'semantic.db'):
        path = source / 'data' / 'indexes' / name
        if path.is_file():
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as original:
                with closing(sqlite3.connect(output_indexes / name)) as output:
                    original.backup(output)
            copied.append(name)
    target_settings.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    return copied


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', type=Path, default=Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'SearchAgent-vNext')
    args = parser.parse_args()
    print(migrate(args.source, args.destination))

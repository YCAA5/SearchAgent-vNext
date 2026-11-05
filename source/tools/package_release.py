import argparse
import hashlib
import importlib.metadata
import json
import shutil
import zipfile
from pathlib import Path


ROOT_FILES = {
    'catalog_state.py', 'scope_paths.py', 'preparation.py', 'PROGRAM.md', 'CHANGELOG.md', 'main.py', 'desktop_app.py', 'ui_theme.py', 'i18n.py', 'app_paths.py', 'diagnostics.py',
    'local_catalog.py', 'semantic_search.py', 'document_preview.py', 'model_runtime.py', 'format_readers.py',
    'requirements.txt', 'requirements-dev.txt', 'requirements-lock.txt', 'SearchAgent.spec',
    'README.md', 'README.en.md', '.gitignore', '.gitattributes', '.env.example', 'Baslat.cmd',
}
SAFE_DIRECTORIES = {'agents', 'services', 'database', 'tests', 'tools', 'assets', '.github'}
SAFE_SUFFIXES = {'.py', '.ps1', '.txt', '.md', '.yml', '.yaml', '.svg', '.ico', '.png', '.ttf', '.csv', '.pdf', '.xyz'}


def source_files(project):
    project = Path(project).resolve()
    for path in sorted(project.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(project)
        if any(part in {'.git', '.venv', '.runtime', '__pycache__', '.pytest_cache', 'dist', 'build', 'releases', 'data', 'logs'} for part in relative.parts):
            continue
        if len(relative.parts) == 1 and relative.name in ROOT_FILES:
            yield path, relative
        elif relative.parts[0] in SAFE_DIRECTORIES and path.suffix.lower() in SAFE_SUFFIXES:
            yield path, relative
        elif relative.as_posix() in {'config/example.json', 'docs/DISTRIBUTION.md', 'docs/BUILD.md'}:
            yield path, relative


def write_source_archive(project, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, relative in source_files(project):
            archive.write(path, 'SearchAgent/' + relative.as_posix())
    return output


def copy_runtime(source, destination, gpu='cuda_v13', tesseract=None):
    source, destination = Path(source), Path(destination)
    ollama = source / 'ollama'
    if not (ollama / 'ollama.exe').is_file():
        raise FileNotFoundError('Ollama runtime is missing.')
    (destination / 'ollama').mkdir(parents=True, exist_ok=True)
    for path in ollama.iterdir():
        if path.is_file():
            shutil.copy2(path, destination / 'ollama' / path.name)
    library = ollama / 'lib' / 'ollama'
    library_output = destination / 'ollama' / 'lib' / 'ollama'
    library_output.mkdir(parents=True, exist_ok=True)
    for path in library.iterdir():
        if path.is_file():
            shutil.copy2(path, library_output / path.name)
        elif path.is_dir() and path.name in {gpu, 'vulkan'}:
            shutil.copytree(path, library_output / path.name, dirs_exist_ok=True)
    manifest_path = Path('manifests/registry.ollama.ai/library/qwen3-embedding/0.6b')
    manifest = source / 'models' / manifest_path
    content = json.loads(manifest.read_text(encoding='utf-8'))
    target_manifest = destination / 'models' / manifest_path
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, target_manifest)
    blob_directory = destination / 'models' / 'blobs'
    blob_directory.mkdir(parents=True, exist_ok=True)
    for entry in [content['config'], *content['layers']]:
        digest = entry['digest']
        if not digest.startswith('sha256:') or len(digest) != 71 or any(character not in '0123456789abcdef' for character in digest[7:]):
            raise ValueError('Model manifest contains an invalid digest.')
        name = digest.replace(':', '-')
        shutil.copy2(source / 'models' / 'blobs' / name, blob_directory / name)
        if sha256(blob_directory / name) != digest[7:]:
            raise ValueError('Copied model data failed SHA-256 verification.')
    if tesseract:
        tesseract = Path(tesseract)
        target = destination / 'tesseract'
        target.mkdir(parents=True, exist_ok=True)
        for path in tesseract.iterdir():
            if path.is_file() and (path.suffix.lower() == '.dll' or path.name == 'tesseract.exe' or path.name.lower().startswith(('license', 'copying', 'notice'))):
                shutil.copy2(path, target / path.name)
        (target / 'tessdata').mkdir(exist_ok=True)
        for name in ('eng.traineddata', 'tur.traineddata', 'osd.traineddata'):
            shutil.copy2(tesseract / 'tessdata' / name, target / 'tessdata' / name)
        if (tesseract / 'doc').is_dir():
            shutil.copytree(tesseract / 'doc', target / 'doc', dirs_exist_ok=True)


def collect_notices(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    packages = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name']
        if name.lower() in {'pip', 'pytest', 'pyinstaller', 'setuptools'}:
            continue
        licenses = []
        for member in distribution.files or []:
            if any(Path(part).name.lower().startswith(('license', 'copying', 'notice')) for part in Path(str(member)).parts):
                path = Path(distribution.locate_file(member))
                if path.is_file():
                    target = destination / name / Path(str(member)).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    licenses.append(target.relative_to(destination).as_posix())
        packages.append({'name': name, 'version': distribution.version, 'license_files': licenses})
    (destination / 'packages.json').write_text(json.dumps(packages, indent=2), encoding='utf-8')
    (destination / 'README.txt').write_text('Bundled Python packages retain their upstream licenses. Runtime/model components retain their own upstream licenses. Project licensing is not assigned by this build.\nOllama: https://github.com/ollama/ollama\nQwen3-Embedding: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B\nTesseract: https://github.com/tesseract-ocr/tesseract\n', encoding='utf-8')


def write_app_archive(application, output):
    application, output = Path(application), Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in application.rglob('*'):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(application)
                if any(part in {'userdata', 'config', 'logs', 'indexes', '__pycache__'} for part in relative.parts):
                    continue
                if path.suffix.lower() in {'.db', '.sqlite', '.log'}:
                    continue
                archive.write(path, 'SearchAgent/' + relative.as_posix())
    return output


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--application', type=Path)
    parser.add_argument('--tesseract', type=Path)
    parser.add_argument('--gpu', choices=['cpu', 'cuda_v12', 'cuda_v13'], default='cuda_v13')
    args = parser.parse_args()
    output = args.output or args.project / 'releases'
    application = args.application or args.project / 'dist' / 'SearchAgent'
    if not (application / 'SearchAgent.exe').is_file():
        raise FileNotFoundError('Build SearchAgent.exe before creating the release.')
    if args.runtime:
        copy_runtime(args.runtime, application / 'runtime', args.gpu, args.tesseract)
    shutil.copy2(args.project / 'PROGRAM.md', application / 'PROGRAM.md')
    shutil.copy2(args.project / 'CHANGELOG.md', application / 'CHANGELOG.md')
    collect_notices(application / 'third-party-notices')
    archives = [write_source_archive(args.project, output / 'SearchAgent-Source.zip'),
                write_app_archive(application, output / 'SearchAgent-Windows.zip')]
    (output / 'SHA256SUMS.txt').write_text(''.join(f'{sha256(path)}  {path.name}\n' for path in archives), encoding='utf-8')
    print(json.dumps([{'file': str(path), 'bytes': path.stat().st_size} for path in archives], indent=2))


if __name__ == '__main__':
    main()

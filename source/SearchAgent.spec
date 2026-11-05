from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / 'assets'), 'assets')]
binaries = []
hiddenimports = ['python_calamine', 'striprtf.striprtf', 'PIL.ImageTk', 'pymupdf', 'onnxruntime', 'networkx', 'yaml', 'psutil', 'tabulate']
for package in ('customtkinter', 'pymupdf'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += collect_data_files('onnxruntime')
binaries += collect_dynamic_libs('onnxruntime')
for distribution in ('pymupdf', 'pymupdf-layout', 'pymupdf4llm', 'python-calamine', 'customtkinter'):
    datas += copy_metadata(distribution)

analysis = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries, datas=datas,
                    hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
                    excludes=['pytest', 'torch', 'tensorflow', 'IPython', 'jupyter', 'matplotlib', 'scipy', 'pandas'],
                    noarchive=False)
archive = PYZ(analysis.pure)
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='SearchAgent',
                 debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
                 console=False, icon=str(root / 'assets' / 'app-icon.ico'))
application = COLLECT(executable, analysis.binaries, analysis.datas, strip=False, upx=False, name='SearchAgent')

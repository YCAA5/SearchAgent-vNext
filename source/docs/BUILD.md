# Building Search Agent on Windows

Python 3.12 x64 is required for development. Release users do not need Python.
Tesseract with eng/tur language data is required for OCR integration tests.
For the full guide and capacity recommendations, see ../PROGRAM.md.

1. Create a local virtual environment and install `requirements-lock.txt`.
2. Run `python -m pytest tests -q -p no:cacheprovider`.
3. Run `python tools/build_icon.py` if the editable icon was changed.
4. Run `python -m PyInstaller --noconfirm SearchAgent.spec`.

The result is `dist/SearchAgent/SearchAgent.exe` with its `_internal` support
directory. Keep the directory intact. `tools/build_windows.ps1` automates the
development environment, test, icon and build steps.

To create the offline distribution, run `tools/package_release.py` with
`--runtime` pointing to the prepared Ollama/model runtime directory and
`--tesseract` pointing to the Tesseract installation directory. The default
package includes CPU libraries, Vulkan and CUDA 13 libraries; CUDA 12 can be
chosen with `--gpu cuda_v12`, or use `--gpu cpu` for a CPU/Vulkan package.

The package tool creates source and Windows ZIP files plus SHA-256 checksums
under `releases/`. Python dependencies, model blobs and OCR binaries are carried
in the Windows package, not committed into the source repository. Model blob
checksums are verified while assembling the distribution.

`SearchAgent.exe --self-test-report report.json` checks bundled readers, icons,
languages, appearance and result layouts in a hidden test window. Add
`--verify-ocr` or `--verify-model` for offline runtime checks. Set
`SEARCH_AGENT_OLLAMA_PORT` to an unused local port when checking an independent
model service; only a service started by that test is stopped afterward.

GitHub Actions runs the test suite and builds an application-only artifact.
The large offline AI runtime is assembled separately by the package tool.

For the organized delivery use --workpath ../build --distpath ../application.
The package tool accepts --application ../application/SearchAgent --output ../releases.

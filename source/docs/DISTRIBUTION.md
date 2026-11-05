# Distribution and personal data

The source repository contains application code, tests, requirements, icons and
build instructions. It does not contain a developer's `.venv`, `.runtime`,
`.env`, selected folders, document contents, indexes, model weights or logs.

Use `SearchAgent-Source.zip` as the clean source export. The export is generated
from an allowlist, rather than archiving the entire working directory. Use the
Windows ZIP as a GitHub Release download, not as a Git-tracked source file.
`SHA256SUMS.txt` lists the distribution hashes. No repository or release is
published automatically by the local packaging tool.

The frozen application stores preferences, indexes and logs under
`%LOCALAPPDATA%/SearchAgent-vNext`. A fresh distribution starts without a document
index. Add folders and click Prepare / update search before searching. Application data
can be relocated with `--data-dir` or `SEARCH_AGENT_HOME`. Development runs retain
their existing project-local config and indexes.

`tools/migrate_profile.py --source <development-folder>` copies an existing
development profile to the EXE profile using SQLite backups. It refuses to
overwrite an existing destination. This profile remains local and is never
included in release archives.

The `runtime` directory next to the EXE contains Ollama, Qwen3-Embedding-0.6B and
Tesseract with Turkish/English language data when built as an offline package.
The model service binds only to the local loopback interface and cloud mode is
disabled. An existing compatible local Ollama service is reused when available.

On Windows, the bundled OCR runtime is cached under the private profile if its
installation path contains characters unsupported by the native OCR build.
This lets the application run from paths containing Turkish characters.

The application is not code-signed in this development build. Windows may show
an unknown-publisher prompt for downloaded executables. No Windows security
settings are changed by the application or the build scripts.

Third-party packages keep their upstream licenses; available notices are in
`third-party-notices` and the vendor runtime folders. The project owner's source
license must be selected separately; this build does not assign one.

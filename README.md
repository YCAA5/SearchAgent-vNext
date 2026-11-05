# SearchAgent-vNext
I tried to develop a local AI-powered file search engine. What I needed was to create a search program that would search for files on my computer and connected storage devices not by their names, but based on the content I could recall. This is how far I was able to develop it using ChatGPT Astra.


# Search Agent vNext Release

Program guide: [source/PROGRAM.md](source/PROGRAM.md)

- source/: clean GitHub source project
- application/SearchAgent/: executable EXE and support folders
- releases/: shareable ZIP packages and SHA-256 hashes
- reports/: pre-release changes, test results, and duration metrics
- build/: build intermediate files
- validation/: local test files; not shared

The previous project and personal profile have been preserved. No GitHub release has been made.

Translated with DeepL.com (free version)

## Application source

The complete application source, tests, icons, dependency versions and build scripts are in [source/](source/).

- [Complete program guide and system requirements](source/PROGRAM.md)
- [English overview](source/README.en.md)
- [Turkish overview](source/README.md)
- [Changes](source/CHANGELOG.md)
- [Windows build instructions](source/docs/BUILD.md)

Development commands are run from the `source` directory. The full offline Windows package includes Python libraries, Ollama, Qwen3-Embedding-0.6B and Tesseract; it is distributed separately from Git-tracked source files.

Personal documents, selected folders, indexes, logs, credentials and model weights are excluded from this repository.

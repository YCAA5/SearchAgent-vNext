
"""
Search Agent - File Scanner v0.1

Selected directory scanner.
- Recursive directory discovery
- File extension classification
- File metadata collection
- Terminal report
- JSON export

Original files are never modified.
"""

import os
import json
import argparse

from pathlib import Path
from datetime import datetime
from collections import Counter


SUPPORTED_FORMATS = {
    ".pdf": "document",
    ".docx": "document",
    ".txt": "text",
    ".xlsx": "spreadsheet",
    ".pptx": "presentation",
    ".html": "web",
    ".htm": "web",
    ".csv": "spreadsheet",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


def get_file_metadata(file_path: Path) -> dict:
    """Collect metadata without modifying the original file."""

    stat = file_path.stat(follow_symlinks=False)
    extension = file_path.suffix.lower()

    return {
        "name": file_path.name,
        "path": str(file_path.resolve()),
        "extension": extension,
        "category": SUPPORTED_FORMATS.get(extension, "unsupported"),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime
        ).astimezone().isoformat(timespec="seconds"),
    }


def scan_directory(root_path: Path) -> dict:
    """Recursively scan a selected directory."""

    root_path = root_path.resolve()

    if not root_path.exists():
        raise FileNotFoundError(f"Folder not found: {root_path}")

    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    supported_files = []
    unsupported_files = []
    errors = []

    directories = [root_path]

    while directories:
        current_dir = directories.pop()

        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            directories.append(Path(entry.path))
                            continue

                        if entry.is_file(follow_symlinks=False):
                            metadata = get_file_metadata(
                                Path(entry.path)
                            )

                            if metadata["category"] == "unsupported":
                                unsupported_files.append(metadata)
                            else:
                                supported_files.append(metadata)

                    except OSError as exc:
                        errors.append({
                            "path": entry.path,
                            "error": str(exc),
                        })

        except OSError as exc:
            errors.append({
                "path": str(current_dir),
                "error": str(exc),
            })

    supported_files.sort(key=lambda item: item["path"].lower())
    unsupported_files.sort(key=lambda item: item["path"].lower())

    all_supported = supported_files

    category_counts = dict(
        Counter(item["category"] for item in all_supported)
    )

    return {
        "scanner_version": "0.1",
        "root_directory": str(root_path),
        "scanned_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "summary": {
            "supported_files": len(supported_files),
            "unsupported_files": len(unsupported_files),
            "total_files": (
                len(supported_files) + len(unsupported_files)
            ),
            "errors": len(errors),
            "categories": category_counts,
        },
        "supported_files": supported_files,
        "unsupported_files": unsupported_files,
        "errors": errors,
    }


def export_json(report: dict, output_path: Path) -> None:
    """Export scan results to JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=4,
        )


def print_report(report: dict, output_path: Path) -> None:
    """Print scan summary to terminal."""

    summary = report["summary"]

    print("\n" + "=" * 55)
    print("       SEARCH AGENT - FILE SCANNER v0.1")
    print("=" * 55)

    print(f"\nScanned directory : {report['root_directory']}")
    print(f"Total files       : {summary['total_files']}")
    print(f"Supported files   : {summary['supported_files']}")
    print(f"Unsupported files : {summary['unsupported_files']}")
    print(f"Errors            : {summary['errors']}")

    print("\n--- FILE CATEGORIES ---")

    for category, count in sorted(summary["categories"].items()):
        print(f"{category:<18}: {count}")

    print("\n--- JSON EXPORT ---")
    print(f"Report saved to: {output_path}")

    print("\n" + "=" * 55)
    print("SCAN COMPLETED")
    print("=" * 55 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Search Agent File Scanner v0.1"
    )

    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory to scan"
    )

    parser.add_argument(
        "--output",
        help="Custom JSON output path"
    )

    args = parser.parse_args()

    selected_directory = args.directory

    if not selected_directory:
        selected_directory = input(
            "Enter directory path to scan: "
        ).strip().strip('"')

    root_path = Path(selected_directory)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    default_output = (
        Path("data") /
        "indexes" /
        f"file_inventory_{timestamp}.json"
    )

    output_path = (
        Path(args.output)
        if args.output
        else default_output
    )

    try:
        print("\nScanning directory...")

        report = scan_directory(root_path)

        export_json(report, output_path)

        print_report(report, output_path)

    except (OSError, ValueError) as exc:
        print(f"\nScanner error: {exc}")


if __name__ == "__main__":
    main()

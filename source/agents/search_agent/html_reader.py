
"""
Search Agent - HTML Reader v0.1

Features:
- HTML title extraction
- Main text extraction
- H1-H6 heading extraction
- Link extraction
- Metadata extraction
- Script and style exclusion
- Character count

Original HTML files are never modified.
"""

from pathlib import Path

from bs4 import BeautifulSoup


def read_html(file_path: str | Path) -> dict:
    """Extract readable content and metadata from an HTML file."""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("File must have an HTML or HTM extension.")

    content = path.read_text(encoding="utf-8-sig")

    soup = BeautifulSoup(content, "html.parser")

    # Extract metadata before modifying the document.
    metadata = {}

    for name in ["description", "keywords", "author"]:
        tag = soup.find(
            "meta",
            attrs={"name": name}
        )

        metadata[name] = (
            tag.get("content", "").strip()
            if tag
            else None
        )

    # Extract page title.
    title = (
        soup.title.get_text(strip=True)
        if soup.title
        else None
    )

    # Extract headings.
    headings = []

    for tag in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6"]
    ):
        text = tag.get_text(" ", strip=True)

        if text:
            headings.append({
                "level": int(tag.name[1]),
                "text": text,
            })

    # Extract links.
    links = []

    for tag in soup.find_all("a", href=True):
        links.append({
            "text": tag.get_text(" ", strip=True),
            "url": tag["href"].strip(),
        })

    # Remove non-content elements.
    for tag in soup.find_all(
        ["script", "style", "noscript", "template", "svg"]
    ):
        tag.decompose()

    # Remove elements marked as hidden.
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()

    for tag in soup.find_all(
        style=lambda value: value and "display:none" in value.replace(" ", "").lower()
    ):
        tag.decompose()

    # Extract readable text.
    body = soup.body if soup.body else soup

    text = body.get_text(" ", strip=True)

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_type": "html",
        "title": title,
        "text": text,
        "headings": headings,
        "links": links,
        "metadata": metadata,
        "total_characters": len(text),
    }

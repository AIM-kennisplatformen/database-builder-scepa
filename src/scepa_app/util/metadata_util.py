import html
from typing import Any

from bs4 import BeautifulSoup
from database_builder_libs.models.abstract_source import Content


def strip_html_tags(text: str | None) -> str | None:
    """
    Remove HTML/XML tags from text and decode all HTML entities.

    Combines two approaches for optimal results:

    1. BeautifulSoup for tag removal:
       - Handles malformed/unclosed HTML tags correctly
       - Preserves meaningful whitespace
       - Safe for complex nested structures

    2. html.unescape() for entity decoding:
       - Handles named entities: &lt;, &gt;, &mdash;, &copy;, etc. (258+ entities)
       - Handles decimal entities: &#123;, &#160;, etc.
       - Handles hexadecimal entities: &#x1A;, &#x003C;, etc.

    Args:
        text: String that may contain HTML tags and entities

    Returns:
        Clean string with tags removed and entities decoded, or None if input is None

    Example:
        >>> strip_html_tags("<p>Price: &#163;50 &amp; &lt;select&gt;</p>")
        "Price: £50 & <select>"
    """
    if not text:
        return text

    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    text = html.unescape(text)

    return text.strip() if text else None


def escape_typeql_string(text: str | None) -> str | None:
    """Escape special characters for TypeQL string literals."""
    if not text:
        return text
    # Escape backslashes first, then quotes
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    return text


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize metadata fields by removing unwanted content.

    Operations:
    - Strips HTML/XML tags from all string fields
    - Removes None values to avoid null checks
    - Cleans up whitespace

    Args:
        metadata: Dictionary of metadata fields

    Returns:
        Dictionary with HTML-stripped, non-None values
    """
    sanitized = {}
    for key, value in metadata.items():
        # Skip None values entirely
        if value is None:
            continue

        if isinstance(value, str):
            # Strip HTML tags from string values
            value = strip_html_tags(value)
        elif isinstance(value, list) and value and isinstance(value[0], str):
            # Handle list of strings (e.g., authors, keywords)
            value = [strip_html_tags(v) for v in value]

        # Only include non-empty values after sanitization
        if value:
            sanitized[key] = value

    return sanitized


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize metadata fields for storage in TypeQL.

    Operations:
    - Escapes special characters (quotes, backslashes) for TypeQL syntax
    - Ensures strings are TypeQL-safe

    Args:
        metadata: Dictionary of metadata fields (typically already sanitized)

    Returns:
        Dictionary with TypeQL-escaped values

    Note:
        This function should typically be called after sanitize_metadata().
        It expects clean input without HTML tags or None values.
    """
    normalized = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            # Escape special characters for TypeQL
            value = escape_typeql_string(value)
        elif isinstance(value, list) and value and isinstance(value[0], str):
            # Handle list of strings (e.g., authors, keywords)
            value = [escape_typeql_string(v) for v in value]

        normalized[key] = value

    return normalized


def _zotero_nonempty(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _zotero_format_name(creator: dict) -> str:
    """Format a Zotero creator dict as 'Last, First'."""
    if "name" in creator:
        return creator["name"].strip()
    last = (creator.get("lastName") or "").strip()
    first = (creator.get("firstName") or "").strip()
    if last and first:
        return f"{last}, {first}"
    return last or first


def extract_zotero_metadata(zotero_content: Content) -> dict[str, Any]:
    """
    Pull the fields we care about out of a Zotero Content object.

    ZoteroSource.get_content() sets Content.content = item["data"], so the
    dict is already flat — title, creators, publisher, etc. are top-level keys.

    Returns a dict with the same field names used in the PDF metadata dict so
    it can be merged directly into Content.content["metadata"]:

        title, authors, publishing_institute, summary, keywords
    """
    data = zotero_content.content

    authors = [
        _zotero_format_name(c)
        for c in (data.get("creators") or [])
        if c.get("creatorType") in ("author", "editor")
        and "name" not in c  # single "name" field = organisation, not a person
    ] or None

    publishing_institute = _zotero_nonempty(
        data.get("institution")
    ) or _zotero_nonempty(data.get("publisher"))

    tags = [t["tag"] for t in (data.get("tags") or []) if t.get("tag")]

    return {
        "title": _zotero_nonempty(data.get("title")),
        "authors": authors,
        "publishing_institute": {"name": publishing_institute}
        if publishing_institute
        else None,
        "summary": _zotero_nonempty(data.get("abstractNote")),
        "keywords": tags or None,
    }


def merge_zotero_into_content(
    pdf_content: Content,
    zotero_fields: dict[str, Any],
) -> Content:
    """
    Overlay Zotero-sourced fields onto the PDF Content's metadata dict.

    Only non-None Zotero fields are written; PDF-extracted values are kept
    for everything else.  The ``source`` tracking dict is updated accordingly.
    """
    meta = dict(pdf_content.content.get("metadata", {}))
    source = dict(meta.get("source", {}))

    for field_name, value in zotero_fields.items():
        if value is not None:
            meta[field_name] = value
            source[field_name] = "zotero"

    meta["source"] = source

    updated = dict(pdf_content.content)
    updated["metadata"] = meta

    return Content(date=pdf_content.date, id_=pdf_content.id_, content=updated)

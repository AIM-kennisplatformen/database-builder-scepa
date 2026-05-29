"""
zotero.py
~~~~~~~~~
Converts a raw Zotero API item dict into a BibTeX string via CiteBuilder.

Usage:
    from cite_builder.zotero import zotero_to_bibtex
    bib = zotero_to_bibtex(zotero_item)
"""

from __future__ import annotations
from .citebuilder import CiteBuilder

_cb = CiteBuilder()

# Map Zotero itemType → CiteBuilder method
_DISPATCH = {
    "journalArticle":   _cb.create_article,
    "preprint":         _cb.create_article,
    "report":           _cb.create_article,
    "thesis":           _cb.create_article,
    "book":             _cb.create_book,
    "bookSection":      _cb.create_book,
    "conferencePaper":  _cb.create_inproceedings,
    "webpage":          _cb.create_webpage,
    "blogPost":         _cb.create_webpage,
    "document":         _cb.create_webpage,
}


def _parse_authors(creators: list[dict]) -> list[str]:
    """Return BibTeX-formatted 'Last, First' author strings."""
    authors = []
    for c in creators:
        if c.get("creatorType") != "author":
            continue
        last = c.get("lastName", "").strip()
        first = c.get("firstName", "").strip()
        if last and first:
            authors.append(f"{last}, {first}")
        elif last:
            authors.append(last)
        elif first:
            authors.append(first)
    return authors


def _parse_editors(creators: list[dict]) -> list[str]:
    editors = []
    for c in creators:
        if c.get("creatorType") != "editor":
            continue
        last = c.get("lastName", "").strip()
        first = c.get("firstName", "").strip()
        editors.append(f"{last}, {first}" if last and first else last or first)
    return editors


def _year(date_str: str) -> str:
    """Extract 4-digit year from any date string."""
    import re
    m = re.search(r"\b(\d{4})\b", date_str or "")
    return m.group(1) if m else ""


def _citation_key(data: dict, authors: list[str], year: str) -> str:
    """Use Zotero key as citation key — short and stable."""
    return data.get("key") or data.get("citationKey") or (
        (authors[0].split(",")[0] if authors else "Unknown") + year
    )


def zotero_to_bibtex(item: dict) -> str:
    """
    Convert a Zotero API item dict to a BibTeX string.

    Handles: journalArticle, book, bookSection, conferencePaper,
             webpage, preprint, report, thesis, blogPost, document.
    Falls back to @misc for any unrecognised type.
    """
    data = item.get("data", item)  # accept both raw item and unwrapped data dict
    item_type = data.get("itemType", "document")
    creators = data.get("creators", [])

    authors = _parse_authors(creators)
    editors = _parse_editors(creators)
    year    = _year(data.get("date", ""))
    key     = _citation_key(data, authors, year)
    doi     = data.get("DOI", "").strip()
    url     = data.get("url", "").strip()

 
    common = {
        "citation_key": key,
        "title":        data.get("title", ""),
        "authors":      authors,
        "year":         year,
        "doi":          doi,
        "url":          url,
    }


    if item_type in ("journalArticle", "preprint", "report", "thesis"):
        return _cb.create_article(
            **common,
            journal = data.get("publicationTitle") or data.get("reporter") or "",
            volume  = data.get("volume", ""),
            number  = data.get("issue", ""),
            pages   = data.get("pages", ""),
        )

    elif item_type in ("book", "bookSection"):
        return _cb.create_book(
            **common,
            editors   = editors,
            publisher = data.get("publisher", ""),
            address   = data.get("place", ""),
            edition   = data.get("edition", ""),
            isbn      = data.get("ISBN", ""),
        )

    elif item_type == "conferencePaper":
        return _cb.create_inproceedings(
            **common,
            booktitle    = data.get("proceedingsTitle") or data.get("publicationTitle", ""),
            pages        = data.get("pages", ""),
            organization = data.get("publisher", ""),
            address      = data.get("place", ""),
        )

    elif item_type in ("webpage", "blogPost", "document"):
        accessed = data.get("accessDate", "")
        if accessed:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(accessed.replace("Z", "+00:00"))
                accessed = dt.strftime("%b. %d, %Y")
            except ValueError:
                pass
        return _cb.create_webpage(
            **common,
            organization = data.get("publisher") or data.get("websiteTitle", ""),
            accessed     = accessed,
        )

    else:
        # Fallback: @misc with whatever fields we have
        return _cb.create_webpage(**common)
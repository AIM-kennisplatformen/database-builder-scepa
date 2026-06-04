"""
citation_export.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Generates BibTeX entries from document metadata dicts.

Supports IEEE-style bibliography (IEEEtran.bst) for:
  - @article       — journalArticle, preprint
  - @techreport    — report
  - @phdthesis     — thesis
  - @book          — book, bookSection
  - @inproceedings — conferencePaper
  - @misc          — webpage, blogPost, document

DOI-based fetch from doi.org is attempted first; document metadata
is used as fallback when the DOI is absent or the fetch fails.

"""

from __future__ import annotations

import logging
import re
import requests
from datetime import datetime


logger = logging.getLogger(__name__)

# Fixed English month abbreviations so output is locale-independent.
_MONTH_ABBR = {
    1: "Jan.", 2: "Feb.", 3: "Mar.", 4: "Apr.", 5: "May", 6: "Jun.",
    7: "Jul.", 8: "Aug.", 9: "Sep.", 10: "Oct.", 11: "Nov.", 12: "Dec.",
}


# ---------------------------------------------------------------------------
# BibTeX rendering helpers
# ---------------------------------------------------------------------------

def _clean(value: str) -> str:
    return " ".join(str(value).split())


def _format_authors(authors: str | list[str]) -> str:
    if isinstance(authors, list):
        return " and ".join(_clean(a) for a in authors if a)
    return _clean(authors)


def _make_key(title: str, year: str | int) -> str:
    # Unicode-aware: keep alphabetic characters (incl. accented) and drop the rest.
    first_word = "".join(c for c in title.split()[0] if c.isalpha()) if title else "Unknown"
    return f"{first_word}{year}"


def _render_entry(entry_type: str, key: str, fields: dict[str, str]) -> str:
    lines = [f"@{entry_type}{{{key},"]
    max_key_len = max(len(k) for k in fields)
    for k, v in fields.items():
        if v:
            lines.append(f"  {k:<{max_key_len}} = {{{v}}},")
    # Only strip a trailing comma if at least one field line was emitted;
    # otherwise the opening line would be mangled into invalid BibTeX.
    if len(lines) > 1 and lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DOI lookup
# ---------------------------------------------------------------------------

def _from_doi(doi: str, timeout: int = 5) -> str | None:
    """Fetch BibTeX from doi.org content negotiation. Returns None on failure."""
    doi = doi.strip().lstrip("https://doi.org/").lstrip("http://dx.doi.org/")
    try:
        r = requests.get(
            f"https://doi.org/{doi}",
            headers={"Accept": "application/x-bibtex; charset=utf-8"},
            timeout=timeout,
        )
        r.raise_for_status()
        bib = r.text.strip()
        if bib.startswith("@"):
            return bib
    except requests.exceptions.RequestException as exc:
        logger.warning("DOI BibTeX fetch failed for %r: %s", doi, exc)
    return None


# ---------------------------------------------------------------------------
# Entry builders
# ---------------------------------------------------------------------------

def _article(
    *,
    citation_key: str = "",
    title: str = "",
    authors: str = "",
    journal: str = "",
    year: str = "",
    volume: str = "",
    number: str = "",
    pages: str = "",
    doi: str = "",
    url: str = "",
) -> str:
    if doi:
        bib = _from_doi(doi)
        if bib:
            return bib
    key = citation_key or _make_key(title, year)
    return _render_entry("article", key, {
        "author":  _format_authors(authors),
        "title":   _clean(title),
        "journal": _clean(journal),
        "year":    year,
        "volume":  volume,
        "number":  number,
        "pages":   _clean(pages),
        "doi":     _clean(doi),
        "url":     _clean(url),
    })


def _techreport(
    *,
    citation_key: str = "",
    title: str = "",
    authors: str = "",
    institution: str = "",
    year: str = "",
    number: str = "",
    address: str = "",
    doi: str = "",
    url: str = "",
) -> str:
    if doi:
        bib = _from_doi(doi)
        if bib:
            return bib
    key = citation_key or _make_key(title, year)
    return _render_entry("techreport", key, {
        "author":      _format_authors(authors),
        "title":       _clean(title),
        "institution": _clean(institution),
        "year":        year,
        "number":      _clean(number),
        "address":     _clean(address),
        "doi":         _clean(doi),
        "url":         _clean(url),
    })


def _phdthesis(
    *,
    citation_key: str = "",
    title: str = "",
    authors: str = "",
    school: str = "",
    year: str = "",
    address: str = "",
    doi: str = "",
    url: str = "",
) -> str:
    if doi:
        bib = _from_doi(doi)
        if bib:
            return bib
    key = citation_key or _make_key(title, year)
    return _render_entry("phdthesis", key, {
        "author":  _format_authors(authors),
        "title":   _clean(title),
        "school":  _clean(school),
        "year":    year,
        "address": _clean(address),
        "doi":     _clean(doi),
        "url":     _clean(url),
    })


def _book(
    *,
    citation_key: str = "",
    title: str = "",
    authors: str = "",
    editors: str = "",
    publisher: str = "",
    year: str = "",
    address: str = "",
    edition: str = "",
    isbn: str = "",
    doi: str = "",
    url: str = "",
) -> str:
    if doi:
        bib = _from_doi(doi)
        if bib:
            return bib
    key = citation_key or _make_key(title, year)
    return _render_entry("book", key, {
        "author":    _format_authors(authors),
        "editor":    _format_authors(editors),
        "title":     _clean(title),
        "publisher": _clean(publisher),
        "year":      year,
        "address":   _clean(address),
        "edition":   _clean(edition),
        "isbn":      _clean(isbn),
        "doi":       _clean(doi),
        "url":       _clean(url),
    })


def _inproceedings(
    *,
    citation_key: str = "",
    title: str = "",
    authors: str = "",
    booktitle: str = "",
    year: str = "",
    pages: str = "",
    organization: str = "",
    address: str = "",
    doi: str = "",
    url: str = "",
) -> str:
    if doi:
        bib = _from_doi(doi)
        if bib:
            return bib
    key = citation_key or _make_key(title, year)
    return _render_entry("inproceedings", key, {
        "author":       _format_authors(authors),
        "title":        _clean(title),
        "booktitle":    _clean(booktitle),
        "year":         year,
        "pages":        _clean(pages),
        "organization": _clean(organization),
        "address":      _clean(address),
        "doi":          _clean(doi),
        "url":          _clean(url),
    })


def _misc(
    *,
    citation_key: str = "",
    title: str = "",
    authors: str = "",
    year: str = "",
    url: str = "",
    accessed: str = "",
    organization: str = "",
) -> str:
    key = citation_key or _make_key(title, year)
    note_parts = []
    if url:
        note_parts.append(f"[Online]. Available: {url}")
    if accessed:
        note_parts.append(f"Accessed: {accessed}")
    return _render_entry("misc", key, {
        "author":       _format_authors(authors),
        "title":        _clean(title),
        "year":         year,
        "organization": _clean(organization),
        "url":          _clean(url),
        "note":         ". ".join(note_parts),
    })


# ---------------------------------------------------------------------------
# Zotero metadata parsing
# ---------------------------------------------------------------------------

def _parse_people(creators: list[dict], role: str) -> str:
    """Parse Zotero creators of a given role into a BibTeX 'Last, First' string."""
    people = []
    for c in creators:
        if c.get("creatorType") != role:
            continue
        last  = c.get("lastName", "").strip()
        first = c.get("firstName", "").strip()
        # Handle organisations stored as a single 'name' field
        name  = c.get("name", "").strip()
        if last and first:
            people.append(f"{last}, {first}")
        elif last or first:
            people.append(last or first)
        elif name:
            people.append(name)
    return " and ".join(people)


def _extract_year(date_str: str) -> str:
    m = re.search(r"\b(\d{4})\b", date_str or "")
    return m.group(1) if m else ""


def _format_access_date(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return f"{_MONTH_ABBR[dt.month]} {dt.day:02d}, {dt.year}"
    except ValueError:
        return iso_date


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def zotero_to_bibtex(item: dict) -> str:
    """
    Convert a Zotero API item dict to a BibTeX string.

    Accepts both the full Zotero API response (with a nested 'data' key)
    and the unwrapped data dict directly.
    """
    data      = item.get("data", item)
    item_type = str(data.get("itemType") or "document")
    creators  = data.get("creators") or []

    authors = _parse_people(creators, "author")
    editors = _parse_people(creators, "editor")
    year    = _extract_year(str(data.get("date") or ""))
    key     = str(data.get("key") or data.get("citationKey") or _make_key(str(data.get("title") or ""), year))
    doi     = str(data.get("DOI") or "").strip()
    url     = str(data.get("url") or "").strip()

    common: dict[str, str] = {
        "citation_key": key,
        "title":        str(data.get("title") or ""),
        "authors":      authors,
        "year":         year,
        "doi":          doi,
        "url":          url,
    }

    if item_type in ("journalArticle", "preprint"):
        return _article(
            **common,
            journal = str(data.get("publicationTitle") or ""),
            volume  = str(data.get("volume") or ""),
            number  = str(data.get("issue") or ""),
            pages   = str(data.get("pages") or ""),
        )

    if item_type == "report":
        return _techreport(
            **common,
            institution = str(data.get("institution") or data.get("publisher") or ""),
            number      = str(data.get("reportNumber") or ""),
            address     = str(data.get("place") or ""),
        )

    if item_type == "thesis":
        return _phdthesis(
            **common,
            school  = str(data.get("university") or data.get("publisher") or ""),
            address = str(data.get("place") or ""),
        )

    if item_type in ("book", "bookSection"):
        return _book(
            **common,
            editors   = editors,
            publisher = str(data.get("publisher") or ""),
            address   = str(data.get("place") or ""),
            edition   = str(data.get("edition") or ""),
            isbn      = str(data.get("ISBN") or ""),
        )

    if item_type == "conferencePaper":
        return _inproceedings(
            **common,
            booktitle    = str(data.get("proceedingsTitle") or data.get("publicationTitle") or ""),
            pages        = str(data.get("pages") or ""),
            organization = str(data.get("publisher") or ""),
            address      = str(data.get("place") or ""),
        )

    misc_common = {k: v for k, v in common.items() if k != "doi"}

    if item_type in ("webpage", "blogPost", "document"):
        raw_access = str(data.get("accessDate") or "")
        return _misc(
            **misc_common,
            organization = str(data.get("publisher") or data.get("websiteTitle") or ""),
            accessed     = _format_access_date(raw_access) if raw_access else "",
        )

    # Fallback for any unrecognised item type
    return _misc(**misc_common)
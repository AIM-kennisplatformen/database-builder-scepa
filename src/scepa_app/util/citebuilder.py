"""
cite_builder.py
~~~~~~~~~~~~~~~
Generates BibTeX entries for use with IEEE-style bibliography (IEEEtran.bst).

Supports:
  - @article       — journal papers (with or without DOI)
  - @book          — books
  - @inproceedings — conference papers
  - @misc          — websites / online resources

Usage:
    from cite_builder import CiteBuilder

    cb = CiteBuilder()

    # From DOI (fetches metadata automatically)
    bib = cb.from_doi("10.1109/TPAMI.2021.1234567")

    # Manual entries
    bib = cb.create_article(citation_key="Smith2024", title="...", ...)
    bib = cb.create_book(citation_key="Goodfellow2016", title="...", ...)
    bib = cb.create_inproceedings(citation_key="He2016", title="...", ...)
    bib = cb.create_webpage(citation_key="PyTorch2024", title="...", ...)
"""

from __future__ import annotations

import re

import requests


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean(value: str) -> str:
    """Strip and normalise whitespace in a field value."""
    return " ".join(str(value).split())


def _format_authors(authors: str | list[str]) -> str:
    """
    Accept either a pre-formatted BibTeX author string or a list of names.
    List items may be "First Last" or "Last, First" — both are kept as-is
    and joined with ' and '.
    """
    if isinstance(authors, list):
        return " and ".join(_clean(a) for a in authors if a)
    return _clean(authors)


def _make_key(title: str, year: str | int) -> str:
    """Auto-generate a citation key from the first title word + year."""
    first_word = re.sub(r"[^a-zA-Z]", "", title.split()[0]) if title else "Unknown"
    return f"{first_word}{year}"


def _render_entry(entry_type: str, key: str, fields: dict[str, str]) -> str:
    """Render a BibTeX entry string from a dict of fields."""
    lines = [f"@{entry_type}{{{key},"]
    max_key_len = max(len(k) for k in fields)
    for k, v in fields.items():
        if v:  # skip empty fields
            lines.append(f"  {k:<{max_key_len}} = {{{v}}},")
    # Remove trailing comma from last field (cosmetic)
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CiteBuilder:
    """
    Builds BibTeX entries for IEEE-style references.

    All `create_*` methods return a BibTeX string ready to paste into a
    .bib file.  Every field is optional except where noted; missing fields
    are simply omitted from the output.
    """

    # ------------------------------------------------------------------
    # DOI lookup
    # ------------------------------------------------------------------

    def from_doi(self, doi: str, timeout: int = 5) -> str | None:
        """
        Fetch a BibTeX entry directly from doi.org content negotiation.

        Returns the BibTeX string if successful, or None if the DOI could
        not be resolved or the response is not valid BibTeX.
        """
        doi = doi.strip().lstrip("https://doi.org/").lstrip("http://dx.doi.org/")
        url = f"https://doi.org/{doi}"
        headers = {"Accept": "application/x-bibtex; charset=utf-8"}
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            bib = r.text.strip()
            if bib.startswith("@"):
                return bib
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # @article
    # ------------------------------------------------------------------

    def create_article(
        self,
        *,
        citation_key: str = "",
        title: str = "",
        authors: str | list[str] = "",
        journal: str = "",
        year: str | int = "",
        volume: str | int = "",
        number: str | int = "",
        pages: str = "",
        doi: str = "",
        url: str = "",
        note: str = "",
    ) -> str:
        """
        Build an @article entry.

        If a DOI is provided, tries to fetch the canonical BibTeX first
        and falls back to building from the supplied fields on failure.

        Required by IEEE: author, title, journal, year.
        """
        if doi:
            try:
                return self.from_doi(doi)
            except Exception:
                pass  # fall through to manual build

        key = citation_key or _make_key(title, year)
        author_str = _format_authors(authors)
        fields = {
            "author":  author_str,
            "title":   _clean(title),
            "journal": _clean(journal),
            "year":    str(year),
            "volume":  str(volume) if volume else "",
            "number":  str(number) if number else "",
            "pages":   _clean(pages),
            "doi":     _clean(doi),
            "url":     _clean(url),
            "note":    _clean(note),
        }
        return _render_entry("article", key, fields)

    # ------------------------------------------------------------------
    # @book
    # ------------------------------------------------------------------

    def create_book(
        self,
        *,
        citation_key: str = "",
        title: str = "",
        authors: str | list[str] = "",
        editors: str | list[str] = "",
        publisher: str = "",
        year: str | int = "",
        address: str = "",
        edition: str = "",
        isbn: str = "",
        doi: str = "",
        url: str = "",
        note: str = "",
    ) -> str:
        """
        Build a @book entry.

        IEEE requires: author/editor, title, publisher, year.
        """
        if doi:
            try:
                return self.from_doi(doi)
            except Exception:
                pass

        key = citation_key or _make_key(title, year)
        author_str = _format_authors(authors)
        editor_str = _format_authors(editors)
        fields = {
            "author":    author_str,
            "editor":    editor_str,
            "title":     _clean(title),
            "publisher": _clean(publisher),
            "year":      str(year),
            "address":   _clean(address),
            "edition":   _clean(edition),
            "isbn":      _clean(isbn),
            "doi":       _clean(doi),
            "url":       _clean(url),
            "note":      _clean(note),
        }
        return _render_entry("book", key, fields)

    # ------------------------------------------------------------------
    # @inproceedings
    # ------------------------------------------------------------------

    def create_inproceedings(
        self,
        *,
        citation_key: str = "",
        title: str = "",
        authors: str | list[str] = "",
        booktitle: str = "",
        year: str | int = "",
        pages: str = "",
        organization: str = "",
        publisher: str = "",
        address: str = "",
        doi: str = "",
        url: str = "",
        note: str = "",
    ) -> str:
        """
        Build an @inproceedings entry (conference paper).

        IEEE requires: author, title, booktitle, year.
        booktitle should be the full conference name, e.g.
        "Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR)".
        """
        if doi:
            try:
                return self.from_doi(doi)
            except Exception:
                pass

        key = citation_key or _make_key(title, year)
        author_str = _format_authors(authors)
        fields = {
            "author":       author_str,
            "title":        _clean(title),
            "booktitle":    _clean(booktitle),
            "year":         str(year),
            "pages":        _clean(pages),
            "organization": _clean(organization),
            "publisher":    _clean(publisher),
            "address":      _clean(address),
            "doi":          _clean(doi),
            "url":          _clean(url),
            "note":         _clean(note),
        }
        return _render_entry("inproceedings", key, fields)

    # ------------------------------------------------------------------
    # @misc  (websites, online resources, software, …)
    # ------------------------------------------------------------------

    def create_webpage(
        self,
        *,
        citation_key: str = "",
        title: str = "",
        authors: str | list[str] = "",
        year: str | int = "",
        url: str = "",
        accessed: str = "",
        organization: str = "",
        note: str = "",
    ) -> str:
        """
        Build a @misc entry for an online/webpage source.

        IEEE style for websites:
          Author(s), "Title," Organization, Year. [Online]. Available: URL.
          Accessed: Date.

        `accessed` should be a human-readable date string, e.g. "Jan. 15, 2024".
        The [Online] note and accessed date are folded into the `note` field
        automatically if `url` is provided.
        """
        key = citation_key or _make_key(title, year)
        author_str = _format_authors(authors)

        # Build the IEEE-style note
        auto_note_parts = []
        if url:
            auto_note_parts.append(f"[Online]. Available: {url}")
        if accessed:
            auto_note_parts.append(f"Accessed: {accessed}")
        if note:
            auto_note_parts.append(note)
        full_note = ". ".join(auto_note_parts)

        fields = {
            "author":       author_str,
            "title":        _clean(title),
            "year":         str(year),
            "organization": _clean(organization),
            "url":          _clean(url),
            "note":         full_note,
        }
        return _render_entry("misc", key, fields)
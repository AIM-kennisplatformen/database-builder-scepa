from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List
import re

from docling_core.types.doc import DoclingDocument, SectionHeaderItem, TextItem
from pypdf import PdfReader

@dataclass(slots=True)
class TextMetadata:
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    institute: Optional[str] = None
    # field -> "pdf_metadata" | "docling_heuristic"
    source: dict[str, str] = field(default_factory=dict)


class TextMetadataExtractor:
    """
    Extracts whatever metadata it can from:
      1) PDF embedded metadata (/Title, /Author)
      2) Docling text heuristics (first lines / first section header)

    No Zotero usage.
    """

    _AFFIL_KWS = (
        "university", "universiteit",
        "institute", "instituut",
        "department", "faculteit",
        "school", "lab", "laboratory",
        "research", "centre", "center",
        "ministry", "ministerie",
        "gemeente", "provincie",
    )

    def extract(self, *, pdf_path: str, doc: DoclingDocument) -> TextMetadata:
        meta = TextMetadata(source={})

        self._fill_from_pdf_metadata(meta, pdf_path)
        self._fill_from_docling(meta, doc)
        if meta.authors is not None and len(meta.authors) == 0:
            meta.authors = None

        return meta

    def _fill_from_pdf_metadata(self, meta: TextMetadata, pdf_path: str) -> None:
        try:
            reader = PdfReader(pdf_path)
            info = reader.metadata
        except Exception:
            return

        if not info:
            return

        if meta.title is None:
            title = getattr(info, "title", None)
            if not title and hasattr(info, "get"):
                title = info.get("/Title")
            title = self._clean_pdf_meta_string(title)
            if title:
                meta.title = title
                meta.source["title"] = "pdf_metadata"

        if meta.authors is None:
            author = getattr(info, "author", None)
            if not author and hasattr(info, "get"):
                author = info.get("/Author")
            author = self._clean_pdf_meta_string(author)
            if author:
                meta.authors = self._split_authors(author)
                meta.source["authors"] = "pdf_metadata"

    def _clean_pdf_meta_string(self, value: object) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        # common junk
        junk = {"unknown", "untitled", "microsoft word", "writer", "author"}
        if s.lower() in junk:
            return None
        return s

    def _split_authors(self, s: str) -> List[str]:
        # conservative splitting
        if ";" in s:
            parts = [p.strip() for p in s.split(";")]
        elif re.search(r"\band\b", s, flags=re.I):
            parts = [p.strip() for p in re.split(r"\band\b", s, flags=re.I)]
        else:
            parts = [s]
        return [p for p in parts if p]

    # ─────────────────────────────────────────────
    # Docling heuristics fallback
    # ─────────────────────────────────────────────

    def _fill_from_docling(self, meta: TextMetadata, doc: DoclingDocument) -> None:
        lines = self._first_lines(doc, limit=80)

        if meta.title is None:
            title = self._first_section_header(doc) or self._first_reasonable_line(lines)
            if title:
                meta.title = title
                meta.source["title"] = "docling_heuristic"

        if meta.authors is None:
            authors = self._guess_authors(lines)
            if authors:
                meta.authors = authors
                meta.source["authors"] = "docling_heuristic"

        if meta.institute is None:
            institute = self._guess_institute(lines)
            if institute:
                meta.institute = institute
                meta.source["institute"] = "docling_heuristic"

    def _first_section_header(self, doc: DoclingDocument) -> Optional[str]:
        for node, _ in doc.iterate_items():
            if isinstance(node, SectionHeaderItem):
                t = (node.text or "").strip()
                if self._looks_like_title(t):
                    return t
        return None

    def _first_lines(self, doc: DoclingDocument, *, limit: int) -> List[str]:
        out: List[str] = []
        for node, _ in doc.iterate_items():
            if isinstance(node, (SectionHeaderItem, TextItem)):
                t = (node.text or "").strip()
                if not t:
                    continue
                for ln in t.splitlines():
                    ln = ln.strip()
                    if ln:
                        out.append(ln)
                        if len(out) >= limit:
                            return out
        return out

    def _first_reasonable_line(self, lines: List[str]) -> Optional[str]:
        for ln in lines[:30]:
            if self._looks_like_title(ln):
                return ln
        return None

    def _looks_like_title(self, s: str) -> bool:
        s = s.strip()
        if len(s) < 8:
            return False
        if "@" in s:
            return False
        if len(s.split()) < 2:
            return False
        if re.fullmatch(r"[\W\d_]+", s):
            return False
        # avoid obvious section markers
        if s.lower() in {"abstract", "samenvatting", "summary", "inhoud", "contents"}:
            return False
        return True

    def _guess_authors(self, lines: List[str]) -> Optional[List[str]]:
        # very conservative: name-like patterns near top, avoid emails
        for ln in lines[:25]:
            if "@" in ln:
                continue
            low = ln.lower()
            if low.startswith(("abstract", "samenvatting", "summary", "inhoud", "contents")):
                continue

            # "Alice Smith, Bob Jones" / "Alice Smith • Bob Jones"
            if re.search(r"[•;,]", ln) and re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", ln):
                parts = re.split(r"[•;,]\s*", ln)
                names = [
                    p.strip()
                    for p in parts
                    if re.fullmatch(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", p.strip())
                ]
                if names:
                    return names

            # single full name line
            if re.fullmatch(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", ln) and len(ln.split()) <= 4:
                return [ln.strip()]

        return None

    def _guess_institute(self, lines: List[str]) -> Optional[str]:
        for ln in lines[:40]:
            if "@" in ln:
                continue
            low = ln.lower()
            if any(k in low for k in self._AFFIL_KWS):
                return ln.strip()
        return None
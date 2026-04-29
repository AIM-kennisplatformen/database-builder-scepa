from __future__ import annotations

import json
import re
from typing import Any, Optional

from docling_core.types.doc.document import SectionHeaderItem, TextItem
from pypdf import PdfReader

from .text_metadata import TextMetadata, Acknowledgement
from database_builder_libs.utility.extract.document_parser_docling import ParsedDocument


FIRST_LINES_LIMIT = 120
HEADER_SCAN_LIMIT = 10
LLM_HEADER_LINES = 60
SUMMARY_SECTION_LIMIT = 4
TITLE_MIN_LENGTH = 8
TITLE_MIN_WORDS = 2
PDF_METADATA_JUNK = {"unknown", "untitled", "microsoft word", "writer", "author"}

LLM_PROMPT_TEMPLATE = """
Extract metadata from the document header.

Return JSON.

{{
"authors": ["First Last"],
"acknowledgements": [
{{
"name": "Entity",
"type": "person | organization | group",
"relation": "funding | collaboration | contribution | review | support"
}}
]
}}

Rules:

- Authors must be personal names.
- Ignore job titles.
- Ignore copyright text.
- Extract acknowledgement entities.

Text:
{text}
"""


class TextMetadataExtractor:
    """Extracts metadata from a document using heuristics, PDF metadata, and optional LLM enrichment."""

    _SUMMARY_HEADERS = (
        "abstract",
        "summary",
        "executive summary",
        "samenvatting",
    )

    def __init__(
        self, *, llm_client: Any | None = None, llm_model: str = "gpt-4.1-mini"
    ):
        self.llm_client = llm_client
        self.llm_model = llm_model

    def extract(
        self,
        *,
        pdf_path: str,
        doc: ParsedDocument,
        meta: Optional[TextMetadata] = None,
    ) -> TextMetadata:
        meta = meta or TextMetadata(source={})

        self._fill_from_pdf_metadata(meta, pdf_path)

        lines = self._first_lines(doc.doc, limit=FIRST_LINES_LIMIT)

        if meta.title is None:
            title = self._first_section_header(doc.doc) or self._first_reasonable_line(
                lines
            )

            if title:
                meta.title = title
                meta.source.setdefault("title", "docling_heuristic")

        if self.llm_client:
            authors, acknowledgements = self._extract_llm(lines)

            if meta.authors is None and authors:
                meta.authors = authors
                meta.source.setdefault("authors", "llm")

            if not meta.acknowledgements and acknowledgements:
                meta.acknowledgements = acknowledgements
                meta.source.setdefault("acknowledgements", "llm")

        if meta.summary is None:
            summary = self._find_summary(doc.doc)

            if summary:
                meta.summary = summary
                meta.source.setdefault("summary", "docling_heuristic")

        if meta.authors is None:
            for line in lines[:HEADER_SCAN_LIMIT]:
                parsed = self.parse_author_line(line)

                if len(parsed) >= 2:
                    meta.authors = parsed
                    meta.source["authors"] = "header_pattern"
                    break

        return meta

    def _fill_from_pdf_metadata(self, meta: TextMetadata, pdf_path: str) -> None:
        """Populate metadata fields from embedded PDF metadata."""

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

    def parse_author_line(self, text: str) -> list[str]:
        """Parse abbreviated author lines like 'Smith J., Doe A.'."""

        text = text.replace(" and ", ",")
        parts = [p.strip() for p in text.split(",") if p.strip()]

        authors = []
        pattern = re.compile(r"^([A-Z][a-zA-Z\-']+)\s+([A-Z])\.?$")

        for part in parts:
            m = pattern.match(part)

            if m:
                last, initial = m.groups()
                authors.append(f"{initial} {last}")

        return authors

    def _extract_llm(
        self, lines: list[str]
    ) -> tuple[list[str] | None, list[Acknowledgement]]:
        """Use an LLM to extract authors and acknowledgement entities."""

        assert self.llm_client is not None
        text = "\n".join(lines[:LLM_HEADER_LINES])
        prompt = LLM_PROMPT_TEMPLATE.format(text=text)

        try:
            res = self.llm_client.chat.completions.create(
                model=self.llm_model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )

            content = res.choices[0].message.content.strip()
            match = re.search(r"\{.*\}", content, re.S)

            if not match:
                return None, []

            data = json.loads(match.group(0))

            acknowledgements = []

            for a in data.get("acknowledgements", []):
                acknowledgements.append(
                    Acknowledgement(
                        name=a.get("name"),
                        type=a.get("type"),
                        relation=a.get("relation"),
                    )
                )

            return data.get("authors"), acknowledgements

        except Exception:
            return None, []

    def _find_summary(self, doc) -> str | None:
        """Extract the summary/abstract section from the document."""

        collecting = False
        collected = []

        for node, _ in doc.iterate_items():
            if isinstance(node, SectionHeaderItem):
                h = (node.text or "").strip().lower()

                if any(k in h for k in self._SUMMARY_HEADERS):
                    collecting = True
                    continue

                if collecting:
                    break

            if collecting and isinstance(node, TextItem):
                t = (node.text or "").strip()

                if t:
                    collected.append(t)

        if collected:
            return "\n".join(collected[:SUMMARY_SECTION_LIMIT])

        return None

    def _first_lines(self, doc, limit: int) -> list[str]:
        """Return the first N textual lines from the document."""

        out = []

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

    def _first_section_header(self, doc) -> str | None:
        """Return the first section header that looks like a title."""

        for node, _ in doc.iterate_items():
            if isinstance(node, SectionHeaderItem):
                t = (node.text or "").strip()

                if self._looks_like_title(t):
                    return t

        return None

    def _first_reasonable_line(self, lines: list[str]) -> str | None:
        """Return the first line that plausibly looks like a title."""

        for ln in lines[: HEADER_SCAN_LIMIT * 3]:
            if self._looks_like_title(ln):
                return ln

        return None

    def _looks_like_title(self, s: str) -> bool:
        """Heuristic to determine if a string resembles a title."""

        if len(s) < TITLE_MIN_LENGTH:
            return False

        if "@" in s:
            return False

        if len(s.split()) < TITLE_MIN_WORDS:
            return False

        return True

    def _clean_pdf_meta_string(self, value: Any) -> str | None:
        """Clean noisy strings from PDF metadata."""

        if value is None:
            return None

        s = str(value).strip()

        if not s:
            return None

        if s.lower() in PDF_METADATA_JUNK:
            return None

        return s

    def _split_authors(self, s: str) -> list[str]:
        """Split author lists into individual names."""

        if ";" in s:
            parts = [p.strip() for p in s.split(";")]
        elif re.search(r"\band\b", s, flags=re.I):
            parts = [p.strip() for p in re.split(r"\band\b", s, flags=re.I)]
        else:
            parts = [s.strip()]

        return [p for p in parts if p]

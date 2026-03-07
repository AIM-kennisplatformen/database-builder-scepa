from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List
import json
import re

from docling_core.types.doc import DoclingDocument, SectionHeaderItem, TextItem
from pypdf import PdfReader


@dataclass(slots=True)
class Institution:
    name: str
    parent: Optional[str] = None


@dataclass(slots=True)
class Acknowledgement:
    name: str
    type: str
    relation: str


@dataclass(slots=True)
class TextMetadata:
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    institutions: List[Institution] = field(default_factory=list)
    summary: Optional[str] = None
    acknowledgements: List[Acknowledgement] = field(default_factory=list)
    source: dict[str, str] = field(default_factory=dict)


class TextMetadataExtractor:

    _SUMMARY_HEADERS = (
        "abstract",
        "summary",
        "executive summary",
        "samenvatting",
    )

    def __init__(self, *, llm_client=None, llm_model="gpt-4.1-mini"):
        self.llm_client = llm_client
        self.llm_model = llm_model

    # ─────────────────────────────────────────────

    def extract(self, *, pdf_path: str, doc: DoclingDocument) -> TextMetadata:

        meta = TextMetadata(source={})

        self._fill_from_pdf_metadata(meta, pdf_path)

        lines = self._first_lines(doc, limit=120)

        if meta.title is None:

            title = self._first_section_header(doc) or self._first_reasonable_line(lines)

            if title:
                meta.title = title
                meta.source["title"] = "docling_heuristic"

        if self.llm_client:

            authors, institutions, acknowledgements = self._extract_llm(lines)

            if authors:
                meta.authors = authors
                meta.source["authors"] = "llm"

            if institutions:
                meta.institutions = institutions
                meta.source["institutions"] = "llm"

            if acknowledgements:
                meta.acknowledgements = acknowledgements
                meta.source["acknowledgements"] = "llm"

        summary = self._find_summary(doc)

        if summary:
            meta.summary = summary
            meta.source["summary"] = "docling_heuristic"

        return meta

    # ─────────────────────────────────────────────
    # PDF metadata
    # ─────────────────────────────────────────────

    def _fill_from_pdf_metadata(self, meta: TextMetadata, pdf_path: str):

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

    # ─────────────────────────────────────────────
    # LLM extraction
    # ─────────────────────────────────────────────

    def _extract_llm(self, lines):

        assert self.llm_client is not None
        text = "\n".join(lines[:60])

        prompt = f"""
Extract metadata from the document header.

Return JSON.

{{
  "authors": ["First Last"],
  "institutions": [
    {{
      "name": "Institution Name",
      "parent": "Parent Institution or null"
    }}
  ],
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
- Institutions should include research centers and universities.
- If one institution belongs to another, use parent.
- Ignore copyright text.
- Extract acknowledgement entities.

Text:
{text}
"""

        try:

            res = self.llm_client.chat.completions.create(
                model=self.llm_model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )

            content = res.choices[0].message.content.strip()

            match = re.search(r"\{.*\}", content, re.S)

            if not match:
                return None, None, []

            data = json.loads(match.group(0))

            institutions = []

            for inst in data.get("institutions", []):
                institutions.append(
                    Institution(
                        name=inst.get("name"),
                        parent=inst.get("parent"),
                    )
                )

            acknowledgements = []

            for a in data.get("acknowledgements", []):

                acknowledgements.append(
                    Acknowledgement(
                        name=a.get("name"),
                        type=a.get("type"),
                        relation=a.get("relation"),
                    )
                )

            return (
                data.get("authors"),
                institutions,
                acknowledgements,
            )

        except Exception:
            return None, None, []

    # ─────────────────────────────────────────────
    # Summary extraction
    # ─────────────────────────────────────────────

    def _find_summary(self, doc):

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
            return "\n".join(collected[:4])

        return None

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _first_lines(self, doc, limit):

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

    def _first_section_header(self, doc):

        for node, _ in doc.iterate_items():

            if isinstance(node, SectionHeaderItem):

                t = (node.text or "").strip()

                if self._looks_like_title(t):
                    return t

        return None

    def _first_reasonable_line(self, lines):

        for ln in lines[:30]:

            if self._looks_like_title(ln):
                return ln

        return None

    def _looks_like_title(self, s):

        if len(s) < 8:
            return False

        if "@" in s:
            return False

        if len(s.split()) < 2:
            return False

        return True

    def _clean_pdf_meta_string(self, value):

        if value is None:
            return None

        s = str(value).strip()

        if not s:
            return None

        junk = {"unknown", "untitled", "microsoft word", "writer", "author"}

        if s.lower() in junk:
            return None

        return s

    def _split_authors(self, s: str) -> List[str]:
        if ";" in s:
            parts = [p.strip() for p in s.split(";")]
        elif re.search(r"\band\b", s, flags=re.I):
            parts = [p.strip() for p in re.split(r"\band\b", s, flags=re.I)]
        else:
            parts = [s.strip()]

        return [p for p in parts if p]
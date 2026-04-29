from __future__ import annotations

from typing import Any, List, Optional, TypedDict

from .text_metadata import Institution, TextMetadata


LITERATURE_TYPES = {"report", "policy brief", "thesis", "article"}

TAG_PREFIX_MAP = {
    "strategy:": "strategic_overview",
    "target:": "target_groups",
    "practice:": "best_practices",
}

INSTITUTION_HINTS = {
    "university",
    "institute",
    "research",
    "centre",
    "center",
    "group",
    "foundation",
    "association",
    "agency",
    "organisation",
    "organization",
    "network",
}


class KeywordExtraction(TypedDict):
    keywords: list[str] | None
    literature_type: str | None
    strategic_overview: list[str] | None
    target_groups: list[str] | None
    best_practices: list[str] | None


class ZoteroMetadataExtractor:
    """Extract metadata from Zotero API entries."""

    def extract(self, *, zotero_entry: dict[str, Any]) -> TextMetadata:
        """Convert a Zotero entry into a TextMetadata object."""

        meta = TextMetadata(source={})
        data: dict[str, Any] = zotero_entry.get("data", {})

        if title := data.get("title"):
            meta.title = title
            meta.source["title"] = "zotero"

        if authors := self._extract_authors(data):
            meta.authors = authors
            meta.source["authors"] = "zotero"

        tags = self._extract_keywords(data)

        if tags["keywords"]:
            meta.keywords = tags["keywords"]

        if tags["literature_type"]:
            meta.literature_type = tags["literature_type"]

        if tags["strategic_overview"]:
            meta.strategic_overview = tags["strategic_overview"]

        if tags["target_groups"]:
            meta.target_groups = tags["target_groups"]

        if tags["best_practices"]:
            meta.best_practices = tags["best_practices"]

        if summary := data.get("abstractNote"):
            meta.summary = summary
            meta.source["summary"] = "zotero"

        if publisher := data.get("publisher"):
            meta.publishing_institute = Institution(name=publisher)
            meta.source["publishing_institute"] = "zotero"

        if key := zotero_entry.get("key"):
            meta.source["zotero_key"] = key

        if library := zotero_entry.get("library", {}).get("name"):
            meta.source["zotero_library"] = library

        return meta

    def _extract_authors(self, data: dict[str, Any]) -> List[str]:
        """Extract personal authors from Zotero creators."""

        authors: list[str] = []

        for creator in data.get("creators", []):
            if creator.get("creatorType") != "author":
                continue

            name: Optional[str]

            if creator.get("name"):
                name = creator["name"]

                if name and self._is_institution_name(name):
                    continue
            else:
                first = creator.get("firstName", "")
                last = creator.get("lastName", "")
                name = f"{first} {last}".strip()

            if name:
                authors.append(name)

        return authors

    def _extract_keywords(self, data: dict[str, Any]) -> KeywordExtraction:
        """Extract structured keyword information from Zotero tags."""

        keywords: list[str] = []
        strategic: list[str] = []
        targets: list[str] = []
        practices: list[str] = []
        literature_type: str | None = None

        for tag in data.get("tags", []):
            if not isinstance(tag, dict):
                continue

            value = tag.get("tag")
            if not value:
                continue

            t = value.lower()

            if t in LITERATURE_TYPES:
                literature_type = value
                continue

            for prefix, field in TAG_PREFIX_MAP.items():
                if t.startswith(prefix):
                    cleaned = value[len(prefix) :].strip()

                    if field == "strategic_overview":
                        strategic.append(cleaned)
                    elif field == "target_groups":
                        targets.append(cleaned)
                    elif field == "best_practices":
                        practices.append(cleaned)

                    break
            else:
                keywords.append(value)

        return {
            "keywords": keywords or None,
            "literature_type": literature_type,
            "strategic_overview": strategic or None,
            "target_groups": targets or None,
            "best_practices": practices or None,
        }

    def _is_institution_name(self, name: str) -> bool:
        """Heuristic to filter out institutional authors."""

        n = name.lower()
        return any(k in n for k in INSTITUTION_HINTS)

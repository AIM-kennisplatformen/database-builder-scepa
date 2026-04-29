from dataclasses import dataclass, field
from typing import Optional


MetadataSource = dict[str, str]


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
    authors: list[str] | None = None
    publishing_institute: Optional[Institution] = None
    summary: Optional[str] = None

    acknowledgements: list[Acknowledgement] = field(default_factory=list)

    source: MetadataSource = field(default_factory=dict)

    keywords: list[str] | None = None

    literature_type: Optional[str] = None
    strategic_overview: list[str] | None = None
    target_groups: list[str] | None = None
    best_practices: list[str] | None = None

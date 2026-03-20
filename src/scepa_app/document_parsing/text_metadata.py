from dataclasses import dataclass, field
from typing import Optional, List



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
    publishing_institute: Optional[Institution] = None
    summary: Optional[str] = None

    acknowledgements: List[Acknowledgement] = field(default_factory=list)

    source: dict[str, str] = field(default_factory=dict)

    keywords: Optional[List[str]] = None

    literature_type: Optional[str] = None
    strategic_overview: Optional[List[str]] = None
    target_groups: Optional[List[str]] = None
    best_practices: Optional[List[str]] = None
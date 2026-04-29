from __future__ import annotations

import hashlib
from typing import Any, Iterable

from database_builder_libs.models.abstract_source import Content
from database_builder_libs.models.node import EntityType, KeyAttribute, Node, NodeId


NOISE_TERMS = {
    "interviewees",
    "participants",
    "attendees",
    "reviewers",
    "respondents",
    "community members",
    "staff",
    "team",
    "students",
    "focus group",
    "focus groups",
    "survey participants",
}

KEYWORD_DOC_TYPES = {
    "scientific literature": "discriminatingconcept-bol-scientific",
    "survey": "discriminatingconcept-bol-surveys",
    "project report": "discriminatingconcept-bol-projectreports",
}

KEYWORD_FUNCTIONS = {
    "best practice": "best-practices",
    "best practices": "best-practices",
    "strategic overview": "strategic-overview",
    "target group": "target-groups",
    "target groups": "target-groups",
}

AUTHORSHIP_RELATION = "authorship"
SCIENTIFIC_RELATION = "discriminatingconcept-bol-scientific"
GREY_LITERATURE_RELATION = "discriminatingconcept-bol-greyliterature"
TEXTDOCUMENT_ENTITY = "textdocument"
PERSON_ENTITY = "person"
PUBLISHING_INSTITUTION_ENTITY = "publishinginstitution"
PERSON_KEY_ATTR = "person-key"
NAME_KEY_ATTR = "namelike-name"
HASH_KEY_ATTR = "hashvalue"


class MetadataNodeExporter:
    def export(
        self, content_list: Iterable[Content], doc_hash: str | None = None
    ) -> list[Node]:
        nodes: dict[str, Node] = {}

        for content in content_list:
            meta = content.content.get("metadata", {})
            current_hash = doc_hash or self._hash(meta)
            relations: list[dict[str, object]] = []

            for author in meta.get("authors") or []:
                key = self._person_key(author)
                nodes.setdefault(key, self._person_node(author))
                relations.append(
                    {
                        "type": AUTHORSHIP_RELATION,
                        "roles": {
                            "author": {
                                "entity_type": PERSON_ENTITY,
                                "key_attr": PERSON_KEY_ATTR,
                                "key": key,
                            },
                            "authoredwork": {
                                "entity_type": TEXTDOCUMENT_ENTITY,
                                "key_attr": HASH_KEY_ATTR,
                                "key": current_hash,
                            },
                        },
                        "attributes": {
                            "authorship-id": hashlib.sha256(
                                f"{key}|{current_hash}".encode()
                            ).hexdigest()
                        },
                    }
                )

            for ack in meta.get("acknowledgements") or []:
                name = ack.get("name", "")
                if self._is_noise(name):
                    continue

                nodes.setdefault(name, self._institution_node(name))
                relations.append(
                    {
                        "type": SCIENTIFIC_RELATION,
                        "roles": {
                            "attributedto": {
                                "entity_type": PUBLISHING_INSTITUTION_ENTITY,
                                "key_attr": NAME_KEY_ATTR,
                                "key": name,
                            },
                            "attributedthing": {
                                "entity_type": TEXTDOCUMENT_ENTITY,
                                "key_attr": HASH_KEY_ATTR,
                                "key": current_hash,
                            },
                        },
                        "attributes": {"function": ack.get("relation")},
                    }
                )

            doc_type = None
            semantic_functions: set[str] = set()

            for tag in meta.get("keywords") or []:
                normalized = self._normalize(tag)
                for keyword, dtype in KEYWORD_DOC_TYPES.items():
                    if keyword in normalized:
                        doc_type = dtype
                for keyword, func in KEYWORD_FUNCTIONS.items():
                    if keyword in normalized:
                        semantic_functions.add(func)

            for func in semantic_functions:
                relations.append(
                    {
                        "type": SCIENTIFIC_RELATION,
                        "roles": {
                            "attributedthing": {
                                "entity_type": TEXTDOCUMENT_ENTITY,
                                "key_attr": HASH_KEY_ATTR,
                                "key": current_hash,
                            }
                        },
                        "attributes": {"function": func},
                    }
                )

            if doc_type is None:
                if meta.get("keywords"):
                    doc_type = SCIENTIFIC_RELATION
                elif meta.get("acknowledgements"):
                    doc_type = GREY_LITERATURE_RELATION

            if doc_type:
                relations.append(
                    {
                        "type": doc_type,
                        "roles": {
                            "attributedthing": {
                                "entity_type": TEXTDOCUMENT_ENTITY,
                                "key_attr": HASH_KEY_ATTR,
                                "key": current_hash,
                            }
                        },
                    }
                )

            nodes[current_hash] = Node(
                id=NodeId(current_hash),
                entity_type=EntityType(TEXTDOCUMENT_ENTITY),
                key_attribute=KeyAttribute(HASH_KEY_ATTR),
                payload_data={"namelike-title": meta.get("title")}
                if meta.get("title")
                else {},
                relations=tuple(relations),
            )

        return list(nodes.values())

    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def _person_key(self, name: str) -> str:
        return name.strip().lower().replace(" ", "_")

    def _is_noise(self, name: str) -> bool:
        normalized = name.lower()
        return len(normalized) < 3 or any(term in normalized for term in NOISE_TERMS)

    def _hash(self, meta: dict[str, Any]) -> str:
        parts = [
            meta.get("title") or "",
            ",".join(meta.get("authors") or []),
            meta.get("summary") or "",
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _person_node(self, name: str) -> Node:
        key = self._person_key(name)
        if "," in name:
            last, _, first = name.partition(",")
            payload = {"namelike-first": first.strip(), "namelike-last": last.strip()}
        else:
            parts = name.split(" ", 1)
            payload = {"namelike-first": parts[0]}
            if len(parts) == 2:
                payload["namelike-last"] = parts[1]

        return Node(
            id=NodeId(key),
            entity_type=EntityType(PERSON_ENTITY),
            key_attribute=KeyAttribute(PERSON_KEY_ATTR),
            payload_data=payload,
            relations=(),
        )

    def _institution_node(self, name: str) -> Node:
        return Node(
            id=NodeId(name),
            entity_type=EntityType(PUBLISHING_INSTITUTION_ENTITY),
            key_attribute=KeyAttribute(NAME_KEY_ATTR),
            payload_data={"namelike-name": name},
            relations=(),
        )

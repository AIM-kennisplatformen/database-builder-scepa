from __future__ import annotations

import hashlib
from typing import Iterable, List, Dict, Any

from database_builder_libs.models.node import (
    Node,
    NodeId,
    EntityType,
    KeyAttribute,
)

from database_builder_libs.models.abstract_source import Content


class MetadataNodeExporter:

    NOISE_TERMS = {
        "interviewees","participants","attendees","reviewers",
        "respondents","community members","staff","team",
        "students","focus group","focus groups","survey participants",
    }

    # ─────────────────────────────────────────────
    # KEYWORD MAPPINGS
    # ─────────────────────────────────────────────

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

    # ─────────────────────────────────────────────
    # MAIN EXPORT
    # ─────────────────────────────────────────────

    def export(self, content_list: Iterable[Content], doc_hash: str | None = None) -> List[Node]:

        nodes: Dict[str, Node] = {}

        for content in content_list:

            meta: dict[str, Any] = content.content.get("metadata", {})

            # Use provided hash or compute from metadata
            if doc_hash is None:
                doc_hash = self._hash(meta)
            relations = []

            # ───────── AUTHORS

            for author in meta.get("authors") or []:

                key = self._person_key(author)
                nodes.setdefault(key, self._person_node(author))

                relations.append({
                    "type": "authorship",
                    "roles": {
                        "author": {
                            "entity_type": "person",
                            "key_attr": "person-key",
                            "key": key,
                        },
                        "authoredwork": {
                            "entity_type": "textdocument",
                            "key_attr": "hashvalue",
                            "key": doc_hash,
                        },
                    },
                    "attributes": {
                        "authorship-id": hashlib.sha256(
                            f"{key}|{doc_hash}".encode()
                        ).hexdigest()
                    },
                })

            # ───────── ACKNOWLEDGEMENTS

            for ack in meta.get("acknowledgements") or []:

                name = ack.get("name", "")

                if self._is_noise(name):
                    continue

                nodes.setdefault(
                    name,
                    self._institution_node(name)
                )

                relations.append({
                    "type": "discriminatingconcept-bol-scientific",
                    "roles": {
                        "attributedto": {
                            "entity_type": "publishinginstitution",
                            "key_attr": "namelike-name",
                            "key": name,
                        },
                        "attributedthing": {
                            "entity_type": "textdocument",
                            "key_attr": "hashvalue",
                            "key": doc_hash,
                        },
                    },
                    "attributes": {
                        "function": ack.get("relation")
                    }
                })

            # ───────── KEYWORD PROCESSING

            doc_type = None
            semantic_functions = set()

            for tag in meta.get("keywords") or []:

                t = self._normalize(tag)

                # detect document type
                for keyword, dtype in self.KEYWORD_DOC_TYPES.items():
                    if keyword in t:
                        doc_type = dtype

                # detect semantic classification
                for keyword, func in self.KEYWORD_FUNCTIONS.items():
                    if keyword in t:
                        semantic_functions.add(func)

            # add semantic relations
            for func in semantic_functions:

                relations.append({
                    "type": "discriminatingconcept-bol-scientific",
                    "roles": {
                        "attributedthing": {
                            "entity_type": "textdocument",
                            "key_attr": "hashvalue",
                            "key": doc_hash,
                        }
                    },
                    "attributes": {
                        "function": func
                    }
                })

            # ───────── FALLBACK CLASSIFICATION

            if doc_type is None:

                if meta.get("keywords"):
                    doc_type = "discriminatingconcept-bol-scientific"

                elif meta.get("acknowledgements"):
                    doc_type = "discriminatingconcept-bol-greyliterature"

            if doc_type:

                relations.append({
                    "type": doc_type,
                    "roles": {
                        "attributedthing": {
                            "entity_type": "textdocument",
                            "key_attr": "hashvalue",
                            "key": doc_hash,
                        }
                    }
                })

            # ───────── DOCUMENT NODE

            nodes[doc_hash] = Node(
                id=NodeId(doc_hash),
                entity_type=EntityType("textdocument"),
                key_attribute=KeyAttribute("hashvalue"),
                payload_data={
                    "namelike-title": meta.get("title")
                } if meta.get("title") else {},
                relations=tuple(relations),
            )

        return list(nodes.values())

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def _person_key(self, name: str) -> str:
        return name.strip().lower().replace(" ", "_")

    def _is_noise(self, name: str) -> bool:
        n = name.lower()
        return len(n) < 3 or any(term in n for term in self.NOISE_TERMS)

    def _hash(self, meta: dict[str, Any]) -> str:

        parts = [
            meta.get("title") or "",
            ",".join(meta.get("authors") or []),
            meta.get("summary") or "",
        ]

        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    # ─────────────────────────────────────────────
    # NODE BUILDERS
    # ─────────────────────────────────────────────

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
            entity_type=EntityType("person"),
            key_attribute=KeyAttribute("person-key"),
            payload_data=payload,
            relations=(),
        )

    def _institution_node(self, name: str) -> Node:

        return Node(
            id=NodeId(name),
            entity_type=EntityType("publishinginstitution"),
            key_attribute=KeyAttribute("namelike-name"),
            payload_data={"namelike-name": name},
            relations=(),
        )
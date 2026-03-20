from __future__ import annotations

import hashlib
from typing import Iterable, List, Dict

from database_builder_libs.models.node import (
    Node,
    NodeId,
    EntityType,
    KeyAttribute,
)

from ..document_parsing.text_metadata import TextMetadata


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

    def export(self, metadata_list: Iterable[TextMetadata]) -> List[Node]:

        nodes: Dict[str, Node] = {}

        for meta in metadata_list:

            doc_hash = self._hash(meta)
            relations = []

            # ───────── AUTHORS

            for author in meta.authors or []:

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

            for ack in meta.acknowledgements or []:

                if self._is_noise(ack.name):
                    continue

                nodes.setdefault(
                    ack.name,
                    self._institution_node(ack.name)
                )

                relations.append({
                    "type": "discriminatingconcept-bol-scientific",
                    "roles": {
                        "attributedto": {
                            "entity_type": "publishinginstitution",
                            "key_attr": "namelike-name",
                            "key": ack.name,
                        },
                        "attributedthing": {
                            "entity_type": "textdocument",
                            "key_attr": "hashvalue",
                            "key": doc_hash,
                        },
                    },
                    "attributes": {
                        "function": ack.relation
                    }
                })

            # ───────── KEYWORD PROCESSING

            doc_type = None
            semantic_functions = set()

            for tag in meta.keywords or []:

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

                if meta.keywords:
                    doc_type = "discriminatingconcept-bol-scientific"

                elif meta.acknowledgements:
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
                    "namelike-title": meta.title
                } if meta.title else {},
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

    def _hash(self, meta: TextMetadata) -> str:

        parts = [
            meta.title or "",
            ",".join(meta.authors or []),
            meta.summary or "",
        ]

        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    # ─────────────────────────────────────────────
    # NODE BUILDERS
    # ─────────────────────────────────────────────

    def _person_node(self, name: str) -> Node:

        key = self._person_key(name)
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
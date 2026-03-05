from __future__ import annotations

import hashlib
from typing import Iterable, List, Dict

from database_builder_libs.models.node import (
    Node,
    NodeId,
    EntityType,
    KeyAttribute,
)

from ..document_parsing.extraction.extract_text_metadata import TextMetadata


class MetadataNodeExporter:

    def export(self, metadata_list: Iterable[TextMetadata]) -> List[Node]:
        nodes: Dict[str, Node] = {}

        for meta in metadata_list:

            doc_hash = self._compute_hash(meta)

            relations = []

            if meta.authors:
                for author in meta.authors:
                    person_node = self._build_person_node(author)

                    nodes.setdefault(person_node.id, person_node)

                    relations.append(
                        self._build_authorship_relation(author, doc_hash)
                    )
            if meta.institute:

                institute_node = self._build_institution_node(meta.institute)

                nodes.setdefault(str(institute_node.id), institute_node)

                relations.append(
                    self._build_attribution_relation(meta.institute, doc_hash)
                )
            document_node = self._build_document_node(
                meta,
                doc_hash,
                tuple(relations),
            )

            nodes[document_node.id] = document_node

        return list(nodes.values())

    def _build_institution_node(self, institute: str) -> Node:

        key = institute

        return Node(
            id=NodeId(key),
            entity_type=EntityType("publishinginstitution"),
            key_attribute=KeyAttribute("namelike-name"),
            payload_data={
                "namelike-name": institute
            },
            relations=(),
        )
    def _build_attribution_relation(self, institute: str, doc_hash: str):

        return {
            "type": "discriminatingconcept-bol-greyliterature",
            "roles": {
                "attributedto": {
                    "entity_type": "publishinginstitution",
                    "key_attr": "namelike-name",
                    "key": institute,
                },
                "attributedthing": {
                    "entity_type": "textdocument",
                    "key_attr": "hashvalue",
                    "key": doc_hash,
                },
            },
        }
    def _build_document_node(
        self,
        meta: TextMetadata,
        doc_hash: str,
        relations: tuple,
    ) -> Node:

        payload = {}

        if meta.title:
            payload["namelike-title"] = meta.title

        return Node(
            id=NodeId(doc_hash),
            entity_type=EntityType("textdocument"),
            key_attribute=KeyAttribute("hashvalue"),
            payload_data=payload,
            relations=relations,
        )
    def _build_person_node(self, name: str) -> Node:
        key = self._normalize_person_key(name)

        parts = name.strip().split(" ", 1)

        payload = {}

        if len(parts) == 2:
            payload["namelike-first"] = parts[0]
            payload["namelike-last"] = parts[1]
        else:
            payload["namelike-first"] = name

        return Node(
            id=NodeId(key),
            entity_type=EntityType("person"),
            key_attribute=KeyAttribute("person-key"),
            payload_data=payload,
            relations=(),
        )

    def _build_authorship_relation(self, author: str, doc_hash: str) -> dict:
        person_key = self._normalize_person_key(author)

        # deterministic relation id
        rel_id = hashlib.sha256(
            f"{person_key}|{doc_hash}".encode()
        ).hexdigest()

        return {
            "type": "authorship",
            "roles": {
                "author": {
                    "entity_type": "person",
                    "key_attr": "person-key",
                    "key": person_key,
                },
                "authoredwork": {
                    "entity_type": "textdocument",
                    "key_attr": "hashvalue",
                    "key": doc_hash,
                },
            },
            "attributes": {
                "authorship-id": rel_id
            },
        }

    def _compute_hash(self, meta: TextMetadata) -> str:
        basis = "|".join(
            [
                meta.title or "",
                ",".join(meta.authors or []),
                meta.institute or "",
            ]
        )

        return hashlib.sha256(basis.encode()).hexdigest()

    def _normalize_person_key(self, name: str) -> str:
        return name.strip().lower().replace(" ", "_")
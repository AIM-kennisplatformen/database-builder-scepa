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
     
    def _is_noise_ack(self, name: str) -> bool:
        n = name.lower()

        if len(n) < 3:
            return True

        for term in self.NOISE_TERMS:
            if term in n:
                return True

        return False

    def export(self, metadata_list: Iterable[TextMetadata]) -> List[Node]:

        nodes: Dict[str, Node] = {}

        for meta in metadata_list:

            doc_hash = self._compute_hash(meta)

            relations = []

            # ─────────────────────────────
            # AUTHORS
            # ─────────────────────────────

            if meta.authors:
                for author in meta.authors:

                    person_node = self._build_person_node(author)
                    nodes.setdefault(person_node.id, person_node)

                    relations.append(
                        self._build_authorship_relation(author, doc_hash)
                    )

            # ─────────────────────────────
            # INSTITUTIONS
            # ─────────────────────────────

            if meta.institutions:

                for inst in meta.institutions:

                    inst_node = self._build_institution_node(inst.name)
                    nodes.setdefault(str(inst_node.id), inst_node)

                    relations.append(
                        self._build_attribution_relation(inst.name, doc_hash)
                    )

                    # hierarchy relation
                    if inst.parent:

                        parent_node = self._build_institution_node(inst.parent)
                        nodes.setdefault(str(parent_node.id), parent_node)

                        relations.append(
                            self._build_part_of_relation(inst.name, inst.parent)
                        )

            # ─────────────────────────────
            # ACKNOWLEDGEMENTS
            # ─────────────────────────────

            # ─────────────────────────────
            # ACKNOWLEDGEMENTS
            # ─────────────────────────────

            if meta.acknowledgements:

                for ack in meta.acknowledgements:
                    if self._is_noise_ack(ack.name):
                        continue
                    if ack.type == "person":

                        person_node = self._build_person_node(ack.name)
                        nodes.setdefault(str(person_node.id), person_node)

                        entity_type = "person"
                        key_attr = "person-key"
                        key = self._normalize_person_key(ack.name)

                    else:

                        inst_node = self._build_institution_node(ack.name)
                        nodes.setdefault(str(inst_node.id), inst_node)

                        entity_type = "publishinginstitution"
                        key_attr = "namelike-name"
                        key = ack.name

                    # attribution relation (must use concrete subtype)
                    relations.append({
                        "type": "discriminatingconcept-bol-greyliterature",
                        "roles": {
                            "attributedto": {
                                "entity_type": entity_type,
                                "key_attr": key_attr,
                                "key": key,
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

                    # funding detection
                    if ack.relation == "funding" and meta.institutions:

                        relations.append({
                            "type": "funding-external",
                            "roles": {
                                "subsidyprovider": {
                                    "entity_type": "institution",
                                    "key_attr": "namelike-name",
                                    "key": ack.name,
                                },
                                "recipient-institute": {
                                    "entity_type": "institution",
                                    "key_attr": "namelike-name",
                                    "key": meta.institutions[0].name,
                                }
                            }
                        })

            # ─────────────────────────────
            # DOCUMENT
            # ─────────────────────────────

            document_node = self._build_document_node(
                meta,
                doc_hash,
                tuple(relations),
            )

            nodes[document_node.id] = document_node

        return list(nodes.values())
    # ─────────────────────────────────────────────
    # Institution node
    # ─────────────────────────────────────────────

    def _build_institution_node(self, institute: str) -> Node:

        return Node(
            id=NodeId(institute),
            entity_type=EntityType("publishinginstitution"),
            key_attribute=KeyAttribute("namelike-name"),
            payload_data={
                "namelike-name": institute
            },
            relations=(),
        )

    # ─────────────────────────────────────────────
    # Document attribution
    # ─────────────────────────────────────────────

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

    # ─────────────────────────────────────────────
    # Institution hierarchy
    # ─────────────────────────────────────────────

    def _build_part_of_relation(self, child: str, parent: str):

        return {
            "type": "composition-organizational",
            "roles": {
                "organizationalunit": {
                    "entity_type": "publishinginstitution",
                    "key_attr": "namelike-name",
                    "key": child,
                },
                "overarchingunit": {
                    "entity_type": "publishinginstitution",
                    "key_attr": "namelike-name",
                    "key": parent,
                },
            },
        }

    # ─────────────────────────────────────────────
    # Document node
    # ─────────────────────────────────────────────

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

    # ─────────────────────────────────────────────
    # Person node
    # ─────────────────────────────────────────────

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

    # ─────────────────────────────────────────────
    # Authorship
    # ─────────────────────────────────────────────

    def _build_authorship_relation(self, author: str, doc_hash: str):

        person_key = self._normalize_person_key(author)

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

    # ─────────────────────────────────────────────
    # Hash
    # ─────────────────────────────────────────────

    def _compute_hash(self, meta):

        parts = [
            meta.title or "",
            ",".join(meta.authors) if meta.authors else "",
            ",".join(i.name for i in meta.institutions) if meta.institutions else "",
            meta.summary or "",
        ]

        return hashlib.sha256("|".join(parts).encode()).hexdigest()
    
    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _normalize_person_key(self, name: str) -> str:
        return name.strip().lower().replace(" ", "_")
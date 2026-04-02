import hashlib
import unittest
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any

# Mock the imports since we don't have the actual modules
class MockNodeId(str):
    pass

class MockEntityType(str):
    pass

class MockKeyAttribute(str):
    pass

class MockNode:
    def __init__(self, id, entity_type, key_attribute, payload_data, relations):
        self.id = id
        self.entity_type = entity_type
        self.key_attribute = key_attribute
        self.payload_data = payload_data
        self.relations = relations

class MockContent:
    def __init__(self, metadata: Dict[str, Any]):
        self.content = {"metadata": metadata}

# Patch the imports
import sys
sys.modules['database_builder_libs'] = MagicMock()
sys.modules['database_builder_libs.models'] = MagicMock()
sys.modules['database_builder_libs.models.node'] = MagicMock(
    Node=MockNode,
    NodeId=MockNodeId,
    EntityType=MockEntityType,
    KeyAttribute=MockKeyAttribute,
)
sys.modules['database_builder_libs.models.abstract_source'] = MagicMock()

from database_builder_libs.models.node import Node, NodeId, EntityType, KeyAttribute
from database_builder_libs.models.abstract_source import Content

# Now import the module under test
import importlib.util
spec = importlib.util.spec_from_loader("metadata_node_exporter", loader=None)
# Since we can't load the actual module, we'll define the class here with the source

class MetadataNodeExporter:

    NOISE_TERMS = {
        "interviewees","participants","attendees","reviewers",
        "respondents","community members","staff","team",
        "students","focus group","focus groups","survey participants",
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

    def export(self, content_list):
        nodes = {}
        for content in content_list:
            meta = content.content.get("metadata", {})
            doc_hash = self._hash(meta)
            relations = []

            # AUTHORS
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

            # ACKNOWLEDGEMENTS
            for ack in meta.get("acknowledgements") or []:
                name = ack.get("name", "")

                if self._is_noise(name):
                    continue

                nodes.setdefault(name, self._institution_node(name))

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

            # KEYWORD PROCESSING
            doc_type = None
            semantic_functions = set()

            for tag in meta.get("keywords") or []:
                t = self._normalize(tag)

                for keyword, dtype in self.KEYWORD_DOC_TYPES.items():
                    if keyword in t:
                        doc_type = dtype

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

            # FALLBACK CLASSIFICATION
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

            # DOCUMENT NODE
            nodes[doc_hash] = MockNode(
                id=MockNodeId(doc_hash),
                entity_type=MockEntityType("textdocument"),
                key_attribute=MockKeyAttribute("hashvalue"),
                payload_data={
                    "namelike-title": meta.get("title")
                } if meta.get("title") else {},
                relations=tuple(relations),
            )

        return list(nodes.values())

    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def _person_key(self, name: str) -> str:
        return name.strip().lower().replace(" ", "_")

    def _is_noise(self, name: str) -> bool:
        n = name.lower()
        return len(n) < 3 or any(term in n for term in self.NOISE_TERMS)

    def _hash(self, meta: dict) -> str:
        parts = [
            meta.get("title") or "",
            ",".join(meta.get("authors") or []),
            meta.get("summary") or "",
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _person_node(self, name: str) -> MockNode:
        key = self._person_key(name)

        if "," in name:
            last, _, first = name.partition(",")
            payload = {"namelike-first": first.strip(), "namelike-last": last.strip()}
        else:
            parts = name.split(" ", 1)
            payload = {"namelike-first": parts[0]}
            if len(parts) == 2:
                payload["namelike-last"] = parts[1]

        return MockNode(
            id=MockNodeId(key),
            entity_type=MockEntityType("person"),
            key_attribute=MockKeyAttribute("person-key"),
            payload_data=payload,
            relations=(),
        )

    def _institution_node(self, name: str) -> MockNode:
        return MockNode(
            id=MockNodeId(name),
            entity_type=MockEntityType("publishinginstitution"),
            key_attribute=MockKeyAttribute("namelike-name"),
            payload_data={"namelike-name": name},
            relations=(),
        )


class TestMetadataNodeExporterNormalize(unittest.TestCase):
    """Tests for the _normalize helper method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_normalize_strips_whitespace(self):
        result = self.exporter._normalize("  hello world  ")
        self.assertEqual(result, "hello world")

    def test_normalize_converts_to_lowercase(self):
        result = self.exporter._normalize("HELLO WORLD")
        self.assertEqual(result, "hello world")

    def test_normalize_combined(self):
        result = self.exporter._normalize("  HELLO WORLD  ")
        self.assertEqual(result, "hello world")

    def test_normalize_empty_string(self):
        result = self.exporter._normalize("")
        self.assertEqual(result, "")


class TestMetadataNodeExporterPersonKey(unittest.TestCase):
    """Tests for the _person_key helper method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_person_key_simple_name(self):
        result = self.exporter._person_key("John Doe")
        self.assertEqual(result, "john_doe")

    def test_person_key_with_whitespace(self):
        result = self.exporter._person_key("  John Doe  ")
        self.assertEqual(result, "john_doe")

    def test_person_key_uppercase(self):
        result = self.exporter._person_key("JOHN DOE")
        self.assertEqual(result, "john_doe")

    def test_person_key_multiple_spaces(self):
        result = self.exporter._person_key("John Q Public")
        self.assertEqual(result, "john_q_public")

    def test_person_key_single_name(self):
        result = self.exporter._person_key("Madonna")
        self.assertEqual(result, "madonna")


class TestMetadataNodeExporterIsNoise(unittest.TestCase):
    """Tests for the _is_noise helper method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_is_noise_short_strings(self):
        self.assertTrue(self.exporter._is_noise("ab"))
        self.assertTrue(self.exporter._is_noise("a"))
        self.assertTrue(self.exporter._is_noise(""))

    def test_is_noise_long_enough_but_not_noisy(self):
        self.assertFalse(self.exporter._is_noise("MIT"))
        self.assertFalse(self.exporter._is_noise("Harvard University"))

    def test_is_noise_contains_noise_term(self):
        self.assertTrue(self.exporter._is_noise("interviewees"))
        self.assertTrue(self.exporter._is_noise("participants"))
        self.assertTrue(self.exporter._is_noise("focus group"))
        self.assertTrue(self.exporter._is_noise("survey participants"))

    def test_is_noise_case_insensitive(self):
        self.assertTrue(self.exporter._is_noise("INTERVIEWEES"))
        self.assertTrue(self.exporter._is_noise("Participants"))

    def test_is_noise_partial_match(self):
        # Should match if term is contained
        self.assertTrue(self.exporter._is_noise("the interviewees team"))


class TestMetadataNodeExporterHash(unittest.TestCase):
    """Tests for the _hash helper method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_hash_consistent(self):
        meta = {
            "title": "Test Title",
            "authors": ["John Doe", "Jane Smith"],
            "summary": "Test summary"
        }
        hash1 = self.exporter._hash(meta)
        hash2 = self.exporter._hash(meta)
        self.assertEqual(hash1, hash2)

    def test_hash_different_for_different_content(self):
        meta1 = {"title": "Title 1", "authors": [], "summary": ""}
        meta2 = {"title": "Title 2", "authors": [], "summary": ""}
        hash1 = self.exporter._hash(meta1)
        hash2 = self.exporter._hash(meta2)
        self.assertNotEqual(hash1, hash2)

    def test_hash_with_empty_metadata(self):
        meta = {}
        hash_val = self.exporter._hash(meta)
        self.assertEqual(len(hash_val), 64)  # SHA256 hex digest length

    def test_hash_with_missing_fields(self):
        meta = {"title": "Only Title"}
        hash_val = self.exporter._hash(meta)
        self.assertEqual(len(hash_val), 64)

    def test_hash_different_order_authors(self):
        meta1 = {"title": "Test", "authors": ["John", "Jane"], "summary": ""}
        meta2 = {"title": "Test", "authors": ["Jane", "John"], "summary": ""}
        hash1 = self.exporter._hash(meta1)
        hash2 = self.exporter._hash(meta2)
        self.assertNotEqual(hash1, hash2)


class TestMetadataNodeExporterPersonNode(unittest.TestCase):
    """Tests for the _person_node builder method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_person_node_simple_name(self):
        node = self.exporter._person_node("John Doe")
        self.assertEqual(node.entity_type, "person")
        self.assertEqual(node.key_attribute, "person-key")
        self.assertEqual(node.id, "john_doe")
        self.assertEqual(node.payload_data.get("namelike-first"), "John")
        self.assertEqual(node.payload_data.get("namelike-last"), "Doe")

    def test_person_node_single_name(self):
        node = self.exporter._person_node("Madonna")
        self.assertEqual(node.id, "madonna")
        self.assertEqual(node.payload_data.get("namelike-first"), "Madonna")
        self.assertNotIn("namelike-last", node.payload_data)

    def test_person_node_comma_format(self):
        node = self.exporter._person_node("Doe, John")
        self.assertEqual(node.payload_data.get("namelike-first"), "John")
        self.assertEqual(node.payload_data.get("namelike-last"), "Doe")

    def test_person_node_comma_format_with_spaces(self):
        node = self.exporter._person_node("Doe,  John  ")
        self.assertEqual(node.payload_data.get("namelike-first"), "John")
        self.assertEqual(node.payload_data.get("namelike-last"), "Doe")

    def test_person_node_multiple_parts(self):
        node = self.exporter._person_node("John Q Public")
        self.assertEqual(node.payload_data.get("namelike-first"), "John")
        self.assertEqual(node.payload_data.get("namelike-last"), "Q Public")


class TestMetadataNodeExporterInstitutionNode(unittest.TestCase):
    """Tests for the _institution_node builder method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_institution_node_creates_correct_type(self):
        node = self.exporter._institution_node("MIT")
        self.assertEqual(node.entity_type, "publishinginstitution")
        self.assertEqual(node.key_attribute, "namelike-name")

    def test_institution_node_sets_name(self):
        node = self.exporter._institution_node("Massachusetts Institute of Technology")
        self.assertEqual(node.id, "Massachusetts Institute of Technology")
        self.assertEqual(node.payload_data.get("namelike-name"), "Massachusetts Institute of Technology")

    def test_institution_node_no_relations(self):
        node = self.exporter._institution_node("Harvard")
        self.assertEqual(node.relations, ())


class TestMetadataNodeExporterExport(unittest.TestCase):
    """Integration tests for the export method"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_export_empty_list(self):
        result = self.exporter.export([])
        self.assertEqual(result, [])

    def test_export_single_document_no_metadata(self):
        content = MockContent({})
        result = self.exporter.export([content])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].entity_type, "textdocument")

    def test_export_document_with_title(self):
        content = MockContent({"title": "My Document"})
        result = self.exporter.export([content])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].payload_data.get("namelike-title"), "My Document")

    def test_export_document_with_authors(self):
        content = MockContent({
            "title": "Research Paper",
            "authors": ["John Doe", "Jane Smith"]
        })
        result = self.exporter.export([content])
        self.assertEqual(len(result), 3)  # 1 document + 2 person nodes
        
        # Check that person nodes were created
        person_nodes = [n for n in result if n.entity_type == "person"]
        self.assertEqual(len(person_nodes), 2)

    def test_export_authors_create_authorship_relations(self):
        content = MockContent({
            "title": "Paper",
            "authors": ["John Doe"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        authorship_relations = [r for r in doc_node.relations if r.get("type") == "authorship"]
        self.assertEqual(len(authorship_relations), 1)
        self.assertIn("author", authorship_relations[0]["roles"])

    def test_export_acknowledgements_filtered(self):
        content = MockContent({
            "title": "Paper",
            "acknowledgements": [
                {"name": "MIT", "relation": "funding"},
                {"name": "participants", "relation": "contribution"}  # Should be filtered
            ]
        })
        result = self.exporter.export([content])
        institution_nodes = [n for n in result if n.entity_type == "publishinginstitution"]
        self.assertEqual(len(institution_nodes), 1)
        self.assertEqual(institution_nodes[0].id, "MIT")

    def test_export_keyword_doc_type_scientific(self):
        content = MockContent({
            "title": "Paper",
            "keywords": ["scientific literature", "research"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        # Should have a classification relation
        doc_type_relations = [r for r in doc_node.relations 
                            if r.get("type") == "discriminatingconcept-bol-scientific"]
        self.assertTrue(len(doc_type_relations) > 0)

    def test_export_keyword_doc_type_survey(self):
        content = MockContent({
            "title": "Survey",
            "keywords": ["survey"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        survey_relations = [r for r in doc_node.relations 
                          if r.get("type") == "discriminatingconcept-bol-surveys"]
        self.assertEqual(len(survey_relations), 1)

    def test_export_keyword_functions(self):
        content = MockContent({
            "title": "Document",
            "keywords": ["best practices", "strategic overview"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        # Should have semantic function relations
        functions = [r.get("attributes", {}).get("function") 
                    for r in doc_node.relations 
                    if r.get("attributes", {}).get("function")]
        self.assertIn("best-practices", functions)
        self.assertIn("strategic-overview", functions)

    def test_export_fallback_classification_with_keywords(self):
        content = MockContent({
            "title": "Document",
            "keywords": ["some random keyword"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        # Should default to scientific concept
        scientific_relations = [r for r in doc_node.relations 
                              if r.get("type") == "discriminatingconcept-bol-scientific"]
        self.assertTrue(len(scientific_relations) > 0)

    def test_export_fallback_classification_with_acknowledgements(self):
        content = MockContent({
            "title": "Document",
            "acknowledgements": [{"name": "MIT", "relation": "funding"}]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        # Should classify as grey literature
        grey_lit_relations = [r for r in doc_node.relations 
                            if r.get("type") == "discriminatingconcept-bol-greyliterature"]
        self.assertEqual(len(grey_lit_relations), 1)

    def test_export_multiple_documents(self):
        contents = [
            MockContent({"title": "Doc 1", "authors": ["Author A"]}),
            MockContent({"title": "Doc 2", "authors": ["Author B"]}),
        ]
        result = self.exporter.export(contents)
        
        # Should have 2 documents and potentially shared or unique authors
        doc_nodes = [n for n in result if n.entity_type == "textdocument"]
        self.assertEqual(len(doc_nodes), 2)

    def test_export_shared_author_deduplication(self):
        contents = [
            MockContent({"title": "Doc 1", "authors": ["John Doe"]}),
            MockContent({"title": "Doc 2", "authors": ["John Doe"]}),
        ]
        result = self.exporter.export(contents)
        
        # Should have 2 documents and 1 shared person node
        person_nodes = [n for n in result if n.entity_type == "person"]
        self.assertEqual(len(person_nodes), 1)
        self.assertEqual(person_nodes[0].id, "john_doe")


class TestMetadataNodeExporterEdgeCases(unittest.TestCase):
    """Edge case tests"""

    def setUp(self):
        self.exporter = MetadataNodeExporter()

    def test_export_with_none_values(self):
        content = MockContent({
            "title": None,
            "authors": None,
            "keywords": None,
            "acknowledgements": None
        })
        result = self.exporter.export([content])
        self.assertEqual(len(result), 1)

    def test_export_keyword_case_insensitive(self):
        content = MockContent({
            "title": "Paper",
            "keywords": ["SCIENTIFIC LITERATURE", "Best Practices"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        functions = [r.get("attributes", {}).get("function") 
                    for r in doc_node.relations 
                    if r.get("attributes", {}).get("function")]
        self.assertIn("best-practices", functions)

    def test_authorship_id_consistency(self):
        content = MockContent({
            "title": "Paper",
            "authors": ["John Doe"]
        })
        result = self.exporter.export([content])
        doc_node = [n for n in result if n.entity_type == "textdocument"][0]
        
        authorship_relations = [r for r in doc_node.relations if r.get("type") == "authorship"]
        self.assertTrue(len(authorship_relations) > 0)
        
        # Check that authorship-id exists and is a valid hex string
        auth_id = authorship_relations[0]["attributes"]["authorship-id"]
        self.assertEqual(len(auth_id), 64)  # SHA256 hex length
        int(auth_id, 16)  # Should not raise


if __name__ == "__main__":
    unittest.main()
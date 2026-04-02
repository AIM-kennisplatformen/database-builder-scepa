import unittest
from unittest.mock import Mock, MagicMock, patch
from io import StringIO
from typing import List, Dict, Any, cast

# Mock the imports
import sys
sys.modules['database_builder_libs'] = MagicMock()
sys.modules['database_builder_libs.models'] = MagicMock()
sys.modules['database_builder_libs.models.node'] = MagicMock()
sys.modules['database_builder_libs.stores'] = MagicMock()
sys.modules['database_builder_libs.stores.typedb_v2'] = MagicMock()
sys.modules['database_builder_libs.stores.typedb_v2.typedb_v2_store'] = MagicMock()


# Type definitions
class MockNodeId(str):
    pass


class MockEntityType(str):
    pass


class MockKeyAttribute(str):
    pass


class RelationData(dict):
    """Mock RelationData type - just a dict subclass"""
    pass


class MockNode:
    def __init__(self, id, entity_type, key_attribute, payload_data, relations):
        self.id = MockNodeId(id)
        self.entity_type = MockEntityType(entity_type)
        self.key_attribute = MockKeyAttribute(key_attribute)
        self.payload_data = payload_data
        self.relations = tuple(relations) if relations else ()

    def __repr__(self):
        return (f"MockNode(id={self.id}, entity_type={self.entity_type}, "
                f"key_attribute={self.key_attribute})")


# The actual module code
def format_node(node) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"Entity Type : {node.entity_type}")
    lines.append(f"Node ID     : {node.id}")
    lines.append(f"Key Attr    : {node.key_attribute}")
    lines.append("Payload:")
    for k, v in node.payload_data.items():
        lines.append(f"  {k}: {v}")
    if node.relations:
        lines.append("Relations:")
        for rel in node.relations:
            rel = cast(RelationData, rel)
            lines.append(f"  type: {rel['type']}")
            # roles
            for role, ref in rel.get("roles", {}).items():
                lines.append(
                    f"    {role} -> "
                    f"{ref['entity_type']}({ref['key_attr']}={ref['key']})"
                )
            # attributes
            for attr, value in rel.get("attributes", {}).items():
                lines.append(f"    {attr}: {value}")
    else:
        lines.append("Relations: none")
    return "\n".join(lines)


def print_nodes(nodes: List) -> None:
    for node in nodes:
        print(format_node(node))


# ─────────────────────────────────────────────────────────────────────
# UNIT TESTS
# ─────────────────────────────────────────────────────────────────────

class TestFormatNodeBasic(unittest.TestCase):
    """Tests for basic node formatting functionality"""

    def test_format_node_simple(self):
        """Test formatting a simple node with minimal data"""
        node = MockNode(
            id="test-id",
            entity_type="person",
            key_attribute="person-key",
            payload_data={},
            relations=[]
        )
        result = format_node(node)

        self.assertIn("=" * 70, result)
        self.assertIn("Entity Type : person", result)
        self.assertIn("Node ID     : test-id", result)
        self.assertIn("Key Attr    : person-key", result)
        self.assertIn("Payload:", result)
        self.assertIn("Relations: none", result)

    def test_format_node_has_separator(self):
        """Test that output starts with separator line"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        lines = result.split("\n")
        self.assertEqual(lines[0], "=" * 70)

    def test_format_node_field_order(self):
        """Test that fields appear in correct order"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        lines = result.split("\n")

        entity_idx = next(i for i, line in enumerate(lines) if "Entity Type" in line)
        node_id_idx = next(i for i, line in enumerate(lines) if "Node ID" in line)
        key_idx = next(i for i, line in enumerate(lines) if "Key Attr" in line)
        payload_idx = next(i for i, line in enumerate(lines) if "Payload:" in line)

        self.assertLess(entity_idx, node_id_idx)
        self.assertLess(node_id_idx, key_idx)
        self.assertLess(key_idx, payload_idx)


class TestFormatNodePayload(unittest.TestCase):
    """Tests for payload data formatting"""

    def test_format_node_empty_payload(self):
        """Test formatting node with empty payload"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        self.assertIn("Payload:", result)
        # Should not have indented payload items
        lines = result.split("\n")
        payload_idx = next(i for i, line in enumerate(lines) if "Payload:" in line)
        self.assertFalse(any(line.startswith("  ") for line in lines[payload_idx+1:payload_idx+3]))

    def test_format_node_single_payload_item(self):
        """Test formatting node with single payload item"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={"name": "John Doe"},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("  name: John Doe", result)

    def test_format_node_multiple_payload_items(self):
        """Test formatting node with multiple payload items"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com"
            },
            relations=[]
        )
        result = format_node(node)
        self.assertIn("  first_name: John", result)
        self.assertIn("  last_name: Doe", result)
        self.assertIn("  email: john@example.com", result)

    def test_format_node_payload_with_special_characters(self):
        """Test formatting node with special characters in payload"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={"description": "Test with <special> & characters"},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("Test with <special> & characters", result)

    def test_format_node_payload_with_numbers(self):
        """Test formatting node with numeric payload values"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={"count": 42, "score": 3.14},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("count: 42", result)
        self.assertIn("score: 3.14", result)

    def test_format_node_payload_with_none(self):
        """Test formatting node with None values in payload"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={"value": None},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("value: None", result)

    def test_format_node_payload_with_empty_string(self):
        """Test formatting node with empty string in payload"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={"empty": ""},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("empty: ", result)


class TestFormatNodeRelations(unittest.TestCase):
    """Tests for relation formatting"""

    def test_format_node_no_relations(self):
        """Test formatting node with no relations"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        self.assertIn("Relations: none", result)

    def test_format_node_single_relation_with_role(self):
        """Test formatting node with single relation containing role"""
        relation = {
            "type": "authorship",
            "roles": {
                "author": {
                    "entity_type": "person",
                    "key_attr": "person-key",
                    "key": "john_doe"
                }
            },
            "attributes": {}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("Relations:", result)
        self.assertIn("type: authorship", result)
        self.assertIn("author -> person(person-key=john_doe)", result)

    def test_format_node_relation_with_multiple_roles(self):
        """Test formatting relation with multiple roles"""
        relation = {
            "type": "authorship",
            "roles": {
                "author": {
                    "entity_type": "person",
                    "key_attr": "person-key",
                    "key": "john_doe"
                },
                "work": {
                    "entity_type": "document",
                    "key_attr": "doc-id",
                    "key": "doc123"
                }
            },
            "attributes": {}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("author -> person(person-key=john_doe)", result)
        self.assertIn("work -> document(doc-id=doc123)", result)

    def test_format_node_relation_with_attributes(self):
        """Test formatting relation with attributes"""
        relation = {
            "type": "authorship",
            "roles": {},
            "attributes": {
                "role": "primary",
                "order": 1
            }
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("role: primary", result)
        self.assertIn("order: 1", result)

    def test_format_node_relation_without_roles_key(self):
        """Test formatting relation without 'roles' key"""
        relation = {
            "type": "classification",
            "attributes": {"function": "best-practices"}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("type: classification", result)
        self.assertIn("function: best-practices", result)

    def test_format_node_relation_without_attributes_key(self):
        """Test formatting relation without 'attributes' key"""
        relation = {
            "type": "reference",
            "roles": {
                "source": {
                    "entity_type": "document",
                    "key_attr": "doc-id",
                    "key": "doc1"
                }
            }
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("type: reference", result)
        self.assertIn("source -> document(doc-id=doc1)", result)

    def test_format_node_multiple_relations(self):
        """Test formatting node with multiple relations"""
        relations = [
            {
                "type": "authorship",
                "roles": {
                    "author": {
                        "entity_type": "person",
                        "key_attr": "person-key",
                        "key": "john_doe"
                    }
                },
                "attributes": {}
            },
            {
                "type": "published_by",
                "roles": {
                    "publisher": {
                        "entity_type": "institution",
                        "key_attr": "inst-name",
                        "key": "MIT"
                    }
                },
                "attributes": {}
            }
        ]
        node = MockNode("id", "type", "key", {}, relations)
        result = format_node(node)

        self.assertIn("type: authorship", result)
        self.assertIn("type: published_by", result)
        self.assertIn("john_doe", result)
        self.assertIn("MIT", result)

    def test_format_node_relation_indentation(self):
        """Test that relation elements are properly indented"""
        relation = {
            "type": "authorship",
            "roles": {
                "author": {
                    "entity_type": "person",
                    "key_attr": "person-key",
                    "key": "john_doe"
                }
            },
            "attributes": {"order": 1}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)
        lines = result.split("\n")

        # Find relation type line and check indentation of following items
        type_idx = next(i for i, line in enumerate(lines) if "type: authorship" in line)
        role_line = lines[type_idx + 1]
        attr_line = lines[type_idx + 2]

        self.assertTrue(role_line.startswith("    "))  # 4 spaces for role
        self.assertTrue(attr_line.startswith("    "))  # 4 spaces for attribute


class TestFormatNodeComplexScenarios(unittest.TestCase):
    """Tests for complex node formatting scenarios"""

    def test_format_document_node(self):
        """Test formatting a realistic document node"""
        relation = {
            "type": "authorship",
            "roles": {
                "author": {
                    "entity_type": "person",
                    "key_attr": "person-key",
                    "key": "jane_smith"
                },
                "work": {
                    "entity_type": "textdocument",
                    "key_attr": "hashvalue",
                    "key": "abc123def456"
                }
            },
            "attributes": {
                "authorship-id": "xyz789"
            }
        }
        node = MockNode(
            id="abc123def456",
            entity_type="textdocument",
            key_attribute="hashvalue",
            payload_data={"namelike-title": "Research on AI"},
            relations=[relation]
        )
        result = format_node(node)

        self.assertIn("Entity Type : textdocument", result)
        self.assertIn("Node ID     : abc123def456", result)
        self.assertIn("Key Attr    : hashvalue", result)
        self.assertIn("namelike-title: Research on AI", result)
        self.assertIn("type: authorship", result)
        self.assertIn("jane_smith", result)
        self.assertIn("authorship-id: xyz789", result)

    def test_format_person_node(self):
        """Test formatting a realistic person node"""
        node = MockNode(
            id="john_doe",
            entity_type="person",
            key_attribute="person-key",
            payload_data={
                "namelike-first": "John",
                "namelike-last": "Doe"
            },
            relations=[]
        )
        result = format_node(node)

        self.assertIn("Entity Type : person", result)
        self.assertIn("Node ID     : john_doe", result)
        self.assertIn("namelike-first: John", result)
        self.assertIn("namelike-last: Doe", result)
        self.assertIn("Relations: none", result)

    def test_format_institution_node_with_funding_relation(self):
        """Test formatting institution node with funding relation"""
        relation = {
            "type": "discriminatingconcept-bol-scientific",
            "roles": {
                "attributedto": {
                    "entity_type": "publishinginstitution",
                    "key_attr": "namelike-name",
                    "key": "National Science Foundation"
                },
                "attributedthing": {
                    "entity_type": "textdocument",
                    "key_attr": "hashvalue",
                    "key": "doc_hash_123"
                }
            },
            "attributes": {
                "function": "funding"
            }
        }
        node = MockNode(
            id="National Science Foundation",
            entity_type="publishinginstitution",
            key_attribute="namelike-name",
            payload_data={"namelike-name": "National Science Foundation"},
            relations=[relation]
        )
        result = format_node(node)

        self.assertIn("Entity Type : publishinginstitution", result)
        self.assertIn("National Science Foundation", result)
        self.assertIn("type: discriminatingconcept-bol-scientific", result)
        self.assertIn("function: funding", result)


class TestPrintNodes(unittest.TestCase):
    """Tests for print_nodes function"""

    @patch('sys.stdout', new_callable=StringIO)
    def test_print_nodes_empty_list(self, mock_stdout):
        """Test printing empty list of nodes"""
        print_nodes([])
        self.assertEqual(mock_stdout.getvalue(), "")

    @patch('sys.stdout', new_callable=StringIO)
    def test_print_nodes_single_node(self, mock_stdout):
        """Test printing single node"""
        node = MockNode("id", "type", "key", {"name": "test"}, [])
        print_nodes([node])
        output = mock_stdout.getvalue()

        self.assertIn("Entity Type : type", output)
        self.assertIn("Node ID     : id", output)
        self.assertIn("name: test", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_print_nodes_multiple_nodes(self, mock_stdout):
        """Test printing multiple nodes"""
        nodes = [
            MockNode("id1", "person", "key", {"name": "John"}, []),
            MockNode("id2", "document", "key", {"title": "Paper"}, [])
        ]
        print_nodes(nodes)
        output = mock_stdout.getvalue()

        self.assertIn("Entity Type : person", output)
        self.assertIn("Entity Type : document", output)
        self.assertIn("John", output)
        self.assertIn("Paper", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_print_nodes_separation(self, mock_stdout):
        """Test that multiple nodes are visually separated"""
        nodes = [
            MockNode("id1", "person", "key", {}, []),
            MockNode("id2", "document", "key", {}, [])
        ]
        print_nodes(nodes)
        output = mock_stdout.getvalue()

        # Should have two separator lines for two nodes
        separator_count = output.count("=" * 70)
        self.assertEqual(separator_count, 2)

    @patch('sys.stdout', new_callable=StringIO)
    def test_print_nodes_with_relations(self, mock_stdout):
        """Test printing nodes with relations"""
        relation = {
            "type": "authorship",
            "roles": {
                "author": {
                    "entity_type": "person",
                    "key_attr": "person-key",
                    "key": "john_doe"
                }
            },
            "attributes": {}
        }
        nodes = [
            MockNode("id1", "person", "key", {"name": "John Doe"}, []),
            MockNode("id2", "document", "key", {"title": "Paper"}, [relation])
        ]
        print_nodes(nodes)
        output = mock_stdout.getvalue()

        self.assertIn("Relations:", output)
        self.assertIn("type: authorship", output)
        self.assertIn("john_doe", output)


class TestFormatNodeEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions"""

    def test_format_node_with_very_long_id(self):
        """Test formatting node with very long ID"""
        long_id = "a" * 1000
        node = MockNode(long_id, "type", "key", {}, [])
        result = format_node(node)
        self.assertIn(long_id, result)

    def test_format_node_with_unicode_characters(self):
        """Test formatting node with unicode characters"""
        node = MockNode(
            id="unicode_test",
            entity_type="type",
            key_attribute="key",
            payload_data={"name": "François Müller 北京"},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("François Müller 北京", result)

    def test_format_node_with_multiline_payload(self):
        """Test formatting node with newlines in payload"""
        node = MockNode(
            id="id",
            entity_type="type",
            key_attribute="key",
            payload_data={"description": "Line 1\nLine 2\nLine 3"},
            relations=[]
        )
        result = format_node(node)
        self.assertIn("Line 1\nLine 2\nLine 3", result)

    def test_format_node_relation_with_empty_roles(self):
        """Test formatting relation with empty roles dict"""
        relation = {
            "type": "classification",
            "roles": {},
            "attributes": {"class": "type-a"}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("type: classification", result)
        self.assertIn("class: type-a", result)

    def test_format_node_relation_with_empty_attributes(self):
        """Test formatting relation with empty attributes dict"""
        relation = {
            "type": "reference",
            "roles": {
                "source": {
                    "entity_type": "doc",
                    "key_attr": "id",
                    "key": "doc1"
                }
            },
            "attributes": {}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("type: reference", result)
        self.assertIn("source -> doc(id=doc1)", result)

    def test_format_node_preserves_payload_key_order(self):
        """Test that payload items appear in order"""
        from collections import OrderedDict
        payload = OrderedDict([
            ("a_first", "1"),
            ("b_second", "2"),
            ("c_third", "3")
        ])
        node = MockNode("id", "type", "key", payload, [])
        result = format_node(node)
        lines = result.split("\n")

        a_idx = next((i for i, line in enumerate(lines) if "a_first" in line), -1)
        b_idx = next((i for i, line in enumerate(lines) if "b_second" in line), -1)
        c_idx = next((i for i, line in enumerate(lines) if "c_third" in line), -1)

        self.assertLess(a_idx, b_idx)
        self.assertLess(b_idx, c_idx)


class TestFormatNodeStructure(unittest.TestCase):
    """Tests for output structure and formatting consistency"""

    def test_format_node_returns_string(self):
        """Test that format_node returns a string"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        self.assertIsInstance(result, str)

    def test_format_node_has_newlines(self):
        """Test that output contains newlines"""
        node = MockNode("id", "type", "key", {"key": "value"}, [])
        result = format_node(node)
        self.assertIn("\n", result)

    def test_format_node_starts_with_separator(self):
        """Test that output starts with separator"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        self.assertTrue(result.startswith("=" * 70))

    def test_format_node_no_trailing_newline(self):
        """Test that output doesn't have trailing newline"""
        node = MockNode("id", "type", "key", {}, [])
        result = format_node(node)
        self.assertFalse(result.endswith("\n"))

    def test_format_node_consistent_spacing(self):
        """Test consistent spacing in output"""
        node = MockNode(
            "id",
            "type",
            "key",
            {"field1": "value1", "field2": "value2"},
            []
        )
        result = format_node(node)
        lines = result.split("\n")

        # All payload lines should start with 2 spaces
        payload_idx = next(i for i, line in enumerate(lines) if "Payload:" in line)
        end_idx = next((i for i in range(payload_idx + 1, len(lines)) 
                        if not lines[i].startswith("  ")), len(lines))
        payload_lines = lines[payload_idx + 1:end_idx]
        
        for line in payload_lines:
            if line.strip():  # Non-empty lines
                self.assertTrue(line.startswith("  "))


class TestFormatNodeSpecialCases(unittest.TestCase):
    """Tests for special formatting cases"""

    def test_format_node_entity_type_with_special_chars(self):
        """Test entity type with special characters"""
        node = MockNode("id", "type-with-dashes_and_underscores", "key", {}, [])
        result = format_node(node)
        self.assertIn("type-with-dashes_and_underscores", result)

    def test_format_node_key_attribute_with_dots(self):
        """Test key attribute with dots (nested notation)"""
        node = MockNode("id", "type", "obj.attr.nested", {}, [])
        result = format_node(node)
        self.assertIn("obj.attr.nested", result)

    def test_format_relation_role_name_variations(self):
        """Test various role name formats"""
        relation = {
            "type": "test",
            "roles": {
                "author": {"entity_type": "person", "key_attr": "id", "key": "1"},
                "co_author": {"entity_type": "person", "key_attr": "id", "key": "2"},
                "authoredwork": {"entity_type": "doc", "key_attr": "id", "key": "3"}
            },
            "attributes": {}
        }
        node = MockNode("id", "type", "key", {}, [relation])
        result = format_node(node)

        self.assertIn("author ->", result)
        self.assertIn("co_author ->", result)
        self.assertIn("authoredwork ->", result)

    def test_format_node_payload_value_formatting(self):
        """Test that payload values are formatted as-is"""
        node = MockNode(
            "id",
            "type",
            "key",
            {
                "bool_val": True,
                "list_val": [1, 2, 3],
                "dict_val": {"nested": "value"}
            },
            []
        )
        result = format_node(node)

        self.assertIn("bool_val: True", result)
        self.assertIn("list_val: [1, 2, 3]", result)
        self.assertIn("dict_val: {'nested': 'value'}", result)


if __name__ == "__main__":
    unittest.main()
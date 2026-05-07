from database_builder_libs.models.node import EntityType, KeyAttribute, Node, NodeId

from scepa_app.util.node_util import format_node


def test_format_node_includes_relations():
    node = Node(
        id=NodeId("doc-1"),
        entity_type=EntityType("textdocument"),
        key_attribute=KeyAttribute("hashvalue"),
        payload_data={"namelike-title": "Title"},
        relations=(
            {
                "type": "authorship",
                "roles": {
                    "author": {
                        "entity_type": "person",
                        "key_attr": "person-key",
                        "key": "alice",
                    }
                },
                "attributes": {"authorship-id": "abc"},
            },
        ),
    )

    formatted = format_node(node)

    assert "Entity Type" in formatted
    assert "Relations:" in formatted
    assert "authorship" in formatted
    assert "alice" in formatted

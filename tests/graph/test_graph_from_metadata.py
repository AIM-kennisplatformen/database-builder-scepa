from scepa_app.document_parsing.text_metadata import Acknowledgement, TextMetadata
from scepa_app.graph.graph_from_metadata import MetadataNodeExporter


def test_export_creates_document_author_and_institution_nodes():
    exporter = MetadataNodeExporter()

    metadata = TextMetadata(
        title="A Title",
        authors=["Alice Smith"],
        acknowledgements=[
            Acknowledgement(name="University of Example", type="organization", relation="support"),
            Acknowledgement(name="survey participants", type="group", relation="support"),
        ],
        keywords=["scientific literature", "best practices", "survey"],
    )

    nodes = exporter.export([metadata])

    assert len(nodes) == 3

    doc_node = next(node for node in nodes if node.entity_type == "textdocument")
    person_node = next(node for node in nodes if node.entity_type == "person")
    institution_node = next(
        node for node in nodes if node.entity_type == "publishinginstitution"
    )

    assert doc_node.payload_data == {"namelike-title": "A Title"}
    assert person_node.payload_data == {
        "namelike-first": "Alice",
        "namelike-last": "Smith",
    }
    assert institution_node.payload_data == {
        "namelike-name": "University of Example"
    }

    relation_types = [relation["type"] for relation in doc_node.relations]

    assert "authorship" in relation_types
    assert "discriminatingconcept-bol-scientific" in relation_types
    assert "discriminatingconcept-bol-surveys" in relation_types

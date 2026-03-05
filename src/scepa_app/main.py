from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .document_parsing.extraction.extract_text_chunks import TextChunkExtractor
from .document_parsing.extraction.extract_text_structure import TextStructureExtractor
from .document_parsing.extraction.extract_text_metadata import TextMetadataExtractor

from .document_parsing.embedding.embed_chunks import ChunkEmbedder
from .document_parsing.embedding.openai_embedding_model import OpenAICompatibleEmbeddingModel

from .graph.graph_from_metadata import MetadataNodeExporter
from database_builder_libs.stores.typedb_v2.typedb_v2_store import TypeDbDatastore
from database_builder_libs.models.node import Node
from dataclasses import replace
from typing import Mapping, cast
from database_builder_libs.stores.typedb_v2.typedb_v2_store import RelationData, RelationRef

def normalize_node(node: Node) -> Node:
    return replace(
        node,
        entity_type=str(node.entity_type),
        key_attribute=str(node.key_attribute),
        payload_data=dict(node.payload_data),
        relations=tuple(node.relations),
    )
load_dotenv()

LAST_SYNC_FILE = Path(".last_sync")
DOWNLOAD_DIR = Path("./downloads")

DEFAULT_SYNC_TIME = datetime(2025, 11, 21, 9, 4, 50, tzinfo=timezone.utc)


def load_last_sync() -> datetime:
    if not LAST_SYNC_FILE.exists():
        return DEFAULT_SYNC_TIME
    return datetime.fromisoformat(LAST_SYNC_FILE.read_text().strip()).astimezone(timezone.utc)


def save_last_sync(ts: datetime) -> None:
    LAST_SYNC_FILE.write_text(ts.isoformat())


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    pdf_path = Path(os.getenv("PDF_PATH", "PDF_INPUT/document.pdf"))
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path.resolve()}")

    # -----------------------------------------
    # Extract document structure
    # -----------------------------------------

    structure_extractor = TextStructureExtractor()
    docling_doc = TextStructureExtractor._convert(
        self=structure_extractor,
        pdf_path=str(pdf_path),
    )

    sections = structure_extractor._extract_sections(docling_doc)

    # -----------------------------------------
    # Extract metadata
    # -----------------------------------------

    metadata_extractor = TextMetadataExtractor()
    metadata = metadata_extractor.extract(
        pdf_path=str(pdf_path),
        doc=docling_doc,
    )

    # -----------------------------------------
    # Extract text chunks
    # -----------------------------------------

    chunk_extractor = TextChunkExtractor()

    chunks = chunk_extractor.extract_chunks(
        sections,
        document_id=os.getenv("DOCUMENT_ID", pdf_path.stem),
    )

    # -----------------------------------------
    # Embed chunks
    # -----------------------------------------

    embedder = ChunkEmbedder(
        OpenAICompatibleEmbeddingModel(
            base_url=require_env("OPENAI_HOST"),
            api_key=require_env("OPENAI_API_KEY"),
            model=require_env("OPENAI_EMBEDDING_MODEL"),
        )
    )

    embedder.embed(chunks)

    print(len(chunks), "embedded chunks")

    # -----------------------------------------
    # Convert metadata → graph nodes
    # -----------------------------------------

    exporter = MetadataNodeExporter()

    nodes = exporter.export([metadata])

    print(f"Generated {len(nodes)} nodes")


    # -----------------------------------------
    # Store nodes in TypeDB
    # -----------------------------------------

    typedb = TypeDbDatastore()

    typedb.connect(
        {
            "uri": require_env("TYPEDB_URI"),
            "database": require_env("TYPEDB_DATABASE"),
            "schema_path": require_env("TYPEDB_SCHEMA_PATH"),
        }
    )
    for node in nodes:
        typedb.store_node(normalize_node(node))
    print(f"Stored {len(nodes)} nodes in TypeDB")
    print()
    print("Generated Nodes")
    print("---------------")

    for node in nodes:
        print("=" * 70)
        print(f"Entity Type : {node.entity_type}")
        print(f"Node ID     : {node.id}")
        print(f"Key Attr    : {node.key_attribute}")

        print("Payload:")
        for k, v in node.payload_data.items():
            print(f"  {k}: {v}")

        if node.relations:
            print("Relations:")

            for rel_obj in node.relations:

                rel = cast(RelationData, rel_obj)

                print(f"  type: {rel['type']}")

                roles: Mapping[str, RelationRef] = rel["roles"] if "roles" in rel else {}

                for role, ref in roles.items():
                    print(
                        f"    {role} -> "
                        f"{ref['entity_type']}({ref['key_attr']}={ref['key']})"
                    )
        else:
            print("Relations: none")

    print("=" * 70)
    print(f"Total nodes: {len(nodes)}")
    print()
    # -----------------------------------------
    # Summary
    # -----------------------------------------

    print()
    print("Pipeline summary")
    print("----------------")
    print(f"Document metadata: {metadata}")
    print(f"Sections extracted: {len(sections)}")
    print(f"Chunks created:     {len(chunks)}")

    for c in chunks[:17]:
        print("-" * 60)
        print(
            f"chunk_index={c.chunk_index} "
            f"section={c.metadata.get('section_title') if c.metadata else None}"
        )
        print(
            c.text[:300].replace("\n", " ")
            + ("..." if len(c.text) > 300 else "")
        )
    print("\nRetrieved nodes from TypeDB")
    print("-----------------------------")

    retrieved_nodes = typedb.get_nodes("entity=textdocument&include=relations")
    for node in retrieved_nodes:
        print("=" * 70)
        print(f"Entity Type : {node.entity_type}")
        print(f"Node ID     : {node.id}")
        print(f"Key Attr    : {node.key_attribute}")

        print("Payload:")
        for k, v in node.payload_data.items():
            print(f"  {k}: {v}")

        if node.relations:
            print("Relations:")
            for rel_obj in node.relations:

                rel = cast(RelationData, rel_obj)

                print(f"  type: {rel['type']}")

                roles: Mapping[str, RelationRef] = rel["roles"] if "roles" in rel else {}

                for role, ref in roles.items():
                    print(
                        f"    {role} -> "
                        f"{ref['entity_type']}({ref['key_attr']}={ref['key']})"
                    )

                    # 🔎 If relation points to institution, fetch it
                    if role == "attributedto":
                        inst_filter = (
                            f"entity={ref['entity_type']}&"
                            f"{ref['key_attr']}={ref['key']}"
                        )

                        inst_nodes = typedb.get_nodes(inst_filter)

                        for inst in inst_nodes:
                            name = inst.payload_data.get("namelike-name")
                            if name:
                                print(f"      Institution name: {name}")

        else:
            print("Relations: none")

if __name__ == "__main__":
    main()
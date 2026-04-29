from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import json
import sys
from pathlib import Path
from typing import Any

from .document_parsing.extract_text_metadata import TextMetadataExtractor
from .document_parsing.extract_text_metadata_zotero import ZoteroMetadataExtractor

from .graph.graph_from_metadata import MetadataNodeExporter
from .util.node_util import print_nodes
from .util.partial_sync import PartialSync
from .settings import Settings, load_settings

from database_builder_libs.sources.zotero_source import ZoteroSource
from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore
from database_builder_libs.utility.extract.document_parser_docling import DocumentParserDocling, ParsedDocument
from database_builder_libs.utility.chunk.summary_and_sections import SummaryAndSectionsStrategy
from database_builder_libs.utility.embed_chunk.openai_compatible import OpenAICompatibleChunkEmbedder
from database_builder_libs.models.node import EntityType, KeyAttribute, Node, NodeId

def dump_nodes(nodes: list[Node], path: Path) -> None:
    """Serialize nodes to a JSON file for later replay."""
    data = [asdict(node) for node in nodes]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Dumped {len(nodes)} nodes to {path}")


def load_nodes(path: Path) -> list[Node]:
    """Deserialize nodes from a previously dumped JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = [
        Node(
            id=NodeId(item["id"]),
            payload_data=item.get("payload_data", {}),
            relations=item.get("relations", []),
            entity_type=EntityType(item.get("entity_type", "node")),
            key_attribute=KeyAttribute(item.get("key_attribute", "id")),
        )
        for item in data
    ]
    print(f"Loaded {len(nodes)} nodes from {path}")
    return nodes


def parse_document(pdf_path: Path) -> ParsedDocument:
    return DocumentParserDocling().parse(str(pdf_path))


def extract_metadata(
    pdf_path: Path,
    doc: ParsedDocument,
    settings: Settings,
    zotero_item: dict[str, Any],
):
    from openai import OpenAI

    zotero_meta = ZoteroMetadataExtractor().extract(zotero_entry=zotero_item)

    extractor = TextMetadataExtractor(
        llm_client=OpenAI(base_url=settings.openai_host, api_key=settings.openai_key),
        llm_model=settings.llm_model,
    )

    return extractor.extract(
        pdf_path=str(pdf_path),
        doc=doc,
        meta=zotero_meta,
    )


def extract_chunks(
    doc: ParsedDocument,
    document_id: str,
    summary: str | None = None,
):
    return SummaryAndSectionsStrategy().chunk(
        doc.sections,
        document_id=document_id,
        summary=summary,
    )


def embed_chunks(chunks, settings: Settings):
    return OpenAICompatibleChunkEmbedder(
        base_url=settings.openai_host,
        api_key=settings.openai_key,
        model=settings.embedding_model,
    ).embed(chunks)


def connect_qdrant(settings: Settings) -> QdrantDatastore:
    qdrant = QdrantDatastore()
    qdrant.connect(
        {
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection,
            "vector_size": settings.qdrant_vector_size,
        }
    )
    return qdrant


def store_vectors(chunks, qdrant: QdrantDatastore) -> None:
    qdrant.store_chunks(chunks)


def connect_typedb(settings: Settings) -> TypeDbDatastore:
    typedb = TypeDbDatastore()
    typedb.connect(
        {
            "uri": settings.typedb_uri,
            "username": settings.typedb_username,
            "password": settings.typedb_password,
            "database": settings.typedb_database,
            "schema_path": settings.typedb_schema,
        }
    )
    return typedb


def store_graph(nodes, typedb: TypeDbDatastore) -> None:
    for node in nodes:
        typedb.store_node(node)


def print_summary(metadata, sections, chunks) -> None:
    print("\nPipeline summary")
    print("----------------")
    print(f"Document metadata: {metadata}")
    print(f"Sections extracted: {len(sections)}")
    print(f"Chunks created: {len(chunks)}")

    for c in chunks[:10]:
        print("-" * 60)
        print(
            f"chunk_index={c.chunk_index} "
            f"section={c.metadata.get('section_title') if c.metadata else None}"
        )
        print(c.text[:300].replace("\n", " "))


def replay_nodes(json_path: Path, settings: Settings) -> None:
    """Load dumped nodes from disk and store them into TypeDB."""
    nodes = load_nodes(json_path)
    typedb = connect_typedb(settings)
    store_graph(nodes, typedb)
    print_nodes(nodes)


def process_item(
    item: dict[str, Any],
    settings: Settings,
    zot: ZoteroSource,
    qdrant: QdrantDatastore,
    typedb: TypeDbDatastore,
) -> None:
    item_key = item["key"]

    zot.download_zotero_item(
        item_id=item_key,
        download_path=str(settings.pdf_path),
    )

    pdf_path = settings.pdf_path / f"{item_key}.pdf"

    if not pdf_path.exists():
        return

    doc = parse_document(pdf_path)
    metadata = extract_metadata(pdf_path, doc, settings, item)
    chunks = extract_chunks(doc, document_id=item_key, summary=metadata.summary)
    chunks = embed_chunks(chunks, settings)

    store_vectors(chunks, qdrant)

    nodes = MetadataNodeExporter().export([metadata])
    dump_nodes(nodes, settings.pdf_path / f"{item_key}_nodes.json")
    store_graph(nodes, typedb)

    print_nodes(nodes)
    print_summary(metadata, doc.sections, chunks)


def main() -> None:
    settings = load_settings()
    qdrant = connect_qdrant(settings)
    typedb = connect_typedb(settings)

    zot = ZoteroSource()
    zot.connect(
        {
            "library_id": settings.zotero_library_id,
            "library_type": "group",
            "api_key": settings.zotero_api_key,
        }
    )

    sync = PartialSync()
    last_sync = sync.start_sync("Zotero")
    last_sync_dt = datetime.fromtimestamp(last_sync) if last_sync is not None else None

    artifacts = zot.get_list_artefacts(last_synced=last_sync_dt)
    sync.finish_sync("Zotero", artifacts)

    metadata_items = zot.get_all_documents_metadata(
        collection_id=settings.zotero_collection_id
    )

    items = (
        metadata_items
        if settings.max_documents is None
        else metadata_items[: settings.max_documents]
    )

    for item in items:
        process_item(item, settings, zot, qdrant, typedb)

    print("\nRetrieved nodes from TypeDB")

    retrieved = typedb.get_nodes("entity=textdocument&include=relations")
    print_nodes(retrieved)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--load":
        replay_nodes(Path(sys.argv[2]), load_settings())
    else:
        main()

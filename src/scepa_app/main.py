from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .document_parsing.extraction.extract_text_chunks import TextChunkExtractor
from .document_parsing.extraction.extract_text_structure import TextStructureExtractor
from .document_parsing.extraction.extract_text_metadata import TextMetadataExtractor
from .document_parsing.extraction.extract_text_metadata_zotero import ZoteroMetadataExtractor

from .document_parsing.embedding.embed_chunks import ChunkEmbedder
from .document_parsing.embedding.openai_embedding_model import OpenAICompatibleEmbeddingModel

from .graph.graph_from_metadata import MetadataNodeExporter
from .util.node_util import print_nodes
from .util.partial_sync import PartialSync

from database_builder_libs.sources.zotero_source import ZoteroSource
from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
from database_builder_libs.stores.typedb_v2.typedb_v2_store import TypeDbDatastore

load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> dict:
    return {
        "pdf_path": Path(require_env("PDF_PATH")),
        "openai_host": require_env("OPENAI_HOST"),
        "openai_key": require_env("OPENAI_API_KEY"),
        "embedding_model": require_env("OPENAI_EMBEDDING_MODEL"),
        "typedb_uri": require_env("TYPEDB_URI"),
        "typedb_database": require_env("TYPEDB_DATABASE"),
        "typedb_schema": require_env("TYPEDB_SCHEMA_PATH"),
        "zotero_library_id": require_env("ZOTERO_LIBRARY_ID"),
        "zotero_api_key": require_env("ZOTERO_API_KEY"),
        "zotero_collection_id": require_env("ZOTERO_COLLECTION_ID"),
    }


def parse_document(pdf_path: Path):
    extractor = TextStructureExtractor()
    doc = extractor.convert(str(pdf_path))
    sections = extractor.extract_sections(doc)
    return doc, sections


def extract_metadata(pdf_path: Path, doc, config: dict, zotero_item: dict[str, Any]):

    zotero_meta = ZoteroMetadataExtractor().extract(zotero_entry=zotero_item)

    openai_client = OpenAI(
        base_url=config["openai_host"],
        api_key=config["openai_key"],
    )

    extractor = TextMetadataExtractor(
        llm_client=openai_client,
        llm_model="google/gemma-2-9b-it-fast",
    )

    return extractor.extract(
        pdf_path=str(pdf_path),
        doc=doc,
        meta=zotero_meta,
    )


def extract_chunks(sections, document_id: str):
    return TextChunkExtractor().extract_chunks(sections, document_id=document_id)


def embed_chunks(chunks, config):

    embedder = ChunkEmbedder(
        OpenAICompatibleEmbeddingModel(
            base_url=config["openai_host"],
            api_key=config["openai_key"],
            model=config["embedding_model"],
        )
    )

    return embedder.embed(chunks)


def store_vectors(chunks):

    qdrant = QdrantDatastore()

    qdrant.connect(
        {
            "url": "http://localhost:6333",
            "collection": "knowledge_base",
            "vector_size": 4096,
        }
    )

    qdrant.store_chunks(chunks)


def store_graph(nodes, config):

    typedb = TypeDbDatastore()

    typedb.connect(
        {
            "uri": config["typedb_uri"],
            "database": config["typedb_database"],
            "schema_path": config["typedb_schema"],
        }
    )

    for node in nodes:
        typedb.store_node(node)

    return typedb


def print_summary(metadata, sections, chunks):

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


def main():

    config = load_config()

    zot = ZoteroSource()
    zot.connect(
        {
            "library_id": config["zotero_library_id"],
            "library_type": "group",
            "api_key": config["zotero_api_key"],
        }
    )

    sync = PartialSync()

    last_sync = sync.start_sync("Zotero")

    artifacts = zot.get_list_artefacts(last_synced=last_sync)

    sync.finish_sync("Zotero", artifacts)

    metadata_items = zot.get_all_documents_metadata(
        collection_id=config["zotero_collection_id"]
    )

    for item in metadata_items:

        item_key = item["key"]

        zot.download_zotero_item(
            item_id=item_key,
            download_path=config["pdf_path"],
        )

        pdf_path = config["pdf_path"] / f"{item_key}.pdf"

        if not pdf_path.exists():
            continue

        doc, sections = parse_document(pdf_path)

        metadata = extract_metadata(pdf_path, doc, config, item)

        chunks = extract_chunks(sections, document_id=item_key)

        chunks = embed_chunks(chunks, config)

        store_vectors(chunks)

        nodes = MetadataNodeExporter().export([metadata])

        typedb = store_graph(nodes, config)

        print_nodes(nodes)

        print_summary(metadata, sections, chunks)

    print("\nRetrieved nodes from TypeDB")

    typedb = TypeDbDatastore()

    typedb.connect(
        {
            "uri": config["typedb_uri"],
            "database": config["typedb_database"],
            "schema_path": config["typedb_schema"],
        }
    )

    retrieved = typedb.get_nodes("entity=textdocument&include=relations")

    print_nodes(retrieved)


if __name__ == "__main__":
    main()
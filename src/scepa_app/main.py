from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .document_parsing.extraction.extract_text_chunks import TextChunkExtractor
from .document_parsing.extraction.extract_text_structure import TextStructureExtractor
from .document_parsing.extraction.extract_text_metadata import TextMetadataExtractor

from .document_parsing.embedding.embed_chunks import ChunkEmbedder
from .document_parsing.embedding.openai_embedding_model import OpenAICompatibleEmbeddingModel

from .graph.graph_from_metadata import MetadataNodeExporter

from database_builder_libs.stores.typedb_v2.typedb_v2_store import TypeDbDatastore
from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
from openai import OpenAI
from .util.node_util import print_nodes

load_dotenv()


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> dict:
    return {
        "pdf_path": Path(os.getenv("PDF_PATH", "PDF_INPUT/document.pdf")),
        "document_id": os.getenv("DOCUMENT_ID"),
        "openai_host": require_env("OPENAI_HOST"),
        "openai_key": require_env("OPENAI_API_KEY"),
        "embedding_model": require_env("OPENAI_EMBEDDING_MODEL"),
        "typedb_uri": require_env("TYPEDB_URI"),
        "typedb_database": require_env("TYPEDB_DATABASE"),
        "typedb_schema": require_env("TYPEDB_SCHEMA_PATH"),
    }


# ---------------------------------------------------------
# Extraction
# ---------------------------------------------------------

def parse_document(pdf_path: Path):
    extractor = TextStructureExtractor()
    doc = extractor.convert(pdf_path=str(pdf_path))
    sections = extractor.extract_sections(doc)
    return doc, sections

def extract_metadata(pdf_path: Path, doc, config: dict):

    openai_client = OpenAI(
        base_url=config["openai_host"],
        api_key=config["openai_key"],
    )

    extractor = TextMetadataExtractor(
        llm_client=openai_client,
        llm_model="google/gemma-2-9b-it-fast"
    )

    return extractor.extract(
        pdf_path=str(pdf_path),
        doc=doc
    )

def extract_chunks(sections, document_id: str):
    extractor = TextChunkExtractor()
    return extractor.extract_chunks(sections, document_id=document_id)


# ---------------------------------------------------------
# Embedding
# ---------------------------------------------------------

def embed_chunks(chunks, config):
    embedder = ChunkEmbedder(
        OpenAICompatibleEmbeddingModel(
            base_url=config["openai_host"],
            api_key=config["openai_key"],
            model=config["embedding_model"],
        )
    )

    return embedder.embed(chunks)


# ---------------------------------------------------------
# Storage
# ---------------------------------------------------------

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
    typedb.remove_nodes("entity=textdocument", allow_multiple=True)
    typedb.remove_nodes("entity=person", allow_multiple=True)
    for node in nodes:
        typedb.store_node(node)

    return typedb


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def print_summary(metadata, sections, chunks):
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


# ---------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------

def main() -> None:
    config = load_config()

    pdf_path: Path = config["pdf_path"]

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path.resolve()}")

    # Parse document
    doc, sections = parse_document(pdf_path)

    # Metadata
    metadata = extract_metadata(pdf_path, doc, config)

    # Chunks
    chunks = extract_chunks(
        sections,
        document_id=config["document_id"] or pdf_path.stem,
    )

    # Embeddings
    chunks = embed_chunks(chunks, config)

    # Vector store
    store_vectors(chunks)

    # Graph nodes
    nodes = MetadataNodeExporter().export([metadata])

    print(f"Generated {len(nodes)} nodes")

    # Graph storage
    typedb = store_graph(nodes, config)

    print(f"Stored {len(nodes)} nodes in TypeDB")
    print("\nGenerated Nodes")
    print_nodes(nodes)

    # Summary
    print_summary(metadata, sections, chunks)

    # Retrieve nodes
    print("\nRetrieved nodes from TypeDB")
    print("-----------------------------")

    retrieved = typedb.get_nodes("entity=textdocument&include=relations")
    print_nodes(retrieved)


if __name__ == "__main__":
    main()
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from scepa_app.util.metadata_util import extract_zotero_metadata, merge_zotero_into_content, normalize_metadata, sanitize_metadata

from .graph.graph_from_metadata import MetadataNodeExporter
from .util.node_util import print_nodes
from .util.partial_sync import PartialSync

from database_builder_libs.models.chunk import Chunk
from database_builder_libs.models.abstract_source import Content
from database_builder_libs.sources.zotero_source import ZoteroSource
from database_builder_libs.sources.pdf_source import (
    PDFSource,
    SectionsConfig,
    FieldExtractionConfig,
    OrderedStrategyConfig,
    ExtractionStrategy,
)
from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore
from database_builder_libs.utility.chunk.summary_and_sections import SummaryAndSectionsStrategy
from database_builder_libs.utility.embed_chunk.openai_compatible import OpenAICompatibleChunkEmbedder


load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> dict:
    return {
        "pdf_path":              Path(require_env("PDF_PATH")),
        "openai_host":           require_env("OPENAI_HOST"),
        "openai_llm_model":      require_env("OPENAI_LLM_MODEL"),
        "openai_key":            require_env("OPENAI_API_KEY"),
        "embedding_model":       require_env("OPENAI_EMBEDDING_MODEL"),
        "embedding_vector_size": require_env("EMBEDDING_VECTOR_SIZE"),
        "typedb_uri":            require_env("TYPEDB_URI"),
        "typedb_database":       require_env("TYPEDB_DATABASE"),
        "typedb_schema":         require_env("TYPEDB_SCHEMA_PATH"),
        "typedb_user":           require_env("TYPEDB_USER"),
        "typedb_password":       require_env("TYPEDB_PASSWORD"),
        "zotero_library_id":     require_env("ZOTERO_LIBRARY_ID"),
        "zotero_api_key":        require_env("ZOTERO_API_KEY"),
        "zotero_collection_id":  require_env("ZOTERO_COLLECTION_ID"),
        "qdrant_api_key":        require_env("QDRANT_API_KEY"),
        "qdrant_uri":            require_env("QDRANT_URI"),
        "qdrant_collection":     require_env("QDRANT_COLLECTION")
    }


def is_downloadable_item(zotero_content: Content) -> bool:
    """
    Check if a Zotero item has a downloadable attachment.
    
    Returns True only for items that:
    - Are of a downloadable type (journal article, book, conference paper, etc.)
    - Have attachments metadata in Zotero
    - Are not just web links or snapshots without content
    
    Skips:
    - ResearchGate links
    - Amazon links
    - PubMed links
    - Web snapshots without actual files
    - Items with no attachments
    """
    item_type = zotero_content.content.get("itemType", "")
    
    # Item types that can legitimately have PDF attachments
    downloadable_types = {
        "journalArticle",
        "book",
        "bookSection",
        "conferencePaper",
        "thesis",
        "report",
        "document",
    }
    
    # Skip if item type is not downloadable
    if item_type not in downloadable_types:
        return False
    
    # Skip if no attachments listed in Zotero
    attachments = zotero_content.content.get("attachments", [])
    if not attachments:
        return False
    
    return True


def build_pdf_source(config: dict, zotero_fields: dict[str, Any]) -> PDFSource:
    """
    Connect a PDFSource with extraction strategies tailored to what Zotero
    already provides for this specific document.

    Fields already present in Zotero are omitted from the config entirely so
    PDFSource does not extract them.  Fields missing from Zotero fall back to
    the normal LLM / DOCLING / FILE_METADATA chain.

    Field strategy logic
    --------------------
    title
        Zotero  → omit (PDFSource skips)
        Missing → LLM first (avoids watermark headers), then DOCLING

    authors
        Zotero  → omit (PDFSource skips)
        Missing → FILE_METADATA + LLM (LLM always runs to overwrite noise)

    publishing_institute
        Zotero  → omit (PDFSource skips)
        Missing → LLM first, FILE_METADATA fallback

    summary
        Zotero  → omit (PDFSource skips)
        Missing → DOCLING (abstract section detection is reliable)

    acknowledgements
        Never in Zotero → always LLM

    sections / chunks
        Always extracted from the PDF.
    """
    cfg: dict[str, Any] = {
        "folder_path":  str(config["pdf_path"]),
        "llm_base_url": config["openai_host"],
        "llm_api_key":  config["openai_key"],
        "llm_model":    config["openai_llm_model"],

        "title": FieldExtractionConfig(enabled=False) if zotero_fields["title"] else
            FieldExtractionConfig(
                strategies=OrderedStrategyConfig(
                    order=[ExtractionStrategy.LLM, ExtractionStrategy.DOCLING],
                )
            ),

        "authors": FieldExtractionConfig(enabled=False) if zotero_fields["authors"] else
            FieldExtractionConfig(
                strategies=OrderedStrategyConfig(
                    order=[ExtractionStrategy.FILE_METADATA, ExtractionStrategy.LLM],
                    stop_on_success=False,
                )
            ),

        "publishing_institute": FieldExtractionConfig(enabled=False) if zotero_fields["publishing_institute"] else
            FieldExtractionConfig(
                strategies=OrderedStrategyConfig(
                    order=[ExtractionStrategy.LLM, ExtractionStrategy.FILE_METADATA],
                )
            ),

        "summary": FieldExtractionConfig(enabled=False) if zotero_fields["summary"] else
            FieldExtractionConfig(
                strategies=OrderedStrategyConfig(
                    order=[ExtractionStrategy.DOCLING],
                )
            ),

        "acknowledgements": FieldExtractionConfig(
            strategies=OrderedStrategyConfig(order=[ExtractionStrategy.LLM])
        ),

        "sections": SectionsConfig(
            chunking_strategy=SummaryAndSectionsStrategy(),
            embedder=OpenAICompatibleChunkEmbedder(
                base_url=config["openai_host"],
                api_key=config["openai_key"],
                model=config["embedding_model"],
            ),
        ),
    }
    src = PDFSource()
    src.connect(cfg)
    return src


def build_zotero_source(config: dict) -> ZoteroSource:
    """Build Zotero source for fetching document metadata."""
    src = ZoteroSource()
    src.connect({
        "library_id":   config["zotero_library_id"],
        "library_type": "group",
        "api_key":      config["zotero_api_key"],
    })
    return src


def build_qdrant(config: dict) -> QdrantDatastore:
    """
    Build Qdrant connection with conditional HTTPS based on URI scheme.
    
    HTTPS is automatically enabled for https:// URIs,
    disabled for http:// URIs.
    """
    store = QdrantDatastore()
    enable_https = config["qdrant_uri"].startswith("https://")
    
    store.connect({
        "url":         config["qdrant_uri"],
        "collection":  config["qdrant_collection"],
        "api_key":     config["qdrant_api_key"],
        "vector_size": config["embedding_vector_size"],
        "https":       enable_https
    })
    return store


def build_typedb(config: dict) -> TypeDbDatastore:
    """
    Build TypeDB connection with conditional TLS based on URI scheme.
    
    TLS is automatically enabled for https:// URIs,
    disabled for http:// URIs.
    """
    store = TypeDbDatastore()
    enable_tls = config["typedb_uri"].startswith("https://")
    
    store.connect({
        "uri": config["typedb_uri"],
        "username": config["typedb_user"],
        "password": config["typedb_password"],
        "database": config["typedb_database"],
        "schema_path": config["typedb_schema"],
        "tls": enable_tls
    })
    return store


def store_vectors(chunks: list[Chunk], qdrant: QdrantDatastore) -> None:
    """Store document chunks in vector database."""
    qdrant.store_chunks(chunks)


def store_graph(content: Content, typedb: TypeDbDatastore, doc_hash: str | None = None) -> list:
    """
    Store content graph in TypeDB with sanitized and normalized metadata.
    
    Process:
    1. Sanitize metadata (strip HTML, remove None values)
    2. Normalize metadata (escape special characters for TypeQL)
    3. Export as graph nodes
    4. Store in TypeDB
    """
    meta = content.content.get("metadata", {})
    
    # Step 1: Sanitize (remove unwanted content)
    sanitized_meta = sanitize_metadata(meta)
    
    # Step 2: Normalize (escape special characters for TypeQL)
    # This prevents TypeQL syntax errors from quotes, apostrophes, etc.
    normalized_meta = normalize_metadata(sanitized_meta)
    
    # Update content with processed metadata
    content_copy = Content(
        date=content.date,
        id_=content.id_,
        content={**content.content, "metadata": normalized_meta}
    )
    
    # Export and store in TypeDB
    nodes = MetadataNodeExporter().export([content_copy], doc_hash=doc_hash)
    for node in nodes:
        typedb.store_node(node)
    return nodes


def print_summary(content: Content, chunks: list[Chunk]) -> None:
    """Print summary of processed document and chunks."""
    meta = content.content.get("metadata", {})
    print("\nPipeline summary")
    print("----------------")
    print(f"Title:   {meta.get('title')}")
    print(f"Authors: {meta.get('authors')}")
    print(f"Source:  {meta.get('source')}")
    print(f"Chunks:  {len(chunks)}")
    for c in chunks[:10]:
        print("-" * 60)
        print(
            f"chunk_index={c.chunk_index} "
            f"section={c.metadata.get('section_title') if c.metadata else None}"
        )
        print(c.text[:300].replace("\n", " "))


def main() -> None:
    """Main pipeline for processing documents from Zotero."""
    config = load_config()
    zot    = build_zotero_source(config)
    qdrant = build_qdrant(config)
    typedb = build_typedb(config)

    # Track documents that failed processing
    failed_documents = []
    skipped_documents = []

    # Initialize incremental sync
    sync         = PartialSync()
    last_sync    = sync.start_sync("Zotero")
    last_sync_dt = datetime.fromtimestamp(last_sync) if last_sync is not None else None

    artefacts = zot.get_list_artefacts(last_synced=last_sync_dt)
    sync.finish_sync("Zotero", artefacts)

    # Fetch Zotero content (metadata + stable IDs)
    zotero_contents = zot.get_content(artefacts)

    for zotero_content in zotero_contents:
        item_key      = zotero_content.id_
        zotero_fields = extract_zotero_metadata(zotero_content)

        print(f"\n[{item_key}] {zotero_fields.get('title', 'Unknown')}")

        if not is_downloadable_item(zotero_content):
            item_type = zotero_content.content.get("itemType", "unknown")
            skipped_documents.append({
                "item_key": item_key,
                "title": zotero_fields.get("title") or "Unknown",
                "reason": f"Item type '{item_type}' is not downloadable"
            })
            print(f"  [skip] Item type not downloadable: {item_type}")
            continue

        try:
            # 1. Download PDF from Zotero
            zot.download_zotero_item(
                item_id=item_key,
                download_path=config["pdf_path"],
            )

            pdf_path = config["pdf_path"] / f"{item_key}.pdf"
            
            if not pdf_path.exists():
                skipped_documents.append({
                    "item_key": item_key,
                    "title": zotero_fields.get("title") or "Unknown",
                    "reason": "PDF file not downloaded"
                })
                print("  [skip] No PDF file downloaded")
                continue
            
            file_size = pdf_path.stat().st_size
            if file_size == 0:
                skipped_documents.append({
                    "item_key": item_key,
                    "title": zotero_fields.get("title") or "Unknown",
                    "reason": "PDF file is empty"
                })
                print("  [skip] PDF file is empty")
                continue

            pdf_src  = build_pdf_source(config, zotero_fields)
            contents = pdf_src.get_content([
                (pdf_path.name, datetime.fromtimestamp(pdf_path.stat().st_mtime))
            ])

            if not contents:
                print("  [skip] PDFSource produced no content")
                continue

            content = merge_zotero_into_content(contents[0], zotero_fields)
            
            # Compute document hash for traceability
            meta = content.content.get("metadata", {})
            doc_hash = hashlib.sha256("|".join([
                meta.get("title") or "",
                ",".join(meta.get("authors") or []),
                meta.get("summary") or "",
            ]).encode()).hexdigest()
            
            # Add document_hash to chunk metadata for traceability
            chunks = []
            for c in content.content["chunks"]:
                c["metadata"] = c.get("metadata") or {}
                c["metadata"]["document_hash"] = doc_hash
                chunks.append(Chunk(**c))

            store_vectors(chunks, qdrant)
            nodes = store_graph(content, typedb, doc_hash=doc_hash)

            print_nodes(nodes)
            print_summary(content, chunks)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            failed_documents.append({
                "item_key": item_key,
                "title": zotero_fields.get("title") or "Unknown",
                "error": error_msg,
            })
            print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
            continue

    print("\nRetrieved nodes from TypeDB")
    retrieved = typedb.get_nodes("entity=textdocument&include=relations")
    print_nodes(retrieved)

    if skipped_documents:
        print("\n" + "=" * 80)
        print(f"ℹ️  INFO: {len(skipped_documents)} document(s) skipped (expected)")
        print("=" * 80)
        for doc in skipped_documents[:5]:  # Show first 5
            print(f"\n[{doc['item_key']}] {doc['title']}")
            print(f"  Reason: {doc['reason']}")
        if len(skipped_documents) > 5:
            print(f"\n... and {len(skipped_documents) - 5} more skipped documents")
        print("\n" + "=" * 80)

    if failed_documents:
        print("\n" + "=" * 80)
        print(f"⚠️  WARNING: {len(failed_documents)} document(s) failed to process")
        print("=" * 80)
        for doc in failed_documents:
            print(f"\n[{doc['item_key']}] {doc['title']}")
            print(f"  Error: {doc['error'][:150]}")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
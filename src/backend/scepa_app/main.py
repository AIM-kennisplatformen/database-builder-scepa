from __future__ import annotations

import json
import hashlib
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

from .graph.graph_from_metadata import MetadataNodeExporter
from .util.metadata_util import (
    extract_zotero_metadata,
    merge_zotero_into_content,
    normalize_metadata,
    sanitize_metadata,
)
from .util.node_util import print_nodes
from .util.partial_sync import PartialSync
from .settings import Settings, load_settings

from database_builder_libs.models.abstract_source import Content
from database_builder_libs.models.chunk import Chunk
from database_builder_libs.sources.zotero_source import ZoteroSource
from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore
from database_builder_libs.utility.chunk.summary_and_sections import (
    SummaryAndSectionsStrategy,
)
from database_builder_libs.utility.embed_chunk.openai_compatible import (
    OpenAICompatibleChunkEmbedder,
)

if TYPE_CHECKING:
    from database_builder_libs.models.node import Node
    from database_builder_libs.sources.pdf_source import PDFSource


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
        "openai_llm_model": require_env("OPENAI_LLM_MODEL"),
        "openai_key": require_env("OPENAI_API_KEY"),
        "embedding_model": require_env("OPENAI_EMBEDDING_MODEL"),
        "embedding_vector_size": require_env("EMBEDDING_VECTOR_SIZE"),
        "typedb_uri": require_env("TYPEDB_URI"),
        "typedb_database": require_env("TYPEDB_DATABASE"),
        "typedb_schema": require_env("TYPEDB_SCHEMA_PATH"),
        "typedb_user": require_env("TYPEDB_USER"),
        "typedb_password": require_env("TYPEDB_PASSWORD"),
        "zotero_library_id": require_env("ZOTERO_LIBRARY_ID"),
        "zotero_api_key": require_env("ZOTERO_API_KEY"),
        "zotero_collection_id": require_env("ZOTERO_COLLECTION_ID"),
        "qdrant_api_key": require_env("QDRANT_API_KEY"),
        "qdrant_uri": require_env("QDRANT_URI"),
        "qdrant_collection": require_env("QDRANT_COLLECTION"),
        "accepted_file_types": os.getenv("ACCEPTED_FILE_TYPES", "pdf,epub").split(","),
        "strict_file_types": os.getenv("STRICT_FILE_TYPES", "false").lower() == "true",
    }


def get_file_types_for_config(accepted_types: list[str]) -> list[str]:
    if isinstance(accepted_types, str):
        return [t.strip().lower() for t in accepted_types.split(",")]
    return [t.strip().lower() for t in accepted_types]


def dump_nodes(nodes: list, path: Path) -> None:
    data = [asdict(node) for node in nodes]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_nodes(path: Path) -> list[Node]:
    data = json.loads(path.read_text(encoding="utf-8"))
    from database_builder_libs.models.node import EntityType, KeyAttribute, Node, NodeId

    return [
        Node(
            id=NodeId(item["id"]),
            entity_type=EntityType(item["entity_type"]),
            key_attribute=KeyAttribute(item["key_attribute"]),
            payload_data=item.get("payload_data", {}),
            relations=tuple(item.get("relations", [])),
        )
        for item in data
    ]


def build_pdf_source(config: dict, zotero_fields: dict[str, Any]) -> PDFSource:
    from database_builder_libs.sources.pdf_source import (
        ExtractionStrategy,
        FieldExtractionConfig,
        OrderedStrategyConfig,
        PDFSource,
        SectionsConfig,
    )

    cfg: dict[str, Any] = {
        "folder_path": str(config["pdf_path"]),
        "llm_base_url": config["openai_host"],
        "llm_api_key": config["openai_key"],
        "llm_model": config["openai_llm_model"],
        "title": FieldExtractionConfig(enabled=False)
        if zotero_fields["title"]
        else FieldExtractionConfig(
            strategies=OrderedStrategyConfig(
                order=[ExtractionStrategy.LLM, ExtractionStrategy.DOCLING]
            ),
        ),
        "authors": FieldExtractionConfig(enabled=False)
        if zotero_fields["authors"]
        else FieldExtractionConfig(
            strategies=OrderedStrategyConfig(
                order=[ExtractionStrategy.FILE_METADATA, ExtractionStrategy.LLM],
                stop_on_success=False,
            ),
        ),
        "publishing_institute": FieldExtractionConfig(enabled=False)
        if zotero_fields["publishing_institute"]
        else FieldExtractionConfig(
            strategies=OrderedStrategyConfig(
                order=[ExtractionStrategy.LLM, ExtractionStrategy.FILE_METADATA]
            ),
        ),
        "summary": FieldExtractionConfig(enabled=False)
        if zotero_fields["summary"]
        else FieldExtractionConfig(
            strategies=OrderedStrategyConfig(order=[ExtractionStrategy.DOCLING]),
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
    src = ZoteroSource()
    src.connect(
        {
            "library_id": config["zotero_library_id"],
            "library_type": "group",
            "api_key": config["zotero_api_key"],
        }
    )
    return src


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


def build_qdrant(config: dict) -> QdrantDatastore:
    store = QdrantDatastore()
    enable_https = config["qdrant_uri"].startswith("https://")
    store.connect(
        {
            "url": config["qdrant_uri"],
            "collection": config["qdrant_collection"],
            "api_key": config["qdrant_api_key"],
            "vector_size": config["embedding_vector_size"],
            "https": enable_https,
        }
    )
    return store


def build_typedb(config: dict) -> TypeDbDatastore:
    store = TypeDbDatastore()
    enable_tls = config["typedb_uri"].startswith("https://")
    store.connect(
        {
            "uri": config["typedb_uri"],
            "username": config["typedb_user"],
            "password": config["typedb_password"],
            "database": config["typedb_database"],
            "schema_path": config["typedb_schema"],
            "tls": enable_tls,
        }
    )
    return store


def store_vectors(chunks: list[Chunk], qdrant: QdrantDatastore) -> None:
    qdrant.store_chunks(chunks)


def store_graph(
    content: Content, typedb: TypeDbDatastore, doc_hash: str | None = None
) -> list:
    meta = content.content.get("metadata", {})
    sanitized_meta = sanitize_metadata(meta)
    normalized_meta = normalize_metadata(sanitized_meta)

    content_copy = Content(
        date=content.date,
        id_=content.id_,
        content={**content.content, "metadata": normalized_meta},
    )
    nodes = MetadataNodeExporter().export([content_copy], doc_hash=doc_hash)

    for node in nodes:
        typedb.store_node(node)

    return nodes


def print_summary(content: Content, chunks: list[Chunk]) -> None:
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
            f"chunk_index={c.chunk_index} section={c.metadata.get('section_title') if c.metadata else None}"
        )
        print(c.text[:300].replace("\n", " "))


def process_item(
    item: dict[str, Any],
    settings: Settings,
    zot: ZoteroSource,
    qdrant: QdrantDatastore,
    typedb: TypeDbDatastore,
) -> None:
    from database_builder_libs.utility.extract.document_parser_docling import (
        DocumentParserDocling,
    )

    item_key = item["key"]

    zot.download_zotero_item(item_id=item_key, download_path=str(settings.pdf_path))

    pdf_path = settings.pdf_path / f"{item_key}.pdf"
    if not pdf_path.exists():
        return

    doc = DocumentParserDocling().parse(str(pdf_path))
    content_for_meta = Content(
        date=datetime.fromtimestamp(pdf_path.stat().st_mtime),
        id_=item_key,
        content=item,
    )
    zotero_fields = extract_zotero_metadata(content_for_meta)

    chunks = SummaryAndSectionsStrategy().chunk(
        doc.sections,
        document_id=item_key,
        summary=zotero_fields.get("summary"),
    )
    chunks = OpenAICompatibleChunkEmbedder(
        base_url=settings.openai_host,
        api_key=settings.openai_key,
        model=settings.embedding_model,
    ).embed(chunks)

    store_vectors(chunks, qdrant)
    content = Content(
        date=datetime.fromtimestamp(pdf_path.stat().st_mtime),
        id_=item_key,
        content={"metadata": zotero_fields},
    )
    nodes = MetadataNodeExporter().export([content])
    dump_nodes(nodes, settings.pdf_path / f"{item_key}_nodes.json")
    for node in nodes:
        typedb.store_node(node)

    print_nodes(nodes)
    print_summary(content, chunks)


def main() -> None:
    failed_documents = []
    skipped_documents = []

    try:
        config = load_config()

        zot = build_zotero_source(config)
        qdrant = build_qdrant(config)
        typedb = build_typedb(config)

        accepted_file_types = get_file_types_for_config(config["accepted_file_types"])
        strict_mode = config["strict_file_types"]
        allow_fallback = not strict_mode

        print("\n📁 File Type Configuration:")
        print(f"   Accepted types: {accepted_file_types}")
        print(f"   Strict mode: {strict_mode} (fallback: {allow_fallback})")
        print()

        sync = PartialSync()
        last_sync = sync.start_sync("Zotero")
        last_sync_dt = (
            datetime.fromtimestamp(last_sync) if last_sync is not None else None
        )

        artefacts = zot.get_list_artefacts(last_synced=last_sync_dt)
        sync.finish_sync("Zotero", artefacts)

        if not hasattr(zot, "get_content"):
            raise AttributeError

        zotero_contents = zot.get_content(artefacts)

        for zotero_content in zotero_contents:
            item_key = zotero_content.id_
            zotero_fields = extract_zotero_metadata(zotero_content)

            print(f"\n[{item_key}] {zotero_fields.get('title', 'Unknown')}")

            try:
                download_success = zot.download_zotero_item(
                    item_id=item_key,
                    download_path=config["pdf_path"],
                    accept_types=accepted_file_types,
                    allow_fallback=allow_fallback,
                )

                if not download_success:
                    skipped_documents.append(
                        {
                            "item_key": item_key,
                            "title": zotero_fields.get("title") or "Unknown",
                            "reason": f"No acceptable file type found (wanted: {', '.join(accepted_file_types)})",
                        }
                    )
                    print("  [skip] No acceptable file type downloaded")
                    continue

                possible_extensions = [
                    ".pdf",
                    ".epub",
                    ".docx",
                    ".doc",
                    ".txt",
                    ".html",
                ]
                pdf_path = None

                for ext in possible_extensions:
                    candidate = config["pdf_path"] / f"{item_key}{ext}"
                    if candidate.exists():
                        pdf_path = candidate
                        break

                if pdf_path is None:
                    skipped_documents.append(
                        {
                            "item_key": item_key,
                            "title": zotero_fields.get("title") or "Unknown",
                            "reason": "Downloaded file not found on disk",
                        }
                    )
                    print("  [skip] Downloaded file not found")
                    continue

                if pdf_path.stat().st_size == 0:
                    skipped_documents.append(
                        {
                            "item_key": item_key,
                            "title": zotero_fields.get("title") or "Unknown",
                            "reason": "Downloaded file is empty",
                        }
                    )
                    print(f"  [skip] Downloaded file is empty ({pdf_path.name})")
                    continue

                print(f"  ✓ Downloaded: {pdf_path.name}")

                pdf_src = build_pdf_source(config, zotero_fields)
                contents = pdf_src.get_content(
                    [(pdf_path.name, datetime.fromtimestamp(pdf_path.stat().st_mtime))]
                )

                if not contents:
                    print("  [skip] PDFSource produced no content")
                    continue

                content = merge_zotero_into_content(contents[0], zotero_fields)
                meta = content.content.get("metadata", {})
                doc_hash = hashlib.sha256(
                    "|".join(
                        [
                            meta.get("title") or "",
                            ",".join(meta.get("authors") or []),
                            meta.get("summary") or "",
                        ]
                    ).encode()
                ).hexdigest()

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
                failed_documents.append(
                    {
                        "item_key": item_key,
                        "title": zotero_fields.get("title") or "Unknown",
                        "error": f"{type(e).__name__}: {str(e)}",
                    }
                )
                print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
                continue
    except (RuntimeError, AttributeError):
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

    if skipped_documents:
        print("\n" + "=" * 80)
        print(f"ℹ️  INFO: {len(skipped_documents)} document(s) skipped (expected)")
        print("=" * 80)
        for doc in skipped_documents[:5]:
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

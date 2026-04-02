from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

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


# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> dict:
    return {
        "pdf_path":             Path(require_env("PDF_PATH")),
        "openai_host":          require_env("OPENAI_HOST"),
        "openai_key":           require_env("OPENAI_API_KEY"),
        "embedding_model":      require_env("OPENAI_EMBEDDING_MODEL"),
        "typedb_uri":           require_env("TYPEDB_URI"),
        "typedb_database":      require_env("TYPEDB_DATABASE"),
        "typedb_schema":        require_env("TYPEDB_SCHEMA_PATH"),
        "zotero_library_id":    require_env("ZOTERO_LIBRARY_ID"),
        "zotero_api_key":       require_env("ZOTERO_API_KEY"),
        "zotero_collection_id": require_env("ZOTERO_COLLECTION_ID"),
    }


# --------------------------------------------------------------------------- #
# Zotero metadata helpers                                                      #
# --------------------------------------------------------------------------- #

def _zotero_nonempty(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _zotero_format_name(creator: dict) -> str:
    """Format a Zotero creator dict as 'Last, First'."""
    if "name" in creator:
        return creator["name"].strip()
    last  = (creator.get("lastName")  or "").strip()
    first = (creator.get("firstName") or "").strip()
    if last and first:
        return f"{last}, {first}"
    return last or first


def extract_zotero_metadata(zotero_content: Content) -> dict[str, Any]:
    """
    Pull the fields we care about out of a Zotero Content object.

    ZoteroSource.get_content() sets Content.content = item["data"], so the
    dict is already flat — title, creators, publisher, etc. are top-level keys.

    Returns a dict with the same field names used in the PDF metadata dict so
    it can be merged directly into Content.content["metadata"]:

        title, authors, publishing_institute, summary, keywords
    """
    data = zotero_content.content

    authors = [
        _zotero_format_name(c)
        for c in (data.get("creators") or [])
        if c.get("creatorType") in ("author", "editor")
        and "name" not in c  # single "name" field = organisation, not a person
    ] or None

    publishing_institute = (
        _zotero_nonempty(data.get("institution"))
        or _zotero_nonempty(data.get("publisher"))
    )

    tags = [t["tag"] for t in (data.get("tags") or []) if t.get("tag")]

    return {
        "title":                _zotero_nonempty(data.get("title")),
        "authors":              authors,
        "publishing_institute": {"name": publishing_institute} if publishing_institute else None,
        "summary":              _zotero_nonempty(data.get("abstractNote")),
        "keywords":             tags or None,
    }


# --------------------------------------------------------------------------- #
# Infrastructure                                                               #
# --------------------------------------------------------------------------- #

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
    # Fields Zotero already supplies are disabled so PDFSource does not
    # extract them.  Omitting a field is not enough — PDFDocumentConfig
    # has a default_factory for every field, so an absent key silently
    # falls back to the default extraction strategy.
    cfg: dict[str, Any] = {
        "folder_path":  str(config["pdf_path"]),
        "llm_base_url": config["openai_host"],
        "llm_api_key":  config["openai_key"],
        "llm_model":    "google/gemma-2-9b-it-fast",

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

        # acknowledgements — never in Zotero, always extract
        "acknowledgements": FieldExtractionConfig(
            strategies=OrderedStrategyConfig(order=[ExtractionStrategy.LLM])
        ),

        # sections / chunking — always from PDF
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
    src.connect({
        "library_id":   config["zotero_library_id"],
        "library_type": "group",
        "api_key":      config["zotero_api_key"],
    })
    return src


def build_qdrant() -> QdrantDatastore:
    store = QdrantDatastore()
    store.connect({
        "url":         "http://dbscepadev.mads-han.src.surf-hosted.nl:6333",
        "collection":  "knowledge_base",
        "vector_size": 4096,
    })
    return store


def build_typedb(config: dict) -> TypeDbDatastore:
    store = TypeDbDatastore()
    store.connect(
        {
            "uri": config["typedb_uri"],
            "username": "admin",
            "password": "password",
            "database": config["typedb_database"],
            "schema_path": config["typedb_schema"],
        }
    )
    return store


# --------------------------------------------------------------------------- #
# Zotero metadata merge                                                        #
# --------------------------------------------------------------------------- #

def merge_zotero_into_content(
    pdf_content: Content,
    zotero_fields: dict[str, Any],
) -> Content:
    """
    Overlay Zotero-sourced fields onto the PDF Content's metadata dict.

    Only non-None Zotero fields are written; PDF-extracted values are kept
    for everything else.  The ``source`` tracking dict is updated accordingly.
    """
    meta   = dict(pdf_content.content.get("metadata", {}))
    source = dict(meta.get("source", {}))

    for field_name, value in zotero_fields.items():
        if value is not None:
            meta[field_name]    = value
            source[field_name]  = "zotero"

    meta["source"] = source

    updated = dict(pdf_content.content)
    updated["metadata"] = meta

    return Content(date=pdf_content.date, id_=pdf_content.id_, content=updated)


# --------------------------------------------------------------------------- #
# Storage                                                                      #
# --------------------------------------------------------------------------- #

def store_vectors(chunks: list[Chunk], qdrant: QdrantDatastore) -> None:
    qdrant.store_chunks(chunks)


def store_graph(content: Content, typedb: TypeDbDatastore, doc_hash: str | None = None) -> list:
    nodes = MetadataNodeExporter().export([content], doc_hash=doc_hash)
    for node in nodes:
        typedb.store_node(node)
    return nodes


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #

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
            f"chunk_index={c.chunk_index} "
            f"section={c.metadata.get('section_title') if c.metadata else None}"
        )
        print(c.text[:300].replace("\n", " "))


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def main() -> None:
    config = load_config()
    zot    = build_zotero_source(config)
    qdrant = build_qdrant()
    typedb = build_typedb(config)

    # ── Incremental sync cursor ───────────────────────────────────────────────
    sync         = PartialSync()
    last_sync    = sync.start_sync("Zotero")
    last_sync_dt = datetime.fromtimestamp(last_sync) if last_sync is not None else None

    artefacts = zot.get_list_artefacts(last_synced=last_sync_dt)
    sync.finish_sync("Zotero", artefacts)

    # ── Fetch Zotero Content objects (metadata + stable IDs) ─────────────────
    zotero_contents = zot.get_content(artefacts[:5])

    for zotero_content in zotero_contents:
        item_key      = zotero_content.id_
        zotero_fields = extract_zotero_metadata(zotero_content)

        print(
            f"\n[{item_key}] Zotero supplies: "
            + (", ".join(k for k, v in zotero_fields.items() if v is not None) or "nothing")
        )

        # 1. Download PDF from Zotero
        zot.download_zotero_item(
            item_id=item_key,
            download_path=config["pdf_path"],
        )

        pdf_path = config["pdf_path"] / f"{item_key}.pdf"
        if not pdf_path.exists():
            print(f"[skip] No PDF downloaded for {item_key}")
            continue

        # 2. Build a PDFSource configured for this document's specific gaps,
        #    then parse + chunk + embed
        pdf_src  = build_pdf_source(config, zotero_fields)
        contents = pdf_src.get_content([
            (pdf_path.name, datetime.fromtimestamp(pdf_path.stat().st_mtime))
        ])

        if not contents:
            print(f"[skip] PDFSource produced no content for {item_key}")
            continue

        # 3. Overlay Zotero metadata on top of whatever PDFSource produced
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

        # 4. Store
        store_vectors(chunks, qdrant)
        nodes = store_graph(content, typedb, doc_hash=doc_hash)

        # 5. Report
        print_nodes(nodes)
        print_summary(content, chunks)

    # ── Read-back from TypeDB ─────────────────────────────────────────────────
    print("\nRetrieved nodes from TypeDB")
    retrieved = typedb.get_nodes("entity=textdocument&include=relations")
    print_nodes(retrieved)


if __name__ == "__main__":
    main()
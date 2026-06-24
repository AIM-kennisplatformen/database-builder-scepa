"""Ingestion endpoint — runs the parsing/embedding/storage pipeline in a background thread."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter

from .models import IngestResponse, IngestResult, QueueStatus
from .upload import UPLOAD_DIR, _load_registry, _save_registry

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)


def _run_ingestion() -> IngestResponse:
    # Lazy imports heavy ML libs only loaded when actually ingesting
    from scepa_app.main import store_graph, store_vectors
    from scepa_app.db import connect_qdrant, connect_typedb
    from scepa_app.settings import load_settings
    from database_builder_libs.models.abstract_source import Content
    from database_builder_libs.utility.chunk.summary_and_sections import (
        SummaryAndSectionsStrategy,
    )
    from database_builder_libs.utility.embed_chunk.openai_compatible import (
        OpenAICompatibleChunkEmbedder,
    )
    from database_builder_libs.utility.extract.document_parser_docling import (
        DocumentParserDocling,
    )

    # Get all pending documents from the JSON registry
    registry = _load_registry()
    eligible_documents = [
        (doc_hash, entry)
        for doc_hash, entry in registry.items()
        if entry["status"] in ("pending", "approved")
    ]
    if not eligible_documents:
        return IngestResponse(total=0, ingested=0, failed=0, results=[])

    # Connect to databases and embedder once for all documents
    settings = load_settings()
    qdrant = connect_qdrant(settings)
    typedb = connect_typedb(settings)
    embedder = OpenAICompatibleChunkEmbedder(
        base_url=settings.openai_host,
        api_key=settings.openai_key,
        model=settings.embedding_model,
    )
    results: list[IngestResult] = []

    for doc_hash, entry in eligible_documents:
        # Mark as ingesting so the frontend can show progress
        entry["status"] = QueueStatus.INGESTING.value
        _save_registry(registry)
        try:
            file_path = UPLOAD_DIR / f"{doc_hash}_{entry['filename']}"
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Same pipeline as main.py: parse -> chunk -> embed -> store
            doc = DocumentParserDocling().parse(str(file_path))
            chunks = SummaryAndSectionsStrategy().chunk(
                doc.sections, document_id=doc_hash
            )
            chunks = embedder.embed(chunks)
            for chunk in chunks:
                chunk.metadata = {**(chunk.metadata or {}), "document_hash": doc_hash}

            # Store vectors in Qdrant and graph nodes in TypeDB
            store_vectors(chunks, qdrant)
            content = Content(
                date=datetime.fromtimestamp(file_path.stat().st_mtime),
                id_=doc_hash,
                content={"metadata": entry["metadata"]},
            )
            nodes = store_graph(content, typedb, doc_hash=doc_hash)

            entry["status"] = QueueStatus.INGESTED.value
            _save_registry(registry)
            results.append(
                IngestResult(
                    document_hash=doc_hash,
                    filename=entry["filename"],
                    status="ingested",
                    message=f"{len(chunks)} chunks, {len(nodes)} nodes",
                )
            )
        except Exception as e:
            logger.exception("Ingestion failed for %s", doc_hash)
            entry["status"] = QueueStatus.FAILED.value
            _save_registry(registry)
            results.append(
                IngestResult(
                    document_hash=doc_hash,
                    filename=entry["filename"],
                    status="failed",
                    message=f"{type(e).__name__}: {str(e)[:200]}",
                )
            )

    return IngestResponse(
        total=len(results),
        ingested=sum(1 for result in results if result.status == "ingested"),
        failed=sum(1 for result in results if result.status == "failed"),
        results=results,
    )


@router.post("", response_model=IngestResponse, summary="Ingest all eligible documents")
async def ingest_all() -> IngestResponse:
    # Run in thread so the server stays responsive during heavy processing
    return await asyncio.get_event_loop().run_in_executor(None, _run_ingestion)

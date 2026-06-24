"""Upload endpoint — save files to disk with metadata, list/delete from queue."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ..db import (
    connect_qdrant,
    connect_typedb,
    disconnect_qdrant,
    disconnect_typedb,
    document_in_qdrant,
    document_in_typedb,
)
from ..settings import load_settings
from .models import (
    BulkUploadResponse,
    DocumentMetadata,
    DocumentUploadResult,
    QueueEntry,
    QueueStatus,
    UploadStatus,
)

if TYPE_CHECKING:
    from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
    from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
REGISTRY_PATH = Path("uploads/registry.json")
ACCEPTED_FILE_EXTENSIONS = {".pdf", ".docx", ".html", ".md", ".csv", ".pptx", ".xlsx"}
MAX_FILE_SIZE_MB = 50


def _load_registry() -> dict[str, dict]:
    """Load the upload queue from disk. Returns {hash: entry_dict}."""
    if not REGISTRY_PATH.exists():
        return {}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(registry: dict[str, dict]) -> None:
    """Persist the upload queue to disk."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


async def _process_single_file(
    file: UploadFile,
    metadata: DocumentMetadata,
    registry: dict[str, dict],
    typedb: TypeDbDatastore | None,
    qdrant: QdrantDatastore | None,
) -> DocumentUploadResult:
    filename = file.filename or "unknown"

    # Validate file extension
    ext = Path(filename).suffix.lower()
    if ext not in ACCEPTED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{ext}' not supported. Accepted: {', '.join(sorted(ACCEPTED_FILE_EXTENSIONS))}",
        )

    content = await file.read()

    # Validate file size
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File '{filename}' is {size_mb:.1f}MB, max is {MAX_FILE_SIZE_MB}MB.",
        )

    # Hash file content for deduplication
    file_hash = hashlib.sha256(content).hexdigest()

    # Reject documents that already exist in the knowledge database either as a
    # TypeDB node or as Qdrant vectors
    # Both stores are checked so the message can report exactly where it was found
    in_typedb = document_in_typedb(typedb, file_hash)
    in_qdrant = document_in_qdrant(qdrant, file_hash)
    if in_typedb or in_qdrant:
        sources = [
            name for name, hit in (("TypeDB", in_typedb), ("Qdrant", in_qdrant)) if hit
        ]
        return DocumentUploadResult(
            filename=filename,
            status=UploadStatus.DUPLICATE,
            document_hash=file_hash,
            message=f"This document already exists in the database and was not uploaded again. (found in: {', '.join(sources)})",
        )

    # Reject documents already present locally (queued or on disk). Tailor the
    # message so the user knows whether it is ingested or merely waiting in the queue.
    if file_hash in registry and (UPLOAD_DIR / f"{file_hash}_{filename}").exists():
        existing_status = registry[file_hash].get("status")
        if existing_status == QueueStatus.INGESTED.value:
            message = "This document already exists in the database and was not uploaded again."
        else:
            message = (
                "This document is already in the upload queue and was not added again."
            )
        return DocumentUploadResult(
            filename=filename,
            status=UploadStatus.DUPLICATE,
            document_hash=file_hash,
            message=message,
        )

    # Save file as {hash}_{filename} and register in queue
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / f"{file_hash}_{filename}").write_bytes(content)

    entry = QueueEntry(
        document_hash=file_hash,
        filename=filename,
        metadata=metadata,
        status=QueueStatus.PENDING,
        uploaded_at=datetime.now(timezone.utc),
    )
    registry[file_hash] = json.loads(entry.model_dump_json())

    return DocumentUploadResult(
        filename=filename,
        status=UploadStatus.SUCCESS,
        document_hash=file_hash,
        message="Uploaded and queued.",
    )


@router.post(
    "",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload documents",
)
async def upload_documents(
    files: Annotated[list[UploadFile], File(description="Document files")],
    metadata: Annotated[
        str, Form(description="JSON array of metadata objects, one per file")
    ],
) -> BulkUploadResponse:
    # Parse and validate the metadata JSON
    try:
        raw_metadata_list = json.loads(metadata)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {e}") from e

    if not isinstance(raw_metadata_list, list) or len(raw_metadata_list) != len(files):
        raise HTTPException(
            status_code=422,
            detail=f"Metadata array length ({len(raw_metadata_list) if isinstance(raw_metadata_list, list) else 'not array'}) must match files ({len(files)}).",
        )

    # Validate each metadata entry against the Pydantic model
    metadata_objects = []
    for index, raw_metadata in enumerate(raw_metadata_list):
        try:
            metadata_objects.append(DocumentMetadata.model_validate(raw_metadata))
        except Exception as e:
            raise HTTPException(
                status_code=422, detail=f"Invalid metadata at index {index}: {e}"
            ) from e

    # Process each file (validate, hash, save, queue). Open the database connections
    # once for the whole batch so the duplicate checks are done once per request. The
    # checks are best-effort: if a store is unavailable, skip it and still upload.
    registry = _load_registry()
    results: list[DocumentUploadResult] = []

    typedb: TypeDbDatastore | None = None
    qdrant: QdrantDatastore | None = None
    try:
        typedb = connect_typedb(load_settings(), apply_schema=False)
    except Exception:
        logger.warning(
            "Could not connect to TypeDB; skipping its duplicate check.", exc_info=True
        )
    try:
        qdrant = connect_qdrant(load_settings())
    except Exception:
        logger.warning(
            "Could not connect to Qdrant; skipping its duplicate check.", exc_info=True
        )

    try:
        for file, meta in zip(files, metadata_objects):
            try:
                results.append(
                    await _process_single_file(file, meta, registry, typedb, qdrant)
                )
            except HTTPException as e:
                results.append(
                    DocumentUploadResult(
                        filename=file.filename or "unknown",
                        status=UploadStatus.FAILED,
                        message=e.detail,
                    )
                )
    finally:
        disconnect_typedb(typedb)
        disconnect_qdrant(qdrant)

    _save_registry(registry)

    return BulkUploadResponse(
        total=len(results),
        successful=sum(
            1 for result in results if result.status == UploadStatus.SUCCESS
        ),
        duplicates=sum(
            1 for result in results if result.status == UploadStatus.DUPLICATE
        ),
        failed=sum(1 for result in results if result.status == UploadStatus.FAILED),
        results=results,
    )


@router.get("/queue", response_model=list[QueueEntry], summary="List upload queue")
async def list_queue() -> list[QueueEntry]:
    """Return all queued documents, newest first."""
    registry = _load_registry()
    entries = [QueueEntry.model_validate(entry) for entry in registry.values()]
    entries.sort(key=lambda entry: entry.uploaded_at, reverse=True)
    return entries


@router.patch(
    "/queue/{document_hash}",
    response_model=QueueEntry,
    summary="Update document metadata",
)
async def update_queue_entry(
    document_hash: str, metadata: DocumentMetadata
) -> QueueEntry:
    """Update the metadata of a queued document. Blocked once the document has been ingested."""
    registry = _load_registry()
    if document_hash not in registry:
        raise HTTPException(status_code=404, detail="Not found.")
    if registry[document_hash].get("status") == QueueStatus.INGESTED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit metadata of an ingested document.",
        )
    registry[document_hash]["metadata"] = json.loads(metadata.model_dump_json())
    _save_registry(registry)
    return QueueEntry.model_validate(registry[document_hash])


@router.delete(
    "/queue/{document_hash}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove from queue",
)
async def delete_queue_entry(document_hash: str) -> None:
    """Remove a document from the queue and delete its file from disk.

    Ingested documents cannot be deleted removal from databases is a separate operation.
    """
    registry = _load_registry()
    if document_hash not in registry:
        raise HTTPException(status_code=404, detail="Not found.")
    if registry[document_hash].get("status") == QueueStatus.INGESTED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an ingested document. Removal from databases is not yet supported.",
        )
    entry = registry.pop(document_hash)
    _save_registry(registry)
    file_path = UPLOAD_DIR / f"{document_hash}_{entry['filename']}"
    if file_path.exists():
        file_path.unlink()

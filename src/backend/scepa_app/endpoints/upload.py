"""Upload endpoint — save files to disk with metadata, list/delete from queue."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from .models import (
    BulkUploadResponse,
    DocumentMetadata,
    DocumentUploadResult,
    QueueEntry,
    QueueStatus,
    UploadStatus,
)

router = APIRouter(prefix="/upload", tags=["upload"])

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
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


async def _process_single_file(file: UploadFile, metadata: DocumentMetadata, registry: dict[str, dict]) -> DocumentUploadResult:
    """Validate, hash, deduplicate, save file to disk, and add to queue."""
    filename = file.filename or "unknown"

    # Validate file extension
    ext = Path(filename).suffix.lower()
    if ext not in ACCEPTED_FILE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"File type '{ext}' not supported. Accepted: {', '.join(sorted(ACCEPTED_FILE_EXTENSIONS))}")

    content = await file.read()

    # Validate file size
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"File '{filename}' is {size_mb:.1f}MB, max is {MAX_FILE_SIZE_MB}MB.")

    # Hash file content for deduplication
    file_hash = hashlib.sha256(content).hexdigest()

    # Skip if already uploaded
    if file_hash in registry:
        return DocumentUploadResult(filename=filename, status=UploadStatus.DUPLICATE, document_hash=file_hash, message="Document already exists.")

    # Save file as {hash}_{filename} and register in queue
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / f"{file_hash}_{filename}").write_bytes(content)

    entry = QueueEntry(document_hash=file_hash, filename=filename, metadata=metadata, status=QueueStatus.PENDING, uploaded_at=datetime.now(timezone.utc))
    registry[file_hash] = json.loads(entry.model_dump_json())

    return DocumentUploadResult(filename=filename, status=UploadStatus.SUCCESS, document_hash=file_hash, message="Uploaded and queued.")


@router.post("", response_model=BulkUploadResponse, status_code=status.HTTP_201_CREATED, summary="Upload documents")
async def upload_documents(
    files: Annotated[list[UploadFile], File(description="Document files")],
    metadata: Annotated[str, Form(description="JSON array of metadata objects, one per file")],
) -> BulkUploadResponse:
    """Accept one or more files with a JSON metadata array. Each file gets its own metadata entry."""
    # Parse and validate the metadata JSON
    try:
        metadata_list_raw = json.loads(metadata)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {e}") from e

    if not isinstance(metadata_list_raw, list) or len(metadata_list_raw) != len(files):
        raise HTTPException(status_code=422, detail=f"Metadata array length ({len(metadata_list_raw) if isinstance(metadata_list_raw, list) else 'not array'}) must match files ({len(files)}).")

    # Validate each metadata entry against the Pydantic model
    metadata_objects = []
    for i, raw in enumerate(metadata_list_raw):
        try:
            metadata_objects.append(DocumentMetadata.model_validate(raw))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid metadata at index {i}: {e}") from e

    # Process each file (validate, hash, save, queue)
    registry = _load_registry()
    results: list[DocumentUploadResult] = []

    for file, meta in zip(files, metadata_objects):
        try:
            results.append(await _process_single_file(file, meta, registry))
        except HTTPException as e:
            results.append(DocumentUploadResult(filename=file.filename or "unknown", status=UploadStatus.FAILED, message=e.detail))

    _save_registry(registry)

    return BulkUploadResponse(
        total=len(results),
        successful=sum(1 for r in results if r.status == UploadStatus.SUCCESS),
        duplicates=sum(1 for r in results if r.status == UploadStatus.DUPLICATE),
        failed=sum(1 for r in results if r.status == UploadStatus.FAILED),
        results=results,
    )


@router.get("/queue", response_model=list[QueueEntry], summary="List upload queue")
async def list_queue() -> list[QueueEntry]:
    """Return all queued documents, newest first."""
    registry = _load_registry()
    entries = [QueueEntry.model_validate(v) for v in registry.values()]
    entries.sort(key=lambda e: e.uploaded_at, reverse=True)
    return entries


@router.delete("/queue/{document_hash}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove from queue")
async def delete_queue_entry(document_hash: str) -> None:
    """Remove a document from the queue and delete its file from disk."""
    registry = _load_registry()
    if document_hash not in registry:
        raise HTTPException(status_code=404, detail="Not found.")
    entry = registry.pop(document_hash)
    _save_registry(registry)
    file_path = UPLOAD_DIR / f"{document_hash}_{entry['filename']}"
    if file_path.exists():
        file_path.unlink()

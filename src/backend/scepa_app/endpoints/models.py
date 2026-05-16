"""Pydantic models for upload and ingestion endpoints."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    SCIENTIFIC_JOURNAL_ARTICLE = "scientificjournalarticle"
    BOOK = "book"
    BOOK_CHAPTER = "bookchapter"
    PROJECT_PROPOSAL = "projectproposal"
    BLOG_POST = "blogpost"
    NEWSPAPER_ARTICLE = "newspaperarticle"
    POLICY_PAPER = "policypaper"
    INTERVIEW = "interview"
    SCIENTIFIC_STUDY_REPORT = "scientificstudiereport"
    THESIS = "thesis"


class ContentLabel(str, Enum):
    GENERAL = "general"
    TARGET_GROUPS = "target_groups"
    BEST_PRACTICES = "best_practices"
    SCIENTIFIC_LITERATURE = "scientific_literature"
    GREY_LITERATURE = "grey_literature"
    PROJECT_REPORTS = "project_reports"
    POLICY_DOCUMENT = "policy_document"


class QueueStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    title: str = Field(..., min_length=1)
    authors: list[str] = Field(..., min_length=1)
    document_type: DocumentType
    publishing_date: date
    publishing_organization: str | None = None
    publication_medium: str | None = None
    project: str | None = None
    isbn: str | None = None
    doi: str | None = None
    url: str | None = None
    language: str | None = None
    content_labels: list[ContentLabel] = Field(..., min_length=1)


class UploadStatus(str, Enum):
    SUCCESS = "success"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class DocumentUploadResult(BaseModel):
    filename: str
    status: UploadStatus
    document_hash: str | None = None
    message: str | None = None


class BulkUploadResponse(BaseModel):
    total: int
    successful: int
    duplicates: int
    failed: int
    results: list[DocumentUploadResult]


class QueueEntry(BaseModel):
    document_hash: str
    filename: str
    metadata: DocumentMetadata
    status: QueueStatus = QueueStatus.PENDING
    uploaded_at: datetime


class IngestResult(BaseModel):
    document_hash: str
    filename: str
    status: str
    message: str | None = None


class IngestResponse(BaseModel):
    total: int
    ingested: int
    failed: int
    results: list[IngestResult]

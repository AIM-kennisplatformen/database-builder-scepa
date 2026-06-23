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


class UserpersonaLabel(str, Enum):
    """Labels mapping to the 'Userpersona' hyper-relation in the TypeDB schema."""

    TARGET_GROUPS = "target_groups"
    STRATEGIC_OVERVIEW = "strategic_overview"
    BEST_PRACTICES = "best_practices"


class KindsOfLiteratureLabel(str, Enum):
    """Labels mapping to 'discriminatory-factor-kinds-of-literature' in the TypeDB schema."""

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
    # Obligatory fields — all five must be provided for every document.
    title: str = Field(..., min_length=1)
    authors: list[str] = Field(..., min_length=1)
    document_type: DocumentType
    publishing_date: date = Field(..., description="Date the document was published.")
    publishing_organization: str = Field(..., min_length=1, description="Organization that published or commissioned the document.")
    # Optional fields.
    publication_medium: str | None = None
    project: str | None = None
    isbn: str | None = None
    doi: str | None = None
    url: str | None = None
    language: str | None = None
    userpersona_labels: list[UserpersonaLabel] = Field(default_factory=list, description="Target groups, strategic overview, and/or best practices.")
    kinds_of_literature_labels: list[KindsOfLiteratureLabel] = Field(default_factory=list, description="Scientific literature, grey literature, project reports, and/or policy documents.")


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

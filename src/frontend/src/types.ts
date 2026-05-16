export const DOCUMENT_TYPES = [
  { value: "scientificjournalarticle", label: "Scientific Journal Article" },
  { value: "book", label: "Book" },
  { value: "bookchapter", label: "Book Chapter" },
  { value: "projectproposal", label: "Project Proposal" },
  { value: "blogpost", label: "Blog Post" },
  { value: "newspaperarticle", label: "Newspaper Article" },
  { value: "policypaper", label: "Policy Paper" },
  { value: "interview", label: "Interview" },
  { value: "scientificstudiereport", label: "Scientific Study Report" },
  { value: "thesis", label: "Thesis" },
] as const;

export const CONTENT_LABELS = [
  { value: "general", label: "General" },
  { value: "target_groups", label: "Target Groups" },
  { value: "best_practices", label: "Best Practices" },
  { value: "scientific_literature", label: "Scientific Literature" },
  { value: "grey_literature", label: "Grey Literature" },
  { value: "project_reports", label: "Project Reports" },
  { value: "policy_document", label: "Policy Document" },
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number]["value"];
export type ContentLabel = (typeof CONTENT_LABELS)[number]["value"];

export interface DocumentMetadata {
  title: string;
  authors: string[];
  document_type: DocumentType;
  publishing_date: string;
  content_labels: ContentLabel[];
  publishing_organization?: string;
  publication_medium?: string;
  project?: string;
  isbn?: string;
  doi?: string;
  url?: string;
  language?: string;
}

export interface DocumentEntry {
  id: string;
  file: File | null;
  metadata: DocumentMetadata;
}

export interface UploadResult {
  filename: string;
  status: "success" | "duplicate" | "failed";
  document_hash: string | null;
  message: string | null;
}

export interface BulkUploadResponse {
  total: number;
  successful: number;
  duplicates: number;
  failed: number;
  results: UploadResult[];
}

export interface QueueEntry {
  document_hash: string;
  filename: string;
  metadata: DocumentMetadata;
  status: "pending" | "ingesting" | "ingested" | "failed";
  uploaded_at: string;
}

export interface IngestResult {
  document_hash: string;
  filename: string;
  status: string;
  message: string | null;
}

export interface IngestResponse {
  total: number;
  ingested: number;
  failed: number;
  results: IngestResult[];
}

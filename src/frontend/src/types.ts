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

/** Labels mapping to the 'Userpersona' hyper-relation in the TypeDB schema. */
export const USERPERSONA_LABELS = [
  { value: "target_groups", label: "Target Groups" },
  { value: "strategic_overview", label: "Strategic Overview" },
  { value: "best_practices", label: "Best Practices" },
] as const;

/** Labels mapping to 'discriminatory-factor-kinds-of-literature' in the TypeDB schema. */
export const KINDS_OF_LITERATURE_LABELS = [
  { value: "scientific_literature", label: "Scientific Literature" },
  { value: "grey_literature", label: "Grey Literature" },
  { value: "project_reports", label: "Project Reports" },
  { value: "policy_document", label: "Policy Document" },
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number]["value"];
export type UserpersonaLabel = (typeof USERPERSONA_LABELS)[number]["value"];
export type KindsOfLiteratureLabel = (typeof KINDS_OF_LITERATURE_LABELS)[number]["value"];

/** Document types that require a publishing date. */
export const SCIENTIFIC_DOC_TYPES: DocumentType[] = [
  "scientificjournalarticle",
  "scientificstudiereport",
  "thesis",
];

export interface DocumentMetadata {
  // Obligatory fields — all five must be filled before upload.
  title: string;
  authors: string[];
  document_type: DocumentType;
  publishing_date: string;
  publishing_organization: string;
  userpersona_labels: UserpersonaLabel[];
  kinds_of_literature_labels: KindsOfLiteratureLabel[];
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

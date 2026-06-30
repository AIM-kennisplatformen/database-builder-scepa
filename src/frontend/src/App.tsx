import { useEffect, useRef, useState } from "react";
import DocumentCard from "./DocumentCard";
import QueueView from "./QueueView";
import type { DocumentEntry, BulkUploadResponse, DocumentMetadata, ExistingInstances } from "./types";
import "./App.css";

const API_BASE = "/api/v1";
type Tab = "upload" | "queue";

/** Create a blank metadata form for a selected file. */
function createEntry(file: File): DocumentEntry {
  return {
    id: crypto.randomUUID(),
    file,
    metadata: {
      title: "",
      authors: [],
      document_type: "book",
      publishing_date: "",
      publishing_organization: "",
      userpersona_labels: [],
      kinds_of_literature_labels: [],
    },
  };
}

/** Remove empty optional fields before sending to the API. */
function stripEmpty(meta: DocumentMetadata): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(meta).filter(([, v]) => {
      if (Array.isArray(v)) return true; // always send arrays (even empty)
      return v !== undefined && v !== "";
    })
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("upload");
  const [entries, setEntries] = useState<DocumentEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<BulkUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [instances, setInstances] = useState<ExistingInstances>({ organizations: [], authors: [] });
  const fileRef = useRef<HTMLInputElement>(null);

  // Load existing TypeDB instances once so the metadata forms can suggest them
  // for reuse. Best-effort: on failure the forms fall back to plain free-text.
  useEffect(() => {
    fetch(`${API_BASE}/instances`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: ExistingInstances | null) => data && setInstances(data))
      .catch(() => {});
  }, []);

  const handleFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setEntries((prev) => [...prev, ...files.map(createEntry)]);
    setResult(null);
    setError(null);
    // Reset input so the same files can be re-selected
    if (fileRef.current) fileRef.current.value = "";
  };

  const updateEntry = (id: string, updated: DocumentEntry) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? updated : e)));
  };

  const deleteEntry = (id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  // All obligatory fields must be filled before upload is allowed:
  // title, authors, document type, publishing date, and organization.
  const canSubmit =
    !uploading &&
    entries.length > 0 &&
    entries.every(
      (e) =>
        e.file !== null &&
        e.metadata.title.trim() !== "" &&
        e.metadata.authors.length > 0 &&
        e.metadata.publishing_date !== "" &&
        e.metadata.publishing_organization.trim() !== ""
    );

  // Split the upload results so duplicates and failures can be shown as a clear
  // error callout, separate from the successful uploads.
  const okResults = result?.results.filter((r) => r.status === "success") ?? [];
  const duplicateResults = result?.results.filter((r) => r.status === "duplicate") ?? [];
  const failedResults = result?.results.filter((r) => r.status === "failed") ?? [];

  const handleSubmit = async () => {
    setUploading(true);
    setError(null);
    setResult(null);

    try {
      // Build multipart form: files[] + metadata JSON array
      const formData = new FormData();
      for (const entry of entries) {
        if (!entry.file) throw new Error("All documents must have a file.");
        formData.append("files", entry.file);
      }
      formData.append("metadata", JSON.stringify(entries.map((e) => stripEmpty(e.metadata))));

      const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Upload failed (${res.status})`);
      }

      const data: BulkUploadResponse = await res.json();
      setResult(data);
      if (data.failed === 0) setEntries([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="app">
      <h1>SCEPA Document Upload</h1>
      <p className="subtitle">Upload documents with metadata to the knowledge platform</p>

      <nav className="tabs">
        <button className={`tab ${tab === "upload" ? "tab-active" : ""}`} onClick={() => setTab("upload")}>
          Upload
        </button>
        <button className={`tab ${tab === "queue" ? "tab-active" : ""}`} onClick={() => setTab("queue")}>
          Queue &amp; Ingest
        </button>
      </nav>

      {tab === "upload" && (
        <>
          {/* Introductory text explaining the value of metadata */}
          <div className="intro-box">
            <p>
              <strong>Thank you for contributing to the SCEPA knowledge platform!</strong> By
              carefully filling in the metadata for each document you upload, you help us build a
              high-quality expert system. Your expert judgement on document type, target groups, and
              literature category directly improves how knowledge is organised and retrieved for all
              users.
            </p>
          </div>

          {/* File picker — select multiple files at once */}
          <div className="file-picker">
            <p>Select one or more files to create upload forms</p>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".pdf,.docx,.html,.md,.csv,.pptx,.xlsx"
              onChange={handleFilesSelected}
            />
          </div>

          {entries.length === 0 && (
            <p className="empty">No files selected yet. Pick files above to get started.</p>
          )}

          {entries.map((entry, i) => (
            <DocumentCard
              key={entry.id}
              entry={entry}
              index={i}
              onChange={updateEntry}
              onDelete={deleteEntry}
              instances={instances}
            />
          ))}

          {entries.length > 0 && (
            <div className="toolbar">
              <span>{entries.length} document{entries.length !== 1 ? "s" : ""} ready</span>
              <div className="spacer" />
              <button className="btn-primary" disabled={!canSubmit} onClick={handleSubmit}>
                {uploading ? "Uploading…" : "Upload all"}
              </button>
            </div>
          )}

          {error && (
            <div className="result-box result-error">
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* Clear error callout for documents that already exist or failed */}
          {result && (duplicateResults.length > 0 || failedResults.length > 0) && (
            <div className="result-box result-error">
              <strong>Some documents were not uploaded:</strong>
              <ul>
                {duplicateResults.map((r, i) => (
                  <li key={`dup-${i}`}>
                    ⚠️ <strong>{r.filename}</strong> {r.message}
                  </li>
                ))}
                {failedResults.map((r, i) => (
                  <li key={`fail-${i}`}>
                    ❌ <strong>{r.filename}</strong> {r.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Success summary */}
          {result && okResults.length > 0 && (
            <div className="result-box result-ok">
              <strong>Done!</strong> {okResults.length} document{okResults.length !== 1 ? "s" : ""} uploaded and queued.
              <ul>
                {okResults.map((r, i) => (
                  <li key={`ok-${i}`}>✓ {r.filename}</li>
                ))}
              </ul>
              <button style={{ marginTop: "0.5rem" }} onClick={() => setTab("queue")}>
                Go to Queue →
              </button>
            </div>
          )}
        </>
      )}

      {tab === "queue" && <QueueView />}
    </div>
  );
}

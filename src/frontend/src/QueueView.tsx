import { useEffect, useState } from "react";
import type { QueueEntry, IngestResponse, DocumentMetadata } from "./types";
import MetadataForm from "./MetadataForm";

const API_BASE = "/api/v1";

function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function deepCopy<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

export default function QueueView() {
  const [entries, setEntries] = useState<QueueEntry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedHash, setExpandedHash] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<DocumentMetadata | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/upload/queue`);
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      const updated: QueueEntry[] = await res.json();
      setEntries(updated);
      // If the expanded card got ingested while we were away, drop the draft
      if (expandedHash) {
        const still = updated.find((e) => e.document_hash === expandedHash);
        if (!still || still.status === "ingested") setEditDraft(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchQueue(); }, []);

  const isDeletable = (entry: QueueEntry) => entry.status !== "ingested";

  const toggle = (hash: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(hash) ? next.delete(hash) : next.add(hash);
      return next;
    });
  };

  const toggleExpand = (entry: QueueEntry) => {
    const hash = entry.document_hash;
    if (expandedHash === hash) {
      setExpandedHash(null);
      setEditDraft(null);
      setSaveError(null);
    } else {
      setExpandedHash(hash);
      if (entry.status !== "ingested") setEditDraft(deepCopy(entry.metadata));
      else setEditDraft(null);
      setSaveError(null);
    }
  };

  const selectAll = () => setSelected(new Set(entries.filter(isDeletable).map((e) => e.document_hash)));
  const selectNone = () => setSelected(new Set());

  const bulkDelete = async () => {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} document(s)?`)) return;
    for (const hash of selected) {
      await fetch(`${API_BASE}/upload/queue/${hash}`, { method: "DELETE" });
    }
    setSelected(new Set());
    setExpandedHash(null);
    setEditDraft(null);
    await fetchQueue();
  };

  const handleIngestAll = async () => {
    setIngesting(true);
    setIngestResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/ingest`, { method: "POST" });
      if (!res.ok) throw new Error(`Ingestion failed (${res.status})`);
      setIngestResult(await res.json());
      await fetchQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIngesting(false);
    }
  };

  const saveEdit = async (entry: QueueEntry) => {
    if (!editDraft) return;

    // Frontend guard: block save if the document is already ingested
    if (entry.status === "ingested") {
      setSaveError("Cannot edit metadata of an ingested document.");
      return;
    }

    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch(`${API_BASE}/upload/queue/${entry.document_hash}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editDraft),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Save failed (${res.status})`);
      }
      const updated: QueueEntry = await res.json();
      // Update the entry in place and reset draft so Save/Cancel disappear
      setEntries((prev) => prev.map((e) => e.document_hash === entry.document_hash ? updated : e));
      setEditDraft(deepCopy(updated.metadata));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const cancelEdit = (entry: QueueEntry) => {
    setEditDraft(deepCopy(entry.metadata));
    setSaveError(null);
  };

  const isDirty = (entry: QueueEntry): boolean => {
    if (!editDraft) return false;
    return JSON.stringify(editDraft) !== JSON.stringify(entry.metadata);
  };

  const canSave = (): boolean => {
    if (!editDraft) return false;
    return (
      editDraft.title.trim() !== "" &&
      editDraft.authors.length > 0 &&
      editDraft.publishing_date !== "" &&
      editDraft.publishing_organization.trim() !== ""
    );
  };

  const pendingCount = entries.filter((e) => e.status === "pending").length;

  return (
    <div>
      <div className="toolbar">
        <button onClick={selectAll}>Select all</button>
        <button onClick={selectNone}>Deselect</button>
        <button onClick={fetchQueue}>Refresh</button>
        <div className="spacer" />
        <button className="btn-danger" disabled={selected.size === 0} onClick={bulkDelete}>
          Delete selected ({selected.size})
        </button>
      </div>

      <div className="toolbar">
        <button className="btn-primary" disabled={pendingCount === 0 || ingesting} onClick={handleIngestAll}>
          {ingesting ? "Ingesting..." : `Ingest all (${pendingCount})`}
        </button>
      </div>

      {error && <div className="result-box result-error"><strong>Error:</strong> {error}</div>}

      {ingestResult && (
        <div className="result-box result-ok">
          <strong>Done:</strong> {ingestResult.ingested} ingested, {ingestResult.failed} failed
          <ul>
            {ingestResult.results.map((r, i) => (
              <li key={i}>[{r.status}] {r.filename} — {r.message}</li>
            ))}
          </ul>
        </div>
      )}

      {loading && <p className="empty">Loading...</p>}
      {!loading && entries.length === 0 && <p className="empty">Queue is empty.</p>}

      {entries.map((entry) => {
        const isExpanded = expandedHash === entry.document_hash;
        const canDelete = isDeletable(entry);
        const editable = entry.status !== "ingested";
        const dirty = isExpanded && isDirty(entry);

        return (
          <div
            key={entry.document_hash}
            className={`queue-card ${selected.has(entry.document_hash) ? "queue-card-selected" : ""} ${isExpanded ? "queue-card-expanded" : ""}`}
          >
            <div className="queue-card-row" onClick={() => toggleExpand(entry)} style={{ cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={selected.has(entry.document_hash)}
                disabled={!canDelete}
                title={canDelete ? undefined : "Ingested documents cannot be deleted from the queue"}
                onChange={() => toggle(entry.document_hash)}
                onClick={(e) => e.stopPropagation()}
              />
              <div className="queue-card-body">
                <h4>{entry.metadata.title || entry.filename}</h4>
                <div className="queue-meta">
                  <span className={`queue-status queue-status-${entry.status}`}>[{entry.status}]</span>{" "}
                  {entry.metadata.authors.join(", ")} | {humanize(entry.metadata.document_type)}
                  {entry.metadata.publishing_date && ` | ${entry.metadata.publishing_date}`}
                </div>
              </div>
              <span className={`queue-expand-icon ${isExpanded ? "queue-expand-icon-open" : ""}`}>▾</span>
            </div>

            {isExpanded && (
              <div className="queue-card-detail">
                {editable && editDraft ? (
                  <>
                    <MetadataForm
                      value={editDraft}
                      onChange={(patch) => setEditDraft((prev) => prev ? { ...prev, ...patch } : prev)}
                    />
                    {saveError && (
                      <div className="result-box result-error" style={{ marginTop: "0.5rem" }}>
                        {saveError}
                      </div>
                    )}
                    {dirty && (
                      <div className="toolbar" style={{ marginTop: "0.75rem" }}>
                        <button
                          className="btn-primary"
                          disabled={saving || !canSave()}
                          onClick={() => saveEdit(entry)}
                        >
                          {saving ? "Saving…" : "Save"}
                        </button>
                        <button disabled={saving} onClick={() => cancelEdit(entry)}>Cancel</button>
                      </div>
                    )}
                  </>
                ) : (
                  <dl className="detail-list">
                    <dt>Filename</dt>
                    <dd>{entry.filename}</dd>

                    <dt>Title</dt>
                    <dd>{entry.metadata.title || <em>—</em>}</dd>

                    <dt>Authors</dt>
                    <dd>{entry.metadata.authors.length > 0 ? entry.metadata.authors.join(", ") : <em>—</em>}</dd>

                    <dt>Document type</dt>
                    <dd>{humanize(entry.metadata.document_type)}</dd>

                    <dt>Publishing date</dt>
                    <dd>{entry.metadata.publishing_date || <em>Not specified</em>}</dd>

                    <dt>Status</dt>
                    <dd><span className={`queue-status queue-status-${entry.status}`}>{entry.status}</span></dd>

                    <dt>Uploaded at</dt>
                    <dd>{new Date(entry.uploaded_at).toLocaleString()}</dd>

                    <dt>Userpersona labels</dt>
                    <dd>
                      {entry.metadata.userpersona_labels?.length > 0
                        ? entry.metadata.userpersona_labels.map(humanize).join(", ")
                        : <em>None</em>}
                    </dd>

                    <dt>Kind of literature labels</dt>
                    <dd>
                      {entry.metadata.kinds_of_literature_labels?.length > 0
                        ? entry.metadata.kinds_of_literature_labels.map(humanize).join(", ")
                        : <em>None</em>}
                    </dd>

                    {entry.metadata.publishing_organization && (
                      <><dt>Organisation</dt><dd>{entry.metadata.publishing_organization}</dd></>
                    )}
                    {entry.metadata.publication_medium && (
                      <><dt>Publication medium</dt><dd>{entry.metadata.publication_medium}</dd></>
                    )}
                    {entry.metadata.project && (
                      <><dt>Project</dt><dd>{entry.metadata.project}</dd></>
                    )}
                    {entry.metadata.isbn && (
                      <><dt>ISBN</dt><dd>{entry.metadata.isbn}</dd></>
                    )}
                    {entry.metadata.doi && (
                      <><dt>DOI</dt><dd>{entry.metadata.doi}</dd></>
                    )}
                    {entry.metadata.url && (
                      <><dt>URL</dt><dd><a href={entry.metadata.url} target="_blank" rel="noopener noreferrer">{entry.metadata.url}</a></dd></>
                    )}
                    {entry.metadata.language && (
                      <><dt>Language</dt><dd>{entry.metadata.language}</dd></>
                    )}
                  </dl>
                )}

                <div className="detail-hash">
                  <small>Hash: {entry.document_hash}</small>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

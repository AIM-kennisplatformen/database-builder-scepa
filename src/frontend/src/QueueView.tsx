import { useEffect, useState } from "react";
import type { QueueEntry, IngestResponse } from "./types";

const API_BASE = "/api/v1";

// Shows all uploaded documents with their status. Allows bulk delete and ingest.
export default function QueueView() {
  const [entries, setEntries] = useState<QueueEntry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/upload/queue`);
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      setEntries(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchQueue(); }, []);

  const toggle = (hash: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(hash) ? next.delete(hash) : next.add(hash);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(entries.map((e) => e.document_hash)));
  const selectNone = () => setSelected(new Set());

  // Delete all selected documents from the queue and disk.
  const bulkDelete = async () => {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} document(s)?`)) return;
    for (const hash of selected) {
      await fetch(`${API_BASE}/upload/queue/${hash}`, { method: "DELETE" });
    }
    setSelected(new Set());
    await fetchQueue();
  };

  // Trigger ingestion of all pending documents.
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

      {entries.map((entry) => (
        <div key={entry.document_hash} className={`queue-card ${selected.has(entry.document_hash) ? "queue-card-selected" : ""}`}>
          <input type="checkbox" checked={selected.has(entry.document_hash)} onChange={() => toggle(entry.document_hash)} />
          <div className="queue-card-body">
            <h4>{entry.metadata.title || entry.filename}</h4>
            <div className="queue-meta">
              [{entry.status}] {entry.metadata.authors.join(", ")} | {entry.metadata.document_type} | {entry.metadata.publishing_date}
            </div>
            <div className="queue-meta">
              Labels: {entry.metadata.content_labels.join(", ")}
              {entry.metadata.publishing_organization && ` | Org: ${entry.metadata.publishing_organization}`}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

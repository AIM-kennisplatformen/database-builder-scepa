import type { DocumentEntry, DocumentType, ContentLabel } from "./types";
import { DOCUMENT_TYPES, CONTENT_LABELS } from "./types";

interface Props {
  entry: DocumentEntry;
  index: number;
  onChange: (id: string, entry: DocumentEntry) => void;
  onDelete: (id: string) => void;
}

// Metadata form for a single uploaded file.
export default function DocumentCard({ entry, index, onChange, onDelete }: Props) {
  // Merge partial metadata update into the entry.
  const update = (patch: Partial<DocumentEntry["metadata"]>) => {
    onChange(entry.id, {
      ...entry,
      metadata: { ...entry.metadata, ...patch },
    });
  };

  const handleAuthorsChange = (value: string) => {
    update({ authors: value.split(",").map((a) => a.trim()).filter(Boolean) });
  };

  const handleLabelToggle = (label: ContentLabel) => {
    const current = entry.metadata.content_labels;
    const next = current.includes(label)
      ? current.filter((l) => l !== label)
      : [...current, label];
    update({ content_labels: next });
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          {entry.file?.name ?? `Document ${index + 1}`}
        </span>
        <button className="btn-danger" onClick={() => onDelete(entry.id)}>
          Remove
        </button>
      </div>

      <div className="field">
        <label>Title *</label>
        <input
          type="text"
          placeholder="Document title"
          value={entry.metadata.title}
          onChange={(e) => update({ title: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Authors * (comma-separated)</label>
        <input
          type="text"
          placeholder="John Doe, Jane Smith"
          value={entry.metadata.authors.join(", ")}
          onChange={(e) => handleAuthorsChange(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Kind of document *</label>
        <select
          value={entry.metadata.document_type}
          onChange={(e) => update({ document_type: e.target.value as DocumentType })}
        >
          {DOCUMENT_TYPES.map((dt) => (
            <option key={dt.value} value={dt.value}>{dt.label}</option>
          ))}
        </select>
      </div>

      <div className="field">
        <label>Publishing date *</label>
        <input
          type="date"
          value={entry.metadata.publishing_date}
          onChange={(e) => update({ publishing_date: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Content labels * (select at least one)</label>
        <div className="check-grid">
          {CONTENT_LABELS.map((cl) => (
            <label key={cl.value}>
              <input
                type="checkbox"
                checked={entry.metadata.content_labels.includes(cl.value)}
                onChange={() => handleLabelToggle(cl.value)}
              />
              {cl.label}
            </label>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Publishing organisation</label>
        <input
          type="text"
          placeholder="Organisation name"
          value={entry.metadata.publishing_organization ?? ""}
          onChange={(e) => update({ publishing_organization: e.target.value || undefined })}
        />
      </div>

      {/* Collapsible section for optional metadata */}
      <details>
        <summary>More optional fields</summary>
        <div className="field">
          <label>Publication medium</label>
          <input type="text" placeholder="e.g. Journal name"
            value={entry.metadata.publication_medium ?? ""}
            onChange={(e) => update({ publication_medium: e.target.value || undefined })} />
        </div>
        <div className="field">
          <label>Project</label>
          <input type="text" placeholder="Project name"
            value={entry.metadata.project ?? ""}
            onChange={(e) => update({ project: e.target.value || undefined })} />
        </div>
        <div className="field">
          <label>ISBN</label>
          <input type="text" placeholder="978-3-16-148410-0"
            value={entry.metadata.isbn ?? ""}
            onChange={(e) => update({ isbn: e.target.value || undefined })} />
        </div>
        <div className="field">
          <label>DOI</label>
          <input type="text" placeholder="10.1234/example"
            value={entry.metadata.doi ?? ""}
            onChange={(e) => update({ doi: e.target.value || undefined })} />
        </div>
        <div className="field">
          <label>URL</label>
          <input type="url" placeholder="https://example.com"
            value={entry.metadata.url ?? ""}
            onChange={(e) => update({ url: e.target.value || undefined })} />
        </div>
        <div className="field">
          <label>Language</label>
          <input type="text" placeholder="en, nl, de…"
            value={entry.metadata.language ?? ""}
            onChange={(e) => update({ language: e.target.value || undefined })} />
        </div>
      </details>
    </div>
  );
}

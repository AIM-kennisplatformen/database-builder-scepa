import type { DocumentType, UserpersonaLabel, KindsOfLiteratureLabel, DocumentMetadata } from "./types";
import { DOCUMENT_TYPES, USERPERSONA_LABELS, KINDS_OF_LITERATURE_LABELS } from "./types";

interface Props {
  value: DocumentMetadata;
  onChange: (patch: Partial<DocumentMetadata>) => void;
}

export default function MetadataForm({ value, onChange }: Props) {
  const handleAuthorsChange = (raw: string) => {
    onChange({ authors: raw.split(",").map((a) => a.trim()).filter(Boolean) });
  };

  const handleUserpersonaToggle = (label: UserpersonaLabel) => {
    const current = value.userpersona_labels;
    onChange({
      userpersona_labels: current.includes(label)
        ? current.filter((l) => l !== label)
        : [...current, label],
    });
  };

  const handleLiteratureToggle = (label: KindsOfLiteratureLabel) => {
    const current = value.kinds_of_literature_labels;
    onChange({
      kinds_of_literature_labels: current.includes(label)
        ? current.filter((l) => l !== label)
        : [...current, label],
    });
  };

  return (
    <>
      <div className="field">
        <label>Title *</label>
        <span className="field-hint">The full title of the document as it appears on the cover or header.</span>
        <input
          type="text"
          placeholder="Document title"
          value={value.title}
          onChange={(e) => onChange({ title: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Authors * (comma-separated)</label>
        <span className="field-hint">List all authors separated by commas.</span>
        <input
          type="text"
          placeholder="John Doe, Jane Smith"
          value={value.authors.join(", ")}
          onChange={(e) => handleAuthorsChange(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Kind of document *</label>
        <span className="field-hint">Select the type that best describes this document.</span>
        <select
          value={value.document_type}
          onChange={(e) => onChange({ document_type: e.target.value as DocumentType })}
        >
          {DOCUMENT_TYPES.map((dt) => (
            <option key={dt.value} value={dt.value}>{dt.label}</option>
          ))}
        </select>
      </div>

      <div className="field">
        <label>Publishing date *</label>
        <span className="field-hint">The date the document was published.</span>
        <input
          type="date"
          value={value.publishing_date}
          onChange={(e) => onChange({ publishing_date: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Userpersona labels</label>
        <span className="field-hint">
          Does this document relate to specific target groups, strategic overviews, or best practices?
        </span>
        <div className="check-grid">
          {USERPERSONA_LABELS.map((cl) => (
            <label key={cl.value}>
              <input
                type="checkbox"
                checked={value.userpersona_labels.includes(cl.value)}
                onChange={() => handleUserpersonaToggle(cl.value)}
              />
              {cl.label}
            </label>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Kind of literature labels</label>
        <span className="field-hint">What category of literature does this document belong to?</span>
        <div className="check-grid">
          {KINDS_OF_LITERATURE_LABELS.map((cl) => (
            <label key={cl.value}>
              <input
                type="checkbox"
                checked={value.kinds_of_literature_labels.includes(cl.value)}
                onChange={() => handleLiteratureToggle(cl.value)}
              />
              {cl.label}
            </label>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Publishing organisation *</label>
        <span className="field-hint">The organisation that published or commissioned this document.</span>
        <input
          type="text"
          placeholder="Organisation name"
          value={value.publishing_organization}
          onChange={(e) => onChange({ publishing_organization: e.target.value })}
        />
      </div>

      <details>
        <summary>More optional fields</summary>
        <div className="field">
          <label>Publication medium</label>
          <span className="field-hint">Where was this document published? (e.g. journal name, website)</span>
          <input
            type="text"
            placeholder="e.g. Journal name"
            value={value.publication_medium ?? ""}
            onChange={(e) => onChange({ publication_medium: e.target.value || undefined })}
          />
        </div>
        <div className="field">
          <label>Project</label>
          <span className="field-hint">If this document is part of a project, enter the project name.</span>
          <input
            type="text"
            placeholder="Project name"
            value={value.project ?? ""}
            onChange={(e) => onChange({ project: e.target.value || undefined })}
          />
        </div>
        <div className="field">
          <label>ISBN</label>
          <input
            type="text"
            placeholder="978-3-16-148410-0"
            value={value.isbn ?? ""}
            onChange={(e) => onChange({ isbn: e.target.value || undefined })}
          />
        </div>
        <div className="field">
          <label>DOI</label>
          <input
            type="text"
            placeholder="10.1234/example"
            value={value.doi ?? ""}
            onChange={(e) => onChange({ doi: e.target.value || undefined })}
          />
        </div>
        <div className="field">
          <label>URL</label>
          <input
            type="url"
            placeholder="https://example.com"
            value={value.url ?? ""}
            onChange={(e) => onChange({ url: e.target.value || undefined })}
          />
        </div>
        <div className="field">
          <label>Language</label>
          <span className="field-hint">The language the document is written in.</span>
          <input
            type="text"
            placeholder="en, nl, de…"
            value={value.language ?? ""}
            onChange={(e) => onChange({ language: e.target.value || undefined })}
          />
        </div>
      </details>
    </>
  );
}

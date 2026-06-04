import type { DocumentEntry } from "./types";
import MetadataForm from "./MetadataForm";

interface Props {
  entry: DocumentEntry;
  index: number;
  onChange: (id: string, entry: DocumentEntry) => void;
  onDelete: (id: string) => void;
}

// Metadata form for a single uploaded file.
export default function DocumentCard({ entry, index, onChange, onDelete }: Props) {
  const update = (patch: Partial<DocumentEntry["metadata"]>) => {
    onChange(entry.id, { ...entry, metadata: { ...entry.metadata, ...patch } });
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
      <MetadataForm value={entry.metadata} onChange={update} />
    </div>
  );
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  suggestions: string[];
  listId: string;
  placeholder?: string;
}

// Text input backed by a native <datalist>: users can pick an existing instance
// from the suggestions or simply type a new value. Keeping it free-text means a
// new TypeDB thing can still be suggested (see issue #8/#14).
export default function AutocompleteInput({ value, onChange, suggestions, listId, placeholder }: Props) {
  return (
    <>
      <input
        type="text"
        list={listId}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <datalist id={listId}>
        {suggestions.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
    </>
  );
}

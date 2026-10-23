import { useState } from "react";
import type { MedicalHistoryEntry } from "../api";

interface Props {
  title: string;
  entries: MedicalHistoryEntry[];
  onAdd: (text: string) => Promise<void>;
  onDelete: (entryId: string) => Promise<void>;
}

export default function MedicalHistorySection({ title, entries, onAdd, onDelete }: Props) {
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    await onAdd(text.trim());
    setText("");
    setAdding(false);
  }

  return (
    <div className="mb-6 last:mb-0">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
        <button
          onClick={() => setAdding((v) => !v)}
          className="text-sm font-medium text-teal-700 hover:text-teal-900"
        >
          {adding ? "Cancel" : "+ Add"}
        </button>
      </div>

      {adding && (
        <form onSubmit={handleSubmit} className="mb-3 flex gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            autoFocus
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
          <button
            type="submit"
            className="rounded-lg bg-teal-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-teal-700"
          >
            Save
          </button>
        </form>
      )}

      {entries.length === 0 ? (
        <p className="text-sm text-slate-400">None recorded.</p>
      ) : (
        <ul className="space-y-1">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
            >
              <span className="text-slate-700">{entry.text}</span>
              <button
                onClick={() => onDelete(entry.id)}
                aria-label="Remove entry"
                className="text-slate-400 hover:text-red-600"
              >
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { useState } from "react";

interface Props {
  onSave: (text: string) => Promise<void>;
}

export default function CaregiverDailyNoteForm({ onSave }: Props) {
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    await onSave(text.trim());
    setText("");
    setAdding(false);
  }

  return (
    <div className="mt-3">
      <button
        onClick={() => setAdding((v) => !v)}
        className="text-sm font-medium text-teal-700 hover:text-teal-900"
      >
        {adding ? "Cancel" : "Add a note for today"}
      </button>

      {adding && (
        <form onSubmit={handleSubmit} className="mt-2 flex gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            autoFocus
            placeholder="e.g. Let's have a quiet day indoors today"
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
    </div>
  );
}

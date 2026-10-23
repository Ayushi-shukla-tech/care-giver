import type { MedicalHistory } from "../api";

function ReadOnlyList({ title, items }: { title: string; items: { id: string; text: string }[] }) {
  return (
    <div className="mb-6 last:mb-0">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400">None recorded.</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
              {item.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MedicalHistoryReadOnly({ history }: { history: MedicalHistory }) {
  return (
    <div>
      <ReadOnlyList title="Conditions" items={history.conditions} />
      <ReadOnlyList title="Allergies" items={history.allergies} />
      <ReadOnlyList title="Notes" items={history.notes} />
    </div>
  );
}

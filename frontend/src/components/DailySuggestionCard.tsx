import type { DailySuggestion } from "../api";

export default function DailySuggestionCard({ suggestion }: { suggestion: DailySuggestion | null }) {
  if (!suggestion) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-base text-slate-500">
        Loading today's activity idea…
      </div>
    );
  }

  return (
    <div className="rounded-2xl border-2 border-teal-200 bg-teal-50 p-6">
      {suggestion.weather_summary && (
        <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-teal-700">
          {suggestion.location_label} · {suggestion.weather_summary}
        </p>
      )}
      {suggestion.greeting && (
        <p className="mb-2 text-xl font-bold leading-snug text-teal-900">{suggestion.greeting}</p>
      )}
      <p className="text-base leading-relaxed text-teal-800">{suggestion.text}</p>
    </div>
  );
}

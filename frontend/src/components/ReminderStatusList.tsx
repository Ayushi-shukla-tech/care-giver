import { useState } from "react";
import type { ReminderEvent } from "../api";
import { formatIstTime } from "../istTime";

const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  pending: { label: "Pending", className: "bg-slate-100 text-slate-600" },
  alarm_fired: { label: "Ringing", className: "bg-amber-100 text-amber-700" },
  call_placed: { label: "Called patient", className: "bg-orange-100 text-orange-700" },
  acknowledged_taken: { label: "Taken", className: "bg-emerald-100 text-emerald-700" },
  acknowledged_skipped: { label: "Skipped", className: "bg-slate-200 text-slate-600" },
  escalated: { label: "Missed — escalated", className: "bg-red-100 text-red-700" },
  cancelled: { label: "Cancelled", className: "bg-slate-100 text-slate-400" },
};

const ACTIVE_STATUSES = new Set(["pending", "alarm_fired", "call_placed"]);

function ReminderRow({ reminder }: { reminder: ReminderEvent }) {
  const style = STATUS_STYLES[reminder.status] ?? {
    label: reminder.status,
    className: "bg-slate-100 text-slate-600",
  };
  return (
    <li
      data-status={reminder.status}
      className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
    >
      <span className="text-sm text-slate-700">{formatIstTime(reminder.scheduled_at)}</span>
      <span className={`rounded-full px-3 py-1 text-xs font-medium ${style.className}`}>
        {style.label}
      </span>
    </li>
  );
}

export default function ReminderStatusList({ reminders }: { reminders: ReminderEvent[] }) {
  const [historyExpanded, setHistoryExpanded] = useState(false);

  const active = reminders.filter((r) => ACTIVE_STATUSES.has(r.status));
  const history = reminders.filter((r) => !ACTIVE_STATUSES.has(r.status));

  if (reminders.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
        No reminders scheduled for this day.
      </div>
    );
  }

  return (
    <div>
      {active.length > 0 ? (
        <ul className="space-y-2">
          {active.map((r) => (
            <ReminderRow key={r.id} reminder={r} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-400">Nothing currently needs attention.</p>
      )}

      {history.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setHistoryExpanded((v) => !v)}
            className="text-sm font-medium text-slate-500 hover:text-slate-700"
          >
            {historyExpanded ? "Hide history ▲" : `Show history (${history.length}) ▼`}
          </button>
          {historyExpanded && (
            <ul className="mt-2 space-y-2">
              {history.map((r) => (
                <ReminderRow key={r.id} reminder={r} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

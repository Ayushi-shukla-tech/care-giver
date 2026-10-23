import { useState } from "react";
import { ackReminder } from "../api";
import type { ReminderEvent } from "../api";

interface Props {
  reminder: ReminderEvent;
  onAcked: () => void;
  onSnooze: () => void;
  isSnoozed: boolean;
}

const ACTIONABLE_STATUSES = ["pending", "alarm_fired", "call_placed"];

export default function PatientReminderActions({ reminder, onAcked, onSnooze, isSnoozed }: Props) {
  const [submitting, setSubmitting] = useState(false);

  async function handleAck(status: "taken" | "skipped") {
    setSubmitting(true);
    try {
      await ackReminder(reminder.id, status);
      onAcked();
    } finally {
      setSubmitting(false);
    }
  }

  if (!ACTIONABLE_STATUSES.includes(reminder.status)) {
    const label = reminder.status === "acknowledged_taken" ? "Taken ✓" : "Skipped";
    return <p className="text-xl font-medium text-slate-500">{label}</p>;
  }

  if (isSnoozed) {
    return <p className="text-xl font-medium text-slate-500">Snoozed — reminding again soon</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          onClick={() => handleAck("taken")}
          disabled={submitting}
          className="flex-1 rounded-xl bg-emerald-600 px-4 py-6 text-2xl font-bold text-white transition hover:bg-emerald-700 disabled:opacity-60"
        >
          I took it
        </button>
        <button
          onClick={() => handleAck("skipped")}
          disabled={submitting}
          className="flex-1 rounded-xl bg-slate-300 px-4 py-6 text-2xl font-bold text-slate-700 transition hover:bg-slate-400 disabled:opacity-60"
        >
          Skip
        </button>
      </div>
      <button
        onClick={onSnooze}
        disabled={submitting}
        className="w-full rounded-lg bg-slate-100 px-4 py-3 text-base font-medium text-slate-600 transition hover:bg-slate-200 disabled:opacity-60"
      >
        Remind me in 5 min
      </button>
    </div>
  );
}

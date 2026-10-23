import { useCallback, useEffect, useState } from "react";
import { createSchedule, deleteSchedule, listSchedules, updateSchedule } from "../api";
import type { Schedule } from "../api";
import Modal from "./Modal";
import ScheduleTimesForm from "./ScheduleTimesForm";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatTime(time_of_day: string): string {
  const [hourStr, minute] = time_of_day.split(":");
  const hour = Number(hourStr);
  const period = hour >= 12 ? "PM" : "AM";
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  return `${displayHour}:${minute} ${period}`;
}

function formatDays(days_of_week: string): string {
  const days = days_of_week.split(",").map(Number).sort();
  if (days.length === 7) return "Every day";
  return days.map((d) => DAY_LABELS[d]).join(", ");
}

export default function MedicineScheduleList({ medicineId }: { medicineId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [addingTime, setAddingTime] = useState(false);

  const refresh = useCallback(() => {
    listSchedules(medicineId).then(setSchedules);
  }, [medicineId]);

  useEffect(() => {
    if (expanded) refresh();
  }, [expanded, refresh]);

  async function handleDelete(scheduleId: string) {
    if (!window.confirm("Remove this reminder time?")) return;
    await deleteSchedule(scheduleId);
    refresh();
  }

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        {expanded ? "Hide schedule ▲" : "Show schedule ▼"}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {schedules.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
            >
              <span className="text-slate-700">
                ⏰ {formatTime(s.time_of_day)} · {formatDays(s.days_of_week)}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setEditingSchedule(s)}
                  className="text-teal-700 hover:text-teal-900"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(s.id)}
                  className="text-slate-400 hover:text-red-600"
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
          <button
            onClick={() => setAddingTime(true)}
            className="text-sm font-medium text-teal-700 hover:text-teal-900"
          >
            + Add another time
          </button>
        </div>
      )}

      {editingSchedule && (
        <Modal title="Edit Reminder Time" onClose={() => setEditingSchedule(null)}>
          <ScheduleTimesForm
            mode="edit"
            initial={editingSchedule}
            onSubmit={async (updates) => {
              await updateSchedule(editingSchedule.id, updates);
              setEditingSchedule(null);
              refresh();
            }}
          />
        </Modal>
      )}

      {addingTime && (
        <Modal title="Add Reminder Time" onClose={() => setAddingTime(false)}>
          <ScheduleTimesForm
            mode="create"
            onSubmit={async (entries) => {
              for (const entry of entries) {
                await createSchedule(
                  medicineId,
                  entry.time_of_day,
                  entry.days_of_week,
                  entry.call_after_minutes,
                  entry.escalate_after_minutes
                );
              }
              setAddingTime(false);
              refresh();
            }}
          />
        </Modal>
      )}
    </div>
  );
}

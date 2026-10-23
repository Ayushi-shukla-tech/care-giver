import { useEffect, useState } from "react";
import { getAdherenceCalendar, getRemindersOnDate } from "../api";
import type { DayAdherence, ReminderEvent } from "../api";
import ReminderStatusList from "./ReminderStatusList";

const STATUS_COLORS: Record<string, string> = {
  all_taken: "bg-emerald-400",
  some_missed: "bg-amber-400",
  escalated: "bg-red-500",
};

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export default function AdherenceCalendar({ patientId }: { patientId: string }) {
  const [days, setDays] = useState<Map<string, DayAdherence>>(new Map());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedReminders, setSelectedReminders] = useState<ReminderEvent[]>([]);

  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();

  useEffect(() => {
    getAdherenceCalendar(patientId).then((entries) => {
      setDays(new Map(entries.map((e) => [e.date, e])));
    });
  }, [patientId]);

  async function handleDayClick(dateStr: string) {
    setSelectedDate(dateStr);
    const reminders = await getRemindersOnDate(patientId, dateStr);
    setSelectedReminders(reminders);
  }

  const totalDays = daysInMonth(year, month);
  const cells = Array.from({ length: totalDays }, (_, i) => i + 1);

  return (
    <div>
      <div className="grid grid-cols-7 gap-2">
        {cells.map((day) => {
          const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const entry = days.get(dateStr);
          const colorClass = entry ? STATUS_COLORS[entry.status] : "bg-slate-100";
          return (
            <button
              key={dateStr}
              onClick={() => handleDayClick(dateStr)}
              className={`flex h-10 w-10 items-center justify-center rounded-lg text-xs font-medium text-white ${colorClass} ${
                !entry ? "text-slate-400" : ""
              } transition hover:opacity-80`}
            >
              {day}
            </button>
          );
        })}
      </div>

      {selectedDate && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">{selectedDate}</h3>
            <button
              onClick={() => setSelectedDate(null)}
              className="text-sm text-slate-400 hover:text-slate-600"
            >
              Close
            </button>
          </div>
          <ReminderStatusList reminders={selectedReminders} />
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import type { Schedule } from "../api";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ALL_DAYS = "0,1,2,3,4,5,6";

interface ScheduleEntry {
  time_of_day: string;
  days_of_week: string;
  call_after_minutes: number;
  escalate_after_minutes: number;
}

type Props =
  | {
      mode: "create";
      onSubmit: (entries: ScheduleEntry[]) => Promise<void>;
    }
  | {
      mode: "edit";
      initial: Schedule;
      onSubmit: (updates: ScheduleEntry) => Promise<void>;
    };

function daysToSet(daysOfWeek: string): Set<number> {
  return new Set(daysOfWeek.split(",").map(Number));
}

function daysSetToString(days: Set<number>): string {
  return Array.from(days).sort().join(",");
}

export default function ScheduleTimesForm(props: Props) {
  const initialDays = props.mode === "edit" ? daysToSet(props.initial.days_of_week) : new Set([0, 1, 2, 3, 4, 5, 6]);
  const isEveryDayInitially = initialDays.size === 7;

  const [frequency, setFrequency] = useState<"every_day" | "specific">(
    isEveryDayInitially ? "every_day" : "specific"
  );
  const [selectedDays, setSelectedDays] = useState<Set<number>>(initialDays);
  const [times, setTimes] = useState<string[]>(
    props.mode === "edit" ? [props.initial.time_of_day] : ["08:00"]
  );
  const [callAfter, setCallAfter] = useState(
    props.mode === "edit" ? props.initial.call_after_minutes : 5
  );
  const [escalateAfter, setEscalateAfter] = useState(
    props.mode === "edit" ? props.initial.escalate_after_minutes : 15
  );

  function toggleDay(day: number) {
    setSelectedDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) {
        next.delete(day);
      } else {
        next.add(day);
      }
      return next;
    });
  }

  function updateTime(index: number, value: string) {
    setTimes((prev) => prev.map((t, i) => (i === index ? value : t)));
  }

  function addTime() {
    setTimes((prev) => [...prev, "08:00"]);
  }

  function removeTime(index: number) {
    setTimes((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const daysOfWeek = frequency === "every_day" ? ALL_DAYS : daysSetToString(selectedDays);

    if (props.mode === "create") {
      const entries: ScheduleEntry[] = times.map((time_of_day) => ({
        time_of_day,
        days_of_week: daysOfWeek,
        call_after_minutes: callAfter,
        escalate_after_minutes: escalateAfter,
      }));
      await props.onSubmit(entries);
    } else {
      await props.onSubmit({
        time_of_day: times[0],
        days_of_week: daysOfWeek,
        call_after_minutes: callAfter,
        escalate_after_minutes: escalateAfter,
      });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Frequency</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setFrequency("every_day")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              frequency === "every_day"
                ? "bg-teal-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Every day
          </button>
          <button
            type="button"
            onClick={() => setFrequency("specific")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              frequency === "specific"
                ? "bg-teal-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Specific days
          </button>
        </div>
      </div>

      {frequency === "specific" && (
        <div className="flex flex-wrap gap-2">
          {DAY_LABELS.map((label, index) => (
            <button
              key={label}
              type="button"
              onClick={() => toggleDay(index)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                selectedDays.has(index)
                  ? "bg-teal-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          {props.mode === "create" ? "Times" : "Time"}
        </label>
        <div className="space-y-2">
          {times.map((time, index) => (
            <div key={index} className="flex gap-2">
              <input
                type="time"
                value={time}
                onChange={(e) => updateTime(index, e.target.value)}
                required
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              />
              {props.mode === "create" && times.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeTime(index)}
                  className="rounded-lg px-3 py-2 text-slate-400 hover:text-red-600"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        {props.mode === "create" && (
          <button
            type="button"
            onClick={addTime}
            className="mt-2 text-sm font-medium text-teal-700 hover:text-teal-900"
          >
            + Add another time
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Call after (minutes)
          </label>
          <input
            type="number"
            value={callAfter}
            onChange={(e) => setCallAfter(Number(e.target.value))}
            min={0}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Escalate after (minutes)
          </label>
          <input
            type="number"
            value={escalateAfter}
            onChange={(e) => setEscalateAfter(Number(e.target.value))}
            min={0}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>
      </div>

      <button
        type="submit"
        className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700"
      >
        {props.mode === "create" ? "Add medicine" : "Save changes"}
      </button>
    </form>
  );
}

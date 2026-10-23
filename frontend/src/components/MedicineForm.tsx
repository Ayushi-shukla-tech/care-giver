import { useState } from "react";
import { createMedicine, createSchedule } from "../api";
import ScheduleTimesForm from "./ScheduleTimesForm";

interface Props {
  patientId: string;
  onCreated: () => void;
}

export default function MedicineForm({ patientId, onCreated }: Props) {
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");

  async function handleScheduleSubmit(
    entries: {
      time_of_day: string;
      days_of_week: string;
      call_after_minutes: number;
      escalate_after_minutes: number;
    }[]
  ) {
    const medicine = await createMedicine(patientId, name, dose);
    for (const entry of entries) {
      await createSchedule(
        medicine.id,
        entry.time_of_day,
        entry.days_of_week,
        entry.call_after_minutes,
        entry.escalate_after_minutes
      );
    }
    setName("");
    setDose("");
    onCreated();
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
          <input
            placeholder="Metformin"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Dose</label>
          <input
            placeholder="500mg"
            value={dose}
            onChange={(e) => setDose(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>
      </div>

      <ScheduleTimesForm mode="create" onSubmit={handleScheduleSubmit} />
    </div>
  );
}

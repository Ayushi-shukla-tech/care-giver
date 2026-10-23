import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createPatient, listPatients } from "../api";
import type { Patient } from "../api";

export default function PatientListPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    listPatients().then(setPatients);
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const patient = await createPatient(name, phone);
    setPatients((prev) => [...prev, patient]);
    setName("");
    setPhone("");
    setShowForm(false);
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-600 text-white">
              ♥
            </div>
            <span className="text-lg font-semibold text-slate-900">CareGiver</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900">Your Patients</h1>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700"
          >
            {showForm ? "Cancel" : "+ Add patient"}
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={handleAdd}
            className="mb-6 space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
              <input
                placeholder="Grandma Jones"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Phone number</label>
              <input
                placeholder="+15551234567"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700"
            >
              Add patient
            </button>
          </form>
        )}

        {patients.length === 0 && !showForm ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
            No patients yet. Add one to get started.
          </div>
        ) : (
          <ul className="space-y-2">
            {patients.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/patients/${p.id}`}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm transition hover:border-teal-300 hover:shadow-md"
                >
                  <div>
                    <p className="font-medium text-slate-900">{p.name}</p>
                    <p className="text-sm text-slate-500">{p.phone_number}</p>
                  </div>
                  <span className="text-slate-400">→</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}

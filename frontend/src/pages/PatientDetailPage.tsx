import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  createAllergy,
  createCondition,
  createNote,
  deleteAllergy,
  deleteCondition,
  deleteMedicine,
  deleteNote,
  getDailySuggestion,
  getRemindersOnDate,
  invitePatient,
  listAllergies,
  listConditions,
  listMedicines,
  listNotes,
  listPatients,
  setCaregiverDailyNote,
} from "../api";
import type { DailySuggestion, Medicine, MedicalHistoryEntry, Patient, ReminderEvent } from "../api";
import AdherenceCalendar from "../components/AdherenceCalendar";
import CaregiverDailyNoteForm from "../components/CaregiverDailyNoteForm";
import DailySuggestionCard from "../components/DailySuggestionCard";
import DayNavigator from "../components/DayNavigator";
import MedicalHistorySection from "../components/MedicalHistorySection";
import MedicineForm from "../components/MedicineForm";
import MedicineScheduleList from "../components/MedicineScheduleList";
import Modal from "../components/Modal";
import ReminderStatusList from "../components/ReminderStatusList";
import { addDaysToIstDateString, todayIstDateString } from "../istTime";
import { useEventStream } from "../useEventStream";

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const patientId = id!;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [selectedDate, setSelectedDate] = useState(todayIstDateString());
  const [reminders, setReminders] = useState<ReminderEvent[]>([]);
  const [banner, setBanner] = useState<string | null>(null);
  const [inviteSent, setInviteSent] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [addMedicineOpen, setAddMedicineOpen] = useState(false);
  const [medicalHistoryOpen, setMedicalHistoryOpen] = useState(false);
  const [conditions, setConditions] = useState<MedicalHistoryEntry[]>([]);
  const [allergies, setAllergies] = useState<MedicalHistoryEntry[]>([]);
  const [notes, setNotes] = useState<MedicalHistoryEntry[]>([]);
  const [dailySuggestion, setDailySuggestion] = useState<DailySuggestion | null>(null);

  const refreshDailySuggestion = useCallback(() => {
    getDailySuggestion(patientId).then(setDailySuggestion);
  }, [patientId]);

  useEffect(() => {
    refreshDailySuggestion();
  }, [refreshDailySuggestion]);

  const refreshMedicalHistory = useCallback(() => {
    listConditions(patientId).then(setConditions);
    listAllergies(patientId).then(setAllergies);
    listNotes(patientId).then(setNotes);
  }, [patientId]);

  useEffect(() => {
    if (medicalHistoryOpen) refreshMedicalHistory();
  }, [medicalHistoryOpen, refreshMedicalHistory]);

  async function handleInvite() {
    await invitePatient(patientId);
    setInviteSent(true);
  }

  async function handleDeleteMedicine(medicineId: string, name: string) {
    if (!window.confirm(`Remove ${name}? This will stop future reminders for it.`)) {
      return;
    }
    await deleteMedicine(medicineId);
    listMedicines(patientId).then(setMedicines);
    refreshReminders();
  }

  const refreshReminders = useCallback(() => {
    getRemindersOnDate(patientId, selectedDate).then(setReminders);
  }, [patientId, selectedDate]);

  useEffect(() => {
    listPatients().then((patients) => {
      setPatient(patients.find((p) => p.id === patientId) ?? null);
    });
    listMedicines(patientId).then(setMedicines);
  }, [patientId]);

  useEffect(() => {
    refreshReminders();
  }, [refreshReminders]);

  const handleStreamEvent = useCallback(
    (event: { type: string; reminder_event_id: string }) => {
      if (event.type === "escalated") {
        setBanner("A dose was missed and has been escalated.");
      }
      refreshReminders();
    },
    [refreshReminders]
  );

  useEventStream(patientId, handleStreamEvent);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-4">
          <Link to="/patients" className="text-sm text-slate-500 hover:text-slate-700">
            ← Patients
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        {banner && (
          <div className="mb-6 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <span>⚠ {banner}</span>
            <button onClick={() => setBanner(null)} className="text-red-600 hover:text-red-800">
              Dismiss
            </button>
          </div>
        )}

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              {patient ? patient.name : "Patient Overview"}
            </h1>
            {patient && (
              <p className="text-sm text-slate-500">
                {patient.phone_number} · {patient.timezone}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCalendarOpen(true)}
              aria-label="Toggle adherence calendar"
              title="Adherence history"
              className="rounded-lg border border-slate-200 bg-white p-2 text-lg text-slate-500 transition hover:bg-slate-50"
            >
              📅
            </button>
            <button
              onClick={() => setMedicalHistoryOpen(true)}
              aria-label="Toggle medical history"
              title="Medical history"
              className="rounded-lg border border-slate-200 bg-white p-2 text-lg text-slate-500 transition hover:bg-slate-50"
            >
              📋
            </button>
            <Link
              to={`/patients/${patientId}/prescriptions`}
              aria-label="Prescriptions"
              title="Prescriptions"
              className="rounded-lg border border-slate-200 bg-white p-2 text-lg text-slate-500 transition hover:bg-slate-50"
            >
              💊
            </Link>
            <button
              onClick={handleInvite}
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              {inviteSent ? "Code sent ✓" : "Invite patient"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <div>
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                  Medicines
                </h2>
                <button
                  onClick={() => setAddMedicineOpen(true)}
                  className="text-sm font-medium text-teal-700 hover:text-teal-900"
                >
                  + Add medicine
                </button>
              </div>
              {medicines.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
                  No medicines added yet.
                </div>
              ) : (
                <ul className="space-y-2">
                  {medicines.map((m) => (
                    <li
                      key={m.id}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-slate-900">{m.name}</p>
                          <p className="text-sm text-slate-500">{m.dose}</p>
                        </div>
                        <button
                          onClick={() => handleDeleteMedicine(m.id, m.name)}
                          aria-label={`Remove ${m.name}`}
                          title={`Remove ${m.name}`}
                          className="rounded-lg p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                        >
                          🗑
                        </button>
                      </div>
                      <MedicineScheduleList medicineId={m.id} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <div>
            <section className="lg:sticky lg:top-6">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
                Reminders
              </h2>
              <DayNavigator
                dateString={selectedDate}
                onPrevious={() => setSelectedDate((d) => addDaysToIstDateString(d, -1))}
                onNext={() => setSelectedDate((d) => addDaysToIstDateString(d, 1))}
                nextDisabled={selectedDate >= todayIstDateString()}
              />
              <ReminderStatusList reminders={reminders} />
            </section>

            <section className="mt-6">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
                Daily Planned Activities
              </h2>
              <DailySuggestionCard suggestion={dailySuggestion} />
              <CaregiverDailyNoteForm
                onSave={async (text) => {
                  await setCaregiverDailyNote(patientId, text);
                  refreshDailySuggestion();
                }}
              />
            </section>
          </div>
        </div>
      </main>

      {calendarOpen && (
        <Modal title="Adherence History" onClose={() => setCalendarOpen(false)}>
          <AdherenceCalendar patientId={patientId} />
        </Modal>
      )}

      {addMedicineOpen && (
        <Modal title="Add Medicine" onClose={() => setAddMedicineOpen(false)}>
          <MedicineForm
            patientId={patientId}
            onCreated={() => {
              listMedicines(patientId).then(setMedicines);
              refreshReminders();
              setAddMedicineOpen(false);
            }}
          />
        </Modal>
      )}

      {medicalHistoryOpen && (
        <Modal title="Medical History" onClose={() => setMedicalHistoryOpen(false)}>
          <MedicalHistorySection
            title="Conditions"
            entries={conditions}
            onAdd={async (text) => {
              await createCondition(patientId, text);
              refreshMedicalHistory();
            }}
            onDelete={async (entryId) => {
              await deleteCondition(entryId);
              refreshMedicalHistory();
            }}
          />
          <MedicalHistorySection
            title="Allergies"
            entries={allergies}
            onAdd={async (text) => {
              await createAllergy(patientId, text);
              refreshMedicalHistory();
            }}
            onDelete={async (entryId) => {
              await deleteAllergy(entryId);
              refreshMedicalHistory();
            }}
          />
          <MedicalHistorySection
            title="Notes"
            entries={notes}
            onAdd={async (text) => {
              await createNote(patientId, text);
              refreshMedicalHistory();
            }}
            onDelete={async (entryId) => {
              await deleteNote(entryId);
              refreshMedicalHistory();
            }}
          />
        </Modal>
      )}
    </div>
  );
}

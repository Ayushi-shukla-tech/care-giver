import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  generateDailySuggestion,
  getDailySuggestionAsPatient,
  getMedicalHistory,
  getPatientToken,
  patientRemindersOnDate,
} from "../api";
import type { DailySuggestion, MedicalHistory, ReminderEvent } from "../api";
import { useReminderAlarm } from "../useReminderAlarm";
import { addDaysToIstDateString, formatIstTime, todayIstDateString } from "../istTime";
import DailySuggestionCard from "../components/DailySuggestionCard";
import DayNavigator from "../components/DayNavigator";
import EnableRemindersBanner, { attemptUnlockAudioAndSpeech } from "../components/EnableRemindersBanner";
import MedicalHistoryReadOnly from "../components/MedicalHistoryReadOnly";
import Modal from "../components/Modal";
import PatientReminderActions from "../components/PatientReminderActions";

const REMINDERS_ENABLED_KEY = "reminders_sound_enabled";
const ACTIVE_STATUSES = new Set(["pending", "alarm_fired", "call_placed"]);

function extractPatientIdFromToken(): string | null {
  return localStorage.getItem("patient_id");
}

export default function PatientTodayPage() {
  const navigate = useNavigate();
  const patientId = extractPatientIdFromToken();
  const [remindersEnabled, setRemindersEnabled] = useState(
    () => localStorage.getItem(REMINDERS_ENABLED_KEY) === "true"
  );
  const [medicalHistoryOpen, setMedicalHistoryOpen] = useState(false);
  const [medicalHistory, setMedicalHistory] = useState<MedicalHistory | null>(null);
  const [selectedDate, setSelectedDate] = useState(todayIstDateString());
  const [pastDayReminders, setPastDayReminders] = useState<ReminderEvent[]>([]);
  const [dailySuggestion, setDailySuggestion] = useState<DailySuggestion | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(false);

  const isToday = selectedDate === todayIstDateString();

  const { reminders, alarmingIds, snoozedIds, snooze, refresh } = useReminderAlarm(
    patientId ?? "",
    remindersEnabled && isToday
  );

  useEffect(() => {
    if (remindersEnabled) {
      attemptUnlockAudioAndSpeech();
    }
  }, []);

  useEffect(() => {
    if (!getPatientToken() || !patientId) {
      navigate("/pair");
    }
  }, [patientId, navigate]);

  useEffect(() => {
    if (!patientId || isToday) return;
    patientRemindersOnDate(patientId, selectedDate).then(setPastDayReminders);
  }, [patientId, selectedDate, isToday]);

  useEffect(() => {
    console.warn("[daily-suggestion] effect ran, patientId =", patientId, "isToday =", isToday);
    if (!patientId || !isToday) {
      console.warn("[daily-suggestion] bailing out early (missing patientId or not today)");
      return;
    }

    if (!("geolocation" in navigator)) {
      console.warn("[daily-suggestion] geolocation not supported by this browser, using fallback");
      getDailySuggestionAsPatient(patientId).then(setDailySuggestion);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        generateDailySuggestion(patientId, position.coords.latitude, position.coords.longitude)
          .then(setDailySuggestion)
          .catch((err) => console.error("[daily-suggestion] generate request failed", err));
      },
      (geoError) => {
        console.warn("[daily-suggestion] geolocation failed, using fallback:", geoError.code, geoError.message);
        getDailySuggestionAsPatient(patientId).then(setDailySuggestion);
      }
    );
  }, [patientId, isToday]);

  function handleToggleReminders(next: boolean) {
    setRemindersEnabled(next);
    localStorage.setItem(REMINDERS_ENABLED_KEY, String(next));
  }

  async function handleViewHealthInfo() {
    if (patientId) {
      const history = await getMedicalHistory(patientId);
      setMedicalHistory(history);
    }
    setMedicalHistoryOpen(true);
  }

  if (!getPatientToken() || !patientId) {
    return null;
  }

  const displayedReminders = isToday ? reminders : pastDayReminders;
  const activeReminders = displayedReminders.filter((r) => ACTIVE_STATUSES.has(r.status));
  const historyReminders = displayedReminders.filter((r) => !ACTIVE_STATUSES.has(r.status));

  function renderReminderCard(r: ReminderEvent) {
    const isAlarming = isToday && alarmingIds.has(r.id);
    return (
      <div
        key={r.id}
        className={`rounded-2xl border-2 p-6 shadow-sm transition ${
          isAlarming ? "animate-pulse border-red-400 bg-red-50" : "border-slate-200 bg-white"
        }`}
      >
        <p className="mb-1 text-center text-2xl font-bold text-slate-900">
          {r.medicine_name} — {r.medicine_dose}
        </p>
        <p className="mb-4 text-center text-lg text-slate-500">{formatIstTime(r.scheduled_at)}</p>
        {isToday && ACTIVE_STATUSES.has(r.status) ? (
          <PatientReminderActions
            reminder={r}
            onAcked={refresh}
            onSnooze={() => snooze(r.id)}
            isSnoozed={snoozedIds.has(r.id)}
          />
        ) : (
          <p className="text-center text-lg text-slate-500">{r.status}</p>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="fixed right-4 top-4 z-40 flex items-center gap-3">
        <button
          onClick={handleViewHealthInfo}
          aria-label="View my health info"
          title="View my health info"
          className="flex h-14 w-14 items-center justify-center rounded-full border border-slate-200 bg-white text-2xl text-slate-500 shadow-sm transition hover:bg-slate-50"
        >
          📋
        </button>
        <EnableRemindersBanner enabled={remindersEnabled} onToggle={handleToggleReminders} />
      </div>

      <div className="mx-auto max-w-md">
        <h1 className="mb-8 text-center text-3xl font-bold text-slate-900">
          Medicines
        </h1>

        {isToday && (
          <div className="mb-8">
            <DailySuggestionCard suggestion={dailySuggestion} />
          </div>
        )}

        <DayNavigator
          dateString={selectedDate}
          onPrevious={() => setSelectedDate((d) => addDaysToIstDateString(d, -1))}
          onNext={() => setSelectedDate((d) => addDaysToIstDateString(d, 1))}
          nextDisabled={isToday}
        />

        {displayedReminders.length === 0 ? (
          <p className="text-center text-xl text-slate-500">Nothing scheduled for this day.</p>
        ) : (
          <>
            {activeReminders.length > 0 ? (
              <div className="space-y-5">{activeReminders.map(renderReminderCard)}</div>
            ) : (
              <p className="text-center text-lg text-slate-400">Nothing currently needs attention.</p>
            )}

            {historyReminders.length > 0 && (
              <div className="mt-5">
                <button
                  onClick={() => setHistoryExpanded((v) => !v)}
                  className="w-full rounded-xl bg-white px-4 py-3 text-center text-base font-semibold text-slate-500 shadow-sm transition hover:bg-slate-100 hover:text-slate-700"
                >
                  {historyExpanded ? "Hide history ▲" : `Show history (${historyReminders.length}) ▼`}
                </button>
                {historyExpanded && (
                  <div className="mt-4 space-y-5">{historyReminders.map(renderReminderCard)}</div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {medicalHistoryOpen && medicalHistory && (
        <Modal title="My Health Info" onClose={() => setMedicalHistoryOpen(false)}>
          <MedicalHistoryReadOnly history={medicalHistory} />
        </Modal>
      )}
    </div>
  );
}

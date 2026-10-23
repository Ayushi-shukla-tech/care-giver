const BASE_URL = "http://localhost:8001";

export function setToken(token: string): void {
  localStorage.setItem("access_token", token);
}

export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("Content-Type", "application/json");
  return fetch(`${BASE_URL}${path}`, { ...options, headers });
}

export async function signup(email: string, password: string): Promise<{ access_token: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error("Signup failed");
  return response.json();
}

export async function login(email: string, password: string): Promise<{ access_token: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error("Login failed");
  return response.json();
}

export async function googleSignIn(idToken: string): Promise<{ access_token: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!response.ok) throw new Error("Google sign-in failed");
  return response.json();
}

export interface Patient {
  id: string;
  name: string;
  phone_number: string;
  timezone: string;
}

export async function listPatients(): Promise<Patient[]> {
  const response = await authFetch("/api/v1/patients");
  if (!response.ok) throw new Error("Failed to list patients");
  return response.json();
}

export async function createPatient(
  name: string,
  phone_number: string,
  timezone = "UTC"
): Promise<Patient> {
  const response = await authFetch("/api/v1/patients", {
    method: "POST",
    body: JSON.stringify({ name, phone_number, timezone }),
  });
  if (!response.ok) throw new Error("Failed to create patient");
  return response.json();
}

export interface Medicine {
  id: string;
  patient_id: string;
  name: string;
  dose: string;
  instructions: string | null;
}

export async function listMedicines(patientId: string): Promise<Medicine[]> {
  const response = await authFetch(`/api/v1/patients/${patientId}/medicines`);
  if (!response.ok) throw new Error("Failed to list medicines");
  return response.json();
}

export async function deleteMedicine(medicineId: string): Promise<void> {
  const response = await authFetch(`/api/v1/medicines/${medicineId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete medicine");
}

export async function createMedicine(
  patientId: string,
  name: string,
  dose: string,
  instructions?: string
): Promise<Medicine> {
  const response = await authFetch(`/api/v1/patients/${patientId}/medicines`, {
    method: "POST",
    body: JSON.stringify({ name, dose, instructions }),
  });
  if (!response.ok) throw new Error("Failed to create medicine");
  return response.json();
}

export async function createSchedule(
  medicineId: string,
  time_of_day: string,
  days_of_week: string,
  call_after_minutes = 5,
  escalate_after_minutes = 15
): Promise<void> {
  const response = await authFetch(`/api/v1/medicines/${medicineId}/schedules`, {
    method: "POST",
    body: JSON.stringify({
      time_of_day,
      days_of_week,
      call_after_minutes,
      escalate_after_minutes,
    }),
  });
  if (!response.ok) throw new Error("Failed to create schedule");
}

export interface Schedule {
  id: string;
  medicine_id: string;
  time_of_day: string;
  days_of_week: string;
  call_after_minutes: number;
  escalate_after_minutes: number;
}

export async function listSchedules(medicineId: string): Promise<Schedule[]> {
  const response = await authFetch(`/api/v1/medicines/${medicineId}/schedules`);
  if (!response.ok) throw new Error("Failed to list schedules");
  return response.json();
}

export async function updateSchedule(
  scheduleId: string,
  updates: Partial<{
    time_of_day: string;
    days_of_week: string;
    call_after_minutes: number;
    escalate_after_minutes: number;
  }>
): Promise<Schedule> {
  const response = await authFetch(`/api/v1/schedules/${scheduleId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw new Error("Failed to update schedule");
  return response.json();
}

export async function deleteSchedule(scheduleId: string): Promise<void> {
  const response = await authFetch(`/api/v1/schedules/${scheduleId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to delete schedule");
}

export interface ReminderEvent {
  id: string;
  reminder_schedule_id: string;
  scheduled_at: string;
  status: string;
  medicine_name: string;
  medicine_dose: string;
}

export async function todaysReminders(patientId: string): Promise<ReminderEvent[]> {
  const response = await authFetch(`/api/v1/patients/${patientId}/reminders/today`);
  if (!response.ok) throw new Error("Failed to fetch today's reminders");
  return response.json();
}

export function setPatientToken(token: string): void {
  localStorage.setItem("patient_access_token", token);
}

export function getPatientToken(): string | null {
  return localStorage.getItem("patient_access_token");
}

export async function patientAuthFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getPatientToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("Content-Type", "application/json");
  return fetch(`${BASE_URL}${path}`, { ...options, headers });
}

export async function verifyPatientOtp(
  phone_number: string,
  code: string
): Promise<{ access_token: string; patient_id: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/patient/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number, code }),
  });
  if (!response.ok) throw new Error("Verification failed");
  return response.json();
}

export async function invitePatient(patientId: string): Promise<void> {
  const response = await authFetch(`/api/v1/patients/${patientId}/invite`, {
    method: "POST",
  });
  if (!response.ok) throw new Error("Failed to send invite");
}

export async function patientTodaysReminders(patientId: string): Promise<ReminderEvent[]> {
  const response = await patientAuthFetch(`/api/v1/patients/${patientId}/reminders/today`);
  if (!response.ok) throw new Error("Failed to fetch reminders");
  return response.json();
}

export async function ackReminder(eventId: string, ackStatus: "taken" | "skipped"): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/v1/reminders/${eventId}/ack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: ackStatus }),
  });
  if (!response.ok) throw new Error("Failed to acknowledge reminder");
}

export interface DayAdherence {
  date: string;
  status: "all_taken" | "some_missed" | "escalated";
}

export async function getAdherenceCalendar(patientId: string): Promise<DayAdherence[]> {
  const response = await authFetch(`/api/v1/patients/${patientId}/adherence/calendar`);
  if (!response.ok) throw new Error("Failed to fetch adherence calendar");
  return response.json();
}

export async function getRemindersOnDate(patientId: string, date: string): Promise<ReminderEvent[]> {
  const response = await authFetch(`/api/v1/patients/${patientId}/reminders?date=${date}`);
  if (!response.ok) throw new Error("Failed to fetch reminders for date");
  return response.json();
}

export async function patientRemindersOnDate(patientId: string, date: string): Promise<ReminderEvent[]> {
  const response = await patientAuthFetch(`/api/v1/patients/${patientId}/reminders?date=${date}`);
  if (!response.ok) throw new Error("Failed to fetch reminders for date");
  return response.json();
}

export interface MedicalHistoryEntry {
  id: string;
  text: string;
  created_at: string;
}

export interface MedicalHistory {
  conditions: MedicalHistoryEntry[];
  allergies: MedicalHistoryEntry[];
  notes: MedicalHistoryEntry[];
}

async function listEntries(patientId: string, pathSegment: string): Promise<MedicalHistoryEntry[]> {
  const response = await authFetch(`/api/v1/patients/${patientId}/${pathSegment}`);
  if (!response.ok) throw new Error(`Failed to list ${pathSegment}`);
  return response.json();
}

async function createEntry(
  patientId: string,
  pathSegment: string,
  text: string
): Promise<MedicalHistoryEntry> {
  const response = await authFetch(`/api/v1/patients/${patientId}/${pathSegment}`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error(`Failed to create ${pathSegment} entry`);
  return response.json();
}

async function deleteEntry(pathSegment: string, entryId: string): Promise<void> {
  const response = await authFetch(`/api/v1/${pathSegment}/${entryId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error(`Failed to delete ${pathSegment} entry`);
}

export const listConditions = (patientId: string) => listEntries(patientId, "conditions");
export const createCondition = (patientId: string, text: string) =>
  createEntry(patientId, "conditions", text);
export const deleteCondition = (entryId: string) => deleteEntry("conditions", entryId);

export const listAllergies = (patientId: string) => listEntries(patientId, "allergies");
export const createAllergy = (patientId: string, text: string) =>
  createEntry(patientId, "allergies", text);
export const deleteAllergy = (entryId: string) => deleteEntry("allergies", entryId);

export const listNotes = (patientId: string) => listEntries(patientId, "notes");
export const createNote = (patientId: string, text: string) => createEntry(patientId, "notes", text);
export const deleteNote = (entryId: string) => deleteEntry("notes", entryId);

export async function getMedicalHistory(patientId: string): Promise<MedicalHistory> {
  const response = await patientAuthFetch(`/api/v1/patients/${patientId}/medical-history`);
  if (!response.ok) throw new Error("Failed to fetch medical history");
  return response.json();
}

export interface DailySuggestion {
  text: string;
  greeting: string | null;
  source: "ai" | "caregiver" | "default";
  location_label: string | null;
  weather_summary: string | null;
}

export async function generateDailySuggestion(
  patientId: string,
  latitude: number,
  longitude: number
): Promise<DailySuggestion> {
  const response = await patientAuthFetch(`/api/v1/patients/${patientId}/daily-suggestion/generate`, {
    method: "POST",
    body: JSON.stringify({ latitude, longitude }),
  });
  if (!response.ok) throw new Error("Failed to generate daily suggestion");
  return response.json();
}

export async function getDailySuggestion(patientId: string): Promise<DailySuggestion> {
  const response = await authFetch(`/api/v1/patients/${patientId}/daily-suggestion`);
  if (!response.ok) throw new Error("Failed to fetch daily suggestion");
  return response.json();
}

export async function getDailySuggestionAsPatient(patientId: string): Promise<DailySuggestion> {
  const response = await patientAuthFetch(`/api/v1/patients/${patientId}/daily-suggestion`);
  if (!response.ok) throw new Error("Failed to fetch daily suggestion");
  return response.json();
}

export async function setCaregiverDailyNote(patientId: string, text: string): Promise<DailySuggestion> {
  const response = await authFetch(`/api/v1/patients/${patientId}/daily-suggestion`, {
    method: "PUT",
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error("Failed to save daily note");
  return response.json();
}

export async function authFetchFormData(path: string, formData: FormData): Promise<Response> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(`${BASE_URL}${path}`, { method: "POST", headers, body: formData });
}

export interface PrescriptionCandidate {
  name: string;
  dose: string;
  frequency_hint: string;
  status: "pending" | "confirmed" | "skipped";
}

export interface PrescriptionImage {
  id: string;
  file_url: string;
  position: number;
}

export interface Prescription {
  id: string;
  patient_id: string;
  images: PrescriptionImage[];
  status: "pending_review" | "reviewed";
  candidates: PrescriptionCandidate[];
  uploaded_at: string;
}

export class PrescriptionRejectedError extends Error {}

export async function uploadPrescription(patientId: string, files: File[]): Promise<Prescription> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const response = await authFetchFormData(`/api/v1/patients/${patientId}/prescriptions`, formData);
  if (response.status === 422) {
    const body = await response.json().catch(() => null);
    if (typeof body?.detail === "string") {
      throw new PrescriptionRejectedError(body.detail);
    }
  }
  if (!response.ok) throw new Error("Failed to upload prescription");
  return response.json();
}

export async function listPrescriptions(patientId: string): Promise<Prescription[]> {
  const response = await authFetch(`/api/v1/patients/${patientId}/prescriptions`);
  if (!response.ok) throw new Error("Failed to list prescriptions");
  return response.json();
}

export async function getPrescription(patientId: string, prescriptionId: string): Promise<Prescription> {
  const response = await authFetch(`/api/v1/patients/${patientId}/prescriptions/${prescriptionId}`);
  if (!response.ok) throw new Error("Failed to fetch prescription");
  return response.json();
}

export async function updatePrescriptionCandidate(
  patientId: string,
  prescriptionId: string,
  index: number,
  body: { status: "confirmed" | "skipped"; name?: string; dose?: string }
): Promise<Prescription> {
  const response = await authFetch(
    `/api/v1/patients/${patientId}/prescriptions/${prescriptionId}/candidates/${index}`,
    { method: "PATCH", body: JSON.stringify(body) }
  );
  if (!response.ok) throw new Error("Failed to update candidate");
  return response.json();
}

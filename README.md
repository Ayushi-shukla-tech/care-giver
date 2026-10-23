# CareGiver

CareGiver is a medication-adherence platform for elderly patients who aren't comfortable with technology. A **caregiver** (usually a family member) does the setup and data entry from a web dashboard. The **patient** pairs a device once and then gets alarms and phone calls when it's time to take medicine.

> Status: proof of concept. Integrations with outside services (Twilio, Groq, Cloudflare R2/Supabase, Open-Meteo) sit behind provider switches. Every provider defaults to `logging`, which prints to the console instead of calling the outside service.

## Features

- **Caregiver accounts.** Sign up with email and password, or with Google.
- **Patient management.** Add patients and pair a patient's device with a one-time code sent to their phone.
- **Medicines and schedules.** Set times of day and days of the week for each medicine. Medicines can be deactivated.
- **Reminder escalation loop.** If the patient doesn't respond, a reminder escalates through these steps:
  1. An alarm goes off on the patient's device.
  2. The patient gets an automated phone call (`call_after_minutes`).
  3. The caregiver is alerted (`escalate_after_minutes`).

  The patient acknowledges a reminder with **Taken** or **Skipped**. Updates reach the dashboard live over Server-Sent Events.
- **Adherence calendar.** A day-by-day history of taken, skipped and missed doses.
- **Medical history.** Each patient's conditions and allergies.
- **Prescriptions.** Upload prescription images. AI (Groq vision) extracts the medicines, and the caregiver reviews and edits the result.
- **Daily suggestion.** Each day the patient gets a greeting and an activity suggestion, generated from the local weather and their medical history. The caregiver can override it.
- **Indian Standard Time (IST).** The app works out days and schedule times in IST.

## Tech stack

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.14, FastAPI, SQLAlchemy, Alembic, APScheduler, Pydantic Settings, `uv` |
| Database | PostgreSQL 16 (via Docker Compose) |
| Frontend | React 19, TypeScript, Vite, React Router, Tailwind CSS v4, Oxlint |
| Auth     | JWT (caregiver and patient tokens), Google Identity Services |

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, routers, 30s scheduler tick
│   │   ├── config.py          # Settings (read from env / backend/.env)
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── scheduler.py       # Creates today's reminders and escalates them
│   │   ├── events.py          # In-process event bus for SSE
│   │   ├── *_provider.py      # Pluggable integrations (call, OTP, storage, AI, weather)
│   │   └── routers/           # API routes under /api/v1
│   ├── alembic/               # Database migrations
│   └── tests/                 # pytest suite
├── frontend/
│   └── src/
│       ├── pages/             # Login, Pair, PatientList, PatientDetail, Prescriptions, PatientToday
│       ├── components/
│       └── api.ts             # API client (backend at http://localhost:8000)
├── docs/superpowers/          # Design specs and implementation plans for each feature
├── docker-compose.yml         # Local Postgres
└── .githooks/pre-commit       # gitleaks secret scan
```

## Getting started

### Prerequisites

- Docker
- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js 20 or later and npm
- Optional: [gitleaks](https://github.com/gitleaks/gitleaks) for the pre-commit secret scan

### 1. Start Postgres

```bash
docker compose up -d
```

### 2. Run the backend

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: `GET /health`

### 3. Run the frontend

```bash
cd frontend
npm install
echo "VITE_GOOGLE_CLIENT_ID=<your-google-oauth-client-id>" > .env.local   # optional; only needed for Google sign-in
npm run dev
```

Open http://localhost:5173.

The backend allows CORS only from `http://localhost:5173`. The frontend expects the API at `http://localhost:8000`, which is hard-coded in `frontend/src/api.ts`.

### 4. Enable the secret-scanning hook (recommended)

```bash
git config core.hooksPath .githooks
```

## Configuration

The backend reads its settings from environment variables or from `backend/.env`. All of them are defined in [backend/app/config.py](backend/app/config.py).

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+psycopg2://caregiver:caregiver@localhost:5432/caregiver` | Matches `docker-compose.yml` |
| `JWT_SECRET` | `dev-secret-change-me` | **Change this outside local development** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Caregiver token lifetime (1 day) |
| `PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES` | `525600` | Patient token lifetime (1 year) |
| `GOOGLE_CLIENT_ID` | — | Needed for Google sign-in |
| `CALL_PROVIDER` | `logging` | `logging` \| `twilio` |
| `OTP_PROVIDER` | `logging` | `logging` \| `twilio` |
| `STORAGE_PROVIDER` | `logging` | `logging` \| `r2` \| `supabase` |
| `PRESCRIPTION_EXTRACTION_PROVIDER` | `logging` | `logging` \| `groq` |
| `SUGGESTION_PROVIDER` | `logging` | `logging` \| `groq` |
| `WEATHER_PROVIDER` | `logging` | `logging` \| `open-meteo` |
| `GROQ_API_KEY` | — | Needed by the `groq` providers |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL` | — | Needed for `STORAGE_PROVIDER=r2` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_BUCKET_NAME` | — | Needed for `STORAGE_PROVIDER=supabase` |

The `twilio` call and OTP providers are placeholders: selecting them raises `NotImplementedError`. With the default `logging` provider, the OTP code for patient pairing is printed in the backend console.

## How pairing works

1. The caregiver adds a patient with a phone number and clicks **Invite**. The backend creates a 6-digit code that is valid for 10 minutes and sends it to the patient's phone through the OTP provider.
2. On the patient's device, open `/pair` and enter the phone number and the code. The device receives a long-lived patient token.
3. The device opens `/patient/today`, which shows the day's reminders, alarms and the daily suggestion.

## API overview

All routes are under `/api/v1`. The complete schema is at `/docs`.

| Area | Routes |
|------|--------|
| Caregiver auth | `POST /auth/signup`, `POST /auth/login`, `POST /auth/google` |
| Patient auth | `POST /auth/patient/verify` |
| Patients | `GET/POST /patients`, `POST /patients/{id}/invite` |
| Medicines and schedules | `/patients/{id}/medicines`, `/medicines/{id}`, `/medicines/{id}/schedules`, `/schedules/{id}` |
| Medical history | `/patients/{id}/medical-history`, plus routes for conditions and allergies |
| Prescriptions | `/patients/{id}/prescriptions[/{prescription_id}]` (upload, list, get, edit) |
| Reminders | `/patients/{id}/reminders/today`, `/patients/{id}/reminders`, `/patients/{id}/adherence/calendar`, `POST /reminders/{id}/ack` |
| Live events | `GET /patients/{id}/events/stream` (SSE) |
| Daily suggestion | `GET/PUT /patients/{id}/daily-suggestion`, `POST /patients/{id}/daily-suggestion/generate` |

## Development

```bash
# Backend tests
cd backend && uv run pytest

# Create a new migration after changing models
cd backend && uv run alembic revision --autogenerate -m "describe change"

# Frontend lint and production build
cd frontend && npm run lint && npm run build
```

The design spec and implementation plan for each feature are in [docs/superpowers/](docs/superpowers/).

## Known limitations

- The Twilio call and OTP providers aren't implemented yet.
- The reminder scheduler runs inside the API process: APScheduler checks every 30 seconds. The SSE event bus also lives in that process's memory. Because of both, run only one backend instance.
- The API base URL and the allowed CORS origin are hard-coded for local development.

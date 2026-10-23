import datetime
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.call_provider import get_call_provider
from app.db import SessionLocal
from app.routers import auth, daily_suggestion, medical_history, medicines, patient_auth, patients, prescriptions, reminders
from app.scheduler import advance_reminder_events, materialize_todays_events

scheduler = BackgroundScheduler()


def _run_scheduler_tick():
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        materialize_todays_events(db, now)
        advance_reminder_events(db, now, get_call_provider())
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(_run_scheduler_tick, "interval", seconds=30, id="reminder_tick")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="CareGiver API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(patient_auth.router)
app.include_router(patients.router)
app.include_router(medicines.router)
app.include_router(medical_history.router)
app.include_router(prescriptions.router)
app.include_router(daily_suggestion.router)
app.include_router(reminders.router)


@app.get("/health")
def health():
    return {"status": "ok"}

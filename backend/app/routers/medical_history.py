import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_caregiver, get_current_patient
from app.db import get_db
from app.models import Allergy, Condition, Note, PatientProfile, User
from app.schemas import EntryCreate, EntryResponse, MedicalHistoryResponse

router = APIRouter(prefix="/api/v1", tags=["medical-history"])

_ENTITY_CONFIG = {
    "conditions": Condition,
    "allergies": Allergy,
    "notes": Note,
}


def _get_owned_patient(db: Session, patient_id: str, caregiver: User) -> PatientProfile:
    patient = (
        db.query(PatientProfile)
        .filter(PatientProfile.id == patient_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _get_owned_entry(db: Session, model, entry_id: str, caregiver: User):
    entry = (
        db.query(model)
        .join(PatientProfile, model.patient_id == PatientProfile.id)
        .filter(model.id == entry_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _register_entity_routes(path_segment: str, model):
    @router.get(
        f"/patients/{{patient_id}}/{path_segment}",
        response_model=list[EntryResponse],
        name=f"list_{path_segment}",
    )
    def list_entries(
        patient_id: str,
        db: Session = Depends(get_db),
        caregiver: User = Depends(get_current_caregiver),
    ):
        _get_owned_patient(db, patient_id, caregiver)
        return db.query(model).filter(model.patient_id == patient_id).all()

    @router.post(
        f"/patients/{{patient_id}}/{path_segment}",
        response_model=EntryResponse,
        name=f"create_{path_segment}",
    )
    def create_entry(
        patient_id: str,
        body: EntryCreate,
        db: Session = Depends(get_db),
        caregiver: User = Depends(get_current_caregiver),
    ):
        _get_owned_patient(db, patient_id, caregiver)
        entry = model(patient_id=patient_id, text=body.text, created_at=datetime.datetime.utcnow())
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @router.delete(
        f"/{path_segment}/{{entry_id}}",
        status_code=204,
        name=f"delete_{path_segment}",
    )
    def delete_entry(
        entry_id: str,
        db: Session = Depends(get_db),
        caregiver: User = Depends(get_current_caregiver),
    ):
        entry = _get_owned_entry(db, model, entry_id, caregiver)
        db.delete(entry)
        db.commit()


for _path_segment, _model in _ENTITY_CONFIG.items():
    _register_entity_routes(_path_segment, _model)


@router.get("/patients/{patient_id}/medical-history", response_model=MedicalHistoryResponse)
def get_medical_history(
    patient_id: str,
    db: Session = Depends(get_db),
    patient_session=Depends(get_current_patient),
):
    _patient_user, own_patient = patient_session
    if own_patient.id != patient_id:
        raise HTTPException(status_code=404, detail="Patient not found")

    return MedicalHistoryResponse(
        conditions=db.query(Condition).filter(Condition.patient_id == patient_id).all(),
        allergies=db.query(Allergy).filter(Allergy.patient_id == patient_id).all(),
        notes=db.query(Note).filter(Note.patient_id == patient_id).all(),
    )

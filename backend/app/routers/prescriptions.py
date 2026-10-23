import datetime
import json
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_caregiver
from app.db import get_db
from app.models import PatientProfile, Prescription, PrescriptionImage, PrescriptionStatus, User
from app.prescription_classifier import NotAPrescriptionError
from app.prescription_extraction_provider import get_extraction_provider
from app.schemas import CandidateUpdateRequest, PrescriptionResponse
from app.storage_provider import get_storage_provider

router = APIRouter(prefix="/api/v1/patients", tags=["prescriptions"])


def _get_owned_patient(db: Session, patient_id: str, caregiver: User) -> PatientProfile:
    patient = (
        db.query(PatientProfile)
        .filter(PatientProfile.id == patient_id, PatientProfile.caregiver_id == caregiver.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _get_owned_prescription(db: Session, patient_id: str, prescription_id: str, caregiver: User) -> Prescription:
    _get_owned_patient(db, patient_id, caregiver)
    prescription = (
        db.query(Prescription)
        .filter(Prescription.id == prescription_id, Prescription.patient_id == patient_id)
        .first()
    )
    if prescription is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return prescription


def _to_response(db: Session, prescription: Prescription) -> PrescriptionResponse:
    images = (
        db.query(PrescriptionImage)
        .filter(PrescriptionImage.prescription_id == prescription.id)
        .order_by(PrescriptionImage.position)
        .all()
    )
    return PrescriptionResponse(
        id=prescription.id,
        patient_id=prescription.patient_id,
        images=[{"id": img.id, "file_url": img.file_url, "position": img.position} for img in images],
        status=prescription.status.value,
        candidates=json.loads(prescription.raw_extraction),
        uploaded_at=prescription.uploaded_at,
    )


@router.post("/{patient_id}/prescriptions", response_model=PrescriptionResponse)
async def upload_prescription(
    patient_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    _get_owned_patient(db, patient_id, caregiver)

    file_contents = []
    for file in files:
        content = await file.read()
        content_type = file.content_type or "application/octet-stream"
        file_contents.append((file.filename, content, content_type))

    # Classify + extract before touching storage so rejected images are never persisted.
    try:
        candidates = get_extraction_provider().extract(
            [(content, content_type) for _name, content, content_type in file_contents]
        )
    except NotAPrescriptionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    storage = get_storage_provider()
    image_payloads = []
    for filename, content, content_type in file_contents:
        file_url = storage.upload(patient_id, filename, content, content_type)
        image_payloads.append((file_url, content, content_type))
    for candidate in candidates:
        candidate["status"] = "pending"

    prescription = Prescription(
        patient_id=patient_id,
        status=PrescriptionStatus.pending_review,
        raw_extraction=json.dumps(candidates),
        uploaded_at=datetime.datetime.utcnow(),
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)

    for position, (file_url, _content, _content_type) in enumerate(image_payloads):
        db.add(PrescriptionImage(prescription_id=prescription.id, file_url=file_url, position=position))
    db.commit()
    db.refresh(prescription)

    return _to_response(db, prescription)


@router.get("/{patient_id}/prescriptions", response_model=List[PrescriptionResponse])
def list_prescriptions(
    patient_id: str,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    _get_owned_patient(db, patient_id, caregiver)
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.uploaded_at.desc())
        .all()
    )
    return [_to_response(db, p) for p in prescriptions]


@router.get("/{patient_id}/prescriptions/{prescription_id}", response_model=PrescriptionResponse)
def get_prescription(
    patient_id: str,
    prescription_id: str,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    prescription = _get_owned_prescription(db, patient_id, prescription_id, caregiver)
    return _to_response(db, prescription)


@router.patch(
    "/{patient_id}/prescriptions/{prescription_id}/candidates/{index}",
    response_model=PrescriptionResponse,
)
def update_candidate(
    patient_id: str,
    prescription_id: str,
    index: int,
    body: CandidateUpdateRequest,
    db: Session = Depends(get_db),
    caregiver: User = Depends(get_current_caregiver),
):
    prescription = _get_owned_prescription(db, patient_id, prescription_id, caregiver)
    candidates = json.loads(prescription.raw_extraction)

    if index < 0 or index >= len(candidates):
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidates[index]["status"] = body.status
    if body.name is not None:
        candidates[index]["name"] = body.name
    if body.dose is not None:
        candidates[index]["dose"] = body.dose

    prescription.raw_extraction = json.dumps(candidates)

    if all(c["status"] != "pending" for c in candidates):
        prescription.status = PrescriptionStatus.reviewed

    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return _to_response(db, prescription)

import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_patient_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=settings.patient_access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_caregiver(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.role != UserRole.caregiver:
        raise credentials_error
    return user


def get_current_patient_from_token(token: str, db: Session):
    """Raw-token variant, same pattern as get_current_caregiver_from_token."""
    from app.models import PatientProfile

    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.role != UserRole.patient:
        raise credentials_error

    patient = db.query(PatientProfile).filter(PatientProfile.user_id == user.id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="No linked patient profile")

    return user, patient


def get_current_patient(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    return get_current_patient_from_token(token, db)


def get_current_caregiver_from_token(token: str, db: Session) -> User:
    """Same validation as get_current_caregiver, callable with a raw token string
    (for SSE, where the token arrives as a query param, not a header)."""
    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.role != UserRole.caregiver:
        raise credentials_error
    return user


def get_owned_patient_via_caregiver_or_patient_session(
    patient_id: str, db: Session, authorization: str
):
    """Returns the PatientProfile if the caller is either the caregiver who owns
    it, or the patient's own session. Raises 401/404 HTTPException otherwise."""
    from app.models import PatientProfile

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    patient = db.query(PatientProfile).filter(PatientProfile.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    try:
        caregiver = get_current_caregiver_from_token(token, db)
        if patient.caregiver_id != caregiver.id:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient
    except HTTPException as caregiver_auth_error:
        if caregiver_auth_error.status_code == 404:
            raise
        _patient_user, own_patient = get_current_patient_from_token(token, db)
        if own_patient.id != patient_id:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient

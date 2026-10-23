import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.db import get_db
from app.models import User, UserRole
from app.schemas import GoogleAuthRequest, LoginRequest, SignupRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole.caregiver,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/google", response_model=TokenResponse)
def google_signin(body: GoogleAuthRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        claims = id_token.verify_oauth2_token(
            body.id_token, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

    google_sub = claims["sub"]
    email = claims.get("email")
    name = claims.get("name")

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None and email:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            user.google_sub = google_sub
            db.add(user)
            db.commit()
            db.refresh(user)

    if user is None:
        user = User(
            email=email,
            name=name,
            google_sub=google_sub,
            role=UserRole.caregiver,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))

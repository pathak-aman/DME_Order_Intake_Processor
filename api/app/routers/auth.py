import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import Base, engine, get_db
from app.models import User
from app.schemas import Token, UserCreate, UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@router.post(
    "/register/",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """Create a new user account. Email must be unique."""
    # Ensure database tables exist in Neon / Postgres
    try:
        existing = db.query(User).filter(User.email == user_in.email).first()
    except Exception as e:
        logger.warning("Query failed, auto-creating schema tables: %s", e)
        db.rollback()
        Base.metadata.create_all(bind=engine)
        existing = db.query(User).filter(User.email == user_in.email).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/token",
    response_model=Token,
    summary="Login and get JWT access token",
)
@router.post(
    "/token/",
    response_model=Token,
    include_in_schema=False,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """
    OAuth2 password flow. `username` field accepts the user's email address.
    Returns a Bearer JWT token valid for `ACCESS_TOKEN_EXPIRE_MINUTES` minutes.
    """
    try:
        user = db.query(User).filter(User.email == form_data.username).first()
    except Exception as e:
        logger.warning("Login query failed, ensuring tables exist: %s", e)
        db.rollback()
        Base.metadata.create_all(bind=engine)
        user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=token)

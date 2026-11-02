from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None


# ─── Orders ──────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    """Manual order creation (all fields optional — can be filled via PDF later)."""
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_dob: str | None = None
    provider_name: str | None = None
    provider_npi: str | None = None
    status: str = "needs_review"

    @field_validator("provider_npi")
    @classmethod
    def validate_npi(cls, v: str | None) -> str | None:
        if v is not None and (not v.isdigit() or len(v) != 10):
            raise ValueError("provider_npi must be exactly 10 digits")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"verified", "needs_review"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class OrderUpdate(BaseModel):
    """Partial update — all fields optional."""
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_dob: str | None = None
    provider_name: str | None = None
    provider_npi: str | None = None
    status: str | None = None

    @field_validator("provider_npi")
    @classmethod
    def validate_npi(cls, v: str | None) -> str | None:
        if v is not None and (not v.isdigit() or len(v) != 10):
            raise ValueError("provider_npi must be exactly 10 digits")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in {"verified", "needs_review"}:
            raise ValueError("status must be 'verified' or 'needs_review'")
        return v


class OrderOut(BaseModel):
    id: int
    user_id: int
    patient_first_name: str | None
    patient_last_name: str | None
    patient_dob: str | None
    provider_name: str | None
    provider_npi: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

"""
Orders router — Complete CRUD and PDF Upload with AI Extraction and Strict Validation.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Order, User
from app.schemas import OrderCreate, OrderOut, OrderUpdate
from app.services.extractor import extract_order_from_pdf
from app.services.validator import validate_and_sanitize_order

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get(
    "/",
    response_model=List[OrderOut],
    summary="List all orders for the authenticated user",
)
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Order]:
    """Returns only orders that belong to the currently authenticated user (isolated per user)."""
    return (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )


@router.post(
    "/",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Manually create a new order",
)
def create_order(
    order_in: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    """Create an order manually (without PDF upload)."""
    # Validate clinical values using the zero-guessing validator
    sanitized, _ = validate_and_sanitize_order(order_in.model_dump())

    order = Order(
        user_id=current_user.id,
        patient_first_name=sanitized.get("patient_first_name"),
        patient_last_name=sanitized.get("patient_last_name"),
        patient_dob=sanitized.get("patient_dob"),
        provider_name=sanitized.get("provider_name"),
        provider_npi=sanitized.get("provider_npi"),
        status=sanitized.get("status", "needs_review"),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    summary="Get a single order by ID",
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    """Retrieve an order by ID. Enforces strict tenant isolation."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return order


@router.put(
    "/{order_id}",
    response_model=OrderOut,
    summary="Update an order's fields",
)
def update_order(
    order_id: int,
    order_in: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    """Update order fields. Re-evaluates validation before saving."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    update_data = order_in.model_dump(exclude_unset=True)

    # Merge existing values with updates for validation
    combined = {
        "patient_first_name": update_data.get("patient_first_name", order.patient_first_name),
        "patient_last_name": update_data.get("patient_last_name", order.patient_last_name),
        "patient_dob": update_data.get("patient_dob", order.patient_dob),
        "provider_name": update_data.get("provider_name", order.provider_name),
        "provider_npi": update_data.get("provider_npi", order.provider_npi),
    }

    sanitized, _ = validate_and_sanitize_order(combined)

    for field, value in sanitized.items():
        if field in ("patient_first_name", "patient_last_name", "patient_dob", "provider_name", "provider_npi"):
            setattr(order, field, value)

    # If status explicitly provided in update_data, allow overriding; otherwise use sanitized
    if "status" in update_data and update_data["status"]:
        order.status = update_data["status"]
    else:
        order.status = sanitized["status"]

    db.commit()
    db.refresh(order)
    return order


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an order",
)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an order. Enforces strict tenant isolation."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    db.delete(order)
    db.commit()


@router.post(
    "/upload",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF and extract DME order fields",
)
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    """
    Accepts an uploaded PDF (scanned faxes, multi-page prescriptions, messy documents).
    Extracts:
      - patient_first_name
      - patient_last_name
      - patient_dob
      - provider_name
      - provider_npi
    Applies strict zero-guessing validation before persisting to database.
    """
    filename = file.filename or ""
    if not (filename.lower().endswith(".pdf") or (file.content_type and "pdf" in file.content_type.lower())):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported.",
        )

    try:
        pdf_bytes = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded PDF file: {str(e)}",
        )

    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    logger.info(f"Processing PDF '{filename}' ({len(pdf_bytes)} bytes) for user {current_user.id}")

    # 1. Extract values using Gemini multimodal extractor
    raw_extracted = extract_order_from_pdf(pdf_bytes)
    logger.info(f"Raw extracted data: {raw_extracted}")

    # 2. Strict validation & zero-guessing enforcement before saving
    sanitized, issues = validate_and_sanitize_order(raw_extracted)
    if issues:
        logger.info(f"Validation issues identified (zero-guessing policy): {issues}")

    # 3. Create and save order in database scoped to current user
    order = Order(
        user_id=current_user.id,
        patient_first_name=sanitized["patient_first_name"],
        patient_last_name=sanitized["patient_last_name"],
        patient_dob=sanitized["patient_dob"],
        provider_name=sanitized["provider_name"],
        provider_npi=sanitized["provider_npi"],
        status=sanitized["status"],
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info(f"Order #{order.id} saved with status '{order.status}' for user #{current_user.id}")
    return order

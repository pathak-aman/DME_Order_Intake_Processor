"""
Orders router — Phase 2 (CRUD) and Phase 3 (PDF Upload) placeholder.
Endpoints are scaffolded and return 501 until Phase 2/3 implementation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Order, User
from app.schemas import OrderCreate, OrderOut, OrderUpdate

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get(
    "/",
    response_model=list[OrderOut],
    summary="List all orders for the authenticated user",
)
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Order]:
    """Returns only orders that belong to the currently authenticated user."""
    return db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()


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
    order = Order(user_id=current_user.id, **order_in.model_dump())
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
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    update_data = order_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

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
    summary="Upload a PDF and extract DME order fields (Phase 3)",
)
def upload_pdf(
    current_user: User = Depends(get_current_user),
) -> None:
    """
    PDF extraction endpoint — implemented in Phase 3.
    Accepts multipart/form-data with a 'file' field (PDF).
    Extracts patient and provider fields via Gemini Vision.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF extraction is not yet implemented. Coming in Phase 3.",
    )

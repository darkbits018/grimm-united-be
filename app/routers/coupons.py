import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.models import Coupon
from app.database import SessionLocal
from app.utils import require_admin

router = APIRouter()


class CouponCreate(BaseModel):
    code: str
    discount_percent: float
    max_uses: Optional[int] = None
    expires_at: Optional[str] = None  # ISO date string or None
    is_active: bool = True


class CouponValidate(BaseModel):
    code: str


def coupon_to_dict(c: Coupon) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "discount_percent": c.discount_percent,
        "max_uses": c.max_uses,
        "uses": c.uses,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "is_active": c.is_active,
    }


@router.get("/api/admin/coupons")
def list_coupons(x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    db = SessionLocal()
    coupons = db.query(Coupon).order_by(Coupon.id.desc()).all()
    db.close()
    return [coupon_to_dict(c) for c in coupons]


@router.post("/api/admin/coupons")
def create_coupon(data: CouponCreate, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    db = SessionLocal()
    existing = db.query(Coupon).filter(Coupon.code == data.code.upper()).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    expires = None
    if data.expires_at:
        try:
            expires = datetime.fromisoformat(data.expires_at)
        except ValueError:
            db.close()
            raise HTTPException(status_code=400, detail="Invalid expires_at format")
    c = Coupon(
        code=data.code.upper().strip(),
        discount_percent=data.discount_percent,
        max_uses=data.max_uses,
        expires_at=expires,
        is_active=data.is_active,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    result = coupon_to_dict(c)
    db.close()
    return result


@router.put("/api/admin/coupons/{coupon_id}")
def update_coupon(coupon_id: int, data: CouponCreate, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    db = SessionLocal()
    c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not c:
        db.close()
        raise HTTPException(status_code=404, detail="Coupon not found")
    c.code = data.code.upper().strip()
    c.discount_percent = data.discount_percent
    c.max_uses = data.max_uses
    c.is_active = data.is_active
    if data.expires_at:
        try:
            c.expires_at = datetime.fromisoformat(data.expires_at)
        except ValueError:
            db.close()
            raise HTTPException(status_code=400, detail="Invalid expires_at format")
    else:
        c.expires_at = None
    db.commit()
    result = coupon_to_dict(c)
    db.close()
    return result


@router.delete("/api/admin/coupons/{coupon_id}")
def delete_coupon(coupon_id: int, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    db = SessionLocal()
    c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not c:
        db.close()
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(c)
    db.commit()
    db.close()
    return {"message": "Deleted"}


@router.post("/api/coupons/validate")
def validate_coupon(data: CouponValidate):
    """Public endpoint — called from checkout to validate a coupon code."""
    db = SessionLocal()
    c = db.query(Coupon).filter(Coupon.code == data.code.upper().strip()).first()
    if not c or not c.is_active:
        db.close()
        raise HTTPException(status_code=404, detail="Invalid or inactive coupon")
    if c.expires_at and c.expires_at < datetime.utcnow():
        db.close()
        raise HTTPException(status_code=400, detail="Coupon has expired")
    if c.max_uses is not None and c.uses >= c.max_uses:
        db.close()
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")
    db.close()
    return {"code": c.code, "discount_percent": c.discount_percent}

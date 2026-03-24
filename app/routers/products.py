import json
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from app.schemas import ProductCreate
from app.models import Product
from app.database import SessionLocal
from app.utils import require_admin, product_to_dict

router = APIRouter()


@router.get("/api/admin/products")
def list_all_products(x_admin_token: str = Header(None)):
    """Admin view — returns all products including inactive ones."""
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    db.close()
    return [product_to_dict(p) for p in products]


@router.get("/api/products")
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
):
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    q = db.query(Product).filter(Product.is_active == True)
    if category and category.lower() != "all":
        q = q.filter(Product.category == category)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if min_price is not None:
        q = q.filter(Product.price >= min_price)
    if max_price is not None:
        q = q.filter(Product.price <= max_price)
    products = q.order_by(Product.created_at.desc()).all()
    db.close()

    # Group color variants under one product using qikink_client_product_id
    # Products without a client_product_id are returned as-is
    grouped: dict = {}
    ungrouped = []
    for p in products:
        key = p.qikink_client_product_id
        if key:
            if key not in grouped:
                d = product_to_dict(p)
                # Strip color suffix from name (e.g. "Shirt — Black" → "Shirt")
                base_name = d["name"]
                for sep in [" — ", " - "]:
                    if sep in base_name:
                        base_name = base_name.rsplit(sep, 1)[0]
                        break
                d["name"] = base_name
                d["variants"] = []
                grouped[key] = d
            grouped[key]["variants"].append({
                "id": str(p.id),
                "color": p.qikink_color_id,
                "color_name": _color_name(p.name),
                "image": json.loads(p.images or "[]")[0] if p.images else "",
                "images": json.loads(p.images or "[]"),
                "sizes": json.loads(p.sizes or "[]"),
                "stock_per_size": json.loads(p.stock_per_size or "{}"),
                "qikink_color_id": p.qikink_color_id,
            })
        else:
            d = product_to_dict(p)
            d["variants"] = []
            ungrouped.append(d)

    return list(grouped.values()) + ungrouped


def _color_name(product_name: str) -> str:
    """Extract color name from 'Product Title — Color' format."""
    for sep in [" — ", " - "]:
        if sep in product_name:
            return product_name.rsplit(sep, 1)[-1]
    return ""


@router.get("/api/products/{product_id}")
def get_product(product_id: int):
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        db.close()
        raise HTTPException(status_code=404, detail="Product not found")

    result = product_to_dict(p)
    result["variants"] = []

    # Fetch sibling variants (same client_product_id)
    if p.qikink_client_product_id:
        siblings = db.query(Product).filter(
            Product.qikink_client_product_id == p.qikink_client_product_id,
            Product.is_active == True,
        ).all()
        for s in siblings:
            result["variants"].append({
                "id": str(s.id),
                "color_name": _color_name(s.name),
                "image": json.loads(s.images or "[]")[0] if s.images else "",
                "images": json.loads(s.images or "[]"),
                "sizes": json.loads(s.sizes or "[]"),
                "stock_per_size": json.loads(s.stock_per_size or "{}"),
                "qikink_color_id": s.qikink_color_id,
            })
        # Strip color suffix from name
        base_name = result["name"]
        for sep in [" — ", " - "]:
            if sep in base_name:
                base_name = base_name.rsplit(sep, 1)[0]
                break
        result["name"] = base_name

    db.close()
    return result


@router.post("/api/admin/products")
def create_product(data: ProductCreate, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    p = Product(
        name=data.name, description=data.description, price=data.price,
        compare_at_price=data.compare_at_price,
        images=json.dumps(data.images), sizes=json.dumps(data.sizes),
        stock_per_size=json.dumps(data.stock_per_size),
        category=data.category, tags=json.dumps(data.tags), is_active=data.is_active,
        qikink_sku=data.qikink_sku,
        qikink_print_type_id=data.qikink_print_type_id,
        qikink_design_code=data.qikink_design_code,
        qikink_design_url=data.qikink_design_url,
        qikink_mockup_url=data.qikink_mockup_url,
        qikink_client_product_id=data.qikink_client_product_id,
        qikink_color_id=data.qikink_color_id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    result = product_to_dict(p)
    db.close()
    return result


@router.put("/api/admin/products/{product_id}")
def update_product(product_id: int, data: ProductCreate, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        db.close()
        raise HTTPException(status_code=404, detail="Product not found")
    p.name = data.name
    p.description = data.description
    p.price = data.price
    p.compare_at_price = data.compare_at_price
    p.images = json.dumps(data.images)
    p.sizes = json.dumps(data.sizes)
    p.stock_per_size = json.dumps(data.stock_per_size)
    p.category = data.category
    p.tags = json.dumps(data.tags)
    p.is_active = data.is_active
    p.qikink_sku = data.qikink_sku
    p.qikink_print_type_id = data.qikink_print_type_id
    p.qikink_design_code = data.qikink_design_code
    p.qikink_design_url = data.qikink_design_url
    p.qikink_mockup_url = data.qikink_mockup_url
    p.qikink_client_product_id = data.qikink_client_product_id
    p.qikink_color_id = data.qikink_color_id
    db.commit()
    result = product_to_dict(p)
    db.close()
    return result


@router.delete("/api/admin/products/{product_id}")
def delete_product(product_id: int, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        db.close()
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(p)
    db.commit()
    db.close()
    return {"message": "Product deleted"}

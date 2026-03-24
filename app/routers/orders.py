import json
import hmac
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from app.schemas import OrderCreate, RazorpayVerify, OrderStatusUpdate
from app.models import Order, OrderItem, Coupon, Product
from app.database import SessionLocal
from app.utils import require_admin, order_to_dict, send_email
from app.config import settings
from app.services.qikink import push_order_to_qikink

router = APIRouter()


@router.post("/api/coupons/validate")
def validate_coupon(payload: dict):
    code = (payload.get("code") or "").strip().upper()
    subtotal = float(payload.get("subtotal") or 0)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    coupon = db.query(Coupon).filter(Coupon.code == code, Coupon.is_active == True).first()
    db.close()
    if not coupon:
        if code == "GRIMM10":
            discount = round(subtotal * 0.10)
            return {"valid": True, "discount_percent": 10, "discount_amount": discount, "code": code}
        raise HTTPException(status_code=404, detail="Invalid coupon code")
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Coupon has expired")
    if coupon.max_uses and coupon.uses >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")
    discount = round(subtotal * coupon.discount_percent / 100)
    return {"valid": True, "discount_percent": coupon.discount_percent, "discount_amount": discount, "code": code}


@router.post("/api/orders")
async def create_order(data: OrderCreate):
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")

    order_id = f"GU-{int(datetime.utcnow().timestamp() * 1000)}"
    razorpay_order_id = None

    if settings and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            rp_order = client.order.create({
                "amount": int(data.total * 100),
                "currency": "INR",
                "receipt": order_id,
                "notes": {"customer_email": data.shipping_address.email},
            })
            razorpay_order_id = rp_order["id"]
        except Exception as e:
            print(f"Razorpay order creation failed: {e}")

    db = SessionLocal()
    order = Order(
        id=order_id,
        razorpay_order_id=razorpay_order_id,
        customer_name=data.shipping_address.name,
        customer_email=data.shipping_address.email,
        phone=data.shipping_address.phone,
        shipping_address=json.dumps(data.shipping_address.model_dump()),
        status="pending",
        subtotal=data.subtotal,
        discount=data.discount,
        shipping=data.shipping,
        total=data.total,
        coupon_code=data.coupon_code,
    )
    db.add(order)
    db.flush()
    for item in data.items:
        db.add(OrderItem(
            order_id=order_id,
            product_id=int(item.product_id) if item.product_id else None,
            product_name=item.product_name,
            size=item.size,
            quantity=item.quantity,
            unit_price=item.unit_price,
            image=item.image,
        ))
    db.commit()
    db.close()

    return {
        "order_id": order_id,
        "razorpay_order_id": razorpay_order_id,
        "amount": int(data.total * 100),
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID if settings else None,
    }


@router.post("/api/orders/verify-payment")
async def verify_payment(data: RazorpayVerify):
    if not settings or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay not configured")
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")

    generated = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{data.razorpay_order_id}|{data.razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if generated != data.razorpay_signature:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    db = SessionLocal()
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        db.close()
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "paid"
    order.razorpay_payment_id = data.razorpay_payment_id
    db.commit()

    items_html = "".join(
        f"<tr><td>{i.product_name}</td><td>{i.size}</td><td>{i.quantity}</td><td>₹{i.unit_price * i.quantity:,.0f}</td></tr>"
        for i in order.items
    )
    addr = json.loads(order.shipping_address)
    confirmation_html = f"""<html><body>
        <h2>Order Confirmed — {order.id}</h2>
        <p>Hi {order.customer_name}, your order has been placed successfully!</p>
        <table border="1" cellpadding="6" cellspacing="0">
            <tr><th>Item</th><th>Size</th><th>Qty</th><th>Price</th></tr>
            {items_html}
        </table>
        <p><b>Total: ₹{order.total:,.0f}</b></p>
        <p><b>Shipping to:</b> {addr.get('line1')}, {addr.get('city')}, {addr.get('state')} {addr.get('pincode')}</p>
        <p>Estimated delivery: 5–7 business days.</p>
        <p>Track your order at: <a href="https://grimmunited.com/orders/{order.id}">grimmunited.com/orders/{order.id}</a></p>
    </body></html>"""

    # Push to Qikink for fulfillment
    qikink_order_id = None
    if settings and settings.QIKINK_CLIENT_ID and settings.QIKINK_ACCESS_TOKEN:
        try:
            items_with_products = []
            for oi in order.items:
                product = db.query(Product).filter(Product.id == oi.product_id).first() if oi.product_id else None
                items_with_products.append((oi, product))
            qk_resp = await push_order_to_qikink(order, items_with_products)
            qikink_order_id = str(qk_resp.get("order_id", ""))
            order.qikink_order_id = qikink_order_id
            db.commit()
            print(f"Qikink order pushed: {qikink_order_id}")
        except Exception as e:
            print(f"Qikink push failed for {order.id}: {e}")

    db.close()
    await send_email(order.customer_email, f"Order Confirmed — {order.id}", confirmation_html)
    return {"message": "Payment verified", "order_id": order.id, "status": "paid", "qikink_order_id": qikink_order_id}


@router.get("/api/orders/{order_id}")
def get_order(order_id: str):
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    db.close()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_to_dict(order)


@router.get("/api/admin/orders")
def list_orders(x_admin_token: str = Header(None), status: Optional[str] = None):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    q = db.query(Order)
    if status and status != "all":
        q = q.filter(Order.status == status)
    orders = q.order_by(Order.created_at.desc()).all()
    db.close()
    return [order_to_dict(o) for o in orders]


@router.put("/api/admin/orders/{order_id}/status")
async def update_order_status(order_id: str, data: OrderStatusUpdate, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        db.close()
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = data.status
    db.commit()

    if data.status == "shipped":
        addr = json.loads(order.shipping_address)
        shipped_html = f"""<html><body>
            <h2>Your Order Has Shipped! 🚚</h2>
            <p>Hi {order.customer_name}, your order <b>{order.id}</b> is on its way.</p>
            <p>Shipping to: {addr.get('line1')}, {addr.get('city')}, {addr.get('state')} {addr.get('pincode')}</p>
            <p>Track your order: <a href="https://grimmunited.com/orders/{order.id}">grimmunited.com/orders/{order.id}</a></p>
        </body></html>"""
        db.close()
        await send_email(order.customer_email, f"Your Order {order.id} Has Shipped!", shipped_html)
    else:
        db.close()

    return {"message": "Status updated", "order_id": order_id, "status": data.status}


@router.post("/api/admin/orders/{order_id}/push-qikink")
async def push_to_qikink(order_id: str, x_admin_token: str = Header(None)):
    """Manually push a paid order to Qikink — useful if the auto-push failed."""
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    if not settings or not settings.QIKINK_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Qikink credentials not configured")

    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        db.close()
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("paid", "processing"):
        db.close()
        raise HTTPException(status_code=400, detail=f"Order status is '{order.status}', must be paid to push")

    items_with_products = []
    for oi in order.items:
        product = db.query(Product).filter(Product.id == oi.product_id).first() if oi.product_id else None
        items_with_products.append((oi, product))

    try:
        qk_resp = await push_order_to_qikink(order, items_with_products)
        qikink_order_id = str(qk_resp.get("order_id", ""))
        order.qikink_order_id = qikink_order_id
        db.commit()
        db.close()
        return {"message": "Pushed to Qikink", "qikink_order_id": qikink_order_id}
    except Exception as e:
        db.close()
        raise HTTPException(status_code=502, detail=f"Qikink push failed: {e}")

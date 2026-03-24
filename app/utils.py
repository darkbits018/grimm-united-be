import json
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException
from app.config import settings
from app.models import Product, Order


def require_admin(token: str):
    if not settings or token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized")


def product_to_dict(p: Product) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "compare_at_price": p.compare_at_price,
        "images": json.loads(p.images or "[]"),
        "sizes": json.loads(p.sizes or "[]"),
        "stock_per_size": json.loads(p.stock_per_size or "{}"),
        "category": p.category,
        "tags": json.loads(p.tags or "[]"),
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "qikink_sku": p.qikink_sku,
        "qikink_print_type_id": p.qikink_print_type_id,
        "qikink_design_code": p.qikink_design_code,
        "qikink_client_product_id": p.qikink_client_product_id,
        "qikink_color_id": p.qikink_color_id,
    }


def order_to_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "razorpay_order_id": o.razorpay_order_id,
        "razorpay_payment_id": o.razorpay_payment_id,
        "customer_name": o.customer_name,
        "customer_email": o.customer_email,
        "phone": o.phone,
        "shipping_address": json.loads(o.shipping_address or "{}"),
        "status": o.status,
        "subtotal": o.subtotal,
        "discount": o.discount,
        "shipping": o.shipping,
        "total": o.total,
        "coupon_code": o.coupon_code,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "qikink_order_id": o.qikink_order_id,
        "items": [
            {
                "product_id": str(i.product_id) if i.product_id else None,
                "product_name": i.product_name,
                "size": i.size,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "image": i.image,
            }
            for i in (o.items or [])
        ],
    }


async def send_email(to: str, subject: str, html: str):
    if not settings:
        return
    message = MIMEMultipart()
    message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(html, "html"))
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.MAIL_SERVER,
            port=settings.MAIL_PORT,
            username=settings.MAIL_USERNAME,
            password=settings.MAIL_PASSWORD,
            use_tls=settings.MAIL_PORT == 465,
            start_tls=settings.MAIL_PORT == 587,
        )
    except Exception as e:
        print(f"Email send failed to {to}: {e}")

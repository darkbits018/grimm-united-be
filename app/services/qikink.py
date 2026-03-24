"""
Qikink API service — wraps order creation and status retrieval.
Sandbox:  https://sandbox.qikink.com/
Live:     https://api.qikink.com/
"""

import json
import httpx
from app.config import settings

# Maps our size labels to Qikink size_ids
SIZE_ID_MAP = {
    "XS": "9", "S": "1", "M": "2", "L": "3",
    "XL": "4", "XXL": "6", "2XL": "6", "3XL": "7",
}


def _base_url() -> str:
    if settings and not settings.QIKINK_SANDBOX:
        return "https://api.qikink.com"
    return "https://sandbox.qikink.com"


def _headers() -> dict:
    if not settings or not settings.QIKINK_CLIENT_ID or not settings.QIKINK_ACCESS_TOKEN:
        raise RuntimeError("Qikink credentials not configured")
    return {
        "ClientId": settings.QIKINK_CLIENT_ID,
        "Accesstoken": settings.QIKINK_ACCESS_TOKEN,
    }


async def push_order_to_qikink(order, items_with_products: list) -> dict:
    """
    Push a paid order to Qikink for fulfillment.
    items_with_products: list of (OrderItem, Product | None)
    """
    addr_raw = json.loads(order.shipping_address or "{}")
    name_parts = (order.customer_name or "").split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    line_items = []
    for oi, product in items_with_products:
        if not product:
            print(f"Warning: no product record for OrderItem {oi.id} — skipped")
            continue

        if product.qikink_client_product_id:
            # Use saved product from Qikink dashboard (search_from_my_products=1)
            # Qikink identifies the variant by client_product_id + size_id + color_id
            size_id = SIZE_ID_MAP.get(oi.size.upper(), "2")  # default M
            line_items.append({
                "search_from_my_products": 1,
                "client_product_id": product.qikink_client_product_id,
                "size_id": size_id,
                "color_id": product.qikink_color_id or "2",  # default Black
                "quantity": str(oi.quantity),
                "price": str(oi.unit_price),
            })
        elif product.qikink_sku and product.qikink_design_code:
            # Fallback: SKU + inline design
            size_map = {"XS":"XS","S":"S","M":"M","L":"L","XL":"XL","XXL":"XXL"}
            suffix = size_map.get(oi.size.upper(), oi.size.upper())
            sku = product.qikink_sku if product.qikink_sku.endswith(f"-{suffix}") else f"{product.qikink_sku}-{suffix}"
            line_items.append({
                "search_from_my_products": 0,
                "print_type_id": product.qikink_print_type_id or 1,
                "sku": sku,
                "quantity": str(oi.quantity),
                "price": str(oi.unit_price),
                "designs": [{
                    "design_code": product.qikink_design_code,
                    "width_inches": "",
                    "height_inches": "",
                    "placement_sku": "fr",
                    "design_link": product.qikink_design_url or "",
                    "mockup_link": product.qikink_mockup_url or oi.image or "",
                }],
            })
        else:
            print(f"Warning: {oi.product_name} has no Qikink config — skipped")
            continue

    if not line_items:
        raise ValueError("No Qikink-configured items in this order")

    payload = {
        "order_number": order.id,
        "qikink_shipping": "1",
        "gateway": "Prepaid",
        "total_order_value": str(order.total),
        "line_items": line_items,
        "shipping_address": {
            "first_name": first_name,
            "last_name": last_name,
            "address1": addr_raw.get("line1", ""),
            "address2": addr_raw.get("line2", ""),
            "phone": order.phone or "",
            "email": order.customer_email,
            "city": addr_raw.get("city", ""),
            "zip": addr_raw.get("pincode", ""),
            "province": addr_raw.get("state", ""),
            "country_code": "IN",
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base_url()}/api/order/create",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def get_qikink_order(qikink_order_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_base_url()}/api/order",
            headers=_headers(),
            params={"id": qikink_order_id},
        )
        resp.raise_for_status()
        return resp.json()

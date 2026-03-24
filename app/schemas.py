from pydantic import BaseModel, EmailStr
from typing import List, Optional


class BasicInfo(BaseModel):
    name: str
    email: EmailStr
    instagramHandle: Optional[str] = ""
    twitterHandle: Optional[str] = ""


class StylePreferences(BaseModel):
    styles: List[str]
    otherStyles: Optional[str] = ""


class ClothingTypes(BaseModel):
    types: List[str]


class PricingPreferences(BaseModel):
    priceRange: str


class Feedback(BaseModel):
    designSuggestions: str
    generalFeedback: str


class Consent(BaseModel):
    cashbackConsent: bool
    subscribeUpdates: bool = False


class InterestForm(BaseModel):
    basicInfo: BasicInfo
    stylePreferences: StylePreferences
    clothingTypes: ClothingTypes
    pricingPreferences: PricingPreferences
    feedback: Feedback
    consent: Consent


class NewsletterPayload(BaseModel):
    subject: str
    body: str


class ContactPayload(BaseModel):
    name: str
    email: EmailStr
    message: str


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    price: float
    compare_at_price: Optional[float] = None
    images: List[str] = []
    sizes: List[str] = []
    stock_per_size: dict = {}
    category: Optional[str] = ""
    tags: List[str] = []
    is_active: bool = True
    # Qikink fulfillment
    qikink_sku: Optional[str] = None
    qikink_print_type_id: Optional[int] = None
    qikink_design_code: Optional[str] = None
    qikink_design_url: Optional[str] = None
    qikink_mockup_url: Optional[str] = None
    qikink_client_product_id: Optional[str] = None  # from Qikink "My Products"
    qikink_color_id: Optional[str] = None           # e.g. "2"=Black, "3"=Navy Blue


class OrderItemIn(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    size: str
    quantity: int
    unit_price: float
    image: Optional[str] = None


class ShippingAddressIn(BaseModel):
    name: str
    email: EmailStr
    phone: str
    line1: str
    line2: Optional[str] = ""
    city: str
    state: str
    pincode: str
    country: str = "India"


class OrderCreate(BaseModel):
    items: List[OrderItemIn]
    shipping_address: ShippingAddressIn
    subtotal: float
    discount: float = 0
    shipping: float = 0
    total: float
    coupon_code: Optional[str] = None


class RazorpayVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    order_id: str


class OrderStatusUpdate(BaseModel):
    status: str

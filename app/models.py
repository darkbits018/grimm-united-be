from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255))
    instagram_handle = Column(String(255), nullable=True)
    twitter_handle = Column(String(255), nullable=True)
    styles = Column(Text)
    other_styles = Column(Text, nullable=True)
    clothing_types = Column(Text)
    price_range = Column(String(100))
    design_suggestions = Column(Text)
    general_feedback = Column(Text)
    cashback_consent = Column(Boolean)
    subscribe_updates = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    compare_at_price = Column(Float, nullable=True)
    images = Column(Text, default="[]")
    sizes = Column(Text, default="[]")
    stock_per_size = Column(Text, default="{}")
    category = Column(String(100))
    tags = Column(Text, default="[]")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Qikink fulfillment fields
    qikink_sku = Column(String(100), nullable=True)
    qikink_print_type_id = Column(Integer, nullable=True)
    qikink_design_code = Column(String(100), nullable=True)
    qikink_design_url = Column(Text, nullable=True)
    qikink_mockup_url = Column(Text, nullable=True)
    qikink_client_product_id = Column(String(50), nullable=True)  # e.g. "31964577"
    qikink_color_id = Column(String(10), nullable=True)           # e.g. "2" for Black
    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    id = Column(String(50), primary_key=True)
    razorpay_order_id = Column(String(255), nullable=True)
    razorpay_payment_id = Column(String(255), nullable=True)
    customer_name = Column(String(255))
    customer_email = Column(String(255))
    phone = Column(String(50), nullable=True)
    shipping_address = Column(Text)
    status = Column(String(50), default="pending")
    subtotal = Column(Float)
    discount = Column(Float, default=0)
    shipping = Column(Float, default=0)
    total = Column(Float)
    coupon_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    qikink_order_id = Column(String(100), nullable=True)  # Qikink's internal order_id after fulfillment push
    qikink_push_failed = Column(Boolean, default=False)   # True if auto-push failed — needs manual CSV upload
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(255))
    size = Column(String(20))
    quantity = Column(Integer)
    unit_price = Column(Float)
    image = Column(Text, nullable=True)
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)
    discount_percent = Column(Float, nullable=False)
    max_uses = Column(Integer, nullable=True)
    uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

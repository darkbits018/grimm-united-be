from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import Column, Integer, String, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
import os
import json
from dotenv import load_dotenv

# Environment variables will be loaded below using the absolute path

COUNTER_FILE = "stats.json"

def get_stats():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "r") as f:
            return json.load(f)
    return {"interest_count": 1250} # Starting base

def update_stats():
    stats = get_stats()
    stats["interest_count"] += 1
    with open(COUNTER_FILE, "w") as f:
        json.dump(stats, f)
    return stats

# Get absolute path to .env and load it
base_dir = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(base_dir, ".env")
load_dotenv(env_file)

class Settings(BaseSettings):
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    DATABASE_URL: Optional[str] = None
    
    # Values will be read from the environment (populated by load_dotenv)
    model_config = SettingsConfigDict(extra="ignore")

try:
    settings = Settings()
    print("Success: Settings loaded from .env")
except Exception as e:
    print(f"Warning: Settings could not be loaded. Error: {e}")
    settings = None

# Database Setup
Base = declarative_base()

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255))
    instagram_handle = Column(String(255), nullable=True)
    twitter_handle = Column(String(255), nullable=True)
    styles = Column(Text) # Stored as comma separated or JSON string
    other_styles = Column(Text, nullable=True)
    clothing_types = Column(Text)
    price_range = Column(String(100))
    design_suggestions = Column(Text)
    general_feedback = Column(Text)
    cashback_consent = Column(Boolean)
    subscribe_updates = Column(Boolean)

engine = None
SessionLocal = None

if settings and settings.DATABASE_URL:
    try:
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        print("Success: Connected to PostgreSQL database")
    except Exception as e:
        print(f"Warning: Could not connect to database. Error: {e}")

import asyncio

app = FastAPI()

# Background task to simulate organic growth
async def simulate_growth():
    while True:
        await asyncio.sleep(60) # Every minute
        if os.path.exists(COUNTER_FILE):
             update_stats()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulate_growth())

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def read_root():
    return {"status": "Grimm United Backend is running"}

@app.get("/api/stats")
def get_interest_stats():
    return get_stats()

@app.post("/api/interest")
async def submit_interest(data: InterestForm):
    # Update count locally
    update_stats()
    
    # Save to Database if configured
    if SessionLocal:
        try:
            db = SessionLocal()
            db_submission = Submission(
                name=data.basicInfo.name,
                email=data.basicInfo.email,
                instagram_handle=data.basicInfo.instagramHandle,
                twitter_handle=data.basicInfo.twitterHandle,
                styles=", ".join(data.stylePreferences.styles),
                other_styles=data.stylePreferences.otherStyles,
                clothing_types=", ".join(data.clothingTypes.types),
                price_range=data.pricingPreferences.priceRange,
                design_suggestions=data.feedback.designSuggestions,
                general_feedback=data.feedback.generalFeedback,
                cashback_consent=data.consent.cashbackConsent,
                subscribe_updates=data.consent.subscribeUpdates
            )
            db.add(db_submission)
            db.commit()
            db.close()
            print(f"Success: Submission from {data.basicInfo.email} saved to database")
        except Exception as e:
            print(f"Error saving to database: {e}")
            # We continue to send email even if DB fails for now
    
    if not settings:
        raise HTTPException(status_code=500, detail="Backend mail settings not configured.")
    
    # Create the email body
    html = f"""
    <html>
        <body>
            <h3>New Interest Form Submission</h3>
            <p><b>Name:</b> {data.basicInfo.name}</p>
            <p><b>Email:</b> {data.basicInfo.email}</p>
            <p><b>Instagram:</b> {data.basicInfo.instagramHandle or 'N/A'}</p>
            <p><b>Twitter:</b> {data.basicInfo.twitterHandle or 'N/A'}</p>
            <hr>
            <p><b>Style Preferences:</b> {', '.join(data.stylePreferences.styles)}</p>
            <p><b>Other Styles:</b> {data.stylePreferences.otherStyles or 'None'}</p>
            <p><b>Clothing Types:</b> {', '.join(data.clothingTypes.types)}</p>
            <p><b>Price Range:</b> {data.pricingPreferences.priceRange}</p>
            <hr>
            <p><b>Design Suggestions:</b> {data.feedback.designSuggestions}</p>
            <p><b>General Feedback:</b> {data.feedback.generalFeedback}</p>
            <hr>
            <p><b>Cashback Consent:</b> {'Yes' if data.consent.cashbackConsent else 'No'}</p>
            <p><b>Subscribed to Updates:</b> {'Yes' if data.consent.subscribeUpdates else 'No'}</p>
        </body>
    </html>
    """

    message = MIMEMultipart()
    message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    message["To"] = settings.MAIL_FROM
    message["Subject"] = f"New Interest: {data.basicInfo.name}"
    message.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.MAIL_SERVER,
            port=settings.MAIL_PORT,
            username=settings.MAIL_USERNAME,
            password=settings.MAIL_PASSWORD,
            use_tls=False,
            start_tls=True if settings.MAIL_PORT == 587 else False
        )
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification email: {str(e)}")

    return {"message": "Interest submitted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

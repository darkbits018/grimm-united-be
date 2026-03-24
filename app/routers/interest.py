from fastapi import APIRouter, Header, HTTPException
from app.schemas import InterestForm, NewsletterPayload
from app.models import Submission
from app.database import SessionLocal
from app.utils import require_admin, send_email
from app.config import settings
from app.stats import update_stats

router = APIRouter()


@router.post("/api/interest")
async def submit_interest(data: InterestForm):
    update_stats()
    if SessionLocal:
        try:
            db = SessionLocal()
            db.add(Submission(
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
                subscribe_updates=data.consent.subscribeUpdates,
            ))
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error saving submission: {e}")

    if not settings:
        raise HTTPException(status_code=500, detail="Backend mail settings not configured.")

    html = f"""<html><body>
        <h3>New Interest Form Submission</h3>
        <p><b>Name:</b> {data.basicInfo.name}</p>
        <p><b>Email:</b> {data.basicInfo.email}</p>
        <p><b>Instagram:</b> {data.basicInfo.instagramHandle or 'N/A'}</p>
        <p><b>Twitter:</b> {data.basicInfo.twitterHandle or 'N/A'}</p>
        <hr>
        <p><b>Styles:</b> {', '.join(data.stylePreferences.styles)}</p>
        <p><b>Other Styles:</b> {data.stylePreferences.otherStyles or 'None'}</p>
        <p><b>Clothing Types:</b> {', '.join(data.clothingTypes.types)}</p>
        <p><b>Price Range:</b> {data.pricingPreferences.priceRange}</p>
        <hr>
        <p><b>Design Suggestions:</b> {data.feedback.designSuggestions}</p>
        <p><b>General Feedback:</b> {data.feedback.generalFeedback}</p>
        <hr>
        <p><b>Cashback Consent:</b> {'Yes' if data.consent.cashbackConsent else 'No'}</p>
        <p><b>Subscribed:</b> {'Yes' if data.consent.subscribeUpdates else 'No'}</p>
    </body></html>"""

    await send_email(settings.MAIL_FROM, f"New Interest: {data.basicInfo.name}", html)
    return {"message": "Interest submitted successfully"}


@router.get("/api/admin/submissions")
async def get_submissions(x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    submissions = db.query(Submission).order_by(Submission.id.desc()).all()
    db.close()
    return submissions


@router.get("/api/admin/analytics")
async def get_analytics(x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    submissions = db.query(Submission).all()
    db.close()
    total = len(submissions)
    style_counts, clothing_counts, price_counts = {}, {}, {}
    for s in submissions:
        if s.styles:
            for style in s.styles.split(", "):
                style_counts[style] = style_counts.get(style, 0) + 1
        if s.clothing_types:
            for c in s.clothing_types.split(", "):
                clothing_counts[c] = clothing_counts.get(c, 0) + 1
        if s.price_range:
            price_counts[s.price_range] = price_counts.get(s.price_range, 0) + 1
    return {"total_submissions": total, "style_distribution": style_counts,
            "clothing_distribution": clothing_counts, "price_distribution": price_counts}


@router.post("/api/admin/newsletter")
async def send_newsletter(payload: NewsletterPayload, x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    subscribers = db.query(Submission).filter(Submission.subscribe_updates == True).all()
    db.close()
    if not subscribers:
        return {"message": "No subscribers found", "sent": 0}
    sent, failed = 0, 0
    for sub in subscribers:
        try:
            await send_email(sub.email, payload.subject, payload.body)
            sent += 1
        except Exception:
            failed += 1
    return {"message": "Newsletter sent", "sent": sent, "failed": failed}

from fastapi import APIRouter, Header, HTTPException
from app.schemas import ContactPayload
from app.models import ContactMessage
from app.database import SessionLocal
from app.utils import require_admin, send_email
from app.config import settings

router = APIRouter()


@router.post("/api/contact")
async def contact(data: ContactPayload):
    if SessionLocal:
        try:
            db = SessionLocal()
            db.add(ContactMessage(name=data.name, email=data.email, message=data.message))
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error saving contact message: {e}")
    if settings:
        html = f"""<html><body>
            <h3>New Contact Message</h3>
            <p><b>Name:</b> {data.name}</p>
            <p><b>Email:</b> {data.email}</p>
            <hr>
            <p><b>Message:</b></p>
            <p>{data.message}</p>
        </body></html>"""
        try:
            await send_email(settings.MAIL_FROM, f"Contact: {data.name}", html)
        except Exception as e:
            print(f"Email send failed: {e}")
    return {"message": "Message sent"}


@router.get("/api/admin/contacts")
def get_contacts(x_admin_token: str = Header(None)):
    require_admin(x_admin_token)
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database not connected")
    db = SessionLocal()
    messages = db.query(ContactMessage).order_by(ContactMessage.id.desc()).all()
    db.close()
    return [
        {"id": m.id, "name": m.name, "email": m.email, "message": m.message,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in messages
    ]

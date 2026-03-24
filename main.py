import asyncio
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.stats import simulate_growth
from app.routers import general, contact, interest, products, orders, coupons

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(general.router)
app.include_router(contact.router)
app.include_router(interest.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(coupons.router)


async def keep_alive():
    if not settings or not settings.RENDER_EXTERNAL_URL:
        return
    while True:
        await asyncio.sleep(600)
        try:
            async with httpx.AsyncClient() as client:
                await client.get(settings.RENDER_EXTERNAL_URL)
        except Exception as e:
            print(f"Self-ping failed: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

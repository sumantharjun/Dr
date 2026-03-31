from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.models import *  # noqa: F401,F403 — ensures all models are registered
from app.routers import auth, devices, feeding, washing, dispensing, alerts, orders, metrics, activity

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Baby Feeding API",
    description="Backend API for the Smart Baby Feeding & Bottle Care Monitoring System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(feeding.router)
app.include_router(washing.router)
app.include_router(dispensing.router)
app.include_router(alerts.router)
app.include_router(orders.router)
app.include_router(metrics.router)
app.include_router(activity.router)


@app.on_event("startup")
def seed_products():
    """Seed default products if none exist."""
    db = SessionLocal()
    try:
        from app.models.order import Product
        if db.query(Product).count() == 0:
            products = [
                Product(name="Baby Bottle Cleaning Liquid 500ml", description="Specially formulated cleaning liquid for baby bottles.", price=12.99, category="cleaning", stock=100),
                Product(name="Baby Bottle Cleaning Liquid 1L", description="Economy size cleaning liquid for baby bottles.", price=19.99, category="cleaning", stock=50),
                Product(name="Baby Bottle 240ml (Pack of 3)", description="BPA-free wide-neck baby bottles.", price=24.99, category="bottles", stock=80),
                Product(name="Bottle Brush Set", description="Soft-bristle brush set for manual cleaning.", price=8.99, category="accessories", stock=60),
                Product(name="Sterilization Tablets (50 pack)", description="Effervescent sterilization tablets.", price=9.99, category="cleaning", stock=120),
                Product(name="Baby Bottle Nipples Size M (4 pack)", description="Medium-flow silicone nipples.", price=7.99, category="accessories", stock=90),
            ]
            db.add_all(products)
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}

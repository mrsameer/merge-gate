from fastapi import FastAPI

from app.orders.router import router as orders_router

app = FastAPI(title="Demo Orders Service")
app.include_router(orders_router, prefix="/orders", tags=["orders"])

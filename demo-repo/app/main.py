"""FastAPI entrypoint for the demo order service."""

from fastapi import FastAPI

from app.orders.router import router as orders_router

app = FastAPI(title="Demo Order Service")
app.include_router(orders_router)

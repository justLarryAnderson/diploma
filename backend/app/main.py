from fastapi import FastAPI
from app.routes import train, predict

app = FastAPI(title="Diploma Vision", version="1.0")

app.include_router(train.router, prefix="/api", tags=["train"])
app.include_router(predict.router, prefix="/api", tags=["predict"])

@app.get("/")
async def root():
    return {"message": "Diploma Vision API"}
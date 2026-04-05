# в файле predict.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, Task
from sqlalchemy import select
import uuid

router = APIRouter()

@router.post("/predict/{task_id}")
async def predict(
    task_id: uuid.UUID,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # Находим задачу
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Model not ready yet")
    
    # Здесь будет загрузка модели и инференс
    # Пока вернём заглушку
    return {"detections": []}
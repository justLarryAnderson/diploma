import uuid
import os
import zipfile
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, Task
from app.schemas import TrainRequest, TrainResponse, TaskStatus
import aiofiles
from fastapi.responses import Response, FileResponse

router = APIRouter()

# Папка для хранения датасетов (монтируется в volume)
DATASETS_ROOT = Path("/app/data/datasets")

async def validate_dataset_structure(zip_path: Path) -> bool:
    """
    Проверяет, что внутри zip-архива есть:
    - data.yaml
    - train/images/
    - train/labels/
    (и/или val/images, val/labels — опционально)
    Возвращает True, если структура корректна.
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            # Проверяем наличие обязательных файлов и папок
            has_data_yaml = any('data.yaml' in f for f in files)
            has_train_images = any('train/images' in f for f in files)
            has_train_labels = any('train/labels' in f for f in files)
            # Для простоты будем требовать только train, валидация опциональна
            if has_data_yaml and has_train_images and has_train_labels:
                return True
            return False
    except Exception as e:
        return False

@router.post("/train", response_model=TrainResponse)
async def start_training(
    name: str = Form(...),
    epochs: int = Form(50),
    model_size: str = Form("n"),
    dataset: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None  # пока не используем, но оставим
):
    # 1. Создаём уникальный ID задачи
    task_id = uuid.uuid4()
    task_dir = DATASETS_ROOT / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Сохраняем загруженный zip-файл временно
    zip_path = task_dir / "dataset.zip"
    
    # Используем aiofiles для асинхронной записи
    async with aiofiles.open(zip_path, 'wb') as out_file:
        content = await dataset.read()
        await out_file.write(content)
    
    # 3. Проверяем структуру архива
    if not await validate_dataset_structure(zip_path):
        # Удаляем папку задачи, если структура невалидна
        shutil.rmtree(task_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Invalid dataset structure. Expected data.yaml, train/images, train/labels.")
    
    # 4. Распаковываем архив в ту же папку (для удобства)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(task_dir)
    # Удаляем zip-файл после распаковки
    zip_path.unlink()
    
    # 5. Создаём запись в БД
    new_task = Task(
        id=task_id,
        user_id="user_1",  # для демо, позже можно добавить авторизацию
        name=name,
        status="pending",
        dataset_path=str(task_dir)
    )
    db.add(new_task)
    await db.commit()
    
    # 6. Формируем URL для скачивания датасета (который будет использовать Kaggle)
    # Бэкенд доступен по порту 8000, внутри Docker-сети — backend:8000, но для Kaggle нужен публичный адрес.
    # Для разработки можно использовать ngrok или развернуть на сервере.
    # Пока вернём локальный URL, который будет работать только если Kaggle ноутбук запущен локально.
    # В реальном дипломе нужно будет использовать публичный URL (например, через ngrok).
    dataset_url = f"http://backend:8000/api/dataset/{task_id}"  # внутри Docker сети
    # Для доступа извне при локальной разработке можно использовать http://localhost:8000/api/dataset/{task_id}
    # но Kaggle ноутбук не сможет обратиться к localhost. Обсудим позже.
    
    return TrainResponse(
        task_id=task_id,
        status="pending",
        dataset_url=dataset_url
    )
    
from fastapi.responses import FileResponse

@router.get("/dataset/{task_id}")
async def download_dataset(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # Находим задачу
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Папка с датасетом
    dataset_path = Path(task.dataset_path)
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="Dataset not found on disk")
    
    # Создаём zip-архив на лету и отдаём
    # Но чтобы не хранить дубликат, можно заархивировать прямо в ответе
    import io
    import zipfile
    
    # Создаём буфер в памяти
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dataset_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, dataset_path)
                zf.write(full_path, arcname)
    
    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=dataset_{task_id}.zip"}
    )
    
@router.post("/train/{task_id}/complete")
async def complete_training(
    task_id: uuid.UUID,
    metrics: str = Form(...),  # получаем JSON строку
    model_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # Находим задачу
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем, что задача в статусе pending
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Task already completed or in progress")
    
    # Сохраняем модель
    model_dir = Path("/app/models") / str(task_id)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "best.pt"
    
    async with aiofiles.open(model_path, 'wb') as out_file:
        content = await model_file.read()
        await out_file.write(content)
    
    # Парсим метрики
    import json
    try:
        metrics_dict = json.loads(metrics)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metrics JSON")
    
    # Обновляем запись в БД
    task.status = "completed"
    task.model_path = str(model_path)
    task.metrics = metrics_dict
    await db.commit()
    
    return {"status": "completed", "task_id": str(task_id)}

@router.get("/train/{task_id}", response_model=TaskStatus)
async def get_training_status(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(
        id=task.id,
        name=task.name,
        status=task.status,
        metrics=task.metrics,
        created_at=task.created_at,
        updated_at=task.updated_at
    )
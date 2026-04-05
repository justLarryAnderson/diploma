from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

class TrainRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())  # отключаем защиту
    name: str
    epochs: int = Field(50, ge=1, le=300)
    model_size: str = Field("n", pattern="^(n|s|m|l|x)$")

class TrainResponse(BaseModel):
    task_id: UUID
    status: str
    dataset_url: str

class TaskStatus(BaseModel):
    id: UUID
    name: str
    status: str
    metrics: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class CompleteTrainRequest(BaseModel):
    metrics: Dict[str, Any]

class PredictResponse(BaseModel):
    detections: list
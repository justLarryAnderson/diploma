from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, func, JSON, Text
import uuid
from sqlalchemy.dialects.postgresql import UUID

# Используем asyncpg
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/diploma"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# Модель таблицы tasks
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    dataset_path = Column(Text, nullable=True)
    model_path = Column(Text, nullable=True)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
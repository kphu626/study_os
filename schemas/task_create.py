import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class TaskCreate(BaseModel):
    description: str
    deadline: Optional[str] = None

    @validator("deadline")
    def valid_future_date(cls, v: Optional[str]):
        if v is None or not v.strip():
            return None
        try:
            datetime.fromisoformat(v.strip())
            return v.strip()
        except ValueError:
            raise ValueError(f"Invalid deadline format: '{v}'. Use YYYY-MM-DD.")


class TaskResponse(TaskCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed: bool = False

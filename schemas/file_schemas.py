from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import Optional


class FileAttachment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_name: str
    stored_filename: str  # Unique filename in the assets directory
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

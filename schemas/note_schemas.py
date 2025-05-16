from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import List, Optional

from .file_schemas import FileAttachment


class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = ""
    tags: Optional[List[str]] = Field(default_factory=list)
    linked_note_ids: List[str] = Field(default_factory=list)
    attachments: List[FileAttachment] = Field(default_factory=list)
    parent_id: Optional[str] = None
    is_folder: bool = False
    order: int = 0
    icon: Optional[str] = None


class NoteCreate(NoteBase):
    pass


class Note(NoteBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # For Pydantic V1, use `orm_mode = True` if you were loading from ORM
        # For Pydantic V2, use `from_attributes = True`
        from_attributes = True

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class FlashcardBase(BaseModel):
    question: str = Field(..., alias="q", min_length=1)
    answer: str = Field(..., alias="a", min_length=1)


class FlashcardCreate(FlashcardBase):
    pass


class Flashcard(FlashcardBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # deck_id: Optional[str] = None # Example: if you add decks
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Changed from orm_mode
        populate_by_name = True  # Changed from allow_population_by_field_name

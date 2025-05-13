"""
Pydantic Schemas for StudyOS
"""

from .task_create import TaskCreate, TaskResponse
from .note_schemas import Note, NoteCreate, NoteBase
from .flashcard_schema import Flashcard, FlashcardCreate, FlashcardBase
from .progress_schema import ProgressData, ProgressEntry

__all__ = [
    "TaskCreate",
    "TaskResponse",
    "Note",
    "NoteCreate",
    "NoteBase",
    "Flashcard",
    "FlashcardCreate",
    "FlashcardBase",
    "ProgressData",
    "ProgressEntry",
]

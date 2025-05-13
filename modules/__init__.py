"""
StudyOS Modules Package
This file makes the 'modules' directory a Python package and exposes
the module classes for easier importing.
"""

from .base_module import BaseModule
from .notes_module import NotesModule
from .flashcards_module import FlashcardModule
from .tasks_module import TaskModule
from .progress_module import ProgressModule
from .settings_module import SettingsModule
from .statistics_module import StatisticsModule

# Optional: Define __all__ to specify what `from modules import *` imports.
# This is good practice if you intend for `import *` to be used,
# though explicit imports (as in your main.py) are generally preferred.
__all__ = [
    "BaseModule",
    "NotesModule",
    "FlashcardModule",
    "TaskModule",
    "ProgressModule",
    "SettingsModule",
    "StatisticsModule",
]

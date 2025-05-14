import dearpygui.dearpygui as dpg
from typing import TYPE_CHECKING, Union, Optional, cast

from .base_module import BaseModule
from .notes_module import NotesModule
from .tasks_module import TaskModule
from .flashcards_module import FlashcardModule

# from core import Core # Removed old import

if TYPE_CHECKING:  # Added TYPE_CHECKING block
    from core.app import Core  # Import Core from core.app for type hinting

    # from .notes_module import NotesModule # Moved out
    # from .tasks_module import TaskModule # Moved out
    # from .flashcards_module import FlashcardModule # Moved out
    from ..schemas.task_create import TaskResponse  # Corrected: path and file name


class StatisticsModule(BaseModule):
    def __init__(self, core: "Core"):  # Changed to string literal "Core"
        super().__init__(core)
        # self.theme = theme_manager # Redundant if core.theme_manager is used
        # If you need theme_manager specifically, access via self.core.theme_manager
        self.dpg_notes_count_tag: Union[int, str] = 0
        self.dpg_tasks_total_tag: Union[int, str] = 0
        self.dpg_tasks_completed_tag: Union[int, str] = 0
        self.dpg_flashcards_count_tag: Union[int, str] = 0

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the Dear PyGui view for the Statistics module."""
        self.dpg_notes_count_tag = dpg.generate_uuid()
        self.dpg_tasks_total_tag = dpg.generate_uuid()
        self.dpg_tasks_completed_tag = dpg.generate_uuid()
        self.dpg_flashcards_count_tag = dpg.generate_uuid()

        with dpg.group(parent=parent_container_tag):
            dpg.add_text("Application Statistics", color=(220, 220, 220))
            dpg.add_separator()

            dpg.add_button(
                label="Refresh Statistics", callback=self.load_data, width=-1
            )
            dpg.add_separator()

            dpg.add_text("Notes:", color=(180, 180, 180))
            dpg.add_text("Total Notes: ", tag=self.dpg_notes_count_tag)

            dpg.add_spacer(height=10)
            dpg.add_text("Tasks:", color=(180, 180, 180))
            dpg.add_text("Total Tasks: ", tag=self.dpg_tasks_total_tag)
            dpg.add_text("Completed Tasks: ", tag=self.dpg_tasks_completed_tag)

            dpg.add_spacer(height=10)
            dpg.add_text("Flashcards:", color=(180, 180, 180))
            dpg.add_text("Total Flashcards: ", tag=self.dpg_flashcards_count_tag)

        self.load_data()  # Initial load of stats

    def load_data(
        self, sender=None, app_data=None, user_data=None
    ):  # Added DPG callback signature
        """Loads and displays statistics from other modules."""
        # print(f"[{self.__class__.__name__}] load_data called.")

        notes_count = 0
        tasks_total = 0
        tasks_completed = 0
        flashcards_count = 0

        notes_module_instance = self.core.module_registry.get(
            "Notes"
        )  # Reverted to original key "Notes"
        if isinstance(notes_module_instance, NotesModule):
            # Now type checkers know notes_module_instance is NotesModule
            notes_count = len(notes_module_instance.notes)
        # else:
        # self.core.logger.warning("NotesModule not found or not of type NotesModule in registry.")

        tasks_module_instance = self.core.module_registry.get(
            "Tasks"
        )  # Reverted to original key "Tasks"
        if isinstance(tasks_module_instance, TaskModule):  # Corrected: TaskModule
            # Now type checkers know tasks_module_instance is TasksModule
            tasks_total = len(tasks_module_instance.tasks)
            # Ensuring task is hinted for clarity, assuming tasks_module_instance.tasks contains TaskResponse objects
            tasks_completed = sum(
                1 for task in tasks_module_instance.tasks if task.completed
            )
        # else:
        # self.core.logger.warning("TasksModule not found or not of type TasksModule in registry.")

        flashcards_module_instance = self.core.module_registry.get(
            "Flashcards"
        )  # Reverted to original key "Flashcards"
        if isinstance(
            flashcards_module_instance, FlashcardModule
        ):  # Corrected: FlashcardModule
            # Now type checkers know flashcards_module_instance is FlashcardsModule
            flashcards_count = len(flashcards_module_instance.cards)
        # else:
        # self.core.logger.warning("FlashcardsModule not found or not of type FlashcardsModule in registry.")

        # Update DPG text items if they exist
        if dpg.is_dearpygui_running():  # Ensure DPG is active
            if dpg.does_item_exist(self.dpg_notes_count_tag):
                dpg.set_value(self.dpg_notes_count_tag, f"Total Notes: {notes_count}")
            if dpg.does_item_exist(self.dpg_tasks_total_tag):
                dpg.set_value(self.dpg_tasks_total_tag, f"Total Tasks: {tasks_total}")
            if dpg.does_item_exist(self.dpg_tasks_completed_tag):
                dpg.set_value(
                    self.dpg_tasks_completed_tag, f"Completed Tasks: {tasks_completed}"
                )
            if dpg.does_item_exist(self.dpg_flashcards_count_tag):
                dpg.set_value(
                    self.dpg_flashcards_count_tag,
                    f"Total Flashcards: {flashcards_count}",
                )
        # print(f"[{self.__class__.__name__}] Stats updated: N={notes_count}, T={tasks_total}, C={tasks_completed}, F={flashcards_count}")

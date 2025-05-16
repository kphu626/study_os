import json
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Union

import dearpygui.dearpygui as dpg
from pydantic import ValidationError

from schemas import TaskCreate, TaskResponse

from .base_module import BaseModule

if TYPE_CHECKING:
    from core.app import Core


class TaskModule(BaseModule):
    def __init__(self, core: "Core"):
        super().__init__(core)

        if (
            hasattr(self.core, "config")
            and self.core.config is not None
            and hasattr(self.core.config, "tasks_path")
        ):
            self.data_path = self.core.config.tasks_path
        else:
            from core.config import AppConfig as DefaultAppConfig

            self.data_path = DefaultAppConfig().tasks_path
            print(
                f"Warning: TaskModule could not find tasks_path in core.config. Using default: {self.data_path}",
            )
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        self.tasks: List[TaskResponse] = []

        # Initialize DPG tags with placeholders
        self.dpg_description_input_tag: Union[int, str] = 0
        self.dpg_deadline_input_tag: Union[int, str] = 0
        self.dpg_tasks_list_container_tag: Union[int, str] = 0
        self.dpg_status_text_tag: Union[int, str] = 0

    def _load_tasks_from_file(self) -> List[TaskResponse]:
        """Loads tasks from the JSON file and parses them into TaskResponse objects."""
        loaded_tasks: List[TaskResponse] = []
        if self.data_path.exists() and self.data_path.stat().st_size > 0:
            try:
                raw_data = json.loads(
                    self.data_path.read_text(encoding="utf-8"))
                if isinstance(raw_data, list):
                    for task_item_data in raw_data:
                        if isinstance(task_item_data, dict):
                            try:
                                # Ensure datetime fields are handled if stored as strings
                                # Field renamed to created_at in schema
                                if "created_at" in task_item_data and isinstance(
                                    task_item_data["created_at"],
                                    str,
                                ):
                                    task_item_data["created_at"] = (
                                        datetime.fromisoformat(
                                            task_item_data["created_at"],
                                        )
                                    )
                                elif "created" in task_item_data and isinstance(
                                    task_item_data["created"],
                                    str,
                                ):
                                    # Handle old data if necessary
                                    task_item_data["created_at"] = (
                                        datetime.fromisoformat(
                                            task_item_data["created"],
                                        )
                                    )
                                    del task_item_data["created"]

                                loaded_tasks.append(
                                    TaskResponse(**task_item_data))
                            except ValidationError as e:
                                print(
                                    f"Skipping a task due to validation error: {e.errors()}",
                                )
                            except Exception as e:
                                print(
                                    f"Skipping a task due to other parsing error: {e} for data {task_item_data}",
                                )
            except json.JSONDecodeError:
                print(
                    f"Error decoding JSON from {self.data_path}. Starting with an empty list.",
                )
            except Exception as e:
                print(
                    f"An unexpected error occurred while loading tasks from file: {e}",
                )
        return loaded_tasks

    def _save_tasks_to_file(self):
        """Saves the current self.tasks list to the JSON file."""
        try:
            tasks_to_save = []
            for task in self.tasks:
                task_dict = task.model_dump()
                # Field renamed to created_at
                if isinstance(task_dict.get("created_at"), datetime):
                    task_dict["created_at"] = task_dict["created_at"].isoformat()
                elif "created" in task_dict and isinstance(task_dict["created"], str):
                    task_dict["created_at"] = datetime.fromisoformat(
                        task_dict["created"],
                    )
                    del task_dict["created"]
                tasks_to_save.append(task_dict)

            self.data_path.write_text(
                json.dumps(tasks_to_save, indent=2),
                encoding="utf-8",
            )
            if dpg.does_item_exist(self.dpg_status_text_tag):
                dpg.set_value(self.dpg_status_text_tag, "Tasks saved.")
        except Exception as e:
            print(f"Error saving tasks to {self.data_path}: {e}")
            if dpg.does_item_exist(self.dpg_status_text_tag):
                dpg.set_value(self.dpg_status_text_tag,
                              f"Error saving tasks: {e}")

    def load_data(self):
        """Loads tasks from file into self.tasks and refreshes the DPG list."""
        self.tasks = self._load_tasks_from_file()
        print(f"[{self.__class__.__name__}] {len(self.tasks)} tasks loaded.")
        if dpg.is_dearpygui_running() and dpg.does_item_exist(
            self.dpg_tasks_list_container_tag,
        ):
            self._dpg_display_tasks_list()
        elif not dpg.is_dearpygui_running():
            pass
        else:
            print(
                f"[{self.__class__.__name__}] DPG tasks list container not ready during load_data.",
            )

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the Dear PyGui view for the Tasks module."""
        # Generate DPG tags now
        self.dpg_description_input_tag = dpg.generate_uuid()
        self.dpg_deadline_input_tag = dpg.generate_uuid()
        self.dpg_tasks_list_container_tag = dpg.generate_uuid()
        self.dpg_status_text_tag = dpg.generate_uuid()

        with dpg.group(parent=parent_container_tag):
            dpg.add_text("Manage Your Tasks", color=(220, 220, 220))
            dpg.add_separator()

            # Input section
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag=self.dpg_description_input_tag,
                    label="Task Description",
                    hint="Enter task details",
                    width=-1,
                )
            add_btn = dpg.add_button(
                label="Add Task",
                callback=self._dpg_add_task_callback,
                width=200,
            )
            with dpg.tooltip(add_btn):
                dpg.add_text("Add a new task to your list")
                dpg.add_text("Format: Description + optional deadline")

            deadline_input = dpg.add_input_text(
                tag=self.dpg_deadline_input_tag,
                label="Deadline (YYYY-MM-DD)",
                hint="Optional deadline",
                width=200,
            )
            with dpg.tooltip(deadline_input):
                dpg.add_text("Optional due date in format: YYYY-MM-DD")

            dpg.add_spacer(height=10)
            self.dpg_status_text_tag = dpg.add_text(
                "", tag=self.dpg_status_text_tag)
            dpg.add_separator()

            # Task list section
            dpg.add_text("Current Tasks:")
            with dpg.child_window(
                tag=self.dpg_tasks_list_container_tag,
                autosize_y=True,
                border=True,
                height=-1,
            ):
                pass

        self.load_data()

    def _dpg_display_tasks_list(self):
        if not dpg.does_item_exist(self.dpg_tasks_list_container_tag):
            print(
                f"[{self.__class__.__name__}] Task list container tag {self.dpg_tasks_list_container_tag} does not exist.",
            )
            return

        dpg.delete_item(self.dpg_tasks_list_container_tag, children_only=True)

        if not self.tasks:
            dpg.add_text(
                "No tasks yet! Add one above.",
                parent=self.dpg_tasks_list_container_tag,
            )
        else:
            # Sort tasks: incomplete first, then by creation date (optional, can be added later)
            # sorted_tasks = sorted(self.tasks, key=lambda t: (t.completed, t.created_at))
            sorted_tasks = self.tasks  # No sorting for now, keep original order

            for task in sorted_tasks:
                with dpg.group(
                    horizontal=True,
                    parent=self.dpg_tasks_list_container_tag,
                ):
                    # Consistent tag format
                    checkbox_tag = f"task_checkbox_{task.id}"
                    dpg.add_checkbox(
                        tag=checkbox_tag,
                        default_value=task.completed,
                        user_data={"task_id": task.id,
                                   "checkbox_tag": checkbox_tag},
                        callback=self._dpg_toggle_task_completion_callback,
                    )

                    task_text_content = task.description
                    task_text_item = dpg.add_text(task_text_content)

                    if task.completed:
                        if dpg.does_item_exist(task_text_item):
                            # Example: dim completed tasks. DPG has no direct strikethrough for add_text.
                            # You might theme specific items or use custom rendering if complex styling is needed.
                            dpg.configure_item(
                                task_text_item, color=(150, 150, 150, 180)
                            )  # Dim color

                    deadline_text = (
                        f"- Deadline: {task.deadline}"
                        if task.deadline
                        else "- No deadline"
                    )
                    dpg.add_text(deadline_text)

                    dpg.add_button(
                        label="Delete",
                        user_data=task.id,
                        callback=self._dpg_delete_task_callback,
                        small=True,
                    )

        if dpg.does_item_exist(self.dpg_status_text_tag):
            dpg.set_value(
                self.dpg_status_text_tag,
                f"Displayed {len(self.tasks)} tasks.",
            )
        # print(f"[{self.__class__.__name__}] Displayed {len(self.tasks)} tasks.")

    def _dpg_toggle_task_completion_callback(self, sender, app_data, user_data):
        task_id = user_data["task_id"]
        # This is the new state of the checkbox (True/False)
        is_completed = app_data

        task_to_update = next((t for t in self.tasks if t.id == task_id), None)
        if task_to_update:
            task_to_update.completed = is_completed
            self._save_tasks_to_file()  # Save change
            # For now, refresh the whole list to reflect changes (like potential re-sorting or style changes)
            self._dpg_display_tasks_list()
            if dpg.does_item_exist(self.dpg_status_text_tag):
                status = "completed" if is_completed else "marked as not completed"
                dpg.set_value(
                    self.dpg_status_text_tag,
                    f"Task '{task_to_update.description[:20]}...' {status}.",
                )
        elif dpg.does_item_exist(self.dpg_status_text_tag):
            dpg.set_value(
                self.dpg_status_text_tag,
                f"Error: Could not find task with ID {task_id} to toggle completion.",
            )

    def _dpg_delete_task_callback(self, sender, app_data, user_data):
        task_id_to_delete = user_data

        # Find and remove the task
        original_len = len(self.tasks)
        self.tasks = [
            task for task in self.tasks if task.id != task_id_to_delete]

        if len(self.tasks) < original_len:
            self._save_tasks_to_file()
            self._dpg_display_tasks_list()  # Refresh the list
            if dpg.does_item_exist(self.dpg_status_text_tag):
                dpg.set_value(self.dpg_status_text_tag, "Task deleted.")
        elif dpg.does_item_exist(self.dpg_status_text_tag):
            dpg.set_value(
                self.dpg_status_text_tag,
                f"Error: Could not find task with ID {task_id_to_delete} to delete.",
            )

    def _dpg_add_task_callback(self, sender, app_data, user_data):
        description = dpg.get_value(self.dpg_description_input_tag)
        deadline_str: Optional[str] = dpg.get_value(
            self.dpg_deadline_input_tag)

        if not description.strip():
            dpg.set_value(
                self.dpg_status_text_tag,
                "Error: Task description cannot be empty.",
            )
            return

        try:
            # Deadline is now Optional in TaskCreate and validated by Pydantic
            current_deadline = deadline_str.strip() if deadline_str else None

            new_task_data = TaskCreate(
                description=description,
                deadline=current_deadline,
            )
            # TaskResponse now handles id and created_at defaults via Field(default_factory=...)
            new_task = TaskResponse(**new_task_data.model_dump())

            self.tasks.append(new_task)
            self._save_tasks_to_file()
            self._dpg_display_tasks_list()
            dpg.set_value(self.dpg_description_input_tag, "")
            dpg.set_value(self.dpg_deadline_input_tag, "")
            dpg.set_value(self.dpg_status_text_tag, "Task added successfully!")

        except ValidationError as exc:
            # Construct a more readable error message from Pydantic details
            error_messages = []
            for error in exc.errors():
                loc = " -> ".join(map(str, error["loc"]))
                error_messages.append(f"Field '{loc}': {error['msg']}")
            full_error_msg = "Validation Error(s): " + \
                "; ".join(error_messages)
            dpg.set_value(self.dpg_status_text_tag, full_error_msg)
            print(
                f"Task creation validation error: {exc.errors()}",
            )  # Log detailed errors
        except Exception as e:
            dpg.set_value(self.dpg_status_text_tag,
                          f"Error adding task: {e!s}")
            print(f"Error adding task: {e}")

    def handle_keyboard(self, key_code: int):
        ENTER_KEY = 532  # Verify with your system
        if key_code == ENTER_KEY:
            # Provide default values for callback parameters
            self._dpg_add_task_callback(
                sender=None, app_data=None, user_data=None)

    def get_focusable_items(self):
        return [self.dpg_description_input_tag, self.dpg_deadline_input_tag]

    def _some_callback(self, sender, app_data, user_data=None):
        """Example callback implementation"""
        # Add pass statement to fix indentation error

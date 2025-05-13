import dearpygui.dearpygui as dpg
from typing import TYPE_CHECKING, Dict, Callable, Optional, Any, Union
import asyncio

if TYPE_CHECKING:
    from core.app import StudyOS  # Changed from relative


class CommandBar:
    def __init__(self, app: "StudyOS"):
        self.app = app  # Store a reference to the main application
        self.input_tag: Optional[Union[int, str]] = None  # Deferred UUID
        # Deferred UUID
        self.status_message_tag: Optional[Union[int, str]] = None
        self._last_status_was_error = False

        self.commands: Dict[str, Callable[..., None]] = {
            "help": self._cmd_help,
            "open notes": lambda: self._cmd_open_module("NotesModule"),
            "open tasks": lambda: self._cmd_open_module("TaskModule"),
            "open flashcards": lambda: self._cmd_open_module("FlashcardModule"),
            "open progress": lambda: self._cmd_open_module("ProgressModule"),
            "open settings": lambda: self._cmd_open_module("SettingsModule"),
            "open statistics": lambda: self._cmd_open_module("StatisticsModule"),
            "theme default light": lambda: self._cmd_apply_theme("Default Light"),
            "theme default dark": lambda: self._cmd_apply_theme("Default Dark"),
            "theme microsoft": lambda: self._cmd_apply_theme("Microsoft Inspired"),
            "theme apple light": lambda: self._cmd_apply_theme("Apple Inspired Light"),
            "theme github dark": lambda: self._cmd_apply_theme("GitHub Inspired Dark"),
            "theme calm green": lambda: self._cmd_apply_theme("Calm Green"),
            # Add more commands here
        }

    def _initialize_dpg_tags(self):
        """Generates DPG tags. Call after DPG context is created."""
        self.input_tag = dpg.generate_uuid()
        self.status_message_tag = dpg.generate_uuid()
        print("[CommandBar._initialize_dpg_tags] DPG tags initialized.")

    def _set_status_message(self, message: str, is_error: bool = False):
        if self.status_message_tag is None or not dpg.does_item_exist(
            self.status_message_tag
        ):
            # print("[CommandBar._set_status_message] Status message tag not ready or item doesn't exist.")
            return
        dpg.set_value(self.status_message_tag, message)
        # Simple color change for error messages
        text_color = (255, 100, 100, 255) if is_error else (180, 180, 180, 255)
        dpg.configure_item(self.status_message_tag, color=text_color)
        self._last_status_was_error = is_error

    def _cmd_help(self):
        available_commands = "\nAvailable commands:\n" + "\n".join(
            [f"- {cmd}" for cmd in self.commands.keys()]
        )
        help_message = f"Type a command and press Enter. {available_commands}"
        self._set_status_message(help_message)

    def _cmd_open_module(self, module_key: str):
        print(f"[CommandBar] Attempting to open module: {module_key}")
        if hasattr(self.app, "switch_module") and callable(self.app.switch_module):
            if module_key in self.app.registered_module_instances:
                # Properly handle async call in sync context
                asyncio.run(self.app.switch_module(module_key))
                self._set_status_message(
                    f"Opened module: {module_key.replace('Module', '')}"
                )
            else:
                self._set_status_message(
                    f"Error: Module '{module_key}' not recognized.", is_error=True
                )
        else:
            self._set_status_message(
                "Error: Cannot switch modules.", is_error=True)

    def _cmd_apply_theme(self, theme_name: str):
        print(f"[CommandBar] Attempting to apply theme: {theme_name}")
        if hasattr(self.app, "core") and hasattr(self.app.core, "theme_manager"):
            theme_manager = self.app.core.theme_manager
            if theme_name in theme_manager.get_theme_names():
                theme_manager.apply_theme(theme_name)
                self._set_status_message(f"Applied theme: {theme_name}")
            else:
                self._set_status_message(
                    f"Error: Theme '{theme_name}' not found.", is_error=True
                )
        else:
            self._set_status_message(
                "Error: Cannot apply theme. Theme manager not available.", is_error=True
            )

    def build_dpg_view(self, parent_tag: str | int):
        """Builds the DPG UI for the command bar and adds it to the parent."""
        if self.input_tag is None or self.status_message_tag is None:
            print(
                "[CommandBar.build_dpg_view] Error: DPG tags not initialized. Call _initialize_dpg_tags first."
            )
            # Optionally, create a placeholder or error message in the UI
            with dpg.group(parent=parent_tag):
                dpg.add_text("Error: CommandBar not initialized.",
                             color=(255, 0, 0))
            return

        with dpg.group(
            parent=parent_tag
        ):  # Ensure this group is under the intended parent
            with dpg.group(horizontal=True, width=-1):
                dpg.add_input_text(
                    tag=self.input_tag,
                    hint="Enter command (e.g., 'help', 'open settings', 'theme calm green')...",
                    width=-1,  # Take available width
                    on_enter=True,
                    callback=self._process_command_input,
                    # user_data can be added if needed by the callback
                )
            dpg.add_text(
                "", tag=self.status_message_tag, color=(180, 180, 180, 255)
            )  # Default subtle color

    def _process_command_input(self, sender: Any, app_data: Any, user_data: Any):
        if self.input_tag is None:
            print("[CommandBar._process_command_input] Error: input_tag is None.")
            return
        command_text = dpg.get_value(self.input_tag).strip().lower()
        print(f"[CommandBar] Processing command: '{command_text}'")

        if not command_text:
            self._set_status_message("")  # Clear status if input is empty
            return

        # Exact match first
        if command_text in self.commands:
            try:
                self.commands[command_text]()
            except Exception as e:
                self._set_status_message(
                    f"Error executing command '{command_text}': {e}", is_error=True
                )
                print(
                    f"[CommandBar] Exception executing command '{command_text}': {e}")
            dpg.set_value(self.input_tag, "")  # Clear input after processing
            return

        # Check for partial matches for theme commands (e.g. "theme calm" -> "theme calm green")
        # This is a simple prefix match, can be expanded
        if command_text.startswith("theme "):
            partial_theme_name = command_text[len("theme "):]
            matched_theme = None
            for full_theme_command in self.commands.keys():
                if (
                    full_theme_command.startswith("theme ")
                    and partial_theme_name in full_theme_command
                ):
                    # A bit simplistic, prefers first partial match.
                    # For "theme dark", it might pick "Default Dark" or "Github Inspired Dark".
                    # For now, we require more specific theme names or exact matches.
                    # To make this more robust, we might need a more sophisticated match or list options.
                    # For now, let's stick to exact command matching primarily.
                    # This logic is tricky; exact match is better for now.
                    pass

        # If no exact match, show an error or 'unknown command'
        self._set_status_message(
            f"Unknown command: '{command_text}'. Type 'help' for options.",
            is_error=True,
        )
        # dpg.set_value(self.input_tag, "") # Don't clear for unknown, let user edit

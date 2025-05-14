import dearpygui.dearpygui as dpg
from typing import TYPE_CHECKING, Optional, Union, List, Tuple

if TYPE_CHECKING:
    from .notes_module import NotesModule # Forward reference for type hinting
    # from core.app import Core # If Core access is needed directly

class NotesDialogManager:
    def __init__(self, notes_module: 'NotesModule'):
        self.nm = notes_module  # Reference to the main notes module
        self.core = notes_module.core
        self.logger = notes_module.logger # Assuming NotesModule has a logger

        # --- Dialog DPG Tags ---
        self.new_folder_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.new_folder_name_input_tag: Union[int, str] = dpg.generate_uuid()
        self.new_folder_icon_input_tag: Union[int, str] = dpg.generate_uuid()

        self.new_note_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.new_note_title_input_tag: Union[int, str] = dpg.generate_uuid()
        self.new_note_icon_input_tag: Union[int, str] = dpg.generate_uuid()
        self.new_note_parent_folder_dropdown_tag: Union[int, str] = dpg.generate_uuid()
        # ... other dialog tags will be added here ...

        # --- Initialize/Define Dialogs ---
        self._define_all_dialogs()

    def _define_all_dialogs(self):
        """Calls individual methods to define each dialog window."""
        self._define_new_folder_dialog()
        self._define_new_note_dialog()
        # ... other dialog definitions will be called here ...

    def _define_new_folder_dialog(self):
        if not dpg.does_item_exist(self.new_folder_dialog_tag):
            with dpg.window(
                label="Create New Folder",
                modal=True,
                show=False,
                tag=self.new_folder_dialog_tag,
                width=350,
                height=150,
                no_resize=True,
            ):
                dpg.add_input_text(
                    tag=self.new_folder_name_input_tag, label="Folder Name", width=-1
                )
                dpg.add_input_text(
                    tag=self.new_folder_icon_input_tag, label="Icon (emoji)", width=-1, hint="e.g., 📁 or ✨"
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Create Folder",
                        callback=self.nm._execute_create_folder, # Call NotesModule's method
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(self.new_folder_dialog_tag, show=False),
                        width=-1,
                    )

    def _define_new_note_dialog(self):
        if not dpg.does_item_exist(self.new_note_dialog_tag):
            with dpg.window(
                label="Create New Note",
                modal=True,
                show=False,
                tag=self.new_note_dialog_tag,
                width=400,
                height=200,
                no_resize=True,
            ):
                dpg.add_input_text(
                    tag=self.new_note_title_input_tag, label="Note Title", width=-1, hint="Enter title for your new note..."
                )
                dpg.add_input_text(
                    tag=self.new_note_icon_input_tag, label="Icon (emoji)", width=-1, hint="e.g., ✨ or 📝"
                )
                dpg.add_text("Parent Folder:")
                dpg.add_combo(
                    tag=self.new_note_parent_folder_dropdown_tag,
                    items=[], # Will be populated by show_new_note_dialog
                    width=-1,
                    default_value="None (Root)"
                )
                dpg.add_spacer(height=5)
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Create Note & Edit",
                        callback=self.nm._execute_create_new_note, # Call NotesModule's method
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(self.new_note_dialog_tag, show=False),
                        width=-1,
                    )

    # --- Methods to show/populate dialogs ---
    def show_new_folder_dialog(self, parent_id: Optional[str]):
        """Sets up and shows the 'New Folder Dialog'."""
        # self.logger.info(f"[NotesDialogManager.show_new_folder_dialog] Parent ID: {parent_id}")
        self.nm.pending_new_folder_parent_id = parent_id # NotesModule still holds this specific state

        if dpg.does_item_exist(self.new_folder_name_input_tag):
            dpg.set_value(self.new_folder_name_input_tag, "")
        if dpg.does_item_exist(self.new_folder_icon_input_tag):
            dpg.set_value(self.new_folder_icon_input_tag, "")

        if dpg.does_item_exist(self.new_folder_dialog_tag):
            dpg.configure_item(self.new_folder_dialog_tag, show=True)
            if dpg.does_item_exist(self.new_folder_name_input_tag):
                dpg.focus_item(self.new_folder_name_input_tag)
        else:
            self.logger.error("[NotesDialogManager.show_new_folder_dialog] New folder dialog tag does not exist!")
            # self.nm._show_error("Cannot open New Folder dialog.") # If NotesModule has a generic error display

class NotesContextMenuManager:
    def __init__(self, notes_module: 'NotesModule'):
        self.nm = notes_module
        self.core = notes_module.core
        self.logger = notes_module.logger

        # --- Context Menu DPG Tags ---
        # self.note_context_menu_tag: Union[int, str] = dpg.generate_uuid()
        # This tag might be better owned by NotesModule if context menu items directly call NotesModule methods

    # --- Methods to handle context menu ---
    # Example:
    # def handle_sidebar_click(self, item_id: str):
    #     # ... logic from _handle_note_sidebar_click ...
    #     pass

    pass

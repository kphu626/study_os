import json
from datetime import datetime  # For Note schema
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import dearpygui.dearpygui as dpg  # Changed from flet
from pydantic import ValidationError  # Added for specific exception handling

from core.decorators import handle_errors
from schemas import Note, NoteCreate  # Import the new schemas

# from core import Core # Removed old import
from .base_module import BaseModule
from .notes_ui_utils import \
    NotesDialogManager  # , NotesContextMenuManager # Import the new manager

if TYPE_CHECKING:  # Added TYPE_CHECKING block
    from core.app import Core  # Import Core from core.app for type hinting


# Dummy data for the tree view - REMOVED
# DUMMY_NOTE_HIERARCHY = { ... }


class NotesModule(BaseModule):  # Renamed from NoteModule
    def __init__(self, core: "Core"):  # Changed to string literal "Core"
        # print("[NotesModule.__init__] Method started.")
        super().__init__(core)
        # self.logger = self.core.logger # REMOVE THIS LINE - logger comes from BaseModule
        # print("[NotesModule.__init__] super().__init__(core) called.")

        # Instantiate UI Managers
        self.dialog_manager = NotesDialogManager(self)
        # self.context_menu_manager = NotesContextMenuManager(self) # For later

        # print("[NotesModule.__init__] Setting up data_path...")
        if (
            hasattr(self.core, "config")
            # Ensure config is not None before accessing attributes
            and self.core.config is not None
            and hasattr(
                self.core.config, "notes_path"
            )  # Directly use notes_path from AppConfig
        ):
            self.data_path = self.core.config.notes_path
            # print(f"[NotesModule.__init__] data_path set from core.config: {self.data_path}") # ADDED
        else:
            # Fallback, ensure AppConfig default is used if core.config was missing
            # This case should ideally not happen if Core initializes AppConfig correctly
            from core.config import \
                AppConfig as DefaultAppConfig  # Temporary import

            self.data_path = DefaultAppConfig().notes_path
            # print(f"[NotesModule.__init__] WARNING: data_path set from DefaultAppConfig: {self.data_path}") # ADDED
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
        # print(f"[NotesModule.__init__] Data directory ensured: {self.data_path.parent}") # ADDED

        self.notes: List[Note] = []  # To store loaded Note objects
        # print("[NotesModule.__init__] self.notes initialized.") # ADDED
        # To track for updates
        self.current_editing_note_id: Optional[str] = None
        # print("[NotesModule.__init__] self.current_editing_note_id initialized.") # ADDED

        # DPG tags will be generated in build_dpg_view. Initialize to a type DPG expects for tags (int or str).
        # Using a placeholder value like 0, as they will be overwritten.
        self.dpg_notes_list_container_tag: Union[int, str] = 0
        self.dpg_title_field_tag: Union[int, str] = 0
        self.dpg_content_field_tag: Union[int, str] = 0
        self.dpg_preview_area_tag: Union[int, str] = 0
        self.dpg_status_text_tag: Union[int, str] = dpg.generate_uuid()
        # print("[NotesModule.__init__] DPG tags initialized with placeholders.")
        # print("[NotesModule.__init__] Method finished.")

        # Tag for the area in the main tab where note content is displayed
        self.note_content_display_area_tag: Union[int, str] = dpg.generate_uuid()
        # Tags for the edit controls (these are part of the main display, not the editor window)
        self.note_content_input_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # This was for inline editing
        self.edit_button_tag: Union[int, str] = dpg.generate_uuid()
        self.save_button_tag: Union[int, str] = dpg.generate_uuid()
        self.cancel_button_tag: Union[int, str] = dpg.generate_uuid()

        # Tags for tag editing UI
        self.note_tags_display_group_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # Group to display current tags
        self.new_tag_input_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # Input for new tag
        self.add_tag_button_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # Button to add the new tag

        # Tags for tag filtering UI
        self.tag_filter_list_container_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # Container for filter tags
        self.sidebar_notes_list_actual_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # Actual list of notes in sidebar
        self.active_tag_filter: Optional[str] = None

        # State for current note being displayed/edited
        self.currently_selected_note_id: Optional[str] = None

        # Add view mode state
        self.card_view = True
        self.SYSTEM_SPECIFIC_LSHIFT_CODE = 528  # From core/app.py

        # Initialize editor window item tags
        self.editor_title: Optional[Union[int, str]] = None
        self.editor_content: Optional[Union[int, str]] = None

        # Define the editor window here so it exists when the module is created
        if not dpg.does_item_exist(
            "editor_window"
        ):  # Ensure it's only defined once globally if multiple notes modules were possible
            with dpg.window(
                tag="editor_window",
                label="Note Editor",
                width=600,
                height=400,
                show=False,  # Initially hidden
                on_close=self._close_editor,  # Assuming _close_editor is defined
            ):
                self.editor_title = dpg.add_input_text(label="Title")
                self.editor_content = dpg.add_input_text(
                    label="Content", multiline=True, height=-40, tab_input=True
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Save", callback=self._save_note
                    )  # Assuming _save_note is defined
                    dpg.add_button(label="Cancel", callback=self._close_editor)

        # Initial load and display of notes
        self.load_data()  # Call load_data which will call _dpg_display_notes_list

        # For context menu
        self.note_context_menu_tag: Union[int, str] = dpg.generate_uuid()
        self.context_menu_active_note_id: Optional[str] = (
            None  # Store ID for context actions
        )
        self.rename_note_window_tag: Union[int, str] = dpg.generate_uuid()
        self.rename_note_input_tag: Union[int, str] = dpg.generate_uuid()

        # --- Delete Note Confirmation Dialog Items ---
        self._setup_delete_confirmation_dialog_tags()

        # --- New Folder Dialog Items --- (MOVED TO NotesDialogManager)
        # self.new_folder_dialog_tag: Union[int, str] = dpg.generate_uuid()
        # self.new_folder_name_input_tag: Union[int, str] = dpg.generate_uuid()
        # self.new_folder_icon_input_tag: Union[int, str] = dpg.generate_uuid() # For the new icon input

        self.pending_new_folder_parent_id: Optional[str] = (
            None  # State remains in NotesModule for now
        )
        self.pending_new_note_parent_id: Optional[str] = (
            None  # State remains in NotesModule for now
        )

        # --- Constants for Icons and Special Values ---
        self.ICON_FOLDER_DEFAULT = "📁"
        self.ICON_NOTE_DEFAULT = "📄"
        self.ICON_ROOT = "🌳"  # Icon for root in dropdowns
        self.ROOT_SENTINEL_VALUE = "__MOVE_TO_ROOT__"  # Sentinel for moving to root

        # Definition of New Folder Dialog MOVED to NotesDialogManager
        # if not dpg.does_item_exist(self.new_folder_dialog_tag):
        #     with dpg.window(
        #         label="Create New Folder",
        #         modal=True,
        #         show=False,
        #         tag=self.new_folder_dialog_tag,
        #         width=350, # Slightly wider for icon
        #         height=150, # Slightly taller for icon
        #         no_resize=True,
        #     ):
        #         dpg.add_input_text(
        #             tag=self.new_folder_name_input_tag, label="Folder Name", width=-1
        #         )
        #         dpg.add_input_text(
        #             tag=self.new_folder_icon_input_tag, label="Icon (emoji)", width=-1, hint="e.g., 📁 or ✨"
        #         ) # New input for icon
        #         with dpg.group(horizontal=True):
        #             dpg.add_button(
        #                 label="Create Folder",
        #                 callback=self._execute_create_folder,
        #                 width=-1,
        #             )
        #             dpg.add_button(
        #                 label="Cancel",
        #                 callback=lambda: dpg.configure_item(self.new_folder_dialog_tag, show=False),
        #                 width=-1,
        #             )

        # --- New Note Dialog Items --- (MOVED TO NotesDialogManager)
        # self.new_note_dialog_tag: Union[int, str] = dpg.generate_uuid()
        # self.new_note_title_input_tag: Union[int, str] = dpg.generate_uuid()
        # self.new_note_icon_input_tag: Union[int, str] = dpg.generate_uuid()
        # self.new_note_parent_folder_dropdown_tag: Union[int, str] = dpg.generate_uuid()

        # To store (label, id) for dropdown: List[Tuple[str, Optional[str]]]
        # This state is still managed by NotesModule as it's dynamically populated based on self.notes
        self.available_folders_for_new_note_dropdown: List[
            Tuple[str, Optional[str]]
        ] = []

        # Definition of New Note Dialog MOVED to NotesDialogManager
        # if not dpg.does_item_exist(self.new_note_dialog_tag):
        #     with dpg.window(
        #         label="Create New Note",
        #         modal=True,
        #         show=False,
        #         tag=self.new_note_dialog_tag,
        #         width=400,
        #         height=200,
        #         no_resize=True,
        #     ):
        #         dpg.add_input_text(
        #             tag=self.new_note_title_input_tag, label="Note Title", width=-1, hint="Enter title for your new note..."
        #         )
        #         dpg.add_input_text(
        #             tag=self.new_note_icon_input_tag, label="Icon (emoji)", width=-1, hint="e.g., ✨ or 📝"
        #         )
        #         dpg.add_text("Parent Folder:")
        #         dpg.add_combo(
        #             tag=self.new_note_parent_folder_dropdown_tag,
        #             items=[], # Will be populated dynamically
        #             width=-1,
        #             default_value="None (Root)" # Default selection label
        #         )
        #         dpg.add_spacer(height=5)
        #         with dpg.group(horizontal=True):
        #             dpg.add_button(
        #                 label="Create Note & Edit",
        #                 callback=self._execute_create_new_note, # New callback to be created
        #                 width=-1,
        #             )
        #             dpg.add_button(
        #                 label="Cancel",
        #                 callback=lambda: dpg.configure_item(self.new_note_dialog_tag, show=False),
        #                 width=-1,
        #             )

        # --- Move Item Dialog Items ---
        self.move_item_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.move_item_label_tag: Union[int, str] = (
            dpg.generate_uuid()
        )  # To display which item is being moved
        self.move_item_destination_folder_dropdown_tag: Union[int, str] = (
            dpg.generate_uuid()
        )
        self.item_to_move_id: Optional[str] = (
            None  # Store the ID of the item being moved
        )
        # To store (label, id) for dropdown: List[Tuple[str, Optional[str]]]
        self.available_folders_for_move_dropdown: List[Tuple[str, Optional[str]]] = []

        if not dpg.does_item_exist(self.move_item_dialog_tag):
            with dpg.window(
                label="Move Item To...",
                modal=True,
                show=False,
                tag=self.move_item_dialog_tag,
                width=400,
                height=180,  # Adjusted height
                no_resize=True,
            ):
                dpg.add_text(
                    "Moving item: ", tag=self.move_item_label_tag
                )  # Will be updated with item name
                dpg.add_spacer(height=5)
                dpg.add_text("Select Destination Folder:")
                dpg.add_combo(
                    tag=self.move_item_destination_folder_dropdown_tag,
                    items=[],  # Will be populated dynamically
                    width=-1,
                    default_value="None (Root)",
                )
                dpg.add_spacer(height=10)
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Move Item",
                        callback=self._execute_move_item,  # New callback
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(
                            self.move_item_dialog_tag, show=False
                        ),
                        width=-1,
                    )

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the main display area for the Notes tab."""
        print(
            f"[NotesModule.build_dpg_view] Attempting to build in parent: {parent_container_tag} (type: {type(parent_container_tag)})"
        )

        if not dpg.does_item_exist(parent_container_tag):
            print(
                f"[NotesModule.build_dpg_view] Error: Parent container {parent_container_tag} does not exist!"
            )
            # Cannot build the view if the parent isn't there
            return

        # Ensure the target tag doesn't already exist (e.g., from a previous failed build)
        if dpg.does_item_exist(self.note_content_display_area_tag):
            print(
                f"[NotesModule.build_dpg_view] Warning: Content display tag {self.note_content_display_area_tag} already exists. Deleting children."
            )
            dpg.delete_item(self.note_content_display_area_tag, children_only=True)
        else:
            # Create the main group for note content display
            dpg.add_group(
                tag=self.note_content_display_area_tag, parent=parent_container_tag
            )
            print(
                f"[NotesModule.build_dpg_view] Created content display group {self.note_content_display_area_tag} in parent {parent_container_tag}"
            )

        # Add initial placeholder text inside the (now guaranteed) existing group
        dpg.add_text(
            "Select a note from the sidebar to view its content.",
            parent=self.note_content_display_area_tag,
        )

        # REMOVED OLD UI elements that were previously built here:
        # - dpg_notes_list_container_tag generation and usage
        # - dpg_title_field_tag, dpg_content_field_tag, dpg_preview_area_tag generation
        # - Status text setup (consider if needed elsewhere)
        # - Card view controls (New Note button moved to sidebar)
        # - Card View Container

        # The editor window is now defined in __init__
        # if not dpg.does_item_exist("editor_window"): # Ensure it's only defined once
        #     with dpg.window(
        #         tag="editor_window",
        #         label="Note Editor",
        #         width=600,
        #         height=400,
        #         show=False,
        #         on_close=self._close_editor,
        #     ):
        #         self.editor_title = dpg.add_input_text(label="Title")
        #         self.editor_content = dpg.add_input_text(
        #             label="Content",  # Added label
        #             multiline=True,
        #             height=-40,  # Adjusted height to leave space for buttons
        #             tab_input=True
        #         )
        #         with dpg.group(horizontal=True): # Group for buttons
        #             dpg.add_button(label="Save", callback=self._save_note)
        #             dpg.add_button(label="Cancel", callback=self._close_editor) # Added Cancel button

    def _dpg_display_notes_list(self):
        if not dpg.does_item_exist(self.dpg_notes_list_container_tag):
            return

        # Clear existing notes from the list UI
        dpg.delete_item(self.dpg_notes_list_container_tag, children_only=True)

        # Re-add static elements if necessary (or design so they are not deleted)
        dpg.add_text("Notes", parent=self.dpg_notes_list_container_tag)
        dpg.add_separator(parent=self.dpg_notes_list_container_tag)

        if not self.notes:
            dpg.add_text("No notes found.", parent=self.dpg_notes_list_container_tag)
        else:
            for note in self.notes:
                # Use a unique tag for each button if needed, or rely on user_data
                dpg.add_button(
                    label=note.title if note.title else "Untitled",
                    user_data=note.id,
                    callback=self._OBSOLETE_dpg_load_note_for_editing_callback,
                    width=-1,
                    parent=self.dpg_notes_list_container_tag,
                )
        dpg.set_value(self.dpg_status_text_tag, f"Loaded {len(self.notes)} notes.")

    def _OBSOLETE_dpg_load_note_for_editing_callback(self, sender, app_data, user_data):
        print("[_OBSOLETE_dpg_load_note_for_editing_callback] Called - OBSOLETE.")

    def _OBSOLETE_dpg_clear_editor_callback(self, sender, app_data, user_data):
        print("[_OBSOLETE_dpg_clear_editor_callback] Called - OBSOLETE.")

    def _OBSOLETE_dpg_update_preview_callback(self, sender, app_data, user_data):
        print("[_OBSOLETE_dpg_update_preview_callback] Called - OBSOLETE.")
        pass

    def _OBSOLETE_dpg_save_note_callback(self, sender, app_data, user_data):
        print("[_OBSOLETE_dpg_save_note_callback] Called - OBSOLETE.")

    def load_data(self):
        self.notes.clear()
        if self.data_path.exists() and self.data_path.stat().st_size > 0:
            try:
                raw_notes_data = json.loads(self.data_path.read_text(encoding="utf-8"))
                if isinstance(raw_notes_data, list):
                    for note_data in raw_notes_data:
                        try:
                            self.notes.append(Note(**note_data))
                        except ValidationError as e:
                            print(
                                f"[NotesModule.load_data] Skipping invalid note data: {note_data}. Error: {e.errors()}"
                            )
                        except Exception as ex:
                            print(
                                f"[NotesModule.load_data] Unexpected error processing note data: {note_data}. Error: {ex}"
                            )
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {self.data_path}. No notes loaded.")
                if dpg.is_dearpygui_running() and dpg.does_item_exist(
                    self.dpg_status_text_tag
                ):  # Check if UI exists
                    dpg.set_value(
                        self.dpg_status_text_tag,
                        "Error loading notes: Invalid data file.",
                    )
            except Exception as e:
                self._show_error(f"Load error: {str(e)}")

        # Ensure the DPG view is ready before trying to update it
        if dpg.is_dearpygui_running() and dpg.does_item_exist(
            self.dpg_notes_list_container_tag
        ):
            self._dpg_display_notes_list()
        elif not dpg.is_dearpygui_running():
            pass
        else:
            print("NotesModule.load_data: DPG list container not ready yet.")

    def handle_keyboard(self, key_code: int):
        # Ctrl+S = 564 (empirical code)
        if key_code == 564 and dpg.is_key_down(self.SYSTEM_SPECIFIC_LSHIFT_CODE):
            self._OBSOLETE_dpg_save_note_callback(None, None, None)

    def get_focusable_items(self):
        if dpg.does_item_exist("editor_window") and dpg.is_item_shown("editor_window"):
            return [self.editor_title, self.editor_content]
        elif dpg.does_item_exist(
            self.dialog_manager.new_note_dialog_tag
        ) and dpg.is_item_shown(self.dialog_manager.new_note_dialog_tag):
            # This part will also need to use self.dialog_manager once New Note Dialog is moved
            return [
                self.new_note_title_input_tag,
                self.new_note_icon_input_tag,
                self.new_note_parent_folder_dropdown_tag,
            ]
        elif dpg.does_item_exist(
            self.dialog_manager.new_folder_dialog_tag
        ) and dpg.is_item_shown(self.dialog_manager.new_folder_dialog_tag):
            return [
                self.dialog_manager.new_folder_name_input_tag,
                self.dialog_manager.new_folder_icon_input_tag,
            ]
        elif dpg.does_item_exist(
            self.dialog_manager.delete_confirm_dialog_tag
        ) and dpg.is_item_shown(self.dialog_manager.delete_confirm_dialog_tag):
            # This part will use self.dialog_manager once Delete Confirm Dialog is moved
            pass
        elif dpg.does_item_exist(
            self.dialog_manager.rename_note_window_tag
        ) and dpg.is_item_shown(self.dialog_manager.rename_note_window_tag):
            # This part will use self.dialog_manager once Rename Dialog is moved
            return [self.rename_note_input_tag]
        return []

    def _create_new_note(self, sender, app_data):
        self.logger.info("[_create_new_note] Request to open 'New Note Dialog'.")

        # Ensure dialog manager and its tags are initialized
        if (
            not hasattr(self.dialog_manager, "new_note_dialog_tag")
            or not hasattr(self.dialog_manager, "new_note_title_input_tag")
            or not hasattr(self.dialog_manager, "new_note_icon_input_tag")
            or not hasattr(self.dialog_manager, "new_note_parent_folder_dropdown_tag")
        ):
            self.logger.error(
                "NotesDialogManager is not fully initialized with required DPG tags for new_note_dialog."
            )
            # Attempt to define/re-define the dialog if missing critical tags.
            # This suggests an initialization order issue or incomplete setup in NotesDialogManager.
            if hasattr(self.dialog_manager, "define_new_note_dialog"):
                self.logger.info(
                    "Attempting to define new_note_dialog via NotesDialogManager."
                )
                self.dialog_manager.define_new_note_dialog()  # Ensure it exists
            else:
                self.logger.error(
                    "NotesDialogManager does not have define_new_note_dialog method."
                )
                return

        # Populate the folder dropdown using the dialog manager's tag
        self._populate_folder_dropdown_for_new_note_dialog()

        # Configure and show the dialog using tags from the dialog_manager
        try:
            if dpg.does_item_exist(self.dialog_manager.new_note_dialog_tag):
                dpg.set_value(
                    self.dialog_manager.new_note_title_input_tag, "New Note Title"
                )
                dpg.set_value(
                    self.dialog_manager.new_note_icon_input_tag, self.ICON_NOTE_DEFAULT
                )  # Use default icon
                # The dropdown is populated by _populate_folder_dropdown_for_new_note_dialog

                # Call the dialog manager to center and show the dialog
                self.dialog_manager.show_and_center_new_note_dialog()
                # self.logger.info(f"Showing new note dialog: {self.dialog_manager.new_note_dialog_tag}") # Logging now in manager
            else:
                self.logger.error(
                    f"New note dialog (tag: {self.dialog_manager.new_note_dialog_tag}) does not exist even after attempting re-definition."
                )
        except Exception as e:
            self.logger.error(f"Error configuring or showing new note dialog: {e}")

    def _toggle_view_mode(self, sender):
        self.card_view = not self.card_view
        dpg.configure_item(
            "card_container",
            horizontal=self.card_view,
            wrap=300 if self.card_view else 0,
        )
        dpg.set_item_label(
            sender, "Switch to List View" if self.card_view else "Switch to Card View"
        )
        self._update_note_display()

    def _update_note_display(self):
        dpg.delete_item("card_container", children_only=True)

        if self.card_view:
            # Card View
            for note in self.notes:
                with dpg.child_window(
                    parent="card_container", width=280, height=120, border=True
                ) as card:
                    with dpg.group():
                        dpg.add_text(note.title[:20], bullet=True)
                        dpg.add_text(note.content[:60] + "...", color=(150, 150, 150))
                        dpg.add_separator()
                        with dpg.group(horizontal=True):
                            dpg.add_button(
                                label="Edit",
                                callback=lambda s, a, n=note: self._open_editor(n),
                            )
                            dpg.add_button(
                                label="Delete",
                                callback=lambda s, a, n=note: self._delete_note(n.id),
                            )

        else:
            # List View
            for note in self.notes:
                with dpg.group(parent="card_container"):
                    dpg.add_text(note.title, bullet=True)
                    dpg.add_button(
                        label="Open", callback=lambda s, a, n=note: self._open_editor(n)
                    )

    def _open_editor(self, note):
        print(f"Opening editor for note: {note.title if note else 'New Note'}")
        if self.editor_title is not None and self.editor_content is not None:
            dpg.set_value(self.editor_title, note.title if note else "")
            dpg.set_value(self.editor_content, note.content if note else "")
            dpg.show_item("editor_window")
            self.current_editing_note_id = note.id if note else None
        else:
            print("Error: Editor title or content tags not initialized.")

    def _close_editor(self, sender, app_data):
        # Implement the logic to close the editor
        if dpg.does_item_exist("editor_window"):
            dpg.configure_item("editor_window", show=False)
        # Optionally, clear/reset editor fields here if needed
        # dpg.set_value(self.editor_title, "")
        # dpg.set_value(self.editor_content, "")

    def _save_note(self, sender, app_data):
        note_title = ""
        note_content = ""
        if self.editor_title is not None:
            note_title = dpg.get_value(self.editor_title)
        if self.editor_content is not None:
            note_content = dpg.get_value(self.editor_content)

        self.logger.info(
            f"[_save_note] Attempting to save. Title: '{note_title}', Current Editing ID: {self.current_editing_note_id}"
        )

        if self.current_editing_note_id:
            # Find and update existing note
            existing_note = next(
                (n for n in self.notes if n.id == self.current_editing_note_id), None
            )
            if existing_note:
                if (
                    not note_title.strip()
                ):  # Check if title becomes empty for an existing note
                    self.logger.warning(
                        f"[_save_note] Title for existing note ID {existing_note.id} cannot be empty. Save aborted."
                    )
                    self._show_error(
                        "Note title cannot be empty."
                    )  # Use existing error display
                    # Optionally, could revert the dpg.get_value(self.editor_title) to existing_note.title
                    # or simply not proceed with the update of the title field if it's crucial it never gets blanked.
                    # For now, just preventing the save of the blank title.
                    return
                existing_note.title = note_title
                existing_note.content = note_content
                existing_note.updated_at = datetime.utcnow()
                self.logger.info(
                    f"[_save_note] Updated existing note: {existing_note.id}"
                )
            else:
                self.logger.error(
                    f"[_save_note] Error: Could not find note with ID {self.current_editing_note_id} to update."
                )
                self._show_error(
                    f"Error: Note {self.current_editing_note_id} not found for update."
                )
                return  # Don't proceed if note to update isn't found
        else:
            # Create new note object
            if not note_title.strip():
                self.logger.warning(
                    "[_save_note] Title for new note cannot be empty. Save aborted."
                )
                self._show_error("Note title cannot be empty.")
                self.pending_new_note_parent_id = None  # Reset on abort
                return
            try:
                parent_for_new_note = self.pending_new_note_parent_id
                new_note_schema = NoteCreate(
                    title=note_title,
                    content=note_content,
                    parent_id=parent_for_new_note,
                )
                new_note = Note(**new_note_schema.model_dump())
                self.notes.append(new_note)
                self.logger.info(
                    f"[_save_note] Created new note: {new_note.id} with parent_id: {parent_for_new_note}"
                )
            except ValidationError as e:
                self.logger.error(
                    f"[_save_note] Pydantic validation error for new note: {e}"
                )
                self._show_error(
                    f"Validation Error: {e.errors()[0]['msg'] if e.errors() else 'Invalid data'}"
                )
                self.pending_new_note_parent_id = None  # Reset on error
                return

        self.logger.debug(
            f"[_save_note] About to save. self.notes contains: {[n.title for n in self.notes]}"
        )
        self.logger.debug(
            f"[_save_note] Note being processed: Title='{note_title}', ID='{self.current_editing_note_id}'"
        )
        self._save_notes()  # Save all notes to file
        self._refresh_sidebar_note_list()  # Refresh the sidebar

        if dpg.does_item_exist("editor_window"):
            dpg.hide_item("editor_window")
        self.pending_new_note_parent_id = (
            None  # Reset after successful save or if editor closed
        )
        self.current_editing_note_id = None

    @handle_errors
    def _delete_note(self, note_id: str):
        try:
            self.notes = [n for n in self.notes if n.id != note_id]
            self._save_notes()
            self._refresh_sidebar_note_list()
            # If the deleted note was the one being viewed, clear the main content area
            if self.currently_selected_note_id == note_id:
                self.currently_selected_note_id = None
                if dpg.does_item_exist(self.note_content_display_area_tag):
                    dpg.delete_item(
                        self.note_content_display_area_tag, children_only=True
                    )
                    dpg.add_text(
                        "Select a note from the sidebar to view its content.",
                        parent=self.note_content_display_area_tag,
                    )

        except Exception as e:
            self._show_error(f"Delete failed: {str(e)}")

    def _show_error(self, message: str):
        dpg.set_value(self.dpg_status_text_tag, message)
        dpg.configure_item(self.dpg_status_text_tag, color=(255, 0, 0))

    def _save_notes(self):
        # Use model_dump(mode='json') for Pydantic V2 to ensure datetimes are serialized to ISO strings
        notes_data = [note.model_dump(mode="json") for note in self.notes]
        # The result of model_dump(mode='json') is already a JSON-friendly dict/list structure,
        # so json.dumps will handle it correctly.
        self.data_path.write_text(json.dumps(notes_data, indent=2))
        # After saving notes, if tag filtering is active, the unique tags might have changed.
        if dpg.is_dearpygui_running() and dpg.does_item_exist(
            self.tag_filter_list_container_tag
        ):
            self._refresh_tag_filter_list()  # New method to update the filter UI

    def build_sidebar_view(self, sidebar_parent_tag: str):
        """Builds the note list/tree view and tag filter within the specified sidebar parent."""
        print(
            f"[NotesModule.build_sidebar_view] Building sidebar in parent: {sidebar_parent_tag}"
        )

        with dpg.child_window(
            parent=sidebar_parent_tag, border=False, width=-1, height=-1
        ):
            dpg.add_button(
                label="(+) New Note", width=-1, callback=self._create_new_note
            )
            dpg.add_separator()
            dpg.add_text("Filter by Tag:")
            with dpg.group(tag=self.tag_filter_list_container_tag, horizontal=False):
                pass  # This will be populated by _refresh_tag_filter_list
            dpg.add_separator()
            dpg.add_spacer(height=5)
            dpg.add_text("Notes:")
            # Container for the actual list of notes, to be populated by _refresh_sidebar_note_list
            with dpg.group(tag=self.sidebar_notes_list_actual_tag):
                dpg.add_text("--- Notes List Container Start ---", color=(255,0,0)) # DEBUG Line
                pass  # This will be populated by _refresh_sidebar_note_list

        # Initial population
        self._refresh_tag_filter_list()
        self._refresh_sidebar_note_list()

    def _get_all_unique_tags(self) -> List[str]:
        all_tags = set()
        for note in self.notes:
            if note.tags:
                for tag in note.tags:
                    all_tags.add(tag)
        # Case-insensitive sort
        return sorted(list(all_tags), key=lambda x: x.lower())

    def _refresh_tag_filter_list(self):
        if not dpg.does_item_exist(self.tag_filter_list_container_tag):
            return
        dpg.delete_item(self.tag_filter_list_container_tag, children_only=True)
        unique_tags = self._get_all_unique_tags()

        # "All Notes" selectable
        all_notes_label = "- All Notes -"
        is_all_notes_active = self.active_tag_filter is None
        with dpg.group(parent=self.tag_filter_list_container_tag):
            all_notes_selectable = dpg.add_selectable(
                label=all_notes_label,
                user_data=None,
                callback=self._on_filter_tag_selected,
                span_columns=True,
            )
            if is_all_notes_active:
                # Crude way to show selection: add a simple marker.
                # A theme or specific styling would be better long-term.
                dpg.set_item_label(all_notes_selectable, f"> {all_notes_label}")

        for tag in unique_tags:
            is_tag_active = self.active_tag_filter == tag
            with dpg.group(parent=self.tag_filter_list_container_tag):
                tag_selectable = dpg.add_selectable(
                    label=tag,
                    user_data=tag,
                    callback=self._on_filter_tag_selected,
                    span_columns=True,
                )
                if is_tag_active:
                    dpg.set_item_label(tag_selectable, f"> {tag}")

    def _on_filter_tag_selected(self, sender, app_data, user_data):
        selected_tag = user_data
        # No change if the active item is re-selected via its direct selectable call
        # (since the label change indicates selection already)
        # However, if a *different* item is selected, or if logic changes state, then update.

        if self.active_tag_filter == selected_tag:
            # If clicking the currently active tag, or if "All Notes" is clicked when it's effectively active
            # This effectively deselects it, making "All Notes" active implicitly
            self.active_tag_filter = None
        else:
            self.active_tag_filter = selected_tag

        print(
            f"[NotesModule._on_filter_tag_selected] Active filter: {self.active_tag_filter}"
        )
        self._refresh_sidebar_note_list()
        self._refresh_tag_filter_list()  # Re-render to update selection states

    def _build_sidebar_tree_recursive(
        self,
        parent_dpg_tag: Union[int, str],
        current_parent_id: Optional[str],
        notes_by_parent: Dict[Optional[str], List[Note]],
    ):
        self.logger.debug(f"[_build_sidebar_tree_recursive] Called for parent_id: {current_parent_id}, DPG parent: {parent_dpg_tag}")
        children = notes_by_parent.get(current_parent_id, [])
        self.logger.debug(f"[_build_sidebar_tree_recursive] Children found: {[c.title for c in children]}")

        sorted_children = sorted(
            children,
            key=lambda x: (not x.is_folder, x.order, x.title.lower())
        )
        self.logger.debug(f"[_build_sidebar_tree_recursive] Sorted children: {[c.title for c in sorted_children]}")

        if not sorted_children and current_parent_id is not None:
            pass

        for item in sorted_children:
            self.logger.debug(f"Attempting to render item: {item.title} (ID: {item.id}) in DPG parent {parent_dpg_tag}")
            # SIMPLIFIED RENDERING FOR DEBUGGING:
            dpg.add_text(f"[SIMPLE] {item.title}", parent=parent_dpg_tag, color=(100, 255, 100))

            # ORIGINAL TREE NODE LOGIC (COMMENTED OUT FOR NOW):
            # default_folder_icon = "📁"
            # default_note_icon = "📄"
            # icon_to_use = item.icon if item.icon and item.icon.strip() else (default_folder_icon if item.is_folder else default_note_icon)
            # item_label = f"{icon_to_use} {item.title}"
            # dpg_item_tag = f"sidebar_item_{item.id}"

            # if item.is_folder:
            #     with dpg.tree_node(label=item_label, tag=dpg_item_tag, parent=parent_dpg_tag, user_data=item.id, default_open=False, selectable=True) as folder_node_tag:
            #         with dpg.item_handler_registry(tag=f"handler_for_folder_{item.id}") as handler_reg_tag:
            #             dpg.add_item_clicked_handler(
            #                 button=dpg.mvMouseButton_Left,
            #                 callback=self._on_note_selected_from_tree,
            #                 user_data=item.id
            #             )
            #             dpg.add_item_clicked_handler(
            #                 button=dpg.mvMouseButton_Right,
            #                 callback=self._handle_note_sidebar_click,
            #                 user_data=item.id
            #             )
            #         dpg.bind_item_handler_registry(folder_node_tag, handler_reg_tag)
            #         self._build_sidebar_tree_recursive(folder_node_tag, item.id, notes_by_parent)
            # else: # It's a note
            #     note_node_tag = dpg.add_tree_node(label=item_label, tag=dpg_item_tag, parent=parent_dpg_tag, user_data=item.id, leaf=True, selectable=True)
            #     with dpg.item_handler_registry(tag=f"handler_for_note_{item.id}") as handler_reg_tag:
            #         dpg.add_item_clicked_handler(
            #             button=dpg.mvMouseButton_Left,
            #             callback=self._on_note_selected_from_tree,
            #             user_data=item.id
            #         )
            #         dpg.add_item_clicked_handler(
            #             button=dpg.mvMouseButton_Right,
            #             callback=self._handle_note_sidebar_click,
            #             user_data=item.id
            #         )
            #     dpg.bind_item_handler_registry(note_node_tag, handler_reg_tag)

    def _refresh_sidebar_note_list(self):
        self.logger.debug(
            f"[_refresh_sidebar_note_list] Refreshing. self.notes contains: {[n.title for n in self.notes]}"
        )
        self.logger.debug(
            f"[_refresh_sidebar_note_list] Active filter: {self.active_tag_filter}"
        )
        # self.logger.debug("[_refresh_sidebar_note_list] Refreshing sidebar note list (hierarchical).")
        if not hasattr(
            self, "sidebar_notes_list_actual_tag"
        ) or not dpg.does_item_exist(self.sidebar_notes_list_actual_tag):
            self.logger.error(
                "[_refresh_sidebar_note_list] Sidebar notes list container does not exist."
            )
        return

        dpg.delete_item(self.sidebar_notes_list_actual_tag, children_only=True)

        # Apply tag filtering first
        current_notes_to_display = self.notes
        if self.active_tag_filter:
            # For hierarchical view, tag filtering needs careful consideration.
            # Option 1: Show only notes with the tag, and their parent folders (even if parents don't have the tag).
            # Option 2: Show only notes AND folders that have the tag.
            # For simplicity, let's try Option 1: Show tagged notes and their ancestors.
            # This is complex. A simpler initial filter: show all notes if a tag is active,
            # and highlight or visually indicate those with the tag.
            # Or, more simply for now: only filter leaf notes.

            # Simplistic filter for now: only notes (not folders) are directly filtered by tag.
            # Folders will appear if they contain (eventually) a matched note.
            # This requires adjusting the recursive build to check if any descendant has the tag.

            # Current simple approach: filter the flat list of notes first, then build hierarchy of those.
            # This means empty folders (after filtering) won't show.
            notes_with_tag = {
                note.id
                for note in self.notes
                if note.tags
                and self.active_tag_filter in note.tags
                and not note.is_folder
            }

            # Include all folders, and notes that match the tag.
            # To show parent folders of tagged notes:
            # 1. Get all notes that match the tag.
            # 2. For each matched note, find all its ancestors and add them to a set of items to display.
            # 3. Add all folders to this set as well, so they can be containers.

            items_to_render_ids = set()
            if self.active_tag_filter:
                notes_map = {note.id: note for note in self.notes}
                for note in self.notes:
                    if (
                        not note.is_folder
                        and note.tags
                        and self.active_tag_filter in note.tags
                    ):
                        items_to_render_ids.add(note.id)
                        # Add all ancestors
                        curr_parent_id = note.parent_id
                        while curr_parent_id and curr_parent_id in notes_map:
                            items_to_render_ids.add(curr_parent_id)
                            curr_parent_id = notes_map[curr_parent_id].parent_id
                # Also include all folders so they can be rendered if they contain a tagged note
                for note in self.notes:
                    if note.is_folder:
                        items_to_render_ids.add(
                            note.id
                        )  # We'll let the recursive build hide empty ones
                current_notes_to_display = [
                    note for note in self.notes if note.id in items_to_render_ids
                ]
            else:
                current_notes_to_display = self.notes

        self.logger.debug(
            f"[_refresh_sidebar_note_list] current_notes_to_display (after filter): {[n.title for n in current_notes_to_display]}"
        )

        if not current_notes_to_display:
            dpg.add_text(
                "No notes or folders found.", parent=self.sidebar_notes_list_actual_tag
            )
            # self.logger.debug("[_refresh_sidebar_note_list] No items to display after potential filtering.")
            return

        # Build a dictionary of notes/folders by their parent_id
        notes_by_parent: Dict[Optional[str], List[Note]] = {}
        for note_item in current_notes_to_display:
            parent_id = note_item.parent_id
            if parent_id not in notes_by_parent:
                notes_by_parent[parent_id] = []
            notes_by_parent[parent_id].append(note_item)

        self.logger.debug(f"[_refresh_sidebar_note_list] notes_by_parent structure: { {k: [n.title for n in v] for k,v in notes_by_parent.items()} }")
        self.logger.debug(f"[_refresh_sidebar_note_list] About to call _build_sidebar_tree_recursive with parent_dpg_tag: {self.sidebar_notes_list_actual_tag}")
        self._build_sidebar_tree_recursive(self.sidebar_notes_list_actual_tag, None, notes_by_parent)
        self.logger.debug(f"[_refresh_sidebar_note_list] Returned from _build_sidebar_tree_recursive")

        # dpg.get_item_children returns a dict: {slot: [child_ids]}
        children_dict = dpg.get_item_children(self.sidebar_notes_list_actual_tag)
        slot_1_children = children_dict.get(1, []) # Get children in slot 1

        if not slot_1_children and not current_notes_to_display:
             dpg.add_text("[Debug] No notes or folders exist at all.", parent=self.sidebar_notes_list_actual_tag, color=(200,200,200))
        elif not slot_1_children and current_notes_to_display:
             dpg.add_text("[Debug] Notes exist but failed to render in sidebar.", parent=self.sidebar_notes_list_actual_tag, color=(255,100,100))
        elif slot_1_children and not current_notes_to_display:
             # This case should ideally not happen if logic is correct (rendered items but no data to display)
             dpg.add_text("[Debug] Anomaly: Sidebar has items but no data source?", parent=self.sidebar_notes_list_actual_tag, color=(255,0,255))

    def _on_note_selected_from_tree(self, sender, app_data, user_data):
        """Callback when a note is selected in the sidebar list."""
        selected_note_id = user_data
        self.currently_selected_note_id = (
            selected_note_id  # Store currently selected ID
        )
        print(
            f"[NotesModule._on_note_selected_from_tree] Note selected ID: {selected_note_id}. Checking for display area tag: {self.note_content_display_area_tag}"
        )

        # Add a small safeguard - maybe the item exists but isn't ready?
        # dpg.split_frame() # Uncomment if timing issues persist
        # dpg.sleep(0.01)   # Uncomment if timing issues persist

        if dpg.does_item_exist(self.note_content_display_area_tag):
            print(
                f"[NotesModule._on_note_selected_from_tree] Display area tag {self.note_content_display_area_tag} found. Clearing children."
            )
            dpg.delete_item(self.note_content_display_area_tag, children_only=True)

            selected_note: Optional[Note] = next(
                (note for note in self.notes if note.id == selected_note_id), None
            )

            if selected_note:
                display_title = (
                    selected_note.title if selected_note.title else "Untitled Note"
                )
                display_content = (
                    selected_note.content if selected_note.content else "[No content]"
                )

                try:
                    created_str = (
                        selected_note.created_at.strftime("%Y-%m-%d %H:%M")
                        if selected_note.created_at
                        else "N/A"
                    )
                    updated_str = (
                        selected_note.updated_at.strftime("%Y-%m-%d %H:%M")
                        if selected_note.updated_at
                        else "N/A"
                    )
                except AttributeError:
                    created_str = (
                        str(selected_note.created_at)
                        if selected_note.created_at
                        else "N/A"
                    )
                    updated_str = (
                        str(selected_note.updated_at)
                        if selected_note.updated_at
                        else "N/A"
                    )

                # -- Top Section: Title, Metadata, Edit/Save/Cancel Buttons --
                with dpg.group(
                    horizontal=True, parent=self.note_content_display_area_tag
                ):
                    dpg.add_text(display_title, wrap=0)
                    # Edit button (initially visible)
                    dpg.add_button(
                        label="Edit",
                        tag=self.edit_button_tag,
                        callback=self._enable_editing,
                    )
                    # Save button (initially hidden)
                    dpg.add_button(
                        label="Save",
                        tag=self.save_button_tag,
                        callback=self._save_edited_note,
                        show=False,
                    )
                    # Cancel button (initially hidden)
                    dpg.add_button(
                        label="Cancel",
                        tag=self.cancel_button_tag,
                        callback=self._cancel_editing,
                        show=False,
                    )

                dpg.add_text(
                    f"Created: {created_str} | Updated: {updated_str}",
                    parent=self.note_content_display_area_tag,
                    color=(180, 180, 180),
                )
                dpg.add_separator(parent=self.note_content_display_area_tag)

                # --- Tags Display and Editing UI ---
                dpg.add_text("Tags:", parent=self.note_content_display_area_tag)

                # Group to display current tags (will be populated dynamically)
                with dpg.group(
                    tag=self.note_tags_display_group_tag,
                    horizontal=True,
                    parent=self.note_content_display_area_tag,
                ):
                    if selected_note.tags:
                        for tag_text in selected_note.tags:
                            with dpg.group(
                                horizontal=True, parent=self.note_tags_display_group_tag
                            ):
                                dpg.add_text(f"[{tag_text}]")
                                dpg.add_button(
                                    label="(x)",
                                    user_data={
                                        "note_id": selected_note.id,
                                        "tag_to_remove": tag_text,
                                    },
                                    callback=self._remove_tag_from_current_note,
                                    small=True,
                                )
                            dpg.add_spacer(
                                width=4, parent=self.note_tags_display_group_tag
                            )  # Spacer between tag groups
                    else:
                        dpg.add_text("(No tags yet)", color=(150, 150, 150))

                # Input for adding a new tag
                with dpg.group(
                    horizontal=True, parent=self.note_content_display_area_tag
                ):
                    dpg.add_input_text(tag=self.new_tag_input_tag, hint="Enter new tag")
                    dpg.add_button(
                        tag=self.add_tag_button_tag,
                        label="Add Tag",
                        callback=self._add_tag_to_current_note,
                    )

                dpg.add_separator(
                    parent=self.note_content_display_area_tag
                )  # Separator before content
                dpg.add_spacer(height=5, parent=self.note_content_display_area_tag)

                # -- Content Display/Edit Area --
                dpg.add_input_text(
                    tag=self.note_content_input_tag,  # Assign specific tag
                    default_value=display_content,
                    parent=self.note_content_display_area_tag,
                    multiline=True,
                    readonly=True,  # Start as read-only
                    width=-1,
                    height=-1,
                )
                print(
                    f"[NotesModule._on_note_selected_from_tree] Successfully populated display area for note {selected_note_id}."
                )
            else:
                print(
                    f"[NotesModule._on_note_selected_from_tree] Note object not found for ID {selected_note_id}."
                )
                dpg.add_text(
                    f"Error: Could not find note with ID {selected_note_id}.",
                    parent=self.note_content_display_area_tag,
                    color=(255, 0, 0),
                )
        else:
            print(
                f"[NotesModule._on_note_selected_from_tree] CRITICAL Error: Content display area tag {self.note_content_display_area_tag} does not exist AFTER check!"
            )
            # Maybe log the whole item registry? Or try to rebuild?
            # dpg.show_item_registry() # Potentially very verbose

    # Removed _find_dummy_note_content

    # Old _dpg_display_notes_list removed

    # --- Edit/Save/Cancel Callbacks ---
    def _enable_editing(self, sender, app_data, user_data):
        """Make the content input writable and swap buttons."""
        print("[NotesModule._enable_editing] Enabling edit mode.")
        if dpg.does_item_exist(self.note_content_input_tag):
            dpg.configure_item(self.note_content_input_tag, readonly=False)
            # Make sure the input field gets focus? (Optional)
            # dpg.focus_item(self.note_content_input_tag)

        if dpg.does_item_exist(self.edit_button_tag):
            dpg.configure_item(self.edit_button_tag, show=False)

        if dpg.does_item_exist(self.save_button_tag):
            dpg.configure_item(self.save_button_tag, show=True)

        if dpg.does_item_exist(self.cancel_button_tag):
            dpg.configure_item(self.cancel_button_tag, show=True)

    def _save_edited_note(self, sender, app_data, user_data):
        """Save changes, make read-only, swap buttons."""
        print("[NotesModule._save_edited_note] Saving changes.")
        if self.currently_selected_note_id is None:
            print("[NotesModule._save_edited_note] Error: No note selected to save.")
            self._disable_editing(revert_changes=False)
            return

        try:
            new_content = dpg.get_value(self.note_content_input_tag)
            note_to_update = next(
                (n for n in self.notes if n.id == self.currently_selected_note_id), None
            )

            if note_to_update:
                note_to_update.content = new_content
                note_to_update.updated_at = datetime.utcnow()  # Update timestamp
                self._save_notes()  # Save the entire notes list back to JSON
                print(
                    f"[NotesModule._save_edited_note] Note '{note_to_update.id}' saved."
                )
                # TODO: Refresh the displayed timestamp efficiently
                # For now, selecting the note again will show the updated time.
            else:
                print(
                    f"[NotesModule._save_edited_note] Error: Could not find note with ID {self.currently_selected_note_id} to save."
                )
                # Optionally show error to user via status bar?

        except Exception as e:
            print(f"[NotesModule._save_edited_note] Exception during save: {e}")
            # Optionally show error to user
        finally:
            # Always disable editing mode after attempt
            self._disable_editing(revert_changes=False)

    def _cancel_editing(self, sender, app_data, user_data):
        """Revert changes, make read-only, swap buttons."""
        print("[NotesModule._cancel_editing] Cancelling edit.")
        if self.currently_selected_note_id is None:
            print("[NotesModule._cancel_editing] Error: No note selected to cancel.")
            self._disable_editing(revert_changes=True)
            return

        try:
            original_note = next(
                (n for n in self.notes if n.id == self.currently_selected_note_id), None
            )
            if original_note and dpg.does_item_exist(self.note_content_input_tag):
                # Revert input field to original content
                original_content = (
                    original_note.content if original_note.content else ""
                )
                dpg.set_value(self.note_content_input_tag, original_content)
                print(
                    f"[NotesModule._cancel_editing] Reverted content for note '{original_note.id}'."
                )
            elif not original_note:
                print(
                    f"[NotesModule._cancel_editing] Error: Could not find note with ID {self.currently_selected_note_id} to revert content."
                )
            # If input tag doesn't exist, we can't revert, but still disable editing

        except Exception as e:
            print(f"[NotesModule._cancel_editing] Exception during cancel: {e}")
        finally:
            # Always disable editing mode after attempt
            self._disable_editing(
                revert_changes=True
            )  # Pass True for clarity, though value isn't used in disable

    def _disable_editing(self, revert_changes: bool):
        """Make content read-only and swap buttons back."""
        # Note: Revert logic is handled by caller (_cancel_editing) for now
        print(
            f"[NotesModule._disable_editing] Disabling edit mode. Revert: {revert_changes}"
        )

        if dpg.does_item_exist(self.note_content_input_tag):
            dpg.configure_item(self.note_content_input_tag, readonly=True)

        if dpg.does_item_exist(self.edit_button_tag):
            dpg.configure_item(self.edit_button_tag, show=True)

        if dpg.does_item_exist(self.save_button_tag):
            dpg.configure_item(self.save_button_tag, show=False)

        if dpg.does_item_exist(self.cancel_button_tag):
            dpg.configure_item(self.cancel_button_tag, show=False)

    # --- Tagging Methods ---
    def _add_tag_to_current_note(self, sender, app_data, user_data):
        if self.currently_selected_note_id is None:
            print("[NotesModule._add_tag_to_current_note] No note selected.")
            # Optionally: show status to user
            return

        new_tag_text = dpg.get_value(self.new_tag_input_tag).strip()

        if not new_tag_text:
            print("[NotesModule._add_tag_to_current_note] Tag cannot be empty.")
            # Optionally: show status to user
            return

        # Basic validation (e.g., length, allowed characters - can be expanded)
        if len(new_tag_text) > 30:
            print("[NotesModule._add_tag_to_current_note] Tag too long (max 30 chars).")
            return

        selected_note = next(
            (note for note in self.notes if note.id == self.currently_selected_note_id),
            None,
        )
        if not selected_note:
            print(
                f"[NotesModule._add_tag_to_current_note] Selected note with ID {self.currently_selected_note_id} not found."
            )
            return

        if not hasattr(selected_note, "tags") or selected_note.tags is None:
            selected_note.tags = []  # Initialize if somehow missing

        if new_tag_text.lower() not in [
            t.lower() for t in selected_note.tags
        ]:  # Case-insensitive check
            selected_note.tags.append(new_tag_text)
            selected_note.updated_at = datetime.utcnow()  # Update note's timestamp
            self._save_notes()
            dpg.set_value(self.new_tag_input_tag, "")  # Clear input field
            self._refresh_displayed_tags(selected_note)  # Update the UI
            print(
                f"[NotesModule._add_tag_to_current_note] Tag '{new_tag_text}' added to note '{selected_note.id}'."
            )
        else:
            print(
                f"[NotesModule._add_tag_to_current_note] Tag '{new_tag_text}' already exists on note '{selected_note.id}'."
            )
            dpg.set_value(self.new_tag_input_tag, "")  # Still clear input

    def _refresh_displayed_tags(self, note: Note):
        if not dpg.does_item_exist(self.note_tags_display_group_tag):
            return

        dpg.delete_item(self.note_tags_display_group_tag, children_only=True)
        parent_group = self.note_tags_display_group_tag

        if note.tags:
            for tag_text in note.tags:
                with dpg.group(horizontal=True, parent=parent_group):
                    dpg.add_text(f"[{tag_text}]")
                    # Add a small button to remove the tag
                    dpg.add_button(
                        label="(x)",
                        user_data={"note_id": note.id, "tag_to_remove": tag_text},
                        callback=self._remove_tag_from_current_note,
                        small=True,
                    )  # Make button small
                dpg.add_spacer(
                    width=4, parent=parent_group
                )  # Spacer between tag groups
        else:
            dpg.add_text("(No tags yet)", color=(150, 150, 150), parent=parent_group)

    def _remove_tag_from_current_note(self, sender, app_data, user_data):
        if (
            not user_data
            or "note_id" not in user_data
            or "tag_to_remove" not in user_data
        ):
            print("[NotesModule._remove_tag_from_current_note] Invalid user_data.")
            return

        note_id = user_data["note_id"]
        tag_to_remove = user_data["tag_to_remove"]

        if self.currently_selected_note_id != note_id:
            print(
                f"[NotesModule._remove_tag_from_current_note] Mismatch: current note {self.currently_selected_note_id}, tag removal for {note_id}"
            )
            # This shouldn't happen if UI is refreshed correctly but good to check.
            return

        selected_note = next((n for n in self.notes if n.id == note_id), None)

        if not selected_note:
            print(
                f"[NotesModule._remove_tag_from_current_note] Note with ID {note_id} not found."
            )
            return

        if not hasattr(selected_note, "tags") or selected_note.tags is None:
            print(
                f"[NotesModule._remove_tag_from_current_note] Note {note_id} has no tags attribute or it's None."
            )
            return  # Nothing to remove

        # Case-insensitive removal
        tag_to_remove_lower = tag_to_remove.lower()
        original_length = len(selected_note.tags)
        selected_note.tags = [
            t for t in selected_note.tags if t.lower() != tag_to_remove_lower
        ]

        if len(selected_note.tags) < original_length:
            selected_note.updated_at = datetime.utcnow()
            self._save_notes()
            self._refresh_displayed_tags(selected_note)
            print(
                f"[NotesModule._remove_tag_from_current_note] Tag '{tag_to_remove}' removed from note '{note_id}'."
            )
        else:
            print(
                f"[NotesModule._remove_tag_from_current_note] Tag '{tag_to_remove}' not found on note '{note_id}'."
            )

    def _handle_note_sidebar_click(self, sender, app_data, user_data):
        # sender: ID of the item_handler_registry that caught the click.
        # app_data: Mouse button that was clicked (e.g., dpg.mvMouseButton_Right which is 1).
        # user_data: The note.id passed when creating the item_clicked_handler.

        clicked_note_id = user_data  # This is the note.id
        self.context_menu_active_note_id = clicked_note_id
        # self.logger.debug(f"[_handle_note_sidebar_click] Right-click detected on note ID: {clicked_note_id}. Sender: {sender}, App Data: {app_data}")

        if not clicked_note_id:
            # self.logger.warning("[_handle_note_sidebar_click] No note ID received in user_data.")
            return

        # Ensure context menu tag exists
        if not self.note_context_menu_tag or not dpg.does_item_exist(
            self.note_context_menu_tag
        ):
            self.logger.error(
                "[_handle_note_sidebar_click] Context menu tag does not exist!"
            )
            # Attempt to recreate it if it's missing, though this indicates a deeper issue.
            self.note_context_menu_tag = dpg.generate_uuid()
            with dpg.window(
                tag=self.note_context_menu_tag,
                popup=True,
                autosize=True,
                no_title_bar=True,
                show=False,
            ) as menu_tag:
                self.logger.info(f"Recreated context menu with tag: {menu_tag}")
                # It will be empty initially, items added below.

        # Clear any existing items in the context menu first
        dpg.delete_item(self.note_context_menu_tag, children_only=True)

        # Populate the context menu dynamically
        # The user_data for these menu items will be the clicked_note_id
        # so the callbacks know which note to act upon.
        dpg.add_menu_item(
            label="Open",
            callback=self._context_open_note,
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
        )
        dpg.add_menu_item(
            label="Edit",
            callback=self._context_edit_note,  # Assuming _context_edit_note is defined
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
        )
        dpg.add_menu_item(
            label="Rename",
            callback=self._context_rename_note_setup,  # Opens the rename dialog
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
        )
        dpg.add_menu_item(
            label="Delete",
            callback=self._context_delete_note_from_context,  # Prompts for deletion
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
        )
        dpg.add_menu_item(
            label="Move...",  # Placeholder for now
            callback=self._context_move_note,  # Assuming _context_move_note is defined
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
            enabled=False,  # Disable 'Move' for now as it's not implemented
        )
        dpg.add_separator(
            parent=self.note_context_menu_tag
        )  # Separator before New Folder
        dpg.add_menu_item(
            label="New Folder",
            callback=self._context_create_folder_setup,
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
        )

        clicked_item_object = next(
            (n for n in self.notes if n.id == clicked_note_id), None
        )
        if clicked_item_object and clicked_item_object.is_folder:
            dpg.add_menu_item(
                label="New Note Here",
                callback=self._context_create_note_in_folder_setup,
                user_data=clicked_note_id,
                parent=self.note_context_menu_tag,
            )

        dpg.add_separator(parent=self.note_context_menu_tag)
        dpg.add_menu_item(
            label="New Folder",
            callback=self._context_create_folder_setup,
            user_data=clicked_note_id,
            parent=self.note_context_menu_tag,
        )

        # Show the context menu at the mouse position
        # dpg.set_item_pos(self.note_context_menu_tag, dpg.get_mouse_pos(local=False))
        dpg.configure_item(self.note_context_menu_tag, show=True)
        # self.logger.debug(f"Showing context menu '{self.note_context_menu_tag}' for note ID '{clicked_note_id}'.")

    def _context_open_note(self, sender, app_data, user_data):
        note_id = user_data
        if note_id:
            # self.logger.debug(f"[_context_open_note] Opening note with ID: {note_id}")
            # Simulate a left-click selection to reuse existing display logic
            self._on_note_selected_from_tree(
                sender=f"note_selectable_{note_id}", app_data=None, user_data=note_id
            )
        else:
            # self.logger.warning("[_context_open_note] No note ID provided.")
            pass

    def _context_edit_note(self, sender, app_data, user_data):
        note_id = user_data
        if note_id:
            # self.logger.debug(f"[_context_edit_note] Attempting to edit note with ID: {note_id}")
            note_to_edit = next((n for n in self.notes if n.id == note_id), None)
            if note_to_edit:
                # self.logger.debug(f"[_context_edit_note] Note found: {note_to_edit.title}. Opening editor.")
                self._open_editor(
                    note_to_edit
                )  # _open_editor should handle populating and showing the editor
            else:
                # self.logger.warning(f"[_context_edit_note] Note with ID {note_id} not found.")
                self._show_error(f"Could not find note with ID {note_id} to edit.")
        else:
            # self.logger.warning("[_context_edit_note] No note ID provided for editing.")
            pass

    def _context_create_folder_setup(self, sender, app_data, user_data):
        clicked_item_id = user_data  # ID of the item that was right-clicked
        actual_parent_id: Optional[str] = None

        if clicked_item_id:
            # If a folder was clicked, the new folder goes inside it.
            # If a note was clicked, the new folder goes in the same parent as that note.
            clicked_item = self._find_note_by_id(clicked_item_id)
            if clicked_item:
                if clicked_item.is_folder:
                    actual_parent_id = clicked_item_id
                else:
                    actual_parent_id = clicked_item.parent_id  # Can be None (root)
            # If clicked_item_id was None or item not found, actual_parent_id remains None (root)

        # self.logger.info(f"[_context_create_folder_setup] Calling dialog_manager.show_new_folder_dialog with parent_id: {actual_parent_id}")
        self.dialog_manager.show_new_folder_dialog(actual_parent_id)

    def _context_create_note_in_folder_setup(self, sender, app_data, user_data):
        parent_folder_id = (
            user_data  # This is the ID of the folder where the note should be created
        )
        # self.logger.info(f"[_context_create_note_in_folder_setup] Request to create new note in folder ID: {parent_folder_id}")

        self.pending_new_note_parent_id = parent_folder_id
        self.current_editing_note_id = None  # Explicitly ensure we are in new note mode

        if self.editor_title is not None:
            dpg.set_value(self.editor_title, "New Note")  # Default title
        if self.editor_content is not None:
            dpg.set_value(self.editor_content, "")
        dpg.show_item("editor_window")
        if self.editor_title is not None:  # Attempt to focus after showing
            dpg.focus_item(self.editor_title)

    def _context_rename_note_setup(self, sender, app_data, user_data):
        note_id_to_rename = user_data  # This is the note_id from the context menu item
        # self.logger.debug(f"[_context_rename_note_setup] Setting up rename for note ID: {note_id_to_rename}")

        if not note_id_to_rename:
            # self.logger.warning("[_context_rename_note_setup] No note ID provided.")
            return

        # self.context_menu_active_note_id should already be set by _handle_note_sidebar_click
        # but we confirm it or set it explicitly if necessary for robustness, though user_data is more direct here.
        self.context_menu_active_note_id = note_id_to_rename

        note_to_rename = next(
            (n for n in self.notes if n.id == note_id_to_rename), None
        )

        if note_to_rename:
            # self.logger.debug(f"[_context_rename_note_setup] Note found: '{note_to_rename.title}'. Populating input field.")
            dpg.set_value(self.rename_note_input_tag, note_to_rename.title)
            dpg.configure_item(self.rename_note_window_tag, show=True)
        else:
            # self.logger.warning(f"[_context_rename_note_setup] Note with ID {note_id_to_rename} not found.")
            self._show_error(
                f"Could not find note with ID {note_id_to_rename} to rename."
            )

    def _execute_create_folder(self, sender, app_data, user_data):
        folder_name = dpg.get_value(
            self.dialog_manager.new_folder_name_input_tag
        ).strip()
        folder_icon = dpg.get_value(
            self.dialog_manager.new_folder_icon_input_tag
        ).strip()
        parent_id = (
            self.pending_new_folder_parent_id
        )  # This state is still managed by NotesModule

        if not folder_name:
            self._show_error("Folder name cannot be empty.")
            # Keep dialog open, focus name input again
            if dpg.does_item_exist(self.dialog_manager.new_folder_name_input_tag):
                dpg.focus_item(self.dialog_manager.new_folder_name_input_tag)
            return

        # self.logger.info(f"Executing create folder: '{folder_name}' with icon '{folder_icon}' under parent ID: {parent_id}")
        try:
            new_order = self._get_next_order_in_parent(parent_id)
            new_folder_schema = NoteCreate(
                title=folder_name,
                is_folder=True,
                parent_id=parent_id,
                content="",
                icon=folder_icon if folder_icon else None,
                order=new_order,
            )
            created_folder = Note(**new_folder_schema.model_dump())
            self.notes.append(created_folder)
            self._save_notes()
            self._refresh_sidebar_note_list()
            # self.logger.info(f"Created folder '{created_folder.title}' (ID: {created_folder.id}) successfully.")
        except Exception as e:
            self.logger.error(f"Error executing create folder: {e}")
            self._show_error(f"Failed to create folder: {e}")
        finally:
            dpg.configure_item(self.new_folder_dialog_tag, show=False)
            dpg.set_value(self.new_folder_name_input_tag, "")
            dpg.set_value(self.new_folder_icon_input_tag, "")  # Clear icon input
            self.pending_new_folder_parent_id = None

    def _setup_delete_confirmation_dialog_tags(self):
        # Call this in __init__ or ensure tags are defined before first use
        if not hasattr(self, "delete_confirm_dialog_tag"):
            self.delete_confirm_dialog_tag = dpg.generate_uuid()
            self.delete_confirm_text_tag = dpg.generate_uuid()
            self.delete_confirm_note_id_to_delete: Optional[str] = None

            with dpg.window(
                label="Confirm Deletion",
                modal=True,
                show=False,
                tag=self.delete_confirm_dialog_tag,
                width=400,
                height=150,
                no_resize=True,
                no_close=True,  # Prevent accidental close, force choice
            ) as dialog_tag:
                self.delete_confirm_text_tag = dpg.add_text(
                    "Are you sure you want to delete this note?"  # Initial simple text
                )
                dpg.add_separator()
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Yes, Delete",
                        callback=self._execute_confirmed_delete,
                        width=-1,
                    )
                    dpg.add_button(
                        label="No, Cancel",
                        callback=lambda: dpg.configure_item(
                            self.delete_confirm_dialog_tag, show=False
                        ),
                        width=-1,
                    )
            # self.logger.info(f"Delete confirmation dialog ensured/created with tag: {dialog_tag}")
        # else:
        # self.logger.debug("Delete confirmation dialog already exists.")

    def _show_delete_confirmation_dialog(self, note_id: str, note_title: str):
        if not hasattr(self, "delete_confirm_dialog_tag") or not dpg.does_item_exist(
            self.delete_confirm_dialog_tag
        ):
            self.logger.info("Delete confirmation dialog not set up, creating now.")
        self._setup_delete_confirmation_dialog_tags()  # Ensure it exists

        if not dpg.does_item_exist(self.delete_confirm_dialog_tag):
            self.logger.error(
                "Failed to create or find delete confirmation dialog. Cannot proceed."
            )
            self._show_error("Error: Delete confirmation dialog is unavailable.")
            return

        self.delete_confirm_note_id_to_delete = note_id
        dpg.set_value(
            self.delete_confirm_text_tag,
            f"Are you sure you want to delete the note: '{note_title}'?\nThis action cannot be undone.",
        )
        dpg.configure_item(self.delete_confirm_dialog_tag, show=True)
        # self.logger.debug(f"Showing delete confirmation for note ID: {note_id}, Title: '{note_title}'.")

    def _execute_confirmed_delete(self, sender, app_data, user_data):
        note_id_to_delete = self.delete_confirm_note_id_to_delete
        # self.logger.debug(f"[_execute_confirmed_delete] Confirmation received to delete note ID: {note_id_to_delete}")

        dpg.configure_item(
            self.delete_confirm_dialog_tag, show=False
        )  # Hide dialog first

        if note_id_to_delete:
            self._delete_note(
                note_id_to_delete
            )  # This method handles data, save, and UI refresh
            # self.logger.info(f"[_execute_confirmed_delete] Note ID '{note_id_to_delete}' passed to _delete_note.")
        else:
            # self.logger.warning("[_execute_confirmed_delete] No note ID was stored for deletion.")
            self._show_error("Error: Could not determine which note to delete.")
        self.delete_confirm_note_id_to_delete = None  # Clear the stored ID

    # Callback for 'Delete' from context menu
    def _context_delete_note_from_context(self, sender, app_data, user_data):
        note_id_to_delete = user_data  # This is the note_id from the context menu item
        # self.logger.debug(f"[_context_delete_note_from_context] Request to delete note ID: {note_id_to_delete}")

        if not note_id_to_delete:
            # self.logger.warning("[_context_delete_note_from_context] No note ID provided.")
            return

        note_to_delete = next(
            (n for n in self.notes if n.id == note_id_to_delete), None
        )

        if note_to_delete:
            # self.logger.debug(f"[_context_delete_note_from_context] Note found: '{note_to_delete.title}'. Showing confirmation.")
            # Ensure the dialog is set up before showing it
            if not hasattr(self, "delete_confirm_dialog_tag"):
                self._setup_delete_confirmation_dialog_tags()
            self._show_delete_confirmation_dialog(
                note_id_to_delete, note_to_delete.title
            )
        else:
            # self.logger.warning(f"[_context_delete_note_from_context] Note with ID {note_id_to_delete} not found.")
            self._show_error(
                f"Could not find note with ID {note_id_to_delete} to delete."
            )

    def _context_move_note(self, sender, app_data, user_data):
        item_id_to_move = user_data
        # self.logger.info(f"[_context_move_note] Request to move item ID: {item_id_to_move}")

        item_being_moved = self._find_note_by_id(item_id_to_move)  # Use helper
        if not item_being_moved:
            self._show_error(f"Cannot move: Item {item_id_to_move} not found.")
            # self.logger.warning(f"[_context_move_note] Item with ID {item_id_to_move} not found for moving.")
            return

        self.item_to_move_id = item_id_to_move
        item_base_icon = (
            item_being_moved.icon
            if item_being_moved.icon and item_being_moved.icon.strip()
            else (
                self.ICON_FOLDER_DEFAULT
                if item_being_moved.is_folder
                else self.ICON_NOTE_DEFAULT
            )
        )
        item_display_name = f"{item_base_icon} {item_being_moved.title}"

        if dpg.does_item_exist(self.move_item_label_tag):
            dpg.set_value(self.move_item_label_tag, f"Moving: {item_display_name}")
        else:
            self.logger.error(
                f"[_context_move_note] Move item label tag {self.move_item_label_tag} does not exist."
            )

        # Initialize with the "Root" option using the sentinel value
        self.available_folders_for_move_dropdown = [
            (f"{self.ICON_ROOT} Root", self.ROOT_SENTINEL_VALUE)
        ]

        ids_to_exclude = {item_id_to_move}  # Exclude the item itself
        if item_being_moved.is_folder:
            descendant_ids = self._get_all_descendant_ids(item_id_to_move, self.notes)
            ids_to_exclude.update(descendant_ids)
            # self.logger.debug(f"[_context_move_note] Excluding item {item_id_to_move} and its descendants: {descendant_ids}")

        # Sort folders by title for the dropdown
        valid_destination_folders = sorted(
            [
                note
                for note in self.notes
                if note.is_folder and note.id not in ids_to_exclude
            ],
            key=lambda f: f.title.lower(),
        )

        for folder in valid_destination_folders:
            self.available_folders_for_move_dropdown.append((folder.title, folder.id))

        dropdown_labels = [item[0] for item in self.available_folders_for_move_dropdown]

        if dpg.does_item_exist(self.move_item_destination_folder_dropdown_tag):
            dpg.configure_item(
                self.move_item_destination_folder_dropdown_tag, items=dropdown_labels
            )
            # Set default. If current parent is a valid destination, select it. Otherwise 'None (Root)' or first valid.
            current_parent_label = "None (Root)"
            if item_being_moved.parent_id:
                current_parent_folder = next(
                    (
                        f_title
                        for f_title, f_id in self.available_folders_for_move_dropdown
                        if f_id == item_being_moved.parent_id
                    ),
                    None,
                )
                if current_parent_folder:
                    current_parent_label = current_parent_folder

            if current_parent_label in dropdown_labels:
                dpg.set_value(
                    self.move_item_destination_folder_dropdown_tag, current_parent_label
                )
            elif (
                dropdown_labels
            ):  # Fallback to first item if current parent isn't valid or None (Root) isn't in filtered list
                dpg.set_value(
                    self.move_item_destination_folder_dropdown_tag, dropdown_labels[0]
                )
        else:
            self.logger.error(
                "[_context_move_note] Destination folder dropdown DPG item does not exist!"
            )

        if dpg.does_item_exist(self.move_item_dialog_tag):
            dpg.configure_item(self.move_item_dialog_tag, show=True)
        else:
            self.logger.error(
                "[_context_move_note] 'Move Item Dialog' DPG item does not exist!"
            )
            self._show_error("Cannot open Move Item dialog.")

    def _execute_move_item(self, sender, app_data, user_data):
        # self.logger.info(f"[_execute_move_item] Called. Item to move ID: {self.item_to_move_id}")
        selected_destination_label = dpg.get_value(
            self.move_item_destination_folder_dropdown_tag
        )

        actual_new_parent_id: Optional[str] = None
        found_label = False
        for label, p_id_or_sentinel in self.available_folders_for_move_dropdown:
            if label == selected_destination_label:
                if p_id_or_sentinel == self.ROOT_SENTINEL_VALUE:
                    actual_new_parent_id = None
                else:
                    actual_new_parent_id = (
                        p_id_or_sentinel  # This is already an Optional[str]
                    )
                found_label = True
                break

        if not found_label:
            self._show_error(
                "Error: Selected destination not found in available options."
            )
            self.logger.error(
                f"[_execute_move_item] Selected label '{selected_destination_label}' not in {self.available_folders_for_move_dropdown}"
            )
            dpg.configure_item(self.move_item_dialog_tag, show=False)
            return

        if self.item_to_move_id is None:
            self._show_error("Error: No item was identified to be moved.")
            dpg.configure_item(self.move_item_dialog_tag, show=False)
            return

        item_to_update = self._find_note_by_id(self.item_to_move_id)
        if not item_to_update:
            self._show_error(
                f"Error: Item with ID {self.item_to_move_id} not found for moving."
            )
            dpg.configure_item(self.move_item_dialog_tag, show=False)
            self.item_to_move_id = None  # Clear it
            return

        # Validation: Prevent moving a folder into itself or one of its own descendants
        if item_to_update.is_folder:
            if actual_new_parent_id == item_to_update.id:  # Moving folder into itself
                self._show_error("Cannot move a folder into itself.")
                # self.logger.info("[_execute_move_item] Prevented moving folder into itself.")
                return  # Keep dialog open for user to correct

            descendants_of_item_being_moved = self._get_all_descendant_ids(
                item_to_update.id, self.notes
            )
            if actual_new_parent_id in descendants_of_item_being_moved:
                self._show_error("Cannot move a folder into one of its own subfolders.")
                # self.logger.info("[_execute_move_item] Prevented moving folder into a descendant.")
                return  # Keep dialog open

        # Validation: Prevent moving to the current parent (no actual change)
        if item_to_update.parent_id == actual_new_parent_id:
            self._show_error(
                f"Item is already in the selected destination. No move performed."
            )
            # self.logger.info(f"[_execute_move_item] Item '{item_to_update.title}' is already in parent '{actual_new_parent_id}'.")
            # Not closing dialog here, user might want to pick another or cancel.
            return

        # self.logger.info(f"[_execute_move_item] Attempting to move '{item_to_update.title}' (ID: {self.item_to_move_id}) to parent ID: {actual_new_parent_id}")
        try:
            # Calculate order *before* changing parent_id if item is just reordering in same parent,
            # but for a move to a *new* parent, order is based on target parent's current children.
            new_order = self._get_next_order_in_parent(actual_new_parent_id)

            item_to_update.parent_id = actual_new_parent_id
            item_to_update.order = new_order
            item_to_update.updated_at = datetime.utcnow()

            self._save_notes()
            self._refresh_sidebar_note_list()

            # Update main view if the moved item was selected
            if self.currently_selected_note_id == item_to_update.id:
                self._update_note_display()

            # self.logger.info(f"[_execute_move_item] Item '{item_to_update.title}' moved successfully to parent '{actual_new_parent_id}' with order {new_order}.")
        except Exception as e:
            self.logger.error(
                f"[_execute_move_item] Error moving item: {e}", exc_info=True
            )
            self._show_error(f"Failed to move item: {e}")
        finally:
            dpg.configure_item(self.move_item_dialog_tag, show=False)
            self.item_to_move_id = None  # Clear the stored ID

    def _get_all_descendant_ids(
        self, folder_id: str, notes_list: List[Note]
    ) -> set[str]:
        # self.logger.debug(f"[_get_all_descendant_ids] Getting descendants for folder_id: {folder_id}")
        descendants = set()
        children = [note for note in notes_list if note.parent_id == folder_id]
        for child in children:
            descendants.add(child.id)
            if child.is_folder:
                descendants.update(self._get_all_descendant_ids(child.id, notes_list))
        # self.logger.debug(f"[_get_all_descendant_ids] Descendants for {folder_id}: {descendants}")
        return descendants

    def _get_next_order_in_parent(self, parent_id: Optional[str]) -> int:
        """Calculates the next available order index for a given parent."""
        if parent_id is None:  # Root items
            count = sum(1 for note in self.notes if note.parent_id is None)
        else:  # Items in a specific folder
            count = sum(1 for note in self.notes if note.parent_id == parent_id)
        return count

    def _find_note_by_id(self, note_id: str) -> Optional[Note]:
        """Finds a note or folder by its ID."""
        return next((note for note in self.notes if note.id == note_id), None)

    # Make sure to add the new methods if they are not defined elsewhere.
    # For example, if _open_editor or similar are not fully implemented.
    # Ensure that the _delete_note method correctly refreshes the sidebar.

    # Helper to find note by ID, can be used by context actions
    # def get_note_by_id(self, note_id: str) -> Optional[Note]:
    #     return next((note for note in self.notes if note.id == note_id), None)

    # Ensure that in your sidebar building logic (e.g., _refresh_sidebar_note_list),
    # when you create the selectable items for each note, you are assigning
    # its dpg.mvMouseButton_Right click handler to the self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG
    # Example (conceptual):
    # for note in notes_to_display:
    #     with dpg.tree_node(label=note.title, user_data=note.id, parent=parent_tag_for_notes_list) as note_node_tag:
    #         # Make the tree_node itself clickable for selection (left-click)
    #         dpg.add_selectable(label=f"Select {note.title}", user_data=note.id, callback=self._on_note_selected_from_tree, parent=note_node_tag) # This is if tree_node itself doesn't fire selection
    #         # Assign the handler registry for right-click context menu
    #         dpg.bind_item_handler_registry(note_node_tag, self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG)

    # Or if using simple selectables:
    # for note in notes_to_display:
    #    item_tag = dpg.add_selectable(label=note.title, user_data=note.id, callback=self._on_note_selected_from_tree, parent=self.sidebar_notes_list_actual_tag)
    #    dpg.bind_item_handler_registry(item_tag, self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG)

    # Consider adding confirmation dialogs for delete operations.
    # The _open_editor method should be checked to ensure it correctly loads the note.
    # The _delete_note method needs to handle removing the note from self.notes, saving, and refreshing the UI.
    # The `self.context_menu_active_note_id` is correctly set in `_handle_note_sidebar_click`.

    # Ensure the `_get_note_by_id` (if you add it) or similar logic is robust.
    # Ensure `_on_note_selected_from_tree` correctly handles loading the note content.
    # Ensure `_open_editor` is correctly implemented and opens the editor with the note's data.
    # Ensure `_context_rename_note_setup`

    def _execute_create_new_note(self, sender, app_data, user_data):
        """Handles creation of a new note from the 'New Note Dialog'."""
        # self.logger.info("[_execute_create_new_note] Creating note from dialog.")

        title = dpg.get_value(self.dialog_manager.new_note_title_input_tag).strip()
        icon = dpg.get_value(self.dialog_manager.new_note_icon_input_tag).strip()
        selected_parent_label = dpg.get_value(
            self.dialog_manager.new_note_parent_folder_dropdown_tag
        )

        if not title:
            self._show_error("Note title cannot be empty.")
            # self.logger.warning("[_execute_create_new_note] Title was empty.")
            dpg.focus_item(
                self.dialog_manager.new_note_title_input_tag
            )  # Keep dialog open and focus title
            return

        actual_parent_id: Optional[str] = None
        # Find the parent_id from the label selected in the dropdown
        for p_label, p_id in self.available_folders_for_new_note_dropdown:
            if p_label == selected_parent_label:
                actual_parent_id = (
                    p_id  # This will be None if "None (Root)" was selected
                )
                break

        # self.logger.debug(f"[_execute_create_new_note] Title: '{title}', Icon: '{icon}', Parent ID: {actual_parent_id}")

        try:
            new_order = self._get_next_order_in_parent(actual_parent_id)
            note_create_data = NoteCreate(
                title=title,
                content="",  # New notes start with empty content in the editor
                is_folder=False,
                parent_id=actual_parent_id,
                icon=icon if icon else None,  # Use icon if provided
                order=new_order,
            )
            new_note = Note(**note_create_data.model_dump())
            self.notes.append(new_note)
            self._save_notes()
            self._refresh_sidebar_note_list()

            dpg.configure_item(self.dialog_manager.new_note_dialog_tag, show=False)
            dpg.set_value(
                self.dialog_manager.new_note_title_input_tag, ""
            )  # Clear for next time
            dpg.set_value(
                self.dialog_manager.new_note_icon_input_tag, ""
            )  # Clear for next time
            # Default dropdown to root for next time is handled by _create_new_note setup

            # Open the editor for the new note
            self._open_editor(new_note)
            # self.logger.info(f"[_execute_create_new_note] Successfully created and opened new note: {new_note.id}")

        except ValidationError as e:
            self.logger.error(
                f"[_execute_create_new_note] Validation error: {e.errors()}"
            )
            self._show_error(
                f"Validation Error: {e.errors()[0]['msg'] if e.errors() else 'Invalid data'}"
            )
        except Exception as e:
            self.logger.error(
                f"[_execute_create_new_note] Failed to create new note: {e}",
                exc_info=True,
            )
            self._show_error(f"Failed to create new note: {e}")

    def _populate_folder_dropdown_for_new_note_dialog(self):
        # self.logger.debug(
        #     "[_populate_folder_dropdown_for_new_note_dialog] Populating folder dropdown for new note."
        # )
        # Initialize with the option to place in root
        self.available_folders_for_new_note_dropdown = [
            ("None (Root)", self.ROOT_SENTINEL_VALUE)
        ]

        # Iterate through all notes to find folders (notes that can act as parents)
        notes_module_instance = self.core.module_registry.get("Notes")
        if notes_module_instance:  # Check if the module instance exists
            # Ensure notes_module_instance is indeed a NotesModule and has 'notes' attribute
            if hasattr(notes_module_instance, "notes") and isinstance(
                notes_module_instance.notes, list
            ):
                for (
                    note_object
                ) in (
                    notes_module_instance.notes
                ):  # Iterate over the list of Note Pydantic objects
                    if (
                        note_object.is_folder
                    ):  # Check the is_folder attribute of the Note object
                        title = (
                            note_object.title
                            if note_object.title
                            else "Untitled Folder"
                        )
                        self.available_folders_for_new_note_dropdown.append(
                            (title, note_object.id)
                        )
            else:
                self.logger.error(
                    "Notes module does not have a valid 'notes' list attribute."
                )
        else:
            self.logger.error(
                "Notes module not found in _populate_folder_dropdown_for_new_note_dialog"
            )

        # self.logger.debug(f"Available folders for dropdown: {self.available_folders_for_new_note_dropdown}")

        # Ensure the dropdown tag exists via the dialog manager
        if hasattr(
            self.dialog_manager, "new_note_parent_folder_dropdown_tag"
        ) and dpg.does_item_exist(
            self.dialog_manager.new_note_parent_folder_dropdown_tag
        ):
            dropdown_items = [
                item[0] for item in self.available_folders_for_new_note_dropdown
            ]
            dpg.configure_item(
                self.dialog_manager.new_note_parent_folder_dropdown_tag,
                items=dropdown_items,
            )
            # Set a default value if needed, e.g., the first item which is "None (Root)"
            if dropdown_items:
                dpg.set_value(
                    self.dialog_manager.new_note_parent_folder_dropdown_tag,
                    dropdown_items[0],
                )
        else:
            self.logger.warning(
                "new_note_parent_folder_dropdown_tag does not exist or dialog_manager is not set up correctly."
            )

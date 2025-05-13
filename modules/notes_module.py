import dearpygui.dearpygui as dpg  # Changed from flet
import json
from pathlib import Path
from datetime import datetime  # For Note schema
from typing import TYPE_CHECKING, List, Optional, Union, Tuple  # Added Union and Tuple
from pydantic import ValidationError  # Added for specific exception handling

# from core import Core # Removed old import
from .base_module import BaseModule
from schemas import NoteCreate, Note  # Import the new schemas
from core.decorators import handle_errors

if TYPE_CHECKING:  # Added TYPE_CHECKING block
    from core.app import Core  # Import Core from core.app for type hinting


# Dummy data for the tree view - REMOVED
# DUMMY_NOTE_HIERARCHY = { ... }


class NotesModule(BaseModule):  # Renamed from NoteModule
    def __init__(self, core: "Core"):  # Changed to string literal "Core"
        # print("[NotesModule.__init__] Method started.")
        super().__init__(core)
        # print("[NotesModule.__init__] super().__init__(core) called.")

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
            from core.config import AppConfig as DefaultAppConfig  # Temporary import

            self.data_path = DefaultAppConfig().notes_path
            # print(f"[NotesModule.__init__] WARNING: data_path set from DefaultAppConfig: {self.data_path}") # ADDED
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
        # print(f"[NotesModule.__init__] Data directory ensured: {self.data_path.parent}") # ADDED

        self.notes: List[Note] = []  # To store loaded Note objects
        # print("[NotesModule.__init__] self.notes initialized.") # ADDED
        self.current_editing_note_id: Optional[str] = None  # To track for updates
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
        self.note_content_input_tag: Union[int, str] = dpg.generate_uuid() # This was for inline editing
        self.edit_button_tag: Union[int, str] = dpg.generate_uuid()
        self.save_button_tag: Union[int, str] = dpg.generate_uuid()
        self.cancel_button_tag: Union[int, str] = dpg.generate_uuid()

        # Tags for tag editing UI
        self.note_tags_display_group_tag: Union[int, str] = dpg.generate_uuid() # Group to display current tags
        self.new_tag_input_tag: Union[int, str] = dpg.generate_uuid()       # Input for new tag
        self.add_tag_button_tag: Union[int, str] = dpg.generate_uuid()      # Button to add the new tag

        # Tags for tag filtering UI
        self.tag_filter_list_container_tag: Union[int, str] = dpg.generate_uuid() # Container for filter tags
        self.sidebar_notes_list_actual_tag: Union[int, str] = dpg.generate_uuid() # Actual list of notes in sidebar
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
        if not dpg.does_item_exist("editor_window"): # Ensure it's only defined once globally if multiple notes modules were possible
            with dpg.window(
                tag="editor_window",
                label="Note Editor",
                width=600,
                height=400,
                show=False, # Initially hidden
                on_close=self._close_editor, # Assuming _close_editor is defined
            ):
                self.editor_title = dpg.add_input_text(label="Title")
                self.editor_content = dpg.add_input_text(
                    label="Content",
            multiline=True,
                    height=-40,
                    tab_input=True
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Save", callback=self._save_note) # Assuming _save_note is defined
                    dpg.add_button(label="Cancel", callback=self._close_editor)

        # Initial load and display of notes
        self.load_data()  # Call load_data which will call _dpg_display_notes_list

        # For context menu
        self.note_context_menu_tag: Union[int, str] = dpg.generate_uuid()
        self.context_menu_active_note_id: Optional[str] = None # Store ID for context actions
        self.rename_note_window_tag: Union[int, str] = dpg.generate_uuid()
        self.rename_note_input_tag: Union[int, str] = dpg.generate_uuid()

        # Handler Registry for note items in sidebar
        self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG = "note_sidebar_item_handler_registry_actual_tag" # Use a clear string tag
        if not dpg.does_item_exist(self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG):
            print(f"[NotesModule.__init__] Creating new handler registry with tag: {self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}")
            # dpg.add_handler_registry returns an int ID, but we want to use our string tag.
            # We create handlers as children of the registry using the 'parent' argument,
            # or by creating them within a 'with dpg.handler_registry(tag=...):' block.
            with dpg.handler_registry(tag=self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG):
                dpg.add_mouse_click_handler(
                    button=dpg.mvMouseButton_Right,
                    callback=self._handle_note_sidebar_click
                )
            # ===== BEGIN DEBUGGING ADDITION =====
            if dpg.does_item_exist(self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG):
                registry_info = dpg.get_item_info(self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG)
                print(f"[NotesModule.__init__] Handler registry '{self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}' info after creation: {registry_info}")
            else:
                print(f"[NotesModule.__init__] CRITICAL FAILURE: Handler registry '{self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}' does NOT exist after creation attempt.")
            # ===== END DEBUGGING ADDITION =====
        else:
            print(f"[NotesModule.__init__] Using existing handler registry with tag: {self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}")
            # ===== BEGIN DEBUGGING ADDITION (for existing case) =====
            if dpg.does_item_exist(self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG):
                registry_info = dpg.get_item_info(self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG)
                print(f"[NotesModule.__init__] EXISTING Handler registry '{self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}' info: {registry_info}")
            # ===== END DEBUGGING ADDITION =====

        # Define the actual context menu window (initially empty and hidden)
        if not dpg.does_item_exist(self.note_context_menu_tag):
            with dpg.window(tag=self.note_context_menu_tag, popup=True, autosize=True, no_title_bar=True, show=False):
                pass # Items will be added dynamically

        # Define Rename Note dialog (modal, initially hidden)
        if not dpg.does_item_exist(self.rename_note_window_tag):
            with dpg.window(label="Rename Note", modal=True, show=False, tag=self.rename_note_window_tag, width=300, height=120, no_resize=True):
                dpg.add_input_text(tag=self.rename_note_input_tag, label="New Title", width=-1)
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Rename", callback=self._context_rename_note_execute, width=-1)
                    dpg.add_button(label="Cancel", callback=lambda: dpg.configure_item(self.rename_note_window_tag, show=False), width=-1)

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the main display area for the Notes tab."""
        print(f"[NotesModule.build_dpg_view] Attempting to build in parent: {parent_container_tag} (type: {type(parent_container_tag)})")

        if not dpg.does_item_exist(parent_container_tag):
            print(f"[NotesModule.build_dpg_view] Error: Parent container {parent_container_tag} does not exist!")
            # Cannot build the view if the parent isn't there
            return

        # Ensure the target tag doesn't already exist (e.g., from a previous failed build)
        if dpg.does_item_exist(self.note_content_display_area_tag):
            print(f"[NotesModule.build_dpg_view] Warning: Content display tag {self.note_content_display_area_tag} already exists. Deleting children.")
            dpg.delete_item(self.note_content_display_area_tag, children_only=True)
        else:
            # Create the main group for note content display
            dpg.add_group(tag=self.note_content_display_area_tag, parent=parent_container_tag)
            print(f"[NotesModule.build_dpg_view] Created content display group {self.note_content_display_area_tag} in parent {parent_container_tag}")

        # Add initial placeholder text inside the (now guaranteed) existing group
        dpg.add_text("Select a note from the sidebar to view its content.", parent=self.note_content_display_area_tag)

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
                            print(f"[NotesModule.load_data] Skipping invalid note data: {note_data}. Error: {e.errors()}")
                        except Exception as ex:
                            print(f"[NotesModule.load_data] Unexpected error processing note data: {note_data}. Error: {ex}")
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
        return [self.dpg_title_field_tag, self.dpg_content_field_tag]

    def _create_new_note(self, sender, app_data):
        dpg.show_item("editor_window")
        if self.editor_title is not None:
            dpg.set_value(self.editor_title, "")
        if self.editor_content is not None:
            dpg.set_value(self.editor_content, "")

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
        # Basic implementation: Get data and hide window
        # Full implementation will handle saving to self.notes and file
        note_title = ""
        note_content = ""
        if self.editor_title is not None:
            note_title = dpg.get_value(self.editor_title)
        if self.editor_content is not None:
            note_content = dpg.get_value(self.editor_content)

        print(f"Saving note. Title: '{note_title}', ID: {self.current_editing_note_id}")

        if self.current_editing_note_id:
            # Find and update existing note
            existing_note = next((n for n in self.notes if n.id == self.current_editing_note_id), None)
            if existing_note:
                existing_note.title = note_title
                existing_note.content = note_content
                existing_note.updated_at = datetime.utcnow()
                print(f"Updated existing note: {existing_note.id}")
            else:
                print(f"Error: Could not find note with ID {self.current_editing_note_id} to update.")
                # Optionally create a new one as a fallback, or show an error
                # For now, just log and proceed to save (which will save all notes including any new ones if any)
        else:
            # Create new note object
            new_note_schema = NoteCreate(title=note_title, content=note_content)
            # Convert to Note model (which includes id, created_at, updated_at)
            new_note = Note(**new_note_schema.model_dump())
            self.notes.append(new_note)
            print(f"Created new note: {new_note.id}")

        self._save_notes() # Save all notes to file
        self._refresh_sidebar_note_list() # Refresh the sidebar

        if dpg.does_item_exist("editor_window"):
            dpg.hide_item("editor_window")
        self.current_editing_note_id = None # Reset

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
                    dpg.delete_item(self.note_content_display_area_tag, children_only=True)
                    dpg.add_text(
                        "Select a note from the sidebar to view its content.",
                        parent=self.note_content_display_area_tag
                    )

        except Exception as e:
            self._show_error(f"Delete failed: {str(e)}")

    def _show_error(self, message: str):
        dpg.set_value(self.dpg_status_text_tag, message)
        dpg.configure_item(self.dpg_status_text_tag, color=(255, 0, 0))

    def _save_notes(self):
        # Use model_dump(mode='json') for Pydantic V2 to ensure datetimes are serialized to ISO strings
        notes_data = [note.model_dump(mode='json') for note in self.notes]
        # The result of model_dump(mode='json') is already a JSON-friendly dict/list structure,
        # so json.dumps will handle it correctly.
        self.data_path.write_text(json.dumps(notes_data, indent=2))
        # After saving notes, if tag filtering is active, the unique tags might have changed.
        if dpg.is_dearpygui_running() and dpg.does_item_exist(self.tag_filter_list_container_tag):
            self._refresh_tag_filter_list() # New method to update the filter UI

    def build_sidebar_view(self, sidebar_parent_tag: str):
        """Builds the note list/tree view and tag filter within the specified sidebar parent."""
        print(f"[NotesModule.build_sidebar_view] Building sidebar in parent: {sidebar_parent_tag}")

        with dpg.child_window(parent=sidebar_parent_tag, border=False, width=-1, height=-1):
            dpg.add_button(label="(+) New Note", width=-1, callback=self._create_new_note)
            dpg.add_separator()
            dpg.add_text("Filter by Tag:")
            with dpg.group(tag=self.tag_filter_list_container_tag, horizontal=False):
                pass # This will be populated by _refresh_tag_filter_list
            dpg.add_separator()
            dpg.add_spacer(height=5)
            dpg.add_text("Notes:")
            # Container for the actual list of notes, to be populated by _refresh_sidebar_note_list
            with dpg.group(tag=self.sidebar_notes_list_actual_tag):
                pass # This will be populated by _refresh_sidebar_note_list

        # Initial population
        self._refresh_tag_filter_list()
        self._refresh_sidebar_note_list()

    def _get_all_unique_tags(self) -> List[str]:
        all_tags = set()
        for note in self.notes:
            if note.tags:
                for tag in note.tags:
                    all_tags.add(tag)
        return sorted(list(all_tags), key=lambda x: x.lower()) # Case-insensitive sort

    def _refresh_tag_filter_list(self):
        if not dpg.does_item_exist(self.tag_filter_list_container_tag):
            return
        dpg.delete_item(self.tag_filter_list_container_tag, children_only=True)
        unique_tags = self._get_all_unique_tags()

        # "All Notes" selectable
        all_notes_label = "- All Notes -"
        is_all_notes_active = self.active_tag_filter is None
        with dpg.group(parent=self.tag_filter_list_container_tag):
            all_notes_selectable = dpg.add_selectable(label=all_notes_label,
                               user_data=None,
                               callback=self._on_filter_tag_selected,
                               span_columns=True)
            if is_all_notes_active:
                # Crude way to show selection: add a simple marker.
                # A theme or specific styling would be better long-term.
                dpg.set_item_label(all_notes_selectable, f"> {all_notes_label}")

        for tag in unique_tags:
            is_tag_active = self.active_tag_filter == tag
            with dpg.group(parent=self.tag_filter_list_container_tag):
                tag_selectable = dpg.add_selectable(label=tag,
                                   user_data=tag,
                                   callback=self._on_filter_tag_selected,
                                   span_columns=True)
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

        print(f"[NotesModule._on_filter_tag_selected] Active filter: {self.active_tag_filter}")
        self._refresh_sidebar_note_list()
        self._refresh_tag_filter_list() # Re-render to update selection states


    def _refresh_sidebar_note_list(self):
        if not dpg.does_item_exist(self.sidebar_notes_list_actual_tag):
            print(f"[NotesModule._refresh_sidebar_note_list] Sidebar notes list container {self.sidebar_notes_list_actual_tag} does not exist.")
            return

        dpg.delete_item(self.sidebar_notes_list_actual_tag, children_only=True)

        notes_to_display = []
        if self.active_tag_filter:
            for note in self.notes:
                if note.tags and self.active_tag_filter in note.tags:
                    notes_to_display.append(note)
        else:
            notes_to_display = self.notes # Show all notes if no filter

        if not notes_to_display:
            dpg.add_text("No notes match filter or no notes exist.", parent=self.sidebar_notes_list_actual_tag)
        else:
            first_selectable_created = False #  DEBUGGING FLAG
            for note in notes_to_display:
                note_label = note.title if note.title else "Untitled Note"
                # Assign a unique tag to the selectable for context menu identification

                current_selectable_tag = f"note_selectable_{note.id}"
                # ===== BEGIN DEBUGGING ADDITION =====
                if not first_selectable_created:
                    current_selectable_tag = "test_selectable_tag_hardcoded"
                    print(f"[NotesModule._refresh_sidebar_note_list] USING HARDCODED TAG for first item: {current_selectable_tag}")
                    first_selectable_created = True
                # ===== END DEBUGGING ADDITION =====

                dpg.add_selectable(
                    label=note_label,
                    parent=self.sidebar_notes_list_actual_tag,
                    user_data=note.id, # This is for left-click (selection)
                    callback=self._on_note_selected_from_tree,
                    tag=current_selectable_tag # Use potentially modified tag
                )

                # ===== BEGIN DEBUGGING ADDITION =====
                if not dpg.does_item_exist(current_selectable_tag):
                    print(f"[NotesModule._refresh_sidebar_note_list] CRITICAL FAILURE: Selectable item '{current_selectable_tag}' does NOT exist immediately after creation and before binding!")
                    continue # Skip binding for this non-existent item
                else:
                    print(f"[NotesModule._refresh_sidebar_note_list] CONFIRMED: Selectable item '{current_selectable_tag}' exists before binding.")
                # ===== END DEBUGGING ADDITION =====

                # Bind the handler registry to this specific selectable item
                if dpg.does_item_exist(self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG): # Use the string tag

                    # ===== BEGIN FOCUSED BINDING ATTEMPT =====
                    # Use string tag for selectable (confirmed to exist)
                    # Use integer ID 1 for handler registry (based on 'target': 1 from its __init__ info)
                    registry_hardcoded_int_id = 1

                    print(f"[NotesModule._refresh_sidebar_note_list] Attempting bind with selectable_tag (string) '{current_selectable_tag}' and registry_id (int) {registry_hardcoded_int_id}")
                    try:
                        dpg.bind_item_handler_registry(current_selectable_tag, registry_hardcoded_int_id)
                        print(f"[NotesModule._refresh_sidebar_note_list] Successfully bound '{current_selectable_tag}' to registry ID {registry_hardcoded_int_id}.")
                    except Exception as e:
                        print(f"[NotesModule._refresh_sidebar_note_list] ERROR binding '{current_selectable_tag}' to registry ID {registry_hardcoded_int_id}: {e}")
                        print(f"[NotesModule._refresh_sidebar_note_list] Falling back to binding with STRING TAGS for both as a last resort.")
                        # Fallback to original string tag method if the mixed mode fails
                        try:
                            dpg.bind_item_handler_registry(current_selectable_tag, self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG)
                            print(f"[NotesModule._refresh_sidebar_note_list] Successfully bound with STRING TAGS: '{current_selectable_tag}' to '{self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}'.")
                        except Exception as e2:
                            print(f"[NotesModule._refresh_sidebar_note_list] ERROR binding with STRING TAGS: '{current_selectable_tag}' to '{self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG}': {e2}")
                    # ===== END FOCUSED BINDING ATTEMPT =====
                else:
                    print(f"[NotesModule._refresh_sidebar_note_list] CRITICAL: Handler registry {self.NOTE_SIDEBAR_HANDLER_REGISTRY_TAG} not found.")

    def _on_note_selected_from_tree(self, sender, app_data, user_data):
        """Callback when a note is selected in the sidebar list."""
        selected_note_id = user_data
        self.currently_selected_note_id = selected_note_id # Store currently selected ID
        print(f"[NotesModule._on_note_selected_from_tree] Note selected ID: {selected_note_id}. Checking for display area tag: {self.note_content_display_area_tag}")

        # Add a small safeguard - maybe the item exists but isn't ready?
        # dpg.split_frame() # Uncomment if timing issues persist
        # dpg.sleep(0.01)   # Uncomment if timing issues persist

        if dpg.does_item_exist(self.note_content_display_area_tag):
            print(f"[NotesModule._on_note_selected_from_tree] Display area tag {self.note_content_display_area_tag} found. Clearing children.")
            dpg.delete_item(self.note_content_display_area_tag, children_only=True)

            selected_note: Optional[Note] = next((note for note in self.notes if note.id == selected_note_id), None)

            if selected_note:
                display_title = selected_note.title if selected_note.title else "Untitled Note"
                display_content = selected_note.content if selected_note.content else "[No content]"

                try:
                    created_str = selected_note.created_at.strftime("%Y-%m-%d %H:%M") if selected_note.created_at else "N/A"
                    updated_str = selected_note.updated_at.strftime("%Y-%m-%d %H:%M") if selected_note.updated_at else "N/A"
                except AttributeError:
                     created_str = str(selected_note.created_at) if selected_note.created_at else "N/A"
                     updated_str = str(selected_note.updated_at) if selected_note.updated_at else "N/A"

                # -- Top Section: Title, Metadata, Edit/Save/Cancel Buttons --
                with dpg.group(horizontal=True, parent=self.note_content_display_area_tag):
                    dpg.add_text(display_title, wrap=0)
                    # Edit button (initially visible)
                    dpg.add_button(label="Edit", tag=self.edit_button_tag, callback=self._enable_editing)
                    # Save button (initially hidden)
                    dpg.add_button(label="Save", tag=self.save_button_tag, callback=self._save_edited_note, show=False)
                    # Cancel button (initially hidden)
                    dpg.add_button(label="Cancel", tag=self.cancel_button_tag, callback=self._cancel_editing, show=False)

                dpg.add_text(f"Created: {created_str} | Updated: {updated_str}", parent=self.note_content_display_area_tag, color=(180, 180, 180))
                dpg.add_separator(parent=self.note_content_display_area_tag)

                # --- Tags Display and Editing UI ---
                dpg.add_text("Tags:", parent=self.note_content_display_area_tag)

                # Group to display current tags (will be populated dynamically)
                with dpg.group(tag=self.note_tags_display_group_tag, horizontal=True, parent=self.note_content_display_area_tag):
                    if selected_note.tags:
                        for tag_text in selected_note.tags:
                            with dpg.group(horizontal=True, parent=self.note_tags_display_group_tag):
                                dpg.add_text(f"[{tag_text}]")
                                dpg.add_button(label="(x)",
                                               user_data={"note_id": selected_note.id, "tag_to_remove": tag_text},
                                               callback=self._remove_tag_from_current_note,
                                               small=True)
                            dpg.add_spacer(width=4, parent=self.note_tags_display_group_tag) # Spacer between tag groups
                    else:
                        dpg.add_text("(No tags yet)", color=(150, 150, 150))

                # Input for adding a new tag
                with dpg.group(horizontal=True, parent=self.note_content_display_area_tag):
                    dpg.add_input_text(tag=self.new_tag_input_tag, hint="Enter new tag")
                    dpg.add_button(tag=self.add_tag_button_tag, label="Add Tag", callback=self._add_tag_to_current_note)

                dpg.add_separator(parent=self.note_content_display_area_tag) # Separator before content
                dpg.add_spacer(height=5, parent=self.note_content_display_area_tag)

                # -- Content Display/Edit Area --
                dpg.add_input_text(
                    tag=self.note_content_input_tag, # Assign specific tag
                    default_value=display_content,
                    parent=self.note_content_display_area_tag,
                    multiline=True,
                    readonly=True, # Start as read-only
                    width=-1,
                    height=-1
                )
                print(f"[NotesModule._on_note_selected_from_tree] Successfully populated display area for note {selected_note_id}.")
            else:
                 print(f"[NotesModule._on_note_selected_from_tree] Note object not found for ID {selected_note_id}.")
                 dpg.add_text(f"Error: Could not find note with ID {selected_note_id}.", parent=self.note_content_display_area_tag, color=(255,0,0))
        else:
            print(f"[NotesModule._on_note_selected_from_tree] CRITICAL Error: Content display area tag {self.note_content_display_area_tag} does not exist AFTER check!")
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
            note_to_update = next((n for n in self.notes if n.id == self.currently_selected_note_id), None)

            if note_to_update:
                note_to_update.content = new_content
                note_to_update.updated_at = datetime.utcnow() # Update timestamp
                self._save_notes() # Save the entire notes list back to JSON
                print(f"[NotesModule._save_edited_note] Note '{note_to_update.id}' saved.")
                # TODO: Refresh the displayed timestamp efficiently
                # For now, selecting the note again will show the updated time.
            else:
                print(f"[NotesModule._save_edited_note] Error: Could not find note with ID {self.currently_selected_note_id} to save.")
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
            original_note = next((n for n in self.notes if n.id == self.currently_selected_note_id), None)
            if original_note and dpg.does_item_exist(self.note_content_input_tag):
                 # Revert input field to original content
                 original_content = original_note.content if original_note.content else ""
                 dpg.set_value(self.note_content_input_tag, original_content)
                 print(f"[NotesModule._cancel_editing] Reverted content for note '{original_note.id}'.")
            elif not original_note:
                 print(f"[NotesModule._cancel_editing] Error: Could not find note with ID {self.currently_selected_note_id} to revert content.")
            # If input tag doesn't exist, we can't revert, but still disable editing

        except Exception as e:
            print(f"[NotesModule._cancel_editing] Exception during cancel: {e}")
        finally:
             # Always disable editing mode after attempt
             self._disable_editing(revert_changes=True) # Pass True for clarity, though value isn't used in disable

    def _disable_editing(self, revert_changes: bool):
        """Make content read-only and swap buttons back."""
        # Note: Revert logic is handled by caller (_cancel_editing) for now
        print(f"[NotesModule._disable_editing] Disabling edit mode. Revert: {revert_changes}")

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

        selected_note = next((note for note in self.notes if note.id == self.currently_selected_note_id), None)
        if not selected_note:
            print(f"[NotesModule._add_tag_to_current_note] Selected note with ID {self.currently_selected_note_id} not found.")
            return

        if not hasattr(selected_note, 'tags') or selected_note.tags is None:
            selected_note.tags = [] # Initialize if somehow missing

        if new_tag_text.lower() not in [t.lower() for t in selected_note.tags]: # Case-insensitive check
            selected_note.tags.append(new_tag_text)
            selected_note.updated_at = datetime.utcnow() # Update note's timestamp
            self._save_notes()
            dpg.set_value(self.new_tag_input_tag, "") # Clear input field
            self._refresh_displayed_tags(selected_note) # Update the UI
            print(f"[NotesModule._add_tag_to_current_note] Tag '{new_tag_text}' added to note '{selected_note.id}'.")
        else:
            print(f"[NotesModule._add_tag_to_current_note] Tag '{new_tag_text}' already exists on note '{selected_note.id}'.")
            dpg.set_value(self.new_tag_input_tag, "") # Still clear input

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
                    dpg.add_button(label="(x)",
                                   user_data={"note_id": note.id, "tag_to_remove": tag_text},
                                   callback=self._remove_tag_from_current_note,
                                   small=True) # Make button small
                dpg.add_spacer(width=4, parent=parent_group) # Spacer between tag groups
        else:
            dpg.add_text("(No tags yet)", color=(150, 150, 150), parent=parent_group)

    def _remove_tag_from_current_note(self, sender, app_data, user_data):
        if not user_data or "note_id" not in user_data or "tag_to_remove" not in user_data:
            print("[NotesModule._remove_tag_from_current_note] Invalid user_data.")
            return

        note_id = user_data["note_id"]
        tag_to_remove = user_data["tag_to_remove"]

        if self.currently_selected_note_id != note_id:
            print(f"[NotesModule._remove_tag_from_current_note] Mismatch: current note {self.currently_selected_note_id}, tag removal for {note_id}")
            # This shouldn't happen if UI is refreshed correctly but good to check.
            return

        selected_note = next((n for n in self.notes if n.id == note_id), None)

        if not selected_note:
            print(f"[NotesModule._remove_tag_from_current_note] Note with ID {note_id} not found.")
            return

        if not hasattr(selected_note, 'tags') or selected_note.tags is None:
            print(f"[NotesModule._remove_tag_from_current_note] Note {note_id} has no tags attribute or it's None.")
            return # Nothing to remove

        # Case-insensitive removal
        tag_to_remove_lower = tag_to_remove.lower()
        original_length = len(selected_note.tags)
        selected_note.tags = [t for t in selected_note.tags if t.lower() != tag_to_remove_lower]

        if len(selected_note.tags) < original_length:
            selected_note.updated_at = datetime.utcnow()
            self._save_notes()
            self._refresh_displayed_tags(selected_note)
            print(f"[NotesModule._remove_tag_from_current_note] Tag '{tag_to_remove}' removed from note '{note_id}'.")
        else:
            print(f"[NotesModule._remove_tag_from_current_note] Tag '{tag_to_remove}' not found on note '{note_id}'.")

    def _handle_note_sidebar_click(self, sender, app_data):
        # app_data is [mouse_button, item_clicked_tag]
        mouse_button = app_data[0]
        item_clicked_tag_any = app_data[1] # item_clicked_tag can be int or str

        item_clicked_tag = str(item_clicked_tag_any) # Ensure string for prefix check

        # We only care about right-clicks on our specific note selectables
        if mouse_button == dpg.mvMouseButton_Right and item_clicked_tag.startswith("note_selectable_"):
            self.context_menu_active_note_id = item_clicked_tag.replace("note_selectable_", "", 1)
            print(f"[NotesModule._handle_note_sidebar_click] Right-click on note ID: {self.context_menu_active_note_id}")

            # Clear previous items and populate context menu
            dpg.delete_item(self.note_context_menu_tag, children_only=True)

            dpg.add_menu_item(label="Open/Edit", parent=self.note_context_menu_tag, callback=self._context_open_note)
            dpg.add_menu_item(label="Rename", parent=self.note_context_menu_tag, callback=self._context_rename_note_setup)
            dpg.add_menu_item(label="Delete", parent=self.note_context_menu_tag, callback=self._context_delete_note_from_context)

            # Position and show the context menu
            # Ensure main window is active for positioning, or use absolute screen coords if available for mouse.
            # dpg.split_frame() # may help if get_mouse_pos() is stale
            mouse_pos = dpg.get_mouse_pos(local=False) # Get screen mouse position
            dpg.configure_item(self.note_context_menu_tag, pos=mouse_pos, show=True)
        elif dpg.is_item_shown(self.note_context_menu_tag) and mouse_button == dpg.mvMouseButton_Left:
            # Hide context menu if a left click happens anywhere else while it's open
            # More robust would be to check if the click is outside the menu bounds.
            dpg.configure_item(self.note_context_menu_tag, show=False)
            self.context_menu_active_note_id = None # Clear active ID

    def _context_open_note(self, sender, app_data, user_data):
        if self.context_menu_active_note_id:
            note = next((n for n in self.notes if n.id == self.context_menu_active_note_id), None)
            if note:
                self._open_editor(note)
        dpg.configure_item(self.note_context_menu_tag, show=False)
        self.context_menu_active_note_id = None

    def _context_rename_note_setup(self, sender, app_data, user_data):
        if self.context_menu_active_note_id:
            note = next((n for n in self.notes if n.id == self.context_menu_active_note_id), None)
            if note:
                dpg.set_value(self.rename_note_input_tag, note.title if note.title else "")
                dpg.configure_item(self.rename_note_window_tag, show=True)
        dpg.configure_item(self.note_context_menu_tag, show=False)
        # self.context_menu_active_note_id remains set until rename is confirmed or cancelled

    def _context_rename_note_execute(self, sender, app_data, user_data):
        if self.context_menu_active_note_id:
            new_title = dpg.get_value(self.rename_note_input_tag)
            note_to_rename = next((n for n in self.notes if n.id == self.context_menu_active_note_id), None)
            if note_to_rename:
                note_to_rename.title = new_title
                note_to_rename.updated_at = datetime.utcnow()
                self._save_notes()
                self._refresh_sidebar_note_list()
                # If this note is currently displayed in the main area, refresh that too
                if self.currently_selected_note_id == self.context_menu_active_note_id:
                    self._on_note_selected_from_tree(sender=None, app_data=None, user_data=self.context_menu_active_note_id)
            print(f"Note {self.context_menu_active_note_id} renamed to '{new_title}'")
        dpg.configure_item(self.rename_note_window_tag, show=False)
        self.context_menu_active_note_id = None # Clear after operation

    def _context_delete_note_from_context(self, sender, app_data, user_data):
        if self.context_menu_active_note_id:
            self._delete_note(self.context_menu_active_note_id)
            # _delete_note now calls _refresh_sidebar_note_list and handles clearing display if needed
        dpg.configure_item(self.note_context_menu_tag, show=False)
        self.context_menu_active_note_id = None

# Removed old Flet-specific methods if any were left (none were visible in snippet)
# Ensure all methods are now DPG specific or data logic.

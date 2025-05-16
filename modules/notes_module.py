import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import dearpygui.dearpygui as dpg
from pydantic import ValidationError

from schemas import (  # Ensure these are in schemas/note_schemas.py or similar
    Note,
    NoteCreate,
)

from .base_module import BaseModule
from .notes_ui_utils import NotesDialogManager

if TYPE_CHECKING:
    from core.app import Core  # For type hinting Core instance


class NotesModule(BaseModule):
    MODULE_NAME = "Notes"
    MODULE_TAG = "notes_module"

    ICON_NOTE_DEFAULT = "[N]"
    ICON_FOLDER_DEFAULT = "[F]"
    ICON_ROOT = "[R]"
    ROOT_SENTINEL_VALUE = "__root_level_note__"  # For dropdowns indicating root

    def __init__(self, core: "Core"):
        super().__init__(core)
        self.module_tag = self.__class__.MODULE_TAG
        self.logger.info(
            f"Initializing {self.name} module ({self.module_tag})...")
        # Temporarily force logger level for this module to DEBUG
        import logging

        self.logger.setLevel(logging.DEBUG)
        self.logger.debug(
            f"{self.name} logger level forced to DEBUG for this session.")

        self.notes: List[Note] = []
        self.notes_data_index: Dict[str, Note] = {}
        self.all_tags: set[str] = set()

        self.current_editing_note_id: Optional[str] = None
        self.active_tag_filter: Optional[str] = None
        self.currently_selected_sidebar_note_id: Optional[str] = None

        self.pending_new_item_parent_id: Optional[str] = (
            None  # For context menu creation
        )
        self.pending_new_item_is_folder: bool = False

        # Data path
        self.data_path = self.core.config.notes_path  # Get from AppConfig via Core
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        # UI Managers
        self.dialog_manager = NotesDialogManager(
            self,
        )  # Pass self (NotesModule instance)

        # --- DPG Tags ---
        # Sidebar
        self.sidebar_list_tag = f"{self.module_tag}_sidebar_list_actual_group"
        self.create_note_button_tag = f"{self.module_tag}_create_note_btn"
        self.create_folder_button_tag = f"{self.module_tag}_create_folder_btn"
        self.tag_filter_input_tag = f"{self.module_tag}_tag_filter_input"

        # Editor Window (reusable pop-up)
        self.editor_window_tag = f"{self.module_tag}_editor_window"
        self.editor_title_input_tag = f"{self.module_tag}_editor_title_input"
        self.editor_content_input_tag = f"{self.module_tag}_editor_content_input"
        self.editor_tags_input_tag = f"{self.module_tag}_editor_tags_input"
        self.editor_save_button_tag = f"{self.module_tag}_editor_save_button"
        self.editor_close_button_tag = f"{self.module_tag}_editor_close_button"

        # Context Menu
        self.context_menu_tag = f"{self.module_tag}_context_menu"
        self.context_menu_active_item_id: Optional[str] = (
            None  # ID of item right-clicked
        )

        # Main content area (placeholder for now, editor is a window)
        self.main_content_area_tag = f"{self.module_tag}_main_content_area"

        self._define_editor_window()  # Define it once

        self.load_data()
        self.logger.info(
            f"{self.name} module initialized with {len(self.notes)} notes/folders.",
        )

    def _define_editor_window(self):
        if dpg.does_item_exist(self.editor_window_tag):
            return  # Already defined

        with dpg.window(  # Corrected: content needs to be inside this 'with'
            label="Note Editor",
            tag=self.editor_window_tag,
            width=700,
            height=550,
            show=False,  # Initially hidden
            on_close=self._on_editor_window_close,
            no_collapse=True,
            pos=[200, 100],  # Initial position
        ):
            dpg.add_input_text(
                label="Title", tag=self.editor_title_input_tag, width=-1)
            dpg.add_input_text(
                label="Tags (comma-sep)",
                tag=self.editor_tags_input_tag,
                width=-1,
            )
            dpg.add_input_text(
                label="Content",
                tag=self.editor_content_input_tag,
                multiline=True,
                width=-1,
                height=-75,  # Leave space for buttons
                tab_input=True,
            )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save",
                    tag=self.editor_save_button_tag,
                    callback=self._save_note_from_editor,
                    width=100,
                )
                dpg.add_button(
                    label="Close",
                    tag=self.editor_close_button_tag,
                    callback=self._on_editor_window_close,
                    width=100,
                )
        self.logger.debug(f"Editor window '{self.editor_window_tag}' defined.")

    def load_data(self):
        self.logger.info(f"Loading notes from {self.data_path}")
        self.notes = []
        try:
            if self.data_path.exists():
                with open(self.data_path, encoding="utf-8") as f:
                    notes_data_from_file = json.load(f)
                    for i, item_dict in enumerate(notes_data_from_file):
                        try:
                            item_id = item_dict.get("id", str(uuid.uuid4()))
                            item_dict["id"] = item_id
                            item_dict.setdefault(
                                "title",
                                f"Untitled Item {item_id[:8]}",
                            )
                            item_dict.setdefault("content", "")
                            item_dict.setdefault("tags", [])
                            # Handle parent_id sentinel values before validation
                            parent_id_val = item_dict.get("parent_id")
                            if (
                                parent_id_val == self.ROOT_SENTINEL_VALUE
                                or parent_id_val == "__MOVE_TO_ROOT__"
                            ):
                                item_dict["parent_id"] = None
                            else:
                                item_dict.setdefault(
                                    "parent_id",
                                    None,
                                )  # Ensure it's None if not present or not a sentinel

                            item_dict.setdefault("order", i)
                            # Force override to default icons from the class
                            is_folder = item_dict.get(
                                "is_folder",
                                False,
                            )  # ensure is_folder is determined first
                            item_dict["icon"] = (
                                self.ICON_FOLDER_DEFAULT
                                if is_folder
                                else self.ICON_NOTE_DEFAULT
                            )
                            item_dict.setdefault(
                                "created_at",
                                datetime.now(timezone.utc).isoformat(),
                            )
                            item_dict.setdefault(
                                "updated_at",
                                datetime.now(timezone.utc).isoformat(),
                            )

                            note_obj = Note(**item_dict)
                            self.notes.append(note_obj)
                        except ValidationError as ve:
                            self.logger.error(
                                f"Validation error for item data: {item_dict.get('id', 'Unknown ID')}. Details: {ve}. Skipping.",
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Error parsing item data: {item_dict.get('id', 'Unknown ID')}. Error: {e}. Skipping.",
                            )
                self.logger.info(
                    f"Successfully loaded {len(self.notes)} items.")
            else:
                self.logger.info(
                    f"Notes file not found: {self.data_path}. Starting empty, will create file on first save.",
                )
                self.notes = []
        except json.JSONDecodeError:
            self.logger.error(
                f"Error decoding JSON from {self.data_path}. File might be corrupted. Starting empty.",
            )
            self.notes = []
        except Exception as e:
            self.logger.error(
                f"Unexpected error during load_data: {e}. Starting empty.",
            )
            self.notes = []

        self._update_internal_structures()

    def _save_notes(self):
        self.logger.info(f"Saving {len(self.notes)} items to {self.data_path}")
        try:
            # Ensure notes are sorted by order before saving to maintain structure implicitly
            # if items are ever loaded without relying on parent_id for ordering.
            # For now, we rely on parent_id and then title for sorting in display.
            # notes_to_save_sorted = sorted(self.notes, key=lambda n: (n.parent_id or "", n.order, n.title.lower()))
            # notes_to_save = [note.model_dump(mode="json") for note in notes_to_save_sorted]
            notes_to_save = [note.model_dump(mode="json")
                             for note in self.notes]
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(notes_to_save, f, indent=4)
            self.logger.debug("Notes saved successfully.")
        except Exception as e:
            self.logger.error(
                f"Failed to save notes to {self.data_path}: {e}",
                exc_info=True,
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Critical Error: Failed to save notes! Check logs.",
                    duration=10,
                    level="error",
                )

    def _update_internal_structures(self):
        self.logger.debug(
            f"Updating internal structures. Notes count: {len(self.notes)}",
        )
        self.notes_data_index = {note.id: note for note in self.notes}

        current_tags = set()
        for note in self.notes:
            if note.tags and isinstance(note.tags, list):
                for tag in note.tags:
                    if isinstance(tag, str):
                        current_tags.add(tag.strip())
        self.all_tags = {t for t in current_tags if t}

        self._populate_available_folders_for_dialog_manager()
        self.logger.debug(
            f"Internal structures updated. Index size: {len(self.notes_data_index)}, Unique tags: {len(self.all_tags)}",
        )

    def _populate_available_folders_for_dialog_manager(self):
        # This list is used by DialogManager to populate its dropdowns
        self.dialog_manager.available_folders_for_dropdown = [
            (f"{self.ICON_ROOT} Root", self.ROOT_SENTINEL_VALUE),
        ]
        sorted_folders = sorted(
            [note for note in self.notes if note.is_folder],
            key=lambda f: f.title.lower(),
        )
        for folder in sorted_folders:
            self.dialog_manager.available_folders_for_dropdown.append(
                (f"{folder.icon} {folder.title}", folder.id),
            )
        self.logger.debug(
            f"Populated available folders for DialogManager: {len(self.dialog_manager.available_folders_for_dropdown)} items.",
        )
        # Tell dialog manager to update DPG items
        self.dialog_manager.refresh_dropdown_items_in_dialogs()

    # --- UI Building ---
    def build_dpg_view(self, parent_container_tag: Union[int, str]):
        self.logger.debug(
            f"Building main DPG view in parent: {parent_container_tag}")
        with dpg.group(parent=parent_container_tag, tag=self.main_content_area_tag):
            dpg.add_text(
                "Select a note or folder from the sidebar.",
                tag=dpg.generate_uuid(),
            )

    def build_sidebar_view(self, parent_tag: Union[int, str]):
        self.logger.debug(
            f"Building sidebar view for {self.name} in parent: {parent_tag}",
        )
        with dpg.group(
            tag=f"{self.module_tag}_sidebar_content_group",
            parent=parent_tag,
        ):
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="New Note",
                    tag=self.create_note_button_tag,
                    callback=self._create_new_note_action,
                    width=-1,
                )
                dpg.add_button(
                    label="New Folder",
                    tag=self.create_folder_button_tag,
                    callback=self._create_new_folder_action,
                    width=-1,
                )
            dpg.add_input_text(
                label="Filter Tags",
                tag=self.tag_filter_input_tag,
                callback=self._apply_tag_filter_from_input,
                hint="tag1, tag2 (Enter to filter)",
                width=-1,
                tracked=True,
                track_offset=0.5,  # Make it slightly less sensitive
            )
            dpg.add_spacer(height=5)
            # This group will hold the dynamically generated list/tree of notes/folders
            with dpg.child_window(
                tag=self.sidebar_list_tag,
                border=False,
                width=-1,
                height=-1,
            ):  # Use child_window for better scrolling
                # Initial population
                self._refresh_sidebar_list()

        # Define the context menu once
        with dpg.menu(tag=self.context_menu_tag, show=False):
            # Items will be added dynamically in _handle_sidebar_item_right_click
            pass

        self.logger.debug(f"Sidebar view for {self.name} built.")

    def _refresh_sidebar_list(self):
        self.logger.info(f"Refreshing sidebar. Items: {len(self.notes)}.")
        if not dpg.does_item_exist(self.sidebar_list_tag):
            self.logger.error(
                f"Sidebar list tag '{self.sidebar_list_tag}' does not exist. Cannot refresh.",
            )
            return

        # Clear existing items
        dpg.delete_item(self.sidebar_list_tag, children_only=True)

        # Debug: Add a marker to see if this part is reached and the container is visible
        # dpg.add_text("--- Notes List Container Re-rendered ---", parent=self.sidebar_list_tag, color=[0, 255, 0])

        if not self.notes:
            dpg.add_text("No notes yet.", parent=self.sidebar_list_tag)
            self.logger.debug("No notes to display in sidebar.")
            return

        # Prepare data for tree building: group items by their parent_id
        items_by_parent: Dict[Optional[str], List[Note]] = {}
        for note in self.notes:
            items_by_parent.setdefault(note.parent_id, []).append(note)

        # Sort items within each parent group by title (and folders first)
        for parent_id in items_by_parent:
            items_by_parent[parent_id].sort(
                key=lambda x: (not x.is_folder, x.title.lower()),
            )

        # Build the tree starting from root items (parent_id is None)
        self._build_sidebar_tree_recursive(
            dpg_parent_tag=self.sidebar_list_tag,
            current_item_parent_id=None,
            items_by_parent=items_by_parent,
        )
        self.logger.debug("Sidebar refresh complete.")

    def _build_sidebar_tree_recursive(
        self,
        dpg_parent_tag: Union[int, str],
        current_item_parent_id: Optional[str],
        items_by_parent: Dict[Optional[str], List[Note]],
    ):
        # Get children of the current_item_parent_id
        children = items_by_parent.get(current_item_parent_id, [])

        if not children:
            if (
                current_item_parent_id is not None
            ):  # Only add "empty" if it's a folder, not root
                pass  # No "empty" message for now, cleaner UI
            return

        for item in children:
            # Ensure this critical log line is active and correct
            self.logger.debug(
                f"_build_sidebar_tree_recursive: Processing item ID: {item.id}, Title: '{item.title}', Icon: '{item.icon}', IsFolder: {item.is_folder}",
            )
            # DIRECT PRINT FOR DEBUGGING ICON VALUE - Can be removed or commented out now
            # print(f"DIRECT PRINT - Icon for {item.title}: '{item.icon}'")

            # Reverted to original label to use item.icon
            label = f"{item.icon} {item.title}"
            # label = f"NOTE: {item.title}" # Simplified label for debugging - KEEP THIS FOR NOW
            self.logger.debug(
                f"_build_sidebar_tree_recursive: Generated label: '{label}'",
            )
            item_tag = f"sidebar_item_{item.id}"

            # Explicitly delete existing handler registry for this item_tag before recreating
            handler_registry_tag = f"{item_tag}_handler_registry"
            if dpg.does_item_exist(handler_registry_tag):
                dpg.delete_item(handler_registry_tag)

            if item.is_folder:
                # For folders, use a tree node
                with dpg.tree_node(
                    label=label,
                    tag=item_tag,
                    parent=dpg_parent_tag,
                    default_open=False,
                ):
                    # Attach handlers to the tree node itself
                    with dpg.item_handler_registry(tag=handler_registry_tag):
                        dpg.add_item_clicked_handler(
                            button=dpg.mvMouseButton_Left,
                            callback=self._handle_sidebar_item_left_click,
                            user_data=item.id,
                        )
                        dpg.add_item_clicked_handler(
                            button=dpg.mvMouseButton_Right,
                            callback=self._handle_sidebar_item_right_click,
                            user_data=item.id,
                        )
                    dpg.bind_item_handler_registry(
                        item_tag,
                        handler_registry_tag,
                    )

                    # Recursively build the tree for children of this folder
                    self._build_sidebar_tree_recursive(
                        dpg_parent_tag=item_tag,  # Children are parented to this tree_node
                        current_item_parent_id=item.id,
                        items_by_parent=items_by_parent,
                    )
            else:
                # For notes, use a selectable
                # Make sure the selectable is parented correctly to dpg_parent_tag
                selectable_item = dpg.add_selectable(
                    label=label,
                    tag=item_tag,
                    parent=dpg_parent_tag,  # Explicitly parent here
                    user_data=item.id,  # Store note_id for callback
                    span_columns=True,  # Make it span full width if in a table/tree
                )
                # Attach handlers to the selectable
                # Explicitly delete existing handler registry for this item_tag before recreating (already done above, but ensure context)
                # handler_registry_tag = f"{item_tag}_handler_registry" # Redundant declaration
                # if dpg.does_item_exist(handler_registry_tag): # Check already performed
                #    dpg.delete_item(handler_registry_tag)

                with dpg.item_handler_registry(
                    tag=handler_registry_tag,
                ):  # Use the defined handler_registry_tag
                    dpg.add_item_clicked_handler(
                        button=dpg.mvMouseButton_Left,
                        callback=self._handle_sidebar_item_left_click,
                        user_data=item.id,
                    )
                    dpg.add_item_clicked_handler(
                        button=dpg.mvMouseButton_Right,
                        callback=self._handle_sidebar_item_right_click,
                        user_data=item.id,
                    )
                dpg.bind_item_handler_registry(item_tag, handler_registry_tag)

            # Highlight if selected
            # Simplified placeholder for highlighting logic

    def _create_new_note_action(self, sender=None, app_data=None, user_data=None):
        self.logger.debug("'_create_new_note_action' triggered.")
        self.pending_new_item_parent_id = self.ROOT_SENTINEL_VALUE  # Default to root
        self.pending_new_item_is_folder = False
        self.dialog_manager.show_new_item_dialog(
            is_folder=False,
            parent_id_to_select=self.ROOT_SENTINEL_VALUE,
        )

    def _create_new_folder_action(self, sender=None, app_data=None, user_data=None):
        self.logger.debug("'_create_new_folder_action' triggered.")
        self.pending_new_item_parent_id = self.ROOT_SENTINEL_VALUE  # Default to root
        self.pending_new_item_is_folder = True
        self.dialog_manager.show_new_item_dialog(
            is_folder=True,
            parent_id_to_select=self.ROOT_SENTINEL_VALUE,
        )

    def execute_create_new_item(
        self,
        title: str,
        icon: Optional[str],  # Icon is now managed by is_folder
        chosen_parent_id_from_dropdown: Optional[str],
        is_folder: bool,
    ):
        self.logger.info(
            f"Executing create new item: Title='{title}', IsFolder={is_folder}, ParentID='{chosen_parent_id_from_dropdown}'",
        )
        if not title.strip():
            self.logger.warning("New item title is empty. Aborting creation.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Title cannot be empty!",
                    duration=3,
                    level="warning",
                )
            return

        actual_parent_id: Optional[str] = None
        if (
            chosen_parent_id_from_dropdown
            and chosen_parent_id_from_dropdown != self.ROOT_SENTINEL_VALUE
        ):
            actual_parent_id = chosen_parent_id_from_dropdown
            # Ensure parent exists and is a folder
            parent_item = self.get_item_by_id(actual_parent_id)
            if not parent_item or not parent_item.is_folder:
                self.logger.error(
                    f"Invalid parent ID '{actual_parent_id}' or parent is not a folder. Defaulting to root.",
                )
                actual_parent_id = None  # Default to root if parent is invalid
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Invalid parent folder selected. Item created at root.",
                        duration=5,
                        level="warning",
                    )

        # Determine order: append to children of the parent, or to root items
        sibling_items = [
            item for item in self.notes if item.parent_id == actual_parent_id
        ]
        new_order = len(sibling_items)

        timestamp = datetime.now(timezone.utc)
        new_item_id = str(uuid.uuid4())

        default_icon = self.ICON_FOLDER_DEFAULT if is_folder else self.ICON_NOTE_DEFAULT

        try:
            new_note_data = NoteCreate(
                id=new_item_id,
                title=title.strip(),
                content="",  # Empty content for new notes/folders
                tags=[],
                parent_id=actual_parent_id,
                is_folder=is_folder,
                order=new_order,
                icon=default_icon,  # Use default icon based on type
                # created_at and updated_at will be set by Pydantic model default_factory
            )
            # Create the Note Pydantic model instance
            # Pydantic will use default_factory for created_at and updated_at
            new_note = Note(**new_note_data.model_dump())

            self.notes.append(new_note)
            # This will update index and tags, and repopulate dialog manager folders
            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()  # Update the UI

            self.logger.info(
                f"Successfully created new {'folder' if is_folder else 'note'}: ID={new_note.id}, Title='{new_note.title}', ParentID='{new_note.parent_id}'.",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"{'Folder' if is_folder else 'Note'} '{new_note.title}' created.",
                    duration=3,
                    level="success",
                )
        except ValidationError as ve:
            self.logger.error(
                f"Validation error creating new item: {ve}",
                exc_info=True,
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error creating item: {ve}",
                    duration=5,
                    level="error",
                )
        except Exception as e:
            self.logger.error(
                f"Unexpected error creating new item: {e}",
                exc_info=True,
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "An unexpected error occurred. See logs.",
                    duration=5,
                    level="error",
                )

    def _open_editor_for_note(self, note_id: str):
        self.logger.debug(f"Opening editor for note ID: {note_id}")
        note_to_edit = self.notes_data_index.get(note_id)

        if not note_to_edit:
            self.logger.error(
                f"Note not found: {note_id}. Cannot open editor.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: Note {note_id} not found!",
                    level="error",
                )
            return
        if note_to_edit.is_folder:
            self.logger.warning(
                f"Attempted to open folder '{note_to_edit.title}' in note editor. Aborted.",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Cannot edit folder '{note_to_edit.title}' as a note.",
                    level="warning",
                )
            return

        self.current_editing_note_id = note_id
        editor_label = f"Edit Note: {note_to_edit.title[:40]}{'...' if len(note_to_edit.title) > 40 else ''}"

        dpg.set_value(self.editor_title_input_tag, note_to_edit.title)
        dpg.set_value(
            self.editor_content_input_tag,
            note_to_edit.content if note_to_edit.content else "",
        )
        dpg.set_value(
            self.editor_tags_input_tag,
            ", ".join(note_to_edit.tags) if note_to_edit.tags else "",
        )

        dpg.configure_item(self.editor_window_tag,
                           label=editor_label, show=True)
        dpg.focus_item(self.editor_content_input_tag)
        self.logger.info(
            f"Editor opened for note: '{note_to_edit.title}' (ID: {note_id}).",
        )

    def _save_note_from_editor(self, sender=None, app_data=None, user_data=None):
        if self.current_editing_note_id is None:
            self.logger.warning(
                "Save attempt from editor but no note ID is being edited.",
            )
            return

        note_to_edit = self.get_item_by_id(self.current_editing_note_id)
        if not note_to_edit:
            self.logger.error(
                f"Cannot save: Note with ID '{self.current_editing_note_id}' not found.",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Note not found for editing.",
                    duration=3,
                    level="error",
                )
            dpg.configure_item(self.editor_window_tag,
                               show=False)  # Close editor
            return

        new_title = dpg.get_value(self.editor_title_input_tag)
        new_content = dpg.get_value(self.editor_content_input_tag)
        new_tags_str = dpg.get_value(self.editor_tags_input_tag)
        new_tags = [tag.strip()
                    for tag in new_tags_str.split(",") if tag.strip()]

        if not new_title.strip():
            self.logger.warning("Note title cannot be empty during save.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Title cannot be empty!",
                    duration=3,
                    level="warning",
                )
            # Do not close editor, let user fix it
            return

        try:
            update_data = {
                "title": new_title.strip(),
                "content": new_content,
                "tags": new_tags,
                "updated_at": datetime.now(timezone.utc),  # Update timestamp
                # id, parent_id, is_folder, order, icon, created_at remain unchanged during simple edit
            }
            # Create a new Note object with updated fields
            # This uses Pydantic's update-like mechanism via model_copy
            updated_note = note_to_edit.model_copy(update=update_data)

            # Replace the old note object with the updated one in self.notes
            note_index = -1
            for i, n in enumerate(self.notes):
                if n.id == self.current_editing_note_id:
                    note_index = i
                    break

            if note_index != -1:
                self.notes[note_index] = updated_note
            else:  # Should not happen if note_to_edit was found
                self.logger.error(
                    f"Note {self.current_editing_note_id} was in index but not in self.notes list during save.",
                )
                # Fallback: append if somehow missing
                self.notes.append(updated_note)

            self._update_internal_structures()  # Update index and tags
            self._save_notes()
            self._refresh_sidebar_list()  # Update UI

            self.logger.info(f"Note '{updated_note.id}' updated successfully.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Note '{updated_note.title}' saved.",
                    duration=3,
                    level="success",
                )
            dpg.configure_item(
                self.editor_window_tag,
                show=False,
            )  # Close editor on successful save
            self.current_editing_note_id = None

        except ValidationError as ve:
            self.logger.error(
                f"Validation error updating note: {ve}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error saving note: {ve}",
                    duration=5,
                    level="error",
                )
        except Exception as e:
            self.logger.error(
                f"Unexpected error saving note: {e}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "An unexpected error occurred while saving. See logs.",
                    duration=5,
                    level="error",
                )

    def _on_editor_window_close(self, sender=None, app_data=None, user_data=None):
        self.logger.debug(
            f"Editor window closed. Current editing ID was: {self.current_editing_note_id}",
        )
        # TODO: Check for unsaved changes
        if dpg.does_item_exist(
            self.editor_window_tag,
        ):  # Ensure it exists before trying to hide
            dpg.configure_item(self.editor_window_tag, show=False)
        self.current_editing_note_id = None

    # --- Interaction Handlers ---
    def _handle_sidebar_item_left_click(self, sender, app_data, item_id: str):
        self.logger.debug(f"Sidebar item left-clicked. Item ID: {item_id}")
        item = self.notes_data_index.get(item_id)
        if item:
            if item.is_folder:
                self.logger.debug(
                    f"Folder '{item.title}' clicked. DPG Tree_Node handles expansion.",
                )
                # If a folder is clicked, we might want to deselect any selected note
                if self.currently_selected_sidebar_note_id is not None:
                    self.currently_selected_sidebar_note_id = None
                    self._refresh_sidebar_list()  # Refresh to unhighlight note
            else:  # It's a note
                self.logger.info(
                    f"Note '{item.title}' selected. Opening in editor.")
                self.currently_selected_sidebar_note_id = (
                    item_id  # Set current selection
                )
                self._open_editor_for_note(item_id)
                self._refresh_sidebar_list()  # Refresh to highlight this note and unhighlight others
        else:
            self.logger.warning(
                f"Selected item_id '{item_id}' not found in index.")
            # If an invalid item was somehow clicked, clear selection
            if self.currently_selected_sidebar_note_id is not None:
                self.currently_selected_sidebar_note_id = None
                self._refresh_sidebar_list()

    def _handle_sidebar_item_right_click(self, sender, app_data, item_id: str):
        self.logger.debug(f"Sidebar item right-clicked. Item ID: {item_id}")
        self.context_menu_active_item_id = item_id
        item = self.notes_data_index.get(item_id)
        if not item:
            self.logger.error(
                f"Cannot show context menu: Item {item_id} not found.")
            return

        if not dpg.does_item_exist(self.context_menu_tag):
            with dpg.window(
                popup=True,
                tag=self.context_menu_tag,
                autosize=True,
                no_title_bar=True,
                show=False,
                no_move=True,
            ):  # no_move to prevent dragging context menu
                pass

        dpg.delete_item(self.context_menu_tag, children_only=True)

        if not item.is_folder:
            dpg.add_menu_item(
                label="Open/Edit",
                callback=self._context_open_edit_action,
                user_data=item_id,
                parent=self.context_menu_tag,
            )

        dpg.add_menu_item(
            label="Rename...",
            callback=self._context_rename_action,
            user_data=item_id,
            parent=self.context_menu_tag,
        )
        dpg.add_menu_item(
            label="Delete...",
            callback=self._context_delete_action,
            user_data=item_id,
            parent=self.context_menu_tag,
        )

        dpg.add_separator(parent=self.context_menu_tag)
        if item.is_folder:
            dpg.add_menu_item(
                label="New Note Here",
                callback=self._context_new_note_in_folder_action,
                user_data=item_id,
                parent=self.context_menu_tag,
            )
            dpg.add_menu_item(
                label="New Subfolder Here",
                callback=self._context_new_folder_in_folder_action,
                user_data=item_id,
                parent=self.context_menu_tag,
            )

        # dpg.add_menu_item(label="Move To...", callback=self._context_move_action, user_data=item_id, parent=self.context_menu_tag, enabled=False) # TODO

        dpg.configure_item(self.context_menu_tag, show=True)

    # --- Context Menu Actions ---
    def _context_open_edit_action(self, sender, app_data, item_id: str):
        self.logger.debug(f"Context menu: Open/Edit for {item_id}")
        self._open_editor_for_note(item_id)  # This handles notes only

    def _context_rename_action(self, sender, app_data, item_id: str):
        self.logger.debug(f"Context menu: Rename for {item_id}")
        item = self.notes_data_index.get(item_id)
        if item and hasattr(self.dialog_manager, "show_rename_item_dialog"):
            self.dialog_manager.show_rename_item_dialog(item)
        elif hasattr(self.core, "gui_manager") and self.core.gui_manager:
            self.core.gui_manager.show_toast(
                f"Error: Item {item_id} not found for rename.",
                level="error",
            )

    def _context_delete_action(self, sender, app_data, item_id: str):
        self.logger.debug(f"Context menu: Delete for {item_id}")
        item = self.notes_data_index.get(item_id)
        if item and hasattr(self.dialog_manager, "show_delete_confirmation_dialog"):
            self.dialog_manager.show_delete_confirmation_dialog(item)
        elif hasattr(self.core, "gui_manager") and self.core.gui_manager:
            self.core.gui_manager.show_toast(
                f"Error: Item {item_id} not found for delete.",
                level="error",
            )

    def _context_new_note_in_folder_action(
        self,
        sender,
        app_data,
        parent_folder_id: str,
    ):
        self.logger.debug(
            f"Context menu: New Note in folder {parent_folder_id}")
        self.pending_new_item_parent_id = parent_folder_id
        self.pending_new_item_is_folder = False
        if hasattr(self.dialog_manager, "show_new_item_dialog"):
            self.dialog_manager.show_new_item_dialog(
                is_folder=False,
                parent_id_override=parent_folder_id,
            )

    def _context_new_folder_in_folder_action(
        self,
        sender,
        app_data,
        parent_folder_id: str,
    ):
        self.logger.debug(
            f"Context menu: New Subfolder in folder {parent_folder_id}")
        self.pending_new_item_parent_id = parent_folder_id
        self.pending_new_item_is_folder = True
        if hasattr(self.dialog_manager, "show_new_item_dialog"):
            self.dialog_manager.show_new_item_dialog(
                is_folder=True,
                parent_id_override=parent_folder_id,
            )

    # --- Confirmed Actions (called by DialogManager) ---
    def execute_rename_item(
        self,
        item_id: str,
        new_title: str,
        new_icon: Optional[str],
    ):
        self.logger.info(
            f"Executing rename for item ID '{item_id}' to title '{new_title}'",
        )
        if not new_title.strip():
            self.logger.warning("Rename title is empty. Aborting.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "New title cannot be empty!",
                    duration=3,
                    level="warning",
                )
            return

        item_to_rename = self.get_item_by_id(item_id)
        if not item_to_rename:
            self.logger.error(
                f"Cannot rename: Item with ID '{item_id}' not found.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Item not found for renaming.",
                    duration=3,
                    level="error",
                )
            return

        try:
            update_data = {
                "title": new_title.strip(),
                "updated_at": datetime.now(timezone.utc),
            }
            if new_icon and new_icon.strip():  # Only update icon if provided
                update_data["icon"] = new_icon.strip()

            updated_item = item_to_rename.model_copy(update=update_data)

            # Replace in self.notes
            note_index = -1
            for i, n in enumerate(self.notes):
                if n.id == item_id:
                    note_index = i
                    break

            if note_index != -1:
                self.notes[note_index] = updated_item
            else:
                self.logger.error(
                    f"Item {item_id} was in index but not in self.notes list during rename.",
                )
                # This case should ideally not happen if get_item_by_id worked.
                # Consider if self.notes needs rebuilding from index if inconsistencies are possible.
                self.notes.append(updated_item)  # Fallback

            # This updates index and also folder list for dialogs
            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()  # Update UI

            self.logger.info(
                f"Item '{updated_item.id}' renamed to '{updated_item.title}' successfully.",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"{'Folder' if updated_item.is_folder else 'Note'} '{updated_item.title}' renamed.",
                    duration=3,
                    level="success",
                )
        except ValidationError as ve:
            self.logger.error(
                f"Validation error renaming item: {ve}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error renaming item: {ve}",
                    duration=5,
                    level="error",
                )
        except Exception as e:
            self.logger.error(
                f"Unexpected error renaming item: {e}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "An unexpected error occurred during rename. See logs.",
                    duration=5,
                    level="error",
                )

        # Close any dialogs that might have been open for this, e.g., rename dialog
        self.dialog_manager.close_rename_item_dialog()

    def execute_delete_item(self, item_id: str):
        self.logger.info(f"Executing delete for item ID '{item_id}'")
        item_to_delete = self.get_item_by_id(item_id)

        if not item_to_delete:
            self.logger.warning(f"Item ID '{item_id}' not found for deletion.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Item not found.",
                    duration=3,
                    level="warning",
                )
            return

        items_to_delete_ids = {item_id}
        # If it's a folder, find all descendant notes and folders
        if item_to_delete.is_folder:
            queue = [item_id]
            processed_ids_for_deletion_scan = (
                set()
            )  # To avoid issues with cyclic dependencies if ever possible

            while queue:
                current_parent_id = queue.pop(0)
                if current_parent_id in processed_ids_for_deletion_scan:
                    continue
                processed_ids_for_deletion_scan.add(current_parent_id)

                for child in self.notes:
                    if child.parent_id == current_parent_id:
                        items_to_delete_ids.add(child.id)
                        if (
                            child.is_folder
                        ):  # If child is a folder, add its ID to the queue to process its children
                            queue.append(child.id)

        self.logger.debug(
            f"Items identified for deletion (including children if folder): {items_to_delete_ids}",
        )

        # Filter self.notes to keep only items NOT in items_to_delete_ids
        original_count = len(self.notes)
        self.notes = [
            note for note in self.notes if note.id not in items_to_delete_ids]
        deleted_count = original_count - len(self.notes)

        if deleted_count > 0:
            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()
            self.logger.info(
                f"Successfully deleted {deleted_count} item(s) (item '{item_to_delete.title}' and its children if it was a folder).",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"{'Folder' if item_to_delete.is_folder else 'Note'} '{item_to_delete.title}' and its contents deleted.",
                    duration=3,
                    level="success",
                )
        else:
            self.logger.warning(
                f"Attempted to delete item '{item_id}', but no items were removed. This might indicate an issue or it was already deleted.",
            )
            # No toast if nothing actually changed, or could be a "already deleted" type message.

        # If the deleted item was being edited or selected, clear that state
        if self.current_editing_note_id in items_to_delete_ids:
            self.current_editing_note_id = None
            if dpg.does_item_exist(self.editor_window_tag) and dpg.is_item_shown(
                self.editor_window_tag,
            ):
                dpg.configure_item(
                    self.editor_window_tag,
                    show=False,
                )  # Close editor if open for deleted item

        if self.currently_selected_sidebar_note_id in items_to_delete_ids:
            self.currently_selected_sidebar_note_id = None

        # Close context menu if it was for the deleted item
        if self.context_menu_active_item_id in items_to_delete_ids:
            dpg.configure_item(self.context_menu_tag, show=False)
            self.context_menu_active_item_id = None

        # Close delete confirmation dialog if it's open
        self.dialog_manager.close_delete_item_dialog()

    def _apply_tag_filter_from_input(self, sender=None, app_data=None, user_data=None):
        self.active_tag_filter = dpg.get_value(
            self.tag_filter_input_tag).strip()
        self.logger.info(
            f"Tag filter updated from input: '{self.active_tag_filter}'")
        self._refresh_sidebar_list()

    # --- Misc Helpers ---
    def get_item_by_id(
        self,
        item_id: str,
    ) -> Optional[Note]:  # Public for DialogManager
        return self.notes_data_index.get(item_id)

    def shutdown(self):
        self.logger.info(f"{self.name} module shutting down.")
        # Perform any cleanup, e.g., ensure notes are saved if there are pending changes.
        # For now, saving is done on each operation, so direct shutdown is okay.

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import dearpygui.dearpygui as dpg
from pydantic import ValidationError

from schemas import (  # Ensure these are in schemas/note_schemas.py or similar
    Note, NoteCreate)

from .base_module import BaseModule
from .notes_ui_utils import NotesDialogManager

if TYPE_CHECKING:
    from core.app import Core  # For type hinting Core instance


class NotesModule(BaseModule):
    MODULE_NAME = "Notes"
    MODULE_TAG = "notes_module"

    ICON_NOTE_DEFAULT = "📄"
    ICON_FOLDER_DEFAULT = "📁"
    ICON_ROOT = "🌳"
    ROOT_SENTINEL_VALUE = "__root_level_note__"  # For dropdowns indicating root

    def __init__(self, core: "Core"):
        super().__init__(core)
        self.logger.info(f"Initializing {self.name} module...")

        self.notes: List[Note] = []
        self.notes_data_index: Dict[str, Note] = {}
        self.all_tags: set[str] = set()

        self.current_editing_note_id: Optional[str] = None
        self.active_tag_filter: Optional[str] = None

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

        with dpg.window(
            label="Note Editor",
            tag=self.editor_window_tag,
            width=700,
            height=550,
            show=False,  # Initially hidden
            on_close=self._on_editor_window_close,
            no_collapse=True,
            pos=[200, 100],  # Initial position
        ):
            dpg.add_input_text(label="Title", tag=self.editor_title_input_tag, width=-1)
            dpg.add_input_text(
                label="Tags (comma-sep)", tag=self.editor_tags_input_tag, width=-1,
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
                                "title", f"Untitled Item {item_id[:8]}",
                            )
                            item_dict.setdefault("content", "")
                            item_dict.setdefault("tags", [])
                            item_dict.setdefault("parent_id", None)
                            item_dict.setdefault("order", i)
                            is_folder = item_dict.get("is_folder", False)
                            item_dict["is_folder"] = is_folder
                            item_dict.setdefault(
                                "created_at", datetime.now(timezone.utc).isoformat(),
                            )
                            item_dict.setdefault(
                                "updated_at", datetime.now(timezone.utc).isoformat(),
                            )
                            item_dict.setdefault(
                                "icon",
                                self.ICON_FOLDER_DEFAULT
                                if is_folder
                                else self.ICON_NOTE_DEFAULT,
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
                self.logger.info(f"Successfully loaded {len(self.notes)} items.")
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
            notes_to_save = [note.model_dump(mode="json") for note in self.notes]
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(notes_to_save, f, indent=4)
            self.logger.debug("Notes saved successfully.")
        except Exception as e:
            self.logger.error(
                f"Failed to save notes to {self.data_path}: {e}", exc_info=True,
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
        self.dialog_manager.refresh_dropdown_items_in_dialogs()  # Tell dialog manager to update DPG items

    # --- UI Building ---
    def build_dpg_view(self, parent_container_tag: Union[int, str]):
        self.logger.debug(f"Building main DPG view in parent: {parent_container_tag}")
        with dpg.group(parent=parent_container_tag, tag=self.main_content_area_tag):
            dpg.add_text(
                "Select a note or folder from the sidebar.", tag=dpg.generate_uuid(),
            )

    def build_sidebar_view(self, parent_tag: Union[int, str]):
        self.logger.debug(f"Building sidebar view in parent: {parent_tag}")
        with dpg.child_window(parent=parent_tag, width=-1, border=False):
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="New Note",
                    tag=self.create_note_button_tag,
                    callback=self._create_new_note_action,
                    width=-1,
                )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="New Folder",
                    tag=self.create_folder_button_tag,
                    callback=self._create_new_folder_action,
                    width=-1,
                )

            dpg.add_spacer(height=5)
            dpg.add_input_text(
                label="Filter Tags",
                tag=self.tag_filter_input_tag,
                callback=self._apply_tag_filter_from_input,
                width=-1,
                hint="tag1, tag2...",
            )
            dpg.add_text("Items:")
            with dpg.group(tag=self.sidebar_list_tag):
                pass

        self._refresh_sidebar_list()

    def _refresh_sidebar_list(self):
        self.logger.debug(
            f"Refreshing sidebar. Total items: {len(self.notes)}, Filter: '{self.active_tag_filter}'",
        )
        if not dpg.does_item_exist(self.sidebar_list_tag):
            self.logger.error(
                f"Sidebar list container '{self.sidebar_list_tag}' does not exist. Cannot refresh.",
            )
            return

        dpg.delete_item(self.sidebar_list_tag, children_only=True)

        notes_to_display_filtered = list(self.notes)
        if self.active_tag_filter:
            filter_tags = {
                tag.strip().lower()
                for tag in self.active_tag_filter.split(",")
                if tag.strip()
            }
            if filter_tags:
                # This simplistic filter only shows notes that match, losing hierarchy.
                # TODO: A proper filter would show notes and their parent folders.
                notes_to_display_filtered = [
                    note
                    for note in self.notes
                    if not note.is_folder
                    and note.tags
                    and filter_tags.intersection({t.lower() for t in note.tags})
                ]
                self.logger.debug(
                    f"Applied tag filter. Notes to display after filter: {len(notes_to_display_filtered)}",
                )

        notes_by_parent: Dict[Optional[str], List[Note]] = {}

        # If filtering, we might only want to build hierarchy from filtered items + their ancestors
        # For now, if filtering, we'll use notes_to_display_filtered directly (losing hierarchy)
        # If not filtering, use all self.notes for full hierarchy
        source_for_hierarchy = self.notes  # if not self.active_tag_filter else notes_to_display_filtered # Decide on this logic
        # For full hierarchy always, then grey out non-matches:
        source_for_hierarchy = self.notes

        for item in source_for_hierarchy:
            parent_id = item.parent_id
            if parent_id not in notes_by_parent:
                notes_by_parent[parent_id] = []
            notes_by_parent[parent_id].append(item)

        if (
            not source_for_hierarchy and self.active_tag_filter
        ):  # Check notes_to_display_filtered if filtering was effective
            dpg.add_text(
                f"No notes match filter: {self.active_tag_filter}",
                parent=self.sidebar_list_tag,
                color=(200, 200, 100),
            )
        elif not source_for_hierarchy:
            dpg.add_text(
                "No items yet. Create one!",
                parent=self.sidebar_list_tag,
                color=(200, 200, 200),
            )
        else:
            self._build_sidebar_tree_recursive(
                self.sidebar_list_tag, None, notes_by_parent,
            )
        self.logger.debug("Sidebar refresh complete.")

    def _build_sidebar_tree_recursive(
        self,
        dpg_parent_tag: Union[int, str],
        current_item_parent_id: Optional[str],
        items_by_parent: Dict[Optional[str], List[Note]],
    ):
        children = items_by_parent.get(current_item_parent_id, [])
        sorted_children = sorted(
            children,
            key=lambda x: (
                not x.is_folder,
                x.order if x.order is not None else 0,
                x.title.lower(),
            ),
        )

        # Determine active filter tags for greying out non-matching items
        active_filter_tags_set = set()
        if self.active_tag_filter:
            active_filter_tags_set = {
                tag.strip().lower()
                for tag in self.active_tag_filter.split(",")
                if tag.strip()
            }

        for item in sorted_children:
            item_dpg_tag = f"{self.module_tag}_sidebar_item_{item.id}"
            display_label = f"{item.icon} {item.title}" if item.icon else item.title

            # Grey out non-matching items if a filter is active
            item_color = (255, 255, 255, 255)  # Default color
            is_dimmed = False
            if active_filter_tags_set:
                if item.is_folder:
                    # A folder is dimmed if none of its children (recursively) match the filter. This is complex.
                    # Simpler: folders are never dimmed by tag filter directly, only their note children.
                    pass
                elif not item.tags or not active_filter_tags_set.intersection(
                    {t.lower() for t in item.tags},
                ):
                    item_color = (128, 128, 128, 200)  # Dim color
                    is_dimmed = True

            handler_reg_tag = f"{item_dpg_tag}_handler_reg"
            if not dpg.does_item_exist(handler_reg_tag):  # Define once
                with dpg.item_handler_registry(tag=handler_reg_tag):
                    dpg.add_item_clicked_handler(
                        dpg.mvMouseButton_Right,
                        callback=self._handle_sidebar_item_right_click,
                        user_data=item.id,
                    )
                    # Left click for notes handled by selectable's callback

            if item.is_folder:
                with dpg.tree_node(
                    label=display_label,
                    tag=item_dpg_tag,
                    parent=dpg_parent_tag,
                    user_data=item.id,
                ) as folder_node:
                    dpg.bind_item_handler_registry(folder_node, handler_reg_tag)
                    if (
                        dpg.does_item_exist(folder_node) and is_dimmed
                    ):  # Tree node itself doesn't have simple color
                        # Could add a text item inside with dim color if needed, or theme it
                        pass
                    self._build_sidebar_tree_recursive(
                        folder_node, item.id, items_by_parent,
                    )
            else:  # It's a note
                selectable_tag = dpg.add_selectable(
                    label=display_label,
                    tag=item_dpg_tag,
                    parent=dpg_parent_tag,
                    user_data=item.id,
                    span_columns=True,
                    callback=self._handle_sidebar_item_left_click,
                )
                dpg.bind_item_handler_registry(selectable_tag, handler_reg_tag)
                if is_dimmed and dpg.does_item_exist(selectable_tag):
                    # Themeing selectables for color is better. This is a workaround.
                    # dpg.configure_item(selectable_tag, ) # No direct color for selectable text easily
                    pass

    # --- Item Creation Callbacks ---
    def _create_new_note_action(self, sender=None, app_data=None, user_data=None):
        self.logger.info("Create new note action triggered.")
        self.pending_new_item_parent_id = (
            user_data.get("parent_id") if isinstance(user_data, dict) else None
        )
        self.pending_new_item_is_folder = False
        self.dialog_manager.show_new_item_dialog(
            is_folder=False, parent_id_override=self.pending_new_item_parent_id,
        )

    def _create_new_folder_action(self, sender=None, app_data=None, user_data=None):
        self.logger.info("Create new folder action triggered.")
        self.pending_new_item_parent_id = (
            user_data.get("parent_id") if isinstance(user_data, dict) else None
        )
        self.pending_new_item_is_folder = True
        self.dialog_manager.show_new_item_dialog(
            is_folder=True, parent_id_override=self.pending_new_item_parent_id,
        )

    # This method is called by DialogManager after its dialog is confirmed
    def execute_create_new_item(
        self,
        title: str,
        icon: Optional[str],
        chosen_parent_id_from_dropdown: Optional[str],
        is_folder: bool,
    ):
        self.logger.info(
            f"Executing creation. Title: '{title}', Folder: {is_folder}, Chosen Parent in Dialog: {chosen_parent_id_from_dropdown}, Pending Parent: {self.pending_new_item_parent_id}",
        )

        actual_parent_id = self.pending_new_item_parent_id
        if actual_parent_id is None:
            if chosen_parent_id_from_dropdown == self.ROOT_SENTINEL_VALUE:
                actual_parent_id = None
            else:
                actual_parent_id = chosen_parent_id_from_dropdown

        self.logger.debug(f"Final parent_id for new item: {actual_parent_id}")

        new_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        default_icon = self.ICON_FOLDER_DEFAULT if is_folder else self.ICON_NOTE_DEFAULT

        children_of_parent = [
            item for item in self.notes if item.parent_id == actual_parent_id
        ]
        new_order = len(children_of_parent)

        try:
            item_data = NoteCreate(
                id=new_id,
                title=title,
                content="",
                tags=[],
                icon=icon if icon and icon.strip() else default_icon,
                parent_id=actual_parent_id,
                is_folder=is_folder,
                order=new_order,
                created_at=timestamp,
                updated_at=timestamp,
            )
            new_item_obj = Note(**item_data.model_dump())

            self.notes.append(new_item_obj)
            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()

            item_type_str = "Folder" if is_folder else "Note"
            self.logger.info(
                f"{item_type_str} '{title}' (ID: {new_id}) created successfully under parent {actual_parent_id}.",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"{item_type_str} '{title}' created!", level="success",
                )

            if not is_folder:
                self._open_editor_for_note(new_item_obj.id)

        except ValidationError as ve:
            self.logger.error(
                f"Validation error creating new item: {ve}", exc_info=True,
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: {ve.errors()[0]['msg'] if ve.errors() else 'Invalid data'}",
                    level="error",
                )
        except Exception as e:
            self.logger.error(f"Error creating new item: {e}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Could not create item. Check logs.", level="error",
                )
        finally:
            self.pending_new_item_parent_id = None
            self.pending_new_item_is_folder = False

    # --- Editor Workflow ---
    def _open_editor_for_note(self, note_id: str):
        self.logger.debug(f"Opening editor for note ID: {note_id}")
        note_to_edit = self.notes_data_index.get(note_id)

        if not note_to_edit:
            self.logger.error(f"Note not found: {note_id}. Cannot open editor.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: Note {note_id} not found!", level="error",
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

        dpg.configure_item(self.editor_window_tag, label=editor_label, show=True)
        dpg.focus_item(self.editor_content_input_tag)
        self.logger.info(
            f"Editor opened for note: '{note_to_edit.title}' (ID: {note_id}).",
        )

    def _save_note_from_editor(self, sender=None, app_data=None, user_data=None):
        if not self.current_editing_note_id:
            self.logger.error("No note currently being edited. Cannot save.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: No note selected to save!", level="error",
                )
            return

        note_to_update = self.notes_data_index.get(self.current_editing_note_id)
        if not note_to_update:
            self.logger.error(
                f"Note with ID {self.current_editing_note_id} not found. Cannot save.",
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: Note {self.current_editing_note_id} not found for saving!",
                    level="error",
                )
            return

        try:
            new_title = dpg.get_value(self.editor_title_input_tag).strip()
            new_content = dpg.get_value(self.editor_content_input_tag)
            tags_str = dpg.get_value(self.editor_tags_input_tag).strip()
            new_tags = sorted(
                list(set(tag.strip() for tag in tags_str.split(",") if tag.strip())),
            )

            if not new_title:
                self.logger.warning("Note title cannot be empty. Save aborted.")
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Note title cannot be empty.", level="warning",
                    )
                dpg.focus_item(self.editor_title_input_tag)
                return

            changed = (
                note_to_update.title != new_title
                or note_to_update.content != new_content
                or set(note_to_update.tags if note_to_update.tags else [])
                != set(new_tags)
            )

            if not changed:
                self.logger.info(
                    f"No changes detected for note '{note_to_update.title}'. Save skipped.",
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        f"No changes to save for '{new_title}'.", level="info",
                    )
                return  # Optionally close editor: dpg.configure_item(self.editor_window_tag, show=False)

            note_to_update.title = new_title
            note_to_update.content = new_content
            note_to_update.tags = new_tags
            note_to_update.updated_at = datetime.now(timezone.utc).isoformat()

            self.logger.info(
                f"Saving changes to note: '{note_to_update.title}' (ID: {note_to_update.id})",
            )

            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()

            dpg.configure_item(self.editor_window_tag, show=False)
            self.current_editing_note_id = None
            self.logger.info(f"Note '{note_to_update.title}' saved successfully.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Note '{new_title}' saved!", level="success",
                )

        except Exception as e:
            self.logger.error(
                f"Error saving note {self.current_editing_note_id}: {e}", exc_info=True,
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error saving note: {e}", level="error",
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
                # If we want to select folder to show info in main view, add here
            else:  # It's a note
                self.logger.info(f"Note '{item.title}' selected. Opening in editor.")
                self._open_editor_for_note(item_id)
        else:
            self.logger.warning(f"Selected item_id '{item_id}' not found in index.")

    def _handle_sidebar_item_right_click(self, sender, app_data, item_id: str):
        self.logger.debug(f"Sidebar item right-clicked. Item ID: {item_id}")
        self.context_menu_active_item_id = item_id
        item = self.notes_data_index.get(item_id)
        if not item:
            self.logger.error(f"Cannot show context menu: Item {item_id} not found.")
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
                f"Error: Item {item_id} not found for rename.", level="error",
            )

    def _context_delete_action(self, sender, app_data, item_id: str):
        self.logger.debug(f"Context menu: Delete for {item_id}")
        item = self.notes_data_index.get(item_id)
        if item and hasattr(self.dialog_manager, "show_delete_confirmation_dialog"):
            self.dialog_manager.show_delete_confirmation_dialog(item)
        elif hasattr(self.core, "gui_manager") and self.core.gui_manager:
            self.core.gui_manager.show_toast(
                f"Error: Item {item_id} not found for delete.", level="error",
            )

    def _context_new_note_in_folder_action(
        self, sender, app_data, parent_folder_id: str,
    ):
        self.logger.debug(f"Context menu: New Note in folder {parent_folder_id}")
        self.pending_new_item_parent_id = parent_folder_id
        self.pending_new_item_is_folder = False
        if hasattr(self.dialog_manager, "show_new_item_dialog"):
            self.dialog_manager.show_new_item_dialog(
                is_folder=False, parent_id_override=parent_folder_id,
            )

    def _context_new_folder_in_folder_action(
        self, sender, app_data, parent_folder_id: str,
    ):
        self.logger.debug(f"Context menu: New Subfolder in folder {parent_folder_id}")
        self.pending_new_item_parent_id = parent_folder_id
        self.pending_new_item_is_folder = True
        if hasattr(self.dialog_manager, "show_new_item_dialog"):
            self.dialog_manager.show_new_item_dialog(
                is_folder=True, parent_id_override=parent_folder_id,
            )

    # --- Confirmed Actions (called by DialogManager) ---
    def execute_rename_item(
        self, item_id: str, new_title: str, new_icon: Optional[str],
    ):
        self.logger.info(
            f"Executing rename for item {item_id} to '{new_title}', icon: '{new_icon}'",
        )
        item = self.notes_data_index.get(item_id)
        if item:
            item.title = new_title
            if new_icon and new_icon.strip():
                item.icon = new_icon.strip()
            elif new_icon == "":  # Explicitly empty string clears to default
                item.icon = (
                    self.ICON_FOLDER_DEFAULT
                    if item.is_folder
                    else self.ICON_NOTE_DEFAULT
                )
            item.updated_at = datetime.now(timezone.utc).isoformat()

            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Item '{new_title}' renamed.", level="success",
                )

            if (
                self.current_editing_note_id == item_id and not item.is_folder
            ):  # Update editor window title if it was this note
                dpg.configure_item(
                    self.editor_window_tag,
                    label=f"Edit Note: {item.title[:40]}{'...' if len(item.title) > 40 else ''}",
                )
        elif hasattr(self.core, "gui_manager") and self.core.gui_manager:
            self.logger.error(f"Cannot rename: Item {item_id} not found.")
            self.core.gui_manager.show_toast(
                f"Error: Item {item_id} not found for renaming.", level="error",
            )

    def execute_delete_item(self, item_id: str):
        self.logger.info(f"Executing delete for item {item_id}")
        item_to_delete = self.notes_data_index.get(item_id)
        if not item_to_delete:
            self.logger.error(f"Cannot delete: Item {item_id} not found.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: Item {item_id} not found for deletion.", level="error",
                )
            return

        items_to_remove_ids = {item_id}
        if item_to_delete.is_folder:
            q = [item_id]
            head = 0
            while head < len(q):
                current_parent_id = q[head]
                head += 1
                for child in self.notes:  # Search all notes
                    if child.parent_id == current_parent_id:
                        items_to_remove_ids.add(child.id)
                        if child.is_folder:
                            q.append(child.id)
            self.logger.info(
                f"Folder deletion: also removing descendants: {items_to_remove_ids - {item_id}}",
            )

        original_count = len(self.notes)
        self.notes = [note for note in self.notes if note.id not in items_to_remove_ids]

        if len(self.notes) < original_count:
            if self.current_editing_note_id in items_to_remove_ids:
                self._on_editor_window_close()  # Close editor if open note deleted

            self._update_internal_structures()
            self._save_notes()
            self._refresh_sidebar_list()
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Item '{item_to_delete.title}' and its contents deleted.",
                    level="success",
                )
            self.logger.info(
                f"Deleted item(s) related to ID {item_id}. Original count: {original_count}, new: {len(self.notes)}.",
            )
        else:
            self.logger.warning(
                f"Delete executed for {item_id}, but no items removed. Might indicate an issue.",
            )

    # --- Tag Filtering ---
    def _apply_tag_filter_from_input(self, sender=None, app_data=None, user_data=None):
        self.active_tag_filter = dpg.get_value(self.tag_filter_input_tag).strip()
        self.logger.info(f"Tag filter updated from input: '{self.active_tag_filter}'")
        self._refresh_sidebar_list()

    # --- Misc Helpers ---
    def get_item_by_id(
        self, item_id: str,
    ) -> Optional[Note]:  # Public for DialogManager
        return self.notes_data_index.get(item_id)

    def shutdown(self):
        self.logger.info(f"{self.name} module shutting down.")
        # Perform any cleanup, e.g., ensure notes are saved if there are pending changes.
        # For now, saving is done on each operation, so direct shutdown is okay.

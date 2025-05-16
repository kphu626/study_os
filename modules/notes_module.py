import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Union, Tuple
from pathlib import Path  # Added import

import dearpygui.dearpygui as dpg
from pydantic import ValidationError

from schemas import (  # Ensure these are in schemas/note_schemas.py or similar
    Note,
    NoteCreate,
)
from schemas.file_schemas import FileAttachment  # Added import

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
        self.logger.info(f"Initializing {self.name} module ({self.module_tag})...")
        # Temporarily force logger level for this module to DEBUG
        import logging

        self.logger.setLevel(logging.DEBUG)
        self.logger.debug(f"{self.name} logger level forced to DEBUG for this session.")

        self.notes: List[Note] = []
        self.notes_data_index: Dict[str, Note] = {}
        self.all_tags: set[str] = set()

        self.current_editing_note_id: Optional[str] = None
        self.active_tag_filter: Optional[str] = None
        self.currently_selected_sidebar_note_id: Optional[str] = None
        # For main content view
        self.currently_viewed_note_id: Optional[str] = None

        self.pending_new_item_parent_id: Optional[str] = (
            None  # For context menu creation
        )
        self.pending_new_item_is_folder: bool = False

        # Data path
        self.data_path = self.core.config.notes_path  # Get from AppConfig via Core
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.assets_path = self.core.config.assets_dir  # Get assets path
        # Ensure assets path exists
        self.assets_path.mkdir(parents=True, exist_ok=True)

        # UI Managers
        self.dialog_manager = NotesDialogManager(
            self,
        )  # Pass self (NotesModule instance)

        self.active_search_query: Optional[str] = None  # For sidebar search

        # --- DPG Tags ---
        # Sidebar
        self.sidebar_list_tag = f"{self.module_tag}_sidebar_list_actual_group"
        self.create_note_button_tag = f"{self.module_tag}_create_note_btn"
        self.create_folder_button_tag = f"{self.module_tag}_create_folder_btn"
        self.tag_filter_input_tag = f"{self.module_tag}_tag_filter_input"
        self.sidebar_search_input_tag = (
            f"{self.module_tag}_sidebar_search_input"  # New tag for search
        )

        # Date Filter UI Tags
        self.date_filter_group_tag = f"{self.module_tag}_date_filter_group"
        self.created_after_input_tag = f"{self.module_tag}_created_after_input"
        self.created_before_input_tag = f"{self.module_tag}_created_before_input"
        self.modified_after_input_tag = f"{self.module_tag}_modified_after_input"
        self.modified_before_input_tag = f"{self.module_tag}_modified_before_input"
        self.apply_date_filters_button_tag = f"{self.module_tag}_apply_date_filters_btn"
        self.clear_date_filters_button_tag = f"{self.module_tag}_clear_date_filters_btn"

        # Editor Window (reusable pop-up)
        self.editor_window_tag = f"{self.module_tag}_editor_window"
        self.editor_title_input_tag = f"{self.module_tag}_editor_title_input"
        self.editor_content_input_tag = f"{self.module_tag}_editor_content_input"
        self.editor_tags_input_tag = f"{self.module_tag}_editor_tags_input"
        self.editor_save_button_tag = f"{self.module_tag}_editor_save_button"
        self.editor_close_button_tag = f"{self.module_tag}_editor_close_button"

        # Editor Linked Notes UI
        self.editor_linked_notes_group_tag = (
            f"{self.module_tag}_editor_linked_notes_group"
        )
        self.editor_linked_notes_list_tag = (
            f"{self.module_tag}_editor_linked_notes_list"  # Child window
        )
        self.editor_add_link_button_tag = f"{self.module_tag}_editor_add_link_button"

        # Editor Attachments UI
        self.editor_attachments_group_tag = (
            f"{self.module_tag}_editor_attachments_group"
        )
        self.editor_attachments_list_tag = f"{self.module_tag}_editor_attachments_list"
        self.editor_add_attachment_button_tag = (
            f"{self.module_tag}_editor_add_attachment_button"
        )
        self.file_dialog_add_attachment_tag = (
            f"{self.module_tag}_file_dialog_add_attachment"
        )

        # Add Link Dialog (within NotesModule for now, not DialogManager)
        self.add_link_dialog_tag = f"{self.module_tag}_add_link_dialog"
        self.add_link_dialog_listbox_tag = f"{self.module_tag}_add_link_dialog_listbox"
        self.add_link_dialog_filter_tag = f"{self.module_tag}_add_link_dialog_filter"
        self.add_link_dialog_link_button_tag = (
            f"{self.module_tag}_add_link_dialog_link_button"
        )

        # Context Menu
        self.context_menu_tag = f"{self.module_tag}_context_menu"
        self.context_menu_active_item_id: Optional[str] = (
            None  # ID of item right-clicked
        )

        # Main content area (placeholder for now, editor is a window)
        # This tag is the parent provided by StudyOS
        self.main_content_area_tag = f"{self.module_tag}_main_content_area"
        # Group within the main_content_area_tag
        self.main_content_display_group_tag = (
            f"{self.module_tag}_main_content_display_group"
        )
        self.main_content_title_tag = f"{self.module_tag}_main_content_title"
        self.main_content_tags_tag = f"{self.module_tag}_main_content_tags"
        self.main_content_text_input_tag = (
            # For displaying content
            f"{self.module_tag}_main_content_text_input"
        )
        # For linked notes in main view
        self.main_content_linked_list_tag = (
            f"{self.module_tag}_main_content_linked_list"
        )
        self.main_content_placeholder_text_tag = f"{self.module_tag}_main_placeholder"

        # File Dialogs for Import/Export
        self.file_dialog_export_tag = f"{self.module_tag}_file_dialog_export"
        self.file_dialog_import_tag = f"{self.module_tag}_file_dialog_import"
        self._define_file_dialogs()  # Define them once
        self._define_add_attachment_file_dialog()  # Define attachment dialog

        # Buttons for sidebar (tags defined here, added in build_sidebar_view)
        self.export_button_tag = f"{self.module_tag}_export_btn"
        self.import_button_tag = f"{self.module_tag}_import_btn"

        # Attributes for storing parsed date filter values
        # Store as string, parse on use
        self.created_after_filter: Optional[str] = None
        self.created_before_filter: Optional[str] = None
        self.modified_after_filter: Optional[str] = None
        self.modified_before_filter: Optional[str] = None

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
            width=750,
            height=800,
            show=False,
            on_close=self._on_editor_window_close,
            no_collapse=True,
            pos=[200, 100],
        ):
            title_input = dpg.add_input_text(
                label="Title", tag=self.editor_title_input_tag, width=-1
            )
            with dpg.tooltip(title_input):
                dpg.add_text("The title of your note or folder.")

            tags_input = dpg.add_input_text(
                label="Tags (comma-sep)",
                tag=self.editor_tags_input_tag,
                width=-1,
                hint="e.g., work, important, idea",
            )
            with dpg.tooltip(tags_input):
                dpg.add_text(
                    "Comma-separated list of tags for organization and filtering."
                )

            content_input = dpg.add_input_text(
                label="Content",
                tag=self.editor_content_input_tag,
                multiline=True,
                width=-1,
                height=-350,
                tab_input=True,
                hint="Enter your note content here. Markdown is supported for viewing.",
            )
            with dpg.tooltip(content_input):
                dpg.add_text(
                    "Main content of your note. Markdown syntax can be used for formatting (view only for now)."
                )

            # Linked Notes Section
            with dpg.group(tag=self.editor_linked_notes_group_tag):
                dpg.add_separator()
                dpg.add_text("Linked Notes:")
                with dpg.child_window(
                    tag=self.editor_linked_notes_list_tag, height=80, border=True
                ):
                    pass  # Populated by _refresh_editor_linked_notes_display
                add_link_btn = dpg.add_button(
                    label="Link to another Note...",
                    tag=self.editor_add_link_button_tag,
                    callback=self._show_add_link_dialog,
                    width=-1,
                )
                with dpg.tooltip(add_link_btn):
                    dpg.add_text(
                        "Create a link to another existing note in your database."
                    )

            # Attachments Section
            with dpg.group(tag=self.editor_attachments_group_tag):
                dpg.add_separator()
                dpg.add_text("Attachments:")
                with dpg.child_window(
                    tag=self.editor_attachments_list_tag, height=100, border=True
                ):
                    pass  # Populated by _refresh_editor_attachments_display
                add_att_btn = dpg.add_button(
                    label="Add Attachment...",
                    tag=self.editor_add_attachment_button_tag,
                    callback=lambda: dpg.show_item(self.file_dialog_add_attachment_tag),
                    width=-1,
                )
                with dpg.tooltip(add_att_btn):
                    dpg.add_text("Attach a file from your computer to this note.")

            dpg.add_spacer(height=10)  # Spacer before save/close buttons

            with dpg.group(horizontal=True):
                save_btn = dpg.add_button(
                    label="Save",
                    tag=self.editor_save_button_tag,
                    callback=self._save_note_from_editor,
                    width=100,
                )
                with dpg.tooltip(save_btn):
                    dpg.add_text("Save all changes made to this note.")

                close_btn = dpg.add_button(
                    label="Close",
                    tag=self.editor_close_button_tag,
                    callback=self._on_editor_window_close,
                    width=100,
                )
                with dpg.tooltip(close_btn):
                    dpg.add_text(
                        "Close the editor. Unsaved changes may be lost (though autosave might occur on operations)."
                    )  # Added more detail
        self.logger.debug(
            f"Editor window '{self.editor_window_tag}' defined with tooltips, linked notes and attachments sections."
        )

    def _define_file_dialogs(self):
        # Export Dialog
        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._perform_export,
            tag=self.file_dialog_export_tag,
            width=600,
            height=400,
            default_filename="notes_export.json",
            modal=True,  # Make it modal so user must interact
        ):
            dpg.add_file_extension(".json", color=(150, 255, 150, 255))
            dpg.add_file_extension(".*", color=(0, 255, 255, 255))  # All files

        # Import Dialog
        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._perform_import,
            tag=self.file_dialog_import_tag,
            width=600,
            height=400,
            modal=True,  # Make it modal
        ):
            dpg.add_file_extension(".json", color=(150, 255, 150, 255))
            dpg.add_file_extension(".*", color=(0, 255, 255, 255))

    def _define_add_attachment_file_dialog(self):
        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._handle_add_attachment_callback,
            tag=self.file_dialog_add_attachment_tag,
            width=700,
            height=450,
            modal=True,
            # allow_multi_select=True # Consider this later for UX
        ):
            dpg.add_file_extension(
                ".*", color=(150, 255, 150, 255)
            )  # Allow all files for now

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
                            item_dict.setdefault(
                                "linked_note_ids", []
                            )  # Default for linked notes
                            item_dict.setdefault(
                                "attachments", []
                            )  # Default for attachments

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
                            # Ensure new fields have defaults if loading old data
                            item_dict.setdefault("linked_note_ids", [])

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
            # Ensure notes are sorted by order before saving to maintain structure implicitly
            # if items are ever loaded without relying on parent_id for ordering.
            # For now, we rely on parent_id and then title for sorting in display.
            # notes_to_save_sorted = sorted(self.notes, key=lambda n: (n.parent_id or "", n.order, n.title.lower()))
            # notes_to_save = [note.model_dump(mode="json") for note in notes_to_save_sorted]
            notes_to_save = [note.model_dump(mode="json") for note in self.notes]
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
                    duration_ms=3000,
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

    def _get_all_descendant_ids(self, folder_id: str) -> set[str]:
        """Recursively gets all descendant note/folder IDs for a given folder_id."""
        descendant_ids: set[str] = set()
        children = [item for item in self.notes if item.parent_id == folder_id]
        for child in children:
            descendant_ids.add(child.id)
            if child.is_folder:
                descendant_ids.update(self._get_all_descendant_ids(child.id))
        return descendant_ids

    def _populate_available_folders_for_dialog_manager(
        self, exclude_self_and_children_id: Optional[str] = None
    ):
        # This list is used by DialogManager to populate its dropdowns
        self.dialog_manager.available_folders_for_dropdown = [
            (f"{self.ICON_ROOT} Root Level", self.ROOT_SENTINEL_VALUE),
        ]

        ids_to_exclude: set[str] = set()
        if exclude_self_and_children_id:
            item_to_exclude = self.get_item_by_id(exclude_self_and_children_id)
            if item_to_exclude:
                ids_to_exclude.add(exclude_self_and_children_id)
                if item_to_exclude.is_folder:
                    ids_to_exclude.update(
                        self._get_all_descendant_ids(exclude_self_and_children_id)
                    )

        self.logger.debug(
            f"Populating available folders. Excluding IDs: {ids_to_exclude if ids_to_exclude else 'None'}"
        )

        sorted_folders = sorted(
            [note for note in self.notes if note.is_folder],
            key=lambda f: f.title.lower(),
        )
        for folder in sorted_folders:
            if folder.id in ids_to_exclude:
                continue
            self.dialog_manager.available_folders_for_dropdown.append(
                (f"{folder.icon} {folder.title}", folder.id),
            )
        self.logger.debug(
            f"Populated available folders for DialogManager: {len(self.dialog_manager.available_folders_for_dropdown)} items after exclusion.",
        )

    # --- UI Building ---
    def build_dpg_view(self, parent_container_tag: Union[int, str]):
        self.logger.debug(f"Building main DPG view in parent: {parent_container_tag}")
        # parent_container_tag is self.main_content_area_tag defined in __init__ and given by StudyOS
        # We add our actual display group inside it.
        if dpg.does_item_exist(self.main_content_display_group_tag):
            dpg.delete_item(self.main_content_display_group_tag)

        with dpg.group(
            tag=self.main_content_display_group_tag,
            parent=parent_container_tag,
            width=-1,
            height=-1,
        ):
            dpg.add_text(
                "Select a note from the sidebar to view its content.",
                tag=self.main_content_placeholder_text_tag,
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
                new_note_btn = dpg.add_button(
                    label="New Note",
                    tag=self.create_note_button_tag,
                    callback=self._create_new_note_action,
                    width=-1,
                )
                with dpg.tooltip(new_note_btn):
                    dpg.add_text("Create a new blank note at the root level.")

                new_folder_btn = dpg.add_button(
                    label="New Folder",
                    tag=self.create_folder_button_tag,
                    callback=self._create_new_folder_action,
                    width=-1,
                )
                with dpg.tooltip(new_folder_btn):
                    dpg.add_text(
                        "Create a new folder at the root level to organize notes."
                    )

            search_input = dpg.add_input_text(
                label="Search Notes",
                tag=self.sidebar_search_input_tag,
                callback=self._apply_sidebar_search_filter,
                hint="Search title/content (Enter)",
                width=-1,
                on_enter=True,
            )
            with dpg.tooltip(search_input):
                dpg.add_text(
                    "Search note titles and content. Press Enter to trigger search."
                )

            tag_filter_input = dpg.add_input_text(
                label="Filter Tags",
                tag=self.tag_filter_input_tag,
                callback=self._apply_tag_filter_from_input,
                hint="tag1, tag2 (Enter to filter)",
                width=-1,
                on_enter=True,
            )
            with dpg.tooltip(tag_filter_input):
                dpg.add_text(
                    "Filter notes by tags. Enter comma-separated tags and press Enter."
                )

            dpg.add_spacer(height=5)

            # --- Date Filters Section ---
            with dpg.collapsing_header(
                label="Date Filters", default_open=False, tag=self.date_filter_group_tag
            ):
                created_after_input = dpg.add_input_text(
                    label="Created After",
                    tag=self.created_after_input_tag,
                    hint="YYYY-MM-DD",
                    width=-1,
                )
                with dpg.tooltip(created_after_input):
                    dpg.add_text(
                        "Show notes created on or after this date (YYYY-MM-DD)."
                    )

                created_before_input = dpg.add_input_text(
                    label="Created Before",
                    tag=self.created_before_input_tag,
                    hint="YYYY-MM-DD",
                    width=-1,
                )
                with dpg.tooltip(created_before_input):
                    dpg.add_text(
                        "Show notes created on or before this date (YYYY-MM-DD)."
                    )

                modified_after_input = dpg.add_input_text(
                    label="Modified After",
                    tag=self.modified_after_input_tag,
                    hint="YYYY-MM-DD",
                    width=-1,
                )
                with dpg.tooltip(modified_after_input):
                    dpg.add_text(
                        "Show notes modified on or after this date (YYYY-MM-DD)."
                    )

                modified_before_input = dpg.add_input_text(
                    label="Modified Before",
                    tag=self.modified_before_input_tag,
                    hint="YYYY-MM-DD",
                    width=-1,
                )
                with dpg.tooltip(modified_before_input):
                    dpg.add_text(
                        "Show notes modified on or before this date (YYYY-MM-DD)."
                    )

                with dpg.group(horizontal=True, width=-1):
                    apply_dates_btn = dpg.add_button(
                        label="Apply Dates",
                        tag=self.apply_date_filters_button_tag,
                        callback=self._apply_date_filters_action,  # Callback to be implemented
                        width=-1,
                    )
                    with dpg.tooltip(apply_dates_btn):
                        dpg.add_text("Apply the specified date filters.")

                    clear_dates_btn = dpg.add_button(
                        label="Clear Dates",
                        tag=self.clear_date_filters_button_tag,
                        callback=self._clear_date_filters_action,  # Callback to be implemented
                        width=-1,
                    )
                    with dpg.tooltip(clear_dates_btn):
                        dpg.add_text("Remove all active date filters.")
                dpg.add_spacer(height=5)
            # --- End Date Filters Section ---

            dpg.add_spacer(height=5)
            with dpg.group(horizontal=True):
                import_btn = dpg.add_button(
                    label="Import Notes...",
                    tag=self.import_button_tag,
                    callback=lambda: dpg.show_item(self.file_dialog_import_tag),
                    width=-1,
                )
                with dpg.tooltip(import_btn):
                    dpg.add_text("Import notes from a JSON backup file.")
                export_btn = dpg.add_button(
                    label="Export All Notes...",
                    tag=self.export_button_tag,
                    callback=lambda: dpg.show_item(self.file_dialog_export_tag),
                    width=-1,
                )
                with dpg.tooltip(export_btn):
                    dpg.add_text(
                        "Export all current notes and folders to a JSON backup file."
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
        # Determine the list of notes to display based on active filters
        notes_to_render = self.notes
        processed_ids_for_hierarchy = (
            set()
        )  # Store IDs of notes that pass filters to build hierarchy for folders

        # Helper to parse date string to date object for filtering
        # Moved _parse_date_input to be a standalone helper method in the class

        # 0. Parse active date filters once
        # These will be datetime.date objects or None
        active_created_after = self._parse_date_input(self.created_after_filter)
        active_created_before = self._parse_date_input(self.created_before_filter)
        active_modified_after = self._parse_date_input(self.modified_after_filter)
        active_modified_before = self._parse_date_input(self.modified_before_filter)

        # 1. Apply search query filter (if active)
        if self.active_search_query:
            query = self.active_search_query.lower()
            search_results = []
            for note in notes_to_render:
                if (
                    note.is_folder
                ):  # Always include folders in search results if their children match
                    # We will determine folder visibility later based on filtered children
                    continue
                if query in note.title.lower() or query in note.content.lower():
                    search_results.append(note)
                    processed_ids_for_hierarchy.add(note.id)
            notes_to_render = (
                search_results  # notes_to_render now only contains matching notes
            )
        else:
            # If no search query, all non-folder items initially pass this stage for hierarchy building
            for note in notes_to_render:
                if not note.is_folder:
                    processed_ids_for_hierarchy.add(note.id)

        # 2. Apply tag filter (if active) to the results of the search filter (or all notes)
        if self.active_tag_filter:
            tag_query = {
                tag.strip().lower()
                for tag in self.active_tag_filter.split(",")
                if tag.strip()
            }
            if tag_query:  # Only filter if there are actual tags entered
                tag_filtered_notes = []
                current_processed_ids = set()  # Reset for tag filtering pass
                for note in (
                    notes_to_render
                ):  # notes_to_render is from search filter or all notes
                    if note.is_folder:
                        continue
                    note_tags_lower = {t.lower() for t in (note.tags or [])}
                    if tag_query.issubset(note_tags_lower):
                        tag_filtered_notes.append(note)
                        current_processed_ids.add(note.id)
                notes_to_render = tag_filtered_notes
                processed_ids_for_hierarchy = (
                    current_processed_ids  # Update with tag filter results
                )
        # If tag filter is not active, processed_ids_for_hierarchy remains from search (or all non-folders)

        # 3. Apply Date Filters (New Section)
        # This will filter notes_to_render further if any date filters are active.
        # It also updates processed_ids_for_hierarchy for items that pass this stage.
        if (
            active_created_after
            or active_created_before
            or active_modified_after
            or active_modified_before
        ):
            date_filtered_notes = []
            current_processed_ids_date_filter = (
                set()
            )  # IDs that pass date filter specifically

            for note in notes_to_render:  # notes_to_render is from previous filters
                if note.is_folder:
                    # Folders are not directly filtered by date, their visibility depends on children
                    continue

                try:
                    # Parse note's dates (they are ISO strings)
                    # Ensure timezone info is handled or stripped for naive comparison if filters are naive
                    # For simplicity, assuming filters are naive (YYYY-MM-DD string inputs lead to naive date objects)
                    # Note dates are stored as ISO strings, e.g., "2023-10-26T10:00:00Z"
                    # Convert to datetime.datetime, then to .date() for comparison
                    # note_created_dt = datetime.fromisoformat(note.created_at.replace('Z', '+00:00')) # Handle Z for UTC
                    # note_created_date = note_created_dt.date()
                    # note_updated_dt = datetime.fromisoformat(note.updated_at.replace('Z', '+00:00'))
                    # note_updated_date = note_updated_dt.date()

                    # Corrected: note.created_at and note.updated_at are already datetime objects from Pydantic
                    note_created_date = note.created_at.date()
                    note_updated_date = note.updated_at.date()
                except ValueError as e:
                    self.logger.error(
                        f"Error parsing date for note '{note.id}' ('{note.title}'): {e}. Skipping date filter for this note."
                    )
                    # If dates are unparseable, it can't pass date filters. Decide if it should be included if no date filters applied.
                    # For now, if a date filter is active and note's date is bad, it won't match.
                    continue  # Skip this note for date filtering if its dates are malformed

                # Apply Created Date Filters
                if active_created_after and note_created_date < active_created_after:
                    continue
                if active_created_before and note_created_date > active_created_before:
                    continue

                # Apply Modified Date Filters
                if active_modified_after and note_updated_date < active_modified_after:
                    continue
                if (
                    active_modified_before
                    and note_updated_date > active_modified_before
                ):
                    continue

                # If all checks pass, add to results
                date_filtered_notes.append(note)
                current_processed_ids_date_filter.add(note.id)

            notes_to_render = date_filtered_notes
            processed_ids_for_hierarchy = (
                current_processed_ids_date_filter  # Update with date filter results
            )

        # Collect all parent folders of the filtered notes to ensure they are displayed
        hierarchy_to_display_ids = set(
            processed_ids_for_hierarchy
        )  # Start with the notes themselves
        for note_id in processed_ids_for_hierarchy:
            note_item = self.notes_data_index.get(note_id)
            if not note_item:  # Check if the note_item exists
                self.logger.warning(
                    f"_refresh_sidebar_list: Note ID {note_id} from processed_ids_for_hierarchy not found in notes_data_index."
                )
                continue  # Skip if ID not found in index

            parent_id = note_item.parent_id
            while parent_id:
                hierarchy_to_display_ids.add(parent_id)
                parent_item_obj = self.notes_data_index.get(
                    parent_id
                )  # Renamed to avoid conflict
                if parent_item_obj:
                    parent_id = parent_item_obj.parent_id
                else:
                    self.logger.warning(
                        f"_refresh_sidebar_list: Parent ID {parent_id} not found in notes_data_index while tracing hierarchy for {note_id}."
                    )
                    break  # Should not happen in consistent data

        # Final list of items to consider for tree building includes filtered notes and their ancestor folders
        final_items_for_tree_building = [
            self.notes_data_index[id_]
            for id_ in hierarchy_to_display_ids
            if id_ in self.notes_data_index
        ]
        # Also add any folders that were not picked up as ancestors but should be displayed if they are empty and search/tag filters are off
        if not self.active_search_query and not self.active_tag_filter:
            all_items_display = self.notes
        else:  # Only display items that are part of the hierarchy or are folders and might become visible
            # We need to ensure all folders are potentially available for the tree builder, then it will hide empty ones if they have no filtered children.
            all_items_display = [
                n for n in self.notes if n.is_folder or n.id in hierarchy_to_display_ids
            ]

        self.logger.info(
            f"Refreshing sidebar. Items to render: {len(all_items_display)} after filters."
        )
        if not dpg.does_item_exist(self.sidebar_list_tag):
            self.logger.error(
                f"Sidebar list tag '{self.sidebar_list_tag}' does not exist. Cannot refresh.",
            )
            return

        dpg.delete_item(self.sidebar_list_tag, children_only=True)

        if not all_items_display:
            dpg.add_text(
                "No notes match filters or no notes yet.", parent=self.sidebar_list_tag
            )
            self.logger.debug("No notes to display in sidebar after filtering.")
            return

        items_by_parent: Dict[Optional[str], List[Note]] = {}
        for note in all_items_display:  # Use the filtered list here
            # Only add note to items_by_parent if it's a folder OR it passed the filters
            if note.is_folder or note.id in hierarchy_to_display_ids:
                items_by_parent.setdefault(note.parent_id, []).append(note)

        for parent_id in items_by_parent:
            items_by_parent[parent_id].sort(
                key=lambda x: (not x.is_folder, x.title.lower()),
            )

        self._build_sidebar_tree_recursive(
            dpg_parent_tag=self.sidebar_list_tag,
            current_item_parent_id=None,
            items_by_parent=items_by_parent,
            # Pass the set of specifically matched notes to ensure they are not filtered out by tree recursion if they are empty folders
            # This is now handled by `all_items_display` and `hierarchy_to_display_ids` logic above
            # so `_build_sidebar_tree_recursive` doesn't need extra filter params.
        )
        self.logger.debug("Sidebar refresh complete with filters applied.")

    def _build_sidebar_tree_recursive(
        self,
        dpg_parent_tag: Union[int, str],
        current_item_parent_id: Optional[str],
        items_by_parent: Dict[Optional[str], List[Note]],
        # originally_matched_ids: set[str] # Removed this, logic handled before call
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
                    duration_ms=3000,
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
                        duration_ms=3000,
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
            # Corrected Note instantiation
            note_base_data = {
                "title": title.strip(),
                "content": "",  # Empty content for new notes/folders
                "tags": [],
                "parent_id": actual_parent_id,
                "is_folder": is_folder,
                "order": new_order,
                "icon": default_icon,
                # linked_note_ids and attachments will use default_factory
            }
            new_note = Note(id=new_item_id, **note_base_data)

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
                    duration_ms=3000,
                    level="info",
                )
        except ValidationError as ve:
            self.logger.error(
                f"Validation error creating new item: {ve}",
                exc_info=True,
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error creating item: {ve}",
                    duration_ms=5000,
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
                    duration_ms=5000,
                    level="error",
                )

    def _open_editor_for_note(self, note_id: str):
        self.logger.debug(f"Opening editor for note ID: {note_id}")
        note = self.notes_data_index.get(note_id)
        if not note:
            self.logger.error(
                f"Note with ID '{note_id}' not found. Cannot open editor."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: Note '{note_id}' not found.",
                    duration_ms=5000,
                    level="error",
                )
            return
        if note.is_folder:
            self.logger.warning(
                f"Attempted to open editor for folder '{note.title}'. This action is for notes only."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Cannot edit a folder in the note editor.",
                    duration_ms=5000,
                    level="warning",
                )
            return

        self.current_editing_note_id = note_id
        dpg.set_value(self.editor_title_input_tag, note.title)
        dpg.set_value(self.editor_content_input_tag, note.content)
        dpg.set_value(self.editor_tags_input_tag, ", ".join(note.tags or []))

        self._refresh_editor_linked_notes_display(note_id)  # Populate linked notes
        self._refresh_editor_attachments_display(note_id)  # Populate attachments

        if not dpg.does_item_exist(self.editor_window_tag):
            self.logger.error("Editor window tag does not exist. Defining it.")
            self._define_editor_window()  # Should have been defined at init

        dpg.configure_item(
            self.editor_window_tag, show=True, label=f"Edit: {note.title[:50]}"
        )
        dpg.focus_item(self.editor_content_input_tag)
        self.logger.info(f"Editor opened for note: '{note.title}'.")

    def _save_note_from_editor(self, sender=None, app_data=None, user_data=None):
        if not self.current_editing_note_id:
            self.logger.error("Save attempt failed: No note is currently being edited.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: No note selected for saving.",
                    duration_ms=5000,
                    level="error",
                )
            return

        note_to_update = self.notes_data_index.get(self.current_editing_note_id)
        if not note_to_update:
            self.logger.error(
                f"Save attempt failed: Note with ID '{self.current_editing_note_id}' not found in index."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Note data not found for saving.",
                    duration_ms=5000,
                    level="error",
                )
            return

        new_title = dpg.get_value(self.editor_title_input_tag).strip()
        new_content = dpg.get_value(
            self.editor_content_input_tag
        )  # Keep whitespace as is
        new_tags_str = dpg.get_value(self.editor_tags_input_tag).strip()

        if not new_title:
            self.logger.warning("Note title cannot be empty.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Note title cannot be empty!", duration_ms=3000, level="warning"
                )
            dpg.focus_item(self.editor_title_input_tag)
            return

        # linked_note_ids are modified directly on the note_to_update object by helper functions
        # so they are already part of the note_to_update model.

        update_data = {
            "title": new_title,
            "content": new_content,
            "tags": [tag.strip() for tag in new_tags_str.split(",") if tag.strip()],
            "updated_at": datetime.now(timezone.utc),
            # linked_note_ids will be saved as part of the note_to_update model
        }

        try:
            # Create a new Note object with the updated data
            # This ensures that linked_note_ids on note_to_update is preserved if it was changed
            updated_note = note_to_update.model_copy(update=update_data)

            # Update in self.notes list
            for i, n in enumerate(self.notes):
                if n.id == self.current_editing_note_id:
                    self.notes[i] = updated_note
                    break
            # Update in index
            self.notes_data_index[self.current_editing_note_id] = updated_note

            self._save_notes()
            self._update_internal_structures()
            self._refresh_sidebar_list()  # Update sidebar

            # Also refresh the linked notes display in case titles changed, though not strictly necessary here
            # self._refresh_editor_linked_notes_display(self.current_editing_note_id)

            dpg.configure_item(
                self.editor_window_tag, label=f"Edit: {updated_note.title[:50]}"
            )  # Update editor title
            self.logger.info(
                f"Note '{updated_note.title}' (ID: {self.current_editing_note_id}) saved successfully."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Note '{updated_note.title}' saved.",
                    duration_ms=3000,
                    level="info",
                )

        except ValidationError as ve:
            self.logger.error(
                f"Validation error saving note {self.current_editing_note_id}: {ve}"
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error saving note: Validation failed. Check logs.",
                    duration_ms=5000,
                    level="error",
                )
        except Exception as e:
            self.logger.error(
                f"Unexpected error saving note {self.current_editing_note_id}: {e}",
                exc_info=True,
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
            # Update selection state for sidebar highlighting (if any)
            self.currently_selected_sidebar_note_id = item_id
            self._render_note_in_main_view(item_id)
            # self._refresh_sidebar_list() # Call refresh_sidebar_list to update selection highlight. Consider if too slow.
            if item.is_folder:
                self.logger.debug(
                    f"Folder '{item.title}' clicked. Main view updated to folder placeholder."
                )
            else:
                self.logger.info(
                    f"Note '{item.title}' selected. Displaying in main view area."
                )
        else:
            self.logger.warning(f"Selected item_id '{item_id}' not found in index.")
            self.currently_selected_sidebar_note_id = None
            self._render_note_in_main_view(None)  # Clear main view

        # Smart refresh: only refresh sidebar if selection actually changed something visual or if filters need re-eval for highlight
        # For now, let _render_note_in_main_view handle view updates. Sidebar refresh is complex for just selection.
        # A dedicated _update_sidebar_selection_highlight(item_id) would be better if DPG allows easy styling of tree/selectable.
        # For now, we rely on the fact that tree nodes might show selection implicitly.

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
                label="Open",
                callback=self._context_open_note_action,
                user_data=item_id,
                parent=self.context_menu_tag,
            )
            dpg.add_menu_item(
                label="Edit",
                callback=self._context_edit_note_action,
                user_data=item_id,
                parent=self.context_menu_tag,
            )
        # Common actions for both notes and folders
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
        dpg.add_menu_item(
            label="Move To...",
            callback=self._context_move_action,
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

        dpg.configure_item(self.context_menu_tag, show=True)

    # --- Context Menu Actions ---
    def _context_open_note_action(self, sender, app_data, item_id: str):
        """Handles the 'Open' action for a note from the context menu."""
        self.logger.debug(f"Context menu: Open Note for {item_id}")
        item = self.notes_data_index.get(item_id)
        if item and not item.is_folder:
            # For now, open also means edit
            self._open_editor_for_note(item_id)
        elif item and item.is_folder:
            self.logger.debug(
                f"Context menu: 'Open' on folder {item_id} - no specific action, expansion is via tree node click."
            )
            # Optionally, ensure folder is expanded if DPG allows programmatic control here
        else:
            self.logger.warning(
                f"Context menu: Open Note action for non-existent item {item_id}"
            )

    def _context_edit_note_action(self, sender, app_data, item_id: str):
        """Handles the 'Edit' action for a note from the context menu."""
        self.logger.debug(f"Context menu: Edit Note for {item_id}")
        item = self.notes_data_index.get(item_id)
        if item and not item.is_folder:
            self._open_editor_for_note(item_id)
        elif item and item.is_folder:
            self.logger.warning(
                f"Context menu: 'Edit' on folder {item_id} - this should be handled by 'Rename'."
            )
            # Folders are "edited" by renaming. This option ideally shouldn't show for folders if "Edit" implies content edit.
            # However, current logic shows "Edit" only if NOT a folder, so this branch is defensive.
        else:
            self.logger.warning(
                f"Context menu: Edit Note action for non-existent item {item_id}"
            )

    def _context_rename_action(self, sender, app_data, item_id: str):
        self.logger.debug(f"Context menu: Rename for {item_id}")
        item = self.notes_data_index.get(item_id)
        if item and hasattr(self.dialog_manager, "show_rename_item_dialog"):
            self.dialog_manager.show_rename_item_dialog(item)
        elif hasattr(self.core, "gui_manager") and self.core.gui_manager:
            self.core.gui_manager.show_toast(
                f"Error: Item {item_id} not found for rename.",
                duration_ms=4000,
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
                duration_ms=4000,
                level="error",
            )

    def _context_new_note_in_folder_action(
        self,
        sender,
        app_data,
        parent_folder_id: str,
    ):
        self.logger.debug(f"Context menu: New Note in folder {parent_folder_id}")
        self.pending_new_item_parent_id = parent_folder_id
        self.pending_new_item_is_folder = False
        if hasattr(self.dialog_manager, "show_new_item_dialog"):
            self.dialog_manager.show_new_item_dialog(
                is_folder=False,
                parent_id_to_select=parent_folder_id,
            )

    def _context_new_folder_in_folder_action(
        self,
        sender,
        app_data,
        parent_folder_id: str,
    ):
        self.logger.debug(f"Context menu: New Subfolder in folder {parent_folder_id}")
        self.pending_new_item_parent_id = parent_folder_id
        self.pending_new_item_is_folder = True
        if hasattr(self.dialog_manager, "show_new_item_dialog"):
            self.dialog_manager.show_new_item_dialog(
                is_folder=True,
                parent_id_to_select=parent_folder_id,
            )

    def _context_move_action(self, sender, app_data, item_id: str):
        """Handles the 'Move To...' action from the context menu."""
        self.logger.debug(f"Context menu: Move To... for {item_id}")
        item = self.get_item_by_id(item_id)
        if item and hasattr(self.dialog_manager, "show_move_item_dialog"):
            self.dialog_manager.show_move_item_dialog(item)
            # The dialog manager will eventually call self.execute_move_item
        elif not item:
            self.logger.error(
                f"Context menu: Cannot move item {item_id} - item not found."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error: Item {item_id} not found for move.",
                    duration_ms=5000,
                    level="error",
                )
        else:  # Item exists but dialog_manager is not configured
            self.logger.error(
                f"Context menu: DialogManager does not have show_move_item_dialog method."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Move functionality not fully configured.",
                    duration_ms=5000,
                    level="error",
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
                    duration_ms=3000,
                    level="warning",
                )
            return

        item_to_rename = self.get_item_by_id(item_id)
        if not item_to_rename:
            self.logger.error(f"Cannot rename: Item with ID '{item_id}' not found.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Item not found for renaming.",
                    duration_ms=4000,
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
                    duration_ms=3000,
                    level="success",
                )
        except ValidationError as ve:
            self.logger.error(f"Validation error renaming item: {ve}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error renaming item: {ve}",
                    duration_ms=5000,
                    level="error",
                )
        except Exception as e:
            self.logger.error(f"Unexpected error renaming item: {e}", exc_info=True)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "An unexpected error occurred during rename. See logs.",
                    duration_ms=5000,
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
                    duration_ms=3000,
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
                        if child.is_folder:  # If child is a folder, add its ID to the queue to process its children
                            queue.append(child.id)

        self.logger.debug(
            f"Items identified for deletion (including children if folder): {items_to_delete_ids}",
        )

        # Filter self.notes to keep only items NOT in items_to_delete_ids
        original_count = len(self.notes)
        self.notes = [note for note in self.notes if note.id not in items_to_delete_ids]
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
                    duration_ms=3000,
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

    def execute_move_item(self, item_id: str, new_parent_id: Optional[str]):
        """Executes the move of an item to a new parent folder."""
        self.logger.info(
            f"Executing move for item ID '{item_id}' to parent ID '{new_parent_id}'"
        )
        item_to_move = self.get_item_by_id(item_id)

        if not item_to_move:
            self.logger.error(f"Cannot move: Item with ID '{item_id}' not found.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Item not found for moving.", duration_ms=5000, level="error"
                )
            return

        # Prevent moving a folder into itself or one of its children (cyclical dependency)
        if item_to_move.is_folder and new_parent_id:
            current_parent_id_trace = new_parent_id
            while current_parent_id_trace:
                if current_parent_id_trace == item_id:
                    self.logger.error(
                        f"Cannot move folder '{item_to_move.title}' ({item_id}) into itself or a child folder."
                    )
                    if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                        self.core.gui_manager.show_toast(
                            "Error: Cannot move folder into itself or a subfolder.",
                            duration_ms=5000,
                            level="error",
                        )
                    return
                parent_item = self.get_item_by_id(current_parent_id_trace)
                current_parent_id_trace = parent_item.parent_id if parent_item else None

        # Ensure the new parent ID is valid (exists and is a folder, or None for root)
        if new_parent_id:
            target_parent_item = self.get_item_by_id(new_parent_id)
            if not target_parent_item or not target_parent_item.is_folder:
                self.logger.error(
                    f"Cannot move: Target parent ID '{new_parent_id}' is not a valid folder or does not exist."
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Error: Invalid target folder for move.",
                        duration_ms=5000,
                        level="error",
                    )
                return

        try:
            # Using model_copy(update=...) for Pydantic models is safer for updates
            updated_data = {
                "parent_id": (
                    new_parent_id if new_parent_id != self.ROOT_SENTINEL_VALUE else None
                ),
                "updated_at": datetime.now(timezone.utc),
            }
            # If you have an 'order' field that needs resetting on move, handle it here.
            # For example: updated_data["order"] = new_order_value

            # Update the actual item in the list self.notes
            for i, note in enumerate(self.notes):
                if note.id == item_id:
                    # Pydantic models are immutable by default unless configured otherwise.
                    # Create a new instance with updated values.
                    updated_note = note.model_copy(update=updated_data)
                    self.notes[i] = updated_note
                    # Update index
                    self.notes_data_index[item_id] = updated_note
                    break
            else:  # Should not happen if item_to_move was found
                self.logger.error(f"Item {item_id} disappeared during move operation.")
                return

            self._save_notes()
            self._refresh_sidebar_list()
            # Potentially refresh main content if the moved item was open
            self.logger.info(
                f"Item '{item_to_move.title}' moved successfully to parent '{new_parent_id}'."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Item '{item_to_move.title}' moved.",
                    duration_ms=3000,
                    level="info",
                )

        except Exception as e:
            self.logger.error(
                f"Error during move operation for item '{item_id}': {e}", exc_info=True
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Could not move item.", duration_ms=5000, level="error"
                )

    def _apply_tag_filter_from_input(self, sender=None, app_data=None, user_data=None):
        filter_value = dpg.get_value(self.tag_filter_input_tag)
        self.logger.debug(f"Tag filter input changed: '{filter_value}'")
        self.active_tag_filter = filter_value.strip() if filter_value else None
        self._refresh_sidebar_list()

    def _apply_sidebar_search_filter(self, sender=None, app_data=None, user_data=None):
        search_value = dpg.get_value(self.sidebar_search_input_tag)
        self.logger.debug(f"Sidebar search input: '{search_value}'")
        self.active_search_query = (
            search_value.strip().lower() if search_value else None
        )
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

    def _render_note_in_main_view(self, note_id: Optional[str]):
        if not dpg.does_item_exist(self.main_content_display_group_tag):
            self.logger.error(
                f"Main content display group '{self.main_content_display_group_tag}' does not exist."
            )
            return

        dpg.delete_item(self.main_content_display_group_tag, children_only=True)

        note = self.get_item_by_id(note_id) if note_id else None

        if not note or note.is_folder:
            self.currently_viewed_note_id = None
            dpg.add_text(
                (
                    "Select a note from the sidebar to view its content."
                    if not (note and note.is_folder)
                    else f"Folder '{note.title}' selected. Select a note to view."
                ),
                parent=self.main_content_display_group_tag,
                tag=self.main_content_placeholder_text_tag,  # Re-add placeholder
            )
            if note and note.is_folder:
                self.logger.debug(
                    f"Folder '{note.title}' selected, showing placeholder in main view."
                )
            else:
                self.logger.debug(
                    "No note/invalid note selected, showing placeholder in main view."
                )
            return

        self.currently_viewed_note_id = note_id
        self.logger.debug(
            f"Rendering note '{note.title}' (ID: {note_id}) in main view area."
        )

        with dpg.child_window(
            parent=self.main_content_display_group_tag,
            border=False,
            width=-1,
            height=-1,
        ):
            dpg.add_text(
                f"Title: {note.title}", tag=self.main_content_title_tag, wrap=-1
            )  # Wrap within child window width
            dpg.add_text(
                f"Tags: {', '.join(note.tags) if note.tags else 'No tags'}",
                tag=self.main_content_tags_tag,
            )
            dpg.add_separator()
            dpg.add_text("Content:")
            dpg.add_input_text(
                tag=self.main_content_text_input_tag,
                default_value=note.content,
                multiline=True,
                readonly=True,
                width=-1,
                height=(dpg.get_item_height(self.main_content_display_group_tag) or 600)
                // 3,  # Added fallback
            )

            dpg.add_separator()
            dpg.add_text("Linked Notes:")
            with dpg.child_window(
                tag=self.main_content_linked_list_tag, height=100, border=True
            ):
                if not note.linked_note_ids:
                    dpg.add_text("No linked notes.")
                else:
                    for linked_id in note.linked_note_ids:
                        linked_note = self.get_item_by_id(linked_id)
                        display_title = (
                            f"{linked_note.title}"
                            if linked_note
                            else f"ID: {linked_id} (Not Found)"
                        )
                        if linked_note and not linked_note.is_folder:
                            dpg.add_button(
                                label=display_title,
                                user_data=linked_id,
                                callback=self._jump_to_linked_note_main_view,
                                width=-1,
                            )
                        else:
                            dpg.add_text(
                                display_title
                                if linked_note
                                else f"Invalid Link (Folder/Missing): {linked_id}"
                            )

            # Display Attachments in Main View
            dpg.add_separator()
            dpg.add_text("Attachments:")
            # Tag for main view attachments list
            main_view_attachments_list_tag = (
                f"{self.module_tag}_main_view_attachments_list"
            )
            with dpg.child_window(
                tag=main_view_attachments_list_tag, height=100, border=True
            ):
                if not note.attachments:
                    dpg.add_text("No attachments.")
                else:
                    for att in note.attachments:
                        with dpg.group(horizontal=True):
                            dpg.add_text(
                                f"{att.original_name} ({att.size_bytes // 1024 if att.size_bytes else 0} KB)"
                            )
                            dpg.add_button(
                                label="Open",
                                user_data=att.id,
                                callback=self._open_attachment_from_main_view,
                                small=True,
                            )
                            # No remove from main view for now, only from editor

    def _jump_to_linked_note_main_view(self, sender, app_data, user_data: str):
        linked_note_id = user_data
        self.logger.debug(f"Jumping to linked note from main view: {linked_note_id}")
        target_note = self.get_item_by_id(linked_note_id)
        if target_note and not target_note.is_folder:
            self._render_note_in_main_view(
                linked_note_id
            )  # Re-render main view for the new note
            # Try to highlight in sidebar (best effort, might need more robust state management with sidebar refresh)
            if self.currently_selected_sidebar_note_id != linked_note_id:
                self.currently_selected_sidebar_note_id = linked_note_id
                # This will rebuild sidebar, potentially losing scroll / open states.
                self._refresh_sidebar_list()
        elif target_note and target_note.is_folder:
            self.logger.info(
                f"Linked item {linked_note_id} is a folder. Cannot 'jump to' in editor context."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"'{target_note.title}' is a folder.",
                    duration_ms=3000,
                    level="info",
                )
        else:
            self.logger.warning(
                f"Could not jump to linked note {linked_note_id}, not found or invalid."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Linked note (ID: {linked_note_id}) not found.",
                    duration_ms=3000,
                    level="warning",
                )

    def _open_attachment_from_main_view(self, sender, app_data, attachment_id: str):
        if not self.currently_viewed_note_id:
            return
        note = self.get_item_by_id(self.currently_viewed_note_id)
        if not note:
            return

        attachment_to_open = next(
            (att for att in note.attachments if att.id == attachment_id), None
        )
        if attachment_to_open:
            file_to_open = self.assets_path / attachment_to_open.stored_filename
            if file_to_open.exists():
                try:
                    import os
                    import subprocess
                    import sys  # Required for sys.platform

                    if os.name == "nt":  # Windows
                        os.startfile(file_to_open)
                    elif os.name == "posix":  # macOS, Linux
                        subprocess.call(
                            ("open", file_to_open)
                            if sys.platform == "darwin"
                            else ("xdg-open", file_to_open)
                        )
                    self.logger.info(
                        f"Attempting to open attachment from main view: {file_to_open}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Could not open attachment {file_to_open} from main view: {e}"
                    )
                    if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                        self.core.gui_manager.show_toast(
                            f"Could not open file: {e}", level="error"
                        )
            else:
                self.logger.error(
                    f"Attachment file not found for main view: {file_to_open}"
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Attachment file missing!", level="error"
                    )
        else:
            self.logger.warning(
                f"Attachment ID {attachment_id} not found in current note for opening from main view."
            )

    def _handle_add_attachment_callback(self, sender, app_data, user_data):
        # app_data: {'file_path_name': 'path/to/file', 'file_name': 'file', 'current_path': 'path/to', ...}
        # For multi-select, app_data['selections'] would be a dict: {'filename1': 'path1', 'filename2': 'path2'}
        if not self.current_editing_note_id:
            self.logger.error(
                "Cannot add attachment: No note is currently being edited."
            )
            return

        if not app_data or not app_data.get("file_path_name"):
            self.logger.info("Add attachment dialog cancelled or no file selected.")
            return

        selected_file_path = Path(app_data["file_path_name"])
        original_file_name = selected_file_path.name

        # Create unique stored filename
        unique_id = str(uuid.uuid4())
        stored_filename = f"{unique_id}_{original_file_name}"
        destination_path = self.assets_path / stored_filename

        try:
            # Copy file to assets directory
            # Using shutil for more robust copy
            import shutil

            shutil.copy2(selected_file_path, destination_path)
            self.logger.info(
                f"Copied attachment '{original_file_name}' to '{destination_path}'"
            )

            file_size = destination_path.stat().st_size
            # TODO: Mime type detection (e.g. using 'mimetypes' library)
            # import mimetypes
            # mime_type, _ = mimetypes.guess_type(destination_path)
            mime_type = "application/octet-stream"  # Placeholder

            attachment_data = FileAttachment(
                original_name=original_file_name,
                stored_filename=stored_filename,
                mime_type=mime_type,
                size_bytes=file_size,
            )

            note = self.notes_data_index.get(self.current_editing_note_id)
            if note:
                note.attachments.append(attachment_data)
                note.updated_at = datetime.now(timezone.utc)
                self._refresh_editor_attachments_display(self.current_editing_note_id)
                self.logger.info(
                    f"Attachment '{original_file_name}' added to note '{note.title}'."
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        f"Attachment '{original_file_name}' added.", level="success"
                    )
            else:
                self.logger.error(
                    f"Failed to add attachment: Current editing note {self.current_editing_note_id} not found."
                )
                # Clean up copied file if note not found?
                if destination_path.exists():
                    destination_path.unlink(missing_ok=True)

        except Exception as e:
            self.logger.error(
                f"Error adding attachment '{original_file_name}': {e}", exc_info=True
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error adding attachment: {e}", level="error"
                )
            if destination_path.exists():  # Ensure cleanup on error
                destination_path.unlink(missing_ok=True)

    def _refresh_editor_attachments_display(self, current_note_id: Optional[str]):
        if not current_note_id:
            if dpg.does_item_exist(self.editor_attachments_list_tag):
                dpg.delete_item(self.editor_attachments_list_tag, children_only=True)
            return

        note = self.notes_data_index.get(current_note_id)
        if not dpg.does_item_exist(self.editor_attachments_list_tag):
            self.logger.error(
                f"Editor attachments list tag '{self.editor_attachments_list_tag}' does not exist."
            )
            return

        dpg.delete_item(self.editor_attachments_list_tag, children_only=True)

        if not note or not note.attachments:
            dpg.add_text("No attachments.", parent=self.editor_attachments_list_tag)
            return

        for att in note.attachments:
            with dpg.group(
                horizontal=True, parent=self.editor_attachments_list_tag
            ) as att_group:
                # dpg.add_text(f"{att.original_name} ({att.size_bytes // 1024 if att.size_bytes else 0} KB)")
                # Instead of text and then buttons, make the text part of a button or selectable for tooltip on whole item
                att_display_label = f"{att.original_name} ({att.size_bytes // 1024 if att.size_bytes else 0} KB)"
                # Using a disabled button or selectable to make it part of the group for tooltip, but not directly interactive itself
                main_label_item = dpg.add_text(
                    att_display_label
                )  # Changed to simple text, tooltip on group

                with dpg.tooltip(att_group):
                    dpg.add_text(f"File: {att.original_name}")
                    dpg.add_text(f"Size: {att.size_bytes} bytes")
                    dpg.add_text(
                        f"Type: {att.mime_type if att.mime_type else 'Unknown'}"
                    )
                    dpg.add_text(f"Stored as: {att.stored_filename}")

                open_btn = dpg.add_button(
                    label="Open",
                    user_data=att.id,
                    callback=self._open_attachment_from_editor,
                    small=True,
                )
                with dpg.tooltip(open_btn):
                    dpg.add_text(
                        "Open this attachment with the default system application."
                    )

                remove_btn = dpg.add_button(
                    label="X",
                    user_data=(current_note_id, att.id),
                    callback=self._remove_attachment_from_editor_callback,
                    small=True,
                )
                with dpg.tooltip(remove_btn):
                    dpg.add_text(
                        "Remove this attachment from the note (deletes the file). Warn: Irreversible."
                    )

    def _open_attachment_from_editor(self, sender, app_data, attachment_id: str):
        if not self.currently_viewed_note_id:
            return
        note = self.get_item_by_id(self.currently_viewed_note_id)
        if not note:
            return

        attachment_to_open = next(
            (att for att in note.attachments if att.id == attachment_id), None
        )
        if attachment_to_open:
            file_to_open = self.assets_path / attachment_to_open.stored_filename
            if file_to_open.exists():
                try:
                    import os
                    import subprocess
                    import sys  # Required for sys.platform

                    if os.name == "nt":  # Windows
                        os.startfile(file_to_open)
                    elif os.name == "posix":  # macOS, Linux
                        subprocess.call(
                            ("open", file_to_open)
                            if sys.platform == "darwin"
                            else ("xdg-open", file_to_open)
                        )
                    self.logger.info(
                        f"Attempting to open attachment from main view: {file_to_open}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Could not open attachment {file_to_open} from main view: {e}"
                    )
                    if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                        self.core.gui_manager.show_toast(
                            f"Could not open file: {e}", level="error"
                        )
            else:
                self.logger.error(
                    f"Attachment file not found for main view: {file_to_open}"
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Attachment file missing!", level="error"
                    )
        else:
            self.logger.warning(
                f"Attachment ID {attachment_id} not found in current note for opening from main view."
            )

    def _remove_attachment_from_editor_callback(
        self, sender, app_data, user_data: tuple[str, str]
    ):
        current_note_id, attachment_id_to_remove = user_data
        note = self.notes_data_index.get(current_note_id)
        if note:
            original_len = len(note.attachments)
            attachment_to_delete = next(
                (att for att in note.attachments if att.id == attachment_id_to_remove),
                None,
            )

            if attachment_to_delete:
                note.attachments = [
                    att for att in note.attachments if att.id != attachment_id_to_remove
                ]
                if len(note.attachments) < original_len:
                    note.updated_at = datetime.now(timezone.utc)
                    # Delete file from assets directory
                    file_to_delete = (
                        self.assets_path / attachment_to_delete.stored_filename
                    )
                    if file_to_delete.exists():
                        try:
                            file_to_delete.unlink()
                            self.logger.info(
                                f"Deleted attachment file: {file_to_delete}"
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Error deleting attachment file {file_to_delete}: {e}"
                            )
                    else:
                        self.logger.warning(
                            f"Attachment file not found for deletion: {file_to_delete}"
                        )

                    self._refresh_editor_attachments_display(current_note_id)
                    self.logger.info(
                        f"Removed attachment {attachment_id_to_remove} from note {current_note_id}."
                    )
                    if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                        self.core.gui_manager.show_toast(
                            f"Attachment '{attachment_to_delete.original_name}' removed.",
                            level="info",
                        )
            else:
                self.logger.warning(
                    f"Attachment {attachment_id_to_remove} not found on note {current_note_id} for removal."
                )
        else:
            self.logger.warning(
                f"Failed to remove attachment: Note {current_note_id} not found."
            )

    # --- Import/Export Logic ---
    def _perform_export(self, sender, app_data, user_data):
        self.logger.debug(f"Export file dialog callback. AppData: {app_data}")
        if not app_data or not app_data.get("file_path_name"):
            self.logger.warning("Export cancelled or no file path selected.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Export cancelled.", duration_ms=2000, level="info"
                )
            return

        file_path = app_data["file_path_name"]
        self.logger.info(
            f"Attempting to export {len(self.notes)} notes to: {file_path}"
        )

        try:
            notes_to_export = [note.model_dump(mode="json") for note in self.notes]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(notes_to_export, f, indent=4)
            self.logger.info(f"Successfully exported notes to {file_path}")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Notes exported to {file_path}", duration_ms=3000, level="success"
                )
        except Exception as e:
            self.logger.error(
                f"Error exporting notes to {file_path}: {e}", exc_info=True
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error exporting notes: {e}", duration_ms=5000, level="error"
                )

    def _perform_import(self, sender, app_data, user_data):
        self.logger.debug(f"Import file dialog callback. AppData: {app_data}")
        if not app_data or not app_data.get("file_path_name"):
            self.logger.warning("Import cancelled or no file path selected.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Import cancelled.", duration_ms=2000, level="info"
                )
            return

        file_path = app_data["file_path_name"]
        self.logger.info(f"Attempting to import notes from: {file_path}")
        imported_count = 0
        skipped_count = 0
        id_collision_new_id_count = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data_from_file = json.load(f)

            if not isinstance(data_from_file, list):
                self.logger.error("Import failed: JSON root is not a list.")
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Import failed: Invalid file format (not a list).",
                        duration_ms=3000,
                        level="error",
                    )
                return

            new_notes_to_add = []
            for item_dict in data_from_file:
                if not isinstance(item_dict, dict):
                    self.logger.warning(f"Skipping item, not a dictionary: {item_dict}")
                    skipped_count += 1
                    continue

                try:
                    # Ensure all fields required by Note model are present or defaulted
                    # Pydantic will use defaults for missing fields if defined in schema
                    # Explicitly ensure new fields from current schema get defaults if not in old JSON
                    item_dict.setdefault("linked_note_ids", [])
                    item_dict.setdefault("is_folder", False)
                    item_dict.setdefault("order", 0)
                    item_dict.setdefault(
                        "icon",
                        (
                            self.ICON_NOTE_DEFAULT
                            if not item_dict.get("is_folder")
                            else self.ICON_FOLDER_DEFAULT
                        ),
                    )
                    item_dict.setdefault("parent_id", None)
                    item_dict.setdefault(
                        "created_at", datetime.now(timezone.utc).isoformat()
                    )
                    item_dict.setdefault(
                        "updated_at", datetime.now(timezone.utc).isoformat()
                    )

                    imported_id = item_dict.get("id")
                    if imported_id and imported_id in self.notes_data_index:
                        # ID collision. Generate a new ID for the imported note.
                        self.logger.warning(
                            f"ID collision for '{imported_id}'. Assigning new ID for imported note titled '{item_dict.get('title')}'."
                        )
                        item_dict["id"] = str(uuid.uuid4())
                        id_collision_new_id_count += 1
                    elif not imported_id:
                        # Ensure ID if missing
                        item_dict["id"] = str(uuid.uuid4())

                    note_obj = Note(**item_dict)
                    new_notes_to_add.append(note_obj)
                    imported_count += 1
                except ValidationError as ve:
                    self.logger.error(
                        f"Validation error for imported item: {item_dict.get('title', 'Unknown Title')}. Details: {ve}. Skipping."
                    )
                    skipped_count += 1
                except Exception as e:
                    self.logger.error(
                        f"Error processing imported item: {item_dict.get('title', 'Unknown Title')}. Error: {e}. Skipping."
                    )
                    skipped_count += 1

            if new_notes_to_add:
                self.notes.extend(new_notes_to_add)
                self._update_internal_structures()
                self._save_notes()  # Save merged data
                self._refresh_sidebar_list()

            msg = f"Import complete. Added: {imported_count}, New IDs assigned (collision): {id_collision_new_id_count}, Skipped: {skipped_count}."
            self.logger.info(msg)
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                level = "success" if imported_count > 0 else "warning"
                if skipped_count > 0 and imported_count == 0:
                    level = "error"
                self.core.gui_manager.show_toast(msg, level=level, duration_ms=7000)

        except json.JSONDecodeError:
            self.logger.error(
                f"Error decoding JSON from {file_path}. File might be corrupted."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Import failed: File is not valid JSON.",
                    duration_ms=5000,
                    level="error",
                )
        except Exception as e:
            self.logger.error(
                f"Error importing notes from {file_path}: {e}", exc_info=True
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Error importing notes: {e}", duration_ms=5000, level="error"
                )

    def _refresh_editor_linked_notes_display(self, current_note_id: Optional[str]):
        if not current_note_id:
            self.logger.warning(
                "_refresh_editor_linked_notes_display called with no current_note_id"
            )
            if dpg.does_item_exist(self.editor_linked_notes_list_tag):
                dpg.delete_item(self.editor_linked_notes_list_tag, children_only=True)
            return

        note = self.notes_data_index.get(current_note_id)
        if not note:
            # ... (error logging as before)
            if dpg.does_item_exist(self.editor_linked_notes_list_tag):
                dpg.delete_item(self.editor_linked_notes_list_tag, children_only=True)
            return

        if not dpg.does_item_exist(self.editor_linked_notes_list_tag):
            # ... (error logging as before)
            return

        dpg.delete_item(self.editor_linked_notes_list_tag, children_only=True)

        if not note.linked_note_ids:
            dpg.add_text("No linked notes.", parent=self.editor_linked_notes_list_tag)
            return

        for linked_id in note.linked_note_ids:
            linked_note = self.notes_data_index.get(linked_id)
            display_title = (
                f"{linked_note.title}"
                if linked_note
                else f"ID: {linked_id} (Not Found)"
            )

            with dpg.group(
                horizontal=True, parent=self.editor_linked_notes_list_tag
            ) as link_group_item:
                if linked_note and not linked_note.is_folder:
                    link_button = dpg.add_button(
                        label=display_title,
                        user_data=linked_id,
                        callback=self._jump_to_linked_note,
                        width=-50,
                    )  # Keep button for action
                    with dpg.tooltip(
                        link_group_item
                    ):  # Tooltip on the group for the whole line
                        dpg.add_text(f"Linked Note: {linked_note.title}")
                        dpg.add_text(f"ID: {linked_id}")
                        dpg.add_text("Click title to open, 'X' to remove link.")
                elif linked_note and linked_note.is_folder:
                    folder_text = dpg.add_text(
                        f"{display_title} (Folder - Not Clickable)",
                        parent=link_group_item,
                    )
                    with dpg.tooltip(link_group_item):
                        dpg.add_text(f"Linked Folder: {linked_note.title}")
                        dpg.add_text(f"ID: {linked_id}")
                        dpg.add_text(
                            "This is a folder and cannot be opened directly here."
                        )
                else:  # Not found
                    not_found_text = dpg.add_text(display_title, parent=link_group_item)
                    with dpg.tooltip(link_group_item):
                        dpg.add_text(
                            f"Broken Link: Note with ID {linked_id} not found."
                        )

                remove_btn = dpg.add_button(
                    label="X",
                    user_data=(current_note_id, linked_id),
                    callback=self._remove_link_from_editor_callback,
                    width=30,
                    small=True,
                    parent=link_group_item,
                )
                # Tooltip for remove button is already covered if tooltip is on link_group_item,
                # or could be specific if preferred.
                # For now, the group tooltip should cover the action of X.

    # --- Linked Notes Dialog and Callbacks (New Methods) ---
    def _show_add_link_dialog(self, sender=None, app_data=None, user_data=None):
        """Populates and shows the 'Add Link' dialog."""
        if not self.current_editing_note_id:
            self.logger.warning(
                "_show_add_link_dialog called but no note is being edited."
            )
            return

        if not dpg.does_item_exist(self.add_link_dialog_tag):
            self.logger.error(
                f"Add Link dialog tag '{self.add_link_dialog_tag}' does not exist. Defining."
            )
            # Minimal definition here, ideally defined in __init__ or a dedicated UI method
            with dpg.window(
                label="Link to Note",
                modal=True,
                show=False,
                tag=self.add_link_dialog_tag,
                width=500,
                height=400,
                pos=[300, 200],
            ):
                dpg.add_input_text(
                    label="Filter",
                    tag=self.add_link_dialog_filter_tag,
                    callback=self._filter_add_link_dialog_list,
                    width=-1,
                )
                dpg.add_listbox(
                    tag=self.add_link_dialog_listbox_tag, width=-1, num_items=10
                )
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Link Selected",
                        tag=self.add_link_dialog_link_button_tag,
                        callback=self._execute_add_link_from_dialog,
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(
                            self.add_link_dialog_tag, show=False
                        ),
                        width=-1,
                    )

        self._filter_add_link_dialog_list()  # Populate with all eligible notes initially
        dpg.configure_item(self.add_link_dialog_tag, show=True)
        dpg.focus_item(self.add_link_dialog_filter_tag)

    def _filter_add_link_dialog_list(self, sender=None, app_data=None, user_data=None):
        """Filters the listbox in the 'Add Link' dialog based on input."""
        filter_text = (
            dpg.get_value(self.add_link_dialog_filter_tag).lower()
            if dpg.does_item_exist(self.add_link_dialog_filter_tag)
            else ""
        )

        eligible_notes: List[Tuple[str, str]] = []  # (display_name, note_id)
        current_editing_note = (
            self.get_item_by_id(self.current_editing_note_id)
            if self.current_editing_note_id
            else None
        )

        for note in self.notes:
            if note.is_folder:
                continue  # Cannot link to folders
            if self.current_editing_note_id == note.id:
                continue  # Cannot link to self
            if current_editing_note and note.id in current_editing_note.linked_note_ids:
                continue  # Already linked

            if filter_text in note.title.lower():
                eligible_notes.append((note.title, note.id))

        eligible_notes.sort(key=lambda x: x[0].lower())
        display_titles = [en[0] for en in eligible_notes]

        if dpg.does_item_exist(self.add_link_dialog_listbox_tag):
            dpg.configure_item(
                self.add_link_dialog_listbox_tag,
                items=display_titles,
                user_data=eligible_notes,
            )

    def _execute_add_link_from_dialog(self, sender=None, app_data=None, user_data=None):
        """Adds the selected note from the dialog to the current note's links."""
        selected_title = dpg.get_value(self.add_link_dialog_listbox_tag)
        if not selected_title or not self.current_editing_note_id:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "No note selected to link or no current note.",
                    duration_ms=3000,
                    level="warning",
                )
            return

        listbox_user_data: List[Tuple[str, str]] = (
            dpg.get_item_user_data(self.add_link_dialog_listbox_tag) or []
        )

        note_id_to_link: Optional[str] = None
        for title, note_id_val in listbox_user_data:
            if title == selected_title:
                note_id_to_link = note_id_val
                break

        if not note_id_to_link:
            self.logger.error(
                f"Could not find ID for selected link title: {selected_title}"
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error finding note to link.", level="error"
                )
            return

        note_to_update = self.notes_data_index.get(self.current_editing_note_id)
        if note_to_update:
            if note_id_to_link not in note_to_update.linked_note_ids:
                note_to_update.linked_note_ids.append(note_id_to_link)
                note_to_update.updated_at = datetime.now(timezone.utc)
                # No explicit save here, _save_note_from_editor will handle it.
                # Or if linking should be instant: self._save_notes()

                self._refresh_editor_linked_notes_display(self.current_editing_note_id)
                self.logger.info(
                    f"Linked note {note_id_to_link} to {self.current_editing_note_id}."
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        f"Note '{selected_title}' linked.", level="success"
                    )
            else:
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    self.core.gui_manager.show_toast(
                        "Note already linked.", level="info"
                    )

        dpg.configure_item(self.add_link_dialog_tag, show=False)

    def _jump_to_linked_note(self, sender, app_data, user_data: str):
        """Handles click on a linked note in the editor's list."""
        linked_note_id = user_data
        self.logger.debug(f"Editor: Jumping to linked note ID: {linked_note_id}")
        target_note = self.get_item_by_id(linked_note_id)

        if target_note and not target_note.is_folder:
            # Option 1: Open in editor (if not already open for this note)
            # self._open_editor_for_note(linked_note_id) # This would replace current edit

            # Option 2: Display in main view and select in sidebar (consistent with main view jump)
            self._render_note_in_main_view(linked_note_id)
            if self.currently_selected_sidebar_note_id != linked_note_id:
                self.currently_selected_sidebar_note_id = linked_note_id
                # This might be too disruptive if editor is primary focus
                self._refresh_sidebar_list()

            # Option 3: If editor should stay primary focus, maybe just a toast
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Opening '{target_note.title}' in main view.",
                    duration_ms=3000,
                    level="info",
                )

        elif target_note and target_note.is_folder:
            self.logger.info(
                f"Linked item {linked_note_id} is a folder. Cannot 'jump to' in editor context."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"'{target_note.title}' is a folder.",
                    duration_ms=3000,
                    level="info",
                )
        else:
            self.logger.warning(
                f"Could not jump to linked note {linked_note_id}, not found or invalid."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Linked note (ID: {linked_note_id}) not found.",
                    duration_ms=3000,
                    level="warning",
                )

    def _remove_link_from_editor_callback(
        self, sender, app_data, user_data: tuple[str, str]
    ):
        """Removes a linked note ID from the current editing note."""
        current_note_id, linked_id_to_remove = user_data

        if not current_note_id or not linked_id_to_remove:
            self.logger.error("Invalid user_data for removing link.")
            return

        note_to_update = self.notes_data_index.get(current_note_id)
        if note_to_update:
            if linked_id_to_remove in note_to_update.linked_note_ids:
                note_to_update.linked_note_ids.remove(linked_id_to_remove)
                note_to_update.updated_at = datetime.now(timezone.utc)
                # Changes will be saved by _save_note_from_editor or an explicit save

                self._refresh_editor_linked_notes_display(current_note_id)
                self.logger.info(
                    f"Removed link to {linked_id_to_remove} from note {current_note_id}."
                )
                if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                    linked_note_obj = self.get_item_by_id(linked_id_to_remove)
                    removed_title = (
                        linked_note_obj.title
                        if linked_note_obj
                        else linked_id_to_remove
                    )
                    self.core.gui_manager.show_toast(
                        f"Link to '{removed_title}' removed.",
                        duration_ms=3000,
                        level="info",
                    )
            else:
                self.logger.warning(
                    f"Link {linked_id_to_remove} not found on note {current_note_id} for removal."
                )
        else:
            self.logger.warning(
                f"Note {current_note_id} not found, cannot remove link."
            )

    # --- Date Filter Actions ---
    def _parse_date_input(
        self, date_str: Optional[str]
    ) -> Optional[datetime.date]:  # Changed date_str to Optional[str]
        """Helper to parse YYYY-MM-DD string to date object."""
        if not date_str:  # Handles None or empty string
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            self.logger.warning(
                f"Invalid date format: {date_str}. Expected YYYY-MM-DD."
            )
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    f"Invalid date: '{date_str}'. Use YYYY-MM-DD.",
                    duration_ms=4000,
                    level="warning",
                )
            return None

    def _apply_date_filters_action(self, sender=None, app_data=None, user_data=None):
        self.logger.debug("Apply Date Filters button clicked.")
        made_change = False

        created_after_str = dpg.get_value(self.created_after_input_tag)
        created_before_str = dpg.get_value(self.created_before_input_tag)
        modified_after_str = dpg.get_value(self.modified_after_input_tag)
        modified_before_str = dpg.get_value(self.modified_before_input_tag)

        # Store raw strings, parsing will happen in _refresh_sidebar_list or a helper there.
        # This simplifies immediate validation here - if a string exists, it's a filter.
        # We only need to check for malformed strings if they try to apply.

        # Validate and store. If any date is invalid, we stop and don't apply any.
        parsed_created_after = self._parse_date_input(created_after_str)
        if created_after_str and parsed_created_after is None:
            return  # Invalid date, toast shown by helper

        parsed_created_before = self._parse_date_input(created_before_str)
        if created_before_str and parsed_created_before is None:
            return

        parsed_modified_after = self._parse_date_input(modified_after_str)
        if modified_after_str and parsed_modified_after is None:
            return

        parsed_modified_before = self._parse_date_input(modified_before_str)
        if modified_before_str and parsed_modified_before is None:
            return

        if self.created_after_filter != created_after_str:
            self.created_after_filter = created_after_str
            made_change = True
        if self.created_before_filter != created_before_str:
            self.created_before_filter = created_before_str
            made_change = True
        if self.modified_after_filter != modified_after_str:
            self.modified_after_filter = modified_after_str
            made_change = True
        if self.modified_before_filter != modified_before_str:
            self.modified_before_filter = modified_before_str
            made_change = True

        if made_change:
            self.logger.info(
                f"Date filters updated: CA: '{self.created_after_filter}', CB: '{self.created_before_filter}', MA: '{self.modified_after_filter}', MB: '{self.modified_before_filter}'. Refreshing list."
            )
            self._refresh_sidebar_list()
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Date filters applied.", duration_ms=3000, level="info"
                )
        else:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "No changes to date filters.", duration_ms=3000, level="info"
                )

    def _clear_date_filters_action(self, sender=None, app_data=None, user_data=None):
        self.logger.debug("Clear Date Filters button clicked.")
        made_change = False
        if self.created_after_filter:
            self.created_after_filter = None
            dpg.set_value(self.created_after_input_tag, "")
            made_change = True
        if self.created_before_filter:
            self.created_before_filter = None
            dpg.set_value(self.created_before_input_tag, "")
            made_change = True
        if self.modified_after_filter:
            self.modified_after_filter = None
            dpg.set_value(self.modified_after_input_tag, "")
            made_change = True
        if self.modified_before_filter:
            self.modified_before_filter = None
            dpg.set_value(self.modified_before_input_tag, "")
            made_change = True

        if made_change:
            self.logger.info("Date filters cleared. Refreshing list.")
            self._refresh_sidebar_list()
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Date filters cleared.", duration_ms=3000, level="info"
                )
        else:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "No date filters active to clear.", duration_ms=3000, level="info"
                )

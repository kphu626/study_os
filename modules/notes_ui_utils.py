from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import dearpygui.dearpygui as dpg

if TYPE_CHECKING:
    from schemas.note_schemas import Note  # Added this import

    from .notes_module import NotesModule  # Forward reference for type hinting

    # from core.app import Core # If Core access is needed directly


class NotesDialogManager:
    def __init__(self, notes_module_instance: "NotesModule"):
        self.notes_module = notes_module_instance
        self.core = self.notes_module.core  # Access core services via notes_module
        self.logger = self.notes_module.logger

        # --- Dialog DPG Tags ---
        # Unified New Item Dialog
        self.new_item_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.new_item_title_input_tag: Union[int, str] = dpg.generate_uuid()
        self.new_item_parent_dropdown_tag: Union[int, str] = dpg.generate_uuid()
        self.new_item_create_button_tag: Union[int, str] = dpg.generate_uuid()

        # Rename Item Dialog
        self.rename_item_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.rename_item_id_storage: Optional[str] = (
            None  # To store ID of item being renamed
        )
        self.rename_item_title_input_tag: Union[int, str] = dpg.generate_uuid()

        # Delete Confirmation Dialog
        self.delete_confirm_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.delete_confirm_item_id_storage: Optional[str] = None
        self.delete_confirm_text_tag: Union[int, str] = dpg.generate_uuid()

        # Move Item Dialog
        self.move_item_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.move_item_id_storage: Optional[str] = None
        self.move_item_current_item_text_tag: Union[int, str] = dpg.generate_uuid()
        self.move_item_parent_dropdown_tag: Union[int, str] = dpg.generate_uuid()
        self.move_item_confirm_button_tag: Union[int, str] = dpg.generate_uuid()

        # State for dialogs
        self.creating_folder: bool = False  # To know what the new_item_dialog is for
        self.available_folders_for_dropdown: List[
            Tuple[str, Optional[str]]
        ] = []  # Populated by NotesModule

        self._define_all_dialogs()

    def _define_all_dialogs(self):
        """Calls individual methods to define each dialog window."""
        self._define_new_item_dialog()
        self._define_rename_item_dialog()
        self._define_delete_confirmation_dialog()
        self._define_move_item_dialog()

    def _center_dialog(self, dialog_tag: Union[int, str]):
        if dpg.does_item_exist(dialog_tag):
            # Ensure dialog has explicit width/height or use get_item_rect_size
            try:
                dialog_width = dpg.get_item_configuration(dialog_tag)["width"]
                dialog_height = dpg.get_item_configuration(dialog_tag)["height"]
            except Exception:  # Changed from bare except:
                rect_size = dpg.get_item_rect_size(dialog_tag)
                dialog_width = rect_size[0]
                dialog_height = rect_size[1]

            if (
                dialog_width <= 0 or dialog_height <= 0
            ):  # If autosized and not rendered yet, might be 0
                # Use estimated reasonable defaults if size is unknown
                dialog_width = max(dialog_width, 400)
                dialog_height = max(dialog_height, 200)

            viewport_width = dpg.get_viewport_width()
            viewport_height = dpg.get_viewport_height()
            pos_x = max(0, (viewport_width - dialog_width) // 2)
            pos_y = max(0, (viewport_height - dialog_height) // 2)
            dpg.configure_item(dialog_tag, pos=[pos_x, pos_y])

    def _define_new_item_dialog(self):
        if not dpg.does_item_exist(self.new_item_dialog_tag):
            with dpg.window(
                label="Create New Item",
                modal=True,
                show=False,
                tag=self.new_item_dialog_tag,
                width=400,
                height=180,
                no_resize=True,
            ):
                dpg.add_input_text(
                    label="Title",
                    tag=self.new_item_title_input_tag,
                    width=-1,
                )
                dpg.add_text("Parent Location:")
                dpg.add_combo(
                    tag=self.new_item_parent_dropdown_tag,
                    items=[],
                    width=-1,
                )
                dpg.add_spacer(height=10)
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Create",
                        tag=self.new_item_create_button_tag,
                        callback=self._execute_create_item_dialog_callback,
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(
                            self.new_item_dialog_tag,
                            show=False,
                        ),
                        width=-1,
                    )

    def show_new_item_dialog(self, is_folder: bool, parent_id_to_select: Optional[str]):
        self.creating_folder = is_folder
        dialog_label = "Create New Folder" if is_folder else "Create New Note"
        default_title = "New Folder" if is_folder else "New Note"

        dpg.configure_item(self.new_item_dialog_tag, label=dialog_label)
        dpg.set_value(self.new_item_title_input_tag, default_title)

        self.refresh_dropdown_items_in_dialogs()  # Ensure dropdown is populated

        # Attempt to set default parent in dropdown
        selected_dropdown_label = None
        if parent_id_to_select:
            for label, item_id_val in self.available_folders_for_dropdown:
                if item_id_val == parent_id_to_select:
                    selected_dropdown_label = label
                    break
        if (
            not selected_dropdown_label
        ):  # Default to root if no override or override not found
            selected_dropdown_label = self.available_folders_for_dropdown[0][
                0
            ]  # First item is Root

        if (
            dpg.does_item_exist(self.new_item_parent_dropdown_tag)
            and selected_dropdown_label
        ):
            dpg.set_value(self.new_item_parent_dropdown_tag, selected_dropdown_label)

        self._center_dialog(self.new_item_dialog_tag)
        dpg.configure_item(self.new_item_dialog_tag, show=True)
        dpg.focus_item(self.new_item_title_input_tag)
        self.logger.debug(
            f"Showing '{dialog_label}' dialog. Pre-selected parent: {selected_dropdown_label}",
        )

    def _execute_create_item_dialog_callback(self, sender, app_data, user_data):
        title = dpg.get_value(self.new_item_title_input_tag).strip()
        selected_parent_label = dpg.get_value(self.new_item_parent_dropdown_tag)

        if not title:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Title cannot be empty.",
                    duration_ms=3000,  # GUIManager expects ms
                    level="warning",
                )
            dpg.focus_item(self.new_item_title_input_tag)
            return

        chosen_parent_id: Optional[str] = None
        for p_label, p_id_val in self.available_folders_for_dropdown:
            if p_label == selected_parent_label:
                chosen_parent_id = p_id_val
                break

        dpg.configure_item(self.new_item_dialog_tag, show=False)
        self.notes_module.execute_create_new_item(
            title,
            None,
            chosen_parent_id,
            self.creating_folder,
        )

    def _define_rename_item_dialog(self):
        if not dpg.does_item_exist(self.rename_item_dialog_tag):
            with dpg.window(
                label="Rename Item",
                modal=True,
                show=False,
                tag=self.rename_item_dialog_tag,
                width=400,
                height=150,
                no_resize=True,
            ):
                dpg.add_input_text(
                    label="New Title",
                    tag=self.rename_item_title_input_tag,
                    width=-1,
                )
                dpg.add_spacer(height=10)
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Rename",
                        callback=self._execute_rename_item_dialog_callback,
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(
                            self.rename_item_dialog_tag,
                            show=False,
                        ),
                        width=-1,
                    )

    def show_rename_item_dialog(self, item: "Note"):
        self.rename_item_id_storage = item.id
        dpg.set_value(self.rename_item_title_input_tag, item.title)

        self._center_dialog(self.rename_item_dialog_tag)
        dpg.configure_item(
            self.rename_item_dialog_tag,
            show=True,
            label=f"Rename: {item.title[:30]}",
        )
        dpg.focus_item(self.rename_item_title_input_tag)

    def _execute_rename_item_dialog_callback(self, sender, app_data, user_data):
        new_title = dpg.get_value(self.rename_item_title_input_tag).strip()

        if not self.rename_item_id_storage:
            self.logger.error("Rename item ID not found in storage.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Could not determine item to rename.",
                    duration_ms=3000,
                    level="error",
                )
            dpg.configure_item(self.rename_item_dialog_tag, show=False)
            return

        if not new_title:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "New title cannot be empty.",
                    duration_ms=3000,
                    level="warning",
                )
            dpg.focus_item(self.rename_item_title_input_tag)
            return

        dpg.configure_item(self.rename_item_dialog_tag, show=False)
        self.notes_module.execute_rename_item(
            self.rename_item_id_storage,
            new_title,
            None,  # Icon is no longer part of rename dialog
        )
        self.rename_item_id_storage = None

    def close_rename_item_dialog(self):
        """Closes the rename item dialog if it exists and is visible."""
        if dpg.does_item_exist(self.rename_item_dialog_tag) and dpg.is_item_shown(
            self.rename_item_dialog_tag
        ):
            dpg.configure_item(self.rename_item_dialog_tag, show=False)
            self.logger.debug("Rename item dialog closed.")

    def _define_delete_confirmation_dialog(self):
        if not dpg.does_item_exist(self.delete_confirm_dialog_tag):
            with dpg.window(
                label="Confirm Deletion",
                modal=True,
                show=False,
                tag=self.delete_confirm_dialog_tag,
                width=400,
                height=120,
                no_resize=True,
                no_close=True,
            ):
                dpg.add_text("Are you sure?", tag=self.delete_confirm_text_tag)
                dpg.add_spacer(height=10)
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Yes, Delete",
                        callback=self._execute_delete_confirm_dialog_callback,
                        width=-1,
                    )
                    dpg.add_button(
                        label="No, Cancel",
                        callback=lambda: dpg.configure_item(
                            self.delete_confirm_dialog_tag,
                            show=False,
                        ),
                        width=-1,
                    )

    def show_delete_confirmation_dialog(self, item: "Note"):
        self.delete_confirm_item_id_storage = item.id
        item_type = "folder" if item.is_folder else "note"
        confirmation_message = (
            f"Are you sure you want to delete the {item_type} '{item.title}'?"
        )
        if item.is_folder:
            confirmation_message += (
                "\nAll its contents will also be deleted. This cannot be undone."
            )
        else:
            confirmation_message += "\nThis action cannot be undone."
        dpg.set_value(self.delete_confirm_text_tag, confirmation_message)

        self._center_dialog(self.delete_confirm_dialog_tag)
        dpg.configure_item(self.delete_confirm_dialog_tag, show=True)

    def _execute_delete_confirm_dialog_callback(self, sender, app_data, user_data):
        if self.delete_confirm_item_id_storage:
            self.notes_module.execute_delete_item(
                self.delete_confirm_item_id_storage,
            )
            self.delete_confirm_item_id_storage = None  # Clear after use
        dpg.configure_item(self.delete_confirm_dialog_tag, show=False)

    def close_delete_item_dialog(self):
        """Closes the delete confirmation dialog if it exists and is visible."""
        if dpg.does_item_exist(self.delete_confirm_dialog_tag) and dpg.is_item_shown(
            self.delete_confirm_dialog_tag
        ):
            dpg.configure_item(self.delete_confirm_dialog_tag, show=False)
            self.logger.debug("Delete confirmation dialog closed.")

    def _define_move_item_dialog(self):
        """Defines the DPG window for moving an item (note or folder)."""
        if not dpg.does_item_exist(self.move_item_dialog_tag):
            with dpg.window(
                label="Move Item To...",
                modal=True,
                show=False,
                tag=self.move_item_dialog_tag,
                width=450,
                height=200,  # Increased height for text and dropdown
                no_resize=True,
            ):
                dpg.add_text("Moving item:", tag=self.move_item_current_item_text_tag)
                dpg.add_spacer(height=5)
                dpg.add_text("Select New Parent Folder:")
                dpg.add_combo(
                    tag=self.move_item_parent_dropdown_tag,
                    items=[],  # Populated by refresh_dropdown_items_in_dialogs
                    width=-1,
                )
                dpg.add_spacer(height=15)
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Move Item",
                        tag=self.move_item_confirm_button_tag,
                        callback=self._execute_move_item_dialog_callback,
                        width=-1,
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.configure_item(
                            self.move_item_dialog_tag,
                            show=False,
                        ),
                        width=-1,
                    )
        self.logger.debug(f"Move Item dialog ({self.move_item_dialog_tag}) defined.")

    def show_move_item_dialog(self, item: "Note"):
        """Shows the dialog to move an item to a new parent folder."""
        if not item:
            self.logger.error("show_move_item_dialog: No item provided.")
            return

        self.move_item_id_storage = item.id
        item_type_str = "Folder" if item.is_folder else "Note"

        # Update the text displaying which item is being moved
        if dpg.does_item_exist(self.move_item_current_item_text_tag):
            dpg.set_value(
                self.move_item_current_item_text_tag,
                f"Moving {item_type_str}: {item.title}",
            )

        # Populate and set the dropdown
        # Exclude the item itself and its children from the list of possible parents
        # Also exclude current parent? For now, allow moving to same parent (no-op)
        self.refresh_dropdown_items_in_dialogs(
            exclude_item_id=item.id, for_move_dialog=True
        )

        # Try to pre-select the current parent, if any, otherwise Root
        target_parent_label = (
            self.notes_module.ROOT_SENTINEL_VALUE
        )  # Default to root label
        if item.parent_id:
            for label, folder_id_val in self.available_folders_for_dropdown:
                if folder_id_val == item.parent_id:
                    target_parent_label = label
                    break

        if dpg.does_item_exist(self.move_item_parent_dropdown_tag):
            dpg.set_value(self.move_item_parent_dropdown_tag, target_parent_label)

        self._center_dialog(self.move_item_dialog_tag)
        dpg.configure_item(
            self.move_item_dialog_tag,
            show=True,
            label=f"Move {item_type_str}: {item.title[:30]}...",
        )
        self.logger.debug(
            f"Showing Move Item dialog for '{item.title}' (ID: {item.id})."
        )

    def _execute_move_item_dialog_callback(self, sender, app_data, user_data):
        """Callback for the 'Move' button in the move item dialog."""
        selected_parent_label = dpg.get_value(self.move_item_parent_dropdown_tag)

        if not self.move_item_id_storage:
            self.logger.error("Move item ID not found in storage during execute.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: Could not determine item to move.",
                    duration_ms=3000,
                    level="error",
                )
            dpg.configure_item(self.move_item_dialog_tag, show=False)
            return

        new_parent_id: Optional[str] = self.get_parent_id_from_dropdown_label(
            selected_parent_label
        )

        # The check for moving a folder into itself is done in NotesModule.execute_move_item
        # Here we just pass the selected ID (None for root)

        dpg.configure_item(self.move_item_dialog_tag, show=False)
        self.notes_module.execute_move_item(
            self.move_item_id_storage,
            new_parent_id,
        )
        self.move_item_id_storage = None  # Clear after use

    def refresh_dropdown_items_in_dialogs(
        self, exclude_item_id: Optional[str] = None, for_move_dialog: bool = False
    ):
        # This method is called by NotesModule when its folder structure might change,
        # or when a dialog needing this list is about to be shown.
        self.notes_module._populate_available_folders_for_dialog_manager(
            exclude_self_and_children_id=exclude_item_id if for_move_dialog else None
        )
        # self.available_folders_for_dropdown is now updated by the call above

        dropdown_labels = [label for label, _ in self.available_folders_for_dropdown]

        if dpg.does_item_exist(self.new_item_parent_dropdown_tag):
            current_value = dpg.get_value(self.new_item_parent_dropdown_tag)
            dpg.configure_item(self.new_item_parent_dropdown_tag, items=dropdown_labels)
            if (
                current_value in dropdown_labels
            ):  # try to preserve selection if still valid
                dpg.set_value(self.new_item_parent_dropdown_tag, current_value)
            elif dropdown_labels:
                dpg.set_value(self.new_item_parent_dropdown_tag, dropdown_labels[0])

        if dpg.does_item_exist(self.move_item_parent_dropdown_tag) and for_move_dialog:
            current_value_move = dpg.get_value(self.move_item_parent_dropdown_tag)
            # Filtered list is already set in self.available_folders_for_dropdown by the _populate call
            dpg.configure_item(
                self.move_item_parent_dropdown_tag, items=dropdown_labels
            )

            if current_value_move in dropdown_labels:  # try to preserve selection
                dpg.set_value(self.move_item_parent_dropdown_tag, current_value_move)
            elif dropdown_labels:  # set to first if previous is invalid or not set
                dpg.set_value(self.move_item_parent_dropdown_tag, dropdown_labels[0])

    def get_parent_id_from_dropdown_label(self, selected_label: str) -> Optional[str]:
        """Helper to get the actual ID or sentinel from a dropdown label."""
        for (
            label,
            id_val,
        ) in self.available_folders_for_dropdown:  # Search the currently set list
            if label == selected_label:
                return id_val
        self.logger.warning(f"Could not find ID for dropdown label: '{selected_label}'")
        return (
            self.notes_module.ROOT_SENTINEL_VALUE
        )  # Fallback to root sentinel if not found


# Removed old NotesContextMenuManager as it was a stub and context menu logic is simpler in NotesModule for now

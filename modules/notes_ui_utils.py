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
        self.new_item_icon_input_tag: Union[int, str] = dpg.generate_uuid()
        self.new_item_parent_dropdown_tag: Union[int, str] = dpg.generate_uuid()
        self.new_item_create_button_tag: Union[int, str] = dpg.generate_uuid()

        # Rename Item Dialog
        self.rename_item_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.rename_item_id_storage: Optional[str] = (
            None  # To store ID of item being renamed
        )
        self.rename_item_title_input_tag: Union[int, str] = dpg.generate_uuid()
        self.rename_item_icon_input_tag: Union[int, str] = dpg.generate_uuid()

        # Delete Confirmation Dialog
        self.delete_confirm_dialog_tag: Union[int, str] = dpg.generate_uuid()
        self.delete_confirm_item_id_storage: Optional[str] = None
        self.delete_confirm_text_tag: Union[int, str] = dpg.generate_uuid()

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

    def _center_dialog(self, dialog_tag: Union[int, str]):
        if dpg.does_item_exist(dialog_tag):
            # Ensure dialog has explicit width/height or use get_item_rect_size
            try:
                dialog_width = dpg.get_item_configuration(dialog_tag)["width"]
                dialog_height = dpg.get_item_configuration(dialog_tag)["height"]
            except Exception:  # Changed from bare except
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
                height=220,
                no_resize=True,
            ):
                dpg.add_input_text(
                    label="Title",
                    tag=self.new_item_title_input_tag,
                    width=-1,
                )
                dpg.add_input_text(
                    label="Icon (emoji)",
                    tag=self.new_item_icon_input_tag,
                    width=-1,
                    hint="e.g., ✨ or 📁",
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
        default_icon = (
            self.notes_module.ICON_FOLDER_DEFAULT
            if is_folder
            else self.notes_module.ICON_NOTE_DEFAULT
        )

        dpg.configure_item(self.new_item_dialog_tag, label=dialog_label)
        dpg.set_value(self.new_item_title_input_tag, default_title)
        dpg.set_value(self.new_item_icon_input_tag, default_icon)

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
        icon = dpg.get_value(self.new_item_icon_input_tag).strip()
        selected_parent_label = dpg.get_value(self.new_item_parent_dropdown_tag)

        if not title:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Title cannot be empty.",
                    duration=3,
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
            icon,
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
                height=180,
                no_resize=True,
            ):
                dpg.add_input_text(
                    label="New Title",
                    tag=self.rename_item_title_input_tag,
                    width=-1,
                )
                dpg.add_input_text(
                    label="New Icon (emoji)",
                    tag=self.rename_item_icon_input_tag,
                    width=-1,
                    hint="Leave blank to keep current",
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
        dpg.set_value(
            self.rename_item_icon_input_tag,
            item.icon if item.icon else "",
        )  # Show current icon or empty

        self._center_dialog(self.rename_item_dialog_tag)
        dpg.configure_item(
            self.rename_item_dialog_tag,
            show=True,
            label=f"Rename: {item.title[:30]}",
        )
        dpg.focus_item(self.rename_item_title_input_tag)

    def _execute_rename_item_dialog_callback(self, sender, app_data, user_data):
        new_title = dpg.get_value(self.rename_item_title_input_tag).strip()
        new_icon = dpg.get_value(
            self.rename_item_icon_input_tag,
        ).strip()  # Empty string if user clears it

        if not new_title:
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Title cannot be empty.",
                    duration=3,
                    level="warning",
                )
            dpg.focus_item(self.rename_item_title_input_tag)
            return

        if self.rename_item_id_storage:
            dpg.configure_item(self.rename_item_dialog_tag, show=False)
            self.notes_module.execute_rename_item(
                self.rename_item_id_storage,
                new_title,
                new_icon,
            )
        else:
            self.logger.error("Item ID for rename was not stored.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: No item selected for rename.",
                    level="error",
                )
        self.rename_item_id_storage = None  # Clear stored ID

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
            dpg.configure_item(self.delete_confirm_dialog_tag, show=False)
            self.notes_module.execute_delete_item(self.delete_confirm_item_id_storage)
        else:
            self.logger.error("Item ID for delete confirmation was not stored.")
            if hasattr(self.core, "gui_manager") and self.core.gui_manager:
                self.core.gui_manager.show_toast(
                    "Error: No item ID for deletion.",
                    level="error",
                )
        self.delete_confirm_item_id_storage = None

    def refresh_dropdown_items_in_dialogs(self):
        self.logger.debug("Refreshing dropdown items in dialogs if they exist.")
        dropdown_labels = [item[0] for item in self.available_folders_for_dropdown]
        if dpg.does_item_exist(self.new_item_parent_dropdown_tag):
            current_value = None
            try:  # Get current value if combo exists and has a value
                current_value = dpg.get_value(self.new_item_parent_dropdown_tag)
            except Exception:  # Changed from bare except
                pass  # Ignore if it fails (e.g. no items yet)

            dpg.configure_item(self.new_item_parent_dropdown_tag, items=dropdown_labels)
            if current_value and current_value in dropdown_labels:
                dpg.set_value(
                    self.new_item_parent_dropdown_tag,
                    current_value,
                )  # Try to preserve selection
            elif dropdown_labels:  # Default to first item (Root)
                dpg.set_value(self.new_item_parent_dropdown_tag, dropdown_labels[0])
        # Add for other dialogs with folder dropdowns if any (e.g., move item dialog)

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

from typing import TYPE_CHECKING, Any, Dict, Optional, Union, cast

import dearpygui.dearpygui as dpg

# Removed Flet-specific ThemeManager import
from .base_module import BaseModule

if TYPE_CHECKING:
    from core.app import Core
    from core.theme_manager import ThemeManager  # For type hinting


class SettingsModule(BaseModule):
    def __init__(self, core: "Core"):
        super().__init__(core)
        # self.light_theme_tag: Union[int, str] = 0 # Removed
        # self.dark_theme_tag: Union[int, str] = 0 # Removed
        # self.dpg_theme_radio_tag: Union[int, str] = 0 # Removed
        # self.current_theme_name: str = "Dark" # Removed, will get from ThemeManager

        self.theme_manager: Optional[ThemeManager] = None
        if hasattr(self.core, "theme_manager") and self.core.theme_manager is not None:
            self.theme_manager = self.core.theme_manager

        # Defer UUID generation - Initialize as None here
        self.dpg_theme_combo_tag: Optional[Union[int, str]] = None
        self.dpg_current_theme_text_tag: Optional[Union[int, str]] = None
        self.font_combo_tag: Union[int, str] = 0  # Assuming it will be UUID
        self.font_size_label_tag: Optional[Union[int, str]] = (
            None  # For dynamic updates if needed
        )
        self.font_size_input_tag: Union[int, str] = (
            0  # Initialize with a placeholder, will be UUID
        )

        self.dpg_status_text_tag: Optional[Union[int, str]] = None
        self.current_font_display_name: Optional[str] = None
        self._font_combo_id: Optional[Union[int, str]] = None

    def initialize_dpg_tags(self):
        """Generates DPG tags. Call after DPG context is created."""
        print("[SettingsModule.initialize_dpg_tags] Generating DPG tags...")  # ADD LOG
        self.dpg_theme_combo_tag = dpg.generate_uuid()
        self.dpg_current_theme_text_tag = dpg.generate_uuid()
        self.font_combo_tag = dpg.generate_uuid()
        self.font_size_input_tag = dpg.generate_uuid()
        self.dpg_status_text_tag = dpg.generate_uuid()
        print("[SettingsModule.initialize_dpg_tags] DPG tags generated.")  # ADD LOG

    # Flet-specific build method removed
    # def build(self):
    #     return ft.Column(...)

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the Dear PyGui view for the Settings module."""
        print("[SettingsModule.build_dpg_view] Building settings view...")

        # Ensure DPG tags are initialized before building view
        if (
            self.dpg_theme_combo_tag is None or self.font_combo_tag is None
        ):  # Added font_combo_tag check
            print(
                "[SettingsModule.build_dpg_view] DPG tags not fully initialized. Calling initialize_dpg_tags.",
            )
            self.initialize_dpg_tags()  # Initialize if they weren't already
            if (
                self.dpg_theme_combo_tag is None or self.font_combo_tag is None
            ):  # Check again
                print(
                    "[SettingsModule.build_dpg_view] CRITICAL: DPG tags still None after initialization attempt.",
                )
                with dpg.group(parent=parent_container_tag):
                    dpg.add_text(
                        "Error: Settings module critical failure.",
                        color=(255, 0, 0),
                    )
                return

        theme_names = []
        default_combo_theme = "Default Dark"  # A sensible fallback

        if self.theme_manager:
            theme_names = self.theme_manager.get_theme_names()
            current_manager_theme = self.theme_manager.get_current_theme_name()
            if current_manager_theme and current_manager_theme in theme_names:
                default_combo_theme = current_manager_theme
            elif theme_names:  # If current not set/valid, but themes exist
                default_combo_theme = theme_names[0]

        with dpg.group(parent=parent_container_tag):
            dpg.add_text(
                "Application Settings",
            )  # Removed color for now, theme will handle
            dpg.add_separator()
            dpg.add_text("Select Theme:")
            theme_combo = dpg.add_combo(
                items=theme_names,
                default_value=default_combo_theme,
                callback=self._on_theme_selected,
                tag=self.dpg_theme_combo_tag,
                width=-1,
            )
            with dpg.tooltip(theme_combo):
                dpg.add_text("Change application color theme")
                dpg.add_text("Changes take effect immediately")
            dpg.add_text(
                f"Current: {default_combo_theme}",
                tag=cast("Union[int, str]", self.dpg_current_theme_text_tag),
            )
            dpg.add_separator()
            dpg.add_text("Font Settings:")

            # Font controls
            if self.core.theme_manager:
                with dpg.group():  # Main group for font controls
                    self.build_font_selection()  # Font combo

                    # Group for size input (slider removed)
                    with dpg.group(horizontal=True):
                        # Tag for the font size input (though not strictly needed if callback is direct)
                        dpg.add_input_int(
                            label="Size",  # Added label as slider is removed
                            tag=self.font_size_input_tag,
                            default_value=self.core.theme_manager.font_size,
                            min_value=8,
                            max_value=36,
                            width=80,  # Slightly wider now that it's standalone
                            step=1,
                            callback=lambda sender, app_data, user_data: self._update_font_size(
                                app_data
                            ),
                            on_enter=True,  # Trigger callback on enter
                        )
                    dpg.add_button(label="Reset Fonts",
                                   callback=self._reset_fonts)

            dpg.add_separator()
            dpg.add_text("Other settings will appear here.")

        # Initial application of theme via ThemeManager is handled by app.py
        # We just need to ensure our UI reflects the current state if possible.
        self.update_displayed_theme_name(default_combo_theme)
        print("[SettingsModule.build_dpg_view] Settings view built.")  # ADD LOG

    def _on_theme_selected(self, sender, selected_theme_name, user_data):
        if self.theme_manager and self.dpg_theme_combo_tag:
            self.theme_manager.apply_theme(selected_theme_name)
            # ThemeManager now updates self.core.config.theme_name internally
            if self.core and self.core.config:  # Save config directly
                self.core.config.save_config()
                print("[SettingsModule] AppConfig theme change saved.")

            if actual_applied_theme := self.theme_manager.get_current_theme_name():
                self.update_displayed_theme_name(actual_applied_theme)
                if dpg.does_item_exist(self.dpg_theme_combo_tag):
                    dpg.set_value(self.dpg_theme_combo_tag,
                                  actual_applied_theme)

    def update_displayed_theme_name(self, theme_name: str):
        if not self.dpg_current_theme_text_tag:
            return
        if dpg.does_item_exist(self.dpg_current_theme_text_tag):
            dpg.set_value(self.dpg_current_theme_text_tag,
                          f"Current: {theme_name}")

    def load_data(self):
        # print(f"[{self.__class__.__name__}] load_data called.")
        if not dpg.is_dearpygui_running() or not self.theme_manager:
            return

        current_theme = self.theme_manager.get_current_theme_name()
        theme_names = self.theme_manager.get_theme_names()

        combo_tag = self.dpg_theme_combo_tag

        if combo_tag is None:
            # If the combo tag hasn\'t been generated, nothing to update
            print(
                "[SettingsModule.load_data] Error: Combo tag not initialized.",
            )  # ADD LOG
            return

        # At this point, combo_tag is Union[int, str]
        theme_to_set_in_combo = None
        displayed_theme_name_for_text = None

        if current_theme and current_theme in theme_names:
            theme_to_set_in_combo = current_theme
            displayed_theme_name_for_text = current_theme
        elif (
            theme_names
        ):  # Fallback if current_theme is None or not in list, but themes exist
            fallback_theme = theme_names[0]
            theme_to_set_in_combo = fallback_theme
            displayed_theme_name_for_text = fallback_theme

        if theme_to_set_in_combo is not None:
            if dpg.does_item_exist(combo_tag):
                dpg.set_value(combo_tag, theme_to_set_in_combo)

        if displayed_theme_name_for_text is not None:
            self.update_displayed_theme_name(displayed_theme_name_for_text)

    def _update_font(self, font_name: str):
        if self.core.theme_manager and self.dpg_status_text_tag:
            try:
                self.core.theme_manager.set_font(font_name)
                # ThemeManager now updates self.core.config.font_name internally
                if self.core and self.core.config:  # Save config directly
                    self.core.config.save_config()
                    print("[SettingsModule] AppConfig font name change saved.")
            except ValueError as e:
                if dpg.does_item_exist(self.dpg_status_text_tag):
                    dpg.set_value(self.dpg_status_text_tag, str(e))

    def _update_font_size(self, size: int):
        if self.core.theme_manager and self.font_combo_tag:
            try:
                self.core.theme_manager.set_font_size(size)
                if self.core and self.core.config:
                    self.core.config.save_config()
                    print(
                        f"[SettingsModule] Font size updated to {size}pt and config saved.",
                    )

                if self.font_combo_tag is not None and dpg.does_item_exist(
                    self.font_combo_tag,
                ):
                    dpg.set_value(
                        self.font_combo_tag,
                        self.core.theme_manager.current_font,
                    )

                # Explicitly apply the new global font to the font size input widget itself
                if self.font_size_input_tag is not None and dpg.does_item_exist(
                    self.font_size_input_tag,
                ):
                    current_app_font_dpg_tag = (
                        self.core.theme_manager.get_last_globally_bound_dpg_font_tag()
                    )
                    # Font tag 0 (DPG default) is conceptually always valid for binding
                    if (
                        dpg.does_item_exist(current_app_font_dpg_tag)
                        or current_app_font_dpg_tag == 0
                    ):
                        dpg.bind_item_font(
                            self.font_size_input_tag,
                            current_app_font_dpg_tag,
                        )
                        print(
                            f"[SettingsModule] Applied font tag {current_app_font_dpg_tag} to font size input widget.",
                        )
                    else:
                        print(
                            f"[SettingsModule] Warning: Could not bind font tag {current_app_font_dpg_tag} to font size input. Tag might not exist.",
                        )
                else:
                    print(
                        "[SettingsModule] Warning: Font size input tag not found, cannot apply font to it.",
                    )

            except ValueError as e:
                print(f"[SettingsModule] Error updating font size: {e}")

    def _reset_fonts(self):
        if self.core.theme_manager:
            self.core.theme_manager.reset_font_settings()

            if self.font_combo_tag is not None and dpg.does_item_exist(
                self.font_combo_tag,
            ):
                dpg.set_value(self.font_combo_tag,
                              self.core.theme_manager.current_font)

            # Use the ThemeManager's default constant for clarity
            from core.theme_manager import (
                ThemeManager as TM_Defaults,
            )  # Import for constant

            default_size = TM_Defaults.DEFAULT_FONT_SIZE
            self._update_font_size(default_size)

            # Manually update slider and input if their tags are known (they are now due to new callback structure)
            # However, _on_font_size_control_changed handles syncing them if _update_font_size is called.
            # To ensure they visually update to the default_size, we can call the sync logic.
            # This is a bit redundant as _update_font_size will trigger the callback indirectly.
            # A cleaner way: if we had stable tags for slider/input, set them directly here.
            # For now, _update_font_size followed by ThemeManager defaults should be okay.
            # The _on_font_size_control_changed will handle updating the visual of the other control.

            # Find the slider and input tags if they exist (they are generated in build_dpg_view)
            # This is complex. The callback structure should handle it now if one triggers the other.
            # The simplest is to assume that if _update_font_size is called, the controls will eventually reflect it via callbacks.
            # To explicitly update them: find their tags. We generate them in build_dpg_view.
            # Let's assume the lambda for the slider/input in build_dpg_view correctly passes the OTHER control's tag.
            # If _update_font_size changes the actual size, and if the slider/input callbacks are robust,
            # they should query self.core.theme_manager.font_size and update themselves.
            # The new `_on_font_size_control_changed` helps here.
            # We just need to ensure that method correctly updates the *other* control.
            # Let's call _on_font_size_control_changed with a dummy source to update both if needed.
            # This requires knowing the tags, which are dynamic. The current setup is:
            # slider calls _on_font_size_control_changed(app_data, font_size_input_tag, "slider")
            # input calls  _on_font_size_control_changed(app_data, font_size_slider_tag, "input")
            # This is fine. Calling _update_font_size(default_size) will cause ThemeManager to change size,
            # then the next time the settings tab is rendered, the controls will pick up the new default_value.
            # To make it immediate *without* relying on re-render, we'd need stable tags for slider/input.
            # The current approach of _on_font_size_control_changed updating the *other* control is key.
            # When _update_font_size calls set_font_size, and then the _on_font_size_control_changed is called,
            # it should read the *new* actual size and update both.
            # The self._update_font_size(default_size) call should be sufficient for the ThemeManager.
            # The UI controls themselves need to be told to re-read their values if they don't automatically.
            # The `default_value` in `dpg.add_slider_int` and `dpg.add_input_int` is only for initial creation.
            # We need to dpg.set_value on them after reset.

            # We need a way to get font_size_slider_tag and font_size_input_tag here.
            # For now, this is not straightforward without storing them on self or re-querying.
            # The _on_font_size_control_changed handles syncing them IF one of them is changed by the user.
            # After a programmatic reset, we need to explicitly set both.
            # We can't easily get their dynamic tags here. A simpler fix in build_dpg_view is to ensure
            # they are recreated or reconfigured if the settings tab is rebuilt.
            # Or, store these specific tags on self if they become critical for external updates.

            print("[SettingsModule] Fonts reset. Triggering config save.")
            if self.core and self.core.config:
                self.core.config.save_config()

    def build_font_selection(self):
        print(
            "[SettingsModule.build_font_selection] Attempting to build font selection UI...",
        )
        if not self.core.theme_manager or self.font_combo_tag is None:
            print(
                "[SettingsModule.build_font_selection] Theme manager or font_combo_tag not available. Aborting.",
            )
            return

        theme_mgr = self.core.theme_manager
        # theme_mgr is already checked by the condition above, but good for linters/safety
        if theme_mgr is None:
            return

        font_items = []
        font_map = {}  # Map display name to real font name
        current_font_display_name = (
            None  # Variable to store the display name for the current font
        )

        current_real_font = theme_mgr.current_font

        for (
            font_name
        ) in theme_mgr.get_available_fonts():  # Changed variable name for clarity
            if theme_mgr.is_font_available(font_name):
                display_name = font_name  # Use real name as display name
                font_items.append(display_name)
                font_map[display_name] = font_name
                if font_name == current_real_font:
                    current_font_display_name = display_name
            else:
                display_name = f"{font_name} (unavailable)"
                font_items.append(display_name)
                # Map back to real name
                font_map[display_name] = font_name
                # Check if the current font is this one, even if unavailable
                if font_name == current_real_font:
                    current_font_display_name = display_name

        # Fallback if the current font wasn't found in the available list (shouldn't happen?)
        if current_font_display_name is None and font_items:
            current_font_display_name = font_items[0]
        elif current_font_display_name is None:
            current_font_display_name = ""  # Ensure it's a string if list is empty

        # The font combo is now expected to be parented by the group in build_dpg_view
        # We create it here if it doesn't exist, or configure it if it does.
        if dpg.does_item_exist(self.font_combo_tag):
            dpg.configure_item(
                self.font_combo_tag,
                items=font_items,
                default_value=current_font_display_name,  # Use DISPLAY NAME
                callback=lambda s, a_d, u_d: self._on_font_changed(
                    s,
                    a_d,
                    font_map,
                ),  # Pass font_map
            )
            print(
                f"[SettingsModule.build_font_selection] Configured existing font combo: {self.font_combo_tag}",
            )
        else:
            # This should be the primary path if tags are unique per module instance build
            dpg.add_combo(
                tag=self.font_combo_tag,
                items=font_items,
                default_value=current_font_display_name,  # Use DISPLAY NAME
                label="Font",
                callback=lambda s, a_d, u_d: self._on_font_changed(
                    s,
                    a_d,
                    font_map,
                ),  # Pass font_map
                width=200,
            )
            print(
                f"[SettingsModule.build_font_selection] Created new font combo: {self.font_combo_tag}",
            )

    def _on_font_changed(
        self,
        sender: int,
        selected_display_name: Any,
        font_map: Dict[str, str],
    ):
        actual_font_name = font_map.get(
            selected_display_name,
            selected_display_name,
        )  # Fallback to raw if not in map
        print(
            f"[SettingsModule._on_font_changed] Selected display: '{selected_display_name}', actual font: '{actual_font_name}'",
        )
        self._update_font(actual_font_name)

    def _on_theme_changed(self, sender, app_data):
        """Handle theme selection change"""
        if self.core.theme_manager:
            self.core.theme_manager.apply_theme(app_data)

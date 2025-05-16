import dearpygui.dearpygui as dpg
import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.app import StudyOS


class GUIManager:
    TOAST_WINDOW_TAG_PREFIX = "toast_window_"

    def __init__(self, app_instance: "StudyOS"):
        self.app = app_instance  # Reference to the main StudyOS app instance
        self.core = self.app.core  # Reference to Core
        self.active_toast_id: Optional[str] = None
        self.toast_counter = 0

    def show_toast(self, message: str, duration_ms: int = 3000, level: str = "info"):
        """
        Displays a toast notification.

        Args:
            message: The message to display.
            duration_ms: How long the toast should be visible in milliseconds.
            level: Type of toast ('info', 'warning', 'error', 'success'). Affects color.
        """
        # Ensure this runs in the DPG thread if called from elsewhere
        if not dpg.is_dearpygui_running():
            dpg.split_frame()  # Process one frame to ensure DPG is ready for calls
            # Ensure a container is active
            dpg.push_container_stack(dpg.add_window())

        # Delete previous toast if exists
        if self.active_toast_id and dpg.does_item_exist(self.active_toast_id):
            # Clean up associated timer if any (more robust timer management needed for this)
            # For simplicity, we assume timer callback handles deletion or it's modal-like
            dpg.delete_item(self.active_toast_id)
            # Also try to delete its timer if we stored its tag
            timer_tag = f"{self.active_toast_id}_timer"
            if dpg.does_item_exist(timer_tag):
                dpg.delete_item(timer_tag)

        self.toast_counter += 1
        toast_tag = f"{self.TOAST_WINDOW_TAG_PREFIX}{self.toast_counter}_{uuid.uuid4()}"
        self.active_toast_id = toast_tag

        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()

        toast_width = 300
        toast_height = (
            50 + (len(message) // 40) * 15
        )  # Basic height adjustment for message length

        pos_x = viewport_width - toast_width - 20
        pos_y = viewport_height - toast_height - 20  # Bottom right

        # Define colors based on level
        if level == "success":
            bg_color = (50, 150, 50, 220)
            text_color = (230, 255, 230, 255)
        elif level == "warning":
            bg_color = (180, 130, 0, 220)
            text_color = (255, 240, 200, 255)
        elif level == "error":
            bg_color = (180, 50, 50, 220)
            text_color = (255, 230, 230, 255)
        else:  # info
            bg_color = (50, 50, 80, 220)
            text_color = (230, 230, 250, 255)

        with dpg.window(
            tag=toast_tag,
            show=True,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_scrollbar=True,
            no_collapse=True,
            no_close=True,  # Timer will close it
            width=toast_width,
            height=toast_height,
            pos=[int(pos_x), int(pos_y)],
            autosize=False,  # Explicit size
            min_size=[100, 30],  # Prevent too small if autosize was on
        ):
            dpg.add_text(message, color=text_color, wrap=toast_width - 20)
            # Apply background color to the window using a theme
            with dpg.theme() as toast_theme:
                with dpg.theme_component(
                    dpg.mvWindowAppItem
                ):  # Target the window itself
                    dpg.add_theme_color(
                        dpg.mvThemeCol_WindowBg, bg_color, category=dpg.mvThemeCat_Core
                    )
                    # dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0,0, category=dpg.mvThemeCat_Core)
            dpg.bind_item_theme(toast_tag, toast_theme)

        # Timer to delete the toast
        # The callback for the timer needs to be defined such that it can access the toast_tag
        # and the theme tag to delete them.

        timer_tag_local = f"{toast_tag}_timer"

        def _auto_close_toast(sender, app_data, user_data):
            toast_to_delete, theme_to_delete = user_data
            if dpg.does_item_exist(toast_to_delete):
                dpg.delete_item(toast_to_delete)
            if dpg.does_item_exist(theme_to_delete):
                dpg.delete_item(theme_to_delete)
            # Also delete the timer itself
            if dpg.does_item_exist(sender):  # sender is the timer_tag_local
                dpg.delete_item(sender)

            # If this was the active toast, clear the active_toast_id
            if self.active_toast_id == toast_to_delete:
                self.active_toast_id = None

        dpg.add_timer(
            tag=timer_tag_local,
            delay=duration_ms / 1000.0,  # DPG timer is in seconds
            callback=_auto_close_toast,
            user_data=(toast_tag, toast_theme),  # Pass toast_tag and theme_tag
            # Parent to the toast window so it gets cleaned up if toast is deleted early
            parent=toast_tag,
            calls=1,  # Run only once
        )

        if not dpg.is_dearpygui_running():
            dpg.pop_container_stack()

    def cleanup_all_toasts(self):  # Potentially useful for shutdown
        # This is a bit simplistic, a more robust way would be to iterate through known toast tags
        # if we were managing multiple simultaneous toasts.
        if self.active_toast_id and dpg.does_item_exist(self.active_toast_id):
            dpg.delete_item(self.active_toast_id)
            timer_tag = f"{self.active_toast_id}_timer"
            if dpg.does_item_exist(timer_tag):
                dpg.delete_item(timer_tag)
        self.active_toast_id = None

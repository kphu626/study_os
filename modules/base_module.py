import logging
from typing import TYPE_CHECKING
import dearpygui.dearpygui as dpg  # Added DPG import

if TYPE_CHECKING:
    from core.app import Core  # Import specifically from core.app for type checking


class BaseModule:
    def __init__(self, core: "Core"):  # Use string literal for type hint
        self.core = core
        self.logger = logging.getLogger(self.__class__.__name__)
        # self.view = None # This was Flet-specific, DPG views are built differently

    async def load_data(self):
        """Override for async data loading"""
        pass

    def initialize_dpg_tags(self):
        """Override in child modules if they need to generate DPG tags before building the view."""
        # print(f"[{self.__class__.__name__}] initialize_dpg_tags called (default implementation)." )
        pass

    def build_sidebar_view(self, sidebar_parent_tag: str):
        """Override in child modules if they need to populate a common sidebar area."""
        # print(f"[{self.__class__.__name__}] build_sidebar_view called (default implementation)." )
        pass

    def build_dpg_view(self, parent_container_tag: str):
        """Override in child modules to build their Dear PyGui view.
        The view should be added under the parent_container_tag.
        """
        # Default placeholder view
        dpg.add_text(
            f"Placeholder view for {self.__class__.__name__}",
            parent=parent_container_tag,
        )
        # In a real module, you would add specific DPG items:
        # with dpg.group(parent=parent_container_tag):
        #     dpg.add_button(label=f"Button from {self.__class__.__name__}")
        #     dpg.add_input_text(label="Input here")

    def handle_keyboard(self, key_code: int):
        """Override in child modules to handle key presses"""
        pass

    def get_focusable_items(self) -> list:
        """Return list of focusable item tags in order"""
        return []

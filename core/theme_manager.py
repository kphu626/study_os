import dearpygui.dearpygui as dpg
from typing import Optional, TYPE_CHECKING
from pathlib import Path
import logging
import os

if TYPE_CHECKING:
    from core.app import Core


class ThemeManager:
    DEFAULT_THEME_NAME = "Default Dark"
    DEFAULT_FONT_NAME = "Roboto"  # Or whatever your actual default is
    DEFAULT_FONT_SIZE = 13

    def __init__(self, core: "Core"):
        self.core = core
        self.themes = {}
        self._requires_initialization = True
        self.active_theme_tag = None
        self.font_registry = None  # Deferred initialization
        self._fonts = {}
        self.unavailable_fonts = set()  # Track failed fonts
        self.available_fonts = set()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_globally_bound_dpg_font_tag: int = 0  # Initialize with DPG default

        # Load initial settings from config, with fallbacks
        self.initial_theme_name = self.core.config.theme_name or self.DEFAULT_THEME_NAME
        self.initial_font_name = self.core.config.font_name or self.DEFAULT_FONT_NAME
        self.initial_font_size = self.core.config.font_size or self.DEFAULT_FONT_SIZE

        # These will be set by DPG operations or after initialization
        self.current_theme_name = self.initial_theme_name
        self.current_font = self.initial_font_name
        self.font_size = self.initial_font_size

        print(
            f"[ThemeManager] Initializing with: Theme='{self.current_theme_name}', Font='{self.current_font}', Size={self.font_size}"
        )
        print("[ThemeManager] Instance created (DPG operations deferred)")

    def initialize(self):
        """Call this after DPG context exists"""
        if self._requires_initialization:
            print("[ThemeManager.initialize] Initializing DPG components...")
            self.font_registry = dpg.add_font_registry()
            print(
                f"[ThemeManager.initialize] Font registry created: {self.font_registry}"
            )
            print(
                f"[ThemeManager.initialize] Initial font size from config: {self.initial_font_size}pt"
            )
            self._load_system_fonts()  # Loads available fonts using initial_font_size implicitly
            self._create_default_themes()  # Defines theme structures

            print(
                f"[ThemeManager.initialize] Applying initial theme: '{self.initial_theme_name}'"
            )
            self.apply_theme(
                self.initial_theme_name
            )  # Ensures the configured theme is active

            # Set this to False BEFORE applying initial font/size so they don't defer.
            self._requires_initialization = False

            if self.initial_font_name:
                print(
                    f"[ThemeManager.initialize] Applying initial font: '{self.initial_font_name}' with initial size: {self.initial_font_size}pt (current self.font_size: {self.font_size}pt)"
                )
                self.set_font(
                    self.initial_font_name
                )  # set_font now reloads using current self.font_size

            print(
                f"[ThemeManager.initialize] Applying initial font size: {self.initial_font_size}pt (current self.font_size before call: {self.font_size}pt)"
            )
            self.set_font_size(
                self.initial_font_size
            )  # set_font_size will use this new value

            print(
                f"[ThemeManager.initialize] Initialization complete. Active theme: {self.current_theme_name}, Font: {self.current_font} @ {self.font_size}pt"
            )

    def _create_default_themes(self):
        print(
            "[ThemeManager._initialize_theme_definitions] Generating UUID and defining themes..."
        )
        self.active_theme_tag = dpg.generate_uuid()  # Generate UUID now
        print(
            f"[ThemeManager._initialize_theme_definitions] Generated active_theme_tag: {self.active_theme_tag}"
        )

        self.themes = {
            "Default Light": {
                int(dpg.mvThemeCol_WindowBg): (240, 240, 240, 255),
                int(dpg.mvThemeCol_ChildBg): (240, 240, 240, 255),
                int(dpg.mvThemeCol_TitleBg): (220, 220, 220, 255),
                int(dpg.mvThemeCol_TitleBgActive): (0, 120, 215, 255),
                int(dpg.mvThemeCol_TitleBgCollapsed): (200, 200, 200, 255),
                int(dpg.mvThemeCol_Text): (0, 0, 0, 255),
                int(dpg.mvThemeCol_Button): (220, 220, 220, 255),
                int(dpg.mvThemeCol_ButtonHovered): (200, 200, 200, 255),
                int(dpg.mvThemeCol_ButtonActive): (0, 100, 180, 255),
                int(dpg.mvThemeCol_FrameBg): (255, 255, 255, 255),
                int(dpg.mvThemeCol_FrameBgHovered): (230, 230, 230, 255),
                int(dpg.mvThemeCol_FrameBgActive): (210, 210, 210, 255),
                int(dpg.mvThemeCol_Header): (0, 120, 215, 255),
                int(dpg.mvThemeCol_HeaderHovered): (0, 100, 190, 255),
                int(dpg.mvThemeCol_HeaderActive): (0, 80, 160, 255),
                int(dpg.mvThemeCol_ScrollbarBg): (240, 240, 240, 255),
                int(dpg.mvThemeCol_ScrollbarGrab): (200, 200, 200, 255),
                int(dpg.mvThemeCol_Separator): (200, 200, 200, 255),
            },
            "Default Dark": {
                int(dpg.mvThemeCol_WindowBg): (30, 30, 30, 255),
                int(dpg.mvThemeCol_ChildBg): (35, 35, 35, 255),
                int(dpg.mvThemeCol_TitleBg): (25, 25, 25, 255),
                int(dpg.mvThemeCol_TitleBgActive): (50, 100, 150, 255),
                int(dpg.mvThemeCol_TitleBgCollapsed): (20, 20, 20, 255),
                int(dpg.mvThemeCol_Text): (230, 230, 230, 255),
                int(dpg.mvThemeCol_Button): (70, 70, 70, 255),
                int(dpg.mvThemeCol_ButtonHovered): (90, 90, 90, 255),
                int(dpg.mvThemeCol_ButtonActive): (50, 120, 190, 255),
                int(dpg.mvThemeCol_FrameBg): (50, 50, 50, 255),
                int(dpg.mvThemeCol_FrameBgHovered): (60, 60, 60, 255),
                int(dpg.mvThemeCol_FrameBgActive): (40, 40, 40, 255),
                int(dpg.mvThemeCol_Header): (50, 100, 150, 255),
                int(dpg.mvThemeCol_HeaderHovered): (60, 120, 180, 255),
                int(dpg.mvThemeCol_HeaderActive): (40, 80, 130, 255),
                int(dpg.mvThemeCol_ScrollbarBg): (30, 30, 30, 255),
                int(dpg.mvThemeCol_ScrollbarGrab): (80, 80, 80, 255),
                int(dpg.mvThemeCol_Separator): (80, 80, 80, 255),
            },
            "Microsoft Inspired": {
                int(dpg.mvThemeCol_WindowBg): (242, 242, 242, 255),
                int(dpg.mvThemeCol_ChildBg): (248, 248, 248, 255),
                int(dpg.mvThemeCol_TitleBg): (230, 230, 230, 255),
                int(dpg.mvThemeCol_TitleBgActive): (0, 120, 212, 255),
                int(dpg.mvThemeCol_TitleBgCollapsed): (200, 200, 200, 255),
                int(dpg.mvThemeCol_Text): (10, 10, 10, 255),
                int(dpg.mvThemeCol_Button): (225, 225, 225, 255),
                int(dpg.mvThemeCol_ButtonHovered): (200, 228, 249, 255),
                int(dpg.mvThemeCol_ButtonActive): (0, 120, 212, 255),
                int(dpg.mvThemeCol_FrameBg): (255, 255, 255, 255),
                int(dpg.mvThemeCol_FrameBgHovered): (240, 240, 240, 255),
                int(dpg.mvThemeCol_FrameBgActive): (220, 220, 220, 255),
                int(dpg.mvThemeCol_Header): (0, 120, 212, 255),
                int(dpg.mvThemeCol_HeaderHovered): (0, 100, 190, 255),
                int(dpg.mvThemeCol_HeaderActive): (0, 80, 160, 255),
                int(dpg.mvThemeCol_ScrollbarBg): (242, 242, 242, 255),
                int(dpg.mvThemeCol_ScrollbarGrab): (204, 204, 204, 255),
                int(dpg.mvThemeCol_Separator): (204, 204, 204, 255),
            },
            "Apple Inspired Light": {
                int(dpg.mvThemeCol_WindowBg): (238, 238, 238, 255),
                int(dpg.mvThemeCol_ChildBg): (245, 245, 245, 255),
                int(dpg.mvThemeCol_TitleBg): (228, 228, 228, 255),
                int(dpg.mvThemeCol_TitleBgActive): (0, 122, 255, 255),
                int(dpg.mvThemeCol_TitleBgCollapsed): (210, 210, 210, 255),
                int(dpg.mvThemeCol_Text): (20, 20, 20, 255),
                int(dpg.mvThemeCol_Button): (230, 230, 230, 255),
                int(dpg.mvThemeCol_ButtonHovered): (210, 210, 210, 255),
                int(dpg.mvThemeCol_ButtonActive): (0, 122, 255, 255),
                int(dpg.mvThemeCol_FrameBg): (250, 250, 250, 255),
                int(dpg.mvThemeCol_FrameBgHovered): (230, 230, 230, 255),
                int(dpg.mvThemeCol_FrameBgActive): (210, 210, 210, 255),
                int(dpg.mvThemeCol_Header): (0, 122, 255, 255),
                int(dpg.mvThemeCol_HeaderHovered): (0, 100, 230, 255),
                int(dpg.mvThemeCol_HeaderActive): (0, 80, 200, 255),
                int(dpg.mvThemeCol_ScrollbarBg): (238, 238, 238, 255),
                int(dpg.mvThemeCol_ScrollbarGrab): (190, 190, 190, 255),
                int(dpg.mvThemeCol_Separator): (190, 190, 190, 255),
            },
            "GitHub Inspired Dark": {
                int(dpg.mvThemeCol_WindowBg): (13, 17, 23, 255),
                int(dpg.mvThemeCol_ChildBg): (22, 27, 34, 255),
                int(dpg.mvThemeCol_TitleBg): (13, 17, 23, 255),
                int(dpg.mvThemeCol_TitleBgActive): (31, 111, 235, 255),
                int(dpg.mvThemeCol_TitleBgCollapsed): (10, 10, 10, 255),
                int(dpg.mvThemeCol_Text): (201, 209, 217, 255),
                int(dpg.mvThemeCol_Button): (35, 39, 46, 255),
                int(dpg.mvThemeCol_ButtonHovered): (50, 55, 62, 255),
                int(dpg.mvThemeCol_ButtonActive): (40, 167, 69, 255),
                int(dpg.mvThemeCol_FrameBg): (22, 27, 34, 255),
                int(dpg.mvThemeCol_FrameBgHovered): (30, 35, 42, 255),
                int(dpg.mvThemeCol_FrameBgActive): (25, 30, 37, 255),
                int(dpg.mvThemeCol_Header): (31, 111, 235, 255),
                int(dpg.mvThemeCol_HeaderHovered): (40, 120, 245, 255),
                int(dpg.mvThemeCol_HeaderActive): (20, 90, 200, 255),
                int(dpg.mvThemeCol_ScrollbarBg): (13, 17, 23, 255),
                int(dpg.mvThemeCol_ScrollbarGrab): (50, 55, 62, 255),
                int(dpg.mvThemeCol_Separator): (50, 55, 62, 255),
            },
            "Calm Green": {
                int(dpg.mvThemeCol_WindowBg): (230, 240, 230, 255),
                int(dpg.mvThemeCol_ChildBg): (235, 245, 235, 255),
                int(dpg.mvThemeCol_TitleBg): (210, 220, 210, 255),
                int(dpg.mvThemeCol_TitleBgActive): (100, 150, 100, 255),
                int(dpg.mvThemeCol_TitleBgCollapsed): (200, 210, 200, 255),
                int(dpg.mvThemeCol_Text): (50, 70, 50, 255),
                int(dpg.mvThemeCol_Button): (200, 220, 200, 255),
                int(dpg.mvThemeCol_ButtonHovered): (180, 200, 180, 255),
                int(dpg.mvThemeCol_ButtonActive): (100, 150, 100, 255),
                int(dpg.mvThemeCol_FrameBg): (240, 250, 240, 255),
                int(dpg.mvThemeCol_FrameBgHovered): (220, 230, 220, 255),
                int(dpg.mvThemeCol_FrameBgActive): (200, 210, 200, 255),
                int(dpg.mvThemeCol_Header): (100, 150, 100, 255),
                int(dpg.mvThemeCol_HeaderHovered): (90, 130, 90, 255),
                int(dpg.mvThemeCol_HeaderActive): (80, 110, 80, 255),
                int(dpg.mvThemeCol_ScrollbarBg): (230, 240, 230, 255),
                int(dpg.mvThemeCol_ScrollbarGrab): (180, 200, 180, 255),
                int(dpg.mvThemeCol_Separator): (180, 200, 180, 255),
            },
        }
        print("[ThemeManager._initialize_theme_definitions] Themes defined.")
        # Create the default theme object now that themes and UUID are ready
        # Use the initial_theme_name determined in __init__
        self._create_dpg_theme_object(self.initial_theme_name)
        print(
            f"[ThemeManager._initialize_theme_definitions] Initial theme object created for: {self.initial_theme_name}."
        )

    def _create_dpg_theme_object(self, theme_name: str):
        print(
            f"[ThemeManager._create_dpg_theme_object] Creating theme object for: {theme_name}"
        )
        if self.active_theme_tag is None:
            # This might happen if initialize wasn't called or DPG context not ready
            # For robustness, generate it here if it's missing
            self.active_theme_tag = dpg.generate_uuid()
            print(
                f"[ThemeManager._create_dpg_theme_object] Generated missing active_theme_tag: {self.active_theme_tag}"
            )

        default_fallback_theme = self.DEFAULT_THEME_NAME
        if not self.themes:  # Check if themes dict is empty
            print(
                f"Error: Themes dictionary is empty. Cannot create theme object for '{theme_name}'. Falling back to {default_fallback_theme} assumptions."
            )
            # Attempt to create a very basic fallback if possible, or just return
            # Set current theme name even if creation is partial
            self.current_theme_name = default_fallback_theme
            # Maybe log this as a more severe issue
            return  # Or attempt a minimal theme creation if that makes sense

        if theme_name not in self.themes:
            print(
                f"Warning: Theme '{theme_name}' not found. Using '{default_fallback_theme}'."
            )
            theme_name = default_fallback_theme

        theme_colors = self.themes[theme_name]
        self.current_theme_name = theme_name  # Set current theme name
        self.core.config.theme_name = self.current_theme_name  # Update config

        if dpg.does_item_exist(self.active_theme_tag):
            dpg.delete_item(self.active_theme_tag)

        with dpg.theme(tag=self.active_theme_tag):
            with dpg.theme_component(dpg.mvAll):
                for dpg_item_property, color_value in theme_colors.items():
                    dpg.add_theme_color(
                        dpg_item_property, color_value, category=dpg.mvThemeCat_Core
                    )

    def apply_theme(self, theme_name: str):
        print(f"[ThemeManager.apply_theme] Applying theme: {theme_name}")
        self._create_dpg_theme_object(
            theme_name
        )  # This updates self.current_theme_name and config

        if self.active_theme_tag is None:
            print("Error: active_theme_tag is None. Cannot bind DPG theme.")
            return

        dpg.bind_theme(self.active_theme_tag)
        print(
            f"[ThemeManager.apply_theme] Attempted to bind theme: {self.active_theme_tag} for theme name {theme_name}"
        )

    def get_theme_names(self) -> list[str]:
        return list(self.themes.keys())

    def get_current_theme_name(self) -> Optional[str]:
        return self.current_theme_name

    def _load_system_fonts(self):
        """Load a predefined list of common system fonts with availability tracking."""
        if not self.font_registry:
            self.logger.error(
                "Font registry not initialized in _load_system_fonts!")
            return

        self.unavailable_fonts.clear()
        self.available_fonts.clear()
        self._fonts.clear()  # Clear previously loaded font IDs

        # The keys of common_font_files in _find_font_path are good candidates for display names.
        # We need to access that dictionary or replicate its keys here.
        # For simplicity, let's define a list of display names we want to try loading.
        # These names should correspond to what _find_font_path can resolve.
        font_display_names_to_try = [
            "Arial",
            "Arial Black",
            "Calibri",
            "Cambria",
            "Candara",
            "Comic Sans MS",
            "Consolas",
            "Constantia",
            "Corbel",
            "Courier New",
            "Franklin Gothic Medium",
            "Gabriola",
            "Gadugi",
            "Georgia",
            "Impact",
            "Lucida Console",
            "Lucida Sans Unicode",
            "Microsoft Sans Serif",
            "Palatino Linotype",
            "Roboto",
            "Segoe UI",
            "Segoe UI Light",
            "Segoe UI Semibold",
            "Segoe UI Historic",
            "Sitka Text",
            "Sylfaen",
            "Tahoma",
            "Times New Roman",
            "Trebuchet MS",
            "Verdana",
            # Ensure these names align with how _find_font_path tries to map them to filenames
        ]

        self.logger.info(
            f"Attempting to load {len(font_display_names_to_try)} common fonts."
        )

        for name in font_display_names_to_try:
            font_id = self._load_font(
                name
            )  # _load_font uses self.font_size and _find_font_path
            if (
                font_id is not None
            ):  # _load_font returns Optional[int], 0 is a valid ID (DPG default)
                self._fonts[name] = font_id
                # self.available_fonts is managed by _load_font
                self.logger.debug(
                    f"Successfully queued/loaded font '{name}' with ID: {font_id} for system fonts."
                )
            else:
                # self.unavailable_fonts is managed by _load_font
                self.logger.debug(
                    f"Failed to load font '{name}' during system font loading phase."
                )

        if not self._fonts:  # If absolutely no fonts were loaded from the common list
            self.logger.warning(
                "No common fonts loaded. Attempting to load DPG default as fallback."
            )
            self._load_fallback_font()  # Ensures at least DPG default is available

        self.logger.info(
            f"Finished loading system fonts. Total loaded into _fonts: {len(self._fonts)}. Available according to available_fonts set: {len(self.available_fonts)}"
        )

    def _load_fallback_font(self):
        """Embed a basic font as last resort"""
        try:
            if self.font_registry is None:
                raise RuntimeError(
                    "Cannot load fallback font - registry missing")

            # Instead of trying to load a file that doesn't exist, just use DPG's default
            self._fonts["Default"] = 0  # Use built-in default font
            self.available_fonts.add("Default")
        except Exception as e:
            print(f"Critical font error: {str(e)}")
            self._fonts["Default"] = 0

    def _load_font(self, font_name: str) -> Optional[int]:
        """Loads a single font file with the current self.font_size and adds it to the registry."""
        if not self.font_registry:
            self.logger.error(
                "Font registry not initialized during _load_font!")
            return None

        try:
            # Use the existing _find_font_path which needs to be made more robust
            font_path_str = self._find_font_path(font_name)

            if not font_path_str:
                self.logger.warning(
                    f"Font file not found for: {font_name} via _find_font_path."
                )
                self.unavailable_fonts.add(font_name)
                return None

            font_path = Path(font_path_str)
            if not font_path.exists():
                self.logger.warning(
                    f"Font file path does not exist: {font_path}")
                self.unavailable_fonts.add(font_name)
                return None

            # Add the font with the current ThemeManager's font_size
            # DPG expects font size as an int.
            font_id_any = dpg.add_font(
                str(font_path), int(self.font_size), parent=self.font_registry
            )

            if isinstance(font_id_any, str):
                self.logger.error(
                    f"dpg.add_font returned a string error for {font_name}: {font_id_any}"
                )
                self.unavailable_fonts.add(font_name)
                return None  # Explicitly return None on string error

            # If not a string, it should be an int (the font ID) or potentially None if DPG changes behavior.
            # We assume int here if no error string.
            font_id: Optional[int] = (
                font_id_any if isinstance(font_id_any, int) else None
            )

            if (
                font_id is not None and font_id != 0
            ):  # DPG default font is 0, treat actual 0 as success if returned as int
                self.logger.info(
                    f"Successfully loaded font: {font_name} (Path: {font_path}, Size: {self.font_size}pt) -> ID: {font_id}"
                )
                self.available_fonts.add(font_name)
                if font_name in self.unavailable_fonts:
                    self.unavailable_fonts.remove(font_name)
                return font_id
            elif font_id == 0:
                self.logger.info(
                    f"Loaded font {font_name} and received ID 0 (DPG default/fallback). Considering it available if no error string."
                )
                self.available_fonts.add(
                    font_name
                )  # If ID is 0, it means DPG will use its default if this is bound
                if font_name in self.unavailable_fonts:
                    self.unavailable_fonts.remove(font_name)
                return 0  # Return 0 if DPG assigned its default font ID
            else:
                self.logger.error(
                    f"Failed to load font {font_name}: dpg.add_font returned unexpected value {font_id_any}"
                )
                self.unavailable_fonts.add(font_name)
                return None

        except Exception as e:
            self.logger.error(
                f"Error loading font {font_name} at size {self.font_size}: {e}",
                exc_info=True,
            )
            self.unavailable_fonts.add(font_name)
            return None

    def set_font(self, font_name: str):
        print(
            f"[ThemeManager.set_font] START - Called with font_name: '{font_name}', current self.font_size: {self.font_size}pt, requires_init: {self._requires_initialization}"
        )
        if self._requires_initialization:
            print(
                "[ThemeManager.set_font] ThemeManager not fully initialized (requires_initialization is True). Deferring DPG font operations."
            )
            self.initial_font_name = font_name
            self.current_font = font_name
            return

        # Proceed if _requires_initialization is False
        print(
            "[ThemeManager.set_font] Proceeding with DPG operations as requires_initialization is False."
        )

        # Always attempt to load/reload the font with the current size.
        # This ensures that if the font_size has changed since this font was last loaded,
        # it gets re-registered with DPG at the correct current size.
        # _load_font uses self.font_size
        print(
            f"[ThemeManager.set_font] Calling _load_font('{font_name}') with self.font_size = {self.font_size}pt"
        )
        loaded_font_id = self._load_font(font_name)
        print(
            f"[ThemeManager.set_font] _load_font returned ID: {loaded_font_id} for '{font_name}'"
        )

        if loaded_font_id is None:  # _load_font returns None on failure
            print(
                f"Failed to load font: {font_name} at size {self.font_size}pt. Retaining current font: {self.current_font} or DPG default."
            )
            # Attempt to rebind the previously known good current font, or DPG default if current_font also fails
            font_to_rebind = self._fonts.get(self.current_font, 0)
            dpg.bind_font(font_to_rebind)
            self.last_globally_bound_dpg_font_tag = font_to_rebind
            # Do not update self.current_font or config.font_name if the new font failed to load.
            return

        # Font loaded successfully (loaded_font_id can be 0 if DPG default was used by _load_font)
        self._fonts[font_name] = loaded_font_id
        self.available_fonts.add(font_name)
        if font_name in self.unavailable_fonts:
            self.unavailable_fonts.remove(font_name)

        # Now bind the newly loaded/reloaded font
        dpg.bind_font(loaded_font_id)
        self.last_globally_bound_dpg_font_tag = loaded_font_id
        self.current_font = font_name
        self.core.config.font_name = self.current_font
        print(
            f"Successfully loaded and bound font: {font_name} with ID {loaded_font_id} at size {self.font_size}pt"
        )

    def set_font_size(self, size: int):
        print(
            f"[ThemeManager.set_font_size] START - Called with size: {size}pt, current self.font_size: {self.font_size}pt, requires_init: {self._requires_initialization}"
        )
        if not isinstance(size, int) or not (8 <= size <= 72):  # Basic validation
            print(f"Invalid font size: {size}. Must be int between 8-72.")
            return

        # Allow font size change even if it's the same, if we are in the init phase, to ensure it's processed.
        if self.font_size == size and not self._requires_initialization:
            print(f"Font size already {size}pt.")
            return

        self.font_size = size
        self.core.config.font_size = self.font_size  # Update config

        # if not dpg.is_dearpygui_running() or self._requires_initialization: # OLD CONDITION
        if self._requires_initialization:  # NEW CONDITION
            print(
                "[ThemeManager.set_font_size] ThemeManager not fully initialized (requires_initialization is True). Storing size for later."
            )
            self.initial_font_size = size
            return

        print(
            "[ThemeManager.set_font_size] Proceeding with DPG operations as requires_initialization is False."
        )

        print(
            f"[ThemeManager.set_font_size] Calling _refresh_fonts. Current font: '{self.current_font}', new size to apply: {self.font_size}pt"
        )
        self._refresh_fonts()  # This should handle reloading all known fonts with new size

        # After refreshing, ensure the *currently selected* font is bound
        font_to_bind: int  # Declare type for clarity
        if self.current_font in self._fonts:
            font_to_bind = self._fonts[self.current_font]
            dpg.bind_font(font_to_bind)
            self.last_globally_bound_dpg_font_tag = font_to_bind
            print(
                f"[ThemeManager.set_font_size] Re-bound font '{self.current_font}' with size {self.font_size}pt."
            )
        elif (
            self._fonts
        ):  # If current_font somehow invalid, bind first available or default
            font_to_bind = next(
                iter(self._fonts.values()), 0
            )  # Get first loaded font or DPG default
            dpg.bind_font(font_to_bind)
            self.last_globally_bound_dpg_font_tag = font_to_bind
            print(
                f"[ThemeManager.set_font_size] Current font '{self.current_font}' not in loaded _fonts after refresh. Bound a fallback."
            )
        else:  # No fonts loaded at all
            font_to_bind = 0  # DPG default
            dpg.bind_font(font_to_bind)
            self.last_globally_bound_dpg_font_tag = font_to_bind
            print(
                "[ThemeManager.set_font_size] No fonts in _fonts after refresh. Bound DPG default font."
            )

    def _refresh_fonts(self):
        """Re-registers all known fonts, typically after a size change."""
        if not self.font_registry or not dpg.is_dearpygui_running():
            print(
                "[ThemeManager._refresh_fonts] Font registry not ready or DPG not running."
            )
            return

        print(
            f"[ThemeManager._refresh_fonts] START - Current font: '{self.current_font}', target size: {self.font_size}pt."
        )
        # DPG does not have a simple "clear font registry" or "update font size globally".
        # We need to delete and re-add fonts if their size parameter needs to change.
        # This is complex because DPG's font handling is by adding font files with a specific size.
        # A simpler approach for DPG is to re-add the font with the new size and re-bind it.

        # Keep track of fonts that were successfully reloaded
        # reloaded_fonts = {} # No longer needed if only reloading current font

        # Attempt to reload all previously available fonts with the new size
        # fonts_to_reload = list(self.available_fonts) # Iterate over a copy
        # if self.current_font not in fonts_to_reload and self.current_font not in self.unavailable_fonts:
        #     # Ensure current_font is considered if it was valid
        #     fonts_to_reload.append(self.current_font)

        # for font_name in set(fonts_to_reload): # Use set to avoid duplicates
        # Only reload the current font
        font_name_to_reload = self.current_font
        if font_name_to_reload and (
            font_name_to_reload in self.available_fonts
            or font_name_to_reload not in self.unavailable_fonts
        ):
            self.logger.info(
                f"[ThemeManager._refresh_fonts] Attempting to reload current font '{font_name_to_reload}' with size {self.font_size}pt."
            )
            print(
                f"[ThemeManager._refresh_fonts] Calling _load_font('{font_name_to_reload}') with self.font_size = {self.font_size}pt"
            )

            new_font_id = self._load_font(
                font_name_to_reload
            )  # _load_font now implicitly uses self.font_size
            if new_font_id is not None and new_font_id != 0:
                self._fonts[font_name_to_reload] = (
                    new_font_id  # Update/add to _fonts map
                )
                if font_name_to_reload in self.unavailable_fonts:
                    self.unavailable_fonts.remove(font_name_to_reload)
                self.available_fonts.add(font_name_to_reload)
                self.logger.info(
                    f"[ThemeManager._refresh_fonts] Successfully reloaded '{font_name_to_reload}'. New ID: {new_font_id}"
                )
            else:
                self.logger.error(
                    f"[ThemeManager._refresh_fonts] Failed to reload font '{font_name_to_reload}' with new size. Marking as unavailable."
                )
                self.unavailable_fonts.add(font_name_to_reload)
                if font_name_to_reload in self.available_fonts:
                    self.available_fonts.remove(font_name_to_reload)
                if (
                    font_name_to_reload in self._fonts
                ):  # Remove from active fonts if reload failed
                    del self._fonts[font_name_to_reload]
        else:
            self.logger.warning(
                f"[ThemeManager._refresh_fonts] Current font '{font_name_to_reload}' not suitable for reload (e.g. unavailable or None)."
            )

        # self._fonts = reloaded_fonts # No longer needed

        # After reloading, the application's global font needs to be re-bound
        # to reflect the new size for the currently active font.
        # This is typically handled by the caller of set_font_size.
        print(
            f"[ThemeManager._refresh_fonts] Fonts refreshed. Current active font: {self.current_font}. Re-bind in calling function."
        )

    def get_available_fonts(self) -> list:
        return list(self._fonts.keys())

    def get_last_globally_bound_dpg_font_tag(self) -> int:
        """Returns the DPG font tag that ThemeManager last bound globally."""
        return self.last_globally_bound_dpg_font_tag

    def reset_font_settings(self):
        self.font_size = 13
        self.set_font("Roboto")

    def is_font_available(self, font_name: str) -> bool:
        return font_name in self.available_fonts

    def _find_font_path(self, font_name: str) -> Optional[str]:
        """
        Attempts to find the font file path for a given font name.
        Currently provides a basic search for Windows common fonts.
        Future: Extend for cross-platform or use a font management library.
        """
        self.logger.debug(f"Searching for font file for: {font_name}")
        font_name_lower = font_name.lower()
        possible_extensions = [".ttf", ".otf"]

        # Common font file names (case-insensitive check against keys)
        # Map common display names to typical filenames
        common_font_files = {
            "arial": "arial.ttf",
            "arial black": "ariblk.ttf",
            "calibri": "calibri.ttf",
            # Font collections might need special handling or specific font index
            "cambria": "cambria.ttc",
            "candara": "Candara.ttf",
            "comic sans ms": "comic.ttf",
            "consolas": "consola.ttf",
            "constantia": "constan.ttf",
            "corbel": "corbel.ttf",
            "courier new": "cour.ttf",
            "franklin gothic medium": "framd.ttf",
            "gabriola": "Gabriola.ttf",
            "gadugi": "Gadugi.ttf",
            "georgia": "georgia.ttf",
            "impact": "impact.ttf",
            "lucida console": "lucon.ttf",
            # Often this filename for Lucida Sans Unicode
            "lucida sans unicode": "l_10646.ttf",
            "microsoft sans serif": "micross.ttf",
            "palatino linotype": "pala.ttf",
            "roboto": "Roboto-Regular.ttf",
            "segoe ui": "segoeui.ttf",
            "segoe ui light": "segoeuil.ttf",
            "segoe ui semibold": "seguisb.ttf",
            "segoe ui historic": "seguihis.ttf",
            "sitka text": "Sitka.ttc",
            "sylfaen": "sylfaen.ttf",
            "tahoma": "tahoma.ttf",
            "times new roman": "times.ttf",
            "trebuchet ms": "trebuc.ttf",
            "verdana": "verdana.ttf",
            # Add more common mappings as needed
        }

        # Try direct match or common mapping first
        target_filename = common_font_files.get(
            font_name_lower, f"{font_name_lower}.ttf"
        )  # Default to font_name.ttf

        # System font directories (Windows example)
        # For a more robust solution, use a library like matplotlib.font_manager or platformdirs
        system_font_dirs = []
        if os.name == "nt":  # Windows
            windir = os.environ.get("WINDIR")
            if windir:
                system_font_dirs.append(Path(windir) / "Fonts")
            # User-specific fonts
            local_app_data = os.environ.get("LOCALAPPDATA")
            if local_app_data:
                system_font_dirs.append(
                    Path(local_app_data) / "Microsoft" / "Windows" / "Fonts"
                )
        # Add elif for macOS, Linux if needed later
        # else: # macOS or Linux (very basic examples, not exhaustive)
        # system_font_dirs.extend([
        #     Path("/usr/share/fonts"),
        #     Path("/usr/local/share/fonts"),
        #     Path(os.path.expanduser("~/.fonts")),
        #     Path("/Library/Fonts"), # macOS
        #     Path(os.path.expanduser("~/Library/Fonts")) # macOS User
        # ])

        # Check a bundled 'fonts' directory first (if you plan to ship fonts)
        # bundled_font_dir = Path(__file__).parent.parent / "fonts" # Assumes core/fonts
        # if bundled_font_dir.is_dir():
        #     for ext in possible_extensions:
        #         potential_path = bundled_font_dir / f"{font_name}{ext}"
        #         if potential_path.exists():
        #             self.logger.info(f"Found bundled font: {potential_path}")
        #             return str(potential_path)
        #         potential_path_mapped = bundled_font_dir / target_filename
        #         if potential_path_mapped.exists():
        #             self.logger.info(f"Found bundled font (mapped): {potential_path_mapped}")
        #             return str(potential_path_mapped)

        # Search system directories
        for font_dir in system_font_dirs:
            if font_dir.is_dir():
                for ext in possible_extensions:
                    # Try exact name first
                    potential_path = font_dir / f"{font_name}{ext}"
                    if potential_path.exists():
                        self.logger.info(
                            f"Found system font: {potential_path}")
                        return str(potential_path)

                    # Try target_filename (mapped from common names)
                    potential_path_mapped = font_dir / target_filename
                    if potential_path_mapped.exists():
                        self.logger.info(
                            f"Found system font (mapped): {potential_path_mapped}"
                        )
                        return str(potential_path_mapped)

                    # Fallback: iterate through directory for case-insensitive partial matches (can be slow)
                    # for item in font_dir.iterdir():
                    #     if item.is_file() and item.stem.lower() == font_name_lower and item.suffix.lower() in possible_extensions:
                    #         self.logger.info(f"Found system font (iterated): {item}")
                    #         return str(item)

        self.logger.warning(
            f"Font '{font_name}' (as '{target_filename}') not found in searched system directories."
        )
        return None

import asyncio
import logging
import threading
import traceback
from typing import Dict, Optional, Union  # Added Callable and Union

import dearpygui.dearpygui as dpg  # Changed from flet

# from flet import Icons # DPG doesn't use Flet Icons directly
# from core.theme_manager import ThemeManager # Removed as the file is deleted
from core.codebase_guardian import UnifiedGuardian
from core.command_bar import CommandBar  # Import CommandBar

# from core import ThemeManager, UnifiedGuardian # ThemeManager is Flet specific for now
from core.config import AppConfig
from core.theme_manager import ThemeManager  # Import ThemeManager
from modules import (
    BaseModule,
    FlashcardModule,
    NotesModule,
    ProgressModule,
    SettingsModule,
    StatisticsModule,
    TaskModule,
)

# --- Logger Setup --- (assuming this is the main app logger)
# This is a bit unusual to have here directly, usually it's in main.py or a dedicated config
# However, if this is the intended global logger config, we can use it.
# For now, let's assume a logger is obtained in __init__
# logger = logging.getLogger(__name__) # Example of getting a logger


# Define logger at module level for StudyOS
logger = logging.getLogger(__name__)


class Core:
    """Central service container"""

    def __init__(self, app: "StudyOS"):
        print("[Core.__init__] Initializing Core...")  # ADD LOG
        self.app = app
        self.config = AppConfig.load_config()
        self.module_registry = ModuleRegistry()
        self.guardian = UnifiedGuardian()
        # Initialize theme manager with core reference
        self.theme_manager = ThemeManager(self)  # Add self as parameter
        print("[Core.__init__] Core initialized.")  # ADD LOG


# This async main seems unused by the ft.app(target=main) at the bottom, which uses the sync main.
# async def main(page: ft.Page):
#     # This was the previous approach for starting guardian, kept for reference
#     # guardian = UnifiedGuardian()
#     # asyncio.create_task(guardian.start())


class ModuleRegistry:
    """Dependency injection container for modules"""

    def __init__(self):
        print("[ModuleRegistry.__init__] Initializing ModuleRegistry...")  # ADD LOG
        self._modules: Dict[str, BaseModule] = {}
        print("[ModuleRegistry.__init__] ModuleRegistry initialized.")  # ADD LOG

    def register(self, name: str, module: BaseModule):
        self._modules[name] = module

    def get(self, name: str) -> BaseModule | None:
        return self._modules.get(name)


class StudyOS:
    PRIMARY_WINDOW_TAG = "primary_window"
    NAV_RAIL_TAG = "nav_rail_group"
    MODULE_DISPLAY_TAG = "module_display_group"
    COMMAND_BAR_CONTAINER_TAG = (
        "command_bar_container_group"  # New tag for command bar parent
    )
    LOADING_TEXT_TAG = "loading_text_indicator"
    CONTENT_AREA_TAG = "content_area_group"
    MODULE_VIEW_AREA_TAG = "module_view_area_group"
    SIDEBAR_TAG = "studos_sidebar_group"
    SIDEBAR_ACTUAL_WINDOW_TAG = "sidebar_actual_window_content_area"  # New unique tag
    MAIN_CONTENT_GROUP_TAG = "main_content_group"
    SIDEBAR_TOGGLE_BTN_TAG = "sidebar_toggle_button"
    TOP_CONTROLS_GROUP_TAG = "top_controls_group"

    def __init__(self):
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )  # Add logger to StudyOS
        self.logger.info("Initializing StudyOS...")
        print("[StudyOS.__init__] Initializing StudyOS...")
        self.core = Core(self)
        self.current_module_key = None
        self.command_bar = CommandBar(self)
        self.font_size = 16
        self.sidebar_width = 250
        print("[StudyOS.__init__] StudyOS initialized.")

    def _start_background_services(self):  # Keep for future, but comment call
        """Starts long-running background services."""

        def guardian_runner():
            asyncio.run(self.core.guardian.start())

        guardian_thread = threading.Thread(target=guardian_runner, daemon=True)
        guardian_thread.name = "UnifiedGuardianThread"
        guardian_thread.start()

    def _setup_dpg_viewport_and_window(self):
        print(
            "[StudyOS._setup_dpg_viewport_and_window] Setting up viewport...",
        )  # ADD LOG
        # Start maximized, but provide a sensible default width/height
        # if the window is restored or if maximized isn't supported/desired.
        # dpg.create_viewport(title="NeuroStudy OS", width=1280, height=800, maximized=True)
        dpg.create_viewport(
            title="NeuroStudy OS",
            width=1280,
            height=800,
        )  # Temporarily remove maximized=True
        print(
            "[StudyOS._setup_dpg_viewport_and_window] Viewport setup complete.",
        )  # ADD LOG

        # The primary window will now be setup in _init_dpg_ui_layout for better structure
        # with dpg.window(label="Main Application Window", tag=self.PRIMARY_WINDOW_TAG, width=dpg.get_viewport_width(), height=dpg.get_viewport_height()):
        #     dpg.add_text("NeuroStudy OS Content Area - Placeholder") # This will be removed
        # dpg.set_primary_window(self.PRIMARY_WINDOW_TAG, True)

    def _init_modules_and_registry(self):
        print(
            "[StudyOS._init_modules_and_registry] Initializing modules and registry...",
        )  # ADD LOG
        """Instantiate modules and register them with the core registry."""
        notes_module = NotesModule(self.core)
        task_module = TaskModule(self.core)
        flashcard_module = FlashcardModule(self.core)
        progress_module = ProgressModule(self.core)
        settings_module = SettingsModule(self.core)
        statistics_module = StatisticsModule(self.core)

        self.registered_module_instances = {
            "Notes": notes_module,
            "Tasks": task_module,
            "Flashcards": flashcard_module,
            "Progress": progress_module,
            "Settings": settings_module,
            "Stats": statistics_module,
        }

        for name, instance in self.registered_module_instances.items():
            self.core.module_registry.register(name, instance)
        print(
            "[StudyOS._init_modules_and_registry] Modules and registry initialized.",
        )  # ADD LOG

    def _init_dpg_ui_layout(self):
        """Initialize the main UI layout with Dear PyGui."""
        try:
            # Initialize the tab ID to module mapping dictionary
            self.tab_id_to_module = {}

            print("[StudyOS._init_dpg_ui_layout] Initializing DPG UI layout...")

            # Add width calculation for sidebar/main content
            initial_sidebar_width = 250
            self.sidebar_width = initial_sidebar_width  # Store for toggling

            with dpg.window(
                label="Main Application",
                tag=self.PRIMARY_WINDOW_TAG,
                width=-1,
                height=-1,
                no_title_bar=True,
                no_resize=True,
                no_move=True,
            ):
                with dpg.group(horizontal=True):  # Main horizontal layout
                    # --- Sidebar (Left) ---
                    with dpg.group(tag=self.SIDEBAR_TAG, width=self.sidebar_width):
                        dpg.add_button(
                            label="<",  # Initial label for "visible" state
                            tag=self.SIDEBAR_TOGGLE_BTN_TAG,
                            callback=self._toggle_sidebar,
                            width=-1,  # Span the width of the sidebar
                            height=30,
                        )
                        with dpg.tooltip(
                            self.SIDEBAR_TOGGLE_BTN_TAG
                        ):  # Move tooltip too
                            dpg.add_text("Toggle Sidebar Visibility")

                        # dpg.add_separator() # Removed original separator, button is now first

                        # --- Populate Sidebar with Note Tree --- START
                        notes_module_instance = self.core.module_registry.get(
                            "Notes")
                        if (
                            notes_module_instance
                            and hasattr(notes_module_instance, "build_sidebar_view")
                            and callable(notes_module_instance.build_sidebar_view)
                        ):
                            print(
                                "[StudyOS._init_dpg_ui_layout] Calling NotesModule.build_sidebar_view...",
                            )
                            try:
                                notes_module_instance.build_sidebar_view(
                                    self.SIDEBAR_TAG,
                                )
                            except SystemError as se:
                                print(
                                    f"[StudyOS._init_dpg_ui_layout] CRITICAL SystemError during NotesModule.build_sidebar_view: {se}",
                                )
                                print(
                                    f"[StudyOS._init_dpg_ui_layout] Traceback: {traceback.format_exc()}",
                                )
                                if dpg.does_item_exist(self.SIDEBAR_TAG):
                                    dpg.add_text(
                                        "Notes sidebar FAILED to load due to SystemError.",
                                        parent=self.SIDEBAR_TAG,
                                        color=(255, 0, 0),
                                    )
                            except Exception as e:
                                print(
                                    f"[StudyOS._init_dpg_ui_layout] EXCEPTION during NotesModule.build_sidebar_view: {e}",
                                )
                                print(
                                    f"[StudyOS._init_dpg_ui_layout] Traceback: {traceback.format_exc()}",
                                )
                                if dpg.does_item_exist(self.SIDEBAR_TAG):
                                    dpg.add_text(
                                        "Notes sidebar FAILED to load due to Exception.",
                                        parent=self.SIDEBAR_TAG,
                                        color=(255, 0, 0),
                                    )
                        else:
                            print(
                                "[StudyOS._init_dpg_ui_layout] Notes module or build_sidebar_view not found.",
                            )
                            if dpg.does_item_exist(
                                self.SIDEBAR_TAG,
                            ):  # Ensure parent exists before adding text
                                dpg.add_text(
                                    "Notes tree failed to load.",
                                    parent=self.SIDEBAR_TAG,
                                    color=(255, 0, 0),
                                )
                        # --- Populate Sidebar with Note Tree --- END
                        # Sidebar content here was a placeholder comment, actual population is above

                    # --- Main Content Area (Right) ---
                    with dpg.group(tag=self.MAIN_CONTENT_GROUP_TAG, width=-1):
                        # dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (50, 50, 0, 100), parent=self.MAIN_CONTENT_GROUP_TAG) # REVERTED

                        # Top controls group (toggle button and command bar)
                        with dpg.group(
                            horizontal=True,
                            tag=self.TOP_CONTROLS_GROUP_TAG,
                            width=-1,
                        ):
                            # dpg.add_button(
                            #     label="<",
                            #     tag=self.SIDEBAR_TOGGLE_BTN_TAG,
                            #     callback=self._toggle_sidebar,
                            #     width=30,
                            #     height=30,
                            # )
                            # with dpg.tooltip(self.SIDEBAR_TOGGLE_BTN_TAG):
                            # dpg.add_text("Toggle Sidebar Visibility")

                            # dpg.add_spacer(width=10) # REMOVE
                            # dpg.add_text("DEBUG_TEXT_A", color=(255, 0, 0)) # REMOVE
                            # print(f"[DEBUG] TOP_CONTROLS_GROUP_TAG exists: {dpg.does_item_exist(self.TOP_CONTROLS_GROUP_TAG)}") # Can keep or remove print

                            # Restore Command Bar build logic if it was commented out for this group
                            if self.command_bar:
                                if hasattr(self.command_bar, "_initialize_dpg_tags"):
                                    # This might be an issue if called multiple times
                                    self.command_bar._initialize_dpg_tags()
                                print(
                                    "[StudyOS._init_dpg_ui_layout] Building Command Bar view (original location - will be empty for now)...",
                                )
                                # self.command_bar.build_dpg_view( # Call will be moved
                                #     parent_tag=self.TOP_CONTROLS_GROUP_TAG
                                # )
                                print(
                                    "[StudyOS._init_dpg_ui_layout] Command Bar build call skipped from original location.",
                                )
                            else:
                                print(
                                    "[StudyOS._init_dpg_ui_layout] Command bar not available",
                                )

                        # Add separator between top controls and tab bar
                        dpg.add_separator()
                        dpg.add_spacer(height=5)

                        # Create the main tab bar for modules
                        self.main_tabbar_id = dpg.add_tab_bar(
                            callback=self._on_tab_selected,
                        )

                        # Create tabs for each module
                        for (
                            module_key,
                            module_instance,
                        ) in self.registered_module_instances.items():
                            # Create a tab for this module
                            tab_id = dpg.add_tab(
                                label=module_key,
                                parent=self.main_tabbar_id,
                            )
                            print(
                                f"[StudyOS._init_dpg_ui_layout] Created tab with ID {tab_id} for module '{module_key}'",
                            )

                            # Store the mapping of tab ID to module key
                            self.tab_id_to_module[tab_id] = module_key

                            # Create a container group INSIDE the tab with the specific tag
                            tab_content_area_tag = f"tab_content_{module_key}"
                            with dpg.group(parent=tab_id, tag=tab_content_area_tag):
                                # Add a placeholder initially, it will be replaced by switch_module
                                dpg.add_text(
                                    f"Loading {module_key}...",
                                    tag=f"placeholder_{module_key}",
                                )

            # Set primary window
            dpg.set_primary_window(self.PRIMARY_WINDOW_TAG, True)
            print(
                "[StudyOS._init_dpg_ui_layout] DPG UI layout initialized with tabs and sidebar.",
            )

            # Add a Main Menu Bar
            with dpg.menu_bar(parent=self.PRIMARY_WINDOW_TAG):
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="New Note",
                                      callback=self._menu_new_note)
                    dpg.add_menu_item(
                        label="Save All Notes",
                        callback=self._menu_save_all_notes,
                    )
                    dpg.add_separator()
                    dpg.add_menu_item(
                        label="Exit",
                        callback=lambda: dpg.stop_dearpygui(),
                    )

                with dpg.menu(label="Settings"):
                    dpg.add_menu_item(
                        label="App Settings",
                        callback=self._menu_open_settings,
                    )

                with dpg.menu(label="Help"):
                    dpg.add_menu_item(label="About StudyOS",
                                      callback=self._menu_about)

            # Define the "About" window (modal, initially hidden)
            # Ensure this tag is unique and managed if multiple modals are added later
            about_window_tag = "about_studyos_window"
            if not dpg.does_item_exist(about_window_tag):
                with dpg.window(
                    label="About StudyOS",
                    modal=True,
                    show=False,
                    tag=about_window_tag,
                    width=400,
                    height=200,
                    no_resize=True,
                    no_close=False,
                ):
                    dpg.add_text("StudyOS - Your Second Brain")
                    dpg.add_text("Version: 0.1.0 (Alpha)")
                    dpg.add_separator()
                    dpg.add_text("Developed with Dear PyGui and Python.")
                    dpg.add_spacer(height=10)
                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="OK",
                            width=-1,
                            callback=lambda: dpg.configure_item(
                                about_window_tag,
                                show=False,
                            ),
                        )

        except Exception as e:
            print(
                f"[StudyOS._init_dpg_ui_layout] Error initializing DPG UI layout: {e}",
            )
            traceback.print_exc()

    def _toggle_sidebar(self, sender, app_data, user_data):
        """Toggles the visibility of the sidebar group."""
        # Use class attributes for tags
        current_sidebar_tag = self.SIDEBAR_TAG
        toggle_button_tag = self.SIDEBAR_TOGGLE_BTN_TAG

        if not dpg.does_item_exist(current_sidebar_tag):
            self.logger.error(
                f"Sidebar tag '{current_sidebar_tag}' does not exist during toggle.",
            )
            return
        # It's okay if the button doesn't exist for some reason, just log it if we try to use it.

        is_visible = dpg.is_item_shown(current_sidebar_tag)

        if is_visible:
            dpg.hide_item(current_sidebar_tag)
            if dpg.does_item_exist(toggle_button_tag):
                dpg.set_item_label(toggle_button_tag, ">")
            else:
                self.logger.warning(
                    f"Sidebar toggle button '{toggle_button_tag}' not found when trying to set label.",
                )
            self.logger.info("Sidebar hidden.")
        else:
            # Explicitly set width before showing to ensure it's restored
            dpg.configure_item(current_sidebar_tag, width=self.sidebar_width)
            dpg.show_item(current_sidebar_tag)
            if dpg.does_item_exist(toggle_button_tag):
                dpg.set_item_label(toggle_button_tag, "<")
            else:
                self.logger.warning(
                    f"Sidebar toggle button '{toggle_button_tag}' not found when trying to set label.",
                )
            self.logger.info(f"Sidebar shown with width {self.sidebar_width}.")

    def _on_tab_selected(self, sender, app_data, user_data):
        """Callback executed when a module tab is selected."""
        print(
            f"[_on_tab_selected] Tab selection: sender={sender}, app_data={app_data}")

        # Use the mapping we created during initialization
        module_key = self.tab_id_to_module.get(app_data)

        if module_key:
            print(f"[_on_tab_selected] Selected module: {module_key}")

            # Proceed to switch module
            def run_async_switch():
                try:
                    asyncio.run(self.switch_module(module_key))
                except RuntimeError as e:
                    print(
                        f"[_on_tab_selected] RuntimeError running switch_module for {module_key}: {e}.",
                    )
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.switch_module(module_key))
                    except Exception as inner_e:
                        print(
                            f"[_on_tab_selected] Error running switch_module in new loop for {module_key}: {inner_e}",
                        )

            thread = threading.Thread(target=run_async_switch, daemon=True)
            thread.start()
        else:
            print(
                f"[_on_tab_selected] Could not find module for tab ID: {app_data}")
            print(
                f"[_on_tab_selected] Available mappings: {self.tab_id_to_module}")

    async def _load_initial_module_view(self):
        print(
            "[StudyOS._load_initial_module_view] Loading initial module view...",
        )  # ADD LOG
        if self.registered_module_instances:
            initial_module_key = list(
                self.registered_module_instances.keys())[0]
            await self.switch_module(initial_module_key)  # Add await
        print(
            "[StudyOS._load_initial_module_view] Initial module view loaded.",
        )  # ADD LOG

    async def switch_module(self, module_key_or_instance: Union[str, BaseModule]):
        """Switches the main view to the specified module (now async)"""
        print(
            f"[StudyOS.switch_module] Attempting to switch to module: {module_key_or_instance}",
        )  # ADD LOG
        module_instance: Optional[BaseModule] = None
        current_key_to_set: Optional[str] = None

        if isinstance(module_key_or_instance, str):
            current_key_to_set = module_key_or_instance
            module_instance = self.core.module_registry.get(
                module_key_or_instance)
            if not module_instance:
                print(
                    f"[StudyOS.switch_module] Error: Module key '{module_key_or_instance}' not found in registered instances.",
                )
                if dpg.does_item_exist(self.MODULE_VIEW_AREA_TAG):
                    dpg.delete_item(self.MODULE_VIEW_AREA_TAG,
                                    children_only=True)
                    with dpg.group(parent=self.MODULE_VIEW_AREA_TAG):
                        dpg.add_text(
                            f"Error: Module '{module_key_or_instance}' could not be loaded.",
                            color=(255, 0, 0),
                        )
                return
        elif isinstance(module_key_or_instance, BaseModule):
            module_instance = module_key_or_instance
            for key, instance in self.registered_module_instances.items():
                if instance == module_instance:
                    current_key_to_set = key
                    break
            if current_key_to_set is None:
                print(
                    "[StudyOS.switch_module] Error: Provided module instance not found in registered_module_instances.",
                )
                return
        else:
            print(
                f"[StudyOS.switch_module] Error: Invalid type for module_key_or_instance: {type(module_key_or_instance)}.",
            )
            return

        # MODULE_VIEW_AREA_TAG (the old way).
        # Find the correct parent tag for the module's content within its tab.
        module_tab_content_tag = f"tab_content_{current_key_to_set}"

        if dpg.does_item_exist(module_tab_content_tag):
            # Clear previous content from the tab's content area first
            dpg.delete_item(module_tab_content_tag, children_only=True)
        else:
            print(
                f"[StudyOS.switch_module] Error: Tab content area '{module_tab_content_tag}' does not exist. Cannot build view.",
            )
            # Display error in the main area if tab area fails?
            # Or perhaps log and return.
            return  # Stop if the target container isn't there

        # Build and add the new module's view
        if hasattr(module_instance, "build_dpg_view") and callable(
            module_instance.build_dpg_view,
        ):
            try:
                # --- Initialize DPG Tags (if applicable) --- START
                if hasattr(module_instance, "initialize_dpg_tags") and callable(
                    module_instance.initialize_dpg_tags,
                ):
                    print(
                        f"[StudyOS.switch_module] Initializing DPG tags for module: {current_key_to_set}",
                    )
                    module_instance.initialize_dpg_tags()
                # --- Initialize DPG Tags (if applicable) --- END

                print(
                    f"[StudyOS.switch_module] Building DPG view for module: {current_key_to_set} into {module_tab_content_tag}",
                )
                # Pass the specific tab's content area tag as the parent
                module_instance.build_dpg_view(
                    parent_container_tag=module_tab_content_tag,
                )
                print(
                    f"[StudyOS.switch_module] Finished building DPG view for module: {current_key_to_set}",
                )  # ADD LOG
            except Exception as e:
                print(
                    f"[StudyOS.switch_module] Error building DPG view for {current_key_to_set}: {e}",
                )
                # Display error message within the tab's content area
                if dpg.does_item_exist(module_tab_content_tag):
                    # Ensure the placeholder is removed before adding error
                    placeholder_tag = f"placeholder_{current_key_to_set}"
                    if dpg.does_item_exist(placeholder_tag):
                        dpg.delete_item(placeholder_tag)
                    dpg.add_text(
                        f"Error building view for {current_key_to_set}: {e}",
                        color=(255, 0, 0),
                        parent=module_tab_content_tag,
                    )
        else:
            print(
                f"[StudyOS.switch_module] Module {current_key_to_set} does not have a callable build_dpg_view method.",
            )
            # Display error message within the tab's content area
            if dpg.does_item_exist(module_tab_content_tag):
                # Ensure the placeholder is removed before adding error
                placeholder_tag = f"placeholder_{current_key_to_set}"
                if dpg.does_item_exist(placeholder_tag):
                    dpg.delete_item(placeholder_tag)
                dpg.add_text(
                    f"Cannot display module {current_key_to_set}. No view available.",
                    color=(255, 0, 0),
                    parent=module_tab_content_tag,
                )

        # Call the new module's load_data method if it exists and DPG is running
        if (
            dpg.is_dearpygui_running()
            and hasattr(module_instance, "load_data")
            and callable(module_instance.load_data)
        ):
            try:
                print(
                    f"[StudyOS.switch_module] Calling load_data for {current_key_to_set}...",
                )
                # Properly handle async/sync load_data
                if asyncio.iscoroutinefunction(module_instance.load_data):
                    await module_instance.load_data()
                else:
                    # Wrap sync call in executor
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, module_instance.load_data)
                print(
                    f"[StudyOS.switch_module] load_data for {current_key_to_set} finished.",
                )
            except Exception as e:
                print(
                    f"[StudyOS.switch_module] Error calling load_data for {current_key_to_set}: {e}",
                )

        self.current_module_key = current_key_to_set  # Use the determined key
        print(
            f"[StudyOS.switch_module] Switched to module: {self.current_module_key}")

    def _handle_dpg_resize(self, sender, app_data):
        """Responsive layout handler for DPG viewport."""
        width = dpg.get_viewport_width()
        height = dpg.get_viewport_height()
        if dpg.does_item_exist(self.PRIMARY_WINDOW_TAG):
            dpg.configure_item(self.PRIMARY_WINDOW_TAG,
                               width=width, height=height)

        nav_width = 200
        if dpg.does_item_exist(self.NAV_RAIL_TAG):
            dpg.configure_item(self.NAV_RAIL_TAG, width=nav_width)
        # The module display group should adjust automatically if it's the last expanding item
        # in a horizontal group, or if we set its width explicitly like:
        # module_display_width = width - nav_width - any_spacing
        # dpg.configure_item(self.MODULE_DISPLAY_TAG, width=module_display_width)

    async def run_dpg_app(self):
        dpg.create_context()
        print("[StudyOS.run_dpg_app] DPG context created.")

        # Create viewport early. This was previously in _setup_dpg_viewport_and_window
        # but let's ensure it's explicitly part of this main sequence if that method isn't always called.
        # Actually, _setup_dpg_viewport_and_window handles this.
        self._setup_dpg_viewport_and_window()
        print(
            "[StudyOS.run_dpg_app] Viewport setup called via _setup_dpg_viewport_and_window.",
        )

        # Initialize theme manager first
        self.core.theme_manager.initialize()
        print("[StudyOS.run_dpg_app] Theme manager initialized.")

        # Initialize modules AFTER DPG context and theme manager
        self._init_modules_and_registry()  # SYNC
        print("[StudyOS.run_dpg_app] Modules and registry initialized.")

        # Initialize UI components (creates window, tabs, placeholders)
        self._init_dpg_ui_layout()  # SYNC
        print("[StudyOS.run_dpg_app] DPG UI layout initialized.")

        # Load the view for the initial module
        print("[StudyOS.run_dpg_app] Attempting to load initial module view...")
        try:
            await self._load_initial_module_view()  # Ensure this is awaited
            print("[StudyOS.run_dpg_app] Initial module view loaded successfully.")
        except Exception as e:
            print(
                f"[StudyOS.run_dpg_app] CRITICAL ERROR loading initial module view: {e}",
            )
            traceback.print_exc()
            # Optionally, display an error in the UI if possible at this stage

        # Setup DPG (configures DPG with all created items)
        dpg.setup_dearpygui()
        print("[StudyOS.run_dpg_app] Dear PyGui setup complete.")

        dpg.show_viewport()  # Makes the viewport visible
        print("[StudyOS.run_dpg_app] Viewport shown.")

        # Primary window should be set within _init_dpg_ui_layout or immediately after window creation.
        # dpg.set_primary_window(self.PRIMARY_WINDOW_TAG, True) # This is already in _init_dpg_ui_layout
        # print("[StudyOS.run_dpg_app] Primary window set (or confirmed).")

        print("[StudyOS.run_dpg_app] Starting Dear PyGui main loop...")
        dpg.start_dearpygui()  # This blocks
        print("[StudyOS.run_dpg_app] Dear PyGui main loop finished.")

        dpg.destroy_context()
        print("[StudyOS.run_dpg_app] DPG context destroyed.")

    def _global_key_down_handler(self, sender, app_data):
        if (key_code := app_data) and (active_module := self.get_active_module()):
            if hasattr(active_module, "handle_keyboard"):
                active_module.handle_keyboard(key_code)

    async def _navigate_next_module(self):
        module_keys = list(self.registered_module_instances.keys())
        if module_keys:
            current_index = (
                module_keys.index(self.current_module_key)
                if self.current_module_key
                else 0
            )
            new_index = (current_index + 1) % len(module_keys)
            await self.switch_module(module_keys[new_index])
            self._focus_first_component()

    def _navigate_previous_module(self):
        module_keys = list(self.registered_module_instances.keys())
        if not module_keys:
            return

        current_index = (
            module_keys.index(
                self.current_module_key) if self.current_module_key else 0
        )
        new_index = (current_index - 1) % len(module_keys)
        # Create new event loop for sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.switch_module(module_keys[new_index]))
        self._focus_first_component()

    def _focus_first_component(self):
        if self.current_module_key and (
            module := self.core.module_registry.get(self.current_module_key)
        ):
            if hasattr(module, "get_focusable_items"):
                focusables = module.get_focusable_items()
                if focusables:
                    dpg.focus_item(focusables[0])

    # _global_key_release_handler removed
    # def _global_key_release_handler(self, sender, app_data, user_data):
    #    ...

    def _navigate_horizontal_components(self, direction: int):
        # Implementation logic here
        pass

    def _handle_space_key(self):
        # Implementation logic here
        pass

    def _save_window_state(self):
        # Implementation logic here
        # Example: Save window size, position, current module, etc.
        # For now, it does nothing.
        print("[StudyOS._save_window_state] Called (currently a stub).")
        # If it were to call async operations, it would use await here.
        # Example: await some_async_save_operation()

    def get_active_module(self):
        if self.current_module_key:
            return self.core.module_registry.get(self.current_module_key)
        return None

    def _load_font(self, font_name: str) -> Optional[int]:
        try:
            font_path = self._find_font_path(font_name)
            if not font_path:
                print(f"Font not found: {font_name}, using default")
                return 0  # Return default font ID

            # dpg.add_font might be typed as returning int | str by the linter
            loaded_font_id = dpg.add_font(str(font_path), self.font_size)

            if isinstance(loaded_font_id, str):
                # If dpg.add_font returns a string, this is unexpected for a font ID.
                # Log this scenario and return the default font ID (0).
                print(
                    f"Warning: dpg.add_font returned a string ('{loaded_font_id}') for font '{font_name}'. Using default font ID.",
                )
                return 0

            # At this point, loaded_font_id should be an int if no string was returned.
            return loaded_font_id
        except Exception as e:
            print(f"Font load error: {e}")

    # --- Font Handling Placeholder ---
    def _find_font_path(self, font_name: str) -> Optional[str]:
        """Placeholder for font finding logic.
        Should search system paths or bundled fonts.
        Returns the absolute path as a string if found, otherwise None.
        """
        print(
            f"[StudyOS._find_font_path] Searching for font: {font_name} (Placeholder - returning None)",
        )
        # TODO: Implement actual font searching logic (e.g., using matplotlib.font_manager or platform specific methods)
        # Example: Check common locations or a bundled 'fonts' directory
        # font_dir = Path(__file__).parent.parent / "fonts" # Assuming fonts dir exists
        # potential_path = font_dir / f"{font_name}.ttf"
        # if potential_path.exists():
        #    return str(potential_path)
        return None  # Default: Font not found

    def _menu_open_settings(self, sender, app_data, user_data):
        """Switches to the Settings module tab via a thread to handle async call."""
        module_key = "Settings"
        print(
            f"[StudyOS._menu_open_settings] Menu item clicked, preparing to switch to module: {module_key}",
        )

        def run_async_switch_settings():
            try:
                # Ensure a new event loop for the thread if necessary
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.switch_module(module_key))
            except RuntimeError as e:
                # This might happen if an event loop is already running in the main thread
                # and DPG callbacks are in a context where new_event_loop is problematic.
                # A more robust solution might involve an asyncio queue if this becomes an issue.
                print(
                    f"[StudyOS._menu_open_settings] RuntimeError running switch_module for {module_key}: {e}. Trying without new loop.",
                )
                # Fallback: try running directly if a loop is somehow available from DPG's context for the thread
                try:
                    asyncio.run(
                        self.switch_module(module_key),
                    )  # This might still have issues with nested loops
                except RuntimeError as e2:
                    print(
                        f"[StudyOS._menu_open_settings] Nested RuntimeError for {module_key}: {e2}. Manual switch in main thread might be needed or queue.",
                    )
                except Exception as ex:
                    print(
                        f"[StudyOS._menu_open_settings] General Exception running switch_module for {module_key}: {ex}",
                    )
            except Exception as ex_outer:
                print(
                    f"[StudyOS._menu_open_settings] Outer Exception for {module_key}: {ex_outer}",
                )

        thread = threading.Thread(
            target=run_async_switch_settings, daemon=True)
        thread.start()
        print(
            f"[StudyOS._menu_open_settings] Thread started for switching to {module_key}",
        )

    def _menu_new_note(self, sender, app_data, user_data):
        """Handles the File > New Note menu action."""
        print("[StudyOS._menu_new_note] 'New Note' menu item selected.")
        notes_module = self.get_module_by_key("Notes")
        if (
            isinstance(notes_module, NotesModule)
            and hasattr(notes_module, "_create_new_note")
            and callable(notes_module._create_new_note)
        ):
            notes_module._create_new_note(
                sender, app_data)  # Pass through DPG args
            print("[StudyOS._menu_new_note] Called NotesModule._create_new_note().")
        else:
            print(
                "[StudyOS._menu_new_note] NotesModule or its _create_new_note method not found/callable.",
            )

    def _menu_save_all_notes(self, sender, app_data, user_data):
        """Handles the File > Save All Notes menu action."""
        print("[StudyOS._menu_save_all_notes] 'Save All Notes' menu item selected.")
        notes_module = self.get_module_by_key("Notes")
        if (
            isinstance(notes_module, NotesModule)
            and hasattr(notes_module, "_save_notes")
            and callable(notes_module._save_notes)
        ):
            notes_module._save_notes()
            print("[StudyOS._menu_save_all_notes] Called NotesModule._save_notes().")
            # Optionally, provide user feedback e.g., via a status bar update
        else:
            print(
                "[StudyOS._menu_save_all_notes] NotesModule or its _save_notes method not found/callable.",
            )

    def _menu_about(self, sender, app_data, user_data):
        """Handles the Help > About StudyOS menu action."""
        about_window_tag = "about_studyos_window"
        if dpg.does_item_exist(about_window_tag):
            print(f"[StudyOS._menu_about] Showing '{about_window_tag}'.")
            dpg.configure_item(about_window_tag, show=True)
        else:
            print(
                f"[StudyOS._menu_about] Error: '{about_window_tag}' does not exist.")

    # --- Utility Methods ---
    def get_module_by_key(self, module_key: str) -> Optional[BaseModule]:
        return self.core.module_registry.get(module_key)


# Remove Flet-specific main and app runner
# def main(page: ft.Page):
#     StudyOS(page)
#
# if __name__ == "__main__":
#     ft.app(target=main, view=ft.AppView.FLET_APP)

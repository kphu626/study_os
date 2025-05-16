import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from core.app import StudyOS  # Main application class

# Ensure the app's root directory is in the Python path
# This allows a_sync_configs.run_tests.py to import modules from the main app
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.append(str(SCRIPT_DIR))


# Import module types for type hinting if needed later
# from modules.notes_module import NotesModule
# from modules.settings_module import SettingsModule

# --- Logger Setup ---
LOG_FILE_PATH = SCRIPT_DIR / "test_run.log"
# Clear previous log file
if LOG_FILE_PATH.exists():
    LOG_FILE_PATH.unlink()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-7s] [%(name)-20s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout),  # Also print to console
    ],
)
logger = logging.getLogger("TEST_RUNNER")


# --- Test Context ---
class TestContext:
    def __init__(self, app: StudyOS):
        self.app = app
        self.core = app.core
        self.notes_module = app.core.module_registry.get(
            "Notes"
        )  # Corrected method name
        self.settings_module = app.core.module_registry.get(
            "Settings"
        )  # Corrected method name
        # Add other modules as needed


test_suite = []
current_test_index = 0
overall_test_status = True
test_context_global: Optional[TestContext] = None


def log_test_status(test_name: str, status: str, details: str = ""):
    global overall_test_status
    if status.upper() == "FAIL" or status.upper() == "ERROR":
        overall_test_status = False
        logger.error(
            f"Test: {test_name} - Status: {status} - Details: {details if details else 'N/A'}"
        )
    elif status.upper() == "SUCCESS":
        logger.info(f"Test: {test_name} - Status: {status}")
    elif status.upper() == "START":
        logger.info(f"Test: {test_name} - Status: STARTING...")
    else:  # INFO, PROGRESS, etc.
        logger.info(
            f"Test: {test_name} - Status: {status} - Details: {details if details else ''}"
        )


# --- Test Definitions ---
# Placeholder for actual test functions
# Each test function should take 'context: TestContext' as an argument
# and return True for success, False for failure.


def placeholder_test_example(context: TestContext):
    test_name = "placeholder_test_example"
    log_test_status(test_name, "START")
    try:
        # Simulate some actions
        logger.info(f"[{test_name}] Performing mock actions...")
        time.sleep(0.1)  # Simulate work

        # Simulate a check
        if context.app is None:
            log_test_status(test_name, "FAIL", "App context is None.")
            return False

        log_test_status(test_name, "SUCCESS")
        return True
    except Exception as e:
        log_test_status(test_name, "ERROR", str(e))
        return False


# Add tests to the suite
test_suite.append(placeholder_test_example)
# test_suite.append(test_app_initialization) # Will be defined later
# test_suite.append(test_settings_change_theme) # Will be defined later
# test_suite.append(test_notes_create_and_save_note) # Will be defined later


# --- DPG Frame Callback for Test Execution ---
def run_tests_frame_callback(sender, app_data):
    global current_test_index, test_context_global, overall_test_status

    if test_context_global is None:
        logger.error("TestContext not initialized. Aborting tests.")
        dpg.stop_dearpygui()
        return

    if current_test_index < len(test_suite):
        test_func = test_suite[current_test_index]
        test_name = test_func.__name__

        # Run the test
        passed = False
        try:
            passed = test_func(test_context_global)
        except Exception as e:
            log_test_status(test_name, "ERROR",
                            f"Unhandled exception in test: {e}")
            passed = False  # Ensure it's marked as failed

        if (
            not passed and overall_test_status
        ):  # Check if overall status was flipped by log_test_status
            # If test_func returned False but didn't log FAIL/ERROR via log_test_status
            if not any(
                handler.level <= logging.ERROR
                for handler in logger.handlers
                if hasattr(handler, "level")
            ):  # A bit of a hack to see if error was already logged
                log_test_status(
                    test_name,
                    "FAIL",
                    "Test function returned False without specific error log.",
                )

        current_test_index += 1
        # Add a small delay to allow DPG to process UI events if tests interact heavily
        # For now, tests are calling methods directly, so this might not be strictly needed
        # If tests were simulating clicks via OS events, this would be crucial.
        # time.sleep(0.05)
    else:
        log_test_status(
            "ALL_TESTS_COMPLETED",
            "FINAL_SUMMARY",
            f"Overall Status: {'PASS' if overall_test_status else 'FAIL'}",
        )
        dpg.stop_dearpygui()


# --- Main Test Execution ---
def main():
    global test_context_global
    logger.info("Initializing Test Runner...")

    # 1. Create the application instance
    try:
        app = StudyOS()
        test_context_global = TestContext(app)  # Initialize global context
    except Exception as e:
        logger.critical(
            f"Failed to initialize StudyOS app for testing: {e}", exc_info=True
        )
        return

    logger.info("StudyOS App instance created for testing.")

    # 2. DPG Setup (adapted from core/app.py's run_dpg_app)
    # We need to replicate the setup sequence without the final blocking start_dearpygui()
    # and instead use our frame callback.

    try:
        core = app.core
        dpg.create_context()
        logger.info("DPG context created.")

        dpg.configure_app(
            manual_callback_management=True
        )  # Important for frame-by-frame control if needed
        logger.info("DPG manual_callback_management configured.")

        dpg.create_viewport(
            # Constants are on StudyOS (app instance)
            title=app.PRIMARY_WINDOW_TAG,
            width=1280,  # Using default values from StudyOS for now
            height=800,  # Using default values from StudyOS for now
            # title=app.APP_TITLE, # APP_TITLE is not directly on StudyOS, PRIMARY_WINDOW_TAG is more suitable or a new constant
            # width=app.initial_window_width, # initial_window_width is not directly on StudyOS
            # height=app.initial_window_height, # initial_window_height is not directly on StudyOS
        )
        logger.info("DPG viewport created.")

        # Initialize modules, theme, and UI layout (as done in Core.run_dpg_app which is actually StudyOS.run_dpg_app)
        # These calls are on the StudyOS instance (app)
        app._init_modules_and_registry()  # This will call __init__ on modules
        logger.info("Modules and registry initialized by StudyOS app.")

        # Theme manager is on core, but initialization should be done after modules possibly
        core.theme_manager.initialize()  # This applies theme and font
        logger.info("Theme Manager initialized by Core.")

        # Critical: Ensure the main UI structure is built so that tags exist for tests
        # This sets the primary window and calls build_module_content_area etc.
        app._init_dpg_ui_layout()
        logger.info("DPG UI layout initialized by StudyOS app.")

        dpg.set_viewport_vsync(True)  # Good practice
        dpg.setup_dearpygui()
        logger.info("Dear PyGui setup complete.")

        dpg.show_viewport()
        logger.info("Viewport shown.")

        # Load the initial module view before starting the test frame callback
        logger.info("Attempting to load initial module view asynchronously...")
        try:
            asyncio.run(app._load_initial_module_view())
            logger.info("Initial module view loaded.")
            # Add a frame split and a tiny delay to help DPG process UI changes from the async call
            dpg.split_frame()
            time.sleep(0.1)  # Increased slightly to allow for UI processing
            logger.info("DPG frame split and delay after initial module load.")

        except Exception as e:
            logger.critical(
                f"Failed to load initial module view: {e}", exc_info=True)
            # Decide if tests should be aborted here
            dpg.destroy_context()
            return

        # Instead of dpg.set_primary_window and dpg.start_dearpygui()...
        # We use a frame callback to run our tests.
        dpg.set_frame_callback(
            1, run_tests_frame_callback
        )  # Provide frame=1 and the callback
        logger.info(
            f"Test frame callback registered. Starting DPG render loop to run {len(test_suite)} tests..."
        )

        dpg.start_dearpygui()  # This will now be driven by our frame callback

    except Exception as e:
        logger.critical(
            f"An error occurred during DPG setup or test execution: {e}", exc_info=True
        )
    finally:
        if dpg.is_dearpygui_running():
            dpg.stop_dearpygui()
        dpg.destroy_context()
        logger.info("Test run finished. DPG context destroyed.")


if __name__ == "__main__":
    main()

import asyncio
import logging
import sys
from pathlib import Path

from core.app import StudyOS  # Import StudyOS

# --- Logger Setup ---
LOG_FILE_PATH = Path(__file__).resolve().parent / "app.log"
# Optional: Clear previous log file on each run
# if LOG_FILE_PATH.exists():
#     LOG_FILE_PATH.unlink()

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture more details initially
    format="[%(asctime)s] [%(levelname)-7s] [%(name)-25s] [%(funcName)-25s] %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE_PATH, mode="w"
        ),  # mode='w' to overwrite log each run
        logging.StreamHandler(sys.stdout),  # Also print to console
    ],
)

# Get a logger for the main script
logger = logging.getLogger(__name__)  # Use __name__ for the logger name
# --- End Logger Setup ---

# from flet import app, Page # No longer using Flet
print("[main.py] Importing StudyOS...")

print("[main.py] StudyOS imported.")

# ThemeManager is managed by StudyOS internally via its Core object
# from core.theme_manager import ThemeManager # No longer directly needed here
# Modules are also managed by StudyOS internally
# from modules import (
#     NotesModule,
#     FlashcardModule,
#     TaskModule,
#     ProgressModule,
#     SettingsModule,
#     StatisticsModule,
# )


async def main():
    print("[main.py] main() called")
    study_os = StudyOS()
    print("[main.py] StudyOS instance created.")

    # Let StudyOS handle theme initialization in run_dpg_app()
    print("[main.py] Calling run_dpg_app()...")
    await study_os.run_dpg_app()
    print("[main.py] run_dpg_app() finished.")


if __name__ == "__main__":
    print("[main.py] Starting application...")
    asyncio.run(main())
    print("[main.py] Application terminated.")
    # app(target=main) # Flet's app runner

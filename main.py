from core.app import StudyOS  # Import StudyOS
import dearpygui.dearpygui as dpg
import asyncio

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

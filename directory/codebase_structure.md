study_os/
├── main.py             # App entry point, routing, and theme
├── notes_module.py     # Markdown notes UI + logic
├── flashcards_module.py# Flashcards UI + spaced repetition
├── tasks_module.py     # Todo list with deadlines
├── progress_module.py  # Progress bar + stats
└── data/               # Auto-saved data
    ├── notes.json
    ├── flashcards.json
    └── tasks.json

import flet as ft
from notes_module import notes_ui
from flashcards_module import flashcards_ui
from tasks_module import tasks_ui
from progress_module import progress_ui

def main(page: ft.Page):
    # App settings
    page.title = "Study OS"
    page.theme_mode = ft.ThemeMode.DARK  # Default to dark mode
    page.padding = 0
    page.window_min_width = 800
    page.window_min_height = 600

    # Theme setup
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary="#4a8fe7",
            secondary="#44c4a1",
            surface="#1e1e1e",
            on_surface="#ffffff",
        ),
        text_theme=ft.TextTheme(body_medium=ft.TextStyle(size=16)),
    )

    # Navigation Rail (left sidebar)
    nav_rail = ft.NavigationRail(
        selected_index=0,
        destinations=[
            ft.NavigationRailDestination(icon=ft.icons.NOTE, label="Notes"),
            ft.NavigationRailDestination(icon=ft.icons.FLASH_ON, label="Flashcards"),
            ft.NavigationRailDestination(icon=ft.icons.TASK, label="Tasks"),
            ft.NavigationRailDestination(icon=ft.icons.BAR_CHART, label="Progress"),
        ],
        on_change=lambda e: navigate(e.control.selected_index),
    )

    # Content area (right side)
    content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def navigate(index: int):
        content.controls.clear()
        if index == 0:
            content.controls.append(notes_ui(page))
        elif index == 1:
            content.controls.append(flashcards_ui(page))
        elif index == 2:
            content.controls.append(tasks_ui(page))
        elif index == 3:
            content.controls.append(progress_ui(page))
        page.update()

    # Initial load
    navigate(0)
    page.add(
        ft.Row(
            [nav_rail, ft.VerticalDivider(width=1), content],
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)

import dearpygui.dearpygui as dpg
import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Union, Optional
from pydantic import ValidationError

from .base_module import BaseModule
from schemas import Flashcard

if TYPE_CHECKING:
    from core.app import Core


class FlashcardModule(BaseModule):
    def __init__(self, core: "Core"):
        super().__init__(core)
        if (
            hasattr(self.core, "config")
            and self.core.config is not None
            and hasattr(self.core.config, "flashcards_path")
        ):
            self.data_path = self.core.config.flashcards_path
        else:
            from core.config import AppConfig as DefaultAppConfig

            self.data_path = DefaultAppConfig().flashcards_path
            print(
                f"Warning: FlashcardModule could not find flashcards_path in core.config. Using default: {self.data_path}"
            )
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        self.cards: List[Flashcard] = []
        self.current_card_index: int = 0
        self.is_answer_visible: bool = False

        # DPG Tags - initialize with placeholders
        self.dpg_question_text_tag: Union[int, str] = 0
        self.dpg_answer_text_tag: Union[int, str] = 0
        self.dpg_card_info_text_tag: Union[int, str] = 0
        self.dpg_flip_button_tag: Union[int, str] = 0  # If we want to change its label

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the Dear PyGui view for the Flashcards module."""
        self.dpg_question_text_tag = dpg.generate_uuid()
        self.dpg_answer_text_tag = dpg.generate_uuid()
        self.dpg_card_info_text_tag = dpg.generate_uuid()
        self.dpg_flip_button_tag = dpg.generate_uuid()

        with dpg.group(parent=parent_container_tag):
            dpg.add_text("Flashcards", color=(220, 220, 220))
            dpg.add_separator()

            dpg.add_text("Question:", tag=dpg.generate_uuid())  # Static label
            # Use a child window for a bordered area if desired
            with dpg.child_window(height=100, border=True):
                dpg.add_text("Loading...", tag=self.dpg_question_text_tag, wrap=-1)

            dpg.add_spacer(height=5)
            dpg.add_text("Answer:", tag=dpg.generate_uuid())  # Static label
            with dpg.child_window(height=100, border=True):
                dpg.add_text(
                    "Click 'Flip' to see answer", tag=self.dpg_answer_text_tag, wrap=-1
                )

            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                prev_btn = dpg.add_button(
                    label="Previous", callback=self._dpg_prev_card, width=100
                )
                with dpg.tooltip(prev_btn):
                    dpg.add_text("Go to previous card")
                    dpg.add_text("Shortcut: Left Arrow")

                flip_btn = dpg.add_button(
                    label="Flip",
                    tag=self.dpg_flip_button_tag,
                    callback=self._dpg_flip_card,
                    width=100,
                )
                with dpg.tooltip(flip_btn):
                    dpg.add_text("Reveal/hide the answer")
                    dpg.add_text("Shortcut: Space bar")

                next_btn = dpg.add_button(
                    label="Next", callback=self._dpg_next_card, width=100
                )
                with dpg.tooltip(next_btn):
                    dpg.add_text("Go to next card")
                    dpg.add_text("Shortcut: Right Arrow")

            dpg.add_spacer(height=5)
            dpg.add_text("Card info", tag=self.dpg_card_info_text_tag)

        self.load_data()  # Load and display the first card

    def load_data(self):
        self.cards.clear()
        if self.data_path.exists() and self.data_path.stat().st_size > 0:
            try:
                raw_data = json.loads(self.data_path.read_text(encoding="utf-8"))
                if isinstance(raw_data, list):
                    for card_data in raw_data:
                        try:
                            self.cards.append(Flashcard(**card_data))
                        except ValidationError as e:
                            print(
                                f"Skipping a flashcard due to validation error: {e.errors()}"
                            )
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {self.data_path} for flashcards.")

        self.current_card_index = 0
        self.is_answer_visible = False  # Reset visibility on load
        if dpg.is_dearpygui_running():  # Ensure DPG is ready for UI updates
            self._dpg_display_current_card()
        else:
            # If DPG isn't running (e.g. initial setup), _dpg_display_current_card will be called from build_dpg_view after load_data
            pass

    def _dpg_display_current_card(self):
        if (
            not dpg.does_item_exist(self.dpg_question_text_tag)
            or not dpg.does_item_exist(self.dpg_answer_text_tag)
            or not dpg.does_item_exist(self.dpg_card_info_text_tag)
            or not dpg.does_item_exist(self.dpg_flip_button_tag)
        ):
            # print("Flashcard DPG items not ready for display update.")
            return

        if not self.cards:
            dpg.set_value(self.dpg_question_text_tag, "No flashcards loaded.")
            dpg.set_value(
                self.dpg_answer_text_tag,
                "Please add flashcards to data/flashcards.json",
            )
            dpg.set_value(self.dpg_card_info_text_tag, "Card 0 of 0")
            dpg.configure_item(self.dpg_flip_button_tag, label="Flip")
            return

        card = self.cards[self.current_card_index]
        dpg.set_value(self.dpg_question_text_tag, card.question)

        if self.is_answer_visible:
            dpg.set_value(self.dpg_answer_text_tag, card.answer)
            dpg.configure_item(self.dpg_flip_button_tag, label="Hide Answer")
        else:
            dpg.set_value(self.dpg_answer_text_tag, "(Click 'Flip' or 'Show Answer')")
            dpg.configure_item(self.dpg_flip_button_tag, label="Show Answer")

        dpg.set_value(
            self.dpg_card_info_text_tag,
            f"Card {self.current_card_index + 1} of {len(self.cards)}",
        )

    def _dpg_flip_card(self, sender=0, app_data=0, user_data=0):
        if not self.cards:
            return
        self.is_answer_visible = not self.is_answer_visible
        self._dpg_display_current_card()

    def _dpg_next_card(self, sender=0, app_data=0, user_data=0):
        if not self.cards:
            return
        self.current_card_index = (self.current_card_index + 1) % len(self.cards)
        self.is_answer_visible = False  # Hide answer when moving to next card
        self._dpg_display_current_card()

    def _dpg_prev_card(self, sender=0, app_data=0, user_data=0):
        if not self.cards:
            return
        self.current_card_index = (self.current_card_index - 1 + len(self.cards)) % len(
            self.cards
        )
        self.is_answer_visible = False  # Hide answer when moving to previous card
        self._dpg_display_current_card()

    def handle_keyboard(self, key_code: int):
        # Empirical key codes from your system
        LEFT_ARROW = 512
        RIGHT_ARROW = 513
        SPACE = 532

        if key_code == SPACE:
            self._dpg_flip_card()
        elif key_code == LEFT_ARROW:
            self._dpg_prev_card()
        elif key_code == RIGHT_ARROW:
            self._dpg_next_card()

    def get_focusable_items(self):
        return [self.dpg_flip_button_tag]

    def _update_card_callback(self, sender=0, app_data=0, user_data=0):
        pass

    def _delete_card_callback(self, sender=0, app_data=0, user_data=0):
        pass

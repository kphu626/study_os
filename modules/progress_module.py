import dearpygui.dearpygui as dpg
import json
from pathlib import Path
from typing import TYPE_CHECKING, Union, Optional
from pydantic import ValidationError

from .base_module import BaseModule
from schemas import ProgressData

if TYPE_CHECKING:
    from core.app import Core


class ProgressModule(BaseModule):
    def __init__(self, core: "Core"):
        super().__init__(core)
        if (
            hasattr(self.core, "config")
            and self.core.config is not None
            and hasattr(self.core.config, "progress_path")
        ):
            self.data_path = self.core.config.progress_path
        else:
            self.data_path = Path("data/progress.json")
            print(f"Warning: ProgressModule using default data_path: {self.data_path}")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        self.progress_data: Optional[ProgressData] = None

        # DPG chart item tags - initialize with placeholders
        self.dpg_plot_tag: Union[int, str] = 0
        self.dpg_xaxis_tag: Union[int, str] = 0
        self.dpg_yaxis_tag: Union[int, str] = 0
        self.dpg_line_series_tag: Union[int, str] = 0
        self.dpg_status_text_tag: Union[int, str] = 0  # For messages

    def build_dpg_view(self, parent_container_tag: str):
        """Builds the Dear PyGui view for the Progress module."""
        self.dpg_plot_tag = dpg.generate_uuid()
        self.dpg_xaxis_tag = dpg.generate_uuid()
        self.dpg_yaxis_tag = dpg.generate_uuid()
        self.dpg_line_series_tag = dpg.generate_uuid()
        self.dpg_status_text_tag = dpg.generate_uuid()

        with dpg.group(parent=parent_container_tag):
            dpg.add_text("Study Progress", color=(220, 220, 220))
            dpg.add_separator()
            self.dpg_status_text_tag = dpg.add_text(
                "Loading progress data...", tag=self.dpg_status_text_tag
            )

            # Plot takes full width and available height
            plot = dpg.add_plot(
                label="Progress Over Time",
                tag=self.dpg_plot_tag,
                height=-1,
                width=-1,
                no_title=True,
            )
            with dpg.tooltip(plot):
                dpg.add_text("Interactive progress chart")
                dpg.add_text("Click+drag to pan, scroll to zoom")
                dpg.add_text("Right-click for context menu")

            self.dpg_xaxis_tag = dpg.add_plot_axis(
                dpg.mvXAxis, label="Day Index", tag=self.dpg_xaxis_tag
            )
            # dpg.set_axis_limits_auto(self.dpg_xaxis_tag) # Auto-fit X axis

            self.dpg_yaxis_tag = dpg.add_plot_axis(
                dpg.mvYAxis, label="Score", tag=self.dpg_yaxis_tag
            )
            # dpg.set_axis_limits_auto(self.dpg_yaxis_tag) # Auto-fit Y axis

            # Initial empty data for the line series
            self.dpg_line_series_tag = dpg.add_line_series(
                [],
                [],
                label="Scores",
                parent=self.dpg_yaxis_tag,
                tag=self.dpg_line_series_tag,
            )

        self.load_data()  # Load data and update chart

    def load_data(self):
        """Loads progress data from file and updates the DPG chart."""
        if self.data_path.exists() and self.data_path.stat().st_size > 0:
            try:
                raw_data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.progress_data = ProgressData(**raw_data)  # Parse with Pydantic
                if dpg.does_item_exist(self.dpg_status_text_tag):
                    dpg.set_value(
                        self.dpg_status_text_tag,
                        f"Loaded {len(self.progress_data.history)} progress entries.",
                    )
            except json.JSONDecodeError:
                self.progress_data = None
                if dpg.does_item_exist(self.dpg_status_text_tag):
                    dpg.set_value(
                        self.dpg_status_text_tag,
                        f"Error decoding JSON from {self.data_path}",
                    )
                print(f"Error decoding JSON from {self.data_path}")
            except ValidationError as e:
                self.progress_data = None
                if dpg.does_item_exist(self.dpg_status_text_tag):
                    dpg.set_value(
                        self.dpg_status_text_tag, f"Validation Error: {e.errors()}"
                    )
                print(f"Progress data validation error: {e.errors()}")
            except Exception as e:
                self.progress_data = None
                if dpg.does_item_exist(self.dpg_status_text_tag):
                    dpg.set_value(
                        self.dpg_status_text_tag,
                        f"Unexpected error loading progress: {e}",
                    )
                print(f"Unexpected error loading progress: {e}")
        else:
            self.progress_data = None
            if dpg.does_item_exist(self.dpg_status_text_tag):
                dpg.set_value(
                    self.dpg_status_text_tag,
                    f"Progress data file not found: {self.data_path}",
                )
            print(f"Progress data file not found: {self.data_path}")

        if dpg.is_dearpygui_running():  # Check if DPG context is active
            self._dpg_update_chart()
        else:
            # If DPG isn't running (e.g. initial setup), _dpg_update_chart will be called via load_data from build_dpg_view
            pass

    def _dpg_update_chart(self):
        """Updates the DPG plot with data from self.progress_data."""
        if (
            not dpg.does_item_exist(self.dpg_line_series_tag)
            or not dpg.does_item_exist(self.dpg_xaxis_tag)
            or not dpg.does_item_exist(self.dpg_yaxis_tag)
        ):
            # print("Progress DPG plot items not ready for update.")
            return

        x_data = []
        y_data = []

        if self.progress_data and self.progress_data.history:
            # For X-axis, let's use simple indices for now for simplicity.
            # Using actual dates on X-axis requires dpg.set_axis_ticks with (label, value) pairs.
            x_data = [float(i) for i in range(len(self.progress_data.history))]
            y_data = [float(entry.score) for entry in self.progress_data.history]
            if dpg.does_item_exist(self.dpg_status_text_tag):
                dpg.set_value(
                    self.dpg_status_text_tag, f"Plotting {len(y_data)} data points."
                )
        else:
            if dpg.does_item_exist(self.dpg_status_text_tag):
                dpg.set_value(self.dpg_status_text_tag, "No progress data to plot.")

        dpg.set_value(self.dpg_line_series_tag, [x_data, y_data])

        # Auto-fit axes after setting data
        # Check if items exist before trying to fit axes, especially if data is empty
        if dpg.does_item_exist(self.dpg_xaxis_tag):
            dpg.fit_axis_data(self.dpg_xaxis_tag)
        if dpg.does_item_exist(self.dpg_yaxis_tag):
            dpg.fit_axis_data(self.dpg_yaxis_tag)

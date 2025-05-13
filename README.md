# StudyOS

StudyOS is a desktop application built with Dear PyGui, designed to help users manage their study-related activities.

## Features

Currently, StudyOS includes the following modules:

* **Notes**: Create and save notes. (Basic Dear PyGui UI implemented)
* **Flashcards**: Review flashcards. (Placeholder Dear PyGui UI)
* **Tasks**: Manage a to-do list. (Placeholder Dear PyGui UI)
* **Progress**: Visualize study progress. (Placeholder Dear PyGui UI)
* **Statistics**: View summary statistics. (Placeholder Dear PyGui UI)
* **Settings**: Customize the application. (Placeholder Dear PyGui UI, DPG theming TBD)

## Tech Stack

* Python
* Dear PyGui (for the user interface)
* Pydantic (for data validation)

## Getting Started

### Prerequisites

* Python 3.8 or higher
* Pip (Python package installer)

### Installation & Running

1. Clone the repository:

    ```bash
    git clone <your-repository-url>
    cd study_os
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Run the application:

    ```bash
    python main.py
    ```

## Project Structure

* `main.py`: Main application entry point.
* `core/`: Core application logic, including the main `StudyOS` class.
* `modules/`: Contains individual feature modules (Notes, Tasks, etc.).
  * `base_module.py`: A base class for all UI modules.
* `schemas/`: Pydantic schemas for data validation.
* `data/`: Default directory for storing JSON data files for modules.
* `interface/`: (Experimental) Contains advanced UI and backend processing concepts.
* `themes/`: This directory previously held Flet themes and should be removed or is pending removal. Dear PyGui theming is handled differently.

## Future Ideas (from experimental files)

The `interface/` directory contains experimental code for:

* A "Morphic Interface" / "Neural Canvas".
* A "Cognitive Optimizer" for code architecture.

These are not currently integrated into the main application.

---

*(Add more sections as needed, e.g., How to Contribute, License)*

# KFM Sprint 1 - Self-Assembling Agentic AI MVP

This project is the Minimum Viable Product (MVP) for exploring the 'Kill, Fuck, Marry' (KFM) paradigm for self-assembling AI agents.

## Project Structure

- `docs/`: Contains project documentation (e.g., PRD, design notes).
- `notebooks/`: (Optional) Jupyter notebooks for experimentation.
- `scripts/`: Contains utility scripts (e.g., PRD generation, data processing).
- `src/`: Contains the main source code for the KFM agent.
- `tasks/`: Contains task definitions and generated task files managed by Task Master AI.
- `tests/`: Contains unit and integration tests.
- `.gitignore`: Specifies intentionally untracked files that Git should ignore.
- `requirements.txt`: Lists the project's Python dependencies.
- `README.md`: This file.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd KFM_Sprint1
    ```
2.  **Create and activate the virtual environment:**
    ```bash
    # Create the virtual environment (if it doesn't exist)
    python -m venv venv

    # Activate the environment
    # On macOS/Linux:
    source venv/bin/activate
    # On Windows:
    # .\venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Documentation

Key documentation for the project:

- [KFM Paradigm Design](docs/design_notes/kfm_paradigm.md) - Detailed explanation of the Kill, Fuck, Marry component management strategy.
- [Reflection Node Implementation](docs/reflection_node.md) - Documentation for the reflection node component
- [Reflection Prompt Template](docs/reflection_prompt_template.md) - Detailed guide for the LLM reflection prompt template
- [Reflection Prompt Design Notes](docs/design_notes/reflection_prompt_design.md) - Design decisions and considerations for the reflection prompt template

## KFM Paradigm

This project implements the Kill, Fuck, Marry (KFM) paradigm for dynamic AI component management:

*   **Marry:** Integrate the best component for long-term use.
*   **Fuck:** Temporarily use a sub-optimal component when no ideal one is available.
*   **Kill:** Remove or deactivate underperforming/obsolete components.

For a detailed explanation, see the [KFM Paradigm Design Document](docs/design_notes/kfm_paradigm.md).

## Usage

(To be added later)

## Contributing

(To be added later) 
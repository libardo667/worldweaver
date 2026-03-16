# Gemini Context for WorldWeaver

This document provides a summary of the WorldWeaver project to be used as instructional context for future interactions.

## Project Overview

WorldWeaver is a multi-component, persistent shared world platform. It is grounded in real geography and populated by autonomous AI residents. Human players can interact with this world and its AI inhabitants. The project is structured as a monorepo containing several distinct but related parts.

### Core Components

*   `worldweaver_engine/`: This is the main application, containing the backend server, the web client, and world administration tools.
    *   **Backend:** A Python application built with FastAPI, SQLAlchemy, and Alembic for database migrations. It serves the main API for the world state, narration, and player actions.
    *   **Client:** A single-page application built with React, TypeScript, and Vite.
*   `ww_agent/`: A separate Python application that runs the AI "residents". It connects to the `worldweaver_engine` via its HTTP API and manages the cognitive loops of the AI agents.
*   `shards/`: Contains data and configurations for different "worlds" or geographical areas, such as San Francisco (`ww_sfo`) and Portland (`ww_pdx`).
*   `worldweaver_artifacts/`: Stores local-only outputs and archived materials, and is not part of the primary source code.

## Key Technologies

*   **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Alembic
*   **Frontend:** React, TypeScript, Vite, Leaflet.js
*   **AI/LLM:** Configurable integration with models like OpenAI and Gemini.
*   **Database:** SQLite for local development, likely configurable for production.
*   **Containerization:** Docker and Docker Compose are used for running the full stack.
*   **CI/CD:** GitHub Actions are used for continuous integration, running tests and static analysis.
*   **Code Quality:** `ruff` for linting and `black` for formatting.
*   **Testing:** `pytest` for backend testing.

## Development Workflow

The project uses a centralized script, `worldweaver_engine/scripts/dev.py`, to manage common development tasks.

### Initial Setup

To install all backend and frontend dependencies, run the following command from the `worldweaver_engine` directory:

```bash
python scripts/dev.py install
```

### Running the Application

The preferred method for running the local development environment is using the Docker Compose wrapper script. This command will start the `worldweaver_engine` backend, the `ww_agent` service, and the client for a specific world shard.

To start the stack for the San Francisco shard (`ww_sfo`):

```bash
# From the worldweaver_engine/ directory
python scripts/dev.py weave-up --city ww_sfo
```

The web client will be available at `http://localhost:5173`.

To stop the services:
```bash
python scripts/dev.py weave-down --city ww_sfo
```

### Running Tests

To run the backend test suite using `pytest`, use this command from the `worldweaver_engine` directory:

```bash
python scripts/dev.py test
```

For a stricter check that mirrors the CI process:
```bash
python scripts/dev.py quality-strict
```

### Linting and Formatting

To run the linter (`ruff`) and formatter (`black`) across the Python codebase, use this command from the `worldweaver_engine` directory:

```bash
python scripts/dev.py lint-all
```

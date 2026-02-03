# AGENTS.md

Instructions for AI agents working in this repository.

## Project overview
- DrupalBench is a Drupal 11–focused LLM benchmark that mines Drupal issues, generates synthetic tasks, evaluates model patches inside a Dockerized Drupal environment, and visualizes results with a React + Vite dashboard.

## Repository layout (high signal)
- `bench-init.sh`: one-time environment bootstrap (Docker up, Drupal install, Drush, phpunit config, initial git commit inside container).
- `docker-compose.yml`, `Dockerfile`: evaluation runtime; app lives in `./app` and is mounted into the container.
- `scripts/evaluate.py`: runs model evaluations, applies patches in the container, runs PHPUnit, writes `results.json`.
- `scripts/mine_issues.py`: mines Drupal.org issues into `tasks.json`.
- `scripts/phase5/task_generator.py`: creates `synthetic_tasks.json`.
- `scripts/filter_tasks.py`, `scripts/filter_synthetic_tasks.py`: validate tasks in container and write filtered outputs.
- `scripts/update_frontend.py`: transforms `results.json` into `frontend/src/data/results.json` and runs a frontend build.
- `frontend/`: React + Vite dashboard.
- `app/`: Drupal 11 codebase created by `bench-init.sh` (mounted into the container).

## Environment + dependencies
- Requires Docker + Docker Compose, Python 3, and Node.js + npm for the frontend.
- Network access is required for issue mining and synthetic task generation.
- Model evaluation reads `.env` in the repo root. Common keys: `MODEL_PROVIDER`, `MODEL_NAME`, `GEMINI_API_KEY`, `OLLAMA_HOST`.

## Common workflows
- Initialize environment (first time):
  - `./bench-init.sh`
- Run evaluation:
  - `python scripts/evaluate.py`
  - `python scripts/evaluate.py --samples 3`
  - `python scripts/evaluate.py --task_id 123456`
- Mine real issues:
  - `python scripts/mine_issues.py`
- Generate synthetic tasks:
  - `python scripts/phase5/task_generator.py --limit 5`
- Update frontend data + build:
  - `python scripts/update_frontend.py`
- Frontend dev server:
  - `cd frontend && npm install && npm run dev`

## Data files (do not hand-edit unless asked)
- `tasks.json`: real tasks from Drupal.org mining.
- `synthetic_tasks.json`: generated tasks.
- `results.json`: evaluation output used by the frontend.
- `frontend/src/data/results.json`: derived from `results.json` via `scripts/update_frontend.py`.

## Working conventions for agents
- Prefer using the provided scripts instead of manually editing benchmark data files.
- `app/` is a full Drupal install and can be large; only touch it when the task explicitly requires code changes within Drupal core or modules.
- Evaluation runs inside the Docker container (`docker-compose exec -T drupal ...`); keep host-side changes in sync with container expectations.
- When making patches for Drupal tasks, ensure diffs are standard `git apply -p1` compatible with `a/` and `b/` prefixes (matches `scripts/evaluate.py` assumptions).
- Frontend is Vite + React; follow existing file structure and TypeScript settings if editing.


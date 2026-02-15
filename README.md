# DrupalBench

DrupalBench is a Drupal 11–focused LLM benchmark. It mines real Drupal issues, generates synthetic tasks, evaluates model patches in a Dockerized Drupal environment, and visualizes results in a React dashboard.

## Requirements

- Docker + Docker Compose
- Python 3 + `pip`
- Node.js + npm (for the frontend)
- Internet access (for issue mining and synthetic task generation)

## Repository layout

- `bench-init.sh`: one-time environment bootstrap (Drupal install + test setup)
- `docker-compose.yml`, `Dockerfile`: evaluation runtime
- `scripts/evaluate.py`: run model evaluations and produce `results.json`
- `scripts/mine_issues.py`: mine Drupal.org issues into `tasks.json`
- `scripts/phase5/task_generator.py`: generate `synthetic_tasks.json`
- `scripts/update_frontend.py`: write results into `frontend/src/data/results.json` and build
- `frontend/`: React + Vite dashboard

## Quick start (environment setup)

1) Start the containers and install Drupal 11 in `app/`:

```bash
./bench-init.sh
```

2) Create a `.env` for model evaluation (example):

```bash
MODEL_PROVIDER=gemini
MODEL_NAME=gemini-3-flash-preview
GEMINI_API_KEY=your_api_key_here
# or for OpenAI
# MODEL_PROVIDER=openai
# MODEL_NAME=gpt-4.1-mini
# OPENAI_API_KEY=your_api_key_here
# or for local Ollama
# MODEL_PROVIDER=ollama
# MODEL_NAME=llama3.1
# OLLAMA_HOST=http://localhost:11434
```

## Run the evaluation script

`evaluate.py` reads `tasks.json` and `synthetic_tasks.json`, calls the model, applies patches inside the Dockerized Drupal repo, and runs PHPUnit where possible. Output is written to `results.json`.

Examples:

```bash
python scripts/evaluate.py
```

```bash
python scripts/evaluate.py --samples 3
```

```bash
python scripts/evaluate.py --task_id 123456
```

Notes:

- A running Docker environment is required (`./bench-init.sh`).
- Evaluation calls out to the configured model provider in `.env`.
- `results.json` is updated after each task, so partial runs still produce data.

## Mine issues (real tasks)

`mine_issues.py` pulls Drupal.org issues, locates the related GitLab merge request, and stores the issue prompt + ground-truth diff in `tasks.json`.

```bash
python scripts/mine_issues.py
```

Notes:

- The script calls the Drupal.org API and Drupal GitLab API, so network access is required.
- It targets Drupal core and related projects (see `scripts/mine_issues.py`).
- It only keeps issues whose MRs include PHPUnit test changes.

## Generate synthetic tasks

`task_generator.py` scrapes Drupal change records and uses the model provider to synthesize tasks and ground-truth patches into `synthetic_tasks.json`.

```bash
python scripts/phase5/task_generator.py --limit 5
```

Notes:

- Requires a configured model provider in `.env` (same as evaluation).
- Uses Drupal change record pages as input context.

### Optional: filter tasks that don’t apply

```bash
python scripts/filter_tasks.py
python scripts/filter_synthetic_tasks.py
```

These scripts apply patches inside the Docker container and write filtered outputs to `tasks_filtered.json` and `synthetic_tasks_filtered.json`.

## Update the frontend

`update_frontend.py` transforms `results.json` into `frontend/src/data/results.json` and runs a production build.

```bash
python scripts/update_frontend.py
```

Notes:

- Requires Node.js + npm and installed frontend dependencies.
- If you haven’t installed frontend deps yet:

```bash
cd frontend
npm install
```

## Run the frontend locally

```bash
cd frontend
npm install
npm run dev
```

The dashboard reads `frontend/src/data/results.json`, which is updated by `scripts/update_frontend.py`.

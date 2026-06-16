# Repository Guidelines

## Project Structure & Module Organization

This repository contains project documentation, a static UI prototype, and the `third` Python service.

- `README.md` links the main documentation entry points.
- `docs/` contains product, API, database, architecture, and activity-flow documents.
- `docs/ui/` contains the static UI prototype: `index.html`, `app.js`, `styles.css`, and UI flow docs.
- `third/` contains the Python workflow service, including `agents/`, `workflow/`, `Tool/`, `Prompt/`, `storage/`, `runtime/`, `migrations/`, and `tests/`.
- `docker-compose.yml` starts local MySQL and Redis, plus optional `third` service containers.

## Build, Test, and Development Commands

Run commands from the repository root unless noted.

```powershell
docker compose up -d
```
Starts local MySQL on `3307` and Redis on `6380`.

```powershell
Copy-Item third/.env.local.docker.example third/.env
pip install -r third/requirements.txt
alembic upgrade head
python -m third.scripts.seed_runagent_prompts
```
Prepares the local Python service and syncs `Prompt/runagent/*.yaml` into `prompt_registry`.

```powershell
uvicorn third.api:app --host 0.0.0.0 --port 8001 --reload
python -m third.worker
```
Runs the API and async worker locally.

```powershell
python -m unittest discover third\tests
```
Runs the Python test suite.

## Coding Style & Naming Conventions

Python code targets Python 3.10+. Use 4-space indentation, type hints where practical, `snake_case` for functions and modules, and `PascalCase` for classes. Preserve the existing direct, explicit style and avoid broad refactors during feature work. Tool files use the pattern `third/Tool/tool_<Capability>.py`; runagent prompts use versioned keys such as `parse_feishu_record.v1.yaml`.

## Testing Guidelines

Tests use `unittest` and live in `third/tests/`. Name files `test_*.py` and keep tests close to the behavior being changed. For workflow changes, cover registry consistency, template output, validator failures, and mock Tool execution. For prompt changes, update YAML, run the seed command, and test the output contract.

## Commit & Pull Request Guidelines

Recent commits use short Chinese summaries without a strict prefix. Keep messages concise, imperative, and scoped, for example `优化workflow模板注册`. Pull requests should state the changed area, list verification commands, and note any required env or migration steps. Include screenshots only for visible `docs/ui/` changes.

## Security & Configuration Tips

Do not commit real `.env` files, Feishu credentials, OpenAI keys, MySQL DSNs, or Redis URLs. Use `.env.example`, `.env.local.docker.example`, `.env.docker.mock`, and `.env.docker.real.example` as templates. Keep `THIRD_DEBUG_ENABLED=0` outside local development.

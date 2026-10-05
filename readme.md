# ACP dev environment

Runs the Automated Curation Platform (ACP) and the services it depends on in Docker, so nothing has to be installed on the host except Docker. Source code is bind-mounted, so edits are picked up without rebuilding.

## Services

| Service      | What it is                                         | Port  |
|--------------|----------------------------------------------------|-------|
| `acp`        | Automated Curation Platform (FastAPI)              | 10124 |
| `acp-worker` | RQ worker that consumes the `acp-deposit` queue    | -     |
| `aca`        | Repository Assistant Service (serves app configs)  | 2810  |
| `mts`        | Metadata Transformation Service                    | -     |
| `db`         | Postgres 15                                        | -     |
| `redis`      | Redis 7 (job queue)                                | -     |

## Layout

```
acp-dev/
├── compose.yaml
├── Dockerfile.dev        # shared by acp, aca and mts
├── worker_dev.py         # minimal RQ worker with logging
├── .env.example          # copy to .env.development
├── acp/                  # git submodule
├── aca/                  # git submodule
└── mts/                  # git submodule
```

## Setup

```bash
git clone --recurse-submodules git@github.com:Dans-labs/acp-stack-dev.git acp-dev
cd acp-dev
cp .env.example .env.development
# edit .env.development: set DB_USER, DB_PASSWORD, DB_ENCRYPTION_KEY, ...
# Also, in every submodule, create and edit a conf/.secrets.toml file
cp ./aca/conf/.secrets.toml.sample ./aca/conf/.secrets.toml
cp ./acp/conf/.secrets.toml.sample ./acp/conf/.secrets.toml
cp ./mts/conf/.secrets.toml.sample ./mts/conf/.secrets.toml
docker compose --env-file .env.development up --build
```

If you cloned without `--recurse-submodules`, run `git submodule update --init`.

Generate a valid `DB_ENCRYPTION_KEY` (Fernet key) with:

```bash
docker compose --env-file .env.development run --rm acp \
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Important: the worker must be running

ACP does not perform the Dataverse deposit itself. `POST /inbox/dataset/SUBMIT` only puts a job on the `acp-deposit` queue in Redis and returns 200. The `acp-worker` service picks it up and does the actual deposit.

If the worker is not running, requests succeed but nothing arrives in Dataverse; the jobs just sit in Redis until a worker starts.

Worker logs: `docker compose logs -f acp-worker`

## Live reload

- `acp`, `aca`, `mts`: restart automatically when `.py` files under `src/` change (watchfiles, polling mode).
- `acp-worker`: does **not** auto-restart. After changing deposit code run `docker compose restart acp-worker`.
- Changes to `conf/` files are not watched; restart the service manually.

## Configuration notes

- Containers reach each other by service name. `localhost` inside a container is the container itself, so URLs must use `aca`, `redis`, `db`, etc.
- Env vars that matter, set in `compose.yaml` / `.env.development` or in the respective subrepo's `conf/.secrets.toml`:
  - `ASSISTANT_CONFIG_URL=http://aca:2810`
  - `REDIS_URL=redis://redis:6379/0`
  - `DB_*` (host `db`, port 5432)
  - `DB_ENCRYPTION_KEY`
- `WATCHFILES_FORCE_POLLING=true` avoids hitting the host inotify watch limit.
- OpenTelemetry warnings about `localhost:4317` are harmless (no collector). Silence with `OTEL_SDK_DISABLED=true`.

## Useful commands

```bash
# start / stop
docker compose --env-file .env.development up -d --build
docker compose --env-file .env.development down        # keeps the DB volume
docker compose --env-file .env.development down -v     # also wipes the DB

# logs
docker compose logs -f acp acp-worker

# inspect the queue
docker compose exec redis redis-cli keys 'rq:*'
docker compose exec redis redis-cli llen rq:queue:acp-deposit

# dev only: clear all queued/failed jobs
docker compose exec redis redis-cli flushall
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Request returns 200 but nothing in Dataverse | Worker not running, check `acp-worker` logs |
| `Error 111 connecting to localhost:6379` | `REDIS_URL` not set to `redis://redis:6379/0` |
| `Connection refused ... localhost:2810` on startup | `ASSISTANT_CONFIG_URL` not set to `http://aca:2810` |
| `OS file watch limit reached` | Keep `WATCHFILES_FORCE_POLLING=true` |
| Re-submitting a dataset does nothing | Old job with the same ID in Redis; `redis-cli flushall` (dev only) |
| Upstream `Dockerfile-dev` fails with apt 404s | It targets Debian 11 + Poetry (outdated); use `Dockerfile.dev` here |

## Updating upstream code

```bash
git submodule update --remote acp   # or aca / mts
git add acp && git commit -m "Bump acp"
```
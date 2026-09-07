# Development Stack

The development stack (`docker-compose.dev.yml`) mounts the source tree for live
reload, runs a Vite dev server for the UI, and includes Flower for Celery
monitoring.

## Step 1 — Create `.env.dev`

The dev compose file reads **`.env.dev`** (not `.env`):

```bash
cp env.sample .env.dev
```

## Step 2 — Configure the database

The dev stack runs a MariaDB service whose container must pass a health check
before the API starts. That requires database credentials, so set the following
in `.env.dev`:

```dotenv
DB_ENGINE=mysql
MYSQL_USER=devify
MYSQL_PASSWORD=devify
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=devify
MYSQL_ROOT_PASSWORD=devify_root
```

> **Why this matters:** `env.sample` defaults to `DB_ENGINE=sqlite` with the
> MySQL block commented out. If `MYSQL_ROOT_PASSWORD` is unset, the MariaDB
> container exits with *"Database is uninitialized and password option is not
> specified"* and crash-loops, and the API never starts because it waits on the
> database's health check.

See [Database](/en/self-hosting/configuration/database.md) for all engine
options.

## Step 3 — Install UI dependencies

The dev compose mounts the host's `ui/node_modules` into the UI container, so
dependencies must be installed on the host first — otherwise the container fails
with `sh: vite: not found`:

```bash
cd ui && npm install && cd ..
```

## Step 4 — Build and start

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

> **Important — `--env-file .env.dev`:** the `env_file:` entries in the compose
> file only inject variables **inside** the containers. Port mappings like
> `${DJANGO_HOST_PORT}` and `${FLOWER_HOST_PORT}` are interpolated from the
> project's default `.env` or the shell, **not** from `env_file`. Passing
> `--env-file .env.dev` makes your custom ports (and any other interpolated
> values) take effect. Without it, ports fall back to their defaults.

## Development ports

| Service | Default host port | Variable |
|---------|-------------------|----------|
| App (via Nginx → UI + API) | `8000` | `DJANGO_HOST_PORT` |
| Flower (Celery monitoring) | `5555` | `FLOWER_HOST_PORT` |
| Haraka (inbound SMTP) | `25` | `HARAKA_SMTP_PORT` |

If a port is already in use on your host, change the corresponding variable in
`.env.dev` and re-run the `up` command with `--env-file .env.dev`.

## Verify

```bash
docker compose -f docker-compose.dev.yml ps          # all services healthy/up
curl -f http://127.0.0.1:8000/health                 # HTTP 200
```

Next: [First run](./first-run.md).

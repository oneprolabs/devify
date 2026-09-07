# Deployment Overview

Devify is open source and self-hostable. This section takes you from a fresh
clone to a running stack — for both local development and self-hosted
production. It assumes basic familiarity with Docker and the command line.

## Prerequisites

- **Docker** and **Docker Compose v2** (`docker compose`, not the legacy
  `docker-compose`).
- **Node.js 18+** and **npm** — only needed for the development stack (the UI
  runs a Vite dev server on the host's `node_modules`).
- **Git**.
- At least one supported **LLM provider** account with API credentials,
  including a **multimodal** model (required for image understanding and intent
  detection).
- An **SMTP server** for outbound notifications.

## Minimum host resources

| Resource | Minimum |
|----------|---------|
| CPU | 2 cores |
| RAM | 4 GB |
| Storage | 20 GB |

## Get the code

```bash
git clone https://github.com/cloud2ai/devify.git
cd devify
```

Repository layout (top level):

```text
devify/                 # Django backend (the app code lives here)
ui/                     # Vue 3 frontend (Vite)
docker/                 # Service configs (Haraka, Nginx, MySQL)
docker-compose.yml      # Production stack
docker-compose.dev.yml  # Development stack
env.sample              # Environment template
```

## Choose a stack

All configuration is driven by an environment file copied from `env.sample`.
The file name differs by stack:

| Stack | Env file | Compose file | Guide |
|-------|----------|--------------|-------|
| Development | `.env.dev` | `docker-compose.dev.yml` | [Development](./development.md) |
| Production | `.env` | `docker-compose.yml` | [Production](./production.md) |

> **Boolean values must be lowercase `true` / `false`.**

Once the stack is running, continue with [First run](./first-run.md) to create
the admin user and connect your models. For all environment variables, see the
[Configuration](/en/self-hosting/configuration/environment.md) section.

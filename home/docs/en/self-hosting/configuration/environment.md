# Environment Variables

All configuration is driven by an environment file copied from `env.sample`
(`.env.dev` for development, `.env` for production). **Boolean values must be
lowercase `true` / `false`.** This page is the grouped reference; the deeper
topics have their own pages.

## Django / runtime

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret key — change for production |
| `DJANGO_DEBUG` | `true` for dev, `false` for production |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | Origins allowed to call the API |
| `SITE_DOMAIN`, `SITE_NAME` | Public site domain (no protocol) — used for OAuth and webhooks |
| `FRONTEND_URL`, `VITE_API_BASE_URL` | Frontend URL and the API base the frontend calls |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | Auto-created superuser on first run |

## Database

Select an engine with `DB_ENGINE`. See [Database](./database.md) for details.

## Celery / Redis / cache

| Variable | Purpose |
|----------|---------|
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Point to `redis://redis:6379/0` |
| `CELERY_CONCURRENCY`, `CELERY_LOG_LEVEL` | Worker tuning |
| `CACHE_BACKEND` | `redis` |
| `FLOWER_HOST_PORT` | Flower monitoring port (dev) |

## Email / notifications

See [Email & notifications](./email-notifications.md).

| Variable | Purpose |
|----------|---------|
| `EMAIL_BACKEND` | `smtp` backend for production, `console` for dev |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | Outbound SMTP for notifications |
| `DEFAULT_FROM_EMAIL` | From address |
| `AUTO_ASSIGN_EMAIL_DOMAIN` | Domain for auto-assigned inbound mailboxes (Haraka) |
| `HARAKA_SMTP_PORT`, `HARAKA_EMAIL_BASE_DIR` | Inbound SMTP settings |

## OAuth (optional)

See [OAuth login](./oauth.md).

| Variable | Purpose |
|----------|---------|
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google login |
| `ACCOUNT_DEFAULT_HTTP_PROTOCOL` | `http` for dev, `https` for production |

## AI models / providers

`env.sample` includes legacy Azure OpenAI variables (`AZURE_OPENAI_*`), but
**model providers are configured in the management console after startup**, not
primarily through `.env`. See
[LLM providers](./llm-providers.md).

## Monitoring (optional)

`SENTRY_*` and `VITE_SENTRY_*` — leave empty to disable Sentry.

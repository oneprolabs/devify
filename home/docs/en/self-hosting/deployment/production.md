# Production Stack

The production stack (`docker-compose.yml`) uses prebuilt images and fronts the
app with Nginx.

## Step 1 — Create `.env`

```bash
cp env.sample .env
```

Set production values, at minimum:

- `DJANGO_DEBUG=false`, a strong `SECRET_KEY`
- `ALLOWED_HOSTS`, `SITE_DOMAIN`, `FRONTEND_URL`, `VITE_API_BASE_URL`,
  `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`
- Database: `DB_ENGINE=mysql` with `MYSQL_HOST=mysql` and a strong
  `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD`
- `EMAIL_*` for outbound notifications
- `AUTO_ASSIGN_EMAIL_DOMAIN` if you use inbound email
- `ACCOUNT_DEFAULT_HTTP_PROTOCOL=https`

For the full variable reference, see
[Configuration](/en/self-hosting/configuration/environment.md).

## Step 2 — Build and start

```bash
docker compose build
docker compose up -d
```

The production stack includes: API (gunicorn), worker, scheduler, UI, Nginx,
MariaDB, Redis, and Haraka.

## Production ports

Nginx publishes the app; put your own HTTPS reverse proxy in front of it.

| Variable | Default | Purpose |
|----------|---------|---------|
| `NGINX_HTTP_PORT` | `10080` | HTTP entry point |
| `NGINX_HTTPS_PORT` | `10443` | HTTPS entry point |
| `NGINX_ADMIN_PORT` | `19443` | Admin |
| `HARAKA_SMTP_PORT` | `25` | Inbound SMTP |

## HTTPS

For HTTPS, terminate TLS at a reverse proxy such as **Nginx Proxy Manager**,
**Traefik**, or **Caddy**, and forward to `NGINX_HTTP_PORT`.

Next: [Inbound email (Haraka)](./haraka.md) and [First run](./first-run.md).
